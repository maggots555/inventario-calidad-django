"use strict";
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
 * Clase principal que maneja el formulario de Nueva solicitud.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Centraliza autocompletado de producto y orden, carga de unidades,
 * visibilidad de campos según tipo_solicitud y creación automática de órdenes.
 */
class SolicitudBajaFormHandler {
    constructor(apiUnidadesUrl, apiTecnicosUrl, apiBuscarCrearOrdenUrl) {
        var _a, _b, _c, _d, _e;
        // Estado interno
        this.ordenEncontrada = false;
        this.ordenId = null;
        this.productoDebounceTimer = null;
        this.productoAbortController = null;
        this.ordenDebounceTimer = null;
        this.ordenAbortController = null;
        this.ordenAutocompleteResultados = [];
        this.ordenIndiceActivo = -1;
        this.ordenTextoSeleccionado = '';
        this.prefijoOrdenRequerido = null;
        this.stockActual = 0;
        this.productoTextoSeleccionado = '';
        // Estado de selección de unidades (NUEVO)
        this.unidadesSeleccionadas = new Set();
        this.cantidadSolicitada = 0;
        // Guardar URLs de los APIs
        this.apiUnidadesUrl = apiUnidadesUrl;
        this.apiTecnicosUrl = apiTecnicosUrl;
        this.apiBuscarCrearOrdenUrl = apiBuscarCrearOrdenUrl;
        // Obtener referencias a los elementos del DOM - Campos principales
        this.tipoSolicitudSelect = document.getElementById('id_tipo_solicitud');
        this.productoHidden = document.getElementById('id_producto');
        this.productoAutocompleteWrapper = document.getElementById('producto-autocomplete-wrapper');
        this.productoTextInput = (_a = this.productoAutocompleteWrapper) === null || _a === void 0 ? void 0 : _a.querySelector('.producto-autocomplete-input');
        this.cantidadInput = document.getElementById('id_cantidad');
        this.unidadSelect = document.getElementById('id_unidad_inventario');
        this.tecnicoSelect = document.getElementById('id_tecnico_asignado');
        this.sucursalDestinoSelect = document.getElementById('id_sucursal_destino');
        this.unidadContainer = document.getElementById('unidad-container');
        this.tecnicoContainer = document.getElementById('tecnico-container');
        this.sucursalDestinoContainer = document.getElementById('sucursal-destino-container');
        this.stockInfo = document.getElementById('stock-info');
        // Obtener referencias a elementos de unidades agrupadas (NUEVO)
        this.unidadesAgrupadasContainer = document.getElementById('unidades-agrupadas-container');
        this.gruposUnidadesContent = document.getElementById('grupos-unidades-content');
        this.contadorSeleccionadas = document.getElementById('contador-seleccionadas');
        this.cantidadSolicitadaDisplay = document.getElementById('cantidad-solicitada-display');
        this.unidadesSeleccionadasInput = document.getElementById('unidades_seleccionadas_ids');
        // Obtener referencias a los elementos del DOM - Campos de orden
        this.ordenClienteInput = document.getElementById('id_orden_cliente_input');
        this.ordenServicioHidden = document.getElementById('id_orden_servicio');
        this.sucursalOrdenSelect = document.getElementById('id_sucursal_orden');
        this.ordenStatusDiv = document.getElementById('orden-status');
        this.ordenInfo = document.getElementById('ordenInfo');
        this.ordenInfoTexto = document.getElementById('ordenInfoTexto');
        this.ordenHelpText = document.getElementById('orden-help-text');
        this.ordenAutocompleteWrapper = document.getElementById('orden-autocomplete-wrapper');
        this.ordenAutocompleteDropdown = (_b = this.ordenAutocompleteWrapper) === null || _b === void 0 ? void 0 : _b.querySelector('.orden-autocomplete-dropdown');
        this.sucursalContainer = document.getElementById('sucursal-container');
        const form = document.getElementById('solicitud-baja-form');
        this.apiBuscarProductosUrl = (form === null || form === void 0 ? void 0 : form.dataset.apiBuscarProductos)
            || ((_c = this.productoAutocompleteWrapper) === null || _c === void 0 ? void 0 : _c.dataset.apiUrl)
            || '';
        this.apiBuscarOrdenesUrl = ((_d = this.ordenAutocompleteWrapper) === null || _d === void 0 ? void 0 : _d.dataset.apiUrl) || '';
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
        if ((_e = this.productoHidden) === null || _e === void 0 ? void 0 : _e.value) {
            this.handleProductoChange();
        }
    }
    /**
     * Deshabilita la opción de transferencia para empleados no-agentes
     *
     * NUEVO (Enero 2026): Solo agentes de almacén pueden hacer transferencias
     */
    deshabilitarOpcionTransferencia() {
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
    initProductoAutocomplete() {
        const wrapper = this.productoAutocompleteWrapper;
        const hiddenInput = this.productoHidden;
        const textInput = this.productoTextInput;
        if (!wrapper || !hiddenInput || !textInput)
            return;
        const dropdown = wrapper.querySelector('.producto-autocomplete-dropdown');
        if (!dropdown)
            return;
        const minChars = 2;
        const debounceMs = 300;
        let resultados = [];
        let indiceActivo = -1;
        this.productoTextoSeleccionado = textInput.value;
        const cerrarDropdown = () => {
            dropdown.classList.remove('show');
            indiceActivo = -1;
        };
        const marcarInvalido = (invalido) => {
            textInput.classList.toggle('is-invalid-selection', invalido);
        };
        const getStockMetaClass = (stock) => {
            if (stock === 0)
                return 'text-danger';
            return 'text-muted';
        };
        const renderResultados = (items) => {
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
        const seleccionar = (prod) => {
            hiddenInput.value = String(prod.id);
            textInput.value = `${prod.codigo} — ${prod.nombre}`;
            this.productoTextoSeleccionado = textInput.value;
            this.stockActual = prod.stock;
            marcarInvalido(false);
            cerrarDropdown();
            this.actualizarStockInfoDisplay();
            this.handleProductoChange();
        };
        const buscar = async (termino) => {
            if (!this.apiBuscarProductosUrl || termino.length < minChars) {
                cerrarDropdown();
                return;
            }
            if (this.productoAbortController)
                this.productoAbortController.abort();
            this.productoAbortController = new AbortController();
            try {
                const url = `${this.apiBuscarProductosUrl}?q=${encodeURIComponent(termino)}`;
                const resp = await fetch(url, {
                    signal: this.productoAbortController.signal,
                    headers: { 'X-Requested-With': 'XMLHttpRequest' },
                });
                if (!resp.ok)
                    throw new Error(`HTTP ${resp.status}`);
                const data = await resp.json();
                renderResultados(data.productos || []);
            }
            catch (err) {
                if (err instanceof Error && err.name === 'AbortError')
                    return;
                cerrarDropdown();
            }
        };
        textInput.addEventListener('input', () => {
            const valor = textInput.value.trim();
            if (valor !== this.productoTextoSeleccionado) {
                hiddenInput.value = '';
                this.stockActual = 0;
                marcarInvalido(false);
                if (this.stockInfo)
                    this.stockInfo.innerHTML = '';
            }
            if (this.productoDebounceTimer)
                clearTimeout(this.productoDebounceTimer);
            this.productoDebounceTimer = setTimeout(() => { void buscar(valor); }, debounceMs);
        });
        textInput.addEventListener('focus', () => {
            const valor = textInput.value.trim();
            if (valor.length >= minChars && valor !== this.productoTextoSeleccionado) {
                void buscar(valor);
            }
        });
        textInput.addEventListener('keydown', (e) => {
            var _a;
            if (!dropdown.classList.contains('show'))
                return;
            const items = dropdown.querySelectorAll('.producto-autocomplete-item');
            if (items.length === 0)
                return;
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                indiceActivo = Math.min(indiceActivo + 1, items.length - 1);
            }
            else if (e.key === 'ArrowUp') {
                e.preventDefault();
                indiceActivo = Math.max(indiceActivo - 1, 0);
            }
            else if (e.key === 'Enter' && indiceActivo >= 0) {
                e.preventDefault();
                const prod = resultados[indiceActivo];
                if (prod)
                    seleccionar(prod);
                return;
            }
            else if (e.key === 'Escape') {
                cerrarDropdown();
                return;
            }
            else {
                return;
            }
            items.forEach((item, i) => item.classList.toggle('active', i === indiceActivo));
            (_a = items[indiceActivo]) === null || _a === void 0 ? void 0 : _a.scrollIntoView({ block: 'nearest' });
        });
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target))
                cerrarDropdown();
        });
    }
    /**
     * Muestra el stock disponible y valida cantidad vs stock en el cliente.
     */
    actualizarStockInfoDisplay() {
        var _a, _b;
        if (!this.stockInfo)
            return;
        if (!((_a = this.productoHidden) === null || _a === void 0 ? void 0 : _a.value)) {
            this.stockInfo.innerHTML = '';
            return;
        }
        const cantidad = parseInt(((_b = this.cantidadInput) === null || _b === void 0 ? void 0 : _b.value) || '0', 10);
        let stockClass = 'text-success';
        if (this.stockActual === 0) {
            stockClass = 'text-danger';
        }
        else if (cantidad > this.stockActual) {
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
    getPrefijoRequerido() {
        var _a;
        const tipo = (_a = this.tipoSolicitudSelect) === null || _a === void 0 ? void 0 : _a.value;
        if (tipo === 'servicio_tecnico')
            return 'OOW';
        if (tipo === 'venta_mostrador')
            return 'FL';
        return null;
    }
    /**
     * Actualiza placeholder, texto de ayuda y data-prefijo del autocompletado de orden.
     *
     * Si el usuario cambia entre Servicio Técnico y Venta Mostrador, limpia el
     * campo porque cada tipo usa un prefijo distinto (OOW vs FL).
     */
    actualizarConfigOrden(limpiarSiCambiaPrefijo = true) {
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
            }
            else if (nuevoPrefijo === 'FL') {
                this.ordenClienteInput.placeholder = 'Buscar orden FL- (venta mostrador)...';
            }
            else {
                this.ordenClienteInput.placeholder = 'Buscar orden...';
            }
        }
        if (this.ordenHelpText) {
            if (nuevoPrefijo === 'OOW') {
                this.ordenHelpText.innerHTML =
                    'Busca órdenes <strong>OOW-</strong> (diagnóstico). Si no existe, se creará al enviar.';
            }
            else if (nuevoPrefijo === 'FL') {
                this.ordenHelpText.innerHTML =
                    'Busca órdenes <strong>FL-</strong> (venta mostrador). Si no existe, se creará al enviar.';
            }
            else {
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
    initOrdenAutocomplete() {
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
        const cerrarDropdown = () => {
            dropdown.classList.remove('show');
            ordenContainer === null || ordenContainer === void 0 ? void 0 : ordenContainer.classList.remove('orden-autocomplete-activo');
            this.ordenIndiceActivo = -1;
        };
        const abrirDropdown = () => {
            ordenContainer === null || ordenContainer === void 0 ? void 0 : ordenContainer.classList.add('orden-autocomplete-activo');
            dropdown.classList.add('show');
        };
        const escaparHtml = (texto) => {
            const div = document.createElement('div');
            div.appendChild(document.createTextNode(texto));
            return div.innerHTML;
        };
        const resaltarCoincidencia = (texto, query) => {
            const safe = escaparHtml(texto || '');
            if (!query)
                return safe;
            const q = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`(${q})`, 'gi');
            return safe.replace(regex, '<mark>$1</mark>');
        };
        const filtrarPorPrefijo = (items) => {
            if (!this.prefijoOrdenRequerido)
                return items;
            const prefijo = `${this.prefijoOrdenRequerido}-`;
            return items.filter((r) => r.orden_cliente.toUpperCase().startsWith(prefijo));
        };
        const mostrarInfoSeleccion = (r) => {
            if (!this.ordenInfo || !this.ordenInfoTexto)
                return;
            this.ordenInfo.classList.remove('d-none', 'alert-warning');
            this.ordenInfo.classList.add('alert-info');
            this.ordenInfoTexto.innerHTML = `
                <strong>${escaparHtml(r.orden_cliente)}</strong><br>
                Estado: ${escaparHtml(r.estado)}<br>
                Marca: ${escaparHtml(r.marca)}${r.modelo ? ` · ${escaparHtml(r.modelo)}` : ''}<br>
                Orden interna: ${escaparHtml(r.numero_orden_interno)} · Serie: ${escaparHtml(r.numero_serie)}
            `;
        };
        const seleccionar = (r) => {
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
        const renderResultados = (query, items) => {
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
        const buscar = async (query) => {
            if (!this.apiBuscarOrdenesUrl || query.length < minChars || !this.prefijoOrdenRequerido) {
                cerrarDropdown();
                return;
            }
            if (this.ordenAbortController)
                this.ordenAbortController.abort();
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
                if (!resp.ok)
                    throw new Error(`HTTP ${resp.status}`);
                const data = await resp.json();
                renderResultados(query, data.resultados || []);
            }
            catch (err) {
                if (err instanceof Error && err.name === 'AbortError')
                    return;
                cerrarDropdown();
            }
        };
        input.addEventListener('input', () => {
            const query = input.value.trim();
            if (query !== this.ordenTextoSeleccionado) {
                if (this.ordenServicioHidden)
                    this.ordenServicioHidden.value = '';
                this.ordenEncontrada = false;
                this.ordenId = null;
                this.ocultarOrdenInfo();
                if (this.ordenStatusDiv)
                    this.ordenStatusDiv.innerHTML = '';
            }
            if (this.ordenDebounceTimer)
                clearTimeout(this.ordenDebounceTimer);
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
        input.addEventListener('keydown', (e) => {
            const visible = dropdown.classList.contains('show') && this.ordenAutocompleteResultados.length > 0;
            if (!visible)
                return;
            if (e.key === 'Escape') {
                e.preventDefault();
                cerrarDropdown();
            }
            else if (e.key === 'ArrowDown') {
                e.preventDefault();
                this.ordenIndiceActivo = Math.min(this.ordenIndiceActivo + 1, this.ordenAutocompleteResultados.length - 1);
            }
            else if (e.key === 'ArrowUp') {
                e.preventDefault();
                this.ordenIndiceActivo = Math.max(this.ordenIndiceActivo - 1, 0);
            }
            else if (e.key === 'Enter' && this.ordenIndiceActivo >= 0) {
                e.preventDefault();
                const r = this.ordenAutocompleteResultados[this.ordenIndiceActivo];
                if (r)
                    seleccionar(r);
                return;
            }
            else {
                return;
            }
            dropdown.querySelectorAll('.orden-autocomplete-item').forEach((item, i) => {
                item.classList.toggle('active', i === this.ordenIndiceActivo);
                if (i === this.ordenIndiceActivo)
                    item.scrollIntoView({ block: 'nearest' });
            });
        });
        document.addEventListener('click', (e) => {
            if (!wrapper.contains(e.target))
                cerrarDropdown();
        });
    }
    ocultarOrdenInfo() {
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
    initEventListeners() {
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
                var _a;
                if (!this.ordenId && ((_a = this.ordenClienteInput) === null || _a === void 0 ? void 0 : _a.value.trim())) {
                    this.buscarOrdenCliente();
                }
            });
        }
        // Interceptar el submit del formulario para validar y crear orden si es necesario
        const form = document.getElementById('solicitud-baja-form');
        if (form) {
            form.addEventListener('submit', (e) => {
                this.handleFormSubmit(e, form);
            });
        }
        else {
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
    handleTipoSolicitudChange() {
        var _a, _b;
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
                if (label && !((_a = label.textContent) === null || _a === void 0 ? void 0 : _a.includes('*'))) {
                    label.innerHTML = '<i class="bi bi-person-gear me-1"></i>Técnico de Laboratorio *';
                }
                if (ordenContainer) {
                    ordenContainer.style.display = 'block';
                }
            }
            else {
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
                if (label && !((_b = label.textContent) === null || _b === void 0 ? void 0 : _b.includes('*'))) {
                    label.innerHTML = '<i class="bi bi-building me-1"></i>Sucursal Destino *';
                }
            }
            else {
                this.sucursalDestinoContainer.style.display = 'none';
                this.sucursalDestinoSelect.value = '';
                this.sucursalDestinoSelect.removeAttribute('required');
            }
        }
    }
    /**
     * Limpia los campos relacionados con la orden de servicio
     */
    limpiarCamposOrden() {
        var _a;
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
        (_a = document.getElementById('orden-container')) === null || _a === void 0 ? void 0 : _a.classList.remove('orden-autocomplete-activo');
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
    validarFormatoOrden() {
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
    buscarOrdenCliente() {
        var _a;
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
        const tipoSolicitud = ((_a = this.tipoSolicitudSelect) === null || _a === void 0 ? void 0 : _a.value) || '';
        const url = `${this.apiBuscarCrearOrdenUrl}?orden_cliente=${encodeURIComponent(valor)}&tipo_solicitud=${encodeURIComponent(tipoSolicitud)}`;
        fetch(url)
            .then(response => response.json())
            .then((data) => {
            this.procesarRespuestaBusqueda(data);
        })
            .catch(error => {
            console.error('Error buscando orden:', error);
            this.ordenStatusDiv.innerHTML = `
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
    procesarRespuestaBusqueda(data) {
        var _a;
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
            }
            else {
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
            this.ordenTextoSeleccionado = data.orden_cliente || ((_a = this.ordenClienteInput) === null || _a === void 0 ? void 0 : _a.value) || '';
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
        }
        else {
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
    handleFormSubmit(e, form) {
        var _a, _b, _c, _d, _e, _f, _g, _h, _j, _k;
        // ========== VALIDACIÓN: Producto seleccionado desde autocompletado ==========
        const productoTexto = ((_a = this.productoTextInput) === null || _a === void 0 ? void 0 : _a.value.trim()) || '';
        if (!((_b = this.productoHidden) === null || _b === void 0 ? void 0 : _b.value)) {
            e.preventDefault();
            (_c = this.productoTextInput) === null || _c === void 0 ? void 0 : _c.classList.add('is-invalid-selection');
            if (productoTexto) {
                alert('Selecciona un producto de la lista de resultados.');
            }
            else {
                alert('Debes buscar y seleccionar un producto.');
            }
            (_d = this.productoTextInput) === null || _d === void 0 ? void 0 : _d.focus();
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
        const tipoSolicitud = (_e = this.tipoSolicitudSelect) === null || _e === void 0 ? void 0 : _e.value;
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
        const ordenCliente = (_f = this.ordenClienteInput) === null || _f === void 0 ? void 0 : _f.value.trim().toUpperCase();
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
        const sucursalId = (_g = this.sucursalOrdenSelect) === null || _g === void 0 ? void 0 : _g.value;
        if (!sucursalId) {
            alert('Debe seleccionar una sucursal para crear la orden de servicio.');
            (_h = this.sucursalOrdenSelect) === null || _h === void 0 ? void 0 : _h.focus();
            return;
        }
        // Verificar que se haya seleccionado técnico
        const tecnicoId = (_j = this.tecnicoSelect) === null || _j === void 0 ? void 0 : _j.value;
        if (!tecnicoId) {
            alert('Debe seleccionar un técnico de laboratorio.');
            (_k = this.tecnicoSelect) === null || _k === void 0 ? void 0 : _k.focus();
            return;
        }
        // Mostrar indicador de carga
        const submitBtn = document.querySelector('button[type="submit"]');
        const originalText = (submitBtn === null || submitBtn === void 0 ? void 0 : submitBtn.innerHTML) || 'Enviar';
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
    crearOrdenYEnviar(ordenCliente, sucursalId, tecnicoId, form, submitBtn, originalText) {
        var _a;
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
                tipo_solicitud: ((_a = this.tipoSolicitudSelect) === null || _a === void 0 ? void 0 : _a.value) || 'servicio_tecnico',
            }),
        })
            .then(response => response.json())
            .then((data) => {
            if (data.success && data.created && data.orden_id) {
                // ✅ Orden creada exitosamente
                // Guardar el ID en el campo oculto
                if (this.ordenServicioHidden) {
                    this.ordenServicioHidden.value = data.orden_id.toString();
                }
                // Ahora sí enviar el formulario
                form.submit();
            }
            else {
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
    getCSRFToken() {
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
            if (cookieValue)
                return cookieValue;
        }
        return '';
    }
    /**
     * Maneja el cambio en la cantidad solicitada
     *
     * NUEVO (Enero 2026): Actualiza el display y revalida selección
     */
    handleCantidadChange() {
        var _a, _b, _c;
        const cantidad = parseInt(((_a = this.cantidadInput) === null || _a === void 0 ? void 0 : _a.value) || '0', 10);
        this.cantidadSolicitada = cantidad;
        // Actualizar display
        if (this.cantidadSolicitadaDisplay) {
            this.cantidadSolicitadaDisplay.textContent = cantidad.toString();
        }
        // Validar cantidad vs stock si hay producto seleccionado
        if ((_b = this.productoHidden) === null || _b === void 0 ? void 0 : _b.value) {
            this.actualizarStockInfoDisplay();
        }
        // Si hay unidades agrupadas cargadas, actualizar validación
        if (((_c = this.unidadesAgrupadasContainer) === null || _c === void 0 ? void 0 : _c.style.display) !== 'none') {
            this.actualizarContadorSeleccionadas();
        }
    }
    /**
     * Actualiza el contador de unidades seleccionadas
     */
    actualizarContadorSeleccionadas() {
        if (!this.contadorSeleccionadas)
            return;
        const seleccionadas = this.unidadesSeleccionadas.size;
        const requeridas = this.cantidadSolicitada;
        const badge = this.contadorSeleccionadas;
        badge.textContent = `${seleccionadas} / ${requeridas} seleccionadas`;
        // Cambiar color según estado
        badge.className = 'badge bg-light text-dark';
        if (seleccionadas === 0) {
            badge.className = 'badge bg-secondary';
        }
        else if (seleccionadas === requeridas) {
            badge.className = 'badge bg-success';
        }
        else if (seleccionadas > requeridas) {
            badge.className = 'badge bg-danger';
        }
        else {
            badge.className = 'badge bg-warning text-dark';
        }
    }
    /**
     * Maneja el click en un checkbox de unidad
     *
     * ACTUALIZADO (Enero 2026): Valida solicitudes pendientes
     */
    handleUnidadCheckboxChange(unidadId, checked) {
        if (checked) {
            // Verificar si la unidad tiene solicitud pendiente
            const checkbox = document.querySelector(`input[data-unidad-id="${unidadId}"]`);
            const tieneSolicitud = (checkbox === null || checkbox === void 0 ? void 0 : checkbox.getAttribute('data-tiene-solicitud')) === 'true';
            if (tieneSolicitud) {
                const confirmar = confirm('⚠️ ADVERTENCIA: Esta unidad ya tiene una solicitud pendiente.\n\n' +
                    '¿Estás seguro de que quieres seleccionarla?\n\n' +
                    'Esto podría causar conflictos de inventario si ambas solicitudes se procesan.');
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
                if (checkbox)
                    checkbox.checked = false;
                return;
            }
            this.unidadesSeleccionadas.add(unidadId);
        }
        else {
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
    actualizarUnidadesSeleccionadasInput() {
        if (!this.unidadesSeleccionadasInput)
            return;
        const idsArray = Array.from(this.unidadesSeleccionadas);
        this.unidadesSeleccionadasInput.value = idsArray.join(',');
    }
    /**
     * Renderiza los grupos de unidades con checkboxes
     */
    renderizarGruposUnidades(grupos) {
        if (!this.gruposUnidadesContent)
            return;
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
                                                 ID: #${solicitudPendiente === null || solicitudPendiente === void 0 ? void 0 : solicitudPendiente.id}<br>
                                                 Solicitante: ${solicitudPendiente === null || solicitudPendiente === void 0 ? void 0 : solicitudPendiente.solicitante}<br>
                                                 Fecha: ${solicitudPendiente === null || solicitudPendiente === void 0 ? void 0 : solicitudPendiente.fecha}<br>
                                                 Tipo: ${solicitudPendiente === null || solicitudPendiente === void 0 ? void 0 : solicitudPendiente.tipo}<br>
                                                 Cantidad: ${solicitudPendiente === null || solicitudPendiente === void 0 ? void 0 : solicitudPendiente.cantidad}">
                                        ⚠️ Pendiente
                                    </span>
                                ` : ''}
                            </label>
                        </td>
                        <td>
                            ${unidad.sucursal_actual ?
                    `<i class="bi bi-building text-primary me-1"></i><span class="fw-medium">${unidad.sucursal_actual.nombre}</span>` :
                    `<i class="bi bi-house text-secondary me-1"></i><span class="text-muted">Almacén Central</span>`}
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
            new window.bootstrap.Tooltip(tooltipTriggerEl);
        });
        // Agregar event listeners a los checkboxes
        const checkboxes = this.gruposUnidadesContent.querySelectorAll('.unidad-checkbox');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const target = e.target;
                const unidadId = parseInt(target.getAttribute('data-unidad-id') || '0');
                this.handleUnidadCheckboxChange(unidadId, target.checked);
            });
        });
    }
    /**
     * Obtiene la clase CSS para el badge de estado
     */
    getBadgeEstado(estado) {
        const badgeMap = {
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
    handleProductoChange() {
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
            .then((data) => {
            this.processUnidadesResponse(data);
        })
            .catch(error => {
            console.error('Error cargando unidades:', error);
            this.unidadSelect.innerHTML = '<option value="">-- Error al cargar unidades --</option>';
        });
    }
    /**
     * Procesa la respuesta del API de unidades
     *
     * ACTUALIZADO (Enero 2026): Renderiza unidades agrupadas con checkboxes
     */
    processUnidadesResponse(data) {
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
        }
        else if (this.unidadesAgrupadasContainer) {
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
let solicitudBajaHandler = null;
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
function initSolicitudBajaForm(apiUnidadesUrl, apiTecnicosUrl, apiBuscarCrearOrdenUrl) {
    document.addEventListener('DOMContentLoaded', function () {
        solicitudBajaHandler = new SolicitudBajaFormHandler(apiUnidadesUrl, apiTecnicosUrl, apiBuscarCrearOrdenUrl);
    });
}
// Exportar función al scope global para que el template pueda usarla
window.initSolicitudBajaForm = initSolicitudBajaForm;
//# sourceMappingURL=solicitud_baja_form.js.map