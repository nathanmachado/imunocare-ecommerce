"""Custom fields + dados de apoio do rastreio da jornada (Feature 56 / A2).

Reuso primeiro — o que este módulo NÃO reimplementa:

  - Funil/pipeline de Lead: 100% ``CRM Lead`` nativo (app ``crm``) + os campos
    já adicionados pelo ``imunocare_crm_custom`` (``source_channel``,
    ``patient``, etc.) — não duplicamos nada disso.
  - Classificação grosseira de canal de origem: em vez de inventar mais um
    Select próprio, mapeamos a origem da sessão (Google Ads/Meta Ads/Busca
    Orgânica/Referência/Direto) para o campo NATIVO ``CRM Lead.source``
    (Link ``CRM Lead Source``) — ``_ensure_crm_lead_sources`` só garante que
    esses registros existam.
  - Carrinho = ``Quotation`` (``order_type="Shopping Cart"``) do próprio
    webshop — não duplicamos o carrinho. Só adicionamos 1 Custom Field
    (``imun_session_id``) para amarrar a sessão anônima ao carrinho/pedido já
    existente (necessário para "orçou?"/"fechou?"/"abandonou carrinho?" no
    relatório A2.3 e para o A2.4 alimentar o Lead).

O que este módulo constrói (o gap):
  - Custom Fields em ``CRM Lead``: granularidade de UTM/click-id que o CRM
    nativo não tem, + link de volta para a sessão anônima (jornada completa).
  - Custom Field em ``Quotation``: ``imun_session_id`` (amarração carrinho <->
    sessão, ver ``rastreio.api.vincular_carrinho_atual``).
  - Custom Field em ``Patient Appointment``: ``imun_session_id`` (mesma
    amarração para agendamentos vindos da loja — complementa
    ``imun_origem_loja`` já criado por ``agendamento.setup``).

Idempotente: seguro para rodar em todo ``bench migrate``. Se ``CRM Lead``
ainda não existir (app ``crm`` não instalado), degrada com aviso.
"""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

_LOG_TITLE = "imunocare_ecommerce.rastreio.setup"

# Nome dos CRM Lead Source usados como classificação grosseira de canal.
# Mesmos rótulos usados em Imunocare Web Session.origem (ver rastreio/api.py
# _classificar_origem) para que o carimbo em CRM Lead.source seja 1:1.
CRM_LEAD_SOURCES = [
	"Google Ads",
	"Meta Ads",
	"Busca Orgânica",
	"Referência",
	"Direto",
	"Outra Campanha",
]

CRM_LEAD_CUSTOM_FIELDS = {
	"CRM Lead": [
		{
			"fieldname": "imun_rastreio_section",
			"fieldtype": "Section Break",
			"label": "Rastreio da Jornada (Ecommerce)",
			"insert_after": "source",
			"collapsible": 1,
		},
		{
			"fieldname": "imun_utm_source",
			"fieldtype": "Data",
			"label": "utm_source",
			"insert_after": "imun_rastreio_section",
		},
		{
			"fieldname": "imun_utm_medium",
			"fieldtype": "Data",
			"label": "utm_medium",
			"insert_after": "imun_utm_source",
		},
		{
			"fieldname": "imun_utm_campaign",
			"fieldtype": "Data",
			"label": "utm_campaign",
			"insert_after": "imun_utm_medium",
		},
		{
			"fieldname": "imun_column_break_utm",
			"fieldtype": "Column Break",
			"insert_after": "imun_utm_campaign",
		},
		{
			"fieldname": "imun_utm_term",
			"fieldtype": "Data",
			"label": "utm_term",
			"insert_after": "imun_column_break_utm",
		},
		{
			"fieldname": "imun_utm_content",
			"fieldtype": "Data",
			"label": "utm_content",
			"insert_after": "imun_utm_term",
		},
		{
			"fieldname": "imun_gclid",
			"fieldtype": "Data",
			"label": "gclid",
			"insert_after": "imun_utm_content",
		},
		{
			"fieldname": "imun_fbclid",
			"fieldtype": "Data",
			"label": "fbclid",
			"insert_after": "imun_gclid",
		},
		{
			"fieldname": "imun_sessao_web",
			"fieldtype": "Link",
			"options": "Imunocare Web Session",
			"label": "Sessão Web de Origem",
			"insert_after": "imun_fbclid",
			"read_only": 1,
			"description": "Sessão anônima (jornada completa: páginas vistas, tempo no site, carrinho) que originou este Lead. Só é vinculada com consentimento LGPD.",
		},
		{
			"fieldname": "imun_carrinho_abandonado",
			"fieldtype": "Check",
			"default": "0",
			"label": "Teve Carrinho Abandonado",
			"insert_after": "imun_sessao_web",
			"read_only": 1,
			"description": "Marcado automaticamente quando o scheduler de carrinho abandonado (rastreio.tasks) associa este Lead a um carrinho não finalizado.",
		},
	]
}

QUOTATION_CUSTOM_FIELDS = {
	"Quotation": [
		{
			"fieldname": "imun_session_id",
			"fieldtype": "Data",
			"label": "Sessão Web (Imunocare Ecommerce)",
			"insert_after": "order_type",
			"read_only": 1,
			"no_copy": 1,
			"description": "ID da Imunocare Web Session que originou este carrinho (amarrado no 1º add-to-cart/checkout, quando há consentimento de rastreio).",
		},
		{
			"fieldname": "imun_abandono_notificado",
			"fieldtype": "Check",
			"default": "0",
			"label": "Abandono de Carrinho Já Notificado",
			"insert_after": "imun_session_id",
			"read_only": 1,
			"no_copy": 1,
			"description": "Marcado pelo scheduler (rastreio.tasks.detectar_carrinhos_abandonados) para não reprocessar o mesmo carrinho a cada execução.",
		},
	]
}

PATIENT_APPOINTMENT_CUSTOM_FIELDS = {
	"Patient Appointment": [
		{
			"fieldname": "imun_session_id",
			"fieldtype": "Data",
			"label": "Sessão Web (Imunocare Ecommerce)",
			"insert_after": "imun_origem_loja",
			"read_only": 1,
			"no_copy": 1,
			"description": "ID da Imunocare Web Session que originou este agendamento pela loja (quando há consentimento de rastreio).",
		},
	]
}


def setup_rastreio() -> None:
	"""Entry-point idempotente (after_migrate). Nunca interrompe o migrate."""
	try:
		if frappe.db.exists("DocType", "CRM Lead"):
			create_custom_fields(CRM_LEAD_CUSTOM_FIELDS, ignore_validate=True)
			_ensure_crm_lead_sources()
		else:
			frappe.logger(_LOG_TITLE).warning(
				"CRM Lead (app crm) ainda não instalado — custom fields de rastreio no Lead adiados."
			)

		if frappe.db.exists("DocType", "Quotation"):
			create_custom_fields(QUOTATION_CUSTOM_FIELDS, ignore_validate=True)

		if frappe.db.exists("DocType", "Patient Appointment") and frappe.db.exists(
			"Custom Field", {"dt": "Patient Appointment", "fieldname": "imun_origem_loja"}
		):
			create_custom_fields(PATIENT_APPOINTMENT_CUSTOM_FIELDS, ignore_validate=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
	finally:
		frappe.clear_cache()


def _ensure_crm_lead_sources() -> None:
	if not frappe.db.exists("DocType", "CRM Lead Source"):
		return
	for source in CRM_LEAD_SOURCES:
		if not frappe.db.exists("CRM Lead Source", source):
			frappe.get_doc({"doctype": "CRM Lead Source", "source_name": source}).insert(
				ignore_permissions=True, ignore_if_duplicate=True
			)
