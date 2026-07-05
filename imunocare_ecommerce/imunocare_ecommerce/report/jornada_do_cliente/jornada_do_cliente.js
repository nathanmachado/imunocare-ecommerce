// Filtros do relatório "Jornada do Cliente" (Feature 56 / A2.3).
frappe.query_reports["Jornada do Cliente"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("De"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
		},
		{
			fieldname: "to_date",
			label: __("Até"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
		},
		{
			fieldname: "origem",
			label: __("Origem"),
			fieldtype: "Select",
			options: "\nGoogle Ads\nMeta Ads\nBusca Orgânica\nReferência\nDireto\nOutra Campanha",
		},
		{
			fieldname: "somente_convertidos",
			label: __("Somente sessões que viraram Lead"),
			fieldtype: "Check",
		},
		{
			fieldname: "somente_carrinho_abandonado",
			label: __("Somente carrinho abandonado"),
			fieldtype: "Check",
		},
	],
};
