// ============================================================================
// VISOR DE CÁMARA INTEGRADO - MEDIA CAPTURE API
// ============================================================================

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * 
 * Esta clase maneja la cámara integrada usando la API getUserMedia del navegador.
 * Permite tomar múltiples fotos sin salir de la página, como WhatsApp Web.
 * 
 * Funcionalidades:
 * - Acceso a cámara trasera/frontal
 * - Captura de múltiples fotos en secuencia
 * - Preview en tiempo real
 * - Integración con el sistema de subida existente
 */

interface FotoCapturada {
    blob: Blob;
    dataUrl: string;
    timestamp: number;
}

interface DispositivoCamara {
    deviceId: string;
    label: string;
    tipo: 'frontal' | 'trasera';
    facingMode?: 'user' | 'environment';
}

class CamaraIntegrada {
    // Elementos del DOM
    private modal: HTMLElement | null;
    private videoElement: HTMLVideoElement | null;
    private canvas: HTMLCanvasElement | null;
    private btnCapturar: HTMLButtonElement | null;
    private btnCambiarCamara: HTMLButtonElement | null;
    private btnCerrar: HTMLButtonElement | null;
    private btnFinalizar: HTMLButtonElement | null;
    private contadorFotos: HTMLElement | null;
    private cameraError: HTMLElement | null;
    private mensajeError: HTMLElement | null;
    private detalleError: HTMLElement | null;
    private selectorLentes: HTMLElement | null;
    
    // Stream de video
    private mediaStream: MediaStream | null = null;
    private facingMode: 'user' | 'environment' = 'environment'; // Trasera por defecto
    
    // Gestión de dispositivos de cámara
    private dispositivosCamara: DispositivoCamara[] = [];
    private dispositivoActualId: string | null = null;
    private camarasTraseras: DispositivoCamara[] = [];
    private camarasFrontales: DispositivoCamara[] = [];
    
    // Fotos capturadas
    private fotosCapturadas: FotoCapturada[] = [];
    
    // Callback para integración con sistema de subida
    private onFotosCapturadas: ((fotos: Blob[]) => void) | null = null;
    
    constructor() {
        this.modal = document.getElementById('modalCamaraIntegrada');
        this.videoElement = document.getElementById('videoPreview') as HTMLVideoElement;
        this.canvas = document.getElementById('canvasCaptura') as HTMLCanvasElement;
        this.btnCapturar = document.getElementById('btnCapturar') as HTMLButtonElement;
        this.btnCambiarCamara = document.getElementById('btnCambiarCamara') as HTMLButtonElement;
        this.btnCerrar = document.getElementById('btnCerrarCamara') as HTMLButtonElement;
        this.btnFinalizar = document.getElementById('btnFinalizarCaptura') as HTMLButtonElement;
        this.contadorFotos = document.getElementById('contadorFotos');
        this.cameraError = document.getElementById('cameraError');
        this.mensajeError = document.getElementById('mensajeError');
        this.detalleError = document.getElementById('detalleError');
        this.selectorLentes = document.getElementById('selectorLentes');
        
        this.init();
    }
    
    private init(): void {
        if (!this.modal) {
            console.warn('⚠️ Modal de cámara no encontrado');
            return;
        }
        
        // Event listeners del modal
        this.modal.addEventListener('shown.bs.modal', () => this.abrirCamara());
        this.modal.addEventListener('hidden.bs.modal', () => this.cerrarCamara());
        
        // Event listeners de botones
        if (this.btnCapturar) {
            this.btnCapturar.addEventListener('click', () => this.capturarFoto());
        }
        
        if (this.btnCambiarCamara) {
            this.btnCambiarCamara.addEventListener('click', () => this.cambiarCamara());
        }
        
        if (this.btnCerrar) {
            this.btnCerrar.addEventListener('click', () => this.cerrarModal());
        }
        
        if (this.btnFinalizar) {
            this.btnFinalizar.addEventListener('click', () => this.finalizarCaptura());
        }
        
        console.log('✅ Cámara integrada inicializada');
    }
    
    /**
     * Abre la cámara usando getUserMedia
     * EXPLICACIÓN: Ahora detecta primero todos los dispositivos disponibles
     * y permite seleccionar entre diferentes lentes (gran angular, normal, teleobjetivo)
     * 
     * BUG FIX: Detiene streams ANTES de detectar dispositivos para evitar conflictos
     */
    private async abrirCamara(): Promise<void> {
        console.log('📷 Intentando abrir cámara...');
        
        // Ocultar error si estaba visible
        if (this.cameraError) {
            this.cameraError.style.display = 'none';
        }
        
        try {
            // CRÍTICO: Detener stream anterior PRIMERO (antes de detectar dispositivos)
            if (this.mediaStream) {
                this.detenerStream();
                // Esperar un momento para asegurar liberación completa
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            
            // PASO 1: Detectar todos los dispositivos de cámara disponibles
            await this.detectarDispositivosCamara();
            
            // PASO 2: Construir constraints según dispositivo seleccionado
            const constraints: MediaStreamConstraints = {
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
            
        } catch (error) {
            console.error('❌ Error al acceder a la cámara:', error);
            this.mostrarError(error as Error);
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
     */
    private async detectarDispositivosCamara(): Promise<void> {
        let streamTemporal: MediaStream | null = null;
        
        try {
            // Primero solicitar permisos si aún no los tiene
            // IMPORTANTE: Guardamos el stream temporal para liberarlo después
            streamTemporal = await navigator.mediaDevices.getUserMedia({ video: true });
            
            // Obtener lista de todos los dispositivos multimedia
            const devices = await navigator.mediaDevices.enumerateDevices();
            
            // Filtrar solo dispositivos de video (cámaras)
            const camaras = devices.filter(device => device.kind === 'videoinput');
            
            console.log(`🔍 Detectadas ${camaras.length} cámara(s)`);
            
            // Limpiar arrays
            this.dispositivosCamara = [];
            this.camarasTraseras = [];
            this.camarasFrontales = [];
            
            // Clasificar cámaras por tipo
            for (const camara of camaras) {
                const label = camara.label.toLowerCase();
                
                // Determinar si es frontal o trasera
                const esFrontal = label.includes('front') || label.includes('user') || label.includes('facing front');
                const esTrasera = label.includes('back') || label.includes('rear') || label.includes('environment') || label.includes('facing back');
                
                const dispositivo: DispositivoCamara = {
                    deviceId: camara.deviceId,
                    label: camara.label,
                    tipo: esFrontal ? 'frontal' : 'trasera',
                    facingMode: esFrontal ? 'user' : 'environment'
                };
                
                this.dispositivosCamara.push(dispositivo);
                
                if (esFrontal) {
                    this.camarasFrontales.push(dispositivo);
                } else {
                    this.camarasTraseras.push(dispositivo);
                }
                
                console.log(`  📹 ${dispositivo.label} (${dispositivo.tipo})`);
            }
            
            // Si no hay dispositivo seleccionado, elegir la primera cámara trasera
            if (!this.dispositivoActualId && this.camarasTraseras.length > 0) {
                this.dispositivoActualId = this.camarasTraseras[0].deviceId;
            } else if (!this.dispositivoActualId && this.camarasFrontales.length > 0) {
                this.dispositivoActualId = this.camarasFrontales[0].deviceId;
            }
            
        } catch (error) {
            console.error('❌ Error al detectar dispositivos de cámara:', error);
        } finally {
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
    private construirConstraintsCamara(): MediaTrackConstraints {
        const constraints: MediaTrackConstraints = {
            width: { ideal: 1920 },
            height: { ideal: 1080 }
        };
        
        // Si hay un dispositivo específico seleccionado, usarlo
        if (this.dispositivoActualId) {
            constraints.deviceId = { exact: this.dispositivoActualId };
        } else {
            // Fallback: usar facingMode
            constraints.facingMode = this.facingMode;
        }
        
        return constraints;
    }
    
    /**
     * Actualiza la UI del selector de lentes
     */
    private actualizarSelectorLentes(): void {
        if (!this.selectorLentes) return;
        
        // Limpiar selector
        this.selectorLentes.innerHTML = '';
        
        // Solo mostrar selector si hay múltiples cámaras traseras
        const camarasActivas = this.facingMode === 'environment' ? this.camarasTraseras : this.camarasFrontales;
        
        if (camarasActivas.length <= 1) {
            this.selectorLentes.style.display = 'none';
            return;
        }
        
        this.selectorLentes.style.display = 'flex';
        
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
            
            if (this.selectorLentes) {
                this.selectorLentes.appendChild(btn);
            }
        });
    }
    
    /**
     * Obtiene icono y texto para un lente según su label
     */
    private obtenerInfoLente(label: string, index: number): { icono: string; texto: string } {
        const labelLower = label.toLowerCase();
        
        // Intentar identificar el tipo de lente por el label
        if (labelLower.includes('ultra') || labelLower.includes('wide') || labelLower.includes('0.5')) {
            return { icono: 'bi-arrows-angle-expand', texto: '0.5x' };
        } else if (labelLower.includes('tele') || labelLower.includes('zoom') || labelLower.includes('2x') || labelLower.includes('3x')) {
            return { icono: 'bi-zoom-in', texto: '2x' };
        } else if (labelLower.includes('macro')) {
            return { icono: 'bi-flower1', texto: 'Macro' };
        } else {
            // Por defecto, asignar nombres genéricos
            return { icono: 'bi-camera', texto: `Lente ${index + 1}` };
        }
    }
    
    /**
     * Cambia a un dispositivo de cámara específico
     */
    private async cambiarADispositivo(deviceId: string): Promise<void> {
        console.log(`🔄 Cambiando a dispositivo: ${deviceId}`);
        
        this.dispositivoActualId = deviceId;
        await this.abrirCamara();
    }
    
    /**
     * Configura tap-to-focus en el video
     */
    private configurarTapToFocus(): void {
        if (!this.videoElement || !this.mediaStream) {
            return;
        }
        
        // Obtener el track de video
        const videoTrack = this.mediaStream.getVideoTracks()[0];
        
        // Verificar si el dispositivo soporta focus
        const capabilities: any = videoTrack.getCapabilities();
        if (!capabilities.focusMode || !capabilities.focusMode.includes('continuous')) {
            console.log('⚠️ Dispositivo no soporta enfoque manual');
            return;
        }
        
        // Event listener para tap en el video
        this.videoElement.addEventListener('click', async (e: MouseEvent) => {
            await this.enfocarEnPunto(e);
        });
        
        // También para touch en móviles
        this.videoElement.addEventListener('touchstart', async (e: TouchEvent) => {
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
    private async enfocarEnPunto(e: MouseEvent): Promise<void> {
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
                } as any]
            });
            
            // Feedback visual (círculo en el punto tocado)
            // Calcular coordenadas relativas al contenedor
            const relativeX = e.clientX - rect.left;
            const relativeY = e.clientY - rect.top;
            this.mostrarIndicadorEnfoque(relativeX, relativeY);
            
            console.log(`🎯 Enfocando en: (${(x*100).toFixed(0)}%, ${(y*100).toFixed(0)}%)`);
            
        } catch (error) {
            console.warn('⚠️ No se pudo aplicar enfoque:', error);
        }
    }
    
    /**
     * Muestra un indicador visual de enfoque
     */
    private mostrarIndicadorEnfoque(x: number, y: number): void {
        if (!this.videoElement) return;
        
        const container = this.videoElement.parentElement;
        if (!container) return;
        
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
    private detenerStream(): void {
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
    private async cambiarCamara(): Promise<void> {
        console.log('🔄 Cambiando entre frontal/trasera...');
        
        // Alternar entre frontal y trasera
        this.facingMode = this.facingMode === 'environment' ? 'user' : 'environment';
        
        // Seleccionar el primer dispositivo del tipo nuevo
        const camarasDisponibles = this.facingMode === 'environment' ? this.camarasTraseras : this.camarasFrontales;
        
        if (camarasDisponibles.length > 0) {
            this.dispositivoActualId = camarasDisponibles[0].deviceId;
        } else {
            // Fallback si no hay cámaras del tipo deseado
            this.dispositivoActualId = null;
        }
        
        // Reiniciar cámara con nueva orientación
        await this.abrirCamara();
    }
    
    /**
     * Captura una foto del stream de video
     */
    private capturarFoto(): void {
        if (!this.videoElement || !this.canvas) {
            console.error('❌ Elementos no disponibles para captura');
            return;
        }
        
        // Verificar que hay video activo
        if (!this.mediaStream || this.videoElement.readyState < 2) {
            console.warn('⚠️ Video no listo para captura');
            return;
        }
        
        console.log('📸 Capturando foto...');
        
        // Configurar canvas con dimensiones del video
        const videoWidth = this.videoElement.videoWidth;
        const videoHeight = this.videoElement.videoHeight;
        
        this.canvas.width = videoWidth;
        this.canvas.height = videoHeight;
        
        // Dibujar frame actual del video en el canvas
        const context = this.canvas.getContext('2d');
        if (!context) {
            console.error('❌ No se pudo obtener contexto del canvas');
            return;
        }
        
        context.drawImage(this.videoElement, 0, 0, videoWidth, videoHeight);
        
        // Convertir canvas a Blob
        this.canvas.toBlob((blob) => {
            if (!blob) {
                console.error('❌ Error al crear blob de la foto');
                return;
            }
            
            // Obtener dataURL para preview
            const dataUrl = this.canvas!.toDataURL('image/jpeg', 0.95);
            
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
            
            console.log(`✅ Foto capturada. Total: ${this.fotosCapturadas.length}`);
            
        }, 'image/jpeg', 0.95);
    }
    
    /**
     * Actualiza el contador de fotos tomadas
     */
    private actualizarContador(): void {
        if (this.contadorFotos) {
            this.contadorFotos.textContent = String(this.fotosCapturadas.length);
        }
    }
    
    /**
     * Muestra feedback visual al capturar foto (flash)
     */
    private mostrarFeedbackCaptura(): void {
        if (!this.videoElement) return;
        
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
    private finalizarCaptura(): void {
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
    private cerrarModal(): void {
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
    private cerrarCamara(): void {
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
    private mostrarError(error: Error): void {
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
        } else if (error.name === 'NotFoundError') {
            this.mensajeError.textContent = 'No se encontró ninguna cámara';
            this.detalleError.textContent = 'Verifica que tu dispositivo tenga una cámara disponible';
        } else if (error.name === 'NotReadableError') {
            this.mensajeError.textContent = 'Cámara en uso por otra aplicación';
            this.detalleError.textContent = 'Cierra otras aplicaciones que estén usando la cámara';
        } else {
            this.mensajeError.textContent = 'No se pudo acceder a la cámara';
            this.detalleError.textContent = error.message || 'Error desconocido';
        }
    }
    
    /**
     * Abre el modal de cámara
     */
    public abrir(): void {
        if (this.modal) {
            const bsModal = new bootstrap.Modal(this.modal);
            bsModal.show();
        }
    }
    
    /**
     * Configura callback para recibir fotos capturadas
     */
    public setOnFotosCapturadas(callback: (fotos: Blob[]) => void): void {
        this.onFotosCapturadas = callback;
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('modalCamaraIntegrada')) {
        (window as any).camaraIntegrada = new CamaraIntegrada();
        console.log('✅ Cámara integrada disponible');
    }
});
