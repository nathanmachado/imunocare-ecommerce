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
});

// ---------------------------------------------------------------------------
// Página do item (produto único) — Atividade 541
// ---------------------------------------------------------------------------

function imun_decidir_botao_pagina_item() {
	var itemEl = document.querySelector("[data-item-code]");
	if (!itemEl) {
		return;
	}
	var item_code = itemEl.getAttribute("data-item-code");
	if (!item_code) {
		return;
	}

	// Sinal exposto pela Atividade 540 (templates/generators/item/item.html +
	// catalogo.jinja_utils.imun_sinal_servico) — evita a ida ao backend no
	// caso comum ("produto": mantém o botão nativo tal como já está na tela).
	var $productPage = $(".imun-product-page").first();
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
		if (!info.logged_in) {
			window.location.href =
				"/login?redirect-to=" + encodeURIComponent(window.location.pathname);
			return;
		}
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
		if (!frappe.session.user || frappe.session.user === "Guest") {
			window.location.href =
				"/login?redirect-to=" + encodeURIComponent(window.location.pathname);
			return;
		}
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
function imun_abrir_dialogo_agendamento(params, info) {
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
			imun_montar_dialogo_agendamento(params, info, r.message || {});
		},
	});
}

function imun_montar_dialogo_agendamento(params, info, domiciliar_info) {
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

// Reuso site-wide (R2/Feature 70 — carrossel de médicos na home,
// public/js/medicos_carrossel.js): mesmo diálogo de agendamento, sem
// duplicar a lógica de disponibilidade/confirmação acima.
window.imunAbrirAgendamentoDialogo = imun_abrir_dialogo_agendamento;
