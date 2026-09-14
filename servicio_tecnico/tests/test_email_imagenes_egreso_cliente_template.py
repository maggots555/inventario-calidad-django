"""
Tests de la plantilla HTML y del texto plano del correo de fotos de egreso.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo. Solo se rellena el HTML y el text/plain para no
romper los {% if %} (fecha de finalización, cargador, seguimiento)
al pasar el diseño a tablas.
"""

from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_imagenes_egreso import (
    construir_texto_plano_imagenes_egreso,
)


PLANTILLA = 'servicio_tecnico/emails/imagenes_egreso_cliente.html'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_imagenes_egreso_cliente_task.

    Args:
        **overrides: Claves a cambiar (seguimiento, cargador, etc.).

    Returns:
        dict: Contexto para render_to_string.
    """
    detalle = SimpleNamespace(
        orden_cliente='FL-4004',
        tipo_equipo='Laptop',
        marca='Dell',
        modelo='XPS 13',
        numero_serie='SN-EGRESO-001',
        tiene_cargador=True,
        numero_serie_cargador='CHG-001',
    )
    orden = SimpleNamespace(
        numero_orden_interno='INT-4004',
        fecha_ingreso=datetime(2026, 9, 1, 9, 0),
        fecha_finalizacion=datetime(2026, 9, 14, 16, 0),
    )
    contexto = {
        'orden': orden,
        'detalle': detalle,
        'mensaje_personalizado': '',
        'fecha_envio_texto': '14/09/2026',
        'hora_envio_texto': '16:10',
        'cantidad_imagenes': 4,
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'whatsapp_empleado': '',
        'seguimiento_url': None,
    }
    contexto.update(overrides)
    return contexto


class ImagenesEgresoEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas, paleta SIC, aviso de no recoger."""

    def test_render_base_incluye_aviso_y_layout(self):
        """Feliz: aviso de no recoger, orden, fotos, sin flex ni emojis de título."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Fotografías de egreso', html)
        self.assertIn('Registro de estado final del equipo', html)
        self.assertIn('Estimado/a cliente,', html)
        self.assertIn('aún no está listo para ser recolectado', html)
        self.assertIn('NO es una confirmación de que puede acudir a recoger su equipo', html)
        self.assertIn('FL-4004', html)
        self.assertIn('Laptop Dell XPS 13', html)
        self.assertIn('SN-EGRESO-001', html)
        self.assertIn('Incluido', html)
        self.assertIn('CHG-001', html)
        self.assertIn('14/09/2026 16:00', html)
        self.assertIn('4', html)
        self.assertIn('notificación de disponibilidad', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('class="email-brandbar"', html)
        self.assertIn('bgcolor="#1e293b"', html)
        self.assertIn('https://sicfix.mx/', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('#667eea', html)
        self.assertNotIn('Ver seguimiento de mi equipo', html)

    def test_sin_fecha_finalizacion_omite_fila(self):
        """Si la orden aún no tiene fecha de cierre, no se pinta esa fila."""
        contexto = _contexto()
        contexto['orden'].fecha_finalizacion = None
        html = render_to_string(PLANTILLA, contexto)
        self.assertNotIn('Fecha de finalización', html)

    def test_sin_cargador_muestra_no_incluido(self):
        """Sin cargador: texto “No incluido”, sin número de serie."""
        contexto = _contexto()
        contexto['detalle'].tiene_cargador = False
        contexto['detalle'].numero_serie_cargador = ''
        html = render_to_string(PLANTILLA, contexto)
        self.assertIn('No incluido', html)
        self.assertNotIn('CHG-001', html)

    def test_con_seguimiento_muestra_boton_en_tu(self):
        """El CTA conserva el tuteo original y la URL pública."""
        url = 'https://app.sigmasystem.work/seguimiento/token-egreso/'
        html = render_to_string(PLANTILLA, _contexto(seguimiento_url=url))
        self.assertIn(url, html)
        self.assertIn('Consulta el <strong>estado de tu equipo</strong>', html)
        self.assertIn('Ver seguimiento de mi equipo', html)
        self.assertIn('fillcolor="#1f6391"', html)

    def test_mensaje_personalizado_aparece(self):
        """El recado extra se inserta cuando viene en el contexto."""
        html = render_to_string(
            PLANTILLA,
            _contexto(mensaje_personalizado='Equipo limpio y empacado.'),
        )
        self.assertIn('Mensaje adicional', html)
        self.assertIn('Equipo limpio y empacado.', html)


class ImagenesEgresoTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar el aviso de no recoger y la misma URL."""

    def test_texto_plano_incluye_aviso_y_omite_url_si_falta(self):
        """Feliz: aviso, orden, fotos, sin seguimiento."""
        texto = construir_texto_plano_imagenes_egreso(_contexto())
        self.assertIn('Estimado/a cliente,', texto)
        self.assertIn('aún no está listo para ser recolectado', texto)
        self.assertIn('NO es una confirmación', texto)
        self.assertIn('FL-4004', texto)
        self.assertIn('4 fotografía', texto)
        self.assertIn('Incluido (S/N: CHG-001)', texto)
        self.assertIn('NO RESPONDA', texto)
        self.assertNotIn('https://app.sigmasystem.work/seguimiento/', texto)

    def test_texto_plano_con_seguimiento_lleva_la_misma_url(self):
        """Borde: la URL pública viaja también en texto plano."""
        url = 'https://app.sigmasystem.work/seguimiento/token-egreso/'
        texto = construir_texto_plano_imagenes_egreso(
            _contexto(seguimiento_url=url),
        )
        self.assertIn(url, texto)
        self.assertIn('Consulta el estado de tu equipo', texto)
