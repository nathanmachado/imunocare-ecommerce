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

_CANAIS = ("email", "whatsapp")


def _texto(valor) -> str:
	"""Normaliza um campo de texto vindo do payload do cliente.

	Endpoint ``allow_guest`` não pode confiar no formato do que chega: recusa
	tipo inesperado (número, lista, dict) em vez de deixar estourar mais
	adiante — ``str.partition``, ``re.sub``, ``escape_html`` etc. todos
	esperam string e nenhum deles trata o erro sozinho.
	"""
	if valor is None:
		return ""
	if not isinstance(valor, str):
		frappe.throw(_("Dados de cadastro inválidos."), title=_("Requisição inválida"))
	return valor


def _como_dict(valor) -> dict:
	"""Converte o payload recebido (JSON string ou dict) em dict.

	Recusa JSON malformado e JSON que decodifica para algo que não é um
	objeto (ex.: ``"[1,2,3]"`` vira lista, não dict) — ambos estourariam mais
	adiante sem essa checagem explícita.
	"""
	if valor is None:
		return {}
	if isinstance(valor, str):
		try:
			valor = json.loads(valor) if valor else {}
		except (TypeError, ValueError):
			frappe.throw(_("Dados de cadastro inválidos."), title=_("Requisição inválida"))
	if not isinstance(valor, dict):
		frappe.throw(_("Dados de cadastro inválidos."), title=_("Requisição inválida"))
	return dict(valor)


def _so_digitos(valor) -> str:
	return "".join(c for c in _texto(valor) if c.isdigit())


@frappe.whitelist(allow_guest=True)
def canais_disponiveis() -> dict:
	return canais.disponiveis()


def _resolver_envio(canal: str, dados: dict) -> tuple[str, str]:
	"""Devolve ``(canal_efetivo, destino)`` — para onde o código realmente vai.

	CPF novo (nenhum Patient dono): usa o canal e o contato exatamente como a
	pessoa digitou.

	CPF já cadastrado: o contato SEMPRE vem do cadastro, nunca do que foi
	digitado — quem sabe o CPF de outra pessoa não consegue redirecionar o
	código para o próprio contato (isso seria takeover de conta: a Task 5 usa
	exatamente este fluxo para vincular User↔Patient). A ordem de prioridade:

	1. O contato do canal pedido, se estiver preenchido no cadastro.
	2. Senão, o contato do OUTRO canal do MESMO cadastro, se preenchido —
	   padrão bancário: o cliente recebe o destino mascarado do canal que
	   realmente foi usado, mesmo que tenha pedido outro. ``canal_efetivo``
	   muda de acordo, para que quem chama (``solicitar_codigo``) confira
	   disponibilidade e envie pelo canal certo.
	3. Se nem e-mail nem celular estiverem preenchidos no cadastro, recusa —
	   caminho de EXCEÇÃO (nunca um fallback silencioso), com mensagem
	   genérica que não confirma que aquele CPF existe.
	"""
	cpf = _so_digitos(dados.get("cpf"))
	contato = (
		frappe.db.get_value("Patient", {"cpf": cpf}, ["email", "mobile"], as_dict=True)
		if cpf
		else None
	)

	if not contato:
		destino = _texto(dados.get("email")) if canal == "email" else _texto(dados.get("celular"))
		return canal, destino

	campo_pedido = "email" if canal == "email" else "mobile"
	if contato.get(campo_pedido):
		return canal, contato[campo_pedido]

	canal_outro = "whatsapp" if canal == "email" else "email"
	campo_outro = "mobile" if canal == "email" else "email"
	if contato.get(campo_outro):
		return canal_outro, contato[campo_outro]

	frappe.throw(
		_("Não foi possível enviar o código de verificação. Procure a clínica."),
		title=_("Verificação indisponível"),
	)


def _destino_de_envio(canal: str, dados: dict) -> str:
	"""Só o destino (ver ``_resolver_envio`` para o canal efetivamente usado,
	que pode divergir do pedido quando o CPF já é de um cadastro)."""
	return _resolver_envio(canal, dados)[1]


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=600)
def solicitar_codigo(canal: str, dados: str | dict) -> dict:
	if not isinstance(canal, str) or canal not in _CANAIS:
		frappe.throw(_("Canal de verificação inválido."), title=_("Requisição inválida"))

	dados = _como_dict(dados)

	# canal_efetivo pode divergir do pedido (ver _resolver_envio) — toda
	# checagem daqui em diante (disponibilidade, envio, máscara) usa o
	# efetivo, nunca o originalmente pedido.
	canal_efetivo, destino = _resolver_envio(canal, dados)

	if not destino:
		frappe.throw(
			_("Informe um e-mail válido.")
			if canal_efetivo == "email"
			else _("Informe um celular válido.")
		)

	if not canais.disponiveis().get(canal_efetivo):
		frappe.throw(_("Este canal de verificação está indisponível no momento."))

	# O código só existe aqui e no envio: nunca na resposta, nunca em log.
	valor = codigo.emitir(frappe.session.sid, dados)
	canais.enviar(canal_efetivo, destino, valor, _texto(dados.get("nome")))

	return {
		"destino_mascarado": canais.mascarar(canal_efetivo, destino),
		"expira_em": codigo.TTL_PADRAO,
	}
