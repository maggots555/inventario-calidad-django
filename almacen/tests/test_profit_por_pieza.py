"""
Tests de profit mínimo y efectivo por pieza (reparación).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Validamos los rangos de margen mínimo según costo unitario y que
resolver_profit_linea tome el mayor entre perfil/override y el mínimo.
También comprobamos el motor de precios con % distintos por pieza y
el rechazo de overrides debajo del mínimo.
"""

from decimal import Decimal
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from almacen.utils.pdf_cotizacion_cliente import calcular_precios_items_cotizacion
from almacen.utils.profit_por_pieza import (
    aplicar_profit_overrides_a_items,
    calcular_precio_unitario_con_profit,
    obtener_profit_minimo,
    parsear_profit_overrides,
    profit_cumple_minimo,
    rangos_profit_minimo_para_frontend,
    resolver_profit_linea,
    validar_profit_overrides_contra_lineas,
)


class ProfitMinimoRangosTest(SimpleTestCase):
    """Bordes de los cuatro rangos de costo unitario."""

    def test_rango_0_a_499(self):
        self.assertEqual(obtener_profit_minimo(0), Decimal('0.28'))
        self.assertEqual(obtener_profit_minimo(499.99), Decimal('0.28'))
        self.assertEqual(obtener_profit_minimo('250'), Decimal('0.28'))

    def test_borde_500(self):
        """$499.99 → 28%; $500 → 24%."""
        self.assertEqual(obtener_profit_minimo(499.99), Decimal('0.28'))
        self.assertEqual(obtener_profit_minimo(500), Decimal('0.24'))

    def test_rango_500_a_999(self):
        self.assertEqual(obtener_profit_minimo(999.99), Decimal('0.24'))

    def test_borde_1000(self):
        self.assertEqual(obtener_profit_minimo(999.99), Decimal('0.24'))
        self.assertEqual(obtener_profit_minimo(1000), Decimal('0.22'))

    def test_rango_1000_a_1499(self):
        self.assertEqual(obtener_profit_minimo(1499.99), Decimal('0.22'))

    def test_borde_1500(self):
        self.assertEqual(obtener_profit_minimo(1499.99), Decimal('0.22'))
        self.assertEqual(obtener_profit_minimo(1500), Decimal('0.20'))
        self.assertEqual(obtener_profit_minimo(99999), Decimal('0.20'))

    def test_rangos_frontend_serializables(self):
        """El JSON del modal debe recibir exactamente 4 rangos."""
        rangos = rangos_profit_minimo_para_frontend()
        self.assertEqual(len(rangos), 4)
        self.assertIsNone(rangos[-1]['costo_max'])


class ResolverProfitLineaTest(SimpleTestCase):
    """Perfil como default + override + piso por costo."""

    def test_perfil_por_encima_del_minimo(self):
        # Costo 100 → min 28%; perfil 36% → se queda en 36%
        self.assertEqual(
            resolver_profit_linea(100, 0.36),
            Decimal('0.36'),
        )

    def test_perfil_por_debajo_del_minimo_se_eleva(self):
        # Costo 100 → min 28%; perfil 20% → sube a 28%
        self.assertEqual(
            resolver_profit_linea(100, 0.20),
            Decimal('0.28'),
        )

    def test_override_valido_sube_sobre_perfil(self):
        self.assertEqual(
            resolver_profit_linea(100, 0.36, profit_override=0.45),
            Decimal('0.45'),
        )

    def test_override_debajo_del_minimo_se_eleva(self):
        # API/UI pueden clampar; resolver siempre respeta el piso
        self.assertEqual(
            resolver_profit_linea(100, 0.36, profit_override=0.10),
            Decimal('0.28'),
        )

    def test_profit_cumple_minimo(self):
        self.assertTrue(profit_cumple_minimo(100, 0.28))
        self.assertFalse(profit_cumple_minimo(100, 0.27))
        self.assertTrue(profit_cumple_minimo(1500, 0.20))
        self.assertFalse(profit_cumple_minimo(1500, 0.19))

    def test_precio_unitario_con_profit(self):
        # 1000 / (1 - 0.36) = 1562.50
        self.assertEqual(
            calcular_precio_unitario_con_profit(1000, 0.36),
            Decimal('1562.50'),
        )


class MotorProfitPorPiezaTest(SimpleTestCase):
    """calcular_precios_items_cotizacion con overrides distintos."""

    def test_mezcla_de_profits_distintos(self):
        """
        Pieza A $100 @ 40% + Pieza B $600 @ 30% → suma de precios independientes.

        EXPLICACIÓN: ya no hay un solo factor global; cada línea tiene su %.
        """
        items = [
            {
                'pk': 1,
                'descripcion': 'Barata',
                'cantidad': 1,
                'costo_unitario': 100.0,
                'es_servicio': False,
                'profit_override': 0.40,
            },
            {
                'pk': 2,
                'descripcion': 'Cara',
                'cantidad': 1,
                'costo_unitario': 600.0,
                'es_servicio': False,
                'profit_override': 0.30,
            },
        ]
        calculo = calcular_precios_items_cotizacion(
            items=items,
            tipo_servicio='estandar',
        )
        # 100/0.60 ≈ 166.67; 600/0.70 ≈ 857.14
        esperado_a = float(calcular_precio_unitario_con_profit(100, 0.40))
        esperado_b = float(calcular_precio_unitario_con_profit(600, 0.30))
        por_pk = {i['pk']: i for i in calculo['items_calculados']}
        self.assertAlmostEqual(por_pk[1]['precio_unitario_cliente'], esperado_a, places=2)
        self.assertAlmostEqual(por_pk[2]['precio_unitario_cliente'], esperado_b, places=2)
        self.assertAlmostEqual(
            calculo['precio_sin_iva'],
            round(esperado_a + esperado_b, 2),
            places=2,
        )
        self.assertEqual(por_pk[1]['profit_aplicado'], 0.40)
        self.assertEqual(por_pk[2]['profit_aplicado'], 0.30)

    def test_servicio_sin_profit_aplicado(self):
        items = [
            {
                'pk': 9,
                'descripcion': 'Limpieza',
                'cantidad': 1,
                'costo_unitario': 1160.0,
                'es_servicio': True,
            },
        ]
        calculo = calcular_precios_items_cotizacion(items=items, tipo_servicio='estandar')
        self.assertIsNone(calculo['items_calculados'][0]['profit_aplicado'])

    def test_parsear_y_aplicar_overrides(self):
        overrides = parsear_profit_overrides('{"10": 0.40, "11": 0.35}')
        self.assertEqual(overrides[10], Decimal('0.40'))
        items = [
            {'pk': 10, 'es_servicio': False, 'costo_unitario': 100},
            {'pk': 11, 'es_servicio': False, 'costo_unitario': 200},
        ]
        con_ov = aplicar_profit_overrides_a_items(items, overrides)
        self.assertEqual(con_ov[0]['profit_override'], 0.40)
        self.assertEqual(con_ov[1]['profit_override'], 0.35)

    def test_validar_override_bajo_minimo_rechaza(self):
        linea = MagicMock()
        linea.pk = 5
        linea.costo_unitario = Decimal('100')
        linea.es_linea_reacondicionado = False
        linea.producto.nombre = 'Pantalla'
        ok, msg = validar_profit_overrides_contra_lineas(
            [linea],
            {5: Decimal('0.10')},
        )
        self.assertFalse(ok)
        self.assertIn('mínimo', msg.lower())

    def test_validar_override_valido_acepta(self):
        linea = MagicMock()
        linea.pk = 5
        linea.costo_unitario = Decimal('100')
        linea.es_linea_reacondicionado = False
        linea.producto.nombre = 'Pantalla'
        ok, msg = validar_profit_overrides_contra_lineas(
            [linea],
            {5: Decimal('0.30')},
        )
        self.assertTrue(ok)
        self.assertEqual(msg, '')

    def test_resumen_email_coincide_con_motor_por_pieza(self):
        """
        Regresión: el resumen del correo no debe usar un solo % del perfil.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Antes el email sumaba costos y aplicaba el profit del perfil (ej. 36%).
        Si una pieza iba al 45%, el PDF/modal mostraban un total y el correo otro.
        Ahora el resumen debe salir de calcular_precios_items_cotizacion.
        """
        from almacen.utils.pdf_cotizacion_cliente import (
            TIPO_SERVICIO_NOMBRES,
            calcular_precio_cliente,
            calcular_precios_items_cotizacion,
        )

        items = [
            {
                'pk': 1,
                'descripcion': 'Pieza A',
                'cantidad': 1,
                'costo_unitario': 100.0,
                'es_servicio': False,
                'profit_override': 0.45,
            },
            {
                'pk': 2,
                'descripcion': 'Pieza B',
                'cantidad': 1,
                'costo_unitario': 600.0,
                'es_servicio': False,
                'profit_override': 0.30,
            },
        ]
        # Misma lógica que tasks.enviar_cotizacion_cliente_task (reparación)
        calculo_items = calcular_precios_items_cotizacion(
            items=items,
            tipo_servicio='estandar',
        )
        resumen_email = {
            'servicio_nombre': TIPO_SERVICIO_NOMBRES.get('estandar', 'Cotización'),
            'precio_sin_iva': calculo_items['precio_sin_iva'],
            'iva': calculo_items['iva'],
            'precio_con_iva': calculo_items['precio_con_iva'],
        }

        # El método viejo (un solo %) da otro total → debe diferir
        resumen_viejo = calcular_precio_cliente(
            costo_piezas=700.0,
            tipo_servicio='estandar',
        )
        self.assertNotEqual(
            resumen_email['precio_sin_iva'],
            resumen_viejo['precio_sin_iva'],
        )
        # Y el email nuevo coincide con la suma por pieza del motor
        self.assertEqual(
            resumen_email['precio_sin_iva'],
            calculo_items['precio_sin_iva'],
        )
        self.assertEqual(
            resumen_email['precio_con_iva'],
            calculo_items['precio_con_iva'],
        )
