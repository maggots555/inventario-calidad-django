"use strict";
/**
 * Helper compartido: enlazar botón de cámara con scanner_codigo.ts.
 *
 * Objetivo de negocio:
 * Evitar duplicar la lógica de click → abrirScannerCodigo en detalle_orden,
 * formularios de crear orden, etc.
 *
 * Efectos secundarios:
 * - Registra un listener click en el botón indicado
 * - Al detectar código, escribe en el input y dispara eventos input/change (vía scanner_codigo)
 */
/**
 * Enlaza un botón de cámara con el scanner universal y un input destino.
 *
 * @param btnId - ID del botón que abre la cámara
 * @param inputId - ID del input donde se pegará el código
 * @param tituloModal - Título del modal del scanner
 * @param requiereCheckbox - Si se define, exige que el checkbox esté activo
 */
function enlazarScannerBoton(btnId, inputId, tituloModal, requiereCheckbox) {
    const btn = document.getElementById(btnId);
    const input = document.getElementById(inputId);
    if (!btn || !input) {
        return;
    }
    btn.addEventListener('click', () => {
        // Validar checkbox previo (p. ej. "Tiene cargador")
        if (requiereCheckbox) {
            const checkbox = document.getElementById(requiereCheckbox.id);
            if (!(checkbox === null || checkbox === void 0 ? void 0 : checkbox.checked) || btn.disabled) {
                window.alert(requiereCheckbox.mensaje);
                return;
            }
        }
        if (typeof window.abrirScannerCodigo !== 'function') {
            window.alert('El scanner no está disponible. Recarga la página o escribe el número a mano.');
            return;
        }
        window.abrirScannerCodigo({
            targetInput: input,
            tituloModal,
            onDetect: () => {
                input.focus();
            },
        });
    });
}
window.enlazarScannerBoton = enlazarScannerBoton;
//# sourceMappingURL=scanner_enlace.js.map