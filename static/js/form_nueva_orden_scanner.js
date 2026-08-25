"use strict";
/**
 * Scanner QR / Data Matrix en formularios de crear orden (OOW y Venta Mostrador FL).
 *
 * Objetivo de negocio:
 * Permitir escanear número de serie del equipo y del cargador al registrar
 * una orden nueva, sin escribir manualmente.
 *
 * Dependencias:
 * - scanner_enlace.ts → window.enlazarScannerBoton
 * - scanner_codigo.js → window.abrirScannerCodigo
 *
 * Nota: OOW y FL comparten los mismos IDs de input; un solo init sirve para ambos.
 */
/**
 * Enlaza botones de cámara en form_nueva_orden.html y form_nueva_orden_venta_mostrador.html.
 */
function inicializarScannerFormNuevaOrden() {
    const enlazar = window.enlazarScannerBoton;
    if (!enlazar) {
        return;
    }
    enlazar('btnEscanearNumeroSerieCrear', 'id_numero_serie', 'Escanear número de serie del equipo');
    enlazar('btnEscanearCargadorCrear', 'id_numero_serie_cargador', 'Escanear número de serie del cargador', {
        id: 'id_tiene_cargador',
        mensaje: 'Marca la casilla "¿Incluye cargador?" para poder escanear el número.',
    }, 'barras');
}
document.addEventListener('DOMContentLoaded', () => {
    inicializarScannerFormNuevaOrden();
});
//# sourceMappingURL=form_nueva_orden_scanner.js.map