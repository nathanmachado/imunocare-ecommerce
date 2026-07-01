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

_GRUPO_PAI = "Loja Imunocare"

# Ordem importa: o pai deve ser criado antes dos filhos.
# Tupla: (nome, is_group, parent_item_group)
_ITEM_GROUPS: list[tuple[str, int, str]] = [
	(_GRUPO_PAI, 1, "All Item Groups"),
	("Vacinas", 0, _GRUPO_PAI),
	("Vitaminas Injetáveis", 0, _GRUPO_PAI),
	("Terapias Injetáveis", 0, _GRUPO_PAI),
	("Consultas Médicas", 0, _GRUPO_PAI),
	("Vale-Presente", 0, _GRUPO_PAI),
	("Brincos", 0, _GRUPO_PAI),
]

# Mapeamento item_group real → seção da loja.
# A chave é substring (lower) do item_group do Item no banco.
# Primeiro match vence — a ordem da lista é relevante.
_SECTION_MAP: list[tuple[str, str]] = [
	("vacina", "Vacinas"),
	("vitamina", "Vitaminas Injetáveis"),
	("terapia injetável", "Terapias Injetáveis"),
	("terapia", "Terapias Injetáveis"),
	("consulta", "Consultas Médicas"),
	("médico", "Consultas Médicas"),
	("vale", "Vale-Presente"),
	("brinco", "Brincos"),
]

_LOG_TITLE = "imunocare_ecommerce.catalogo.setup"


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
	"""Garante a existência dos 7 Item Groups da loja (idempotente)."""
	if not frappe.db.exists("DocType", "Item Group"):
		return  # ERPNext não instalado; improvável em produção
	for name, is_group, parent in _ITEM_GROUPS:
		_ensure_item_group(name, is_group, parent)


def _ensure_item_group(name: str, is_group: int, parent: str) -> None:
	"""Cria o Item Group se não existir.

	Se já existir (ex: "Vacinas" criado pelo imunocare_clinic_ext), a função
	retorna sem alterações — preserva o parent_item_group original para não
	quebrar a hierarquia de estoque já configurada.

	O campo show_in_website é um Custom Field adicionado pelo webshop.
	Só é definido se o webshop já estiver instalado.
	"""
	if frappe.db.exists("Item Group", name):
		return

	doc_data: dict = {
		"doctype": "Item Group",
		"item_group_name": name,
		"is_group": is_group,
		"parent_item_group": parent,
	}

	# show_in_website é Custom Field do webshop — só existirá após install-app webshop
	if frappe.db.exists("Custom Field", {"dt": "Item Group", "fieldname": "show_in_website"}):
		doc_data["show_in_website"] = 1

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

	for item in items:
		section = _resolve_section(item.item_group)
		if not section:
			ignorados += 1
			continue
		_upsert_website_item(item, section)
		publicados += 1

	frappe.logger(_LOG_TITLE).info(
		f"setup_catalogo: {publicados} Website Item(s) publicados, "
		f"{ignorados} Item(s) ignorados (sem mapeamento de seção)."
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
