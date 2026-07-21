"""
Tests: aviso a recepción + correo "Notificar equipo disponible".

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1) Helper anti-dup: egreso vs cambio a finalizado (viceversa).
2) Vista POST: solo en estado finalizado; segundo clic = ya notificado.
3) URL / reexport de humo.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve, reverse

from inventario.models import Empleado, Sucursal
from notificaciones.models import Notificacion
from servicio_tecnico import views as st_views
from servicio_tecnico import views_envios_cliente
from servicio_tecnico.models import DetalleEquipo, HistorialOrden, OrdenServicio
from servicio_tecnico.services.notificaciones_recepcion import (
    notificar_recepcion_equipo_listo,
)


User = get_user_model()


class NotificarEquipoDisponibleReexportTest(SimpleTestCase):
    """Humo: reexport + URL."""

    def test_reexport_y_url(self):
        self.assertIs(
            st_views.notificar_equipo_disponible,
            views_envios_cliente.notificar_equipo_disponible,
        )
        match = resolve(
            reverse('servicio_tecnico:notificar_equipo_disponible', args=[1])
        )
        self.assertIs(match.func, views_envios_cliente.notificar_equipo_disponible)


class AvisoRecepcionEquipoListoTest(TestCase):
    """Anti-duplicado entre disparador egreso y finalizado."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Aviso Recepción',
            ciudad='CDMX',
            direccion='Av. Test 123',
            horario_atencion='Lun-Vie 9-18',
        )
        self.user_resp = User.objects.create_user(
            username='recep_test',
            password='testpass123',
        )
        self.responsable = Empleado.objects.create(
            nombre_completo='Recepcionista Test',
            cargo='Recepcionista',
            area='Recepción',
            email='recep@test.local',
            sucursal=self.sucursal,
            user=self.user_resp,
            rol='recepcionista',
        )
        self.user_tec = User.objects.create_user(
            username='tec_aviso',
            password='testpass123',
        )
        self.tecnico = Empleado.objects.create(
            nombre_completo='Técnico Test',
            cargo='Técnico',
            area='Laboratorio',
            email='tec@test.local',
            sucursal=self.sucursal,
            user=self.user_tec,
            rol='tecnico',
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='control_calidad',
            tecnico_asignado_actual=self.tecnico,
            responsable_seguimiento=self.responsable,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-AVISO-01',
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='Latitude',
            numero_serie='STAVISO01',
            email_cliente='cliente.aviso@test.local',
            nombre_cliente='Cliente Aviso',
            falla_principal='No enciende',
            gama='media',
        )
        # DetalleEquipo.save() marca es_fuera_garantia por prefijo OOW-
        self.orden.refresh_from_db()
        self.assertTrue(self.orden.es_fuera_garantia)

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_aviso_por_egreso_y_omite_finalizado(self, _mock_push):
        """Primero egreso avisa; luego finalizado se omite."""
        ok = notificar_recepcion_equipo_listo(self.orden, motivo='egreso')
        self.assertTrue(ok)
        self.orden.refresh_from_db()
        self.assertTrue(self.orden.aviso_recepcion_listo_enviado)

        notifs = Notificacion.objects.filter(usuario=self.user_resp)
        self.assertGreaterEqual(notifs.count(), 1)

        ok2 = notificar_recepcion_equipo_listo(self.orden, motivo='finalizado')
        self.assertFalse(ok2)
        avisos = HistorialOrden.objects.filter(
            orden=self.orden,
            tipo_evento='sistema',
            comentario__icontains='equipo listo para notificar recolección',
        )
        self.assertEqual(avisos.count(), 1)

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_aviso_por_finalizado_y_omite_egreso(self, _mock_push):
        """Viceversa: primero finalizado; egreso se omite."""
        ok = notificar_recepcion_equipo_listo(self.orden, motivo='finalizado')
        self.assertTrue(ok)
        ok2 = notificar_recepcion_equipo_listo(self.orden, motivo='egreso')
        self.assertFalse(ok2)

    @patch('servicio_tecnico.tasks.enviar_recordatorio_imagen_task')
    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_signal_al_pasar_a_finalizado(self, _mock_push, _mock_recordatorio):
        """Guardar orden en finalizado dispara el signal (una sola vez)."""
        self.assertFalse(self.orden.aviso_recepcion_listo_enviado)
        self.orden.estado = 'finalizado'
        self.orden.save()
        self.orden.refresh_from_db()
        self.assertTrue(self.orden.aviso_recepcion_listo_enviado)
        self.assertGreaterEqual(
            Notificacion.objects.filter(usuario=self.user_resp).count(),
            1,
        )


class DestinatariosGarantiaOowTest(TestCase):
    """
    OOW → recepción; garantía → dispatchers.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Creamos un recepcionista y un dispatcher. Según es_fuera_garantia,
    solo uno de los dos debe recibir la campanita.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Destinatarios',
            ciudad='CDMX',
        )
        self.user_recep = User.objects.create_user(
            username='recep_dest',
            password='testpass123',
        )
        self.recepcionista = Empleado.objects.create(
            nombre_completo='Recepcion Dest',
            cargo='Recepcionista',
            area='Recepción',
            email='recep.dest@test.local',
            sucursal=self.sucursal,
            user=self.user_recep,
            rol='recepcionista',
        )
        self.user_disp = User.objects.create_user(
            username='disp_dest',
            password='testpass123',
        )
        self.dispatcher = Empleado.objects.create(
            nombre_completo='Dispatcher Dest',
            cargo='Dispatcher',
            area='Operaciones',
            email='disp.dest@test.local',
            sucursal=self.sucursal,
            user=self.user_disp,
            rol='dispatcher',
        )
        self.user_tec = User.objects.create_user(
            username='tec_dest',
            password='testpass123',
        )
        self.tecnico = Empleado.objects.create(
            nombre_completo='Tecnico Dest',
            cargo='Técnico',
            area='Laboratorio',
            email='tec.dest@test.local',
            sucursal=self.sucursal,
            user=self.user_tec,
            rol='tecnico',
        )

    def _crear_orden(self, folio: str, responsable=None) -> OrdenServicio:
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='control_calidad',
            tecnico_asignado_actual=self.tecnico,
            responsable_seguimiento=responsable,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente=folio,
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='XPS',
            numero_serie=f'ST-{folio}',
            email_cliente='cliente.dest@test.local',
            nombre_cliente='Cliente Dest',
            falla_principal='Falla test',
            gama='media',
        )
        orden.refresh_from_db()
        return orden

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_oow_notifica_recepcion_no_dispatcher(self, _mock_push):
        """Fuera de garantía: campanita al responsable (recepcionista)."""
        orden = self._crear_orden('OOW-DEST-01', responsable=self.recepcionista)
        self.assertTrue(orden.es_fuera_garantia)

        ok = notificar_recepcion_equipo_listo(orden, motivo='egreso')
        self.assertTrue(ok)

        self.assertGreaterEqual(
            Notificacion.objects.filter(usuario=self.user_recep).count(),
            1,
        )
        self.assertEqual(
            Notificacion.objects.filter(usuario=self.user_disp).count(),
            0,
        )
        historial = HistorialOrden.objects.filter(
            orden=orden,
            comentario__icontains='Aviso a recepción',
        )
        self.assertEqual(historial.count(), 1)

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_garantia_notifica_dispatcher_no_recepcion(self, _mock_push):
        """En garantía: campanita a dispatchers, no a recepción."""
        orden = self._crear_orden('SIC-DEST-99', responsable=self.recepcionista)
        self.assertFalse(orden.es_fuera_garantia)

        ok = notificar_recepcion_equipo_listo(orden, motivo='finalizado')
        self.assertTrue(ok)

        self.assertGreaterEqual(
            Notificacion.objects.filter(usuario=self.user_disp).count(),
            1,
        )
        self.assertEqual(
            Notificacion.objects.filter(usuario=self.user_recep).count(),
            0,
        )
        historial = HistorialOrden.objects.filter(
            orden=orden,
            comentario__icontains='Aviso a dispatchers',
        )
        self.assertEqual(historial.count(), 1)


class NotificarEquipoDisponibleVistaTest(TestCase):
    """POST notificar_equipo_disponible vía RequestFactory (sin Axes/login)."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Correo Disponible',
            ciudad='GDL',
            direccion='Calle Correo 1',
        )
        self.user = User.objects.create_user(
            username='recep_correo',
            password='testpass123',
            is_staff=True,
        )
        # Superuser evita fricción del decorador de permisos en tests
        self.user.is_superuser = True
        self.user.save()
        self.empleado = Empleado.objects.create(
            nombre_completo='Recepcion Correo',
            cargo='Recepcionista',
            area='Recepción',
            email='recep.correo@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='recepcionista',
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='finalizado',
            tecnico_asignado_actual=self.empleado,
            responsable_seguimiento=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-MAIL-01',
            tipo_equipo='Laptop',
            marca='HP',
            modelo='EliteBook',
            numero_serie='STMAIL01',
            email_cliente='cliente.mail@test.local',
            nombre_cliente='Cliente Mail',
            falla_principal='Pantalla',
            gama='alta',
        )
        self.factory = RequestFactory()
        self.url = reverse(
            'servicio_tecnico:notificar_equipo_disponible',
            args=[self.orden.pk],
        )

    def _post(self):
        request = self.factory.post(self.url)
        request.user = self.user
        return views_envios_cliente.notificar_equipo_disponible(
            request, self.orden.pk
        )

    @patch('servicio_tecnico.tasks.enviar_notificacion_equipo_disponible_task')
    def test_post_finalizado_encola_task(self, mock_task):
        mock_task.delay = MagicMock(return_value=MagicMock(id='task-test-1'))
        response = self._post()
        self.assertEqual(response.status_code, 200)
        data = response.json() if hasattr(response, 'json') else None
        if data is None:
            import json
            data = json.loads(response.content.decode())
        self.assertTrue(data['success'])
        self.orden.refresh_from_db()
        self.assertIsNotNone(self.orden.fecha_notificacion_equipo_disponible)
        mock_task.delay.assert_called_once()

    def test_post_estado_no_finalizado_400(self):
        self.orden.estado = 'reparacion'
        self.orden.save(update_fields=['estado'])
        response = self._post()
        self.assertEqual(response.status_code, 400)
        import json
        data = json.loads(response.content.decode())
        self.assertFalse(data['success'])

    @patch('servicio_tecnico.tasks.enviar_notificacion_equipo_disponible_task')
    def test_segundo_post_ya_notificado(self, mock_task):
        mock_task.delay = MagicMock(return_value=MagicMock(id='t1'))
        r1 = self._post()
        self.assertEqual(r1.status_code, 200)
        r2 = self._post()
        self.assertEqual(r2.status_code, 400)
        import json
        data = json.loads(r2.content.decode())
        self.assertTrue(data.get('ya_notificado'))
