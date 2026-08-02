"""Página institucional "Parceria com Médicos" (F8) — proposta de valor ao
médico parceiro + formulário -> CRM Lead (ver ``landing.parceria_medicos``).

Reuso: SEO via Website Route Meta (``landing.setup._meta_paginas_estaticas``,
mesmo padrão nativo usado pelo resto da loja); rastreio de origem/UTM via
``rastreio.js``/``window.ImunRastreio`` (Feature 56 / A2), já site-wide.
"""

from __future__ import annotations

no_cache = 1


def get_context(context):
	context.no_cache = 1
	context.title = "Parceria com Médicos — Imunocare"
	return context
