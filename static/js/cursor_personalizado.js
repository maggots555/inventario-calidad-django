"use strict";
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
/** Catálogo completo con SVG embebido (evita fetch async y FOUC). */
const CURSOR_VARIANTES = {
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
    ganso: {
        id: 'ganso',
        nombre: 'Ganso',
        descripcion: 'Ganso blanco con pico naranja (hotspot).',
        accent: '#f97316',
        svgMarkup: `
<svg width="32" height="32" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <defs>
    <filter id="dropShadowGansoRuntime" x="-50%" y="-50%" width="200%" height="200%">
      <feGaussianBlur in="SourceAlpha" stdDeviation="0.7"/>
      <feOffset dx="1" dy="1" result="offsetblur"/>
      <feComponentTransfer><feFuncA type="linear" slope="0.4"/></feComponentTransfer>
      <feMerge><feMergeNode/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>
  <g filter="url(#dropShadowGansoRuntime)">
    <ellipse cx="18" cy="21" rx="10" ry="7.5" fill="#f8fafc" stroke="#64748b" stroke-width="1.1"/>
    <path d="M12 20 C15 17 20 17 24 20 C20 22 15 22 12 20 Z" fill="#e2e8f0" stroke="#94a3b8" stroke-width="0.7"/>
    <path d="M12 16 C10 12 8 8 7 5 C9 4.5 11 6 12 9 C13 12 14 15 15 17 Z" fill="#f8fafc" stroke="#64748b" stroke-width="1.1" stroke-linejoin="round"/>
    <circle cx="7.5" cy="5.5" r="3.4" fill="#f8fafc" stroke="#64748b" stroke-width="1.1"/>
    <circle cx="6.4" cy="5" r="0.85" fill="#1e293b"/>
    <circle cx="6.15" cy="4.75" r="0.28" fill="#ffffff"/>
    <path d="M4.5 5.8 L1.5 4.2 L4.3 3.4 Z" fill="#f97316" stroke="#c2410c" stroke-width="0.7" stroke-linejoin="round"/>
    <path d="M14 28 L12.5 30.5 M14 28 L14.5 30.5 M14 28 L15.5 30.2" stroke="#f97316" stroke-width="1.2" stroke-linecap="round"/>
    <path d="M20 28 L18.5 30.5 M20 28 L20.5 30.5 M20 28 L21.5 30.2" stroke="#f97316" stroke-width="1.2" stroke-linecap="round"/>
    <path d="M26 18 C29 17 30 20 28 22 C27 20 27 19 26 18 Z" fill="#e2e8f0" stroke="#94a3b8" stroke-width="0.7"/>
    <circle class="cursor-core-dot" cx="18" cy="20" r="1.2" fill="#cbd5e1" opacity="0.95"/>
  </g>
</svg>`.trim(),
    },
};
/** Opción “cursor del sistema” (sin SVG custom). */
const CURSOR_SYSTEM_ITEM = {
    id: 'system',
    nombre: 'Sistema',
    descripcion: 'Cursor normal del sistema operativo.',
    accent: '#64748b',
};
const CURSOR_IDS_VALIDOS = [
    'tech',
    'classic',
    'minimal',
    'banana',
    'hongo',
    'metallica',
    'ganso',
    'system',
];
/** Evita registrar mousemove/hover dos veces al cambiar de variante. */
let motorCursorListo = false;
/** Variante activa para colorear la estela. */
let varianteTrailActual = 'tech';
/**
 * Estela — pool + frecuencia equilibrada (suave sin saturar el DOM).
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Antes se creaba y borraba un <div> en cada partícula (~30 ms).
 * Ahora reutilizamos N divs fijos (pool).
 * 60 ms se sentía “a saltos”; ~42 ms es un punto medio: más suave
 * que 60, y sigue costando menos que spawnear/destruir nodos.
 * Si el pool está ocupado, se salta esa partícula.
 */
const TRAIL_POOL_SIZE = 16;
/** Antes 30 (denso) → 60 (raro) → 42 (suave + razonable). */
const TRAIL_INTERVAL_MS = 42;
/** Duración del fade; debe coincidir con transition CSS (~0.4s). */
const TRAIL_FADE_MS = 400;
let trailPool = [];
let trailPoolListo = false;
let lastTrailTime = 0;
/**
 * Detecta táctil / híbrido / pantallas chicas.
 * Mismo criterio que el cursor original (evita bug “sin cursor”).
 */
function esDispositivoTactilOHibrido() {
    return ('ontouchstart' in window ||
        navigator.maxTouchPoints > 0 ||
        window.matchMedia('(hover: none)').matches ||
        window.matchMedia('(pointer: coarse)').matches ||
        window.innerWidth <= 1024);
}
/**
 * Valida y normaliza un id leído de localStorage.
 */
function normalizarCursorId(valor) {
    if (valor && CURSOR_IDS_VALIDOS.includes(valor)) {
        return valor;
    }
    // Default: el tech histórico de SIGMA
    return 'tech';
}
/**
 * Lee la preferencia del usuario. Si no hay nada guardado → 'tech'.
 */
function getCursorPreferido() {
    try {
        return normalizarCursorId(localStorage.getItem(CURSOR_STORAGE_KEY));
    }
    catch {
        // localStorage puede fallar en modo privado estricto
        return 'tech';
    }
}
/**
 * Persiste la elección en este navegador/dispositivo.
 */
function setCursorPreferido(id) {
    try {
        localStorage.setItem(CURSOR_STORAGE_KEY, id);
    }
    catch {
        console.warn('No se pudo guardar preferencia de cursor en localStorage');
    }
}
/**
 * Lista pública para el modal (sin markup SVG pesado en el listado).
 */
function obtenerCatalogoPublico() {
    // EXPLICACIÓN: Object.values evita olvidar una variante nueva en el modal
    const variantes = Object.values(CURSOR_VARIANTES).map((v) => ({
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
function obtenerSvgPreview(id) {
    if (id === 'system') {
        // Icono tipográfico simple: no hay SVG custom
        return '';
    }
    return CURSOR_VARIANTES[id].svgMarkup;
}
/**
 * Oculta el custom y restaura el cursor del SO.
 */
function desactivarCursorPersonalizado(motivo) {
    // EXPLICACIÓN: sin custom-cursor-active, base.css NO fuerza cursor: none
    document.documentElement.classList.remove('custom-cursor-active');
    document.documentElement.removeAttribute('data-cursor-variant');
    const cursor = document.getElementById('tech-cursor');
    if (cursor) {
        cursor.style.display = 'none';
        cursor.classList.remove('hover-active');
    }
    // Ocultar partículas del pool para que no queden puntos flotando
    ocultarPoolTrail();
    console.log(`Cursor personalizado deshabilitado (${motivo}) — fallback al cursor del sistema`);
}
/**
 * Crea una sola vez los divs reutilizables de la estela.
 * Efectos secundarios: añade TRAIL_POOL_SIZE nodos a document.body.
 */
function asegurarPoolTrail() {
    if (trailPoolListo) {
        return;
    }
    trailPoolListo = true;
    for (let i = 0; i < TRAIL_POOL_SIZE; i++) {
        const el = document.createElement('div');
        // Empiezan ocultos; al spawnear se muestran y se reciclan
        el.className = 'cursor-trail';
        el.style.display = 'none';
        el.setAttribute('aria-hidden', 'true');
        document.body.appendChild(el);
        trailPool.push({ el, busy: false, hideTimer: null });
    }
}
/**
 * Esconde todas las partículas del pool (p. ej. al pasar a cursor sistema).
 */
function ocultarPoolTrail() {
    for (const slot of trailPool) {
        if (slot.hideTimer !== null) {
            clearTimeout(slot.hideTimer);
            slot.hideTimer = null;
        }
        slot.busy = false;
        slot.el.style.display = 'none';
        slot.el.style.opacity = '0';
    }
}
/**
 * Muestra una partícula de estela en (x, y) reusando el pool.
 *
 * Args:
 *   x, y — coordenadas del mouse (clientX/clientY)
 *
 * Efectos secundarios: reutiliza un div del pool; no crea nodos nuevos.
 * Si todos están ocupados, no hace nada (mejor que saturar el DOM).
 */
function crearParticulaTrail(x, y) {
    asegurarPoolTrail();
    // Buscar el primer slot libre
    const slot = trailPool.find((p) => !p.busy);
    if (!slot) {
        return;
    }
    slot.busy = true;
    if (slot.hideTimer !== null) {
        clearTimeout(slot.hideTimer);
        slot.hideTimer = null;
    }
    const el = slot.el;
    // Paso 1: reset visual SIN transición (snap a visible en la nueva posición)
    el.style.transition = 'none';
    el.className = `cursor-trail cursor-trail--${varianteTrailActual}`;
    el.style.left = `${x}px`;
    el.style.top = `${y}px`;
    el.style.opacity = '1';
    el.style.transform = 'translate(-50%, -50%) scale(1)';
    el.style.display = '';
    // Forzar reflow para que el navegador “vea” el estado inicial
    // antes de animar el fade (si no, a veces salta directo a opacity 0)
    void el.offsetWidth;
    // Paso 2: reactivar transición CSS y animar desaparición
    el.style.transition = '';
    requestAnimationFrame(() => {
        el.style.transform = 'translate(-50%, -50%) scale(0)';
        el.style.opacity = '0';
    });
    // Paso 3: al terminar el fade, liberar el slot (no se borra el div)
    slot.hideTimer = setTimeout(() => {
        el.style.display = 'none';
        slot.busy = false;
        slot.hideTimer = null;
    }, TRAIL_FADE_MS);
}
/**
 * Inyecta el SVG de la variante dentro de #tech-cursor.
 */
function inyectarSvgVariante(cursorEl, id) {
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
function asegurarMotorCursor(cursor) {
    if (motorCursorListo) {
        return;
    }
    motorCursorListo = true;
    // Pool listo desde el primer uso del motor (12 divs fijos, no se recrean)
    asegurarPoolTrail();
    // EXPLICACIÓN: requestAnimationFrame evita jank al mover el SVG
    document.addEventListener('mousemove', (e) => {
        // Si el usuario eligió "sistema", el div está oculto; no crear estela
        if (!document.documentElement.classList.contains('custom-cursor-active')) {
            return;
        }
        requestAnimationFrame(() => {
            cursor.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
            // Menos frecuencia = menos trabajo (TRAIL_INTERVAL_MS ≈ 60)
            const now = Date.now();
            if (now - lastTrailTime > TRAIL_INTERVAL_MS) {
                crearParticulaTrail(e.clientX, e.clientY);
                lastTrailTime = now;
            }
        });
    });
    const selectoresInteractivos = 'a, button, input, select, textarea, .btn, .card, .select2-container, .select2-selection, .select2-results__option';
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
function aplicarCursorPreferido(idOpcional) {
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
//# sourceMappingURL=cursor_personalizado.js.map