"""
Tests: notificaciones al cerrar respuesta de cotización (aceptar / rechazar).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando el cliente termina de responder todas las piezas/servicios, el sistema
debe avisar:

- Aceptación total/parcial CON piezas → solo rol Compras (push + campanita + email Celery)
- Aceptación SOLO servicios (piezas rechazadas) → responsable de seguimiento; no Compras
- Rechazo total → Compras + técnico asignado + responsable de seguimiento

Estos tests mockean push/campanita/Celery para no enviar nada real en CI.
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from almacen.models import LineaCotizacion, LineaServicioAdicional, SolicitudCotizacion
from almacen.tests.helpers_integracion_cotizacion import BaseIntegracionCotizacionMixin
from almacen.utils.notificar_respuesta_cotizacion import (
    obtener_destinatarios_rechazo,
    obtener_empleados_compras,
)
from inventario.models import Empleado

User = get_user_model()


class NotificarRespuestaCotizacionTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Integración del hook en actualizar_estado_segun_lineas + helpers de destinatarios.

    Objetivo de negocio:
        Cubrir aceptación (solo Compras), rechazo (Compras+ST) y bordes
        (pendientes, sin orden, deduplicación).
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='NOTIF-RESP')
        # Empleado de Compras distinto al técnico (self.empleado es recepcionista)
        self.user_compras = User.objects.create_user(
            username='compras_notif_resp',
            password='testpass123',
            email='compras.notif@test.local',
        )
        self.empleado_compras = Empleado.objects.create(
            user=self.user_compras,
            nombre_completo='Compras Notif',
            cargo='Compras',
            area='COMPRAS',
            email='compras.notif@test.local',
            sucursal=self.sucursal,
            rol='compras',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )
        # Responsable de seguimiento distinto del técnico
        self.user_resp = User.objects.create_user(
            username='responsable_notif_resp',
            password='testpass123',
            email='responsable.notif@test.local',
        )
        self.empleado_responsable = Empleado.objects.create(
            user=self.user_resp,
            nombre_completo='Responsable Seguimiento',
            cargo='Dispatcher',
            area='FRONTDESK',
            email='responsable.notif@test.local',
            sucursal=self.sucursal,
            rol='dispatcher',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )

    def _crear_linea_extra(self, solicitud: SolicitudCotizacion, *, sufijo: str) -> LineaCotizacion:
        """Segunda línea pendiente para escenarios parciales / pendientes."""
        return LineaCotizacion.objects.create(
            solicitud=solicitud,
            producto=self.producto,
            proveedor=self.proveedor,
            descripcion_pieza=f'Pieza extra {sufijo}',
            cantidad=1,
            costo_unitario=Decimal('80.00'),
            precio_unitario_cliente=Decimal('160.00'),
            estado_cliente='pendiente',
        )

    def test_obtener_empleados_compras(self) -> None:
        """El filtro de rol compras incluye al empleado de Compras creado."""
        compras = obtener_empleados_compras()
        ids = {e.pk for e in compras}
        self.assertIn(self.empleado_compras.pk, ids)
        self.assertNotIn(self.empleado.pk, ids)

    def test_destinatarios_rechazo_con_orden_incluye_tres_roles(self) -> None:
        """
        Con orden: Compras + técnico + responsable (3 personas distintas).
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-NOTIF-RECH-01',
            estado='cotizacion',
        )
        # self.empleado ya es tecnico_asignado_actual en el helper
        orden.responsable_seguimiento = self.empleado_responsable
        orden.save(update_fields=['responsable_seguimiento'])

        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            estado='enviada_cliente',
        )

        destinatarios = obtener_destinatarios_rechazo(solicitud)
        user_ids = {e.user_id for e in destinatarios}
        self.assertEqual(len(user_ids), 3)
        self.assertIn(self.user_compras.pk, user_ids)
        self.assertIn(self.empleado.user_id, user_ids)
        self.assertIn(self.user_resp.pk, user_ids)

    def test_destinatarios_rechazo_dedup_tecnico_igual_responsable(self) -> None:
        """Si técnico y responsable son la misma persona, solo aparece una vez."""
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-NOTIF-DEDUP-01',
            estado='cotizacion',
        )
        # Técnico = responsable = self.empleado
        orden.responsable_seguimiento = self.empleado
        orden.save(update_fields=['responsable_seguimiento'])

        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            estado='enviada_cliente',
        )

        destinatarios = obtener_destinatarios_rechazo(solicitud)
        user_ids = [e.user_id for e in destinatarios]
        # Compras + técnico/responsable (1) = 2 únicos
        self.assertEqual(len(user_ids), len(set(user_ids)))
        self.assertEqual(len(set(user_ids)), 2)
        self.assertIn(self.empleado.user_id, set(user_ids))

    def test_destinatarios_rechazo_sin_orden_solo_compras(self) -> None:
        """Sin orden ST: solo Compras (no hay técnico/responsable)."""
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
        )
        destinatarios = obtener_destinatarios_rechazo(solicitud)
        user_ids = {e.user_id for e in destinatarios}
        self.assertEqual(user_ids, {self.user_compras.pk})

    @patch('almacen.utils.notificar_respuesta_cotizacion.enviar_push_y_campanita')
    @patch(
        'almacen.tasks.notificar_compras_cotizacion_aceptada_task.delay'
    )
    @patch(
        'almacen.tasks.notificar_respuesta_cotizacion_rechazada_task.delay'
    )
    def test_aceptacion_total_notifica_solo_compras(
        self,
        mock_delay_rechazo,
        mock_delay_aceptada,
        mock_push_campanita,
    ) -> None:
        """
        Al aprobar la única línea pendiente → totalmente_aprobada y aviso a Compras.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-NOTIF-ACEP-01',
            estado='cotizacion',
        )
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=orden,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )

        # Simula la aprobación del cliente (dispara actualizar_estado_segun_lineas)
        linea.aprobar()

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'totalmente_aprobada')

        mock_delay_aceptada.assert_called_once()
        self.assertEqual(mock_delay_aceptada.call_args.args[0], solicitud.pk)
        mock_delay_rechazo.assert_not_called()

        # Push/campanita solo a lista de compradores (1 en este test)
        mock_push_campanita.assert_called_once()
        empleados_notif = list(mock_push_campanita.call_args.args[0])
        self.assertEqual({e.pk for e in empleados_notif}, {self.empleado_compras.pk})

    @patch('almacen.utils.notificar_respuesta_cotizacion.enviar_push_y_campanita')
    @patch(
        'almacen.tasks.notificar_compras_cotizacion_aceptada_task.delay'
    )
    def test_aceptacion_parcial_notifica_compras(
        self,
        mock_delay_aceptada,
        mock_push_campanita,
    ) -> None:
        """Mezcla aprobada + rechazada → parcialmente_aprobada y notifica Compras."""
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-NOTIF-PARC-01',
            estado='cotizacion',
        )
        solicitud, linea1 = self._crear_solicitud_con_linea(
            orden=orden,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        linea2 = self._crear_linea_extra(solicitud, sufijo='PARC')

        linea1.aprobar()
        # Aún hay pendiente: no debe notificar todavía
        mock_delay_aceptada.assert_not_called()

        linea2.rechazar(motivo='Costo alto')
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'parcialmente_aprobada')
        mock_delay_aceptada.assert_called_once()
        mock_push_campanita.assert_called()

    @patch('almacen.utils.notificar_respuesta_cotizacion.enviar_push_y_campanita')
    @patch(
        'almacen.tasks.notificar_compras_cotizacion_aceptada_task.delay'
    )
    @patch(
        'almacen.tasks.notificar_respuesta_cotizacion_rechazada_task.delay'
    )
    def test_con_pendientes_no_notifica(
        self,
        mock_delay_rechazo,
        mock_delay_aceptada,
        mock_push_campanita,
    ) -> None:
        """Si queda al menos una línea pendiente, no se cierra ni se notifica."""
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-NOTIF-PEND-01',
            estado='cotizacion',
        )
        solicitud, linea1 = self._crear_solicitud_con_linea(
            orden=orden,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        self._crear_linea_extra(solicitud, sufijo='PEND')

        linea1.aprobar()
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'enviada_cliente')
        mock_delay_aceptada.assert_not_called()
        mock_delay_rechazo.assert_not_called()
        mock_push_campanita.assert_not_called()

    @patch('almacen.utils.notificar_respuesta_cotizacion.enviar_push_y_campanita')
    @patch(
        'almacen.tasks.notificar_respuesta_cotizacion_rechazada_task.delay'
    )
    @patch(
        'almacen.tasks.notificar_compras_cotizacion_aceptada_task.delay'
    )
    def test_rechazo_total_notifica_compras_tecnico_responsable(
        self,
        mock_delay_aceptada,
        mock_delay_rechazo,
        mock_push_campanita,
    ) -> None:
        """
        Rechazo total con orden: email de rechazo encolado y push a 3 roles.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-NOTIF-RECH-02',
            estado='cotizacion',
        )
        orden.responsable_seguimiento = self.empleado_responsable
        orden.save(update_fields=['responsable_seguimiento'])

        solicitud, linea = self._crear_solicitud_con_linea(
            orden=orden,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        linea.rechazar(motivo='Cliente no autorizó')

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'totalmente_rechazada')

        mock_delay_rechazo.assert_called_once()
        self.assertEqual(mock_delay_rechazo.call_args.args[0], solicitud.pk)
        mock_delay_aceptada.assert_not_called()

        empleados_notif = list(mock_push_campanita.call_args.args[0])
        user_ids = {e.user_id for e in empleados_notif}
        self.assertEqual(
            user_ids,
            {self.user_compras.pk, self.empleado.user_id, self.user_resp.pk},
        )

    @patch('almacen.utils.notificar_respuesta_cotizacion.enviar_push_y_campanita')
    @patch(
        'almacen.tasks.notificar_respuesta_cotizacion_rechazada_task.delay'
    )
    def test_rechazo_sin_orden_solo_compras(
        self,
        mock_delay_rechazo,
        mock_push_campanita,
    ) -> None:
        """Rechazo sin orden: solo Compras en push/campanita."""
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        linea.rechazar(motivo='Sin presupuesto')

        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'totalmente_rechazada')
        mock_delay_rechazo.assert_called_once()

        empleados_notif = list(mock_push_campanita.call_args.args[0])
        self.assertEqual({e.pk for e in empleados_notif}, {self.empleado_compras.pk})

    @patch('almacen.utils.notificar_respuesta_cotizacion.enviar_push_y_campanita')
    @patch(
        'almacen.tasks.notificar_compras_cotizacion_aceptada_task.delay'
    )
    def test_no_renotifica_si_estado_ya_cerrado(
        self,
        mock_delay_aceptada,
        mock_push_campanita,
    ) -> None:
        """
        Llamar otra vez actualizar_estado_segun_lineas ya cerrado no reenvía.

        EXPLICACIÓN: el hook compara estado_previo vs nuevo; si no cambió, silencio.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-NOTIF-REENT-01',
            estado='cotizacion',
        )
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=orden,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        linea.aprobar()
        self.assertEqual(mock_delay_aceptada.call_count, 1)

        # Reentrada con estado ya totalmente_aprobada
        solicitud.refresh_from_db()
        solicitud.actualizar_estado_segun_lineas()
        self.assertEqual(mock_delay_aceptada.call_count, 1)
        self.assertEqual(mock_push_campanita.call_count, 1)

    @patch('almacen.utils.notificar_respuesta_cotizacion.enviar_push_y_campanita')
    @patch(
        'almacen.tasks.notificar_compras_cotizacion_aceptada_task.delay'
    )
    def test_aceptacion_solo_servicio_avisa_responsable_no_compras(
        self,
        mock_delay_aceptada,
        mock_push_campanita,
    ) -> None:
        """
        Piezas rechazadas + limpieza aceptada: no email a Compras;
        push al responsable de seguimiento para «Generar servicio».
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-NOTIF-SRV-01',
            estado='cotizacion',
        )
        orden.responsable_seguimiento = self.empleado_responsable
        orden.save(update_fields=['responsable_seguimiento'])

        solicitud, linea = self._crear_solicitud_con_linea(
            orden=orden,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        servicio = LineaServicioAdicional.objects.create(
            solicitud=solicitud,
            tipo_servicio='limpieza',
            costo=Decimal('450.00'),
            estado_cliente='pendiente',
        )

        linea.rechazar(motivo='No autorizó la pieza')
        mock_delay_aceptada.assert_not_called()
        mock_push_campanita.assert_not_called()

        servicio.aprobar()
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'parcialmente_aprobada')

        mock_delay_aceptada.assert_not_called()
        mock_push_campanita.assert_called_once()
        empleados_notif = list(mock_push_campanita.call_args.args[0])
        self.assertEqual({e.pk for e in empleados_notif}, {self.empleado_responsable.pk})
        self.assertIn('Generar servicio', mock_push_campanita.call_args.kwargs['mensaje'])
