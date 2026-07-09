/**
 * Consultar SICSER — copia la sucursal elegida a los formularios de importación.
 *
 * Objetivo: al importar una orden desde SICSER, enviar la sucursal SIGMA
 * seleccionada en el filtro superior (o dejar vacío para asignación automática por CIS).
 */

function inicializarImportacionSicser(): void {
    const selectorSucursal = document.querySelector<HTMLSelectElement>('#sicser-sucursal-import');
    const formularios = document.querySelectorAll<HTMLFormElement>('form.sicser-import-form');

    formularios.forEach((formulario: HTMLFormElement): void => {
        formulario.addEventListener('submit', (): void => {
            const campoOculto = formulario.querySelector<HTMLInputElement>('.js-sicser-sucursal');
            if (campoOculto && selectorSucursal) {
                campoOculto.value = selectorSucursal.value;
            }
        });
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inicializarImportacionSicser);
} else {
    inicializarImportacionSicser();
}
