"""
Tests de la plantilla HTML y del texto plano del correo de envío RHITSO.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No enviamos un correo real. Solo pedimos a Django que “rellene” el HTML
(`render_to_string`) y el texto plano con datos de mentira (SimpleNamespace).
Así comprobamos que las etiquetas {% if %} no se rompieron al rediseñar
el correo a tablas (Gmail/Outlook no entienden flex ni CSS de página web).
"""

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_rhitso_envio import (
    construir_texto_plano_rhitso_envio,
)


PLANTILLA = 'servicio_tecnico/emails/rhitso_envio.html'


def _contexto(**overrides):
    """
    Arma un contexto mínimo igual al que usa la tarea Celery.

    Args:
        **overrides: Claves que queremos cambiar en un test concreto
            (por ejemplo un ``orden`` sin detalle).

    Returns:
        dict: Contexto listo para render_to_string.
    """
    detalle = SimpleNamespace(
        orden_cliente='OOW-09647',
        marca='Dell',
        modelo='Inspiron 15 3535',
        numero_serie='SN-RHITSO-01',
        numero_serie_cargador='CHG-001',
    )
    orden = SimpleNamespace(
        numero_orden_interno='INT-2048',
        descripcion_rhitso='No enciende, posible falla en motherboard.',
        detalle_equipo=detalle,
    )
    contexto = {
        'orden': orden,
        'fecha_envio_texto': '15/09/2026',
        'hora_envio_texto': '11:40',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
    }
    contexto.update(overrides)
    return contexto


class RhitsoEnvioEmailTemplateTests(SimpleTestCase):
    """
    El HTML debe ser un correo de tablas, paleta SIC, y respetar los if.
    """

    def test_render_base_incluye_datos_y_layout_de_correo(self):
        """Feliz: orden, serie, tablas 600px, paleta SIC, contacto actual."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Envío de equipo RHITSO', html)
        self.assertIn('Buen día Team RHITSO', html)
        self.assertIn('Enviamos equipo para revisión especializada', html)
        self.assertIn('OOW-09647', html)
        self.assertIn('SN-RHITSO-01', html)
        self.assertIn('Dell', html)
        self.assertIn('Inspiron 15 3535', html)
        self.assertIn('CHG-001', html)
        self.assertIn('No enciende, posible falla en motherboard.', html)
        self.assertIn('Alejandro García', html)
        self.assertIn('55-35-45-81-92', html)
        self.assertIn('cis_mex@sic.com.mx', html)
        self.assertIn('Formato RHITSO (PDF)', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('class="email-brandbar"', html)
        self.assertIn('bgcolor="#1e293b"', html)
        self.assertIn('SIC México', html)
        self.assertIn('Saludos cordiales', html)
        # Correo operativo con el laboratorio: no copiamos el aviso al cliente.
        self.assertNotIn('NO RESPONDA', html)
        # CSS de página web que Outlook rompe / paleta genérica de IA
        self.assertNotIn('display:flex', html)
        self.assertNotIn('display:grid', html)
        self.assertNotIn('#667eea', html)
        self.assertNotIn('#764ba2', html)

    def test_sin_detalle_usa_fallbacks(self):
        """Borde: sin detalle/serie/cargador/falla → N/A, SIN CARGADOR, No especificado."""
        orden = SimpleNamespace(
            numero_orden_interno='INT-2048',
            descripcion_rhitso='',
            detalle_equipo=None,
        )
        html = render_to_string(PLANTILLA, _contexto(orden=orden))

        self.assertIn('INT-2048', html)
        self.assertIn('N/A', html)
        self.assertIn('SIN CARGADOR', html)
        self.assertIn('No especificado', html)
        self.assertNotIn('OOW-09647', html)
        self.assertNotIn('SN-RHITSO-01', html)


class RhitsoEnvioTextoPlanoTests(SimpleTestCase):
    """El text/plain debe decir lo mismo que el HTML (paridad de la skill)."""

    def test_texto_plano_incluye_nucleo_sin_no_responda(self):
        """Feliz: saludo, orden, contacto, adjuntos; sin aviso de no responder."""
        texto = construir_texto_plano_rhitso_envio(_contexto())
        self.assertIn('Buen día Team RHITSO', texto)
        self.assertIn('OOW-09647', texto)
        self.assertIn('SN-RHITSO-01', texto)
        self.assertIn('Dell Inspiron 15 3535', texto)
        self.assertIn('CHG-001', texto)
        self.assertIn('No enciende, posible falla en motherboard.', texto)
        self.assertIn('Alejandro García', texto)
        self.assertIn('cis_mex@sic.com.mx', texto)
        self.assertIn('Formato RHITSO (PDF)', texto)
        self.assertIn('Imágenes de evidencia', texto)
        self.assertIn('SIC México', texto)
        self.assertIn('https://sicfix.mx/', texto)
        self.assertNotIn('NO RESPONDA', texto)

    def test_texto_plano_sin_detalle_usa_fallbacks(self):
        """Borde: los mismos N/A / SIN CARGADOR / No especificado que el HTML."""
        orden = SimpleNamespace(
            numero_orden_interno='INT-2048',
            descripcion_rhitso='',
            detalle_equipo=None,
        )
        texto = construir_texto_plano_rhitso_envio(_contexto(orden=orden))
        self.assertIn('Orden: INT-2048', texto)
        self.assertIn('Número de serie: N/A', texto)
        self.assertIn('Modelo: N/A', texto)
        self.assertIn('Cargador: SIN CARGADOR', texto)
        self.assertIn('Descripción de la falla: No especificado', texto)
        self.assertNotIn('OOW-09647', texto)
