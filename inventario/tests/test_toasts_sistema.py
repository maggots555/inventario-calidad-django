"""
Humo de los toasts de sistema (django.contrib.messages en base.html).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Las vistas avisan al usuario con messages.success/error/... Django los
guarda en la sesión y base.html los pinta. Antes eran barras .alert
arriba del contenido; ahora son toasts flotantes (#sigma-toast-stack).

Este test no abre el navegador. Solo renderiza base.html con mensajes
en el request y comprueba que el HTML nuevo existe y el viejo ya no.
La barra inferior (sigma-toast__timer) es el temporizador visual.
"""

from django.contrib import messages
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
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class ToastsSistemaTest(TestCase):
    """
    Objetivo: el layout staff pinta messages como toasts profesionales
    (no como alertas Bootstrap que empujan el contenido).

    Efectos secundarios: crea un User mínimo en la BD de pruebas.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Crea factory y un usuario autenticado para renderizar el layout."""
        self.factory = RequestFactory()
        self.usuario = User.objects.create_user(
            username='toast_sistema_test',
            password='testpass123',
        )

    def _request_con_mensajes(self):
        """
        Arma un GET autenticado y le mete un mensaje de cada tipo.

        Returns:
            HttpRequest listo para render_to_string con context processors.
        """
        request = self.factory.get('/')
        request.user = self.usuario
        request.session = SessionStore()
        # FallbackStorage es el almacén de messages en tests (sin cookies reales)
        request._messages = FallbackStorage(request)

        messages.success(request, 'Pedido guardado')
        messages.error(request, 'No se pudo guardar')
        messages.warning(request, 'Revisa el stock')
        messages.info(request, 'Hay una actualizacion')
        return request

    def test_base_html_carga_css_de_toasts(self):
        """base.html debe enlazar toasts.css (si se quita, el look se rompe)."""
        request = self._request_con_mensajes()
        html = render_to_string('base.html', {}, request=request)

        self.assertIn('css/toasts.css', html)

    def test_messages_se_pintan_como_toasts_no_como_alertas(self):
        """
        Cada level_tag tiene su toast; el bloque viejo de .alert ya no existe.
        """
        request = self._request_con_mensajes()
        html = render_to_string('base.html', {}, request=request)

        # Paso 1: el contenedor flotante siempre identifica el sistema nuevo
        self.assertIn('id="sigma-toast-stack"', html)
        self.assertIn('class="sigma-toast-stack"', html)

        # Paso 2: un toast por tipo, con título y texto
        self.assertIn('sigma-toast--success', html)
        self.assertIn('sigma-toast--error', html)
        self.assertIn('sigma-toast--warning', html)
        self.assertIn('sigma-toast--info', html)

        self.assertIn('Éxito', html)
        self.assertIn('Error', html)
        self.assertIn('Aviso', html)
        self.assertIn('Información', html)

        self.assertIn('Pedido guardado', html)
        self.assertIn('No se pudo guardar', html)
        self.assertIn('Revisa el stock', html)
        self.assertIn('Hay una actualizacion', html)

        # Paso 3: ya no se usa el markup viejo (alert + tags de Django)
        self.assertNotIn('alert alert-success alert-dismissible', html)
        self.assertNotIn('alert alert-error alert-dismissible', html)
        self.assertNotIn('alert alert-warning alert-dismissible', html)
        self.assertNotIn('alert alert-info alert-dismissible', html)

        # Paso 4: el stack flota fuera del wrapper (evita recorte overflow)
        pos_stack = html.find('id="sigma-toast-stack"')
        pos_wrapper = html.find('id="mainWrapper"')
        self.assertGreater(pos_stack, 0)
        self.assertGreater(pos_wrapper, pos_stack)

        # Paso 5: cada toast trae la barra-temporizador (se llena mientras está visible)
        self.assertGreaterEqual(html.count('sigma-toast__timer'), 4)
        self.assertGreaterEqual(html.count('sigma-toast__timer-bar'), 4)

    def test_stack_existe_aunque_no_haya_mensajes(self):
        """
        El contenedor vacío debe existir para que mostrarNotificacion()
        en JS tenga dónde pintar.
        """
        request = self.factory.get('/')
        request.user = self.usuario
        request.session = SessionStore()
        request._messages = FallbackStorage(request)

        html = render_to_string('base.html', {}, request=request)

        self.assertIn('id="sigma-toast-stack"', html)
        self.assertNotIn('sigma-toast--success', html)
        self.assertNotIn('sigma-toast--error', html)
