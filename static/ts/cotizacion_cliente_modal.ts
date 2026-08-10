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
    esModoReacondicionado?: () => boolean;
    appendDatosReacondicionado?: (formData: FormData) => boolean;
    buildPreviewParamsReac?: () => URLSearchParams;
}

/** Configuración inyectada por Django en el template */
interface CotizacionClienteConfig {
    urlApi:      string;
    urlPreview:  string;
    csrfToken:   string;
    gama:        string;
    /** Email detectado automáticamente desde la orden o solicitud */
    emailDetectado: string;
    /** Asunto sugerido al abrir el modal (prefijo + orden o service tag) */
    asuntoCorreoDefault: string;
    /** Configuración de profit por perfil, inyectada desde .env vía Django */
    profitConfig: Record<string, PerfilProfit>;
    /**
     * Rangos mínimos por perfil (mapa completo).
     * Al cambiar Mostrador↔Estándar el TS usa el set correcto sin roundtrip.
     */
    rangosProfitMinimoPorPerfil: Record<string, RangoProfitMinimo[]>;
    /**
     * Fallback legacy: un solo set de rangos (semilla).
     * Se usa solo si falta el mapa por perfil.
     */
    rangosProfitMinimo?: RangoProfitMinimo[];
    lineas: LineaItem[];
    servicios: ServicioItem[];
}

/** Un tramo de margen mínimo según costo unitario */
interface RangoProfitMinimo {
    costo_min: number;
    costo_max: number | null;
    profit_minimo: number;
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
    estado_cliente: string;   // pendiente, aprobada, rechazada, compra_generada
    /** % ya guardado al enviar (fracción 0–1); null si aún no se personalizó */
    profit_aplicado: number | null;
}

/** Un servicio adicional (limpieza, reinstalación SO, etc.) */
interface ServicioItem {
    pk:     number;
    nombre: string;
    costo:  number;            // precio final con IVA incluido (sin profit adicional)
    estado_cliente: string;
}

/** Resultado de la calculadora de profit */
interface ResultadoCalculo {
    subtotal_costo:         number;   // suma de costos internos de piezas
    precio_piezas_sin_iva:  number;   // piezas con margen (total de reparación sin IVA)
    precio_sin_iva:         number;   // precio al cliente sin IVA (= piezas con margen)
    precio_con_iva:         number;   // precio al cliente con IVA 16%
    diagnostico:            number;   // siempre 0: el diagnóstico no entra en reparación
    precio_menos_diag_iva:  number;   // legacy (= precio_con_iva; ya no hay descuento)
    costos_fijos_total:     number;   // suma de costos fijos internos (auditoría)
    porcentaje_profit:      number;   // ej. 0.36 para estándar
    mano_obra:              number;   // mano de obra interna (auditoría)
    ganancia_bruta_dinero:  number;   // control interno Excel
    ganancia_bruta_pct:     number;   // control interno Excel
}

// ============================================================
// FUNCIÓN PRINCIPAL DE CÁLCULO
// Replica la lógica de pdf_cotizacion_cliente.py en TypeScript
// ============================================================

/**
 * Calcula el precio al cliente usando profit por pieza (perfil + overrides).
 *
 * Fórmula (espejo del backend en profit_por_pieza.py / pdf_cotizacion_cliente.py):
 *
 *   por cada pieza: precio_unit = costo / (1 - profit_efectivo)
 *   profit_efectivo = max(override o perfil, mínimo_por_costo_unitario)
 *
 * Los costos fijos y la mano de obra NO inflan el precio al cliente; solo
 * alimentan la ganancia bruta de control interno.
 *
 * @param tipo         - Perfil de servicio ('estandar', 'alta_gama', etc.)
 * @param lineas       - Piezas activas con costo unitario y cantidad
 * @param profitPorPk  - Mapa pk → profit fracción elegido en el modal
 * @param rangos       - Rangos de mínimo por costo unitario
 * @param manoObra     - Mano de obra interna (solo auditoría)
 * @returns ResultadoCalculo con todos los valores
 */
function calcularPrecioClientePorPiezas(
    tipo: string,
    lineas: LineaItem[],
    profitPorPk: Record<number, number>,
    rangos: RangoProfitMinimo[],
    manoObra: number
): ResultadoCalculo {
    const cfg = window.COTIZACION_CLIENTE_CONFIG?.profitConfig?.[tipo];
    const profitPerfil = cfg?.profit_target ?? 0.36;
    const costosFijos = cfg?.costos_fijos ?? [25, 160];
    const costosFijosTotal = costosFijos.reduce((a: number, b: number) => a + b, 0);

    let costoTotal = 0;
    let precioPiezasSinIva = 0;
    let sumaProfitPonderado = 0;

    // Paso a paso: cada pieza con su propio margen (mínimo según costo unitario)
    for (const linea of lineas) {
        const costoUnit = linea.costo;
        const cantidad = linea.cantidad;
        costoTotal += costoUnit * cantidad;
        const override = profitPorPk[linea.pk];
        const profit = resolverProfitLineaTs(
            costoUnit,
            profitPerfil,
            override !== undefined ? override : null,
            rangos,
        );
        const precioUnit = costoUnit > 0 && profit < 1
            ? costoUnit / (1 - profit)
            : costoUnit;
        const subtotal = Math.round(precioUnit * cantidad * 100) / 100;
        precioPiezasSinIva += subtotal;
        sumaProfitPonderado += profit * (costoUnit * cantidad);
    }

    precioPiezasSinIva = Math.round(precioPiezasSinIva * 100) / 100;
    const precioSinIva = precioPiezasSinIva;
    const precioConIva = precioSinIva * 1.16;
    // Profit “promedio” ponderado por costo (solo para la fila resumen)
    const profitPromedio = costoTotal > 0
        ? sumaProfitPonderado / costoTotal
        : profitPerfil;

    const totalCostosExcel = costoTotal + manoObra + costosFijosTotal;
    const gananciaBrutaDinero = precioPiezasSinIva - totalCostosExcel;
    const gananciaBrutaPct = precioPiezasSinIva > 0
        ? gananciaBrutaDinero / precioPiezasSinIva
        : 0;

    return {
        subtotal_costo:        costoTotal,
        precio_piezas_sin_iva: precioPiezasSinIva,
        precio_sin_iva:        precioSinIva,
        precio_con_iva:        precioConIva,
        diagnostico:           0,
        precio_menos_diag_iva: precioConIva,
        costos_fijos_total:    costosFijosTotal,
        porcentaje_profit:     profitPromedio,
        mano_obra:             manoObra,
        ganancia_bruta_dinero: gananciaBrutaDinero,
        ganancia_bruta_pct:    gananciaBrutaPct,
    };
}

/**
 * Profit mínimo según costo unitario (espejo de obtener_profit_minimo en Python).
 */
function obtenerProfitMinimoTs(costoUnitario: number, rangos: RangoProfitMinimo[]): number {
    const costo = Math.max(0, costoUnitario);
    for (const rango of rangos) {
        if (rango.costo_max === null) {
            if (costo >= rango.costo_min) return rango.profit_minimo;
        } else if (costo >= rango.costo_min && costo < rango.costo_max) {
            return rango.profit_minimo;
        }
    }
    // Defensa: mismo fallback que Python (último tramo semilla = 28%)
    return 0.28;
}

/**
 * max(override|perfil, mínimo del rango). Espejo de resolver_profit_linea.
 */
function resolverProfitLineaTs(
    costoUnitario: number,
    profitPerfil: number,
    profitOverride: number | null,
    rangos: RangoProfitMinimo[],
): number {
    const minimo = obtenerProfitMinimoTs(costoUnitario, rangos);
    let base = profitOverride !== null && !Number.isNaN(profitOverride)
        ? profitOverride
        : profitPerfil;
    if (base >= 1) base = 0.99;
    if (base < 0) base = 0;
    return Math.max(base, minimo);
}

/**
 * Calcula el precio al cliente usando el perfil de profit seleccionado (legacy 1 %).
 *
 * Conservada por compatibilidad; la calculadora del modal usa
 * calcularPrecioClientePorPiezas().
 */
function calcularPrecioCliente(
    tipo: string,
    costoTotal: number,
    manoObra: number
): ResultadoCalculo {
    const cfg = window.COTIZACION_CLIENTE_CONFIG?.profitConfig?.[tipo];

    const profit      = cfg?.profit_target  ?? 0.36;
    const costosFijos = cfg?.costos_fijos   ?? [25, 160];

    const costosFijosTotal = costosFijos.reduce((a: number, b: number) => a + b, 0);

    const precioPiezasSinIva = profit < 1 ? costoTotal / (1 - profit) : costoTotal;
    const precioSinIva = precioPiezasSinIva;
    const precioConIva = precioSinIva * 1.16;

    const totalCostosExcel = costoTotal + manoObra + costosFijosTotal;
    const gananciaBrutaDinero = precioPiezasSinIva - totalCostosExcel;
    const gananciaBrutaPct = precioPiezasSinIva > 0
        ? gananciaBrutaDinero / precioPiezasSinIva
        : 0;

    return {
        subtotal_costo:        costoTotal,
        precio_piezas_sin_iva: precioPiezasSinIva,
        precio_sin_iva:        precioSinIva,
        precio_con_iva:        precioConIva,
        diagnostico:           0,
        precio_menos_diag_iva: precioConIva,
        costos_fijos_total:    costosFijosTotal,
        porcentaje_profit:     profit,
        mano_obra:             manoObra,
        ganancia_bruta_dinero: gananciaBrutaDinero,
        ganancia_bruta_pct:    gananciaBrutaPct,
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

/** Valida formato básico de email (mismo criterio que el backend) */
function esEmailValido(email: string): boolean {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

/** True si el ítem entra al cálculo (pendiente o aprobada; excluye rechazada y compra_generada) */
function esItemCotizable(estado: string): boolean {
    return estado === 'pendiente' || estado === 'aprobada';
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

    // --------------------------------------------------------
    // Badges de % profit: se actualizan desde profitConfig (panel BD / .env)
    // para no mostrar porcentajes hardcodeados desactualizados.
    // --------------------------------------------------------
    document.querySelectorAll<HTMLElement>('.profit-badge[data-profit-tipo]').forEach((badge) => {
        const tipo = badge.dataset.profitTipo;
        if (!tipo) return;
        const target = config.profitConfig?.[tipo]?.profit_target;
        if (typeof target === 'number') {
            badge.textContent = `${Math.round(target * 100)}% profit`;
        }
    });

    // --- Referencias a elementos del DOM ---
    const tipoServicioInput  = document.querySelector<HTMLInputElement>('#tipoServicioInput');
    // manoObraOverride ya no existe como input — el campo es solo informativo.
    // La mano de obra NO entra en el cálculo de profit. El diagnóstico se cobra
    // al ingresar el equipo y tampoco entra en esta cotización de reparación.
    const calcBody           = document.querySelector<HTMLElement>('#calcBody');
    const btnPreviewPDF      = document.querySelector<HTMLButtonElement>('#btnPreviewPDF');
    const iframePreview      = document.querySelector<HTMLIFrameElement>('#iframePreviewPDF');
    const previewContainer   = document.querySelector<HTMLElement>('#previewPDFContainer');
    const previewPlaceholder = document.querySelector<HTMLElement>('#previewPDFPlaceholder');
    const btnConfirmar       = document.querySelector<HTMLButtonElement>('#btnConfirmarEnvioCliente');
    const alertaDiv          = document.querySelector<HTMLElement>('#alertaEnvioModal');
    const emailClienteInput  = document.querySelector<HTMLInputElement>('#emailClienteInput');
    const emailClienteCard   = document.querySelector<HTMLElement>('#emailClienteCard');
    const emailEstadoLabel   = document.querySelector<HTMLElement>('#emailClienteEstadoLabel');
    const emailDisplay       = document.querySelector<HTMLElement>('#emailClienteDisplay');
    const emailHint          = document.querySelector<HTMLElement>('#emailClienteHint');

    // Email original detectado por Django (referencia para comparar cambios)
    const emailDetectado = (config.emailDetectado ?? '').trim();

    // --- Botones de tipo de servicio (visual radials) ---
    const botonesTipo = document.querySelectorAll<HTMLElement>('.servicio-tipo-btn');

    // Desglose abierto por defecto: ahí están los inputs de profit por pieza
    let desgloseAbierto = true;

    // Profit personalizado por pieza (pk → fracción 0–1). El perfil es el default.
    /**
     * Devuelve los tramos de mínimo del tipo de cotización activo.
     * Preferimos el mapa por perfil; si falta, caemos a la lista legacy.
     */
    function rangosDelPerfil(tipo: string): RangoProfitMinimo[] {
        const mapa = config.rangosProfitMinimoPorPerfil;
        if (mapa && mapa[tipo] && mapa[tipo].length > 0) {
            return mapa[tipo];
        }
        return config.rangosProfitMinimo ?? [];
    }

    const profitPorPieza: Record<number, number> = {};

    /**
     * Reinicia cada pieza al % del perfil (elevado al mínimo del rango).
     * Se llama al cambiar de Mostrador/Estándar/etc. para no mezclar overrides viejos.
     */
    function reiniciarProfitDesdePerfil(tipo: string): void {
        const perfil = config.profitConfig?.[tipo]?.profit_target ?? 0.36;
        const rangos = rangosDelPerfil(tipo);
        for (const linea of config.lineas) {
            if (!esItemCotizable(linea.estado_cliente || 'pendiente')) continue;
            // Si ya había profit guardado en BD y es el primer arranque, lo respetamos
            // solo cuando el mapa aún está vacío para esa pk (ver inicialización abajo).
            profitPorPieza[linea.pk] = resolverProfitLineaTs(
                linea.costo,
                perfil,
                null,
                rangos,
            );
        }
    }

    // Arranque: perfil activo del modal, o profit_aplicado ya persistido
    {
        const tipoInicial = tipoServicioInput?.value || 'estandar';
        const perfilInicial = config.profitConfig?.[tipoInicial]?.profit_target ?? 0.36;
        const rangosIniciales = rangosDelPerfil(tipoInicial);
        for (const linea of config.lineas) {
            if (!esItemCotizable(linea.estado_cliente || 'pendiente')) continue;
            if (linea.profit_aplicado !== null && linea.profit_aplicado !== undefined) {
                profitPorPieza[linea.pk] = resolverProfitLineaTs(
                    linea.costo,
                    perfilInicial,
                    Number(linea.profit_aplicado),
                    rangosIniciales,
                );
            } else {
                profitPorPieza[linea.pk] = resolverProfitLineaTs(
                    linea.costo,
                    perfilInicial,
                    null,
                    rangosIniciales,
                );
            }
        }
    }

    /** Serializa el mapa de profit para API/preview */
    function serializarProfitPorPieza(): string {
        return JSON.stringify(profitPorPieza);
    }

    // --------------------------------------------------------
    // FUNCIÓN: Sincronizar tarjeta de email con el input editable
    // Muestra en tiempo real qué correo se enviará al cliente.
    // --------------------------------------------------------
    function actualizarTarjetaEmail(): void {
        if (!emailClienteCard || !emailEstadoLabel || !emailDisplay || !emailClienteInput) return;

        const valorActual = emailClienteInput.value.trim();
        const valorDetectado = emailDetectado;

        // Limpiar estados visuales previos
        emailClienteCard.classList.remove('sin-email', 'modificado', 'invalido');
        if (emailHint) {
            emailHint.style.display = 'none';
            emailHint.textContent = '';
        }

        // Caso 1: campo vacío
        if (!valorActual) {
            emailClienteCard.classList.add('sin-email');
            emailEstadoLabel.innerHTML = valorDetectado
                ? '<i class="bi bi-exclamation-triangle me-1"></i>Email requerido'
                : '<i class="bi bi-exclamation-triangle me-1"></i>Sin email detectado';
            emailDisplay.textContent = 'Ingresa el correo del destinatario abajo';
            emailClienteInput.classList.remove('is-valid', 'is-invalid');
            return;
        }

        // Caso 2: formato inválido
        if (!esEmailValido(valorActual)) {
            emailClienteCard.classList.add('invalido');
            emailEstadoLabel.textContent = 'Formato de correo inválido';
            emailDisplay.textContent = valorActual;
            if (emailHint) {
                emailHint.style.display = 'block';
                emailHint.textContent = 'Usa un formato como cliente@ejemplo.com';
            }
            emailClienteInput.classList.remove('is-valid');
            emailClienteInput.classList.add('is-invalid');
            return;
        }

        emailClienteInput.classList.remove('is-invalid');
        emailClienteInput.classList.add('is-valid');

        // Caso 3: coincide con el detectado (o se ingresó manualmente sin detección previa)
        if (valorActual.toLowerCase() === valorDetectado.toLowerCase()) {
            if (valorDetectado) {
                emailEstadoLabel.textContent = 'Email detectado:';
                emailDisplay.textContent = valorActual;
            } else {
                emailEstadoLabel.textContent = 'Email ingresado manualmente:';
                emailDisplay.textContent = valorActual;
            }
            return;
        }

        // Caso 4: el usuario modificó el correo detectado
        emailClienteCard.classList.add('modificado');
        emailEstadoLabel.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Email modificado:';
        emailDisplay.textContent = valorActual;
        if (emailHint && valorDetectado) {
            emailHint.style.display = 'block';
            emailHint.textContent = `Detectado originalmente: ${valorDetectado}`;
        }
    }

    // --------------------------------------------------------
    // EVENTO: Cambios en el email del cliente
    // --------------------------------------------------------
    emailClienteInput?.addEventListener('input', actualizarTarjetaEmail);
    emailClienteInput?.addEventListener('blur', actualizarTarjetaEmail);

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
            // Al cambiar perfil: resetear % de cada pieza al default del nuevo perfil
            reiniciarProfitDesdePerfil(tipo);
            // Recalcular y mostrar resultado
            actualizarCalculadora();
        });
    });

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
        const lineasCotizables = config.lineas.filter(l => esItemCotizable(l.estado_cliente || 'pendiente'));
        const lineasExcluidas = config.lineas.filter(l => !esItemCotizable(l.estado_cliente || 'pendiente'));
        const serviciosCotizables = config.servicios.filter(s => esItemCotizable(s.estado_cliente || 'pendiente'));
        const serviciosExcluidos = config.servicios.filter(s => !esItemCotizable(s.estado_cliente || 'pendiente'));
        const tipoActual = tipoServicioInput?.value || 'estandar';
        const perfilActual = config.profitConfig?.[tipoActual]?.profit_target ?? 0.36;
        const rangosActuales = rangosDelPerfil(tipoActual);

        // Cada pieza: input de % + precio resultante en vivo
        const filasLineas = lineasCotizables.map(l => {
            const cantTxt = l.cantidad > 1 ? ` <span class="desglose-cant">× ${l.cantidad}</span>` : '';
            const minimo = obtenerProfitMinimoTs(l.costo, rangosActuales);
            const profit = resolverProfitLineaTs(
                l.costo,
                perfilActual,
                profitPorPieza[l.pk] ?? null,
                rangosActuales,
            );
            const precioUnit = l.costo > 0 && profit < 1 ? l.costo / (1 - profit) : l.costo;
            const subtotal = Math.round(precioUnit * l.cantidad * 100) / 100;
            const pctMostrar = Math.round(profit * 1000) / 10; // 1 decimal
            const minPct = Math.round(minimo * 100);
            return `
            <div class="calc-desglose-item calc-desglose-item-profit" data-linea-pk="${l.pk}">
                <div class="desglose-profit-fila">
                    <span class="desglose-nombre">${l.nombre}${cantTxt}</span>
                    <span class="desglose-val">${fmtPeso(l.costo * l.cantidad)}</span>
                </div>
                <div class="desglose-profit-controles">
                    <label class="desglose-profit-label" for="profitPieza_${l.pk}">
                        Profit %
                        <small class="text-muted">(mín. ${minPct}%)</small>
                    </label>
                    <input type="number"
                           class="form-control form-control-sm profit-pieza-input"
                           id="profitPieza_${l.pk}"
                           data-linea-pk="${l.pk}"
                           data-minimo="${minimo}"
                           min="${minPct}"
                           max="99"
                           step="0.5"
                           value="${pctMostrar}">
                    <span class="desglose-precio-cliente" title="Precio al cliente sin IVA">
                        → ${fmtPeso(subtotal)}
                    </span>
                </div>
            </div>`;
        }).join('');

        const filasLineasExcluidas = lineasExcluidas.map(l => `
            <div class="calc-desglose-item text-muted" style="text-decoration: line-through; opacity: 0.75;">
                <span class="desglose-nombre">${l.nombre} <small>(rechazada — no incluida)</small></span>
                <span class="desglose-val">${fmtPeso(l.costo * l.cantidad)}</span>
            </div>`).join('');

        const filasServicios = serviciosCotizables.length > 0
            ? `<div class="calc-desglose-grupo-titulo">Servicios adicionales (IVA incluido)</div>
               ${serviciosCotizables.map(s => `
               <div class="calc-desglose-item">
                   <span class="desglose-nombre">${s.nombre}</span>
                   <span class="desglose-val">${fmtPeso(s.costo)}</span>
               </div>`).join('')}`
            : '';

        const filasServiciosExcluidos = serviciosExcluidos.length > 0
            ? serviciosExcluidos.map(s => `
               <div class="calc-desglose-item text-muted" style="text-decoration: line-through; opacity: 0.75;">
                   <span class="desglose-nombre">${s.nombre} <small>(rechazado — no incluido)</small></span>
                   <span class="desglose-val">${fmtPeso(s.costo)}</span>
               </div>`).join('')
            : '';

        return `
            ${lineasCotizables.length > 0
                ? `<div class="calc-desglose-grupo-titulo">Piezas en cotización (${lineasCotizables.length}) — ajusta el profit por pieza</div>${filasLineas}`
                : '<div class="calc-desglose-vacio">Sin piezas activas para cotizar</div>'}
            ${filasLineasExcluidas}
            ${filasServicios}
            ${filasServiciosExcluidos}`;
    }

    // --------------------------------------------------------
    // FUNCIÓN: Actualizar calculadora de profit
    // Lee los costos de las líneas y servicios del config,
    // aplica el perfil seleccionado y renderiza el resultado.
    // --------------------------------------------------------
    function actualizarCalculadora(): void {
        if (!calcBody || !tipoServicioInput) return;

        const tipo = tipoServicioInput.value || 'estandar';
        // Mano de obra = 0: el campo es solo informativo, no entra en el cálculo.
        // El diagnóstico tampoco entra: se cobra al ingresar el equipo.
        const manoObra = 0;

        const lineasActivas = config.lineas.filter(l => esItemCotizable(l.estado_cliente || 'pendiente'));
        const serviciosActivos = config.servicios.filter(s => esItemCotizable(s.estado_cliente || 'pendiente'));

        const costoLineas = lineasActivas.reduce((acc, l) => acc + (l.costo * l.cantidad), 0);
        const serviciosConIva = serviciosActivos.reduce((acc, s) => acc + s.costo, 0);
        const soloServicios = lineasActivas.length === 0 && serviciosActivos.length > 0;
        const sinItemsActivos = lineasActivas.length === 0 && serviciosActivos.length === 0;

        if (sinItemsActivos) {
            calcBody.innerHTML = `
                <div class="alert alert-warning mb-0 py-2 px-3" style="font-size: 0.85rem;">
                    <i class="bi bi-exclamation-triangle me-1"></i>
                    No hay piezas ni servicios pendientes o aprobados para cotizar.
                    Las líneas rechazadas no se incluyen.
                </div>
                <div class="calc-desglose-panel" style="display:block; margin-top: 0.5rem;">
                    ${renderDesgloseHTML()}
                </div>
            `;
            return;
        }

        // PDF/cotización solo con servicios activos: suma directa + desglose IVA
        if (soloServicios) {
            // EXPLICACIÓN: los servicios ya traen IVA; sin IVA = ÷ 1.16
            const subtotalSinIvaSoloServ = serviciosConIva / 1.16;
            const ivaSoloServ = serviciosConIva - subtotalSinIvaSoloServ;
            calcBody.innerHTML = `
                <div class="calc-row">
                    <span class="etq">Servicios adicionales (IVA incluido)</span>
                    <span class="val">${fmtPeso(serviciosConIva)}</span>
                </div>
                <div class="calc-desglose-panel" style="display:block">
                    ${renderDesgloseHTML()}
                </div>
                <div class="calc-row">
                    <span class="etq">Subtotal (sin IVA)</span>
                    <span class="val">${fmtPeso(subtotalSinIvaSoloServ)}</span>
                </div>
                <div class="calc-row">
                    <span class="etq">IVA (16%)</span>
                    <span class="val">${fmtPeso(ivaSoloServ)}</span>
                </div>
                <div class="calc-row total-iva">
                    <span class="etq">TOTAL CON IVA (16%)</span>
                    <span class="val">${fmtPeso(serviciosConIva)}</span>
                </div>
            `;
            return;
        }

        // Profit por pieza (perfil + overrides del modal)
        const res = calcularPrecioClientePorPiezas(
            tipo,
            lineasActivas,
            profitPorPieza,
            rangosDelPerfil(tipo),
            manoObra,
        );
        // EXPLICACIÓN: servicios ya vienen con IVA; su parte sin IVA se obtiene ÷ 1.16
        const serviciosSinIva = serviciosConIva > 0 ? serviciosConIva / 1.16 : 0;
        const subtotalSinIvaTotal = res.precio_sin_iva + serviciosSinIva;
        const precioConIvaTotal = res.precio_con_iva + serviciosConIva;
        const ivaTotal = precioConIvaTotal - subtotalSinIvaTotal;

        // Construir las filas de resultado en HTML
        calcBody.innerHTML = `
            <div class="calc-row calc-row-desglose-toggle" role="button" title="Ver desglose por pieza">
                <span class="etq">
                    Costo interno piezas
                    <span class="desglose-chevron">${desgloseAbierto ? '▾' : '▸'}</span>
                </span>
                <span class="val">${fmtPeso(costoLineas)}</span>
            </div>
            <div class="calc-desglose-panel" style="display:${desgloseAbierto ? 'block' : 'none'}">
                ${renderDesgloseHTML()}
            </div>
            ${serviciosConIva > 0 ? `
            <div class="calc-row">
                <span class="etq">Servicios adicionales (IVA incluido, sin profit)</span>
                <span class="val">${fmtPeso(serviciosConIva)}</span>
            </div>` : ''}
            <div class="calc-row">
                <span class="etq">Costos fijos internos (${tipo}) — no se cobran al cliente</span>
                <span class="val">${fmtPeso(res.costos_fijos_total)}</span>
            </div>
            <div class="calc-row">
                <span class="etq">Profit promedio ponderado (editable por pieza arriba)</span>
                <span class="val">${fmtPct(res.porcentaje_profit)}</span>
            </div>
            <div class="calc-row">
                <span class="etq">Subtotal (sin IVA)</span>
                <span class="val">${fmtPeso(subtotalSinIvaTotal)}</span>
            </div>
            <div class="calc-row">
                <span class="etq">IVA (16%)</span>
                <span class="val">${fmtPeso(ivaTotal)}</span>
            </div>
            <div class="calc-row total-iva">
                <span class="etq">TOTAL CON IVA (16%)</span>
                <span class="val">${fmtPeso(precioConIvaTotal)}</span>
            </div>
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
    // EVENTO: Cambio de profit % por pieza (inputs del desglose)
    // --------------------------------------------------------
    calcBody?.addEventListener('change', (e: Event) => {
        const input = (e.target as HTMLElement).closest('input.profit-pieza-input') as HTMLInputElement | null;
        if (!input) return;
        const pk = Number(input.dataset.lineaPk);
        const minimo = Number(input.dataset.minimo ?? '0');
        let pct = parseFloat(input.value);
        if (Number.isNaN(pct)) pct = minimo * 100;
        // Clampar en UI al mínimo y a 99%
        const minPct = minimo * 100;
        if (pct < minPct) pct = minPct;
        if (pct >= 100) pct = 99;
        profitPorPieza[pk] = pct / 100;
        // Mantener desglose abierto al editar
        desgloseAbierto = true;
        actualizarCalculadora();
    });
    calcBody?.addEventListener('input', (e: Event) => {
        // Feedback inmediato al teclear (sin esperar blur/change)
        const input = (e.target as HTMLElement).closest('input.profit-pieza-input') as HTMLInputElement | null;
        if (!input) return;
        const pk = Number(input.dataset.lineaPk);
        const minimo = Number(input.dataset.minimo ?? '0');
        let pct = parseFloat(input.value);
        if (Number.isNaN(pct)) return;
        const minPct = minimo * 100;
        if (pct < minPct) pct = minPct;
        if (pct >= 100) pct = 99;
        profitPorPieza[pk] = pct / 100;
    });

    // --------------------------------------------------------
    // EVENTO: Botón "Generar preview" del PDF
    // Carga el PDF en el iframe usando la vista preview_pdf_cotizacion
    // --------------------------------------------------------
    btnPreviewPDF?.addEventListener('click', () => {
        if (!tipoServicioInput || !iframePreview || !previewContainer || !previewPlaceholder) return;

        // Modo reacondicionado: preview con parámetros del equipo ofertado
        if (window.esModoReacondicionado?.()) {
            const marca = document.querySelector<HTMLInputElement>('#reacMarca')?.value.trim();
            const modelo = document.querySelector<HTMLInputElement>('#reacModelo')?.value.trim();
            const costo = parseFloat(document.querySelector<HTMLInputElement>('#reacCostoProveedor')?.value ?? '0');
            if (!marca || !modelo || !costo || costo <= 0) {
                alert('Completa marca, modelo y costo de proveedor para previsualizar.');
                return;
            }
            const params = window.buildPreviewParamsReac?.() ?? new URLSearchParams();
            const url = `${config.urlPreview}?${params.toString()}`;
            btnPreviewPDF.disabled = true;
            btnPreviewPDF.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Generando...';
            iframePreview.src = url;
            previewContainer.style.display = 'block';
            previewPlaceholder.style.display = 'none';
            iframePreview.onload = () => {
                btnPreviewPDF.disabled = false;
                btnPreviewPDF.innerHTML = '<i class="bi bi-eye me-1"></i>Actualizar preview';
            };
            return;
        }

        const tipo      = tipoServicioInput.value || 'estandar';

        // Construir la URL del preview con parámetros + profit por pieza
        const params = new URLSearchParams({
            tipo_servicio: tipo,
            mano_de_obra_override: '0',
            profit_por_pieza: serializarProfitPorPieza(),
        });
        const radioAgrupacion = document.querySelector<HTMLInputElement>('input[name="modo_agrupacion"]:checked');
        if (radioAgrupacion?.value) {
            params.set('modo_agrupacion', radioAgrupacion.value);
        }

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

        // Validar email antes de enviar (usa el valor del input, no el detectado)
        const emailParaEnvio = (emailClienteInput?.value ?? '').trim();
        if (!emailParaEnvio) {
            mostrarAlerta('warning', '<i class="bi bi-envelope-exclamation me-1"></i>Debes ingresar el email del cliente.');
            actualizarTarjetaEmail();
            emailClienteInput?.focus();
            return;
        }
        if (!esEmailValido(emailParaEnvio)) {
            mostrarAlerta('warning', '<i class="bi bi-envelope-x me-1"></i>El email no tiene un formato válido.');
            actualizarTarjetaEmail();
            emailClienteInput?.focus();
            return;
        }

        // Mostrar spinner en el botón
        const textoBtn   = document.querySelector<HTMLElement>('#btnEnvioTexto');
        const spinnerBtn = document.querySelector<HTMLElement>('#btnEnvioSpinner');
        if (textoBtn) textoBtn.style.display = 'none';
        if (spinnerBtn) spinnerBtn.style.display = '';
        if (btnConfirmar) btnConfirmar.disabled = true;

        try {
            const formData = new FormData();
            formData.append('csrfmiddlewaretoken', config.csrfToken);
            formData.append('email_cliente',         emailParaEnvio);
            formData.append('mensaje_personalizado', document.querySelector<HTMLTextAreaElement>('#mensajePersonalizado')?.value ?? '');
            formData.append('asunto_correo',         document.querySelector<HTMLInputElement>('#asuntoCorreoInput')?.value ?? '');

            // Modo reacondicionado: datos del equipo + costeo Excel
            if (window.esModoReacondicionado?.()) {
                if (!window.appendDatosReacondicionado?.(formData)) {
                    mostrarAlerta('warning', '<i class="bi bi-exclamation-triangle me-1"></i>Marca, modelo y costo de proveedor son obligatorios.');
                    restaurarBoton();
                    return;
                }
            } else {
                formData.append('modo_cotizacion', 'reparacion');
                formData.append('tipo_servicio',         tipoServicioInput.value || 'estandar');
                formData.append('mano_de_obra_override', '0');
                formData.append('profit_por_pieza', serializarProfitPorPieza());
                const radioAgrupacion = document.querySelector<HTMLInputElement>('input[name="modo_agrupacion"]:checked');
                formData.append('modo_agrupacion', radioAgrupacion?.value ?? 'todo_junto');
            }

            // CC de empleados (checkboxes marcados)
            const checksCopia = document.querySelectorAll<HTMLInputElement>('input[name="copia_empleados"]:checked');
            checksCopia.forEach(chk => {
                formData.append('copia_empleados', chk.value);
            });

            // Enviar la petición al endpoint API
            const response = await fetch(config.urlApi, {
                method:  'POST',
                body:    formData,
                headers: { 'X-CSRFToken': window.getCsrfToken?.() ?? config.csrfToken },
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
    // FUNCIÓN: Restablecer asunto del correo al abrir el modal
    // --------------------------------------------------------
    function actualizarAsuntoCorreo(): void {
        const inputAsunto = document.querySelector<HTMLInputElement>('#asuntoCorreoInput');
        if (!inputAsunto) return;
        inputAsunto.value = config.asuntoCorreoDefault || 'Cotización SIC — ';
    }

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
        actualizarTarjetaEmail();
        actualizarAsuntoCorreo();
        // Resetear alerta al abrir
        if (alertaDiv) {
            alertaDiv.style.display = 'none';
            alertaDiv.innerHTML = '';
        }
        // Restaurar botón por si se abrió después de un error
        restaurarBoton();
    });

    // Ejecutar calculadora y tarjeta de email al cargar la página
    actualizarCalculadora();
    actualizarTarjetaEmail();
});
