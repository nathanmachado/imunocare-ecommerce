// Carrossel do hero da home (REDESIGN 2026-09-04, iteração 2 — pedido do
// dono): produtos em DESTAQUE (catalogo.setup.hero_carrossel), renderizados
// no Jinja de www/index.html como uma lista de <a> reais (1 por slide) —
// este script só cuida da APRESENTAÇÃO (mostrar 1 por vez, autoplay,
// setas/dots, teclado) e nunca da navegação em si (cada slide já é um link
// de verdade para a categoria do produto: funciona por tab+Enter mesmo sem
// JS nenhum, ver `tabindex`/`aria-hidden` que o Jinja já alterna).
//
// Acessibilidade (pedido explícito do dono):
//   - Autoplay ~5s, PAUSADO no hover/foco (mouseenter/focusin) e retomado
//     no mouseleave/focusout.
//   - `prefers-reduced-motion: reduce` -> autoplay NUNCA liga (troca só por
//     clique/teclado/dots).
//   - Setas + dots são <button> nativos (foco/Enter/Espaço de graça); o
//     slide ativo vira `tabindex="0"`/`aria-hidden="false"`, os demais
//     `tabindex="-1"`/`aria-hidden="true"` (não roubam Tab enquanto ocultos).
//
// Site-wide (web_include_js) — no-op fora da home (sem
// `[data-imun-hero-carrossel]` na página).
(function () {
	var AUTOPLAY_MS = 5000;

	function iniciar(raiz) {
		var track = raiz.querySelector("[data-imun-slide]") && raiz.querySelector(".imun-hero-carrossel-track");
		var slides = Array.prototype.slice.call(raiz.querySelectorAll("[data-imun-slide]"));
		var dots = Array.prototype.slice.call(raiz.querySelectorAll("[data-imun-dot]"));
		var btnPrev = raiz.querySelector("[data-imun-prev]");
		var btnNext = raiz.querySelector("[data-imun-next]");

		if (!track || slides.length === 0) return;

		var atual = 0;
		var timer = null;
		var reduzMovimento =
			window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

		function ir(indice) {
			indice = ((indice % slides.length) + slides.length) % slides.length;
			slides[atual].classList.remove("is-active");
			slides[atual].setAttribute("aria-hidden", "true");
			slides[atual].setAttribute("tabindex", "-1");
			if (dots[atual]) {
				dots[atual].classList.remove("is-active");
				dots[atual].setAttribute("aria-selected", "false");
			}

			atual = indice;

			slides[atual].classList.add("is-active");
			slides[atual].setAttribute("aria-hidden", "false");
			slides[atual].setAttribute("tabindex", "0");
			if (dots[atual]) {
				dots[atual].classList.add("is-active");
				dots[atual].setAttribute("aria-selected", "true");
			}
		}

		function proximo() {
			ir(atual + 1);
		}

		function anterior() {
			ir(atual - 1);
		}

		function ligarAutoplay() {
			if (reduzMovimento || slides.length < 2) return;
			pararAutoplay();
			timer = window.setInterval(proximo, AUTOPLAY_MS);
		}

		function pararAutoplay() {
			if (timer) {
				window.clearInterval(timer);
				timer = null;
			}
		}

		if (btnPrev) {
			btnPrev.addEventListener("click", function () {
				anterior();
				ligarAutoplay(); // reinicia a contagem após interação manual
			});
		}
		if (btnNext) {
			btnNext.addEventListener("click", function () {
				proximo();
				ligarAutoplay();
			});
		}
		dots.forEach(function (dot, indice) {
			dot.addEventListener("click", function () {
				ir(indice);
				ligarAutoplay();
			});
		});

		// Pausa no hover/foco (mouse e teclado) — requisito explícito do dono.
		raiz.addEventListener("mouseenter", pararAutoplay);
		raiz.addEventListener("mouseleave", ligarAutoplay);
		raiz.addEventListener("focusin", pararAutoplay);
		raiz.addEventListener("focusout", ligarAutoplay);

		// Setas do teclado quando o foco está dentro do carrossel (extra —
		// tab/Enter nos <a> já navegam de graça, isso só melhora o troca-de-
		// slide sem precisar percorrer os botões).
		raiz.addEventListener("keydown", function (ev) {
			if (ev.key === "ArrowRight") {
				proximo();
				ligarAutoplay();
			} else if (ev.key === "ArrowLeft") {
				anterior();
				ligarAutoplay();
			}
		});

		ir(0);
		ligarAutoplay();
	}

	function iniciarTudo() {
		document.querySelectorAll("[data-imun-hero-carrossel]").forEach(iniciar);
	}

	if (window.frappe && typeof frappe.ready === "function") {
		frappe.ready(iniciarTudo);
	} else {
		document.addEventListener("DOMContentLoaded", iniciarTudo);
	}
})();
