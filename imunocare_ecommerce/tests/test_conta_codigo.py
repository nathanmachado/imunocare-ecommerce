import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.conta import codigo as mod

_SID = "sid-de-teste-123"
_DADOS = {"nome": "Ana Souza", "email": "ana@exemplo.com"}


class TestCodigoVerificacao(FrappeTestCase):
	def tearDown(self):
		mod.descartar(_SID)

	def test_codigo_tem_6_digitos(self):
		c = mod.emitir(_SID, _DADOS)
		self.assertRegex(c, r"^\d{6}$")

	def test_codigo_correto_devolve_os_dados(self):
		c = mod.emitir(_SID, _DADOS)
		self.assertEqual(mod.conferir(_SID, c), _DADOS)

	def test_codigo_em_claro_nao_fica_no_redis(self):
		c = mod.emitir(_SID, _DADOS)
		cru = frappe.cache.get(mod._chave(_SID))
		self.assertNotIn(c.encode(), cru, "o código em claro está guardado")

	def test_codigo_errado_e_recusado(self):
		mod.emitir(_SID, _DADOS)
		with self.assertRaises(mod.CodigoInvalido):
			mod.conferir(_SID, "000000")

	def test_bloqueia_na_sexta_tentativa(self):
		c = mod.emitir(_SID, _DADOS)
		for _ in range(mod.MAX_TENTATIVAS):
			with self.assertRaises(mod.CodigoInvalido):
				mod.conferir(_SID, "000000")
		# esgotado: nem o código certo vale mais
		with self.assertRaises(mod.CodigoBloqueado):
			mod.conferir(_SID, c)

	def test_codigo_expirado_e_recusado(self):
		c = mod.emitir(_SID, _DADOS, ttl=1)
		frappe.cache.delete(mod._chave(_SID))  # simula a expiração
		with self.assertRaises(mod.CodigoInvalido):
			mod.conferir(_SID, c)

	def test_uso_bem_sucedido_queima_o_codigo(self):
		c = mod.emitir(_SID, _DADOS)
		mod.conferir(_SID, c)
		with self.assertRaises(mod.CodigoInvalido):
			mod.conferir(_SID, c)

	def test_chave_nasce_com_validade(self):
		mod.emitir(_SID, _DADOS, ttl=600)
		self.assertGreater(frappe.cache.ttl(mod._chave(_SID)), 0)
