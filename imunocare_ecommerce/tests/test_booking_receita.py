"""Change ``venda-sob-receita``, task 4.1 — confirmação de posse da receita ao
agendar pelo site.

Casos (a)-(f) do ``tasks.md``:
  (a) ``info_agendamento`` de item marcado devolve ``exige_receita=True``, de
      item não marcado devolve ``False``.
  (b) ``criar_agendamento`` de item marcado sem ``receita_confirmada`` é
      recusado.
  (c) com ``receita_confirmada=True`` cria o Appointment com
      ``imun_receita_declarada=1``.
  (d) item não marcado não exige o parâmetro.
  (e) fluxo visitante completo (emitir -> conferir -> ``confirmar_codigo_e_agendar``
      com ``receita_confirmada`` no payload) cria o Appointment com a
      declaração gravada.
  (f) mesmo teste (e) repetido para ``confirmar_codigo_e_vincular_logado``.
  (g) achado do CTO na verificação em navegador da 4.2: ``frappe.call`` do
      storefront chega ao servidor com ``receita_confirmada`` como STRING
      (``"true"``/``"false"``), nunca como ``bool`` Python — o caminho direto
      logado (JS) nunca passava com o box marcado porque
      ``frappe.utils.cint("true") == 0``. Estes testes chamam
      ``criar_agendamento``/``confirmar_codigo_e_agendar``/
      ``confirmar_codigo_e_vincular_logado`` com STRING, imitando o payload
      HTTP real, tanto para aceitar (``"true"``/``"1"``) quanto para recusar
      (``"false"``/``"0"``).

CPFs de teste: gerados por ``_cpf_valido`` (dígito verificador correto, nunca
os CPFs "clássicos" já em uso por dados manuais do projeto — 52998224725,
11144477735 etc.).
"""

from __future__ import annotations

import random
import secrets

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.agendamento import booking
from imunocare_ecommerce.conta import codigo as mod_codigo
from imunocare_ecommerce.conta import verificacao

_IP_TESTE = "203.0.113.77"


def _apagar_definitivamente(doctype: str, name: str) -> None:
	# Delete + commit: teste de agendamento comita (cicatriz do projeto —
	# feedback_frappe_test_commit_appointment); sem isso, o rollback de
	# fim-de-classe do FrappeTestCase desfaz só a limpeza e ressuscita o
	# registro comitado.
	if frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep


def _cpf_valido() -> str:
	"""CPF de teste com dígito verificador correto, gerado a cada chamada —
	nunca um CPF "clássico" (52998224725, 11144477735 etc.) já em uso por
	dados manuais do projeto (feedback_run_tests_module_reseta_defaults /
	memória do projeto)."""
	digitos = [random.randint(0, 9) for _ in range(9)]
	if len(set(digitos)) == 1:
		digitos[0] = (digitos[0] + 1) % 10

	def _dv(seq: list[int]) -> int:
		tam = len(seq)
		soma = sum(d * (tam + 1 - i) for i, d in enumerate(seq))
		return (soma * 10 % 11) % 10

	d1 = _dv(digitos)
	d2 = _dv(digitos + [d1])
	return "".join(str(d) for d in digitos + [d1, d2])


def _identidade_unica(prefixo: str) -> tuple[str, str]:
	sufixo = frappe.generate_hash(length=6)
	email = f"{prefixo}.{sufixo}@exemplo.com"
	celular = "519" + str(random.randint(10**7, 10**8 - 1))
	return email, celular


def _limpar_rate_limit(func_dotted: str, ip: str = _IP_TESTE) -> None:
	chave = frappe.cache.make_key(f"imun_rl:{func_dotted}:{ip}")
	frappe.cache.delete(chave)


class _BaseComItemAgendavel(FrappeTestCase):
	"""Fixture comum: Appointment Type + Practitioner + Item/Website Item,
	um marcado ``imun_exige_receita=1`` e outro sem a marcação — mesmo molde
	de ``TestInfoAgendamentoItemTrazBootDatas`` (test_booking.py)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sufixo = frappe.generate_hash(length=6)

		cls._appointment_type = frappe.get_doc(
			{
				"doctype": "Appointment Type",
				"appointment_type": f"Teste Receita — Tipo {sufixo}",
				"allow_booking_for": "Practitioner",
				"default_duration": 30,
			}
		).insert(ignore_permissions=True)
		cls._practitioner = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": f"Praticante Teste Receita {sufixo}",
				"status": "Active",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		item_group = (
			"Todos os Grupos de Item"
			if frappe.db.exists("Item Group", "Todos os Grupos de Item")
			else "All Item Groups"
		)

		cls._item_code_marcado = f"TESTE-RECEITA-MARCADO-{sufixo}"
		cls._item_marcado = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls._item_code_marcado,
				"item_name": cls._item_code_marcado,
				"item_group": item_group,
				"stock_uom": "Nos",
				"imun_exige_receita": 1,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		cls._wi_marcado = frappe.get_doc(
			{
				"doctype": "Website Item",
				"item_code": cls._item_code_marcado,
				"web_item_name": cls._item_code_marcado,
				"item_name": cls._item_code_marcado,
				"published": 1,
				"imun_appointment_type": cls._appointment_type.name,
				"imun_practitioner": cls._practitioner.name,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		cls._item_code_livre = f"TESTE-RECEITA-LIVRE-{sufixo}"
		cls._item_livre = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls._item_code_livre,
				"item_name": cls._item_code_livre,
				"item_group": item_group,
				"stock_uom": "Nos",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		cls._wi_livre = frappe.get_doc(
			{
				"doctype": "Website Item",
				"item_code": cls._item_code_livre,
				"web_item_name": cls._item_code_livre,
				"item_name": cls._item_code_livre,
				"published": 1,
				"imun_appointment_type": cls._appointment_type.name,
				"imun_practitioner": cls._practitioner.name,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

	@classmethod
	def tearDownClass(cls):
		_apagar_definitivamente("Website Item", cls._wi_marcado.name)
		_apagar_definitivamente("Item", cls._item_marcado.name)
		_apagar_definitivamente("Website Item", cls._wi_livre.name)
		_apagar_definitivamente("Item", cls._item_livre.name)
		_apagar_definitivamente("Appointment Type", cls._appointment_type.name)
		_apagar_definitivamente("Healthcare Practitioner", cls._practitioner.name)
		super().tearDownClass()

	def setUp(self):
		self._usuario_antes = frappe.session.user

	def tearDown(self):
		frappe.set_user(self._usuario_antes)

	def _novo_website_user(self, prefixo: str) -> str:
		email, celular = _identidade_unica(prefixo)
		u = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Teste",
				"last_name": prefixo,
				"send_welcome_email": 0,
				"mobile_no": celular,
				"user_type": "Website User",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_apagar_definitivamente, "User", u.name)
		return u.name


class TestInfoAgendamentoExigeReceita(_BaseComItemAgendavel):
	"""(a) ``info_agendamento`` devolve ``exige_receita`` correto."""

	def test_item_marcado_devolve_exige_receita_true(self):
		r = booking.info_agendamento(self._item_code_marcado)
		self.assertTrue(r["agendavel"])
		self.assertTrue(r["exige_receita"])

	def test_item_nao_marcado_devolve_exige_receita_false(self):
		r = booking.info_agendamento(self._item_code_livre)
		self.assertTrue(r["agendavel"])
		self.assertFalse(r["exige_receita"])


class TestCriarAgendamentoExigeConfirmacao(_BaseComItemAgendavel):
	"""(b)/(c)/(d) — ``criar_agendamento`` confere a confirmação no servidor."""

	def test_item_marcado_sem_confirmacao_e_recusado(self):
		usuario = self._novo_website_user("receita.sem.confirmacao")
		frappe.set_user(usuario)

		with self.assertRaises(frappe.ValidationError):
			booking.criar_agendamento(
				appointment_date="2030-07-01",
				appointment_time="09:00:00",
				item_code=self._item_code_marcado,
				practitioner=self._practitioner.name,
				patient_data={
					"dob": "1990-01-01",
					"cpf": _cpf_valido(),
					"sex": "Male",
					"mobile": "51999112233",
				},
			)
		# Requisição direta sem a confirmação: nenhum Patient/Appointment
		# fica para trás (a recusa é ANTES de resolver/inserir paciente).
		self.assertFalse(frappe.db.exists("Patient", {"user_id": usuario}))

	def test_item_marcado_com_confirmacao_cria_e_declara(self):
		usuario = self._novo_website_user("receita.com.confirmacao")
		frappe.set_user(usuario)

		resultado = booking.criar_agendamento(
			appointment_date="2030-07-02",
			appointment_time="09:00:00",
			item_code=self._item_code_marcado,
			practitioner=self._practitioner.name,
			patient_data={
				"dob": "1990-01-01",
				"cpf": _cpf_valido(),
				"sex": "Male",
				"mobile": "51999112233",
			},
			receita_confirmada=True,
		)
		self.addCleanup(_apagar_definitivamente, "Patient Appointment", resultado["appointment"])
		paciente = frappe.db.get_value("Patient Appointment", resultado["appointment"], "patient")
		self.addCleanup(_apagar_definitivamente, "Patient", paciente)

		self.assertEqual(
			frappe.db.get_value("Patient Appointment", resultado["appointment"], "imun_receita_declarada"),
			1,
		)

	def test_item_nao_marcado_nao_exige_o_parametro(self):
		usuario = self._novo_website_user("receita.item.livre")
		frappe.set_user(usuario)

		resultado = booking.criar_agendamento(
			appointment_date="2030-07-03",
			appointment_time="09:00:00",
			item_code=self._item_code_livre,
			practitioner=self._practitioner.name,
			patient_data={
				"dob": "1990-01-01",
				"cpf": _cpf_valido(),
				"sex": "Male",
				"mobile": "51999112233",
			},
			# receita_confirmada omitido de propósito: item não marcado não
			# exige nada.
		)
		self.addCleanup(_apagar_definitivamente, "Patient Appointment", resultado["appointment"])
		paciente = frappe.db.get_value("Patient Appointment", resultado["appointment"], "patient")
		self.addCleanup(_apagar_definitivamente, "Patient", paciente)

		self.assertFalse(
			frappe.db.get_value("Patient Appointment", resultado["appointment"], "imun_receita_declarada")
		)


class TestCriarAgendamentoReceitaConfirmadaComoString(_BaseComItemAgendavel):
	"""(g) — achado do CTO na verificação em navegador: ``frappe.call`` chega
	ao servidor com ``receita_confirmada`` como STRING (imitando o payload
	HTTP real), nunca como ``bool`` Python. ``frappe.utils.sbool`` tem que
	aceitar ``"true"``/``"1"`` e recusar ``"false"``/``"0"``."""

	def test_string_true_e_aceita(self):
		usuario = self._novo_website_user("receita.string.true")
		frappe.set_user(usuario)

		resultado = booking.criar_agendamento(
			appointment_date="2030-07-06",
			appointment_time="09:00:00",
			item_code=self._item_code_marcado,
			practitioner=self._practitioner.name,
			patient_data={
				"dob": "1990-01-01",
				"cpf": _cpf_valido(),
				"sex": "Male",
				"mobile": "51999112233",
			},
			receita_confirmada="true",
		)
		self.addCleanup(_apagar_definitivamente, "Patient Appointment", resultado["appointment"])
		paciente = frappe.db.get_value("Patient Appointment", resultado["appointment"], "patient")
		self.addCleanup(_apagar_definitivamente, "Patient", paciente)

		self.assertEqual(
			frappe.db.get_value("Patient Appointment", resultado["appointment"], "imun_receita_declarada"),
			1,
		)

	def test_string_1_e_aceita(self):
		usuario = self._novo_website_user("receita.string.1")
		frappe.set_user(usuario)

		resultado = booking.criar_agendamento(
			appointment_date="2030-07-07",
			appointment_time="09:00:00",
			item_code=self._item_code_marcado,
			practitioner=self._practitioner.name,
			patient_data={
				"dob": "1990-01-01",
				"cpf": _cpf_valido(),
				"sex": "Male",
				"mobile": "51999112233",
			},
			receita_confirmada="1",
		)
		self.addCleanup(_apagar_definitivamente, "Patient Appointment", resultado["appointment"])
		paciente = frappe.db.get_value("Patient Appointment", resultado["appointment"], "patient")
		self.addCleanup(_apagar_definitivamente, "Patient", paciente)

		self.assertEqual(
			frappe.db.get_value("Patient Appointment", resultado["appointment"], "imun_receita_declarada"),
			1,
		)

	def test_string_false_e_recusada(self):
		usuario = self._novo_website_user("receita.string.false")
		frappe.set_user(usuario)

		with self.assertRaises(frappe.ValidationError):
			booking.criar_agendamento(
				appointment_date="2030-07-08",
				appointment_time="09:00:00",
				item_code=self._item_code_marcado,
				practitioner=self._practitioner.name,
				patient_data={
					"dob": "1990-01-01",
					"cpf": _cpf_valido(),
					"sex": "Male",
					"mobile": "51999112233",
				},
				receita_confirmada="false",
			)
		self.assertFalse(frappe.db.exists("Patient", {"user_id": usuario}))

	def test_string_0_e_recusada(self):
		usuario = self._novo_website_user("receita.string.0")
		frappe.set_user(usuario)

		with self.assertRaises(frappe.ValidationError):
			booking.criar_agendamento(
				appointment_date="2030-07-09",
				appointment_time="09:00:00",
				item_code=self._item_code_marcado,
				practitioner=self._practitioner.name,
				patient_data={
					"dob": "1990-01-01",
					"cpf": _cpf_valido(),
					"sex": "Male",
					"mobile": "51999112233",
				},
				receita_confirmada="0",
			)
		self.assertFalse(frappe.db.exists("Patient", {"user_id": usuario}))


class TestVisitanteRepassaReceitaConfirmadaNosDoisCaminhos(_BaseComItemAgendavel):
	"""(e)/(f) — payload do OTP carrega ``receita_confirmada`` e os DOIS
	caminhos de confirmação (``confirmar_codigo_e_agendar`` para visitante
	novo, ``confirmar_codigo_e_vincular_logado`` para logado com CPF
	colidido) repassam para ``criar_agendamento``. Regra fechada pela metade
	é cicatriz do projeto — os dois são testados, não só um."""

	def _dados_base(self, prefixo: str, receita_confirmada: bool | str = True) -> dict:
		email, celular = _identidade_unica(prefixo)
		return {
			"nome": "Visitante Receita",
			"email": email,
			"celular": celular,
			"cpf": _cpf_valido(),
			"dob": "1990-05-10",
			"sexo": "Female",
			"receita_confirmada": receita_confirmada,
			# Fora do fluxo real, `solicitar_codigo` grava estas duas chaves
			# (contato PROVADO) antes de `codigo.emitir` — aqui simulamos o
			# mesmo payload sem passar por `solicitar_codigo` (fora do
			# escopo desta task: rate limit/canal), então precisamos setá-las
			# à mão para `_garantir_usuario` funcionar.
			"canal_verificado": "email",
			"destino_verificado": email,
		}

	def test_confirmar_codigo_e_agendar_repassa_receita_confirmada(self):
		"""(e) — visitante novo: emitir -> conferir -> confirmar_codigo_e_agendar."""
		dados = self._dados_base("visitante.receita.e")
		sid = secrets.token_urlsafe(32)
		codigo_valor = mod_codigo.emitir(sid, dados)

		frappe.set_user("Guest")
		resultado = verificacao.confirmar_codigo_e_agendar(
			codigo=codigo_valor,
			appointment_date="2030-07-04",
			appointment_time="09:00:00",
			verificacao_id=sid,
			item_code=self._item_code_marcado,
			practitioner=self._practitioner.name,
		)
		frappe.set_user(self._usuario_antes)

		self.assertIn("appointment", resultado)
		self.addCleanup(_apagar_definitivamente, "Patient Appointment", resultado["appointment"])
		paciente = frappe.db.get_value("Patient Appointment", resultado["appointment"], "patient")
		self.addCleanup(_apagar_definitivamente, "Patient", paciente)
		self.addCleanup(_apagar_definitivamente, "User", resultado["usuario"])

		self.assertEqual(
			frappe.db.get_value("Patient Appointment", resultado["appointment"], "imun_receita_declarada"),
			1,
		)

	def test_confirmar_codigo_e_vincular_logado_repassa_receita_confirmada(self):
		"""(f) — mesmo teste (e), pelo caminho do usuário LOGADO com CPF já
		cadastrado num Patient órfão (``confirmar_codigo_e_vincular_logado``)."""
		cpf = _cpf_valido()
		orfao_email, orfao_celular = _identidade_unica("orfao.receita.f")
		orfao = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Orfao",
				"middle_name": "Receita",
				"last_name": "Teste",
				"sex": "Male",
				"dob": "1985-01-01",
				"cpf": cpf,
				"mobile": orfao_celular,
				"email": orfao_email,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_apagar_definitivamente, "Patient", orfao.name)

		usuario = self._novo_website_user("logado.receita.f")
		frappe.set_user(usuario)

		dados = {
			"nome": "Logado Receita",
			"email": _identidade_unica("logado.receita.f.email")[0],
			"celular": _identidade_unica("logado.receita.f.cel")[1],
			"cpf": cpf,
			"dob": "1990-05-10",
			"sexo": "Male",
			"receita_confirmada": True,
		}
		sid = secrets.token_urlsafe(32)
		codigo_valor = mod_codigo.emitir(sid, dados)

		resultado = verificacao.confirmar_codigo_e_vincular_logado(
			codigo=codigo_valor,
			appointment_date="2030-07-05",
			appointment_time="09:00:00",
			verificacao_id=sid,
			item_code=self._item_code_marcado,
			practitioner=self._practitioner.name,
		)

		self.assertIn("appointment", resultado)
		self.addCleanup(_apagar_definitivamente, "Patient Appointment", resultado["appointment"])

		self.assertEqual(
			frappe.db.get_value("Patient Appointment", resultado["appointment"], "imun_receita_declarada"),
			1,
		)
		self.assertEqual(frappe.db.get_value("Patient", orfao.name, "user_id"), usuario)

	def test_confirmar_codigo_e_agendar_aceita_receita_confirmada_como_string(self):
		"""(g) — mesmo achado do CTO, no caminho do visitante: o payload
		guardado por ``solicitar_codigo``/``codigo.emitir`` pode chegar com
		``receita_confirmada`` como STRING (``"true"``), nunca só ``bool``."""
		dados = self._dados_base("visitante.receita.g.string", receita_confirmada="true")
		sid = secrets.token_urlsafe(32)
		codigo_valor = mod_codigo.emitir(sid, dados)

		frappe.set_user("Guest")
		resultado = verificacao.confirmar_codigo_e_agendar(
			codigo=codigo_valor,
			appointment_date="2030-07-10",
			appointment_time="09:00:00",
			verificacao_id=sid,
			item_code=self._item_code_marcado,
			practitioner=self._practitioner.name,
		)
		frappe.set_user(self._usuario_antes)

		self.assertIn("appointment", resultado)
		self.addCleanup(_apagar_definitivamente, "Patient Appointment", resultado["appointment"])
		paciente = frappe.db.get_value("Patient Appointment", resultado["appointment"], "patient")
		self.addCleanup(_apagar_definitivamente, "Patient", paciente)
		self.addCleanup(_apagar_definitivamente, "User", resultado["usuario"])

		self.assertEqual(
			frappe.db.get_value("Patient Appointment", resultado["appointment"], "imun_receita_declarada"),
			1,
		)

	def test_confirmar_codigo_e_agendar_recusa_receita_confirmada_string_false(self):
		"""(g) — ``"false"`` (string) tem que continuar recusando, nunca
		``bool("false") == True`` por engano. ``_garantir_usuario`` comita a
		conta ANTES de chegar em ``criar_agendamento`` (mesmo cuidado de
		login_as de ``frappe/core/api/user_invitation.py``) — a limpeza do
		User é registrada ANTES da chamada, pelo e-mail (autoname), pra não
		deixar conta órfã comitada mesmo quando a exceção estoura depois."""
		dados = self._dados_base("visitante.receita.g.false", receita_confirmada="false")
		self.addCleanup(_apagar_definitivamente, "User", dados["email"])
		sid = secrets.token_urlsafe(32)
		codigo_valor = mod_codigo.emitir(sid, dados)

		frappe.set_user("Guest")
		try:
			with self.assertRaises(frappe.ValidationError):
				verificacao.confirmar_codigo_e_agendar(
					codigo=codigo_valor,
					appointment_date="2030-07-11",
					appointment_time="09:00:00",
					verificacao_id=sid,
					item_code=self._item_code_marcado,
					practitioner=self._practitioner.name,
				)
		finally:
			frappe.set_user(self._usuario_antes)
