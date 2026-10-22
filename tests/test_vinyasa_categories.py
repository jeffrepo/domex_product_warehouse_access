from lxml import etree

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


VINYASA_GROUP = "domex_product_warehouse_access.group_vinyasa"
ACCOUNTING_GROUP = "domex_product_warehouse_access.group_accounting_product"
ALL_CATEGORIES_GROUP = "domex_product_warehouse_access.group_all_product_categories"


@tagged("post_install", "-at_install")
class TestVinyasaCategories(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a, cls.company_b = cls.env["res.company"].sudo().create([
            {"name": "Vinyasa access A"}, {"name": "Vinyasa access B"},
        ])
        cls.companies = cls.company_a | cls.company_b
        cls.warehouse_a, cls.warehouse_b = cls.env["stock.warehouse"].sudo().create([
            {"name": "Vinyasa access A", "code": "VGA", "company_id": cls.company_a.id},
            {"name": "Vinyasa access B", "code": "VGB", "company_id": cls.company_b.id},
        ])

        def make_user(login, vinyasa=False, settings=False, companies=None):
            companies = companies or cls.companies
            groups = "base.group_user,base.group_multi_company,product.group_product_manager"
            if vinyasa:
                groups += "," + VINYASA_GROUP
            if settings:
                groups += ",base.group_system"
            warehouses = (cls.warehouse_a | cls.warehouse_b).filtered(
                lambda warehouse: warehouse.company_id in companies,
            )
            return new_test_user(
                cls.env(su=True), login=login, groups=groups,
                company_id=cls.company_a.id, company_ids=[Command.set(companies.ids)],
                domex_warehouse_ids=[Command.set(warehouses.ids)],
            )

        cls.user = make_user("domex_category_shared")
        cls.member = make_user("domex_category_vinyasa", vinyasa=True)
        cls.member_a = make_user("domex_category_vinyasa_a", vinyasa=True, companies=cls.company_a)
        cls.settings = make_user("domex_category_settings", settings=True)
        cls.primary_admin = cls.env.ref("base.user_admin").sudo()
        cls.primary_admin.write({
            "company_ids": [Command.link(company.id) for company in cls.companies],
            "group_ids": [Command.unlink(cls.env.ref(VINYASA_GROUP).id)],
        })
        categories = cls.env["product.category"].sudo()
        cls.common_a, cls.common_b, cls.vinyasa = categories.create([
            {"name": "Domex category shared A"},
            {"name": "Domex category shared B"},
            {"name": "Domex category Vinyasa", "domex_vinyasa": True},
        ])
        cls.child = categories.create({"name": "Domex category shared child", "parent_id": cls.vinyasa.id})
        cls.shared_categories = cls.common_a | cls.common_b | cls.child
        cls.categories = cls.shared_categories | cls.vinyasa

        def make_product(name, category=None, company=None):
            warehouse = cls.warehouse_b if company == cls.company_b else cls.warehouse_a
            return cls.env["product.template"].sudo().with_context(
                allowed_company_ids=cls.companies.ids,
            ).create({
                "name": "Domex Vinyasa test " + name, "type": "service",
                "categ_id": category.id if category else False,
                "company_id": company.id if company else False,
                "domex_warehouse_ids": [Command.set(warehouse.ids)],
            })

        cls.common_product = make_product("common", cls.common_b)
        cls.uncategorized = make_product("uncategorized")
        cls.restricted_product = make_product("restricted", cls.vinyasa)
        cls.child_product = make_product("shared child", cls.child)
        cls.company_b_product = make_product("company B", cls.vinyasa, cls.company_b)
        cls.shared_products = cls.common_product | cls.uncategorized | cls.child_product
        cls.products = cls.shared_products | cls.restricted_product | cls.company_b_product

    def _model(self, name, user=None, companies=None):
        return self.env[name].with_user(user or self.user).with_context(
            allowed_company_ids=(companies or self.company_a).ids,
        )

    def _assert_categories(self, expected, user=None, companies=None):
        model = self._model("product.category", user, companies)
        domain = [("id", "in", self.categories.ids)]
        self.assertEqual(set(model.search(domain).ids), set(expected.ids))
        self.assertEqual({row["id"] for row in model.search_read(domain, ["name"])}, set(expected.ids))
        self.assertEqual({rid for rid, name in model.name_search(domain=domain)}, set(expected.ids))

    def _assert_products(self, expected, user=None, companies=None):
        for name in ("product.template", "product.product"):
            with self.subTest(model=name):
                records = self.products if name == "product.template" else self.products.product_variant_ids
                visible = expected if name == "product.template" else expected.product_variant_ids
                model = self._model(name, user, companies)
                domain = [("id", "in", records.ids)]
                self.assertEqual(set(model.search(domain).ids), set(visible.ids))
                self.assertEqual({rid for rid, title in model.name_search(domain=domain)}, set(visible.ids))
                # Product selectors in customer and vendor invoices.
                for flag in ("sale_ok", "purchase_ok"):
                    self.assertEqual(
                        {rid for rid, title in model.name_search(domain=domain + [(flag, "=", True)])},
                        set(visible.ids),
                    )

    def test_shared_categories_do_not_depend_on_selected_companies(self):
        for companies in (self.company_a, self.company_b, self.companies):
            self._assert_categories(self.shared_categories, companies=companies)
        # Reading a shared category with a Vinyasa parent must still work.
        values = self._model("product.category").browse(self.child.id).web_read({
            "name": {}, "parent_id": {"fields": {"display_name": {}}},
        })
        self.assertEqual(values[0]["name"], self.child.name)

    def test_new_categories_are_shared_by_default(self):
        category = self._model("product.category").create({"name": "New shared category"})
        self.assertFalse(category.sudo().domex_vinyasa)
        self._model("product.category", companies=self.company_b).browse(category.id).read(["name"])

    def test_group_only_sees_flagged_categories_without_granting_companies(self):
        for companies in (self.company_a, self.company_b, self.companies):
            self._assert_categories(self.vinyasa, self.member, companies)
        self._assert_categories(self.vinyasa, self.member_a)
        self.assertEqual(self.member_a.company_ids, self.company_a)

    def test_only_principal_admin_is_exempt_without_group(self):
        self.assertFalse(self.primary_admin.has_group(VINYASA_GROUP))
        self._assert_categories(self.categories, self.primary_admin)
        self._assert_categories(self.shared_categories, self.settings)
        self.settings.sudo().write({"name": self.primary_admin.name})
        self._assert_categories(self.shared_categories, self.settings)
        group = self.env.ref(VINYASA_GROUP)
        self.settings.sudo().write({"group_ids": [Command.link(group.id)]})
        self._assert_categories(self.vinyasa, self.settings)
        self.primary_admin.write({"group_ids": [Command.link(group.id)]})
        self._assert_categories(self.categories, self.primary_admin)
        self._assert_products(self.products - self.company_b_product, self.primary_admin)

    def test_group_changes_invalidate_categories_and_products(self):
        group = self.env.ref(VINYASA_GROUP)
        self._assert_categories(self.shared_categories)
        self._assert_products(self.shared_products)
        self.user.sudo().write({"group_ids": [Command.link(group.id)]})
        self._assert_categories(self.vinyasa)
        self._assert_products(self.restricted_product)
        self.user.sudo().write({"group_ids": [Command.unlink(group.id)]})
        self._assert_categories(self.shared_categories)
        self._assert_products(self.shared_products)

    def test_direct_access_to_flagged_categories_is_denied(self):
        category = self._model("product.category").browse(self.vinyasa.id)
        with self.assertRaises(AccessError):
            category.read(["name"])
        with self.assertRaises(AccessError), self.cr.savepoint():
            category.write({"name": "Forbidden"})
        with self.assertRaises(AccessError), self.cr.savepoint():
            category.unlink()

    def test_vinyasa_member_cannot_access_unmarked_categories_directly(self):
        for record in self.shared_categories:
            category = self._model("product.category", self.member).browse(record.id)
            with self.subTest(category=record.id), self.assertRaises(AccessError):
                category.read(["name"])
            with self.assertRaises(AccessError), self.cr.savepoint():
                category.write({"name": "Forbidden"})
            with self.assertRaises(AccessError), self.cr.savepoint():
                category.unlink()
        with self.assertRaises(AccessError), self.cr.savepoint():
            self._model("product.category", self.member).create({"name": "Forbidden shared category"})

    def test_products_and_variants_follow_their_own_category_flag(self):
        self._assert_products(self.shared_products)
        self._assert_products(self.restricted_product, self.member)
        self._assert_products(self.products - self.company_b_product, self.primary_admin)
        for name in ("product.template", "product.product"):
            record = self.restricted_product if name == "product.template" else self.restricted_product.product_variant_id
            with self.assertRaises(AccessError):
                self._model(name).browse(record.id).read(["name"])
            self._model(name).browse(
                self.child_product.id if name == "product.template" else self.child_product.product_variant_id.id,
            ).read(["name", "categ_id"])
            for shared in self.shared_products:
                shared_record = shared if name == "product.template" else shared.product_variant_id
                with self.subTest(model=name, product=shared_record.id), self.assertRaises(AccessError):
                    self._model(name, self.member).browse(shared_record.id).read(["name", "categ_id"])

    def test_vinyasa_group_does_not_bypass_product_companies(self):
        self._assert_products(self.restricted_product, self.member_a)
        self._assert_products(self.restricted_product | self.company_b_product, self.member, self.companies)
        with self.assertRaises(AccessError):
            self._model("product.template", self.member_a).browse(self.company_b_product.id).read(["name"])

    def test_flag_changes_apply_without_inheritance_or_cached_ids(self):
        self.assertFalse(self.child.domex_vinyasa)
        self._assert_products(self.shared_products)
        self.vinyasa.sudo().write({"domex_vinyasa": False})
        self._assert_categories(self.categories)
        self._assert_products(self.products - self.company_b_product)
        self._assert_categories(self.categories.browse(), self.member)
        self._assert_products(self.products.browse(), self.member)
        self.child.sudo().write({"domex_vinyasa": True})
        self._assert_categories(self.categories - self.child)
        self._assert_products(self.common_product | self.uncategorized | self.restricted_product)
        self._assert_categories(self.child, self.member)
        self._assert_products(self.child_product, self.member)
        self.child.sudo().write({"domex_vinyasa": False})
        self.vinyasa.sudo().write({"domex_vinyasa": True})
        self.child.sudo().write({"parent_id": self.common_a.id})
        self._assert_categories(self.shared_categories)
        self._assert_products(self.shared_products)

    def test_parent_changes_do_not_reclassify_categories(self):
        child = self._model("product.category", self.primary_admin).browse(self.child.id)
        child.write({"parent_id": self.common_a.id})
        child.write({"parent_id": self.vinyasa.id})
        self.assertFalse(child.sudo().domex_vinyasa)
        self._assert_categories(self.shared_categories)
        self._assert_products(self.shared_products)
        self._assert_categories(self.vinyasa, self.member)
        self._assert_products(self.restricted_product, self.member)

    def test_flags_are_protected_in_api_and_import(self):
        for user, category in ((self.user, self.common_a), (self.member, self.vinyasa)):
            with self.assertRaises(AccessError), self.cr.savepoint():
                self._model("product.category", user).browse(category.id).write({
                    "domex_vinyasa": not category.domex_vinyasa,
                })
            with self.assertRaises(AccessError), self.cr.savepoint():
                self._model("product.category", user).create({"name": "Forbidden", "domex_vinyasa": True})
        result = self._model("product.category").load(
            [".id", "domex_vinyasa"], [[str(self.common_a.id), "True"]],
        )
        self.assertTrue(any(message["type"] == "error" for message in result["messages"]))
        self.assertFalse(self.common_a.sudo().domex_vinyasa)

    def test_delete_cannot_remove_protection_through_cascade(self):
        self.vinyasa.sudo().write({"parent_id": self.common_a.id})
        for user, category in ((self.user, self.common_a), (self.member, self.vinyasa)):
            with self.assertRaises(AccessError), self.cr.savepoint():
                self._model("product.category", user).browse(category.id).unlink()
        self.assertTrue(self.vinyasa.exists())
        self.assertEqual(self.restricted_product.categ_id, self.vinyasa)

    def test_copy_preserves_classification_for_administrators(self):
        common_copy = self._model("product.category").browse(self.common_a.id).copy()
        self.assertFalse(common_copy.sudo().domex_vinyasa)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self._model("product.category", self.member).browse(self.vinyasa.id).copy()
        copied = self._model("product.category", self.primary_admin).browse(self.vinyasa.id).copy()
        self.assertTrue(copied.domex_vinyasa)

    def test_recategorizing_products_cannot_remove_protection(self):
        another_vinyasa = self.env["product.category"].sudo().create({
            "name": "Another Vinyasa category", "domex_vinyasa": True,
        })
        for name in ("product.template", "product.product"):
            record = self.restricted_product if name == "product.template" else self.restricted_product.product_variant_id
            for category_id in (False, self.common_a.id, self.child.id):
                with self.subTest(model=name, category=category_id), self.assertRaises(AccessError), self.cr.savepoint():
                    self._model(name, self.member).browse(record.id).write({"categ_id": category_id})
            self._model(name, self.member).browse(record.id).write({"categ_id": another_vinyasa.id})
        self._model("product.template", self.primary_admin).browse(self.restricted_product.id).write({
            "categ_id": self.common_a.id,
        })
        self._assert_products(self.shared_products | self.restricted_product)

    def test_defaults_and_group_expansion_follow_category_access(self):
        for name in ("product.template", "product.product"):
            model = self._model(name, companies=self.company_b)
            for category in self.shared_categories:
                defaults = model.with_context(default_categ_id=category.id).default_get(["categ_id"])
                self.assertEqual(defaults["categ_id"], category.id)
            defaults = model.with_context(default_categ_id=self.vinyasa.id).default_get(["categ_id"])
            self.assertFalse(defaults.get("categ_id"))
        products = self._model("product.template").with_context(group_expand=True)
        expanded = products._read_group_categ_id(self._model("product.category").browse(), [])
        self.assertTrue(set(self.shared_categories.ids) <= set(expanded.ids))
        self.assertNotIn(self.vinyasa.id, expanded.ids)
        expanded = products.with_context(default_categ_id=self.vinyasa.id)._read_group_categ_id(
            self._model("product.category").browse(), [],
        )
        self.assertFalse(expanded)

    def test_vinyasa_defaults_and_group_expansion_exclude_shared_categories(self):
        for name in ("product.template", "product.product"):
            model = self._model(name, self.member, self.company_b)
            defaults = model.with_context(default_categ_id=self.vinyasa.id).default_get(["categ_id"])
            self.assertEqual(defaults["categ_id"], self.vinyasa.id)
            for category in self.shared_categories:
                defaults = model.with_context(default_categ_id=category.id).default_get(["categ_id"])
                self.assertFalse(defaults.get("categ_id"))
        products = self._model("product.template", self.member).with_context(group_expand=True)
        expanded = products._read_group_categ_id(
            self._model("product.category", self.member).browse(), [],
        )
        self.assertIn(self.vinyasa.id, expanded.ids)
        self.assertFalse(set(self.shared_categories.ids) & set(expanded.ids))
        expanded = products.with_context(default_categ_id=self.common_a.id)._read_group_categ_id(
            self._model("product.category", self.member).browse(), [],
        )
        self.assertFalse(expanded)

    def test_global_rule_cannot_be_bypassed_by_permissive_groups(self):
        for name in ("product.category", "product.template", "product.product"):
            self.env["ir.rule"].sudo().create({
                "name": "Vinyasa permissive test rule", "model_id": self.env["ir.model"]._get_id(name),
                "groups": [Command.link(self.env.ref("product.group_product_manager").id)],
                "domain_force": "[(1, '=', 1)]",
            })
        self._assert_categories(self.shared_categories)
        self._assert_products(self.shared_products)
        self._assert_categories(self.vinyasa, self.member)
        self._assert_products(self.restricted_product, self.member)

    def test_views_expose_classification_only_to_settings(self):
        for xmlid, view_type in (
            ("product.product_category_form_view", "form"), ("product.product_category_list_view", "list"),
        ):
            for user, expected in ((self.user, False), (self.primary_admin, True)):
                arch = etree.fromstring(self._model("product.category", user).get_view(
                    view_id=self.env.ref(xmlid).id, view_type=view_type,
                )["arch"])
                self.assertEqual(bool(arch.xpath("//field[@name='domex_vinyasa']")), expected)

    def test_vinyasa_group_still_requires_warehouses_for_products(self):
        self.member.sudo().write({"domex_warehouse_ids": [Command.clear()]})
        self._assert_categories(self.vinyasa, self.member)
        self._assert_products(self.products.browse(), self.member)
        self.member.sudo().write({"domex_warehouse_ids": [Command.set(self.warehouse_a.ids)]})
        self._assert_products(self.restricted_product, self.member)

    def test_accounting_products_require_both_groups_when_category_is_vinyasa(self):
        accounting_products = self.restricted_product | self.common_product | self.uncategorized
        accounting_products.sudo().write({
            "domex_accounting_product": True, "domex_warehouse_ids": [Command.clear()],
        })
        self.member.sudo().write({"domex_warehouse_ids": [Command.clear()]})
        self._assert_products(self.products.browse(), self.member)
        self.member.sudo().write({"group_ids": [Command.link(self.env.ref(ACCOUNTING_GROUP).id)]})
        self._assert_products(self.restricted_product, self.member)
        self.member.sudo().write({"group_ids": [Command.unlink(self.env.ref(VINYASA_GROUP).id)]})
        self._assert_products(self.common_product | self.uncategorized, self.member)

    def test_all_categories_grant_and_revoke_preserve_previous_catalog(self):
        group = self.env.ref(ALL_CATEGORIES_GROUP)
        for user, original_categories, original_products in (
            (self.user, self.shared_categories, self.shared_products),
            (self.member, self.vinyasa, self.restricted_product),
            (self.settings, self.shared_categories, self.shared_products),
        ):
            with self.subTest(user=user.login):
                had_vinyasa = user.has_group(VINYASA_GROUP)
                # Warm both rule caches before changing membership.
                self._assert_categories(original_categories, user)
                self._assert_products(original_products, user)
                user.sudo().write({"group_ids": [Command.link(group.id)]})
                self._assert_categories(self.categories, user)
                self._assert_products(self.products - self.company_b_product, user)
                self.assertEqual(user.has_group(VINYASA_GROUP), had_vinyasa)
                user.sudo().write({"group_ids": [Command.unlink(group.id)]})
                self._assert_categories(original_categories, user)
                self._assert_products(original_products, user)
                self.assertEqual(user.has_group(VINYASA_GROUP), had_vinyasa)

    def test_all_categories_reads_common_accounting_service_with_vinyasa_group(self):
        # Regression: a Vinyasa member with accounting access cannot read a
        # supplier-bill service whose category is shared. No warehouse is needed.
        accounting = self.common_product | self.restricted_product | self.uncategorized
        accounting.sudo().write({
            "company_id": self.company_a.id,
            "domex_accounting_product": True,
            "domex_warehouse_ids": [Command.clear()],
        })
        self.member.sudo().write({
            "group_ids": [Command.link(self.env.ref(ACCOUNTING_GROUP).id)],
            "domex_warehouse_ids": [Command.clear()],
        })
        self._assert_products(self.restricted_product, self.member)
        self.env.invalidate_all()
        for name, rid in (
            ("product.template", self.common_product.id),
            ("product.product", self.common_product.product_variant_id.id),
            ("product.category", self.common_product.categ_id.id),
        ):
            with self.subTest(model=name), self.assertRaises(AccessError):
                self._model(name, self.member).browse(rid).read(["name"])

        self.member.sudo().write({
            "group_ids": [Command.link(self.env.ref(ALL_CATEGORIES_GROUP).id)],
        })
        self.env.invalidate_all()
        self._assert_categories(self.categories, self.member)
        self._assert_products(accounting, self.member)
        for name in ("product.template", "product.product"):
            records = accounting if name == "product.template" else accounting.product_variant_ids
            values = self._model(name, self.member).browse(records.ids).web_read({
                "display_name": {}, "categ_id": {"fields": {"display_name": {}}},
            })
            self.assertEqual({row["id"] for row in values}, set(records.ids))
        self.assertTrue(self.member.has_group(VINYASA_GROUP))
        self.assertFalse(self.member.domex_warehouse_ids)

        # Revoking accounting access must still hide these services, even while
        # both category groups remain assigned and their domains are cached.
        self.member.sudo().write({"group_ids": [Command.unlink(self.env.ref(ACCOUNTING_GROUP).id)]})
        self._assert_products(self.products.browse(), self.member)
        with self.assertRaises(AccessError):
            self._model("product.product", self.member).browse(
                self.common_product.product_variant_id.id,
            ).read(["name"])

    def test_all_categories_keeps_selected_and_allowed_company_limits(self):
        for user in (self.member, self.member_a):
            user.sudo().write({"group_ids": [Command.link(self.env.ref(ALL_CATEGORIES_GROUP).id)]})
            self._assert_categories(self.categories, user)
            self._assert_products(self.products - self.company_b_product, user)
            with self.assertRaises(AccessError):
                self._model("product.template", user).browse(self.company_b_product.id).read(["name"])
        self._assert_products(self.products, self.member, self.companies)
        self.assertEqual(self.member_a.company_ids, self.company_a)
        for name in ("product.template", "product.product"):
            with self.subTest(model=name), self.assertRaises(AccessError):
                self._model(name, self.member_a, self.company_b).search([])

    def test_all_categories_still_requires_an_applicable_warehouse(self):
        self.member.sudo().write({
            "group_ids": [Command.link(self.env.ref(ALL_CATEGORIES_GROUP).id)],
            "domex_warehouse_ids": [Command.clear()],
        })
        self._assert_categories(self.categories, self.member)
        self._assert_products(self.products.browse(), self.member)
        self.member.sudo().write({"domex_warehouse_ids": [Command.set(self.warehouse_b.ids)]})
        self._assert_products(self.products.browse(), self.member)
        self._assert_products(self.company_b_product, self.member, self.companies)
        self.member.sudo().write({"domex_warehouse_ids": [Command.set(self.warehouse_a.ids)]})
        self._assert_products(self.products - self.company_b_product, self.member, self.companies)

    def test_all_categories_does_not_grant_configuration_permissions(self):
        self.member.sudo().write({"group_ids": [Command.link(self.env.ref(ALL_CATEGORIES_GROUP).id)]})
        self.assertFalse(self.member.has_group("base.group_system"))
        self.assertFalse(self.member.has_group(ACCOUNTING_GROUP))
        self._assert_categories(self.categories, self.member)
        with self.assertRaises(AccessError), self.cr.savepoint():
            self._model("product.category", self.member).browse(self.vinyasa.id).write({"domex_vinyasa": False})
        with self.assertRaises(AccessError), self.cr.savepoint():
            self._model("product.template", self.member).browse(self.restricted_product.id).write({
                "categ_id": self.common_a.id,
            })
        with self.assertRaises(AccessError), self.cr.savepoint():
            self._model("product.category", self.member).browse(self.vinyasa.id).unlink()
        with self.assertRaises(AccessError), self.cr.savepoint():
            self._model("res.users", self.member).browse(self.member.id).write({
                "group_ids": [Command.link(self.env.ref("base.group_system").id)],
            })

    def test_all_categories_preserves_other_global_rules(self):
        self.member.sudo().write({"group_ids": [Command.link(self.env.ref(ALL_CATEGORIES_GROUP).id)]})
        self.env["ir.rule"].sudo().create({
            "name": "Additional category restriction",
            "model_id": self.env["ir.model"]._get_id("product.category"),
            "domain_force": "[('id', '!=', %s)]" % self.common_a.id,
        })
        self._assert_categories(self.categories - self.common_a, self.member)
        with self.assertRaises(AccessError):
            self._model("product.category", self.member).browse(self.common_a.id).read(["name"])
