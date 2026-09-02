import random
import secrets
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


def _token() -> str:
	"""Token opaco por verificação — o mesmo formato que ``solicitar_codigo``
	gera em produção (``secrets.token_urlsafe``). NUNCA ``frappe.session.sid``:
	fora de um request de verdade ele vale sempre 'Administrator', e mesmo
	num request real todo visitante anônimo compartilha o MESMO sid literal
	('Guest') — foi exatamente esse compartilhamento que causou o bug que
	``TestConcorrenciaEntreVisitantesAnonimos`` reproduz abaixo."""
	return secrets.token_urlsafe(32)


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

	def test_reenviar_codigo_descarta_a_verificacao_anterior(self):
		"""Fix round 1: cada emissão vira uma chave PRÓPRIA no Redis — sem
		descartar a anterior explicitamente, ela só morreria pelo TTL (até
		10 min), deixando o código da PRIMEIRA emissão confirmável em
		paralelo com o da segunda. "Reenviar código" manda
		``verificacao_id_anterior`` de volta e o servidor tem que apagá-la
		antes de emitir a nova."""
		codigos = []
		with patch(
			"imunocare_ecommerce.conta.canais.enviar",
			side_effect=lambda canal, destino, codigo, nome: codigos.append(codigo),
		):
			r1 = verificacao.solicitar_codigo("email", dict(_DADOS))
			r2 = verificacao.solicitar_codigo(
				"email", dict(_DADOS), verificacao_id_anterior=r1["verificacao_id"]
			)

		self.assertNotEqual(r1["verificacao_id"], r2["verificacao_id"])
		self.assertEqual(len(codigos), 2)
		codigo_da_primeira, codigo_da_segunda = codigos

		# O código da PRIMEIRA emissão deixa de ser aceito — a chave foi
		# descartada pelo reenvio, não só sobrescrita.
		with self.assertRaises(mod_codigo.CodigoInvalido):
			mod_codigo.conferir(r1["verificacao_id"], codigo_da_primeira)

		# O da SEGUNDA (a que o cliente realmente tem na tela) funciona.
		dados = mod_codigo.conferir(r2["verificacao_id"], codigo_da_segunda)
		self.assertEqual(dados["email"], _DADOS["email"])

	def test_reenviar_codigo_sem_verificacao_id_anterior_nao_estoura(self):
		"""verificacao_id_anterior é opcional — omitido, vazio ou de tipo
		estranho (dado vindo do cliente) nunca pode virar 500; descartar um
		token que não existe é no-op silencioso."""
		for valor in (None, "", "token-que-nunca-existiu", 123, ["a"]):
			with self.subTest(valor=valor):
				r = verificacao.solicitar_codigo(
					"email", dict(_DADOS), verificacao_id_anterior=valor
				)
				self.assertIn("verificacao_id", r)


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

	def test_codigo_errado_nao_cria_nada(self):
		antes_user = frappe.db.count("User")
		antes_pac = frappe.db.count("Patient")
		token = _token()
		mod_codigo.emitir(token, dict(_DADOS))
		with self.assertRaises(mod_codigo.CodigoInvalido):
			verificacao.confirmar_codigo_e_agendar(
				codigo="000000",
				verificacao_id=token,
				appointment_date="2030-01-10",
				appointment_time="09:00:00",
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
		token = _token()
		c = mod_codigo.emitir(token, dados)
		with self.assertRaises(frappe.ValidationError):
			verificacao.confirmar_codigo_e_agendar(
				codigo=c,
				verificacao_id=token,
				appointment_date="2030-01-10",
				appointment_time="09:00:00",
			)
		self.assertEqual(frappe.db.count("User"), antes_user)
		self.assertEqual(frappe.db.count("Patient"), antes_pac)

	def test_menor_para_outra_pessoa_e_recusado_e_nao_cria_nada(self):
		"""Item 2 da revisão 2026-09-01, mesmo teste acima mas pelo caminho
		"para outra pessoa": um menor não pode criar conta nem figurar como
		responsável de outro paciente, mesmo que o paciente informado
		(paciente_dob) seja adulto — a idade que bloqueia é a de quem está
		se cadastrando (dob), sempre."""
		antes_user = frappe.db.count("User")
		antes_pac = frappe.db.count("Patient")
		dados = dict(
			_DADOS,
			email="crianca.responsavel@exemplo.com",
			dob="2015-06-01",
			canal_verificado="email",
			destino_verificado="crianca.responsavel@exemplo.com",
			para_outra_pessoa=True,
			paciente_nome="Avó Souza",
			paciente_cpf="52998224725",
			paciente_dob="1950-01-01",
			paciente_sexo="Female",
		)
		token = _token()
		c = mod_codigo.emitir(token, dados)
		with self.assertRaises(frappe.ValidationError):
			verificacao.confirmar_codigo_e_agendar(
				codigo=c,
				verificacao_id=token,
				appointment_date="2030-01-10",
				appointment_time="09:00:00",
			)
		self.assertEqual(frappe.db.count("User"), antes_user)
		self.assertEqual(frappe.db.count("Patient"), antes_pac)


class TestParaOutraPessoaNaoAdotaPatientExistente(FrappeTestCase):
	"""CRÍTICO 1 da revisão 2026-09-02 — takeover de prontuário.

	Cadeia de ataque fechada aqui: um atacante pede o código com o PRÓPRIO
	CPF/contato (prova posse de si mesmo, recebe e confirma o código
	normalmente) mas com ``para_outra_pessoa=1`` e ``paciente_cpf`` = CPF de
	OUTRA pessoa (adivinhável — CPF não é segredo). Antes do fix,
	``confirmar_codigo_e_agendar`` resolvia o paciente por ``paciente_cpf``
	e adotava qualquer Patient encontrado sem ``user_id`` (todos os 12
	Patients de produção estavam nesse estado) — vinculando o prontuário da
	vítima à conta do atacante. Decisão (b) do relatório da revisão: recusa
	SEMPRE que ``paciente_cpf`` (não ``cpf``) encontra um Patient
	pré-existente, mesmo órfão — nunca adota."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._appointment_type = frappe.get_doc(
			{
				"doctype": "Appointment Type",
				"appointment_type": "Teste Takeover CPF Paciente",
				"allow_booking_for": "Practitioner",
				"default_duration": 30,
			}
		).insert(ignore_permissions=True)
		cls._practitioner = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "Praticante Teste Takeover",
				"status": "Active",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

	@classmethod
	def tearDownClass(cls):
		_apagar_definitivamente("Appointment Type", cls._appointment_type.name)
		_apagar_definitivamente("Healthcare Practitioner", cls._practitioner.name)
		super().tearDownClass()

	def setUp(self):
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = _IP_TESTE
		_limpar_rate_limit_confirmar_codigo()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_paciente_cpf_de_patient_orfao_pre_existente_nao_e_adotado(self):
		vitima = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Vítima",
				"middle_name": "de",
				"last_name": "Alvo",
				"sex": "Female",
				"dob": "1980-01-01",
				"cpf": "52998224725",
				"mobile": "51999990000",
				"email": "vitima.alvo@exemplo.com",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(frappe.delete_doc, "Patient", vitima.name, force=True)
		self.assertFalse(vitima.user_id, "precondição: Patient órfão, igual aos 12 de produção")

		email_atacante, celular_atacante = _identidade_unica("atacante.takeover")
		dados = dict(
			_DADOS,
			email=email_atacante,
			celular=celular_atacante,
			cpf="39053344705",  # CPF do PRÓPRIO atacante — novo, provado por ele mesmo
			canal_verificado="email",
			destino_verificado=email_atacante,
			para_outra_pessoa=True,
			paciente_nome="Vítima Alvo",
			paciente_cpf="52998224725",  # CPF da vítima, adivinhado
			paciente_dob="1980-01-01",
			paciente_sexo="Female",
		)
		token = _token()
		c = mod_codigo.emitir(token, dados)
		with self.assertRaises(frappe.ValidationError):
			verificacao.confirmar_codigo_e_agendar(
				codigo=c,
				verificacao_id=token,
				appointment_date="2030-01-10",
				appointment_time="09:00:00",
			)

		# O prontuário da vítima NUNCA é vinculado à conta do atacante.
		self.assertFalse(frappe.db.get_value("Patient", vitima.name, "user_id"))
		# A checagem acontece ANTES de criar a conta do atacante — nenhum
		# rastro fica para trás de uma tentativa recusada.
		self.assertFalse(frappe.db.exists("User", email_atacante))

	def test_cpf_proprio_pre_existente_continua_sendo_adotado_normalmente(self):
		"""Regressão: a checagem nova é só para ``paciente_cpf``
		(``para_outra_pessoa``) — quem já tem um Patient órfão cadastrado com
		o PRÓPRIO CPF (dados["cpf"]) continua vinculando normalmente, porque
		a prova de posse aí é o próprio contato verificado (ver
		_resolver_envio)."""
		email, celular = _identidade_unica("dono.cpf.proprio")
		orfao = frappe.get_doc(
			{
				"doctype": "Patient",
				"first_name": "Gustavo",
				"middle_name": "de",
				"last_name": "Neto",
				"sex": "Male",
				"dob": "1990-05-10",
				"cpf": "39053344705",
				"mobile": celular,
				"email": email,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_limpar_contatos_vinculados, "Patient", orfao.name)
		self.addCleanup(_apagar_definitivamente, "Patient", orfao.name)
		self.addCleanup(_apagar_definitivamente, "Customer", "Gustavo Neto")

		dados = dict(
			_DADOS,
			email=email,
			celular=celular,
			canal_verificado="email",
			destino_verificado=email,
		)
		token = _token()
		c = mod_codigo.emitir(token, dados)
		resultado = verificacao.confirmar_codigo_e_agendar(
			codigo=c,
			verificacao_id=token,
			appointment_date="2030-01-10",
			appointment_time="09:00:00",
			appointment_type=self._appointment_type.name,
			practitioner=self._practitioner.name,
		)
		self.addCleanup(_apagar_definitivamente, "User", email)
		self.addCleanup(_apagar_definitivamente, "Patient Appointment", resultado["appointment"])

		self.assertEqual(
			frappe.db.get_value("Patient Appointment", resultado["appointment"], "patient"),
			orfao.name,
		)
		self.assertEqual(frappe.db.get_value("Patient", orfao.name, "user_id"), email)


class TestExigirAdulto(FrappeTestCase):
	"""Item 2 da revisão 2026-09-01 (fechando pela metade o fix anterior):
	quem CRIA A CONTA precisa ser maior de 18 SEMPRE — para si mesmo ou para
	outra pessoa. Antes, ``para_outra_pessoa=True`` pulava a checagem por
	completo, e um menor conseguia criar conta e figurar como responsável de
	um paciente. Regra única: a idade que importa é sempre a de ``dob``
	(quem está se verificando), nunca a de ``paciente_dob``."""

	def test_menor_de_idade_para_si_mesmo_e_recusado(self):
		dados = dict(_DADOS, dob="2015-01-01")
		with self.assertRaises(frappe.ValidationError):
			verificacao._exigir_adulto(dados)

	def test_adulto_para_si_mesmo_passa(self):
		verificacao._exigir_adulto(dict(_DADOS))  # não lança

	def test_menor_de_idade_para_outra_pessoa_tambem_e_recusado(self):
		"""O achado do item 2: sem para_outra_pessoa=True como escapatória,
		um menor não pode mais se cadastrar como responsável de ninguém —
		mesmo que o PACIENTE (paciente_dob) seja um bebê, sem relação com a
		idade de quem estaria criando a conta."""
		dados = dict(
			_DADOS,
			dob="2015-01-01",
			para_outra_pessoa=True,
			paciente_dob="2020-01-01",
		)
		with self.assertRaises(frappe.ValidationError):
			verificacao._exigir_adulto(dados)

	def test_adulto_para_outra_pessoa_passa(self):
		"""A idade que importa é a de quem verifica (dob), não a do paciente
		atendido (paciente_dob) — um bebê como paciente não bloqueia um
		adulto responsável por ele."""
		dados = dict(_DADOS, para_outra_pessoa=True, paciente_dob="2020-01-01")
		verificacao._exigir_adulto(dados)  # não lança


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

	def test_conta_criada_pela_loja_ganha_a_role_patient(self):
		"""M1 da revisão 2026-09-02: critério de aceite 3 exige a role nativa
		"Patient" — ``Portal Settings.default_role`` é config GERAL do site
		(qualquer Website User, não só quem se cadastra pela loja) e pode
		divergir sem relação nenhuma com este fluxo."""
		email, celular = _identidade_unica("role.patient.task5")
		dados = dict(
			_DADOS,
			celular=celular,
			canal_verificado="email",
			destino_verificado=email,
		)
		usuario, criado = verificacao._garantir_usuario(dados)
		self.addCleanup(_apagar_definitivamente, "User", usuario)

		self.assertTrue(criado)
		self.assertIn("Patient", frappe.get_roles(usuario))

	def test_canal_email_de_usuario_desabilitado_e_recusado(self):
		"""Item 3 da revisão 2026-09-02: ``LoginManager.post_login`` não
		valida ``enabled`` sozinho — um ex-funcionário desabilitado cujo
		e-mail bata com o contato verificado não pode ganhar sessão pela
		loja sem senha/2FA."""
		email_desabilitado, _c = _identidade_unica("desabilitado.email.task5")
		usuario_desabilitado = frappe.get_doc(
			{
				"doctype": "User",
				"email": email_desabilitado,
				"first_name": "Ex",
				"last_name": "Funcionario",
				"send_welcome_email": 0,
				"user_type": "Website User",
				"enabled": 0,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_apagar_definitivamente, "User", usuario_desabilitado.name)

		dados = dict(
			_DADOS,
			canal_verificado="email",
			destino_verificado=email_desabilitado,
		)
		usuario_antes = frappe.session.user
		with self.assertRaises(frappe.ValidationError):
			verificacao._garantir_usuario(dados)
		self.assertEqual(frappe.session.user, usuario_antes, "não pode logar em conta desabilitada")

	def test_canal_email_de_system_user_e_recusado(self):
		"""Mesmo achado, para um System User interno (existem contas de
		e-mail internas no próprio ERP) cujo e-mail bata com o contato
		verificado — nunca ganha sessão pela loja."""
		email_interno, _c = _identidade_unica("system.user.email.task5")
		interno = frappe.get_doc(
			{
				"doctype": "User",
				"email": email_interno,
				"first_name": "Interno",
				"last_name": "ERP",
				"send_welcome_email": 0,
				"enabled": 1,
				# user_type é CALCULADO por User.validate a partir de
				# has_desk_access() (ver frappe/core/doctype/user/user.py) —
				# sem role de acesso ao Desk, viraria "Website User" mesmo
				# sem passar nada explícito. Uma role real de acesso ao Desk
				# é o que efetivamente simula um System User interno.
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)
		self.assertEqual(interno.user_type, "System User", "precondição do teste")
		self.addCleanup(_apagar_definitivamente, "User", interno.name)

		dados = dict(
			_DADOS,
			canal_verificado="email",
			destino_verificado=email_interno,
		)
		usuario_antes = frappe.session.user
		with self.assertRaises(frappe.ValidationError):
			verificacao._garantir_usuario(dados)
		self.assertEqual(frappe.session.user, usuario_antes, "não pode logar num System User")

	def test_canal_whatsapp_com_celular_de_usuario_desabilitado_e_recusado(self):
		"""Mesmo achado do ramo por e-mail, pelo ramo por WhatsApp: um
		celular verificado que bate com um User desabilitado não ganha
		sessão."""
		email_dono, celular_dono = _identidade_unica("desabilitado.celular.task5")
		dono = frappe.get_doc(
			{
				"doctype": "User",
				"email": email_dono,
				"first_name": "Dono",
				"last_name": "Desabilitado",
				"mobile_no": celular_dono,
				"send_welcome_email": 0,
				"user_type": "Website User",
				"enabled": 0,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_apagar_definitivamente, "User", dono.name)

		dados = dict(_DADOS, canal_verificado="whatsapp", destino_verificado=celular_dono)
		usuario_antes = frappe.session.user
		with self.assertRaises(frappe.ValidationError):
			verificacao._garantir_usuario(dados)
		self.assertEqual(frappe.session.user, usuario_antes, "não pode logar em conta desabilitada")

	def test_canal_whatsapp_com_celular_de_system_user_e_recusado(self):
		email_interno, celular_interno = _identidade_unica("system.user.celular.task5")
		interno = frappe.get_doc(
			{
				"doctype": "User",
				"email": email_interno,
				"first_name": "Interno",
				"last_name": "ERP Celular",
				"mobile_no": celular_interno,
				"send_welcome_email": 0,
				"enabled": 1,
				# ver comentário equivalente no teste por e-mail acima.
				"roles": [{"role": "System Manager"}],
			}
		).insert(ignore_permissions=True)
		self.addCleanup(_apagar_definitivamente, "User", interno.name)
		self.assertEqual(interno.user_type, "System User", "precondição do teste")

		dados = dict(_DADOS, canal_verificado="whatsapp", destino_verificado=celular_interno)
		usuario_antes = frappe.session.user
		with self.assertRaises(frappe.ValidationError):
			verificacao._garantir_usuario(dados)
		self.assertEqual(frappe.session.user, usuario_antes, "não pode logar num System User")

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

	def tearDown(self):
		frappe.set_user("Administrator")

	def _confirmar(self, dados, appointment_time):
		token = _token()
		c = mod_codigo.emitir(token, dados)
		return verificacao.confirmar_codigo_e_agendar(
			codigo=c,
			verificacao_id=token,
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

	def test_solicitar_codigo_seguido_de_confirmar_agenda_de_ponta_a_ponta(self):
		"""Item 3 da revisão 2026-09-01: até aqui, TODO teste de
		``confirmar_codigo_e_agendar`` ancorava chamando ``mod_codigo.emitir``
		direto (ver ``_confirmar`` acima) — pulando o endpoint
		``solicitar_codigo`` por completo. A costura entre os dois endpoints
		(o ``verificacao_id`` que um devolve e o outro exige de volta —
		exatamente o que a correção do token opaco criou) nunca era
		exercitada por um teste. Este chama os DOIS endpoints públicos em
		sequência, como o navegador faz de verdade: pede o código de
		verdade (envio mockado, sem rede), captura o ``verificacao_id`` do
		retorno, e confirma com ele."""
		# Esta classe só reseta o balde de confirmar_codigo_e_agendar no
		# setUp (ver acima) — solicitar_codigo é uma chamada NOVA aqui, e o
		# balde é compartilhado por IP entre TODAS as classes deste módulo;
		# reset explícito para este teste não depender da ordem de execução
		# das classes vizinhas.
		_limpar_rate_limit_solicitar_codigo()
		email, celular = _identidade_unica("ciclo.real.task3")
		dados = dict(_DADOS, email=email, celular=celular)

		codigos_enviados = []
		with (
			patch.object(
				verificacao.canais, "disponiveis", return_value={"email": True, "whatsapp": False}
			),
			patch(
				"imunocare_ecommerce.conta.canais.enviar",
				side_effect=lambda canal, destino, codigo, nome: codigos_enviados.append(codigo),
			),
		):
			resposta = verificacao.solicitar_codigo("email", dados)

		self.assertEqual(len(codigos_enviados), 1)
		self.assertIn("verificacao_id", resposta)

		resultado = verificacao.confirmar_codigo_e_agendar(
			codigo=codigos_enviados[0],
			verificacao_id=resposta["verificacao_id"],
			appointment_date="2030-02-15",
			appointment_time="11:00:00",
			appointment_type=self._appointment_type.name,
			practitioner=self._practitioner.name,
		)
		self.addCleanup(_apagar_definitivamente, "User", email)
		self.addCleanup(_apagar_definitivamente, "Patient Appointment", resultado["appointment"])

		paciente = frappe.db.get_value("Patient Appointment", resultado["appointment"], "patient")
		self.addCleanup(_limpar_contatos_vinculados, "Patient", paciente)
		self.addCleanup(_apagar_definitivamente, "Patient", paciente)
		# create_customer (hook nativo do Healthcare) cria um Customer de
		# mesmo nome do Patient — órfão se não limpar.
		self.addCleanup(_apagar_definitivamente, "Customer", paciente)

		self.assertTrue(resultado["conta_criada"])
		self.assertEqual(resultado["usuario"], email)
		self.assertEqual(frappe.session.user, email)

		# A verificação da PRIMEIRA emissão foi consumida — confirmar de
		# novo com o mesmo par código/token tem que ser recusado (prova que
		# passamos pelo Redis de verdade, não por um atalho de teste).
		with self.assertRaises(mod_codigo.CodigoInvalido):
			mod_codigo.conferir(resposta["verificacao_id"], codigos_enviados[0])


class TestConcorrenciaEntreVisitantesAnonimos(FrappeTestCase):
	"""Prova o defeito CRÍTICO (comprovado por HTTP, não hipótese):
	``frappe.session.sid`` vale a MESMA string literal ("Guest") para
	QUALQUER visitante anônimo. Usá-lo como chave no Redis fazia dois
	visitantes concorrentes dividirem UMA ÚNICA chave — o segundo a pedir
	código apagava o do primeiro (``codigo.emitir`` faz DELETE+HSET antes de
	regravar), e a pessoa que pediu primeiro via "Código incorreto" mesmo
	digitando certo.

	Sem sid nenhum aqui de propósito: os testes deste módulo rodam fora de
	um request de verdade, onde ``frappe.session.sid`` vale sempre
	'Administrator' — um valor FIXO que mascararia justamente o bug (dois
	pedidos "simultâneos" cairiam na mesma chave por acidentes de ambiente
	de teste, não pela causa real). Este teste passa pelos DOIS endpoints
	públicos (``solicitar_codigo`` + ``confirmar_codigo_e_agendar``), com o
	token opaco (``verificacao_id``) que cada um devolve/recebe — a mesma
	superfície que o navegador do visitante usa. Tem que FALHAR no código
	antigo (chave = sid) e passar no novo (chave = token por verificação)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._appointment_type = frappe.get_doc(
			{
				"doctype": "Appointment Type",
				"appointment_type": "E2E Concorrencia Reserva Visitante",
				"allow_booking_for": "Practitioner",
				"default_duration": 30,
			}
		).insert(ignore_permissions=True)
		cls._practitioner = frappe.get_doc(
			{
				"doctype": "Healthcare Practitioner",
				"first_name": "Praticante Teste Concorrencia",
				"status": "Active",
			}
		).insert(ignore_permissions=True, ignore_mandatory=True)

	@classmethod
	def tearDownClass(cls):
		_apagar_definitivamente("Appointment Type", cls._appointment_type.name)
		_apagar_definitivamente("Healthcare Practitioner", cls._practitioner.name)
		super().tearDownClass()

	def setUp(self):
		frappe.local.request = frappe._dict(method="POST")
		frappe.local.request_ip = _IP_TESTE
		_limpar_rate_limit_solicitar_codigo()
		_limpar_rate_limit_confirmar_codigo()

		# Precondição: canal e-mail disponível (mesmo padrão de
		# TestSolicitarCodigo), e_mail_id próprio para não colidir com o
		# Email Account de outra classe deste módulo.
		self._conta_email = frappe.get_doc(
			{
				"doctype": "Email Account",
				"email_id": "verificacao-concorrencia@exemplo.com",
				"enable_outgoing": 1,
				"default_outgoing": 1,
				"smtp_server": "127.0.0.1",
				"awaiting_password": 1,
			}
		).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc,
			"Email Account",
			self._conta_email.name,
			force=True,
			ignore_permissions=True,
		)

		# Nenhum teste toca a rede: captura o código em claro pelo argumento
		# que canais.enviar receberia de verdade — é a única forma de saber
		# o código sem ele nunca aparecer na resposta HTTP (ver codigo.py).
		self._codigos_enviados = []
		patcher = patch(
			"imunocare_ecommerce.conta.canais.enviar",
			side_effect=lambda canal, destino, codigo, nome: self._codigos_enviados.append(codigo),
		)
		self.addCleanup(patcher.stop)
		patcher.start()

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_dois_visitantes_pedem_codigo_em_sequencia_sem_se_atropelar(self):
		email_ana, celular_ana = _identidade_unica("ana.concorrencia")
		email_bruno, celular_bruno = _identidade_unica("bruno.concorrencia")

		dados_ana = dict(
			_DADOS,
			nome="Ana Concorrência",
			email=email_ana,
			celular=celular_ana,
			cpf="39053344705",
			sexo="Female",
		)
		dados_bruno = dict(
			_DADOS,
			nome="Bruno Concorrência",
			email=email_bruno,
			celular=celular_bruno,
			cpf="52998224725",
			sexo="Male",
		)

		# Ana pede primeiro; Bruno pede DEPOIS, exatamente a ordem do
		# incidente relatado ("Ana pede o código -> Bruno pede o código ->
		# Ana digita o dela -> código incorreto").
		r_ana = verificacao.solicitar_codigo("email", dados_ana)
		r_bruno = verificacao.solicitar_codigo("email", dados_bruno)

		# O CERNE do fix: dois pedidos em sequência recebem tokens
		# DIFERENTES. No código antigo os dois caíam na MESMA chave
		# (frappe.session.sid == "Guest" para qualquer anônimo) e o pedido
		# de Bruno apagava o de Ana.
		self.assertIn("verificacao_id", r_ana)
		self.assertIn("verificacao_id", r_bruno)
		self.assertNotEqual(r_ana["verificacao_id"], r_bruno["verificacao_id"])

		self.assertEqual(len(self._codigos_enviados), 2)
		codigo_ana, codigo_bruno = self._codigos_enviados

		# Ana confirma com O DELA (pedido primeiro, código emitido primeiro)
		# DEPOIS que Bruno já pediu o dele — no bug antigo isto já bastava
		# para "Código incorreto" ou pior, confirmar com os dados de Bruno.
		resultado_ana = verificacao.confirmar_codigo_e_agendar(
			codigo=codigo_ana,
			verificacao_id=r_ana["verificacao_id"],
			appointment_date="2030-03-01",
			appointment_time="09:00:00",
			appointment_type=self._appointment_type.name,
			practitioner=self._practitioner.name,
		)
		self.addCleanup(_apagar_definitivamente, "User", email_ana)

		resultado_bruno = verificacao.confirmar_codigo_e_agendar(
			codigo=codigo_bruno,
			verificacao_id=r_bruno["verificacao_id"],
			appointment_date="2030-03-01",
			appointment_time="10:00:00",
			appointment_type=self._appointment_type.name,
			practitioner=self._practitioner.name,
		)
		self.addCleanup(_apagar_definitivamente, "User", email_bruno)

		self.addCleanup(_apagar_definitivamente, "Patient Appointment", resultado_ana["appointment"])
		self.addCleanup(
			_apagar_definitivamente, "Patient Appointment", resultado_bruno["appointment"]
		)

		pac_ana = frappe.db.get_value("Patient Appointment", resultado_ana["appointment"], "patient")
		pac_bruno = frappe.db.get_value(
			"Patient Appointment", resultado_bruno["appointment"], "patient"
		)
		self.addCleanup(_limpar_contatos_vinculados, "Patient", pac_ana)
		self.addCleanup(_limpar_contatos_vinculados, "Patient", pac_bruno)
		self.addCleanup(_apagar_definitivamente, "Patient", pac_ana)
		self.addCleanup(_apagar_definitivamente, "Patient", pac_bruno)
		# create_customer (hook nativo do Healthcare) cria um Customer de
		# mesmo nome do Patient — órfão se não limpar.
		self.addCleanup(_apagar_definitivamente, "Customer", "Ana Concorrência")
		self.addCleanup(_apagar_definitivamente, "Customer", "Bruno Concorrência")

		# Prova final de isolamento: cada um confirmou com o PRÓPRIO
		# código/token e caiu no PRÓPRIO cadastro — nenhum viu dado do outro.
		self.assertNotEqual(pac_ana, pac_bruno)
		self.assertEqual(frappe.db.get_value("Patient", pac_ana, "first_name"), "Ana")
		self.assertEqual(frappe.db.get_value("Patient", pac_bruno, "first_name"), "Bruno")
		self.assertNotEqual(resultado_ana["appointment"], resultado_bruno["appointment"])

	def test_verificacao_id_ausente_ou_invalido_e_recusado_com_mensagem_generica(self):
		"""Ausente, vazio, tipo errado ou desconhecido — SEMPRE a mesma
		recusa genérica de código expirado, nunca revelando a diferença
		entre "token inválido" e "código expirado de verdade"."""
		for valor_invalido in (None, "", "token-que-nunca-existiu", 123, ["a"], {"x": 1}):
			with self.subTest(valor_invalido=valor_invalido):
				with self.assertRaises(mod_codigo.CodigoInvalido):
					verificacao.confirmar_codigo_e_agendar(
						codigo="000000",
						verificacao_id=valor_invalido,
						appointment_date="2030-03-01",
						appointment_time="09:00:00",
					)

	def test_verificacao_id_omitido_e_recusado(self):
		"""Nem chamado (default None do parâmetro) — mesmo caminho do teste
		acima, mas sem passar o argumento, para provar que o default do
		endpoint também é seguro."""
		with self.assertRaises(mod_codigo.CodigoInvalido):
			verificacao.confirmar_codigo_e_agendar(
				codigo="000000",
				appointment_date="2030-03-01",
				appointment_time="09:00:00",
			)


class TestRegressaoCriarAgendamento(FrappeTestCase):
	def test_criar_agendamento_continua_recusando_guest(self):
		"""A porta de entrada do visitante é a função nova, não esta."""
		from imunocare_ecommerce.agendamento.booking import criar_agendamento

		frappe.set_user("Guest")
		self.addCleanup(frappe.set_user, "Administrator")
		with self.assertRaises(frappe.PermissionError):
			criar_agendamento(appointment_date="2030-01-10", appointment_time="09:00:00")
