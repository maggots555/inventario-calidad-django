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

/** Condición opcional: el scanner solo abre si un checkbox está marcado */
interface RequiereCheckboxScanner {
  id: string;
  mensaje: string;
}

/**
 * Enlaza un botón de cámara con el scanner universal y un input destino.
 *
 * @param btnId - ID del botón que abre la cámara
 * @param inputId - ID del input donde se pegará el código
 * @param tituloModal - Título del modal del scanner
 * @param requiereCheckbox - Si se define, exige que el checkbox esté activo
 */
function enlazarScannerBoton(
  btnId: string,
  inputId: string,
  tituloModal: string,
  requiereCheckbox?: RequiereCheckboxScanner,
  modoInicial?: 'cuadrado' | 'barras',
): void {
  const btn = document.getElementById(btnId) as HTMLButtonElement | null;
  const input = document.getElementById(inputId) as HTMLInputElement | null;

  if (!btn || !input) {
    return;
  }

  btn.addEventListener('click', () => {
    // Validar checkbox previo (p. ej. "Tiene cargador")
    if (requiereCheckbox) {
      const checkbox = document.getElementById(requiereCheckbox.id) as HTMLInputElement | null;
      if (!checkbox?.checked || btn.disabled) {
        window.alert(requiereCheckbox.mensaje);
        return;
      }
    }

    if (typeof window.abrirScannerCodigo !== 'function') {
      window.alert(
        'El scanner no está disponible. Recarga la página o escribe el número a mano.',
      );
      return;
    }

    window.abrirScannerCodigo({
      targetInput: input,
      tituloModal,
      modoInicial,
      onDetect: () => {
        input.focus();
      },
    });
  });
}

window.enlazarScannerBoton = enlazarScannerBoton;
