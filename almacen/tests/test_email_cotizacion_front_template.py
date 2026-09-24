"""
Tests del HTML del correo de cotización a Front (Recepción).

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo ni se toca la base de datos. Solo se rellena la
plantilla para comprobar que ya es un correo de tablas (no una página
web) y que el texto de negocio sigue ahí.
"""

from decimal import Decimal
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


PLANTILLA = 'almacen/emails/cotizacion_front.html'
URL_DETALLE = 'https://mexico.sigmasystem.work/almacen/solicitudes-cotizacion/9/'


def _linea(
    numero: int,
    nombre: str,
    costo: Decimal,
    subtotal: Decimal,
    cantidad: int = 1,
    descripcion: str = '',
    notas: str = '',
    imagenes: list | None = None,
) -> dict:
    """
    Arma una línea falsa con los campos que la plantilla lee.

    Args:
        numero: Número de línea.
        nombre: Nombre del producto.
        costo: Costo unitario. 0 muestra "Pendiente".
        subtotal: Subtotal de la línea. 0 muestra un guion.
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
            costo_unitario=costo,
            subtotal=subtotal,
        ),
        'imagenes': imagenes or [],
    }


def _solicitud(**overrides) -> SimpleNamespace:
    """
    Solicitud falsa con los campos que el HTML consulta.

    Args:
        **overrides: Campos a cambiar (sin orden, cliente, etc.).

    Returns:
        SimpleNamespace: Solicitud lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    solicitud = SimpleNamespace(
        orden_servicio=SimpleNamespace(
            detalle_equipo=SimpleNamespace(numero_serie='SN-FRONT-1'),
        ),
        service_tag='SN-SUELTO',
        numero_orden_cliente='FL-900',
        sin_orden_activa=False,
        nombre_cliente='Ana López',
        email_cliente='ana@ejemplo.com',
        telefono_cliente='5512345678',
        costo_total=Decimal('301.00'),
    )
    for clave, valor in overrides.items():
        setattr(solicitud, clave, valor)
    return solicitud


def _contexto(**overrides) -> dict:
    """
    Contexto mínimo igual al de notificar_front_cotizacion_task.

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
                'Pantalla 15',
                Decimal('150.50'),
                Decimal('301.00'),
                cantidad=2,
                descripcion='Panel original',
                notas='Con bisel',
                imagenes=[{'cid': 'linea1_img9', 'descripcion': 'Foto del panel'}],
            ),
        ],
        'info_equipo': {
            'tipo': 'Laptop',
            'marca': 'Dell',
            'modelo': 'Latitude',
            'service_tag': 'SN-FRONT-1',
        },
        'mensaje_personalizado': '',
        'nombre_usuario': 'Luis Compras',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'fecha_envio_texto': '24/09/2026',
        'hora_envio_texto': '10:15',
        'url_detalle': URL_DETALLE,
    }
    contexto.update(overrides)
    return contexto


class CotizacionFrontEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas y conservar el texto de Front."""

    def test_con_orden_es_correo_de_tablas(self):
        """Con orden: barra, piezas, botón y pie interno, sin CSS de página."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('#1f6391', html)
        self.assertIn('Nueva cotización', html)
        self.assertIn('S/T: SN-FRONT-1', html)
        self.assertIn('Equipo de Recepción,', html)
        self.assertIn('Información del equipo', html)
        self.assertIn('Orden Cliente:', html)
        self.assertIn('FL-900', html)
        self.assertIn('Laptop Dell', html)
        self.assertIn('Latitude', html)
        self.assertIn('Pantalla 15', html)
        self.assertIn('Panel original', html)
        self.assertIn('Con bisel', html)
        self.assertIn('cid:linea1_img9', html)
        self.assertIn('width="96"', html)
        self.assertIn('$150.50', html)
        self.assertIn('$301.00', html)
        self.assertIn('Instrucciones para Recepción', html)
        self.assertIn('5 días hábiles', html)
        self.assertIn('Abrir solicitud en SIGMA', html)
        self.assertIn(URL_DETALLE, html)
        self.assertIn('Luis Compras', html)
        self.assertIn('NO RESPONDA', html)
        self.assertIn('Sistema de Almacén SIC', html)
        self.assertIn('SIC México', html)
        self.assertIn('24/09/2026', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('instagram.com', html)
        self.assertNotIn('cid:icon_', html)
        self.assertNotIn('Datos del cliente', html)

    def test_sin_orden_muestra_datos_del_cliente(self):
        """Sin orden activa: cliente, correo y teléfono; no el panel del equipo."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                solicitud=_solicitud(orden_servicio=None, sin_orden_activa=True),
                info_equipo=None,
                nombre_usuario='',
            ),
        )

        self.assertIn('Datos del cliente', html)
        self.assertIn('Ana López', html)
        self.assertIn('ana@ejemplo.com', html)
        self.assertIn('5512345678', html)
        self.assertIn('SN-SUELTO', html)
        self.assertIn('Cotización generada desde el Sistema de Almacén', html)
        self.assertNotIn('Información del equipo', html)
        self.assertNotIn('Luis Compras', html)

    def test_nota_y_costo_pendiente(self):
        """Nota libre se muestra; costo en cero dice Pendiente, no un precio."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                mensaje_personalizado='Avisar antes de las 3.',
                lineas_con_imagenes=[
                    _linea(2, 'Teclado', Decimal('0'), Decimal('0')),
                ],
            ),
        )

        self.assertIn('Nota adicional', html)
        self.assertIn('Avisar antes de las 3.', html)
        self.assertIn('Pendiente', html)
        self.assertIn('Teclado', html)
        self.assertNotIn('$0.00', html)

    def test_sin_nota_omite_el_bloque(self):
        """Sin mensaje no aparece la etiqueta de nota adicional."""
        html = render_to_string(PLANTILLA, _contexto())
        self.assertNotIn('Nota adicional', html)

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
        self.assertIn('Producto / Descripción', html)
