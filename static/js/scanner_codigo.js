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
 * - Elige la lente principal (1x) cuando el teléfono expone varias traseras
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
const MODO_TOGGLE_ID = 'scannerModoToggle';
const FRAME_ID = 'scannerCodigoFrame';
const CONSEJO_ID = 'scannerCodigoConsejo';
const SELECTOR_LENTES_ID = 'scannerSelectorLentes';
const STORAGE_MODO_KEY = 'sigma_scanner_modo';
/** Recuerda la última lente que sí sirvió para escanear en este teléfono */
const STORAGE_DEVICE_KEY = 'sigma_scanner_deviceId';
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
/** Ancho máx. del recorte horizontal (barras 1D) */
const MAX_ANCHO_BARRAS_PX = 960;
/** Alto mín. del recorte horizontal ampliado (más píxeles por barra) */
const MIN_ALTO_BARRAS_PX = 180;
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
/** Solo barras 1D — modo horizontal (menos ruido que buscar QR/DM). */
const FORMATOS_BARRAS_1D = [
    'Code128',
    'Code39',
    'Codabar',
    'EAN13',
    'EAN8',
    'UPCA',
    'UPCE',
];
/** Recortes horizontales [ancho, alto] como fracción del frame de video */
const RECORTES_BARRAS = [
    [0.88, 0.28],
    [0.92, 0.34],
    [0.80, 0.40],
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
    modo: 'cuadrado',
    camarasTraseras: [],
    dispositivoActualId: null,
    lenteElegidaPorUsuario: false,
    cambiandoLente: false,
};
/**
 * Garantiza que el modal del scanner exista en el DOM.
 * Si no está (primera vez), lo crea una sola vez y lo reutiliza.
 */
function asegurarModalScanner() {
    let modal = document.getElementById(MODAL_ID);
    if (modal) {
        asegurarHostSelectorLentes(modal);
        enlazarToggleModoScanner(modal);
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
          <div id="${MODO_TOGGLE_ID}" class="btn-group w-100 mb-3" role="group" aria-label="Tipo de código a escanear">
            <button type="button" class="btn btn-outline-primary active" data-scanner-modo="cuadrado">
              <i class="bi bi-qr-code" aria-hidden="true"></i> Cuadrado (QR / Data Matrix)
            </button>
            <button type="button" class="btn btn-outline-primary" data-scanner-modo="barras">
              <i class="bi bi-upc-scan" aria-hidden="true"></i> Barras (Code 128)
            </button>
          </div>
          <div class="scanner-container scanner-container--mejorado">
            <div id="${VIDEO_HOST_ID}"></div>
            <div class="scanner-overlay">
              <div id="${FRAME_ID}" class="scanner-frame scanner-frame--preciso"></div>
            </div>
            <div id="${SELECTOR_LENTES_ID}" class="scanner-selector-lentes" hidden></div>
          </div>
          <div id="${TIPS_ID}" class="mt-3 text-start" hidden></div>
          <div id="${CONSEJO_ID}" class="alert alert-info mt-3 mb-0 text-start small">
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
    enlazarToggleModoScanner(modal);
    return modal;
}
/**
 * Si el modal ya existía (sesión previa), garantiza el host del selector.
 * Va FUERA de .scanner-overlay porque ese overlay tiene pointer-events: none.
 */
function asegurarHostSelectorLentes(modal) {
    if (modal.querySelector(`#${SELECTOR_LENTES_ID}`)) {
        return;
    }
    const contenedor = modal.querySelector('.scanner-container');
    if (!contenedor) {
        return;
    }
    const host = document.createElement('div');
    host.id = SELECTOR_LENTES_ID;
    host.className = 'scanner-selector-lentes';
    host.hidden = true;
    contenedor.appendChild(host);
}
/**
 * Lee el último modo elegido por el usuario (localStorage) o devuelve default.
 */
function obtenerModoPersistido(defaultModo) {
    try {
        const guardado = localStorage.getItem(STORAGE_MODO_KEY);
        if (guardado === 'cuadrado' || guardado === 'barras') {
            return guardado;
        }
    }
    catch {
        // localStorage bloqueado (modo privado, etc.)
    }
    return defaultModo;
}
/**
 * Guarda la preferencia de modo para la próxima apertura del scanner.
 */
function persistirModoScanner(modo) {
    try {
        localStorage.setItem(STORAGE_MODO_KEY, modo);
    }
    catch {
        // Ignorar si no se puede persistir
    }
}
/**
 * ¿El label describe una cámara frontal (selfie)?
 *
 * EXPLICACIÓN PARA PRINCIPIANTES: enumerateDevices() mezcla frontales y
 * traseras. El scanner siempre quiere la trasera (el equipo está sobre la mesa).
 */
function esCamaraFrontal(label) {
    const l = label.toLowerCase();
    return (l.includes('front')
        || l.includes('user')
        || l.includes('selfie')
        || l.includes('facing front'));
}
/**
 * Clasifica una lente por el nombre que reporta Android/iOS.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES: la API web NO tiene un campo “lente 1x”.
 * Chrome en Android a veces llama al gran angular “ultra-wide” o “0.5”;
 * iPhone suele decir “Back Camera” y solo expone una trasera.
 *
 * “wide” solo (sin ultra) NO lo tratamos como gran angular: en iOS “Wide”
 * es la cámara principal.
 */
function clasificarLente(label) {
    const l = label.toLowerCase();
    // Gran angular: distorsiona y aleja el código — pésimo para Data Matrix.
    if (l.includes('ultra')
        || l.includes('ultrawide')
        || l.includes('0.5')
        || l.includes('wide-angle')
        || l.includes('wide angle')) {
        return 'ultrawide';
    }
    if (l.includes('tele')
        || l.includes('2x')
        || l.includes('3x')
        || l.includes('5x')) {
        return 'tele';
    }
    if (l.includes('macro')) {
        return 'macro';
    }
    if (l.includes('back')
        || l.includes('rear')
        || l.includes('environment')
        || l.includes('facing back')) {
        return 'principal';
    }
    return 'desconocido';
}
/**
 * Puntaje para elegir default: mayor = mejor para leer códigos.
 * Principal gana; gran angular queda al fondo (sigue disponible en el selector).
 */
function puntajeLente(label) {
    const tipo = clasificarLente(label);
    if (tipo === 'principal') {
        return 100;
    }
    if (tipo === 'desconocido') {
        return 50;
    }
    if (tipo === 'tele') {
        return 20;
    }
    if (tipo === 'macro') {
        return 10;
    }
    return 0;
}
/**
 * Elige la lente con la que debe abrir el scanner.
 *
 * @param camaras - Solo traseras (ya filtradas)
 * @param deviceIdGuardado - Última lente que funcionó en este teléfono, o null
 */
function elegirCamaraPrincipal(camaras, deviceIdGuardado) {
    if (camaras.length === 0) {
        return null;
    }
    // Preferencia del técnico (o la que auto-corregimos la vez anterior)
    if (deviceIdGuardado && camaras.some((c) => c.deviceId === deviceIdGuardado)) {
        return deviceIdGuardado;
    }
    let mejor = camaras[0];
    let mejorPuntaje = puntajeLente(mejor.label);
    for (let i = 1; i < camaras.length; i += 1) {
        const candidata = camaras[i];
        const puntaje = puntajeLente(candidata.label);
        if (puntaje > mejorPuntaje) {
            mejor = candidata;
            mejorPuntaje = puntaje;
        }
    }
    return mejor.deviceId;
}
function obtenerDeviceIdPersistido() {
    try {
        return localStorage.getItem(STORAGE_DEVICE_KEY);
    }
    catch {
        return null;
    }
}
function persistirDeviceIdScanner(deviceId) {
    try {
        localStorage.setItem(STORAGE_DEVICE_KEY, deviceId);
    }
    catch {
        // localStorage bloqueado (modo privado, etc.)
    }
}
/**
 * Actualiza marco visual, botones del toggle y texto de consejo según el modo.
 */
function aplicarModoScanner(modo) {
    sesion.modo = modo;
    persistirModoScanner(modo);
    const frame = document.getElementById(FRAME_ID);
    if (frame) {
        frame.classList.remove('scanner-frame--preciso', 'scanner-frame--barras');
        frame.classList.add(modo === 'barras' ? 'scanner-frame--barras' : 'scanner-frame--preciso');
    }
    const toggle = document.getElementById(MODO_TOGGLE_ID);
    if (toggle) {
        toggle.querySelectorAll('[data-scanner-modo]').forEach((btn) => {
            const esActivo = btn.getAttribute('data-scanner-modo') === modo;
            btn.classList.toggle('active', esActivo);
            btn.setAttribute('aria-pressed', esActivo ? 'true' : 'false');
        });
    }
    actualizarConsejoModal(modo);
    ocultarTipsSinDeteccion();
}
/**
 * Texto de ayuda bajo el visor — distinto para cuadrado vs barras 1D.
 */
function actualizarConsejoModal(modo) {
    const host = document.getElementById(CONSEJO_ID);
    if (!host) {
        return;
    }
    if (modo === 'barras') {
        host.innerHTML = `
      <i class="bi bi-info-circle" aria-hidden="true"></i>
      <strong>Modo barras:</strong> alinea las <em>rayas horizontales</em> dentro del marco ancho.
      Muchos cargadores HP/Dell usan Code 128 (franja blanca con rayas negras).
      Evita reflejos en plástico negro; si falla, copia el número impreso debajo de las barras.`;
        return;
    }
    host.innerHTML = `
    <i class="bi bi-info-circle" aria-hidden="true"></i>
    <strong>Modo cuadrado:</strong> etiquetas Dell suelen ser
    <em>Data Matrix</em> (cuadrícula densa, sin 3 cuadritos de QR).
    Acerca el código hasta que llene el marco; buena luz y mano firme ayudan.`;
}
/**
 * Registra listeners en el toggle Cuadrado/Barras (solo una vez al crear modal).
 */
function enlazarToggleModoScanner(modal) {
    const toggle = modal.querySelector(`#${MODO_TOGGLE_ID}`);
    if (!toggle || toggle.getAttribute('data-scanner-toggle-listo') === '1') {
        return;
    }
    toggle.setAttribute('data-scanner-toggle-listo', '1');
    toggle.addEventListener('click', (event) => {
        const btn = event.target.closest('[data-scanner-modo]');
        if (!btn) {
            return;
        }
        const modo = btn.getAttribute('data-scanner-modo');
        if (modo !== 'cuadrado' && modo !== 'barras') {
            return;
        }
        if (modo === sesion.modo) {
            return;
        }
        aplicarModoScanner(modo);
        // Reiniciar tips si la cámara ya está activa
        if (sesion.activa) {
            limpiarTimersFeedback();
            programarFeedbackSinDeteccion();
            mostrarEstadoScanner('info', modo === 'barras'
                ? 'Modo barras — alinea las rayas horizontales en el marco ancho'
                : 'Modo cuadrado — acerca el QR o Data Matrix al marco');
        }
    });
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
    const esBarras = sesion.modo === 'barras';
    if (nivel === 'suave') {
        mostrarEstadoScanner('warning', esBarras
            ? 'Aún no reconozco las barras. Alinea la franja en el marco ancho…'
            : 'Aún no reconozco el código. Acércalo más al marco e inténtalo de nuevo…');
        if (esBarras) {
            tipsHost.innerHTML = `
      <div class="alert alert-warning mb-0 text-start">
        <strong><i class="bi bi-exclamation-triangle" aria-hidden="true"></i>
        No se detectó todavía</strong>
        <ul class="mb-0 mt-2 ps-3">
          <li>Alinea las <strong>rayas horizontales</strong> paralelas al borde largo del marco.</li>
          <li>Inclina el cargador para <strong>evitar reflejo</strong> en plástico negro.</li>
          <li>Acerca hasta que la franja de barras llene casi todo el ancho del marco.</li>
          <li>Mantén el dispositivo estable 1–2 segundos.</li>
        </ul>
      </div>`;
            return;
        }
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
    if (esBarras) {
        tipsHost.innerHTML = `
    <div class="alert alert-warning mb-0 text-start">
      <strong><i class="bi bi-question-circle" aria-hidden="true"></i>
      Sigue sin reconocerse</strong>
      <ul class="mb-0 mt-2 ps-3">
        <li>Prueba otro ángulo o más luz directa sobre la etiqueta blanca.</li>
        <li>Si el cargador tiene <strong>Data Matrix</strong> (cuadrado), cambia a modo Cuadrado arriba.</li>
        <li>Copia el número impreso debajo de las barras (p. ej. 8SGX21J75539C1TJ33P08ZC).</li>
        <li>Pulsa <em>Cancelar</em> y usa el teclado — no bloqueamos el guardado.</li>
      </ul>
    </div>`;
        return;
    }
    tipsHost.innerHTML = `
    <div class="alert alert-warning mb-0 text-start">
      <strong><i class="bi bi-question-circle" aria-hidden="true"></i>
      Sigue sin reconocerse</strong>
      <ul class="mb-0 mt-2 ps-3">
        <li>Prueba otro ángulo o distancia (un poco más cerca suele bastar).</li>
        <li>Si es etiqueta con <strong>rayas lineales</strong>, cambia a modo Barras arriba.</li>
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
async function intentarLeerConZxingWasm(imageData, formatos = FORMATOS_SCANNER) {
    const api = obtenerZXingWasm();
    if (!api) {
        return null;
    }
    const opciones = {
        tryHarder: true,
        formats: formatos,
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
    const formatos = sesion.modo === 'barras' ? FORMATOS_BARRAS_1D : FORMATOS_SCANNER;
    return intentarLeerConZxingWasm(ctx.getImageData(0, 0, dest, dest), formatos);
}
/**
 * Recorte horizontal panorámico — optimizado para Code 128 en cargadores.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Las barras 1D son anchas y bajas; un recorte cuadrado las corta.
 * Ampliamos la banda central para dar más píxeles a cada rayita.
 */
async function escanearRecorteHorizontal(fraccionAncho, fraccionAlto) {
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
    const ancho = Math.floor(vw * fraccionAncho);
    const alto = Math.floor(vh * fraccionAlto);
    const sx = Math.floor((vw - ancho) / 2);
    const sy = Math.floor((vh - alto) / 2);
    const destW = Math.min(MAX_ANCHO_BARRAS_PX, Math.floor(ancho * FACTOR_ZOOM_RECORTE));
    const destH = Math.max(MIN_ALTO_BARRAS_PX, Math.floor(alto * FACTOR_ZOOM_RECORTE * 2));
    canvas.width = destW;
    canvas.height = destH;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(video, sx, sy, ancho, alto, 0, 0, destW, destH);
    return intentarLeerConZxingWasm(ctx.getImageData(0, 0, destW, destH), FORMATOS_BARRAS_1D);
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
    const formatos = sesion.modo === 'barras' ? FORMATOS_BARRAS_1D : FORMATOS_SCANNER;
    return intentarLeerConZxingWasm(ctx.getImageData(0, 0, dw, dh), formatos);
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
        if (!sesion.activa || !sesion.video || sesion.cambiandoLente) {
            return;
        }
        if (sesion.analizandoFrame) {
            return;
        }
        if (sesion.video.readyState !== sesion.video.HAVE_ENOUGH_DATA) {
            return;
        }
        sesion.analizandoFrame = true;
        const tick = indiceTick;
        indiceTick += 1;
        const esBarras = sesion.modo === 'barras';
        void (async () => {
            try {
                let leido = null;
                if (esBarras) {
                    const [fw, fh] = RECORTES_BARRAS[tick % RECORTES_BARRAS.length];
                    leido = await escanearRecorteHorizontal(fw, fh);
                    if (!leido && tick % 4 === 0) {
                        leido = await escanearRecorteHorizontal(0.95, 0.45);
                    }
                }
                else {
                    const fraccion = fraccionesRecorte[tick % fraccionesRecorte.length];
                    leido = await escanearRecorteCentralAmpliado(fraccion);
                    if (!leido && tick % 4 === 0) {
                        leido = await escanearFrameCompleto();
                    }
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
 * Normaliza el texto leído (quita sufijo REV de etiquetas de cargador).
 */
function limpiarCodigoDetectado(codigo) {
    return codigo.replace(/\s+REV:\d+\s*$/i, '').trim();
}
/**
 * Cuando hay detección válida: escribe en el input, avisa y cierra el modal.
 */
function procesarCodigoDetectado(codigo, tipo) {
    if (!sesion.activa || !sesion.opciones) {
        return;
    }
    const codigoLimpio = limpiarCodigoDetectado(codigo);
    // Pausar de inmediato para no procesar el mismo código varias veces
    sesion.activa = false;
    limpiarTimersFeedback();
    ocultarTipsSinDeteccion();
    reproducirBeepConfirmacion();
    mostrarEstadoScanner('success', `${tipo} detectado: ${codigoLimpio}`);
    const input = sesion.opciones.targetInput;
    input.value = codigoLimpio;
    input.dispatchEvent(new Event('input', { bubbles: true }));
    input.dispatchEvent(new Event('change', { bubbles: true }));
    if (sesion.opciones.onDetect) {
        sesion.opciones.onDetect(codigoLimpio);
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
    sesion.cambiandoLente = false;
    limpiarTimersFeedback();
    ocultarTipsSinDeteccion();
    ocultarSelectorLentesScanner();
    if (sesion.intervaloQr !== null) {
        window.clearInterval(sesion.intervaloQr);
        sesion.intervaloQr = null;
    }
    detenerTracksActuales();
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
    sesion.camarasTraseras = [];
    sesion.dispositivoActualId = null;
    sesion.lenteElegidaPorUsuario = false;
    sesion.framesSinExito = 0;
    sesion.analizandoFrame = false;
}
/**
 * Corta el stream actual sin destruir el <video> (hace falta al cambiar de lente).
 */
function detenerTracksActuales() {
    if (sesion.video && sesion.video.srcObject) {
        const stream = sesion.video.srcObject;
        stream.getTracks().forEach((track) => track.stop());
        sesion.video.srcObject = null;
    }
    sesion.videoTrack = null;
}
function esperarMs(ms) {
    return new Promise((resolve) => {
        window.setTimeout(resolve, ms);
    });
}
/**
 * Lista cámaras traseras. Hay que pedir permiso ANTES: si no, los labels
 * llegan vacíos y no podemos distinguir gran angular de 1x.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES: abrimos un stream temporal solo para que
 * el navegador rellene los nombres; lo cerramos de inmediato. En iPhone
 * suele haber 1 trasera → el selector se oculta solo.
 */
async function detectarCamarasTraseras() {
    if (sesion.camarasTraseras.length > 0) {
        return;
    }
    let streamTemporal = null;
    try {
        streamTemporal = await navigator.mediaDevices.getUserMedia({ video: true });
        const devices = await navigator.mediaDevices.enumerateDevices();
        const videoInputs = devices.filter((d) => d.kind === 'videoinput');
        const traseras = [];
        for (const camara of videoInputs) {
            if (esCamaraFrontal(camara.label)) {
                continue;
            }
            traseras.push({ deviceId: camara.deviceId, label: camara.label });
        }
        // Si no pudimos clasificar ninguna, usamos todas (mejor eso que quedarnos ciegos)
        sesion.camarasTraseras = traseras.length > 0
            ? traseras
            : videoInputs.map((c) => ({ deviceId: c.deviceId, label: c.label }));
    }
    catch (err) {
        console.warn('No se pudieron listar cámaras del scanner:', err);
        sesion.camarasTraseras = [];
    }
    finally {
        if (streamTemporal) {
            streamTemporal.getTracks().forEach((t) => t.stop());
        }
        // Android a veces no libera el hardware al instante
        await esperarMs(200);
    }
}
/**
 * Constraints del preview. Con deviceId pedimos ESA lente; si no, “trasera”.
 */
function construirConstraintsVideo(deviceId, estricto) {
    const constraints = estricto
        ? {
            width: { ideal: 1280, max: 1280 },
            height: { ideal: 720, max: 720 },
            frameRate: { ideal: 30, max: 30 },
        }
        : {
            width: { ideal: 1280 },
            height: { ideal: 720 },
        };
    if (deviceId) {
        constraints.deviceId = { exact: deviceId };
    }
    else {
        constraints.facingMode = estricto ? { ideal: 'environment' } : 'environment';
    }
    return constraints;
}
async function solicitarStreamCamara(deviceId, estricto) {
    return navigator.mediaDevices.getUserMedia({
        video: construirConstraintsVideo(deviceId, estricto),
        audio: false,
    });
}
/**
 * Engancha el stream al <video> ya creado y aplica enfoque/zoom suave.
 */
async function adjuntarStreamAlVideo(stream) {
    if (!sesion.video) {
        throw new Error('No se pudo crear el elemento de video.');
    }
    const track = stream.getVideoTracks()[0] || null;
    sesion.videoTrack = track;
    if (track) {
        await aplicarMejorasEnfoque(track);
    }
    sesion.video.srcObject = stream;
    // EXPLICACIÓN PARA PRINCIPIANTES: a veces el video ya tiene metadatos
    // cuando asignamos el stream (sobre todo al cambiar de lente). Si
    // esperamos el evento loadedmetadata y ya se disparó, nos quedamos colgados.
    const aplicarTamanoCanvas = () => {
        if (sesion.canvas && sesion.video) {
            sesion.canvas.width = sesion.video.videoWidth;
            sesion.canvas.height = sesion.video.videoHeight;
        }
    };
    if (sesion.video.readyState >= HTMLMediaElement.HAVE_METADATA) {
        aplicarTamanoCanvas();
    }
    else {
        await new Promise((resolve) => {
            sesion.video.addEventListener('loadedmetadata', () => {
                aplicarTamanoCanvas();
                resolve();
            }, { once: true });
        });
    }
    await sesion.video.play();
}
/**
 * Chrome en Android: el gran angular suele reportar zoom.min < 1 (p. ej. 0.5).
 * La lente 1x arranca en 1.0. Si el técnico ya eligió a mano, no tocamos nada.
 */
function pistaPareceGranAngular(track) {
    if (clasificarLente(track.label) === 'ultrawide') {
        return true;
    }
    if (typeof track.getCapabilities !== 'function') {
        return false;
    }
    const caps = track.getCapabilities();
    return Boolean(caps.zoom && typeof caps.zoom.min === 'number' && caps.zoom.min < 1);
}
/**
 * Si abrimos el 0.5x por error, saltamos a otra trasera (no ultrawide si hay).
 */
async function corregirGranAngularSiAplica() {
    if (sesion.lenteElegidaPorUsuario || !sesion.videoTrack) {
        return;
    }
    if (!pistaPareceGranAngular(sesion.videoTrack)) {
        return;
    }
    const actual = sesion.dispositivoActualId;
    const noUltra = sesion.camarasTraseras.find((c) => c.deviceId !== actual && clasificarLente(c.label) !== 'ultrawide');
    const cualquiera = sesion.camarasTraseras.find((c) => c.deviceId !== actual);
    const alternativa = noUltra || cualquiera;
    if (!alternativa) {
        return;
    }
    await cambiarLenteScanner(alternativa.deviceId, 'auto');
}
/**
 * Icono/texto del botón — mismo criterio visual que la cámara de fotos.
 */
function obtenerInfoLenteScanner(label, index) {
    const tipo = clasificarLente(label);
    if (tipo === 'ultrawide') {
        return { icono: 'bi-arrows-angle-expand', texto: '0.5x' };
    }
    if (tipo === 'tele') {
        return { icono: 'bi-zoom-in', texto: '2x' };
    }
    if (tipo === 'macro') {
        return { icono: 'bi-flower1', texto: 'Macro' };
    }
    if (tipo === 'principal') {
        return { icono: 'bi-camera', texto: '1x' };
    }
    return { icono: 'bi-camera', texto: index === 0 ? '1x' : `Lente ${index + 1}` };
}
function ocultarSelectorLentesScanner() {
    const host = document.getElementById(SELECTOR_LENTES_ID);
    if (!host) {
        return;
    }
    host.hidden = true;
    host.innerHTML = '';
}
/**
 * Pinta 0.5x / 1x / 2x solo si hay más de una trasera.
 * EXPLICACIÓN PARA PRINCIPIANTES: en iPhone casi nunca aparece; en Android
 * con triple cámara sí, por si la heurística se equivoca.
 */
function actualizarSelectorLentesScanner() {
    const host = document.getElementById(SELECTOR_LENTES_ID);
    if (!host) {
        return;
    }
    if (sesion.camarasTraseras.length <= 1) {
        ocultarSelectorLentesScanner();
        return;
    }
    host.hidden = false;
    host.innerHTML = '';
    const fragment = document.createDocumentFragment();
    sesion.camarasTraseras.forEach((camara, index) => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'scanner-btn-lente';
        btn.title = camara.label || `Lente ${index + 1}`;
        if (camara.deviceId === sesion.dispositivoActualId) {
            btn.classList.add('active');
        }
        const { icono, texto } = obtenerInfoLenteScanner(camara.label, index);
        btn.innerHTML = `<i class="bi ${icono}" aria-hidden="true"></i> ${texto}`;
        btn.addEventListener('click', () => {
            void cambiarLenteScanner(camara.deviceId, 'usuario');
        });
        fragment.appendChild(btn);
    });
    host.appendChild(fragment);
}
/**
 * Cambia de lente sin cerrar el modal ni el modo cuadrado/barras.
 *
 * @param deviceId - Cámara destino
 * @param origen - 'usuario' (tocó el botón) o 'auto' (corrección zoom.min)
 */
async function cambiarLenteScanner(deviceId, origen) {
    if (sesion.cambiandoLente) {
        return;
    }
    if (deviceId === sesion.dispositivoActualId && sesion.videoTrack) {
        return;
    }
    sesion.cambiandoLente = true;
    try {
        sesion.dispositivoActualId = deviceId;
        if (origen === 'usuario') {
            sesion.lenteElegidaPorUsuario = true;
        }
        persistirDeviceIdScanner(deviceId);
        detenerTracksActuales();
        await esperarMs(150);
        let stream;
        try {
            stream = await solicitarStreamCamara(deviceId, true);
        }
        catch (err) {
            const nombre = err.name;
            if (nombre === 'OverconstrainedError') {
                stream = await solicitarStreamCamara(deviceId, false);
            }
            else {
                throw err;
            }
        }
        await adjuntarStreamAlVideo(stream);
        actualizarSelectorLentesScanner();
    }
    catch (err) {
        console.error('No se pudo cambiar de lente del scanner:', err);
        mostrarEstadoScanner('warning', 'No se pudo cambiar de lente. Prueba otra o escribe el código a mano.');
    }
    finally {
        sesion.cambiandoLente = false;
    }
}
/**
 * Arranca getUserMedia + loop zxing-wasm dentro del modal ya visible.
 */
async function iniciarSesionCamara() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        mostrarEstadoScanner('error', 'Tu navegador no soporta acceso a la cámara. Escribe el código manualmente.');
        return;
    }
    const hostOk = location.protocol === 'https:'
        || location.hostname === 'localhost'
        || location.hostname === '127.0.0.1';
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
        await detectarCamarasTraseras();
        const guardado = obtenerDeviceIdPersistido();
        const deviceId = elegirCamaraPrincipal(sesion.camarasTraseras, guardado);
        sesion.dispositivoActualId = deviceId;
        sesion.lenteElegidaPorUsuario = Boolean(guardado && deviceId === guardado);
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // 1280×720 se ve fluido en tablets; el recorte central ampliado aporta detalle.
        // Pedimos deviceId exacto para no caer en el gran angular por default.
        let stream;
        try {
            stream = await solicitarStreamCamara(deviceId, true);
        }
        catch (err) {
            const nombre = err.name;
            if (nombre === 'OverconstrainedError') {
                await iniciarSesionCamaraFallback(deviceId);
                return;
            }
            throw err;
        }
        await adjuntarStreamAlVideo(stream);
        await corregirGranAngularSiAplica();
        if (sesion.dispositivoActualId) {
            persistirDeviceIdScanner(sesion.dispositivoActualId);
        }
        actualizarSelectorLentesScanner();
        sesion.activa = true;
        sesion.inicioEscaneoMs = Date.now();
        sesion.framesSinExito = 0;
        ocultarTipsSinDeteccion();
        mostrarEstadoScanner('info', sesion.modo === 'barras'
            ? 'Scanner activo (modo barras) — alinea las rayas en el marco ancho'
            : 'Scanner activo — acerca el código al marco (sobre todo si es pequeño)');
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
            await iniciarSesionCamaraFallback(sesion.dispositivoActualId);
        }
        else {
            mostrarEstadoScanner('error', `Error del scanner: ${err.message || 'desconocido'}`);
        }
    }
}
/**
 * Segunda oportunidad si el dispositivo no acepta 1280×720 exacto.
 */
async function iniciarSesionCamaraFallback(deviceId) {
    try {
        if (!sesion.video) {
            prepararVideoYCanvas();
        }
        if (!sesion.video) {
            throw new Error('No se pudo crear el elemento de video.');
        }
        let stream;
        try {
            stream = await solicitarStreamCamara(deviceId, false);
        }
        catch {
            // Último recurso: cualquier trasera, sin deviceId
            stream = await solicitarStreamCamara(null, false);
        }
        await adjuntarStreamAlVideo(stream);
        await corregirGranAngularSiAplica();
        if (sesion.dispositivoActualId) {
            persistirDeviceIdScanner(sesion.dispositivoActualId);
        }
        actualizarSelectorLentesScanner();
        sesion.activa = true;
        sesion.inicioEscaneoMs = Date.now();
        mostrarEstadoScanner('info', sesion.modo === 'barras'
            ? 'Scanner activo (modo barras) — alinea las rayas en el marco ancho'
            : 'Scanner activo (resolución estándar) — acerca el código al marco');
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
    var _a;
    if (!opciones.targetInput) {
        console.error('abrirScannerCodigo: falta targetInput');
        return;
    }
    sesion.opciones = opciones;
    const modalEl = asegurarModalScanner();
    const modoInicial = (_a = opciones.modoInicial) !== null && _a !== void 0 ? _a : obtenerModoPersistido('cuadrado');
    aplicarModoScanner(modoInicial);
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