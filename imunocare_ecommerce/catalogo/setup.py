"""Configuração do catálogo web da loja Imunocare — taxonomia 2026-09-04
(spec ``docs/specs/2026-09-04-redesign-loja-identidade-oficial.md``): 7
categorias de topo + "Planos" como subcategoria de "Vacinas".

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
          │     └── Planos  (subcategoria — taxonomia 2026-09-04)
          ├── Vitaminas          (era "Vitaminas Injetáveis" — rename)
          ├── Terapias Injetáveis
          ├── Consultas          (era "Consultas Médicas" — rename)
          ├── Nutracêuticos      (novo, nasce vazio)
          ├── Cuidado diário     (novo, nasce vazio; consolida a antiga
          │                       Linha Care — Filtro Solar/Serum Facial/
          │                       Filtro Solar Infantil, ver
          │                       ``_consolidar_linha_care``)
          ├── Vale-Presente      (fora da nav de topo — item 2a)
          ├── Brincos
          └── Exames             (fora da nav de topo — item 2a)

ATENÇÃO — "Vacinas" pode já existir (criado pelo imunocare_clinic_ext / seed):
  - Se NÃO existe → cria sob "Loja Imunocare" (ideal para navegação).
  - Se JÁ existe  → mantém o parent original; o operador pode reparentar
    manualmente para "Loja Imunocare" via Stock > Item Group se desejar.
  Os demais grupos são criados sob "Loja Imunocare" (exceto "Planos", cujo
  parent é "Vacinas" — ver ``_mover_planos_para_vacinas``).

Mapeamento Item → seção:
  Apenas Items de serviço (is_stock_item=0, is_sales_item=1) são publicados.
  O item_group do Item é comparado (substring, case-insensitive) com as
  palavras-chave definidas em _SECTION_MAP.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

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

# Linha Care (F7, DESCONTINUADA pela taxonomia 2026-09-04 — ver
# ``_consolidar_linha_care``): a separação "Imuno x Care" em duas linhas de
# navegação virou UMA lista flat de 7 categorias (spec 2026-09-04, "não
# fatiar o que é o mesmo caso" — todas são categoria de topo da MESMA loja).
# Constante mantida só para a função de consolidação achar os nomes antigos.
_GRUPO_PAI_CARE = "Cuidado Pessoal"

# Ordem importa: o pai deve ser criado antes dos filhos.
# Taxonomia 2026-09-04 (spec ``docs/specs/2026-09-04-redesign-loja-
# identidade-oficial.md`` — decisão do dono): 7 categorias de topo —
# Vacinas/Vitaminas/Terapias Injetáveis/Consultas/Nutracêuticos (novo)/
# Cuidado diário (novo)/Brincos. "Vitaminas Injetáveis"->"Vitaminas" e
# "Consultas Médicas"->"Consultas" são RENAMES reais (ver
# ``_renomear_categorias_2026_09``); "Planos" deixa de ser categoria de topo
# e vira filho de "Vacinas" (ver ``_mover_planos_para_vacinas``).
_ITEM_GROUPS: list[tuple[str, int, str]] = [
	(_GRUPO_PAI, 1, "All Item Groups"),
	("Vacinas", 0, _GRUPO_PAI),
	("Vitaminas", 0, _GRUPO_PAI),
	("Terapias Injetáveis", 0, _GRUPO_PAI),
	("Consultas", 0, _GRUPO_PAI),
	# Nutracêuticos/Cuidado diário (NOVOS — taxonomia 2026-09-04): nascem
	# vazios, com o mesmo tratamento de "categoria sem produto ainda" já
	# usado por Consultas/Exames/Terapias (ver catalogo.jinja_utils).
	("Nutracêuticos", 0, _GRUPO_PAI),
	("Cuidado diário", 0, _GRUPO_PAI),
	("Vale-Presente", 0, _GRUPO_PAI),
	("Brincos", 0, _GRUPO_PAI),
	# Planos: parent real é "Vacinas" (reparentado por
	# ``_mover_planos_para_vacinas`` quando o registro já existir com o
	# parent antigo — ``_ensure_item_group`` preserva parent em registro
	# existente, então a criação normal só vale para instalação NOVA).
	("Planos", 0, "Vacinas"),
	# Exames (F7): novo, sem item hoje — página informativa (ver
	# templates/generators/item_group.html + catalogo.jinja_utils).
	("Exames", 0, _GRUPO_PAI),
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
	("vitamina", "Vitaminas"),
	("terapia injetável", "Terapias Injetáveis"),
	("terapia", "Terapias Injetáveis"),
	("consulta", "Consultas"),
	("médico", "Consultas"),
	("exame", "Exames"),
	("vale", "Vale-Presente"),
	("brinco", "Brincos"),
	# Taxonomia 2026-09-04: as 3 categorias antigas da Linha Care (filtro
	# solar/sérum facial) consolidam em UMA categoria só, "Cuidado diário"
	# (nome escolhido para não soar "cosmético" — spec 2026-09-04).
	("filtro solar infantil", "Cuidado diário"),
	("filtro solar", "Cuidado diário"),
	("sérum facial", "Cuidado diário"),
	("serum facial", "Cuidado diário"),
	("repelente", "Cuidado diário"),
	("nutracêutico", "Nutracêuticos"),
	("nutraceutico", "Nutracêuticos"),
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
	# Taxonomia 2026-09-04: "Vitaminas Injetáveis" -> "Vitaminas" (rename).
	"Vitaminas": (
		"Aplicação intramuscular de vitaminas e complexos vitamínicos, mediante avaliação "
		"de um profissional de saúde. Reposição pontual conforme indicação clínica."
	),
	"Terapias Injetáveis": (
		"Aplicação de terapias injetáveis sob prescrição e acompanhamento médico."
	),
	# Taxonomia 2026-09-04: "Consultas Médicas" -> "Consultas" (rename).
	"Consultas": (
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
	# Taxonomia 2026-09-04: "Planos" virou subcategoria de "Vacinas" — copy
	# mantida (ainda é a mesma categoria de produto, só mudou de posição na
	# árvore de navegação).
	"Planos": (
		"Planos Imunocare — pacotes fechados de doses de vacina com condição especial, "
		"ideais para completar o esquema vacinal recomendado."
	),
	"Exames": (
		"Agende exames na Imunocare, com coleta/realização presencial na clínica e "
		"orientação de profissional de saúde habilitado."
	),
	# Taxonomia 2026-09-04 (NOVAS categorias, nascem vazias — estado "em
	# breve" via catalogo.jinja_utils._INFO_CATEGORIA_VAZIA):
	"Nutracêuticos": (
		"Nutracêuticos Imunocare: suplementação oral com curadoria de profissional de "
		"saúde — em breve na loja."
	),
	"Cuidado diário": (
		"Cuidado diário Imunocare: filtro solar, repelente e produtos para a saúde da "
		"pele no dia a dia — em breve na loja."
	),
	# Linha Care (F7, DESCONTINUADA — consolidada em "Cuidado diário" acima).
	# Copy mantida só por histórico/SEO residual enquanto as rotas antigas
	# não forem removidas (ver ``_consolidar_linha_care`` — grupos ficam
	# com show_in_website=0, não aparecem mais na loja).
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
	"""Garante a existência/taxonomia dos 7 Item Groups de topo da loja
	(``_ITEM_GROUPS``, taxonomia 2026-09-04) — idempotente."""
	if not frappe.db.exists("DocType", "Item Group"):
		return  # ERPNext não instalado; improvável em produção
	_migrar_pacotes_para_planos()
	_renomear_categorias_2026_09()
	# ANTES do loop de _ITEM_GROUPS: "Vacinas" ganha uma subcategoria
	# ("Planos") na taxonomia 2026-09-04 — se ainda for folha (``is_group=0``,
	# caso real do ambiente: criado pelo imunocare_clinic_ext/seed antes de
	# qualquer subcategoria existir), o PRÓPRIO re-save de "Vacinas" dentro do
	# loop abaixo (``_ensure_item_group`` força a description 1x, ver
	# ``forcar_descricao``) já dispararia o ValidationError do NestedSet
	# ("cannot be a leaf node as it has children") assim que "Planos" for
	# reparentado — por isso a promoção acontece AQUI, antes de qualquer
	# save de "Vacinas" ou "Planos" nesta execução (achado em teste local).
	_garantir_vacinas_e_grupo()
	for name, is_group, parent in _ITEM_GROUPS:
		_ensure_item_group(name, is_group, parent)
	_mover_planos_para_vacinas()
	_consolidar_linha_care()


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


# Taxonomia 2026-09-04: renomes reais (mesmo padrão de
# ``_migrar_pacotes_para_planos`` — ``frappe.rename_doc(force=True)``, NUNCA
# ``ignore_permissions`` no wrapper público, ver aviso ali). ``old -> new``.
_RENOMES_2026_09: list[tuple[str, str]] = [
	("Vitaminas Injetáveis", "Vitaminas"),
	("Consultas Médicas", "Consultas"),
]


def _renomear_categorias_2026_09() -> None:
	"""Taxonomia 2026-09-04 (spec ``docs/specs/2026-09-04-redesign-loja-
	identidade-oficial.md``): "Vitaminas Injetáveis" -> "Vitaminas" e
	"Consultas Médicas" -> "Consultas" — nomear pela categoria como o dono
	decidiu exibir na nav, não pelo rótulo técnico anterior.

	Mesma receita de ``_migrar_pacotes_para_planos`` (rename real via
	``frappe.rename_doc``, que já cascade-atualiza ``Item.item_group``,
	``Website Item Group.item_group`` etc.) + reset de ``route`` para o
	webshop recalcular a partir do nome novo (``WebshopItemGroup.make_route``
	só preenche rota vazia). Idempotente: se o nome ANTIGO não existir mais,
	é no-op; se o nome NOVO já existir (rename já aplicado, ou instalação
	nova que nasceu direto com o nome certo via ``_ITEM_GROUPS``), também
	não faz nada — nunca mescla/duplica."""
	for antigo, novo in _RENOMES_2026_09:
		if not frappe.db.exists("Item Group", antigo) or frappe.db.exists("Item Group", novo):
			continue
		try:
			frappe.rename_doc("Item Group", antigo, novo, force=True)
			doc = frappe.get_doc("Item Group", novo)
			if doc.route:
				doc.route = None
				doc.flags.ignore_permissions = True
				doc.save(ignore_permissions=True)
			frappe.logger(_LOG_TITLE).info(
				f"Item Group '{antigo}' renomeado para '{novo}' (taxonomia 2026-09-04)."
			)
		except Exception:
			frappe.log_error(frappe.get_traceback(), _LOG_TITLE)


def _garantir_vacinas_e_grupo() -> None:
	"""Taxonomia 2026-09-04: "Vacinas" passa a ter uma subcategoria
	("Planos") — precisa ser ``is_group=1`` (grupo), nunca folha.

	IMPORTANTE (achado em teste local 2026-09-04, não hipotético): "Vacinas"
	no ambiente real nasceu FOLHA (``is_group=0``, criado pelo
	``imunocare_clinic_ext``/seed, antes de qualquer subcategoria existir).
	O ``NestedSet`` nativo do Frappe rejeita salvar um Item Group folha que
	tenha filho ("... cannot be a leaf node as it has children") — e
	``_ensure_item_group`` (chamada logo depois, no loop de ``_ITEM_GROUPS``)
	sempre resalva "Vacinas" (força a description 1x, ver
	``forcar_descricao``), então a promoção a grupo tem que acontecer AQUI,
	ANTES do loop — depois é tarde: o próprio resave de "Vacinas" já explode.

	Idempotente: só salva se ``is_group`` ainda for 0. Nunca lança (chamada
	no meio do after_migrate)."""
	if not frappe.db.exists("Item Group", "Vacinas"):
		return
	try:
		doc = frappe.get_doc("Item Group", "Vacinas")
		if doc.is_group:
			return
		doc.is_group = 1
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
		frappe.logger(_LOG_TITLE).info(
			"Item Group 'Vacinas' virou grupo (is_group=1) para receber 'Planos' como subcategoria."
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)


def _mover_planos_para_vacinas() -> None:
	"""Taxonomia 2026-09-04: "Planos" deixa de ser categoria de topo da loja
	e vira SUBCATEGORIA (filho) de "Vacinas" — decisão do dono (planos são,
	na prática, um jeito de comprar um conjunto de doses de vacina).

	``_ensure_item_group`` (chamada antes, no loop de ``_ITEM_GROUPS``)
	preserva o ``parent_item_group`` de um registro JÁ EXISTENTE de propósito
	(não sobrescreve hierarquia de estoque manual) — por isso, para um
	"Planos" que já exista com o parent antigo ("Loja Imunocare"), o
	reparenting explícito é feito aqui, uma única vez. Idempotente: se
	"Planos" já tem parent "Vacinas" (instalação nova, ou já migrado), é
	no-op. Reseta ``route`` para o webshop recalcular sob "vacinas/planos"
	(mesma técnica do rename). Pressupõe que ``_garantir_vacinas_e_grupo``
	já rodou (chamada ANTES do loop de ``_ITEM_GROUPS``, ver
	``_setup_item_groups``) — "Vacinas" já é grupo quando chegamos aqui."""
	if not frappe.db.exists("Item Group", "Planos") or not frappe.db.exists("Item Group", "Vacinas"):
		return
	doc = frappe.get_doc("Item Group", "Planos")
	if doc.parent_item_group == "Vacinas":
		return
	try:
		doc.parent_item_group = "Vacinas"
		doc.route = None
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
		frappe.logger(_LOG_TITLE).info(
			"Item Group 'Planos' reparentado para 'Vacinas' (taxonomia 2026-09-04 — sai da nav de topo)."
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)


# Taxonomia 2026-09-04: nomes da Linha Care descontinuada (consolidada em
# "Cuidado diário" — ver ``_SECTION_MAP``/``_GROUP_COPY`` acima).
_LINHA_CARE_DESCONTINUADA: tuple[str, ...] = (
	_GRUPO_PAI_CARE,
	"Filtro Solar",
	"Serum Facial",
	"Filtro Solar Infantil",
)


def _consolidar_linha_care() -> None:
	"""Taxonomia 2026-09-04: a Linha Care (2 linhas de nav Imuno x Care, F7)
	vira UMA lista flat de 7 categorias — "Filtro Solar"/"Serum Facial"/
	"Filtro Solar Infantil" (0 produtos publicados até hoje, confirmado no
	catálogo curado) consolidam em uma categoria só, "Cuidado diário"
	(``_ITEM_GROUPS`` acima).

	Reversível por design (doutrina do projeto): NÃO apaga/renomeia os
	grupos antigos (evita perder histórico/qualquer link externo já
	indexado) — só desliga ``show_in_website`` (custom field do webshop),
	tirando-os da navegação/sitemap público. Reaparecem instantaneamente se
	um operador marcar ``show_in_website=1`` de novo pelo Desk; o próximo
	migrate não desfaz (só desliga quem estiver ligado, nunca liga)."""
	tem_show_in_website = frappe.db.exists(
		"Custom Field", {"dt": "Item Group", "fieldname": "show_in_website"}
	)
	if not tem_show_in_website:
		return
	for nome in _LINHA_CARE_DESCONTINUADA:
		if not frappe.db.exists("Item Group", nome):
			continue
		if not frappe.db.get_value("Item Group", nome, "show_in_website"):
			continue
		try:
			frappe.db.set_value("Item Group", nome, "show_in_website", 0, update_modified=False)
			frappe.logger(_LOG_TITLE).info(
				f"Item Group '{nome}' tirado da navegação pública (Linha Care consolidada em 'Cuidado diário')."
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


_ARQUIVO_LOJA = Path(__file__).parent / "catalogo_loja.json"


def _carregar_mapa_loja() -> dict:
	"""Carrega ``catalogo_loja.json`` -> dict ``{item_name: entrada}``.

	CATÁLOGO CURADO da loja (2026-08-11), SEM preços (seguro versionar). Cada
	entrada tem ``item_names`` (1+ variações do nome que identificam o MESMO
	produto), ``web_name`` (nome de vitrine), ``secao`` (categoria da loja) e
	``foto`` (slug do arquivo em ``public/img/produtos/<slug>.jpg``).

	Por que múltiplos nomes por produto: dev e PROD divergem no ``item_code``
    E no ``item_name`` do mesmo produto (dev usa o nome de loja como
	``item_name``; prod usa o nome clínico "Aplicação Vacina X"). Casar por
	``item_name`` cobrindo AMBAS as grafias liga o produto certo à sua seção/
	nome/foto nos dois ambientes, sem depender do ``item_code``."""
	try:
		with open(_ARQUIVO_LOJA, encoding="utf-8") as f:
			dados = json.load(f)
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return {}
	mapa: dict = {}
	for entrada in dados:
		for nome in entrada.get("item_names", []):
			mapa[nome] = entrada
	return mapa


def _publish_website_items() -> None:
	"""Publica APENAS os produtos do catálogo curado (``catalogo_loja.json``),
	casando pelo ``item_name`` do Item (elegível: is_sales_item=1,
	is_stock_item=0, disabled=0).

	Curado por design (2026-08-11 — go-live prod): antes a seção era inferida
	por keyword do ``item_group`` e publicava TODO item de serviço elegível —
	o que, na estrutura de PROD (tudo sob "Aplicação de Vacinas"), classificaria
	vitaminas/brincos como "Vacina" e ainda publicaria itens de teste/duplicados/
	calendários. Agora só entram os produtos do mapa, na seção correta, com o
	nome de vitrine e a foto certos — mesmo comportamento limpo em dev e prod.
	Item fora do mapa (ex.: tirzepatida — F9, itens de teste, Calendário Premium)
	simplesmente não é publicado."""
	if not frappe.db.exists("DocType", "Item"):
		return

	mapa = _carregar_mapa_loja()
	if not mapa:
		frappe.logger(_LOG_TITLE).warning("catalogo_loja.json vazio/ausente — nada publicado.")
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

	for item in items:
		entrada = mapa.get(item.item_name)
		if not entrada:
			ignorados += 1
			continue
		_upsert_website_item(item, entrada)
		publicados += 1

	frappe.logger(_LOG_TITLE).info(
		f"setup_catalogo: {publicados} Website Item(s) do catálogo curado publicados, "
		f"{ignorados} Item(s) fora do catálogo curado (não publicados)."
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


_IMG_PRODUTOS_URL = "/assets/imunocare_ecommerce/img/produtos"
_IMG_PRODUTOS_PREFIXO_GERIDO = "/assets/imunocare_ecommerce/img/"
_IMG_PRODUTOS_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def _imagem_produto(slug: str | None) -> str | None:
	"""Imagem do produto pelo SLUG do catálogo curado: se existir
	``public/img/produtos/<slug>.<ext>`` (jpg/png/jpeg/webp), retorna a URL
	``/assets`` correspondente; senão ``None``.

	O slug (campo ``foto`` de ``catalogo_loja.json``) é estável e independente
	do ``item_code`` — por isso a MESMA foto liga o produto em dev e em prod,
	que têm ``item_code`` diferentes. Trocar a foto = substituir o arquivo do
	slug; adicionar produto = novo slug no JSON + arquivo."""
	if not slug:
		return None
	try:
		base = frappe.get_app_path("imunocare_ecommerce", "public", "img", "produtos")
	except Exception:
		return None
	for ext in _IMG_PRODUTOS_EXTS:
		if os.path.exists(os.path.join(base, f"{slug}{ext}")):
			return f"{_IMG_PRODUTOS_URL}/{slug}{ext}"
	return None


def _upsert_website_item(item: "frappe._dict", entrada: dict) -> None:
	"""Cria ou atualiza o Website Item de um produto do catálogo curado.

	``entrada`` vem de ``catalogo_loja.json`` (web_name/secao/foto). O nome de
	vitrine e a seção são AUTORITATIVOS (curados) — a seção é gravada como a
	ÚNICA de ``website_item_groups`` (corrige a classificação errada quando o
	``item_group`` nativo do Item é genérico, ex.: "Aplicação de Vacinas" em
	prod). A ``short_description`` só é preenchida se vazia."""
	web_name = entrada.get("web_name") or item.item_name
	secao = entrada.get("secao")

	existing_name: str | None = frappe.db.get_value(
		"Website Item", {"item_code": item.item_code}, "name"
	)

	if existing_name:
		doc = frappe.get_doc("Website Item", existing_name)
	else:
		doc = frappe.new_doc("Website Item")
		doc.item_code = item.item_code

	doc.published = 1
	doc.web_item_name = web_name  # nome de vitrine curado (autoritativo)

	# short_description: texto plano (sem HTML), máx 140 chars — só se vazia
	if not doc.short_description and item.description:
		plain = re.sub(r"<[^>]+>", "", item.description or "").strip()
		doc.short_description = plain[:140] if plain else ""

	# Seção curada = única categoria de navegação (substitui as anteriores que
	# este módulo gerencia; evita item aparecer na seção errada).
	if secao:
		doc.set("website_item_groups", [{"item_group": secao}])

	doc.save(ignore_permissions=True)

	# Foto do produto (slug curado). Gravada DIRETO no banco DEPOIS do save: o
	# webshop (``WebsiteItem.validate_website_image``, upstream, não tocado)
	# ZERA qualquer ``website_image`` que não seja um doc File público — e um
	# asset estático ``/assets/.../img/`` não tem File associado.
	# ``frappe.db.set_value`` contorna essa validação sem tocar upstream.
	# Respeita upload manual do operador (``/files/...``); sobrescreve só quando
	# vazio ou quando é uma imagem NOSSA (``/assets/``).
	img = _imagem_produto(entrada.get("foto"))
	if img:
		atual = frappe.db.get_value("Website Item", doc.name, "website_image")
		if not atual or str(atual).startswith(_IMG_PRODUTOS_PREFIXO_GERIDO):
			frappe.db.set_value(
				"Website Item",
				doc.name,
				{"website_image": img, "thumbnail": img},
				update_modified=False,
			)


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
	"Vitaminas",
	"Terapias Injetáveis",
	"Planos",
	"Brincos",
	"Consultas",
	# Nutracêuticos/Cuidado diário (taxonomia 2026-09-04): sem produto ainda
	# — a checagem "sem item publicado -> continue" logo abaixo já as omite
	# desta lista de carrosséis com conteúdo real; mantidas aqui de propósito
	# para aparecerem automaticamente assim que o dono publicar o 1º item.
	"Nutracêuticos",
	"Cuidado diário",
]

# Ordem de navegação — taxonomia 2026-09-04: UMA lista flat com as 7
# categorias de topo (a separação Imuno x Care em duas linhas, F7, foi
# descontinuada — ver ``_consolidar_linha_care``). "Planos" NÃO entra aqui
# (saiu da nav de topo, agora é subcategoria de "Vacinas" — spec 2026-09-04).
_NAV_ORDEM_IMUNO: list[str] = [
	"Vacinas",
	"Vitaminas",
	"Terapias Injetáveis",
	"Consultas",
	"Nutracêuticos",
	"Cuidado diário",
	"Brincos",
]
# Linha Care descontinuada (taxonomia 2026-09-04) — lista vazia preserva a
# assinatura de ``nav_categorias(grupo_pai)`` (ver ``www/index.py``) sem
# quebrar quem ainda chama com "Cuidado Pessoal"; sempre retorna [].
_NAV_ORDEM_CARE: list[str] = []


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
				# REDESIGN 2026-09-04 (cards "Opção A" — protótipo): selo "Mais
				# agendada" é uma curadoria MANUAL do dono (``destaque: true``
				# em catalogo_loja.json, ver ``_mapa_destaque``) — nunca
				# inferido/fabricado aqui (nenhum dado real de "mais agendado"
				# existe nesta atividade; até o dono marcar, todo item vem
				# ``False``, sem selo nenhum).
				"destaque": _mapa_destaque().get(wi.web_item_name, False),
			}
			for wi in website_items
		]
		secoes.append({"nome": nome_secao, "route": route, "itens": itens})

	return secoes


def _mapa_destaque() -> dict[str, bool]:
	"""``{web_item_name: True}`` para os produtos curados com ``"destaque":
	true`` em ``catalogo_loja.json`` (campo opcional, ausente = ``False``).
	Reuso: mesma fonte do catálogo curado (``_carregar_mapa_loja``), nenhuma
	segunda lista de "produtos em destaque" mantida à parte."""
	return {
		entrada["web_name"]: True
		for entrada in _carregar_mapa_loja().values()
		if entrada.get("web_name") and entrada.get("destaque")
	}


def nav_categorias(grupo_pai: str) -> list[dict]:
	"""Categorias de navegação da loja (taxonomia 2026-09-04: lista flat
	única, ``_NAV_ORDEM_IMUNO``) — TODAS, mesmo as sem produto publicado
	ainda (essas caem na página de categoria informativa, ver
	templates/generators/item_group.html). Cada item: {"nome", "route"}.

	``grupo_pai="Cuidado Pessoal"`` (linha Care, F7) sempre devolve ``[]`` —
	descontinuada, consolidada em "Cuidado diário" na lista flat (ver
	``_consolidar_linha_care``). Parâmetro mantido só por compatibilidade de
	assinatura com quem ainda chamar com o nome antigo.

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


# ---------------------------------------------------------------------------
# Tarefa E (spec 2026-09-03-cadastro-paciente-portal-e-colisao-cpf.md) —
# backfill de taxonomia: Item.item_group genérico ("Aplicação de Vacinas")
# em brincos/vitaminas/etc.
# ---------------------------------------------------------------------------


def backfill_item_group_taxonomia(aplicar: bool = False) -> list[dict]:
	"""Corrige ``Item.item_group`` para o que o item REALMENTE É (nunca o 1º
	caso de uso), usando a MESMA curadoria já usada para publicar o Website
	Item (``catalogo_loja.json`` — ``entrada["secao"]``) como fonte única de
	verdade — não inventa uma segunda classificação.

	Causa raiz: ``_upsert_website_item`` já corrige a categoria de NAVEGAÇÃO
	(``website_item_groups``, o que rege filtro/tab da loja) sem tocar no
	``Item.item_group`` bruto — por isso 38 produtos (brincos, vitaminas
	injetáveis etc., migrados em massa) continuam com ``item_group =
	"Aplicação de Vacinas"`` no cadastro do Item, mesmo já aparecendo na
	categoria certa na loja. Isso vaza como rótulo errado em qualquer lugar
	que leia o ``Item.item_group`` bruto (breadcrumb do produto — ver
	``imun_parents_corrigidos`` — e qualquer relatório/tela do Desk que
	agrupe por Item Group).

	SEMPRE roda em modo dry-run por padrão (``aplicar=False``) — só relata o
	que MUDARIA, nunca escreve. O CTO decide quando aplicar (``aplicar=True``)
	depois de revisar a lista, rodando via ``bench execute`` — mudança de
	DADOS em produção não é responsabilidade deste Dev (doutrina do projeto).

	Idempotente: rodar de novo depois de aplicado não muda mais nada (todo
	item já estaria com o ``item_group`` curado == ``secao``).

	Risco documentado (relatório ao CTO): ``Item.item_group`` alimenta
	default de conta contábil/imposto/preço em alguns fluxos do ERPNext
	(Item Group Defaults) — confirmar que as 6 categorias da loja não têm
	default de conta divergente do que "Aplicação de Vacinas" tinha, antes
	de aplicar em massa.

	Devolve uma lista de ``{"item_code", "item_name", "item_group_atual",
	"item_group_novo"}`` — vazia se não houver nada a corrigir (ou se algo
	impedir a leitura, nunca lança)."""
	try:
		if not frappe.db.exists("DocType", "Item"):
			return []

		mapa = _carregar_mapa_loja()
		if not mapa:
			return []

		# Só reatribui para uma seção que EXISTE como Item Group de verdade —
		# nunca cria um Item Group novo aqui (isso é papel de
		# _setup_item_groups, já idempotente e já rodado no migrate).
		secoes_validas = {
			nome
			for nome in {entrada.get("secao") for entrada in mapa.values() if entrada.get("secao")}
			if frappe.db.exists("Item Group", nome)
		}
		if not secoes_validas:
			return []

		items = frappe.get_all(
			"Item",
			filters={"disabled": 0, "is_stock_item": 0, "is_sales_item": 1},
			fields=["name", "item_code", "item_name", "item_group"],
		)

		mudancas: list[dict] = []
		for item in items:
			entrada = mapa.get(item.item_name)
			if not entrada:
				continue
			secao = entrada.get("secao")
			if not secao or secao not in secoes_validas:
				continue
			if item.item_group == secao:
				continue  # já correto — idempotente.
			mudancas.append(
				{
					"item_code": item.item_code,
					"item_name": item.item_name,
					"item_group_atual": item.item_group,
					"item_group_novo": secao,
				}
			)

		if aplicar:
			for mudanca in mudancas:
				frappe.db.set_value(
					"Item",
					mudanca["item_code"],
					"item_group",
					mudanca["item_group_novo"],
					update_modified=False,
				)
			if mudancas:
				frappe.db.commit()  # nosemgrep

		return mudancas
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return []


# ---------------------------------------------------------------------------
# Atividade REDESIGN 2026-09-04 — alias público pedido pelo spec
# ---------------------------------------------------------------------------


def migrar_item_group_produtos(dry_run: bool = True) -> list[dict]:
	"""Alias público de ``backfill_item_group_taxonomia`` (Tarefa E, já
	implementada e idempotente) com a assinatura pedida pelo spec 2026-09-04
	(``dry_run=True`` por padrão). Reuso total — NÃO duplica a lógica de
	reclassificação, só inverte o nome do parâmetro (``dry_run`` ao contrário
	de ``aplicar``) para bater com o nome usado no spec/relatório.

	Uso (via ``bench execute``, sempre em dry-run primeiro):

		bench --site <site> execute imunocare_ecommerce.catalogo.setup.migrar_item_group_produtos

	Para aplicar de fato (o CTO decide, depois de revisar a lista):

		bench --site <site> execute imunocare_ecommerce.catalogo.setup.migrar_item_group_produtos --kwargs '{"dry_run": false}'
	"""
	return backfill_item_group_taxonomia(aplicar=not dry_run)
