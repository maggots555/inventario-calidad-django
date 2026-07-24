"""
Tests del interruptor de plantilla en envío de diagnóstico al cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El modal tiene un switch «Reparación a nivel componente». Si está activo,
la vista pasa tipo_plantilla='nivel_componente' a Celery; si no, 'estandar'.

No enviamos correo real: mockeamos .delay() (política de tests del proyecto).
También verificamos que la plantilla HTML nueva renderiza FAQ e imágenes CID.
"""

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, OrdenServicio
from servicio_tecnico.views_envios_cliente import enviar_diagnostico_cliente


User = get_user_model()


class EnviarDiagnosticoPlantillaNivelComponenteTest(TestCase):
    """
    Verifica que enviar_diagnostico_cliente propague tipo_plantilla a Celery.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        """
        Crea sucursal, usuario con permiso y orden con diagnóstico listo para envío.
        """
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Diagnóstico Plantilla',
            ciudad='CDMX',
            direccion='Av. Test Diagnóstico 1',
            horario_atencion='Lun-Vie 9-18',
        )
        self.user = User.objects.create_user(
            username='user_diag_plantilla',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Usuario Diagnóstico Plantilla',
            cargo='Técnico',
            area='Laboratorio',
            email='diag.plantilla@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            numero_whatsapp='5512345678',
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
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-PLANTILLA-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude 5520',
            numero_serie='SN-PLANTILLA-01',
            email_cliente='cliente.diag@test.local',
            nombre_cliente='Cliente Diagnóstico',
            falla_principal='No enciende / daño en tarjeta madre',
            diagnostico_sic=(
                'Se identifica daño en tarjeta madre. '
                'Candidato a reparación a nivel componente.'
            ),
            gama='media',
        )

        self.url = reverse(
            'servicio_tecnico:enviar_diagnostico_cliente',
            args=[self.orden.pk],
        )

    def _post_enviar(self, data: dict):
        """
        Arma un POST autenticado hacia la vista (sin pasar por Axes/login).
        """
        request = self.factory.post(self.url, data=data)
        request.user = self.user
        return enviar_diagnostico_cliente(request, orden_id=self.orden.pk)

    def _datos_base(self) -> dict:
        """Datos mínimos válidos del formulario del modal."""
        return {
            'folio': 'DX-PLANTILLA-001',
            'componentes': '[]',
            'mensaje_personalizado': '',
        }

    @patch('servicio_tecnico.tasks.enviar_diagnostico_cliente_task.delay')
    def test_sin_flag_usa_plantilla_estandar(self, mock_delay):
        """
        Caso default: sin interruptor → tipo_plantilla='estandar'.
        """
        mock_delay.return_value = MagicMock(id='task-diag-estandar')

        response = self._post_enviar(self._datos_base())

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode())
        self.assertTrue(payload['success'])
        mock_delay.assert_called_once()
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs['tipo_plantilla'], 'estandar')
        self.assertEqual(kwargs['orden_id'], self.orden.pk)
        self.assertEqual(kwargs['folio'], 'DX-PLANTILLA-001')

    @patch('servicio_tecnico.tasks.enviar_diagnostico_cliente_task.delay')
    def test_flag_activo_usa_plantilla_nivel_componente(self, mock_delay):
        """
        Caso feliz: interruptor ON → tipo_plantilla='nivel_componente'.
        """
        mock_delay.return_value = MagicMock(id='task-diag-nivel')

        datos = self._datos_base()
        datos['plantilla_nivel_componente'] = '1'

        response = self._post_enviar(datos)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode())
        self.assertTrue(payload['success'])
        mock_delay.assert_called_once()
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs['tipo_plantilla'], 'nivel_componente')
        self.assertEqual(kwargs['folio'], 'DX-PLANTILLA-001')


class PlantillaDiagnosticoNivelComponenteRenderTest(TestCase):
    """
    Humo: la plantilla HTML de nivel componente incluye FAQ y CIDs esperados.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Render Plantilla',
            ciudad='CDMX',
            direccion='Av. Render 1',
            horario_atencion='Lun-Vie 9-18',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Render',
            cargo='Técnico',
            area='Laboratorio',
            email='render.tech@test.local',
            sucursal=self.sucursal,
            rol='tecnico',
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
        )
        self.detalle = DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-RENDER-01',
            tipo_equipo='Laptop',
            marca='HP',
            modelo='EliteBook',
            numero_serie='SN-RENDER-01',
            email_cliente='render@test.local',
            nombre_cliente='Cliente Render',
            falla_principal='Daño TM',
            diagnostico_sic='Diagnóstico de prueba',
            gama='media',
        )

    def test_plantilla_incluye_faq_y_cids_rhitso(self):
        """
        Render básico: FAQ, enlace Más información y cid de galería RHITSO.
        """
        html = render_to_string(
            'servicio_tecnico/emails/diagnostico_cliente_nivel_componente.html',
            {
                'orden': self.orden,
                'detalle': self.detalle,
                'folio': 'DX-RENDER-001',
                'mensaje_personalizado': '',
                'fecha_envio_texto': '24/07/2026',
                'hora_envio_texto': '12:00',
                'cantidad_imagenes': 0,
                'componentes_seleccionados': [],
                'piezas_creadas': 0,
                'empresa_nombre': 'SIC',
                'pais_nombre': 'México',
                'email_empleado': 'tech@test.local',
                'nombre_empleado': 'Técnico Test',
                'whatsapp_empleado': '525512345678',
                'seguimiento_url': None,
            },
        )

        self.assertIn('Preguntas frecuentes', html)
        self.assertIn('cid:rhitso_reballing', html)
        self.assertIn('https://sic.com.mx/reparacion-tarjeta-madre/', html)
        self.assertIn('REPARACIÓN A NIVEL COMPONENTE', html)
        self.assertIn('https://wa.me/525512345678', html)
        # No debe incluir diagrama.png (excluido a propósito)
        self.assertNotIn('diagrama', html.lower())
