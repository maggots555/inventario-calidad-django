"""
Tests — el analizador de sentimiento Ollama envía num_ctx alineado.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No llamamos a Ollama real. Interceptamos urllib.request.urlopen y revisamos
el JSON del payload: debe incluir options.num_ctx = CHAT_SEGUIMIENTO_NUM_CTX
(igual que chat de seguimiento y pulir diagnóstico).
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings


# Encuesta mínima válida para armar el prompt sin depender de la BD.
_ENCUESTA_MINIMA = {
    'calificacion_general': 5,
    'calificacion_atencion': 5,
    'calificacion_tiempo': 4,
    'nps': 9,
    'recomienda': True,
    'comentario': 'Buen servicio, muy atentos.',
}


class AnalizarSentimientoNumCtxTest(SimpleTestCase):
    """
    Verifica que analizar_sentimiento_encuestas manda num_ctx a Ollama.

    Objetivo de negocio: misma ventana de contexto que chat/diagnóstico
    para no truncar prompts largos ni forzar reload del modelo.
    """

    @override_settings(
        OLLAMA_ENABLED=True,
        OLLAMA_BASE_URL='http://localhost:11434',
        OLLAMA_TIMEOUT=30,
        CHAT_SEGUIMIENTO_NUM_CTX=8192,
    )
    @patch('servicio_tecnico.ollama_client.urllib.request.urlopen')
    def test_payload_incluye_num_ctx_8192(self, mock_urlopen: MagicMock) -> None:
        """
        El body POST a /api/chat debe llevar options.num_ctx = 8192.
        """
        # Respuesta falsa de Ollama con JSON de análisis válido.
        respuesta_ia = {
            'message': {
                'content': json.dumps({
                    'sentimiento_general': 'positivo',
                    'resumen_ejecutivo': 'Clientes satisfechos.',
                    'temas_positivos': ['atención'],
                    'temas_negativos': [],
                    'recomendacion_ia': 'Mantener el nivel de servicio.',
                }),
            },
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(respuesta_ia).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_urlopen.return_value = mock_resp

        from servicio_tecnico.ollama_client import analizar_sentimiento_encuestas

        resultado = analizar_sentimiento_encuestas(
            encuestas=[_ENCUESTA_MINIMA],
            modelo='gemma3:12b',
        )

        self.assertTrue(resultado['success'], msg=resultado.get('error'))

        # El Request de urllib lleva el payload en .data (bytes JSON).
        request_obj = mock_urlopen.call_args[0][0]
        payload = json.loads(request_obj.data.decode('utf-8'))

        self.assertEqual(payload['options']['num_ctx'], 8192)
        self.assertEqual(payload['options']['temperature'], 0.2)
        self.assertEqual(payload['options']['num_predict'], 600)
        self.assertEqual(payload['format'], 'json')

    @override_settings(
        OLLAMA_ENABLED=True,
        OLLAMA_BASE_URL='http://localhost:11434',
        OLLAMA_TIMEOUT=30,
        CHAT_SEGUIMIENTO_NUM_CTX=4096,
    )
    @patch('servicio_tecnico.ollama_client.urllib.request.urlopen')
    def test_respeta_num_ctx_desde_settings(self, mock_urlopen: MagicMock) -> None:
        """
        Si CHAT_SEGUIMIENTO_NUM_CTX cambia en settings, el payload lo refleja.
        """
        respuesta_ia = {
            'message': {
                'content': json.dumps({
                    'sentimiento_general': 'neutral',
                    'resumen_ejecutivo': 'Sin comentarios destacables.',
                    'temas_positivos': [],
                    'temas_negativos': [],
                    'recomendacion_ia': 'Seguir monitoreando.',
                }),
            },
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(respuesta_ia).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_urlopen.return_value = mock_resp

        from servicio_tecnico.ollama_client import analizar_sentimiento_encuestas

        resultado = analizar_sentimiento_encuestas(
            encuestas=[_ENCUESTA_MINIMA],
            modelo='gemma3:12b',
        )

        self.assertTrue(resultado['success'], msg=resultado.get('error'))
        request_obj = mock_urlopen.call_args[0][0]
        payload = json.loads(request_obj.data.decode('utf-8'))
        self.assertEqual(payload['options']['num_ctx'], 4096)
