"use strict";
/* =============================================================================
   DARK MODE TOGGLE - Manejo del tema claro/oscuro
   Descripción: Lee la preferencia de localStorage o del sistema operativo,
   y permite al usuario alternar entre temas con el botón de la navbar.
   ============================================================================= */
/** Colores de la barra de estado / theme-color (claro = marca, oscuro = body dark). */
const THEME_COLOR_CLARO = '#1f6391';
const THEME_COLOR_OSCURO = '#0f172a';
/**
 * Actualiza el meta theme-color para la barra de estado en móvil/PWA.
 *
 * Objetivo: que Android/Chrome (y PWA standalone) pinten la status bar
 * del mismo color que el tema activo, no el azul fijo del HTML.
 *
 * @param tema - `'dark'` o `'light'` (cualquier otro valor se trata como claro)
 */
function actualizarThemeColor(tema) {
    const metaTheme = document.querySelector('meta[name="theme-color"]');
    if (!metaTheme) {
        return;
    }
    metaTheme.setAttribute('content', tema === 'dark' ? THEME_COLOR_OSCURO : THEME_COLOR_CLARO);
}
/**
 * Inicializa el toggle de modo oscuro.
 *
 * Lógica de prioridad:
 * 1. Si el usuario ya eligió un tema → usar ese (localStorage 'theme')
 * 2. Si no, respetar la preferencia del SO (prefers-color-scheme)
 * 3. Fallback: modo claro
 *
 * Efectos: al cargar, sincroniza theme-color con data-bs-theme (por si el
 * anti-flash no corrió o se navega sin reload completo). Al clic, guarda
 * preferencia y actualiza tema + barra de estado.
 */
function inicializarDarkMode() {
    const html = document.documentElement;
    const temaActual = html.getAttribute('data-bs-theme') || 'light';
    // Refuerzo: al cargar la página, barra de estado = tema ya aplicado
    actualizarThemeColor(temaActual);
    const toggle = document.getElementById('darkModeToggle');
    if (!toggle) {
        return;
    }
    toggle.addEventListener('click', function () {
        const currentTheme = html.getAttribute('data-bs-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-bs-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        actualizarThemeColor(newTheme);
    });
}
// Ejecutar al cargar el DOM
document.addEventListener('DOMContentLoaded', inicializarDarkMode);
//# sourceMappingURL=dark_mode.js.map