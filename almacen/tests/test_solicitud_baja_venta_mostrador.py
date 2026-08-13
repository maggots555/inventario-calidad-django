"""
Tests: SolicitudBaja (stock interno) → PiezaVentaMostrador, sin tocar cotización.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Este flujo es paralelo al de cotización. Al aprobar una baja vinculada a
OOW- o FL- debe aparecer una pieza en Venta Mostrador, pero:

- NO se crea LineaCotizacion / CompraProducto / PiezaCotizada / SeguimientoPieza.
- Si la orden ya tiene paquete plata/oro/premium, el precio de la pieza es $0
  (el SSD/kit ya se cobró en el paquete).
- Si hay servicio de limpieza y el producto es un kit de limpieza, también $0
  (el kit va de regalo en ese servicio).
- Si el kit se vende sin ese servicio, se usa el costo_unitario del almacén.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from almacen.models import (
    CompraProducto,
    LineaCotizacion,
    ProductoAlmacen,
    SolicitudBaja,
)
from almacen.tests.helpers_integracion_cotizacion import (
    BaseIntegracionCotizacionMixin,
    request_post,
)
from almacen.utils.sincronizar_solicitud_baja_vm import (
    registrar_pieza_vm_desde_solicitud_baja,
)
from almacen.views import procesar_solicitud
from scorecard.models import ComponenteEquipo
from servicio_tecnico.models import (
    HistorialOrden,
    PiezaCotizada,
    PiezaVentaMostrador,
    SeguimientoPieza,
    VentaMostrador,
)


class SolicitudBajaVentaMostradorTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Objetivo: stock interno llega a VM sin pisar el flujo de cotización.

    Efectos secundarios: crea órdenes, solicitudes de baja y (si aplica) VM.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='BAJA-VM')
        # El mixin deja stock en 0; aprobar descuenta, así que hace falta existencias.
        self.producto.stock_actual = 10
        self.producto.save(update_fields=['stock_actual'])

    def _crear_solicitud_baja(
        self,
        *,
        orden,
        tipo_solicitud: str = 'servicio_tecnico',
        cantidad: int = 1,
        producto=None,
    ) -> SolicitudBaja:
        """
        Crea una SolicitudBaja pendiente lista para aprobar.

        Args:
            orden: OrdenServicio vinculada, o None.
            tipo_solicitud: Choice de TIPO_SOLICITUD_ALMACEN_CHOICES.
            cantidad: Unidades a sacar del stock.
            producto: ProductoAlmacen; por defecto el RAM del mixin.

        Returns:
            SolicitudBaja en estado pendiente.
        """
        return SolicitudBaja.objects.create(
            tipo_solicitud=tipo_solicitud,
            producto=producto or self.producto,
            cantidad=cantidad,
            orden_servicio=orden,
            solicitante=self.empleado,
            observaciones='Solicitud de prueba stock interno',
        )

    def _crear_producto_kit_limpieza(self) -> ProductoAlmacen:
        """
        Producto de almacén reconocible como kit de limpieza (P0186).

        Returns:
            ProductoAlmacen con nombre KIT DE LIMPIEZA y costo propio.
        """
        ComponenteEquipo.objects.get_or_create(
            nombre='Kit de Limpieza',
            defaults={'activo': True, 'tipo_equipo': 'todos'},
        )
        return ProductoAlmacen.objects.create(
            codigo_producto='SKU-KIT-BAJA-VM',
            nombre='KIT DE LIMPIEZA',
            tipo_producto='resurtible',
            costo_unitario=Decimal('80.00'),
            stock_actual=10,
            proveedor_principal=self.proveedor,
        )

    def _crear_orden_fl(self, *, orden_cliente: str):
        """
        Orden FL (venta_mostrador) mínima para el tipo venta_mostrador.

        Args:
            orden_cliente: Folio FL visible (único por test).

        Returns:
            OrdenServicio con tipo_servicio='venta_mostrador'.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente=orden_cliente,
            estado='almacen',
        )
        orden.tipo_servicio = 'venta_mostrador'
        orden.save(update_fields=['tipo_servicio'])
        return orden

    def test_aprobar_oow_sin_paquete_crea_vm_con_costo(self) -> None:
        """
        OOW sin paquete: crea VM + pieza al costo del almacén, sin linea_cotizacion.
        """
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-BAJA-01')
        solicitud = self._crear_solicitud_baja(
            orden=orden,
            tipo_solicitud='servicio_tecnico',
        )
        solicitud.aprobar(self.empleado, 'ok')

        pieza = registrar_pieza_vm_desde_solicitud_baja(solicitud)

        self.assertIsNotNone(pieza)
        self.assertIsNone(pieza.linea_cotizacion_id)
        self.assertEqual(pieza.solicitud_baja_id, solicitud.pk)
        self.assertEqual(pieza.cantidad, 1)
        self.assertEqual(pieza.precio_unitario, Decimal('150.00'))
        self.assertEqual(pieza.venta_mostrador.orden_id, orden.pk)
        self.assertIn('Stock interno', pieza.notas)
        self.assertEqual(
            VentaMostrador.objects.filter(orden=orden).count(),
            1,
        )
        self.assertTrue(
            HistorialOrden.objects.filter(
                orden=orden,
                tipo_evento='pieza',
            ).exists()
        )

    def test_aprobar_fl_sin_paquete_crea_pieza_vm(self) -> None:
        """
        FL sin paquete también registra la pieza en Venta Mostrador.
        """
        orden = self._crear_orden_fl(orden_cliente='FL-BAJA-01')
        solicitud = self._crear_solicitud_baja(
            orden=orden,
            tipo_solicitud='venta_mostrador',
        )
        solicitud.aprobar(self.empleado, 'ok')

        pieza = registrar_pieza_vm_desde_solicitud_baja(solicitud)

        self.assertIsNotNone(pieza)
        self.assertEqual(pieza.venta_mostrador.orden_id, orden.pk)
        self.assertEqual(pieza.precio_unitario, Decimal('150.00'))
        self.assertIsNone(pieza.linea_cotizacion_id)

    def test_paquete_plata_existente_pieza_a_cero_sin_duplicar_vm(self) -> None:
        """
        Paquete plata ya cobrado: la pieza de stock interno va a $0 en esa misma VM.
        """
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-BAJA-PLATA')
        vm = VentaMostrador.objects.create(
            orden=orden,
            paquete='plata',
            costo_paquete=Decimal('2900.00'),
        )
        total_antes = vm.total_venta

        solicitud = self._crear_solicitud_baja(orden=orden)
        solicitud.aprobar(self.empleado, 'entrega ssd paquete')
        pieza = registrar_pieza_vm_desde_solicitud_baja(solicitud)

        self.assertIsNotNone(pieza)
        self.assertEqual(pieza.precio_unitario, Decimal('0.00'))
        self.assertEqual(pieza.subtotal, Decimal('0.00'))
        self.assertEqual(
            VentaMostrador.objects.filter(orden=orden).count(),
            1,
        )
        vm.refresh_from_db()
        self.assertEqual(vm.pk, pieza.venta_mostrador.pk)
        self.assertEqual(vm.total_venta, total_antes)

    def test_kit_con_servicio_limpieza_va_a_cero(self) -> None:
        """
        Limpieza y mantenimiento ya cobrada: el kit físico sale a $0 (va de regalo).
        """
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-BAJA-KIT-GRATIS')
        vm = VentaMostrador.objects.create(
            orden=orden,
            paquete='ninguno',
            incluye_limpieza=True,
            costo_limpieza=Decimal('1050.00'),
        )
        total_antes = vm.total_venta
        kit = self._crear_producto_kit_limpieza()

        solicitud = self._crear_solicitud_baja(orden=orden, producto=kit)
        solicitud.aprobar(self.empleado, 'kit incluido en limpieza')
        pieza = registrar_pieza_vm_desde_solicitud_baja(solicitud)

        self.assertIsNotNone(pieza)
        self.assertEqual(pieza.precio_unitario, Decimal('0.00'))
        self.assertEqual(pieza.subtotal, Decimal('0.00'))
        self.assertIn('limpieza y mantenimiento', pieza.notas.lower())
        vm.refresh_from_db()
        self.assertEqual(vm.total_venta, total_antes)

    def test_kit_sin_servicio_limpieza_usa_costo_stock(self) -> None:
        """Kit vendido suelto (sin limpieza) lleva el costo_unitario de almacén."""
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-BAJA-KIT-PAGO')
        kit = self._crear_producto_kit_limpieza()

        solicitud = self._crear_solicitud_baja(orden=orden, producto=kit)
        solicitud.aprobar(self.empleado, 'venta de kit')
        pieza = registrar_pieza_vm_desde_solicitud_baja(solicitud)

        self.assertIsNotNone(pieza)
        self.assertEqual(pieza.precio_unitario, Decimal('80.00'))

    def test_limpieza_no_regala_otras_piezas(self) -> None:
        """Una RAM pedida con servicio de limpieza SÍ cobra costo de stock."""
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-BAJA-LIM-RAM')
        VentaMostrador.objects.create(
            orden=orden,
            paquete='ninguno',
            incluye_limpieza=True,
            costo_limpieza=Decimal('1050.00'),
        )

        solicitud = self._crear_solicitud_baja(orden=orden)
        solicitud.aprobar(self.empleado, 'ram no es kit')
        pieza = registrar_pieza_vm_desde_solicitud_baja(solicitud)

        self.assertIsNotNone(pieza)
        self.assertEqual(pieza.precio_unitario, Decimal('150.00'))

    def test_consumo_interno_no_crea_pieza_vm(self) -> None:
        """Consumo interno no va a Venta Mostrador aunque se apruebe."""
        solicitud = self._crear_solicitud_baja(
            orden=None,
            tipo_solicitud='consumo_interno',
        )
        solicitud.aprobar(self.empleado, 'oficina')

        pieza = registrar_pieza_vm_desde_solicitud_baja(solicitud)

        self.assertIsNone(pieza)
        self.assertEqual(PiezaVentaMostrador.objects.count(), 0)
        self.assertEqual(VentaMostrador.objects.count(), 0)

    def test_rechazar_no_crea_pieza_vm(self) -> None:
        """Rechazo deja stock y no registra pieza (el util exige estado aprobada)."""
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-BAJA-RECH')
        solicitud = self._crear_solicitud_baja(orden=orden)
        solicitud.rechazar(self.empleado, 'sin existencias correctas')

        pieza = registrar_pieza_vm_desde_solicitud_baja(solicitud)

        self.assertIsNone(pieza)
        self.assertEqual(PiezaVentaMostrador.objects.count(), 0)

    def test_no_pisa_flujo_cotizacion(self) -> None:
        """
        Con cotización OOW ya sincronizada, la baja no crea línea/compra/seguimiento
        ni otra PiezaCotizada.
        """
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-BAJA-COT')
        _solicitud_cot, _linea = self._crear_solicitud_con_linea(orden=orden)

        piezas_cot_antes = PiezaCotizada.objects.filter(
            cotizacion__orden=orden,
        ).count()
        lineas_antes = LineaCotizacion.objects.count()
        compras_antes = CompraProducto.objects.count()
        seguimientos_antes = SeguimientoPieza.objects.count()

        solicitud = self._crear_solicitud_baja(orden=orden)
        solicitud.aprobar(self.empleado, 'stock interno')
        pieza = registrar_pieza_vm_desde_solicitud_baja(solicitud)

        self.assertIsNotNone(pieza)
        self.assertIsNone(pieza.linea_cotizacion_id)
        self.assertEqual(
            PiezaCotizada.objects.filter(cotizacion__orden=orden).count(),
            piezas_cot_antes,
        )
        self.assertEqual(LineaCotizacion.objects.count(), lineas_antes)
        self.assertEqual(CompraProducto.objects.count(), compras_antes)
        self.assertEqual(SeguimientoPieza.objects.count(), seguimientos_antes)

    def test_util_idempotente_no_duplica_pieza(self) -> None:
        """Segunda llamada al util reutiliza la misma PiezaVentaMostrador."""
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-BAJA-IDEM')
        solicitud = self._crear_solicitud_baja(orden=orden)
        solicitud.aprobar(self.empleado, 'ok')

        primera = registrar_pieza_vm_desde_solicitud_baja(solicitud)
        segunda = registrar_pieza_vm_desde_solicitud_baja(solicitud)

        self.assertEqual(primera.pk, segunda.pk)
        self.assertEqual(
            PiezaVentaMostrador.objects.filter(solicitud_baja=solicitud).count(),
            1,
        )

    def test_vista_aprobar_registra_pieza_vm(self) -> None:
        """
        El gancho HTTP de procesar_solicitud crea la pieza al aprobar.
        """
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-BAJA-HTTP')
        solicitud = self._crear_solicitud_baja(orden=orden)
        url = reverse('almacen:procesar_solicitud', kwargs={'pk': solicitud.pk})

        respuesta = procesar_solicitud(
            request_post(
                self.factory,
                self.user,
                url,
                {'accion': 'aprobar', 'observaciones': 'entregado'},
            ),
            solicitud.pk,
        )

        self.assertEqual(respuesta.status_code, 302)
        pieza = PiezaVentaMostrador.objects.get(solicitud_baja=solicitud)
        self.assertEqual(pieza.venta_mostrador.orden_id, orden.pk)
        self.assertIsNone(pieza.linea_cotizacion_id)
