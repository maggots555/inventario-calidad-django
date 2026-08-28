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
        self.assertEqual(
            payload['generation_config']['transcription_config']['mode']['type'],
            'smart',
        )
