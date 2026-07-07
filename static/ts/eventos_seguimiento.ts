/**
 * eventos_seguimiento.ts — Registro de eventos de producto en la vista pública del cliente.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Cuando el cliente hace algo importante (ve el banner PWA, abre el chat, etc.),
 * este módulo envía un POST silencioso al servidor para guardar ese evento.
 * El token del enlace ya va en la URL — no necesitamos sesión de usuario.
 *
 * NOTA TÉCNICA: IIFE para no chocar con otros scripts al compilar juntos.
 */
/// <reference path="./eventos_seguimiento.d.ts" />
(function (): void {

const SESSION_KEY = 'sic_seguimiento_session';
const DEDUP_PREFIX = 'sic_evt_dedup_';

/** URL del endpoint POST, inyectada por Django en data-eventos-url del body */
const EVENTOS_URL = document.body.dataset.eventosUrl ?? '';

/**
 * Genera o recupera un UUID de sesión en sessionStorage.
 * Agrupa eventos de la misma visita en el dashboard.
 */
function obtenerSessionId(): string {
    let id = sessionStorage.getItem(SESSION_KEY);
    if (!id) {
        id = crypto.randomUUID();
        sessionStorage.setItem(SESSION_KEY, id);
    }
    return id;
}

/**
 * Envía un evento al servidor sin bloquear la UI.
 *
 * @param tipo - Código del evento (ej. 'pwa_banner_mostrado')
 * @param metadata - Datos extra opcionales (sin texto del chat)
 * @param unaVezPorSesion - Si true, no reenvía el mismo tipo en esta pestaña
 */
function registrarEvento(
    tipo: string,
    metadata: Record<string, unknown> = {},
    unaVezPorSesion = false,
): void {
    if (!EVENTOS_URL) return;

    if (unaVezPorSesion) {
        const clave = DEDUP_PREFIX + tipo;
        if (sessionStorage.getItem(clave)) return;
        sessionStorage.setItem(clave, '1');
    }

    const payload = {
        tipo,
        session_id: obtenerSessionId(),
        metadata,
    };

    fetch(EVENTOS_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
    }).catch((err: unknown) => {
        console.warn('[EventosSeg] No se pudo enviar evento', tipo, err);
    });
}

// API global mínima para otros módulos de esta página
(window as Window).EventosSeguimiento = {
    registrarEvento,
    obtenerSessionId,
};

/**
 * Si el cliente llegó desde una notificación push con ?abrir=diagnostico,
 * abrimos el PDF dentro del mismo contexto de la PWA (no el navegador externo).
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * El push no puede enlazar directo al PDF porque el celular lo abre fuera de
 * la app instalada. Primero abrimos la página de seguimiento y desde aquí
 * redirigimos al PDF, igual que si el cliente pulsara el botón manualmente.
 */
function abrirDiagnosticoDesdePush(): void {
    const params = new URLSearchParams(window.location.search);
    if (params.get('abrir') !== 'diagnostico') return;

    const pdfUrl = document.body.dataset.diagnosticoPdfUrl ?? '';
    if (!pdfUrl) return;

    // Quitar el parámetro para que un refresh no vuelva a abrir el PDF
    const urlLimpia = new URL(window.location.href);
    urlLimpia.searchParams.delete('abrir');
    window.history.replaceState({}, '', urlLimpia.pathname + urlLimpia.hash);

    const separador = pdfUrl.includes('?') ? '&' : '?';
    window.location.href = `${pdfUrl}${separador}origen=push`;
}

document.addEventListener('DOMContentLoaded', () => {
    abrirDiagnosticoDesdePush();
});

})();
