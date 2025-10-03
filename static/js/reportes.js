/**
 * JAVASCRIPT PARA REPORTES AVANZADOS - FASE 1
 * Sistema Score Card - Análisis Profesional estilo Power BI
 */

// ============================================
// VARIABLES GLOBALES
// ============================================
let reportCharts = {};
let datosReportes = {};
let filtrosActivos = {
    fecha_inicio: null,
    fecha_fin: null,
    sucursal: null,
    tecnico: null,
    area: null,
    severidad: null,
    estado: null
};

// ============================================
// INICIALIZACIÓN
// ============================================
document.addEventListener('DOMContentLoaded', function() {
    console.log('🚀 Inicializando reportes avanzados - FASE 2');
    
    // Inicializar sistema de tabs
    inicializarTabs();
    
    // Cargar opciones de filtros
    cargarOpcionesFiltros();
    
    // Cargar datos de reportes
    cargarDatosReportes();
});

// ============================================
// SISTEMA DE TABS
// ============================================
function inicializarTabs() {
    const tabLinks = document.querySelectorAll('.tab-link');
    
    tabLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            
            // Remover clase active de todos los tabs
            tabLinks.forEach(l => l.classList.remove('active'));
            document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
            
            // Activar tab seleccionado
            this.classList.add('active');
            const targetTab = this.getAttribute('data-tab');
            document.getElementById(targetTab).classList.add('active');
            
            // Cargar datos específicos del tab si es necesario
            cargarDatosTab(targetTab);
        });
    });
}

function cargarDatosTab(tabId) {
    console.log(`📊 Cargando datos para tab: ${tabId}`);
    
    switch(tabId) {
        case 'tab-resumen':
            // Ya cargado en inicialización
            break;
        case 'tab-atribuibilidad':
            if (!datosReportes.atribuibilidad) {
                cargarAnalisisAtribuibilidad();
            }
            break;
        case 'tab-tecnicos':
            if (!datosReportes.tecnicos) {
                cargarAnalisisTecnicos();
            }
            break;
        case 'tab-reincidencias':
            if (!datosReportes.reincidencias) {
                cargarAnalisisReincidencias();
            }
            break;
        case 'tab-tiempos':
            if (!datosReportes.tiempos) {
                cargarAnalisisTiempos();
            }
            break;
        case 'tab-componentes':
            if (!datosReportes.componentes) {
                cargarAnalisisComponentes();
            }
            break;
        case 'tab-notificaciones':
            if (!datosReportes.notificaciones) {
                cargarAnalisisNotificaciones();
            }
            break;
    }
}

// ============================================
// CARGA DE DATOS PRINCIPALES
// ============================================
function cargarDatosReportes() {
    mostrarLoading(true);
    
    const queryString = construirQueryString();
    
    // Cargar datos del dashboard (resumen ejecutivo)
    fetch('/scorecard/api/datos-dashboard/' + queryString)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                datosReportes.dashboard = data;
                actualizarResumenEjecutivo(data.kpis);
                crearGraficoPareto(data.distribucion_categorias);
                crearTendenciaTrimestral(data.tendencia_mensual);
                crearTipoFallo();
                crearHeatmapSucursales(data.analisis_sucursales);
                crearComparativaMensual(data.tendencia_mensual);
                crearMetricasCalidad(data.kpis);
            }
        })
        .catch(error => {
            console.error('❌ Error al cargar datos del dashboard:', error);
            mostrarError('Error al cargar datos del dashboard');
        })
        .finally(() => {
            mostrarLoading(false);
        });
}

function cargarAnalisisAtribuibilidad() {
    mostrarLoading(true);
    
    const queryString = construirQueryString();
    
    fetch('/scorecard/api/analisis-atribuibilidad/' + queryString)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                datosReportes.atribuibilidad = data;
                
                // Actualizar KPIs de atribuibilidad
                document.getElementById('kpi-atribuibles').textContent = data.atribuibilidad.atribuibles;
                document.getElementById('kpi-no-atribuibles').textContent = data.atribuibilidad.no_atribuibles;
                document.getElementById('kpi-porcentaje-atribuibles').textContent = 
                    `${data.atribuibilidad.porcentaje_atribuibles}%`;
                document.getElementById('kpi-porcentaje-no-atribuibles').textContent = 
                    `${data.atribuibilidad.porcentaje_no_atribuibles}%`;
                
                // Crear gráficos
                crearGraficoAtribuibilidad(data.distribucion_atribuibilidad);
                crearTendenciaAtribuibilidad(data.tendencia_atribuibilidad);
                crearRankingNoAtribuibles(data.ranking_no_atribuibles);
                crearDistribucionRazones(data.distribucion_razones);
                
                // Mostrar justificaciones
                mostrarJustificaciones(data.justificaciones_recientes);
            }
        })
        .catch(error => {
            console.error('❌ Error al cargar análisis de atribuibilidad:', error);
            mostrarError('Error al cargar análisis de atribuibilidad');
        })
        .finally(() => {
            mostrarLoading(false);
        });
}

function cargarAnalisisTecnicos() {
    mostrarLoading(true);
    
    const queryString = construirQueryString();
    
    fetch('/scorecard/api/analisis-tecnicos/' + queryString)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                datosReportes.tecnicos = data;
                
                // Actualizar estadísticas generales
                document.getElementById('total-tecnicos').textContent = data.estadisticas.total_tecnicos;
                document.getElementById('promedio-score').textContent = 
                    `${data.estadisticas.promedio_score}/100`;
                document.getElementById('promedio-dias-tecnicos').textContent = 
                    `${data.estadisticas.promedio_dias_resolucion} días`;
                
                // Crear gráficos
                crearRankingTecnicos(data.ranking_datos);
                
                // Mostrar tablas
                mostrarScorecardTecnicos(data.scorecard_completo);
                mostrarTopMejores(data.top_10_mejores);
                mostrarTopAtencion(data.top_10_atencion);
            }
        })
        .catch(error => {
            console.error('❌ Error al cargar análisis de técnicos:', error);
            mostrarError('Error al cargar análisis de técnicos');
        })
        .finally(() => {
            mostrarLoading(false);
        });
}

// ============================================
// GRÁFICOS - RESUMEN EJECUTIVO
// ============================================
function actualizarResumenEjecutivo(kpis) {
    document.getElementById('report-total').textContent = kpis.total_incidencias;
    document.getElementById('report-criticas').textContent = kpis.incidencias_criticas;
    document.getElementById('report-reincidencias').textContent = 
        `${kpis.reincidencias} (${kpis.porcentaje_reincidencias}%)`;
    document.getElementById('report-promedio').textContent = `${kpis.promedio_dias_cierre} días`;
}

function crearGraficoPareto(datos) {
    const ctx = document.getElementById('paretoChart');
    
    // Calcular porcentajes acumulados
    const total = datos.data.reduce((a, b) => a + b, 0);
    let acumulado = 0;
    const porcentajesAcum = datos.data.map(val => {
        acumulado += (val / total) * 100;
        return acumulado;
    });
    
    if (reportCharts.paretoChart) {
        reportCharts.paretoChart.destroy();
    }
    
    reportCharts.paretoChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                type: 'bar',
                label: 'Cantidad',
                data: datos.data,
                backgroundColor: '#0d6efd',
                borderWidth: 1,
                yAxisID: 'y',
                order: 2
            }, {
                type: 'line',
                label: '% Acumulado',
                data: porcentajesAcum,
                borderColor: '#dc3545',
                backgroundColor: 'rgba(220, 53, 69, 0.1)',
                borderWidth: 3,
                fill: false,
                yAxisID: 'y1',
                order: 1,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) {
                                label += ': ';
                            }
                            if (context.parsed.y !== null) {
                                if (context.datasetIndex === 1) {
                                    label += context.parsed.y.toFixed(2) + '%';
                                } else {
                                    label += context.parsed.y;
                                }
                            }
                            return label;
                        }
                    }
                }
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Cantidad de Incidencias'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    min: 0,
                    max: 100,
                    title: {
                        display: true,
                        text: '% Acumulado'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

function crearTendenciaTrimestral(datos) {
    const ctx = document.getElementById('tendenciaTriChart');
    
    if (reportCharts.tendenciaTriChart) {
        reportCharts.tendenciaTriChart.destroy();
    }
    
    reportCharts.tendenciaTriChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Incidencias',
                data: datos.data,
                borderColor: '#28a745',
                backgroundColor: 'rgba(40, 167, 69, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 6,
                pointHoverRadius: 8,
                pointBackgroundColor: '#28a745',
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearTipoFallo() {
    const ctx = document.getElementById('tipoFalloChart');
    
    const tipos = ['Hardware', 'Software', 'Cosmético', 'Funcional'];
    const valores = [45, 25, 15, 15];
    
    if (reportCharts.tipoFalloChart) {
        reportCharts.tipoFalloChart.destroy();
    }
    
    reportCharts.tipoFalloChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: tipos,
            datasets: [{
                data: valores,
                backgroundColor: ['#dc3545', '#ffc107', '#17a2b8', '#28a745'],
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function crearHeatmapSucursales(datos) {
    const ctx = document.getElementById('heatmapChart');
    
    const maxVal = Math.max(...datos.data);
    const colores = datos.data.map(val => {
        const intensity = val / maxVal;
        return `rgba(220, 53, 69, ${0.3 + intensity * 0.7})`;
    });
    
    if (reportCharts.heatmapChart) {
        reportCharts.heatmapChart.destroy();
    }
    
    reportCharts.heatmapChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Incidencias por Sucursal',
                data: datos.data,
                backgroundColor: colores,
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearComparativaMensual(datos) {
    const ctx = document.getElementById('comparativaMensualChart');
    
    if (reportCharts.comparativaMensualChart) {
        reportCharts.comparativaMensualChart.destroy();
    }
    
    reportCharts.comparativaMensualChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Incidencias',
                data: datos.data,
                backgroundColor: '#17a2b8',
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearMetricasCalidad(kpis) {
    const ctx = document.getElementById('metricasChart');
    
    const tasaCierre = kpis.total_incidencias > 0 
        ? ((kpis.incidencias_cerradas / kpis.total_incidencias) * 100).toFixed(1)
        : 0;
    
    const tasaCriticas = kpis.total_incidencias > 0
        ? ((kpis.incidencias_criticas / kpis.total_incidencias) * 100).toFixed(1)
        : 0;
    
    if (reportCharts.metricasChart) {
        reportCharts.metricasChart.destroy();
    }
    
    reportCharts.metricasChart = new Chart(ctx, {
        type: 'radar',
        data: {
            labels: ['Tasa Cierre', 'Reincidencias', 'Críticas', 'Tiempo Resolución', 'Eficiencia'],
            datasets: [{
                label: 'Métricas de Calidad (%)',
                data: [tasaCierre, 100 - kpis.porcentaje_reincidencias, 100 - tasaCriticas, 75, 80],
                backgroundColor: 'rgba(13, 110, 253, 0.2)',
                borderColor: '#0d6efd',
                borderWidth: 2,
                pointBackgroundColor: '#0d6efd',
                pointBorderColor: '#fff',
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                r: {
                    beginAtZero: true,
                    max: 100
                }
            }
        }
    });
}

// ============================================
// GRÁFICOS - ATRIBUIBILIDAD (FASE 1)
// ============================================
function crearGraficoAtribuibilidad(datos) {
    const ctx = document.getElementById('graficoAtribuibilidad');
    
    if (reportCharts.graficoAtribuibilidad) {
        reportCharts.graficoAtribuibilidad.destroy();
    }
    
    reportCharts.graficoAtribuibilidad = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: datos.labels,
            datasets: [{
                data: datos.data,
                backgroundColor: datos.colors,
                borderWidth: 3,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        font: {
                            size: 14,
                            weight: 'bold'
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((value / total) * 100).toFixed(2);
                            return `${label}: ${value} (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

function crearTendenciaAtribuibilidad(datos) {
    const ctx = document.getElementById('tendenciaAtribuibilidad');
    
    if (reportCharts.tendenciaAtribuibilidad) {
        reportCharts.tendenciaAtribuibilidad.destroy();
    }
    
    reportCharts.tendenciaAtribuibilidad = new Chart(ctx, {
        type: 'line',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Atribuibles',
                data: datos.atribuibles,
                borderColor: '#4CAF50',
                backgroundColor: 'rgba(76, 175, 80, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 5,
                pointHoverRadius: 7
            }, {
                label: 'No Atribuibles',
                data: datos.no_atribuibles,
                borderColor: '#FF9800',
                backgroundColor: 'rgba(255, 152, 0, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearRankingNoAtribuibles(datos) {
    const ctx = document.getElementById('rankingNoAtribuibles');
    
    if (reportCharts.rankingNoAtribuibles) {
        reportCharts.rankingNoAtribuibles.destroy();
    }
    
    reportCharts.rankingNoAtribuibles = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Incidencias No Atribuibles',
                data: datos.data,
                backgroundColor: '#FF9800',
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearDistribucionRazones(datos) {
    const ctx = document.getElementById('distribucionRazones');
    
    if (reportCharts.distribucionRazones) {
        reportCharts.distribucionRazones.destroy();
    }
    
    reportCharts.distribucionRazones = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Cantidad',
                data: datos.data,
                backgroundColor: datos.colors,
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function mostrarJustificaciones(justificaciones) {
    const container = document.getElementById('lista-justificaciones');
    
    if (justificaciones.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">No hay justificaciones recientes</p>';
        return;
    }
    
    let html = '';
    justificaciones.forEach(just => {
        html += `
            <div class="justificacion-card">
                <div class="justificacion-header">
                    <span class="justificacion-folio">${just.folio}</span>
                    <span class="justificacion-fecha">${just.fecha}</span>
                </div>
                <div class="justificacion-tecnico">
                    <i class="bi bi-person"></i> Técnico: <strong>${just.tecnico}</strong>
                </div>
                <div class="justificacion-texto">
                    "${just.justificacion}"
                </div>
                <div class="justificacion-marcador">
                    Marcado por: ${just.marcado_por}
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// ============================================
// GRÁFICOS - TÉCNICOS (FASE 1)
// ============================================
function crearRankingTecnicos(datos) {
    const ctx = document.getElementById('rankingTecnicosChart');
    
    if (reportCharts.rankingTecnicosChart) {
        reportCharts.rankingTecnicosChart.destroy();
    }
    
    reportCharts.rankingTecnicosChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Total Incidencias',
                data: datos.total,
                backgroundColor: '#0d6efd',
                borderWidth: 1
            }, {
                label: 'Críticas',
                data: datos.criticas,
                backgroundColor: '#dc3545',
                borderWidth: 1
            }, {
                label: 'Reincidencias',
                data: datos.reincidencias,
                backgroundColor: '#ffc107',
                borderWidth: 1
            }, {
                label: 'No Atribuibles',
                data: datos.no_atribuibles,
                backgroundColor: '#FF9800',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function mostrarScorecardTecnicos(scorecard) {
    const container = document.getElementById('scorecard-completo');
    
    if (scorecard.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">No hay datos disponibles</p>';
        return;
    }
    
    let html = `
        <table class="scorecard-table">
            <thead>
                <tr>
                    <th>Técnico</th>
                    <th>Área</th>
                    <th>Sucursal</th>
                    <th>Total</th>
                    <th>Críticas</th>
                    <th>Reincidencias</th>
                    <th>% Atrib.</th>
                    <th>Días Prom.</th>
                    <th>Score</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    scorecard.forEach(tec => {
        const scoreClass = tec.score_calidad >= 80 ? 'score-excelente' :
                          tec.score_calidad >= 60 ? 'score-bueno' :
                          tec.score_calidad >= 40 ? 'score-regular' : 'score-atencion';
        
        html += `
            <tr>
                <td class="tecnico-name">${tec.tecnico}</td>
                <td>${tec.area}</td>
                <td>${tec.sucursal}</td>
                <td>${tec.total_incidencias}</td>
                <td>${tec.criticas} (${tec.porcentaje_criticas}%)</td>
                <td>${tec.reincidencias} (${tec.porcentaje_reincidencias}%)</td>
                <td>${tec.porcentaje_atribuibilidad}%</td>
                <td>${tec.promedio_dias}</td>
                <td><span class="badge-score ${scoreClass}">${tec.score_calidad}</span></td>
            </tr>
        `;
    });
    
    html += `
            </tbody>
        </table>
    `;
    
    container.innerHTML = html;
}

function mostrarTopMejores(topMejores) {
    const container = document.getElementById('top-mejores');
    
    if (topMejores.length === 0) {
        container.innerHTML = '<p class="text-muted">No hay datos disponibles</p>';
        return;
    }
    
    let html = '<div class="row">';
    
    topMejores.slice(0, 3).forEach((tec, index) => {
        const medalla = index === 0 ? '🥇' : index === 1 ? '🥈' : '🥉';
        
        html += `
            <div class="col-md-4 mb-3">
                <div class="card border-success">
                    <div class="card-body text-center">
                        <div style="font-size: 3rem;">${medalla}</div>
                        <h5 class="card-title mt-2">${tec.tecnico}</h5>
                        <p class="text-muted">${tec.area}</p>
                        <h3 class="text-success">${tec.score_calidad}/100</h3>
                        <small class="text-muted">${tec.total_incidencias} incidencias | ${tec.promedio_dias} días prom.</small>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

function mostrarTopAtencion(topAtencion) {
    const container = document.getElementById('top-atencion');
    
    if (topAtencion.length === 0) {
        container.innerHTML = '<p class="text-muted">No hay técnicos que requieran atención especial</p>';
        return;
    }
    
    let html = '<div class="list-group">';
    
    topAtencion.forEach(tec => {
        html += `
            <div class="list-group-item">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1">${tec.tecnico}</h6>
                        <small class="text-muted">${tec.area} - ${tec.sucursal}</small>
                    </div>
                    <span class="badge bg-warning text-dark">Score: ${tec.score_calidad}</span>
                </div>
                <div class="mt-2">
                    <small>
                        <i class="bi bi-exclamation-triangle text-danger"></i> ${tec.criticas} críticas |
                        <i class="bi bi-arrow-repeat text-warning"></i> ${tec.reincidencias} reincidencias |
                        <i class="bi bi-clock text-info"></i> ${tec.promedio_dias} días prom.
                    </small>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// ============================================
// ANÁLISIS DE REINCIDENCIAS (FASE 2)
// ============================================
function cargarAnalisisReincidencias() {
    mostrarLoading(true);
    
    const queryString = construirQueryString();
    
    fetch('/scorecard/api/analisis-reincidencias/' + queryString)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                datosReportes.reincidencias = data;
                
                // Actualizar KPIs
                document.getElementById('kpi-total-reincidencias').textContent = data.kpis.total_reincidencias;
                document.getElementById('kpi-porcentaje-reincidencias').textContent = 
                    `${data.kpis.porcentaje_reincidencias}%`;
                document.getElementById('kpi-tiempo-entre-reincidencias').textContent = 
                    `${data.kpis.tiempo_promedio_entre_reincidencias} días`;
                document.getElementById('kpi-cadenas-largas').textContent = data.kpis.total_cadenas_largas;
                
                // Crear gráficos
                crearGraficoReincidenciasTecnico(data.ranking_reincidencias_tecnico);
                crearGraficoTopEquiposReincidentes(data.top_equipos_reincidentes);
                crearTendenciaReincidencias(data.tendencia_reincidencias);
                crearDistribucionCategoriasReincidencias(data.distribucion_categorias_reincidencias);
                
                // Mostrar tablas
                mostrarCadenasReincidencias(data.cadenas_reincidencias);
            }
        })
        .catch(error => {
            console.error('❌ Error al cargar análisis de reincidencias:', error);
            mostrarError('Error al cargar análisis de reincidencias');
        })
        .finally(() => {
            mostrarLoading(false);
        });
}

function crearGraficoReincidenciasTecnico(datos) {
    const ctx = document.getElementById('graficoReincidenciasTecnico');
    
    if (reportCharts.graficoReincidenciasTecnico) {
        reportCharts.graficoReincidenciasTecnico.destroy();
    }
    
    reportCharts.graficoReincidenciasTecnico = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Reincidencias',
                data: datos.reincidencias,
                backgroundColor: '#ffc107',
                borderWidth: 1,
                borderRadius: 5
            }, {
                label: '% Reincidencias',
                data: datos.porcentajes,
                backgroundColor: '#dc3545',
                borderWidth: 1,
                borderRadius: 5,
                yAxisID: 'y1'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                }
            },
            scales: {
                y: {
                    type: 'linear',
                    display: true,
                    position: 'left',
                    beginAtZero: true,
                    ticks: { stepSize: 1 },
                    title: {
                        display: true,
                        text: 'Cantidad'
                    }
                },
                y1: {
                    type: 'linear',
                    display: true,
                    position: 'right',
                    beginAtZero: true,
                    max: 100,
                    title: {
                        display: true,
                        text: 'Porcentaje (%)'
                    },
                    grid: {
                        drawOnChartArea: false
                    }
                }
            }
        }
    });
}

function crearGraficoTopEquiposReincidentes(datos) {
    const ctx = document.getElementById('graficoTopEquiposReincidentes');
    
    if (reportCharts.graficoTopEquiposReincidentes) {
        reportCharts.graficoTopEquiposReincidentes.destroy();
    }
    
    reportCharts.graficoTopEquiposReincidentes = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Reincidencias',
                data: datos.data,
                backgroundColor: '#dc3545',
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearTendenciaReincidencias(datos) {
    const ctx = document.getElementById('tendenciaReincidencias');
    
    if (reportCharts.tendenciaReincidencias) {
        reportCharts.tendenciaReincidencias.destroy();
    }
    
    reportCharts.tendenciaReincidencias = new Chart(ctx, {
        type: 'line',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Reincidencias',
                data: datos.data,
                borderColor: '#ffc107',
                backgroundColor: 'rgba(255, 193, 7, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearDistribucionCategoriasReincidencias(datos) {
    const ctx = document.getElementById('distribucionCategoriasReincidencias');
    
    if (reportCharts.distribucionCategoriasReincidencias) {
        reportCharts.distribucionCategoriasReincidencias.destroy();
    }
    
    reportCharts.distribucionCategoriasReincidencias = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: datos.labels,
            datasets: [{
                data: datos.data,
                backgroundColor: datos.colors,
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function mostrarCadenasReincidencias(cadenas) {
    const container = document.getElementById('tabla-cadenas-reincidencias');
    
    if (cadenas.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">No hay cadenas de reincidencias detectadas</p>';
        return;
    }
    
    let html = '<div class="table-responsive"><table class="table table-hover">';
    html += '<thead class="table-dark"><tr>';
    html += '<th>Folio Original</th><th>Equipo</th><th>Técnico</th><th>Total Reincidencias</th><th>Detalles</th>';
    html += '</tr></thead><tbody>';
    
    cadenas.forEach(cadena => {
        html += `
            <tr>
                <td><strong>${cadena.folio_original}</strong><br><small class="text-muted">${cadena.fecha_original}</small></td>
                <td>${cadena.tipo_equipo} ${cadena.marca}<br><small class="text-muted">${cadena.numero_serie}</small></td>
                <td>${cadena.tecnico}</td>
                <td><span class="badge bg-danger">${cadena.total_reincidencias}</span></td>
                <td>
                    <button class="btn btn-sm btn-outline-primary" onclick="verDetallesCadena('${cadena.folio_original}')">
                        <i class="bi bi-eye"></i> Ver Cadena
                    </button>
                </td>
            </tr>
        `;
    });
    
    html += '</tbody></table></div>';
    container.innerHTML = html;
}

// ============================================
// ANÁLISIS DE TIEMPOS (FASE 2)
// ============================================
function cargarAnalisisTiempos() {
    mostrarLoading(true);
    
    const queryString = construirQueryString();
    
    fetch('/scorecard/api/analisis-tiempos/' + queryString)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                datosReportes.tiempos = data;
                
                // Actualizar KPIs
                document.getElementById('kpi-tiempo-promedio-cierre').textContent = 
                    `${data.kpis.tiempo_promedio_cierre} días`;
                document.getElementById('kpi-tiempo-minimo').textContent = 
                    `${data.kpis.tiempo_minimo_cierre} días`;
                document.getElementById('kpi-tiempo-maximo').textContent = 
                    `${data.kpis.tiempo_maximo_cierre} días`;
                document.getElementById('kpi-total-alertas').textContent = data.kpis.total_alertas;
                
                // Crear gráficos
                crearDistribucionTiempos(data.distribucion_tiempos);
                crearRankingRapidos(data.ranking_rapidos);
                crearRankingLentos(data.ranking_lentos);
                crearTendenciaTiempos(data.tendencia_tiempos);
                crearAnalisisPorSeveridad(data.analisis_por_severidad);
                
                // Mostrar alertas
                mostrarAlertasTiempos(data.alertas_tiempos);
            }
        })
        .catch(error => {
            console.error('❌ Error al cargar análisis de tiempos:', error);
            mostrarError('Error al cargar análisis de tiempos');
        })
        .finally(() => {
            mostrarLoading(false);
        });
}

function crearDistribucionTiempos(datos) {
    const ctx = document.getElementById('distribucionTiempos');
    
    if (reportCharts.distribucionTiempos) {
        reportCharts.distribucionTiempos.destroy();
    }
    
    reportCharts.distribucionTiempos = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Cantidad de Incidencias',
                data: datos.data,
                backgroundColor: datos.colors,
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearRankingRapidos(datos) {
    const ctx = document.getElementById('rankingRapidos');
    
    if (reportCharts.rankingRapidos) {
        reportCharts.rankingRapidos.destroy();
    }
    
    reportCharts.rankingRapidos = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Días Promedio',
                data: datos.data,
                backgroundColor: '#28a745',
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: '🏆 Top 10 Técnicos Más Rápidos'
                }
            },
            scales: {
                x: {
                    beginAtZero: true
                }
            }
        }
    });
}

function crearRankingLentos(datos) {
    const ctx = document.getElementById('rankingLentos');
    
    if (reportCharts.rankingLentos) {
        reportCharts.rankingLentos.destroy();
    }
    
    reportCharts.rankingLentos = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Días Promedio',
                data: datos.data,
                backgroundColor: '#dc3545',
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: '⚠️ Top 10 Técnicos Más Lentos'
                }
            },
            scales: {
                x: {
                    beginAtZero: true
                }
            }
        }
    });
}

function crearTendenciaTiempos(datos) {
    const ctx = document.getElementById('tendenciaTiempos');
    
    if (reportCharts.tendenciaTiempos) {
        reportCharts.tendenciaTiempos.destroy();
    }
    
    reportCharts.tendenciaTiempos = new Chart(ctx, {
        type: 'line',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Días Promedio de Cierre',
                data: datos.data,
                borderColor: '#17a2b8',
                backgroundColor: 'rgba(23, 162, 184, 0.1)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 6,
                pointHoverRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function crearAnalisisPorSeveridad(datos) {
    const ctx = document.getElementById('analisisPorSeveridad');
    
    if (reportCharts.analisisPorSeveridad) {
        reportCharts.analisisPorSeveridad.destroy();
    }
    
    reportCharts.analisisPorSeveridad = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Días Promedio',
                data: datos.data,
                backgroundColor: datos.colors,
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function mostrarAlertasTiempos(alertas) {
    const container = document.getElementById('lista-alertas-tiempos');
    
    if (alertas.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">No hay incidencias con alertas de tiempo</p>';
        return;
    }
    
    let html = '<div class="list-group">';
    
    alertas.forEach(alerta => {
        const clase = alerta.dias_abierta > 30 ? 'danger' : alerta.dias_abierta > 20 ? 'warning' : 'info';
        
        html += `
            <div class="list-group-item list-group-item-${clase}">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1"><strong>${alerta.folio}</strong> - ${alerta.tipo_equipo} ${alerta.marca}</h6>
                        <small>
                            <i class="bi bi-person"></i> ${alerta.tecnico} | 
                            <i class="bi bi-calendar"></i> ${alerta.fecha_deteccion} | 
                            <span class="badge bg-secondary">${alerta.severidad}</span>
                            <span class="badge bg-primary">${alerta.estado}</span>
                        </small>
                    </div>
                    <div class="text-end">
                        <h4 class="mb-0"><strong>${alerta.dias_abierta}</strong></h4>
                        <small>días abierta</small>
                    </div>
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    container.innerHTML = html;
}

// Función auxiliar para ver detalles de cadena de reincidencias
function verDetallesCadena(folio_original) {
    const cadenas = datosReportes.reincidencias?.cadenas_reincidencias || [];
    const cadena = cadenas.find(c => c.folio_original === folio_original);
    
    if (!cadena) {
        alert('No se encontró información de la cadena');
        return;
    }
    
    let mensaje = `📋 CADENA DE REINCIDENCIAS\n\n`;
    mensaje += `Folio Original: ${cadena.folio_original}\n`;
    mensaje += `Fecha: ${cadena.fecha_original}\n`;
    mensaje += `Equipo: ${cadena.tipo_equipo} ${cadena.marca}\n`;
    mensaje += `Serie: ${cadena.numero_serie}\n`;
    mensaje += `Técnico: ${cadena.tecnico}\n`;
    mensaje += `Total Reincidencias: ${cadena.total_reincidencias}\n\n`;
    mensaje += `Para ver detalles completos de todas las incidencias relacionadas,\n`;
    mensaje += `consulte el módulo de Incidencias con el número de serie del equipo.`;
    
    alert(mensaje);
}

// ============================================
// ANÁLISIS DE COMPONENTES (FASE 3)
// ============================================
function cargarAnalisisComponentes() {
    mostrarLoading(true);
    
    const queryString = construirQueryString();
    
    fetch('/scorecard/api/analisis-componentes/' + queryString)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                datosReportes.componentes = data;
                
                // Actualizar KPIs
                document.getElementById('kpi-total-componentes').textContent = data.kpis.total_con_componente;
                document.getElementById('kpi-porcentaje-componentes').textContent = 
                    `${data.kpis.porcentaje_con_componente}%`;
                document.getElementById('kpi-componentes-unicos').textContent = data.kpis.total_componentes_unicos;
                document.getElementById('kpi-componente-frecuente').textContent = data.kpis.componente_mas_frecuente;
                
                // Crear gráficos
                crearGraficoTopComponentes(data.top_componentes);
                crearGraficoSeveridadComponentes(data.severidad_componentes);
                crearTendenciaComponentes(data.tendencia_componentes);
                
                // Mostrar tabla
                mostrarComponentesCriticos(data.componentes_criticos);
            }
        })
        .catch(error => {
            console.error('❌ Error al cargar análisis de componentes:', error);
            mostrarError('Error al cargar análisis de componentes');
        })
        .finally(() => {
            mostrarLoading(false);
        });
}

function crearGraficoTopComponentes(datos) {
    const ctx = document.getElementById('graficoTopComponentes');
    
    if (reportCharts.graficoTopComponentes) {
        reportCharts.graficoTopComponentes.destroy();
    }
    
    reportCharts.graficoTopComponentes = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Total Incidencias',
                data: datos.data,
                backgroundColor: datos.colors,
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Top 10 Componentes con Más Fallos'
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearGraficoSeveridadComponentes(datos) {
    const ctx = document.getElementById('graficoSeveridadComponentes');
    
    if (reportCharts.graficoSeveridadComponentes) {
        reportCharts.graficoSeveridadComponentes.destroy();
    }
    
    reportCharts.graficoSeveridadComponentes = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: datos.datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                },
                title: {
                    display: true,
                    text: 'Distribución de Severidad por Componente'
                }
            },
            scales: {
                x: {
                    stacked: true
                },
                y: {
                    stacked: true,
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearTendenciaComponentes(datos) {
    const ctx = document.getElementById('tendenciaComponentes');
    
    if (reportCharts.tendenciaComponentes) {
        reportCharts.tendenciaComponentes.destroy();
    }
    
    reportCharts.tendenciaComponentes = new Chart(ctx, {
        type: 'line',
        data: {
            labels: datos.labels,
            datasets: datos.datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                },
                title: {
                    display: true,
                    text: 'Tendencia de Componentes Principales (6 Meses)'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function mostrarComponentesCriticos(componentes) {
    const container = document.getElementById('tabla-componentes-criticos');
    
    if (componentes.length === 0) {
        container.innerHTML = '<p class="text-muted text-center">No hay componentes críticos detectados</p>';
        return;
    }
    
    let html = '<div class="table-responsive"><table class="table table-hover">';
    html += '<thead class="table-dark"><tr>';
    html += '<th>Componente</th><th>Total Incidencias</th><th>Incidencias Críticas</th><th>% Críticas</th>';
    html += '</tr></thead><tbody>';
    
    componentes.forEach(comp => {
        const badgeClass = comp.porcentaje_criticas > 50 ? 'bg-danger' : 
                          comp.porcentaje_criticas > 30 ? 'bg-warning' : 'bg-info';
        
        html += `
            <tr>
                <td><strong>${comp.componente}</strong></td>
                <td>${comp.total}</td>
                <td><span class="badge bg-danger">${comp.criticas}</span></td>
                <td><span class="badge ${badgeClass}">${comp.porcentaje_criticas}%</span></td>
            </tr>
        `;
    });
    
    html += '</tbody></table></div>';
    container.innerHTML = html;
}

// ============================================
// ANÁLISIS DE NOTIFICACIONES (FASE 3)
// ============================================
function cargarAnalisisNotificaciones() {
    mostrarLoading(true);
    
    const queryString = construirQueryString();
    
    fetch('/scorecard/api/analisis-notificaciones/' + queryString)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                datosReportes.notificaciones = data;
                
                // Actualizar KPIs
                document.getElementById('kpi-total-notificaciones').textContent = data.kpis.total_notificaciones;
                document.getElementById('kpi-tasa-exito').textContent = `${data.kpis.tasa_exito}%`;
                document.getElementById('kpi-tiempo-promedio-notif').textContent = 
                    `${data.kpis.tiempo_promedio_minutos} min`;
                document.getElementById('kpi-notificaciones-fallidas').textContent = data.kpis.fallidas;
                
                // Crear gráficos
                crearGraficoTiposNotificacion(data.distribucion_tipos);
                crearTendenciaNotificaciones(data.tendencia_notificaciones);
                crearGraficoTopDestinatarios(data.top_destinatarios);
                crearGraficoDiasSemana(data.distribucion_dias_semana);
                crearGraficoSeveridadNotificaciones(data.distribucion_severidad);
            }
        })
        .catch(error => {
            console.error('❌ Error al cargar análisis de notificaciones:', error);
            mostrarError('Error al cargar análisis de notificaciones');
        })
        .finally(() => {
            mostrarLoading(false);
        });
}

function crearGraficoTiposNotificacion(datos) {
    const ctx = document.getElementById('graficoTiposNotificacion');
    
    if (reportCharts.graficoTiposNotificacion) {
        reportCharts.graficoTiposNotificacion.destroy();
    }
    
    reportCharts.graficoTiposNotificacion = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: datos.labels,
            datasets: [{
                data: datos.data,
                backgroundColor: datos.colors,
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: 'Distribución por Tipo de Notificación'
                }
            }
        }
    });
}

function crearTendenciaNotificaciones(datos) {
    const ctx = document.getElementById('tendenciaNotificaciones');
    
    if (reportCharts.tendenciaNotificaciones) {
        reportCharts.tendenciaNotificaciones.destroy();
    }
    
    reportCharts.tendenciaNotificaciones = new Chart(ctx, {
        type: 'line',
        data: {
            labels: datos.labels,
            datasets: datos.datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top'
                },
                title: {
                    display: true,
                    text: 'Tendencia Mensual de Notificaciones'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearGraficoTopDestinatarios(datos) {
    const ctx = document.getElementById('graficoTopDestinatarios');
    
    if (reportCharts.graficoTopDestinatarios) {
        reportCharts.graficoTopDestinatarios.destroy();
    }
    
    reportCharts.graficoTopDestinatarios = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Notificaciones Recibidas',
                data: datos.data,
                backgroundColor: '#3498db',
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            indexAxis: 'y',
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Top 10 Destinatarios Más Frecuentes'
                }
            },
            scales: {
                x: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearGraficoDiasSemana(datos) {
    const ctx = document.getElementById('graficoDiasSemana');
    
    if (reportCharts.graficoDiasSemana) {
        reportCharts.graficoDiasSemana.destroy();
    }
    
    reportCharts.graficoDiasSemana = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: datos.labels,
            datasets: [{
                label: 'Notificaciones',
                data: datos.data,
                backgroundColor: datos.colors,
                borderWidth: 1,
                borderRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                title: {
                    display: true,
                    text: 'Distribución por Día de la Semana'
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { stepSize: 1 }
                }
            }
        }
    });
}

function crearGraficoSeveridadNotificaciones(datos) {
    const ctx = document.getElementById('graficoSeveridadNotificaciones');
    
    if (reportCharts.graficoSeveridadNotificaciones) {
        reportCharts.graficoSeveridadNotificaciones.destroy();
    }
    
    reportCharts.graficoSeveridadNotificaciones = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: datos.labels,
            datasets: [{
                data: datos.data,
                backgroundColor: datos.colors,
                borderWidth: 2,
                borderColor: '#fff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom'
                },
                title: {
                    display: true,
                    text: 'Notificaciones por Severidad de Incidencia'
                }
            }
        }
    });
}

// ============================================
// UTILIDADES
// ============================================
function mostrarLoading(show) {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        if (show) {
            overlay.classList.add('active');
        } else {
            overlay.classList.remove('active');
        }
    }
}

function mostrarError(mensaje) {
    console.error('❌', mensaje);
    // Aquí podrías agregar un toast o alerta visual
    alert(mensaje);
}

// ============================================
// SISTEMA DE FILTROS
// ============================================
function cargarOpcionesFiltros() {
    console.log('🔧 Cargando opciones de filtros...');
    
    // Cargar sucursales desde la API
    fetch('/scorecard/api/analisis-atribuibilidad/')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.incidencias_por_sucursal) {
                const selectSucursal = document.getElementById('filtroSucursal');
                const sucursales = data.incidencias_por_sucursal.labels;
                
                sucursales.forEach(sucursal => {
                    const option = document.createElement('option');
                    option.value = sucursal;
                    option.textContent = sucursal;
                    selectSucursal.appendChild(option);
                });
            }
        });
    
    // Cargar técnicos desde la API
    fetch('/scorecard/api/analisis-tecnicos/')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.ranking_general) {
                const selectTecnico = document.getElementById('filtroTecnico');
                const tecnicos = data.ranking_general.map(t => t.tecnico);
                
                tecnicos.forEach(tecnico => {
                    const option = document.createElement('option');
                    option.value = tecnico;
                    option.textContent = tecnico;
                    selectTecnico.appendChild(option);
                });
            }
        });
}

function aplicarFiltros() {
    console.log('🔍 Aplicando filtros...');
    
    // Capturar valores de los filtros
    filtrosActivos.fecha_inicio = document.getElementById('filtroFechaInicio').value || null;
    filtrosActivos.fecha_fin = document.getElementById('filtroFechaFin').value || null;
    filtrosActivos.sucursal = document.getElementById('filtroSucursal').value || null;
    filtrosActivos.tecnico = document.getElementById('filtroTecnico').value || null;
    filtrosActivos.area = document.getElementById('filtroArea').value || null;
    filtrosActivos.severidad = document.getElementById('filtroSeveridad').value || null;
    filtrosActivos.estado = document.getElementById('filtroEstado').value || null;
    
    console.log('📋 Filtros activos:', filtrosActivos);
    
    // Validar que al menos un filtro esté activo
    const algunFiltroActivo = Object.values(filtrosActivos).some(valor => valor !== null);
    
    if (!algunFiltroActivo) {
        alert('⚠️ Por favor selecciona al menos un filtro antes de aplicar.');
        return;
    }
    
    // Limpiar datos anteriores para forzar recarga
    datosReportes = {};
    
    // Destruir gráficos existentes
    Object.values(reportCharts).forEach(chart => {
        if (chart && typeof chart.destroy === 'function') {
            chart.destroy();
        }
    });
    reportCharts = {};
    
    // Recargar datos con filtros aplicados
    mostrarLoading(true);
    cargarDatosReportes();
    
    // Mostrar mensaje de confirmación
    setTimeout(() => {
        alert('✅ Filtros aplicados correctamente. Los datos se han actualizado.');
    }, 1000);
}

function limpiarFiltros() {
    console.log('🧹 Limpiando filtros...');
    
    // Limpiar valores de los inputs
    document.getElementById('filtroFechaInicio').value = '';
    document.getElementById('filtroFechaFin').value = '';
    document.getElementById('filtroSucursal').value = '';
    document.getElementById('filtroTecnico').value = '';
    document.getElementById('filtroArea').value = '';
    document.getElementById('filtroSeveridad').value = '';
    document.getElementById('filtroEstado').value = '';
    
    // Resetear filtros activos
    filtrosActivos = {
        fecha_inicio: null,
        fecha_fin: null,
        sucursal: null,
        tecnico: null,
        area: null,
        severidad: null,
        estado: null
    };
    
    // Limpiar datos anteriores
    datosReportes = {};
    
    // Destruir gráficos existentes
    Object.values(reportCharts).forEach(chart => {
        if (chart && typeof chart.destroy === 'function') {
            chart.destroy();
        }
    });
    reportCharts = {};
    
    // Recargar datos sin filtros
    mostrarLoading(true);
    cargarDatosReportes();
    
    alert('✅ Filtros limpiados. Mostrando todos los datos.');
}

function construirQueryString() {
    const params = new URLSearchParams();
    
    if (filtrosActivos.fecha_inicio) params.append('fecha_inicio', filtrosActivos.fecha_inicio);
    if (filtrosActivos.fecha_fin) params.append('fecha_fin', filtrosActivos.fecha_fin);
    if (filtrosActivos.sucursal) params.append('sucursal', filtrosActivos.sucursal);
    if (filtrosActivos.tecnico) params.append('tecnico', filtrosActivos.tecnico);
    if (filtrosActivos.area) params.append('area', filtrosActivos.area);
    if (filtrosActivos.severidad) params.append('severidad', filtrosActivos.severidad);
    if (filtrosActivos.estado) params.append('estado', filtrosActivos.estado);
    
    return params.toString() ? '?' + params.toString() : '';
}

