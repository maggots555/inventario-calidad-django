"use strict";
/// <reference lib="webworker" />
/**
 * La directiva anterior incluye los tipos de WebWorker/ServiceWorker.
 * IMPORTANTE: Los Service Workers NO son módulos ES (no usan import/export),
 * por eso usamos esta directiva en lugar de importar tipos.
 *
 * EXPLICACIÓN para el alias `sw`:
 * TypeScript infiere `self` como `Window` cuando hay ambigüedad entre
 * el lib DOM y el lib WebWorker. Para evitar ese conflicto usamos un
 * alias explícito con el tipo correcto:
 *   const sw = self as unknown as ServiceWorkerGlobalScope;
 * Así TypeScript sabe exactamente qué métodos y eventos están disponibles.
 */
/**
 * Service Worker — SIGMA PWA
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Un Service Worker es un script que el navegador ejecuta en segundo plano,
 * completamente separado de la página web. Actúa como un "proxy" entre
 * tu aplicación y la red: intercepta cada petición (fetch) y decide
 * si responde con datos del caché o va a la red.
 *
 * ¿Por qué aquí no hay `window` ni `document`?
 * Porque el SW corre fuera del contexto del navegador. En lugar de esos
 * objetos, tenemos `self` (que es ServiceWorkerGlobalScope), `caches`,
 * `FetchEvent`, `ExtendableEvent`, etc.
 *
 * Ciclo de vida de un Service Worker:
 * 1. install  → Se descarga e instala. Aquí precacheamos assets críticos.
 * 2. activate → Se activa (puede reemplazar a un SW anterior). Aquí limpiamos
 *               cachés viejos.
 * 3. fetch    → Intercepta CADA petición HTTP de la app. Aquí aplicamos
 *               las estrategias de caché.
 *
 * Estrategias usadas:
 * ┌─────────────────────┬────────────────────────────────────────────────────┐
 * │ /static/**          │ Cache First: caché → si falla → red → guardar      │
 * │                     │ Ideal para CSS, JS, imágenes (cambian poco)         │
 * ├─────────────────────┼────────────────────────────────────────────────────┤
 * │ Navegación (HTML)   │ Network First: red → si falla → página /offline/   │
 * │                     │ Garantiza contenido fresco, pero con fallback       │
 * ├─────────────────────┼────────────────────────────────────────────────────┤
 * │ APIs / otros        │ Network Only: siempre red, nunca caché              │
 * │                     │ Datos críticos (notificaciones, formularios, etc.)  │
 * └─────────────────────┴────────────────────────────────────────────────────┘
 *
 * NOTA SOBRE ManifestStaticFilesStorage (producción):
 * Django en producción renombra los archivos con un hash: base.abc123.css
 * Por eso NO hardcodeamos rutas de CSS/JS en el precache. En su lugar,
 * usamos "caché en tiempo de ejecución" (runtime caching): la primera vez
 * que el navegador pide un archivo, el SW lo cachea. Así siempre usamos
 * los nombres correctos sin importar el hash.
 */
// ============================================================================
// ALIAS TIPADO — Resuelve la ambigüedad de tipos en TypeScript
// ============================================================================
/**
 * `self` en un Service Worker es ServiceWorkerGlobalScope, pero TypeScript
 * puede inferirlo como Window cuando hay múltiples libs activas.
 * Este alias fuerza el tipo correcto para que el autocompletado y los
 * chequeos de tipo funcionen correctamente.
 */
const sw = self;
// ============================================================================
// CONFIGURACIÓN
// ============================================================================
/**
 * Versión del caché. Cambiar este string fuerza la eliminación de cachés
 * viejos en el próximo activate. Se recomienda cambiar al hacer un deploy
 * significativo (aunque no es estrictamente necesario — el SW se actualiza
 * automáticamente cuando el archivo JS cambia).
 */
const CACHE_VERSION = 'v1';
/**
 * Nombres de los cachés. Son como "cajones" separados en el almacenamiento
 * del navegador. Tener dos permite invalidarlos de forma independiente.
 */
const STATIC_CACHE_NAME = `sigma-static-${CACHE_VERSION}`; // CSS, JS, imágenes
const OFFLINE_CACHE_NAME = `sigma-offline-${CACHE_VERSION}`; // Página offline
/**
 * Assets que se descargan y cachean inmediatamente al instalar el SW.
 * IMPORTANTE: Solo rutas fijas que NO cambian con ManifestStaticFilesStorage.
 * La página /offline/ es la más crítica: debe estar disponible sin red.
 */
const PRECACHE_URLS = [
    '/offline/', // Página offline personalizada (obligatorio)
    '/static/images/favicon.svg', // Icono de la app
];
/**
 * Prefijos de URL que van a la red y NUNCA al caché.
 * Rutas de datos dinámicos: APIs, notificaciones, admin, auth.
 */
const NETWORK_ONLY_PREFIXES = [
    '/notificaciones/',
    '/sic-gestion-sistema/',
    '/login/',
    '/logout/',
    '/feedback/',
    '/feedback-satisfaccion/',
];
// ============================================================================
// EVENTO: install
// Descarga y guarda los assets críticos al instalar el SW.
// skipWaiting() hace que el nuevo SW tome control inmediatamente,
// sin esperar a que se cierren las pestañas con el SW anterior.
// ============================================================================
sw.addEventListener('install', (event) => {
    event.waitUntil(caches.open(OFFLINE_CACHE_NAME)
        .then((cache) => cache.addAll(PRECACHE_URLS))
        .then(() => sw.skipWaiting()));
});
// ============================================================================
// EVENTO: activate
// Se ejecuta cuando el SW nuevo toma el control.
// Limpia cachés de versiones anteriores para no desperdiciar espacio.
// clients.claim() hace que el SW controle las pestañas abiertas
// inmediatamente, sin necesidad de recargar.
// ============================================================================
sw.addEventListener('activate', (event) => {
    const cachesActuales = new Set([STATIC_CACHE_NAME, OFFLINE_CACHE_NAME]);
    event.waitUntil(caches.keys()
        .then((cacheNames) => Promise.all(cacheNames
        .filter((name) => !cachesActuales.has(name))
        .map((name) => {
        console.log(`[SIGMA SW] Eliminando caché antiguo: ${name}`);
        return caches.delete(name);
    })))
        .then(() => sw.clients.claim()));
});
// ============================================================================
// EVENTO: fetch
// Intercepta CADA petición HTTP de la aplicación.
// ============================================================================
sw.addEventListener('fetch', (event) => {
    const request = event.request;
    const url = new URL(request.url);
    // ── 1. Ignorar peticiones a otros dominios (CDNs, APIs externas) ──
    // No cacheamos Bootstrap CDN, jQuery CDN, etc.
    if (url.origin !== sw.location.origin) {
        return;
    }
    // ── 2. Ignorar métodos que no sean GET ──
    // POST, PUT, DELETE nunca van al caché (son mutaciones de datos).
    if (request.method !== 'GET') {
        return;
    }
    // ── 3. Rutas Network Only — nunca al caché ──
    const esNetworkOnly = NETWORK_ONLY_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
    if (esNetworkOnly) {
        return; // Sin event.respondWith → el navegador maneja normalmente
    }
    // ── 4. Assets estáticos → Cache First ──
    // CSS, JS, imágenes: priorizamos el caché para carga instantánea.
    // Si no está en caché, vamos a la red y lo guardamos para después.
    if (url.pathname.startsWith('/static/')) {
        event.respondWith(estrategiaStaticFirst(request));
        return;
    }
    // ── 5. Navegación (páginas HTML) → Network First con fallback offline ──
    // Para pages HTML siempre intentamos la red primero (contenido fresco).
    // Si no hay conexión, mostramos la página offline personalizada.
    if (request.mode === 'navigate') {
        event.respondWith(estrategiaNavigacion(request));
        return;
    }
    // ── 6. Todo lo demás → Network Only (pasar sin intervenir) ──
    // Por defecto, no interferimos con peticiones que no identificamos.
});
// ============================================================================
// ESTRATEGIAS DE CACHÉ
// ============================================================================
/**
 * Cache First con fallback a red.
 *
 * EXPLICACIÓN:
 * 1. Buscar en el caché → si existe, devolver inmediatamente (carga instantánea).
 * 2. Si NO está en caché → ir a la red → guardar en caché → devolver.
 * 3. Si la red falla y tampoco está en caché → lanzar error (el navegador lo maneja).
 *
 * Ideal para: CSS, JS, imágenes, fuentes — archivos que no cambian frecuentemente.
 */
async function estrategiaStaticFirst(request) {
    const cachedResponse = await caches.match(request);
    if (cachedResponse) {
        return cachedResponse;
    }
    const networkResponse = await fetch(request);
    // Solo cachear respuestas válidas (status 200)
    if (networkResponse.ok) {
        const cache = await caches.open(STATIC_CACHE_NAME);
        // Guardar una copia en caché (clone porque Response solo se puede leer una vez)
        cache.put(request, networkResponse.clone());
    }
    return networkResponse;
}
/**
 * Network First con fallback a página offline.
 *
 * EXPLICACIÓN:
 * 1. Intentar la red primero (siempre queremos contenido actualizado en páginas).
 * 2. Si la red responde → devolver el resultado.
 * 3. Si la red falla (sin conexión) → devolver la página /offline/ del caché.
 *
 * Ideal para: navegación entre páginas HTML de Django.
 */
async function estrategiaNavigacion(request) {
    try {
        const networkResponse = await fetch(request);
        return networkResponse;
    }
    catch {
        // Sin conexión → buscar la página offline en el caché
        console.log('[SIGMA SW] Sin conexión, sirviendo página offline.');
        const offlinePage = await caches.match('/offline/');
        if (offlinePage) {
            return offlinePage;
        }
        // Si por alguna razón offline tampoco está en caché, respuesta mínima
        return new Response('<h1>Sin conexión</h1><p>Por favor verifica tu conexión a internet.</p>', {
            status: 503,
            headers: { 'Content-Type': 'text/html; charset=utf-8' },
        });
    }
}
// ══════════════════════════════════════════════════════════════════════════════
// WEB PUSH — Recibir y mostrar notificaciones
// ══════════════════════════════════════════════════════════════════════════════
/**
 * Evento 'push': se dispara cuando el servidor envía una notificación push.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Cuando Django llama a pywebpush, el navegador entrega el mensaje aquí
 * aunque el usuario no tenga el sitio abierto. El SW es quien recibe
 * el mensaje y llama a showNotification() para que el SO muestre la
 * notificación nativa del dispositivo.
 *
 * El payload que llega es el JSON que mandamos desde push_service.py:
 * { "titulo": "...", "mensaje": "...", "url": "..." }
 */
sw.addEventListener('push', (event) => {
    var _a, _b, _c;
    // Estructura por defecto si el payload viene vacío o malformado
    let titulo = 'SIGMA';
    let mensaje = 'Tienes una nueva notificación.';
    let url = '/';
    if (event.data) {
        try {
            const data = event.data.json();
            titulo = (_a = data.titulo) !== null && _a !== void 0 ? _a : titulo;
            mensaje = (_b = data.mensaje) !== null && _b !== void 0 ? _b : mensaje;
            url = (_c = data.url) !== null && _c !== void 0 ? _c : url;
        }
        catch {
            console.warn('[SIGMA SW] No se pudo parsear el payload push.');
        }
    }
    const opciones = {
        body: mensaje,
        icon: '/static/images/favicon.svg',
        badge: '/static/images/favicon.svg',
        tag: url, // Agrupar notificaciones del mismo url (evita duplicados)
        data: { url }, // Pasar la URL al evento notificationclick
    };
    // waitUntil garantiza que el SW no se duerma antes de mostrar la notificación
    event.waitUntil(sw.registration.showNotification(titulo, opciones));
});
/**
 * Evento 'notificationclick': se dispara cuando el usuario toca la notificación.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Cuando el usuario toca la notificación en su teléfono o computadora,
 * este evento se activa. Aquí decidimos qué hacer:
 * 1. Cerrar la notificación.
 * 2. Si ya hay una pestaña abierta del sitio → enfocarla y navegar.
 * 3. Si no hay pestaña abierta → abrir una nueva.
 */
sw.addEventListener('notificationclick', (event) => {
    var _a, _b;
    event.notification.close();
    const urlDestino = (_b = (_a = event.notification.data) === null || _a === void 0 ? void 0 : _a.url) !== null && _b !== void 0 ? _b : '/';
    event.waitUntil(sw.clients
        .matchAll({ type: 'window', includeUncontrolled: true })
        .then((clientList) => {
        // Buscar una pestaña existente del sitio
        for (const client of clientList) {
            if ('focus' in client) {
                client.navigate(urlDestino);
                return client.focus();
            }
        }
        // No hay pestaña → abrir nueva
        return sw.clients.openWindow(urlDestino);
    }));
});
//# sourceMappingURL=service_worker.js.map