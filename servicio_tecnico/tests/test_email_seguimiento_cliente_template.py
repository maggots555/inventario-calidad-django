"""
Tests de la plantilla HTML y del texto plano del correo de seguimiento.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo real. Solo se rellena el HTML y el texto plano con
datos de prueba, para no romper los {% if %} al pasar el diseño a tablas.
"""

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_seguimiento_cliente import (
    construir_texto_plano_seguimiento_cliente,
)


PLANTILLA = 'servicio_tecnico/emails/seguimiento_cliente.html'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_seguimiento_cliente_task.

    Args:
        **overrides: Claves a cambiar (responsable, URL, etc.).

    Returns:
        dict: Contexto para render_to_string.
    """
    contexto = {
        'folio': 'FL-2002',
        'marca_equipo': 'Dell',
        'modelo_equipo': 'XPS 13',
        'tipo_equipo': 'Laptop',
        'seguimiento_url': 'https://app.sigmasystem.work/seguimiento/token-demo/',
        'nombre_responsable': 'María López',
        'email_responsable': 'maria.lopez@sic.local',
        'fecha_envio': '14/09/2026',
    }
    contexto.update(overrides)
    return contexto


class SeguimientoClienteEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas, paleta SIC, mismos textos."""

    def test_render_base_incluye_folio_cta_y_layout(self):
        """Feliz: folio, URL, tablas 600px, sin flex ni gradiente de layout."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Seguimiento de tu equipo', html)
        self.assertIn('FL-2002', html)
        self.assertIn('Laptop — Dell XPS 13', html)
        self.assertIn('https://app.sigmasystem.work/seguimiento/token-demo/', html)
        self.assertIn('Ver estado de mi equipo', html)
        self.assertIn('María López', html)
        self.assertIn('maria.lopez@sic.local', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)

    def test_sin_responsable_muestra_pendiente(self):
        """Si aún no hay responsable, se ve el texto de pendiente."""
        html = render_to_string(
            PLANTILLA,
            _contexto(nombre_responsable=None, email_responsable=None),
        )
        self.assertIn('Pendiente de asignar', html)
        self.assertIn('Se te notificará cuando se asigne a tu responsable.', html)
        self.assertNotIn('María López', html)


class SeguimientoClienteTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar la misma URL que el HTML."""

    def test_texto_plano_incluye_url_y_folio(self):
        """Feliz: folio, equipo, CTA y responsable en texto."""
        url = 'https://app.sigmasystem.work/seguimiento/token-demo/'
        texto = construir_texto_plano_seguimiento_cliente(_contexto())
        self.assertIn('FL-2002', texto)
        self.assertIn('Laptop — Dell XPS 13', texto)
        self.assertIn(url, texto)
        self.assertIn('María López', texto)
        self.assertNotIn('Pendiente de asignar', texto)

    def test_texto_plano_sin_responsable(self):
        """Borde: sin responsable, el plano replica el HTML."""
        texto = construir_texto_plano_seguimiento_cliente(
            _contexto(nombre_responsable=None, email_responsable=None)
        )
        self.assertIn('Pendiente de asignar', texto)
        self.assertIn('Se te notificará cuando se asigne a tu responsable.', texto)
