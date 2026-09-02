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
import re
import secrets

import frappe
from frappe import _
from frappe.utils import getdate, nowdate

from imunocare_ecommerce.conta import canais, codigo
from imunocare_ecommerce.rate_limit import rate_limit

_CANAIS = ("email", "whatsapp")
MAIORIDADE = 18
_RE_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _msg_envio_indisponivel() -> str:
	"""Item 4 da revisão 2026-09-01: uma ÚNICA mensagem para os dois caminhos
	que terminam sem destino para enviar o código — CPF novo sem contato
	digitado E CPF de um Patient já cadastrado sem e-mail/celular
	preenchidos. Duas mensagens diferentes ali seriam um oráculo (revelariam
	se o CPF existe). Função (não constante de módulo) porque ``_()``
	depende do idioma da requisição corrente — resolver no import fixaria a
	tradução do processo, não da requisição."""
	return _("Não foi possível enviar o código de verificação. Procure a clínica.")


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


def _formato_valido(canal: str, dados: dict) -> bool:
	"""Item 5 da revisão 2026-09-02: só o FORMATO do que foi digitado, nunca
	consulta nada (nem o CPF) — por isso é seguro rodar isto ANTES de
	``_resolver_envio``. A mensagem que ``solicitar_codigo`` mostra quando
	isto falha depende só do que a pessoa digitou, então não é um oráculo de
	CPF: um e-mail/celular mal formatado recebe a mesma recusa não importa
	se o CPF digitado já existe ou não."""
	if canal == "email":
		return bool(_RE_EMAIL.match(_texto(dados.get("email")).strip()))
	return len(_so_digitos(dados.get("celular"))) in (10, 11)


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
	   caminho de EXCEÇÃO (nunca um fallback silencioso), com a MESMA
	   mensagem genérica que ``solicitar_codigo`` usa para "não informou
	   contato" (ver ``_msg_envio_indisponivel``): duas mensagens diferentes
	   aqui dariam para inferir que aquele CPF existe — exatamente o que o
	   spec proíbe ("nunca revelar se um e-mail ou CPF já existe"). Note que
	   ``solicitar_codigo`` já validou o FORMATO do que foi digitado (item 5
	   da revisão 2026-09-02, ``_formato_valido``) ANTES de chamar esta
	   função — daqui em diante toda mensagem é essa genérica única, nunca
	   "Informe um e-mail válido." (essa já foi decidida lá atrás, sem tocar
	   CPF nenhum).
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

	frappe.throw(_msg_envio_indisponivel(), title=_("Verificação indisponível"))


def _destino_de_envio(canal: str, dados: dict) -> str:
	"""Só o destino (ver ``_resolver_envio`` para o canal efetivamente usado,
	que pode divergir do pedido quando o CPF já é de um cadastro)."""
	return _resolver_envio(canal, dados)[1]


def _descartar_verificacao_anterior(verificacao_id_anterior) -> None:
	"""Apaga a chave da emissão anterior no botão "Reenviar código".

	Dado vindo do cliente: ausente, vazio ou de tipo estranho nunca estoura
	— só não descarta nada (``codigo.descartar`` de uma chave que não existe
	já é no-op silencioso no Redis, então nem checamos existência aqui).

	Descartar não é um jeito de invalidar a verificação de OUTRA pessoa: o
	token tem 256 bits de entropia (``secrets.token_urlsafe(32)``) — quem o
	possui já é, por construção, o dono daquela verificação. Não há consulta
	nem validação de "dono" a fazer; a posse do token já É a prova."""
	if isinstance(verificacao_id_anterior, str) and verificacao_id_anterior:
		codigo.descartar(verificacao_id_anterior)


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=5, seconds=600)
def solicitar_codigo(
	canal: str, dados: str | dict, verificacao_id_anterior: str | None = None
) -> dict:
	if not isinstance(canal, str) or canal not in _CANAIS:
		frappe.throw(_("Canal de verificação inválido."), title=_("Requisição inválida"))

	dados = _como_dict(dados)

	# Item 5 da revisão 2026-09-02: valida o FORMATO do contato ANTES de
	# qualquer consulta ao CPF. A resposta desta checagem depende só do que
	# a pessoa digitou (nunca do estado de cadastro) — não é um oráculo, e
	# devolve de volta a mensagem específica que ajuda o caso comum (erro de
	# digitação). Ordem obrigatória: formato -> CPF -> destino -> daí em
	# diante SÓ mensagem genérica (ver _msg_envio_indisponivel).
	if not _formato_valido(canal, dados):
		frappe.throw(
			_("Informe um e-mail válido.") if canal == "email" else _("Informe um celular válido."),
			title=_("Requisição inválida"),
		)

	# canal_efetivo pode divergir do pedido (ver _resolver_envio) — toda
	# checagem daqui em diante (disponibilidade, envio, máscara) usa o
	# efetivo, nunca o originalmente pedido.
	canal_efetivo, destino = _resolver_envio(canal, dados)

	if not destino:
		# Mesma mensagem de _resolver_envio quando o CPF já cadastrado não
		# tem contato (item 4 da revisão 2026-09-01) — texto diferente
		# aqui era um oráculo de existência de CPF (ver _msg_envio_indisponivel).
		frappe.throw(_msg_envio_indisponivel(), title=_("Verificação indisponível"))

	if not canais.disponiveis().get(canal_efetivo):
		frappe.throw(_("Este canal de verificação está indisponível no momento."))

	# canal_verificado/destino_verificado viajam DENTRO de "dados" para o
	# Redis: é o CONTATO PROVADO (o que _resolver_envio decidiu), nunca o
	# que a pessoa digitou. confirmar_codigo_e_agendar ancora a conta nisso
	# — nunca num campo do formulário que ninguém verificou (fix da revisão
	# 2026-09-01: canal whatsapp verificava o celular mas logava pelo
	# e-mail digitado, sem relação provada com quem verificou).
	dados["canal_verificado"] = canal_efetivo
	dados["destino_verificado"] = destino

	# A chave no Redis NUNCA é frappe.session.sid: todo visitante anônimo
	# compartilha o MESMO sid literal ("Guest") — usá-lo faria o segundo
	# visitante a pedir código colidir na MESMA chave com o primeiro, e cada
	# um confirmaria contra os dados do outro (incidente real, corrigido
	# nesta revisão). Token opaco por verificação, um NOVO por chamada —
	# mesmo padrão do ``tmp_id`` do 2FA nativo do Frappe. Ele viaja pro
	# cliente e volta em ``confirmar_codigo_e_agendar`` como
	# ``verificacao_id``; nunca é adivinhável (32 bytes de entropia).
	#
	# Cada emissão vira uma chave PRÓPRIA (não sobrescreve mais nenhuma
	# outra) — por isso o botão "Reenviar código" precisa mandar o
	# ``verificacao_id`` da emissão anterior de volta aqui em
	# ``verificacao_id_anterior``: sem descartá-la explicitamente, ela só
	# morreria pelo TTL (até 10 min depois), deixando o código antigo
	# válido e confirmável em paralelo com o novo.
	_descartar_verificacao_anterior(verificacao_id_anterior)
	verificacao_id = secrets.token_urlsafe(32)

	# O código só existe aqui e no envio: nunca na resposta, nunca em log.
	valor = codigo.emitir(verificacao_id, dados)
	canais.enviar(canal_efetivo, destino, valor, _texto(dados.get("nome")))

	# Item 4 da revisão 2026-09-02: a máscara devolvida é SEMPRE do que a
	# PESSOA DIGITOU para o canal pedido — nunca do contato efetivamente
	# usado (``destino``), que só diverge do digitado justamente quando o
	# CPF já era de um Patient cadastrado (ver _resolver_envio). Devolver a
	# máscara do cadastro nesse caso vazava (a) que aquele CPF já existe e
	# (b) a 1ª letra+domínio do e-mail da vítima, ou os 4 últimos dígitos do
	# celular — um oráculo bem mais barato que o do item 1 (5 CPFs por IP a
	# cada 10 min, sem precisar resolver OTP nenhum). Quando o CPF é novo,
	# ``digitado`` e ``destino`` são o MESMO valor (ver _resolver_envio) —
	# nenhuma perda de fidelidade no caso comum.
	digitado = dados.get("email") if canal == "email" else dados.get("celular")
	return {
		"verificacao_id": verificacao_id,
		"destino_mascarado": canais.mascarar(canal, _texto(digitado)),
		"expira_em": codigo.TTL_PADRAO,
	}


# ---------------------------------------------------------------------------
# Confirmação do código: cria User + Patient e agenda (Task 5)
# ---------------------------------------------------------------------------


def _validar_verificacao_id(verificacao_id) -> str:
	"""Recusa ``verificacao_id`` ausente/vazio/de tipo errado com a MESMA
	mensagem genérica de código expirado que ``codigo.conferir`` usa para
	chave inexistente no Redis — "token inválido" e "código expirado" são
	indistinguíveis de propósito para quem chama de fora."""
	if not isinstance(verificacao_id, str) or not verificacao_id:
		frappe.throw(
			_("Código expirado. Peça um novo."),
			codigo.CodigoInvalido,
			title=_("Código inválido"),
		)
	return verificacao_id


def _idade(dob) -> int | None:
	if not dob:
		return None
	nasc, hoje = getdate(dob), getdate(nowdate())
	if nasc > hoje:
		return None
	return hoje.year - nasc.year - ((hoje.month, hoje.day) < (nasc.month, nasc.day))


def _exigir_adulto(dados: dict) -> None:
	"""Quem CRIA A CONTA precisa ser maior de 18 — sempre, para si mesmo ou
	para outra pessoa.

	``dados["dob"]`` é sempre a data de nascimento de quem está se
	verificando (nunca a do paciente atendido quando
	``para_outra_pessoa=True`` — essa é ``paciente_dob``, um campo à parte).

	Fix da revisão 2026-09-01 (item 2): a checagem antiga só rodava para
	"para si mesmo" — quem marcava "a consulta é para outra pessoa" nunca
	tinha a própria idade verificada, então um menor conseguia criar conta e
	figurar como RESPONSÁVEL de um paciente (mesma classe do achado que a
	checagem "para si mesmo" já corrigia, só que fechada pela metade). Regra
	única e mais simples: sem ramo por ``para_outra_pessoa``, porque a
	idade que importa é sempre a de quem está criando a conta.
	"""
	idade = _idade(dados.get("dob"))
	if idade is not None and idade < MAIORIDADE:
		frappe.throw(
			_("Menores de 18 anos não podem se cadastrar. Procure a clínica para agendar com a ajuda de um responsável."),
			title=_("Cadastro não permitido"),
		)


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


def _logar(email: str) -> None:
	"""Deixa ``email`` logado no contexto atual.

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
	login_manager = getattr(frappe.local, "login_manager", None)
	if login_manager is not None:
		login_manager.login_as(email)
	else:
		frappe.set_user(email)


def _usuario_elegivel_para_login(nome_usuario: str) -> bool:
	"""IMPORTANTE 3 da revisão 2026-09-02: ``LoginManager.post_login`` NÃO
	valida ``enabled``/``user_type`` sozinho — quem chama ``login_as`` é
	quem tem que garantir isso. Sem esta checagem, um ``User`` desabilitado
	(ex-funcionário) ou um **System User** interno (existem contas de
	e-mail internas no próprio ERP) cujo e-mail/celular batesse com o
	digitado ganhava sessão pela loja, sem senha e sem 2FA, só por controlar
	aquele contato. Só ``Website User`` habilitado pode ganhar sessão por
	este fluxo de OTP."""
	info = frappe.db.get_value("User", nome_usuario, ["enabled", "user_type"], as_dict=True)
	return bool(info and info.enabled and info.user_type == "Website User")


def _criar_website_user(email: str, dados: dict, mobile_no: str | None = None):
	primeiro, meio, ultimo = _partir_nome(dados.get("nome"))
	u = frappe.new_doc("User")
	u.email = email
	u.first_name = primeiro
	u.middle_name = meio
	u.last_name = ultimo
	u.mobile_no = mobile_no if mobile_no is not None else dados.get("celular")
	u.user_type = "Website User"
	u.send_welcome_email = 0
	u.flags.ignore_permissions = True
	u.insert(ignore_permissions=True)
	# M1 da revisão 2026-09-02: o critério de aceite 3 exige a role nativa
	# "Patient" (healthcare.setup.default_portal_role) — ``Portal
	# Settings.default_role`` é uma config GERAL do site (vale para
	# QUALQUER Website User, não só quem se cadastra como paciente pela
	# loja) e pode ser trocada por outro motivo, sem relação com este fluxo,
	# quebrando o critério de aceite silenciosamente. Garante a role certa
	# direto, sem depender daquela config.
	if frappe.db.exists("Role", "Patient"):
		u.add_roles("Patient")
	return u


def _garantir_usuario_por_email(email_verificado: str, dados: dict) -> tuple[str, bool]:
	"""``email_verificado`` já é o contato PROVADO (``destino_verificado``
	de um ``canal_verificado == "email"``) — nunca o campo ``email`` cru do
	formulário, que pode divergir dele quando o CPF já era de um cadastro
	(``_resolver_envio`` manda o código para o e-mail do CADASTRO, não para
	o digitado)."""
	email = (email_verificado or "").strip().lower()
	if not email:
		frappe.throw(_("Não foi possível confirmar seu contato. Peça um novo código."))

	criado = False
	if not frappe.db.exists("User", email):
		_criar_website_user(email, dados)
		criado = True
	elif not _usuario_elegivel_para_login(email):
		# Item 3: mesma mensagem genérica de "peça um novo código" — nunca
		# confirma nem nega que aquele e-mail já é de uma conta (interna ou
		# desabilitada), só recusa o login.
		frappe.throw(_("Não foi possível confirmar seu contato. Peça um novo código."))
	# A sessão precisa estar gravada antes de login_as — mesmo cuidado de
	# frappe/core/api/user_invitation.py:150.
	frappe.db.commit()  # nosemgrep
	_logar(email)
	return email, criado


def _garantir_usuario_por_celular(celular_verificado: str, dados: dict) -> tuple[str, bool]:
	"""``celular_verificado`` é o WhatsApp que efetivamente recebeu e provou
	o código — a ÂNCORA da conta é ele, nunca o e-mail digitado no mesmo
	formulário (ninguém verificou aquele e-mail). Só cria conta nova com o
	e-mail digitado quando esse e-mail ainda não pertence a ninguém; se já
	pertencer, recusa — nunca loga em conta alheia por coincidência de
	e-mail digitado."""
	celular = _so_digitos(celular_verificado)
	if not celular:
		frappe.throw(_("Não foi possível confirmar seu contato. Peça um novo código."))

	existente = frappe.db.get_value("User", {"mobile_no": celular}, "name")
	if existente:
		if not _usuario_elegivel_para_login(existente):
			# Item 3: mesmo caso do ramo por e-mail — um celular que bate com
			# um User desabilitado/System User não ganha sessão.
			frappe.throw(_("Não foi possível confirmar seu contato. Peça um novo código."))
		# M3 da revisão 2026-09-02: mesmo cuidado do ramo "cria conta nova"
		# logo abaixo (sessão gravada ANTES de login_as, mesmo padrão de
		# frappe/core/api/user_invitation.py:150) — reaproveitar uma conta
		# existente também dispara login_as, não só criar uma nova.
		frappe.db.commit()  # nosemgrep
		_logar(existente)
		return existente, False

	email = (dados.get("email") or "").strip().lower()
	if not email:
		frappe.throw(_("Informe um e-mail para concluir o cadastro."))
	if frappe.db.exists("User", email):
		# O celular verificado não é o desta conta — nunca cria/loga usando
		# um e-mail que já pertence a outra pessoa (mensagem genérica: não
		# confirma nem nega que o e-mail digitado existe).
		#
		# Limitação CONSCIENTE (item 5 da revisão 2026-09-01): quem já provou
		# controlar um celular novo ainda consegue, testando e-mails
		# candidatos, distinguir "conta criada em silêncio" (sucesso) deste
		# "erro específico" — um oráculo de existência de e-mail. Fechar essa
		# distinção por completo exigiria SEMPRE "ter sucesso" aqui (ex.:
		# criar a conta com um login sintético amarrado só ao celular,
		# ignorando o e-mail que colidiu), mas isso pioraria o caminho
		# honesto mais comum deste ramo: a pessoa digitou um e-mail que É
		# dela mesma, de uma conta já existente criada por outro canal — hoje
		# ela recebe a dica explícita "tente verificar por e-mail" e recupera
		# a própria conta; com o login sintético ela perderia essa dica e
		# ficaria com uma conta-fantasma extra, sem entender por quê. Fica
		# como está — decisão consciente, não descuido — e a mitigação real
		# é econômica: cada tentativa aqui exige resolver um código OTP novo
		# por WhatsApp, e ambos os endpoints (solicitar_codigo e este) já são
		# limitados por IP via ``rate_limit`` (Task 4/5), o que encarece a
		# enumeração em massa sem bloquear o cliente honesto.
		frappe.throw(
			_(
				"Não foi possível concluir seu cadastro com estes dados. "
				"Tente verificar por e-mail."
			),
			title=_("Verificação indisponível"),
		)

	_criar_website_user(email, dados, mobile_no=celular)
	frappe.db.commit()  # nosemgrep
	_logar(email)
	return email, True


def _garantir_usuario(dados: dict) -> tuple[str, bool]:
	"""Cria (ou reaproveita) o Website User e o deixa logado. Devolve
	``(usuario, criado)``.

	A ÂNCORA da conta é sempre o CONTATO VERIFICADO — ``canal_verificado`` +
	``destino_verificado``, gravados por ``solicitar_codigo`` em cima do que
	``_resolver_envio`` decidiu — NUNCA um campo apenas digitado no
	formulário. ``login_as``/``frappe.set_user`` não provam posse de nada
	sozinhos: quem prova é o código de verificação, e só do canal que
	efetivamente o entregou. Usar ``dados.get("email")`` (digitado, não
	verificado) para decidir em qual conta logar permitiria a quem prova
	controlar o próprio WhatsApp digitar o e-mail de OUTRA pessoa e sair
	logado na conta dela — inclusive num System User interno (fix da
	revisão 2026-09-01, Task 5 fix round 1).
	"""
	canal = dados.get("canal_verificado")
	destino = dados.get("destino_verificado")

	if canal == "whatsapp":
		return _garantir_usuario_por_celular(destino, dados)
	if canal == "email":
		return _garantir_usuario_por_email(destino, dados)

	# Sem canal_verificado (código emitido fora de solicitar_codigo — não
	# deveria acontecer no fluxo real): recusa em vez de cair para o e-mail
	# digitado, que é exatamente o furo que esta correção fecha.
	frappe.throw(_("Não foi possível confirmar seu contato. Peça um novo código."))


@frappe.whitelist(allow_guest=True, methods=["POST"])
@rate_limit(limit=10, seconds=600)
def confirmar_codigo_e_agendar(
	codigo: str,
	appointment_date: str,
	appointment_time: str,
	verificacao_id: str | None = None,
	item_code: str | None = None,
	appointment_type: str | None = None,
	practitioner: str | None = None,
	modalidade: str | None = None,
	session_id: str | None = None,
) -> dict:
	from imunocare_ecommerce.agendamento.booking import criar_agendamento
	from imunocare_ecommerce.conta.codigo import conferir

	verificacao_id = _validar_verificacao_id(verificacao_id)
	dados = conferir(verificacao_id, codigo)
	_exigir_adulto(dados)

	para_outro = bool(dados.get("para_outra_pessoa"))
	cpf = _so_digitos(dados.get("paciente_cpf") if para_outro else dados.get("cpf"))
	paciente = frappe.db.get_value("Patient", {"cpf": cpf}, "name")

	# CRÍTICO 1 da revisão 2026-09-02 (takeover de prontuário): um Patient
	# PRÉ-EXISTENTE encontrado por ``paciente_cpf`` (para_outra_pessoa=1)
	# nunca é vinculado à conta de quem está se verificando — mesmo que
	# esteja órfão (``user_id`` vazio). CPF não é segredo, e quem digita o
	# CPF de outra pessoa como "paciente" não passou por NENHUMA prova de
	# posse do contato daquele registro (a prova de posse aqui é só do
	# ADULTO que está se verificando — dados["cpf"], nunca paciente_cpf).
	# Decisão (b) do relatório da revisão: recusa e orienta a procurar a
	# clínica, em vez de (a) estender a verificação de posse a paciente_cpf
	# — mais simples, e "para outra pessoa" É justamente o caso em que o
	# adulto normalmente NÃO consegue provar posse do contato do paciente
	# (uma criança não tem contato próprio). Checagem ANTES de
	# ``_garantir_usuario`` de propósito: nenhuma conta/registro chega a ser
	# criado quando a reserva vai ser recusada de qualquer jeito (mesmo
	# padrão "não cria nada" dos outros throws deste endpoint).
	#
	# Risco residual ACEITO (documentado no relatório ao CTO): quem já
	# completa a verificação do PRÓPRIO contato (dados["cpf"]/canal
	# verificado) ainda consegue, por tentativa e erro, inferir se um dado
	# paciente_cpf já é de um Patient cadastrado (sucesso cria vs. este
	# throw). É um oráculo mais lento que o do item 4 (exige resolver um
	# código OTP de verdade a cada tentativa, já limitado por IP via
	# rate_limit) — fechar por completo exigiria a opção (a), descartada
	# acima por complexidade desproporcional ao ganho.
	if paciente and para_outro:
		frappe.throw(
			_(
				"Não foi possível concluir o cadastro dessa pessoa por aqui. "
				"Procure a clínica para agendar."
			),
			title=_("Cadastro não permitido"),
		)

	usuario, conta_criada = _garantir_usuario(dados)

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
	resultado["conta_criada"] = conta_criada
	# Item 1 da revisão 2026-09-01: o cliente lê frappe.session.user no
	# carregamento da página — nunca fica sabendo, sozinho, que o backend
	# logou outro usuário no meio desta chamada. Devolve explicitamente QUEM
	# ficou logado para o JS atualizar o próprio estado (e o cabeçalho do
	# site) em vez de adivinhar.
	resultado["usuario"] = usuario
	return resultado
