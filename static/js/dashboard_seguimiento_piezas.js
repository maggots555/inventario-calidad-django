"use strict";
/**
 * DASHBOARD DE SEGUIMIENTO DE PIEZAS - TYPESCRIPT
 *
 * Funcionalidades:
 * - Auto-hide para alertas
 * - Loading overlay durante filtrado/exportación
 * - Transiciones suaves entre tabs
 * - Validación de formulario de filtros
 * - Inicialización de gráficos Plotly
 */
// ============================================
// CLASE PARA LOADING OVERLAY
// ============================================
class LoadingOverlayManager {
    constructor() {
        this.overlay = document.getElementById('loading-overlay');
        if (!this.overlay) {
            console.warn('Loading overlay element not found');
        }
    }
    show() {
        if (this.overlay) {
            this.overlay.classList.add('active');
        }
    }
    hide() {
        if (this.overlay) {
            this.overlay.classList.remove('active');
        }
    }
}
// ============================================
// CLASE PARA MANEJO DE TABS
// ============================================
class TabNavigationManager {
    constructor() {
        this.tabs = document.querySelectorAll('.nav-tabs .nav-link');
        this.tabContents = document.querySelectorAll('.tab-pane');
    }
    init() {
        this.tabs.forEach((tab) => {
            tab.addEventListener('click', (event) => {
                event.preventDefault();
                const target = tab.getAttribute('data-bs-target');
                if (target) {
                    this.switchTab(target);
                }
            });
        });
    }
    switchTab(tabId) {
        // Remover clase active de todos los tabs
        this.tabs.forEach((tab) => {
            tab.classList.remove('active');
        });
        // Remover clase active y show de todos los contenidos
        this.tabContents.forEach((content) => {
            content.classList.remove('show', 'active');
        });
        // Activar el tab seleccionado
        const selectedTab = document.querySelector(`[data-bs-target="${tabId}"]`);
        if (selectedTab) {
            selectedTab.classList.add('active');
        }
        // Mostrar el contenido correspondiente
        const selectedContent = document.querySelector(tabId);
        if (selectedContent) {
            selectedContent.classList.add('show', 'active');
        }
        // Trigger Plotly resize en gráficos si es la pestaña de visualizaciones
        if (tabId === '#visualizaciones' && typeof Plotly !== 'undefined') {
            setTimeout(() => {
                const plotlyDivs = document.querySelectorAll('.plotly-graph-div');
                plotlyDivs.forEach((div) => {
                    // @ts-ignore - Plotly is loaded globally
                    Plotly.Plots.resize(div);
                });
            }, 100);
        }
    }
}
// ============================================
// CLASE PARA VALIDACIÓN DE FORMULARIO
// ============================================
class FilterFormValidator {
    constructor(formId = 'filtros-form') {
        this.form = document.getElementById(formId);
        this.fechaInicioInput = document.getElementById('fecha_inicio');
        this.fechaFinInput = document.getElementById('fecha_fin');
    }
    validateDateRange() {
        if (!this.fechaInicioInput || !this.fechaFinInput) {
            return true; // Si no existen los campos, permitir envío
        }
        const fechaInicio = this.fechaInicioInput.value;
        const fechaFin = this.fechaFinInput.value;
        // Si ambos campos tienen valores, validar rango
        if (fechaInicio && fechaFin) {
            const inicio = new Date(fechaInicio);
            const fin = new Date(fechaFin);
            if (inicio > fin) {
                alert('La fecha de inicio no puede ser mayor que la fecha de fin.');
                return false;
            }
            // Validar que el rango no sea mayor a 1 año
            const diffTime = Math.abs(fin.getTime() - inicio.getTime());
            const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
            if (diffDays > 365) {
                const confirmar = confirm('El rango de fechas es mayor a 1 año. Esto puede tardar en cargar. ¿Desea continuar?');
                return confirmar;
            }
        }
        return true;
    }
    validateForm() {
        return this.validateDateRange();
    }
    setupValidation() {
        if (this.form) {
            this.form.addEventListener('submit', (event) => {
                if (!this.validateForm()) {
                    event.preventDefault();
                }
            });
        }
    }
}
// ============================================
// CLASE PARA AUTO-HIDE DE ALERTAS
// ============================================
class AlertManager {
    constructor(autoHideDelay = 5000) {
        this.alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        this.autoHideDelay = autoHideDelay;
    }
    init() {
        this.alerts.forEach((alert) => {
            // Agregar botón de cerrar si no existe
            if (!alert.querySelector('.btn-close')) {
                const closeButton = document.createElement('button');
                closeButton.type = 'button';
                closeButton.className = 'btn-close';
                closeButton.setAttribute('data-bs-dismiss', 'alert');
                closeButton.setAttribute('aria-label', 'Close');
                alert.appendChild(closeButton);
            }
            // Auto-hide después del delay
            setTimeout(() => {
                this.hideAlert(alert);
            }, this.autoHideDelay);
        });
    }
    hideAlert(alert) {
        alert.style.transition = 'opacity 0.5s ease';
        alert.style.opacity = '0';
        setTimeout(() => {
            alert.remove();
        }, 500);
    }
}
// ============================================
// CLASE PARA MANEJO DE EXPORTACIÓN
// ============================================
class ExportManager {
    constructor(loadingOverlay) {
        this.exportButton = document.getElementById('btn-exportar-excel');
        this.loadingOverlay = loadingOverlay;
    }
    init() {
        if (this.exportButton) {
            this.exportButton.addEventListener('click', (event) => {
                this.handleExport(event);
            });
        }
    }
    handleExport(event) {
        // Mostrar loading overlay
        this.loadingOverlay.show();
        // El formulario se enviará normalmente
        // El loading se ocultará cuando la página termine de cargar el archivo
        setTimeout(() => {
            this.loadingOverlay.hide();
        }, 3000); // 3 segundos de timeout por si falla la descarga
    }
}
// ============================================
// CLASE PARA TOOLTIPS (BOOTSTRAP)
// ============================================
class TooltipManager {
    constructor() {
        this.tooltipTriggerList = Array.from(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    }
    init() {
        if (typeof bootstrap !== 'undefined') {
            this.tooltipTriggerList.forEach((tooltipTriggerEl) => {
                // @ts-ignore - Bootstrap is loaded globally
                new bootstrap.Tooltip(tooltipTriggerEl);
            });
        }
    }
}
// ============================================
// CLASE PARA SMOOTH SCROLL
// ============================================
class SmoothScrollManager {
    init() {
        const links = document.querySelectorAll('a[href^="#"]');
        links.forEach((link) => {
            link.addEventListener('click', (event) => {
                const href = link.getAttribute('href');
                if (href && href !== '#' && href !== '#!') {
                    event.preventDefault();
                    const target = document.querySelector(href);
                    if (target) {
                        target.scrollIntoView({
                            behavior: 'smooth',
                            block: 'start'
                        });
                    }
                }
            });
        });
    }
}
// ============================================
// CLASE PARA VISTA AGRUPADA (NUEVO)
// ============================================
class VistaAgrupadaManager {
    /**
     * Maneja las funcionalidades interactivas de la vista agrupada:
     * - Expandir/colapsar proveedores adicionales
     * - Expandir/colapsar detalles completos de seguimiento
     * - Animaciones suaves
     */
    init() {
        this.setupToggleProveedores();
        this.setupToggleDetalles();
        this.setupRowClickExpand();
    }
    /**
     * Configura botones para expandir/colapsar proveedores adicionales
     */
    setupToggleProveedores() {
        const toggleButtons = document.querySelectorAll('.toggle-proveedores');
        toggleButtons.forEach((button) => {
            button.addEventListener('click', (event) => {
                event.stopPropagation(); // Evitar que dispare el click de la fila
                const ordenId = button.getAttribute('data-orden-id');
                if (ordenId) {
                    this.toggleProveedores(ordenId, button);
                }
            });
        });
    }
    /**
     * Expande o colapsa la lista de proveedores adicionales
     */
    toggleProveedores(ordenId, button) {
        const proveedoresExtra = document.getElementById(`proveedores-${ordenId}`);
        const icon = button.querySelector('i');
        if (proveedoresExtra) {
            if (proveedoresExtra.classList.contains('d-none')) {
                // Expandir
                proveedoresExtra.classList.remove('d-none');
                proveedoresExtra.classList.add('expanded');
                if (icon) {
                    icon.classList.remove('bi-chevron-down');
                    icon.classList.add('bi-chevron-up');
                }
                button.innerHTML = button.innerHTML.replace('Ver', 'Ocultar');
            }
            else {
                // Colapsar
                proveedoresExtra.classList.add('d-none');
                proveedoresExtra.classList.remove('expanded');
                if (icon) {
                    icon.classList.remove('bi-chevron-up');
                    icon.classList.add('bi-chevron-down');
                }
                button.innerHTML = button.innerHTML.replace('Ocultar', 'Ver');
            }
        }
    }
    /**
     * Configura botones para expandir/colapsar detalles completos
     */
    setupToggleDetalles() {
        const toggleButtons = document.querySelectorAll('.toggle-detalles');
        toggleButtons.forEach((button) => {
            button.addEventListener('click', (event) => {
                event.stopPropagation(); // Evitar que dispare el click de la fila
                const ordenId = button.getAttribute('data-orden-id');
                if (ordenId) {
                    this.toggleDetalles(ordenId, button);
                }
            });
        });
    }
    /**
     * Expande o colapsa la fila de detalles completos
     */
    toggleDetalles(ordenId, button) {
        const detallesRow = document.getElementById(`detalles-${ordenId}`);
        const icon = button.querySelector('i');
        if (detallesRow) {
            if (detallesRow.classList.contains('d-none')) {
                // Expandir
                detallesRow.classList.remove('d-none');
                detallesRow.classList.add('show');
                button.classList.add('expanded');
                if (icon) {
                    icon.classList.remove('bi-chevron-down');
                    icon.classList.add('bi-chevron-up');
                }
                // Cambiar estilo del botón
                button.classList.remove('btn-outline-info');
                button.classList.add('btn-info');
                button.innerHTML = '<i class="bi bi-chevron-up"></i> Ocultar';
            }
            else {
                // Colapsar
                detallesRow.classList.add('d-none');
                detallesRow.classList.remove('show');
                button.classList.remove('expanded');
                if (icon) {
                    icon.classList.remove('bi-chevron-up');
                    icon.classList.add('bi-chevron-down');
                }
                // Restaurar estilo del botón
                button.classList.remove('btn-info');
                button.classList.add('btn-outline-info');
                button.innerHTML = '<i class="bi bi-chevron-down"></i> Detalles';
            }
        }
    }
    /**
     * Permite hacer clic en toda la fila para expandir detalles
     * (excepto en botones y enlaces)
     */
    setupRowClickExpand() {
        const ordenRows = document.querySelectorAll('.orden-row');
        ordenRows.forEach((row) => {
            row.addEventListener('click', (event) => {
                var _a;
                const target = event.target;
                // Verificar que no se hizo clic en un botón, enlace o input
                if (!target.closest('button') &&
                    !target.closest('a') &&
                    !target.closest('input') &&
                    !target.closest('select')) {
                    const ordenId = row.getAttribute('data-orden-id');
                    if (ordenId) {
                        const toggleButton = (_a = row.nextElementSibling) === null || _a === void 0 ? void 0 : _a.querySelector('.toggle-detalles');
                        if (toggleButton) {
                            // Simular click en el botón de detalles
                            const toggleButtonInRow = row.querySelector('.toggle-detalles');
                            if (toggleButtonInRow) {
                                toggleButtonInRow.click();
                            }
                        }
                    }
                }
            });
            // Agregar cursor pointer para indicar que la fila es clickeable
            row.style.cursor = 'pointer';
        });
    }
    /**
     * Expande automáticamente órdenes con prioridad crítica al cargar
     */
    autoExpandCriticas() {
        const ordenesRows = document.querySelectorAll('.orden-row');
        ordenesRows.forEach((row) => {
            var _a;
            // Buscar badge de prioridad crítica
            const badgeCritico = row.querySelector('.badge.bg-danger.badge-lg');
            if (badgeCritico && ((_a = badgeCritico.textContent) === null || _a === void 0 ? void 0 : _a.includes('CRÍTICO'))) {
                const ordenId = row.getAttribute('data-orden-id');
                if (ordenId) {
                    const toggleButton = row.querySelector('.toggle-detalles');
                    if (toggleButton) {
                        // Expandir automáticamente después de 500ms
                        setTimeout(() => {
                            this.toggleDetalles(ordenId, toggleButton);
                        }, 500);
                    }
                }
            }
        });
    }
}
// ============================================
// CLASE PRINCIPAL - DASHBOARD MANAGER
// ============================================
class DashboardSeguimientoPiezas {
    constructor() {
        this.loadingOverlay = new LoadingOverlayManager();
        this.tabManager = new TabNavigationManager();
        this.formValidator = new FilterFormValidator('form-filtros');
        this.alertManager = new AlertManager(5000); // 5 segundos
        this.exportManager = new ExportManager(this.loadingOverlay);
        this.tooltipManager = new TooltipManager();
        this.smoothScrollManager = new SmoothScrollManager();
        this.vistaAgrupadaManager = new VistaAgrupadaManager();
    }
    init() {
        console.log('Inicializando Dashboard de Seguimiento de Piezas...');
        // Inicializar componentes
        this.tabManager.init();
        this.alertManager.init();
        this.exportManager.init();
        this.tooltipManager.init();
        this.smoothScrollManager.init();
        // Inicializar vista agrupada (NUEVO)
        this.vistaAgrupadaManager.init();
        // Setup validación de formulario
        if (this.formValidator instanceof FilterFormValidator) {
            this.formValidator.setupValidation();
        }
        // Agregar fade-in a elementos principales
        this.addFadeInAnimations();
        // Mostrar loading overlay al enviar formulario de filtros
        this.setupFormSubmitLoading();
        // Auto-expandir órdenes críticas (NUEVO)
        setTimeout(() => {
            this.vistaAgrupadaManager.autoExpandCriticas();
        }, 1000);
        console.log('Dashboard inicializado correctamente.');
    }
    addFadeInAnimations() {
        const elements = document.querySelectorAll('.kpi-card, .card, .alert');
        elements.forEach((element, index) => {
            element.style.animationDelay = `${index * 0.1}s`;
            element.classList.add('fade-in');
        });
    }
    setupFormSubmitLoading() {
        const form = document.getElementById('filtros-form');
        if (form) {
            form.addEventListener('submit', () => {
                this.loadingOverlay.show();
            });
        }
    }
}
// ============================================
// INICIALIZACIÓN CUANDO EL DOM ESTÁ LISTO
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    const dashboard = new DashboardSeguimientoPiezas();
    dashboard.init();
});
// ============================================
// EXPORTAR PARA USO EXTERNO (OPCIONAL)
// ============================================
// Si necesitas acceder al dashboard desde la consola del navegador para debugging
window.dashboardSeguimientoPiezas = DashboardSeguimientoPiezas;
//# sourceMappingURL=dashboard_seguimiento_piezas.js.map