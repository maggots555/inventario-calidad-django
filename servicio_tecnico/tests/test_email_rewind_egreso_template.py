"""
Tests de la plantilla HTML y del texto plano del correo rewind de egreso.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo. Solo se rellena el HTML y el text/plain para no
romper los {% if %} (venta mostrador, thumbnail, seguimiento, cargador).
"""

from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_rewind_egreso import (
    construir_texto_plano_rewind_egreso,
)


PLANTILLA = 'servicio_tecnico/emails/rewind_egreso_cliente.html'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_rewind_egreso_email_task.

    Args:
        **overrides: Claves a cambiar (VM, thumbnail, URL, etc.).

    Returns:
        dict: Contexto para render_to_string.
    """
    detalle = SimpleNamespace(
        orden_cliente='FL-6006',
        tipo_equipo='Laptop',
        marca='Dell',
        modelo='XPS 13',
        numero_serie='SN-REWIND-001',
        tiene_cargador=True,
        numero_serie_cargador='CHG-006',
    )
    orden = SimpleNamespace(
        numero_orden_interno='INT-6006',
        fecha_ingreso=datetime(2026, 9, 1, 9, 0),
        fecha_finalizacion=datetime(2026, 9, 14, 16, 0),
    )
    contexto = {
        'orden': orden,
        'detalle': detalle,
        'fecha_envio_texto': '14/09/2026',
        'hora_envio_texto': '16:20',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'whatsapp_empleado': '525512345678',
        'seguimiento_url': 'https://app.sigmasystem.work/seguimiento/token-rewind/',
        'thumbnail_disponible': True,
        'video_url': 'https://app.sigmasystem.work/media/rewind.mp4',
        'es_venta_mostrador': False,
    }
    contexto.update(overrides)
    return contexto


class RewindEgresoEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas, paleta SIC, aviso de no recoger."""

    def test_render_base_incluye_video_y_layout(self):
        """Feliz ST: diagnóstico en el copy, thumbnail CID y CTA."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Resumen de tu servicio', html)
        self.assertIn('Estimado/a cliente,', html)
        self.assertIn('el diagnóstico, la reparación', html)
        self.assertIn('ingreso, diagnóstico, reparación y egreso', html)
        self.assertIn('cid:thumbnail_video', html)
        self.assertIn('https://app.sigmasystem.work/media/rewind.mp4', html)
        self.assertIn('Toca aquí para reproducir el video', html)
        self.assertIn('Ver el estado de mi equipo', html)
        self.assertIn('fillcolor="#1f6391"', html)
        self.assertIn('FL-6006', html)
        self.assertIn('Confirme disponibilidad antes de recoger', html)
        self.assertIn('notificación de disponibilidad', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('class="email-brandbar"', html)
        self.assertIn('bgcolor="#1e293b"', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)

    def test_venta_mostrador_omite_diagnostico(self):
        """Venta mostrador: el copy no menciona diagnóstico."""
        html = render_to_string(PLANTILLA, _contexto(es_venta_mostrador=True))
        self.assertIn('la reparación, hasta el resultado final', html)
        self.assertIn('ingreso, reparación y egreso', html)
        self.assertNotIn('el diagnóstico, la reparación', html)
        self.assertNotIn('ingreso, diagnóstico, reparación', html)

    def test_sin_thumbnail_omite_cid_y_conserva_descripcion(self):
        """Sin miniatura: no hay cid, sí el texto del video."""
        html = render_to_string(PLANTILLA, _contexto(thumbnail_disponible=False))
        self.assertNotIn('cid:thumbnail_video', html)
        self.assertNotIn('Toca aquí para reproducir el video', html)
        self.assertIn('Video resumen del proceso', html)
        self.assertIn('registrado fotográficamente', html)

    def test_sin_seguimiento_omite_cta(self):
        """Sin URL pública no se pinta el botón de estado."""
        html = render_to_string(PLANTILLA, _contexto(seguimiento_url=None))
        self.assertNotIn('Ver el estado de mi equipo', html)

    def test_sin_cargador_muestra_no_incluido(self):
        """Sin cargador: texto “No incluido”."""
        contexto = _contexto()
        contexto['detalle'].tiene_cargador = False
        contexto['detalle'].numero_serie_cargador = ''
        html = render_to_string(PLANTILLA, contexto)
        self.assertIn('No incluido', html)
        self.assertNotIn('CHG-006', html)


class RewindEgresoTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar la URL del video y el aviso de no recoger."""

    def test_plano_incluye_url_video_y_aviso(self):
        """Feliz: URL del video, seguimiento y cláusula de disponibilidad."""
        texto = construir_texto_plano_rewind_egreso(_contexto())
        self.assertIn('Resumen de tu servicio', texto)
        self.assertIn('el diagnóstico, la reparación', texto)
        self.assertIn('https://app.sigmasystem.work/media/rewind.mp4', texto)
        self.assertIn('https://app.sigmasystem.work/seguimiento/token-rewind/', texto)
        self.assertIn('Confirme disponibilidad antes de recoger', texto)
        self.assertIn('NO RESPONDA', texto)

    def test_plano_venta_mostrador_omite_diagnostico(self):
        """VM en plano: no menciona diagnóstico."""
        texto = construir_texto_plano_rewind_egreso(
            _contexto(es_venta_mostrador=True),
        )
        self.assertIn('ingreso, reparación y egreso', texto)
        self.assertNotIn('diagnóstico', texto)
