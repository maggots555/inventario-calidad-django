"""
Tests unitarios de las diapositivas Pillow del rewind.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No generamos el MP4 ni llamamos FFmpeg/Celery. Solo comprobamos que
el "pintor" (rewind_slides.py) escribe PNG del tamaño correcto, con
4 tarjetas en diagnóstico / 3 en venta mostrador, y el copy del cierre
que acordamos con el cliente (confianza + siguiente paso).
"""

from __future__ import annotations

import os
import tempfile

from django.test import SimpleTestCase
from PIL import Image

from servicio_tecnico.services.rewind_slides import (
    ALTO,
    ANCHO,
    COLOR_ACENTO,
    TEXTO_CIERRE_KICKER,
    TEXTO_CIERRE_SUBTITULO,
    TEXTO_CIERRE_TITULO,
    TEXTO_SECCIONES,
    TEXTO_SECCIONES_VM,
    generar_slides_rewind,
    lineas_cierre,
)

TIPOS_DIAGNOSTICO = ['ingreso', 'diagnostico', 'reparacion', 'egreso']
TIPOS_VM = ['ingreso', 'reparacion', 'egreso']


def _assert_png_valido(test: SimpleTestCase, ruta: str) -> Image.Image:
    """
    El archivo existe, pesa algo y mide 1280×720.

    Args:
        test: TestCase que hace los assert.
        ruta: PNG generado.

    Returns:
        Imagen abierta (el caller puede muestrear píxeles).
    """
    test.assertTrue(os.path.isfile(ruta), f'No existe {ruta}')
    test.assertGreater(os.path.getsize(ruta), 8_000, f'{ruta} parece vacío')
    img = Image.open(ruta)
    test.assertEqual(img.size, (ANCHO, ALTO), f'{ruta} no es 1280×720')
    return img


class CopyCierreRewindTest(SimpleTestCase):
    """El mensaje final debe transmitir confianza y el siguiente paso."""

    def test_lineas_cierre_acordadas(self):
        """Las 3 líneas públicas coinciden con el copy del plan."""
        kicker, titulo, subtitulo = lineas_cierre()
        self.assertEqual(kicker, 'Gracias por tu confianza')
        self.assertEqual(titulo, 'Tu equipo está listo')
        self.assertEqual(subtitulo, 'Te contactaremos para coordinar la entrega')
        # Las constantes exportadas son las mismas (una sola fuente de verdad).
        self.assertEqual(kicker, TEXTO_CIERRE_KICKER)
        self.assertEqual(titulo, TEXTO_CIERRE_TITULO)
        self.assertEqual(subtitulo, TEXTO_CIERRE_SUBTITULO)


class GenerarSlidesRewindTest(SimpleTestCase):
    """Pintado de PNG: dimensiones, cantidad de tarjetas y look oscuro."""

    def test_diagnostico_genera_intro_4_tarjetas_y_cierre(self):
        """Diagnóstico: intro + 4 secciones + cierre, todos 1280×720."""
        with tempfile.TemporaryDirectory(prefix='rewind_slides_') as tmp:
            slides = generar_slides_rewind(
                tmp,
                folio='FL-TEST-001',
                equipo='Laptop Dell Latitude 5420',
                tipos_activos=TIPOS_DIAGNOSTICO,
                es_venta_mostrador=False,
                incluir_intro_y_secciones=True,
            )
            self.assertIsNotNone(slides['intro'])
            _assert_png_valido(self, slides['intro'])
            self.assertEqual(set(slides['secciones']), set(TIPOS_DIAGNOSTICO))
            self.assertEqual(len(slides['secciones']), 4)
            for tipo in TIPOS_DIAGNOSTICO:
                _assert_png_valido(self, slides['secciones'][tipo])
            cierre = _assert_png_valido(self, slides['cierre'])
            self._assert_look_cinematico(cierre)

    def test_venta_mostrador_genera_3_tarjetas(self):
        """Venta mostrador: 3 tarjetas (sin diagnóstico)."""
        with tempfile.TemporaryDirectory(prefix='rewind_slides_vm_') as tmp:
            slides = generar_slides_rewind(
                tmp,
                folio='VM-100',
                equipo='Impresora HP',
                tipos_activos=TIPOS_VM,
                es_venta_mostrador=True,
                incluir_intro_y_secciones=True,
            )
            self.assertEqual(set(slides['secciones']), set(TIPOS_VM))
            self.assertEqual(len(slides['secciones']), 3)
            self.assertNotIn('diagnostico', slides['secciones'])
            self.assertEqual(
                set(TEXTO_SECCIONES_VM),
                {'ingreso', 'reparacion', 'egreso'},
            )
            # El copy de diagnóstico NO se usa en VM (tiene 4 claves).
            self.assertIn('diagnostico', TEXTO_SECCIONES)

    def test_modo_simple_solo_cierre(self):
        """Fotos incompletas: no hay intro ni tarjetas, sí hay cierre."""
        with tempfile.TemporaryDirectory(prefix='rewind_slides_simple_') as tmp:
            slides = generar_slides_rewind(
                tmp,
                folio='X',
                equipo='',
                tipos_activos=TIPOS_DIAGNOSTICO,
                incluir_intro_y_secciones=False,
            )
            self.assertIsNone(slides['intro'])
            self.assertEqual(slides['secciones'], {})
            _assert_png_valido(self, slides['cierre'])

    def _assert_look_cinematico(self, img: Image.Image) -> None:
        """
        El fondo ya no es el azul plano #1f6391: es navy oscuro con barra de acento.

        Args:
            img: PNG de cierre (o cualquier slide del mismo fondo).
        """
        rgb = img.convert('RGB')
        # Barra superior de 4 px: acento de marca.
        pixel_barra = rgb.getpixel((ANCHO // 2, 1))
        self.assertEqual(pixel_barra, COLOR_ACENTO)
        # Un punto del centro-arriba del lienzo debe ser OSCURO (no azul brillante).
        pixel_fondo = rgb.getpixel((ANCHO // 2, 80))
        luminancia = sum(pixel_fondo) / 3
        self.assertLess(
            luminancia,
            80,
            f'El fondo no se ve cinematográfico oscuro: {pixel_fondo}',
        )
