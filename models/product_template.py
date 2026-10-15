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

    def write(self, vals):
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
        groups="base.group_system",
        domain="[('company_id', '=', company_id)] if company_id else []",
        help="Los usuarios necesitan al menos uno de estos almacenes asignado "
             "en una compañía seleccionada para acceder al producto. "
             "Todas las variantes comparten esta asignación.",
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
