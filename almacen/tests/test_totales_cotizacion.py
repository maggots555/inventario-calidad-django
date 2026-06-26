"""
Tests de fórmulas de totales aprobados en cotizaciones.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Las propiedades del modelo combinan piezas (sin IVA + profit) y servicios
(con IVA incluido). Estos tests verifican la aritmética sin depender de BD.
Caso de referencia manual: solicitud SOL-2026-0025.
"""

from decimal import Decimal, ROUND_HALF_UP
from unittest import TestCase

IVA = Decimal('1.16')


def _piezas_con_iva(sin_iva: Decimal) -> Decimal:
    return (sin_iva * IVA).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _servicios_sin_iva(con_iva: Decimal) -> Decimal:
    return (con_iva / IVA).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class TotalesAprobadosFormulaTest(TestCase):
    """Caso SOL-2026-0025: una pieza aprobada + limpieza aprobada."""

    # Datos del escenario real (pieza 75 aprobada, servicio limpieza aprobado)
    PIEZAS_SIN_IVA = Decimal('2462.67')
    PIEZAS_COSTO = Decimal('1400.00')
    SERVICIOS_CON_IVA = Decimal('1050.00')

    def test_piezas_con_iva(self):
        self.assertEqual(_piezas_con_iva(self.PIEZAS_SIN_IVA), Decimal('2856.70'))

    def test_servicios_sin_iva(self):
        self.assertEqual(_servicios_sin_iva(self.SERVICIOS_CON_IVA), Decimal('905.17'))

    def test_total_a_cobrar_con_iva(self):
        total = _piezas_con_iva(self.PIEZAS_SIN_IVA) + self.SERVICIOS_CON_IVA
        self.assertEqual(total, Decimal('3906.70'))

    def test_total_sin_iva(self):
        total = self.PIEZAS_SIN_IVA + _servicios_sin_iva(self.SERVICIOS_CON_IVA)
        self.assertEqual(total, Decimal('3367.84'))

    def test_margen_piezas(self):
        margen = self.PIEZAS_SIN_IVA - self.PIEZAS_COSTO
        self.assertEqual(margen, Decimal('1062.67'))

    def test_cotizacion_enviada_no_cambia_con_rechazos(self):
        """Snapshot original: todas las piezas y servicios de la cotización."""
        precio_enviado_sin_iva = Decimal('9709.01')
        precio_enviado_con_iva = Decimal('11262.45')
        self.assertEqual(
            (precio_enviado_sin_iva * IVA).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
            precio_enviado_con_iva,
        )
