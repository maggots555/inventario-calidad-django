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
            requiere_accion=True,
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
        self.assertIn('accion', data)
        self.assertGreaterEqual(len(data['accion']), 1)
        item = data['accion'][0]
        self.assertEqual(item.get('categoria'), 'equipo_disponible')
        self.assertTrue(item.get('requiere_accion'))


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
        self.assertTrue(notif.requiere_accion)


class OrdenPendientesYContadoresSedeTest(TestCase):
    """
    «Por hacer» pone lo no leído arriba y cuenta Satélite / Drop Off aparte.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Si una notificación ya se abrió, baja debajo de las que siguen
    pendientes, aunque sea más nueva. El numerito de Equipo disponible
    suma las tres categorías; cada sede tiene el suyo.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        from django.core.cache import cache
        cache.clear()
        self.user = User.objects.create_user(
            username='api_sede',
            password='testpass123',
        )
        self.factory = RequestFactory()

    def _listar(self) -> dict:
        import json
        request = self.factory.get('/notificaciones/api/listar/')
        request.user = self.user
        response = notif_views.obtener_notificaciones(request)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content.decode())

    def test_no_leidas_van_antes_que_una_vista_mas_nueva(self):
        """La más nueva, si ya se vio, queda al final del corte."""
        from datetime import timedelta

        from django.utils import timezone

        ahora = timezone.now()
        pendiente_vieja = Notificacion.objects.create(
            titulo='Pendiente vieja',
            mensaje='Sigue abierta',
            tipo='info',
            usuario=self.user,
            requiere_accion=True,
        )
        pendiente_nueva = Notificacion.objects.create(
            titulo='Pendiente nueva',
            mensaje='También abierta',
            tipo='info',
            usuario=self.user,
            requiere_accion=True,
        )
        vista_reciente = Notificacion.objects.create(
            titulo='Ya vista',
            mensaje='Se abrió',
            tipo='info',
            usuario=self.user,
            requiere_accion=True,
            leida=True,
        )
        # Paso: las fechas se fijan a mano para no depender del orden de alta.
        pendiente_vieja.fecha_creacion = ahora - timedelta(hours=5)
        pendiente_vieja.save(update_fields=['fecha_creacion'])
        pendiente_nueva.fecha_creacion = ahora - timedelta(hours=1)
        pendiente_nueva.save(update_fields=['fecha_creacion'])
        vista_reciente.fecha_creacion = ahora
        vista_reciente.save(update_fields=['fecha_creacion'])

        ids = [item['id'] for item in self._listar()['accion']]
        self.assertEqual(
            ids,
            [pendiente_nueva.pk, pendiente_vieja.pk, vista_reciente.pk],
        )

    def test_contadores_separan_satelite_y_dropoff(self):
        """El chip general suma las tres; cada sede cuenta solo la suya."""
        Notificacion.objects.create(
            titulo='General',
            mensaje='Otra sede',
            tipo='info',
            usuario=self.user,
            categoria='equipo_disponible',
            requiere_accion=True,
        )
        Notificacion.objects.create(
            titulo='Satélite',
            mensaje='Lista en Satélite',
            tipo='info',
            usuario=self.user,
            categoria='equipo_disponible_satelite',
            requiere_accion=True,
        )
        Notificacion.objects.create(
            titulo='Drop Off',
            mensaje='Lista en Drop Off',
            tipo='info',
            usuario=self.user,
            categoria='equipo_disponible_dropoff',
            requiere_accion=True,
        )
        # Ya abierta: sigue contando. La tarea no está hecha hasta el correo.
        Notificacion.objects.create(
            titulo='Satélite vista',
            mensaje='Ya se abrió',
            tipo='info',
            usuario=self.user,
            categoria='equipo_disponible_satelite',
            requiere_accion=True,
            leida=True,
        )
        # Ya cumplida: sale del chip.
        from django.utils import timezone
        Notificacion.objects.create(
            titulo='Drop Off hecha',
            mensaje='Correo enviado',
            tipo='info',
            usuario=self.user,
            categoria='equipo_disponible_dropoff',
            requiere_accion=True,
            leida=True,
            cumplida=True,
            fecha_cumplida=timezone.now(),
        )
        data = self._listar()
        self.assertEqual(data['no_leidas_equipo'], 4)
        self.assertEqual(data['no_leidas_equipo_satelite'], 2)
        self.assertEqual(data['no_leidas_equipo_dropoff'], 1)


class ReclasificarAvisosExistentesTest(TestCase):
    """La migración mueve avisos viejos según el nombre que ya trae el mensaje."""

    databases = {'default', 'mexico'}

    def test_mensaje_con_sede_cambia_categoria(self):
        from django.apps import apps
        from django.db import connections
        import importlib

        migracion = importlib.import_module(
            'notificaciones.migrations.0009_reclasificar_equipo_por_sucursal'
        )

        user = User.objects.create_user(
            username='mig_sede',
            password='testpass123',
        )
        satelite = Notificacion.objects.create(
            titulo='Equipo listo',
            mensaje=(
                'La orden SIC-1 (S/T: ABC) está lista en Satélite. '
                'Notifica al cliente que puede recolectar el equipo.'
            ),
            tipo='info',
            usuario=user,
            categoria='equipo_disponible',
            requiere_accion=True,
        )
        dropoff = Notificacion.objects.create(
            titulo='Equipo listo',
            mensaje=(
                'La orden SIC-2 (S/T: DEF) está lista en Drop Off Sur. '
                'Notifica al cliente que puede recolectar el equipo.'
            ),
            tipo='info',
            usuario=user,
            categoria='equipo_disponible',
            requiere_accion=True,
        )
        otra = Notificacion.objects.create(
            titulo='Equipo listo',
            mensaje=(
                'La orden SIC-3 (S/T: GHI) está lista en Guadalajara. '
                'Notifica al cliente que puede recolectar el equipo.'
            ),
            tipo='info',
            usuario=user,
            categoria='equipo_disponible',
            requiere_accion=True,
        )
        oow = Notificacion.objects.create(
            titulo='Equipo listo',
            mensaje=(
                'La orden OOW-1 (S/T: JKL) está lista. '
                'Notifica al cliente que puede recolectar el equipo.'
            ),
            tipo='info',
            usuario=user,
            categoria='equipo_disponible',
            requiere_accion=True,
        )

        class _Editor:
            """Imita el schema_editor: solo nos importa el alias de la base."""

            connection = connections['default']

        migracion.reclasificar_equipo_por_sucursal(apps, _Editor())
        satelite.refresh_from_db()
        dropoff.refresh_from_db()
        otra.refresh_from_db()
        oow.refresh_from_db()
        self.assertEqual(satelite.categoria, 'equipo_disponible_satelite')
        self.assertEqual(dropoff.categoria, 'equipo_disponible_dropoff')
        self.assertEqual(otra.categoria, 'equipo_disponible')
        self.assertEqual(oow.categoria, 'equipo_disponible')
