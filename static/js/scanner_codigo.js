"use strict";
/**
 * Scanner universal de códigos QR y de barras (cámara del dispositivo).
 *
 * Objetivo de negocio:
 * Abrir un modal con la cámara, detectar QR (jsQR) o barras (QuaggaJS)
 * y escribir el valor en un input HTML (p. ej. número de cargador en Garantía Dell).
 *
 * Dependencias (CDN en el template, no npm):
 * - QuaggaJS 0.12.x → códigos de barras
 * - jsQR 1.4.x → códigos QR
 *
 * Efectos secundarios:
 * - Solicita permiso de cámara (getUserMedia)
 * - Inyecta un modal Bootstrap en el DOM si no existe
 * - Al detectar: llena el input, dispara evento `input` y cierra el modal
 *
 * Mejoras de precisión (QR pequeños):
 * - Cámara a resolución alta + enfoque continuo si el dispositivo lo permite
 * - Escaneo del centro del marco ampliado 2× (más píxeles por módulo del QR)
 * - inversionAttempts attemptBoth (QR claros/oscuros)
 * - Feedback si pasan varios segundos sin detectar
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Inventario tenía esta lógica duplicada en HTML. Aquí la sacamos a un módulo
 * reutilizable: cualquier página llama `abrirScannerCodigo({ targetInput })`
 * y el código aparece solo en el textbox indicado.
 */
function obtenerBootstrapModal(element) {
    const bs = window.bootstrap;
    return new bs.Modal(element);
}
const MODAL_ID = 'scannerCodigoUniversalModal';
const VIDEO_HOST_ID = 'scannerCodigoVideoHost';
const STATUS_ID = 'scannerCodigoStatus';
const TIPS_ID = 'scannerCodigoTips';
/** Segundos sin detección antes del primer aviso de ayuda */
const SEGUNDOS_ANTES_TIP = 5;
/** Cada cuántos segundos refrescar tips si sigue fallando */
const SEGUNDOS_ENTRE_TIPS = 8;
/** Intervalo del loop jsQR (ms). Un poco más rápido ayuda con QR pequeños. */
const INTERVALO_JSQR_MS = 70;
/** Factor de ampliación del recorte central (2 = el QR se ve el doble de grande en píxeles) */
const FACTOR_ZOOM_RECORTE = 2.2;
const sesion = {
    activa: false,
    video: null,
    canvas: null,
    canvasCtx: null,
    intervaloQr: null,
    timeoutSinDetectar: null,
    intervaloTips: null,
    framesSinExito: 0,
    inicioEscaneoMs: 0,
    modalInstancia: null,
    opciones: null,
    videoTrack: null,
};
/**
 * Garantiza que el modal del scanner exista en el DOM.
 * Si no está (primera vez), lo crea una sola vez y lo reutiliza.
 */
function asegurarModalScanner() {
    let modal = document.getElementById(MODAL_ID);
    if (modal) {
        return modal;
    }
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Creamos el HTML del modal desde JS para no copiarlo en cada template.
    // Bootstrap lo reconoce por las clases `.modal` / `data-bs-dismiss`.
    modal = document.createElement('div');
    modal.id = MODAL_ID;
    modal.className = 'modal fade';
    modal.tabIndex = -1;
    modal.setAttribute('aria-labelledby', 'scannerCodigoUniversalLabel');
    modal.setAttribute('aria-hidden', 'true');
    modal.innerHTML = `
    <div class="modal-dialog modal-lg modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h5 class="modal-title" id="scannerCodigoUniversalLabel">
            <i class="bi bi-camera" aria-hidden="true"></i>
            Scanner QR / código de barras
          </h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Cerrar"></button>
        </div>
        <div class="modal-body text-center">
          <div id="${STATUS_ID}" class="mb-3"></div>
          <div class="scanner-container scanner-container--mejorado">
            <div id="${VIDEO_HOST_ID}"></div>
            <div class="scanner-overlay">
              <div class="scanner-frame scanner-frame--preciso"></div>
            </div>
          </div>
          <div id="${TIPS_ID}" class="mt-3 text-start" hidden></div>
          <div class="alert alert-info mt-3 mb-0 text-start small">
            <i class="bi bi-info-circle" aria-hidden="true"></i>
            <strong>Consejo:</strong> acerca el código hasta que llene casi todo el marco
            (sobre todo si el QR es pequeño). Buena luz y mano firme ayudan.
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
        </div>
      </div>
    </div>
  `;
    document.body.appendChild(modal);
    return modal;
}
function mostrarEstadoScanner(tipo, mensaje) {
    const host = document.getElementById(STATUS_ID);
    if (!host) {
        return;
    }
    const clases = {
        success: 'alert-success',
        warning: 'alert-warning',
        error: 'alert-danger',
        info: 'alert-info',
    };
    host.innerHTML = `<div class="alert ${clases[tipo]} mb-0">${mensaje}</div>`;
}
/**
 * Muestra tips cuando el scanner no logra leer el código.
 * EXPLICACIÓN PARA PRINCIPIANTES: no es un “error fatal”; guía al usuario
 * a acercar el código, mejorar luz o escribir a mano.
 */
function mostrarTipsSinDeteccion(nivel) {
    const tipsHost = document.getElementById(TIPS_ID);
    if (!tipsHost) {
        return;
    }
    tipsHost.hidden = false;
    if (nivel === 'suave') {
        mostrarEstadoScanner('warning', 'Aún no reconozco el código. Acércalo más al marco e inténtalo de nuevo…');
        tipsHost.innerHTML = `
      <div class="alert alert-warning mb-0 text-start">
        <strong><i class="bi bi-exclamation-triangle" aria-hidden="true"></i>
        No se detectó todavía</strong>
        <ul class="mb-0 mt-2 ps-3">
          <li>Acerca el QR/código hasta que ocupe casi todo el marco azul.</li>
          <li>Si el QR es muy pequeño, acércalo más (el zoom digital ayuda).</li>
          <li>Evita reflejos y sombra; busca luz pareja.</li>
          <li>Mantén el dispositivo estable 1–2 segundos.</li>
        </ul>
      </div>`;
        return;
    }
    mostrarEstadoScanner('warning', 'Sigo sin leerlo. Puedes cancelar y escribir el número a mano.');
    tipsHost.innerHTML = `
    <div class="alert alert-warning mb-0 text-start">
      <strong><i class="bi bi-question-circle" aria-hidden="true"></i>
      Sigue sin reconocerse</strong>
      <ul class="mb-0 mt-2 ps-3">
        <li>Prueba otro ángulo o distancia (un poco más cerca suele bastar).</li>
        <li>Limpia la lente si está opaca o con huellas.</li>
        <li>Si el código está dañado o borroso, escríbelo manualmente en el campo.</li>
        <li>Pulsa <em>Cancelar</em> y usa el teclado — no bloqueamos el guardado.</li>
      </ul>
    </div>`;
}
function ocultarTipsSinDeteccion() {
    const tipsHost = document.getElementById(TIPS_ID);
    if (tipsHost) {
        tipsHost.hidden = true;
        tipsHost.innerHTML = '';
    }
}
function limpiarTimersFeedback() {
    if (sesion.timeoutSinDetectar !== null) {
        window.clearTimeout(sesion.timeoutSinDetectar);
        sesion.timeoutSinDetectar = null;
    }
    if (sesion.intervaloTips !== null) {
        window.clearInterval(sesion.intervaloTips);
        sesion.intervaloTips = null;
    }
}
/**
 * Programa avisos si pasan varios segundos sin detectar nada.
 */
function programarFeedbackSinDeteccion() {
    limpiarTimersFeedback();
    sesion.timeoutSinDetectar = window.setTimeout(() => {
        if (!sesion.activa) {
            return;
        }
        mostrarTipsSinDeteccion('suave');
        // Segundo nivel de tips si sigue fallando
        sesion.intervaloTips = window.setInterval(() => {
            if (!sesion.activa) {
                return;
            }
            mostrarTipsSinDeteccion('fuerte');
        }, SEGUNDOS_ENTRE_TIPS * 1000);
    }, SEGUNDOS_ANTES_TIP * 1000);
}
function reproducirBeepConfirmacion() {
    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        const audioContext = new AudioCtx();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();
        oscillator.connect(gainNode);
        gainNode.connect(audioContext.destination);
        oscillator.frequency.value = 800;
        gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.1);
        oscillator.start(audioContext.currentTime);
        oscillator.stop(audioContext.currentTime + 0.1);
    }
    catch {
        // Sin audio no bloqueamos el flujo
    }
}
/**
 * Prepara el <video> visible y un <canvas> oculto para jsQR.
 */
function prepararVideoYCanvas() {
    const host = document.getElementById(VIDEO_HOST_ID);
    if (!host) {
        throw new Error('No se encontró el contenedor de video del scanner.');
    }
    host.innerHTML = '';
    const video = document.createElement('video');
    video.className = 'scanner-video';
    video.setAttribute('autoplay', '');
    video.setAttribute('muted', '');
    video.setAttribute('playsinline', '');
    host.appendChild(video);
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'display:none;position:absolute;top:-9999px;left:-9999px;';
    document.body.appendChild(canvas);
    // willReadFrequently: avisa al navegador que leeremos muchos frames (mejor rendimiento)
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    sesion.video = video;
    sesion.canvas = canvas;
    sesion.canvasCtx = ctx;
}
function libreriasScannerDisponibles() {
    return typeof Quagga !== 'undefined' && typeof jsQR === 'function';
}
/**
 * Intenta activar enfoque continuo / autoenfoque en la pista de video.
 * No todos los dispositivos lo soportan; si falla, seguimos igual.
 */
async function aplicarMejorasEnfoque(track) {
    const caps = track.getCapabilities ? track.getCapabilities() : null;
    if (!caps) {
        return;
    }
    const advanced = [];
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // focusMode continuous = la cámara reenfoca sola al acercar el código.
    if (caps.focusMode && caps.focusMode.includes('continuous')) {
        advanced.push({ focusMode: 'continuous' });
    }
    else if (caps.focusMode && caps.focusMode.includes('single-shot')) {
        advanced.push({ focusMode: 'single-shot' });
    }
    // Un poco de zoom óptico (si existe) acerca QR pequeños sin perder nitidez
    if (caps.zoom && typeof caps.zoom.max === 'number' && caps.zoom.max > 1) {
        const zoomIdeal = Math.min(caps.zoom.max, Math.max(caps.zoom.min || 1, 1.5));
        advanced.push({ zoom: zoomIdeal });
    }
    if (advanced.length === 0) {
        return;
    }
    try {
        await track.applyConstraints({ advanced: advanced });
    }
    catch (err) {
        console.warn('No se pudieron aplicar constraints de enfoque/zoom:', err);
    }
}
/**
 * Inicia QuaggaJS sobre el video ya con stream (códigos de barras).
 */
function iniciarQuagga() {
    if (!sesion.video || typeof Quagga === 'undefined') {
        return;
    }
    Quagga.init({
        inputStream: {
            name: 'Live',
            type: 'LiveStream',
            target: sesion.video,
            constraints: {
                // Resolución más alta que 640×480 mejora códigos finos
                width: { ideal: 1280 },
                height: { ideal: 720 },
            },
            area: {
                // Solo analiza el centro (coincide con el marco visual)
                top: '15%',
                right: '15%',
                left: '15%',
                bottom: '15%',
            },
        },
        decoder: {
            readers: [
                'code_128_reader',
                'ean_reader',
                'ean_8_reader',
                'code_39_reader',
                'upc_reader',
                'upc_e_reader',
                'codabar_reader',
                'i2of5_reader',
            ],
        },
        locator: {
            // patchSize small + sin halfSample = más precisión (un poco más CPU)
            patchSize: 'small',
            halfSample: false,
        },
        numOfWorkers: 2,
        frequency: 8,
        debug: false,
    }, (err) => {
        if (err) {
            console.error('Error Quagga:', err);
            return;
        }
        Quagga.start();
    });
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Quagga dispara onDetected muchas veces; confianza > 55 acepta lecturas
    // un poco más débiles (códigos pequeños) sin ser demasiado permisivo.
    Quagga.onDetected((result) => {
        const codigo = result.codeResult.code;
        const confianza = result.codeResult.confidence || 0;
        if (confianza > 55) {
            procesarCodigoDetectado(codigo, 'Código de barras');
        }
    });
}
/**
 * Ejecuta jsQR sobre ImageData ya preparado.
 * Devuelve el texto del QR o null.
 */
function intentarJsQr(imageData) {
    const qr = jsQR(imageData.data, imageData.width, imageData.height, {
        // attemptBoth: prueba QR normales e invertidos (fondo oscuro / claro)
        inversionAttempts: 'attemptBoth',
    });
    return qr ? qr.data : null;
}
/**
 * Dibuja un recorte centrado del video, ampliado (zoom digital), y lo pasa a jsQR.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Un QR pequeño en la foto completa tiene pocos píxeles por “cuadrito”.
 * Si recortamos el centro y lo agrandamos, esos cuadritos se ven más grandes
 * y jsQR los lee mucho mejor — sin cambiar de cámara.
 *
 * @param fraccionLado - fracción del lado menor del video (0.35–0.7)
 * @returns texto del QR o null
 */
function escanearRecorteCentralAmpliado(fraccionLado) {
    const video = sesion.video;
    const canvas = sesion.canvas;
    const ctx = sesion.canvasCtx;
    if (!video || !canvas || !ctx) {
        return null;
    }
    const vw = video.videoWidth;
    const vh = video.videoHeight;
    if (vw < 40 || vh < 40) {
        return null;
    }
    const lado = Math.floor(Math.min(vw, vh) * fraccionLado);
    const sx = Math.floor((vw - lado) / 2);
    const sy = Math.floor((vh - lado) / 2);
    const dest = Math.floor(lado * FACTOR_ZOOM_RECORTE);
    canvas.width = dest;
    canvas.height = dest;
    // imageSmoothingEnabled false = pixels nítidos al ampliar (mejor para QR)
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(video, sx, sy, lado, lado, 0, 0, dest, dest);
    const imageData = ctx.getImageData(0, 0, dest, dest);
    return intentarJsQr(imageData);
}
/**
 * Escaneo de respaldo: frame completo (QR grandes / ya cercanos).
 */
function escanearFrameCompleto() {
    const video = sesion.video;
    const canvas = sesion.canvas;
    const ctx = sesion.canvasCtx;
    if (!video || !canvas || !ctx) {
        return null;
    }
    const vw = video.videoWidth;
    const vh = video.videoHeight;
    // Límite de píxeles para no saturar CPU en 4K; 1920 de ancho basta
    const maxAncho = 1600;
    const escala = vw > maxAncho ? maxAncho / vw : 1;
    const dw = Math.floor(vw * escala);
    const dh = Math.floor(vh * escala);
    canvas.width = dw;
    canvas.height = dh;
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(video, 0, 0, dw, dh);
    const imageData = ctx.getImageData(0, 0, dw, dh);
    return intentarJsQr(imageData);
}
/**
 * Loop de jsQR: recortes ampliados (QR pequeños) + frame completo.
 */
function iniciarJsQr() {
    if (sesion.intervaloQr !== null) {
        window.clearInterval(sesion.intervaloQr);
    }
    sesion.framesSinExito = 0;
    // Fracciones del centro: más cerrado = más zoom digital sobre QR chicos
    const fraccionesRecorte = [0.42, 0.55, 0.68];
    let indiceFraccion = 0;
    sesion.intervaloQr = window.setInterval(() => {
        if (!sesion.activa || !sesion.video) {
            return;
        }
        if (sesion.video.readyState !== sesion.video.HAVE_ENOUGH_DATA) {
            return;
        }
        // Paso A: recorte central ampliado (prioridad para QR pequeños)
        const fraccion = fraccionesRecorte[indiceFraccion % fraccionesRecorte.length];
        indiceFraccion += 1;
        let codigo = escanearRecorteCentralAmpliado(fraccion);
        // Paso B: cada 3 ticks, también prueba el frame completo
        if (!codigo && indiceFraccion % 3 === 0) {
            codigo = escanearFrameCompleto();
        }
        if (codigo) {
            procesarCodigoDetectado(codigo, 'Código QR');
            return;
        }
        sesion.framesSinExito += 1;
    }, INTERVALO_JSQR_MS);
}
/**
 * Cuando hay detección válida: escribe en el input, avisa y cierra el modal.
 */
function procesarCodigoDetectado(codigo, tipo) {
    if (!sesion.activa || !sesion.opciones) {
        return;
    }
    // Pausar de inmediato para no procesar el mismo código varias veces
    sesion.activa = false;
    limpiarTimersFeedback();
    ocultarTipsSinDeteccion();
    reproducirBeepConfirmacion();
    mostrarEstadoScanner('success', `${tipo} detectado: ${codigo}`);
    const input = sesion.opciones.targetInput;
    input.value = codigo;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    if (sesion.opciones.onDetect) {
        sesion.opciones.onDetect(codigo);
    }
    // Breve pausa para que el usuario vea el mensaje de éxito
    window.setTimeout(() => {
        if (sesion.modalInstancia) {
            sesion.modalInstancia.hide();
        }
        input.focus();
    }, 700);
}
/**
 * Libera cámara, Quagga, intervalos y canvas oculto.
 */
function detenerScannerCodigo() {
    sesion.activa = false;
    limpiarTimersFeedback();
    ocultarTipsSinDeteccion();
    if (typeof Quagga !== 'undefined') {
        try {
            Quagga.offDetected();
            Quagga.stop();
        }
        catch {
            // Quagga puede fallar si nunca arrancó
        }
    }
    if (sesion.intervaloQr !== null) {
        window.clearInterval(sesion.intervaloQr);
        sesion.intervaloQr = null;
    }
    if (sesion.video && sesion.video.srcObject) {
        const stream = sesion.video.srcObject;
        stream.getTracks().forEach((track) => track.stop());
        sesion.video.srcObject = null;
    }
    if (sesion.canvas && sesion.canvas.parentNode) {
        sesion.canvas.parentNode.removeChild(sesion.canvas);
    }
    const host = document.getElementById(VIDEO_HOST_ID);
    if (host) {
        host.innerHTML = '';
    }
    sesion.video = null;
    sesion.canvas = null;
    sesion.canvasCtx = null;
    sesion.videoTrack = null;
    sesion.framesSinExito = 0;
}
/**
 * Arranca getUserMedia + Quagga + jsQR dentro del modal ya visible.
 */
async function iniciarSesionCamara() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        mostrarEstadoScanner('error', 'Tu navegador no soporta acceso a la cámara. Escribe el código manualmente.');
        return;
    }
    const hostOk = location.protocol === 'https:' ||
        location.hostname === 'localhost' ||
        location.hostname === '127.0.0.1';
    if (!hostOk) {
        mostrarEstadoScanner('warning', 'Para usar la cámara necesitas HTTPS (o localhost). Mientras tanto, escribe el código a mano.');
        return;
    }
    if (!libreriasScannerDisponibles()) {
        mostrarEstadoScanner('error', 'Faltan las librerías del scanner (Quagga / jsQR). Recarga la página.');
        return;
    }
    try {
        prepararVideoYCanvas();
        if (!sesion.video) {
            throw new Error('No se pudo crear el elemento de video.');
        }
        // Preferimos cámara trasera + resolución alta (mejor detalle en QR chicos)
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { ideal: 'environment' },
                width: { ideal: 1920, min: 1280 },
                height: { ideal: 1080, min: 720 },
                frameRate: { ideal: 30, min: 15 },
            },
        });
        const track = stream.getVideoTracks()[0] || null;
        sesion.videoTrack = track;
        if (track) {
            await aplicarMejorasEnfoque(track);
        }
        sesion.video.srcObject = stream;
        await new Promise((resolve) => {
            sesion.video.addEventListener('loadedmetadata', () => {
                if (sesion.canvas && sesion.video) {
                    sesion.canvas.width = sesion.video.videoWidth;
                    sesion.canvas.height = sesion.video.videoHeight;
                }
                resolve();
            }, { once: true });
        });
        await sesion.video.play();
        sesion.activa = true;
        sesion.inicioEscaneoMs = Date.now();
        sesion.framesSinExito = 0;
        ocultarTipsSinDeteccion();
        mostrarEstadoScanner('info', 'Scanner activo — acerca el código al marco (sobre todo si es pequeño)');
        programarFeedbackSinDeteccion();
        iniciarQuagga();
        iniciarJsQr();
    }
    catch (error) {
        console.error('Error al iniciar scanner:', error);
        const err = error;
        if (err.name === 'NotAllowedError') {
            mostrarEstadoScanner('error', 'Permisos de cámara denegados. Permite el acceso en el navegador.');
        }
        else if (err.name === 'NotFoundError') {
            mostrarEstadoScanner('error', 'No se encontró cámara en este dispositivo.');
        }
        else if (err.name === 'OverconstrainedError') {
            // Fallback: constraints muy estrictas (1920) fallaron → pedir sin min
            await iniciarSesionCamaraFallback();
        }
        else {
            mostrarEstadoScanner('error', `Error del scanner: ${err.message || 'desconocido'}`);
        }
    }
}
/**
 * Segunda oportunidad si el dispositivo no acepta 1920×1080.
 */
async function iniciarSesionCamaraFallback() {
    try {
        prepararVideoYCanvas();
        if (!sesion.video) {
            throw new Error('No se pudo crear el elemento de video.');
        }
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'environment',
                width: { ideal: 1280 },
                height: { ideal: 720 },
            },
        });
        const track = stream.getVideoTracks()[0] || null;
        sesion.videoTrack = track;
        if (track) {
            await aplicarMejorasEnfoque(track);
        }
        sesion.video.srcObject = stream;
        await new Promise((resolve) => {
            sesion.video.addEventListener('loadedmetadata', () => resolve(), { once: true });
        });
        await sesion.video.play();
        sesion.activa = true;
        sesion.inicioEscaneoMs = Date.now();
        mostrarEstadoScanner('info', 'Scanner activo (resolución estándar) — acerca el código al marco');
        programarFeedbackSinDeteccion();
        iniciarQuagga();
        iniciarJsQr();
    }
    catch (error) {
        console.error('Fallback scanner falló:', error);
        mostrarEstadoScanner('error', 'No se pudo iniciar la cámara. Escribe el código manualmente.');
    }
}
/**
 * API pública: abre el modal del scanner y escribe el resultado en el input.
 *
 * @param opciones - Input destino y callback opcional al detectar
 */
function abrirScannerCodigo(opciones) {
    if (!opciones.targetInput) {
        console.error('abrirScannerCodigo: falta targetInput');
        return;
    }
    sesion.opciones = opciones;
    const modalEl = asegurarModalScanner();
    const titulo = modalEl.querySelector('#scannerCodigoUniversalLabel');
    if (titulo && opciones.tituloModal) {
        titulo.innerHTML = `<i class="bi bi-camera" aria-hidden="true"></i> ${opciones.tituloModal}`;
    }
    const status = document.getElementById(STATUS_ID);
    if (status) {
        status.innerHTML = '';
    }
    ocultarTipsSinDeteccion();
    // Listeners con once para no acumular al abrir varias veces
    modalEl.addEventListener('shown.bs.modal', () => {
        void iniciarSesionCamara();
    }, { once: true });
    modalEl.addEventListener('hidden.bs.modal', () => {
        detenerScannerCodigo();
        sesion.modalInstancia = null;
    }, { once: true });
    sesion.modalInstancia = obtenerBootstrapModal(modalEl);
    sesion.modalInstancia.show();
}
// Exponer en window para que formato_garantia.ts (IIFE) y otras pantallas lo usen
window.abrirScannerCodigo = abrirScannerCodigo;
//# sourceMappingURL=scanner_codigo.js.map