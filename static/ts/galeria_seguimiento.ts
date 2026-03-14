/**
 * GALERÍA DE IMÁGENES — SEGUIMIENTO PÚBLICO DE ORDEN
 * ====================================================
 *
 * Carrusel tipo "riel" para la página pública que ve el cliente.
 * Incluye:
 *  - Auto-avance cada 3.5 segundos
 *  - Pausa al pasar el mouse o al tocar (móvil)
 *  - Deslizamiento con gestos táctiles (swipe)
 *  - IntersectionObserver: se detiene si el carrusel no está visible
 *  - Click/tap abre un lightbox a pantalla completa
 *  - Navegación con teclado (← → Escape)
 *  - Swipe en el lightbox para cambiar imagen
 *
 * COMPILACIÓN:
 *   npm run build
 *   Genera: static/js/galeria_seguimiento.js
 *
 * @version 1.0.0
 * @date Marzo 2026
 */

/** Datos de cada imagen de la galería (leídos desde data-* attributes del HTML) */
interface ImagenGaleria {
    src: string;
    tipo: string;
    tipoLabel: string;
    descripcion: string;
}

/** Clase principal del carrusel */
class GaleriaRiel {
    private readonly container: HTMLElement;
    private readonly rail!: HTMLElement;
    private readonly items!: HTMLElement[];
    private readonly imagenes!: ImagenGaleria[];

    private currentIndex: number = 0;
    private timer: ReturnType<typeof setInterval> | null = null;
    private readonly INTERVAL_MS: number = 3500;
    private isPaused: boolean = false;

    // Touch tracking (carrusel)
    private touchStartX: number = 0;
    private touchStartY: number = 0;

    // Lightbox
    private lightbox: HTMLElement | null = null;
    private lbImg: HTMLImageElement | null = null;
    private lbTipo: HTMLElement | null = null;
    private lbDesc: HTMLElement | null = null;
    private lbCounter: HTMLElement | null = null;
    private lightboxIndex: number = 0;
    private lbTouchStartX: number = 0;

    constructor(container: HTMLElement) {
        this.container = container;

        const rail = container.querySelector<HTMLElement>('.st-galeria-rail');
        if (!rail) return;
        this.rail = rail;

        this.items = Array.from(
            container.querySelectorAll<HTMLElement>('.st-galeria-item')
        );

        if (this.items.length === 0) return;

        // Leer datos de los data-attributes de cada item
        this.imagenes = this.items.map((el) => ({
            src: el.dataset['src'] ?? '',
            tipo: el.dataset['tipo'] ?? '',
            tipoLabel: el.dataset['tipoLabel'] ?? '',
            descripcion: el.dataset['descripcion'] ?? '',
        }));

        this.buildDots();
        this.bindNavButtons();
        this.bindCarouselTouch();
        this.bindHoverPause();
        this.bindItemClicks();
        this.initLightbox();
        this.initIntersectionObserver();

        // Estado inicial
        this.goTo(0, false);
        this.startAutoAdvance();
    }

    // ─────────────────────────────────────────────────
    // DOTS INDICADORES
    // ─────────────────────────────────────────────────

    private buildDots(): void {
        const dotsContainer = this.container.querySelector<HTMLElement>('.st-galeria-dots');
        if (!dotsContainer) return;

        this.imagenes.forEach((_, i) => {
            const dot = document.createElement('button');
            dot.className = 'st-galeria-dot';
            dot.type = 'button';
            dot.setAttribute('role', 'tab');
            dot.setAttribute('aria-label', `Imagen ${i + 1}`);

            dot.addEventListener('click', () => {
                this.goTo(i);
                this.resetTimer();
            });

            dotsContainer.appendChild(dot);
        });
    }

    private updateDots(): void {
        const dots = this.container.querySelectorAll<HTMLElement>('.st-galeria-dot');
        dots.forEach((dot, i) => {
            const active = i === this.currentIndex;
            dot.classList.toggle('st-galeria-dot--active', active);
            dot.setAttribute('aria-selected', String(active));
        });
    }

    // ─────────────────────────────────────────────────
    // BOTONES ANTERIOR / SIGUIENTE
    // ─────────────────────────────────────────────────

    private bindNavButtons(): void {
        const prev = this.container.querySelector<HTMLButtonElement>('.st-galeria-prev');
        const next = this.container.querySelector<HTMLButtonElement>('.st-galeria-next');

        prev?.addEventListener('click', () => {
            this.advance(-1);
            this.resetTimer();
        });

        next?.addEventListener('click', () => {
            this.advance(1);
            this.resetTimer();
        });
    }

    // ─────────────────────────────────────────────────
    // GESTOS TÁCTILES (CARRUSEL)
    // ─────────────────────────────────────────────────

    private bindCarouselTouch(): void {
        this.rail.addEventListener('touchstart', (e: TouchEvent) => {
            this.touchStartX = e.touches[0].clientX;
            this.touchStartY = e.touches[0].clientY;
            this.isPaused = true;
        }, { passive: true });

        this.rail.addEventListener('touchend', (e: TouchEvent) => {
            const dx = e.changedTouches[0].clientX - this.touchStartX;
            const dy = Math.abs(e.changedTouches[0].clientY - this.touchStartY);

            // Solo swipe horizontal significativo (> 40px) que no sea scroll vertical
            if (Math.abs(dx) > 40 && dy < 60) {
                this.advance(dx < 0 ? 1 : -1);
                this.resetTimer();
            }
            this.isPaused = false;
        }, { passive: true });
    }

    // ─────────────────────────────────────────────────
    // PAUSA EN HOVER (escritorio)
    // ─────────────────────────────────────────────────

    private bindHoverPause(): void {
        this.container.addEventListener('mouseenter', () => { this.isPaused = true; });
        this.container.addEventListener('mouseleave', () => { this.isPaused = false; });
    }

    // ─────────────────────────────────────────────────
    // CLICK EN ITEM → ABRIR LIGHTBOX
    // ─────────────────────────────────────────────────

    private bindItemClicks(): void {
        this.items.forEach((item, i) => {
            item.addEventListener('click', () => this.openLightbox(i));

            // Soporte de teclado: Enter/Espacio abre el lightbox
            item.addEventListener('keydown', (e: KeyboardEvent) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.openLightbox(i);
                }
            });
        });
    }

    // ─────────────────────────────────────────────────
    // PAUSAR CUANDO NO ESTÁ VISIBLE (IntersectionObserver)
    // ─────────────────────────────────────────────────

    private initIntersectionObserver(): void {
        if (!('IntersectionObserver' in window)) return; // fallback para browsers viejos

        const observer = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    this.startAutoAdvance();
                } else {
                    this.stopAutoAdvance();
                }
            });
        }, { threshold: 0.2 });

        observer.observe(this.container);
    }

    // ─────────────────────────────────────────────────
    // NAVEGACIÓN DEL CARRUSEL
    // ─────────────────────────────────────────────────

    private goTo(index: number, animate: boolean = true): void {
        const count = this.imagenes.length;
        this.currentIndex = ((index % count) + count) % count;

        // Calcular desplazamiento para centrar el item activo
        const item = this.items[this.currentIndex];
        if (!item) return;

        const itemWidth = item.offsetWidth;
        const gap = 10;
        const trackWidth = (this.rail.parentElement?.offsetWidth ?? 0);
        const itemLeft = this.currentIndex * (itemWidth + gap);

        // Centrar el item activo dentro del track visible
        const offset = itemLeft - (trackWidth - itemWidth) / 2;
        const maxOffset = Math.max(0, count * (itemWidth + gap) - trackWidth);
        const clamped = Math.max(0, Math.min(offset, maxOffset));

        if (!animate) {
            this.rail.style.transition = 'none';
            this.rail.style.transform = `translateX(-${clamped}px)`;
            // Forzar reflow para que la transición se reactive correctamente
            void this.rail.offsetWidth;
            this.rail.style.transition = '';
        } else {
            this.rail.style.transform = `translateX(-${clamped}px)`;
        }

        // Actualizar clases activas en items
        this.items.forEach((el, i) => {
            el.classList.toggle('st-galeria-item--active', i === this.currentIndex);
        });

        this.updateDots();
    }

    private advance(direction: 1 | -1): void {
        this.goTo(this.currentIndex + direction);
    }

    // ─────────────────────────────────────────────────
    // AUTO-AVANCE
    // ─────────────────────────────────────────────────

    private startAutoAdvance(): void {
        if (this.timer !== null) return; // ya está corriendo
        if (this.imagenes.length <= 1) return; // una sola imagen no necesita auto-avance

        this.timer = setInterval(() => {
            if (!this.isPaused) this.advance(1);
        }, this.INTERVAL_MS);
    }

    private stopAutoAdvance(): void {
        if (this.timer !== null) {
            clearInterval(this.timer);
            this.timer = null;
        }
    }

    private resetTimer(): void {
        this.stopAutoAdvance();
        this.startAutoAdvance();
    }

    // ─────────────────────────────────────────────────
    // LIGHTBOX
    // ─────────────────────────────────────────────────

    private initLightbox(): void {
        this.lightbox = document.getElementById('st-lightbox');
        if (!this.lightbox) return;

        this.lbImg     = this.lightbox.querySelector<HTMLImageElement>('.st-lb-img');
        this.lbTipo    = this.lightbox.querySelector<HTMLElement>('.st-lb-tipo');
        this.lbDesc    = this.lightbox.querySelector<HTMLElement>('.st-lb-desc');
        this.lbCounter = this.lightbox.querySelector<HTMLElement>('.st-lb-counter');

        // Cerrar al hacer click en el fondo
        this.lightbox.addEventListener('click', (e: MouseEvent) => {
            if (e.target === this.lightbox) this.closeLightbox();
        });

        // Botones de control
        this.lightbox.querySelector('.st-lb-close')
            ?.addEventListener('click', () => this.closeLightbox());

        this.lightbox.querySelector('.st-lb-prev')
            ?.addEventListener('click', () => this.lightboxNavigate(-1));

        this.lightbox.querySelector('.st-lb-next')
            ?.addEventListener('click', () => this.lightboxNavigate(1));

        // Teclado
        document.addEventListener('keydown', (e: KeyboardEvent) => {
            if (!this.lightbox?.classList.contains('st-lb--visible')) return;
            if (e.key === 'Escape')      this.closeLightbox();
            if (e.key === 'ArrowLeft')   this.lightboxNavigate(-1);
            if (e.key === 'ArrowRight')  this.lightboxNavigate(1);
        });

        // Swipe táctil en el lightbox
        this.lightbox.addEventListener('touchstart', (e: TouchEvent) => {
            this.lbTouchStartX = e.touches[0].clientX;
        }, { passive: true });

        this.lightbox.addEventListener('touchend', (e: TouchEvent) => {
            const dx = e.changedTouches[0].clientX - this.lbTouchStartX;
            if (Math.abs(dx) > 50) this.lightboxNavigate(dx < 0 ? 1 : -1);
        }, { passive: true });
    }

    private openLightbox(index: number): void {
        if (!this.lightbox) return;

        this.lightboxIndex = index;
        this.lightboxRender();
        this.lightbox.classList.add('st-lb--visible');
        document.body.style.overflow = 'hidden';
        this.stopAutoAdvance();
    }

    private closeLightbox(): void {
        if (!this.lightbox) return;

        this.lightbox.classList.remove('st-lb--visible');
        document.body.style.overflow = '';
        this.startAutoAdvance();
    }

    private lightboxNavigate(direction: 1 | -1): void {
        const count = this.imagenes.length;
        this.lightboxIndex = ((this.lightboxIndex + direction) % count + count) % count;
        this.lightboxRender();
    }

    private lightboxRender(): void {
        const img = this.imagenes[this.lightboxIndex];
        if (!img) return;

        // Fade-out → cambiar src → fade-in
        if (this.lbImg) {
            this.lbImg.style.opacity = '0';
            const newSrc = img.src;
            this.lbImg.onload = () => {
                if (this.lbImg) this.lbImg.style.opacity = '1';
            };
            this.lbImg.src = newSrc;
            this.lbImg.alt = img.tipoLabel;
        }

        // Badge de tipo (reutiliza clases de chip del carrusel)
        if (this.lbTipo) {
            this.lbTipo.textContent = img.tipoLabel;
            this.lbTipo.className = `st-lb-tipo st-galeria-chip st-galeria-chip--${img.tipo}`;
            // En el lightbox el chip no está posicionado absolute
            this.lbTipo.style.position = 'static';
        }

        if (this.lbDesc) {
            this.lbDesc.textContent = img.descripcion || '';
            this.lbDesc.style.display = img.descripcion ? 'block' : 'none';
        }

        if (this.lbCounter) {
            this.lbCounter.textContent = `${this.lightboxIndex + 1} / ${this.imagenes.length}`;
        }
    }
}

// ─────────────────────────────────────────────────
// INICIALIZACIÓN
// ─────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    const container = document.querySelector<HTMLElement>('.st-galeria');
    if (container) new GaleriaRiel(container);
});
