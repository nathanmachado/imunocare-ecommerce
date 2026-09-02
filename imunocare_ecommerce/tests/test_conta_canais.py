from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.conta import canais


class TestCanais(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Campo novo (whatsapp_otp_ativo, governança 2026-09-02) — sincroniza
		# só ESTE doctype a partir do .json em disco, sem depender de um
		# `bench migrate` completo (fora do escopo permitido desta correção).
		frappe.reload_doctype("Imunocare Ecommerce Settings", force=True)

	def setUp(self):
		# Cada teste começa com a trava no estado DEFAULT (desligada) —
		# nenhum teste deste módulo pode vazar o valor para o próximo.
		frappe.db.set_single_value("Imunocare Ecommerce Settings", "whatsapp_otp_ativo", 0)

	def test_mascara_email_preservando_a_primeira_letra(self):
		self.assertEqual(canais.mascarar("email", "ana@exemplo.com"), "a***@exemplo.com")

	def test_mascara_celular_preservando_os_4_ultimos(self):
		self.assertEqual(canais.mascarar("whatsapp", "51999881234"), "*******1234")

	def test_mascara_celular_com_4_digitos_mascara_tudo(self):
		# menos de 5 dígitos: revelar os "4 últimos" seria expor o contato
		# inteiro, que é exatamente o que mascarar() existe para evitar.
		self.assertEqual(canais.mascarar("whatsapp", "1234"), "****")

	def test_mascara_celular_com_5_digitos_revela_os_4_ultimos(self):
		# Item 8 da revisão 2026-09-01 — fronteira nunca testada: exatamente
		# 5 dígitos cai no ramo "normal" (>= 5), não no "mascara tudo" (< 5).
		# Comportamento ATUAL, fixado de propósito: revela 4 dos 5 dígitos.
		self.assertEqual(canais.mascarar("whatsapp", "51999"), "*1999")

	def test_mascara_celular_com_1_digito_mascara_tudo(self):
		self.assertEqual(canais.mascarar("whatsapp", "5"), "*")

	def test_mascara_celular_string_vazia_nao_revela_nada(self):
		self.assertEqual(canais.mascarar("whatsapp", ""), "")

	def test_mascara_celular_none_nao_revela_nada(self):
		self.assertEqual(canais.mascarar("whatsapp", None), "")

	def test_mascarar_canal_desconhecido_e_recusado(self):
		# mascarar() tem que ser tão careteira com canal inválido quanto
		# enviar() — nenhum dos dois pode assumir um canal por omissão.
		with self.assertRaises(frappe.ValidationError):
			canais.mascarar("pombo-correio", "ana@exemplo.com")

	def test_email_disponivel_quando_ha_conta_padrao(self):
		conta = frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_id": "canais-teste@exemplo.com",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"smtp_server": "127.0.0.1",
				"awaiting_password": 1,
			}
		).insert(ignore_permissions=True)
		# limpeza explícita: o FrappeTestCase só faz rollback no fim da
		# classe inteira, não a cada teste — sem isso, esta conta padrão
		# vazaria para os testes seguintes (inclusive o de ausência).
		self.addCleanup(
			frappe.delete_doc,
			"Email Account",
			conta.name,
			force=True,
			ignore_permissions=True,
		)
		self.assertIs(canais.disponiveis()["email"], True)

	def test_email_indisponivel_sem_conta_padrao(self):
		# Não há Email Account com default_outgoing=1 neste bench (o teste
		# anterior limpa a que cria); confirma o ramo negativo de verdade.
		self.assertIs(canais.disponiveis()["email"], False)

	def test_whatsapp_disponivel_com_template_aprovado_e_trava_ligada(self):
		# Criar um WhatsApp Templates de verdade dispara o hook
		# after_insert do frappe_whatsapp, que faz POST real para a API da
		# Meta (frappe_whatsapp/doctype/whatsapp_templates/whatsapp_templates.py,
		# método after_insert -> make_post_request). Isso violaria "nenhum
		# teste pode tocar rede", então mockamos frappe.db.exists — que é o
		# único ponto de leitura de disponiveis() para este canal — em vez
		# de inserir o documento.
		frappe.db.set_single_value("Imunocare Ecommerce Settings", "whatsapp_otp_ativo", 1)
		with patch.object(frappe.db, "exists", return_value=True):
			self.assertIs(canais.disponiveis()["whatsapp"], True)

	def test_whatsapp_indisponivel_sem_template_aprovado_mesmo_com_trava_ligada(self):
		frappe.db.set_single_value("Imunocare Ecommerce Settings", "whatsapp_otp_ativo", 1)
		with patch.object(frappe.db, "exists", return_value=False):
			self.assertIs(canais.disponiveis()["whatsapp"], False)

	def test_whatsapp_indisponivel_com_trava_desligada_mesmo_com_template_aprovado(self):
		"""GOVERNANÇA (revisão 2026-09-02): antes desta trava, um template
		AUTHENTICATION aprovado na Meta acendia o canal sozinho, sem deploy e
		sem revisão humana. Default DESLIGADO — aprovação de template
		sozinha não basta mais."""
		frappe.db.set_single_value("Imunocare Ecommerce Settings", "whatsapp_otp_ativo", 0)
		with patch.object(frappe.db, "exists", return_value=True):
			self.assertIs(canais.disponiveis()["whatsapp"], False)

	def test_canal_desconhecido_e_recusado(self):
		with self.assertRaises(frappe.ValidationError):
			canais.enviar("pombo-correio", "ana@exemplo.com", "123456", "Ana")

	def test_enviar_email_chama_sendmail_com_destinatario_e_codigo(self):
		with patch("imunocare_ecommerce.conta.canais.frappe.sendmail") as mock_sendmail:
			canais.enviar("email", "ana@exemplo.com", "654321", "Ana")

		mock_sendmail.assert_called_once()
		_args, kwargs = mock_sendmail.call_args
		self.assertEqual(kwargs["recipients"], ["ana@exemplo.com"])
		self.assertIn("654321", kwargs["message"])

	def test_enviar_email_nunca_poe_o_codigo_no_assunto(self):
		"""Item 7 da revisão 2026-09-02: o Email Queue gravado pelo
		frappe.sendmail persiste assunto E corpo — código no assunto ficava
		legível em claro no banco para quem tiver leitura do doctype,
		contradizendo "nada toca o banco antes do código conferir"."""
		with patch("imunocare_ecommerce.conta.canais.frappe.sendmail") as mock_sendmail:
			canais.enviar("email", "ana@exemplo.com", "654321", "Ana")

		_args, kwargs = mock_sendmail.call_args
		self.assertNotIn("654321", kwargs["subject"])

	def test_enviar_whatsapp_insere_whatsapp_message_outgoing_com_codigo(self):
		with (
			patch.object(frappe.db, "get_value", return_value="codigo_verificacao-pt_BR"),
			patch("imunocare_ecommerce.conta.canais.frappe.get_doc") as mock_get_doc,
		):
			mock_doc = mock_get_doc.return_value
			canais.enviar("whatsapp", "51999881234", "654321", "Ana")

		args, _kwargs = mock_get_doc.call_args
		payload = args[0]
		self.assertEqual(payload["doctype"], "WhatsApp Message")
		self.assertEqual(payload["type"], "Outgoing")
		self.assertEqual(payload["to"], "51999881234")
		self.assertIn("654321", payload["body_param"])
		mock_doc.insert.assert_called_once_with(ignore_permissions=True)
