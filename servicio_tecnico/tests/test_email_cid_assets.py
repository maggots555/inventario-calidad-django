"""
Tests del adjunto CID del logo SIC blanco (barra de marca de correos).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No enviamos correo. Creamos un mensaje de mentira con un método
``attach`` y comprobamos que se pega un PNG con Content-ID
``logo_sic_white`` (el HTML usa src="cid:logo_sic_white").
"""

from email.mime.image import MIMEImage
from unittest.mock import patch

from django.test import SimpleTestCase

from servicio_tecnico.services.email_cid_assets import adjuntar_logo_blanco_email


class _MensajeFalso:
    """Sustituto mínimo de EmailMessage: solo guarda lo que se adjunta."""

    def __init__(self):
        self.partes = []

    def attach(self, parte):
        self.partes.append(parte)


class AdjuntarLogoBlancoEmailTests(SimpleTestCase):
    """El helper debe pegar el PNG blanco sin tocar cid:logo_sic."""

    def test_adjunta_png_con_cid_logo_sic_white(self):
        """Feliz: finders encuentra el PNG y el CID coincide con la plantilla."""
        mensaje = _MensajeFalso()
        ok = adjuntar_logo_blanco_email(mensaje, '[TEST]')

        self.assertTrue(ok)
        self.assertEqual(len(mensaje.partes), 1)
        parte = mensaje.partes[0]
        self.assertIsInstance(parte, MIMEImage)
        self.assertEqual(parte['Content-ID'], '<logo_sic_white>')
        self.assertIn('logo_sic_white.png', parte['Content-Disposition'])

    def test_sin_archivo_devuelve_false_y_no_adjunta(self):
        """Si el PNG no está en static/, no se rompe el envío del correo."""
        mensaje = _MensajeFalso()
        with patch(
            'servicio_tecnico.services.email_cid_assets.finders.find',
            return_value=None,
        ):
            ok = adjuntar_logo_blanco_email(mensaje, '[TEST]')

        self.assertFalse(ok)
        self.assertEqual(mensaje.partes, [])
