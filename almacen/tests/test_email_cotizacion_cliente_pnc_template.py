"""
Tests del HTML del correo PNC al cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo. Solo se rellena la plantilla para comprobar que
ya es un correo de tablas, que la carta de retiro solo sale con orden,
y que las redes del cliente se quedaron (sicgroup.mx, no sicfix).
"""

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


PLANTILLA = 'almacen/emails/cotizacion_cliente_pnc.html'


def _solicitud(**overrides) -> SimpleNamespace:
    """
    Solicitud falsa con los campos que el HTML del cliente lee.

    Args:
        **overrides: Campos a cambiar (orden, service tag, folio).

    Returns:
        SimpleNamespace: Solicitud lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    solicitud = SimpleNamespace(
        orden_servicio=None,
        service_tag='SN-CLI-1',
        numero_solicitud='SOL-77',
    )
    for clave, valor in overrides.items():
        setattr(solicitud, clave, valor)
    return solicitud


def _contexto(**overrides) -> dict:
    """
    Contexto mínimo igual al de notificar_cliente_pnc_task.

    Args:
        **overrides: Claves a cambiar (orden, nota, WhatsApp, etc.).

    Returns:
        dict: Contexto para render_to_string.

    Efectos secundarios:
        Ninguno.
    """
    contexto = {
        'solicitud': _solicitud(),
        'lineas_listado': [
            {
                'numero': 1,
                'producto': 'Tarjeta madre',
                'descripcion': 'Dell Latitude',
                'cantidad': 1,
            },
        ],
        'nombre_cliente': 'Ana López',
        'mensaje_personalizado': '',
        'tiene_orden_vinculada': False,
        'nombre_usuario': 'Luis Front',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'fecha_envio_texto': '24/09/2026',
        'hora_envio_texto': '10:15',
        'whatsapp_empleado': '5215555555555',
        'referencia_cliente': 'S/T: SN-CLI-1',
    }
    contexto.update(overrides)
    return contexto


class CotizacionClientePncEmailTemplateTests(SimpleTestCase):
    """El HTML al cliente debe ser correo de tablas y conservar el aviso."""

    def test_sin_orden_es_correo_de_cliente(self):
        """Sin orden: aviso y redes, sin la carta de retiro del equipo."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('Aviso sobre su solicitud', html)
        self.assertIn('S/T: SN-CLI-1', html)
        self.assertIn('Estimado/a Ana López,', html)
        self.assertIn('Componentes no disponibles para cotización', html)
        self.assertIn('no están disponibles para cotizar', html)
        self.assertIn('A continuación el listado de componentes revisados:', html)
        self.assertIn('Tarjeta madre', html)
        self.assertIn('Dell Latitude', html)
        self.assertIn('No disponible', html)
        self.assertIn('alternativas', html)
        self.assertIn('su solicitud', html)
        self.assertNotIn('SOL-77', html)
        self.assertIn('Luis Front', html)
        self.assertIn('NO RESPONDA', html)
        self.assertIn('responsable de seguimiento', html)
        self.assertIn('Visítanos y síguenos en nuestras redes sociales', html)
        self.assertIn('https://sicgroup.mx/', html)
        self.assertIn('Sitio Web', html)
        self.assertIn('cid:icon_instagram', html)
        self.assertIn('https://wa.me/5215555555555', html)
        self.assertIn('SIC México', html)
        self.assertNotIn('Me dirijo de SIC MÉXICO', html)
        self.assertNotIn('sicfix.mx', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)

    def test_con_orden_incluye_carta_de_retiro(self):
        """Con orden vinculada aparece la carta y el service tag del equipo."""
        solicitud = _solicitud(
            orden_servicio=SimpleNamespace(
                detalle_equipo=SimpleNamespace(numero_serie='SN-ORDEN-9'),
            ),
            service_tag='',
        )
        html = render_to_string(
            PLANTILLA,
            _contexto(
                solicitud=solicitud,
                tiene_orden_vinculada=True,
                referencia_cliente='OOW-100',
            ),
        )

        self.assertIn('S/T: SN-ORDEN-9', html)
        self.assertIn('OOW-100', html)
        self.assertNotIn('SOL-77', html)
        self.assertIn('Me dirijo de SIC MÉXICO', html)
        self.assertIn('retirar su equipo', html)
        self.assertIn('éste mismo medio', html)
        self.assertNotIn('S/T: SN-CLI-1', html)

    def test_sin_serie_muestra_folio_de_solicitud(self):
        """Sin orden ni service tag, el subtítulo es el folio de la solicitud."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                solicitud=_solicitud(service_tag=''),
                referencia_cliente='SOL-77',
            ),
        )
        self.assertIn('SOL-77', html)
        self.assertNotIn('S/T:', html)

    def test_nota_y_sin_whatsapp(self):
        """La nota se muestra; sin número no se pinta el enlace de WhatsApp."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                mensaje_personalizado='Le avisamos en cuanto haya novedad.',
                whatsapp_empleado='',
                nombre_usuario='',
            ),
        )

        self.assertIn('Nota adicional:', html)
        self.assertIn('Le avisamos en cuanto haya novedad.', html)
        self.assertIn('Mensaje enviado desde el Sistema de Almacén', html)
        self.assertNotIn('wa.me', html)
        self.assertNotIn('Luis Front', html)

    def test_sin_nota_omite_el_bloque(self):
        """Sin mensaje no aparece la etiqueta de nota adicional."""
        html = render_to_string(PLANTILLA, _contexto())
        self.assertNotIn('Nota adicional:', html)
