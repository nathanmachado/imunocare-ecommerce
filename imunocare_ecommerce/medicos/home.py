"""Leitura para a home (R2 — carrossel de médicos parceiros). Só consulta,
não escreve nada — os custom fields são geridos por ``medicos.setup``.
"""

from __future__ import annotations

import frappe


def medicos_para_home(limite: int = 8) -> list[dict]:
	"""Healthcare Practitioner com ``imun_publicar_site=1``, para o carrossel
	da home. Cada item: {"nome", "foto", "especialidade", "bio",
	"appointment_type" (ou None), "practitioner"}.

	Degrade gracioso: retorna lista vazia (nunca lança exceção) se o
	Healthcare não estiver instalado, o custom field ainda não existir
	(app recém-instalado, antes do primeiro migrate) ou não houver nenhum
	profissional publicado — a home esconde a seção inteira nesse caso (ver
	``www/index.html``)."""
	try:
		if not frappe.db.exists("DocType", "Healthcare Practitioner"):
			return []
		if not frappe.db.exists("Custom Field", {"dt": "Healthcare Practitioner", "fieldname": "imun_publicar_site"}):
			return []

		practitioners = frappe.get_all(
			"Healthcare Practitioner",
			filters={"imun_publicar_site": 1, "status": "Active"},
			fields=[
				"name",
				"practitioner_name",
				"image",
				"department",
				"designation",
				"imun_bio_publica",
				"imun_appointment_type",
			],
			order_by="practitioner_name asc",
			limit_page_length=limite,
		)
		return [
			{
				"practitioner": p.name,
				"nome": p.practitioner_name,
				"foto": p.image,
				"especialidade": p.designation or p.department or "",
				"bio": (p.imun_bio_publica or "").strip(),
				"appointment_type": p.imun_appointment_type or None,
			}
			for p in practitioners
		]
	except Exception:
		frappe.log_error(frappe.get_traceback(), "imunocare_ecommerce.medicos.home")
		return []
