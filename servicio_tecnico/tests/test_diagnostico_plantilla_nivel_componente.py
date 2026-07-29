"""
Tests del selector de plantilla en envío de diagnóstico al cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El modal tiene 3 radios (estándar / nivel componente / validación).
La vista pasa tipo_plantilla a Celery según el radio (o el flag viejo
plantilla_nivel_componente=1 por compatibilidad).

No enviamos correo real: mockeamos .delay() (política de tests del proyecto).
También verificamos que las plantillas HTML renderizan el contenido esperado.
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
        Caso default: sin radio / sin flag → tipo_plantilla='estandar'.
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
        Compatibilidad: flag viejo plantilla_nivel_componente=1
        → tipo_plantilla='nivel_componente'.
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

    @patch('servicio_tecnico.tasks.enviar_diagnostico_cliente_task.delay')
    def test_tipo_plantilla_nivel_componente_por_radio(self, mock_delay):
        """
        Radio tipo_plantilla=nivel_componente → Celery recibe ese valor.
        """
        mock_delay.return_value = MagicMock(id='task-diag-nivel-radio')

        datos = self._datos_base()
        datos['tipo_plantilla'] = 'nivel_componente'

        response = self._post_enviar(datos)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode())
        self.assertTrue(payload['success'])
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs['tipo_plantilla'], 'nivel_componente')

    @patch('servicio_tecnico.tasks.enviar_diagnostico_cliente_task.delay')
    def test_tipo_plantilla_validacion(self, mock_delay):
        """
        Caso feliz: radio validación → tipo_plantilla='validacion'.
        """
        mock_delay.return_value = MagicMock(id='task-diag-validacion')

        datos = self._datos_base()
        datos['tipo_plantilla'] = 'validacion'

        response = self._post_enviar(datos)

        self.assertEqual(response.status_code, 200)
        payload = json.loads(response.content.decode())
        self.assertTrue(payload['success'])
        mock_delay.assert_called_once()
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs['tipo_plantilla'], 'validacion')
        self.assertEqual(kwargs['folio'], 'DX-PLANTILLA-001')

    @patch('servicio_tecnico.tasks.enviar_diagnostico_cliente_task.delay')
    def test_tipo_plantilla_invalido_cae_a_estandar(self, mock_delay):
        """
        Valor fuera de whitelist → se fuerza 'estandar' (seguro).
        """
        mock_delay.return_value = MagicMock(id='task-diag-invalido')

        datos = self._datos_base()
        datos['tipo_plantilla'] = 'plantilla_inventada'

        response = self._post_enviar(datos)

        self.assertEqual(response.status_code, 200)
        kwargs = mock_delay.call_args.kwargs
        self.assertEqual(kwargs['tipo_plantilla'], 'estandar')


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
        # Dominio del sitio corporativo en la plantilla (sicfix.mx)
        self.assertIn('https://sicfix.mx/reparacion-tarjeta-madre/', html)
        self.assertIn('REPARACIÓN A NIVEL COMPONENTE', html)
        self.assertIn('https://wa.me/525512345678', html)
        # No debe incluir diagrama.png (excluido a propósito)
        self.assertNotIn('diagrama', html.lower())


class PlantillaDiagnosticoValidacionRenderTest(TestCase):
    """
    Humo: la plantilla HTML de validación incluye garantía, horario y recolección.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Validación',
            ciudad='Naucalpan',
            estado_provincia='Estado de México',
            direccion='Circuito Economistas 15-A, Cd Satélite',
            horario_atencion='Lunes a Viernes de 09:00 a 17:30 hrs horario corrido.',
            telefono='5555555555',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Validación',
            cargo='Técnico',
            area='Laboratorio',
            email='validacion.tech@test.local',
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
            orden_cliente='OOW-VALID-01',
            tipo_equipo='Laptop',
            marca='Lenovo',
            modelo='ThinkPad',
            numero_serie='SN-VALID-01',
            email_cliente='validacion@test.local',
            nombre_cliente='Cliente Validación',
            falla_principal='Revisión / validación',
            diagnostico_sic='Equipo funcional tras revisión.',
            gama='media',
        )

    def _contexto_base(
        self,
        es_fuera_garantia: bool = True,
        es_sucursal_drop_off: bool = False,
    ) -> dict:
        """Contexto mínimo que Celery inyecta para plantilla validacion."""
        return {
            'orden': self.orden,
            'detalle': self.detalle,
            'folio': 'DX-VALID-001',
            'mensaje_personalizado': '',
            'fecha_envio_texto': '29/07/2026',
            'hora_envio_texto': '14:30',
            'cantidad_imagenes': 0,
            'componentes_seleccionados': [],
            'piezas_creadas': 0,
            'empresa_nombre': 'SIC MÉXICO',
            'pais_nombre': 'México',
            'email_empleado': 'tech@test.local',
            'nombre_empleado': 'Técnico Test',
            'whatsapp_empleado': '525512345678',
            'seguimiento_url': None,
            'nombre_cliente': 'Cliente Validación',
            'horario_atencion': self.sucursal.horario_atencion,
            'sucursal_nombre': self.sucursal.nombre,
            'sucursal_direccion': self.sucursal.direccion,
            'sucursal_ciudad_estado': 'Naucalpan, Estado de México',
            'sucursal_telefono': self.sucursal.telefono,
            'es_fuera_garantia': es_fuera_garantia,
            'es_sucursal_drop_off': es_sucursal_drop_off,
        }

    def test_plantilla_incluye_garantia_y_horario(self):
        """
        Render básico: garantía 1 semana, horario dinámico y texto de recolección.
        """
        html = render_to_string(
            'servicio_tecnico/emails/diagnostico_cliente_validacion.html',
            self._contexto_base(es_fuera_garantia=True),
        )

        # Normalizamos espacios/saltos de línea del HTML para asserts de copy
        html_plano = ' '.join(html.split())

        self.assertIn('DIAGNÓSTICO DE VALIDACIÓN', html_plano)
        self.assertIn('GARANTÍA DE VALIDACIÓN ES DE 1 SEMANA', html_plano)
        self.assertIn('no será necesario cotizar ningún componente', html_plano)
        self.assertIn(self.sucursal.horario_atencion, html_plano)
        self.assertIn('Circuito Economistas 15-A', html_plano)
        self.assertIn('listo para que pase a recolectar', html_plano)
        self.assertIn('CLÁUSULA 6', html_plano)
        self.assertNotIn('espere la notificación de equipo disponible', html_plano)

    def test_garantia_omite_nota_almacenaje(self):
        """
        Dentro de garantía: no debe mostrar la cláusula 6 de almacenaje.
        """
        html = render_to_string(
            'servicio_tecnico/emails/diagnostico_cliente_validacion.html',
            self._contexto_base(es_fuera_garantia=False),
        )

        self.assertIn('GARANTÍA DE VALIDACIÓN ES DE 1 SEMANA', html)
        self.assertNotIn('CLÁUSULA 6', html)
        self.assertNotIn('ALMACENAJE O DESTRUCCIÓN', html)

    def test_drop_off_pide_esperar_notificacion(self):
        """
        Drop Off: no invita a recolectar; pide esperar correo de equipo disponible.
        """
        html = render_to_string(
            'servicio_tecnico/emails/diagnostico_cliente_validacion.html',
            self._contexto_base(
                es_fuera_garantia=True,
                es_sucursal_drop_off=True,
            ),
        )
        html_plano = ' '.join(html.split())

        self.assertIn('GARANTÍA DE VALIDACIÓN ES DE 1 SEMANA', html_plano)
        self.assertIn('espere la notificación de equipo disponible', html_plano)
        # No debe aparecer el bloque de recolección inmediata
        self.assertNotIn('listo para que pase a recolectar', html_plano)
        self.assertNotIn('CLÁUSULA 6', html_plano)
        self.assertNotIn('Le recuerdo los horarios de atención', html_plano)
        self.assertNotIn('1 día hábil', html_plano)
