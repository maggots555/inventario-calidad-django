/**
 * empleado_marcas_garantia.ts
 * ===========================
 *
 * Objetivo de negocio:
 *   En el alta/edición de un empleado, las casillas "Atiende garantías Dell"
 *   y "Atiende garantías Lenovo" solo se muestran si el rol es Dispatcher.
 *
 * Argumentos / entrada:
 *   Select #id_rol. En el formulario de empleados, el bloque
 *   #bloque-marcas-garantia. En el admin de Django, las filas
 *   .field-atiende_garantias_dell y .field-atiende_garantias_lenovo.
 *
 * Efectos secundarios:
 *   Solo muestra u oculta. No apaga las casillas: si cambian el rol y lo
 *   regresan antes de guardar, no se pierde lo marcado. El servidor las
 *   apaga al guardar cuando el rol final no es dispatcher.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Este archivo es la fuente. El navegador no lo lee directo: `pnpm run build`
 * lo convierte en static/js/empleado_marcas_garantia.js.
 */

(function empleadoMarcasGarantiaMain(): void {
    /**
     * Enseña u oculta Dell/Lenovo según el rol elegido.
     */
    function aplicarVisibilidadMarcas(): void {
        const selectRol = document.getElementById('id_rol');
        if (!(selectRol instanceof HTMLSelectElement)) {
            return;
        }

        const bloqueFormulario = document.getElementById('bloque-marcas-garantia');
        const filasAdmin = document.querySelectorAll<HTMLElement>(
            '.field-atiende_garantias_dell, .field-atiende_garantias_lenovo',
        );
        const esDispatcher = selectRol.value === 'dispatcher';

        if (bloqueFormulario) {
            bloqueFormulario.hidden = !esDispatcher;
        }

        filasAdmin.forEach((fila: HTMLElement) => {
            fila.hidden = !esDispatcher;
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        const selectRol = document.getElementById('id_rol');
        if (!(selectRol instanceof HTMLSelectElement)) {
            return;
        }

        selectRol.addEventListener('change', aplicarVisibilidadMarcas);
        aplicarVisibilidadMarcas();
    });
})();
