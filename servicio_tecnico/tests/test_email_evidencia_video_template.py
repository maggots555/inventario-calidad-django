"""
Tests de la plantilla HTML y del texto plano del correo de evidencia en video.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo. Solo se rellena el HTML y el text/plain para no
romper los {% if %} (IA, miniatura, URL, mensaje, seguimiento, WhatsApp).
"""

from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_evidencia_video import (
    construir_texto_plano_evidencia_video,
)


PLANTILLA = 'servicio_tecnico/emails/evidencia_video_cliente.html'


def _video(**overrides):
    """
    Un video de mentira, igual a un elemento de videos_data.

    Args:
        **overrides: Campos a cambiar (sin miniatura, sin URL, etc.).

    Returns:
        dict: Datos que la plantilla espera de un video.
    """
    video = {
        'id': 41,
        'tipo_display': 'Diagnóstico',
        'descripcion': 'Prueba de encendido',
        'duracion': '1:20',
        'tamano': '12.5',
        'tiene_thumbnail': True,
        'video_url': 'https://app.sigmasystem.work/media/evidencia-41.mp4',
    }
    video.update(overrides)
    return video


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_evidencia_video_task.

    Args:
        **overrides: Claves a cambiar (IA, mensaje, seguimiento, etc.).

    Returns:
        dict: Contexto para render_to_string.
    """
    detalle = SimpleNamespace(
        orden_cliente='FL-7041',
        tipo_equipo='Laptop',
        marca='Dell',
        modelo='XPS 13',
        numero_serie='SN-VIDEO-001',
    )
    orden = SimpleNamespace(
        numero_orden_interno='INT-7041',
        fecha_ingreso=datetime(2026, 9, 2, 11, 15),
    )
    contexto = {
        'orden': orden,
        'detalle': detalle,
        'fecha_envio_texto': '14/09/2026',
        'hora_envio_texto': '11:40',
        'cantidad_videos': 1,
        'videos_data': [_video()],
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'whatsapp_empleado': '',
        'seguimiento_url': None,
        'analisis_ia_texto': None,
        'analisis_ia_modelo': None,
        'mensaje_personalizado': '',
    }
    contexto.update(overrides)
    return contexto


class EvidenciaVideoEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas, paleta SIC, y respetar los if."""

    def test_render_base_incluye_video_y_layout(self):
        """Feliz: orden, miniatura CID, URL y layout de 600 px."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Evidencia en video del servicio', html)
        self.assertIn('Registro Visual del Proceso de Reparación', html)
        self.assertIn('Estimado/a cliente,', html)
        self.assertIn('proceso de diagnóstico y reparación', html)
        self.assertIn('FL-7041', html)
        self.assertIn('Laptop Dell', html)
        self.assertIn('XPS 13', html)
        self.assertIn('SN-VIDEO-001', html)
        self.assertIn('Videos de evidencia (1)', html)
        self.assertIn('Diagnóstico', html)
        self.assertIn('cid:thumb_video_41', html)
        self.assertIn('https://app.sigmasystem.work/media/evidencia-41.mp4', html)
        self.assertIn('Reproducir video', html)
        self.assertIn('"Prueba de encendido"', html)
        self.assertIn('1:20', html)
        self.assertIn('12.5 MB', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('class="email-brandbar"', html)
        self.assertIn('bgcolor="#1e293b"', html)
        self.assertIn('fillcolor="#1f6391"', html)
        self.assertIn('Sitio Web', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('#667eea', html)
        self.assertNotIn('object-fit', html)

    def test_sin_orden_cliente_usa_numero_interno(self):
        """Si no hay folio de cliente, se muestra la orden interna."""
        contexto = _contexto()
        contexto['detalle'].orden_cliente = ''
        html = render_to_string(PLANTILLA, contexto)
        self.assertIn('INT-7041', html)
        self.assertNotIn('FL-7041', html)

    def test_con_analisis_ia_muestra_seccion(self):
        """Si la IA respondió, el resumen aparece en el HTML."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                analisis_ia_texto='Se observa el equipo encendiendo.',
                analisis_ia_modelo='gemini-test',
            ),
        )
        self.assertIn('Resumen Ejecutivo del Servicio', html)
        self.assertIn('Se observa el equipo encendiendo.', html)
        self.assertIn('gemini-test', html)

    def test_sin_analisis_ia_omite_seccion(self):
        """Si la IA falló, no se menciona el resumen."""
        html = render_to_string(PLANTILLA, _contexto())
        self.assertNotIn('Resumen Ejecutivo del Servicio', html)

    def test_sin_thumbnail_omite_cid_y_conserva_boton(self):
        """Sin miniatura: no hay cid, sí el enlace para reproducir."""
        html = render_to_string(
            PLANTILLA,
            _contexto(videos_data=[_video(tiene_thumbnail=False)]),
        )
        self.assertNotIn('cid:thumb_video_41', html)
        self.assertIn('Reproducir video', html)
        self.assertIn('Diagnóstico', html)

    def test_sin_url_omite_boton(self):
        """Sin URL no se pinta el botón de reproducir."""
        html = render_to_string(
            PLANTILLA,
            _contexto(videos_data=[_video(video_url='')]),
        )
        self.assertNotIn('Reproducir video', html)
        self.assertIn('cid:thumb_video_41', html)

    def test_mensaje_y_seguimiento_opcionales(self):
        """Mensaje y seguimiento solo aparecen si vienen en el contexto."""
        html = render_to_string(PLANTILLA, _contexto())
        self.assertNotIn('Mensaje adicional del equipo:', html)
        self.assertNotIn('Ver seguimiento de mi equipo', html)

        html_extra = render_to_string(
            PLANTILLA,
            _contexto(
                mensaje_personalizado='Ya puede revisar los videos.',
                seguimiento_url='https://app.sigmasystem.work/seguimiento/token-video/',
                whatsapp_empleado='525512345678',
            ),
        )
        self.assertIn('Mensaje adicional del equipo:', html_extra)
        self.assertIn('Ya puede revisar los videos.', html_extra)
        self.assertIn('Consulta el', html_extra)
        self.assertIn('estado de tu equipo', html_extra)
        self.assertIn('Ver seguimiento de mi equipo', html_extra)
        self.assertIn('https://wa.me/525512345678', html_extra)

    def test_dos_videos_conservan_sus_cid(self):
        """El ciclo pinta un CID distinto por video."""
        videos = [
            _video(),
            _video(
                id=42,
                tipo_display='Reparación',
                descripcion='',
                duracion='',
                tamano='',
                video_url='https://app.sigmasystem.work/media/evidencia-42.mp4',
            ),
        ]
        html = render_to_string(
            PLANTILLA,
            _contexto(cantidad_videos=2, videos_data=videos),
        )
        self.assertIn('Videos de evidencia (2)', html)
        self.assertIn('cid:thumb_video_41', html)
        self.assertIn('cid:thumb_video_42', html)
        self.assertIn('Reparación', html)


class EvidenciaVideoTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar las mismas URLs y el mismo aviso."""

    def test_plano_incluye_url_video_y_aviso(self):
        """Feliz: URL del video, datos del equipo y aviso de no responder."""
        texto = construir_texto_plano_evidencia_video(_contexto())
        self.assertIn('Evidencia en video del servicio', texto)
        self.assertIn('proceso de diagnóstico y reparación', texto)
        self.assertIn('FL-7041', texto)
        self.assertIn('https://app.sigmasystem.work/media/evidencia-41.mp4', texto)
        self.assertIn('Reproducir video:', texto)
        self.assertIn('registro de calidad y transparencia', texto)
        self.assertIn('NO RESPONDA', texto)
        self.assertNotIn('Resumen Ejecutivo', texto)

    def test_plano_incluye_ia_mensaje_y_seguimiento(self):
        """Opcionales: IA, mensaje, seguimiento y WhatsApp."""
        texto = construir_texto_plano_evidencia_video(
            _contexto(
                analisis_ia_texto='Se observa el equipo encendiendo.',
                analisis_ia_modelo='gemini-test',
                mensaje_personalizado='Ya puede revisar los videos.',
                seguimiento_url='https://app.sigmasystem.work/seguimiento/token-video/',
                whatsapp_empleado='525512345678',
            ),
        )
        self.assertIn('Se observa el equipo encendiendo.', texto)
        self.assertIn('gemini-test', texto)
        self.assertIn('Ya puede revisar los videos.', texto)
        self.assertIn('https://app.sigmasystem.work/seguimiento/token-video/', texto)
        self.assertIn('https://wa.me/525512345678', texto)
