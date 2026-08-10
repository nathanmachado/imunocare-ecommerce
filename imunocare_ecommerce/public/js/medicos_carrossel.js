// Carrossel de médicos parceiros na home (R2 — Feature 70 / REDO do site).
//
// Reuso: o botão "Agendar" de cada card abre o MESMO diálogo de agendamento
// já usado pelo item da loja (public/js/agendamento.js,
// window.imunAbrirAgendamentoDialogo) — passando {appointment_type}
// (agendamento direto, sem Website Item — mesmo formato já suportado por
// agendamento.booking._resolver_agendavel/_tipo_agendavel_direto, usado
// também pela landing "Protocolo de Emagrecimento") em vez de {item_code}.
// Nenhuma lógica de disponibilidade/confirmação é duplicada aqui.
//
// O profissional vem do PRÓPRIO card (data-practitioner, Healthcare
// Practitioner.name) — não deixamos o backend "adivinhar" o profissional
// (o que só funciona quando existe exatamente 1 Practitioner Ativo no
// sistema, ver agendamento.booking._resolver_practitioner) porque o
// carrossel pode ter vários médicos publicados ao mesmo tempo.
//
// Site-wide via hooks.web_include_js — no-op silencioso se a home não tiver
// nenhum card publicado (medicos vazio -> seção some, ver www/index.html).
frappe.ready(function () {
	$(document).on("click", ".imun-medico-agendar", function () {
		var $btn = $(this);
		var practitioner = $btn.data("practitioner");
		var appointmentType = $btn.data("appointment-type");
		if (!appointmentType || !practitioner) {
			return;
		}
		if (!frappe.session.user || frappe.session.user === "Guest") {
			window.location.href =
				"/login?redirect-to=" +
				encodeURIComponent(window.location.pathname + "#medicos-parceiros");
			return;
		}
		if (!window.imunAbrirAgendamentoDialogo) {
			return;
		}
		window.imunAbrirAgendamentoDialogo(
			{ appointment_type: appointmentType },
			{ practitioner: practitioner, logged_in: true }
		);
	});
});
