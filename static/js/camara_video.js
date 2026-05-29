"use strict";
// ============================================================================
// CÁMARA GRABADORA DE VIDEO — GALERÍA DE EVIDENCIAS
// Módulo: camara_video.ts  →  compilado en static/js/camara_video.js
// ============================================================================
/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 *
 * Este módulo controla la cámara grabadora de video integrada en detalle_orden.
 * Funciona de forma diferente a la cámara de fotos (camara_integrada.ts):
 * en lugar de capturar frames estáticos, usa la API nativa MediaRecorder del
 * navegador para grabar video directamente desde la cámara trasera del teléfono.
 *
 * MÁQUINA DE ESTADOS:
 * ┌─────────────────────────────────────────────────────────────────┐
 * │  idle → [● Grabar] → grabando → [■ Detener] → preview         │
 * │  preview → [✓ Subir] → subiendo → (recarga página al guardar)  │
 * │  preview → [✗ Descartar] → idle                               │
 * └─────────────────────────────────────────────────────────────────┘
 *
 * LÍMITES:
 *  - Auto-stop al acumular 90 MB de chunks (5 MB antes del hard-limit de 95 MB)
 *  - El servidor acepta hasta 10 minutos (600 s, safety-limit en FFmpeg)
 *  - El blob se envía al mismo endpoint que upload_video.ts (form_type=subir_video)
 *
 * COMPATIBILIDAD DE MIME TYPE:
 *  - Chrome/Firefox graban en 'video/webm' (con variantes de codec)
 *  - El backend normaliza 'video/webm;codecs=vp9,opus' → 'video/webm' antes
 *    de validar (fix en forms.py)
 */
// ============================================================================
// CONSTANTES
// ============================================================================
/**
 * Tamaño acumulado de chunks en bytes en que se dispara el auto-stop.
 * 90 MB — 5 MB de buffer antes del hard-limit de 95 MB del servidor.
 */
const CV_AUTO_STOP_BYTES = 90 * 1024 * 1024;
/** Máximo de MB que muestra el label del contador (hard-limit real del servidor) */
const CV_MAX_LABEL_MB = 95;
/**
 * Mensajes contextuales por tipo de video.
 * Mismo patrón y contenido que AVISOS_VIDEO en upload_video.ts.
 */
const CV_AVISOS = {
    ingreso: {
        clase: 'aviso-ingreso',
        texto: '📥 Video de ingreso: documenta el estado inicial del equipo al recibirlo.',
    },
    diagnostico: {
        clase: 'aviso-diagnostico',
        texto: '🔍 Video de diagnóstico: muestra el proceso de identificación del problema.',
    },
    reparacion: {
        clase: 'aviso-reparacion',
        texto: '🔧 Video de reparación: evidencia del trabajo realizado en el equipo.',
    },
    egreso: {
        clase: 'aviso-egreso',
        texto: '📤 Video de egreso: documenta el estado final del equipo antes de entregarlo.',
    },
    packing: {
        clase: 'aviso-packing',
        texto: '📦 Video de packing: evidencia del empaque y protección para envío.',
    },
};
// ============================================================================
// CLASE PRINCIPAL
// ============================================================================
class CamaraVideo {
    // ────────────────────────────────────────────────────────────────────────
    // CONSTRUCTOR
    // ────────────────────────────────────────────────────────────────────────
    constructor() {
        // EXPLICACIÓN: Asignamos TODAS las propiedades primero (aunque queden null
        // si el elemento no existe), luego verificamos si el modal está presente.
        // Esto es requerido por strictPropertyInitialization de TypeScript.
        // ── Referencias al DOM ───────────────────────────────────────────────────
        // PATRÓN del proyecto: declarar como Type | null = null y asignar en el constructor.
        // Esto satisface strictPropertyInitialization sin necesitar el operador !.
        this.modalEl = null;
        this.bsModal = null;
        this.videoEl = null;
        // Paneles de controles inferiores (uno por estado de la máquina)
        this.panelIdle = null;
        this.panelGrabando = null;
        this.panelPreview = null;
        this.panelSubiendo = null;
        // Botones de acción
        this.btnGrabar = null;
        this.btnDetener = null;
        this.btnSubir = null;
        this.btnDescartar = null;
        // Barra de progreso de grabación (indica MB usados en tiempo real)
        this.contProgreso = null;
        this.progressBar = null;
        this.labelMB = null;
        // Selector de tipo + aviso + descripción (visibles en estado preview/subiendo)
        this.contTipo = null;
        this.previewActions = null; // Descartar + Guardar dentro del overlay
        this.tipoCards = null;
        this.avisoCont = null;
        this.descripcionInput = null;
        // Indicadores de progreso de subida al servidor
        this.contProgressSubida = null;
        this.barraSubida = null;
        this.textoSubida = null;
        this.contFFmpeg = null;
        // Mensaje de error general (visible en todos los estados)
        this.errorCont = null;
        this.mensajeError = null;
        // ── Estado interno ───────────────────────────────────────────────────────
        this.stream = null;
        this.recorder = null;
        this.chunks = [];
        this.totalBytes = 0;
        this.videoBlob = null;
        this.estado = 'idle';
        this.modalEl = document.getElementById('modalCamaraVideo');
        // Si el modal no existe en esta página, no hay nada más que hacer.
        // Todas las propiedades quedan en null y el módulo no hace nada.
        if (!this.modalEl)
            return;
        this.bsModal = new bootstrap.Modal(this.modalEl);
        // ── DOM: elementos del visor y controles ──
        this.videoEl = document.getElementById('cvVideoEl');
        this.panelIdle = document.getElementById('cvPanelIdle');
        this.panelGrabando = document.getElementById('cvPanelGrabando');
        this.panelPreview = document.getElementById('cvPanelPreview');
        this.panelSubiendo = document.getElementById('cvPanelSubiendo');
        this.btnGrabar = document.getElementById('cvBtnGrabar');
        this.btnDetener = document.getElementById('cvBtnDetener');
        this.btnSubir = document.getElementById('cvBtnSubir');
        this.btnDescartar = document.getElementById('cvBtnDescartar');
        this.contProgreso = document.getElementById('cvContProgreso');
        this.progressBar = document.getElementById('cvProgressBar');
        this.labelMB = document.getElementById('cvLabelMB');
        this.contTipo = document.getElementById('cvContTipo');
        this.previewActions = document.getElementById('cvPreviewActions');
        this.tipoCards = document.getElementById('cvTipoCards');
        this.avisoCont = document.getElementById('cvAvisoCont');
        this.descripcionInput = document.getElementById('cvDescripcion');
        this.contProgressSubida = document.getElementById('cvContProgressSubida');
        this.barraSubida = document.getElementById('cvBarraSubida');
        this.textoSubida = document.getElementById('cvTextoSubida');
        this.contFFmpeg = document.getElementById('cvContFFmpeg');
        this.errorCont = document.getElementById('cvErrorCont');
        this.mensajeError = document.getElementById('cvMensajeError');
        this.registrarEventos();
    }
    // ────────────────────────────────────────────────────────────────────────
    // REGISTRO DE EVENTOS
    // ────────────────────────────────────────────────────────────────────────
    registrarEventos() {
        var _a, _b, _c, _d, _e;
        // Botón externo que abre el modal (en el header de la sección galería)
        const btnAbrir = document.getElementById('btnAbrirCamaraVideo');
        if (btnAbrir) {
            btnAbrir.addEventListener('click', () => this.abrir());
        }
        // Botones de la máquina de estados
        (_a = this.btnGrabar) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => this.iniciarGrabacion());
        (_b = this.btnDetener) === null || _b === void 0 ? void 0 : _b.addEventListener('click', () => this.detenerGrabacion());
        (_c = this.btnSubir) === null || _c === void 0 ? void 0 : _c.addEventListener('click', () => void this.subirVideo());
        (_d = this.btnDescartar) === null || _d === void 0 ? void 0 : _d.addEventListener('click', () => this.descartar());
        // Limpiar stream y recursos cuando Bootstrap cierra el modal
        (_e = this.modalEl) === null || _e === void 0 ? void 0 : _e.addEventListener('hidden.bs.modal', () => this.liberarRecursos());
        // Avisos contextuales al seleccionar tipo de video
        if (this.tipoCards) {
            const radios = this.tipoCards.querySelectorAll('input[type="radio"]');
            radios.forEach(radio => {
                radio.addEventListener('change', () => this.actualizarAviso(radio.value));
            });
        }
    }
    // ────────────────────────────────────────────────────────────────────────
    // ABRIR MODAL
    // ────────────────────────────────────────────────────────────────────────
    async abrir() {
        if (!this.bsModal)
            return;
        this.resetearEstado();
        this.bsModal.show();
        // Pequeño delay para que el modal termine la animación de apertura de
        // Bootstrap antes de solicitar permisos de cámara (mejor UX en móvil)
        await new Promise(resolve => setTimeout(resolve, 250));
        await this.activarCamara();
    }
    // ────────────────────────────────────────────────────────────────────────
    // ACTIVAR CÁMARA TRASERA
    // ────────────────────────────────────────────────────────────────────────
    async activarCamara() {
        this.ocultarError();
        try {
            /*
             * EXPLICACIÓN:
             * facingMode: { ideal: 'environment' } solicita la cámara trasera.
             * Usamos 'ideal' en lugar de 'exact' para mayor compatibilidad:
             * - 'exact' falla en dispositivos sin cámara trasera (escritorio, portátiles)
             * - 'ideal' permite que el navegador use la mejor disponible
             * Resolución: 1280×720 (el servidor lo trunca a 720p igualmente)
             */
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    facingMode: { ideal: 'environment' },
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                },
                audio: true,
            });
            if (this.videoEl) {
                this.videoEl.srcObject = this.stream;
                this.videoEl.muted = true; // Sin eco en el preview en vivo
                this.videoEl.controls = false;
            }
        }
        catch (err) {
            const msg = err instanceof Error ? err.message : String(err);
            this.mostrarError(`No se pudo acceder a la cámara.\n` +
                `Verifica los permisos del navegador.\n\n(${msg})`);
        }
    }
    // ────────────────────────────────────────────────────────────────────────
    // INICIAR GRABACIÓN
    // ────────────────────────────────────────────────────────────────────────
    iniciarGrabacion() {
        if (!this.stream) {
            this.mostrarError('No hay cámara activa. Cierra y vuelve a abrir el grabador.');
            return;
        }
        this.chunks = [];
        this.totalBytes = 0;
        this.actualizarContador(0);
        // Elegir el mejor MIME type que soporte este navegador
        const tipoMime = this.elegirMimeType();
        try {
            this.recorder = new MediaRecorder(this.stream, {
                mimeType: tipoMime || undefined,
            });
        }
        catch {
            // Fallback sin especificar mimeType — el navegador elige el predeterminado
            this.recorder = new MediaRecorder(this.stream);
        }
        /*
         * EXPLICACIÓN — timeslice=1000:
         * MediaRecorder.start(ms) dispara ondataavailable cada `ms` milisegundos.
         * Con 1000 ms obtenemos un chunk por segundo → el contador de MB se
         * actualiza en tiempo real sin consumir demasiada RAM ni interrumpir el stream.
         */
        this.recorder.ondataavailable = (e) => this.onChunk(e);
        this.recorder.onstop = () => this.onRecorderStop();
        this.recorder.start(1000);
        this.setEstado('grabando');
    }
    // ────────────────────────────────────────────────────────────────────────
    // CHUNK RECIBIDO — actualizar contador en tiempo real
    // ────────────────────────────────────────────────────────────────────────
    onChunk(e) {
        if (e.data.size === 0)
            return;
        this.chunks.push(e.data);
        this.totalBytes += e.data.size;
        this.actualizarContador(this.totalBytes);
        // Auto-stop al llegar al límite de tamaño configurado
        if (this.totalBytes >= CamaraVideo.AUTO_STOP_BYTES) {
            this.detenerGrabacion();
        }
    }
    // ────────────────────────────────────────────────────────────────────────
    // DETENER GRABACIÓN
    // ────────────────────────────────────────────────────────────────────────
    detenerGrabacion() {
        if (this.recorder && this.recorder.state !== 'inactive') {
            /*
             * EXPLICACIÓN:
             * recorder.stop() es asíncrono. Antes de devolver el control,
             * el navegador termina de procesar el último chunk y dispara onstop.
             * Por eso el cambio de estado a 'preview' ocurre en onRecorderStop(),
             * no aquí, para garantizar que el blob esté completamente formado.
             */
            this.recorder.stop();
        }
    }
    // ────────────────────────────────────────────────────────────────────────
    // CALLBACK: todos los chunks listos → mostrar preview
    // ────────────────────────────────────────────────────────────────────────
    onRecorderStop() {
        var _a;
        const tipoMime = ((_a = this.recorder) === null || _a === void 0 ? void 0 : _a.mimeType) || 'video/webm';
        this.videoBlob = new Blob(this.chunks, { type: tipoMime });
        // Sustituir el stream en vivo por el video grabado para que el usuario
        // pueda revisarlo antes de decidir si sube o descarta
        const urlPreview = URL.createObjectURL(this.videoBlob);
        if (this.videoEl) {
            this.videoEl.srcObject = null;
            this.videoEl.src = urlPreview;
            this.videoEl.muted = false; // El técnico puede escuchar el audio grabado
            this.videoEl.controls = true;
        }
        this.setEstado('preview');
    }
    // ────────────────────────────────────────────────────────────────────────
    // SUBIR VIDEO AL SERVIDOR
    // ────────────────────────────────────────────────────────────────────────
    async subirVideo() {
        var _a, _b;
        if (!this.tipoCards)
            return;
        // Validar que se eligió un tipo antes de subir
        const tipoRadio = this.tipoCards.querySelector('input[type="radio"]:checked');
        if (!tipoRadio) {
            this.mostrarError('Elige el tipo de video antes de subir.');
            return;
        }
        if (!this.videoBlob) {
            this.mostrarError('No hay video grabado. Cierra el modal e inténtalo de nuevo.');
            return;
        }
        this.ocultarError();
        this.setEstado('subiendo');
        /*
         * EXPLICACIÓN — FormData manual:
         * No tenemos un <form> real (el video viene del MediaRecorder como Blob,
         * no de un <input type="file">). Construimos FormData a mano replicando
         * exactamente los campos que el endpoint detalle_orden espera.
         *
         * Campos requeridos (mismo shape que el form HTML de subir_video):
         *   csrfmiddlewaretoken → protección CSRF obligatoria en Django
         *   form_type           → 'subir_video' (dispatcher en views.py)
         *   tipo                → valor del radio card seleccionado
         *   descripcion         → texto opcional
         *   video               → el Blob con nombre .webm
         */
        const formData = new FormData();
        // CSRF token — sin él, Django rechaza el POST con error 403
        const csrfInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfInput) {
            formData.append('csrfmiddlewaretoken', csrfInput.value);
        }
        formData.append('form_type', 'subir_video');
        formData.append('tipo', tipoRadio.value);
        formData.append('descripcion', ((_b = (_a = this.descripcionInput) === null || _a === void 0 ? void 0 : _a.value) === null || _b === void 0 ? void 0 : _b.trim()) || '');
        // El archivo se nombra con timestamp para garantizar unicidad
        const nombreArchivo = `grabacion_${Date.now()}.webm`;
        formData.append('video', this.videoBlob, nombreArchivo);
        // ── XHR — mismo patrón y timeout que upload_video.ts ──
        const xhr = new XMLHttpRequest();
        // Progreso de subida → actualizar barra
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                this.actualizarProgressSubida(pct);
                if (pct >= 100) {
                    // Upload completo → FFmpeg procesando en el servidor
                    if (this.contProgressSubida)
                        this.contProgressSubida.style.display = 'none';
                    if (this.contFFmpeg)
                        this.contFFmpeg.style.display = 'block';
                }
            }
        });
        // Respuesta del servidor
        xhr.addEventListener('load', () => {
            try {
                const data = JSON.parse(xhr.responseText);
                if (data.success) {
                    // Éxito — recargar la página para mostrar el video en la galería
                    setTimeout(() => window.location.reload(), 1200);
                }
                else {
                    this.setEstado('preview');
                    this.mostrarError(data.error || 'Error desconocido al guardar el video.');
                }
            }
            catch {
                this.setEstado('preview');
                this.mostrarError(`Error inesperado del servidor (código ${xhr.status}). Intenta de nuevo.`);
            }
        });
        xhr.addEventListener('error', () => {
            this.setEstado('preview');
            this.mostrarError('Error de conexión. Verifica tu internet e intenta de nuevo.');
        });
        xhr.addEventListener('timeout', () => {
            this.setEstado('preview');
            this.mostrarError('La solicitud tardó demasiado. El video puede ser muy grande.');
        });
        xhr.open('POST', window.location.href);
        xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
        xhr.timeout = 360000; // 6 minutos — mismo que upload_video.ts
        xhr.send(formData);
    }
    // ────────────────────────────────────────────────────────────────────────
    // DESCARTAR — volver a idle y reactivar stream en vivo
    // ────────────────────────────────────────────────────────────────────────
    descartar() {
        var _a, _b;
        // Liberar la URL del Blob del preview para evitar memory leaks
        if ((_b = (_a = this.videoEl) === null || _a === void 0 ? void 0 : _a.src) === null || _b === void 0 ? void 0 : _b.startsWith('blob:')) {
            URL.revokeObjectURL(this.videoEl.src);
        }
        // Restaurar stream en vivo en el visor
        if (this.videoEl) {
            this.videoEl.src = '';
            this.videoEl.srcObject = this.stream;
            this.videoEl.muted = true;
            this.videoEl.controls = false;
        }
        // Limpiar datos de la grabación descartada
        this.chunks = [];
        this.totalBytes = 0;
        this.videoBlob = null;
        this.recorder = null;
        // Limpiar selección de tipo y descripción
        if (this.tipoCards) {
            this.tipoCards
                .querySelectorAll('input[type="radio"]')
                .forEach(r => { r.checked = false; });
        }
        if (this.descripcionInput)
            this.descripcionInput.value = '';
        if (this.avisoCont) {
            this.avisoCont.textContent = '';
            this.avisoCont.className = 'tipo-imagen-aviso d-none mt-2';
        }
        this.ocultarError();
        this.setEstado('idle');
    }
    // ────────────────────────────────────────────────────────────────────────
    // HELPER — MIME TYPE
    // ────────────────────────────────────────────────────────────────────────
    /**
     * Devuelve el MIME type preferido soportado por este navegador.
     * Orden: VP9+Opus (mejor relación calidad/tamaño) → VP8+Opus → base webm.
     * El backend normaliza los codecs explícitos antes de validar (forms.py).
     */
    elegirMimeType() {
        const candidatos = [
            'video/webm;codecs=vp9,opus',
            'video/webm;codecs=vp8,opus',
            'video/webm;codecs=vp9',
            'video/webm;codecs=vp8',
            'video/webm',
            'video/mp4', // Safari / iOS (soporte MediaRecorder experimental en iOS 14.3+)
        ];
        for (const tipo of candidatos) {
            if (MediaRecorder.isTypeSupported(tipo))
                return tipo;
        }
        return ''; // Deja que el navegador elija el predeterminado
    }
    // ────────────────────────────────────────────────────────────────────────
    // HELPER — CONTADOR EN TIEMPO REAL
    // ────────────────────────────────────────────────────────────────────────
    /**
     * Actualiza la barra de progreso y el label de MB.
     * Color: verde (0-60%) → amarillo (60-85%) → rojo (85-100%)
     */
    actualizarContador(bytes) {
        const AUTO_STOP = CamaraVideo.AUTO_STOP_BYTES;
        const mb = bytes / (1024 * 1024);
        const pct = Math.min((bytes / AUTO_STOP) * 100, 100);
        if (this.progressBar) {
            this.progressBar.style.width = `${pct}%`;
            this.progressBar.setAttribute('aria-valuenow', String(Math.round(pct)));
            this.progressBar.classList.remove('bg-success', 'bg-warning', 'bg-danger');
            if (pct < 60) {
                this.progressBar.classList.add('bg-success');
            }
            else if (pct < 85) {
                this.progressBar.classList.add('bg-warning');
            }
            else {
                this.progressBar.classList.add('bg-danger');
            }
        }
        if (this.labelMB) {
            this.labelMB.textContent = `${mb.toFixed(1)} MB / ${CV_MAX_LABEL_MB} MB`;
        }
    }
    // ────────────────────────────────────────────────────────────────────────
    // HELPER — AVISO CONTEXTUAL POR TIPO
    // ────────────────────────────────────────────────────────────────────────
    actualizarAviso(tipo) {
        if (!this.avisoCont)
            return;
        const aviso = CV_AVISOS[tipo];
        if (aviso) {
            this.avisoCont.textContent = aviso.texto;
            this.avisoCont.className = `tipo-imagen-aviso ${aviso.clase} mt-2`;
        }
        else {
            this.avisoCont.textContent = '';
            this.avisoCont.className = 'tipo-imagen-aviso d-none mt-2';
        }
    }
    // ────────────────────────────────────────────────────────────────────────
    // HELPER — BARRA DE PROGRESO DE SUBIDA XHR
    // ────────────────────────────────────────────────────────────────────────
    actualizarProgressSubida(pct) {
        if (this.contProgressSubida)
            this.contProgressSubida.style.display = 'block';
        if (this.barraSubida) {
            this.barraSubida.style.width = `${pct}%`;
            this.barraSubida.setAttribute('aria-valuenow', String(pct));
        }
        if (this.textoSubida) {
            this.textoSubida.textContent = pct < 100 ? `Subiendo… ${pct}%` : 'Subida completa';
        }
    }
    // ────────────────────────────────────────────────────────────────────────
    // MÁQUINA DE ESTADOS — actualizar visibilidad de paneles
    // ────────────────────────────────────────────────────────────────────────
    setEstado(nuevoEstado) {
        this.estado = nuevoEstado;
        // Ocultar todos los paneles de control
        [this.panelIdle, this.panelGrabando, this.panelPreview, this.panelSubiendo]
            .forEach(p => { if (p)
            p.style.display = 'none'; });
        // Barra de progreso de grabación: solo visible mientras graba
        if (this.contProgreso) {
            this.contProgreso.style.display = nuevoEstado === 'grabando' ? 'block' : 'none';
        }
        // Panel de tipo + descripción: visible en preview y mientras se sube
        if (this.contTipo) {
            this.contTipo.style.display =
                (nuevoEstado === 'preview' || nuevoEstado === 'subiendo') ? 'block' : 'none';
        }
        // Botones Descartar/Guardar: solo visibles en estado 'preview'
        // (en 'subiendo' se ocultan porque la subida ya comenzó)
        if (this.previewActions) {
            this.previewActions.style.display = nuevoEstado === 'preview' ? 'flex' : 'none';
        }
        // Mostrar el panel correspondiente al nuevo estado
        const panelMap = {
            idle: this.panelIdle,
            grabando: this.panelGrabando,
            preview: this.panelPreview,
            subiendo: this.panelSubiendo,
        };
        const panelActivo = panelMap[nuevoEstado];
        if (panelActivo)
            panelActivo.style.display = 'flex';
        // En 'subiendo': deshabilitar controles para evitar cambios durante la subida
        if (this.tipoCards) {
            this.tipoCards
                .querySelectorAll('input[type="radio"]')
                .forEach(r => { r.disabled = nuevoEstado === 'subiendo'; });
        }
        if (this.descripcionInput) {
            this.descripcionInput.disabled = nuevoEstado === 'subiendo';
        }
    }
    // ────────────────────────────────────────────────────────────────────────
    // RESETEAR ESTADO — limpieza completa antes de abrir el modal
    // ────────────────────────────────────────────────────────────────────────
    resetearEstado() {
        var _a;
        this.chunks = [];
        this.totalBytes = 0;
        this.videoBlob = null;
        this.recorder = null;
        this.stream = null;
        if (this.videoEl) {
            if ((_a = this.videoEl.src) === null || _a === void 0 ? void 0 : _a.startsWith('blob:'))
                URL.revokeObjectURL(this.videoEl.src);
            this.videoEl.src = '';
            this.videoEl.srcObject = null;
            this.videoEl.controls = false;
            this.videoEl.muted = true;
        }
        // Limpiar formulario de tipo y descripción
        if (this.tipoCards) {
            this.tipoCards
                .querySelectorAll('input[type="radio"]')
                .forEach(r => { r.checked = false; r.disabled = false; });
        }
        if (this.descripcionInput) {
            this.descripcionInput.value = '';
            this.descripcionInput.disabled = false;
        }
        if (this.avisoCont) {
            this.avisoCont.textContent = '';
            this.avisoCont.className = 'tipo-imagen-aviso d-none mt-2';
        }
        // Limpiar indicadores de subida
        if (this.contProgressSubida)
            this.contProgressSubida.style.display = 'none';
        if (this.contFFmpeg)
            this.contFFmpeg.style.display = 'none';
        if (this.barraSubida)
            this.barraSubida.style.width = '0%';
        if (this.textoSubida)
            this.textoSubida.textContent = 'Subiendo…';
        this.actualizarContador(0);
        this.ocultarError();
        this.setEstado('idle');
    }
    // ────────────────────────────────────────────────────────────────────────
    // LIBERAR RECURSOS — al cerrar el modal
    // ────────────────────────────────────────────────────────────────────────
    liberarRecursos() {
        var _a;
        // Detener grabación si estaba activa
        if (this.recorder && this.recorder.state !== 'inactive') {
            this.recorder.stop();
        }
        // Detener todas las pistas del stream (libera la cámara y el micrófono)
        if (this.stream) {
            this.stream.getTracks().forEach(t => t.stop());
            this.stream = null;
        }
        // Liberar Blob URL del preview si existe
        if (this.videoEl) {
            if ((_a = this.videoEl.src) === null || _a === void 0 ? void 0 : _a.startsWith('blob:'))
                URL.revokeObjectURL(this.videoEl.src);
            this.videoEl.src = '';
            this.videoEl.srcObject = null;
        }
    }
    // ────────────────────────────────────────────────────────────────────────
    // HELPERS — ERRORES
    // ────────────────────────────────────────────────────────────────────────
    mostrarError(msg) {
        if (this.errorCont)
            this.errorCont.style.display = 'block';
        if (this.mensajeError)
            this.mensajeError.textContent = msg;
    }
    ocultarError() {
        if (this.errorCont)
            this.errorCont.style.display = 'none';
        if (this.mensajeError)
            this.mensajeError.textContent = '';
    }
}
// ── Límites ──────────────────────────────────────────────────────────────
CamaraVideo.AUTO_STOP_BYTES = CV_AUTO_STOP_BYTES;
// ============================================================================
// INICIALIZACIÓN — solo si el modal existe en esta página
// ============================================================================
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('modalCamaraVideo')) {
        new CamaraVideo();
    }
});
//# sourceMappingURL=camara_video.js.map