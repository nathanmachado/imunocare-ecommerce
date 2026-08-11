"""Home da loja Imunocare (BRIEF_LOJA.md item 5; ver F6 — revisão de design,
inventário 2026-08-02, sobre o fallback de imagem por ícone).

Reuso: as seções (Vacinas/Vitaminas/.../Planos) e seus itens vêm de
``catalogo.setup.secoes_para_home`` (Website Item + Item Price já publicados
pelo catálogo — nenhuma consulta nova é criada aqui). O link "ver todos" de
cada seção é a própria página nativa da categoria
(``templates/generators/item_group.html``, gerada pelo webshop a partir do
Item Group). A página de produto (ao clicar num item) também é 100% nativa.

Website Settings.home_page="index" (``identidade.setup``) faz "/" renderizar
este template.
"""

from __future__ import annotations

import frappe
from frappe.utils import fmt_money

no_cache = 1

# F6 (revisão de design — inventário 2026-08-02): REMOVIDO o fallback de
# imagem genérica por seção (moco.jpg repetido em 3 das 4 seções, crítica do
# mockup x implementação). Produto sem ``website_image`` própria renderiza o
# ícone SVG de traço da seção no card (ver imun_icone() em
# templates/includes/imun_icons.html) — não mais uma foto repetida.


def get_context(context):
	context.no_cache = 1
	# F1 (inventário 2026-08-02): fonte única do <title> — antes o
	# www/index.html tinha um {% block title %} com texto fixo próprio,
	# ignorando este context.title (o "title" da base.html vem do context).
	context.title = "Imunocare — Clínica de Vacinas Particulares em Uberlândia"

	try:
		from imunocare_ecommerce.catalogo.setup import secoes_para_home

		context.secoes = _formatar_precos(secoes_para_home(limite_por_secao=4))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "imunocare_ecommerce.www.index")
		context.secoes = []

	context.domiciliar_ativo = False
	try:
		if frappe.db.exists("DocType", "Imunocare Ecommerce Settings"):
			s = frappe.get_single("Imunocare Ecommerce Settings")
			context.domiciliar_ativo = bool(s.get("domiciliar_ativo")) and float(
				s.get("taxa_domiciliar") or 0
			) > 0
	except Exception:
		pass

	# F7 (duas linhas Imuno x Care): nav com TODAS as categorias de cada
	# linha, mesmo as que ainda não têm produto publicado (essas caem na
	# página informativa de categoria vazia — ver
	# templates/generators/item_group.html + catalogo.jinja_utils). Diferente
	# de `context.secoes` acima (só categorias COM produto, para o carrossel
	# de cards da home).
	try:
		from imunocare_ecommerce.catalogo.setup import nav_categorias

		context.nav_imuno = nav_categorias("Loja Imunocare")
		context.nav_care = nav_categorias("Cuidado Pessoal")
	except Exception:
		frappe.log_error(frappe.get_traceback(), "imunocare_ecommerce.www.index")
		context.nav_imuno = []
		context.nav_care = []

	# R2 (Feature 70 — REDO do site): carrossel de médicos parceiros. Lista
	# vazia (nenhum profissional com imun_publicar_site=1) esconde a seção
	# inteira no template — ver medicos.home.medicos_para_home().
	try:
		from imunocare_ecommerce.medicos.home import medicos_para_home

		context.medicos = medicos_para_home()
	except Exception:
		frappe.log_error(frappe.get_traceback(), "imunocare_ecommerce.www.index")
		context.medicos = []

	return context


_DESC_PADRAO_SECAO = {
	"Vacinas": "Aplicação por profissional de saúde habilitado, na clínica ou em casa.",
	"Vitaminas Injetáveis": "Reposição com avaliação profissional — mais energia e imunidade.",
	"Terapias Injetáveis": "Protocolos com indicação e acompanhamento profissional.",
	# Item 2b (2026-08-10): "Pacotes" -> "Planos".
	"Planos": "Condição especial para completar o esquema recomendado.",
	"Brincos": "Furo de orelha com técnica asséptica e material hipoalergênico.",
	"Consultas Médicas": "Orientação profissional para vacinar e se cuidar com segurança.",
	"Vale-Presente": "Presenteie saúde: crédito para vacinas, vitaminas ou consultas.",
}


def _formatar_precos(secoes: list[dict]) -> list[dict]:
	for secao in secoes:
		desc_padrao = _DESC_PADRAO_SECAO.get(secao["nome"], "")
		for item in secao["itens"]:
			item["preco_fmt"] = fmt_money(item["preco"], currency="BRL") if item.get("preco") else None
			# F6: sem imagem própria -> None (o template desenha o ícone SVG da
			# seção no lugar; nada de foto genérica repetida).
			# Card do layout aprovado (design alvo v1) exige uma descrição curta —
			# usa Website Item.short_description; cai no texto padrão da seção
			# quando o item ainda não tem short_description cadastrada.
			descricao = (item.get("descricao") or "").strip() or desc_padrao
			if len(descricao) > 96:
				descricao = descricao[:93].rstrip() + "..."
			item["descricao"] = descricao
	return secoes
