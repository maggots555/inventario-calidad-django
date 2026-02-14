"use strict";
// ============================================================================
// SISTEMA DUAL DE SUBIDA DE IMÁGENES - GALERÍA Y CÁMARA
// Versión 6.0 - Subida por lotes con reintentos automáticos (anti-Cloudflare)
// ============================================================================
class UploadImagenesDual {
    constructor() {
        // NUEVO v5.0: IDs de campos Django (leídos desde data-* attributes del form)
        this.tipoSelectId = '';
        this.descripcionInputId = '';
        // Panel de resumen
        this.panelResumen = null;
        // Contenedor de toasts
        this.toastContainer = null;
        // Array de imágenes seleccionadas (FUENTE DE VERDAD)
        this.imagenesSeleccionadas = [];
        // Límites de validación
        this.MAX_IMAGENES = 30;
        this.MAX_SIZE_MB = 50;
        this.MAX_SIZE_BYTES = this.MAX_SIZE_MB * 1024 * 1024;
        this.ADVERTENCIA_SIZE_MB = 40; // Advertir si > 40MB
        // Límite total del request (alineado con Cloudflare Free: 100MB max)
        this.MAX_REQUEST_SIZE_MB = 95; // DATA_UPLOAD_MAX_MEMORY_SIZE
        this.MAX_REQUEST_SIZE_BYTES = this.MAX_REQUEST_SIZE_MB * 1024 * 1024;
        this.ADVERTENCIA_REQUEST_MB = 76; // Advertir al 80% del límite
        // NUEVO v5.0: Timeout de XHR (10 minutos, alineado con Gunicorn y Nginx)
        this.XHR_TIMEOUT_MS = 600000;
        // v6.0: Configuración de subida por lotes (anti-Cloudflare disconnect)
        // Cada lote genera un request HTTP independiente, nueva conexión cada vez
        this.BATCH_SIZE = 5; // Imágenes por lote (~15-25MB typ.)
        this.MAX_RETRIES = 2; // Reintentos por lote fallido
        this.RETRY_DELAY_MS = 3000; // Delay base entre reintentos (×intento)
        // v6.0: Estado de progreso por lotes
        this.loteActual = 0;
        this.totalLotes = 0;
        // Control de estado de procesamiento
        this.estaProcesando = false;
        this.archivosListos = false;
        // Control de envío (para evitar doble-click)
        this.enviando = false;
        this.ultimoClickSubir = 0;
        this.DEBOUNCE_MS = 1500; // 1.5 segundos entre clicks
        // NUEVO v5.0: Flag para protección beforeunload
        this.subiendoImagenes = false;
        // Elementos de selección de archivos
        this.inputGaleria = document.getElementById('inputGaleria');
        this.inputCamara = document.getElementById('inputCamara');
        this.previewContainer = document.getElementById('previewImagenes');
        this.contenedorMiniaturas = document.getElementById('contenedorMiniaturas');
        this.btnSubir = document.getElementById('btnSubirImagenes');
        this.btnLimpiarTodo = document.getElementById('btnLimpiarTodo');
        this.cantidadSpan = document.getElementById('cantidadImagenes');
        // NUEVO v5.0: Elementos del formulario y progreso
        this.formElement = document.getElementById('formSubirImagenes');
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
    init() {
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
    inicializarFormularioSubida() {
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
    handleSubmit(e) {
        e.preventDefault(); // Prevenir envío normal del formulario
        // Verificar si puede enviar (no procesando, no enviando, hay archivos)
        if (!this.puedeEnviar()) {
            console.warn('⚠️ El sistema está procesando o no está listo. Ignorando submit.');
            if (this.getEstaEnviando()) {
                this.mostrarToast('Ya hay una subida en progreso. Por favor espera.', 'warning');
            }
            else if (this.getEstaProcesando()) {
                this.mostrarToast('Los archivos aún se están procesando. Espera un momento.', 'info');
            }
            else {
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
        // v6.0: Dividir archivos en lotes de BATCH_SIZE
        // Cada lote se envía como un request HTTP independiente,
        // lo que evita que Cloudflare Tunnel corte la conexión.
        const lotes = [];
        for (let i = 0; i < archivosParaSubir.length; i += this.BATCH_SIZE) {
            lotes.push(archivosParaSubir.slice(i, i + this.BATCH_SIZE));
        }
        console.log(`📦 Dividiendo ${archivosParaSubir.length} imagen(es) en ${lotes.length} lote(s) de hasta ${this.BATCH_SIZE}`);
        // Deshabilitar formulario durante la subida
        this.deshabilitarFormulario();
        // Mostrar barra de progreso
        if (this.progresoDiv)
            this.progresoDiv.style.display = 'block';
        if (this.barraProgreso)
            this.barraProgreso.style.width = '0%';
        if (this.textoProgreso)
            this.textoProgreso.textContent = 'Iniciando subida...';
        if (this.porcentajeProgreso)
            this.porcentajeProgreso.textContent = '0%';
        // Activar protección beforeunload
        this.subiendoImagenes = true;
        // Iniciar subida por lotes (async)
        this.enviarPorLotes(lotes);
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
    construirFormData(archivos) {
        const formData = new FormData();
        // Agregar token CSRF
        if (this.formElement) {
            const csrfInput = this.formElement.querySelector('input[name="csrfmiddlewaretoken"]');
            if (csrfInput) {
                formData.append('csrfmiddlewaretoken', csrfInput.value);
            }
        }
        // Agregar tipo de formulario
        formData.append('form_type', 'subir_imagenes');
        // Agregar tipo de imagen desde el select de Django
        if (this.tipoSelectId) {
            const tipoSelect = document.getElementById(this.tipoSelectId);
            if (tipoSelect) {
                formData.append('tipo', tipoSelect.value);
            }
        }
        // Agregar descripción desde el input de Django
        if (this.descripcionInputId) {
            const descripcionInput = document.getElementById(this.descripcionInputId);
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
    // =========================================================================
    // v6.0: SISTEMA DE SUBIDA POR LOTES CON REINTENTOS AUTOMÁTICOS
    // =========================================================================
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Envía las imágenes divididas en lotes pequeños (5 imágenes cada uno).
     *
     * ¿Por qué lotes? Cloudflare Tunnel (el proxy que protege tu servidor)
     * a veces corta conexiones grandes de forma aleatoria. Al dividir en
     * lotes pequeños (~15-25MB cada uno), cada request es rápido y tiene
     * mucha menos probabilidad de ser cortado.
     *
     * Si un lote falla, se reintenta automáticamente hasta 2 veces con
     * espera creciente (3s, 6s). Cada reintento crea una nueva conexión
     * HTTP, evitando el problema de la conexión anterior.
     *
     * Los lotes anteriores exitosos Ya están guardados en el servidor,
     * así que si el lote 3 falla, las imágenes de los lotes 1 y 2 no se pierden.
     */
    async enviarPorLotes(lotes) {
        this.totalLotes = lotes.length;
        const resultados = [];
        let totalImagenesGuardadas = 0;
        let totalErrores = [];
        let lotesExitosos = 0;
        let lotesReintentados = 0;
        let huboFalloDefinitivo = false;
        // Calcular totales para info
        const totalArchivos = lotes.reduce((sum, l) => sum + l.length, 0);
        const totalBytes = lotes.reduce((sum, l) => sum + l.reduce((s, f) => s + f.size, 0), 0);
        const totalMB = (totalBytes / (1024 * 1024)).toFixed(2);
        // Mostrar info inicial
        if (this.infoArchivos) {
            this.infoArchivos.innerHTML = `
                <div class="d-flex align-items-center justify-content-between flex-wrap">
                    <span><i class="bi bi-collection"></i> <strong>${totalArchivos}</strong> imagen${totalArchivos !== 1 ? 'es' : ''} en <strong>${lotes.length}</strong> lote${lotes.length !== 1 ? 's' : ''}</span>
                    <span class="badge bg-secondary">${totalMB} MB total</span>
                </div>
            `;
        }
        // Procesar cada lote secuencialmente
        for (let i = 0; i < lotes.length; i++) {
            this.loteActual = i + 1;
            const lote = lotes[i];
            let intentos = 0;
            let exito = false;
            let resultado = null;
            // Intentar enviar el lote (con reintentos automáticos)
            while (intentos <= this.MAX_RETRIES && !exito) {
                if (intentos > 0) {
                    // Es un reintento — nueva conexión HTTP
                    lotesReintentados++;
                    const delayMs = this.RETRY_DELAY_MS * intentos;
                    console.warn(`🔄 Reintento ${intentos}/${this.MAX_RETRIES} del lote ${i + 1} en ${delayMs / 1000}s...`);
                    this.mostrarReintento(i + 1, lotes.length, intentos, delayMs);
                    await this.delay(delayMs);
                }
                try {
                    resultado = await this.enviarLote(lote, i, lotes.length);
                    if (resultado.success) {
                        exito = true;
                        lotesExitosos++;
                        totalImagenesGuardadas += resultado.imagenesGuardadas;
                        if (resultado.errores.length > 0) {
                            totalErrores = totalErrores.concat(resultado.errores);
                        }
                        resultados.push(resultado);
                        console.log(`✅ Lote ${i + 1}/${lotes.length}: ${resultado.imagenesGuardadas} imagen(es) guardadas`);
                        // Remover las imágenes exitosas del array interno
                        this.removerImagenesSubidas(lote);
                    }
                    else {
                        // El servidor respondió con error (no error de red)
                        console.error(`❌ Lote ${i + 1}: Error del servidor — ${resultado.message}`);
                        if (resultado.imagenesGuardadas > 0) {
                            // Éxito parcial: guardó algunas antes del error
                            totalImagenesGuardadas += resultado.imagenesGuardadas;
                            resultados.push(resultado);
                            // No reintentar: el servidor ya procesó parcialmente
                        }
                        totalErrores.push(`Lote ${i + 1}: ${resultado.message}`);
                        break; // No reintentar errores del servidor (validación, etc.)
                    }
                }
                catch (errorInfo) {
                    // Error de red (XHR error/timeout) — SÍ reintentar
                    intentos++;
                    const info = errorInfo;
                    console.error(`❌ Lote ${i + 1}: Error de red (intento ${intentos}/${this.MAX_RETRIES + 1}) — ${info.tipo}`);
                    if (intentos > this.MAX_RETRIES) {
                        // Agotados los reintentos para este lote
                        huboFalloDefinitivo = true;
                        resultados.push({
                            batchIndex: i,
                            success: false,
                            imagenesGuardadas: 0,
                            imagenesOmitidas: [],
                            errores: [`Lote ${i + 1}: Fallo después de ${this.MAX_RETRIES + 1} intentos (${info.tipo})`],
                            cambioEstado: false,
                            message: info.diagnostico,
                            archivosEnviados: lote.length
                        });
                        totalErrores.push(`Lote ${i + 1} (${lote.length} imgs): ${info.diagnostico}`);
                    }
                }
            }
        }
        // Desactivar protección beforeunload
        this.subiendoImagenes = false;
        this.marcarFinEnvio();
        // Mostrar resumen final consolidado
        this.mostrarResumenFinal(totalImagenesGuardadas, totalErrores, lotesExitosos, lotes.length, lotesReintentados, huboFalloDefinitivo);
    }
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Envía UN solo lote de imágenes al servidor usando XMLHttpRequest (XHR).
     * Retorna una Promise (promesa) que se resuelve cuando el servidor responde,
     * o se rechaza si hay un error de red (Cloudflare cortó la conexión, etc.)
     *
     * Cada llamada a este método crea un XHR NUEVO = una conexión HTTP nueva.
     * Esto es clave: si la conexión anterior se cortó, la nueva es independiente.
     */
    enviarLote(archivos, batchIndex, totalBatches) {
        return new Promise((resolve, reject) => {
            var _a;
            const formData = this.construirFormData(archivos);
            const tamanioLote = archivos.reduce((sum, f) => sum + f.size, 0);
            const tamanioMB = (tamanioLote / (1024 * 1024)).toFixed(2);
            console.log(`📤 Enviando lote ${batchIndex + 1}/${totalBatches}: ${archivos.length} archivo(s), ${tamanioMB} MB`);
            const xhr = new XMLHttpRequest();
            // Progreso: calcular posición global dentro de todos los lotes
            xhr.upload.addEventListener('progress', (e) => {
                if (!e.lengthComputable)
                    return;
                const porcentajeLote = Math.round((e.loaded / e.total) * 100);
                // Progreso global: cada lote contribuye una fracción igual
                const porcentajeBase = (batchIndex / totalBatches) * 100;
                const porcentajeContribucion = (1 / totalBatches) * 100;
                const porcentajeGlobal = Math.round(porcentajeBase + (porcentajeLote / 100) * porcentajeContribucion);
                if (this.barraProgreso)
                    this.barraProgreso.style.width = porcentajeGlobal + '%';
                if (this.porcentajeProgreso)
                    this.porcentajeProgreso.textContent = porcentajeGlobal + '%';
                if (porcentajeLote < 100) {
                    // Subiendo datos al servidor
                    if (this.textoProgreso) {
                        this.textoProgreso.textContent = totalBatches > 1
                            ? `Lote ${batchIndex + 1}/${totalBatches} — Subiendo... ${porcentajeLote}%`
                            : `Subiendo... ${porcentajeLote}%`;
                    }
                    if (this.infoArchivos) {
                        const mbSubidos = (e.loaded / (1024 * 1024)).toFixed(2);
                        this.infoArchivos.innerHTML = `
                            <div class="d-flex align-items-center justify-content-between flex-wrap">
                                <span><i class="bi bi-cloud-arrow-up text-primary"></i> ${totalBatches > 1 ? `Lote ${batchIndex + 1}/${totalBatches}: ` : ''}Subiendo <strong>${archivos.length}</strong> imagen${archivos.length !== 1 ? 'es' : ''}...</span>
                                <span class="badge bg-primary">${mbSubidos} / ${tamanioMB} MB</span>
                            </div>
                            ${totalBatches > 1 ? `<div class="mt-1"><small class="text-muted">Progreso global: ${porcentajeGlobal}%</small></div>` : ''}
                        `;
                    }
                }
                else {
                    // Datos enviados, servidor procesando
                    if (this.textoProgreso) {
                        this.textoProgreso.textContent = totalBatches > 1
                            ? `Lote ${batchIndex + 1}/${totalBatches} — Procesando en servidor...`
                            : 'Procesando en servidor...';
                    }
                    if (this.barraProgreso)
                        this.barraProgreso.classList.add('progress-bar-striped');
                    if (this.infoArchivos) {
                        this.infoArchivos.innerHTML = `
                            <div class="d-flex align-items-center">
                                <span class="spinner-border spinner-border-sm text-info me-2"></span>
                                <span>${totalBatches > 1 ? `Lote ${batchIndex + 1}/${totalBatches}: ` : ''}Comprimiendo y guardando ${archivos.length} imagen${archivos.length !== 1 ? 'es' : ''}...</span>
                            </div>
                        `;
                    }
                }
            });
            // Respuesta del servidor
            xhr.addEventListener('load', () => {
                if (this.barraProgreso)
                    this.barraProgreso.classList.remove('progress-bar-striped');
                if (xhr.status === 200 || xhr.status === 500) {
                    try {
                        const data = JSON.parse(xhr.responseText);
                        resolve({
                            batchIndex: batchIndex,
                            success: data.success,
                            imagenesGuardadas: data.imagenes_guardadas || 0,
                            imagenesOmitidas: data.imagenes_omitidas || [],
                            errores: data.errores || [],
                            cambioEstado: data.cambio_estado || false,
                            message: data.message || data.error || '',
                            archivosEnviados: archivos.length
                        });
                    }
                    catch (e) {
                        console.error('Error al parsear respuesta del lote:', e);
                        reject({ tipo: 'parse_error', diagnostico: 'Respuesta del servidor no válida' });
                    }
                }
                else {
                    reject({ tipo: `http_${xhr.status}`, diagnostico: `Error HTTP ${xhr.status}` });
                }
            });
            // Error de red — esto es lo que dispara Cloudflare al cortar
            xhr.addEventListener('error', () => {
                let tipo = 'desconocido';
                let diagnostico = '';
                if (!navigator.onLine) {
                    tipo = 'sin_internet';
                    diagnostico = 'Sin conexión a internet';
                }
                else if (tamanioLote > 100 * 1024 * 1024) {
                    tipo = 'cloudflare_limite';
                    diagnostico = `Lote de ${tamanioMB}MB excede límite Cloudflare`;
                }
                else {
                    tipo = 'conexion_cortada';
                    diagnostico = 'Conexión cortada (Cloudflare Tunnel, red inestable)';
                }
                console.error(`[LOTE ${batchIndex + 1} ERROR] Tipo: ${tipo} | ${diagnostico}`);
                console.error(`[LOTE ${batchIndex + 1} ERROR] Archivos: ${archivos.length}, Tamaño: ${tamanioMB} MB, Hora: ${new Date().toISOString()}`);
                reject({ tipo, diagnostico });
            });
            // Timeout
            xhr.addEventListener('timeout', () => {
                console.error(`[LOTE ${batchIndex + 1} TIMEOUT] ${tamanioMB}MB, timeout=${this.XHR_TIMEOUT_MS / 1000}s`);
                reject({ tipo: 'timeout', diagnostico: `Timeout después de ${this.XHR_TIMEOUT_MS / 60000} minutos` });
            });
            // Abrir y enviar (nueva conexión HTTP cada vez)
            const url = ((_a = this.formElement) === null || _a === void 0 ? void 0 : _a.action) || window.location.href;
            xhr.open('POST', url);
            xhr.timeout = this.XHR_TIMEOUT_MS;
            xhr.send(formData);
        });
    }
    /**
     * Muestra la UI de reintento: barra amarilla con countdown.
     */
    mostrarReintento(loteNum, totalLotes, intento, delayMs) {
        if (this.textoProgreso) {
            this.textoProgreso.textContent = `Reintentando lote ${loteNum}/${totalLotes}...`;
        }
        if (this.barraProgreso) {
            this.barraProgreso.classList.add('progress-bar-striped', 'progress-bar-animated');
            this.barraProgreso.classList.remove('bg-success', 'bg-danger');
            this.barraProgreso.classList.add('bg-warning');
        }
        if (this.infoArchivos) {
            this.infoArchivos.innerHTML = `
                <div class="d-flex align-items-center text-warning">
                    <span class="spinner-border spinner-border-sm me-2"></span>
                    <span>
                        <i class="bi bi-arrow-repeat"></i>
                        Reintento ${intento}/${this.MAX_RETRIES} del lote ${loteNum} — esperando ${delayMs / 1000}s...
                        <br><small class="text-muted">Los lotes anteriores se guardaron correctamente.</small>
                    </span>
                </div>
            `;
        }
    }
    /**
     * Remueve del array interno las imágenes que ya se subieron exitosamente.
     * Usa nombre+tamaño como clave para identificar cada archivo.
     */
    removerImagenesSubidas(archivosSubidos) {
        const clavesSubidas = new Set(archivosSubidos.map(f => `${f.name}_${f.size}_${f.lastModified}`));
        this.imagenesSeleccionadas = this.imagenesSeleccionadas.filter(img => {
            const clave = `${img.file.name}_${img.file.size}_${img.file.lastModified}`;
            if (clavesSubidas.has(clave)) {
                URL.revokeObjectURL(img.previewUrl); // Liberar memoria
                return false; // Remover del array
            }
            return true; // Mantener
        });
    }
    /**
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Muestra el resumen final después de que todos los lotes terminaron.
     * Hay 3 escenarios posibles:
     * 1. Todo exitoso → mensaje verde, recarga la página
     * 2. Éxito parcial → mensaje amarillo, las imágenes pendientes quedan seleccionadas
     * 3. Todo falló → mensaje rojo, todas las imágenes quedan seleccionadas para reintento
     */
    mostrarResumenFinal(totalGuardadas, errores, lotesExitosos, totalLotes, lotesReintentados, huboFalloDefinitivo) {
        if (totalGuardadas > 0 && !huboFalloDefinitivo) {
            // ═══════════════════════════════════════════════════════════
            // ESCENARIO 1: TODO EXITOSO
            // ═══════════════════════════════════════════════════════════
            if (this.barraProgreso) {
                this.barraProgreso.classList.remove('progress-bar-animated', 'progress-bar-striped', 'bg-warning');
                this.barraProgreso.classList.add('bg-success');
                this.barraProgreso.style.width = '100%';
            }
            if (this.textoProgreso)
                this.textoProgreso.textContent = '¡Completado!';
            if (this.porcentajeProgreso)
                this.porcentajeProgreso.textContent = '✓';
            let mensaje = `✅ ${totalGuardadas} imagen(es) subida(s) correctamente.`;
            if (totalLotes > 1) {
                mensaje += ` (${lotesExitosos} lote${lotesExitosos !== 1 ? 's' : ''})`;
            }
            if (lotesReintentados > 0) {
                mensaje += ` — ${lotesReintentados} reintento(s) exitoso(s)`;
            }
            let html = `
                <div class="d-flex align-items-center text-success">
                    <i class="bi bi-check-circle-fill me-2"></i>
                    <span>${mensaje}</span>
                </div>
            `;
            if (errores.length > 0) {
                html += `
                    <div class="mt-1">
                        <small class="text-danger">
                            <i class="bi bi-x-circle"></i> ${errores.length} error(es) menores al procesar
                        </small>
                    </div>
                `;
            }
            if (this.infoArchivos)
                this.infoArchivos.innerHTML = html;
            this.limpiarDespuesDeExito();
            // Recargar para mostrar las imágenes guardadas
            setTimeout(() => { window.location.reload(); }, 1500);
        }
        else if (totalGuardadas > 0 && huboFalloDefinitivo) {
            // ═══════════════════════════════════════════════════════════
            // ESCENARIO 2: ÉXITO PARCIAL (algunas subidas, otras fallaron)
            // ═══════════════════════════════════════════════════════════
            if (this.barraProgreso) {
                this.barraProgreso.classList.remove('progress-bar-animated', 'progress-bar-striped', 'bg-success', 'bg-danger');
                this.barraProgreso.classList.add('bg-warning');
                this.barraProgreso.style.width = '100%';
            }
            if (this.textoProgreso)
                this.textoProgreso.textContent = 'Parcialmente completado';
            if (this.porcentajeProgreso)
                this.porcentajeProgreso.textContent = '⚠';
            const restantes = this.imagenesSeleccionadas.length;
            let html = `
                <div class="text-warning">
                    <i class="bi bi-exclamation-triangle-fill me-1"></i>
                    Se subieron <strong>${totalGuardadas}</strong> imagen(es), pero <strong>${restantes}</strong> no pudieron enviarse.
                </div>
                <div class="mt-1">
                    <small class="text-muted">
                        <i class="bi bi-info-circle"></i> Las imágenes pendientes siguen seleccionadas.
                        Puedes presionar <strong>Subir</strong> de nuevo para reintentarlas.
                    </small>
                </div>
            `;
            if (errores.length > 0) {
                html += `
                    <details class="mt-2">
                        <summary class="text-muted" style="cursor: pointer; font-size: 0.8rem;">
                            <i class="bi bi-bug"></i> Detalles técnicos (${errores.length})
                        </summary>
                        <div class="mt-1 p-2 bg-light rounded" style="font-size: 0.75rem; font-family: monospace;">
                            ${errores.map(e => `<div>• ${e}</div>`).join('')}
                        </div>
                    </details>
                `;
            }
            if (this.infoArchivos)
                this.infoArchivos.innerHTML = html;
            // Actualizar preview y botón para las imágenes restantes
            this.actualizarPreview();
            this.archivosListos = this.imagenesSeleccionadas.length > 0;
            this.actualizarEstadoBotonSubir();
            this.actualizarPanelResumen();
            // Rehabilitar formulario para reintento manual
            setTimeout(() => { this.rehabilitarFormulario(); }, 2000);
            this.mostrarToast(`${totalGuardadas} imagen(es) subida(s). ${restantes} pendiente(s) — presiona Subir para reintentar.`, 'warning', undefined, 10000);
        }
        else {
            // ═══════════════════════════════════════════════════════════
            // ESCENARIO 3: TODO FALLÓ
            // ═══════════════════════════════════════════════════════════
            if (this.barraProgreso) {
                this.barraProgreso.classList.remove('bg-success', 'progress-bar-animated', 'progress-bar-striped', 'bg-warning');
                this.barraProgreso.classList.add('bg-danger');
                this.barraProgreso.style.width = '100%';
            }
            if (this.textoProgreso)
                this.textoProgreso.textContent = 'Error';
            if (this.porcentajeProgreso)
                this.porcentajeProgreso.textContent = '✗';
            let html = `
                <div class="text-danger">
                    <i class="bi bi-x-circle-fill me-1"></i>
                    No se pudo subir ninguna imagen después de múltiples intentos.
                </div>
                <div class="mt-1">
                    <small class="text-muted">
                        <i class="bi bi-info-circle"></i> Tus imágenes siguen seleccionadas.
                        Espera unos segundos y presiona <strong>Subir</strong> para reintentar.
                    </small>
                </div>
            `;
            if (errores.length > 0) {
                html += `
                    <details class="mt-2">
                        <summary class="text-muted" style="cursor: pointer; font-size: 0.8rem;">
                            <i class="bi bi-bug"></i> Info técnica para soporte
                        </summary>
                        <div class="mt-1 p-2 bg-light rounded" style="font-size: 0.75rem; font-family: monospace;">
                            ${errores.map(e => `<div>• ${e}</div>`).join('')}
                            <div><strong>Hora:</strong> ${new Date().toLocaleString('es-MX')}</div>
                            <div><strong>Navegador:</strong> ${navigator.userAgent.substring(0, 80)}...</div>
                            <div><strong>Online:</strong> ${navigator.onLine ? 'Sí' : 'No'}</div>
                        </div>
                    </details>
                `;
            }
            if (this.infoArchivos)
                this.infoArchivos.innerHTML = html;
            this.mostrarToast('No se pudo completar la subida. Presiona Subir para reintentar.', 'error', undefined, 10000);
            // Rehabilitar formulario y resetear barra después de 4 segundos
            setTimeout(() => {
                this.rehabilitarFormulario();
                if (this.progresoDiv)
                    this.progresoDiv.style.display = 'none';
                if (this.barraProgreso) {
                    this.barraProgreso.classList.remove('bg-danger');
                    this.barraProgreso.classList.add('progress-bar-animated', 'bg-success');
                    this.barraProgreso.style.width = '0%';
                }
                this.actualizarEstadoBotonSubir();
            }, 4000);
        }
    }
    /**
     * Deshabilita el formulario durante la subida.
     * Previene interacción con los controles mientras se sube.
     */
    deshabilitarFormulario() {
        if (this.btnSubir) {
            this.btnSubir.disabled = true;
            this.btnSubir.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Subiendo...';
        }
        // Deshabilitar select de tipo y input de descripción
        if (this.tipoSelectId) {
            const tipoSelect = document.getElementById(this.tipoSelectId);
            if (tipoSelect)
                tipoSelect.disabled = true;
        }
        if (this.descripcionInputId) {
            const descripcionInput = document.getElementById(this.descripcionInputId);
            if (descripcionInput)
                descripcionInput.disabled = true;
        }
    }
    /**
     * Rehabilita el formulario después de un error.
     * Permite al usuario reintentar la subida.
     */
    rehabilitarFormulario() {
        if (this.btnSubir)
            this.btnSubir.disabled = false;
        // Rehabilitar select de tipo y input de descripción
        if (this.tipoSelectId) {
            const tipoSelect = document.getElementById(this.tipoSelectId);
            if (tipoSelect)
                tipoSelect.disabled = false;
        }
        if (this.descripcionInputId) {
            const descripcionInput = document.getElementById(this.descripcionInputId);
            if (descripcionInput)
                descripcionInput.disabled = false;
        }
    }
    /**
     * Protección beforeunload: advierte al usuario si intenta cerrar/navegar
     * durante una subida activa. Se activa al iniciar el XHR y se desactiva
     * al completar (éxito o error).
     */
    advertenciaBeforeUnload(e) {
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
    crearContenedorToasts() {
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
    mostrarToast(mensaje, tipo = 'info', detalles, duracion = 6000) {
        if (!this.toastContainer)
            return;
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
            if (typeof window.bootstrap !== 'undefined') {
                const bsToast = new window.bootstrap.Toast(toastElement, {
                    autohide: true,
                    delay: duracion
                });
                bsToast.show();
                // Eliminar del DOM después de ocultarse
                toastElement.addEventListener('hidden.bs.toast', () => {
                    toastElement.remove();
                });
            }
            else {
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
    crearPanelResumen() {
        var _a;
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
        (_a = previewContainer.parentElement) === null || _a === void 0 ? void 0 : _a.insertBefore(panel, previewContainer);
        this.panelResumen = panel;
    }
    /**
     * Actualiza el panel de resumen con la información actual
     */
    actualizarPanelResumen() {
        if (!this.panelResumen)
            return;
        const resumen = this.obtenerResumen();
        // Mostrar/ocultar panel
        if (resumen.cantidad > 0) {
            this.panelResumen.classList.remove('d-none');
        }
        else {
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
        const barraLimite = this.panelResumen.querySelector('#barraLimiteServidor');
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
            }
            else if (porcentajeUso >= 80) {
                barraLimite.classList.add('bg-warning');
                textoLimite.classList.add('text-warning');
            }
            else if (porcentajeUso >= 60) {
                barraLimite.classList.add('bg-info');
                textoLimite.classList.remove('text-danger', 'text-warning');
            }
            else {
                barraLimite.classList.add('bg-success');
                textoLimite.classList.remove('text-danger', 'text-warning');
            }
        }
        // Actualizar estado
        const estadoBadge = this.panelResumen.querySelector('#resumenEstado');
        if (estadoBadge) {
            if (this.estaProcesando) {
                estadoBadge.className = 'badge bg-warning';
                estadoBadge.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Procesando...';
            }
            else if (resumen.excedeLimiteTotal) {
                estadoBadge.className = 'badge bg-danger';
                estadoBadge.innerHTML = '<i class="bi bi-x-circle me-1"></i>Excede límite del servidor';
            }
            else if (resumen.listoParaSubir) {
                estadoBadge.className = 'badge bg-success';
                estadoBadge.innerHTML = '<i class="bi bi-check-circle me-1"></i>Listo para subir';
            }
            else {
                estadoBadge.className = 'badge bg-secondary';
                estadoBadge.textContent = 'Selecciona imágenes';
            }
        }
        // Actualizar advertencias
        const advertenciasDiv = this.panelResumen.querySelector('#resumenAdvertencias');
        const textoAdvertencias = this.panelResumen.querySelector('#textoAdvertencias');
        if (advertenciasDiv && textoAdvertencias) {
            const mensajes = [];
            if (resumen.excedeLimiteTotal) {
                const exceso = ((resumen.tamanioTotal / (1024 * 1024)) - this.MAX_REQUEST_SIZE_MB).toFixed(1);
                mensajes.push(`⚠️ El tamaño total excede el límite del servidor en ${exceso}MB. Elimina algunas imágenes.`);
            }
            else if (resumen.cercaDelLimite) {
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
                }
                else if (resumen.cercaDelLimite || resumen.archivosAdvertencia.length > 0) {
                    this.panelResumen.className = 'alert alert-warning mb-3';
                }
                else {
                    this.panelResumen.className = 'alert alert-info mb-3';
                }
            }
            else {
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
    puedeEnviar() {
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
    marcarEnviando() {
        this.enviando = true;
        this.ultimoClickSubir = Date.now();
        this.actualizarEstadoBotonSubir();
        console.log('📤 Envío iniciado - botón bloqueado');
    }
    /**
     * API PÚBLICA: Marcar que terminó el envío (éxito o error)
     */
    marcarFinEnvio() {
        this.enviando = false;
        this.actualizarEstadoBotonSubir();
        console.log('✅ Envío finalizado - botón desbloqueado');
    }
    /**
     * API PÚBLICA: Limpiar después de subida exitosa
     */
    limpiarDespuesDeExito() {
        this.limpiarTodo();
        this.marcarFinEnvio();
    }
    /**
     * API PÚBLICA: Obtener resumen de la subida para mostrar
     */
    obtenerResumen() {
        const archivosGrandes = [];
        const archivosAdvertencia = [];
        let tamanioTotal = 0;
        this.imagenesSeleccionadas.forEach(img => {
            tamanioTotal += img.file.size;
            const sizeMB = img.file.size / (1024 * 1024);
            if (sizeMB > this.MAX_SIZE_MB) {
                archivosGrandes.push(`${img.file.name} (${sizeMB.toFixed(1)}MB - excede límite)`);
            }
            else if (sizeMB > this.ADVERTENCIA_SIZE_MB) {
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
    getCantidadImagenes() {
        return this.imagenesSeleccionadas.length;
    }
    /**
     * API PÚBLICA: Verificar si está procesando
     */
    getEstaProcesando() {
        return this.estaProcesando;
    }
    /**
     * API PÚBLICA: Verificar si está enviando
     */
    getEstaEnviando() {
        return this.enviando;
    }
    /**
     * API PÚBLICA: Obtener los archivos seleccionados como array de File.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Este método devuelve los archivos directamente desde el array interno.
     * Es la fuente de verdad del sistema, inmune a modificaciones del DOM.
     */
    getArchivos() {
        return this.imagenesSeleccionadas.map(img => img.file);
    }
    // =========================================================================
    // Métodos de cámara integrada
    // =========================================================================
    /**
     * Abre el modal de cámara integrada
     */
    abrirCamaraIntegrada() {
        const camaraIntegrada = window.camaraIntegrada;
        if (camaraIntegrada) {
            camaraIntegrada.abrir();
        }
        else {
            console.error('❌ Cámara integrada no disponible');
            this.mostrarToast('La cámara integrada no está disponible. Verifica que estés usando HTTPS o localhost.', 'error');
        }
    }
    /**
     * Configura el callback para recibir fotos de la cámara integrada
     */
    configurarCamaraIntegrada() {
        // Esperar a que la cámara integrada esté disponible
        const intervalo = setInterval(() => {
            const camaraIntegrada = window.camaraIntegrada;
            if (camaraIntegrada) {
                clearInterval(intervalo);
                // Configurar callback para recibir fotos capturadas
                camaraIntegrada.setOnFotosCapturadas((fotos) => {
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
    agregarFotosDeCamara(fotos) {
        console.log(`📸 Recibidas ${fotos.length} foto(s) desde cámara integrada`);
        // Convertir Blobs a Files
        const archivos = fotos.map((blob, index) => {
            const timestamp = Date.now() + index;
            return new File([blob], `captura_${timestamp}.jpg`, { type: 'image/jpeg' });
        });
        // Agregar usando el método existente
        this.agregarArchivos(archivos);
        // Mostrar toast de confirmación
        this.mostrarToast(`${fotos.length} foto(s) capturada(s) desde la cámara`, 'success');
    }
    // =========================================================================
    // Manejo de archivos
    // =========================================================================
    /**
     * Maneja la selección de archivos desde cualquier input
     */
    handleFileSelect(event) {
        const input = event.target;
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
    async agregarArchivos(archivos) {
        // CRÍTICO: Marcar como procesando y deshabilitar botón de subir
        this.estaProcesando = true;
        this.archivosListos = false;
        this.actualizarEstadoBotonSubir();
        this.actualizarPanelResumen();
        let agregados = 0;
        let omitidos = 0;
        const errores = [];
        const advertencias = [];
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
            this.mostrarToast(`${errores.length} archivo(s) no se pudieron agregar`, 'error', errores, 8000);
        }
        // Mostrar advertencias si hay archivos grandes
        if (advertencias.length > 0 && errores.length === 0) {
            this.mostrarToast(`${advertencias.length} archivo(s) son muy grandes y pueden tardar en subir`, 'warning', advertencias, 5000);
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
    delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    /**
     * Actualiza el estado del botón de subir según el contexto.
     */
    actualizarEstadoBotonSubir() {
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
        }
        else if (this.enviando) {
            this.btnSubir.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Subiendo...';
        }
        else if (this.estaProcesando) {
            this.btnSubir.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Procesando...';
        }
        else if (this.imagenesSeleccionadas.length > 0) {
            this.btnSubir.innerHTML = `<i class="bi bi-cloud-upload"></i> Subir ${this.imagenesSeleccionadas.length} Imagen${this.imagenesSeleccionadas.length !== 1 ? 'es' : ''}`;
        }
        else {
            this.btnSubir.innerHTML = '<i class="bi bi-cloud-upload"></i> Subir Imágenes';
        }
        console.log(`🔘 Botón: ${debeEstarDeshabilitado ? 'DESHABILITADO' : 'HABILITADO'} | Procesando: ${this.estaProcesando} | Enviando: ${this.enviando} | Listos: ${this.archivosListos} | Excede límite: ${resumen.excedeLimiteTotal}`);
    }
    /**
     * Actualiza la visualización del preview de imágenes
     */
    actualizarPreview() {
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
        }
        else {
            this.previewContainer.style.display = 'none';
        }
    }
    /**
     * Crea un elemento de miniatura para una imagen
     */
    crearMiniatura(imagen, index) {
        const col = document.createElement('div');
        col.className = 'col-4 col-sm-3 col-md-2';
        // Calcular tamaño del archivo
        const sizeMB = imagen.file.size / (1024 * 1024);
        const sizeText = sizeMB.toFixed(2);
        // Color del indicador según tamaño
        let sizeClass = 'text-success'; // < 10MB
        if (sizeMB > this.ADVERTENCIA_SIZE_MB) {
            sizeClass = 'text-warning fw-bold';
        }
        else if (sizeMB > 20) {
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
        const btnEliminar = col.querySelector('.btn-eliminar-preview');
        if (btnEliminar) {
            btnEliminar.addEventListener('click', () => this.eliminarImagen(imagen.id));
        }
        return col;
    }
    /**
     * Elimina una imagen del array de seleccionadas.
     * v5.0: Simplificado, ya no transfiere a input oculto.
     */
    eliminarImagen(id) {
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
    limpiarTodo() {
        // Liberar memoria de todos los ObjectURLs
        this.imagenesSeleccionadas.forEach(img => {
            URL.revokeObjectURL(img.previewUrl);
        });
        // Limpiar array
        this.imagenesSeleccionadas = [];
        // Limpiar inputs de selección
        if (this.inputGaleria)
            this.inputGaleria.value = '';
        if (this.inputCamara)
            this.inputCamara.value = '';
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
    destroy() {
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
        window.uploadImagenesDual = new UploadImagenesDual();
        console.log('✅ Sistema de subida dual v5.0 inicializado');
    }
});
//# sourceMappingURL=upload_imagenes_dual.js.map