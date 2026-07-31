"""
Tests de cascada automática en analizar_sentimiento_dispatch.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Estos tests NO llaman a Google ni a Ollama de verdad. Usamos `unittest.mock`
para simular respuestas y comprobar que el dispatcher:
1. Se detiene en el primer Gemini exitoso
2. Prueba el siguiente Gemini si el error es recuperable
3. Salta a Ollama si el error es irrecuperable o se agotan los Gemini
4. Devuelve error si todos fallan
5. Con override Ollama no toca Gemini
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


# Encuesta mínima para armar el dispatch sin depender de la BD.
_ENCUESTA_MINIMA = {
    'calificacion_general': 5,
    'calificacion_atencion': 5,
    'calificacion_tiempo': 4,
    'nps': 9,
    'recomienda': True,
    'comentario': 'Buen servicio.',
}

_ANALISIS_OK = {
    'sentimiento_general': 'positivo',
    'resumen_ejecutivo': 'Clientes satisfechos en general.',
    'temas_positivos': ['atención'],
    'temas_negativos': [],
    'recomendacion_ia': 'Mantener el nivel de servicio.',
}


@override_settings(
    GEMINI_ENABLED=True,
    OLLAMA_ENABLED=True,
    GEMINI_MODELS=['gemini-primero', 'gemini-segundo'],
    OLLAMA_MODEL='modelo-ollama-local',
)
class AnalizarSentimientoDispatchCascadaTests(SimpleTestCase):
    """
    Objetivo: validar la cascada Gemini → Ollama del sentimiento sin red real.

    No toca BD; solo lógica del dispatcher con mocks.
    """

    def _kwargs(self) -> dict:
        """Argumentos comunes: modo automático (sin override)."""
        return {
            'encuestas': [_ENCUESTA_MINIMA],
            'modelo_override': '',
        }

    @patch('servicio_tecnico.ollama_client.analizar_sentimiento_encuestas')
    @patch('servicio_tecnico.gemini_client.analizar_sentimiento_encuestas')
    def test_exito_primer_gemini_no_llama_ollama(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Si el primer Gemini responde bien, no debe intentar más ni Ollama."""
        from servicio_tecnico.ollama_client import analizar_sentimiento_dispatch

        mock_gemini.return_value = {
            'success': True,
            'analisis': _ANALISIS_OK,
            'modelo_usado': 'gemini-primero',
        }

        resultado = analizar_sentimiento_dispatch(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['modelo_usado'], 'gemini-primero')
        self.assertEqual(mock_gemini.call_count, 1)
        mock_ollama.assert_not_called()

    @patch('servicio_tecnico.ollama_client.analizar_sentimiento_encuestas')
    @patch('servicio_tecnico.gemini_client.analizar_sentimiento_encuestas')
    def test_error_recuperable_prueba_siguiente_gemini(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """rate_limit en el primero → intenta el segundo Gemini; si ok, no Ollama."""
        from servicio_tecnico.ollama_client import analizar_sentimiento_dispatch

        mock_gemini.side_effect = [
            {
                'success': False,
                'error': 'Rate limit',
                'error_type': 'rate_limit',
            },
            {
                'success': True,
                'analisis': _ANALISIS_OK,
                'modelo_usado': 'gemini-segundo',
            },
        ]

        resultado = analizar_sentimiento_dispatch(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['modelo_usado'], 'gemini-segundo')
        self.assertEqual(mock_gemini.call_count, 2)
        mock_ollama.assert_not_called()

    @patch('servicio_tecnico.ollama_client.analizar_sentimiento_encuestas')
    @patch('servicio_tecnico.gemini_client.analizar_sentimiento_encuestas')
    def test_error_irrecuperable_salta_a_ollama(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """hard_error en el primer Gemini → no prueba el segundo; cae a Ollama."""
        from servicio_tecnico.ollama_client import analizar_sentimiento_dispatch

        mock_gemini.return_value = {
            'success': False,
            'error': 'API key inválida',
            'error_type': 'hard_error',
        }
        mock_ollama.return_value = {
            'success': True,
            'analisis': _ANALISIS_OK,
            'modelo_usado': 'modelo-ollama-local',
        }

        resultado = analizar_sentimiento_dispatch(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['modelo_usado'], 'modelo-ollama-local')
        self.assertEqual(mock_gemini.call_count, 1)
        mock_ollama.assert_called_once()
        self.assertEqual(
            mock_ollama.call_args.kwargs.get('modelo'),
            'modelo-ollama-local',
        )

    @patch('servicio_tecnico.ollama_client.analizar_sentimiento_encuestas')
    @patch('servicio_tecnico.gemini_client.analizar_sentimiento_encuestas')
    def test_todos_gemini_fallan_cae_a_ollama(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Todos los Gemini con error recuperable → se agotan → Ollama."""
        from servicio_tecnico.ollama_client import analizar_sentimiento_dispatch

        mock_gemini.side_effect = [
            {'success': False, 'error': 'timeout 1', 'error_type': 'timeout'},
            {'success': False, 'error': 'timeout 2', 'error_type': 'timeout'},
        ]
        mock_ollama.return_value = {
            'success': True,
            'analisis': _ANALISIS_OK,
            'modelo_usado': 'modelo-ollama-local',
        }

        resultado = analizar_sentimiento_dispatch(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(mock_gemini.call_count, 2)
        mock_ollama.assert_called_once()

    @patch('servicio_tecnico.ollama_client.analizar_sentimiento_encuestas')
    @patch('servicio_tecnico.gemini_client.analizar_sentimiento_encuestas')
    def test_todo_falla_devuelve_error(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Si Gemini y Ollama fallan, success=False con mensaje claro."""
        from servicio_tecnico.ollama_client import analizar_sentimiento_dispatch

        mock_gemini.side_effect = [
            {'success': False, 'error': 'fallo g1', 'error_type': 'server_error'},
            {'success': False, 'error': 'fallo g2', 'error_type': 'server_error'},
        ]
        mock_ollama.return_value = {
            'success': False,
            'error': 'Ollama no disponible',
        }

        resultado = analizar_sentimiento_dispatch(**self._kwargs())

        self.assertFalse(resultado['success'])
        self.assertIn('Ollama', resultado.get('error', ''))

    @patch('servicio_tecnico.ollama_client.analizar_sentimiento_encuestas')
    @patch('servicio_tecnico.gemini_client.analizar_sentimiento_encuestas')
    def test_override_ollama_sin_cascada_gemini(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Override Ollama explícito: no debe tocar Gemini."""
        from servicio_tecnico.ollama_client import analizar_sentimiento_dispatch

        mock_ollama.return_value = {
            'success': True,
            'analisis': _ANALISIS_OK,
            'modelo_usado': 'gemma-local',
        }

        kwargs = self._kwargs()
        kwargs['modelo_override'] = '[Ollama] gemma-local'
        resultado = analizar_sentimiento_dispatch(**kwargs)

        self.assertTrue(resultado['success'])
        mock_gemini.assert_not_called()
        mock_ollama.assert_called_once()
        # Debe pasar el nombre limpio sin prefijo
        self.assertEqual(
            mock_ollama.call_args.kwargs.get('modelo'),
            'gemma-local',
        )

    @patch('servicio_tecnico.ollama_client.analizar_sentimiento_encuestas')
    @patch('servicio_tecnico.gemini_client.analizar_sentimiento_encuestas')
    def test_override_gemini_primero_luego_resto(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """
        Override Gemini: el elegido primero; si falla recuperable, prueba el resto.
        """
        from servicio_tecnico.ollama_client import analizar_sentimiento_dispatch

        mock_gemini.side_effect = [
            {
                'success': False,
                'error': 'rate limit elegido',
                'error_type': 'rate_limit',
            },
            {
                'success': True,
                'analisis': _ANALISIS_OK,
                'modelo_usado': 'gemini-primero',
            },
        ]

        kwargs = self._kwargs()
        kwargs['modelo_override'] = '[Gemini] gemini-segundo'
        resultado = analizar_sentimiento_dispatch(**kwargs)

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['modelo_usado'], 'gemini-primero')
        # Primero el override (gemini-segundo), luego gemini-primero del resto
        self.assertEqual(mock_gemini.call_count, 2)
        self.assertEqual(
            mock_gemini.call_args_list[0].kwargs.get('modelo'),
            'gemini-segundo',
        )
        self.assertEqual(
            mock_gemini.call_args_list[1].kwargs.get('modelo'),
            'gemini-primero',
        )
        mock_ollama.assert_not_called()
