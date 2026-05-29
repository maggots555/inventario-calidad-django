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
const CV_AVISOS: Record<string, { clase: string; texto: string }> = {
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
// TIPOS
// ============================================================================

/** Estados posibles de la máquina de estados de la grabadora */
type EstadoCamaraVideo = 'idle' | 'grabando' | 'preview' | 'subiendo';

/** Respuesta JSON del backend al subir un video (mismo shape que upload_video.ts) */
interface CvVideoUploadResponse {
    success: boolean;
    message?: string;
    error?: string;
    form_errors?: Record<string, string[]>;
    video_id?: number;
    tipo?: string;
    tamano_original_mb?: number;
    porcentaje_compresion?: number | null;
    thumbnail_url?: string;
    error_type?: string;
}

// ============================================================================
// TIPOS LOCALES
// ============================================================================

/**
 * Interfaz mínima del Bootstrap Modal que usa esta clase.
 * Evita depender del namespace 'bootstrap' (UMD) en archivos de script puro.
 * Patrón equivalente a FotoCapturada en camara_integrada.ts.
 */
interface BsModal {
    show(): void;
    hide(): void;
    dispose(): void;
}

// ============================================================================
// CLASE PRINCIPAL
// ============================================================================

class CamaraVideo {

    // ── Límites ──────────────────────────────────────────────────────────────
    private static readonly AUTO_STOP_BYTES = CV_AUTO_STOP_BYTES;

    // ── Referencias al DOM ───────────────────────────────────────────────────
    // PATRÓN del proyecto: declarar como Type | null = null y asignar en el constructor.
    // Esto satisface strictPropertyInitialization sin necesitar el operador !.
    private modalEl: HTMLElement | null = null;
    private bsModal: BsModal | null = null;
    private videoEl: HTMLVideoElement | null = null;

    // Paneles de controles inferiores (uno por estado de la máquina)
    private panelIdle: HTMLElement | null = null;
    private panelGrabando: HTMLElement | null = null;
    private panelPreview: HTMLElement | null = null;
    private panelSubiendo: HTMLElement | null = null;

    // Botones de acción
    private btnGrabar: HTMLButtonElement | null = null;
    private btnDetener: HTMLButtonElement | null = null;
    private btnSubir: HTMLButtonElement | null = null;
    private btnDescartar: HTMLButtonElement | null = null;

    // Barra de progreso de grabación (indica MB usados en tiempo real)
    private contProgreso: HTMLElement | null = null;
    private progressBar: HTMLElement | null = null;
    private labelMB: HTMLElement | null = null;
    private labelTiempo: HTMLElement | null = null;

    // Selector de tipo + aviso + descripción (visibles en estado preview/subiendo)
    private contTipo: HTMLElement | null = null;
    private previewActions: HTMLElement | null = null;   // Descartar + Guardar dentro del overlay
    private tipoCards: HTMLElement | null = null;
    private avisoCont: HTMLElement | null = null;
    private descripcionInput: HTMLTextAreaElement | null = null;

    // Indicadores de progreso de subida al servidor
    private contProgressSubida: HTMLElement | null = null;
    private barraSubida: HTMLElement | null = null;
    private textoSubida: HTMLElement | null = null;
    private contFFmpeg: HTMLElement | null = null;

    // Mensaje de error inline (visible en preview/subiendo, dentro del overlay de tipo)
    private errorCont: HTMLElement | null = null;
    private mensajeError: HTMLElement | null = null;

    // Mensaje de error superior (visible en idle/grabando, flotando sobre el video)
    private errorContTop: HTMLElement | null = null;
    private mensajeErrorTop: HTMLElement | null = null;

    // ── Estado interno ───────────────────────────────────────────────────────
    private stream: MediaStream | null = null;
    private recorder: MediaRecorder | null = null;
    private chunks: BlobPart[] = [];
    private totalBytes = 0;
    private videoBlob: Blob | null = null;
    private estado: EstadoCamaraVideo = 'idle';

    // ── Cronómetro de grabación ───────────────────────────────────────────────
    private tiempoInicioMs = 0;          // Date.now() cuando arranca la grabación
    private intervaloTiempo: ReturnType<typeof setInterval> | null = null;

    // ── Tap-to-focus (mismo patrón que CamaraIntegrada) ──────────────────────
    private abortController: AbortController | null = null;  // Cancela listeners de tap
    private ultimoEnfoque = 0;                               // Timestamp para debounce
    private enfocandoActualmente = false;                    // Flag para evitar solapamientos

    // ────────────────────────────────────────────────────────────────────────
    // CONSTRUCTOR
    // ────────────────────────────────────────────────────────────────────────

    constructor() {
        // EXPLICACIÓN: Asignamos TODAS las propiedades primero (aunque queden null
        // si el elemento no existe), luego verificamos si el modal está presente.
        // Esto es requerido por strictPropertyInitialization de TypeScript.

        this.modalEl = document.getElementById('modalCamaraVideo');

        // Si el modal no existe en esta página, no hay nada más que hacer.
        // Todas las propiedades quedan en null y el módulo no hace nada.
        if (!this.modalEl) return;

        this.bsModal = new bootstrap.Modal(this.modalEl);

        // ── DOM: elementos del visor y controles ──
        this.videoEl            = document.getElementById('cvVideoEl')            as HTMLVideoElement;
        this.panelIdle          = document.getElementById('cvPanelIdle');
        this.panelGrabando      = document.getElementById('cvPanelGrabando');
        this.panelPreview       = document.getElementById('cvPanelPreview');
        this.panelSubiendo      = document.getElementById('cvPanelSubiendo');
        this.btnGrabar          = document.getElementById('cvBtnGrabar')          as HTMLButtonElement;
        this.btnDetener         = document.getElementById('cvBtnDetener')         as HTMLButtonElement;
        this.btnSubir           = document.getElementById('cvBtnSubir')           as HTMLButtonElement;
        this.btnDescartar       = document.getElementById('cvBtnDescartar')       as HTMLButtonElement;
        this.contProgreso       = document.getElementById('cvContProgreso');
        this.progressBar        = document.getElementById('cvProgressBar');
        this.labelMB            = document.getElementById('cvLabelMB');
        this.labelTiempo        = document.getElementById('cvLabelTiempo');
        this.contTipo           = document.getElementById('cvContTipo');
        this.previewActions     = document.getElementById('cvPreviewActions');
        this.tipoCards          = document.getElementById('cvTipoCards');
        this.avisoCont          = document.getElementById('cvAvisoCont');
        this.descripcionInput   = document.getElementById('cvDescripcion')        as HTMLTextAreaElement;
        this.contProgressSubida = document.getElementById('cvContProgressSubida');
        this.barraSubida        = document.getElementById('cvBarraSubida');
        this.textoSubida        = document.getElementById('cvTextoSubida');
        this.contFFmpeg         = document.getElementById('cvContFFmpeg');
        this.errorCont          = document.getElementById('cvErrorCont');
        this.mensajeError       = document.getElementById('cvMensajeError');
        this.errorContTop       = document.getElementById('cvErrorContTop');
        this.mensajeErrorTop    = document.getElementById('cvMensajeErrorTop');

        this.registrarEventos();
    }

    // ────────────────────────────────────────────────────────────────────────
    // REGISTRO DE EVENTOS
    // ────────────────────────────────────────────────────────────────────────

    private registrarEventos(): void {
        // Botón externo que abre el modal (en el header de la sección galería)
        const btnAbrir = document.getElementById('btnAbrirCamaraVideo');
        if (btnAbrir) {
            btnAbrir.addEventListener('click', () => this.abrir());
        }

        // Botones de la máquina de estados
        this.btnGrabar?.addEventListener('click',    () => this.iniciarGrabacion());
        this.btnDetener?.addEventListener('click',   () => this.detenerGrabacion());
        this.btnSubir?.addEventListener('click',     () => void this.subirVideo());
        this.btnDescartar?.addEventListener('click', () => this.descartar());

        // Limpiar stream y recursos cuando Bootstrap cierra el modal
        this.modalEl?.addEventListener('hidden.bs.modal', () => this.liberarRecursos());

        // Avisos contextuales al seleccionar tipo de video
        // También limpia el error "elige el tipo" si estaba visible
        if (this.tipoCards) {
            const radios = this.tipoCards.querySelectorAll<HTMLInputElement>('input[type="radio"]');
            radios.forEach(radio => {
                radio.addEventListener('change', () => {
                    this.actualizarAviso(radio.value);
                    this.ocultarError();
                });
            });
        }
    }

    // ────────────────────────────────────────────────────────────────────────
    // ABRIR MODAL
    // ────────────────────────────────────────────────────────────────────────

    async abrir(): Promise<void> {
        if (!this.bsModal) return;
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

    private async activarCamara(): Promise<void> {
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
                    width:  { ideal: 1920 },
                    height: { ideal: 1080 },
                },
                audio: true,
            });

            if (this.videoEl) {
                this.videoEl.srcObject = this.stream;
                this.videoEl.muted     = true;   // Sin eco en el preview en vivo
                this.videoEl.controls  = false;
            }

            // Activar tap-to-focus (solo en dispositivos que lo soporten)
            this.configurarTapToFocus();
        } catch (err: unknown) {
            const msg = err instanceof Error ? err.message : String(err);
            this.mostrarError(
                `No se pudo acceder a la cámara.\n` +
                `Verifica los permisos del navegador.\n\n(${msg})`
            );
        }
    }

    // ────────────────────────────────────────────────────────────────────────
    // INICIAR GRABACIÓN
    // ────────────────────────────────────────────────────────────────────────

    iniciarGrabacion(): void {
        if (!this.stream) {
            this.mostrarError('No hay cámara activa. Cierra y vuelve a abrir el grabador.');
            return;
        }

        this.chunks     = [];
        this.totalBytes = 0;
        this.actualizarContador(0);

        // Elegir el mejor MIME type que soporte este navegador
        const tipoMime = this.elegirMimeType();

        try {
            this.recorder = new MediaRecorder(this.stream, {
                mimeType: tipoMime || undefined,
            });
        } catch {
            // Fallback sin especificar mimeType — el navegador elige el predeterminado
            this.recorder = new MediaRecorder(this.stream);
        }

        /*
         * EXPLICACIÓN — timeslice=1000:
         * MediaRecorder.start(ms) dispara ondataavailable cada `ms` milisegundos.
         * Con 1000 ms obtenemos un chunk por segundo → el contador de MB se
         * actualiza en tiempo real sin consumir demasiada RAM ni interrumpir el stream.
         */
        this.recorder.ondataavailable = (e: BlobEvent) => this.onChunk(e);
        this.recorder.onstop          = ()             => this.onRecorderStop();

        this.recorder.start(1000);
        this.tiempoInicioMs = Date.now();
        this.intervaloTiempo = setInterval(() => this.actualizarTiempo(), 1000);
        this.setEstado('grabando');
    }

    // ────────────────────────────────────────────────────────────────────────
    // CHUNK RECIBIDO — actualizar contador en tiempo real
    // ────────────────────────────────────────────────────────────────────────

    private onChunk(e: BlobEvent): void {
        if (e.data.size === 0) return;

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

    detenerGrabacion(): void {
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

    private onRecorderStop(): void {
        // Detener el cronómetro al terminar la grabación
        if (this.intervaloTiempo !== null) {
            clearInterval(this.intervaloTiempo);
            this.intervaloTiempo = null;
        }

        const tipoMime = this.recorder?.mimeType || 'video/webm';
        this.videoBlob = new Blob(this.chunks, { type: tipoMime });

        // Sustituir el stream en vivo por el video grabado para que el usuario
        // pueda revisarlo antes de decidir si sube o descarta
        const urlPreview = URL.createObjectURL(this.videoBlob);
        if (this.videoEl) {
            this.videoEl.srcObject = null;
            this.videoEl.src       = urlPreview;
            this.videoEl.muted     = false;  // El técnico puede escuchar el audio grabado
            this.videoEl.controls  = true;
        }

        this.setEstado('preview');
    }

    // ────────────────────────────────────────────────────────────────────────
    // SUBIR VIDEO AL SERVIDOR
    // ────────────────────────────────────────────────────────────────────────

    async subirVideo(): Promise<void> {
        if (!this.tipoCards) return;

        // Validar que se eligió un tipo antes de subir
        const tipoRadio = this.tipoCards.querySelector<HTMLInputElement>('input[type="radio"]:checked');
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
        const csrfInput = document.querySelector<HTMLInputElement>('[name=csrfmiddlewaretoken]');
        if (csrfInput) {
            formData.append('csrfmiddlewaretoken', csrfInput.value);
        }

        formData.append('form_type',   'subir_video');
        formData.append('tipo',        tipoRadio.value);
        formData.append('descripcion', this.descripcionInput?.value?.trim() || '');

        // El archivo se nombra con timestamp para garantizar unicidad
        const nombreArchivo = `grabacion_${Date.now()}.webm`;
        formData.append('video', this.videoBlob, nombreArchivo);

        // ── XHR — mismo patrón y timeout que upload_video.ts ──
        const xhr = new XMLHttpRequest();

        // Progreso de subida → actualizar barra
        xhr.upload.addEventListener('progress', (e: ProgressEvent) => {
            if (e.lengthComputable) {
                const pct = Math.round((e.loaded / e.total) * 100);
                this.actualizarProgressSubida(pct);
                if (pct >= 100) {
                    // Upload completo → FFmpeg procesando en el servidor
                    if (this.contProgressSubida) this.contProgressSubida.style.display = 'none';
                    if (this.contFFmpeg)         this.contFFmpeg.style.display         = 'block';
                }
            }
        });

        // Respuesta del servidor
        xhr.addEventListener('load', () => {
            try {
                const data: CvVideoUploadResponse = JSON.parse(xhr.responseText);
                if (data.success) {
                    // Éxito — recargar la página para mostrar el video en la galería
                    setTimeout(() => window.location.reload(), 1200);
                } else {
                    this.setEstado('preview');
                    this.mostrarError(data.error || 'Error desconocido al guardar el video.');
                }
            } catch {
                this.setEstado('preview');
                this.mostrarError(
                    `Error inesperado del servidor (código ${xhr.status}). Intenta de nuevo.`
                );
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

    descartar(): void {
        // Liberar la URL del Blob del preview para evitar memory leaks
        if (this.videoEl?.src?.startsWith('blob:')) {
            URL.revokeObjectURL(this.videoEl.src);
        }

        // Restaurar stream en vivo en el visor
        if (this.videoEl) {
            this.videoEl.src       = '';
            this.videoEl.srcObject = this.stream;
            this.videoEl.muted     = true;
            this.videoEl.controls  = false;
        }

        // Limpiar datos de la grabación descartada
        this.chunks     = [];
        this.totalBytes = 0;
        this.videoBlob  = null;
        this.recorder   = null;

        // Limpiar selección de tipo y descripción
        if (this.tipoCards) {
            this.tipoCards
                .querySelectorAll<HTMLInputElement>('input[type="radio"]')
                .forEach(r => { r.checked = false; });
        }
        if (this.descripcionInput) this.descripcionInput.value = '';
        if (this.avisoCont) {
            this.avisoCont.textContent = '';
            this.avisoCont.className   = 'tipo-imagen-aviso d-none mt-2';
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
    private elegirMimeType(): string {
        const candidatos = [
            'video/webm;codecs=vp9,opus',
            'video/webm;codecs=vp8,opus',
            'video/webm;codecs=vp9',
            'video/webm;codecs=vp8',
            'video/webm',
            'video/mp4',  // Safari / iOS (soporte MediaRecorder experimental en iOS 14.3+)
        ];
        for (const tipo of candidatos) {
            if (MediaRecorder.isTypeSupported(tipo)) return tipo;
        }
        return ''; // Deja que el navegador elija el predeterminado
    }

    // ────────────────────────────────────────────────────────────────────────
    // HELPER — CRONÓMETRO EN TIEMPO REAL
    // ────────────────────────────────────────────────────────────────────────

    /** Actualiza el label de tiempo transcurrido cada segundo (disparado por setInterval). */
    private actualizarTiempo(): void {
        if (!this.labelTiempo) return;
        const segundos = Math.floor((Date.now() - this.tiempoInicioMs) / 1000);
        const mm = Math.floor(segundos / 60);
        const ss = String(segundos % 60).padStart(2, '0');
        // Conservar el icono REC (primer hijo) y reemplazar solo el texto
        const icono = this.labelTiempo.querySelector('i');
        this.labelTiempo.textContent = `${mm}:${ss}`;
        if (icono) this.labelTiempo.prepend(icono);
    }

    // ────────────────────────────────────────────────────────────────────────
    // HELPER — CONTADOR EN TIEMPO REAL
    // ────────────────────────────────────────────────────────────────────────

    /**
     * Actualiza la barra de progreso y el label de MB.
     * Color: verde (0-60%) → amarillo (60-85%) → rojo (85-100%)
     */
    private actualizarContador(bytes: number): void {
        const AUTO_STOP = CamaraVideo.AUTO_STOP_BYTES;
        const mb        = bytes / (1024 * 1024);
        const pct       = Math.min((bytes / AUTO_STOP) * 100, 100);

        if (this.progressBar) {
            this.progressBar.style.width = `${pct}%`;
            this.progressBar.setAttribute('aria-valuenow', String(Math.round(pct)));
            this.progressBar.classList.remove('bg-success', 'bg-warning', 'bg-danger');
            if (pct < 60) {
                this.progressBar.classList.add('bg-success');
            } else if (pct < 85) {
                this.progressBar.classList.add('bg-warning');
            } else {
                this.progressBar.classList.add('bg-danger');
            }
        }

        if (this.labelMB) {
            this.labelMB.textContent = `${mb.toFixed(1)} MB / ${CV_MAX_LABEL_MB} MB`;
        }
        // Resetear el label de tiempo al limpiar el contador (bytes=0 → estado inicial)
        if (bytes === 0 && this.labelTiempo) {
            const icono = this.labelTiempo.querySelector('i');
            this.labelTiempo.textContent = '0:00';
            if (icono) this.labelTiempo.prepend(icono);
        }
    }

    // ────────────────────────────────────────────────────────────────────────
    // HELPER — AVISO CONTEXTUAL POR TIPO
    // ────────────────────────────────────────────────────────────────────────

    private actualizarAviso(tipo: string): void {
        if (!this.avisoCont) return;
        const aviso = CV_AVISOS[tipo];
        if (aviso) {
            this.avisoCont.textContent = aviso.texto;
            this.avisoCont.className   = `tipo-imagen-aviso ${aviso.clase} mt-2`;
        } else {
            this.avisoCont.textContent = '';
            this.avisoCont.className   = 'tipo-imagen-aviso d-none mt-2';
        }
    }

    // ────────────────────────────────────────────────────────────────────────
    // HELPER — BARRA DE PROGRESO DE SUBIDA XHR
    // ────────────────────────────────────────────────────────────────────────

    private actualizarProgressSubida(pct: number): void {
        if (this.contProgressSubida) this.contProgressSubida.style.display = 'block';
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

    private setEstado(nuevoEstado: EstadoCamaraVideo): void {
        this.estado = nuevoEstado;

        // Ocultar todos los paneles de control
        [this.panelIdle, this.panelGrabando, this.panelPreview, this.panelSubiendo]
            .forEach(p => { if (p) p.style.display = 'none'; });

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
        const panelMap: Record<EstadoCamaraVideo, HTMLElement | null> = {
            idle:     this.panelIdle,
            grabando: this.panelGrabando,
            preview:  this.panelPreview,
            subiendo: this.panelSubiendo,
        };
        const panelActivo = panelMap[nuevoEstado];
        if (panelActivo) panelActivo.style.display = 'flex';

        // En 'subiendo': deshabilitar controles para evitar cambios durante la subida
        if (this.tipoCards) {
            this.tipoCards
                .querySelectorAll<HTMLInputElement>('input[type="radio"]')
                .forEach(r => { r.disabled = nuevoEstado === 'subiendo'; });
        }
        if (this.descripcionInput) {
            this.descripcionInput.disabled = nuevoEstado === 'subiendo';
        }
    }

    // ────────────────────────────────────────────────────────────────────────
    // RESETEAR ESTADO — limpieza completa antes de abrir el modal
    // ────────────────────────────────────────────────────────────────────────

    private resetearEstado(): void {
        // Detener cronómetro si quedó activo
        if (this.intervaloTiempo !== null) {
            clearInterval(this.intervaloTiempo);
            this.intervaloTiempo = null;
        }
        this.tiempoInicioMs = 0;

        this.chunks     = [];
        this.totalBytes = 0;
        this.videoBlob  = null;
        this.recorder   = null;
        this.stream     = null;

        if (this.videoEl) {
            if (this.videoEl.src?.startsWith('blob:')) URL.revokeObjectURL(this.videoEl.src);
            this.videoEl.src       = '';
            this.videoEl.srcObject = null;
            this.videoEl.controls  = false;
            this.videoEl.muted     = true;
        }

        // Limpiar formulario de tipo y descripción
        if (this.tipoCards) {
            this.tipoCards
                .querySelectorAll<HTMLInputElement>('input[type="radio"]')
                .forEach(r => { r.checked = false; r.disabled = false; });
        }
        if (this.descripcionInput) {
            this.descripcionInput.value    = '';
            this.descripcionInput.disabled = false;
        }
        if (this.avisoCont) {
            this.avisoCont.textContent = '';
            this.avisoCont.className   = 'tipo-imagen-aviso d-none mt-2';
        }

        // Limpiar indicadores de subida
        if (this.contProgressSubida) this.contProgressSubida.style.display = 'none';
        if (this.contFFmpeg)         this.contFFmpeg.style.display         = 'none';
        if (this.barraSubida)        this.barraSubida.style.width           = '0%';
        if (this.textoSubida)        this.textoSubida.textContent           = 'Subiendo…';

        this.actualizarContador(0);
        this.ocultarError();
        this.setEstado('idle');
    }

    // ────────────────────────────────────────────────────────────────────────
    // LIBERAR RECURSOS — al cerrar el modal
    // ────────────────────────────────────────────────────────────────────────

    private liberarRecursos(): void {
        // Detener cronómetro si quedó activo al cerrar el modal
        if (this.intervaloTiempo !== null) {
            clearInterval(this.intervaloTiempo);
            this.intervaloTiempo = null;
        }

        // Cancelar listeners de tap-to-focus
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
        this.enfocandoActualmente = false;

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
            if (this.videoEl.src?.startsWith('blob:')) URL.revokeObjectURL(this.videoEl.src);
            this.videoEl.src       = '';
            this.videoEl.srcObject = null;
        }
    }

    // ────────────────────────────────────────────────────────────────────────
    // TAP-TO-FOCUS — mismo patrón que CamaraIntegrada
    // ────────────────────────────────────────────────────────────────────────

    /**
     * Configura los listeners de tap/click para hacer foco en el punto tocado.
     * Solo activa si el dispositivo soporta 'single-shot' focusMode.
     */
    private configurarTapToFocus(): void {
        if (!this.videoEl || !this.stream) return;

        const videoTrack = this.stream.getVideoTracks()[0];
        if (!this.verificarSoporteFocus(videoTrack)) {
            console.log('⚠️ Dispositivo no soporta tap-to-focus (single-shot no disponible)');
            return;
        }

        this.abortController = new AbortController();
        const signal = this.abortController.signal;

        // Click en escritorio
        this.videoEl.addEventListener('click', (e: MouseEvent) => {
            void this.enfocarEnPunto({ clientX: e.clientX, clientY: e.clientY });
        }, { signal });

        // Touch en móviles — sin MouseEvent sintético
        this.videoEl.addEventListener('touchstart', (e: TouchEvent) => {
            e.preventDefault();
            const touch = e.touches[0];
            void this.enfocarEnPunto({ clientX: touch.clientX, clientY: touch.clientY });
        }, { signal, passive: false });

        console.log('✅ Tap-to-focus configurado (grabador de video)');
    }

    /** Verifica si el track soporta single-shot focus (necesario para tap-to-focus). */
    private verificarSoporteFocus(videoTrack: MediaStreamTrack): boolean {
        if (typeof videoTrack.getCapabilities !== 'function') return false;
        const capabilities: any = videoTrack.getCapabilities();
        if (!capabilities || !Array.isArray(capabilities.focusMode)) return false;
        return capabilities.focusMode.includes('single-shot');
    }

    /**
     * Enfoca en el punto tocado/clickeado.
     * Aplica single-shot, muestra indicador visual y restaura continuous.
     */
    private async enfocarEnPunto(punto: { clientX: number; clientY: number }): Promise<void> {
        // Debounce: ignorar si han pasado menos de 500 ms desde el último toque
        const ahora = Date.now();
        if (ahora - this.ultimoEnfoque < 500) return;

        // Si ya hay un enfoque en progreso, mostrar feedback y salir
        if (this.enfocandoActualmente) {
            this.mostrarIndicadorEnfoqueBloqueado(punto);
            return;
        }

        if (!this.videoEl || !this.stream) return;

        this.ultimoEnfoque       = ahora;
        this.enfocandoActualmente = true;

        const videoTrack = this.stream.getVideoTracks()[0];
        const FOCUS_RESTORE_DELAY_MS = 800;
        let enfoqueOriginalMode = 'continuous';

        try {
            const rect = this.videoEl.getBoundingClientRect();
            const x = (punto.clientX - rect.left) / rect.width;
            const y = (punto.clientY - rect.top)  / rect.height;

            if (x < 0 || x > 1 || y < 0 || y > 1) return;

            const settings: any = videoTrack.getSettings();
            enfoqueOriginalMode = settings.focusMode || 'continuous';

            const enfoquePromise = videoTrack.applyConstraints({
                advanced: [{ focusMode: 'single-shot', pointsOfInterest: [{ x, y }] } as any]
            });
            const timeoutPromise = new Promise<void>((_, reject) =>
                setTimeout(() => reject(new Error('Timeout de enfoque (2s)')), 2000)
            );

            await Promise.race([enfoquePromise, timeoutPromise]);

            this.mostrarIndicadorEnfoque(
                punto.clientX - rect.left,
                punto.clientY - rect.top
            );

            await new Promise(resolve => setTimeout(resolve, FOCUS_RESTORE_DELAY_MS));
            await videoTrack.applyConstraints({
                advanced: [{ focusMode: enfoqueOriginalMode } as any]
            });

        } catch {
            // Restaurar modo original incluso en error
            try {
                await videoTrack.applyConstraints({
                    advanced: [{ focusMode: enfoqueOriginalMode } as any]
                });
            } catch { /* silencioso — dispositivo no soporta restaurar */ }
        } finally {
            this.enfocandoActualmente = false;
        }
    }

    /** Indicador visual de enfoque en el punto tocado (cuadrado blanco → verde). */
    private mostrarIndicadorEnfoque(x: number, y: number): void {
        if (!this.videoEl) return;
        const container = this.videoEl.parentElement;
        if (!container) return;

        const indicator = document.createElement('div');
        indicator.className  = 'focus-indicator';
        indicator.style.left = `${x}px`;
        indicator.style.top  = `${y}px`;
        container.appendChild(indicator);

        requestAnimationFrame(() => indicator.classList.add('focus-indicator--focusing'));

        setTimeout(() => {
            indicator.classList.add('focus-indicator--done');
            setTimeout(() => indicator.remove(), 300);
        }, 700);
    }

    /** Indicador visual cuando ya hay un enfoque en progreso (amarillo pulsante). */
    private mostrarIndicadorEnfoqueBloqueado(punto: { clientX: number; clientY: number }): void {
        if (!this.videoEl) return;
        const container = this.videoEl.parentElement;
        if (!container) return;

        const rect = this.videoEl.getBoundingClientRect();
        const indicator = document.createElement('div');
        indicator.className  = 'focus-indicator focus-indicator--busy';
        indicator.style.left = `${punto.clientX - rect.left}px`;
        indicator.style.top  = `${punto.clientY - rect.top}px`;
        container.appendChild(indicator);

        setTimeout(() => indicator.remove(), 600);
    }

    // ────────────────────────────────────────────────────────────────────────
    // HELPERS — ERRORES
    // ────────────────────────────────────────────────────────────────────────

    private mostrarError(msg: string): void {
        /*
         * En estados 'preview' y 'subiendo', el error se muestra inline dentro
         * del overlay de tipo (cvContTipo), justo encima de los botones Descartar/Guardar.
         * En 'idle' y 'grabando', cvContTipo está oculto → usar el elemento flotante
         * en la parte superior del visor (cvErrorContTop).
         */
        const esPreviewOSubiendo = this.estado === 'preview' || this.estado === 'subiendo';
        if (esPreviewOSubiendo) {
            if (this.errorCont)    this.errorCont.style.display  = 'block';
            if (this.mensajeError) this.mensajeError.textContent = msg;
        } else {
            if (this.errorContTop)    this.errorContTop.style.display  = 'block';
            if (this.mensajeErrorTop) this.mensajeErrorTop.textContent = msg;
        }
    }

    private ocultarError(): void {
        if (this.errorCont)       this.errorCont.style.display       = 'none';
        if (this.mensajeError)    this.mensajeError.textContent       = '';
        if (this.errorContTop)    this.errorContTop.style.display     = 'none';
        if (this.mensajeErrorTop) this.mensajeErrorTop.textContent    = '';
    }
}

// ============================================================================
// INICIALIZACIÓN — solo si el modal existe en esta página
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('modalCamaraVideo')) {
        new CamaraVideo();
    }
});
