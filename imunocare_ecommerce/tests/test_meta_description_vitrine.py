"""vitrine-sem-marca 1.3 — meta description da página do produto vem da descrição
curta (+ sufixo) e não muda ao salvar Item/Website Item; nunca é o item_name."""

from __future__ import annotations

import re

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.website.serve import get_response_content
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request

_MARCA = "MarcaFabricanteXPTO"


def _meta(html: str, nome: str = "description") -> str:
	m = re.search(rf'<meta name="{nome}" content="([^"]*)"', html)
	return m.group(1) if m else ""


class TestMetaDescriptionVitrine(FrappeTestCase):
	def setUp(self):
		self.suf = frappe.generate_hash(length=6).lower()
		self.code = f"tst-md-{self.suf}"
		self.item = frappe.get_doc(
			{"doctype": "Item", "item_code": self.code, "item_name": f"{_MARCA} {self.suf}",
			 "item_group": "All Item Groups", "stock_uom": "Nos", "is_stock_item": 0,
			 "is_sales_item": 1, "description": f"Descricao longa do ERP {self.suf} {_MARCA}"}
		).insert(ignore_permissions=True)
		self.sufixo_orig = frappe.db.get_single_value("Imunocare Ecommerce Settings", "meta_description_sufixo")
		self.sufixo = " | Sufixo Teste"
		frappe.db.set_single_value("Imunocare Ecommerce Settings", "meta_description_sufixo", self.sufixo)

	def tearDown(self):
		frappe.db.set_single_value("Imunocare Ecommerce Settings", "meta_description_sufixo", self.sufixo_orig)
		frappe.db.delete("Website Route Meta", {"name": ["like", f"%{self.suf}%"]})
		for wi in frappe.get_all("Website Item", filters={"item_code": self.code}, pluck="name"):
			frappe.delete_doc("Website Item", wi, force=1, ignore_permissions=True)
		frappe.delete_doc("Item", self.code, force=1, ignore_permissions=True)
		frappe.db.commit()

	def _website_item(self, curta):
		wi = frappe.get_doc(
			{"doctype": "Website Item", "item_code": self.code, "web_item_name": f"Vitrine {self.suf}",
			 "published": 1, "route": f"loja-teste/{self.suf}", "short_description": curta,
			 "web_long_description": f"<p>Texto da vitrine {self.suf}</p>"}
		).insert(ignore_permissions=True)
		frappe.db.commit()
		return wi

	def _pagina(self, wi):
		frappe.clear_cache()
		# o webshop lê frappe.request.environ ao montar o breadcrumb
		frappe.local.request = Request(EnvironBuilder(path="/" + wi.route).get_environ())
		return get_response_content(wi.route)

	def test_curta_mais_sufixo_e_estavel_apos_salvar(self):
		wi = self._website_item(f"Curta aprovada {self.suf}")
		esperado = f"Curta aprovada {self.suf}{self.sufixo}"
		self.assertEqual(_meta(self._pagina(wi)), esperado)
		self.assertEqual(_meta(self._pagina(wi), "twitter:description") or esperado, esperado)

		self.item.reload()
		self.item.description = f"Outra descricao longa {self.suf}"
		self.item.save(ignore_permissions=True)
		wi.reload()
		wi.save(ignore_permissions=True)
		self.assertEqual(_meta(self._pagina(wi)), esperado)

	def test_sem_curta_nunca_item_name(self):
		wi = self._website_item("")
		desc = _meta(self._pagina(wi))
		self.assertTrue(desc)
		self.assertNotIn(_MARCA, desc)
		self.assertIn(f"Texto da vitrine {self.suf}", desc)
		self.assertLessEqual(len(desc), 300)
