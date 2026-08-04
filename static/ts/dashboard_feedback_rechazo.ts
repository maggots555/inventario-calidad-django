/**
 * Dashboard de Feedback de Rechazo de Cotización
 * Lógica cliente: Chart.js, filtros AJAX, tabla paginada y comentarios.
 */

interface FbrKPIsData {
    total_enviados: number;
    total_respondidos: number;
    total_pendientes: number;
    total_expirados: number;
    tasa_respuesta: number;
    motivo_mas_frecuente: string;
    motivo_mas_frecuente_porcentaje: number;
}

interface FbrMotivoItem {
    motivo: string;
    label: string;
    total: number;
    respondidos: number;
}

interface FbrTendenciaData {
    labels: string[];
    datasets: {
        total_enviados: number[];
        total_respondidos: number[];
        tasa_respuesta: number[];
    };
}

interface FbrFeedbackItem {
    id: number;
    orden_numero: string;
    orden_id: number;
    equipo: string;
    email_cliente: string;
    responsable: string;
    sucursal: string;
    motivo_rechazo: string;
    fecha_envio: string;
    fecha_respuesta: string | null;
    dias_restantes: number;
    estado: 'respondido' | 'pendiente' | 'expirado' | 'no_enviado';
    comentario_cliente: string;
}

interface FbrListaData {
    feedbacks: FbrFeedbackItem[];
    total: number;
    paginas: number;
    pagina_actual: number;
}

interface FbrComentarioItem {
    orden_numero: string;
    orden_id: number;
    responsable: string;
    motivo_rechazo: string;
    comentario: string;
    fecha: string;
}

/** Respuesta del endpoint de análisis de sentimiento (rechazo). */
interface FbrAnalisisIAData {
    success: boolean;
    error?: string;
    desde_cache?: boolean;
    sentimiento_general?: 'positivo' | 'negativo' | 'mixto' | 'neutral';
    resumen_ejecutivo?: string;
    temas_positivos?: string[];
    temas_negativos?: string[];
    recomendacion_ia?: string;
    total_encuestas?: number;
    modelo_usado?: string;
    fecha_analisis?: string;
    badge_color?: string;
    icono?: string;
}

class DashboardFeedbackRechazo {
    private urls: { [key: string]: string } = {};
    private urlDetalle: string = '';
    private chartMotivos: any = null;
    private chartTendencia: any = null;
    private estadoActual: string = 'todos';
    private paginaActual: number = 1;
    private debounceTimer: ReturnType<typeof setTimeout> | null = null;

    inicializar(): void {
        const urlsEl = document.getElementById('dashboardUrls');
        if (!urlsEl) return;

        this.urls = {
            kpis: urlsEl.dataset.urlKpis || '',
            porMotivo: urlsEl.dataset.urlPorMotivo || '',
            tendencia: urlsEl.dataset.urlTendencia || '',
            lista: urlsEl.dataset.urlLista || '',
            comentarios: urlsEl.dataset.urlComentarios || '',
            analisisIA: urlsEl.dataset.urlAnalisisIa || '',
            exportar: urlsEl.dataset.urlExportar || '',
            exportarPdf: urlsEl.dataset.urlExportarPdf || '',
        };
        this.urlDetalle = (urlsEl.dataset.urlDetalle || '').replace('/0/', '/{id}/');

        this.bindEventos();
        this.cargarTodo();
    }

    private bindEventos(): void {
        document.getElementById('btnAplicarFiltros')?.addEventListener('click', () => this.cargarTodo());
        document.getElementById('btnLimpiarFiltros')?.addEventListener('click', () => this.limpiarFiltros());

        // Tabs
        document.querySelectorAll('#tabsFeedbacks .nav-link').forEach(tab => {
            tab.addEventListener('click', (e) => {
                e.preventDefault();
                document.querySelectorAll('#tabsFeedbacks .nav-link').forEach(t => t.classList.remove('active'));
                (e.target as HTMLElement).classList.add('active');
                this.estadoActual = (e.target as HTMLElement).dataset.estado || 'todos';
                this.paginaActual = 1;
                this.cargarTabla();
            });
        });

        // Buscador con debounce
        document.getElementById('inputBusqueda')?.addEventListener('input', () => {
            if (this.debounceTimer) clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => {
                this.paginaActual = 1;
                this.cargarTabla();
            }, 400);
        });

        // Export Excel
        document.getElementById('btnExportarExcel')?.addEventListener('click', (e) => {
            e.preventDefault();
            const params = this.obtenerFiltros();
            window.location.href = this.urls.exportar + '?' + params.toString();
        });

        // Export PDF — Reporte Ejecutivo con los mismos filtros activos
        // EXPLICACIÓN PARA PRINCIPIANTES: el servidor genera gráficos (~3-6 s);
        // mostramos spinner y restauramos el botón tras 6 s (espejo de encuestas).
        document.getElementById('btnExportarPDF')?.addEventListener('click', (e) => {
            e.preventDefault();
            const params = this.obtenerFiltros();
            const btn = e.currentTarget as HTMLAnchorElement;
            const textoOriginal = btn.innerHTML;
            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Generando PDF...';
            btn.classList.add('disabled');
            window.location.href = this.urls.exportarPdf + '?' + params.toString();
            setTimeout(() => {
                btn.innerHTML = textoOriginal;
                btn.classList.remove('disabled');
            }, 6000);
        });

        // ── Análisis de sentimiento IA (reutiliza pipeline de satisfacción) ──
        document.getElementById('btnAnalizarIA')?.addEventListener('click', () => {
            this.cargarAnalisisIA(false);
        });
        document.getElementById('btnRegenerarIA')?.addEventListener('click', () => {
            const selectorEl = document.getElementById('iaModeloSelector') as HTMLSelectElement | null;
            const modeloElegido = selectorEl ? selectorEl.value : '';
            this.cargarAnalisisIA(true, modeloElegido);
        });
        document.getElementById('btnReintentarIA')?.addEventListener('click', () => {
            this.cargarAnalisisIA(false);
        });
    }

    private obtenerFiltros(): URLSearchParams {
        const params = new URLSearchParams();
        const fields: { [key: string]: string } = {
            fecha_desde: 'filtroFechaDesde',
            fecha_hasta: 'filtroFechaHasta',
            responsable_id: 'filtroResponsable',
            sucursal_id: 'filtroSucursal',
            motivo_rechazo: 'filtroMotivo',
        };
        for (const [param, id] of Object.entries(fields)) {
            const val = (document.getElementById(id) as HTMLInputElement)?.value;
            if (val) params.set(param, val);
        }
        return params;
    }

    /** Filtros como objeto JSON para el POST de análisis IA. */
    private obtenerFiltrosJson(): Record<string, string> {
        const out: Record<string, string> = {};
        this.obtenerFiltros().forEach((valor, clave) => {
            out[clave] = valor;
        });
        return out;
    }

    private limpiarFiltros(): void {
        ['filtroFechaDesde', 'filtroFechaHasta', 'filtroResponsable', 'filtroSucursal', 'filtroMotivo'].forEach(id => {
            const el = document.getElementById(id) as HTMLInputElement;
            if (el) el.value = '';
        });
        this.cargarTodo();
    }

    private cargarTodo(): void {
        this.cargarKPIs();
        this.cargarPorMotivo();
        this.cargarTendencia();
        this.cargarTabla();
        this.cargarComentarios();
    }

    // ── KPIs ─────────────────────────────────────────────────────────

    private cargarKPIs(): void {
        const params = this.obtenerFiltros();
        fetch(this.urls.kpis + '?' + params.toString())
            .then(r => r.json())
            .then((data: FbrKPIsData) => {
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
            .catch(() => {});
    }

    // ── Distribución por Motivo ───────────────────────────────────────

    private cargarPorMotivo(): void {
        const loading = document.getElementById('loadingMotivos');
        if (loading) loading.classList.add('show');

        const params = this.obtenerFiltros();
        fetch(this.urls.porMotivo + '?' + params.toString())
            .then(r => r.json())
            .then((data: { motivos: FbrMotivoItem[] }) => {
                if (loading) loading.classList.remove('show');
                this.renderizarChartMotivos(data.motivos);
            })
            .catch(() => { if (loading) loading.classList.remove('show'); });
    }

    private renderizarChartMotivos(motivos: FbrMotivoItem[]): void {
        const ctx = (document.getElementById('chartMotivos') as HTMLCanvasElement)?.getContext('2d');
        if (!ctx) return;

        if (this.chartMotivos) this.chartMotivos.destroy();

        // Ajustar altura
        const wrapper = document.querySelector('.fbr-chart-wrapper.barras-motivos') as HTMLElement;
        if (wrapper) wrapper.style.height = Math.max(350, motivos.length * 45) + 'px';

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
                            afterBody: (context: any) => {
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

    private cargarTendencia(): void {
        const loading = document.getElementById('loadingTendencia');
        if (loading) loading.classList.add('show');

        const params = this.obtenerFiltros();
        fetch(this.urls.tendencia + '?' + params.toString())
            .then(r => r.json())
            .then((data: FbrTendenciaData) => {
                if (loading) loading.classList.remove('show');
                this.renderizarChartTendencia(data);
            })
            .catch(() => { if (loading) loading.classList.remove('show'); });
    }

    private renderizarChartTendencia(data: FbrTendenciaData): void {
        const ctx = (document.getElementById('chartTendencia') as HTMLCanvasElement)?.getContext('2d');
        if (!ctx) return;

        if (this.chartTendencia) this.chartTendencia.destroy();

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

    private cargarTabla(): void {
        const loading = document.getElementById('loadingTabla');
        if (loading) loading.classList.add('show');

        const params = this.obtenerFiltros();
        params.set('estado', this.estadoActual);
        params.set('page', String(this.paginaActual));
        params.set('page_size', '15');

        const busqueda = (document.getElementById('inputBusqueda') as HTMLInputElement)?.value;
        if (busqueda) params.set('busqueda', busqueda);

        fetch(this.urls.lista + '?' + params.toString())
            .then(r => r.json())
            .then((data: FbrListaData) => {
                if (loading) loading.classList.remove('show');
                this.renderizarTabla(data);
                this.renderizarPaginacion(data);
            })
            .catch(() => { if (loading) loading.classList.remove('show'); });
    }

    private renderizarTabla(data: FbrListaData): void {
        const tbody = document.getElementById('tablaFeedbacksBody');
        if (!tbody) return;

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
                if ((e.target as HTMLElement).closest('a')) return;
                const id = (fila as HTMLElement).dataset.id;
                const detalle = tbody.querySelector(`.fila-detalle[data-parent="${id}"]`);
                if (detalle) {
                    detalle.classList.toggle('show');
                    fila.classList.toggle('expanded');
                }
            });
            const id = (fila as HTMLElement).dataset.id;
            if (tbody.querySelector(`.fila-detalle[data-parent="${id}"]`)) {
                (fila as HTMLElement).style.cursor = 'pointer';
            }
        });
    }

    private renderizarPaginacion(data: FbrListaData): void {
        const container = document.getElementById('paginacionFeedbacks');
        if (!container) return;

        if (data.paginas <= 1) { container.innerHTML = ''; return; }

        let html = `<button class="btn-pag" ${data.pagina_actual <= 1 ? 'disabled' : ''} data-page="${data.pagina_actual - 1}"><i class="bi bi-chevron-left"></i></button>`;

        const start = Math.max(1, data.pagina_actual - 2);
        const end = Math.min(data.paginas, data.pagina_actual + 2);

        if (start > 1) html += `<button class="btn-pag" data-page="1">1</button><span class="pag-info">...</span>`;

        for (let i = start; i <= end; i++) {
            html += `<button class="btn-pag ${i === data.pagina_actual ? 'active' : ''}" data-page="${i}">${i}</button>`;
        }

        if (end < data.paginas) html += `<span class="pag-info">...</span><button class="btn-pag" data-page="${data.paginas}">${data.paginas}</button>`;

        html += `<button class="btn-pag" ${data.pagina_actual >= data.paginas ? 'disabled' : ''} data-page="${data.pagina_actual + 1}"><i class="bi bi-chevron-right"></i></button>`;
        html += `<span class="pag-info">${data.total} feedbacks</span>`;

        container.innerHTML = html;

        container.querySelectorAll('.btn-pag:not(:disabled)').forEach(btn => {
            btn.addEventListener('click', () => {
                this.paginaActual = parseInt((btn as HTMLElement).dataset.page || '1');
                this.cargarTabla();
            });
        });
    }

    // ── Comentarios ──────────────────────────────────────────────────

    private cargarComentarios(): void {
        const params = this.obtenerFiltros();
        fetch(this.urls.comentarios + '?' + params.toString())
            .then(r => r.json())
            .then((data: { comentarios: FbrComentarioItem[] }) => {
                this.renderizarComentarios(data.comentarios);
            })
            .catch(() => {});
    }

    private renderizarComentarios(comentarios: FbrComentarioItem[]): void {
        const container = document.getElementById('comentariosContainer');
        if (!container) return;

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

    // ── Análisis de Sentimiento IA ─────────────────────────────────────

    /**
     * Muestra uno de los 4 estados de la tarjeta IA.
     */
    private mostrarEstadoIA(estado: 'inicial' | 'cargando' | 'resultado' | 'error'): void {
        const estados: Record<string, string> = {
            inicial: 'iaEstadoInicial',
            cargando: 'iaEstadoCargando',
            resultado: 'iaEstadoResultado',
            error: 'iaEstadoError',
        };
        for (const [key, id] of Object.entries(estados)) {
            const el = document.getElementById(id);
            if (el) el.classList.toggle('d-none', key !== estado);
        }
    }

    /**
     * Llama al endpoint de análisis IA de rechazo (mismo pipeline que satisfacción).
     * @param forzar - Si true, ignora caché
     * @param modeloElegido - Vacío = cascada Automática Gemini → Ollama
     */
    cargarAnalisisIA(forzar: boolean = false, modeloElegido: string = ''): void {
        if (!this.urls.analisisIA) return;

        const progresoEl = document.getElementById('iaProgreso');
        if (progresoEl) {
            if (!modeloElegido) {
                progresoEl.innerHTML = (
                    'Procesando feedbacks con <strong>cascada automática</strong> ' +
                    '(Gemini → Ollama). Esto puede tomar unos segundos.'
                );
            } else {
                const nombreModelo = modeloElegido.replace(
                    /^\[Ollama\]\s*|\[Gemini\]\s*/i,
                    '',
                );
                const esGemini = modeloElegido.toLowerCase().includes('gemini');
                const proveedor = esGemini ? 'Google Gemini' : 'IA local';
                progresoEl.innerHTML = (
                    `Procesando feedbacks con <strong>${this.escaparHtml(nombreModelo)}</strong> ` +
                    `(${proveedor}). Esto puede tomar unos segundos.`
                );
            }
        }

        this.mostrarEstadoIA('cargando');

        const body: Record<string, unknown> = {
            ...this.obtenerFiltrosJson(),
            forzar,
        };
        if (modeloElegido) {
            body['modelo'] = modeloElegido;
        }

        fetch(this.urls.analisisIA, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.obtenerCsrfToken(),
            },
            body: JSON.stringify(body),
        })
            .then(r => r.json())
            .then((data: FbrAnalisisIAData) => {
                if (data.success) {
                    this.renderizarAnalisisIA(data);
                    this.mostrarEstadoIA('resultado');
                } else {
                    const errEl = document.getElementById('iaErrorMensaje');
                    if (errEl) {
                        errEl.textContent = data.error || 'Error al generar el análisis.';
                    }
                    this.mostrarEstadoIA('error');
                }
            })
            .catch((err) => {
                console.error('[AnalisisIA Rechazo] Error de red:', err);
                const errEl = document.getElementById('iaErrorMensaje');
                if (errEl) {
                    errEl.textContent = (
                        'No se pudo conectar con el servidor. '
                        + 'Verifica que el servicio de IA esté activo.'
                    );
                }
                this.mostrarEstadoIA('error');
            });
    }

    private renderizarAnalisisIA(data: FbrAnalisisIAData): void {
        const badge = document.getElementById('iaBadgeSentimiento');
        if (badge) {
            const sentimientoLabel: Record<string, string> = {
                positivo: 'Positivo',
                negativo: 'Negativo',
                mixto: 'Mixto',
                neutral: 'Neutral',
            };
            const icono = data.icono || 'bi-emoji-expressionless';
            const sentimiento = data.sentimiento_general || 'neutral';
            badge.innerHTML = (
                `<i class="bi ${this.escaparHtml(icono)} me-1"></i>`
                + `${sentimientoLabel[sentimiento] || 'Neutral'}`
            );
            badge.className = (
                `badge ia-badge-sentimiento ia-sentimiento-${sentimiento}`
            );
        }

        const resumen = document.getElementById('iaResumenEjecutivo');
        if (resumen) resumen.textContent = data.resumen_ejecutivo || '';

        const chipsPositivos = document.getElementById('iaTemasPositivos');
        if (chipsPositivos) {
            const temas = data.temas_positivos || [];
            chipsPositivos.innerHTML = temas.length > 0
                ? temas.map(
                    t => `<span class="ia-chip ia-chip-positivo">${this.escaparHtml(t)}</span>`,
                ).join('')
                : '<span class="text-muted small fst-italic">Sin señales favorables destacadas</span>';
        }

        const chipsNegativos = document.getElementById('iaTemasNegativos');
        if (chipsNegativos) {
            const temas = data.temas_negativos || [];
            chipsNegativos.innerHTML = temas.length > 0
                ? temas.map(
                    t => `<span class="ia-chip ia-chip-negativo">${this.escaparHtml(t)}</span>`,
                ).join('')
                : '<span class="text-muted small fst-italic">Sin razones de rechazo detectadas</span>';
        }

        const rec = document.getElementById('iaRecomendacion');
        if (rec) {
            if (data.recomendacion_ia) {
                rec.innerHTML = (
                    `<i class="bi bi-lightbulb-fill me-2 text-warning"></i>`
                    + `${this.escaparHtml(data.recomendacion_ia)}`
                );
                rec.classList.remove('d-none');
            } else {
                rec.classList.add('d-none');
            }
        }

        const metadatos = document.getElementById('iaMetadatos');
        if (metadatos) {
            const cacheLabel = data.desde_cache
                ? '<span class="ia-cache-badge">caché</span>'
                : '<span class="ia-cache-badge ia-cache-nuevo">nuevo</span>';
            metadatos.innerHTML = (
                `<i class="bi bi-cpu me-1"></i>${this.escaparHtml(data.modelo_usado || '')} `
                + `· ${data.total_encuestas || 0} feedbacks `
                + `· ${this.escaparHtml(data.fecha_analisis || '')} `
                + cacheLabel
            );
        }
    }

    /**
     * CSRF: en producción la cookie es sigma_csrftoken; en dev csrftoken.
     */
    private obtenerCsrfToken(): string {
        // CSRF global (csrf.ts)
        return window.getCsrfToken?.() ?? '';
    }

    // ── Helpers ───────────────────────────────────────────────────────

    private renderizarBadgeEstado(estado: string, diasRestantes: number): string {
        const config: { [key: string]: { texto: string; clase: string; icono: string } } = {
            respondido: { texto: 'Respondido', clase: 'respondido', icono: 'bi-check-circle-fill' },
            pendiente: { texto: `Pendiente (${diasRestantes}d)`, clase: 'pendiente', icono: 'bi-hourglass-split' },
            expirado: { texto: 'Expirado', clase: 'expirado', icono: 'bi-x-circle-fill' },
            no_enviado: { texto: 'No enviado', clase: 'no_enviado', icono: 'bi-dash-circle' },
        };
        const c = config[estado] || config.no_enviado;
        return `<span class="fbr-badge ${c.clase}"><i class="bi ${c.icono}"></i> ${c.texto}</span>`;
    }

    private setTexto(id: string, texto: string): void {
        const el = document.getElementById(id);
        if (el) el.textContent = texto;
    }

    private escaparHtml(texto: string): string {
        const div = document.createElement('div');
        div.textContent = texto;
        return div.innerHTML;
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new DashboardFeedbackRechazo();
    dashboard.inicializar();
});
