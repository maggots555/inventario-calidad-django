"""
Tests de humo tras extraer multimedia (Fase 5).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No subimos FFmpeg ni archivos reales. Solo confirmamos que:
1) urls.py resuelve eliminar/descargar al módulo nuevo.
2) views.py reexporta compressors y vistas HTTP.
3) detalle_orden sigue viendo comprimir_y_guardar_imagen (import de services).
4) El service tiene Image/ImagenOrden (regresión NameError).
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve, reverse

from servicio_tecnico import views as st_views
from servicio_tecnico import views_multimedia
from servicio_tecnico.models import ImagenOrden
from servicio_tecnico.services import multimedia as multimedia_svc
from servicio_tecnico.views_multimedia import eliminar_imagen


User = get_user_model()


class CompatibilidadMultimediaReexportsTest(SimpleTestCase):
    """Reexports + resolve sin tocar BD."""

    def test_views_reexporta_compressors_y_vistas(self):
        """Compressors y URLs siguen disponibles en servicio_tecnico.views."""
        self.assertIs(
            st_views.comprimir_y_guardar_imagen,
            multimedia_svc.comprimir_y_guardar_imagen,
        )
        self.assertIs(
            st_views.comprimir_y_guardar_video,
            multimedia_svc.comprimir_y_guardar_video,
        )
        self.assertIs(
            st_views.descargar_imagen_original,
            views_multimedia.descargar_imagen_original,
        )
        self.assertIs(st_views.eliminar_imagen, views_multimedia.eliminar_imagen)
        self.assertIs(st_views.eliminar_video, views_multimedia.eliminar_video)

    def test_urls_multimedia_resuelven_modulo_nuevo(self):
        """reverse/resolve apuntan a views_multimedia."""
        casos = [
            (
                'servicio_tecnico:descargar_imagen',
                {'imagen_id': 1},
                views_multimedia.descargar_imagen_original,
            ),
            (
                'servicio_tecnico:eliminar_imagen',
                {'imagen_id': 1},
                views_multimedia.eliminar_imagen,
            ),
            (
                'servicio_tecnico:eliminar_video',
                {'video_id': 1},
                views_multimedia.eliminar_video,
            ),
        ]
        for name, kwargs, expected in casos:
            with self.subTest(name=name):
                url = reverse(name, kwargs=kwargs)
                match = resolve(url)
                self.assertIs(match.func, expected, msg=f'Fallo en {name}')

    def test_compressors_viven_en_services_multimedia(self):
        """__module__ de los helpers apunta a services.multimedia (no al monolito)."""
        self.assertEqual(
            st_views.comprimir_y_guardar_imagen.__module__,
            'servicio_tecnico.services.multimedia',
        )
        self.assertEqual(
            st_views.comprimir_y_guardar_video.__module__,
            'servicio_tecnico.services.multimedia',
        )

    def test_service_tiene_imports_criticos(self):
        """
        Regresión NameError: Image, ImagenOrden, os en el service.

        EXPLICACIÓN PARA PRINCIPIANTES:
        En el monolito Image/os venían del import global de views.py.
        Al mover, deben vivir en services/multimedia.py.
        """
        for nombre in ('Image', 'ImageOps', 'ImagenOrden', 'VideoOrden', 'os'):
            with self.subTest(nombre=nombre):
                self.assertTrue(
                    hasattr(multimedia_svc, nombre),
                    msg=f'Falta {nombre} en services.multimedia',
                )

    def test_views_multimedia_tiene_imports_criticos(self):
        """Regresión: JsonResponse, HistorialOrden, os en views_multimedia."""
        for nombre in (
            'JsonResponse',
            'HistorialOrden',
            'ImagenOrden',
            'VideoOrden',
            'os',
            'get_object_or_404',
            'messages',
        ):
            with self.subTest(nombre=nombre):
                self.assertTrue(
                    hasattr(views_multimedia, nombre),
                    msg=f'Falta {nombre} en views_multimedia',
                )


class EliminarImagenPermisoSmokeTest(TestCase):
    """
    Smoke: eliminar_imagen sin empleado activo responde 403 JSON.

    Efectos secundarios: crea User en BD de pruebas (sin tocar archivos).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='test_eliminar_img',
            password='testpass123',
        )
        # Permiso del decorador (si falta, redirige a acceso denegado en vez de JSON)
        ct = ContentType.objects.get_for_model(ImagenOrden)
        permiso = Permission.objects.get(
            content_type=ct,
            codename='delete_imagenorden',
        )
        self.user.user_permissions.add(permiso)
        self.factory = RequestFactory()

    def test_sin_empleado_responde_403_json(self):
        """
        Usuario con permiso Django pero sin perfil Empleado → 403 JSON.

        EXPLICACIÓN PARA PRINCIPIANTES:
        La vista exige request.user.empleado activo además del permiso.
        Así comprobamos que la lógica movida sigue protegida.
        """
        request = self.factory.post('/servicio-tecnico/imagenes/1/eliminar/')
        request.user = self.user

        response = eliminar_imagen(request, imagen_id=1)

        self.assertEqual(response.status_code, 403)
        self.assertIn(b'success', response.content)
