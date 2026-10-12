from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ProductTemplate(models.Model):
    _inherit = "product.template"

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
