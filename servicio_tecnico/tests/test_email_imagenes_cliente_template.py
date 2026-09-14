"""
Tests de la plantilla HTML y del texto plano del correo de fotos de ingreso.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No enviamos un correo real. Solo pedimos a Django que “rellene” el HTML
(`render_to_string`) y el texto plano con datos de mentira (SimpleNamespace).
Así comprobamos que las etiquetas {% if %} no se rompieron al rediseñar
el correo a tablas (Gmail/Outlook no entienden flex ni CSS de página web).
"""

from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_imagenes_ingreso import (
    construir_texto_plano_imagenes_ingreso,
)


PLANTILLA = 'servicio_tecnico/emails/imagenes_cliente.html'


def _contexto(**overrides):
    """
    Arma un contexto mínimo igual al que usa la tarea Celery.

    Args:
        **overrides: Claves que queremos cambiar en un test concreto
            (por ejemplo analisis_ia_texto o seguimiento_url).

    Returns:
        dict: Contexto listo para render_to_string.
    """
    detalle = SimpleNamespace(
        orden_cliente='FL-1001',
        tipo_equipo='Laptop',
        marca='Dell',
        modelo='XPS 13',
        numero_serie='SN-TEST-001',
        nombre_cliente='Ana Pérez',
    )
    orden = SimpleNamespace(
        numero_orden_interno='INT-1001',
        fecha_ingreso=datetime(2026, 9, 14, 10, 30),
    )
    contexto = {
        'orden': orden,
        'detalle': detalle,
        'mensaje_personalizado': '',
        'fecha_envio_texto': '14/09/2026',
        'hora_envio_texto': '10:35',
        'cantidad_imagenes': 3,
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'whatsapp_empleado': '',
        'seguimiento_url': None,
        'analisis_ia_texto': None,
        'analisis_ia_modelo': None,
    }
    contexto.update(overrides)
    return contexto


class ImagenesClienteEmailTemplateTests(SimpleTestCase):
    """
    El HTML debe ser un correo de tablas, paleta SIC, y respetar los if.
    """

    def test_render_base_incluye_datos_y_layout_de_correo(self):
        """Feliz: orden, fotos, tablas 600px, paleta SIC, sin flex ni morado."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Fotografías de ingreso', html)
        self.assertIn('Recibimos su equipo y adjuntamos las fotografías de ingreso.', html)
        self.assertIn('FL-1001', html)
        self.assertIn('Laptop Dell XPS 13', html)
        self.assertIn('SN-TEST-001', html)
        self.assertIn('Ana Pérez', html)
        self.assertIn('3', html)
        self.assertIn('fotografía', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('class="email-brandbar"', html)
        self.assertIn('bgcolor="#1e293b"', html)
        # CSS de página web que Outlook rompe / paleta genérica de IA
        self.assertNotIn('display:flex', html)
        self.assertNotIn('#667eea', html)
        self.assertNotIn('#764ba2', html)

    def test_sin_nombre_usa_saludo_generico(self):
        """Si no hay nombre_cliente, se mantiene el saludo original."""
        contexto = _contexto()
        contexto['detalle'].nombre_cliente = ''
        html = render_to_string(PLANTILLA, contexto)
        self.assertIn('Estimado/a cliente,', html)
        self.assertNotIn('Estimado/a Ana', html)

    def test_con_analisis_ia_muestra_seccion(self):
        """Si la IA respondió, el análisis aparece en el HTML."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                analisis_ia_texto='Carcasa en buen estado, sin golpes visibles.',
                analisis_ia_modelo='gemini-test',
            ),
        )
        self.assertIn('Análisis de condición estética al ingreso', html)
        self.assertIn('Carcasa en buen estado, sin golpes visibles.', html)
        self.assertIn('gemini-test', html)

    def test_sin_analisis_ia_omite_seccion(self):
        """Si la IA falló, no se menciona el análisis (fail-safe)."""
        html = render_to_string(PLANTILLA, _contexto())
        self.assertNotIn('Análisis de condición estética al ingreso', html)

    def test_con_seguimiento_muestra_boton_y_url(self):
        """El CTA es HTML (no imagen) y lleva la URL pública."""
        url = 'https://app.sigmasystem.work/seguimiento/token-demo/'
        html = render_to_string(PLANTILLA, _contexto(seguimiento_url=url))
        self.assertIn(url, html)
        self.assertIn('Ver seguimiento de mi equipo', html)
        self.assertIn('fillcolor="#1f6391"', html)

    def test_sin_seguimiento_omite_boton(self):
        """Sin enlace de seguimiento no se pinta el botón."""
        html = render_to_string(PLANTILLA, _contexto(seguimiento_url=None))
        self.assertNotIn('Ver seguimiento de mi equipo', html)

    def test_mensaje_personalizado_aparece(self):
        """El recado del técnico se inserta cuando viene en el contexto."""
        html = render_to_string(
            PLANTILLA,
            _contexto(mensaje_personalizado='Equipo recibido con funda.'),
        )
        self.assertIn('Mensaje adicional', html)
        self.assertIn('Equipo recibido con funda.', html)


class ImagenesClienteTextoPlanoTests(SimpleTestCase):
    """El text/plain debe decir lo mismo que el HTML (paridad de la skill)."""

    def test_texto_plano_incluye_nucleo_y_omite_ia_si_falta(self):
        """Feliz: saludo, orden, fotos, sin bloque de IA ni URL."""
        texto = construir_texto_plano_imagenes_ingreso(_contexto())
        self.assertIn('Estimado/a Ana Pérez,', texto)
        self.assertIn('FL-1001', texto)
        self.assertIn('3 fotografías adjuntas', texto)
        self.assertIn('NO RESPONDA', texto)
        self.assertNotIn('ANÁLISIS DE CONDICIÓN', texto)
        self.assertNotIn('https://app.sigmasystem.work/seguimiento/', texto)

    def test_texto_plano_con_ia_y_seguimiento(self):
        """Borde: IA + URL de seguimiento viajan también en texto plano."""
        url = 'https://app.sigmasystem.work/seguimiento/token-demo/'
        texto = construir_texto_plano_imagenes_ingreso(
            _contexto(
                analisis_ia_texto='Pantalla sin rayones.',
                analisis_ia_modelo='gemini-test',
                seguimiento_url=url,
            )
        )
        self.assertIn('Pantalla sin rayones.', texto)
        self.assertIn('gemini-test', texto)
        self.assertIn(url, texto)
        self.assertIn('Consulte el estado de su equipo', texto)
