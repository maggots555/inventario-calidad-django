"use strict";
// ============================================================================
// SISTEMA DUAL DE SUBIDA DE IMÁGENES - GALERÍA Y CÁMARA
// Versión 3.0 - Validación límite total del servidor + mejoras UX
// ============================================================================
class UploadImagenesDual {
    constructor() {
        // NUEVO v2.0: Panel de resumen
        this.panelResumen = null;
        // NUEVO v2.0: Contenedor de toasts
        this.toastContainer = null;
        // Array de imágenes seleccionadas
        this.imagenesSeleccionadas = [];
        // Límites de validación
        this.MAX_IMAGENES = 30;
        this.MAX_SIZE_MB = 50;
        this.MAX_SIZE_BYTES = this.MAX_SIZE_MB * 1024 * 1024;
        this.ADVERTENCIA_SIZE_MB = 40; // Advertir si > 40MB
        // NUEVO: Límite total del request (alineado con Cloudflare Free: 100MB max)
        this.MAX_REQUEST_SIZE_MB = 95; // DATA_UPLOAD_MAX_MEMORY_SIZE
        this.MAX_REQUEST_SIZE_BYTES = this.MAX_REQUEST_SIZE_MB * 1024 * 1024;
        this.ADVERTENCIA_REQUEST_MB = 76; // Advertir al 80% del límite
        // Control de estado de procesamiento
        this.estaProcesando = false;
        this.archivosListos = false;
        // NUEVO v2.0: Control de envío (para evitar doble-click)
        this.enviando = false;
        this.ultimoClickSubir = 0;
        this.DEBOUNCE_MS = 1500; // 1.5 segundos entre clicks
        this.inputGaleria = document.getElementById('inputGaleria');
        this.inputCamara = document.getElementById('inputCamara');
        this.inputUnificado = document.getElementById('imagenesUnificadas');
        this.previewContainer = document.getElementById('previewImagenes');
        this.contenedorMiniaturas = document.getElementById('contenedorMiniaturas');
        this.btnSubir = document.getElementById('btnSubirImagenes');
        this.btnLimpiarTodo = document.getElementById('btnLimpiarTodo');
        this.cantidadSpan = document.getElementById('cantidadImagenes');
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
        console.log('✅ Sistema dual de subida de imágenes v2.0 inicializado');
    }
    // =========================================================================
    // NUEVO v2.0: Sistema de Toasts Bootstrap
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
     * MEJORADO: Más descriptivo y con detalles
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
    // NUEVO v2.0: Panel de Resumen Pre-Subida
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
            
            <!-- NUEVO: Barra de progreso del límite total del servidor -->
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
        // NUEVO: Actualizar barra de progreso del límite del servidor
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
                // NUEVO: Estado de error si excede el límite del servidor
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
            const advertencias = [...resumen.archivosGrandes, ...resumen.archivosAdvertencia];
            const mensajes = [];
            // NUEVO: Advertencia si excede el límite total del servidor
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
    // API PÚBLICA v2.0: Para integración con scripts externos
    // =========================================================================
    /**
     * API PÚBLICA: Consultar si el sistema está listo para subir
     * Usada por el script del template para evitar doble submit
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
     * API PÚBLICA: Marcar que se inició el envío (llamado desde el template)
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
        // NUEVO: Validar límite total del request (95MB - alineado con Cloudflare Free)
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
    // =========================================================================
    // Métodos de cámara integrada (sin cambios)
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
     * NOTA: Este método NO se modifica para mantener compatibilidad con cámara
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
     * Agrega archivos al array de imágenes seleccionadas
     * MODIFICADO v2.0: Mejor feedback con toasts
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
        // Transferir archivos al input
        await this.transferirArchivosAInputUnificado();
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
     * Actualiza el estado del botón de subir según el contexto
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
     * MEJORADO v2.0: Indicador de tamaño con color
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
     * Elimina una imagen del array de seleccionadas
     */
    async eliminarImagen(id) {
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
            this.actualizarPanelResumen();
            // Re-transferir archivos
            this.estaProcesando = true;
            this.archivosListos = false;
            this.actualizarEstadoBotonSubir();
            await this.transferirArchivosAInputUnificado();
            this.estaProcesando = false;
            this.archivosListos = this.imagenesSeleccionadas.length > 0;
            this.actualizarEstadoBotonSubir();
            this.actualizarPanelResumen();
        }
    }
    /**
     * Limpia todas las imágenes seleccionadas
     */
    limpiarTodo() {
        // Liberar memoria de todos los ObjectURLs
        this.imagenesSeleccionadas.forEach(img => {
            URL.revokeObjectURL(img.previewUrl);
        });
        // Limpiar array
        this.imagenesSeleccionadas = [];
        // Limpiar inputs
        if (this.inputGaleria)
            this.inputGaleria.value = '';
        if (this.inputCamara)
            this.inputCamara.value = '';
        if (this.inputUnificado)
            this.inputUnificado.value = '';
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
     * Transfiere archivos del array al input unificado para envío al servidor
     */
    async transferirArchivosAInputUnificado() {
        if (!this.inputUnificado) {
            return;
        }
        console.log(`📦 Transfiriendo ${this.imagenesSeleccionadas.length} archivo(s) al input unificado...`);
        // Crear un nuevo DataTransfer para manipular los archivos del input
        const dataTransfer = new DataTransfer();
        // Agregar todos los archivos seleccionados
        for (const imagen of this.imagenesSeleccionadas) {
            dataTransfer.items.add(imagen.file);
            // Yield al event loop cada 5 archivos para mantener UI responsive
            if (dataTransfer.files.length % 5 === 0) {
                await this.delay(5);
            }
        }
        // Asignar al input unificado
        this.inputUnificado.files = dataTransfer.files;
        // Pequeño delay para asegurar que el navegador termine de asignar los archivos
        await this.delay(20);
        console.log(`✅ ${dataTransfer.files.length} archivo(s) transferido(s) y listos para enviar`);
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
        console.log('✅ Sistema de subida dual v2.0 inicializado');
    }
});
//# sourceMappingURL=upload_imagenes_dual.js.map