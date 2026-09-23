"""
Tests de la plantilla HTML y del texto plano de la encuesta de satisfacción.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo. Solo se rellena el HTML y el text/plain para no
romper las cinco estrellas, el botón de respaldo ni el pie propio de
este correo (no es el de los demás).
"""

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_feedback_satisfaccion import (
    construir_texto_plano_feedback_satisfaccion,
)


PLANTILLA = 'servicio_tecnico/emails/feedback_satisfaccion.html'
URL = 'https://app.sigmasystem.work/feedback-satisfaccion/token-sat/'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_feedback_satisfaccion_task.

    Args:
        **overrides: Claves a cambiar (sin fecha, sin tipo, etc.).

    Returns:
        dict: Contexto para render_to_string.
    """
    contexto = {
        'folio': 'FL-2201',
        'marca_equipo': 'Dell',
        'modelo_equipo': 'XPS 13',
        'tipo_equipo': 'Laptop',
        'fecha_entrega': '02/09/2026',
        'feedback_url': URL,
        'dias_vigencia': 12,
        'fecha_envio': '14/09/2026',
    }
    contexto.update(overrides)
    return contexto


class FeedbackSatisfaccionEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas y conservar las cinco estrellas."""

    def test_render_base_incluye_estrellas_y_layout(self):
        """Feliz: folio, estrellas, botón y pie propio de este correo."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('¡Tu equipo fue entregado!', html)
        self.assertIn('Laptop — Dell XPS 13', html)
        self.assertIn('Folio: FL-2201', html)
        self.assertIn('Entregado el 02/09/2026', html)
        self.assertIn('¿Cómo te tratamos?', html)
        self.assertIn('2 minutos', html)
        for numero, etiqueta in (
            (1, 'Muy malo'),
            (2, 'Malo'),
            (3, 'Regular'),
            (4, 'Bueno'),
            (5, 'Excelente'),
        ):
            self.assertIn(f'{URL}?estrellas={numero}', html)
            self.assertIn(etiqueta, html)
        self.assertIn('O completa la encuesta aquí', html)
        self.assertIn('personal y de uso único', html)
        self.assertIn('12 días', html)
        self.assertIn('Tus respuestas son confidenciales', html)
        self.assertIn('SIC - Comercialización y Servicios', html)
        self.assertIn('https://instagram.com/sicfix.mx', html)
        self.assertIn('https://facebook.com/sicfix.mx', html)
        self.assertIn('https://wa.me/523318189988', html)
        self.assertIn('Este correo fue enviado el 14/09/2026', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('fillcolor="#1f6391"', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('#667eea', html)

    def test_sin_fecha_ni_tipo_omite_esas_lineas(self):
        """Sin entrega ni tipo no se inventa texto."""
        html = render_to_string(
            PLANTILLA,
            _contexto(fecha_entrega='', tipo_equipo=''),
        )
        self.assertNotIn('Entregado el', html)
        self.assertNotIn('Laptop', html)
        self.assertIn('Dell XPS 13', html)


class FeedbackSatisfaccionTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar las cinco URLs de estrellas."""

    def test_plano_incluye_cinco_estrellas_y_respaldo(self):
        """Feliz: cada calificación y el botón apuntan al mismo formulario."""
        texto = construir_texto_plano_feedback_satisfaccion(_contexto())
        self.assertIn('¡Tu equipo fue entregado!', texto)
        self.assertIn('Laptop — Dell XPS 13', texto)
        for numero in range(1, 6):
            self.assertIn(f'{URL}?estrellas={numero}', texto)
        self.assertIn(URL, texto)
        self.assertIn('https://wa.me/523318189988', texto)
        self.assertIn('Este correo fue enviado el 14/09/2026', texto)

    def test_plano_sin_fecha_no_inventa_entrega(self):
        """Sin fecha de entrega el plano tampoco la menciona."""
        texto = construir_texto_plano_feedback_satisfaccion(
            _contexto(fecha_entrega=''),
        )
        self.assertNotIn('Entregado el', texto)
