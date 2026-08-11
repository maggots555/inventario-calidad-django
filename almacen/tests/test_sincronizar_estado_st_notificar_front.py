"""
Tests: sync de estado ST al «Notificar a Front» según plantilla.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El modal Notificar a Front tiene dos plantillas:
- cotizacion_lista → ST a cotizacion_recibida_proveedor
- partes_no_disponibles → solo correo a Front; NO cambia ST
  (el PNC en ST lo pone «Notificar cliente: sin piezas»)

También se puede recuperar desde PNC con la plantilla de cotización lista.
La vista HTTP pasa tipo_plantilla al util y a la tarea Celery (mockeada).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from almacen.tests.helpers_integracion_cotizacion import (
    BaseIntegracionCotizacionMixin,
    request_post,
)
from almacen.utils.sincronizar_estado_st import (
    ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR,
    ESTADO_ST_ESPERANDO_CLIENTE,
    ESTADO_ST_PNC,
    TIPO_PLANTILLA_COTIZACION_LISTA,
    TIPO_PLANTILLA_PARTES_NO_DISPONIBLES,
    sincronizar_estado_st_al_enviar_cotizacion_cliente,
    sincronizar_estado_st_al_notificar_front,
)
from almacen.views import notificar_front


class SincronizarEstadoStAlNotificarFrontUtilTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Regla unitaria del util según tipo_plantilla.

    Objetivo de negocio:
        Cotización lista avanza ST; plantilla PNC a Front no toca ST.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='SYNC-FRONT')

    def test_plantilla_lista_pasa_a_recibida_proveedor(self) -> None:
        """
        Caso feliz: plantilla cotización lista → cotizacion_recibida_proveedor.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-SYNC-FRONT-01',
            estado='cotizacion_enviada_proveedor',
        )
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='borrador',
        )

        cambiado = sincronizar_estado_st_al_notificar_front(
            solicitud,
            usuario=self.user,
            tipo_plantilla=TIPO_PLANTILLA_COTIZACION_LISTA,
        )

        self.assertTrue(cambiado)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR)

    def test_plantilla_pnc_no_cambia_st(self) -> None:
        """
        Plantilla partes_no_disponibles: solo correo; ST no cambia.

        EXPLICACIÓN: la fuente única de PNC en ST es el botón al cliente.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-SYNC-FRONT-02',
            estado='cotizacion_enviada_proveedor',
        )
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='borrador',
        )
        estado_antes = orden.estado

        cambiado = sincronizar_estado_st_al_notificar_front(
            solicitud,
            usuario=self.user,
            tipo_plantilla=TIPO_PLANTILLA_PARTES_NO_DISPONIBLES,
        )

        self.assertFalse(cambiado)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, estado_antes)
        self.assertNotEqual(orden.estado, ESTADO_ST_PNC)

    def test_sin_orden_no_cambia_nada(self) -> None:
        """Sin orden vinculada: el util retorna False (correo sí puede ir aparte)."""
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='borrador',
        )

        cambiado = sincronizar_estado_st_al_notificar_front(
            solicitud,
            usuario=self.user,
            tipo_plantilla=TIPO_PLANTILLA_PARTES_NO_DISPONIBLES,
        )
        self.assertFalse(cambiado)

    def test_desde_pnc_con_plantilla_lista_recupera_a_recibida(self) -> None:
        """
        Recuperación: orden en PNC + plantilla cotización lista → recibida.

        EXPLICACIÓN: si después del PNC sí encontraron partes, Front/Compras
        puede re-notificar con la plantilla normal y el ST avanza.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-SYNC-FRONT-03',
            estado=ESTADO_ST_PNC,
        )
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_front',
        )

        cambiado = sincronizar_estado_st_al_notificar_front(
            solicitud,
            usuario=self.user,
            tipo_plantilla=TIPO_PLANTILLA_COTIZACION_LISTA,
        )

        self.assertTrue(cambiado)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR)

    def test_borde_esperando_piezas_no_retrocede(self) -> None:
        """Orden ya avanzada → el util NO pisa el estado (ni a PNC ni a recibida)."""
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-SYNC-FRONT-04',
            estado='esperando_piezas',
        )
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_front',
        )

        cambiado = sincronizar_estado_st_al_notificar_front(
            solicitud,
            usuario=self.user,
            tipo_plantilla=TIPO_PLANTILLA_PARTES_NO_DISPONIBLES,
        )

        self.assertFalse(cambiado)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'esperando_piezas')

    def test_ya_en_destino_no_duplica(self) -> None:
        """Reenvío con la misma plantilla: ya está en destino → False."""
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-SYNC-FRONT-05',
            estado=ESTADO_ST_PNC,
        )
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_front',
        )

        cambiado = sincronizar_estado_st_al_notificar_front(
            solicitud,
            usuario=self.user,
            tipo_plantilla=TIPO_PLANTILLA_PARTES_NO_DISPONIBLES,
        )
        self.assertFalse(cambiado)

    def test_desde_pnc_enviar_cotizacion_cliente_pasa_a_esperar(self) -> None:
        """
        Tras PNC, enviar cotización alternativa (ej. REAC) → ST a cotizacion.

        EXPLICACIÓN: aunque no hubo piezas, Front ofrece alternativa y
        queda esperando si el cliente acepta o no.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-SYNC-FRONT-06',
            estado=ESTADO_ST_PNC,
        )
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_front',
        )

        cambiado = sincronizar_estado_st_al_enviar_cotizacion_cliente(
            solicitud,
            usuario=self.user,
        )

        self.assertTrue(cambiado)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, ESTADO_ST_ESPERANDO_CLIENTE)

        ultimo = (
            orden.historial.filter(
                tipo_evento='cambio_estado',
                estado_nuevo=ESTADO_ST_ESPERANDO_CLIENTE,
            )
            .order_by('-fecha_evento')
            .first()
        )
        self.assertIsNotNone(ultimo)
        self.assertIn(solicitud.numero_solicitud, ultimo.comentario or '')


class NotificarFrontVistaPlantillaTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Integración HTTP: POST notificar_front con tipo_plantilla + mock Celery.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='NF-VISTA')
        self.orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-NF-VISTA-01',
            estado='cotizacion_enviada_proveedor',
        )
        self.solicitud, _linea = self._crear_solicitud_con_linea(
            orden=self.orden,
            sin_orden_activa=False,
            estado='borrador',
        )

    @patch('almacen.tasks.notificar_front_cotizacion_task.delay')
    def test_notificar_pnc_no_cambia_st_y_pasa_tipo_plantilla(self, mock_delay) -> None:
        """
        POST con plantilla PNC: ST sin cambio; Celery recibe tipo_plantilla.
        """
        mock_delay.return_value = MagicMock(id='task-pnc-test')
        url = reverse('almacen:notificar_front', args=[self.solicitud.pk])
        data = {
            'tipo_plantilla': TIPO_PLANTILLA_PARTES_NO_DISPONIBLES,
            'copia_empleados': [self.empleado.email],
            'mensaje_personalizado': 'Sin stock en mercado',
        }
        request = request_post(self.factory, self.user, url, data)
        respuesta = notificar_front(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 200)
        payload = json.loads(respuesta.content)
        self.assertTrue(payload['success'])
        self.assertEqual(
            payload['data']['tipo_plantilla'],
            TIPO_PLANTILLA_PARTES_NO_DISPONIBLES,
        )
        self.assertIn('PNC', payload['message'])

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'cotizacion_enviada_proveedor')
        self.assertNotEqual(self.orden.estado, ESTADO_ST_PNC)

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'enviada_front')

        # Celery debe recibir tipo_plantilla=partes_no_disponibles
        self.assertTrue(mock_delay.called)
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs.get('tipo_plantilla'), TIPO_PLANTILLA_PARTES_NO_DISPONIBLES)

    @patch('almacen.tasks.notificar_front_cotizacion_task.delay')
    def test_notificar_lista_pasa_a_recibida_proveedor(self, mock_delay) -> None:
        """POST con plantilla cotización lista (default de negocio)."""
        mock_delay.return_value = MagicMock(id='task-lista-test')
        url = reverse('almacen:notificar_front', args=[self.solicitud.pk])
        data = {
            'tipo_plantilla': TIPO_PLANTILLA_COTIZACION_LISTA,
            'copia_empleados': [self.empleado.email],
        }
        request = request_post(self.factory, self.user, url, data)
        respuesta = notificar_front(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 200)
        payload = json.loads(respuesta.content)
        self.assertTrue(payload['success'])

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR)

        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs.get('tipo_plantilla'), TIPO_PLANTILLA_COTIZACION_LISTA)

    @patch('almacen.tasks.notificar_front_cotizacion_task.delay')
    def test_tipo_plantilla_invalido_rechaza(self, mock_delay) -> None:
        """Plantilla desconocida → 400 y no encola Celery."""
        url = reverse('almacen:notificar_front', args=[self.solicitud.pk])
        data = {
            'tipo_plantilla': 'plantilla_inventada',
            'copia_empleados': [self.empleado.email],
        }
        request = request_post(self.factory, self.user, url, data)
        respuesta = notificar_front(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 400)
        payload = json.loads(respuesta.content)
        self.assertFalse(payload['success'])
        mock_delay.assert_not_called()
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'cotizacion_enviada_proveedor')
