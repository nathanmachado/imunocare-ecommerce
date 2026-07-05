"""Integração da jornada rastreada com o funil do CRM (Feature 56 / A2.4).

Reuso primeiro — o que este módulo NÃO reimplementa:

  - Funil/pipeline: 100% ``CRM Lead`` nativo. Não criamos um segundo "funil".
  - Critério de "Lead aberto" para dedup (``converted=0``) e normalização de
    telefone: mesmo padrão de
    ``imunocare_crm_custom.channels.base.get_or_create_lead``/``_find_open_lead``
    (reaproveitado quando o app está instalado; com *fallback* local só para
    não acoplar rigidamente a outro app — ver ``_normalizar_telefone``). Isso
    garante que, se o cliente depois ligar/mandar WhatsApp, o dedup nativo do
    ``imunocare_crm_custom`` encontre o MESMO Lead (mesmo ``mobile_no``
    normalizado) em vez de duplicar.

Identidade x consentimento (ver relatório ao CTO): a identidade (e-mail/
telefone) usada aqui SEMPRE vem de um ato transacional do próprio cliente
(login para agendar/comprar, ou formulário que ele preencheu) — não depende
de consentimento de rastreio para existir. O consentimento de rastreio
(``Imunocare Web Session``) só governa se a JORNADA (UTM, páginas vistas,
tempo no site) fica disponível para enriquecer esse Lead; sem consentimento,
o Lead ainda é criado/atualizado normalmente (base legal: execução de
contrato/relacionamento comercial), só que sem o carimbo de origem/jornada.
"""

from __future__ import annotations

import frappe

_LOG_TITLE = "imunocare_ecommerce.rastreio.funil"


# ---------------------------------------------------------------------------
# Normalização de telefone (reusa imunocare_crm_custom quando disponível)
# ---------------------------------------------------------------------------


def _normalizar_telefone(phone: str | None) -> str | None:
	if not phone:
		return None
	try:
		from imunocare_crm_custom.utils.phone import normalize_phone

		return normalize_phone(phone)
	except Exception:
		# imunocare_crm_custom não instalado neste site, ou telefone não normalizável.
		digitos = "".join(c for c in phone if c.isdigit() or c == "+")
		return digitos or None


def _find_open_lead(email: str | None, phone_e164: str | None) -> str | None:
	"""Mesmo critério de 'lead aberto' do imunocare_crm_custom (converted=0)."""
	if phone_e164:
		found = frappe.get_all(
			"CRM Lead",
			filters={"converted": 0, "mobile_no": phone_e164},
			pluck="name",
			order_by="creation desc",
			limit=1,
		)
		if found:
			return found[0]
	if email:
		found = frappe.get_all(
			"CRM Lead",
			filters={"converted": 0, "email": email},
			pluck="name",
			order_by="creation desc",
			limit=1,
		)
		if found:
			return found[0]
	return None


# ---------------------------------------------------------------------------
# Carimbo de origem/UTM (a partir da Imunocare Web Session, se houver)
# ---------------------------------------------------------------------------

_UTM_FIELD_MAP = {
	"utm_source": "imun_utm_source",
	"utm_medium": "imun_utm_medium",
	"utm_campaign": "imun_utm_campaign",
	"utm_term": "imun_utm_term",
	"utm_content": "imun_utm_content",
	"gclid": "imun_gclid",
	"fbclid": "imun_fbclid",
}


def _carimbar_origem(lead, session: "frappe._dict | None") -> None:
	"""Preenche source/UTM só se ainda vazios (preserva o primeiro-toque)."""
	if not session:
		return
	if not lead.get("source") and session.get("origem"):
		lead.source = session.origem
	for session_field, lead_field in _UTM_FIELD_MAP.items():
		if not lead.get(lead_field) and session.get(session_field):
			lead.set(lead_field, session.get(session_field))
	if not lead.get("imun_sessao_web"):
		lead.imun_sessao_web = session.name


def _sessao(session_id: str | None) -> "frappe._dict | None":
	if not session_id or not frappe.db.exists("Imunocare Web Session", session_id):
		return None
	return frappe.get_doc("Imunocare Web Session", session_id)


# ---------------------------------------------------------------------------
# Entry-point principal — chamado pelos pontos de conversão da loja
# ---------------------------------------------------------------------------


def registrar_conversao(
	tipo_evento: str,
	email: str | None = None,
	phone: str | None = None,
	nome: str | None = None,
	session_id: str | None = None,
) -> str | None:
	"""Cria/atualiza o CRM Lead correspondente a uma conversão da loja.

	``tipo_evento`` é só para log/rastreabilidade (ex.: "agendamento_confirmado",
	"pedido_confirmado", "carrinho_abandonado", "lead_form_submit"). Retorna o
	nome do CRM Lead, ou ``None`` se não houver identidade suficiente (nem
	e-mail nem telefone) ou se o app ``crm`` não estiver instalado.

	Idempotente: reaproveita o Lead aberto (``converted=0``) já existente com
	o mesmo e-mail/telefone em vez de duplicar (mesmo critério do
	``imunocare_crm_custom``).
	"""
	if not email and not phone:
		return None
	if not frappe.db.exists("DocType", "CRM Lead"):
		return None

	try:
		phone_e164 = _normalizar_telefone(phone)
		email = email.strip() if email else None
		session = _sessao(session_id)
		now = frappe.utils.now_datetime()

		lead_name = _find_open_lead(email, phone_e164)
		if lead_name:
			lead = frappe.get_doc("CRM Lead", lead_name)
			dirty = False
			if not lead.email and email:
				lead.email = email
				dirty = True
			if not lead.mobile_no and phone_e164:
				lead.mobile_no = phone_e164
				lead.phone = phone_e164
				dirty = True
			before = lead.as_dict()
			_carimbar_origem(lead, session)
			if lead.as_dict() != before:
				dirty = True
			if tipo_evento == "carrinho_abandonado" and not lead.get("imun_carrinho_abandonado"):
				lead.imun_carrinho_abandonado = 1
				dirty = True
			if dirty:
				lead.save(ignore_permissions=True)
		else:
			lead = frappe.new_doc("CRM Lead")
			if email:
				lead.email = email
			if phone_e164:
				lead.mobile_no = phone_e164
				lead.phone = phone_e164
			if nome:
				lead.lead_name = nome
				partes = nome.split()
				lead.first_name = partes[0]
				if len(partes) > 1:
					lead.last_name = partes[-1]
			else:
				# first_name é obrigatório no CRM Lead nativo; sem nome informado,
				# usa um fallback derivado do e-mail/telefone (nunca bloqueia a conversão).
				lead.first_name = (email.split("@")[0] if email else phone_e164) or "Cliente"
			_carimbar_origem(lead, session)
			if not lead.get("source"):
				lead.source = "Direto"
			if tipo_evento == "carrinho_abandonado":
				lead.imun_carrinho_abandonado = 1
			lead.insert(ignore_permissions=True)
			lead_name = lead.name

		if session:
			frappe.db.set_value(
				"Imunocare Web Session",
				session.name,
				{
					"converteu_lead": 1,
					"lead": lead_name,
					"contact_email": email,
				},
				update_modified=False,
			)
			if tipo_evento == "carrinho_abandonado":
				frappe.db.set_value(
					"Imunocare Web Session", session.name, "carrinho_abandonado", 1, update_modified=False
				)

		frappe.logger(_LOG_TITLE).info(
			f"registrar_conversao: {tipo_evento} -> CRM Lead {lead_name} (session={session_id})."
		)
		return lead_name
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return None


# ---------------------------------------------------------------------------
# doc_event — Sales Order (checkout da loja concluído)
# ---------------------------------------------------------------------------


def on_sales_order_submit(doc, method=None) -> None:
	"""Registrado em hooks.doc_events. Só age em pedidos vindos do carrinho
	da loja (``order_type == "Shopping Cart"``) — é um no-op silencioso para
	todos os demais Sales Orders da clínica (walk-in, B2B, etc.).
	"""
	try:
		if doc.get("order_type") != "Shopping Cart":
			return

		session_id = None
		for item in doc.get("items") or []:
			quotation = item.get("prevdoc_docname")
			if quotation:
				session_id = frappe.db.get_value("Quotation", quotation, "imun_session_id")
				if session_id:
					break

		email = doc.get("contact_email")
		phone = doc.get("contact_mobile") or doc.get("contact_phone")
		nome = doc.get("contact_display") or doc.get("customer_name")

		registrar_conversao(
			tipo_evento="pedido_confirmado",
			email=email,
			phone=phone,
			nome=nome,
			session_id=session_id,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
