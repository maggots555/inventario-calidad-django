"""
Tests de humo tras extraer APIs de búsqueda y vistas misc de views.py (Fase 1).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No hacemos búsquedas reales contra un catálogo grande. Solo confirmamos que:
1) urls.py sigue resolviendo a los callables nuevos.
2) views.py reexporta los mismos nombres.
3) El autocomplete con q corto (< 2 caracteres) responde JSON vacío.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import resolve, reverse

from servicio_tecnico import views as st_views
from servicio_tecnico import views_apis_busqueda
from servicio_tecnico import views_misc
from servicio_tecnico.models import OrdenServicio
from servicio_tecnico.views_apis_busqueda import api_buscar_ordenes_autocomplete


User = get_user_model()


class CompatibilidadApisMiscReexportsTest(SimpleTestCase):
    """
    Verifica reexports y resolve de URLs sin tocar BD.

    Objetivo: si alguien borra un import por error, urls.py dejaría de ver
    views.api_buscar_* / views.acceso_denegado.
    """

    def test_views_reexporta_apis_y_misc(self):
        """Los símbolos públicos siguen en el módulo views."""
        self.assertIs(
            st_views.api_buscar_ordenes_autocomplete,
            views_apis_busqueda.api_buscar_ordenes_autocomplete,
        )
        self.assertIs(
            st_views.api_buscar_ordenes_reingreso,
            views_apis_busqueda.api_buscar_ordenes_reingreso,
        )
        self.assertIs(
            st_views.api_buscar_orden_por_serie,
            views_apis_busqueda.api_buscar_orden_por_serie,
        )
        self.assertIs(
            st_views.api_buscar_modelos_por_marca,
            views_apis_busqueda.api_buscar_modelos_por_marca,
        )
        self.assertIs(st_views.acceso_denegado, views_misc.acceso_denegado)
        self.assertIs(
            st_views.actualizar_email_cliente,
            views_misc.actualizar_email_cliente,
        )

    def test_urls_apis_y_misc_resuelven_modulos_nuevos(self):
        """reverse/resolve apuntan a views_apis_busqueda y views_misc."""
        casos = [
            (
                'servicio_tecnico:api_buscar_ordenes_autocomplete',
                None,
                views_apis_busqueda.api_buscar_ordenes_autocomplete,
            ),
            (
                'servicio_tecnico:api_buscar_ordenes_reingreso',
                None,
                views_apis_busqueda.api_buscar_ordenes_reingreso,
            ),
            (
                'servicio_tecnico:api_buscar_orden_por_serie',
                None,
                views_apis_busqueda.api_buscar_orden_por_serie,
            ),
            (
                'servicio_tecnico:api_buscar_modelos_por_marca',
                None,
                views_apis_busqueda.api_buscar_modelos_por_marca,
            ),
            (
                'servicio_tecnico:acceso_denegado_servicio_tecnico',
                None,
                views_misc.acceso_denegado,
            ),
            (
                'servicio_tecnico:actualizar_email_cliente',
                {'detalle_id': 1},
                views_misc.actualizar_email_cliente,
            ),
        ]
        for name, kwargs, expected in casos:
            url = reverse(name, kwargs=kwargs) if kwargs else reverse(name)
            match = resolve(url)
            self.assertIs(match.func, expected, msg=f'Fallo en {name}')


class AutocompleteSmokeTest(TestCase):
    """
    Smoke del autocomplete: q de 1 carácter debe devolver resultados vacíos.

    Efectos secundarios: crea User + Permission en la BD de pruebas.
    """

    def setUp(self):
        """
        Crea un usuario con permiso view_ordenservicio (el decorador lo exige).

        Args:
            (ninguno — setUp de Django TestCase)

        Efectos secundarios:
            Inserta User y Permission en la BD de pruebas.
        """
        self.user = User.objects.create_user(
            username='test_autocomplete',
            password='testpass123',
        )
        # Paso 1: obtener el permiso que pide la API de autocomplete
        ct = ContentType.objects.get_for_model(OrdenServicio)
        permiso = Permission.objects.get(
            content_type=ct,
            codename='view_ordenservicio',
        )
        # Paso 2: asignar el permiso al usuario de prueba
        self.user.user_permissions.add(permiso)
        self.factory = RequestFactory()

    def test_autocomplete_q_corto_devuelve_lista_vacia(self):
        """
        Con q='a' (1 carácter) la API responde {"resultados": []} sin consultar BD.

        EXPLICACIÓN PARA PRINCIPIANTES:
        La vista exige mínimo 2 caracteres. Si el usuario escribe solo uno,
        devolvemos vacío de inmediato (ahorra consultas y evita ruido).
        """
        # Paso 1: armar petición GET como haría el typeahead del frontend
        request = self.factory.get(
            '/servicio-tecnico/api/buscar-ordenes-autocomplete/',
            {'q': 'a'},
        )
        request.user = self.user

        # Paso 2: llamar la vista directa (sin pasar por el middleware completo)
        response = api_buscar_ordenes_autocomplete(request)

        # Paso 3: validar JSON vacío
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data, {'resultados': []})
