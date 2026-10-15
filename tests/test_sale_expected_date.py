from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import Command, fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tests.common import new_test_user


@tagged("post_install", "-at_install")
class TestSaleExpectedDate(TransactionCase):
    NOW = datetime(2026, 10, 15, 12)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a, cls.company_b = cls.env["res.company"].sudo().create([
            {"name": "Domex sale date A"}, {"name": "Domex sale date B"},
        ])
        cls.companies = cls.company_a | cls.company_b
        cls.warehouse_a, cls.warehouse_b = cls.env["stock.warehouse"].sudo().create([
            {"name": "Domex sale date A", "code": "DSDA", "company_id": cls.company_a.id},
            {"name": "Domex sale date B", "code": "DSDB", "company_id": cls.company_b.id},
        ])
        cls.seller = new_test_user(
            cls.env(su=True), login="domex_sale_date_seller",
            groups="base.group_user,base.group_multi_company,sales_team.group_sale_salesman",
            company_id=cls.company_a.id, company_ids=[Command.set(cls.companies.ids)],
            domex_warehouse_ids=[Command.set(cls.warehouse_a.ids)],
        )
        cls.partner = cls.env["res.partner"].sudo().create({"name": "Domex sale date customer"})
        cls.common_category, cls.vinyasa_category = cls.env["product.category"].sudo().create([
            {"name": "Domex sale date common"},
            {"name": "Domex sale date Vinyasa", "domex_vinyasa": True},
        ])
        Template = cls.env["product.template"].sudo().with_context(allowed_company_ids=cls.companies.ids)

        def product(name, company=None, warehouses=None, category=None, accounting=False):
            return Template.create({
                "name": name, "type": "service" if accounting else "consu",
                "company_id": (company or cls.company_a).id,
                "categ_id": (category or cls.common_category).id,
                "taxes_id": [Command.clear()],
                "domex_accounting_product": accounting,
                "domex_warehouse_ids": [Command.set(warehouses.ids if warehouses else [])],
            }).product_variant_id

        cls.visible = product("Domex sale visible", warehouses=cls.warehouse_a)
        cls.unassigned = product("Domex sale unassigned")
        cls.accounting = product("Domex sale accounting", accounting=True)
        cls.vinyasa = product("Domex sale Vinyasa", warehouses=cls.warehouse_a, category=cls.vinyasa_category)
        cls.other_company = product("Domex sale company B", company=cls.company_b)

    def _order(self, products, company=None, **extra):
        company = company or self.company_a
        values = {
            "name": "Domex expected date regression",
            "partner_id": self.partner.id,
            "company_id": company.id,
            "user_id": self.seller.id,
            "date_order": self.NOW,
            "order_line": [Command.create({
                "product_id": product.id, "name": "Historical line",
                "product_uom_id": product.uom_id.id, "product_uom_qty": 1,
                "price_unit": 10, "tax_ids": [Command.clear()],
                "customer_lead": lead,
            }) for product, lead in products],
        }
        model = self.env["sale.order"].sudo().with_company(company)
        if "warehouse_id" in model._fields:
            values["warehouse_id"] = (self.warehouse_b if company == self.company_b else self.warehouse_a).id
        values.update(extra)
        return model.create(values)

    def _read_list(self, orders, companies=None):
        # Discard fixture/sudo caches so the regression exercises real reads.
        self.env.invalidate_all()
        with freeze_time(self.NOW):
            rows = self.env["sale.order"].with_user(self.seller).with_context(
                allowed_company_ids=(companies or self.company_a).ids,
            ).web_search_read(
                domain=[("id", "in", orders.ids)],
                specification={"name": {}, "expected_date": {}},
                order="id", limit=80,
            )["records"]
        for row in rows:
            if row["expected_date"]:
                row["expected_date"] = fields.Datetime.to_datetime(row["expected_date"])
        return rows

    def _assert_product_hidden(self, product, companies=None):
        self.env.invalidate_all()
        for model, record_id in (("product.product", product.id), ("product.template", product.product_tmpl_id.id)):
            records = self.env[model].with_user(self.seller).with_context(
                allowed_company_ids=(companies or self.company_a).ids,
            )
            self.assertFalse(records.search([("id", "=", record_id)]))
            with self.assertRaises(AccessError):
                records.browse(record_id).read(["name"])

    def test_list_date_includes_hidden_goods_without_granting_product_access(self):
        order = self._order([(self.visible, 7), (self.unassigned, 2)])
        self._assert_product_hidden(self.unassigned)
        # Reproduce the failure before the integration, using the real native
        # computation and record rules rather than a mocked product read.
        with patch.object(self.env["sale.order"]._fields["expected_date"], "compute_sudo", False):
            with self.assertRaises(AccessError):
                self._read_list(order)
        rows = self._read_list(order)
        self.assertEqual(rows[0]["expected_date"], self.NOW + timedelta(days=2))
        self._assert_product_hidden(self.unassigned)
        visible = self.visible.with_user(self.seller).with_context(allowed_company_ids=self.company_a.ids)
        self.assertTrue(visible.search([("id", "=", self.visible.id)]))

    def test_accounting_and_vinyasa_products_do_not_block_list_date(self):
        for product, expected in (
            (self.accounting, False),  # The native calculation excludes services.
            (self.vinyasa, self.NOW + timedelta(days=3)),
        ):
            with self.subTest(product=product.id):
                order = self._order([(product, 3)])
                self._assert_product_hidden(product)
                self.assertEqual(self._read_list(order)[0]["expected_date"], expected)
                self._assert_product_hidden(product)

    def test_sales_company_rules_remain_in_force(self):
        order = self._order([(self.other_company, 4)], company=self.company_b)
        self.assertFalse(self._read_list(order))
        user_order = order.with_user(self.seller).with_context(allowed_company_ids=self.company_a.ids)
        with self.assertRaises(AccessError):
            user_order.read(["expected_date"])
        rows = self._read_list(order, companies=self.companies)
        self.assertEqual(rows[0]["expected_date"], self.NOW + timedelta(days=4))
        self._assert_product_hidden(self.other_company, companies=self.companies)

    def test_salesperson_record_rules_remain_in_force(self):
        order = self._order([(self.unassigned, 2)], user_id=self.env.ref("base.user_admin").id)
        self.assertFalse(self._read_list(order))
        with self.assertRaises(AccessError):
            order.with_user(self.seller).with_context(allowed_company_ids=self.company_a.ids).read(["expected_date"])

    def test_cancelled_and_empty_orders_keep_native_false_date(self):
        cancelled = self._order([(self.unassigned, 2)], state="cancel")
        empty = self._order([])
        rows = self._read_list(cancelled | empty)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(row["expected_date"] is False for row in rows))

    def test_shipping_policy_keeps_native_minimum_and_maximum_dates(self):
        if "picking_policy" not in self.env["sale.order"]._fields:
            self.skipTest("sale_stock is not installed")
        for policy, days in (("direct", 2), ("one", 7)):
            with self.subTest(policy=policy):
                order = self._order([(self.visible, 2), (self.unassigned, 7)], picking_policy=policy)
                self.assertEqual(
                    self._read_list(order)[0]["expected_date"],
                    self.NOW + timedelta(days=days),
                )
