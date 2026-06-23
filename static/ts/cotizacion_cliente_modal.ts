/**
 * cotizacion_cliente_modal.ts
 * ===========================
 * Módulo TypeScript para el modal "Enviar Cotización al Cliente" en
 * la vista detalle_solicitud.html del módulo almacén.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * --------------------------------
 * Este archivo maneja toda la interacción del modal en el navegador:
 * 1. Calculadora de profit en tiempo real (client-side, sin roundtrip al servidor)
 * 2. Selección del tipo de servicio (botones radiales visuales)
 * 3. Selección del modo de agrupación (un PDF / dos PDFs)
 * 4. Previsualización del PDF en un iframe
 * 5. Envío del formulario como JSON al endpoint API
 *
 * Datos de entrada: window.COTIZACION_CLIENTE_CONFIG (inyectado por Django en el template)
 */

// ============================================================
// TIPOS E INTERFACES
// ============================================================

// En archivos TypeScript sin imports/exports (scripts globales), la extensión
// de Window se hace directamente en el nivel superior — no con 'declare global'.
// Esto le dice a TypeScript que window.COTIZACION_CLIENTE_CONFIG existe y
// cuál es su tipo, sin usar 'any'.
interface Window {
    COTIZACION_CLIENTE_CONFIG: CotizacionClienteConfig;
}

/** Configuración inyectada por Django en el template */
interface CotizacionClienteConfig {
    urlApi:      string;
    urlPreview:  string;
    csrfToken:   string;
    gama:        string;
    /** Configuración de profit por perfil, inyectada desde .env vía Django */
    profitConfig: Record<string, PerfilProfit>;
    lineas: LineaItem[];
    servicios: ServicioItem[];
}

/** Datos de profit, costos fijos y diagnóstico para un perfil de servicio */
interface PerfilProfit {
    profit_target: number;   // porcentaje de ganancia (0-1), ej. 0.36
    costos_fijos:  number[]; // lista de costos fijos operativos en MXN sin IVA
    diagnostico:   number;   // cargo de diagnóstico en MXN sin IVA
}

/** Una línea de cotización (pieza) */
interface LineaItem {
    pk:          number;
    nombre:      string;
    descripcion: string;
    cantidad:    number;
    costo:       number;       // costo unitario sin IVA (costo interno)
    es_necesaria: boolean;
}

/** Un servicio adicional (limpieza, reinstalación SO, etc.) */
interface ServicioItem {
    pk:     number;
    nombre: string;
    costo:  number;            // costo interno sin IVA, cantidad = 1
}

/** Resultado de la calculadora de profit */
interface ResultadoCalculo {
    subtotal_costo:         number;   // suma de todos los costos internos
    precio_sin_iva:         number;   // precio al cliente sin IVA (con profit aplicado)
    precio_con_iva:         number;   // precio al cliente con IVA 16%
    diagnostico:            number;   // costo del diagnóstico del perfil
    precio_menos_diag_iva:  number;   // precio_con_iva - diagnostico*(1+0.16)
    costos_fijos_total:     number;   // suma de costos fijos del perfil
    porcentaje_profit:      number;   // ej. 0.36 para estándar
    mano_obra:              number;   // mano de obra ingresada (sin IVA)
}

// ============================================================
// FUNCIÓN PRINCIPAL DE CÁLCULO
// Replica la lógica de pdf_cotizacion_cliente.py en TypeScript
// ============================================================

/**
 * Calcula el precio al cliente usando el perfil de profit seleccionado.
 *
 * Fórmula (espejo exacto del backend Python en pdf_cotizacion_cliente.py):
 *
 *   base              = costoTotal + manoObra + costosFijosTotal
 *   precio_sin_iva    = (base / (1 - profit%)) + diagnostico
 *   precio_con_iva    = precio_sin_iva * 1.16
 *   precio_menos_diag = precio_con_iva - (diagnostico * 1.16)
 *
 * NOTA sobre mano de obra vs diagnóstico:
 *   - Mano de obra: va en la BASE antes del factor de profit (se vende con margen)
 *   - Diagnóstico:  se suma DESPUÉS del factor (cargo fijo sin margen adicional)
 *
 * @param tipo         - Perfil de servicio ('estandar', 'alta_gama', etc.)
 * @param costoTotal   - Suma de todos los costos internos (piezas + servicios)
 * @param manoObra     - Costo de mano de obra sin IVA
 * @returns ResultadoCalculo con todos los valores
 */
function calcularPrecioCliente(
    tipo: string,
    costoTotal: number,
    manoObra: number
): ResultadoCalculo {
    // Leer la configuración de profit del objeto inyectado por Django en el template.
    // Los valores vienen del .env del servidor, nunca del código fuente del repositorio.
    const cfg = window.COTIZACION_CLIENTE_CONFIG?.profitConfig?.[tipo];

    // Fallback defensivo: si por algún motivo el perfil no existe, usar valores
    // del perfil 'estandar' para no romper la calculadora silenciosamente.
    const profit      = cfg?.profit_target  ?? 0.36;
    const costosFijos = cfg?.costos_fijos   ?? [25, 160];
    const diagnostico = cfg?.diagnostico    ?? 570;

    // Sumar los costos fijos del perfil
    const costosFijosTotal = costosFijos.reduce((a: number, b: number) => a + b, 0);

    // Base de costos que llevan profit: piezas + mano de obra + costos fijos
    // La mano de obra va aquí porque también se vende con margen de ganancia
    const baseCosto = costoTotal + manoObra + costosFijosTotal;

    // Precio sin IVA = base con profit + diagnóstico (sin profit, es cargo fijo)
    // El diagnóstico se suma DESPUÉS del factor, igual que en el Python
    const precioSinIva = (profit < 1 ? baseCosto / (1 - profit) : baseCosto) + diagnostico;

    // Precio al cliente con IVA 16%
    const precioConIva = precioSinIva * 1.16;

    // Precio con descuento diagnóstico (si el cliente ya lo pagó al ingreso)
    const precioMenosDiagIva = precioConIva - (diagnostico * 1.16);

    return {
        subtotal_costo:        costoTotal,
        precio_sin_iva:        precioSinIva,
        precio_con_iva:        precioConIva,
        diagnostico:           diagnostico,
        precio_menos_diag_iva: precioMenosDiagIva,
        costos_fijos_total:    costosFijosTotal,
        porcentaje_profit:     profit,
        mano_obra:             manoObra,
    };
}

// ============================================================
// UTILIDADES
// ============================================================

/** Formatea un número como precio MXN con 2 decimales */
function fmtPeso(valor: number): string {
    return `$${valor.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} MXN`;
}

/** Formatea un porcentaje */
function fmtPct(valor: number): string {
    return `${(valor * 100).toFixed(0)}%`;
}

// ============================================================
// INICIALIZACIÓN DEL MÓDULO
// Se ejecuta cuando el DOM está listo
// ============================================================

document.addEventListener('DOMContentLoaded', () => {

    // --- Leer la configuración inyectada por Django ---
    const config = (window as unknown as { COTIZACION_CLIENTE_CONFIG: CotizacionClienteConfig })
        .COTIZACION_CLIENTE_CONFIG;

    // Si el config no existe en esta página, salir silenciosamente
    if (!config) return;

    // --- Referencias a elementos del DOM ---
    const tipoServicioInput  = document.querySelector<HTMLInputElement>('#tipoServicioInput');
    const manoObraInput      = document.querySelector<HTMLInputElement>('#manoObraOverride');
    const calcBody           = document.querySelector<HTMLElement>('#calcBody');
    const btnPreviewPDF      = document.querySelector<HTMLButtonElement>('#btnPreviewPDF');
    const iframePreview      = document.querySelector<HTMLIFrameElement>('#iframePreviewPDF');
    const previewContainer   = document.querySelector<HTMLElement>('#previewPDFContainer');
    const previewPlaceholder = document.querySelector<HTMLElement>('#previewPDFPlaceholder');
    const btnConfirmar       = document.querySelector<HTMLButtonElement>('#btnConfirmarEnvioCliente');
    const alertaDiv          = document.querySelector<HTMLElement>('#alertaEnvioModal');
    const checkDescuento     = document.querySelector<HTMLInputElement>('#checkDescuentoDiagnostico');

    // --- Botones de tipo de servicio (visual radials) ---
    const botonesTipo = document.querySelectorAll<HTMLElement>('.servicio-tipo-btn');

    // Estado del desglose expandible: false = colapsado, true = expandido.
    // Se mantiene entre recalculaciones para no perder la posición del usuario.
    let desgloseAbierto = false;

    // --------------------------------------------------------
    // EVENTO: Clic en botones de tipo de servicio
    // --------------------------------------------------------
    botonesTipo.forEach(btn => {
        btn.addEventListener('click', () => {
            // Quitar la clase 'activo' de todos los botones
            botonesTipo.forEach(b => b.classList.remove('activo'));
            // Marcar el botón clicado como activo
            btn.classList.add('activo');
            // Actualizar el input hidden con el valor del tipo seleccionado
            const tipo = btn.dataset['tipo'] ?? 'estandar';
            if (tipoServicioInput) tipoServicioInput.value = tipo;
            // Recalcular y mostrar resultado
            actualizarCalculadora();
        });
    });

    // --------------------------------------------------------
    // EVENTO: Cambio en mano de obra
    // --------------------------------------------------------
    manoObraInput?.addEventListener('input', actualizarCalculadora);

    // --------------------------------------------------------
    // EVENTO: Cambio en checkbox de descuento diagnóstico
    // --------------------------------------------------------
    checkDescuento?.addEventListener('change', actualizarCalculadora);

    // --------------------------------------------------------
    // EVENTO: Botones de modo de agrupación (visual)
    // --------------------------------------------------------
    const agrupacionOptions = document.querySelectorAll<HTMLElement>('.agrupacion-option');
    agrupacionOptions.forEach(opt => {
        opt.addEventListener('click', () => {
            agrupacionOptions.forEach(o => o.classList.remove('activo'));
            opt.classList.add('activo');
        });
    });

    // --------------------------------------------------------
    // FUNCIÓN: Construir HTML del desglose expandible
    // Muestra cada pieza y servicio con su costo individual.
    // --------------------------------------------------------

    /**
     * Genera el HTML interno del panel de desglose por ítems.
     *
     * Se invoca dentro de actualizarCalculadora() y se incrusta en calcBody.
     * El panel se muestra u oculta según el estado de `desgloseAbierto`.
     *
     * @returns Cadena HTML con el contenido del panel .calc-desglose-panel
     */
    function renderDesgloseHTML(): string {
        // --- Sección de piezas ---
        // Cada pieza muestra: nombre, "× cantidad" si es > 1, y el subtotal
        const filasLineas = config.lineas.map(l => {
            // Texto de cantidad solo si hay más de una unidad de la misma pieza
            const cantTxt = l.cantidad > 1 ? ` <span class="desglose-cant">× ${l.cantidad}</span>` : '';
            return `
            <div class="calc-desglose-item">
                <span class="desglose-nombre">${l.nombre}${cantTxt}</span>
                <span class="desglose-val">${fmtPeso(l.costo * l.cantidad)}</span>
            </div>`;
        }).join('');

        // --- Sección de servicios adicionales (solo si existen) ---
        const filasServicios = config.servicios.length > 0
            ? `<div class="calc-desglose-grupo-titulo">Servicios adicionales</div>
               ${config.servicios.map(s => `
               <div class="calc-desglose-item">
                   <span class="desglose-nombre">${s.nombre}</span>
                   <span class="desglose-val">${fmtPeso(s.costo)}</span>
               </div>`).join('')}`
            : '';

        return `
            ${config.lineas.length > 0
                ? `<div class="calc-desglose-grupo-titulo">Piezas (${config.lineas.length})</div>${filasLineas}`
                : '<div class="calc-desglose-vacio">Sin piezas registradas</div>'}
            ${filasServicios}`;
    }

    // --------------------------------------------------------
    // FUNCIÓN: Actualizar calculadora de profit
    // Lee los costos de las líneas y servicios del config,
    // aplica el perfil seleccionado y renderiza el resultado.
    // --------------------------------------------------------
    function actualizarCalculadora(): void {
        if (!calcBody || !tipoServicioInput) return;

        const tipo     = tipoServicioInput.value || 'estandar';
        const manoObra = parseFloat(manoObraInput?.value ?? '0') || 0;

        // Calcular la suma de costos internos de todas las piezas
        const costoLineas = config.lineas.reduce((acc, l) => {
            return acc + (l.costo * l.cantidad);
        }, 0);

        // Suma de costos de servicios adicionales (cantidad = 1)
        const costoServicios = config.servicios.reduce((acc, s) => acc + s.costo, 0);

        // Costo total interno (piezas + servicios)
        const costoTotal = costoLineas + costoServicios;

        // Calcular usando el perfil
        const res = calcularPrecioCliente(tipo, costoTotal, manoObra);

        // Determinar si se muestra el descuento diagnóstico
        const mostrarDescuento = checkDescuento?.checked ?? false;

        // Construir las filas de resultado en HTML
        calcBody.innerHTML = `
            <div class="calc-row calc-row-desglose-toggle" role="button" title="Ver desglose por pieza">
                <span class="etq">
                    Costo interno total (piezas + servicios)
                    <span class="desglose-chevron">${desgloseAbierto ? '▾' : '▸'}</span>
                </span>
                <span class="val">${fmtPeso(res.subtotal_costo)}</span>
            </div>
            <div class="calc-desglose-panel" style="display:${desgloseAbierto ? 'block' : 'none'}">
                ${renderDesgloseHTML()}
            </div>
            ${res.mano_obra > 0 ? `
            <div class="calc-row">
                <span class="etq">Mano de obra (costo interno, lleva profit)</span>
                <span class="val">${fmtPeso(res.mano_obra)}</span>
            </div>` : ''}
            <div class="calc-row">
                <span class="etq">Costos fijos del perfil (${tipo})</span>
                <span class="val">${fmtPeso(res.costos_fijos_total)}</span>
            </div>
            <div class="calc-row">
                <span class="etq">Profit aplicado</span>
                <span class="val">${fmtPct(res.porcentaje_profit)}</span>
            </div>
            ${res.diagnostico > 0 ? `
            <div class="calc-row">
                <span class="etq">Diagnóstico técnico (cargo fijo, sin profit)</span>
                <span class="val">${fmtPeso(res.diagnostico)}</span>
            </div>` : ''}
            <div class="calc-row">
                <span class="etq">Reparación y piezas (sin IVA)</span>
                <span class="val">${fmtPeso(res.precio_sin_iva - res.diagnostico)}</span>
            </div>
            <div class="calc-row total-iva">
                <span class="etq">TOTAL CON IVA (16%)</span>
                <span class="val">${fmtPeso(res.precio_con_iva)}</span>
            </div>
            ${mostrarDescuento && res.diagnostico > 0 ? `
            <div class="calc-row descuento">
                <span class="etq">- Diagnóstico ya pagado: ${fmtPeso(res.diagnostico)} + IVA</span>
                <span class="val">- ${fmtPeso(res.diagnostico * 1.16)}</span>
            </div>
            <div class="calc-row total-pagar">
                <span class="etq">TOTAL A PAGAR (menos diagnóstico)</span>
                <span class="val">${fmtPeso(res.precio_menos_diag_iva)}</span>
            </div>` : ''}
        `;
    }

    // --------------------------------------------------------
    // EVENTO DELEGADO: Toggle del desglose expandible
    // Se registra UNA SOLA VEZ sobre calcBody para que funcione
    // incluso después de que actualizarCalculadora() reemplaze el innerHTML.
    // --------------------------------------------------------
    calcBody?.addEventListener('click', (e: Event) => {
        // Verificar si el clic fue dentro del toggle (o en el mismo toggle)
        const toggle = (e.target as HTMLElement).closest('.calc-row-desglose-toggle');
        if (!toggle) return;

        // Invertir el estado y volver a renderizar la calculadora con el nuevo estado
        desgloseAbierto = !desgloseAbierto;
        actualizarCalculadora();
    });

    // --------------------------------------------------------
    // EVENTO: Botón "Generar preview" del PDF
    // Carga el PDF en el iframe usando la vista preview_pdf_cotizacion
    // --------------------------------------------------------
    btnPreviewPDF?.addEventListener('click', () => {
        if (!tipoServicioInput || !iframePreview || !previewContainer || !previewPlaceholder) return;

        const tipo     = tipoServicioInput.value || 'estandar';
        const manoObra = manoObraInput?.value ?? '';
        const descuento = checkDescuento?.checked ? '1' : '0';

        // Construir la URL del preview con parámetros
        const params = new URLSearchParams({
            tipo_servicio: tipo,
            mano_de_obra_override: manoObra,
            incluir_descuento_diagnostico: descuento,
        });

        const url = `${config.urlPreview}?${params.toString()}`;

        // Mostrar spinner en el botón mientras carga
        btnPreviewPDF.disabled = true;
        btnPreviewPDF.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Cargando...';

        // Cargar el PDF en el iframe
        iframePreview.src = url;
        previewContainer.style.display = 'block';
        previewPlaceholder.style.display = 'none';

        // Restaurar el botón cuando el iframe termine de cargar
        iframePreview.onload = () => {
            btnPreviewPDF.disabled = false;
            btnPreviewPDF.innerHTML = '<i class="bi bi-eye me-1"></i>Actualizar preview';
        };
    });

    // --------------------------------------------------------
    // EVENTO: Botón "Confirmar Envío al Cliente"
    // Recolecta todos los datos del modal y los envía como
    // un FormData POST al endpoint API.
    // --------------------------------------------------------
    btnConfirmar?.addEventListener('click', async () => {
        if (!tipoServicioInput || !alertaDiv) return;

        // Ocultar alerta previa
        alertaDiv.style.display = 'none';
        alertaDiv.innerHTML = '';

        // Mostrar spinner en el botón
        const textoBtn   = document.querySelector<HTMLElement>('#btnEnvioTexto');
        const spinnerBtn = document.querySelector<HTMLElement>('#btnEnvioSpinner');
        if (textoBtn) textoBtn.style.display = 'none';
        if (spinnerBtn) spinnerBtn.style.display = '';
        if (btnConfirmar) btnConfirmar.disabled = true;

        try {
            // Recolectar todos los campos del modal en un FormData
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', config.csrfToken);
            formData.append('tipo_servicio',         tipoServicioInput.value || 'estandar');
            formData.append('email_cliente',         document.querySelector<HTMLInputElement>('#emailClienteInput')?.value ?? '');
            formData.append('mensaje_personalizado', document.querySelector<HTMLTextAreaElement>('#mensajePersonalizado')?.value ?? '');
            formData.append('mano_de_obra_override', manoObraInput?.value ?? '');

            // Descuento diagnóstico (si el checkbox existe y está marcado)
            if (checkDescuento?.checked) {
                formData.append('incluir_descuento_diagnostico', '1');
            }

            // Modo de agrupación (radio seleccionado)
            const radioAgrupacion = document.querySelector<HTMLInputElement>('input[name="modo_agrupacion"]:checked');
            formData.append('modo_agrupacion', radioAgrupacion?.value ?? 'todo_junto');

            // CC de empleados (checkboxes marcados)
            const checksCopia = document.querySelectorAll<HTMLInputElement>('input[name="copia_empleados"]:checked');
            checksCopia.forEach(chk => {
                formData.append('copia_empleados', chk.value);
            });

            // Enviar la petición al endpoint API
            const response = await fetch(config.urlApi, {
                method:  'POST',
                body:    formData,
                headers: { 'X-CSRFToken': config.csrfToken },
            });

            // Parsear la respuesta JSON
            const data = await response.json() as { success: boolean; mensaje?: string; error?: string; grupos_enviados?: number };

            if (data.success) {
                // Éxito: mostrar mensaje y cerrar modal después de 2 segundos
                mostrarAlerta('success', `<i class="bi bi-check-circle me-1"></i>${data.mensaje ?? 'Correo enviado correctamente.'}`);
                setTimeout(() => {
                    const modal = document.querySelector<HTMLElement>('#modalEnviarCotizacionCliente');
                    const bsModal = (window as unknown as { bootstrap: { Modal: { getInstance: (el: Element) => { hide: () => void } | null } } }).bootstrap?.Modal?.getInstance(modal!);
                    bsModal?.hide();
                    // Recargar la página para reflejar el nuevo estado de la solicitud
                    window.location.reload();
                }, 2500);
            } else {
                // Error: mostrar el mensaje de error
                mostrarAlerta('danger', `<i class="bi bi-exclamation-triangle me-1"></i>${data.error ?? 'Error desconocido.'}`);
                restaurarBoton();
            }

        } catch (err) {
            // Error de red o inesperado
            mostrarAlerta('danger', `<i class="bi bi-wifi-off me-1"></i>Error de conexión. Intenta de nuevo.`);
            restaurarBoton();
        }
    });

    // --------------------------------------------------------
    // FUNCIÓN: Mostrar alerta en el footer del modal
    // --------------------------------------------------------
    function mostrarAlerta(tipo: 'success' | 'danger' | 'warning', html: string): void {
        if (!alertaDiv) return;
        alertaDiv.style.display = 'block';
        alertaDiv.innerHTML = `<div class="alert alert-${tipo} py-2 mb-0" role="alert">${html}</div>`;
    }

    // --------------------------------------------------------
    // FUNCIÓN: Restaurar estado del botón confirmar
    // --------------------------------------------------------
    function restaurarBoton(): void {
        const textoBtn   = document.querySelector<HTMLElement>('#btnEnvioTexto');
        const spinnerBtn = document.querySelector<HTMLElement>('#btnEnvioSpinner');
        if (textoBtn)    textoBtn.style.display = '';
        if (spinnerBtn)  spinnerBtn.style.display = 'none';
        if (btnConfirmar) btnConfirmar.disabled = false;
    }

    // --------------------------------------------------------
    // INICIALIZAR: Calcular al cargar el modal por primera vez
    // Se usa el evento 'show.bs.modal' de Bootstrap
    // --------------------------------------------------------
    const modalEl = document.querySelector<HTMLElement>('#modalEnviarCotizacionCliente');
    modalEl?.addEventListener('show.bs.modal', () => {
        actualizarCalculadora();
        // Resetear alerta al abrir
        if (alertaDiv) {
            alertaDiv.style.display = 'none';
            alertaDiv.innerHTML = '';
        }
        // Restaurar botón por si se abrió después de un error
        restaurarBoton();
    });

    // Ejecutar calculadora inmediatamente por si el DOM ya tiene valores
    actualizarCalculadora();
});
