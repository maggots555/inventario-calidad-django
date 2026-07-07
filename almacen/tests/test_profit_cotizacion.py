"""
Tests de la fórmula de profit alineada con el Excel operativo.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Verificamos que el margen solo aplique sobre piezas, que el diagnóstico se sume
aparte y que costos fijos / mano de obra no inflen el precio al cliente.
"""

from django.test import SimpleTestCase

from almacen.utils.pdf_cotizacion_cliente import (
    _calcular_matematica_profit,
    calcular_precio_cliente,
    calcular_precios_items_cotizacion,
)


class ProfitCotizacionExcelTest(SimpleTestCase):
    """Casos numéricos del perfil estándar (profit 36%, fijos 185, diag 570)."""

    PROFIT_TARGET = 0.36
    COSTOS_FIJOS = [25.0, 160.0]
    DIAGNOSTICO = 570.0

    def _matematica(self, costo_piezas: float, mano_obra: float = 0.0):
        return _calcular_matematica_profit(
            suma_costos_brutos=costo_piezas,
            profit_target=self.PROFIT_TARGET,
            diagnostico=self.DIAGNOSTICO,
            costos_fijos=self.COSTOS_FIJOS,
            mano_obra=mano_obra,
        )

    def test_precio_final_perfil_estandar_ejemplo_excel(self):
        """PRECIO_FINAL_SIN_IVA = 1000/0.64 + 570 = 2132.50"""
        resultado = self._matematica(1000.0)
        self.assertEqual(resultado['precio_piezas_sin_iva'], 1562.50)
        self.assertEqual(resultado['precio_final_sin_iva'], 2132.50)

    def test_costos_fijos_y_mano_obra_no_inflan_precio_cliente(self):
        """Fijos y MO solo afectan ganancia bruta, no el precio al cliente."""
        sin_mo = self._matematica(1000.0, mano_obra=0.0)
        con_mo = self._matematica(1000.0, mano_obra=500.0)
        self.assertEqual(sin_mo['precio_final_sin_iva'], con_mo['precio_final_sin_iva'])

        sin_fijos = _calcular_matematica_profit(
            suma_costos_brutos=1000.0,
            profit_target=self.PROFIT_TARGET,
            diagnostico=self.DIAGNOSTICO,
            costos_fijos=[],
            mano_obra=0.0,
        )
        con_fijos = self._matematica(1000.0)
        self.assertEqual(
            sin_fijos['precio_final_sin_iva'],
            con_fijos['precio_final_sin_iva'],
        )

    def test_ganancia_bruta_bloque_excel(self):
        """GANANCIA_BRUTA = PRECIO_PIEZAS - (piezas + MO + fijos)."""
        resultado = self._matematica(1000.0, mano_obra=200.0)
        # 1562.50 - (1000 + 200 + 185) = 177.50
        self.assertEqual(resultado['ganancia_bruta_dinero'], 177.50)
        self.assertAlmostEqual(
            resultado['ganancia_bruta_porcentaje'],
            177.50 / 1562.50,
            places=4,
        )

    def test_subtotales_items_cuadran_con_precio_final(self):
        """Σ subtotales de piezas == PRECIO_FINAL_SIN_IVA tras redondeo."""
        items = [
            {'descripcion': 'Pantalla', 'cantidad': 1, 'costo_unitario': 600.0, 'es_servicio': False},
            {'descripcion': 'Teclado', 'cantidad': 2, 'costo_unitario': 200.0, 'es_servicio': False},
        ]
        calculo = calcular_precios_items_cotizacion(
            items=items,
            tipo_servicio='estandar',
            mano_de_obra_override=999.0,
        )
        suma_subtotales = sum(
            i['subtotal_cliente']
            for i in calculo['items_calculados']
            if not i.get('es_servicio')
        )
        self.assertEqual(suma_subtotales, calculo['precio_sin_iva'])
        self.assertEqual(calculo['precio_sin_iva'], 2132.50)

    def test_calcular_precio_cliente_coincide_con_excel(self):
        """Resumen de email usa la misma fórmula que el PDF."""
        resultado = calcular_precio_cliente(
            costo_piezas=1000.0,
            tipo_servicio='estandar',
            mano_de_obra_override=200.0,
        )
        self.assertEqual(resultado['precio_sin_iva'], 2132.50)
        self.assertEqual(resultado['precio_con_iva'], round(2132.50 * 1.16, 2))
        self.assertEqual(resultado['ganancia_bruta_dinero'], 177.50)

    def test_solo_servicios_sin_profit(self):
        """Cotización solo con servicios adicionales: suma directa."""
        items = [
            {
                'descripcion': 'Limpieza',
                'cantidad': 1,
                'costo_unitario': 1160.0,
                'es_servicio': True,
            },
        ]
        calculo = calcular_precios_items_cotizacion(items=items, tipo_servicio='estandar')
        self.assertEqual(calculo['precio_con_iva'], 1160.0)
        self.assertEqual(calculo['diagnostico'], 0)
        self.assertEqual(calculo['precio_piezas_sin_iva'], 0.0)

    def test_sin_piezas_con_diagnostico_genera_linea_reparacion(self):
        """Si no hay costo de piezas pero sí diagnóstico, aparece línea de reparación."""
        calculo = calcular_precios_items_cotizacion(
            items=[],
            tipo_servicio='estandar',
        )
        self.assertEqual(calculo['precio_sin_iva'], 570.0)
        self.assertEqual(len(calculo['items_calculados']), 1)
        self.assertEqual(
            calculo['items_calculados'][0]['descripcion'],
            'Servicio de reparación',
        )

    def test_rep_nivel_componente_sin_diagnostico(self):
        """Rep. nivel componente replica mostrador: sin cargo ni descuento de diagnóstico."""
        resultado = calcular_precio_cliente(
            costo_piezas=1000.0,
            tipo_servicio='rep_nivel_componente',
        )
        self.assertEqual(resultado['diagnostico'], 0)
        self.assertIsNone(resultado.get('precio_menos_diagnostico'))
        # Mismo margen que mostrador por defecto: 1000 / 0.58 ≈ 1724.14
        self.assertAlmostEqual(resultado['precio_sin_iva'], round(1000 / 0.58, 2), places=2)
