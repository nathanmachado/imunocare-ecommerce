"""Preço exibido na loja: Pix e parcelado derivados do preço do ERP (vitrine-sem-marca)."""

import frappe
from frappe.utils import flt

_CAMPOS = {
	"desconto_pix": "desconto_pix",
	"juros_vista": "juros_vista",
	"juros_parcelado": "juros_parcelado",
	"parcelas": "numero_parcelas",
	"parcela_minima": "parcela_minima",
}


def _params_do_settings() -> dict:
	# get_singles_dict lê tabSingles cru: campo novo sem valor vem ausente, não 0.
	d = frappe.db.get_singles_dict("Imunocare Ecommerce Settings")
	return {k: d.get(f) for k, f in _CAMPOS.items()}


def _vazio(v) -> bool:
	return v is None or v == ""


def preco_loja(preco, params=None) -> dict | None:
	"""{"pix", "parcelas", "parcela"} | {"pix"} se parcela < mínima | None sem parâmetros/preço."""
	p = params if params is not None else _params_do_settings()
	if _vazio(preco) or flt(preco) <= 0 or any(_vazio(p.get(k)) for k in _CAMPOS):
		return None
	preco = flt(preco)
	n = int(flt(p["parcelas"]))
	minima = flt(p["parcela_minima"])
	if n <= 0 or minima <= 0:
		return None

	pix = flt(preco * (1 - flt(p["desconto_pix"]) / 100), 2)
	total = preco / (1 + flt(p["juros_vista"]) / 100) * (1 + flt(p["juros_parcelado"]) / 100)
	parcela = flt(total / n, 2)
	if parcela < minima:
		return {"pix": pix}
	return {"pix": pix, "parcelas": n, "parcela": parcela}
