import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.conta import canais


class TestCanais(FrappeTestCase):
	def test_mascara_email_preservando_a_primeira_letra(self):
		self.assertEqual(canais.mascarar("email", "ana@exemplo.com"), "a***@exemplo.com")

	def test_mascara_celular_preservando_os_4_ultimos(self):
		self.assertEqual(canais.mascarar("whatsapp", "51999881234"), "*******1234")

	def test_email_disponivel_so_com_conta_padrao(self):
		self.assertEqual(
			canais.disponiveis()["email"],
			bool(frappe.db.exists("Email Account", {"default_outgoing": 1})),
		)

	def test_whatsapp_exige_template_authentication_aprovado(self):
		esperado = bool(
			frappe.db.exists(
				"WhatsApp Templates", {"category": "AUTHENTICATION", "status": "APPROVED"}
			)
		)
		self.assertEqual(canais.disponiveis()["whatsapp"], esperado)

	def test_canal_desconhecido_e_recusado(self):
		with self.assertRaises(frappe.ValidationError):
			canais.enviar("pombo-correio", "ana@exemplo.com", "123456", "Ana")
