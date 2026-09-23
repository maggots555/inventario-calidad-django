"""
Tests de la plantilla HTML y del texto plano de la Nota de Venta Directa.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo ni PDF. Solo se rellena el HTML y el text/plain para
no romper los {% if %} (contacto, WhatsApp, Service Tag vacío).
"""

from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_formato_venta_mostrador import (
    construir_texto_plano_formato_venta_mostrador,
)


PLANTILLA = 'servicio_tecnico/emails/formato_venta_mostrador_cliente.html'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_formato_venta_mostrador_email_task.

    Args:
        **overrides: Claves a cambiar (WhatsApp, serie vacía, etc.).

    Returns:
        dict: Contexto para render_to_string y texto plano.
    """
    detalle = SimpleNamespace(
        tipo_equipo='Laptop',
        marca='Dell',
        modelo='XPS 13',
        numero_serie='SN-VM-001',
    )
    orden = SimpleNamespace(
        numero_orden_interno='INT-9009',
        fecha_ingreso=datetime(2026, 9, 15, 10, 30),
    )
    contexto = {
        'orden': orden,
        'detalle': detalle,
        'orden_sicser': 'FL-9009',
        'nombre_cliente': '',
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


class FormatoVentaMostradorEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas y conservar la nota de venta."""

    def test_render_base_incluye_copy_y_layout(self):
        """Feliz: orden, Service Tag, 1 PDF y pie sicfix.mx."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Nota de venta directa', html)
        self.assertIn('Orden: FL-9009', html)
        self.assertIn('Buen día estimado/a usuario', html)
        self.assertNotIn('Buen día estimado usuario', html)
        self.assertIn('Nota de Venta Directa', html)
        self.assertIn('y/o piezas adquiridos', html)
        self.assertIn('Laptop Dell', html)
        self.assertIn('XPS 13', html)
        self.assertIn('SN-VM-001', html)
        self.assertIn('1 PDF', html)
        self.assertIn('nota de venta de los servicios adquiridos', html)
        self.assertIn('SIC México', html)
        self.assertIn('tech@test.local', html)
        self.assertIn('Técnico Test', html)
        self.assertIn('https://wa.me/525512345678', html)
        self.assertIn('Sitio Web', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)

    def test_sin_service_tag_muestra_guion(self):
        """Sin número de serie el HTML pinta el guion largo."""
        contexto = _contexto()
        contexto['detalle'].numero_serie = ''
        html = render_to_string(PLANTILLA, contexto)
        self.assertIn('—', html)
        self.assertNotIn('SN-VM-001', html)

    def test_sin_empleado_omite_contacto_y_whatsapp(self):
        """Sin técnico: responsable de seguimiento y sin WhatsApp."""
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

    def test_con_nombre_saluda_a_esa_persona(self):
        """Si hay nombre, el saludo lo usa y no dice “usuario”."""
        html = render_to_string(
            PLANTILLA,
            _contexto(nombre_cliente='Ana Pérez'),
        )
        self.assertIn('Buen día estimado/a Ana Pérez', html)
        self.assertNotIn('estimado/a usuario', html)


class NombreParaSaludoTests(SimpleTestCase):
    """El saludo prefiere la persona de contacto y, si no hay, el cliente."""

    def test_persona_contacto_gana_sobre_nombre_de_orden(self):
        """Si el formato tiene contacto, ese nombre es el del saludo."""
        from servicio_tecnico.services.email_formato_venta_mostrador import (
            nombre_para_saludo,
        )

        formato = SimpleNamespace(persona_contacto='Ana Pérez')
        detalle = SimpleNamespace(nombre_cliente='Empresa SA')
        self.assertEqual(nombre_para_saludo(formato, detalle), 'Ana Pérez')

    def test_sin_contacto_usa_nombre_cliente(self):
        """Sin persona de contacto se usa el nombre de la orden."""
        from servicio_tecnico.services.email_formato_venta_mostrador import (
            nombre_para_saludo,
        )

        formato = SimpleNamespace(persona_contacto='')
        detalle = SimpleNamespace(nombre_cliente='Luis Gómez')
        self.assertEqual(nombre_para_saludo(formato, detalle), 'Luis Gómez')

    def test_sin_nombre_queda_vacio(self):
        """Sin ninguno, el correo cae en “usuario”."""
        from servicio_tecnico.services.email_formato_venta_mostrador import (
            nombre_para_saludo,
        )

        formato = SimpleNamespace(persona_contacto='  ')
        self.assertEqual(nombre_para_saludo(formato, None), '')


class FormatoVentaMostradorTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar la nota, el PDF y el mismo pie."""

    def test_plano_incluye_nota_pdf_y_contacto(self):
        """Feliz: documento adjunto, datos del equipo y WhatsApp."""
        texto = construir_texto_plano_formato_venta_mostrador(_contexto())
        self.assertIn('Buen día estimado/a usuario', texto)
        self.assertIn('Nota de Venta Directa', texto)
        self.assertIn('FL-9009', texto)
        self.assertIn('SN-VM-001', texto)
        self.assertIn('1 PDF', texto)
        self.assertIn('Técnico Test (tech@test.local)', texto)
        self.assertIn('https://wa.me/525512345678', texto)
        self.assertIn('NO RESPONDA', texto)

    def test_plano_sin_serie_usa_guion(self):
        """Sin Service Tag el plano usa el guion."""
        contexto = _contexto()
        contexto['detalle'].numero_serie = ''
        texto = construir_texto_plano_formato_venta_mostrador(contexto)
        self.assertIn('Service Tag: —', texto)

    def test_plano_sin_empleado_usa_responsable(self):
        """Sin técnico el plano no inventa WhatsApp."""
        texto = construir_texto_plano_formato_venta_mostrador(
            _contexto(
                email_empleado='',
                nombre_empleado='',
                whatsapp_empleado='',
            ),
        )
        self.assertIn('su responsable de seguimiento', texto)
        self.assertNotIn('Contacto:', texto)
        self.assertNotIn('wa.me/', texto)
