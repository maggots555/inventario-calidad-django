"""
Humo del manual de órdenes con diagnóstico (OOW).

EXPLICACIÓN PARA PRINCIPIANTES:
Usamos RequestFactory (no Client) para no pasar por PaisMiddleware, igual
que el resto de tests de inventario. Cada capítulo debe exigir login y,
con usuario autenticado, pintar 200.
"""

from django.contrib.auth.models import AnonymousUser, User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventario.models import Empleado
from inventario.views_manual import (
    VISTAS_MANUAL_HUMOS,
    manual_indice,
    manual_rol_facturacion,
    manual_rol_front,
    resolver_area_manual,
)


def _request(factory, user, path):
    """
    Arma un GET con sesión y messages para llamar la vista directo.

    Args:
        factory: RequestFactory.
        user: User o AnonymousUser.
        path: ruta (ej. /manual/).

    Returns:
        HttpRequest listo para la vista.
    """
    request = factory.get(path)
    request.user = user
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    return request


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class ManualUsuarioHumoTests(TestCase):
    """
    Objetivo: el manual OOW es interno (login) y todas las páginas responden.

    Efectos secundarios: crea un User y un Empleado de prueba.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Crea factory, usuario staff y ficha de recepcionista (Front)."""
        self.factory = RequestFactory()
        self.usuario = User.objects.create_user(
            username='manual_front',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Recepción de prueba',
            cargo='Recepcionista',
            area='Recepción',
            email='manual.front@example.com',
            activo=True,
            user=self.usuario,
            rol='recepcionista',
        )

    def test_anonimo_redirige_a_login_en_todas_las_paginas(self) -> None:
        """Sin sesión, cada capítulo manda a /login/."""
        for nombre_url, vista, _slug in VISTAS_MANUAL_HUMOS:
            path = reverse(nombre_url)
            request = _request(self.factory, AnonymousUser(), path)
            response = vista(request)
            self.assertEqual(
                response.status_code,
                302,
                msg=f'{nombre_url} debía redirigir sin login',
            )
            self.assertIn('/login/', response.url)

    def test_autenticado_obtiene_200_en_todas_las_paginas(self) -> None:
        """Con sesión, cada capítulo pinta HTML 200 y el título del índice."""
        user = User.objects.get(pk=self.usuario.pk)
        for nombre_url, vista, _slug in VISTAS_MANUAL_HUMOS:
            path = reverse(nombre_url)
            request = _request(self.factory, user, path)
            response = vista(request)
            self.assertEqual(response.status_code, 200, msg=f'{nombre_url} no respondió 200')
            html = response.content.decode()
            self.assertIn('OOW · diagnóstico', html)
            self.assertIn(path, html)

    def test_navbar_incluye_enlace_al_manual(self) -> None:
        """El manual es un botón de acción (como la campana), no un ítem del menú."""
        request = _request(self.factory, self.usuario, '/')
        html = render_to_string('base.html', {}, request=request)
        self.assertIn(reverse('manual:indice'), html)
        self.assertIn('title="Manual órdenes con diagnóstico (OOW)"', html)
        self.assertIn('bi-journal-bookmark', html)
        # Ya no vive en el menú de módulos (Inventario, Almacén, Config…)
        self.assertNotIn('class="menu-text">Manual</span>', html)
        self.assertNotIn('class="menu-text-full">Manual de operación</span>', html)

    def test_recepcionista_ve_chip_tu_area_en_front(self) -> None:
        """El rol Recepcionista se traduce a Front y marca «Tu área»."""
        self.assertEqual(resolver_area_manual(self.usuario), 'front')
        path = reverse('manual:rol_front')
        request = _request(self.factory, self.usuario, path)
        response = manual_rol_front(request)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Tu área', html)
        self.assertIn('rol Recepcionista', html)

    def test_portada_tiene_titulo_oow_diagrama_y_menciona_fl(self) -> None:
        """La portada se llama OOW, trae el diagrama clicable y deja FL para otro manual."""
        path = reverse('manual:indice')
        request = _request(self.factory, self.usuario, path)
        response = manual_indice(request)
        html = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertIn('Manual órdenes con diagnóstico (OOW)', html)
        self.assertIn('Diagrama de flujo', html)
        self.assertIn('aria-label="Diagrama de flujo de órdenes con diagnóstico OOW"', html)
        self.assertIn('¿Qué contestó el cliente?', html)
        self.assertIn('Venta mostrador (FL)', html)
        self.assertIn(reverse('manual:acepta'), html)
        self.assertIn(reverse('manual:recotizacion'), html)

    def test_facturacion_ve_chip_tu_area(self) -> None:
        """El rol Facturación tiene capítulo propio y marca «Tu área»."""
        usuario_fact = User.objects.create_user(
            username='manual_fact',
            password='testpass123',
        )
        Empleado.objects.create(
            nombre_completo='Facturación de prueba',
            cargo='Facturación',
            area='Administración',
            email='manual.fact@example.com',
            activo=True,
            user=usuario_fact,
            rol='facturacion',
        )
        self.assertEqual(resolver_area_manual(usuario_fact), 'facturacion')
        path = reverse('manual:rol_facturacion')
        request = _request(self.factory, usuario_fact, path)
        response = manual_rol_facturacion(request)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Tu área', html)
        self.assertIn('Pagos por validar', html)
        self.assertIn('Ya aparece', html)
