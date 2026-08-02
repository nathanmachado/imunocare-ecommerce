"""Landing "Protocolo de Emagrecimento com Acompanhamento Médico" (F9).

ads-safe: copy revisada para as políticas de saúde do Google Ads/Meta,
RDC 96/2008 (Anvisa) e código de ética médica (CFM) — NUNCA menciona
mounjaro/tirzepatida/semaglutida/marcas/princípios ativos, "caneta
emagrecedora", promessa quantitativa de peso perdido, preço de medicamento,
nem venda online de medicamento (o produto aqui é o SERVIÇO — avaliação
médica). Ver ``landing.protocolo_emagrecimento`` para o backend do CTA.

Reuso: SEO via Website Route Meta (``landing.setup._meta_paginas_estaticas``);
CTA reusa o agendamento online já construído em ``agendamento.booking``
(A1.3), sem Website Item de medicamento (fora do catálogo de produtos).
"""

from __future__ import annotations

import frappe

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.title = "Protocolo de Emagrecimento com Acompanhamento Médico — Imunocare"

	context.appointment_type = frappe.db.get_single_value(
		"Imunocare Ecommerce Settings", "protocolo_emagrecimento_appointment_type"
	)
	return context
