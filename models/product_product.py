from odoo import api, fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    # Related fields normally compute in sudo. These choices depend on the
    # requesting user and must not become all warehouses on the variant form.
    domex_available_warehouse_ids = fields.Many2many(
        related="product_tmpl_id.domex_available_warehouse_ids", compute_sudo=False,
    )

    @api.model
    def default_get(self, fields_list):
        # Explicit defaults on delegated fields can skip template.default_get.
        return self.env["product.template"]._domex_filter_category_default(
            super().default_get(fields_list),
        )

    def write(self, vals):
        if {"domex_warehouse_ids", "company_id"} & vals.keys():
            # A related many2many executes its commands before calling the
            # template inverse. Validate the original commands first, including
            # CREATE/UPDATE/DELETE, before they can touch stock.warehouse.
            self.check_access("write")
            self.product_tmpl_id._domex_check_warehouse_write(vals)
        return super().write(vals)
