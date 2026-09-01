from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.conta import verificacao

_DADOS = {
	"nome": "Ana Souza",
	"email": "ana.nova@exemplo.com",
	"celular": "51999881234",
	"cpf": "39053344705",  # CPF válido de teste
	"dob": "1990-05-10",
	"sexo": "Female",
}


class TestSolicitarCodigo(FrappeTestCase):
	def setUp(self):
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = "203.0.113.9"

		# Precondição: canal e-mail disponível, sem depender do estado
		# ambiental do bench (mesmo padrão de test_conta_canais.py).
		conta = frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_id": "verificacao-teste@exemplo.com",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"smtp_server": "127.0.0.1",
				"awaiting_password": 1,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc,
			"Email Account",
			conta.name,
			force=True,
			ignore_permissions=True,
		)

		# Nenhum teste pode tocar a rede: mocka o envio de verdade.
		patcher = patch("imunocare_ecommerce.conta.canais.enviar")
		self.addCleanup(patcher.stop)
		patcher.start()

	def test_resposta_nao_contem_o_codigo(self):
		r = verificacao.solicitar_codigo("email", dict(_DADOS))
		self.assertNotIn("codigo", r)
		for valor in r.values():
			self.assertNotRegex(str(valor), r"^\d{6}$")

	def test_devolve_destino_mascarado_e_validade(self):
		r = verificacao.solicitar_codigo("email", dict(_DADOS))
		self.assertEqual(r["destino_mascarado"], "a***@exemplo.com")
		self.assertEqual(r["expira_em"], 600)

	def test_cpf_novo_usa_o_contato_digitado(self):
		self.assertEqual(_DADOS["email"], verificacao._destino_de_envio("email", dict(_DADOS)))

	def test_cpf_ja_cadastrado_usa_o_contato_do_cadastro(self):
		"""Quem digita CPF alheio não recebe nada — o código vai para o dono."""
		paciente = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Bruno",
				# ``middle_name`` explícito: o Property Setter que o torna
				# obrigatório (imunocare_clinic_ext/install.py
				# NATIVE_PROPERTY_SETTERS) sobrevive ao after_migrate mesmo
				# depois do patch desta feature — defeito de outro app, fora
				# do escopo desta task (ver riscos no relatório da Task 4).
				"middle_name": "de",
				"last_name": "Lima",
				"sex": "Male",
				"dob": "1985-02-02",
				"cpf": "52998224725",
				"mobile": "51988776655",
				"email": "bruno.dono@exemplo.com",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Patient", paciente.name, force=True)

		dados = dict(_DADOS, cpf="52998224725", email="invasor@exemplo.com")
		self.assertEqual(
			verificacao._destino_de_envio("email", dados), "bruno.dono@exemplo.com"
		)

	def test_canal_indisponivel_e_recusado(self):
		if not verificacao.canais_disponiveis()["whatsapp"]:
			with self.assertRaises(frappe.ValidationError):
				verificacao.solicitar_codigo("whatsapp", dict(_DADOS))
