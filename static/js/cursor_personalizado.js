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
};
/** Opción “cursor del sistema” (sin SVG custom). */
const CURSOR_SYSTEM_ITEM = {
    id: 'system',
    nombre: 'Sistema',
    descripcion: 'Cursor normal del sistema operativo.',
    accent: '#64748b',
};
const CURSOR_IDS_VALIDOS = ['tech', 'classic', 'minimal', 'system'];
/** Evita registrar mousemove/hover dos veces al cambiar de variante. */
let motorCursorListo = false;
/** Variante activa para colorear la estela. */
let varianteTrailActual = 'tech';
/** Intervalo mínimo entre partículas de estela (ms). */
let lastTrailTime = 0;
const TRAIL_INTERVAL_MS = 30;
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
    return [
        {
            id: CURSOR_VARIANTES.tech.id,
            nombre: CURSOR_VARIANTES.tech.nombre,
            descripcion: CURSOR_VARIANTES.tech.descripcion,
            accent: CURSOR_VARIANTES.tech.accent,
        },
        {
            id: CURSOR_VARIANTES.classic.id,
            nombre: CURSOR_VARIANTES.classic.nombre,
            descripcion: CURSOR_VARIANTES.classic.descripcion,
            accent: CURSOR_VARIANTES.classic.accent,
        },
        {
            id: CURSOR_VARIANTES.minimal.id,
            nombre: CURSOR_VARIANTES.minimal.nombre,
            descripcion: CURSOR_VARIANTES.minimal.descripcion,
            accent: CURSOR_VARIANTES.minimal.accent,
        },
        CURSOR_SYSTEM_ITEM,
    ];
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
    console.log(`Cursor personalizado deshabilitado (${motivo}) — fallback al cursor del sistema`);
}
/**
 * Crea una partícula de estela en (x, y) con color según la variante.
 */
function crearParticulaTrail(x, y) {
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
    // EXPLICACIÓN: requestAnimationFrame evita jank al mover el SVG
    document.addEventListener('mousemove', (e) => {
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