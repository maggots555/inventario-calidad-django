"""
Tests: notificar al cliente PNC (partes no disponibles) + bloqueo aprobar.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1) Util sync: con orden → ST a PNC; sin orden → no toca ST.
2) Ya en PNC → comentario de reaviso (no cambia estado).
3) Vista HTTP: primer aviso + flag; reenvío solo con flag.
4) Helper/vista: no aprobar tras PNC sin cotización/REAC.
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
from almacen.utils.cotizacion_items_cliente import solicitud_permite_aprobar_lineas
from almacen.utils.sincronizar_estado_st import (
    ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR,
    ESTADO_ST_PNC,
    sincronizar_estado_st_al_notificar_cliente_pnc,
    sincronizar_estado_st_por_respuesta_cliente,
)
from almacen.views import (
    aprobar_todas_lineas,
    notificar_cliente_pnc,
    responder_linea_cotizacion,
)


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

    def test_ya_en_pnc_registra_comentario_reaviso(self) -> None:
        """Si ya está en PNC, registra comentario de reaviso sin cambiar estado."""
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-PNC-CLI-02',
            estado=ESTADO_ST_PNC,
        )
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_cliente',
        )
        comentarios_antes = orden.historial.filter(tipo_evento='comentario').count()

        cambiado = sincronizar_estado_st_al_notificar_cliente_pnc(
            solicitud,
            usuario=self.user,
        )

        self.assertTrue(cambiado)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, ESTADO_ST_PNC)
        self.assertEqual(
            orden.historial.filter(tipo_evento='comentario').count(),
            comentarios_antes + 1,
        )
        ultimo = (
            orden.historial.filter(tipo_evento='comentario')
            .order_by('-fecha_evento')
            .first()
        )
        self.assertIn('re-notificado', (ultimo.comentario or '').lower())
        self.assertIn(linea.descripcion_pieza, ultimo.comentario or '')

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
    def test_feliz_pasa_a_enviada_cliente_flag_y_pnc(self, mock_delay) -> None:
        """POST válido: enviada_cliente + flag + ST PNC + Celery."""
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
        self.assertFalse(payload['data'].get('es_reenvio'))

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'enviada_cliente')
        self.assertTrue(self.solicitud.aviso_pnc_cliente_enviado)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, ESTADO_ST_PNC)

        self.assertTrue(mock_delay.called)
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs.get('email_cliente'), 'cliente.pnc@test.local')

    @patch('almacen.tasks.notificar_cliente_pnc_task.delay')
    def test_reenvio_con_flag_encola_sin_romper_estado(self, mock_delay) -> None:
        """Reenvío en enviada_cliente + flag: Celery OK, estado intacto."""
        mock_delay.return_value = MagicMock(id='task-pnc-reenvio')
        self.solicitud.estado = 'enviada_cliente'
        self.solicitud.aviso_pnc_cliente_enviado = True
        self.solicitud.save(
            update_fields=['estado', 'aviso_pnc_cliente_enviado'],
        )
        self.orden.estado = ESTADO_ST_PNC
        self.orden.save(update_fields=['estado'])

        url = reverse('almacen:notificar_cliente_pnc', args=[self.solicitud.pk])
        data = {'email_cliente': 'cliente.pnc@test.local'}
        request = request_post(self.factory, self.user, url, data)
        respuesta = notificar_cliente_pnc(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 200)
        payload = json.loads(respuesta.content)
        self.assertTrue(payload['success'])
        self.assertTrue(payload['data'].get('es_reenvio'))

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'enviada_cliente')
        self.assertTrue(self.solicitud.aviso_pnc_cliente_enviado)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, ESTADO_ST_PNC)
        mock_delay.assert_called_once()

    @patch('almacen.tasks.notificar_cliente_pnc_task.delay')
    def test_reenvio_sin_flag_rechaza(self, mock_delay) -> None:
        """enviada_cliente sin flag PNC → 400 (flujo normal con cotización)."""
        self.solicitud.estado = 'enviada_cliente'
        self.solicitud.aviso_pnc_cliente_enviado = False
        self.solicitud.save(
            update_fields=['estado', 'aviso_pnc_cliente_enviado'],
        )

        url = reverse('almacen:notificar_cliente_pnc', args=[self.solicitud.pk])
        data = {'email_cliente': 'cliente.pnc@test.local'}
        request = request_post(self.factory, self.user, url, data)
        respuesta = notificar_cliente_pnc(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 400)
        payload = json.loads(respuesta.content)
        self.assertFalse(payload['success'])
        mock_delay.assert_not_called()

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
        """Sin orden: igual pasa a enviada_cliente, marca flag y manda correo."""
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
        self.assertTrue(solicitud.aviso_pnc_cliente_enviado)
        self.assertEqual(solicitud.email_cliente, 'consulta@test.local')
        mock_delay.assert_called_once()


class NotificarClientePncTaskTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Task Celery notificar_cliente_pnc_task: asunto con ⚠️ y plantilla.

    EXPLICACIÓN PARA PRINCIPIANTES:
    No usa el broker real. Con .run() ejecutamos la tarea en el test y
    interceptamos EmailMessage.send para revisar asunto y cuerpo HTML.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='PNC-TASK')
        self.solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
        )
        self.solicitud.nombre_cliente = 'Cliente Prueba PNC'
        self.solicitud.aviso_pnc_cliente_enviado = True
        self.solicitud.save(
            update_fields=['nombre_cliente', 'aviso_pnc_cliente_enviado'],
        )

    def test_asunto_incluye_emoji_y_cuerpo_carta(self) -> None:
        """Asunto con ⚠️; HTML con carta SIC MÉXICO y footer de recepción."""
        from almacen.tasks import notificar_cliente_pnc_task

        capturados = []

        def _fake_send(self_msg, fail_silently=False):
            # EXPLICACIÓN: capturamos el EmailMessage real sin salir a la red
            capturados.append(self_msg)
            return 1

        with patch(
            'django.core.mail.EmailMessage.send',
            new=_fake_send,
        ):
            resultado = notificar_cliente_pnc_task.run(
                solicitud_id=self.solicitud.pk,
                email_cliente='cliente.pnc@test.local',
                mensaje_personalizado='',
                copia_empleados=[],
                usuario_id=self.user.pk,
                db_alias='default',
            )

        self.assertTrue(resultado.get('success'))
        self.assertEqual(len(capturados), 1)
        msg = capturados[0]

        # Remitente: Compras (no Almacén) en correos PNC al cliente
        self.assertIn('Sistema de Compras', msg.from_email)

        # Asunto: emoji de advertencia al inicio (igual patrón PNC recepción)
        self.assertTrue(
            msg.subject.startswith('⚠️'),
            f'El asunto debe empezar con ⚠️; recibió: {msg.subject!r}',
        )
        self.assertIn('componentes no disponibles', msg.subject)
        # Sin orden vinculada → el asunto debe llevar S/T, no OOW-
        self.assertIn('S/T:', msg.subject)

        body = msg.body
        self.assertIn('Componentes no disponibles para cotización', body)
        self.assertIn('Me dirijo de SIC MÉXICO', body)
        self.assertIn('correo automático no supervisado', body)
        self.assertIn('NO RESPONDA', body)
        self.assertIn('responsable de seguimiento', body)
        self.assertIn('Visítanos y síguenos en nuestras redes sociales', body)


class SolicitudPermiteAprobarLineasTest(BaseIntegracionCotizacionMixin, TestCase):
    """Helper: bloqueo de aprobar tras aviso PNC hasta cotización/REAC."""

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='PNC-APR')

    def test_sin_flag_permite(self) -> None:
        """Flujo normal sin aviso PNC → se puede aprobar."""
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
        )
        self.assertFalse(solicitud.aviso_pnc_cliente_enviado)
        self.assertTrue(solicitud_permite_aprobar_lineas(solicitud))

    def test_con_flag_sin_alternativa_bloquea(self) -> None:
        """Con flag PNC y sin cotización/REAC → no aprobar."""
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
        )
        solicitud.aviso_pnc_cliente_enviado = True
        solicitud.save(update_fields=['aviso_pnc_cliente_enviado'])
        self.assertFalse(solicitud_permite_aprobar_lineas(solicitud))

    def test_con_flag_y_tipo_servicio_permite(self) -> None:
        """Tras enviar cotización (tipo_servicio_cliente) → sí aprobar."""
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
        )
        solicitud.aviso_pnc_cliente_enviado = True
        solicitud.tipo_servicio_cliente = 'estandar'
        solicitud.save(
            update_fields=['aviso_pnc_cliente_enviado', 'tipo_servicio_cliente'],
        )
        self.assertTrue(solicitud_permite_aprobar_lineas(solicitud))

    def test_con_flag_y_reac_permite(self) -> None:
        """Con snapshot REAC → sí aprobar."""
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
        )
        solicitud.aviso_pnc_cliente_enviado = True
        solicitud.resultado_costeo_reac = {'total_precio_contado_mxn': 12000}
        solicitud.save(
            update_fields=['aviso_pnc_cliente_enviado', 'resultado_costeo_reac'],
        )
        self.assertTrue(solicitud_permite_aprobar_lineas(solicitud))


class AprobarTrasPncVistaTest(BaseIntegracionCotizacionMixin, TestCase):
    """Vista: rechaza aprobar si hubo PNC sin cotización/REAC."""

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='PNC-APR-V')
        self.solicitud, self.linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
        )
        self.solicitud.aviso_pnc_cliente_enviado = True
        self.solicitud.save(update_fields=['aviso_pnc_cliente_enviado'])

    def test_aprobar_linea_bloqueada(self) -> None:
        """POST aprobar línea → mensaje de error y línea sigue pendiente."""
        url = reverse(
            'almacen:responder_linea_cotizacion',
            args=[self.solicitud.pk, self.linea.pk],
        )
        request = request_post(
            self.factory,
            self.user,
            url,
            {'decision': 'aprobar'},
        )
        respuesta = responder_linea_cotizacion(
            request,
            self.solicitud.pk,
            self.linea.pk,
        )

        self.assertEqual(respuesta.status_code, 302)
        self.linea.refresh_from_db()
        self.assertEqual(self.linea.estado_cliente, 'pendiente')

    def test_aprobar_todas_bloqueada(self) -> None:
        """POST aprobar todas → no cambia líneas."""
        url = reverse('almacen:aprobar_todas_lineas', args=[self.solicitud.pk])
        request = request_post(self.factory, self.user, url, {})
        respuesta = aprobar_todas_lineas(request, self.solicitud.pk)

        self.assertEqual(respuesta.status_code, 302)
        self.linea.refresh_from_db()
        self.assertEqual(self.linea.estado_cliente, 'pendiente')

    def test_aprobar_linea_permitida_tras_tipo_servicio(self) -> None:
        """Con tipo_servicio_cliente, aprobar línea sí funciona."""
        self.solicitud.tipo_servicio_cliente = 'mostrador'
        self.solicitud.save(update_fields=['tipo_servicio_cliente'])

        url = reverse(
            'almacen:responder_linea_cotizacion',
            args=[self.solicitud.pk, self.linea.pk],
        )
        request = request_post(
            self.factory,
            self.user,
            url,
            {'decision': 'aprobar'},
        )
        respuesta = responder_linea_cotizacion(
            request,
            self.solicitud.pk,
            self.linea.pk,
        )

        self.assertEqual(respuesta.status_code, 302)
        self.linea.refresh_from_db()
        self.assertEqual(self.linea.estado_cliente, 'aprobada')
