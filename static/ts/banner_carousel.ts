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

interface BannerSlotState {
  slot: HTMLElement;
  slides: HTMLElement[];
  dots: HTMLElement[];
  total: number;
  current: number;
  timer: ReturnType<typeof setInterval> | null;
  interval: number;
}

(function (): void {

  // Tiempo entre rotaciones: 5 segundos
  const ROTATION_INTERVAL = 5000;

  /**
   * Inicializa el carrusel de un slot específico.
   * Solo actúa si hay más de 1 slide en el slot.
   */
  function initSlot(slot: HTMLElement): BannerSlotState | null {
    const slides = Array.from(
      slot.querySelectorAll<HTMLElement>('.st-banner-slide')
    );
    const dots = Array.from(
      slot.querySelectorAll<HTMLElement>('.st-banner-dot')
    );

    if (slides.length <= 1) {
      // Un solo banner: no se necesita carrusel
      return null;
    }

    const state: BannerSlotState = {
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

      dot.addEventListener('keydown', (e: KeyboardEvent) => {
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
  function goToSlide(state: BannerSlotState, index: number): void {
    // Ocultar slide actual
    state.slides[state.current].classList.remove('st-banner-slide--active');
    state.dots[state.current]?.classList.remove('st-banner-dot--active');

    // Activar nuevo slide
    state.current = (index + state.total) % state.total;
    state.slides[state.current].classList.add('st-banner-slide--active');
    state.dots[state.current]?.classList.add('st-banner-dot--active');
  }

  /**
   * Avanza al siguiente slide.
   */
  function nextSlide(state: BannerSlotState): void {
    goToSlide(state, state.current + 1);
  }

  /**
   * Inicia el temporizador de rotación automática.
   */
  function startTimer(state: BannerSlotState): void {
    if (state.timer !== null) return; // Ya corriendo
    state.timer = setInterval(() => {
      nextSlide(state);
    }, state.interval);
  }

  /**
   * Pausa el temporizador (hover/focus).
   */
  function pauseTimer(state: BannerSlotState): void {
    if (state.timer !== null) {
      clearInterval(state.timer);
      state.timer = null;
    }
  }

  /**
   * Reinicia el temporizador (después de interacción manual).
   */
  function resetTimer(state: BannerSlotState): void {
    pauseTimer(state);
    startTimer(state);
  }

  /**
   * Inicializa todos los slots de banners en la página.
   */
  function initAll(): void {
    // Seleccionar todos los slots que tienen más de 1 banner
    const slots = document.querySelectorAll<HTMLElement>(
      '.st-banner-slot[data-banners]'
    );

    slots.forEach((slot) => {
      const bannerCount = parseInt(slot.getAttribute('data-banners') ?? '1', 10);
      if (bannerCount > 1) {
        initSlot(slot);
      }
    });
  }

  // Esperar a que el DOM esté listo
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }

})();
