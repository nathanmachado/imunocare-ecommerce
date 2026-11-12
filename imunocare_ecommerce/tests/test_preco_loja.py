"""Preço da loja pela regra do fiscal (parcelas-do-cartao-pela-price); parâmetros fictícios."""

from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.catalogo.preco import preco_loja

# Juros 0 e antecipação 0: parcela = preço / n, o que isola o corte por máximo e mínima.
P = {"taxa_juros_anual": 0, "taxa_antecipacao": 0, "desconto_avista": 10, "maximo_parcelas": 4, "parcela_minima": 50}


class TestPrecoLoja(FrappeTestCase):
	def test_pix_e_maior_n_oferecido(self):
		self.assertEqual(preco_loja(500, P), {"pix": 450.0, "parcelas": 4, "parcela": 125.0})

	def test_n_e_o_maior_permitido_pela_minima(self):
		r = preco_loja(150, P)  # 3x = 50 ainda vale; 4x = 37,50 não
		self.assertEqual((r["pix"], r["parcelas"], r["parcela"]), (135.0, 3, 50.0))

	def test_so_1x_sem_parcelado(self):
		self.assertEqual(preco_loja(80, P), {"pix": 72.0})  # 2x = 40 < mínima
		self.assertEqual(preco_loja(500, {**P, "maximo_parcelas": 1}), {"pix": 450.0})

	def test_juros_encarecem_a_parcela(self):
		r = preco_loja(1000, {**P, "taxa_juros_anual": 24, "maximo_parcelas": 3})
		self.assertEqual(r["parcelas"], 3)
		self.assertGreater(r["parcela"] * 3, 1000)

	def test_nao_configurado_ou_sem_preco(self):
		with patch("imunocare_ecommerce.catalogo.preco.parametros_do_fiscal", return_value=None):
			self.assertIsNone(preco_loja(500))
		for preco in (None, "", 0, -5):
			self.assertIsNone(preco_loja(preco, P), preco)

	def test_fiscal_ausente_como_nao_configurado(self):
		with patch("frappe.get_attr", side_effect=ImportError):
			self.assertIsNone(preco_loja(500))
			self.assertIsNone(preco_loja(500, P))
