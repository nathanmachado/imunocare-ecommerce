"""Importa o catálogo REAL (com preços) de ``catalogo/catalogo_prod.json`` para o
imunocare.local — Items + Item Price + Website Item das seções vacinas / vitaminas /
terapias / brincos / pacotes (Feature 55 / A1 — brief ``catalogo/BRIEF_LOJA.md``).

Reuso: a criação/atualização do Website Item, a seção de navegação
(``website_item_groups``) e a publicação continuam 100% a cargo de
``catalogo.setup.setup_catalogo`` (não duplicamos essa lógica) — este módulo só
garante que os **Items reais + Item Price** existam antes dela rodar.

A seção "planos" (Calendário Premium, preço 0) é **intencionalmente ignorada**
— não é produto de venda (brief item 2).

Idempotente: reexecutar não duplica Item/Item Price; atualiza o preço (Venda
Padrão) e preenche copy/imagem só quando ainda estão vazios (preserva edição
manual do operador feita depois pelo Desk).

Preços são dado sensível de negócio — este módulo só lê ``catalogo_prod.json``
(arquivo de trabalho local, fora do controle de versão de produção) e grava no
banco local; nunca loga o valor em texto plano fora do frappe.logger interno.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

import frappe

_LOG_TITLE = "imunocare_ecommerce.catalogo.importar_prod"

_ARQUIVO_CATALOGO = Path(__file__).parent / "catalogo_prod.json"

_PRICE_LIST_PREFERIDA = "Venda Padrão"
_PRICE_LIST_FALLBACK = "Standard Selling"
_STOCK_UOM = "Unidade"

# chave do JSON -> (Item Group / seção da loja, prefixo do item_code)
_SECOES: dict[str, tuple[str, str]] = {
	"vacinas": ("Vacinas", "vac"),
	"vitaminas": ("Vitaminas Injetáveis", "vit"),
	"terapias": ("Terapias Injetáveis", "ter"),
	"brincos": ("Brincos", "bri"),
	"pacotes": ("Pacotes", "pac"),
	# "planos": NÃO importado — Calendário Premium (preço 0) não é produto de venda.
}

# F7 (Linha Care): extensão PRONTA para receber a lista real de produtos do
# dono — hoje `catalogo_prod.json` não tem essas chaves, então o loop de
# importação abaixo processa listas vazias (no-op seguro). Quando o dono
# fornecer produtos, basta adicionar as chaves "filtro_solar"/
# "serum_facial"/"filtro_solar_infantil" ao JSON no mesmo formato das demais
# seções (item_name/nome_loja/preco) — nenhum código novo é necessário.
# Preços NÃO são inventados aqui (doutrina "reuso primeiro"/dados sensíveis).
_SECOES_CARE: dict[str, tuple[str, str]] = {
	"filtro_solar": ("Filtro Solar", "flt"),
	"serum_facial": ("Serum Facial", "ser"),
	"filtro_solar_infantil": ("Filtro Solar Infantil", "fli"),
}

# Nomes de loja "feios"/técnicos trocados por um nome amigável — F2 (catálogo
# v1). Chave = entrada["item_name"] BRUTO do catalogo_prod.json (não
# nome_loja) — é o identificador estável usado também para o item_code (ver
# `_nome_loja_estavel`), então o override NUNCA muda a rota/SKU do produto,
# só o rótulo exibido na loja.
_NOME_LOJA_OVERRIDE: dict[str, str] = {
	"APL-HPV9": "Vacina HPV Nonavalente (9-valente)",
	# Brincos — F2: "Adulto"/"Infantil" cru -> nome de loja explicativo.
	"Aplicação Brinco Adulto": "Aplicação de Brinco Adulto",
	"Aplicação Brinco Infantil": "Aplicação de Brinco Infantil",
	# Vitaminas — F2: nome com fórmula química/concentração -> nome amigável
	# (a concentração/forma técnica continua na descrição do produto).
	"Aplicação Intramuscular Coenzima Q10 - 5% (100 mg)": "Coenzima Q10 Injetável",
	"Aplicação Intramuscular Colina - 25% (500 mg)": "Colina Injetável",
	"Aplicação Intramuscular Complexo B Com Vit.B1": "Complexo B Injetável (com B1)",
	"Aplicação Intramuscular Complexo B Com Vit.B12": "Complexo B Injetável (com B12)",
	"Aplicação Intramuscular Resveratrol Bioencapsulado - 1,5 %": "Resveratrol Injetável",
	"Aplicação Intramuscular Vitamina B1 (Tiamina - 10%)": "Vitamina B1 Injetável (Tiamina)",
	"Aplicação Intramuscular Vitamina B12 (Metilcobalamina - 0,25%)": (
		"Vitamina B12 Injetável (Metilcobalamina)"
	),
	# Corrige "Ascorbico" sem acento herdado da produção (F2).
	"Aplicação Intramuscular Vitamina C (Ácido Ascorbico - 22,2%)": (
		"Vitamina C Injetável (Ácido Ascórbico)"
	),
	"Aplicação Intramuscular Vitamina D3 (Colecalciferol 1,5%) 600.000 UI/ml": (
		"Vitamina D3 Injetável (Colecalciferol)"
	),
	"Aplicação Intramuscular Vitamina Dk2 (D3 600.000UI + K2Mk7 1,3Mg)": "Vitamina D3 + K2 Injetável",
	# Terapia injetável — F2/F9: NUNCA expor o princípio ativo/nome comercial
	# em nenhum campo público (título, rota, SKU visível, copy). Regra
	# inegociável do dono (política de saúde do Google Ads/Meta, RDC 96/2008,
	# CFM — medicamento não é vendido online). Ver relatório: risco crítico
	# sinalizado ao CTO — o item já estava PUBLICADO em checkout direto,
	# expondo o nome do medicamento no <title>, H1, descrição e no "Item
	# Code" (SKU) visível na página nativa do webshop.
	"Aplicação Dose Tirzepatida": "Terapia Injetável para Controle de Peso",
}

# Item_codes que precisam ter a copy FORÇADAMENTE atualizada nesta rodada
# (F2), mesmo já tendo short_description/web_long_description preenchidos
# pela geração anterior (texto genérico de tema, não específico do produto —
# ver BRIEF_LOJA.md / atividade F2). Fora desta lista, a regra de
# idempotência normal vale (só preenche campo vazio, preserva edição
# manual). Calculado a partir do slug ESTÁVEL (ver `_nome_loja_estavel`), não
# muda entre execuções.
_FORCAR_ATUALIZACAO_COPY: set[str] = {
	"vit-coenzima-q10-5-100-mg",
	"vit-colina-25-500-mg",
	"vit-complexo-b-com-vitb1",
	"vit-complexo-b-com-vitb12",
	"vit-resveratrol-bioencapsulado-15",
	"vit-vitamina-b1-tiamina-10",
	"vit-vitamina-b12-metilcobalamina-025",
	"vit-vitamina-c-acido-ascorbico-222",
	"vit-vitamina-d3-colecalciferol-15-600000-uiml",
	"vit-vitamina-dk2-d3-600000ui-k2mk7-13mg",
	"bri-adulto",
	"bri-infantil",
	# item_code final APÓS o rename por compliance (ver
	# `_item_code_sanitizado`/`_TERMOS_PROIBIDOS_PUBLICOS`) — o antigo
	# "ter-tirzepatida" deixa de existir com esse nome.
	"ter-terapia-injetavel-para-controle-de-peso",
	# HPV — F2: cobertura de keyword "vacina hpv preço/idade" adicionada
	# nesta atividade ao texto já existente (que era específico, só faltava
	# a keyword) — força a atualização 1x.
	"vac-vacina-hpv-nonavalente-9-valente",
}

# F9 (regra inegociável, ver relatório): termos que NUNCA podem aparecer em
# NENHUM campo público do site (título, nome, descrição, e também o
# "Item Code"/SKU exibido na página nativa do produto — webshop
# item_details.html, upstream, mostra `doc.item_code` cru). Verificado em
# TODA importação (não só na 1ª vez) — rede de segurança caso um item novo
# entre no catalogo_prod.json com um nome não-conforme.
_TERMOS_PROIBIDOS_PUBLICOS: tuple[str, ...] = (
	"tirzepatida",
	"mounjaro",
	"semaglutida",
	"ozempic",
	"wegovy",
	"saxenda",
	"liraglutida",
	"caneta emagrecedora",
)

# Imagens já staged em public/img/ — associação por palavra-chave do nome.
# Só QDENGA tem foto específica (brief item 2). F6 (revisão de design,
# inventário 2026-08-02) REVERTEU a ideia inicial de F2 de usar as fotos
# genéricas (moco.jpg etc.) como fallback POR SEÇÃO no Website Item — a
# crítica de design apontou "moco.jpg em 3 das 4 seções" como repetição
# ruim. Produto sem foto própria fica com ``website_image`` vazio de
# propósito: o fallback visual agora é o ÍCONE SVG de traço da seção
# (templates/includes/imun_icons.html), não mais uma foto repetida.
# Fotos de produto das vacinas (mão segurando o frasco + rótulo da marca),
# fornecidas pelo dono 2026-08-09, otimizadas em public/img/vacinas/. Match por
# substring no NOME DE LOJA do item; PRIMEIRA ocorrência vence (_imagem_para),
# então a ORDEM importa — o mais específico vem antes do mais genérico:
#   - "rotavirus" ANTES de "pentavalente" (senão "Rotavirus Pentavalente"
#     casaria com a foto do Pentavalente puro).
#   - "tetraxim" (DTPa+IPV) ANTES de "dtpa" (senão "DTPa + IPV - Tetraxim"
#     casaria com a foto do DTPa puro).
# Vacinas do catálogo sem foto no lote (HPV, Beyfortus, Febre Amarela, etc.)
# ficam sem website_image de propósito → fallback é o ícone SVG da seção.
# "pneumo-23.jpg" fica mapeado para uso futuro (não há item 23V hoje).
_IMAGEM_POR_PALAVRA: list[tuple[str, str]] = [
	("qdenga", "vacinas/qdenga.jpg"),
	("rotavirus", "vacinas/rotavirus-pentavalente.jpg"),
	("pentavalente", "vacinas/pentavalente.jpg"),
	("influenza tetravalente", "vacinas/influenza-tetravalente.jpg"),
	("acwy", "vacinas/meningo-acwy.jpg"),
	("meningite b", "vacinas/meningo-b.jpg"),
	("meningocócica b", "vacinas/meningo-b.jpg"),
	("13v", "vacinas/pneumo-13.jpg"),
	("15v", "vacinas/pneumo-15.jpg"),
	("20v", "vacinas/pneumo-20.jpg"),
	("23v", "vacinas/pneumo-23.jpg"),
	("mmr", "vacinas/triplice-viral-mmr.jpg"),
	("tetraxim", "vacinas/tetravalente.jpg"),
	("dtpa", "vacinas/dtpa.jpg"),
	("varicela", "vacinas/varivax.jpg"),
]


# ---------------------------------------------------------------------------
# Slug do item_code (ascii, minúsculo, hífen)
# ---------------------------------------------------------------------------


def _slug(texto: str) -> str:
	texto = texto.strip().lower().replace("–", "-").replace("—", "-")
	texto = unicodedata.normalize("NFKD", texto)
	texto = "".join(c for c in texto if not unicodedata.combining(c))
	texto = re.sub(r"[^\w\s-]", "", texto)
	texto = re.sub(r"[\s_]+", "-", texto)
	return re.sub(r"-+", "-", texto).strip("-")


# ---------------------------------------------------------------------------
# Copy (SEO / política de saúde) — templates por tema, first-pass.
# ---------------------------------------------------------------------------
# Cada função devolve (short_description, web_long_description). Tom factual,
# sem promessa de resultado, com indicação de avaliação profissional — a
# Imunocare Ecommerce Settings.texto_disclaimer_padrao é anexada por
# landing.setup (website_content), não repetida aqui.


def _copy_vacina(nome: str) -> tuple[str, str]:
	n = nome.lower()
	if "hpv" in n:
		return (
			f"Vacina do HPV ({nome}) na Imunocare, clínica de vacinas particulares. Veja preço "
			"e idade recomendada e agende a aplicação com avaliação de profissional de saúde.",
			"<p>A vacina contra o HPV (Papilomavírus Humano) é indicada para adolescentes e "
			"adultos conforme avaliação médica, dentro do esquema vacinal recomendado. "
			"Na Imunocare você agenda a vacina HPV — nonavalente — em ambiente clínico, com "
			"aplicação por profissional de saúde habilitado.</p>"
			"<p>Consulte nossa equipe sobre o preço da vacina HPV, idade recomendada, número "
			"de doses e intervalo do esquema vacinal — a vacina do HPV/vacina contra HPV "
			"também está disponível para atendimento a domicílio.</p>",
		)
	if "influenza" in n or "efluelda" in n or "gripe" in n:
		return (
			f"Vacina da gripe / influenza ({nome}) — clínica de vacinas particulares. "
			"Indicada anualmente conforme avaliação profissional.",
			"<p>A vacina influenza (vacina da gripe) protege contra as cepas do vírus "
			"influenza em circulação e é recomendada anualmente, especialmente para "
			"grupos de maior risco. A Imunocare aplica a vacina tetravalente/quadrivalente "
			"e a formulação para idosos (Efluelda), conforme indicação.</p>"
			"<p>Fale com nossa equipe sobre a formulação mais indicada para sua idade e "
			"histórico de saúde.</p>",
		)
	if "febre amarela" in n:
		return (
			"Vacina febre amarela — onde tomar em clínica particular na Imunocare, com "
			"aplicação por profissional de saúde.",
			"<p>A vacina febre amarela é indicada para residentes e viajantes de/para áreas "
			"com recomendação vacinal, conforme avaliação de um profissional de saúde. "
			"Sabendo onde tomar a vacina febre amarela com agilidade, a Imunocare oferece "
			"atendimento particular sem necessidade de encaixe no sistema público.</p>"
			"<p>Consulte indicações, contraindicações e prazo de validade internacional "
			"do certificado de vacinação.</p>",
		)
	if "qdenga" in n or "dengue" in n:
		return (
			"Vacina da dengue Qdenga (Takeda) — clínica de vacinas particulares na "
			"Imunocare, com avaliação de profissional de saúde.",
			"<p>A Qdenga (Takeda) é a vacina contra a dengue, indicada conforme avaliação "
			"médica e faixa etária recomendada pela bula. A Imunocare oferece a aplicação "
			"em ambiente clínico particular, sem fila de espera.</p>"
			"<p>Consulte nossa equipe sobre indicações, contraindicações e esquema de doses.</p>",
		)
	if "pneumocócica" in n or "pneumo" in n:
		return (
			f"Vacina pneumocócica ({nome}) — clínica de vacinas particulares, indicada "
			"para crianças, idosos e grupos de risco.",
			"<p>As vacinas pneumocócicas (pneumo 13, 15 e 20 valente) protegem contra "
			"sorotipos do Streptococcus pneumoniae e são indicadas para crianças, idosos "
			"e pessoas com condições de risco, conforme avaliação profissional.</p>"
			"<p>Consulte qual formulação (13V, 15V ou 20V) é mais indicada para o seu caso.</p>",
		)
	if "meningi" in n or "meningoc" in n:
		return (
			f"Vacina meningocócica ({nome}) — clínica de vacinas particulares, indicada "
			"para adolescentes, adultos e crianças conforme calendário.",
			"<p>As vacinas meningocócicas protegem contra sorogrupos da bactéria "
			"Neisseria meningitidis e são indicadas dentro do calendário vacinal do "
			"adolescente e do adulto, conforme avaliação de profissional de saúde.</p>",
		)
	if any(k in n for k in ("pentavalente", "hexavalente", "rotavirus", "dtpa")):
		return (
			f"Vacina infantil {nome} — clínica de vacinas particulares para bebês, com "
			"aplicação por profissional de saúde.",
			"<p>Vacina indicada dentro do calendário vacinal infantil (vacina bebê / "
			"vacina de 2 meses particular em diante), conforme avaliação de um "
			"profissional de saúde habilitado. A Imunocare oferece atendimento "
			"particular ágil, com todo o cuidado da aplicação em bebês e crianças.</p>",
		)
	return (
		f"{nome} — clínica de imunização e vacinas particulares em Uberlândia, com "
		"aplicação por profissional de saúde habilitado.",
		f"<p>Vacina {nome} disponível para aplicação particular na Imunocare, clínica de "
		"imunização e vacinas particulares. Consulte preços de vacinas particulares e "
		"disponibilidade de vacina a domicílio. O atendimento é realizado por profissional "
		"de saúde habilitado, que avalia indicações e contraindicações antes da "
		"aplicação.</p>",
	)


# F2 (catálogo v1): copy PRÓPRIA por vitamina — as 10 caíam antes em 1 único
# template genérico ("Aplicação intramuscular de {nome}..." repetido). Chave =
# nome de loja já amigável (pós-override, ver _NOME_LOJA_OVERRIDE). Tom
# factual, sem promessa de resultado, sempre "conforme avaliação/indicação
# profissional" (política de saúde do Google) — não afirma que a vitamina
# trata/previne nada; só descreve para que serve a via de aplicação.
_COPY_VITAMINAS: dict[str, tuple[str, str]] = {
	"Coenzima Q10 Injetável": (
		"Aplicação intramuscular de Coenzima Q10, mediante avaliação de profissional de saúde.",
		"<p>A Coenzima Q10 é uma substância naturalmente presente nas células, associada ao "
		"metabolismo energético. Na Imunocare, a aplicação intramuscular é feita por "
		"profissional de saúde habilitado, conforme avaliação e indicação — não substitui "
		"acompanhamento médico ou nutricional contínuo.</p>",
	),
	"Colina Injetável": (
		"Aplicação intramuscular de Colina, mediante avaliação de profissional de saúde.",
		"<p>A colina é um nutriente relacionado a funções celulares e hepáticas. A aplicação "
		"intramuscular na Imunocare é realizada por profissional de saúde habilitado, "
		"conforme avaliação clínica individual.</p>",
	),
	"Complexo B Injetável (com B1)": (
		"Aplicação intramuscular do Complexo B com Vitamina B1 (Tiamina), com avaliação profissional.",
		"<p>O Complexo B com Vitamina B1 (Tiamina) reúne vitaminas do grupo B associadas ao "
		"metabolismo energético e ao funcionamento do sistema nervoso. Aplicação intramuscular "
		"realizada por profissional de saúde habilitado, conforme avaliação clínica.</p>",
	),
	"Complexo B Injetável (com B12)": (
		"Aplicação intramuscular do Complexo B com Vitamina B12, com avaliação profissional.",
		"<p>O Complexo B com Vitamina B12 reúne vitaminas do grupo B, com a B12 associada à "
		"formação de células sanguíneas e ao sistema nervoso. Aplicação intramuscular "
		"realizada por profissional de saúde habilitado, conforme avaliação clínica.</p>",
	),
	"Resveratrol Injetável": (
		"Aplicação intramuscular de Resveratrol bioencapsulado, mediante avaliação profissional.",
		"<p>O resveratrol é um composto antioxidante encontrado em plantas. Na Imunocare, a "
		"aplicação intramuscular (forma bioencapsulada) é feita por profissional de saúde "
		"habilitado, conforme avaliação e indicação individual.</p>",
	),
	"Vitamina B1 Injetável (Tiamina)": (
		"Aplicação intramuscular de Vitamina B1 (Tiamina), mediante avaliação profissional.",
		"<p>A Vitamina B1 (Tiamina) participa do metabolismo de carboidratos e do funcionamento "
		"do sistema nervoso. Aplicação intramuscular realizada por profissional de saúde "
		"habilitado na Imunocare, conforme avaliação clínica — reposição pontual, não substitui "
		"acompanhamento médico contínuo.</p>",
	),
	"Vitamina B12 Injetável (Metilcobalamina)": (
		"Aplicação intramuscular de Vitamina B12 (Metilcobalamina), com avaliação profissional.",
		"<p>A Vitamina B12 (Metilcobalamina) está associada à formação de células sanguíneas, "
		"ao metabolismo energético e ao sistema nervoso. Aplicação intramuscular realizada por "
		"profissional de saúde habilitado, conforme avaliação e indicação clínica.</p>",
	),
	"Vitamina C Injetável (Ácido Ascórbico)": (
		"Aplicação intramuscular de Vitamina C (Ácido Ascórbico), mediante avaliação profissional.",
		"<p>A Vitamina C (Ácido Ascórbico) é um antioxidante associado ao suporte do sistema "
		"imunológico. Aplicação intramuscular realizada por profissional de saúde habilitado na "
		"Imunocare, conforme avaliação clínica individual.</p>",
	),
	"Vitamina D3 Injetável (Colecalciferol)": (
		"Aplicação intramuscular de Vitamina D3 (Colecalciferol), com avaliação profissional.",
		"<p>A Vitamina D3 (Colecalciferol) está associada à saúde óssea e ao sistema "
		"imunológico. Indicada mediante avaliação de níveis séricos e orientação de um "
		"profissional de saúde — aplicação intramuscular realizada na Imunocare.</p>",
	),
	"Vitamina D3 + K2 Injetável": (
		"Aplicação intramuscular de Vitamina D3 + K2, mediante avaliação de profissional de saúde.",
		"<p>A combinação de Vitamina D3 (Colecalciferol) e Vitamina K2 é associada à saúde "
		"óssea. Aplicação intramuscular realizada por profissional de saúde habilitado na "
		"Imunocare, conforme avaliação clínica individual.</p>",
	),
}


def _copy_vitamina(nome: str) -> tuple[str, str]:
	if nome in _COPY_VITAMINAS:
		return _COPY_VITAMINAS[nome]
	# Fallback genérico (produto novo ainda não individualizado no dict acima).
	return (
		f"Aplicação intramuscular de {nome}, mediante avaliação de profissional de saúde.",
		f"<p>Aplicação intramuscular de {nome} na Imunocare, realizada por profissional de "
		"saúde habilitado após avaliação clínica. Indicada para reposição pontual "
		"conforme prescrição — não substitui acompanhamento médico ou nutricional "
		"contínuo.</p>",
	)


# F9 (ads-safe, regra inegociável do dono — ver relatório): esta é a ÚNICA
# terapia injetável do catálogo hoje e o produto por trás dela é um
# medicamento de controle de peso. O nome comercial/princípio ativo NUNCA
# aparece aqui (nem em nenhuma outra página do site) — linguagem aprovada:
# "Protocolo de Emagrecimento com Acompanhamento Médico" / "avaliação
# médica" / "tratamentos modernos aprovados pela Anvisa" (sem citar qual).
def _copy_terapia(nome: str) -> tuple[str, str]:
	return (
		"Terapia injetável para controle de peso, com acompanhamento médico na Imunocare. "
		"Agende uma avaliação para saber se o tratamento é indicado para você.",
		"<p>A Imunocare oferece aplicação de terapia injetável para controle de peso, sempre "
		"mediante avaliação médica prévia e acompanhamento contínuo. A indicação, a "
		"prescrição e o acompanhamento do tratamento são de responsabilidade do médico "
		"responsável — resultados variam de pessoa para pessoa.</p>"
		"<p>Este tratamento não é vendido diretamente pela loja. Agende uma avaliação médica "
		"para saber se o protocolo de controle de peso é indicado para o seu caso.</p>",
	)


# F2: copy própria por brinco (adulto x infantil) — antes caíam no mesmo
# template genérico interpolado.
_COPY_BRINCOS: dict[str, tuple[str, str]] = {
	"Aplicação de Brinco Adulto": (
		"Aplicação de brinco (piercing de orelha) para adultos, com material esterilizado, na Imunocare.",
		"<p>Furo de orelha para adultos realizado em ambiente clínico, com material "
		"hipoalergênico esterilizado e técnica asséptica. Procedimento realizado pela equipe "
		"de enfermagem, com orientações de cuidado pós-procedimento.</p>",
	),
	"Aplicação de Brinco Infantil": (
		"Aplicação de brinco (piercing de orelha) infantil, com técnica segura e material esterilizado, na Imunocare.",
		"<p>Furo de orelha infantil realizado com todo o cuidado, em ambiente clínico, com "
		"material hipoalergênico esterilizado e técnica asséptica. Procedimento indicado "
		"conforme avaliação da equipe no momento do atendimento, com orientações aos pais/"
		"responsáveis sobre os cuidados pós-procedimento.</p>",
	),
}


def _copy_brinco(nome: str) -> tuple[str, str]:
	if nome in _COPY_BRINCOS:
		return _COPY_BRINCOS[nome]
	return (
		f"Aplicação de brinco ({nome}) com material esterilizado, em ambiente clínico.",
		f"<p>Aplicação de brinco (piercing de orelha) {nome.lower()} realizada em ambiente "
		"clínico, com material esterilizado e técnica segura. Procedimento indicado "
		"conforme avaliação da equipe no momento do atendimento.</p>",
	)


def _copy_pacote(nome: str) -> tuple[str, str]:
	return (
		f"{nome} — condição especial para completar o esquema vacinal na Imunocare.",
		f"<p>{nome}: pacote fechado de doses para completar o esquema vacinal recomendado, "
		"com aplicação por profissional de saúde habilitado a cada visita. Consulte "
		"disponibilidade de agenda para as doses seguintes.</p>",
	)


def _copy_care(nome: str) -> tuple[str, str]:
	"""F7 (Linha Care): copy genérica — o dono ainda não forneceu a lista real
	de produtos; quando fornecer, dá pra individualizar copy por produto do
	mesmo jeito que foi feito para vitaminas/brincos (F2)."""
	return (
		f"{nome} — Linha Care Imunocare, cuidado pessoal para o dia a dia.",
		f"<p>{nome} da Linha Care Imunocare. Consulte modo de uso e composição antes de "
		"utilizar.</p>",
	)


_COPY_POR_SECAO = {
	"vacinas": _copy_vacina,
	"vitaminas": _copy_vitamina,
	"terapias": _copy_terapia,
	"filtro_solar": _copy_care,
	"serum_facial": _copy_care,
	"filtro_solar_infantil": _copy_care,
	"brincos": _copy_brinco,
	"pacotes": _copy_pacote,
}


def _imagem_para(nome: str, chave_secao: str) -> str | None:
	"""Imagem específica por palavra-chave no nome, ou ``None`` (F6: sem
	fallback de foto genérica por seção — o visual de fallback é o ícone SVG,
	resolvido no template, não gravado no Website Item)."""
	n = nome.lower()
	for palavra, arquivo in _IMAGEM_POR_PALAVRA:
		if palavra in n:
			return f"/assets/imunocare_ecommerce/img/{arquivo}"
	return None


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def _carregar_catalogo() -> dict:
	with open(_ARQUIVO_CATALOGO, encoding="utf-8") as f:
		return json.load(f)


# ---------------------------------------------------------------------------
# F1 (inventário 2026-08-02): fallbacks que evitavam falha silenciosa
# item-a-item quando o ambiente não tinha exatamente "Venda Padrão"/"Unidade"
# (ex.: site novo, ainda no chart-of-accounts/UOM padrão do ERPNext).
# ---------------------------------------------------------------------------

_price_list_resolvida: str | None = None


def _price_list() -> str:
	"""Price List a usar: "Venda Padrão" se existir, senão "Standard Selling"
	(sempre presente no ERPNext). Resolvida 1x por execução (memoizada)."""
	global _price_list_resolvida
	if _price_list_resolvida:
		return _price_list_resolvida
	if frappe.db.exists("Price List", _PRICE_LIST_PREFERIDA):
		_price_list_resolvida = _PRICE_LIST_PREFERIDA
	else:
		frappe.logger(_LOG_TITLE).warning(
			f'Price List "{_PRICE_LIST_PREFERIDA}" não existe — usando fallback "{_PRICE_LIST_FALLBACK}".'
		)
		_price_list_resolvida = _PRICE_LIST_FALLBACK
	return _price_list_resolvida


def _ensure_uom() -> None:
	"""Cria a UOM "Unidade" se ainda não existir — sem isso todo Item.insert()
	desta importação falhava silenciosamente (LinkValidationError capturado
	pelo try/except de cada item, item a item, sem produto nenhum publicado)."""
	if frappe.db.exists("UOM", _STOCK_UOM):
		return
	frappe.get_doc({"doctype": "UOM", "uom_name": _STOCK_UOM, "must_be_whole_number": 1}).insert(
		ignore_permissions=True
	)
	frappe.logger(_LOG_TITLE).info(f'UOM "{_STOCK_UOM}" criada (fallback ausente no ambiente).')


def _contem_termo_proibido(texto: str | None) -> bool:
	t = (texto or "").lower()
	return any(termo in t for termo in _TERMOS_PROIBIDOS_PUBLICOS)


def _item_code_sanitizado(item_code_atual: str, nome_loja_novo: str, prefixo: str) -> str:
	"""F9 (compliance): se ``item_code_atual`` expõe um termo proibido (ex.:
	"ter-tirzepatida" — visível publicamente como "Item Code" na página
	nativa do produto, upstream, não editável por override de nome/copy),
	renomeia o documento ``Item`` para um slug limpo derivado do nome de loja
	já sanitizado (``nome_loja_novo``). Cascata automática do
	``frappe.rename_doc`` atualiza os Links em Item Price/Website Item.

	Idempotente: se o item já foi renomeado numa execução anterior, o
	``item_code_atual`` computado a partir do JSON (nome ORIGINAL, nunca
	muda) sempre bate com o nome ainda-não-sanitizado — o rename só roda
	quando o doc "feio" ainda existir sob esse nome.
	"""
	if not _contem_termo_proibido(item_code_atual):
		return item_code_atual

	novo = f"{prefixo}-{_slug(nome_loja_novo)}"
	if _contem_termo_proibido(novo):
		# nome_loja_novo (override) ainda contém o termo — não renomeia para
		# algo igualmente não-conforme; sinaliza para correção manual do
		# override em _NOME_LOJA_OVERRIDE.
		frappe.log_error(
			f"Item '{item_code_atual}': nome_loja_novo ainda contém termo proibido "
			"(F9) — corrija _NOME_LOJA_OVERRIDE. Rename NÃO realizado.",
			_LOG_TITLE,
		)
		return item_code_atual

	if not frappe.db.exists("Item", item_code_atual):
		return novo  # doc "feio" nunca existiu (ambiente novo) — já nasce limpo
	if frappe.db.exists("Item", novo):
		return novo  # já renomeado numa execução anterior

	# frappe.rename_doc (top-level) NÃO aceita ``ignore_permissions`` (só o
	# ``frappe.model.rename_doc.rename_doc`` interno aceita — descoberto ao
	# validar esta atividade: o TypeError ficava só no traceback, sem impedir
	# o resto do migrate, e o loop seguia criando o Item NOVO com o slug
	# limpo sem nunca renomear/remover o antigo, deixando os dois lado a
	# lado). Não precisamos de bypass de permissão aqui: este código roda em
	# ``after_migrate`` (contexto Administrator). ``force=True`` só por
	# segurança, embora ``Item.allow_rename`` já seja 1 por padrão no ERPNext.
	frappe.rename_doc("Item", item_code_atual, novo, force=True)
	frappe.logger(_LOG_TITLE).info(
		f"Item renomeado por compliance F9 (termo proibido no SKU público): "
		f"'{item_code_atual}' -> '{novo}'."
	)
	return novo


def _ensure_item(item_code: str, item_name: str, item_group: str) -> None:
	"""Cria o Item se não existir. Se já existir, só sincroniza item_name
	(rótulo de exibição) quando o override de nome_loja (F2) mudou — o
	item_code (identidade/rota) nunca muda aqui, então isso nunca renomeia o
	documento, só atualiza um campo de rótulo."""
	if frappe.db.exists("Item", item_code):
		if frappe.db.get_value("Item", item_code, "item_name") != item_name:
			frappe.db.set_value("Item", item_code, "item_name", item_name, update_modified=False)
		return
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_name,
			"item_group": item_group,
			"stock_uom": _STOCK_UOM,
			"is_stock_item": 0,
			"is_sales_item": 1,
			"include_item_in_manufacturing": 0,
			"disabled": 0,
		}
	).insert(ignore_permissions=True)


def _ensure_item_price(item_code: str, preco: float) -> None:
	price_list = _price_list()
	existente = frappe.db.get_value(
		"Item Price", {"item_code": item_code, "price_list": price_list, "selling": 1}, "name"
	)
	if existente:
		if frappe.db.get_value("Item Price", existente, "price_list_rate") != preco:
			frappe.db.set_value("Item Price", existente, "price_list_rate", preco, update_modified=False)
		return
	frappe.get_doc(
		{
			"doctype": "Item Price",
			"item_code": item_code,
			"price_list": price_list,
			"selling": 1,
			"price_list_rate": preco,
		}
	).insert(ignore_permissions=True)


def _preencher_copy_e_imagem(item_code: str, nome_loja: str, chave_secao: str) -> None:
	"""Preenche web_item_name/short_description/web_long_description/imagem do
	Website Item. Regra padrão: só quando ainda estão vazios (não sobrescreve
	edição manual). Exceção (F2): ``item_code`` em ``_FORCAR_ATUALIZACAO_COPY``
	tem a copy/nome SEMPRE ressincronizados com o gerador atual — são os
	produtos que a atividade F2 identificou com texto genérico de tema (nunca
	editados manualmente pelo Desk). Chamado ANTES de
	catalogo.setup.setup_catalogo() publicar; se o Website Item ainda não
	existir, cria o registro mínimo aqui mesmo (setup_catalogo depois só
	ajusta published=1 e a seção)."""
	forcar = item_code in _FORCAR_ATUALIZACAO_COPY

	existing_name = frappe.db.get_value("Website Item", {"item_code": item_code}, "name")
	doc = frappe.get_doc("Website Item", existing_name) if existing_name else frappe.new_doc("Website Item")
	if not existing_name:
		doc.item_code = item_code

	if not doc.web_item_name or forcar:
		doc.web_item_name = nome_loja

	gerador_copy = _COPY_POR_SECAO[chave_secao]
	short_desc, long_desc = gerador_copy(nome_loja)
	if not doc.short_description or forcar:
		doc.short_description = short_desc[:140]
	if not doc.web_long_description or forcar:
		doc.web_long_description = long_desc

	imagem = _imagem_para(nome_loja, chave_secao)
	if imagem and not doc.website_image:
		doc.website_image = imagem

	# F2/F9: quando forçamos a atualização (nome/copy mudaram de verdade), a
	# ROTA (URL pública) precisa acompanhar — "set_route()" nativo (Frappe
	# WebsiteGenerator) só gera rota nova se ``route`` estiver vazio. Sem
	# isso, o "ter-tirzepatida" continuaria publicado em uma URL contendo o
	# nome do medicamento mesmo com o resto da página já sanitizado — o
	# ambiente ainda é local/dev (sem link externo apontando pra essas
	# rotas), então regenerar é seguro.
	if forcar:
		doc.route = None

	doc.flags.ignore_permissions = True
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)


def importar_catalogo_prod() -> None:
	"""Entry-point idempotente (after_migrate). Nunca interrompe o migrate.

	Cria/atualiza os Items reais + Item Price (Venda Padrão) + copy inicial do
	Website Item a partir de ``catalogo_prod.json``. A publicação final
	(published=1, seção de navegação) é feita por
	``catalogo.setup.setup_catalogo``, chamada logo em seguida no hooks.py.
	"""
	if not _ARQUIVO_CATALOGO.exists():
		frappe.logger(_LOG_TITLE).warning(f"{_ARQUIVO_CATALOGO} não encontrado — import pulado.")
		return

	try:
		dados = _carregar_catalogo()
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return

	try:
		# Garante os Item Groups da loja (inclusive "Pacotes") ANTES de criar
		# os Items — senão o Item.insert() falha com LinkValidationError.
		from imunocare_ecommerce.catalogo.setup import ensure_item_groups

		ensure_item_groups()
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return

	# F1: UOM "Unidade" garantida ANTES do loop — sem ela, todo Item.insert()
	# falhava silenciosamente (LinkValidationError capturado item a item).
	try:
		_ensure_uom()
	except Exception:
		frappe.log_error(frappe.get_traceback(), _LOG_TITLE)
		return

	# F7: mescla Linha Imuno (_SECOES) + Linha Care (_SECOES_CARE, hoje sem
	# chave presente em catalogo_prod.json -> loop vira no-op para ela).
	todas_secoes = {**_SECOES, **_SECOES_CARE}

	criados = 0
	for chave_secao, (item_group, prefixo) in todas_secoes.items():
		for entrada in dados.get(chave_secao, []):
			try:
				criados += _processar_entrada(chave_secao, item_group, prefixo, entrada)
			except Exception:
				frappe.log_error(frappe.get_traceback(), _LOG_TITLE)

	frappe.logger(_LOG_TITLE).info(f"importar_catalogo_prod: {criados} item(ns) do catálogo real processado(s).")


def _processar_entrada(chave_secao: str, item_group: str, prefixo: str, entrada: dict) -> bool:
	"""Cria/atualiza 1 Item + Item Price + copy do Website Item a partir de 1
	entrada do catalogo_prod.json. Retorna True em caso de sucesso (usado só
	para contagem no log)."""
	# nome_loja_original: SEMPRE o valor bruto do JSON — é a base do
	# slug/item_code, e por isso tem que ser ESTÁVEL entre execuções (nunca
	# muda, mesmo que _NOME_LOJA_OVERRIDE seja atualizado no futuro — senão
	# o produto "renomeia" o item_code e vira um registro duplicado em vez
	# de atualizar o existente).
	nome_loja_original = entrada.get("nome_loja") or entrada["item_name"]
	item_code_estavel = f"{prefixo}-{_slug(nome_loja_original)}"

	# nome_loja: o rótulo REALMENTE exibido na loja (título, H1, SKU
	# visível, copy) — aplica o override amigável/compliance (F2/F9) sem
	# afetar o item_code acima.
	nome_loja = _NOME_LOJA_OVERRIDE.get(entrada["item_name"], nome_loja_original)

	# Compatibilidade com o override PRÉ-EXISTENTE (ex.: "APL-HPV9" ->
	# "Vacina HPV Nonavalente...", já em produção ANTES desta atividade): o
	# código ANTERIOR (pré-F2) gerava o item_code a partir do nome JÁ COM
	# OVERRIDE, não do nome bruto. Se o Item já existe sob esse slug
	# "legado" e ainda NÃO existe sob o slug estável, reaproveita o legado
	# em vez de criar um duplicado — só overrides introduzidos NESTA
	# atividade (F2/F9) nascem direto no slug estável.
	item_code_legado = f"{prefixo}-{_slug(nome_loja)}"
	if (
		item_code_legado != item_code_estavel
		and frappe.db.exists("Item", item_code_legado)
		and not frappe.db.exists("Item", item_code_estavel)
	):
		item_code = item_code_legado
	else:
		item_code = item_code_estavel

	# F9: exceção ao item_code "estável" acima — se ele próprio expõe um
	# termo proibido (o "Item Code" é público na página do produto), renomeia
	# o Item para um slug limpo.
	item_code = _item_code_sanitizado(item_code, nome_loja, prefixo)

	preco = float(entrada.get("preco") or 0)

	_ensure_item(item_code, nome_loja, item_group)
	_ensure_item_price(item_code, preco)
	_preencher_copy_e_imagem(item_code, nome_loja, chave_secao)
	return True
