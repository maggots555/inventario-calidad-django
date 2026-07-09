"""
Tests del motor de costeo de equipos reacondicionados (Excel Certificados SIC).
"""

from django.test import SimpleTestCase

from almacen.utils.costeo_reacondicionado import (
    calcular_costeo,
    obtener_etiqueta_opcion_pago_reac,
    obtener_precio_reac_con_iva,
    obtener_precio_reac_sin_iva,
)


class CosteoReacondicionadoTest(SimpleTestCase):
    """Valida la fórmula con los valores de ejemplo del Excel operativo."""

    def test_ejemplo_excel_valores_actuales(self):
        """Con los defaults del Excel, los totales deben ser consistentes."""
        resultado = calcular_costeo(costo_proveedor=5431.03, dias_front_desk=1)

        self.assertEqual(resultado['costo_proveedor'], 5431.03)
        self.assertEqual(resultado['gastos_administracion_front_desk'], 70.0)
        self.assertEqual(resultado['total_costos_fijos'], 5686.03)
        self.assertAlmostEqual(resultado['subtotal_sin_iva'], 7581.37, places=2)
        self.assertAlmostEqual(resultado['iva'], 1213.02, places=2)
        self.assertAlmostEqual(resultado['total_precio_contado_mxn'], 8794.39, places=2)

        dif = resultado['opciones_diferidas_con_iva']
        self.assertGreater(dif['diferido_3_meses'], resultado['total_precio_contado_mxn'])
        self.assertGreater(dif['diferido_6_meses'], dif['diferido_3_meses'])
        self.assertGreater(dif['diferido_12_meses'], dif['diferido_6_meses'])

    def test_sin_diagnostico_ni_profit_reparacion(self):
        """El costeo reacondicionado no mezcla lógica de perfiles de reparación."""
        resultado = calcular_costeo(costo_proveedor=1000.0, dias_front_desk=1)
        self.assertNotIn('diagnostico', resultado)
        self.assertGreater(resultado['total_precio_contado_mxn'], 1000.0)

    def test_obtener_precio_por_opcion_pago(self):
        """Cada forma de pago resuelve el monto correcto del snapshot."""
        costeo = calcular_costeo(costo_proveedor=5431.03, dias_front_desk=1)
        contado = float(obtener_precio_reac_con_iva(costeo, 'contado'))
        dif_6 = float(obtener_precio_reac_con_iva(costeo, 'diferido_6_meses'))
        self.assertAlmostEqual(contado, costeo['total_precio_contado_mxn'], places=2)
        self.assertGreater(dif_6, contado)
        sin_iva = float(obtener_precio_reac_sin_iva(costeo, 'contado'))
        self.assertAlmostEqual(sin_iva, costeo['subtotal_sin_iva'], places=2)

    def test_etiqueta_opcion_pago(self):
        self.assertEqual(
            obtener_etiqueta_opcion_pago_reac('diferido_6_meses'),
            'Financiamiento 6 meses',
        )
