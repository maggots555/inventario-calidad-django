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
5) Solo servicio (piezas rechazadas): al aceptar se crea VentaMostrador;
   la orden NO pasa a En reparación hasta el 50% + POST. Front NO puede
   generar compras de piezas.
6) Pieza + servicio: al aceptar ya está VentaMostrador (cobro 50% correcto)
   y CompraProducto sigue en 0 hasta «Generar Compras» (con el 50% cargado).

Los fixtures compartidos viven en helpers_integracion_cotizacion.py
(también los usa test_e2e_flujo_dinero.py).

Celery / envío de correo se mockean (.delay) para no tocar IO real en CI.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase, override_settings
from django.urls import reverse

from decimal import ROUND_HALF_UP, Decimal

from almacen.models import CompraProducto, LineaServicioAdicional, SolicitudCotizacion
from almacen.tests.helpers_integracion_cotizacion import (
    BaseIntegracionCotizacionMixin,
    request_post,
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
from servicio_tecnico.models import Cotizacion, OrdenServicio, VentaMostrador
from servicio_tecnico.services.pagos_orden import calcular_resumen_cobro

User = get_user_model()


class IntegracionCotizacionConOrdenTest(BaseIntegracionCotizacionMixin, TestCase):
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

        self._registrar_anticipo_50(self.orden)

        # Paso 2: vista HTTP generar_compras_solicitud (POST)
        url = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(self.factory, self.user, url, {})
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
        request_rechazar = request_post(
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
        request_motivo = request_post(
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


class IntegracionCotizacionSinOrdenTest(BaseIntegracionCotizacionMixin, TestCase):
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
        request = request_post(self.factory, self.user, url, {})
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
        request_vincular = request_post(
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

        self._registrar_anticipo_50(self.orden)

        # Paso 2: ahora sí generar compras
        url_compras = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request_compras = request_post(self.factory, self.user, url_compras, {})
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


def _usuario_front_sin_compras(*, username: str):
    """
    Usuario con permiso de editar solicitudes, sin permiso de crear compras.

    Simula al Recepcionista (Front): no puede pulsar «Generar Compras»
    de piezas (falta add_compraproducto).

    Args:
        username: Nombre único del user de prueba.

    Returns:
        User recargado (caché de permisos fresca).
    """
    user = User.objects.create_user(username=username, password='testpass123')
    content_type = ContentType.objects.get_for_model(SolicitudCotizacion)
    permiso = Permission.objects.get(
        content_type=content_type,
        codename='change_solicitudcotizacion',
    )
    user.user_permissions.add(permiso)
    return User.objects.get(pk=user.pk)


class IntegracionSoloServicioAceptadoTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Cliente rechaza todas las piezas y solo acepta un servicio adicional.

    Objetivo de negocio:
        Al cerrar la respuesta, el servicio ya debe estar en VentaMostrador
        para cobrar el 50%. La orden NO pasa a En reparación hasta ese
        anticipo (y el POST de confirmar). Sin CompraProducto.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='SRV')
        self.orden = self._crear_orden_con_detalle(orden_cliente='OOW-INT-SRV-01')
        self.solicitud, self.linea = self._crear_solicitud_con_linea(
            orden=self.orden,
            sin_orden_activa=False,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        # El servicio debe existir ANTES de responder las piezas: si no, al
        # rechazar la única línea la solicitud se cierra como totalmente_rechazada.
        self.servicio = LineaServicioAdicional.objects.create(
            solicitud=self.solicitud,
            tipo_servicio='limpieza',
            costo=Decimal('450.00'),
            estado_cliente='pendiente',
        )
        self.cotizacion = Cotizacion.objects.get(orden=self.orden)
        self.user_front = _usuario_front_sin_compras(username='front_int_srv')

    def _cerrar_solo_servicio(self) -> None:
        """Rechaza la pieza y aprueba la limpieza (cierra la solicitud)."""
        self.assertTrue(self.linea.rechazar(motivo='Cliente no autorizó la pieza'))
        self.assertTrue(self.servicio.aprobar())
        self.solicitud.refresh_from_db()
        self.orden.refresh_from_db()
        self.cotizacion.refresh_from_db()

    def test_rechazar_piezas_y_aceptar_servicio_deja_flags_correctos(self) -> None:
        """
        Tras responder: el servicio ya está en ST para cobrar, pero la
        solicitud sigue aprobada y la orden NO salta a En reparación.
        """
        from almacen.utils.anticipo_solicitud import puede_cerrar_solo_servicios

        self._cerrar_solo_servicio()

        self.assertEqual(self.solicitud.estado, 'parcialmente_aprobada')
        self.assertEqual(self.orden.estado, 'cliente_acepta_cotizacion')
        self.assertFalse(self.solicitud.puede_generar_compras())
        self.assertFalse(self.solicitud.puede_generar_venta_mostrador())
        self.assertTrue(puede_cerrar_solo_servicios(self.solicitud))
        # La cotización ST no debe verse como rechazada: aceptaron el servicio.
        self.assertIs(self.cotizacion.usuario_acepto, True)

        venta = VentaMostrador.objects.get(orden=self.orden)
        self.assertTrue(venta.incluye_limpieza)
        self.assertEqual(venta.costo_limpieza, Decimal('450.00'))
        self.assertEqual(CompraProducto.objects.count(), 0)

    def test_solo_servicio_con_anticipo_previo_cierra_al_aceptar(self) -> None:
        """
        Si Front ya había cargado el 50% antes de confirmar, al aceptar
        se copia VM y sí pasa a En reparación en ese momento.
        """
        from servicio_tecnico.services.pagos_orden import registrar_pago

        # El 50% del servicio ($450) son $225. Lo cargamos ANTES de confirmar.
        registrar_pago(
            orden=self.orden,
            empleado=self.empleado,
            monto=Decimal('225.00'),
            tipo='anticipo',
            metodo='efectivo',
            codigo_pais='MX',
        )
        self._cerrar_solo_servicio()

        self.assertEqual(self.solicitud.estado, 'completada')
        self.assertEqual(self.orden.estado, 'reparacion')
        self.assertEqual(VentaMostrador.objects.filter(orden=self.orden).count(), 1)
        self.assertEqual(CompraProducto.objects.count(), 0)

    def test_no_genera_servicio_si_aun_faltan_piezas_por_responder(self) -> None:
        """
        Borde: el cliente aceptó la limpieza pero la pieza sigue pendiente.

        EXPLICACIÓN: el botón no debe aparecer (ni el POST cerrar la solicitud)
        hasta que TODAS las líneas tengan respuesta. Si no, se completaría
        a medias y la orden saltaría a En reparación con piezas sin decidir.
        """
        self.assertTrue(self.servicio.aprobar())
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'enviada_cliente')
        self.assertFalse(self.solicitud.puede_generar_venta_mostrador())
        self.assertFalse(self.solicitud.puede_generar_compras())

        url = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(self.factory, self.user_front, url, {})
        respuesta = generar_compras_solicitud(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self.solicitud.refresh_from_db()
        self.orden.refresh_from_db()
        self.servicio.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'enviada_cliente')
        self.assertEqual(self.orden.estado, 'cotizacion')
        self.assertEqual(self.servicio.estado_cliente, 'aprobada')
        self.assertEqual(VentaMostrador.objects.filter(orden=self.orden).count(), 0)

    def test_post_sin_anticipo_no_pasa_a_reparacion(self) -> None:
        """
        Sin el 50%, el POST no completa ni pasa la orden a En reparación.
        """
        self._cerrar_solo_servicio()
        vm_id = VentaMostrador.objects.get(orden=self.orden).pk

        url = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(self.factory, self.user_front, url, {})
        respuesta = generar_compras_solicitud(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        textos = [str(m.message) for m in get_messages(request)]
        self.assertTrue(any('anticipo' in t.lower() for t in textos))

        self.solicitud.refresh_from_db()
        self.orden.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'parcialmente_aprobada')
        self.assertEqual(self.orden.estado, 'cliente_acepta_cotizacion')
        self.assertEqual(CompraProducto.objects.count(), 0)
        self.assertEqual(VentaMostrador.objects.get(orden=self.orden).pk, vm_id)

    def test_post_con_anticipo_50_pasa_a_reparacion(self) -> None:
        """
        Con el 50% cargado, el POST cierra a En reparación sin CompraProducto.
        """
        self._cerrar_solo_servicio()
        vm_id = VentaMostrador.objects.get(orden=self.orden).pk
        self._registrar_anticipo_50(self.orden)

        url = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(self.factory, self.user_front, url, {})
        respuesta = generar_compras_solicitud(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self.solicitud.refresh_from_db()
        self.orden.refresh_from_db()
        self.servicio.refresh_from_db()

        self.assertEqual(CompraProducto.objects.count(), 0)
        self.assertEqual(self.solicitud.estado, 'completada')
        self.assertEqual(self.orden.estado, 'reparacion')
        self.assertEqual(self.servicio.estado_cliente, 'compra_generada')
        self.assertEqual(VentaMostrador.objects.filter(orden=self.orden).count(), 1)
        venta = VentaMostrador.objects.get(orden=self.orden)
        self.assertEqual(venta.pk, vm_id)
        self.assertTrue(venta.incluye_limpieza)
        self.assertEqual(venta.costo_limpieza, Decimal('450.00'))

    def test_front_no_puede_generar_compras_de_piezas(self) -> None:
        """
        Si hay piezas aprobadas, Front se bloquea y no nace CompraProducto.
        """
        self.assertTrue(self.linea.aprobar())
        self.assertTrue(self.servicio.rechazar(motivo='No lo quiere'))
        self.solicitud.refresh_from_db()
        self.assertTrue(self.solicitud.puede_generar_compras())

        url = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(self.factory, self.user_front, url, {})
        respuesta = generar_compras_solicitud(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        textos = [str(m.message) for m in get_messages(request)]
        self.assertTrue(any('Solo Compras' in t for t in textos))
        self.assertEqual(CompraProducto.objects.count(), 0)
        self.linea.refresh_from_db()
        self.assertEqual(self.linea.estado_cliente, 'aprobada')
        self.assertIsNone(self.linea.compra_generada_id)


class IntegracionPiezaYServicioAceptadoTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Cliente acepta pieza Y servicio adicional.

    Objetivo de negocio:
        Al confirmar, Front debe ver el servicio en el cobro (50% correcto)
        sin que exista CompraProducto. Compras genera las compras después.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='MIX')
        self.orden = self._crear_orden_con_detalle(orden_cliente='OOW-INT-MIX-01')
        self.solicitud, self.linea = self._crear_solicitud_con_linea(
            orden=self.orden,
            sin_orden_activa=False,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        self.servicio = LineaServicioAdicional.objects.create(
            solicitud=self.solicitud,
            tipo_servicio='limpieza',
            costo=Decimal('450.00'),
            estado_cliente='pendiente',
        )
        self.cotizacion = Cotizacion.objects.get(orden=self.orden)

    def test_al_aceptar_pieza_y_servicio_vm_entra_al_cobro_sin_compra(self) -> None:
        """
        Feliz: aprobar pieza + limpieza → VentaMostrador y 50% con servicio;
        CompraProducto sigue en 0 y Compras aún puede generar compras.
        """
        self.assertTrue(self.linea.aprobar())
        self.assertTrue(self.servicio.aprobar())
        self.solicitud.refresh_from_db()
        self.orden.refresh_from_db()
        self.cotizacion.refresh_from_db()
        self.servicio.refresh_from_db()

        # Paso: solicitud cerrada, piezas listas para Compras, servicio ya en ST.
        self.assertEqual(self.solicitud.estado, 'totalmente_aprobada')
        self.assertEqual(self.orden.estado, 'cliente_acepta_cotizacion')
        self.assertTrue(self.solicitud.puede_generar_compras())
        self.assertFalse(self.solicitud.puede_generar_venta_mostrador())
        self.assertEqual(self.servicio.estado_cliente, 'compra_generada')
        self.assertEqual(CompraProducto.objects.count(), 0)

        venta = VentaMostrador.objects.get(orden=self.orden)
        self.assertTrue(venta.incluye_limpieza)
        self.assertEqual(venta.costo_limpieza, Decimal('450.00'))

        # Los precios al cliente se congelan al responder (no el 300 del fixture).
        # Lo que importa: el 50% incluye la limpieza, no solo las piezas.
        self.linea.refresh_from_db()
        precio_pieza = self.linea.precio_unitario_cliente
        iva = (precio_pieza * Decimal('0.16')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        total_esperado = precio_pieza + iva + Decimal('450.00')
        anticipo_esperado = (total_esperado * Decimal('0.50')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        anticipo_solo_piezas = ((precio_pieza + iva) * Decimal('0.50')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

        orden = OrdenServicio.objects.get(pk=self.orden.pk)
        resumen = calcular_resumen_cobro(orden, codigo_pais='MX')
        self.assertFalse(resumen.es_estimado)
        self.assertEqual(resumen.subtotal_cotizacion, precio_pieza)
        self.assertEqual(resumen.iva_cotizacion, iva)
        self.assertEqual(resumen.total_venta_mostrador, Decimal('450.00'))
        self.assertEqual(resumen.total_a_cobrar, total_esperado)
        self.assertEqual(resumen.anticipo_minimo, anticipo_esperado)
        self.assertGreater(resumen.anticipo_minimo, anticipo_solo_piezas)

    def test_generar_compras_sin_pago_no_crea_compra_producto(self) -> None:
        """
        Pieza + servicio aceptados, sin abono: el POST no crea CompraProducto.
        """
        self.assertTrue(self.linea.aprobar())
        self.assertTrue(self.servicio.aprobar())
        self.solicitud.refresh_from_db()
        self.assertTrue(self.solicitud.puede_generar_compras())

        url = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(self.factory, self.user, url, {})
        respuesta = generar_compras_solicitud(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        textos = [str(m.message) for m in get_messages(request)]
        self.assertTrue(any('anticipo' in t.lower() for t in textos))

        self.linea.refresh_from_db()
        self.solicitud.refresh_from_db()
        self.assertIsNone(self.linea.compra_generada_id)
        self.assertEqual(self.linea.estado_cliente, 'aprobada')
        self.assertEqual(self.solicitud.estado, 'totalmente_aprobada')
        self.assertEqual(CompraProducto.objects.count(), 0)

    def test_generar_compras_con_anticipo_50_crea_compra_producto(self) -> None:
        """
        Mismo caso, Front carga el 50%: sí se generan las compras.
        """
        self.assertTrue(self.linea.aprobar())
        self.assertTrue(self.servicio.aprobar())
        self.solicitud.refresh_from_db()
        self._registrar_anticipo_50(self.orden)

        url = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(self.factory, self.user, url, {})
        respuesta = generar_compras_solicitud(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self.linea.refresh_from_db()
        self.solicitud.refresh_from_db()
        self.assertIsNotNone(self.linea.compra_generada_id)
        self.assertEqual(self.linea.estado_cliente, 'compra_generada')
        self.assertEqual(self.solicitud.estado, 'completada')
        self.assertEqual(CompraProducto.objects.count(), 1)

    @override_settings(STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    })
    def test_detalle_boton_compras_apagado_sin_anticipo(self) -> None:
        """
        UI: el botón Generar Compras se ve, pero está deshabilitado
        hasta el 50%, con el texto de pagado vs mínimo.
        """
        from almacen.views import detalle_solicitud_cotizacion

        self.assertTrue(self.linea.aprobar())
        self.assertTrue(self.servicio.aprobar())
        self.solicitud.refresh_from_db()
        self.assertTrue(self.solicitud.puede_generar_compras())

        url = reverse(
            'almacen:detalle_solicitud_cotizacion',
            kwargs={'pk': self.solicitud.pk},
        )
        request = self.factory.get(url)
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        respuesta = detalle_solicitud_cotizacion(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 200)
        html = respuesta.content.decode('utf-8')
        self.assertIn('Generar Compras', html)
        self.assertIn('Falta anticipo', html)
        self.assertIn('disabled', html)
        # El formulario de POST no debe estar activo todavía.
        self.assertNotIn(
            '¿Generar compras para las líneas aprobadas?',
            html,
        )

    def test_vincular_orden_copia_servicio_ya_aceptado(self) -> None:
        """
        Sin orden: al aceptar no hay VM; al vincular sí se copia el servicio.
        """
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-INT-MIX-VIN')
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        servicio = LineaServicioAdicional.objects.create(
            solicitud=solicitud,
            tipo_servicio='limpieza',
            costo=Decimal('450.00'),
            estado_cliente='pendiente',
        )

        self.assertTrue(linea.aprobar())
        self.assertTrue(servicio.aprobar())
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'totalmente_aprobada')
        self.assertEqual(VentaMostrador.objects.filter(orden=orden).count(), 0)

        url_vincular = reverse(
            'almacen:vincular_orden_solicitud',
            kwargs={'pk': solicitud.pk},
        )
        resp = vincular_orden_solicitud(
            request_post(
                self.factory,
                self.user,
                url_vincular,
                {'orden_pk': str(orden.pk)},
            ),
            solicitud.pk,
        )
        self.assertEqual(resp.status_code, 302)

        solicitud.refresh_from_db()
        servicio.refresh_from_db()
        orden.refresh_from_db()
        self.assertEqual(solicitud.orden_servicio_id, orden.pk)
        self.assertTrue(solicitud.puede_generar_compras())
        self.assertEqual(servicio.estado_cliente, 'compra_generada')
        self.assertEqual(CompraProducto.objects.count(), 0)
        venta = VentaMostrador.objects.get(orden=orden)
        self.assertTrue(venta.incluye_limpieza)
        self.assertEqual(venta.costo_limpieza, Decimal('450.00'))
        self.assertEqual(orden.estado, 'cliente_acepta_cotizacion')
        cotizacion = Cotizacion.objects.get(orden=orden)
        self.assertIs(cotizacion.usuario_acepto, True)

