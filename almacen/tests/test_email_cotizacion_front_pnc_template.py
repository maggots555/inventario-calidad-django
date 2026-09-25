"""
Tests del HTML del correo PNC a Front (partes no disponibles).

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo ni se toca la base de datos. Solo se rellena la
plantilla para comprobar que ya es un correo de tablas y que el aviso
PNC (con orden y sin orden) no se perdió.
"""

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


PLANTILLA = 'almacen/emails/cotizacion_front_pnc.html'
URL_DETALLE = 'https://mexico.sigmasystem.work/almacen/solicitudes-cotizacion/9/'


def _linea(
    numero: int,
    nombre: str,
    cantidad: int = 1,
    descripcion: str = '',
    notas: str = '',
    imagenes: list | None = None,
) -> dict:
    """
    Arma una línea falsa con los campos que la plantilla PNC lee.

    Args:
        numero: Número de línea.
        nombre: Nombre del componente no encontrado.
        cantidad: Piezas de esa línea.
        descripcion: Texto opcional de la pieza.
        notas: Nota opcional de la línea.
        imagenes: Lista de dicts con cid y descripcion, o None.

    Returns:
        dict: Item ``linea`` + ``imagenes``, igual que la tarea Celery.

    Efectos secundarios:
        Ninguno.
    """
    return {
        'linea': SimpleNamespace(
            numero_linea=numero,
            producto=SimpleNamespace(nombre=nombre),
            descripcion_pieza=descripcion,
            notas=notas,
            cantidad=cantidad,
        ),
        'imagenes': imagenes or [],
    }


def _solicitud(**overrides) -> SimpleNamespace:
    """
    Solicitud falsa con los campos que el HTML PNC consulta.

    Args:
        **overrides: Campos a cambiar (sin orden, cliente, etc.).

    Returns:
        SimpleNamespace: Solicitud lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    solicitud = SimpleNamespace(
        orden_servicio=SimpleNamespace(
            detalle_equipo=SimpleNamespace(numero_serie='SN-PNC-1'),
        ),
        service_tag='SN-SUELTO',
        numero_orden_cliente='FL-901',
        sin_orden_activa=False,
        nombre_cliente='Ana López',
        email_cliente='ana@ejemplo.com',
        telefono_cliente='5512345678',
    )
    for clave, valor in overrides.items():
        setattr(solicitud, clave, valor)
    return solicitud


def _contexto(**overrides) -> dict:
    """
    Contexto mínimo igual al de notificar_front_cotizacion_task (PNC).

    Args:
        **overrides: Claves a cambiar (equipo, nota, líneas, etc.).

    Returns:
        dict: Contexto para render_to_string.

    Efectos secundarios:
        Ninguno.
    """
    contexto = {
        'solicitud': _solicitud(),
        'lineas_con_imagenes': [
            _linea(
                1,
                'Tarjeta madre',
                cantidad=1,
                descripcion='Dell Latitude',
                notas='Sin stock',
                imagenes=[{'cid': 'linea1_img3', 'descripcion': 'Foto de la tarjeta'}],
            ),
        ],
        'info_equipo': {
            'tipo': 'Laptop',
            'marca': 'Dell',
            'modelo': 'Latitude',
            'service_tag': 'SN-PNC-1',
        },
        'mensaje_personalizado': '',
        'nombre_usuario': 'Luis Compras',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'fecha_envio_texto': '24/09/2026',
        'hora_envio_texto': '10:15',
        'url_detalle': URL_DETALLE,
        'whatsapp_empleado': '5215555555555',
    }
    for clave, valor in overrides.items():
        contexto[clave] = valor
    return contexto


class CotizacionFrontPncEmailTemplateTests(SimpleTestCase):
    """El HTML PNC debe ser correo de tablas y conservar el aviso a Front."""

    def test_con_orden_es_correo_de_tablas(self):
        """Con orden: alerta PNC, piezas sin precio, botón y pie interno."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('#c2410c', html)
        self.assertIn('PNC — Partes no disponibles', html)
        self.assertIn('S/T: SN-PNC-1', html)
        self.assertIn('Equipo de Recepción,', html)
        self.assertIn('Componentes no disponibles para cotización', html)
        self.assertIn('no están disponibles para cotizar', html)
        self.assertIn('«Notificar cliente: sin piezas (PNC)»', html)
        self.assertIn('no se encontraron', html)
        self.assertIn('Información del equipo', html)
        self.assertIn('FL-901', html)
        self.assertIn('Laptop Dell', html)
        self.assertIn('Tarjeta madre', html)
        self.assertIn('Dell Latitude', html)
        self.assertIn('Sin stock', html)
        self.assertIn('cid:linea1_img3', html)
        self.assertIn('width="96"', html)
        self.assertIn('No disponible', html)
        self.assertIn('Componente no encontrado', html)
        self.assertIn('Reparación a nivel componente', html)
        self.assertIn('Equipo reacondicionado', html)
        self.assertIn('Instrucciones para Recepción', html)
        self.assertIn('no hay disponibilidad', html)
        self.assertIn('Abrir solicitud en SIGMA', html)
        self.assertIn(URL_DETALLE, html)
        self.assertIn('notificar PNC', html)
        self.assertIn('Luis Compras', html)
        self.assertIn('NO RESPONDA', html)
        self.assertIn('área de Compras', html)
        self.assertIn('SIC México', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('instagram.com', html)
        self.assertNotIn('cid:icon_', html)
        self.assertNotIn('wa.me', html)
        self.assertNotIn('Costo Unit.', html)
        self.assertNotIn('5 días hábiles', html)
        self.assertNotIn('aún no tiene orden', html)

    def test_sin_orden_cambia_el_aviso_y_oculta_contacto(self):
        """Sin orden: otro párrafo de PNC, y no pinta email ni teléfono."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                solicitud=_solicitud(orden_servicio=None, sin_orden_activa=True),
                info_equipo=None,
                nombre_usuario='',
            ),
        )

        self.assertIn('aún no tiene orden de Servicio Técnico vinculada', html)
        self.assertIn('Datos del cliente', html)
        self.assertIn('Ana López', html)
        self.assertIn('SN-SUELTO', html)
        self.assertIn('Notificación PNC generada desde el Sistema de Almacén', html)
        self.assertNotIn('«Notificar cliente: sin piezas (PNC)»', html)
        self.assertNotIn('Información del equipo', html)
        self.assertNotIn('ana@ejemplo.com', html)
        self.assertNotIn('5512345678', html)
        self.assertNotIn('Email:', html)
        self.assertNotIn('Luis Compras', html)

    def test_nota_de_compras_se_muestra(self):
        """La nota libre conserva el título de Compras, no el de cotización."""
        html = render_to_string(
            PLANTILLA,
            _contexto(mensaje_personalizado='Importación inviable.'),
        )

        self.assertIn('Nota adicional de Compras', html)
        self.assertIn('Importación inviable.', html)

    def test_sin_nota_omite_el_bloque(self):
        """Sin mensaje no aparece la etiqueta de nota de Compras."""
        html = render_to_string(PLANTILLA, _contexto())
        self.assertNotIn('Nota adicional de Compras', html)

    def test_sin_equipo_ni_cliente_omite_paneles(self):
        """Si no hay equipo ni modo sin orden, no se pintan esos paneles."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                solicitud=_solicitud(sin_orden_activa=False, numero_orden_cliente=''),
                info_equipo=None,
            ),
        )

        self.assertNotIn('Información del equipo', html)
        self.assertNotIn('Datos del cliente', html)
        self.assertNotIn('Orden Cliente:', html)
        self.assertIn('«Notificar cliente: sin piezas (PNC)»', html)
        self.assertIn('Componente no encontrado', html)
