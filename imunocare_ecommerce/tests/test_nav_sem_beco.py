"""vitrine-sem-marca 4.2 — categoria sem Website Item publicado não aparece na navegação."""

from __future__ import annotations

from unittest.mock import patch

import frappe

from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.catalogo import setup


class TestNavSemBeco(FrappeTestCase):
	def test_so_categoria_com_publicado_entra_na_nav(self):
		contagens = {"Vacinas": 1, "Consultas": 0}
		with patch(
			"imunocare_ecommerce.catalogo.jinja_utils.contagem_produtos_publicados",
			side_effect=lambda g: contagens.get(g, 0),
		):
			nomes = [c["nome"] for c in setup.nav_categorias_loja()]
		self.assertNotIn("Consultas", nomes)
		self.assertTrue(set(nomes) <= {"Vacinas"})

	def test_com_website_item_real(self):
		cheio, vazio = "ZZ Nav Cheio", "ZZ Nav Vazio"
		for g in (cheio, vazio):
			frappe.get_doc(
				{"doctype": "Item Group", "item_group_name": g, "parent_item_group": "All Item Groups",
				 "show_in_website": 1}
			).insert(ignore_permissions=True)
		item = frappe.get_doc(
			{"doctype": "Item", "item_code": "ZZ-NAV-ITEM", "item_name": "ZZ Nav Item",
			 "item_group": cheio, "stock_uom": "Nos", "is_stock_item": 0}
		).insert(ignore_permissions=True)
		frappe.get_doc(
			{"doctype": "Website Item", "item_code": item.name, "web_item_name": "ZZ Nav Item",
			 "item_group": cheio, "published": 1}
		).insert(ignore_permissions=True)
		with patch.object(setup, "_NAV_ORDEM_IMUNO", [cheio, vazio]):
			nomes = [c["nome"] for c in setup.nav_categorias_loja()]
		self.assertEqual(nomes, [cheio])

	def tearDown(self):
		frappe.db.rollback()
		for wi in frappe.get_all("Website Item", filters={"item_code": "ZZ-NAV-ITEM"}, pluck="name"):
			frappe.delete_doc("Website Item", wi, force=True)
		frappe.delete_doc("Item", "ZZ-NAV-ITEM", force=True, ignore_missing=True)
		for g in ("ZZ Nav Cheio", "ZZ Nav Vazio"):
			frappe.delete_doc("Item Group", g, force=True, ignore_missing=True)
		frappe.db.commit()
