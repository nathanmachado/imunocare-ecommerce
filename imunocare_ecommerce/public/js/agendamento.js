// Widget de agendamento online (Feature 55 / A1.3; evoluído na Feature 72 —
// Atividade 541 — "botão contextual": este arquivo passou de "só ADICIONA um
// botão Agendar" para "DECIDE o botão" — serviço esconde o nativo e mostra
// "Agendar"; produto mantém o nativo. Nenhum item fica sem botão (fallback
// explícito: se algo estiver mal configurado, o nativo continua visível).
//
// Reuso: injeta/decide o botão na página nativa de detalhe do Website Item
// (webshop `templates/generators/item/item.html`/`item_details.html`) e no
// grid/lista nativos (`webshop.ProductGrid`/`ProductList`,
// `product_ui/grid.js`/`list.js`) SEM tocar nesses templates/arquivos — só
// lê o sinal já exposto (Atividade 540 — data-attribute na página do item,
// `item.imun_servico` no JSON do grid, ver `catalogo.api.get_product_filter_data_loja`)
// e usa `frappe.ui.Dialog` (já carregado nessa página pelo próprio webshop
// via `dialog.bundle.js`).
//
// Site-wide via hooks.web_include_js — roda em toda página pública e sai
// cedo se não houver item agendável na página atual.
frappe.ready(function () {
	imun_decidir_botao_pagina_item();
	imun_patch_botao_grid();
	imun_retomar_reserva_pendente();
});

// Reserva como visitante (Task 6) — sessionStorage "imun_reserva_pendente":
// sobrevive à ida ao /login e ao reload do caso "horário sumiu" (ver
// imun_passo_codigo). Carimbado com ``criado_em`` e limpo no fechamento dos
// diálogos "Quase lá"/"Digite o código" quando a pessoa DESISTE (fix round 1
// — achado da review 2026-09-01: sem isso, uma aba que loga bem depois por
// qualquer outro motivo reabria o modal sozinho com data/horário velhos).
var IMUN_RESERVA_PENDENTE_TTL_MS = 30 * 60 * 1000; // 30 min

function imun_guardar_reserva_pendente(escolha) {
	escolha.criado_em = Date.now();
	sessionStorage.setItem("imun_reserva_pendente", JSON.stringify(escolha));
}

function imun_limpar_reserva_pendente() {
	sessionStorage.removeItem("imun_reserva_pendente");
}

// Quem foi ao /login, ou cujo horário sumiu enquanto digitava o código,
// volta/recarrega aqui — reabre o modal com a escolha preservada. O horário
// É REVALIDADO (imun_montar_dialogo_agendamento chama get_horarios de novo
// via preset), porque nunca ficou reservado enquanto a pessoa se
// identificava. Cobre os dois formatos de escolha: item da loja
// (``item_code``) e agendamento direto por profissional (``appointment_type``
// + ``practitioner``, carrossel de médicos — ``medicos_carrossel.js``).
function imun_retomar_reserva_pendente() {
	var pendente = sessionStorage.getItem("imun_reserva_pendente");
	if (!pendente || !frappe.session.user || frappe.session.user === "Guest") {
		return;
	}
	sessionStorage.removeItem("imun_reserva_pendente");
	var e = JSON.parse(pendente);
	if (!e.criado_em || Date.now() - e.criado_em > IMUN_RESERVA_PENDENTE_TTL_MS) {
		// Escolha velha demais — não reabre sozinho com data/horário obsoletos.
		return;
	}
	if (e.item_code) {
		frappe.call({
			method: "imunocare_ecommerce.agendamento.booking.info_agendamento",
			args: { item_code: e.item_code },
			callback: function (r) {
				if (r.message && r.message.agendavel) {
					imun_abrir_dialogo_agendamento({ item_code: e.item_code }, r.message, e);
				}
			},
		});
		return;
	}
	if (e.appointment_type && e.practitioner) {
		// Mesmo padrão do clique original em medicos_carrossel.js: o
		// profissional já foi escolhido no card, sem ida ao backend — só repõe
		// o mesmo params/info que o clique teria montado.
		imun_abrir_dialogo_agendamento(
			{ appointment_type: e.appointment_type },
			{ practitioner: e.practitioner, logged_in: true },
			e
		);
	}
}

// ---------------------------------------------------------------------------
// Página do item (produto único) — Atividade 541
// ---------------------------------------------------------------------------

function imun_decidir_botao_pagina_item() {
	// Atividade 550 (fix): lê o item_code do NOSSO container primeiro
	// (".imun-product-page[data-imun-item-code]", Atividade 540) e só cai para
	// "[data-item-code]" do webshop como FALLBACK. O atributo do webshop vive
	// no botão "Adicionar ao carrinho" (item_add_to_cart.html, upstream), que
	// só renderiza se passar por uma cadeia de condições do carrinho
	// (shopping_cart.cart_settings.enabled; product_info.price e
	// in_stock/allow_items_not_in_stock) — nada disso tem relação com o item
	// ser agendável. Quando essas condições falhavam, "[data-item-code]" não
	// existia em NENHUM lugar da página, a função saía aqui na 1ª linha e o
	// botão "Agendar" sumia silenciosamente, sem erro (bug confirmado no
	// navegador). O nosso container não tem essa dependência.
	var $productPage = $(".imun-product-page").first();
	var item_code = $productPage.attr("data-imun-item-code");
	if (!item_code) {
		var itemEl = document.querySelector("[data-item-code]");
		item_code = itemEl ? itemEl.getAttribute("data-item-code") : null;
	}
	if (!item_code) {
		return;
	}

	// Sinal exposto pela Atividade 540 (templates/generators/item/item.html +
	// catalogo.jinja_utils.imun_sinal_servico) — evita a ida ao backend no
	// caso comum ("produto": mantém o botão nativo tal como já está na tela).
	var sinalServico = $productPage.length && $productPage.attr("data-imun-servico") === "1";
	if (!sinalServico) {
		return;
	}

	// Confirmação/validação completa no backend (agendamento.booking já sabe
	// se o Appointment Type/profissional realmente funcionam) — só ENTÃO
	// esconde o botão nativo. Fallback explícito (SPEC item 4): se
	// `agendavel` vier falso (ex.: Appointment Type foi apagado depois), o
	// botão nativo de produto permanece visível — a página nunca fica sem
	// nenhum botão.
	frappe.call({
		method: "imunocare_ecommerce.agendamento.booking.info_agendamento",
		args: { item_code: item_code },
		callback: function (r) {
			var info = r.message;
			if (!info || !info.agendavel) {
				return;
			}
			imun_esconder_botao_nativo_pagina();
			imun_render_botao_agendar(item_code, info);
		},
	});
}

function imun_esconder_botao_nativo_pagina() {
	// item_add_to_cart.html (webshop, upstream): ".btn-add-to-cart" ("Add to
	// Cart"/"Add to Quote") e ".btn-view-in-cart" ("View in Cart"/"View in
	// Quote") — os dois únicos botões de carrinho da página do item.
	$(".item-cart .btn-add-to-cart, .item-cart .btn-view-in-cart").addClass("d-none");
}

function imun_render_botao_agendar(item_code, info) {
	var $host = $(".item-cart").first();
	if (!$host.length) {
		return;
	}
	var $btn = $(
		'<button type="button" class="btn btn-primary mt-2 imun-btn-agendar">' +
			__("Agendar") +
			"</button>"
	);
	$host.append($btn);

	$btn.on("click", function () {
		// A parede de /login caiu (Reserva como visitante — Task 6): o modal
		// abre para qualquer um; quem não está logado é ramificado para a
		// identificação/verificação dentro do próprio diálogo, no Confirmar
		// (ver imun_montar_dialogo_agendamento/imun_passo_identificacao).
		imun_abrir_dialogo_agendamento({ item_code: item_code }, info);
	});
}

// ---------------------------------------------------------------------------
// Grid/lista de listagem (all-products, categorias) — Atividade 541
//
// Monkey-patch de `webshop.ProductGrid`/`ProductList.get_primary_button`
// (mesmo padrão de `product_grid_style.js`, que já faz o mesmo com
// `get_card_body_html`): guarda a implementação NATIVA e só substitui a
// saída quando `item.imun_servico` vier `1` (enriquecido pelo backend, ver
// `catalogo.api.get_product_filter_data_loja`) — produto continua 100%
// nativo (Add to Cart/Quote, variantes, estoque, preço), sem duplicar essa
// lógica aqui.
// ---------------------------------------------------------------------------

function imun_patch_botao_grid() {
	if (typeof webshop === "undefined") {
		return;
	}

	if (webshop.ProductGrid && !webshop.ProductGrid.prototype._imun_patched) {
		var original_grid_btn = webshop.ProductGrid.prototype.get_primary_button;
		webshop.ProductGrid.prototype.get_primary_button = function (item, settings) {
			if (item.imun_servico) {
				return imun_html_botao_agendar_card(item);
			}
			return original_grid_btn.call(this, item, settings);
		};
		webshop.ProductGrid.prototype._imun_patched = true;
	}

	if (webshop.ProductList && !webshop.ProductList.prototype._imun_patched) {
		var original_list_btn = webshop.ProductList.prototype.get_primary_button;
		webshop.ProductList.prototype.get_primary_button = function (item, settings) {
			if (item.imun_servico) {
				return imun_html_botao_agendar_card(item);
			}
			return original_list_btn.call(this, item, settings);
		};
		webshop.ProductList.prototype._imun_patched = true;
	}
}

function imun_html_botao_agendar_card(item) {
	return (
		'<div class="btn btn-sm btn-primary w-100 mt-2 imun-btn-agendar-card" ' +
		'data-item-code="' +
		frappe.utils.escape_html(item.item_code || "") +
		'">' +
		__("Agendar") +
		"</div>"
	);
}

// Delegado (os cards são recriados a cada render/"Carregar mais" — ver
// product_list_more.js) — clique abre o MESMO diálogo da página do item,
// mas só depois de validar no backend (agendamento.booking.info_agendamento)
// que o serviço realmente está configurado; fallback: se não estiver, avisa
// o cliente em vez de abrir um diálogo quebrado (nunca lança 500).
frappe.ready(function () {
	$(document).on("click", ".imun-btn-agendar-card", function (e) {
		e.preventDefault();
		var item_code = $(this).data("item-code");
		if (!item_code) {
			return;
		}
		// A parede de /login caiu aqui também (Reserva como visitante —
		// Task 6): o card da listagem abre o mesmo modal para qualquer um.
		frappe.call({
			method: "imunocare_ecommerce.agendamento.booking.info_agendamento",
			args: { item_code: item_code },
			freeze: true,
			callback: function (r) {
				var info = r.message;
				if (!info || !info.agendavel) {
					frappe.msgprint(
						__("Este item ainda não está disponível para agendamento online. Fale com a clínica.")
					);
					return;
				}
				imun_abrir_dialogo_agendamento({ item_code: item_code }, info);
			},
		});
	});
});

// Diálogo de agendamento compartilhado — aceita ``params`` com
// ``{item_code}`` (item da loja, fluxo A1.3 acima) OU ``{appointment_type}``
// (agendamento direto, ex.: carrossel de médicos na home — R2/Feature 70)
// porque ``agendamento.booking`` já resolve os dois formatos
// (``_resolver_agendavel``). Exposto em ``window.imunAbrirAgendamentoDialogo``
// para outros scripts site-wide reusarem sem duplicar o diálogo inteiro.
//
// ``preset`` (opcional, Reserva como visitante — Task 6): ``{appointment_date,
// appointment_time}`` de uma escolha feita ANTES de identificar/logar —
// preenche o diálogo ao reabrir depois do /login ou depois de uma
// verificação, mas o horário É REVALIDADO normalmente (não fica reservado
// enquanto a pessoa se identifica).
function imun_abrir_dialogo_agendamento(params, info, preset) {
	// F3 (evoluído na Atividade 542-dep / Feature 72): modalidade "Na clínica
	// x Domiciliar" — consome ``info_domiciliar_agendamento`` (elegibilidade
	// POR SERVIÇO: só oferece Domiciliar quando o Appointment Type do item
	// tiver ``imun_permite_domiciliar=1``, lido defensivamente — ver
	// ``agendamento/domiciliar.py``). Antes desta atividade a elegibilidade
	// era só o flag GLOBAL da loja (``info_domiciliar()``, ainda usado pelo
	// carrinho de produtos em ``domiciliar_cart.js``, sem noção de serviço).
	frappe.call({
		method: "imunocare_ecommerce.agendamento.domiciliar.info_domiciliar_agendamento",
		args: params,
		callback: function (r) {
			imun_montar_dialogo_agendamento(params, info, r.message || {}, preset);
		},
	});
}

// PORQUÊ ISTO EXISTE (fix crítico 2026-09-01 — "Agendar" não abria nada, nem
// para visitante nem para cliente logado, no bench E em produção):
//
// ``frappe.ui.Dialog`` com campo ``fieldtype: "Date"`` é um CONTROLE DE DESK
// (``ControlDate``). Ao montar, ele chama
// ``frappe.datetime.now_date()`` -> ``_date()``
// (frappe/public/js/frappe/utils/datetime.js:237), que lê
// ``frappe.boot.time_zone?.system || frappe.sys_defaults.time_zone``. No
// Desk, ``frappe.sys_defaults`` é atribuído a partir de
// ``frappe.boot.sysdefaults`` no bootstrap (frappe/public/js/frappe/desk.js:321)
// — mas ISSO NUNCA RODA numa página pública da loja. Lá ``frappe.boot`` existe
// (o site injeta), porém sem ``time_zone`` e sem ``sysdefaults``, e
// ``frappe.sys_defaults`` fica simplesmente indefinido. Resultado real:
// ``Cannot read properties of undefined (reading 'time_zone')`` dentro de
// ``make_picker``/``get_now_date``, o diálogo estoura ANTES de exibir
// qualquer coisa (``.modal.show`` nunca aparece no DOM) — não é paranoia,
// foi reproduzido no bench e em produção.
//
// A correção não reimplementa nada do Desk: só PREENCHE o que falta usando o
// que o backend (agendamento.booking.info_agendamento/info_agendamento_tipo,
// função ``_boot_datas``) já devolve — mesmo formato que
// ``frappe.website.utils.get_boot_data`` usa para ``time_zone``
// (system/user). NUNCA sobrescreve valor já existente: no Desk esses campos
// vêm certos e não podem ser mexidos; aqui só entram quando ausentes.
//
// Precisa rodar ANTES de qualquer ``new frappe.ui.Dialog(...)`` que tenha
// campo Date — não só o de agendamento (``appointment_date``), também o de
// identificação do visitante (``dob``/``paciente_dob``, mais abaixo).
function imun_garantir_boot_datas(info) {
	info = info || {};
	frappe.boot = frappe.boot || {};

	if (!frappe.boot.time_zone) {
		if (info.time_zone) {
			frappe.boot.time_zone = info.time_zone;
		} else {
			// Alguns chamadores (ex.: public/js/medicos_carrossel.js — carrossel
			// de médicos da home) montam o ``info`` localmente, SEM passar pelo
			// backend, e por isso nunca trazem time_zone. Sem isso o mesmo
			// ControlDate quebraria ali também. Fuso do navegador é aproximação
			// razoável só para o widget de calendário abrir em "hoje" — a data
			// escolhida vira uma string ``yyyy-mm-dd`` de qualquer forma
			// (get_horarios/criar_agendamento não dependem de fuso).
			var fuso_navegador =
				(window.Intl && Intl.DateTimeFormat().resolvedOptions().timeZone) || "America/Sao_Paulo";
			frappe.boot.time_zone = { system: fuso_navegador, user: fuso_navegador };
		}
	}

	frappe.boot.sysdefaults = frappe.boot.sysdefaults || {};
	if (!frappe.boot.sysdefaults.date_format && info.date_format) {
		frappe.boot.sysdefaults.date_format = info.date_format;
	}
	if (!frappe.boot.sysdefaults.time_format && info.time_format) {
		frappe.boot.sysdefaults.time_format = info.time_format;
	}

	// frappe.sys_defaults é o que datetime.js realmente lê em vários pontos
	// (fallback de time_zone, first_day_of_the_week etc.) — só é espelhado a
	// partir de frappe.boot.sysdefaults no bootstrap do Desk, que a loja
	// nunca executa.
	frappe.sys_defaults = frappe.sys_defaults || {};
	frappe.sys_defaults.date_format = frappe.sys_defaults.date_format || frappe.boot.sysdefaults.date_format;
	frappe.sys_defaults.time_format = frappe.sys_defaults.time_format || frappe.boot.sysdefaults.time_format;
	frappe.sys_defaults.time_zone = frappe.sys_defaults.time_zone || frappe.boot.time_zone.system;
}

function imun_montar_dialogo_agendamento(params, info, domiciliar_info, preset) {
	imun_garantir_boot_datas(info);
	var fields = [
		{
			fieldname: "appointment_date",
			label: __("Data"),
			fieldtype: "Date",
			reqd: 1,
		},
		{
			fieldname: "horarios_html",
			fieldtype: "HTML",
		},
		{
			fieldname: "appointment_time",
			label: __("Horário selecionado"),
			fieldtype: "Data",
			read_only: 1,
		},
	];

	if (domiciliar_info.ativo) {
		fields.push({
			fieldname: "modalidade_sb",
			fieldtype: "Section Break",
		});
		fields.push({
			fieldname: "modalidade",
			label: __("Atendimento"),
			fieldtype: "Select",
			options: __("Na clínica") + "\n" + __("Domiciliar (+ taxa)"),
			default: __("Na clínica"),
			description: __(
				"No atendimento domiciliar, a taxa de {0} é confirmada e cobrada pela recepção — ainda não é cobrada automaticamente neste agendamento online.",
				[domiciliar_info.taxa_fmt]
			),
		});
	}

	var d = new frappe.ui.Dialog({
		// Título genérico (Feature 72): este diálogo compartilhado agenda
		// vacina/vitamina/terapia/consulta — não só "Consulta" (mesmo botão
		// "Agendar" em toda a loja, ver imun_render_botao_agendar/
		// imun_html_botao_agendar_card/medicos_carrossel.js).
		title: __("Agendar"),
		fields: fields,
		primary_action_label: __("Confirmar Agendamento"),
		primary_action: function (values) {
			if (!values.appointment_time) {
				frappe.msgprint(__("Selecione um horário disponível."));
				return;
			}
			var domiciliar = domiciliar_info.ativo && values.modalidade === __("Domiciliar (+ taxa)");

			// Reserva como visitante (Task 6): guest chegou até o Confirmar
			// sem logar — ramifica para identificação/verificação em vez de
			// chamar criar_agendamento direto (que recusa Guest). O horário
			// escolhido aqui é só a INTENÇÃO; confirmar_codigo_e_agendar é
			// quem de fato cria o agendamento, já logado.
			if (!info.logged_in) {
				imun_passo_identificacao(d, params, info, values, domiciliar);
				return;
			}

			frappe.call({
				method: "imunocare_ecommerce.agendamento.booking.criar_agendamento",
				args: Object.assign(
					{
						appointment_date: values.appointment_date,
						appointment_time: values.appointment_time,
						practitioner: info.practitioner,
						modalidade: domiciliar ? "Domiciliar" : "Na Clínica",
						// Rastreio da jornada (Feature 56 / A2.4) — null se o cliente não
						// consentiu, e o agendamento segue normalmente sem UTM/origem.
						session_id: window.ImunRastreio ? window.ImunRastreio.sessionId() : null,
					},
					params
				),
				freeze: true,
				freeze_message: __("Agendando..."),
				callback: function (r) {
					if (!r.message) {
						return;
					}
					d.hide();
					if (r.message.payment_url) {
						window.location.href = r.message.payment_url;
					} else {
						var mensagem = __(
							"Seu agendamento ({0}) foi registrado. Nossa equipe entrará em contato para combinar o pagamento.",
							[r.message.appointment]
						);
						if (r.message.aviso_domiciliar) {
							mensagem += "<br><br>" + frappe.utils.escape_html(r.message.aviso_domiciliar);
						}
						frappe.msgprint({
							title: __("Agendamento confirmado"),
							message: mensagem,
							indicator: "green",
						});
					}
				},
			});
		},
	});

	d.fields_dict.appointment_date.$input.on("change", function () {
		var data = d.get_value("appointment_date");
		if (!data) {
			return;
		}
		var $wrap = d.fields_dict.horarios_html.$wrapper;
		$wrap.html('<div class="text-muted">' + __("Consultando horários...") + "</div>");
		d.set_value("appointment_time", "");

		frappe.call({
			method: "imunocare_ecommerce.agendamento.booking.get_horarios",
			args: Object.assign({ data: data, practitioner: info.practitioner }, params),
			callback: function (r) {
				imun_render_horarios(d, r.message || {});
			},
		});
	});

	d.show();

	// Reabertura pós-login/verificação (Task 6): repõe a escolha de data/hora
	// de antes de identificar — o listener de "change" acima revalida o
	// horário no backend (get_horarios), porque ele NÃO ficou reservado
	// enquanto a pessoa se verificava.
	if (preset) {
		d.set_value("appointment_date", preset.appointment_date);
		d.set_value("appointment_time", preset.appointment_time);
	}
}

function imun_render_horarios(d, res) {
	var $wrap = d.fields_dict.horarios_html.$wrapper;
	if (res.aviso) {
		$wrap.html('<div class="text-muted">' + frappe.utils.escape_html(res.aviso) + "</div>");
		return;
	}
	if (!res.horarios || !res.horarios.length) {
		$wrap.html('<div class="text-muted">' + __("Nenhum horário livre nesta data.") + "</div>");
		return;
	}
	var html = res.horarios
		.map(function (h) {
			return (
				'<button type="button" class="btn btn-outline-primary btn-sm mr-1 mb-1 imun-slot-btn" data-hora="' +
				h.hora +
				'">' +
				h.hora.slice(0, 5) +
				"</button>"
			);
		})
		.join("");
	$wrap.html(html);
	$wrap.on("click", ".imun-slot-btn", function () {
		$wrap.find(".imun-slot-btn").removeClass("btn-primary").addClass("btn-outline-primary");
		$(this).removeClass("btn-outline-primary").addClass("btn-primary");
		d.set_value("appointment_time", $(this).data("hora"));
	});
}

// ---------------------------------------------------------------------------
// Reserva como visitante (Task 6) — identificação + código, dentro do
// próprio modal. Backend: imunocare_ecommerce.conta.verificacao (Tasks 4/5).
// ---------------------------------------------------------------------------

// Guest que chegou ao Confirmar: escolhe entrar na conta ou se verificar.
// ``info`` é o mesmo objeto que o clique original montou (item da loja OU
// carrossel de médicos) — carregamos ``info.practitioner`` na escolha para
// que o fluxo por ``appointment_type`` (sem Website Item) consiga resolver o
// profissional em ``confirmar_codigo_e_agendar`` sem depender do "só existe
// 1 Practitioner Ativo" (ver agendamento.booking._resolver_practitioner).
function imun_passo_identificacao(dialogo, params, info, values, domiciliar) {
	// Este diálogo também tem campos Date (dob/paciente_dob) — mesma
	// quebra do ControlDate na loja (ver imun_garantir_boot_datas acima).
	// Idempotente/nunca sobrescreve: repetir aqui é seguro mesmo já tendo
	// rodado ao montar o diálogo de agendamento.
	imun_garantir_boot_datas(info);
	var escolha = {
		item_code: params.item_code,
		appointment_type: params.appointment_type,
		practitioner: info.practitioner,
		appointment_date: values.appointment_date,
		appointment_time: values.appointment_time,
		modalidade: domiciliar ? "Domiciliar" : "Na Clínica",
	};
	// Sobrevive ao page load do /login (botão "Já tenho conta") e a um
	// reload após "horário sumiu" (ver o error: do passo do código). Limpo no
	// on_hide dos dois diálogos abaixo quando a pessoa DESISTE (fecha sem
	// avançar) — não só ao fechar a aba.
	imun_guardar_reserva_pendente(escolha);

	dialogo.hide();
	var avancouParaCodigo = false;
	var d2 = new frappe.ui.Dialog({
		title: __("Quase lá"),
		fields: [
			{
				fieldtype: "HTML",
				options: "<p>" + __("Para confirmar o horário escolhido, identifique-se.") + "</p>",
			},
			{ fieldname: "ja_tenho_conta", fieldtype: "Button", label: __("Já tenho conta") },
			{ fieldtype: "Section Break" },
			{ fieldname: "nome", fieldtype: "Data", label: __("Nome completo"), reqd: 1 },
			{ fieldname: "celular", fieldtype: "Data", label: __("Celular / WhatsApp"), reqd: 1 },
			{ fieldname: "email", fieldtype: "Data", label: __("E-mail"), options: "Email", reqd: 1 },
			{ fieldname: "cpf", fieldtype: "Data", label: __("CPF"), reqd: 1 },
			{ fieldname: "dob", fieldtype: "Date", label: __("Data de nascimento"), reqd: 1 },
			{
				fieldname: "sexo",
				fieldtype: "Select",
				label: __("Sexo"),
				options: "\nMale\nFemale\nOther",
				reqd: 1,
			},
			{
				fieldname: "para_outra_pessoa",
				fieldtype: "Check",
				label: __("A consulta é para outra pessoa"),
				description: __(
					"Menor de 18 anos só pode ser agendado por um responsável — marque esta opção e informe os dados de quem vai ser atendido."
				),
			},
			{
				fieldname: "paciente_nome",
				fieldtype: "Data",
				label: __("Nome do paciente"),
				depends_on: "para_outra_pessoa",
				mandatory_depends_on: "para_outra_pessoa",
			},
			{
				fieldname: "paciente_cpf",
				fieldtype: "Data",
				label: __("CPF do paciente"),
				depends_on: "para_outra_pessoa",
				mandatory_depends_on: "para_outra_pessoa",
			},
			{
				fieldname: "paciente_dob",
				fieldtype: "Date",
				label: __("Nascimento do paciente"),
				depends_on: "para_outra_pessoa",
				mandatory_depends_on: "para_outra_pessoa",
			},
			{
				fieldname: "paciente_sexo",
				fieldtype: "Select",
				label: __("Sexo do paciente"),
				options: "\nMale\nFemale\nOther",
				depends_on: "para_outra_pessoa",
				mandatory_depends_on: "para_outra_pessoa",
			},
			{ fieldtype: "Section Break" },
			{
				fieldname: "canal",
				fieldtype: "Select",
				label: __("Receber o código por"),
				reqd: 1,
				// Mudança de contrato (revisão de segurança 2026-09-01): o canal
				// não é cosmético — é ele que ANCORA a conta. Verificar por
				// WhatsApp identifica pelo CELULAR; por e-mail, pelo E-MAIL. Quem
				// já tem conta de e-mail e verifica por WhatsApp pode entrar numa
				// conta nova, não na antiga.
				description: __(
					"O contato que você confirmar aqui é o que abre/identifica sua conta — não o outro campo do formulário."
				),
			},
		],
		primary_action_label: __("Receber código"),
		primary_action: function (v) {
			var canalEfetivo = v.canal === __("WhatsApp") ? "whatsapp" : "email";
			frappe.call({
				method: "imunocare_ecommerce.conta.verificacao.solicitar_codigo",
				args: { canal: canalEfetivo, dados: v },
				freeze: true,
				freeze_message: __("Enviando código..."),
				callback: function (r) {
					if (!r.message) {
						return;
					}
					avancouParaCodigo = true;
					d2.hide();
					imun_passo_codigo(escolha, r.message, { canal: canalEfetivo, dados: v });
				},
			});
		},
		on_hide: function () {
			// Fechou sem avançar (X, backdrop, Esc) = desistiu — não deixa a
			// escolha pendente reabrir o modal sozinho depois.
			if (!avancouParaCodigo) {
				imun_limpar_reserva_pendente();
			}
		},
	});

	d2.fields_dict.ja_tenho_conta.$input.on("click", function () {
		window.location.href = "/login?redirect-to=" + encodeURIComponent(window.location.pathname);
	});

	// O seletor só oferece o canal que está operacional AGORA.
	frappe.call({
		method: "imunocare_ecommerce.conta.verificacao.canais_disponiveis",
		callback: function (r) {
			var opcoes = [];
			if ((r.message || {}).whatsapp) {
				opcoes.push(__("WhatsApp"));
			}
			if ((r.message || {}).email) {
				opcoes.push(__("E-mail"));
			}
			d2.set_df_property("canal", "options", opcoes.join("\n"));
			if (opcoes.length === 1) {
				d2.set_value("canal", opcoes[0]);
			}
		},
	});

	d2.show();
}

// Passo do código — ``reenvio`` guarda {canal, dados} da última chamada a
// ``solicitar_codigo`` para o botão "Reenviar código" reenviar o mesmo
// formulário. Cada emissão vira uma chave PRÓPRIA no Redis (não sobrescreve
// mais nenhuma outra) — por isso o reenvio manda também
// ``verificacao_id_anterior`` (o ``envio.verificacao_id`` corrente, lido no
// clique) para o servidor descartar a verificação velha antes de emitir a
// nova (ver conta/verificacao.py:_descartar_verificacao_anterior).
function imun_passo_codigo(escolha, envio, reenvio) {
	var concluido = false;
	var recarregando = false;
	var d3 = new frappe.ui.Dialog({
		title: __("Digite o código"),
		fields: [
			{ fieldname: "aviso_html", fieldtype: "HTML" },
			{ fieldname: "codigo", fieldtype: "Data", label: __("Código de 6 dígitos"), reqd: 1 },
		],
		primary_action_label: __("Confirmar reserva"),
		primary_action: function (v) {
			frappe.call({
				method: "imunocare_ecommerce.conta.verificacao.confirmar_codigo_e_agendar",
				args: {
					codigo: v.codigo,
					// envio.verificacao_id é lido no momento do clique, não na criação
					// do diálogo — "Reenviar código" reatribui envio (abaixo) com um
					// token NOVO, e o antigo tem que ser descartado (é a chave que
					// muda no Redis a cada emissão).
					verificacao_id: envio.verificacao_id,
					appointment_date: escolha.appointment_date,
					appointment_time: escolha.appointment_time,
					item_code: escolha.item_code,
					appointment_type: escolha.appointment_type,
					practitioner: escolha.practitioner,
					modalidade: escolha.modalidade,
					session_id: window.ImunRastreio ? window.ImunRastreio.sessionId() : null,
				},
				freeze: true,
				freeze_message: __("Confirmando..."),
				callback: function (r) {
					if (!r.message) {
						return;
					}
					concluido = true;
					imun_limpar_reserva_pendente();
					d3.hide();
					imun_mensagem_confirmacao_guest(r.message);
				},
				error: function (r) {
					// Código errado/expirado/bloqueado e "menor sem responsável"
					// acontecem ANTES do login (dentro de
					// confirmar_codigo_e_agendar, antes de _garantir_usuario) — a
					// mensagem do servidor já aparece sozinha (frappe.call mostra
					// _server_messages mesmo com este `error` custom, ver
					// frappe/public/js/frappe/request.js:cleanup); não duplicamos
					// a regra aqui, só não engolimos o erro (não fazemos nada:
					// dialogo continua aberto, campo código pronto pra nova
					// tentativa/reenvio).
					//
					// O ÚNICO caso tratado aqui é o esperado do passo 5: horário
					// tomado enquanto a pessoa digitava o código. Esse ponto só é
					// alcançado DEPOIS de login_as/criação de conta — a pessoa
					// perde o horário, nunca o cadastro. Identificado pela classe
					// de exceção do healthcare (Patient Appointment.
					// validate_overlaps), não pelo texto da mensagem.
					var exc = r && r.exc_type;
					if (exc !== "OverlapError" && exc !== "MaximumCapacityError") {
						return;
					}
					recarregando = true;
					d3.hide();
					// Item 6 da revisão 2026-09-01: OverlapError do healthcare
					// (patient_appointment.py:validate_overlaps) não significa só
					// "outra pessoa preencheu esse horário" — o mesmo erro cobre
					// "você (o mesmo paciente) já tem uma consulta nesse dia". A
					// mensagem cobre os dois sentidos sem afirmar qual foi.
					frappe.msgprint({
						title: __("Não foi possível confirmar este horário"),
						message: __(
							"Esse horário pode ter sido preenchido por outra pessoa, ou você já tem uma consulta marcada para esse dia. Sua conta já está criada e você está conectado — escolha outro horário."
						),
						indicator: "orange",
					});
					// Recarrega para o front enxergar a sessão nova e reabrir o
					// modal já logado, com a data revalidada. Timestamp novo: essa
					// escolha acabou de nascer, não herda a idade da anterior.
					imun_guardar_reserva_pendente(escolha);
					setTimeout(function () {
						window.location.reload();
					}, 2500);
				},
			});
		},
		secondary_action_label: __("Reenviar código"),
		secondary_action: function () {
			if (!reenvio) {
				return;
			}
			frappe.call({
				method: "imunocare_ecommerce.conta.verificacao.solicitar_codigo",
				// verificacao_id_anterior = o token que ainda está com a pessoa
				// nessa hora (lido de ``envio``, não de ``reenvio``, que nunca muda) —
				// o servidor descarta essa chave velha antes de emitir a nova.
				args: Object.assign({}, reenvio, { verificacao_id_anterior: envio.verificacao_id }),
				freeze: true,
				freeze_message: __("Reenviando código..."),
				callback: function (r) {
					if (!r.message) {
						return;
					}
					envio = r.message;
					imun_atualizar_aviso_codigo(d3, envio);
					d3.set_value("codigo", "");
					frappe.show_alert({ message: __("Novo código enviado."), indicator: "green" });
				},
			});
		},
		on_hide: function () {
			// Fechou sem confirmar e sem cair no caso "horário sumiu" (que já
			// regrava a escolha pendente sozinho) = desistiu de verdade.
			if (!concluido && !recarregando) {
				imun_limpar_reserva_pendente();
			}
		},
	});
	imun_atualizar_aviso_codigo(d3, envio);
	d3.show();
}

function imun_atualizar_aviso_codigo(d3, envio) {
	d3.fields_dict.aviso_html.$wrapper.html(
		"<p>" +
			__("Enviamos um código para {0}. Ele vale por 10 minutos.", [
				frappe.utils.escape_html(envio.destino_mascarado),
			]) +
			"</p>"
	);
}

// Mensagem final do fluxo de visitante — mesmo shape de resultado de
// criar_agendamento (payment_url/aviso_domiciliar), acrescido de
// ``conta_criada`` (Task 5): diferencia "criamos sua conta" de "você entrou
// numa conta que já existia" (ex.: CPF já cadastrado, ou celular/e-mail já
// era de um Website User).
function imun_mensagem_confirmacao_guest(resultado) {
	if (resultado.payment_url) {
		window.location.href = resultado.payment_url;
		return;
	}
	var contaMsg = resultado.conta_criada
		? __("Criamos sua conta para você acompanhar este e outros agendamentos.")
		: __("Você entrou na conta que já tinha conosco.");
	var mensagem = __(
		"Seu agendamento ({0}) foi registrado. Nossa equipe entrará em contato para combinar o pagamento.",
		[resultado.appointment]
	);
	mensagem += "<br><br>" + contaMsg;
	if (resultado.aviso_domiciliar) {
		mensagem += "<br><br>" + frappe.utils.escape_html(resultado.aviso_domiciliar);
	}

	// Item 1 da revisão 2026-09-01: frappe.session.user foi lido no
	// carregamento da página e continua "Guest" no cliente mesmo depois de
	// confirmar_codigo_e_agendar logar a pessoa no servidor — o cabeçalho do
	// site seguiria mostrando "Entrar" para quem acabou de criar conta.
	// Atualiza o valor em memória com o que o backend REALMENTE logou
	// (``resultado.usuario`` — nunca adivinhado no cliente) e recarrega a
	// página para o cabeçalho refletir a sessão nova. O reload só acontece
	// quando este diálogo FECHA (custom_onhide, disparado por qualquer jeito
	// de fechar — botão OK, X, clique fora, ESC): a pessoa sempre lê a
	// mensagem de sucesso antes, nunca pisca.
	if (resultado.usuario) {
		frappe.session.user = resultado.usuario;
	}
	var dialogo = frappe.msgprint({
		title: __("Reserva confirmada"),
		message: mensagem,
		indicator: "green",
	});
	if (resultado.usuario && dialogo) {
		dialogo.custom_onhide = function () {
			window.location.reload();
		};
	}
}

// Reuso site-wide (R2/Feature 70 — carrossel de médicos na home,
// public/js/medicos_carrossel.js): mesmo diálogo de agendamento, sem
// duplicar a lógica de disponibilidade/confirmação acima.
window.imunAbrirAgendamentoDialogo = imun_abrir_dialogo_agendamento;
