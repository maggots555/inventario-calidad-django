"use strict";
/**
 * mi_perfil.ts
 * Carrusel de opiniones de clientes en "Mi Perfil" y "Directorio".
 * + Selector de cursor personalizado (modal, solo vista propia).
 *
 * Enfoque: translateX en PÍXELES (no %) para evitar el bug de porcentaje
 * relativo al track en lugar de al wrapper.
 *
 * Cursor: usa window.SigmaCursor (cursor_personalizado.js en base.html).
 * Guarda preferencia en localStorage clave 'sigma-cursor' (como el tema).
 * Los tipos de SigmaCursor / CursorId viven en cursor_personalizado.ts (globales).
 */
// ── Clase principal del carrusel ───────────────────────────────────────────
class ReviewCarousel {
    constructor(wrapper) {
        this.current = 0;
        this.autoTimer = null;
        this.AUTO_INTERVAL_MS = 4500;
        this.touchStartX = 0;
        this.touchStartY = 0;
        this.wrapper = wrapper;
        const track = wrapper.querySelector('.review-track');
        const dotsBar = wrapper.querySelector('.review-dots-bar');
        if (!track || !dotsBar)
            return;
        this.track = track;
        this.dotsBar = dotsBar;
        this.slides = Array.from(track.querySelectorAll('.review-slide')).map((el) => {
            var _a, _b;
            return ({
                element: el,
                rating: parseInt((_a = el.dataset['rating']) !== null && _a !== void 0 ? _a : '0', 10),
                recomienda: (_b = el.dataset['recomienda']) !== null && _b !== void 0 ? _b : '',
            });
        });
        if (this.slides.length === 0)
            return;
        this._setSlideDimensions(); // Asignar ancho en px ANTES de todo
        this._renderStars();
        this._buildDots();
        this._updateView();
        // Recalcular ancho y posición si la ventana cambia de tamaño
        window.addEventListener('resize', () => {
            this._setSlideDimensions();
            this._updateView();
        });
        // Auto-scroll
        this._startAuto();
        // Pausa en hover y focus
        this.wrapper.addEventListener('mouseenter', () => this._stopAuto());
        this.wrapper.addEventListener('mouseleave', () => this._startAuto());
        this.wrapper.addEventListener('focusin', () => this._stopAuto());
        this.wrapper.addEventListener('focusout', () => this._startAuto());
        // Swipe táctil
        this.wrapper.addEventListener('touchstart', (e) => {
            this.touchStartX = e.touches[0].clientX;
            this.touchStartY = e.touches[0].clientY;
        }, { passive: true });
        this.wrapper.addEventListener('touchend', (e) => {
            const dx = e.changedTouches[0].clientX - this.touchStartX;
            const dy = e.changedTouches[0].clientY - this.touchStartY;
            if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 40) {
                this._goTo(dx < 0 ? this._nextIndex() : this._prevIndex());
                this._resetAuto();
            }
        }, { passive: true });
    }
    // ── Asignar ancho exacto a cada slide en píxeles ─────────────────────
    // EXPLICACIÓN: width:100% en un hijo flex resuelve contra el TRACK
    // (que mide N × wrapper), no contra el wrapper. Por eso asignamos
    // el ancho del wrapper directamente como valor px en cada slide.
    _setSlideDimensions() {
        const w = this.wrapper.offsetWidth;
        this.slides.forEach(({ element }) => {
            element.style.width = `${w}px`;
        });
    }
    // ── Dibujar estrellas ──────────────────────────────────────────────────
    _renderStars() {
        this.slides.forEach(({ element, rating }) => {
            const container = element.querySelector('.review-stars-display');
            if (!container)
                return;
            container.innerHTML = '';
            for (let i = 1; i <= 5; i++) {
                const star = document.createElement('span');
                star.textContent = '★';
                star.className = i <= rating ? 'rs-star rs-filled' : 'rs-star rs-empty';
                star.setAttribute('aria-hidden', 'true');
                container.appendChild(star);
            }
        });
    }
    // ── Construir puntos de navegación ────────────────────────────────────
    _buildDots() {
        this.dotsBar.innerHTML = '';
        if (this.slides.length <= 1)
            return;
        this.slides.forEach((_, idx) => {
            const dot = document.createElement('button');
            dot.className = 'review-dot';
            dot.type = 'button';
            dot.setAttribute('aria-label', `Ir a opinión ${idx + 1}`);
            dot.addEventListener('click', (e) => {
                e.preventDefault();
                this._goTo(idx);
                this._resetAuto();
            });
            this.dotsBar.appendChild(dot);
        });
    }
    // ── Navegar a slide ───────────────────────────────────────────────────
    _goTo(index) {
        this.current = index;
        this._updateView();
    }
    // ── Actualizar posición usando PÍXELES (no %) ─────────────────────────
    // EXPLICACIÓN: translateX(%) usa % del elemento mismo (el track),
    // que mide N veces el wrapper si hay N slides. Por eso usamos px.
    _updateView() {
        const slideWidth = this.wrapper.offsetWidth;
        this.track.style.transform = `translateX(-${this.current * slideWidth}px)`;
        // Actualizar dots
        const dots = this.dotsBar.querySelectorAll('.review-dot');
        dots.forEach((dot, idx) => {
            dot.classList.toggle('active', idx === this.current);
            dot.setAttribute('aria-pressed', String(idx === this.current));
        });
        // Accesibilidad
        this.slides.forEach(({ element }, idx) => {
            element.setAttribute('aria-hidden', String(idx !== this.current));
        });
    }
    // ── Índices cíclicos ──────────────────────────────────────────────────
    _nextIndex() {
        return (this.current + 1) % this.slides.length;
    }
    _prevIndex() {
        return (this.current - 1 + this.slides.length) % this.slides.length;
    }
    // ── Auto-scroll ───────────────────────────────────────────────────────
    _startAuto() {
        if (this.slides.length <= 1)
            return;
        this._stopAuto();
        this.autoTimer = setInterval(() => this._goTo(this._nextIndex()), this.AUTO_INTERVAL_MS);
    }
    _stopAuto() {
        if (this.autoTimer !== null) {
            clearInterval(this.autoTimer);
            this.autoTimer = null;
        }
    }
    _resetAuto() {
        this._stopAuto();
        this._startAuto();
    }
}
/**
 * Nombres legibles para el label “Preferencia actual”.
 * CursorId es el type global definido en cursor_personalizado.ts.
 */
const CURSOR_NOMBRES = {
    tech: 'Tech Cyan',
    classic: 'Classic Gold',
    minimal: 'Minimal',
    banana: 'Banana',
    hongo: 'Hongo Mario',
    metallica: 'Metallica M',
    ganso: 'Ganso',
    system: 'Sistema',
};
/**
 * Inicializa el modal de personalizar cursor en Mi Perfil.
 *
 * Objetivo: al elegir una card, guardar + aplicar vía window.SigmaCursor.
 * Efectos: localStorage (dentro de SigmaCursor.aplicar) y UI selected/label.
 */
function inicializarSelectorCursorPerfil() {
    const grid = document.getElementById('cursor-options-grid');
    const modal = document.getElementById('modalPersonalizarCursor');
    // Vista directorio u otras páginas sin modal → salir en silencio
    if (!grid || !modal) {
        return;
    }
    const api = window.SigmaCursor;
    const labelActual = document.getElementById('cursor-pref-actual-label');
    const alertaCompat = document.getElementById('cursor-compat-alert');
    /**
     * Marca la card seleccionada y actualiza el texto del label.
     */
    function refrescarUISeleccion(id) {
        var _a;
        // grid ya se validó arriba; tipado estricto no lo recuerda en closures
        const gridEl = document.getElementById('cursor-options-grid');
        if (!gridEl) {
            return;
        }
        gridEl.querySelectorAll('.cursor-option-card').forEach((card) => {
            const esSel = card.dataset['cursorId'] === id;
            card.classList.toggle('is-selected', esSel);
            card.setAttribute('aria-selected', esSel ? 'true' : 'false');
        });
        if (labelActual) {
            labelActual.textContent = (_a = CURSOR_NOMBRES[id]) !== null && _a !== void 0 ? _a : id;
        }
    }
    // Inyectar previews SVG en las cards (desde el catálogo de SigmaCursor)
    if (api) {
        grid.querySelectorAll('[data-preview-for]').forEach((preview) => {
            const id = preview.dataset['previewFor'];
            if (!id || id === 'system') {
                return;
            }
            const svg = api.obtenerSvgPreview(id);
            if (svg) {
                preview.innerHTML = svg;
            }
        });
    }
    // Aviso si el dispositivo no soporta custom (táctil / ≤1024)
    if (alertaCompat && api && !api.esDispositivoCompatible()) {
        alertaCompat.hidden = false;
    }
    // Estado inicial según localStorage
    const preferidoInicial = api ? api.getPreferido() : 'tech';
    refrescarUISeleccion(preferidoInicial);
    // Clic en cada opción
    grid.querySelectorAll('.cursor-option-card').forEach((card) => {
        card.addEventListener('click', () => {
            const id = card.dataset['cursorId'];
            if (!id) {
                return;
            }
            // EXPLICACIÓN: aplicar() guarda en localStorage y cambia el SVG global
            if (api) {
                api.aplicar(id);
            }
            else {
                try {
                    localStorage.setItem('sigma-cursor', id);
                }
                catch {
                    /* ignore */
                }
            }
            refrescarUISeleccion(id);
        });
    });
    // Al abrir el modal, sincronizar (p. ej. cambio en otra pestaña)
    modal.addEventListener('show.bs.modal', () => {
        const actual = api ? api.getPreferido() : preferidoInicial;
        refrescarUISeleccion(actual);
        if (alertaCompat && api) {
            alertaCompat.hidden = api.esDispositivoCompatible();
        }
    });
}
// ── Inicialización ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.review-carousel-wrapper')
        .forEach((wrapper) => new ReviewCarousel(wrapper));
    inicializarSelectorCursorPerfil();
});
//# sourceMappingURL=mi_perfil.js.map