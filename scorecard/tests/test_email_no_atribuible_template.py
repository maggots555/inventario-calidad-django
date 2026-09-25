"""
Tests del HTML del correo de incidencia no atribuible.

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo. Solo se rellena la plantilla para comprobar que
ya es un correo de tablas y que la justificación no se pierde.
"""

from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


PLANTILLA = 'scorecard/emails/no_atribuible.html'


def _incidencia(**overrides) -> SimpleNamespace:
    """
    Incidencia falsa con los campos que el HTML lee.

    Args:
        **overrides: Campos a cambiar (orden, servicio).

    Returns:
        SimpleNamespace: Incidencia lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    incidencia = SimpleNamespace(
        folio='INC-4',
        get_tipo_equipo_display=lambda: 'Laptop',
        marca='Dell',
        modelo='Latitude',
        numero_serie='SN-4',
        numero_orden='OOW-4',
        servicio_realizado=SimpleNamespace(nombre='Diagnóstico'),
        fecha_deteccion=datetime(2026, 9, 20),
        tipo_incidencia=SimpleNamespace(nombre='Daño estético'),
    )
    for clave, valor in overrides.items():
        setattr(incidencia, clave, valor)
    return incidencia


class NoAtribuibleEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas y conservar el aviso al técnico."""

    def test_completo_es_correo_interno(self):
        """Con orden: folio, justificación y pie, sin CSS de página."""
        html = render_to_string(
            PLANTILLA,
            {
                'incidencia': _incidencia(),
                'tecnico': SimpleNamespace(nombre_completo='Luis Técnico'),
                'justificacion': 'El daño ya venía de origen.',
                'marcado_por': 'Marta Calidad',
                'fecha_actual': datetime(2026, 9, 24, 16, 30),
            },
        )

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('Información Importante', html)
        self.assertIn('Incidencia no atribuible', html)
        self.assertIn('Hola <strong>Luis Técnico</strong>', html)
        self.assertIn('INC-4', html)
        self.assertIn('NO ATRIBUIBLE', html)
        self.assertIn('NO afectará tu Score Card', html)
        self.assertIn('Laptop - Dell Latitude', html)
        self.assertIn('SN-4', html)
        self.assertIn('OOW-4', html)
        self.assertIn('Diagnóstico', html)
        self.assertIn('20/09/2026', html)
        self.assertIn('Daño estético', html)
        self.assertIn('El daño ya venía de origen.', html)
        self.assertIn('conclusiones finales', html)
        self.assertIn('Marta Calidad', html)
        self.assertIn('24/09/2026 16:30', html)
        self.assertIn('no responder a este correo', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('instagram.com', html)

    def test_sin_orden_omite_esas_filas(self):
        """Sin orden ni servicio no se pintan esas etiquetas."""
        html = render_to_string(
            PLANTILLA,
            {
                'incidencia': _incidencia(numero_orden='', servicio_realizado=None),
                'tecnico': SimpleNamespace(nombre_completo='Luis Técnico'),
                'justificacion': 'No aplica.',
                'marcado_por': 'Sistema',
                'fecha_actual': datetime(2026, 9, 24, 8, 0),
            },
        )

        self.assertNotIn('Orden Cliente:', html)
        self.assertNotIn('Servicio Realizado:', html)
        self.assertIn('Folio:', html)
        self.assertIn('No aplica.', html)
