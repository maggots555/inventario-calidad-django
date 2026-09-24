"""
Tests del PDF de diagnóstico (Platypus, estilo OOW / RHITSO).

EXPLICACIÓN PARA PRINCIPIANTES:
No enviamos correo ni tocamos la BD. Armamos una orden de mentira
(SimpleNamespace) y pedimos a PDFGeneratorDiagnostico que escriba un PDF
en un MEDIA_ROOT temporal.

Así comprobamos que el rediseño no se comió datos:
1. El archivo nace bien (%PDF, ruta, nombre DIAGNOSTICO_).
2. Folio, equipo, falla, pieza y leyenda siguen en el texto.
3. Un diagnóstico largo ya no truena ni se corta.
4. La pieza extra y los colores necesaria/opcional siguen saliendo.
"""

import base64
import re
import subprocess
import tempfile
import zlib
from types import SimpleNamespace

from django.test import SimpleTestCase, override_settings

from servicio_tecnico.utils.pdf_diagnostico import PDFGeneratorDiagnostico


def _orden(**overrides_detalle):
    """
    Orden + detalle mínimos como los que usa el generador.

    Args:
        **overrides_detalle: campos extra o de reemplazo en detalle_equipo.

    Returns:
        SimpleNamespace listo para PDFGeneratorDiagnostico.
    """
    detalle = SimpleNamespace(
        marca='Dell',
        modelo='Inspiron 15 3535 con nombre largo que antes se cortaba en la celda',
        tipo_equipo='Laptop',
        numero_serie='SN-DIAG-01-MUY-LARGO-PARA-NO-TRUNCAR',
        falla_principal='No enciende y el LED parpadea 3 veces.',
        diagnostico_sic='Falla en motherboard. Se cotiza tarjeta.',
    )
    for clave, valor in overrides_detalle.items():
        setattr(detalle, clave, valor)
    return SimpleNamespace(id=77, detalle_equipo=detalle)


def _texto_pdf(data: bytes) -> str:
    """
    Extrae el texto visible con pdftotext (poppler).

    Args:
        data: bytes del PDF ya generado.

    Returns:
        Texto plano. Cadena vacía si pdftotext no está.
    """
    with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            salida = subprocess.run(
                ['pdftotext', '-layout', tmp.name, '-'],
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return ''
    return salida.stdout.decode('utf-8', errors='replace')


def _plano(texto: str) -> str:
    """Junta saltos de línea: pdftotext parte una celda envuelta en varias líneas."""
    return ' '.join(texto.split())


def _cajas(data: bytes) -> list:
    """
    Posición de cada palabra (pdftotext -bbox).

    y crece hacia abajo: un yMin grande está cerca del pie de la hoja.

    Returns:
        Lista de dicts {pagina, texto, y_min, y_max}.
    """
    import re
    with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
        tmp.write(data)
        tmp.flush()
        try:
            salida = subprocess.run(
                ['pdftotext', '-bbox', tmp.name, '-'],
                check=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError):
            return []
    html = salida.stdout.decode('utf-8', errors='replace')
    cajas = []
    pagina = 0
    for linea in html.splitlines():
        if '<page ' in linea:
            pagina += 1
        coincidencia = re.search(
            r'yMin="([\d.]+)".*?yMax="([\d.]+)">(.*?)</word>',
            linea,
        )
        if coincidencia and pagina:
            cajas.append({
                'pagina': pagina,
                'y_min': float(coincidencia.group(1)),
                'y_max': float(coincidencia.group(2)),
                'texto': coincidencia.group(3),
            })
    return cajas


def _streams(data: bytes) -> str:
    """
    Descomprime los streams de contenido (ASCII85 + Flate, como los escribe ReportLab).

    Args:
        data: bytes del PDF.

    Returns:
        Operadores de dibujo, en latin-1. Sirve para ver los colores de relleno.
    """
    partes = []
    patron = rb'/Filter \[ /ASCII85Decode /FlateDecode \] /Length (\d+)\s*>>\s*stream\n'
    for coincidencia in re.finditer(patron, data):
        inicio = coincidencia.end()
        crudo = data[inicio:inicio + int(coincidencia.group(1))]
        try:
            inflado = zlib.decompress(base64.a85decode(crudo, adobe=True))
        except (ValueError, zlib.error):
            continue
        partes.append(inflado.decode('latin-1', errors='replace'))
    return '\n'.join(partes)


class PdfDiagnosticoPlatypusTest(SimpleTestCase):
    """Generación real del PDF sin BD ni correo."""

    def _generar(self, orden=None, componentes=None, folio='MX_CIS_TEST_02690', email='tecnico@sic.com.mx'):
        """
        Llama a generar_pdf() con MEDIA_ROOT temporal.

        Returns:
            dict: resultado del generador, con `_bytes` y `_texto` si hubo éxito.
        """
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                generador = PDFGeneratorDiagnostico(
                    orden=orden or _orden(),
                    folio=folio,
                    componentes_seleccionados=componentes or [],
                    email_empleado=email,
                    pais_config={
                        'empresa_nombre': 'SIC Comercialización y Servicios México SC',
                        'empresa_nombre_corto': 'SIC México',
                    },
                )
                resultado = generador.generar_pdf()
                if resultado.get('success') and resultado.get('ruta'):
                    with open(resultado['ruta'], 'rb') as archivo:
                        resultado['_bytes'] = archivo.read()
                    resultado['_texto'] = _texto_pdf(resultado['_bytes'])
                return resultado

    def test_feliz_conserva_datos_y_ruta(self):
        """Feliz: PDF válido y el cliente sigue viendo folio, equipo y falla."""
        resultado = self._generar(componentes=[{
            'componente_db': 'Motherboard',
            'dpn': 'DPN: 0XPJWG',
            'seleccionado': True,
            'es_necesaria': True,
        }])

        self.assertTrue(resultado['success'], resultado.get('error'))
        self.assertTrue(resultado['archivo'].startswith('DIAGNOSTICO_'))
        self.assertTrue(resultado['archivo'].endswith('.pdf'))
        self.assertIn('MX_CIS_TEST_02690', resultado['archivo'])
        self.assertIn('temp/diagnostico', resultado['ruta'].replace('\\', '/'))
        self.assertGreater(resultado['size'], 100)
        self.assertTrue(resultado['_bytes'].startswith(b'%PDF'))

        texto = _plano(resultado['_texto'])
        self.assertIn('FORMATO DE DIAGNÓSTICO', texto)
        self.assertIn('MX_CIS_TEST_02690', texto)
        # pdftotext parte la celda envuelta; el final prueba que ya no se trunca.
        self.assertIn('Inspiron 15 3535 con nombre largo que antes se', texto)
        self.assertIn('cortaba en la celda', texto)
        self.assertIn('SN-DIAG-01-MUY-LARGO-PARA-NO-TR', texto)
        self.assertIn('UNCAR', texto)
        self.assertIn('No enciende y el LED parpadea 3 veces.', texto)
        self.assertIn('Falla en motherboard. Se cotiza tarjeta.', texto)
        self.assertIn('TARJETA (MOTHERBOARD)', texto)
        self.assertIn('DPN: 0XPJWG', texto)
        self.assertIn('= Pieza necesaria', texto)
        self.assertIn('= Pieza opcional / recomendada', texto)
        self.assertIn('tecnico@sic.com.mx', texto)
        self.assertIn('SIC México', texto)
        self.assertIn('Página 1', texto)

    def test_diagnostico_largo_no_se_corta_ni_truena(self):
        """Borde: un análisis de varias hojas se genera completo."""
        marca_final = 'FIN-DIAGNOSTICO-LARGO-XYZ'
        texto_largo = ('Se observa falla intermitente de encendido. ' * 80) + marca_final
        resultado = self._generar(_orden(diagnostico_sic=texto_largo))

        self.assertTrue(resultado['success'], resultado.get('error'))
        self.assertTrue(resultado['_bytes'].startswith(b'%PDF'))
        self.assertIn(marca_final, _plano(resultado['_texto']))
        self.assertIn('Página 2', resultado['_texto'])

    def test_pieza_adicional_y_colores_necesaria_opcional(self):
        """
        Borde: la pieza extra aparece, y verde/amarillo siguen en el PDF.

        El verde es necesaria; el amarillo es opcional. Son los mismos
        hex que leía el cliente en el formato anterior.
        """
        componentes = [
            {
                'componente_db': 'Pantalla',
                'dpn': 'LCD-NECESARIA-01',
                'seleccionado': True,
                'es_necesaria': True,
            },
            {
                'componente_db': 'Lector de tarjetas',
                'dpn': 'LECTOR-OPCIONAL-02',
                'seleccionado': True,
                'es_necesaria': False,
            },
        ]
        resultado = self._generar(componentes=componentes)

        self.assertTrue(resultado['success'], resultado.get('error'))
        texto = _plano(resultado['_texto'])
        self.assertIn('LCD Ó DISPLAY', texto)
        self.assertIn('LCD-NECESARIA-01', texto)
        self.assertIn('LECTOR DE TARJETAS', texto)
        self.assertIn('LECTOR-OPCIONAL-02', texto)
        # Las 18 fijas se dibujan aunque nadie las haya marcado.
        self.assertIn('BATERIA', texto)

        streams = _streams(resultado['_bytes'])
        # ReportLab omite el cero: #C6EFCE → .776471 .937255 .807843
        self.assertIn('.776471', streams)
        self.assertIn('.937255', streams)
        # #FFEB9C → 1 .921569 .611765
        self.assertIn('.921569', streams)
        self.assertIn('.611765', streams)

    def test_sin_datos_usa_los_mismos_textos_vacios(self):
        """Borde: sin falla ni diagnóstico, los avisos de siempre."""
        orden = SimpleNamespace(
            id=1,
            detalle_equipo=SimpleNamespace(
                marca='',
                modelo='',
                tipo_equipo='',
                numero_serie='',
                falla_principal='',
                diagnostico_sic='',
            ),
        )
        resultado = self._generar(orden=orden, email='', folio='PREVIEW')

        self.assertTrue(resultado['success'], resultado.get('error'))
        texto = resultado['_texto']
        self.assertIn('Sin reporte de usuario', texto)
        self.assertIn('Sin diagnóstico registrado', texto)
        self.assertIn('N/A', texto)
        self.assertNotIn('a@b.c', texto)
        self.assertNotIn('Contacto', texto)

    def test_contacto_queda_al_fondo_de_la_ultima_hoja(self):
        """
        La fila Empresa/Contacto no flota tras la leyenda: va al hueco
        de encima del pie, en la última hoja (también si hay página 2).
        """
        resultado = self._generar(
            orden=_orden(diagnostico_sic='Se observa falla intermitente. ' * 80),
            email='j.alvarez@sic.com.mx',
        )
        self.assertTrue(resultado['success'], resultado.get('error'))
        cajas = _cajas(resultado['_bytes'])
        self.assertTrue(cajas, 'pdftotext -bbox no devolvió palabras')

        ultima = max(caja['pagina'] for caja in cajas)
        self.assertGreaterEqual(ultima, 2)

        contacto = next(c for c in cajas if c['texto'] == 'Contacto')
        pie = next(
            c for c in cajas
            if c['texto'] == 'Página' and c['pagina'] == ultima
        )
        leyenda = next(c for c in cajas if c['texto'] == 'necesaria')

        self.assertEqual(contacto['pagina'], ultima)
        # Encima del pie, no a mitad de la hoja junto a la leyenda.
        self.assertLess(leyenda['y_min'], contacto['y_min'] - 200)
        self.assertGreater(contacto['y_min'], 680)
        self.assertLess(contacto['y_max'], pie['y_min'])
