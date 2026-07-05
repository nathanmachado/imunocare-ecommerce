// Widget de agendamento online (Feature 55 / A1.3).
//
// Reuso: injeta um botão "Agendar" na página nativa de detalhe do Website
// Item (webshop `templates/generators/item/item.html`/`item_details.html`)
// SEM tocar nesses templates — lê o item_code do atributo `data-item-code`
// que o webshop já renderiza no botão "Add to Cart" e usa `frappe.ui.Dialog`
// (já carregado nessa página pelo próprio webshop via `dialog.bundle.js`).
//
// Site-wide via hooks.web_include_js — roda em toda página pública e sai
// cedo se não houver item agendável na página atual.
frappe.ready(function () {
	var itemEl = document.querySelector("[data-item-code]");
	if (!itemEl) {
		return;
	}
	var item_code = itemEl.getAttribute("data-item-code");
	if (!item_code) {
		return;
	}

	frappe.call({
		method: "imunocare_ecommerce.agendamento.booking.info_agendamento",
		args: { item_code: item_code },
		callback: function (r) {
			var info = r.message;
			if (!info || !info.agendavel) {
				return;
			}
			imun_render_botao_agendar(item_code, info);
		},
	});
});

function imun_render_botao_agendar(item_code, info) {
	var $host = $(".item-cart").first();
	if (!$host.length) {
		return;
	}
	var $btn = $(
		'<button type="button" class="btn btn-primary mt-2 imun-btn-agendar">' +
			__("Agendar Consulta") +
			"</button>"
	);
	$host.append($btn);

	$btn.on("click", function () {
		if (!info.logged_in) {
			window.location.href =
				"/login?redirect-to=" + encodeURIComponent(window.location.pathname);
			return;
		}
		imun_abrir_dialogo_agendamento(item_code, info);
	});
}

function imun_abrir_dialogo_agendamento(item_code, info) {
	var d = new frappe.ui.Dialog({
		title: __("Agendar Consulta"),
		fields: [
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
		],
		primary_action_label: __("Confirmar Agendamento"),
		primary_action: function (values) {
			if (!values.appointment_time) {
				frappe.msgprint(__("Selecione um horário disponível."));
				return;
			}
			frappe.call({
				method: "imunocare_ecommerce.agendamento.booking.criar_agendamento",
				args: {
					item_code: item_code,
					appointment_date: values.appointment_date,
					appointment_time: values.appointment_time,
					practitioner: info.practitioner,
					// Rastreio da jornada (Feature 56 / A2.4) — null se o cliente não
					// consentiu, e o agendamento segue normalmente sem UTM/origem.
					session_id: window.ImunRastreio ? window.ImunRastreio.sessionId() : null,
				},
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
						frappe.msgprint({
							title: __("Agendamento confirmado"),
							message: __(
								"Seu agendamento ({0}) foi registrado. Nossa equipe entrará em contato para combinar o pagamento.",
								[r.message.appointment]
							),
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
			args: { item_code: item_code, data: data, practitioner: info.practitioner },
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
