"use strict";
/**
 * Scanner QR / Data Matrix en modal "Editar Información del Equipo".
 *
 * Objetivo de negocio:
 * Reutilizar scanner_codigo.ts para capturar número de serie del equipo
 * y del cargador sin salir del detalle de orden.
 *
 * Dependencias:
 * - scanner_enlace.ts expone window.enlazarScannerBoton
 * - scanner_codigo.js expone window.abrirScannerCodigo
 */
/**
 * Inicializa los botones de scanner del modal editar info equipo.
 * Solo corre si los elementos existen en la página (detalle_orden).
 */
function inicializarScannerModalEditarEquipo() {
    const enlazar = window.enlazarScannerBoton;
    if (!enlazar) {
        return;
    }
    enlazar('btnEscanearNumeroSerieModal', 'id_numero_serie', 'Escanear número de serie del equipo');
    enlazar('btnEscanearCargadorModal', 'id_numero_serie_cargador_modal', 'Escanear número de serie del cargador', {
        id: 'id_tiene_cargador_modal',
        mensaje: 'Marca la casilla "Tiene cargador" para poder escanear el número.',
    }, 'barras');
}
document.addEventListener('DOMContentLoaded', () => {
    inicializarScannerModalEditarEquipo();
});
//# sourceMappingURL=detalle_orden_scanner.js.map