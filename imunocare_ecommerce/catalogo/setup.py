"""Configuração do catálogo web das 6 seções da loja Imunocare.

Idempotente: pode ser chamado via after_install e after_migrate sem efeitos
colaterais ao rodar múltiplas vezes.

Se o app webshop ainda não estiver instalado (DocType "Website Item" ausente),
os Item Groups são criados normalmente mas a publicação dos Website Items é
adiada e registrada em log — o CTO deve rodar bench migrate novamente após
instalar o webshop.

Hierarquia de Item Groups criada:
  All Item Groups
    └── Loja Imunocare  (is_group=1, pai de navegação)
          ├── Vacinas
          ├── Vitaminas Injetáveis
          ├── Terapias Injetáveis
          ├── Consultas Médicas
          ├── Vale-Presente
          └── Brincos

ATENÇÃO — "Vacinas" pode já existir (criado pelo imunocare_clinic_ext / seed):
  - Se NÃO existe → cria sob "Loja Imunocare" (ideal para navegação).
  - Se JÁ existe  → mantém o parent original; o operador pode reparentar
    manualmente para "Loja Imunocare" via Stock > Item Group se desejar.
  Os demais 5 grupos são novos e serão criados sob "Loja Imunocare".

Mapeamento Item → seção:
  Apenas Items de serviço (is_stock_item=0, is_sales_item=1) são publicados.
  O item_group do Item é comparado (substring, case-insensitive) com as
  palavras-chave definidas em _SECTION_MAP.
"""

from __future__ import annotations

import re

import frappe

# ---------------------------------------------------------------------------
# Taxonomia da loja
# ---------------------------------------------------------------------------

# F7 (duas linhas Imuno x Care): "Loja Imunocare" já era, na prática, a
# "Linha Imuno" (clínica/injetáveis) — mantido o NOME/rota técnica como
# estava de propósito (F7 avisa: "mover Item Group de pai reflete nas
# rotas" — renomear/reparentar agora quebraria as rotas já publicadas dos
# produtos reais). A separação Imuno x Care (F5/F7) é uma decisão de
# APRESENTAÇÃO (nav do site, ver www/index.html) sobre a MESMA árvore
# nativa de Item Group — sem duplicar taxonomia nem gerar churn de rota.
_GRUPO_PAI = "Loja Imunocare"  # = "Linha Imuno" na navegação do site

# Linha Care (F7): novo grupo-pai irmão de "Loja Imunocare", só para
# produtos de cuidado pessoal (cosmético) — nada de injetável/clínico aqui.
_GRUPO_PAI_CARE = "Cuidado Pessoal"  # = "Linha Care" na navegação do site

# Ordem importa: o pai deve ser criado antes dos filhos.
# Tupla: (nome, is_group, parent_item_group)
# Item 2b (2026-08-10): "Pacotes" -> "Planos" (rename real, ver
# ``_migrar_pacotes_para_planos``, chamada por ``_setup_item_groups``).
_ITEM_GROUPS: list[tuple[str, int, str]] = [
	(_GRUPO_PAI, 1, "All Item Groups"),
	("Vacinas", 0, _GRUPO_PAI),
	("Vitaminas Injetáveis", 0, _GRUPO_PAI),
	("Terapias Injetáveis", 0, _GRUPO_PAI),
	("Consultas Médicas", 0, _GRUPO_PAI),
	("Vale-Presente", 0, _GRUPO_PAI),
	("Brincos", 0, _GRUPO_PAI),
	("Planos", 0, _GRUPO_PAI),
	# Exames (F7): novo, sem item hoje — página informativa (ver
	# templates/generators/item_group.html + catalogo.jinja_utils).
	("Exames", 0, _GRUPO_PAI),
]

# Linha Care (F7): estrutura pronta (show_in_website=1, copy SEO), sem
# produtos ainda — o dono cadastra a lista real depois (ver
# catalogo.importar_prod._SECOES_CARE, já pronto para receber). Até lá,
# cada categoria renderiza com copy "em breve" + captura de interesse (via
# templates/generators/item_group.html, mesmo tratamento de categoria vazia
# usado em Consultas/Exames/Terapias).
_ITEM_GROUPS_CARE: list[tuple[str, int, str]] = [
	(_GRUPO_PAI_CARE, 1, "All Item Groups"),
	("Filtro Solar", 0, _GRUPO_PAI_CARE),
	("Serum Facial", 0, _GRUPO_PAI_CARE),
	("Filtro Solar Infantil", 0, _GRUPO_PAI_CARE),
]

# Mapeamento item_group real → seção da loja.
# A chave é substring (lower) do item_group do Item no banco.
# Primeiro match vence — a ordem da lista é relevante.
_SECTION_MAP: list[tuple[str, str]] = [
	# Item 2b: "Pacotes" -> "Planos". Mantida a keyword "pacote" (itens reais
	# cujo item_group ainda contém essa palavra continuam mapeando certo) +
	# nova keyword "plano" (para item_group já cadastrado com o nome novo).
	("pacote", "Planos"),
	("plano", "Planos"),
	("vacina", "Vacinas"),
	("vitamina", "Vitaminas Injetáveis"),
	("terapia injetável", "Terapias Injetáveis"),
	("terapia", "Terapias Injetáveis"),
	("consulta", "Consultas Médicas"),
	("médico", "Consultas Médicas"),
	("exame", "Exames"),
	("vale", "Vale-Presente"),
	("brinco", "Brincos"),
	("filtro solar infantil", "Filtro Solar Infantil"),
	("filtro solar", "Filtro Solar"),
	("sérum facial", "Serum Facial"),
	("serum facial", "Serum Facial"),
]

# Copy (SEO) de cada categoria — usada como Item Group.description (aparece na
# página nativa da categoria, templates/generators/item_group.html, e é
# reaproveitada por landing.setup como fallback de meta description da rota).
# Só é gravada se o campo ainda estiver vazio (não sobrescreve edição manual).
_GROUP_COPY: dict[str, str] = {
	"Vacinas": (
		"Clínica de vacinas particulares e clínica de imunização em Uberlândia. Vacinação "
		"para bebês, crianças, adolescentes, adultos e idosos — vacina da gripe, vacina do "
		"HPV (preço e idade sob consulta), febre amarela, dengue (Qdenga) e mais, com "
		"aplicação por profissional de saúde habilitado. Consulte preços de vacinas "
		"particulares e disponibilidade de vacina a domicílio."
	),
	"Vitaminas Injetáveis": (
		"Aplicação intramuscular de vitaminas e complexos vitamínicos, mediante avaliação "
		"de um profissional de saúde. Reposição pontual conforme indicação clínica."
	),
	"Terapias Injetáveis": (
		"Aplicação de terapias injetáveis sob prescrição e acompanhamento médico."
	),
	"Consultas Médicas": (
		"Agende consultas médicas na Imunocare, com horários online e atendimento "
		"presencial na clínica."
	),
	"Vale-Presente": ("Vale-presente Imunocare para vacinas, vitaminas e serviços da clínica."),
	"Brincos": (
		"Aplicação de brincos (piercing de orelha) infantil e adulto, com material "
		"esterilizado e procedimento seguro."
	),
	# Item 2b: "Pacotes" -> "Planos" (chave renomeada; copy ajustada mantendo
	# "pacote(s)" como sinônimo, para não perder correspondência de busca).
	"Planos": (
		"Planos Imunocare — pacotes fechados de doses de vacina com condição especial, "
		"ideais para completar o esquema vacinal recomendado."
	),
	"Exames": (
		"Agende exames na Imunocare, com coleta/realização presencial na clínica e "
		"orientação de profissional de saúde habilitado."
	),
	# Linha Care (F7) — copy SEO para as categorias ainda sem produto.
	"Cuidado Pessoal": (
		"Linha Care Imunocare: cuidado pessoal para o dia a dia, com a mesma confiança da "
		"Linha Imuno. Filtro solar, sérum facial e filtro solar infantil — em breve."
	),
	"Filtro Solar": ("Filtro solar Imunocare para proteção diária da pele — em breve na loja."),
	"Serum Facial": ("Sérum facial Imunocare para cuidado da pele — em breve na loja."),
	"Filtro Solar Infantil": (
		"Filtro solar infantil Imunocare, formulado para a pele sensível das crianças — em "
		"breve na loja."
	),
}

_LOG_TITLE = "imunocare_ecommerce.catalogo.setup"

# F9 (regra inegociável — ver relatório do dev-ecommerce, risco crítico):
# medicamento nunca é vendido online, em NENHUMA página do site. O item
# "Terapia Injetável — Controle de Peso" (ex-"ter-tirzepatida", renomeado por
# compliance em catalogo.importar_prod) chegou a esta atividade JÁ
# publicado no checkout direto (add-to-cart/pagar online, sem gate de
# avaliação médica) — despublicamos aqui como correção de segurança. O
# canal correto para esse interesse é a landing "Protocolo de Emagrecimento"
# (F9, CTA único "Agende sua avaliação médica"), fora do catálogo de
# produtos. Item permanece elegível a NF/faturamento manual pela recepção
# (não desabilitado no ERP, só tirado do checkout self-service da loja).
_ITEM_CODES_EXCLUIR_LOJA_DIRETA: set[str] = {
	"ter-terapia-injetavel-para-controle-de-peso",
}


# ---------------------------------------------------------------------------
# Entry-point público
# ---------------------------------------------------------------------------


def setup_catalogo() -> None:
	"""Entry-point idempotente: cria Item Groups e publica Website Items.

	Registrado nos hooks after_install e after_migrate.
	Falhas não interrompem o migrate — são registradas em frappe.log_error.
	"""
	try:
		_setup_item_groups()
		if frappe.db.exists("DocType", "Website Item"):
			_publish_website_items()
		else:
			frappe.logger(_LOG_TITLE).warning(
				"webshop ainda não instalado — Website Items não foram criados. "
				"Execute bench migrate após: bench --site <site> install-app webshop"
			)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
	finally:
		frappe.clear_cache()


# ---------------------------------------------------------------------------
# Item Groups
# ---------------------------------------------------------------------------


def _setup_item_groups() -> None:
	"""Garante a existência dos Item Groups das duas linhas da loja — Imuno
	(``_ITEM_GROUPS``) e Care (``_ITEM_GROUPS_CARE``, F7) — idempotente."""
	if not frappe.db.exists("DocType", "Item Group"):
		return  # ERPNext não instalado; improvável em produção
	_migrar_pacotes_para_planos()
	for name, is_group, parent in _ITEM_GROUPS:
		_ensure_item_group(name, is_group, parent)
	for name, is_group, parent in _ITEM_GROUPS_CARE:
		_ensure_item_group(name, is_group, parent)


def _migrar_pacotes_para_planos() -> None:
	"""Item 2b (2026-08-10): rename real do Item Group "Pacotes" -> "Planos"
	— seguro porque a loja ainda não está em produção (trocar a rota pública
	não quebra link externo/Google Ads em produção).

	``frappe.rename_doc`` já cuida de atualizar o docname, o campo
	``item_group_name`` (autoname ``field:item_group_name``) e todo Link
	("Item.item_group", "Website Item Group.item_group" etc. — cascata
	nativa do framework). O que ele NÃO faz sozinho é recalcular a ROTA do
	webshop: ``WebshopItemGroup.make_route()`` (apps/webshop, upstream, não
	tocado) só preenche ``self.route`` se estiver vazio — então, sem ação
	extra, a categoria continuaria respondendo em
	"/loja-imunocare/pacotes" em vez de "/planos". Por isso, no caminho de
	rename simples, limpamos ``route`` e salvamos de novo para a rota nativa
	ser recalculada a partir do novo nome.

	IMPORTANTE (2026-08-11): usa ``force=True`` e NÃO ``ignore_permissions``.
	O wrapper público ``frappe.rename_doc`` (frappe/__init__.py) NÃO expõe o
	kwarg ``ignore_permissions`` (só a função interna
	``frappe.model.rename_doc.rename_doc`` tem) — passá-lo levanta
	``TypeError``, que o try/except abaixo engolia silenciosamente (foi o que
	deixou "Pacotes" intacto e criou um "Planos" vazio ao lado, no 1º migrate
	desta feature). Em ``after_migrate`` o usuário é Administrator, então
	``force=True`` já basta para permissão.

	Auto-recuperação: se um "Planos" já existir (instalação nova que nasce
	com o nome certo via ``_ITEM_GROUPS``, OU o "Planos vazio" órfão criado
	pela tentativa que falhou), consolida "Pacotes" nele com ``merge=True``
	(move item/links e apaga "Pacotes"); senão, faz o rename simples +
	recálculo de rota. Idempotente: se "Pacotes" não existe, é no-op."""
	if not frappe.db.exists("Item Group", "Pacotes"):
		return
	try:
		if frappe.db.exists("Item Group", "Planos"):
			# "Planos" já existe -> mescla "Pacotes" nele (move o(s) item(ns) e
			# atualiza os Links; "Pacotes" é apagado). A rota de "Planos" já é
			# a correta (/loja-imunocare/planos), não precisa recalcular.
			frappe.rename_doc("Item Group", "Pacotes", "Planos", merge=True, force=True)
		else:
			frappe.rename_doc("Item Group", "Pacotes", "Planos", force=True)
			doc = frappe.get_doc("Item Group", "Planos")
			if doc.route:
				doc.route = None
				doc.flags.ignore_permissions = True
				doc.save(ignore_permissions=True)
		frappe.logger(_LOG_TITLE).info(
			"Item Group 'Pacotes' migrado para 'Planos' (item 2b)."
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)


def ensure_item_groups() -> None:
	"""Wrapper público de ``_setup_item_groups`` — usado por
	``catalogo.importar_prod`` para garantir que os Item Groups da loja
	(inclusive "Planos") já existam ANTES de criar os Items reais."""
	_setup_item_groups()


def _ensure_item_group(name: str, is_group: int, parent: str) -> None:
	"""Cria o Item Group se não existir; se já existir, garante show_in_website=1
	e a description (copy) da categoria — sem alterar o parent_item_group.

	Se já existir (ex: "Vacinas" criado pelo imunocare_clinic_ext), preserva o
	parent_item_group original para não quebrar a hierarquia de estoque já
	configurada — só liga a visibilidade no site e completa a description.

	O campo show_in_website é um Custom Field adicionado pelo webshop. Só é
	definido se o webshop já estiver instalado (idem para "description", que
	também é Custom Field do webshop).
	"""
	tem_show_in_website = frappe.db.exists(
		"Custom Field", {"dt": "Item Group", "fieldname": "show_in_website"}
	)
	tem_description = frappe.db.exists("Custom Field", {"dt": "Item Group", "fieldname": "description"})
	copy = _GROUP_COPY.get(name)

	if frappe.db.exists("Item Group", name):
		doc = frappe.get_doc("Item Group", name)
		mudou = False
		if tem_show_in_website and not doc.get("show_in_website"):
			doc.show_in_website = 1
			mudou = True
		# F2 (validação): "Vacinas" já tinha description antes da cobertura de
		# keywords desta atividade ("clínica de imunização"/"vacina a
		# domicílio"/"preços") — força a atualização 1x só para esse grupo,
		# preservando a regra normal (só preenche vazio) para os demais.
		forcar_descricao = name == "Vacinas"
		if tem_description and copy and (not doc.get("description") or forcar_descricao):
			doc.description = copy
			mudou = True
		if mudou:
			doc.flags.ignore_permissions = True
			doc.save(ignore_permissions=True)
		return

	doc_data: dict = {
		"doctype": "Item Group",
		"item_group_name": name,
		"is_group": is_group,
		"parent_item_group": parent,
	}

	if tem_show_in_website:
		doc_data["show_in_website"] = 1
	if tem_description and copy:
		doc_data["description"] = copy

	frappe.get_doc(doc_data).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Website Items — publicação no catálogo
# ---------------------------------------------------------------------------


def _publish_website_items() -> None:
	"""Cria/atualiza Website Items para os Items de serviço existentes.

	Critério de elegibilidade:
	  - disabled = 0
	  - is_stock_item = 0  → item de serviço/aplicação (não insumo físico)
	  - is_sales_item = 1  → faturável ao cliente

	Esses são os itens de "Aplicação - [Vacina]" criados automaticamente pelo
	Healthcare Therapy Type. Os insumos físicos (estoque) são excluídos — eles
	controlam o estoque interno e não devem aparecer na loja pública.

	Para cada item elegível, a seção da loja é inferida pelo item_group via
	_resolve_section(). Items sem match em _SECTION_MAP são ignorados.
	"""
	if not frappe.db.exists("DocType", "Item"):
		return

	items = frappe.get_all(
		"Item",
		filters={
			"disabled": 0,
			"is_stock_item": 0,
			"is_sales_item": 1,
		},
		fields=["name", "item_code", "item_name", "item_group", "description"],
	)

	publicados = 0
	ignorados = 0
	excluidos = 0

	for item in items:
		if item.item_code in _ITEM_CODES_EXCLUIR_LOJA_DIRETA:
			_despublicar_se_necessario(item.item_code)
			excluidos += 1
			continue
		section = _resolve_section(item.item_group)
		if not section:
			ignorados += 1
			continue
		_upsert_website_item(item, section)
		publicados += 1

	frappe.logger(_LOG_TITLE).info(
		f"setup_catalogo: {publicados} Website Item(s) publicados, "
		f"{ignorados} Item(s) ignorados (sem mapeamento de seção), "
		f"{excluidos} excluído(s) do checkout direto (F9 — compliance)."
	)


def _despublicar_se_necessario(item_code: str) -> None:
	"""Garante published=0 para itens na lista de exclusão de checkout direto
	(F9), mesmo que uma execução anterior já os tenha publicado."""
	existente = frappe.db.get_value("Website Item", {"item_code": item_code}, ["name", "published"])
	if not existente:
		return
	name, published = existente
	if published:
		frappe.db.set_value("Website Item", name, "published", 0, update_modified=False)
		frappe.logger(_LOG_TITLE).info(
			f"Website Item '{name}' ({item_code}) despublicado (F9 — sem checkout direto)."
		)


def _resolve_section(item_group: str) -> str | None:
	"""Retorna a seção da loja para um dado item_group, ou None se não mapeado."""
	if not item_group:
		return None
	ig_lower = item_group.lower()
	for keyword, section in _SECTION_MAP:
		if keyword in ig_lower:
			return section
	return None


def _upsert_website_item(item: "frappe._dict", section: str) -> None:
	"""Cria ou atualiza o Website Item vinculado ao Item.

	Preserva customizações manuais: web_item_name e short_description só são
	preenchidos automaticamente se ainda estiverem em branco.
	"""
	existing_name: str | None = frappe.db.get_value(
		"Website Item", {"item_code": item.item_code}, "name"
	)

	if existing_name:
		doc = frappe.get_doc("Website Item", existing_name)
	else:
		doc = frappe.new_doc("Website Item")
		doc.item_code = item.item_code

	doc.published = 1

	# Preenche web_item_name só se vazio (permite renomear manualmente depois)
	if not doc.web_item_name:
		doc.web_item_name = item.item_name

	# short_description: texto plano (sem HTML), máx 140 chars
	if not doc.short_description and item.description:
		plain = re.sub(r"<[^>]+>", "", item.description or "").strip()
		doc.short_description = plain[:140] if plain else ""

	# Garante que a seção correta esteja em website_item_groups
	_ensure_website_item_section(doc, section)

	doc.save(ignore_permissions=True)


def _ensure_website_item_section(doc: "frappe.Document", section: str) -> None:
	"""Adiciona a seção ao website_item_groups se ainda não estiver presente.

	website_item_groups permite que um Website Item apareça em múltiplas
	categorias do webshop. A seção principal (item_group) do Website Item é
	read-only (fetched de Item.item_group), então usamos website_item_groups
	para vincular à categoria de navegação da loja.
	"""
	existing = {row.item_group for row in (doc.get("website_item_groups") or [])}
	if section not in existing:
		doc.append("website_item_groups", {"item_group": section})


# ---------------------------------------------------------------------------
# Leitura para a Home (www/index.py) — só consulta, não escreve nada.
# ---------------------------------------------------------------------------

# Ordem de exibição das seções na home. Seções sem nenhum Website Item
# publicado são omitidas silenciosamente (ex.: Consultas Médicas nesta 1ª
# versão, sem itens ainda cadastrados).
#
# Item 2a (2026-08-10): "Exames" e "Vale-Presente" tirados da home/nav "nesse
# momento", a pedido do dono — remoção SÓ DE EXIBIÇÃO e REVERSÍVEL (os Item
# Groups continuam existindo no banco, ``_ITEM_GROUPS`` acima não foi
# alterado; basta devolver os dois nomes a estas listas para reaparecerem).
SECOES_HOME_ORDEM: list[str] = [
	"Vacinas",
	"Vitaminas Injetáveis",
	"Terapias Injetáveis",
	"Planos",
	"Brincos",
	"Consultas Médicas",
	# Linha Care (F7):
	"Filtro Solar",
	"Serum Facial",
	"Filtro Solar Infantil",
]

# Ordem de navegação (F7 — nav com TODAS as categorias, mesmo vazias).
# Item 2a: "Exames"/"Vale-Presente" removidos daqui também (ver comentário
# acima de SECOES_HOME_ORDEM — mesma regra, mesma reversibilidade).
_NAV_ORDEM_IMUNO: list[str] = [
	"Vacinas",
	"Vitaminas Injetáveis",
	"Terapias Injetáveis",
	"Planos",
	"Consultas Médicas",
	"Brincos",
]
_NAV_ORDEM_CARE: list[str] = ["Filtro Solar", "Serum Facial", "Filtro Solar Infantil"]


def secoes_para_home(limite_por_secao: int = 4) -> list[dict]:
	"""Seções da loja com Website Items publicados, para a home (Feature 55).

	Cada seção: {"nome", "route" (do Item Group), "itens": [{"nome","route",
	"preco" (float ou None), "imagem", "descricao" (short_description, para o
	card do layout aprovado — ajuste 2026-07)]}. Seções sem item publicado
	são omitidas. Não lança exceção — usada em request de página pública.
	"""
	if not frappe.db.exists("DocType", "Website Item"):
		return []

	price_list = frappe.db.get_single_value("Webshop Settings", "price_list") or "Venda Padrão"
	secoes: list[dict] = []

	for nome_secao in SECOES_HOME_ORDEM:
		item_groups = frappe.get_all(
			"Website Item Group",
			filters={"item_group": nome_secao, "parenttype": "Website Item"},
			pluck="parent",
		)
		if not item_groups:
			continue

		website_items = frappe.get_all(
			"Website Item",
			filters={"name": ["in", item_groups], "published": 1},
			fields=[
				"name",
				"item_code",
				"web_item_name",
				"route",
				"website_image",
				"thumbnail",
				"short_description",
			],
			# Vitrine da home: itens COM foto primeiro (as vacinas fotografadas
			# do lote 2026-08-09), depois alfabético — para a prévia de 4 cards
			# não cair só nos itens sem imagem (que renderizam o ícone SVG).
			# ``website_image desc`` = strings não-vazias antes de NULL/'' no
			# MariaDB (NULLs por último em DESC); seções sem nenhuma foto
			# (Vitaminas/Planos/Brincos) empatam e caem no ``web_item_name``.
			# (order_by só aceita "campo [asc|desc]" — CASE é barrado pelo
			# sanitizador do frappe.get_all como "Consulta SQL ilegal".)
			order_by="website_image desc, web_item_name asc",
			limit_page_length=limite_por_secao,
		)
		if not website_items:
			continue

		precos = {}
		if website_items:
			codigos = [wi.item_code for wi in website_items]
			for row in frappe.get_all(
				"Item Price",
				filters={"item_code": ["in", codigos], "price_list": price_list, "selling": 1},
				fields=["item_code", "price_list_rate"],
			):
				precos[row.item_code] = row.price_list_rate

		route = frappe.db.get_value("Item Group", nome_secao, "route")
		itens = [
			{
				"nome": wi.web_item_name or wi.item_code,
				"route": wi.route,
				"preco": precos.get(wi.item_code),
				"imagem": wi.website_image or wi.thumbnail,
				"descricao": wi.short_description,
			}
			for wi in website_items
		]
		secoes.append({"nome": nome_secao, "route": route, "itens": itens})

	return secoes


def nav_categorias(grupo_pai: str) -> list[dict]:
	"""Categorias da linha Imuno ("Loja Imunocare") ou Care ("Cuidado
	Pessoal") para a navegação da home (F7) — TODAS, mesmo as sem produto
	publicado ainda (essas caem na página de categoria informativa, ver
	templates/generators/item_group.html). Cada item: {"nome", "route"}.

	Consulta por NOME (``_NAV_ORDEM_IMUNO``/``_NAV_ORDEM_CARE``), não por
	``parent_item_group`` — "Vacinas" pode ter sido criado antes deste app
	(pelo imunocare_clinic_ext/seed) com parent "All Item Groups" em vez de
	"Loja Imunocare" (ver ``_ensure_item_group``, que preserva o parent
	original); filtrar por parent perderia essa categoria da navegação.
	Não lança exceção — usada em request de página pública.
	"""
	if not frappe.db.exists("DocType", "Item Group"):
		return []

	ordem = _NAV_ORDEM_IMUNO if grupo_pai == _GRUPO_PAI else _NAV_ORDEM_CARE if grupo_pai == _GRUPO_PAI_CARE else []
	if not ordem:
		return []

	grupos = frappe.get_all(
		"Item Group", filters={"name": ["in", ordem]}, fields=["item_group_name", "route"]
	)
	por_nome = {g.item_group_name: g.route for g in grupos}

	return [
		{"nome": nome, "route": por_nome[nome]}
		for nome in ordem
		if por_nome.get(nome)
	]


def nav_categorias_loja() -> list[dict]:
	"""Wrapper público de ``nav_categorias(_GRUPO_PAI)`` — Linha Imuno (as
	mesmas categorias/ordem da nav da home, já sem Exames/Vale-Presente —
	item 2a). Usado por ``catalogo.api.categorias_nav`` (item 4 — barra de
	chips de categoria nas páginas de listagem do webshop) para não expor o
	nome do grupo-pai fora deste módulo nem duplicar a lista de categorias."""
	return nav_categorias(_GRUPO_PAI)
