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

// ── Interfaz que describe cada slide del carrusel ──────────────────────────
interface ReviewSlide {
    element: HTMLElement;
    rating: number;       // 0-5
    recomienda: string;   // '1', '0', o '' (sin respuesta)
}

// ── Clase principal del carrusel ───────────────────────────────────────────
class ReviewCarousel {
    private wrapper: HTMLElement;
    private track!: HTMLElement;
    private slides!: ReviewSlide[];
    private dotsBar!: HTMLElement;

    private current: number = 0;
    private autoTimer: ReturnType<typeof setInterval> | null = null;
    private readonly AUTO_INTERVAL_MS = 4500;

    private touchStartX: number = 0;
    private touchStartY: number = 0;

    constructor(wrapper: HTMLElement) {
        this.wrapper = wrapper;

        const track   = wrapper.querySelector<HTMLElement>('.review-track');
        const dotsBar = wrapper.querySelector<HTMLElement>('.review-dots-bar');

        if (!track || !dotsBar) return;

        this.track   = track;
        this.dotsBar = dotsBar;

        this.slides = Array.from(
            track.querySelectorAll<HTMLElement>('.review-slide')
        ).map((el) => ({
            element:    el,
            rating:     parseInt(el.dataset['rating'] ?? '0', 10),
            recomienda: el.dataset['recomienda'] ?? '',
        }));

        if (this.slides.length === 0) return;

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
        this.wrapper.addEventListener('focusin',    () => this._stopAuto());
        this.wrapper.addEventListener('focusout',   () => this._startAuto());

        // Swipe táctil
        this.wrapper.addEventListener('touchstart', (e: TouchEvent) => {
            this.touchStartX = e.touches[0].clientX;
            this.touchStartY = e.touches[0].clientY;
        }, { passive: true });

        this.wrapper.addEventListener('touchend', (e: TouchEvent) => {
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
    private _setSlideDimensions(): void {
        const w = this.wrapper.offsetWidth;
        this.slides.forEach(({ element }) => {
            element.style.width = `${w}px`;
        });
    }

    // ── Dibujar estrellas ──────────────────────────────────────────────────
    private _renderStars(): void {
        this.slides.forEach(({ element, rating }) => {
            const container = element.querySelector<HTMLElement>('.review-stars-display');
            if (!container) return;
            container.innerHTML = '';
            for (let i = 1; i <= 5; i++) {
                const star = document.createElement('span');
                star.textContent = '★';
                star.className   = i <= rating ? 'rs-star rs-filled' : 'rs-star rs-empty';
                star.setAttribute('aria-hidden', 'true');
                container.appendChild(star);
            }
        });
    }

    // ── Construir puntos de navegación ────────────────────────────────────
    private _buildDots(): void {
        this.dotsBar.innerHTML = '';
        if (this.slides.length <= 1) return;

        this.slides.forEach((_, idx) => {
            const dot = document.createElement('button');
            dot.className = 'review-dot';
            dot.type      = 'button';
            dot.setAttribute('aria-label', `Ir a opinión ${idx + 1}`);
            dot.addEventListener('click', (e: Event) => {
                e.preventDefault();
                this._goTo(idx);
                this._resetAuto();
            });
            this.dotsBar.appendChild(dot);
        });
    }

    // ── Navegar a slide ───────────────────────────────────────────────────
    private _goTo(index: number): void {
        this.current = index;
        this._updateView();
    }

    // ── Actualizar posición usando PÍXELES (no %) ─────────────────────────
    // EXPLICACIÓN: translateX(%) usa % del elemento mismo (el track),
    // que mide N veces el wrapper si hay N slides. Por eso usamos px.
    private _updateView(): void {
        const slideWidth = this.wrapper.offsetWidth;
        this.track.style.transform = `translateX(-${this.current * slideWidth}px)`;

        // Actualizar dots
        const dots = this.dotsBar.querySelectorAll<HTMLButtonElement>('.review-dot');
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
    private _nextIndex(): number {
        return (this.current + 1) % this.slides.length;
    }
    private _prevIndex(): number {
        return (this.current - 1 + this.slides.length) % this.slides.length;
    }

    // ── Auto-scroll ───────────────────────────────────────────────────────
    private _startAuto(): void {
        if (this.slides.length <= 1) return;
        this._stopAuto();
        this.autoTimer = setInterval(() => this._goTo(this._nextIndex()), this.AUTO_INTERVAL_MS);
    }
    private _stopAuto(): void {
        if (this.autoTimer !== null) {
            clearInterval(this.autoTimer);
            this.autoTimer = null;
        }
    }
    private _resetAuto(): void {
        this._stopAuto();
        this._startAuto();
    }
}

/**
 * Nombres legibles para el label “Preferencia actual”.
 * CursorId es el type global definido en cursor_personalizado.ts.
 */
const CURSOR_NOMBRES: Record<CursorId, string> = {
    tech: 'Tech Cyan',
    classic: 'Classic Gold',
    minimal: 'Minimal',
    banana: 'Banana',
    hongo: 'Hongo Mario',
    metallica: 'Metallica M',
    ganso: 'Ganso',
    mariposa: 'Mariposa',
    system: 'Sistema',
};

/**
 * Inicializa el modal de personalizar cursor en Mi Perfil.
 *
 * Objetivo: al elegir una card, guardar + aplicar vía window.SigmaCursor.
 * Efectos: localStorage (dentro de SigmaCursor.aplicar) y UI selected/label.
 */
function inicializarSelectorCursorPerfil(): void {
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
    function refrescarUISeleccion(id: CursorId): void {
        // grid ya se validó arriba; tipado estricto no lo recuerda en closures
        const gridEl = document.getElementById('cursor-options-grid');
        if (!gridEl) {
            return;
        }
        gridEl.querySelectorAll<HTMLElement>('.cursor-option-card').forEach((card) => {
            const esSel = card.dataset['cursorId'] === id;
            card.classList.toggle('is-selected', esSel);
            card.setAttribute('aria-selected', esSel ? 'true' : 'false');
        });
        if (labelActual) {
            labelActual.textContent = CURSOR_NOMBRES[id] ?? id;
        }
    }

    // Inyectar previews SVG en las cards (desde el catálogo de SigmaCursor)
    if (api) {
        grid.querySelectorAll<HTMLElement>('[data-preview-for]').forEach((preview) => {
            const id = preview.dataset['previewFor'] as CursorId | undefined;
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
    const preferidoInicial: CursorId = api ? api.getPreferido() : 'tech';
    refrescarUISeleccion(preferidoInicial);

    // Clic en cada opción
    grid.querySelectorAll<HTMLButtonElement>('.cursor-option-card').forEach((card) => {
        card.addEventListener('click', () => {
            const id = card.dataset['cursorId'] as CursorId | undefined;
            if (!id) {
                return;
            }

            // EXPLICACIÓN: aplicar() guarda en localStorage y cambia el SVG global
            if (api) {
                api.aplicar(id);
            } else {
                try {
                    localStorage.setItem('sigma-cursor', id);
                } catch {
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
    document.querySelectorAll<HTMLElement>('.review-carousel-wrapper')
        .forEach((wrapper) => new ReviewCarousel(wrapper));

    inicializarSelectorCursorPerfil();
});

