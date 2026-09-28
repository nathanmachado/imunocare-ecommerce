"""Change ``area-do-medico-parceiro``, task 3.1 (D6, D8, D9) —
``www/area_do_medico.get_context``.

Cobre só o requisito desta task: controle de acesso no servidor (Guest,
cliente comum, médico revogado/sem acesso, médico com acesso) e o
tratamento de ``de``/``ate`` (padrão, inválidas, invertidas) — nunca lê
médico do request. A consulta em si (``aplicacoes_do_medico``) já tem
suíte própria em ``imunocare_clinic_ext`` (task 2.1); aqui ela é mockada
para isolar a página, exceto onde o teste exige o fluxo real do cadastro
(conceder/revogar, D3/D4/D5, já testado em ``imunocare_clinic_ext`` também
— usado aqui só para produzir um médico real com/sem acesso).

Reuso: mesmo padrão de criação de Website User de teste de
``test_booking.py::_novo_website_user``; mesmo padrão de cadastro real do
médico parceiro (``imun_acesso_site`` + ``imun_email`` no Healthcare
Practitioner External) de
``imunocare_clinic_ext/tests/test_area_do_medico_parceiro.py::_inserir_com_acesso``.

Correção da revisão do CTO (rodada 2): o Jinja do Frappe roda sem
``autoescape`` (``frappe/utils/jinja.py``) — ``paciente``/``produto`` vêm de
cadastro/reserva de visitante (texto livre), então o template escapa cada
valor dinâmico (``| e``) explicitamente. ``TestTemplateRenderaSemXss``
renderiza só o bloco ``page_content`` do template real (via
``Template.blocks``, sem precisar montar toda a cadeia de
``{% extends %}`` de ``templates/web.html``/``templates/base.html``, que
exige contexto de request que este teste não tem) e confere: HTML
malicioso escapado, dose formatada ("2ª dose"/"—") e a tabela envolvida em
``table-responsive`` (celular).
"""

from __future__ import annotations

import itertools
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, nowdate
from frappe.utils.jinja import get_jenv

from imunocare_ecommerce.www.area_do_medico import get_context

_TEMPLATE_PATH = "imunocare_ecommerce/www/area-do-medico.html"


def _render_page_content(context: dict) -> str:
	"""Renderiza só o bloco ``page_content`` do template real (o mesmo
	arquivo usado em produção), sem depender de ``base_template_path``/
	``show_sidebar``/etc. que só existem numa requisição web de verdade."""
	tmpl = get_jenv().get_template(_TEMPLATE_PATH)
	jinja_context = tmpl.new_context(context)
	return "".join(tmpl.blocks["page_content"](jinja_context))

_EMAIL_SEQ = itertools.count(1)


def _apagar_definitivamente(doctype: str, name: str) -> None:
	if frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		frappe.db.commit()


def _novo_email_de_teste(prefixo: str) -> str:
	return f"area.medico.pagina.{prefixo}.{next(_EMAIL_SEQ)}@example.com"


class TestAreaDoMedicoGetContext(FrappeTestCase):
	def setUp(self):
		self._usuario_antes = frappe.session.user
		self._form_dict_antes = frappe.local.form_dict
		frappe.local.form_dict = frappe._dict()

	def tearDown(self):
		frappe.local.form_dict = self._form_dict_antes
		frappe.set_user("Administrator")

	# -- helpers -----------------------------------------------------------

	def _novo_website_user(self, prefixo: str) -> str:
		email = _novo_email_de_teste(prefixo)
		u = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Teste",
				"last_name": prefixo,
				"send_welcome_email": 0,
				"user_type": "Website User",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_apagar_definitivamente, "User", u.name)
		return u.name

	def _novo_medico_com_acesso(self, prefixo: str) -> tuple[str, str]:
		"""Fluxo real do cadastro (D3/D4): External + ``imun_acesso_site=1`` +
		``imun_email`` cria (ou reaproveita) o Website User e liga
		``user_id``. Devolve (practitioner_name, email/login)."""
		email = _novo_email_de_teste(prefixo)
		doc = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": f"Dr(a) {prefixo}",
				"status": "Active",
				"practitioner_type": "External",
				"imun_acesso_site": 1,
				"imun_email": email,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_apagar_definitivamente, "Healthcare Practitioner", doc.name)
		self.addCleanup(_apagar_definitivamente, "User", email)
		return doc.name, email

	# -- controle de acesso --------------------------------------------------

	def test_guest_redireciona_para_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			get_context(frappe._dict())
		self.assertEqual(frappe.flags.redirect_location, "/login?redirect-to=/area-do-medico")

	def test_cliente_comum_nao_tem_acesso(self):
		email = self._novo_website_user("cliente")
		frappe.set_user(email)
		with self.assertRaises(frappe.PermissionError):
			get_context(frappe._dict())

	def test_medico_revogado_nao_tem_acesso(self):
		practitioner, email = self._novo_medico_com_acesso("revogado")
		doc = frappe.get_doc("Healthcare Practitioner", practitioner)
		doc.imun_acesso_site = 0
		doc.save(ignore_permissions=True)
		frappe.db.commit()

		frappe.set_user(email)
		with self.assertRaises(frappe.PermissionError):
			get_context(frappe._dict())

	# -- médico com acesso: contexto e blindagem do request -----------------

	def test_medico_com_acesso_recebe_as_proprias_linhas_e_ignora_practitioner_do_request(self):
		practitioner, email = self._novo_medico_com_acesso("comacesso")
		frappe.set_user(email)

		linhas = [{"paciente": "Maria", "produto": "Shingrix", "dose": "1ª dose", "data": getdate(nowdate())}]
		frappe.local.form_dict = frappe._dict({"practitioner": "Outro Doutor Qualquer"})

		with patch("imunocare_clinic_ext.area_medico.aplicacoes_do_medico") as mock_aplicacoes:
			mock_aplicacoes.return_value = linhas
			context = get_context(frappe._dict())

		self.assertEqual(context.aplicacoes, linhas)
		self.assertIsNone(context.aviso)
		mock_aplicacoes.assert_called_once()
		medico_chamado = mock_aplicacoes.call_args[0][0]
		self.assertEqual(medico_chamado, practitioner)
		self.assertNotEqual(medico_chamado, "Outro Doutor Qualquer")

	def test_datas_invalidas_caem_no_padrao_de_90_dias(self):
		_practitioner, email = self._novo_medico_com_acesso("datainvalida")
		frappe.set_user(email)
		frappe.local.form_dict = frappe._dict({"de": "nao-e-uma-data", "ate": ""})

		with patch("imunocare_clinic_ext.area_medico.aplicacoes_do_medico") as mock_aplicacoes:
			mock_aplicacoes.return_value = []
			context = get_context(frappe._dict())

		ate_esperado = getdate(nowdate())
		de_esperado = add_days(ate_esperado, -90)
		self.assertEqual(context.ate, ate_esperado)
		self.assertEqual(context.de, de_esperado)
		mock_aplicacoes.assert_called_once_with(_practitioner, de_esperado, ate_esperado)

	def test_de_maior_que_ate_mostra_lista_vazia_com_aviso(self):
		_practitioner, email = self._novo_medico_com_acesso("deforadeordem")
		frappe.set_user(email)
		frappe.local.form_dict = frappe._dict({"de": "2026-09-20", "ate": "2026-09-10"})

		with patch("imunocare_clinic_ext.area_medico.aplicacoes_do_medico") as mock_aplicacoes:
			context = get_context(frappe._dict())

		self.assertEqual(context.aplicacoes, [])
		self.assertTrue(context.aviso)
		mock_aplicacoes.assert_not_called()


# ---------------------------------------------------------------------------
# Correção da revisão do CTO (rodada 2): template sem autoescape — escapar
# todo valor dinâmico; dose formatada "Nª dose"/"—"; tabela em
# table-responsive (celular).
# ---------------------------------------------------------------------------


class TestTemplateAreaDoMedicoEscapaEFormata(FrappeTestCase):
	def _contexto_base(self, **overrides) -> dict:
		context = {
			"de": getdate("2026-01-01"),
			"ate": getdate("2026-09-01"),
			"aviso": None,
			"aplicacoes": [],
		}
		context.update(overrides)
		return context

	def test_paciente_e_produto_com_html_saem_escapados(self):
		"""Achado da revisão: sem ``autoescape`` no Jinja do Frappe
		(``frappe/utils/jinja.py``), ``paciente`` (reserva de visitante) e
		``produto`` (cadastro) renderizados crus seriam XSS armazenado."""
		html = _render_page_content(
			self._contexto_base(
				aplicacoes=[
					{
						"paciente": "<script>alert(1)</script>",
						"produto": "Vac & Cia <b>forte</b>",
						"dose": 2,
						"data": getdate("2026-05-01"),
					}
				]
			)
		)
		self.assertNotIn("<script>alert(1)</script>", html)
		self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
		self.assertNotIn("<b>forte</b>", html)
		self.assertIn("Vac &amp; Cia &lt;b&gt;forte&lt;/b&gt;", html)

	def test_aviso_com_html_sai_escapado(self):
		html = _render_page_content(
			self._contexto_base(aviso='<img src=x onerror="alert(1)">')
		)
		self.assertNotIn('<img src=x onerror="alert(1)">', html)
		self.assertIn("&lt;img src=x onerror=", html)

	def test_dose_formatada_com_numero_e_vazia_com_travessao(self):
		html = _render_page_content(
			self._contexto_base(
				aplicacoes=[
					{"paciente": "Maria", "produto": "Shingrix", "dose": 2, "data": getdate("2026-05-01")},
					{"paciente": "João", "produto": "Shingrix", "dose": None, "data": getdate("2026-05-02")},
				]
			)
		)
		self.assertIn("2ª dose", html)
		self.assertIn("—", html)
		self.assertNotIn("<td>2</td>", html)

	def test_tabela_em_table_responsive(self):
		html = _render_page_content(
			self._contexto_base(
				aplicacoes=[
					{"paciente": "Maria", "produto": "Shingrix", "dose": 1, "data": getdate("2026-05-01")}
				]
			)
		)
		self.assertIn('<div class="table-responsive">', html)
		self.assertIn("</table>\n\t</div>", html)
