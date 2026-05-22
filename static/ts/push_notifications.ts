/**
 * push_notifications.ts — Gestión de suscripción Web Push para SIGMA
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo controla el botón de notificaciones push en la página de perfil.
 * Se encarga de:
 *   1. Leer el estado actual del permiso del navegador
 *   2. Mostrar el toggle con el estado correcto (activo / inactivo / bloqueado)
 *   3. Al activar: solicitar permiso → suscribir al SW → enviar al servidor
 *   4. Al desactivar: cancelar suscripción en el servidor
 *   5. Si el permiso está BLOQUEADO: mostrar un tooltip con instrucciones
 *
 * Flujo técnico de suscripción:
 *   GET  /notificaciones/push/vapid-key/  → obtener llave pública VAPID
 *   pushManager.subscribe({...})          → el navegador devuelve un PushSubscription
 *   POST /notificaciones/push/suscribir/  → guardar en el servidor
 */

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

const toggleBtn     = document.querySelector<HTMLButtonElement>('#push-toggle-btn');
const toggleLabel   = document.querySelector<HTMLSpanElement>('#push-toggle-label');
const toggleBadge   = document.querySelector<HTMLSpanElement>('#push-toggle-badge');
const deniedTooltip = document.querySelector<HTMLDivElement>('#push-denied-tooltip');
const toggleWrapper = document.querySelector<HTMLDivElement>('#push-toggle-wrapper');

// ── Utilidades ───────────────────────────────────────────────────────────────

/**
 * Convierte una llave pública VAPID en base64url al Uint8Array que necesita
 * pushManager.subscribe(). Es el formato requerido por la Web Push API.
 */
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

/** Obtiene el CSRF token de las cookies de Django (requerido para POST). */
function getCsrfToken(): string {
    const match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
}

/** POST con JSON y CSRF automático. */
async function postJson(url: string, body: object): Promise<PushApiResponse> {
    const res = await fetch(url, {
        method:  'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken':  getCsrfToken(),
        },
        body: JSON.stringify(body),
    });
    return res.json() as Promise<PushApiResponse>;
}

// ── Estado visual del toggle ─────────────────────────────────────────────────

type PushEstado = 'activo' | 'inactivo' | 'bloqueado' | 'no-soportado';

function aplicarEstado(estado: PushEstado): void {
    if (!toggleBtn || !toggleLabel || !toggleBadge) return;

    // Resetear clases de estado del botón
    toggleBtn.classList.remove('is-active', 'is-blocked');
    toggleBtn.disabled = false;

    switch (estado) {
        case 'activo':
            toggleBtn.classList.add('is-active');
            toggleBtn.innerHTML = '<i class="bi bi-bell-fill"></i>Desactivar notificaciones';
            toggleLabel.textContent = 'Las notificaciones push están activas en este dispositivo.';
            toggleBadge.className   = 'pcard-push-badge is-active';
            toggleBadge.textContent = 'Activo';
            ocultarTooltipBloqueado();
            break;

        case 'inactivo':
            toggleBtn.innerHTML = '<i class="bi bi-bell-slash"></i>Activar notificaciones';
            toggleLabel.textContent = 'Activa las notificaciones para recibir avisos de tus órdenes.';
            toggleBadge.className   = 'pcard-push-badge is-inactive';
            toggleBadge.textContent = 'Inactivo';
            ocultarTooltipBloqueado();
            break;

        case 'bloqueado':
            toggleBtn.classList.add('is-blocked');
            toggleBtn.innerHTML = '<i class="bi bi-bell-slash-fill"></i>Notificaciones bloqueadas';
            toggleLabel.textContent = 'El navegador bloqueó las notificaciones. Sigue las instrucciones.';
            toggleBadge.className   = 'pcard-push-badge is-blocked';
            toggleBadge.textContent = 'Bloqueado';
            toggleBtn.disabled      = true;
            mostrarTooltipBloqueado();
            break;

        case 'no-soportado':
            toggleBtn.innerHTML     = '<i class="bi bi-bell-slash"></i>No disponible';
            toggleLabel.textContent = 'Tu navegador no soporta notificaciones push.';
            toggleBadge.className   = 'pcard-push-badge is-loading';
            toggleBadge.textContent = 'No soportado';
            toggleBtn.disabled      = true;
            break;
    }
}

// ── Tooltip de ayuda cuando el permiso está BLOQUEADO ────────────────────────

function mostrarTooltipBloqueado(): void {
    if (deniedTooltip) {
        deniedTooltip.style.display = 'block';
    }
}

function ocultarTooltipBloqueado(): void {
    if (deniedTooltip) {
        deniedTooltip.style.display = 'none';
    }
}

// ── Lógica principal ─────────────────────────────────────────────────────────

/**
 * Lee el estado actual del SW y del permiso push para inicializar la UI.
 */
async function inicializarToggle(): Promise<void> {
    if (!toggleBtn) return;

    // Verificar soporte del navegador
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        aplicarEstado('no-soportado');
        return;
    }

    const permiso = Notification.permission;

    if (permiso === 'denied') {
        aplicarEstado('bloqueado');
        return;
    }

    // Verificar si ya hay una suscripción activa en este navegador
    try {
        const registro = await navigator.serviceWorker.ready;
        const suscripcionActual = await registro.pushManager.getSubscription();
        aplicarEstado(suscripcionActual ? 'activo' : 'inactivo');
    } catch {
        aplicarEstado('inactivo');
    }
}

/**
 * Suscribir: pedir permiso → obtener VAPID key → suscribir → enviar al servidor.
 */
async function activarPush(): Promise<void> {
    if (!toggleBtn) return;
    toggleBtn.disabled = true;
    toggleBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>Activando...';

    try {
        // 1. Solicitar permiso al usuario
        const permiso = await Notification.requestPermission();
        if (permiso !== 'granted') {
            aplicarEstado(permiso === 'denied' ? 'bloqueado' : 'inactivo');
            return;
        }

        // 2. Obtener la llave pública VAPID del servidor
        const vapidRes  = await fetch('/notificaciones/push/vapid-key/');
        const vapidData = await vapidRes.json() as VapidKeyResponse;
        const vapidKey  = urlBase64ToUint8Array(vapidData.vapid_public_key);

        // 3. Crear la suscripción en el navegador
        const registro     = await navigator.serviceWorker.ready;
        const suscripcion  = await registro.pushManager.subscribe({
            userVisibleOnly:      true,   // Requerido por la spec: siempre mostrar notificación
            applicationServerKey: vapidKey,
        });

        // 4. Enviar los datos de suscripción al servidor Django
        const suscripcionJson = suscripcion.toJSON() as {
            endpoint: string;
            keys: { p256dh: string; auth: string };
        };

        const res = await postJson('/notificaciones/push/suscribir/', {
            endpoint: suscripcionJson.endpoint,
            keys:     suscripcionJson.keys,
        });

        if (res.ok) {
            aplicarEstado('activo');
        } else {
            console.error('[PUSH] Error al guardar suscripción:', res.error);
            aplicarEstado('inactivo');
        }

    } catch (err) {
        console.error('[PUSH] Error al activar push:', err);
        aplicarEstado('inactivo');
    }
}

/**
 * Desuscribir: cancelar en el navegador → notificar al servidor.
 */
async function desactivarPush(): Promise<void> {
    if (!toggleBtn) return;
    toggleBtn.disabled = true;
    toggleBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span>Desactivando...';

    try {
        const registro    = await navigator.serviceWorker.ready;
        const suscripcion = await registro.pushManager.getSubscription();

        if (suscripcion) {
            const endpoint = suscripcion.endpoint;
            await suscripcion.unsubscribe();

            // Notificar al servidor para marcar la suscripción como inactiva
            await postJson('/notificaciones/push/cancelar/', { endpoint });
        }

        aplicarEstado('inactivo');

    } catch (err) {
        console.error('[PUSH] Error al desactivar push:', err);
        // Aunque falle, mostramos inactivo porque ya no hay suscripción local
        aplicarEstado('inactivo');
    }
}

// ── Event listener del botón ─────────────────────────────────────────────────

if (toggleBtn) {
    toggleBtn.addEventListener('click', async () => {
        if (Notification.permission === 'denied') {
            mostrarTooltipBloqueado();
            return;
        }

        const registro    = await navigator.serviceWorker.ready;
        const suscripcion = await registro.pushManager.getSubscription();

        if (suscripcion) {
            await desactivarPush();
        } else {
            await activarPush();
        }
    });
}

// ── Inicializar al cargar la página ─────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    inicializarToggle().catch((err) => {
        console.warn('[PUSH] Error al inicializar toggle:', err);
    });
});
