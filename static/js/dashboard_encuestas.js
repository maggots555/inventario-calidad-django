"use strict";
/**
 * Dashboard de Encuestas de Satisfacción
 * Lógica cliente: Chart.js, filtros AJAX, tabla paginada, comentarios y análisis IA.
 */
class DashboardEncuestas {
    constructor() {
        this.urls = {};
        this.urlDetalle = '';
        this.chartTendencia = null;
        this.chartNPS = null;
        this.chartResponsables = null;
        this.estadoActual = 'todas';
        this.paginaActual = 1;
        this.datosResponsables = [];
        this.debounceTimer = null;
        this.aiModelos = []; // Lista de modelos disponibles ([Ollama]/[Gemini])
    }
    inicializar() {
        const urlsEl = document.getElementById('dashboardUrls');
        if (!urlsEl)
            return;
        this.urls = {
            kpis: urlsEl.dataset.urlKpis || '',
            tendencia: urlsEl.dataset.urlTendencia || '',
            responsable: urlsEl.dataset.urlResponsable || '',
            nps: urlsEl.dataset.urlNps || '',
            lista: urlsEl.dataset.urlLista || '',
            comentarios: urlsEl.dataset.urlComentarios || '',
            exportar: urlsEl.dataset.urlExportar || '',
            exportarPdf: urlsEl.dataset.urlExportarPdf || '',
            analisisIA: urlsEl.dataset.urlAnalisisIa || '',
        };
        this.urlDetalle = (urlsEl.dataset.urlDetalle || '').replace('/0/', '/{id}/');
        // Leer la lista de modelos IA disponibles (separados por "||" desde Django)
        const aiModelsRaw = urlsEl.dataset.aiModels || '';
        this.aiModelos = aiModelsRaw
            ? aiModelsRaw.split('||').map(m => m.trim()).filter(m => m.length > 0)
            : [];
        this.bindEventos();
        this.cargarTodo();
    }
    bindEventos() {
        var _a, _b, _c, _d, _e, _f, _g, _h, _j;
        (_a = document.getElementById('btnAplicarFiltros')) === null || _a === void 0 ? void 0 : _a.addEventListener('click', () => this.cargarTodo());
        (_b = document.getElementById('btnLimpiarFiltros')) === null || _b === void 0 ? void 0 : _b.addEventListener('click', () => this.limpiarFiltros());
        // Tabs de la tabla
        document.querySelectorAll('#tabsEncuestas .nav-link').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('#tabsEncuestas .nav-link').forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');
                this.estadoActual = e.target.dataset.estado || 'todas';
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
        // Orden de responsables
        (_d = document.getElementById('selectOrdenResponsable')) === null || _d === void 0 ? void 0 : _d.addEventListener('change', () => {
            this.renderizarChartResponsables();
        });
        // Export Excel pasa filtros
        (_e = document.getElementById('btnExportarExcel')) === null || _e === void 0 ? void 0 : _e.addEventListener('click', (e) => {
            e.preventDefault();
            const params = this.obtenerFiltros();
            window.location.href = this.urls.exportar + '?' + params.toString();
        });
        // Export PDF — Reporte Ejecutivo con los mismos filtros activos
        (_f = document.getElementById('btnExportarPDF')) === null || _f === void 0 ? void 0 : _f.addEventListener('click', (e) => {
            e.preventDefault();
            const params = this.obtenerFiltros();
            // Indicar visualmente que se está generando el PDF
            const btn = e.currentTarget;
            const textoOriginal = btn.innerHTML;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Generando PDF...';
            btn.classList.add('disabled');
            // Iniciar descarga — el servidor puede tardar ~3-5s por los gráficos
            window.location.href = this.urls.exportarPdf + '?' + params.toString();
            // Restaurar botón después de 6 segundos
            setTimeout(() => {
                btn.innerHTML = textoOriginal;
                btn.classList.remove('disabled');
            }, 6000);
        });
        // ── Análisis de Sentimiento IA ────────────────────────────────
        (_g = document.getElementById('btnAnalizarIA')) === null || _g === void 0 ? void 0 : _g.addEventListener('click', () => {
            this.cargarAnalisisIA(false);
        });
        (_h = document.getElementById('btnRegenerarIA')) === null || _h === void 0 ? void 0 : _h.addEventListener('click', () => {
            // Leer el modelo elegido en el selector (si existe en el DOM)
            const selectorEl = document.getElementById('iaModeloSelector');
            const modeloElegido = selectorEl ? selectorEl.value : '';
            this.cargarAnalisisIA(true, modeloElegido);
        });
        (_j = document.getElementById('btnReintentarIA')) === null || _j === void 0 ? void 0 : _j.addEventListener('click', () => {
            this.cargarAnalisisIA(false);
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
            tipo_orden: 'filtroTipoOrden',
        };
        for (const [param, id] of Object.entries(fields)) {
            const val = (_a = document.getElementById(id)) === null || _a === void 0 ? void 0 : _a.value;
            if (val)
                params.set(param, val);
        }
        return params;
    }
    limpiarFiltros() {
        ['filtroFechaDesde', 'filtroFechaHasta', 'filtroResponsable', 'filtroSucursal', 'filtroTipoOrden'].forEach(id => {
            const el = document.getElementById(id);
            if (el)
                el.value = '';
        });
        this.cargarTodo();
    }
    cargarTodo() {
        this.cargarKPIs();
        this.cargarTendencia();
        this.cargarDistribucionNPS();
        this.cargarPorResponsable();
        this.cargarTabla();
        this.cargarComentarios();
    }
    // ── KPIs ─────────────────────────────────────────────────────────
    cargarKPIs() {
        const params = this.obtenerFiltros();
        fetch(this.urls.kpis + '?' + params.toString())
            .then(r => r.json())
            .then((data) => {
            this.setTexto('kpiEnviadas', String(data.total_enviadas));
            this.setTexto('kpiRespondidas', String(data.total_respondidas));
            this.setTexto('kpiTasaRespuesta', `${data.tasa_respuesta}% tasa de respuesta`);
            this.setTexto('kpiPendientes', String(data.total_pendientes));
            this.setTexto('kpiExpiradas', String(data.total_expiradas));
            // NPS Score con color semáforo
            const npsEl = document.getElementById('kpiNPSScore');
            if (npsEl) {
                npsEl.textContent = String(data.nps_score);
                npsEl.className = 'kpi-valor ' + this.claseNPS(data.nps_score);
            }
            // Calificación con estrellas
            this.setTexto('kpiCalificacion', data.calificacion_promedio.toFixed(1));
            const estrellasEl = document.getElementById('kpiEstrellas');
            if (estrellasEl)
                estrellasEl.innerHTML = this.renderizarEstrellas(data.calificacion_promedio);
            // Sub-métricas
            this.setTexto('subCalAtencion', data.calificacion_atencion_promedio.toFixed(1) + ' / 5');
            this.setTexto('subCalTiempo', data.calificacion_tiempo_promedio.toFixed(1) + ' / 5');
            this.setTexto('subTasaRec', data.tasa_recomendacion + '%');
            const barraAtencion = document.getElementById('barraAtencion');
            if (barraAtencion)
                barraAtencion.style.width = (data.calificacion_atencion_promedio / 5 * 100) + '%';
            const barraTiempo = document.getElementById('barraTiempo');
            if (barraTiempo)
                barraTiempo.style.width = (data.calificacion_tiempo_promedio / 5 * 100) + '%';
            const barraRec = document.getElementById('barraRecomendacion');
            if (barraRec)
                barraRec.style.width = data.tasa_recomendacion + '%';
            // Badges de tabs
            this.setTexto('badgePendientes', String(data.total_pendientes));
            this.setTexto('badgeRespondidas', String(data.total_respondidas));
            this.setTexto('badgeExpiradas', String(data.total_expiradas));
        })
            .catch(() => { });
    }
    // ── Tendencia ────────────────────────────────────────────────────
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
                        label: 'Calificación Promedio',
                        data: data.datasets.calificacion_promedio,
                        borderColor: '#eab308',
                        backgroundColor: 'rgba(234, 179, 8, 0.1)',
                        yAxisID: 'y',
                        tension: 0.3,
                        fill: true,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                    },
                    {
                        label: 'NPS Promedio',
                        data: data.datasets.nps_promedio,
                        borderColor: '#8b5cf6',
                        backgroundColor: 'rgba(139, 92, 246, 0.1)',
                        yAxisID: 'y1',
                        tension: 0.3,
                        fill: false,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                    },
                    {
                        label: 'Tasa Respuesta (%)',
                        data: data.datasets.tasa_respuesta,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        yAxisID: 'y2',
                        tension: 0.3,
                        fill: false,
                        borderDash: [5, 5],
                        pointRadius: 3,
                        pointHoverRadius: 5,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: { position: 'top', labels: { usePointStyle: true, padding: 15 } },
                    tooltip: {
                        callbacks: {
                            afterBody: (context) => {
                                const idx = context[0].dataIndex;
                                return `Enviadas: ${data.datasets.total_enviadas[idx]} | Respondidas: ${data.datasets.total_respondidas[idx]}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        type: 'linear', position: 'left',
                        min: 0, max: 5,
                        title: { display: true, text: 'Calificación (1-5)' },
                        ticks: { stepSize: 1 },
                    },
                    y1: {
                        type: 'linear', position: 'right',
                        min: 0, max: 10,
                        title: { display: true, text: 'NPS (0-10)' },
                        grid: { drawOnChartArea: false },
                        ticks: { stepSize: 2 },
                    },
                    y2: {
                        type: 'linear', position: 'right',
                        min: 0, max: 100,
                        display: false,
                    },
                },
            },
        });
    }
    // ── Distribución NPS ─────────────────────────────────────────────
    cargarDistribucionNPS() {
        const loading = document.getElementById('loadingNPS');
        if (loading)
            loading.classList.add('show');
        const params = this.obtenerFiltros();
        fetch(this.urls.nps + '?' + params.toString())
            .then(r => r.json())
            .then((data) => {
            if (loading)
                loading.classList.remove('show');
            this.renderizarChartNPS(data);
            const npsEl = document.getElementById('npsScoreCentral');
            if (npsEl) {
                npsEl.textContent = String(data.nps_score);
                npsEl.className = 'nps-valor ' + this.claseNPS(data.nps_score);
            }
        })
            .catch(() => { if (loading)
            loading.classList.remove('show'); });
    }
    renderizarChartNPS(data) {
        var _a;
        const ctx = (_a = document.getElementById('chartNPS')) === null || _a === void 0 ? void 0 : _a.getContext('2d');
        if (!ctx)
            return;
        if (this.chartNPS)
            this.chartNPS.destroy();
        this.chartNPS = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: [
                    `Promotores (9-10): ${data.promotores}`,
                    `Pasivos (7-8): ${data.pasivos}`,
                    `Detractores (0-6): ${data.detractores}`,
                ],
                datasets: [{
                        data: [data.promotores, data.pasivos, data.detractores],
                        backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                        borderWidth: 2,
                        borderColor: '#ffffff',
                    }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: { position: 'bottom', labels: { usePointStyle: true, padding: 12, font: { size: 12 } } },
                },
            },
        });
    }
    // ── Por Responsable ──────────────────────────────────────────────
    cargarPorResponsable() {
        const loading = document.getElementById('loadingResponsables');
        if (loading)
            loading.classList.add('show');
        const params = this.obtenerFiltros();
        fetch(this.urls.responsable + '?' + params.toString())
            .then(r => r.json())
            .then((data) => {
            if (loading)
                loading.classList.remove('show');
            this.datosResponsables = data.responsables;
            this.renderizarChartResponsables();
        })
            .catch(() => { if (loading)
            loading.classList.remove('show'); });
    }
    renderizarChartResponsables() {
        var _a;
        const ctx = (_a = document.getElementById('chartResponsables')) === null || _a === void 0 ? void 0 : _a.getContext('2d');
        if (!ctx)
            return;
        const ordenSelect = document.getElementById('selectOrdenResponsable');
        const ordenCampo = (ordenSelect === null || ordenSelect === void 0 ? void 0 : ordenSelect.value) || 'calificacion';
        const sorted = [...this.datosResponsables].sort((a, b) => {
            if (ordenCampo === 'calificacion')
                return b.calificacion_promedio - a.calificacion_promedio;
            if (ordenCampo === 'nps')
                return b.nps_score - a.nps_score;
            return b.total_enviadas - a.total_enviadas;
        });
        // Tomar top 6 para el radar (más de 6 se vuelve ilegible)
        const top = sorted.slice(0, 6);
        if (this.chartResponsables)
            this.chartResponsables.destroy();
        const colores = [
            { bg: 'rgba(59, 130, 246, 0.15)', border: '#3b82f6' },
            { bg: 'rgba(16, 185, 129, 0.15)', border: '#10b981' },
            { bg: 'rgba(139, 92, 246, 0.15)', border: '#8b5cf6' },
            { bg: 'rgba(234, 179, 8, 0.15)', border: '#eab308' },
            { bg: 'rgba(239, 68, 68, 0.15)', border: '#ef4444' },
            { bg: 'rgba(245, 158, 11, 0.15)', border: '#f59e0b' },
        ];
        const datasets = top.map((r, i) => ({
            label: r.nombre || 'Sin asignar',
            data: [
                r.calificacion_promedio * 20, // Normalizar a 0-100 (de 0-5)
                r.nps_promedio * 10, // Normalizar a 0-100 (de 0-10)
                r.tasa_recomendacion, // Ya es 0-100
                r.nps_score > 0 ? r.nps_score : 0, // NPS Score (puede ser negativo, clamp a 0)
                (r.total_respondidas / (r.total_enviadas || 1)) * 100, // Tasa respuesta
            ],
            backgroundColor: colores[i % colores.length].bg,
            borderColor: colores[i % colores.length].border,
            borderWidth: 2,
            pointBackgroundColor: colores[i % colores.length].border,
            pointBorderColor: '#fff',
            pointRadius: 4,
            pointHoverRadius: 6,
        }));
        this.chartResponsables = new Chart(ctx, {
            type: 'radar',
            data: {
                labels: ['Calificación', 'NPS Prom.', 'Recomendación', 'NPS Score', 'Tasa Respuesta'],
                datasets: datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { usePointStyle: true, padding: 10, font: { size: 11 } },
                    },
                    tooltip: {
                        callbacks: {
                            label: (context) => {
                                const idx = context.datasetIndex;
                                const r = top[idx];
                                const metrica = context.label;
                                if (metrica === 'Calificación')
                                    return ` ${r.nombre}: ${r.calificacion_promedio}/5`;
                                if (metrica === 'NPS Prom.')
                                    return ` ${r.nombre}: ${r.nps_promedio}/10`;
                                if (metrica === 'Recomendación')
                                    return ` ${r.nombre}: ${r.tasa_recomendacion}%`;
                                if (metrica === 'NPS Score')
                                    return ` ${r.nombre}: ${r.nps_score}`;
                                return ` ${r.nombre}: ${Math.round((r.total_respondidas / (r.total_enviadas || 1)) * 100)}%`;
                            }
                        }
                    }
                },
                scales: {
                    r: {
                        beginAtZero: true,
                        max: 100,
                        ticks: {
                            stepSize: 25,
                            font: { size: 10 },
                            backdropColor: 'transparent',
                        },
                        pointLabels: {
                            font: { size: 11, weight: 'bold' },
                            color: '#374151',
                        },
                        grid: { color: 'rgba(0, 0, 0, 0.06)' },
                        angleLines: { color: 'rgba(0, 0, 0, 0.06)' },
                    }
                },
            },
        });
        // Renderizar tabla ranking
        this.renderizarTablaRanking(sorted);
    }
    renderizarTablaRanking(sorted) {
        const tbody = document.getElementById('tablaRankingBody');
        if (!tbody)
            return;
        if (sorted.length === 0) {
            tbody.innerHTML = `<tr><td colspan="7" class="enc-sin-datos">
                <i class="bi bi-people"></i> Sin datos de responsables
            </td></tr>`;
            return;
        }
        let html = '';
        for (let i = 0; i < sorted.length; i++) {
            const r = sorted[i];
            const pos = i + 1;
            let posClass = '';
            if (pos === 1)
                posClass = 'top-1';
            else if (pos === 2)
                posClass = 'top-2';
            else if (pos === 3)
                posClass = 'top-3';
            const npsClase = this.claseNPS(r.nps_score);
            html += `
                <tr>
                    <td><span class="ranking-pos ${posClass}">${pos}</span></td>
                    <td class="fw-semibold">${this.escaparHtml(r.nombre || 'Sin asignar')}</td>
                    <td class="text-center">${r.total_enviadas}</td>
                    <td class="text-center">${r.total_respondidas}</td>
                    <td>${this.renderizarEstrellas(r.calificacion_promedio)} <small class="text-muted">${r.calificacion_promedio}</small></td>
                    <td class="text-center"><span class="fw-bold ${npsClase}">${r.nps_score}</span></td>
                    <td class="text-center">${r.tasa_recomendacion}%</td>
                </tr>`;
        }
        tbody.innerHTML = html;
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
        const tbody = document.getElementById('tablaEncuestasBody');
        if (!tbody)
            return;
        if (data.encuestas.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="11" class="enc-sin-datos">
                    <i class="bi bi-clipboard-x"></i>
                    No se encontraron encuestas con los filtros seleccionados
                </td></tr>`;
            return;
        }
        let html = '';
        for (const enc of data.encuestas) {
            const detalleOrdenUrl = this.urlDetalle.replace('{id}', String(enc.orden_id));
            const tieneDetalle = enc.comentario_cliente || enc.calificacion_atencion || enc.calificacion_tiempo;
            html += `
                <tr class="fila-encuesta" data-id="${enc.id}">
                    <td class="text-center">${tieneDetalle ? '<i class="bi bi-chevron-right expand-icon"></i>' : ''}</td>
                    <td><a href="${this.escaparHtml(detalleOrdenUrl)}" class="text-decoration-none fw-semibold">${this.escaparHtml(enc.orden_numero)}</a></td>
                    <td class="text-truncate" style="max-width: 180px;" title="${this.escaparHtml(enc.equipo)}">${this.escaparHtml(enc.equipo)}</td>
                    <td class="text-truncate" style="max-width: 160px;">${this.escaparHtml(enc.email_cliente)}</td>
                    <td>${this.escaparHtml(enc.responsable)}</td>
                    <td>${this.escaparHtml(enc.sucursal)}</td>
                    <td>${this.escaparHtml(enc.fecha_envio)}</td>
                    <td>${this.renderizarBadgeEstado(enc.estado, enc.dias_restantes)}</td>
                    <td>${enc.calificacion_general ? this.renderizarEstrellas(enc.calificacion_general) : '<span class="text-muted">—</span>'}</td>
                    <td>${enc.nps !== null ? this.renderizarBadgeNPS(enc.nps) : '<span class="text-muted">—</span>'}</td>
                    <td>${this.renderizarRecomienda(enc.recomienda)}</td>
                </tr>`;
            // Fila de detalle expandible
            if (tieneDetalle) {
                html += `
                    <tr class="fila-detalle" data-parent="${enc.id}">
                        <td colspan="11" class="px-4 py-3">
                            <div class="row g-3">
                                ${enc.calificacion_atencion ? `<div class="col-auto"><small class="text-muted">Atención:</small> ${this.renderizarEstrellas(enc.calificacion_atencion)}</div>` : ''}
                                ${enc.calificacion_tiempo ? `<div class="col-auto"><small class="text-muted">Tiempo:</small> ${this.renderizarEstrellas(enc.calificacion_tiempo)}</div>` : ''}
                                ${enc.fecha_respuesta ? `<div class="col-auto"><small class="text-muted">Respondida:</small> <strong>${this.escaparHtml(enc.fecha_respuesta)}</strong></div>` : ''}
                            </div>
                            ${enc.comentario_cliente ? `<div class="mt-2 fst-italic text-secondary">"${this.escaparHtml(enc.comentario_cliente)}"</div>` : ''}
                        </td>
                    </tr>`;
            }
        }
        tbody.innerHTML = html;
        // Click para expandir/colapsar
        tbody.querySelectorAll('.fila-encuesta').forEach(fila => {
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
            // Solo poner cursor pointer si tiene detalle expandible
            const id = fila.dataset.id;
            if (tbody.querySelector(`.fila-detalle[data-parent="${id}"]`)) {
                fila.style.cursor = 'pointer';
            }
        });
    }
    renderizarPaginacion(data) {
        const container = document.getElementById('paginacionEncuestas');
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
        html += `<span class="pag-info">${data.total} encuestas</span>`;
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
                <div class="enc-sin-datos">
                    <i class="bi bi-chat-left-text"></i>
                    No hay comentarios de clientes aún
                </div>`;
            return;
        }
        let html = '';
        for (const c of comentarios) {
            const detalleUrl = this.urlDetalle.replace('{id}', String(c.orden_id));
            html += `
                <div class="enc-comentario-card enc-fade-in">
                    <div class="comentario-texto">${this.escaparHtml(c.comentario)}</div>
                    <div class="comentario-meta">
                        <div>
                            ${this.renderizarEstrellas(c.calificacion)}
                            ${this.renderizarRecomienda(c.recomienda)}
                            <span class="ms-2">${this.renderizarBadgeNPS(c.nps)}</span>
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
    // ── Helpers de renderizado ────────────────────────────────────────
    renderizarEstrellas(valor) {
        let html = '<span class="enc-estrellas">';
        const redondeado = Math.round(valor);
        for (let i = 1; i <= 5; i++) {
            html += i <= redondeado
                ? '<i class="bi bi-star-fill"></i>'
                : '<i class="bi bi-star"></i>';
        }
        html += '</span>';
        return html;
    }
    renderizarBadgeEstado(estado, diasRestantes) {
        const config = {
            respondida: { texto: 'Respondida', clase: 'respondida', icono: 'bi-check-circle-fill' },
            pendiente: { texto: `Pendiente (${diasRestantes}d)`, clase: 'pendiente', icono: 'bi-hourglass-split' },
            expirada: { texto: 'Expirada', clase: 'expirada', icono: 'bi-x-circle-fill' },
            no_enviada: { texto: 'No enviada', clase: 'no_enviada', icono: 'bi-dash-circle' },
        };
        const c = config[estado] || config.no_enviada;
        return `<span class="enc-badge ${c.clase}"><i class="bi ${c.icono}"></i> ${c.texto}</span>`;
    }
    renderizarBadgeNPS(valor) {
        let clase = 'nps-negativo';
        if (valor >= 9)
            clase = 'nps-positivo';
        else if (valor >= 7)
            clase = 'nps-neutro';
        return `<span class="fw-bold ${clase}">${valor}</span>`;
    }
    renderizarRecomienda(valor) {
        if (valor === null)
            return '<span class="text-muted">—</span>';
        return valor
            ? '<i class="bi bi-hand-thumbs-up-fill enc-pulgar-up" title="Sí recomienda"></i>'
            : '<i class="bi bi-hand-thumbs-down-fill enc-pulgar-down" title="No recomienda"></i>';
    }
    claseNPS(score) {
        if (score > 50)
            return 'nps-positivo';
        if (score >= 0)
            return 'nps-neutro';
        return 'nps-negativo';
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
    // ── Análisis de Sentimiento IA ────────────────────────────────────
    /**
     * Retorna los filtros activos como objeto JSON para enviar en el body del POST.
     * Reutiliza los mismos inputs que obtenerFiltros() pero en formato objeto.
     */
    obtenerFiltrosJson() {
        var _a;
        const campos = {
            fecha_desde: 'filtroFechaDesde',
            fecha_hasta: 'filtroFechaHasta',
            responsable_id: 'filtroResponsable',
            sucursal_id: 'filtroSucursal',
            tipo_orden: 'filtroTipoOrden',
        };
        const resultado = {};
        for (const [param, id] of Object.entries(campos)) {
            const val = (_a = document.getElementById(id)) === null || _a === void 0 ? void 0 : _a.value;
            if (val)
                resultado[param] = val;
        }
        return resultado;
    }
    /**
     * Muestra uno de los 4 estados de la tarjeta IA:
     * 'inicial' | 'cargando' | 'resultado' | 'error'
     */
    mostrarEstadoIA(estado) {
        const estados = {
            inicial: 'iaEstadoInicial',
            cargando: 'iaEstadoCargando',
            resultado: 'iaEstadoResultado',
            error: 'iaEstadoError',
        };
        for (const [key, id] of Object.entries(estados)) {
            const el = document.getElementById(id);
            if (el)
                el.classList.toggle('d-none', key !== estado);
        }
    }
    /**
     * Llama al endpoint de análisis IA y renderiza la tarjeta con el resultado.
     * @param forzar        - Si true, ignora el caché y solicita un nuevo análisis.
     * @param modeloElegido - Modelo con prefijo visual, ej: "[Gemini] gemini-2.0-flash".
     *                        Si está vacío, el backend usa el modelo por defecto.
     */
    cargarAnalisisIA(forzar = false, modeloElegido = '') {
        if (!this.urls.analisisIA)
            return;
        // Actualizar el texto de "cargando" con el modelo que se está usando
        const progresoEl = document.getElementById('iaProgreso');
        if (progresoEl) {
            const nombreModelo = modeloElegido
                ? modeloElegido.replace(/^\[Ollama\]\s*|\[Gemini\]\s*/i, '')
                : (this.aiModelos[0] || 'modelo IA');
            const esGemini = modeloElegido.toLowerCase().includes('gemini') ||
                (!modeloElegido && nombreModelo.toLowerCase().startsWith('gemini'));
            const proveedor = esGemini ? 'Google Gemini' : 'IA local';
            progresoEl.innerHTML = (`Procesando encuestas con <strong>${this.escaparHtml(nombreModelo)}</strong> ` +
                `(${proveedor}). Esto puede tomar unos segundos.`);
        }
        this.mostrarEstadoIA('cargando');
        // Obtener el token CSRF del DOM (Django lo pone en un meta tag o en la cookie)
        const csrfToken = this.obtenerCsrfToken();
        const body = {
            ...this.obtenerFiltrosJson(),
            forzar,
        };
        // Solo enviar el modelo si hay uno seleccionado (evita sobrescribir el default)
        if (modeloElegido) {
            body['modelo'] = modeloElegido;
        }
        fetch(this.urls.analisisIA, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken,
            },
            body: JSON.stringify(body),
        })
            .then(r => r.json())
            .then((data) => {
            if (data.success) {
                this.renderizarAnalisisIA(data);
                this.mostrarEstadoIA('resultado');
            }
            else {
                const errEl = document.getElementById('iaErrorMensaje');
                if (errEl)
                    errEl.textContent = data.error || 'Error al generar el análisis.';
                this.mostrarEstadoIA('error');
            }
        })
            .catch((err) => {
            console.error('[AnalisisIA] Error de red:', err);
            const errEl = document.getElementById('iaErrorMensaje');
            if (errEl)
                errEl.textContent = 'No se pudo conectar con el servidor. Verifica que el servicio de IA esté activo.';
            this.mostrarEstadoIA('error');
        });
    }
    /**
     * Rellena los elementos del DOM con los datos del análisis devueltos por la API.
     */
    renderizarAnalisisIA(data) {
        // ── Badge de sentimiento ──────────────────────────────────────
        const badge = document.getElementById('iaBadgeSentimiento');
        if (badge) {
            const sentimientoLabel = {
                positivo: 'Positivo',
                negativo: 'Negativo',
                mixto: 'Mixto',
                neutral: 'Neutral',
            };
            const icono = data.icono || 'bi-emoji-expressionless';
            badge.innerHTML = `<i class="bi ${this.escaparHtml(icono)} me-1"></i>${sentimientoLabel[data.sentimiento_general || 'neutral'] || 'Neutral'}`;
            // Limpiar clases de color anteriores y aplicar la nueva
            badge.className = `badge ia-badge-sentimiento ia-sentimiento-${data.sentimiento_general || 'neutral'}`;
        }
        // ── Resumen ejecutivo ─────────────────────────────────────────
        const resumen = document.getElementById('iaResumenEjecutivo');
        if (resumen)
            resumen.textContent = data.resumen_ejecutivo || '';
        // ── Temas positivos ───────────────────────────────────────────
        const chiposPositivos = document.getElementById('iaTemasPositivos');
        if (chiposPositivos) {
            const temas = data.temas_positivos || [];
            chiposPositivos.innerHTML = temas.length > 0
                ? temas.map(t => `<span class="ia-chip ia-chip-positivo">${this.escaparHtml(t)}</span>`).join('')
                : '<span class="text-muted small fst-italic">Sin aspectos positivos destacados</span>';
        }
        // ── Temas negativos ───────────────────────────────────────────
        const chipsNegativos = document.getElementById('iaTemasNegativos');
        if (chipsNegativos) {
            const temas = data.temas_negativos || [];
            chipsNegativos.innerHTML = temas.length > 0
                ? temas.map(t => `<span class="ia-chip ia-chip-negativo">${this.escaparHtml(t)}</span>`).join('')
                : '<span class="text-muted small fst-italic">Sin áreas de mejora detectadas</span>';
        }
        // ── Recomendación ─────────────────────────────────────────────
        const rec = document.getElementById('iaRecomendacion');
        if (rec) {
            if (data.recomendacion_ia) {
                rec.innerHTML = `<i class="bi bi-lightbulb-fill me-2 text-warning"></i>${this.escaparHtml(data.recomendacion_ia)}`;
                rec.classList.remove('d-none');
            }
            else {
                rec.classList.add('d-none');
            }
        }
        // ── Metadatos del pie ─────────────────────────────────────────
        const metadatos = document.getElementById('iaMetadatos');
        if (metadatos) {
            const cacheLabel = data.desde_cache
                ? '<span class="ia-cache-badge">caché</span>'
                : '<span class="ia-cache-badge ia-cache-nuevo">nuevo</span>';
            metadatos.innerHTML = (`<i class="bi bi-cpu me-1"></i>${this.escaparHtml(data.modelo_usado || 'gemma4:e4b')} ` +
                `· ${data.total_encuestas || 0} encuestas ` +
                `· ${this.escaparHtml(data.fecha_analisis || '')} ` +
                cacheLabel);
        }
    }
    /**
     * Obtiene el token CSRF desde la cookie de Django.
     * Django requiere este token en todos los POST que no sean formularios HTML.
     */
    obtenerCsrfToken() {
        const nombre = 'csrftoken';
        const cookies = document.cookie.split(';');
        for (const cookie of cookies) {
            const [key, val] = cookie.trim().split('=');
            if (key === nombre)
                return decodeURIComponent(val);
        }
        return '';
    }
}
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new DashboardEncuestas();
    dashboard.inicializar();
});
//# sourceMappingURL=dashboard_encuestas.js.map