/**
 * detalle_orden_pago_diagnostico.ts — autollenado del cobro de diagnóstico.
 *
 * Objetivo de negocio:
 *     El diagnóstico se guarda SIN IVA ($570), pero el cliente entrega en caja
 *     el total CON IVA ($661.20). Quien cobra no tiene por qué hacer esa cuenta
 *     de cabeza: al elegir el tipo de pago "Diagnóstico / mano de obra", el
 *     campo de monto se llena solo con lo que falta por cubrir.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 *     Los importes NO se calculan aquí. Llegan ya resueltos desde el servidor
 *     en atributos data- del formulario, porque el dinero se calcula en un solo
 *     lugar (services/pagos_diagnostico.py). Si multiplicáramos por 1.16 en el
 *     navegador tendríamos dos fuentes de verdad, y tarde o temprano una de las
 *     dos quedaría desactualizada (por ejemplo, en un país sin IVA).
 *
 * Efectos secundarios:
 *     Modifica el valor del input de monto y muestra/oculta un texto de ayuda.
 */

(function detalleOrdenPagoDiagnosticoMain(): void {
    const TIPO_DIAGNOSTICO = 'diagnostico';

    document.addEventListener('DOMContentLoaded', function (): void {
        const formulario = document.getElementById('formRegistrarPago');
        if (!(formulario instanceof HTMLFormElement)) {
            return;
        }

        const posibleTipo = formulario.querySelector('[name="tipo"]');
        const posibleMonto = formulario.querySelector('[name="monto"]');
        if (!(posibleTipo instanceof HTMLSelectElement)) {
            return;
        }
        if (!(posibleMonto instanceof HTMLInputElement)) {
            return;
        }

        // EXPLICACIÓN PARA PRINCIPIANTES:
        // Reasignamos a constantes con tipo explícito porque TypeScript no
        // conserva el resultado del `instanceof` dentro de las funciones de
        // más abajo (se ejecutan después, cuando ya no puede garantizarlo).
        const selectTipo: HTMLSelectElement = posibleTipo;
        const inputMonto: HTMLInputElement = posibleMonto;

        // Saldo pendiente del diagnóstico, ya con IVA, calculado en el servidor.
        const saldoDiagnostico = formulario.dataset.saldoDiagnostico || '';
        const montoSinIva = formulario.dataset.diagnosticoSinIva || '';
        const ivaDiagnostico = formulario.dataset.diagnosticoIva || '';

        // Texto de ayuda: se crea una sola vez y se reutiliza.
        const ayuda = document.createElement('div');
        ayuda.className = 'form-text text-info d-none';
        ayuda.id = 'ayudaMontoDiagnostico';
        inputMonto.insertAdjacentElement('afterend', ayuda);

        /**
         * Recuerda qué valor pusimos nosotros para no pisar lo que teclee
         * la persona. Si ella escribe otra cantidad, se respeta.
         */
        let valorSugerido = '';

        function limpiarSugerencia(): void {
            // Paso: solo borramos si el contenido sigue siendo el nuestro.
            if (valorSugerido !== '' && inputMonto.value === valorSugerido) {
                inputMonto.value = '';
            }
            valorSugerido = '';
            ayuda.classList.add('d-none');
            ayuda.textContent = '';
        }

        function aplicarSugerenciaDiagnostico(): void {
            const saldo = parseFloat(saldoDiagnostico);

            // Paso: sin saldo pendiente no hay nada que sugerir. Puede pasar si
            // el diagnóstico ya está cubierto o si la orden aún no tiene uno.
            if (!isFinite(saldo) || saldo <= 0) {
                ayuda.textContent =
                    'Este diagnóstico ya está cubierto. Verifica antes de registrar otro cobro.';
                ayuda.classList.remove('d-none', 'text-info');
                ayuda.classList.add('text-warning');
                return;
            }

            // Paso: llenamos el campo solo si está vacío o si trae una
            // sugerencia previa nuestra; nunca sobre algo escrito a mano.
            const vacio = inputMonto.value.trim() === '';
            const esSugerenciaPrevia = valorSugerido !== '' && inputMonto.value === valorSugerido;
            if (vacio || esSugerenciaPrevia) {
                valorSugerido = saldo.toFixed(2);
                inputMonto.value = valorSugerido;
            }

            // Paso: explicamos de dónde sale el número para que quien cobra
            // pueda verificarlo contra el comprobante del cliente.
            ayuda.classList.remove('d-none', 'text-warning');
            ayuda.classList.add('text-info');
            if (montoSinIva !== '' && ivaDiagnostico !== '') {
                ayuda.textContent =
                    'Incluye IVA: $' + montoSinIva + ' + $' + ivaDiagnostico +
                    ' = $' + saldo.toFixed(2) + '. Es lo que el cliente paga en caja.';
            } else {
                ayuda.textContent = 'Monto con IVA incluido: $' + saldo.toFixed(2) + '.';
            }
        }

        function alCambiarTipo(): void {
            if (selectTipo.value === TIPO_DIAGNOSTICO) {
                aplicarSugerenciaDiagnostico();
            } else {
                limpiarSugerencia();
            }
        }

        selectTipo.addEventListener('change', alCambiarTipo);

        // Paso: si el formulario se repinta con el tipo ya seleccionado
        // (por ejemplo tras un error de validación), aplicamos la ayuda.
        if (selectTipo.value === TIPO_DIAGNOSTICO) {
            alCambiarTipo();
        }
    });
})();
