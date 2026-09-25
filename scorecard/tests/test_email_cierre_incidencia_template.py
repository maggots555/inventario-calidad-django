"""
Tests del HTML de los correos de cierre de incidencia.

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo. Solo se rellena la plantilla para comprobar que
el cierre atribuible y el no atribuible no se mezclan.
"""

from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


def _incidencia(**overrides) -> SimpleNamespace:
    """
    Incidencia falsa con los campos que los dos cierres leen.

    Args:
        **overrides: Campos a cambiar.

    Returns:
        SimpleNamespace: Incidencia lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    incidencia = SimpleNamespace(
        folio='INC-7',
        get_tipo_equipo_display=lambda: 'Laptop',
        marca='Dell',
        modelo='Latitude',
        numero_serie='SN-7',
        numero_orden='OOW-7',
        servicio_realizado=SimpleNamespace(nombre='Reparación'),
        fecha_deteccion=datetime(2026, 9, 10),
        tipo_incidencia=SimpleNamespace(nombre='Daño estético'),
        get_grado_severidad_display=lambda: 'Alto',
        descripcion_incidencia='Rayón en la tapa.',
        justificacion_no_atribuible='El daño ya venía de origen.',
    )
    for clave, valor in overrides.items():
        setattr(incidencia, clave, valor)
    return incidencia


def _contexto(**overrides) -> dict:
    """
    Contexto común de los dos correos de cierre.

    Args:
        **overrides: Claves a cambiar.

    Returns:
        dict: Contexto para render_to_string.

    Efectos secundarios:
        Ninguno.
    """
    contexto = {
        'incidencia': _incidencia(),
        'tecnico': SimpleNamespace(nombre_completo='Luis Técnico'),
        'mensaje_adicional': 'Se cambió el proceso de empaque.',
        'enviado_por': 'Marta Calidad',
        'fecha_cierre': datetime(2026, 9, 24, 17, 15),
    }
    contexto.update(overrides)
    return contexto


class CierreIncidenciaEmailTemplateTests(SimpleTestCase):
    """El cierre atribuible debe avisar que sí cuenta en el Score Card."""

    def test_completo_es_correo_interno(self):
        """Con datos: impacto, severidad y conclusión, sin CSS de página."""
        html = render_to_string(
            'scorecard/emails/cierre_incidencia.html',
            _contexto(),
        )

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('Incidencia Cerrada', html)
        self.assertIn('Hola <strong>Luis Técnico</strong>', html)
        self.assertIn('INC-7', html)
        self.assertIn('SÍ se contabilizará', html)
        self.assertIn('Laptop - Dell Latitude', html)
        self.assertIn('OOW-7', html)
        self.assertIn('Alto', html)
        self.assertIn('24/09/2026 17:15', html)
        self.assertIn('Rayón en la tapa.', html)
        self.assertIn('Acciones Correctivas y Conclusión', html)
        self.assertIn('Se cambió el proceso de empaque.', html)
        self.assertIn('servicios futuros', html)
        self.assertIn('Marta Calidad', html)
        self.assertNotIn('NO afecta tu Score Card', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('instagram.com', html)

    def test_sin_opcionales_omite_bloques(self):
        """Sin orden, descripción ni mensaje no se pintan esas secciones."""
        html = render_to_string(
            'scorecard/emails/cierre_incidencia.html',
            _contexto(
                incidencia=_incidencia(
                    numero_orden='',
                    servicio_realizado=None,
                    descripcion_incidencia='',
                ),
                mensaje_adicional='',
            ),
        )

        self.assertNotIn('Orden Cliente:', html)
        self.assertNotIn('Servicio Realizado:', html)
        self.assertNotIn('Descripción de la Incidencia', html)
        self.assertNotIn('Acciones Correctivas y Conclusión', html)
        self.assertIn('SÍ se contabilizará', html)


class CierreNoAtribuibleEmailTemplateTests(SimpleTestCase):
    """El cierre no atribuible debe recordar que no afecta el Score Card."""

    def test_completo_conserva_la_justificacion(self):
        """Con datos: recordatorio verde, justificación y conclusión."""
        html = render_to_string(
            'scorecard/emails/cierre_no_atribuible.html',
            _contexto(),
        )

        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('Conclusión Final', html)
        self.assertIn('Cerrada - no atribuible', html)
        self.assertIn('NO afecta tu Score Card', html)
        self.assertIn('Por qué NO fue atribuible', html)
        self.assertIn('El daño ya venía de origen.', html)
        self.assertIn('Descripción Original', html)
        self.assertIn('Conclusión Final y Acciones Tomadas', html)
        self.assertIn('seguimiento dado al caso', html)
        self.assertNotIn('SÍ se contabilizará', html)
        self.assertNotIn('Severidad:', html)
        self.assertNotIn('instagram.com', html)

    def test_sin_textos_omite_secciones(self):
        """Sin justificación, descripción ni mensaje no se pintan esos títulos."""
        html = render_to_string(
            'scorecard/emails/cierre_no_atribuible.html',
            _contexto(
                incidencia=_incidencia(
                    numero_orden='',
                    servicio_realizado=None,
                    justificacion_no_atribuible='',
                    descripcion_incidencia='',
                ),
                mensaje_adicional='',
            ),
        )

        self.assertNotIn('Por qué NO fue atribuible', html)
        self.assertNotIn('Descripción Original', html)
        self.assertNotIn('Conclusión Final y Acciones Tomadas', html)
        self.assertNotIn('Orden Cliente:', html)
        self.assertIn('NO afecta tu Score Card', html)
