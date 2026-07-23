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
const sesion = {
    activa: false,
    video: null,
    canvas: null,
    canvasCtx: null,
    intervaloQr: null,
    modalInstancia: null,
    opciones: null,
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
          <div class="scanner-container">
            <div id="${VIDEO_HOST_ID}"></div>
            <div class="scanner-overlay">
              <div class="scanner-frame"></div>
            </div>
          </div>
          <div class="alert alert-info mt-3 mb-0 text-start">
            <i class="bi bi-info-circle" aria-hidden="true"></i>
            Coloca el código dentro del marco. Se detectan QR y códigos de barras
            (Code 128, EAN, UPC, etc.). Requiere HTTPS o localhost.
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
    const ctx = canvas.getContext('2d');
    sesion.video = video;
    sesion.canvas = canvas;
    sesion.canvasCtx = ctx;
}
function libreriasScannerDisponibles() {
    return typeof Quagga !== 'undefined' && typeof jsQR === 'function';
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
                width: { ideal: 640 },
                height: { ideal: 480 },
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
            patchSize: 'medium',
            halfSample: true,
        },
        numOfWorkers: 2,
        frequency: 10,
        debug: false,
    }, (err) => {
        if (err) {
            console.error('Error Quagga:', err);
            return;
        }
        Quagga.start();
    });
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Quagga dispara onDetected muchas veces; solo aceptamos confianza > 70
    // para evitar lecturas falsas de reflejos o códigos a medias.
    Quagga.onDetected((result) => {
        const codigo = result.codeResult.code;
        const confianza = result.codeResult.confidence || 0;
        if (confianza > 70) {
            procesarCodigoDetectado(codigo, 'Código de barras');
        }
    });
}
/**
 * Loop de jsQR: cada 100 ms toma un frame del video y busca un QR.
 */
function iniciarJsQr() {
    if (sesion.intervaloQr !== null) {
        window.clearInterval(sesion.intervaloQr);
    }
    sesion.intervaloQr = window.setInterval(() => {
        if (!sesion.activa || !sesion.video || !sesion.canvas || !sesion.canvasCtx) {
            return;
        }
        if (sesion.video.readyState !== sesion.video.HAVE_ENOUGH_DATA) {
            return;
        }
        // Paso 1: copiar el frame actual al canvas oculto
        sesion.canvas.width = sesion.video.videoWidth;
        sesion.canvas.height = sesion.video.videoHeight;
        sesion.canvasCtx.drawImage(sesion.video, 0, 0, sesion.canvas.width, sesion.canvas.height);
        // Paso 2: pedir a jsQR que busque un código en esos píxeles
        const imageData = sesion.canvasCtx.getImageData(0, 0, sesion.canvas.width, sesion.canvas.height);
        const qr = jsQR(imageData.data, imageData.width, imageData.height, {
            inversionAttempts: 'dontInvert',
        });
        if (qr) {
            procesarCodigoDetectado(qr.data, 'Código QR');
        }
    }, 100);
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
        // Preferimos cámara trasera en móviles (facingMode: environment)
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'environment',
                width: { ideal: 1280, min: 640, max: 1920 },
                height: { ideal: 720, min: 480, max: 1080 },
                aspectRatio: { ideal: 16 / 9 },
                frameRate: { ideal: 30, min: 15 },
            },
        });
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
        mostrarEstadoScanner('success', 'Scanner activo — enfoca el código hacia la cámara');
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
        else {
            mostrarEstadoScanner('error', `Error del scanner: ${err.message || 'desconocido'}`);
        }
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