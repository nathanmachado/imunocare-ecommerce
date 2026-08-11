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
