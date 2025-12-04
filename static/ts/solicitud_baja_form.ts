/* =============================================================================
   SOLICITUD BAJA FORM - TypeScript para el formulario de Solicitud de Baja
   
   EXPLICACIÓN PARA PRINCIPIANTES:
   --------------------------------
   Este archivo TypeScript maneja la lógica dinámica del formulario de solicitud
   de baja del almacén. Específicamente:
   
   1. Carga dinámica de unidades: Cuando seleccionas un producto, se cargan las
      unidades disponibles de ese producto vía AJAX.
   
   2. Mostrar/ocultar campo de técnico: Cuando seleccionas "Servicio Técnico"
      como tipo de solicitud, aparece el campo para seleccionar el técnico.
      Este campo es obligatorio solo para ese tipo de solicitud.
   
   3. Búsqueda/Creación de Orden de Servicio: Permite buscar órdenes por número
      de orden del cliente (OOW-xxx o FL-xxx). Si no existe, se puede crear
      automáticamente una nueva orden con estado "Proveniente de Almacén".
   
   FLUJO:
   - Usuario selecciona tipo de solicitud
   - Si es "servicio_tecnico" → Muestra selector de técnico (obligatorio)
   - Si es otro tipo → Oculta selector de técnico
   
   - Usuario selecciona producto
   - Se hace petición AJAX para obtener unidades disponibles
   - Se actualiza el dropdown de unidades
   
   - Usuario escribe número de orden del cliente
   - Se valida formato (debe empezar con OOW- o FL-)
   - Se busca en el servidor si existe
   - Si no existe → Se muestra opción de crear automáticamente
   - Al enviar el formulario → Se crea la orden si es necesario
   
   ACTUALIZADO: Diciembre 2025 - Agregada funcionalidad de búsqueda/creación
   de órdenes por orden_cliente
   ============================================================================= */

/**
 * Interface para los datos de unidad recibidos del API
 * 
 * EXPLICACIÓN: En TypeScript, las interfaces definen la "forma" de un objeto.
 * Esto nos ayuda a saber exactamente qué campos tendrá cada unidad.
 */
interface UnidadData {
    id: number;
    codigo_interno: string;
    numero_serie: string;
    marca: string;
    modelo: string;
    estado: string;
    estado_display: string;
    disponibilidad: string;
    origen: string;
    origen_display: string;
}

/**
 * Interface para la respuesta del API de unidades
 */
interface UnidadesApiResponse {
    success: boolean;
    producto_id?: number;
    producto_nombre?: string;
    stock_actual?: number;
    stock_info?: string;
    unidades?: UnidadData[];
    total_unidades?: number;
    error?: string;
}

/**
 * Interface para los datos de técnico recibidos del API
 */
interface TecnicoData {
    id: number;
    nombre: string;
    cargo: string;
    sucursal: string;
}

/**
 * Interface para la respuesta del API de técnicos
 */
interface TecnicosApiResponse {
    success: boolean;
    tecnicos?: TecnicoData[];
    total?: number;
    error?: string;
}

/**
 * Interface para la respuesta del API de búsqueda/creación de orden
 */
interface OrdenClienteApiResponse {
    success: boolean;
    found?: boolean;
    created?: boolean;
    orden_id?: number;
    orden_cliente?: string;
    numero_orden_interno?: string;
    estado?: string;
    estado_display?: string;
    sucursal?: string;
    mensaje?: string;
    error?: string;
    formato_invalido?: boolean;
}

/**
 * Clase principal que maneja el formulario de solicitud de baja
 * 
 * EXPLICACIÓN: Usamos una clase para organizar todo el código relacionado
 * con el formulario. Esto hace el código más limpio y fácil de mantener.
 */
class SolicitudBajaFormHandler {
    // Elementos del DOM - Campos principales
    private tipoSolicitudSelect: HTMLSelectElement | null;
    private productoSelect: HTMLSelectElement | null;
    private unidadSelect: HTMLSelectElement | null;
    private tecnicoSelect: HTMLSelectElement | null;
    private unidadContainer: HTMLElement | null;
    private tecnicoContainer: HTMLElement | null;
    private stockInfo: HTMLElement | null;
    
    // Elementos del DOM - Campos de orden de servicio
    private ordenClienteInput: HTMLInputElement | null;
    private ordenServicioHidden: HTMLInputElement | null;
    private sucursalOrdenSelect: HTMLSelectElement | null;
    private ordenStatusDiv: HTMLElement | null;
    private sucursalContainer: HTMLElement | null;
    
    // URLs de los APIs (se establecen desde el template)
    private apiUnidadesUrl: string;
    private apiTecnicosUrl: string;
    private apiBuscarCrearOrdenUrl: string;
    
    // Estado interno
    private ordenEncontrada: boolean = false;
    private ordenId: number | null = null;
    private debounceTimer: ReturnType<typeof setTimeout> | null = null;
    
    constructor(apiUnidadesUrl: string, apiTecnicosUrl: string, apiBuscarCrearOrdenUrl: string) {
        // Guardar URLs de los APIs
        this.apiUnidadesUrl = apiUnidadesUrl;
        this.apiTecnicosUrl = apiTecnicosUrl;
        this.apiBuscarCrearOrdenUrl = apiBuscarCrearOrdenUrl;
        
        // Obtener referencias a los elementos del DOM - Campos principales
        this.tipoSolicitudSelect = document.getElementById('id_tipo_solicitud') as HTMLSelectElement;
        this.productoSelect = document.getElementById('id_producto') as HTMLSelectElement;
        this.unidadSelect = document.getElementById('id_unidad_inventario') as HTMLSelectElement;
        this.tecnicoSelect = document.getElementById('id_tecnico_asignado') as HTMLSelectElement;
        this.unidadContainer = document.getElementById('unidad-container');
        this.tecnicoContainer = document.getElementById('tecnico-container');
        this.stockInfo = document.getElementById('stock-info');
        
        // Obtener referencias a los elementos del DOM - Campos de orden
        this.ordenClienteInput = document.getElementById('id_orden_cliente_input') as HTMLInputElement;
        this.ordenServicioHidden = document.getElementById('id_orden_servicio') as HTMLInputElement;
        this.sucursalOrdenSelect = document.getElementById('id_sucursal_orden') as HTMLSelectElement;
        this.ordenStatusDiv = document.getElementById('orden-status');
        this.sucursalContainer = document.getElementById('sucursal-container');
        
        // Inicializar eventos
        this.initEventListeners();
        
        // Configuración inicial basada en valores actuales
        this.handleTipoSolicitudChange();
        if (this.productoSelect?.value) {
            this.handleProductoChange();
        }
    }
    
    /**
     * Inicializa los event listeners para los campos del formulario
     */
    private initEventListeners(): void {
        // Evento: Cambio en tipo de solicitud
        if (this.tipoSolicitudSelect) {
            this.tipoSolicitudSelect.addEventListener('change', () => {
                this.handleTipoSolicitudChange();
            });
        }
        
        // Evento: Cambio en producto
        if (this.productoSelect) {
            this.productoSelect.addEventListener('change', () => {
                this.handleProductoChange();
            });
        }
        
        // Evento: Input en orden_cliente (con debounce para no hacer muchas peticiones)
        if (this.ordenClienteInput) {
            this.ordenClienteInput.addEventListener('input', () => {
                this.handleOrdenClienteInput();
            });
            
            // También buscar al perder el foco
            this.ordenClienteInput.addEventListener('blur', () => {
                this.buscarOrdenCliente();
            });
        }
        
        // Interceptar el submit del formulario para crear orden si es necesario
        // IMPORTANTE: Usar ID específico porque hay otros formularios en la página (ej: logout)
        const form = document.getElementById('solicitud-baja-form') as HTMLFormElement;
        
        if (form) {
            form.addEventListener('submit', (e: Event) => {
                this.handleFormSubmit(e, form);
            });
        } else {
            console.error('❌ No se encontró el formulario');
        }
    }
    
    /**
     * Maneja el cambio en el tipo de solicitud
     * 
     * LÓGICA:
     * - Si tipo_solicitud === 'servicio_tecnico' → Mostrar campo técnico y orden
     * - Cualquier otro valor → Ocultar campo técnico y limpiar selección
     */
    private handleTipoSolicitudChange(): void {
        if (!this.tipoSolicitudSelect || !this.tecnicoContainer || !this.tecnicoSelect) {
            return;
        }
        
        const tipoSolicitud = this.tipoSolicitudSelect.value;
        const ordenContainer = document.getElementById('orden-container');
        
        // Mostrar campos de técnico y orden para: servicio_tecnico Y venta_mostrador
        // Ambos tipos requieren crear una OrdenServicio vinculada
        if (tipoSolicitud === 'servicio_tecnico' || tipoSolicitud === 'venta_mostrador') {
            // Mostrar campo de técnico
            this.tecnicoContainer.style.display = 'block';
            // Agregar indicador visual de requerido
            this.tecnicoSelect.setAttribute('required', 'required');
            // Actualizar label para mostrar que es obligatorio
            const label = this.tecnicoContainer.querySelector('label');
            if (label && !label.textContent?.includes('*')) {
                label.innerHTML = '<i class="bi bi-person-gear me-1"></i>Técnico de Laboratorio *';
            }
            
            // Mostrar campo de orden
            if (ordenContainer) {
                ordenContainer.style.display = 'block';
            }
        } else {
            // Ocultar campo de técnico
            this.tecnicoContainer.style.display = 'none';
            // Limpiar selección
            this.tecnicoSelect.value = '';
            // Remover requerido
            this.tecnicoSelect.removeAttribute('required');
            
            // Ocultar campo de orden
            if (ordenContainer) {
                ordenContainer.style.display = 'none';
            }
            // Limpiar campos de orden
            this.limpiarCamposOrden();
        }
    }
    
    /**
     * Limpia los campos relacionados con la orden de servicio
     */
    private limpiarCamposOrden(): void {
        if (this.ordenClienteInput) {
            this.ordenClienteInput.value = '';
        }
        if (this.ordenServicioHidden) {
            this.ordenServicioHidden.value = '';
        }
        if (this.ordenStatusDiv) {
            this.ordenStatusDiv.innerHTML = '';
            this.ordenStatusDiv.className = '';
        }
        if (this.sucursalContainer) {
            this.sucursalContainer.style.display = 'none';
        }
        this.ordenEncontrada = false;
        this.ordenId = null;
    }
    
    /**
     * Maneja el input en el campo orden_cliente con debounce
     * 
     * EXPLICACIÓN: Debounce significa que esperamos un poco después de que
     * el usuario deje de escribir antes de hacer la búsqueda. Esto evita
     * hacer muchas peticiones al servidor mientras el usuario escribe.
     */
    private handleOrdenClienteInput(): void {
        // Cancelar timer anterior si existe
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        
        // Validar formato mientras escribe
        this.validarFormatoOrden();
        
        // Esperar 500ms después de que el usuario deje de escribir
        this.debounceTimer = setTimeout(() => {
            this.buscarOrdenCliente();
        }, 500);
    }
    
    /**
     * Valida el formato del número de orden mientras el usuario escribe
     */
    private validarFormatoOrden(): void {
        if (!this.ordenClienteInput || !this.ordenStatusDiv) {
            return;
        }
        
        const valor = this.ordenClienteInput.value.trim().toUpperCase();
        
        if (!valor) {
            this.ordenStatusDiv.innerHTML = '';
            this.ordenStatusDiv.className = '';
            if (this.sucursalContainer) {
                this.sucursalContainer.style.display = 'none';
            }
            return;
        }
        
        // Verificar formato OOW- o FL-
        if (!valor.startsWith('OOW-') && !valor.startsWith('FL-')) {
            this.ordenStatusDiv.innerHTML = `
                <span class="text-warning">
                    <i class="bi bi-exclamation-triangle me-1"></i>
                    El número debe empezar con "OOW-" o "FL-"
                </span>
            `;
            this.ordenStatusDiv.className = 'mt-2';
            return;
        }
        
        // Formato válido, mostrar indicador de búsqueda
        this.ordenStatusDiv.innerHTML = `
            <span class="text-muted">
                <i class="bi bi-search me-1"></i>
                Buscando orden...
            </span>
        `;
    }
    
    /**
     * Busca una orden de servicio por orden_cliente
     */
    private buscarOrdenCliente(): void {
        if (!this.ordenClienteInput || !this.ordenStatusDiv) {
            return;
        }
        
        const valor = this.ordenClienteInput.value.trim().toUpperCase();
        
        if (!valor) {
            this.limpiarCamposOrden();
            return;
        }
        
        // Verificar formato antes de buscar
        if (!valor.startsWith('OOW-') && !valor.startsWith('FL-')) {
            return;
        }
        
        // Hacer petición al API
        fetch(`${this.apiBuscarCrearOrdenUrl}?orden_cliente=${encodeURIComponent(valor)}`)
            .then(response => response.json())
            .then((data: OrdenClienteApiResponse) => {
                this.procesarRespuestaBusqueda(data);
            })
            .catch(error => {
                console.error('Error buscando orden:', error);
                this.ordenStatusDiv!.innerHTML = `
                    <span class="text-danger">
                        <i class="bi bi-x-circle me-1"></i>
                        Error al buscar la orden
                    </span>
                `;
            });
    }
    
    /**
     * Procesa la respuesta de búsqueda de orden
     */
    private procesarRespuestaBusqueda(data: OrdenClienteApiResponse): void {
        if (!this.ordenStatusDiv || !this.sucursalContainer) {
            return;
        }
        
        if (!data.success) {
            // Error en la búsqueda
            if (data.formato_invalido) {
                this.ordenStatusDiv.innerHTML = `
                    <span class="text-warning">
                        <i class="bi bi-exclamation-triangle me-1"></i>
                        ${data.error}
                    </span>
                `;
            } else {
                this.ordenStatusDiv.innerHTML = `
                    <span class="text-danger">
                        <i class="bi bi-x-circle me-1"></i>
                        ${data.error}
                    </span>
                `;
            }
            this.sucursalContainer.style.display = 'none';
            this.ordenEncontrada = false;
            this.ordenId = null;
            return;
        }
        
        if (data.found) {
            // ✅ Orden encontrada
            this.ordenStatusDiv.innerHTML = `
                <div class="alert alert-success py-2 mb-0">
                    <i class="bi bi-check-circle me-1"></i>
                    <strong>Orden encontrada:</strong> ${data.numero_orden_interno}
                    <br>
                    <small class="text-muted">
                        Estado: ${data.estado_display} | Sucursal: ${data.sucursal}
                    </small>
                </div>
            `;
            this.ordenEncontrada = true;
            this.ordenId = data.orden_id || null;
            
            // Guardar el ID en el campo oculto
            if (this.ordenServicioHidden && data.orden_id) {
                this.ordenServicioHidden.value = data.orden_id.toString();
            }
            
            // Ocultar selector de sucursal (no es necesario)
            this.sucursalContainer.style.display = 'none';
        } else {
            // ⚠️ Orden no encontrada - mostrar opción de crear
            this.ordenStatusDiv.innerHTML = `
                <div class="alert alert-info py-2 mb-0">
                    <i class="bi bi-info-circle me-1"></i>
                    <strong>Orden no encontrada</strong>
                    <br>
                    <small>
                        Se creará automáticamente con el número "${data.orden_cliente}" 
                        al enviar la solicitud.
                    </small>
                </div>
            `;
            this.ordenEncontrada = false;
            this.ordenId = null;
            
            // Limpiar campo oculto
            if (this.ordenServicioHidden) {
                this.ordenServicioHidden.value = '';
            }
            
            // Mostrar selector de sucursal (necesario para crear)
            this.sucursalContainer.style.display = 'block';
        }
    }
    
    /**
     * Maneja el envío del formulario
     * Si hay una orden por crear, la crea primero
     */
    private handleFormSubmit(e: Event, form: HTMLFormElement): void {
        const tipoSolicitud = this.tipoSolicitudSelect?.value;
        
        // Solo procesar si es servicio técnico o venta mostrador
        // Ambos tipos requieren crear una OrdenServicio vinculada
        if (tipoSolicitud !== 'servicio_tecnico' && tipoSolicitud !== 'venta_mostrador') {
            return; // Dejar que el formulario se envíe normalmente
        }
        
        // Si ya hay una orden encontrada/seleccionada, continuar normalmente
        if (this.ordenEncontrada && this.ordenId) {
            return;
        }
        
        // Verificar si hay un número de orden ingresado
        const ordenCliente = this.ordenClienteInput?.value.trim().toUpperCase();
        
        if (!ordenCliente) {
            return; // No hay orden, continuar normalmente
        }
        
        // A partir de aquí, hay una orden que crear - PREVENIR ENVÍO
        e.preventDefault();
        
        // Validar formato
        if (!ordenCliente.startsWith('OOW-') && !ordenCliente.startsWith('FL-')) {
            alert('El número de orden debe empezar con "OOW-" o "FL-"');
            return;
        }
        
        // Verificar que se haya seleccionado sucursal
        const sucursalId = this.sucursalOrdenSelect?.value;
        if (!sucursalId) {
            alert('Debe seleccionar una sucursal para crear la orden de servicio.');
            this.sucursalOrdenSelect?.focus();
            return;
        }
        
        // Verificar que se haya seleccionado técnico
        const tecnicoId = this.tecnicoSelect?.value;
        if (!tecnicoId) {
            alert('Debe seleccionar un técnico de laboratorio.');
            this.tecnicoSelect?.focus();
            return;
        }
        
        // Mostrar indicador de carga
        const submitBtn = document.querySelector('button[type="submit"]') as HTMLButtonElement;
        const originalText = submitBtn?.innerHTML || 'Enviar';
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.innerHTML = '<i class="bi bi-hourglass-split me-1"></i>Creando orden...';
        }
        
        // Crear la orden vía API y luego enviar el formulario
        this.crearOrdenYEnviar(ordenCliente, sucursalId, tecnicoId, form, submitBtn, originalText);
    }
    
    /**
     * Crea una orden de servicio y luego envía el formulario
     */
    private crearOrdenYEnviar(
        ordenCliente: string, 
        sucursalId: string, 
        tecnicoId: string,
        form: HTMLFormElement,
        submitBtn: HTMLButtonElement | null,
        originalText: string
    ): void {
        fetch(this.apiBuscarCrearOrdenUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.getCSRFToken(),
            },
            body: JSON.stringify({
                orden_cliente: ordenCliente,
                sucursal_id: sucursalId,
                tecnico_id: tecnicoId,
                tipo_solicitud: this.tipoSolicitudSelect?.value || 'servicio_tecnico',
            }),
        })
        .then(response => response.json())
        .then((data: OrdenClienteApiResponse) => {
            if (data.success && data.created && data.orden_id) {
                // ✅ Orden creada exitosamente
                // Guardar el ID en el campo oculto
                if (this.ordenServicioHidden) {
                    this.ordenServicioHidden.value = data.orden_id.toString();
                }
                
                // Ahora sí enviar el formulario
                form.submit();
            } else {
                // ❌ Error al crear
                console.error('Error en respuesta de API:', data);
                alert(data.error || 'Error al crear la orden de servicio');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }
            }
        })
        .catch(error => {
            console.error('Error creando orden:', error);
            alert('Error de conexión al crear la orden');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalText;
            }
        });
    }
    
    /**
     * Obtiene el token CSRF de las cookies
     */
    private getCSRFToken(): string {
        const name = 'csrftoken';
        let cookieValue = '';
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
    
    /**
     * Maneja el cambio en la selección de producto
     * Carga las unidades disponibles vía AJAX
     */
    private handleProductoChange(): void {
        if (!this.productoSelect || !this.unidadSelect || !this.unidadContainer) {
            return;
        }
        
        const productoId = this.productoSelect.value;
        
        // Mostrar estado de carga
        this.unidadSelect.innerHTML = '<option value="">-- Cargando unidades... --</option>';
        
        if (!productoId) {
            this.unidadSelect.innerHTML = '<option value="">-- Seleccione un producto primero --</option>';
            this.unidadContainer.style.display = 'none';
            if (this.stockInfo) {
                this.stockInfo.textContent = '';
            }
            return;
        }
        
        // Hacer petición AJAX para obtener unidades
        fetch(`${this.apiUnidadesUrl}?producto_id=${productoId}`)
            .then(response => response.json())
            .then((data: UnidadesApiResponse) => {
                this.processUnidadesResponse(data);
            })
            .catch(error => {
                console.error('Error cargando unidades:', error);
                this.unidadSelect!.innerHTML = '<option value="">-- Error al cargar unidades --</option>';
            });
    }
    
    /**
     * Procesa la respuesta del API de unidades
     */
    private processUnidadesResponse(data: UnidadesApiResponse): void {
        if (!this.unidadSelect || !this.unidadContainer) {
            return;
        }
        
        // Mostrar info de stock
        if (this.stockInfo && data.stock_info) {
            this.stockInfo.innerHTML = `<span class="text-success"><i class="bi bi-box-seam me-1"></i>${data.stock_info}</span>`;
        }
        
        // Limpiar y agregar opción por defecto
        this.unidadSelect.innerHTML = '<option value="">-- Cualquier unidad disponible --</option>';
        
        // Agregar unidades si existen
        if (data.unidades && data.unidades.length > 0) {
            data.unidades.forEach((unidad: UnidadData) => {
                const option = document.createElement('option');
                option.value = unidad.id.toString();
                
                // Formato: "Samsung 870 EVO - S/N: ABC123 (Nuevo)"
                let texto = '';
                if (unidad.marca) texto += unidad.marca;
                if (unidad.modelo) texto += ' ' + unidad.modelo;
                if (unidad.numero_serie) texto += ' - S/N: ' + unidad.numero_serie;
                texto += ' (' + unidad.estado_display + ')';
                
                option.textContent = texto.trim() || `Unidad #${unidad.id}`;
                this.unidadSelect!.appendChild(option);
            });
            this.unidadContainer.style.display = 'block';
        } else {
            this.unidadSelect.innerHTML = '<option value="">-- No hay unidades registradas --</option>';
            this.unidadContainer.style.display = 'block';
        }
    }
}

// Variable global para la instancia del handler
let solicitudBajaHandler: SolicitudBajaFormHandler | null = null;

/**
 * Función de inicialización que se llama desde el template
 * 
 * EXPLICACIÓN:
 * Esta función se exporta para que el template pueda llamarla con las URLs
 * de los APIs como parámetros. Esto permite que Django genere las URLs
 * correctamente usando {% url 'nombre_url' %}.
 * 
 * @param apiUnidadesUrl - URL del API para obtener unidades de un producto
 * @param apiTecnicosUrl - URL del API para obtener técnicos disponibles
 * @param apiBuscarCrearOrdenUrl - URL del API para buscar/crear órdenes por orden_cliente
 */
function initSolicitudBajaForm(
    apiUnidadesUrl: string, 
    apiTecnicosUrl: string,
    apiBuscarCrearOrdenUrl: string
): void {
    document.addEventListener('DOMContentLoaded', function() {
        solicitudBajaHandler = new SolicitudBajaFormHandler(
            apiUnidadesUrl, 
            apiTecnicosUrl,
            apiBuscarCrearOrdenUrl
        );
    });
}

// Exportar función al scope global para que el template pueda usarla
(window as typeof window & { initSolicitudBajaForm: typeof initSolicitudBajaForm }).initSolicitudBajaForm = initSolicitudBajaForm;
