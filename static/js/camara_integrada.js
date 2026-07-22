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
        // ── SISTEMA ADAPTATIVO DE CALIDAD (v8.1) + WORKER JPEG (v9.0) ────────────
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // Comprimir a JPEG es lo más pesado. Antes ocurría en el hilo principal
        // con canvas.toBlob() y congelaba botones/preview en celulares lentos.
        //
        // Ahora preferimos un Web Worker + OffscreenCanvas (segundo plano).
        // Si el navegador no lo soporta, caemos al toBlob() de siempre.
        //
        // Además medimos el tiempo de la PRIMERA captura. Si tarda más de 2.5 s,
        // bajamos calidad JPEG (0.95 → 0.75) sin tocar la resolución Full HD.
        this.dispositivoLento = false; // true cuando se detecta hardware lento
        this.primeraCaptura = true; // false tras la primera medición
        // ── Web Worker JPEG (v9.0) ───────────────────────────────────────────────
        // jpegWorker: hilo aparte que comprime; null si no hay soporte o tras cerrar.
        // encodePendientes: Promises de encodes en curso (Finalizar espera a todas).
        // aceptaResultadosEncode: false al descartar/cerrar → ignora Blobs tardíos.
        // colaEncodeWorker: encadena encodes en serie dentro del mismo Worker.
        this.jpegWorker = null;
        this.soportaEncodeWorker = false;
        this.siguienteEncodeId = 1;
        this.encodePendientes = new Map();
        this.aceptaResultadosEncode = true;
        this.colaEncodeWorker = Promise.resolve();
        this.workerMessageHandler = null;
        this.workerErrorHandler = null;
        /** Resolvers pendientes esperando la respuesta del Worker por id */
        this.encodeResolvers = new Map();
        // OPTIMIZACIÓN v6.0: Control de event listeners para prevenir memory leaks
        this.abortController = null;
        // OPTIMIZACIÓN v6.0: Sistema de enfoque robusto
        // NOTA: enfoqueOriginalMode se declara como variable local en enfocarEnPunto(),
        // no como propiedad de clase, para evitar condiciones de carrera entre llamadas.
        this.ultimoEnfoque = 0; // Timestamp para debounce
        this.enfocandoActualmente = false; // Flag de estado
        // Callback para integración con sistema de subida
        this.onFotosCapturadas = null;
        // Control de navegación del botón "Atrás" en Android (NUEVO)
        this.modalAbierto = false;
        this.historyStateKey = 'camaraIntegrada';
        this.popstateHandler = null;
        // FIX iOS Safari: Handler para prevenir el bounce scroll elástico dentro del modal
        // Se guarda la referencia para poder removerlo al cerrar el modal
        this.preventTouchMoveHandler = null;
        // Sistema híbrido de detección de orientación (NUEVO v5.2 / actualizado v7.0)
        this.orientacionManual = null; // null = auto, 0/90/180/270 = manual forzado
        this.modoDeteccion = 'auto'; // Modo actual - DEFAULT: auto (giroscopio)
        // SISTEMA GIROSCOPIO / SENSOR DE ORIENTACIÓN (NUEVO v7.0)
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // En lugar de adivinar la orientación por las dimensiones del video (poco confiable),
        // ahora leemos directamente los sensores del dispositivo:
        // - screenOrientationAngle: el ángulo que reporta la pantalla (0/90/180/270)
        // - deviceGamma / deviceBeta: valores del giroscopio físico del celular
        //   · gamma: inclinación izquierda/derecha (-90° a 90°)
        //   · beta: inclinación adelante/atrás (-180° a 180°)
        // Cuando el usuario bloquea la rotación automática, la pantalla no rota pero
        // el giroscopio sigue reportando la inclinación real — así seguimos sabiendo
        // cómo está sosteniendo el celular aunque la pantalla esté "fija".
        this.screenOrientationAngle = 0;
        this.deviceGamma = null;
        this.deviceBeta = null;
        this.deviceOrientationHandler = null;
        this.screenOrientationChangeHandler = null;
        this.permisosOrientacionSolicitados = false;
        // Último ángulo mostrado en el badge (-1 = nunca mostrado → fuerza actualización inicial)
        this.lastOrientacionBadge = -1;
        this.modal = document.getElementById('modalCamaraIntegrada');
        this.videoElement = document.getElementById('videoPreview');
        this.canvas = document.getElementById('canvasCaptura');
        this.btnCapturar = document.getElementById('btnCapturar');
        this.btnCambiarCamara = document.getElementById('btnCambiarCamara');
        this.btnCerrar = document.getElementById('btnCerrarCamara');
        this.btnFinalizar = document.getElementById('btnFinalizarCaptura');
        this.contadorFotos = document.getElementById('contadorFotos');
        this.badgeFotosTomadas = document.getElementById('badgeFotosTomadas'); // NUEVO v6.0: Badge para feedback verde
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
     * FIX iOS Safari: Bloquea el scroll del body para evitar el bounce scroll elástico
     */
    onModalAbierto() {
        this.modalAbierto = true;
        this.aceptaResultadosEncode = true;
        this.agregarProteccionBotonAtras();
        this.iniciarMonitoreoOrientacion(); // v7.0: async, se ejecuta en paralelo (sin await)
        // v8.1: Resetear flag de primera captura al abrir una nueva sesión.
        // Si el dispositivo ya fue marcado como lento, lo mantenemos (no remedir cada vez).
        // Solo reseteamos primeraCaptura para que si el usuario cierra y vuelve a abrir
        // sin que hayamos llegado a medir, se pueda medir correctamente.
        this.primeraCaptura = true;
        this.bloquearScrollBody(); // FIX iOS: Prevenir bounce scroll
        this.asegurarJpegWorker(); // v9.0: lazy-init Worker JPEG (o fallback)
        this.abrirCamara();
    }
    /**
     * Se ejecuta cuando el modal se cierra
     * NUEVO: Limpia la protección del botón "Atrás"
     * OPTIMIZACIÓN v6.0: Limpia event listeners para prevenir memory leaks
     * FIX iOS Safari: Restaura el scroll del body al cerrar
     */
    onModalCerrado() {
        this.modalAbierto = false;
        // v9.0: al cerrar (X / atrás / dismiss) descartamos encodes en curso
        this.aceptaResultadosEncode = false;
        this.terminarJpegWorker();
        this.removerProteccionBotonAtras();
        this.detenerMonitoreoOrientacion();
        this.restaurarScrollBody(); // FIX iOS: Restaurar scroll normal
        // OPTIMIZACIÓN v6.0: Cancelar todos los listeners de tap-to-focus
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
            console.log('🧹 Event listeners limpiados (AbortController)');
        }
        this.cerrarCamara();
    }
    /**
     * Bloquea el scroll del body cuando el modal de cámara está abierto.
     *
     * FIX iOS Safari: Este es el fix más crítico para el bug del modal "movible".
     *
     * PROBLEMA: iOS Safari tiene un "bounce scroll" elástico que permite desplazar
     * cualquier contenido aunque CSS diga overflow:hidden. Esto causa que:
     *   1. El usuario arrastra el modal y lo desplaza visualmente
     *   2. El layout (y las áreas de toque) permanecen en su posición original
     *   3. El botón se VE desplazado pero el área de toque sigue arriba
     *   4. El botón "no funciona" excepto en la orilla donde empieza el área de toque real
     *
     * SOLUCIÓN: Interceptar el evento touchmove en el documento y llamar
     * preventDefault(). Esto cancela el gesto de scroll ANTES de que iOS lo procese.
     * Los botones siguen recibiendo eventos touchstart/touchend normalmente.
     *
     * IMPORTANTE: Solo se cancela touchmove en el modal, no en los botones.
     * touch-action:manipulation en CSS ya maneja los botones por separado.
     */
    bloquearScrollBody() {
        const body = document.body;
        const html = document.documentElement;
        // Guardar posición actual del scroll para restaurarla al cerrar
        const scrollY = window.scrollY;
        // Bloquear scroll del body con CSS
        body.style.overflow = 'hidden';
        body.style.position = 'fixed';
        body.style.top = `-${scrollY}px`;
        body.style.left = '0';
        body.style.right = '0';
        body.style.width = '100%';
        html.style.overflow = 'hidden';
        // Guardar el scrollY para restaurarlo al cerrar
        body.dataset.scrollY = String(scrollY);
        // FIX iOS Safari específico: preventDefault en touchmove del documento
        // Esto es lo que realmente bloquea el bounce scroll de iOS
        // NOTA: debe ser { passive: false } para poder llamar preventDefault()
        this.preventTouchMoveHandler = (event) => {
            var _a, _b;
            // Solo bloquear si el toque viene del modal de cámara (no de otros elementos)
            const target = event.target;
            const esDentroDelModal = (_b = (_a = this.modal) === null || _a === void 0 ? void 0 : _a.contains(target)) !== null && _b !== void 0 ? _b : false;
            if (esDentroDelModal) {
                // Permitir el toque en los botones de control (no bloquear clicks)
                // pero sí bloquear el gesto de arrastre/scroll
                const esBoton = target.closest('button, .btn') !== null;
                if (!esBoton) {
                    event.preventDefault();
                }
                // Los botones tienen touch-action:manipulation en CSS, así que
                // los gestos en ellos ya están manejados correctamente
            }
        };
        document.addEventListener('touchmove', this.preventTouchMoveHandler, { passive: false });
        console.log('🔒 Scroll del body bloqueado (FIX iOS Safari)');
    }
    /**
     * Restaura el scroll del body al cerrar el modal.
     * Revierte exactamente los cambios de bloquearScrollBody().
     */
    restaurarScrollBody() {
        const body = document.body;
        const html = document.documentElement;
        // Recuperar posición de scroll guardada
        const scrollY = parseInt(body.dataset.scrollY || '0', 10);
        // Restaurar estilos del body
        body.style.overflow = '';
        body.style.position = '';
        body.style.top = '';
        body.style.left = '';
        body.style.right = '';
        body.style.width = '';
        html.style.overflow = '';
        delete body.dataset.scrollY;
        // Restaurar posición de scroll sin animación
        window.scrollTo({ top: scrollY, behavior: 'instant' });
        // Remover listener de touchmove
        if (this.preventTouchMoveHandler) {
            document.removeEventListener('touchmove', this.preventTouchMoveHandler);
            this.preventTouchMoveHandler = null;
        }
        console.log('🔓 Scroll del body restaurado (FIX iOS Safari)');
    }
    /**
     * Inicia el monitoreo de orientación usando sensores del dispositivo.
     *
     * v7.0 — Sistema de giroscopio:
     *
     * CAPA 1 — Screen Orientation API:
     *   Lee screen.orientation.angle (0/90/180/270) directamente.
     *   Funciona cuando la rotación automática está activada.
     *
     * CAPA 2 — DeviceOrientationEvent (giroscopio físico):
     *   Lee gamma/beta del giroscopio, que reportan la inclinación REAL
     *   del dispositivo aunque la rotación automática esté bloqueada.
     *
     * iOS 13+: requiere permiso explícito del usuario para DeviceOrientationEvent.
     *   Se solicita automáticamente al abrir el modal.
     *
     * Android: no requiere permiso, los eventos llegan directamente.
     */
    async iniciarMonitoreoOrientacion() {
        var _a;
        // ── CAPA 1: Screen Orientation API ──────────────────────────────────
        if ((_a = window.screen) === null || _a === void 0 ? void 0 : _a.orientation) {
            // Leer ángulo inicial
            this.screenOrientationAngle = window.screen.orientation.angle;
            // Suscribirse a cambios
            this.screenOrientationChangeHandler = () => {
                this.screenOrientationAngle = window.screen.orientation.angle;
                this.actualizarBadgeOrientacion();
                console.log(`📐 screen.orientation cambió: ${this.screenOrientationAngle}°`);
            };
            window.screen.orientation.addEventListener('change', this.screenOrientationChangeHandler);
        }
        else if (typeof window.orientation !== 'undefined') {
            // Fallback legacy para iOS < 16.4 y algunos Android
            this.screenOrientationAngle = Math.abs(Number(window.orientation));
        }
        // ── CAPA 2: DeviceOrientationEvent (giroscopio físico) ───────────────
        // EXPLICACIÓN PARA PRINCIPIANTES:
        // DeviceOrientationEvent.gamma = inclinación izquierda/derecha del celular
        // - gamma cerca de 0 → celular vertical (portrait)
        // - gamma cerca de 90 → celular inclinado a la derecha (landscape)
        // - gamma cerca de -90 → celular inclinado a la izquierda (landscape inverso)
        this.deviceOrientationHandler = (e) => {
            this.deviceGamma = e.gamma;
            this.deviceBeta = e.beta;
            // Actualizar badge solo cuando la orientación inferida cambia (0/90/180/270).
            // El giroscopio dispara ~60 veces/segundo — comparar antes de re-renderizar
            // garantiza máximo 4 actualizaciones posibles al rotar el celular.
            const nuevaOrientacion = this.inferirOrientacionDeGiroscopio();
            if (nuevaOrientacion !== this.lastOrientacionBadge) {
                this.lastOrientacionBadge = nuevaOrientacion;
                this.actualizarBadgeOrientacion();
            }
        };
        try {
            // iOS 13+: DeviceOrientationEvent requiere permiso explícito
            if (typeof DeviceOrientationEvent.requestPermission === 'function') {
                if (!this.permisosOrientacionSolicitados) {
                    this.permisosOrientacionSolicitados = true;
                    console.log('📱 iOS detectado — solicitando permiso de giroscopio...');
                    const permiso = await DeviceOrientationEvent.requestPermission();
                    if (permiso === 'granted') {
                        window.addEventListener('deviceorientation', this.deviceOrientationHandler);
                        console.log('✅ Permiso de giroscopio concedido (iOS)');
                    }
                    else {
                        // Sin permiso: solo usamos screen.orientation (funciona si rotación automática está ON)
                        console.warn('⚠️ Permiso de giroscopio denegado — usando solo screen.orientation');
                    }
                }
                else {
                    // Permiso ya solicitado en sesión anterior — intentar suscribirse directamente
                    window.addEventListener('deviceorientation', this.deviceOrientationHandler);
                }
            }
            else {
                // Android y escritorio: sin permiso necesario
                window.addEventListener('deviceorientation', this.deviceOrientationHandler);
                console.log('✅ Giroscopio suscrito (Android/desktop — sin permiso necesario)');
            }
        }
        catch (err) {
            // El permiso falló o la API no está disponible → seguimos con screen.orientation
            console.warn('⚠️ No se pudo suscribir al giroscopio:', err);
        }
        // Actualizar badge con estado inicial
        this.actualizarBadgeOrientacion();
        console.log(`👂 Monitoreo de orientación iniciado | screen.orientation: ${this.screenOrientationAngle}° | giroscopio: ${this.deviceGamma !== null ? 'activo' : 'no disponible'}`);
    }
    /**
     * Detiene el monitoreo de orientación y limpia todos los listeners.
     * v7.0: implementación real de limpieza (antes era solo un console.log)
     */
    detenerMonitoreoOrientacion() {
        var _a;
        // Remover listener de screen.orientation
        if (this.screenOrientationChangeHandler && ((_a = window.screen) === null || _a === void 0 ? void 0 : _a.orientation)) {
            window.screen.orientation.removeEventListener('change', this.screenOrientationChangeHandler);
            this.screenOrientationChangeHandler = null;
        }
        // Remover listener del giroscopio
        if (this.deviceOrientationHandler) {
            window.removeEventListener('deviceorientation', this.deviceOrientationHandler);
            this.deviceOrientationHandler = null;
        }
        // Resetear sentinel para que la próxima apertura fuerce actualización del badge
        this.deviceGamma = null;
        this.deviceBeta = null;
        this.lastOrientacionBadge = -1;
        console.log('🛑 Monitoreo de orientación detenido — listeners removidos');
    }
    /**
     * Actualiza el badge visual con la orientación actual
     * NUEVO: Muestra el ángulo detectado y un ícono visual
     */
    actualizarBadgeOrientacion() {
        var _a;
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
        // ── Contra-rotación de iconos ────────────────────────────────────────
        // Aplica cam-orient-X al modal-body para que el CSS contra-rote todos
        // los iconos de badges y botones, manteniéndolos legibles igual que
        // una app nativa de cámara (el badge de orientación queda excluido).
        const modalBody = (_a = this.modal) === null || _a === void 0 ? void 0 : _a.querySelector('.modal-body');
        if (modalBody) {
            modalBody.classList.remove('cam-orient-0', 'cam-orient-90', 'cam-orient-180', 'cam-orient-270');
            modalBody.classList.add(`cam-orient-${orientacion}`);
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
                // OPTIMIZACIÓN v6.0: Esperar 200ms para asegurar liberación completa en Android
                // Incrementado de 150ms para mayor compatibilidad con dispositivos lentos
                await new Promise(resolve => setTimeout(resolve, 200));
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
     * Construye las constraints para getUserMedia según el dispositivo seleccionado.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Pedimos Full HD (1920×1080) como ideal. Antes pedíamos ~4K (4096×2160) y las
     * fotos salían nítidas, pero el preview en vivo se sentía con lag en celulares
     * de gama media: el stream del <video> usa esa misma resolución todo el tiempo.
     *
     * Full HD es un buen balance para documentación técnica (rayones, etiquetas)
     * y mantiene el preview fluido. No usamos "min" estricto: si el hardware no
     * llega a 1080p, el navegador entrega lo máximo que pueda sin fallar.
     *
     * En dispositivos lentos solo bajamos la calidad JPEG (0.95 → 0.75), no los
     * píxeles del stream (ver capturarFoto / modo optimizado).
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
     * Configura tap-to-focus en el video.
     * OPTIMIZACIÓN v6.0: Usa AbortController para limpieza automática de listeners.
     *
     * MEJORA: La validación de capabilities se hace aquí una sola vez mediante
     * verificarSoporteFocus(), con el criterio correcto (single-shot).
     * Antes se verificaba 'continuous' aquí y 'single-shot' en enfocarEnPunto —
     * dos chequeos distintos que podían dar resultados contradictorios.
     *
     * MEJORA: Los listeners de touch ya no crean un MouseEvent sintético.
     * enfocarEnPunto() acepta directamente {clientX, clientY} como objeto plano,
     * que tanto MouseEvent como TouchEvent exponen de forma nativa.
     */
    configurarTapToFocus() {
        if (!this.videoElement || !this.mediaStream) {
            return;
        }
        const videoTrack = this.mediaStream.getVideoTracks()[0];
        // Validación única y consistente: ¿soporta single-shot?
        if (!this.verificarSoporteFocus(videoTrack)) {
            console.log('⚠️ Dispositivo no soporta tap-to-focus (single-shot no disponible)');
            return;
        }
        // OPTIMIZACIÓN v6.0: Crear AbortController para cancelar listeners automáticamente
        this.abortController = new AbortController();
        const signal = this.abortController.signal;
        // Click en escritorio
        this.videoElement.addEventListener('click', (e) => {
            this.enfocarEnPunto({ clientX: e.clientX, clientY: e.clientY });
        }, { signal });
        // Touch en móviles — sin MouseEvent sintético, pasamos las coordenadas directamente
        this.videoElement.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            this.enfocarEnPunto({ clientX: touch.clientX, clientY: touch.clientY });
        }, { signal, passive: false });
        console.log('✅ Tap-to-focus configurado (con AbortController)');
    }
    /**
     * Verifica si un video track soporta tap-to-focus con modo 'single-shot'.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * 'single-shot' = el sensor hace UN enfoque y se detiene (modo foto).
     * 'continuous'  = el sensor enfoca constantemente (modo video, más batería).
     * Para tap-to-focus necesitamos 'single-shot': el usuario toca, enfocamos
     * en ese punto, y luego volvemos a 'continuous' para el preview.
     *
     * Esta función centraliza el criterio para evitar duplicación entre
     * configurarTapToFocus() y enfocarEnPunto().
     *
     * @param videoTrack Track de video a verificar
     * @returns true si el track soporta single-shot focus
     */
    verificarSoporteFocus(videoTrack) {
        // getCapabilities() puede no existir en algunos navegadores/dispositivos
        if (typeof videoTrack.getCapabilities !== 'function') {
            return false;
        }
        const capabilities = videoTrack.getCapabilities();
        if (!capabilities || !Array.isArray(capabilities.focusMode)) {
            return false;
        }
        return capabilities.focusMode.includes('single-shot');
    }
    /**
     * Enfoca la cámara en un punto específico.
     *
     * MEJORAS respecto a la versión anterior:
     *
     * 1. FIRMA: acepta {clientX, clientY} en lugar de MouseEvent.
     *    Elimina la necesidad de crear MouseEvent sintéticos desde touchstart.
     *
     * 2. ESTADO LOCAL: enfoqueOriginalMode es ahora variable local, no propiedad
     *    de instancia. Evita condiciones de carrera si el AbortController cancela
     *    el listener antes de que llegue el finally.
     *
     * 3. CONSTANTE NOMBRADA: FOCUS_RESTORE_DELAY_MS documenta el "magic number" 800.
     *
     * 4. FEEDBACK OCUPADO: cuando enfocandoActualmente === true, muestra un
     *    indicador visual amarillo en el punto tocado en vez de silenciar el tap.
     *
     * 5. VALIDACIÓN ELIMINADA: getCapabilities() se llama una sola vez en
     *    verificarSoporteFocus(), que es invocada desde configurarTapToFocus()
     *    antes de registrar cualquier listener. No tiene sentido repetirla aquí.
     *
     * @param punto Coordenadas del toque/click (clientX, clientY del viewport)
     */
    async enfocarEnPunto(punto) {
        // PASO 1: DEBOUNCE — ignorar si han pasado menos de 500ms desde el último toque
        const ahora = Date.now();
        if (ahora - this.ultimoEnfoque < 500) {
            console.log('⚠️ Debounce: Ignorando toque (muy rápido)');
            return;
        }
        // PASO 2: Si ya hay un enfoque en progreso, mostrar feedback visual y salir
        if (this.enfocandoActualmente) {
            console.log('⚠️ Enfoque en progreso, ignorando toque');
            this.mostrarIndicadorEnfoqueBloqueado(punto);
            return;
        }
        if (!this.videoElement || !this.mediaStream) {
            return;
        }
        // Actualizar timestamp y bloquear nuevas peticiones
        this.ultimoEnfoque = ahora;
        this.enfocandoActualmente = true;
        const videoTrack = this.mediaStream.getVideoTracks()[0];
        // Tiempo de espera antes de restaurar el modo continuous.
        // 800ms es el mínimo seguro para que el AF del sensor termine en
        // dispositivos de gama media (Snapdragon 6xx/7xx). En gama alta
        // termina antes y el modo continuous vuelve sin impacto visible.
        const FOCUS_RESTORE_DELAY_MS = 800;
        // Modo original como variable LOCAL — no como estado de instancia.
        // Valor por defecto defensivo: 'continuous' es el modo estándar de preview.
        let enfoqueOriginalMode = 'continuous';
        try {
            // Calcular coordenadas normalizadas (0 a 1) relativas al video
            const rect = this.videoElement.getBoundingClientRect();
            const x = (punto.clientX - rect.left) / rect.width;
            const y = (punto.clientY - rect.top) / rect.height;
            // Validar coordenadas (deben estar en rango 0-1)
            if (x < 0 || x > 1 || y < 0 || y > 1) {
                console.warn('⚠️ Coordenadas fuera de rango:', { x, y });
                return;
            }
            // Guardar el modo actual antes de cambiarlo
            const settings = videoTrack.getSettings();
            enfoqueOriginalMode = settings.focusMode || 'continuous';
            console.log(`📐 Modo de enfoque original: ${enfoqueOriginalMode}`);
            // PASO 3: Aplicar enfoque con TIMEOUT de 2 segundos
            const enfoquePromise = videoTrack.applyConstraints({
                advanced: [{
                        focusMode: 'single-shot',
                        pointsOfInterest: [{ x, y }]
                    }]
            });
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => reject(new Error('Timeout de enfoque (2s)')), 2000);
            });
            // Race: lo que termine primero (enfoque exitoso o timeout)
            await Promise.race([enfoquePromise, timeoutPromise]);
            console.log(`🎯 Enfoque aplicado en: (${(x * 100).toFixed(0)}%, ${(y * 100).toFixed(0)}%)`);
            // Mostrar indicador visual (coordenadas relativas al contenedor del video)
            const relativeX = punto.clientX - rect.left;
            const relativeY = punto.clientY - rect.top;
            this.mostrarIndicadorEnfoque(relativeX, relativeY);
            // PASO 4: Esperar y RESTAURAR modo original
            await new Promise(resolve => setTimeout(resolve, FOCUS_RESTORE_DELAY_MS));
            await videoTrack.applyConstraints({
                advanced: [{ focusMode: enfoqueOriginalMode }]
            });
            console.log(`✅ Modo de enfoque restaurado a: ${enfoqueOriginalMode}`);
        }
        catch (error) {
            if (error instanceof Error && error.message.includes('Timeout')) {
                console.warn('⏱️ Timeout de enfoque alcanzado, restaurando modo original');
            }
            else {
                console.warn('⚠️ Error al aplicar enfoque:', error);
            }
            // CRÍTICO: Restaurar modo original incluso en error
            try {
                await videoTrack.applyConstraints({
                    advanced: [{ focusMode: enfoqueOriginalMode }]
                });
                console.log(`✅ Modo restaurado después de error: ${enfoqueOriginalMode}`);
            }
            catch (restoreError) {
                console.error('❌ No se pudo restaurar modo de enfoque:', restoreError);
            }
        }
        finally {
            // SIEMPRE liberar el flag de enfoque
            this.enfocandoActualmente = false;
        }
    }
    /**
     * Muestra un indicador visual de enfoque en el punto tocado.
     *
     * MEJORA: Usa clases CSS (.focus-indicator, .focus-indicator--focusing,
     * .focus-indicator--done) en lugar de estilos inline, siguiendo las
     * reglas del proyecto (AGENTS.md §2: NEVER put CSS in elements).
     *
     * @param x Coordenada X relativa al contenedor del video (px)
     * @param y Coordenada Y relativa al contenedor del video (px)
     */
    mostrarIndicadorEnfoque(x, y) {
        if (!this.videoElement)
            return;
        const container = this.videoElement.parentElement;
        if (!container)
            return;
        const indicator = document.createElement('div');
        indicator.className = 'focus-indicator';
        indicator.style.left = `${x}px`;
        indicator.style.top = `${y}px`;
        container.appendChild(indicator);
        // Activar la animación de "enfocado" en el siguiente frame de render
        // (requestAnimationFrame garantiza que el browser ya pintó el estado inicial)
        requestAnimationFrame(() => {
            indicator.classList.add('focus-indicator--focusing');
        });
        // Fade out y eliminar
        setTimeout(() => {
            indicator.classList.add('focus-indicator--done');
            setTimeout(() => indicator.remove(), 300);
        }, 700);
    }
    /**
     * Muestra un indicador visual de "ocupado" cuando ya hay un enfoque en progreso.
     *
     * En lugar de silenciar el tap sin feedback, mostramos un indicador amarillo
     * pulsante que le dice al usuario "ya estoy enfocando, espera un momento".
     *
     * @param punto Coordenadas del toque ignorado (clientX, clientY del viewport)
     */
    mostrarIndicadorEnfoqueBloqueado(punto) {
        if (!this.videoElement)
            return;
        const container = this.videoElement.parentElement;
        if (!container)
            return;
        const rect = this.videoElement.getBoundingClientRect();
        const x = punto.clientX - rect.left;
        const y = punto.clientY - rect.top;
        const indicator = document.createElement('div');
        indicator.className = 'focus-indicator focus-indicator--busy';
        indicator.style.left = `${x}px`;
        indicator.style.top = `${y}px`;
        container.appendChild(indicator);
        // La animación CSS maneja el fade-out; solo necesitamos eliminar el elemento
        setTimeout(() => indicator.remove(), 600);
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
    // =========================================================================
    // Web Worker JPEG (v9.0) — compresión en segundo plano
    // =========================================================================
    /**
     * Inicializa el Worker de JPEG si el navegador lo soporta.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Leemos la URL desde data-worker-url del modal (Django {% static %}).
     * Si falta OffscreenCanvas, Worker o la URL, usamos toBlob en el hilo principal.
     */
    asegurarJpegWorker() {
        var _a, _b, _c;
        if (this.jpegWorker) {
            return;
        }
        const workerUrl = (_c = (_b = (_a = this.modal) === null || _a === void 0 ? void 0 : _a.dataset.workerUrl) === null || _b === void 0 ? void 0 : _b.trim()) !== null && _c !== void 0 ? _c : '';
        const puedeWorker = typeof Worker !== 'undefined' &&
            typeof OffscreenCanvas !== 'undefined' &&
            typeof createImageBitmap === 'function' &&
            workerUrl.length > 0;
        if (!puedeWorker) {
            this.soportaEncodeWorker = false;
            console.warn('⚠️ Encode JPEG en Worker no disponible — usando toBlob (hilo principal)');
            return;
        }
        try {
            this.jpegWorker = new Worker(workerUrl);
            this.soportaEncodeWorker = true;
            this.workerMessageHandler = (event) => {
                this.onJpegWorkerMessage(event.data);
            };
            this.workerErrorHandler = (event) => {
                console.error('❌ Error en jpeg_encode_worker:', event.message);
                // Rechazar todas las peticiones abiertas y desactivar Worker
                this.encodeResolvers.forEach(({ reject }) => {
                    reject(new Error(event.message || 'Error en Worker JPEG'));
                });
                this.encodeResolvers.clear();
                this.soportaEncodeWorker = false;
                this.terminarJpegWorker();
            };
            this.jpegWorker.addEventListener('message', this.workerMessageHandler);
            this.jpegWorker.addEventListener('error', this.workerErrorHandler);
            console.log('✅ Worker JPEG listo:', workerUrl);
        }
        catch (err) {
            console.warn('⚠️ No se pudo crear Worker JPEG — fallback toBlob:', err);
            this.soportaEncodeWorker = false;
            this.jpegWorker = null;
        }
    }
    /**
     * Resuelve o rechaza la Promise asociada a un id de encode.
     */
    onJpegWorkerMessage(data) {
        const pendiente = this.encodeResolvers.get(data.id);
        if (!pendiente) {
            return;
        }
        this.encodeResolvers.delete(data.id);
        if (data.ok) {
            pendiente.resolve(data.blob);
        }
        else {
            pendiente.reject(new Error(data.error || 'Error desconocido en Worker JPEG'));
        }
    }
    /**
     * Termina el Worker y limpia resolvers/cola (al cerrar el modal).
     * Los Blobs a medias NO se envían al upload gracias a aceptaResultadosEncode=false.
     */
    terminarJpegWorker() {
        this.encodeResolvers.forEach(({ reject }) => {
            reject(new Error('Worker JPEG terminado (modal cerrado)'));
        });
        this.encodeResolvers.clear();
        this.encodePendientes.clear();
        this.colaEncodeWorker = Promise.resolve();
        if (this.jpegWorker) {
            if (this.workerMessageHandler) {
                this.jpegWorker.removeEventListener('message', this.workerMessageHandler);
            }
            if (this.workerErrorHandler) {
                this.jpegWorker.removeEventListener('error', this.workerErrorHandler);
            }
            this.jpegWorker.terminate();
            this.jpegWorker = null;
            console.log('🛑 Worker JPEG terminado');
        }
        this.workerMessageHandler = null;
        this.workerErrorHandler = null;
    }
    /**
     * Comprime el canvas a JPEG: Worker si hay soporte, si no toBlob.
     *
     * @param canvas Canvas con el frame ya rotado (solo para fallback toBlob)
     * @param bitmap Instantánea del frame (obligatoria para Worker; se transfiere)
     * @param quality Calidad JPEG 0–1
     * @returns Blob JPEG
     */
    async comprimirCanvasAJpeg(canvas, bitmap, quality) {
        if (this.soportaEncodeWorker && this.jpegWorker && bitmap) {
            try {
                return await this.comprimirConWorker(bitmap, quality);
            }
            catch (err) {
                console.warn('⚠️ Worker JPEG falló — fallback toBlob:', err);
                this.soportaEncodeWorker = false;
                // El bitmap ya pudo haberse transferido; para fallback usamos el canvas
            }
        }
        else if (bitmap) {
            // Worker no disponible: cerrar bitmap para no filtrar memoria
            bitmap.close();
        }
        return this.comprimirConToBlob(canvas, quality);
    }
    /**
     * Envía un ImageBitmap al Worker (cola en serie) y espera el Blob.
     * El bitmap se transfiere: deja de ser usable en el hilo principal.
     */
    comprimirConWorker(bitmap, quality) {
        const worker = this.jpegWorker;
        if (!worker) {
            bitmap.close();
            return Promise.reject(new Error('Worker JPEG no inicializado'));
        }
        // Encadenar en serie: un encode tras otro en el mismo Worker
        const trabajo = this.colaEncodeWorker.then(() => {
            const id = this.siguienteEncodeId++;
            const blobPromise = new Promise((resolve, reject) => {
                this.encodeResolvers.set(id, { resolve, reject });
            });
            try {
                const mensaje = { id, bitmap, quality };
                // Transferimos el bitmap: el hilo principal ya no lo puede usar
                worker.postMessage(mensaje, [bitmap]);
            }
            catch (err) {
                this.encodeResolvers.delete(id);
                try {
                    bitmap.close();
                }
                catch {
                    // Ya transferido o inválido
                }
                throw err;
            }
            return blobPromise;
        });
        // Mantener la cola viva aunque un encode falle (para no bloquear los siguientes)
        this.colaEncodeWorker = trabajo.then(() => undefined, () => undefined);
        return trabajo;
    }
    /**
     * Fallback clásico: comprime en el hilo principal (puede congelar la UI).
     */
    comprimirConToBlob(canvas, quality) {
        return new Promise((resolve, reject) => {
            canvas.toBlob((b) => {
                if (b) {
                    resolve(b);
                }
                else {
                    reject(new Error('Error al crear blob de la foto'));
                }
            }, 'image/jpeg', quality);
        });
    }
    /**
     * Tras la primera encode, decide si activar modo optimizado (calidad 0.75).
     */
    aplicarDeteccionDispositivoLento(tiempoBlobMs) {
        if (!this.primeraCaptura) {
            return;
        }
        this.primeraCaptura = false;
        const UMBRAL_LENTO_MS = 2500;
        if (!this.dispositivoLento && tiempoBlobMs > UMBRAL_LENTO_MS) {
            this.dispositivoLento = true;
            console.warn(`⚡ Dispositivo lento detectado: encode JPEG tardó ${tiempoBlobMs}ms. ` +
                `Activando modo optimizado (calidad JPEG 0.75, resolución Full HD sin cambios).`);
            this.mostrarToastModoOptimizado(tiempoBlobMs);
        }
        else if (!this.dispositivoLento) {
            console.log(`✅ Dispositivo rápido: encode JPEG tardó ${tiempoBlobMs}ms — calidad máxima activa.`);
        }
    }
    /**
     * Espera a que terminen todos los encodes pendientes (para Finalizar).
     */
    async esperarEncodesPendientes() {
        const pendientes = Array.from(this.encodePendientes.values());
        if (pendientes.length === 0) {
            return;
        }
        console.log(`⏳ Esperando ${pendientes.length} encode(s) JPEG pendiente(s)...`);
        // ES2019: sin Promise.allSettled — envolvemos cada una para no fallar el lote
        await Promise.all(pendientes.map((p) => p.then(() => undefined, () => undefined)));
    }
    /**
     * Captura una foto del stream de video.
     * v9.0: el frame se copia al canvas en el hilo principal; el JPEG pesado
     * se comprime en un Worker (si hay soporte). El obturador se libera pronto
     * para no trabar la UI mientras comprime.
     */
    async capturarFoto() {
        // CRÍTICO: Prevenir capturas dobles/múltiples del frame (no del encode)
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
        // Marcar como capturando (solo mientras copiamos el frame)
        this.estáCapturando = true;
        if (this.btnCapturar) {
            this.btnCapturar.disabled = true;
            this.btnCapturar.classList.add('capturing', 'processing');
            const iconoOriginal = this.btnCapturar.innerHTML;
            this.btnCapturar.innerHTML = '<i class="bi bi-hourglass-split"></i>';
            this.btnCapturar.dataset.iconoOriginal = iconoOriginal;
        }
        // Metadatos para el log (se rellenan en el try)
        let orientacion = 0;
        let videoWidth = 0;
        let videoHeight = 0;
        let canvasWidth = 0;
        let canvasHeight = 0;
        let necesitaRotacion = false;
        let calidadJpeg = this.dispositivoLento ? 0.75 : 0.95;
        let canvasClon = null;
        let bitmapCaptura = null;
        try {
            console.log('📸 Capturando foto...');
            orientacion = this.obtenerOrientacionFinal();
            console.log(`📐 Orientación detectada: ${orientacion}°`);
            videoWidth = this.videoElement.videoWidth;
            videoHeight = this.videoElement.videoHeight;
            necesitaRotacion = orientacion === 90 || orientacion === 270;
            const targetW = necesitaRotacion ? videoHeight : videoWidth;
            const targetH = necesitaRotacion ? videoWidth : videoHeight;
            const canvasActual = this.canvas;
            if (!canvasActual) {
                console.error('❌ Canvas no disponible');
                return;
            }
            if (canvasActual.width !== targetW || canvasActual.height !== targetH) {
                canvasActual.width = targetW;
                canvasActual.height = targetH;
                console.log(`📐 Canvas redimensionado a ${targetW}×${targetH}`);
            }
            canvasWidth = canvasActual.width;
            canvasHeight = canvasActual.height;
            const context = canvasActual.getContext('2d');
            if (!context) {
                console.error('❌ No se pudo obtener contexto del canvas');
                return;
            }
            context.clearRect(0, 0, canvasWidth, canvasHeight);
            this.aplicarTransformacionCanvas(context, orientacion, canvasWidth, canvasHeight);
            context.drawImage(this.videoElement, 0, 0, videoWidth, videoHeight);
            context.setTransform(1, 0, 0, 1, 0, 0);
            calidadJpeg = this.dispositivoLento ? 0.75 : 0.95;
            // Copia síncrona del frame: la siguiente captura puede reutilizar
            // #canvasCaptura sin pisar este encode (Worker o toBlob).
            canvasClon = document.createElement('canvas');
            canvasClon.width = canvasWidth;
            canvasClon.height = canvasHeight;
            const ctxClon = canvasClon.getContext('2d');
            if (!ctxClon) {
                console.error('❌ No se pudo clonar el canvas de captura');
                return;
            }
            ctxClon.drawImage(canvasActual, 0, 0);
            // Instantánea transferible para el Worker (rápido vs JPEG)
            if (this.soportaEncodeWorker && typeof createImageBitmap === 'function') {
                bitmapCaptura = await createImageBitmap(canvasClon);
            }
            // Flash inmediato: el usuario siente que la foto “ya salió”
            this.mostrarFeedbackCaptura();
        }
        catch (error) {
            console.error('❌ Error al capturar frame:', error);
            if (bitmapCaptura) {
                bitmapCaptura.close();
                bitmapCaptura = null;
            }
            return;
        }
        finally {
            // Liberar obturador pronto (~200 ms). El JPEG puede seguir comprimiendo.
            setTimeout(() => {
                this.estáCapturando = false;
                if (this.btnCapturar) {
                    this.btnCapturar.disabled = false;
                    this.btnCapturar.classList.remove('capturing', 'processing');
                    const iconoOriginal = this.btnCapturar.dataset.iconoOriginal || '<i class="bi bi-circle"></i>';
                    this.btnCapturar.innerHTML = iconoOriginal;
                }
            }, 200);
        }
        if (!canvasClon) {
            return;
        }
        // ── Encode en segundo plano (Worker o toBlob sobre el clon) ───────────
        const pendienteId = Date.now() + Math.floor(Math.random() * 1000);
        const canvasParaEncode = canvasClon;
        const bitmapParaEncode = bitmapCaptura;
        const calidadParaEncode = calidadJpeg;
        const promesaEncode = (async () => {
            const t0 = Date.now();
            try {
                const blob = await this.comprimirCanvasAJpeg(canvasParaEncode, bitmapParaEncode, calidadParaEncode);
                const tiempoBlob = Date.now() - t0;
                // Si el usuario cerró el modal, descartamos el resultado
                if (!this.aceptaResultadosEncode) {
                    console.log(`🗑️ Encode pendiente #${pendienteId} descartado (modal cerrado)`);
                    return;
                }
                this.aplicarDeteccionDispositivoLento(tiempoBlob);
                this.fotosCapturadas.push({
                    blob: blob,
                    timestamp: Date.now()
                });
                this.actualizarContador();
                console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
                console.log(`✅ FOTO LISTA #${this.fotosCapturadas.length}`);
                console.log(`  📐 Orientación: ${orientacion}° (${this.obtenerDescripcionOrientacion(orientacion)})`);
                console.log(`  📏 Video: ${videoWidth}x${videoHeight} | Canvas: ${canvasWidth}x${canvasHeight}`);
                console.log(`  🔄 Rotación: ${necesitaRotacion ? 'SÍ' : 'NO'}`);
                console.log(`  💾 Blob: ${(blob.size / 1024).toFixed(2)} KB`);
                console.log(`  ⏱️ Encode: ${tiempoBlob}ms | Calidad: ${calidadParaEncode} | ` +
                    `Vía: ${this.soportaEncodeWorker ? 'Worker' : 'toBlob'} | ` +
                    `Modo: ${this.dispositivoLento ? 'OPTIMIZADO' : 'MÁXIMA'}`);
                console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
            }
            catch (error) {
                if (!this.aceptaResultadosEncode) {
                    return;
                }
                console.error('❌ Error al comprimir foto:', error);
            }
        })();
        this.encodePendientes.set(pendienteId, promesaEncode);
        void promesaEncode.finally(() => {
            this.encodePendientes.delete(pendienteId);
        });
    }
    /**
     * Toggle manual de orientación.
     *
     * v7.0: Cicla por todos los estados en orden:
     *   auto → 0° (portrait) → 90° (landscape derecha) → 180° (portrait invertido)
     *           → 270° (landscape izquierda) → auto → ...
     *
     * Útil cuando el giroscopio no está disponible o el usuario quiere forzar
     * una orientación específica independientemente de cómo sostiene el celular.
     */
    toggleOrientacionManual() {
        console.log('🔄 Toggle manual de orientación activado');
        if (this.modoDeteccion === 'auto') {
            // auto → primera orientación manual (portrait 0°)
            this.modoDeteccion = 'manual';
            this.orientacionManual = 0;
            console.log('  ✅ Modo MANUAL activado → 0° (portrait)');
        }
        else {
            // Ciclar entre orientaciones manuales → volver a auto al final
            switch (this.orientacionManual) {
                case 0:
                    this.orientacionManual = 90;
                    console.log('  🔄 Manual → 90° (landscape derecha)');
                    break;
                case 90:
                    this.orientacionManual = 180;
                    console.log('  🔄 Manual → 180° (portrait invertido)');
                    break;
                case 180:
                    this.orientacionManual = 270;
                    console.log('  🔄 Manual → 270° (landscape izquierda)');
                    break;
                case 270:
                default:
                    // Regresa a auto
                    this.modoDeteccion = 'auto';
                    this.orientacionManual = null;
                    console.log('  🤖 Modo AUTO activado (sensores)');
                    break;
            }
        }
        // Actualizar badge
        this.actualizarBadgeOrientacion();
    }
    /**
     * Obtiene la orientación final usando lógica híbrida.
     *
     * v7.0: En modo auto usa detectarOrientacionPorSensor() (giroscopio + screen.orientation).
     * El modo manual sigue existiendo como override cuando el usuario lo activa.
     *
     * @returns Ángulo de rotación en grados (0, 90, 180, 270)
     */
    obtenerOrientacionFinal() {
        // PRIORIDAD 1: Si el usuario fijó manualmente una orientación, respetarla
        if (this.modoDeteccion === 'manual' && this.orientacionManual !== null) {
            console.log(`📐 Usando orientación MANUAL forzada: ${this.orientacionManual}°`);
            return this.orientacionManual;
        }
        // PRIORIDAD 2: Detección automática por sensores (giroscopio + screen.orientation)
        const orientacionAuto = this.detectarOrientacionPorSensor();
        console.log(`📐 Usando orientación AUTO (sensores): ${orientacionAuto}°`);
        return orientacionAuto;
    }
    /**
     * Detecta orientación usando los sensores del dispositivo.
     *
     * v7.0 — reemplaza detectarOrientacionPorVideo() como método principal.
     *
     * Prioridad de fuentes:
     *  1. Screen Orientation API (screen.orientation.type) — más limpia y directa
     *  2. Giroscopio (DeviceOrientationEvent.gamma/beta) — fallback cuando rotation lock activo
     *  3. window.orientation legacy — fallback para iOS < 16.4
     *  4. Dimensiones de video — último recurso (comportamiento anterior)
     *
     * @returns Ángulo de rotación (0, 90, 180, 270) que necesita el canvas para compensar
     */
    detectarOrientacionPorSensor() {
        var _a;
        // ── FUENTE 1: Screen Orientation API ──
        if ((_a = window.screen) === null || _a === void 0 ? void 0 : _a.orientation) {
            const tipo = window.screen.orientation.type;
            // Mapeo screen.orientation.type → ángulo de canvas:
            // portrait-primary   = 0°  → sin rotación
            // landscape-primary  = 90° → landscape (botón derecha)
            // portrait-secondary = 180° → portrait invertido
            // landscape-secondary = 270° → landscape (botón izquierda)
            let orientacionScreen;
            switch (tipo) {
                case 'portrait-primary':
                    orientacionScreen = 0;
                    break;
                case 'landscape-primary':
                    orientacionScreen = 90;
                    break;
                case 'portrait-secondary':
                    orientacionScreen = 180;
                    break;
                case 'landscape-secondary':
                    orientacionScreen = 270;
                    break;
                default: orientacionScreen = 0;
            }
            // ── FUENTE 2 (corrección): Giroscopio cuando rotation lock está activo ──
            // Si el giroscopio dice algo diferente a lo que reporta la pantalla,
            // es señal de que el usuario activó el bloqueo de rotación y el celular
            // físicamente está en otra posición. En ese caso, confiamos en el giroscopio.
            if (this.deviceGamma !== null && this.deviceBeta !== null) {
                const orientacionFisica = this.inferirOrientacionDeGiroscopio();
                // "Discrepancia significativa": diferencia > 80° en el rango circular
                const diff = Math.abs(orientacionFisica - orientacionScreen);
                const discrepancia = Math.min(diff, 360 - diff);
                if (discrepancia > 80) {
                    console.log(`🔒 Rotation lock detectado — screen: ${orientacionScreen}° / giroscopio: ${orientacionFisica}° → usando giroscopio`);
                    return orientacionFisica;
                }
            }
            console.log(`📐 Orientación por screen.orientation.type (${tipo}): ${orientacionScreen}°`);
            return orientacionScreen;
        }
        // ── FUENTE 3: window.orientation legacy (iOS < 16.4) ──
        if (typeof window.orientation !== 'undefined') {
            // Convención de window.orientation (diferente a screen.orientation.angle):
            // 0 = portrait, 90 = landscape izquierda, -90 = landscape derecha, 180 = portrait invertido
            const angLegacy = Number(window.orientation);
            let orientacionLegacy;
            switch (angLegacy) {
                case 0:
                    orientacionLegacy = 0;
                    break;
                case 90:
                    orientacionLegacy = 270;
                    break; // window.90 = landscape izquierda = nuestro 270
                case -90:
                    orientacionLegacy = 90;
                    break; // window.-90 = landscape derecha = nuestro 90
                case 180:
                    orientacionLegacy = 180;
                    break;
                default: orientacionLegacy = 0;
            }
            console.log(`📐 Orientación por window.orientation (${angLegacy}°): ${orientacionLegacy}°`);
            return orientacionLegacy;
        }
        // ── FUENTE 4: Solo giroscopio (sin screen.orientation) ──
        if (this.deviceGamma !== null) {
            const orientacionGiro = this.inferirOrientacionDeGiroscopio();
            console.log(`📐 Orientación por giroscopio puro: ${orientacionGiro}°`);
            return orientacionGiro;
        }
        // ── FUENTE 5: Fallback final — dimensiones del stream de video ──
        console.warn('⚠️ Sensores no disponibles — fallback a dimensiones de video');
        return this.detectarOrientacionPorVideo();
    }
    /**
     * Infiere la orientación del dispositivo a partir de los valores del giroscopio.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * El giroscopio reporta cómo está inclinado el celular en los 3 ejes del espacio.
     * Nosotros usamos:
     * - gamma: inclinación izquierda/derecha
     *   · cerca de 0  → celular vertical (portrait)
     *   · cerca de +90 → inclinado hacia la derecha (landscape derecha)
     *   · cerca de -90 → inclinado hacia la izquierda (landscape izquierda)
     * - beta: inclinación adelante/atrás
     *   · cerca de +90 → inclinado hacia adelante (portrait normal)
     *   · cerca de -90 → inclinado hacia atrás (portrait invertido)
     *
     * @returns 0, 90, 180 o 270
     */
    inferirOrientacionDeGiroscopio() {
        var _a, _b;
        const gamma = (_a = this.deviceGamma) !== null && _a !== void 0 ? _a : 0;
        const beta = (_b = this.deviceBeta) !== null && _b !== void 0 ? _b : 90;
        if (gamma > 45)
            return 90; // Celular inclinado derecha → landscape botón derecha
        if (gamma < -45)
            return 270; // Celular inclinado izquierda → landscape botón izquierda
        if (beta < -45)
            return 180; // Celular boca abajo → portrait invertido
        return 0; // Celular vertical → portrait normal
    }
    /**
     * Detecta orientación analizando las dimensiones del stream de video.
     * Método de ÚLTIMO RECURSO usado solo cuando no hay sensores disponibles.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * En lugar de preguntarle al sistema operativo la orientación del celular,
     * miramos directamente las dimensiones del video que viene de la cámara.
     *
     * - Si el video es más ancho que alto (1920x1080) → Landscape (horizontal)
     * - Si el video es más alto que ancho (1080x1920) → Portrait (vertical)
     *
     * @returns 0 para portrait, 270 para landscape
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
     * NUEVO v6.0: Activa feedback verde cuando hay fotos capturadas
     */
    actualizarContador() {
        if (this.contadorFotos) {
            this.contadorFotos.textContent = String(this.fotosCapturadas.length);
        }
        // NUEVO v6.0: Activar feedback verde cuando hay fotos
        if (this.badgeFotosTomadas) {
            if (this.fotosCapturadas.length > 0) {
                // Activar estado verde
                this.badgeFotosTomadas.classList.add('badge-active');
            }
            else {
                // Volver a estado normal (gris)
                this.badgeFotosTomadas.classList.remove('badge-active');
            }
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
     * Finaliza la captura y envía fotos al sistema de preview.
     * v9.0: espera encodes JPEG pendientes antes de entregar los Blobs.
     */
    async finalizarCaptura() {
        console.log(`🎬 Finalizando captura. Pendientes: ${this.encodePendientes.size}`);
        if (this.btnFinalizar) {
            this.btnFinalizar.disabled = true;
        }
        try {
            await this.esperarEncodesPendientes();
            console.log(`🎬 Entregando ${this.fotosCapturadas.length} foto(s) al upload`);
            if (this.onFotosCapturadas && this.fotosCapturadas.length > 0) {
                const blobs = this.fotosCapturadas.map(f => f.blob);
                this.onFotosCapturadas(blobs);
            }
            this.fotosCapturadas = [];
            this.actualizarContador();
            this.cerrarModal();
        }
        finally {
            if (this.btnFinalizar) {
                this.btnFinalizar.disabled = false;
            }
        }
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
        // (encodes en curso ya fueron marcados con aceptaResultadosEncode=false)
        if (this.fotosCapturadas.length > 0) {
            console.log(`🗑️ Descartando ${this.fotosCapturadas.length} foto(s) no confirmada(s)`);
            this.fotosCapturadas = [];
            this.actualizarContador();
        }
    }
    /**
     * Muestra un toast informando al usuario que se activó el modo optimizado.
     *
     * EXPLICACIÓN PARA PRINCIPIANTES:
     * Cuando el sistema detecta que el dispositivo es lento, le decimos al usuario
     * en lenguaje simple qué pasó y qué cambia. El toast dura 6 segundos para
     * que haya tiempo de leerlo antes de tomar la siguiente foto.
     *
     * @param tiempoMs Tiempo que tardó el primer toBlob() en ms (para mostrar en debug)
     */
    mostrarToastModoOptimizado(tiempoMs) {
        // Crear contenedor de toast si no existe (reutiliza el mismo que upload_imagenes_dual)
        let container = document.getElementById('toastContainerImagenes');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainerImagenes';
            container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = '9999'; // Por encima del modal de cámara
            document.body.appendChild(container);
        }
        const toastId = `toast_modo_opt_${Date.now()}`;
        const toastHtml = `
            <div id="${toastId}" class="toast border-start border-4 border-info" role="alert" aria-live="assertive" aria-atomic="true">
                <div class="toast-header">
                    <i class="bi bi-lightning-charge-fill text-info me-2"></i>
                    <strong class="me-auto">Modo optimizado activado</strong>
                    <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Cerrar"></button>
                </div>
                <div class="toast-body">
                    <p class="mb-1">
                        Tu dispositivo procesa imágenes de alta resolución lentamente
                        <small class="text-muted">(${(tiempoMs / 1000).toFixed(1)}s en la primera captura)</small>.
                    </p>
                    <p class="mb-0 small text-muted">
                        <i class="bi bi-check-circle text-success"></i>
                        Compresión ajustada automáticamente. La resolución Full HD se mantiene —
                        las fotos siguen siendo aptas para documentar detalles finos.
                    </p>
                </div>
            </div>
        `;
        container.insertAdjacentHTML('beforeend', toastHtml);
        const toastEl = document.getElementById(toastId);
        if (toastEl && typeof window.bootstrap !== 'undefined') {
            const bsToast = new window.bootstrap.Toast(toastEl, {
                autohide: true,
                delay: 7000
            });
            bsToast.show();
            toastEl.addEventListener('hidden.bs.toast', () => toastEl.remove());
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