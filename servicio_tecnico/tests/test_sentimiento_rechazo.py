"""
Tests — sentimiento IA: MAX_TOKENS, tipo rechazo, formateo y humo API.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No llamamos a Gemini/Ollama reales. Mockeamos respuestas para verificar:
1. finishReason=MAX_TOKENS → hard_error (cascada puede ir a Ollama)
2. El dispatch propaga tipo='rechazo' a los clientes
3. El formateo de rechazo no incluye NPS/estrellas
4. La URL de análisis de rechazo existe y llama al dispatch con tipo rechazo
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse


# ---------------------------------------------------------------------------
# Helpers de formateo / prompts
# ---------------------------------------------------------------------------


class FormateoSentimientoRechazoTests(SimpleTestCase):
    """El texto del prompt de rechazo usa motivo + comentario, no NPS."""

    def test_formatear_rechazo_sin_nps(self) -> None:
        from servicio_tecnico.ollama_client import _formatear_encuesta

        texto = _formatear_encuesta(
            {'motivo': 'Costo muy elevado', 'comentario': 'Está caro'},
            0,
            tipo='rechazo',
        )
        self.assertIn('Costo muy elevado', texto)
        self.assertIn('Está caro', texto)
        self.assertNotIn('NPS', texto)
        self.assertNotIn('estrellas', texto)

    def test_prompt_rechazo_menciona_cotizacion(self) -> None:
        from servicio_tecnico.ollama_client import _obtener_prompts_sentimiento

        sistema, _usuario = _obtener_prompts_sentimiento('rechazo')
        self.assertIn('cotización', sistema.lower())
        self.assertIn('rechaz', sistema.lower())


# ---------------------------------------------------------------------------
# MAX_TOKENS en Gemini sentimiento
# ---------------------------------------------------------------------------


@override_settings(
    GEMINI_ENABLED=True,
    GEMINI_API_KEY='fake-key-test',
    GEMINI_TIMEOUT=5,
)
class GeminiSentimientoMaxTokensTests(SimpleTestCase):
    """
    Si Gemini corta la respuesta (MAX_TOKENS), debe fallar con hard_error.
    """

    @patch('servicio_tecnico.gemini_client.urllib.request.urlopen')
    def test_max_tokens_devuelve_hard_error(self, mock_urlopen: MagicMock) -> None:
        from servicio_tecnico.gemini_client import analizar_sentimiento_encuestas

        respuesta = {
            'candidates': [
                {
                    'finishReason': 'MAX_TOKENS',
                    'content': {
                        'parts': [{'text': '{"sentimiento_general": "posi'}],
                    },
                },
            ],
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(respuesta).encode('utf-8')
        mock_resp.__enter__.return_value = mock_resp
        mock_resp.__exit__.return_value = False
        mock_urlopen.return_value = mock_resp

        resultado = analizar_sentimiento_encuestas(
            encuestas=[{'comentario': 'ok', 'motivo': 'costo_alto'}],
            modelo='gemini-test',
            tipo='rechazo',
        )

        self.assertFalse(resultado['success'])
        self.assertEqual(resultado.get('error_type'), 'hard_error')
        self.assertIn('tokens', resultado.get('error', '').lower())


# ---------------------------------------------------------------------------
# Dispatch propaga tipo=rechazo
# ---------------------------------------------------------------------------


@override_settings(
    GEMINI_ENABLED=True,
    OLLAMA_ENABLED=True,
    GEMINI_MODELS=['gemini-primero'],
    OLLAMA_MODEL='modelo-ollama-local',
)
class DispatchTipoRechazoTests(SimpleTestCase):
    """El dispatcher debe pasar tipo='rechazo' a Gemini/Ollama."""

    @patch('servicio_tecnico.ollama_client.analizar_sentimiento_encuestas')
    @patch('servicio_tecnico.gemini_client.analizar_sentimiento_encuestas')
    def test_propaga_tipo_rechazo_a_gemini(
        self,
        mock_gemini: MagicMock,
        mock_ollama: MagicMock,
    ) -> None:
        from servicio_tecnico.ollama_client import analizar_sentimiento_dispatch

        mock_gemini.return_value = {
            'success': True,
            'analisis': {
                'sentimiento_general': 'negativo',
                'resumen_ejecutivo': 'Rechazos por precio.',
                'temas_positivos': [],
                'temas_negativos': ['precio'],
                'recomendacion_ia': 'Revisar márgenes.',
            },
            'modelo_usado': 'gemini-primero',
        }

        resultado = analizar_sentimiento_dispatch(
            encuestas=[{'motivo': 'Costo', 'comentario': 'Caro'}],
            modelo_override='',
            tipo='rechazo',
        )

        self.assertTrue(resultado['success'])
        mock_gemini.assert_called_once()
        self.assertEqual(mock_gemini.call_args.kwargs.get('tipo'), 'rechazo')
        mock_ollama.assert_not_called()


# ---------------------------------------------------------------------------
# Humo API rechazo (RequestFactory — evita Axes / ForcePassword middleware)
# ---------------------------------------------------------------------------


@override_settings(AI_ENABLED=True)
class ApiAnalisisSentimientoRechazoHumoTests(TestCase):
    """
    Verifica que el endpoint llama al dispatch con tipo='rechazo'.

    Usa RequestFactory (como test_guardar_diagnostico_sic_ia) para no pelear
    con middleware Axes / cambio de contraseña / multi-tenant HTTP.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        from django.test import RequestFactory

        User = get_user_model()
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            username='tester_rechazo_ia',
            password='testpass123',
        )
        perm = Permission.objects.get(
            codename='view_dashboard_gerencial',
            content_type__app_label='servicio_tecnico',
        )
        self.user.user_permissions.add(perm)

    @patch('servicio_tecnico.ollama_client.analizar_sentimiento_dispatch')
    @patch(
        'servicio_tecnico.views_feedback_rechazo_dash._filtrar_feedback_rechazo',
    )
    def test_api_llama_dispatch_con_tipo_rechazo(
        self,
        mock_filtrar: MagicMock,
        mock_dispatch: MagicMock,
    ) -> None:
        from servicio_tecnico.views_feedback_rechazo_dash import (
            api_analisis_sentimiento_rechazo,
        )

        # QuerySet falso: un feedback respondido con comentario
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.values.return_value = [
            {
                'motivo_rechazo_snapshot': 'costo_alto',
                'comentario_cliente': 'Muy caro para mí',
            },
        ]
        mock_filtrar.return_value = mock_qs

        mock_dispatch.return_value = {
            'success': True,
            'analisis': {
                'sentimiento_general': 'negativo',
                'resumen_ejecutivo': 'Precio elevado.',
                'temas_positivos': [],
                'temas_negativos': ['costo'],
                'recomendacion_ia': 'Ofertas escalonadas.',
            },
            'modelo_usado': 'gemini-mock',
        }

        url = reverse('servicio_tecnico:api_analisis_sentimiento_rechazo')
        request = self.factory.post(
            url,
            data=json.dumps({'forzar': True}),
            content_type='application/json',
        )
        request.user = self.user

        resp = api_analisis_sentimiento_rechazo(request)

        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content.decode('utf-8'))
        self.assertTrue(data['success'])
        mock_dispatch.assert_called_once()
        self.assertEqual(mock_dispatch.call_args.kwargs.get('tipo'), 'rechazo')
