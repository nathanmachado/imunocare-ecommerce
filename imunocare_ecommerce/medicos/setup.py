"""Carrossel de médicos parceiros na home (R2 — Feature 70 / REDO do site).

Reuso primeiro — o que este módulo NÃO reimplementa:

  - Cadastro do médico: 100% ``Healthcare Practitioner`` nativo (Healthcare) —
    já tem ``image``, ``department``, ``designation``, ``status``. Nenhum
    DocType novo.
  - Agendamento pelo botão "Agendar" do carrossel: 100% o fluxo já pronto em
    ``agendamento.booking`` (mesmo endpoint usado pela landing "Protocolo de
    Emagrecimento" — ``info_agendamento_tipo``/``get_horarios``/
    ``criar_agendamento`` aceitando ``appointment_type`` direto, sem Website
    Item) + o diálogo JS compartilhado (``public/js/agendamento.js``,
    ``window.imunAbrirAgendamentoDialogo``). Ver ``public/js/medicos_carrossel.js``.

O que este módulo acrescenta (o gap): 3 Custom Fields em
``Healthcare Practitioner`` para controlar SE e COMO o profissional aparece
no site público — nada disso existe no Healthcare nativo (que não tem noção
de "site"/loja):

  - ``imun_publicar_site`` (Check): opt-in explícito — por padrão NENHUM
    profissional aparece no site (evita publicar acidentalmente um médico
    que só atende B2B/convênio).
  - ``imun_bio_publica`` (Small Text): texto curto para o card do carrossel
    (a ficha interna do Healthcare Practitioner não tem um campo de bio
    voltado ao público).
  - ``imun_appointment_type`` (Link -> Appointment Type): qual tipo de
    agendamento o botão "Agendar" do card abre. Opcional — sem ele, o card
    mostra "Saiba mais" (link para a landing /parceria-com-medicos) em vez
    de abrir o diálogo de horários.

Idempotente: ``create_custom_fields(..., update=True)`` faz upsert por
(dt, fieldname) — mesmo padrão usado em ``imunocare_clinic_ext.custom_fields``
e em ``agendamento.setup``. Nunca interrompe o migrate.
"""

from __future__ import annotations

import frappe

_LOG_TITLE = "imunocare_ecommerce.medicos.setup"

CUSTOM_FIELDS: dict[str, list[dict]] = {
	"Healthcare Practitioner": [
		{
			"fieldname": "imun_site_section",
			"fieldtype": "Section Break",
			"label": "Publicação no Site (Loja Imunocare)",
			"insert_after": "designation",
			"collapsible": 1,
		},
		{
			"fieldname": "imun_publicar_site",
			"fieldtype": "Check",
			"label": "Publicar no site (carrossel de médicos parceiros)",
			"insert_after": "imun_site_section",
			"default": "0",
			"description": (
				"Se marcado, este profissional aparece no carrossel de médicos "
				"parceiros da home da loja (foto, especialidade e bio abaixo)."
			),
		},
		{
			"fieldname": "imun_bio_publica",
			"fieldtype": "Small Text",
			"label": "Bio pública (site)",
			"insert_after": "imun_publicar_site",
			"depends_on": "eval:doc.imun_publicar_site",
			"description": "Texto curto exibido no card do carrossel da home (2-3 linhas).",
		},
		{
			"fieldname": "imun_appointment_type",
			"fieldtype": "Link",
			"options": "Appointment Type",
			"label": "Tipo de Agendamento (site)",
			"insert_after": "imun_bio_publica",
			"depends_on": "eval:doc.imun_publicar_site",
			"description": (
				"Opcional. Se preenchido, o botão \"Agendar\" do card abre o mesmo "
				"diálogo de horários já usado pelo agendamento online da loja "
				"(agendamento.booking), com este profissional pré-selecionado. Vazio: "
				"o card mostra \"Saiba mais\", levando à página Parceria com Médicos."
			),
		},
	]
}


def setup_medicos() -> None:
	"""Entry-point idempotente (after_install/after_migrate). Nunca interrompe
	o migrate — degrada com aviso em log se o Healthcare ainda não estiver
	instalado."""
	try:
		if not frappe.db.exists("DocType", "Healthcare Practitioner"):
			frappe.logger(_LOG_TITLE).warning(
				"healthcare ainda não instalado — custom fields do carrossel de médicos adiados."
			)
			return
		from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

		create_custom_fields(CUSTOM_FIELDS, update=True)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
	finally:
		frappe.clear_cache()
