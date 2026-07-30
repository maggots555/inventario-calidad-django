"""
Tests de la fórmula de profit de cotización al cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Verificamos que el margen solo aplique sobre piezas, que el diagnóstico
YA NO se sume ni se diluya en las piezas, y que costos fijos / mano de obra
no inflen el precio al cliente. La reparación se abona completa; el
diagnóstico se cobra aparte al ingresar el equipo.
"""

from django.test import SimpleTestCase

from almacen.utils.pdf_cotizacion_cliente import (
    _calcular_matematica_profit,
    calcular_precio_cliente,
    calcular_precios_items_cotizacion,
)


class ProfitCotizacionExcelTest(SimpleTestCase):
    """Casos numéricos del perfil estándar (profit 36%, fijos 185)."""

    PROFIT_TARGET = 0.36
    COSTOS_FIJOS = [25.0, 160.0]
    # Valor histórico del perfil; el motor lo ignora en el precio de reparación
    DIAGNOSTICO_LEGACY = 570.0

    def _matematica(self, costo_piezas: float, mano_obra: float = 0.0, diagnostico: float = 0.0):
        return _calcular_matematica_profit(
            suma_costos_brutos=costo_piezas,
            profit_target=self.PROFIT_TARGET,
            diagnostico=diagnostico,
            costos_fijos=self.COSTOS_FIJOS,
            mano_obra=mano_obra,
        )

    def test_precio_final_solo_piezas_con_margen(self):
        """PRECIO_FINAL_SIN_IVA = 1000/0.64 = 1562.50 (sin sumar diagnóstico)."""
        resultado = self._matematica(1000.0, diagnostico=self.DIAGNOSTICO_LEGACY)
        self.assertEqual(resultado['precio_piezas_sin_iva'], 1562.50)
        self.assertEqual(resultado['precio_final_sin_iva'], 1562.50)

    def test_diagnostico_no_diluye_precio_final(self):
        """Pasar diagnóstico legacy no cambia el total de reparación."""
        sin_diag = self._matematica(1000.0, diagnostico=0.0)
        con_diag = self._matematica(1000.0, diagnostico=self.DIAGNOSTICO_LEGACY)
        self.assertEqual(sin_diag['precio_final_sin_iva'], con_diag['precio_final_sin_iva'])
        self.assertEqual(sin_diag['factor_redistrib'], con_diag['factor_redistrib'])

    def test_costos_fijos_y_mano_obra_no_inflan_precio_cliente(self):
        """Fijos y MO solo afectan ganancia bruta, no el precio al cliente."""
        sin_mo = self._matematica(1000.0, mano_obra=0.0)
        con_mo = self._matematica(1000.0, mano_obra=500.0)
        self.assertEqual(sin_mo['precio_final_sin_iva'], con_mo['precio_final_sin_iva'])

        sin_fijos = _calcular_matematica_profit(
            suma_costos_brutos=1000.0,
            profit_target=self.PROFIT_TARGET,
            diagnostico=0.0,
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
        self.assertEqual(calculo['precio_sin_iva'], 1562.50)
        self.assertIsNone(calculo.get('precio_menos_diagnostico'))
        self.assertEqual(calculo['diagnostico'], 0)

    def test_calcular_precio_cliente_coincide_sin_diagnostico(self):
        """Resumen de email usa la misma fórmula que el PDF (sin diagnóstico)."""
        resultado = calcular_precio_cliente(
            costo_piezas=1000.0,
            tipo_servicio='estandar',
            mano_de_obra_override=200.0,
        )
        self.assertEqual(resultado['precio_sin_iva'], 1562.50)
        self.assertEqual(resultado['precio_con_iva'], round(1562.50 * 1.16, 2))
        self.assertEqual(resultado['ganancia_bruta_dinero'], 177.50)
        self.assertIsNone(resultado.get('precio_menos_diagnostico'))
        self.assertEqual(resultado['diagnostico'], 0.0)

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

    def test_sin_piezas_no_genera_linea_por_diagnostico(self):
        """Sin piezas: no se inventa línea de reparación por diagnóstico legacy."""
        calculo = calcular_precios_items_cotizacion(
            items=[],
            tipo_servicio='estandar',
        )
        self.assertEqual(calculo['precio_sin_iva'], 0.0)
        self.assertEqual(len(calculo['items_calculados']), 0)
        self.assertIsNone(calculo.get('precio_menos_diagnostico'))

    def test_rep_nivel_componente_sin_diagnostico(self):
        """Rep. nivel componente replica mostrador: sin cargo de diagnóstico."""
        resultado = calcular_precio_cliente(
            costo_piezas=1000.0,
            tipo_servicio='rep_nivel_componente',
        )
        self.assertEqual(resultado['diagnostico'], 0)
        self.assertIsNone(resultado.get('precio_menos_diagnostico'))
        # Mismo margen que mostrador por defecto: 1000 / 0.58 ≈ 1724.14
        self.assertAlmostEqual(resultado['precio_sin_iva'], round(1000 / 0.58, 2), places=2)

    def test_flag_descuento_true_no_cambia_totales(self):
        """
        Regresión: pasar incluir_descuento_diagnostico=True no debe restar nada.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Antes el flag restaba diagnóstico×1.16 del total. Ahora el parámetro
        es legacy y se ignora: True y False deben dar el mismo resultado.
        """
        items = [
            {
                'descripcion': 'Pantalla',
                'cantidad': 1,
                'costo_unitario': 1000.0,
                'es_servicio': False,
            },
        ]
        con_flag = calcular_precios_items_cotizacion(
            items=items,
            tipo_servicio='estandar',
            incluir_descuento_diagnostico=True,
        )
        sin_flag = calcular_precios_items_cotizacion(
            items=items,
            tipo_servicio='estandar',
            incluir_descuento_diagnostico=False,
        )

        self.assertEqual(con_flag['precio_sin_iva'], sin_flag['precio_sin_iva'])
        self.assertEqual(con_flag['precio_con_iva'], sin_flag['precio_con_iva'])
        self.assertEqual(con_flag['precio_sin_iva'], 1562.50)
        self.assertIsNone(con_flag['precio_menos_diagnostico'])
        self.assertIsNone(sin_flag['precio_menos_diagnostico'])

        # Misma garantía en el resumen usado por email/preview
        resumen_true = calcular_precio_cliente(
            costo_piezas=1000.0,
            tipo_servicio='estandar',
            incluir_descuento_diagnostico=True,
        )
        resumen_false = calcular_precio_cliente(
            costo_piezas=1000.0,
            tipo_servicio='estandar',
            incluir_descuento_diagnostico=False,
        )
        self.assertEqual(resumen_true['precio_con_iva'], resumen_false['precio_con_iva'])
        self.assertIsNone(resumen_true['precio_menos_diagnostico'])
