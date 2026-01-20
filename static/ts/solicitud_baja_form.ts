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
 * 
 * ACTUALIZADO (Enero 2026): Agregada info de solicitudes pendientes
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
    costo_unitario?: number;
    fecha_registro?: string;
    tiene_solicitud_pendiente?: boolean;  // NUEVO
    solicitud_pendiente?: {  // NUEVO
        id: number;
        solicitante: string;
        fecha: string;
        tipo: string;
        cantidad?: number;
    };
    // Campos de ubicación/sucursal (Enero 2026)
    sucursal_actual?: {
        codigo: string;
        nombre: string;
    } | null;
}

/**
 * Interface para grupo de unidades
 * 
 * ACTUALIZADO (Enero 2026): Para mostrar unidades agrupadas con checkboxes
 */
interface GrupoUnidadData {
    marca: string;
    modelo: string;
    estado: string;
    estado_display: string;
    cantidad: number;
    unidades: UnidadData[];
}

/**
 * Interface para la respuesta del API de unidades
 * 
 * ACTUALIZADO (Enero 2026): Ahora incluye grupos además de lista plana
 */
interface UnidadesApiResponse {
    success: boolean;
    producto_id?: number;
    producto_nombre?: string;
    stock_actual?: number;
    stock_info?: string;
    unidades?: UnidadData[];
    grupos?: GrupoUnidadData[];  // NUEVO
    total_unidades?: number;
    total_grupos?: number;  // NUEVO
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
    private cantidadInput: HTMLInputElement | null;  // NUEVO
    private unidadSelect: HTMLSelectElement | null;
    private tecnicoSelect: HTMLSelectElement | null;
    private sucursalDestinoSelect: HTMLSelectElement | null;  // NUEVO
    private unidadContainer: HTMLElement | null;
    private tecnicoContainer: HTMLElement | null;
    private sucursalDestinoContainer: HTMLElement | null;  // NUEVO
    private stockInfo: HTMLElement | null;
    
    // Elementos del DOM - Unidades agrupadas (NUEVO)
    private unidadesAgrupadasContainer: HTMLElement | null;
    private gruposUnidadesContent: HTMLElement | null;
    private contadorSeleccionadas: HTMLElement | null;
    private cantidadSolicitadaDisplay: HTMLElement | null;
    private unidadesSeleccionadasInput: HTMLInputElement | null;
    
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
    
    // Estado de selección de unidades (NUEVO)
    private unidadesSeleccionadas: Set<number> = new Set();
    private cantidadSolicitada: number = 0;
    
    constructor(apiUnidadesUrl: string, apiTecnicosUrl: string, apiBuscarCrearOrdenUrl: string) {
        // Guardar URLs de los APIs
        this.apiUnidadesUrl = apiUnidadesUrl;
        this.apiTecnicosUrl = apiTecnicosUrl;
        this.apiBuscarCrearOrdenUrl = apiBuscarCrearOrdenUrl;
        
        // Obtener referencias a los elementos del DOM - Campos principales
        this.tipoSolicitudSelect = document.getElementById('id_tipo_solicitud') as HTMLSelectElement;
        this.productoSelect = document.getElementById('id_producto') as HTMLSelectElement;
        this.cantidadInput = document.getElementById('id_cantidad') as HTMLInputElement;
        this.unidadSelect = document.getElementById('id_unidad_inventario') as HTMLSelectElement;
        this.tecnicoSelect = document.getElementById('id_tecnico_asignado') as HTMLSelectElement;
        this.sucursalDestinoSelect = document.getElementById('id_sucursal_destino') as HTMLSelectElement;
        this.unidadContainer = document.getElementById('unidad-container');
        this.tecnicoContainer = document.getElementById('tecnico-container');
        this.sucursalDestinoContainer = document.getElementById('sucursal-destino-container');
        this.stockInfo = document.getElementById('stock-info');
        
        // Obtener referencias a elementos de unidades agrupadas (NUEVO)
        this.unidadesAgrupadasContainer = document.getElementById('unidades-agrupadas-container');
        this.gruposUnidadesContent = document.getElementById('grupos-unidades-content');
        this.contadorSeleccionadas = document.getElementById('contador-seleccionadas');
        this.cantidadSolicitadaDisplay = document.getElementById('cantidad-solicitada-display');
        this.unidadesSeleccionadasInput = document.getElementById('unidades_seleccionadas_ids') as HTMLInputElement;
        
        // Obtener referencias a los elementos del DOM - Campos de orden
        this.ordenClienteInput = document.getElementById('id_orden_cliente_input') as HTMLInputElement;
        this.ordenServicioHidden = document.getElementById('id_orden_servicio') as HTMLInputElement;
        this.sucursalOrdenSelect = document.getElementById('id_sucursal_orden') as HTMLSelectElement;
        this.ordenStatusDiv = document.getElementById('orden-status');
        this.sucursalContainer = document.getElementById('sucursal-container');
        
        // ========== DESHABILITAR OPCIÓN TRANSFERENCIA PARA NO-AGENTES (NUEVO) ==========
        // Si el campo tiene el atributo data-es-agente="false", deshabilitar la opción transferencia
        if (this.tipoSolicitudSelect) {
            const esAgente = this.tipoSolicitudSelect.getAttribute('data-es-agente');
            if (esAgente === 'false') {
                this.deshabilitarOpcionTransferencia();
            }
        }
        
        // Inicializar eventos
        this.initEventListeners();
        
        // Configuración inicial basada en valores actuales
        this.handleTipoSolicitudChange();
        if (this.productoSelect?.value) {
            this.handleProductoChange();
        }
    }
    
    /**
     * Deshabilita la opción de transferencia para empleados no-agentes
     * 
     * NUEVO (Enero 2026): Solo agentes de almacén pueden hacer transferencias
     */
    private deshabilitarOpcionTransferencia(): void {
        if (!this.tipoSolicitudSelect) {
            return;
        }
        
        // Buscar la opción "transferencia" y deshabilitarla
        const opciones = this.tipoSolicitudSelect.options;
        for (let i = 0; i < opciones.length; i++) {
            if (opciones[i].value === 'transferencia') {
                opciones[i].disabled = true;
                opciones[i].text = '🔒 Transferencia entre Sucursales (Solo Agentes de Almacén)';
                break;
            }
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
        
        // Evento: Cambio en cantidad (NUEVO)
        if (this.cantidadInput) {
            this.cantidadInput.addEventListener('input', () => {
                this.handleCantidadChange();
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
        
        // Interceptar el submit del formulario para validar y crear orden si es necesario
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
     * - Si tipo_solicitud === 'transferencia' → Mostrar campo sucursal destino
     * - Cualquier otro valor → Ocultar campos especiales
     */
    private handleTipoSolicitudChange(): void {
        if (!this.tipoSolicitudSelect) {
            return;
        }
        
        const tipoSolicitud = this.tipoSolicitudSelect.value;
        const ordenContainer = document.getElementById('orden-container');
        
        // ========== TÉCNICO Y ORDEN (servicio_tecnico, venta_mostrador) ==========
        if (this.tecnicoContainer && this.tecnicoSelect) {
            if (tipoSolicitud === 'servicio_tecnico' || tipoSolicitud === 'venta_mostrador') {
                this.tecnicoContainer.style.display = 'block';
                this.tecnicoSelect.setAttribute('required', 'required');
                const label = this.tecnicoContainer.querySelector('label');
                if (label && !label.textContent?.includes('*')) {
                    label.innerHTML = '<i class="bi bi-person-gear me-1"></i>Técnico de Laboratorio *';
                }
                
                if (ordenContainer) {
                    ordenContainer.style.display = 'block';
                }
            } else {
                this.tecnicoContainer.style.display = 'none';
                this.tecnicoSelect.value = '';
                this.tecnicoSelect.removeAttribute('required');
                
                if (ordenContainer) {
                    ordenContainer.style.display = 'none';
                }
                this.limpiarCamposOrden();
            }
        }
        
        // ========== SUCURSAL DESTINO (transferencia) ==========
        if (this.sucursalDestinoContainer && this.sucursalDestinoSelect) {
            if (tipoSolicitud === 'transferencia') {
                this.sucursalDestinoContainer.style.display = 'block';
                this.sucursalDestinoSelect.setAttribute('required', 'required');
                const label = this.sucursalDestinoContainer.querySelector('label');
                if (label && !label.textContent?.includes('*')) {
                    label.innerHTML = '<i class="bi bi-building me-1"></i>Sucursal Destino *';
                }
            } else {
                this.sucursalDestinoContainer.style.display = 'none';
                this.sucursalDestinoSelect.value = '';
                this.sucursalDestinoSelect.removeAttribute('required');
            }
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
     * 
     * ACTUALIZADO (Enero 2026): Valida selección de unidades obligatoria
     */
    private handleFormSubmit(e: Event, form: HTMLFormElement): void {
        // ========== VALIDACIÓN: Unidades seleccionadas (NUEVO) ==========
        const cantidad = this.cantidadSolicitada;
        const seleccionadas = this.unidadesSeleccionadas.size;
        
        if (cantidad > 0 && seleccionadas !== cantidad) {
            e.preventDefault();
            alert(`Debes seleccionar exactamente ${cantidad} unidad(es). Has seleccionado ${seleccionadas}.`);
            return;
        }
        
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
     * Maneja el cambio en la cantidad solicitada
     * 
     * NUEVO (Enero 2026): Actualiza el display y revalida selección
     */
    private handleCantidadChange(): void {
        const cantidad = parseInt(this.cantidadInput?.value || '0');
        this.cantidadSolicitada = cantidad;
        
        // Actualizar display
        if (this.cantidadSolicitadaDisplay) {
            this.cantidadSolicitadaDisplay.textContent = cantidad.toString();
        }
        
        // Si hay unidades agrupadas cargadas, actualizar validación
        if (this.unidadesAgrupadasContainer?.style.display !== 'none') {
            this.actualizarContadorSeleccionadas();
        }
    }
    
    /**
     * Actualiza el contador de unidades seleccionadas
     */
    private actualizarContadorSeleccionadas(): void {
        if (!this.contadorSeleccionadas) return;
        
        const seleccionadas = this.unidadesSeleccionadas.size;
        const requeridas = this.cantidadSolicitada;
        
        const badge = this.contadorSeleccionadas;
        badge.textContent = `${seleccionadas} / ${requeridas} seleccionadas`;
        
        // Cambiar color según estado
        badge.className = 'badge bg-light text-dark';
        if (seleccionadas === 0) {
            badge.className = 'badge bg-secondary';
        } else if (seleccionadas === requeridas) {
            badge.className = 'badge bg-success';
        } else if (seleccionadas > requeridas) {
            badge.className = 'badge bg-danger';
        } else {
            badge.className = 'badge bg-warning text-dark';
        }
    }
    
    /**
     * Maneja el click en un checkbox de unidad
     * 
     * ACTUALIZADO (Enero 2026): Valida solicitudes pendientes
     */
    private handleUnidadCheckboxChange(unidadId: number, checked: boolean): void {
        if (checked) {
            // Verificar si la unidad tiene solicitud pendiente
            const checkbox = document.querySelector(`input[data-unidad-id="${unidadId}"]`) as HTMLInputElement;
            const tieneSolicitud = checkbox?.getAttribute('data-tiene-solicitud') === 'true';
            
            if (tieneSolicitud) {
                const confirmar = confirm(
                    '⚠️ ADVERTENCIA: Esta unidad ya tiene una solicitud pendiente.\n\n' +
                    '¿Estás seguro de que quieres seleccionarla?\n\n' +
                    'Esto podría causar conflictos de inventario si ambas solicitudes se procesan.'
                );
                
                if (!confirmar) {
                    // Desmarcar el checkbox si el usuario cancela
                    checkbox.checked = false;
                    return;
                }
            }
            
            // Verificar límite
            if (this.unidadesSeleccionadas.size >= this.cantidadSolicitada) {
                alert(`Solo puedes seleccionar ${this.cantidadSolicitada} unidad(es)`);
                // Desmarcar el checkbox
                if (checkbox) checkbox.checked = false;
                return;
            }
            this.unidadesSeleccionadas.add(unidadId);
        } else {
            this.unidadesSeleccionadas.delete(unidadId);
        }
        
        // Actualizar contador
        this.actualizarContadorSeleccionadas();
        
        // Actualizar input hidden con los IDs
        this.actualizarUnidadesSeleccionadasInput();
    }
    
    /**
     * Actualiza el input hidden con los IDs de unidades seleccionadas
     */
    private actualizarUnidadesSeleccionadasInput(): void {
        if (!this.unidadesSeleccionadasInput) return;
        
        const idsArray = Array.from(this.unidadesSeleccionadas);
        this.unidadesSeleccionadasInput.value = idsArray.join(',');
    }
    
    /**
     * Renderiza los grupos de unidades con checkboxes
     */
    private renderizarGruposUnidades(grupos: GrupoUnidadData[]): void {
        if (!this.gruposUnidadesContent) return;
        
        if (!grupos || grupos.length === 0) {
            this.gruposUnidadesContent.innerHTML = `
                <div class="text-center text-muted py-4">
                    <i class="bi bi-inbox fs-1"></i>
                    <p class="mt-2">No hay unidades disponibles para este producto</p>
                </div>
            `;
            return;
        }
        
        // Construir HTML para grupos expandibles
        let html = '<div class="accordion" id="accordionUnidades">';
        
        grupos.forEach((grupo, index) => {
            const badgeEstado = this.getBadgeEstado(grupo.estado);
            
            html += `
                <div class="accordion-item">
                    <h2 class="accordion-header" id="heading${index}">
                        <button class="accordion-button collapsed" type="button" 
                                data-bs-toggle="collapse" data-bs-target="#collapse${index}" 
                                aria-expanded="false" aria-controls="collapse${index}">
                            <div class="d-flex align-items-center justify-content-between w-100 me-3">
                                <div>
                                    <strong>${grupo.marca}</strong> ${grupo.modelo}
                                    <span class="ms-2 ${badgeEstado}">${grupo.estado_display}</span>
                                </div>
                                <span class="badge bg-primary rounded-pill">${grupo.cantidad} unidades</span>
                            </div>
                        </button>
                    </h2>
                    <div id="collapse${index}" class="accordion-collapse collapse" 
                         aria-labelledby="heading${index}" data-bs-parent="#accordionUnidades">
                        <div class="accordion-body">
                            <div class="table-responsive">
                                <table class="table table-sm table-hover mb-0">
                                    <thead class="table-light">
                                        <tr>
                                            <th style="width: 40px;"></th>
                                            <th>Código Interno</th>
                                            <th>Ubicación (Sucursal)</th>
                                            <th>Origen</th>
                                            <th class="text-end">Costo</th>
                                            <th>Fecha Registro</th>
                                        </tr>
                                    </thead>
                                    <tbody>
            `;
            
            grupo.unidades.forEach(unidad => {
                // Verificar si tiene solicitud pendiente
                const tieneSolicitudPendiente = unidad.tiene_solicitud_pendiente || false;
                const solicitudPendiente = unidad.solicitud_pendiente;
                
                html += `
                    <tr ${tieneSolicitudPendiente ? 'class="table-warning"' : ''}>
                        <td>
                            <input type="checkbox" class="form-check-input unidad-checkbox" 
                                   data-unidad-id="${unidad.id}"
                                   data-tiene-solicitud="${tieneSolicitudPendiente}"
                                   id="unidad_${unidad.id}">
                        </td>
                        <td>
                            <label for="unidad_${unidad.id}" class="form-label mb-0">
                                ${unidad.codigo_interno || '—'}
                                ${tieneSolicitudPendiente ? `
                                    <span class="badge bg-warning text-dark ms-1" 
                                          data-bs-toggle="tooltip" 
                                          data-bs-html="true"
                                          data-bs-placement="top"
                                          title="⚠️ <strong>Solicitud Pendiente</strong><br>
                                                 ID: #${solicitudPendiente?.id}<br>
                                                 Solicitante: ${solicitudPendiente?.solicitante}<br>
                                                 Fecha: ${solicitudPendiente?.fecha}<br>
                                                 Tipo: ${solicitudPendiente?.tipo}<br>
                                                 Cantidad: ${solicitudPendiente?.cantidad}">
                                        ⚠️ Pendiente
                                    </span>
                                ` : ''}
                            </label>
                        </td>
                        <td>
                            ${unidad.sucursal_actual ? 
                                `<i class="bi bi-building text-primary me-1"></i><span class="fw-medium">${unidad.sucursal_actual.nombre}</span>` : 
                                `<i class="bi bi-house text-secondary me-1"></i><span class="text-muted">Almacén Central</span>`
                            }
                        </td>
                        <td><small>${unidad.origen_display || '—'}</small></td>
                        <td class="text-end">
                            ${unidad.costo_unitario ? '$' + unidad.costo_unitario.toFixed(2) : '—'}
                        </td>
                        <td><small>${unidad.fecha_registro || '—'}</small></td>
                    </tr>
                `;
            });
            
            html += `
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
        
        this.gruposUnidadesContent.innerHTML = html;
        
        // Inicializar tooltips de Bootstrap para mostrar detalles de solicitudes pendientes
        const tooltipTriggerList = this.gruposUnidadesContent.querySelectorAll('[data-bs-toggle="tooltip"]');
        tooltipTriggerList.forEach(tooltipTriggerEl => {
            new (window as any).bootstrap.Tooltip(tooltipTriggerEl);
        });
        
        // Agregar event listeners a los checkboxes
        const checkboxes = this.gruposUnidadesContent.querySelectorAll('.unidad-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const target = e.target as HTMLInputElement;
                const unidadId = parseInt(target.getAttribute('data-unidad-id') || '0');
                this.handleUnidadCheckboxChange(unidadId, target.checked);
            });
        });
    }
    
    /**
     * Obtiene la clase CSS para el badge de estado
     */
    private getBadgeEstado(estado: string): string {
        const badgeMap: {[key: string]: string} = {
            'nuevo': 'badge bg-success',
            'usado_bueno': 'badge bg-primary',
            'usado_regular': 'badge bg-warning text-dark',
            'reparado': 'badge bg-info',
            'defectuoso': 'badge bg-danger',
            'para_revision': 'badge bg-secondary',
        };
        return badgeMap[estado] || 'badge bg-secondary';
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
        
        // Limpiar selección anterior
        this.unidadesSeleccionadas.clear();
        this.actualizarUnidadesSeleccionadasInput();
        this.actualizarContadorSeleccionadas();
        
        // Mostrar estado de carga
        this.unidadSelect.innerHTML = '<option value="">-- Cargando unidades... --</option>';
        
        if (!productoId) {
            this.unidadSelect.innerHTML = '<option value="">-- Seleccione un producto primero --</option>';
            this.unidadContainer.style.display = 'none';
            if (this.unidadesAgrupadasContainer) {
                this.unidadesAgrupadasContainer.style.display = 'none';
            }
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
     * 
     * ACTUALIZADO (Enero 2026): Renderiza unidades agrupadas con checkboxes
     */
    private processUnidadesResponse(data: UnidadesApiResponse): void {
        if (!this.unidadSelect || !this.unidadContainer) {
            return;
        }
        
        // Mostrar info de stock
        if (this.stockInfo && data.stock_info) {
            this.stockInfo.innerHTML = `<span class="text-success"><i class="bi bi-box-seam me-1"></i>${data.stock_info}</span>`;
        }
        
        // Actualizar cantidad solicitada en el display
        this.handleCantidadChange();
        
        // Ocultar selector simple (deprecado)
        this.unidadContainer.style.display = 'none';
        
        // Mostrar contenedor de unidades agrupadas
        if (this.unidadesAgrupadasContainer && data.grupos && data.grupos.length > 0) {
            this.unidadesAgrupadasContainer.style.display = 'block';
            this.renderizarGruposUnidades(data.grupos);
        } else if (this.unidadesAgrupadasContainer) {
            this.unidadesAgrupadasContainer.style.display = 'block';
            if (this.gruposUnidadesContent) {
                this.gruposUnidadesContent.innerHTML = `
                    <div class="alert alert-warning">
                        <i class="bi bi-exclamation-triangle me-1"></i>
                        <strong>No hay unidades disponibles</strong>
                        <p class="mb-0 small">
                            Este producto no tiene unidades individuales disponibles.
                            Debes registrar unidades antes de poder crear una solicitud.
                        </p>
                    </div>
                `;
            }
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
