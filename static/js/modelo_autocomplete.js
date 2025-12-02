"use strict";
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
 * ============================================================================
 * CLASE PRINCIPAL: ModeloAutocomplete
 * ============================================================================
 */
class ModeloAutocomplete {
    /**
     * Constructor - Inicializa la funcionalidad
     */
    constructor() {
        this.modeloSelect = null;
        this.marcaSelect = null;
        this.apiUrl = '';
        // Esperar a que el DOM esté completamente cargado
        $(document).ready(() => {
            this.init();
        });
    }
    /**
     * Inicializar la funcionalidad de autocompletado
     */
    init() {
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
    initializeSelect2() {
        if (!this.modeloSelect || !this.marcaSelect)
            return;
        const config = {
            ajax: {
                url: this.apiUrl,
                dataType: 'json',
                delay: 300, // Esperar 300ms después de que el usuario deje de escribir
                data: (params) => {
                    var _a;
                    const marcaSeleccionada = (_a = this.marcaSelect) === null || _a === void 0 ? void 0 : _a.val();
                    return {
                        marca: marcaSeleccionada,
                        q: params.term // Término de búsqueda ingresado por el usuario
                    };
                },
                processResults: (data) => {
                    var _a, _b;
                    // Verificar si hay error en la respuesta
                    if (data.error) {
                        console.error('Error en API:', data.error);
                        return { results: [] };
                    }
                    // Log de resultados para debugging (solo en desarrollo)
                    if (data.results && data.results.length > 0) {
                        const marca = (_a = this.marcaSelect) === null || _a === void 0 ? void 0 : _a.val();
                        console.log(`✅ ${data.results.length} modelos encontrados para marca: ${marca}`);
                    }
                    else {
                        const marca = (_b = this.marcaSelect) === null || _b === void 0 ? void 0 : _b.val();
                        console.log(`ℹ️ No hay modelos registrados para marca: ${marca}`);
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
            templateResult: (result) => {
                if (!result.id) {
                    return result.text; // Mostrar "Buscando..." o "No hay resultados"
                }
                // Crear elemento HTML con badge de gama
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
                // Si no hay gama, mostrar solo el nombre
                return result.id;
            },
            // Personalizar cómo se muestra la selección
            templateSelection: (selection) => {
                return selection.text || selection.id;
            }
        };
        // Aplicar Select2 al elemento
        this.modeloSelect.select2(config);
        // Manejar errores de AJAX
        this.modeloSelect.on('select2:error', (e) => {
            console.error('Error en Select2 AJAX:', e.params.jqXHR.responseText);
            this.showErrorNotification('Error al cargar modelos. Verifica tu conexión.');
        });
        // Reinicializar cursor personalizado para elementos de Select2
        this.reinicializarCursorPersonalizado();
        console.log('Select2 inicializado en campo modelo');
    }
    /**
     * Reinicializar cursor personalizado para elementos de Select2
     */
    reinicializarCursorPersonalizado() {
        const cursor = document.getElementById('tech-cursor');
        if (!cursor)
            return;
        // Esperar un momento para que Select2 genere sus elementos en el DOM
        setTimeout(() => {
            const select2Elements = document.querySelectorAll('.select2-container, .select2-selection, .select2-dropdown');
            select2Elements.forEach((el) => {
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
    setupEventListeners() {
        if (!this.marcaSelect || !this.modeloSelect)
            return;
        // Cuando cambia la marca, limpiar el campo modelo
        this.marcaSelect.on('change', () => {
            this.onMarcaChange();
        });
        // Cuando se abre el Select2, verificar que haya marca seleccionada
        this.modeloSelect.on('select2:opening', (e) => {
            var _a;
            if (!((_a = this.marcaSelect) === null || _a === void 0 ? void 0 : _a.val())) {
                e.preventDefault();
                this.showMarcaWarning();
            }
        });
        console.log('Event listeners configurados');
    }
    /**
     * Manejar el cambio de marca
     */
    onMarcaChange() {
        if (!this.modeloSelect || !this.marcaSelect)
            return;
        // Limpiar la selección del modelo
        this.modeloSelect.val(null).trigger('change');
        // Cerrar el dropdown si está abierto
        this.modeloSelect.select2('close');
        console.log('Marca cambiada - Campo modelo reiniciado');
    }
    /**
     * Mostrar advertencia cuando no hay marca seleccionada
     */
    showMarcaWarning() {
        if (!this.modeloSelect)
            return;
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
    /**
     * Mostrar notificación de error
     */
    showErrorNotification(mensaje) {
        if (!this.modeloSelect)
            return;
        const $container = this.modeloSelect.closest('.mb-3');
        if ($container) {
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
        console.error('Error mostrado:', mensaje);
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
//# sourceMappingURL=modelo_autocomplete.js.map