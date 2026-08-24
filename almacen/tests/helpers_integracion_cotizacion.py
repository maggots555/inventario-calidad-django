"""
Helpers compartidos para tests de integración Almacén ↔ ST (cotización).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Varios archivos de test necesitan lo mismo: un POST con sesión/messages,
una sucursal + usuario, una orden y una solicitud con línea.

En lugar de copiar/pegar (y que un test quede desfasado del otro), vivimos
aquí las piezas reutilizables:

- request_post: arma el HttpRequest para RequestFactory.
- BaseIntegracionCotizacionMixin: crea sucursal, user, producto, orden, solicitud.

Los tests de «por tramos» (test_integracion_cotizacion_st) y los E2E del
dinero (test_e2e_flujo_dinero) importan desde este módulo.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from almacen.models import LineaCotizacion, ProductoAlmacen, Proveedor, SolicitudCotizacion
from inventario.models import Empleado, Sucursal
from scorecard.models import ComponenteEquipo
from servicio_tecnico.models import DetalleEquipo, OrdenServicio


User = get_user_model()


def request_post(factory: RequestFactory, user, url: str, data: dict | None = None):
    """
    Arma un POST autenticado con sesión y messages.

    Args:
        factory: RequestFactory de Django.
        user: Usuario autenticado (suele ser superuser en estos tests).
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


# Alias histórico: el archivo viejo usaba _request_post
_request_post = request_post


class BaseIntegracionCotizacionMixin:
    """
    Fixtures compartidas para los escenarios de integración cotización.

    Objetivo: no repetir la creación de sucursal/usuario/producto en cada clase.

    Efectos secundarios:
        Cada método _crear_* inserta filas reales en la BD de test.
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

        Args:
            orden_cliente: Folio visible del cliente (único por test).
            estado: Estado inicial de la orden (default cotizacion).

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

        EXPLICACIÓN: al guardar con orden_servicio, el modelo sincroniza
        Cotizacion + PiezaCotizada en Servicio Técnico (no hace falta POST crear).

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

    def _registrar_anticipo_50(self, orden):
        """
        Carga en la orden un abono igual al 50% del total a cobrar.

        EXPLICACIÓN: el candado de Generar Compras exige este anticipo.
        Usamos efectivo para no disparar avisos a Facturación en CI.

        Args:
            orden: OrdenServicio con cotización/VM ya sincronizadas.

        Returns:
            PagoOrden creado, o None si el total es $0 (nada que cobrar).
        """
        from servicio_tecnico.models import OrdenServicio
        from servicio_tecnico.services.pagos_orden import (
            calcular_resumen_cobro,
            registrar_pago,
        )

        # Recargamos la orden: el cobro usa piezas/VM que pudieron nacer al aceptar.
        orden = OrdenServicio.objects.get(pk=orden.pk)
        resumen = calcular_resumen_cobro(orden, codigo_pais='MX')
        # Total $0 (p. ej. FL sin piezas en cobro): el candado deja pasar.
        if resumen.anticipo_minimo <= 0:
            return None
        return registrar_pago(
            orden=orden,
            empleado=self.empleado,
            monto=resumen.anticipo_minimo,
            tipo='anticipo',
            metodo='efectivo',
            codigo_pais='MX',
        )


# Alias con guion bajo: compatibilidad con imports antiguos del mixin privado
_BaseIntegracionCotizacionMixin = BaseIntegracionCotizacionMixin
