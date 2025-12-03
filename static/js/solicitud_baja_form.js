"use strict";
/* =============================================================================
   SOLICITUD BAJA FORM - TypeScript para el formulario de Solicitud de Baja
   
   EXPLICACIÓN PARA PRINCIPIANTES:
   --------------------------------
   Este archivo TypeScript maneja la lógica dinámica del formulario de solicitud
   de baja del almacén. Específicamente:
   
   1. Carga dinámica de unidades: Cuando seleccionas un producto, se cargan las
      unidades disponibles de ese producto vía AJAX.
   
   2. Mostrar/ocultar campo de técnico: Cuando seleccionas "Servicio Técnico"
      como tipo de solicitud, aparece el campo para seleccionar el técnico.
      Este campo es obligatorio solo para ese tipo de solicitud.
   
   FLUJO:
   - Usuario selecciona tipo de solicitud
   - Si es "servicio_tecnico" → Muestra selector de técnico (obligatorio)
   - Si es otro tipo → Oculta selector de técnico
   
   - Usuario selecciona producto
   - Se hace petición AJAX para obtener unidades disponibles
   - Se actualiza el dropdown de unidades
   ============================================================================= */
/**
 * Clase principal que maneja el formulario de solicitud de baja
 *
 * EXPLICACIÓN: Usamos una clase para organizar todo el código relacionado
 * con el formulario. Esto hace el código más limpio y fácil de mantener.
 */
class SolicitudBajaFormHandler {
    constructor(apiUnidadesUrl, apiTecnicosUrl) {
        var _a;
        // Guardar URLs de los APIs
        this.apiUnidadesUrl = apiUnidadesUrl;
        this.apiTecnicosUrl = apiTecnicosUrl;
        // Obtener referencias a los elementos del DOM
        this.tipoSolicitudSelect = document.getElementById('id_tipo_solicitud');
        this.productoSelect = document.getElementById('id_producto');
        this.unidadSelect = document.getElementById('id_unidad_inventario');
        this.tecnicoSelect = document.getElementById('id_tecnico_asignado');
        this.unidadContainer = document.getElementById('unidad-container');
        this.tecnicoContainer = document.getElementById('tecnico-container');
        this.stockInfo = document.getElementById('stock-info');
        // Inicializar eventos
        this.initEventListeners();
        // Configuración inicial basada en valores actuales
        this.handleTipoSolicitudChange();
        if ((_a = this.productoSelect) === null || _a === void 0 ? void 0 : _a.value) {
            this.handleProductoChange();
        }
    }
    /**
     * Inicializa los event listeners para los campos del formulario
     */
    initEventListeners() {
        // Evento: Cambio en tipo de solicitud
        if (this.tipoSolicitudSelect) {
            this.tipoSolicitudSelect.addEventListener('change', () => {
                this.handleTipoSolicitudChange();
            });
        }
        // Evento: Cambio en producto
        if (this.productoSelect) {
            this.productoSelect.addEventListener('change', () => {
                this.handleProductoChange();
            });
        }
    }
    /**
     * Maneja el cambio en el tipo de solicitud
     *
     * LÓGICA:
     * - Si tipo_solicitud === 'servicio_tecnico' → Mostrar campo técnico
     * - Cualquier otro valor → Ocultar campo técnico y limpiar selección
     */
    handleTipoSolicitudChange() {
        var _a;
        if (!this.tipoSolicitudSelect || !this.tecnicoContainer || !this.tecnicoSelect) {
            return;
        }
        const tipoSolicitud = this.tipoSolicitudSelect.value;
        if (tipoSolicitud === 'servicio_tecnico') {
            // Mostrar campo de técnico
            this.tecnicoContainer.style.display = 'block';
            // Agregar indicador visual de requerido
            this.tecnicoSelect.setAttribute('required', 'required');
            // Actualizar label para mostrar que es obligatorio
            const label = this.tecnicoContainer.querySelector('label');
            if (label && !((_a = label.textContent) === null || _a === void 0 ? void 0 : _a.includes('*'))) {
                label.innerHTML = '<i class="bi bi-person-gear me-1"></i>Técnico de Laboratorio *';
            }
        }
        else {
            // Ocultar campo de técnico
            this.tecnicoContainer.style.display = 'none';
            // Limpiar selección
            this.tecnicoSelect.value = '';
            // Remover requerido
            this.tecnicoSelect.removeAttribute('required');
        }
    }
    /**
     * Maneja el cambio en la selección de producto
     * Carga las unidades disponibles vía AJAX
     */
    handleProductoChange() {
        if (!this.productoSelect || !this.unidadSelect || !this.unidadContainer) {
            return;
        }
        const productoId = this.productoSelect.value;
        // Mostrar estado de carga
        this.unidadSelect.innerHTML = '<option value="">-- Cargando unidades... --</option>';
        if (!productoId) {
            this.unidadSelect.innerHTML = '<option value="">-- Seleccione un producto primero --</option>';
            this.unidadContainer.style.display = 'none';
            if (this.stockInfo) {
                this.stockInfo.textContent = '';
            }
            return;
        }
        // Hacer petición AJAX para obtener unidades
        fetch(`${this.apiUnidadesUrl}?producto_id=${productoId}`)
            .then(response => response.json())
            .then((data) => {
            this.processUnidadesResponse(data);
        })
            .catch(error => {
            console.error('Error cargando unidades:', error);
            this.unidadSelect.innerHTML = '<option value="">-- Error al cargar unidades --</option>';
        });
    }
    /**
     * Procesa la respuesta del API de unidades
     */
    processUnidadesResponse(data) {
        if (!this.unidadSelect || !this.unidadContainer) {
            return;
        }
        // Mostrar info de stock
        if (this.stockInfo && data.stock_info) {
            this.stockInfo.innerHTML = `<span class="text-success"><i class="bi bi-box-seam me-1"></i>${data.stock_info}</span>`;
        }
        // Limpiar y agregar opción por defecto
        this.unidadSelect.innerHTML = '<option value="">-- Cualquier unidad disponible --</option>';
        // Agregar unidades si existen
        if (data.unidades && data.unidades.length > 0) {
            data.unidades.forEach((unidad) => {
                const option = document.createElement('option');
                option.value = unidad.id.toString();
                // Formato: "Samsung 870 EVO - S/N: ABC123 (Nuevo)"
                let texto = '';
                if (unidad.marca)
                    texto += unidad.marca;
                if (unidad.modelo)
                    texto += ' ' + unidad.modelo;
                if (unidad.numero_serie)
                    texto += ' - S/N: ' + unidad.numero_serie;
                texto += ' (' + unidad.estado_display + ')';
                option.textContent = texto.trim() || `Unidad #${unidad.id}`;
                this.unidadSelect.appendChild(option);
            });
            this.unidadContainer.style.display = 'block';
        }
        else {
            this.unidadSelect.innerHTML = '<option value="">-- No hay unidades registradas --</option>';
            this.unidadContainer.style.display = 'block';
        }
    }
}
/**
 * Función de inicialización que se llama desde el template
 *
 * EXPLICACIÓN:
 * Esta función se exporta para que el template pueda llamarla con las URLs
 * de los APIs como parámetros. Esto permite que Django genere las URLs
 * correctamente usando {% url 'nombre_url' %}.
 *
 * @param apiUnidadesUrl - URL del API para obtener unidades de un producto
 * @param apiTecnicosUrl - URL del API para obtener técnicos disponibles
 */
function initSolicitudBajaForm(apiUnidadesUrl, apiTecnicosUrl) {
    document.addEventListener('DOMContentLoaded', function () {
        solicitudBajaHandler = new SolicitudBajaFormHandler(apiUnidadesUrl, apiTecnicosUrl);
    });
}
// Exportar función al scope global para que el template pueda usarla
window.initSolicitudBajaForm = initSolicitudBajaForm;
//# sourceMappingURL=solicitud_baja_form.js.map