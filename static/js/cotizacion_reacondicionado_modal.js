"use strict";
/**
 * cotizacion_reacondicionado_modal.ts
 * ====================================
 * Modo "Equipo reacondicionado" dentro del modal Enviar Cotización al Cliente.
 */
function fmtPesoReac(valor) {
    return `$${valor.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function calcularCosteoReacondicionado(costoProveedor, diasFrontDesk, cfg) {
    const diarioFrontDesk = cfg.recurso_front_desk_mensual / 30;
    const gastosAdministracion = diarioFrontDesk * diasFrontDesk * cfg.pct_front_desk;
    const costosFijos = (costoProveedor + gastosAdministracion
        + cfg.mantenimiento_materiales + cfg.gastos_operacion_ingeniero);
    const pctVariables = cfg.pct_overhead + cfg.pct_mkt + cfg.pct_comision_venta + cfg.pct_margen_ganancia;
    const subtotalSinIva = costosFijos / (1 - pctVariables);
    const iva = subtotalSinIva * cfg.pct_iva;
    const totalContado = subtotalSinIva + iva;
    const calcDiferido = (pctMeses) => {
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
function renderCalculadoraReac(res) {
    const body = document.querySelector('#calcReacBody');
    if (!body)
        return;
    const dif = res.opciones_diferidas_con_iva;
    body.innerHTML = `
        <div class="calc-row"><span class="etq">Subtotal (sin IVA)</span><span class="val">${fmtPesoReac(res.subtotal_sin_iva)}</span></div>
        <div class="calc-row"><span class="etq">IVA (16%)</span><span class="val">${fmtPesoReac(res.iva)}</span></div>
        <div class="calc-row total-iva"><span class="etq">TOTAL DE CONTADO (con IVA)</span><span class="val">${fmtPesoReac(res.total_precio_contado_mxn)}</span></div>
        <div class="calc-row reac-diferido"><span class="etq">Pago diferido 3 meses (con IVA)</span><span class="val">${fmtPesoReac(dif.diferido_3_meses)}</span></div>
        <div class="calc-row reac-diferido"><span class="etq">Pago diferido 6 meses (con IVA)</span><span class="val">${fmtPesoReac(dif.diferido_6_meses)}</span></div>
        <div class="calc-row reac-diferido"><span class="etq">Pago diferido 12 meses (con IVA)</span><span class="val">${fmtPesoReac(dif.diferido_12_meses)}</span></div>`;
}
function actualizarCalculadoraReac() {
    var _a, _b, _c, _d, _e;
    const cfg = (_a = window.COTIZACION_REACONDICIONADO_CONFIG) === null || _a === void 0 ? void 0 : _a.costeoConfig;
    const body = document.querySelector('#calcReacBody');
    if (!cfg || !body)
        return;
    const costo = parseFloat((_c = (_b = document.querySelector('#reacCostoProveedor')) === null || _b === void 0 ? void 0 : _b.value) !== null && _c !== void 0 ? _c : '0');
    const dias = parseInt((_e = (_d = document.querySelector('#reacDiasFrontDesk')) === null || _d === void 0 ? void 0 : _d.value) !== null && _e !== void 0 ? _e : '1', 10) || 1;
    if (!costo || costo <= 0) {
        body.innerHTML = '<div class="text-center py-3 text-muted" style="font-size:0.82rem;">Ingresa el costo de proveedor para ver los precios</div>';
        return;
    }
    renderCalculadoraReac(calcularCosteoReacondicionado(costo, dias, cfg));
}
function cambiarModoCotizacion(modo) {
    const panelRep = document.querySelector('#panelReparacion');
    const panelReac = document.querySelector('#panelReacondicionado');
    const inputModo = document.querySelector('#modoCotizacionInput');
    const tabRep = document.querySelector('#tabReparacion');
    const tabReac = document.querySelector('#tabReacondicionado');
    if (inputModo)
        inputModo.value = modo;
    if (panelRep)
        panelRep.style.display = modo === 'reparacion' ? '' : 'none';
    if (panelReac)
        panelReac.style.display = modo === 'reacondicionado' ? '' : 'none';
    tabRep === null || tabRep === void 0 ? void 0 : tabRep.classList.toggle('active', modo === 'reparacion');
    tabReac === null || tabReac === void 0 ? void 0 : tabReac.classList.toggle('active', modo === 'reacondicionado');
    if (modo === 'reacondicionado')
        actualizarCalculadoraReac();
}
window.esModoReacondicionado = () => {
    var _a;
    return ((_a = document.querySelector('#modoCotizacionInput')) === null || _a === void 0 ? void 0 : _a.value) === 'reacondicionado';
};
window.appendDatosReacondicionado = (formData) => {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s;
    formData.append('modo_cotizacion', 'reacondicionado');
    const marca = (_b = (_a = document.querySelector('#reacMarca')) === null || _a === void 0 ? void 0 : _a.value.trim()) !== null && _b !== void 0 ? _b : '';
    const modelo = (_d = (_c = document.querySelector('#reacModelo')) === null || _c === void 0 ? void 0 : _c.value.trim()) !== null && _d !== void 0 ? _d : '';
    const costoRaw = (_f = (_e = document.querySelector('#reacCostoProveedor')) === null || _e === void 0 ? void 0 : _e.value) !== null && _f !== void 0 ? _f : '';
    if (!marca || !modelo || !costoRaw || parseFloat(costoRaw) <= 0)
        return false;
    formData.append('reac_marca', marca);
    formData.append('reac_modelo', modelo);
    formData.append('reac_procesador', (_h = (_g = document.querySelector('#reacProcesador')) === null || _g === void 0 ? void 0 : _g.value) !== null && _h !== void 0 ? _h : '');
    formData.append('reac_ram', (_k = (_j = document.querySelector('#reacRam')) === null || _j === void 0 ? void 0 : _j.value) !== null && _k !== void 0 ? _k : '');
    formData.append('reac_sistema_operativo', (_m = (_l = document.querySelector('#reacSO')) === null || _l === void 0 ? void 0 : _l.value) !== null && _m !== void 0 ? _m : '');
    formData.append('reac_especificaciones', (_p = (_o = document.querySelector('#reacEspecificaciones')) === null || _o === void 0 ? void 0 : _o.value) !== null && _p !== void 0 ? _p : '');
    formData.append('reac_costo_proveedor', costoRaw);
    formData.append('reac_dias_front_desk', (_r = (_q = document.querySelector('#reacDiasFrontDesk')) === null || _q === void 0 ? void 0 : _q.value) !== null && _r !== void 0 ? _r : '1');
    if ((_s = document.querySelector('#reacCargador')) === null || _s === void 0 ? void 0 : _s.checked) {
        formData.append('reac_incluye_cargador', '1');
    }
    return true;
};
window.buildPreviewParamsReac = () => {
    var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k, _l, _m, _o, _p, _q, _r, _s;
    const params = new URLSearchParams();
    params.set('modo_cotizacion', 'reacondicionado');
    params.set('reac_marca', (_b = (_a = document.querySelector('#reacMarca')) === null || _a === void 0 ? void 0 : _a.value) !== null && _b !== void 0 ? _b : '');
    params.set('reac_modelo', (_d = (_c = document.querySelector('#reacModelo')) === null || _c === void 0 ? void 0 : _c.value) !== null && _d !== void 0 ? _d : '');
    params.set('reac_procesador', (_f = (_e = document.querySelector('#reacProcesador')) === null || _e === void 0 ? void 0 : _e.value) !== null && _f !== void 0 ? _f : '');
    params.set('reac_ram', (_h = (_g = document.querySelector('#reacRam')) === null || _g === void 0 ? void 0 : _g.value) !== null && _h !== void 0 ? _h : '');
    params.set('reac_sistema_operativo', (_k = (_j = document.querySelector('#reacSO')) === null || _j === void 0 ? void 0 : _j.value) !== null && _k !== void 0 ? _k : '');
    params.set('reac_especificaciones', (_m = (_l = document.querySelector('#reacEspecificaciones')) === null || _l === void 0 ? void 0 : _l.value) !== null && _m !== void 0 ? _m : '');
    params.set('reac_costo_proveedor', (_p = (_o = document.querySelector('#reacCostoProveedor')) === null || _o === void 0 ? void 0 : _o.value) !== null && _p !== void 0 ? _p : '');
    params.set('reac_dias_front_desk', (_r = (_q = document.querySelector('#reacDiasFrontDesk')) === null || _q === void 0 ? void 0 : _q.value) !== null && _r !== void 0 ? _r : '1');
    if ((_s = document.querySelector('#reacCargador')) === null || _s === void 0 ? void 0 : _s.checked) {
        params.set('reac_incluye_cargador', '1');
    }
    return params;
};
document.addEventListener('DOMContentLoaded', () => {
    var _a, _b;
    if (!document.querySelector('#modalEnviarCotizacionCliente'))
        return;
    (_a = document.querySelector('#tabReparacion')) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => cambiarModoCotizacion('reparacion'));
    (_b = document.querySelector('#tabReacondicionado')) === null || _b === void 0 ? void 0 : _b.addEventListener('click', () => cambiarModoCotizacion('reacondicionado'));
    ['#reacCostoProveedor', '#reacDiasFrontDesk'].forEach(sel => {
        var _a;
        (_a = document.querySelector(sel)) === null || _a === void 0 ? void 0 : _a.addEventListener('input', actualizarCalculadoraReac);
    });
});
//# sourceMappingURL=cotizacion_reacondicionado_modal.js.map