"""Custom fields do agendamento online (Feature 55 / A1.3).

Reuso máximo: o agendamento em si é um ``Patient Appointment`` nativo do
Healthcare (``imunocare_clinic_ext`` já opera o ciclo Pagamento->Aplicação->
Faturamento sobre esse mesmo DocType). Este módulo só acrescenta o elo que
falta — "qual item da loja abre qual tipo de agendamento, com qual
profissional" — via 2 Custom Fields em ``Website Item`` e 1 em
``Patient Appointment`` (rastreio de origem). A lógica de disponibilidade de
horário, criação do paciente e faturamento vive em ``agendamento.booking``.

Idempotente: pode ser chamado múltiplas vezes (after_migrate) sem duplicar
Custom Fields. Se ``webshop``/``healthcare`` ainda não estiverem instalados,
degrada com aviso — não interrompe o migrate.
"""

from __future__ import annotations

import frappe

_LOG_TITLE = "imunocare_ecommerce.agendamento.setup"

# (dt, fieldname, definição sem dt/fieldname)
_CUSTOM_FIELDS: list[tuple[str, str, dict]] = [
	(
		"Website Item",
		"imun_agendamento_sb",
		{
			"fieldtype": "Section Break",
			"label": "Agendamento Online (Healthcare)",
			"insert_after": "route",
			"collapsible": 1,
		},
	),
	(
		"Website Item",
		"imun_appointment_type",
		{
			"fieldtype": "Link",
			"options": "Appointment Type",
			"label": "Tipo de Agendamento",
			"insert_after": "imun_agendamento_sb",
			"description": (
				"Se preenchido, este item exibe um botão \"Agendar\" na loja em vez de "
				"(ou além de) compra direta — ao confirmar, cria um Patient Appointment "
				"nativo do Healthcare. Deixe vazio para itens que não são agendáveis "
				"(ex.: vacinas de aplicação avulsa, vale-presente, brincos)."
			),
		},
	),
	(
		"Website Item",
		"imun_practitioner",
		{
			"fieldtype": "Link",
			"options": "Healthcare Practitioner",
			"label": "Profissional (padrão)",
			"insert_after": "imun_appointment_type",
			"description": (
				"Opcional. Profissional que atende este serviço pela loja. Se vazio, "
				"o agendamento só é aceito automaticamente quando existir exatamente 1 "
				"Healthcare Practitioner Ativo cadastrado; caso contrário o cliente "
				"precisa escolher (fora do escopo desta 1ª versão)."
			),
		},
	),
	(
		"Patient Appointment",
		"imun_origem_loja",
		{
			"fieldtype": "Check",
			"label": "Originado na Loja Online",
			"insert_after": "duration",
			"read_only": 1,
			"description": "Marcado automaticamente quando o agendamento nasce do fluxo A1.3 (loja/site).",
		},
	),
	(
		"Patient Appointment",
		"imun_modalidade",
		{
			"fieldtype": "Select",
			"options": "Na Clínica\nDomiciliar",
			"default": "Na Clínica",
			"label": "Modalidade de Atendimento",
			"insert_after": "imun_origem_loja",
			"description": (
				"Escolhida pelo cliente ao agendar pela loja (BRIEF_LOJA.md item 4). "
				"A taxa de atendimento domiciliar (Imunocare Ecommerce Settings) ainda não "
				"é cobrada automaticamente neste fluxo — a recepção confirma/cobra a taxa "
				"conforme o atendimento."
			),
		},
	),
]


def setup_agendamento() -> None:
	"""Entry-point idempotente (after_migrate). Nunca interrompe o migrate."""
	try:
		if not frappe.db.exists("DocType", "Website Item"):
			frappe.logger(_LOG_TITLE).warning(
				"webshop ainda não instalado — custom fields de agendamento adiados."
			)
			return
		if not frappe.db.exists("DocType", "Patient Appointment"):
			frappe.logger(_LOG_TITLE).warning(
				"healthcare ainda não instalado — custom fields de agendamento adiados."
			)
			return
		for dt, fieldname, definicao in _CUSTOM_FIELDS:
			_ensure_custom_field(dt, fieldname, definicao)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
	finally:
		frappe.clear_cache()


def _ensure_custom_field(dt: str, fieldname: str, definicao: dict) -> None:
	if frappe.db.exists("Custom Field", {"dt": dt, "fieldname": fieldname}):
		return
	doc_data = {
		"doctype": "Custom Field",
		"dt": dt,
		"fieldname": fieldname,
		**definicao,
	}
	frappe.get_doc(doc_data).insert(ignore_permissions=True)
