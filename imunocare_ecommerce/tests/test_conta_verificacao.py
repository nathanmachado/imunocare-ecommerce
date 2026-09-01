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

_IP_TESTE = "203.0.113.9"


def _limpar_rate_limit_solicitar_codigo():
	# Mesmo IP em vários testes deste módulo somaria no MESMO balde do
	# rate_limit (janela de 600s) e estouraria RateLimitExceededError sem
	# relação nenhuma com o que o teste quer provar — mesmo padrão de reset
	# de test_rate_limit.py.
	chave = frappe.cache.make_key(
		f"imun_rl:imunocare_ecommerce.conta.verificacao.solicitar_codigo:{_IP_TESTE}"
	)
	frappe.cache.delete(chave)


class TestSolicitarCodigo(FrappeTestCase):
	def setUp(self):
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = _IP_TESTE
		_limpar_rate_limit_solicitar_codigo()

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
		# Precondição montada no teste (não depende do ambiente ter ou não
		# WhatsApp configurado) — mesmo padrão de test_conta_canais.py: afirma
		# sempre, nunca passa por vacuidade.
		with patch.object(
			verificacao.canais, "disponiveis", return_value={"email": True, "whatsapp": False}
		):
			with self.assertRaises(frappe.ValidationError):
				verificacao.solicitar_codigo("whatsapp", dict(_DADOS))


class TestResolverEnvio(FrappeTestCase):
	"""Fix crítico da revisão da Task 4: quando o CPF já é de um Patient, o
	contato SEMPRE vem do cadastro — nunca do que foi digitado, mesmo que o
	canal pedido esteja vazio no cadastro. Testa ``_resolver_envio``/
	``_destino_de_envio`` diretamente, sem depender de canal disponível
	(essas funções não checam disponibilidade — quem chama, checa)."""

	def test_canal_pedido_vazio_mas_outro_do_cadastro_preenchido_usa_o_outro(self):
		# email vazio simula o cadastro latente que a revisão apontou (hoje
		# email/mobile são reqd em produção — 12/12 pacientes preenchidos —
		# mas nada no código garante isso para sempre). ignore_mandatory
		# reproduz esse estado sem depender do bench.
		paciente = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Carla",
				"middle_name": "de",
				"last_name": "Nunes",
				"sex": "Female",
				"dob": "1992-04-09",
				"cpf": "16899535009",
				"mobile": "51977778888",
				"email": "",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		self.addCleanup(frappe.delete_doc, "Patient", paciente.name, force=True)

		# Pede email (vazio no cadastro); nunca pode usar o que foi digitado.
		dados = dict(_DADOS, cpf="16899535009", email="invasor@exemplo.com")
		canal_efetivo, destino = verificacao._resolver_envio("email", dados)
		self.assertEqual(canal_efetivo, "whatsapp")
		self.assertEqual(destino, "51977778888")
		# _destino_de_envio (compat) devolve só o destino do canal efetivo.
		self.assertEqual(verificacao._destino_de_envio("email", dados), "51977778888")

	def test_nenhum_contato_preenchido_no_cadastro_e_recusado(self):
		paciente = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Diego",
				"middle_name": "de",
				"last_name": "Alves",
				"sex": "Male",
				"dob": "1988-11-20",
				"cpf": "52998224725",
				"mobile": "",
				"email": "",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		self.addCleanup(frappe.delete_doc, "Patient", paciente.name, force=True)

		dados = dict(_DADOS, cpf="52998224725", email="invasor@exemplo.com")
		with self.assertRaises(frappe.ValidationError):
			verificacao._destino_de_envio("email", dados)


class TestEntradaInvalida(FrappeTestCase):
	"""Fix importante da revisão da Task 4: endpoint allow_guest não pode
	confiar no formato do payload — cada caminho abaixo estourava exceção não
	tratada (500) antes do fix."""

	def setUp(self):
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = _IP_TESTE
		_limpar_rate_limit_solicitar_codigo()

	def test_dados_json_malformado_e_recusado(self):
		with self.assertRaises(frappe.ValidationError):
			verificacao.solicitar_codigo("email", "{isto nao e json")

	def test_dados_json_valido_mas_nao_e_objeto_e_recusado(self):
		with self.assertRaises(frappe.ValidationError):
			verificacao.solicitar_codigo("email", "[1, 2, 3]")

	def test_campo_de_dados_com_tipo_inesperado_e_recusado(self):
		with self.assertRaises(frappe.ValidationError):
			verificacao.solicitar_codigo("email", dict(_DADOS, cpf=39053344705))

	def test_canal_com_tipo_inesperado_e_recusado(self):
		with self.assertRaises(frappe.ValidationError):
			verificacao.solicitar_codigo(["email"], dict(_DADOS))
