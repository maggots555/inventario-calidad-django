"""
Tests del HTML del correo interno de recotización a Compras.

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo. Solo se rellena la plantilla para comprobar que
ya es un aviso interno de tablas y que la ronda, las piezas y el
enlace no se pierden.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from almacen.utils.cotizacion_email_context import asunto_recotizacion_solicitada


PLANTILLA = 'almacen/emails/recotizacion_solicitada.html'
URL = 'https://mexico.sigmasystem.work/almacen/solicitudes-cotizacion/4/'


def _solicitud(**overrides) -> SimpleNamespace:
    """
    Solicitud falsa con los campos que el HTML lee.

    Args:
        **overrides: Campos a cambiar.

    Returns:
        SimpleNamespace: Solicitud lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    solicitud = SimpleNamespace(
        numero_solicitud='SOL-4',
        numero_orden_cliente='OOW-4',
        service_tag='SN-4',
        marca='Dell',
        modelo='Latitude',
    )
    for clave, valor in overrides.items():
        setattr(solicitud, clave, valor)
    return solicitud


def _contexto(**overrides) -> dict:
    """
    Contexto mínimo igual al de notificar_recotizacion_solicitada_task.

    Args:
        **overrides: Claves a cambiar (ronda, piezas, nota).

    Returns:
        dict: Contexto para render_to_string.

    Efectos secundarios:
        Ninguno.
    """
    contexto = {
        'solicitud': _solicitud(),
        'ronda_nueva': 2,
        'ronda_cerrada': 1,
        'ronda_anterior': SimpleNamespace(
            fecha_vencimiento=date(2026, 9, 20),
            observaciones='El cliente pidió esperar.',
        ),
        'lineas': [
            SimpleNamespace(
                numero_linea=1,
                descripcion_pieza='Pantalla 15',
                proveedor=SimpleNamespace(nombre='Refacciones Norte'),
                cantidad=1,
                costo_unitario=Decimal('800.00'),
            ),
        ],
        'solicitado_por': 'Marta Front',
        'fecha_envio_texto': '24/09/2026',
        'hora_envio_texto': '14:00',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'url_solicitud': URL,
        'nombre_cliente': 'Carlos Orden',
        'equipo': 'Laptop Dell Latitude',
    }
    contexto.update(overrides)
    return contexto


class RecotizacionSolicitadaEmailTemplateTests(SimpleTestCase):
    """El HTML de recotización debe ser correo interno y conservar la ronda."""

    def test_con_piezas_es_correo_interno(self):
        """Con piezas: ronda, costos, enlace y pie sin redes."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('Recotización solicitada', html)
        self.assertIn('Ronda 2', html)
        self.assertIn('Equipo de Compras,', html)
        self.assertIn('5 días hábiles', html)
        self.assertIn('<strong>OOW-4</strong> cumplió', html.replace('\n', ' '))
        self.assertIn('Borrador', html)
        self.assertIn('ronda', html)
        self.assertIn('SOL-4', html)
        self.assertIn('OOW-4', html)
        self.assertIn('SN-4', html)
        self.assertIn('Carlos Orden', html)
        self.assertIn('Laptop Dell Latitude', html)
        self.assertIn('venció el 20/09/2026', html)
        self.assertIn('Marta Front', html)
        self.assertIn('El cliente pidió esperar.', html)
        self.assertIn('Piezas por recotizar', html)
        self.assertIn('Pantalla 15', html)
        self.assertIn('Refacciones Norte', html)
        self.assertIn('Costo ronda 1', html)
        self.assertIn('$800.00', html)
        self.assertIn('Ir a la cotización', html)
        self.assertIn(URL, html)
        self.assertIn('NO RESPONDA', html)
        self.assertIn('contacte al área de Compras', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('instagram.com', html)
        self.assertNotIn('cid:icon_', html)

    def test_sin_piezas_ni_orden_muestra_sin_nombre(self):
        """Sin piezas no hay tabla. Sin cliente queda el texto Sin nombre."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                solicitud=_solicitud(numero_orden_cliente='', service_tag='', marca='', modelo=''),
                lineas=[],
                ronda_anterior=SimpleNamespace(fecha_vencimiento=None, observaciones=''),
                nombre_cliente='',
                equipo='',
            ),
        )

        self.assertIn('Sin nombre', html)
        self.assertIn('<strong>SOL-4</strong> cumplió', html.replace('\n', ' '))
        self.assertNotIn('Piezas por recotizar', html)
        self.assertNotIn('Orden cliente:', html)
        self.assertNotIn('Service Tag:', html)
        self.assertNotIn('Nota:', html)
        self.assertNotIn('venció el', html)
        self.assertIn('Ronda 1', html)


class AsuntoRecotizacionSolicitadaTests(SimpleTestCase):
    """El asunto pone la orden del cliente antes del folio interno."""

    def test_orden_cliente_va_primero(self):
        """Con OOW, el SOL queda entre paréntesis."""
        solicitud = SimpleNamespace(
            numero_solicitud='SOL-2026-0105',
            numero_orden_cliente='OOW-12092',
            service_tag='SN-1',
        )
        self.assertEqual(
            asunto_recotizacion_solicitada(solicitud),
            '🔄 Recotización solicitada — OOW-12092 (SOL-2026-0105)',
        )

    def test_sin_orden_deja_el_folio(self):
        """Sin orden ni Service Tag el asunto no repite el SOL."""
        solicitud = SimpleNamespace(
            numero_solicitud='SOL-2026-0105',
            numero_orden_cliente='',
            service_tag='',
        )
        self.assertEqual(
            asunto_recotizacion_solicitada(solicitud),
            '🔄 Recotización solicitada — SOL-2026-0105',
        )
