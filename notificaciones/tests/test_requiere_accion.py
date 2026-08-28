"""
Tests del campo requiere_accion (pestañas Por hacer / Avisos).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1) crear_notificacion guarda el flag.
2) La API lista DOS cortes (acción vs avisos); 20 avisos nuevos no tapan
   un pendiente más viejo.
3) marcar-avisos solo marca informativas.
4) enviar_push_y_campanita usa True por default y acepta False.
"""

from unittest.mock import patch
import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import RequestFactory, TestCase

from inventario.models import Empleado, Sucursal
from notificaciones import views as notif_views
from notificaciones.models import Notificacion
from notificaciones.utils import crear_notificacion, notificar_info

User = get_user_model()


class CrearNotificacionRequiereAccionTest(TestCase):
    """Utils persisten requiere_accion."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.user = User.objects.create_user(
            username='notif_accion',
            password='testpass123',
        )

    def test_crear_notificacion_default_sin_accion(self):
        notifs = crear_notificacion(
            titulo='Correo enviado',
            mensaje='FYI',
            usuario=self.user,
        )
        self.assertGreaterEqual(len(notifs), 1)
        self.assertFalse(notifs[0].requiere_accion)

    def test_crear_notificacion_con_accion(self):
        notifs = crear_notificacion(
            titulo='Pago por validar',
            mensaje='Revisa la cuenta',
            usuario=self.user,
            requiere_accion=True,
        )
        self.assertTrue(notifs[0].requiere_accion)

    def test_notificar_info_acepta_requiere_accion(self):
        notifs = notificar_info(
            'Equipo listo',
            'Avisa al cliente',
            usuario=self.user,
            requiere_accion=True,
        )
        self.assertTrue(notifs[0].requiere_accion)


class ApiListarDosCortesTest(TestCase):
    """JSON de listar: dos listas, contadores y tope independiente."""

    databases = {'default', 'mexico'}

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='api_accion',
            password='testpass123',
        )
        self.factory = RequestFactory()

    def _listar(self) -> dict:
        request = self.factory.get('/notificaciones/api/listar/')
        request.user = self.user
        response = notif_views.obtener_notificaciones(request)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content.decode())

    def test_listar_incluye_cortes_y_contadores(self):
        Notificacion.objects.create(
            titulo='Pendiente',
            mensaje='Haz esto',
            tipo='warning',
            usuario=self.user,
            requiere_accion=True,
        )
        Notificacion.objects.create(
            titulo='Correo enviado',
            mensaje='FYI',
            tipo='exito',
            usuario=self.user,
            requiere_accion=False,
        )
        data = self._listar()
        self.assertEqual(data['no_leidas_accion'], 1)
        self.assertEqual(data['no_leidas_avisos'], 1)
        self.assertEqual(data['no_leidas'], 1)
        self.assertEqual(len(data['accion']), 1)
        self.assertEqual(len(data['avisos']), 1)
        self.assertFalse(data.get('hay_mas_accion'))
        self.assertFalse(data.get('hay_mas_avisos'))
        self.assertTrue(data['accion'][0]['requiere_accion'])
        self.assertFalse(data['avisos'][0]['requiere_accion'])

    def test_avisos_recientes_no_ocultan_accion_vieja(self):
        """
        El tope de 20 era mezclado: 20 correos nuevos escondían un pago viejo.
        Ahora cada corte tiene su propio tope.
        """
        accion = Notificacion.objects.create(
            titulo='Pago por validar viejo',
            mensaje='Sigue pendiente',
            tipo='warning',
            usuario=self.user,
            requiere_accion=True,
        )
        # 25 avisos más nuevos que el pendiente (auto_now_add no se pisa fácil:
        # el orden de creación basta: la acción se creó primero).
        for i in range(25):
            Notificacion.objects.create(
                titulo=f'Aviso {i}',
                mensaje='Ruido Celery',
                tipo='exito',
                usuario=self.user,
                requiere_accion=False,
            )
        data = self._listar()
        ids_accion = [item['id'] for item in data['accion']]
        self.assertIn(accion.pk, ids_accion)
        self.assertEqual(len(data['avisos']), 20)
        self.assertEqual(data['no_leidas_accion'], 1)
        self.assertTrue(data.get('hay_mas_avisos'))
        self.assertFalse(data.get('hay_mas_accion'))

    def test_contador_equipo_solo_accion_no_leida(self):
        Notificacion.objects.create(
            titulo='Equipo listo',
            mensaje='Avisa',
            tipo='info',
            usuario=self.user,
            categoria='equipo_disponible',
            requiere_accion=True,
        )
        Notificacion.objects.create(
            titulo='Equipo disponible notificado',
            mensaje='Ya se envió',
            tipo='exito',
            usuario=self.user,
            categoria='equipo_disponible',
            requiere_accion=False,
        )
        data = self._listar()
        self.assertEqual(data['no_leidas_equipo'], 1)


class MarcarAvisosNoTocaAccionTest(TestCase):
    """POST marcar-avisos deja intactas las de Por hacer."""

    databases = {'default', 'mexico'}

    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username='api_marcar_avisos',
            password='testpass123',
        )
        self.factory = RequestFactory()
        self.accion = Notificacion.objects.create(
            titulo='Pago pendiente',
            mensaje='Valida',
            tipo='warning',
            usuario=self.user,
            requiere_accion=True,
        )
        self.aviso = Notificacion.objects.create(
            titulo='Video listo',
            mensaje='OK',
            tipo='exito',
            usuario=self.user,
            requiere_accion=False,
        )

    def test_marcar_avisos_no_toca_accion(self):
        request = self.factory.post('/notificaciones/api/marcar-avisos/')
        request.user = self.user
        response = notif_views.marcar_avisos_leidos(request)
        self.assertEqual(response.status_code, 200)
        self.accion.refresh_from_db()
        self.aviso.refresh_from_db()
        self.assertFalse(self.accion.leida)
        self.assertTrue(self.aviso.leida)
        body = json.loads(response.content.decode())
        self.assertEqual(body.get('no_leidas_accion'), 1)
        self.assertEqual(body.get('no_leidas_avisos'), 0)


class EnviarPushYCampanitaFlagTest(TestCase):
    """El helper de negocio default True; False para confirmaciones."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Flag Notif',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='flag_campanita',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Compras Flag',
            cargo='Compras',
            area='Compras',
            email='flag.campanita@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='compras',
            activo=True,
        )

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_default_requiere_accion_true(self, _mock_push):
        from almacen.utils.notificar_respuesta_cotizacion import enviar_push_y_campanita

        enviar_push_y_campanita(
            [self.empleado],
            titulo='Cotización aceptada',
            mensaje='Genera compras',
            url='/almacen/solicitudes/1/',
        )
        notif = Notificacion.objects.filter(
            usuario=self.user,
            titulo='Cotización aceptada',
        ).first()
        self.assertIsNotNone(notif)
        self.assertTrue(notif.requiere_accion)

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_explicito_false_queda_aviso(self, _mock_push):
        from almacen.utils.notificar_respuesta_cotizacion import enviar_push_y_campanita

        enviar_push_y_campanita(
            [self.empleado],
            titulo='Pago validado en cuenta',
            mensaje='Ya aparece',
            url='/st/orden/1/',
            requiere_accion=False,
        )
        notif = Notificacion.objects.filter(
            usuario=self.user,
            titulo='Pago validado en cuenta',
        ).first()
        self.assertIsNotNone(notif)
        self.assertFalse(notif.requiere_accion)
