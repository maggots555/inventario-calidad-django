"""
La contraseña temporal no deja bajar archivos de /media/.

EXPLICACIÓN PARA PRINCIPIANTES:
El middleware ya mandaba al empleado a cambiar su clave antes de usar
el sistema, pero /media/ era una excepción. Estas pruebas comprueban
que las fotos y comprobantes también esperan, y que quien ya cambió
la clave sigue pudiendo abrirlos.
"""

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from inventario.middleware import ForcePasswordChangeMiddleware
from inventario.models import Empleado


def _middleware():
    """
    Arma el middleware con una respuesta fija 'ok' si deja pasar.

    Returns:
        ForcePasswordChangeMiddleware listo para __call__.
    """
    def get_response(request):
        return HttpResponse('ok')

    return ForcePasswordChangeMiddleware(get_response)


def _request(factory, path, user):
    """
    Request con sesión y messages, que el middleware usa al avisar.

    Args:
        factory: RequestFactory.
        path: URL que el empleado intenta abrir.
        user: User, o AnonymousUser.

    Returns:
        HttpRequest.
    """
    request = factory.get(path)
    request.user = user
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    return request


class ForcePasswordMediaTests(TestCase):
    """
    Objetivo: /media/ sigue el mismo candado que el resto del sistema.

    Efectos: crea dos empleados (clave temporal y clave ya cambiada).
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = _middleware()
        self.user_temporal = User.objects.create_user(
            username='temporal.media@test.local',
            password='temp12345',
        )
        Empleado.objects.create(
            nombre_completo='Temporal Media',
            cargo='Técnico',
            area='Laboratorio',
            email='temporal.media@test.local',
            user=self.user_temporal,
            rol='tecnico',
            activo=True,
            contraseña_configurada=False,
            tiene_acceso_sistema=True,
        )
        self.user_listo = User.objects.create_user(
            username='listo.media@test.local',
            password='clave-nueva',
        )
        Empleado.objects.create(
            nombre_completo='Listo Media',
            cargo='Técnico',
            area='Laboratorio',
            email='listo.media@test.local',
            user=self.user_listo,
            rol='tecnico',
            activo=True,
            contraseña_configurada=True,
            tiene_acceso_sistema=True,
        )

    def test_clave_temporal_no_abre_media(self):
        """Quien no cambió la clave no descarga la evidencia."""
        request = _request(
            self.factory,
            '/media/mexico/servicio_tecnico/imagenes/OOW-1/ingreso.jpg',
            self.user_temporal,
        )
        response = self.middleware(request)
        # 403, no redirect: cada foto no debe dejar un aviso en la sesión.
        self.assertEqual(response.status_code, 403)
        self.assertNotIn(b'ok', response.content)

    def test_clave_temporal_sigue_viendo_el_css(self):
        """La pantalla de cambio necesita /static/; eso no se bloquea."""
        request = _request(
            self.factory,
            '/static/css/base.css',
            self.user_temporal,
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    def test_clave_ya_cambiada_abre_media(self):
        """Un empleado normal sigue viendo los archivos."""
        request = _request(
            self.factory,
            '/media/mexico/servicio_tecnico/imagenes/OOW-1/ingreso.jpg',
            self.user_listo,
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')

    def test_visitante_sin_sesion_llega_a_la_vista_de_media(self):
        """
        El anónimo no lo frena este middleware.

        La vista de media decide sola: banner público, token o 404.
        """
        request = _request(
            self.factory,
            '/media/mexico/banners/promo.jpg',
            AnonymousUser(),
        )
        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b'ok')
