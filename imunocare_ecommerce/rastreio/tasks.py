"""Jobs agendados do rastreio da jornada (Feature 56 / A2.3 + A2.4 + LGPD).

  - ``detectar_carrinhos_abandonados`` (hourly): carrinho abandonado é lido
    diretamente do ``Quotation`` (``order_type="Shopping Cart"``) nativo do
    webshop — não duplicamos o carrinho em lugar nenhum. Só carimba
    ``imun_abandono_notificado`` (evita reprocessar) e alimenta o funil via
    ``rastreio.funil.registrar_conversao``.
  - ``purgar_dados_antigos`` (daily): minimização de dados (LGPD) — Imunocare
    Web Event tem retenção curta (default 180 dias); Imunocare Web Session
    sem conversão em Lead tem retenção mais longa mas finita (default 400
    dias). Sessões já convertidas em Lead são preservadas (valor para o CRM),
    mas seus Web Events "brutos" ainda são purgados no prazo normal — o
    resumo que importa (origem/UTM/conversão) já está carimbado no Lead.

Ambos idempotentes e tolerantes a falha — nunca devem quebrar o scheduler.
"""

from __future__ import annotations

import frappe
from frappe.utils import add_to_date, add_days, now_datetime

_LOG_TITLE = "imunocare_ecommerce.rastreio.tasks"


def _settings() -> "frappe._dict":
	if frappe.db.exists("DocType", "Imunocare Ecommerce Settings"):
		return frappe.get_single("Imunocare Ecommerce Settings")
	return frappe._dict()


# ---------------------------------------------------------------------------
# Carrinho abandonado
# ---------------------------------------------------------------------------


def detectar_carrinhos_abandonados() -> dict:
	"""Varre Quotations (Shopping Cart) paradas há X horas e alimenta o funil.

	Retorna contagens para observabilidade (log). Nunca lança para o scheduler.
	"""
	if not frappe.db.exists("DocType", "Quotation"):
		return {"escaneados": 0, "notificados": 0, "erros": 0}
	if not frappe.db.exists("Custom Field", {"dt": "Quotation", "fieldname": "imun_session_id"}):
		# rastreio.setup ainda não rodou (webshop instalado depois) — adia.
		return {"escaneados": 0, "notificados": 0, "erros": 0}

	horas = frappe.utils.cint(_settings().get("carrinho_abandonado_horas") or 2)
	cutoff = add_to_date(now_datetime(), hours=-horas)

	candidatos = frappe.get_all(
		"Quotation",
		filters={
			"order_type": "Shopping Cart",
			"docstatus": 0,
			"modified": ("<=", cutoff),
			"imun_abandono_notificado": 0,
		},
		fields=[
			"name",
			"contact_email",
			"contact_mobile",
			"contact_display",
			"customer_name",
			"grand_total",
			"imun_session_id",
		],
	)

	notificados = 0
	erros = 0
	for q in candidatos:
		try:
			if not q.grand_total or not (q.contact_email or q.contact_mobile):
				# carrinho vazio ou sem qualquer identidade (não deveria ocorrer —
				# carrinho exige login — mas não custa garantir).
				frappe.db.set_value(
					"Quotation", q.name, "imun_abandono_notificado", 1, update_modified=False
				)
				continue

			from imunocare_ecommerce.rastreio.funil import registrar_conversao

			registrar_conversao(
				tipo_evento="carrinho_abandonado",
				email=q.contact_email,
				phone=q.contact_mobile,
				nome=q.contact_display or q.customer_name,
				session_id=q.imun_session_id,
			)

			if q.imun_session_id and frappe.db.exists("Imunocare Web Session", q.imun_session_id):
				_registrar_evento_abandono(q)

			frappe.db.set_value(
				"Quotation", q.name, "imun_abandono_notificado", 1, update_modified=False
			)
			notificados += 1
		except Exception:
			erros += 1
			frappe.log_error(
				title=f"detectar_carrinhos_abandonados falhou (quotation={q.name})",
				message=frappe.get_traceback(),
			)

	resultado = {"escaneados": len(candidatos), "notificados": notificados, "erros": erros}
	frappe.logger(_LOG_TITLE).info(f"detectar_carrinhos_abandonados: {resultado}")
	return resultado


def _registrar_evento_abandono(q) -> None:
	frappe.get_doc(
		{
			"doctype": "Imunocare Web Event",
			"session": q.imun_session_id,
			"tipo_evento": "carrinho_abandonado",
			"timestamp": now_datetime(),
			"metadados": {"quotation": q.name, "valor": q.grand_total},
		}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Retenção / minimização de dados (LGPD)
# ---------------------------------------------------------------------------


def purgar_dados_antigos() -> dict:
	"""Remove Imunocare Web Event/Session além da janela de retenção configurada."""
	settings = _settings()
	dias_eventos = frappe.utils.cint(settings.get("retencao_eventos_dias") or 180)
	dias_sessoes = frappe.utils.cint(settings.get("retencao_sessoes_dias") or 400)

	eventos_removidos = 0
	sessoes_removidas = 0
	try:
		if frappe.db.exists("DocType", "Imunocare Web Event"):
			cutoff_eventos = add_days(now_datetime(), -dias_eventos)
			eventos_removidos = frappe.db.count(
				"Imunocare Web Event", {"timestamp": ("<", cutoff_eventos)}
			)
			frappe.db.delete("Imunocare Web Event", {"timestamp": ("<", cutoff_eventos)})

		if frappe.db.exists("DocType", "Imunocare Web Session"):
			cutoff_sessoes = add_days(now_datetime(), -dias_sessoes)
			filtros = {"ultimo_acesso": ("<", cutoff_sessoes), "converteu_lead": 0}
			sessoes_removidas = frappe.db.count("Imunocare Web Session", filtros)
			frappe.db.delete("Imunocare Web Session", filtros)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)

	resultado = {"eventos_removidos": eventos_removidos, "sessoes_removidas": sessoes_removidas}
	frappe.logger(_LOG_TITLE).info(f"purgar_dados_antigos: {resultado}")
	return resultado
