/* =============================================================================
   VENTA MOSTRADOR - JavaScript AJAX
   Descripción: Funciones para gestión de Ventas Mostrador (sin diagnóstico)
   Autor: Sistema de Servicio Técnico
   Fecha: 8 de Octubre, 2025
   ============================================================================= */

// ============================================================================
// VARIABLES GLOBALES Y CONSTANTES
// ============================================================================

// Obtener el ID de la orden desde el DOM
const ordenId = window.location.pathname.split('/')[3];

// Descripciones de paquetes (sin precios fijos — ahora son editables en el formulario)
const DESCRIPCIONES_PAQUETES = {
    'premium': `
        <strong>🏆 SOLUCIÓN PREMIUM</strong><br>
        <ul class="mb-0 mt-2">
            <li>RAM 16GB DDR5 Samsung (4800-5600 MHz)</li>
            <li>SSD 1TB de alta velocidad</li>
            <li>Kit de Limpieza Profesional de REGALO</li>
            <li>Instalación y configuración incluida</li>
        </ul>
    `,
    'oro': `
        <strong>🥇 SOLUCIÓN ORO</strong><br>
        <ul class="mb-0 mt-2">
            <li>RAM 8GB DDR5 Samsung (3200 MHz)</li>
            <li>SSD 1TB de alta velocidad</li>
            <li>Instalación y configuración incluida</li>
        </ul>
    `,
    'plata': `
        <strong>🥈 SOLUCIÓN PLATA</strong><br>
        <ul class="mb-0 mt-2">
            <li>SSD 1TB de alta velocidad</li>
            <li>Instalación y configuración incluida</li>
        </ul>
    `,
    'ninguno': '<em>Sin paquete adicional - Servicios individuales</em>'
};

// Precios sugeridos (se autorellenan al seleccionar paquete, pero son editables)
const PRECIOS_SUGERIDOS_PAQUETES = {
    'premium': 5500.00,
    'oro':     3850.00,
    'plata':   2900.00,
    'ninguno': 0.00,
};

// ============================================================================
// INICIALIZACIÓN AL CARGAR LA PÁGINA
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('✅ Venta Mostrador JS inicializado para orden:', ordenId);
    
    // Inicializar event listeners
    inicializarEventListeners();
    
    // Calcular subtotal inicial si hay valores
    calcularSubtotalPiezaVentaMostrador();
});

// ============================================================================
// INICIALIZAR EVENT LISTENERS
// ============================================================================

function inicializarEventListeners() {
    // Select de paquete: mostrar descripción
    const selectPaquete = document.getElementById('id_paquete_venta');
    if (selectPaquete) {
        selectPaquete.addEventListener('change', mostrarDescripcionPaquete);
        mostrarDescripcionPaquete(); // Mostrar inicial
    }
    
    // Checkboxes de servicios: mostrar/ocultar campos de costo
    const checkboxes = [
        { checkbox: 'id_incluye_cambio_pieza', div: 'divCostoCambioPieza' },
        { checkbox: 'id_incluye_limpieza', div: 'divCostoLimpieza' },
        { checkbox: 'id_incluye_kit_limpieza', div: 'divCostoKit' },
        { checkbox: 'id_incluye_reinstalacion_so', div: 'divCostoReinstalacion' },
        { checkbox: 'id_incluye_respaldo', div: 'divCostoRespaldo' }
    ];
    
    checkboxes.forEach(item => {
        const checkbox = document.getElementById(item.checkbox);
        if (checkbox) {
            checkbox.addEventListener('change', function() {
                toggleCampoCosto(item.checkbox, item.div);
            });
            // Inicializar estado
            toggleCampoCosto(item.checkbox, item.div);
        }
    });
    
    // Inputs de cantidad y precio: calcular subtotal
    const inputCantidad = document.getElementById('id_cantidad');
    const inputPrecio = document.getElementById('id_precio_unitario');
    
    if (inputCantidad) {
        inputCantidad.addEventListener('input', calcularSubtotalPiezaVentaMostrador);
    }
    if (inputPrecio) {
        inputPrecio.addEventListener('input', calcularSubtotalPiezaVentaMostrador);
    }
    
    // Formulario de venta mostrador
    const formVentaMostrador = document.getElementById('formVentaMostrador');
    if (formVentaMostrador) {
        formVentaMostrador.addEventListener('submit', function(e) {
            e.preventDefault();
            guardarVentaMostrador();
        });
    }
    
    // Formulario de pieza venta mostrador
    const formPiezaVentaMostrador = document.getElementById('formPiezaVentaMostrador');
    if (formPiezaVentaMostrador) {
        formPiezaVentaMostrador.addEventListener('submit', function(e) {
            e.preventDefault();
            guardarPiezaVentaMostrador();
        });
    }
    
    // ⛔ EVENT LISTENER DE CONVERSIÓN ELIMINADO (Oct 2025)
    // Funcionalidad de conversión a diagnóstico eliminada
}

// ============================================================================
// FUNCIONES DE UI - MOSTRAR/OCULTAR ELEMENTOS
// ============================================================================

/**
 * Muestra la descripción del paquete seleccionado
 */
function mostrarDescripcionPaquete() {
    const selectPaquete = document.getElementById('id_paquete_venta');
    const divDescripcion = document.getElementById('descripcionPaquete');
    const textoDescripcion = document.getElementById('textoPaquete');
    const divCostoPaquete = document.getElementById('divCostoPaquete');
    const inputCostoPaquete = document.getElementById('id_costo_paquete');

    if (!selectPaquete || !divDescripcion || !textoDescripcion) return;

    const paqueteSeleccionado = selectPaquete.value;

    if (paqueteSeleccionado && paqueteSeleccionado !== 'ninguno' && DESCRIPCIONES_PAQUETES[paqueteSeleccionado]) {
        textoDescripcion.innerHTML = DESCRIPCIONES_PAQUETES[paqueteSeleccionado];
        divDescripcion.style.display = 'block';

        // Mostrar campo de precio y autorellenar solo si está vacío o en cero
        if (divCostoPaquete) divCostoPaquete.style.display = 'block';
        if (inputCostoPaquete) {
            inputCostoPaquete.required = true;
            const valorActual = parseFloat(inputCostoPaquete.value) || 0;
            if (valorActual <= 0) {
                inputCostoPaquete.value = PRECIOS_SUGERIDOS_PAQUETES[paqueteSeleccionado].toFixed(2);
            }
        }
    } else {
        divDescripcion.style.display = 'none';

        // Ocultar campo de precio y resetear
        if (divCostoPaquete) divCostoPaquete.style.display = 'none';
        if (inputCostoPaquete) {
            inputCostoPaquete.required = false;
            inputCostoPaquete.value = '0.00';
            inputCostoPaquete.classList.remove('is-invalid');
        }
    }
}

/**
 * Muestra u oculta campo de costo según checkbox
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta función controla la visibilidad de los campos de costo cuando
 * marcas o desmarcas un servicio adicional. Además, agrega validaciones
 * para asegurar que si marcas un servicio, DEBES ingresar un costo válido.
 * 
 * VALIDACIONES APLICADAS:
 * - required: Campo obligatorio (no se puede dejar vacío)
 * - min=0.01: El valor debe ser mayor a 0 (previene valores negativos o cero)
 * - step=0.01: Permite ingresar centavos (decimales)
 */
function toggleCampoCosto(checkboxId, divId) {
    const checkbox = document.getElementById(checkboxId);
    const div = document.getElementById(divId);
    
    if (!checkbox || !div) return;
    
    // Obtener el input de costo dentro del div
    const input = div.querySelector('input[type="number"]');
    
    if (checkbox.checked) {
        // ✅ SERVICIO MARCADO: Mostrar campo y habilitar validación
        div.style.display = 'block';
        if (input) {
            input.required = true;
            input.min = '0.01';  // 🆕 NUEVO: Valor mínimo (mayor a 0)
            input.step = '0.01'; // Permite decimales
            
            // 🆕 NUEVO: Validación en tiempo real al cambiar el valor
            input.addEventListener('input', function() {
                const valor = parseFloat(this.value) || 0;
                if (valor <= 0) {
                    this.setCustomValidity('El costo debe ser mayor a $0.00');
                    this.classList.add('is-invalid');
                } else {
                    this.setCustomValidity('');
                    this.classList.remove('is-invalid');
                }
            });
            
            // Disparar validación inicial si ya tiene un valor
            if (input.value) {
                input.dispatchEvent(new Event('input'));
            }
        }
    } else {
        // ❌ SERVICIO DESMARCADO: Ocultar campo y resetear validación
        div.style.display = 'none';
        if (input) {
            input.required = false;
            input.min = '';
            input.value = '0.00';  // Valor por defecto para enviar en POST
            input.setCustomValidity(''); // Limpiar errores de validación
            input.classList.remove('is-invalid');
        }
    }
}

// ============================================================================
// FUNCIONES WRAPPER ESPECÍFICAS (Llamadas desde template)
// ============================================================================

/**
 * Toggle para campo de cambio de pieza
 */
function toggleCambioPiezaCosto() {
    toggleCampoCosto('id_incluye_cambio_pieza', 'divCostoCambioPieza');
}

/**
 * Toggle para campo de limpieza
 */
function toggleLimpiezaCosto() {
    toggleCampoCosto('id_incluye_limpieza', 'divCostoLimpieza');
}

/**
 * Toggle para campo de kit de limpieza
 */
function toggleKitCosto() {
    toggleCampoCosto('id_incluye_kit_limpieza', 'divCostoKit');
}

/**
 * Toggle para campo de reinstalación SO
 */
function toggleReinstalacionCosto() {
    toggleCampoCosto('id_incluye_reinstalacion_so', 'divCostoReinstalacion');
}

/**
 * Toggle para campo de respaldo de información
 */
function toggleRespaldoCosto() {
    toggleCampoCosto('id_incluye_respaldo', 'divCostoRespaldo');
}

// ============================================================================
// CÁLCULOS
// ============================================================================

/**
 * Calcula y muestra el subtotal de una pieza
 */
function calcularSubtotalPiezaVentaMostrador() {
    const inputCantidad = document.getElementById('id_cantidad');
    const inputPrecio = document.getElementById('id_precio_unitario');
    const spanSubtotal = document.getElementById('subtotalPiezaVentaMostrador');
    
    if (!inputCantidad || !inputPrecio || !spanSubtotal) return;
    
    const cantidad = parseFloat(inputCantidad.value) || 0;
    const precio = parseFloat(inputPrecio.value) || 0;
    const subtotal = cantidad * precio;
    
    spanSubtotal.textContent = formatearMoneda(subtotal);
}

// ============================================================================
// MODAL: VENTA MOSTRADOR
// ============================================================================

/**
 * Abre el modal para crear venta mostrador
 */
function abrirModalVentaMostrador() {
    const modal = new bootstrap.Modal(document.getElementById('modalVentaMostrador'));
    const form = document.getElementById('formVentaMostrador');
    
    // Limpiar formulario
    if (form) form.reset();

    // Ocultar campo de precio de paquete al resetear
    const divCostoPaquete = document.getElementById('divCostoPaquete');
    if (divCostoPaquete) divCostoPaquete.style.display = 'none';

    // Ocultar alerta de errores
    const alertErrores = document.getElementById('alertErroresVentaMostrador');
    if (alertErrores) alertErrores.classList.add('d-none');
    
    // Mostrar modal
    modal.show();
}

/**
 * Guarda la venta mostrador (CREATE)
 * 
 * MEJORA (Enero 2026):
 * Ahora valida que TODOS los servicios marcados tengan un costo válido (mayor a 0)
 * antes de enviar el formulario. Previene enviar datos incompletos.
 */
function guardarVentaMostrador() {
    const form = document.getElementById('formVentaMostrador');
    const formData = new FormData(form);
    
    // Validaciones básicas
    const paquete = document.getElementById('id_paquete_venta').value;
    if (!paquete) {
        mostrarAlerta('Por favor selecciona un paquete', 'danger');
        return;
    }

    // Validar precio del paquete si se seleccionó uno real
    if (paquete !== 'ninguno') {
        const inputCostoPaquete = document.getElementById('id_costo_paquete');
        const costoPaquete = parseFloat(inputCostoPaquete ? inputCostoPaquete.value : 0) || 0;
        if (costoPaquete <= 0) {
            mostrarAlerta('⚠️ El precio del paquete debe ser mayor a $0.00', 'danger');
            if (inputCostoPaquete) {
                inputCostoPaquete.focus();
                inputCostoPaquete.classList.add('is-invalid');
            }
            return;
        }
        if (inputCostoPaquete) inputCostoPaquete.classList.remove('is-invalid');
    }
    
    // 🆕 VALIDACIÓN MEJORADA: Servicios con costos obligatorios
    const servicios = [
        { checkbox: 'id_incluye_cambio_pieza', input: 'id_costo_cambio_pieza', nombre: 'Cambio de Pieza' },
        { checkbox: 'id_incluye_limpieza', input: 'id_costo_limpieza', nombre: 'Limpieza' },
        { checkbox: 'id_incluye_kit_limpieza', input: 'id_costo_kit', nombre: 'Kit de Limpieza' },
        { checkbox: 'id_incluye_reinstalacion_so', input: 'id_costo_reinstalacion', nombre: 'Reinstalación SO' },
        { checkbox: 'id_incluye_respaldo', input: 'id_costo_respaldo', nombre: 'Respaldo de Información' }
    ];
    
    for (const servicio of servicios) {
        const checkbox = document.getElementById(servicio.checkbox);
        const input = document.getElementById(servicio.input);
        
        if (checkbox && checkbox.checked) {
            // ✅ Servicio marcado: DEBE tener un costo válido
            const costo = parseFloat(input.value);
            
            // 🆕 VALIDACIÓN 1: Campo vacío o no numérico
            if (!input.value || isNaN(costo)) {
                mostrarAlerta(
                    `⚠️ El servicio "${servicio.nombre}" está marcado pero no tiene un costo válido. ` +
                    `Por favor ingresa un valor mayor a $0.00`,
                    'danger'
                );
                input.focus(); // Enfocar el campo con error
                input.classList.add('is-invalid'); // Resaltar visualmente
                return;
            }
            
            // 🆕 VALIDACIÓN 2: Costo debe ser mayor a 0
            if (costo <= 0) {
                mostrarAlerta(
                    `⚠️ El costo de "${servicio.nombre}" debe ser mayor a $0.00. ` +
                    `Valor ingresado: $${costo.toFixed(2)}`,
                    'danger'
                );
                input.focus();
                input.classList.add('is-invalid');
                return;
            }
            
            // ✅ Costo válido: Limpiar marcas de error
            input.classList.remove('is-invalid');
        }
    }
    
    // Mostrar loading
    const btnSubmit = form.querySelector('button[type="submit"]');
    const textoOriginal = btnSubmit.innerHTML;
    btnSubmit.disabled = true;
    btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
    
    // Hacer petición AJAX
    fetch(`/servicio-tecnico/ordenes/${ordenId}/venta-mostrador/crear/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // ✅ NUEVO: Mensaje contextual según si es complemento o principal
            let mensaje = data.message;
            if (data.es_complemento) {
                mensaje += ' ✨ (Ventas adicionales registradas)';
            }
            
            // Éxito
            mostrarAlerta(mensaje, 'success');
            
            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalVentaMostrador'));
            if (modal) modal.hide();
            
            // Recargar página después de 1 segundo
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            // Errores de validación
            mostrarErroresFormulario(data.errors, 'listaErroresVentaMostrador', 'alertErroresVentaMostrador');
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = textoOriginal;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        mostrarAlerta('Error al guardar la venta mostrador. Por favor intenta nuevamente.', 'danger');
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = textoOriginal;
    });
}

// ============================================================================
// MODAL: PIEZA VENTA MOSTRADOR
// ============================================================================

/**
 * Abre el modal para agregar pieza
 */
function abrirModalPiezaVentaMostrador(esEdicion = false, piezaId = null) {
    const modal = new bootstrap.Modal(document.getElementById('modalPiezaVentaMostrador'));
    const form = document.getElementById('formPiezaVentaMostrador');
    const titulo = document.getElementById('modalPiezaVentaMostradorTitulo');
    const btnTexto = document.getElementById('btnPiezaVentaMostradorTexto');
    
    // Limpiar formulario
    if (form) form.reset();
    
    // Ocultar alerta de errores
    const alertErrores = document.getElementById('alertErroresPiezaVentaMostrador');
    if (alertErrores) alertErrores.classList.add('d-none');
    
    if (esEdicion && piezaId) {
        // Modo edición
        titulo.textContent = 'Editar Pieza';
        btnTexto.textContent = 'Guardar Cambios';
        document.getElementById('piezaVentaMostradorId').value = piezaId;
        
        // Cargar datos de la pieza
        cargarDatosPiezaVentaMostrador(piezaId);
    } else {
        // Modo agregar
        titulo.textContent = 'Agregar Pieza';
        btnTexto.textContent = 'Agregar Pieza';
        document.getElementById('piezaVentaMostradorId').value = '';
        calcularSubtotalPiezaVentaMostrador();
    }
    
    modal.show();
}

/**
 * Carga los datos de una pieza para editar
 */
function cargarDatosPiezaVentaMostrador(piezaId) {
    // Obtener datos de la fila
    const fila = document.querySelector(`#tablaPiezasVentaMostrador tr[data-pieza-id="${piezaId}"]`);
    if (!fila) {
        console.error('No se encontró la fila de la pieza');
        return;
    }
    
    // Extraer valores de la fila
    const celdas = fila.querySelectorAll('td');
    const descripcion = celdas[0].querySelector('strong').textContent.trim();
    const cantidad = parseInt(celdas[2].textContent.trim());
    const precioUnitario = parseFloat(celdas[3].textContent.replace('$', '').replace(',', ''));
    
    // Llenar formulario
    document.getElementById('id_descripcion_pieza').value = descripcion;
    document.getElementById('id_cantidad').value = cantidad;
    document.getElementById('id_precio_unitario').value = precioUnitario.toFixed(2);
    
    // Calcular subtotal
    calcularSubtotalPiezaVentaMostrador();
}

/**
 * Guarda o edita una pieza de venta mostrador
 */
function guardarPiezaVentaMostrador() {
    const form = document.getElementById('formPiezaVentaMostrador');
    const formData = new FormData(form);
    const piezaId = document.getElementById('piezaVentaMostradorId').value;
    
    // Validaciones
    const descripcion = document.getElementById('id_descripcion_pieza').value.trim();
    const cantidad = parseInt(document.getElementById('id_cantidad').value) || 0;
    const precio = parseFloat(document.getElementById('id_precio_unitario').value) || 0;
    
    if (!descripcion || descripcion.length < 3) {
        mostrarAlerta('La descripción debe tener al menos 3 caracteres', 'danger');
        return;
    }
    
    if (cantidad < 1) {
        mostrarAlerta('La cantidad debe ser al menos 1', 'danger');
        return;
    }
    
    if (precio <= 0) {
        mostrarAlerta('El precio unitario debe ser mayor a 0', 'danger');
        return;
    }
    
    // Determinar URL según sea agregar o editar
    let url;
    let method = 'POST';
    
    if (piezaId) {
        // Editar
        url = `/servicio-tecnico/venta-mostrador/piezas/${piezaId}/editar/`;
    } else {
        // Agregar
        url = `/servicio-tecnico/ordenes/${ordenId}/venta-mostrador/piezas/agregar/`;
    }
    
    // Mostrar loading
    const btnSubmit = form.querySelector('button[type="submit"]');
    const textoOriginal = btnSubmit.innerHTML;
    btnSubmit.disabled = true;
    btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';
    
    // Hacer petición AJAX
    fetch(url, {
        method: method,
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Éxito
            mostrarAlerta(data.message, 'success');
            
            // Cerrar modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('modalPiezaVentaMostrador'));
            if (modal) modal.hide();
            
            // Recargar página
            setTimeout(() => {
                window.location.reload();
            }, 800);
        } else {
            // Errores
            mostrarErroresFormulario(data.errors, 'listaErroresPiezaVentaMostrador', 'alertErroresPiezaVentaMostrador');
            btnSubmit.disabled = false;
            btnSubmit.innerHTML = textoOriginal;
        }
    })
    .catch(error => {
        console.error('Error:', error);
        mostrarAlerta('Error al guardar la pieza. Por favor intenta nuevamente.', 'danger');
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = textoOriginal;
    });
}

/**
 * Editar pieza venta mostrador
 */
function editarPiezaVentaMostrador(piezaId) {
    abrirModalPiezaVentaMostrador(true, piezaId);
}

/**
 * Elimina una pieza de venta mostrador
 */
function eliminarPiezaVentaMostrador(piezaId) {
    if (!confirm('¿Estás seguro de eliminar esta pieza? Esta acción no se puede deshacer.')) {
        return;
    }
    
    // Hacer petición AJAX
    fetch(`/servicio-tecnico/venta-mostrador/piezas/${piezaId}/eliminar/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            mostrarAlerta(data.message, 'success');
            
            // Recargar página
            setTimeout(() => {
                window.location.reload();
            }, 800);
        } else {
            mostrarAlerta(data.message || 'Error al eliminar la pieza', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        mostrarAlerta('Error al eliminar la pieza. Por favor intenta nuevamente.', 'danger');
    });
}

// ============================================================================
// ⛔ FUNCIONES DE CONVERSIÓN A DIAGNÓSTICO ELIMINADAS (Oct 2025)
// ============================================================================
// Las funciones convertirADiagnostico() y confirmarConversionDiagnostico()
// fueron eliminadas en la refactorización.
//
// Venta mostrador ahora es un complemento opcional que puede coexistir
// con cotización en la misma orden. No se requiere "convertir".
// ============================================================================

// ============================================================================
// FUNCIONES HELPER
// ============================================================================

/**
 * Obtiene el valor de una cookie (para CSRF token)
 */
function getCookie(name) {
    let cookieValue = null;
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
 * Formatea un número como moneda
 */
function formatearMoneda(valor) {
    return '$' + parseFloat(valor).toFixed(2).replace(/\d(?=(\d{3})+\.)/g, '$&,');
}

/**
 * Muestra una alerta Bootstrap
 */
function mostrarAlerta(mensaje, tipo = 'info') {
    // Crear elemento de alerta
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${tipo} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
    alertDiv.style.zIndex = '9999';
    alertDiv.style.minWidth = '300px';
    alertDiv.innerHTML = `
        ${mensaje}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    // Agregar al body
    document.body.appendChild(alertDiv);
    
    // Auto-remover después de 5 segundos
    setTimeout(() => {
        const bsAlert = new bootstrap.Alert(alertDiv);
        bsAlert.close();
    }, 5000);
}

/**
 * Muestra errores de formulario en un alert
 */
function mostrarErroresFormulario(errors, listaId, alertId) {
    const lista = document.getElementById(listaId);
    const alert = document.getElementById(alertId);
    
    if (!lista || !alert) return;
    
    // Limpiar lista
    lista.innerHTML = '';
    
    // Agregar errores
    if (typeof errors === 'object') {
        for (const [campo, mensajes] of Object.entries(errors)) {
            if (Array.isArray(mensajes)) {
                mensajes.forEach(mensaje => {
                    const li = document.createElement('li');
                    li.textContent = `${campo}: ${mensaje}`;
                    lista.appendChild(li);
                });
            } else {
                const li = document.createElement('li');
                li.textContent = `${campo}: ${mensajes}`;
                lista.appendChild(li);
            }
        }
    } else {
        const li = document.createElement('li');
        li.textContent = errors;
        lista.appendChild(li);
    }
    
    // Mostrar alert
    alert.classList.remove('d-none');
    
    // Scroll al alert
    alert.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

console.log('✅ Venta Mostrador JS - Todas las funciones cargadas correctamente');
