"""
Tests de la plantilla HTML y del texto plano del aviso de cotización vencida.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo. Solo se rellena el HTML y el text/plain para no
perder el aviso de vigencia ni inventar un botón que este correo no tiene.
"""

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_vigencia_vencida import (
    construir_texto_plano_vigencia_vencida,
)


PLANTILLA = 'servicio_tecnico/emails/vigencia_vencida.html'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_vigencia_vencida_task.

    Args:
        **overrides: Claves a cambiar (sin modelo, etc.).

    Returns:
        dict: Contexto para render_to_string.
    """
    contexto = {
        'nombre_cliente': 'usuario',
        'folio': 'FL-3301',
        'marca_equipo': 'Dell',
        'modelo_equipo': 'XPS 13',
        'fecha_envio': '14/09/2026',
    }
    contexto.update(overrides)
    return contexto


class VigenciaVencidaEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas y conservar el aviso."""

    def test_render_base_incluye_aviso_y_layout(self):
        """Feliz: folio, aviso de vigencia y pie, sin botón inventado."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Aviso de cotización vencida', html)
        self.assertIn('Folio FL-3301', html)
        self.assertIn('Estimado/a usuario,', html)
        self.assertNotIn('Estimado/a Estimado', html)
        self.assertIn('vencido', html)
        self.assertIn('por falta de respuesta', html)
        self.assertIn('Dell', html)
        self.assertIn('XPS 13', html)
        self.assertIn('ya no se encuentra vigente', html)
        self.assertIn('Próximos pasos', html)
        self.assertIn('hasta nuevo aviso', html)
        self.assertIn('Gracias por confiar en nuestros servicios.', html)
        self.assertIn('contacte directamente a su responsable.', html)
        self.assertIn('https://sicfix.mx/', html)
        self.assertIn('https://www.instagram.com/sic_mexico/?hl=es', html)
        self.assertIn('https://www.facebook.com/LatAmSic', html)
        self.assertIn('https://wa.me/', html)
        self.assertIn('Enviado el 14/09/2026', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('class="email-brandbar"', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('#667eea', html)
        self.assertNotIn('Dejar mi comentario', html)

    def test_sin_modelo_no_inventa_equipo(self):
        """Sin modelo solo se muestra la marca."""
        html = render_to_string(PLANTILLA, _contexto(modelo_equipo=''))
        self.assertIn('Dell', html)
        self.assertNotIn('XPS 13', html)


class VigenciaVencidaTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar el mismo aviso, sin enlace de encuesta."""

    def test_plano_incluye_aviso_y_redes(self):
        """Feliz: vigencia vencida, próximos pasos y WhatsApp vacío."""
        texto = construir_texto_plano_vigencia_vencida(_contexto())
        self.assertIn('Aviso de cotización vencida', texto)
        self.assertIn('FL-3301', texto)
        self.assertIn('por falta de respuesta', texto)
        self.assertIn('ya no se encuentra vigente', texto)
        self.assertIn('hasta nuevo aviso', texto)
        self.assertIn('NO RESPONDA', texto)
        self.assertIn('WhatsApp: https://wa.me/', texto)
        self.assertNotIn('estrellas', texto)

    def test_plano_sin_modelo_no_inventa_equipo(self):
        """Sin modelo el plano tampoco lo menciona."""
        texto = construir_texto_plano_vigencia_vencida(_contexto(modelo_equipo=''))
        self.assertIn('Equipo: Dell', texto)
        self.assertNotIn('XPS 13', texto)
