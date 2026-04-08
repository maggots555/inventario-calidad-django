"use strict";
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
const OLLAMA_MIN_CHARS = 20;
const OLLAMA_ENDPOINT = '/servicio-tecnico/api/pulir-diagnostico-sic/';
// ============================================================================
// FUNCIÓN: Obtener el CSRF token desde las cookies
// Soporta el nombre personalizado del proyecto (sigma_csrftoken) y el estándar.
// ============================================================================
function getOllamaCsrfToken() {
    const cookieNames = ['sigma_csrftoken', 'csrftoken'];
    for (const name of cookieNames) {
        const regex = new RegExp(`(?:^|;\\s*)${name}=([^;]+)`);
        const match = document.cookie.match(regex);
        if (match)
            return decodeURIComponent(match[1]);
    }
    return '';
}
// ============================================================================
// FUNCIÓN PRINCIPAL: iniciarMejorarDiagSIC
// Recibe las referencias del DOM ya validadas y registra todos los listeners.
// ============================================================================
function iniciarMejorarDiagSIC(textarea, botonMejorar, modalEl, datosEquipo) {
    // Instanciar el modal de Bootstrap
    const modal = new bootstrap.Modal(modalEl);
    // --- Referencias FASE 1 (configuración) ---
    const faseConfig = modalEl.querySelector('#ollamaFaseConfig');
    const selectorModelo = modalEl.querySelector('#ollamaModeloSelector');
    const btnGenerar = modalEl.querySelector('#btnGenerarMejora');
    // --- Referencias FASE 2 (resultado) ---
    const faseResultado = modalEl.querySelector('#ollamaFaseResultado');
    const modeloActivo = modalEl.querySelector('#ollamaModeloActivo');
    const btnCambiarMod = modalEl.querySelector('#btnCambiarModelo');
    const panelOriginal = modalEl.querySelector('#diagOriginalTexto');
    const spinnerMejorado = modalEl.querySelector('#diagMejoradoSpinner');
    const textMejorado = modalEl.querySelector('#diagMejoradoContenido');
    const alertaError = modalEl.querySelector('#diagErrorAlerta');
    const textoError = modalEl.querySelector('#diagErrorTexto');
    const diagModeloBadge = modalEl.querySelector('#diagModeloBadge');
    // --- Referencias footer ---
    const botonesResultado = modalEl.querySelector('#ollamaBotonesResultado');
    const btnAceptar = modalEl.querySelector('#btnAceptarMejora');
    const btnReintentar = modalEl.querySelector('#btnReintentar');
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
    let textoOriginal = '';
    let textoPropuesto = '';
    let cargando = false;
    // ========================================================================
    // VALOR GUARDADO EN BASE DE DATOS
    // Al inicializar, registramos el texto actual como el "guardado".
    // Se actualiza cuando el formulario se guarda exitosamente.
    // ========================================================================
    let textoGuardadoEnBD = textarea.value.trim();
    // ========================================================================
    // EVALUAR ESTADO DEL BOTÓN PRINCIPAL — DOBLE VALIDACIÓN:
    //   1) El diagnóstico debe tener ≥20 caracteres
    //   2) El diagnóstico debe estar guardado (sin cambios pendientes)
    // ========================================================================
    function evaluarEstadoBoton() {
        const texto = textarea.value.trim();
        const suficiente = texto.length >= OLLAMA_MIN_CHARS;
        const guardado = texto === textoGuardadoEnBD;
        botonMejorar.disabled = !suficiente || !guardado;
        if (!suficiente && !guardado) {
            botonMejorar.title = 'Guarda el formulario primero y asegúrate de tener al menos 20 caracteres';
        }
        else if (!guardado) {
            botonMejorar.title = 'Guarda el formulario antes de mejorar con IA';
        }
        else if (!suficiente) {
            const faltan = OLLAMA_MIN_CHARS - texto.length;
            botonMejorar.title = `Escribe al menos ${faltan} caracteres más para habilitar`;
        }
        else {
            botonMejorar.title = 'Mejorar la redacción del diagnóstico con IA';
        }
    }
    // ========================================================================
    // MOSTRAR FASE 1 — Configuración (selector de modelo)
    // ========================================================================
    function mostrarFaseConfig() {
        faseConfig.classList.remove('d-none');
        faseResultado.classList.add('d-none');
        botonesResultado.style.setProperty('display', 'none', 'important');
    }
    // ========================================================================
    // MOSTRAR FASE 2 — Resultado (dos paneles)
    // ========================================================================
    function mostrarFaseResultado() {
        faseConfig.classList.add('d-none');
        faseResultado.classList.remove('d-none');
        botonesResultado.style.removeProperty('display');
        botonesResultado.style.display = 'flex';
    }
    // ========================================================================
    // ESTADO: CARGANDO — Spinner en el panel derecho
    // Usamos classList con d-none/d-flex de Bootstrap para evitar conflictos.
    // ========================================================================
    function mostrarEstadoCargando() {
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
    function mostrarResultado(texto, modelo) {
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
    function mostrarError(mensaje) {
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
    async function llamarOllama(modeloSeleccionado) {
        var _a, _b;
        cargando = true;
        mostrarEstadoCargando();
        // Actualizar badge del modelo activo en la barra superior
        modeloActivo.textContent = modeloSeleccionado;
        // Leer la falla principal del equipo para enriquecer el prompt
        const fallaEl = document.querySelector(datosEquipo.fallaIdSelector);
        const fallaPrincipal = fallaEl ? fallaEl.value.trim() : '';
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
            const data = await response.json();
            if (data.success && data.diagnostico_mejorado) {
                textoPropuesto = data.diagnostico_mejorado;
                mostrarResultado(data.diagnostico_mejorado, (_a = data.modelo_usado) !== null && _a !== void 0 ? _a : modeloSeleccionado);
            }
            else {
                mostrarError((_b = data.error) !== null && _b !== void 0 ? _b : 'Error desconocido al procesar la solicitud.');
            }
        }
        catch (err) {
            const mensaje = err instanceof Error
                ? `Error de red: ${err.message}`
                : 'Error de conexión. Verifica que Ollama esté disponible.';
            mostrarError(mensaje);
        }
        finally {
            cargando = false;
        }
    }
    // ========================================================================
    // REGISTRAR EVENT LISTENERS
    // ========================================================================
    // Habilitar/deshabilitar botón principal mientras el técnico escribe
    textarea.addEventListener('input', evaluarEstadoBoton);
    // Detectar submit del formulario para actualizar el texto "guardado en BD"
    const formConfiguracion = document.querySelector('#formConfiguracion');
    if (formConfiguracion) {
        formConfiguracion.addEventListener('submit', () => {
            textoGuardadoEnBD = textarea.value.trim();
            evaluarEstadoBoton();
        });
    }
    // Clic en "Mejorar Diag. con IA" — abre el modal en Fase 1 (configuración)
    botonMejorar.addEventListener('click', () => {
        if (cargando)
            return;
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
        if (cargando)
            return;
        const modelo = selectorModelo.value;
        mostrarFaseResultado();
        void llamarOllama(modelo);
    });
    // Clic en "Cambiar modelo" — vuelve a Fase 1 sin cerrar el modal
    btnCambiarMod.addEventListener('click', () => {
        if (cargando)
            return;
        mostrarFaseConfig();
    });
    // Botón REINTENTAR: vuelve a llamar a Ollama con el mismo modelo
    // (el técnico puede cambiar el selector antes de reintentar si lo desea)
    btnReintentar.addEventListener('click', () => {
        if (cargando)
            return;
        const modelo = selectorModelo.value;
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
document.addEventListener('DOMContentLoaded', function () {
    var _a, _b, _c, _d, _e, _f;
    // Solo inicializar si el botón existe (renderiza solo con OLLAMA_ENABLED=True)
    const botonMejorar = document.querySelector('#btnMejorarDiagIA');
    if (!botonMejorar)
        return;
    const textarea = document.querySelector('#id_diagnostico_sic');
    if (!textarea)
        return;
    const modalEl = document.querySelector('#modalMejorarDiagIA');
    if (!modalEl)
        return;
    // Leer datos del equipo desde atributos data-* del botón (puestos en el template)
    const datosEquipo = {
        tipoEquipo: (_a = botonMejorar.dataset['tipoEquipo']) !== null && _a !== void 0 ? _a : '',
        marca: (_b = botonMejorar.dataset['marca']) !== null && _b !== void 0 ? _b : '',
        modelo: (_c = botonMejorar.dataset['modelo']) !== null && _c !== void 0 ? _c : '',
        gama: (_d = botonMejorar.dataset['gama']) !== null && _d !== void 0 ? _d : '',
        equipoEnciende: (_e = botonMejorar.dataset['equipoEnciende']) !== null && _e !== void 0 ? _e : 'true',
        fallaIdSelector: (_f = botonMejorar.dataset['fallaSelector']) !== null && _f !== void 0 ? _f : '#id_falla_principal',
    };
    iniciarMejorarDiagSIC(textarea, botonMejorar, modalEl, datosEquipo);
});
//# sourceMappingURL=ollama_sic.js.map