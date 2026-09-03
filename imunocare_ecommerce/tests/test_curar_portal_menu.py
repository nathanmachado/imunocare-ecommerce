"""Atividade F do spec 2026-09-02-loja-mitigacao-fluxos.md — curadoria do
portal /me (Portal Settings) para o cliente da loja.

``Portal Menu Item`` (child table de ``Portal Settings.menu``) não tem campo
"hidden" — o campo real é ``enabled`` (Check): ``enabled=0`` é quem
efetivamente esconde o item do menu de /me.

Fix da revisão 2026-09-03 (footgun apontado pelo CTO): a curadoria virou
ONE-SHOT (``_FLAG_PORTAL_MENU_CURADO``, via ``frappe.db.get_default``/
``set_default``) — sem isso, o after_migrate reaplicava ``enabled=0`` a CADA
migrate e desfazia silenciosamente qualquer reabilitação manual do dono pelo
Desk."""

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.loja.setup import (
	_FLAG_PORTAL_MENU_CURADO,
	_PORTAL_ROTAS_MANTER,
	_PORTAL_ROTAS_OCULTAR,
	curar_portal_menu,
)


class TestCurarPortalMenu(FrappeTestCase):
	def setUp(self):
		# Snapshot do estado real de "enabled" para restaurar no tearDown —
		# este teste roda contra o Portal Settings de VERDADE do bench (é um
		# Singleton, não dá para isolar num doc novo).
		settings = frappe.get_single("Portal Settings")
		self._estado_antes = {item.route: item.get("enabled") for item in settings.menu}
		self._flag_antes = frappe.db.get_default(_FLAG_PORTAL_MENU_CURADO)
		# Cada teste começa "nunca curado" — sem isso, uma execução anterior
		# (inclusive a rodada manual já feita neste bench) faria a curadoria
		# ser pulada silenciosamente e os testes passariam por acidente.
		frappe.defaults.clear_default(_FLAG_PORTAL_MENU_CURADO)

	def tearDown(self):
		settings = frappe.get_single("Portal Settings")
		mudou = False
		for item in settings.menu:
			original = self._estado_antes.get(item.route)
			if item.get("enabled") != original:
				item.enabled = original
				mudou = True
		if mudou:
			settings.flags.ignore_permissions = True
			settings.save(ignore_permissions=True)

		frappe.defaults.clear_default(_FLAG_PORTAL_MENU_CURADO)
		if self._flag_antes:
			frappe.db.set_default(_FLAG_PORTAL_MENU_CURADO, self._flag_antes)

	def test_oculta_itens_irrelevantes_e_mantem_os_essenciais(self):
		curar_portal_menu()

		settings = frappe.get_single("Portal Settings")
		por_rota = {item.route: item for item in settings.menu}

		for rota in _PORTAL_ROTAS_OCULTAR:
			if rota in por_rota:
				self.assertFalse(por_rota[rota].enabled, f"{rota} deveria estar desabilitado (oculto)")

		for rota in _PORTAL_ROTAS_MANTER:
			if rota in por_rota:
				# Nunca é FORÇADO a habilitado — só não é tocado; se já estava
				# habilitado (estado nativo/comum), continua.
				self.assertEqual(
					por_rota[rota].enabled,
					self._estado_antes.get(rota),
					f"{rota} não deveria ser alterado por esta curadoria",
				)

	def test_marca_a_flag_de_execucao_unica(self):
		self.assertFalse(frappe.db.get_default(_FLAG_PORTAL_MENU_CURADO))
		curar_portal_menu()
		self.assertTrue(frappe.db.get_default(_FLAG_PORTAL_MENU_CURADO))

	def test_idempotente_rodar_duas_vezes_nao_quebra(self):
		curar_portal_menu()
		curar_portal_menu()

		settings = frappe.get_single("Portal Settings")
		por_rota = {item.route: item for item in settings.menu}
		for rota in _PORTAL_ROTAS_OCULTAR:
			if rota in por_rota:
				self.assertFalse(por_rota[rota].enabled)

	def test_nunca_reabilita_item_ja_desabilitado_por_outro_motivo(self):
		# Um item de _PORTAL_ROTAS_MANTER que o operador já tinha desabilitado
		# manualmente por outra razão não é reaberto por esta curadoria.
		settings = frappe.get_single("Portal Settings")
		alvo = None
		for item in settings.menu:
			if item.route in _PORTAL_ROTAS_MANTER:
				alvo = item.route
				item.enabled = 0
				break
		if not alvo:
			self.skipTest("nenhuma rota de _PORTAL_ROTAS_MANTER presente neste bench")
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)

		curar_portal_menu()

		settings = frappe.get_single("Portal Settings")
		por_rota = {item.route: item for item in settings.menu}
		self.assertFalse(por_rota[alvo].enabled)

	def test_one_shot_nao_desfaz_reabilitacao_manual_do_dono_no_migrate_seguinte(self):
		"""Reproduz exatamente o footgun apontado pelo CTO: 1ª execução
		esconde; o dono reabilita manualmente pelo Desk; uma 2ª "chamada de
		migrate" NÃO pode desfazer a escolha do dono."""
		curar_portal_menu()

		settings = frappe.get_single("Portal Settings")
		por_rota = {item.route: item for item in settings.menu}
		alvo = next((r for r in _PORTAL_ROTAS_OCULTAR if r in por_rota), None)
		if not alvo:
			self.skipTest("nenhuma rota de _PORTAL_ROTAS_OCULTAR presente neste bench")
		self.assertFalse(por_rota[alvo].enabled, "precondição: a 1ª execução escondeu")

		# O dono reabilita manualmente pelo Desk.
		por_rota[alvo].enabled = 1
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)

		# Simula o migrate seguinte chamando curar_portal_menu() de novo.
		curar_portal_menu()

		settings = frappe.get_single("Portal Settings")
		por_rota = {item.route: item for item in settings.menu}
		self.assertTrue(
			por_rota[alvo].enabled,
			"one-shot: a 2ª execução não pode desfazer a reabilitação manual do dono",
		)
