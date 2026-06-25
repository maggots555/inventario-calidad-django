/* =============================================================================
   SOLICITUD BAJA FORM - TypeScript para el formulario de Nueva solicitud
   
   EXPLICACIÓN PARA PRINCIPIANTES:
   --------------------------------
   Este archivo TypeScript maneja la lógica dinámica del formulario de solicitud
   del almacén. Específicamente:
   
   1. Autocompletado de producto: Búsqueda AJAX por código o nombre con stock
      visible en tiempo real. El ID seleccionado se guarda en un campo oculto.
   
   2. Carga dinámica de unidades: Al elegir un producto, se cargan las unidades
      disponibles (agrupadas por marca/modelo) vía AJAX.
   
   3. Mostrar/ocultar campos según tipo de solicitud:
      - servicio_tecnico / venta_mostrador → técnico + vincular orden
      - transferencia → sucursal destino
   
   4. Autocompletado de orden de servicio (Junio 2026):
      - servicio_tecnico → solo busca órdenes OOW- (diagnóstico)
      - venta_mostrador → solo busca órdenes FL- (venta mostrador)
      - Typeahead parcial vía servicio_tecnico:api_buscar_ordenes_autocomplete
      - Coincidencia exacta / creación vía almacen:api_buscar_crear_orden
   
   FLUJO PRODUCTO:
   - Usuario escribe en el campo de búsqueda (mín. 2 caracteres)
   - Se muestran sugerencias con stock disponible
   - Al seleccionar → carga unidades y valida cantidad vs stock
   
   FLUJO ORDEN:
   - Usuario elige tipo de solicitud (define prefijo OOW o FL)
   - Escribe en el campo de orden → dropdown con órdenes activas filtradas
   - Al seleccionar del dropdown → vincula id_orden_servicio automáticamente
   - Si escribe número completo no listado → blur busca coincidencia exacta
   - Si no existe → al enviar se crea orden con estado "Proveniente de Almacén"
   
   ACTUALIZADO: Junio 2026 - Autocompletado de producto y orden con filtro OOW/FL
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

/** Producto retornado por api_buscar_productos */
interface ProductoBusqueda {
    id: number;
    codigo: string;
    nombre: string;
    stock: number;
    costo: number;
    tipo: string;
}

interface ProductoBusquedaResponse {
    productos: ProductoBusqueda[];
}

/** Resultado de api_buscar_ordenes_autocomplete (typeahead de órdenes ST) */
interface OrdenAutocompleteResultado {
    id: number;
    orden_cliente: string;
    numero_serie: string;
    numero_orden_interno: string;
    marca: string;
    modelo: string;
    estado: string;
}

interface OrdenAutocompleteResponse {
    resultados: OrdenAutocompleteResultado[];
}

/**
 * Clase principal que maneja el formulario de Nueva solicitud.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Centraliza autocompletado de producto y orden, carga de unidades,
 * visibilidad de campos según tipo_solicitud y creación automática de órdenes.
 */
class SolicitudBajaFormHandler {
    // Elementos del DOM - Campos principales
    private tipoSolicitudSelect: HTMLSelectElement | null;
    private productoHidden: HTMLInputElement | null;
    private productoTextInput: HTMLInputElement | null;
    private productoAutocompleteWrapper: HTMLElement | null;
    private cantidadInput: HTMLInputElement | null;
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
    private ordenInfo: HTMLElement | null;
    private ordenInfoTexto: HTMLElement | null;
    private ordenHelpText: HTMLElement | null;
    private ordenAutocompleteWrapper: HTMLElement | null;
    private ordenAutocompleteDropdown: HTMLElement | null;
    private sucursalContainer: HTMLElement | null;
    
    // URLs de los APIs (se establecen desde el template)
    private apiUnidadesUrl: string;
    private apiTecnicosUrl: string;
    private apiBuscarCrearOrdenUrl: string;
    private apiBuscarProductosUrl: string;
    private apiBuscarOrdenesUrl: string;
    
    // Estado interno
    private ordenEncontrada: boolean = false;
    private ordenId: number | null = null;
    private productoDebounceTimer: ReturnType<typeof setTimeout> | null = null;
    private productoAbortController: AbortController | null = null;
    private ordenDebounceTimer: ReturnType<typeof setTimeout> | null = null;
    private ordenAbortController: AbortController | null = null;
    private ordenAutocompleteResultados: OrdenAutocompleteResultado[] = [];
    private ordenIndiceActivo: number = -1;
    private ordenTextoSeleccionado: string = '';
    private prefijoOrdenRequerido: 'OOW' | 'FL' | null = null;
    private stockActual: number = 0;
    private productoTextoSeleccionado: string = '';
    
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
        this.productoHidden = document.getElementById('id_producto') as HTMLInputElement;
        this.productoAutocompleteWrapper = document.getElementById('producto-autocomplete-wrapper');
        this.productoTextInput = this.productoAutocompleteWrapper?.querySelector(
            '.producto-autocomplete-input'
        ) as HTMLInputElement | null;
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
        this.ordenInfo = document.getElementById('ordenInfo');
        this.ordenInfoTexto = document.getElementById('ordenInfoTexto');
        this.ordenHelpText = document.getElementById('orden-help-text');
        this.ordenAutocompleteWrapper = document.getElementById('orden-autocomplete-wrapper');
        this.ordenAutocompleteDropdown = this.ordenAutocompleteWrapper?.querySelector(
            '.orden-autocomplete-dropdown'
        ) as HTMLElement | null;
        this.sucursalContainer = document.getElementById('sucursal-container');
        
        const form = document.getElementById('solicitud-baja-form') as HTMLFormElement | null;
        this.apiBuscarProductosUrl = form?.dataset.apiBuscarProductos
            || this.productoAutocompleteWrapper?.dataset.apiUrl
            || '';
        this.apiBuscarOrdenesUrl = this.ordenAutocompleteWrapper?.dataset.apiUrl || '';
        
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
        this.initProductoAutocomplete();
        this.initOrdenAutocomplete();
        
        // Configuración inicial basada en valores actuales
        this.handleTipoSolicitudChange();
        if (this.productoHidden?.value) {
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
     * Inicializa el autocompletado AJAX del campo Producto.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Reemplaza el antiguo <select> gigante. El usuario escribe y el servidor
     * devuelve coincidencias con stock. El ID real va en #id_producto (oculto).
     */
    private initProductoAutocomplete(): void {
        const wrapper = this.productoAutocompleteWrapper;
        const hiddenInput = this.productoHidden;
        const textInput = this.productoTextInput;
        if (!wrapper || !hiddenInput || !textInput) return;

        const dropdown = wrapper.querySelector<HTMLElement>('.producto-autocomplete-dropdown');
        if (!dropdown) return;

        const minChars = 2;
        const debounceMs = 300;
        let resultados: ProductoBusqueda[] = [];
        let indiceActivo = -1;
        this.productoTextoSeleccionado = textInput.value;

        const cerrarDropdown = (): void => {
            dropdown.classList.remove('show');
            indiceActivo = -1;
        };

        const marcarInvalido = (invalido: boolean): void => {
            textInput.classList.toggle('is-invalid-selection', invalido);
        };

        const getStockMetaClass = (stock: number): string => {
            if (stock === 0) return 'text-danger';
            return 'text-muted';
        };

        const renderResultados = (items: ProductoBusqueda[]): void => {
            dropdown.innerHTML = '';
            resultados = items;
            indiceActivo = -1;

            if (items.length === 0) {
                const vacio = document.createElement('div');
                vacio.className = 'producto-autocomplete-empty';
                vacio.textContent = 'Sin coincidencias';
                dropdown.appendChild(vacio);
                dropdown.classList.add('show');
                return;
            }

            items.forEach((prod, idx) => {
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'producto-autocomplete-item';
                const stockClass = getStockMetaClass(prod.stock);
                btn.innerHTML = `
                    <div class="prod-codigo">${prod.codigo}</div>
                    <div class="prod-nombre">${prod.nombre}</div>
                    <div class="prod-meta ${stockClass}">Stock: ${prod.stock} · $${prod.costo.toFixed(2)}</div>
                `;
                btn.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    seleccionar(prod);
                });
                btn.dataset.index = String(idx);
                dropdown.appendChild(btn);
            });
            dropdown.classList.add('show');
        };

        const seleccionar = (prod: ProductoBusqueda): void => {
            hiddenInput.value = String(prod.id);
            textInput.value = `${prod.codigo} — ${prod.nombre}`;
            this.productoTextoSeleccionado = textInput.value;
            this.stockActual = prod.stock;
            marcarInvalido(false);
            cerrarDropdown();
            this.actualizarStockInfoDisplay();
            this.handleProductoChange();
        };

        const buscar = async (termino: string): Promise<void> => {
            if (!this.apiBuscarProductosUrl || termino.length < minChars) {
                cerrarDropdown();
                return;
            }

            if (this.productoAbortController) this.productoAbortController.abort();
            this.productoAbortController = new AbortController();

            try {
                const url = `${this.apiBuscarProductosUrl}?q=${encodeURIComponent(termino)}`;
                const resp = await fetch(url, {
                    signal: this.productoAbortController.signal,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const data: ProductoBusquedaResponse = await resp.json();
                renderResultados(data.productos || []);
            } catch (err) {
                if (err instanceof Error && err.name === 'AbortError') return;
                cerrarDropdown();
            }
        };

        textInput.addEventListener('input', () => {
            const valor = textInput.value.trim();
            if (valor !== this.productoTextoSeleccionado) {
                hiddenInput.value = '';
                this.stockActual = 0;
                marcarInvalido(false);
                if (this.stockInfo) this.stockInfo.innerHTML = '';
            }
            if (this.productoDebounceTimer) clearTimeout(this.productoDebounceTimer);
            this.productoDebounceTimer = setTimeout(() => { void buscar(valor); }, debounceMs);
        });

        textInput.addEventListener('focus', () => {
            const valor = textInput.value.trim();
            if (valor.length >= minChars && valor !== this.productoTextoSeleccionado) {
                void buscar(valor);
            }
        });

        textInput.addEventListener('keydown', (e: KeyboardEvent) => {
            if (!dropdown.classList.contains('show')) return;
            const items = dropdown.querySelectorAll<HTMLButtonElement>('.producto-autocomplete-item');
            if (items.length === 0) return;

            if (e.key === 'ArrowDown') {
                e.preventDefault();
                indiceActivo = Math.min(indiceActivo + 1, items.length - 1);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                indiceActivo = Math.max(indiceActivo - 1, 0);
            } else if (e.key === 'Enter' && indiceActivo >= 0) {
                e.preventDefault();
                const prod = resultados[indiceActivo];
                if (prod) seleccionar(prod);
                return;
            } else if (e.key === 'Escape') {
                cerrarDropdown();
                return;
            } else {
                return;
            }

            items.forEach((item, i) => item.classList.toggle('active', i === indiceActivo));
            items[indiceActivo]?.scrollIntoView({ block: 'nearest' });
        });

        document.addEventListener('click', (e: Event) => {
            if (!wrapper.contains(e.target as Node)) cerrarDropdown();
        });
    }

    /**
     * Muestra el stock disponible y valida cantidad vs stock en el cliente.
     */
    private actualizarStockInfoDisplay(): void {
        if (!this.stockInfo) return;

        if (!this.productoHidden?.value) {
            this.stockInfo.innerHTML = '';
            return;
        }

        const cantidad = parseInt(this.cantidadInput?.value || '0', 10);
        let stockClass = 'text-success';
        if (this.stockActual === 0) {
            stockClass = 'text-danger';
        } else if (cantidad > this.stockActual) {
            stockClass = 'text-warning';
        }

        let mensaje = `<span class="${stockClass}"><i class="bi bi-box-seam me-1"></i>Stock disponible: ${this.stockActual} unidad(es)</span>`;
        if (cantidad > 0 && cantidad > this.stockActual) {
            mensaje += `<br><span class="text-danger small">La cantidad solicitada (${cantidad}) supera el stock disponible.</span>`;
        }
        this.stockInfo.innerHTML = mensaje;
    }

    /**
     * Obtiene el prefijo de orden requerido según el tipo de solicitud actual.
     *
     * Regla de negocio:
     * - servicio_tecnico  → OOW- (diagnóstico técnico)
     * - venta_mostrador   → FL-  (venta mostrador)
     */
    private getPrefijoRequerido(): 'OOW' | 'FL' | null {
        const tipo = this.tipoSolicitudSelect?.value;
        if (tipo === 'servicio_tecnico') return 'OOW';
        if (tipo === 'venta_mostrador') return 'FL';
        return null;
    }

    /**
     * Actualiza placeholder, texto de ayuda y data-prefijo del autocompletado de orden.
     *
     * Si el usuario cambia entre Servicio Técnico y Venta Mostrador, limpia el
     * campo porque cada tipo usa un prefijo distinto (OOW vs FL).
     */
    private actualizarConfigOrden(limpiarSiCambiaPrefijo: boolean = true): void {
        const nuevoPrefijo = this.getPrefijoRequerido();
        const prefijoAnterior = this.prefijoOrdenRequerido;

        if (limpiarSiCambiaPrefijo && prefijoAnterior !== null && nuevoPrefijo !== prefijoAnterior) {
            this.limpiarCamposOrden();
        }

        this.prefijoOrdenRequerido = nuevoPrefijo;

        if (this.ordenAutocompleteWrapper) {
            this.ordenAutocompleteWrapper.dataset.prefijo = nuevoPrefijo || '';
        }

        if (this.ordenClienteInput) {
            if (nuevoPrefijo === 'OOW') {
                this.ordenClienteInput.placeholder = 'Buscar orden OOW- (diagnóstico)...';
            } else if (nuevoPrefijo === 'FL') {
                this.ordenClienteInput.placeholder = 'Buscar orden FL- (venta mostrador)...';
            } else {
                this.ordenClienteInput.placeholder = 'Buscar orden...';
            }
        }

        if (this.ordenHelpText) {
            if (nuevoPrefijo === 'OOW') {
                this.ordenHelpText.innerHTML =
                    'Busca órdenes <strong>OOW-</strong> (diagnóstico). Si no existe, se creará al enviar.';
            } else if (nuevoPrefijo === 'FL') {
                this.ordenHelpText.innerHTML =
                    'Busca órdenes <strong>FL-</strong> (venta mostrador). Si no existe, se creará al enviar.';
            } else {
                this.ordenHelpText.textContent =
                    'Seleccione el tipo de solicitud para ver las órdenes disponibles.';
            }
        }
    }

    /**
     * Inicializa el autocompletado typeahead de órdenes de servicio.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * - Búsqueda parcial en órdenes activas (api_buscar_ordenes_autocomplete)
     * - Filtra por prefijo OOW o FL según tipo_solicitud
     * - Al elegir del dropdown: guarda orden_id en #id_orden_servicio
     * - Al salir del campo (blur): si no hubo selección, busca coincidencia exacta
     */
    private initOrdenAutocomplete(): void {
        if (!this.ordenClienteInput || !this.ordenAutocompleteDropdown || !this.ordenAutocompleteWrapper) {
            return;
        }

        const input = this.ordenClienteInput;
        const dropdown = this.ordenAutocompleteDropdown;
        const wrapper = this.ordenAutocompleteWrapper;
        const ordenContainer = document.getElementById('orden-container');
        const minChars = 2;
        const debounceMs = 300;
        this.ordenTextoSeleccionado = input.value.trim();

        const cerrarDropdown = (): void => {
            dropdown.classList.remove('show');
            ordenContainer?.classList.remove('orden-autocomplete-activo');
            this.ordenIndiceActivo = -1;
        };

        const abrirDropdown = (): void => {
            ordenContainer?.classList.add('orden-autocomplete-activo');
            dropdown.classList.add('show');
        };

        const escaparHtml = (texto: string): string => {
            const div = document.createElement('div');
            div.appendChild(document.createTextNode(texto));
            return div.innerHTML;
        };

        const resaltarCoincidencia = (texto: string, query: string): string => {
            const safe = escaparHtml(texto || '');
            if (!query) return safe;
            const q = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`(${q})`, 'gi');
            return safe.replace(regex, '<mark>$1</mark>');
        };

        const filtrarPorPrefijo = (items: OrdenAutocompleteResultado[]): OrdenAutocompleteResultado[] => {
            if (!this.prefijoOrdenRequerido) return items;
            const prefijo = `${this.prefijoOrdenRequerido}-`;
            return items.filter((r) => r.orden_cliente.toUpperCase().startsWith(prefijo));
        };

        const mostrarInfoSeleccion = (r: OrdenAutocompleteResultado): void => {
            if (!this.ordenInfo || !this.ordenInfoTexto) return;
            this.ordenInfo.classList.remove('d-none', 'alert-warning');
            this.ordenInfo.classList.add('alert-info');
            this.ordenInfoTexto.innerHTML = `
                <strong>${escaparHtml(r.orden_cliente)}</strong><br>
                Estado: ${escaparHtml(r.estado)}<br>
                Marca: ${escaparHtml(r.marca)}${r.modelo ? ` · ${escaparHtml(r.modelo)}` : ''}<br>
                Orden interna: ${escaparHtml(r.numero_orden_interno)} · Serie: ${escaparHtml(r.numero_serie)}
            `;
        };

        const seleccionar = (r: OrdenAutocompleteResultado): void => {
            input.value = r.orden_cliente;
            this.ordenTextoSeleccionado = r.orden_cliente;
            if (this.ordenServicioHidden) {
                this.ordenServicioHidden.value = String(r.id);
            }
            this.ordenEncontrada = true;
            this.ordenId = r.id;
            cerrarDropdown();
            if (this.ordenStatusDiv) {
                this.ordenStatusDiv.innerHTML = '';
            }
            if (this.sucursalContainer) {
                this.sucursalContainer.style.display = 'none';
            }
            mostrarInfoSeleccion(r);
        };

        const renderResultados = (query: string, items: OrdenAutocompleteResultado[]): void => {
            dropdown.innerHTML = '';
            this.ordenAutocompleteResultados = filtrarPorPrefijo(items);
            this.ordenIndiceActivo = -1;

            if (this.ordenAutocompleteResultados.length === 0) {
                dropdown.innerHTML = `
                    <div class="orden-autocomplete-empty">
                        <i class="bi bi-search"></i>
                        <span>Sin coincidencias para "<strong>${escaparHtml(query)}</strong>"</span>
                    </div>
                `;
                abrirDropdown();
                return;
            }

            const lista = document.createElement('ul');
            lista.className = 'orden-autocomplete-lista';
            lista.setAttribute('role', 'listbox');

            this.ordenAutocompleteResultados.forEach((r, idx) => {
                const li = document.createElement('li');
                li.className = 'orden-autocomplete-item';
                li.setAttribute('role', 'option');
                li.dataset.index = String(idx);
                li.innerHTML = `
                    <div class="orden-autocomplete-item-principal">
                        <span class="orden-autocomplete-orden">${resaltarCoincidencia(r.orden_cliente, query)}</span>
                        <span class="orden-autocomplete-marca badge bg-secondary">${escaparHtml(r.marca)}</span>
                    </div>
                    <div class="orden-autocomplete-item-secundario">
                        <span><i class="bi bi-upc-scan"></i> ${resaltarCoincidencia(r.numero_serie, query)}</span>
                        <span><i class="bi bi-hash"></i> ${resaltarCoincidencia(r.numero_orden_interno, query)}</span>
                        <span class="badge bg-light text-dark">${escaparHtml(r.estado)}</span>
                    </div>
                `;
                li.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    seleccionar(r);
                });
                li.addEventListener('mouseenter', () => {
                    this.ordenIndiceActivo = idx;
                    lista.querySelectorAll('.orden-autocomplete-item').forEach((item, i) => {
                        item.classList.toggle('active', i === idx);
                    });
                });
                lista.appendChild(li);
            });

            dropdown.appendChild(lista);
            abrirDropdown();
        };

        const buscar = async (query: string): Promise<void> => {
            if (!this.apiBuscarOrdenesUrl || query.length < minChars || !this.prefijoOrdenRequerido) {
                cerrarDropdown();
                return;
            }

            if (this.ordenAbortController) this.ordenAbortController.abort();
            this.ordenAbortController = new AbortController();

            dropdown.innerHTML = `
                <div class="orden-autocomplete-cargando">
                    <div class="spinner-border spinner-border-sm text-primary" role="status">
                        <span class="visually-hidden">Buscando...</span>
                    </div>
                    <span>Buscando...</span>
                </div>
            `;
            abrirDropdown();

            try {
                const url = `${this.apiBuscarOrdenesUrl}?q=${encodeURIComponent(query)}&tipo=activas&prefijo=${encodeURIComponent(this.prefijoOrdenRequerido)}`;
                const resp = await fetch(url, {
                    signal: this.ordenAbortController.signal,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                const data: OrdenAutocompleteResponse = await resp.json();
                renderResultados(query, data.resultados || []);
            } catch (err) {
                if (err instanceof Error && err.name === 'AbortError') return;
                cerrarDropdown();
            }
        };

        input.addEventListener('input', () => {
            const query = input.value.trim();

            if (query !== this.ordenTextoSeleccionado) {
                if (this.ordenServicioHidden) this.ordenServicioHidden.value = '';
                this.ordenEncontrada = false;
                this.ordenId = null;
                this.ocultarOrdenInfo();
                if (this.ordenStatusDiv) this.ordenStatusDiv.innerHTML = '';
            }

            if (this.ordenDebounceTimer) clearTimeout(this.ordenDebounceTimer);

            if (query.length < minChars) {
                cerrarDropdown();
                return;
            }

            this.ordenDebounceTimer = setTimeout(() => { void buscar(query); }, debounceMs);
        });

        input.addEventListener('focus', () => {
            const query = input.value.trim();
            if (query.length >= minChars && query !== this.ordenTextoSeleccionado && this.ordenAutocompleteResultados.length > 0) {
                abrirDropdown();
            }
        });

        input.addEventListener('keydown', (e: KeyboardEvent) => {
            const visible = dropdown.classList.contains('show') && this.ordenAutocompleteResultados.length > 0;
            if (!visible) return;

            if (e.key === 'Escape') {
                e.preventDefault();
                cerrarDropdown();
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.ordenIndiceActivo = Math.min(this.ordenIndiceActivo + 1, this.ordenAutocompleteResultados.length - 1);
            } else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.ordenIndiceActivo = Math.max(this.ordenIndiceActivo - 1, 0);
            } else if (e.key === 'Enter' && this.ordenIndiceActivo >= 0) {
                e.preventDefault();
                const r = this.ordenAutocompleteResultados[this.ordenIndiceActivo];
                if (r) seleccionar(r);
                return;
            } else {
                return;
            }

            dropdown.querySelectorAll<HTMLElement>('.orden-autocomplete-item').forEach((item, i) => {
                item.classList.toggle('active', i === this.ordenIndiceActivo);
                if (i === this.ordenIndiceActivo) item.scrollIntoView({ block: 'nearest' });
            });
        });

        document.addEventListener('click', (e: Event) => {
            if (!wrapper.contains(e.target as Node)) cerrarDropdown();
        });
    }

    private ocultarOrdenInfo(): void {
        if (this.ordenInfo) {
            this.ordenInfo.classList.add('d-none');
        }
        if (this.ordenInfoTexto) {
            this.ordenInfoTexto.innerHTML = '';
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
        
        // Evento: Cambio en cantidad (NUEVO)
        if (this.cantidadInput) {
            this.cantidadInput.addEventListener('input', () => {
                this.handleCantidadChange();
            });
        }
        
        // Evento: Input en orden_cliente — blur para búsqueda exacta si no se eligió del dropdown
        if (this.ordenClienteInput) {
            this.ordenClienteInput.addEventListener('blur', () => {
                if (!this.ordenId && this.ordenClienteInput?.value.trim()) {
                    this.buscarOrdenCliente();
                }
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
        
        // Actualizar prefijo y textos del autocompletado de orden
        this.actualizarConfigOrden(true);
        
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
        if (this.ordenAutocompleteDropdown) {
            this.ordenAutocompleteDropdown.classList.remove('show');
            this.ordenAutocompleteDropdown.innerHTML = '';
        }
        document.getElementById('orden-container')?.classList.remove('orden-autocomplete-activo');
        this.ocultarOrdenInfo();
        if (this.sucursalContainer) {
            this.sucursalContainer.style.display = 'none';
        }
        this.ordenEncontrada = false;
        this.ordenId = null;
        this.ordenTextoSeleccionado = '';
        this.ordenAutocompleteResultados = [];
    }
    
    /**
     * Valida el formato del número de orden según el tipo de solicitud.
     *
     * @returns true si el formato es válido para el tipo actual; false si hay error mostrado en UI
     */
    private validarFormatoOrden(): boolean {
        if (!this.ordenClienteInput || !this.ordenStatusDiv) {
            return false;
        }
        
        const valor = this.ordenClienteInput.value.trim().toUpperCase();
        const prefijo = this.prefijoOrdenRequerido;
        
        if (!valor) {
            this.ordenStatusDiv.innerHTML = '';
            this.ordenStatusDiv.className = '';
            if (this.sucursalContainer) {
                this.sucursalContainer.style.display = 'none';
            }
            return false;
        }
        
        if (prefijo === 'OOW' && !valor.startsWith('OOW-')) {
            this.ordenStatusDiv.innerHTML = `
                <span class="text-warning">
                    <i class="bi bi-exclamation-triangle me-1"></i>
                    Para Servicio Técnico el número debe empezar con "OOW-"
                </span>
            `;
            this.ordenStatusDiv.className = 'mt-2';
            return false;
        }
        
        if (prefijo === 'FL' && !valor.startsWith('FL-')) {
            this.ordenStatusDiv.innerHTML = `
                <span class="text-warning">
                    <i class="bi bi-exclamation-triangle me-1"></i>
                    Para Venta Mostrador el número debe empezar con "FL-"
                </span>
            `;
            this.ordenStatusDiv.className = 'mt-2';
            return false;
        }
        
        return true;
    }
    
    /**
     * Busca una orden por coincidencia exacta de orden_cliente.
     *
     * Se ejecuta en blur cuando el usuario escribió un número completo pero no
     * lo eligió del dropdown. Usa api_buscar_crear_orden con tipo_solicitud.
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
        
        if (!this.validarFormatoOrden()) {
            return;
        }
        
        const tipoSolicitud = this.tipoSolicitudSelect?.value || '';
        const url = `${this.apiBuscarCrearOrdenUrl}?orden_cliente=${encodeURIComponent(valor)}&tipo_solicitud=${encodeURIComponent(tipoSolicitud)}`;
        
        fetch(url)
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
            this.ordenEncontrada = true;
            this.ordenId = data.orden_id || null;
            this.ordenTextoSeleccionado = data.orden_cliente || this.ordenClienteInput?.value || '';
            
            if (this.ordenServicioHidden && data.orden_id) {
                this.ordenServicioHidden.value = data.orden_id.toString();
            }
            
            this.ordenStatusDiv.innerHTML = '';
            this.sucursalContainer.style.display = 'none';
            
            if (this.ordenInfo && this.ordenInfoTexto) {
                this.ordenInfo.classList.remove('d-none', 'alert-warning');
                this.ordenInfo.classList.add('alert-info');
                this.ordenInfoTexto.innerHTML = `
                    <strong>${data.orden_cliente || ''}</strong><br>
                    Estado: ${data.estado_display || data.estado || ''}<br>
                    Orden interna: ${data.numero_orden_interno || ''}<br>
                    Sucursal: ${data.sucursal || 'Sin asignar'}
                `;
            }
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
            this.ocultarOrdenInfo();
            
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
        // ========== VALIDACIÓN: Producto seleccionado desde autocompletado ==========
        const productoTexto = this.productoTextInput?.value.trim() || '';
        if (!this.productoHidden?.value) {
            e.preventDefault();
            this.productoTextInput?.classList.add('is-invalid-selection');
            if (productoTexto) {
                alert('Selecciona un producto de la lista de resultados.');
            } else {
                alert('Debes buscar y seleccionar un producto.');
            }
            this.productoTextInput?.focus();
            return;
        }

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
        
        // Validar formato según tipo de solicitud
        const prefijoEsperado = tipoSolicitud === 'venta_mostrador' ? 'FL-' : 'OOW-';
        const mensajePrefijo = tipoSolicitud === 'venta_mostrador'
            ? 'Para Venta Mostrador el número de orden debe empezar con "FL-"'
            : 'Para Servicio Técnico el número de orden debe empezar con "OOW-"';
        
        if (!ordenCliente.startsWith(prefijoEsperado)) {
            alert(mensajePrefijo);
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
     * Obtiene el token CSRF de las cookies.
     * En producción Django usa 'sigma_csrftoken'; en desarrollo usa 'csrftoken'.
     * Se intenta primero el nombre de producción y luego el predeterminado.
     */
    private getCSRFToken(): string {
        const names = ['sigma_csrftoken', 'csrftoken'];
        for (const name of names) {
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
            if (cookieValue) return cookieValue;
        }
        return '';
    }
    
    /**
     * Maneja el cambio en la cantidad solicitada
     * 
     * NUEVO (Enero 2026): Actualiza el display y revalida selección
     */
    private handleCantidadChange(): void {
        const cantidad = parseInt(this.cantidadInput?.value || '0', 10);
        this.cantidadSolicitada = cantidad;
        
        // Actualizar display
        if (this.cantidadSolicitadaDisplay) {
            this.cantidadSolicitadaDisplay.textContent = cantidad.toString();
        }
        
        // Validar cantidad vs stock si hay producto seleccionado
        if (this.productoHidden?.value) {
            this.actualizarStockInfoDisplay();
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
        if (!this.productoHidden || !this.unidadSelect || !this.unidadContainer) {
            return;
        }
        
        const productoId = this.productoHidden.value;
        
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
            this.stockActual = 0;
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
        
        // Mostrar info de stock (el API puede refinar el mensaje con unidades individuales)
        if (this.stockInfo && data.stock_info) {
            this.stockInfo.innerHTML = `<span class="text-success"><i class="bi bi-box-seam me-1"></i>${data.stock_info}</span>`;
        }
        if (typeof data.stock_actual === 'number') {
            this.stockActual = data.stock_actual;
            this.actualizarStockInfoDisplay();
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
 * Función de inicialización que se llama desde el template.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Django genera las URLs de los APIs y las pasa aquí para que JavaScript
 * no tenga rutas hardcodeadas. El handler configura autocompletado de producto
 * y orden, además del flujo de creación automática de órdenes OOW-/FL-.
 *
 * @param apiUnidadesUrl - Unidades disponibles de un producto seleccionado
 * @param apiTecnicosUrl - Técnicos de laboratorio para asignar
 * @param apiBuscarCrearOrdenUrl - Búsqueda exacta y creación de orden si no existe
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
