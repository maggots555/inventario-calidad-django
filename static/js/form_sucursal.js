"use strict";
/**
 * form_sucursal.ts
 * ================
 *
 * Objetivo de negocio:
 *   Ayudas mínimas del formulario de sucursal (alta / edición).
 *
 * Argumentos / entrada:
 *   Formulario #sucursalForm con data-campo-codigo (id del input código).
 *
 * Efectos secundarios:
 *   Pone el código en mayúsculas mientras se escribe. No llama APIs ni
 *   genera códigos: si el campo queda vacío, el modelo Django crea SUC001…
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 * Antes este archivo era un <script> enorme dentro del HTML: inventaba un
 * código aleatorio (chocaba con el del modelo), capitalizaba cada palabra
 * al vuelo y pedía confirm() al guardar. Eso se siente “viejo” y estorba.
 * Aquí solo queda lo útil.
 */
(function formSucursalMain() {
    /**
     * Convierte el código a mayúsculas (SUC001, MTY, etc.).
     */
    function initCodigoMayusculas() {
        const form = document.getElementById('sucursalForm');
        if (!form) {
            return;
        }
        const idCodigo = form.dataset.campoCodigo;
        if (!idCodigo) {
            return;
        }
        const codigo = document.getElementById(idCodigo);
        if (!(codigo instanceof HTMLInputElement)) {
            return;
        }
        // EXPLICACIÓN: el modelo compara códigos únicos; unificar mayúsculas
        // evita duplicados tipo "suc001" vs "SUC001".
        codigo.addEventListener('input', () => {
            // Guardamos el cursor para que toUpperCase no lo mande al final.
            const inicio = codigo.selectionStart;
            const fin = codigo.selectionEnd;
            codigo.value = codigo.value.toUpperCase();
            if (inicio !== null && fin !== null) {
                codigo.setSelectionRange(inicio, fin);
            }
        });
    }
    document.addEventListener('DOMContentLoaded', () => {
        initCodigoMayusculas();
    });
})();
//# sourceMappingURL=form_sucursal.js.map