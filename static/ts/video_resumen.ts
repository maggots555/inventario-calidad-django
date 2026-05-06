// ============================================================================
// VIDEO RESUMEN DE GALERÍA — Ken Burns + Xfade + Música de fondo
// Versión 2.0 — Mayo 2026
// ============================================================================

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 *
 * Este módulo controla la sección "Video Resumen" en detalle_orden.html.
 * Maneja DOS flujos Celery independientes:
 *
 * FLUJO 1 — GENERACIÓN (Ken Burns + xfade):
 *   Click "Generar/Regenerar" → POST generar/ → polling estado/ → mostrar player
 *
 * FLUJO 2 — DESCARGA COMPRIMIDA (CRF 28 para menor peso):
 *   Click "Descargar comprimido" → POST comprimir/ → polling compresion/estado/
 *   → SUCCESS → window.location.href = url (el navegador descarga automáticamente)
 *
 * Estados Celery manejados en ambos flujos:
 *   PENDING  → "En cola…"
 *   STARTED  → "Procesando con FFmpeg…"
 *   SUCCESS  → Resultado listo
 *   FAILURE  → Error, mostrar mensaje
 */

// ============================================================================
// CONSTANTES DE CONFIGURACIÓN
// ============================================================================

/** Intervalo de polling en milisegundos (3 segundos) */
const POLLING_INTERVAL = 3000;

/** Tiempo máximo de polling antes de mostrar timeout (20 minutos) */
const MAX_POLLING_TIME_MS = 20 * 60 * 1000;

// ============================================================================
// ESTADO DEL MÓDULO — Flujo de generación
// ============================================================================

/** ID del intervalo de polling de generación activo */
let pollingIntervalId: ReturnType<typeof setInterval> | null = null;

/** Timestamp de inicio del polling de generación */
let pollingStartTime: number = 0;

// ============================================================================
// ESTADO DEL MÓDULO — Flujo de descarga/compresión
// ============================================================================

/** ID del intervalo de polling de compresión activo */
let pollingCompresionId: ReturnType<typeof setInterval> | null = null;

/** Timestamp de inicio del polling de compresión */
let pollingCompresionStart: number = 0;

// ============================================================================
// INICIALIZACIÓN
// ============================================================================

/**
 * Inicializa todos los listeners del módulo.
 * Se ejecuta cuando el DOM está listo.
 */
function inicializarVideoResumen(): void {
    const btnGenerar   = document.getElementById('btn-generar-video-resumen') as HTMLButtonElement | null;
    const btnRegenerar = document.getElementById('btn-regenerar-video-resumen') as HTMLButtonElement | null;
    const btnDescargar = document.getElementById('vr-btn-descargar') as HTMLButtonElement | null;

    if (btnGenerar)   btnGenerar.addEventListener('click', manejarClickGenerar);
    if (btnRegenerar) btnRegenerar.addEventListener('click', manejarClickGenerar);
    if (btnDescargar) btnDescargar.addEventListener('click', manejarClickDescargar);
}

// ============================================================================
// FLUJO 1: GENERACIÓN DEL VIDEO RESUMEN
// ============================================================================

/**
 * Maneja el clic en "Generar" / "Regenerar".
 */
async function manejarClickGenerar(event: MouseEvent): Promise<void> {
    const btn = event.currentTarget as HTMLButtonElement;
    const ordenId    = btn.dataset.ordenId;
    const urlGenerar = btn.dataset.urlGenerar;
    const tieneVideo = btn.dataset.tieneVideo === 'true';

    if (!ordenId || !urlGenerar) {
        mostrarError('Configuración incorrecta del botón. Recarga la página.');
        return;
    }

    if (tieneVideo) {
        const ok = confirm(
            '¿Deseas regenerar el video resumen?\n\n' +
            'El video anterior será reemplazado por uno nuevo con las fotos actuales.\n' +
            'Este proceso puede tardar varios minutos.'
        );
        if (!ok) return;
    }

    await lanzarGeneracion(parseInt(ordenId), urlGenerar);
}

/**
 * Encola la tarea de generación e inicia el polling.
 */
async function lanzarGeneracion(ordenId: number, urlGenerar: string): Promise<void> {
    mostrarEstadoGenerando();

    try {
        const respuesta = await fetch(urlGenerar, {
            method: 'POST',
            headers: {
                'X-CSRFToken': obtenerCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
        });

        const datos = await respuesta.json() as {
            success: boolean;
            task_id?: string;
            n_fotos?: number;
            error?: string;
        };

        if (!datos.success || !datos.task_id) {
            mostrarError(datos.error || 'No se pudo iniciar la generación del video.');
            return;
        }

        actualizarMensajeGenerando(datos.n_fotos ?? 0);
        iniciarPollingGeneracion(datos.task_id);

    } catch (err) {
        mostrarError('Error de conexión. Verifica tu internet e intenta de nuevo.');
        console.error('[VideoResumen] Error en lanzarGeneracion:', err);
    }
}

/**
 * Inicia el polling periódico del flujo de generación.
 */
function iniciarPollingGeneracion(taskId: string): void {
    detenerPollingGeneracion();
    pollingStartTime = Date.now();

    pollingIntervalId = setInterval(async () => {
        if (Date.now() - pollingStartTime > MAX_POLLING_TIME_MS) {
            detenerPollingGeneracion();
            mostrarError(
                'El proceso tardó demasiado. Recarga la página en unos minutos para verificar.'
            );
            return;
        }
        await consultarEstadoGeneracion(taskId);
    }, POLLING_INTERVAL);
}

function detenerPollingGeneracion(): void {
    if (pollingIntervalId !== null) {
        clearInterval(pollingIntervalId);
        pollingIntervalId = null;
    }
}

/**
 * Consulta el estado de la tarea de generación y actualiza la UI.
 */
async function consultarEstadoGeneracion(taskId: string): Promise<void> {
    const contenedor   = document.getElementById('video-resumen-contenedor');
    const urlBase      = contenedor?.dataset.urlEstado;
    if (!urlBase) return;

    const url = urlBase.replace('TASK_ID_PLACEHOLDER', taskId);

    try {
        const respuesta = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });

        const datos = await respuesta.json() as {
            estado: string;
            listo: boolean;
            video_url?: string;
            thumbnail_url?: string;
            video_id?: number;
            n_fotos?: number;
            tamano_mb?: number;
            error?: string;
        };

        actualizarEstadoGenerando(datos.estado);

        if (datos.listo) {
            detenerPollingGeneracion();

            if (datos.estado === 'SUCCESS' && datos.video_url) {
                mostrarVideoListo(
                    datos.video_url,
                    datos.thumbnail_url ?? null,
                    datos.video_id ?? 0,
                    datos.n_fotos ?? 0,
                    datos.tamano_mb ?? 0,
                );
            } else {
                mostrarError(datos.error || 'Error desconocido al generar el video.');
            }
        }

    } catch (err) {
        console.warn('[VideoResumen] Error consultando generación (reintentando):', err);
    }
}

// ============================================================================
// FLUJO 2: DESCARGA COMPRIMIDA
// ============================================================================

/**
 * Maneja el clic en "Descargar comprimido".
 * Encola la tarea Celery de compresión y muestra el spinner en el botón.
 */
async function manejarClickDescargar(event: MouseEvent): Promise<void> {
    const btn          = event.currentTarget as HTMLButtonElement;
    const urlComprimir = btn.dataset.urlComprimir;

    if (!urlComprimir) {
        console.warn('[VideoResumen] Botón de descarga sin data-url-comprimir');
        return;
    }

    // Si ya está comprimiendo, ignorar el clic
    if (btn.disabled) return;

    await lanzarCompresion(btn, urlComprimir);
}

/**
 * Encola la tarea de compresión e inicia el polling de descarga.
 *
 * @param btn          - El botón que disparó el evento (para actualizar su estado)
 * @param urlComprimir - URL del endpoint POST de compresión
 */
async function lanzarCompresion(btn: HTMLButtonElement, urlComprimir: string): Promise<void> {
    // Poner el botón en estado "comprimiendo"
    setBtnDescargaEstado(btn, 'comprimiendo');

    try {
        const respuesta = await fetch(urlComprimir, {
            method: 'POST',
            headers: {
                'X-CSRFToken': obtenerCsrfToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
        });

        const datos = await respuesta.json() as {
            success: boolean;
            task_id?: string;
            tamano_original_mb?: number;
            error?: string;
        };

        if (!datos.success || !datos.task_id) {
            setBtnDescargaEstado(btn, 'error');
            console.error('[VideoResumen] Error al encolar compresión:', datos.error);
            return;
        }

        iniciarPollingCompresion(btn, datos.task_id);

    } catch (err) {
        setBtnDescargaEstado(btn, 'error');
        console.error('[VideoResumen] Error de red al encolar compresión:', err);
    }
}

/**
 * Inicia el polling periódico del flujo de compresión/descarga.
 *
 * @param btn    - Referencia al botón (para restaurar su estado al terminar)
 * @param taskId - ID de la tarea Celery de compresión
 */
function iniciarPollingCompresion(btn: HTMLButtonElement, taskId: string): void {
    detenerPollingCompresion();
    pollingCompresionStart = Date.now();

    pollingCompresionId = setInterval(async () => {
        if (Date.now() - pollingCompresionStart > MAX_POLLING_TIME_MS) {
            detenerPollingCompresion();
            setBtnDescargaEstado(btn, 'error');
            return;
        }
        await consultarEstadoCompresion(btn, taskId);
    }, POLLING_INTERVAL);
}

function detenerPollingCompresion(): void {
    if (pollingCompresionId !== null) {
        clearInterval(pollingCompresionId);
        pollingCompresionId = null;
    }
}

/**
 * Consulta el estado de la tarea de compresión.
 * Cuando termina con SUCCESS: dispara la descarga automáticamente.
 *
 * @param btn    - Botón de descarga (para actualizar su estado)
 * @param taskId - ID de la tarea Celery
 */
async function consultarEstadoCompresion(btn: HTMLButtonElement, taskId: string): Promise<void> {
    const contenedor = document.getElementById('video-resumen-contenedor');
    const urlBase    = contenedor?.dataset.urlCompresionEstado;
    if (!urlBase) return;

    const url = urlBase.replace('TASK_ID_PLACEHOLDER', taskId);

    try {
        const respuesta = await fetch(url, {
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
        });

        const datos = await respuesta.json() as {
            estado: string;
            listo: boolean;
            video_url?: string;
            tamano_final_mb?: number;
            tamano_original_mb?: number;
            error?: string;
        };

        if (!datos.listo) return;

        detenerPollingCompresion();

        if (datos.estado === 'SUCCESS' && datos.video_url) {
            // Restaurar el botón
            setBtnDescargaEstado(btn, 'listo');
            // Disparar descarga automáticamente: crea un <a> invisible y lo clickea
            const a = document.createElement('a');
            a.href     = datos.video_url;
            a.download = 'video_resumen_comprimido.mp4';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        } else {
            setBtnDescargaEstado(btn, 'error');
            console.error('[VideoResumen] Compresión fallida:', datos.error);
        }

    } catch (err) {
        console.warn('[VideoResumen] Error consultando compresión (reintentando):', err);
    }
}

/**
 * Actualiza el estado visual del botón de descarga.
 *
 * @param btn    - El botón a actualizar
 * @param estado - 'listo' | 'comprimiendo' | 'error'
 */
function setBtnDescargaEstado(
    btn: HTMLButtonElement,
    estado: 'listo' | 'comprimiendo' | 'error'
): void {
    const icono  = btn.querySelector('#vr-btn-descargar-icon') as HTMLElement | null;
    const texto  = btn.querySelector('#vr-btn-descargar-texto') as HTMLElement | null;

    if (estado === 'comprimiendo') {
        btn.disabled = true;
        btn.classList.remove('btn-outline-primary', 'btn-outline-danger');
        btn.classList.add('btn-outline-secondary');
        if (icono) { icono.className = 'spinner-border spinner-border-sm me-1'; }
        if (texto) texto.textContent = 'Comprimiendo...';

    } else if (estado === 'listo') {
        btn.disabled = false;
        btn.classList.remove('btn-outline-secondary', 'btn-outline-danger');
        btn.classList.add('btn-outline-primary');
        if (icono) { icono.className = 'bi bi-download me-1'; }
        if (texto) texto.textContent = 'Descargar comprimido';

    } else { // error
        btn.disabled = false;
        btn.classList.remove('btn-outline-secondary', 'btn-outline-primary');
        btn.classList.add('btn-outline-danger');
        if (icono) { icono.className = 'bi bi-exclamation-triangle me-1'; }
        if (texto) texto.textContent = 'Error — reintentar';
    }
}

// ============================================================================
// MANIPULACIÓN DE LA UI — Flujo de generación
// ============================================================================

function mostrarEstadoGenerando(): void {
    const panelBotones  = document.getElementById('vr-panel-botones');
    const panelGenerando = document.getElementById('vr-panel-generando');
    const panelVideo    = document.getElementById('vr-panel-video');
    const panelError    = document.getElementById('vr-panel-error');

    if (panelBotones)   panelBotones.classList.add('d-none');
    if (panelGenerando) panelGenerando.classList.remove('d-none');
    if (panelVideo)     panelVideo.classList.add('d-none');
    if (panelError)     panelError.classList.add('d-none');
}

function actualizarMensajeGenerando(nFotos: number): void {
    const el = document.getElementById('vr-msg-generando');
    if (el) el.textContent = `Procesando ${nFotos} fotos con efecto Ken Burns y transiciones...`;
}

function actualizarEstadoGenerando(estado: string): void {
    const el = document.getElementById('vr-estado-celery');
    if (!el) return;

    const mensajes: Record<string, string> = {
        'PENDING': 'En cola, esperando worker disponible...',
        'STARTED': 'FFmpeg procesando: aplicando efecto Ken Burns y transiciones...',
        'RETRY':   'Reintentando después de un error transitorio...',
    };

    el.textContent = mensajes[estado] ?? `Estado: ${estado}`;
}

/**
 * Muestra el player con el video recién generado y configura el botón de descarga.
 */
function mostrarVideoListo(
    videoUrl: string,
    thumbUrl: string | null,
    videoId: number,
    nFotos: number,
    tamanMb: number,
): void {
    const panelGenerando = document.getElementById('vr-panel-generando');
    const panelVideo     = document.getElementById('vr-panel-video');
    const videoEl        = document.getElementById('vr-video-player') as HTMLVideoElement | null;
    const infoEl         = document.getElementById('vr-info-video');
    const btnRegenerar   = document.getElementById('btn-regenerar-video-resumen') as HTMLButtonElement | null;

    if (panelGenerando) panelGenerando.classList.add('d-none');
    if (panelVideo)     panelVideo.classList.remove('d-none');

    if (videoEl) {
        videoEl.src = videoUrl;
        if (thumbUrl) videoEl.poster = thumbUrl;
        videoEl.load();
    }

    if (infoEl) infoEl.textContent = `${nFotos} fotos · ${tamanMb} MB`;

    // Actualizar el botón de descarga con el nuevo video_id y la URL de compresión
    // NOTA: Tras regenerar, el template no se recarga, por eso actualizamos el DOM
    const contenedor = document.getElementById('video-resumen-contenedor');
    const btnDescargar = document.getElementById('vr-btn-descargar') as HTMLButtonElement | null;
    if (btnDescargar && contenedor) {
        // Construir la URL de comprimir con el nuevo video_id
        // La URL base es /servicio-tecnico/video-resumen/<video_id>/comprimir/
        // Tomamos la URL existente y reemplazamos el ID si ya tenía uno,
        // o usamos el patrón del contenedor
        const urlActual = btnDescargar.dataset.urlComprimir ?? '';
        if (urlActual) {
            // Reemplazar el ID numérico en la URL (ej: /video-resumen/123/comprimir/)
            btnDescargar.dataset.urlComprimir = urlActual.replace(/\/\d+\/comprimir\//, `/${videoId}/comprimir/`);
        }
        btnDescargar.dataset.videoId = String(videoId);
        // Actualizar también el data-url-compresion-estado del contenedor no es necesario
        // (usa TASK_ID_PLACEHOLDER, no depende del video_id)
        setBtnDescargaEstado(btnDescargar, 'listo');
    }

    if (btnRegenerar) btnRegenerar.dataset.tieneVideo = 'true';
}

function mostrarError(mensaje: string): void {
    const panelBotones   = document.getElementById('vr-panel-botones');
    const panelGenerando = document.getElementById('vr-panel-generando');
    const panelError     = document.getElementById('vr-panel-error');
    const msgError       = document.getElementById('vr-msg-error');

    if (panelGenerando) panelGenerando.classList.add('d-none');
    if (panelBotones)   panelBotones.classList.remove('d-none');
    if (panelError)     panelError.classList.remove('d-none');
    if (msgError)       msgError.textContent = mensaje;
}

// ============================================================================
// UTILIDADES
// ============================================================================

/**
 * Obtiene el CSRF token de las cookies de Django.
 * Soporta sigma_csrftoken (producción) y csrftoken (desarrollo).
 * Mismo patrón que ollama_sic.ts y voz_diagnostico.ts.
 */
function obtenerCsrfToken(): string {
    const cookieNames: string[] = ['sigma_csrftoken', 'csrftoken'];
    for (const name of cookieNames) {
        const regex: RegExp = new RegExp(`(?:^|;\\s*)${name}=([^;]+)`);
        const match: RegExpMatchArray | null = document.cookie.match(regex);
        if (match) return decodeURIComponent(match[1]);
    }
    return '';
}

// ============================================================================
// ARRANQUE
// ============================================================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarVideoResumen);
} else {
    inicializarVideoResumen();
}
