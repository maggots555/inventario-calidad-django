"""
Tests de los plazos del proceso en el chat de seguimiento.

EXPLICACIÓN PARA PRINCIPIANTES:
El asistente solo sabe lo que va escrito en su prompt. Estos tests
comprueban dos cosas, sin llamar a la IA:

1. El prompt siempre incluye los rangos oficiales (diagnóstico, cotización,
   reparación y recolección).
2. Python decide si la cotización de esta orden sigue vigente.
   El día hábil 5 todavía vale; el 6 ya pide recotización.
"""

from datetime import datetime

from django.test import SimpleTestCase

from servicio_tecnico.chat_seguimiento_helpers import texto_vigencia_cotizacion_chat
from servicio_tecnico.ollama_client import construir_prompt_seguimiento


def _mensajes_minimos() -> list[dict]:
    """Arma un prompt con datos de relleno. No toca la base de datos."""
    return construir_prompt_seguimiento(
        pregunta='¿Cuánto tarda el diagnóstico?',
        folio='OOW-1',
        tipo_equipo='Laptop',
        marca='Dell',
        modelo_equipo='Inspiron',
        numero_serie='ABC',
        falla_principal='No enciende',
        diagnostico_sic='Pendiente',
        estado_actual='En diagnóstico',
        timeline_texto='  Sin registros aún',
        nombre_responsable='Ana',
        piezas_texto='',
        historial_mensajes=[],
    )


class PromptPlazosProcesoTests(SimpleTestCase):
    """
    Objetivo: el system prompt lleva la política de plazos de SIC.

    No llama a Ollama ni a Gemini.
    """

    def test_prompt_incluye_rangos_oficiales(self) -> None:
        """
        Feliz: diagnóstico, cotización, vigencia, reparación y recolección
        aparecen en el mensaje de sistema.
        """
        mensajes = _mensajes_minimos()
        sistema = mensajes[0]['content']

        self.assertIn('1 a 5 días hábiles', sistema)
        self.assertIn('1 a 6 días hábiles', sistema)
        self.assertIn('5 días hábiles desde que se compartió', sistema)
        self.assertIn('1 a 3 días hábiles', sistema)
        self.assertIn('responsable de seguimiento haya confirmado que está listo', sistema)
        # La regla le prohíbe mezclar la vigencia de la cotización con la del enlace.
        self.assertIn('no del enlace de seguimiento', sistema)


class VigenciaCotizacionChatTests(SimpleTestCase):
    """
    Objetivo: la vigencia se cuenta en días hábiles, sin contar el día de envío.

    Lunes 5 de octubre de 2026 es el día de envío.
    El lunes 12 son 5 días hábiles transcurridos (sigue vigente).
    El martes 13 es el sexto (ya pide recotización).
    """

    def test_dia_5_sigue_vigente(self) -> None:
        """Borde: exactamente 5 días hábiles todavía no vencen la cotización."""
        texto = texto_vigencia_cotizacion_chat(
            datetime(2026, 10, 5),
            None,
            ahora=datetime(2026, 10, 12),
        )
        self.assertIn('vigente', texto)
        self.assertNotIn('recotización', texto)

    def test_dia_6_pide_recotizacion(self) -> None:
        """Borde: el sexto día hábil ya pide recotización."""
        texto = texto_vigencia_cotizacion_chat(
            datetime(2026, 10, 5),
            None,
            ahora=datetime(2026, 10, 13),
        )
        self.assertIn('vencida', texto)
        self.assertIn('recotización', texto)

    def test_cotizacion_ya_respondida_no_pide_recotizacion(self) -> None:
        """Borde: si el cliente ya aceptó o rechazó, no se habla de vigencia."""
        aceptada = texto_vigencia_cotizacion_chat(
            datetime(2026, 10, 5),
            True,
            ahora=datetime(2026, 10, 20),
        )
        rechazada = texto_vigencia_cotizacion_chat(
            datetime(2026, 10, 5),
            False,
            ahora=datetime(2026, 10, 20),
        )
        self.assertEqual(aceptada, '')
        self.assertEqual(rechazada, '')

    def test_sin_fecha_no_adivina(self) -> None:
        """Borde: sin fecha de envío no se inventa si ya venció."""
        texto = texto_vigencia_cotizacion_chat(None, None, ahora=datetime(2026, 10, 13))
        self.assertEqual(texto, '')
