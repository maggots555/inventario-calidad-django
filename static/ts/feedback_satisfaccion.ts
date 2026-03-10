/**
 * feedback_satisfaccion.ts
 * Lógica interactiva de la encuesta de satisfacción del cliente.
 * Maneja estrellas, NPS, pulgares, progreso y confetti.
 */

// ─── Interfaces ──────────────────────────────────────────────────────────────

interface StarGroup {
  container: HTMLElement;
  stars: NodeListOf<HTMLElement>;
  hiddenInput: HTMLInputElement;
  label?: HTMLElement;
  value: number;
}

interface ConfettiConfig {
  count: number;
  colors: string[];
}

// ─── Etiquetas de estrellas ───────────────────────────────────────────────────

const STAR_LABELS: Record<number, string> = {
  1: 'Muy malo 😞',
  2: 'Malo 😕',
  3: 'Regular 😐',
  4: 'Bueno 🙂',
  5: '¡Excelente! 🤩',
};

// ─── Utilidades DOM ───────────────────────────────────────────────────────────

function getEl<T extends HTMLElement>(id: string): T | null {
  return document.getElementById(id) as T | null;
}

function showError(id: string): void {
  const el = document.getElementById(id);
  if (el) el.classList.add('visible');
}

function hideError(id: string): void {
  const el = document.getElementById(id);
  if (el) el.classList.remove('visible');
}

// ─── Sistema de calificación con estrellas ────────────────────────────────────

function initStarGroup(
  containerId: string,
  inputId: string,
  labelId?: string,
): StarGroup | null {
  const container = getEl<HTMLElement>(containerId);
  const hiddenInput = getEl<HTMLInputElement>(inputId);
  if (!container || !hiddenInput) return null;

  const stars = container.querySelectorAll<HTMLElement>('.fs-star');
  const label = labelId ? (getEl<HTMLElement>(labelId) ?? undefined) : undefined;

  const group: StarGroup = { container, stars, hiddenInput, label, value: 0 };

  stars.forEach((star) => {
    const val = parseInt(star.dataset['value'] ?? '0', 10);

    // Hover
    star.addEventListener('mouseenter', () => {
      highlightStars(stars, val);
      if (label) label.textContent = STAR_LABELS[val] ?? '';
    });

    star.addEventListener('mouseleave', () => {
      highlightStars(stars, group.value);
      if (label) label.textContent = group.value > 0 ? (STAR_LABELS[group.value] ?? '') : 'Toca para calificar';
    });

    // Click
    star.addEventListener('click', () => {
      group.value = val;
      hiddenInput.value = String(val);
      highlightStars(stars, val);
      if (label) label.textContent = STAR_LABELS[val] ?? '';
      updateProgress();
    });
  });

  return group;
}

function highlightStars(stars: NodeListOf<HTMLElement>, upTo: number): void {
  stars.forEach((star) => {
    const val = parseInt(star.dataset['value'] ?? '0', 10);
    star.classList.toggle('active', val <= upTo);
  });
}

// ─── Sistema de mini-estrellas (calificaciones opcionales) ───────────────────

function initMiniStarGroup(groupName: string, inputId: string): void {
  const container = document.querySelector<HTMLElement>(`[id="${groupName}Stars"]`);
  const hiddenInput = getEl<HTMLInputElement>(inputId);
  if (!container || !hiddenInput) return;

  const stars = container.querySelectorAll<HTMLElement>('.fs-mini-star');
  let currentValue = 0;

  stars.forEach((star) => {
    const val = parseInt(star.dataset['value'] ?? '0', 10);

    star.addEventListener('mouseenter', () => highlightMiniStars(stars, val));
    star.addEventListener('mouseleave', () => highlightMiniStars(stars, currentValue));

    star.addEventListener('click', () => {
      currentValue = val;
      hiddenInput.value = String(val);
      highlightMiniStars(stars, val);
    });
  });
}

function highlightMiniStars(stars: NodeListOf<HTMLElement>, upTo: number): void {
  stars.forEach((star) => {
    const val = parseInt(star.dataset['value'] ?? '0', 10);
    star.classList.toggle('active', val <= upTo);
  });
}

// ─── NPS Scale ───────────────────────────────────────────────────────────────

function initNPS(): void {
  const grid      = getEl<HTMLElement>('npsGrid');
  const npsInput  = getEl<HTMLInputElement>('id_nps');
  if (!grid || !npsInput) return;

  const buttons = grid.querySelectorAll<HTMLButtonElement>('.fs-nps-btn');

  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const val = btn.dataset['value'] ?? '';
      npsInput.value = val;

      buttons.forEach((b) => b.classList.remove('active'));
      btn.classList.add('active');

      hideError('errorNps');
      updateProgress();
    });
  });
}

// ─── Thumb Buttons (Recomienda) ───────────────────────────────────────────────

function initThumbs(): void {
  const thumbYes      = getEl<HTMLButtonElement>('thumbYes');
  const thumbNo       = getEl<HTMLButtonElement>('thumbNo');
  const recomiendaIn  = getEl<HTMLInputElement>('id_recomienda');
  if (!thumbYes || !thumbNo || !recomiendaIn) return;

  thumbYes.addEventListener('click', () => {
    recomiendaIn.value = 'true';
    thumbYes.classList.add('active-yes');
    thumbNo.classList.remove('active-no');
    hideError('errorRecomienda');
    updateProgress();
  });

  thumbNo.addEventListener('click', () => {
    recomiendaIn.value = 'false';
    thumbNo.classList.add('active-no');
    thumbYes.classList.remove('active-yes');
    hideError('errorRecomienda');
    updateProgress();
  });
}

// ─── Toggle sección opcional ─────────────────────────────────────────────────

function initOptionalToggle(): void {
  const toggle  = getEl<HTMLElement>('optionalToggle');
  const content = getEl<HTMLElement>('optionalContent');
  const wrapper = getEl<HTMLElement>('optionalWrapper');
  if (!toggle || !content || !wrapper) return;

  function doToggle(): void {
    const isOpen = content!.classList.toggle('open');
    wrapper!.classList.toggle('open', isOpen);
    toggle!.setAttribute('aria-expanded', String(isOpen));
  }

  toggle.addEventListener('click', doToggle);
  toggle.addEventListener('keydown', (e: KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); doToggle(); }
  });
}

// ─── Contador de caracteres para textarea ────────────────────────────────────

function initCharCounter(): void {
  const textarea  = document.getElementById('id_comentario_satisfaccion') as HTMLTextAreaElement | null;
  const counter   = getEl<HTMLElement>('charCount');
  if (!textarea || !counter) return;

  textarea.addEventListener('input', () => {
    counter.textContent = String(textarea.value.length);
  });
}

// ─── Barra de progreso ────────────────────────────────────────────────────────

function updateProgress(): void {
  const fill         = getEl<HTMLElement>('progressFill');
  const generalInput = getEl<HTMLInputElement>('id_calificacion_general');
  const npsInput     = getEl<HTMLInputElement>('id_nps');
  const recomiendaIn = getEl<HTMLInputElement>('id_recomienda');
  if (!fill) return;

  let filled = 0;
  if (generalInput && generalInput.value)  filled++;
  if (npsInput     && npsInput.value !== '') filled++;
  if (recomiendaIn && recomiendaIn.value)  filled++;

  const pct = Math.round((filled / 3) * 100);
  fill.style.width = `${pct}%`;
}

// ─── Validación frontend ──────────────────────────────────────────────────────

function validateForm(): boolean {
  let valid = true;

  const generalInput = getEl<HTMLInputElement>('id_calificacion_general');
  if (!generalInput?.value) {
    showError('errorGeneral');
    document.getElementById('section-estrellas')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    valid = false;
  } else {
    hideError('errorGeneral');
  }

  const npsInput = getEl<HTMLInputElement>('id_nps');
  if (!npsInput?.value && npsInput?.value !== '0') {
    if (valid) document.getElementById('section-nps')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    showError('errorNps');
    valid = false;
  } else {
    hideError('errorNps');
  }

  const recomiendaIn = getEl<HTMLInputElement>('id_recomienda');
  if (!recomiendaIn?.value) {
    if (valid) document.getElementById('section-recomienda')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
    showError('errorRecomienda');
    valid = false;
  } else {
    hideError('errorRecomienda');
  }

  return valid;
}

// ─── Confetti 🎉 ─────────────────────────────────────────────────────────────

function launchConfetti(config: ConfettiConfig): void {
  const wrapper = getEl<HTMLElement>('confettiWrapper');
  if (!wrapper) return;

  for (let i = 0; i < config.count; i++) {
    const piece = document.createElement('div');
    piece.className = 'fs-confetti-piece';
    piece.style.left     = `${Math.random() * 100}%`;
    piece.style.animationDuration  = `${1.5 + Math.random() * 2.5}s`;
    piece.style.animationDelay     = `${Math.random() * 0.8}s`;
    piece.style.backgroundColor    = config.colors[Math.floor(Math.random() * config.colors.length)] ?? '#667eea';
    piece.style.transform = `rotate(${Math.random() * 360}deg)`;
    if (Math.random() > 0.5) {
      piece.style.borderRadius = '50%';
      piece.style.width  = `${6 + Math.random() * 8}px`;
      piece.style.height = piece.style.width;
    }
    wrapper.appendChild(piece);
  }
}

// ─── Inicialización ───────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {

  // Estado "formulario"
  const form = document.getElementById('feedbackForm') as HTMLFormElement | null;

  if (form) {
    // Estrellas generales
    initStarGroup('generalStars', 'id_calificacion_general', 'generalStarLabel');

    // Mini-estrellas opcionales
    initMiniStarGroup('atencion', 'id_calificacion_atencion');
    initMiniStarGroup('tiempo',   'id_calificacion_tiempo');

    // NPS, pulgares, toggle opcional, contador
    initNPS();
    initThumbs();
    initOptionalToggle();
    initCharCounter();

    // Validar al submit
    form.addEventListener('submit', (e: Event) => {
      if (!validateForm()) {
        e.preventDefault();
        return;
      }
      // Deshabilitar botón para evitar doble-submit
      const btn = getEl<HTMLButtonElement>('submitBtn');
      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Enviando… ⏳';
      }
    });

    // Inicializar barra de progreso
    updateProgress();
  }

  // Estado "gracias" — lanzar confetti
  const confettiWrapper = getEl<HTMLElement>('confettiWrapper');
  if (confettiWrapper) {
    launchConfetti({
      count: 80,
      colors: ['#667eea', '#764ba2', '#fbbf24', '#10b981', '#f093fb', '#ef4444'],
    });
  }
});
