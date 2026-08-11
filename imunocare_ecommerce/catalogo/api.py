"""API pública leve do catálogo — usada pelo JS de listagem (item 4, chips de
navegação por categoria em /all-products e nas páginas de categoria).

Reuso: nenhuma lógica nova de categoria é criada aqui — só expõe
``catalogo.setup.nav_categorias_loja()`` (mesma fonte usada pela nav da home,
``www/index.py``) como endpoint ``allow_guest`` para o JS chamar 1x por
carregamento de página de listagem.
"""

from __future__ import annotations

import frappe


@frappe.whitelist(allow_guest=True)
def categorias_nav() -> list[dict]:
	"""Categorias ativas da Linha Imuno (Vacinas/Vitaminas Injetáveis/Terapias
	Injetáveis/Planos/Consultas Médicas/Brincos — já refletindo a remoção de
	Exames/Vale-Presente do item 2a), cada uma com ``{"nome", "route"}``.

	Não lança exceção — chamado de página pública (guest incluso)."""
	try:
		from imunocare_ecommerce.catalogo.setup import nav_categorias_loja

		return nav_categorias_loja()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "imunocare_ecommerce.catalogo.api")
		return []


# ---------------------------------------------------------------------------
# Atividade 541 (Feature 72) — sinal serviço×produto no grid/listagem
# ---------------------------------------------------------------------------


@frappe.whitelist(allow_guest=True)
def get_product_filter_data_loja(query_args=None) -> dict:
	"""Override de ``webshop.webshop.api.get_product_filter_data``
	(``hooks.override_whitelisted_methods``) — MESMO retorno nativo (query,
	filtros, paginação de ``ProductQuery``, 100% reusados, upstream não
	tocado), só ACRESCENTA ``imun_servico``/``imun_appointment_type`` em cada
	item.

	Cobre os dois pontos de entrada do grid/lista: o carregamento inicial
	(``webshop...product_ui/views.js``) e o "Carregar mais"
	(``public/js/product_list_more.js``) — ambos chamam este MESMO método
	whitelisted, então o override cobre os dois sem código extra.

	``public/js/agendamento.js`` monkey-patcha
	``webshop.ProductGrid/ProductList.get_primary_button`` pra ler
	``item.imun_servico`` e desenhar "Agendar" no lugar do botão nativo —
	sem precisar de 1 chamada ao backend por card."""
	from webshop.webshop.api import get_product_filter_data

	resultado = get_product_filter_data(query_args=query_args)
	_enriquecer_com_sinal_servico(resultado.get("items") or [])
	return resultado


def _enriquecer_com_sinal_servico(items: list) -> None:
	from imunocare_ecommerce.catalogo.servico import sinal_servico

	for item in items:
		try:
			sinal = sinal_servico(item.get("item_code"))
		except Exception:
			frappe.log_error(frappe.get_traceback(), "imunocare_ecommerce.catalogo.api")
			sinal = {"servico": False, "appointment_type": None}
		item["imun_servico"] = 1 if sinal["servico"] else 0
		item["imun_appointment_type"] = sinal["appointment_type"]
