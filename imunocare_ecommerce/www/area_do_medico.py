"""Página "Área do Médico Parceiro" — change ``area-do-medico-parceiro``,
task 3.1 (D6, D8, D9).

Server-rendered, sem JS/endpoint próprio: a página só apresenta o que
``imunocare_clinic_ext.area_medico`` (task 2.1) já resolve — quem é o médico
da sessão e o que ele pode ver. Nenhum parâmetro de médico é lido do
request; o médico é SEMPRE ``frappe.session.user``, resolvido no servidor.

Reuso: mesmo padrão de controle de acesso de ``frappe/www/app.py``
(Guest -> ``frappe.redirect("/login?redirect-to=...")``) e de
``frappe/www/me.py`` (``context.show_sidebar``); o link no menu lateral é o
item nativo ``standard_portal_menu_items`` filtrado pela role do usuário
(``hooks.py``) — a role NÃO é o controle de acesso (D6): quem decide é o
cadastro do médico, sempre aqui no servidor.

Import defensivo do ``imunocare_clinic_ext`` (mesmo padrão de
``agendamento.booking``, ex. ``patient_hooks.is_valid_cpf``):
``imunocare_ecommerce`` não declara ``imunocare_clinic_ext`` em
``required_apps`` — se o app clínico não estiver instalado, a página nega
acesso em vez de quebrar com 500.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

no_cache = 1

_PERIODO_PADRAO_DIAS = 90


def _parse_data(valor):
	"""``getdate`` de um valor de ``form_dict``, ou ``None`` se vazio/inválido
	(nunca lança — data inválida cai no padrão, não em erro 500)."""
	if not valor:
		return None
	try:
		return getdate(valor)
	except Exception:
		return None


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = True
	context.title = _("Área do Médico Parceiro")

	if frappe.session.user == "Guest":
		frappe.redirect("/login?redirect-to=/area-do-medico")

	try:
		from imunocare_clinic_ext.area_medico import (
			aplicacoes_do_medico,
			medico_parceiro_da_sessao,
		)
	except ImportError:
		aplicacoes_do_medico = None
		medico_parceiro_da_sessao = None

	practitioner = medico_parceiro_da_sessao() if medico_parceiro_da_sessao else None
	if not practitioner:
		frappe.throw(_("Você não tem acesso a esta página."), frappe.PermissionError)

	# Nenhum parâmetro de médico é lido do request — só ``de``/``ate``. Um
	# eventual ``form_dict["practitioner"]`` (ou qualquer outro campo) é
	# ignorado; o médico já foi resolvido acima, exclusivamente da sessão.
	de = _parse_data(frappe.form_dict.get("de"))
	ate = _parse_data(frappe.form_dict.get("ate"))

	if de is None or ate is None:
		ate = getdate(nowdate())
		de = add_days(ate, -_PERIODO_PADRAO_DIAS)

	context.de = de
	context.ate = ate

	if de > ate:
		context.aviso = _("A data inicial não pode ser depois da data final.")
		context.aplicacoes = []
	else:
		context.aviso = None
		context.aplicacoes = aplicacoes_do_medico(practitioner, de, ate)

	return context
