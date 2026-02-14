"use strict";
/**
 * diagnostico_modal.ts
 * ====================
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo TypeScript maneja toda la lógica interactiva del modal
 * "Enviar Diagnóstico al Cliente" en la página detalle_orden.html.
 *
 * ¿Qué hace?
 * - Actualiza el asunto del correo en tiempo real al escribir el folio
 * - Cuenta componentes seleccionados e imágenes seleccionadas
 * - Permite seleccionar/deseleccionar todos los componentes e imágenes
 * - Genera el JSON de componentes para enviar al servidor
 * - Maneja el envío del formulario via AJAX (fetch)
 * - Actualiza la vista previa del PDF en el iframe
 * - Muestra feedback visual (loading, éxito, error)
 */
// ========================================================================
// FUNCIONES PRINCIPALES
// ========================================================================
/**
 * Inicializa toda la lógica del modal de diagnóstico.
 * Se ejecuta cuando el DOM está completamente cargado.
 */
function initDiagnosticoModal() {
    // Elementos del DOM
    const inputFolio = document.getElementById('inputFolioDiagnostico');
    const spanFolioPreview = document.getElementById('spanFolioPreview');
    const btnEnviar = document.getElementById('btnEnviarDiagnostico');
    const form = document.getElementById('formEnviarDiagnostico');
    const inputComponentesJSON = document.getElementById('inputComponentesJSON');
    const btnRefrescarPreview = document.getElementById('btnRefrescarPreviewDiag');
    const iframePreview = document.getElementById('iframePreviewDiagnostico');
    // Checkboxes
    const checkboxSelectAllImgs = document.getElementById('seleccionarTodasImagenesDiag');
    // Botón y dropdown para agregar componentes adicionales
    const btnAgregarComponente = document.getElementById('btnAgregarComponente');
    const dropdownComponentesAdicionales = document.getElementById('dropdownComponentesAdicionales');
    const componentesAdicionalesTbody = document.getElementById('componentesAdicionales');
    // Contadores
    const contadorComponentes = document.getElementById('contadorComponentesSeleccionados');
    const contadorImagenes = document.getElementById('contadorImagenesDiagSeleccionadas');
    // Contador para IDs únicos de componentes dinámicos
    let contadorComponentesDinamicos = 0;
    const componentesAgregados = new Set(); // Para evitar duplicados
    // Si no hay modal en la página, no ejecutar nada
    if (!form)
        return;
    // ====================================================================
    // 1. Actualización en tiempo real del asunto
    // ====================================================================
    if (inputFolio && spanFolioPreview) {
        inputFolio.addEventListener('input', () => {
            const folioValue = inputFolio.value.trim();
            spanFolioPreview.textContent = folioValue || '___';
        });
    }
    // ====================================================================
    // 2. Contador de componentes seleccionados
    // ====================================================================
    function actualizarContadorComponentes() {
        // Contar componentes predefinidos
        const checkboxesPredefinidos = document.querySelectorAll('.checkbox-componente');
        let seleccionados = 0;
        checkboxesPredefinidos.forEach(cb => {
            if (cb.checked)
                seleccionados++;
        });
        // Contar componentes adicionales dinámicos
        const checkboxesDinamicos = document.querySelectorAll('.checkbox-componente-dinamico');
        checkboxesDinamicos.forEach(cb => {
            if (cb.checked)
                seleccionados++;
        });
        if (contadorComponentes) {
            contadorComponentes.textContent = `${seleccionados} seleccionado${seleccionados !== 1 ? 's' : ''}`;
        }
    }
    // Event listeners para checkboxes de componentes predefinidos
    document.querySelectorAll('.checkbox-componente').forEach(cb => {
        cb.addEventListener('change', actualizarContadorComponentes);
    });
    // ====================================================================
    // 3. Contador de imágenes seleccionadas
    // ====================================================================
    function actualizarContadorImagenes() {
        const checkboxes = document.querySelectorAll('.checkbox-imagen-diag');
        let seleccionadas = 0;
        checkboxes.forEach(cb => {
            if (cb.checked)
                seleccionadas++;
        });
        if (contadorImagenes) {
            contadorImagenes.textContent = `${seleccionadas} seleccionada${seleccionadas !== 1 ? 's' : ''}`;
        }
    }
    // Event listeners para checkboxes de imágenes
    document.querySelectorAll('.checkbox-imagen-diag').forEach(cb => {
        cb.addEventListener('change', actualizarContadorImagenes);
    });
    // Seleccionar/deseleccionar todas las imágenes
    if (checkboxSelectAllImgs) {
        checkboxSelectAllImgs.addEventListener('change', () => {
            const checked = checkboxSelectAllImgs.checked;
            document.querySelectorAll('.checkbox-imagen-diag').forEach(cb => {
                cb.checked = checked;
            });
            actualizarContadorImagenes();
        });
    }
    // ====================================================================
    // 4. Componentes adicionales dinámicos
    // ====================================================================
    /**
     * Carga el dropdown con componentes adicionales disponibles.
     * Lee la lista de componentes del data-attribute y los inserta en el dropdown.
     */
    function cargarDropdownComponentes() {
        if (!btnAgregarComponente || !dropdownComponentesAdicionales)
            return;
        try {
            const componentesJSON = btnAgregarComponente.getAttribute('data-componentes');
            if (!componentesJSON) {
                dropdownComponentesAdicionales.innerHTML = '<li><span class="dropdown-item text-muted small">No hay componentes adicionales disponibles</span></li>';
                return;
            }
            const componentes = JSON.parse(componentesJSON);
            if (componentes.length === 0) {
                dropdownComponentesAdicionales.innerHTML = '<li><span class="dropdown-item text-muted small">No hay componentes adicionales disponibles</span></li>';
                return;
            }
            // Limpiar dropdown
            dropdownComponentesAdicionales.innerHTML = '';
            // Agregar cada componente como opción
            componentes.forEach(nombreComponente => {
                const li = document.createElement('li');
                const a = document.createElement('a');
                a.className = 'dropdown-item cursor-pointer';
                a.style.color = '#000'; // Forzar color negro para visibilidad
                a.textContent = nombreComponente;
                a.addEventListener('click', () => agregarComponenteDinamico(nombreComponente));
                li.appendChild(a);
                dropdownComponentesAdicionales.appendChild(li);
            });
        }
        catch (error) {
            console.error('Error al cargar componentes disponibles:', error);
            dropdownComponentesAdicionales.innerHTML = '<li><span class="dropdown-item text-danger small">Error cargando componentes</span></li>';
        }
    }
    /**
     * Agrega una fila dinámica para un componente adicional.
     */
    function agregarComponenteDinamico(nombreComponente) {
        if (!componentesAdicionalesTbody)
            return;
        // Evitar duplicados
        if (componentesAgregados.has(nombreComponente)) {
            alert(`⚠️ El componente "${nombreComponente}" ya ha sido agregado.`);
            return;
        }
        contadorComponentesDinamicos++;
        const idUnico = `comp_dinamico_${contadorComponentesDinamicos}`;
        // Crear fila
        const tr = document.createElement('tr');
        tr.className = 'table-success'; // Destacar que es dinámico
        tr.setAttribute('data-componente-nombre', nombreComponente);
        // Celda checkbox
        const tdCheck = document.createElement('td');
        tdCheck.className = 'text-center align-middle';
        const checkbox = document.createElement('input');
        checkbox.className = 'form-check-input checkbox-componente-dinamico';
        checkbox.type = 'checkbox';
        checkbox.checked = true; // Pre-seleccionado
        checkbox.id = idUnico;
        checkbox.setAttribute('data-componente-db', nombreComponente);
        checkbox.addEventListener('change', actualizarContadorComponentes);
        tdCheck.appendChild(checkbox);
        // Celda nombre
        const tdNombre = document.createElement('td');
        tdNombre.className = 'align-middle fw-semibold';
        const label = document.createElement('label');
        label.htmlFor = idUnico;
        label.className = 'mb-0 cursor-pointer d-block';
        label.innerHTML = `${nombreComponente} <span class="badge bg-success ms-2">ADICIONAL</span>`;
        tdNombre.appendChild(label);
        // Celda DPN
        const tdDpn = document.createElement('td');
        tdDpn.className = 'align-middle';
        const inputDpn = document.createElement('input');
        inputDpn.type = 'text';
        inputDpn.className = 'form-control form-control-sm input-dpn-dinamico';
        inputDpn.setAttribute('data-componente-db', nombreComponente);
        inputDpn.placeholder = 'Ej: DPN: 0XPJWG';
        tdDpn.appendChild(inputDpn);
        // Botón eliminar
        const btnEliminar = document.createElement('button');
        btnEliminar.type = 'button';
        btnEliminar.className = 'btn btn-danger btn-sm ms-2';
        btnEliminar.innerHTML = '<i class="bi bi-x-circle"></i>';
        btnEliminar.title = 'Eliminar componente';
        btnEliminar.addEventListener('click', () => eliminarComponenteDinamico(tr, nombreComponente));
        tdDpn.appendChild(btnEliminar);
        // Ensamblar fila
        tr.appendChild(tdCheck);
        tr.appendChild(tdNombre);
        tr.appendChild(tdDpn);
        // Insertar en tabla
        componentesAdicionalesTbody.appendChild(tr);
        // Registrar como agregado
        componentesAgregados.add(nombreComponente);
        // Actualizar contador
        actualizarContadorComponentes();
    }
    /**
     * Elimina una fila de componente dinámico.
     */
    function eliminarComponenteDinamico(fila, nombreComponente) {
        if (confirm(`¿Eliminar el componente "${nombreComponente}"?`)) {
            fila.remove();
            componentesAgregados.delete(nombreComponente);
            actualizarContadorComponentes();
        }
    }
    // Cargar dropdown al inicializar
    cargarDropdownComponentes();
    // ====================================================================
    // 5. Construir JSON de componentes
    // ====================================================================
    function construirComponentesJSON() {
        const componentes = [];
        // 1. Componentes predefinidos (de la tabla estática)
        const checkboxesPredefinidos = document.querySelectorAll('.checkbox-componente');
        checkboxesPredefinidos.forEach(cb => {
            const componenteDb = cb.getAttribute('data-componente-db') || '';
            const inputDpn = document.querySelector(`.input-dpn[data-componente-db="${componenteDb}"]`);
            componentes.push({
                componente_db: componenteDb,
                dpn: inputDpn ? inputDpn.value.trim() : '',
                seleccionado: cb.checked
            });
        });
        // 2. Componentes adicionales dinámicos (agregados por el usuario)
        const checkboxesDinamicos = document.querySelectorAll('.checkbox-componente-dinamico');
        checkboxesDinamicos.forEach(cb => {
            const componenteDb = cb.getAttribute('data-componente-db') || '';
            const inputDpn = document.querySelector(`.input-dpn-dinamico[data-componente-db="${componenteDb}"]`);
            componentes.push({
                componente_db: componenteDb,
                dpn: inputDpn ? inputDpn.value.trim() : '',
                seleccionado: cb.checked
            });
        });
        return componentes;
    }
    // ====================================================================
    // 6. Actualizar vista previa del PDF
    // ====================================================================
    if (btnRefrescarPreview && iframePreview) {
        btnRefrescarPreview.addEventListener('click', () => {
            const folio = inputFolio ? inputFolio.value.trim() : 'PREVIEW';
            const componentes = construirComponentesJSON();
            // Construir URL con parámetros
            const previewUrl = form.getAttribute('action') || '';
            // La URL de preview es diferente a la de envío
            // Extraer la base (orden/<id>/) y agregar preview-pdf-diagnostico/
            const baseUrl = previewUrl.replace('enviar-diagnostico-cliente/', 'preview-pdf-diagnostico/');
            const params = new URLSearchParams();
            params.set('folio', folio || 'PREVIEW');
            params.set('componentes', JSON.stringify(componentes));
            const fullUrl = `${baseUrl}?${params.toString()}`;
            // Mostrar loading
            btnRefrescarPreview.disabled = true;
            btnRefrescarPreview.innerHTML = '<i class="bi bi-hourglass-split"></i> Generando...';
            iframePreview.src = fullUrl;
            // Restaurar botón cuando carga
            iframePreview.onload = () => {
                btnRefrescarPreview.disabled = false;
                btnRefrescarPreview.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Actualizar Vista Previa';
            };
            // Timeout de seguridad
            setTimeout(() => {
                if (btnRefrescarPreview.disabled) {
                    btnRefrescarPreview.disabled = false;
                    btnRefrescarPreview.innerHTML = '<i class="bi bi-arrow-clockwise"></i> Actualizar Vista Previa';
                }
            }, 15000);
        });
    }
    // ====================================================================
    // 7. Envío del formulario via AJAX
    // ====================================================================
    if (btnEnviar && form) {
        btnEnviar.addEventListener('click', async () => {
            // Validaciones client-side
            const folio = inputFolio ? inputFolio.value.trim() : '';
            if (!folio) {
                alert('⚠️ El folio es obligatorio. Por favor, ingresa un folio para el diagnóstico.');
                if (inputFolio)
                    inputFolio.focus();
                return;
            }
            // Verificar que al menos un componente está seleccionado
            const componentesSeleccionados = document.querySelectorAll('.checkbox-componente:checked');
            if (componentesSeleccionados.length === 0) {
                const continuar = confirm('⚠️ No has seleccionado ningún componente.\n\n' +
                    '¿Deseas continuar sin marcar componentes?\n' +
                    '(El PDF se generará sin observaciones de componentes)');
                if (!continuar)
                    return;
            }
            // Confirmación final
            const confirmMsg = `¿Enviar diagnóstico al cliente?\n\n` +
                `📋 Folio: ${folio}\n` +
                `🔧 Componentes: ${componentesSeleccionados.length} seleccionados\n` +
                `📸 Imágenes: ${document.querySelectorAll('.checkbox-imagen-diag:checked').length} seleccionadas\n\n` +
                `El estado de la orden cambiará a "Diagnóstico enviado al cliente".`;
            if (!confirm(confirmMsg))
                return;
            // Preparar datos del formulario
            const formData = new FormData(form);
            // Agregar JSON de componentes
            const componentesJSON = JSON.stringify(construirComponentesJSON());
            formData.set('componentes', componentesJSON);
            // Mostrar estado de loading
            btnEnviar.disabled = true;
            const textoOriginal = btnEnviar.innerHTML;
            btnEnviar.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span> Enviando diagnóstico...';
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest'
                    }
                });
                const data = await response.json();
                if (data.success) {
                    // Éxito - mostrar mensaje y cerrar modal
                    alert(data.message || '✅ Diagnóstico enviado exitosamente.');
                    // Cerrar modal
                    const modalElement = document.getElementById('modalEnviarDiagnostico');
                    if (modalElement) {
                        // eslint-disable-next-line @typescript-eslint/no-explicit-any
                        const bsLib = window['bootstrap'];
                        if (bsLib) {
                            const modal = bsLib.Modal.getInstance(modalElement);
                            if (modal)
                                modal.hide();
                        }
                    }
                    // Recargar página para ver estado actualizado
                    window.location.reload();
                }
                else {
                    // Error del servidor
                    alert(data.error || '❌ Error al enviar el diagnóstico.');
                }
            }
            catch (error) {
                console.error('Error en envío de diagnóstico:', error);
                alert('❌ Error de conexión. Verifica tu conexión a internet e intenta nuevamente.');
            }
            finally {
                // Restaurar botón
                btnEnviar.disabled = false;
                btnEnviar.innerHTML = textoOriginal;
            }
        });
    }
}
// ========================================================================
// INICIALIZACIÓN
// ========================================================================
document.addEventListener('DOMContentLoaded', initDiagnosticoModal);
//# sourceMappingURL=diagnostico_modal.js.map