// Camada de rastreio first-party da jornada do cliente (Feature 56 / A2.1).
//
// Reuso: NÃO usa Google Analytics nem Meta Pixel (isso é a Feature B/C, e
// envolve cookies/consentimento de terceiros). Tudo aqui fala só com o
// próprio ERPNext (imunocare_ecommerce.rastreio.api), site-wide via
// hooks.web_include_js, como o seo_jsonld.js/agendamento.js já fazem.
//
// LGPD (Feature 56 / A2.2): nenhum evento é enviado ao servidor antes do
// cliente clicar "Aceitar" no banner de consentimento. Enquanto o
// consentimento estiver pendente ou recusado, este script não grava cookie
// nenhum, não gera identificador nenhum e não faz nenhuma chamada de rede —
// "não rastrear" é o comportamento padrão.
(function () {
	"use strict";

	var COOKIE_VISITOR = "imun_vid";
	var STORAGE_SESSION = "imun_sid";
	var STORAGE_CONSENT = "imun_consent";
	var HEARTBEAT_MS = 30000;
	var VISITOR_MAX_AGE_DIAS = 400;

	var _config = null;
	var _heartbeatTimer = null;

	function iniciar() {
		if (!window.frappe || !frappe.call) {
			return;
		}
		frappe.call({
			method: "imunocare_ecommerce.rastreio.api.config",
			callback: function (r) {
				_config = (r && r.message) || { ativo: false };
				if (!_config.ativo) {
					return;
				}
				var consentimento = _lerConsentimento();
				if (consentimento === "aceito") {
					_iniciarRastreio();
				} else if (!consentimento) {
					_exibirBanner();
				}
				// consentimento === "recusado" -> não faz nada (não rastreia).
			},
		});
	}

	// -------------------------------------------------------------------
	// Consentimento (LGPD)
	// -------------------------------------------------------------------

	function _lerConsentimento() {
		try {
			return window.localStorage.getItem(STORAGE_CONSENT);
		} catch (e) {
			return null;
		}
	}

	function _salvarConsentimento(valor) {
		try {
			window.localStorage.setItem(STORAGE_CONSENT, valor);
		} catch (e) {
			// localStorage indisponível (modo privado etc.) — degrada sem rastrear.
		}
	}

	function _exibirBanner() {
		if (document.getElementById("imun-consent-banner")) {
			return;
		}
		var texto =
			(_config && _config.texto_banner) ||
			__(
				"Usamos cookies e identificadores anônimos para entender sua navegação e melhorar nossos serviços. Sem seu consentimento, nada é registrado."
			);
		var politica = (_config && _config.politica_privacidade_url) || "/politica-de-privacidade";

		var $banner = $(
			'<div id="imun-consent-banner" style="position:fixed;left:0;right:0;bottom:0;z-index:9999;' +
				"background:#222;color:#fff;padding:14px 20px;font-size:14px;display:flex;" +
				'flex-wrap:wrap;gap:12px;align-items:center;justify-content:space-between;">' +
				'<span style="flex:1;min-width:240px;">' +
				frappe.utils.escape_html(texto) +
				' <a href="' +
				politica +
				'" target="_blank" style="color:#9cf;">' +
				__("Saiba mais") +
				"</a></span>" +
				'<span style="display:flex;gap:8px;white-space:nowrap;">' +
				'<button type="button" class="btn btn-sm btn-light imun-consent-recusar">' +
				__("Recusar") +
				"</button>" +
				'<button type="button" class="btn btn-sm btn-primary imun-consent-aceitar">' +
				__("Aceitar") +
				"</button>" +
				"</span></div>"
		);
		$("body").append($banner);

		$banner.on("click", ".imun-consent-aceitar", function () {
			_salvarConsentimento("aceito");
			$banner.remove();
			_iniciarRastreio(true);
		});
		$banner.on("click", ".imun-consent-recusar", function () {
			_salvarConsentimento("recusado");
			$banner.remove();
			// Por opção de design (ver rastreio/api.py): recusa não gera nenhuma
			// chamada de rede — só o registro local da preferência do usuário.
		});
	}

	// -------------------------------------------------------------------
	// Identificadores (só existem com consentimento aceito)
	// -------------------------------------------------------------------

	function _gerarId() {
		if (window.crypto && crypto.randomUUID) {
			return crypto.randomUUID().replace(/-/g, "");
		}
		return (
			Date.now().toString(36) + Math.random().toString(36).slice(2) + Math.random().toString(36).slice(2)
		).slice(0, 32);
	}

	function _lerCookie(nome) {
		var match = document.cookie.match(new RegExp("(?:^|; )" + nome + "=([^;]*)"));
		return match ? decodeURIComponent(match[1]) : null;
	}

	function _gravarCookie(nome, valor, diasValidade) {
		var expira = new Date();
		expira.setTime(expira.getTime() + diasValidade * 24 * 60 * 60 * 1000);
		document.cookie =
			nome + "=" + encodeURIComponent(valor) + ";expires=" + expira.toUTCString() + ";path=/;SameSite=Lax";
	}

	function _visitorId() {
		var vid = _lerCookie(COOKIE_VISITOR);
		if (!vid) {
			vid = _gerarId();
			_gravarCookie(COOKIE_VISITOR, vid, VISITOR_MAX_AGE_DIAS);
		}
		return vid;
	}

	function _sessionId() {
		var sid = null;
		try {
			sid = window.sessionStorage.getItem(STORAGE_SESSION);
		} catch (e) {
			// sessionStorage indisponível — gera um id efêmero só para esta página
			// (perde continuidade entre páginas, mas não quebra o rastreio).
		}
		if (!sid) {
			sid = _gerarId();
			try {
				window.sessionStorage.setItem(STORAGE_SESSION, sid);
			} catch (e) {
				/* noop */
			}
		}
		return sid;
	}

	// -------------------------------------------------------------------
	// UTM / referrer (capturados só na 1ª página da sessão)
	// -------------------------------------------------------------------

	function _parametroUrl(nome) {
		try {
			return new URLSearchParams(window.location.search).get(nome);
		} catch (e) {
			return null;
		}
	}

	function _contextoOrigem() {
		return {
			utm_source: _parametroUrl("utm_source"),
			utm_medium: _parametroUrl("utm_medium"),
			utm_campaign: _parametroUrl("utm_campaign"),
			utm_term: _parametroUrl("utm_term"),
			utm_content: _parametroUrl("utm_content"),
			gclid: _parametroUrl("gclid"),
			fbclid: _parametroUrl("fbclid"),
			referrer: document.referrer || null,
		};
	}

	// -------------------------------------------------------------------
	// Envio de eventos
	// -------------------------------------------------------------------

	function _enviarEvento(tipoEvento, extra) {
		var args = Object.assign(
			{
				visitor_id: _visitorId(),
				session_id: _sessionId(),
				tipo_evento: tipoEvento,
				rota: window.location.pathname,
			},
			extra || {}
		);
		frappe.call({
			method: "imunocare_ecommerce.rastreio.api.evento",
			type: "POST",
			args: args,
		});
	}

	function _iniciarRastreio(primeiraVezNestaSessao) {
		var sessaoJaIniciada = false;
		try {
			sessaoJaIniciada = !!window.sessionStorage.getItem(STORAGE_SESSION);
		} catch (e) {
			/* trata como nova */
		}

		var extra = {};
		if (!sessaoJaIniciada) {
			extra = _contextoOrigem();
		}
		_enviarEvento(primeiraVezNestaSessao ? "consentimento_aceito" : "page_view", extra);

		_ligarCarrinho();
		_ligarCliquesLoja();
		_ligarHeartbeat();
	}

	function _ligarCarrinho() {
		frappe.call({
			method: "imunocare_ecommerce.rastreio.api.vincular_carrinho_atual",
			args: { session_id: _sessionId() },
		});
	}

	function _ligarCliquesLoja() {
		// Delegado no document: cobre botões renderizados após o load (listagem
		// de produtos, cart dropdown, etc.) sem tocar nos templates do webshop.
		$(document).on("click", ".btn-add-to-cart, .btn-add-to-cart-list", function () {
			var itemCode = $(this).attr("data-item-code");
			_enviarEvento("add_to_cart", { metadados: JSON.stringify({ item_code: itemCode }) });
		});
		$(document).on("click", ".remove-cart-item", function () {
			var itemCode = $(this).attr("data-item-code");
			_enviarEvento("remove_from_cart", { metadados: JSON.stringify({ item_code: itemCode }) });
		});
		$(document).on("click", 'a[href^="tel:"]', function () {
			_enviarEvento("call_click");
		});
		$(document).on("click", 'a[href*="wa.me"], a[href*="api.whatsapp.com"]', function () {
			_enviarEvento("whatsapp_click");
		});
	}

	function _ligarHeartbeat() {
		function ping() {
			if (document.visibilityState === "visible") {
				_enviarEvento("heartbeat");
			}
		}
		_heartbeatTimer = window.setInterval(ping, HEARTBEAT_MS);
		document.addEventListener("visibilitychange", function () {
			if (document.visibilityState === "visible" && !_heartbeatTimer) {
				_heartbeatTimer = window.setInterval(ping, HEARTBEAT_MS);
			}
		});
	}

	// Exposto para outros scripts do app (ex.: agendamento.js) amarrarem a
	// conversão à sessão SEM duplicar a lógica de consentimento/ids aqui.
	// Retorna null quando o rastreio não está ativo/consentido — os
	// chamadores devem tratar isso como "sem sessão para vincular" (nunca
	// bloqueante).
	window.ImunRastreio = {
		sessionId: function () {
			return _lerConsentimento() === "aceito" ? _sessionId() : null;
		},
	};

	if (window.frappe && frappe.ready) {
		frappe.ready(iniciar);
	} else {
		document.addEventListener("DOMContentLoaded", iniciar);
	}
})();
