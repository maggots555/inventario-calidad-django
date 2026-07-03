/**
 * push_notifications_cliente.ts — Notificaciones push para el CLIENTE en el seguimiento público
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo es el equivalente de `push_notifications.ts` (que usan los
 * empleados en "Mi Perfil"), pero para el cliente final en la página pública
 * `/seguimiento/<token>/`.
 *
 * La diferencia clave es CÓMO nos identificamos ante el servidor:
 * - El empleado usa su sesión iniciada (`request.user` en Django).
 * - El cliente NO tiene cuenta — se identifica con el TOKEN de su enlace,
 *   que ya viene incrustado en las URLs de los 3 endpoints (ver atributos
 *   data-* del contenedor #st-push-wrapper en el HTML).
 *
 * Flujo técnico (idéntico al de empleados, cambia solo la URL):
 *   GET  /seguimiento/<token>/push/vapid-key/  → llave pública VAPID
 *   pushManager.subscribe({...})               → el navegador genera la suscripción
 *   POST /seguimiento/<token>/push/suscribir/  → la guardamos en el servidor
 *
 * NOTA TÉCNICA: todo el archivo va envuelto en un IIFE (función que se
 * ejecuta sola) para que sus variables (VAPID_URL, PushEstado, etc.) no
 * choquen con las de 'push_notifications.ts' — ambos se compilan juntos y,
 * sin este envoltorio, TypeScript los trataría como si compartieran el
 * mismo espacio global (ambos declaran nombres iguales).
 */
/// <reference path="./eventos_seguimiento.d.ts" />
(function (): void {

// ── Tipos ────────────────────────────────────────────────────────────────────

interface VapidKeyResponse {
    vapid_public_key: string;
}

interface PushApiResponse {
    ok: boolean;
    accion?: string;
    error?: string;
}

// ── Referencias al DOM ───────────────────────────────────────────────────────

const wrapper = document.querySelector<HTMLDivElement>('#st-push-wrapper');
const btn     = document.querySelector<HTMLButtonElement>('#st-push-btn');
const icon    = document.querySelector<HTMLSpanElement>('#st-push-icon');
const label   = document.querySelector<HTMLParagraphElement>('#st-push-label');

// Las URLs de los 3 endpoints viajan en atributos data-* del propio HTML,
// generadas por Django con {% url %} — así este script no necesita conocer
// el token directamente ni construir URLs a mano.
const VAPID_URL      = wrapper?.dataset.vapidUrl ?? '';
const SUSCRIBIR_URL  = wrapper?.dataset.suscribirUrl ?? '';
const CANCELAR_URL   = wrapper?.dataset.cancelarUrl ?? '';

// ── Utilidades ───────────────────────────────────────────────────────────────

function urlBase64ToUint8Array(base64String: string): ArrayBuffer {
    const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    const base64  = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const rawData = atob(base64);
    const buffer  = new Uint8Array(rawData.length);
    for (let i = 0; i < rawData.length; i++) {
        buffer[i] = rawData.charCodeAt(i);
    }
    return buffer.buffer as ArrayBuffer;
}

/**
 * A diferencia de push_notifications.ts (que sí necesita X-CSRFToken porque
 * el usuario tiene sesión con cookie CSRF), estos endpoints son públicos y
 * están marcados @csrf_exempt en Django (igual que el chat de IA de esta
 * misma página) — el token en la URL ya es la validación de identidad.
 */
async function postJson(url: string, body: object): Promise<PushApiResponse> {
    const res = await fetch(url, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    });
    return res.json() as Promise<PushApiResponse>;
}

// ── Estado visual del botón ──────────────────────────────────────────────────

type PushEstado = 'activo' | 'inactivo' | 'bloqueado' | 'no-soportado';

function aplicarEstado(estado: PushEstado): void {
    if (!btn || !icon || !label) return;

    btn.classList.remove('is-active', 'is-blocked');
    btn.disabled = false;
    btn.innerHTML = '';

    switch (estado) {
        case 'activo':
            icon.textContent = '🔔';
            btn.classList.add('is-active');
            btn.textContent = 'Desactivar';
            label.textContent = 'Notificaciones activas: te avisaremos de cada avance.';
            break;

        case 'inactivo':
            icon.textContent = '🔕';
            btn.textContent = 'Activar';
            label.textContent = 'Activa las notificaciones para enterarte de cada avance de tu equipo.';
            break;

        case 'bloqueado':
            icon.textContent = '🔕';
            btn.classList.add('is-blocked');
            btn.textContent = 'Bloqueadas';
            btn.disabled = true;
            label.textContent = 'Bloqueaste las notificaciones en este navegador. Actívalas desde el ícono de candado junto a la URL.';
            break;

        case 'no-soportado':
            icon.textContent = '🔕';
            btn.textContent = 'No disponible';
            btn.disabled = true;
            label.textContent = 'Tu navegador no soporta notificaciones push.';
            break;
    }
}

// ── Lógica principal ─────────────────────────────────────────────────────────

async function inicializar(): Promise<void> {
    if (!btn || !wrapper) return;

    if (!VAPID_URL || !SUSCRIBIR_URL || !CANCELAR_URL) {
        // Sin URLs no hay forma de continuar — ocultamos el bloque en vez de
        // mostrar un botón roto.
        wrapper.style.display = 'none';
        return;
    }

    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        aplicarEstado('no-soportado');
        return;
    }

    const permiso = Notification.permission;
    if (permiso === 'denied') {
        window.EventosSeguimiento?.registrarEvento('push_permiso_denegado', {}, true);
        aplicarEstado('bloqueado');
        return;
    }

    try {
        const registro = await navigator.serviceWorker.ready;
        const suscripcionActual = await registro.pushManager.getSubscription();
        aplicarEstado(suscripcionActual ? 'activo' : 'inactivo');
    } catch {
        aplicarEstado('inactivo');
    }
}

async function activar(): Promise<void> {
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = 'Activando...';

    try {
        const permiso = await Notification.requestPermission();
        if (permiso !== 'granted') {
            if (permiso === 'denied') {
                window.EventosSeguimiento?.registrarEvento('push_permiso_denegado');
            }
            aplicarEstado(permiso === 'denied' ? 'bloqueado' : 'inactivo');
            return;
        }

        const vapidRes  = await fetch(VAPID_URL);
        const vapidData = await vapidRes.json() as VapidKeyResponse;
        const vapidKey  = urlBase64ToUint8Array(vapidData.vapid_public_key);

        const registro    = await navigator.serviceWorker.ready;
        const suscripcion = await registro.pushManager.subscribe({
            userVisibleOnly:      true,
            applicationServerKey: vapidKey,
        });

        const suscripcionJson = suscripcion.toJSON() as {
            endpoint: string;
            keys: { p256dh: string; auth: string };
        };

        const res = await postJson(SUSCRIBIR_URL, {
            endpoint: suscripcionJson.endpoint,
            keys:     suscripcionJson.keys,
        });

        if (res.ok) {
            aplicarEstado('activo');
        } else {
            console.error('[PushCliente] Error al guardar suscripción:', res.error);
            aplicarEstado('inactivo');
        }
    } catch (err) {
        console.error('[PushCliente] Error al activar push:', err);
        aplicarEstado('inactivo');
    }
}

async function desactivar(): Promise<void> {
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = 'Desactivando...';

    try {
        const registro    = await navigator.serviceWorker.ready;
        const suscripcion = await registro.pushManager.getSubscription();

        if (suscripcion) {
            const endpoint = suscripcion.endpoint;
            await suscripcion.unsubscribe();
            await postJson(CANCELAR_URL, { endpoint });
        }

        aplicarEstado('inactivo');
    } catch (err) {
        console.error('[PushCliente] Error al desactivar push:', err);
        aplicarEstado('inactivo');
    }
}

// ── Event listener del botón ─────────────────────────────────────────────────

if (btn) {
    btn.addEventListener('click', async () => {
        if (Notification.permission === 'denied') {
            aplicarEstado('bloqueado');
            return;
        }

        const registro    = await navigator.serviceWorker.ready;
        const suscripcion = await registro.pushManager.getSubscription();

        if (suscripcion) {
            await desactivar();
        } else {
            await activar();
        }
    });
}

// ── Inicializar al cargar la página ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    inicializar().catch((err) => {
        console.warn('[PushCliente] Error al inicializar:', err);
    });
});

})();
