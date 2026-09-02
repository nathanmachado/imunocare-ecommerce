"""Agendamento de serviço/consulta pela loja -> Patient Appointment (Feature 55 / A1.3).

Reuso primeiro — o que este módulo NÃO reimplementa:

  - Disponibilidade de horário: ``healthcare...patient_appointment.get_availability_data``
    (mesma função usada pelo diálogo nativo do Desk). Nós só filtramos os
    slots livres a partir do ``slot_details`` que ela retorna (ver
    ``_slots_livres`` — versão simplificada da lógica de
    ``patient_appointment.js:get_slots`` para o storefront: sem grupos/
    videoconferência, só "livre x ocupado x passado").
  - Regras de status/duração/appointment_for do Patient Appointment: o
    próprio ``validate()`` do Healthcare (fetch_from de Appointment Type).
  - Cobrança: quando há item de cobrança/valor configurado no profissional
    ou no Appointment Type, reaproveitamos ``create_sales_invoice`` do
    próprio Healthcare (mesma função do botão "Invoice Appointment" do
    Desk) e então ``erpnext...make_payment_request`` com
    ``order_type="Shopping Cart"`` — o MESMO caminho que o webshop já usa
    para o carrinho (A3/pagamento/setup.py), porque o override
    ``webshop...override_doctype.payment_request.PaymentRequest.get_gateway_details``
    ignora o gateway explícito e usa sempre ``Webshop Settings.payment_gateway_account``
    quando ``order_type == "Shopping Cart"``. Não criamos nenhum código de
    gateway/checkout novo.
  - Paciente: se o usuário logado já tem um ``Patient`` (por ``user_id`` ou
    ``email``), reusa. Senão cria um Patient novo (padrão "PF sob demanda" já
    usado em ``imunocare_clinic_ext.recebimento_agendamento``), delegando a
    validação de campos obrigatórios ao próprio DocType (não replicamos a
    lista de campos obrigatórios do Patient, que é customizada pelo
    imunocare_clinic_ext e pode mudar).

Guardas: qualquer falta de configuração (Appointment Type ausente, sem
profissional, sem Practitioner Schedule, sem item de cobrança) resulta em
mensagem clara ao cliente — nunca em erro 500 "cru".
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import get_system_timezone, get_time, getdate, now_datetime

_LOG_TITLE = "imunocare_ecommerce.agendamento.booking"


def _boot_datas() -> dict:
	"""Fuso/formato de data-hora que o controle ``Date`` do Desk (``frappe.ui.Dialog``
	com ``fieldtype: "Date"``) precisa para montar sem quebrar.

	Bug real (bench e produção, visitante e logado): nosso diálogo de
	agendamento é montado numa página da LOJA (storefront), não no Desk. Lá
	``frappe.boot`` existe (o site injeta), mas ``frappe.boot.time_zone`` e
	``frappe.boot.sysdefaults``/``frappe.sys_defaults`` vêm ausentes —
	``frappe.sys_defaults`` só é preenchido a partir de ``frappe.boot.sysdefaults``
	no bootstrap do Desk (``frappe/public/js/frappe/desk.js:321``). O controle
	Date (``frappe/public/js/frappe/form/controls/date.js:make_picker`` →
	``get_now_date`` → ``frappe.datetime.now_date`` → ``_date``,
	``frappe/public/js/frappe/utils/datetime.js:237``) lê
	``frappe.boot.time_zone?.system || frappe.sys_defaults.time_zone`` — com os
	dois ausentes, estoura ``Cannot read properties of undefined (reading
	'time_zone')`` e o diálogo nunca abre. Por isso devolvemos aqui o que o JS
	da loja (``imun_garantir_boot_datas``, agendamento.js) usa para PREENCHER
	(nunca sobrescrever) o boot antes de montar qualquer diálogo com campo Date.

	Mesmo formato que ``frappe.website.utils.get_boot_data`` já usa para
	``time_zone`` (system/user) — não inventamos um shape novo."""
	time_zone_usuario = None
	if frappe.session.user != "Guest":
		time_zone_usuario = frappe.db.get_value("User", frappe.session.user, "time_zone")

	sistema = get_system_timezone()
	return {
		"time_zone": {"system": sistema, "user": time_zone_usuario or sistema},
		"date_format": frappe.get_system_settings("date_format") or "yyyy-mm-dd",
		"time_format": frappe.get_system_settings("time_format") or "HH:mm:ss",
	}


# ---------------------------------------------------------------------------
# Resolução do item agendável
# ---------------------------------------------------------------------------


def _website_item(item_code: str) -> "frappe._dict | None":
	"""Website Item pelo item_code ou pelo próprio nome do Website Item."""
	fields = ["name", "item_code", "published", "web_item_name", "imun_appointment_type", "imun_practitioner"]
	wi = frappe.db.get_value("Website Item", {"item_code": item_code}, fields, as_dict=True)
	if not wi:
		wi = frappe.db.get_value("Website Item", item_code, fields, as_dict=True)
	return wi


def _item_agendavel(item_code: str) -> tuple["frappe._dict", str]:
	"""Retorna (website_item, appointment_type) ou lança erro claro."""
	wi = _website_item(item_code)
	if not wi or not wi.published:
		frappe.throw(_("Item não encontrado ou não publicado na loja."))
	if not wi.imun_appointment_type:
		frappe.throw(
			_("Este item ainda não está configurado para agendamento online. Fale com a clínica.")
		)
	if not frappe.db.exists("Appointment Type", wi.imun_appointment_type):
		frappe.throw(
			_("O Tipo de Agendamento configurado ({0}) não existe mais.").format(wi.imun_appointment_type)
		)
	allow_booking_for = frappe.db.get_value(
		"Appointment Type", wi.imun_appointment_type, "allow_booking_for"
	)
	if allow_booking_for and allow_booking_for != "Practitioner":
		frappe.throw(
			_("Este serviço não é agendado por profissional; contate a clínica para agendar.")
		)
	return wi, wi.imun_appointment_type


def _tipo_agendavel_direto(appointment_type: str) -> tuple["frappe._dict", str]:
	"""Mesma validação de ``_item_agendavel``, mas para agendamento SEM
	Website Item (F9 — landing "Protocolo de Emagrecimento": "Fora do
	catálogo de produtos, sem Website Item de medicamento"). Usada quando o
	agendamento vem de ``Imunocare Ecommerce Settings.<...>_appointment_type``
	em vez do campo ``imun_appointment_type`` de um Website Item."""
	if not frappe.db.exists("Appointment Type", appointment_type):
		frappe.throw(_("O Tipo de Agendamento configurado ({0}) não existe mais.").format(appointment_type))
	allow_booking_for = frappe.db.get_value("Appointment Type", appointment_type, "allow_booking_for")
	if allow_booking_for and allow_booking_for != "Practitioner":
		frappe.throw(_("Este serviço não é agendado por profissional; contate a clínica para agendar."))
	# _dict "vazio" no formato esperado por _resolver_practitioner — sem
	# profissional padrão fixo (a landing pode ter 1 ou nenhum configurado).
	return frappe._dict({"imun_practitioner": None}), appointment_type


def _resolver_agendavel(item_code: str | None, appointment_type: str | None) -> tuple["frappe._dict", str]:
	"""Ponto único de resolução (item da loja OU tipo direto — F9). Reusado
	por ``get_horarios``/``info_agendamento``/``criar_agendamento`` para não
	duplicar a lógica de validação em cada endpoint."""
	if appointment_type:
		return _tipo_agendavel_direto(appointment_type)
	if item_code:
		return _item_agendavel(item_code)
	frappe.throw(_("Informe o item ou o tipo de agendamento."))


def _resolver_practitioner(wi: "frappe._dict", informado: str | None = None) -> str:
	if wi.imun_practitioner:
		if informado and informado != wi.imun_practitioner:
			frappe.throw(_("Profissional inválido para este serviço."))
		return wi.imun_practitioner

	if informado:
		if not frappe.db.exists("Healthcare Practitioner", {"name": informado, "status": "Active"}):
			frappe.throw(_("Profissional indisponível."))
		return informado

	ativos = frappe.get_all("Healthcare Practitioner", filters={"status": "Active"}, pluck="name")
	if len(ativos) == 1:
		return ativos[0]
	frappe.throw(
		_("Não foi possível determinar automaticamente o profissional deste serviço. Fale com a clínica.")
	)


# ---------------------------------------------------------------------------
# Disponibilidade de horários (thin wrapper sobre o nativo)
# ---------------------------------------------------------------------------


def _slots_livres(slot_details: list[dict], data, duracao: int) -> list[dict]:
	"""Discretiza os ``avail_slot`` (janelas) em horários de ``duracao`` minutos,
	removendo os que colidem com agendamentos existentes ou já passaram (se a
	data for hoje). Versão simplificada de ``patient_appointment.js:get_slots``
	(sem capacidade de grupo / opção de videoconferência — fora do escopo da
	loja online nesta 1ª versão).
	"""
	livres: list[dict] = []
	agora = now_datetime()
	e_hoje = agora.date() == data
	minutos_agora = agora.hour * 60 + agora.minute

	for info in slot_details:
		ocupados = []
		for ap in info.get("appointments") or []:
			t = get_time(ap.get("appointment_time"))
			inicio = t.hour * 60 + t.minute
			fim = inicio + int(ap.get("duration") or duracao or 0)
			ocupados.append((inicio, fim))

		for slot in info.get("avail_slot") or []:
			t_ini = get_time(slot.get("from_time"))
			t_fim = get_time(slot.get("to_time"))
			ini = t_ini.hour * 60 + t_ini.minute
			fim = t_fim.hour * 60 + t_fim.minute
			cursor = ini
			while cursor + duracao <= fim:
				fim_slot = cursor + duracao
				colide = any(cursor < fo and fim_slot > fi for (fi, fo) in ocupados)
				passado = e_hoje and cursor <= minutos_agora
				if not colide and not passado:
					livres.append(
						{
							"hora": f"{cursor // 60:02d}:{cursor % 60:02d}:00",
							"service_unit": info.get("service_unit"),
						}
					)
				cursor += duracao
	return livres


@frappe.whitelist(allow_guest=True)
def get_horarios(
	data: str,
	item_code: str | None = None,
	practitioner: str | None = None,
	appointment_type: str | None = None,
) -> dict:
	"""Horários livres de um item agendável (ou de um ``appointment_type``
	direto — F9) em uma data. Nunca lança 500 — falhas de configuração viram
	``{"horarios": [], "aviso": "..."}``."""
	wi, appointment_type = _resolver_agendavel(item_code, appointment_type)
	prof = _resolver_practitioner(wi, practitioner)
	duracao = frappe.db.get_value("Appointment Type", appointment_type, "default_duration") or 30

	try:
		from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
			get_availability_data,
		)

		resultado = get_availability_data(
			data, prof, json.dumps({"doctype": "Patient Appointment"})
		)
	except frappe.exceptions.ValidationError as e:
		return {"practitioner": prof, "duracao": duracao, "horarios": [], "aviso": str(e)}
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {
			"practitioner": prof,
			"duracao": duracao,
			"horarios": [],
			"aviso": _("Não foi possível consultar horários agora. Tente novamente mais tarde."),
		}

	livres = _slots_livres(resultado.get("slot_details") or [], getdate(data), int(duracao))
	return {"practitioner": prof, "duracao": duracao, "horarios": livres}


@frappe.whitelist(allow_guest=True)
def info_agendamento(item_code: str) -> dict:
	"""Info leve para o storefront decidir se mostra o botão "Agendar"."""
	wi = _website_item(item_code)
	if not wi or not wi.published or not wi.imun_appointment_type:
		return {"agendavel": False}
	try:
		_wi, appointment_type = _item_agendavel(item_code)
		practitioner = _resolver_practitioner(wi)
	except frappe.exceptions.ValidationError:
		return {"agendavel": False}

	resultado = {
		"agendavel": True,
		"appointment_type": appointment_type,
		"practitioner": practitioner,
		"logged_in": frappe.session.user != "Guest",
	}
	resultado.update(_boot_datas())
	return resultado


@frappe.whitelist(allow_guest=True)
def info_agendamento_tipo(appointment_type: str) -> dict:
	"""Equivalente a ``info_agendamento``, mas para agendamento SEM Website
	Item (F9 — landing "Protocolo de Emagrecimento"). O chamador passa o
	``appointment_type`` diretamente (ex.: vindo de
	``Imunocare Ecommerce Settings``)."""
	if not appointment_type or not frappe.db.exists("Appointment Type", appointment_type):
		return {"agendavel": False}
	try:
		wi, appointment_type = _tipo_agendavel_direto(appointment_type)
		practitioner = _resolver_practitioner(wi)
	except frappe.exceptions.ValidationError:
		return {"agendavel": False}

	resultado = {
		"agendavel": True,
		"appointment_type": appointment_type,
		"practitioner": practitioner,
		"logged_in": frappe.session.user != "Guest",
	}
	resultado.update(_boot_datas())
	return resultado


# ---------------------------------------------------------------------------
# Paciente — "PF sob demanda" (mesmo padrão do imunocare_clinic_ext)
# ---------------------------------------------------------------------------


def _resolver_paciente(patient: str | None, patient_data: dict | str | None) -> str:
	user = frappe.session.user

	if patient:
		pac = frappe.db.get_value("Patient", patient, ["name", "user_id"], as_dict=True)
		if not pac:
			frappe.throw(_("Paciente informado não encontrado."))
		if pac.user_id and pac.user_id != user:
			frappe.throw(_("Este paciente não pertence à sua conta."))
		if not pac.user_id:
			frappe.db.set_value("Patient", pac.name, "user_id", user, update_modified=False)
		return pac.name

	existente = frappe.db.get_value("Patient", {"user_id": user}, "name") or frappe.db.get_value(
		"Patient", {"email": user}, "name"
	)
	if existente:
		if not frappe.db.get_value("Patient", existente, "user_id"):
			frappe.db.set_value("Patient", existente, "user_id", user, update_modified=False)
		return existente

	if isinstance(patient_data, str):
		patient_data = json.loads(patient_data) if patient_data else {}
	dados = frappe._dict(patient_data or {})

	usr = frappe.get_doc("User", user)
	partes_nome = (dados.get("nome_completo") or usr.full_name or "").split()

	p = frappe.new_doc("Patient")
	p.first_name = dados.get("first_name") or (partes_nome[0] if partes_nome else usr.first_name)
	p.last_name = dados.get("last_name") or (partes_nome[-1] if len(partes_nome) > 1 else usr.last_name or "")
	if len(partes_nome) > 2:
		p.middle_name = dados.get("middle_name") or " ".join(partes_nome[1:-1])
	elif dados.get("middle_name"):
		p.middle_name = dados.get("middle_name")
	p.email = dados.get("email") or usr.email or user
	p.mobile = dados.get("mobile") or usr.get("mobile_no")
	sexo = dados.get("sex") or usr.get("gender")
	if sexo:
		p.sex = sexo
	if dados.get("dob"):
		p.dob = getdate(dados.get("dob"))
	# Campos customizados do imunocare_clinic_ext (cpf/país/cidade de nascimento):
	# só setamos se o DocType os tiver (não assumimos a lista de reqd, que pode mudar).
	meta = frappe.get_meta("Patient")
	for campo in ("cpf", "pais_nascimento", "cidade_nascimento"):
		if dados.get(campo) and meta.has_field(campo):
			p.set(campo, dados.get(campo))
	p.user_id = user
	p.invite_user = 0

	try:
		p.insert(ignore_permissions=True)
	except frappe.MandatoryError as e:
		frappe.throw(
			_(
				"Para concluir seu primeiro agendamento online precisamos completar seu "
				"cadastro de paciente. Dados faltando: {0}"
			).format(str(e)),
			title=_("Cadastro incompleto"),
		)
	return p.name


# ---------------------------------------------------------------------------
# Faturamento opcional (reuso do Healthcare + do Payment Request/maxiPago já
# wireado em imunocare_ecommerce.pagamento.setup) — nunca bloqueia o
# agendamento se a cobrança não estiver configurada.
# ---------------------------------------------------------------------------


def _tentar_faturar_e_cobrar(appointment_doc) -> dict | None:
	from imunocare_ecommerce.pagamento.setup import resolver_conta_gateway_maxipago

	if not resolver_conta_gateway_maxipago():
		# Sem gateway configurado ainda (pendência do CTO/A3) — o agendamento fica
		# confirmado e sem cobrança online; a recepção cobra pelo fluxo normal
		# (imunocare_clinic_ext.recebimento_agendamento) quando o cliente chegar.
		return None

	try:
		from healthcare.healthcare.doctype.patient_appointment.patient_appointment import (
			create_sales_invoice,
		)

		create_sales_invoice(appointment_doc)
	except Exception:
		# Sem item de cobrança/tarifa configurada no profissional ou no
		# Appointment Type — degrada sem quebrar o agendamento.
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return None

	appointment_doc.reload()
	si_name = appointment_doc.get("ref_sales_invoice")
	if not si_name:
		return None

	try:
		from erpnext.accounts.doctype.payment_request.payment_request import make_payment_request

		pr = make_payment_request(
			dt="Sales Invoice",
			dn=si_name,
			order_type="Shopping Cart",  # reusa o gateway do Webshop Settings (mesmo caminho do A3)
			submit_doc=1,
			mute_email=1,
			return_doc=1,
		)
		return {
			"faturado": True,
			"sales_invoice": si_name,
			"payment_request": pr.name,
			"payment_url": pr.get_payment_url(),
		}
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {"faturado": True, "sales_invoice": si_name, "payment_url": None}


def _empresa_padrao() -> str:
	company = frappe.defaults.get_global_default("company")
	if not company:
		companies = frappe.get_all("Company", pluck="name", limit=2)
		if len(companies) == 1:
			company = companies[0]
	if not company:
		frappe.throw(
			_("Configure a empresa padrão (Global Defaults) para permitir agendamento pela loja.")
		)
	return company


# ---------------------------------------------------------------------------
# Entry-point principal
# ---------------------------------------------------------------------------


@frappe.whitelist()
def criar_agendamento(
	appointment_date: str,
	appointment_time: str,
	item_code: str | None = None,
	practitioner: str | None = None,
	patient: str | None = None,
	patient_data: dict | str | None = None,
	session_id: str | None = None,
	modalidade: str | None = None,
	appointment_type: str | None = None,
) -> dict:
	"""Cria o Patient Appointment a partir da loja. Requer login (portal user) —
	mesmo requisito do Web Form nativo ``patient-appointments`` do Healthcare.

	Aceita ``item_code`` (fluxo normal — Website Item com
	``imun_appointment_type``) OU ``appointment_type`` direto (F9 — landing
	"Protocolo de Emagrecimento", sem Website Item de medicamento)."""
	if frappe.session.user == "Guest":
		frappe.throw(
			_("Faça login para agendar sua consulta."), frappe.PermissionError, title=_("Login necessário")
		)

	wi, appointment_type = _resolver_agendavel(item_code, appointment_type)
	prof = _resolver_practitioner(wi, practitioner)
	patient_name = _resolver_paciente(patient, patient_data)
	company = _empresa_padrao()

	pa = frappe.new_doc("Patient Appointment")
	pa.patient = patient_name
	pa.appointment_type = appointment_type
	pa.practitioner = prof
	pa.appointment_date = appointment_date
	pa.appointment_time = appointment_time
	pa.company = company
	pa.imun_origem_loja = 1

	# F1 (inventário 2026-08-02): get_meta("Patient Appointment") chamado 1x só
	# (antes era chamado 2x na mesma função) e reaproveitado nas duas checagens.
	meta_pa = frappe.get_meta("Patient Appointment")
	if session_id and meta_pa.has_field("imun_session_id"):
		pa.imun_session_id = session_id

	modalidade_domiciliar = (modalidade or "").strip().lower() in ("domiciliar", "domicilio", "domicílio")
	if meta_pa.has_field("imun_modalidade"):
		# O Select imun_modalidade (imunocare_clinic_ext) só aceita
		# "Clínica"/"Domiciliar" (MODALIDADE_OPTIONS). Gravar "Na Clínica" aqui
		# fazia todo agendamento NÃO-domiciliar quebrar em pa.insert() com
		# ValidationError (Feature 72, achado do dev-clinic 2026-08-11).
		pa.imun_modalidade = "Domiciliar" if modalidade_domiciliar else "Clínica"
	pa.insert(ignore_permissions=True)

	resultado = {
		"appointment": pa.name,
		"status": pa.status,
		"faturado": False,
		"payment_url": None,
		"modalidade": "Domiciliar" if modalidade_domiciliar else "Clínica",
	}
	if modalidade_domiciliar:
		resultado["aviso_domiciliar"] = _(
			"Atendimento domiciliar selecionado. A taxa de atendimento domiciliar será "
			"confirmada pela recepção antes da visita."
		)

	cobranca = _tentar_faturar_e_cobrar(pa)
	if cobranca:
		resultado.update(cobranca)

	_registrar_conversao_funil(pa, session_id)

	return resultado


def _registrar_conversao_funil(pa, session_id: str | None) -> None:
	"""Alimenta o funil do CRM (Feature 56 / A2.4) — nunca bloqueia o agendamento.

	Identidade (e-mail/telefone) vem do próprio Patient (já garantida pelo login
	necessário para agendar); o ``session_id`` só enriquece com origem/UTM
	quando o cliente deu consentimento de rastreio (Feature 56 / A2.2).
	"""
	try:
		from imunocare_ecommerce.rastreio.funil import registrar_conversao

		email = frappe.db.get_value("Patient", pa.patient, "email")
		mobile = frappe.db.get_value("Patient", pa.patient, "mobile")
		nome = frappe.db.get_value("Patient", pa.patient, "patient_name")
		registrar_conversao(
			tipo_evento="agendamento_confirmado",
			email=email,
			phone=mobile,
			nome=nome,
			session_id=session_id,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
