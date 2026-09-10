"""Task 2.3 (spec loja-agendar-em-toda-pagina) — categoria E termo de busca
devem combinar com E (interseção), não OU. Ver
``imunocare_ecommerce.catalogo.api._combinar_busca_e_categoria`` e
``_codigos_website_item_da_categoria``.

Fixture isolada (2 Item Group + 3 Website Item próprios) em vez de usar
categorias/itens reais do catálogo (``Vacinas``/``Brincos``) — evita
depender de dados que podem mudar e, principalmente, evita o padrão de
"fixture com nome fixo colide entre rodadas de teste" já documentado no
projeto (ver memória ``feedback_frappe_test_commit_appointment`` — a
colisão da "Ana Concorrência" com CPF fixo). Dois cuidados extras,
aprendidos ao rodar ESTE MESMO teste duas vezes seguidas durante o
desenvolvimento (achado, não hipotético):

1. ``Website Item`` tem ``autoname: naming_series``
   (``webshop/webshop/doctype/website_item/website_item.json:4``) — o
   ``name`` (docname) NÃO é o ``item_code`` (vira algo tipo ``WEB-ITM-0152``,
   independente do que você passou no dict de criação). Apagar por
   ``item_code`` (como ``tests/test_carrinho.py`` já faz — mesmo padrão,
   mesmo bug, fora do escopo desta task corrigir lá) é um no-op silencioso
   guardado pelo `if frappe.db.exists(...)`: nunca lança, só nunca apaga —
   confirmado ao vivo (rodei o teste 2x, sobraram 6 ``Website Item`` orfãos
   com o ``item_code`` certo mas nome de doc diferente). Aqui o cleanup usa
   o ``.name`` DEVOLVIDO pelo `.insert()`, não o `item_code`.
2. Termos de busca únicos por rodada (``f"alfaimuntst{sufixo}"``, não
   "alfa" cru): mesmo com o cleanup correto, um teste de BUSCA por
   substring é o pior caso pra colisão de fixture entre rodadas — um termo
   genérico poderia casar com lixo de uma rodada anterior (ou com produto
   real do catálogo) e mascarar um bug. O sufixo aleatório dentro do próprio
   termo buscado garante que só ESTA classe, desta rodada, pode bater.
"""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.catalogo.api import get_product_filter_data_loja


def _apagar_definitivamente(doctype: str, name: str) -> None:
	if frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		frappe.db.commit()


class TestBuscaMaisCategoriaCombinaComE(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		sufixo = frappe.generate_hash(length=6)
		cls._sufixo = sufixo
		cls._termo_alfa = f"alfaimuntst{sufixo}"
		cls._termo_beta = f"betaimuntst{sufixo}"
		cls._grupo_a = f"Teste Busca A {sufixo}"
		cls._grupo_b = f"Teste Busca B {sufixo}"
		cls._website_item_names = []  # docnames reais (naming_series), pro cleanup

		for nome in (cls._grupo_a, cls._grupo_b):
			frappe.get_doc(
				{
					"doctype": "Item Group",
					"item_group_name": nome,
					"is_group": 0,
					"parent_item_group": "All Item Groups",
				}
			).insert(ignore_permissions=True)

		# item_A: grupo A, nome bate com o termo "alfa" -> alvo do caso 1
		# (search=alfa & grupo=A).
		cls._item_a = cls._novo_website_item("A", cls._grupo_a, f"Produto {cls._termo_alfa} Teste")
		# item_B: grupo B, nome TAMBÉM bate com "alfa" -> prova que
		# item_group=A exclui item de outro grupo mesmo batendo a busca.
		cls._item_b = cls._novo_website_item("B", cls._grupo_b, f"Produto {cls._termo_alfa} Teste")
		# item_C: grupo A, nome bate com "beta" -> prova que search=alfa
		# exclui item do MESMO grupo que não bate o termo.
		cls._item_c = cls._novo_website_item("C", cls._grupo_a, f"Produto {cls._termo_beta} Teste")

	@classmethod
	def _novo_website_item(cls, rotulo: str, item_group: str, nome: str) -> str:
		item_code = f"TESTE-BUSCA-{rotulo}-{cls._sufixo}"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": item_code,
				"item_name": nome,
				"item_group": item_group,
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		website_item = frappe.get_doc(
			{
				"doctype": "Website Item",
				"item_code": item_code,
				"web_item_name": nome,
				"item_name": nome,
				"item_group": item_group,
				"published": 1,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		cls._website_item_names.append(website_item.name)
		return item_code

	@classmethod
	def tearDownClass(cls):
		for website_item_name in cls._website_item_names:
			_apagar_definitivamente("Website Item", website_item_name)
		for item_code in (cls._item_a, cls._item_b, cls._item_c):
			_apagar_definitivamente("Item", item_code)
		_apagar_definitivamente("Item Group", cls._grupo_a)
		_apagar_definitivamente("Item Group", cls._grupo_b)
		super().tearDownClass()

	def _codigos(self, **query_args) -> set[str]:
		query_args.setdefault("field_filters", {})
		query_args.setdefault("attribute_filters", {})
		query_args.setdefault("start", 0)
		resultado = get_product_filter_data_loja(query_args=query_args)
		return {item["item_code"] for item in resultado["items"]}

	def test_busca_e_categoria_juntas_so_traz_a_intersecao(self):
		"""Caso 1 do curl manual: search=vacina&item_group=Brincos -> 0 (no
		catálogo real); aqui: termo "alfa" & grupo=A -> só item_A (item_B é
		doutro grupo, item_C não bate a busca)."""
		self.assertEqual(self._codigos(search=self._termo_alfa, item_group=self._grupo_a), {self._item_a})

	def test_busca_sem_bater_categoria_devolve_vazio(self):
		"""Termo que só existe noutra categoria (ou nenhuma) + item_group
		que não tem esse termo -> 0 itens (não "tudo", que seria o bug do
		OR)."""
		self.assertEqual(self._codigos(search=self._termo_alfa, item_group=self._grupo_b), {self._item_b})
		self.assertEqual(self._codigos(search=self._termo_beta, item_group=self._grupo_b), set())

	def test_categoria_sozinha_sem_busca_continua_igual(self):
		"""Caso 3 do curl manual: item_group sozinho (sem search) não muda —
		grupo A tem item_A (alfa) E item_C (beta), os dois devem aparecer."""
		self.assertEqual(self._codigos(item_group=self._grupo_a), {self._item_a, self._item_c})

	def test_busca_sozinha_sem_categoria_continua_igual(self):
		"""Caso 4 do curl manual: search sozinho (sem item_group) não muda —
		o termo "alfa" bate em item_A (grupo A) e item_B (grupo B), das duas
		categorias."""
		self.assertEqual(self._codigos(search=self._termo_alfa), {self._item_a, self._item_b})
