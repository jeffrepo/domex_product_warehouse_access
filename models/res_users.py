from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.fields import Domain


class ResUsers(models.Model):
    _inherit = "res.users"

    domex_warehouse_ids = fields.Many2many(
        "stock.warehouse",
        "domex_res_users_warehouse_rel",
        "user_id",
        "warehouse_id",
        string="Almacenes permitidos para productos",
        groups="base.group_system",
        domain="[('company_id', 'in', company_ids)]",
        copy=False,
        help="Puede asignar varios almacenes de las compañías permitidas del "
             "usuario. Sin almacenes solo podrá ver productos contables si "
             "pertenece al grupo Producto contable. Solo la cuenta principal "
             "de administrador ve todos los productos de las compañías seleccionadas.",
    )

    @api.constrains("domex_warehouse_ids", "company_ids")
    def _check_domex_warehouse_companies(self):
        for user in self.sudo():
            if user.domex_warehouse_ids.company_id - user.company_ids:
                raise ValidationError(self.env._(
                    "Los almacenes asignados deben pertenecer a las compañías "
                    "permitidas del usuario. Retire los almacenes de una compañía "
                    "antes de quitar esa compañía al usuario."
                ))

    @api.model
    def _get_invalidation_fields(self):
        # ir.rule caches domains by user and selected companies. Revoke or grant
        # access immediately after changing the user's warehouse assignments.
        return super()._get_invalidation_fields() | {"domex_warehouse_ids"}

    def _domex_product_warehouse_domain(self, company_ids):
        """Build the global rule using the trusted company_ids from ir.rule."""
        self.ensure_one()
        company_domain = (
            Domain("company_id", "=", False)
            | Domain("company_id", "in", company_ids)
        )
        # Exempt the principal administrator account, not every user assigned
        # the Settings administrator role. XML identity survives login/name edits.
        administrator = self.env.ref("base.user_admin", raise_if_not_found=False)
        if administrator and self.id == administrator.id:
            return company_domain

        warehouse_domain = (
            Domain("id", "in", self.domex_warehouse_ids.ids)
            & Domain("company_id", "in", company_ids)
            & Domain("active", "=", True)
        )
        # Match the SAME warehouse for assignment, company and active status.
        # any! avoids requiring warehouse read permissions just to read products.
        # The trusted user assignments and company_ids still bound the subquery.
        # Keep active/company checks in SQL so warehouse changes are not cached.
        regular_domain = Domain("domex_accounting_product", "=", False)
        warehouse_access = Domain(
            "domex_warehouse_ids", "any!", warehouse_domain,
        )
        regular_domain &= warehouse_access

        accounting_domain = Domain.FALSE
        if self.has_group("domex_product_warehouse_access.group_accounting_product"):
            accounting_domain = Domain("domex_accounting_product", "=", True)

        return (
            company_domain & (regular_domain | accounting_domain)
            & self._domex_product_category_domain()
        )

    def _domex_category_access_domain(self):
        self.ensure_one()
        administrator = self.env.ref("base.user_admin", raise_if_not_found=False)
        if (administrator and self.id == administrator.id) or self.has_group(
            "domex_product_warehouse_access.group_all_product_categories"
        ):
            return Domain.TRUE
        # Membership selects one category set, not an additional permission.
        # Company and ancestor flags do not change the category's own flag.
        return Domain("domex_vinyasa", "=", self.has_group(
            "domex_product_warehouse_access.group_vinyasa"
        ))

    def _domex_product_category_domain(self):
        # The principal administrator already bypasses this filter above.
        if self.has_group("domex_product_warehouse_access.group_all_product_categories"):
            # Bypass only category classification, including uncategorized
            # products. Company, warehouse and accounting checks remain outside.
            return Domain.TRUE
        # any! checks the flag without requiring category configuration rights.
        domain = Domain(
            "categ_id", "any!", self._domex_category_access_domain(),
        )
        if not self.has_group("domex_product_warehouse_access.group_vinyasa"):
            # Uncategorised products belong to the non-Vinyasa catalogue.
            domain |= Domain("categ_id", "=", False)
        return domain
