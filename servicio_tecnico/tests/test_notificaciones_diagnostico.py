"""
Tests: avisos al guardar Diagnóstico SIC por primera vez.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando el SIC pasa de vacío a con texto, el sistema debe avisar:
- Responsable de seguimiento (compartir con el cliente)
- Personal con rol Compras (cotizar piezas)

Canales mockeados: push/campanita y Celery (.delay), sin envío real en CI.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, HistorialOrden, OrdenServicio
from servicio_tecnico.services.cierre_diagnostico import (
    aplicar_fecha_fin_al_guardar_diagnostico_sic,
)
from servicio_tecnico.services.notificaciones_diagnostico import (
    notificar_diagnostico_sic_listo,
)

User = get_user_model()


class NotificacionesDiagnosticoSICTest(TestCase):
    """
    Objetivo: validar destinatarios y anti-spam del aviso de SIC listo.

    Efectos: crea sucursal, empleados con user y órdenes mínimas.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Notif Diag SIC',
            ciudad='CDMX',
        )
        self.empleado_tecnico = Empleado.objects.create(
            nombre_completo='Técnico Notif Diag',
            cargo='Técnico',
            area='Laboratorio',
            email='tecnico.notif.diag@test.local',
            sucursal=self.sucursal,
            rol='tecnico',
            activo=True,
        )

        self.user_responsable = User.objects.create_user(
            username='resp_notif_diag',
            password='testpass123',
            email='resp.notif.diag@test.local',
        )
        self.empleado_responsable = Empleado.objects.create(
            user=self.user_responsable,
            nombre_completo='Responsable Notif Diag',
            cargo='Dispatcher',
            area='FRONTDESK',
            email='resp.notif.diag@test.local',
            sucursal=self.sucursal,
            rol='dispatcher',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )

        self.user_compras = User.objects.create_user(
            username='compras_notif_diag',
            password='testpass123',
            email='compras.notif.diag@test.local',
        )
        self.empleado_compras = Empleado.objects.create(
            user=self.user_compras,
            nombre_completo='Compras Notif Diag',
            cargo='Compras',
            area='COMPRAS',
            email='compras.notif.diag@test.local',
            sucursal=self.sucursal,
            rol='compras',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )

    def _crear_orden(
        self,
        *,
        tipo_servicio: str = 'diagnostico',
        estado: str = 'diagnostico',
        diagnostico_sic: str = '',
        responsable=None,
    ) -> OrdenServicio:
        """
        Crea orden + detalle con SIC y responsable opcional.

        Args:
            tipo_servicio: Código de tipo de servicio.
            estado: Estado inicial.
            diagnostico_sic: Texto del SIC.
            responsable: Empleado responsable de seguimiento o None.

        Returns:
            OrdenServicio con DetalleEquipo.
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio=tipo_servicio,
            estado=estado,
            tecnico_asignado_actual=self.empleado_tecnico,
            responsable_seguimiento=responsable,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='OOW-NOTIF-SIC',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-NOTIF-SIC',
            email_cliente='cliente.notif@test.local',
            nombre_cliente='Cliente Notif',
            falla_principal='No enciende',
            diagnostico_sic=diagnostico_sic,
        )
        return orden

    @patch(
        'servicio_tecnico.tasks_diagnostico.notificar_diagnostico_sic_listo_task.delay'
    )
    @patch(
        'servicio_tecnico.services.notificaciones_diagnostico'
        '.enviar_push_y_campanita'
    )
    def test_primera_vez_con_texto_avisa_responsable_y_compras(
        self,
        mock_push_campanita,
        mock_email_delay,
    ):
        """
        Feliz: SIC vacío → con texto notifica a ambas audiencias y encola email.
        """
        mock_push_campanita.side_effect = [1, 1]

        orden = self._crear_orden(responsable=self.empleado_responsable)
        sic_nuevo = 'Falla en regulador de voltaje; requiere placa madre.'

        resultado = notificar_diagnostico_sic_listo(
            orden,
            diagnostico_sic_anterior='',
            diagnostico_sic_nuevo=sic_nuevo,
        )

        self.assertEqual(resultado['responsable'], 1)
        self.assertEqual(resultado['compras'], 1)
        self.assertEqual(mock_push_campanita.call_count, 2)
        mock_email_delay.assert_called_once()
        self.assertEqual(mock_email_delay.call_args[0][0], orden.pk)
        self.assertIn(
            mock_email_delay.call_args[1]['db_alias'],
            ('default', 'mexico'),
        )

        historial = HistorialOrden.objects.filter(
            orden=orden,
            tipo_evento='sistema',
        ).last()
        self.assertIsNotNone(historial)
        self.assertIn('responsable seguimiento', historial.comentario)
        self.assertIn('Compras', historial.comentario)

    @patch(
        'servicio_tecnico.services.notificaciones_diagnostico'
        '.enviar_push_y_campanita'
    )
    @patch(
        'servicio_tecnico.tasks_diagnostico.notificar_diagnostico_sic_listo_task.delay'
    )
    def test_reedicion_sic_no_notifica(
        self,
        mock_email_delay,
        mock_push_campanita,
    ):
        """Si el SIC ya tenía texto, editar no dispara avisos."""
        orden = self._crear_orden(responsable=self.empleado_responsable)

        resultado = notificar_diagnostico_sic_listo(
            orden,
            diagnostico_sic_anterior='Diagnóstico previo.',
            diagnostico_sic_nuevo='Diagnóstico previo ampliado.',
        )

        self.assertEqual(resultado['responsable'], 0)
        self.assertEqual(resultado['compras'], 0)
        mock_push_campanita.assert_not_called()
        mock_email_delay.assert_not_called()

    @patch(
        'servicio_tecnico.tasks_diagnostico.notificar_diagnostico_sic_listo_task.delay'
    )
    @patch(
        'servicio_tecnico.services.notificaciones_diagnostico'
        '.enviar_push_y_campanita'
    )
    def test_sin_responsable_solo_compras(
        self,
        mock_push_campanita,
        mock_email_delay,
    ):
        """Sin responsable asignado, solo Compras recibe push/campanita."""
        mock_push_campanita.return_value = 1

        orden = self._crear_orden(responsable=None)

        resultado = notificar_diagnostico_sic_listo(
            orden,
            diagnostico_sic_anterior='',
            diagnostico_sic_nuevo='Requiere batería y teclado.',
        )

        self.assertEqual(resultado['responsable'], 0)
        self.assertEqual(resultado['compras'], 1)
        self.assertEqual(mock_push_campanita.call_count, 1)
        mock_email_delay.assert_called_once()

    @patch(
        'servicio_tecnico.tasks_diagnostico.notificar_diagnostico_sic_listo_task.delay'
    )
    @patch(
        'servicio_tecnico.services.notificaciones_diagnostico'
        '.enviar_push_y_campanita'
    )
    def test_sin_compras_solo_responsable(
        self,
        mock_push_campanita,
        mock_email_delay,
    ):
        """Sin empleados Compras, solo el responsable recibe aviso."""
        self.empleado_compras.delete()
        mock_push_campanita.return_value = 1

        orden = self._crear_orden(responsable=self.empleado_responsable)

        resultado = notificar_diagnostico_sic_listo(
            orden,
            diagnostico_sic_anterior='',
            diagnostico_sic_nuevo='Pantalla rota; cotizar display.',
        )

        self.assertEqual(resultado['responsable'], 1)
        self.assertEqual(resultado['compras'], 0)
        self.assertEqual(mock_push_campanita.call_count, 1)
        mock_email_delay.assert_called_once()

    @patch(
        'servicio_tecnico.services.notificaciones_diagnostico'
        '.enviar_push_y_campanita'
    )
    @patch(
        'servicio_tecnico.tasks_diagnostico.notificar_diagnostico_sic_listo_task.delay'
    )
    def test_venta_mostrador_no_notifica(
        self,
        mock_email_delay,
        mock_push_campanita,
    ):
        """Venta Mostrador no dispara avisos de diagnóstico SIC."""
        orden = self._crear_orden(
            tipo_servicio='venta_mostrador',
            responsable=self.empleado_responsable,
        )

        resultado = notificar_diagnostico_sic_listo(
            orden,
            diagnostico_sic_anterior='',
            diagnostico_sic_nuevo='Texto SIC en VM.',
        )

        self.assertEqual(resultado['responsable'], 0)
        self.assertEqual(resultado['compras'], 0)
        mock_push_campanita.assert_not_called()
        mock_email_delay.assert_not_called()

    @patch(
        'servicio_tecnico.services.notificaciones_diagnostico'
        '.notificar_diagnostico_sic_listo'
    )
    def test_integracion_cierre_diagnostico_llama_notificacion(
        self,
        mock_notificar,
    ):
        """
        El helper de cierre invoca notificar_diagnostico_sic_listo al guardar SIC.
        """
        orden = self._crear_orden(responsable=self.empleado_responsable)
        detalle = orden.detalle_equipo
        detalle.diagnostico_sic = 'Diagnóstico integración helper.'
        detalle.save(update_fields=['diagnostico_sic'])

        aplicar_fecha_fin_al_guardar_diagnostico_sic(
            detalle,
            orden,
            self.empleado_tecnico,
            fecha_fin_anterior=None,
            diagnostico_sic_anterior='',
        )

        mock_notificar.assert_called_once_with(
            orden,
            diagnostico_sic_anterior='',
            diagnostico_sic_nuevo='Diagnóstico integración helper.',
        )
