/* =============================================================================
   JAVASCRIPT BASE - Sistema de Inventario
   Descripción: Funciones JavaScript globales y utilidades del sistema
   ============================================================================= */

// Auto-hide de mensajes después de 5 segundos
document.addEventListener('DOMContentLoaded', function() {
    // Configurar auto-hide de alertas
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            if (alert.classList.contains('show')) {
                var bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            }
        });
    }, 5000);
    
    // Inicializar tooltips de Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Inicializar popovers de Bootstrap
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
});

// Funciones globales para el sistema

/**
 * Función para confirmar eliminaciones
 * @param {string} mensaje - Mensaje personalizado de confirmación
 * @returns {boolean} - true si el usuario confirma
 */
function confirmarEliminacion(mensaje = '¿Estás seguro de que quieres eliminar este elemento?') {
    return confirm(mensaje);
}

/**
 * Función para mostrar notificaciones toast
 * @param {string} mensaje - Mensaje a mostrar
 * @param {string} tipo - Tipo de notificación (success, error, warning, info)
 */
function mostrarNotificacion(mensaje, tipo = 'info') {
    // Crear elemento toast
    const toastHtml = `
        <div class="toast align-items-center text-white bg-${tipo === 'error' ? 'danger' : tipo}" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">
                    ${mensaje}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;
    
    // Agregar al contenedor de toasts (si existe)
    let toastContainer = document.getElementById('toast-container');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        toastContainer.className = 'toast-container position-fixed top-0 end-0 p-3';
        document.body.appendChild(toastContainer);
    }
    
    toastContainer.innerHTML = toastHtml;
    const toastElement = toastContainer.querySelector('.toast');
    const toast = new bootstrap.Toast(toastElement);
    toast.show();
}

/**
 * Función para formatear números con separadores de miles
 * @param {number} numero - Número a formatear
 * @returns {string} - Número formateado
 */
function formatearNumero(numero) {
    return numero.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Función para validar formularios antes de envío
 * @param {HTMLFormElement} formulario - Formulario a validar
 * @returns {boolean} - true si es válido
 */
function validarFormulario(formulario) {
    let esValido = true;
    const camposRequeridos = formulario.querySelectorAll('[required]');
    
    camposRequeridos.forEach(function(campo) {
        if (!campo.value.trim()) {
            campo.classList.add('is-invalid');
            esValido = false;
        } else {
            campo.classList.remove('is-invalid');
            campo.classList.add('is-valid');
        }
    });
    
    return esValido;
}

/**
 * Función para limpiar validaciones de formulario
 * @param {HTMLFormElement} formulario - Formulario a limpiar
 */
function limpiarValidaciones(formulario) {
    const campos = formulario.querySelectorAll('.form-control, .form-select');
    campos.forEach(function(campo) {
        campo.classList.remove('is-valid', 'is-invalid');
    });
}

// Event listeners globales
document.addEventListener('DOMContentLoaded', function() {
    // Agregar confirmación a botones de eliminar
    const botonesEliminar = document.querySelectorAll('.btn-eliminar, [data-action="delete"]');
    botonesEliminar.forEach(function(boton) {
        boton.addEventListener('click', function(e) {
            const mensaje = this.getAttribute('data-confirm-message') || 
                           '¿Estás seguro de que quieres eliminar este elemento?';
            if (!confirmarEliminacion(mensaje)) {
                e.preventDefault();
            }
        });
    });
    
    // Agregar validación en tiempo real a formularios
    const formularios = document.querySelectorAll('form');
    formularios.forEach(function(form) {
        const campos = form.querySelectorAll('.form-control, .form-select');
        campos.forEach(function(campo) {
            campo.addEventListener('blur', function() {
                if (this.hasAttribute('required')) {
                    if (!this.value.trim()) {
                        this.classList.add('is-invalid');
                        this.classList.remove('is-valid');
                    } else {
                        this.classList.remove('is-invalid');
                        this.classList.add('is-valid');
                    }
                }
            });
        });
    });
});