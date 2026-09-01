"""Endpoints da reserva como visitante.

O visitante navega e escolhe horário sem conta. Ao confirmar, verifica-se por
código e sai daqui LOGADO, com User e Patient criados — e só então o
agendamento é criado pela ``criar_agendamento`` de sempre, que continua
recusando Guest. Nenhum caminho novo cria agendamento sem usuário.

Organização do módulo (a Task 5 acrescenta funções aqui):
- ``canais_disponiveis`` / ``solicitar_codigo``: Task 4 (este arquivo).
- confirmação do código + criação de User/Patient: Task 5.
"""

from __future__ import annotations

import json

import frappe
from frappe import _

from imunocare_ecommerce.conta import canais, codigo
from imunocare_ecommerce.rate_limit import rate_limit


def _como_dict(valor) -> dict:
	if isinstance(valor, str):
		valor = json.loads(valor or "{}")
	return dict(valor or {})


def _so_digitos(valor: str | None) -> str:
	return "".join(c for c in (valor or "") if c.isdigit())


@frappe.whitelist(allow_guest=True)
def canais_disponiveis() -> dict:
	return canais.disponiveis()


def _destino_de_envio(canal: str, dados: dict) -> str:
	"""Para onde o código vai.

	Se o CPF já pertence a um Patient, o código vai para o contato DO CADASTRO,
	nunca para o que foi digitado. Quem digitou CPF alheio não recebe nada;
	quem é o dono recebe e vincula a conta ao cadastro que já existia.
	"""
	campo = "email" if canal == "email" else "mobile"
	cpf = _so_digitos(dados.get("cpf"))
	if cpf:
		existente = frappe.db.get_value("Patient", {"cpf": cpf}, campo)
		if existente:
			return existente
	return dados.get("email") if canal == "email" else dados.get("celular")


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=600)
def solicitar_codigo(canal: str, dados: str | dict) -> dict:
	dados = _como_dict(dados)

	if not canais.disponiveis().get(canal):
		frappe.throw(_("Este canal de verificação está indisponível no momento."))

	destino = _destino_de_envio(canal, dados)
	if not destino:
		frappe.throw(
			_("Informe um e-mail válido.")
			if canal == "email"
			else _("Informe um celular válido.")
		)

	# O código só existe aqui e no envio: nunca na resposta, nunca em log.
	valor = codigo.emitir(frappe.session.sid, dados)
	canais.enviar(canal, destino, valor, dados.get("nome") or "")

	return {
		"destino_mascarado": canais.mascarar(canal, destino),
		"expira_em": codigo.TTL_PADRAO,
	}
