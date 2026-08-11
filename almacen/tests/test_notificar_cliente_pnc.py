"""
Tests: notificar al cliente PNC (partes no disponibles).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1) Util sync: con orden → ST a PNC; sin orden → no toca ST.
2) Util respuesta: rechazo total desde PNC → rechazada.
3) Vista HTTP: mock Celery, pasa a enviada_cliente, exige email.
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
    ESTADO_ST_PNC,
    sincronizar_estado_st_al_notificar_cliente_pnc,
    sincronizar_estado_st_por_respuesta_cliente,
)
from almacen.views import notificar_cliente_pnc


class SincronizarEstadoStNotificarClientePncUtilTest(
    BaseIntegracionCotizacionMixin,
    TestCase,
):
    """Reglas unitarias del util PNC al cliente + rechazo desde PNC."""

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='PNC-CLI')

    def test_con_orden_pasa_a_pnc(self) -> None:
        """Orden en cotización recibida → PNC al avisar al cliente."""
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-PNC-CLI-01',
            estado=ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR,
        )
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_front',
        )

        cambiado = sincronizar_estado_st_al_notificar_cliente_pnc(
            solicitud,
            usuario=self.user,
        )

        self.assertTrue(cambiado)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, ESTADO_ST_PNC)

        ultimo = (
            orden.historial.filter(
                tipo_evento='cambio_estado',
                estado_nuevo=ESTADO_ST_PNC,
            )
            .order_by('-fecha_evento')
            .first()
        )
        self.assertIsNotNone(ultimo)
        self.assertIn('Cliente notificado', ultimo.comentario or '')
        self.assertIn(linea.descripcion_pieza, ultimo.comentario or '')

    def test_sin_orden_no_cambia_st(self) -> None:
        """Sin orden vinculada: el util no hace nada."""
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_front',
        )
        cambiado = sincronizar_estado_st_al_notificar_cliente_pnc(
            solicitud,
            usuario=self.user,
        )
        self.assertFalse(cambiado)

    def test_ya_en_pnc_no_duplica(self) -> None:
        """Si ya está en PNC, no vuelve a cambiar ni duplicar historial."""
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-PNC-CLI-02',
            estado=ESTADO_ST_PNC,
        )
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_front',
        )
        cambiado = sincronizar_estado_st_al_notificar_cliente_pnc(
            solicitud,
            usuario=self.user,
        )
        self.assertFalse(cambiado)

    def test_rechazo_total_desde_pnc_pasa_a_rechazada(self) -> None:
        """
        Tras avisar PNC, si tipifican rechazo total → ST rechazada.

        EXPLICACIÓN: antes solo se permitía desde «cotizacion»; ahora también
        desde PNC cuando el destino es rechazo.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-PNC-CLI-03',
            estado=ESTADO_ST_PNC,
        )
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='totalmente_rechazada',
        )

        cambiado = sincronizar_estado_st_por_respuesta_cliente(
            solicitud,
            estado_solicitud='totalmente_rechazada',
        )

        self.assertTrue(cambiado)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'rechazada')


class NotificarClientePncVistaTest(BaseIntegracionCotizacionMixin, TestCase):
    """Integración HTTP del endpoint notificar_cliente_pnc."""

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='PNC-VISTA')
        self.orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-PNC-VISTA-01',
            estado='cotizacion_enviada_proveedor',
        )
        self.solicitud, _linea = self._crear_solicitud_con_linea(
            orden=self.orden,
            sin_orden_activa=False,
            estado='enviada_front',
        )

    @patch('almacen.tasks.notificar_cliente_pnc_task.delay')
    def test_feliz_pasa_a_enviada_cliente_y_pnc(self, mock_delay) -> None:
        """POST válido: enviada_cliente + ST PNC + Celery con email."""
        mock_delay.return_value = MagicMock(id='task-pnc-cli')
        url = reverse('almacen:notificar_cliente_pnc', args=[self.solicitud.pk])
        data = {
            'email_cliente': 'cliente.pnc@test.local',
            'mensaje_personalizado': 'Sin stock en mercado',
            'copia_empleados': [self.empleado.email],
        }
        request = request_post(self.factory, self.user, url, data)
        respuesta = notificar_cliente_pnc(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 200)
        payload = json.loads(respuesta.content)
        self.assertTrue(payload['success'])
        self.assertEqual(payload['data']['estado'], 'enviada_cliente')

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'enviada_cliente')

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, ESTADO_ST_PNC)

        self.assertTrue(mock_delay.called)
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs.get('email_cliente'), 'cliente.pnc@test.local')

    @patch('almacen.tasks.notificar_cliente_pnc_task.delay')
    def test_sin_email_rechaza(self, mock_delay) -> None:
        """Sin email del cliente → 400 y no encola."""
        url = reverse('almacen:notificar_cliente_pnc', args=[self.solicitud.pk])
        request = request_post(self.factory, self.user, url, {'email_cliente': ''})
        respuesta = notificar_cliente_pnc(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 400)
        payload = json.loads(respuesta.content)
        self.assertFalse(payload['success'])
        mock_delay.assert_not_called()
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'enviada_front')

    @patch('almacen.tasks.notificar_cliente_pnc_task.delay')
    def test_sin_orden_solo_cambia_solicitud(self, mock_delay) -> None:
        """Sin orden: igual pasa a enviada_cliente y manda correo."""
        mock_delay.return_value = MagicMock(id='task-pnc-sin-orden')
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_front',
        )
        url = reverse('almacen:notificar_cliente_pnc', args=[solicitud.pk])
        data = {'email_cliente': 'consulta@test.local'}
        request = request_post(self.factory, self.user, url, data)
        respuesta = notificar_cliente_pnc(request, solicitud.pk)

        self.assertEqual(respuesta.status_code, 200)
        payload = json.loads(respuesta.content)
        self.assertTrue(payload['success'])

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'enviada_cliente')
        self.assertEqual(solicitud.email_cliente, 'consulta@test.local')
        mock_delay.assert_called_once()
