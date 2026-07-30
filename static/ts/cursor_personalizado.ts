/**
 * cursor_personalizado.ts
 *
 * Objetivo de negocio:
 *   Cursor animado del layout staff (div #tech-cursor) con variantes
 *   elegibles por el usuario desde Mi Perfil. La preferencia se guarda
 *   en localStorage (igual que el tema claro/oscuro), no en la BD.
 *
 * Efectos secundarios:
 *   - Lee/escribe localStorage clave 'sigma-cursor'
 *   - Añade/quita html.custom-cursor-active y data-cursor-variant
 *   - Inyecta SVG en #tech-cursor y crea partículas .cursor-trail
 *   - Expone window.SigmaCursor para el modal de Mi Perfil
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 *   No usamos cursor:url() del navegador. Movemos un SVG con JavaScript.
 *   En táctil/híbrido se desactiva a propósito (evita “sin cursor”).
 *   Este archivo NO usa import/export: el proyecto carga cada .js aparte,
 *   así que compartimos la API con window.SigmaCursor.
 */

/** Clave de localStorage — misma familia que 'theme' del dark mode. */
const CURSOR_STORAGE_KEY = 'sigma-cursor';

/** IDs válidos de variante (incluye apagar el custom). */
type CursorId =
    | 'tech'
    | 'classic'
    | 'minimal'
    | 'banana'
    | 'hongo'
    | 'metallica'
    | 'system';

/**
 * Metadatos públicos de cada opción (sin el SVG completo).
 * El modal de Mi Perfil usa esto para pintar las cards.
 */
interface CursorCatalogoItem {
    id: CursorId;
    nombre: string;
    descripcion: string;
    /** Color de acento para preview / estela (CSS). */
    accent: string;
}

interface CursorVariant extends CursorCatalogoItem {
    /** Markup SVG inline; vacío si id === 'system'. */
    svgMarkup: string;
}

/** Catálogo completo con SVG embebido (evita fetch async y FOUC). */
const CURSOR_VARIANTES: Record<Exclude<CursorId, 'system'>, CursorVariant> = {
    tech: {
        id: 'tech',
        nombre: 'Tech Cyan',
        descripcion: 'Cursor original SIGMA con acento cyan.',
        accent: '#06b6d4',
        svgMarkup: `
<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <filter id="dropShadowTech" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="1"/>
      <feOffset dx="1" dy="1" result="offsetblur"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.5"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <g filter="url(#dropShadowTech)">
    <path d="M2 2 L12 28 L16 18 L26 14 L2 2 Z" fill="#2d3e50" stroke="#06b6d4" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M16 18 L22 24" stroke="#06b6d4" stroke-width="1.5" stroke-linecap="round"/>
    <circle cx="22" cy="24" r="2" fill="#06b6d4"/>
    <circle class="cursor-core-dot" cx="8" cy="10" r="1.5" fill="#06b6d4" opacity="0.8"/>
  </g>
</svg>`.trim(),
    },
    classic: {
        id: 'classic',
        nombre: 'Classic Gold',
        descripcion: 'Misma forma, acento dorado de la marca.',
        accent: '#d4a843',
        svgMarkup: `
<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <filter id="dropShadowClassicRuntime" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="1"/>
      <feOffset dx="1" dy="1" result="offsetblur"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.5"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <g filter="url(#dropShadowClassicRuntime)">
    <path d="M2 2 L12 28 L16 18 L26 14 L2 2 Z" fill="#1e293b" stroke="#d4a843" stroke-width="1.5" stroke-linejoin="round"/>
    <path d="M16 18 L22 24" stroke="#d4a843" stroke-width="1.5" stroke-linecap="round"/>
    <circle cx="22" cy="24" r="2" fill="#d4a843"/>
    <circle class="cursor-core-dot" cx="8" cy="10" r="1.5" fill="#d4a843" opacity="0.85"/>
  </g>
</svg>`.trim(),
    },
    minimal: {
        id: 'minimal',
        nombre: 'Minimal',
        descripcion: 'Flecha limpia, sin detalles tech.',
        accent: '#94a3b8',
        svgMarkup: `
<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <filter id="dropShadowMinimalRuntime" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="0.8"/>
      <feOffset dx="1" dy="1" result="offsetblur"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.4"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <g filter="url(#dropShadowMinimalRuntime)">
    <path d="M3 3 L11 27 L15 17 L25 13 L3 3 Z" fill="#334155" stroke="#94a3b8" stroke-width="1.25" stroke-linejoin="round"/>
    <circle class="cursor-core-dot" cx="8" cy="10" r="1.2" fill="#94a3b8" opacity="0.9"/>
  </g>
</svg>`.trim(),
    },
    banana: {
        id: 'banana',
        nombre: 'Banana',
        descripcion: 'Crescent amarillo con tallo (easter egg).',
        accent: '#f4c430',
        svgMarkup: `
<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <filter id="dropShadowBananaRuntime" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="0.7"/>
      <feOffset dx="1" dy="1" result="offsetblur"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.4"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <g filter="url(#dropShadowBananaRuntime)">
    <path d="M4 3 C10 2 18 8 24 16 C27 20 29 25 30 29 C26 26 22 22 17 17 C12 11 7 6 4 3 Z" fill="#f4c430" stroke="#b8860b" stroke-width="1.15" stroke-linejoin="round"/>
    <path d="M7 6 C12 7 17 12 21 17 C24 21 26 24 28 27 C25 24 22 21 18 17 C14 12 10 8 7 6 Z" fill="#e6b422" opacity="0.55"/>
    <path d="M3 2.2 L5.2 4" stroke="#5c3a1e" stroke-width="2.2" stroke-linecap="round"/>
    <circle cx="29.2" cy="28.5" r="1.35" fill="#5c3a1e"/>
    <path d="M9 6.5 C13 8 17 12 21 17" stroke="#fff6c2" stroke-width="1.6" stroke-linecap="round" opacity="0.75" fill="none"/>
    <circle class="cursor-core-dot" cx="15" cy="13" r="1.25" fill="#fff8dc" opacity="0.95"/>
  </g>
</svg>`.trim(),
    },
    hongo: {
        id: 'hongo',
        nombre: 'Hongo Mario',
        descripcion: 'Super hongo rojo con carita.',
        accent: '#e52521',
        svgMarkup: `
<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <filter id="dropShadowHongoRuntime" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="0.8"/>
      <feOffset dx="1" dy="1" result="offsetblur"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.45"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <g filter="url(#dropShadowHongoRuntime)">
    <ellipse cx="16" cy="12" rx="13" ry="10" fill="#e52521" stroke="#9a1613" stroke-width="1.1"/>
    <ellipse cx="16" cy="16" rx="13" ry="3.2" fill="#c41e1a" stroke="#9a1613" stroke-width="0.8"/>
    <circle cx="9" cy="9" r="2.6" fill="#ffffff"/>
    <circle cx="17" cy="6.5" r="3" fill="#ffffff"/>
    <circle cx="24" cy="10.5" r="2.1" fill="#ffffff"/>
    <path d="M11 16 H21 V25.5 C21 28 18.8 29.5 16 29.5 C13.2 29.5 11 28 11 25.5 Z" fill="#f5d7a1" stroke="#c4a36a" stroke-width="1.1" stroke-linejoin="round"/>
    <ellipse cx="13.5" cy="22" rx="1.15" ry="1.7" fill="#1e293b"/>
    <ellipse cx="18.5" cy="22" rx="1.15" ry="1.7" fill="#1e293b"/>
    <circle cx="13.8" cy="21.4" r="0.35" fill="#ffffff"/>
    <circle cx="18.8" cy="21.4" r="0.35" fill="#ffffff"/>
    <path d="M14 25.2 Q16 26.4 18 25.2" stroke="#1e293b" stroke-width="0.8" stroke-linecap="round" fill="none"/>
    <circle class="cursor-core-dot" cx="16" cy="8" r="1.4" fill="#ffffff" opacity="0.95"/>
  </g>
</svg>`.trim(),
    },
    metallica: {
        id: 'metallica',
        nombre: 'Metallica M',
        descripcion: 'M angular metalica plateada.',
        accent: '#94a3b8',
        svgMarkup: `
<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <filter id="dropShadowMetallicaRuntime" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="0.8"/>
      <feOffset dx="1" dy="1" result="offsetblur"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.5"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <linearGradient id="metalGradMRuntime" x1="2" y1="2" x2="30" y2="30" gradientUnits="userSpaceOnUse">
      <stop stop-color="#f8fafc"/>
      <stop offset="0.45" stop-color="#94a3b8"/>
      <stop offset="1" stop-color="#334155"/>
    </linearGradient>
  </defs>
  <g filter="url(#dropShadowMetallicaRuntime)">
    <path d="M3 2 L3 29 L9 29 L9 14 L16 26 L23 14 L23 29 L29 29 L29 2 L22 2 L22 12 L16 4 L10 12 L10 2 Z" fill="url(#metalGradMRuntime)" stroke="#0f172a" stroke-width="1.15" stroke-linejoin="round"/>
    <path d="M5.5 4.5 L5.5 26.5 M26.5 4.5 L26.5 26.5 M11.5 12 L16 20 L20.5 12" stroke="#e2e8f0" stroke-width="0.7" stroke-linecap="round" opacity="0.45" fill="none"/>
    <circle class="cursor-core-dot" cx="16" cy="10" r="1.25" fill="#ef4444" opacity="0.95"/>
  </g>
</svg>`.trim(),
    },
};

/** Opción “cursor del sistema” (sin SVG custom). */
const CURSOR_SYSTEM_ITEM: CursorCatalogoItem = {
    id: 'system',
    nombre: 'Sistema',
    descripcion: 'Cursor normal del sistema operativo.',
    accent: '#64748b',
};

const CURSOR_IDS_VALIDOS: CursorId[] = [
    'tech',
    'classic',
    'minimal',
    'banana',
    'hongo',
    'metallica',
    'system',
];

/** Evita registrar mousemove/hover dos veces al cambiar de variante. */
let motorCursorListo = false;

/** Variante activa para colorear la estela. */
let varianteTrailActual: Exclude<CursorId, 'system'> = 'tech';

/** Intervalo mínimo entre partículas de estela (ms). */
let lastTrailTime = 0;
const TRAIL_INTERVAL_MS = 30;

/**
 * API pública en window para Mi Perfil y depuración.
 */
interface SigmaCursorApi {
    STORAGE_KEY: string;
    getPreferido: () => CursorId;
    aplicar: (id?: CursorId) => void;
    catalogo: CursorCatalogoItem[];
    esDispositivoCompatible: () => boolean;
    /** SVG inline para previews del modal (vacío si es system). */
    obtenerSvgPreview: (id: CursorId) => string;
}

interface Window {
    SigmaCursor?: SigmaCursorApi;
}

/**
 * Detecta táctil / híbrido / pantallas chicas.
 * Mismo criterio que el cursor original (evita bug “sin cursor”).
 */
function esDispositivoTactilOHibrido(): boolean {
    return (
        'ontouchstart' in window ||
        navigator.maxTouchPoints > 0 ||
        window.matchMedia('(hover: none)').matches ||
        window.matchMedia('(pointer: coarse)').matches ||
        window.innerWidth <= 1024
    );
}

/**
 * Valida y normaliza un id leído de localStorage.
 */
function normalizarCursorId(valor: string | null): CursorId {
    if (valor && (CURSOR_IDS_VALIDOS as string[]).includes(valor)) {
        return valor as CursorId;
    }
    // Default: el tech histórico de SIGMA
    return 'tech';
}

/**
 * Lee la preferencia del usuario. Si no hay nada guardado → 'tech'.
 */
function getCursorPreferido(): CursorId {
    try {
        return normalizarCursorId(localStorage.getItem(CURSOR_STORAGE_KEY));
    } catch {
        // localStorage puede fallar en modo privado estricto
        return 'tech';
    }
}

/**
 * Persiste la elección en este navegador/dispositivo.
 */
function setCursorPreferido(id: CursorId): void {
    try {
        localStorage.setItem(CURSOR_STORAGE_KEY, id);
    } catch {
        console.warn('No se pudo guardar preferencia de cursor en localStorage');
    }
}

/**
 * Lista pública para el modal (sin markup SVG pesado en el listado).
 */
function obtenerCatalogoPublico(): CursorCatalogoItem[] {
    // EXPLICACIÓN: Object.values evita olvidar una variante nueva en el modal
    const variantes: CursorCatalogoItem[] = Object.values(CURSOR_VARIANTES).map((v) => ({
        id: v.id,
        nombre: v.nombre,
        descripcion: v.descripcion,
        accent: v.accent,
    }));
    return [...variantes, CURSOR_SYSTEM_ITEM];
}

/**
 * SVG de preview estático para las cards del modal (misma forma, más chico).
 */
function obtenerSvgPreview(id: CursorId): string {
    if (id === 'system') {
        // Icono tipográfico simple: no hay SVG custom
        return '';
    }
    return CURSOR_VARIANTES[id].svgMarkup;
}

/**
 * Oculta el custom y restaura el cursor del SO.
 */
function desactivarCursorPersonalizado(motivo: string): void {
    // EXPLICACIÓN: sin custom-cursor-active, base.css NO fuerza cursor: none
    document.documentElement.classList.remove('custom-cursor-active');
    document.documentElement.removeAttribute('data-cursor-variant');

    const cursor = document.getElementById('tech-cursor');
    if (cursor) {
        cursor.style.display = 'none';
        cursor.classList.remove('hover-active');
    }

    console.log(`Cursor personalizado deshabilitado (${motivo}) — fallback al cursor del sistema`);
}

/**
 * Crea una partícula de estela en (x, y) con color según la variante.
 */
function crearParticulaTrail(x: number, y: number): void {
    const particle = document.createElement('div');
    // Clase base + modificador por variante (colores en base.css)
    particle.className = `cursor-trail cursor-trail--${varianteTrailActual}`;
    particle.style.left = `${x}px`;
    particle.style.top = `${y}px`;
    document.body.appendChild(particle);

    // Permitir que el navegador pinte el estado inicial antes de animar
    setTimeout(() => {
        particle.style.transform = 'translate(-50%, -50%) scale(0)';
        particle.style.opacity = '0';
    }, 10);

    setTimeout(() => {
        particle.remove();
    }, 510);
}

/**
 * Inyecta el SVG de la variante dentro de #tech-cursor.
 */
function inyectarSvgVariante(cursorEl: HTMLElement, id: Exclude<CursorId, 'system'>): void {
    const variante = CURSOR_VARIANTES[id];
    cursorEl.innerHTML = variante.svgMarkup;
    cursorEl.setAttribute('data-cursor-id', id);
    document.documentElement.setAttribute('data-cursor-variant', id);
    varianteTrailActual = id;
}

/**
 * Engancha mousemove / hover / leave UNA sola vez por carga de página.
 *
 * Args:
 *   cursor — elemento #tech-cursor ya presente en el DOM
 */
function asegurarMotorCursor(cursor: HTMLElement): void {
    if (motorCursorListo) {
        return;
    }
    motorCursorListo = true;

    // EXPLICACIÓN: requestAnimationFrame evita jank al mover el SVG
    document.addEventListener('mousemove', (e: MouseEvent) => {
        // Si el usuario eligió "sistema", el div está oculto; no crear estela
        if (!document.documentElement.classList.contains('custom-cursor-active')) {
            return;
        }

        requestAnimationFrame(() => {
            cursor.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;

            const now = Date.now();
            if (now - lastTrailTime > TRAIL_INTERVAL_MS) {
                crearParticulaTrail(e.clientX, e.clientY);
                lastTrailTime = now;
            }
        });
    });

    const selectoresInteractivos =
        'a, button, input, select, textarea, .btn, .card, .select2-container, .select2-selection, .select2-results__option';

    document.querySelectorAll(selectoresInteractivos).forEach((el) => {
        el.addEventListener('mouseenter', () => {
            cursor.classList.add('hover-active');
        });
        el.addEventListener('mouseleave', () => {
            cursor.classList.remove('hover-active');
        });
    });

    document.addEventListener('mouseleave', () => {
        cursor.style.opacity = '0';
    });
    document.addEventListener('mouseenter', () => {
        cursor.style.opacity = '1';
    });
}

/**
 * Aplica una variante (o relee localStorage si no se pasa id).
 *
 * Efectos:
 *   - Si se pasa id → lo guarda en localStorage
 *   - En táctil → siempre desactiva (pero la preferencia queda guardada)
 *   - system → desactiva custom
 *   - tech/classic/minimal → inyecta SVG y activa
 */
function aplicarCursorPreferido(idOpcional?: CursorId): void {
    // Si el modal manda un id, lo persistimos antes de aplicar
    if (idOpcional !== undefined) {
        setCursorPreferido(idOpcional);
    }

    const preferido = getCursorPreferido();

    // Dispositivos táctiles: nunca custom (preferencia sí se guarda para escritorio)
    if (esDispositivoTactilOHibrido()) {
        desactivarCursorPersonalizado('dispositivo táctil o híbrido');
        return;
    }

    if (preferido === 'system') {
        desactivarCursorPersonalizado('preferencia: cursor del sistema');
        return;
    }

    const cursor = document.getElementById('tech-cursor');
    if (!cursor) {
        desactivarCursorPersonalizado('elemento #tech-cursor no encontrado');
        return;
    }

    // Paso 1: pintar el SVG de la variante elegida
    inyectarSvgVariante(cursor, preferido);

    // Paso 2: avisar al CSS que oculte el cursor del SO
    document.documentElement.classList.add('custom-cursor-active');
    cursor.style.display = '';
    cursor.style.opacity = '1';

    // Paso 3: motor de movimiento (solo la primera vez)
    asegurarMotorCursor(cursor);
}

// Exponer API global ANTES del DOMContentLoaded (por si otro script la consulta)
window.SigmaCursor = {
    STORAGE_KEY: CURSOR_STORAGE_KEY,
    getPreferido: getCursorPreferido,
    aplicar: aplicarCursorPreferido,
    catalogo: obtenerCatalogoPublico(),
    esDispositivoCompatible: () => !esDispositivoTactilOHibrido(),
    obtenerSvgPreview: obtenerSvgPreview,
};

document.addEventListener('DOMContentLoaded', () => {
    aplicarCursorPreferido();
});
