"use strict";
/**
 * Dashboard de Feedback de Rechazo de Cotización
 * Lógica cliente: Chart.js, filtros AJAX, tabla paginada y comentarios.
 */
class DashboardFeedbackRechazo {
    constructor() {
        this.urls = {};
        this.urlDetalle = '';
        this.chartMotivos = null;
        this.chartTendencia = null;
        this.estadoActual = 'todos';
        this.paginaActual = 1;
        this.debounceTimer = null;
    }
    inicializar() {
        const urlsEl = document.getElementById('dashboardUrls');
        if (!urlsEl)
            return;
        this.urls = {
            kpis: urlsEl.dataset.urlKpis || '',
            porMotivo: urlsEl.dataset.urlPorMotivo || '',
            tendencia: urlsEl.dataset.urlTendencia || '',
            lista: urlsEl.dataset.urlLista || '',
            comentarios: urlsEl.dataset.urlComentarios || '',
            exportar: urlsEl.dataset.urlExportar || '',
        };
        this.urlDetalle = (urlsEl.dataset.urlDetalle || '').replace('/0/', '/{id}/');
        this.bindEventos();
        this.cargarTodo();
    }
    bindEventos() {
        var _a, _b, _c, _d;
        (_a = document.getElementById('btnAplicarFiltros')) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => this.cargarTodo());
        (_b = document.getElementById('btnLimpiarFiltros')) === null || _b === void 0 ? void 0 : _b.addEventListener('click', () => this.limpiarFiltros());
        // Tabs
        document.querySelectorAll('#tabsFeedbacks .nav-link').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('#tabsFeedbacks .nav-link').forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');
                this.estadoActual = e.target.dataset.estado || 'todos';
                this.paginaActual = 1;
                this.cargarTabla();
            });
        });
        // Buscador con debounce
        (_c = document.getElementById('inputBusqueda')) === null || _c === void 0 ? void 0 : _c.addEventListener('input', () => {
            if (this.debounceTimer)
                clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => {
                this.paginaActual = 1;
                this.cargarTabla();
            }, 400);
        });
        // Export Excel
        (_d = document.getElementById('btnExportarExcel')) === null || _d === void 0 ? void 0 : _d.addEventListener('click', (e) => {
            e.preventDefault();
            const params = this.obtenerFiltros();
            window.location.href = this.urls.exportar + '?' + params.toString();
        });
    }
    obtenerFiltros() {
        var _a;
        const params = new URLSearchParams();
        const fields = {
            fecha_desde: 'filtroFechaDesde',
            fecha_hasta: 'filtroFechaHasta',
            responsable_id: 'filtroResponsable',
            sucursal_id: 'filtroSucursal',
            motivo_rechazo: 'filtroMotivo',
        };
        for (const [param, id] of Object.entries(fields)) {
            const val = (_a = document.getElementById(id)) === null || _a === void 0 ? void 0 : _a.value;
            if (val)
                params.set(param, val);
        }
        return params;
    }
    limpiarFiltros() {
        ['filtroFechaDesde', 'filtroFechaHasta', 'filtroResponsable', 'filtroSucursal', 'filtroMotivo'].forEach(id => {
            const el = document.getElementById(id);
            if (el)
                el.value = '';
        });
        this.cargarTodo();
    }
    cargarTodo() {
        this.cargarKPIs();
        this.cargarPorMotivo();
        this.cargarTendencia();
        this.cargarTabla();
        this.cargarComentarios();
    }
    // ── KPIs ─────────────────────────────────────────────────────────
    cargarKPIs() {
        const params = this.obtenerFiltros();
        fetch(this.urls.kpis + '?' + params.toString())
            .then(r => r.json())
            .then((data) => {
            this.setTexto('kpiEnviados', String(data.total_enviados));
            this.setTexto('kpiRespondidos', String(data.total_respondidos));
            this.setTexto('kpiTasaRespuesta', `${data.tasa_respuesta}% tasa de respuesta`);
            this.setTexto('kpiPendientes', String(data.total_pendientes));
            this.setTexto('kpiExpirados', String(data.total_expirados));
            this.setTexto('kpiMotivoPrincipal', data.motivo_mas_frecuente || '—');
            this.setTexto('kpiMotivoPorcentaje', data.motivo_mas_frecuente_porcentaje ? `${data.motivo_mas_frecuente_porcentaje}% del total` : '');
            // Badges tabs
            this.setTexto('badgePendientes', String(data.total_pendientes));
            this.setTexto('badgeRespondidos', String(data.total_respondidos));
            this.setTexto('badgeExpirados', String(data.total_expirados));
        })
            .catch(() => { });
    }
    // ── Distribución por Motivo ───────────────────────────────────────
    cargarPorMotivo() {
        const loading = document.getElementById('loadingMotivos');
        if (loading)
            loading.classList.add('show');
        const params = this.obtenerFiltros();
        fetch(this.urls.porMotivo + '?' + params.toString())
            .then(r => r.json())
            .then((data) => {
            if (loading)
                loading.classList.remove('show');
            this.renderizarChartMotivos(data.motivos);
        })
            .catch(() => { if (loading)
            loading.classList.remove('show'); });
    }
    renderizarChartMotivos(motivos) {
        var _a;
        const ctx = (_a = document.getElementById('chartMotivos')) === null || _a === void 0 ? void 0 : _a.getContext('2d');
        if (!ctx)
            return;
        if (this.chartMotivos)
            this.chartMotivos.destroy();
        // Ajustar altura
        const wrapper = document.querySelector('.fbr-chart-wrapper.barras-motivos');
        if (wrapper)
            wrapper.style.height = Math.max(350, motivos.length * 45) + 'px';
        const colores = [
            '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16',
            '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6', '#6366f1',
            '#8b5cf6', '#a855f7', '#d946ef',
        ];
        this.chartMotivos = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: motivos.map(m => m.label),
                datasets: [
                    {
                        label: 'Total enviados',
                        data: motivos.map(m => m.total),
                        backgroundColor: motivos.map((_, i) => colores[i % colores.length] + 'CC'),
                        borderRadius: 4,
                    },
                    {
                        label: 'Respondidos',
                        data: motivos.map(m => m.respondidos),
                        backgroundColor: motivos.map((_, i) => colores[i % colores.length] + '55'),
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: { position: 'top', labels: { usePointStyle: true, padding: 15 } },
                    tooltip: {
                        callbacks: {
                            afterBody: (context) => {
                                const idx = context[0].dataIndex;
                                const m = motivos[idx];
                                const tasa = m.total > 0 ? Math.round(m.respondidos / m.total * 100) : 0;
                                return `Tasa de respuesta: ${tasa}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: { beginAtZero: true, ticks: { stepSize: 1 } },
                    y: { ticks: { font: { size: 11 } } },
                },
            },
        });
    }
    // ── Tendencia ─────────────────────────────────────────────────────
    cargarTendencia() {
        const loading = document.getElementById('loadingTendencia');
        if (loading)
            loading.classList.add('show');
        const params = this.obtenerFiltros();
        fetch(this.urls.tendencia + '?' + params.toString())
            .then(r => r.json())
            .then((data) => {
            if (loading)
                loading.classList.remove('show');
            this.renderizarChartTendencia(data);
        })
            .catch(() => { if (loading)
            loading.classList.remove('show'); });
    }
    renderizarChartTendencia(data) {
        var _a;
        const ctx = (_a = document.getElementById('chartTendencia')) === null || _a === void 0 ? void 0 : _a.getContext('2d');
        if (!ctx)
            return;
        if (this.chartTendencia)
            this.chartTendencia.destroy();
        this.chartTendencia = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: 'Enviados',
                        data: data.datasets.total_enviados,
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        tension: 0.3,
                        fill: true,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                    },
                    {
                        label: 'Respondidos',
                        data: data.datasets.total_respondidos,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        tension: 0.3,
                        fill: false,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                    },
                    {
                        label: 'Tasa Respuesta (%)',
                        data: data.datasets.tasa_respuesta,
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        tension: 0.3,
                        fill: false,
                        borderDash: [5, 5],
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        yAxisID: 'y1',
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top', labels: { usePointStyle: true, padding: 12, font: { size: 11 } } },
                },
                scales: {
                    y: {
                        type: 'linear', position: 'left',
                        beginAtZero: true,
                        title: { display: true, text: 'Cantidad' },
                        ticks: { stepSize: 1 },
                    },
                    y1: {
                        type: 'linear', position: 'right',
                        min: 0, max: 100,
                        title: { display: true, text: '% Respuesta' },
                        grid: { drawOnChartArea: false },
                    },
                },
            },
        });
    }
    // ── Tabla ─────────────────────────────────────────────────────────
    cargarTabla() {
        var _a;
        const loading = document.getElementById('loadingTabla');
        if (loading)
            loading.classList.add('show');
        const params = this.obtenerFiltros();
        params.set('estado', this.estadoActual);
        params.set('page', String(this.paginaActual));
        params.set('page_size', '15');
        const busqueda = (_a = document.getElementById('inputBusqueda')) === null || _a === void 0 ? void 0 : _a.value;
        if (busqueda)
            params.set('busqueda', busqueda);
        fetch(this.urls.lista + '?' + params.toString())
            .then(r => r.json())
            .then((data) => {
            if (loading)
                loading.classList.remove('show');
            this.renderizarTabla(data);
            this.renderizarPaginacion(data);
        })
            .catch(() => { if (loading)
            loading.classList.remove('show'); });
    }
    renderizarTabla(data) {
        const tbody = document.getElementById('tablaFeedbacksBody');
        if (!tbody)
            return;
        if (data.feedbacks.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="9" class="fbr-sin-datos">
                    <i class="bi bi-clipboard-x"></i>
                    No se encontraron feedbacks con los filtros seleccionados
                </td></tr>`;
            return;
        }
        let html = '';
        for (const fb of data.feedbacks) {
            const detalleUrl = this.urlDetalle.replace('{id}', String(fb.orden_id));
            const tieneDetalle = !!fb.comentario_cliente;
            html += `
                <tr class="fila-feedback" data-id="${fb.id}">
                    <td class="text-center">${tieneDetalle ? '<i class="bi bi-chevron-right expand-icon"></i>' : ''}</td>
                    <td><a href="${this.escaparHtml(detalleUrl)}" class="text-decoration-none fw-semibold">${this.escaparHtml(fb.orden_numero)}</a></td>
                    <td class="text-truncate" style="max-width: 170px;" title="${this.escaparHtml(fb.equipo)}">${this.escaparHtml(fb.equipo)}</td>
                    <td class="text-truncate" style="max-width: 150px;">${this.escaparHtml(fb.email_cliente)}</td>
                    <td>${this.escaparHtml(fb.responsable)}</td>
                    <td>${this.escaparHtml(fb.sucursal)}</td>
                    <td><span class="fbr-motivo-badge" title="${this.escaparHtml(fb.motivo_rechazo)}">${this.escaparHtml(fb.motivo_rechazo)}</span></td>
                    <td>${this.escaparHtml(fb.fecha_envio)}</td>
                    <td>${this.renderizarBadgeEstado(fb.estado, fb.dias_restantes)}</td>
                </tr>`;
            if (tieneDetalle) {
                html += `
                    <tr class="fila-detalle" data-parent="${fb.id}">
                        <td colspan="9" class="px-4 py-3">
                            ${fb.fecha_respuesta ? `<div class="mb-2"><small class="text-muted">Respondido:</small> <strong>${this.escaparHtml(fb.fecha_respuesta)}</strong></div>` : ''}
                            <div class="fst-italic text-secondary">"${this.escaparHtml(fb.comentario_cliente)}"</div>
                        </td>
                    </tr>`;
            }
        }
        tbody.innerHTML = html;
        // Click expand
        tbody.querySelectorAll('.fila-feedback').forEach(fila => {
            fila.addEventListener('click', (e) => {
                if (e.target.closest('a'))
                    return;
                const id = fila.dataset.id;
                const detalle = tbody.querySelector(`.fila-detalle[data-parent="${id}"]`);
                if (detalle) {
                    detalle.classList.toggle('show');
                    fila.classList.toggle('expanded');
                }
            });
            const id = fila.dataset.id;
            if (tbody.querySelector(`.fila-detalle[data-parent="${id}"]`)) {
                fila.style.cursor = 'pointer';
            }
        });
    }
    renderizarPaginacion(data) {
        const container = document.getElementById('paginacionFeedbacks');
        if (!container)
            return;
        if (data.paginas <= 1) {
            container.innerHTML = '';
            return;
        }
        let html = `<button class="btn-pag" ${data.pagina_actual <= 1 ? 'disabled' : ''} data-page="${data.pagina_actual - 1}"><i class="bi bi-chevron-left"></i></button>`;
        const start = Math.max(1, data.pagina_actual - 2);
        const end = Math.min(data.paginas, data.pagina_actual + 2);
        if (start > 1)
            html += `<button class="btn-pag" data-page="1">1</button><span class="pag-info">...</span>`;
        for (let i = start; i <= end; i++) {
            html += `<button class="btn-pag ${i === data.pagina_actual ? 'active' : ''}" data-page="${i}">${i}</button>`;
        }
        if (end < data.paginas)
            html += `<span class="pag-info">...</span><button class="btn-pag" data-page="${data.paginas}">${data.paginas}</button>`;
        html += `<button class="btn-pag" ${data.pagina_actual >= data.paginas ? 'disabled' : ''} data-page="${data.pagina_actual + 1}"><i class="bi bi-chevron-right"></i></button>`;
        html += `<span class="pag-info">${data.total} feedbacks</span>`;
        container.innerHTML = html;
        container.querySelectorAll('.btn-pag:not(:disabled)').forEach(btn => {
            btn.addEventListener('click', () => {
                this.paginaActual = parseInt(btn.dataset.page || '1');
                this.cargarTabla();
            });
        });
    }
    // ── Comentarios ──────────────────────────────────────────────────
    cargarComentarios() {
        const params = this.obtenerFiltros();
        fetch(this.urls.comentarios + '?' + params.toString())
            .then(r => r.json())
            .then((data) => {
            this.renderizarComentarios(data.comentarios);
        })
            .catch(() => { });
    }
    renderizarComentarios(comentarios) {
        const container = document.getElementById('comentariosContainer');
        if (!container)
            return;
        if (comentarios.length === 0) {
            container.innerHTML = `
                <div class="fbr-sin-datos">
                    <i class="bi bi-chat-left-text"></i>
                    No hay comentarios de clientes aún
                </div>`;
            return;
        }
        let html = '';
        for (const c of comentarios) {
            const detalleUrl = this.urlDetalle.replace('{id}', String(c.orden_id));
            html += `
                <div class="fbr-comentario-card fbr-fade-in">
                    <div class="comentario-texto">${this.escaparHtml(c.comentario)}</div>
                    <div class="comentario-meta">
                        <div>
                            <span class="fbr-motivo-badge">${this.escaparHtml(c.motivo_rechazo)}</span>
                        </div>
                        <div>
                            <a href="${this.escaparHtml(detalleUrl)}" class="text-decoration-none">${this.escaparHtml(c.orden_numero)}</a>
                            · ${this.escaparHtml(c.responsable)} · ${this.escaparHtml(c.fecha)}
                        </div>
                    </div>
                </div>`;
        }
        container.innerHTML = html;
    }
    // ── Helpers ───────────────────────────────────────────────────────
    renderizarBadgeEstado(estado, diasRestantes) {
        const config = {
            respondido: { texto: 'Respondido', clase: 'respondido', icono: 'bi-check-circle-fill' },
            pendiente: { texto: `Pendiente (${diasRestantes}d)`, clase: 'pendiente', icono: 'bi-hourglass-split' },
            expirado: { texto: 'Expirado', clase: 'expirado', icono: 'bi-x-circle-fill' },
            no_enviado: { texto: 'No enviado', clase: 'no_enviado', icono: 'bi-dash-circle' },
        };
        const c = config[estado] || config.no_enviado;
        return `<span class="fbr-badge ${c.clase}"><i class="bi ${c.icono}"></i> ${c.texto}</span>`;
    }
    setTexto(id, texto) {
        const el = document.getElementById(id);
        if (el)
            el.textContent = texto;
    }
    escaparHtml(texto) {
        const div = document.createElement('div');
        div.textContent = texto;
        return div.innerHTML;
    }
}
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new DashboardFeedbackRechazo();
    dashboard.inicializar();
});
//# sourceMappingURL=dashboard_feedback_rechazo.js.map