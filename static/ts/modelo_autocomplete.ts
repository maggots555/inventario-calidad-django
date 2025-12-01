/**
 * ============================================================================
 * AUTOCOMPLETADO DE MODELOS CON SELECT2
 * ============================================================================
 * 
 * Este archivo TypeScript maneja la funcionalidad de autocompletado del campo
 * "Modelo" en los formularios de creación de órdenes de servicio.
 * 
 * FUNCIONALIDAD:
 * - Convierte el campo "Modelo" en un Select2 con búsqueda AJAX
 * - Busca modelos en ReferenciaGamaEquipo según la marca seleccionada
 * - Permite seleccionar un modelo existente o ingresar uno nuevo
 * - Muestra la gama del equipo junto al nombre del modelo
 * 
 * DEPENDENCIAS:
 * - jQuery 3.7+
 * - Select2 4.1.0+
 * - Bootstrap 5.3+
 * 
 * AUTOR: Jorge Magos (@maggots)
 * FECHA: Diciembre 2025
 * ============================================================================
 */

/**
 * Interface para la respuesta de la API de búsqueda de modelos
 */
interface ModeloSearchResult {
    id: string;           // Nombre del modelo (ej: "Inspiron 3000")
    text: string;         // Texto a mostrar (ej: "Inspiron 3000 - Gama Baja")
    gama?: string;        // Gama del equipo (ej: "baja", "media", "alta")
    rango_costo?: string; // Rango de costo (opcional)
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
 * Configuración de Select2 para el campo modelo
 */
interface Select2Config {
    ajax: {
        url: string;
        dataType: string;
        delay: number;
        data: (params: any) => any;
        processResults: (data: ModeloSearchResponse) => any;
        cache: boolean;
    };
    tags: boolean;
    placeholder: string;
    allowClear: boolean;
    minimumInputLength: number;
    theme: string;
    language: {
        noResults: () => string;
        searching: () => string;
        inputTooShort: () => string;
        errorLoading: () => string;
    };
    templateResult?: (result: ModeloSearchResult) => JQuery | string;
    templateSelection?: (selection: ModeloSearchResult) => string;
}

/**
 * ============================================================================
 * CLASE PRINCIPAL: ModeloAutocomplete
 * ============================================================================
 */
class ModeloAutocomplete {
    private modeloSelect: any = null;
    private marcaSelect: any = null;
    private apiUrl: string = '';

    /**
     * Constructor - Inicializa la funcionalidad
     */
    constructor() {
        // Esperar a que el DOM esté completamente cargado
        $(document).ready(() => {
            this.init();
        });
    }

    /**
     * Inicializar la funcionalidad de autocompletado
     */
    private init(): void {
        // Obtener referencias a los elementos del DOM
        this.modeloSelect = $('#id_modelo');
        this.marcaSelect = $('#id_marca');

        // Verificar que los elementos existan
        if (!this.modeloSelect || this.modeloSelect.length === 0) {
            console.warn('ModeloAutocomplete: Campo "modelo" no encontrado en el DOM');
            return;
        }

        if (!this.marcaSelect || this.marcaSelect.length === 0) {
            console.warn('ModeloAutocomplete: Campo "marca" no encontrado en el DOM');
            return;
        }

        // Obtener la URL de la API desde el atributo data-api-url del elemento
        // Si no existe, usar una URL por defecto
        this.apiUrl = this.modeloSelect.data('api-url') || '/servicio-tecnico/api/buscar-modelos-por-marca/';

        // Inicializar Select2
        this.initializeSelect2();

        // Configurar event listeners
        this.setupEventListeners();

        console.log('ModeloAutocomplete: Inicializado correctamente');
    }

    /**
     * Inicializar Select2 en el campo modelo
     */
    private initializeSelect2(): void {
        if (!this.modeloSelect || !this.marcaSelect) return;

        const config: Select2Config = {
            ajax: {
                url: this.apiUrl,
                dataType: 'json',
                delay: 300, // Esperar 300ms después de que el usuario deje de escribir
                data: (params: any) => {
                    const marcaSeleccionada = this.marcaSelect?.val() as string;
                    return {
                        marca: marcaSeleccionada,
                        q: params.term // Término de búsqueda ingresado por el usuario
                    };
                },
                processResults: (data: ModeloSearchResponse) => {
                    // Verificar si hay error en la respuesta
                    if (data.error) {
                        console.error('Error en API:', data.error);
                        return { results: [] };
                    }

                    return {
                        results: data.results || []
                    };
                },
                cache: true
            },
            tags: true, // IMPORTANTE: Permite ingresar valores personalizados
            placeholder: 'Busca o escribe el modelo del equipo',
            allowClear: true,
            minimumInputLength: 0, // Mostrar opciones inmediatamente al hacer clic
            theme: 'bootstrap-5', // Usar tema de Bootstrap 5
            language: {
                noResults: () => {
                    return 'No hay modelos registrados. Escribe para ingresar uno nuevo.';
                },
                searching: () => {
                    return 'Buscando modelos...';
                },
                inputTooShort: () => {
                    return 'Selecciona una marca primero';
                },
                errorLoading: () => {
                    return 'Error al cargar los resultados';
                }
            },
            // Personalizar cómo se muestra cada resultado en el dropdown
            templateResult: (result: ModeloSearchResult) => {
                if (!result.id) {
                    return result.text; // Mostrar "Buscando..." o "No hay resultados"
                }

                // Mostrar solo el nombre del modelo (sin gama)
                return result.id;
            },
            // Personalizar cómo se muestra la selección
            templateSelection: (selection: ModeloSearchResult) => {
                return selection.text || selection.id;
            }
        };

        // Aplicar Select2 al elemento
        this.modeloSelect.select2(config);

        // Reinicializar cursor personalizado para elementos de Select2
        this.reinicializarCursorPersonalizado();

        console.log('Select2 inicializado en campo modelo');
    }

    /**
     * Reinicializar cursor personalizado para elementos de Select2
     */
    private reinicializarCursorPersonalizado(): void {
        const cursor = document.getElementById('tech-cursor');
        if (!cursor) return;

        // Esperar un momento para que Select2 genere sus elementos en el DOM
        setTimeout(() => {
            const select2Elements = document.querySelectorAll('.select2-container, .select2-selection, .select2-dropdown');
            
            select2Elements.forEach((el: Element) => {
                el.addEventListener('mouseenter', () => {
                    cursor.classList.add('hover-active');
                });

                el.addEventListener('mouseleave', () => {
                    cursor.classList.remove('hover-active');
                });
            });

            console.log('Cursor personalizado reinicializado para Select2');
        }, 100);
    }

    /**
     * Configurar event listeners
     */
    private setupEventListeners(): void {
        if (!this.marcaSelect || !this.modeloSelect) return;

        // Cuando cambia la marca, limpiar el campo modelo
        this.marcaSelect.on('change', () => {
            this.onMarcaChange();
        });

        // Cuando se abre el Select2, verificar que haya marca seleccionada
        this.modeloSelect.on('select2:opening', (e: any) => {
            if (!this.marcaSelect?.val()) {
                e.preventDefault();
                this.showMarcaWarning();
            }
        });

        console.log('Event listeners configurados');
    }

    /**
     * Manejar el cambio de marca
     */
    private onMarcaChange(): void {
        if (!this.modeloSelect || !this.marcaSelect) return;

        // Limpiar la selección del modelo
        this.modeloSelect.val(null).trigger('change');

        // Cerrar el dropdown si está abierto
        this.modeloSelect.select2('close');

        console.log('Marca cambiada - Campo modelo reiniciado');
    }

    /**
     * Mostrar advertencia cuando no hay marca seleccionada
     */
    private showMarcaWarning(): void {
        if (!this.modeloSelect) return;
        
        // Buscar el contenedor del campo modelo para mostrar mensaje
        const $container = this.modeloSelect.closest('.mb-3');
        
        if ($container) {
            // Verificar si ya existe un mensaje de advertencia
            let $warning = $container.find('.marca-warning');
            
            if ($warning.length === 0) {
                // Crear mensaje de advertencia
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

        console.log('Advertencia mostrada: Seleccionar marca primero');
    }
}

/**
 * ============================================================================
 * INICIALIZACIÓN AUTOMÁTICA
 * ============================================================================
 * Crear instancia cuando se carga el script
 */
const modeloAutocomplete = new ModeloAutocomplete();

/**
 * ============================================================================
 * EXPORTAR PARA USO EXTERNO (si se necesita)
 * ============================================================================
 */
// @ts-ignore - Agregar al objeto window para acceso global
window.ModeloAutocomplete = ModeloAutocomplete;
