"use strict";
/**
 * detalle_orden_enviar_imagenes.ts — modal enviar imágenes (Fase C).
 * Build: pnpm run build → static/js/detalle_orden_enviar_imagenes.js
 */
(function detalleOrdenEnviarImagenesMain() {
    /** CSRF global (csrf.ts incluye fallback al input del formulario). */
    function getCsrfTokenImagenes() {
        var _a, _b;
        return (_b = (_a = window.getCsrfToken) === null || _a === void 0 ? void 0 : _a.call(window)) !== null && _b !== void 0 ? _b : '';
    }
    function _el(id) {
        return document.getElementById(id);
    }
    function _qs(selector) {
        return document.querySelector(selector);
    }
    function _qsa(selector) {
        return document.querySelectorAll(selector);
    }
    document.addEventListener('DOMContentLoaded', function () {
        // =========================================================================
        // ELEMENTOS DEL DOM
        // =========================================================================
        const checkboxesImagenes = _qsa('.checkbox-imagen');
        const contadorImagenes = _el('contadorImagenesSeleccionadas');
        const previsualizacionArchivos = _el('previsualizacionArchivos');
        const selectTodas = _el('seleccionarTodasImagenes');
        const mensajePersonalizado = _el('mensaje_personalizado');
        const previsualizacionMensaje = _el('previsualizacionMensajePersonalizado');
        const textoMensajePersonalizado = _el('textoMensajePersonalizado');
        const btnEnviarImagenes = _el('btnEnviarImagenes');
        const formEnviarImagenes = _el('formEnviarImagenesCliente');
        // =========================================================================
        // FUNCIÓN: Actualizar contador de imágenes seleccionadas
        // =========================================================================
        function actualizarContador() {
            const seleccionadas = _qsa('.checkbox-imagen:checked').length;
            if (contadorImagenes) {
                contadorImagenes.textContent = seleccionadas + ' seleccionada' + (seleccionadas !== 1 ? 's' : '');
                // Cambiar color del badge según cantidad
                contadorImagenes.className = 'badge ms-2';
                if (seleccionadas === 0) {
                    contadorImagenes.classList.add('bg-secondary');
                }
                else if (seleccionadas < 3) {
                    contadorImagenes.classList.add('bg-warning', 'text-dark');
                }
                else {
                    contadorImagenes.classList.add('bg-primary');
                }
            }
            if (previsualizacionArchivos) {
                previsualizacionArchivos.innerHTML = `<i class="bi bi-images"></i> ${seleccionadas} imagen${seleccionadas !== 1 ? 'es' : ''}`;
            }
            // =====================================================================
            // CRÍTICO: Validación de email antes de habilitar botón de envío
            // =====================================================================
            // Solo habilitar/deshabilitar el botón si el email es VÁLIDO
            // Si tiene el atributo data-email-invalido, el botón SIEMPRE está disabled
            // (este atributo se establece en el template cuando el email es inválido)
            if (btnEnviarImagenes) {
                const emailInvalido = btnEnviarImagenes.hasAttribute('data-email-invalido');
                if (emailInvalido) {
                    // Email inválido: botón SIEMPRE deshabilitado (no importa cuántas imágenes)
                    btnEnviarImagenes.disabled = true;
                    btnEnviarImagenes.title = '⚠️ Debes configurar un email válido antes de enviar';
                    btnEnviarImagenes.classList.add('btn-outline-secondary');
                    btnEnviarImagenes.classList.remove('btn-primary');
                }
                else {
                    // Email válido: habilitar/deshabilitar según imágenes seleccionadas
                    btnEnviarImagenes.disabled = seleccionadas === 0;
                    btnEnviarImagenes.classList.remove('btn-outline-secondary');
                    btnEnviarImagenes.classList.add('btn-primary');
                    if (seleccionadas === 0) {
                        btnEnviarImagenes.title = 'Debes seleccionar al menos una imagen';
                    }
                    else {
                        btnEnviarImagenes.title = 'Enviar ' + seleccionadas + ' imagen' + (seleccionadas !== 1 ? 'es' : '') + ' al cliente';
                    }
                }
            }
        }
        // =========================================================================
        // EVENTO: Cambio en checkboxes individuales de imágenes
        // =========================================================================
        checkboxesImagenes.forEach(checkbox => {
            checkbox.addEventListener('change', function () {
                actualizarContador();
                // Agregar efecto visual al card
                const card = this.closest('.card');
                if (card) {
                    if (this.checked) {
                        card.classList.add('border-primary', 'border-3', 'shadow');
                    }
                    else {
                        card.classList.remove('border-primary', 'border-3', 'shadow');
                    }
                }
            });
        });
        // =========================================================================
        // EVENTO: Seleccionar/deseleccionar todas las imágenes
        // =========================================================================
        if (selectTodas) {
            selectTodas.addEventListener('change', function () {
                checkboxesImagenes.forEach(checkbox => {
                    checkbox.checked = this.checked;
                    // Aplicar efecto visual
                    const card = checkbox.closest('.card');
                    if (card) {
                        if (this.checked) {
                            card.classList.add('border-primary', 'border-3', 'shadow');
                        }
                        else {
                            card.classList.remove('border-primary', 'border-3', 'shadow');
                        }
                    }
                });
                actualizarContador();
            });
        }
        // =========================================================================
        // INICIO: Actualizar contador al cargar (imágenes pre-seleccionadas en HTML)
        // =========================================================================
        actualizarContador();
        // =========================================================================
        // EVENTO: Actualizar previsualización del mensaje personalizado
        // =========================================================================
        if (mensajePersonalizado) {
            mensajePersonalizado.addEventListener('input', function () {
                const texto = this.value.trim();
                if (previsualizacionMensaje && textoMensajePersonalizado) {
                    if (texto) {
                        previsualizacionMensaje.style.display = 'block';
                        textoMensajePersonalizado.textContent = texto;
                    }
                    else {
                        previsualizacionMensaje.style.display = 'none';
                    }
                }
            });
        }
        // =========================================================================
        // EVENTO: Envío del formulario con validación
        // =========================================================================
        if (formEnviarImagenes) {
            formEnviarImagenes.addEventListener('submit', async function (e) {
                var _a;
                e.preventDefault();
                // =====================================================================
                // VALIDACIÓN 1: Verificar que el email del cliente sea válido
                // =====================================================================
                const btnSubmit = _el('btnEnviarImagenes');
                if (btnSubmit && btnSubmit.hasAttribute('data-email-invalido')) {
                    alert('❌ No se puede enviar el correo\n\n' +
                        'El email del cliente no está configurado o es inválido.\n' +
                        'Por favor, actualiza el email del cliente antes de intentar enviar las imágenes.\n\n' +
                        'Usa el botón "Editar Email del Cliente Ahora" para configurarlo.');
                    return;
                }
                // =====================================================================
                // VALIDACIÓN 2: Verificar que se hayan seleccionado imágenes
                // =====================================================================
                const imagenesSeleccionadas = _qsa('.checkbox-imagen:checked').length;
                if (imagenesSeleccionadas === 0) {
                    alert('⚠️ Debes seleccionar al menos una imagen para enviar.');
                    return;
                }
                // =====================================================================
                // CONFIRMACIÓN FINAL: Confirmar envío con el usuario
                // =====================================================================
                const confirmacion = confirm(`📧 ¿Confirmas el envío de ${imagenesSeleccionadas} imagen${imagenesSeleccionadas !== 1 ? 'es' : ''} al cliente?\n\n` +
                    'El correo se procesará en segundo plano.');
                if (!confirmacion)
                    return;
                // Deshabilitar botón y mostrar loader (reusar variable btnSubmit ya declarada arriba)
                let textoOriginal = '';
                if (btnSubmit) {
                    textoOriginal = btnSubmit.innerHTML;
                    btnSubmit.disabled = true;
                    btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando...';
                }
                // Preparar datos del formulario
                const formData = new FormData(this);
                try {
                    // Enviar petición AJAX con headers correctos
                    const response = await fetch(this.action, {
                        method: 'POST',
                        headers: {
                            'X-CSRFToken': getCsrfTokenImagenes(),
                            'Accept': 'application/json', // Indicar que esperamos JSON
                            'X-Requested-With': 'XMLHttpRequest' // Indicar que es AJAX
                        },
                        body: formData
                    });
                    // Verificar si la respuesta es JSON
                    const contentType = response.headers.get('content-type');
                    if (!contentType || !contentType.includes('application/json')) {
                        // Si no es JSON, probablemente es un redirect (HTML)
                        // El correo se envió correctamente, pero el servidor devolvió HTML
                        console.warn('Respuesta no es JSON, recargando página...');
                        location.reload();
                        return;
                    }
                    const data = await response.json();
                    if (data.success) {
                        // Cerrar modal de envío
                        const modalEnviar = bootstrap.Modal.getInstance(_el('modalEnviarImagenesCliente'));
                        if (modalEnviar) {
                            modalEnviar.hide();
                        }
                        // Construir modal simple de confirmación (segundo plano)
                        const cantidadImagenes = data.data ? data.data.imagenes_seleccionadas : imagenesSeleccionadas;
                        const destinatario = data.data ? data.data.destinatario : '';
                        const modalConfirmacionHTML = `
                        <div class="modal fade" id="modalConfirmacionEnvioImagenes" tabindex="-1" aria-hidden="true">
                            <div class="modal-dialog modal-dialog-centered">
                                <div class="modal-content">
                                    <div class="modal-header modal-header-success text-white">
                                        <h5 class="modal-title">
                                            <i class="bi bi-send-check"></i> Imágenes en Proceso
                                        </h5>
                                    </div>
                                    <div class="modal-body">
                                        <div class="text-center mb-3">
                                            <i class="bi bi-gear" style="font-size: 3rem; color: #198754;"></i>
                                        </div>
                                        <p class="text-center fs-5 mb-2">
                                            <strong>${cantidadImagenes}</strong> imagen${cantidadImagenes !== 1 ? 'es' : ''} 
                                            se enviarán <strong>en segundo plano</strong> a <strong>${destinatario}</strong>.
                                        </p>
                                        <p class="text-center text-muted mb-0">
                                            <i class="bi bi-info-circle me-1"></i>
                                            La compresión y envío se están procesando. Puedes continuar trabajando normalmente.
                                        </p>
                                    </div>
                                    <div class="modal-footer">
                                        <button type="button" class="btn btn-primary" onclick="location.reload()">
                                            <i class="bi bi-check-lg"></i> Aceptar
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    `;
                        // Agregar modal al DOM si no existe
                        let modalConfirmacion = _el('modalConfirmacionEnvioImagenes');
                        if (modalConfirmacion) {
                            modalConfirmacion.remove();
                        }
                        document.body.insertAdjacentHTML('beforeend', modalConfirmacionHTML);
                        // Mostrar modal de confirmación
                        modalConfirmacion = new bootstrap.Modal(_el('modalConfirmacionEnvioImagenes'));
                        (_a = modalConfirmacion.show) === null || _a === void 0 ? void 0 : _a.call(modalConfirmacion);
                        // Actualizar el botón de ingreso en la página de forma inmediata,
                        // sin esperar al reload, para que el usuario vea el cambio al instante.
                        const btnIngreso = _qs('[data-bs-target="#modalEnviarImagenesCliente"]');
                        if (btnIngreso) {
                            btnIngreso.classList.remove('btn-primary');
                            btnIngreso.classList.add('btn-outline-primary');
                            btnIngreso.innerHTML = '<i class="bi bi-check-circle-fill me-1"></i> Imágenes de ingreso ya enviadas'
                                + '<span class="badge bg-primary bg-opacity-25 text-primary ms-2">reenviar</span>';
                        }
                    }
                    else {
                        // Error del servidor
                        alert('❌ Error al enviar el correo:\n\n' + (data.error || 'Error desconocido'));
                    }
                }
                catch (error) {
                    console.error('Error al enviar correo:', error);
                    alert('❌ Error de conexión al enviar el correo.\n\nPor favor, verifica tu conexión a internet e intenta nuevamente.');
                }
                finally {
                    // Restaurar botón solo si existe
                    if (btnSubmit) {
                        btnSubmit.disabled = false;
                        btnSubmit.innerHTML = textoOriginal;
                    }
                }
            });
        }
        // =========================================================================
        // INICIALIZACIÓN: Actualizar contador al cargar
        // =========================================================================
        actualizarContador();
        // =========================================================================
        // HOVER EFFECT: Resaltar cards al pasar el mouse
        // =========================================================================
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // Las cards de imágenes usan .imagen-selectable, pero el checkbox dentro
        // puede ser .checkbox-imagen (modal imágenes al cliente) o 
        // .checkbox-imagen-diag (modal diagnóstico). Buscamos ambos para evitar
        // un error de null cuando querySelector no encuentra la clase correcta.
        _qsa('.imagen-selectable').forEach(card => {
            card.addEventListener('mouseenter', function () {
                const checkbox = this.querySelector('.checkbox-imagen') || this.querySelector('.checkbox-imagen-diag');
                if (checkbox && !checkbox.checked) {
                    this.style.transform = 'scale(1.05)';
                    this.style.transition = 'transform 0.2s ease';
                }
            });
            card.addEventListener('mouseleave', function () {
                this.style.transform = 'scale(1)';
            });
        });
    });
})();
//# sourceMappingURL=detalle_orden_enviar_imagenes.js.map