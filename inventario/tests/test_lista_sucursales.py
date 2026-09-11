"""
Tests de la lista administrativa de sucursales (chips + filtros).

EXPLICACIÓN PARA PRINCIPIANTES:
Usamos RequestFactory (no Client) para evitar el middleware multi-tenant
(PaisMiddleware) que enruta queries a la BD 'mexico' mientras setUp escribe
en 'default'. Es el mismo patrón que test_lista_empleados.
"""

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventario.models import Sucursal
from inventario.views import lista_sucursales


def _request_con_usuario(factory: RequestFactory, user: User, path: str, data=None):
    """
    Arma un request GET listo para llamar la vista (sesión + messages).

    Args:
        factory: RequestFactory de Django
        user: usuario autenticado
        path: ruta URL (puede incluir query string)
        data: dict opcional de query params

    Returns:
        HttpRequest con user, session y messages.
    """
    request = factory.get(path, data=data or {})
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
class ListaSucursalesTests(TestCase):
    """
    Objetivo: verificar humo del rediseño, filtro por estado y contadores.

    Efectos secundarios: crea usuario, permiso y sucursales de prueba en BD.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Crea factory, permiso view_sucursal y sucursales con distintos estados."""
        self.factory = RequestFactory()

        ct = ContentType.objects.get_for_model(Sucursal)
        self.perm_view = Permission.objects.get(
            content_type=ct,
            codename='view_sucursal',
        )

        self.usuario_lectura = User.objects.create_user(
            username='lector_suc',
            password='testpass123',
        )
        self.usuario_lectura.user_permissions.add(self.perm_view)

        self.suc_activa = Sucursal.objects.create(
            codigo='SUC001',
            nombre='Satélite',
            ciudad='Naucalpan',
            responsable='Ana Encargada',
            activa=True,
        )
        self.suc_inactiva = Sucursal.objects.create(
            codigo='SUC002',
            nombre='Guadalajara Centro',
            ciudad='Guadalajara',
            responsable='',
            activa=False,
        )
        self.suc_sin_encargado = Sucursal.objects.create(
            codigo='SUC003',
            nombre='Monterrey Norte',
            ciudad='Monterrey',
            responsable='',
            activa=True,
        )

        self.url = reverse('lista_sucursales')

    def test_lista_responde_200_y_marca_layout_nuevo(self) -> None:
        """Humo: status 200 y aparecen marcas del rediseño (page + CSS/JS)."""
        user = User.objects.get(pk=self.usuario_lectura.pk)
        request = _request_con_usuario(self.factory, user, self.url)
        response = lista_sucursales(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('lista-sucursales-page', content)
        self.assertIn('css/lista_sucursales.css', content)
        self.assertIn('js/lista_sucursales.js', content)
        self.assertIn('Satélite', content)
        self.assertIn('Guadalajara Centro', content)
        self.assertNotIn('bg-primary text-white', content)

    def test_filtro_estado_activa(self) -> None:
        """Caso feliz: estado=activa oculta la sucursal inactiva."""
        user = User.objects.get(pk=self.usuario_lectura.pk)
        request = _request_con_usuario(
            self.factory,
            user,
            self.url,
            data={'estado': 'activa'},
        )
        response = lista_sucursales(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Satélite', content)
        self.assertIn('Monterrey Norte', content)
        self.assertNotIn('Guadalajara Centro', content)

    def test_contadores_coherentes_con_el_catalogo(self) -> None:
        """Los chips muestran total/activas/inactivas/con encargado correctos."""
        user = User.objects.get(pk=self.usuario_lectura.pk)
        request = _request_con_usuario(self.factory, user, self.url)
        response = lista_sucursales(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        # render() de Django entrega HttpResponse (HTML ya pintado), no context_data.
        self.assertRegex(content, r'Total\s*<span class="ls-chip-count">3</span>')
        self.assertRegex(content, r'Activas\s*<span class="ls-chip-count">2</span>')
        self.assertRegex(content, r'Inactivas\s*<span class="ls-chip-count">1</span>')
        self.assertRegex(
            content,
            r'Con encargado\s*<span class="ls-chip-count">1</span>',
        )

    def test_filtro_con_encargado_vacio_borde(self) -> None:
        """Borde: si nadie tiene encargado, empty state al filtrar ese chip."""
        self.suc_activa.responsable = ''
        self.suc_activa.save(update_fields=['responsable'])

        user = User.objects.get(pk=self.usuario_lectura.pk)
        request = _request_con_usuario(
            self.factory,
            user,
            self.url,
            data={'con_encargado': '1'},
        )
        response = lista_sucursales(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('No se encontraron sucursales', content)
        self.assertNotIn('Satélite', content)
