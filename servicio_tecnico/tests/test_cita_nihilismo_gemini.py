"""
Tests — cita diaria Gemini: tope de tokens, thinking y MAX_TOKENS.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No llamamos a Google. Mockeamos urlopen para verificar tres reglas que
rompieron la cita el 10-sep-2026 (logs: 15 chars + finishReason=MAX_TOKENS):

1. El payload pide 1024 tokens y thinking minimal/low (no 150 + medium).
2. Si Gemini corta (MAX_TOKENS), fallamos para que la cascada siga.
3. Si hay una part de thought y otra de texto, usamos solo el texto visible.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from servicio_tecnico.gemini_client import (
    CITA_MAX_OUTPUT_TOKENS,
    texto_visible_parts_gemini,
)


def _respuesta_gemini_mock(texto: str, finish_reason: str = 'STOP', parts=None):
    """
    Arma el JSON mínimo que devuelve generateContent.

    Args:
        texto: Texto visible si no se pasan parts a mano.
        finish_reason: STOP (completo) o MAX_TOKENS (cortado).
        parts: Lista opcional de parts (para simular thought + cita).
    """
    if parts is None:
        parts = [{'text': texto}]
    return {
        'candidates': [
            {
                'finishReason': finish_reason,
                'content': {'parts': parts},
            }
        ],
    }


def _instalar_urlopen_mock(mock_urlopen: MagicMock, respuesta: dict) -> None:
    """
    Configura urlopen como context manager que devuelve el JSON dado.

    Efectos secundarios: muta mock_urlopen (return_value + read).
    """
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(respuesta).encode('utf-8')
    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False
    mock_urlopen.return_value = mock_resp


class TextoVisiblePartsGeminiTests(SimpleTestCase):
    """El helper no debe mostrar el thinking interno de Gemini 3.x."""

    def test_omite_part_thought_y_junta_texto(self) -> None:
        """parts[0] thought + parts[1] cita → solo la cita."""
        cita = texto_visible_parts_gemini(
            [
                {'thought': True, 'text': 'voy a escribir una frase corta'},
                {'text': 'Pinta sobre el silencio y elige tu propio sentido.'},
            ]
        )
        self.assertEqual(
            cita,
            'Pinta sobre el silencio y elige tu propio sentido.',
        )

    def test_lista_vacia_o_none(self) -> None:
        """Sin parts no debe romper: cadena vacía."""
        self.assertEqual(texto_visible_parts_gemini(None), '')
        self.assertEqual(texto_visible_parts_gemini([]), '')


@override_settings(
    GEMINI_ENABLED=True,
    GEMINI_API_KEY='fake-key-test',
    GEMINI_TIMEOUT=5,
    GEMINI_MODEL='gemini-3.8-flash',
)
class GenerarCitaNihilismoGeminiTests(SimpleTestCase):
    """
    Reglas del generador de cita tras el recorte de sep 2026.
    """

    @patch('servicio_tecnico.gemini_client.urllib.request.urlopen')
    def test_payload_38_usa_1024_y_thinking_low(self, mock_urlopen: MagicMock) -> None:
        """
        3.8 no acepta minimal: el helper lo reescribe a low.
        El tope debe ser 1024, no 150.
        """
        _instalar_urlopen_mock(
            mock_urlopen,
            _respuesta_gemini_mock(
                'La hoja en blanco no asusta: es el privilegio de decidir.'
            ),
        )
        from servicio_tecnico.gemini_client import generar_cita_nihilismo_gemini

        resultado = generar_cita_nihilismo_gemini(
            modelo_override='gemini-3.8-flash',
        )
        self.assertTrue(resultado['success'], msg=resultado.get('error'))

        request_obj = mock_urlopen.call_args[0][0]
        payload = json.loads(request_obj.data.decode('utf-8'))
        cfg = payload['generationConfig']
        self.assertEqual(cfg['maxOutputTokens'], CITA_MAX_OUTPUT_TOKENS)
        self.assertEqual(CITA_MAX_OUTPUT_TOKENS, 1024)
        self.assertEqual(cfg['thinkingConfig']['thinkingLevel'], 'low')
        self.assertNotIn('temperature', cfg)

    @patch('servicio_tecnico.gemini_client.urllib.request.urlopen')
    def test_payload_36_conserva_minimal(self, mock_urlopen: MagicMock) -> None:
        """3.6 sí acepta thinkingLevel=minimal."""
        _instalar_urlopen_mock(
            mock_urlopen,
            _respuesta_gemini_mock(
                'Vivir sin guión cósmico es poder escribir el tuyo.'
            ),
        )
        from servicio_tecnico.gemini_client import generar_cita_nihilismo_gemini

        resultado = generar_cita_nihilismo_gemini(
            modelo_override='gemini-3.6-flash',
        )
        self.assertTrue(resultado['success'], msg=resultado.get('error'))

        request_obj = mock_urlopen.call_args[0][0]
        payload = json.loads(request_obj.data.decode('utf-8'))
        cfg = payload['generationConfig']
        self.assertEqual(cfg['maxOutputTokens'], 1024)
        self.assertEqual(cfg['thinkingConfig']['thinkingLevel'], 'minimal')

    @patch('servicio_tecnico.gemini_client.urllib.request.urlopen')
    def test_max_tokens_falla_y_no_acepta_recorte(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        """
        Replica el log de prod: 15 chars + MAX_TOKENS → success=False.
        Así el dispatcher no cachea "Pinta sobre el silencio".
        """
        _instalar_urlopen_mock(
            mock_urlopen,
            _respuesta_gemini_mock(
                'Pinta sobre el',
                finish_reason='MAX_TOKENS',
            ),
        )
        from servicio_tecnico.gemini_client import generar_cita_nihilismo_gemini

        resultado = generar_cita_nihilismo_gemini(
            modelo_override='gemini-3.7-flash',
        )
        self.assertFalse(resultado['success'])
        self.assertEqual(resultado.get('error_type'), 'server_error')
        self.assertIn('MAX_TOKENS', resultado.get('error', ''))
        self.assertNotIn('cita', resultado)

    @patch('servicio_tecnico.gemini_client.urllib.request.urlopen')
    def test_stop_acepta_cita_completa(self, mock_urlopen: MagicMock) -> None:
        """STOP + 2 oraciones → se acepta (camino feliz)."""
        cita = (
            'No hay manual en el cosmos. Eso no es un vacío: es permiso '
            'para inventar lo que hoy te importa.'
        )
        _instalar_urlopen_mock(
            mock_urlopen,
            _respuesta_gemini_mock(cita),
        )
        from servicio_tecnico.gemini_client import generar_cita_nihilismo_gemini

        resultado = generar_cita_nihilismo_gemini(
            modelo_override='gemini-3.8-flash',
        )
        self.assertTrue(resultado['success'], msg=resultado.get('error'))
        self.assertEqual(resultado['cita'], cita)
        self.assertEqual(resultado['modelo_usado'], 'gemini-3.8-flash')

    @patch('servicio_tecnico.gemini_client.urllib.request.urlopen')
    def test_extrae_texto_si_primera_part_es_thought(
        self,
        mock_urlopen: MagicMock,
    ) -> None:
        """
        3.8 a veces manda thought en parts[0] y la cita en parts[1].
        Antes leíamos solo parts[0] y el log decía "Texto extraído vacío".
        """
        cita = 'El silencio no pide permiso: tú le das sentido.'
        _instalar_urlopen_mock(
            mock_urlopen,
            _respuesta_gemini_mock(
                '',
                parts=[
                    {'thought': True, 'text': 'razono una cita breve'},
                    {'text': cita},
                ],
            ),
        )
        from servicio_tecnico.gemini_client import generar_cita_nihilismo_gemini

        resultado = generar_cita_nihilismo_gemini(
            modelo_override='gemini-3.8-flash',
        )
        self.assertTrue(resultado['success'], msg=resultado.get('error'))
        self.assertEqual(resultado['cita'], cita)
