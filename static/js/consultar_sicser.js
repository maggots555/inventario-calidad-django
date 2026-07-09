"use strict";
/**
 * Consultar SICSER — copia la sucursal elegida a los formularios de importación.
 *
 * Objetivo: al importar una orden desde SICSER, enviar la sucursal SIGMA
 * seleccionada en el filtro superior (o dejar vacío para asignación automática por CIS).
 */
function inicializarImportacionSicser() {
    const selectorSucursal = document.querySelector('#sicser-sucursal-import');
    const formularios = document.querySelectorAll('form.sicser-import-form');
    formularios.forEach((formulario) => {
        formulario.addEventListener('submit', () => {
            const campoOculto = formulario.querySelector('.js-sicser-sucursal');
            if (campoOculto && selectorSucursal) {
                campoOculto.value = selectorSucursal.value;
            }
        });
    });
}
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarImportacionSicser);
}
else {
    inicializarImportacionSicser();
}
//# sourceMappingURL=consultar_sicser.js.map