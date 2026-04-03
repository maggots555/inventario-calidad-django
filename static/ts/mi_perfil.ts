/**
 * mi_perfil.ts
 * Carrusel de opiniones de clientes en "Mi Perfil" y "Directorio".
 *
 * Enfoque: translateX en PÍXELES (no %) para evitar el bug de porcentaje
 * relativo al track en lugar de al wrapper.
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
    private prevBtn!: HTMLButtonElement;
    private nextBtn!: HTMLButtonElement;

    private current: number = 0;
    private autoTimer: ReturnType<typeof setInterval> | null = null;
    private readonly AUTO_INTERVAL_MS = 4500;

    private touchStartX: number = 0;
    private touchStartY: number = 0;

    constructor(wrapper: HTMLElement) {
        this.wrapper = wrapper;

        const track   = wrapper.querySelector<HTMLElement>('.review-track');
        const dotsBar = wrapper.querySelector<HTMLElement>('.review-dots-bar');
        const prevBtn = wrapper.querySelector<HTMLButtonElement>('.review-prev');
        const nextBtn = wrapper.querySelector<HTMLButtonElement>('.review-next');

        if (!track || !dotsBar || !prevBtn || !nextBtn) return;

        this.track   = track;
        this.dotsBar = dotsBar;
        this.prevBtn = prevBtn;
        this.nextBtn = nextBtn;

        this.slides = Array.from(
            track.querySelectorAll<HTMLElement>('.review-slide')
        ).map((el) => ({
            element:    el,
            rating:     parseInt(el.dataset['rating'] ?? '0', 10),
            recomienda: el.dataset['recomienda'] ?? '',
        }));

        if (this.slides.length === 0) return;

        this._renderStars();
        this._buildDots();
        this._updateView();

        // Flechas
        prevBtn.addEventListener('click', (e: Event) => {
            e.preventDefault();
            this._goTo(this._prevIndex());
            this._resetAuto();
        });
        nextBtn.addEventListener('click', (e: Event) => {
            e.preventDefault();
            this._goTo(this._nextIndex());
            this._resetAuto();
        });

        // Ocultar flechas si solo hay un slide
        if (this.slides.length <= 1) {
            prevBtn.style.display = 'none';
            nextBtn.style.display = 'none';
        }

        // Recalcular offsets en px si la ventana cambia de tamaño
        window.addEventListener('resize', () => this._updateView());

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

// ── Inicialización ────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll<HTMLElement>('.review-carousel-wrapper')
        .forEach((wrapper) => new ReviewCarousel(wrapper));
});

