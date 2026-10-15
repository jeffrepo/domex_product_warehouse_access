from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def default_get(self, fields_list):
        # Explicit defaults on delegated fields can skip template.default_get.
        return self.env["product.template"]._domex_filter_category_default(
            super().default_get(fields_list),
        )
