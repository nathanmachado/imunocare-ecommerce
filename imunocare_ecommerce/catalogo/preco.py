"""Preço exibido na loja: Pix e parcelado vêm das condições de pagamento do fiscal."""

import frappe
from frappe.utils import flt

_PARAMETROS = "imunocare_fiscal.condicoes_pagamento.parametros"
_CONDICOES = "imunocare_fiscal.condicoes_pagamento.condicoes"


def parametros_do_fiscal() -> dict | None:
	# App fiscal ausente ou com erro = não configurado; a loja nunca cai por isso.
	try:
		return frappe.get_attr(_PARAMETROS)()
	except Exception:
		return None


def preco_loja(preco, params=None) -> dict | None:
	"""{"pix", "parcelas", "parcela"} | {"pix"} sem 2x oferecido | None sem parâmetros/preço."""
	if preco is None or preco == "" or flt(preco) <= 0:
		return None
	params = params or parametros_do_fiscal()
	if not params:
		return None
	try:
		cond = frappe.get_attr(_CONDICOES)(flt(preco), params)
	except Exception:
		return None
	if not cond.get("configurado"):
		return None
	r = {"pix": cond["avista"]}
	ultima = cond["parcelas"][-1] if cond["parcelas"] else None
	if ultima and ultima["n"] >= 2:
		r.update(parcelas=ultima["n"], parcela=ultima["parcela"])
	return r
