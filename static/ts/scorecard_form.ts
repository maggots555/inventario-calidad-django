/**
 * ============================================================================
 * SCORECARD FORM - AUTOCOMPLETADO INTELIGENTE DE ÓRDENES
 * ============================================================================
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo TypeScript maneja la búsqueda automática de órdenes de servicio
 * cuando el usuario escribe un número de serie en el formulario de incidencias.
 * 
 * ¿QUÉ HACE?
 * 1. Detecta cuando el usuario escribe en el campo "número de serie"
 * 2. Envía una petición al servidor para buscar si existe una orden con ese número
 * 3. Si encuentra la orden:
 *    - Muestra toda la información de la orden en un panel bonito
 *    - Autocompleta el campo "número de orden"
 *    - Guarda el ID de la orden en un campo oculto
 * 4. Si NO encuentra la orden:
 *    - Muestra un mensaje informativo
 *    - Permite continuar con el registro manual
 * 
 * LÓGICA DE BÚSQUEDA INTELIGENTE:
 * - Si numero_serie es "NO VISIBLE", "NO IDENTIFICADO", etc. → Busca por orden_cliente
 * - Si numero_serie es normal → Busca por numero_serie
 * - Soporta ambos métodos de búsqueda simultáneos
 * 
 * TECNOLOGÍAS:
 * - TypeScript: JavaScript con tipos para prevenir errores
 * - Fetch API: Para hacer peticiones HTTP al servidor
 * - Bootstrap: Para estilos visuales
 * - Async/Await: Para manejar operaciones asíncronas de forma limpia
 */

// ============================================================================
// INTERFACES: Definen la estructura de los datos
// ============================================================================

/**
 * Estructura de la respuesta del API cuando busca una orden
 */
interface ApiResponse {
    success: boolean;          // ¿La petición fue exitosa?
    encontrado: boolean;       // ¿Se encontró una orden?
    orden: OrdenData | null;   // Datos de la orden (si se encontró)
    mensaje?: string;          // Mensaje informativo
    error?: string;            // Mensaje de error (si hubo problema)
}

/**
 * Estructura de los datos de una orden de servicio
 */
interface OrdenData {
    // Identificadores
    id: number;
    numero_orden_interno: string;
    orden_cliente: string;
    
    // Información del equipo
    tipo_equipo: string;
    tipo_equipo_display: string;
    marca: string;
    modelo: string;
    numero_serie: string;
    gama: string;
    gama_display: string;
    
    // Información de la orden
    fecha_ingreso: string;
    fecha_ingreso_corta: string;
    estado: string;
    estado_display: string;
    dias_en_servicio: number;
    
    // Responsables
    tecnico_responsable: string;
    tecnico_id: number;
    responsable_seguimiento: string;
    responsable_id: number;
    
    // Ubicación
    sucursal: string;
    sucursal_id: number;
    
    // Información adicional
    falla_principal: string;
    equipo_enciende: boolean;
    es_mis: boolean;
    es_reingreso: boolean;
    es_candidato_rhitso: boolean;
}

// ============================================================================
// CLASE PRINCIPAL: ScorecardFormHandler
// ============================================================================

class ScorecardFormHandler {
    // Elementos del DOM (los campos del formulario)
    private numeroSerieInput: HTMLInputElement | null;
    private numeroOrdenInput: HTMLInputElement | null;
    private ordenServicioInput: HTMLInputElement | null;  // Campo oculto con ID de la orden
    private infoContainer: HTMLElement | null;
    
    // Estado de la búsqueda
    private ordenEncontrada: OrdenData | null = null;
    private busquedaEnProgreso: boolean = false;
    
    /**
     * Constructor: Se ejecuta al crear una instancia de la clase
     */
    constructor() {
        this.numeroSerieInput = document.getElementById('id_numero_serie') as HTMLInputElement;
        this.numeroOrdenInput = document.getElementById('id_numero_orden') as HTMLInputElement;
        this.ordenServicioInput = document.getElementById('id_orden_servicio') as HTMLInputElement;
        this.infoContainer = document.getElementById('orden-info-container');
        
        // Inicializar event listeners
        this.init();
    }
    
    /**
     * Inicializar los event listeners
     * 
     * EXPLICACIÓN:
     * Un event listener "escucha" eventos del navegador (click, teclazo, etc.)
     * Cuando ocurre el evento, ejecuta una función.
     */
    private init(): void {
        if (!this.numeroSerieInput) {
            console.warn('[ScorecardForm] Campo numero_serie no encontrado en el DOM');
            return;
        }
        
        // ============================================
        // BÚSQUEDA POR NÚMERO DE SERIE (Service Tag)
        // ============================================
        
        // Escuchar cuando el usuario SALE del campo (onblur)
        this.numeroSerieInput.addEventListener('blur', () => {
            this.buscarOrdenPorSerie();
        });
        
        // También buscar cuando presiona Enter
        this.numeroSerieInput.addEventListener('keypress', (event: KeyboardEvent) => {
            if (event.key === 'Enter') {
                event.preventDefault();  // Evitar que envíe el formulario
                this.buscarOrdenPorSerie();
            }
        });
        
        // ============================================
        // BÚSQUEDA POR NÚMERO DE ORDEN (Orden Cliente)
        // ============================================
        
        if (!this.numeroOrdenInput) {
            console.warn('[ScorecardForm] Campo numero_orden no encontrado en el DOM');
            return;
        }
        
        // Escuchar cuando el usuario SALE del campo (onblur)
        this.numeroOrdenInput.addEventListener('blur', () => {
            this.buscarOrdenPorNumeroCliente();
        });
        
        // También buscar cuando presiona Enter
        this.numeroOrdenInput.addEventListener('keypress', (event: KeyboardEvent) => {
            if (event.key === 'Enter') {
                event.preventDefault();  // Evitar que envíe el formulario
                this.buscarOrdenPorNumeroCliente();
            }
        });
        
        console.log('[ScorecardForm] Event listeners inicializados correctamente (búsqueda bidireccional)');
    }
    
    /**
     * Función que busca orden por NÚMERO DE SERIE (Service Tag)
     * 
     * IMPORTANTE: Si el service tag es inválido (NO VISIBLE, NO IDENTIFICADO, etc.),
     * NO se busca nada. El usuario debe usar el campo "Número de Orden Cliente".
     */
    private async buscarOrdenPorSerie(): Promise<void> {
        // Validar que hay algo escrito
        const numeroSerie = this.numeroSerieInput?.value.trim().toUpperCase();
        
        if (!numeroSerie) {
            this.limpiarInfo();
            return;
        }
        
        // ============================================================================
        // VALIDACIÓN CRÍTICA: ¿Es un service tag inválido?
        // ============================================================================
        const SERIES_INVALIDAS = [
            'NO VISIBLE',
            'NO IDENTIFICADO',
            'NO LEGIBLE',
            'SIN SERIE',
            'N/A',
            'NA',
            'NO APLICA',
            'DESCONOCIDO',
            'NO SE VE',
            'NO TIENE',
            'SIN DATOS'
        ];
        
        const esSerieInvalida = SERIES_INVALIDAS.some(invalida => numeroSerie.includes(invalida));
        
        if (esSerieInvalida) {
            // ⚠️ Service tag inválido → NO buscar
            console.log(`[ScorecardForm] ⚠️ Service tag inválido detectado: "${numeroSerie}"`);
            console.log('[ScorecardForm] → Use el campo "Número de Orden Cliente" para buscar');
            
            this.ordenEncontrada = null;
            this.limpiarAutocompletado();
            this.mostrarMensajeSerieInvalida();
            return;  // SALIR sin hacer búsqueda
        }
        
        // ============================================================================
        // Service tag válido → Proceder con búsqueda
        // ============================================================================
        
        // Evitar múltiples búsquedas simultáneas
        if (this.busquedaEnProgreso) {
            console.log('[ScorecardForm] Búsqueda ya en progreso, ignorando...');
            return;
        }
        
        this.busquedaEnProgreso = true;
        this.mostrarCargando('Buscando por número de serie...');
        
        try {
            // Construir URL del API con parámetros
            const url = `/servicio-tecnico/api/buscar-orden-por-serie/?numero_serie=${encodeURIComponent(numeroSerie)}`;
            
            console.log(`[ScorecardForm] ✓ Buscando orden con número de serie: ${numeroSerie}`);
            
            // Hacer petición al servidor
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('sigma_csrftoken') || this.getCookie('csrftoken') || ''
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data: ApiResponse = await response.json();
            console.log('[ScorecardForm] Respuesta del servidor (por serie):', data);
            
            if (data.success && data.encontrado && data.orden) {
                // ✅ ENCONTRADO
                this.ordenEncontrada = data.orden;
                this.autocompletarCampos(data.orden, 'serie');
                this.mostrarInfoOrden(data.orden);
            } else {
                // ℹ️ NO ENCONTRADO
                this.ordenEncontrada = null;
                this.limpiarAutocompletado();
                this.mostrarOrdenNoEncontrada(data.mensaje || 'No se encontró orden con ese número de serie');
            }
            
        } catch (error) {
            console.error('[ScorecardForm] Error al buscar orden por serie:', error);
            this.mostrarError();
        } finally {
            this.busquedaEnProgreso = false;
        }
    }
    
    /**
     * Función que busca orden por NÚMERO DE ORDEN CLIENTE
     */
    private async buscarOrdenPorNumeroCliente(): Promise<void> {
        // Validar que hay algo escrito
        const numeroOrden = this.numeroOrdenInput?.value.trim();
        
        if (!numeroOrden) {
            this.limpiarInfo();
            return;
        }
        
        // Evitar múltiples búsquedas simultáneas
        if (this.busquedaEnProgreso) {
            console.log('[ScorecardForm] Búsqueda ya en progreso, ignorando...');
            return;
        }
        
        this.busquedaEnProgreso = true;
        this.mostrarCargando('Buscando por número de orden cliente...');
        
        try {
            // Construir URL del API - buscar directamente por orden_cliente
            const url = `/servicio-tecnico/api/buscar-orden-por-serie/?orden_cliente=${encodeURIComponent(numeroOrden)}`;
            
            console.log(`[ScorecardForm] Buscando orden con número de orden cliente: ${numeroOrden}`);
            
            // Hacer petición al servidor
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCookie('sigma_csrftoken') || this.getCookie('csrftoken') || ''
                }
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data: ApiResponse = await response.json();
            console.log('[ScorecardForm] Respuesta del servidor (por orden cliente):', data);
            
            if (data.success && data.encontrado && data.orden) {
                // ✅ ENCONTRADO
                this.ordenEncontrada = data.orden;
                this.autocompletarCampos(data.orden, 'orden');
                this.mostrarInfoOrden(data.orden);
            } else {
                // ℹ️ NO ENCONTRADO
                this.ordenEncontrada = null;
                this.limpiarAutocompletado();
                this.mostrarOrdenNoEncontrada(data.mensaje || 'No se encontró orden con ese número de orden cliente');
            }
            
        } catch (error) {
            console.error('[ScorecardForm] Error al buscar orden por número cliente:', error);
            this.mostrarError();
        } finally {
            this.busquedaEnProgreso = false;
        }
    }
    
    /**
     * Autocompletar campos del formulario con datos de la orden encontrada
     * 
     * @param orden - Datos de la orden encontrada
     * @param origen - 'serie' si se buscó por número de serie, 'orden' si se buscó por orden cliente
     */
    private autocompletarCampos(orden: OrdenData, origen: 'serie' | 'orden'): void {
        // Autocompletar ambos campos según el origen de búsqueda
        if (origen === 'serie') {
            // Búsqueda por serie → autocompletar número de orden
            if (this.numeroOrdenInput) {
                this.numeroOrdenInput.value = orden.orden_cliente;
                this.numeroOrdenInput.readOnly = true;
                this.numeroOrdenInput.classList.add('bg-light');
            }
        } else if (origen === 'orden') {
            // Búsqueda por orden → autocompletar número de serie
            if (this.numeroSerieInput) {
                this.numeroSerieInput.value = orden.numero_serie;
                this.numeroSerieInput.readOnly = true;
                this.numeroSerieInput.classList.add('bg-light');
            }
        }
        
        // Guardar ID de la orden en campo oculto
        if (this.ordenServicioInput) {
            this.ordenServicioInput.value = orden.id.toString();
        }
        
        console.log(`[ScorecardForm] Campos autocompletados para orden ${orden.numero_orden_interno} (búsqueda por ${origen})`);
    }
    
    /**
     * Limpiar campos autocompletados
     */
    private limpiarAutocompletado(): void {
        // Limpiar número de orden
        if (this.numeroOrdenInput) {
            this.numeroOrdenInput.value = '';
            this.numeroOrdenInput.readOnly = false;
            this.numeroOrdenInput.classList.remove('bg-light');
            this.numeroOrdenInput.placeholder = 'Orden del Cliente';
        }
        
        // Limpiar número de serie
        if (this.numeroSerieInput) {
            this.numeroSerieInput.readOnly = false;
            this.numeroSerieInput.classList.remove('bg-light');
        }
        
        // Limpiar campo oculto
        if (this.ordenServicioInput) {
            this.ordenServicioInput.value = '';
        }
    }
    
    /**
     * Mostrar información detallada de la orden encontrada
     */
    private mostrarInfoOrden(orden: OrdenData): void {
        if (!this.infoContainer) return;
        
        // Determinar icono según el tipo de equipo
        const iconoEquipo = this.obtenerIconoEquipo(orden.tipo_equipo);
        
        // Determinar badge de estado
        const badgeEstado = this.obtenerBadgeEstado(orden.estado);
        
        // HTML con información detallada
        this.infoContainer.innerHTML = `
            <div class="alert alert-success alert-dismissible fade show" role="alert">
                <h6 class="alert-heading">
                    <i class="bi bi-check-circle-fill me-2"></i>
                    ✓ Equipo encontrado en sistema
                </h6>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                <hr>
                <div class="row g-2 small">
                    <div class="col-md-6">
                        <p class="mb-1"><strong><i class="bi bi-file-text me-1"></i> Orden Interna:</strong> <span class="badge bg-primary">${orden.numero_orden_interno}</span></p>
                        <p class="mb-1"><strong><i class="bi bi-hash me-1"></i> Orden Cliente:</strong> ${orden.orden_cliente}</p>
                        <p class="mb-1"><strong>${iconoEquipo} Equipo:</strong> ${orden.tipo_equipo_display} ${orden.marca} ${orden.modelo || ''}</p>
                        <p class="mb-1"><strong><i class="bi bi-award me-1"></i> Gama:</strong> <span class="badge bg-secondary">${orden.gama_display}</span></p>
                    </div>
                    <div class="col-md-6">
                        <p class="mb-1"><strong><i class="bi bi-person-badge me-1"></i> Técnico:</strong> ${orden.tecnico_responsable}</p>
                        <p class="mb-1"><strong><i class="bi bi-geo-alt me-1"></i> Sucursal:</strong> ${orden.sucursal}</p>
                        <p class="mb-1"><strong><i class="bi bi-clock-history me-1"></i> Estado:</strong> ${badgeEstado}</p>
                        <p class="mb-0"><small class="text-muted"><i class="bi bi-calendar-event me-1"></i> Ingreso: ${orden.fecha_ingreso_corta} (${orden.dias_en_servicio} días)</small></p>
                    </div>
                </div>
                ${orden.falla_principal ? `<div class="mt-2 p-2 bg-light rounded"><small><strong>Falla reportada:</strong> ${orden.falla_principal}</small></div>` : ''}
            </div>
        `;
    }
    
    /**
     * Mostrar mensaje cuando NO se encuentra la orden
     */
    private mostrarOrdenNoEncontrada(mensaje: string): void {
        if (!this.infoContainer) return;
        
        this.infoContainer.innerHTML = `
            <div class="alert alert-info alert-dismissible fade show" role="alert">
                <h6 class="alert-heading">
                    <i class="bi bi-info-circle-fill me-2"></i>
                    ℹ️ Orden del Cliente (Externa)
                </h6>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                <p class="mb-0">${mensaje}</p>
                <p class="mb-0 mt-2"><small class="text-muted">Puedes continuar ingresando la orden del cliente manualmente en el campo "Número de Orden Cliente".</small></p>
            </div>
        `;
    }
    
    /**
     * Mostrar mensaje cuando el service tag es inválido
     */
    private mostrarMensajeSerieInvalida(): void {
        if (!this.infoContainer) return;
        
        this.infoContainer.innerHTML = `
            <div class="alert alert-warning alert-dismissible fade show" role="alert">
                <h6 class="alert-heading">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    ⚠️ Service Tag No Identificable
                </h6>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                <p class="mb-0">El número de serie ingresado indica que el equipo no tiene un service tag legible.</p>
                <hr>
                <p class="mb-0">
                    <strong>👉 Use el campo "Número de Orden Cliente"</strong> para buscar la orden en el sistema.
                </p>
            </div>
        `;
    }
    
    /**
     * Mostrar indicador de carga mientras busca
     */
    private mostrarCargando(mensaje: string = 'Buscando orden en el sistema...'): void {
        if (!this.infoContainer) return;
        
        this.infoContainer.innerHTML = `
            <div class="alert alert-secondary" role="alert">
                <div class="d-flex align-items-center">
                    <div class="spinner-border spinner-border-sm me-2" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <span>${mensaje}</span>
                </div>
            </div>
        `;
    }
    
    /**
     * Mostrar mensaje de error
     */
    private mostrarError(): void {
        if (!this.infoContainer) return;
        
        this.infoContainer.innerHTML = `
            <div class="alert alert-warning alert-dismissible fade show" role="alert">
                <h6 class="alert-heading">
                    <i class="bi bi-exclamation-triangle-fill me-2"></i>
                    ⚠️ Error al buscar
                </h6>
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                <p class="mb-0">Ocurrió un error al buscar la orden en el sistema. Por favor, intenta de nuevo.</p>
            </div>
        `;
    }
    
    /**
     * Limpiar contenedor de información
     */
    private limpiarInfo(): void {
        if (this.infoContainer) {
            this.infoContainer.innerHTML = '';
        }
        this.ordenEncontrada = null;
    }
    
    /**
     * Obtener cookie (para CSRF token)
     * 
     * EXPLICACIÓN:
     * Django requiere un token CSRF para prevenir ataques.
     * Esta función extrae ese token de las cookies del navegador.
     */
    private getCookie(name: string): string | null {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) {
            return parts.pop()?.split(';').shift() || null;
        }
        return null;
    }
    
    /**
     * Obtener icono según tipo de equipo
     */
    private obtenerIconoEquipo(tipo: string): string {
        const iconos: { [key: string]: string } = {
            'pc': '<i class="bi bi-pc-display-horizontal"></i>',
            'laptop': '<i class="bi bi-laptop"></i>',
            'aio': '<i class="bi bi-display"></i>'
        };
        return iconos[tipo] || '<i class="bi bi-pc"></i>';
    }
    
    /**
     * Obtener badge HTML según estado de la orden
     */
    private obtenerBadgeEstado(estado: string): string {
        // Mapeo de estados a colores de Bootstrap
        const colores: { [key: string]: string } = {
            'espera': 'secondary',
            'recepcion': 'info',
            'diagnostico': 'primary',
            'cotizacion': 'warning',
            'esperando_piezas': 'warning',
            'en_reparacion': 'primary',
            'control_calidad': 'info',
            'finalizado': 'success',
            'entregado': 'success',
            'cancelado': 'danger'
        };
        
        const color = colores[estado] || 'secondary';
        
        // Obtener nombre legible del estado
        const nombreEstado = this.obtenerNombreEstado(estado);
        
        return `<span class="badge bg-${color}">${nombreEstado}</span>`;
    }
    
    /**
     * Obtener nombre legible del estado
     */
    private obtenerNombreEstado(estado: string): string {
        const nombres: { [key: string]: string } = {
            'espera': 'En Espera',
            'recepcion': 'En Recepción',
            'diagnostico': 'En Diagnóstico',
            'cotizacion': 'Cotización Pendiente',
            'esperando_piezas': 'Esperando Piezas',
            'en_reparacion': 'En Reparación',
            'control_calidad': 'Control de Calidad',
            'finalizado': 'Finalizado',
            'entregado': 'Entregado',
            'cancelado': 'Cancelado'
        };
        
        return nombres[estado] || estado;
    }
}

// ============================================================================
// INICIALIZACIÓN AUTOMÁTICA
// ============================================================================

/**
 * Inicializar cuando el DOM esté listo
 * 
 * EXPLICACIÓN:
 * DOMContentLoaded se dispara cuando el HTML está completamente cargado.
 * Es el momento perfecto para inicializar nuestro código JavaScript.
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('[ScorecardForm] Inicializando ScorecardFormHandler...');
    new ScorecardFormHandler();
    console.log('[ScorecardForm] ScorecardFormHandler inicializado correctamente');
});
