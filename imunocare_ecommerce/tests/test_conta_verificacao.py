import random
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from imunocare_ecommerce.conta import codigo as mod_codigo
from imunocare_ecommerce.conta import verificacao

_DADOS = {
	"nome": "Ana Souza",
	"email": "ana.nova@exemplo.com",
	"celular": "51999881234",
	"cpf": "39053344705",  # CPF válido de teste
	"dob": "1990-05-10",
	"sexo": "Female",
}

_IP_TESTE = "203.0.113.9"


def _limpar_rate_limit_solicitar_codigo():
	# Mesmo IP em vários testes deste módulo somaria no MESMO balde do
	# rate_limit (janela de 600s) e estouraria RateLimitExceededError sem
	# relação nenhuma com o que o teste quer provar — mesmo padrão de reset
	# de test_rate_limit.py.
	chave = frappe.cache.make_key(
		f"imun_rl:imunocare_ecommerce.conta.verificacao.solicitar_codigo:{_IP_TESTE}"
	)
	frappe.cache.delete(chave)


def _limpar_rate_limit_confirmar_codigo():
	chave = frappe.cache.make_key(
		f"imun_rl:imunocare_ecommerce.conta.verificacao.confirmar_codigo_e_agendar:{_IP_TESTE}"
	)
	frappe.cache.delete(chave)


def _identidade_unica(prefixo: str) -> tuple[str, str]:
	"""(email, celular) nunca usados antes nesta rodada — evita colidir com
	resíduo de execuções anteriores do próprio teste (``User.mobile_no`` é
	único; e o Frappe compartilha UM Contact entre Patient/Customer/User que
	têm a mesma ``email_id`` — um Patient apagado deixa link morto nesse
	Contact, e reusar o e-mail depois esbarra nele ao salvar)."""
	sufixo = frappe.generate_hash(length=6)
	email = f"{prefixo}.{sufixo}@exemplo.com"
	celular = "519" + str(random.randint(10**7, 10**8 - 1))
	return email, celular


def _limpar_contatos_vinculados(link_doctype: str, link_name: str) -> None:
	"""Remove os Contacts vinculados a ``link_name``.

	O Frappe compartilha UM Contact entre Patient/Customer/User que têm a
	MESMA ``email_id`` (``update_contact``/sync nativo). Deixar esse Contact
	órfão (sem apagar) faz o PRÓXIMO teste que reusar o mesmo nome de
	Patient esbarrar num link morto ao salvar (achado real desta revisão:
	``LinkValidationError: Could not find Row #1: Link Name: Joaquim
	Souza``, com o Patient já apagado mas o Contact ainda apontando pra
	ele)."""
	nomes = frappe.get_all(
		"Dynamic Link",
		filters={"link_doctype": link_doctype, "link_name": link_name, "parenttype": "Contact"},
		pluck="parent",
	)
	for nome in nomes:
		_apagar_definitivamente("Contact", nome)


def _apagar_definitivamente(doctype: str, name: str) -> None:
	"""Apaga e COMMITA.

	``FrappeTestCase`` só desfaz mudanças de um teste no rollback de FIM DE
	CLASSE (``addClassCleanup(_rollback_db)`` — não é por teste). Isso é
	inofensivo até alguém chamar ``frappe.db.commit()`` no meio do caminho
	— e o fluxo completo de ``confirmar_codigo_e_agendar``/
	``_garantir_usuario`` faz exatamente isso (precisa: sessão gravada antes
	de ``login_as``; a cadeia Patient→Appointment→Customer do Healthcare
	também comita em algum ponto do próprio ``criar_agendamento``,
	empiricamente observado). Sem commitar TAMBÉM o delete, o rollback de
	fim-de-classe desfaz só a LIMPEZA (nunca commitada) e ressuscita a linha
	que já tinha virado permanente — visto na prática nesta revisão."""
	if frappe.db.exists(doctype, name):
		frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
	frappe.db.commit()  # nosemgrep


class TestSolicitarCodigo(FrappeTestCase):
	def setUp(self):
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = _IP_TESTE
		_limpar_rate_limit_solicitar_codigo()

		# Precondição: canal e-mail disponível, sem depender do estado
		# ambiental do bench (mesmo padrão de test_conta_canais.py).
		conta = frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_id": "verificacao-teste@exemplo.com",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"smtp_server": "127.0.0.1",
				"awaiting_password": 1,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc,
			"Email Account",
			conta.name,
			force=True,
			ignore_permissions=True,
		)

		# Nenhum teste pode tocar a rede: mocka o envio de verdade.
		patcher = patch("imunocare_ecommerce.conta.canais.enviar")
		self.addCleanup(patcher.stop)
		patcher.start()

	def test_resposta_nao_contem_o_codigo(self):
		r = verificacao.solicitar_codigo("email", dict(_DADOS))
		self.assertNotIn("codigo", r)
		for valor in r.values():
			self.assertNotRegex(str(valor), r"^\d{6}$")

	def test_devolve_destino_mascarado_e_validade(self):
		r = verificacao.solicitar_codigo("email", dict(_DADOS))
		self.assertEqual(r["destino_mascarado"], "a***@exemplo.com")
		self.assertEqual(r["expira_em"], 600)

	def test_cpf_novo_usa_o_contato_digitado(self):
		self.assertEqual(_DADOS["email"], verificacao._destino_de_envio("email", dict(_DADOS)))

	def test_cpf_ja_cadastrado_usa_o_contato_do_cadastro(self):
		"""Quem digita CPF alheio não recebe nada — o código vai para o dono."""
		paciente = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Bruno",
				# ``middle_name`` explícito: o Property Setter que o torna
				# obrigatório (imunocare_clinic_ext/install.py
				# NATIVE_PROPERTY_SETTERS) sobrevive ao after_migrate mesmo
				# depois do patch desta feature — defeito de outro app, fora
				# do escopo desta task (ver riscos no relatório da Task 4).
				"middle_name": "de",
				"last_name": "Lima",
				"sex": "Male",
				"dob": "1985-02-02",
				"cpf": "52998224725",
				"mobile": "51988776655",
				"email": "bruno.dono@exemplo.com",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Patient", paciente.name, force=True)

		dados = dict(_DADOS, cpf="52998224725", email="invasor@exemplo.com")
		self.assertEqual(
			verificacao._destino_de_envio("email", dados), "bruno.dono@exemplo.com"
		)

	def test_canal_indisponivel_e_recusado(self):
		# Precondição montada no teste (não depende do ambiente ter ou não
		# WhatsApp configurado) — mesmo padrão de test_conta_canais.py: afirma
		# sempre, nunca passa por vacuidade.
		with patch.object(
			verificacao.canais, "disponiveis", return_value={"email": True, "whatsapp": False}
		):
			with self.assertRaises(frappe.ValidationError):
				verificacao.solicitar_codigo("whatsapp", dict(_DADOS))


class TestResolverEnvio(FrappeTestCase):
	"""Fix crítico da revisão da Task 4: quando o CPF já é de um Patient, o
	contato SEMPRE vem do cadastro — nunca do que foi digitado, mesmo que o
	canal pedido esteja vazio no cadastro. Testa ``_resolver_envio``/
	``_destino_de_envio`` diretamente, sem depender de canal disponível
	(essas funções não checam disponibilidade — quem chama, checa)."""

	def test_canal_pedido_vazio_mas_outro_do_cadastro_preenchido_usa_o_outro(self):
		# email vazio simula o cadastro latente que a revisão apontou (hoje
		# email/mobile são reqd em produção — 12/12 pacientes preenchidos —
		# mas nada no código garante isso para sempre). ignore_mandatory
		# reproduz esse estado sem depender do bench.
		paciente = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Carla",
				"middle_name": "de",
				"last_name": "Nunes",
				"sex": "Female",
				"dob": "1992-04-09",
				"cpf": "16899535009",
				"mobile": "51977778888",
				"email": "",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		self.addCleanup(frappe.delete_doc, "Patient", paciente.name, force=True)

		# Pede email (vazio no cadastro); nunca pode usar o que foi digitado.
		dados = dict(_DADOS, cpf="16899535009", email="invasor@exemplo.com")
		canal_efetivo, destino = verificacao._resolver_envio("email", dados)
		self.assertEqual(canal_efetivo, "whatsapp")
		self.assertEqual(destino, "51977778888")
		# _destino_de_envio (compat) devolve só o destino do canal efetivo.
		self.assertEqual(verificacao._destino_de_envio("email", dados), "51977778888")

	def test_nenhum_contato_preenchido_no_cadastro_e_recusado(self):
		paciente = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Diego",
				"middle_name": "de",
				"last_name": "Alves",
				"sex": "Male",
				"dob": "1988-11-20",
				"cpf": "52998224725",
				"mobile": "",
				"email": "",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)
		self.addCleanup(frappe.delete_doc, "Patient", paciente.name, force=True)

		dados = dict(_DADOS, cpf="52998224725", email="invasor@exemplo.com")
		with self.assertRaises(frappe.ValidationError):
			verificacao._destino_de_envio("email", dados)


class TestEntradaInvalida(FrappeTestCase):
	"""Fix importante da revisão da Task 4: endpoint allow_guest não pode
	confiar no formato do payload — cada caminho abaixo estourava exceção não
	tratada (500) antes do fix."""

	def setUp(self):
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = _IP_TESTE
		_limpar_rate_limit_solicitar_codigo()

	def test_dados_json_malformado_e_recusado(self):
		with self.assertRaises(frappe.ValidationError):
			verificacao.solicitar_codigo("email", "{isto nao e json")

	def test_dados_json_valido_mas_nao_e_objeto_e_recusado(self):
		with self.assertRaises(frappe.ValidationError):
			verificacao.solicitar_codigo("email", "[1, 2, 3]")

	def test_campo_de_dados_com_tipo_inesperado_e_recusado(self):
		with self.assertRaises(frappe.ValidationError):
			verificacao.solicitar_codigo("email", dict(_DADOS, cpf=39053344705))

	def test_canal_com_tipo_inesperado_e_recusado(self):
		with self.assertRaises(frappe.ValidationError):
			verificacao.solicitar_codigo(["email"], dict(_DADOS))


class TestConfirmarCodigo(FrappeTestCase):
	def setUp(self):
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = _IP_TESTE
		_limpar_rate_limit_confirmar_codigo()
		# frappe.session.sid vale 'Administrator' fora de um request de
		# verdade — todos os testes deste módulo compartilham o MESMO balde
		# no Redis do código de verificação; sem isso um teste contamina o
		# outro (código de sobra de um teste anterior, tentativas já gastas).
		mod_codigo.descartar(frappe.session.sid)

	def tearDown(self):
		mod_codigo.descartar(frappe.session.sid)

	def test_codigo_errado_nao_cria_nada(self):
		antes_user = frappe.db.count("User")
		antes_pac = frappe.db.count("Patient")
		mod_codigo.emitir(frappe.session.sid, dict(_DADOS))
		with self.assertRaises(mod_codigo.CodigoInvalido):
			verificacao.confirmar_codigo_e_agendar(
				codigo="000000", appointment_date="2030-01-10", appointment_time="09:00:00"
			)
		self.assertEqual(frappe.db.count("User"), antes_user)
		self.assertEqual(frappe.db.count("Patient"), antes_pac)

	def test_menor_de_idade_recebe_responsavel_do_adulto(self):
		"""patient_hooks._validate_guardian exige nome+CPF do responsável."""
		dados = dict(
			_DADOS,
			para_outra_pessoa=True,
			paciente_nome="Joaquim Souza",
			paciente_cpf="52998224725",
			paciente_dob="2020-03-01",
			paciente_sexo="Male",
		)
		p = verificacao._montar_paciente(dados, adulto_user="ana.nova@exemplo.com")
		self.assertEqual(p.nome_responsavel, "Ana Souza")
		self.assertEqual(p.cpf_responsavel, "39053344705")

	def test_adulto_para_si_mesmo_nao_ganha_responsavel(self):
		p = verificacao._montar_paciente(dict(_DADOS), adulto_user="ana.nova@exemplo.com")
		self.assertFalse(p.get("nome_responsavel"))

	def test_dois_filhos_geram_dois_pacientes(self):
		"""Critério de aceite 4: o segundo filho não pode reusar o Patient do
		primeiro. A busca por {"user_id": user} devolveria um deles ao acaso."""
		adulto = "ana.nova@exemplo.com"
		base = dict(
			_DADOS, para_outra_pessoa=True, paciente_dob="2019-01-01", paciente_sexo="Female"
		)

		p1 = verificacao._montar_paciente(
			dict(base, paciente_nome="Joaquim Souza", paciente_cpf="52998224725"),
			adulto_user=adulto,
		)
		p1.insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Patient", p1.name, force=True)

		p2 = verificacao._montar_paciente(
			dict(base, paciente_nome="Marina Souza", paciente_cpf="16899535009"),
			adulto_user=adulto,
		)
		p2.insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Patient", p2.name, force=True)

		self.assertNotEqual(p1.name, p2.name)
		self.assertEqual(p1.user_id, p2.user_id, "os dois pendurados no mesmo adulto")

	def test_nome_de_duas_palavras_nao_quebra(self):
		"""'Ana Souza' -> first/last preenchidos, middle vazio. Task 1 liberou."""
		p = verificacao._montar_paciente(dict(_DADOS), adulto_user="ana.nova@exemplo.com")
		self.assertEqual(p.first_name, "Ana")
		self.assertEqual(p.last_name, "Souza")
		p.insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Patient", p.name, force=True)

	def test_menor_para_si_mesmo_e_recusado_e_nao_cria_nada(self):
		"""Fix IMPORTANTE da revisão: sem para_outra_pessoa, quem se verifica
		precisa ser maior de 18 — senão viraria responsável de si mesmo."""
		antes_user = frappe.db.count("User")
		antes_pac = frappe.db.count("Patient")
		dados = dict(
			_DADOS,
			email="crianca.sozinha@exemplo.com",
			dob="2015-06-01",
			canal_verificado="email",
			destino_verificado="crianca.sozinha@exemplo.com",
		)
		c = mod_codigo.emitir(frappe.session.sid, dados)
		with self.assertRaises(frappe.ValidationError):
			verificacao.confirmar_codigo_e_agendar(
				codigo=c, appointment_date="2030-01-10", appointment_time="09:00:00"
			)
		self.assertEqual(frappe.db.count("User"), antes_user)
		self.assertEqual(frappe.db.count("Patient"), antes_pac)


class TestExigirAdultoParaSiMesmo(FrappeTestCase):
	"""Fix IMPORTANTE da revisão (verificacao.py, adulto menor virava
	responsável de si mesmo): sem para_outra_pessoa, a idade computada é a
	da PRÓPRIA pessoa que está se verificando — precisa ser maior de 18."""

	def test_menor_de_idade_para_si_mesmo_e_recusado(self):
		dados = dict(_DADOS, dob="2015-01-01")
		with self.assertRaises(frappe.ValidationError):
			verificacao._exigir_adulto_para_si_mesmo(dados)

	def test_adulto_para_si_mesmo_passa(self):
		verificacao._exigir_adulto_para_si_mesmo(dict(_DADOS))  # não lança

	def test_para_outra_pessoa_ignora_a_idade_de_quem_verifica(self):
		"""A idade que importa aqui é a do ADULTO (dob), não a do paciente
		(paciente_dob) — quando para_outra_pessoa=True a função sai cedo."""
		dados = dict(_DADOS, para_outra_pessoa=True, paciente_dob="2020-01-01")
		verificacao._exigir_adulto_para_si_mesmo(dados)  # não lança


class TestGarantirUsuarioAncoraContatoVerificado(FrappeTestCase):
	"""Fix CRÍTICO da revisão: a âncora da conta é o CONTATO VERIFICADO
	(canal_verificado/destino_verificado, gravados por solicitar_codigo em
	cima do que _resolver_envio decidiu) — nunca um campo digitado no
	formulário que ninguém provou. Antes do fix, canal="whatsapp" provava só
	o celular mas o login usava dados["email"] (não verificado), permitindo
	logar como QUALQUER conta cujo e-mail fosse digitado."""

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_canal_email_cria_e_loga_pelo_destino_verificado(self):
		email, celular = _identidade_unica("nova.conta.task5")
		dados = dict(
			_DADOS,
			celular=celular,
			canal_verificado="email",
			destino_verificado=email,
		)
		usuario, criado = verificacao._garantir_usuario(dados)
		self.addCleanup(_apagar_definitivamente, "User", usuario)

		self.assertEqual(usuario, email)
		self.assertTrue(criado)
		self.assertEqual(frappe.session.user, email)

	def test_canal_whatsapp_com_celular_de_usuario_existente_loga_na_conta_certa(self):
		email_dono, celular_dono = _identidade_unica("dono.celular.task5")
		dono = frappe.get_doc(
			{
				"doctype": "User",
				"email": email_dono,
				"first_name": "Dono",
				"last_name": "Celular",
				"mobile_no": celular_dono,
				"send_welcome_email": 0,
				"user_type": "Website User",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_apagar_definitivamente, "User", dono.name)

		email_digitado, _celular_nao_usado = _identidade_unica("nao.deveria.importar")
		dados = dict(
			_DADOS,
			canal_verificado="whatsapp",
			destino_verificado=celular_dono,
			# o e-mail digitado é de outra pessoa/inexistente — não pode importar
			email=email_digitado,
		)
		usuario, criado = verificacao._garantir_usuario(dados)

		self.assertEqual(usuario, dono.name)
		self.assertFalse(criado)
		self.assertEqual(frappe.session.user, dono.name)
		self.assertFalse(frappe.db.exists("User", email_digitado))

	def test_canal_whatsapp_com_email_digitado_de_terceiro_nao_loga_na_conta_dele(self):
		"""O achado CRÍTICO: sem esta trava, quem prova controlar o próprio
		WhatsApp digitava o e-mail de QUALQUER outra pessoa — inclusive um
		System User interno (user_type default) — e saía logado na conta
		dela, porque login_as não checa posse de nada."""
		email_terceiro, _celular_terceiro = _identidade_unica("vitima.interna.task5")
		terceiro = frappe.get_doc(
			{
				"doctype": "User",
				"email": email_terceiro,
				"first_name": "Vítima",
				"last_name": "Interna",
				"send_welcome_email": 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_apagar_definitivamente, "User", terceiro.name)

		_email_nao_usado, celular_novo = _identidade_unica("nao.usado")
		dados = dict(
			_DADOS,
			canal_verificado="whatsapp",
			destino_verificado=celular_novo,  # celular novo: não bate com o terceiro
			email=email_terceiro,  # digitado, NUNCA verificado
		)
		usuario_antes = frappe.session.user
		with self.assertRaises(frappe.ValidationError):
			verificacao._garantir_usuario(dados)

		self.assertEqual(frappe.session.user, usuario_antes, "não pode logar em conta alheia")
		# a "vítima" não ganhou celular nenhum — nada nela foi tocado
		self.assertFalse(frappe.db.get_value("User", terceiro.name, "mobile_no"))


class TestConfirmarCodigoEAgendarFimAFim(FrappeTestCase):
	"""Fecha a lacuna de spec da revisão: prova o critério de aceite 4 pelo
	ENDPOINT inteiro (não só por _montar_paciente isolada). Dois filhos do
	mesmo adulto, cada um confirmado com seu próprio código, geram dois
	Patient distintos — e cada Patient Appointment aponta para o filho
	certo, nunca para o que _resolver_paciente escolheria ao acaso."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Os Appointment Type já cadastrados no bench são allow_booking_for
		# "Department" (curadoria pendente, fora do escopo desta task) — o
		# fluxo da loja exige "Practitioner". Fixture próprio para não
		# depender de dado de ambiente.
		cls._appointment_type = frappe.get_doc(
			{
				"doctype": "Appointment Type",
				"appointment_type": "E2E Teste Task5 Reserva Visitante",
				"allow_booking_for": "Practitioner",
				"default_duration": 30,
			}
		).insert(ignore_permissions=True)
		# ``employee`` é reqd por Property Setter do imunocare_clinic_ext,
		# mas há Practitioner ativo em produção sem employee vinculado —
		# ignore_mandatory reproduz esse estado real sem depender de
		# Employee/Company de teste.
		cls._practitioner = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "Praticante Teste E2E Task5",
				"status": "Active",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

	@classmethod
	def tearDownClass(cls):
		# Delete + commit: uma reserva bem-sucedida no meio da classe pode ter
		# comitado a transação (ver ``_apagar_definitivamente``) — sem commitar
		# aqui também, o rollback de fim-de-classe desfaz só ESTA limpeza e
		# ressuscita os fixtures.
		_apagar_definitivamente("Appointment Type", cls._appointment_type.name)
		_apagar_definitivamente("Healthcare Practitioner", cls._practitioner.name)
		super().tearDownClass()

	def setUp(self):
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = _IP_TESTE
		_limpar_rate_limit_confirmar_codigo()
		mod_codigo.descartar(frappe.session.sid)

	def tearDown(self):
		mod_codigo.descartar(frappe.session.sid)
		frappe.set_user("Administrator")

	def _confirmar(self, dados, appointment_time):
		c = mod_codigo.emitir(frappe.session.sid, dados)
		return verificacao.confirmar_codigo_e_agendar(
			codigo=c,
			appointment_date="2030-02-01",
			appointment_time=appointment_time,
			appointment_type=self._appointment_type.name,
			practitioner=self._practitioner.name,
		)

	def test_dois_filhos_geram_dois_agendamentos_no_paciente_certo(self):
		# E-mail/celular únicos por execução: o Frappe compartilha um Contact
		# entre Patient/Customer/User pela mesma email_id (ver
		# _identidade_unica) — reusar um valor fixo entre execuções do
		# módulo esbarraria num Contact órfão de uma rodada anterior.
		adulto_email, adulto_celular = _identidade_unica("ana.e2e.task5")
		base = dict(
			_DADOS,
			email=adulto_email,
			celular=adulto_celular,
			canal_verificado="email",
			destino_verificado=adulto_email,
			para_outra_pessoa=True,
			paciente_dob="2019-01-01",
			paciente_sexo="Female",
		)

		r1 = self._confirmar(
			dict(base, paciente_nome="Joaquim Souza", paciente_cpf="52998224725"),
			"09:00:00",
		)
		# Delete + commit (ver _apagar_definitivamente): confirmar_codigo_e_agendar
		# comita ao garantir o usuário (login_as precisa da sessão gravada) — o
		# rollback de fim-de-classe sozinho ressuscitaria o que só a limpeza
		# desfez, nunca o que já virou permanente.
		self.addCleanup(_apagar_definitivamente, "User", adulto_email)
		self.assertTrue(r1["conta_criada"], "primeira reserva cria a conta do adulto")

		r2 = self._confirmar(
			dict(base, paciente_nome="Marina Souza", paciente_cpf="16899535009"),
			"10:00:00",
		)
		self.assertFalse(r2["conta_criada"], "segunda reserva reaproveita a conta já criada")

		self.addCleanup(_apagar_definitivamente, "Patient Appointment", r1["appointment"])
		self.addCleanup(_apagar_definitivamente, "Patient Appointment", r2["appointment"])

		pac1 = frappe.db.get_value("Patient Appointment", r1["appointment"], "patient")
		pac2 = frappe.db.get_value("Patient Appointment", r2["appointment"], "patient")
		self.addCleanup(_limpar_contatos_vinculados, "Patient", pac1)
		self.addCleanup(_limpar_contatos_vinculados, "Patient", pac2)
		self.addCleanup(_apagar_definitivamente, "Patient", pac1)
		self.addCleanup(_apagar_definitivamente, "Patient", pac2)
		# create_customer (hook nativo do Healthcare, Patient.on_update) cria
		# um Customer de mesmo nome — órfão se não limpar (Patient.name aqui
		# é sempre "<primeiro> <último>", mesmo valor do Customer).
		self.addCleanup(_apagar_definitivamente, "Customer", "Joaquim Souza")
		self.addCleanup(_apagar_definitivamente, "Customer", "Marina Souza")

		self.assertNotEqual(pac1, pac2, "o segundo filho não pode reusar o Patient do primeiro")
		self.assertEqual(frappe.db.get_value("Patient", pac1, "first_name"), "Joaquim")
		self.assertEqual(frappe.db.get_value("Patient", pac2, "first_name"), "Marina")
		self.assertEqual(
			frappe.db.get_value("Patient", pac1, "user_id"),
			frappe.db.get_value("Patient", pac2, "user_id"),
			"os dois pendurados na mesma conta do adulto",
		)


class TestRegressaoCriarAgendamento(FrappeTestCase):
	def test_criar_agendamento_continua_recusando_guest(self):
		"""A porta de entrada do visitante é a função nova, não esta."""
		from imunocare_ecommerce.agendamento.booking import criar_agendamento

		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		with self.assertRaises(frappe.PermissionError):
			criar_agendamento(appointment_date="2030-01-10", appointment_time="09:00:00")
