"""
Tests de humo tras extraer RHITSO por orden + envíos al cliente (Fase 7).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No enviamos correos ni generamos PDFs reales. Solo confirmamos que:
1) urls.py resuelve cada ruta al módulo nuevo.
2) views.py reexporta las mismas funciones (compatibilidad).
3) Los cuerpos viven en views_rhitso / views_envios_cliente (no en el monolito).
4) Imports críticos existen (regresión NameError de fases anteriores).
"""

from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse

from servicio_tecnico import views as st_views
from servicio_tecnico import views_envios_cliente
from servicio_tecnico import views_rhitso


class CompatibilidadRhitsoEnviosReexportsTest(SimpleTestCase):
    """Reexports + resolve sin tocar BD."""

    def test_views_reexporta_rhitso(self):
        """Funciones RHITSO por orden siguen disponibles en servicio_tecnico.views."""
        pares = [
            ('gestion_rhitso', views_rhitso.gestion_rhitso),
            ('actualizar_estado_rhitso', views_rhitso.actualizar_estado_rhitso),
            ('registrar_incidencia', views_rhitso.registrar_incidencia),
            ('resolver_incidencia', views_rhitso.resolver_incidencia),
            ('editar_diagnostico_sic', views_rhitso.editar_diagnostico_sic),
            ('agregar_comentario_rhitso', views_rhitso.agregar_comentario_rhitso),
            ('enviar_correo_rhitso', views_rhitso.enviar_correo_rhitso),
            ('generar_pdf_rhitso_prueba', views_rhitso.generar_pdf_rhitso_prueba),
        ]
        for attr, expected in pares:
            with self.subTest(attr=attr):
                self.assertIs(getattr(st_views, attr), expected)

    def test_views_reexporta_envios(self):
        """Envíos al cliente siguen disponibles vía views."""
        pares = [
            ('confirmar_envio_feedback', views_envios_cliente.confirmar_envio_feedback),
            (
                'confirmar_envio_vigencia_vencida',
                views_envios_cliente.confirmar_envio_vigencia_vencida,
            ),
            ('enviar_imagenes_cliente', views_envios_cliente.enviar_imagenes_cliente),
            (
                'enviar_imagenes_egreso_cliente',
                views_envios_cliente.enviar_imagenes_egreso_cliente,
            ),
            (
                'enviar_rewind_egreso_cliente',
                views_envios_cliente.enviar_rewind_egreso_cliente,
            ),
            ('enviar_evidencia_video', views_envios_cliente.enviar_evidencia_video),
            (
                'obtener_destinatarios_egreso',
                views_envios_cliente.obtener_destinatarios_egreso,
            ),
            (
                'enviar_diagnostico_cliente',
                views_envios_cliente.enviar_diagnostico_cliente,
            ),
            ('preview_pdf_diagnostico', views_envios_cliente.preview_pdf_diagnostico),
            (
                'notificar_equipo_disponible',
                views_envios_cliente.notificar_equipo_disponible,
            ),
        ]
        for attr, expected in pares:
            with self.subTest(attr=attr):
                self.assertIs(getattr(st_views, attr), expected)

    def test_modulos_correctos(self):
        """__module__ apunta a los hermanos nuevos, no al monolito."""
        self.assertEqual(
            st_views.gestion_rhitso.__module__,
            'servicio_tecnico.views_rhitso',
        )
        self.assertEqual(
            st_views.enviar_diagnostico_cliente.__module__,
            'servicio_tecnico.views_envios_cliente',
        )
        self.assertEqual(
            st_views.confirmar_envio_feedback.__module__,
            'servicio_tecnico.views_envios_cliente',
        )

    def test_urls_rhitso_resuelven_modulo_nuevo(self):
        """reverse/resolve RHITSO → views_rhitso."""
        casos = [
            (
                'servicio_tecnico:gestion_rhitso',
                {'orden_id': 1},
                views_rhitso.gestion_rhitso,
            ),
            (
                'servicio_tecnico:actualizar_estado_rhitso',
                {'orden_id': 1},
                views_rhitso.actualizar_estado_rhitso,
            ),
            (
                'servicio_tecnico:registrar_incidencia',
                {'orden_id': 1},
                views_rhitso.registrar_incidencia,
            ),
            (
                'servicio_tecnico:resolver_incidencia',
                {'incidencia_id': 1},
                views_rhitso.resolver_incidencia,
            ),
            (
                'servicio_tecnico:editar_diagnostico_sic',
                {'orden_id': 1},
                views_rhitso.editar_diagnostico_sic,
            ),
            (
                'servicio_tecnico:agregar_comentario_rhitso',
                {'orden_id': 1},
                views_rhitso.agregar_comentario_rhitso,
            ),
            (
                'servicio_tecnico:enviar_correo_rhitso',
                {'orden_id': 1},
                views_rhitso.enviar_correo_rhitso,
            ),
            (
                'servicio_tecnico:generar_pdf_rhitso_prueba',
                {'orden_id': 1},
                views_rhitso.generar_pdf_rhitso_prueba,
            ),
        ]
        for name, kwargs, expected in casos:
            with self.subTest(name=name):
                url = reverse(name, kwargs=kwargs)
                match = resolve(url)
                self.assertIs(match.func, expected, msg=f'Fallo en {name}')

    def test_urls_envios_resuelven_modulo_nuevo(self):
        """reverse/resolve envíos → views_envios_cliente."""
        casos = [
            (
                'servicio_tecnico:confirmar_envio_feedback',
                {'feedback_id': 1},
                views_envios_cliente.confirmar_envio_feedback,
            ),
            (
                'servicio_tecnico:confirmar_envio_vigencia_vencida',
                {'orden_id': 1},
                views_envios_cliente.confirmar_envio_vigencia_vencida,
            ),
            (
                'servicio_tecnico:enviar_imagenes_cliente',
                {'orden_id': 1},
                views_envios_cliente.enviar_imagenes_cliente,
            ),
            (
                'servicio_tecnico:enviar_imagenes_egreso_cliente',
                {'orden_id': 1},
                views_envios_cliente.enviar_imagenes_egreso_cliente,
            ),
            (
                'servicio_tecnico:enviar_rewind_egreso_cliente',
                {'orden_id': 1},
                views_envios_cliente.enviar_rewind_egreso_cliente,
            ),
            (
                'servicio_tecnico:enviar_evidencia_video',
                {'orden_id': 1},
                views_envios_cliente.enviar_evidencia_video,
            ),
            (
                'servicio_tecnico:obtener_destinatarios_egreso',
                {'orden_id': 1},
                views_envios_cliente.obtener_destinatarios_egreso,
            ),
            (
                'servicio_tecnico:enviar_diagnostico_cliente',
                {'orden_id': 1},
                views_envios_cliente.enviar_diagnostico_cliente,
            ),
            (
                'servicio_tecnico:preview_pdf_diagnostico',
                {'orden_id': 1},
                views_envios_cliente.preview_pdf_diagnostico,
            ),
            (
                'servicio_tecnico:notificar_equipo_disponible',
                {'orden_id': 1},
                views_envios_cliente.notificar_equipo_disponible,
            ),
        ]
        for name, kwargs, expected in casos:
            with self.subTest(name=name):
                url = reverse(name, kwargs=kwargs)
                match = resolve(url)
                self.assertIs(match.func, expected, msg=f'Fallo en {name}')

    def test_dashboard_rhitso_ya_no_esta_en_views_rhitso(self):
        """
        Dashboard consolidado es Fase 8 (views_dashboard_rhitso), no Fase 7.

        EXPLICACIÓN PARA PRINCIPIANTES:
        views_rhitso.py = gestión por orden. El dashboard de candidatos
        vive en otro módulo para no mezclar pantallas distintas.
        """
        self.assertNotEqual(
            st_views.dashboard_rhitso.__module__,
            'servicio_tecnico.views_rhitso',
        )
        self.assertEqual(
            st_views.dashboard_rhitso.__module__,
            'servicio_tecnico.views_dashboard_rhitso',
        )

    def test_imports_criticos_rhitso(self):
        """Regresión NameError: forms/models/decorators en views_rhitso."""
        for nombre in (
            'ActualizarEstadoRHITSOForm',
            'EditarDiagnosticoSICForm',
            'RegistrarIncidenciaRHITSOForm',
            'ResolverIncidenciaRHITSOForm',
            'OrdenServicio',
            'EstadoRHITSO',
            'SeguimientoRHITSO',
            'IncidenciaRHITSO',
            'ConfiguracionRHITSO',
            'Empleado',
            'registrar_historial',
            'timezone',
            'JsonResponse',
            'permission_required_with_message',
        ):
            with self.subTest(nombre=nombre):
                self.assertTrue(
                    hasattr(views_rhitso, nombre),
                    msg=f'Falta {nombre} en views_rhitso',
                )

    def test_imports_criticos_envios(self):
        """Regresión NameError: modelos/JSON/xframe en views_envios_cliente."""
        for nombre in (
            'OrdenServicio',
            'HistorialOrden',
            'ImagenOrden',
            'VideoOrden',
            'JsonResponse',
            'HttpResponse',
            'json',
            'xframe_options_exempt',
            'messages',
            'permission_required_with_message',
        ):
            with self.subTest(nombre=nombre):
                self.assertTrue(
                    hasattr(views_envios_cliente, nombre),
                    msg=f'Falta {nombre} en views_envios_cliente',
                )


class ConfirmarEnvioVigenciaSmokeTest(SimpleTestCase):
    """
    Smoke: cancelar envío de vigencia no encola Celery.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Si accion != 'enviar', solo muestra mensaje y redirige.
    Mockeamos la orden y .delay() para no tocar BD ni mandar correos.
    """

    @patch('servicio_tecnico.views_envios_cliente.redirect')
    @patch('servicio_tecnico.views_envios_cliente.messages')
    @patch('servicio_tecnico.views_envios_cliente.get_object_or_404')
    @patch('servicio_tecnico.tasks.enviar_vigencia_vencida_task.delay')
    def test_cancelar_no_encola_tarea(
        self, mock_delay, mock_get, mock_messages, mock_redirect
    ):
        """Cancelar no debe llamar a Celery."""
        from unittest.mock import MagicMock

        orden = MagicMock()
        orden.pk = 99
        mock_get.return_value = orden
        mock_redirect.return_value = MagicMock(status_code=302)

        factory = RequestFactory()
        request = factory.post(
            '/fake-confirmar-vigencia/',
            data={'accion': 'cancelar'},
        )
        request.user = MagicMock(is_authenticated=True, pk=1)

        response = views_envios_cliente.confirmar_envio_vigencia_vencida(
            request, orden_id=99
        )

        self.assertEqual(response.status_code, 302)
        mock_delay.assert_not_called()
        mock_messages.info.assert_called_once()
