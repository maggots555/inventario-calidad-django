"use strict";
/**
 * ollama_sic.ts — Mejora de Diagnóstico SIC con IA (cascada automática)
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo maneja el botón "Mejorar Diag. con IA" en el detalle de la orden.
 *
 * Flujo (sin selector de modelo):
 *   1. El técnico hace clic → se abre el modal de comparación
 *   2. De inmediato se llama al API en modo automático (sin campo modelo)
 *   3. El backend prueba Gemini en orden y, si fallan, cae a Ollama
 *   4. Se muestra original vs mejorado + el modelo que resolvió
 *   5. Acciones: Aceptar (aplica + GUARDA en BD) / Reintentar / Descartar
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
const GUARDAR_DIAG_ENDPOINT = '/servicio-tecnico/api/guardar-diagnostico-sic/';
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
    // --- Referencias del modal de resultado (ya no hay fase de selector) ---
    const faseResultado = modalEl.querySelector('#ollamaFaseResultado');
    const modeloActivo = modalEl.querySelector('#ollamaModeloActivo');
    const panelOriginal = modalEl.querySelector('#diagOriginalTexto');
    const spinnerMejorado = modalEl.querySelector('#diagMejoradoSpinner');
    const textMejorado = modalEl.querySelector('#diagMejoradoContenido');
    const alertaError = modalEl.querySelector('#diagErrorAlerta');
    const textoError = modalEl.querySelector('#diagErrorTexto');
    const diagModeloBadge = modalEl.querySelector('#diagModeloBadge');
    const diagEstadisticas = modalEl.querySelector('#diagEstadisticas');
    // --- Referencias footer ---
    const botonesResultado = modalEl.querySelector('#ollamaBotonesResultado');
    const btnAceptar = modalEl.querySelector('#btnAceptarMejora');
    const btnReintentar = modalEl.querySelector('#btnReintentar');
    // Guardia: si falta cualquier elemento no registrar nada
    if (!faseResultado || !modeloActivo ||
        !panelOriginal || !spinnerMejorado || !textMejorado ||
        !alertaError || !textoError || !diagModeloBadge ||
        !diagEstadisticas ||
        !botonesResultado || !btnAceptar || !btnReintentar) {
        console.warn('[DiagIA] Faltan elementos del modal — verificar el template.');
        return;
    }
    if (!datosEquipo.ordenId) {
        console.warn('[DiagIA] Falta data-orden-id en el botón — no se podrá guardar al aceptar.');
    }
    // Estado interno del módulo
    let textoOriginal = '';
    let textoPropuesto = '';
    let cargando = false;
    let guardando = false;
    // ========================================================================
    // VALOR GUARDADO EN BASE DE DATOS
    // Al inicializar, registramos el texto actual como el "guardado".
    // Se actualiza cuando el formulario se guarda o al aceptar mejora IA.
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
            botonMejorar.title = 'Mejorar la redacción del diagnóstico con IA (cascada automática)';
        }
    }
    // ========================================================================
    // MOSTRAR RESULTADO — Dos paneles visibles + botones del footer
    // ========================================================================
    function mostrarFaseResultado() {
        faseResultado.classList.remove('d-none');
        botonesResultado.style.removeProperty('display');
        botonesResultado.style.display = 'flex';
    }
    // ========================================================================
    // ESTADO: CARGANDO — Spinner en el panel derecho
    // ========================================================================
    function mostrarEstadoCargando() {
        spinnerMejorado.classList.remove('d-none');
        spinnerMejorado.classList.add('d-flex');
        textMejorado.style.display = 'none';
        alertaError.style.display = 'none';
        btnAceptar.disabled = true;
        btnReintentar.disabled = true;
        diagModeloBadge.style.display = 'none';
        diagEstadisticas.style.display = 'none';
        // Mientras busca, el badge superior indica cascada automática
        modeloActivo.textContent = 'Automático (Gemini → Ollama)';
    }
    // ========================================================================
    // ESTADO: RESULTADO EXITOSO — Texto mejorado en el panel derecho
    // ========================================================================
    function mostrarResultado(texto, modelo, stats) {
        spinnerMejorado.classList.add('d-none');
        spinnerMejorado.classList.remove('d-flex');
        alertaError.style.display = 'none';
        textMejorado.style.display = 'block';
        textMejorado.textContent = texto;
        btnAceptar.disabled = false;
        btnReintentar.disabled = false;
        if (modelo) {
            modeloActivo.textContent = modelo;
            diagModeloBadge.textContent = `Modelo: ${modelo}`;
            diagModeloBadge.style.display = 'inline-block';
        }
        // Mostrar barra de estadísticas si el backend las incluye
        if (stats &&
            stats.tiempo_ms !== undefined &&
            stats.chars_original !== undefined &&
            stats.chars_mejorado !== undefined) {
            const segs = (stats.tiempo_ms / 1000).toFixed(1);
            const diff = stats.chars_mejorado - stats.chars_original;
            const diffStr = diff >= 0 ? `+${diff}` : `${diff}`;
            const diffColor = diff > 0 ? 'color:#16a34a' : diff < 0 ? 'color:#dc2626' : '';
            diagEstadisticas.innerHTML =
                `<i class="bi bi-clock" title="Tiempo de procesamiento"></i> ${segs}s` +
                    `<span class="stat-sep"></span>` +
                    `<i class="bi bi-body-text" title="Caracteres"></i> ${stats.chars_original} → ${stats.chars_mejorado}` +
                    `<span class="stat-sep"></span>` +
                    `<span style="${diffColor};font-weight:500;">${diffStr} chars</span>`;
            diagEstadisticas.style.display = 'flex';
        }
        else {
            diagEstadisticas.style.display = 'none';
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
        diagEstadisticas.style.display = 'none';
        modeloActivo.textContent = 'Sin modelo disponible';
    }
    // ========================================================================
    // LLAMAR AL API EN MODO AUTOMÁTICO (cascada Gemini → Ollama)
    // No enviamos "modelo": el backend recorre GEMINI_MODELS y cae a Ollama.
    // ========================================================================
    async function llamarCascadaAutomatica() {
        var _a, _b;
        cargando = true;
        mostrarEstadoCargando();
        // Leer la falla principal del equipo para enriquecer el prompt
        const fallaEl = document.querySelector(datosEquipo.fallaIdSelector);
        const fallaPrincipal = fallaEl ? fallaEl.value.trim() : '';
        const formData = new FormData();
        formData.append('diagnostico_sic', textoOriginal);
        // EXPLICACIÓN PARA PRINCIPIANTES: no mandamos "modelo" → cascada automática
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
                mostrarResultado(data.diagnostico_mejorado, (_a = data.modelo_usado) !== null && _a !== void 0 ? _a : 'IA', {
                    tiempo_ms: data.tiempo_ms,
                    chars_original: data.chars_original,
                    chars_mejorado: data.chars_mejorado,
                });
            }
            else {
                mostrarError((_b = data.error) !== null && _b !== void 0 ? _b : 'Error desconocido al procesar la solicitud.');
            }
        }
        catch (err) {
            const mensaje = err instanceof Error
                ? `Error de red: ${err.message}`
                : 'Error de conexión con el servidor de IA.';
            mostrarError(mensaje);
        }
        finally {
            cargando = false;
        }
    }
    // ========================================================================
    // GUARDAR EN BD el diagnóstico aceptado (solo ese campo)
    // ========================================================================
    async function guardarDiagnosticoAceptado(texto) {
        var _a;
        if (!datosEquipo.ordenId) {
            mostrarError('No se pudo identificar la orden para guardar el diagnóstico.');
            return false;
        }
        guardando = true;
        btnAceptar.disabled = true;
        btnReintentar.disabled = true;
        const etiquetaOriginal = btnAceptar.innerHTML;
        btnAceptar.innerHTML =
            '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Guardando...';
        const formData = new FormData();
        formData.append('orden_id', datosEquipo.ordenId);
        formData.append('diagnostico_sic', texto);
        try {
            const response = await fetch(GUARDAR_DIAG_ENDPOINT, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getOllamaCsrfToken(),
                },
                body: formData,
            });
            const data = await response.json();
            if (data.success) {
                return true;
            }
            mostrarError((_a = data.error) !== null && _a !== void 0 ? _a : 'No se pudo guardar el diagnóstico.');
            btnAceptar.innerHTML = etiquetaOriginal;
            btnAceptar.disabled = false;
            btnReintentar.disabled = false;
            return false;
        }
        catch (err) {
            const mensaje = err instanceof Error
                ? `Error de red al guardar: ${err.message}`
                : 'Error de conexión al guardar el diagnóstico.';
            mostrarError(mensaje);
            btnAceptar.innerHTML = etiquetaOriginal;
            btnAceptar.disabled = false;
            btnReintentar.disabled = false;
            return false;
        }
        finally {
            guardando = false;
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
    // Clic en "Mejorar Diag. con IA" — abre modal y genera de inmediato
    botonMejorar.addEventListener('click', () => {
        if (cargando || guardando)
            return;
        // Capturar el texto actual como referencia inmutable para esta sesión
        textoOriginal = textarea.value.trim();
        textoPropuesto = '';
        // Poblar el panel izquierdo con el texto original
        panelOriginal.textContent = textoOriginal;
        mostrarFaseResultado();
        modal.show();
        void llamarCascadaAutomatica();
    });
    // Botón REINTENTAR: vuelve a lanzar la cascada automática
    btnReintentar.addEventListener('click', () => {
        if (cargando || guardando)
            return;
        void llamarCascadaAutomatica();
    });
    // Botón ACEPTAR: aplica al textarea + guarda en BD + cierra el modal
    btnAceptar.addEventListener('click', () => {
        if (cargando || guardando || !textoPropuesto)
            return;
        void (async () => {
            const ok = await guardarDiagnosticoAceptado(textoPropuesto);
            if (!ok) {
                // El texto aún no se aplicó al textarea; el técnico puede reintentar
                return;
            }
            // Aplicar al campo visible y marcar como "ya guardado en BD"
            textarea.value = textoPropuesto;
            textoGuardadoEnBD = textoPropuesto;
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            textarea.classList.add('border-success');
            setTimeout(() => textarea.classList.remove('border-success'), 2000);
            evaluarEstadoBoton();
            modal.hide();
        })();
    });
    // Evaluación inicial del botón principal
    evaluarEstadoBoton();
}
// ============================================================================
// INICIALIZACIÓN — Ejecutar cuando el DOM esté completamente cargado
// ============================================================================
document.addEventListener('DOMContentLoaded', function () {
    var _a, _b, _c, _d, _e, _f, _g;
    // Solo inicializar si el botón existe (renderiza solo con AI_ENABLED=True)
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
        ordenId: (_g = botonMejorar.dataset['ordenId']) !== null && _g !== void 0 ? _g : '',
    };
    iniciarMejorarDiagSIC(textarea, botonMejorar, modalEl, datosEquipo);
});
//# sourceMappingURL=ollama_sic.js.map