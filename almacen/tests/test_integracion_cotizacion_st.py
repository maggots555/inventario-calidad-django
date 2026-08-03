"""
Tests de integración Almacén ↔ ST (flujo cotización completo).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Estos tests NO son humo de modularización: crean datos reales en BD y
llaman las vistas HTTP (RequestFactory) para recorrer el flujo de negocio:

1) Con orden: aprobar línea → generar compras → CompraProducto + sync.
2) Sin orden: generar compras debe bloquearse.
3) Sin orden: vincular orden → entonces sí se pueden generar compras.
4) Rechazo total: rechazar todas + motivo catálogo → Cotizacion ST coherente.

Celery / envío de correo se mockean (.delay) para no tocar IO real en CI.
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase
from django.urls import reverse

from almacen.models import (
    CompraProducto,
    LineaCotizacion,
    ProductoAlmacen,
    Proveedor,
    SolicitudCotizacion,
)
from almacen.utils.sincronizar_rechazo_cotizacion_st import (
    solicitud_requiere_motivo_rechazo_st,
)
from almacen.views import (
    generar_compras_solicitud,
    rechazar_todas_lineas,
    registrar_motivo_rechazo_st,
    vincular_orden_solicitud,
)
from inventario.models import Empleado, Sucursal
from scorecard.models import ComponenteEquipo
from servicio_tecnico.models import Cotizacion, DetalleEquipo, OrdenServicio


User = get_user_model()


def _request_post(factory: RequestFactory, user, url: str, data: dict | None = None):
    """
    Arma un POST autenticado con sesión y messages.

    Args:
        factory: RequestFactory de Django.
        user: Usuario autenticado (superuser en estos tests).
        url: Ruta absoluta o relativa del POST.
        data: Dict de campos del formulario (opcional).

    Returns:
        HttpRequest listo para pasar a la vista.
    """
    request = factory.post(url, data or {})
    request.user = user
    # Session + messages: las vistas usan messages.* y redirect
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    return request


class _BaseIntegracionCotizacionMixin:
    """
    Fixtures compartidas para los escenarios de integración.

    Objetivo: no repetir la creación de sucursal/usuario/producto en cada clase.
    """

    databases = {'default', 'mexico'}

    def _crear_contexto_base(self, *, sufijo: str):
        """
        Crea sucursal, usuario superuser, empleado, proveedor y producto.

        Args:
            sufijo: Texto único para códigos (evita choques unique entre tests).

        Efectos secundarios:
            Inserta filas en Sucursal, User, Empleado, Proveedor, ProductoAlmacen.
        """
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre=f'Sucursal Integración {sufijo}',
            codigo=f'TST-INT-{sufijo}'[:20],
            activa=True,
            ciudad='CDMX',
            direccion='Calle Integración 1',
            horario_atencion='Lun-Vie 9-18',
        )
        self.user = User.objects.create_user(
            username=f'user_int_{sufijo}',
            password='testpass123',
            is_superuser=True,
        )
        self.empleado = Empleado.objects.create(
            user=self.user,
            nombre_completo=f'Integración {sufijo}',
            cargo='Front Desk',
            area='FRONTDESK',
            email=f'int.{sufijo}@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )
        self.proveedor = Proveedor.objects.create(
            nombre=f'Proveedor Integración {sufijo}',
            activo=True,
        )
        # ComponenteEquipo "RAM" ayuda al resolver_componente al sincronizar PiezaCotizada
        self.componente = ComponenteEquipo.objects.get_or_create(
            nombre='RAM',
            defaults={'activo': True, 'tipo_equipo': 'todos'},
        )[0]
        self.producto = ProductoAlmacen.objects.create(
            codigo_producto=f'SKU-INT-{sufijo}',
            nombre=f'MEMORIA RAM DDR4 16GB INT {sufijo}',
            tipo_producto='unico',
            costo_unitario=Decimal('150.00'),
            stock_actual=0,
            proveedor_principal=self.proveedor,
        )

    def _crear_orden_con_detalle(self, *, orden_cliente: str, estado: str = 'cotizacion'):
        """
        Crea OrdenServicio + DetalleEquipo mínimos.

        Returns:
            OrdenServicio creada (con detalle_equipo).
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado=estado,
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente=orden_cliente,
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='Latitude',
            numero_serie=f'SN-{orden_cliente}',
            email_cliente='cliente.integracion@test.local',
            nombre_cliente='Cliente Integración',
        )
        return orden

    def _crear_solicitud_con_linea(
        self,
        *,
        orden=None,
        sin_orden_activa: bool = False,
        estado: str = 'enviada_cliente',
        estado_linea: str = 'pendiente',
    ):
        """
        Crea SolicitudCotizacion + LineaCotizacion vinculadas al producto/proveedor.

        Args:
            orden: OrdenServicio o None (modo sin orden).
            sin_orden_activa: Flag de cotización previa al ingreso.
            estado: Estado inicial de la solicitud.
            estado_linea: Estado inicial de la línea.

        Returns:
            tuple: (solicitud, linea)
        """
        solicitud = SolicitudCotizacion.objects.create(
            orden_servicio=orden,
            sin_orden_activa=sin_orden_activa,
            estado=estado,
            creado_por=self.user,
            service_tag='SN-SIN-ORDEN' if sin_orden_activa else '',
        )
        linea = LineaCotizacion.objects.create(
            solicitud=solicitud,
            producto=self.producto,
            proveedor=self.proveedor,
            descripcion_pieza=self.producto.nombre,
            cantidad=1,
            costo_unitario=Decimal('150.00'),
            precio_unitario_cliente=Decimal('300.00'),
            estado_cliente=estado_linea,
        )
        return solicitud, linea


class IntegracionCotizacionConOrdenTest(_BaseIntegracionCotizacionMixin, TestCase):
    """
    Flujo feliz con orden vinculada desde el inicio + rechazo total sync ST.

    Objetivo de negocio:
        Verificar punta a punta que aprobar → generar compras crea CompraProducto,
        y que el rechazo total deja la Cotizacion ST con motivo de catálogo.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='CON')
        self.orden = self._crear_orden_con_detalle(orden_cliente='OOW-INT-CON-01')
        self.solicitud, self.linea = self._crear_solicitud_con_linea(
            orden=self.orden,
            sin_orden_activa=False,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        # Al crear con orden, el signal/save suele crear Cotizacion ST
        self.cotizacion = Cotizacion.objects.get(orden=self.orden)

    def test_aprobar_y_generar_compras_crea_compra_producto(self) -> None:
        """
        Caso feliz: línea aprobada + POST generar compras → CompraProducto.

        EXPLICACIÓN: simula que el cliente ya aceptó la pieza y Compras
        pulsa «Generar compras» en el detalle de la solicitud.
        """
        # Paso 1: el cliente aprueba la línea (lógica de modelo + sync PiezaCotizada)
        self.assertTrue(self.linea.aprobar())
        self.solicitud.refresh_from_db()
        self.linea.refresh_from_db()
        self.assertEqual(self.linea.estado_cliente, 'aprobada')
        self.assertIn(
            self.solicitud.estado,
            ('totalmente_aprobada', 'parcialmente_aprobada'),
        )
        self.assertTrue(self.solicitud.puede_generar_compras())

        # Paso 2: vista HTTP generar_compras_solicitud (POST)
        url = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request = _request_post(self.factory, self.user, url, {})
        respuesta = generar_compras_solicitud(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        # Paso 3: verificar efectos en BD (vínculo OneToOne linea.compra_generada)
        self.solicitud.refresh_from_db()
        self.linea.refresh_from_db()
        self.assertIsNotNone(self.linea.compra_generada_id)
        compra = CompraProducto.objects.get(pk=self.linea.compra_generada_id)

        self.assertEqual(self.linea.estado_cliente, 'compra_generada')
        self.assertEqual(self.solicitud.estado, 'completada')
        self.assertEqual(compra.producto_id, self.producto.pk)
        self.assertEqual(compra.orden_servicio_id, self.orden.pk)
        self.assertEqual(compra.estado, 'pendiente_llegada')
        self.assertEqual(CompraProducto.objects.count(), 1)

        # Sync ST: tras generar compras en reparación OOW → esperando_piezas
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'esperando_piezas')

    @patch('servicio_tecnico.tasks.enviar_feedback_rechazo_task.delay')
    def test_rechazo_total_y_motivo_sync_st(self, mock_delay) -> None:
        """
        Caso borde: rechazar todas + registrar motivo → Cotizacion ST coherente.

        EXPLICACIÓN: recorrido largo RequestFactory (dos vistas) sin enviar correo.
        """
        url_rechazar = reverse(
            'almacen:rechazar_todas_lineas',
            kwargs={'pk': self.solicitud.pk},
        )
        request_rechazar = _request_post(
            self.factory,
            self.user,
            url_rechazar,
            {'motivo': 'Cliente rechaza todas las piezas'},
        )
        resp1 = rechazar_todas_lineas(request_rechazar, self.solicitud.pk)
        self.assertEqual(resp1.status_code, 302)

        self.solicitud.refresh_from_db()
        self.linea.refresh_from_db()
        self.cotizacion.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'totalmente_rechazada')
        self.assertEqual(self.linea.estado_cliente, 'rechazada')
        self.assertTrue(solicitud_requiere_motivo_rechazo_st(self.solicitud))
        # Aún sin motivo de catálogo en cabecera ST
        self.assertEqual(self.cotizacion.motivo_rechazo, '')

        url_motivo = reverse(
            'almacen:registrar_motivo_rechazo_st',
            kwargs={'pk': self.solicitud.pk},
        )
        request_motivo = _request_post(
            self.factory,
            self.user,
            url_motivo,
            {
                'motivo_rechazo': 'costo_alto',
                'detalle_rechazo': (
                    '[RAZÓN PRINCIPAL]: Presupuesto excedido\n'
                    '[DETALLE]: Integración test'
                ),
            },
        )
        resp2 = registrar_motivo_rechazo_st(request_motivo, self.solicitud.pk)
        self.assertEqual(resp2.status_code, 302)

        self.cotizacion.refresh_from_db()
        self.assertIs(self.cotizacion.usuario_acepto, False)
        self.assertEqual(self.cotizacion.motivo_rechazo, 'costo_alto')
        self.assertFalse(solicitud_requiere_motivo_rechazo_st(self.solicitud))
        # Sin checkbox de feedback → no encola Celery
        mock_delay.assert_not_called()


class IntegracionCotizacionSinOrdenTest(_BaseIntegracionCotizacionMixin, TestCase):
    """
    Flujo sin orden activa: bloqueo de compras y desbloqueo al vincular.

    Objetivo de negocio:
        Evitar generar compras/piezas ST cuando aún no hay OrdenServicio;
        tras vincular, el flujo feliz debe funcionar.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='SIN')
        # Orden que se vinculará después (aún no ligada a la solicitud)
        self.orden = self._crear_orden_con_detalle(orden_cliente='OOW-INT-SIN-01')
        self.solicitud, self.linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )

    def test_generar_compras_sin_orden_bloquea(self) -> None:
        """
        Sin orden vinculada: POST generar compras no crea CompraProducto.

        Complementa el mock de test_generar_compras_sin_orden.py con camino HTTP.
        """
        # Aprobar línea dejando la solicitud lista para comprar… pero sin orden
        self.assertTrue(self.linea.aprobar())
        self.solicitud.refresh_from_db()
        self.assertTrue(self.solicitud.sin_orden_activa)
        self.assertIsNone(self.solicitud.orden_servicio_id)
        self.assertTrue(self.solicitud.compras_pendientes_sin_orden())
        self.assertFalse(self.solicitud.puede_generar_compras())

        url = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request = _request_post(self.factory, self.user, url, {})
        respuesta = generar_compras_solicitud(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self.linea.refresh_from_db()
        self.solicitud.refresh_from_db()
        # No se generó compra ni cambió a compra_generada/completada
        self.assertIsNone(self.linea.compra_generada_id)
        self.assertEqual(self.linea.estado_cliente, 'aprobada')
        self.assertNotEqual(self.solicitud.estado, 'completada')
        self.assertEqual(CompraProducto.objects.count(), 0)

    def test_vincular_orden_luego_generar_compras(self) -> None:
        """
        Vincular orden (POST orden_pk) desbloquea generar compras.

        EXPLICACIÓN: flujo típico «cotizamos antes de que entre el equipo».
        """
        self.assertTrue(self.linea.aprobar())
        self.solicitud.refresh_from_db()
        self.assertTrue(self.solicitud.puede_vincular_orden())

        # Paso 1: vincular la orden existente
        url_vincular = reverse(
            'almacen:vincular_orden_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request_vincular = _request_post(
            self.factory,
            self.user,
            url_vincular,
            {'orden_pk': str(self.orden.pk)},
        )
        resp_vincular = vincular_orden_solicitud(request_vincular, self.solicitud.pk)
        self.assertEqual(resp_vincular.status_code, 302)

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.orden_servicio_id, self.orden.pk)
        self.assertFalse(self.solicitud.sin_orden_activa)
        self.assertTrue(self.solicitud.puede_generar_compras())
        self.assertFalse(self.solicitud.compras_pendientes_sin_orden())

        # Paso 2: ahora sí generar compras
        url_compras = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request_compras = _request_post(self.factory, self.user, url_compras, {})
        resp_compras = generar_compras_solicitud(request_compras, self.solicitud.pk)
        self.assertEqual(resp_compras.status_code, 302)

        self.linea.refresh_from_db()
        self.solicitud.refresh_from_db()
        self.assertIsNotNone(self.linea.compra_generada_id)
        self.assertEqual(self.linea.estado_cliente, 'compra_generada')
        self.assertEqual(self.solicitud.estado, 'completada')

        compra = CompraProducto.objects.get(pk=self.linea.compra_generada_id)
        self.assertEqual(compra.orden_servicio_id, self.orden.pk)
        self.assertEqual(compra.producto_id, self.producto.pk)
