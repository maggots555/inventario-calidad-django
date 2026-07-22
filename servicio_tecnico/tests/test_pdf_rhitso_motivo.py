"""
Tests del layout del bloque MOTIVO en el PDF RHITSO.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Antes, la caja de MOTIVO medía siempre 70 puntos. Si el diagnóstico era largo,
el texto se salía y tapaba ACCESORIOS ENVIADOS.

Estos tests verifican:
1. Que el texto largo se parte en varias líneas (wrap por ancho).
2. Que la altura de la caja crece cuando hay muchas líneas.
3. Que un texto corto sigue respetando el mínimo de 70 pt.
"""

from django.test import SimpleTestCase

from servicio_tecnico.utils.pdf_generator import PDFGeneratorRhitso


class PdfRhitsoMotivoLayoutTest(SimpleTestCase):
    """
    Pruebas unitarias del wrap y la altura dinámica de MOTIVO.

    No tocan la base de datos: solo llaman helpers estáticos del generador.
    """

    def test_texto_corto_una_linea_y_altura_minima(self):
        """
        Caso feliz: un motivo breve cabe en una línea y la caja no baja de 70 pt.
        """
        # Ancho amplio (como el útil del PDF menos márgenes internos).
        ancho_maximo = 500.0
        lineas = PDFGeneratorRhitso._partir_texto_en_lineas(
            'Falla de motherboard',
            ancho_maximo,
            'Helvetica',
            9,
        )

        self.assertEqual(len(lineas), 1)
        self.assertEqual(lineas[0], 'Falla de motherboard')

        alto = PDFGeneratorRhitso._calcular_alto_contenido_motivo(len(lineas))
        # EXPLICACIÓN: aunque quepa en 1 línea, el diseño pide mínimo 70 pt.
        self.assertEqual(alto, 70)

    def test_texto_largo_varias_lineas_y_altura_crece(self):
        """
        Caso borde: párrafo largo → varias líneas y altura mayor a 70 pt.
        """
        # Mismo texto problemático reportado en producción (aprox.).
        motivo_largo = (
            'Se realiza diagnostico a equipo, se observa que el LED de Caps Lock '
            'parpadea 3 veces y se queda prendido, se verifica que el SSD de 512 GB '
            'es reconocido en BIOS y se intenta arrancar, sin embargo el equipo no '
            'pasa de la pantalla de logo. Se determina falla en motherboard y se '
            'solicita envio a RHITSO para diagnostico y cotizacion de reparacion.'
        )
        # Ancho estrecho a propósito para forzar varias líneas (como en el PDF).
        ancho_maximo = 200.0
        lineas = PDFGeneratorRhitso._partir_texto_en_lineas(
            motivo_largo,
            ancho_maximo,
            'Helvetica',
            9,
        )

        self.assertGreater(len(lineas), 1)
        # Ninguna línea debe exceder el ancho máximo medido.
        from reportlab.pdfbase.pdfmetrics import stringWidth

        for linea in lineas:
            self.assertLessEqual(
                stringWidth(linea, 'Helvetica', 9),
                ancho_maximo,
            )

        alto = PDFGeneratorRhitso._calcular_alto_contenido_motivo(len(lineas))
        # padding 20 + N*12 debe superar el mínimo histórico.
        self.assertGreater(alto, 70)
        self.assertEqual(alto, 20 + (len(lineas) * 12))
