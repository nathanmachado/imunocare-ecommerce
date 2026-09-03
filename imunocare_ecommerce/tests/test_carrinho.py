"""Atividade C do spec 2026-09-02-loja-mitigacao-fluxos.md — serviço (item
agendável) nunca entra no carrinho da loja. Sintoma 3 do diagnóstico: com o
catálogo 100% serviços, qualquer item que entrasse no carrinho desembocava
numa "Request for Quote"/cotação que o dono não quer — a raiz era a
AUSÊNCIA de guarda server-side (o front já esconde/troca o botão, mas nada
impedia um POST direto de shopping_cart_update)."""

from __future__ import annotations

from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.catalogo import carrinho


def _apagar_definitivamente(doctype: str, name: str) -> None:
	if frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		frappe.db.commit()


class TestBloquearServicoNoCarrinhoUnitario(FrappeTestCase):
	"""Chama a guarda diretamente com um "doc" leve (frappe._dict) — cobre a
	regra sem depender de toda a maquinaria de validação do Quotation
	(impostos/preço/moeda), que não é o que este teste quer provar."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._appointment_type = frappe.get_doc(
			{
				"doctype": "Appointment Type",
				"appointment_type": "Teste Carrinho — Serviço",
				"allow_booking_for": "Practitioner",
				"default_duration": 30,
			}
		).insert(ignore_permissions=True)

		item_group = (
			"Todos os Grupos de Item" if frappe.db.exists("Item Group", "Todos os Grupos de Item") else "All Item Groups"
		)

		cls._item_code_servico = f"TESTE-CARRINHO-SERVICO-{frappe.generate_hash(length=6)}"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls._item_code_servico,
				"item_name": cls._item_code_servico,
				"item_group": item_group,
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		frappe.get_doc(
			{
				"doctype": "Website Item",
				"item_code": cls._item_code_servico,
				"web_item_name": cls._item_code_servico,
				"item_name": cls._item_code_servico,
				"published": 1,
				"imun_appointment_type": cls._appointment_type.name,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		cls._item_code_produto = f"TESTE-CARRINHO-PRODUTO-{frappe.generate_hash(length=6)}"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls._item_code_produto,
				"item_name": cls._item_code_produto,
				"item_group": item_group,
				"stock_uom": "Nos",
				"is_stock_item": 1,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		frappe.get_doc(
			{
				"doctype": "Website Item",
				"item_code": cls._item_code_produto,
				"web_item_name": cls._item_code_produto,
				"item_name": cls._item_code_produto,
				"published": 1,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

	@classmethod
	def tearDownClass(cls):
		_apagar_definitivamente("Website Item", cls._item_code_servico)
		_apagar_definitivamente("Item", cls._item_code_servico)
		_apagar_definitivamente("Website Item", cls._item_code_produto)
		_apagar_definitivamente("Item", cls._item_code_produto)
		_apagar_definitivamente("Appointment Type", cls._appointment_type.name)
		super().tearDownClass()

	def _quotation_fake(self, order_type: str, item_code: str):
		# SimpleNamespace, não frappe._dict: ``dict.items`` já é um método de
		# instância do dict — ``frappe._dict(items=[...]).items`` resolveria
		# para o MÉTODO ``dict.items`` (lookup normal de atributo encontra a
		# classe antes do fallback ``__getattr__ = dict.get``), nunca para o
		# valor. Documentos reais do Frappe não têm esse problema (não
		# herdam de ``dict``) — este é só um detalhe do duble de teste.
		return SimpleNamespace(
			order_type=order_type,
			items=[SimpleNamespace(item_code=item_code, item_name=item_code)],
		)

	def test_servico_no_carrinho_web_e_recusado(self):
		doc = self._quotation_fake("Shopping Cart", self._item_code_servico)
		with self.assertRaises(frappe.ValidationError) as cm:
			carrinho.bloquear_servico_no_carrinho(doc)
		mensagem = str(cm.exception)
		self.assertIn("Agendar", mensagem)

	def test_produto_no_carrinho_web_continua_permitido(self):
		doc = self._quotation_fake("Shopping Cart", self._item_code_produto)
		# Não lança — item físico segue o caminho normal do webshop.
		carrinho.bloquear_servico_no_carrinho(doc)

	def test_servico_fora_do_carrinho_web_nao_e_afetado(self):
		# Cotação/orçamento manual da recepção (B2B, walk-in) — order_type
		# != "Shopping Cart": a guarda é NO-OP, nunca deve interferir.
		doc = self._quotation_fake("Sales", self._item_code_servico)
		carrinho.bloquear_servico_no_carrinho(doc)

	def test_item_code_inexistente_nao_quebra(self):
		# sinal_servico já é defensivo (nunca lança) — a guarda também não deve
		# quebrar diante de um item_code esquisito/removido no meio do caminho.
		doc = self._quotation_fake("Shopping Cart", "ITEM-QUE-NAO-EXISTE-JAMAIS")
		carrinho.bloquear_servico_no_carrinho(doc)


class TestBloquearServicoNoCarrinhoViaHook(FrappeTestCase):
	"""Fim a fim: prova que o hook `Quotation.validate` (hooks.py doc_events)
	realmente dispara a guarda ao inserir um Quotation de verdade — não só a
	função isolada."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._appointment_type = frappe.get_doc(
			{
				"doctype": "Appointment Type",
				"appointment_type": "Teste Carrinho Hook — Serviço",
				"allow_booking_for": "Practitioner",
				"default_duration": 30,
			}
		).insert(ignore_permissions=True)

		item_group = (
			"Todos os Grupos de Item" if frappe.db.exists("Item Group", "Todos os Grupos de Item") else "All Item Groups"
		)
		cls._item_code_servico = f"TESTE-CARRINHO-HOOK-SERVICO-{frappe.generate_hash(length=6)}"
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": cls._item_code_servico,
				"item_name": cls._item_code_servico,
				"item_group": item_group,
				"stock_uom": "Nos",
				"is_stock_item": 0,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		frappe.get_doc(
			{
				"doctype": "Website Item",
				"item_code": cls._item_code_servico,
				"web_item_name": cls._item_code_servico,
				"item_name": cls._item_code_servico,
				"published": 1,
				"imun_appointment_type": cls._appointment_type.name,
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

		cls._customer_name = f"Teste Carrinho Hook {frappe.generate_hash(length=6)}"
		frappe.get_doc(
			{
				"doctype": "Customer",
				"customer_name": cls._customer_name,
				"customer_type": "Individual",
			}
		).insert(ignore_permissions=True)

	@classmethod
	def tearDownClass(cls):
		_apagar_definitivamente("Customer", cls._customer_name)
		_apagar_definitivamente("Website Item", cls._item_code_servico)
		_apagar_definitivamente("Item", cls._item_code_servico)
		_apagar_definitivamente("Appointment Type", cls._appointment_type.name)
		super().tearDownClass()

	def _quotation_dict(self):
		return {
			"doctype": "Quotation",
			"quotation_to": "Customer",
			"party_name": self._customer_name,
			"order_type": "Shopping Cart",
			"transaction_date": frappe.utils.nowdate(),
			"currency": frappe.get_cached_value("Company", frappe.defaults.get_global_default("company"), "default_currency"),
			"selling_price_list": "Venda Padrão" if frappe.db.exists("Price List", "Venda Padrão") else frappe.get_all("Price List", filters={"selling": 1}, pluck="name")[0],
			"company": frappe.defaults.get_global_default("company"),
			"items": [
				{
					"item_code": self._item_code_servico,
					"item_name": self._item_code_servico,
					"qty": 1,
					"rate": 10,
					"uom": "Nos",
				}
			],
		}

	def test_insert_de_quotation_shopping_cart_com_servico_e_recusado(self):
		with self.assertRaises(frappe.ValidationError) as cm:
			frappe.get_doc(self._quotation_dict()).insert(ignore_permissions=True)
		self.assertIn("Agendar", str(cm.exception))
