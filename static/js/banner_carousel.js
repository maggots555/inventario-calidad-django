"use strict";
/**
 * banner_carousel.ts — Carrusel automático para banners promocionales
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este script busca todos los "slots" de banners en la página.
 * Si un slot tiene más de un banner, los rota automáticamente cada 5 segundos
 * con una transición suave de fade. El usuario puede hacer clic en los dots
 * para saltar a un banner específico.
 *
 * Funciona para todos los tipos de slots:
 * - Skyscrapers laterales (desktop)
 * - Banners horizontales (header, medio, footer)
 *
 * Sistema SIGMA — Abril 2026
 */
(function () {
    // Tiempo entre rotaciones: 5 segundos
    const ROTATION_INTERVAL = 5000;
    /**
     * Inicializa el carrusel de un slot específico.
     * Solo actúa si hay más de 1 slide en el slot.
     */
    function initSlot(slot) {
        const slides = Array.from(slot.querySelectorAll('.st-banner-slide'));
        const dots = Array.from(slot.querySelectorAll('.st-banner-dot'));
        if (slides.length <= 1) {
            // Un solo banner: no se necesita carrusel
            return null;
        }
        const state = {
            slot,
            slides,
            dots,
            total: slides.length,
            current: 0,
            timer: null,
            interval: ROTATION_INTERVAL,
        };
        // Hacer los dots interactivos
        dots.forEach((dot, index) => {
            dot.setAttribute('role', 'button');
            dot.setAttribute('tabindex', '0');
            dot.setAttribute('aria-label', `Banner ${index + 1} de ${slides.length}`);
            dot.addEventListener('click', () => {
                goToSlide(state, index);
                resetTimer(state);
            });
            dot.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    goToSlide(state, index);
                    resetTimer(state);
                }
            });
        });
        // Iniciar la rotación automática
        startTimer(state);
        // Pausar la rotación cuando el usuario interactúa (hover/focus)
        slot.addEventListener('mouseenter', () => pauseTimer(state));
        slot.addEventListener('focusin', () => pauseTimer(state));
        slot.addEventListener('mouseleave', () => startTimer(state));
        slot.addEventListener('focusout', () => {
            // Solo reanudar si el foco salió completamente del slot
            if (!slot.contains(document.activeElement)) {
                startTimer(state);
            }
        });
        return state;
    }
    /**
     * Navega a un slide específico por índice.
     */
    function goToSlide(state, index) {
        var _a, _b;
        // Ocultar slide actual
        state.slides[state.current].classList.remove('st-banner-slide--active');
        (_a = state.dots[state.current]) === null || _a === void 0 ? void 0 : _a.classList.remove('st-banner-dot--active');
        // Activar nuevo slide
        state.current = (index + state.total) % state.total;
        state.slides[state.current].classList.add('st-banner-slide--active');
        (_b = state.dots[state.current]) === null || _b === void 0 ? void 0 : _b.classList.add('st-banner-dot--active');
    }
    /**
     * Avanza al siguiente slide.
     */
    function nextSlide(state) {
        goToSlide(state, state.current + 1);
    }
    /**
     * Inicia el temporizador de rotación automática.
     */
    function startTimer(state) {
        if (state.timer !== null)
            return; // Ya corriendo
        state.timer = setInterval(() => {
            nextSlide(state);
        }, state.interval);
    }
    /**
     * Pausa el temporizador (hover/focus).
     */
    function pauseTimer(state) {
        if (state.timer !== null) {
            clearInterval(state.timer);
            state.timer = null;
        }
    }
    /**
     * Reinicia el temporizador (después de interacción manual).
     */
    function resetTimer(state) {
        pauseTimer(state);
        startTimer(state);
    }
    /**
     * Inicializa todos los slots de banners en la página.
     */
    function initAll() {
        // Seleccionar todos los slots que tienen más de 1 banner
        const slots = document.querySelectorAll('.st-banner-slot[data-banners]');
        slots.forEach((slot) => {
            var _a;
            const bannerCount = parseInt((_a = slot.getAttribute('data-banners')) !== null && _a !== void 0 ? _a : '1', 10);
            if (bannerCount > 1) {
                initSlot(slot);
            }
        });
    }
    // Esperar a que el DOM esté listo
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    }
    else {
        initAll();
    }
})();
//# sourceMappingURL=banner_carousel.js.map