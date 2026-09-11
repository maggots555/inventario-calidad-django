"""
Tests del timeout de inspección IA en el envío de fotos de ingreso.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
La tarea Celery comprime fotos, pide un análisis a Gemini/Ollama y LUEGO
manda el correo. Si la IA se cuelga, Celery mataba al worker (SIGKILL) y
el cliente nunca recibía el correo.

Estos tests NO llaman a Google ni a Ollama de verdad, ni envían correo real.
Comprobamos tres reglas:

1. El HTTP de fotos de ingreso usa INSPECCION_IA_HTTP_TIMEOUT (180s), no los
   600s del análisis de video.
2. Si el primer Gemini da timeout, NO se prueba el segundo ni Ollama.
3. Si Celery lanza SoftTimeLimitExceeded durante la IA, EmailMessage.send
   igual se llama (la IA es no crítica).
"""

from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import URLError

from celery.exceptions import SoftTimeLimitExceeded
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, ImagenOrden, OrdenServicio


User = get_user_model()


def _jpeg_bytes() -> bytes:
    """
    Genera un JPEG diminuto en memoria (no hace falta una foto real).

    Returns:
        bytes: Contenido JPEG de 32x32 px.
    """
    buf = BytesIO()
    Image.new('RGB', (32, 32), color=(10, 20, 30)).save(buf, format='JPEG')
    return buf.getvalue()


@override_settings(
    INSPECCION_IA_HTTP_TIMEOUT=180,
    OLLAMA_VISION_TIMEOUT=600,
    CELERY_TASK_SOFT_TIME_LIMIT=300,
    CELERY_TASK_TIME_LIMIT=600,
)
class TimeoutInspeccionIaHttpTests(SimpleTestCase):
    """
    El timeout de fotos de ingreso debe caber DENTRO del soft limit de Celery.

    No toca BD. Solo settings y urllib mockeado.
    """

    def test_helper_lee_setting_no_el_de_video(self) -> None:
        """INSPECCION_IA_HTTP_TIMEOUT manda; OLLAMA_VISION_TIMEOUT no se cuela."""
        from servicio_tecnico.ollama_client import timeout_inspeccion_ia_http

        self.assertEqual(timeout_inspeccion_ia_http(), 180)

    def test_invariante_menor_que_soft_limit_celery(self) -> None:
        """
        Si el HTTP dura tanto como el soft/hard de Celery, SIGKILL gana.
        Este assert documenta el contrato del .env.
        """
        from django.conf import settings

        from servicio_tecnico.ollama_client import timeout_inspeccion_ia_http

        timeout_http = timeout_inspeccion_ia_http()
        self.assertLess(timeout_http, settings.CELERY_TASK_SOFT_TIME_LIMIT)
        self.assertLess(timeout_http, settings.CELERY_TASK_TIME_LIMIT)

    def test_tarea_time_limit_cubre_http_de_ia(self) -> None:
        """La tarea debe poder terminar el SMTP después de un HTTP de 180s."""
        from servicio_tecnico.ollama_client import timeout_inspeccion_ia_http
        from servicio_tecnico.tasks import enviar_imagenes_cliente_task

        self.assertEqual(enviar_imagenes_cliente_task.soft_time_limit, 300)
        self.assertEqual(enviar_imagenes_cliente_task.time_limit, 420)
        self.assertLess(timeout_inspeccion_ia_http(), enviar_imagenes_cliente_task.soft_time_limit)
        self.assertLess(timeout_inspeccion_ia_http(), enviar_imagenes_cliente_task.time_limit)

    @override_settings(
        GEMINI_ENABLED=True,
        GEMINI_API_KEY='fake-key-test',
        GEMINI_MODEL='gemini-test-vision',
    )
    @patch('servicio_tecnico.gemini_client.urllib.request.urlopen')
    def test_gemini_ingreso_pasa_timeout_de_inspeccion(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        """urlopen de Gemini visión recibe 180s, no los 600s de video."""
        from servicio_tecnico.gemini_client import analizar_imagenes_ingreso_gemini

        mock_urlopen.side_effect = TimeoutError('timed out')
        resultado = analizar_imagenes_ingreso_gemini(imagenes_bytes=[_jpeg_bytes()])

        self.assertEqual(mock_urlopen.call_args.kwargs.get('timeout'), 180)
        self.assertFalse(resultado['success'])
        self.assertEqual(resultado['error_type'], 'timeout')

    @override_settings(
        GEMINI_ENABLED=True,
        GEMINI_API_KEY='fake-key-test',
        GEMINI_MODEL='gemini-test-vision',
    )
    @patch('servicio_tecnico.gemini_client.urllib.request.urlopen')
    def test_gemini_urlerror_timeout_se_clasifica_como_timeout(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        """
        urllib envuelve el timeout del socket en URLError.
        Si lo tratáramos como network_error, el dispatcher reintentaría.
        """
        from servicio_tecnico.gemini_client import analizar_imagenes_ingreso_gemini

        mock_urlopen.side_effect = URLError(TimeoutError('timed out'))
        resultado = analizar_imagenes_ingreso_gemini(imagenes_bytes=[_jpeg_bytes()])

        self.assertFalse(resultado['success'])
        self.assertEqual(resultado['error_type'], 'timeout')

    @override_settings(
        OLLAMA_ENABLED=True,
        OLLAMA_BASE_URL='http://ollama.test',
        OLLAMA_MODEL='gemma-test-vision',
    )
    @patch('servicio_tecnico.ollama_client.urllib.request.urlopen')
    def test_ollama_ingreso_pasa_timeout_de_inspeccion(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        """urlopen de Ollama visión de ingreso también usa 180s."""
        from servicio_tecnico.ollama_client import analizar_imagenes_ingreso_ollama

        mock_urlopen.side_effect = TimeoutError('timed out')
        resultado = analizar_imagenes_ingreso_ollama(imagenes_bytes=[_jpeg_bytes()])

        self.assertEqual(mock_urlopen.call_args.kwargs.get('timeout'), 180)
        self.assertFalse(resultado['success'])
        self.assertEqual(resultado['error_type'], 'timeout')


@override_settings(
    GEMINI_ENABLED=True,
    OLLAMA_ENABLED=True,
    GEMINI_MODELS=['gemini-primero', 'gemini-segundo'],
    OLLAMA_MODEL='modelo-ollama-local',
)
class DispatchTimeoutAbortaCascadaTests(SimpleTestCase):
    """
    Un timeout de visión debe cortar YA: no más Gemini ni Ollama.

    Objetivo: no encadenar varios HTTP de 180s que sumen más que Celery.
    """

    def _kwargs(self) -> dict:
        """Argumentos mínimos del dispatcher de ingreso."""
        return {
            'imagenes_bytes': [_jpeg_bytes()],
            'tipo_equipo': 'Laptop',
            'marca': 'Dell',
            'modelo_equipo': 'Latitude',
        }

    @patch('servicio_tecnico.ollama_client.analizar_imagenes_ingreso_ollama')
    @patch('servicio_tecnico.gemini_client.analizar_imagenes_ingreso_gemini')
    def test_timeout_primer_gemini_no_prueba_segundo_ni_ollama(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Timeout en el primero → success=False, un solo intento Gemini."""
        from servicio_tecnico.ollama_client import analizar_imagenes_ingreso_dispatch

        mock_gemini.return_value = {
            'success': False,
            'error': 'Gemini tardó más de 180s en responder.',
            'error_type': 'timeout',
        }

        resultado = analizar_imagenes_ingreso_dispatch(**self._kwargs())

        self.assertFalse(resultado['success'])
        self.assertEqual(resultado.get('error_type'), 'timeout')
        self.assertEqual(mock_gemini.call_count, 1)
        mock_ollama.assert_not_called()

    @patch('servicio_tecnico.ollama_client.analizar_imagenes_ingreso_ollama')
    @patch('servicio_tecnico.gemini_client.analizar_imagenes_ingreso_gemini')
    def test_rate_limit_si_prueba_siguiente_gemini(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Un 429 es rápido: sí debemos probar el siguiente modelo."""
        from servicio_tecnico.ollama_client import analizar_imagenes_ingreso_dispatch

        mock_gemini.side_effect = [
            {
                'success': False,
                'error': 'cuota agotada',
                'error_type': 'rate_limit',
            },
            {
                'success': True,
                'analisis': 'Equipo en buen estado estético general.',
                'modelo_usado': 'gemini-segundo',
            },
        ]

        resultado = analizar_imagenes_ingreso_dispatch(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['modelo_usado'], 'gemini-segundo')
        self.assertEqual(mock_gemini.call_count, 2)
        mock_ollama.assert_not_called()


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class EnviarImagenesSoftTimeLimitTests(TestCase):
    """
    SoftTimeLimitExceeded en la IA no debe impedir el correo.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Mockeamos el dispatcher para que lance la excepción de Celery, y
    EmailMessage.send para no mandar correo real. Si el except está bien,
    send() se llama una vez y la tarea responde success=True.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        """Crea sucursal, usuario, orden e imagen JPEG de ingreso."""
        self.sucursal = Sucursal.objects.create(
            codigo='SC-IA-TO',
            nombre='Sucursal Timeout IA',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_timeout_ia',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Timeout IA',
            cargo='Técnico',
            area='Laboratorio',
            email='timeout.ia@test.local',
            sucursal=self.sucursal,
            user=self.user,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='TO-IA-0001',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude 5430',
            numero_serie='SN-TIMEOUT-IA',
            email_cliente='cliente.timeout@test.local',
            nombre_cliente='Cliente Timeout IA',
            falla_principal='No enciende',
            gama='media',
        )
        self.imagen = ImagenOrden(
            orden=self.orden,
            tipo='ingreso',
            descripcion='Foto ingreso test timeout',
            subido_por=self.empleado,
        )
        self.imagen.imagen.save(
            'ingreso_timeout.jpg',
            ContentFile(_jpeg_bytes()),
            save=True,
        )

    @patch('notificaciones.utils.notificar_exito')
    @patch('servicio_tecnico.ollama_client.analizar_imagenes_ingreso_dispatch')
    def test_soft_time_limit_no_impide_enviar_correo(
        self,
        mock_dispatch: MagicMock,
        mock_notif: MagicMock,
    ) -> None:
        """
        La IA lanza SoftTimeLimitExceeded → el correo igual se envía.

        Args:
            mock_dispatch: dispatcher de IA (se hace explotar a propósito).
            mock_notif: campanita de éxito (no es el foco de este test).
        """
        from servicio_tecnico.tasks import enviar_imagenes_cliente_task

        mock_dispatch.side_effect = SoftTimeLimitExceeded()
        capturados: list = []

        def _fake_send(self_msg, fail_silently=False):
            """Sustituto de SMTP: guarda el mensaje y finge éxito."""
            capturados.append(self_msg)
            return 1

        with patch('django.core.mail.EmailMessage.send', new=_fake_send):
            resultado = enviar_imagenes_cliente_task.run(
                orden_id=self.orden.pk,
                imagenes_ids=[str(self.imagen.pk)],
                destinatarios_copia=[],
                mensaje_personalizado='',
                usuario_id=self.user.pk,
                modelo_ia_inspeccion='',
                db_alias='default',
            )

        self.assertTrue(resultado.get('success'))
        self.assertEqual(len(capturados), 1)
        self.assertIn('cliente.timeout@test.local', capturados[0].to)
        mock_dispatch.assert_called_once()
        mock_notif.assert_called()
