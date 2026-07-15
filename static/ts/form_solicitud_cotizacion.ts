/**
 * Formulario de Solicitud de Cotización — Lógica de Formset Dinámico
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * --------------------------------
 * Este módulo maneja un "formset" de Django: un conjunto de formularios
 * repetidos (líneas de cotización) que el usuario puede agregar y eliminar
 * dinámicamente desde el navegador.
 *
 * El problema que resuelve:
 * - Django espera recibir los formularios numerados en secuencia continua
 *   (0, 1, 2, 3...) y que TOTAL_FORMS coincida con la cantidad real.
 * - Si eliminas una línea del DOM sin reindexar, Django recibe datos con
 *   índices discontinuos (0, 1, 3) y los formularios "saltados" se pierden.
 *
 * Funcionalidades:
 * 1. Agregar líneas nuevas desde un <template> oculto
 * 2. Eliminar líneas nuevas: remover del DOM + reindexar + decrementar TOTAL_FORMS
 * 3. Eliminar líneas existentes: marcar checkbox DELETE + ocultar visualmente
 * 4. Toggle modo "sin orden activa" (muestra datos del cliente + imágenes)
 * 5. Autocompletado inteligente de órdenes de servicio (serie, orden cliente, interna)
 * 6. Cálculo de subtotales y total general en tiempo real
 * 7. Preview de imágenes de referencia antes de subir
 * 8. Autocomplete de modelo de equipo basado en la marca seleccionada
 */

/* =============================================================================
   INTERFACES — Definiciones de tipos para los datos del formulario
   ============================================================================= */

interface PiezaSugeridaDiagnostico {
    componente_db: string;
    dpn: string;
    es_necesaria: boolean;
}

interface OrdenAutocompleteResultado {
    id: number;
    orden_cliente: string;
    numero_serie: string;
    numero_orden_interno: string;
    marca: string;
    modelo: string;
    estado: string;
    /** Piezas marcadas al enviar el diagnóstico (solo ayuda visual para Almacén) */
    piezas_sugeridas?: PiezaSugeridaDiagnostico[];
}

interface OrdenAutocompleteResponse {
    resultados: OrdenAutocompleteResultado[];
}

interface ModeloResultado {
    id: string;
    text: string;
    gama?: string;
}

interface ModeloResponse {
    results: ModeloResultado[];
    total?: number;
    error?: string;
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

interface ProductoInfoResponse {
    success: boolean;
    producto?: {
        id: number;
        codigo: string;
        nombre: string;
        stock: number;
        costo: number;
        tipo: string;
    };
}

/* =============================================================================
   AUTOCOMPLETADO DE PRODUCTO — Búsqueda AJAX por código o nombre
   ============================================================================= */

class ProductoAutocompleteManager {
    private readonly apiBuscarUrl: string;
    private readonly apiInfoUrlTemplate: string;
    private readonly debounceMs = 300;
    private readonly minChars = 2;

    constructor(form: HTMLFormElement) {
        this.apiBuscarUrl = form.dataset.apiBuscarProductos || '';
        this.apiInfoUrlTemplate = form.dataset.apiInfoProducto || '';
    }

    /** Inicializa todos los wrappers que aún no tienen listeners */
    public initAll(): void {
        document.querySelectorAll<HTMLElement>('.producto-autocomplete:not([data-autocomplete-init])')
            .forEach((wrapper) => this.initWrapper(wrapper));
    }

    /** Configura un campo de autocompletado dentro de una línea del formset */
    public initWrapper(wrapper: HTMLElement): void {
        if (wrapper.dataset.autocompleteInit === '1') return;
        wrapper.dataset.autocompleteInit = '1';

        const hiddenInput = wrapper.querySelector<HTMLInputElement>('.producto-id-input');
        const textInput = wrapper.querySelector<HTMLInputElement>('.producto-autocomplete-input');
        const dropdown = wrapper.querySelector<HTMLElement>('.producto-autocomplete-dropdown');

        if (!hiddenInput || !textInput || !dropdown) return;

        let debounceTimer: ReturnType<typeof setTimeout> | null = null;
        let abortController: AbortController | null = null;
        let resultados: ProductoBusqueda[] = [];
        let indiceActivo = -1;
        let textoSeleccionado = textInput.value;

        const cerrarDropdown = (): void => {
            dropdown.classList.remove('show');
            indiceActivo = -1;
        };

        const marcarInvalido = (invalido: boolean): void => {
            textInput.classList.toggle('is-invalid-selection', invalido);
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
                btn.innerHTML = `
                    <div class="prod-codigo">${prod.codigo}</div>
                    <div class="prod-nombre">${prod.nombre}</div>
                    <div class="prod-meta">Stock: ${prod.stock} · $${prod.costo.toFixed(2)}</div>
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
            textoSeleccionado = textInput.value;
            marcarInvalido(false);
            cerrarDropdown();
            prefillCamposLinea(wrapper, prod.id);
        };

        const buscar = async (termino: string): Promise<void> => {
            if (!this.apiBuscarUrl || termino.length < this.minChars) {
                cerrarDropdown();
                return;
            }

            if (abortController) abortController.abort();
            abortController = new AbortController();

            try {
                const url = `${this.apiBuscarUrl}?q=${encodeURIComponent(termino)}`;
                const resp = await fetch(url, {
                    signal: abortController.signal,
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
            if (valor !== textoSeleccionado) {
                hiddenInput.value = '';
                marcarInvalido(false);
            }
            if (debounceTimer) clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => { void buscar(valor); }, this.debounceMs);
        });

        textInput.addEventListener('focus', () => {
            const valor = textInput.value.trim();
            if (valor.length >= this.minChars && valor !== textoSeleccionado) {
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
}

/** Sugiere descripción y costo si los campos de la línea están vacíos */
async function prefillCamposLinea(wrapper: HTMLElement, productoId: number): Promise<void> {
    const form = document.getElementById('solicitudForm') as HTMLFormElement | null;
    if (!form) return;

    const infoUrlTemplate = form.dataset.apiInfoProducto || '';
    if (!infoUrlTemplate) return;

    const infoUrl = infoUrlTemplate.replace('/0/', `/${productoId}/`);
    const lineaForm = wrapper.closest('.linea-form');
    if (!lineaForm) return;

    const descInput = lineaForm.querySelector<HTMLInputElement>('[name$="-descripcion_pieza"]');
    const costoInput = lineaForm.querySelector<HTMLInputElement>('[name$="-costo_unitario"]');

    try {
        const resp = await fetch(infoUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
        if (!resp.ok) return;
        const data: ProductoInfoResponse = await resp.json();
        if (!data.success || !data.producto) return;

        if (descInput && !descInput.value.trim()) {
            descInput.value = data.producto.nombre;
        }
        if (costoInput && !costoInput.value.trim() && data.producto.costo > 0) {
            costoInput.value = data.producto.costo.toFixed(2);
            costoInput.dispatchEvent(new Event('input', { bubbles: true }));
        }
    } catch {
        // Fail-safe: no bloquear si falla el prellenado
    }
}


/* =============================================================================
   AUTOCOMPLETADO DE ORDEN — Búsqueda typeahead (serie, orden cliente, interna)
   ============================================================================= */

class OrdenAutocompleteManager {
    private readonly wrapper: HTMLElement;
    private readonly input: HTMLInputElement;
    private readonly dropdown: HTMLElement;
    private readonly ordenInfo: HTMLElement;
    private readonly ordenInfoTexto: HTMLElement;
    private readonly apiUrl: string;
    private readonly tipo: string;
    private readonly debounceMs = 300;
    private readonly minChars = 2;

    private debounceTimer: ReturnType<typeof setTimeout> | null = null;
    private abortController: AbortController | null = null;
    private resultados: OrdenAutocompleteResultado[] = [];
    private indiceActivo = -1;
    private textoSeleccionado = '';

    constructor(
        wrapper: HTMLElement,
        ordenInfo: HTMLElement,
        ordenInfoTexto: HTMLElement,
    ) {
        this.wrapper = wrapper;
        this.ordenInfo = ordenInfo;
        this.ordenInfoTexto = ordenInfoTexto;
        this.apiUrl = wrapper.dataset.apiUrl || '';
        this.tipo = wrapper.dataset.tipo || 'activas';

        const input = wrapper.querySelector<HTMLInputElement>('.orden-autocomplete-input');
        const dropdown = wrapper.querySelector<HTMLElement>('.orden-autocomplete-dropdown');
        if (!input || !dropdown) {
            throw new Error('OrdenAutocompleteManager: faltan input o dropdown');
        }
        this.input = input;
        this.dropdown = dropdown;
        this.textoSeleccionado = input.value.trim();
    }

    /** Conecta eventos del campo de búsqueda de orden */
    public init(): void {
        this.input.addEventListener('input', () => this.manejarInput());
        this.input.addEventListener('keydown', (e) => this.manejarTeclado(e));
        this.input.addEventListener('focus', () => {
            if (this.input.value.trim().length >= this.minChars && this.resultados.length > 0) {
                this.mostrarDropdown();
            }
        });

        document.addEventListener('click', (e) => {
            if (!this.wrapper.contains(e.target as Node)) {
                this.cerrarDropdown();
            }
        });

        // Edición: si ya hay orden vinculada, mostrar aviso simple
        if (this.textoSeleccionado) {
            this.mostrarInfoPrellenada(this.textoSeleccionado);
        }
    }

    /** Limpia campo, dropdown y panel de confirmación (modo sin orden) */
    public limpiar(): void {
        this.input.value = '';
        this.textoSeleccionado = '';
        this.cerrarDropdown();
        this.ocultarInfo();
    }

    private manejarInput(): void {
        const query = this.input.value.trim();

        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
            this.debounceTimer = null;
        }

        if (query !== this.textoSeleccionado) {
            this.ocultarInfo();
        }

        if (query.length < this.minChars) {
            this.cerrarDropdown();
            return;
        }

        this.debounceTimer = setTimeout(() => {
            void this.buscar(query);
        }, this.debounceMs);
    }

    private manejarTeclado(e: KeyboardEvent): void {
        const visible = this.dropdown.classList.contains('show') && this.resultados.length > 0;

        switch (e.key) {
            case 'Escape':
                if (visible) {
                    e.preventDefault();
                    this.cerrarDropdown();
                }
                break;
            case 'ArrowDown':
                if (visible) {
                    e.preventDefault();
                    this.navegar(1);
                }
                break;
            case 'ArrowUp':
                if (visible) {
                    e.preventDefault();
                    this.navegar(-1);
                }
                break;
            case 'Enter':
                if (visible && this.indiceActivo >= 0) {
                    e.preventDefault();
                    const r = this.resultados[this.indiceActivo];
                    if (r) this.seleccionar(r);
                }
                break;
        }
    }

    private async buscar(query: string): Promise<void> {
        if (!this.apiUrl) return;

        if (this.abortController) this.abortController.abort();
        this.abortController = new AbortController();

        this.mostrarCargando();

        try {
            const url = `${this.apiUrl}?q=${encodeURIComponent(query)}&tipo=${encodeURIComponent(this.tipo)}`;
            const resp = await fetch(url, {
                signal: this.abortController.signal,
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const data: OrdenAutocompleteResponse = await resp.json();
            this.resultados = data.resultados || [];
            this.indiceActivo = -1;

            if (this.resultados.length > 0) {
                this.renderResultados(query);
            } else {
                this.mostrarSinResultados(query);
            }
        } catch (err) {
            if (err instanceof Error && err.name === 'AbortError') return;
            this.cerrarDropdown();
        }
    }

    private renderResultados(query: string): void {
        const lista = document.createElement('ul');
        lista.className = 'orden-autocomplete-lista';
        lista.setAttribute('role', 'listbox');

        this.resultados.forEach((r, idx) => {
            const li = document.createElement('li');
            li.className = 'orden-autocomplete-item';
            li.setAttribute('role', 'option');
            li.dataset.index = String(idx);

            const ordenHtml = this.resaltarCoincidencia(r.orden_cliente, query);
            const serieHtml = this.resaltarCoincidencia(r.numero_serie, query);
            const internoHtml = this.resaltarCoincidencia(r.numero_orden_interno, query);

            li.innerHTML = `
                <div class="orden-autocomplete-item-principal">
                    <span class="orden-autocomplete-orden">${ordenHtml}</span>
                    <span class="orden-autocomplete-marca badge bg-secondary">${this.escaparHtml(r.marca)}</span>
                </div>
                <div class="orden-autocomplete-item-secundario">
                    <span><i class="bi bi-upc-scan"></i> ${serieHtml}</span>
                    <span><i class="bi bi-hash"></i> ${internoHtml}</span>
                    <span class="badge bg-light text-dark">${this.escaparHtml(r.estado)}</span>
                </div>
            `;

            li.addEventListener('mousedown', (e) => {
                e.preventDefault();
                this.seleccionar(r);
            });
            li.addEventListener('mouseenter', () => this.actualizarSeleccion(idx));

            lista.appendChild(li);
        });

        this.dropdown.innerHTML = '';
        this.dropdown.appendChild(lista);
        this.mostrarDropdown();
    }

    private seleccionar(r: OrdenAutocompleteResultado): void {
        this.input.value = r.orden_cliente;
        this.textoSeleccionado = r.orden_cliente;
        this.cerrarDropdown();
        this.mostrarInfoSeleccion(r);
    }

    private mostrarInfoSeleccion(r: OrdenAutocompleteResultado): void {
        this.ordenInfo.classList.remove('d-none', 'alert-warning');
        this.ordenInfo.classList.add('alert-info');

        // EXPLICACIÓN PARA PRINCIPIANTES:
        // Armamos el resumen de la orden elegida. Si el diagnóstico ya se envió
        // con piezas marcadas, la API trae piezas_sugeridas para orientar a Almacén
        // (no se agregan solas al formset; solo se muestran aquí).
        let htmlSugerencias = '';
        const sugerencias = r.piezas_sugeridas || [];
        if (sugerencias.length > 0) {
            const items = sugerencias.map((p) => {
                const dpn = p.dpn ? ` · DPN: ${this.escaparHtml(p.dpn)}` : '';
                const tipoLabel = p.es_necesaria ? 'Necesaria' : 'Opcional';
                const tipoClass = p.es_necesaria
                    ? 'badge-sugerencia-necesaria'
                    : 'badge-sugerencia-opcional';
                return (
                    `<li class="orden-sugerencia-pieza">` +
                    `<span class="orden-sugerencia-nombre">${this.escaparHtml(p.componente_db)}</span>` +
                    `<span class="orden-sugerencia-dpn">${dpn}</span>` +
                    `<span class="badge ${tipoClass}">${tipoLabel}</span>` +
                    `</li>`
                );
            }).join('');

            htmlSugerencias = `
                <div class="orden-sugerencias-piezas mt-2">
                    <strong class="orden-sugerencias-titulo">
                        <i class="bi bi-lightbulb"></i> Piezas sugeridas por diagnóstico
                        <span class="badge bg-secondary">${sugerencias.length}</span>
                    </strong>
                    <ul class="orden-sugerencias-lista mb-0 mt-1">${items}</ul>
                    <small class="text-muted d-block mt-1">
                        Solo referencia: valida y cotiza las piezas en las líneas de abajo.
                    </small>
                </div>
            `;
        } else {
            htmlSugerencias = `
                <div class="orden-sugerencias-piezas mt-2 orden-sugerencias-vacias">
                    <small class="text-muted">
                        <i class="bi bi-info-circle"></i>
                        Sin piezas sugeridas de diagnóstico (aún no se envió o no se marcaron componentes).
                    </small>
                </div>
            `;
        }

        this.ordenInfoTexto.innerHTML = `
            <strong>${this.escaparHtml(r.orden_cliente)}</strong><br>
            Estado: ${this.escaparHtml(r.estado)}<br>
            Marca: ${this.escaparHtml(r.marca)}${r.modelo ? ` · ${this.escaparHtml(r.modelo)}` : ''}<br>
            Orden interna: ${this.escaparHtml(r.numero_orden_interno)} · Serie: ${this.escaparHtml(r.numero_serie)}
            ${htmlSugerencias}
        `;
    }

    private mostrarInfoPrellenada(ordenCliente: string): void {
        this.ordenInfo.classList.remove('d-none', 'alert-warning');
        this.ordenInfo.classList.add('alert-info');
        this.ordenInfoTexto.innerHTML = `
            <strong>${this.escaparHtml(ordenCliente)}</strong><br>
            <small class="text-muted">Orden vinculada. Escribe para buscar otra.</small>
        `;
    }

    private mostrarSinResultados(query: string): void {
        this.dropdown.innerHTML = `
            <div class="orden-autocomplete-empty">
                <i class="bi bi-search"></i>
                <span>Sin coincidencias para "<strong>${this.escaparHtml(query)}</strong>"</span>
            </div>
        `;
        this.mostrarDropdown();
    }

    private mostrarCargando(): void {
        this.dropdown.innerHTML = `
            <div class="orden-autocomplete-cargando">
                <div class="spinner-border spinner-border-sm text-primary" role="status">
                    <span class="visually-hidden">Buscando...</span>
                </div>
                <span>Buscando...</span>
            </div>
        `;
        this.mostrarDropdown();
    }

    private navegar(direccion: number): void {
        const total = this.resultados.length;
        if (total === 0) return;

        let nuevo = this.indiceActivo + direccion;
        if (nuevo < 0) nuevo = total - 1;
        if (nuevo >= total) nuevo = 0;
        this.actualizarSeleccion(nuevo);
    }

    private actualizarSeleccion(indice: number): void {
        const items = this.dropdown.querySelectorAll<HTMLElement>('.orden-autocomplete-item');
        items.forEach((item, i) => {
            item.classList.toggle('active', i === indice);
            if (i === indice) item.scrollIntoView({ block: 'nearest' });
        });
        this.indiceActivo = indice;
    }

    private mostrarDropdown(): void {
        this.dropdown.classList.add('show');
    }

    private cerrarDropdown(): void {
        this.dropdown.classList.remove('show');
        this.indiceActivo = -1;
    }

    private ocultarInfo(): void {
        this.ordenInfo.classList.add('d-none');
    }

    private resaltarCoincidencia(texto: string, query: string): string {
        const safe = this.escaparHtml(texto || '');
        if (!query) return safe;
        const q = query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const regex = new RegExp(`(${q})`, 'gi');
        return safe.replace(regex, '<mark>$1</mark>');
    }

    private escaparHtml(texto: string): string {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(texto));
        return div.innerHTML;
    }
}


class FormSolicitudCotizacionManager {

    private container: HTMLElement;
    private template: HTMLTemplateElement;
    private addBtn: HTMLElement;
    private totalFormsInput: HTMLInputElement;
    private ordenInput: HTMLInputElement;
    private sinOrdenCheckbox: HTMLInputElement;
    private ordenClienteContainer: HTMLElement;
    private sinOrdenContainer: HTMLElement;
    private serviceTagInput: HTMLInputElement;
    private nombreClienteInput: HTMLInputElement;
    private imagenesReferenciaCard: HTMLElement | null;
    private marcaSelect: HTMLSelectElement | null;
    private modeloInput: HTMLInputElement | null;
    private modeloApiUrl: string;
    private formCount: number;
    private maxImagenes: number;
    private debounceTimer: ReturnType<typeof setTimeout> | null = null;
    private readonly productoAutocomplete: ProductoAutocompleteManager;
    private readonly ordenAutocomplete: OrdenAutocompleteManager;

    constructor() {
        const container = document.getElementById('lineasContainer');
        const template = document.getElementById('lineaTemplate') as HTMLTemplateElement;
        const addBtn = document.getElementById('addLineaBtn');
        const totalFormsInput = document.querySelector<HTMLInputElement>('[name="lineas-TOTAL_FORMS"]');
        const ordenWrapper = document.getElementById('ordenAutocompleteWrapper');
        const ordenInput = document.getElementById('numero_orden_cliente') as HTMLInputElement;
        const ordenInfo = document.getElementById('ordenInfo');
        const ordenInfoTexto = document.getElementById('ordenInfoTexto');
        const sinOrdenCheckbox = document.getElementById('sin_orden_activa') as HTMLInputElement;
        const ordenClienteContainer = document.getElementById('ordenClienteContainer');
        const sinOrdenContainer = document.getElementById('sinOrdenContainer');
        const serviceTagInput = document.getElementById('service_tag') as HTMLInputElement;
        const nombreClienteInput = document.getElementById('nombre_cliente') as HTMLInputElement;
        const imagenesReferenciaCard = document.getElementById('imagenesReferenciaCard');
        const marcaSelect = document.getElementById('marca') as HTMLSelectElement | null;
        const modeloInput = document.getElementById('modelo') as HTMLInputElement | null;

        if (!container) throw new Error('No se encontró #lineasContainer');
        if (!template) throw new Error('No se encontró #lineaTemplate');
        if (!addBtn) throw new Error('No se encontró #addLineaBtn');
        if (!totalFormsInput) throw new Error('No se encontró input de TOTAL_FORMS');
        if (!ordenWrapper) throw new Error('No se encontró #ordenAutocompleteWrapper');
        if (!ordenInput) throw new Error('No se encontró #numero_orden_cliente');
        if (!ordenInfo) throw new Error('No se encontró #ordenInfo');
        if (!ordenInfoTexto) throw new Error('No se encontró #ordenInfoTexto');
        if (!sinOrdenCheckbox) throw new Error('No se encontró #sin_orden_activa');
        if (!ordenClienteContainer) throw new Error('No se encontró #ordenClienteContainer');
        if (!sinOrdenContainer) throw new Error('No se encontró #sinOrdenContainer');
        if (!serviceTagInput) throw new Error('No se encontró #service_tag');
        if (!nombreClienteInput) throw new Error('No se encontró #nombre_cliente');

        this.container = container;
        this.template = template;
        this.addBtn = addBtn;
        this.totalFormsInput = totalFormsInput;
        this.ordenInput = ordenInput;
        this.sinOrdenCheckbox = sinOrdenCheckbox;
        this.ordenClienteContainer = ordenClienteContainer;
        this.sinOrdenContainer = sinOrdenContainer;
        this.serviceTagInput = serviceTagInput;
        this.nombreClienteInput = nombreClienteInput;
        this.imagenesReferenciaCard = imagenesReferenciaCard;
        this.marcaSelect = marcaSelect;
        this.modeloInput = modeloInput;
        this.formCount = parseInt(totalFormsInput.value);

        this.modeloApiUrl = modeloInput?.dataset.apiUrl || '/servicio-tecnico/api/buscar-modelos-por-marca/';
        this.maxImagenes = parseInt(imagenesReferenciaCard?.dataset.max || '6');

        const solicitudForm = document.getElementById('solicitudForm') as HTMLFormElement;
        this.productoAutocomplete = new ProductoAutocompleteManager(solicitudForm);
        this.ordenAutocomplete = new OrdenAutocompleteManager(ordenWrapper, ordenInfo, ordenInfoTexto);

        this.initializeEventListeners();
        this.productoAutocomplete.initAll();
        this.ordenAutocomplete.init();
        this.toggleModoSinOrden();
        this.calcularTotalGeneral();
        this.updateLineNumbers();
    }

    /* =========================================================================
       EVENT LISTENERS — Configuración de todos los listeners
       ========================================================================= */

    private initializeEventListeners(): void {
        this.addBtn.addEventListener('click', () => this.agregarLinea());

        this.container.addEventListener('click', (e: Event) => {
            const target = e.target as HTMLElement;
            const removeBtn = target.closest('.remove-linea-btn') as HTMLElement | null;
            if (removeBtn) {
                const lineaForm = removeBtn.closest('.linea-form') as HTMLElement | null;
                if (lineaForm) this.eliminarLinea(lineaForm);
            }
        });

        this.container.addEventListener('input', (e: Event) => {
            const target = e.target as HTMLElement;
            if (target.matches('[name$="-cantidad"], [name$="-costo_unitario"]')) {
                const lineaForm = target.closest('.linea-form') as HTMLElement | null;
                if (lineaForm) this.calcularSubtotal(lineaForm);
            }
        });

        this.sinOrdenCheckbox.addEventListener('change', () => this.toggleModoSinOrden());

        this.serviceTagInput.addEventListener('input', () => {
            this.serviceTagInput.value = this.serviceTagInput.value.toUpperCase();
        });

        this.initializeImagenesReferencia();
        this.initializeModeloAutocomplete();
    }

    /* =========================================================================
       MODO SIN ORDEN — Toggle entre campos de orden y datos del cliente
       ========================================================================= */

    private toggleModoSinOrden(): void {
        const sinOrden = this.sinOrdenCheckbox.checked;

        if (sinOrden) {
            this.ordenClienteContainer.classList.add('d-none');
            this.sinOrdenContainer.classList.remove('d-none');
            if (this.imagenesReferenciaCard) {
                this.imagenesReferenciaCard.classList.remove('d-none');
            }
            this.ordenInput.removeAttribute('required');
            this.serviceTagInput.setAttribute('required', 'required');
            this.nombreClienteInput.setAttribute('required', 'required');
            this.ordenAutocomplete.limpiar();
        } else {
            this.ordenClienteContainer.classList.remove('d-none');
            this.sinOrdenContainer.classList.add('d-none');
            if (this.imagenesReferenciaCard) {
                this.imagenesReferenciaCard.classList.add('d-none');
            }
            this.ordenInput.setAttribute('required', 'required');
            this.serviceTagInput.removeAttribute('required');
            this.nombreClienteInput.removeAttribute('required');
            this.limpiarCamposCliente();
        }
    }

    private limpiarCamposCliente(): void {
        this.serviceTagInput.value = '';
        this.nombreClienteInput.value = '';
        const telefonoInput = document.getElementById('telefono_cliente') as HTMLInputElement | null;
        const emailInput = document.getElementById('email_cliente') as HTMLInputElement | null;
        if (telefonoInput) telefonoInput.value = '';
        if (emailInput) emailInput.value = '';
        if (this.marcaSelect) this.marcaSelect.value = '';
        if (this.modeloInput) this.modeloInput.value = '';
    }

    /* =========================================================================
       IMÁGENES DE REFERENCIA — Preview y gestión de slots
       ========================================================================= */

    private initializeImagenesReferencia(): void {
        const addSlotBtn = document.getElementById('addImagenSlotBtn');
        if (addSlotBtn) {
            addSlotBtn.addEventListener('click', () => this.agregarSlotImagen());
        }

        const uploadZone = document.getElementById('imagenesUploadZone');
        if (uploadZone) {
            uploadZone.addEventListener('click', (e: Event) => {
                const target = e.target as HTMLElement;
                const removeBtn = target.closest('.remove-imagen-slot') as HTMLElement | null;
                if (removeBtn) {
                    const slot = removeBtn.closest('.imagen-upload-slot') as HTMLElement | null;
                    if (slot) {
                        slot.remove();
                        this.actualizarContadorImagenes();
                    }
                }
            });

            uploadZone.addEventListener('change', (e: Event) => {
                const target = e.target as HTMLInputElement;
                if (target.classList.contains('imagen-ref-input') && target.files) {
                    this.previewImagen(target);
                }
            });
        }
    }

    private agregarSlotImagen(): void {
        const uploadZone = document.getElementById('imagenesUploadZone');
        if (!uploadZone) return;

        const slotsActuales = uploadZone.querySelectorAll('.imagen-upload-slot').length;
        const imagenesExistentes = document.querySelectorAll('#imagenesUploadZone .imagen-ref-input');
        let archivosSeleccionados = 0;
        imagenesExistentes.forEach(input => {
            if ((input as HTMLInputElement).files && (input as HTMLInputElement).files!.length > 0) {
                archivosSeleccionados++;
            }
        });

        if (slotsActuales >= this.maxImagenes) {
            return;
        }

        const slot = document.createElement('div');
        slot.className = 'imagen-upload-slot mb-2';
        slot.innerHTML = `
            <div class="row g-2 align-items-center">
                <div class="col-md-5">
                    <input type="file" name="imagenes_referencia" 
                           class="form-control form-control-sm imagen-ref-input"
                           accept="image/jpeg,image/png,image/gif,image/webp">
                </div>
                <div class="col-md-5">
                    <input type="text" name="descripcion_imagen" 
                           class="form-control form-control-sm"
                           placeholder="Descripción (opcional)" maxlength="200">
                </div>
                <div class="col-md-2">
                    <button type="button" class="btn btn-sm btn-outline-danger remove-imagen-slot" 
                            title="Quitar este slot">
                        <i class="bi bi-x-lg"></i>
                    </button>
                </div>
            </div>
            <div class="imagen-preview mt-1 d-none">
                <img src="" alt="Preview" class="img-thumbnail" style="max-height: 60px;">
            </div>
        `;

        uploadZone.appendChild(slot);

        const newInput = slot.querySelector<HTMLInputElement>('.imagen-ref-input');
        if (newInput) {
            newInput.addEventListener('change', () => {
                if (newInput.files) this.previewImagen(newInput);
            });
        }

        this.actualizarContadorImagenes();
    }

    private previewImagen(input: HTMLInputElement): void {
        const slot = input.closest('.imagen-upload-slot');
        if (!slot) return;

        const previewDiv = slot.querySelector<HTMLElement>('.imagen-preview');
        if (!previewDiv || !input.files || input.files.length === 0) return;

        const file = input.files[0];
        const reader = new FileReader();

        reader.onload = (e: ProgressEvent<FileReader>) => {
            const img = previewDiv.querySelector('img');
            if (img && e.target?.result) {
                img.src = e.target.result as string;
                previewDiv.classList.remove('d-none');
            }
        };

        reader.readAsDataURL(file);
        this.actualizarContadorImagenes();
    }

    private actualizarContadorImagenes(): void {
        const contador = document.getElementById('contadorImagenesRef');
        if (!contador) return;

        const uploadZone = document.getElementById('imagenesUploadZone');
        if (!uploadZone) return;

        const slots = uploadZone.querySelectorAll('.imagen-ref-input');
        let conArchivo = 0;
        slots.forEach(input => {
            if ((input as HTMLInputElement).files && (input as HTMLInputElement).files!.length > 0) {
                conArchivo++;
            }
        });

        const imagenesExistentesEl = document.querySelectorAll('.col-md-2.col-sm-4 .border.rounded');
        const existentes = imagenesExistentesEl.length;

        contador.textContent = `${existentes + conArchivo}/${this.maxImagenes}`;
    }

    /* =========================================================================
       AUTOCOMPLETE DE MODELO — Búsqueda dinámica según marca seleccionada
       ========================================================================= */

    private initializeModeloAutocomplete(): void {
        if (!this.marcaSelect || !this.modeloInput) return;

        this.marcaSelect.addEventListener('change', () => {
            if (this.modeloInput) this.modeloInput.value = '';
        });

        const modeloInput = this.modeloInput;
        const datalistId = 'modelo-datalist';

        let datalist = document.getElementById(datalistId) as HTMLDataListElement | null;
        if (!datalist) {
            datalist = document.createElement('datalist');
            datalist.id = datalistId;
            document.body.appendChild(datalist);
        }
        modeloInput.setAttribute('list', datalistId);

        modeloInput.addEventListener('input', () => {
            if (this.debounceTimer) clearTimeout(this.debounceTimer);

            this.debounceTimer = setTimeout(() => {
                this.buscarModelos();
            }, 300);
        });

        modeloInput.addEventListener('focus', () => {
            this.buscarModelos();
        });
    }

    private buscarModelos(): void {
        if (!this.marcaSelect || !this.modeloInput) return;

        const marca = this.marcaSelect.value;
        const termino = this.modeloInput.value.trim();

        if (!marca) return;

        const url = `${this.modeloApiUrl}?marca=${encodeURIComponent(marca)}&q=${encodeURIComponent(termino)}`;

        fetch(url)
            .then(response => response.json())
            .then((data: ModeloResponse) => {
                const datalist = document.getElementById('modelo-datalist') as HTMLDataListElement;
                if (!datalist) return;

                datalist.innerHTML = '';

                if (data.results && data.results.length > 0) {
                    data.results.forEach(resultado => {
                        const option = document.createElement('option');
                        option.value = resultado.id;
                        if (resultado.gama) {
                            option.label = `${resultado.id} (${resultado.gama})`;
                        }
                        datalist.appendChild(option);
                    });
                }
            })
            .catch(error => {
                console.error('Error buscando modelos:', error);
            });
    }

    /* =========================================================================
       GESTIÓN DE LÍNEAS — Agregar, eliminar y reindexar
       ========================================================================= */

    private agregarLinea(): void {
        const newForm = this.template.content.cloneNode(true) as DocumentFragment;
        const formHtml = newForm.querySelector('.linea-form');

        if (!formHtml) {
            console.error('No se encontró .linea-form en el template');
            return;
        }

        formHtml.innerHTML = formHtml.innerHTML.replace(/__prefix__/g, this.formCount.toString());

        this.container.appendChild(newForm);

        const nuevaLinea = this.container.lastElementChild as HTMLElement | null;
        if (nuevaLinea) {
            const wrapper = nuevaLinea.querySelector<HTMLElement>('.producto-autocomplete');
            if (wrapper) this.productoAutocomplete.initWrapper(wrapper);
        }

        this.formCount++;
        this.totalFormsInput.value = this.formCount.toString();

        this.updateLineNumbers();
        this.calcularTotalGeneral();
    }

    private eliminarLinea(lineaForm: HTMLElement): void {
        const deleteCheckbox = lineaForm.querySelector<HTMLInputElement>('input[name$="-DELETE"]');

        if (deleteCheckbox) {
            this.marcarLineaComoEliminada(lineaForm, deleteCheckbox);
        } else {
            this.removerLineaNueva(lineaForm);
        }
    }

    private marcarLineaComoEliminada(lineaForm: HTMLElement, checkbox: HTMLInputElement): void {
        if (checkbox.checked) {
            checkbox.checked = false;
            lineaForm.style.opacity = '1';
            lineaForm.classList.remove('linea-eliminada');

            const wasRequired = lineaForm.querySelectorAll<HTMLElement>('[data-was-required="true"]');
            wasRequired.forEach(field => {
                field.setAttribute('required', 'required');
                field.removeAttribute('data-was-required');
            });
        } else {
            checkbox.checked = true;
            lineaForm.style.opacity = '0.4';
            lineaForm.classList.add('linea-eliminada');

            const requiredFields = lineaForm.querySelectorAll<HTMLElement>('[required]');
            requiredFields.forEach(field => {
                field.removeAttribute('required');
                field.setAttribute('data-was-required', 'true');
            });
        }

        this.updateLineNumbers();
        this.calcularTotalGeneral();
    }

    private removerLineaNueva(lineaForm: HTMLElement): void {
        lineaForm.remove();
        this.reindexarFormularios();
        this.updateLineNumbers();
        this.calcularTotalGeneral();
    }

    private reindexarFormularios(): void {
        const lineas = this.container.querySelectorAll<HTMLElement>('.linea-form');
        let nuevoIndice = 0;

        lineas.forEach(linea => {
            const deleteCheckbox = linea.querySelector<HTMLInputElement>('input[name$="-DELETE"]');
            if (deleteCheckbox && deleteCheckbox.checked) {
                return;
            }

            const indiceActual = this.obtenerIndiceDeLinea(linea);
            if (indiceActual === null) return;

            if (indiceActual !== nuevoIndice) {
                this.reemplazarIndiceEnLinea(linea, indiceActual, nuevoIndice);
            }

            nuevoIndice++;
        });

        this.formCount = nuevoIndice;
        this.totalFormsInput.value = this.formCount.toString();
    }

    private obtenerIndiceDeLinea(linea: HTMLElement): number | null {
        const campo = linea.querySelector<HTMLElement>('[name^="lineas-"]');
        if (!campo) return null;

        const name = campo.getAttribute('name') || '';
        const match = name.match(/^lineas-(\d+)-/);
        return match ? parseInt(match[1]) : null;
    }

    private reemplazarIndiceEnLinea(linea: HTMLElement, indiceViejo: number, indiceNuevo: number): void {
        const viejo = `lineas-${indiceViejo}-`;
        const nuevo = `lineas-${indiceNuevo}-`;

        const campos = linea.querySelectorAll<HTMLElement>('[name], [id], [for]');
        campos.forEach(campo => {
            const name = campo.getAttribute('name');
            if (name && name.includes(viejo)) {
                campo.setAttribute('name', name.replace(viejo, nuevo));
            }

            const id = campo.getAttribute('id');
            if (id && id.includes(viejo)) {
                campo.setAttribute('id', id.replace(viejo, nuevo));
            }

            const htmlFor = campo.getAttribute('for');
            if (htmlFor && htmlFor.includes(viejo)) {
                campo.setAttribute('for', htmlFor.replace(viejo, nuevo));
            }
        });
    }

    /* =========================================================================
       NÚMEROS DE LÍNEA — Actualización visual de la numeración
       ========================================================================= */

    private updateLineNumbers(): void {
        const lineas = this.container.querySelectorAll<HTMLElement>('.linea-form');
        let numero = 1;

        lineas.forEach(linea => {
            const deleteCheckbox = linea.querySelector<HTMLInputElement>('input[name$="-DELETE"]');
            const isDeleted = deleteCheckbox?.checked || false;

            if (!isDeleted) {
                const lineaNumero = linea.querySelector<HTMLElement>('.linea-numero');
                if (lineaNumero) {
                    lineaNumero.textContent = numero.toString();
                }
                numero++;
            }
        });

        this.actualizarContadorLineasActivas();
    }

    /** Actualiza el contador de líneas activas en el sidebar */
    private actualizarContadorLineasActivas(): void {
        const el = document.getElementById('lineasActivasCount');
        if (!el) return;

        const lineas = this.container.querySelectorAll<HTMLElement>('.linea-form');
        let activas = 0;
        lineas.forEach((linea) => {
            const deleteCheckbox = linea.querySelector<HTMLInputElement>('input[name$="-DELETE"]');
            if (!deleteCheckbox?.checked) activas++;
        });
        el.textContent = String(activas);
    }

    /* =========================================================================
       CÁLCULOS — Subtotales por línea y total general
       ========================================================================= */

    private calcularSubtotal(lineaForm: HTMLElement): void {
        const cantidadInput = lineaForm.querySelector<HTMLInputElement>('[name$="-cantidad"]');
        const costoInput = lineaForm.querySelector<HTMLInputElement>('[name$="-costo_unitario"]');
        const subtotalEl = lineaForm.querySelector<HTMLElement>('.subtotal-linea');

        if (cantidadInput && costoInput && subtotalEl) {
            const cantidad = parseFloat(cantidadInput.value) || 0;
            const costo = parseFloat(costoInput.value) || 0;
            const subtotal = cantidad * costo;
            subtotalEl.textContent = '$' + subtotal.toFixed(2);
        }

        this.calcularTotalGeneral();
    }

    private calcularTotalGeneral(): void {
        let total = 0;
        const lineas = this.container.querySelectorAll<HTMLElement>('.linea-form');

        lineas.forEach(linea => {
            const deleteCheckbox = linea.querySelector<HTMLInputElement>('input[name$="-DELETE"]');
            if (deleteCheckbox?.checked) return;

            const cantidadInput = linea.querySelector<HTMLInputElement>('[name$="-cantidad"]');
            const costoInput = linea.querySelector<HTMLInputElement>('[name$="-costo_unitario"]');

            if (cantidadInput && costoInput) {
                const cantidad = parseFloat(cantidadInput.value) || 0;
                const costo = parseFloat(costoInput.value) || 0;
                total += cantidad * costo;
            }
        });

        const totalEl = document.getElementById('totalGeneral');
        if (totalEl) {
            totalEl.textContent = '$' + total.toFixed(2);
        }
    }
}

/* =============================================================================
   INICIALIZACIÓN — Se ejecuta cuando el DOM está listo
   ============================================================================= */

document.addEventListener('DOMContentLoaded', () => {
    try {
        if (document.getElementById('solicitudForm')) {
            const manager = new FormSolicitudCotizacionManager();
            // @ts-ignore — Exposición para debugging en consola del navegador
            window.formSolicitudManager = manager;
            console.log('✅ FormSolicitudCotizacionManager inicializado correctamente');
        }
    } catch (error) {
        console.error('❌ Error al inicializar FormSolicitudCotizacionManager:', error);
    }
});
