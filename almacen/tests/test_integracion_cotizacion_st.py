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

Los fixtures compartidos viven en helpers_integracion_cotizacion.py
(también los usa test_e2e_flujo_dinero.py).

Celery / envío de correo se mockean (.delay) para no tocar IO real en CI.
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from almacen.models import CompraProducto
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
from servicio_tecnico.models import Cotizacion


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
