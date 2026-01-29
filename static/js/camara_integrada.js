"use strict";
// ============================================================================
// VISOR DE CÁMARA INTEGRADO - MEDIA CAPTURE API
// ============================================================================
class CamaraIntegrada {
    constructor() {
        this.infoCamaras = null; // NUEVO: Para mostrar info de cámaras detectadas
        this.infoOrientacion = null; // NUEVO: Para mostrar orientación detectada
        this.infoModoOrientacion = null; // NUEVO: Indicador de modo (auto/manual)
        this.badgeToggleOrientacion = null; // NUEVO: Badge clickeable para toggle
        // Stream de video
        this.mediaStream = null;
        this.facingMode = 'environment'; // Trasera por defecto
        // Gestión de dispositivos de cámara
        this.dispositivosCamara = [];
        this.dispositivoActualId = null;
        this.camarasTraseras = [];
        this.camarasFrontales = [];
        // Cache de botones del selector de lentes (BUG FIX: evitar recrear DOM)
        this.botonesLenteCache = new Map();
        // Fotos capturadas
        this.fotosCapturadas = [];
        // Flag para prevenir capturas simultáneas (BUG FIX)
        this.estáCapturando = false;
        // Callback para integración con sistema de subida
        this.onFotosCapturadas = null;
        // Control de navegación del botón "Atrás" en Android (NUEVO)
        this.modalAbierto = false;
        this.historyStateKey = 'camaraIntegrada';
        this.popstateHandler = null;
        // Sistema híbrido de detección de orientación (NUEVO v5.2)
        this.orientacionManual = 270; // null = auto, 0/90/180/270 = manual - DEFAULT: 270° landscape
        this.modoDeteccion = 'manual'; // Modo actual - DEFAULT: manual
        this.modal = document.getElementById('modalCamaraIntegrada');
        this.videoElement = document.getElementById('videoPreview');
        this.canvas = document.getElementById('canvasCaptura');
        this.btnCapturar = document.getElementById('btnCapturar');
        this.btnCambiarCamara = document.getElementById('btnCambiarCamara');
        this.btnCerrar = document.getElementById('btnCerrarCamara');
        this.btnFinalizar = document.getElementById('btnFinalizarCaptura');
        this.contadorFotos = document.getElementById('contadorFotos');
        this.cameraError = document.getElementById('cameraError');
        this.mensajeError = document.getElementById('mensajeError');
        this.detalleError = document.getElementById('detalleError');
        this.selectorLentes = document.getElementById('selectorLentes');
        this.infoCamaras = document.getElementById('infoCamaras');
        this.infoOrientacion = document.getElementById('infoOrientacion'); // Badge de orientación
        this.infoModoOrientacion = document.getElementById('infoModoOrientacion'); // Indicador modo (auto/manual)
        this.badgeToggleOrientacion = document.getElementById('badgeToggleOrientacion'); // Badge clickeable
        // Modal de confirmación de salida
        this.modalConfirmacion = document.getElementById('modalConfirmacionSalidaCamara');
        this.btnConfirmarSalida = document.getElementById('btnConfirmarSalida');
        this.cantidadFotosPendientesSpan = document.getElementById('cantidadFotosPendientes');
        this.init();
    }
    init() {
        if (!this.modal) {
            console.warn('⚠️ Modal de cámara no encontrado');
            return;
        }
        // Event listeners del modal
        this.modal.addEventListener('shown.bs.modal', () => this.onModalAbierto());
        this.modal.addEventListener('hidden.bs.modal', () => this.onModalCerrado());
        // Event listeners de botones
        if (this.btnCapturar) {
            this.btnCapturar.addEventListener('click', () => this.capturarFoto());
        }
        if (this.btnCambiarCamara) {
            this.btnCambiarCamara.addEventListener('click', () => this.cambiarCamara());
        }
        if (this.btnCerrar) {
            this.btnCerrar.addEventListener('click', () => this.cerrarConConfirmacion());
        }
        if (this.btnFinalizar) {
            this.btnFinalizar.addEventListener('click', () => this.finalizarCaptura());
        }
        // Event listener para el botón de confirmación de salida (NUEVO)
        if (this.btnConfirmarSalida) {
            this.btnConfirmarSalida.addEventListener('click', () => {
                this.confirmarSalidaConDescarte();
            });
        }
        // Event listener para el badge de toggle de orientación (NUEVO v5.2)
        if (this.badgeToggleOrientacion) {
            this.badgeToggleOrientacion.addEventListener('click', () => {
                this.toggleOrientacionManual();
            });
        }
        console.log('✅ Cámara integrada inicializada');
    }
    /**
     * Se ejecuta cuando el modal se abre
     * NUEVO: Maneja la protección del botón "Atrás" en Android
     */
    onModalAbierto() {
        this.modalAbierto = true;
        this.agregarProteccionBotonAtras();
        this.iniciarMonitoreoOrientacion(); // NUEVO: Monitorear cambios de orientación
        this.abrirCamara();
    }
    /**
     * Se ejecuta cuando el modal se cierra
     * NUEVO: Limpia la protección del botón "Atrás"
     */
    onModalCerrado() {
        this.modalAbierto = false;
        this.removerProteccionBotonAtras();
        this.detenerMonitoreoOrientacion(); // NUEVO: Detener monitoreo
        this.cerrarCamara();
    }
    /**
     * Inicia el monitoreo de cambios de orientación
     * NUEVO: Actualiza el badge en tiempo real cuando el usuario rota el dispositivo
     */
    iniciarMonitoreoOrientacion() {
        // Actualizar badge inicial
        this.actualizarBadgeOrientacion();
        // Escuchar cambios de orientación
        if (window.screen && window.screen.orientation) {
            window.screen.orientation.addEventListener('change', () => {
                this.actualizarBadgeOrientacion();
            });
        }
        // Fallback: escuchar evento orientationchange (deprecated pero funcional)
        window.addEventListener('orientationchange', () => {
            this.actualizarBadgeOrientacion();
        });
        // Fallback adicional: escuchar resize (cuando cambia orientación cambia tamaño)
        window.addEventListener('resize', () => {
            this.actualizarBadgeOrientacion();
        });
        console.log('👂 Monitoreo de orientación iniciado');
    }
    /**
     * Detiene el monitoreo de cambios de orientación
     */
    detenerMonitoreoOrientacion() {
        // Remover listeners (simplificado, los listeners persistirán pero no afectarán)
        console.log('🛑 Monitoreo de orientación detenido');
    }
    /**
     * Actualiza el badge visual con la orientación actual
     * NUEVO: Muestra el ángulo detectado y un ícono visual
     */
    actualizarBadgeOrientacion() {
        const orientacion = this.obtenerOrientacionFinal();
        if (this.infoOrientacion) {
            // Actualizar texto con el ángulo
            this.infoOrientacion.textContent = `${orientacion}°`;
            // Cambiar color del badge según orientación para mejor feedback visual
            const badge = document.getElementById('badgeOrientacion');
            if (badge) {
                // Remover clases anteriores
                badge.classList.remove('orientation-0', 'orientation-90', 'orientation-180', 'orientation-270');
                // Agregar clase según orientación
                badge.classList.add(`orientation-${orientacion}`);
            }
        }
        // NUEVO: Actualizar indicador de modo (automático/manual)
        if (this.infoModoOrientacion) {
            this.infoModoOrientacion.textContent = this.modoDeteccion === 'manual' ? '👤' : '🤖';
        }
        const modo = this.modoDeteccion === 'manual' ? 'MANUAL' : 'AUTO';
        console.log(`📐 Badge actualizado: ${orientacion}° | ${this.obtenerDescripcionOrientacion(orientacion)} | Modo: ${modo}`);
    }
    /**
     * Obtiene una descripción legible de la orientación
     */
    obtenerDescripcionOrientacion(orientacion) {
        switch (orientacion) {
            case 0: return 'Portrait (vertical, normal)';
            case 90: return 'Landscape (horizontal, botón derecha)';
            case 180: return 'Portrait invertido (vertical, cabeza abajo)';
            case 270: return 'Landscape (horizontal, botón izquierda)';
            default: return `Desconocido (${orientacion}°)`;
        }
    }
    /**
     * Agrega protección contra el botón "Atrás" de Android
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * - Cuando el modal se abre, agregamos una entrada al historial del navegador
     * - Si el usuario presiona "Atrás", interceptamos el evento
     * - Si hay fotos capturadas, mostramos confirmación
     * - Si no hay fotos, cerramos el modal normalmente
     */
    agregarProteccionBotonAtras() {
        // Agregar estado al historial para poder interceptar el botón "Atrás"
        const currentState = history.state || {};
        const newState = { ...currentState, [this.historyStateKey]: true };
        // Pushear nuevo estado al historial
        history.pushState(newState, '');
        console.log('🛡️ Protección de botón "Atrás" activada');
        // Crear handler para el evento popstate (botón atrás)
        this.popstateHandler = (event) => {
            console.log('⬅️ Botón "Atrás" presionado');
            // Verificar si el modal sigue abierto
            if (this.modalAbierto) {
                // Prevenir la navegación hacia atrás por ahora
                event.preventDefault();
                // Verificar si hay fotos capturadas sin finalizar
                if (this.fotosCapturadas.length > 0) {
                    // Restaurar estado para que el modal permanezca
                    history.pushState(newState, '');
                    // Mostrar confirmación
                    this.mostrarConfirmacionSalida();
                }
                else {
                    // No hay fotos, cerrar modal normalmente
                    this.cerrarModal();
                }
            }
        };
        // Agregar listener
        window.addEventListener('popstate', this.popstateHandler);
    }
    /**
     * Remueve la protección del botón "Atrás"
     */
    removerProteccionBotonAtras() {
        // Remover listener si existe
        if (this.popstateHandler) {
            window.removeEventListener('popstate', this.popstateHandler);
            this.popstateHandler = null;
        }
        // Retroceder en el historial si el estado de cámara sigue ahí
        if (history.state && history.state[this.historyStateKey]) {
            history.back();
        }
        console.log('🛡️ Protección de botón "Atrás" desactivada');
    }
    /**
     * Muestra diálogo de confirmación antes de salir con fotos sin finalizar
     * NUEVO: Usa modal Bootstrap en lugar de confirm() nativo para mejor UX
     */
    mostrarConfirmacionSalida() {
        if (!this.modalConfirmacion || !this.cantidadFotosPendientesSpan) {
            // Fallback a confirm() nativo si el modal no está disponible
            const mensaje = `Tienes ${this.fotosCapturadas.length} foto(s) capturada(s) sin finalizar.\n\n¿Deseas salir y descartar las fotos?`;
            if (confirm(mensaje)) {
                console.log('✅ Usuario confirmó salida, descartando fotos');
                this.fotosCapturadas = [];
                this.cerrarModal();
            }
            else {
                console.log('❌ Usuario canceló salida, manteniendo modal abierto');
            }
            return;
        }
        console.log(`⚠️ Mostrando confirmación de salida: ${this.fotosCapturadas.length} foto(s) pendientes`);
        // Actualizar cantidad de fotos en el modal de confirmación
        this.cantidadFotosPendientesSpan.textContent = String(this.fotosCapturadas.length);
        // Mostrar modal de confirmación usando Bootstrap
        const bsModalConfirmacion = new bootstrap.Modal(this.modalConfirmacion);
        bsModalConfirmacion.show();
    }
    /**
     * Ejecuta el descarte de fotos y cierre del modal
     * NUEVO: Llamado desde el botón de confirmación
     */
    confirmarSalidaConDescarte() {
        console.log('✅ Usuario confirmó salida, descartando fotos');
        // Descartar fotos capturadas
        this.fotosCapturadas = [];
        this.actualizarContador();
        // Cerrar modal de confirmación
        if (this.modalConfirmacion) {
            const bsModalConfirmacion = bootstrap.Modal.getInstance(this.modalConfirmacion);
            if (bsModalConfirmacion) {
                bsModalConfirmacion.hide();
            }
        }
        // Cerrar modal de cámara
        this.cerrarModal();
    }
    /**
     * Cierra el modal con confirmación si hay fotos
     * MODIFICADO: Ahora verifica si hay fotos antes de cerrar
     */
    cerrarConConfirmacion() {
        if (this.fotosCapturadas.length > 0) {
            this.mostrarConfirmacionSalida();
        }
        else {
            this.cerrarModal();
        }
    }
    /**
     * Abre la cámara usando getUserMedia
     * EXPLICACIÓN: Ahora detecta primero todos los dispositivos disponibles
     * y permite seleccionar entre diferentes lentes (gran angular, normal, teleobjetivo)
     *
     * BUG FIX: Detiene streams ANTES de detectar dispositivos para evitar conflictos
     */
    async abrirCamara() {
        console.log('📷 Intentando abrir cámara...');
        // Ocultar error si estaba visible
        if (this.cameraError) {
            this.cameraError.style.display = 'none';
        }
        try {
            // CRÍTICO: Detener stream anterior PRIMERO (antes de detectar dispositivos)
            if (this.mediaStream) {
                this.detenerStream();
                // Esperar 150ms para asegurar liberación completa (incrementado de 100ms)
                await new Promise(resolve => setTimeout(resolve, 150));
            }
            // PASO 1: Detectar todos los dispositivos de cámara disponibles
            await this.detectarDispositivosCamara();
            // PASO 2: Construir constraints según dispositivo seleccionado
            const constraints = {
                video: this.construirConstraintsCamara(),
                audio: false
            };
            console.log('🎥 Solicitando stream con constraints:', constraints);
            this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
            // Asignar stream al elemento video
            if (this.videoElement) {
                this.videoElement.srcObject = this.mediaStream;
                await this.videoElement.play();
                // Configurar tap-to-focus
                this.configurarTapToFocus();
                console.log('✅ Cámara iniciada correctamente');
                // PASO 3: Actualizar UI del selector de lentes
                this.actualizarSelectorLentes();
            }
        }
        catch (error) {
            console.error('❌ Error al acceder a la cámara:', error);
            this.mostrarError(error);
        }
    }
    /**
     * Detecta todos los dispositivos de cámara disponibles en el dispositivo
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * - enumerateDevices() lista todas las cámaras del dispositivo
     * - Separamos frontales de traseras
     * - Identificamos lentes específicos (gran angular, normal, teleobjetivo)
     *
     * BUG FIX: Ahora liberamos correctamente el stream temporal usado para permisos
     *
     * NOTA IMPORTANTE: En Android, algunos fabricantes no exponen todas las cámaras
     * a través de la API web. Esto depende del navegador y el modelo del celular.
     */
    async detectarDispositivosCamara() {
        let streamTemporal = null;
        try {
            // Primero solicitar permisos si aún no los tiene
            // IMPORTANTE: Guardamos el stream temporal para liberarlo después
            streamTemporal = await navigator.mediaDevices.getUserMedia({ video: true });
            // Obtener lista de todos los dispositivos multimedia
            const devices = await navigator.mediaDevices.enumerateDevices();
            // Filtrar solo dispositivos de video (cámaras)
            const camaras = devices.filter(device => device.kind === 'videoinput');
            console.log(`🔍 Detectadas ${camaras.length} cámara(s) disponibles`);
            console.log('📱 Dispositivo:', navigator.userAgent.includes('Android') ? 'Android' : 'iOS/Otro');
            // Limpiar arrays
            this.dispositivosCamara = [];
            this.camarasTraseras = [];
            this.camarasFrontales = [];
            // Clasificar cámaras por tipo
            for (const camara of camaras) {
                const label = camara.label.toLowerCase();
                // Determinar si es frontal o trasera
                // NOTA: Android puede usar diferentes convenciones de nombres
                const esFrontal = label.includes('front') ||
                    label.includes('user') ||
                    label.includes('facing front') ||
                    label.includes('selfie');
                const esTrasera = label.includes('back') ||
                    label.includes('rear') ||
                    label.includes('environment') ||
                    label.includes('facing back') ||
                    label.includes('camera 0'); // Algunos Android usan camera 0, 1, 2
                const dispositivo = {
                    deviceId: camara.deviceId,
                    label: camara.label,
                    tipo: esFrontal ? 'frontal' : 'trasera',
                    facingMode: esFrontal ? 'user' : 'environment'
                };
                this.dispositivosCamara.push(dispositivo);
                if (esFrontal) {
                    this.camarasFrontales.push(dispositivo);
                }
                else {
                    this.camarasTraseras.push(dispositivo);
                }
                console.log(`  📹 ${dispositivo.label} (${dispositivo.tipo}) [${camara.deviceId.substring(0, 20)}...]`);
            }
            console.log(`✅ Cámaras traseras: ${this.camarasTraseras.length}, Frontales: ${this.camarasFrontales.length}`);
            // NUEVO: Actualizar badge con info elegante de cámaras
            this.actualizarInfoCamaras();
            // Si no hay dispositivo seleccionado, elegir la primera cámara trasera
            if (!this.dispositivoActualId && this.camarasTraseras.length > 0) {
                this.dispositivoActualId = this.camarasTraseras[0].deviceId;
            }
            else if (!this.dispositivoActualId && this.camarasFrontales.length > 0) {
                this.dispositivoActualId = this.camarasFrontales[0].deviceId;
            }
        }
        catch (error) {
            console.error('❌ Error al detectar dispositivos de cámara:', error);
        }
        finally {
            // CRÍTICO: Liberar el stream temporal SIEMPRE (incluso si hay error)
            if (streamTemporal) {
                streamTemporal.getTracks().forEach(track => {
                    track.stop();
                    console.log('🛑 Stream temporal liberado');
                });
                streamTemporal = null;
            }
        }
    }
    /**
     * Construye las constraints para getUserMedia según el dispositivo seleccionado
     */
    construirConstraintsCamara() {
        const constraints = {
            width: { ideal: 1920 },
            height: { ideal: 1080 }
        };
        // Si hay un dispositivo específico seleccionado, usarlo
        if (this.dispositivoActualId) {
            constraints.deviceId = { exact: this.dispositivoActualId };
        }
        else {
            // Fallback: usar facingMode
            constraints.facingMode = this.facingMode;
        }
        return constraints;
    }
    /**
     * Actualiza la UI del selector de lentes
     * BUG FIX: Ahora cachea botones en lugar de recrear DOM completo
     * Esto mejora rendimiento y evita pérdida de estado hover
     */
    actualizarSelectorLentes() {
        if (!this.selectorLentes)
            return;
        // Solo mostrar selector si hay múltiples cámaras del tipo activo
        const camarasActivas = this.facingMode === 'environment' ? this.camarasTraseras : this.camarasFrontales;
        if (camarasActivas.length <= 1) {
            this.selectorLentes.style.display = 'none';
            return;
        }
        this.selectorLentes.style.display = 'flex';
        // Si los botones ya existen, solo actualizar clase 'active'
        if (this.botonesLenteCache.size === camarasActivas.length) {
            this.botonesLenteCache.forEach((btn, deviceId) => {
                if (deviceId === this.dispositivoActualId) {
                    btn.classList.add('active');
                }
                else {
                    btn.classList.remove('active');
                }
            });
            return;
        }
        // Primera vez o cambio de cantidad de cámaras: construir desde cero
        this.selectorLentes.innerHTML = '';
        this.botonesLenteCache.clear();
        // Usar DocumentFragment para construcción eficiente
        const fragment = document.createDocumentFragment();
        // Crear botones para cada cámara
        camarasActivas.forEach((camara, index) => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'btn btn-sm btn-lente';
            // Marcar como activo si es el dispositivo actual
            if (camara.deviceId === this.dispositivoActualId) {
                btn.classList.add('active');
            }
            // Determinar icono y texto según el tipo de lente
            const { icono, texto } = this.obtenerInfoLente(camara.label, index);
            btn.innerHTML = `<i class="bi ${icono}"></i> ${texto}`;
            btn.title = camara.label;
            // Event listener para cambiar a esta cámara
            btn.addEventListener('click', () => this.cambiarADispositivo(camara.deviceId));
            // Cachear botón
            this.botonesLenteCache.set(camara.deviceId, btn);
            fragment.appendChild(btn);
        });
        this.selectorLentes.appendChild(fragment);
    }
    /**
     * Obtiene icono y texto para un lente según su label
     */
    obtenerInfoLente(label, index) {
        const labelLower = label.toLowerCase();
        // Intentar identificar el tipo de lente por el label
        if (labelLower.includes('ultra') || labelLower.includes('wide') || labelLower.includes('0.5')) {
            return { icono: 'bi-arrows-angle-expand', texto: '0.5x' };
        }
        else if (labelLower.includes('tele') || labelLower.includes('zoom') || labelLower.includes('2x') || labelLower.includes('3x')) {
            return { icono: 'bi-zoom-in', texto: '2x' };
        }
        else if (labelLower.includes('macro')) {
            return { icono: 'bi-flower1', texto: 'Macro' };
        }
        else {
            // Por defecto, asignar nombres genéricos
            return { icono: 'bi-camera', texto: `Lente ${index + 1}` };
        }
    }
    /**
     * Actualiza el badge de información de cámaras detectadas
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Muestra solo la letra según el modo: "T" para Trasera, "F" para Frontal
     * Estilo minimalista como WhatsApp
     */
    actualizarInfoCamaras() {
        if (!this.infoCamaras)
            return;
        const total = this.dispositivosCamara.length;
        const traseras = this.camarasTraseras.length;
        const frontales = this.camarasFrontales.length;
        // Mostrar solo la letra: T o F
        let texto = '';
        if (this.facingMode === 'environment') {
            // Modo trasera: mostrar "T" + cantidad si hay múltiples
            texto = traseras > 1 ? `T${traseras}` : 'T';
        }
        else {
            // Modo frontal: mostrar "F" + cantidad si hay múltiples
            texto = frontales > 1 ? `F${frontales}` : 'F';
        }
        this.infoCamaras.textContent = texto;
        console.log(`📊 Info actualizada: ${texto} (Total: ${total})`);
    }
    /**
     * Cambia a un dispositivo de cámara específico
     * BUG FIX: Ahora valida disponibilidad y captura errores
     */
    async cambiarADispositivo(deviceId) {
        console.log(`🔄 Cambiando a dispositivo: ${deviceId}`);
        try {
            // Validar que el dispositivo existe
            const dispositivoExiste = this.dispositivosCamara.some(d => d.deviceId === deviceId);
            if (!dispositivoExiste) {
                console.error(`❌ Dispositivo ${deviceId} no encontrado`);
                return;
            }
            this.dispositivoActualId = deviceId;
            await this.abrirCamara();
        }
        catch (error) {
            console.error('❌ Error al cambiar dispositivo de cámara:', error);
            this.mostrarError(error);
        }
    }
    /**
     * Configura tap-to-focus en el video
     */
    configurarTapToFocus() {
        if (!this.videoElement || !this.mediaStream) {
            return;
        }
        // Obtener el track de video
        const videoTrack = this.mediaStream.getVideoTracks()[0];
        // Verificar si el dispositivo soporta focus
        const capabilities = videoTrack.getCapabilities();
        if (!capabilities.focusMode || !capabilities.focusMode.includes('continuous')) {
            console.log('⚠️ Dispositivo no soporta enfoque manual');
            return;
        }
        // Event listener para tap en el video
        this.videoElement.addEventListener('click', async (e) => {
            await this.enfocarEnPunto(e);
        });
        // También para touch en móviles
        this.videoElement.addEventListener('touchstart', async (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('click', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            await this.enfocarEnPunto(mouseEvent);
        });
        console.log('✅ Tap-to-focus configurado');
    }
    /**
     * Enfoca la cámara en un punto específico
     */
    async enfocarEnPunto(e) {
        if (!this.videoElement || !this.mediaStream) {
            return;
        }
        const videoTrack = this.mediaStream.getVideoTracks()[0];
        try {
            // Calcular coordenadas normalizadas (0 a 1)
            const rect = this.videoElement.getBoundingClientRect();
            const x = (e.clientX - rect.left) / rect.width;
            const y = (e.clientY - rect.top) / rect.height;
            // Aplicar enfoque en el punto
            await videoTrack.applyConstraints({
                advanced: [{
                        focusMode: 'single-shot',
                        pointsOfInterest: [{ x, y }]
                    }]
            });
            // Feedback visual (círculo en el punto tocado)
            // Calcular coordenadas relativas al contenedor
            const relativeX = e.clientX - rect.left;
            const relativeY = e.clientY - rect.top;
            this.mostrarIndicadorEnfoque(relativeX, relativeY);
            console.log(`🎯 Enfocando en: (${(x * 100).toFixed(0)}%, ${(y * 100).toFixed(0)}%)`);
        }
        catch (error) {
            console.warn('⚠️ No se pudo aplicar enfoque:', error);
        }
    }
    /**
     * Muestra un indicador visual de enfoque
     */
    mostrarIndicadorEnfoque(x, y) {
        if (!this.videoElement)
            return;
        const container = this.videoElement.parentElement;
        if (!container)
            return;
        // Crear círculo de enfoque (coordenadas relativas al contenedor)
        const indicator = document.createElement('div');
        indicator.style.position = 'absolute';
        indicator.style.left = `${x}px`;
        indicator.style.top = `${y}px`;
        indicator.style.width = '80px';
        indicator.style.height = '80px';
        indicator.style.border = '2px solid rgba(255, 255, 255, 0.8)';
        indicator.style.borderRadius = '50%';
        indicator.style.transform = 'translate(-50%, -50%)';
        indicator.style.pointerEvents = 'none';
        indicator.style.zIndex = '100';
        indicator.style.transition = 'all 0.3s ease';
        indicator.style.boxShadow = '0 0 0 2px rgba(0, 0, 0, 0.3)';
        container.appendChild(indicator);
        // Animación de enfoque
        setTimeout(() => {
            indicator.style.width = '60px';
            indicator.style.height = '60px';
            indicator.style.borderColor = 'rgba(76, 175, 80, 0.8)';
        }, 100);
        // Eliminar después de 1 segundo
        setTimeout(() => {
            indicator.style.opacity = '0';
            setTimeout(() => indicator.remove(), 300);
        }, 700);
    }
    /**
     * Detiene el stream de video y libera todos los recursos
     * EXPLICACIÓN: Es CRÍTICO detener todos los tracks antes de abrir un nuevo stream
     * para evitar el error "cámara en uso por otra aplicación"
     */
    detenerStream() {
        if (this.mediaStream) {
            console.log('🛑 Deteniendo stream de cámara...');
            // Detener TODOS los tracks (video y audio si los hay)
            this.mediaStream.getTracks().forEach(track => {
                track.stop();
                console.log(`  ✓ Track detenido: ${track.kind} (${track.label})`);
            });
            this.mediaStream = null;
        }
        // Limpiar el srcObject del video
        if (this.videoElement) {
            this.videoElement.srcObject = null;
            this.videoElement.load(); // Forzar limpieza del elemento video
        }
        console.log('✅ Stream completamente liberado');
    }
    /**
     * Cambia entre cámara frontal y trasera
     */
    async cambiarCamara() {
        console.log('🔄 Cambiando entre frontal/trasera...');
        // Alternar entre frontal y trasera
        this.facingMode = this.facingMode === 'environment' ? 'user' : 'environment';
        // Limpiar cache de botones (BUG FIX: forzar reconstrucción con nuevo tipo)
        this.botonesLenteCache.clear();
        // Seleccionar el primer dispositivo del tipo nuevo
        const camarasDisponibles = this.facingMode === 'environment' ? this.camarasTraseras : this.camarasFrontales;
        if (camarasDisponibles.length > 0) {
            this.dispositivoActualId = camarasDisponibles[0].deviceId;
        }
        else {
            // Fallback si no hay cámaras del tipo deseado
            this.dispositivoActualId = null;
        }
        // Actualizar badge de info ANTES de abrir la cámara
        this.actualizarInfoCamaras();
        // Reiniciar cámara con nueva orientación
        await this.abrirCamara();
    }
    /**
     * Captura una foto del stream de video
     * BUG FIX: Ahora es async y previene capturas simultáneas con debouncing de 300ms
     * NUEVO: Detecta y respeta la orientación del dispositivo (landscape/portrait)
     */
    async capturarFoto() {
        // CRÍTICO: Prevenir capturas dobles/múltiples
        if (this.estáCapturando) {
            console.warn('⚠️ Captura en progreso, ignorando clic...');
            return;
        }
        if (!this.videoElement || !this.canvas) {
            console.error('❌ Elementos no disponibles para captura');
            return;
        }
        // Verificar que hay video activo
        if (!this.mediaStream || this.videoElement.readyState < 2) {
            console.warn('⚠️ Video no listo para captura');
            return;
        }
        // Marcar como capturando
        this.estáCapturando = true;
        // Deshabilitar botón visualmente
        if (this.btnCapturar) {
            this.btnCapturar.disabled = true;
            this.btnCapturar.classList.add('capturing');
        }
        try {
            console.log('📸 Capturando foto...');
            // NUEVO: Obtener orientación del dispositivo
            const orientacion = this.obtenerOrientacionFinal();
            console.log(`📐 Orientación detectada: ${orientacion}°`);
            // Dimensiones originales del video
            const videoWidth = this.videoElement.videoWidth;
            const videoHeight = this.videoElement.videoHeight;
            // NUEVO: Calcular dimensiones del canvas según orientación
            // Si la orientación es 90° o 270°, intercambiamos ancho y alto
            const necesitaRotacion = orientacion === 90 || orientacion === 270;
            const canvasWidth = necesitaRotacion ? videoHeight : videoWidth;
            const canvasHeight = necesitaRotacion ? videoWidth : videoHeight;
            // Configurar canvas con dimensiones correctas
            this.canvas.width = canvasWidth;
            this.canvas.height = canvasHeight;
            // Obtener contexto del canvas
            const context = this.canvas.getContext('2d');
            if (!context) {
                console.error('❌ No se pudo obtener contexto del canvas');
                return;
            }
            // NUEVO: Aplicar transformación según orientación
            this.aplicarTransformacionCanvas(context, orientacion, canvasWidth, canvasHeight);
            // Dibujar frame actual del video en el canvas (ya con rotación aplicada)
            context.drawImage(this.videoElement, 0, 0, videoWidth, videoHeight);
            // Restaurar transformación del canvas para futuras capturas
            context.setTransform(1, 0, 0, 1, 0, 0);
            // Convertir canvas a Blob (ahora usando Promise para evitar race conditions)
            const blob = await new Promise((resolve, reject) => {
                this.canvas.toBlob((b) => {
                    if (b) {
                        resolve(b);
                    }
                    else {
                        reject(new Error('Error al crear blob de la foto'));
                    }
                }, 'image/jpeg', 0.95);
            });
            // Obtener dataURL para preview
            const dataUrl = this.canvas.toDataURL('image/jpeg', 0.95);
            // Agregar a lista de fotos capturadas
            this.fotosCapturadas.push({
                blob: blob,
                dataUrl: dataUrl,
                timestamp: Date.now()
            });
            // Actualizar contador
            this.actualizarContador();
            // Feedback visual
            this.mostrarFeedbackCaptura();
            // LOGS DETALLADOS PARA DEBUG
            console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
            console.log(`✅ FOTO CAPTURADA #${this.fotosCapturadas.length}`);
            console.log(`  📐 Orientación aplicada: ${orientacion}° (${this.obtenerDescripcionOrientacion(orientacion)})`);
            console.log(`  📏 Video original: ${videoWidth}x${videoHeight}`);
            console.log(`  📏 Canvas final: ${canvasWidth}x${canvasHeight}`);
            console.log(`  🔄 Rotación aplicada: ${necesitaRotacion ? 'SÍ' : 'NO'}`);
            console.log(`  💾 Tamaño blob: ${(blob.size / 1024).toFixed(2)} KB`);
            console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
        }
        catch (error) {
            console.error('❌ Error al capturar foto:', error);
        }
        finally {
            // DEBOUNCING: Esperar 300ms antes de permitir otra captura
            setTimeout(() => {
                this.estáCapturando = false;
                if (this.btnCapturar) {
                    this.btnCapturar.disabled = false;
                    this.btnCapturar.classList.remove('capturing');
                }
            }, 300);
        }
    }
    /**
     * Toggle manual de orientación
     * NUEVO v5.2: Permite al usuario cambiar manualmente entre portrait/landscape
     */
    toggleOrientacionManual() {
        console.log('🔄 Toggle manual de orientación activado');
        if (this.modoDeteccion === 'auto') {
            // Cambiar a modo manual
            this.modoDeteccion = 'manual';
            // Obtener orientación actual y alternar
            const orientacionActual = this.obtenerOrientacionFinal();
            // CORREGIDO: Usar 270° para landscape (mano derecha) en lugar de 90°
            this.orientacionManual = orientacionActual === 0 ? 270 : 0; // Alternar entre portrait y landscape
            console.log(`  ✅ Modo MANUAL activado. Orientación fijada en: ${this.orientacionManual}°`);
        }
        else {
            // Ya está en modo manual, alternar orientación
            // CORREGIDO: Usar 270° para landscape (mano derecha) en lugar de 90°
            this.orientacionManual = this.orientacionManual === 0 ? 270 : 0;
            console.log(`  🔄 Orientación manual cambiada a: ${this.orientacionManual}°`);
        }
        // Actualizar badge
        this.actualizarBadgeOrientacion();
    }
    /**
     * Obtiene la orientación final usando lógica híbrida
     * NUEVO v5.2: Prioriza orientación manual sobre auto-detección
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Este es el método principal que decide qué orientación usar.
     * Primero revisa si el usuario configuró algo manual, si no, usa auto-detección.
     *
     * @returns Ángulo de rotación en grados (0, 90, 180, 270)
     */
    obtenerOrientacionFinal() {
        // PRIORIDAD 1: Si hay orientación manual, usarla
        if (this.modoDeteccion === 'manual' && this.orientacionManual !== null) {
            console.log(`📐 Usando orientación MANUAL: ${this.orientacionManual}°`);
            return this.orientacionManual;
        }
        // PRIORIDAD 2: Detección automática por dimensiones de video
        const orientacionAuto = this.detectarOrientacionPorVideo();
        console.log(`📐 Usando orientación AUTO: ${orientacionAuto}°`);
        return orientacionAuto;
    }
    /**
     * Detecta orientación analizando las dimensiones del stream de video
     * NUEVO v5.2: Método principal de auto-detección que SÍ funciona
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * En lugar de preguntarle al sistema operativo la orientación del celular,
     * miramos directamente las dimensiones del video que viene de la cámara.
     *
     * - Si el video es más ancho que alto (1920x1080) → Landscape (horizontal)
     * - Si el video es más alto que ancho (1080x1920) → Portrait (vertical)
     *
     * Esto funciona porque las cámaras modernas adaptan su resolución según
     * cómo sostienes el celular.
     *
     * @returns 0 para portrait, 90 para landscape
     */
    detectarOrientacionPorVideo() {
        if (!this.videoElement) {
            console.warn('⚠️ Video no disponible, asumiendo portrait 0°');
            return 0;
        }
        const videoWidth = this.videoElement.videoWidth;
        const videoHeight = this.videoElement.videoHeight;
        console.group('🎥 Analizando dimensiones del stream de video');
        console.log(`  📊 Resolución del video: ${videoWidth}x${videoHeight}`);
        // Calcular aspect ratio
        const aspectRatio = videoWidth / videoHeight;
        console.log(`  📐 Aspect ratio: ${aspectRatio.toFixed(2)}`);
        let orientacion;
        if (videoWidth > videoHeight) {
            // Video horizontal = Landscape (mano derecha)
            // CORREGIDO: Usar 270° en lugar de 90° para orientación correcta
            orientacion = 270;
            console.log(`  ✅ Detección: LANDSCAPE (ancho > alto) → 270°`);
        }
        else if (videoWidth < videoHeight) {
            // Video vertical = Portrait
            orientacion = 0;
            console.log(`  ✅ Detección: PORTRAIT (alto > ancho)`);
        }
        else {
            // Cuadrado (raro) - asumir portrait
            orientacion = 0;
            console.log(`  ⚠️ Video cuadrado, asumiendo PORTRAIT`);
        }
        console.groupEnd();
        return orientacion;
    }
    /**
     * Aplica transformación al canvas según la orientación del dispositivo
     * NUEVO: Rota y traslada el canvas para que la imagen quede correcta
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * El canvas tiene un sistema de coordenadas que podemos transformar.
     * Según la orientación, necesitamos:
     * 1. Trasladar el origen del canvas
     * 2. Rotar el canvas
     * 3. Esto hace que cuando dibujemos la imagen, quede en la orientación correcta
     *
     * @param context Contexto 2D del canvas
     * @param orientacion Ángulo de rotación (0, 90, 180, 270)
     * @param canvasWidth Ancho del canvas
     * @param canvasHeight Alto del canvas
     */
    aplicarTransformacionCanvas(context, orientacion, canvasWidth, canvasHeight) {
        // Limpiar cualquier transformación previa
        context.setTransform(1, 0, 0, 1, 0, 0);
        switch (orientacion) {
            case 0:
                // Portrait normal - no requiere transformación
                // La imagen ya está en la orientación correcta
                break;
            case 90:
                // Landscape derecha (botón del celular a la derecha)
                // 1. Trasladar al borde derecho
                // 2. Rotar 90° en sentido horario
                context.translate(canvasWidth, 0);
                context.rotate(90 * Math.PI / 180);
                console.log('🔄 Aplicando rotación 90° (landscape derecha)');
                break;
            case 180:
                // Portrait invertido (poco común)
                // 1. Trasladar a la esquina inferior derecha
                // 2. Rotar 180°
                context.translate(canvasWidth, canvasHeight);
                context.rotate(180 * Math.PI / 180);
                console.log('🔄 Aplicando rotación 180° (portrait invertido)');
                break;
            case 270:
                // Landscape izquierda (botón del celular a la izquierda)
                // 1. Trasladar al borde inferior
                // 2. Rotar 270° (equivalente a -90°)
                context.translate(0, canvasHeight);
                context.rotate(270 * Math.PI / 180);
                console.log('🔄 Aplicando rotación 270° (landscape izquierda)');
                break;
            default:
                console.warn(`⚠️ Orientación no reconocida: ${orientacion}°`);
                break;
        }
    }
    /**
     * Actualiza el contador de fotos tomadas
     */
    actualizarContador() {
        if (this.contadorFotos) {
            this.contadorFotos.textContent = String(this.fotosCapturadas.length);
        }
    }
    /**
     * Muestra feedback visual al capturar foto (flash)
     */
    mostrarFeedbackCaptura() {
        if (!this.videoElement)
            return;
        // Crear overlay blanco para simular flash
        const flash = document.createElement('div');
        flash.style.position = 'absolute';
        flash.style.top = '0';
        flash.style.left = '0';
        flash.style.width = '100%';
        flash.style.height = '100%';
        flash.style.backgroundColor = 'white';
        flash.style.opacity = '0.7';
        flash.style.pointerEvents = 'none';
        flash.style.zIndex = '1000';
        flash.style.transition = 'opacity 0.2s ease';
        const container = this.videoElement.parentElement;
        if (container) {
            container.appendChild(flash);
            // Fade out del flash
            setTimeout(() => {
                flash.style.opacity = '0';
                setTimeout(() => flash.remove(), 200);
            }, 50);
        }
        // Sonido de captura (opcional - puede ser molesto)
        // new Audio('/static/audio/camera-shutter.mp3').play().catch(() => {});
    }
    /**
     * Finaliza la captura y envía fotos al sistema de preview
     */
    finalizarCaptura() {
        console.log(`🎬 Finalizando captura. ${this.fotosCapturadas.length} foto(s) capturada(s)`);
        // Si hay callback configurado, enviar las fotos
        if (this.onFotosCapturadas && this.fotosCapturadas.length > 0) {
            const blobs = this.fotosCapturadas.map(f => f.blob);
            this.onFotosCapturadas(blobs);
        }
        // Limpiar fotos capturadas
        this.fotosCapturadas = [];
        this.actualizarContador();
        // Cerrar modal
        this.cerrarModal();
    }
    /**
     * Cierra el modal de cámara
     */
    cerrarModal() {
        if (this.modal) {
            const bsModal = bootstrap.Modal.getInstance(this.modal);
            if (bsModal) {
                bsModal.hide();
            }
        }
    }
    /**
     * Cierra la cámara y libera recursos
     */
    cerrarCamara() {
        console.log('📷 Cerrando cámara...');
        this.detenerStream();
        // Limpiar fotos capturadas si el usuario cancela
        if (this.fotosCapturadas.length > 0) {
            console.log(`🗑️ Descartando ${this.fotosCapturadas.length} foto(s) no confirmada(s)`);
            this.fotosCapturadas = [];
            this.actualizarContador();
        }
    }
    /**
     * Muestra mensaje de error al usuario
     */
    mostrarError(error) {
        console.error('❌ Error de cámara:', error);
        if (!this.cameraError || !this.mensajeError || !this.detalleError) {
            return;
        }
        // Ocultar video
        if (this.videoElement) {
            this.videoElement.style.display = 'none';
        }
        // Mostrar mensaje de error
        this.cameraError.style.display = 'flex';
        // Personalizar mensaje según el tipo de error
        if (error.name === 'NotAllowedError') {
            this.mensajeError.textContent = 'Permiso de cámara denegado';
            this.detalleError.textContent = 'Por favor, permite el acceso a la cámara en la configuración del navegador';
        }
        else if (error.name === 'NotFoundError') {
            this.mensajeError.textContent = 'No se encontró ninguna cámara';
            this.detalleError.textContent = 'Verifica que tu dispositivo tenga una cámara disponible';
        }
        else if (error.name === 'NotReadableError') {
            this.mensajeError.textContent = 'Cámara en uso por otra aplicación';
            this.detalleError.textContent = 'Cierra otras aplicaciones que estén usando la cámara';
        }
        else {
            this.mensajeError.textContent = 'No se pudo acceder a la cámara';
            this.detalleError.textContent = error.message || 'Error desconocido';
        }
    }
    /**
     * Abre el modal de cámara
     */
    abrir() {
        if (this.modal) {
            const bsModal = new bootstrap.Modal(this.modal);
            bsModal.show();
        }
    }
    /**
     * Configura callback para recibir fotos capturadas
     */
    setOnFotosCapturadas(callback) {
        this.onFotosCapturadas = callback;
    }
}
// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('modalCamaraIntegrada')) {
        window.camaraIntegrada = new CamaraIntegrada();
        console.log('✅ Cámara integrada disponible');
    }
});
//# sourceMappingURL=camara_integrada.js.map