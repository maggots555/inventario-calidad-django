"use strict";
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
 * 2. Eliminar unidades de compra
 * 3. Actualizar números de línea secuenciales automáticamente
 * 4. Validar que la suma de cantidades = cantidad total de la compra
 * 5. CALCULAR COSTO PROMEDIO PONDERADO automáticamente
 * 6. Mostrar costo total en tiempo real
 *
 * NUEVO FLUJO:
 * - El usuario DEBE agregar al menos una línea de detalle
 * - Cada línea DEBE tener marca y costo
 * - La suma de cantidades DEBE coincidir con la cantidad total
 * - El costo unitario promedio se CALCULA automáticamente
 */
/**
 * Clase principal que maneja el formulario de compra
 */
class FormCompraManager {
    /**
     * Constructor: Se ejecuta cuando se crea una instancia de la clase
     */
    constructor() {
        // Buscar elementos en el DOM
        const container = document.getElementById('unidadesContainer');
        const template = document.getElementById('unidadTemplate');
        const addBtn = document.getElementById('addUnidadBtn');
        const totalFormsInput = document.querySelector('[name="unidades-TOTAL_FORMS"]');
        const cantidadTotalInput = document.querySelector('[name="cantidad"]');
        const costoPromedioInput = document.querySelector('[name="costo_unitario"]');
        const costoTotalDisplay = document.getElementById('costoTotalDisplay');
        const validacionResumen = document.getElementById('validacionResumen');
        const submitBtn = document.getElementById('submitBtn');
        // Validar que todos los elementos existen
        if (!container)
            throw new Error('No se encontró #unidadesContainer');
        if (!template)
            throw new Error('No se encontró #unidadTemplate');
        if (!addBtn)
            throw new Error('No se encontró #addUnidadBtn');
        if (!totalFormsInput)
            throw new Error('No se encontró input de TOTAL_FORMS');
        if (!cantidadTotalInput)
            throw new Error('No se encontró input de cantidad total');
        if (!costoPromedioInput)
            throw new Error('No se encontró input de costo_unitario');
        // Asignar a las propiedades
        this.container = container;
        this.template = template;
        this.addBtn = addBtn;
        this.totalFormsInput = totalFormsInput;
        this.cantidadTotalInput = cantidadTotalInput;
        this.costoPromedioInput = costoPromedioInput;
        this.costoTotalDisplay = costoTotalDisplay;
        this.validacionResumen = validacionResumen;
        this.submitBtn = submitBtn;
        this.formCount = parseInt(totalFormsInput.value);
        // Inicializar eventos
        this.initializeEventListeners();
        this.updateLineNumbers();
        this.recalcularTodo();
    }
    /**
     * Configura todos los event listeners
     */
    initializeEventListeners() {
        // Botón para agregar nueva unidad
        this.addBtn.addEventListener('click', () => this.addNewUnidad());
        // Botones de eliminar existentes
        this.container.querySelectorAll('.remove-unidad-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.removeUnidad(e));
        });
        // Escuchar cambios en inputs de cantidad y costo
        this.container.addEventListener('input', (e) => {
            const target = e.target;
            if (target.classList.contains('cantidad-input') ||
                target.classList.contains('costo-unidad-input')) {
                this.recalcularTodo();
            }
        });
        // Escuchar cambios en checkboxes de DELETE
        this.container.addEventListener('change', (e) => {
            const target = e.target;
            if (target.type === 'checkbox' && target.name.endsWith('-DELETE')) {
                this.recalcularTodo();
            }
        });
        // Escuchar cambios en la cantidad total
        this.cantidadTotalInput.addEventListener('input', () => {
            this.recalcularTodo();
        });
    }
    /**
     * Agrega una nueva línea de UnidadCompra
     */
    addNewUnidad() {
        const newForm = this.template.content.cloneNode(true);
        const formHtml = newForm.querySelector('.unidad-form');
        if (!formHtml) {
            console.error('No se encontró .unidad-form en el template');
            return;
        }
        // Reemplazar __prefix__ con el índice actual
        formHtml.innerHTML = formHtml.innerHTML.replace(/__prefix__/g, this.formCount.toString());
        // Agregar al contenedor
        this.container.appendChild(newForm);
        // Incrementar contador
        this.formCount++;
        this.totalFormsInput.value = this.formCount.toString();
        // Actualizar interfaz
        this.updateLineNumbers();
        this.recalcularTodo();
        // Agregar listeners al nuevo formulario
        const lastForm = this.container.lastElementChild;
        if (lastForm) {
            const removeBtn = lastForm.querySelector('.remove-unidad-btn');
            if (removeBtn) {
                removeBtn.addEventListener('click', (e) => this.removeUnidad(e));
            }
            // Listeners para recálculo en tiempo real
            const cantidadInput = lastForm.querySelector('.cantidad-input');
            const costoInput = lastForm.querySelector('.costo-unidad-input');
            if (cantidadInput) {
                cantidadInput.addEventListener('input', () => this.recalcularTodo());
            }
            if (costoInput) {
                costoInput.addEventListener('input', () => this.recalcularTodo());
            }
        }
    }
    /**
     * Maneja el toggle de activar/desactivar una línea
     */
    removeUnidad(event) {
        const target = event.target;
        const button = target.closest('.remove-unidad-btn');
        const unidadForm = button === null || button === void 0 ? void 0 : button.closest('.unidad-form');
        if (!unidadForm)
            return;
        // Buscar el checkbox DELETE
        const deleteCheckbox = unidadForm.querySelector('input[name$="-DELETE"]');
        if (deleteCheckbox) {
            // Toggle: si está marcado, desmarcar; si no, marcar
            if (deleteCheckbox.checked) {
                // REACTIVAR
                deleteCheckbox.checked = false;
                // Restaurar required a los campos que lo tenían
                const wasRequiredFields = unidadForm.querySelectorAll('[data-was-required="true"]');
                wasRequiredFields.forEach(field => {
                    field.setAttribute('required', 'required');
                    field.removeAttribute('data-was-required');
                });
                // Restaurar apariencia
                unidadForm.style.opacity = '1';
                unidadForm.style.backgroundColor = '';
                // Cambiar botón a "Desactivar"
                button.innerHTML = '<i class="bi bi-eye-slash"></i> Desactivar';
                button.classList.remove('btn-outline-success');
                button.classList.add('btn-outline-secondary');
            }
            else {
                // DESACTIVAR
                deleteCheckbox.checked = true;
                // Quitar required de todos los campos para que no valide
                const requiredFields = unidadForm.querySelectorAll('[required]');
                requiredFields.forEach(field => {
                    field.removeAttribute('required');
                    field.setAttribute('data-was-required', 'true');
                });
                // Ocultar visualmente la línea
                unidadForm.style.opacity = '0.5';
                unidadForm.style.backgroundColor = '#f8f9fa';
                // Cambiar el botón a "Reactivar"
                button.innerHTML = '<i class="bi bi-eye"></i> Reactivar';
                button.classList.remove('btn-outline-secondary');
                button.classList.add('btn-outline-success');
            }
        }
        else {
            // Si no tiene DELETE (nuevas líneas), simplemente remover del DOM
            unidadForm.remove();
        }
        this.updateLineNumbers();
        this.recalcularTodo();
    }
    /**
     * Actualiza los números de línea secuenciales
     */
    updateLineNumbers() {
        const forms = this.container.querySelectorAll('.unidad-form');
        let lineNumber = 1;
        forms.forEach(form => {
            // Verificar si está marcada para eliminar
            const deleteCheckbox = form.querySelector('input[name$="-DELETE"]');
            const isDeleted = (deleteCheckbox === null || deleteCheckbox === void 0 ? void 0 : deleteCheckbox.checked) || false;
            if (!isDeleted) {
                const lineInput = form.querySelector('input[name$="-numero_linea"]');
                if (lineInput) {
                    lineInput.value = lineNumber.toString();
                }
                lineNumber++;
            }
        });
    }
    /**
     * Obtiene los datos de todas las unidades válidas (no eliminadas)
     */
    getUnidadesValidas() {
        const unidades = [];
        const forms = this.container.querySelectorAll('.unidad-form');
        forms.forEach(form => {
            const deleteCheckbox = form.querySelector('input[name$="-DELETE"]');
            const isDeleted = (deleteCheckbox === null || deleteCheckbox === void 0 ? void 0 : deleteCheckbox.checked) || false;
            if (!isDeleted) {
                const cantidadInput = form.querySelector('input[name$="-cantidad"]');
                const costoInput = form.querySelector('input[name$="-costo_unitario"]');
                const marcaSelect = form.querySelector('select[name$="-marca"]');
                const modeloInput = form.querySelector('input[name$="-modelo"]');
                const cantidad = parseInt((cantidadInput === null || cantidadInput === void 0 ? void 0 : cantidadInput.value) || '0') || 0;
                const costo = parseFloat((costoInput === null || costoInput === void 0 ? void 0 : costoInput.value) || '0') || 0;
                unidades.push({
                    numeroLinea: unidades.length + 1,
                    cantidad: cantidad,
                    marca: (marcaSelect === null || marcaSelect === void 0 ? void 0 : marcaSelect.value) || '',
                    modelo: (modeloInput === null || modeloInput === void 0 ? void 0 : modeloInput.value) || '',
                    numeroSerie: '',
                    costoUnitario: costo,
                    especificaciones: '',
                    eliminada: false
                });
            }
        });
        return unidades;
    }
    /**
     * Calcula el resumen de validación completo
     */
    calcularResumen() {
        const cantidadTotal = parseInt(this.cantidadTotalInput.value) || 0;
        const unidades = this.getUnidadesValidas();
        let sumaUnidades = 0;
        let sumaCostos = 0;
        let lineasValidas = 0;
        const errores = [];
        unidades.forEach((unidad, index) => {
            sumaUnidades += unidad.cantidad;
            if (unidad.cantidad > 0 && unidad.costoUnitario > 0) {
                sumaCostos += unidad.cantidad * unidad.costoUnitario;
                lineasValidas++;
            }
            // Validaciones por línea
            if (unidad.cantidad > 0) {
                if (!unidad.marca) {
                    errores.push(`Línea ${index + 1}: Falta la marca`);
                }
                if (unidad.costoUnitario <= 0) {
                    errores.push(`Línea ${index + 1}: Falta el costo`);
                }
            }
        });
        // Calcular costo promedio ponderado
        const costoPromedio = sumaUnidades > 0 ? sumaCostos / sumaUnidades : 0;
        const costoTotal = cantidadTotal * costoPromedio;
        // Validación de cantidad
        if (sumaUnidades > 0 && sumaUnidades !== cantidadTotal) {
            errores.push(`Suma de unidades (${sumaUnidades}) ≠ cantidad total (${cantidadTotal})`);
        }
        // Validación de mínimo
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
            errores
        };
    }
    /**
     * Recalcula todo y actualiza la interfaz
     */
    recalcularTodo() {
        const resumen = this.calcularResumen();
        // Actualizar campo de costo promedio (readonly)
        this.costoPromedioInput.value = resumen.costoPromedio.toFixed(2);
        // Actualizar costo total
        if (this.costoTotalDisplay) {
            this.costoTotalDisplay.value = resumen.costoTotal.toFixed(2);
        }
        // Mostrar/actualizar resumen de validación
        this.actualizarResumenVisual(resumen);
    }
    /**
     * Actualiza el resumen visual de validación
     */
    actualizarResumenVisual(resumen) {
        if (!this.validacionResumen)
            return;
        // Mostrar el panel de resumen
        this.validacionResumen.style.display = 'block';
        // Actualizar valores
        const cantidadDisplay = document.getElementById('cantidadTotalDisplay');
        const sumaDisplay = document.getElementById('sumaUnidadesDisplay');
        const estadoDisplay = document.getElementById('estadoValidacionDisplay');
        if (cantidadDisplay)
            cantidadDisplay.textContent = resumen.cantidadTotal.toString();
        if (sumaDisplay)
            sumaDisplay.textContent = resumen.sumaUnidades.toString();
        if (estadoDisplay) {
            if (resumen.isValid) {
                estadoDisplay.innerHTML = '<span class="badge bg-success">✓ Válido</span>';
                this.validacionResumen.className = 'alert alert-success mb-3';
            }
            else if (resumen.sumaUnidades === 0) {
                estadoDisplay.innerHTML = '<span class="badge bg-warning">⚠ Agrega líneas</span>';
                this.validacionResumen.className = 'alert alert-warning mb-3';
            }
            else if (resumen.sumaUnidades !== resumen.cantidadTotal) {
                const diff = resumen.cantidadTotal - resumen.sumaUnidades;
                const msg = diff > 0 ? `Faltan ${diff}` : `Sobran ${Math.abs(diff)}`;
                estadoDisplay.innerHTML = `<span class="badge bg-danger">✗ ${msg}</span>`;
                this.validacionResumen.className = 'alert alert-danger mb-3';
            }
            else {
                estadoDisplay.innerHTML = '<span class="badge bg-warning">⚠ Revisa los campos</span>';
                this.validacionResumen.className = 'alert alert-warning mb-3';
            }
        }
        // Habilitar/deshabilitar botón de submit (opcional, el backend valida también)
        if (this.submitBtn) {
            // No deshabilitamos, solo cambiamos el estilo visual
            this.submitBtn.classList.toggle('btn-primary', resumen.isValid);
            this.submitBtn.classList.toggle('btn-warning', !resumen.isValid);
        }
    }
    /**
     * Método público para obtener el resumen actual
     */
    getResumen() {
        return this.calcularResumen();
    }
}
/**
 * Inicialización cuando el DOM está listo
 */
document.addEventListener('DOMContentLoaded', () => {
    try {
        // Crear instancia del manager solo si estamos en la página correcta
        if (document.getElementById('compraForm')) {
            const formManager = new FormCompraManager();
            // Exponer en window para debugging
            window.formCompraManager = formManager;
            console.log('✅ FormCompraManager inicializado correctamente');
        }
    }
    catch (error) {
        console.error('❌ Error al inicializar FormCompraManager:', error);
    }
});
//# sourceMappingURL=form_compra.js.map