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
/**
 * Intervalo del loop jsQR (ms).
 * EXPLICACIÓN PARA PRINCIPIANTES: si analizamos cada frame a tope, el hilo
 * principal se satura y el video se ve a tirones. ~150 ms ≈ 6–7 lecturas/s,
 * suficiente para detectar y deja aire para pintar la cámara fluido.
 */
const INTERVALO_JSQR_MS = 150;
/**
 * Tope del canvas de análisis (lado en px).
 * Ampliar de más (p. ej. 1000×1000) hace lento a jsQR; 480 mantiene QR chicos
 * legibles sin matar el FPS del preview.
 */
const MAX_LADO_ANALISIS_PX = 480;
/** Factor de ampliación del recorte central (antes de aplicar el tope) */
const FACTOR_ZOOM_RECORTE = 2;
/** Ancho máx. del escaneo “frame completo” de respaldo */
const MAX_ANCHO_FRAME_COMPLETO = 640;
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
    // Un poco de zoom óptico (si existe) acerca QR pequeños sin perder nitidez.
    // Evitamos zoom alto: fuerza reenfoques y se siente “pesado”.
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
 * Inicia QuaggaJS sobre el video ya con stream (códigos de barras).
 * Configuración “ligera”: Quagga es pesado; si lo ponemos a máxima precisión
 * el preview de cámara se traba.
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
            area: {
                // Solo analiza el centro (coincide con el marco visual)
                top: '18%',
                right: '18%',
                left: '18%',
                bottom: '18%',
            },
        },
        decoder: {
            // Menos readers = menos CPU; los más usados en series/inventario
            readers: [
                'code_128_reader',
                'code_39_reader',
                'ean_reader',
                'ean_8_reader',
                'upc_reader',
            ],
        },
        locator: {
            // halfSample true = analiza a la mitad de resolución (mucho más fluido)
            patchSize: 'medium',
            halfSample: true,
        },
        numOfWorkers: 1,
        frequency: 4,
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
 *
 * @param intentarInvertir - si true, prueba también QR invertidos (cuesta más CPU)
 */
function intentarJsQr(imageData, intentarInvertir) {
    const qr = jsQR(imageData.data, imageData.width, imageData.height, {
        // dontInvert es más barato; attemptBoth solo en ticks alternos
        inversionAttempts: intentarInvertir ? 'attemptBoth' : 'dontInvert',
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
 * @param intentarInvertir - modo invertido (más CPU)
 * @returns texto del QR o null
 */
function escanearRecorteCentralAmpliado(fraccionLado, intentarInvertir) {
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
    // Tope de tamaño: precisión OK + video fluido
    const dest = Math.min(MAX_LADO_ANALISIS_PX, Math.max(240, Math.floor(lado * FACTOR_ZOOM_RECORTE)));
    canvas.width = dest;
    canvas.height = dest;
    // imageSmoothingEnabled false = pixels nítidos al ampliar (mejor para QR)
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(video, sx, sy, lado, lado, 0, 0, dest, dest);
    const imageData = ctx.getImageData(0, 0, dest, dest);
    return intentarJsQr(imageData, intentarInvertir);
}
/**
 * Escaneo de respaldo: frame reducido (QR grandes / ya cercanos).
 * Nunca a resolución nativa: eso era una causa fuerte de lag.
 */
function escanearFrameCompleto(intentarInvertir) {
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
    const imageData = ctx.getImageData(0, 0, dw, dh);
    return intentarJsQr(imageData, intentarInvertir);
}
/**
 * Loop de jsQR: un solo análisis por tick (no apilar trabajo).
 */
function iniciarJsQr() {
    if (sesion.intervaloQr !== null) {
        window.clearInterval(sesion.intervaloQr);
    }
    sesion.framesSinExito = 0;
    sesion.analizandoFrame = false;
    // Rotamos una fracción por tick (no tres análisis seguidos)
    const fraccionesRecorte = [0.45, 0.58, 0.70];
    let indiceTick = 0;
    sesion.intervaloQr = window.setInterval(() => {
        if (!sesion.activa || !sesion.video) {
            return;
        }
        // Si el análisis anterior aún corre, saltamos: evita cola de lag
        if (sesion.analizandoFrame) {
            return;
        }
        if (sesion.video.readyState !== sesion.video.HAVE_ENOUGH_DATA) {
            return;
        }
        sesion.analizandoFrame = true;
        try {
            const fraccion = fraccionesRecorte[indiceTick % fraccionesRecorte.length];
            const probarInvertido = indiceTick % 2 === 1;
            indiceTick += 1;
            // Prioridad: recorte central (QR pequeños) — un solo intento por tick
            let codigo = escanearRecorteCentralAmpliado(fraccion, probarInvertido);
            // Cada 4 ticks: frame completo ligero (QR grandes ya cerca)
            if (!codigo && indiceTick % 4 === 0) {
                codigo = escanearFrameCompleto(false);
            }
            if (codigo) {
                procesarCodigoDetectado(codigo, 'Código QR');
                return;
            }
            sesion.framesSinExito += 1;
        }
        finally {
            sesion.analizandoFrame = false;
        }
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
    sesion.analizandoFrame = false;
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
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // 1280×720 se ve fluido en tablets; 1920×1080 satura CPU al analizar QR.
        // El “zoom digital” del recorte central compensaba el detalle de Full HD.
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
        // jsQR primero; Quagga un poco después para no pelear el arranque del preview
        iniciarJsQr();
        window.setTimeout(() => {
            if (sesion.activa) {
                iniciarQuagga();
            }
        }, 400);
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
        iniciarJsQr();
        window.setTimeout(() => {
            if (sesion.activa) {
                iniciarQuagga();
            }
        }, 400);
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