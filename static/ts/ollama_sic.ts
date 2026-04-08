/**
 * ollama_sic.ts — Mejora de Diagnóstico SIC con IA (Ollama)
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo maneja toda la lógica del botón "Mejorar Diag. con IA" en el
 * detalle de la orden de servicio. El flujo tiene DOS FASES:
 *
 * FASE 1 — Configuración (al abrir el modal):
 *   - Se muestra el selector de modelo y el botón "Generar mejora"
 *   - El técnico elige el modelo que quiere probar
 *   - Al hacer clic en "Generar", pasa a la Fase 2
 *
 * FASE 2 — Resultado:
 *   - Panel izquierdo: texto original del técnico (referencia inmutable)
 *   - Panel derecho: spinner → texto mejorado por el modelo seleccionado
 *   - Acciones: Aceptar / Reintentar / Cambiar modelo (vuelve a Fase 1)
 *
 * DOBLE VALIDACIÓN del botón principal:
 *   - El diagnóstico debe tener ≥20 caracteres
 *   - El diagnóstico debe estar GUARDADO (sin cambios pendientes)
 *
 * IMPORTANTE: La IA solo sugiere mejoras de redacción.
 * Nunca cambia el contenido técnico del diagnóstico.
 */

// Constantes de configuración
const OLLAMA_MIN_CHARS: number = 20;
const OLLAMA_ENDPOINT: string = '/servicio-tecnico/api/pulir-diagnostico-sic/';

// ============================================================================
// FUNCIÓN: Obtener el CSRF token desde las cookies
// Soporta el nombre personalizado del proyecto (sigma_csrftoken) y el estándar.
// ============================================================================
function getOllamaCsrfToken(): string {
    const cookieNames: string[] = ['sigma_csrftoken', 'csrftoken'];
    for (const name of cookieNames) {
        const regex: RegExp = new RegExp(`(?:^|;\\s*)${name}=([^;]+)`);
        const match: RegExpMatchArray | null = document.cookie.match(regex);
        if (match) return decodeURIComponent(match[1]);
    }
    return '';
}

// Interfaces para tipado de la respuesta del API
interface OllamaResponse {
    success: boolean;
    diagnostico_mejorado?: string;
    modelo_usado?: string;
    error?: string;
}

interface DatosEquipo {
    tipoEquipo: string;
    marca: string;
    modelo: string;
    gama: string;
    equipoEnciende: string;
    fallaIdSelector: string;
}

// ============================================================================
// FUNCIÓN PRINCIPAL: iniciarMejorarDiagSIC
// Recibe las referencias del DOM ya validadas y registra todos los listeners.
// ============================================================================
function iniciarMejorarDiagSIC(
    textarea: HTMLTextAreaElement,
    botonMejorar: HTMLButtonElement,
    modalEl: HTMLElement,
    datosEquipo: DatosEquipo
): void {

    // Instanciar el modal de Bootstrap
    const modal = new bootstrap.Modal(modalEl);

    // --- Referencias FASE 1 (configuración) ---
    const faseConfig      = modalEl.querySelector('#ollamaFaseConfig') as HTMLElement;
    const selectorModelo  = modalEl.querySelector('#ollamaModeloSelector') as HTMLSelectElement;
    const btnGenerar      = modalEl.querySelector('#btnGenerarMejora') as HTMLButtonElement;

    // --- Referencias FASE 2 (resultado) ---
    const faseResultado   = modalEl.querySelector('#ollamaFaseResultado') as HTMLElement;
    const modeloActivo    = modalEl.querySelector('#ollamaModeloActivo') as HTMLElement;
    const btnCambiarMod   = modalEl.querySelector('#btnCambiarModelo') as HTMLButtonElement;
    const panelOriginal   = modalEl.querySelector('#diagOriginalTexto') as HTMLElement;
    const spinnerMejorado = modalEl.querySelector('#diagMejoradoSpinner') as HTMLElement;
    const textMejorado    = modalEl.querySelector('#diagMejoradoContenido') as HTMLElement;
    const alertaError     = modalEl.querySelector('#diagErrorAlerta') as HTMLElement;
    const textoError      = modalEl.querySelector('#diagErrorTexto') as HTMLElement;
    const diagModeloBadge = modalEl.querySelector('#diagModeloBadge') as HTMLElement;

    // --- Referencias footer ---
    const botonesResultado = modalEl.querySelector('#ollamaBotonesResultado') as HTMLElement;
    const btnAceptar       = modalEl.querySelector('#btnAceptarMejora') as HTMLButtonElement;
    const btnReintentar    = modalEl.querySelector('#btnReintentar') as HTMLButtonElement;

    // Guardia: si falta cualquier elemento no registrar nada
    if (!faseConfig || !selectorModelo || !btnGenerar ||
        !faseResultado || !modeloActivo || !btnCambiarMod ||
        !panelOriginal || !spinnerMejorado || !textMejorado ||
        !alertaError || !textoError || !diagModeloBadge ||
        !botonesResultado || !btnAceptar || !btnReintentar) {
        console.warn('[OllamaIA] Faltan elementos del modal — verificar el template.');
        return;
    }

    // Estado interno del módulo
    let textoOriginal: string = '';
    let textoPropuesto: string = '';
    let cargando: boolean = false;

    // ========================================================================
    // VALOR GUARDADO EN BASE DE DATOS
    // Al inicializar, registramos el texto actual como el "guardado".
    // Se actualiza cuando el formulario se guarda exitosamente.
    // ========================================================================
    let textoGuardadoEnBD: string = textarea.value.trim();

    // ========================================================================
    // EVALUAR ESTADO DEL BOTÓN PRINCIPAL — DOBLE VALIDACIÓN:
    //   1) El diagnóstico debe tener ≥20 caracteres
    //   2) El diagnóstico debe estar guardado (sin cambios pendientes)
    // ========================================================================
    function evaluarEstadoBoton(): void {
        const texto: string = textarea.value.trim();
        const suficiente: boolean = texto.length >= OLLAMA_MIN_CHARS;
        const guardado: boolean = texto === textoGuardadoEnBD;

        botonMejorar.disabled = !suficiente || !guardado;

        if (!suficiente && !guardado) {
            botonMejorar.title = 'Guarda el formulario primero y asegúrate de tener al menos 20 caracteres';
        } else if (!guardado) {
            botonMejorar.title = 'Guarda el formulario antes de mejorar con IA';
        } else if (!suficiente) {
            const faltan: number = OLLAMA_MIN_CHARS - texto.length;
            botonMejorar.title = `Escribe al menos ${faltan} caracteres más para habilitar`;
        } else {
            botonMejorar.title = 'Mejorar la redacción del diagnóstico con IA';
        }
    }

    // ========================================================================
    // MOSTRAR FASE 1 — Configuración (selector de modelo)
    // ========================================================================
    function mostrarFaseConfig(): void {
        faseConfig.classList.remove('d-none');
        faseResultado.classList.add('d-none');
        botonesResultado.style.setProperty('display', 'none', 'important');
    }

    // ========================================================================
    // MOSTRAR FASE 2 — Resultado (dos paneles)
    // ========================================================================
    function mostrarFaseResultado(): void {
        faseConfig.classList.add('d-none');
        faseResultado.classList.remove('d-none');
        botonesResultado.style.removeProperty('display');
        botonesResultado.style.display = 'flex';
    }

    // ========================================================================
    // ESTADO: CARGANDO — Spinner en el panel derecho
    // Usamos classList con d-none/d-flex de Bootstrap para evitar conflictos.
    // ========================================================================
    function mostrarEstadoCargando(): void {
        spinnerMejorado.classList.remove('d-none');
        spinnerMejorado.classList.add('d-flex');
        textMejorado.style.display = 'none';
        alertaError.style.display = 'none';
        btnAceptar.disabled = true;
        btnReintentar.disabled = true;
        diagModeloBadge.style.display = 'none';
    }

    // ========================================================================
    // ESTADO: RESULTADO EXITOSO — Texto mejorado en el panel derecho
    // ========================================================================
    function mostrarResultado(texto: string, modelo: string): void {
        spinnerMejorado.classList.add('d-none');
        spinnerMejorado.classList.remove('d-flex');
        alertaError.style.display = 'none';
        textMejorado.style.display = 'block';
        textMejorado.textContent = texto;
        btnAceptar.disabled = false;
        btnReintentar.disabled = false;

        if (modelo) {
            diagModeloBadge.textContent = `Modelo: ${modelo}`;
            diagModeloBadge.style.display = 'inline-block';
        }
    }

    // ========================================================================
    // ESTADO: ERROR — Alerta en el panel derecho
    // ========================================================================
    function mostrarError(mensaje: string): void {
        spinnerMejorado.classList.add('d-none');
        spinnerMejorado.classList.remove('d-flex');
        textMejorado.style.display = 'none';
        alertaError.style.display = 'block';
        textoError.textContent = mensaje;
        btnAceptar.disabled = true;
        btnReintentar.disabled = false;
        diagModeloBadge.style.display = 'none';
    }

    // ========================================================================
    // LLAMAR A OLLAMA VÍA AJAX
    // Siempre usa textoOriginal (capturado al abrir el modal) como referencia.
    // El modelo se lee en el momento de llamar (para que Reintentar pueda
    // cambiar de modelo sin volver a la Fase 1 si el técnico lo desea).
    // ========================================================================
    async function llamarOllama(modeloSeleccionado: string): Promise<void> {
        cargando = true;
        mostrarEstadoCargando();

        // Actualizar badge del modelo activo en la barra superior
        modeloActivo.textContent = modeloSeleccionado;

        // Leer la falla principal del equipo para enriquecer el prompt
        const fallaEl = document.querySelector<HTMLTextAreaElement>(datosEquipo.fallaIdSelector);
        const fallaPrincipal: string = fallaEl ? fallaEl.value.trim() : '';

        const formData = new FormData();
        formData.append('diagnostico_sic', textoOriginal);
        formData.append('modelo', modeloSeleccionado);
        formData.append('tipo_equipo', datosEquipo.tipoEquipo);
        formData.append('marca', datosEquipo.marca);
        formData.append('modelo_equipo', datosEquipo.modelo);
        formData.append('gama', datosEquipo.gama);
        formData.append('equipo_enciende', datosEquipo.equipoEnciende);
        formData.append('falla_principal', fallaPrincipal);

        try {
            const response = await fetch(OLLAMA_ENDPOINT, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getOllamaCsrfToken(),
                },
                body: formData,
            });

            const data = await response.json() as OllamaResponse;

            if (data.success && data.diagnostico_mejorado) {
                textoPropuesto = data.diagnostico_mejorado;
                mostrarResultado(data.diagnostico_mejorado, data.modelo_usado ?? modeloSeleccionado);
            } else {
                mostrarError(data.error ?? 'Error desconocido al procesar la solicitud.');
            }
        } catch (err: unknown) {
            const mensaje: string = err instanceof Error
                ? `Error de red: ${err.message}`
                : 'Error de conexión. Verifica que Ollama esté disponible.';
            mostrarError(mensaje);
        } finally {
            cargando = false;
        }
    }

    // ========================================================================
    // REGISTRAR EVENT LISTENERS
    // ========================================================================

    // Habilitar/deshabilitar botón principal mientras el técnico escribe
    textarea.addEventListener('input', evaluarEstadoBoton);

    // Detectar submit del formulario para actualizar el texto "guardado en BD"
    const formConfiguracion = document.querySelector<HTMLFormElement>('#formConfiguracion');
    if (formConfiguracion) {
        formConfiguracion.addEventListener('submit', () => {
            textoGuardadoEnBD = textarea.value.trim();
            evaluarEstadoBoton();
        });
    }

    // Clic en "Mejorar Diag. con IA" — abre el modal en Fase 1 (configuración)
    botonMejorar.addEventListener('click', () => {
        if (cargando) return;

        // Capturar el texto actual como referencia inmutable para esta sesión
        textoOriginal = textarea.value.trim();
        textoPropuesto = '';

        // Poblar el panel izquierdo con el texto original
        panelOriginal.textContent = textoOriginal;

        // Resetear a Fase 1 (el técnico elige modelo y hace clic en Generar)
        mostrarFaseConfig();

        modal.show();
    });

    // Clic en "Generar mejora" — lanza la llamada a Ollama y pasa a Fase 2
    btnGenerar.addEventListener('click', () => {
        if (cargando) return;
        const modelo: string = selectorModelo.value;
        mostrarFaseResultado();
        void llamarOllama(modelo);
    });

    // Clic en "Cambiar modelo" — vuelve a Fase 1 sin cerrar el modal
    btnCambiarMod.addEventListener('click', () => {
        if (cargando) return;
        mostrarFaseConfig();
    });

    // Botón REINTENTAR: vuelve a llamar a Ollama con el mismo modelo
    // (el técnico puede cambiar el selector antes de reintentar si lo desea)
    btnReintentar.addEventListener('click', () => {
        if (cargando) return;
        const modelo: string = selectorModelo.value;
        void llamarOllama(modelo);
    });

    // Botón ACEPTAR: copia el texto mejorado al textarea y cierra el modal
    btnAceptar.addEventListener('click', () => {
        if (textoPropuesto) {
            textarea.value = textoPropuesto;
            // Notificar a otros listeners del cambio (ej: contador de caracteres)
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            // Breve destello verde para confirmar que el texto fue aplicado
            textarea.classList.add('border-success');
            setTimeout(() => textarea.classList.remove('border-success'), 2000);
        }
        modal.hide();
    });

    // Evaluación inicial del botón principal
    evaluarEstadoBoton();
}

// ============================================================================
// INICIALIZACIÓN — Ejecutar cuando el DOM esté completamente cargado
// ============================================================================
document.addEventListener('DOMContentLoaded', function (): void {
    // Solo inicializar si el botón existe (renderiza solo con OLLAMA_ENABLED=True)
    const botonMejorar = document.querySelector<HTMLButtonElement>('#btnMejorarDiagIA');
    if (!botonMejorar) return;

    const textarea = document.querySelector<HTMLTextAreaElement>('#id_diagnostico_sic');
    if (!textarea) return;

    const modalEl = document.querySelector<HTMLElement>('#modalMejorarDiagIA');
    if (!modalEl) return;

    // Leer datos del equipo desde atributos data-* del botón (puestos en el template)
    const datosEquipo: DatosEquipo = {
        tipoEquipo:      botonMejorar.dataset['tipoEquipo'] ?? '',
        marca:           botonMejorar.dataset['marca'] ?? '',
        modelo:          botonMejorar.dataset['modelo'] ?? '',
        gama:            botonMejorar.dataset['gama'] ?? '',
        equipoEnciende:  botonMejorar.dataset['equipoEnciende'] ?? 'true',
        fallaIdSelector: botonMejorar.dataset['fallaSelector'] ?? '#id_falla_principal',
    };

    iniciarMejorarDiagSIC(textarea, botonMejorar, modalEl, datosEquipo);
});
