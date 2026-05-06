"use strict";
// ============================================================================
// VIDEO RESUMEN DE GALERÍA — Ken Burns + Xfade + Música de fondo
// Versión 1.0 — Mayo 2026
// ============================================================================
/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 *
 * Este módulo controla la sección "Video Resumen" en detalle_orden.html.
 * Como el video se genera con FFmpeg (proceso pesado), usamos Celery:
 *
 * Flujo completo:
 * 1. El técnico hace clic en "Generar Video Resumen"
 * 2. Este script hace un POST a /ordenes/<id>/video-resumen/generar/
 * 3. Django encola la tarea en Celery y devuelve un task_id
 * 4. Este script consulta el estado cada POLLING_INTERVAL ms usando GET
 * 5. Cuando el estado es SUCCESS: muestra el video player y botón de descarga
 * 6. Cuando el estado es FAILURE: muestra el mensaje de error
 *
 * Estados Celery que manejamos:
 *   PENDING  → "En cola…"
 *   STARTED  → "Procesando con FFmpeg…"
 *   SUCCESS  → Video listo, mostrar player
 *   FAILURE  → Error, mostrar mensaje
 */
// ============================================================================
// CONSTANTES DE CONFIGURACIÓN
// ============================================================================
/** Intervalo de polling en milisegundos (3 segundos) */
const POLLING_INTERVAL = 3000;
/** Tiempo máximo de polling antes de dar timeout al usuario (20 minutos) */
const MAX_POLLING_TIME_MS = 20 * 60 * 1000;
// ============================================================================
// ESTADO DEL MÓDULO
// ============================================================================
/** ID del intervalo de polling activo (para poder detenerlo) */
let pollingIntervalId = null;
/** Timestamp de inicio del polling (para calcular timeout) */
let pollingStartTime = 0;
// ============================================================================
// FUNCIÓN PRINCIPAL DE INICIALIZACIÓN
// ============================================================================
/**
 * Inicializa todos los listeners del módulo de video resumen.
 * Se ejecuta cuando el DOM está listo.
 */
function inicializarVideoResumen() {
    const btnGenerar = document.getElementById('btn-generar-video-resumen');
    const btnRegenerar = document.getElementById('btn-regenerar-video-resumen');
    if (btnGenerar) {
        btnGenerar.addEventListener('click', manejarClickGenerar);
    }
    if (btnRegenerar) {
        btnRegenerar.addEventListener('click', manejarClickGenerar);
    }
}
// ============================================================================
// MANEJADORES DE EVENTOS
// ============================================================================
/**
 * Maneja el clic en los botones "Generar" / "Regenerar".
 * Valida, muestra confirmación si aplica, y lanza la generación.
 */
async function manejarClickGenerar(event) {
    const btn = event.currentTarget;
    const ordenId = btn.dataset.ordenId;
    const urlGenerar = btn.dataset.urlGenerar;
    const tieneVideoExistente = btn.dataset.tieneVideo === 'true';
    if (!ordenId || !urlGenerar) {
        mostrarError('Configuración incorrecta del botón. Recarga la página.');
        return;
    }
    // Si ya hay un video, pedir confirmación antes de regenerar
    if (tieneVideoExistente) {
        const confirmar = confirm('¿Deseas regenerar el video resumen?\n\n' +
            'El video anterior será reemplazado por uno nuevo con las fotos actuales.\n' +
            'Este proceso puede tardar varios minutos.');
        if (!confirmar)
            return;
    }
    await lanzarGeneracion(parseInt(ordenId), urlGenerar);
}
// ============================================================================
// LÓGICA DE GENERACIÓN Y POLLING
// ============================================================================
/**
 * Hace el POST para encolar la tarea y comienza el polling.
 *
 * @param ordenId - ID de la OrdenServicio
 * @param urlGenerar - URL del endpoint POST de generación
 */
async function lanzarGeneracion(ordenId, urlGenerar) {
    var _a;
    // Mostrar el estado "generando"
    mostrarEstadoGenerando();
    try {
        // Obtener el CSRF token de la cookie (Django requiere esto en POSTs)
        const csrfToken = obtenerCsrfToken();
        const respuesta = await fetch(urlGenerar, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'X-Requested-With': 'XMLHttpRequest',
            },
        });
        const datos = await respuesta.json();
        if (!datos.success || !datos.task_id) {
            mostrarError(datos.error || 'No se pudo iniciar la generación del video.');
            return;
        }
        // Tarea encolada correctamente — comenzar polling
        const nFotos = (_a = datos.n_fotos) !== null && _a !== void 0 ? _a : 0;
        actualizarMensajeGenerando(nFotos);
        iniciarPolling(datos.task_id);
    }
    catch (err) {
        mostrarError('Error de conexión. Verifica tu internet e intenta de nuevo.');
        console.error('[VideoResumen] Error en lanzarGeneracion:', err);
    }
}
/**
 * Inicia el polling periódico para consultar el estado de la tarea Celery.
 *
 * @param taskId - ID de la tarea Celery a consultar
 */
function iniciarPolling(taskId) {
    // Detener polling anterior si existe
    detenerPolling();
    pollingStartTime = Date.now();
    pollingIntervalId = setInterval(async () => {
        // Verificar timeout
        if (Date.now() - pollingStartTime > MAX_POLLING_TIME_MS) {
            detenerPolling();
            mostrarError('El proceso tardó demasiado. Es posible que el video se esté procesando. ' +
                'Recarga la página en unos minutos para verificar.');
            return;
        }
        await consultarEstado(taskId);
    }, POLLING_INTERVAL);
}
/**
 * Detiene el polling activo.
 */
function detenerPolling() {
    if (pollingIntervalId !== null) {
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }
}
/**
 * Consulta el estado de la tarea Celery y actualiza la UI.
 *
 * @param taskId - ID de la tarea a consultar
 */
async function consultarEstado(taskId) {
    var _a, _b, _c, _d;
    // La URL de estado se construye desde el atributo data del contenedor
    const contenedor = document.getElementById('video-resumen-contenedor');
    const urlEstadoBase = contenedor === null || contenedor === void 0 ? void 0 : contenedor.dataset.urlEstado;
    if (!urlEstadoBase)
        return;
    const urlEstado = urlEstadoBase.replace('TASK_ID_PLACEHOLDER', taskId);
    try {
        const respuesta = await fetch(urlEstado, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });
        const datos = await respuesta.json();
        // Actualizar mensaje según estado
        actualizarEstadoGenerando(datos.estado);
        if (datos.listo) {
            detenerPolling();
            if (datos.estado === 'SUCCESS' && datos.video_url) {
                mostrarVideoListo(datos.video_url, (_a = datos.thumbnail_url) !== null && _a !== void 0 ? _a : null, (_b = datos.video_id) !== null && _b !== void 0 ? _b : 0, (_c = datos.n_fotos) !== null && _c !== void 0 ? _c : 0, (_d = datos.tamano_mb) !== null && _d !== void 0 ? _d : 0);
            }
            else {
                mostrarError(datos.error || 'Error desconocido al generar el video.');
            }
        }
    }
    catch (err) {
        // Error de red — no detenemos el polling, puede ser transitorio
        console.warn('[VideoResumen] Error al consultar estado (reintentando):', err);
    }
}
// ============================================================================
// MANIPULACIÓN DE LA UI
// ============================================================================
/**
 * Oculta el botón de generar y muestra el panel de "generando".
 */
function mostrarEstadoGenerando() {
    const panelBotones = document.getElementById('vr-panel-botones');
    const panelGenerando = document.getElementById('vr-panel-generando');
    const panelVideo = document.getElementById('vr-panel-video');
    const panelError = document.getElementById('vr-panel-error');
    if (panelBotones)
        panelBotones.classList.add('d-none');
    if (panelGenerando)
        panelGenerando.classList.remove('d-none');
    if (panelVideo)
        panelVideo.classList.add('d-none');
    if (panelError)
        panelError.classList.add('d-none');
}
/**
 * Actualiza el mensaje de estado mientras se genera el video.
 *
 * @param nFotos - Número de fotos que se están procesando
 */
function actualizarMensajeGenerando(nFotos) {
    const el = document.getElementById('vr-msg-generando');
    if (el) {
        el.textContent = `Procesando ${nFotos} fotos con efecto Ken Burns y transiciones...`;
    }
}
/**
 * Actualiza el texto de estado según el estado Celery actual.
 *
 * @param estado - Estado actual de la tarea ('PENDING', 'STARTED', etc.)
 */
function actualizarEstadoGenerando(estado) {
    var _a;
    const el = document.getElementById('vr-estado-celery');
    if (!el)
        return;
    const mensajes = {
        'PENDING': 'En cola, esperando worker disponible...',
        'STARTED': 'FFmpeg procesando: aplicando efecto Ken Burns y transiciones...',
        'RETRY': 'Reintentando después de un error transitorio...',
    };
    el.textContent = (_a = mensajes[estado]) !== null && _a !== void 0 ? _a : `Estado: ${estado}`;
}
/**
 * Muestra el video player con el video generado.
 *
 * @param videoUrl - URL del archivo MP4
 * @param thumbUrl - URL del thumbnail (puede ser null)
 * @param videoId - ID del VideoOrden en la BD
 * @param nFotos - Número de fotos procesadas
 * @param tamanMb - Tamaño del video en MB
 */
function mostrarVideoListo(videoUrl, thumbUrl, videoId, nFotos, tamanMb) {
    const panelGenerando = document.getElementById('vr-panel-generando');
    const panelVideo = document.getElementById('vr-panel-video');
    const videoEl = document.getElementById('vr-video-player');
    const btnDescargar = document.getElementById('vr-btn-descargar');
    const infoEl = document.getElementById('vr-info-video');
    const btnRegenerar = document.getElementById('btn-regenerar-video-resumen');
    if (panelGenerando)
        panelGenerando.classList.add('d-none');
    if (panelVideo)
        panelVideo.classList.remove('d-none');
    // Configurar el elemento <video>
    if (videoEl) {
        videoEl.src = videoUrl;
        if (thumbUrl)
            videoEl.poster = thumbUrl;
        videoEl.load();
    }
    // Configurar botón de descarga
    if (btnDescargar) {
        btnDescargar.href = videoUrl;
        btnDescargar.download = `video_resumen_${videoId}.mp4`;
    }
    // Mostrar información del video
    if (infoEl) {
        infoEl.textContent = `${nFotos} fotos · ${tamanMb} MB`;
    }
    // Actualizar el botón "Regenerar" para indicar que ya existe un video
    if (btnRegenerar) {
        btnRegenerar.dataset.tieneVideo = 'true';
    }
}
/**
 * Oculta los otros paneles y muestra el mensaje de error.
 *
 * @param mensaje - Descripción del error
 */
function mostrarError(mensaje) {
    const panelBotones = document.getElementById('vr-panel-botones');
    const panelGenerando = document.getElementById('vr-panel-generando');
    const panelError = document.getElementById('vr-panel-error');
    const msgError = document.getElementById('vr-msg-error');
    if (panelGenerando)
        panelGenerando.classList.add('d-none');
    if (panelBotones)
        panelBotones.classList.remove('d-none'); // Mostrar botón de nuevo
    if (panelError)
        panelError.classList.remove('d-none');
    if (msgError)
        msgError.textContent = mensaje;
}
// ============================================================================
// UTILIDADES
// ============================================================================
/**
 * Obtiene el CSRF token de las cookies de Django.
 * Soporta el nombre personalizado del proyecto (sigma_csrftoken) y el estándar (csrftoken).
 * En producción el proyecto puede usar sigma_csrftoken — igual que en ollama_sic.ts y voz_diagnostico.ts.
 *
 * @returns El valor del CSRF token como string
 */
function obtenerCsrfToken() {
    const cookieNames = ['sigma_csrftoken', 'csrftoken'];
    for (const name of cookieNames) {
        const regex = new RegExp(`(?:^|;\\s*)${name}=([^;]+)`);
        const match = document.cookie.match(regex);
        if (match)
            return decodeURIComponent(match[1]);
    }
    return '';
}
// ============================================================================
// INICIALIZACIÓN AL CARGAR EL DOM
// ============================================================================
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarVideoResumen);
}
else {
    // El DOM ya está listo (script cargado con defer o al final del body)
    inicializarVideoResumen();
}
//# sourceMappingURL=video_resumen.js.map