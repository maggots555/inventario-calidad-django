"""
Tests: folio de orden en el historial de movimientos es un enlace a ST.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando una SALIDA está ligada a una orden, el historial ya muestra el
folio (ej. FL-9326) como badge. Ahora ese badge debe abrir el detalle
de la orden, igual que en la lista de unidades.

Cubrimos dos pantallas:
- Historial del detalle de producto (la captura del usuario)
- Lista global `/almacen/movimientos/`
"""

from decimal import Decimal

from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase, override_settings
from django.urls import reverse

from django.utils import timezone

from almacen.models import CompraProducto, MovimientoAlmacen
from almacen.tests.helpers_integracion_cotizacion import BaseIntegracionCotizacionMixin
from almacen.views import detalle_producto, lista_movimientos


@override_settings(
    # En tests no hay collectstatic: ManifestStaticFilesStorage rompe {% static %}
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class MovimientosFolioEnlaceTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    El badge de orden en movimientos debe ser un enlace a la orden ST.

    Objetivo de negocio:
        Clic en FL-/OOW- del historial abre el servicio, sin buscar a mano.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='MOV-FOLIO')
        self.orden = self._crear_orden_con_detalle(orden_cliente='FL-MOV-01')
        # SALIDA vinculada: el save() ajusta stock; stock 0 → -1 es válido en test
        self.movimiento_con_orden = MovimientoAlmacen.objects.create(
            tipo='salida',
            producto=self.producto,
            cantidad=1,
            costo_unitario=Decimal('150.00'),
            empleado=self.empleado,
            orden_servicio=self.orden,
            observaciones='Salida de prueba con orden',
        )
        self.movimiento_sin_orden = MovimientoAlmacen.objects.create(
            tipo='entrada',
            producto=self.producto,
            cantidad=1,
            costo_unitario=Decimal('150.00'),
            empleado=self.empleado,
            observaciones='Entrada de stock sin orden',
        )
        self.url_orden = reverse(
            'servicio_tecnico:detalle_orden',
            args=[self.orden.pk],
        )

    def _request_get(self, path: str):
        """
        Arma un GET autenticado (sesión + messages) para llamar la vista.

        Args:
            path: Ruta absoluta (puede incluir query string).

        Returns:
            HttpRequest listo para la vista.
        """
        request = self.factory.get(path)
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_historial_producto_folio_es_enlace_a_la_orden(self) -> None:
        """
        Caso feliz: en el detalle del producto, FL-MOV-01 apunta a la orden.

        EXPLICACIÓN: simula abrir el producto y ver el historial de
        movimientos; el badge azul debe ser clicable.
        """
        url = reverse('almacen:detalle_producto', args=[self.producto.pk])
        respuesta = detalle_producto(self._request_get(url), self.producto.pk)
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('FL-MOV-01', html)
        self.assertIn(self.url_orden, html)

    def test_lista_movimientos_folio_es_enlace_a_la_orden(self) -> None:
        """Misma regla en la lista global de movimientos."""
        url = reverse('almacen:lista_movimientos')
        respuesta = lista_movimientos(self._request_get(url))
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('FL-MOV-01', html)
        self.assertIn(self.url_orden, html)

    def test_movimiento_sin_orden_no_inventa_enlace(self) -> None:
        """
        Borde: un movimiento sin orden no fabrica link a detalle_orden.

        EXPLICACIÓN: en la misma página hay un movimiento con orden
        (1 enlace) y otro sin ella. No debe aparecer un segundo link.
        """
        url = reverse('almacen:detalle_producto', args=[self.producto.pk])
        respuesta = detalle_producto(self._request_get(url), self.producto.pk)
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(html.count(self.url_orden), 1)


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class MovimientosCompraEnlaceTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    El badge Compra #N en movimientos debe abrir el detalle de esa compra.

    Objetivo de negocio:
        Clic en Compra #129 lleva a `/almacen/compras/129/`, sin buscar a mano.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='MOV-COMPRA')
        # Compra directa mínima: el save() calcula costo_total solo
        self.compra = CompraProducto.objects.create(
            tipo='compra',
            estado='recibida',
            producto=self.producto,
            proveedor=self.proveedor,
            cantidad=50,
            costo_unitario=Decimal('598.00'),
            fecha_pedido=timezone.now().date(),
            registrado_por=self.user,
        )
        self.movimiento_compra = MovimientoAlmacen.objects.create(
            tipo='entrada',
            producto=self.producto,
            cantidad=50,
            costo_unitario=Decimal('598.00'),
            empleado=self.empleado,
            compra=self.compra,
            observaciones=f'Recepción de compra #{self.compra.pk}.',
        )
        self.url_compra = reverse('almacen:detalle_compra', args=[self.compra.pk])

    def _request_get(self, path: str):
        """
        Arma un GET autenticado (sesión + messages) para llamar la vista.

        Args:
            path: Ruta absoluta.

        Returns:
            HttpRequest listo para la vista.
        """
        request = self.factory.get(path)
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_lista_movimientos_compra_es_enlace(self) -> None:
        """
        Caso feliz: en la lista de movimientos, Compra #N apunta al detalle.

        EXPLICACIÓN: es el badge verde de la captura (ENTRADA + Compra #129).
        """
        url = reverse('almacen:lista_movimientos')
        respuesta = lista_movimientos(self._request_get(url))
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(f'Compra #{self.compra.pk}', html)
        self.assertIn(self.url_compra, html)

    def test_historial_producto_compra_es_enlace(self) -> None:
        """Misma regla en el historial del detalle de producto."""
        url = reverse('almacen:detalle_producto', args=[self.producto.pk])
        respuesta = detalle_producto(self._request_get(url), self.producto.pk)
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(f'Compra #{self.compra.pk}', html)
        self.assertIn(self.url_compra, html)
