"""vitrine-sem-marca 2.2: página do produto e relacionados mostram Pix + parcelado."""

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.catalogo.preco_jinja import moeda_brl, preco_loja_exibicao

_CAMPOS = ("desconto_pix", "juros_vista", "juros_parcelado", "numero_parcelas", "parcela_minima")
_SETTINGS = "Imunocare Ecommerce Settings"
_TESTE = {"desconto_pix": 10, "juros_vista": 0, "juros_parcelado": 20, "numero_parcelas": 4, "parcela_minima": 50}


def _info(rate):
	return frappe._dict(
		formatted_price="R$ NATIVO", formatted_price_sales_uom="R$ NATIVO", price_list_rate=rate,
		formatted_mrp=None,
	)


def _ctx_pagina(rate):
	cart = frappe._dict(
		cart_settings=frappe._dict(enabled=1, show_price=1, enable_wishlist=0, enable_recommendations=1,
			enable_reviews=0, allow_items_not_in_stock=1, show_stock_availability=0,
			show_contact_us_button=0, enable_checkout=1, show_stock_availability_=0),
		product_info=frappe._dict(price=_info(rate), uom="Nos", in_stock=1),
	)
	doc = frappe._dict(item_code="X-1", web_item_name="X", item_name="X", item_group="G",
		offers=[], website_image=None, imun_meta_title=None, website_content="", slideshow=None,
		thumbnail=None, has_variants=0, web_long_description="", description="")
	rel = [frappe._dict(item_code="X-2", route="x2", website_item_name="Rel", website_item_thumbnail=None,
		price_info=_info(rate))]
	return frappe._dict(shopping_cart=cart, doc=doc, item_code="X-1", recommended_items=rel, parents=[],
		show_tabs=0, tabs=None, website_specifications=None, slides=None, has_variants=0, wished=0,
		product_info=cart.product_info, cart_settings=cart.cart_settings)


def _bloco(nome, ctx):
	env = frappe.get_jenv()
	t = env.get_template("templates/generators/item/item.html")
	return "".join(t.blocks[nome](t.new_context(dict(ctx))))


class TestPrecoVitrineRender(FrappeTestCase):
	def setUp(self):
		self._orig = {c: frappe.db.get_singles_dict(_SETTINGS).get(c) for c in _CAMPOS}
		self._set(_TESTE)

	def tearDown(self):
		for c, v in self._orig.items():
			frappe.db.sql(
				"delete from tabSingles where doctype=%s and field=%s", (_SETTINGS, c))
			if v is not None:
				frappe.db.sql(
					"insert into tabSingles (doctype, field, value) values (%s,%s,%s)", (_SETTINGS, c, v))
		frappe.clear_cache(doctype=_SETTINGS)

	def _set(self, valores):
		for c in _CAMPOS:
			frappe.db.sql("delete from tabSingles where doctype=%s and field=%s", (_SETTINGS, c))
			if valores.get(c) is not None:
				frappe.db.sql(
					"insert into tabSingles (doctype, field, value) values (%s,%s,%s)",
					(_SETTINGS, c, valores[c]))

	def test_moeda_brl(self):
		self.assertEqual(moeda_brl(1234.5), "R$ 1.234,50")
		self.assertEqual(moeda_brl(9), "R$ 9,00")

	def test_exibicao_textos(self):
		r = preco_loja_exibicao("X", 1000)
		self.assertEqual(r["texto_pix"], "R$ 900,00 no Pix")
		self.assertEqual(r["texto_parcelado"], "em até 4 x de R$ 300,00")
		self.assertEqual((r["pix"], r["parcelas"], r["parcela"]), (900.0, 4, 300.0))

	def test_pagina_mostra_pix_e_parcelado(self):
		html = _bloco("page_content", _ctx_pagina(500))
		self.assertEqual(html.count("R$ 450,00 no Pix"), 2)  # página + relacionado
		self.assertEqual(html.count("em até 4 x de R$ 150,00"), 2)
		self.assertNotIn("NATIVO", html)

	def test_abaixo_do_minimo_so_pix(self):
		html = _bloco("page_content", _ctx_pagina(100))
		self.assertIn("R$ 90,00 no Pix", html)
		self.assertNotIn("em até", html)

	def test_sem_parametros_preco_nativo(self):
		self._set({})
		html = _bloco("page_content", _ctx_pagina(500))
		self.assertIn("R$ NATIVO", html)
		self.assertNotIn("no Pix", html)

	def test_sem_preco_nenhuma_linha(self):
		html = _bloco("page_content", _ctx_pagina(0))
		self.assertNotIn("no Pix", html)
		self.assertNotIn("em até", html)
