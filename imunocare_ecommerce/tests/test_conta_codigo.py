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
		# A chave é um Redis HASH (não mais um blob String) desde o fix do
		# fatiamento atômico das tentativas — GET bruto daria WRONGTYPE.
		c = mod.emitir(_SID, _DADOS)
		pipe = frappe.cache.pipeline()
		pipe.hgetall(mod._chave(_SID))
		cru = pipe.execute()[0]
		bruto = b" ".join(cru.values())
		self.assertNotIn(c.encode(), bruto, "o código em claro está guardado")

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

	def test_tentativas_bate_com_o_numero_de_chamadas_sequenciais(self):
		# Item 7 da revisão 2026-09-01: este teste é sequencial (uma chamada
		# de cada vez) — ele prova o VALOR FINAL do contador depois de N
		# chamadas em sequência, não atomicidade sob concorrência. A
		# implementação antiga (ler o JSON inteiro, somar em Python, regravar
		# o blob) também passaria neste teste sequencial; quem garante que o
		# contador não perde/dobra tentativa sob chamadas CONCORRENTES é a
		# atomicidade do HINCRBY no servidor Redis, não este teste — este é
		# só regressão do valor final.
		mod.emitir(_SID, _DADOS)
		n = 3
		for _ in range(n):
			with self.assertRaises(mod.CodigoInvalido):
				mod.conferir(_SID, "000000")

		pipe = frappe.cache.pipeline()
		pipe.hget(mod._chave(_SID), "tentativas")
		tentativas = pipe.execute()[0]
		self.assertEqual(int(tentativas), n)
