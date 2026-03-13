"use strict";
/**
 * Dashboard de Seguimiento de Clientes
 * Lógica cliente: filtros AJAX, KPIs, tabla paginada y gráficas Chart.js.
 *
 * API endpoints consumidos:
 *   GET /servicio-tecnico/seguimiento-enlaces/api/kpis/
 *   GET /servicio-tecnico/seguimiento-enlaces/api/tendencia/
 *   GET /servicio-tecnico/seguimiento-enlaces/api/top/
 *   GET /servicio-tecnico/seguimiento-enlaces/api/tabla/
 */
// ─── Clase principal ─────────────────────────────────────────────────────────
class DashboardSeguimientoEnlaces {
    // Elemento raíz; si no existe en el DOM no hacemos nada
    constructor() {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        this.chartTendencia = null;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        this.chartTop = null;
        this.paginaActual = 1;
        if (!document.getElementById('kpiContainer'))
            return;
        this.init();
    }
    init() {
        this.bindFiltros();
        this.cargarTodo();
    }
    // ── Filtros ──────────────────────────────────────────────────────────────
    bindFiltros() {
        var _a, _b, _c, _d, _e;
        (_a = document.getElementById('btnAplicar')) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => {
            this.paginaActual = 1;
            this.cargarTodo();
        });
        (_b = document.getElementById('btnLimpiar')) === null || _b === void 0 ? void 0 : _b.addEventListener('click', () => {
            document.getElementById('filtroFechaDesde').value = '';
            document.getElementById('filtroFechaHasta').value = '';
            document.getElementById('filtroResponsable').value = '';
            document.getElementById('filtroSucursal').value = '';
            document.getElementById('filtroTipoOrden').value = '';
            this.paginaActual = 1;
            this.cargarTodo();
        });
        (_c = document.getElementById('tablaOrden')) === null || _c === void 0 ? void 0 : _c.addEventListener('change', () => {
            this.paginaActual = 1;
            this.cargarTabla();
        });
        (_d = document.getElementById('btnPaginaAnterior')) === null || _d === void 0 ? void 0 : _d.addEventListener('click', () => {
            this.paginaActual--;
            this.cargarTabla();
        });
        (_e = document.getElementById('btnPaginaSiguiente')) === null || _e === void 0 ? void 0 : _e.addEventListener('click', () => {
            this.paginaActual++;
            this.cargarTabla();
        });
    }
    buildParams(extra = {}) {
        var _a, _b, _c, _d, _e;
        const params = new URLSearchParams();
        const desde = (_a = document.getElementById('filtroFechaDesde')) === null || _a === void 0 ? void 0 : _a.value;
        const hasta = (_b = document.getElementById('filtroFechaHasta')) === null || _b === void 0 ? void 0 : _b.value;
        const resp = (_c = document.getElementById('filtroResponsable')) === null || _c === void 0 ? void 0 : _c.value;
        const suc = (_d = document.getElementById('filtroSucursal')) === null || _d === void 0 ? void 0 : _d.value;
        const tipo = (_e = document.getElementById('filtroTipoOrden')) === null || _e === void 0 ? void 0 : _e.value;
        if (desde)
            params.set('fecha_desde', desde);
        if (hasta)
            params.set('fecha_hasta', hasta);
        if (resp)
            params.set('responsable_id', resp);
        if (suc)
            params.set('sucursal_id', suc);
        if (tipo)
            params.set('tipo_orden', tipo);
        Object.entries(extra).forEach(([k, v]) => params.set(k, String(v)));
        return params.toString();
    }
    // ── Carga total ──────────────────────────────────────────────────────────
    cargarTodo() {
        this.cargarKPIs();
        this.cargarTendencia();
        this.cargarTop();
        this.cargarTabla();
    }
    // ── KPIs ─────────────────────────────────────────────────────────────────
    async cargarKPIs() {
        const url = `/servicio-tecnico/seguimiento-enlaces/api/kpis/?${this.buildParams()}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok)
                return;
            const data = await resp.json();
            this.renderKPIs(data);
        }
        catch (_) { /* silencioso */ }
    }
    renderKPIs(d) {
        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el)
                el.textContent = String(val);
        };
        set('kpiTotalEnlaces', d.total_enlaces.toLocaleString('es-MX'));
        set('kpiTotalAccesos', d.total_accesos.toLocaleString('es-MX'));
        set('kpiPromedioAccesos', d.promedio_accesos.toLocaleString('es-MX'));
        set('kpiSinVisitas', d.sin_visitas.toLocaleString('es-MX'));
        set('kpiCorreosEnviados', d.correos_enviados.toLocaleString('es-MX'));
        set('kpiTasaApertura', `${d.tasa_apertura}%`);
        const noEnv = document.getElementById('kpiCorreosNoenviados');
        if (noEnv)
            noEnv.textContent = `${d.correos_no_enviados} sin enviar`;
    }
    // ── Tendencia ────────────────────────────────────────────────────────────
    async cargarTendencia() {
        const loader = document.getElementById('loaderTendencia');
        const canvas = document.getElementById('chartTendencia');
        const empty = document.getElementById('emptyTendencia');
        if (loader)
            loader.style.display = 'flex';
        if (canvas)
            canvas.style.display = 'none';
        if (empty)
            empty.style.display = 'none';
        const url = `/servicio-tecnico/seguimiento-enlaces/api/tendencia/?${this.buildParams()}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok)
                throw new Error('API error');
            const data = await resp.json();
            if (!data.creados.length && !data.accesos.length) {
                if (loader)
                    loader.style.display = 'none';
                if (empty)
                    empty.style.display = 'block';
                return;
            }
            if (loader)
                loader.style.display = 'none';
            if (canvas)
                canvas.style.display = 'block';
            this.renderTendencia(data, canvas);
        }
        catch (_) {
            if (loader)
                loader.style.display = 'none';
            if (empty)
                empty.style.display = 'block';
        }
    }
    renderTendencia(data, canvas) {
        if (this.chartTendencia) {
            this.chartTendencia.destroy();
            this.chartTendencia = null;
        }
        // Unir todas las fechas y ordenar
        const allDates = Array.from(new Set([
            ...data.creados.map(d => d.dia),
            ...data.accesos.map(d => d.dia),
        ])).sort();
        const creadosMap = new Map(data.creados.map(d => [d.dia, d.total]));
        const accesosMap = new Map(data.accesos.map(d => [d.dia, d.total]));
        const labels = allDates.map(d => {
            const [y, m, day] = d.split('-');
            return `${day}/${m}/${y.slice(2)}`;
        });
        const serieCreados = allDates.map(d => { var _a; return (_a = creadosMap.get(d)) !== null && _a !== void 0 ? _a : 0; });
        const serieAccesos = allDates.map(d => { var _a; return (_a = accesosMap.get(d)) !== null && _a !== void 0 ? _a : 0; });
        this.chartTendencia = new Chart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Accesos de clientes',
                        data: serieAccesos,
                        borderColor: '#0d9488',
                        backgroundColor: 'rgba(13,148,136,0.10)',
                        borderWidth: 2.5,
                        pointRadius: 3,
                        tension: 0.35,
                        fill: true,
                        yAxisID: 'yAccesos',
                    },
                    {
                        label: 'Nuevos enlaces',
                        data: serieCreados,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59,130,246,0.08)',
                        borderWidth: 2,
                        pointRadius: 3,
                        tension: 0.35,
                        fill: true,
                        yAxisID: 'yCreados',
                        borderDash: [5, 3],
                    },
                ],
            },
            options: {
                responsive: true,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top', labels: { font: { size: 12 } } },
                    tooltip: { callbacks: {
                            label: (ctx) => ` ${ctx.dataset.label}: ${ctx.parsed.y}`,
                        } },
                },
                scales: {
                    yAccesos: {
                        type: 'linear',
                        position: 'left',
                        beginAtZero: true,
                        ticks: { precision: 0, font: { size: 11 } },
                        title: { display: true, text: 'Accesos', font: { size: 11 } },
                        grid: { color: 'rgba(0,0,0,0.05)' },
                    },
                    yCreados: {
                        type: 'linear',
                        position: 'right',
                        beginAtZero: true,
                        ticks: { precision: 0, font: { size: 11 } },
                        title: { display: true, text: 'Nuevos enlaces', font: { size: 11 } },
                        grid: { drawOnChartArea: false },
                    },
                    x: { ticks: { font: { size: 10 }, maxRotation: 45 } },
                },
            },
        });
    }
    // ── Top órdenes ──────────────────────────────────────────────────────────
    async cargarTop() {
        const loader = document.getElementById('loaderTop');
        const canvas = document.getElementById('chartTop');
        const empty = document.getElementById('emptyTop');
        if (loader)
            loader.style.display = 'flex';
        if (canvas)
            canvas.style.display = 'none';
        if (empty)
            empty.style.display = 'none';
        const url = `/servicio-tecnico/seguimiento-enlaces/api/top/?${this.buildParams()}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok)
                throw new Error('API error');
            const data = await resp.json();
            if (!data.top.length) {
                if (loader)
                    loader.style.display = 'none';
                if (empty)
                    empty.style.display = 'block';
                return;
            }
            if (loader)
                loader.style.display = 'none';
            if (canvas)
                canvas.style.display = 'block';
            this.renderTop(data.top, canvas);
        }
        catch (_) {
            if (loader)
                loader.style.display = 'none';
            if (empty)
                empty.style.display = 'block';
        }
    }
    renderTop(items, canvas) {
        if (this.chartTop) {
            this.chartTop.destroy();
            this.chartTop = null;
        }
        // Orden descendente → mostrar de arriba hacia abajo → invertir para Chart.js horizontal
        const sorted = [...items].sort((a, b) => a.accesos - b.accesos);
        const labels = sorted.map(i => i.folio);
        const values = sorted.map(i => i.accesos);
        this.chartTop = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                        label: 'Accesos',
                        data: values,
                        backgroundColor: labels.map((_, i) => {
                            const alpha = 0.45 + (i / labels.length) * 0.55;
                            return `rgba(31,99,145,${alpha.toFixed(2)})`;
                        }),
                        borderRadius: 5,
                        borderSkipped: false,
                    }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                plugins: {
                    legend: { display: false },
                    tooltip: { callbacks: {
                            label: (ctx) => ` ${ctx.parsed.x} acceso${ctx.parsed.x !== 1 ? 's' : ''}`,
                        } },
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        ticks: { precision: 0, font: { size: 11 } },
                        grid: { color: 'rgba(0,0,0,0.05)' },
                    },
                    y: { ticks: { font: { size: 11 } } },
                },
            },
        });
    }
    // ── Tabla paginada ───────────────────────────────────────────────────────
    async cargarTabla() {
        var _a, _b;
        const loader = document.getElementById('loaderTabla');
        const tbody = document.getElementById('tablaBody');
        const badge = document.getElementById('tablaTotalBadge');
        if (loader)
            loader.style.display = 'flex';
        if (tbody)
            tbody.innerHTML = '';
        const orden = (_b = (_a = document.getElementById('tablaOrden')) === null || _a === void 0 ? void 0 : _a.value) !== null && _b !== void 0 ? _b : '-fecha_creacion';
        const url = `/servicio-tecnico/seguimiento-enlaces/api/tabla/?${this.buildParams({
            page: this.paginaActual,
            order_by: orden,
        })}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok)
                throw new Error('API error');
            const data = await resp.json();
            if (loader)
                loader.style.display = 'none';
            if (badge)
                badge.textContent = data.total.toLocaleString('es-MX');
            this.renderTabla(data.filas);
            this.renderPaginacion(data);
        }
        catch (_) {
            if (loader)
                loader.style.display = 'none';
            if (tbody)
                tbody.innerHTML = `
                <tr><td colspan="10" class="text-center text-danger py-3">
                    <i class="bi bi-exclamation-circle me-1"></i>Error al cargar datos
                </td></tr>`;
        }
    }
    renderTabla(filas) {
        const tbody = document.getElementById('tablaBody');
        if (!tbody)
            return;
        if (!filas.length) {
            tbody.innerHTML = `
                <tr><td colspan="10" class="text-center text-muted py-4">
                    <i class="bi bi-inbox me-2"></i>No hay enlaces que coincidan con los filtros
                </td></tr>`;
            return;
        }
        tbody.innerHTML = filas.map(f => {
            const accBadge = f.accesos > 0
                ? `<span class="badge-accesos-alto">${f.accesos}</span>`
                : `<span class="badge-accesos-sin">0</span>`;
            const correoBadge = f.correo_enviado
                ? `<span class="badge-correo-ok"><i class="bi bi-check-lg me-1"></i>Enviado</span>`
                : `<span class="badge-correo-no"><i class="bi bi-x-lg me-1"></i>No enviado</span>`;
            return `
            <tr>
                <td><a href="/servicio-tecnico/ordenes/${f.orden_id}/" class="fw-semibold text-decoration-none">${f.orden_cliente}</a></td>
                <td class="text-truncate" style="max-width:140px" title="${f.equipo}">${f.equipo}</td>
                <td>${f.numero_serie}</td>
                <td class="text-truncate" style="max-width:140px" title="${f.email}">${f.email}</td>
                <td>${f.sucursal}</td>
                <td><span class="badge bg-secondary" style="font-size:0.7rem">${f.estado}</span></td>
                <td class="text-center">${accBadge}</td>
                <td class="text-center">${correoBadge}</td>
                <td class="text-nowrap">${f.fecha_creacion}</td>
                <td class="text-nowrap">${f.ultimo_acceso}</td>
            </tr>`;
        }).join('');
    }
    renderPaginacion(data) {
        const info = document.getElementById('tablaPaginaInfo');
        const prev = document.getElementById('btnPaginaAnterior');
        const next = document.getElementById('btnPaginaSiguiente');
        if (info) {
            const desde = (data.pagina - 1) * 50 + 1;
            const hasta = Math.min(data.pagina * 50, data.total);
            info.textContent = data.total > 0
                ? `Mostrando ${desde}–${hasta} de ${data.total.toLocaleString('es-MX')} enlace${data.total !== 1 ? 's' : ''}`
                : 'Sin resultados';
        }
        if (prev)
            prev.disabled = !data.tiene_anterior;
        if (next)
            next.disabled = !data.tiene_siguiente;
    }
}
// ── Bootstrap ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    new DashboardSeguimientoEnlaces();
});
//# sourceMappingURL=dashboard_seguimiento_enlaces.js.map