"""
Tests de humo tras modularizar helpers y vistas SICSER fuera de views.py.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Estos tests NO llaman a la API real de SICSER. Solo confirman que:
1) Los nombres siguen disponibles en servicio_tecnico.views (urls.py no se rompe).
2) registrar_historial escribe en BD desde services.historial.
3) El decorador de permisos redirige si falta el permiso.
4) Las URLs nombradas de SICSER resuelven al callable correcto.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse, resolve

from inventario.models import Empleado, Sucursal
from servicio_tecnico.decorators import permission_required_with_message
from servicio_tecnico.models import HistorialOrden, OrdenServicio
from servicio_tecnico.services.historial import registrar_historial
from servicio_tecnico import views as st_views
from servicio_tecnico import views_sicser


User = get_user_model()


class CompatibilidadReexportsViewsTest(SimpleTestCase):
    """
    Verifica que views.py reexporta lo extraído (sin tocar BD).

    Objetivo: si alguien borra un import por error, urls.py dejaría de ver
    views.consultar_sicser y fallaría al arrancar o al resolver rutas.
    """

    def test_views_reexporta_helpers_y_sicser(self):
        """Los símbolos públicos siguen en el módulo views."""
        self.assertTrue(callable(st_views.permission_required_with_message))
        self.assertTrue(callable(st_views.registrar_historial))
        self.assertIs(st_views.consultar_sicser, views_sicser.consultar_sicser)
        self.assertIs(st_views.importar_orden_sicser, views_sicser.importar_orden_sicser)

    def test_urls_sicser_resuelven_al_modulo_nuevo(self):
        """reverse/resolve apuntan a las funciones de views_sicser."""
        # Paso 1: armar la URL con el name que usa el proyecto
        url_consulta = reverse('servicio_tecnico:consultar_sicser')
        url_importar = reverse('servicio_tecnico:importar_orden_sicser')

        # Paso 2: resolve() dice qué función atenderá esa URL
        match_consulta = resolve(url_consulta)
        match_importar = resolve(url_importar)

        self.assertIs(match_consulta.func, views_sicser.consultar_sicser)
        self.assertIs(match_importar.func, views_sicser.importar_orden_sicser)


class RegistrarHistorialServiceTest(TestCase):
    """
    Prueba que el servicio de historial persiste un evento en BD.

    Efectos secundarios del helper bajo prueba: INSERT en HistorialOrden.
    """

    def setUp(self):
        """
        Crea sucursal + técnico + orden mínima para poder registrar historial.

        Args:
            (ninguno — setUp de Django TestCase)

        Efectos secundarios:
            Inserta Sucursal, Empleado y OrdenServicio en la BD de pruebas.
        """
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Test Modularización',
            ciudad='CDMX',
        )
        self.tecnico = Empleado.objects.create(
            nombre_completo='Técnico Test',
            cargo='Técnico',
            area='Laboratorio',
            sucursal=self.sucursal,
        )
        # OrdenServicio.save() genera numero_orden_interno y un evento 'creacion'
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tecnico_asignado_actual=self.tecnico,
            tipo_servicio='diagnostico',
        )

    def test_registrar_historial_crea_evento(self):
        """registrar_historial deja un HistorialOrden con los datos enviados."""
        # Contamos cuántos eventos había (al menos el de creación automática)
        antes = HistorialOrden.objects.filter(orden=self.orden).count()

        evento = registrar_historial(
            orden=self.orden,
            tipo_evento='comentario',
            usuario=self.tecnico,
            comentario='Prueba modularización historial',
            es_sistema=False,
        )

        self.assertIsNotNone(evento.pk)
        self.assertEqual(evento.tipo_evento, 'comentario')
        self.assertEqual(evento.comentario, 'Prueba modularización historial')
        self.assertEqual(evento.usuario_id, self.tecnico.pk)
        self.assertFalse(evento.es_sistema)
        self.assertEqual(
            HistorialOrden.objects.filter(orden=self.orden).count(),
            antes + 1,
        )

    def test_import_desde_views_sigue_siendo_el_mismo_callable(self):
        """Compatibilidad: from servicio_tecnico.views import registrar_historial."""
        from servicio_tecnico.views import registrar_historial as desde_views

        self.assertIs(desde_views, registrar_historial)


class PermissionRequiredDecoratorTest(TestCase):
    """
    Verifica el decorador de permisos sin pasar por una vista de negocio real.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='user_sin_perm_st',
            password='test-pass-123',
        )
        self.user_con_perm = User.objects.create_user(
            username='user_con_perm_st',
            password='test-pass-123',
        )
        # Asignar permiso real de ST (view_ordenservicio)
        ct = ContentType.objects.get_for_model(OrdenServicio)
        perm = Permission.objects.get(
            content_type=ct,
            codename='view_ordenservicio',
        )
        self.user_con_perm.user_permissions.add(perm)

    def test_sin_permiso_redirige_a_acceso_denegado(self):
        """Si falta el permiso, no ejecuta la vista y redirige."""
        # Vista falsa solo para el test
        @permission_required_with_message('servicio_tecnico.view_ordenservicio')
        def vista_falsa(request):
            return 'ok'

        request = self.factory.get('/fake/')
        request.user = self.user
        respuesta = vista_falsa(request)

        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('acceso-denegado', respuesta.url)
        self.assertIn('permiso=servicio_tecnico.view_ordenservicio', respuesta.url)

    def test_con_permiso_ejecuta_la_vista(self):
        """Con permiso, el decorador deja pasar al cuerpo de la vista."""
        @permission_required_with_message('servicio_tecnico.view_ordenservicio')
        def vista_falsa(request):
            return 'ok'

        request = self.factory.get('/fake/')
        request.user = self.user_con_perm
        self.assertEqual(vista_falsa(request), 'ok')
