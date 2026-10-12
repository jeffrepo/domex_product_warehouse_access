from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import Form, TransactionCase, tagged
from odoo.tests.common import new_test_user


ACCOUNTING_GROUP = "domex_product_warehouse_access.group_accounting_product"


@tagged("post_install", "-at_install")
class TestProductWarehouseAccess(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a, cls.company_b, cls.company_c = cls.env["res.company"].sudo().create([
            {"name": "Domex access A"}, {"name": "Domex access B"}, {"name": "Domex access C"},
        ])
        cls.warehouse_a, cls.warehouse_a2, cls.warehouse_b = cls.env["stock.warehouse"].sudo().create([
            {"name": "Access A1", "code": "DWA1", "company_id": cls.company_a.id},
            {"name": "Access A2", "code": "DWA2", "company_id": cls.company_a.id},
            {"name": "Access B1", "code": "DWB1", "company_id": cls.company_b.id},
        ])
        companies = cls.company_a | cls.company_b
        assigned = cls.warehouse_a | cls.warehouse_b

        def make_user(login, warehouses=None, accounting=False, administrator=False):
            groups = "base.group_user,base.group_multi_company,product.group_product_manager"
            if accounting:
                groups += "," + ACCOUNTING_GROUP
            if administrator:
                groups += ",base.group_system"
            return new_test_user(
                cls.env(su=True), login=login, groups=groups,
                company_id=cls.company_a.id,
                company_ids=[Command.set(companies.ids)],
                domex_warehouse_ids=[Command.set(warehouses.ids if warehouses else [])],
            )

        cls.operator = make_user("domex_warehouse_operator", assigned)
        cls.empty_user = make_user("domex_warehouse_empty")
        cls.accountant = make_user("domex_warehouse_accountant", accounting=True)
        cls.dual_user = make_user("domex_warehouse_dual", assigned, accounting=True)
        cls.administrator = make_user("domex_warehouse_admin", administrator=True)
        cls.accounting_admin = make_user("domex_warehouse_accounting_admin", accounting=True, administrator=True)
        Template = cls.env["product.template"].sudo().with_context(
            allowed_company_ids=(companies | cls.company_c).ids,
        )

        def make_product(name, company=None, warehouses=None, accounting=False):
            return Template.create({
                "name": "Domex access " + name,
                "type": "service" if accounting else "consu",
                "company_id": company.id if company else False,
                "domex_warehouse_ids": [Command.set(warehouses.ids if warehouses else [])],
                "domex_accounting_product": accounting,
            })

        cls.regular_a = make_product("regular A", cls.company_a, cls.warehouse_a)
        cls.regular_a2 = make_product("regular A2", cls.company_a, cls.warehouse_a2)
        cls.regular_b = make_product("regular B", cls.company_b, cls.warehouse_b)
        cls.shared = make_product("shared", warehouses=assigned)
        cls.cross_match = make_product("cross match", warehouses=cls.warehouse_a2 | cls.warehouse_b)
        cls.unassigned = make_product("unassigned")
        cls.accounting_a = make_product("accounting A", cls.company_a, accounting=True)
        cls.accounting_b = make_product("accounting B", cls.company_b, accounting=True)
        cls.accounting_shared = make_product("accounting shared", accounting=True)
        cls.accounting_c = make_product("accounting C", cls.company_c, accounting=True)
        cls.products = (
            cls.regular_a | cls.regular_a2 | cls.regular_b | cls.shared
            | cls.cross_match | cls.unassigned | cls.accounting_a
            | cls.accounting_b | cls.accounting_shared | cls.accounting_c
        )

    def _model(self, model_name, user=None, companies=None):
        return self.env[model_name].with_user(user or self.operator).with_context(
            allowed_company_ids=(companies or self.company_a).ids,
        )

    def _records(self, templates, model_name):
        return templates if model_name == "product.template" else templates.product_variant_ids

    def _assert_visible(self, expected, user=None, companies=None):
        for model_name in ("product.template", "product.product"):
            with self.subTest(model=model_name):
                model = self._model(model_name, user, companies)
                domain = [("id", "in", self._records(self.products, model_name).ids)]
                expected_ids = set(self._records(expected, model_name).ids)
                self.assertEqual(set(model.search(domain).ids), expected_ids)
                self.assertEqual(model.search_count(domain), len(expected_ids))
                self.assertEqual({row["id"] for row in model.search_read(domain, ["name"])}, expected_ids)
                self.assertEqual({record_id for record_id, _name in model.name_search(domain=domain)}, expected_ids)

    def test_warehouse_access_without_inventory_permissions(self):
        self.assertFalse(self.operator.has_group("stock.group_stock_user"))
        self._assert_visible(self.regular_a | self.shared)

    def test_multiple_warehouses_in_same_company(self):
        self.operator.sudo().write({"domex_warehouse_ids": [Command.link(self.warehouse_a2.id)]})
        self._assert_visible(self.regular_a | self.regular_a2 | self.shared | self.cross_match)

    def test_no_warehouses_and_no_accounting_group_means_no_products(self):
        self._assert_visible(self.products.browse(), self.empty_user)

    def test_company_switch_and_same_warehouse_match(self):
        # A-only must not combine the user's B1 assignment with the product's A2.
        self._assert_visible(self.regular_a | self.shared, companies=self.company_a)
        self._assert_visible(self.regular_b | self.shared | self.cross_match, companies=self.company_b)
        self._assert_visible(
            self.regular_a | self.regular_b | self.shared | self.cross_match,
            companies=self.company_a | self.company_b,
        )

    def test_accounting_group_without_warehouses(self):
        self._assert_visible(self.accounting_a | self.accounting_shared, self.accountant)
        self._assert_visible(self.accounting_b | self.accounting_shared, self.accountant, self.company_b)
        self._assert_visible(
            self.accounting_a | self.accounting_b | self.accounting_shared,
            self.accountant, self.company_a | self.company_b,
        )

    def test_both_access_types_are_combined(self):
        self._assert_visible(
            self.regular_a | self.shared | self.accounting_a | self.accounting_shared, self.dual_user,
        )

    def test_administrator_needs_accounting_group_too(self):
        regular = self.regular_a | self.regular_a2 | self.shared | self.cross_match | self.unassigned
        self._assert_visible(regular, self.administrator)
        self._assert_visible(regular | self.accounting_a | self.accounting_shared, self.accounting_admin)

    def test_direct_access_to_hidden_records_is_denied(self):
        for template in (self.regular_a2, self.regular_b, self.accounting_a, self.unassigned):
            for model_name in ("product.template", "product.product"):
                record = self._model(model_name).browse(self._records(template, model_name).ids)
                with self.subTest(product=template.name, model=model_name):
                    with self.assertRaises(AccessError):
                        record.read(["name"])
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        record.write({"name": "Forbidden change"})
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        record.unlink()

    def test_regular_users_cannot_change_security_fields(self):
        for user, template in ((self.operator, self.regular_a), (self.accountant, self.accounting_a)):
            for model_name in ("product.template", "product.product"):
                record = self._model(model_name, user).browse(self._records(template, model_name).ids)
                for values in (
                    {"domex_warehouse_ids": [Command.link(self.warehouse_a2.id)]},
                    {"domex_accounting_product": not template.domex_accounting_product},
                ):
                    with self.subTest(user=user.login, model=model_name, values=values):
                        with self.assertRaises(AccessError), self.cr.savepoint():
                            record.write(values)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self.operator.with_user(self.operator).write({
                "domex_warehouse_ids": [Command.link(self.warehouse_a2.id)],
            })

    def test_create_and_context_defaults_cannot_bypass_assignments(self):
        for model_name in ("product.template", "product.product"):
            model = self._model(model_name)
            for values in (
                {"name": "Hidden unassigned product"},
                {"name": "Forbidden accounting", "domex_accounting_product": True},
                {"name": "Forbidden warehouse", "domex_warehouse_ids": [Command.link(self.warehouse_a.id)]},
            ):
                with self.subTest(model=model_name, values=values):
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        model.create(values)
            with self.assertRaises(AccessError), self.cr.savepoint():
                model.with_context(default_domex_accounting_product=True).create({"name": "Context bypass"})
            with self.assertRaises(AccessError), self.cr.savepoint():
                model.with_context(default_domex_warehouse_ids=[Command.link(self.warehouse_a.id)]).create({
                    "name": "Warehouse context bypass",
                })

    def test_user_assignment_change_invalidates_cached_rule(self):
        self._assert_visible(self.regular_a | self.shared)
        self.operator.sudo().write({"domex_warehouse_ids": [Command.set(self.warehouse_a2.ids)]})
        self._assert_visible(self.regular_a2 | self.cross_match)
        self.operator.sudo().write({"domex_warehouse_ids": [Command.clear()]})
        self._assert_visible(self.products.browse())

    def test_accounting_group_grant_and_revocation_invalidate_cached_rule(self):
        self._assert_visible(self.products.browse(), self.empty_user)
        group = self.env.ref(ACCOUNTING_GROUP)
        self.empty_user.sudo().write({"group_ids": [Command.link(group.id)]})
        self._assert_visible(self.accounting_a | self.accounting_shared, self.empty_user)
        self.empty_user.sudo().write({"group_ids": [Command.unlink(group.id)]})
        self._assert_visible(self.products.browse(), self.empty_user)

    def test_product_reassignment_and_classification_take_effect_immediately(self):
        self._assert_visible(self.regular_a | self.shared)
        self.regular_a.sudo().write({"domex_warehouse_ids": [Command.set(self.warehouse_a2.ids)]})
        self._assert_visible(self.shared)
        self.shared.sudo().write({"domex_warehouse_ids": [Command.clear()], "domex_accounting_product": True})
        self._assert_visible(self.products.browse())
        self._assert_visible(self.accounting_a | self.accounting_shared | self.shared, self.accountant)
        self.shared.sudo().write({"domex_accounting_product": False})
        self._assert_visible(self.accounting_a | self.accounting_shared, self.accountant)

    def test_archived_warehouse_stops_granting_access(self):
        self._assert_visible(self.regular_a | self.shared)
        self.warehouse_a.sudo().active = False
        self._assert_visible(self.products.browse())
        self._assert_visible(self.accounting_a | self.accounting_shared, self.accountant)
        self.warehouse_a.sudo().active = True
        self._assert_visible(self.regular_a | self.shared)

    def test_user_warehouse_company_consistency(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.operator.sudo().write({"company_ids": [Command.set(self.company_a.ids)]})
        self.operator.sudo().write({
            "company_ids": [Command.set(self.company_a.ids)],
            "domex_warehouse_ids": [Command.set(self.warehouse_a.ids)],
        })
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.operator.sudo().write({"domex_warehouse_ids": [Command.link(self.warehouse_b.id)]})

    def test_product_warehouse_company_consistency(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.regular_a.sudo().write({"domex_warehouse_ids": [Command.link(self.warehouse_b.id)]})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.shared.sudo().write({"company_id": self.company_a.id})
        self.shared.sudo().write({
            "company_id": self.company_a.id,
            "domex_warehouse_ids": [Command.set(self.warehouse_a.ids)],
        })

    def test_accounting_products_cannot_have_warehouses_even_in_sudo(self):
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.accounting_a.sudo().write({"domex_warehouse_ids": [Command.link(self.warehouse_a.id)]})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.regular_a.sudo().write({"domex_accounting_product": True})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.env["product.template"].sudo().create({
                "name": "Invalid accounting product", "domex_accounting_product": True,
                "domex_warehouse_ids": [Command.link(self.warehouse_a.id)],
            })

    def test_variants_share_template_assignments(self):
        variant = self.regular_a.product_variant_id.sudo()
        self.assertEqual(variant.domex_warehouse_ids, self.warehouse_a)
        variant.write({"domex_warehouse_ids": [Command.set(self.warehouse_a2.ids)]})
        self.assertEqual(self.regular_a.domex_warehouse_ids, self.warehouse_a2)
        variant.write({"domex_accounting_product": True, "domex_warehouse_ids": [Command.clear()]})
        self.assertTrue(self.regular_a.domex_accounting_product)
        self.assertFalse(self.regular_a.domex_warehouse_ids)

    def test_form_onchange_clears_warehouses(self):
        template = self._model("product.template", self.accounting_admin).browse(self.regular_a.id)
        with Form(template) as form:
            form.domex_accounting_product = True
        self.assertTrue(template.domex_accounting_product)
        self.assertFalse(template.domex_warehouse_ids)

    def test_fields_are_available_on_template_and_variant_forms(self):
        for model_name, view_ref in (
            ("product.template", "product.product_template_only_form_view"),
            ("product.product", "product.product_normal_form_view"),
        ):
            model = self._model(model_name, self.accounting_admin)
            arch = etree.fromstring(model.get_view(
                view_id=self.env.ref(view_ref).id, view_type="form",
            )["arch"])
            self.assertTrue(arch.xpath("//field[@name='domex_warehouse_ids']"))
            self.assertTrue(arch.xpath("//field[@name='domex_accounting_product']"))

    def test_group_rules_cannot_expand_global_restriction(self):
        for model_name in ("product.template", "product.product"):
            self.env["ir.rule"].sudo().create({
                "name": "Additional permissive group rule",
                "model_id": self.env["ir.model"]._get_id(model_name),
                "groups": [Command.link(self.env.ref("product.group_product_manager").id)],
                "domain_force": "[(1, '=', 1)]",
            })
        self._assert_visible(self.regular_a | self.shared)

    def test_unauthorized_company_context_is_rejected(self):
        for model_name in ("product.template", "product.product"):
            with self.assertRaises(AccessError):
                self._model(model_name, self.accountant, self.company_c).search([])

    def test_sudo_bypasses_record_rules(self):
        for model_name in ("product.template", "product.product"):
            records = self._records(self.products, model_name)
            found = self._model(model_name, self.empty_user).sudo().search([("id", "in", records.ids)])
            self.assertEqual(set(found.ids), set(records.ids))
