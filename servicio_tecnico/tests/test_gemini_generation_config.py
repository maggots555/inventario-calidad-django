"""
Tests de humo — generationConfig dual Gemini 2.5 vs 3.6+ / 3.5 Flash-Lite.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No llamamos a la API real de Google (no gasta free tier ni necesita API key).
Solo verificamos que el helper arma el JSON correcto según el modelo:

- Modelos nuevos (3.8/3.7/3.6-flash, 3.5-flash-lite): SIN temperature/topP;
  thinking con thinkingLevel.
- 3.7 y 3.8 no aceptan thinkingLevel=minimal: se reescribe a low.
- Modelos 2.5: CON temperature/topP y thinkingBudget (comportamiento previo).
"""

from django.test import SimpleTestCase, override_settings

from servicio_tecnico.gemini_client import (
    GEMINI_MODEL_DEFAULT,
    construir_generation_config,
    usa_api_gemini_sin_sampling,
)


class UsaApiGeminiSinSamplingTest(SimpleTestCase):
    """
    Detecta qué modelos usan la API nueva (jul 2026+).

    Objetivo: no mandar temperature a 3.8 / 3.7 / 3.6 / 3.5-flash-lite.
    """

    def test_detecta_modelos_nuevos(self):
        """3.8, 3.7, 3.6 y 3.5-flash-lite (y prefijo UI) activan la rama nueva."""
        self.assertTrue(usa_api_gemini_sin_sampling('gemini-3.8-flash'))
        self.assertTrue(usa_api_gemini_sin_sampling('gemini-3.7-flash'))
        self.assertTrue(usa_api_gemini_sin_sampling('gemini-3.6-flash'))
        self.assertTrue(usa_api_gemini_sin_sampling('gemini-3.5-flash-lite'))
        self.assertTrue(usa_api_gemini_sin_sampling('[Gemini] gemini-3.8-flash'))
        self.assertTrue(usa_api_gemini_sin_sampling('[Gemini] gemini-3.6-flash'))

    def test_no_confunde_2_5_ni_3_5_flash_completo(self):
        """2.5 y gemini-3.5-flash (sin -lite) siguen en rama clásica."""
        self.assertFalse(usa_api_gemini_sin_sampling('gemini-2.5-flash'))
        self.assertFalse(usa_api_gemini_sin_sampling('gemini-2.5-flash-lite'))
        self.assertFalse(usa_api_gemini_sin_sampling('gemini-3.5-flash'))
        self.assertFalse(usa_api_gemini_sin_sampling('gemini-2.0-flash'))


class ConstruirGenerationConfigTest(SimpleTestCase):
    """
    Verifica el dict generationConfig para cada familia de modelos.
    """

    def test_modelo_nuevo_sin_sampling_con_thinking_level(self):
        """3.6: maxOutputTokens + thinkingLevel; sin temperature/topP."""
        cfg = construir_generation_config(
            'gemini-3.6-flash',
            max_output_tokens=8192,
            temperature=0.3,
            top_p=0.9,
            thinking_budget=0,
            thinking_level='medium',
        )
        self.assertEqual(cfg['maxOutputTokens'], 8192)
        self.assertEqual(cfg['thinkingConfig'], {'thinkingLevel': 'medium'})
        self.assertNotIn('temperature', cfg)
        self.assertNotIn('topP', cfg)
        self.assertNotIn('thinkingBudget', cfg.get('thinkingConfig', {}))

    def test_default_thinking_level_es_medium(self):
        """Si el caller no pasa thinking_level, 3.x usa medium (soportado en toda la cascada 3.x)."""
        cfg = construir_generation_config(
            'gemini-3.8-flash',
            max_output_tokens=1024,
        )
        self.assertEqual(cfg['thinkingConfig']['thinkingLevel'], 'medium')
        cfg_lite = construir_generation_config(
            'gemini-3.5-flash-lite',
            max_output_tokens=1024,
        )
        self.assertEqual(cfg_lite['thinkingConfig']['thinkingLevel'], 'medium')

    def test_flash_lite_nuevo_minimal(self):
        """3.5-flash-lite sigue aceptando minimal si alguien lo pide (red de seguridad)."""
        cfg = construir_generation_config(
            'gemini-3.5-flash-lite',
            max_output_tokens=1024,
            thinking_level='minimal',
            response_mime_type='application/json',
        )
        self.assertEqual(cfg['thinkingConfig']['thinkingLevel'], 'minimal')
        self.assertEqual(cfg['responseMimeType'], 'application/json')
        self.assertNotIn('temperature', cfg)

    def test_38_flash_minimal_se_reescribe_a_low(self):
        """3.8 Flash no acepta minimal: el helper envía low (evita HTTP 400)."""
        cfg = construir_generation_config(
            'gemini-3.8-flash',
            max_output_tokens=8192,
            temperature=0.3,
            top_p=0.9,
            thinking_level='minimal',
        )
        self.assertEqual(cfg['thinkingConfig']['thinkingLevel'], 'low')
        self.assertNotIn('temperature', cfg)
        self.assertNotIn('topP', cfg)

    def test_37_flash_minimal_se_reescribe_a_low(self):
        """3.7 Flash tampoco acepta minimal: mismo remap a low."""
        cfg = construir_generation_config(
            'gemini-3.7-flash',
            max_output_tokens=2048,
            thinking_level='minimal',
        )
        self.assertEqual(cfg['thinkingConfig']['thinkingLevel'], 'low')
        self.assertNotIn('temperature', cfg)

    def test_38_flash_medium_se_conserva(self):
        """Callers piden medium: 3.8 no debe degradarlo a low."""
        cfg = construir_generation_config(
            'gemini-3.8-flash',
            max_output_tokens=3072,
            thinking_level='medium',
        )
        self.assertEqual(cfg['thinkingConfig']['thinkingLevel'], 'medium')

    def test_36_flash_minimal_se_conserva(self):
        """3.6 sí soporta minimal: no reescribir (solo 3.7/3.8 lo rechazan)."""
        cfg = construir_generation_config(
            'gemini-3.6-flash',
            max_output_tokens=8192,
            thinking_level='minimal',
        )
        self.assertEqual(cfg['thinkingConfig']['thinkingLevel'], 'minimal')

    def test_modelo_2_5_conserva_temperature_y_budget(self):
        """2.5-flash: temperature + topP + thinkingBudget (API clásica)."""
        cfg = construir_generation_config(
            'gemini-2.5-flash',
            max_output_tokens=2048,
            temperature=0.15,
            top_p=0.9,
            thinking_budget=-1,
            thinking_level='medium',  # se ignora en rama 2.5
        )
        self.assertEqual(cfg['temperature'], 0.15)
        self.assertEqual(cfg['topP'], 0.9)
        self.assertEqual(cfg['maxOutputTokens'], 2048)
        self.assertEqual(cfg['thinkingConfig'], {'thinkingBudget': -1})
        self.assertNotIn('thinkingLevel', cfg['thinkingConfig'])

    def test_top_p_none_omite_campo_en_2_5(self):
        """Si top_p=None en 2.5, no se incluye topP (transcripción/cita)."""
        cfg = construir_generation_config(
            'gemini-2.5-flash-lite',
            max_output_tokens=150,
            temperature=0.9,
            top_p=None,
            thinking_budget=0,
        )
        self.assertEqual(cfg['temperature'], 0.9)
        self.assertNotIn('topP', cfg)


@override_settings(
    GEMINI_MODEL='gemini-3.8-flash',
    GEMINI_MODELS=[
        'gemini-3.8-flash',
        'gemini-3.7-flash',
        'gemini-3.6-flash',
        'gemini-3.5-flash-lite',
        'gemini-2.5-flash',
        'gemini-2.5-flash-lite',
    ],
)
class DefaultsGeminiConfigTest(SimpleTestCase):
    """
    Humo de defaults alineados con .env.example (sep 2026).
    """

    def test_default_constante_y_settings(self):
        """Default canónico del módulo y settings de prueba coinciden."""
        from django.conf import settings

        self.assertEqual(GEMINI_MODEL_DEFAULT, 'gemini-3.8-flash')
        self.assertEqual(settings.GEMINI_MODEL, 'gemini-3.8-flash')
        self.assertEqual(settings.GEMINI_MODELS[0], 'gemini-3.8-flash')
        self.assertEqual(settings.GEMINI_MODELS[1], 'gemini-3.7-flash')
        self.assertIn('gemini-3.6-flash', settings.GEMINI_MODELS)
        self.assertIn('gemini-3.5-flash-lite', settings.GEMINI_MODELS)
        # Previews viejos ya no deben estar en la cascada recomendada
        self.assertNotIn('gemini-3-flash-preview', settings.GEMINI_MODELS)
        self.assertNotIn('gemini-3.1-flash-lite-preview', settings.GEMINI_MODELS)
        self.assertNotIn('gemini-3.8-flash-cyber', settings.GEMINI_MODELS)
