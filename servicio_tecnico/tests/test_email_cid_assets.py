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
    """El helper pega solo el PNG blanco de la barra."""

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

    def test_los_envios_no_pegan_el_logo_azul(self):
        """El PNG azul sigue para PDF y favicon; ningún correo lo adjunta."""
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[2]
        # Estos archivos arman el mensaje. Si vuelve '<logo_sic>', el azul
        # viaja otra vez aunque la plantilla no lo muestre.
        archivos = [
            raiz / 'servicio_tecnico/tasks.py',
            raiz / 'servicio_tecnico/tasks_formato_venta_mostrador.py',
            raiz / 'servicio_tecnico/tasks_diagnostico.py',
            raiz / 'servicio_tecnico/tasks_pagos.py',
            raiz / 'almacen/tasks.py',
            raiz / 'almacen/tasks_solicitud_baja.py',
            raiz / 'almacen/tasks_vigencia_cotizacion.py',
            raiz / 'inventario/utils.py',
            raiz / 'scorecard/emails.py',
        ]
        for ruta in archivos:
            texto = ruta.read_text(encoding='utf-8')
            self.assertNotIn("'<logo_sic>'", texto, ruta.name)
