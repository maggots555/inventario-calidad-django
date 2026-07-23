"use strict";
/**
 * Scanner universal (cámara): QR, Data Matrix y barras 1D.
 *
 * Objetivo de negocio:
 * Abrir un modal con la cámara, detectar códigos y escribir el valor en un input
 * (p. ej. número de cargador en Garantía Dell).
 *
 * Dependencia única (CDN):
 * - zxing-wasm 3.1.x (zxing-cpp en WebAssembly) → Data Matrix, QR, Code 128/39, EAN, UPC…
 *
 * Por qué no Quagga / jsQR:
 * - QuaggaJS 0.12 (2017) y jsQR 1.4 están congelados; Quagga solo 1D.
 * - zxing-wasm es el motor open-source actual más preciso (probado con etiqueta Dell).
 *
 * Efectos secundarios:
 * - Solicita permiso de cámara (getUserMedia)
 * - Inyecta un modal Bootstrap en el DOM si no existe
 * - Al detectar: llena el input, dispara evento `input` y cierra el modal
 */
/** true cuando el módulo WASM ya se precalentó (evita demora en el 1er frame) */
let zxingWasmListo = false;
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
/**
 * Intervalo del loop de detección (ms).
 * EXPLICACIÓN PARA PRINCIPIANTES: si analizamos cada frame a tope, el hilo
 * principal se satura y el video se ve a tirones. ~150 ms deja aire al preview.
 */
const INTERVALO_DETECCION_MS = 150;
/**
 * Tope del canvas de análisis (lado en px).
 * Data Matrix densos (cargador Dell) necesitan más píxeles que un QR simple;
 * 640 equilibra lectura vs fluidez.
 */
const MAX_LADO_ANALISIS_PX = 640;
/** Factor de ampliación del recorte central (antes de aplicar el tope) */
const FACTOR_ZOOM_RECORTE = 2.4;
/** Ancho máx. del escaneo “frame completo” de respaldo */
const MAX_ANCHO_FRAME_COMPLETO = 640;
/** Formatos que pedimos a zxing-wasm (prioridad de negocio: Dell + inventario). */
const FORMATOS_SCANNER = [
    'DataMatrix',
    'QRCode',
    'Code128',
    'Code39',
    'EAN13',
    'EAN8',
    'UPCA',
    'UPCE',
    'Codabar',
];
/**
 * Traduce el nombre técnico del formato a texto legible en español.
 */
function etiquetaFormato(formato) {
    const mapa = {
        DataMatrix: 'Data Matrix',
        QRCode: 'Código QR',
        QRCodeModel1: 'Código QR',
        QRCodeModel2: 'Código QR',
        Code128: 'Código de barras',
        Code39: 'Código de barras',
        EAN13: 'Código de barras',
        EAN8: 'Código de barras',
        UPCA: 'Código de barras',
        UPCE: 'Código de barras',
        Codabar: 'Código de barras',
    };
    return mapa[formato] || formato || 'Código';
}
const sesion = {
    activa: false,
    video: null,
    canvas: null,
    canvasCtx: null,
    intervaloQr: null,
    analizandoFrame: false,
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
            <strong>Consejo:</strong> las etiquetas de cargador Dell suelen ser
            <em>Data Matrix</em> (cuadrado sin los 3 ojos de un QR). Acerca el código
            hasta que llene casi todo el marco; buena luz y mano firme ayudan.
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
          <li>Acerca el código hasta que ocupe casi todo el marco azul.</li>
          <li>En cargadores Dell el código es <strong>Data Matrix</strong> (no QR):
              se ve como una cuadrícula densa, sin 3 cuadritos grandes en las esquinas.</li>
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
 * Prepara el <video> visible y un <canvas> oculto para el análisis.
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
function obtenerZXingWasm() {
    const w = window;
    return w.ZXingWASM || null;
}
/**
 * Descarga/compila el WASM de zxing-cpp al abrir el modal (antes del 1er frame).
 */
async function calentarZxingWasm() {
    const api = obtenerZXingWasm();
    if (!api || zxingWasmListo) {
        return;
    }
    try {
        if (typeof api.prepareZXingModule === 'function') {
            await Promise.resolve(api.prepareZXingModule({ fireImmediately: true }));
        }
        else {
            // Fuerza instancia creando una ImageData mínima
            const dummy = new ImageData(8, 8);
            await api.readBarcodes(dummy, { formats: ['DataMatrix'], maxNumberOfSymbols: 1 });
        }
        zxingWasmListo = true;
    }
    catch (err) {
        // Aunque falle el calentamiento, readBarcodes puede instanciar después
        console.warn('Precalentamiento zxing-wasm:', err);
    }
}
function libreriasScannerDisponibles() {
    return obtenerZXingWasm() !== null;
}
/**
 * Sube contraste en ImageData (copia) para ayudar con poca luz / reflejos.
 * EXPLICACIÓN PARA PRINCIPIANTES: el motor lee mejor blanco/negro “duros”.
 */
function potenciarContrasteImageData(origen) {
    const copia = new ImageData(new Uint8ClampedArray(origen.data), origen.width, origen.height);
    const d = copia.data;
    const factor = 1.45;
    const intercept = 128 * (1 - factor);
    for (let i = 0; i < d.length; i += 4) {
        const gris = 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
        const v = Math.max(0, Math.min(255, factor * gris + intercept));
        d[i] = v;
        d[i + 1] = v;
        d[i + 2] = v;
    }
    return copia;
}
/**
 * Lee códigos con zxing-wasm (Data Matrix, QR y barras 1D en un solo motor).
 * Probado con etiqueta real Dell → "CN01C4XJLOC0056A04CSA02".
 */
async function intentarLeerConZxingWasm(imageData) {
    const api = obtenerZXingWasm();
    if (!api) {
        return null;
    }
    const opciones = {
        tryHarder: true,
        formats: FORMATOS_SCANNER,
        maxNumberOfSymbols: 1,
    };
    try {
        let results = await api.readBarcodes(imageData, opciones);
        if (results.length && results[0].text) {
            return {
                codigo: results[0].text.trim(),
                tipo: etiquetaFormato(results[0].format),
            };
        }
        // Segundo intento: contraste alto (reflejo / poca luz)
        results = await api.readBarcodes(potenciarContrasteImageData(imageData), opciones);
        if (results.length && results[0].text) {
            return {
                codigo: results[0].text.trim(),
                tipo: etiquetaFormato(results[0].format),
            };
        }
    }
    catch (err) {
        console.warn('zxing-wasm lectura:', err);
    }
    return null;
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
    if (caps.zoom && typeof caps.zoom.max === 'number' && caps.zoom.max > 1) {
        const zoomIdeal = Math.min(caps.zoom.max, Math.max(caps.zoom.min || 1, 1.25));
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
 * Dibuja un recorte centrado ampliado y lo pasa a zxing-wasm.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Un solo motor lee Data Matrix (Dell), QR y barras. Antes usábamos 3 librerías
 * (Quagga + jsQR + ZXing JS); ahora todo va por zxing-cpp WASM.
 */
async function escanearRecorteCentralAmpliado(fraccionLado) {
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
    const dest = Math.min(MAX_LADO_ANALISIS_PX, Math.max(360, Math.floor(lado * FACTOR_ZOOM_RECORTE)));
    canvas.width = dest;
    canvas.height = dest;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(video, sx, sy, lado, lado, 0, 0, dest, dest);
    return intentarLeerConZxingWasm(ctx.getImageData(0, 0, dest, dest));
}
/**
 * Escaneo de respaldo: frame reducido.
 */
async function escanearFrameCompleto() {
    const video = sesion.video;
    const canvas = sesion.canvas;
    const ctx = sesion.canvasCtx;
    if (!video || !canvas || !ctx) {
        return null;
    }
    const vw = video.videoWidth;
    const vh = video.videoHeight;
    const escala = vw > MAX_ANCHO_FRAME_COMPLETO ? MAX_ANCHO_FRAME_COMPLETO / vw : 1;
    const dw = Math.floor(vw * escala);
    const dh = Math.floor(vh * escala);
    canvas.width = dw;
    canvas.height = dh;
    ctx.imageSmoothingEnabled = true;
    ctx.drawImage(video, 0, 0, dw, dh);
    return intentarLeerConZxingWasm(ctx.getImageData(0, 0, dw, dh));
}
/**
 * Loop de detección unificado (zxing-wasm), un análisis por tick.
 */
function iniciarLoopDeteccion() {
    if (sesion.intervaloQr !== null) {
        window.clearInterval(sesion.intervaloQr);
    }
    sesion.framesSinExito = 0;
    sesion.analizandoFrame = false;
    if (!obtenerZXingWasm()) {
        console.warn('zxing-wasm no está cargado: el scanner no podrá leer códigos.');
    }
    const fraccionesRecorte = [0.35, 0.48, 0.60];
    let indiceTick = 0;
    sesion.intervaloQr = window.setInterval(() => {
        if (!sesion.activa || !sesion.video) {
            return;
        }
        if (sesion.analizandoFrame) {
            return;
        }
        if (sesion.video.readyState !== sesion.video.HAVE_ENOUGH_DATA) {
            return;
        }
        sesion.analizandoFrame = true;
        const fraccion = fraccionesRecorte[indiceTick % fraccionesRecorte.length];
        const tick = indiceTick;
        indiceTick += 1;
        void (async () => {
            try {
                let leido = await escanearRecorteCentralAmpliado(fraccion);
                if (!leido && tick % 4 === 0) {
                    leido = await escanearFrameCompleto();
                }
                if (leido) {
                    procesarCodigoDetectado(leido.codigo, leido.tipo);
                    return;
                }
                sesion.framesSinExito += 1;
            }
            finally {
                sesion.analizandoFrame = false;
            }
        })();
    }, INTERVALO_DETECCION_MS);
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
 * Libera cámara, intervalos y canvas oculto.
 */
function detenerScannerCodigo() {
    sesion.activa = false;
    limpiarTimersFeedback();
    ocultarTipsSinDeteccion();
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
    sesion.analizandoFrame = false;
}
/**
 * Arranca getUserMedia + loop zxing-wasm dentro del modal ya visible.
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
        mostrarEstadoScanner('error', 'Falta zxing-wasm (motor del scanner). Recarga la página o revisa tu conexión al CDN.');
        return;
    }
    void calentarZxingWasm();
    try {
        prepararVideoYCanvas();
        if (!sesion.video) {
            throw new Error('No se pudo crear el elemento de video.');
        }
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // 1280×720 se ve fluido en tablets; el recorte central ampliado aporta detalle.
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: { ideal: 'environment' },
                width: { ideal: 1280, max: 1280 },
                height: { ideal: 720, max: 720 },
                frameRate: { ideal: 30, max: 30 },
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
        // Un solo motor (zxing-wasm) para Data Matrix, QR y barras
        iniciarLoopDeteccion();
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
            // Fallback: constraints estrictas fallaron → pedir sin max
            await iniciarSesionCamaraFallback();
        }
        else {
            mostrarEstadoScanner('error', `Error del scanner: ${err.message || 'desconocido'}`);
        }
    }
}
/**
 * Segunda oportunidad si el dispositivo no acepta 1280×720 exacto.
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
        iniciarLoopDeteccion();
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
    // Precalentar WASM cuanto antes (mientras abre el modal)
    void calentarZxingWasm();
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