/**
 * TypeScript para Formulario de Compra Directa (Almacén)
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * --------------------------------
 * Este archivo maneja la lógica de un formset de Django, que es un conjunto
 * de formularios dinámicos que se pueden agregar/eliminar desde el navegador.
 *
 * Funcionalidades principales:
 * 1. Agregar nuevas unidades de compra dinámicamente
 * 2. Eliminar/desactivar unidades de compra
 * 3. Actualizar números de línea secuenciales automáticamente
 * 4. Validar que la suma de cantidades = cantidad total de la compra
 * 5. Calcular costo promedio ponderado automáticamente
 * 6. Mostrar costo total y resumen en el sidebar sticky
 * 7. Autocompletado AJAX del producto (código o nombre)
 */

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

/**
 * Autocompletado de producto — misma lógica que cotizaciones/solicitudes.
 */
class ProductoAutocompleteCompra {
    private readonly apiBuscarUrl: string;
    private readonly apiInfoUrlTemplate: string;
    private readonly stockInfo: HTMLElement | null;
    private readonly debounceMs = 300;
    private readonly minChars = 2;

    constructor(form: HTMLFormElement) {
        this.apiBuscarUrl = form.dataset.apiBuscarProductos || '';
        this.apiInfoUrlTemplate = form.dataset.apiInfoProducto || '';
        this.stockInfo = document.getElementById('stock-info');
    }

    public init(): void {
        const wrapper = document.getElementById('producto-autocomplete-wrapper');
        if (!wrapper || wrapper.dataset.autocompleteInit === '1') return;

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

        const actualizarStockInfo = (stock: number, costo: number): void => {
            if (!this.stockInfo) return;
            const stockClass = stock === 0 ? 'text-danger' : 'text-muted';
            this.stockInfo.innerHTML = `Stock actual: <strong class="${stockClass}">${stock}</strong> · Último costo: $${costo.toFixed(2)}`;
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
                const stockClass = prod.stock === 0 ? 'text-danger' : 'text-muted';
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
            textoSeleccionado = textInput.value;
            marcarInvalido(false);
            cerrarDropdown();
            actualizarStockInfo(prod.stock, prod.costo);
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

        const cargarProductoInicial = async (productoId: string): Promise<void> => {
            if (!this.apiInfoUrlTemplate || !productoId) return;

            const infoUrl = this.apiInfoUrlTemplate.replace('/0/', `/${productoId}/`);
            try {
                const resp = await fetch(infoUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
                if (!resp.ok) return;
                const data: ProductoInfoResponse = await resp.json();
                if (!data.success || !data.producto) return;

                textInput.value = `${data.producto.codigo} — ${data.producto.nombre}`;
                textoSeleccionado = textInput.value;
                actualizarStockInfo(data.producto.stock, data.producto.costo);
            } catch {
                // Fail-safe: no bloquear si falla la carga inicial
            }
        };

        textInput.addEventListener('input', () => {
            const valor = textInput.value.trim();
            if (valor !== textoSeleccionado) {
                hiddenInput.value = '';
                marcarInvalido(false);
                if (this.stockInfo) this.stockInfo.innerHTML = '';
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

        // Edición o POST con error: hidratar etiqueta si hay ID pero el texto está vacío
        if (hiddenInput.value && !textInput.value.trim()) {
            void cargarProductoInicial(hiddenInput.value);
        } else if (hiddenInput.value && textInput.value.trim()) {
            void cargarProductoInicial(hiddenInput.value);
        }
    }
}

interface UnidadCompraData {
    numeroLinea: number;
    cantidad: number;
    marca: string;
    modelo: string;
    numeroSerie: string;
    costoUnitario: number;
    especificaciones: string;
    eliminada: boolean;
}

interface ValidationSummary {
    cantidadTotal: number;
    sumaUnidades: number;
    costoPromedio: number;
    costoTotal: number;
    isValid: boolean;
    lineasValidas: number;
    lineasActivas: number;
    errores: string[];
}

class FormCompraManager {
    private container: HTMLElement;
    private template: HTMLTemplateElement;
    private addBtn: HTMLElement;
    private totalFormsInput: HTMLInputElement;
    private cantidadTotalInput: HTMLInputElement;
    private costoPromedioInput: HTMLInputElement;
    private costoTotalDisplay: HTMLInputElement | null;
    private validacionResumen: HTMLElement | null;
    private lineasActivasCount: HTMLElement | null;
    private submitBtns: NodeListOf<HTMLButtonElement>;
    private formCount: number;

    constructor() {
        const container = document.getElementById('unidadesContainer');
        const template = document.getElementById('unidadTemplate') as HTMLTemplateElement;
        const addBtn = document.getElementById('addUnidadBtn');
        const totalFormsInput = document.querySelector<HTMLInputElement>('[name="unidades-TOTAL_FORMS"]');
        const cantidadTotalInput = document.querySelector<HTMLInputElement>('[name="cantidad"]');
        const costoPromedioInput = document.querySelector<HTMLInputElement>('[name="costo_unitario"]');
        const costoTotalDisplay = document.getElementById('costoTotalDisplay') as HTMLInputElement | null;
        const validacionResumen = document.getElementById('validacionResumen');
        const lineasActivasCount = document.getElementById('lineasActivasCount');
        const submitBtns = document.querySelectorAll<HTMLButtonElement>('.btn-submit-compra');

        if (!container) throw new Error('No se encontró #unidadesContainer');
        if (!template) throw new Error('No se encontró #unidadTemplate');
        if (!addBtn) throw new Error('No se encontró #addUnidadBtn');
        if (!totalFormsInput) throw new Error('No se encontró input de TOTAL_FORMS');
        if (!cantidadTotalInput) throw new Error('No se encontró input de cantidad total');
        if (!costoPromedioInput) throw new Error('No se encontró input de costo_unitario');

        this.container = container;
        this.template = template;
        this.addBtn = addBtn;
        this.totalFormsInput = totalFormsInput;
        this.cantidadTotalInput = cantidadTotalInput;
        this.costoPromedioInput = costoPromedioInput;
        this.costoTotalDisplay = costoTotalDisplay;
        this.validacionResumen = validacionResumen;
        this.lineasActivasCount = lineasActivasCount;
        this.submitBtns = submitBtns;
        this.formCount = parseInt(totalFormsInput.value, 10);

        this.initializeEventListeners();
        this.updateLineNumbers();
        this.recalcularTodo();
    }

    private initializeEventListeners(): void {
        this.addBtn.addEventListener('click', () => this.addNewUnidad());

        this.container.querySelectorAll<HTMLElement>('.remove-unidad-btn').forEach((btn) => {
            btn.addEventListener('click', (e) => this.removeUnidad(e));
        });

        this.container.addEventListener('input', (e) => {
            const target = e.target as HTMLElement;
            if (
                target.classList.contains('cantidad-input') ||
                target.classList.contains('costo-unidad-input') ||
                target.matches('input[name$="-cantidad"]') ||
                target.matches('input[name$="-costo_unitario"]')
            ) {
                this.recalcularTodo();
            }
        });

        this.container.addEventListener('change', (e) => {
            const target = e.target as HTMLInputElement;
            if (target.type === 'checkbox' && target.name.endsWith('-DELETE')) {
                this.recalcularTodo();
            }
            if (target.matches('select[name$="-marca"]')) {
                this.recalcularTodo();
            }
        });

        this.cantidadTotalInput.addEventListener('input', () => {
            this.recalcularTodo();
        });
    }

    private addNewUnidad(): void {
        const newForm = this.template.content.cloneNode(true) as DocumentFragment;
        const formHtml = newForm.querySelector('.unidad-form');

        if (!formHtml) {
            console.error('No se encontró .unidad-form en el template');
            return;
        }

        formHtml.innerHTML = formHtml.innerHTML.replace(/__prefix__/g, this.formCount.toString());
        this.container.appendChild(newForm);

        this.formCount++;
        this.totalFormsInput.value = this.formCount.toString();

        this.updateLineNumbers();
        this.recalcularTodo();

        const lastForm = this.container.lastElementChild;
        if (lastForm) {
            const removeBtn = lastForm.querySelector<HTMLElement>('.remove-unidad-btn');
            if (removeBtn) {
                removeBtn.addEventListener('click', (e) => this.removeUnidad(e));
            }
        }
    }

    private removeUnidad(event: Event): void {
        const target = event.target as HTMLElement;
        const button = target.closest('.remove-unidad-btn') as HTMLElement;
        const unidadForm = button?.closest('.unidad-form') as HTMLElement;

        if (!unidadForm) return;

        const deleteCheckbox = unidadForm.querySelector<HTMLInputElement>('input[name$="-DELETE"]');

        if (deleteCheckbox) {
            if (deleteCheckbox.checked) {
                deleteCheckbox.checked = false;

                const wasRequiredFields = unidadForm.querySelectorAll<HTMLInputElement>('[data-was-required="true"]');
                wasRequiredFields.forEach((field) => {
                    field.setAttribute('required', 'required');
                    field.removeAttribute('data-was-required');
                });

                unidadForm.classList.remove('unidad-desactivada');

                button.innerHTML = '<i class="bi bi-eye-slash"></i> Desactivar';
                button.classList.remove('btn-outline-success');
                button.classList.add('btn-outline-secondary');
            } else {
                deleteCheckbox.checked = true;

                const requiredFields = unidadForm.querySelectorAll<HTMLInputElement>('[required]');
                requiredFields.forEach((field) => {
                    field.removeAttribute('required');
                    field.setAttribute('data-was-required', 'true');
                });

                unidadForm.classList.add('unidad-desactivada');

                button.innerHTML = '<i class="bi bi-eye"></i> Reactivar';
                button.classList.remove('btn-outline-secondary');
                button.classList.add('btn-outline-success');
            }
        } else {
            unidadForm.remove();
            this.formCount = Math.max(0, this.formCount - 1);
            this.totalFormsInput.value = this.formCount.toString();
        }

        this.updateLineNumbers();
        this.recalcularTodo();
    }

    private updateLineNumbers(): void {
        const forms = this.container.querySelectorAll<HTMLElement>('.unidad-form');
        let lineNumber = 1;

        forms.forEach((form) => {
            const deleteCheckbox = form.querySelector<HTMLInputElement>('input[name$="-DELETE"]');
            const isDeleted = deleteCheckbox?.checked || false;

            if (!isDeleted) {
                const lineInput = form.querySelector<HTMLInputElement>('input[name$="-numero_linea"]');
                if (lineInput) {
                    lineInput.value = lineNumber.toString();
                }

                const numeroVisible = form.querySelector<HTMLElement>('.unidad-numero');
                if (numeroVisible) {
                    numeroVisible.textContent = lineNumber.toString();
                }

                lineNumber++;
            }
        });
    }

    private getUnidadesValidas(): UnidadCompraData[] {
        const unidades: UnidadCompraData[] = [];
        const forms = this.container.querySelectorAll<HTMLElement>('.unidad-form');

        forms.forEach((form) => {
            const deleteCheckbox = form.querySelector<HTMLInputElement>('input[name$="-DELETE"]');
            const isDeleted = deleteCheckbox?.checked || false;

            if (!isDeleted) {
                const cantidadInput = form.querySelector<HTMLInputElement>('input[name$="-cantidad"]');
                const costoInput = form.querySelector<HTMLInputElement>('input[name$="-costo_unitario"]');
                const marcaSelect = form.querySelector<HTMLSelectElement>('select[name$="-marca"]');
                const modeloInput = form.querySelector<HTMLInputElement>('input[name$="-modelo"]');

                const cantidad = parseInt(cantidadInput?.value || '0', 10) || 0;
                const costo = parseFloat(costoInput?.value || '0') || 0;

                unidades.push({
                    numeroLinea: unidades.length + 1,
                    cantidad,
                    marca: marcaSelect?.value || '',
                    modelo: modeloInput?.value || '',
                    numeroSerie: '',
                    costoUnitario: costo,
                    especificaciones: '',
                    eliminada: false,
                });
            }
        });

        return unidades;
    }

    private calcularResumen(): ValidationSummary {
        const cantidadTotal = parseInt(this.cantidadTotalInput.value, 10) || 0;
        const unidades = this.getUnidadesValidas();

        let sumaUnidades = 0;
        let sumaCostos = 0;
        let lineasValidas = 0;
        const errores: string[] = [];

        unidades.forEach((unidad, index) => {
            sumaUnidades += unidad.cantidad;

            if (unidad.cantidad > 0 && unidad.costoUnitario > 0) {
                sumaCostos += unidad.cantidad * unidad.costoUnitario;
                lineasValidas++;
            }

            if (unidad.cantidad > 0) {
                if (!unidad.marca) {
                    errores.push(`Línea ${index + 1}: Falta la marca`);
                }
                if (unidad.costoUnitario <= 0) {
                    errores.push(`Línea ${index + 1}: Falta el costo`);
                }
            }
        });

        const costoPromedio = sumaUnidades > 0 ? sumaCostos / sumaUnidades : 0;
        const costoTotal = cantidadTotal * costoPromedio;

        if (sumaUnidades > 0 && sumaUnidades !== cantidadTotal) {
            errores.push(`Suma de unidades (${sumaUnidades}) ≠ cantidad total (${cantidadTotal})`);
        }

        if (lineasValidas === 0) {
            errores.push('Debes agregar al menos una línea con marca y costo');
        }

        const isValid = errores.length === 0 && lineasValidas > 0 && sumaUnidades === cantidadTotal;

        return {
            cantidadTotal,
            sumaUnidades,
            costoPromedio,
            costoTotal,
            isValid,
            lineasValidas,
            lineasActivas: unidades.length,
            errores,
        };
    }

    private recalcularTodo(): void {
        const resumen = this.calcularResumen();

        this.costoPromedioInput.value = resumen.costoPromedio.toFixed(2);

        if (this.costoTotalDisplay) {
            this.costoTotalDisplay.value = resumen.costoTotal.toFixed(2);
        }

        if (this.lineasActivasCount) {
            this.lineasActivasCount.textContent = resumen.lineasActivas.toString();
        }

        this.actualizarResumenVisual(resumen);
    }

    private actualizarResumenVisual(resumen: ValidationSummary): void {
        if (!this.validacionResumen) return;

        this.validacionResumen.style.display = 'block';

        const cantidadDisplay = document.getElementById('cantidadTotalDisplay');
        const sumaDisplay = document.getElementById('sumaUnidadesDisplay');
        const estadoDisplay = document.getElementById('estadoValidacionDisplay');

        if (cantidadDisplay) cantidadDisplay.textContent = resumen.cantidadTotal.toString();
        if (sumaDisplay) sumaDisplay.textContent = resumen.sumaUnidades.toString();

        let alertClass = 'form-compra-validacion alert alert-warning mb-0';

        if (estadoDisplay) {
            if (resumen.isValid) {
                estadoDisplay.innerHTML = '<span class="badge bg-success">✓ Válido</span>';
                alertClass = 'form-compra-validacion alert alert-success mb-0';
            } else if (resumen.sumaUnidades === 0) {
                estadoDisplay.innerHTML = '<span class="badge bg-warning">⚠ Agrega líneas</span>';
            } else if (resumen.sumaUnidades !== resumen.cantidadTotal) {
                const diff = resumen.cantidadTotal - resumen.sumaUnidades;
                const msg = diff > 0 ? `Faltan ${diff}` : `Sobran ${Math.abs(diff)}`;
                estadoDisplay.innerHTML = `<span class="badge bg-danger">✗ ${msg}</span>`;
                alertClass = 'form-compra-validacion alert alert-danger mb-0';
            } else {
                estadoDisplay.innerHTML = '<span class="badge bg-warning">⚠ Revisa los campos</span>';
            }
        }

        this.validacionResumen.className = alertClass;

        this.submitBtns.forEach((btn) => {
            btn.classList.toggle('btn-primary', resumen.isValid);
            btn.classList.toggle('btn-warning', !resumen.isValid);
        });
    }

    public getResumen(): ValidationSummary {
        return this.calcularResumen();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    try {
        const compraForm = document.getElementById('compraForm') as HTMLFormElement | null;
        if (compraForm) {
            const productoAutocomplete = new ProductoAutocompleteCompra(compraForm);
            productoAutocomplete.init();

            const formManager = new FormCompraManager();
            (window as Window & { formCompraManager?: FormCompraManager }).formCompraManager = formManager;
            console.log('✅ FormCompraManager inicializado correctamente');
        }
    } catch (error) {
        console.error('❌ Error al inicializar FormCompraManager:', error);
    }
});
