from ast import literal_eval
from unittest.mock import patch

from lxml import etree

from odoo import Command
from odoo.addons.base.models.ir_rule import IrRule as BaseIrRule
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
        cls.primary_admin = cls.env.ref("base.user_admin").sudo()
        cls.primary_admin.write({
            "company_ids": [Command.link(company.id) for company in companies],
            "domex_warehouse_ids": [Command.clear()],
            "group_ids": [Command.unlink(cls.env.ref(ACCOUNTING_GROUP).id)],
        })
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
                self.assertEqual(
                    {record_id for record_id, _name in model.name_search("Domex access", domain=domain)},
                    expected_ids,
                )

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

    def test_principal_administrator_sees_all_products_without_assignments(self):
        regular = self.regular_a | self.regular_a2 | self.shared | self.cross_match | self.unassigned
        self.assertFalse(self.primary_admin.has_group(ACCOUNTING_GROUP))
        self.assertFalse(self.primary_admin.domex_warehouse_ids)
        self._assert_visible(regular | self.accounting_a | self.accounting_shared, self.primary_admin)
        self._assert_visible(
            self.regular_b | self.shared | self.cross_match | self.unassigned
            | self.accounting_b | self.accounting_shared,
            self.primary_admin, self.company_b,
        )
        self._assert_visible(
            self.products - self.accounting_c, self.primary_admin, self.company_a | self.company_b,
        )

    def test_settings_administrator_role_does_not_bypass_restrictions(self):
        self.assertTrue(self.administrator.has_group("base.group_system"))
        self._assert_visible(self.products.browse(), self.administrator)
        self._assert_visible(self.accounting_a | self.accounting_shared, self.accounting_admin)
        self.accounting_admin.sudo().write({"domex_warehouse_ids": [Command.link(self.warehouse_a.id)]})
        self._assert_visible(
            self.regular_a | self.shared | self.accounting_a | self.accounting_shared,
            self.accounting_admin,
        )

    def test_account_name_does_not_grant_administrator_exception(self):
        self.administrator.sudo().write({"name": self.primary_admin.name})
        self._assert_visible(self.products.browse(), self.administrator)

    def test_invoice_selector_domains_respect_warehouse_and_accounting_access(self):
        # Same sale/purchase domains used by account.view_move_form in Odoo 19.
        # Exercising the product selector does not require installing account.
        for user, expected in (
            (self.administrator, self.products.browse()),
            (self.accounting_admin, self.accounting_a | self.accounting_shared),
            (self.operator, self.regular_a | self.shared),
            (self.empty_user, self.products.browse()),
        ):
            for move_type, flag in (("out_invoice", "sale_ok"), ("in_invoice", "purchase_ok")):
                with self.subTest(user=user.login, move_type=move_type):
                    model = self._model("product.product", user).with_context(default_move_type=move_type)
                    found = model.name_search("Domex access", domain=[
                        ("id", "in", self.products.product_variant_ids.ids), (flag, "=", True),
                    ])
                    allowed = expected.filtered(lambda product: product[flag]).product_variant_ids
                    self.assertEqual({record_id for record_id, _name in found}, set(allowed.ids))

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
                {"name": "Forbidden accounting", "domex_accounting_product": True},
                {"name": "Forbidden warehouse", "domex_warehouse_ids": [Command.link(self.warehouse_a2.id)]},
            ):
                with self.subTest(model=model_name, values=values):
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        model.create(values)
            with self.assertRaises(AccessError), self.cr.savepoint():
                model.with_context(default_domex_accounting_product=True).create({"name": "Context bypass"})
            with self.assertRaises(AccessError), self.cr.savepoint():
                model.with_context(default_domex_warehouse_ids=[Command.link(self.warehouse_a2.id)]).create({
                    "name": "Warehouse context bypass",
                })

    def test_creators_can_choose_warehouses_on_both_forms(self):
        # Reproduce Rudy: native creation rights, accounting and all categories,
        # but no Settings or Inventory permissions. A category is optional.
        self.dual_user.sudo().write({"group_ids": [Command.link(self.env.ref(
            "domex_product_warehouse_access.group_all_product_categories",
        ).id)]})
        category = self.env["product.category"].sudo().create({"name": "Creation category"})
        for model_name in ("product.template", "product.product"):
            model = self._model(model_name, self.dual_user)
            fields = model.fields_get()
            self.assertIn("domex_warehouse_ids", fields)
            self.assertNotIn("domex_accounting_product", fields)
            for category_record in (category, category.browse()):
                with self.subTest(model=model_name, category=category_record.ids):
                    with Form(model) as form:
                        form.name = "Product created by a warehouse user"
                        form.company_id = self.company_a
                        form.categ_id = category_record
                        form.domex_warehouse_ids.add(self.warehouse_a)
                    product = form.record
                    self.assertEqual(product.sudo().domex_warehouse_ids, self.warehouse_a)
                    self.assertFalse(product.sudo().domex_accounting_product)
                    self.assertEqual(product.create_uid, self.dual_user)
                    product.read(["name"])
                    template = product if model_name == "product.template" else product.product_tmpl_id
                    template.product_variant_ids.read(["name"])

    def test_creator_warehouse_choices_follow_company_and_assignments(self):
        for model_name in ("product.template", "product.product"):
            model = self._model(model_name)
            self.assertEqual(model.new({"company_id": False}).domex_available_warehouse_ids, self.warehouse_a)
            self.assertFalse(model.new({"company_id": self.company_b.id}).domex_available_warehouse_ids)
            both = model.with_context(allowed_company_ids=(self.company_a | self.company_b).ids)
            self.assertEqual(
                set(both.new({"company_id": False}).domex_available_warehouse_ids.ids),
                set((self.warehouse_a | self.warehouse_b).ids),
            )
            self.assertEqual(both.new({"company_id": self.company_b.id}).domex_available_warehouse_ids, self.warehouse_b)
        self.warehouse_a.sudo().active = False
        self.assertFalse(self._model("product.template").new({"company_id": self.company_a.id}).domex_available_warehouse_ids)

    def test_missing_warehouses_explain_creation_requirement(self):
        for user in (self.operator, self.dual_user, self.empty_user):
            for model_name in ("product.template", "product.product"):
                with self.subTest(user=user.login, model=model_name):
                    with self.assertRaisesRegex(ValidationError, "Acceso Domex"), self.cr.savepoint():
                        self._model(model_name, user).create({"name": "Unassigned new product", "categ_id": False})
        # The principal administrator can still prepare unassigned products.
        self._model("product.template", self.primary_admin).create({"name": "Admin preparation"})

    def test_creators_can_update_only_their_warehouse_assignments(self):
        self.operator.sudo().write({"domex_warehouse_ids": [Command.link(self.warehouse_a2.id)]})
        for model_name in ("product.template", "product.product"):
            # A shared product also has a B warehouse, hidden with only A selected.
            self.shared.sudo().write({"domex_warehouse_ids": [Command.set(
                (self.warehouse_a | self.warehouse_b).ids,
            )]})
            product = self._model(model_name).browse(self._records(self.shared, model_name).id)
            product.web_read({"domex_warehouse_ids": {"fields": {"display_name": {}}}})
            product.write({"domex_warehouse_ids": [
                Command.link(self.warehouse_a2.id), Command.unlink(self.warehouse_a.id),
            ]})
            self.assertEqual(
                set(self.shared.sudo().domex_warehouse_ids.ids),
                set((self.warehouse_a2 | self.warehouse_b).ids),
            )
            product.read(["name"])
            product.write({"name": "Warehouse change preserves normal editing"})
            with self.assertRaises(ValidationError), self.cr.savepoint():
                product.write({"domex_warehouse_ids": [Command.unlink(self.warehouse_a2.id)]})

    def test_creators_cannot_remove_protected_assignments(self):
        self.shared.sudo().write({"domex_warehouse_ids": [Command.link(self.warehouse_a2.id)]})
        for model_name in ("product.template", "product.product"):
            product = self._model(model_name).browse(self._records(self.shared, model_name).id)
            for commands in (
                [Command.unlink(self.warehouse_a2.id)],
                [Command.unlink(self.warehouse_b.id)],
                [Command.clear()],
                [Command.set(self.warehouse_a.ids)],
            ):
                with self.subTest(model=model_name, commands=commands):
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        product.write({"domex_warehouse_ids": commands})
        self.assertEqual(
            set(self.shared.sudo().domex_warehouse_ids.ids),
            set((self.warehouse_a | self.warehouse_a2 | self.warehouse_b).ids),
        )

    def test_warehouse_commands_cannot_modify_warehouse_records(self):
        # Even a native Inventory manager may not use a relation command to
        # create, rename or delete a warehouse through this product field.
        self.operator.sudo().write({"group_ids": [Command.link(self.env.ref("stock.group_stock_manager").id)]})
        for model_name in ("product.template", "product.product"):
            model = self._model(model_name)
            product = model.browse(self._records(self.regular_a, model_name).id)
            for command in (
                Command.create({"name": "Forbidden nested warehouse", "code": "FNW", "company_id": self.company_a.id}),
                Command.update(self.warehouse_a.id, {"name": "Forbidden warehouse rename"}),
                Command.delete(self.warehouse_a.id),
            ):
                with self.subTest(model=model_name, command=command):
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        product.write({"domex_warehouse_ids": [command]})
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        model.create({"name": "Nested command", "domex_warehouse_ids": [command]})
        self.assertEqual(self.warehouse_a.sudo().name, "Access A1")

    def test_create_company_defaults_and_revocations_are_validated(self):
        for model_name in ("product.template", "product.product"):
            model = self._model(model_name)
            for company_id, warehouse in (
                (self.company_a.id, self.warehouse_b),
                (self.company_b.id, self.warehouse_b),
                (self.company_c.id, self.warehouse_a),
            ):
                with self.subTest(model=model_name, company=company_id, warehouse=warehouse.id):
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        model.with_context(default_company_id=company_id).create({
                            "name": "Wrong company", "domex_warehouse_ids": [Command.set(warehouse.ids)],
                        })
            valid = model.with_context(
                default_company_id=self.company_a.id,
                default_domex_warehouse_ids=self.warehouse_a.ids,
            ).create({"name": "Permitted defaults"})
            self.assertEqual(valid.sudo().domex_warehouse_ids, self.warehouse_a)
        # An open form does not retain a revoked or archived permission.
        for change in ("archived", "revoked"):
            if change == "archived":
                self.warehouse_a.sudo().active = False
            else:
                self.warehouse_a.sudo().active = True
                self.operator.sudo().write({"domex_warehouse_ids": [Command.clear()]})
            with self.assertRaises(AccessError), self.cr.savepoint():
                self._model("product.template").create({
                    "name": "Stale form", "domex_warehouse_ids": [Command.link(self.warehouse_a.id)],
                })

    def test_hidden_products_cannot_be_made_accessible_by_assignment(self):
        for model_name in ("product.template", "product.product"):
            for template in (self.regular_a2, self.unassigned):
                record = self._model(model_name).browse(self._records(template, model_name).id)
                with self.assertRaises(AccessError), self.cr.savepoint():
                    record.write({"domex_warehouse_ids": [Command.link(self.warehouse_a.id)]})

    def test_warehouse_assignment_import_respects_permissions(self):
        model = self._model("product.template")
        result = model.load(
            ["name", "company_id/.id", "domex_warehouse_ids/.id"],
            [["Imported permitted product", str(self.company_a.id), str(self.warehouse_a.id)]],
        )
        self.assertFalse([message for message in result["messages"] if message["type"] == "error"])
        product = model.browse(result["ids"])
        self.assertEqual(product.sudo().domex_warehouse_ids, self.warehouse_a)
        result = model.load(
            [".id", "domex_warehouse_ids/.id"], [[str(product.id), str(self.warehouse_a2.id)]],
        )
        self.assertTrue(any(message["type"] == "error" for message in result["messages"]))
        self.assertEqual(product.sudo().domex_warehouse_ids, self.warehouse_a)

    def test_creation_keeps_company_and_category_rules(self):
        vinyasa = self.env["product.category"].sudo().create({"name": "Creation Vinyasa", "domex_vinyasa": True})
        for model_name in ("product.template", "product.product"):
            model = self._model(model_name, companies=self.company_a | self.company_b)
            values = {
                "name": "Creation with category rules", "company_id": self.company_a.id,
                "categ_id": vinyasa.id, "domex_warehouse_ids": [Command.set(self.warehouse_a.ids)],
            }
            with self.assertRaises(AccessError), self.cr.savepoint():
                model.create(values)
            self.operator.sudo().write({"group_ids": [Command.link(self.env.ref(
                "domex_product_warehouse_access.group_all_product_categories",
            ).id)]})
            product = model.create(values)
            product.read(["name"])
            self.operator.sudo().write({"group_ids": [Command.unlink(self.env.ref(
                "domex_product_warehouse_access.group_all_product_categories",
            ).id)]})
            shared = model.create({
                "name": "Shared creation", "company_id": False,
                "domex_warehouse_ids": [Command.set((self.warehouse_a | self.warehouse_b).ids)],
            })
            for company in (self.company_a, self.company_b):
                shared.with_context(allowed_company_ids=company.ids).read(["name"])
            with self.assertRaises(AccessError), self.cr.savepoint():
                model.with_context(allowed_company_ids=self.company_c.ids).create({
                    "name": "Unauthorized context", "domex_warehouse_ids": [Command.link(self.warehouse_a.id)],
                })

    def test_template_company_and_warehouses_can_change_together(self):
        product = self._model("product.template", companies=self.company_a | self.company_b).browse(self.regular_a.id)
        product.write({"company_id": self.company_b.id, "domex_warehouse_ids": [Command.set(self.warehouse_b.ids)]})
        self.assertEqual(product.sudo().company_id, self.company_b)
        self.assertEqual(product.sudo().domex_warehouse_ids, self.warehouse_b)
        product.read(["name"])

    def test_assignment_does_not_grant_product_creation_permissions(self):
        reader = new_test_user(
            self.env(su=True), login="domex_warehouse_reader", groups="base.group_user,stock.group_stock_user",
            company_id=self.company_a.id, company_ids=[Command.set(self.company_a.ids)],
            domex_warehouse_ids=[Command.set(self.warehouse_a.ids)],
        )
        self.assertFalse(reader.has_group("product.group_product_manager"))
        for model_name in ("product.template", "product.product"):
            model = self._model(model_name, reader)
            self.assertNotIn("domex_warehouse_ids", model.fields_get())
            with self.assertRaises(AccessError), self.cr.savepoint():
                model.create({"name": "No native creation permission", "domex_warehouse_ids": [Command.set(self.warehouse_a.ids)]})

    def test_batch_create_validates_every_warehouse_assignment(self):
        for model_name in ("product.template", "product.product"):
            model = self._model(model_name, companies=self.company_a | self.company_b)
            products = model.create([
                {"name": "Batch A", "company_id": self.company_a.id, "domex_warehouse_ids": [Command.set(self.warehouse_a.ids)]},
                {"name": "Batch B", "company_id": self.company_b.id, "domex_warehouse_ids": [Command.set(self.warehouse_b.ids)]},
            ])
            self.assertEqual(len(products), 2)
            products.read(["name"])
            with self.assertRaises(AccessError), self.cr.savepoint():
                model.create([
                    {"name": "Batch allowed", "domex_warehouse_ids": [Command.set(self.warehouse_a.ids)]},
                    {"name": "Batch forbidden", "domex_warehouse_ids": [Command.set(self.warehouse_a2.ids)]},
                ])

    def test_regular_creators_can_duplicate_templates_and_variants(self):
        # Reproduce the RPC product.template.copy as Rudy, with and without
        # accounting access. Neither user may read the protected boolean.
        self.dual_user.sudo().write({"group_ids": [Command.link(self.env.ref(
            "domex_product_warehouse_access.group_all_product_categories",
        ).id)]})
        category = self.env["product.category"].sudo().create({"name": "Copy category"})
        self.regular_a.sudo().write({"categ_id": category.id, "list_price": 123.45})
        for user in (self.operator, self.dual_user):
            for model_name in ("product.template", "product.product"):
                with self.subTest(user=user.login, model=model_name):
                    source = self._model(model_name, user).browse(self._records(self.regular_a, model_name).id)
                    with self.assertRaises(AccessError):
                        source.read(["domex_accounting_product"])
                    duplicate = source.copy()
                    self.assertNotEqual(duplicate.id, source.id)
                    self.assertEqual(duplicate.create_uid, user)
                    self.assertEqual(duplicate.company_id, self.company_a)
                    self.assertEqual(duplicate.categ_id, category)
                    self.assertEqual(duplicate.list_price, 123.45)
                    self.assertEqual(duplicate.domex_warehouse_ids, self.warehouse_a)
                    self.assertFalse(duplicate.sudo().domex_accounting_product)
                    duplicate.read(["name"])
                    with self.assertRaises(AccessError):
                        duplicate.read(["domex_accounting_product"])

    def test_duplicate_uses_only_source_warehouses_the_creator_can_assign(self):
        archived = self.env["stock.warehouse"].sudo().create({
            "name": "Archived copy warehouse", "code": "DCAR", "company_id": self.company_a.id,
        })
        self.operator.sudo().write({"domex_warehouse_ids": [Command.link(archived.id)]})
        source_warehouses = self.warehouse_a | self.warehouse_a2 | self.warehouse_b | archived
        self.shared.sudo().write({"domex_warehouse_ids": [Command.set(source_warehouses.ids)]})
        archived.active = False
        for model_name in ("product.template", "product.product"):
            for companies, expected in (
                (self.company_a, self.warehouse_a),
                (self.company_a | self.company_b, self.warehouse_a | self.warehouse_b),
            ):
                with self.subTest(model=model_name, companies=companies.ids):
                    source = self._model(model_name, companies=companies).browse(self._records(self.shared, model_name).id)
                    duplicate = source.copy()
                    self.assertFalse(duplicate.company_id)
                    self.assertEqual(set(duplicate.sudo().domex_warehouse_ids.ids), set(expected.ids))
                    self.assertEqual(set(self.shared.sudo().domex_warehouse_ids.ids), set(source_warehouses.ids))

    def test_accounting_copies_keep_classification_or_require_settings(self):
        for model_name in ("product.template", "product.product"):
            source_id = self._records(self.accounting_a, model_name).id
            source = self._model(model_name, self.dual_user).browse(source_id)
            for default in (None, {
                "domex_accounting_product": False,
                "domex_warehouse_ids": [Command.set(self.warehouse_a.ids)],
            }):
                with self.assertRaisesRegex(AccessError, "duplicar productos contables"), self.cr.savepoint():
                    source.copy(default)
            for user in (self.accounting_admin, self.primary_admin):
                duplicate = self._model(model_name, user).browse(source_id).copy()
                self.assertTrue(duplicate.domex_accounting_product)
                self.assertFalse(duplicate.domex_warehouse_ids)
                self.assertEqual(duplicate.company_id, self.company_a)
                duplicate.read(["name"])

    def test_copy_defaults_do_not_bypass_protected_fields_or_warehouses(self):
        for model_name in ("product.template", "product.product"):
            source = self._model(model_name).browse(self._records(self.regular_a, model_name).id)
            for default in (
                {"domex_accounting_product": True},
                {"domex_accounting_product": False},
                {"domex_warehouse_ids": [Command.set(self.warehouse_a2.ids)]},
                {"domex_warehouse_ids": [Command.link(self.warehouse_b.id)]},
            ):
                with self.subTest(model=model_name, default=default):
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        source.copy(default)
            with self.assertRaises(AccessError), self.cr.savepoint():
                source.with_context(default_domex_accounting_product=True).copy()
            with self.assertRaises(ValidationError), self.cr.savepoint():
                source.copy({"domex_warehouse_ids": [Command.clear()]})
            duplicate = source.copy({"name": "Explicit permitted copy", "domex_warehouse_ids": [Command.set(self.warehouse_a.ids)]})
            self.assertEqual(duplicate.name, "Explicit permitted copy")
            self.assertEqual(duplicate.domex_warehouse_ids, self.warehouse_a)

    def test_copy_cannot_read_an_inaccessible_source(self):
        for model_name in ("product.template", "product.product"):
            for template in (self.regular_a2, self.regular_b, self.unassigned, self.accounting_a):
                source = self._model(model_name).browse(self._records(template, model_name).id)
                with self.subTest(model=model_name, template=template.id):
                    with self.assertRaises(AccessError), self.cr.savepoint():
                        source.copy({
                            "company_id": self.company_a.id,
                            "domex_warehouse_ids": [Command.set(self.warehouse_a.ids)],
                        })

    def test_copy_to_other_company_requires_compatible_warehouse_override(self):
        source = self._model("product.template", companies=self.company_a | self.company_b).browse(self.regular_a.id)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            source.copy({"company_id": self.company_b.id})
        duplicate = source.copy({
            "company_id": self.company_b.id,
            "domex_warehouse_ids": [Command.set(self.warehouse_b.ids)],
        })
        self.assertEqual(duplicate.company_id, self.company_b)
        self.assertEqual(duplicate.domex_warehouse_ids, self.warehouse_b)
        self.assertEqual(source.company_id, self.company_a)
        self.assertEqual(source.domex_warehouse_ids, self.warehouse_a)

    def test_copy_data_does_not_read_protected_flag_and_handles_batches(self):
        source = self._model("product.template").browse((self.regular_a | self.shared).ids)
        values_list = source.copy_data()
        self.assertEqual(len(values_list), 2)
        for values in values_list:
            self.assertNotIn("domex_accounting_product", values)
            self.assertEqual(values["domex_warehouse_ids"], [Command.set(self.warehouse_a.ids)])
        duplicates = source.copy()
        self.assertEqual(len(duplicates), 2)
        duplicates.read(["name"])

    def test_settings_copy_preserves_warehouses_and_explicit_classification(self):
        source = self._model("product.template", self.primary_admin, self.company_a | self.company_b).browse(self.shared.id)
        duplicate = source.copy()
        self.assertEqual(set(duplicate.domex_warehouse_ids.ids), set(source.domex_warehouse_ids.ids))
        self.assertFalse(duplicate.domex_accounting_product)
        accounting = source.copy({"domex_accounting_product": True, "domex_warehouse_ids": [Command.clear()]})
        self.assertTrue(accounting.domex_accounting_product)
        self.assertFalse(accounting.domex_warehouse_ids)

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
        template = self._model("product.template", self.primary_admin).browse(self.regular_a.id)
        with Form(template) as form:
            form.domex_accounting_product = True
        self.assertTrue(template.domex_accounting_product)
        self.assertFalse(template.domex_warehouse_ids)

    def test_fields_are_available_on_template_and_variant_forms(self):
        for model_name, view_ref in (
            ("product.template", "product.product_template_only_form_view"),
            ("product.product", "product.product_normal_form_view"),
        ):
            model = self._model(model_name, self.primary_admin)
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

    def test_user_form_does_not_read_restricted_company_contacts_for_colors(self):
        # Settings administrators can manage another user's allowed companies,
        # even when those companies' contacts are outside their own selection
        # or permissions. The tag color must not prevent opening that user.
        self.operator.sudo().write({"company_ids": [Command.link(self.company_c.id)]})
        for company in (self.company_b, self.company_c):
            company.partner_id.sudo().write({"company_id": company.id})

        user = self._model("res.users", self.administrator).browse(self.operator.id)
        arch = etree.fromstring(user.get_view(
            view_id=self.env.ref("base.view_users_form").id, view_type="form",
        )["arch"])
        company_nodes = arch.xpath("//page[@name='access_rights']//field[@name='company_ids']")
        self.assertEqual(len(company_nodes), 1)
        options = literal_eval(company_nodes[0].get("options", "{}"))
        self.assertTrue(options["no_create"])
        self.assertNotIn("color_field", options)

        specification = {
            "name": {},
            "company_id": {"fields": {"display_name": {}}},
            "company_ids": {"fields": {"display_name": {}}},
        }
        # Reproduce the native tag request: color reads res.partner and fails.
        with self.assertRaises(AccessError):
            user.web_read({
                **specification,
                "company_ids": {"fields": {"display_name": {}, "color": {}}},
            })
        data = user.web_read(specification)[0]
        self.assertEqual(data["id"], self.operator.id)
        self.assertEqual(
            {company["id"] for company in data["company_ids"]},
            set((self.company_a | self.company_b | self.company_c).ids),
        )
        for company in (self.company_b, self.company_c):
            with self.subTest(company=company.name), self.assertRaises(AccessError):
                self._model("res.partner", self.administrator).browse(company.partner_id.id).read(["name"])

    def test_unauthorized_company_context_is_rejected(self):
        for model_name in ("product.template", "product.product"):
            with self.assertRaises(AccessError):
                self._model(model_name, self.accountant, self.company_c).search([])

    def test_denied_product_in_selected_company_does_not_trigger_reload(self):
        for model_name in ("product.template", "product.product"):
            record = self._model(model_name).browse(self._records(self.regular_a2, model_name).ids)
            with self.assertRaises(AccessError) as caught:
                record.read(["name"])
            self.assertNotIn("suggested_company", getattr(caught.exception, "context", {}) or {})

    def test_unselected_company_redirect_is_preserved(self):
        for model_name in ("product.template", "product.product"):
            record = self._model(model_name).browse(self._records(self.regular_b, model_name).ids)
            with self.assertRaises(AccessError) as caught:
                record.read(["name"])
            self.assertEqual(caught.exception.context["suggested_company"]["id"], self.company_b.id)

    def test_category_redirect_loop_is_stopped_without_granting_access(self):
        # Simulate a category addon restricting the main company. B is selected
        # after A, so appending B again cannot satisfy that category rule.
        rules = self._model("ir.rule", companies=self.company_a | self.company_b)
        for model_name in ("product.category", "product.template", "product.product"):
            error = AccessError("Category/product is still restricted")
            error.context = {
                "suggested_company": {"id": self.company_b.id, "display_name": self.company_b.name},
                "other_context": "preserved",
            }
            with patch.object(BaseIrRule, "_make_access_error", return_value=error):
                result = rules._make_access_error("read", rules.env[model_name].browse())
            self.assertIs(result, error)
            self.assertEqual(result.args, ("Category/product is still restricted",))
            self.assertEqual(result.context, {"other_context": "preserved"})

    def test_redirect_handling_of_other_models_is_unchanged(self):
        rules = self._model("ir.rule")
        error = AccessError("Other model error")
        error.context = {"suggested_company": {"id": self.company_a.id}}
        with patch.object(BaseIrRule, "_make_access_error", return_value=error):
            result = rules._make_access_error("read", rules.env["res.company"].browse())
        self.assertIs(result, error)
        self.assertEqual(result.context["suggested_company"]["id"], self.company_a.id)

    def test_user_and_contact_redirects_only_keep_unselected_companies(self):
        for model_name in ("res.users", "res.partner"):
            for companies in (self.company_a, self.company_a | self.company_b):
                with self.subTest(model=model_name, companies=companies.ids):
                    rules = self._model("ir.rule", self.administrator, companies)
                    error = AccessError("Contact/user is still restricted")
                    error.context = {
                        "suggested_company": {"id": self.company_b.id},
                        "other_context": "preserved",
                    }
                    with patch.object(BaseIrRule, "_make_access_error", return_value=error):
                        result = rules._make_access_error("read", rules.env[model_name].browse())
                    self.assertIs(result, error)
                    self.assertEqual(result.args, ("Contact/user is still restricted",))
                    self.assertEqual(result.context["other_context"], "preserved")
                    self.assertEqual("suggested_company" in result.context, self.company_b not in companies)

    def test_contact_denial_without_company_suggestion_is_unchanged(self):
        rules = self._model("ir.rule", self.administrator)
        error = AccessError("Contact company is not allowed")
        with patch.object(BaseIrRule, "_make_access_error", return_value=error):
            result = rules._make_access_error("read", rules.env["res.partner"].browse())
        self.assertIs(result, error)
        self.assertFalse(getattr(result, "context", None))

    def test_sudo_bypasses_record_rules(self):
        for model_name in ("product.template", "product.product"):
            records = self._records(self.products, model_name)
            found = self._model(model_name, self.empty_user).sudo().search([("id", "in", records.ids)])
            self.assertEqual(set(found.ids), set(records.ids))
