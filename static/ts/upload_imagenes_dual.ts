// ============================================================================
// SISTEMA DUAL DE SUBIDA DE IMÁGENES - GALERÍA Y CÁMARA
// Versión 5.0 - Migración completa: toda la lógica de subida en TypeScript
// ============================================================================

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * 
 * Este módulo maneja la subida de imágenes con dos opciones:
 * 1. Selección desde galería (múltiples archivos a la vez)
 * 2. Captura con cámara (acceso directo en móviles)
 * 
 * Funcionalidades:
 * - Unifica archivos de ambos inputs en un solo array interno (fuente de verdad)
 * - Muestra preview con miniaturas
 * - Permite eliminar imágenes individuales
 * - Valida límites (30 imágenes, 50MB cada una, 95MB total)
 * - Construye FormData y envía via XHR con barra de progreso
 * - Diagnóstico avanzado de errores de red (sin internet, Cloudflare, timeout)
 * - Protección beforeunload durante subida activa
 * 
 * CHANGELOG:
 * 
 * v5.0 (Febrero 2026):
 * - ✅ MIGRACIÓN COMPLETA: Toda la lógica de subida (submit, FormData, XHR,
 *   progreso, errores, beforeunload) movida desde el JS inline del template
 *   a este módulo TypeScript. Un solo punto de control con tipado fuerte.
 * - ✅ ELIMINADO: Input oculto #imagenesUnificadas y transferirArchivosAInputUnificado()
 * - ✅ ELIMINADO: resincronizarInput() (ya no hay input que sincronizar)
 * - ✅ Los IDs de los campos tipo/descripción se leen desde data-* attributes del <form>
 * - ✅ Sin fallback: si el TypeScript no carga, el botón queda disabled
 * 
 * v3.1 (Febrero 2026):
 * - API pública getArchivos(): devuelve archivos desde array interno
 * - API pública resincronizarInput(): restaura input oculto tras error
 * - FIX: Elimina dependencia frágil del input oculto como intermediario
 * 
 * v3.0 (Febrero 2026):
 * - Validación de límite total del request (95MB)
 * - Barra de progreso visual del límite del servidor
 * - Bloqueo automático del botón si excede 95MB
 * - Sistema de colores (verde < 76MB, amarillo 76-95MB, rojo > 95MB)
 * - Panel de resumen con "X MB / 95 MB permitidos"
 * 
 * v2.0 (Enero 2026):
 * - Validación de doble-click unificada con el template
 * - Panel de resumen de tamaño antes de subir
 * - Sistema de toasts Bootstrap para errores descriptivos
 * - Barra de progreso mejorada con conteo individual
 * - API pública para integración con scripts externos
 */

interface ImagenPreview {
    file: File;
    id: string;
    previewUrl: string;
}

// Interface para resumen de subida (API pública)
interface ResumenSubida {
    cantidad: number;
    tamanioTotal: number;
    tamanioMB: string;
    archivosGrandes: string[];
    archivosAdvertencia: string[];
    listoParaSubir: boolean;
    excedeLimiteTotal: boolean;    // Si excede 95MB del request
    cercaDelLimite: boolean;       // Si está cerca del límite (>76MB)
}

class UploadImagenesDual {
    // Elementos del DOM - Selección de archivos
    private inputGaleria: HTMLInputElement | null;
    private inputCamara: HTMLInputElement | null;
    private previewContainer: HTMLElement | null;
    private contenedorMiniaturas: HTMLElement | null;
    private btnSubir: HTMLButtonElement | null;
    private btnLimpiarTodo: HTMLButtonElement | null;
    private cantidadSpan: HTMLElement | null;
    
    // NUEVO v5.0: Elementos del DOM - Formulario y subida
    private formElement: HTMLFormElement | null;
    private progresoDiv: HTMLElement | null;
    private barraProgreso: HTMLElement | null;
    private textoProgreso: HTMLElement | null;
    private porcentajeProgreso: HTMLElement | null;
    private infoArchivos: HTMLElement | null;
    
    // NUEVO v5.0: IDs de campos Django (leídos desde data-* attributes del form)
    private tipoSelectId: string = '';
    private descripcionInputId: string = '';
    
    // Panel de resumen
    private panelResumen: HTMLElement | null = null;
    
    // Contenedor de toasts
    private toastContainer: HTMLElement | null = null;
    
    // Array de imágenes seleccionadas (FUENTE DE VERDAD)
    private imagenesSeleccionadas: ImagenPreview[] = [];
    
    // Límites de validación
    private readonly MAX_IMAGENES = 30;
    private readonly MAX_SIZE_MB = 50;
    private readonly MAX_SIZE_BYTES = this.MAX_SIZE_MB * 1024 * 1024;
    private readonly ADVERTENCIA_SIZE_MB = 40; // Advertir si > 40MB
    
    // Límite total del request (alineado con Cloudflare Free: 100MB max)
    private readonly MAX_REQUEST_SIZE_MB = 95;  // DATA_UPLOAD_MAX_MEMORY_SIZE
    private readonly MAX_REQUEST_SIZE_BYTES = this.MAX_REQUEST_SIZE_MB * 1024 * 1024;
    private readonly ADVERTENCIA_REQUEST_MB = 76; // Advertir al 80% del límite
    
    // NUEVO v5.0: Timeout de XHR (10 minutos, alineado con Gunicorn y Nginx)
    private readonly XHR_TIMEOUT_MS = 600000;
    
    // Control de estado de procesamiento
    private estaProcesando: boolean = false;
    private archivosListos: boolean = false;
    
    // Control de envío (para evitar doble-click)
    private enviando: boolean = false;
    private ultimoClickSubir: number = 0;
    private readonly DEBOUNCE_MS = 1500; // 1.5 segundos entre clicks
    
    // NUEVO v5.0: Flag para protección beforeunload
    private subiendoImagenes: boolean = false;
    
    constructor() {
        // Elementos de selección de archivos
        this.inputGaleria = document.getElementById('inputGaleria') as HTMLInputElement;
        this.inputCamara = document.getElementById('inputCamara') as HTMLInputElement;
        this.previewContainer = document.getElementById('previewImagenes');
        this.contenedorMiniaturas = document.getElementById('contenedorMiniaturas');
        this.btnSubir = document.getElementById('btnSubirImagenes') as HTMLButtonElement;
        this.btnLimpiarTodo = document.getElementById('btnLimpiarTodo') as HTMLButtonElement;
        this.cantidadSpan = document.getElementById('cantidadImagenes');
        
        // NUEVO v5.0: Elementos del formulario y progreso
        this.formElement = document.getElementById('formSubirImagenes') as HTMLFormElement;
        this.progresoDiv = document.getElementById('progresoUpload');
        this.barraProgreso = document.getElementById('barraProgreso');
        this.textoProgreso = document.getElementById('textoProgreso');
        this.porcentajeProgreso = document.getElementById('porcentajeProgreso');
        this.infoArchivos = document.getElementById('infoArchivos');
        
        // NUEVO v5.0: Leer IDs de campos Django desde data-* attributes
        if (this.formElement) {
            this.tipoSelectId = this.formElement.dataset.tipoId || '';
            this.descripcionInputId = this.formElement.dataset.descripcionId || '';
        }
        
        this.init();
    }
    
    private init(): void {
        // Crear contenedor de toasts si no existe
        this.crearContenedorToasts();
        
        // Crear panel de resumen
        this.crearPanelResumen();
        
        // Event listeners para los inputs
        if (this.inputGaleria) {
            this.inputGaleria.addEventListener('change', (e) => this.handleFileSelect(e));
        }
        
        // IMPORTANTE: El botón de cámara ahora abre el modal de cámara integrada
        // en lugar de usar el input file con capture
        const labelCamara = document.querySelector('label[for="inputCamara"]');
        if (labelCamara) {
            labelCamara.addEventListener('click', (e) => {
                e.preventDefault();
                this.abrirCamaraIntegrada();
            });
        }
        
        // Event listener para limpiar todo
        if (this.btnLimpiarTodo) {
            this.btnLimpiarTodo.addEventListener('click', () => this.limpiarTodo());
        }
        
        // Configurar callback de la cámara integrada
        this.configurarCamaraIntegrada();
        
        // NUEVO v5.0: Inicializar formulario de subida (submit handler + beforeunload)
        this.inicializarFormularioSubida();
        
        console.log('✅ Sistema dual de subida de imágenes v5.0 inicializado');
    }
    
    // =========================================================================
    // NUEVO v5.0: Formulario de subida (migrado desde JS inline del template)
    // =========================================================================
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Configura el formulario de subida de imágenes:
     * 1. Intercepta el submit del formulario HTML
     * 2. Construye un FormData con los archivos del array interno
     * 3. Envía via XHR con monitoreo de progreso
     * 4. Registra protección beforeunload para evitar cierre accidental
     */
    private inicializarFormularioSubida(): void {
        if (!this.formElement) {
            console.warn('⚠️ Formulario #formSubirImagenes no encontrado');
            return;
        }
        
        // Interceptar el submit del formulario
        this.formElement.addEventListener('submit', (e) => this.handleSubmit(e));
        
        // Registrar protección beforeunload
        window.addEventListener('beforeunload', (e) => this.advertenciaBeforeUnload(e));
        
        console.log('✅ Formulario de subida inicializado (submit handler + beforeunload)');
    }
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Este es el handler principal del submit. Cuando el usuario hace clic en
     * "Subir Imágenes", esta función:
     * 1. Previene el envío normal del formulario (lo haremos nosotros con XHR)
     * 2. Valida que haya archivos y que el sistema esté listo
     * 3. Construye un FormData con los archivos del array interno
     * 4. Envía con XHR para poder mostrar barra de progreso
     */
    private handleSubmit(e: Event): void {
        e.preventDefault(); // Prevenir envío normal del formulario
        
        // Verificar si puede enviar (no procesando, no enviando, hay archivos)
        if (!this.puedeEnviar()) {
            console.warn('⚠️ El sistema está procesando o no está listo. Ignorando submit.');
            
            if (this.getEstaEnviando()) {
                this.mostrarToast('Ya hay una subida en progreso. Por favor espera.', 'warning');
            } else if (this.getEstaProcesando()) {
                this.mostrarToast('Los archivos aún se están procesando. Espera un momento.', 'info');
            } else {
                this.mostrarToast('Selecciona al menos una imagen antes de subir.', 'warning');
            }
            return;
        }
        
        // Marcar como enviando para bloquear el botón
        this.marcarEnviando();
        
        // Obtener archivos desde el array interno (fuente de verdad)
        const archivosParaSubir = this.getArchivos();
        
        // Validar que haya archivos
        if (archivosParaSubir.length === 0) {
            this.mostrarToast('Por favor selecciona al menos una imagen para subir.', 'warning');
            this.marcarFinEnvio();
            return;
        }
        
        // Construir FormData
        const formData = this.construirFormData(archivosParaSubir);
        
        // Calcular tamaño total para progreso
        let tamanioTotalBytes = 0;
        archivosParaSubir.forEach(archivo => {
            tamanioTotalBytes += archivo.size;
        });
        const tamanioTotalMB = (tamanioTotalBytes / (1024 * 1024)).toFixed(2);
        const cantidadArchivos = archivosParaSubir.length;
        
        // Deshabilitar formulario durante la subida
        this.deshabilitarFormulario();
        
        // Mostrar barra de progreso
        if (this.progresoDiv) this.progresoDiv.style.display = 'block';
        if (this.barraProgreso) this.barraProgreso.style.width = '0%';
        if (this.textoProgreso) this.textoProgreso.textContent = 'Iniciando subida...';
        if (this.porcentajeProgreso) this.porcentajeProgreso.textContent = '0%';
        
        // Mostrar información de la subida
        if (this.infoArchivos) {
            this.infoArchivos.innerHTML = `
                <div class="d-flex align-items-center justify-content-between flex-wrap">
                    <span><i class="bi bi-cloud-arrow-up"></i> Subiendo <strong>${cantidadArchivos}</strong> imagen${cantidadArchivos !== 1 ? 'es' : ''}</span>
                    <span class="badge bg-secondary">${tamanioTotalMB} MB total</span>
                </div>
            `;
        }
        
        // Crear XMLHttpRequest para monitorear progreso
        const xhr = new XMLHttpRequest();
        
        // Monitorear progreso de subida
        xhr.upload.addEventListener('progress', (e) => {
            this.handleUploadProgress(e, cantidadArchivos, tamanioTotalMB);
        });
        
        // Manejar respuesta del servidor
        xhr.addEventListener('load', () => {
            this.handleUploadSuccess(xhr);
        });
        
        // Manejar errores de red
        xhr.addEventListener('error', () => {
            this.handleUploadError(cantidadArchivos, tamanioTotalBytes, tamanioTotalMB);
        });
        
        // Manejar timeout
        xhr.addEventListener('timeout', () => {
            this.handleUploadTimeout(cantidadArchivos, tamanioTotalBytes, tamanioTotalMB);
        });
        
        // Configurar y enviar la petición
        const url = this.formElement?.action || window.location.href;
        xhr.open('POST', url);
        xhr.timeout = this.XHR_TIMEOUT_MS;
        
        // Activar protección beforeunload
        this.subiendoImagenes = true;
        
        xhr.send(formData);
    }
    
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Construye el FormData con todos los datos necesarios para el servidor:
     * - Token CSRF (seguridad de Django)
     * - Tipo de formulario ('subir_imagenes')
     * - Tipo de imagen seleccionado (ingreso, proceso, etc.)
     * - Descripción opcional
     * - Los archivos de imagen (con nombre 'imagenes' que espera Django)
     */
    private construirFormData(archivos: File[]): FormData {
        const formData = new FormData();
        
        // Agregar token CSRF
        if (this.formElement) {
            const csrfInput = this.formElement.querySelector('input[name="csrfmiddlewaretoken"]') as HTMLInputElement;
            if (csrfInput) {
                formData.append('csrfmiddlewaretoken', csrfInput.value);
            }
        }
        
        // Agregar tipo de formulario
        formData.append('form_type', 'subir_imagenes');
        
        // Agregar tipo de imagen desde el select de Django
        if (this.tipoSelectId) {
            const tipoSelect = document.getElementById(this.tipoSelectId) as HTMLSelectElement;
            if (tipoSelect) {
                formData.append('tipo', tipoSelect.value);
            }
        }
        
        // Agregar descripción desde el input de Django
        if (this.descripcionInputId) {
            const descripcionInput = document.getElementById(this.descripcionInputId) as HTMLInputElement;
            if (descripcionInput) {
                formData.append('descripcion', descripcionInput.value || '');
            }
        }
        
        // Agregar cada archivo con el nombre 'imagenes'
        // (Django los recibe con request.FILES.getlist('imagenes'))
        archivos.forEach(archivo => {
            formData.append('imagenes', archivo, archivo.name);
        });
        
        return formData;
    }
    
    /**
     * Maneja el evento de progreso de la subida XHR.
     * Actualiza la barra de progreso y la información visual.
     */
    private handleUploadProgress(e: ProgressEvent, cantidadArchivos: number, tamanioTotalMB: string): void {
        if (!e.lengthComputable) return;
        
        const porcentaje = Math.round((e.loaded / e.total) * 100);
        const mbSubidos = (e.loaded / (1024 * 1024)).toFixed(2);
        
        if (this.barraProgreso) this.barraProgreso.style.width = porcentaje + '%';
        if (this.porcentajeProgreso) this.porcentajeProgreso.textContent = porcentaje + '%';
        
        if (porcentaje < 100) {
            if (this.textoProgreso) this.textoProgreso.textContent = `Subiendo... ${porcentaje}%`;
            if (this.infoArchivos) {
                this.infoArchivos.innerHTML = `
                    <div class="d-flex align-items-center justify-content-between flex-wrap">
                        <span><i class="bi bi-cloud-arrow-up text-primary"></i> Subiendo <strong>${cantidadArchivos}</strong> imagen${cantidadArchivos !== 1 ? 'es' : ''}...</span>
                        <span class="badge bg-primary">${mbSubidos} / ${tamanioTotalMB} MB</span>
                    </div>
                `;
            }
        } else {
            if (this.textoProgreso) this.textoProgreso.textContent = 'Procesando en servidor...';
            if (this.barraProgreso) this.barraProgreso.classList.add('progress-bar-striped');
            if (this.infoArchivos) {
                this.infoArchivos.innerHTML = `
                    <div class="d-flex align-items-center">
                        <span class="spinner-border spinner-border-sm text-info me-2"></span>
                        <span><i class="bi bi-cpu text-info"></i> Comprimiendo y guardando ${cantidadArchivos} imagen${cantidadArchivos !== 1 ? 'es' : ''}, por favor espere...</span>
                    </div>
                `;
            }
        }
    }
    
    /**
     * Maneja la respuesta exitosa del servidor (status 200 o 500).
     * Parsea el JSON y muestra el resultado al usuario.
     */
    private handleUploadSuccess(xhr: XMLHttpRequest): void {
        // Desactivar protección beforeunload
        this.subiendoImagenes = false;
        
        // Marcar fin de envío
        this.marcarFinEnvio();
        
        if (xhr.status === 200 || xhr.status === 500) {
            try {
                const data = JSON.parse(xhr.responseText);
                
                if (data.success) {
                    // Éxito - mostrar mensaje final
                    if (this.barraProgreso) {
                        this.barraProgreso.classList.remove('progress-bar-animated', 'progress-bar-striped');
                        this.barraProgreso.classList.add('bg-success');
                    }
                    if (this.textoProgreso) this.textoProgreso.textContent = '¡Completado!';
                    if (this.porcentajeProgreso) this.porcentajeProgreso.textContent = '✓';
                    
                    // Construir mensaje detallado
                    let mensajeDetalle = `
                        <div class="d-flex align-items-center text-success">
                            <i class="bi bi-check-circle-fill me-2"></i>
                            <span>${data.message}</span>
                        </div>
                    `;
                    
                    // Agregar advertencias si hay imágenes omitidas
                    if (data.imagenes_omitidas && data.imagenes_omitidas.length > 0) {
                        mensajeDetalle += `
                            <div class="mt-1">
                                <small class="text-warning">
                                    <i class="bi bi-exclamation-triangle"></i> 
                                    ${data.imagenes_omitidas.length} imagen(es) omitida(s) por exceder 50MB
                                </small>
                            </div>
                        `;
                    }
                    
                    // Agregar errores si los hay
                    if (data.errores && data.errores.length > 0) {
                        mensajeDetalle += `
                            <div class="mt-1">
                                <small class="text-danger">
                                    <i class="bi bi-x-circle"></i> 
                                    ${data.errores.length} error(es) al procesar
                                </small>
                            </div>
                        `;
                    }
                    
                    if (this.infoArchivos) this.infoArchivos.innerHTML = mensajeDetalle;
                    
                    // Limpiar el sistema
                    this.limpiarDespuesDeExito();
                    
                    // Recargar página después de 1.5 segundos
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);
                } else {
                    // Error reportado por el servidor
                    let mensajeError = data.error || 'Error desconocido al subir imágenes';
                    
                    if (data.error_type) {
                        console.error(`Error tipo: ${data.error_type}`);
                        mensajeError += `<br><small class="text-muted">Tipo: ${data.error_type}</small>`;
                    }
                    
                    // Si se guardaron algunas imágenes antes del error
                    if (data.imagenes_guardadas > 0) {
                        mensajeError += `<br><small class="text-info"><i class="bi bi-info-circle"></i> Se guardaron ${data.imagenes_guardadas} imagen(es) antes del error. Recarga para verlas.</small>`;
                    }
                    
                    this.mostrarErrorCarga(mensajeError);
                    this.mostrarToast(data.error || 'Error al subir imágenes', 'error');
                }
            } catch (e) {
                console.error('Error al parsear respuesta:', e);
                console.error('Respuesta del servidor:', xhr.responseText);
                this.mostrarErrorCarga('Error al procesar la respuesta del servidor. Revisa la consola para más detalles.');
            }
        } else {
            this.mostrarErrorCarga(`Error del servidor (código ${xhr.status}). Por favor intenta nuevamente.`);
        }
    }
    
    /**
     * DIAGNÓSTICO AVANZADO DE ERRORES v3.2 (migrado a v5.0)
     * Analiza el tipo de fallo para dar información útil al usuario y logs
     * detallados para depuración.
     */
    private handleUploadError(cantidadArchivos: number, tamanioTotalBytes: number, tamanioTotalMB: string): void {
        this.subiendoImagenes = false;
        this.marcarFinEnvio();
        
        // Diagnóstico: ¿Qué tipo de error de red ocurrió?
        let diagnostico = '';
        let mensajeUsuario = '';
        let tipoError = 'desconocido';
        
        if (!navigator.onLine) {
            tipoError = 'sin_internet';
            mensajeUsuario = 'Sin conexión a internet. Verifica tu WiFi o datos móviles y reintenta.';
            diagnostico = 'navigator.onLine=false';
        } else if (tamanioTotalBytes > 100 * 1024 * 1024) {
            tipoError = 'cloudflare_limite';
            mensajeUsuario = `El tamaño total (${tamanioTotalMB} MB) excede el límite de Cloudflare (100 MB). Sube menos imágenes por lote.`;
            diagnostico = `tamaño=${tamanioTotalMB}MB, excede límite Cloudflare free=100MB`;
        } else {
            tipoError = 'conexion_servidor';
            mensajeUsuario = 'Error de conexión con el servidor. El servidor puede estar reiniciándose o hay un problema de red. Reintenta en unos segundos.';
            diagnostico = 'navigator.onLine=true, posible: servidor caído, CORS, firewall, o Cloudflare timeout';
        }
        
        // Log detallado para depuración
        const url = this.formElement?.action || window.location.href;
        console.error(`[UPLOAD ERROR] Tipo: ${tipoError}`);
        console.error(`[UPLOAD ERROR] Diagnóstico: ${diagnostico}`);
        console.error(`[UPLOAD ERROR] Archivos: ${cantidadArchivos}, Tamaño: ${tamanioTotalMB} MB`);
        console.error(`[UPLOAD ERROR] URL: ${url}`);
        console.error(`[UPLOAD ERROR] Hora: ${new Date().toISOString()}`);
        
        this.mostrarErrorCarga(mensajeUsuario, tipoError, diagnostico);
        this.mostrarToast(mensajeUsuario, 'error', undefined, 8000);
    }
    
    /**
     * Maneja el timeout de la petición XHR.
     * Da feedback diferenciado según el tamaño del lote.
     */
    private handleUploadTimeout(cantidadArchivos: number, tamanioTotalBytes: number, tamanioTotalMB: string): void {
        this.subiendoImagenes = false;
        this.marcarFinEnvio();
        
        let mensajeUsuario = '';
        let diagnostico = '';
        
        if (tamanioTotalBytes > 50 * 1024 * 1024) {
            mensajeUsuario = `Tiempo agotado (10 min). El lote de ${tamanioTotalMB} MB es muy grande. Intenta con menos imágenes o archivos más pequeños.`;
            diagnostico = `timeout=600s, tamaño=${tamanioTotalMB}MB (grande)`;
        } else {
            mensajeUsuario = 'Tiempo de espera agotado (10 min). El servidor puede estar sobrecargado. Reintenta en unos minutos.';
            diagnostico = `timeout=600s, tamaño=${tamanioTotalMB}MB (normal), posible: servidor lento o sobrecargado`;
        }
        
        console.error(`[UPLOAD TIMEOUT] Diagnóstico: ${diagnostico}`);
        console.error(`[UPLOAD TIMEOUT] Archivos: ${cantidadArchivos}, Tamaño: ${tamanioTotalMB} MB`);
        console.error(`[UPLOAD TIMEOUT] Hora: ${new Date().toISOString()}`);
        
        this.mostrarErrorCarga(mensajeUsuario, 'timeout', diagnostico);
        this.mostrarToast(mensajeUsuario, 'error', undefined, 8000);
    }
    
    /**
     * Muestra un error en la barra de progreso con información de diagnóstico.
     * NO limpia los archivos del array interno (preserva para reintento).
     * Rehabilita el formulario después de 4 segundos.
     */
    private mostrarErrorCarga(mensaje: string, tipoError?: string, diagnostico?: string): void {
        if (this.barraProgreso) {
            this.barraProgreso.classList.remove('bg-success', 'progress-bar-animated', 'progress-bar-striped');
            this.barraProgreso.classList.add('bg-danger');
            this.barraProgreso.style.width = '100%';
        }
        if (this.textoProgreso) this.textoProgreso.textContent = 'Error';
        if (this.porcentajeProgreso) this.porcentajeProgreso.textContent = '✗';
        
        // Construir mensaje con diagnóstico si está disponible
        let htmlError = `
            <div class="text-danger">
                <i class="bi bi-x-circle-fill me-1"></i> ${mensaje}
            </div>
        `;
        
        // Agregar información de diagnóstico expandible
        if (tipoError && diagnostico) {
            htmlError += `
                <details class="mt-2">
                    <summary class="text-muted" style="cursor: pointer; font-size: 0.8rem;">
                        <i class="bi bi-bug"></i> Info técnica para soporte
                    </summary>
                    <div class="mt-1 p-2 bg-light rounded" style="font-size: 0.75rem; font-family: monospace;">
                        <div><strong>Tipo:</strong> ${tipoError}</div>
                        <div><strong>Detalle:</strong> ${diagnostico}</div>
                        <div><strong>Hora:</strong> ${new Date().toLocaleString('es-MX')}</div>
                        <div><strong>Navegador:</strong> ${navigator.userAgent.substring(0, 80)}...</div>
                        <div><strong>Online:</strong> ${navigator.onLine ? 'Sí' : 'No'}</div>
                    </div>
                </details>
            `;
        }
        
        if (this.infoArchivos) this.infoArchivos.innerHTML = htmlError;
        
        // Rehabilitar formulario después de 4 segundos para permitir reintento
        setTimeout(() => {
            this.rehabilitarFormulario();
            
            // Ocultar barra de progreso y resetear estado visual
            if (this.progresoDiv) this.progresoDiv.style.display = 'none';
            if (this.barraProgreso) {
                this.barraProgreso.classList.remove('bg-danger');
                this.barraProgreso.classList.add('progress-bar-animated', 'bg-success');
                this.barraProgreso.style.width = '0%';
            }
            
            // Restaurar texto del botón según el estado real de los archivos
            this.actualizarEstadoBotonSubir();
        }, 4000);
    }
    
    /**
     * Deshabilita el formulario durante la subida.
     * Previene interacción con los controles mientras se sube.
     */
    private deshabilitarFormulario(): void {
        if (this.btnSubir) {
            this.btnSubir.disabled = true;
            this.btnSubir.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Subiendo...';
        }
        
        // Deshabilitar select de tipo y input de descripción
        if (this.tipoSelectId) {
            const tipoSelect = document.getElementById(this.tipoSelectId) as HTMLSelectElement;
            if (tipoSelect) tipoSelect.disabled = true;
        }
        if (this.descripcionInputId) {
            const descripcionInput = document.getElementById(this.descripcionInputId) as HTMLInputElement;
            if (descripcionInput) descripcionInput.disabled = true;
        }
    }
    
    /**
     * Rehabilita el formulario después de un error.
     * Permite al usuario reintentar la subida.
     */
    private rehabilitarFormulario(): void {
        if (this.btnSubir) this.btnSubir.disabled = false;
        
        // Rehabilitar select de tipo y input de descripción
        if (this.tipoSelectId) {
            const tipoSelect = document.getElementById(this.tipoSelectId) as HTMLSelectElement;
            if (tipoSelect) tipoSelect.disabled = false;
        }
        if (this.descripcionInputId) {
            const descripcionInput = document.getElementById(this.descripcionInputId) as HTMLInputElement;
            if (descripcionInput) descripcionInput.disabled = false;
        }
    }
    
    /**
     * Protección beforeunload: advierte al usuario si intenta cerrar/navegar
     * durante una subida activa. Se activa al iniciar el XHR y se desactiva
     * al completar (éxito o error).
     */
    private advertenciaBeforeUnload(e: BeforeUnloadEvent): void {
        if (this.subiendoImagenes) {
            e.preventDefault();
            // Chrome ignora mensajes personalizados, pero otros navegadores lo muestran
            e.returnValue = 'Hay una subida de imágenes en progreso. Si sales, se perderán.';
        }
    }
    
    // =========================================================================
    // Sistema de Toasts Bootstrap
    // =========================================================================
    
    /**
     * Crea el contenedor de toasts si no existe
     */
    private crearContenedorToasts(): void {
        if (document.getElementById('toastContainerImagenes')) {
            this.toastContainer = document.getElementById('toastContainerImagenes');
            return;
        }
        
        const container = document.createElement('div');
        container.id = 'toastContainerImagenes';
        container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        container.style.zIndex = '1100';
        document.body.appendChild(container);
        this.toastContainer = container;
    }
    
    /**
     * Muestra un toast con el mensaje especificado
     */
    public mostrarToast(
        mensaje: string, 
        tipo: 'success' | 'warning' | 'error' | 'info' = 'info',
        detalles?: string[],
        duracion: number = 6000
    ): void {
        if (!this.toastContainer) return;
        
        const iconos = {
            success: 'bi-check-circle-fill',
            warning: 'bi-exclamation-triangle-fill',
            error: 'bi-x-circle-fill',
            info: 'bi-info-circle-fill'
        };
        
        const colores = {
            success: 'text-success',
            warning: 'text-warning',
            error: 'text-danger',
            info: 'text-primary'
        };
        
        const bgClasses = {
            success: 'border-success',
            warning: 'border-warning',
            error: 'border-danger',
            info: 'border-primary'
        };
        
        const toastId = `toast_${Date.now()}`;
        
        // Construir HTML de detalles si existen
        let detallesHtml = '';
        if (detalles && detalles.length > 0) {
            const detallesLimitados = detalles.slice(0, 5); // Máximo 5 detalles
            const hayMas = detalles.length > 5;
            
            detallesHtml = `
                <div class="toast-body pt-0">
                    <small class="text-muted">
                        <ul class="mb-0 ps-3" style="font-size: 0.85em;">
                            ${detallesLimitados.map(d => `<li>${d}</li>`).join('')}
                            ${hayMas ? `<li class="text-muted">... y ${detalles.length - 5} más</li>` : ''}
                        </ul>
                    </small>
                </div>
            `;
        }
        
        const toastHtml = `
            <div id="${toastId}" class="toast border-start border-4 ${bgClasses[tipo]}" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <i class="bi ${iconos[tipo]} ${colores[tipo]} me-2"></i>
                    <strong class="me-auto">${tipo === 'error' ? 'Error' : tipo === 'warning' ? 'Advertencia' : tipo === 'success' ? 'Éxito' : 'Información'}</strong>
                    <small class="text-muted">ahora</small>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Cerrar"></button>
                </div>
                <div class="toast-body">
                    ${mensaje}
                </div>
                ${detallesHtml}
            </div>
        `;
        
        this.toastContainer.insertAdjacentHTML('beforeend', toastHtml);
        
        const toastElement = document.getElementById(toastId);
        if (toastElement) {
            // Usar Bootstrap Toast si está disponible
            if (typeof (window as any).bootstrap !== 'undefined') {
                const bsToast = new (window as any).bootstrap.Toast(toastElement, {
                    autohide: true,
                    delay: duracion
                });
                bsToast.show();
                
                // Eliminar del DOM después de ocultarse
                toastElement.addEventListener('hidden.bs.toast', () => {
                    toastElement.remove();
                });
            } else {
                // Fallback sin Bootstrap
                toastElement.classList.add('show');
                setTimeout(() => {
                    toastElement.remove();
                }, duracion);
            }
        }
    }
    
    // =========================================================================
    // Panel de Resumen Pre-Subida
    // =========================================================================
    
    /**
     * Crea el panel de resumen de subida
     */
    private crearPanelResumen(): void {
        const previewContainer = document.getElementById('previewImagenes');
        if (!previewContainer || document.getElementById('panelResumenSubida')) {
            this.panelResumen = document.getElementById('panelResumenSubida');
            return;
        }
        
        const panel = document.createElement('div');
        panel.id = 'panelResumenSubida';
        panel.className = 'alert alert-info d-none mb-3';
        panel.innerHTML = `
            <div class="d-flex flex-wrap align-items-center justify-content-between gap-2 mb-2">
                <div>
                    <i class="bi bi-info-circle me-1"></i>
                    <span id="resumenCantidad">0 imágenes</span>
                    <span class="text-muted mx-2">|</span>
                    <strong id="resumenTamanio">0 MB</strong>
                </div>
                <div id="resumenEstado" class="badge bg-secondary">
                    Selecciona imágenes
                </div>
            </div>
            
            <!-- Barra de progreso del límite total del servidor -->
            <div class="mb-2">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <small class="text-muted">
                        <i class="bi bi-server"></i> Límite del servidor:
                    </small>
                    <small id="textoLimiteServidor" class="fw-bold">0 / ${this.MAX_REQUEST_SIZE_MB} MB</small>
                </div>
                <div class="progress" style="height: 8px;">
                    <div id="barraLimiteServidor" 
                         class="progress-bar bg-success" 
                         role="progressbar" 
                         style="width: 0%"
                         aria-valuenow="0" 
                         aria-valuemin="0" 
                         aria-valuemax="100">
                    </div>
                </div>
            </div>
            
            <div id="resumenAdvertencias" class="d-none">
                <small class="text-warning">
                    <i class="bi bi-exclamation-triangle"></i>
                    <span id="textoAdvertencias"></span>
                </small>
            </div>
        `;
        
        // Insertar antes del contenedor de preview
        previewContainer.parentElement?.insertBefore(panel, previewContainer);
        this.panelResumen = panel;
    }
    
    /**
     * Actualiza el panel de resumen con la información actual
     */
    private actualizarPanelResumen(): void {
        if (!this.panelResumen) return;
        
        const resumen = this.obtenerResumen();
        
        // Mostrar/ocultar panel
        if (resumen.cantidad > 0) {
            this.panelResumen.classList.remove('d-none');
        } else {
            this.panelResumen.classList.add('d-none');
            return;
        }
        
        // Actualizar cantidad
        const cantidadSpan = this.panelResumen.querySelector('#resumenCantidad');
        if (cantidadSpan) {
            cantidadSpan.textContent = `${resumen.cantidad} imagen${resumen.cantidad !== 1 ? 'es' : ''}`;
        }
        
        // Actualizar tamaño
        const tamanioSpan = this.panelResumen.querySelector('#resumenTamanio');
        if (tamanioSpan) {
            tamanioSpan.textContent = resumen.tamanioMB;
        }
        
        // Actualizar barra de progreso del límite del servidor
        const barraLimite = this.panelResumen.querySelector('#barraLimiteServidor') as HTMLElement;
        const textoLimite = this.panelResumen.querySelector('#textoLimiteServidor');
        
        if (barraLimite && textoLimite) {
            const tamanioTotalMB = resumen.tamanioTotal / (1024 * 1024);
            const porcentajeUso = (tamanioTotalMB / this.MAX_REQUEST_SIZE_MB) * 100;
            
            // Actualizar texto
            textoLimite.textContent = `${tamanioTotalMB.toFixed(1)} / ${this.MAX_REQUEST_SIZE_MB} MB`;
            
            // Actualizar barra
            barraLimite.style.width = `${Math.min(porcentajeUso, 100)}%`;
            barraLimite.setAttribute('aria-valuenow', porcentajeUso.toFixed(0));
            
            // Cambiar color según porcentaje
            barraLimite.className = 'progress-bar';
            if (porcentajeUso >= 100) {
                barraLimite.classList.add('bg-danger');
                textoLimite.classList.add('text-danger');
            } else if (porcentajeUso >= 80) {
                barraLimite.classList.add('bg-warning');
                textoLimite.classList.add('text-warning');
            } else if (porcentajeUso >= 60) {
                barraLimite.classList.add('bg-info');
                textoLimite.classList.remove('text-danger', 'text-warning');
            } else {
                barraLimite.classList.add('bg-success');
                textoLimite.classList.remove('text-danger', 'text-warning');
            }
        }
        
        // Actualizar estado
        const estadoBadge = this.panelResumen.querySelector('#resumenEstado') as HTMLElement;
        if (estadoBadge) {
            if (this.estaProcesando) {
                estadoBadge.className = 'badge bg-warning';
                estadoBadge.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Procesando...';
            } else if (resumen.excedeLimiteTotal) {
                estadoBadge.className = 'badge bg-danger';
                estadoBadge.innerHTML = '<i class="bi bi-x-circle me-1"></i>Excede límite del servidor';
            } else if (resumen.listoParaSubir) {
                estadoBadge.className = 'badge bg-success';
                estadoBadge.innerHTML = '<i class="bi bi-check-circle me-1"></i>Listo para subir';
            } else {
                estadoBadge.className = 'badge bg-secondary';
                estadoBadge.textContent = 'Selecciona imágenes';
            }
        }
        
        // Actualizar advertencias
        const advertenciasDiv = this.panelResumen.querySelector('#resumenAdvertencias') as HTMLElement;
        const textoAdvertencias = this.panelResumen.querySelector('#textoAdvertencias');
        
        if (advertenciasDiv && textoAdvertencias) {
            const mensajes: string[] = [];
            
            if (resumen.excedeLimiteTotal) {
                const exceso = ((resumen.tamanioTotal / (1024 * 1024)) - this.MAX_REQUEST_SIZE_MB).toFixed(1);
                mensajes.push(`⚠️ El tamaño total excede el límite del servidor en ${exceso}MB. Elimina algunas imágenes.`);
            } else if (resumen.cercaDelLimite) {
                const restante = (this.MAX_REQUEST_SIZE_MB - (resumen.tamanioTotal / (1024 * 1024))).toFixed(1);
                mensajes.push(`⚠️ Te quedan ${restante}MB disponibles del límite del servidor.`);
            }
            
            if (resumen.archivosGrandes.length > 0) {
                mensajes.push(`${resumen.archivosGrandes.length} archivo(s) exceden el límite de ${this.MAX_SIZE_MB}MB`);
            }
            if (resumen.archivosAdvertencia.length > 0) {
                mensajes.push(`${resumen.archivosAdvertencia.length} archivo(s) son muy grandes (>40MB)`);
            }
            
            if (mensajes.length > 0) {
                advertenciasDiv.classList.remove('d-none');
                textoAdvertencias.textContent = mensajes.join(' | ');
                
                // Cambiar color del panel según severidad
                if (resumen.excedeLimiteTotal || resumen.archivosGrandes.length > 0) {
                    this.panelResumen.className = 'alert alert-danger mb-3';
                } else if (resumen.cercaDelLimite || resumen.archivosAdvertencia.length > 0) {
                    this.panelResumen.className = 'alert alert-warning mb-3';
                } else {
                    this.panelResumen.className = 'alert alert-info mb-3';
                }
            } else {
                advertenciasDiv.classList.add('d-none');
                this.panelResumen.className = 'alert alert-info mb-3';
            }
        }
    }
    
    // =========================================================================
    // API PÚBLICA: Para integración con scripts externos
    // =========================================================================
    
    /**
     * API PÚBLICA: Consultar si el sistema está listo para subir
     */
    public puedeEnviar(): boolean {
        const ahora = Date.now();
        const tiempoDesdeUltimoClick = ahora - this.ultimoClickSubir;
        
        return this.archivosListos && 
               !this.estaProcesando && 
               !this.enviando && 
               this.imagenesSeleccionadas.length > 0 &&
               tiempoDesdeUltimoClick >= this.DEBOUNCE_MS;
    }
    
    /**
     * API PÚBLICA: Marcar que se inició el envío
     */
    public marcarEnviando(): void {
        this.enviando = true;
        this.ultimoClickSubir = Date.now();
        this.actualizarEstadoBotonSubir();
        console.log('📤 Envío iniciado - botón bloqueado');
    }
    
    /**
     * API PÚBLICA: Marcar que terminó el envío (éxito o error)
     */
    public marcarFinEnvio(): void {
        this.enviando = false;
        this.actualizarEstadoBotonSubir();
        console.log('✅ Envío finalizado - botón desbloqueado');
    }
    
    /**
     * API PÚBLICA: Limpiar después de subida exitosa
     */
    public limpiarDespuesDeExito(): void {
        this.limpiarTodo();
        this.marcarFinEnvio();
    }
    
    /**
     * API PÚBLICA: Obtener resumen de la subida para mostrar
     */
    public obtenerResumen(): ResumenSubida {
        const archivosGrandes: string[] = [];
        const archivosAdvertencia: string[] = [];
        let tamanioTotal = 0;
        
        this.imagenesSeleccionadas.forEach(img => {
            tamanioTotal += img.file.size;
            const sizeMB = img.file.size / (1024 * 1024);
            
            if (sizeMB > this.MAX_SIZE_MB) {
                archivosGrandes.push(`${img.file.name} (${sizeMB.toFixed(1)}MB - excede límite)`);
            } else if (sizeMB > this.ADVERTENCIA_SIZE_MB) {
                archivosAdvertencia.push(`${img.file.name} (${sizeMB.toFixed(1)}MB)`);
            }
        });
        
        const excedeLimiteTotal = tamanioTotal > this.MAX_REQUEST_SIZE_BYTES;
        const cercaDelLimite = tamanioTotal > (this.ADVERTENCIA_REQUEST_MB * 1024 * 1024);
        
        return {
            cantidad: this.imagenesSeleccionadas.length,
            tamanioTotal: tamanioTotal,
            tamanioMB: (tamanioTotal / (1024 * 1024)).toFixed(2) + ' MB',
            archivosGrandes: archivosGrandes,
            archivosAdvertencia: archivosAdvertencia,
            listoParaSubir: this.archivosListos && !this.estaProcesando && archivosGrandes.length === 0 && !excedeLimiteTotal,
            excedeLimiteTotal: excedeLimiteTotal,
            cercaDelLimite: cercaDelLimite
        };
    }
    
    /**
     * API PÚBLICA: Obtener cantidad de imágenes
     */
    public getCantidadImagenes(): number {
        return this.imagenesSeleccionadas.length;
    }
    
    /**
     * API PÚBLICA: Verificar si está procesando
     */
    public getEstaProcesando(): boolean {
        return this.estaProcesando;
    }
    
    /**
     * API PÚBLICA: Verificar si está enviando
     */
    public getEstaEnviando(): boolean {
        return this.enviando;
    }
    
    /**
     * API PÚBLICA: Obtener los archivos seleccionados como array de File.
     * 
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Este método devuelve los archivos directamente desde el array interno.
     * Es la fuente de verdad del sistema, inmune a modificaciones del DOM.
     */
    public getArchivos(): File[] {
        return this.imagenesSeleccionadas.map(img => img.file);
    }
    
    // =========================================================================
    // Métodos de cámara integrada
    // =========================================================================
    
    /**
     * Abre el modal de cámara integrada
     */
    private abrirCamaraIntegrada(): void {
        const camaraIntegrada = (window as any).camaraIntegrada;
        if (camaraIntegrada) {
            camaraIntegrada.abrir();
        } else {
            console.error('❌ Cámara integrada no disponible');
            this.mostrarToast(
                'La cámara integrada no está disponible. Verifica que estés usando HTTPS o localhost.',
                'error'
            );
        }
    }
    
    /**
     * Configura el callback para recibir fotos de la cámara integrada
     */
    private configurarCamaraIntegrada(): void {
        // Esperar a que la cámara integrada esté disponible
        const intervalo = setInterval(() => {
            const camaraIntegrada = (window as any).camaraIntegrada;
            if (camaraIntegrada) {
                clearInterval(intervalo);
                
                // Configurar callback para recibir fotos capturadas
                camaraIntegrada.setOnFotosCapturadas((fotos: Blob[]) => {
                    this.agregarFotosDeCamara(fotos);
                });
                
                console.log('✅ Cámara integrada conectada al sistema de upload');
            }
        }, 100);
        
        // Timeout de 5 segundos
        setTimeout(() => clearInterval(intervalo), 5000);
    }
    
    /**
     * Agrega fotos capturadas desde la cámara integrada
     */
    private agregarFotosDeCamara(fotos: Blob[]): void {
        console.log(`📸 Recibidas ${fotos.length} foto(s) desde cámara integrada`);
        
        // Convertir Blobs a Files
        const archivos: File[] = fotos.map((blob, index) => {
            const timestamp = Date.now() + index;
            return new File([blob], `captura_${timestamp}.jpg`, { type: 'image/jpeg' });
        });
        
        // Agregar usando el método existente
        this.agregarArchivos(archivos);
        
        // Mostrar toast de confirmación
        this.mostrarToast(
            `${fotos.length} foto(s) capturada(s) desde la cámara`,
            'success'
        );
    }
    
    // =========================================================================
    // Manejo de archivos
    // =========================================================================
    
    /**
     * Maneja la selección de archivos desde cualquier input
     */
    private handleFileSelect(event: Event): void {
        const input = event.target as HTMLInputElement;
        
        if (!input.files || input.files.length === 0) {
            return;
        }
        
        const nuevosArchivos = Array.from(input.files);
        const origen = input.id === 'inputGaleria' ? 'galería' : 'cámara';
        
        console.log(`📸 ${nuevosArchivos.length} archivo(s) seleccionado(s) desde ${origen}`);
        
        // Validar y agregar archivos
        this.agregarArchivos(nuevosArchivos);
        
        // Limpiar el input para permitir seleccionar los mismos archivos de nuevo
        input.value = '';
    }
    
    /**
     * Agrega archivos al array de imágenes seleccionadas.
     * v5.0: Ya no transfiere a input oculto, el array es la fuente de verdad.
     */
    private async agregarArchivos(archivos: File[]): Promise<void> {
        // CRÍTICO: Marcar como procesando y deshabilitar botón de subir
        this.estaProcesando = true;
        this.archivosListos = false;
        this.actualizarEstadoBotonSubir();
        this.actualizarPanelResumen();
        
        let agregados = 0;
        let omitidos = 0;
        const errores: string[] = [];
        const advertencias: string[] = [];
        
        console.log(`🔄 Iniciando procesamiento de ${archivos.length} archivo(s)...`);
        
        for (const archivo of archivos) {
            // Validar que sea una imagen
            if (!archivo.type.startsWith('image/')) {
                errores.push(`${archivo.name}: No es una imagen válida`);
                omitidos++;
                continue;
            }
            
            // Validar tamaño
            if (archivo.size > this.MAX_SIZE_BYTES) {
                const sizeMB = (archivo.size / (1024 * 1024)).toFixed(2);
                errores.push(`${archivo.name}: ${sizeMB}MB excede el límite de ${this.MAX_SIZE_MB}MB`);
                omitidos++;
                continue;
            }
            
            // Advertir si está cerca del límite
            const sizeMB = archivo.size / (1024 * 1024);
            if (sizeMB > this.ADVERTENCIA_SIZE_MB) {
                advertencias.push(`${archivo.name}: ${sizeMB.toFixed(1)}MB (archivo grande, puede tardar)`);
            }
            
            // Validar límite total de imágenes
            if (this.imagenesSeleccionadas.length >= this.MAX_IMAGENES) {
                errores.push(`Límite alcanzado: máximo ${this.MAX_IMAGENES} imágenes por carga`);
                omitidos++;
                break;
            }
            
            // Generar ID único
            const id = `img_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            
            // Crear URL de preview
            const previewUrl = URL.createObjectURL(archivo);
            
            // Agregar a la lista
            this.imagenesSeleccionadas.push({
                file: archivo,
                id: id,
                previewUrl: previewUrl
            });
            
            agregados++;
            
            // Yield al event loop cada 3 archivos para mantener UI responsive
            if (agregados % 3 === 0) {
                await this.delay(10);
            }
        }
        
        // Mostrar errores con toast descriptivo
        if (errores.length > 0) {
            console.warn('⚠️ Archivos omitidos:', errores);
            this.mostrarToast(
                `${errores.length} archivo(s) no se pudieron agregar`,
                'error',
                errores,
                8000
            );
        }
        
        // Mostrar advertencias si hay archivos grandes
        if (advertencias.length > 0 && errores.length === 0) {
            this.mostrarToast(
                `${advertencias.length} archivo(s) son muy grandes y pueden tardar en subir`,
                'warning',
                advertencias,
                5000
            );
        }
        
        if (agregados > 0) {
            console.log(`✅ ${agregados} imagen(es) agregada(s). Total: ${this.imagenesSeleccionadas.length}`);
        }
        
        // Actualizar UI
        this.actualizarPreview();
        
        // v5.0: Ya no se llama a transferirArchivosAInputUnificado()
        // El array interno es la fuente de verdad, FormData se construye desde él
        
        // Marcar como listo
        this.estaProcesando = false;
        this.archivosListos = this.imagenesSeleccionadas.length > 0;
        this.actualizarEstadoBotonSubir();
        this.actualizarPanelResumen();
        
        console.log(`✅ Procesamiento completado. Archivos listos: ${this.archivosListos}`);
    }
    
    /**
     * Utilidad: Delay para yield al event loop
     */
    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    /**
     * Actualiza el estado del botón de subir según el contexto.
     */
    public actualizarEstadoBotonSubir(): void {
        if (!this.btnSubir) {
            return;
        }
        
        // Obtener resumen para validar límite total
        const resumen = this.obtenerResumen();
        
        // Deshabilitar si está procesando, enviando, no hay imágenes listas, o excede límite total
        const debeEstarDeshabilitado = this.estaProcesando || 
                                        this.enviando || 
                                        !this.archivosListos || 
                                        this.imagenesSeleccionadas.length === 0 ||
                                        resumen.excedeLimiteTotal;
        
        this.btnSubir.disabled = debeEstarDeshabilitado;
        
        // Cambiar texto del botón según estado
        if (resumen.excedeLimiteTotal) {
            this.btnSubir.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Excede límite del servidor';
        } else if (this.enviando) {
            this.btnSubir.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Subiendo...';
        } else if (this.estaProcesando) {
            this.btnSubir.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Procesando...';
        } else if (this.imagenesSeleccionadas.length > 0) {
            this.btnSubir.innerHTML = `<i class="bi bi-cloud-upload"></i> Subir ${this.imagenesSeleccionadas.length} Imagen${this.imagenesSeleccionadas.length !== 1 ? 'es' : ''}`;
        } else {
            this.btnSubir.innerHTML = '<i class="bi bi-cloud-upload"></i> Subir Imágenes';
        }
        
        console.log(`🔘 Botón: ${debeEstarDeshabilitado ? 'DESHABILITADO' : 'HABILITADO'} | Procesando: ${this.estaProcesando} | Enviando: ${this.enviando} | Listos: ${this.archivosListos} | Excede límite: ${resumen.excedeLimiteTotal}`);
    }
    
    /**
     * Actualiza la visualización del preview de imágenes
     */
    private actualizarPreview(): void {
        if (!this.previewContainer || !this.contenedorMiniaturas || !this.cantidadSpan) {
            return;
        }
        
        // Mostrar u ocultar el contenedor de preview
        if (this.imagenesSeleccionadas.length > 0) {
            this.previewContainer.style.display = 'block';
            
            // Actualizar contador
            this.cantidadSpan.textContent = String(this.imagenesSeleccionadas.length);
            
            // Limpiar miniaturas existentes
            this.contenedorMiniaturas.innerHTML = '';
            
            // Crear miniaturas
            this.imagenesSeleccionadas.forEach((imagen, index) => {
                const miniatura = this.crearMiniatura(imagen, index);
                if (this.contenedorMiniaturas) {
                    this.contenedorMiniaturas.appendChild(miniatura);
                }
            });
        } else {
            this.previewContainer.style.display = 'none';
        }
    }
    
    /**
     * Crea un elemento de miniatura para una imagen
     */
    private crearMiniatura(imagen: ImagenPreview, index: number): HTMLElement {
        const col = document.createElement('div');
        col.className = 'col-4 col-sm-3 col-md-2';
        
        // Calcular tamaño del archivo
        const sizeMB = imagen.file.size / (1024 * 1024);
        const sizeText = sizeMB.toFixed(2);
        
        // Color del indicador según tamaño
        let sizeClass = 'text-success'; // < 10MB
        if (sizeMB > this.ADVERTENCIA_SIZE_MB) {
            sizeClass = 'text-warning fw-bold';
        } else if (sizeMB > 20) {
            sizeClass = 'text-info';
        }
        
        col.innerHTML = `
            <div class="preview-thumbnail" data-id="${imagen.id}">
                <img src="${imagen.previewUrl}" alt="Preview ${index + 1}">
                <button type="button" class="btn-eliminar-preview" data-id="${imagen.id}" title="Eliminar imagen">
                    <i class="bi bi-x-circle-fill"></i>
                </button>
                <div class="preview-info">
                    <small class="${sizeClass}">${sizeText} MB</small>
                </div>
            </div>
        `;
        
        // Event listener para eliminar
        const btnEliminar = col.querySelector('.btn-eliminar-preview') as HTMLButtonElement;
        if (btnEliminar) {
            btnEliminar.addEventListener('click', () => this.eliminarImagen(imagen.id));
        }
        
        return col;
    }
    
    /**
     * Elimina una imagen del array de seleccionadas.
     * v5.0: Simplificado, ya no transfiere a input oculto.
     */
    private eliminarImagen(id: string): void {
        const index = this.imagenesSeleccionadas.findIndex(img => img.id === id);
        
        if (index !== -1) {
            const nombreArchivo = this.imagenesSeleccionadas[index].file.name;
            
            // Liberar memoria del ObjectURL
            URL.revokeObjectURL(this.imagenesSeleccionadas[index].previewUrl);
            
            // Eliminar del array
            this.imagenesSeleccionadas.splice(index, 1);
            
            console.log(`🗑️ Imagen eliminada: ${nombreArchivo}. Total: ${this.imagenesSeleccionadas.length}`);
            
            // Actualizar UI
            this.actualizarPreview();
            this.archivosListos = this.imagenesSeleccionadas.length > 0;
            this.actualizarEstadoBotonSubir();
            this.actualizarPanelResumen();
        }
    }
    
    /**
     * Limpia todas las imágenes seleccionadas.
     * v5.0: Simplificado, ya no limpia input oculto.
     */
    private limpiarTodo(): void {
        // Liberar memoria de todos los ObjectURLs
        this.imagenesSeleccionadas.forEach(img => {
            URL.revokeObjectURL(img.previewUrl);
        });
        
        // Limpiar array
        this.imagenesSeleccionadas = [];
        
        // Limpiar inputs de selección
        if (this.inputGaleria) this.inputGaleria.value = '';
        if (this.inputCamara) this.inputCamara.value = '';
        
        // Resetear estados
        this.estaProcesando = false;
        this.archivosListos = false;
        this.enviando = false;
        
        console.log('🧹 Todas las imágenes eliminadas');
        
        // Actualizar UI
        this.actualizarPreview();
        this.actualizarEstadoBotonSubir();
        this.actualizarPanelResumen();
    }
    
    /**
     * Limpia memoria al destruir el objeto
     */
    public destroy(): void {
        this.imagenesSeleccionadas.forEach(img => {
            URL.revokeObjectURL(img.previewUrl);
        });
        this.imagenesSeleccionadas = [];
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    // Verificar que estamos en la página correcta
    if (document.getElementById('formSubirImagenes')) {
        (window as any).uploadImagenesDual = new UploadImagenesDual();
        console.log('✅ Sistema de subida dual v5.0 inicializado');
    }
});
