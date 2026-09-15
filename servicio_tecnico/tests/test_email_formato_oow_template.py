"""
Tests de la plantilla HTML y del texto plano del correo de formato OOW.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo. Solo se rellena el HTML y el text/plain para no
romper los {% if %} (contacto del técnico, WhatsApp, Service Tag vacío)
al pasar el diseño a tablas.
"""

from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_formato_oow import (
    construir_texto_plano_formato_oow,
)


PLANTILLA = 'servicio_tecnico/emails/formato_oow_cliente.html'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_formato_oow_email_task.

    Args:
        **overrides: Claves a cambiar (WhatsApp, serie vacía, etc.).

    Returns:
        dict: Contexto para render_to_string y texto plano.
    """
    detalle = SimpleNamespace(
        tipo_equipo='Laptop',
        marca='DELL',
        modelo='Latitude 5520',
        numero_serie='EMAILSTAG01',
    )
    orden = SimpleNamespace(
        numero_orden_interno='INT-8008',
        fecha_ingreso=datetime(2026, 9, 15, 10, 30),
    )
    contexto = {
        'orden': orden,
        'detalle': detalle,
        'orden_sicser': 'OOW-EMAIL01',
        'fecha_envio_texto': '15/09/2026',
        'hora_envio_texto': '12:00',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'email_empleado': 'tech@test.local',
        'nombre_empleado': 'Técnico Test',
        'whatsapp_empleado': '525512345678',
    }
    contexto.update(overrides)
    return contexto


class FormatoOowEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas, paleta SIC, copy de OOW."""

    def test_render_base_incluye_copy_y_layout(self):
        """Feliz: orden SICSER, Service Tag, 1 PDF y pie sicfix.mx."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('class="email-brandbar"', html)
        self.assertIn('bgcolor="#1e293b"', html)
        self.assertIn('role="presentation"', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('#667eea', html)
        self.assertNotIn('#2e7d32', html)

        self.assertIn('Formato de servicio fuera de garantía', html)
        self.assertIn('Orden: OOW-EMAIL01', html)
        self.assertIn('Buen día estimado usuario', html)
        self.assertIn('Formato de Servicio Fuera de Garantía (OOW)', html)
        self.assertIn('Laptop DELL Latitude 5520', html)
        self.assertIn('EMAILSTAG01', html)
        self.assertIn('1 PDF', html)
        self.assertIn('formato oficial de servicio firmado', html)
        self.assertIn('https://sicfix.mx/', html)
        self.assertIn('Visítanos y síguenos', html)
        self.assertIn('tech@test.local', html)
        self.assertIn('Técnico Test', html)
        self.assertIn('https://wa.me/525512345678', html)
        self.assertNotIn('Estimado(a) cliente', html)

    def test_sin_service_tag_muestra_guion(self):
        """Sin número de serie el HTML pinta el guion largo —."""
        contexto = _contexto()
        contexto['detalle'].numero_serie = ''
        html = render_to_string(PLANTILLA, contexto)
        self.assertIn('—', html)
        self.assertNotIn('EMAILSTAG01', html)

    def test_sin_empleado_omite_contacto_y_whatsapp(self):
        """Sin técnico: “su responsable de seguimiento” y sin WhatsApp."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                email_empleado='',
                nombre_empleado='',
                whatsapp_empleado='',
            ),
        )
        self.assertIn('su responsable de seguimiento', html)
        self.assertNotIn('Contacto:', html)
        self.assertNotIn('wa.me/', html)
        self.assertNotIn('Técnico Test', html)


class FormatoOowTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar la orden SICSER, el PDF y el mismo pie."""

    def test_plano_incluye_orden_pdf_y_contacto(self):
        """Feliz: documento firmado, datos del equipo y WhatsApp."""
        texto = construir_texto_plano_formato_oow(_contexto())
        self.assertIn('Formato de Servicio Fuera de Garantía (OOW)', texto)
        self.assertIn('OOW-EMAIL01', texto)
        self.assertIn('EMAILSTAG01', texto)
        self.assertIn('1 PDF', texto)
        self.assertIn('Técnico Test (tech@test.local)', texto)
        self.assertIn('https://sicfix.mx/', texto)
        self.assertIn('https://wa.me/525512345678', texto)
        self.assertIn('NO RESPONDA', texto)
        self.assertNotIn('Estimado(a) cliente', texto)

    def test_plano_sin_serie_usa_guion(self):
        """Sin Service Tag el plano usa —."""
        contexto = _contexto()
        contexto['detalle'].numero_serie = ''
        texto = construir_texto_plano_formato_oow(contexto)
        self.assertIn('Service Tag: —', texto)

    def test_plano_sin_empleado_usa_responsable(self):
        """Sin técnico: el plano no inventa WhatsApp ni mailto."""
        texto = construir_texto_plano_formato_oow(
            _contexto(
                email_empleado='',
                nombre_empleado='',
                whatsapp_empleado='',
            ),
        )
        self.assertIn('su responsable de seguimiento', texto)
        self.assertNotIn('Contacto:', texto)
        self.assertNotIn('wa.me/', texto)
