"use strict";
/* =============================================================================
   DARK MODE TOGGLE - Manejo del tema claro/oscuro
   Descripción: Lee la preferencia de localStorage o del sistema operativo,
   y permite al usuario alternar entre temas con el botón de la navbar.
   ============================================================================= */
/**
 * Inicializa el toggle de modo oscuro.
 *
 * Lógica de prioridad:
 * 1. Si el usuario ya eligió un tema → usar ese (localStorage 'theme')
 * 2. Si no, respetar la preferencia del SO (prefers-color-scheme)
 * 3. Fallback: modo claro
 */
function inicializarDarkMode() {
    const toggle = document.getElementById('darkModeToggle');
    if (!toggle)
        return;
    toggle.addEventListener('click', function () {
        const html = document.documentElement;
        const currentTheme = html.getAttribute('data-bs-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        html.setAttribute('data-bs-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        // Actualizar meta theme-color para la barra del navegador móvil
        const metaTheme = document.querySelector('meta[name="theme-color"]');
        if (metaTheme) {
            metaTheme.setAttribute('content', newTheme === 'dark' ? '#0f172a' : '#1f6391');
        }
    });
}
// Ejecutar al cargar el DOM
document.addEventListener('DOMContentLoaded', inicializarDarkMode);
//# sourceMappingURL=dark_mode.js.map