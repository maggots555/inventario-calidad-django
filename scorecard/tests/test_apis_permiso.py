"""
Tests de permiso en las APIs JSON de Scorecard.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El formulario de incidencias pide datos de empleado y reincidencias
con ``fetch``. Esas URLs antes solo exigían estar logueado: un técnico
sin Scorecard podía leer emails de colegas. Ahora piden
``scorecard.view_incidencia``, igual que las listas HTML.

Usamos RequestFactory (no el Client HTTP) para no pelear con el
middleware de país / cambio de contraseña: llamamos la vista directo.
"""

import json

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from scorecard.models import Incidencia
from scorecard.views import api_buscar_reincidencias, api_empleado_data

User = get_user_model()


class ApisScorecardPermisoTest(TestCase):
    """Un técnico sin permiso de Scorecard no lee PII ni reincidencias."""

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal API Scorecard',
            ciudad='CDMX',
        )
        self.user_tecnico = User.objects.create_user(
            username='tecnico_api_sc',
            password='testpass123',
        )
        self.user_calidad = User.objects.create_user(
            username='calidad_api_sc',
            password='testpass123',
        )
        perm = Permission.objects.get(
            content_type=ContentType.objects.get_for_model(Incidencia),
            codename='view_incidencia',
        )
        self.user_calidad.user_permissions.add(perm)

        self.empleado = Empleado.objects.create(
            user=self.user_tecnico,
            nombre_completo='Técnico API',
            cargo='Técnico',
            area='Laboratorio',
            email='tecnico.api@test.local',
            sucursal=self.sucursal,
            rol='tecnico',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )
        self.url_empleado = reverse(
            'scorecard:api_empleado_data',
            kwargs={'empleado_id': self.empleado.pk},
        )
        self.url_reincidencias = reverse('scorecard:api_buscar_reincidencias')

    def _get(self, user, url, view, **kwargs):
        """Arma un GET autenticado y llama la vista (sin middleware extra)."""
        request = self.factory.get(url, kwargs.pop('query', None) or {})
        request.user = user
        return view(request, **kwargs)

    def test_tecnico_sin_permiso_no_lee_email_de_empleado(self) -> None:
        """Borde: login no basta; debe redirigir a acceso denegado."""
        respuesta = self._get(
            self.user_tecnico,
            self.url_empleado,
            api_empleado_data,
            empleado_id=self.empleado.pk,
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('acceso-denegado', respuesta['Location'])

    def test_calidad_con_permiso_recibe_json_del_empleado(self) -> None:
        """Feliz: quien ve incidencias sí puede autocompletar el formulario."""
        respuesta = self._get(
            self.user_calidad,
            self.url_empleado,
            api_empleado_data,
            empleado_id=self.empleado.pk,
        )
        self.assertEqual(respuesta.status_code, 200)
        data = json.loads(respuesta.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['empleado']['email'], 'tecnico.api@test.local')

    def test_tecnico_sin_permiso_no_busca_reincidencias(self) -> None:
        respuesta = self._get(
            self.user_tecnico,
            self.url_reincidencias,
            api_buscar_reincidencias,
            query={'numero_serie': 'ABC123'},
        )
        self.assertEqual(respuesta.status_code, 302)
        self.assertIn('acceso-denegado', respuesta['Location'])

    def test_calidad_con_permiso_consulta_reincidencias(self) -> None:
        respuesta = self._get(
            self.user_calidad,
            self.url_reincidencias,
            api_buscar_reincidencias,
            query={'numero_serie': 'ABC123'},
        )
        self.assertEqual(respuesta.status_code, 200)
        data = json.loads(respuesta.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['count'], 0)
