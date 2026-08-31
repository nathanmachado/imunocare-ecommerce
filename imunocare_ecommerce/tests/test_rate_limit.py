"""Regressão do incidente 2026-08-31: contador de rate limit imortal.

O limiter nativo do Frappe perde o TTL da chave se ela expirar entre o ``GET``
e o ``INCRBY``, e o endpoint fica bloqueado para sempre. Estes testes travam o
comportamento correto do substituto em ``imunocare_ecommerce.rate_limit``.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.rate_limit import rate_limit

_IP = "203.0.113.7"  # TEST-NET-3, nunca é um cliente real


def _chave(fn):
	return frappe.cache.make_key(f"imun_rl:{fn.__module__}.{fn.__name__}:{_IP}")


class TestRateLimit(FrappeTestCase):
	def setUp(self):
		self._request_original = getattr(frappe.local, "request", None)
		self._ip_original = getattr(frappe.local, "request_ip", None)
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = _IP

	def tearDown(self):
		frappe.local.request = self._request_original
		frappe.local.request_ip = self._ip_original

	def test_bloqueia_acima_do_teto(self):
		@rate_limit(limit=2, seconds=60)
		def endpoint():
			return "ok"

		frappe.cache.delete(_chave(endpoint))

		self.assertEqual(endpoint(), "ok")
		self.assertEqual(endpoint(), "ok")
		with self.assertRaises(frappe.RateLimitExceededError):
			endpoint()

	def test_chave_sempre_nasce_com_ttl(self):
		@rate_limit(limit=5, seconds=60)
		def endpoint():
			return "ok"

		chave = _chave(endpoint)
		frappe.cache.delete(chave)

		endpoint()
		self.assertGreater(frappe.cache.ttl(chave), 0, "chave criada sem validade")

	def test_chave_orfa_sem_ttl_e_curada(self):
		"""O modo de falha do incidente: chave viva, contador estourado, TTL -1."""

		@rate_limit(limit=5, seconds=60)
		def endpoint():
			return "ok"

		chave = _chave(endpoint)
		frappe.cache.delete(chave)

		# Reproduz o estado encontrado em produção: sem TTL e acima do teto.
		frappe.cache.set(chave, 244)
		self.assertEqual(frappe.cache.ttl(chave), -1)

		with self.assertRaises(frappe.RateLimitExceededError):
			endpoint()

		# ...mas a chave já saiu imortal: agora expira sozinha.
		self.assertGreater(
			frappe.cache.ttl(chave), 0, "chave imortal continuaria bloqueando para sempre"
		)

	def test_sem_request_nao_limita(self):
		"""Job/console/scheduler não têm IP e não podem ser barrados."""

		@rate_limit(limit=1, seconds=60)
		def endpoint():
			return "ok"

		frappe.local.request = None
		for _ in range(5):
			self.assertEqual(endpoint(), "ok")
