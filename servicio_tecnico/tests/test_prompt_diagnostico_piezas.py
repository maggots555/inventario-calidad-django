"""
Tests del contrato de formato en el prompt de pulido de diagnóstico.

EXPLICACIÓN PARA PRINCIPIANTES:
La IA no debe reescribir el bloque de piezas (encabezados + NOMBRE: DPN),
porque el detector del modal (TypeScript) depende de ese formato.
Estos tests verifican que construir_prompt() incluye esas reglas;
NO llaman a Gemini/Ollama de verdad.
"""

from django.test import SimpleTestCase

from servicio_tecnico.ollama_client import construir_prompt


class PromptDiagnosticoPreservaPiezasTests(SimpleTestCase):
    """
    Objetivo: asegurar que el prompt instruye preservar el bloque de piezas
    y no renombrar componentes (conflicto histórico regla 5 vs regla 7).
    """

    def test_prompt_incluye_contrato_bloque_piezas(self) -> None:
        """
        El prompt debe hablar del bloque de piezas y del formato canónico.
        """
        prompt = construir_prompt(
            diagnostico_sic=(
                'Equipo no carga. '
                'PIEZAS NECESARIAS Y/O PRIORITARIAS.- DCIN: 7XC17, MOBO: 0XPJWG'
            ),
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
        )

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Buscamos frases clave del contrato. Si alguien borra las reglas
        # del prompt, este test falla y avisamos a tiempo.
        self.assertIn('BLOQUE DE PIEZAS', prompt)
        self.assertIn('NOMBRE: CODIGO', prompt)
        self.assertIn('PIEZAS NECESARIAS Y/O PRIORITARIAS', prompt)
        self.assertIn('NUNCA alteres números de parte', prompt)

    def test_prompt_prohibe_renombrar_componentes(self) -> None:
        """
        Ya no debe pedir normalizar coloquialismos de forma positiva
        (eso rompía el detector de piezas); debe prohibir renombrar.
        """
        prompt = construir_prompt(
            diagnostico_sic='Se reviso placa y cargador del equipo portatil.',
        )

        self.assertIn('NO lo renombres', prompt)
        self.assertIn('NUNCA renombres piezas', prompt)
        # Debe aparecer como PROHIBICIÓN, no como instrucción de normalizar
        self.assertIn('NO hagas "placa"→"tarjeta madre"', prompt)
        # La redacción antigua (imperativo de normalizar) no debe volver
        self.assertNotIn(
            'Usa terminología técnica estándar donde el técnico usó términos coloquiales',
            prompt,
        )
