"""
Tests del HTML del correo de cotización aceptada a Compras.

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo. Solo se rellena la plantilla para comprobar que
ya es un aviso interno de tablas y que parcial y total no se mezclan.
"""

from decimal import Decimal
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from almacen.utils.cotizacion_email_context import (
    equipo_visible_solicitud,
    nombre_cliente_visible_solicitud,
)


PLANTILLA = 'almacen/emails/cotizacion_aceptada_compras.html'
URL_DETALLE = 'https://mexico.sigmasystem.work/almacen/solicitudes-cotizacion/12/'


def _solicitud(**overrides) -> SimpleNamespace:
    """
    Solicitud falsa con los campos que el HTML de Compras lee.

    Args:
        **overrides: Campos a cambiar (orden, service tag, estado).

    Returns:
        SimpleNamespace: Solicitud lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    solicitud = SimpleNamespace(
        numero_solicitud='SOL-12',
        nombre_cliente='Ana López',
        numero_orden_cliente='OOW-12',
        service_tag='SN-12',
        get_estado_display=lambda: 'Parcialmente aprobada',
    )
    for clave, valor in overrides.items():
        setattr(solicitud, clave, valor)
    return solicitud


def _contexto(**overrides) -> dict:
    """
    Contexto mínimo igual al de notificar_compras_cotizacion_aceptada_task.

    Args:
        **overrides: Claves a cambiar (parcial, líneas, servicios).

    Returns:
        dict: Contexto para render_to_string.

    Efectos secundarios:
        Ninguno.
    """
    contexto = {
        'solicitud': _solicitud(),
        'lineas_aprobadas': [
            SimpleNamespace(
                numero_linea=1,
                descripcion_pieza='Pantalla 15',
                producto=SimpleNamespace(nombre='Panel Dell'),
                proveedor=SimpleNamespace(nombre='Refacciones Norte'),
                cantidad=1,
                precio_unitario_cliente=Decimal('1500.50'),
            ),
        ],
        'servicios_aprobados': [
            SimpleNamespace(
                numero_linea=1,
                get_tipo_servicio_display=lambda: 'Limpieza',
                costo=Decimal('350.00'),
            ),
        ],
        'es_parcial': True,
        'fecha_envio_texto': '24/09/2026',
        'hora_envio_texto': '12:00',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'url_detalle': URL_DETALLE,
        'nombre_cliente': 'Ana López',
    }
    contexto.update(overrides)
    return contexto


class CotizacionAceptadaComprasEmailTemplateTests(SimpleTestCase):
    """El HTML a Compras debe ser correo interno y conservar las piezas."""

    def test_parcial_es_correo_interno(self):
        """Parcial: piezas, servicio, botón y pie sin redes."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('#166534', html)
        self.assertIn('Cotización aceptada', html)
        self.assertIn('Aceptación parcial', html)
        self.assertIn('SOL-12', html)
        self.assertIn('Equipo de Compras,', html)
        self.assertIn('aceptado parcialmente', html)
        self.assertIn('«Generar compras»', html)
        self.assertIn('Ana López', html)
        self.assertIn('OOW-12', html)
        self.assertIn('SN-12', html)
        self.assertIn('Parcialmente aprobada', html)
        self.assertIn('Pantalla 15', html)
        self.assertIn('Panel Dell', html)
        self.assertIn('Refacciones Norte', html)
        self.assertIn('$1500.50', html)
        self.assertIn('Limpieza', html)
        self.assertIn('$350.00', html)
        self.assertIn('Ver detalle de la solicitud', html)
        self.assertIn(URL_DETALLE, html)
        self.assertIn('NO RESPONDA', html)
        self.assertIn('área de Compras', html)
        self.assertIn('SIC México', html)
        self.assertNotIn('Aceptación total', html)
        self.assertNotIn('aceptado</strong>', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('instagram.com', html)
        self.assertNotIn('cid:icon_', html)

    def test_total_cambia_el_aviso(self):
        """Total: otro título y el verbo «aceptado», sin la palabra parcialmente."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                es_parcial=False,
                solicitud=_solicitud(
                    numero_orden_cliente='',
                    service_tag='',
                    get_estado_display=lambda: 'Aprobada',
                ),
                lineas_aprobadas=[
                    SimpleNamespace(
                        numero_linea=2,
                        descripcion_pieza='Teclado',
                        producto=None,
                        proveedor=None,
                        cantidad=1,
                        precio_unitario_cliente=None,
                    ),
                ],
                servicios_aprobados=[],
            ),
        )

        self.assertIn('Aceptación total', html)
        self.assertIn('<strong>aceptado</strong>', html)
        self.assertNotIn('aceptado parcialmente', html)
        self.assertNotIn('Aceptación parcial', html)
        self.assertNotIn('Orden cliente:', html)
        self.assertNotIn('Service Tag:', html)
        self.assertIn('—', html)
        self.assertNotIn('Servicio aceptado', html)
        self.assertNotIn('Limpieza', html)

    def test_sin_items_avisa(self):
        """Sin piezas ni servicios aparece el aviso, no tablas vacías."""
        html = render_to_string(
            PLANTILLA,
            _contexto(lineas_aprobadas=[], servicios_aprobados=[]),
        )

        self.assertIn('No se encontraron ítems aprobados en esta solicitud.', html)
        html_sin_nombre = render_to_string(PLANTILLA, _contexto(nombre_cliente=''))
        self.assertIn('color:#0f172a;">-</td>', html_sin_nombre)
        self.assertNotIn('Pieza aceptada', html)
        self.assertNotIn('Servicio aceptado', html)


class NombreClienteVisibleSolicitudTests(SimpleTestCase):
    """El nombre del correo sale de la orden si la solicitud no lo trae."""

    def test_usa_el_de_la_orden_si_la_solicitud_esta_vacia(self):
        """Cotización con orden: el cliente registrado está en el equipo."""
        solicitud = SimpleNamespace(
            nombre_cliente='',
            orden_servicio=SimpleNamespace(
                detalle_equipo=SimpleNamespace(nombre_cliente='  Carlos Orden  '),
            ),
        )
        self.assertEqual(nombre_cliente_visible_solicitud(solicitud), 'Carlos Orden')

    def test_prefiere_el_de_la_solicitud(self):
        """Si recepción tecleó un nombre, ese manda sobre el de la orden."""
        solicitud = SimpleNamespace(
            nombre_cliente='Ana Recepción',
            orden_servicio=SimpleNamespace(
                detalle_equipo=SimpleNamespace(nombre_cliente='Carlos Orden'),
            ),
        )
        self.assertEqual(
            nombre_cliente_visible_solicitud(solicitud),
            'Ana Recepción',
        )

    def test_sin_orden_ni_nombre_queda_vacio(self):
        """Sin ninguno de los dos, el correo muestra el guion, no truena."""
        solicitud = SimpleNamespace(nombre_cliente='  ', orden_servicio=None)
        self.assertEqual(nombre_cliente_visible_solicitud(solicitud), '')


class EquipoVisibleSolicitudTests(SimpleTestCase):
    """El equipo del correo sale de la orden si la solicitud no lo trae."""

    def test_usa_el_de_la_orden_si_la_solicitud_esta_vacia(self):
        """Cotización con orden: marca y modelo están en el equipo."""
        solicitud = SimpleNamespace(
            marca='',
            modelo='',
            tipo_equipo='',
            orden_servicio=SimpleNamespace(
                detalle_equipo=SimpleNamespace(
                    tipo_equipo='laptop',
                    get_tipo_equipo_display=lambda: 'Laptop',
                    marca='Dell',
                    modelo='Latitude',
                ),
            ),
        )
        self.assertEqual(
            equipo_visible_solicitud(solicitud),
            'Laptop Dell Latitude',
        )

    def test_sin_orden_usa_lo_capturado_en_la_solicitud(self):
        """Sin orden: tipo, marca visible y modelo de la propia solicitud."""
        solicitud = SimpleNamespace(
            marca='dell',
            get_marca_display=lambda: 'Dell',
            modelo='Inspiron',
            tipo_equipo='',
            orden_servicio=None,
        )
        self.assertEqual(equipo_visible_solicitud(solicitud), 'Dell Inspiron')
