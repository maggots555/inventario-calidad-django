"""
Humo: modo horizontal (barras 1D) en scanner_codigo.ts.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
No probamos la cámara ni zxing-wasm en CI. Solo verificamos que la fuente
TypeScript y el JS compilado incluyen el toggle Cuadrado/Barras, el recorte
horizontal y la API modoInicial.
"""

from pathlib import Path

from django.test import SimpleTestCase


_ROOT = Path(__file__).resolve().parents[2]
_TS = _ROOT / 'static' / 'ts' / 'scanner_codigo.ts'
_JS = _ROOT / 'static' / 'js' / 'scanner_codigo.js'
_TS_ENLACE = _ROOT / 'static' / 'ts' / 'scanner_enlace.ts'
_TS_FORM = _ROOT / 'static' / 'ts' / 'form_nueva_orden_scanner.ts'
_CSS = _ROOT / 'static' / 'css' / 'components.css'


class ScannerModoBarrasAssetsTest(SimpleTestCase):
    """Presencia de símbolos clave en fuente TS, JS compilado y CSS."""

    def setUp(self):
        self.ts = _TS.read_text(encoding='utf-8')
        self.js = _JS.read_text(encoding='utf-8')
        self.css = _CSS.read_text(encoding='utf-8')

    def test_fuente_ts_incluye_modo_barras(self):
        """Regresión: toggle, recorte horizontal y limpieza REV en scanner_codigo.ts."""
        for fragmento in (
            'scanner-frame--barras',
            'escanearRecorteHorizontal',
            'data-scanner-modo',
            'modoInicial',
            'FORMATOS_BARRAS_1D',
            'limpiarCodigoDetectado',
            'sigma_scanner_modo',
        ):
            with self.subTest(fragmento=fragmento):
                self.assertIn(fragmento, self.ts)

    def test_js_compilado_incluye_modo_barras(self):
        """El build debe generar scanner_codigo.js con las mismas piezas."""
        for fragmento in (
            'escanearRecorteHorizontal',
            'data-scanner-modo',
            'modoInicial',
            'FORMATOS_BARRAS_1D',
        ):
            with self.subTest(fragmento=fragmento):
                self.assertIn(fragmento, self.js)

    def test_css_incluye_marco_horizontal(self):
        """Marco visual ancho para barras 1D."""
        self.assertIn('.scanner-frame--barras', self.css)

    def test_scanner_enlace_propaga_modo_inicial(self):
        """Helper compartido acepta modoInicial y lo pasa a abrirScannerCodigo."""
        enlace = _TS_ENLACE.read_text(encoding='utf-8')
        self.assertIn('modoInicial', enlace)

    def test_form_nueva_orden_cargador_usa_modo_barras(self):
        """Al escanear cargador en alta de orden, abrir en modo barras."""
        form_ts = _TS_FORM.read_text(encoding='utf-8')
        self.assertIn("'barras'", form_ts)
        self.assertIn('btnEscanearCargadorCrear', form_ts)
