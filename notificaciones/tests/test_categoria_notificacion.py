"""
Tests del campo categoria (pestañas de la campanita).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1) crear_notificacion guarda categoria.
2) La API /notificaciones/api/listar/ incluye categoria en el JSON.
3) El aviso de equipo disponible usa categoria='equipo_disponible'.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from inventario.models import Empleado, Sucursal
from notificaciones.models import Notificacion
from notificaciones import views as notif_views
from notificaciones.utils import crear_notificacion, notificar_info
from servicio_tecnico.models import DetalleEquipo, OrdenServicio
from servicio_tecnico.services.notificaciones_recepcion import (
    notificar_recepcion_equipo_listo,
)


User = get_user_model()


class CrearNotificacionCategoriaTest(TestCase):
    """Utils persisten categoria."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.user = User.objects.create_user(
            username='notif_cat',
            password='testpass123',
        )

    def test_crear_notificacion_default_general(self):
        notifs = crear_notificacion(
            titulo='Prueba general',
            mensaje='Sin categoria explícita',
            usuario=self.user,
            app_origen='servicio_tecnico',
        )
        self.assertGreaterEqual(len(notifs), 1)
        self.assertEqual(notifs[0].categoria, 'general')

    def test_crear_notificacion_equipo_disponible(self):
        notifs = crear_notificacion(
            titulo='Equipo listo',
            mensaje='Aviso',
            usuario=self.user,
            categoria='equipo_disponible',
        )
        self.assertEqual(notifs[0].categoria, 'equipo_disponible')

    def test_notificar_info_acepta_categoria(self):
        notifs = notificar_info(
            'Info con categoria',
            'Mensaje',
            usuario=self.user,
            categoria='equipo_disponible',
        )
        self.assertEqual(notifs[0].categoria, 'equipo_disponible')


class ApiListarCategoriaTest(TestCase):
    """JSON de listar incluye categoria (RequestFactory, sin middleware Axes)."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.user = User.objects.create_user(
            username='api_cat',
            password='testpass123',
        )
        Notificacion.objects.create(
            titulo='Aviso equipo',
            mensaje='Detalle',
            tipo='info',
            usuario=self.user,
            categoria='equipo_disponible',
            app_origen='servicio_tecnico',
        )
        self.factory = RequestFactory()

    def test_listar_incluye_categoria(self):
        request = self.factory.get('/notificaciones/api/listar/')
        request.user = self.user
        response = notif_views.obtener_notificaciones(request)
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.content.decode())
        self.assertIn('notificaciones', data)
        self.assertGreaterEqual(len(data['notificaciones']), 1)
        item = data['notificaciones'][0]
        self.assertEqual(item.get('categoria'), 'equipo_disponible')


class AvisoRecepcionCategoriaTest(TestCase):
    """Helper de equipo listo marca categoria equipo_disponible."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Cat Notif',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='recep_cat',
            password='testpass123',
        )
        self.responsable = Empleado.objects.create(
            nombre_completo='Recepcion Cat',
            cargo='Recepcionista',
            area='Recepción',
            email='recep.cat@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='recepcionista',
        )
        self.tecnico_user = User.objects.create_user(
            username='tec_cat',
            password='testpass123',
        )
        self.tecnico = Empleado.objects.create(
            nombre_completo='Tecnico Cat',
            cargo='Técnico',
            area='Lab',
            email='tec.cat@test.local',
            sucursal=self.sucursal,
            user=self.tecnico_user,
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
            orden_cliente='OOW-CAT-01',
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='XPS',
            numero_serie='STCAT01',
            email_cliente='cli.cat@test.local',
            nombre_cliente='Cliente Cat',
            falla_principal='Falla',
            gama='media',
        )
        self.orden.refresh_from_db()

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_aviso_usa_categoria_equipo_disponible(self, _mock_push):
        ok = notificar_recepcion_equipo_listo(self.orden, motivo='egreso')
        self.assertTrue(ok)
        notif = Notificacion.objects.filter(
            usuario=self.user,
            categoria='equipo_disponible',
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn('Equipo listo', notif.titulo)
