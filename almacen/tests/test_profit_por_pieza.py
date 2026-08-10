"""
Tests de profit mínimo y efectivo por pieza (reparación).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Validamos los rangos de margen mínimo según costo unitario y que
resolver_profit_linea tome el mayor entre perfil/override y el mínimo.
También comprobamos el motor de precios con % distintos por pieza y
el rechazo de overrides debajo del mínimo.

Rangos vigentes:
  $0–$499 → 45% | $500–$999 → 36% | $1000–$1499 → 30% | $1500+ → 28%
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
        self.assertEqual(obtener_profit_minimo(0), Decimal('0.45'))
        self.assertEqual(obtener_profit_minimo(499.99), Decimal('0.45'))
        self.assertEqual(obtener_profit_minimo('250'), Decimal('0.45'))

    def test_borde_500(self):
        """$499.99 → 45%; $500 → 36%."""
        self.assertEqual(obtener_profit_minimo(499.99), Decimal('0.45'))
        self.assertEqual(obtener_profit_minimo(500), Decimal('0.36'))

    def test_rango_500_a_999(self):
        self.assertEqual(obtener_profit_minimo(999.99), Decimal('0.36'))

    def test_borde_1000(self):
        self.assertEqual(obtener_profit_minimo(999.99), Decimal('0.36'))
        self.assertEqual(obtener_profit_minimo(1000), Decimal('0.30'))

    def test_rango_1000_a_1499(self):
        self.assertEqual(obtener_profit_minimo(1499.99), Decimal('0.30'))

    def test_borde_1500(self):
        self.assertEqual(obtener_profit_minimo(1499.99), Decimal('0.30'))
        self.assertEqual(obtener_profit_minimo(1500), Decimal('0.28'))
        self.assertEqual(obtener_profit_minimo(99999), Decimal('0.28'))

    def test_rangos_frontend_serializables(self):
        """El JSON del modal debe recibir exactamente 4 rangos."""
        rangos = rangos_profit_minimo_para_frontend()
        self.assertEqual(len(rangos), 4)
        self.assertIsNone(rangos[-1]['costo_max'])
        self.assertEqual(rangos[0]['profit_minimo'], 0.45)
        self.assertEqual(rangos[1]['profit_minimo'], 0.36)
        self.assertEqual(rangos[2]['profit_minimo'], 0.30)
        self.assertEqual(rangos[3]['profit_minimo'], 0.28)


class ResolverProfitLineaTest(SimpleTestCase):
    """Perfil como default + override + piso por costo."""

    def test_perfil_por_encima_del_minimo(self):
        # Costo $1500 → min 28%; perfil 36% → se queda en 36%
        self.assertEqual(
            resolver_profit_linea(1500, 0.36),
            Decimal('0.36'),
        )

    def test_perfil_por_debajo_del_minimo_se_eleva(self):
        # Costo $100 → min 45%; perfil 36% → sube a 45%
        self.assertEqual(
            resolver_profit_linea(100, 0.36),
            Decimal('0.45'),
        )

    def test_override_valido_sube_sobre_perfil(self):
        self.assertEqual(
            resolver_profit_linea(100, 0.36, profit_override=0.50),
            Decimal('0.50'),
        )

    def test_override_debajo_del_minimo_se_eleva(self):
        # API/UI pueden clampar; resolver siempre respeta el piso
        self.assertEqual(
            resolver_profit_linea(100, 0.36, profit_override=0.10),
            Decimal('0.45'),
        )

    def test_rangos_explicito_por_perfil_distinto(self):
        """
        Con lista de rangos distinta (como si viniera de BD de otro perfil),
        el mínimo cambia sin tocar la semilla global.
        """
        rangos_suaves = [
            {'costo_min': 0, 'costo_max': 500, 'profit_minimo': 0.40},
            {'costo_min': 500, 'costo_max': 1000, 'profit_minimo': 0.30},
            {'costo_min': 1000, 'costo_max': 1500, 'profit_minimo': 0.25},
            {'costo_min': 1500, 'costo_max': None, 'profit_minimo': 0.20},
        ]
        self.assertEqual(
            obtener_profit_minimo(100, rangos=rangos_suaves),
            Decimal('0.40'),
        )
        self.assertEqual(
            resolver_profit_linea(100, 0.36, rangos=rangos_suaves),
            Decimal('0.40'),
        )

    def test_profit_cumple_minimo(self):
        self.assertTrue(profit_cumple_minimo(100, 0.45))
        self.assertFalse(profit_cumple_minimo(100, 0.44))
        self.assertTrue(profit_cumple_minimo(1500, 0.28))
        self.assertFalse(profit_cumple_minimo(1500, 0.27))

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
        Pieza A $100 @ 50% + Pieza B $600 @ 40% → suma de precios independientes.

        EXPLICACIÓN: ya no hay un solo factor global; cada línea tiene su %.
        Los % están por encima del mínimo de su rango (45% y 36%).
        """
        items = [
            {
                'pk': 1,
                'descripcion': 'Barata',
                'cantidad': 1,
                'costo_unitario': 100.0,
                'es_servicio': False,
                'profit_override': 0.50,
            },
            {
                'pk': 2,
                'descripcion': 'Cara',
                'cantidad': 1,
                'costo_unitario': 600.0,
                'es_servicio': False,
                'profit_override': 0.40,
            },
        ]
        calculo = calcular_precios_items_cotizacion(
            items=items,
            tipo_servicio='estandar',
        )
        esperado_a = float(calcular_precio_unitario_con_profit(100, 0.50))
        esperado_b = float(calcular_precio_unitario_con_profit(600, 0.40))
        por_pk = {i['pk']: i for i in calculo['items_calculados']}
        self.assertAlmostEqual(por_pk[1]['precio_unitario_cliente'], esperado_a, places=2)
        self.assertAlmostEqual(por_pk[2]['precio_unitario_cliente'], esperado_b, places=2)
        self.assertAlmostEqual(
            calculo['precio_sin_iva'],
            round(esperado_a + esperado_b, 2),
            places=2,
        )
        self.assertEqual(por_pk[1]['profit_aplicado'], 0.50)
        self.assertEqual(por_pk[2]['profit_aplicado'], 0.40)

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
        overrides = parsear_profit_overrides('{"10": 0.50, "11": 0.40}')
        self.assertEqual(overrides[10], Decimal('0.50'))
        items = [
            {'pk': 10, 'es_servicio': False, 'costo_unitario': 100},
            {'pk': 11, 'es_servicio': False, 'costo_unitario': 600},
        ]
        con_ov = aplicar_profit_overrides_a_items(items, overrides)
        self.assertEqual(con_ov[0]['profit_override'], 0.50)
        self.assertEqual(con_ov[1]['profit_override'], 0.40)

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
            {5: Decimal('0.45')},
        )
        self.assertTrue(ok)
        self.assertEqual(msg, '')

    def test_validar_con_rangos_de_perfil_custom(self):
        """Con semilla 40% falla; con rangos suaves 40% cumple el mínimo."""
        linea = MagicMock()
        linea.pk = 5
        linea.costo_unitario = Decimal('100')
        linea.es_linea_reacondicionado = False
        linea.producto.nombre = 'Pantalla'
        rangos_suaves = [
            {'costo_min': 0, 'costo_max': 500, 'profit_minimo': 0.40},
            {'costo_min': 500, 'costo_max': 1000, 'profit_minimo': 0.30},
            {'costo_min': 1000, 'costo_max': 1500, 'profit_minimo': 0.25},
            {'costo_min': 1500, 'costo_max': None, 'profit_minimo': 0.20},
        ]
        ok_semilla, _ = validar_profit_overrides_contra_lineas(
            [linea], {5: Decimal('0.40')},
        )
        self.assertFalse(ok_semilla)
        self.assertTrue(profit_cumple_minimo(100, 0.40, rangos=rangos_suaves))
        self.assertFalse(profit_cumple_minimo(100, 0.39, rangos=rangos_suaves))

    def test_resumen_email_coincide_con_motor_por_pieza(self):
        """
        Regresión: el resumen del correo no debe usar un solo % del perfil.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Antes el email sumaba costos y aplicaba el profit del perfil (ej. 36%).
        Si una pieza iba al 50%, el PDF/modal mostraban un total y el correo otro.
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
                'profit_override': 0.50,
            },
            {
                'pk': 2,
                'descripcion': 'Pieza B',
                'cantidad': 1,
                'costo_unitario': 600.0,
                'es_servicio': False,
                'profit_override': 0.40,
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
