"""Sinal serviço×produto do catálogo (Feature 72 — Atividades 540/541).

Fonte ÚNICA da regra "este item é agendável (serviço) ou é produto físico" —
reusada tanto pela página do item (jinja, ``catalogo.jinja_utils``, Atividade
540) quanto pelo grid/listagem (``catalogo.api``, override de
``webshop.webshop.api.get_product_filter_data``, Atividade 541). NÃO duplica
a validação completa de agendamento (isso é
``agendamento.booking._item_agendavel``, que também confere se o Appointment
Type/practitioner realmente funcionam) — aqui é só o SINAL rápido para o
client-side decidir qual botão desenhar sem 1 chamada ao backend por card; o
clique em "Agendar" sempre dispara ``booking.info_agendamento``/
``booking.criar_agendamento`` (validação completa, com fallback pro
comportamento de produto se algo estiver mal configurado — SPEC item 4).

Regra (SPEC 2026-08-11-loja-servico-agendavel.md, item 3):
  - serviço = Website Item tem ``imun_appointment_type`` preenchido;
  - produto = ``is_stock_item=1`` OU sem appointment type.

Um item com ``imun_appointment_type`` preenchido e ``is_stock_item=1`` ao
mesmo tempo (combinação que não deveria existir no catálogo real —
``catalogo/importar_prod.py`` sempre cria ``is_stock_item=0``) cai em
"produto" por segurança: um item de estoque físico nunca deve virar botão de
agendamento.
"""

from __future__ import annotations

import frappe

_LOG_TITLE = "imunocare_ecommerce.catalogo.servico"


def sinal_servico(item_code: str | None) -> dict:
	"""``{"servico": bool, "appointment_type": str | None}`` para um ``item_code``.

	Nunca lança exceção — chamado de página pública (guest incluso) e do
	enriquecimento do grid (potencialmente dezenas de itens por página)."""
	if not item_code:
		return {"servico": False, "appointment_type": None}
	try:
		appointment_type = frappe.db.get_value(
			"Website Item", {"item_code": item_code}, "imun_appointment_type"
		)
		is_stock_item = frappe.db.get_value("Item", item_code, "is_stock_item")
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {"servico": False, "appointment_type": None}

	servico = bool(appointment_type) and not bool(is_stock_item)
	return {"servico": servico, "appointment_type": appointment_type if servico else None}
