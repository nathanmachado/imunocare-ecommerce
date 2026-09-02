import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.patches.v1_0.preparar_reserva_visitante import execute


class TestPreparoReservaVisitante(FrappeTestCase):
	def setUp(self):
		# imunocare.local (bench de teste) não tem nenhuma Email Account com
		# enable_outgoing — diferente da produção (Google Workspace). O patch
		# só promove uma candidata existente a default_outgoing, então o teste
		# garante essa candidata para não depender de dado ambiental.
		if not frappe.db.exists("Email Account", {"enable_outgoing": 1}):
			frappe.get_doc(
				{
					"doctype": "Email Account",
					"email_account_name": "Conta de Teste — Reserva Visitante",
					"email_id": "reserva.teste@example.com",
					"enable_outgoing": 1,
					"smtp_server": "127.0.0.1",
					"no_smtp_authentication": 1,
				}
			).insert(ignore_permissions=True)

	def test_patch_libera_cadastro_e_email_e_nome_do_meio(self):
		execute()

		self.assertEqual(
			frappe.db.get_single_value("Website Settings", "disable_signup"),
			0,
			"cadastro no site continua desligado — /login seguiria beco sem saída",
		)
		self.assertTrue(
			frappe.db.exists("Email Account", {"default_outgoing": 1}),
			"sem conta de saída padrão, todo sendmail genérico falha",
		)
		self.assertFalse(
			frappe.db.exists("Property Setter", "Patient-middle_name-reqd"),
			"middle_name obrigatório barra quem tem nome de duas palavras",
		)

	def test_patch_e_idempotente(self):
		execute()
		execute()  # não pode explodir nem duplicar nada
		self.assertEqual(
			frappe.db.count("Email Account", {"default_outgoing": 1}), 1
		)
