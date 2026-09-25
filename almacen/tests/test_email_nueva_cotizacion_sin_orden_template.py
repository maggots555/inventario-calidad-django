"""
Tests del HTML del correo de cotización sin orden a Compras.

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo. Solo se rellena la plantilla para comprobar que
ya es un aviso interno de tablas y que el cliente, las piezas y el
botón no se pierden.
"""

from decimal import Decimal
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


PLANTILLA = 'almacen/emails/nueva_cotizacion_sin_orden.html'
URL = 'https://mexico.sigmasystem.work/almacen/solicitudes-cotizacion/6/'


def _solicitud(**overrides) -> SimpleNamespace:
    """
    Solicitud falsa con los campos que el HTML sin orden lee.

    Args:
        **overrides: Campos a cambiar.

    Returns:
        SimpleNamespace: Solicitud lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    solicitud = SimpleNamespace(
        numero_solicitud='SOL-6',
        nombre_cliente='Ana López',
        service_tag='SN-6',
        telefono_cliente='5512345678',
        email_cliente='ana@ejemplo.com',
        marca='dell',
        get_marca_display=lambda: 'Dell',
        modelo='Inspiron',
        observaciones='Urgente para el viernes.',
    )
    for clave, valor in overrides.items():
        setattr(solicitud, clave, valor)
    return solicitud


def _contexto(**overrides) -> dict:
    """
    Contexto mínimo igual al de notificar_compras_nueva_cotizacion_task.

    Args:
        **overrides: Claves a cambiar (líneas, usuario).

    Returns:
        dict: Contexto para render_to_string.

    Efectos secundarios:
        Ninguno.
    """
    contexto = {
        'solicitud': _solicitud(),
        'lineas': [
            SimpleNamespace(
                numero_linea=1,
                producto=SimpleNamespace(nombre='Pantalla 15'),
                descripcion_pieza='Panel original',
                notas='Con bisel',
                proveedor=None,
                cantidad=2,
                costo_unitario=Decimal('0'),
                subtotal=Decimal('0'),
            ),
        ],
        'fecha_envio_texto': '24/09/2026',
        'hora_envio_texto': '15:00',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'nombre_usuario': 'Marta Recepción',
        'url_detalle': URL,
    }
    contexto.update(overrides)
    return contexto


class NuevaCotizacionSinOrdenEmailTemplateTests(SimpleTestCase):
    """El HTML sin orden debe ser correo interno y conservar el aviso."""

    def test_completo_es_correo_interno(self):
        """Con datos: cliente, pieza pendiente, instrucciones y pie sin redes."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('#c2410c', html)
        self.assertIn('Nueva cotización sin orden', html)
        self.assertIn('Requiere atención de Compras', html)
        self.assertIn('SOL-6', html)
        self.assertIn('Equipo de Compras,', html)
        self.assertIn('sin orden de servicio vinculada', html)
        self.assertIn('cuando este terminada', html)
        self.assertIn('Editar Unidad', html)
        self.assertIn('Ana López', html)
        self.assertIn('SN-6', html)
        self.assertIn('5512345678', html)
        self.assertIn('ana@ejemplo.com', html)
        self.assertIn('Dell', html)
        self.assertIn('Inspiron', html)
        self.assertIn('Pantalla 15', html)
        self.assertIn('Panel original', html)
        self.assertIn('Con bisel', html)
        self.assertIn('Por asignar', html)
        self.assertIn('Pendiente', html)
        self.assertIn('Urgente para el viernes.', html)
        self.assertIn('Instrucciones para Compras', html)
        self.assertIn('Ver detalle de la solicitud', html)
        self.assertIn(URL, html)
        self.assertIn('Marta Recepción', html)
        self.assertIn('NO RESPONDA', html)
        self.assertIn('área de Almacén', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('instagram.com', html)
        self.assertNotIn('cid:icon_', html)

    def test_minimo_omite_filas_vacias(self):
        """Sin tag, contacto ni observaciones no se pintan esas etiquetas."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                solicitud=_solicitud(
                    nombre_cliente='',
                    service_tag='',
                    telefono_cliente='',
                    email_cliente='',
                    marca='',
                    modelo='',
                    observaciones='',
                ),
                lineas=[
                    SimpleNamespace(
                        numero_linea=2,
                        producto=SimpleNamespace(nombre='Teclado'),
                        descripcion_pieza='',
                        notas='',
                        proveedor=SimpleNamespace(nombre='Refacciones Norte'),
                        cantidad=1,
                        costo_unitario=Decimal('120.50'),
                        subtotal=Decimal('120.50'),
                    ),
                ],
                nombre_usuario='',
            ),
        )

        self.assertIn('color:#0f172a;">-</td>', html)
        self.assertNotIn('Service Tag:', html)
        self.assertNotIn('Teléfono:', html)
        self.assertNotIn('Email:', html)
        self.assertNotIn('Marca:', html)
        self.assertNotIn('Observaciones', html)
        self.assertNotIn('Por asignar', html)
        self.assertNotIn('Pendiente', html)
        self.assertIn('Refacciones Norte', html)
        self.assertIn('$120.50', html)
        self.assertIn('Solicitud creada desde el Sistema de Almacén', html)
        self.assertNotIn('Marta Recepción', html)
