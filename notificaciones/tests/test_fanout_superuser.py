"""
Tests: un superuser no debe ver N copias del mismo aviso de Compras.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
crear_notificacion, por default, clona a otros superusers (tareas Celery
de una sola persona). Si avisamos a 2 de Compras, ese clon por persona
hacía que el admin viera el mismo título dos veces.

Este archivo cubre:
1) El default Celery sigue clonando (una sola persona → admin ve 1 copia).
2) copiar_a_superusers=False no clona.
3) Broadcast a 2 Compras: superuser fuera de la lista ve 1, no 2.
4) Superuser que SÍ es Compras ve 1 (la suya), no 2.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from inventario.models import Empleado, Sucursal
from notificaciones.models import Notificacion
from notificaciones.utils import crear_notificacion, notificar_info

User = get_user_model()

TITULO_COMPRAS = 'Diagnóstico SIC disponible — cotizar piezas'
MENSAJE_COMPRAS = 'La orden SIC-TEST tiene Diagnóstico SIC.'
URL_ORDEN = '/servicio-tecnico/ordenes/1/'


class CrearNotificacionFanoutDefaultTest(TestCase):
    """El default (tareas Celery) sigue avisando a otros superusers."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.tecnico = User.objects.create_user(
            username='tec_fanout',
            password='testpass123',
        )
        self.admin = User.objects.create_user(
            username='admin_fanout',
            password='testpass123',
            is_superuser=True,
            is_staff=True,
        )

    def test_default_clona_a_otro_superuser(self):
        """Una tarea de una persona: el admin recibe 1 copia (no se pierde)."""
        creadas = crear_notificacion(
            titulo='Correo RHITSO enviado',
            mensaje='Se envió el PDF',
            usuario=self.tecnico,
            app_origen='servicio_tecnico',
        )
        self.assertEqual(len(creadas), 2)
        self.assertEqual(
            Notificacion.objects.filter(
                usuario=self.admin,
                titulo='Correo RHITSO enviado',
            ).count(),
            1,
        )

    def test_flag_false_no_clona(self):
        """Broadcast: el caller desactiva el clon por destinatario."""
        crear_notificacion(
            titulo='Aviso interno',
            mensaje='Solo el técnico',
            usuario=self.tecnico,
            copiar_a_superusers=False,
        )
        self.assertEqual(
            Notificacion.objects.filter(usuario=self.admin).count(),
            0,
        )
        self.assertEqual(
            Notificacion.objects.filter(usuario=self.tecnico).count(),
            1,
        )

    def test_superuser_destinatario_no_se_auto_duplica(self):
        """Si el destinatario ya es admin, no se le crea una segunda fila."""
        crear_notificacion(
            titulo='Tarea propia',
            mensaje='El admin disparó esto',
            usuario=self.admin,
        )
        self.assertEqual(
            Notificacion.objects.filter(
                usuario=self.admin,
                titulo='Tarea propia',
            ).count(),
            1,
        )


class EnviarPushCampanitaSinClonesDoblesTest(TestCase):
    """2 de Compras + superuser = 1 fila en la campanita del admin."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Fanout',
            ciudad='CDMX',
        )
        self.user_compras_a = User.objects.create_user(
            username='compras_a',
            password='testpass123',
        )
        self.user_compras_b = User.objects.create_user(
            username='compras_b',
            password='testpass123',
        )
        self.emp_a = self._empleado(
            'Compras A',
            'compras.a@test.local',
            self.user_compras_a,
        )
        self.emp_b = self._empleado(
            'Compras B',
            'compras.b@test.local',
            self.user_compras_b,
        )

    def _empleado(self, nombre, email, user, rol='compras'):
        return Empleado.objects.create(
            nombre_completo=nombre,
            cargo='Compras',
            area='Compras',
            email=email,
            sucursal=self.sucursal,
            user=user,
            rol=rol,
            activo=True,
        )

    def _avisar(self, empleados):
        from almacen.utils.notificar_respuesta_cotizacion import (
            enviar_push_y_campanita,
        )

        return enviar_push_y_campanita(
            empleados,
            titulo=TITULO_COMPRAS,
            mensaje=MENSAJE_COMPRAS,
            url=URL_ORDEN,
            app_origen='servicio_tecnico',
        )

    def _count(self, user):
        return Notificacion.objects.filter(
            usuario=user,
            titulo=TITULO_COMPRAS,
        ).count()

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_superuser_fuera_de_lista_ve_una_copia(self, _mock_push):
        """Admin que NO es Compras ve 1 aviso, no uno por cada comprador."""
        admin = User.objects.create_user(
            username='admin_solo',
            password='testpass123',
            is_superuser=True,
            is_staff=True,
        )
        enviados = self._avisar([self.emp_a, self.emp_b])
        self.assertEqual(enviados, 2)
        self.assertEqual(self._count(self.user_compras_a), 1)
        self.assertEqual(self._count(self.user_compras_b), 1)
        self.assertEqual(self._count(admin), 1)

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_superuser_que_es_compras_ve_una_sola(self, _mock_push):
        """El caso del usuario: admin + rol Compras no recibe clon del compañero."""
        self.user_compras_a.is_superuser = True
        self.user_compras_a.is_staff = True
        self.user_compras_a.save(update_fields=['is_superuser', 'is_staff'])

        enviados = self._avisar([self.emp_a, self.emp_b])
        self.assertEqual(enviados, 2)
        self.assertEqual(self._count(self.user_compras_a), 1)
        self.assertEqual(self._count(self.user_compras_b), 1)

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_mismo_user_dos_veces_en_lista_una_fila(self, _mock_push):
        """Dos filas Empleado / el mismo user no duplican campanita."""
        enviados = self._avisar([self.emp_a, self.emp_a])
        self.assertEqual(enviados, 1)
        self.assertEqual(self._count(self.user_compras_a), 1)

    @patch('notificaciones.push_service.enviar_push_a_usuario', return_value=True)
    def test_notificar_info_kwarg_llega_al_crear(self, _mock_push):
        """El atajo notificar_info respeta copiar_a_superusers=False."""
        admin = User.objects.create_user(
            username='admin_info',
            password='testpass123',
            is_superuser=True,
        )
        notificar_info(
            'Solo destinatario',
            'Sin clon',
            usuario=self.user_compras_a,
            copiar_a_superusers=False,
        )
        self.assertEqual(
            Notificacion.objects.filter(usuario=admin).count(),
            0,
        )
        self.assertEqual(
            Notificacion.objects.filter(usuario=self.user_compras_a).count(),
            1,
        )
