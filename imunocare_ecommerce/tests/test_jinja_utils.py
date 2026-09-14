"""Hotfix 2026-09-13: ``injetar_mensagens_loja`` roda no hook
``update_website_context`` — que dispara para TODA página do renderer de
templates do Frappe, inclusive ``/app`` (desk). O boot do desk já vem com
``__messages`` completo (``frappe.boot.get_bootinfo``, ~19 mil chaves); sem
guarda, o dicionário de ~77 chaves da loja sobrescrevia o do desk inteiro,
deixando a barra lateral/botões em inglês em produção.

Este teste cobre só o guarda por conteúdo (não a rota — ver docstring da
função): boot sem ``__messages`` recebe o dicionário da loja; boot que já
tem ``__messages`` permanece intacto.
"""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.catalogo.jinja_utils import injetar_mensagens_loja


class TestInjetarMensagensLoja(FrappeTestCase):
	def test_injeta_quando_boot_sem_messages(self):
		context = frappe._dict(boot={})

		with patch(
			"imunocare_ecommerce.catalogo.jinja_utils.imun_mensagens_loja",
			return_value={"Add to Cart": "Adicionar ao carrinho"},
		):
			injetar_mensagens_loja(context)

		self.assertEqual(
			context.boot["__messages"],
			{"Add to Cart": "Adicionar ao carrinho"},
			"página web pública (boot sem __messages) tem que receber o "
			"dicionário da loja",
		)

	def test_nao_sobrescreve_boot_do_desk(self):
		context = frappe._dict(boot={"__messages": {"Accounting": "Contabilidade"}})

		with patch(
			"imunocare_ecommerce.catalogo.jinja_utils.imun_mensagens_loja",
			return_value={"Add to Cart": "Adicionar ao carrinho"},
		):
			injetar_mensagens_loja(context)

		self.assertEqual(
			context.boot["__messages"],
			{"Accounting": "Contabilidade"},
			"boot do desk (/app) já vem com __messages completo — não pode "
			"ser sobrescrito pelo dicionário de ~77 chaves da loja",
		)
