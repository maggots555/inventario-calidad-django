/**
 * cotizacion_reacondicionado_modal.ts
 * ====================================
 * Modo "Equipo reacondicionado" dentro del modal Enviar Cotización al Cliente.
 */

interface CosteoReacConfig {
    recurso_front_desk_mensual: number;
    pct_front_desk: number;
    mantenimiento_materiales: number;
    gastos_operacion_ingeniero: number;
    pct_overhead: number;
    pct_mkt: number;
    pct_comision_venta: number;
    pct_margen_ganancia: number;
    pct_iva: number;
    pct_comision_cobro_base: number;
    pct_comision_3m: number;
    pct_comision_6m: number;
    pct_comision_12m: number;
}

interface CosteoReacResultado {
    subtotal_sin_iva: number;
    iva: number;
    total_precio_contado_mxn: number;
    opciones_diferidas_con_iva: {
        diferido_3_meses: number;
        diferido_6_meses: number;
        diferido_12_meses: number;
    };
}

interface Window {
    COTIZACION_REACONDICIONADO_CONFIG?: {
        costeoConfig: CosteoReacConfig;
    };
    esModoReacondicionado?: () => boolean;
    appendDatosReacondicionado?: (formData: FormData) => boolean;
    buildPreviewParamsReac?: () => URLSearchParams;
}

function fmtPesoReac(valor: number): string {
    return `$${valor.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function calcularCosteoReacondicionado(
    costoProveedor: number,
    diasFrontDesk: number,
    cfg: CosteoReacConfig
): CosteoReacResultado {
    const diarioFrontDesk = cfg.recurso_front_desk_mensual / 30;
    const gastosAdministracion = diarioFrontDesk * diasFrontDesk * cfg.pct_front_desk;
    const costosFijos = (
        costoProveedor + gastosAdministracion
        + cfg.mantenimiento_materiales + cfg.gastos_operacion_ingeniero
    );
    const pctVariables = cfg.pct_overhead + cfg.pct_mkt + cfg.pct_comision_venta + cfg.pct_margen_ganancia;
    const subtotalSinIva = costosFijos / (1 - pctVariables);
    const iva = subtotalSinIva * cfg.pct_iva;
    const totalContado = subtotalSinIva + iva;

    const calcDiferido = (pctMeses: number): number => {
        const pctComisionTotal = (cfg.pct_comision_cobro_base + pctMeses) * (1 + cfg.pct_iva);
        return totalContado / (1 - pctComisionTotal);
    };

    return {
        subtotal_sin_iva: Math.round(subtotalSinIva * 100) / 100,
        iva: Math.round(iva * 100) / 100,
        total_precio_contado_mxn: Math.round(totalContado * 100) / 100,
        opciones_diferidas_con_iva: {
            diferido_3_meses: Math.round(calcDiferido(cfg.pct_comision_3m) * 100) / 100,
            diferido_6_meses: Math.round(calcDiferido(cfg.pct_comision_6m) * 100) / 100,
            diferido_12_meses: Math.round(calcDiferido(cfg.pct_comision_12m) * 100) / 100,
        },
    };
}

function renderCalculadoraReac(res: CosteoReacResultado): void {
    const body = document.querySelector<HTMLElement>('#calcReacBody');
    if (!body) return;
    const dif = res.opciones_diferidas_con_iva;
    body.innerHTML = `
        <div class="calc-row"><span class="etq">Subtotal (sin IVA)</span><span class="val">${fmtPesoReac(res.subtotal_sin_iva)}</span></div>
        <div class="calc-row"><span class="etq">IVA (16%)</span><span class="val">${fmtPesoReac(res.iva)}</span></div>
        <div class="calc-row total-iva"><span class="etq">TOTAL DE CONTADO (con IVA)</span><span class="val">${fmtPesoReac(res.total_precio_contado_mxn)}</span></div>
        <div class="calc-row reac-diferido"><span class="etq">Pago diferido 3 meses (con IVA)</span><span class="val">${fmtPesoReac(dif.diferido_3_meses)}</span></div>
        <div class="calc-row reac-diferido"><span class="etq">Pago diferido 6 meses (con IVA)</span><span class="val">${fmtPesoReac(dif.diferido_6_meses)}</span></div>
        <div class="calc-row reac-diferido"><span class="etq">Pago diferido 12 meses (con IVA)</span><span class="val">${fmtPesoReac(dif.diferido_12_meses)}</span></div>`;
}

function actualizarCalculadoraReac(): void {
    const cfg = window.COTIZACION_REACONDICIONADO_CONFIG?.costeoConfig;
    const body = document.querySelector<HTMLElement>('#calcReacBody');
    if (!cfg || !body) return;
    const costo = parseFloat(document.querySelector<HTMLInputElement>('#reacCostoProveedor')?.value ?? '0');
    const dias = parseInt(document.querySelector<HTMLInputElement>('#reacDiasFrontDesk')?.value ?? '1', 10) || 1;
    if (!costo || costo <= 0) {
        body.innerHTML = '<div class="text-center py-3 text-muted" style="font-size:0.82rem;">Ingresa el costo de proveedor para ver los precios</div>';
        return;
    }
    renderCalculadoraReac(calcularCosteoReacondicionado(costo, dias, cfg));
}

function cambiarModoCotizacion(modo: 'reparacion' | 'reacondicionado'): void {
    const panelRep = document.querySelector<HTMLElement>('#panelReparacion');
    const panelReac = document.querySelector<HTMLElement>('#panelReacondicionado');
    const inputModo = document.querySelector<HTMLInputElement>('#modoCotizacionInput');
    const tabRep = document.querySelector<HTMLElement>('#tabReparacion');
    const tabReac = document.querySelector<HTMLElement>('#tabReacondicionado');

    if (inputModo) inputModo.value = modo;
    if (panelRep) panelRep.style.display = modo === 'reparacion' ? '' : 'none';
    if (panelReac) panelReac.style.display = modo === 'reacondicionado' ? '' : 'none';
    tabRep?.classList.toggle('active', modo === 'reparacion');
    tabReac?.classList.toggle('active', modo === 'reacondicionado');
    if (modo === 'reacondicionado') actualizarCalculadoraReac();
}

window.esModoReacondicionado = (): boolean => {
    return document.querySelector<HTMLInputElement>('#modoCotizacionInput')?.value === 'reacondicionado';
};

window.appendDatosReacondicionado = (formData: FormData): boolean => {
    formData.append('modo_cotizacion', 'reacondicionado');
    const marca = document.querySelector<HTMLInputElement>('#reacMarca')?.value.trim() ?? '';
    const modelo = document.querySelector<HTMLInputElement>('#reacModelo')?.value.trim() ?? '';
    const costoRaw = document.querySelector<HTMLInputElement>('#reacCostoProveedor')?.value ?? '';
    if (!marca || !modelo || !costoRaw || parseFloat(costoRaw) <= 0) return false;

    formData.append('reac_marca', marca);
    formData.append('reac_modelo', modelo);
    formData.append('reac_procesador', document.querySelector<HTMLInputElement>('#reacProcesador')?.value ?? '');
    formData.append('reac_ram', document.querySelector<HTMLInputElement>('#reacRam')?.value ?? '');
    formData.append('reac_sistema_operativo', document.querySelector<HTMLInputElement>('#reacSO')?.value ?? '');
    formData.append('reac_especificaciones', document.querySelector<HTMLTextAreaElement>('#reacEspecificaciones')?.value ?? '');
    formData.append('reac_costo_proveedor', costoRaw);
    formData.append('reac_dias_front_desk', document.querySelector<HTMLInputElement>('#reacDiasFrontDesk')?.value ?? '1');
    if (document.querySelector<HTMLInputElement>('#reacCargador')?.checked) {
        formData.append('reac_incluye_cargador', '1');
    }
    return true;
};

window.buildPreviewParamsReac = (): URLSearchParams => {
    const params = new URLSearchParams();
    params.set('modo_cotizacion', 'reacondicionado');
    params.set('reac_marca', document.querySelector<HTMLInputElement>('#reacMarca')?.value ?? '');
    params.set('reac_modelo', document.querySelector<HTMLInputElement>('#reacModelo')?.value ?? '');
    params.set('reac_procesador', document.querySelector<HTMLInputElement>('#reacProcesador')?.value ?? '');
    params.set('reac_ram', document.querySelector<HTMLInputElement>('#reacRam')?.value ?? '');
    params.set('reac_sistema_operativo', document.querySelector<HTMLInputElement>('#reacSO')?.value ?? '');
    params.set('reac_especificaciones', document.querySelector<HTMLTextAreaElement>('#reacEspecificaciones')?.value ?? '');
    params.set('reac_costo_proveedor', document.querySelector<HTMLInputElement>('#reacCostoProveedor')?.value ?? '');
    params.set('reac_dias_front_desk', document.querySelector<HTMLInputElement>('#reacDiasFrontDesk')?.value ?? '1');
    if (document.querySelector<HTMLInputElement>('#reacCargador')?.checked) {
        params.set('reac_incluye_cargador', '1');
    }
    return params;
};

document.addEventListener('DOMContentLoaded', () => {
    if (!document.querySelector('#modalEnviarCotizacionCliente')) return;
    document.querySelector('#tabReparacion')?.addEventListener('click', () => cambiarModoCotizacion('reparacion'));
    document.querySelector('#tabReacondicionado')?.addEventListener('click', () => cambiarModoCotizacion('reacondicionado'));
    ['#reacCostoProveedor', '#reacDiasFrontDesk'].forEach(sel => {
        document.querySelector(sel)?.addEventListener('input', actualizarCalculadoraReac);
    });
});
