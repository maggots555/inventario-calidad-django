// ============================================================================
// SISTEMA DUAL DE SUBIDA DE IMÁGENES - GALERÍA Y CÁMARA
// ============================================================================

/**
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * 
 * Este módulo maneja la subida de imágenes con dos opciones:
 * 1. Selección desde galería (múltiples archivos a la vez)
 * 2. Captura con cámara (acceso directo en móviles)
 * 
 * Funcionalidades:
 * - Unifica archivos de ambos inputs en un solo array
 * - Muestra preview con miniaturas
 * - Permite eliminar imágenes individuales
 * - Valida límites (30 imágenes, 50MB cada una)
 * - Transfiere archivos al input oculto para envío al servidor
 */

interface ImagenPreview {
    file: File;
    id: string;
    previewUrl: string;
}

class UploadImagenesDual {
    // Elementos del DOM
    private inputGaleria: HTMLInputElement | null;
    private inputCamara: HTMLInputElement | null;
    private inputUnificado: HTMLInputElement | null;
    private previewContainer: HTMLElement | null;
    private contenedorMiniaturas: HTMLElement | null;
    private btnSubir: HTMLButtonElement | null;
    private btnLimpiarTodo: HTMLButtonElement | null;
    private cantidadSpan: HTMLElement | null;
    
    // Array de imágenes seleccionadas
    private imagenesSeleccionadas: ImagenPreview[] = [];
    
    // Límites de validación
    private readonly MAX_IMAGENES = 30;
    private readonly MAX_SIZE_MB = 50;
    private readonly MAX_SIZE_BYTES = this.MAX_SIZE_MB * 1024 * 1024;
    
    // Control de estado de procesamiento (NUEVO - FIX para archivos grandes)
    private estaProcesando: boolean = false;  // Indica si está procesando archivos
    private archivosListos: boolean = false;  // Indica si los archivos están 100% listos para subir
    
    constructor() {
        this.inputGaleria = document.getElementById('inputGaleria') as HTMLInputElement;
        this.inputCamara = document.getElementById('inputCamara') as HTMLInputElement;
        this.inputUnificado = document.getElementById('imagenesUnificadas') as HTMLInputElement;
        this.previewContainer = document.getElementById('previewImagenes');
        this.contenedorMiniaturas = document.getElementById('contenedorMiniaturas');
        this.btnSubir = document.getElementById('btnSubirImagenes') as HTMLButtonElement;
        this.btnLimpiarTodo = document.getElementById('btnLimpiarTodo') as HTMLButtonElement;
        this.cantidadSpan = document.getElementById('cantidadImagenes');
        
        this.init();
    }
    
    private init(): void {
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
        
        console.log('✅ Sistema dual de subida de imágenes inicializado');
    }
    
    /**
     * Abre el modal de cámara integrada
     */
    private abrirCamaraIntegrada(): void {
        const camaraIntegrada = (window as any).camaraIntegrada;
        if (camaraIntegrada) {
            camaraIntegrada.abrir();
        } else {
            console.error('❌ Cámara integrada no disponible');
            alert('La cámara integrada no está disponible. Verifica que estés usando HTTPS o localhost.');
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
    }
    
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
     * Agrega archivos al array de imágenes seleccionadas
     * MODIFICADO: Ahora es asíncrono y espera a que los archivos estén 100% listos
     */
    private async agregarArchivos(archivos: File[]): Promise<void> {
        // CRÍTICO: Marcar como procesando y deshabilitar botón de subir
        this.estaProcesando = true;
        this.archivosListos = false;
        this.actualizarEstadoBotonSubir(); // Deshabilitar inmediatamente
        
        let agregados = 0;
        let omitidos = 0;
        const errores: string[] = [];
        
        console.log(`🔄 Iniciando procesamiento de ${archivos.length} archivo(s)...`);
        
        for (const archivo of archivos) {
            // Validar que sea una imagen
            if (!archivo.type.startsWith('image/')) {
                errores.push(`${archivo.name}: No es una imagen`);
                omitidos++;
                continue;
            }
            
            // Validar tamaño
            if (archivo.size > this.MAX_SIZE_BYTES) {
                const sizeMB = (archivo.size / (1024 * 1024)).toFixed(2);
                errores.push(`${archivo.name}: Tamaño ${sizeMB}MB excede el límite de ${this.MAX_SIZE_MB}MB`);
                omitidos++;
                continue;
            }
            
            // Validar límite total de imágenes
            if (this.imagenesSeleccionadas.length >= this.MAX_IMAGENES) {
                errores.push(`Se alcanzó el límite máximo de ${this.MAX_IMAGENES} imágenes`);
                omitidos++;
                break;
            }
            
            // Generar ID único
            const id = `img_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
            
            // Crear URL de preview (operación síncrona pero puede ser pesada)
            const previewUrl = URL.createObjectURL(archivo);
            
            // Agregar a la lista
            this.imagenesSeleccionadas.push({
                file: archivo,
                id: id,
                previewUrl: previewUrl
            });
            
            agregados++;
            
            // NUEVO: Yield al event loop cada 3 archivos para mantener UI responsive
            if (agregados % 3 === 0) {
                await this.delay(10); // 10ms para que el navegador respire
            }
        }
        
        // Mostrar errores si los hay
        if (errores.length > 0) {
            console.warn('⚠️ Archivos omitidos:', errores);
            this.mostrarAlerta(errores.join('\n'), 'warning');
        }
        
        if (agregados > 0) {
            console.log(`✅ ${agregados} imagen(es) agregada(s). Total: ${this.imagenesSeleccionadas.length}`);
        }
        
        // Actualizar UI (pero aún sin habilitar el botón)
        this.actualizarPreview();
        
        // CRÍTICO: Transferir archivos al input y ESPERAR a que termine
        await this.transferirArchivosAInputUnificado();
        
        // CRÍTICO: Marcar como listo SOLO después de que todo esté completo
        this.estaProcesando = false;
        this.archivosListos = this.imagenesSeleccionadas.length > 0;
        this.actualizarEstadoBotonSubir(); // Habilitar si hay archivos
        
        console.log(`✅ Procesamiento completado. Archivos listos: ${this.archivosListos}`);
    }
    
    /**
     * Utilidad: Delay para yield al event loop
     */
    private delay(ms: number): Promise<void> {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    /**
     * Actualiza el preview de miniaturas
     * MODIFICADO: Ya no habilita/deshabilita el botón directamente
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
        
        // NOTA: El estado del botón se maneja en actualizarEstadoBotonSubir()
    }
    
    /**
     * Actualiza el estado del botón de subir según el estado de procesamiento
     * NUEVO: Controla el botón basándose en archivosListos y estaProcesando
     */
    private actualizarEstadoBotonSubir(): void {
        if (!this.btnSubir) {
            return;
        }
        
        // Deshabilitar si está procesando o no hay imágenes listas
        const debeEstarDeshabilitado = this.estaProcesando || !this.archivosListos || this.imagenesSeleccionadas.length === 0;
        
        this.btnSubir.disabled = debeEstarDeshabilitado;
        
        // Cambiar texto del botón si está procesando
        if (this.estaProcesando) {
            this.btnSubir.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Procesando...';
        } else if (this.imagenesSeleccionadas.length > 0) {
            this.btnSubir.innerHTML = '<i class="bi bi-cloud-upload"></i> Subir Imágenes';
        } else {
            this.btnSubir.innerHTML = '<i class="bi bi-cloud-upload"></i> Subir Imágenes';
        }
        
        console.log(`🔘 Botón actualizado: ${debeEstarDeshabilitado ? 'DESHABILITADO' : 'HABILITADO'} | Procesando: ${this.estaProcesando} | Listos: ${this.archivosListos}`);
    }
    
    /**
     * Crea un elemento de miniatura para una imagen
     */
    private crearMiniatura(imagen: ImagenPreview, index: number): HTMLElement {
        const col = document.createElement('div');
        col.className = 'col-4 col-sm-3 col-md-2';
        
        // Calcular tamaño del archivo
        const sizeMB = (imagen.file.size / (1024 * 1024)).toFixed(2);
        
        col.innerHTML = `
            <div class="preview-thumbnail" data-id="${imagen.id}">
                <img src="${imagen.previewUrl}" alt="Preview ${index + 1}">
                <button type="button" class="btn-eliminar-preview" data-id="${imagen.id}" title="Eliminar">
                    <i class="bi bi-x-circle-fill"></i>
                </button>
                <div class="preview-info">
                    <small class="fw-bold">${sizeMB} MB</small>
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
     * Elimina una imagen del array de seleccionadas
     * MODIFICADO: Ahora actualiza el estado de archivosListos
     */
    private async eliminarImagen(id: string): Promise<void> {
        const index = this.imagenesSeleccionadas.findIndex(img => img.id === id);
        
        if (index !== -1) {
            // Liberar memoria del ObjectURL
            URL.revokeObjectURL(this.imagenesSeleccionadas[index].previewUrl);
            
            // Eliminar del array
            this.imagenesSeleccionadas.splice(index, 1);
            
            console.log(`🗑️ Imagen eliminada. Total: ${this.imagenesSeleccionadas.length}`);
            
            // Actualizar UI
            this.actualizarPreview();
            
            // Re-transferir archivos (ahora sin el eliminado)
            this.estaProcesando = true;
            this.archivosListos = false;
            this.actualizarEstadoBotonSubir();
            
            await this.transferirArchivosAInputUnificado();
            
            this.estaProcesando = false;
            this.archivosListos = this.imagenesSeleccionadas.length > 0;
            this.actualizarEstadoBotonSubir();
        }
    }
    
    /**
     * Limpia todas las imágenes seleccionadas
     */
    private limpiarTodo(): void {
        // Liberar memoria de todos los ObjectURLs
        this.imagenesSeleccionadas.forEach(img => {
            URL.revokeObjectURL(img.previewUrl);
        });
        
        // Limpiar array
        this.imagenesSeleccionadas = [];
        
        // Limpiar inputs
        if (this.inputGaleria) this.inputGaleria.value = '';
        if (this.inputCamara) this.inputCamara.value = '';
        if (this.inputUnificado) this.inputUnificado.value = '';
        
        // Resetear estados
        this.estaProcesando = false;
        this.archivosListos = false;
        
        console.log('🧹 Todas las imágenes eliminadas');
        
        // Actualizar UI
        this.actualizarPreview();
        this.actualizarEstadoBotonSubir();
    }
    
    /**
     * Transfiere archivos del array al input unificado para envío al servidor
     * MODIFICADO: Ahora es asíncrono y retorna Promise para garantizar sincronización
     */
    private async transferirArchivosAInputUnificado(): Promise<void> {
        if (!this.inputUnificado) {
            return;
        }
        
        console.log(`📦 Transfiriendo ${this.imagenesSeleccionadas.length} archivo(s) al input unificado...`);
        
        // Crear un nuevo DataTransfer para manipular los archivos del input
        const dataTransfer = new DataTransfer();
        
        // Agregar todos los archivos seleccionados
        // NOTA: DataTransfer.items.add() es síncrono, pero puede ser lento con muchos archivos
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
     * Muestra una alerta al usuario
     */
    private mostrarAlerta(mensaje: string, tipo: 'success' | 'warning' | 'error'): void {
        // Usar el sistema de alertas de Bootstrap existente
        const alertClass = tipo === 'success' ? 'alert-success' : 
                          tipo === 'warning' ? 'alert-warning' : 'alert-danger';
        
        const alertHtml = `
            <div class="alert ${alertClass} alert-dismissible fade show" role="alert">
                <i class="bi bi-${tipo === 'success' ? 'check-circle' : tipo === 'warning' ? 'exclamation-triangle' : 'x-circle'}"></i>
                ${mensaje.replace(/\n/g, '<br>')}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            </div>
        `;
        
        // Insertar antes del formulario
        const form = document.getElementById('formSubirImagenes');
        if (form && form.parentElement) {
            const tempDiv = document.createElement('div');
            tempDiv.innerHTML = alertHtml;
            const alertElement = tempDiv.firstElementChild;
            if (alertElement) {
                form.parentElement.insertBefore(alertElement, form);
            }
            
            // Auto-eliminar después de 5 segundos
            setTimeout(() => {
                const alert = form.parentElement?.querySelector('.alert');
                if (alert) {
                    alert.remove();
                }
            }, 5000);
        }
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
        console.log('✅ Sistema de subida dual inicializado');
    }
});
