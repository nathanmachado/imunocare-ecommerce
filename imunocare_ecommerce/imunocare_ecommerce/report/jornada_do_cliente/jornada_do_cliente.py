# -*- coding: utf-8 -*-
"""Relatório de Comportamento do Cliente — Jornada do Cliente (Feature 56 / A2.3).

Responde ao brief (origem, navegação, virou lead?, orçou/fechou?, ligou?,
canal, novo x recorrente, carrinho abandonado, tempo até converter) cruzando:

  - ``Imunocare Web Session``/``Imunocare Web Event`` (jornada anônima, só
    existe com consentimento — Feature 56 / A2.2).
  - ``CRM Lead`` nativo (virou lead?, status do funil) — vinculado via
    ``Imunocare Web Session.lead`` (carimbado por
    ``imunocare_ecommerce.rastreio.funil``).
  - ``CRM Call Log``/``Communication`` (medium=WhatsApp) do
    ``imunocare_crm_custom`` — "ligou?"/"mandou WhatsApp?" e quantas vezes
    (reuso total: não reimplementamos nada de telefonia/WhatsApp aqui).
  - ``Quotation`` (``order_type="Shopping Cart"``) — "orçou?"/"fechou?" via
    ``imun_session_id`` (carimbado no 1º add-to-cart/checkout) — não depende
    de correspondência por e-mail, é o vínculo direto sessão<->carrinho.
  - ``Patient Appointment`` do ``patient`` do Lead — recorrência (quantos
    agendamentos históricos essa pessoa já teve).

Sessões SEM Lead vinculado (visitante não identificado) aparecem com as
colunas de CRM/vendas vazias — é o comportamento esperado (não há como saber
"ligou?"/"orçou?" de alguém que nunca se identificou), não um bug.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import date_diff


def execute(filters: dict | None = None):
	filters = frappe._dict(filters or {})
	columns = _colunas()
	sessions = _buscar_sessoes(filters)
	if not sessions:
		return columns, []

	lead_names = [s.lead for s in sessions if s.lead]
	leads = _leads_por_nome(lead_names)
	call_counts = _contagem_call_log(lead_names)
	whatsapp_counts = _contagem_whatsapp(lead_names)
	quotations_by_session = _quotations_por_sessao([s.name for s in sessions])
	recorrencia_by_patient = _recorrencia_por_patient(
		[leads[l].patient for l in lead_names if leads.get(l) and leads[l].patient]
	)

	data = []
	for s in sessions:
		lead = leads.get(s.lead) if s.lead else None
		qtns = quotations_by_session.get(s.name, [])
		orcou = len(qtns) > 0
		fechou = any(q.status == "Ordered" for q in qtns)
		valor_orcado = sum(q.grand_total or 0 for q in qtns)

		tempo_ate_converter = None
		if s.converteu_lead and lead and lead.creation:
			tempo_ate_converter = date_diff(lead.creation, s.primeiro_acesso)

		data.append(
			{
				"session_id": s.name,
				"primeiro_acesso": s.primeiro_acesso,
				"origem": s.origem,
				"utm_campaign": s.utm_campaign,
				"landing_page": s.landing_page,
				"paginas_vistas": s.paginas_vistas,
				"duracao_min": round((s.duracao_segundos or 0) / 60, 1),
				"novo_ou_recorrente": _("Recorrente") if not s.novo_visitante else _("Novo"),
				"virou_lead": _("Sim") if s.converteu_lead else _("Não"),
				"lead": s.lead,
				"status_lead": lead.status if lead else None,
				"orcou": _("Sim") if orcou else _("Não"),
				"fechou": _("Sim") if fechou else _("Não"),
				"valor_orcado": valor_orcado,
				"ligou": call_counts.get(s.lead, 0),
				"whatsapp": whatsapp_counts.get(s.lead, 0),
				"retornos_historicos": recorrencia_by_patient.get(lead.patient, 0)
				if lead and lead.patient
				else None,
				"carrinho_abandonado": _("Sim") if s.carrinho_abandonado else _("Não"),
				"tempo_ate_converter_dias": tempo_ate_converter,
			}
		)

	return columns, data


def _colunas() -> list[dict]:
	return [
		{"label": _("Sessão"), "fieldname": "session_id", "fieldtype": "Link", "options": "Imunocare Web Session", "width": 160},
		{"label": _("Primeiro Acesso"), "fieldname": "primeiro_acesso", "fieldtype": "Datetime", "width": 150},
		{"label": _("Origem"), "fieldname": "origem", "fieldtype": "Data", "width": 110},
		{"label": _("Campanha (utm_campaign)"), "fieldname": "utm_campaign", "fieldtype": "Data", "width": 150},
		{"label": _("Página de Entrada"), "fieldname": "landing_page", "fieldtype": "Data", "width": 160},
		{"label": _("Páginas Vistas"), "fieldname": "paginas_vistas", "fieldtype": "Int", "width": 100},
		{"label": _("Tempo no Site (min)"), "fieldname": "duracao_min", "fieldtype": "Float", "width": 130},
		{"label": _("Novo x Recorrente"), "fieldname": "novo_ou_recorrente", "fieldtype": "Data", "width": 120},
		{"label": _("Virou Lead?"), "fieldname": "virou_lead", "fieldtype": "Data", "width": 90},
		{"label": _("Lead"), "fieldname": "lead", "fieldtype": "Link", "options": "CRM Lead", "width": 150},
		{"label": _("Status do Lead"), "fieldname": "status_lead", "fieldtype": "Data", "width": 110},
		{"label": _("Orçou?"), "fieldname": "orcou", "fieldtype": "Data", "width": 80},
		{"label": _("Fechou?"), "fieldname": "fechou", "fieldtype": "Data", "width": 80},
		{"label": _("Valor Orçado"), "fieldname": "valor_orcado", "fieldtype": "Currency", "width": 110},
		{"label": _("Ligou (qtd)"), "fieldname": "ligou", "fieldtype": "Int", "width": 90},
		{"label": _("WhatsApp (qtd)"), "fieldname": "whatsapp", "fieldtype": "Int", "width": 100},
		{"label": _("Retornos Históricos"), "fieldname": "retornos_historicos", "fieldtype": "Int", "width": 130},
		{"label": _("Carrinho Abandonado?"), "fieldname": "carrinho_abandonado", "fieldtype": "Data", "width": 130},
		{"label": _("Dias até Converter"), "fieldname": "tempo_ate_converter_dias", "fieldtype": "Int", "width": 120},
	]


def _buscar_sessoes(filters: dict) -> list["frappe._dict"]:
	condicoes = {}
	if filters.get("from_date"):
		condicoes["primeiro_acesso"] = [">=", filters.get("from_date")]
	if filters.get("to_date"):
		condicoes["primeiro_acesso"] = [
			"between",
			[filters.get("from_date") or "1900-01-01", filters.get("to_date")],
		]
	if filters.get("origem"):
		condicoes["origem"] = filters.get("origem")
	if filters.get("somente_convertidos"):
		condicoes["converteu_lead"] = 1
	if filters.get("somente_carrinho_abandonado"):
		condicoes["carrinho_abandonado"] = 1

	return frappe.get_all(
		"Imunocare Web Session",
		filters=condicoes,
		fields=[
			"name",
			"primeiro_acesso",
			"origem",
			"utm_campaign",
			"landing_page",
			"paginas_vistas",
			"duracao_segundos",
			"novo_visitante",
			"converteu_lead",
			"lead",
			"carrinho_abandonado",
		],
		order_by="primeiro_acesso desc",
		limit_page_length=0,
	)


def _leads_por_nome(lead_names: list[str]) -> dict:
	if not lead_names:
		return {}
	rows = frappe.get_all(
		"CRM Lead",
		filters={"name": ["in", list(set(lead_names))]},
		fields=["name", "status", "patient", "creation"],
	)
	return {r.name: r for r in rows}


def _contagem_call_log(lead_names: list[str]) -> dict:
	if not lead_names or not frappe.db.exists("DocType", "CRM Call Log"):
		return {}
	rows = frappe.db.get_all(
		"CRM Call Log",
		filters={"reference_doctype": "CRM Lead", "reference_docname": ["in", list(set(lead_names))]},
		fields=["reference_docname as lead", "count(name) as qtd"],
		group_by="reference_docname",
	)
	return {r.lead: r.qtd for r in rows}


def _contagem_whatsapp(lead_names: list[str]) -> dict:
	if not lead_names or not frappe.db.exists("DocType", "Communication"):
		return {}
	rows = frappe.db.get_all(
		"Communication",
		filters={
			"reference_doctype": "CRM Lead",
			"reference_name": ["in", list(set(lead_names))],
			"communication_medium": "WhatsApp",
		},
		fields=["reference_name as lead", "count(name) as qtd"],
		group_by="reference_name",
	)
	return {r.lead: r.qtd for r in rows}


def _quotations_por_sessao(session_ids: list[str]) -> dict:
	if not session_ids or not frappe.db.exists(
		"Custom Field", {"dt": "Quotation", "fieldname": "imun_session_id"}
	):
		return {}
	rows = frappe.get_all(
		"Quotation",
		filters={"imun_session_id": ["in", list(set(session_ids))]},
		fields=["name", "imun_session_id", "status", "grand_total"],
	)
	agrupado: dict = {}
	for r in rows:
		agrupado.setdefault(r.imun_session_id, []).append(r)
	return agrupado


def _recorrencia_por_patient(patients: list[str]) -> dict:
	if not patients or not frappe.db.exists("DocType", "Patient Appointment"):
		return {}
	rows = frappe.db.get_all(
		"Patient Appointment",
		filters={"patient": ["in", list(set(patients))]},
		fields=["patient", "count(name) as qtd"],
		group_by="patient",
	)
	return {r.patient: r.qtd for r in rows}
