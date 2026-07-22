"""
Tests de humo: panel Offcanvas de carga de técnicos en lista de órdenes.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No abrimos el navegador. Solo pedimos el HTML de las vistas y comprobamos
que en "activas" aparecen la franja y el panel (#panelCargaTecnicos), y que
en "finalizadas" NO aparecen (mostrar_estadisticas=False).

Usamos RequestFactory (no Client) para evitar el middleware multi-tenant
que enruta a otra BD mientras setUp escribe en 'default'.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import OrdenServicio
from servicio_tecnico.views_ordenes import (
    lista_ordenes_activas,
    lista_ordenes_finalizadas,
)


User = get_user_model()


def _request_con_usuario(factory: RequestFactory, user, path: str):
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
            # Evita exigir manifest de collectstatic para CSS/JS nuevos
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class ListaOrdenesCargaPanelTests(TestCase):
    """
    Objetivo: verificar que el panel de carga solo sale en órdenes activas.

    Efectos secundarios: crea usuario, permiso, sucursal y empleado de prueba.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Crea factory, permiso view_ordenservicio y datos mínimos."""
        self.factory = RequestFactory()

        ct = ContentType.objects.get_for_model(OrdenServicio)
        perm = Permission.objects.get(
            content_type=ct,
            codename='view_ordenservicio',
        )

        self.usuario = User.objects.create_user(
            username='lector_carga_st',
            password='testpass123',
        )
        self.usuario.user_permissions.add(perm)

        # Sucursal + técnico: la vista arma tecnicos_por_sucursal con empleados
        # activos de áreas de laboratorio (si el filtro de la vista los incluye).
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Test Carga Panel',
            ciudad='CDMX',
        )
        # La vista solo lista empleados con este cargo exacto
        self.tecnico = Empleado.objects.create(
            nombre_completo='Técnico Panel Carga',
            cargo='TECNICO DE LABORATORIO',
            area='Laboratorio OOW',
            sucursal=self.sucursal,
            activo=True,
        )

        self.url_activas = reverse('servicio_tecnico:lista_activas')
        self.url_finalizadas = reverse('servicio_tecnico:lista_finalizadas')

    def test_activas_incluye_panel_y_franja(self) -> None:
        """
        Humo activas: status 200 y marcas del panel Offcanvas + franja.
        """
        user = User.objects.get(pk=self.usuario.pk)
        request = _request_con_usuario(self.factory, user, self.url_activas)
        response = lista_ordenes_activas(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        # Franja compacta + Offcanvas (ids del plan)
        self.assertIn('cargaTecnicosStrip', content)
        self.assertIn('panelCargaTecnicos', content)
        self.assertIn('Ver carga completa', content)
        self.assertIn('lo-carga-offcanvas', content)
        # CSS / JS del feature
        self.assertIn('lista_ordenes_carga.css', content)
        self.assertIn('lista_ordenes_carga.js', content)
        # Sucursales colapsables (Satélite abierto por defecto vía collapse show)
        self.assertIn('lo-carga-sucursal-toggle', content)
        self.assertIn('collapseSucursal', content)

    def test_finalizadas_no_incluye_panel(self) -> None:
        """
        Humo finalizadas: status 200 y SIN panel de carga (mostrar_estadisticas=False).
        """
        user = User.objects.get(pk=self.usuario.pk)
        request = _request_con_usuario(
            self.factory, user, self.url_finalizadas
        )
        response = lista_ordenes_finalizadas(request)

        self.assertEqual(response.status_code, 200)
        content = response.content.decode()

        self.assertNotIn('panelCargaTecnicos', content)
        self.assertNotIn('cargaTecnicosStrip', content)
        self.assertNotIn('lista_ordenes_carga.css', content)
