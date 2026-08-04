/**
 * venta_mostrador.ts — AJAX de Ventas Mostrador en detalle de orden.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * --------------------------------
 * Antes vivía solo en static/js/venta_mostrador.js (JS suelto). Ahora la fuente
 * es este TypeScript y `pnpm run build` genera el .js.
 *
 * Qué hace:
 * - Modal de paquetes/servicios (crear VentaMostrador vía fetch).
 * - Modal de piezas (agregar / editar / eliminar).
 * - Validaciones de costos > 0 cuando un servicio está marcado.
 *
 * CSRF: usa window.getCsrfToken (static/ts/csrf.ts, cargado en base.html).
 *
 * El template llama funciones con onclick=...; por eso se publican en window
 * al final (mismo patrón que detalle_orden_page.ts).
 *
 * Efectos secundarios: POST a APIs de ST; recarga la página tras éxito.
 */

(function ventaMostradorMain(): void {
    // Bootstrap 5 global (CDN en base.html). Tipado local para no chocar con
    // otros declare const bootstrap del repo (p. ej. dashboard_rhitso.ts).
    type BsModalInstance = { show(): void; hide(): void };
    type BsApi = {
        Modal: {
            new (element: Element): BsModalInstance;
            getInstance(element: Element): BsModalInstance | null;
        };
        Alert: new (element: Element) => { close(): void };
    };
    const bootstrapApi = (window as unknown as { bootstrap: BsApi }).bootstrap;

    // ========================================================================
    // TIPOS Y CONSTANTES
    // ========================================================================

    type PaqueteKey = 'premium' | 'oro' | 'plata' | 'ninguno';

    interface ServicioCostoConfig {
        checkbox: string;
        div: string;
    }

    interface ServicioValidacionConfig {
        checkbox: string;
        input: string;
        nombre: string;
    }

    /** Respuesta JSON típica de las vistas AJAX de venta mostrador. */
    interface VentaMostradorApiResponse {
        success: boolean;
        message?: string;
        es_complemento?: boolean;
        errors?: string | Record<string, string | string[]>;
    }

    // Obtener el ID de la orden desde el pathname (mismo índice que el JS original).
    // No se cambia el parseo en esta migración para evitar regresiones.
    const ordenId: string = window.location.pathname.split('/')[3];

    const DESCRIPCIONES_PAQUETES: Record<PaqueteKey, string> = {
        premium: `
        <strong>🏆 SOLUCIÓN PREMIUM</strong><br>
        <ul class="mb-0 mt-2">
            <li>RAM 16GB DDR5 Samsung (4800-5600 MHz)</li>
            <li>SSD 1TB de alta velocidad</li>
            <li>Kit de Limpieza Profesional de REGALO</li>
            <li>Instalación y configuración incluida</li>
        </ul>
    `,
        oro: `
        <strong>🥇 SOLUCIÓN ORO</strong><br>
        <ul class="mb-0 mt-2">
            <li>RAM 8GB DDR5 Samsung (3200 MHz)</li>
            <li>SSD 1TB de alta velocidad</li>
            <li>Instalación y configuración incluida</li>
        </ul>
    `,
        plata: `
        <strong>🥈 SOLUCIÓN PLATA</strong><br>
        <ul class="mb-0 mt-2">
            <li>SSD 1TB de alta velocidad</li>
            <li>Instalación y configuración incluida</li>
        </ul>
    `,
        ninguno: '<em>Sin paquete adicional - Servicios individuales</em>',
    };

    const PRECIOS_SUGERIDOS_PAQUETES: Record<PaqueteKey, number> = {
        premium: 5500.0,
        oro: 3850.0,
        plata: 2900.0,
        ninguno: 0.0,
    };

    /** Token CSRF global (csrf.ts). */
    function csrfToken(): string {
        return window.getCsrfToken?.() ?? '';
    }

    function esPaqueteKey(valor: string): valor is PaqueteKey {
        return valor === 'premium' || valor === 'oro' || valor === 'plata' || valor === 'ninguno';
    }

    // ========================================================================
    // INICIALIZACIÓN
    // ========================================================================

    document.addEventListener('DOMContentLoaded', (): void => {
        console.log('✅ Venta Mostrador TS inicializado para orden:', ordenId);
        inicializarEventListeners();
        calcularSubtotalPiezaVentaMostrador();
    });

    function inicializarEventListeners(): void {
        const selectPaquete = document.getElementById('id_paquete_venta');
        if (selectPaquete) {
            selectPaquete.addEventListener('change', mostrarDescripcionPaquete);
            mostrarDescripcionPaquete();
        }

        const checkboxes: ServicioCostoConfig[] = [
            { checkbox: 'id_incluye_cambio_pieza', div: 'divCostoCambioPieza' },
            { checkbox: 'id_incluye_limpieza', div: 'divCostoLimpieza' },
            { checkbox: 'id_incluye_kit_limpieza', div: 'divCostoKit' },
            { checkbox: 'id_incluye_reinstalacion_so', div: 'divCostoReinstalacion' },
            { checkbox: 'id_incluye_respaldo', div: 'divCostoRespaldo' },
        ];

        checkboxes.forEach((item: ServicioCostoConfig): void => {
            const checkbox = document.getElementById(item.checkbox);
            if (checkbox) {
                checkbox.addEventListener('change', (): void => {
                    toggleCampoCosto(item.checkbox, item.div);
                });
                toggleCampoCosto(item.checkbox, item.div);
            }
        });

        const inputCantidad = document.getElementById('id_cantidad');
        const inputPrecio = document.getElementById('id_precio_unitario');

        if (inputCantidad) {
            inputCantidad.addEventListener('input', calcularSubtotalPiezaVentaMostrador);
        }
        if (inputPrecio) {
            inputPrecio.addEventListener('input', calcularSubtotalPiezaVentaMostrador);
        }

        const formVentaMostrador = document.getElementById('formVentaMostrador');
        if (formVentaMostrador) {
            formVentaMostrador.addEventListener('submit', (e: Event): void => {
                e.preventDefault();
                guardarVentaMostrador();
            });
        }

        const formPiezaVentaMostrador = document.getElementById('formPiezaVentaMostrador');
        if (formPiezaVentaMostrador) {
            formPiezaVentaMostrador.addEventListener('submit', (e: Event): void => {
                e.preventDefault();
                guardarPiezaVentaMostrador();
            });
        }
    }

    // ========================================================================
    // UI — DESCRIPCIÓN DE PAQUETE / COSTOS
    // ========================================================================

    /**
     * Muestra la descripción del paquete seleccionado y sugiere precio editable.
     */
    function mostrarDescripcionPaquete(): void {
        const selectPaquete = document.getElementById('id_paquete_venta') as HTMLSelectElement | null;
        const divDescripcion = document.getElementById('descripcionPaquete');
        const textoDescripcion = document.getElementById('textoPaquete');
        const divCostoPaquete = document.getElementById('divCostoPaquete');
        const inputCostoPaquete = document.getElementById('id_costo_paquete') as HTMLInputElement | null;

        if (!selectPaquete || !divDescripcion || !textoDescripcion) return;

        const paqueteSeleccionado = selectPaquete.value;

        if (
            paqueteSeleccionado &&
            paqueteSeleccionado !== 'ninguno' &&
            esPaqueteKey(paqueteSeleccionado) &&
            DESCRIPCIONES_PAQUETES[paqueteSeleccionado]
        ) {
            textoDescripcion.innerHTML = DESCRIPCIONES_PAQUETES[paqueteSeleccionado];
            divDescripcion.style.display = 'block';

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

            if (divCostoPaquete) divCostoPaquete.style.display = 'none';
            if (inputCostoPaquete) {
                inputCostoPaquete.required = false;
                inputCostoPaquete.value = '0.00';
                inputCostoPaquete.classList.remove('is-invalid');
            }
        }
    }

    /**
     * Muestra u oculta campo de costo según checkbox.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Si marcas un servicio, el input de costo se vuelve obligatorio y > 0.
     * Si lo desmarcas, se oculta y se manda 0.00 en el POST.
     */
    function toggleCampoCosto(checkboxId: string, divId: string): void {
        const checkbox = document.getElementById(checkboxId) as HTMLInputElement | null;
        const div = document.getElementById(divId);

        if (!checkbox || !div) return;

        const input = div.querySelector('input[type="number"]') as HTMLInputElement | null;

        if (checkbox.checked) {
            div.style.display = 'block';
            if (input) {
                input.required = true;
                input.min = '0.01';
                input.step = '0.01';

                input.addEventListener('input', function (this: HTMLInputElement): void {
                    const valor = parseFloat(this.value) || 0;
                    if (valor <= 0) {
                        this.setCustomValidity('El costo debe ser mayor a $0.00');
                        this.classList.add('is-invalid');
                    } else {
                        this.setCustomValidity('');
                        this.classList.remove('is-invalid');
                    }
                });

                if (input.value) {
                    input.dispatchEvent(new Event('input'));
                }
            }
        } else {
            div.style.display = 'none';
            if (input) {
                input.required = false;
                input.min = '';
                input.value = '0.00';
                input.setCustomValidity('');
                input.classList.remove('is-invalid');
            }
        }
    }

    /** Wrappers históricos (por si algún template legacy los llama). */
    function toggleCambioPiezaCosto(): void {
        toggleCampoCosto('id_incluye_cambio_pieza', 'divCostoCambioPieza');
    }

    function toggleLimpiezaCosto(): void {
        toggleCampoCosto('id_incluye_limpieza', 'divCostoLimpieza');
    }

    function toggleKitCosto(): void {
        toggleCampoCosto('id_incluye_kit_limpieza', 'divCostoKit');
    }

    function toggleReinstalacionCosto(): void {
        toggleCampoCosto('id_incluye_reinstalacion_so', 'divCostoReinstalacion');
    }

    function toggleRespaldoCosto(): void {
        toggleCampoCosto('id_incluye_respaldo', 'divCostoRespaldo');
    }

    // ========================================================================
    // CÁLCULOS
    // ========================================================================

    function calcularSubtotalPiezaVentaMostrador(): void {
        const inputCantidad = document.getElementById('id_cantidad') as HTMLInputElement | null;
        const inputPrecio = document.getElementById('id_precio_unitario') as HTMLInputElement | null;
        const spanSubtotal = document.getElementById('subtotalPiezaVentaMostrador');

        if (!inputCantidad || !inputPrecio || !spanSubtotal) return;

        const cantidad = parseFloat(inputCantidad.value) || 0;
        const precio = parseFloat(inputPrecio.value) || 0;
        const subtotal = cantidad * precio;

        spanSubtotal.textContent = formatearMoneda(subtotal);
    }

    // ========================================================================
    // MODAL: VENTA MOSTRADOR
    // ========================================================================

    function abrirModalVentaMostrador(): void {
        const modalEl = document.getElementById('modalVentaMostrador');
        if (!modalEl) return;

        const modal = new bootstrapApi.Modal(modalEl);
        const form = document.getElementById('formVentaMostrador') as HTMLFormElement | null;

        if (form) form.reset();

        const divCostoPaquete = document.getElementById('divCostoPaquete');
        if (divCostoPaquete) divCostoPaquete.style.display = 'none';

        const alertErrores = document.getElementById('alertErroresVentaMostrador');
        if (alertErrores) alertErrores.classList.add('d-none');

        modal.show();
    }

    /**
     * Guarda la venta mostrador (CREATE).
     * Valida que servicios marcados tengan costo > 0 antes del fetch.
     */
    function guardarVentaMostrador(): void {
        const form = document.getElementById('formVentaMostrador') as HTMLFormElement | null;
        if (!form) return;

        const formData = new FormData(form);

        const selectPaquete = document.getElementById('id_paquete_venta') as HTMLSelectElement | null;
        const paquete = selectPaquete?.value ?? '';
        if (!paquete) {
            mostrarAlerta('Por favor selecciona un paquete', 'danger');
            return;
        }

        if (paquete !== 'ninguno') {
            const inputCostoPaquete = document.getElementById('id_costo_paquete') as HTMLInputElement | null;
            const costoPaquete = parseFloat(inputCostoPaquete ? inputCostoPaquete.value : '0') || 0;
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

        const servicios: ServicioValidacionConfig[] = [
            { checkbox: 'id_incluye_cambio_pieza', input: 'id_costo_cambio_pieza', nombre: 'Cambio de Pieza' },
            { checkbox: 'id_incluye_limpieza', input: 'id_costo_limpieza', nombre: 'Limpieza' },
            { checkbox: 'id_incluye_kit_limpieza', input: 'id_costo_kit', nombre: 'Kit de Limpieza' },
            { checkbox: 'id_incluye_reinstalacion_so', input: 'id_costo_reinstalacion', nombre: 'Reinstalación SO' },
            { checkbox: 'id_incluye_respaldo', input: 'id_costo_respaldo', nombre: 'Respaldo de Información' },
        ];

        for (const servicio of servicios) {
            const checkbox = document.getElementById(servicio.checkbox) as HTMLInputElement | null;
            const input = document.getElementById(servicio.input) as HTMLInputElement | null;

            if (checkbox && checkbox.checked && input) {
                const costo = parseFloat(input.value);

                if (!input.value || isNaN(costo)) {
                    mostrarAlerta(
                        `⚠️ El servicio "${servicio.nombre}" está marcado pero no tiene un costo válido. ` +
                            `Por favor ingresa un valor mayor a $0.00`,
                        'danger',
                    );
                    input.focus();
                    input.classList.add('is-invalid');
                    return;
                }

                if (costo <= 0) {
                    mostrarAlerta(
                        `⚠️ El costo de "${servicio.nombre}" debe ser mayor a $0.00. ` +
                            `Valor ingresado: $${costo.toFixed(2)}`,
                        'danger',
                    );
                    input.focus();
                    input.classList.add('is-invalid');
                    return;
                }

                input.classList.remove('is-invalid');
            }
        }

        const btnSubmit = form.querySelector('button[type="submit"]') as HTMLButtonElement | null;
        if (!btnSubmit) return;

        const textoOriginal = btnSubmit.innerHTML;
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';

        fetch(`/servicio-tecnico/ordenes/${ordenId}/venta-mostrador/crear/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken(),
            },
            body: formData,
        })
            .then((response: Response): Promise<VentaMostradorApiResponse> => response.json())
            .then((data: VentaMostradorApiResponse): void => {
                if (data.success) {
                    let mensaje = data.message ?? 'Guardado';
                    if (data.es_complemento) {
                        mensaje += ' ✨ (Ventas adicionales registradas)';
                    }

                    mostrarAlerta(mensaje, 'success');

                    const modalEl = document.getElementById('modalVentaMostrador');
                    if (modalEl) {
                        const modal = bootstrapApi.Modal.getInstance(modalEl);
                        if (modal) modal.hide();
                    }

                    setTimeout((): void => {
                        window.location.reload();
                    }, 1000);
                } else {
                    mostrarErroresFormulario(
                        data.errors,
                        'listaErroresVentaMostrador',
                        'alertErroresVentaMostrador',
                    );
                    btnSubmit.disabled = false;
                    btnSubmit.innerHTML = textoOriginal;
                }
            })
            .catch((error: unknown): void => {
                console.error('Error:', error);
                mostrarAlerta('Error al guardar la venta mostrador. Por favor intenta nuevamente.', 'danger');
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = textoOriginal;
            });
    }

    // ========================================================================
    // MODAL: PIEZA VENTA MOSTRADOR
    // ========================================================================

    function abrirModalPiezaVentaMostrador(esEdicion: boolean = false, piezaId: number | null = null): void {
        const modalEl = document.getElementById('modalPiezaVentaMostrador');
        if (!modalEl) return;

        const modal = new bootstrapApi.Modal(modalEl);
        const form = document.getElementById('formPiezaVentaMostrador') as HTMLFormElement | null;
        const titulo = document.getElementById('modalPiezaVentaMostradorTitulo');
        const btnTexto = document.getElementById('btnPiezaVentaMostradorTexto');
        const piezaIdInput = document.getElementById('piezaVentaMostradorId') as HTMLInputElement | null;

        if (form) form.reset();

        const alertErrores = document.getElementById('alertErroresPiezaVentaMostrador');
        if (alertErrores) alertErrores.classList.add('d-none');

        if (esEdicion && piezaId && titulo && btnTexto && piezaIdInput) {
            titulo.textContent = 'Editar Pieza';
            btnTexto.textContent = 'Guardar Cambios';
            piezaIdInput.value = String(piezaId);
            cargarDatosPiezaVentaMostrador(piezaId);
        } else {
            if (titulo) titulo.textContent = 'Agregar Pieza';
            if (btnTexto) btnTexto.textContent = 'Agregar Pieza';
            if (piezaIdInput) piezaIdInput.value = '';
            calcularSubtotalPiezaVentaMostrador();
        }

        modal.show();
    }

    function cargarDatosPiezaVentaMostrador(piezaId: number): void {
        const fila = document.querySelector(
            `#tablaPiezasVentaMostrador tr[data-pieza-id="${piezaId}"]`,
        );
        if (!fila) {
            console.error('No se encontró la fila de la pieza');
            return;
        }

        const celdas = fila.querySelectorAll('td');
        const strongEl = celdas[0]?.querySelector('strong');
        if (!strongEl || !celdas[2] || !celdas[3]) {
            console.error('Estructura de fila de pieza inesperada');
            return;
        }

        const descripcion = (strongEl.textContent ?? '').trim();
        const cantidad = parseInt((celdas[2].textContent ?? '').trim(), 10);
        const precioUnitario = parseFloat(
            (celdas[3].textContent ?? '').replace('$', '').replace(',', ''),
        );

        const descInput = document.getElementById('id_descripcion_pieza') as HTMLInputElement | null;
        const cantInput = document.getElementById('id_cantidad') as HTMLInputElement | null;
        const precioInput = document.getElementById('id_precio_unitario') as HTMLInputElement | null;

        if (descInput) descInput.value = descripcion;
        if (cantInput) cantInput.value = String(cantidad);
        if (precioInput) precioInput.value = precioUnitario.toFixed(2);

        calcularSubtotalPiezaVentaMostrador();
    }

    function guardarPiezaVentaMostrador(): void {
        const form = document.getElementById('formPiezaVentaMostrador') as HTMLFormElement | null;
        if (!form) return;

        const formData = new FormData(form);
        const piezaIdInput = document.getElementById('piezaVentaMostradorId') as HTMLInputElement | null;
        const piezaId = piezaIdInput?.value ?? '';

        const descEl = document.getElementById('id_descripcion_pieza') as HTMLInputElement | null;
        const cantEl = document.getElementById('id_cantidad') as HTMLInputElement | null;
        const precioEl = document.getElementById('id_precio_unitario') as HTMLInputElement | null;

        const descripcion = (descEl?.value ?? '').trim();
        const cantidad = parseInt(cantEl?.value ?? '0', 10) || 0;
        const precio = parseFloat(precioEl?.value ?? '0') || 0;

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

        let url: string;
        const method = 'POST';

        if (piezaId) {
            url = `/servicio-tecnico/venta-mostrador/piezas/${piezaId}/editar/`;
        } else {
            url = `/servicio-tecnico/ordenes/${ordenId}/venta-mostrador/piezas/agregar/`;
        }

        const btnSubmit = form.querySelector('button[type="submit"]') as HTMLButtonElement | null;
        if (!btnSubmit) return;

        const textoOriginal = btnSubmit.innerHTML;
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Guardando...';

        fetch(url, {
            method: method,
            headers: {
                'X-CSRFToken': csrfToken(),
            },
            body: formData,
        })
            .then((response: Response): Promise<VentaMostradorApiResponse> => response.json())
            .then((data: VentaMostradorApiResponse): void => {
                if (data.success) {
                    mostrarAlerta(data.message ?? 'Guardado', 'success');

                    const modalEl = document.getElementById('modalPiezaVentaMostrador');
                    if (modalEl) {
                        const modal = bootstrapApi.Modal.getInstance(modalEl);
                        if (modal) modal.hide();
                    }

                    setTimeout((): void => {
                        window.location.reload();
                    }, 800);
                } else {
                    mostrarErroresFormulario(
                        data.errors,
                        'listaErroresPiezaVentaMostrador',
                        'alertErroresPiezaVentaMostrador',
                    );
                    btnSubmit.disabled = false;
                    btnSubmit.innerHTML = textoOriginal;
                }
            })
            .catch((error: unknown): void => {
                console.error('Error:', error);
                mostrarAlerta('Error al guardar la pieza. Por favor intenta nuevamente.', 'danger');
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = textoOriginal;
            });
    }

    function editarPiezaVentaMostrador(piezaId: number): void {
        abrirModalPiezaVentaMostrador(true, piezaId);
    }

    function eliminarPiezaVentaMostrador(piezaId: number): void {
        if (!confirm('¿Estás seguro de eliminar esta pieza? Esta acción no se puede deshacer.')) {
            return;
        }

        fetch(`/servicio-tecnico/venta-mostrador/piezas/${piezaId}/eliminar/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken(),
            },
        })
            .then((response: Response): Promise<VentaMostradorApiResponse> => response.json())
            .then((data: VentaMostradorApiResponse): void => {
                if (data.success) {
                    mostrarAlerta(data.message ?? 'Eliminado', 'success');
                    setTimeout((): void => {
                        window.location.reload();
                    }, 800);
                } else {
                    mostrarAlerta(data.message || 'Error al eliminar la pieza', 'danger');
                }
            })
            .catch((error: unknown): void => {
                console.error('Error:', error);
                mostrarAlerta('Error al eliminar la pieza. Por favor intenta nuevamente.', 'danger');
            });
    }

    // ========================================================================
    // HELPERS
    // ========================================================================

    function formatearMoneda(valor: number): string {
        return (
            '$' +
            parseFloat(String(valor))
                .toFixed(2)
                .replace(/\d(?=(\d{3})+\.)/g, '$&,')
        );
    }

    function mostrarAlerta(mensaje: string, tipo: string = 'info'): void {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${tipo} alert-dismissible fade show position-fixed top-0 start-50 translate-middle-x mt-3`;
        alertDiv.style.zIndex = '9999';
        alertDiv.style.minWidth = '300px';
        alertDiv.innerHTML = `
        ${mensaje}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;

        document.body.appendChild(alertDiv);

        setTimeout((): void => {
            const bsAlert = new bootstrapApi.Alert(alertDiv);
            bsAlert.close();
        }, 5000);
    }

    function mostrarErroresFormulario(
        errors: string | Record<string, string | string[]> | undefined,
        listaId: string,
        alertId: string,
    ): void {
        const lista = document.getElementById(listaId);
        const alert = document.getElementById(alertId);

        if (!lista || !alert) return;

        lista.innerHTML = '';

        if (errors && typeof errors === 'object') {
            for (const [campo, mensajes] of Object.entries(errors)) {
                if (Array.isArray(mensajes)) {
                    mensajes.forEach((mensaje: string): void => {
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
            li.textContent = typeof errors === 'string' ? errors : 'Error de validación';
            lista.appendChild(li);
        }

        alert.classList.remove('d-none');
        alert.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    // ========================================================================
    // API PÚBLICA (onclick del template)
    // ========================================================================

    window.abrirModalVentaMostrador = abrirModalVentaMostrador;
    window.abrirModalPiezaVentaMostrador = abrirModalPiezaVentaMostrador;
    window.editarPiezaVentaMostrador = editarPiezaVentaMostrador;
    window.eliminarPiezaVentaMostrador = eliminarPiezaVentaMostrador;
    window.toggleCambioPiezaCosto = toggleCambioPiezaCosto;
    window.toggleLimpiezaCosto = toggleLimpiezaCosto;
    window.toggleKitCosto = toggleKitCosto;
    window.toggleReinstalacionCosto = toggleReinstalacionCosto;
    window.toggleRespaldoCosto = toggleRespaldoCosto;

    console.log('✅ Venta Mostrador TS - Funciones públicas registradas en window');
})();
