"""
Humo del layout staff: navbar superior sin sidebar lateral.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Tras retirar la barra lateral, queremos un test automático que falle si
alguien vuelve a meter `id="appSidebar"` en base.html o si se rompe la
navbar superior (única navegación global del backoffice).

Usamos RequestFactory + render_to_string (no Client) para evitar el
middleware multi-tenant, igual que otros tests de inventario.
"""

from django.contrib.auth.models import User
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase, override_settings


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            # Evita exigir manifest de collectstatic para CSS/JS nuevos
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class LayoutBaseSinSidebarTest(TestCase):
    """
    Objetivo: confirmar que base.html ya no incluye la sidebar lateral
    y que la navbar superior sigue presente.

    Efectos secundarios: crea un User mínimo en la BD de pruebas.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Crea factory y un usuario autenticado para renderizar el layout."""
        self.factory = RequestFactory()
        self.usuario = User.objects.create_user(
            username='layout_sidebar_test',
            password='testpass123',
        )

    def _request_autenticado(self):
        """
        Arma un request GET con sesión y messages (como en páginas staff).

        Returns:
            HttpRequest listo para render_to_string con context processors.
        """
        request = self.factory.get('/')
        request.user = self.usuario
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return request

    def test_base_html_sin_sidebar_con_navbar_superior(self):
        """
        base.html no debe tener appSidebar/overlay; sí modern-navbar y menú.
        """
        # Paso 1: renderizar el layout completo (como hereda casi toda página staff)
        html = render_to_string('base.html', {}, request=self._request_autenticado())

        # Paso 2: la sidebar lateral y su overlay ya no deben existir
        self.assertNotIn('id="appSidebar"', html)
        self.assertNotIn('id="sidebarOverlay"', html)
        self.assertNotIn('id="sidebarToggle"', html)
        self.assertNotIn('class="app-sidebar"', html)

        # Paso 3: la navegación canónica (navbar superior) debe seguir ahí
        self.assertIn('modern-navbar', html)
        self.assertIn('id="navbarToggle"', html)
        self.assertIn('navbar-menu', html)

        # Paso 4: el wrapper de contenido sigue (ancho completo, sin colapso)
        self.assertIn('id="mainWrapper"', html)
        self.assertNotIn('sidebar-collapsed', html)
        self.assertNotIn('sidebar-loading', html)

    def test_navbar_almacen_usa_etiqueta_corta_en_desktop(self):
        """
        En desktop el menú muestra "Almacén"; el texto largo va a menu-text-full (móvil).

        EXPLICACIÓN PARA PRINCIPIANTES:
        Esto ahorra ancho horizontal para que la barra quepa al 100% de zoom
        en laptops típicas, igual que "Config" vs "Configuración".
        """
        html = render_to_string('base.html', {}, request=self._request_autenticado())

        # Label corta visible en desktop
        self.assertIn('class="menu-text">Almacén</span>', html)
        # Label completa para el panel móvil
        self.assertIn('class="menu-text-full">Almacén/Compras</span>', html)
        # No debe repetir el texto largo en menu-text (evitar overflow)
        self.assertNotIn('class="menu-text">Almacén/Compras</span>', html)
