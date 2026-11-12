"""vitrine-sem-marca 2.3: a API da listagem acrescenta imun_preco a cada item."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.catalogo.api import _enriquecer_com_preco_loja
from imunocare_ecommerce.catalogo.preco_jinja import preco_loja_exibicao
from imunocare_ecommerce.tests.test_preco_vitrine_render import _CAMPOS, _le, _sem_fiscal, _SETTINGS, _TESTE


class TestPrecoVitrineApi(FrappeTestCase):
	def setUp(self):
		self._orig = {c: _le(c) for c in _CAMPOS}

	def tearDown(self):
		self._grava(self._orig)

	def _grava(self, valores):
		for c in _CAMPOS:
			frappe.db.sql("delete from tabSingles where doctype=%s and field=%s", (_SETTINGS, c))
			if valores.get(c) is not None:
				frappe.db.sql(
					"insert into tabSingles (doctype, field, value) values (%s,%s,%s)", (_SETTINGS, c, valores[c]))
		frappe.clear_cache(doctype=_SETTINGS)

	def test_imun_preco_igual_ao_da_pagina(self):
		self._grava(_TESTE)
		itens = [frappe._dict(item_code="X-1", price_list_rate=1000), frappe._dict(item_code="X-2")]
		_enriquecer_com_preco_loja(itens)
		self.assertEqual(itens[0]["imun_preco"], preco_loja_exibicao("X-1", 1000))
		self.assertEqual(itens[0]["imun_preco"]["texto_pix"], "R$ 900,00 no Pix")
		self.assertIsNone(itens[1]["imun_preco"])

	def test_fiscal_ausente_none(self):
		self._grava(_TESTE)
		itens = [frappe._dict(item_code="X-1", price_list_rate=1000)]
		with patch("frappe.get_attr", side_effect=_sem_fiscal):
			_enriquecer_com_preco_loja(itens)
		self.assertIsNone(itens[0]["imun_preco"])

	def test_sem_parametros_none(self):
		self._grava({})
		itens = [frappe._dict(item_code="X-1", price_list_rate=1000)]
		_enriquecer_com_preco_loja(itens)
		self.assertIsNone(itens[0]["imun_preco"])
