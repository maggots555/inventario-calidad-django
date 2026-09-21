"""
El diagnóstico se cobra con IVA aunque se guarde sin IVA.

EXPLICACIÓN PARA PRINCIPIANTES — el problema que resuelven estos tests:
--------------------------------------------------------------------
`costo_mano_obra` siempre está SIN IVA ($570), porque es lo que el CFDI pide:
el SAT quiere el valor del servicio antes de impuestos. Pero en caja el cliente
entrega $661.20, y su comprobante de transferencia dirá $661.20.

Antes esas dos cifras chocaban: SIGMA validaba el pago contra $570 y rechazaba
el cobro real. La salida fácil habría sido capturar $570 "para que dejara
guardar", pero entonces el registro de SIGMA no cuadraría con el banco y a
Facturación le faltarían $91.20 sin explicación.

La regla que verifican estos tests: los pagos guardan DINERO REAL (con IVA);
el CFDI desglosa ese mismo dinero (sin IVA + IVA). Una sola cifra, dos lecturas.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, OrdenServicio, PagoOrden
from servicio_tecnico.services.diagnostico_catalogo import (
    aplicar_perfil_diagnostico,
)
from servicio_tecnico.services.pagos_diagnostico import resumen_diagnostico
from servicio_tecnico.services.pagos_orden import (
    registrar_pago,
    validar_pago_en_cuenta,
)
from servicio_tecnico.tests.helpers_tarifario import sembrar_tarifario


class BaseCobroDiagnosticoTest(TestCase):
    """Orden con diagnóstico Estándar ($570 sin IVA) ya aplicado."""

    def setUp(self):
        sembrar_tarifario()
        self.sucursal = Sucursal.objects.create(
            nombre='Satelite',
            ciudad='CDMX',
            prefijo_facturacion='SAT',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Cajero IVA',
            cargo='Recepcionista',
            area='FRONTDESK',
            email='cajero.iva@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='reparacion',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-77001',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-IVA-77001',
            falla_principal='No enciende',
            gama='media',
        )
        self.orden.refresh_from_db()
        aplicar_perfil_diagnostico(self.orden, 'estandar')
        self.orden.refresh_from_db()


class DesgloseDelDiagnosticoTest(BaseCobroDiagnosticoTest):
    """La cifra que se muestra arriba, en Cobros y facturación."""

    def test_resumen_desglosa_servicio_iva_y_total(self):
        """$570 de servicio + $91.20 de IVA = $661.20 a cobrar."""
        resumen = resumen_diagnostico(self.orden, codigo_pais='MX')

        self.assertEqual(resumen.monto, Decimal('570.00'))
        self.assertEqual(resumen.iva, Decimal('91.20'))
        self.assertEqual(resumen.monto_con_iva, Decimal('661.20'))

    def test_saldo_inicial_es_el_total_con_iva(self):
        """Sin abonos, falta por cubrir el total con impuesto, no el neto."""
        resumen = resumen_diagnostico(self.orden, codigo_pais='MX')

        self.assertEqual(resumen.pagado, Decimal('0.00'))
        self.assertEqual(resumen.saldo, Decimal('661.20'))
        self.assertFalse(resumen.cubierto_100)

    def test_fuera_de_mexico_no_hay_iva(self):
        """
        El 16% es de México. En otro país el total a cubrir es el neto.

        Si esta regla no existiera, Argentina cobraría un impuesto mexicano.
        """
        resumen = resumen_diagnostico(self.orden, codigo_pais='AR')

        self.assertEqual(resumen.iva, Decimal('0.00'))
        self.assertEqual(resumen.monto_con_iva, Decimal('570.00'))
        self.assertEqual(resumen.saldo, Decimal('570.00'))

    def test_sin_diagnostico_capturado_no_hay_nada_que_cobrar(self):
        """Orden sin perfil elegido: todo en cero y sin IVA inventado."""
        otra = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
        )
        resumen = resumen_diagnostico(otra, codigo_pais='MX')

        self.assertEqual(resumen.monto, Decimal('0.00'))
        self.assertEqual(resumen.iva, Decimal('0.00'))
        self.assertEqual(resumen.monto_con_iva, Decimal('0.00'))
        self.assertFalse(resumen.cubierto_100)


class RegistrarCobroDiagnosticoTest(BaseCobroDiagnosticoTest):
    """El cobro en caja: lo que antes era imposible de guardar."""

    def test_se_puede_cobrar_el_monto_con_iva(self):
        """
        Regresión: $661.20 es el cobro correcto y debe guardarse.

        Este es exactamente el caso que fallaba. El sistema exigía $570 y
        rechazaba el importe que el cliente realmente entregaba.
        """
        pago = registrar_pago(
            orden=self.orden,
            empleado=self.empleado,
            monto=Decimal('661.20'),
            tipo='pago_completo',
            saldo_a_cubrir='diagnostico',
            metodo='transferencia',
            codigo_pais='MX',
        )

        self.assertEqual(pago.monto, Decimal('661.20'))
        resumen = resumen_diagnostico(self.orden, codigo_pais='MX')
        self.assertEqual(resumen.saldo, Decimal('0.00'))
        self.assertTrue(resumen.cubierto_100)

    def test_transferencia_validada_habilita_la_factura(self):
        """
        Una transferencia nace pendiente. El PUE espera a que Finanzas la valide.

        `confirmado_100` es lo que el autofacturador consulta para decidir si
        ya hay algo que timbrar.
        """
        pago = registrar_pago(
            orden=self.orden,
            empleado=self.empleado,
            monto=Decimal('661.20'),
            tipo='pago_completo',
            saldo_a_cubrir='diagnostico',
            metodo='transferencia',
            codigo_pais='MX',
        )
        self.assertFalse(
            resumen_diagnostico(self.orden, codigo_pais='MX').confirmado_100
        )

        validar_pago_en_cuenta(pago, self.empleado, aparece=True)
        resumen = resumen_diagnostico(self.orden, codigo_pais='MX')
        self.assertTrue(resumen.confirmado_100)

    def test_diagnostico_no_se_registra_como_anticipo(self):
        """El diagnóstico siempre es una sola exhibición."""
        with self.assertRaises(ValidationError):
            registrar_pago(
                orden=self.orden,
                empleado=self.empleado,
                monto=Decimal('661.20'),
                tipo='anticipo',
                saldo_a_cubrir='diagnostico',
                metodo='transferencia',
                codigo_pais='MX',
            )

    def test_pagar_solo_el_neto_deja_saldo_del_iva(self):
        """
        Capturar $570 ya no "cubre" el diagnóstico: faltan los $91.20.

        Antes este era el workaround para poder guardar, y dejaba la caja
        descuadrada contra el comprobante del banco.
        """
        registrar_pago(
            orden=self.orden,
            empleado=self.empleado,
            monto=Decimal('570.00'),
            tipo='pago_completo',
            saldo_a_cubrir='diagnostico',
            metodo='transferencia',
            codigo_pais='MX',
        )

        resumen = resumen_diagnostico(self.orden, codigo_pais='MX')
        self.assertEqual(resumen.saldo, Decimal('91.20'))
        self.assertFalse(resumen.cubierto_100)
        self.assertFalse(resumen.confirmado_100)

    def test_cobrar_de_mas_sigue_rechazandose(self):
        """El techo se movió, no desapareció: $700 excede los $661.20."""
        with self.assertRaises(ValidationError):
            registrar_pago(
                orden=self.orden,
                empleado=self.empleado,
                monto=Decimal('700.00'),
                tipo='pago_completo',
                saldo_a_cubrir='diagnostico',
                metodo='transferencia',
                codigo_pais='MX',
            )

        self.assertFalse(PagoOrden.objects.filter(orden=self.orden).exists())

    def test_el_error_explica_el_desglose(self):
        """
        El mensaje debe enseñar el IVA, no solo decir "no cabe".

        Si solo dijera "supera el saldo", quien cobra volvería a intentar con
        el monto sin IVA, que es el error que estamos corrigiendo.
        """
        with self.assertRaises(ValidationError) as ctx:
            registrar_pago(
                orden=self.orden,
                empleado=self.empleado,
                monto=Decimal('700.00'),
                tipo='pago_completo',
                saldo_a_cubrir='diagnostico',
                metodo='transferencia',
                codigo_pais='MX',
            )

        mensaje = ' '.join(ctx.exception.messages)
        self.assertIn('570', mensaje)
        self.assertIn('91.20', mensaje)
        self.assertIn('661.20', mensaje)

    def test_dos_abonos_parciales_suman_el_total(self):
        """Se puede cobrar en dos partes mientras no se pase del total."""
        registrar_pago(
            orden=self.orden,
            empleado=self.empleado,
            monto=Decimal('400.00'),
            tipo='pago_completo',
            saldo_a_cubrir='diagnostico',
            metodo='transferencia',
            codigo_pais='MX',
        )
        registrar_pago(
            orden=self.orden,
            empleado=self.empleado,
            monto=Decimal('261.20'),
            tipo='pago_completo',
            saldo_a_cubrir='diagnostico',
            metodo='transferencia',
            codigo_pais='MX',
        )

        resumen = resumen_diagnostico(self.orden, codigo_pais='MX')
        self.assertEqual(resumen.pagado, Decimal('661.20'))
        self.assertEqual(resumen.saldo, Decimal('0.00'))
        self.assertTrue(resumen.cubierto_100)


class DesgloseEnLaFacturaTest(BaseCobroDiagnosticoTest):
    """El IVA se cobra una vez y se desglosa una vez."""

    def test_la_linea_del_cfdi_va_sin_iva(self):
        """
        Aunque en caja entraron $661.20, el concepto del CFDI es de $570.

        Es la mitad que evita el error clásico: si la línea llevara los
        $661.20, el timbrado le sumaría otro 16% encima.
        """
        from servicio_tecnico.services.facturacion_documentos import (
            calcular_lineas_pue,
        )

        pago = registrar_pago(
            orden=self.orden,
            empleado=self.empleado,
            monto=Decimal('661.20'),
            tipo='pago_completo',
            saldo_a_cubrir='diagnostico',
            metodo='transferencia',
            codigo_pais='MX',
        )
        validar_pago_en_cuenta(pago, self.empleado, aparece=True)

        lineas = calcular_lineas_pue(self.orden)
        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0].importe, Decimal('570.00'))
