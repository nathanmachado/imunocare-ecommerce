"""Cobertura do fix crítico 2026-09-01 — ``info_agendamento``/``info_agendamento_tipo``
passam a devolver ``time_zone``/``date_format``/``time_format`` para o JS
(``imun_garantir_boot_datas``, ``public/js/agendamento.js``) preencher o boot
ANTES de montar qualquer ``frappe.ui.Dialog`` com campo Date — sem isso o
diálogo de agendamento nem abria (``Cannot read properties of undefined
(reading 'time_zone')``), no bench e em produção, para visitante e logado.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.agendamento import booking


def _apagar_definitivamente(doctype: str, name: str) -> None:
	# Delete + commit: mesmo padrão de test_conta_verificacao.py — sem
	# commitar aqui, o rollback de fim-de-teste do FrappeTestCase desfaz só
	# a exclusão e ressuscita o fixture para a próxima classe.
	if frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		frappe.db.commit()


class TestResolverPacienteNaoAdotaOrfaoPorNomeInformado(FrappeTestCase):
	"""CRÍTICO 2 da revisão 2026-09-02 — adoção de Patient órfão por nome
	adivinhável.

	``criar_agendamento`` é ``@frappe.whitelist()`` (não ``allow_guest``,
	mas QUALQUER Website User autenticado pode chamá-la direto, fora do
	fluxo da loja) e aceitava um ``patient`` informado pelo cliente,
	adotando-o para a sessão sempre que aquele Patient não tivesse
	``user_id`` — o nome (``HLC-PAT-AAAA-#####``) é enumerável, e "sem
	user_id" não é prova de posse nenhuma (era o estado de TODOS os 12
	Patients de produção). Fix: um ``patient`` explícito só é aceito se JÁ
	pertencer à sessão atual."""

	def setUp(self):
		self._usuario_antes = frappe.session.user

	def tearDown(self):
		frappe.set_user(self._usuario_antes)

	def _novo_website_user(self, prefixo: str):
		email = f"{prefixo}.{frappe.generate_hash(length=6)}@exemplo.com"
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

	def _novo_patient_orfao(self, prefixo: str, user_id: str | None = None):
		p = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": prefixo,
				"middle_name": "de",
				"last_name": "Teste",
				"sex": "Male",
				"dob": "1990-01-01",
				"user_id": user_id,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		self.addCleanup(_apagar_definitivamente, "Patient", p.name)
		return p

	def test_patient_orfao_informado_pelo_cliente_e_recusado_e_nao_e_adotado(self):
		vitima = self._novo_patient_orfao("VitimaOrfao")
		self.assertFalse(vitima.user_id, "precondição: órfão, igual aos 12 de produção")

		atacante = self._novo_website_user("atacante.booking")
		frappe.set_user(atacante)

		with self.assertRaises(frappe.ValidationError):
			booking._resolver_paciente(vitima.name, None)

		# nunca adota — user_id continua vazio, não vira o do atacante.
		self.assertFalse(frappe.db.get_value("Patient", vitima.name, "user_id"))

	def test_patient_de_outra_conta_continua_recusado(self):
		"""Regressão: Patient já vinculado a OUTRA conta (não órfão) já era
		recusado antes deste fix — continua sendo."""
		dono = self._novo_website_user("dono.booking")
		patient_do_dono = self._novo_patient_orfao("PatientDoDono", user_id=dono)

		outro = self._novo_website_user("outro.booking")
		frappe.set_user(outro)

		with self.assertRaises(frappe.ValidationError):
			booking._resolver_paciente(patient_do_dono.name, None)

	def test_patient_que_ja_pertence_a_sessao_e_aceito(self):
		"""Caminho legítimo: o fluxo interno de verificação (Task 5) grava
		``user_id`` no Patient ANTES de chamar ``criar_agendamento`` — por
		isso ``pac.user_id == user`` já bate quando chega aqui, e não pode
		quebrar."""
		usuario = self._novo_website_user("proprio.booking")
		patient_proprio = self._novo_patient_orfao("PatientProprio", user_id=usuario)
		frappe.set_user(usuario)

		resultado = booking._resolver_paciente(patient_proprio.name, None)
		self.assertEqual(resultado, patient_proprio.name)

	def test_patient_inexistente_e_recusado(self):
		usuario = self._novo_website_user("nome.invalido.booking")
		frappe.set_user(usuario)
		with self.assertRaises(frappe.ValidationError):
			booking._resolver_paciente("HLC-PAT-0000-99999", None)


class TestBootDatas(FrappeTestCase):
	"""Unidade: ``_boot_datas`` nunca lança e sempre devolve os 3 campos, com o
	fuso correto conforme haja (ou não) usuário logado com fuso próprio."""

	def setUp(self):
		self._usuario_antes = frappe.session.user
		self._sysdefaults_tz_antes = frappe.db.get_single_value("System Settings", "time_zone")

	def tearDown(self):
		frappe.set_user(self._usuario_antes)

	def test_formato_do_retorno_como_guest(self):
		frappe.set_user("Guest")
		dados = booking._boot_datas()

		self.assertIn("time_zone", dados)
		self.assertIn("system", dados["time_zone"])
		self.assertIn("user", dados["time_zone"])
		self.assertTrue(dados["time_zone"]["system"], "sem fuso de sistema o ControlDate quebra igual")
		# Guest não tem User.time_zone — cai no fuso do sistema (mesma
		# convenção de frappe.website.utils.get_boot_data).
		self.assertEqual(dados["time_zone"]["user"], dados["time_zone"]["system"])
		self.assertIn("date_format", dados)
		self.assertIn("time_format", dados)
		self.assertTrue(dados["date_format"])
		self.assertTrue(dados["time_format"])

	def test_time_zone_do_usuario_logado_prevalece_quando_configurado(self):
		email = f"boot.datas.{frappe.generate_hash(length=6)}@exemplo.com"
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": "Teste Boot Datas",
				"send_welcome_email": 0,
				"time_zone": "America/New_York",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_apagar_definitivamente, "User", user.name)

		frappe.set_user(user.name)
		dados = booking._boot_datas()

		self.assertEqual(dados["time_zone"]["user"], "America/New_York")
		# O fuso do SISTEMA nunca muda por causa do usuário — só o "user".
		self.assertEqual(dados["time_zone"]["system"], frappe.utils.get_system_timezone())


class TestInfoAgendamentoTipoTrazBootDatas(FrappeTestCase):
	"""``info_agendamento_tipo`` — fluxo F9 (sem Website Item, ex.: landing
	Protocolo de Emagrecimento). Endpoint mais simples para provar o merge
	de ``_boot_datas`` sem precisar de Item/Website Item."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._appointment_type = frappe.get_doc(
			{
				"doctype": "Appointment Type",
				"appointment_type": "Teste Boot Datas — Tipo Direto",
				"allow_booking_for": "Practitioner",
				"default_duration": 30,
			}
		).insert(ignore_permissions=True)
		cls._practitioner = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "Praticante Teste Boot Datas",
				"status": "Active",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

	@classmethod
	def tearDownClass(cls):
		_apagar_definitivamente("Appointment Type", cls._appointment_type.name)
		_apagar_definitivamente("Healthcare Practitioner", cls._practitioner.name)
		super().tearDownClass()

	def test_agendavel_traz_time_zone_e_formatos(self):
		# _resolver_practitioner (sem Website Item, sem practitioner informado)
		# só resolve sozinho quando há EXATAMENTE 1 Healthcare Practitioner
		# Active — este bench (dados reais de dev) tem vários. Fora do escopo
		# deste fix mexer nessa regra de ambiguidade; isolamos com mock para
		# testar só o que interessa aqui: o merge de _boot_datas.
		with patch.object(booking, "_resolver_practitioner", return_value=self._practitioner.name):
			r = booking.info_agendamento_tipo(self._appointment_type.name)

		self.assertTrue(r["agendavel"])
		self.assertEqual(r["practitioner"], self._practitioner.name)
		self.assertEqual(r["time_zone"]["system"], frappe.utils.get_system_timezone())
		self.assertEqual(
			r["date_format"], frappe.get_system_settings("date_format") or "yyyy-mm-dd"
		)
		self.assertEqual(
			r["time_format"], frappe.get_system_settings("time_format") or "HH:mm:ss"
		)

	def test_nao_agendavel_nao_precisa_trazer_boot_datas(self):
		# appointment_type inexistente -> {"agendavel": False} cedo (o JS nem
		# chega a montar o diálogo nesse caso) — não é bug NÃO trazer boot
		# aqui, só confirmamos que continua sem lançar 500.
		r = booking.info_agendamento_tipo("Tipo De Agendamento Que Nao Existe")
		self.assertEqual(r, {"agendavel": False})


class TestInfoAgendamentoItemTrazBootDatas(FrappeTestCase):
	"""Fluxo normal da loja: Website Item -> ``info_agendamento``."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._appointment_type = frappe.get_doc(
			{
				"doctype": "Appointment Type",
				"appointment_type": "Teste Boot Datas — Item Da Loja",
				"allow_booking_for": "Practitioner",
				"default_duration": 15,
			}
		).insert(ignore_permissions=True)
		cls._practitioner = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "Praticante Teste Boot Datas Item",
				"status": "Active",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		if not frappe.db.exists("Item Group", "Todos os Grupos de Item"):
			# nome pt-BR pode não existir no bench de teste — cai para o
			# grupo raiz nativo, que sempre existe.
			cls._item_group = "All Item Groups"
		else:
			cls._item_group = "Todos os Grupos de Item"

		cls._item_code = f"TESTE-BOOT-DATAS-{frappe.generate_hash(length=6)}"
		cls._item = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls._item_code,
				"item_name": cls._item_code,
				"item_group": cls._item_group,
				"stock_uom": "Nos",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		cls._website_item = frappe.get_doc(
			{
				"doctype": "Website Item",
				"item_code": cls._item_code,
				"web_item_name": cls._item_code,
				"item_name": cls._item_code,
				"published": 1,
				"imun_appointment_type": cls._appointment_type.name,
				"imun_practitioner": cls._practitioner.name,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

	@classmethod
	def tearDownClass(cls):
		_apagar_definitivamente("Website Item", cls._website_item.name)
		_apagar_definitivamente("Item", cls._item.name)
		_apagar_definitivamente("Appointment Type", cls._appointment_type.name)
		_apagar_definitivamente("Healthcare Practitioner", cls._practitioner.name)
		super().tearDownClass()

	def test_agendavel_traz_time_zone_e_formatos(self):
		r = booking.info_agendamento(self._item_code)

		self.assertTrue(r["agendavel"])
		self.assertEqual(r["practitioner"], self._practitioner.name)
		self.assertEqual(r["time_zone"]["system"], frappe.utils.get_system_timezone())
		self.assertIn("date_format", r)
		self.assertIn("time_format", r)
