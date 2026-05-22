"use strict";
/**
 * pwa_install.ts — Banner de instalación PWA
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * ================================
 * Este archivo maneja el banner que aparece en la parte inferior de la pantalla
 * invitando al usuario a instalar la app en su celular/computadora.
 *
 * Hay dos flujos distintos según el dispositivo:
 *
 * 1. Android / Chrome / Edge:
 *    El navegador dispara el evento 'beforeinstallprompt' cuando detecta que la
 *    PWA cumple los criterios de instalación. Lo capturamos, lo guardamos, y
 *    cuando el usuario toca "Instalar" llamamos a promptEvent.prompt() para
 *    mostrar el diálogo nativo del navegador.
 *
 * 2. iPhone / iPad (iOS Safari):
 *    Apple NO dispara 'beforeinstallprompt'. En iOS el usuario instala
 *    manualmente: toca el ícono de compartir → "Agregar a pantalla de inicio".
 *    Detectamos que es iOS y mostramos instrucciones visuales.
 *
 * Lógica anti-spam:
 *    Si el usuario cierra el banner, guardamos la fecha en localStorage y no
 *    volvemos a mostrar el banner por COOLDOWN_DIAS días.
 *    Si la app ya está instalada (modo standalone), nunca mostramos el banner.
 */
// ── Constantes ─────────────────────────────────────────────────────────────────
/** Clave en localStorage para guardar cuándo se dismissó el banner */
const DISMISSED_KEY = 'pwa_install_dismissed_at';
/** Días de cooldown tras cerrar el banner */
const COOLDOWN_DIAS = 7;
/** Milisegundos de espera antes de mostrar el banner (no mostrar de inmediato) */
const DELAY_MOSTRAR_MS = 20000; // 20 segundos
// ── Helpers de detección ───────────────────────────────────────────────────────
/**
 * Devuelve true si la app ya está instalada y corriendo en modo standalone.
 * En ese caso nunca mostramos el banner (ya está instalada).
 */
function yaEstaInstalada() {
    // display-mode: standalone → Android/Desktop instalado
    const esStandalone = window.matchMedia('(display-mode: standalone)').matches;
    // navigator.standalone → iOS instalado
    const esStandaloneIOS = navigator.standalone === true;
    return esStandalone || esStandaloneIOS;
}
/**
 * Devuelve true si el usuario cerró el banner recientemente (dentro del cooldown).
 */
function estaEnCooldown() {
    const ts = localStorage.getItem(DISMISSED_KEY);
    if (!ts)
        return false;
    const msPasados = Date.now() - parseInt(ts, 10);
    return msPasados < COOLDOWN_DIAS * 24 * 60 * 60 * 1000;
}
/**
 * Devuelve true si el dispositivo es iOS (iPhone/iPad) y NO está en modo standalone.
 * En iOS necesitamos mostrar instrucciones manuales en lugar del botón nativo.
 */
function esIOSNoInstalado() {
    const esIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
    const noInstalado = !navigator.standalone;
    return esIOS && noInstalado;
}
// ── Animación del banner ───────────────────────────────────────────────────────
/**
 * Hace visible el banner con animación de slide-up desde el bottom.
 */
function mostrarBanner() {
    const banner = document.getElementById('pwa-install-banner');
    if (!banner)
        return;
    banner.style.display = 'block';
    // Forzamos un reflow para que la transición CSS funcione correctamente
    void banner.offsetHeight;
    banner.classList.add('is-visible');
}
/**
 * Oculta el banner con animación de slide-down.
 */
function ocultarBanner() {
    const banner = document.getElementById('pwa-install-banner');
    if (!banner)
        return;
    banner.classList.remove('is-visible');
    banner.addEventListener('transitionend', () => {
        banner.style.display = 'none';
    }, { once: true });
}
/**
 * Guarda la fecha actual en localStorage para activar el cooldown.
 */
function guardarDismiss() {
    localStorage.setItem(DISMISSED_KEY, Date.now().toString());
}
// ── Lógica principal ───────────────────────────────────────────────────────────
/** Guardamos el evento de instalación para usarlo cuando el usuario toque el botón */
let promptEvent = null;
/**
 * Capturamos 'beforeinstallprompt' antes de DOMContentLoaded para no perdernos
 * el evento si el navegador lo dispara muy temprano.
 *
 * IMPORTANTE: llamamos preventDefault() para que el navegador NO muestre
 * su mini-banner automático — nosotros controlamos cuándo mostrarlo.
 */
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    promptEvent = e;
    // No mostramos si ya está instalada o en cooldown
    if (yaEstaInstalada() || estaEnCooldown())
        return;
    // Mostramos después del delay para no interrumpir al usuario de inmediato
    setTimeout(mostrarBanner, DELAY_MOSTRAR_MS);
});
/**
 * Una vez cargado el DOM, conectamos los event listeners del banner.
 */
document.addEventListener('DOMContentLoaded', () => {
    // Si ya está instalada o en cooldown, salimos
    if (yaEstaInstalada() || estaEnCooldown())
        return;
    const installBtn = document.getElementById('pwa-install-btn');
    const dismissBtn = document.getElementById('pwa-dismiss-btn');
    const iosInstr = document.getElementById('pwa-ios-instructions');
    const androidBtn = document.getElementById('pwa-android-btn-wrapper');
    // ── iOS: instrucciones manuales ──────────────────────────────────────────
    if (esIOSNoInstalado()) {
        // Mostramos instrucciones de iOS, ocultamos el botón de Android
        if (iosInstr)
            iosInstr.style.display = 'flex';
        if (androidBtn)
            androidBtn.style.display = 'none';
        setTimeout(mostrarBanner, DELAY_MOSTRAR_MS);
    }
    // ── Botón "Instalar" (Android / Chrome / Edge) ───────────────────────────
    installBtn === null || installBtn === void 0 ? void 0 : installBtn.addEventListener('click', async () => {
        if (!promptEvent)
            return;
        await promptEvent.prompt();
        const { outcome } = await promptEvent.userChoice;
        if (outcome === 'accepted') {
            ocultarBanner();
        }
        promptEvent = null;
    });
    // ── Botón "✕" para cerrar el banner ─────────────────────────────────────
    dismissBtn === null || dismissBtn === void 0 ? void 0 : dismissBtn.addEventListener('click', () => {
        guardarDismiss();
        ocultarBanner();
    });
    // ── Ocultar automáticamente si la app se instala ─────────────────────────
    window.addEventListener('appinstalled', () => {
        ocultarBanner();
    });
});
//# sourceMappingURL=pwa_install.js.map