from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def default_get(self, fields_list):
        return self._domex_filter_category_default(super().default_get(fields_list))

    @api.model
    def _domex_filter_category_default(self, values):
        category_id = values.get("categ_id")
        if category_id and not self.env["product.category"].search(
            [("id", "=", category_id)], limit=1,
        ):
            values["categ_id"] = False
        return values

    def _read_group_categ_id(self, categories, domain):
        expanded = super()._read_group_categ_id(categories, domain)
        # Native group expansion uses sudo; exclude inaccessible empty groups.
        return self.env["product.category"].search([("id", "in", expanded.ids)])

    @api.model
    def _domex_can_configure_all_warehouses(self):
        return self.env.su or self.env.user.has_group("base.group_system")

    @api.model
    def _domex_available_warehouses(self, company_id=False):
        # Validate the selected companies before reading the protected user
        # configuration. sudo is only used to read that user's assignments.
        domain = [("active", "=", True), ("company_id", "in", self.env.companies.ids)]
        if company_id:
            domain.append(("company_id", "=", company_id))
        if not self._domex_can_configure_all_warehouses():
            domain.append(("id", "in", self.env.user.sudo().domex_warehouse_ids.ids))
        return self.env["stock.warehouse"].search(domain)

    @api.depends("company_id")
    @api.depends_context("uid", "allowed_company_ids")
    def _compute_domex_available_warehouse_ids(self):
        for product in self:
            product.domex_available_warehouse_ids = self._domex_available_warehouses(product.company_id.id)

    @api.depends("domex_accounting_product")
    def _compute_domex_warehouse_assignment_required(self):
        for product in self:
            product.domex_warehouse_assignment_required = not product.domex_accounting_product

    @api.model
    def _domex_validate_warehouse_commands(self, commands, current_ids, company_id, accounting=False):
        """Validate relation changes before ORM commands can affect warehouses.

        Product managers may change only their active, selected warehouses.
        Existing assignments outside that set must be preserved, including
        assignments hidden by the warehouse's own company rules.
        """
        available = self._domex_available_warehouses()
        removable_ids = set(available.ids)
        allowed_ids = set(available.filtered(
            lambda warehouse: not company_id or warehouse.company_id.id == company_id,
        ).ids)
        result_ids = set(current_ids)
        for command in commands or []:
            operation = command[0]
            if operation in (fields.Command.LINK, fields.Command.UNLINK):
                permitted_ids = allowed_ids if operation == fields.Command.LINK else removable_ids
                if command[1] not in permitted_ids:
                    raise AccessError(self.env._(
                        "Solo puede asignar o retirar sus almacenes permitidos, activos "
                        "y compatibles con la compañía del producto. Seleccione también "
                        "esa compañía en el selector de Odoo."
                    ))
                if operation == fields.Command.LINK:
                    result_ids.add(command[1])
                else:
                    result_ids.discard(command[1])
            elif operation == fields.Command.SET:
                replacement = set(command[2])
                if ((replacement - result_ids) - allowed_ids
                        or (result_ids - replacement) - removable_ids):
                    raise AccessError(self.env._(
                        "No puede modificar asignaciones de almacenes que no tenga "
                        "permitidos en esta compañía. Conserve esas asignaciones "
                        "o solicite el cambio a un administrador de Ajustes."
                    ))
                result_ids = replacement
            elif operation == fields.Command.CLEAR:
                if result_ids - removable_ids:
                    raise AccessError(self.env._(
                        "No puede retirar los almacenes de otros usuarios o compañías. "
                        "Solicite ese cambio a un administrador de Ajustes."
                    ))
                result_ids.clear()
            else:
                # CREATE, UPDATE and DELETE act on stock.warehouse itself.
                # Never allow them through product assignment, even if the user
                # happens to be an Inventory administrator as well.
                raise AccessError(self.env._(
                    "Desde el producto solo puede vincular o desvincular almacenes "
                    "permitidos existentes; no crear, modificar ni eliminar almacenes."
                ))
        if not accounting and not result_ids & allowed_ids:
            raise ValidationError(self.env._(
                "Seleccione al menos un almacén permitido en la pestaña Acceso Domex. "
                "Si no aparece ninguno, solicite que le asignen un almacén de la "
                "compañía del producto y seleccione esa compañía en Odoo. "
                "Un producto normal sin almacenes no será accesible para usted."
            ))

    def _prepare_create_values(self, vals_list):
        values_list = super()._prepare_create_values(vals_list)
        if not self._domex_can_configure_all_warehouses():
            # Defaults from the UI, context and imports must pass the same
            # checks as explicit values, before the product is inserted.
            for values in values_list:
                self._domex_validate_warehouse_commands(
                    values.get("domex_warehouse_ids", []), set(),
                    values.get("company_id", False), values.get("domex_accounting_product", False),
                )
        return values_list

    def _domex_check_warehouse_write(self, vals):
        if not self._domex_can_configure_all_warehouses() and {"domex_warehouse_ids", "company_id"} & vals.keys():
            # Check the OLD record first: a user cannot grant themselves access
            # by adding a permitted warehouse to an otherwise hidden product.
            self.check_access("write")
            for product in self.sudo():
                self._domex_validate_warehouse_commands(
                    vals.get("domex_warehouse_ids", []), set(product.domex_warehouse_ids.ids),
                    vals.get("company_id", product.company_id.id), product.domex_accounting_product,
                )

    def write(self, vals):
        self._domex_check_warehouse_write(vals)
        if "categ_id" in vals and not self.env.su and not self.env.user.has_group("base.group_system"):
            self.check_access("write")
            category = self.env["product.category"].sudo().browse(vals["categ_id"] or [])
            restricted = bool(category.domex_vinyasa)
            if any(bool(product.categ_id.domex_vinyasa) != restricted for product in self.sudo()):
                raise AccessError(self.env._(
                    "Solo un administrador de Ajustes puede cambiar un producto "
                    "entre una categoría compartida y una categoría Vinyasa."
                ))
        return super().write(vals)

    domex_accounting_product = fields.Boolean(
        string="Producto contable",
        groups="base.group_system",
        help="Los miembros del grupo Producto contable y la cuenta principal "
             "de administrador pueden acceder a este producto, dentro de sus "
             "compañías seleccionadas. "
             "Los productos contables no tienen almacenes asignados.",
    )

    domex_warehouse_ids = fields.Many2many(
        "stock.warehouse",
        "domex_product_template_warehouse_rel",
        "product_tmpl_id",
        "warehouse_id",
        string="Almacenes del producto",
        groups="base.group_system,product.group_product_manager",
        domain="[('company_id', '=', company_id)] if company_id else []",
        help="Los usuarios necesitan al menos uno de estos almacenes asignado "
             "en una compañía seleccionada para acceder al producto. "
             "Todas las variantes comparten esta asignación.",
    )

    domex_available_warehouse_ids = fields.Many2many(
        "stock.warehouse", compute="_compute_domex_available_warehouse_ids",
        compute_sudo=False, groups="base.group_system,product.group_product_manager",
        string="Almacenes disponibles para asignar",
    )

    domex_warehouse_assignment_required = fields.Boolean(
        compute="_compute_domex_warehouse_assignment_required", compute_sudo=True,
        groups="base.group_system,product.group_product_manager",
        string="Requiere almacenes",
    )

    @api.onchange("domex_accounting_product")
    def _onchange_domex_accounting_product(self):
        if self.domex_accounting_product:
            self.domex_warehouse_ids = [fields.Command.clear()]

    @api.constrains("company_id", "domex_warehouse_ids", "domex_accounting_product")
    def _check_domex_warehouse_companies(self):
        # Read the protected configuration also when a regular user changes
        # company_id. This does not elevate the write itself.
        for product in self.sudo():
            if product.domex_accounting_product and product.domex_warehouse_ids:
                raise ValidationError(self.env._(
                    "Un producto contable no puede tener almacenes asignados. "
                    "Retire los almacenes antes de marcar Producto contable."
                ))
            if product.company_id and any(
                warehouse.company_id != product.company_id
                for warehouse in product.domex_warehouse_ids
            ):
                raise ValidationError(self.env._(
                    "Los almacenes de un producto con compañía definida deben "
                    "pertenecer a esa compañía. Para utilizar almacenes de varias "
                    "compañías, el producto debe ser compartido (sin compañía)."
                ))
