"use strict";
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
 * 5. Búsqueda AJAX de órdenes de servicio
 * 6. Cálculo de subtotales y total general en tiempo real
 * 7. Preview de imágenes de referencia antes de subir
 * 8. Autocomplete de modelo de equipo basado en la marca seleccionada
 */
/* =============================================================================
   CLASE PRINCIPAL — FormSolicitudCotizacionManager
   ============================================================================= */
class FormSolicitudCotizacionManager {
    constructor() {
        this.debounceTimer = null;
        const container = document.getElementById('lineasContainer');
        const template = document.getElementById('lineaTemplate');
        const addBtn = document.getElementById('addLineaBtn');
        const totalFormsInput = document.querySelector('[name="lineas-TOTAL_FORMS"]');
        const buscarOrdenBtn = document.getElementById('buscarOrdenBtn');
        const ordenInput = document.getElementById('numero_orden_cliente');
        const ordenInfo = document.getElementById('ordenInfo');
        const ordenInfoTexto = document.getElementById('ordenInfoTexto');
        const sinOrdenCheckbox = document.getElementById('sin_orden_activa');
        const ordenClienteContainer = document.getElementById('ordenClienteContainer');
        const sinOrdenContainer = document.getElementById('sinOrdenContainer');
        const serviceTagInput = document.getElementById('service_tag');
        const nombreClienteInput = document.getElementById('nombre_cliente');
        const imagenesReferenciaCard = document.getElementById('imagenesReferenciaCard');
        const marcaSelect = document.getElementById('marca');
        const modeloInput = document.getElementById('modelo');
        if (!container)
            throw new Error('No se encontró #lineasContainer');
        if (!template)
            throw new Error('No se encontró #lineaTemplate');
        if (!addBtn)
            throw new Error('No se encontró #addLineaBtn');
        if (!totalFormsInput)
            throw new Error('No se encontró input de TOTAL_FORMS');
        if (!buscarOrdenBtn)
            throw new Error('No se encontró #buscarOrdenBtn');
        if (!ordenInput)
            throw new Error('No se encontró #numero_orden_cliente');
        if (!ordenInfo)
            throw new Error('No se encontró #ordenInfo');
        if (!ordenInfoTexto)
            throw new Error('No se encontró #ordenInfoTexto');
        if (!sinOrdenCheckbox)
            throw new Error('No se encontró #sin_orden_activa');
        if (!ordenClienteContainer)
            throw new Error('No se encontró #ordenClienteContainer');
        if (!sinOrdenContainer)
            throw new Error('No se encontró #sinOrdenContainer');
        if (!serviceTagInput)
            throw new Error('No se encontró #service_tag');
        if (!nombreClienteInput)
            throw new Error('No se encontró #nombre_cliente');
        this.container = container;
        this.template = template;
        this.addBtn = addBtn;
        this.totalFormsInput = totalFormsInput;
        this.buscarOrdenBtn = buscarOrdenBtn;
        this.ordenInput = ordenInput;
        this.ordenInfo = ordenInfo;
        this.ordenInfoTexto = ordenInfoTexto;
        this.sinOrdenCheckbox = sinOrdenCheckbox;
        this.ordenClienteContainer = ordenClienteContainer;
        this.sinOrdenContainer = sinOrdenContainer;
        this.serviceTagInput = serviceTagInput;
        this.nombreClienteInput = nombreClienteInput;
        this.imagenesReferenciaCard = imagenesReferenciaCard;
        this.marcaSelect = marcaSelect;
        this.modeloInput = modeloInput;
        this.formCount = parseInt(totalFormsInput.value);
        this.buscarOrdenUrl = buscarOrdenBtn.dataset.url || '';
        this.modeloApiUrl = (modeloInput === null || modeloInput === void 0 ? void 0 : modeloInput.dataset.apiUrl) || '/servicio-tecnico/api/buscar-modelos-por-marca/';
        this.maxImagenes = parseInt((imagenesReferenciaCard === null || imagenesReferenciaCard === void 0 ? void 0 : imagenesReferenciaCard.dataset.max) || '6');
        this.initializeEventListeners();
        this.toggleModoSinOrden();
        this.calcularTotalGeneral();
        this.updateLineNumbers();
    }
    /* =========================================================================
       EVENT LISTENERS — Configuración de todos los listeners
       ========================================================================= */
    initializeEventListeners() {
        this.addBtn.addEventListener('click', () => this.agregarLinea());
        this.container.addEventListener('click', (e) => {
            const target = e.target;
            const removeBtn = target.closest('.remove-linea-btn');
            if (removeBtn) {
                const lineaForm = removeBtn.closest('.linea-form');
                if (lineaForm)
                    this.eliminarLinea(lineaForm);
            }
        });
        this.container.addEventListener('input', (e) => {
            const target = e.target;
            if (target.matches('[name$="-cantidad"], [name$="-costo_unitario"]')) {
                const lineaForm = target.closest('.linea-form');
                if (lineaForm)
                    this.calcularSubtotal(lineaForm);
            }
        });
        this.sinOrdenCheckbox.addEventListener('change', () => this.toggleModoSinOrden());
        this.serviceTagInput.addEventListener('input', () => {
            this.serviceTagInput.value = this.serviceTagInput.value.toUpperCase();
        });
        this.buscarOrdenBtn.addEventListener('click', () => this.buscarOrden());
        this.ordenInput.addEventListener('keydown', (e) => {
            if (e.key === 'Tab' || e.key === 'Enter') {
                e.preventDefault();
                this.buscarOrden();
            }
        });
        this.initializeImagenesReferencia();
        this.initializeModeloAutocomplete();
    }
    /* =========================================================================
       MODO SIN ORDEN — Toggle entre campos de orden y datos del cliente
       ========================================================================= */
    toggleModoSinOrden() {
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
            this.ordenInput.value = '';
            this.ordenInfo.classList.add('d-none');
        }
        else {
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
    limpiarCamposCliente() {
        this.serviceTagInput.value = '';
        this.nombreClienteInput.value = '';
        const telefonoInput = document.getElementById('telefono_cliente');
        const emailInput = document.getElementById('email_cliente');
        if (telefonoInput)
            telefonoInput.value = '';
        if (emailInput)
            emailInput.value = '';
        if (this.marcaSelect)
            this.marcaSelect.value = '';
        if (this.modeloInput)
            this.modeloInput.value = '';
    }
    /* =========================================================================
       IMÁGENES DE REFERENCIA — Preview y gestión de slots
       ========================================================================= */
    initializeImagenesReferencia() {
        const addSlotBtn = document.getElementById('addImagenSlotBtn');
        if (addSlotBtn) {
            addSlotBtn.addEventListener('click', () => this.agregarSlotImagen());
        }
        const uploadZone = document.getElementById('imagenesUploadZone');
        if (uploadZone) {
            uploadZone.addEventListener('click', (e) => {
                const target = e.target;
                const removeBtn = target.closest('.remove-imagen-slot');
                if (removeBtn) {
                    const slot = removeBtn.closest('.imagen-upload-slot');
                    if (slot) {
                        slot.remove();
                        this.actualizarContadorImagenes();
                    }
                }
            });
            uploadZone.addEventListener('change', (e) => {
                const target = e.target;
                if (target.classList.contains('imagen-ref-input') && target.files) {
                    this.previewImagen(target);
                }
            });
        }
    }
    agregarSlotImagen() {
        const uploadZone = document.getElementById('imagenesUploadZone');
        if (!uploadZone)
            return;
        const slotsActuales = uploadZone.querySelectorAll('.imagen-upload-slot').length;
        const imagenesExistentes = document.querySelectorAll('#imagenesUploadZone .imagen-ref-input');
        let archivosSeleccionados = 0;
        imagenesExistentes.forEach(input => {
            if (input.files && input.files.length > 0) {
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
        const newInput = slot.querySelector('.imagen-ref-input');
        if (newInput) {
            newInput.addEventListener('change', () => {
                if (newInput.files)
                    this.previewImagen(newInput);
            });
        }
        this.actualizarContadorImagenes();
    }
    previewImagen(input) {
        const slot = input.closest('.imagen-upload-slot');
        if (!slot)
            return;
        const previewDiv = slot.querySelector('.imagen-preview');
        if (!previewDiv || !input.files || input.files.length === 0)
            return;
        const file = input.files[0];
        const reader = new FileReader();
        reader.onload = (e) => {
            var _a;
            const img = previewDiv.querySelector('img');
            if (img && ((_a = e.target) === null || _a === void 0 ? void 0 : _a.result)) {
                img.src = e.target.result;
                previewDiv.classList.remove('d-none');
            }
        };
        reader.readAsDataURL(file);
        this.actualizarContadorImagenes();
    }
    actualizarContadorImagenes() {
        const contador = document.getElementById('contadorImagenesRef');
        if (!contador)
            return;
        const uploadZone = document.getElementById('imagenesUploadZone');
        if (!uploadZone)
            return;
        const slots = uploadZone.querySelectorAll('.imagen-ref-input');
        let conArchivo = 0;
        slots.forEach(input => {
            if (input.files && input.files.length > 0) {
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
    initializeModeloAutocomplete() {
        if (!this.marcaSelect || !this.modeloInput)
            return;
        this.marcaSelect.addEventListener('change', () => {
            if (this.modeloInput)
                this.modeloInput.value = '';
        });
        const modeloInput = this.modeloInput;
        const datalistId = 'modelo-datalist';
        let datalist = document.getElementById(datalistId);
        if (!datalist) {
            datalist = document.createElement('datalist');
            datalist.id = datalistId;
            document.body.appendChild(datalist);
        }
        modeloInput.setAttribute('list', datalistId);
        modeloInput.addEventListener('input', () => {
            if (this.debounceTimer)
                clearTimeout(this.debounceTimer);
            this.debounceTimer = setTimeout(() => {
                this.buscarModelos();
            }, 300);
        });
        modeloInput.addEventListener('focus', () => {
            this.buscarModelos();
        });
    }
    buscarModelos() {
        if (!this.marcaSelect || !this.modeloInput)
            return;
        const marca = this.marcaSelect.value;
        const termino = this.modeloInput.value.trim();
        if (!marca)
            return;
        const url = `${this.modeloApiUrl}?marca=${encodeURIComponent(marca)}&q=${encodeURIComponent(termino)}`;
        fetch(url)
            .then(response => response.json())
            .then((data) => {
            const datalist = document.getElementById('modelo-datalist');
            if (!datalist)
                return;
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
    agregarLinea() {
        const newForm = this.template.content.cloneNode(true);
        const formHtml = newForm.querySelector('.linea-form');
        if (!formHtml) {
            console.error('No se encontró .linea-form en el template');
            return;
        }
        formHtml.innerHTML = formHtml.innerHTML.replace(/__prefix__/g, this.formCount.toString());
        this.container.appendChild(newForm);
        this.formCount++;
        this.totalFormsInput.value = this.formCount.toString();
        this.updateLineNumbers();
        this.calcularTotalGeneral();
    }
    eliminarLinea(lineaForm) {
        const deleteCheckbox = lineaForm.querySelector('input[name$="-DELETE"]');
        if (deleteCheckbox) {
            this.marcarLineaComoEliminada(lineaForm, deleteCheckbox);
        }
        else {
            this.removerLineaNueva(lineaForm);
        }
    }
    marcarLineaComoEliminada(lineaForm, checkbox) {
        if (checkbox.checked) {
            checkbox.checked = false;
            lineaForm.style.opacity = '1';
            lineaForm.classList.remove('linea-eliminada');
            const wasRequired = lineaForm.querySelectorAll('[data-was-required="true"]');
            wasRequired.forEach(field => {
                field.setAttribute('required', 'required');
                field.removeAttribute('data-was-required');
            });
        }
        else {
            checkbox.checked = true;
            lineaForm.style.opacity = '0.4';
            lineaForm.classList.add('linea-eliminada');
            const requiredFields = lineaForm.querySelectorAll('[required]');
            requiredFields.forEach(field => {
                field.removeAttribute('required');
                field.setAttribute('data-was-required', 'true');
            });
        }
        this.updateLineNumbers();
        this.calcularTotalGeneral();
    }
    removerLineaNueva(lineaForm) {
        lineaForm.remove();
        this.reindexarFormularios();
        this.updateLineNumbers();
        this.calcularTotalGeneral();
    }
    reindexarFormularios() {
        const lineas = this.container.querySelectorAll('.linea-form');
        let nuevoIndice = 0;
        lineas.forEach(linea => {
            const deleteCheckbox = linea.querySelector('input[name$="-DELETE"]');
            if (deleteCheckbox && deleteCheckbox.checked) {
                return;
            }
            const indiceActual = this.obtenerIndiceDeLinea(linea);
            if (indiceActual === null)
                return;
            if (indiceActual !== nuevoIndice) {
                this.reemplazarIndiceEnLinea(linea, indiceActual, nuevoIndice);
            }
            nuevoIndice++;
        });
        this.formCount = nuevoIndice;
        this.totalFormsInput.value = this.formCount.toString();
    }
    obtenerIndiceDeLinea(linea) {
        const campo = linea.querySelector('[name^="lineas-"]');
        if (!campo)
            return null;
        const name = campo.getAttribute('name') || '';
        const match = name.match(/^lineas-(\d+)-/);
        return match ? parseInt(match[1]) : null;
    }
    reemplazarIndiceEnLinea(linea, indiceViejo, indiceNuevo) {
        const viejo = `lineas-${indiceViejo}-`;
        const nuevo = `lineas-${indiceNuevo}-`;
        const campos = linea.querySelectorAll('[name], [id], [for]');
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
    updateLineNumbers() {
        const lineas = this.container.querySelectorAll('.linea-form');
        let numero = 1;
        lineas.forEach(linea => {
            const deleteCheckbox = linea.querySelector('input[name$="-DELETE"]');
            const isDeleted = (deleteCheckbox === null || deleteCheckbox === void 0 ? void 0 : deleteCheckbox.checked) || false;
            if (!isDeleted) {
                const lineaNumero = linea.querySelector('.linea-numero');
                if (lineaNumero) {
                    lineaNumero.value = numero.toString();
                }
                numero++;
            }
        });
    }
    /* =========================================================================
       CÁLCULOS — Subtotales por línea y total general
       ========================================================================= */
    calcularSubtotal(lineaForm) {
        const cantidadInput = lineaForm.querySelector('[name$="-cantidad"]');
        const costoInput = lineaForm.querySelector('[name$="-costo_unitario"]');
        const subtotalEl = lineaForm.querySelector('.subtotal-linea');
        if (cantidadInput && costoInput && subtotalEl) {
            const cantidad = parseFloat(cantidadInput.value) || 0;
            const costo = parseFloat(costoInput.value) || 0;
            const subtotal = cantidad * costo;
            subtotalEl.textContent = '$' + subtotal.toFixed(2);
        }
        this.calcularTotalGeneral();
    }
    calcularTotalGeneral() {
        let total = 0;
        const lineas = this.container.querySelectorAll('.linea-form');
        lineas.forEach(linea => {
            const deleteCheckbox = linea.querySelector('input[name$="-DELETE"]');
            if (deleteCheckbox === null || deleteCheckbox === void 0 ? void 0 : deleteCheckbox.checked)
                return;
            const cantidadInput = linea.querySelector('[name$="-cantidad"]');
            const costoInput = linea.querySelector('[name$="-costo_unitario"]');
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
    /* =========================================================================
       BÚSQUEDA DE ORDEN — AJAX para vincular con órdenes de servicio
       ========================================================================= */
    buscarOrden() {
        if (this.sinOrdenCheckbox.checked)
            return;
        const numero = this.ordenInput.value.trim().toUpperCase();
        if (!numero) {
            this.ordenInfo.classList.add('d-none');
            return;
        }
        if (!numero.startsWith('OOW-') && !numero.startsWith('FL-')) {
            this.ordenInfo.classList.remove('d-none');
            this.ordenInfo.classList.remove('alert-info');
            this.ordenInfo.classList.add('alert-warning');
            this.ordenInfoTexto.textContent = 'Formato inválido. Use OOW-12345 o FL-67890';
            return;
        }
        if (!this.buscarOrdenUrl) {
            console.error('No se configuró la URL de búsqueda de órdenes');
            return;
        }
        const url = `${this.buscarOrdenUrl}?orden_cliente=${encodeURIComponent(numero)}`;
        fetch(url)
            .then(response => response.json())
            .then((data) => {
            this.ordenInfo.classList.remove('d-none');
            if (data.found) {
                this.ordenInfo.classList.remove('alert-warning');
                this.ordenInfo.classList.add('alert-info');
                this.ordenInfoTexto.innerHTML = `
                        <strong>${data.orden_cliente}</strong><br>
                        Estado: ${data.estado_display || data.estado || '-'}<br>
                        Sucursal: ${data.sucursal || '-'}
                    `;
                this.ordenInput.value = numero;
            }
            else if (data.success && !data.found) {
                this.ordenInfo.classList.remove('alert-info');
                this.ordenInfo.classList.add('alert-warning');
                this.ordenInfoTexto.textContent = `No se encontró ninguna orden con el número "${numero}". Verifica que sea correcta.`;
            }
            else {
                this.ordenInfo.classList.remove('alert-info');
                this.ordenInfo.classList.add('alert-warning');
                this.ordenInfoTexto.textContent = data.error || `No se encontró ninguna orden con el número "${numero}"`;
            }
        })
            .catch(error => {
            console.error('Error buscando orden:', error);
            this.ordenInfo.classList.remove('d-none');
            this.ordenInfo.classList.remove('alert-info');
            this.ordenInfo.classList.add('alert-warning');
            this.ordenInfoTexto.textContent = 'Error al buscar la orden. Intenta de nuevo.';
        });
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
    }
    catch (error) {
        console.error('❌ Error al inicializar FormSolicitudCotizacionManager:', error);
    }
});
//# sourceMappingURL=form_solicitud_cotizacion.js.map