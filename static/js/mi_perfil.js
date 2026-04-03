"use strict";
/**
 * mi_perfil.ts
 * Lógica del carrusel de opiniones de clientes en "Mi Perfil" y "Directorio".
 *
 * Qué hace:
 * - Busca todos los wrappers con clase `.review-carousel-wrapper`
 * - Para cada uno, instancia `ReviewCarousel`
 * - ReviewCarousel dibuja estrellas, puntos de navegación y gestiona el scroll
 */
// ── Clase principal del carrusel ───────────────────────────────────────────
class ReviewCarousel {
    constructor(wrapper) {
        this.current = 0;
        this.autoTimer = null;
        this.AUTO_INTERVAL_MS = 4500;
        // Coordenadas para swipe táctil
        this.touchStartX = 0;
        this.touchStartY = 0;
        this.wrapper = wrapper;
        const track = wrapper.querySelector('.review-track');
        const dotsBar = wrapper.querySelector('.review-dots-bar');
        const prevBtn = wrapper.querySelector('.review-prev');
        const nextBtn = wrapper.querySelector('.review-next');
        if (!track || !dotsBar || !prevBtn || !nextBtn)
            return;
        this.track = track;
        this.dotsBar = dotsBar;
        this.prevBtn = prevBtn;
        this.nextBtn = nextBtn;
        // Leer slides del DOM
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
        this._renderStars();
        this._buildDots();
        this._updateView();
        // Botones de navegación (mínimo 44×44 px asegurado en CSS)
        prevBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this._goTo(this._prevIndex());
            this._resetAuto();
        });
        nextBtn.addEventListener('click', (e) => {
            e.preventDefault();
            this._goTo(this._nextIndex());
            this._resetAuto();
        });
        // Ocultar flechas cuando hay un solo slide
        if (this.slides.length <= 1) {
            prevBtn.style.display = 'none';
            nextBtn.style.display = 'none';
        }
        // Auto-scroll
        this._startAuto();
        // Pausa en hover (desktop)
        this.wrapper.addEventListener('mouseenter', () => this._stopAuto());
        this.wrapper.addEventListener('mouseleave', () => this._startAuto());
        // Pausa en focus (accesibilidad)
        this.wrapper.addEventListener('focusin', () => this._stopAuto());
        this.wrapper.addEventListener('focusout', () => this._startAuto());
        // Swipe táctil (mobile)
        this.wrapper.addEventListener('touchstart', (e) => {
            this.touchStartX = e.touches[0].clientX;
            this.touchStartY = e.touches[0].clientY;
        }, { passive: true });
        this.wrapper.addEventListener('touchend', (e) => {
            const dx = e.changedTouches[0].clientX - this.touchStartX;
            const dy = e.changedTouches[0].clientY - this.touchStartY;
            // Solo procesar si el gesto es más horizontal que vertical
            if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 40) {
                if (dx < 0) {
                    this._goTo(this._nextIndex());
                }
                else {
                    this._goTo(this._prevIndex());
                }
                this._resetAuto();
            }
        }, { passive: true });
    }
    // ── Dibujar estrellas en cada slide ───────────────────────────────────
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
    // ── Navegar a un slide específico ─────────────────────────────────────
    _goTo(index) {
        this.current = index;
        this._updateView();
    }
    // ── Actualizar posición del track y estado activo ────────────────────
    _updateView() {
        // Mover track con transform para transición suave
        this.track.style.transform = `translateX(-${this.current * 100}%)`;
        // Actualizar dots
        const dots = this.dotsBar.querySelectorAll('.review-dot');
        dots.forEach((dot, idx) => {
            dot.classList.toggle('active', idx === this.current);
            dot.setAttribute('aria-pressed', String(idx === this.current));
        });
        // Accesibilidad: marcar slide activo
        this.slides.forEach(({ element }, idx) => {
            element.setAttribute('aria-hidden', String(idx !== this.current));
        });
    }
    // ── Índices de navegación cíclica ─────────────────────────────────────
    _nextIndex() {
        return (this.current + 1) % this.slides.length;
    }
    _prevIndex() {
        return (this.current - 1 + this.slides.length) % this.slides.length;
    }
    // ── Control del auto-scroll ───────────────────────────────────────────
    _startAuto() {
        if (this.slides.length <= 1)
            return;
        this._stopAuto();
        this.autoTimer = setInterval(() => {
            this._goTo(this._nextIndex());
        }, this.AUTO_INTERVAL_MS);
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
// ── Inicialización global ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    const wrappers = document.querySelectorAll('.review-carousel-wrapper');
    wrappers.forEach((wrapper) => new ReviewCarousel(wrapper));
});
//# sourceMappingURL=mi_perfil.js.map