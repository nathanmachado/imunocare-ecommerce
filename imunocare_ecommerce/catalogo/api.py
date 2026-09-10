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
	"""Categorias de navegação da loja (taxonomia 2026-09-04 — Vacinas/
	Vitaminas/Terapias Injetáveis/Consultas/Nutracêuticos/Cuidado diário/
	Brincos; Planos e Exames/Vale-Presente ficam fora da nav de topo), cada
	uma com ``{"nome", "route"}``.

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
	item e (Task 2.3) corrige categoria+busca para combinar com E.

	Cobre os dois pontos de entrada do grid/lista: o carregamento inicial
	(``webshop...product_ui/views.js``) e o "Carregar mais"
	(``public/js/product_list_more.js``) — ambos chamam este MESMO método
	whitelisted, então o override cobre os dois sem código extra.

	``public/js/agendamento.js`` monkey-patcha
	``webshop.ProductGrid/ProductList.get_primary_button`` pra ler
	``item.imun_servico`` e desenhar "Agendar" no lugar do botão nativo —
	sem precisar de 1 chamada ao backend por card."""
	from webshop.webshop.api import get_product_filter_data

	query_args = _combinar_busca_e_categoria(query_args)
	resultado = get_product_filter_data(query_args=query_args)
	_enriquecer_com_sinal_servico(resultado.get("items") or [])
	return resultado


# ---------------------------------------------------------------------------
# Task 2.3 (spec loja-agendar-em-toda-pagina) — categoria E busca combinam
# com E, não OU
# ---------------------------------------------------------------------------


def _combinar_busca_e_categoria(query_args):
	"""Causa raiz (achado da Task 2.2, corrigido aqui — ver
	``webshop/webshop/product_data_engine/query.py``): ``ProductQuery.query``
	(linhas 61-66) grava TANTO ``build_item_group_filters`` (linhas 179-198)
	QUANTO ``build_search_filters`` (linhas 200-221) em ``self.or_filters`` —
	a query final vira ``WHERE published=1 AND (cond_categoria_1 OR
	cond_categoria_2 OR ... OR cond_busca_1 OR ...)``: com os dois
	presentes, um item de OUTRA categoria que bata na busca (ou vice-versa)
	também aparece. Só ``field_filters`` (``build_fields_filters``, linhas
	152-176) vai para ``self.filters`` (E) — inclusive listas, que viram
	``["campo", "in", valores]`` (linha 172).

	Fix (ponto único, sem copiar nada do webshop — só REUSA os métodos
	nativos): quando ``query_args`` tem ``search`` E ``item_group`` ao mesmo
	tempo, resolve ANTES quais ``Website Item`` pertencem à categoria — com
	a MESMA regra nativa (``ProductQuery.build_item_group_filters``: match
	direto no campo ``Item.item_group``, match via a tabela CURADA ``Website
	Item Group`` — fonte de verdade da taxonomia deste app, ver
	``catalogo/jinja_utils.py`` — e os grupos descendentes via lft/rgt
	quando ``Item Group.include_descendants``, tudo dentro do PRÓPRIO
	método nativo, chamado direto, não reimplementado) — e converte esse
	conjunto em ``field_filters["item_code"]`` (E, via ``build_fields_filters``),
	tirando ``item_group`` dos args. O resto (``search``,
	``attribute_filters``, ``start``, ``from_filters``) segue pro nativo sem
	mudança — o ``search`` continua OR **entre os próprios campos de busca**
	(item_code/item_name/descrição/etc — é assim que busca deve funcionar),
	só deixa de virar OR com a categoria.

	Sem ``search`` OU sem ``item_group``, devolve ``query_args`` como
	chegou, sem tocar em nada — o caminho de hoje (browsing só por
	categoria, ou só por busca em ``/all-products``, Task 2.2) fica intacto.

	Formato de entrada: mesmo aceito por ``get_product_filter_data``
	(``webshop/webshop/api.py:31-34``) — ``query_args`` pode chegar como
	string JSON (replicamos o mesmo ``json.loads``) ou já como dict/``_dict``
	(chamada Python direta, ex. testes)."""
	import json

	if isinstance(query_args, str):
		query_args = json.loads(query_args)
	query_args = frappe._dict(query_args or {})

	search = query_args.get("search")
	item_group = query_args.get("item_group")
	if not (search and item_group):
		return query_args

	codigos = _codigos_website_item_da_categoria(item_group)

	field_filters = dict(query_args.get("field_filters") or {})
	# Categoria sem NENHUM item publicado (ex.: item_group inexistente/vazio
	# combinado com busca): build_fields_filters (query.py:158-159) IGNORA
	# valor de lista vazia (``if not values: continue``) — sem esta guarda o
	# filtro de item_code sumiria e a busca voltaria a trazer TUDO. Uma
	# chave impossível de bater garante 0 resultados, igual à intersecção
	# vazia esperada.
	field_filters["item_code"] = codigos or ["__imun_categoria_vazia__"]
	query_args["field_filters"] = field_filters
	query_args.pop("item_group", None)
	return query_args


def _codigos_website_item_da_categoria(item_group: str) -> list[str]:
	"""``item_code`` de todo ``Website Item`` PUBLICADO que pertence a
	``item_group`` pela MESMA regra que
	``webshop.webshop.product_data_engine.query.ProductQuery.
	build_item_group_filters`` usa (chamado direto — zero reimplementação
	de lft/rgt/tabela curada): monta as mesmas condições OR do nativo
	(``engine.or_filters``) e as executa aqui como uma consulta própria, só
	para materializar o RESULTADO num filtro de ``item_code`` (não para
	decidir a query inteira — quem decide continua sendo
	``get_product_filter_data``/``ProductQuery.query``)."""
	from webshop.webshop.product_data_engine.query import ProductQuery

	engine = ProductQuery()
	engine.build_item_group_filters(item_group)
	# frappe.db.get_all (mesma chamada que query_items/query.py:97,113 usa
	# pra buscar Website Item publicamente, guest incluso — é só um alias de
	# frappe.get_all, database.py:761-762, mas mantém o padrão visual do
	# nativo aqui).
	return frappe.db.get_all(
		"Website Item",
		filters=[["published", "=", 1]],
		or_filters=engine.or_filters,
		pluck="item_code",
	)


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
