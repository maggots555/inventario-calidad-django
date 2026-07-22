"""
Tests del asunto editable en el envío de correo RHITSO.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El modal permite editar el asunto. La vista debe pasarlo a Celery con .delay().
Si llega vacío, reconstruye el default: 🔧ENVIO DE EQUIPO RHITSO - {orden_cliente}.

No enviamos correo real: mockeamos .delay() (política de tests del proyecto).
Usamos RequestFactory (no client.login) para evitar conflicto con Django-Axes.
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory, TestCase
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, OrdenServicio
from servicio_tecnico.views_rhitso import enviar_correo_rhitso


User = get_user_model()


class EnviarCorreoRhitsoAsuntoTest(TestCase):
    """
    Verifica que enviar_correo_rhitso propague asunto_correo a Celery.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        """
        Crea sucursal, usuario con permiso, orden candidata RHITSO y detalle.
        """
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Asunto RHITSO',
            ciudad='CDMX',
            direccion='Av. Test 1',
            horario_atencion='Lun-Vie 9-18',
        )
        self.user = User.objects.create_user(
            username='user_asunto_rhitso',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Usuario Asunto RHITSO',
            cargo='Técnico',
            area='Laboratorio',
            email='asunto.rhitso@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        perm = Permission.objects.get(
            content_type=ct,
            codename='view_ordenservicio',
        )
        self.user.user_permissions.add(perm)

        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            es_candidato_rhitso=True,
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-09647',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Inspiron 15 3535',
            numero_serie='SN-ASUNTO-01',
            email_cliente='cliente@test.local',
            nombre_cliente='Cliente Test',
            falla_principal='No enciende',
            gama='media',
        )

        self.url = reverse(
            'servicio_tecnico:enviar_correo_rhitso',
            args=[self.orden.pk],
        )

    def _post_enviar(self, data: dict):
        """
        Arma un POST autenticado hacia la vista (sin pasar por Axes/login).
        """
        request = self.factory.post(self.url, data=data)
        request.user = self.user
        return enviar_correo_rhitso(request, orden_id=self.orden.pk)

    @patch('servicio_tecnico.tasks.enviar_correo_rhitso_task.delay')
    def test_pasa_asunto_personalizado_a_celery(self, mock_delay):
        """
        Caso feliz: el asunto editado en el modal llega intacto a .delay().
        """
        mock_delay.return_value = MagicMock(id='task-asunto-custom')
        asunto_custom = 'ASUNTO PERSONALIZADO RHITSO OOW-09647'

        response = self._post_enviar(
            {
                'destinatarios_principales': ['lab@rhitso.test'],
                'asunto_correo': asunto_custom,
            }
        )

        self.assertEqual(response.status_code, 200)
        # JsonResponse de la vista (no Client): parseamos content a mano.
        payload = json.loads(response.content.decode())
        self.assertTrue(payload['success'])
        mock_delay.assert_called_once()
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs['asunto_correo'], asunto_custom)
        self.assertEqual(kwargs['orden_id'], self.orden.pk)

    @patch('servicio_tecnico.tasks.enviar_correo_rhitso_task.delay')
    def test_asunto_vacio_usa_default_con_orden_cliente(self, mock_delay):
        """
        Caso borde: si el asunto llega vacío, la vista arma el default histórico.
        """
        mock_delay.return_value = MagicMock(id='task-asunto-default')

        response = self._post_enviar(
            {
                'destinatarios_principales': ['lab@rhitso.test'],
                'asunto_correo': '   ',
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode())
        self.assertTrue(payload['success'])
        mock_delay.assert_called_once()
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(
            kwargs['asunto_correo'],
            '🔧ENVIO DE EQUIPO RHITSO - OOW-09647',
        )
