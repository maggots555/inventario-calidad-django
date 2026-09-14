"""
Tests de la plantilla HTML y del texto plano del correo de formato garantía.

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

from servicio_tecnico.services.email_formato_garantia import (
    construir_texto_plano_formato_garantia,
)


PLANTILLA = 'servicio_tecnico/emails/formato_garantia_cliente.html'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_formato_garantia_email_task.

    Args:
        **overrides: Claves a cambiar (WhatsApp, serie vacía, etc.).

    Returns:
        dict: Contexto para render_to_string y texto plano.
    """
    detalle = SimpleNamespace(
        tipo_equipo='Laptop',
        marca='Dell',
        modelo='Latitude 7430',
        numero_serie='GARSTAG01',
    )
    orden = SimpleNamespace(
        numero_orden_interno='INT-7007',
        fecha_ingreso=datetime(2026, 9, 14, 10, 30),
    )
    contexto = {
        'orden': orden,
        'detalle': detalle,
        'orden_sicser': '999888777',
        'fecha_envio_texto': '14/09/2026',
        'hora_envio_texto': '11:00',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'email_empleado': 'tech@test.local',
        'nombre_empleado': 'Técnico Test',
        'whatsapp_empleado': '525512345678',
    }
    contexto.update(overrides)
    return contexto


class FormatoGarantiaEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas, paleta SIC, copy de garantía Dell."""

    def test_render_base_incluye_copy_y_layout(self):
        """Feliz: DPS, Service Tag, 1 PDF y pie sicfix.mx."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic', html)
        self.assertIn('role="presentation"', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('#667eea', html)
        self.assertNotIn('#2e7d32', html)

        self.assertIn('Formato de servicio garantía Dell', html)
        self.assertIn('Orden (DPS): 999888777', html)
        self.assertIn('Buen día estimado usuario', html)
        self.assertIn('Formato de Servicio en Garantía Dell', html)
        self.assertIn('Laptop Dell Latitude 7430', html)
        self.assertIn('GARSTAG01', html)
        self.assertIn('1 PDF', html)
        self.assertIn('formato oficial de servicio en garantía firmado', html)
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
        self.assertNotIn('GARSTAG01', html)

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


class FormatoGarantiaTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar el DPS, el PDF y el mismo pie."""

    def test_plano_incluye_dps_pdf_y_contacto(self):
        """Feliz: documento firmado, datos del equipo y WhatsApp."""
        texto = construir_texto_plano_formato_garantia(_contexto())
        self.assertIn('Formato de Servicio en Garantía Dell', texto)
        self.assertIn('999888777', texto)
        self.assertIn('GARSTAG01', texto)
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
        texto = construir_texto_plano_formato_garantia(contexto)
        self.assertIn('Service Tag: —', texto)

    def test_plano_sin_empleado_usa_responsable(self):
        """Sin técnico: el plano no inventa WhatsApp ni mailto."""
        texto = construir_texto_plano_formato_garantia(
            _contexto(
                email_empleado='',
                nombre_empleado='',
                whatsapp_empleado='',
            ),
        )
        self.assertIn('su responsable de seguimiento', texto)
        self.assertNotIn('Contacto:', texto)
        self.assertNotIn('wa.me/', texto)
