from odoo import models


class IrRule(models.Model):
    _inherit = "ir.rule"

    def _make_access_error(self, operation, records):
        error = super()._make_access_error(operation, records)
        if records._name not in {
            "product.template", "product.product", "product.category",
            "res.users", "res.partner",
        }:
            return error

        context = getattr(error, "context", None) or {}
        suggested_company = context.get("suggested_company")
        if suggested_company and suggested_company["id"] in self.env.companies.ids:
            # Odoo 19's form render error handler appends this company and reloads
            # even when already selected. That cannot fix warehouse/group access
            # or category/contact rules limited to the MAIN company, and loops.
            # Keep the denial/message; only suppress the ineffective redirect.
            error.context = {
                key: value for key, value in context.items() if key != "suggested_company"
            }
        return error
