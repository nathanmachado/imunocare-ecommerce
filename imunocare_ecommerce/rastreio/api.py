"""Endpoint de ingestão do rastreio de jornada (Feature 56 / A2.1 + A2.2).

Reuso primeiro — o que este módulo NÃO reimplementa:

  - GA/Meta Pixel: propositalmente NÃO adotados aqui (isso é a Feature B/C,
    exige aceite de cookies de terceiro). Tudo aqui é first-party: o
    ``public/js/rastreio.js`` só fala com ESTE app.
  - Carrinho: é o ``Quotation`` (``order_type="Shopping Cart"``) nativo do
    webshop — ``vincular_carrinho_atual`` só faz a leitura documentada
    (mesmo filtro que ``webshop...cart._get_cart_quotation`` usa
    internamente) e carimba 1 Custom Field, sem duplicar o carrinho.

Guarda LGPD (A2.2): NENHUMA linha é gravada em ``Imunocare Web Session``/
``Imunocare Web Event`` sem que o cliente já tenha optado por "Aceitar" no
banner de consentimento — o próprio ``rastreio.js`` só chama este endpoint
depois do aceite. Isso simplifica a guarda no servidor (não há branch de
"anonimizar parcialmente"): ou a sessão existe com consentimento explícito,
ou não existe nenhum registro. Nenhum IP é armazenado em nenhum caso.

Guarda contra abuso: endpoint ``allow_guest``, mas com rate-limit por IP
(``imunocare_ecommerce.rate_limit``) e validação de tamanho/forma dos
identificadores e do tipo de evento (Select fechado).
"""

from __future__ import annotations

import json
from urllib.parse import urlparse

import frappe
from imunocare_ecommerce.rate_limit import rate_limit
from frappe.utils import now_datetime

_LOG_TITLE = "imunocare_ecommerce.rastreio.api"

# Mesma lista de options de Imunocare Web Event.tipo_evento (mantidas em
# sincronia manualmente — ver o .json do DocType). "heartbeat" é tratado à
# parte (nunca vira linha de Event, só incrementa duracao_segundos).
_TIPOS_EVENTO_VALIDOS = {
	"page_view",
	"add_to_cart",
	"remove_from_cart",
	"call_click",
	"whatsapp_click",
	"lead_form_submit",
	"consentimento_aceito",
	"agendamento_confirmado",
	"pedido_confirmado",
	"carrinho_abandonado",
}
_HEARTBEAT_SEGUNDOS = 30
_ID_MAX_LEN = 64
_TEXTO_MAX_LEN = 500


# ---------------------------------------------------------------------------
# Configuração pública (texto do banner, chave-mestra) — evita hardcode no JS
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def config() -> dict:
	"""Config leve e pública para o ``rastreio.js`` decidir se/como inicializar."""
	if not frappe.db.exists("DocType", "Imunocare Ecommerce Settings"):
		return {"ativo": False}
	settings = frappe.get_single("Imunocare Ecommerce Settings")
	return {
		"ativo": bool(settings.get("rastreio_ativo", 1)),
		"politica_privacidade_url": settings.get("politica_privacidade_url") or "/politica-de-privacidade",
		"texto_banner": settings.get("texto_banner_consentimento") or "",
	}


# ---------------------------------------------------------------------------
# Ingestão de eventos
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=180, seconds=60)
def evento(
	visitor_id: str,
	session_id: str,
	tipo_evento: str,
	rota: str | None = None,
	referrer: str | None = None,
	utm_source: str | None = None,
	utm_medium: str | None = None,
	utm_campaign: str | None = None,
	utm_term: str | None = None,
	utm_content: str | None = None,
	gclid: str | None = None,
	fbclid: str | None = None,
	email: str | None = None,
	phone: str | None = None,
	nome: str | None = None,
	metadados: str | dict | None = None,
) -> dict:
	"""Registra um evento de navegação (chamado só após consentimento aceito).

	Idempotente na criação da sessão (reaproveita se ``session_id`` já existe).
	Nunca lança 500 para o storefront — falhas viram log e ``{"ok": False}``.
	"""
	try:
		visitor_id = _sanitizar_id(visitor_id)
		session_id = _sanitizar_id(session_id)
		if not visitor_id or not session_id:
			return {"ok": False, "erro": "identificadores inválidos"}

		if tipo_evento == "heartbeat":
			_heartbeat(session_id)
			return {"ok": True}

		if tipo_evento not in _TIPOS_EVENTO_VALIDOS:
			return {"ok": False, "erro": "tipo_evento inválido"}

		rota = _truncar(rota)
		referrer = _truncar(referrer)

		session_name = _upsert_sessao(
			visitor_id=visitor_id,
			session_id=session_id,
			rota=rota,
			referrer=referrer,
			utm_source=_truncar(utm_source, 140),
			utm_medium=_truncar(utm_medium, 140),
			utm_campaign=_truncar(utm_campaign, 140),
			utm_term=_truncar(utm_term, 140),
			utm_content=_truncar(utm_content, 140),
			gclid=_truncar(gclid, 140),
			fbclid=_truncar(fbclid, 140),
		)

		_registrar_evento_row(session_name, visitor_id, tipo_evento, rota, metadados)

		# Conversão explícita com identidade (ex.: formulário de contato/newsletter
		# que rode fora do fluxo de checkout/agendamento — esses já se conectam
		# ao funil diretamente via imunocare_ecommerce.rastreio.funil a partir do
		# próprio ponto de conversão, com identidade garantida pelo login).
		if tipo_evento == "lead_form_submit" and (email or phone):
			from imunocare_ecommerce.rastreio.funil import registrar_conversao

			registrar_conversao(
				tipo_evento="lead_form_submit",
				email=_email_valido(email),
				phone=phone,
				nome=nome,
				session_id=session_name,
			)

		return {"ok": True, "session": session_name}
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {"ok": False}


@frappe.whitelist(allow_guest=True)
def vincular_carrinho_atual(session_id: str) -> dict:
	"""Amarra a sessão web ao carrinho (Quotation Shopping Cart) do usuário logado.

	Requer login (mesmo requisito do carrinho nativo do webshop — carrinho é
	por ``contact_email`` = usuário logado). Reaproveita o MESMO filtro que
	``webshop...cart._get_cart_quotation`` usa internamente (contrato estável
	e documentado do modelo de dados do webshop) em vez de importar função
	privada de outro app.

	``allow_guest=True`` (Atividade 537 / Feature 72): o front (``rastreio.js``)
	chama este endpoint logo após o consentimento de cookies, ANTES de saber se
	o visitante está logado — sem ``allow_guest`` o Frappe barra a chamada com
	"Método não permitido" antes mesmo de chegar no early-return abaixo
	(``frappe.session.user == "Guest"``), que já existia e já cobria esse caso
	com segurança (não cria/edita nada para Guest).
	"""
	if frappe.session.user == "Guest":
		return {"linked": False}
	session_id = _sanitizar_id(session_id)
	if not session_id or not frappe.db.exists("Imunocare Web Session", session_id):
		return {"linked": False}

	quotation = frappe.get_all(
		"Quotation",
		filters={
			"contact_email": frappe.session.user,
			"order_type": "Shopping Cart",
			"docstatus": 0,
		},
		order_by="modified desc",
		limit_page_length=1,
		pluck="name",
	)
	if not quotation:
		return {"linked": False}

	if not frappe.db.get_value("Quotation", quotation[0], "imun_session_id"):
		frappe.db.set_value(
			"Quotation", quotation[0], "imun_session_id", session_id, update_modified=False
		)
	return {"linked": True, "quotation": quotation[0]}


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _sanitizar_id(valor: str | None) -> str | None:
	if not valor:
		return None
	valor = str(valor).strip()
	if not valor or len(valor) > _ID_MAX_LEN:
		return None
	# ids são gerados pelo próprio JS (uuid/hex) — restringe a um alfabeto seguro.
	if not all(c.isalnum() or c in "-_" for c in valor):
		return None
	return valor


def _truncar(valor: str | None, tamanho: int = _TEXTO_MAX_LEN) -> str | None:
	if not valor:
		return None
	valor = str(valor).strip()
	return valor[:tamanho] if valor else None


def _email_valido(email: str | None) -> str | None:
	if not email:
		return None
	try:
		frappe.utils.validate_email_address(email, throw=True)
		return email.strip()
	except Exception:
		return None


def _heartbeat(session_id: str) -> None:
	if not frappe.db.exists("Imunocare Web Session", session_id):
		return
	frappe.db.sql(
		"""
		update `tabImunocare Web Session`
		set duracao_segundos = coalesce(duracao_segundos, 0) + %s,
		    ultimo_acesso = %s
		where name = %s
		""",
		(_HEARTBEAT_SEGUNDOS, now_datetime(), session_id),
	)


def _upsert_sessao(
	visitor_id: str,
	session_id: str,
	rota: str | None,
	referrer: str | None,
	utm_source: str | None,
	utm_medium: str | None,
	utm_campaign: str | None,
	utm_term: str | None,
	utm_content: str | None,
	gclid: str | None,
	fbclid: str | None,
) -> str:
	now = now_datetime()

	if frappe.db.exists("Imunocare Web Session", session_id):
		frappe.db.sql(
			"""
			update `tabImunocare Web Session`
			set ultimo_acesso = %s,
			    paginas_vistas = coalesce(paginas_vistas, 0) + 1
			where name = %s
			""",
			(now, session_id),
		)
		return session_id

	novo_visitante = not frappe.db.exists("Imunocare Web Session", {"visitor_id": visitor_id})
	origem = _classificar_origem(utm_source, utm_medium, gclid, fbclid, referrer)

	doc = frappe.get_doc(
		{
			"doctype": "Imunocare Web Session",
			"session_id": session_id,
			"visitor_id": visitor_id,
			"primeiro_acesso": now,
			"ultimo_acesso": now,
			"paginas_vistas": 1,
			"origem": origem,
			"landing_page": rota,
			"referrer": referrer,
			"utm_source": utm_source,
			"utm_medium": utm_medium,
			"utm_campaign": utm_campaign,
			"utm_term": utm_term,
			"utm_content": utm_content,
			"gclid": gclid,
			"fbclid": fbclid,
			"novo_visitante": 1 if novo_visitante else 0,
			"consentimento_status": "Aceito",
			"consentimento_em": now,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _classificar_origem(
	utm_source: str | None,
	utm_medium: str | None,
	gclid: str | None,
	fbclid: str | None,
	referrer: str | None,
) -> str:
	src = (utm_source or "").lower()
	medium = (utm_medium or "").lower()

	if gclid or (src == "google" and medium in ("cpc", "ppc", "paid")):
		return "Google Ads"
	if fbclid or src in ("facebook", "meta", "instagram", "ig"):
		return "Meta Ads"
	if utm_source:
		return "Outra Campanha"
	if referrer:
		try:
			host = urlparse(referrer).netloc.lower()
		except Exception:
			host = ""
		if not host:
			return "Direto"
		if "google." in host:
			return "Busca Orgânica"
		if "bing." in host or "yahoo." in host or "duckduckgo." in host:
			return "Busca Orgânica"
		return "Referência"
	return "Direto"


def _registrar_evento_row(
	session_name: str,
	visitor_id: str,
	tipo_evento: str,
	rota: str | None,
	metadados: str | dict | None,
) -> str:
	payload = _metadados_seguros(metadados)
	ev = frappe.get_doc(
		{
			"doctype": "Imunocare Web Event",
			"session": session_name,
			"visitor_id": visitor_id,
			"tipo_evento": tipo_evento,
			"rota": rota,
			"timestamp": now_datetime(),
			"metadados": payload,
		}
	)
	ev.insert(ignore_permissions=True)
	return ev.name


def _metadados_seguros(metadados: str | dict | None) -> dict:
	"""Normaliza para dict, limita tamanho, nunca inclui PII (contrato do chamador)."""
	if not metadados:
		return {}
	if isinstance(metadados, str):
		try:
			metadados = json.loads(metadados)
		except Exception:
			return {}
	if not isinstance(metadados, dict):
		return {}
	# Limita a poucos campos rasos para não virar um blob arbitrário.
	seguro: dict = {}
	for k, v in list(metadados.items())[:10]:
		if isinstance(v, (str, int, float, bool)) or v is None:
			seguro[str(k)[:40]] = v[:200] if isinstance(v, str) else v
	return seguro
