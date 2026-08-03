/**
 * detalle_orden_page.ts — UI del detalle de orden (Fase C).
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Antes era JS inline en el template. Ahora lee #detalle-orden-page-config
 * y CSRF de cookie (sigma_csrftoken / csrftoken).
 *
 * Todo vive dentro de un IIFE para no chocar con otros .ts globales.
 * Build: pnpm run build → static/js/detalle_orden_page.js
 */

(function detalleOrdenPageMain(): void {
    type DomEl = HTMLElement & {
        value: string;
        checked: boolean;
        disabled: boolean;
        required: boolean;
        action: string;
        reset: () => void;
        src: string;
        pause: () => void;
        load: () => void;
        style: CSSStyleDeclaration;
    };

    interface PageUrls {
        obtenerPieza: string;
        editarPieza: string;
        agregarPieza: string;
        eliminarPieza: string;
        obtenerSeguimiento: string;
        editarSeguimiento: string;
        agregarSeguimiento: string;
        eliminarSeguimiento: string;
        cambiarEstadoSeguimiento: string;
        marcarRecibido: string;
        reenviarNotificacion: string;
        marcarIncorrecta: string;
        marcarDanada: string;
        eliminarImagen: string;
    }

    interface PageConfig {
        estadisticasTecnicos: Record<string, {
            ordenes_activas: number;
            equipos_no_encienden: number;
            tiene_sobrecarga: boolean;
            porcentaje_no_encienden: number;
        }>;
        emailCliente: string;
        modalInicial: 'feedback' | 'vigencia' | 'satisfaccion' | null;
        ordenId: number;
        urls: PageUrls;
    }

    const bootstrap = (window as unknown as {
        bootstrap: {
            Modal: {
                new (el: Element): { show(): void; hide(): void };
                getInstance(el: Element): { show(): void; hide(): void } | null;
            };
            Tooltip: new (el: Element) => unknown;
        };
    }).bootstrap;

    function getCsrfToken(): string {
        const names: string[] = ['sigma_csrftoken', 'csrftoken'];
        for (const name of names) {
            const match = document.cookie.match(new RegExp('(?:^|;\\s*)' + name + '=([^;]+)'));
            if (match) {
                return decodeURIComponent(match[1]);
            }
        }
        return '';
    }

    function _el(id: string): DomEl {
        return document.getElementById(id) as DomEl;
    }

    function _qs(selector: string): DomEl {
        return document.querySelector(selector) as DomEl;
    }

    function _qsa(selector: string): NodeListOf<DomEl> {
        return document.querySelectorAll(selector) as NodeListOf<DomEl>;
    }

    const cfgEl = document.getElementById('detalle-orden-page-config');
    if (!cfgEl || !cfgEl.textContent) {
        console.error('[detalle_orden_page] Falta #detalle-orden-page-config');
        return;
    }
    const config: PageConfig = JSON.parse(cfgEl.textContent) as PageConfig;

const estadisticasTecnicos = config.estadisticasTecnicos;

// ============================================================================
// ALERTA DINÁMICA DE CARGA DE TRABAJO DEL TÉCNICO
// ============================================================================
document.addEventListener('DOMContentLoaded', function() {
    // ============================================================================
    // INICIALIZAR TOOLTIPS DE BOOTSTRAP
    // ============================================================================
    // Los tooltips necesitan inicializarse manualmente para funcionar
    const tooltipTriggerList = [].slice.call(_qsa('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // ============================================================================
    // ✅ NUEVO: MOSTRAR MODALES DE CONFIRMACIÓN POST-RECHAZO (Feedback System)
    // ============================================================================
    // EXPLICACIÓN PARA PRINCIPIANTES:
    // Después de registrar un rechazo, el backend guarda variables en la sesión.
    // Cuando se hace redirect a detalle_orden, esas variables vienen en el contexto.
    // Este código detecta si existen y muestra el modal correspondiente automáticamente.
    
    // Modales post-rechazo / satisfacción (flags vienen del JSON de config)
    if (config.modalInicial === 'feedback') {
        const modalFeedback = _el('modalConfirmarFeedback');
        if (modalFeedback) {
            const bsModalFeedback = new bootstrap.Modal(modalFeedback);
            bsModalFeedback.show();
        }
    } else if (config.modalInicial === 'vigencia') {
        const modalVigencia = _el('modalConfirmarVigenciaVencida');
        if (modalVigencia) {
            const bsModalVigencia = new bootstrap.Modal(modalVigencia);
            bsModalVigencia.show();
        }
    } else if (config.modalInicial === 'satisfaccion') {
        const modalSatisfaccion = _el('modalConfirmarSatisfaccion');
        if (modalSatisfaccion) {
            const bsModalSatisfaccion = new bootstrap.Modal(modalSatisfaccion);
            bsModalSatisfaccion.show();
        }
    }
    
    // ============================================================================
    // ALERTA DE CARGA DE TRABAJO DEL TÉCNICO
    // ============================================================================
    const selectTecnico = _el('id_tecnico_select');
    const divAlerta = _el('alertaTecnico');
    
    if (selectTecnico && divAlerta) {
        // Función para mostrar la alerta según el técnico seleccionado
        function mostrarAlertaTecnico() {
            const tecnicoId = selectTecnico.value;
            
            if (!tecnicoId || !estadisticasTecnicos[tecnicoId]) {
                divAlerta.style.display = 'none';
                return;
            }
            
            const stats = estadisticasTecnicos[tecnicoId];
            const ordenesActivas = stats.ordenes_activas;
            const equiposNoEncienden = stats.equipos_no_encienden;
            const tieneSobrecarga = stats.tiene_sobrecarga;
            const porcentaje = stats.porcentaje_no_encienden;
            
            // Si no tiene órdenes activas, no mostrar nada
            if (ordenesActivas === 0) {
                divAlerta.style.display = 'none';
                return;
            }
            
            // Determinar el tipo de alerta y mensaje
            let tipoAlerta = 'info';
            let icono = 'info-circle';
            let mensaje = '';
            
            if (tieneSobrecarga) {
                // ALERTA ROJA: 3 o más equipos que no encienden
                tipoAlerta = 'danger';
                icono = 'exclamation-triangle-fill';
                mensaje = `
                    <strong>⚠️ ALTA CARGA DE TRABAJO</strong><br>
                    Este técnico tiene <strong>${equiposNoEncienden}</strong> equipos que NO encienden 
                    de un total de <strong>${ordenesActivas}</strong> órdenes activas (${porcentaje}%).<br>
                    <small>Considera asignar a otro técnico con menos carga.</small>
                `;
            } else if (equiposNoEncienden > 0) {
                // ALERTA AMARILLA: Tiene equipos que no encienden pero no sobrecarga
                tipoAlerta = 'warning';
                icono = 'exclamation-circle-fill';
                mensaje = `
                    <strong>⚡ Equipos complejos asignados</strong><br>
                    Este técnico tiene <strong>${equiposNoEncienden}</strong> equipos que NO encienden 
                    de <strong>${ordenesActivas}</strong> órdenes activas (${porcentaje}%).<br>
                    <small>Aún tiene capacidad, pero monitorea su carga de trabajo.</small>
                `;
            } else {
                // ALERTA AZUL: Tiene órdenes pero todas encienden
                tipoAlerta = 'info';
                icono = 'info-circle-fill';
                mensaje = `
                    <strong>✓ Carga normal</strong><br>
                    Este técnico tiene <strong>${ordenesActivas}</strong> órdenes activas, 
                    todos los equipos encienden.<br>
                    <small>Buena disponibilidad para nuevas asignaciones.</small>
                `;
            }
            
            // Mostrar la alerta
            divAlerta.className = `alert alert-${tipoAlerta} d-flex align-items-start`;
            divAlerta.innerHTML = `
                <i class="bi bi-${icono} me-2 mt-1"></i>
                <div style="font-size: 0.9rem;">${mensaje}</div>
            `;
            divAlerta.style.display = 'flex';
        }
        
        // Mostrar alerta al cargar la página (técnico actual)
        mostrarAlertaTecnico();
        
        // Actualizar alerta al cambiar el técnico
        selectTecnico.addEventListener('change', mostrarAlertaTecnico);
    }
});

// ============================================================================
// CONFIRMACIONES ANTES DE ENVIAR FORMULARIOS
// ============================================================================
// Optional chaining: si el form no está en el DOM, no tumbar toda la página.
_el('formCambioEstado')?.addEventListener('submit', function(e) {
    if (!confirm('¿Estás seguro de cambiar el estado de la orden?')) {
        e.preventDefault();
    }
});

// ============================================================================
// CONTROL DEL CAMPO CARGADOR EN EL MODAL
// ============================================================================
function toggleCargadorFieldsModal() {
    const checkboxCargador = _el('id_tiene_cargador_modal');
    const divNumeroSerie = _el('divNumeroSerieCargadorModal');
    
    if (checkboxCargador && divNumeroSerie) {
        if (checkboxCargador.checked) {
            divNumeroSerie.style.display = 'block';
        } else {
            divNumeroSerie.style.display = 'none';
            // Limpiar el campo si se desmarca
            const inputNumeroSerie = _el('id_numero_serie_cargador_modal');
            if (inputNumeroSerie) {
                inputNumeroSerie.value = '';
            }
        }
    }
}

// Inicializar estado al cargar la página
document.addEventListener('DOMContentLoaded', function() {
    toggleCargadorFieldsModal();
});

// Inicializar estado al abrir el modal
const modalEditarInfo = _el('modalEditarInfoEquipo');
if (modalEditarInfo) {
    modalEditarInfo.addEventListener('shown.bs.modal', function() {
        toggleCargadorFieldsModal();
    });
}

// ============================================================================
// GESTIÓN DE COTIZACIÓN - Mostrar/Ocultar campos de rechazo y descuento
// ============================================================================
document.addEventListener('DOMContentLoaded', function() {
    const formGestionar = _el('formGestionarCotizacion');
    
    if (formGestionar) {
        const radiosAccion = _qsa('input[name="accion"]');
        const camposRechazo = _el('camposRechazo');
        const selectMotivo = _qs('select[name="motivo_rechazo"]');
        
        // 🆕 NUEVO: Elementos del descuento de mano de obra
        const divDescontoManoObra = _el('divDescontoManoObra');
        const checkboxDescuento = _el('id_descontar_mano_obra');
        const filaDescuento = _el('filaDescuento');
        const filaTotalFinal = _el('filaTotalFinal');
        const separadorTotal = _el('separadorTotal');
        
        // Función para mostrar/ocultar campos según acción seleccionada
        function toggleCamposRechazo() {
            const accionSeleccionada = _qs('input[name="accion"]:checked');
            
            if (accionSeleccionada && accionSeleccionada.value === 'rechazar') {
                // RECHAZAR: Mostrar campos de rechazo, ocultar descuento
                camposRechazo.style.display = 'block';
                if (selectMotivo) {
                    selectMotivo.required = true;
                }
                
                // Ocultar y desactivar descuento
                if (divDescontoManoObra) {
                    divDescontoManoObra.style.display = 'none';
                    if (checkboxDescuento) {
                        checkboxDescuento.checked = false;
                        checkboxDescuento.disabled = true;
                    }
                }
            } else if (accionSeleccionada && accionSeleccionada.value === 'aceptar') {
                // ACEPTAR: Ocultar campos de rechazo, mostrar descuento
                camposRechazo.style.display = 'none';
                if (selectMotivo) {
                    selectMotivo.required = false;
                }
                
                // Mostrar y habilitar descuento
                if (divDescontoManoObra) {
                    divDescontoManoObra.style.display = 'block';
                    if (checkboxDescuento) {
                        checkboxDescuento.disabled = false;
                    }
                }
            } else {
                // Sin selección: ocultar todo
                camposRechazo.style.display = 'none';
                if (divDescontoManoObra) {
                    divDescontoManoObra.style.display = 'none';
                }
            }
        }
        
        // 🆕 NUEVO: Función para actualizar el resumen de totales
        function actualizarResumenDescuento() {
            if (!checkboxDescuento || !filaDescuento || !filaTotalFinal) return;
            
            if (checkboxDescuento.checked) {
                // Mostrar descuento y total final
                filaDescuento.style.display = 'flex';
                separadorTotal.style.display = 'block';
                filaTotalFinal.style.display = 'flex';
            } else {
                // Ocultar descuento y total final
                filaDescuento.style.display = 'none';
                separadorTotal.style.display = 'none';
                filaTotalFinal.style.display = 'none';
            }
        }
        
        // Escuchar cambios en los radio buttons de acción
        radiosAccion.forEach(radio => {
            radio.addEventListener('change', toggleCamposRechazo);
        });
        
        // 🆕 NUEVO: Escuchar cambios en el checkbox de descuento
        if (checkboxDescuento) {
            checkboxDescuento.addEventListener('change', actualizarResumenDescuento);
        }
        
        // Inicializar al cargar
        toggleCamposRechazo();
        actualizarResumenDescuento();
        
        // Confirmación antes de enviar
        formGestionar.addEventListener('submit', function(e) {
            const accionSeleccionada = _qs('input[name="accion"]:checked');
            
            if (!accionSeleccionada) {
                e.preventDefault();
                alert('Por favor selecciona si aceptas o rechazas la cotización.');
                return false;
            }
            
            const accion = accionSeleccionada.value;
            
            // ✅ NUEVO (Feedback Rechazo): Validar email del cliente antes de rechazar
            if (accion === 'rechazar') {
                const emailCliente = config.emailCliente;
                const motivoSeleccionado = selectMotivo ? selectMotivo.value : '';
                
                // Lista de motivos que requieren envío de correo con link de feedback
                const motivosConFeedback = [
                    'costo_alto', 'muchas_piezas', 'tiempo_largo', 
                    'falta_justificacion', 'no_vale_pena', 'rechazo_sin_decision',
                    'no_especifica_motivo', 'no_autorizado_por_empresa', 'otro'
                ];
                
                // Validar solo si el motivo requiere envío de correo
                if (motivosConFeedback.includes(motivoSeleccionado)) {
                    if (!emailCliente || emailCliente === 'cliente@ejemplo.com') {
                        e.preventDefault();
                        
                        // Mostrar modal de error explicativo
                        const modalHTML = `
                            <div class="modal fade" id="modalEmailInvalido" tabindex="-1" data-bs-backdrop="static">
                                <div class="modal-dialog modal-dialog-centered">
                                    <div class="modal-content" style="border-left: 5px solid #dc3545;">
                                        <div class="modal-header modal-header-danger text-white">
                                            <h5 class="modal-title">
                                                <i class="bi bi-exclamation-triangle-fill"></i> Email del Cliente Inválido
                                            </h5>
                                        </div>
                                        <div class="modal-body">
                                            <div class="alert alert-warning mb-3" style="border-left: 4px solid #ffc107;">
                                                <strong><i class="bi bi-info-circle"></i> ¿Por qué necesitamos un email válido?</strong>
                                                <p class="mb-0 mt-2 small">
                                                    Este motivo de rechazo requiere enviar un correo al cliente para solicitar 
                                                    su retroalimentación sobre por qué rechazó la cotización. Esto nos ayuda a 
                                                    mejorar nuestro servicio.
                                                </p>
                                            </div>
                                            <p class="mb-3">
                                                El email actual es: <strong class="text-danger">${emailCliente || '(vacío)'}</strong>
                                            </p>
                                            <p class="mb-0">
                                                <i class="bi bi-arrow-right-circle text-primary"></i>
                                                Por favor, actualiza el email del cliente antes de continuar.
                                            </p>
                                        </div>
                                        <div class="modal-footer">
                                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                                                <i class="bi bi-x-lg"></i> Cancelar
                                            </button>
                                            <!--
                                              EXPLICACIÓN PARA PRINCIPIANTES:
                                              NO usar onclick="_qs(...)" aquí. _qs/_el viven DENTRO del
                                              IIFE de TypeScript y no existen en window → ReferenceError.
                                              El listener se engancha abajo con addEventListener.
                                            -->
                                            <button type="button" class="btn btn-primary" id="btnEditarInfoDesdeEmailInvalido">
                                                <i class="bi bi-pencil-square"></i> Editar Información del Equipo
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                        
                        // Remover modal existente si hay
                        const modalExistente = _el('modalEmailInvalido');
                        if (modalExistente) modalExistente.remove();
                        
                        // Agregar y mostrar modal
                        document.body.insertAdjacentHTML('beforeend', modalHTML);
                        const modalEmailEl = _el('modalEmailInvalido');
                        const modal = new bootstrap.Modal(modalEmailEl);
                        // Paso: al clic, abrir modal de editar equipo y cerrar este aviso.
                        const btnEditarInfo = _el('btnEditarInfoDesdeEmailInvalido');
                        btnEditarInfo?.addEventListener('click', () => {
                            const triggerEditar = document.querySelector(
                                '[data-bs-target="#modalEditarInfoEquipo"]'
                            ) as HTMLElement | null;
                            triggerEditar?.click();
                            bootstrap.Modal.getInstance(modalEmailEl)?.hide();
                        });
                        modal.show();
                        
                        return false;
                    }
                }
            }
            
            // 🆕 NUEVO: Mensaje personalizado si aplica descuento
            let mensaje;
            if (accion === 'aceptar') {
                if (checkboxDescuento && checkboxDescuento.checked) {
                    mensaje = '¿Confirmas que el cliente ACEPTÓ la cotización con DESCUENTO de mano de obra?\n\n' +
                              '🎁 El diagnóstico será GRATUITO como beneficio.\n' +
                              'Esto cambiará el estado de la orden.';
                } else {
                    mensaje = '¿Confirmas que el cliente ACEPTÓ la cotización?\n' +
                              'Esto cambiará el estado de la orden.';
                }
            } else {
                mensaje = '¿Confirmas que el cliente RECHAZÓ la cotización?\n' +
                          'Esto cambiará el estado de la orden.';
            }
            
            if (!confirm(mensaje)) {
                e.preventDefault();
                return false;
            }
        });
    }
});

// ============================================================================
// GESTIÓN DE PIEZAS COTIZADAS - FUNCIONES AJAX
// ============================================================================

/**
 * Abre el modal para agregar una nueva pieza
 */
async function abrirModalPieza(piezaId: number | null = null) {
    const modal = new bootstrap.Modal(_el('modalPieza'));
    const form = _el('formPieza');
    const titulo = _el('modalPiezaTitulo');
    const btnTexto = _el('btnPiezaTexto');
    const alertErrores = _el('alertErroresPieza');
    
    // Resetear formulario
    form.reset();
    alertErrores.classList.add('d-none');
    
    if (piezaId) {
        // Modo EDITAR - Cargar datos de la pieza
        titulo.textContent = 'Editar Pieza';
        btnTexto.textContent = 'Actualizar Pieza';
        _el('piezaId').value = String(piezaId);
        
        // Cargar datos de la pieza vía AJAX
        try {
            const url = config.urls.obtenerPieza.replace('/0/', `/${piezaId}/`);
            const response = await fetch(url);
            const data = await response.json();
            
            if (data.success) {
                const pieza = data.pieza;
                
                // Poblar el formulario con los datos
                _el('componente').value = pieza.componente_id;
                _el('descripcion_adicional').value = pieza.descripcion_adicional;
                _el('proveedor').value = pieza.proveedor || '';  // ← NUEVO CAMPO (Noviembre 2025)
                _el('cantidad').value = pieza.cantidad;
                _el('costo_unitario').value = pieza.costo_unitario;
                _el('orden_prioridad').value = pieza.orden_prioridad;
                _el('es_necesaria').checked = pieza.es_necesaria;
                _el('sugerida_por_tecnico').checked = pieza.sugerida_por_tecnico;
            } else {
                mostrarToast(data.error || 'Error al cargar datos de la pieza', 'danger');
                return;
            }
        } catch (error) {
            console.error('Error al cargar pieza:', error);
            mostrarToast('Error de conexión al cargar la pieza', 'danger');
            return;
        }
    } else {
        // Modo AGREGAR
        titulo.textContent = 'Agregar Pieza';
        btnTexto.textContent = 'Agregar Pieza';
        _el('piezaId').value = '';
    }
    
    modal.show();
}

/**
 * Guarda una pieza (agregar o editar)
 */
_el('formPieza')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const piezaId = _el('piezaId').value;
    const formData = new FormData(this as unknown as HTMLFormElement);
    const alertErrores = _el('alertErroresPieza');
    const listaErrores = _el('listaErroresPieza');
    
    // Determinar URL según sea agregar o editar
    let url;
    if (piezaId) {
        url = config.urls.editarPieza.replace('/0/', `/${piezaId}/`);
    } else {
        url = config.urls.agregarPieza;
    }
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Cerrar modal
            bootstrap.Modal.getInstance(_el('modalPieza'))?.hide();
            
            // Mostrar mensaje de éxito
            mostrarToast(data.message, 'success');
            
            // Recargar la página para actualizar la tabla
            setTimeout(() => location.reload(), 1000);
        } else {
            // Mostrar errores del formulario
            listaErrores.innerHTML = '';
            if (data.errors) {
                Object.entries(data.errors).forEach(([field, error]) => {
                    const li = document.createElement('li');
                    li.textContent = `${field}: ${error}`;
                    listaErrores.appendChild(li);
                });
            } else if (data.error) {
                const li = document.createElement('li');
                li.textContent = data.error;
                listaErrores.appendChild(li);
            }
            alertErrores.classList.remove('d-none');
        }
    } catch (error) {
        console.error('Error:', error);
        mostrarToast('Error de conexión', 'danger');
    }
});

/**
 * Edita una pieza existente
 */
function editarPieza(piezaId: number) {
    abrirModalPieza(piezaId);
}

/**
 * Elimina una pieza
 */
async function eliminarPieza(piezaId: number) {
    if (!confirm('¿Estás seguro de eliminar esta pieza?')) {
        return;
    }
    
    const url = config.urls.eliminarPieza.replace('/0/', `/${piezaId}/`);
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            mostrarToast(data.message, 'success');
            
            // Eliminar la fila de la tabla
            const fila = _qs(`tr[data-pieza-id="${piezaId}"]`);
            if (fila) {
                fila.remove();
            }
            
            // Recargar para actualizar totales
            setTimeout(() => location.reload(), 1000);
        } else {
            mostrarToast(data.error || 'Error al eliminar', 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        mostrarToast('Error de conexión', 'danger');
    }
}

// ============================================================================
// GESTIÓN DE SEGUIMIENTOS - FUNCIONES AJAX
// ============================================================================

/**
 * Abre el modal para agregar/editar seguimiento
 */
function abrirModalSeguimiento(seguimientoId: number | null = null): void {
    const modal = new bootstrap.Modal(_el('modalSeguimiento'));
    const form = _el('formSeguimiento');
    const titulo = _el('modalSeguimientoTitulo');
    const btnTexto = _el('btnSeguimientoTexto');
    const alertErrores = _el('alertErroresSeguimiento');
    
    // Resetear formulario
    form.reset();
    alertErrores.classList.add('d-none');
    
    if (seguimientoId) {
        // Modo EDITAR
        titulo.textContent = 'Editar Seguimiento';
        btnTexto.textContent = 'Actualizar Seguimiento';
        _el('seguimientoId').value = String(seguimientoId);
        
        // Cargar datos del seguimiento vía AJAX
        cargarDatosSeguimiento(seguimientoId);
    } else {
        // Modo AGREGAR
        titulo.textContent = 'Agregar Seguimiento';
        btnTexto.textContent = 'Agregar Seguimiento';
        _el('seguimientoId').value = '';
        
        // Establecer fecha de hoy por defecto
        const hoy = new Date().toISOString().split('T')[0];
        _el('fecha_pedido').value = hoy;
    }
    
    modal.show();
}

/**
 * Carga los datos de un seguimiento existente en el formulario.
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta función es la que soluciona el problema de edición.
 * Cuando haces clic en "Editar", esta función:
 * 1. Hace una petición al servidor (fetch) pidiendo los datos del seguimiento
 * 2. El servidor responde con un JSON que contiene toda la información
 * 3. La función toma cada campo del JSON y lo coloca en el formulario
 * 
 * Es como copiar datos de una hoja a otra: lee de la base de datos
 * y los pega en los campos del formulario para que puedas editarlos.
 * 
 * @param {number} seguimientoId - ID del seguimiento a cargar
 */
async function cargarDatosSeguimiento(seguimientoId: number) {
    try {
        // Construir la URL para obtener los datos
        const url = config.urls.obtenerSeguimiento.replace('/0/', `/${seguimientoId}/`);
        
        // Hacer la petición al servidor
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            const seg = data.seguimiento;
            
            // Poblar los campos del formulario con los datos recibidos
            // IMPORTANTE: Django agrega el prefijo 'id_' a los campos del formulario
            _el('id_proveedor').value = seg.proveedor;
            _el('descripcion_piezas').value = seg.descripcion_piezas;
            _el('numero_pedido').value = seg.numero_pedido;
            _el('fecha_pedido').value = seg.fecha_pedido;
            _el('fecha_entrega_estimada').value = seg.fecha_entrega_estimada;
            _el('fecha_entrega_real').value = seg.fecha_entrega_real;
            _el('estado').value = seg.estado;
            _el('notas_seguimiento').value = seg.notas_seguimiento;
            
            // Cargar piezas seleccionadas (checkboxes)
            // Primero, desmarcar todas las piezas
            _qsa('input[name="piezas"]').forEach(checkbox => {
                checkbox.checked = false;
            });
            
            // Luego, marcar solo las piezas que pertenecen a este seguimiento
            seg.piezas.forEach((piezaId: number) => {
                const checkbox = _qs(`input[name="piezas"][value="${piezaId}"]`);
                if (checkbox) {
                    checkbox.checked = true;
                }
            });
            
        } else {
            mostrarToast(data.error || 'Error al cargar datos del seguimiento', 'danger');
        }
        
    } catch (error) {
        console.error('Error al cargar seguimiento:', error);
        mostrarToast('Error de conexión al cargar datos', 'danger');
    }
}

/**
 * Guarda un seguimiento (agregar o editar)
 */
_el('formSeguimiento')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const seguimientoId = _el('seguimientoId').value;
    const formData = new FormData(this as unknown as HTMLFormElement);
    const alertErrores = _el('alertErroresSeguimiento');
    const listaErrores = _el('listaErroresSeguimiento');
    
    // Determinar URL
    let url;
    if (seguimientoId) {
        url = config.urls.editarSeguimiento.replace('/0/', `/${seguimientoId}/`);
    } else {
        url = config.urls.agregarSeguimiento;
    }
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCsrfToken()
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            bootstrap.Modal.getInstance(_el('modalSeguimiento'))?.hide();
            mostrarToast(data.message, 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            listaErrores.innerHTML = '';
            if (data.errors) {
                Object.entries(data.errors).forEach(([field, error]) => {
                    const li = document.createElement('li');
                    li.textContent = `${field}: ${error}`;
                    listaErrores.appendChild(li);
                });
            } else if (data.error) {
                const li = document.createElement('li');
                li.textContent = data.error;
                listaErrores.appendChild(li);
            }
            alertErrores.classList.remove('d-none');
        }
    } catch (error) {
        console.error('Error:', error);
        mostrarToast('Error de conexión', 'danger');
    }
});

/**
 * Edita un seguimiento existente
 */
function editarSeguimiento(seguimientoId: number) {
    abrirModalSeguimiento(seguimientoId);
}

/**
 * Elimina un seguimiento
 */
async function eliminarSeguimiento(seguimientoId: number) {
    if (!confirm('¿Estás seguro de eliminar este seguimiento?')) {
        return;
    }
    
    const url = config.urls.eliminarSeguimiento.replace('/0/', `/${seguimientoId}/`);
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            mostrarToast(data.message, 'success');
            
            // Eliminar la card
            const card = _qs(`[data-seguimiento-id="${seguimientoId}"]`).closest('.col-md-6');
            if (card) {
                card.remove();
            }
            
            setTimeout(() => location.reload(), 1000);
        } else {
            mostrarToast(data.error || 'Error al eliminar', 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        mostrarToast('Error de conexión', 'danger');
    }
}

/**
 * Marca una pieza como recibida
 */
// ============================================================================
// CAMBIO RÁPIDO DE ESTADO DE SEGUIMIENTO
// ============================================================================

/**
 * Cambia el estado de un seguimiento de pieza sin necesidad de editar todo el formulario.
 * 
 * EXPLICACIÓN:
 * Permite cambios rápidos de estado: pedido → confirmado → transito → retrasado → recibido
 * Útil para actualizar el progreso del pedido sin entrar al modal de edición completo.
 * 
 * @param {number} seguimientoId - ID del seguimiento a actualizar
 * @param {string} nuevoEstado - Nuevo estado (confirmado, transito, retrasado)
 */
async function cambiarEstadoSeguimiento(seguimientoId: number, nuevoEstado: string) {
    // Mensajes de confirmación según el estado
    const mensajes: Record<string, string> = {
        'confirmado': '¿Confirmar que el proveedor aceptó el pedido?',
        'transito': '¿Marcar el pedido como En Tránsito?',
        'retrasado': '¿Marcar este pedido como Retrasado?'
    };
    
    const estadosNombres: Record<string, string> = {
        'confirmado': 'Confirmado',
        'transito': 'En Tránsito',
        'retrasado': 'Retrasado'
    };
    
    if (!confirm(mensajes[nuevoEstado] || '¿Cambiar el estado?')) {
        return;
    }
    
    const url = config.urls.cambiarEstadoSeguimiento.replace('/0/', `/${seguimientoId}/`);
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    formData.append('nuevo_estado', nuevoEstado);
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            mostrarToast(`✅ Estado actualizado a: ${estadosNombres[nuevoEstado]}`, 'success');
            
            // Actualizar el card visualmente (sin recargar toda la página)
            const card = _qs(`.seguimiento-card[data-seguimiento-id="${seguimientoId}"]`);
            if (card && data.card_html) {
                card.outerHTML = data.card_html;
            } else {
                // Fallback: recargar página
                setTimeout(() => location.reload(), 1000);
            }
        } else {
            mostrarToast(data.error || 'Error al cambiar estado', 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        mostrarToast('Error de conexión', 'danger');
    }
}

// ============================================================================
// MARCAR SEGUIMIENTO COMO RECIBIDO
// ============================================================================

/**
 * Marca una pieza como recibida con opción de enviar o no el correo.
 * 
 * MEJORA (Enero 2026):
 * Ahora pregunta al usuario si desea enviar el correo de notificación,
 * ya que hay casos donde el técnico ya está informado y no es necesario.
 * 
 * @param {number} seguimientoId - ID del seguimiento de la pieza
 */
async function marcarRecibido(seguimientoId: number) {
    // Paso 1: Solicitar fecha de entrega real
    const fechaReal = prompt('Fecha de entrega real (YYYY-MM-DD):', new Date().toISOString().split('T')[0]);
    
    if (!fechaReal) return; // Usuario canceló
    
    // Paso 2: Preguntar si desea enviar correo de notificación
    const enviarEmail = confirm(
        '📧 ¿Deseas enviar email de notificación al técnico?\n\n' +
        'Selecciona:\n' +
        '• OK = Enviar email (recomendado)\n' +
        '• CANCELAR = Omitir envío (si el técnico ya está informado)'
    );
    
    // Paso 3: Preparar datos para enviar al servidor
    const url = config.urls.marcarRecibido.replace('/0/', `/${seguimientoId}/`);
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    formData.append('fecha_entrega_real', fechaReal);
    formData.append('enviar_email', enviarEmail ? 'true' : 'false'); // Nuevo parámetro
    
    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        // Procesar respuesta
        if (data.success) {
            // Mostrar mensaje contextual según si se envió email o no
            let mensajeFinal = data.message;
            
            if (data.email_omitido) {
                mensajeFinal += ' (Email omitido por decisión del usuario)';
            }
            
            mostrarToast(mensajeFinal, 'success');
            setTimeout(() => location.reload(), 1500);
        } else {
            mostrarToast(data.error || 'Error al marcar como recibido', 'danger');
        }
    } catch (error) {
        console.error('Error:', error);
        mostrarToast('Error de conexión', 'danger');
    }
}

/**
 * Reenvía la notificación de pieza recibida al técnico
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta función permite reintentar el envío del email cuando el envío original falló.
 * Por ejemplo, si hubo un problema con el servidor de correo o el email del técnico
 * estaba mal configurado, se puede corregir y luego usar este botón para reenviar.
 * 
 * MEJORA (Enero 2026):
 * Ahora pregunta si realmente desea enviar el correo, permitiendo cancelar si no es necesario.
 * 
 * @param {number} seguimientoId - ID del seguimiento de la pieza recibida
 */
async function reenviarNotificacion(seguimientoId: number) {
    // Confirmación mejorada con opción de omitir envío
    const enviarEmail = confirm(
        '📧 ¿Deseas reenviar el email de notificación al técnico?\n\n' +
        'Selecciona:\n' +
        '• OK = Reenviar email\n' +
        '• CANCELAR = No enviar (si ya no es necesario)'
    );
    
    if (!enviarEmail) {
        // Usuario decidió NO reenviar
        mostrarToast('✓ Reenvío de email cancelado por el usuario', 'info');
        return;
    }
    
    // Construir URL de reenvío
    const url = config.urls.reenviarNotificacion.replace('/0/', `/${seguimientoId}/`);
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    
    try {
        // Mostrar indicador de carga
        mostrarToast('📧 Reenviando notificación...', 'info');
        
        // Realizar petición AJAX
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        // Procesar respuesta
        if (data.success) {
            // Mensaje contextual
            const mensaje = data.email_omitido 
                ? '✓ Email no enviado (omitido por decisión del usuario)'
                : '✅ Notificación reenviada exitosamente';
            
            mostrarToast(mensaje, data.email_omitido ? 'info' : 'success');
            
            if (!data.email_omitido) {
                setTimeout(() => location.reload(), 2000);
            }
        } else {
            mostrarToast(data.error || 'Error al reenviar', 'danger');
        }
    } catch (error) {
        console.error('Error al reenviar notificación:', error);
        mostrarToast('❌ Error de conexión al reenviar', 'danger');
    }
}

/**
 * Marca una pieza como INCORRECTA (WPB - Wrong Part Boxed)
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * ================================
 * Se usa cuando la pieza recibida NO es la correcta:
 * - El proveedor envió la pieza equivocada
 * - No es compatible con el equipo
 * - No cumple las especificaciones
 * 
 * IMPORTANTE: Después de marcar como incorrecta, debes crear
 * un NUEVO seguimiento para pedir la pieza correcta.
 * 
 * @param {number} seguimientoId - ID del seguimiento de la pieza
 */
async function marcarIncorrecto(seguimientoId: number) {
    // Doble confirmación para evitar errores
    const confirmacion = confirm(
        '⚠️ ¿Estás seguro de marcar esta pieza como INCORRECTA?\n\n' +
        'Esto indica que el proveedor envió la pieza equivocada.\n' +
        'Deberás crear un NUEVO pedido para la pieza correcta.\n\n' +
        '¿Continuar?'
    );
    
    if (!confirmacion) return;
    
    // Construir URL
    const url = config.urls.marcarIncorrecta.replace('/0/', `/${seguimientoId}/`);
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    
    try {
        // Mostrar indicador de carga
        mostrarToast('📝 Registrando pieza incorrecta...', 'info');
        
        // Realizar petición AJAX
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        // Procesar respuesta
        if (data.success) {
            mostrarToast(data.message, 'warning');
            
            // Actualizar el card visualmente
            const card = _qs(`.seguimiento-card[data-seguimiento-id="${seguimientoId}"]`);
            if (card && data.seguimiento_html) {
                card.outerHTML = data.seguimiento_html;
            } else {
                // Fallback: recargar página
                setTimeout(() => location.reload(), 1500);
            }
        } else {
            mostrarToast(data.error || 'Error al marcar como incorrecta', 'danger');
        }
    } catch (error) {
        console.error('Error al marcar pieza incorrecta:', error);
        mostrarToast('❌ Error de conexión', 'danger');
    }
}

/**
 * Marca una pieza como DAÑADA o NO FUNCIONAL (DOA - Dead On Arrival)
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * ================================
 * Se usa cuando la pieza recibida está DAÑADA o NO FUNCIONA:
 * - Llegó físicamente dañada (rota, golpeada)
 * - No funciona al probarla (defecto de fábrica)
 * - Tiene problemas técnicos que la hacen inservible
 * 
 * IMPORTANTE: Después de marcar como dañada, debes:
 * 1. Solicitar reemplazo al proveedor (garantía)
 * 2. Crear un NUEVO seguimiento para el reemplazo
 * 
 * @param {number} seguimientoId - ID del seguimiento de la pieza
 */
async function marcarDanado(seguimientoId: number) {
    // Doble confirmación para evitar errores
    const confirmacion = confirm(
        '⚠️ ¿Estás seguro de marcar esta pieza como DAÑADA/NO FUNCIONAL?\n\n' +
        'Esto indica que la pieza llegó dañada o no funciona.\n' +
        'Deberás solicitar reemplazo al proveedor.\n\n' +
        '¿Continuar?'
    );
    
    if (!confirmacion) return;
    
    // Construir URL
    const url = config.urls.marcarDanada.replace('/0/', `/${seguimientoId}/`);
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    
    try {
        // Mostrar indicador de carga
        mostrarToast('📝 Registrando pieza dañada...', 'info');
        
        // Realizar petición AJAX
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        // Procesar respuesta
        if (data.success) {
            mostrarToast(data.message, 'warning');
            
            // Actualizar el card visualmente
            const card = _qs(`.seguimiento-card[data-seguimiento-id="${seguimientoId}"]`);
            if (card && data.seguimiento_html) {
                card.outerHTML = data.seguimiento_html;
            } else {
                // Fallback: recargar página
                setTimeout(() => location.reload(), 1500);
            }
        } else {
            mostrarToast(data.error || 'Error al marcar como dañada', 'danger');
        }
    } catch (error) {
        console.error('Error al marcar pieza dañada:', error);
        mostrarToast('❌ Error de conexión', 'danger');
    }
}

/**
 * Función helper para mostrar notificaciones toast
 */
function mostrarToast(mensaje: string, tipo: string = 'info') {
    // Crear elemento de alerta temporal
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${tipo} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    alertDiv.innerHTML = `
        ${mensaje}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Auto-ocultar después de 3 segundos
    setTimeout(() => {
        alertDiv.remove();
    }, 3000);
}

// ============================================================================
// GESTIÓN DE SELECCIÓN DE PIEZAS EN COTIZACIÓN
// ============================================================================

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta sección maneja la selección de piezas cuando el cliente acepta/rechaza
 * una cotización. Permite seleccionar individualmente qué piezas se aceptan.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Solo ejecutar si existe el formulario de gestión de cotización
    const formGestionar = _el('formGestionarCotizacion');
    if (!formGestionar) return;
    
    // Elementos del DOM
    const checkboxSelectAll = _el('selectAllPiezas');
    const checkboxesPiezas = _qsa('.pieza-checkbox');
    const radioAceptar = _qs('input[name="accion"][value="aceptar"]');
    const radioRechazar = _qs('input[name="accion"][value="rechazar"]');
    const camposRechazo = _el('camposRechazo');
    
    // -------------------------------------------------------------------------
    // 1. FUNCIONALIDAD: Seleccionar/Deseleccionar todas las piezas
    // -------------------------------------------------------------------------
    if (checkboxSelectAll) {
        checkboxSelectAll.addEventListener('change', function(this: DomEl) {
            const isChecked = this.checked;
            checkboxesPiezas.forEach(checkbox => {
                checkbox.checked = isChecked;
            });
            
            // Actualizar visualmente las filas
            actualizarEstiloFilas();
        });
    }
    
    // Actualizar checkbox "Seleccionar todas" si se desmarca alguna pieza individual
    checkboxesPiezas.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            // Si todas están marcadas, marcar "Seleccionar todas"
            const todasMarcadas = Array.from(checkboxesPiezas).every(cb => cb.checked);
            if (checkboxSelectAll) {
                checkboxSelectAll.checked = todasMarcadas;
            }
            
            // Actualizar visualmente las filas
            actualizarEstiloFilas();
        });
    });
    
    // -------------------------------------------------------------------------
    // 2. FUNCIONALIDAD: Mostrar/ocultar campos de rechazo
    // -------------------------------------------------------------------------
    function actualizarCamposRechazo() {
        if (radioRechazar && radioRechazar.checked) {
            // Si rechaza, mostrar campos de rechazo
            if (camposRechazo) {
                camposRechazo.style.display = 'block';
            }
            
            // Deshabilitar checkboxes (no importan si rechaza todo)
            checkboxesPiezas.forEach(checkbox => {
                checkbox.disabled = true;
                checkbox.checked = false; // Desmarcar todas
            });
            if (checkboxSelectAll) {
                checkboxSelectAll.disabled = true;
                checkboxSelectAll.checked = false;
            }
        } else {
            // Si acepta o no ha decidido, ocultar campos de rechazo
            if (camposRechazo) {
                camposRechazo.style.display = 'none';
            }
            
            // Habilitar checkboxes
            checkboxesPiezas.forEach(checkbox => {
                checkbox.disabled = false;
            });
            if (checkboxSelectAll) {
                checkboxSelectAll.disabled = false;
                checkboxSelectAll.checked = true; // Marcar todas por defecto
            }
            
            // Marcar todas las piezas si acepta
            if (radioAceptar && radioAceptar.checked) {
                checkboxesPiezas.forEach(checkbox => {
                    checkbox.checked = true;
                });
            }
        }
        
        actualizarEstiloFilas();
    }
    
    // Escuchar cambios en los radio buttons
    if (radioAceptar) {
        radioAceptar.addEventListener('change', actualizarCamposRechazo);
    }
    if (radioRechazar) {
        radioRechazar.addEventListener('change', actualizarCamposRechazo);
    }
    
    // -------------------------------------------------------------------------
    // 3. FUNCIONALIDAD: Validación antes de enviar
    // -------------------------------------------------------------------------
    // 3. FUNCIONALIDAD: Validación antes de enviar
    // -------------------------------------------------------------------------
    formGestionar.addEventListener('submit', function(e) {
        const accionSeleccionada = _qs('input[name="accion"]:checked');
        
        if (!accionSeleccionada) {
            e.preventDefault();
            alert('❌ Por favor selecciona si el cliente acepta o rechaza la cotización.');
            return;
        }
        
        // Si acepta, procesar piezas seleccionadas (si existen)
        if (accionSeleccionada.value === 'aceptar') {
            const piezasSeleccionadas = Array.from(checkboxesPiezas).filter(cb => cb.checked);
            
            // NUEVO: Ya no se requiere que haya piezas seleccionadas
            // Se permite aceptar cotizaciones con solo mano de obra
            
            // CRÍTICO: Copiar los checkboxes al formulario antes de enviar (solo si hay piezas)
            // Los checkboxes están fuera del form, así que debemos clonarlos
            if (piezasSeleccionadas.length > 0) {
                piezasSeleccionadas.forEach(checkbox => {
                    const hiddenInput = document.createElement('input');
                    hiddenInput.type = 'hidden';
                    hiddenInput.name = 'piezas_seleccionadas';
                    hiddenInput.value = checkbox.value;
                    formGestionar.appendChild(hiddenInput);
                });
            }
            
            // Confirmación con resumen adaptado
            let mensaje;
            if (piezasSeleccionadas.length > 0) {
                mensaje = `¿Confirmar aceptación de ${piezasSeleccionadas.length} pieza(s)?`;
            } else if (checkboxesPiezas.length > 0) {
                // Hay piezas disponibles pero no seleccionó ninguna
                mensaje = '¿Confirmar aceptación de la cotización SIN piezas (solo mano de obra)?';
            } else {
                // No hay piezas en la cotización
                mensaje = '¿Confirmar aceptación de la cotización (solo mano de obra)?';
            }
            
            if (!confirm(mensaje)) {
                e.preventDefault();
                return;
            }
        }
        
        // Si rechaza, confirmar
        if (accionSeleccionada.value === 'rechazar') {
            if (!confirm('¿Estás seguro de rechazar TODA la cotización?')) {
                e.preventDefault();
                return;
            }
        }
    });
    
    // -------------------------------------------------------------------------
    // 4. HELPER: Actualizar estilos visuales de las filas
    // -------------------------------------------------------------------------
    function actualizarEstiloFilas() {
        checkboxesPiezas.forEach(checkbox => {
            const fila = checkbox.closest('tr');
            if (fila) {
                if (checkbox.checked && !checkbox.disabled) {
                    // Pieza seleccionada: resaltar con fondo verde claro
                    fila.style.backgroundColor = 'rgba(40, 167, 69, 0.1)';
                    fila.style.borderLeft = '4px solid #28a745';
                } else if (checkbox.disabled) {
                    // Rechazada: fondo gris
                    fila.style.backgroundColor = 'rgba(108, 117, 125, 0.1)';
                    fila.style.borderLeft = '4px solid #6c757d';
                } else {
                    // Desmarcada pero habilitada: fondo rojo claro
                    fila.style.backgroundColor = 'rgba(220, 53, 69, 0.1)';
                    fila.style.borderLeft = '4px solid #dc3545';
                }
            }
        });
    }
    
    // Inicializar estilos al cargar
    actualizarEstiloFilas();
    actualizarCamposRechazo();
});

// ============================================================================
// FUNCIÓN: ELIMINAR IMAGEN DE LA GALERÍA
// ============================================================================

/**
 * Confirma y elimina una imagen de la galería.
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Esta función maneja todo el proceso de eliminar una imagen:
 * 1. Muestra un cuadro de confirmación para evitar borrados accidentales
 * 2. Envía petición AJAX al servidor para eliminar imagen y archivos
 * 3. Si tiene éxito, elimina visualmente la tarjeta de la imagen del DOM
 * 4. Muestra feedback al usuario (éxito o error)
 * 
 * @param {number} imagenId - ID de la imagen a eliminar
 * @param {string} tipoImagen - Tipo de imagen (para mensaje de confirmación)
 * @param {Event} event - Evento del click (para prevenir propagación)
 */
function confirmarEliminarImagen(imagenId: number, tipoImagen: string, event: Event) {
    // Prevenir que se abra el lightbox al hacer click en eliminar
    event.stopPropagation();
    
    // Doble confirmación para seguridad
    const confirmacion = confirm(
        `⚠️ ¿Estás seguro de eliminar esta imagen de ${tipoImagen}?\n\n` +
        `Esta acción NO se puede deshacer.\n` +
        `Se eliminarán tanto la imagen comprimida como la original.`
    );
    
    if (!confirmacion) {
        return; // Usuario canceló
    }
    
    // Obtener el contenedor de la imagen para efectos visuales
    const contenedorImagen = _qs(`[data-imagen-id="${imagenId}"]`);
    const columnaPadre = contenedorImagen ? contenedorImagen.closest('.col-md-3') : null;
    
    // Mostrar feedback visual: desactivar botón y añadir spinner
    const btnEliminar = event.currentTarget as DomEl;
    const iconoOriginal = btnEliminar.innerHTML;
    btnEliminar.disabled = true;
    btnEliminar.innerHTML = '<span class="spinner-border spinner-border-sm"></span>';
    btnEliminar.style.opacity = '0.6';
    
    // Preparar datos para la petición
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', getCsrfToken());
    
    // URL de eliminación
    const url = config.urls.eliminarImagen.replace('/0/', `/${imagenId}/`);
    
    // Enviar petición AJAX
    fetch(url, {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Éxito: Mostrar mensaje y eliminar del DOM con animación
            mostrarToast(data.message || '✅ Imagen eliminada correctamente', 'success');
            
            // Animar salida y eliminar del DOM
            if (columnaPadre) {
                (columnaPadre as HTMLElement).style.transition = 'all 0.3s ease-out';
                (columnaPadre as HTMLElement).style.opacity = '0';
                (columnaPadre as HTMLElement).style.transform = 'scale(0.8)';
                
                setTimeout(() => {
                    columnaPadre.remove();
                    
                    // Verificar si ya no quedan imágenes en esta categoría
                    verificarCategoriasVacias();
                }, 300);
            }
        } else {
            // Error del servidor
            mostrarToast(data.error || '❌ Error al eliminar la imagen', 'danger');
            
            // Restaurar botón
            btnEliminar.disabled = false;
            btnEliminar.innerHTML = iconoOriginal;
            btnEliminar.style.opacity = '1';
        }
    })
    .catch(error => {
        // Error de red o JavaScript
        console.error('Error al eliminar imagen:', error);
        mostrarToast('❌ Error de conexión. Por favor intenta nuevamente.', 'danger');
        
        // Restaurar botón
        btnEliminar.disabled = false;
        btnEliminar.innerHTML = iconoOriginal;
        btnEliminar.style.opacity = '1';
    });
}

/**
 * Verifica si alguna categoría quedó sin imágenes y muestra mensaje apropiado.
 * 
 * EXPLICACIÓN:
 * Después de eliminar una imagen, revisamos si la categoría (tab) quedó vacía.
 * Si es así, mostramos un mensaje "No hay imágenes de [tipo] aún" en lugar
 * de dejar el espacio en blanco.
 */
function verificarCategoriasVacias() {
    const tabs = _qsa('.tab-pane');
    
    tabs.forEach(tab => {
        const imagenes = tab.querySelectorAll('.gallery-image-container');
        
        if (imagenes.length === 0) {
            // No quedan imágenes en esta categoría
            const tipoCategoria = tab.id; // El ID del tab es el tipo de imagen
            const nombreCategoria = tab.querySelector('.text-center')?.textContent || tipoCategoria;
            
            // Mostrar mensaje de categoría vacía
            tab.innerHTML = `
                <div class="text-center text-muted py-5">
                    <i class="bi bi-image" style="font-size: 3rem;"></i>
                    <p class="mt-2">No hay imágenes de ${tipoCategoria} aún.</p>
                </div>
            `;
        }
    });
}

// ============================================================================
// FEEDBACK VISUAL AL GUARDAR FECHAS DE DIAGNÓSTICO Y REPARACIÓN
// ============================================================================

/**
 * Agrega animación de guardado exitoso a las secciones de fechas.
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * - Cuando el formulario de configuración se guarda exitosamente
 * - Agregamos una animación "pulse" a las secciones de fechas
 * - Esto da feedback visual inmediato al usuario
 * - La animación dura 600ms y luego se remueve automáticamente
 */
document.addEventListener('DOMContentLoaded', function() {
    const formConfiguracion = _el('formConfiguracion');
    
    if (formConfiguracion) {
        formConfiguracion.addEventListener('submit', function(e) {
            // Guardar referencia a las secciones de fechas
            const seccionesFechas = _qsa('.fechas-seccion');
            
            // Agregar clase de guardado después de enviar el formulario
            // Nota: La animación solo se ve si la página no recarga inmediatamente
            seccionesFechas.forEach(seccion => {
                // Esperar un momento para que el formulario se procese
                setTimeout(() => {
                    seccion.classList.add('guardado-exitoso');
                    
                    // Remover la clase después de la animación (600ms)
                    setTimeout(() => {
                        seccion.classList.remove('guardado-exitoso');
                    }, 600);
                }, 100);
            });
        });
    }
    
    // Efecto visual al cambiar fechas
    const inputsFechas = _qsa(
        'input[name="fecha_inicio_diagnostico"], ' +
        'input[name="fecha_fin_diagnostico"], ' +
        'input[name="fecha_inicio_reparacion"], ' +
        'input[name="fecha_fin_reparacion"]'
    );
    
    inputsFechas.forEach(input => {
        // Agregar efecto de "cambio pendiente"
        input.addEventListener('change', function() {
            const seccion = this.closest('.fechas-seccion');
            if (seccion) {
                // Agregar borde pulsante para indicar cambio pendiente
                (seccion as HTMLElement).style.borderLeft = '4px solid #ffc107';
                (seccion as HTMLElement).style.paddingLeft = '8px';
                (seccion as HTMLElement).style.transition = 'all 0.3s ease';
                
                // Tooltip o mensaje visual
                const label = this.previousElementSibling;
                if (label && label.tagName === 'LABEL') {
                    const textoOriginal = label.innerHTML;
                    label.innerHTML = textoOriginal + ' <span class="badge bg-warning text-dark" style="font-size: 0.65rem;">Cambio pendiente</span>';
                    
                    // Limpiar el badge al hacer submit
                    formConfiguracion.addEventListener('submit', function() {
                        label.innerHTML = textoOriginal;
                        (seccion as HTMLElement).style.borderLeft = '';
                        (seccion as HTMLElement).style.paddingLeft = '';
                    }, { once: true });
                }
            }
        });
    });
});



    // EXPLICACIÓN PARA PRINCIPIANTES:
    // El HTML de los partials usa onclick="abrirModalPieza()" etc.
    // Al estar dentro de un IIFE esas funciones NO son globales;
    // las colgamos de window para que el onclick siga funcionando.
    const w = window as unknown as Record<string, unknown>;
    w['abrirModalPieza'] = abrirModalPieza;
    w['editarPieza'] = editarPieza;
    w['eliminarPieza'] = eliminarPieza;
    w['abrirModalSeguimiento'] = abrirModalSeguimiento;
    w['editarSeguimiento'] = editarSeguimiento;
    w['eliminarSeguimiento'] = eliminarSeguimiento;
    w['cambiarEstadoSeguimiento'] = cambiarEstadoSeguimiento;
    w['marcarRecibido'] = marcarRecibido;
    w['marcarIncorrecto'] = marcarIncorrecto;
    w['marcarDanado'] = marcarDanado;
    w['reenviarNotificacion'] = reenviarNotificacion;
    w['confirmarEliminarImagen'] = confirmarEliminarImagen;
    w['mostrarToast'] = mostrarToast;
    w['toggleCargadorFieldsModal'] = toggleCargadorFieldsModal;
})();
