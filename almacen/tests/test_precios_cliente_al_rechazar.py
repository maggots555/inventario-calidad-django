"""
Tests: congelar precios al cliente también al rechazar.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Antes solo se guardaban precios al aprobar la primera línea.
Ahora la primera respuesta (aprobar o rechazar) llama a
persistir_precios_cliente() para análisis posteriores.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from almacen.models import LineaCotizacion, ProductoAlmacen, SolicitudCotizacion
from inventario.models import Empleado, Sucursal
from scorecard.models import ComponenteEquipo
from servicio_tecnico.models import Cotizacion, DetalleEquipo, OrdenServicio, PiezaCotizada


User = get_user_model()


class PreciosClienteAlRechazarTest(TestCase):
    """Objetivo: rechazo sin aprobación previa congela precios (con/sin orden)."""

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Precios Rechazo',
            codigo='TST-PRC',
            activa=True,
            ciudad='CDMX',
            direccion='Calle Precios 1',
            horario_atencion='Lun-Vie 9-18',
        )
        self.user = User.objects.create_user(
            username='front_precios_rech',
            password='testpass123',
            is_superuser=True,
        )
        self.empleado = Empleado.objects.create(
            user=self.user,
            nombre_completo='Front Precios',
            cargo='Recepción',
            area='FRONTDESK',
            email='front.precios@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )
        self.componente = ComponenteEquipo.objects.get_or_create(
            nombre='HDD',
            defaults={'activo': True, 'tipo_equipo': 'todos'},
        )[0]
        self.producto = ProductoAlmacen.objects.create(
            codigo_producto='SKU-HDD-PRC-01',
            nombre='DISCO HDD 1TB PRECIOS',
            tipo_producto='unico',
            costo_unitario=Decimal('100.00'),
            stock_actual=0,
        )

    def _crear_linea(self, solicitud: SolicitudCotizacion, *, costo: str = '100.00'):
        """Línea pendiente SIN precio cliente (simula cotización recién enviada)."""
        return LineaCotizacion.objects.create(
            solicitud=solicitud,
            producto=self.producto,
            descripcion_pieza='HDD 1TB',
            cantidad=1,
            costo_unitario=Decimal(costo),
            precio_unitario_cliente=None,
            subtotal_cliente_sin_iva=None,
            estado_cliente='pendiente',
        )

    def test_rechazo_sin_orden_congela_precios(self) -> None:
        """Sin orden: rechazo total persiste precios en cabecera y línea."""
        solicitud = SolicitudCotizacion.objects.create(
            orden_servicio=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
            creado_por=self.user,
            tipo_servicio_cliente='mostrador',
            nombre_cliente='Cliente Precios',
            email_cliente='cliente.prc@test.local',
            service_tag='SN-PRC-001',
        )
        linea = self._crear_linea(solicitud)
        ordenes_antes = OrdenServicio.objects.count()

        self.assertIsNone(solicitud.fecha_precios_cliente)
        self.assertIsNone(linea.precio_unitario_cliente)

        ok = linea.rechazar(motivo='costo alto')
        self.assertTrue(ok)

        solicitud.refresh_from_db()
        linea.refresh_from_db()

        self.assertEqual(solicitud.estado, 'totalmente_rechazada')
        self.assertIsNotNone(solicitud.fecha_precios_cliente)
        self.assertIsNotNone(linea.precio_unitario_cliente)
        self.assertGreater(linea.precio_unitario_cliente, 0)
        self.assertIsNotNone(solicitud.precio_total_sin_iva_cliente)
        self.assertGreater(solicitud.precio_total_sin_iva_cliente, 0)
        # EXPLICACIÓN: tipificar precios no debe crear orden ST
        self.assertEqual(OrdenServicio.objects.count(), ordenes_antes)

    def test_rechazo_con_orden_st_copia_precio_a_pieza(self) -> None:
        """Con orden ST: rechazo congela precio y lo refleja en PiezaCotizada."""
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='cotizacion',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='OOW-PRC-01',
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='Latitude',
            numero_serie='STPRC001',
            email_cliente='cliente.prc.st@test.local',
        )
        solicitud = SolicitudCotizacion.objects.create(
            orden_servicio=orden,
            estado='enviada_cliente',
            creado_por=self.user,
            tipo_servicio_cliente='estandar',
        )
        Cotizacion.objects.get(orden=orden)
        linea = self._crear_linea(solicitud)

        ok = linea.rechazar(motivo='no le conviene')
        self.assertTrue(ok)

        solicitud.refresh_from_db()
        linea.refresh_from_db()

        self.assertIsNotNone(solicitud.fecha_precios_cliente)
        self.assertIsNotNone(linea.precio_unitario_cliente)
        self.assertGreater(linea.precio_unitario_cliente, 0)

        pieza = PiezaCotizada.objects.filter(
            cotizacion__orden=orden,
        ).first()
        self.assertIsNotNone(pieza)
        assert pieza is not None
        self.assertIs(pieza.aceptada_por_cliente, False)
        self.assertIsNotNone(pieza.precio_unitario_cliente)
        self.assertEqual(pieza.precio_unitario_cliente, linea.precio_unitario_cliente)

    def test_idempotencia_tras_aprobacion_previa(self) -> None:
        """Si ya se congeló al aprobar, un rechazo posterior no recalcula."""
        solicitud = SolicitudCotizacion.objects.create(
            orden_servicio=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
            creado_por=self.user,
            tipo_servicio_cliente='mostrador',
            nombre_cliente='Cliente Mixto',
            email_cliente='mixto@test.local',
            service_tag='SN-PRC-MIX',
        )
        producto2 = ProductoAlmacen.objects.create(
            codigo_producto='SKU-RAM-PRC-02',
            nombre='RAM 8GB PRECIOS',
            tipo_producto='unico',
            costo_unitario=Decimal('50.00'),
            stock_actual=0,
        )
        linea_a = self._crear_linea(solicitud, costo='100.00')
        linea_b = LineaCotizacion.objects.create(
            solicitud=solicitud,
            producto=producto2,
            descripcion_pieza='RAM 8GB',
            cantidad=1,
            costo_unitario=Decimal('50.00'),
            precio_unitario_cliente=None,
            estado_cliente='pendiente',
        )

        self.assertTrue(linea_a.aprobar())
        solicitud.refresh_from_db()
        linea_a.refresh_from_db()
        linea_b.refresh_from_db()

        fecha_candado = solicitud.fecha_precios_cliente
        precio_a = linea_a.precio_unitario_cliente
        precio_b = linea_b.precio_unitario_cliente
        total = solicitud.precio_total_sin_iva_cliente

        self.assertIsNotNone(fecha_candado)
        self.assertIsNotNone(precio_a)
        self.assertIsNotNone(precio_b)

        # Rechazar la segunda línea: no debe mover el candado ni los precios
        self.assertTrue(linea_b.rechazar(motivo='solo esta no'))
        solicitud.refresh_from_db()
        linea_a.refresh_from_db()
        linea_b.refresh_from_db()

        self.assertEqual(solicitud.fecha_precios_cliente, fecha_candado)
        self.assertEqual(linea_a.precio_unitario_cliente, precio_a)
        self.assertEqual(linea_b.precio_unitario_cliente, precio_b)
        self.assertEqual(solicitud.precio_total_sin_iva_cliente, total)
        self.assertEqual(linea_b.estado_cliente, 'rechazada')
