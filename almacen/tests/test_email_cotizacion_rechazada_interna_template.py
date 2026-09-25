"""
Tests del HTML del correo interno de cotización rechazada.

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo. Solo se rellena la plantilla para comprobar que
ya es un aviso interno de tablas y que el técnico, el motivo y los
botones no se pierden.
"""

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


PLANTILLA = 'almacen/emails/cotizacion_rechazada_interna.html'
URL_DETALLE = 'https://mexico.sigmasystem.work/almacen/solicitudes-cotizacion/8/'
URL_ORDEN = 'https://mexico.sigmasystem.work/servicio-tecnico/orden/8/'


def _orden(**overrides) -> SimpleNamespace:
    """
    Orden falsa con técnico y responsable.

    Args:
        **overrides: Campos a quitar o cambiar.

    Returns:
        SimpleNamespace: Orden lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    orden = SimpleNamespace(
        numero_orden_interno='INT-8',
        tecnico_asignado_actual=SimpleNamespace(nombre_completo='Luis Técnico'),
        responsable_seguimiento=SimpleNamespace(nombre_completo='Marta Seguimiento'),
    )
    for clave, valor in overrides.items():
        setattr(orden, clave, valor)
    return orden


def _solicitud(**overrides) -> SimpleNamespace:
    """
    Solicitud falsa con los campos que el HTML de rechazo lee.

    Args:
        **overrides: Campos a cambiar.

    Returns:
        SimpleNamespace: Solicitud lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    solicitud = SimpleNamespace(
        numero_solicitud='SOL-8',
        numero_orden_cliente='OOW-8',
        service_tag='SN-8',
    )
    for clave, valor in overrides.items():
        setattr(solicitud, clave, valor)
    return solicitud


def _contexto(**overrides) -> dict:
    """
    Contexto mínimo igual al de notificar_respuesta_cotizacion_rechazada_task.

    Args:
        **overrides: Claves a cambiar (orden, motivos, ítems).

    Returns:
        dict: Contexto para render_to_string.

    Efectos secundarios:
        Ninguno.
    """
    contexto = {
        'solicitud': _solicitud(),
        'orden': _orden(),
        'lineas_rechazadas': [
            SimpleNamespace(
                numero_linea=1,
                descripcion_pieza='Pantalla rota',
                producto=SimpleNamespace(nombre='Panel Dell'),
                motivo_rechazo='Precio alto',
            ),
        ],
        'servicios_rechazados': [
            SimpleNamespace(
                numero_linea=2,
                get_tipo_servicio_display=lambda: 'Limpieza',
                motivo_rechazo='',
            ),
        ],
        'motivo_catalogo': 'Cliente no autoriza',
        'detalle_items': 'Pieza 1: precio',
        'detalle_rechazo': 'No quiere reparar.',
        'fecha_envio_texto': '24/09/2026',
        'hora_envio_texto': '13:00',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'url_detalle': URL_DETALLE,
        'url_orden': URL_ORDEN,
        'nombre_cliente': 'Carlos Orden',
    }
    contexto.update(overrides)
    return contexto


class CotizacionRechazadaInternaEmailTemplateTests(SimpleTestCase):
    """El HTML de rechazo debe ser correo interno y conservar el aviso."""

    def test_con_orden_es_correo_interno(self):
        """Con orden: técnico, motivo, piezas y los dos botones, sin redes."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('#b91c1c', html)
        self.assertIn('Cotización rechazada', html)
        self.assertIn('No generar compras', html)
        self.assertIn('SOL-8', html)
        self.assertIn('Equipo,', html)
        self.assertIn('rechazó todas', html)
        self.assertIn('Luis Técnico', html)
        self.assertNotIn('técnico asignado,', html)
        self.assertIn('«Generar compras»', html)
        self.assertIn('Carlos Orden', html)
        self.assertIn('OOW-8', html)
        self.assertIn('SN-8', html)
        self.assertIn('INT-8', html)
        self.assertIn('Marta Seguimiento', html)
        self.assertIn('Cliente no autoriza', html)
        self.assertIn('Detalle de rechazo', html)
        self.assertIn('No quiere reparar.', html)
        self.assertNotIn('Motivos por ítem', html)
        self.assertIn('Pantalla rota', html)
        self.assertIn('Panel Dell', html)
        self.assertIn('Precio alto', html)
        self.assertIn('Limpieza', html)
        self.assertIn('Ver solicitud en Almacén', html)
        self.assertIn(URL_DETALLE, html)
        self.assertIn('Ver orden en ST', html)
        self.assertIn(URL_ORDEN, html)
        self.assertIn('NO RESPONDA', html)
        self.assertIn('área de Compras', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('instagram.com', html)
        self.assertNotIn('cid:icon_', html)

    def test_sin_orden_usa_texto_generico(self):
        """Sin orden: no hay botón de ST ni filas de técnico, y nombra al técnico genérico."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                orden=None,
                url_orden='',
                solicitud=_solicitud(numero_orden_cliente='', service_tag=''),
                motivo_catalogo='',
                detalle_rechazo='',
                detalle_items='Limpieza: no procede',
                lineas_rechazadas=[],
                servicios_rechazados=[
                    SimpleNamespace(
                        numero_linea=3,
                        get_tipo_servicio_display=lambda: 'Respaldo',
                        motivo_rechazo='',
                    ),
                ],
                nombre_cliente='',
            ),
        )

        self.assertIn('técnico asignado,', html)
        self.assertNotIn('Luis Técnico', html)
        self.assertNotIn('Orden ST:', html)
        self.assertNotIn('Ver orden en ST', html)
        self.assertNotIn(URL_ORDEN, html)
        self.assertIn('Motivos por ítem', html)
        self.assertIn('Limpieza: no procede', html)
        self.assertNotIn('Detalle de rechazo', html)
        self.assertNotIn('Pieza rechazada', html)
        self.assertIn('Respaldo', html)
        self.assertIn('color:#0f172a;">-</td>', html)
        self.assertNotIn('Orden cliente:', html)
        self.assertNotIn('Motivo catálogo:', html)
