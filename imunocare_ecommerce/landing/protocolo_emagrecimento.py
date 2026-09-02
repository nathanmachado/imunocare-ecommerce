"""Landing "Protocolo de Emagrecimento com Acompanhamento Médico" (F9).

Reuso — o que este módulo NÃO reimplementa:

  - Agendamento em si: 100% ``agendamento.booking`` (A1.3) — a landing usa
    ``booking.info_agendamento_tipo``/``get_horarios``/``criar_agendamento``
    com ``appointment_type`` vindo de
    ``Imunocare Ecommerce Settings.protocolo_emagrecimento_appointment_type``
    em vez de um ``item_code`` (F9: "Fora do catálogo de produtos, sem
    Website Item de medicamento" — não existe Website Item aqui).
  - Lead/funil: ``rastreio.funil.registrar_conversao`` (mesmo ponto de
    conversão de F8/agendamento), com ``origem_source="Protocolo
    Emagrecimento"``.

O que este módulo acrescenta (o gap): quando o Appointment Type ainda NÃO
está configurado (estado inicial nesta atividade — o dono não criou nenhum
Appointment Type/Practitioner de emagrecimento ainda), o CTA "Agende sua
avaliação" degrada para uma captura de interesse simples (nome/telefone/
e-mail) em vez de travar numa função que não pode funcionar sem dado de
negócio que não temos ("reuso primeiro"/"não inventar dado de negócio" —
ver relatório do dev-ecommerce).
"""

from __future__ import annotations

import frappe
from frappe import _
from imunocare_ecommerce.rate_limit import rate_limit

_LOG_TITLE = "imunocare_ecommerce.landing.protocolo_emagrecimento"


@frappe.whitelist(allow_guest=True)
def info_avaliacao() -> dict:
	"""Estado do CTA para o storefront decidir entre calendário de horários
	(Appointment Type configurado) ou formulário de interesse (fallback)."""
	appointment_type = frappe.db.get_single_value(
		"Imunocare Ecommerce Settings", "protocolo_emagrecimento_appointment_type"
	)
	if not appointment_type:
		return {"agendavel": False}

	from imunocare_ecommerce.agendamento.booking import info_agendamento_tipo

	info = info_agendamento_tipo(appointment_type)
	info["appointment_type"] = appointment_type
	return info


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=60)
def enviar_interesse(
	nome: str,
	telefone: str | None = None,
	email: str | None = None,
	mensagem: str | None = None,
	session_id: str | None = None,
) -> dict:
	"""Captura de interesse (fallback quando não há Appointment Type
	configurado ainda). Nunca lança 500 — falhas viram log + mensagem
	amigável."""
	nome = (nome or "").strip()
	email = (email or "").strip() or None
	telefone = (telefone or "").strip() or None

	if not nome:
		frappe.throw(_("Informe seu nome."))
	if not email and not telefone:
		frappe.throw(_("Informe e-mail ou telefone para retornarmos o contato."))

	try:
		from imunocare_ecommerce.rastreio.funil import registrar_conversao

		lead_name = registrar_conversao(
			tipo_evento="lead_form_submit",
			email=email,
			phone=telefone,
			nome=nome,
			session_id=session_id,
			origem_source="Protocolo Emagrecimento",
		)
		if lead_name and mensagem:
			try:
				lead = frappe.get_doc("CRM Lead", lead_name)
				lead.add_comment(
					"Comment",
					f"<b>{_('Protocolo de Emagrecimento — interesse em avaliação')}</b><br>"
					f"Mensagem: {frappe.utils.escape_html(mensagem)[:1000]}",
				)
			except Exception:
				frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {
			"ok": True,
			"mensagem": _("Recebemos seu contato! Nossa equipe vai retornar para agendar sua avaliação."),
		}
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {"ok": False, "mensagem": _("Não foi possível enviar agora. Tente novamente em instantes.")}
