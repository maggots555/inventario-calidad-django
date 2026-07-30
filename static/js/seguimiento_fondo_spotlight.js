"use strict";
/**
 * seguimiento_fondo_spotlight.ts
 *
 * Objetivo: iluminar la grilla de puntos del fondo del portal de seguimiento
 * según la posición del puntero (efecto “spotlight” cyan sobre puntos tenues).
 *
 * Cómo funciona (para principiantes):
 * 1. El CSS pinta dos capas de puntos (grises + cyan de la paleta SIC).
 * 2. La capa cyan solo se ve dentro de una máscara radial.
 * 3. Este script mueve el centro de esa máscara con --st-spot-x / --st-spot-y.
 *
 * Efectos: solo CSS variables en .st-fondo-puntos; no toca BD ni red.
 * Accesibilidad: si el usuario pide reducir movimiento, no seguimos el cursor.
 */
/** Radio del halo en CSS (debe coincidir con el mask del stylesheet). */
const SPOT_ACTIVO = '1';
/**
 * Actualiza las variables CSS del spotlight según coordenadas de pantalla.
 *
 * @param fondo - Elemento `.st-fondo-puntos` donde viven las CSS vars
 * @param clientX - Coordenada X del puntero (viewport)
 * @param clientY - Coordenada Y del puntero (viewport)
 */
function actualizarSpotlight(fondo, clientX, clientY) {
    // EXPLICACIÓN PARA PRINCIPIANTES: usamos px absolutos del viewport porque
    // el div es position:fixed a pantalla completa (igual que el mouse).
    fondo.style.setProperty('--st-spot-x', `${clientX}px`);
    fondo.style.setProperty('--st-spot-y', `${clientY}px`);
    fondo.dataset.activo = SPOT_ACTIVO;
}
/**
 * Apaga el spotlight (puntos solo tenues) al soltar el dedo o salir de la ventana.
 *
 * @param fondo - Elemento `.st-fondo-puntos`
 */
function apagarSpotlight(fondo) {
    delete fondo.dataset.activo;
}
/**
 * Inicializa el seguimiento del puntero sobre el fondo de puntos.
 *
 * @returns void — sale temprano si no hay elemento o si reduce motion
 */
function inicializarFondoSpotlight() {
    const fondo = document.querySelector('.st-fondo-puntos');
    if (!fondo) {
        return;
    }
    // EXPLICACIÓN PARA PRINCIPIANTES: si el SO pide menos animación,
    // dejamos la grilla fija y no movemos el foco con el mouse.
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
    if (reduceMotion.matches) {
        return;
    }
    const onPointerMove = (evento) => {
        actualizarSpotlight(fondo, evento.clientX, evento.clientY);
    };
    // En móvil: al soltar el dedo, ocultamos el halo cyan.
    // En mouse: el clic (pointerup) NO apaga; solo mouseleave.
    const onPointerUp = (evento) => {
        if (evento.pointerType === 'touch' || evento.pointerType === 'pen') {
            apagarSpotlight(fondo);
        }
    };
    const onPointerLeave = () => {
        apagarSpotlight(fondo);
    };
    window.addEventListener('pointermove', onPointerMove, { passive: true });
    window.addEventListener('pointerup', onPointerUp, { passive: true });
    window.addEventListener('pointercancel', onPointerUp, { passive: true });
    document.documentElement.addEventListener('mouseleave', onPointerLeave);
}
// Arranque al cargar el DOM (script al final del body o DOMContentLoaded).
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarFondoSpotlight);
}
else {
    inicializarFondoSpotlight();
}
//# sourceMappingURL=seguimiento_fondo_spotlight.js.map