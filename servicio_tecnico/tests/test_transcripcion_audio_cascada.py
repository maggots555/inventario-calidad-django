"""
Tests de la cascada de transcripción: Transcribe → Gemini Flash → Ollama.

EXPLICACIÓN PARA PRINCIPIANTES:
No llamamos a Google ni a Ollama de verdad. Con `unittest.mock` simulamos
respuestas para comprobar el ORDEN de intentos:

1. Si Transcribe funciona, no se llama a Flash ni a Ollama.
2. Si Transcribe falla, se prueba Gemini general (Flash/Lite).
3. Si Gemini también falla, se llama a Ollama.
4. Si todos fallan, se devuelve error.
"""

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from servicio_tecnico.services.transcripcion_audio import (
    _extraer_texto_interaccion,
    transcribir_audio_cascada,
)


AUDIO_FAKE = b'RIFF....fake-webm-bytes'


@override_settings(
    GEMINI_ENABLED=True,
    GEMINI_TRANSCRIBE_ENABLED=True,
    GEMINI_TRANSCRIBE_MODEL='gemini-3.5-transcribe',
    GEMINI_API_KEY='fake-key-test',
    GEMINI_MODELS=['gemini-3.6-flash', 'gemini-2.5-flash'],
    GEMINI_MODEL='gemini-3.6-flash',
    OLLAMA_ENABLED=True,
    OLLAMA_MODEL='gemma4:e4b',
)
class TranscripcionAudioCascadaTests(SimpleTestCase):
    """
    Objetivo: validar el orden Transcribe → Gemini → Ollama sin red real.
    """

    def _kwargs(self) -> dict:
        return {
            'audio_bytes': AUDIO_FAKE,
            'audio_filename': 'diag.webm',
            'audio_content_type': 'audio/webm',
            'idioma': 'es',
        }

    @patch('servicio_tecnico.ollama_client.transcribir_audio_ollama')
    @patch('servicio_tecnico.gemini_client.transcribir_audio_gemini_con_fallback')
    @patch(
        'servicio_tecnico.services.transcripcion_audio.transcribir_con_gemini_transcribe'
    )
    def test_exito_transcribe_no_llama_gemini_ni_ollama(
        self,
        mock_transcribe: MagicMock,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Si Transcribe responde bien, no se gasta Flash ni Ollama."""
        mock_transcribe.return_value = {
            'success': True,
            'texto': 'El equipo no enciende.',
            'modelo_usado': 'gemini-3.5-transcribe',
        }

        resultado = transcribir_audio_cascada(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['proveedor'], 'gemini-transcribe')
        self.assertEqual(resultado['texto'], 'El equipo no enciende.')
        mock_transcribe.assert_called_once()
        mock_gemini.assert_not_called()
        mock_ollama.assert_not_called()

    @patch('servicio_tecnico.ollama_client.transcribir_audio_ollama')
    @patch('servicio_tecnico.gemini_client.transcribir_audio_gemini_con_fallback')
    @patch(
        'servicio_tecnico.services.transcripcion_audio.transcribir_con_gemini_transcribe'
    )
    def test_transcribe_falla_cae_a_gemini_flash(
        self,
        mock_transcribe: MagicMock,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Transcribe 429/error → Flash; si Flash gana, no se llama Ollama."""
        mock_transcribe.return_value = {
            'success': False,
            'error': 'Gemini Transcribe HTTP 429: quota',
        }
        mock_gemini.return_value = {
            'success': True,
            'texto': 'Texto desde Flash.',
            'modelo_usado': 'gemini-3.6-flash',
            'intentos': 1,
        }

        resultado = transcribir_audio_cascada(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['proveedor'], 'gemini')
        self.assertEqual(resultado['modelo_usado'], 'gemini-3.6-flash')
        mock_transcribe.assert_called_once()
        mock_gemini.assert_called_once()
        # No debe reintentar el modelo STT dentro de GEMINI_MODELS.
        modelos_pasados = mock_gemini.call_args.kwargs.get('modelos')
        self.assertEqual(modelos_pasados, ['gemini-3.6-flash', 'gemini-2.5-flash'])
        mock_ollama.assert_not_called()

    @patch('servicio_tecnico.ollama_client.transcribir_audio_ollama')
    @patch('servicio_tecnico.gemini_client.transcribir_audio_gemini_con_fallback')
    @patch(
        'servicio_tecnico.services.transcripcion_audio.transcribir_con_gemini_transcribe'
    )
    def test_gemini_falla_cae_a_ollama(
        self,
        mock_transcribe: MagicMock,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Si Google (Transcribe + Flash) falla, último recurso es Ollama."""
        mock_transcribe.return_value = {'success': False, 'error': 'transcribe down'}
        mock_gemini.return_value = {
            'success': False,
            'error': 'todos los flash fallaron',
            'intentos': 2,
        }
        mock_ollama.return_value = {
            'success': True,
            'texto': 'Texto desde Ollama.',
        }

        resultado = transcribir_audio_cascada(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['proveedor'], 'ollama')
        self.assertEqual(resultado['texto'], 'Texto desde Ollama.')
        mock_ollama.assert_called_once()

    @patch('servicio_tecnico.ollama_client.transcribir_audio_ollama')
    @patch('servicio_tecnico.gemini_client.transcribir_audio_gemini_con_fallback')
    @patch(
        'servicio_tecnico.services.transcripcion_audio.transcribir_con_gemini_transcribe'
    )
    def test_todos_fallan_devuelve_error(
        self,
        mock_transcribe: MagicMock,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Si nadie transcribe, success=False con el último error."""
        mock_transcribe.return_value = {'success': False, 'error': 't1'}
        mock_gemini.return_value = {
            'success': False,
            'error': 't2',
            'intentos': 1,
        }
        mock_ollama.return_value = {'success': False, 'error': 't3'}

        resultado = transcribir_audio_cascada(**self._kwargs())

        self.assertFalse(resultado['success'])
        self.assertEqual(resultado['error'], 't3')
        self.assertGreaterEqual(resultado['intentos'], 3)

    @override_settings(GEMINI_TRANSCRIBE_ENABLED=False)
    @patch('servicio_tecnico.ollama_client.transcribir_audio_ollama')
    @patch('servicio_tecnico.gemini_client.transcribir_audio_gemini_con_fallback')
    @patch(
        'servicio_tecnico.services.transcripcion_audio.transcribir_con_gemini_transcribe'
    )
    def test_transcribe_desactivado_empieza_en_flash(
        self,
        mock_transcribe: MagicMock,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """GEMINI_TRANSCRIBE_ENABLED=False salta el STT dedicado."""
        mock_gemini.return_value = {
            'success': True,
            'texto': 'solo flash',
            'modelo_usado': 'gemini-3.6-flash',
            'intentos': 1,
        }

        resultado = transcribir_audio_cascada(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['proveedor'], 'gemini')
        mock_transcribe.assert_not_called()
        mock_gemini.assert_called_once()
        mock_ollama.assert_not_called()

    @override_settings(GEMINI_ENABLED=False, GEMINI_TRANSCRIBE_ENABLED=True)
    @patch('servicio_tecnico.ollama_client.transcribir_audio_ollama')
    @patch('servicio_tecnico.gemini_client.transcribir_audio_gemini_con_fallback')
    @patch(
        'servicio_tecnico.services.transcripcion_audio.transcribir_con_gemini_transcribe'
    )
    def test_gemini_apagado_usa_solo_ollama(
        self,
        mock_transcribe: MagicMock,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Sin Gemini, la cascada no llama a Google y va directo a Ollama."""
        mock_ollama.return_value = {
            'success': True,
            'texto': 'solo ollama',
        }

        resultado = transcribir_audio_cascada(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['proveedor'], 'ollama')
        mock_transcribe.assert_not_called()
        mock_gemini.assert_not_called()
        mock_ollama.assert_called_once()

    @patch('servicio_tecnico.gemini_client.transcribir_audio_gemini_con_fallback')
    @patch(
        'servicio_tecnico.services.transcripcion_audio.transcribir_con_gemini_transcribe'
    )
    def test_omite_transcribe_si_esta_en_gemini_models(
        self,
        mock_transcribe: MagicMock,
        mock_gemini: MagicMock,
    ) -> None:
        """No reintenta gemini-3.5-transcribe por generateContent."""
        mock_transcribe.return_value = {'success': False, 'error': 'preview'}
        mock_gemini.return_value = {
            'success': True,
            'texto': 'flash ok',
            'modelo_usado': 'gemini-3.6-flash',
            'intentos': 1,
        }

        with override_settings(
            GEMINI_MODELS=['gemini-3.5-transcribe', 'gemini-3.6-flash'],
        ):
            transcribir_audio_cascada(**self._kwargs())

        modelos_pasados = mock_gemini.call_args.kwargs.get('modelos')
        self.assertEqual(modelos_pasados, ['gemini-3.6-flash'])


class ExtraerTextoInteraccionTests(SimpleTestCase):
    """
    Objetivo: parsear el JSON de Interactions API sin SDK de Google.
    """

    def test_lee_output_text(self):
        """Campo que documenta el SDK."""
        self.assertEqual(
            _extraer_texto_interaccion({'output_text': '  hola  '}),
            'hola',
        )

    def test_lee_outputs_lista(self):
        """REST crudo a veces trae outputs[].text."""
        data = {'outputs': [{'type': 'text', 'text': 'linea uno'}]}
        self.assertEqual(_extraer_texto_interaccion(data), 'linea uno')

    def test_vacio_si_no_hay_texto(self):
        """Sin texto → cascada debe pasar al siguiente proveedor."""
        self.assertEqual(_extraer_texto_interaccion({}), '')


@override_settings(
    GEMINI_ENABLED=True,
    GEMINI_TRANSCRIBE_ENABLED=True,
    GEMINI_TRANSCRIBE_MODEL='gemini-3.5-transcribe',
    GEMINI_API_KEY='fake-key-test',
    GEMINI_TIMEOUT=10,
)
class TranscribirConGeminiTranscribeHttpTests(SimpleTestCase):
    """
    Objetivo: la llamada REST usa Interactions API (no generateContent).
    """

    @patch('servicio_tecnico.services.transcripcion_audio.urllib.request.urlopen')
    def test_post_a_interactions_y_lee_output_text(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        """
        Verifica URL, modelo y que el texto sale de output_text.
        """
        from servicio_tecnico.services.transcripcion_audio import (
            GEMINI_INTERACTIONS_URL,
            transcribir_con_gemini_transcribe,
        )

        # EXPLICACIÓN: urlopen se usa como context manager (`with urlopen(...)`).
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {'output_text': 'Equipo no enciende.'}
        ).encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response

        resultado = transcribir_con_gemini_transcribe(
            audio_bytes=AUDIO_FAKE,
            audio_content_type='audio/webm',
            idioma='es',
        )

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['texto'], 'Equipo no enciende.')
        self.assertEqual(resultado['modelo_usado'], 'gemini-3.5-transcribe')

        request = mock_urlopen.call_args[0][0]
        self.assertEqual(request.full_url, GEMINI_INTERACTIONS_URL)
        payload = json.loads(request.data.decode('utf-8'))
        self.assertEqual(payload['model'], 'gemini-3.5-transcribe')
        self.assertEqual(payload['input'][0]['type'], 'audio')
        config_stt = payload['generation_config']['transcription_config']
        self.assertEqual(config_stt['mode']['type'], 'smart')
        self.assertEqual(config_stt['language_codes'], ['es-MX'])
        # Google responde HTTP 400 si mandamos language_hints (campo inexistente).
        self.assertNotIn('language_hints', config_stt)
        # GEMINI_TIMEOUT=10 en esta clase; audio usa GEMINI_TRANSCRIBE_TIMEOUT (180).
        self.assertEqual(mock_urlopen.call_args.kwargs.get('timeout'), 180)


class TimeoutTranscripcionTests(SimpleTestCase):
    """El timeout de audio no debe heredar GEMINI_TIMEOUT (pulir texto)."""

    @override_settings(GEMINI_TIMEOUT=60, GEMINI_TRANSCRIBE_TIMEOUT=180)
    def test_lee_transcribe_timeout_no_el_global(self):
        from servicio_tecnico.services.transcripcion_audio import timeout_transcripcion

        self.assertEqual(timeout_transcripcion(), 180)


@override_settings(
    GEMINI_ENABLED=True,
    OLLAMA_ENABLED=False,
    GEMINI_TRANSCRIBE_ENABLED=True,
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'transcribe-vista-tests',
        }
    },
)
class TranscripcionCeleryVistaTests(SimpleTestCase):
    """
    POST encola Celery (no corre la cascada). GET consulta AsyncResult.
    """

    def setUp(self) -> None:
        from django.test import RequestFactory

        self.factory = RequestFactory()
        self.user = MagicMock()
        self.user.pk = 7
        self.user.username = 'tec.transcribe'
        self.user.is_authenticated = True
        self.user.is_anonymous = False

    def _post_audio(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.urls import reverse

        from servicio_tecnico.views_ia_diagnostico import transcribir_audio_diagnostico

        audio = SimpleUploadedFile(
            'diagnostico.webm',
            AUDIO_FAKE,
            content_type='audio/webm',
        )
        request = self.factory.post(
            reverse('servicio_tecnico:transcribir_audio_diagnostico'),
            {'idioma': 'es', 'audio': audio},
        )
        request.user = self.user
        return transcribir_audio_diagnostico(request)

    @patch('servicio_tecnico.tasks_transcripcion.transcribir_audio_diagnostico_task.delay')
    @patch('config.paises_config.get_pais_actual')
    def test_post_encola_y_no_corre_cascada(
        self,
        mock_pais: MagicMock,
        mock_delay: MagicMock,
    ) -> None:
        """El request HTTP solo guarda cache y devuelve task_id."""
        from django.core.cache import cache

        from servicio_tecnico.services.transcripcion_audio import clave_cache_owner

        mock_pais.return_value = {'db_alias': 'default'}
        mock_delay.return_value = MagicMock(id='task-uuid-test')

        with patch(
            'servicio_tecnico.services.transcripcion_audio.transcribir_audio_cascada'
        ) as mock_cascada:
            respuesta = self._post_audio()

        self.assertEqual(respuesta.status_code, 200)
        data = json.loads(respuesta.content)
        self.assertTrue(data['success'])
        self.assertEqual(data['task_id'], 'task-uuid-test')
        mock_delay.assert_called_once()
        mock_cascada.assert_not_called()
        self.assertEqual(cache.get(clave_cache_owner('task-uuid-test')), 7)

    @patch('celery.result.AsyncResult')
    def test_get_estado_success_devuelve_texto(self, mock_ar: MagicMock) -> None:
        from django.core.cache import cache
        from django.urls import reverse

        from servicio_tecnico.services.transcripcion_audio import (
            CACHE_TTL_TRANSCRIPCION,
            clave_cache_owner,
        )
        from servicio_tecnico.views_ia_diagnostico import estado_transcripcion_audio

        cache.set(clave_cache_owner('abc'), 7, CACHE_TTL_TRANSCRIPCION)
        mock_ar.return_value.state = 'SUCCESS'
        mock_ar.return_value.result = {
            'success': True,
            'texto': 'El SSD no enciende.',
            'proveedor': 'gemini-transcribe',
            'modelo_usado': 'gemini-3.5-transcribe',
        }
        request = self.factory.get(
            reverse(
                'servicio_tecnico:estado_transcripcion_audio',
                kwargs={'task_id': 'abc'},
            )
        )
        request.user = self.user
        respuesta = estado_transcripcion_audio(request, task_id='abc')
        data = json.loads(respuesta.content)
        self.assertTrue(data['listo'])
        self.assertTrue(data['success'])
        self.assertEqual(data['texto'], 'El SSD no enciende.')

    @patch('celery.result.AsyncResult')
    def test_get_estado_usuario_ajeno_403(self, mock_ar: MagicMock) -> None:
        from django.core.cache import cache
        from django.urls import reverse

        from servicio_tecnico.services.transcripcion_audio import (
            CACHE_TTL_TRANSCRIPCION,
            clave_cache_owner,
        )
        from servicio_tecnico.views_ia_diagnostico import estado_transcripcion_audio

        cache.set(clave_cache_owner('abc'), 99, CACHE_TTL_TRANSCRIPCION)
        request = self.factory.get(
            reverse(
                'servicio_tecnico:estado_transcripcion_audio',
                kwargs={'task_id': 'abc'},
            )
        )
        request.user = self.user
        respuesta = estado_transcripcion_audio(request, task_id='abc')
        self.assertEqual(respuesta.status_code, 403)
        mock_ar.assert_not_called()


@override_settings(
    CACHES={
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'transcribe-tarea-tests',
        }
    },
)
class TranscripcionCeleryTareaTests(SimpleTestCase):
    """La tarea lee cache, borra la clave y llama la cascada."""

    @patch('servicio_tecnico.services.transcripcion_audio.transcribir_audio_cascada')
    def test_tarea_lee_cache_y_devuelve_resultado(
        self,
        mock_cascada: MagicMock,
    ) -> None:
        import base64

        from django.core.cache import cache

        from servicio_tecnico.services.transcripcion_audio import (
            CACHE_TTL_TRANSCRIPCION,
            clave_cache_audio,
        )
        from servicio_tecnico.tasks_transcripcion import (
            transcribir_audio_diagnostico_task,
        )

        cache_key = 'clave-test-audio'
        cache.set(
            clave_cache_audio(cache_key),
            {
                'audio_b64': base64.b64encode(AUDIO_FAKE).decode('ascii'),
                'audio_filename': 'diag.webm',
                'audio_content_type': 'audio/webm',
                'idioma': 'es',
            },
            CACHE_TTL_TRANSCRIPCION,
        )
        mock_cascada.return_value = {
            'success': True,
            'texto': 'Placa madre dañada.',
            'proveedor': 'gemini-transcribe',
            'modelo_usado': 'gemini-3.5-transcribe',
        }

        resultado = transcribir_audio_diagnostico_task.run(
            cache_key=cache_key,
            usuario_id=7,
            db_alias='default',
        )

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['texto'], 'Placa madre dañada.')
        mock_cascada.assert_called_once()
        self.assertIsNone(cache.get(clave_cache_audio(cache_key)))

    def test_tarea_cache_vacio_error(self) -> None:
        from servicio_tecnico.tasks_transcripcion import (
            transcribir_audio_diagnostico_task,
        )

        resultado = transcribir_audio_diagnostico_task.run(
            cache_key='no-existe',
            usuario_id=7,
            db_alias='default',
        )
        self.assertFalse(resultado['success'])
        self.assertIn('expiró', resultado['error'])
