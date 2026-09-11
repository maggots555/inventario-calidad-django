"""
Tests del formulario de sucursal (alta / edición) y confirmación de baja.

EXPLICACIÓN PARA PRINCIPIANTES:
RequestFactory evita PaisMiddleware (mismas razones que test_lista_sucursales).
"""

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventario.models import Sucursal
from inventario.views import crear_sucursal, editar_sucursal, eliminar_sucursal


def _request_con_usuario(factory: RequestFactory, user: User, path: str):
    """
    Arma un request GET listo para llamar la vista (sesión + messages).

    Args:
        factory: RequestFactory de Django
        user: usuario autenticado
        path: ruta URL

    Returns:
        HttpRequest con user, session y messages.
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
class FormSucursalTests(TestCase):
    """
    Objetivo: humo del rediseño de crear / editar / confirmar eliminar.

    Efectos secundarios: crea usuario, permisos y una sucursal de prueba.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Crea factory, permisos CRUD de sucursal y una sede de ejemplo."""
        self.factory = RequestFactory()

        ct = ContentType.objects.get_for_model(Sucursal)
        perm_add = Permission.objects.get(content_type=ct, codename='add_sucursal')
        perm_change = Permission.objects.get(content_type=ct, codename='change_sucursal')
        perm_delete = Permission.objects.get(content_type=ct, codename='delete_sucursal')

        self.usuario = User.objects.create_user(
            username='editor_suc',
            password='testpass123',
        )
        self.usuario.user_permissions.add(perm_add, perm_change, perm_delete)

        self.sucursal = Sucursal.objects.create(
            codigo='SUC010',
            nombre='Satélite',
            ciudad='Naucalpan',
            responsable='Ana Encargada',
            activa=True,
        )

    def test_crear_responde_200_y_marca_layout_nuevo(self) -> None:
        """Humo GET crear: 200 y CSS/JS del formulario rediseñado."""
        user = User.objects.get(pk=self.usuario.pk)
        url = reverse('crear_sucursal')
        response = crear_sucursal(_request_con_usuario(self.factory, user, url))

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('form-sucursal-page', content)
        self.assertIn('css/form_sucursal.css', content)
        self.assertIn('js/form_sucursal.js', content)
        self.assertIn('Nueva sucursal', content)
        self.assertNotIn('bg-primary text-white', content)
        self.assertNotIn('resumenSucursal', content)

    def test_editar_responde_200_con_nombre_de_sede(self) -> None:
        """Humo GET editar: 200 y el nombre de la sucursal en el encabezado."""
        user = User.objects.get(pk=self.usuario.pk)
        url = reverse('editar_sucursal', args=[self.sucursal.id])
        response = editar_sucursal(
            _request_con_usuario(self.factory, user, url),
            sucursal_id=self.sucursal.id,
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('form-sucursal-page', content)
        self.assertIn('Satélite', content)
        self.assertIn('Guardar cambios', content)

    def test_confirmar_eliminar_responde_200_sin_header_rojo(self) -> None:
        """Humo GET confirmar: 200 y ya no usa card-header bg-danger."""
        user = User.objects.get(pk=self.usuario.pk)
        url = reverse('eliminar_sucursal', args=[self.sucursal.id])
        response = eliminar_sucursal(
            _request_con_usuario(self.factory, user, url),
            sucursal_id=self.sucursal.id,
        )

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('form-sucursal-page', content)
        self.assertIn('Satélite', content)
        self.assertNotIn('bg-danger text-white', content)
