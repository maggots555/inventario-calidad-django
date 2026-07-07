/**
 * Dashboard de Seguimiento de Clientes
 * Lógica cliente: filtros AJAX, KPIs, tabla paginada y gráficas Chart.js.
 *
 * API endpoints consumidos:
 *   GET /servicio-tecnico/seguimiento-enlaces/api/kpis/
 *   GET /servicio-tecnico/seguimiento-enlaces/api/tendencia/
 *   GET /servicio-tecnico/seguimiento-enlaces/api/top/
 *   GET /servicio-tecnico/seguimiento-enlaces/api/tabla/
 *   GET /servicio-tecnico/seguimiento-enlaces/api/embudo/
 */

interface PasoEmbudo {
    id: string;
    label: string;
    total: number;
    tasa: number;
}

interface EmbudoSeguimiento {
    total_enlaces: number;
    pasos: PasoEmbudo[];
    push_suscritos: number;
    push_sin_suscripcion: number;
    tasa_push: number;
    con_pdf_diagnostico?: number;
    pdf_diagnostico_abiertos?: number;
}

// ─── Interfaces ─────────────────────────────────────────────────────────────

interface KPIsEnlaces {
    total_enlaces: number;
    total_accesos: number;
    promedio_accesos: number;
    sin_visitas: number;
    correos_enviados: number;
    correos_no_enviados: number;
    tasa_apertura: number;
    push_suscritos: number;
    push_sin_suscripcion: number;
    tasa_push: number;
}

interface PuntoDiario {
    dia: string;
    total: number;
}

interface TendenciaEnlaces {
    creados: PuntoDiario[];
    accesos: PuntoDiario[];
}

interface TopItem {
    folio: string;
    equipo: string;
    accesos: number;
    ultimo_acceso: string;
}

interface TopEnlaces {
    top: TopItem[];
}

interface FilaEnlace {
    folio: string;  // orden_cliente
    orden_id: number;
    orden_cliente: string;
    numero_serie: string;
    equipo: string;
    email: string;
    sucursal: string;
    responsable: string;
    estado: string;
    accesos: number;
    correo_enviado: boolean;
    push_activo: boolean;
    push_dispositivos: number;
    push_fecha: string;
    pwa_instalada: boolean;
    chat_usado: boolean;
    tiene_pdf_diagnostico: boolean;
    diagnostico_pdf_abierto: boolean;
    fecha_creacion: string;
    ultimo_acceso: string;
}

interface TablaEnlaces {
    filas: FilaEnlace[];
    total: number;
    pagina: number;
    total_paginas: number;
    tiene_siguiente: boolean;
    tiene_anterior: boolean;
}

// ─── Clase principal ─────────────────────────────────────────────────────────

class DashboardSeguimientoEnlaces {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    private chartTendencia: any = null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    private chartTop: any = null;
    private paginaActual: number = 1;

    // Elemento raíz; si no existe en el DOM no hacemos nada
    constructor() {
        if (!document.getElementById('kpiContainer')) return;
        this.init();
    }

    private init(): void {
        this.bindFiltros();
        this.cargarTodo();
    }

    // ── Filtros ──────────────────────────────────────────────────────────────

    private bindFiltros(): void {
        document.getElementById('btnAplicar')?.addEventListener('click', () => {
            this.paginaActual = 1;
            this.cargarTodo();
        });

        document.getElementById('btnLimpiar')?.addEventListener('click', () => {
            (document.getElementById('filtroFechaDesde') as HTMLInputElement).value = '';
            (document.getElementById('filtroFechaHasta') as HTMLInputElement).value = '';
            (document.getElementById('filtroResponsable') as HTMLSelectElement).value = '';
            (document.getElementById('filtroSucursal') as HTMLSelectElement).value = '';
            (document.getElementById('filtroTipoOrden') as HTMLSelectElement).value = '';
            this.paginaActual = 1;
            this.cargarTodo();
        });

        document.getElementById('tablaOrden')?.addEventListener('change', () => {
            this.paginaActual = 1;
            this.cargarTabla();
        });

        document.getElementById('btnPaginaAnterior')?.addEventListener('click', () => {
            this.paginaActual--;
            this.cargarTabla();
        });

        document.getElementById('btnPaginaSiguiente')?.addEventListener('click', () => {
            this.paginaActual++;
            this.cargarTabla();
        });
    }

    private buildParams(extra: Record<string, string | number> = {}): string {
        const params = new URLSearchParams();

        const desde = (document.getElementById('filtroFechaDesde') as HTMLInputElement)?.value;
        const hasta  = (document.getElementById('filtroFechaHasta') as HTMLInputElement)?.value;
        const resp   = (document.getElementById('filtroResponsable') as HTMLSelectElement)?.value;
        const suc    = (document.getElementById('filtroSucursal') as HTMLSelectElement)?.value;
        const tipo   = (document.getElementById('filtroTipoOrden') as HTMLSelectElement)?.value;

        if (desde) params.set('fecha_desde', desde);
        if (hasta)  params.set('fecha_hasta', hasta);
        if (resp)   params.set('responsable_id', resp);
        if (suc)    params.set('sucursal_id', suc);
        if (tipo)   params.set('tipo_orden', tipo);

        Object.entries(extra).forEach(([k, v]) => params.set(k, String(v)));

        return params.toString();
    }

    // ── Carga total ──────────────────────────────────────────────────────────

    private cargarTodo(): void {
        this.cargarKPIs();
        this.cargarEmbudo();
        this.cargarTendencia();
        this.cargarTop();
        this.cargarTabla();
    }

    // ── KPIs ─────────────────────────────────────────────────────────────────

    private async cargarKPIs(): Promise<void> {
        const url = `/servicio-tecnico/seguimiento-enlaces/api/kpis/?${this.buildParams()}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok) return;
            const data: KPIsEnlaces = await resp.json();
            this.renderKPIs(data);
        } catch (_) { /* silencioso */ }
    }

    private renderKPIs(d: KPIsEnlaces): void {
        const set = (id: string, val: string | number) => {
            const el = document.getElementById(id);
            if (el) el.textContent = String(val);
        };

        set('kpiTotalEnlaces', d.total_enlaces.toLocaleString('es-MX'));
        set('kpiTotalAccesos', d.total_accesos.toLocaleString('es-MX'));
        set('kpiPromedioAccesos', d.promedio_accesos.toLocaleString('es-MX'));
        set('kpiSinVisitas', d.sin_visitas.toLocaleString('es-MX'));
        set('kpiCorreosEnviados', d.correos_enviados.toLocaleString('es-MX'));
        set('kpiTasaApertura', `${d.tasa_apertura}%`);

        const noEnv = document.getElementById('kpiCorreosNoenviados');
        if (noEnv) noEnv.textContent = `${d.correos_no_enviados} sin enviar`;

        set('kpiPushSuscritos', d.push_suscritos.toLocaleString('es-MX'));
        set('kpiPushSin', d.push_sin_suscripcion.toLocaleString('es-MX'));
        set('kpiTasaPush', `${d.tasa_push}%`);
    }

    // ── Embudo de adopción ───────────────────────────────────────────────────

    private async cargarEmbudo(): Promise<void> {
        const loader = document.getElementById('loaderEmbudo');
        const container = document.getElementById('embudoContainer');

        if (loader) loader.style.display = 'block';
        if (container) container.style.display = 'none';

        const url = `/servicio-tecnico/seguimiento-enlaces/api/embudo/?${this.buildParams()}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok) throw new Error('API error');
            const data: EmbudoSeguimiento = await resp.json();
            this.renderEmbudo(data);
            this.renderPushDesdeEmbudo(data);
        } catch (_) {
            if (container) {
                container.style.display = 'block';
                container.innerHTML = '<p class="text-muted small mb-0">No se pudo cargar el embudo.</p>';
            }
        } finally {
            if (loader) loader.style.display = 'none';
        }
    }

    private renderEmbudo(d: EmbudoSeguimiento): void {
        const container = document.getElementById('embudoContainer');
        if (!container) return;

        if (!d.pasos.length) {
            container.innerHTML = '<p class="text-muted small mb-0">Sin datos para el embudo.</p>';
            container.style.display = 'block';
            return;
        }

        const maxTotal = Math.max(...d.pasos.map(p => p.total), 1);

        container.innerHTML = d.pasos.map(p => `
            <div class="se-embudo-paso">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="se-embudo-label">${p.label}</span>
                    <span class="se-embudo-valor">${p.total.toLocaleString('es-MX')} <small class="text-muted">(${p.tasa}%)</small></span>
                </div>
                <div class="se-embudo-barra-track">
                    <div class="se-embudo-barra-fill" style="width:${Math.round((p.total / maxTotal) * 100)}%"></div>
                </div>
            </div>
        `).join('');

        container.style.display = 'block';
    }

    private renderPushDesdeEmbudo(d: EmbudoSeguimiento): void {
        const set = (id: string, val: string | number) => {
            const el = document.getElementById(id);
            if (el) el.textContent = String(val);
        };
        set('kpiPushSuscritos', d.push_suscritos.toLocaleString('es-MX'));
        set('kpiPushSin', d.push_sin_suscripcion.toLocaleString('es-MX'));
        set('kpiTasaPush', `${d.tasa_push}%`);
    }

    // ── Tendencia ────────────────────────────────────────────────────────────

    private async cargarTendencia(): Promise<void> {
        const loader = document.getElementById('loaderTendencia');
        const canvas = document.getElementById('chartTendencia') as HTMLCanvasElement | null;
        const empty  = document.getElementById('emptyTendencia');

        if (loader) loader.style.display = 'flex';
        if (canvas) canvas.style.display = 'none';
        if (empty)  empty.style.display  = 'none';

        const url = `/servicio-tecnico/seguimiento-enlaces/api/tendencia/?${this.buildParams()}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok) throw new Error('API error');
            const data: TendenciaEnlaces = await resp.json();

            if (!data.creados.length && !data.accesos.length) {
                if (loader) loader.style.display = 'none';
                if (empty)  empty.style.display  = 'block';
                return;
            }

            if (loader) loader.style.display = 'none';
            if (canvas) canvas.style.display = 'block';
            this.renderTendencia(data, canvas!);
        } catch (_) {
            if (loader) loader.style.display = 'none';
            if (empty)  empty.style.display  = 'block';
        }
    }

    private renderTendencia(data: TendenciaEnlaces, canvas: HTMLCanvasElement): void {
        if (this.chartTendencia) { this.chartTendencia.destroy(); this.chartTendencia = null; }

        // Unir todas las fechas y ordenar
        const allDates = Array.from(new Set([
            ...data.creados.map(d => d.dia),
            ...data.accesos.map(d => d.dia),
        ])).sort();

        const creadosMap = new Map(data.creados.map(d => [d.dia, d.total]));
        const accesosMap = new Map(data.accesos.map(d => [d.dia, d.total]));

        const labels  = allDates.map(d => {
            const [y, m, day] = d.split('-');
            return `${day}/${m}/${y.slice(2)}`;
        });
        const serieCreados  = allDates.map(d => creadosMap.get(d) ?? 0);
        const serieAccesos  = allDates.map(d => accesosMap.get(d) ?? 0);

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
                        label: (ctx: any) => ` ${ctx.dataset.label}: ${ctx.parsed.y}`,
                    }},
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

    private async cargarTop(): Promise<void> {
        const loader = document.getElementById('loaderTop');
        const canvas = document.getElementById('chartTop') as HTMLCanvasElement | null;
        const empty  = document.getElementById('emptyTop');

        if (loader) loader.style.display = 'flex';
        if (canvas) canvas.style.display = 'none';
        if (empty)  empty.style.display  = 'none';

        const url = `/servicio-tecnico/seguimiento-enlaces/api/top/?${this.buildParams()}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok) throw new Error('API error');
            const data: TopEnlaces = await resp.json();

            if (!data.top.length) {
                if (loader) loader.style.display = 'none';
                if (empty)  empty.style.display  = 'block';
                return;
            }

            if (loader) loader.style.display = 'none';
            if (canvas) canvas.style.display = 'block';
            this.renderTop(data.top, canvas!);
        } catch (_) {
            if (loader) loader.style.display = 'none';
            if (empty)  empty.style.display  = 'block';
        }
    }

    private renderTop(items: TopItem[], canvas: HTMLCanvasElement): void {
        if (this.chartTop) { this.chartTop.destroy(); this.chartTop = null; }

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
                        label: (ctx: any) => ` ${ctx.parsed.x} acceso${ctx.parsed.x !== 1 ? 's' : ''}`,
                    }},
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

    private async cargarTabla(): Promise<void> {
        const loader = document.getElementById('loaderTabla');
        const tbody  = document.getElementById('tablaBody');
        const badge  = document.getElementById('tablaTotalBadge');

        if (loader) loader.style.display = 'flex';
        if (tbody)  tbody.innerHTML = '';

        const orden = (document.getElementById('tablaOrden') as HTMLSelectElement)?.value ?? '-fecha_creacion';
        const url = `/servicio-tecnico/seguimiento-enlaces/api/tabla/?${this.buildParams({
            page: this.paginaActual,
            order_by: orden,
        })}`;

        try {
            const resp = await fetch(url);
            if (!resp.ok) throw new Error('API error');
            const data: TablaEnlaces = await resp.json();

            if (loader) loader.style.display = 'none';
            if (badge)  badge.textContent = data.total.toLocaleString('es-MX');

            this.renderTabla(data.filas);
            this.renderPaginacion(data);
        } catch (_) {
            if (loader) loader.style.display = 'none';
            if (tbody)  tbody.innerHTML = `
                <tr><td colspan="14" class="text-center text-danger py-3">
                    <i class="bi bi-exclamation-circle me-1"></i>Error al cargar datos
                </td></tr>`;
        }
    }

    private renderTabla(filas: FilaEnlace[]): void {
        const tbody = document.getElementById('tablaBody');
        if (!tbody) return;

        if (!filas.length) {
            tbody.innerHTML = `
                <tr><td colspan="14" class="text-center text-muted py-4">
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

            const pushTooltip = f.push_activo
                ? `Activado${f.push_dispositivos > 1 ? ` (${f.push_dispositivos} dispositivos)` : ''}${f.push_fecha !== '—' ? ` — ${f.push_fecha}` : ''}`
                : 'El cliente no ha activado notificaciones push';

            const pushBadge = f.push_activo
                ? `<span class="badge-push-ok" title="${pushTooltip}"><i class="bi bi-bell-fill me-1"></i>Activo</span>`
                : `<span class="badge-push-no" title="${pushTooltip}"><i class="bi bi-bell-slash me-1"></i>No activado</span>`;

            const pwaBadge = f.pwa_instalada
                ? `<span class="badge-pwa-ok" title="PWA instalada o abierta como app"><i class="bi bi-phone-fill me-1"></i>Sí</span>`
                : `<span class="badge-pwa-no" title="Sin evento de instalación PWA"><i class="bi bi-phone me-1"></i>No</span>`;

            const chatBadge = f.chat_usado
                ? `<span class="badge-chat-ok" title="Envió al menos un mensaje al chat IA"><i class="bi bi-chat-dots-fill me-1"></i>Sí</span>`
                : `<span class="badge-chat-no" title="No usó el chat IA"><i class="bi bi-chat me-1"></i>No</span>`;

            let pdfDxBadge: string;
            if (!f.tiene_pdf_diagnostico) {
                pdfDxBadge = `<span class="badge-pdf-dx-na" title="Aún no se ha enviado diagnóstico con PDF">—</span>`;
            } else if (f.diagnostico_pdf_abierto) {
                pdfDxBadge = `<span class="badge-pdf-dx-ok" title="El cliente abrió el PDF de diagnóstico"><i class="bi bi-file-earmark-pdf-fill me-1"></i>Sí</span>`;
            } else {
                pdfDxBadge = `<span class="badge-pdf-dx-no" title="Diagnóstico enviado pero el cliente no ha abierto el PDF"><i class="bi bi-file-earmark-pdf me-1"></i>No</span>`;
            }

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
                <td class="text-center">${pushBadge}</td>
                <td class="text-center">${pdfDxBadge}</td>
                <td class="text-center">${pwaBadge}</td>
                <td class="text-center">${chatBadge}</td>
                <td class="text-nowrap">${f.fecha_creacion}</td>
                <td class="text-nowrap">${f.ultimo_acceso}</td>
            </tr>`;
        }).join('');
    }

    private renderPaginacion(data: TablaEnlaces): void {
        const info  = document.getElementById('tablaPaginaInfo');
        const prev  = document.getElementById('btnPaginaAnterior') as HTMLButtonElement | null;
        const next  = document.getElementById('btnPaginaSiguiente') as HTMLButtonElement | null;

        if (info) {
            const desde = (data.pagina - 1) * 50 + 1;
            const hasta = Math.min(data.pagina * 50, data.total);
            info.textContent = data.total > 0
                ? `Mostrando ${desde}–${hasta} de ${data.total.toLocaleString('es-MX')} enlace${data.total !== 1 ? 's' : ''}`
                : 'Sin resultados';
        }

        if (prev) prev.disabled = !data.tiene_anterior;
        if (next) next.disabled = !data.tiene_siguiente;
    }
}

// ── Bootstrap ────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    new DashboardSeguimientoEnlaces();
});
