"""
Tests de la regla NPS → recomienda (sin preguntar pulgares al cliente).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No hace falta base de datos: solo comprobamos que el helper clasifique
bien cada número del 0 al 10. SimpleTestCase es más rápido que TestCase.
"""

from django.test import SimpleTestCase

from servicio_tecnico.forms import FeedbackSatisfaccionClienteForm
from servicio_tecnico.services.encuesta_nps import (
    debe_pedir_detalle_calificacion,
    derivar_recomienda_desde_nps,
)


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


class DebePedirDetalleCalificacionTest(SimpleTestCase):
    """
    Objetivo: Atención/Tiempo solo con 1–3 estrellas; 4–5 y vacío = no.

    Efectos secundarios: ninguno.
    """

    def test_uno_a_tres_piden_detalle(self):
        """1, 2 y 3 estrellas sí muestran las sub-calificaciones."""
        for estrellas in (1, 2, 3):
            with self.subTest(estrellas=estrellas):
                self.assertTrue(debe_pedir_detalle_calificacion(estrellas))

    def test_cuatro_cinco_y_vacio_no_piden_detalle(self):
        """4–5 (buena visita) y None/fuera de rango no alargan el form."""
        for estrellas in (None, 0, 4, 5, 6):
            with self.subTest(estrellas=estrellas):
                self.assertFalse(debe_pedir_detalle_calificacion(estrellas))


class FormDescartaDetalleSiNotaAltaTest(SimpleTestCase):
    """
    Objetivo: si alguien manda atención/tiempo con 4–5 estrellas, el
    formulario los tira. Con 1–3 sí se aceptan.

    Efectos secundarios: ninguno (solo valida el Form, sin BD).
    """

    def test_cinco_estrellas_ignora_atencion_y_tiempo(self):
        """Nota alta + detalle en el POST → cleaned_data queda en None."""
        form = FeedbackSatisfaccionClienteForm({
            'calificacion_general': '5',
            'nps': '9',
            'calificacion_atencion': '1',
            'calificacion_tiempo': '2',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.cleaned_data['calificacion_atencion'])
        self.assertIsNone(form.cleaned_data['calificacion_tiempo'])

    def test_dos_estrellas_guarda_detalle(self):
        """Nota baja: Atención y Tiempo sí pasan al cleaned_data."""
        form = FeedbackSatisfaccionClienteForm({
            'calificacion_general': '2',
            'nps': '4',
            'calificacion_atencion': '3',
            'calificacion_tiempo': '2',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['calificacion_atencion'], 3)
        self.assertEqual(form.cleaned_data['calificacion_tiempo'], 2)
