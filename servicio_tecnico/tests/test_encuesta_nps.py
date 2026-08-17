"""
Tests de la regla NPS → recomienda (sin preguntar pulgares al cliente).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No hace falta base de datos: solo comprobamos que el helper clasifique
bien cada número del 0 al 10. SimpleTestCase es más rápido que TestCase.
"""

from django.test import SimpleTestCase

from servicio_tecnico.services.encuesta_nps import derivar_recomienda_desde_nps


class DerivarRecomiendaDesdeNpsTest(SimpleTestCase):
    """
    Objetivo: 0–6 = no recomienda; 7–10 = sí; None o fuera de rango = None.

    Efectos secundarios: ninguno.
    """

    def test_detractores_no_recomiendan(self):
        """NPS 0 a 6 son detractores: el pulgar queda en No."""
        for nps in range(0, 7):
            with self.subTest(nps=nps):
                self.assertIs(derivar_recomienda_desde_nps(nps), False)

    def test_pasivos_y_promotores_si_recomiendan(self):
        """NPS 7–8 (pasivos) y 9–10 (promotores) cuentan como Sí."""
        for nps in range(7, 11):
            with self.subTest(nps=nps):
                self.assertIs(derivar_recomienda_desde_nps(nps), True)

    def test_sin_nps_o_fuera_de_rango_no_inventa(self):
        """None o un número imposible no deben inventar un sí/no."""
        self.assertIsNone(derivar_recomienda_desde_nps(None))
        self.assertIsNone(derivar_recomienda_desde_nps(-1))
        self.assertIsNone(derivar_recomienda_desde_nps(11))
