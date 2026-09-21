"use strict";
/**
 * detalle_orden_pago_diagnostico.ts — autollenado del cobro de diagnóstico.
 *
 * Objetivo de negocio:
 *     El diagnóstico se guarda SIN IVA ($570), pero el cliente entrega en caja
 *     el total CON IVA ($661.20). Al elegir el saldo "Diagnóstico", el monto
 *     se llena solo y el tipo queda en "Pago en una sola exhibición": ese
 *     saldo siempre es PUE y no se captura como anticipo.
 *
 * EXPLICACIÓN PARA PRINCIPIANTES:
 *     Los importes NO se calculan aquí. Llegan ya resueltos desde el servidor
 *     en atributos data- del formulario, porque el dinero se calcula en un solo
 *     lugar (services/pagos_diagnostico.py). Si multiplicáramos por 1.16 en el
 *     navegador tendríamos dos fuentes de verdad.
 *
 * Efectos secundarios:
 *     Modifica el valor del input de monto, habilita o deshabilita opciones
 *     del tipo de pago y muestra u oculta un texto de ayuda.
 *     Si la reparación ya tiene un anticipo, "Pago en una sola exhibición"
 *     queda apagado. Si ya se cobró de contado, "Anticipo" queda apagado.
 */
(function detalleOrdenPagoDiagnosticoMain() {
    const SALDO_DIAGNOSTICO = 'diagnostico';
    const TIPO_CONTADO = 'pago_completo';
    const TIPO_ANTICIPO = 'anticipo';
    document.addEventListener('DOMContentLoaded', function () {
        const formulario = document.getElementById('formRegistrarPago');
        if (!(formulario instanceof HTMLFormElement)) {
            return;
        }
        const posibleSaldo = formulario.querySelector('[name="saldo_a_cubrir"]');
        const posibleTipo = formulario.querySelector('[name="tipo"]');
        const posibleMonto = formulario.querySelector('[name="monto"]');
        if (!(posibleSaldo instanceof HTMLSelectElement)) {
            return;
        }
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
        const selectSaldo = posibleSaldo;
        const selectTipo = posibleTipo;
        const inputMonto = posibleMonto;
        const opcionAnticipo = selectTipo.querySelector('option[value="' + TIPO_ANTICIPO + '"]');
        const opcionContado = selectTipo.querySelector('option[value="' + TIPO_CONTADO + '"]');
        // Familia ya guardada en la reparación: 'anticipo', 'pago_completo' o ''.
        const familiaReparacion = formulario.dataset.familiaReparacion || '';
        // Saldo pendiente del diagnóstico, ya con IVA, calculado en el servidor.
        const saldoDiagnostico = formulario.dataset.saldoDiagnostico || '';
        const montoSinIva = formulario.dataset.diagnosticoSinIva || '';
        const ivaDiagnostico = formulario.dataset.diagnosticoIva || '';
        // Texto de ayuda: se crea una sola vez y se reutiliza.
        const ayuda = document.createElement('div');
        ayuda.className = 'form-text text-info d-none';
        ayuda.id = 'ayudaMontoDiagnostico';
        inputMonto.insertAdjacentElement('afterend', ayuda);
        // Aviso junto al tipo de pago cuando la familia de la reparación ya está fija.
        const ayudaFamilia = document.createElement('div');
        ayudaFamilia.className = 'form-text d-none';
        ayudaFamilia.id = 'ayudaFamiliaReparacion';
        selectTipo.insertAdjacentElement('afterend', ayudaFamilia);
        /**
         * Recuerda qué valor pusimos nosotros para no pisar lo que teclee
         * la persona. Si ella escribe otra cantidad, se respeta.
         */
        let valorSugerido = '';
        function limpiarSugerencia() {
            // Paso: solo borramos si el contenido sigue siendo el nuestro.
            if (valorSugerido !== '' && inputMonto.value === valorSugerido) {
                inputMonto.value = '';
            }
            valorSugerido = '';
            ayuda.classList.add('d-none');
            ayuda.textContent = '';
        }
        function aplicarSugerenciaDiagnostico() {
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
                        ' = $' + saldo.toFixed(2) + '. El diagnóstico siempre es pago en una sola exhibición.';
            }
            else {
                ayuda.textContent = 'Monto con IVA incluido: $' + saldo.toFixed(2) + '.';
            }
        }
        function ponerOpcion(opcion, apagada) {
            if (opcion instanceof HTMLOptionElement) {
                opcion.disabled = apagada;
            }
        }
        function ocultarAyudaFamilia() {
            ayudaFamilia.classList.add('d-none');
            ayudaFamilia.textContent = '';
        }
        function fijarTipoDiagnostico() {
            // Paso: Anticipo no aplica a este saldo. El de contado sí, aunque
            // la reparación ya vaya por anticipos: son bolsillos distintos.
            ponerOpcion(opcionContado, false);
            ponerOpcion(opcionAnticipo, true);
            selectTipo.value = TIPO_CONTADO;
            ocultarAyudaFamilia();
        }
        function aplicarFamiliaReparacion() {
            // Paso: el primer abono ya eligió. El otro tipo se apaga para que
            // no se pueda mezclar anticipo con pago en una sola exhibición.
            const bloqueaContado = familiaReparacion === TIPO_ANTICIPO;
            const bloqueaAnticipo = familiaReparacion === TIPO_CONTADO;
            ponerOpcion(opcionContado, bloqueaContado);
            ponerOpcion(opcionAnticipo, bloqueaAnticipo);
            if (bloqueaContado) {
                selectTipo.value = TIPO_ANTICIPO;
                ayudaFamilia.textContent =
                    'Esta reparación ya tiene un anticipo. El resto se registra igual, como Anticipo.';
                ayudaFamilia.classList.remove('d-none');
                return;
            }
            if (bloqueaAnticipo) {
                selectTipo.value = TIPO_CONTADO;
                ayudaFamilia.textContent =
                    'Esta reparación ya se está cobrando en una sola exhibición.';
                ayudaFamilia.classList.remove('d-none');
                return;
            }
            ocultarAyudaFamilia();
        }
        function alCambiarSaldo() {
            if (selectSaldo.value === SALDO_DIAGNOSTICO) {
                fijarTipoDiagnostico();
                aplicarSugerenciaDiagnostico();
                return;
            }
            aplicarFamiliaReparacion();
            limpiarSugerencia();
        }
        selectSaldo.addEventListener('change', alCambiarSaldo);
        // Paso: si el formulario se repinta con el saldo ya seleccionado
        // (por ejemplo tras un error de validación), aplicamos la ayuda.
        if (selectSaldo.value === SALDO_DIAGNOSTICO) {
            alCambiarSaldo();
        }
    });
})();
//# sourceMappingURL=detalle_orden_pago_diagnostico.js.map