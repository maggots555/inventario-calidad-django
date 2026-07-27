"""
Tests de cascada automática en mejorar_diagnostico_dispatch.

EXPLICACIÓN PARA PRINCIPIANTES:
Estos tests NO llaman a Google ni a Ollama de verdad. Usamos `unittest.mock`
para simular respuestas y comprobar que el dispatcher:
1. Se detiene en el primer Gemini exitoso
2. Prueba el siguiente Gemini si el error es recuperable
3. Salta a Ollama si el error es irrecuperable o se agotan los Gemini
4. Devuelve error si todos fallan
"""

from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


# Texto mínimo válido para el flujo de mejora (≥20 caracteres)
DIAGNOSTICO_MINIMO = 'Equipo no enciende, se reviso fuente y placa.'


@override_settings(
    GEMINI_ENABLED=True,
    OLLAMA_ENABLED=True,
    GEMINI_MODELS=['gemini-primero', 'gemini-segundo'],
    OLLAMA_MODEL='modelo-ollama-local',
)
class MejorarDiagnosticoDispatchCascadaTests(SimpleTestCase):
    """
    Objetivo: validar la cascada Gemini → Ollama sin red real.

    No toca BD; solo lógica del dispatcher con mocks.
    """

    def _kwargs(self) -> dict:
        """Argumentos comunes para llamar al dispatcher."""
        return {
            'diagnostico_sic': DIAGNOSTICO_MINIMO,
            'tipo_equipo': 'Laptop',
            'marca': 'Dell',
            'modelo': 'Latitude',
            'gama': 'media',
            'equipo_enciende': False,
            'falla_principal': 'No enciende',
            'modelo_override': '',  # modo automático
        }

    @patch('servicio_tecnico.ollama_client.mejorar_diagnostico')
    @patch('servicio_tecnico.gemini_client.mejorar_diagnostico')
    def test_exito_primer_gemini_no_llama_ollama(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """
        Si el primer Gemini responde bien, no debe intentar más ni Ollama.
        """
        from servicio_tecnico.ollama_client import mejorar_diagnostico_dispatch

        mock_gemini.return_value = {
            'success': True,
            'diagnostico_mejorado': 'Texto mejorado por Gemini primero.',
            'modelo_usado': 'gemini-primero',
        }

        resultado = mejorar_diagnostico_dispatch(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['modelo_usado'], 'gemini-primero')
        self.assertEqual(mock_gemini.call_count, 1)
        mock_ollama.assert_not_called()

    @patch('servicio_tecnico.ollama_client.mejorar_diagnostico')
    @patch('servicio_tecnico.gemini_client.mejorar_diagnostico')
    def test_error_recuperable_prueba_siguiente_gemini(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """
        rate_limit en el primero → intenta el segundo Gemini; si ese ok, no Ollama.
        """
        from servicio_tecnico.ollama_client import mejorar_diagnostico_dispatch

        mock_gemini.side_effect = [
            {
                'success': False,
                'error': 'Rate limit',
                'error_type': 'rate_limit',
            },
            {
                'success': True,
                'diagnostico_mejorado': 'Texto del segundo Gemini.',
                'modelo_usado': 'gemini-segundo',
            },
        ]

        resultado = mejorar_diagnostico_dispatch(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['modelo_usado'], 'gemini-segundo')
        self.assertEqual(mock_gemini.call_count, 2)
        mock_ollama.assert_not_called()

    @patch('servicio_tecnico.ollama_client.mejorar_diagnostico')
    @patch('servicio_tecnico.gemini_client.mejorar_diagnostico')
    def test_error_irrecuperable_salta_a_ollama(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """
        hard_error en el primer Gemini → no prueba el segundo; cae a Ollama.
        """
        from servicio_tecnico.ollama_client import mejorar_diagnostico_dispatch

        mock_gemini.return_value = {
            'success': False,
            'error': 'API key inválida',
            'error_type': 'hard_error',
        }
        mock_ollama.return_value = {
            'success': True,
            'diagnostico_mejorado': 'Texto de Ollama.',
            'modelo_usado': 'modelo-ollama-local',
        }

        resultado = mejorar_diagnostico_dispatch(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(resultado['modelo_usado'], 'modelo-ollama-local')
        # Solo un intento Gemini (rompió el ciclo) + fallback Ollama
        self.assertEqual(mock_gemini.call_count, 1)
        mock_ollama.assert_called_once()

    @patch('servicio_tecnico.ollama_client.mejorar_diagnostico')
    @patch('servicio_tecnico.gemini_client.mejorar_diagnostico')
    def test_todos_gemini_fallan_cae_a_ollama(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """
        Todos los Gemini con error recuperable → se agotan → Ollama.
        """
        from servicio_tecnico.ollama_client import mejorar_diagnostico_dispatch

        mock_gemini.side_effect = [
            {'success': False, 'error': 'timeout 1', 'error_type': 'timeout'},
            {'success': False, 'error': 'timeout 2', 'error_type': 'timeout'},
        ]
        mock_ollama.return_value = {
            'success': True,
            'diagnostico_mejorado': 'Rescate Ollama.',
            'modelo_usado': 'modelo-ollama-local',
        }

        resultado = mejorar_diagnostico_dispatch(**self._kwargs())

        self.assertTrue(resultado['success'])
        self.assertEqual(mock_gemini.call_count, 2)
        mock_ollama.assert_called_once()

    @patch('servicio_tecnico.ollama_client.mejorar_diagnostico')
    @patch('servicio_tecnico.gemini_client.mejorar_diagnostico')
    def test_todo_falla_devuelve_error(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Si Gemini y Ollama fallan, success=False con mensaje claro."""
        from servicio_tecnico.ollama_client import mejorar_diagnostico_dispatch

        mock_gemini.side_effect = [
            {'success': False, 'error': 'fallo g1', 'error_type': 'server_error'},
            {'success': False, 'error': 'fallo g2', 'error_type': 'server_error'},
        ]
        mock_ollama.return_value = {
            'success': False,
            'error': 'Ollama no disponible',
        }

        resultado = mejorar_diagnostico_dispatch(**self._kwargs())

        self.assertFalse(resultado['success'])
        self.assertIn('Ollama', resultado.get('error', ''))

    @patch('servicio_tecnico.ollama_client.mejorar_diagnostico')
    @patch('servicio_tecnico.gemini_client.mejorar_diagnostico')
    def test_override_ollama_sin_cascada_gemini(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        """Override Ollama explícito: no debe tocar Gemini."""
        from servicio_tecnico.ollama_client import mejorar_diagnostico_dispatch

        mock_ollama.return_value = {
            'success': True,
            'diagnostico_mejorado': 'Solo Ollama.',
            'modelo_usado': 'gemma-local',
        }

        kwargs = self._kwargs()
        kwargs['modelo_override'] = '[Ollama] gemma-local'
        resultado = mejorar_diagnostico_dispatch(**kwargs)

        self.assertTrue(resultado['success'])
        mock_gemini.assert_not_called()
        mock_ollama.assert_called_once()
        # Debe pasar el nombre limpio sin prefijo
        self.assertEqual(
            mock_ollama.call_args.kwargs.get('modelo_override'),
            'gemma-local',
        )
