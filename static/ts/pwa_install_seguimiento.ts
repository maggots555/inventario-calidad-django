/**
 * pwa_install_seguimiento.ts — Banner de instalación PWA del seguimiento del cliente
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * ================================
 * Este archivo es una versión independiente de `pwa_install.ts` (el banner que
 * usan los EMPLEADOS dentro del sistema). Este es exclusivo de la página
 * pública `/seguimiento/<token>/`, que abren los CLIENTES desde su correo.
 *
 * ¿Por qué un archivo separado en vez de reutilizar `pwa_install.ts`?
 * - `pwa_install.ts` solo se carga en páginas que extienden `base.html`
 *   y que requieren sesión iniciada (`{% if user.is_authenticated %}`).
 *   La página de seguimiento es standalone y pública, no pasa por ahí.
 * - El manifest que se instala aquí es DISTINTO (apunta al token del
 *   cliente, no al sistema interno), así que conviene mantener la lógica
 *   de instalación separada para no mezclar los dos flujos.
 * - Usamos una clave de localStorage diferente para el "cooldown" de cierre,
 *   porque localStorage se comparte por dominio (no por página): si
 *   reutilizáramos la misma clave que el banner interno, cerrar uno
 *   silenciaría el otro sin razón.
 *
 * A petición del negocio, este banner es más insistente que el interno:
 * aparece a los 4 segundos (vs. 7s del banner interno), porque esta página
 * la usa un cliente externo una sola vez y queremos maximizar que instale
 * el acceso directo a su seguimiento.
 *
 * Mismo flujo que el banner interno:
 * 1. Android/Chrome/Edge → capturamos 'beforeinstallprompt' y mostramos
 *    nuestro propio botón "Instalar".
 * 2. iOS Safari → no existe ese evento; mostramos instrucciones manuales
 *    ("Compartir" → "Agregar a pantalla de inicio").
 *
 * NOTA TÉCNICA: todo el archivo va envuelto en un IIFE (función que se
 * ejecuta sola) para que sus variables (DISMISSED_KEY, promptEvent, etc.)
 * no choquen con las de 'pwa_install.ts' — ambos scripts se compilan juntos
 * y, sin este envoltorio, TypeScript los trataría como si compartieran el
 * mismo espacio global (ambos declaran nombres iguales).
 */
(function (): void {

// ── Tipos ──────────────────────────────────────────────────────────────────────

interface BeforeInstallPromptEvent extends Event {
    readonly platforms: string[];
    readonly userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
    prompt(): Promise<void>;
}

interface NavigatorIOS extends Navigator {
    standalone?: boolean;
}

// ── Constantes ─────────────────────────────────────────────────────────────────

/** Clave de localStorage propia de esta página (no compartida con el banner interno). */
const DISMISSED_KEY = 'pwa_install_dismissed_at_seguimiento';

/** Días de cooldown tras cerrar el banner. */
const COOLDOWN_DIAS = 7;

/**
 * Milisegundos de espera antes de mostrar el banner.
 * A propósito más corto (4s) que el banner interno (7s): el cliente solo
 * visita esta página una vez desde su correo, así que se prioriza que
 * vea la invitación a instalar cuanto antes.
 */
const DELAY_MOSTRAR_MS = 4_000;

// ── Helpers de detección ───────────────────────────────────────────────────────

function yaEstaInstalada(): boolean {
    const esStandalone = window.matchMedia('(display-mode: standalone)').matches;
    const esStandaloneIOS = (navigator as NavigatorIOS).standalone === true;
    return esStandalone || esStandaloneIOS;
}

function estaEnCooldown(): boolean {
    const ts = localStorage.getItem(DISMISSED_KEY);
    if (!ts) return false;
    const msPasados = Date.now() - parseInt(ts, 10);
    return msPasados < COOLDOWN_DIAS * 24 * 60 * 60 * 1000;
}

function esIOSNoInstalado(): boolean {
    const esIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
    const noInstalado = !(navigator as NavigatorIOS).standalone;
    return esIOS && noInstalado;
}

// ── Animación del banner ───────────────────────────────────────────────────────

function mostrarBanner(): void {
    const banner = document.getElementById('st-pwa-install-banner');
    if (!banner) return;
    banner.style.display = 'block';
    // Forzamos un reflow para que la transición CSS funcione correctamente.
    void banner.offsetHeight;
    banner.classList.add('is-visible');
}

function ocultarBanner(): void {
    const banner = document.getElementById('st-pwa-install-banner');
    if (!banner) return;
    banner.classList.remove('is-visible');
    banner.addEventListener('transitionend', () => {
        banner.style.display = 'none';
    }, { once: true });
}

function guardarDismiss(): void {
    localStorage.setItem(DISMISSED_KEY, Date.now().toString());
}

// ── Lógica principal ───────────────────────────────────────────────────────────

let promptEvent: BeforeInstallPromptEvent | null = null;

window.addEventListener('beforeinstallprompt', (e: Event) => {
    e.preventDefault();
    promptEvent = e as BeforeInstallPromptEvent;

    if (yaEstaInstalada() || estaEnCooldown()) return;

    setTimeout(mostrarBanner, DELAY_MOSTRAR_MS);
});

document.addEventListener('DOMContentLoaded', () => {
    if (yaEstaInstalada() || estaEnCooldown()) return;

    const installBtn = document.getElementById('st-pwa-install-btn') as HTMLButtonElement | null;
    const dismissBtn = document.getElementById('st-pwa-dismiss-btn') as HTMLButtonElement | null;
    const iosInstr   = document.getElementById('st-pwa-ios-instructions') as HTMLElement | null;
    const androidBtn = document.getElementById('st-pwa-android-wrapper') as HTMLElement | null;

    // ── iOS: instrucciones manuales (no existe 'beforeinstallprompt') ────────
    if (esIOSNoInstalado()) {
        if (iosInstr)   iosInstr.style.display   = 'flex';
        if (androidBtn) androidBtn.style.display = 'none';
        setTimeout(mostrarBanner, DELAY_MOSTRAR_MS);
    }

    // ── Botón "Instalar" (Android / Chrome / Edge) ───────────────────────────
    installBtn?.addEventListener('click', async () => {
        if (!promptEvent) return;
        await promptEvent.prompt();
        const { outcome } = await promptEvent.userChoice;
        if (outcome === 'accepted') {
            ocultarBanner();
        }
        promptEvent = null;
    });

    // ── Botón "✕" para cerrar el banner ─────────────────────────────────────
    dismissBtn?.addEventListener('click', () => {
        guardarDismiss();
        ocultarBanner();
    });

    // ── Ocultar automáticamente si la app se instala ─────────────────────────
    window.addEventListener('appinstalled', () => {
        ocultarBanner();
    });
});

})();
