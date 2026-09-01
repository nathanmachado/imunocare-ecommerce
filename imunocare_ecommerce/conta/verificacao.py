"""Endpoints da reserva como visitante.

O visitante navega e escolhe horário sem conta. Ao confirmar, verifica-se por
código e sai daqui LOGADO, com User e Patient criados — e só então o
agendamento é criado pela ``criar_agendamento`` de sempre, que continua
recusando Guest. Nenhum caminho novo cria agendamento sem usuário.

Organização do módulo:
- ``canais_disponiveis`` / ``solicitar_codigo``: Task 4 (este arquivo).
- ``confirmar_codigo_e_agendar`` + montagem de User/Patient: Task 5 (este arquivo).
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from imunocare_ecommerce.conta import canais, codigo
from imunocare_ecommerce.rate_limit import rate_limit

_CANAIS = ("email", "whatsapp")
MAIORIDADE = 18


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


# ---------------------------------------------------------------------------
# Confirmação do código: cria User + Patient e agenda (Task 5)
# ---------------------------------------------------------------------------


def _idade(dob) -> int | None:
	if not dob:
		return None
	nasc, hoje = getdate(dob), getdate(nowdate())
	if nasc > hoje:
		return None
	return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))


def _partir_nome(nome_completo: str) -> tuple[str, str, str]:
	"""'Ana Souza' -> ('Ana', '', 'Souza'). middle_name deixou de ser
	obrigatório justamente para o nome de duas palavras passar (ver
	imunocare_clinic_ext commit 141f3f2)."""
	partes = (nome_completo or "").split()
	if not partes:
		frappe.throw(_("Informe o nome completo."))
	primeiro = partes[0]
	ultimo = partes[-1] if len(partes) > 1 else ""
	meio = " ".join(partes[1:-1]) if len(partes) > 2 else ""
	return primeiro, meio, ultimo


def _montar_paciente(dados: dict, adulto_user: str):
	"""Monta (sem inserir) o Patient de QUEM VAI SER ATENDIDO.

	O user_id é sempre o do adulto verificado — é assim que o portal dele
	enxerga as consultas dos filhos. pais_nascimento não é setado aqui: o
	default do campo já entrega 'Brazil'.
	"""
	para_outro = bool(dados.get("para_outra_pessoa"))
	nome = dados.get("paciente_nome") if para_outro else dados.get("nome")
	cpf = _so_digitos(dados.get("paciente_cpf") if para_outro else dados.get("cpf"))
	dob = dados.get("paciente_dob") if para_outro else dados.get("dob")

	primeiro, meio, ultimo = _partir_nome(nome)
	p = frappe.new_doc("Patient")
	p.first_name = primeiro
	p.middle_name = meio
	p.last_name = ultimo
	p.sex = dados.get("paciente_sexo") if para_outro else dados.get("sexo")
	p.dob = getdate(dob) if dob else None
	p.cpf = cpf
	# Contato é sempre o do adulto: é ele que recebe lembrete e confirmação.
	p.mobile = dados.get("celular")
	p.email = dados.get("email")
	p.user_id = adulto_user
	p.invite_user = 0

	idade = _idade(dob)
	if idade is not None and idade < MAIORIDADE:
		p.nome_responsavel = dados.get("nome")
		p.cpf_responsavel = _so_digitos(dados.get("cpf"))
	return p


def _garantir_usuario(dados: dict) -> str:
	"""Cria (ou reaproveita) o Website User do adulto e o deixa logado.

	Fora de um request HTTP de verdade (job, teste, console) o Frappe nunca
	monta ``frappe.local.login_manager`` — ele só é criado no ciclo de
	``auth.validate_auth_via_hooks``/``LoginManager.__init__`` durante uma
	requisição real (``frappe/auth.py``). Chamar ``.login_as`` sem essa
	checagem estoura ``AttributeError`` nos testes e em qualquer chamada
	interna. Com request, delega ao login_manager (grava cookie de sessão,
	dispara ``on_session_creation`` etc.); sem request, ``frappe.set_user``
	troca só o contexto de execução do processo atual — suficiente para o
	restante desta função e para o ``criar_agendamento`` que vem a seguir.
	"""
	email = (dados.get("email") or "").strip().lower()
	if not frappe.db.exists("User", email):
		primeiro, meio, ultimo = _partir_nome(dados.get("nome"))
		u = frappe.new_doc("User")
		u.email = email
		u.first_name = primeiro
		u.middle_name = meio
		u.last_name = ultimo
		u.mobile_no = dados.get("celular")
		u.user_type = "Website User"
		u.send_welcome_email = 0
		u.flags.ignore_permissions = True
		u.insert(ignore_permissions=True)
		papel = frappe.get_single_value("Portal Settings", "default_role")
		if papel:
			u.add_roles(papel)
	# A sessão precisa estar gravada antes de login_as — mesmo cuidado de
	# frappe/core/api/user_invitation.py:150.
	frappe.db.commit()  # nosemgrep

	login_manager = getattr(frappe.local, "login_manager", None)
	if login_manager is not None:
		login_manager.login_as(email)
	else:
		frappe.set_user(email)
	return email


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=600)
def confirmar_codigo_e_agendar(
	codigo: str,
	appointment_date: str,
	appointment_time: str,
	item_code: str | None = None,
	appointment_type: str | None = None,
	practitioner: str | None = None,
	modalidade: str | None = None,
	session_id: str | None = None,
) -> dict:
	from imunocare_ecommerce.agendamento.booking import criar_agendamento
	from imunocare_ecommerce.conta.codigo import conferir

	dados = conferir(frappe.session.sid, codigo)
	usuario = _garantir_usuario(dados)

	cpf = _so_digitos(
		dados.get("paciente_cpf") if dados.get("para_outra_pessoa") else dados.get("cpf")
	)
	paciente = frappe.db.get_value("Patient", {"cpf": cpf}, "name")
	if paciente:
		if not frappe.db.get_value("Patient", paciente, "user_id"):
			frappe.db.set_value("Patient", paciente, "user_id", usuario, update_modified=False)
	else:
		doc = _montar_paciente(dados, adulto_user=usuario)
		doc.insert(ignore_permissions=True)
		paciente = doc.name

	# SEMPRE explícito: _resolver_paciente busca por {"user_id": user} e
	# devolve UM paciente qualquer entre os vinculados — o que agendaria a
	# vacina do filho mais velho no nome do caçula quando a mesma conta tem
	# dois filhos cadastrados.
	resultado = criar_agendamento(
		appointment_date=appointment_date,
		appointment_time=appointment_time,
		item_code=item_code,
		appointment_type=appointment_type,
		practitioner=practitioner,
		patient=paciente,
		modalidade=modalidade,
		session_id=session_id,
	)
	resultado["conta_criada"] = True
	return resultado
