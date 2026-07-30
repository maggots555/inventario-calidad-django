"""
Tests de humo: selector de cursor personalizado en Mi Perfil.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No abrimos el navegador ni tocamos localStorage. Solo comprobamos que:
1) La vista mi_perfil responde 200 para un empleado con usuario.
2) El HTML incluye el botón y el modal del selector de cursor.
3) En la vista de directorio (perfil ajeno) NO aparece el selector.

Usamos RequestFactory (no Client HTTP) para evitar Django-Axes y
PaisMiddleware / multi-BD en el ciclo completo de request.
"""

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico import views_perfil


User = get_user_model()


def _request_autenticado(factory: RequestFactory, user, path: str):
    """
    Arma un GET autenticado listo para llamar vistas que usan messages/sesión.

    Args:
        factory: RequestFactory de Django.
        user: instancia User autenticada.
        path: ruta URL (path) del request.

    Efectos secundarios: ninguno sobre BD salvo SessionStore si escribe.
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
            # Evita exigir manifest de collectstatic para CSS/JS nuevos
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class SelectorCursorMiPerfilTest(TestCase):
    """
    Humo del markup de personalizar cursor en Mi Perfil.

    Objetivo de negocio: cada usuario puede abrir el modal desde su perfil.
    Efectos: solo render HTML; la preferencia vive en localStorage (cliente).
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        """
        Crea sucursal, usuario técnico y gerente (para vista directorio).

        Args:
            (ninguno — setUp de Django TestCase)

        Efectos secundarios:
            Inserta Sucursal, Users y Empleados en la BD de pruebas.
        """
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Cursor Test',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='cursor_user',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            user=self.user,
            nombre_completo='Empleado Cursor',
            cargo='Técnico',
            area='Laboratorio',
            rol='tecnico',
            sucursal=self.sucursal,
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )
        self.user_gerente = User.objects.create_user(
            username='cursor_gerente',
            password='testpass123',
        )
        self.empleado_gerente = Empleado.objects.create(
            user=self.user_gerente,
            nombre_completo='Gerente Cursor',
            cargo='Gerente',
            area='Gerencia',
            rol='gerente_general',
            sucursal=self.sucursal,
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )

    def test_mi_perfil_incluye_modal_personalizar_cursor(self):
        """
        Mi Perfil (vista propia) muestra botón y modal del selector.

        Args:
            (ninguno)

        Efectos secundarios: ninguno (solo GET vía RequestFactory).
        """
        url = reverse('servicio_tecnico:mi_perfil')
        request = _request_autenticado(self.factory, self.user, url)
        response = views_perfil.mi_perfil(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')

        self.assertIn('Personalizar cursor', content)
        self.assertIn('btn-personalizar-cursor', content)
        self.assertIn('modalPersonalizarCursor', content)
        self.assertIn('cursor-options-grid', content)
        self.assertIn('data-cursor-id="tech"', content)
        self.assertIn('data-cursor-id="classic"', content)
        self.assertIn('data-cursor-id="minimal"', content)
        self.assertIn('data-cursor-id="system"', content)

    def test_perfil_directorio_no_incluye_selector_cursor(self):
        """
        Al ver el perfil de otro empleado no debe salir el selector.

        Args:
            (ninguno)

        Efectos secundarios: ninguno (solo GET).
        """
        url = reverse(
            'servicio_tecnico:perfil_empleado',
            kwargs={'empleado_id': self.empleado.pk},
        )
        request = _request_autenticado(self.factory, self.user_gerente, url)
        response = views_perfil.perfil_empleado(request, self.empleado.pk)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertNotIn('modalPersonalizarCursor', content)
        self.assertNotIn('btn-personalizar-cursor', content)
