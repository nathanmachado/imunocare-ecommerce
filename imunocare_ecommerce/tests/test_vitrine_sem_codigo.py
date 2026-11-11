"""Change vitrine-sem-marca, task 1.1 — a página do produto e o carrinho não
mostram o código interno nem o item_name (que pode trazer a marca); o nome
exibido é o da vitrine (web_item_name)."""

from __future__ import annotations

import re

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.jinja import get_jenv

_CODIGO = "ZZ-COD-INTERNO-9731"
_ITEM_NAME = "Marca Fabricante XPTO 9731 Interno"
_VITRINE = "Vacina da Vitrine 9731"


def _texto_visivel(html: str) -> str:
	return re.sub(r"<[^>]+>", " ", html)


class TestVitrineSemCodigoInterno(FrappeTestCase):
	def test_pagina_do_produto(self):
		doc = frappe._dict(
			item_code=_CODIGO,
			item_name=_ITEM_NAME,
			web_item_name=_VITRINE,
			item_group="Services",
			description="",
			web_long_description="<p>Descrição</p>",
		)
		tmpl = get_jenv().get_template("templates/generators/item/item_details.html")
		html = tmpl.render(doc=doc, shopping_cart=frappe._dict(cart_settings=frappe._dict(), product_info={}), slides=None)
		visivel = _texto_visivel(html)
		self.assertNotIn(_CODIGO, visivel)
		self.assertNotIn(_ITEM_NAME, html)
		self.assertIn(f'itemprop="name">\n\t\t\t{_VITRINE}', html)
		self.assertEqual(html.count('itemprop="name"'), 1)

	def test_carrinho(self):
		item = frappe._dict(
			name="x1",
			item_code=_CODIGO,
			item_name=_ITEM_NAME,
			web_item_name=_VITRINE,
			thumbnail=None,
			qty=1,
			amount=1,
			rate=1,
			additional_notes="",
			is_free_item=0,
		)
		item.get_formatted = lambda campo: "1"
		doc = frappe.new_doc('Quotation')
		# Quotation e não _dict: "items" em dict colide com dict.items()
		doc.items = [item]
		tmpl = get_jenv().get_template("templates/includes/cart/cart_items.html")
		html = tmpl.render(doc=doc, cart_settings=frappe._dict(enable_checkout=0), shopping_cart=frappe._dict())
		visivel = _texto_visivel(re.sub(r"data-item-code=\"[^\"]*\"", "", html))
		self.assertNotIn(_CODIGO, visivel)
		self.assertNotIn(_ITEM_NAME, html)
		self.assertIn(_VITRINE, html)
