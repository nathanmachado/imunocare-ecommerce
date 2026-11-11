"""Preço na loja (vitrine-sem-marca 2.1): Pix e parcelado calculados do preço do ERP.
Os parâmetros abaixo são fictícios, só para exercitar a fórmula."""

from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.catalogo.preco import preco_loja

P = {"desconto_pix": 10, "juros_vista": 0, "juros_parcelado": 20, "parcelas": 4, "parcela_minima": 50}


class TestPrecoLoja(FrappeTestCase):
	def test_acima_do_minimo(self):
		self.assertEqual(preco_loja(500, P), {"pix": 450.0, "parcelas": 4, "parcela": 150.0})

	def test_abaixo_do_minimo_so_pix(self):
		self.assertEqual(preco_loja(100, P), {"pix": 90.0})

	def test_exatamente_no_minimo(self):
		self.assertEqual(preco_loja(166.67, {**P, "parcela_minima": 50.0})["parcelas"], 4)

	def test_juros_vista_desfeito_antes_do_parcelado(self):
		r = preco_loja(110, {**P, "juros_vista": 10, "juros_parcelado": 30, "parcelas": 2, "parcela_minima": 1})
		self.assertEqual(r["parcela"], 65.0)

	def test_zero_percentual_e_valido(self):
		r = preco_loja(200, {**P, "desconto_pix": 0, "juros_parcelado": 0})
		self.assertEqual(r, {"pix": 200.0, "parcelas": 4, "parcela": 50.0})

	def test_parametro_vazio(self):
		for chave in P:
			for vazio in (None, ""):
				self.assertIsNone(preco_loja(500, {**P, chave: vazio}), chave)
		self.assertIsNone(preco_loja(500, {**P, "parcelas": 0}))
		self.assertIsNone(preco_loja(500, {**P, "parcela_minima": 0}))

	def test_preco_invalido(self):
		for preco in (None, 0, -5, ""):
			self.assertIsNone(preco_loja(preco, P))

	def test_arredondamento(self):
		r = preco_loja(100.01, {**P, "desconto_pix": 3, "juros_parcelado": 0, "parcelas": 3, "parcela_minima": 1})
		self.assertEqual(r, {"pix": 97.01, "parcelas": 3, "parcela": 33.34})
