/**
 * Dashboard de Cotizaciones - Interactividad con TypeScript
 * 
 * Este archivo maneja la interactividad avanzada del dashboard:
 * - Auto-submit de filtros
 * - Botones de período rápido
 * - Tooltips personalizados
 * - Exportación de gráficos individuales
 * - Animaciones suaves
 * - Loading states
 * 
 * Autor: Sistema de Servicio Técnico
 * Fecha: Noviembre 2025
 */

// ============================================
// INTERFACES Y TIPOS
// ============================================

/**
 * Interface para los filtros del dashboard
 * Define todos los filtros disponibles y sus tipos
 */
interface FiltrosDashboard {
    fecha_inicio: string | null;
    fecha_fin: string | null;
    sucursal: string | null;
    tecnico: string | null;
    gama: string | null;
    periodo: string;
}

/**
 * Interface para opciones de período rápido
 * Permite seleccionar rangos de fechas predefinidos
 */
interface OpcionesPeriodo {
    label: string;
    dias: number;
}

/**
 * Interface para configuración de exportación de gráficos
 */
interface ConfiguracionExportacion {
    filename: string;
    format: 'png' | 'svg' | 'jpeg' | 'webp';
    width: number;
    height: number;
    scale: number;
}

// ============================================
// CLASE PRINCIPAL DEL DASHBOARD
// ============================================

/**
 * Clase principal que maneja toda la interactividad del dashboard
 * 
 * EXPLAIN TO USER: Esta clase es como el "cerebro" del dashboard.
 * Organiza todo el código JavaScript en un solo lugar y facilita
 * el mantenimiento. Cada método (función) tiene una responsabilidad específica.
 */
class DashboardCotizaciones {
    // Propiedades privadas (solo accesibles dentro de esta clase)
    private filtrosActivos: FiltrosDashboard;
    private formularioFiltros: HTMLFormElement | null;
    private loadingOverlay: HTMLElement | null;
    
    // Opciones de período rápido predefinidas
    private readonly periodos: OpcionesPeriodo[] = [
        { label: 'Últimos 7 días', dias: 7 },
        { label: 'Últimos 15 días', dias: 15 },
        { label: 'Últimos 30 días', dias: 30 },
        { label: 'Últimos 90 días', dias: 90 },
        { label: 'Último año', dias: 365 }
    ];
    
    /**
     * Constructor: Se ejecuta cuando se crea una instancia de la clase
     * Inicializa todas las propiedades y configura los event listeners
     */
    constructor() {
        console.log('🚀 Inicializando Dashboard de Cotizaciones...');
        
        // Obtener filtros actuales de la URL
        this.filtrosActivos = this.obtenerFiltrosActuales();
        
        // Obtener referencias a elementos del DOM
        this.formularioFiltros = document.getElementById('filtros-form') as HTMLFormElement;
        this.loadingOverlay = document.getElementById('loadingOverlay');
        
        // Inicializar todos los event listeners
        this.inicializarEventListeners();
        
        // Inicializar tooltips de Bootstrap
        this.inicializarTooltips();
        
        console.log('✅ Dashboard inicializado correctamente');
        console.log('📊 Filtros activos:', this.filtrosActivos);
    }
    
    // ============================================
    // MÉTODOS DE INICIALIZACIÓN
    // ============================================
    
    /**
     * Obtiene los filtros actuales de los parámetros GET de la URL
     * 
     * EXPLAIN: URLSearchParams es una API del navegador que permite
     * leer los parámetros de la URL (todo lo que viene después del "?").
     * Por ejemplo: ?fecha_inicio=2025-01-01&sucursal=3
     * 
     * @returns {FiltrosDashboard} Objeto con todos los filtros activos
     */
    private obtenerFiltrosActuales(): FiltrosDashboard {
        const params = new URLSearchParams(window.location.search);
        
        return {
            fecha_inicio: params.get('fecha_inicio'),
            fecha_fin: params.get('fecha_fin'),
            sucursal: params.get('sucursal'),
            tecnico: params.get('tecnico'),
            gama: params.get('gama'),
            periodo: params.get('periodo') || 'M' // Default: Mensual
        };
    }
    
    /**
     * Inicializa todos los event listeners del dashboard
     * Event listeners son funciones que se ejecutan cuando ocurre un evento
     * (click, change, submit, etc.)
     */
    private inicializarEventListeners(): void {
        // Loading overlay al enviar formulario
        this.configurarLoadingEnSubmit();
        
        // Auto-submit opcional al cambiar filtros
        this.configurarAutoSubmitFiltros();
        
        // Smooth scroll al cambiar de tab
        this.configurarSmoothScrollTabs();
        
        // Botones de período rápido (si existen en el DOM)
        this.configurarBotonesPeriodo();
        
        console.log('✅ Event listeners configurados');
    }
    
    /**
     * Inicializa los tooltips de Bootstrap
     * 
     * EXPLAIN: Bootstrap tiene tooltips (textos que aparecen al pasar
     * el mouse sobre un elemento), pero necesitan ser inicializados
     * manualmente con JavaScript.
     */
    private inicializarTooltips(): void {
        // Buscar todos los elementos con atributo data-bs-toggle="tooltip"
        const tooltipTriggerList = document.querySelectorAll<HTMLElement>('[data-bs-toggle="tooltip"]');
        
        // Inicializar cada tooltip usando Bootstrap
        tooltipTriggerList.forEach((tooltipTriggerEl: HTMLElement) => {
            // @ts-ignore - Bootstrap puede no tener tipos TypeScript
            new bootstrap.Tooltip(tooltipTriggerEl);
        });
        
        if (tooltipTriggerList.length > 0) {
            console.log(`✅ ${tooltipTriggerList.length} tooltips inicializados`);
        }
    }
    
    // ============================================
    // CONFIGURACIÓN DE EVENTOS
    // ============================================
    
    /**
     * Muestra el loading overlay cuando se envía el formulario
     * Proporciona feedback visual al usuario
     */
    private configurarLoadingEnSubmit(): void {
        if (!this.formularioFiltros) return;
        
        this.formularioFiltros.addEventListener('submit', (event: Event) => {
            // Mostrar loading overlay
            this.mostrarLoading();
            
            // El formulario se envía normalmente (no hacemos preventDefault)
            console.log('📤 Enviando formulario de filtros...');
        });
    }
    
    /**
     * Configura auto-submit del formulario al cambiar selects
     * 
     * EXPLAIN: Esta función hace que el formulario se envíe automáticamente
     * cuando el usuario cambia un select, sin necesidad de hacer click en
     * "Aplicar Filtros". Está comentado por defecto porque algunos usuarios
     * prefieren seleccionar varios filtros antes de aplicarlos.
     */
    private configurarAutoSubmitFiltros(): void {
        if (!this.formularioFiltros) return;
        
        // Obtener todos los selects y inputs de fecha
        const elementosFiltro = this.formularioFiltros.querySelectorAll<HTMLSelectElement | HTMLInputElement>(
            'select, input[type="date"]'
        );
        
        elementosFiltro.forEach((elemento: HTMLSelectElement | HTMLInputElement) => {
            elemento.addEventListener('change', () => {
                // ⚠️ Descomentar la siguiente línea para habilitar auto-submit
                // this.formularioFiltros?.submit();
                
                console.log(`🔄 Filtro cambiado: ${elemento.name} = ${elemento.value}`);
            });
        });
    }
    
    /**
     * Configura smooth scroll al cambiar de tab
     * Hace que la página se desplace suavemente al inicio al cambiar tab
     */
    private configurarSmoothScrollTabs(): void {
        const tabs = document.querySelectorAll<HTMLButtonElement>('[data-bs-toggle="tab"]');
        
        tabs.forEach((tab: HTMLButtonElement) => {
            tab.addEventListener('shown.bs.tab', (event: Event) => {
                // Scroll suave al inicio de la página
                window.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                });
                
                const target = (event.target as HTMLButtonElement).getAttribute('data-bs-target');
                console.log(`📑 Cambiado a tab: ${target}`);
            });
        });
    }
    
    /**
     * Configura botones de período rápido
     * Permite seleccionar rangos de fechas predefinidos con un click
     */
    private configurarBotonesPeriodo(): void {
        // Buscar contenedor de botones de período (si existe)
        const contenedorPeriodos = document.getElementById('botones-periodo-rapido');
        
        if (!contenedorPeriodos) {
            // Si no existe el contenedor, no hacer nada
            return;
        }
        
        // Crear botones para cada período predefinido
        this.periodos.forEach((periodo: OpcionesPeriodo) => {
            const boton = this.crearBotonPeriodo(periodo);
            contenedorPeriodos.appendChild(boton);
        });
        
        console.log(`✅ ${this.periodos.length} botones de período creados`);
    }
    
    /**
     * Crea un botón de período rápido
     * 
     * @param {OpcionesPeriodo} periodo - Configuración del período
     * @returns {HTMLButtonElement} Botón HTML configurado
     */
    private crearBotonPeriodo(periodo: OpcionesPeriodo): HTMLButtonElement {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.className = 'btn btn-outline-primary btn-sm me-2 mb-2';
        boton.textContent = periodo.label;
        
        boton.addEventListener('click', () => {
            this.aplicarPeriodoRapido(periodo.dias);
        });
        
        return boton;
    }
    
    /**
     * Aplica un período rápido calculando las fechas
     * 
     * EXPLAIN: Esta función calcula fecha_inicio y fecha_fin basándose
     * en el número de días hacia atrás desde hoy. Por ejemplo, si
     * el usuario selecciona "Últimos 30 días", calcula fecha_fin = hoy
     * y fecha_inicio = hace 30 días.
     * 
     * @param {number} dias - Número de días hacia atrás
     */
    private aplicarPeriodoRapido(dias: number): void {
        // Calcular fechas
        const fechaFin = new Date();
        const fechaInicio = new Date();
        fechaInicio.setDate(fechaFin.getDate() - dias);
        
        // Formatear fechas a formato ISO (YYYY-MM-DD)
        const fechaInicioStr = this.formatearFechaISO(fechaInicio);
        const fechaFinStr = this.formatearFechaISO(fechaFin);
        
        // Actualizar inputs del formulario
        const inputFechaInicio = document.getElementById('fecha_inicio') as HTMLInputElement;
        const inputFechaFin = document.getElementById('fecha_fin') as HTMLInputElement;
        
        if (inputFechaInicio && inputFechaFin) {
            inputFechaInicio.value = fechaInicioStr;
            inputFechaFin.value = fechaFinStr;
            
            // Enviar formulario automáticamente
            this.formularioFiltros?.submit();
            
            console.log(`📅 Período aplicado: ${fechaInicioStr} a ${fechaFinStr} (${dias} días)`);
        }
    }
    
    // ============================================
    // MÉTODOS DE UI/UX
    // ============================================
    
    /**
     * Muestra el loading overlay
     * Proporciona feedback visual mientras se cargan los datos
     */
    private mostrarLoading(): void {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.add('active');
        }
    }
    
    /**
     * Oculta el loading overlay
     */
    private ocultarLoading(): void {
        if (this.loadingOverlay) {
            this.loadingOverlay.classList.remove('active');
        }
    }
    
    /**
     * Muestra una notificación toast
     * 
     * EXPLAIN: Un toast es un mensaje pequeño que aparece temporalmente
     * en la pantalla (generalmente en la esquina) para notificar al usuario.
     * Bootstrap tiene un componente Toast que podemos usar.
     * 
     * @param {string} mensaje - Mensaje a mostrar
     * @param {string} tipo - Tipo de toast (success, danger, warning, info)
     */
    public mostrarToast(mensaje: string, tipo: 'success' | 'danger' | 'warning' | 'info' = 'info'): void {
        // Buscar contenedor de toasts (debe existir en el HTML)
        let contenedorToasts = document.getElementById('toast-container');
        
        // Si no existe, crear el contenedor
        if (!contenedorToasts) {
            contenedorToasts = document.createElement('div');
            contenedorToasts.id = 'toast-container';
            contenedorToasts.className = 'toast-container position-fixed top-0 end-0 p-3';
            contenedorToasts.style.zIndex = '11';
            document.body.appendChild(contenedorToasts);
        }
        
        // Crear el toast
        const toast = this.crearElementoToast(mensaje, tipo);
        contenedorToasts.appendChild(toast);
        
        // Inicializar y mostrar con Bootstrap
        // @ts-ignore
        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
        
        // Eliminar el toast del DOM después de que se oculte
        toast.addEventListener('hidden.bs.toast', () => {
            toast.remove();
        });
        
        console.log(`📢 Toast mostrado: ${mensaje}`);
    }
    
    /**
     * Crea el elemento HTML del toast
     * 
     * @param {string} mensaje - Mensaje del toast
     * @param {string} tipo - Tipo de toast
     * @returns {HTMLElement} Elemento del toast
     */
    private crearElementoToast(mensaje: string, tipo: string): HTMLElement {
        const toast = document.createElement('div');
        toast.className = `toast align-items-center text-white bg-${tipo} border-0`;
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');
        
        toast.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">
                    ${this.obtenerIconoTipo(tipo)} ${mensaje}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        `;
        
        return toast;
    }
    
    /**
     * Obtiene el icono correspondiente al tipo de toast
     * 
     * @param {string} tipo - Tipo de toast
     * @returns {string} HTML del icono
     */
    private obtenerIconoTipo(tipo: string): string {
        const iconos: { [key: string]: string } = {
            success: '<i class="bi bi-check-circle-fill"></i>',
            danger: '<i class="bi bi-x-circle-fill"></i>',
            warning: '<i class="bi bi-exclamation-triangle-fill"></i>',
            info: '<i class="bi bi-info-circle-fill"></i>'
        };
        
        return iconos[tipo] || iconos['info'];
    }
    
    // ============================================
    // MÉTODOS DE UTILIDAD
    // ============================================
    
    /**
     * Formatea una fecha al formato ISO (YYYY-MM-DD)
     * 
     * EXPLAIN: Los inputs de tipo "date" requieren fechas en formato
     * ISO (YYYY-MM-DD). Esta función convierte un objeto Date de JavaScript
     * a ese formato de texto.
     * 
     * @param {Date} fecha - Fecha a formatear
     * @returns {string} Fecha en formato YYYY-MM-DD
     */
    private formatearFechaISO(fecha: Date): string {
        const año = fecha.getFullYear();
        const mes = String(fecha.getMonth() + 1).padStart(2, '0'); // +1 porque los meses empiezan en 0
        const dia = String(fecha.getDate()).padStart(2, '0');
        
        return `${año}-${mes}-${dia}`;
    }
    
    /**
     * Formatea un número como moneda mexicana
     * 
     * @param {number} valor - Valor a formatear
     * @returns {string} Valor formateado como moneda
     */
    public formatearMoneda(valor: number): string {
        return new Intl.NumberFormat('es-MX', {
            style: 'currency',
            currency: 'MXN'
        }).format(valor);
    }
    
    /**
     * Formatea un número como porcentaje
     * 
     * @param {number} valor - Valor a formatear (0-100)
     * @param {number} decimales - Número de decimales
     * @returns {string} Valor formateado como porcentaje
     */
    public formatearPorcentaje(valor: number, decimales: number = 1): string {
        return `${valor.toFixed(decimales)}%`;
    }
    
    /**
     * Actualiza el valor de un KPI en el DOM
     * 
     * EXPLAIN: Esta función actualiza el valor de un KPI específico
     * sin recargar toda la página. Útil para actualizaciones en tiempo real.
     * 
     * @param {string} kpiId - ID del KPI a actualizar
     * @param {number | string} nuevoValor - Nuevo valor del KPI
     */
    public actualizarKPI(kpiId: string, nuevoValor: number | string): void {
        const elemento = document.querySelector(`.kpi-card[data-kpi="${kpiId}"] .kpi-value`);
        
        if (elemento) {
            // Agregar animación de actualización
            elemento.classList.add('updating');
            
            setTimeout(() => {
                if (typeof nuevoValor === 'number') {
                    elemento.textContent = nuevoValor.toLocaleString('es-MX');
                } else {
                    elemento.textContent = nuevoValor;
                }
                
                elemento.classList.remove('updating');
                elemento.classList.add('updated');
                
                setTimeout(() => {
                    elemento.classList.remove('updated');
                }, 1000);
            }, 300);
            
            console.log(`✅ KPI actualizado: ${kpiId} = ${nuevoValor}`);
        } else {
            console.warn(`⚠️ No se encontró el KPI: ${kpiId}`);
        }
    }
    
    /**
     * Exporta un gráfico de Plotly a imagen
     * 
     * EXPLAIN: Plotly tiene una función integrada para exportar gráficos
     * a imágenes. Esta función facilita la exportación con configuración
     * personalizada.
     * 
     * @param {string} idGrafico - ID del div del gráfico Plotly
     * @param {Partial<ConfiguracionExportacion>} config - Configuración de exportación
     */
    public async exportarGrafico(
        idGrafico: string, 
        config: Partial<ConfiguracionExportacion> = {}
    ): Promise<void> {
        // Configuración por defecto
        const configCompleta: ConfiguracionExportacion = {
            filename: config.filename || `grafico_${idGrafico}`,
            format: config.format || 'png',
            width: config.width || 1920,
            height: config.height || 1080,
            scale: config.scale || 2
        };
        
        // Buscar el gráfico en el DOM
        const elementoGrafico = document.getElementById(idGrafico);
        
        if (!elementoGrafico) {
            console.error(`❌ No se encontró el gráfico: ${idGrafico}`);
            this.mostrarToast('Error: Gráfico no encontrado', 'danger');
            return;
        }
        
        try {
            // Usar Plotly.downloadImage() para exportar
            // @ts-ignore - Plotly puede no tener tipos completos
            await Plotly.downloadImage(elementoGrafico, configCompleta);
            
            console.log(`✅ Gráfico exportado: ${configCompleta.filename}.${configCompleta.format}`);
            this.mostrarToast('Gráfico exportado correctamente', 'success');
        } catch (error) {
            console.error('❌ Error exportando gráfico:', error);
            this.mostrarToast('Error al exportar gráfico', 'danger');
        }
    }
    
    /**
     * Obtiene los filtros activos actuales
     * Útil para debugging o para enviar a una API
     * 
     * @returns {FiltrosDashboard} Filtros activos
     */
    public obtenerFiltros(): FiltrosDashboard {
        return { ...this.filtrosActivos };
    }
    
    /**
     * Limpia todos los filtros y recarga la página
     */
    public limpiarFiltros(): void {
        window.location.href = window.location.pathname;
    }
}

// ============================================
// INICIALIZACIÓN GLOBAL
// ============================================

/**
 * Variable global para acceder a la instancia del dashboard
 * desde la consola del navegador (útil para debugging)
 */
let dashboardCotizaciones: DashboardCotizaciones;

/**
 * Inicializar cuando el DOM esté completamente cargado
 * 
 * EXPLAIN: DOMContentLoaded es un evento que se dispara cuando el HTML
 * está completamente cargado y parseado. Es el momento seguro para
 * manipular el DOM.
 */
document.addEventListener('DOMContentLoaded', () => {
    // Crear instancia del dashboard
    dashboardCotizaciones = new DashboardCotizaciones();
    
    // Hacer disponible globalmente para debugging
    // @ts-ignore
    window.dashboardCotizaciones = dashboardCotizaciones;
    
    console.log('🎉 Dashboard de Cotizaciones completamente cargado');
    console.log('💡 Tip: Usa "dashboardCotizaciones" en la consola para debugging');
});

/**
 * NOTA: No se exporta la clase porque se carga directamente en el navegador
 * sin bundler. La instancia está disponible globalmente como window.dashboardCotizaciones
 * para debugging y acceso desde la consola del navegador.
 * 
 * Si en el futuro se usa un bundler (webpack, vite, etc.), descomentar:
 * export { DashboardCotizaciones, FiltrosDashboard, OpcionesPeriodo, ConfiguracionExportacion };
 */
