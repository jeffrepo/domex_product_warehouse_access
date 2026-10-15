from odoo import fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    # The native compute reads product.type on historical order lines. Catalog
    # restrictions must not prevent reading the date of an accessible order.
    # Keep the native calculation (including sale_stock's shipping policy) and
    # elevate only this computed field, not the order read or product access.
    expected_date = fields.Datetime(compute_sudo=True)
