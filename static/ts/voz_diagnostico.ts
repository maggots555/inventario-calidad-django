/**
 * voz_diagnostico.ts — Dictado por voz para el campo Diagnóstico SIC
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo implementa el botón de micrófono (🎤) que aparece junto al
 * textarea de Diagnóstico SIC en detalle_orden.html. Permite al técnico
 * dictar el diagnóstico en lugar de escribirlo.
 *
 * ARQUITECTURA DE 3 CAPAS (fallback en cascada):
 *
 * Capa 1 — Web Speech API (navegador nativo):
 *   - Funciona en Chrome, Edge y la mayoría de Android.
 *   - No necesita backend ni internet (la transcripción la hace el navegador).
 *   - El texto va apareciendo en tiempo real mientras el técnico habla.
 *   - Se detiene automáticamente cuando deja de hablar (~2 segundos de silencio).
 *
 * Capa 2 — Ollama Whisper (backend, vía /api/transcribir-audio-diagnostico/):
 *   - Activo cuando Web Speech API NO está disponible (Firefox, iOS Safari sin permisos).
 *   - Graba audio con MediaRecorder y lo envía al servidor.
 *   - El servidor usa el modelo Whisper instalado en Ollama para transcribir.
 *
 * Capa 3 — Gemini API (backend, automático si Ollama falla):
 *   - El backend maneja este fallback internamente.
 *   - El frontend no necesita saber qué proveedor respondió.
 *
 * COMPORTAMIENTO:
 * - El texto transcrito se AGREGA al final del texto existente (no lo borra).
 * - El botón tiene 3 estados: inactivo, grabando, procesando.
 * - Compatible con modo oscuro del proyecto.
 * - Mobile-first: toque de 44x44px mínimo (iOS HIG).
 */

// ============================================================================
// CONSTANTES
// ============================================================================

/** URL del endpoint de transcripción en el backend */
const VOZ_ENDPOINT: string = '/servicio-tecnico/api/transcribir-audio-diagnostico/';

/** Tiempo máximo de grabación en milisegundos (60 segundos) */
const VOZ_MAX_DURACION_MS: number = 60_000;

/** Idioma para la transcripción */
const VOZ_IDIOMA: string = 'es-MX';

// ============================================================================
// FUNCIÓN AUXILIAR: Obtener CSRF token desde cookies
// ============================================================================
function getVozCsrfToken(): string {
    const cookieNames: string[] = ['sigma_csrftoken', 'csrftoken'];
    for (const name of cookieNames) {
        const regex: RegExp = new RegExp(`(?:^|;\\s*)${name}=([^;]+)`);
        const match: RegExpMatchArray | null = document.cookie.match(regex);
        if (match) return decodeURIComponent(match[1]);
    }
    return '';
}

// ============================================================================
// INTERFACES
// ============================================================================

interface TranscripcionResponse {
    success: boolean;
    texto?: string;
    proveedor?: string;
    tiempo_ms?: number;
    error?: string;
}

// ============================================================================
// TIPOS para Web Speech API (no siempre en @types/dom estándar)
// ============================================================================
// Nota: no redeclaramos SpeechRecognitionEvent ni SpeechRecognitionErrorEvent
// porque lib.dom.d.ts ya los define. Usamos 'any' en los callbacks para
// evitar conflictos de módulo con las declaraciones nativas del navegador.

// ============================================================================
// CLASE PRINCIPAL: VozDiagnostico
// Encapsula toda la lógica del botón de micrófono para un textarea específico.
// ============================================================================
class VozDiagnostico {
    private readonly textarea: HTMLTextAreaElement;
    private readonly boton: HTMLButtonElement;
    private readonly indicador: HTMLElement;

    // Estado de grabación
    private grabando: boolean = false;
    private mediaRecorder: MediaRecorder | null = null;
    private audioChunks: Blob[] = [];
    private timerTimeout: number | null = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    private reconocedor: any = null;   // Referencia al SpeechRecognition activo
    private sesionReconocimientoId: number = 0;

    // Web Speech API (puede ser undefined en Firefox)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    private readonly SpeechRecognitionClass: any;
    private readonly usaWebSpeech: boolean;

    constructor(textarea: HTMLTextAreaElement, boton: HTMLButtonElement, indicador: HTMLElement) {
        this.textarea = textarea;
        this.boton = boton;
        this.indicador = indicador;

        // Detectar soporte de Web Speech API
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const win = window as any;
        this.SpeechRecognitionClass = win.SpeechRecognition || win.webkitSpeechRecognition || null;
        this.usaWebSpeech = this.SpeechRecognitionClass !== null;

        this.registrarListeners();
    }

    // --------------------------------------------------------------------------
    // Registrar eventos del botón
    // --------------------------------------------------------------------------
    private registrarListeners(): void {
        this.boton.addEventListener('click', () => {
            if (this.grabando) {
                this.detener();
            } else {
                this.iniciar();
            }
        });
    }

    // --------------------------------------------------------------------------
    // Iniciar grabación — elige el método según soporte del navegador
    // --------------------------------------------------------------------------
    private iniciar(): void {
        if (this.usaWebSpeech) {
            this.iniciarWebSpeech();
        } else {
            this.iniciarMediaRecorder();
        }
    }

    // --------------------------------------------------------------------------
    // Detener grabación activa
    // --------------------------------------------------------------------------
    private detener(): void {
        if (this.timerTimeout !== null) {
            clearTimeout(this.timerTimeout);
            this.timerTimeout = null;
        }

        // Web Speech API: anulamos la referencia ANTES de llamar .stop() para que
        // el evento onend sepa que la detención fue intencional (del botón) y no
        // intente reiniciar una nueva sesión.
        if (this.reconocedor) {
            this.sesionReconocimientoId += 1;
            const rec = this.reconocedor;
            this.reconocedor = null;        // ← primero null
            try { rec.stop(); } catch { /* ignorar si ya estaba inactivo */ }
        }

        if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
            this.mediaRecorder.stop();
            // El resto del flujo lo maneja el evento 'onstop'
        }

        this.setEstado('inactivo');
    }

    // ==========================================================================
    // CAPA 1: Web Speech API
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Usamos continuous=true para que el navegador no corte en silencios.
    // Una sola instancia por sesión, SIN reinicio automático.
    // Motivo: al reiniciar con una nueva instancia, Chrome re-entrega el último
    // fragmento de audio de su buffer interno → texto duplicado. La solución
    // es no reiniciar nunca. Si Chrome alcanza su límite (~60s), el texto
    // capturado se guarda y el botón regresa a inactivo para que el técnico
    // presione de nuevo si necesita continuar.
    // ==========================================================================
    private iniciarWebSpeech(): void {
        this.setEstado('grabando');
        const sesionIdActual = ++this.sesionReconocimientoId;

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const rec = new this.SpeechRecognitionClass() as any;
        rec.lang = VOZ_IDIOMA;
        rec.continuous = true;       // No cortar en silencios
        rec.interimResults = true;   // Mostrar texto en tiempo real
        rec.maxAlternatives = 1;

        this.reconocedor = rec;

        let textoBase: string = this.textarea.value;
        let ultimoIndiceFinal: number = -1;
        let ultimoFinalNormalizado: string = '';
        let ultimoFinalTs: number = 0;

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        rec.onresult = (e: any): void => {
            if (this.reconocedor !== rec || this.sesionReconocimientoId !== sesionIdActual) {
                return;
            }

            let parcial = '';
            // Iterar solo desde e.resultIndex — los anteriores ya fueron procesados
            for (let i = e.resultIndex; i < e.results.length; i++) {
                if (e.results[i].isFinal) {
                    // Guardia adicional por si Chrome entrega resultIndex=0 erróneamente
                    if (i > ultimoIndiceFinal) {
                        ultimoIndiceFinal = i;
                        const seg = e.results[i][0].transcript.trim();
                        if (seg) {
                            const segNormalizado = this.normalizarTexto(seg);
                            const ahora = Date.now();
                            const esDuplicadoConsecutivo = (
                                segNormalizado.length > 0 &&
                                segNormalizado === ultimoFinalNormalizado &&
                                (ahora - ultimoFinalTs) < 900
                            );

                            if (!esDuplicadoConsecutivo) {
                                textoBase = this.insertarTexto(textoBase, seg);
                                ultimoFinalNormalizado = segNormalizado;
                                ultimoFinalTs = ahora;
                            }
                        }
                    }
                } else {
                    parcial += e.results[i][0].transcript;
                }
            }
            this.textarea.value = textoBase + (parcial ? ` ${parcial}` : '');
        };

        rec.onend = (): void => {
            if (this.reconocedor !== rec || this.sesionReconocimientoId !== sesionIdActual) {
                return;
            }

            // Guardar siempre el texto capturado hasta este momento
            this.textarea.value = textoBase;
            this.dispatchCambio();
            this.reconocedor = null;
            // Solo cambiar estado si el técnico no ya presionó stop (detener() lo hace antes)
            if (this.grabando) {
                this.mostrarMensaje('Sesión de voz finalizada. Presiona el micrófono para continuar.');
                this.setEstado('inactivo');
            }
        };

        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        rec.onerror = (e: any): void => {
            if (this.reconocedor !== rec || this.sesionReconocimientoId !== sesionIdActual) {
                return;
            }

            if (e.error === 'no-speech' || e.error === 'aborted') {
                // no-speech: silencio — con continuous=true el reconocedor sigue activo
                // aborted: detener() llamó .stop() — flujo normal, onend se encargará
                return;
            }
            if (e.error === 'not-allowed') {
                this.mostrarError('Permiso de micrófono denegado. Revisa la configuración del navegador.');
            } else {
                this.mostrarError(`Error de reconocimiento: ${e.error}`);
            }
            this.textarea.value = textoBase;
            this.reconocedor = null;
            this.setEstado('inactivo');
        };

        rec.start();
    }

    // ==========================================================================
    // CAPA 2: MediaRecorder → Backend (Ollama/Gemini)
    // ==========================================================================
    private iniciarMediaRecorder(): void {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.mostrarError('Este navegador no soporta grabación de audio.');
            return;
        }

        navigator.mediaDevices.getUserMedia({ audio: true, video: false })
            .then((stream: MediaStream) => {
                this.audioChunks = [];

                // Elegir el formato con mejor soporte en el navegador actual
                const mimeType = this.getMimeTypeSoportado();
                const opciones: MediaRecorderOptions = mimeType ? { mimeType } : {};

                this.mediaRecorder = new MediaRecorder(stream, opciones);

                this.mediaRecorder.ondataavailable = (e: BlobEvent): void => {
                    if (e.data && e.data.size > 0) {
                        this.audioChunks.push(e.data);
                    }
                };

                this.mediaRecorder.onstop = (): void => {
                    // Liberar el micrófono
                    stream.getTracks().forEach(track => track.stop());
                    this.enviarAudioAlServidor(mimeType);
                };

                this.mediaRecorder.start(250); // Chunks cada 250ms
                this.setEstado('grabando');

                // Detener automáticamente después del límite de tiempo
                this.timerTimeout = window.setTimeout(() => {
                    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
                        this.mediaRecorder.stop();
                    }
                }, VOZ_MAX_DURACION_MS);
            })
            .catch((err: Error) => {
                if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
                    this.mostrarError('Permiso de micrófono denegado. Revisa la configuración del navegador.');
                } else {
                    this.mostrarError('No se pudo acceder al micrófono: ' + err.message);
                }
                this.setEstado('inactivo');
            });
    }

    /** Detecta el MIME type de audio con mejor soporte en el navegador actual */
    private getMimeTypeSoportado(): string {
        const candidatos: string[] = [
            'audio/webm;codecs=opus',
            'audio/webm',
            'audio/ogg;codecs=opus',
            'audio/ogg',
            'audio/mp4',
        ];
        for (const tipo of candidatos) {
            if (MediaRecorder.isTypeSupported(tipo)) return tipo;
        }
        return '';
    }

    /** Envía el audio grabado al backend para transcripción */
    private enviarAudioAlServidor(mimeType: string): void {
        if (this.audioChunks.length === 0) {
            this.mostrarError('No se capturó audio. Intenta de nuevo.');
            this.setEstado('inactivo');
            return;
        }

        this.setEstado('procesando');

        const extension = this.extensionDesdeMime(mimeType);
        const blob = new Blob(this.audioChunks, { type: mimeType || 'audio/webm' });

        const formData = new FormData();
        formData.append('audio', blob, `diagnostico.${extension}`);
        formData.append('idioma', 'es');

        fetch(VOZ_ENDPOINT, {
            method: 'POST',
            headers: {
                'X-CSRFToken': getVozCsrfToken(),
            },
            body: formData,
        })
            .then(res => res.json())
            .then((data: TranscripcionResponse) => {
                if (data.success && data.texto) {
                    this.textarea.value = this.insertarTexto(this.textarea.value, data.texto);
                    this.dispatchCambio();
                } else {
                    this.mostrarError(data.error || 'Error desconocido al transcribir.');
                }
            })
            .catch((err: Error) => {
                this.mostrarError('Error de conexión al transcribir: ' + err.message);
            })
            .finally(() => {
                this.setEstado('inactivo');
            });
    }

    /** Devuelve la extensión de archivo según el MIME type */
    private extensionDesdeMime(mimeType: string): string {
        if (mimeType.includes('ogg')) return 'ogg';
        if (mimeType.includes('mp4')) return 'mp4';
        return 'webm';
    }

    // ==========================================================================
    // UTILIDADES
    // ==========================================================================

    /**
     * Inserta `nuevo` al final de `base`, con un espacio si base no está vacío.
     * Si base termina en punto, agrega un espacio. Si no termina en nada, agrega
     * un espacio separador.
     */
    private insertarTexto(base: string, nuevo: string): string {
        const baseT = base.trimEnd();
        const nuevoT = nuevo.trim();
        if (!nuevoT) return baseT;

        if (!baseT) return nuevoT;

        const baseTokens = baseT.split(/\s+/);
        const nuevoTokens = nuevoT.split(/\s+/);

        let overlap = 0;
        const limite = Math.min(baseTokens.length, nuevoTokens.length);
        for (let size = limite; size >= 1; size--) {
            const colaBase = baseTokens.slice(baseTokens.length - size).map(token => this.normalizarTexto(token));
            const cabezaNuevo = nuevoTokens.slice(0, size).map(token => this.normalizarTexto(token));
            const coincide = colaBase.length === cabezaNuevo.length && colaBase.every((token, idx) => token === cabezaNuevo[idx]);
            if (coincide) {
                overlap = size;
                break;
            }
        }

        let fragmento = overlap > 0
            ? nuevoTokens.slice(overlap).join(' ').trim()
            : nuevoT;

        if (!fragmento) {
            return baseT;
        }

        if (overlap > 0) {
            return `${baseT} ${fragmento}`.replace(/\s+/g, ' ').trim();
        }

        // Capitalizar la primera letra del nuevo fragmento
        fragmento = fragmento.charAt(0).toUpperCase() + fragmento.slice(1);

        // Si el texto base ya termina en punto o punto y coma, agregar espacio directo
        if (/[.;!?]$/.test(baseT)) {
            return `${baseT} ${fragmento}`;
        }
        // Si no, agregar punto + espacio para separar frases
        return `${baseT}. ${fragmento}`;
    }

    private normalizarTexto(texto: string): string {
        return texto
            .normalize('NFD')
            .replace(/[\u0300-\u036f]/g, '')
            .replace(/[^a-zA-Z0-9ñÑáéíóúÁÉÍÓÚüÜ\s]/g, ' ')
            .replace(/\s+/g, ' ')
            .trim()
            .toLowerCase();
    }

    /** Dispara el evento 'input' en el textarea para que otros listeners reaccionen */
    private dispatchCambio(): void {
        this.textarea.dispatchEvent(new Event('input', { bubbles: true }));
        this.textarea.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // --------------------------------------------------------------------------
    // GESTIÓN DE ESTADOS VISUALES DEL BOTÓN
    // --------------------------------------------------------------------------
    private setEstado(estado: 'inactivo' | 'grabando' | 'procesando'): void {
        this.grabando = estado === 'grabando';

        // Resetear clases
        this.boton.classList.remove('btn-outline-secondary', 'btn-danger', 'btn-warning');
        this.boton.disabled = estado === 'procesando';

        switch (estado) {
            case 'inactivo':
                this.boton.classList.add('btn-outline-secondary');
                this.boton.title = 'Dictar diagnóstico por voz';
                this.boton.innerHTML = '<i class="bi bi-mic"></i>';
                this.indicador.style.display = 'none';
                break;

            case 'grabando':
                this.boton.classList.add('btn-danger');
                this.boton.title = 'Haz clic para detener la grabación';
                this.boton.innerHTML = '<i class="bi bi-mic-fill"></i>';
                this.indicador.style.display = 'inline';
                this.indicador.textContent = this.usaWebSpeech
                    ? 'Escuchando...'
                    : 'Grabando... (clic para detener)';
                break;

            case 'procesando':
                this.boton.classList.add('btn-warning');
                this.boton.title = 'Transcribiendo audio...';
                this.boton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status"></span>';
                this.indicador.style.display = 'inline';
                this.indicador.textContent = 'Transcribiendo...';
                break;
        }
    }

    /** Muestra un mensaje de error breve bajo el botón (en rojo, 5 segundos) */
    private mostrarError(mensaje: string): void {
        this.indicador.style.display = 'inline';
        this.indicador.textContent = mensaje;
        this.indicador.classList.add('text-danger');
        this.indicador.classList.remove('text-muted');

        window.setTimeout(() => {
            this.indicador.style.display = 'none';
            this.indicador.classList.remove('text-danger');
        }, 5000);
    }

    /** Muestra un mensaje informativo breve bajo el botón (en gris, 6 segundos) */
    private mostrarMensaje(mensaje: string): void {
        this.indicador.style.display = 'inline';
        this.indicador.textContent = mensaje;
        this.indicador.classList.add('text-muted');
        this.indicador.classList.remove('text-danger');

        window.setTimeout(() => {
            this.indicador.style.display = 'none';
            this.indicador.classList.remove('text-muted');
        }, 6000);
    }
}

// ============================================================================
// INICIALIZACIÓN
// Espera a que el DOM esté listo y busca el textarea + botón en la página.
// ============================================================================
document.addEventListener('DOMContentLoaded', (): void => {
    const textarea = document.querySelector<HTMLTextAreaElement>('#id_diagnostico_sic');
    const boton = document.querySelector<HTMLButtonElement>('#btnVozDiagnostico');
    const indicador = document.querySelector<HTMLElement>('#vozDiagnosticoIndicador');

    if (!textarea || !boton || !indicador) {
        // Los elementos no existen en esta página — no hacer nada
        return;
    }

    // Instanciar y dejar que el objeto maneje todo
    new VozDiagnostico(textarea, boton, indicador);
});
