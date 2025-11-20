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
// DECLARACIONES GLOBALES
// ============================================

// Plotly y Bootstrap se cargan desde CDN
declare const Plotly: any;

// ============================================
// INTERFACES Y TIPOS
// ============================================

interface LoadingOverlay {
    show(): void;
    hide(): void;
}

interface TabManager {
    init(): void;
    switchTab(tabId: string): void;
}

interface FormValidator {
    validateDateRange(): boolean;
    validateForm(): boolean;
}

// ============================================
// CLASE PARA LOADING OVERLAY
// ============================================

class LoadingOverlayManager implements LoadingOverlay {
    private overlay: HTMLElement | null;

    constructor() {
        this.overlay = document.getElementById('loading-overlay');
        if (!this.overlay) {
            console.warn('Loading overlay element not found');
        }
    }

    public show(): void {
        if (this.overlay) {
            this.overlay.classList.add('active');
        }
    }

    public hide(): void {
        if (this.overlay) {
            this.overlay.classList.remove('active');
        }
    }
}

// ============================================
// CLASE PARA MANEJO DE TABS
// ============================================

class TabNavigationManager implements TabManager {
    private tabs: NodeListOf<HTMLElement>;
    private tabContents: NodeListOf<HTMLElement>;

    constructor() {
        this.tabs = document.querySelectorAll<HTMLElement>('.nav-tabs .nav-link');
        this.tabContents = document.querySelectorAll<HTMLElement>('.tab-pane');
    }

    public init(): void {
        this.tabs.forEach((tab: HTMLElement) => {
            tab.addEventListener('click', (event: MouseEvent) => {
                event.preventDefault();
                const target = tab.getAttribute('data-bs-target');
                if (target) {
                    this.switchTab(target);
                }
            });
        });
    }

    public switchTab(tabId: string): void {
        // Remover clase active de todos los tabs
        this.tabs.forEach((tab: HTMLElement) => {
            tab.classList.remove('active');
        });

        // Remover clase active y show de todos los contenidos
        this.tabContents.forEach((content: HTMLElement) => {
            content.classList.remove('show', 'active');
        });

        // Activar el tab seleccionado
        const selectedTab = document.querySelector<HTMLElement>(`[data-bs-target="${tabId}"]`);
        if (selectedTab) {
            selectedTab.classList.add('active');
        }

        // Mostrar el contenido correspondiente
        const selectedContent = document.querySelector<HTMLElement>(tabId);
        if (selectedContent) {
            selectedContent.classList.add('show', 'active');
        }

        // Trigger Plotly resize en gráficos si es la pestaña de visualizaciones
        if (tabId === '#visualizaciones' && typeof Plotly !== 'undefined') {
            setTimeout(() => {
                const plotlyDivs = document.querySelectorAll<HTMLElement>('.plotly-graph-div');
                plotlyDivs.forEach((div: HTMLElement) => {
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

class FilterFormValidator implements FormValidator {
    private form: HTMLFormElement | null;
    private fechaInicioInput: HTMLInputElement | null;
    private fechaFinInput: HTMLInputElement | null;

    constructor(formId: string = 'filtros-form') {
        this.form = document.getElementById(formId) as HTMLFormElement;
        this.fechaInicioInput = document.getElementById('fecha_inicio') as HTMLInputElement;
        this.fechaFinInput = document.getElementById('fecha_fin') as HTMLInputElement;
    }

    public validateDateRange(): boolean {
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

    public validateForm(): boolean {
        return this.validateDateRange();
    }

    public setupValidation(): void {
        if (this.form) {
            this.form.addEventListener('submit', (event: Event) => {
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
    private alerts: NodeListOf<HTMLElement>;
    private autoHideDelay: number;

    constructor(autoHideDelay: number = 5000) {
        this.alerts = document.querySelectorAll<HTMLElement>('.alert:not(.alert-permanent)');
        this.autoHideDelay = autoHideDelay;
    }

    public init(): void {
        this.alerts.forEach((alert: HTMLElement) => {
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

    private hideAlert(alert: HTMLElement): void {
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
    private exportButton: HTMLButtonElement | null;
    private loadingOverlay: LoadingOverlay;

    constructor(loadingOverlay: LoadingOverlay) {
        this.exportButton = document.getElementById('btn-exportar-excel') as HTMLButtonElement;
        this.loadingOverlay = loadingOverlay;
    }

    public init(): void {
        if (this.exportButton) {
            this.exportButton.addEventListener('click', (event: MouseEvent) => {
                this.handleExport(event);
            });
        }
    }

    private handleExport(event: MouseEvent): void {
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
    private tooltipTriggerList: Element[];

    constructor() {
        this.tooltipTriggerList = Array.from(
            document.querySelectorAll('[data-bs-toggle="tooltip"]')
        );
    }

    public init(): void {
        if (typeof bootstrap !== 'undefined') {
            this.tooltipTriggerList.forEach((tooltipTriggerEl: Element) => {
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
    public init(): void {
        const links = document.querySelectorAll<HTMLAnchorElement>('a[href^="#"]');

        links.forEach((link: HTMLAnchorElement) => {
            link.addEventListener('click', (event: MouseEvent) => {
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

    public init(): void {
        this.setupToggleProveedores();
        this.setupToggleDetalles();
        this.setupRowClickExpand();
    }

    /**
     * Configura botones para expandir/colapsar proveedores adicionales
     */
    private setupToggleProveedores(): void {
        const toggleButtons = document.querySelectorAll<HTMLButtonElement>('.toggle-proveedores');

        toggleButtons.forEach((button: HTMLButtonElement) => {
            button.addEventListener('click', (event: MouseEvent) => {
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
    private toggleProveedores(ordenId: string, button: HTMLButtonElement): void {
        const proveedoresExtra = document.getElementById(`proveedores-${ordenId}`);
        const icon = button.querySelector<HTMLElement>('i');

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
            } else {
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
    private setupToggleDetalles(): void {
        const toggleButtons = document.querySelectorAll<HTMLButtonElement>('.toggle-detalles');

        toggleButtons.forEach((button: HTMLButtonElement) => {
            button.addEventListener('click', (event: MouseEvent) => {
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
    private toggleDetalles(ordenId: string, button: HTMLButtonElement): void {
        const detallesRow = document.getElementById(`detalles-${ordenId}`);
        const icon = button.querySelector<HTMLElement>('i');

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
            } else {
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
    private setupRowClickExpand(): void {
        const ordenRows = document.querySelectorAll<HTMLTableRowElement>('.orden-row');

        ordenRows.forEach((row: HTMLTableRowElement) => {
            row.addEventListener('click', (event: MouseEvent) => {
                const target = event.target as HTMLElement;

                // Verificar que no se hizo clic en un botón, enlace o input
                if (
                    !target.closest('button') &&
                    !target.closest('a') &&
                    !target.closest('input') &&
                    !target.closest('select')
                ) {
                    const ordenId = row.getAttribute('data-orden-id');
                    if (ordenId) {
                        const toggleButton = row.nextElementSibling?.querySelector<HTMLButtonElement>('.toggle-detalles');
                        if (toggleButton) {
                            // Simular click en el botón de detalles
                            const toggleButtonInRow = row.querySelector<HTMLButtonElement>('.toggle-detalles');
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
    public autoExpandCriticas(): void {
        const ordenesRows = document.querySelectorAll<HTMLTableRowElement>('.orden-row');

        ordenesRows.forEach((row: HTMLTableRowElement) => {
            // Buscar badge de prioridad crítica
            const badgeCritico = row.querySelector<HTMLElement>('.badge.bg-danger.badge-lg');

            if (badgeCritico && badgeCritico.textContent?.includes('CRÍTICO')) {
                const ordenId = row.getAttribute('data-orden-id');
                if (ordenId) {
                    const toggleButton = row.querySelector<HTMLButtonElement>('.toggle-detalles');
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
    private loadingOverlay: LoadingOverlay;
    private tabManager: TabManager;
    private formValidator: FormValidator;
    private alertManager: AlertManager;
    private exportManager: ExportManager;
    private tooltipManager: TooltipManager;
    private smoothScrollManager: SmoothScrollManager;
    private vistaAgrupadaManager: VistaAgrupadaManager;

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

    public init(): void {
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

    private addFadeInAnimations(): void {
        const elements = document.querySelectorAll<HTMLElement>('.kpi-card, .card, .alert');
        elements.forEach((element: HTMLElement, index: number) => {
            element.style.animationDelay = `${index * 0.1}s`;
            element.classList.add('fade-in');
        });
    }

    private setupFormSubmitLoading(): void {
        const form = document.getElementById('filtros-form') as HTMLFormElement;
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
(window as any).dashboardSeguimientoPiezas = DashboardSeguimientoPiezas;
