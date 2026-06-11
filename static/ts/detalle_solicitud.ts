/**
 * detalle_solicitud.ts
 * ====================
 * 
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este módulo TypeScript maneja toda la interactividad del detalle
 * de una Solicitud de Cotización en el almacén.
 * 
 * ¿Qué hace?
 * - Gestiona el modal de imágenes por línea (ver, subir, eliminar)
 * - Maneja el modal de rechazo de líneas
 * - Controla el envío de notificación a recepción (FRONTDESK)
 * - Renderiza galerías de imágenes dinámicamente
 * - Envía formularios via AJAX para mejor UX
 * 
 * ESTRUCTURA:
 * - Interfaces: definen la forma de los datos
 * - Clase DetalleSolicitud: encapsula toda la lógica
 * - Inicialización: se ejecuta al cargar la página
 */

// ========================================================================
// INTERFACES (Tipos de datos)
// ========================================================================

/** Datos de una imagen individual de línea */
interface ImagenLineaData {
    id: number;
    url: string;
    nombre: string;
    descripcion: string;
    fecha: string;
    comprimida: boolean;
    tamano_kb: number;
}

/** Datos de una línea con sus imágenes */
interface LineaData {
    numero: number;
    descripcion: string;
    imagenes: ImagenLineaData[];
}

/** Mapa de línea_pk → datos de la línea */
interface ImagenesDataMap {
    [lineaPk: string]: LineaData;
}

/** Configuración pasada desde Django */
interface SolicitudConfig {
    solicitudPk: number;
    maxImagenes: number;
    puedeSubir: boolean;
    urlEliminarImagen: string;
    urlResponderLinea: string;
    urlNotificarFront: string;
    csrfToken: string;
}

/** Evento de Bootstrap Modal con relatedTarget */
interface BootstrapModalEvent extends Event {
    relatedTarget: HTMLElement | undefined;
}

/** Respuesta del servidor al notificar a front */
interface NotificarFrontResponse {
    success: boolean;
    message?: string;
    error?: string;
    data?: {
        task_id: string;
        destinatario: string;
        solicitud: string;
    };
}

// ========================================================================
// CLASE PRINCIPAL
// ========================================================================

class DetalleSolicitud {
    private readonly config: SolicitudConfig;
    private readonly imagenesData: ImagenesDataMap;

    constructor() {
        // Leer configuración desde JSON embebido en el template
        const configEl = document.getElementById('solicitudConfig');
        if (!configEl) {
            throw new Error('Elemento #solicitudConfig no encontrado');
        }
        this.config = JSON.parse(configEl.textContent || '{}');

        // Leer datos de imágenes desde JSON embebido
        const imagenesEl = document.getElementById('imagenesData');
        this.imagenesData = imagenesEl ? JSON.parse(imagenesEl.textContent || '{}') : {};
    }

    /**
     * Inicializa todos los event listeners y funcionalidades
     */
    public init(): void {
        this.initImagenesModal();
        this.initRechazarModal();
        this.initNotificarFront();
    }

    // ====================================================================
    // MODAL DE IMÁGENES DE LÍNEA
    // ====================================================================

    /**
     * Configura el modal de imágenes: al abrirse, carga los datos de la línea
     */
    private initImagenesModal(): void {
        const modal = document.getElementById('imagenesModal');
        if (!modal) return;

        modal.addEventListener('show.bs.modal', (event: Event) => {
            const bsEvent = event as BootstrapModalEvent;
            const button = bsEvent.relatedTarget;
            if (!button) return;

            const lineaPk = button.getAttribute('data-linea-pk');
            const lineaNumero = button.getAttribute('data-linea-numero');
            const lineaDesc = button.getAttribute('data-linea-desc');

            // Actualizar encabezado del modal
            const numeroEl = document.getElementById('imagenesLineaNumero');
            const descEl = document.getElementById('imagenesLineaDesc');
            if (numeroEl) numeroEl.textContent = lineaNumero || '';
            if (descEl) descEl.textContent = lineaDesc || '';

            // Configurar el formulario de subida
            const uploadLineaPk = document.getElementById('uploadLineaPk') as HTMLInputElement;
            if (uploadLineaPk && lineaPk) {
                uploadLineaPk.value = lineaPk;
            }

            // Cargar las imágenes de esta línea
            if (lineaPk) {
                this.cargarImagenesLinea(lineaPk);
            }
        });
    }

    /**
     * Renderiza la galería de imágenes de una línea específica
     */
    private cargarImagenesLinea(lineaPk: string): void {
        const container = document.getElementById('imagenesContainer');
        const contador = document.getElementById('contadorImagenes');
        const espaciosEl = document.getElementById('espaciosDisponibles');
        const btnSubir = document.getElementById('btnSubirImagen') as HTMLButtonElement;
        const formSubir = document.getElementById('formSubirImagen');

        if (!container) return;

        // Obtener datos de la línea
        const lineaData = this.imagenesData[lineaPk];
        if (!lineaData) {
            container.innerHTML = `
                <div class="col-12 text-center text-muted py-4">
                    <i class="bi bi-exclamation-triangle fs-1 d-block mb-2"></i>
                    No se encontraron datos para esta línea
                </div>
            `;
            return;
        }

        const imagenes = lineaData.imagenes || [];
        const totalImagenes = imagenes.length;
        const espaciosDisponibles = this.config.maxImagenes - totalImagenes;

        // Actualizar contador
        if (contador) {
            contador.textContent = `${totalImagenes}/${this.config.maxImagenes}`;
            contador.className = `badge ms-2 ${totalImagenes >= this.config.maxImagenes ? 'bg-danger' : 'bg-secondary'}`;
        }

        // Actualizar espacios disponibles
        if (espaciosEl) {
            espaciosEl.innerHTML = `Espacios disponibles: <strong>${espaciosDisponibles}</strong>`;
        }

        // Deshabilitar botón si no hay espacio
        if (btnSubir && this.config.puedeSubir) {
            if (espaciosDisponibles <= 0) {
                btnSubir.disabled = true;
                btnSubir.innerHTML = '<i class="bi bi-x-circle me-1"></i>Límite alcanzado';
            } else {
                btnSubir.disabled = false;
                btnSubir.innerHTML = '<i class="bi bi-upload me-1"></i>Subir Imagen';
            }
        }

        // Ocultar formulario si no hay espacio
        if (formSubir && espaciosDisponibles <= 0) {
            formSubir.innerHTML = `
                <div class="alert alert-warning mb-0">
                    <i class="bi bi-exclamation-triangle me-1"></i>
                    Se alcanzó el límite de ${this.config.maxImagenes} imágenes para esta línea.
                </div>
            `;
        }

        // Renderizar imágenes
        if (totalImagenes === 0) {
            container.innerHTML = `
                <div class="col-12 text-center text-muted py-4" id="sinImagenes">
                    <i class="bi bi-image fs-1 d-block mb-2"></i>
                    No hay imágenes para esta línea
                </div>
            `;
            return;
        }

        let html = '';
        imagenes.forEach((img) => {
            html += `
                <div class="col-md-4 col-sm-6">
                    <div class="card h-100">
                        <img src="${img.url}" class="card-img-top cursor-pointer" 
                             alt="${img.descripcion || img.nombre}"
                             style="height: 150px; object-fit: cover; cursor: pointer;"
                             data-img-url="${img.url}"
                             data-img-desc="${img.descripcion || img.nombre}"
                             title="Clic para ampliar">
                        <div class="card-body p-2">
                            <p class="card-text small mb-1 text-truncate" title="${img.descripcion || img.nombre}">
                                ${img.descripcion || img.nombre}
                            </p>
                            <small class="text-muted d-block">
                                <i class="bi bi-calendar me-1"></i>${img.fecha}
                                ${img.comprimida ? '<span class="badge bg-info ms-1" title="Imagen comprimida"><i class="bi bi-file-zip"></i></span>' : ''}
                            </small>
                            ${img.tamano_kb ? `<small class="text-muted">${img.tamano_kb} KB</small>` : ''}
                        </div>
                        ${this.config.puedeSubir ? `
                        <div class="card-footer p-1 text-center">
                            <form method="post" 
                                  action="${this.config.urlEliminarImagen.replace('/0/imagenes/0/', `/${lineaPk}/imagenes/${img.id}/`)}"
                                  onsubmit="return confirm('¿Eliminar esta imagen?');"
                                  class="eliminar-imagen-form">
                                <input type="hidden" name="csrfmiddlewaretoken" value="${this.config.csrfToken}">
                                <button type="submit" class="btn btn-sm btn-outline-danger">
                                    <i class="bi bi-trash"></i> Eliminar
                                </button>
                            </form>
                        </div>
                        ` : ''}
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;

        // Agregar event listeners para ampliar imágenes
        container.querySelectorAll('img[data-img-url]').forEach((img) => {
            img.addEventListener('click', () => {
                const url = img.getAttribute('data-img-url') || '';
                const desc = img.getAttribute('data-img-desc') || '';
                this.verImagenAmpliada(url, desc);
            });
        });
    }

    /**
     * Abre el modal de imagen ampliada (lightbox)
     */
    private verImagenAmpliada(url: string, descripcion: string): void {
        const srcEl = document.getElementById('imagenAmpliadaSrc') as HTMLImageElement;
        const descEl = document.getElementById('imagenAmpliadaDesc');
        const modalEl = document.getElementById('imagenAmpliadaModal');

        if (!srcEl || !modalEl) return;

        srcEl.src = url;
        if (descEl) descEl.textContent = descripcion || 'Imagen';

        // Usar Bootstrap Modal API
        const bsLib = (window as unknown as Record<string, unknown>)['bootstrap'] as {
            Modal: new (el: HTMLElement) => { show(): void };
        } | undefined;

        if (bsLib) {
            const modal = new bsLib.Modal(modalEl);
            modal.show();
        }
    }

    // ====================================================================
    // MODAL DE RECHAZO DE LÍNEA
    // ====================================================================

    /**
     * Configura el modal de rechazo: al abrirse, actualiza la URL del form
     */
    private initRechazarModal(): void {
        const modal = document.getElementById('rechazarLineaModal');
        if (!modal) return;

        modal.addEventListener('show.bs.modal', (event: Event) => {
            const bsEvent = event as BootstrapModalEvent;
            const button = bsEvent.relatedTarget;
            if (!button) return;

            const lineaPk = button.getAttribute('data-linea-pk');
            const lineaDesc = button.getAttribute('data-linea-desc');

            // Actualizar la acción del formulario
            const form = document.getElementById('rechazarLineaForm') as HTMLFormElement;
            if (form && lineaPk) {
                form.action = this.config.urlResponderLinea.replace('/0/', `/${lineaPk}/`);
            }

            // Actualizar el texto
            const descEl = document.getElementById('lineaDescModal');
            if (descEl) descEl.textContent = lineaDesc || '';
        });
    }

    // ====================================================================
    // NOTIFICAR A FRONT (NUEVA FUNCIONALIDAD)
    // ====================================================================

    /**
     * Configura el modal y envío de notificación a recepción
     */
    private initNotificarFront(): void {
        const btnEnviar = document.getElementById('btnNotificarFront') as HTMLButtonElement;
        const form = document.getElementById('formNotificarFront') as HTMLFormElement;

        if (!btnEnviar || !form) return;

        btnEnviar.addEventListener('click', (e) => {
            e.preventDefault();
            this.enviarNotificacion(form, btnEnviar);
        });
    }

    /**
     * Envía la notificación via AJAX y muestra feedback
     */
    private async enviarNotificacion(form: HTMLFormElement, btn: HTMLButtonElement): Promise<void> {
        // Deshabilitar botón y mostrar loading
        const textoOriginal = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando...';

        try {
            const formData = new FormData(form);

            const response = await fetch(this.config.urlNotificarFront, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                },
            });

            const data: NotificarFrontResponse = await response.json();

            if (data.success) {
                // Cerrar modal
                const modalEl = document.getElementById('notificarFrontModal');
                if (modalEl) {
                    const bsLib = (window as unknown as Record<string, unknown>)['bootstrap'] as {
                        Modal: { getInstance(el: HTMLElement): { hide(): void } | null };
                    } | undefined;
                    if (bsLib) {
                        const modal = bsLib.Modal.getInstance(modalEl);
                        if (modal) modal.hide();
                    }
                }

                // Mostrar modal de confirmación
                this.mostrarConfirmacion(data);
            } else {
                alert(data.error || '❌ Error al enviar la notificación.');
            }
        } catch (error) {
            console.error('Error en envío de notificación:', error);
            alert('❌ Error de conexión. Verifica tu conexión a internet e intenta nuevamente.');
        } finally {
            // Restaurar botón
            btn.disabled = false;
            btn.innerHTML = textoOriginal;
        }
    }

    /**
     * Muestra modal de confirmación tras envío exitoso
     */
    private mostrarConfirmacion(data: NotificarFrontResponse): void {
        const destinatario = data.data?.destinatario || '';
        const solicitud = data.data?.solicitud || '';

        const modalHTML = `
            <div class="modal fade" id="modalConfirmacionNotificacion" tabindex="-1" aria-hidden="true">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header bg-success text-white">
                            <h5 class="modal-title">
                                <i class="bi bi-send-check"></i> Notificación en Proceso
                            </h5>
                        </div>
                        <div class="modal-body">
                            <div class="text-center mb-3">
                                <i class="bi bi-gear" style="font-size: 3rem; color: #198754;"></i>
                            </div>
                            <p class="text-center fs-5 mb-2">
                                La notificación se está enviando <strong>en segundo plano</strong>.
                            </p>
                            <div class="alert alert-info mb-0">
                                <i class="bi bi-info-circle me-1"></i>
                                <strong>Solicitud:</strong> ${solicitud}<br>
                                <strong>Destinatario:</strong> ${destinatario}<br><br>
                                El correo con la cotización se está procesando.
                                Puedes continuar trabajando normalmente.
                            </div>
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

        // Eliminar modal previo si existe y agregar el nuevo
        const prevModal = document.getElementById('modalConfirmacionNotificacion');
        if (prevModal) prevModal.remove();
        document.body.insertAdjacentHTML('beforeend', modalHTML);

        // Mostrar modal de confirmación
        const bsConfirm = (window as unknown as Record<string, unknown>)['bootstrap'] as {
            Modal: new (el: HTMLElement) => { show(): void };
        } | undefined;
        if (bsConfirm) {
            const confirmModal = new bsConfirm.Modal(
                document.getElementById('modalConfirmacionNotificacion') as HTMLElement
            );
            confirmModal.show();
        }
    }
}

// ========================================================================
// INICIALIZACIÓN
// ========================================================================

document.addEventListener('DOMContentLoaded', () => {
    try {
        const detalle = new DetalleSolicitud();
        detalle.init();
    } catch (error) {
        console.error('Error inicializando DetalleSolicitud:', error);
    }
});
