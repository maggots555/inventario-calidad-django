"""
Generador de PDF para Formato de Diagnóstico SIC
=================================================

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo crea el PDF de diagnóstico que se envía al cliente. Usa el
MISMO estilo visual que OOW y RHITSO (Platypus + barras navy #003366).

Ya no dibuja con canvas y coordenadas Y fijas. Ese diseño viejo cortaba
modelo, serie y número de parte, y el pie podía tapar la leyenda.

Platypus apila bloques. Si no caben, saltan a la página siguiente.
El pie vive en el margen inferior y no tapa el contenido.

La información es la de siempre:
1. Header logo SIC + razón social
2. Título Formato de diagnóstico
3. Folio y fecha
4. Datos del equipo (marca, modelo, tipo, serie)
5. Reporte de usuario (falla reportada)
6. Diagnóstico técnico
7. Piezas a cotizar (18 componentes + adicionales, X, DPN, necesaria/opcional)
8. Contacto del empleado (siempre al fondo de la última hoja)
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.staticfiles import finders
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.rl_config import _FUZZ
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config.constants import COMPONENTES_DIAGNOSTICO_ORDEN

logger = logging.getLogger('servicio_tecnico')

# Paleta idéntica a OOW / RHITSO. Verde y amarillo se quedan: el cliente
# ya lee así qué pieza es necesaria y cuál es opcional.
COLOR_NAVY = colors.HexColor('#003366')
COLOR_NAVY_SUAVE = colors.HexColor('#E8EEF5')
COLOR_GRIS_ALT = colors.HexColor('#F2F2F2')
COLOR_GRIS_BORDE = colors.HexColor('#CCCCCC')
COLOR_ROJO_CHECK = colors.HexColor('#FF0000')
COLOR_VERDE_NECESARIA = colors.HexColor('#C6EFCE')
COLOR_AMARILLO_OPCIONAL = colors.HexColor('#FFEB9C')
COLOR_BLANCO = colors.white
COLOR_NEGRO = colors.black

MARGEN = 15 * mm
MARGEN_INFERIOR = 20 * mm
# Una caja de texto más alta que esto no cabe segura en una hoja: se deja
# fluir como párrafo para que un diagnóstico largo no se salga de la página.
ALTO_MAX_CAJA = 460


class ContactoAlFondo(Flowable):
    """
    Pega la fila de empresa y correo al fondo de la última hoja.

    Objetivo de negocio:
        Ese bloque no debe flotar a mitad de página, después de la leyenda.
        Siempre cierra el PDF, en el hueco justo encima del pie
        (folio a la izquierda y «Página N» a la derecha).

    Cómo lo pide Platypus (no es una coordenada Y fija):
        wrap() dice cuánto alto usa el bloque. Si cabe, se estira hasta el
        fondo del marco y draw() pinta la fila en y=0 de ese bloque.
        Si no cabe, wrap() devuelve más alto del disponible. El marco llama
        a split(); la clase base devuelve [] y ReportLab pasa el bloque
        completo a la hoja siguiente. Es el mismo contrato que usa una
        tabla que no cabe: no se parte, se mueve.

    Args:
        tabla: Table ya armada con empresa y, si hay, el correo.

    Efectos secundarios:
        Ninguno sobre disco ni BD. Solo ocupa el alto que sobra en la hoja.
    """

    def __init__(self, tabla: Table):
        super().__init__()
        self.tabla = tabla
        self._alto_fila = 0.0

    def wrap(self, availWidth, availHeight):
        """
        Mide la fila con alto de sobra y decide si cabe en esta hoja.

        Args:
            availWidth: ancho útil del marco.
            availHeight: alto que queda en la hoja actual.

        Returns:
            (ancho, alto) que el marco debe reservar.
        """
        # Alto generoso a propósito: una tabla "larga" de ReportLab deja de
        # medir filas si el alto pedido ya se llenó. Aquí la fila es una.
        _ancho, alto = self.tabla.wrap(availWidth, 1000)
        self._alto_fila = alto
        self.width = availWidth

        # No cabe en el resto de esta hoja. El marco verá que nos pasamos
        # y nos mandará enteros a la siguiente (split() de Flowable = []).
        if alto > availHeight + _FUZZ:
            self.height = alto
            return availWidth, availHeight + 1

        # Cabe. Ocupamos el resto del marco, menos el margen de error que
        # ReportLab usa en sus propias cuentas, para no fallar por float.
        self.height = max(availHeight - _FUZZ, alto)
        return availWidth, self.height

    def draw(self):
        """y=0 es el fondo del marco, encima de la línea del pie."""
        self.tabla.drawOn(self.canv, 0, 0)


class PDFGeneratorDiagnostico:
    """
    Genera el PDF del formato de Diagnóstico SIC con estilo OOW/RHITSO.

    Objetivo de negocio:
        El cliente recibe el mismo diagnóstico de siempre (equipo, falla,
        análisis y piezas a cotizar), con un documento que se lee igual
        que el formato OOW y el de RHITSO.

    Args:
        orden: OrdenServicio con detalle_equipo.
        folio: Folio visible (ej. 'MX_CIS_MX_MONTERREY1_02690').
        componentes_seleccionados: lista de dicts
            {'componente_db', 'dpn', 'seleccionado', 'es_necesaria'}.
        email_empleado: correo de quien envía el diagnóstico.
        pais_config: dict de get_pais_actual(); nombre de la empresa.

    Efectos secundarios:
        Escribe un archivo en MEDIA_ROOT/temp/diagnostico/. No toca la BD.
    """

    def __init__(
        self,
        orden,
        folio: str,
        componentes_seleccionados: List[Dict] = None,
        email_empleado: str = '',
        pais_config: Dict = None,
    ):
        """
        Prepara datos y estilos. No escribe el archivo todavía.

        Args:
            orden: OrdenServicio.
            folio: Folio que verá el cliente.
            componentes_seleccionados: piezas marcadas en el modal.
            email_empleado: contacto que va al final del PDF.
            pais_config: configuración del país (nombre de empresa).
        """
        self.orden = orden
        self.detalle_equipo = getattr(orden, 'detalle_equipo', None)
        self.folio = '' if folio is None else str(folio)
        self.componentes_seleccionados = componentes_seleccionados or []
        self.email_empleado = email_empleado or ''
        # Si no llega país, México: mismo default que el PDF anterior.
        self.pais_config = pais_config or {}
        self.empresa_nombre = self.pais_config.get(
            'empresa_nombre',
            'SIC Comercialización y Servicios México SC',
        )
        self.empresa_nombre_corto = self.pais_config.get(
            'empresa_nombre_corto',
            'SIC México',
        )
        self._momento = datetime.now()
        self._estilos = getSampleStyleSheet()
        self._crear_estilos()

    def generar_pdf(self) -> Dict[str, Any]:
        """
        Construye el PDF en disco (Celery y la vista previa leen `ruta`).

        Returns:
            dict: {success, archivo, ruta, size} o {success: False, error}.

        Efectos secundarios:
            Crea MEDIA_ROOT/temp/diagnostico/ si no existe y escribe el PDF.
        """
        try:
            # Misma fecha en el nombre y en el cuerpo (no dos now() distintos).
            self._momento = datetime.now()
            fecha = self._momento.strftime('%Y%m%d')
            folio_limpio = self.folio.replace(' ', '_').replace('/', '_')
            nombre_archivo = f'DIAGNOSTICO_{fecha}_{folio_limpio}.pdf'

            directorio_temp = os.path.join(settings.MEDIA_ROOT, 'temp', 'diagnostico')
            os.makedirs(directorio_temp, exist_ok=True)
            ruta_archivo = os.path.join(directorio_temp, nombre_archivo)

            doc = SimpleDocTemplate(
                ruta_archivo,
                pagesize=letter,
                leftMargin=MARGEN,
                rightMargin=MARGEN,
                topMargin=MARGEN,
                bottomMargin=MARGEN_INFERIOR,
                title=f'Diagnóstico - {self.folio}',
                author=self.empresa_nombre_corto,
                subject=f'Diagnóstico de equipo {self._campo("numero_serie")}',
                creator=f'{self.empresa_nombre_corto} - Sistema de Servicio Técnico',
            )

            elementos: List = []
            elementos += self._construir_header()
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._construir_titulo()
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._envolver_seccion(self._construir_folio_fecha())
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._envolver_seccion(self._construir_datos_equipo())
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._construir_bloque_texto(
                'Reporte de usuario',
                self._falla(),
            )
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._construir_bloque_texto(
                'Diagnóstico técnico',
                self._diagnostico_texto(),
            )
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._construir_piezas()
            elementos.append(Spacer(1, 2 * mm))
            elementos.append(self._construir_leyenda())
            # La fila de contacto no va aquí en el flujo: se pega al fondo
            # de la última hoja, encima del pie (folio + página).
            elementos.append(ContactoAlFondo(self._construir_contacto()))

            doc.build(
                elementos,
                onFirstPage=self._dibujar_pie_pagina,
                onLaterPages=self._dibujar_pie_pagina,
            )

            return {
                'success': True,
                'archivo': nombre_archivo,
                'ruta': ruta_archivo,
                'size': os.path.getsize(ruta_archivo),
            }
        except Exception as exc:
            logger.error('[PDF DIAGNOSTICO] Error generando PDF: %s', exc, exc_info=True)
            return {'success': False, 'error': f'Error generando PDF: {exc}'}

    # ------------------------------------------------------------------ estilos

    def _crear_estilos(self) -> None:
        """Registra ParagraphStyles reutilizados en el documento."""
        self._estilos.add(ParagraphStyle(
            'EmpresaHeader',
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=COLOR_NAVY,
            alignment=TA_RIGHT,
            leading=14,
        ))
        self._estilos.add(ParagraphStyle(
            'TituloFormato',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=COLOR_BLANCO,
            alignment=TA_CENTER,
            leading=12,
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaLabel',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NAVY,
            leading=10,
            wordWrap='CJK',
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaLabelCentro',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaValor',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            leading=10,
            wordWrap='CJK',
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaValorCentro',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
            leading=10,
            wordWrap='CJK',
        ))
        self._estilos.add(ParagraphStyle(
            'CuerpoNormal',
            fontName='Helvetica',
            fontSize=9,
            textColor=COLOR_NEGRO,
            alignment=TA_LEFT,
            leading=12,
        ))
        self._estilos.add(ParagraphStyle(
            'MarcaX',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=COLOR_ROJO_CHECK,
            alignment=TA_CENTER,
            leading=12,
        ))
        self._estilos.add(ParagraphStyle(
            'Leyenda',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            leading=10,
        ))

    def _ancho_util(self) -> float:
        """Ancho de página menos márgenes izquierdo y derecho."""
        return letter[0] - (2 * MARGEN)

    def _esc(self, texto: Any) -> str:
        """
        Escapa texto para Paragraph y conserva los saltos de línea del técnico.

        Args:
            texto: valor a mostrar (puede ser None).

        Returns:
            str seguro para el XML de ReportLab.
        """
        if texto is None:
            return ''
        s = str(texto)
        s = s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return s.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br/>')

    def _campo(self, nombre: str, default: str = 'N/A') -> str:
        """Lee un campo del detalle; vacío o ausente → default."""
        detalle = self.detalle_equipo
        if detalle is None:
            return default
        valor = getattr(detalle, nombre, None)
        if valor is None or valor == '':
            return default
        return str(valor)

    def _tipo_equipo(self) -> str:
        """Tipo legible (get_tipo_equipo_display si el modelo lo tiene)."""
        detalle = self.detalle_equipo
        if detalle is None:
            return 'N/A'
        if hasattr(detalle, 'get_tipo_equipo_display'):
            return str(detalle.get_tipo_equipo_display() or 'N/A')
        return str(getattr(detalle, 'tipo_equipo', None) or 'N/A')

    def _falla(self) -> str:
        """Falla que reportó el usuario. Mismo texto vacío que el PDF anterior."""
        if self.detalle_equipo is None:
            return 'Sin reporte de usuario'
        return getattr(self.detalle_equipo, 'falla_principal', None) or 'Sin reporte de usuario'

    def _diagnostico_texto(self) -> str:
        """Análisis técnico. Mismo texto vacío que el PDF anterior."""
        if self.detalle_equipo is None:
            return 'Sin diagnóstico registrado'
        return getattr(self.detalle_equipo, 'diagnostico_sic', None) or 'Sin diagnóstico registrado'

    def _dibujar_pie_pagina(self, canvas, doc) -> None:
        """
        Pie en CADA hoja: folio a la izquierda, página a la derecha.

        Args:
            canvas: canvas de ReportLab de la página actual.
            doc: SimpleDocTemplate (número de página).

        Efectos secundarios:
            Dibuja línea y textos en el margen inferior. No tapa el cuerpo
            porque bottomMargin ya reservó ese espacio.
        """
        canvas.saveState()
        y_pie = 10 * mm
        x_izq = MARGEN
        x_der = letter[0] - MARGEN
        canvas.setStrokeColor(COLOR_GRIS_BORDE)
        canvas.setLineWidth(0.5)
        canvas.line(x_izq, y_pie + 5 * mm, x_der, y_pie + 5 * mm)
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(COLOR_NAVY)
        canvas.drawString(x_izq, y_pie, f'Diagnóstico · {self.folio}')
        canvas.drawRightString(x_der, y_pie, f'Página {doc.page}')
        canvas.restoreState()

    def _envolver_seccion(self, partes: List) -> List:
        """Agrupa header + contenido para que el título no quede solo."""
        if not partes:
            return []
        return [KeepTogether(partes)]

    def _crear_header_seccion(self, titulo: str) -> Table:
        """Barra navy de sección (igual que OOW y RHITSO)."""
        tabla = Table(
            [[Paragraph(self._esc(titulo), self._estilos['TituloFormato'])]],
            colWidths=[self._ancho_util()],
        )
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_NAVY),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        return tabla

    def _tabla_pares(self, pares: List[tuple]) -> Table:
        """Tabla 2 columnas label|valor con jerarquía visual navy."""
        data = [
            [
                Paragraph(self._esc(label), self._estilos['CeldaLabel']),
                Paragraph(self._esc(valor or 'N/A'), self._estilos['CeldaValor']),
            ]
            for label, valor in pares
        ]
        tabla = Table(data, colWidths=[45 * mm, None])
        estilos = [
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('BACKGROUND', (0, 0), (0, -1), COLOR_NAVY_SUAVE),
        ]
        for i in range(len(data)):
            if i % 2 == 0:
                estilos.append(('BACKGROUND', (1, i), (1, i), COLOR_GRIS_ALT))
        tabla.setStyle(TableStyle(estilos))
        return tabla

    def _ruta_logo(self) -> Optional[str]:
        """
        Busca el PNG del logo SIC.

        Primero el finder de Django (desarrollo). Si no está, STATIC_ROOT
        (producción después de collectstatic).
        """
        ruta = finders.find('images/logos/logo_sic.png')
        if ruta and os.path.exists(ruta):
            return ruta
        static_root = getattr(settings, 'STATIC_ROOT', None)
        if static_root:
            candidato = os.path.join(static_root, 'images', 'logos', 'logo_sic.png')
            if os.path.exists(candidato):
                return candidato
        return None

    def _obtener_logo(self) -> Optional[RLImage]:
        """Carga el logo sin estirarlo. Si falta, el header sigue sin imagen."""
        ruta = self._ruta_logo()
        if not ruta:
            return None
        try:
            return RLImage(ruta, width=45 * mm, height=15 * mm, kind='proportional')
        except Exception:
            logger.warning('[PDF DIAGNOSTICO] No se pudo cargar el logo SIC')
            return None

    # ------------------------------------------------------------------ secciones

    def _construir_header(self) -> List:
        """Logo a la izquierda, razón social a la derecha, línea debajo."""
        logo = self._obtener_logo()
        texto = Paragraph(self._esc(self.empresa_nombre), self._estilos['EmpresaHeader'])
        fila = [[logo or '', texto]]
        tabla = Table(fila, colWidths=[55 * mm, None])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
            ('RIGHTPADDING', (0, 0), (0, 0), 0),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ]))
        return [
            tabla,
            Spacer(1, 2 * mm),
            HRFlowable(width='100%', thickness=1, color=COLOR_GRIS_BORDE),
        ]

    def _construir_titulo(self) -> List:
        """Barra navy con el nombre del formato."""
        return [self._crear_header_seccion('FORMATO DE DIAGNÓSTICO')]

    def _construir_folio_fecha(self) -> List:
        """
        Folio y fecha en una sola fila.

        Así no gastamos una barra navy extra: el caso típico (18 piezas y
        textos cortos) sigue cabiendo en una hoja, como el formato anterior.
        """
        ancho = self._ancho_util()
        etiqueta = 22 * mm
        # Dos pares lado a lado: Folio | valor | Fecha | valor.
        ancho_folio = ancho * 0.62 - etiqueta
        ancho_fecha = ancho * 0.38 - etiqueta
        data = [[
            Paragraph('Folio', self._estilos['CeldaLabel']),
            Paragraph(self._esc(self.folio or 'N/A'), self._estilos['CeldaValor']),
            Paragraph('Fecha', self._estilos['CeldaLabel']),
            Paragraph(self._esc(self._momento.strftime('%d/%m/%Y')), self._estilos['CeldaValor']),
        ]]
        tabla = Table(data, colWidths=[etiqueta, ancho_folio, etiqueta, ancho_fecha])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_NAVY_SUAVE),
            ('BACKGROUND', (2, 0), (2, 0), COLOR_NAVY_SUAVE),
            ('BACKGROUND', (1, 0), (1, 0), COLOR_GRIS_ALT),
            ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        return [tabla]

    def _construir_datos_equipo(self) -> List:
        """
        Marca, modelo, tipo y serie en una fila.

        Paragraph envuelve: un modelo largo ya no se corta a mitad de palabra.
        """
        elementos = [self._crear_header_seccion('Datos del equipo'), Spacer(1, 2 * mm)]
        ancho = self._ancho_util()
        anchos = [
            ancho * 0.18,
            ancho * 0.37,
            ancho * 0.15,
            ancho * 0.30,
        ]
        etiquetas = ['MARCA', 'MODELO', 'TIPO', 'SERIE']
        valores = [
            self._campo('marca'),
            self._campo('modelo'),
            self._tipo_equipo(),
            self._campo('numero_serie'),
        ]
        data = [
            [Paragraph(self._esc(et), self._estilos['CeldaLabelCentro']) for et in etiquetas],
            [Paragraph(self._esc(val), self._estilos['CeldaValorCentro']) for val in valores],
        ]
        tabla = Table(data, colWidths=anchos)
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_NAVY_SUAVE),
            ('BACKGROUND', (0, 1), (-1, 1), COLOR_BLANCO),
            ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elementos.append(tabla)
        return elementos

    def _estimar_alto_texto(self, texto: str) -> float:
        """Alto aproximado en puntos para decidir caja fija vs párrafo fluido."""
        ancho_chars = 90
        lineas = 0
        for parrafo in (texto or '').split('\n'):
            largo = len(parrafo.strip())
            # Una línea vacía también ocupa espacio (el técnico dejó un enter).
            lineas += 1 if largo == 0 else max(1, (largo + ancho_chars - 1) // ancho_chars)
        return (lineas * 12) + 24

    def _construir_bloque_texto(self, titulo: str, texto: str) -> List:
        """
        Sección de texto largo (reporte o diagnóstico).

        Si cabe en una hoja, va en una caja con borde. Si es más largo,
        fluye como párrafo y salta de página solo: el canvas viejo lo cortaba.
        """
        # No arrancar la sección si casi no queda hoja (el título quedaría solo).
        partes: List = [CondPageBreak(28 * mm), self._crear_header_seccion(titulo), Spacer(1, 2 * mm)]
        if self._estimar_alto_texto(texto) <= ALTO_MAX_CAJA:
            caja = Table(
                [[Paragraph(self._esc(texto), self._estilos['CuerpoNormal'])]],
                colWidths=[self._ancho_util()],
            )
            caja.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
                ('BACKGROUND', (0, 0), (-1, -1), COLOR_BLANCO),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            partes.append(caja)
            return self._envolver_seccion(partes)

        # Texto que no cabe en una caja: Paragraph se parte entre hojas.
        partes.append(Paragraph(self._esc(texto), self._estilos['CuerpoNormal']))
        return partes

    def _filas_piezas(self) -> List[Dict[str, Any]]:
        """
        Arma las filas de la tabla: primero las 18 fijas, luego las extra.

        Returns:
            Lista de dicts {etiqueta, seleccionado, dpn, es_necesaria}.
        """
        nombres_fijos = {comp['componente_db'] for comp in COMPONENTES_DIAGNOSTICO_ORDEN}
        por_nombre: Dict[str, Dict] = {}
        adicionales: List[Dict] = []

        for comp in self.componentes_seleccionados:
            if not isinstance(comp, dict):
                continue
            nombre_db = comp.get('componente_db', '') or ''
            datos = {
                'seleccionado': bool(comp.get('seleccionado', False)),
                'dpn': comp.get('dpn', '') or '',
                'es_necesaria': comp.get('es_necesaria', True),
            }
            por_nombre[nombre_db] = datos
            # Lo que no está en el catálogo fijo se dibuja al final, igual que antes.
            if nombre_db and nombre_db not in nombres_fijos:
                adicionales.append(comp)

        filas: List[Dict[str, Any]] = []
        for comp_config in COMPONENTES_DIAGNOSTICO_ORDEN:
            datos = por_nombre.get(comp_config['componente_db'], {})
            filas.append({
                'etiqueta': comp_config['label_pdf'],
                'seleccionado': bool(datos.get('seleccionado', False)),
                'dpn': datos.get('dpn', '') or '',
                'es_necesaria': datos.get('es_necesaria', True),
            })

        for comp in adicionales:
            nombre_db = comp.get('componente_db', '') or ''
            filas.append({
                'etiqueta': nombre_db.upper() if nombre_db else 'COMPONENTE ADICIONAL',
                'seleccionado': bool(comp.get('seleccionado', False)),
                'dpn': comp.get('dpn', '') or '',
                'es_necesaria': comp.get('es_necesaria', True),
            })
        return filas

    def _construir_piezas(self) -> List:
        """
        Tabla de piezas a cotizar.

        La X roja y el fondo verde/amarillo significan lo mismo que antes.
        repeatRows repite el título si la tabla pasa a la hoja siguiente.
        El número de parte envuelve: ya no se trunca.
        """
        filas = self._filas_piezas()
        ancho = self._ancho_util()
        ancho_nombre = 52 * mm
        ancho_check = 12 * mm
        ancho_dpn = ancho - ancho_nombre - ancho_check

        encabezado = [
            Paragraph('PIEZAS A COTIZAR', self._estilos['TituloFormato']),
            '',
            '',
        ]
        columnas = [
            Paragraph('Componente', self._estilos['CeldaLabelCentro']),
            Paragraph('X', self._estilos['CeldaLabelCentro']),
            Paragraph('Número de parte / notas', self._estilos['CeldaLabelCentro']),
        ]
        data = [encabezado, columnas]
        # Índice de fila Platypus (0 = título, 1 = columnas, 2+ = piezas).
        colores_dpn: List[tuple] = []

        for i, fila in enumerate(filas):
            marca = Paragraph('X', self._estilos['MarcaX']) if fila['seleccionado'] else ''
            data.append([
                Paragraph(self._esc(fila['etiqueta']), self._estilos['CeldaValor']),
                marca,
                Paragraph(self._esc(fila['dpn']), self._estilos['CeldaValor']),
            ])
            if fila['seleccionado']:
                # El color es el TIPO de pieza, aunque el DPN venga vacío.
                color = COLOR_VERDE_NECESARIA if fila['es_necesaria'] else COLOR_AMARILLO_OPCIONAL
                colores_dpn.append((i + 2, color))

        tabla = Table(
            data,
            colWidths=[ancho_nombre, ancho_check, ancho_dpn],
            repeatRows=2,
        )
        estilos = [
            ('SPAN', (0, 0), (-1, 0)),
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_NAVY),
            ('BACKGROUND', (0, 1), (-1, 1), COLOR_NAVY_SUAVE),
            ('BACKGROUND', (0, 2), (0, -1), COLOR_NAVY_SUAVE),
            ('ALIGN', (1, 1), (1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            # Filas apretadas a propósito: 18 piezas + leyenda deben caber
            # en la misma hoja cuando el diagnóstico es corto.
            ('TOPPADDING', (0, 2), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 2), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, 1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, 1), 3),
        ]
        for indice, color in colores_dpn:
            estilos.append(('BACKGROUND', (2, indice), (2, indice), color))
        tabla.setStyle(TableStyle(estilos))
        return [CondPageBreak(28 * mm), tabla]

    def _construir_leyenda(self) -> Table:
        """Cuadros verde y amarillo con el mismo texto que leía el cliente."""
        data = [[
            '',
            Paragraph('= Pieza necesaria', self._estilos['Leyenda']),
            '',
            Paragraph('= Pieza opcional / recomendada', self._estilos['Leyenda']),
        ]]
        tabla = Table(
            data,
            colWidths=[4 * mm, 42 * mm, 4 * mm, None],
            rowHeights=[5 * mm],
        )
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_VERDE_NECESARIA),
            ('BACKGROUND', (2, 0), (2, 0), COLOR_AMARILLO_OPCIONAL),
            ('BOX', (0, 0), (0, 0), 0.4, COLOR_GRIS_BORDE),
            ('BOX', (2, 0), (2, 0), 0.4, COLOR_GRIS_BORDE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (1, 0), (1, 0), 3),
            ('LEFTPADDING', (3, 0), (3, 0), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        return tabla

    def _construir_contacto(self) -> Table:
        """
        Nombre corto de la empresa y correo del empleado, en una fila.

        No se inserta en el flujo normal: ContactoAlFondo la dibuja
        pegada al fondo de la última hoja, encima del pie.
        """
        ancho = self._ancho_util()
        etiqueta = 22 * mm
        if self.email_empleado:
            ancho_empresa = ancho * 0.42 - etiqueta
            ancho_correo = ancho * 0.58 - etiqueta
            data = [[
                Paragraph('Empresa', self._estilos['CeldaLabel']),
                Paragraph(self._esc(self.empresa_nombre_corto), self._estilos['CeldaValor']),
                Paragraph('Contacto', self._estilos['CeldaLabel']),
                Paragraph(self._esc(self.email_empleado), self._estilos['CeldaValor']),
            ]]
            anchos = [etiqueta, ancho_empresa, etiqueta, ancho_correo]
        else:
            data = [[
                Paragraph('Empresa', self._estilos['CeldaLabel']),
                Paragraph(self._esc(self.empresa_nombre_corto), self._estilos['CeldaValor']),
            ]]
            anchos = [etiqueta, None]
        tabla = Table(data, colWidths=anchos)
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), COLOR_NAVY_SUAVE),
            ('BACKGROUND', (1, 0), (1, 0), COLOR_GRIS_ALT),
            ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        if self.email_empleado:
            tabla.setStyle(TableStyle([
                ('BACKGROUND', (2, 0), (2, 0), COLOR_NAVY_SUAVE),
                ('BACKGROUND', (3, 0), (3, 0), COLOR_GRIS_ALT),
            ]))
        return tabla
