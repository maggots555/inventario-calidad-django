"""
Tests del PDF RHITSO (Platypus, estilo OOW / Venta mostrador).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No enviamos correo ni tocamos la BD. Armamos una orden de mentira
(SimpleNamespace) y pedimos a PDFGeneratorRhitso que escriba un PDF
en un MEDIA_ROOT temporal.

Así comprobamos:
1. Que el archivo nace bien (%PDF, tamaño, ruta).
2. Que un motivo largo ya no truena (Paragraph envuelve solo).
3. Que sin detalle/cargador los fallbacks no rompen la generación.
"""

import tempfile
from types import SimpleNamespace

from django.contrib.staticfiles import finders
from django.test import SimpleTestCase, override_settings
from reportlab.platypus import Image as RLImage, Table

from servicio_tecnico.utils.pdf_generator import PDFGeneratorRhitso


def _orden_completa(**overrides):
    """
    Orden + detalle mínimos como los que usa el generador.

    Args:
        **overrides: atributos extra sobre la orden (ej. descripcion_rhitso).

    Returns:
        SimpleNamespace listo para PDFGeneratorRhitso.
    """
    detalle = SimpleNamespace(
        orden_cliente='OOW-09647',
        modelo='Inspiron 15 3535',
        numero_serie='SN-RHITSO-01',
        tiene_cargador=True,
        numero_serie_cargador='CHG-001',
    )
    orden = SimpleNamespace(
        id=2048,
        numero_orden_interno='INT-2048',
        descripcion_rhitso='Falla de motherboard. Se solicita envío a RHITSO.',
        detalle_equipo=detalle,
    )
    for clave, valor in overrides.items():
        setattr(orden, clave, valor)
    return orden


class PdfRhitsoPlatypusTest(SimpleTestCase):
    """Generación real del PDF sin BD ni correo."""

    def _generar(self, orden, imagenes=None):
        """
        Llama a generar_pdf() con MEDIA_ROOT temporal.

        Returns:
            dict: resultado del generador.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                generador = PDFGeneratorRhitso(orden, imagenes_autorizacion=imagenes or [])
                resultado = generador.generar_pdf()
                # Copiamos bytes antes de que el tmp se borre, para aserciones.
                if resultado.get('success') and resultado.get('ruta'):
                    with open(resultado['ruta'], 'rb') as archivo:
                        resultado['_bytes'] = archivo.read()
                return resultado

    def test_feliz_genera_pdf_con_ruta_y_cabecera(self):
        """Feliz: success, archivo en ruta, magic %PDF y tamaño > 100."""
        resultado = self._generar(_orden_completa())

        self.assertTrue(resultado['success'], resultado.get('error'))
        self.assertTrue(resultado['archivo'].startswith('RHITSO_'))
        self.assertTrue(resultado['archivo'].endswith('.pdf'))
        self.assertGreater(resultado['size'], 100)
        self.assertTrue(resultado['_bytes'].startswith(b'%PDF'))
        self.assertIn('SN-RHITSO-01', resultado['archivo'])

    def test_motivo_largo_genera_sin_error(self):
        """
        Borde: párrafo largo (el que antes tapaba ACCESORIOS).
        Platypus envuelve; el PDF debe nacer igual.
        """
        motivo_largo = (
            'Se realiza diagnostico a equipo, se observa que el LED de Caps Lock '
            'parpadea 3 veces y se queda prendido, se verifica que el SSD de 512 GB '
            'es reconocido en BIOS y se intenta arrancar, sin embargo el equipo no '
            'pasa de la pantalla de logo. Se determina falla en motherboard y se '
            'solicita envio a RHITSO para diagnostico y cotizacion de reparacion. '
            'El cliente autoriza el envio y se adjuntan fotografias de ingreso.'
        )
        resultado = self._generar(_orden_completa(descripcion_rhitso=motivo_largo))

        self.assertTrue(resultado['success'], resultado.get('error'))
        self.assertGreater(resultado['size'], 100)
        self.assertTrue(resultado['_bytes'].startswith(b'%PDF'))

    def test_sin_detalle_ni_cargador_no_rompe(self):
        """Borde: sin detalle → N/A / SIN CARGADOR; el PDF igual se genera."""
        orden = SimpleNamespace(
            id=99,
            numero_orden_interno='INT-99',
            descripcion_rhitso='',
            detalle_equipo=None,
        )
        resultado = self._generar(orden)

        self.assertTrue(resultado['success'], resultado.get('error'))
        self.assertTrue(resultado['_bytes'].startswith(b'%PDF'))
        self.assertGreater(resultado['size'], 100)
        self.assertIn('INT-99', resultado['archivo'])

    def test_header_incluye_logo_rhitso_a_la_derecha(self):
        """
        El encabezado es SIC | empresa | RHITSO, como el formato original.
        Si el PNG no está en static, la celda derecha queda vacía (fail-safe).
        """
        generador = PDFGeneratorRhitso(_orden_completa())
        header = generador._construir_header()
        tabla = header[0]
        self.assertIsInstance(tabla, Table)
        self.assertEqual(len(tabla._cellvalues[0]), 3)

        celda_derecha = tabla._cellvalues[0][2]
        ruta_rhitso = finders.find('images/logos/logo_rhitso.png')
        if ruta_rhitso:
            self.assertIsInstance(celda_derecha, RLImage)
        else:
            self.assertEqual(celda_derecha, '')
