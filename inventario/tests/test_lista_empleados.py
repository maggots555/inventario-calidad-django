"""
Tests de la lista administrativa de empleados (híbrido + panel lateral).

EXPLICACIÓN PARA PRINCIPIANTES:
Usamos RequestFactory (no Client) para evitar el middleware multi-tenant
(PaisMiddleware) que enruta queries a la BD 'mexico' mientras setUp escribe
en 'default'. Es el mismo patrón que notificaciones/tests y formatos OOW.
"""

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventario.models import Empleado
from inventario.views import lista_empleados


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
    # login_required y templates pueden tocar sesión / messages
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
class ListaEmpleadosTests(TestCase):
    """
    Objetivo: verificar humo, permisos de UI y filtro acceso_sistema=pendiente.

    Efectos secundarios: crea usuarios y empleados de prueba en BD de test.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Crea factory, permiso view_empleado y empleados con distintos estados."""
        self.factory = RequestFactory()

        ct = ContentType.objects.get_for_model(Empleado)
        self.perm_view = Permission.objects.get(
            content_type=ct,
            codename='view_empleado',
        )

        self.usuario_lectura = User.objects.create_user(
            username='lector_emp',
            password='testpass123',
        )
        self.usuario_lectura.user_permissions.add(self.perm_view)

        self.usuario_staff = User.objects.create_user(
            username='admin_emp',
            password='testpass123',
            is_staff=True,
        )
        self.usuario_staff.user_permissions.add(self.perm_view)

        self.emp_sin_acceso = Empleado.objects.create(
            nombre_completo='Ana Sin Acceso',
            cargo='Técnico',
            area='Laboratorio',
            email='ana@example.com',
            activo=True,
        )

        user_pendiente = User.objects.create_user(
            username='pendiente_user',
            password='temp12345',
            email='pedro@example.com',
            is_active=True,
        )
        self.emp_pendiente = Empleado.objects.create(
            nombre_completo='Pedro Pendiente',
            cargo='Inspector',
            area='Calidad',
            email='pedro@example.com',
            activo=True,
            user=user_pendiente,
            contraseña_configurada=False,
            tiene_acceso_sistema=True,
        )

        user_activo = User.objects.create_user(
            username='activo_user',
            password='temp12345',
            email='lucia@example.com',
            is_active=True,
        )
        self.emp_activo = Empleado.objects.create(
            nombre_completo='Lucía Activa',
            cargo='Recepcionista',
            area='Recepción',
            email='lucia@example.com',
            activo=True,
            user=user_activo,
            contraseña_configurada=True,
            tiene_acceso_sistema=True,
        )

        self.url = reverse('lista_empleados')

    def test_lista_responde_200_y_marca_layout_nuevo(self) -> None:
        """Humo: status 200 y aparecen marcas del rediseño (page + panel)."""
        # Recargar usuario para que el caché de permisos vea view_empleado
        user = User.objects.get(pk=self.usuario_lectura.pk)
        request = _request_con_usuario(self.factory, user, self.url)
        response = lista_empleados(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('lista-empleados-page', content)
        self.assertIn('panelEmpleado', content)
        self.assertIn('Ana Sin Acceso', content)
        # Columna / etiqueta de rol (default del modelo: Técnico)
        self.assertIn('Rol en el sistema', content)
        self.assertIn('Técnico', content)

    def test_staff_ve_cta_agregar_y_no_staff_modo_lectura(self) -> None:
        """Staff ve 'Agregar empleado'; lector ve 'Modo solo lectura'."""
        staff = User.objects.get(pk=self.usuario_staff.pk)
        resp_staff = lista_empleados(
            _request_con_usuario(self.factory, staff, self.url)
        )
        html_staff = resp_staff.content.decode()
        self.assertIn('Agregar empleado', html_staff)
        self.assertNotIn('Modo solo lectura', html_staff)

        lector = User.objects.get(pk=self.usuario_lectura.pk)
        resp_lectura = lista_empleados(
            _request_con_usuario(self.factory, lector, self.url)
        )
        html_lectura = resp_lectura.content.decode()
        self.assertIn('Modo solo lectura', html_lectura)
        self.assertNotIn('Agregar empleado', html_lectura)

    def test_filtro_acceso_pendiente(self) -> None:
        """Caso feliz: solo aparecen empleados pendientes de activación."""
        user = User.objects.get(pk=self.usuario_lectura.pk)
        request = _request_con_usuario(
            self.factory,
            user,
            self.url,
            data={'acceso_sistema': 'pendiente'},
        )
        response = lista_empleados(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('Pedro Pendiente', content)
        self.assertNotIn('Ana Sin Acceso', content)
        self.assertNotIn('Lucía Activa', content)
        # Chip de pendientes muestra 1 (aparece en resumen y en contador)
        self.assertIn('<strong>1</strong>', content)

    def test_filtro_acceso_pendiente_vacio_borde(self) -> None:
        """Borde: si no hay pendientes, empty state / lista vacía."""
        self.emp_pendiente.contraseña_configurada = True
        self.emp_pendiente.save(update_fields=['contraseña_configurada'])

        user = User.objects.get(pk=self.usuario_lectura.pk)
        request = _request_con_usuario(
            self.factory,
            user,
            self.url,
            data={'acceso_sistema': 'pendiente'},
        )
        response = lista_empleados(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn('No se encontraron empleados', content)
        self.assertNotIn('Pedro Pendiente', content)

    def test_get_estado_acceso_codigo(self) -> None:
        """Helper del modelo devuelve códigos estables para la UI."""
        self.assertEqual(self.emp_sin_acceso.get_estado_acceso_codigo(), 'sin_acceso')
        self.assertEqual(self.emp_pendiente.get_estado_acceso_codigo(), 'pendiente')
        self.assertEqual(self.emp_activo.get_estado_acceso_codigo(), 'activo')
