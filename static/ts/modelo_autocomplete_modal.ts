/**
 * ============================================================================
 * AUTOCOMPLETADO DE MODELOS EN MODAL DE EDICIÓN
 * ============================================================================
 * 
 * Este archivo TypeScript maneja la funcionalidad de autocompletado del campo
 * "Modelo" dentro del MODAL de edición de información del equipo.
 * 
 * DIFERENCIAS CON modelo_autocomplete.ts:
 * - Se activa SOLO cuando el modal se abre (evento 'shown.bs.modal')
 * - Se destruye cuando el modal se cierra (evento 'hidden.bs.modal')
 * - Previene memory leaks y conflictos de IDs
 * - Reutiliza la misma API pero en contexto de modal
 * 
 * FUNCIONALIDAD:
 * - Convierte el campo "Modelo" en un Select2 con búsqueda AJAX
 * - Busca modelos en ReferenciaGamaEquipo según la marca seleccionada
 * - Permite seleccionar un modelo existente o ingresar uno nuevo
 * - Muestra badges de gama (Alta/Media/Baja) con colores
 * - Limpia recursos al cerrar el modal
 * 
 * DEPENDENCIAS:
 * - jQuery 3.7+
 * - Select2 4.1.0+
 * - Bootstrap 5.3+ (para eventos de modal)
 * 
 * AUTOR: Jorge Magos (@maggots)
 * FECHA: Diciembre 2025
 * ============================================================================
 */

/**
 * Interface para la respuesta de la API de búsqueda de modelos
 */
interface ModeloSearchResult {
    id: string;           // Nombre del modelo
    text: string;         // Texto a mostrar
    gama?: string;        // Gama del equipo (baja/media/alta)
    rango_costo?: string; // Rango de costo
}

/**
 * Interface para la respuesta completa de la API
 */
interface ModeloSearchResponse {
    results: ModeloSearchResult[];
    total?: number;
    mensaje?: string;
    error?: string;
}

/**
 * ============================================================================
 * CLASE PRINCIPAL: ModeloAutocompleteModal
 * ============================================================================
 */
class ModeloAutocompleteModal {
    private modalElement: HTMLElement | null = null;
    private modeloSelect: any = null;
    private marcaSelect: any = null;
    private apiUrl: string = '';
    private isInitialized: boolean = false;

    /**
     * Constructor - Configura los event listeners del modal
     */
    constructor() {
        // Esperar a que el DOM esté completamente cargado
        $(document).ready(() => {
            this.init();
        });
    }

    /**
     * Inicializar event listeners del modal
     */
    private init(): void {
        // Obtener referencia al modal
        this.modalElement = document.getElementById('modalEditarInfoEquipo');

        if (!this.modalElement) {
            console.warn('ModeloAutocompleteModal: Modal no encontrado');
            return;
        }

        // Event listener: Cuando el modal se ABRE
        this.modalElement.addEventListener('shown.bs.modal', () => {
            this.onModalShown();
        });

        // Event listener: Cuando el modal se CIERRA
        this.modalElement.addEventListener('hidden.bs.modal', () => {
            this.onModalHidden();
        });

        console.log('✅ ModeloAutocompleteModal: Event listeners configurados');
    }

    /**
     * Manejar apertura del modal - Inicializar Select2
     */
    private onModalShown(): void {
        console.log('📖 Modal abierto - Inicializando Select2 para modelo...');

        // Obtener referencias a los elementos dentro del modal
        this.modeloSelect = $('#id_modelo');
        this.marcaSelect = $('#id_marca');

        // Verificar que los elementos existan
        if (!this.modeloSelect || this.modeloSelect.length === 0) {
            console.warn('⚠️ Campo "modelo" no encontrado en el modal');
            return;
        }

        if (!this.marcaSelect || this.marcaSelect.length === 0) {
            console.warn('⚠️ Campo "marca" no encontrado en el modal');
            return;
        }

        // Obtener URL de la API
        this.apiUrl = this.modeloSelect.data('api-url') || '/servicio-tecnico/api/buscar-modelos-por-marca/';

        // 💾 GUARDAR EL VALOR ACTUAL del modelo antes de destruir Select2
        const valorActual = this.modeloSelect.val();
        console.log('💾 Valor actual del modelo:', valorActual);

        // Verificar si Select2 ya está inicializado
        if (this.modeloSelect.hasClass('select2-hidden-accessible')) {
            console.log('ℹ️ Select2 ya estaba inicializado, destruyendo...');
            this.modeloSelect.select2('destroy');
        }

        // Inicializar Select2
        this.initializeSelect2();

        // 🔄 RESTAURAR EL VALOR después de inicializar Select2
        if (valorActual) {
            // Esperar un momento para que Select2 termine de inicializar
            setTimeout(() => {
                // Crear una opción con el valor actual para Select2
                const option = new Option(valorActual, valorActual, true, true);
                this.modeloSelect.append(option);
                this.modeloSelect.val(valorActual).trigger('change.select2');
                console.log('✅ Valor restaurado:', valorActual);
            }, 50);
        }

        // Configurar event listeners
        this.setupEventListeners();

        this.isInitialized = true;
        console.log('✅ Select2 inicializado correctamente en modal');
    }

    /**
     * Manejar cierre del modal - Destruir Select2
     */
    private onModalHidden(): void {
        if (!this.isInitialized) return;

        console.log('📕 Modal cerrado - Limpiando Select2...');

        // Destruir Select2 para liberar memoria
        if (this.modeloSelect && this.modeloSelect.hasClass('select2-hidden-accessible')) {
            this.modeloSelect.select2('destroy');
        }

        // Limpiar event listeners específicos del modal
        if (this.marcaSelect) {
            this.marcaSelect.off('change');
        }

        if (this.modeloSelect) {
            this.modeloSelect.off('select2:opening');
            this.modeloSelect.off('select2:error');
        }

        this.isInitialized = false;
        console.log('✅ Recursos liberados correctamente');
    }

    /**
     * Inicializar Select2 en el campo modelo
     */
    private initializeSelect2(): void {
        if (!this.modeloSelect || !this.marcaSelect) return;

        const config = {
            ajax: {
                url: this.apiUrl,
                dataType: 'json',
                delay: 300,
                data: (params: any) => {
                    const marcaSeleccionada = this.marcaSelect?.val() as string;
                    return {
                        marca: marcaSeleccionada,
                        q: params.term
                    };
                },
                processResults: (data: ModeloSearchResponse) => {
                    if (data.error) {
                        console.error('❌ Error en API:', data.error);
                        return { results: [] };
                    }

                    // Log de resultados
                    if (data.results && data.results.length > 0) {
                        const marca = this.marcaSelect?.val() as string;
                        console.log(`✅ ${data.results.length} modelos encontrados para ${marca}`);
                    }

                    return {
                        results: data.results || []
                    };
                },
                cache: true
            },
            tags: true, // Permite valores personalizados
            placeholder: 'Busca o escribe el modelo del equipo',
            allowClear: true,
            minimumInputLength: 0,
            theme: 'bootstrap-5',
            dropdownParent: $('#modalEditarInfoEquipo'), // CRÍTICO: Dropdown dentro del modal
            width: '100%', // Asegurar que tome el ancho completo
            language: {
                noResults: () => 'No hay modelos registrados. Escribe para ingresar uno nuevo.',
                searching: () => 'Buscando modelos...',
                inputTooShort: () => 'Selecciona una marca primero',
                errorLoading: () => 'Error al cargar los resultados'
            },
            // CRÍTICO: Para que tags funcione correctamente
            createTag: function (params: any) {
                const term = params.term?.trim();
                
                if (term === '') {
                    return null;
                }

                return {
                    id: term,
                    text: term,
                    newTag: true // Marcar como nuevo
                };
            },
            // Template para mostrar resultados con badges
            templateResult: (result: ModeloSearchResult) => {
                if (!result.id) {
                    return result.text;
                }

                // Si es un tag nuevo (escribió el usuario)
                if ((result as any).newTag) {
                    return $(`
                        <div class="d-flex justify-content-between align-items-center">
                            <span>${result.id}</span>
                            <span class="badge bg-info ms-2">NUEVO</span>
                        </div>
                    `);
                }

                // Crear badge de gama con colores
                if (result.gama) {
                    const gamaClass = result.gama === 'alta' ? 'bg-success' : 
                                     result.gama === 'media' ? 'bg-primary' : 'bg-secondary';
                    
                    const $result = $(`
                        <div class="d-flex justify-content-between align-items-center">
                            <span>${result.id}</span>
                            <span class="badge ${gamaClass} ms-2">${result.gama.toUpperCase()}</span>
                        </div>
                    `);
                    return $result;
                }

                return result.id;
            },
            // Template para la selección
            templateSelection: (selection: ModeloSearchResult) => {
                return selection.text || selection.id;
            },
            // CRÍTICO: Insertar el tag después de crearlo
            insertTag: function (data: any, tag: any) {
                // Insertar el tag al inicio de la lista
                data.unshift(tag);
            }
        };

        // Aplicar Select2
        this.modeloSelect.select2(config);

        // DEBUG: Monitorear eventos de Select2
        this.modeloSelect.on('select2:select', (e: any) => {
            console.log('✅ Seleccionado:', e.params.data);
            
            // FORZAR actualización visual del campo
            const valorSeleccionado = e.params.data.id;
            const textoSeleccionado = e.params.data.text || e.params.data.id;
            
            // Cerrar el dropdown
            this.modeloSelect.select2('close');
            
            // Asegurarse que el valor se establezca en el input original
            this.modeloSelect.val(valorSeleccionado);
            
            // Forzar múltiples actualizaciones para asegurar que se renderice
            setTimeout(() => {
                this.modeloSelect.trigger('change');
                
                // Verificar el elemento de visualización de Select2
                const $selection = this.modeloSelect.next('.select2-container').find('.select2-selection__rendered');
                if ($selection.length > 0) {
                    console.log('🎨 Actualizando visualización Select2...');
                    $selection.text(textoSeleccionado);
                    $selection.attr('title', textoSeleccionado);
                }
            }, 10);
        });

        this.modeloSelect.on('select2:unselect', (e: any) => {
            console.log('❌ Deseleccionado:', e.params.data);
        });

        this.modeloSelect.on('change', (e: any) => {
            const valorActual = $(e.target).val();
            console.log('🔄 Cambio detectado, valor actual:', valorActual);
            
            // Verificar que el input subyacente tenga el valor
            if (valorActual) {
                console.log('📝 Valor establecido en input:', this.modeloSelect.get(0).value);
            }
        });

        // Manejar errores de AJAX
        this.modeloSelect.on('select2:error', (e: any) => {
            console.error('❌ Error en Select2 AJAX:', e.params?.jqXHR?.responseText);
            this.showErrorNotification('Error al cargar modelos. Verifica tu conexión.');
        });

        console.log('🎨 Select2 configurado con badges de gama');
    }

    /**
     * Configurar event listeners específicos del modal
     */
    private setupEventListeners(): void {
        if (!this.marcaSelect || !this.modeloSelect) return;

        // Guardar la marca actual para detectar cambios reales
        let marcaAnterior = this.marcaSelect.val();

        // Cuando cambia la marca, solo limpiar si realmente cambió
        this.marcaSelect.on('change', () => {
            const marcaActual = this.marcaSelect?.val();
            
            // Solo limpiar si la marca cambió realmente (no en la carga inicial)
            if (marcaAnterior && marcaActual !== marcaAnterior) {
                this.onMarcaChange();
            }
            
            marcaAnterior = marcaActual;
        });

        // Cuando se intenta abrir el Select2, verificar que haya marca
        this.modeloSelect.on('select2:opening', (e: any) => {
            if (!this.marcaSelect?.val()) {
                e.preventDefault();
                this.showMarcaWarning();
            }
        });

        console.log('🔗 Event listeners del modal configurados');
    }

    /**
     * Manejar cambio de marca
     */
    private onMarcaChange(): void {
        if (!this.modeloSelect || !this.marcaSelect) return;

        // Limpiar la selección del modelo
        this.modeloSelect.val(null).trigger('change');
        this.modeloSelect.select2('close');

        console.log('🔄 Marca cambiada - Campo modelo reiniciado');
    }

    /**
     * Mostrar advertencia cuando no hay marca seleccionada
     */
    private showMarcaWarning(): void {
        if (!this.modeloSelect) return;
        
        const $container = this.modeloSelect.closest('.mb-3');
        
        if ($container.length > 0) {
            // Verificar si ya existe una advertencia
            let $warning = $container.find('.marca-warning');
            
            if ($warning.length === 0) {
                $warning = $('<div class="alert alert-warning alert-dismissible fade show marca-warning mt-2" role="alert"></div>');
                $warning.html(`
                    <i class="bi bi-exclamation-triangle"></i> 
                    <strong>Selecciona una marca primero</strong> para ver los modelos disponibles.
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                `);
                
                $container.append($warning);

                // Auto-remover después de 5 segundos
                setTimeout(() => {
                    $warning.fadeOut(() => $warning.remove());
                }, 5000);
            }
        }

        console.log('⚠️ Advertencia mostrada: Seleccionar marca primero');
    }

    /**
     * Mostrar notificación de error
     */
    private showErrorNotification(mensaje: string): void {
        if (!this.modeloSelect) return;
        
        const $container = this.modeloSelect.closest('.mb-3');
        
        if ($container.length > 0) {
            const $error = $('<div class="alert alert-danger alert-dismissible fade show mt-2" role="alert"></div>');
            $error.html(`
                <i class="bi bi-exclamation-octagon"></i> 
                <strong>Error:</strong> ${mensaje}
                <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
            `);
            
            $container.append($error);

            setTimeout(() => {
                $error.fadeOut(() => $error.remove());
            }, 5000);
        }

        console.error('❌ Error mostrado:', mensaje);
    }
}

/**
 * ============================================================================
 * INICIALIZACIÓN AUTOMÁTICA
 * ============================================================================
 * Crear instancia cuando se carga el script
 */
const modeloAutocompleteModal = new ModeloAutocompleteModal();

/**
 * ============================================================================
 * EXPORTAR PARA USO EXTERNO (si se necesita)
 * ============================================================================
 */
// @ts-ignore - Agregar al objeto window para acceso global
window.ModeloAutocompleteModal = ModeloAutocompleteModal;
