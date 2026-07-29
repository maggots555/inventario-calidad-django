"""
Tests del rechazo total SIN orden vinculada → motivo en cabecera Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando no hay orden ST (o es FL-), el rechazo total se tipifica en
SolicitudCotizacion (motivo_rechazo / detalle_rechazo), sin crear
OrdenServicio ni Cotizacion ST. También se oculta Crear/Vincular orden.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase
from django.urls import reverse

from almacen.models import (
    LineaCotizacion,
    LineaServicioAdicional,
    ProductoAlmacen,
    SolicitudCotizacion,
)
from almacen.utils.sincronizar_rechazo_cotizacion_st import (
    armar_detalle_rechazo_desde_items,
    mensaje_flash_tras_rechazo_total,
    solicitud_requiere_motivo_rechazo_almacen,
    solicitud_requiere_motivo_rechazo_st,
)
from almacen.views import registrar_motivo_rechazo_solicitud, rechazar_todas_lineas
from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import Cotizacion, OrdenServicio


User = get_user_model()


def _request_post(factory: RequestFactory, user, url: str, data: dict):
    """Arma un POST autenticado con sesión y messages."""
    request = factory.post(url, data)
    request.user = user
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    return request


class RechazoTotalSinOrdenAlmacenTest(TestCase):
    """Objetivo: tipificar rechazo en SolicitudCotizacion sin crear ST."""

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Rechazo Sin Orden',
            codigo='TST-RSO',
            activa=True,
            ciudad='CDMX',
            direccion='Calle Test 2',
            horario_atencion='Lun-Vie 9-18',
        )
        self.user = User.objects.create_user(
            username='front_rechazo_sin',
            password='testpass123',
            is_superuser=True,
        )
        self.empleado = Empleado.objects.create(
            user=self.user,
            nombre_completo='Front Sin Orden',
            cargo='Recepción',
            area='FRONTDESK',
            email='front.sin.orden@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )
        # EXPLICACIÓN: sin_orden_activa + sin orden_servicio = camino Almacén
        self.solicitud = SolicitudCotizacion.objects.create(
            orden_servicio=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
            creado_por=self.user,
            nombre_cliente='Cliente Sin Orden',
            email_cliente='cliente.sin@test.local',
            service_tag='SN-SIN-001',
        )
        self.producto = ProductoAlmacen.objects.create(
            codigo_producto='SKU-HDD-SIN-01',
            nombre='DISCO HDD 1TB TEST',
            tipo_producto='unico',
            costo_unitario=Decimal('50.00'),
            stock_actual=0,
        )
        self.linea = LineaCotizacion.objects.create(
            solicitud=self.solicitud,
            producto=self.producto,
            descripcion_pieza='HDD 1TB',
            cantidad=1,
            costo_unitario=Decimal('50.00'),
            precio_unitario_cliente=Decimal('120.00'),
            estado_cliente='pendiente',
        )
        self.url_rechazar_todas = reverse(
            'almacen:rechazar_todas_lineas',
            kwargs={'pk': self.solicitud.pk},
        )
        self.url_registrar = reverse(
            'almacen:registrar_motivo_rechazo_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )

    def test_rechazo_total_requiere_motivo_almacen_no_st(self) -> None:
        """Sin orden: pide tipificación Almacén; no pide ST; no puede vincular."""
        request = _request_post(
            self.factory,
            self.user,
            self.url_rechazar_todas,
            {'motivo': 'costo alto en pieza'},
        )
        respuesta = rechazar_todas_lineas(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'totalmente_rechazada')
        self.assertTrue(solicitud_requiere_motivo_rechazo_almacen(self.solicitud))
        self.assertFalse(solicitud_requiere_motivo_rechazo_st(self.solicitud))
        self.assertFalse(self.solicitud.puede_vincular_orden())
        self.assertIn(
            'Acciones',
            mensaje_flash_tras_rechazo_total(self.solicitud),
        )
        self.assertNotIn(
            'Servicio Técnico',
            mensaje_flash_tras_rechazo_total(self.solicitud),
        )

    def test_prefill_detalle_incluye_pieza_y_servicio(self) -> None:
        """armar_detalle concatena motivos de líneas y servicios rechazados."""
        self.linea.rechazar(motivo='costo alto')
        LineaServicioAdicional.objects.create(
            solicitud=self.solicitud,
            tipo_servicio='limpieza',
            costo=Decimal('350.00'),
            estado_cliente='rechazada',
            motivo_rechazo='no autorizado',
        )
        self.solicitud.refresh_from_db()

        detalle = armar_detalle_rechazo_desde_items(self.solicitud)
        self.assertIn('Pieza: HDD 1TB — costo alto', detalle)
        self.assertIn('Servicio:', detalle)
        self.assertIn('no autorizado', detalle)

    def test_registrar_motivo_guarda_cabecera_sin_crear_st(self) -> None:
        """POST registra en SolicitudCotizacion; no crea Cotizacion ni Orden."""
        self.linea.rechazar(motivo='texto libre línea')
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'totalmente_rechazada')

        ordenes_antes = OrdenServicio.objects.count()
        cotizaciones_antes = Cotizacion.objects.count()

        request = _request_post(
            self.factory,
            self.user,
            self.url_registrar,
            {
                'motivo_rechazo': 'costo_alto',
                'detalle_rechazo': 'Pieza: HDD 1TB — texto libre línea',
            },
        )
        respuesta = registrar_motivo_rechazo_solicitud(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.motivo_rechazo, 'costo_alto')
        self.assertEqual(
            self.solicitud.detalle_rechazo,
            'Pieza: HDD 1TB — texto libre línea',
        )
        self.assertFalse(solicitud_requiere_motivo_rechazo_almacen(self.solicitud))
        self.assertFalse(self.solicitud.puede_vincular_orden())

        # EXPLICACIÓN: no debe nacer orden ni cotización ST solo por tipificar
        self.assertEqual(OrdenServicio.objects.count(), ordenes_antes)
        self.assertEqual(Cotizacion.objects.count(), cotizaciones_antes)

    def test_registrar_sin_motivo_catalogo_no_guarda(self) -> None:
        """Sin clave válida del catálogo, no se escribe la cabecera."""
        self.linea.rechazar(motivo='x')
        self.solicitud.refresh_from_db()

        request = _request_post(
            self.factory,
            self.user,
            self.url_registrar,
            {'motivo_rechazo': '', 'detalle_rechazo': 'algo'},
        )
        registrar_motivo_rechazo_solicitud(request, self.solicitud.pk)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.motivo_rechazo, '')
        self.assertTrue(solicitud_requiere_motivo_rechazo_almacen(self.solicitud))

    def test_con_orden_st_flujo_almacen_no_aplica(self) -> None:
        """Con orden ST válida, el camino de cabecera Almacén no aplica."""
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='cotizacion',
            tecnico_asignado_actual=self.empleado,
        )
        self.solicitud.orden_servicio = orden
        self.solicitud.sin_orden_activa = False
        self.solicitud.estado = 'totalmente_rechazada'
        self.solicitud.save(
            update_fields=['orden_servicio', 'sin_orden_activa', 'estado'],
        )

        self.assertFalse(solicitud_requiere_motivo_rechazo_almacen(self.solicitud))
        self.assertTrue(solicitud_requiere_motivo_rechazo_st(self.solicitud))
        self.assertIn(
            'Servicio Técnico',
            mensaje_flash_tras_rechazo_total(self.solicitud),
        )

        # El endpoint Almacén debe rechazar si hay camino ST
        request = _request_post(
            self.factory,
            self.user,
            self.url_registrar,
            {'motivo_rechazo': 'costo_alto', 'detalle_rechazo': 'no debe guardar'},
        )
        registrar_motivo_rechazo_solicitud(request, self.solicitud.pk)
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.motivo_rechazo, '')
