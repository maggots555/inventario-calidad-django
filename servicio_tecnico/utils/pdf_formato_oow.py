"""
Generador PDF — Formato de Servicio Fuera de Garantía (OOW)

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Este módulo crea el PDF profesional del formato OOW con el MISMO estilo
visual que las cotizaciones al cliente (Platypus + headers navy #003366).

NO usa el layout “papel” de RHITSO (canvas manual). Usa tablas y párrafos
como PDFCotizacionCliente.

Estructura (páginas bien separadas, sin encimar):
1. Página 1 — Header + título + QR|orden (dos columnas) + cliente
   + equipo + accesorios + firmas en blanco (técnico y cliente, a mano)
2. Página siguiente — Daños estéticos + observaciones técnicas + firma digital
   (si no hay foto de escaneo, muestra aviso PC Audit en observaciones)
3. Página siguiente — Resultado del escaneo (solo si hay fotos)
4. Página(s) — Aviso de Privacidad + firma digital del cliente
5. Página(s) extra — Promociones / catálogo (QR fijos + campañas vigentes)
"""

from __future__ import annotations

import io
import logging
from typing import Any, Dict, List, Optional

from django.contrib.staticfiles import finders
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config.constants import (
    AVISO_PRIVACIDAD_OOW_MX,
    AVISO_PRIVACIDAD_OOW_PLACEHOLDER_OTROS,
    OOW_PROMO_QR_FIJOS,
    OOW_PROMO_TITULO_HOJA,
    catalogo_vistas_dano_estetico,
)
from config.paises_config import get_pais_actual
from servicio_tecnico.services.vistas_dano import vistas_dano_para_pdf

logger = logging.getLogger('servicio_tecnico')

# Colores corporativos (idénticos a cotización cliente)
COLOR_NAVY = colors.HexColor('#003366')
COLOR_NAVY_LIGHT = colors.HexColor('#1d4e8f')
COLOR_NAVY_SUAVE = colors.HexColor('#E8EEF5')  # Fondo suave columna labels
COLOR_GRIS_ALT = colors.HexColor('#F2F2F2')
COLOR_GRIS_BORDE = colors.HexColor('#CCCCCC')
COLOR_GRIS_TEXTO = colors.HexColor('#888888')  # Accesorio = NO
COLOR_AMARILLO_BG = colors.HexColor('#FFF2CC')
COLOR_ROJO_BG = colors.HexColor('#FDECEC')
COLOR_ROJO_ALERTA = colors.HexColor('#C00000')
COLOR_BLANCO = colors.white
COLOR_NEGRO = colors.black

MARGEN = 15 * mm
MARGEN_INFERIOR = 20 * mm  # Extra espacio para pie de página (folio + nº página)


class PDFFormatoServicioOOW:
    """
    Genera el PDF del Formato Digital OOW con estilo cotizaciones.

    Args:
        formato: instancia FormatoServicioOOW (con orden y vistas relacionadas)

    Efectos secundarios:
        Ninguno sobre BD; solo construye un BytesIO en memoria.
    """

    def __init__(self, formato):
        """
        Args:
            formato: FormatoServicioOOW
        """
        self.formato = formato
        self.orden = formato.orden
        self.detalle = formato.orden.detalle_equipo
        self.pais_config = get_pais_actual()
        self._estilos = getSampleStyleSheet()
        self._crear_estilos()

    def generar_pdf(self) -> Dict[str, Any]:
        """
        Construye el PDF completo en un buffer BytesIO.

        Returns:
            dict: {success, buffer, nombre_archivo} o {success: False, error}
        """
        try:
            buffer = io.BytesIO()
            # Folio visible en pie y metadatos (SICSER / orden cliente / interno)
            folio = (
                self.detalle.folio_sicser
                or self.detalle.orden_cliente
                or self.orden.numero_orden_interno
            )
            empresa = self.pais_config.get(
                'empresa_nombre',
                'SIC Comercialización y Servicios de México SC',
            )
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                leftMargin=MARGEN,
                rightMargin=MARGEN,
                topMargin=MARGEN,
                bottomMargin=MARGEN_INFERIOR,
                title=f'Formato OOW — {folio}',
                author=empresa,
                subject='Formato de servicio fuera de garantía',
                creator='SIGMA',
            )

            elementos: List = []
            # --- Página 1: datos generales ---
            elementos += self._construir_header()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_titulo()
            elementos.append(Spacer(1, 3 * mm))
            # EXPLICACIÓN PARA PRINCIPIANTES:
            # QR a la izquierda y Fecha/Número a la derecha: el folio no
            # necesita una barra navy a todo el ancho. Si no hay enlace,
            # la orden vuelve a ir full-width (sin hueco vacío).
            elementos += self._construir_portada_qr_y_orden()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._envolver_seccion(self._construir_datos_cliente())
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._envolver_seccion(self._construir_datos_equipo())
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._envolver_seccion(self._construir_accesorios())
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._envolver_seccion(
                self._construir_firmas_manuscritas_portada()
            )

            # --- Página de daños + observaciones + firma (como el formato papel) ---
            elementos.append(PageBreak())
            elementos += self._construir_danos()
            elementos.append(Spacer(1, 4 * mm))
            # KeepTogether: observaciones y firma intentan ir juntas al pie
            elementos.append(KeepTogether(self._construir_observaciones_y_firma()))

            # --- Escaneo: solo si hay fotos ---
            if self._tiene_fotos_escaneo():
                elementos.append(PageBreak())
                elementos += self._construir_escaneo()

            # --- Aviso de privacidad ---
            elementos += self._construir_aviso_privacidad()

            # --- Promociones / catálogo (después del aviso; no tumba el PDF) ---
            # EXPLICACIÓN PARA PRINCIPIANTES:
            # Esta hoja es publicidad. Si falla (BD, archivo, ReportLab), el
            # aviso de privacidad y el resto del formato igual deben salir.
            try:
                elementos += self._construir_promociones()
            except Exception as exc:
                logger.warning(
                    '[PDF_FORMATO_OOW] Hoja de promociones omitida: %s',
                    exc,
                    exc_info=True,
                )

            # EXPLICACIÓN PARA PRINCIPIANTES:
            # onFirstPage/onLaterPages dibujan el pie en CADA hoja con canvas
            # (fuera del flujo de párrafos). Así siempre sale folio + nº página.
            doc.build(
                elementos,
                onFirstPage=self._dibujar_pie_pagina,
                onLaterPages=self._dibujar_pie_pagina,
            )
            buffer.seek(0)

            nombre = f"FormatoOOW_{self.orden.numero_orden_interno}.pdf"
            return {
                'success': True,
                'buffer': buffer,
                'nombre_archivo': nombre,
            }
        except Exception as exc:
            logger.error('[PDF_FORMATO_OOW] Error: %s', exc, exc_info=True)
            return {'success': False, 'error': str(exc), 'buffer': None}

    def _dibujar_pie_pagina(self, canvas, doc) -> None:
        """
        Pie corporativo: folio a la izquierda, «Página N» a la derecha.

        Args:
            canvas: canvas de ReportLab de la página actual
            doc: SimpleDocTemplate (para márgenes y número de página)

        Efectos secundarios:
            Dibuja sobre el canvas de la página (línea + textos del pie).
        """
        canvas.saveState()
        folio = (
            self.detalle.folio_sicser
            or self.detalle.orden_cliente
            or self.orden.numero_orden_interno
            or ''
        )
        y_pie = 10 * mm
        x_izq = MARGEN
        x_der = letter[0] - MARGEN

        # Línea sutil arriba del pie
        canvas.setStrokeColor(COLOR_GRIS_BORDE)
        canvas.setLineWidth(0.5)
        canvas.line(x_izq, y_pie + 5 * mm, x_der, y_pie + 5 * mm)

        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(COLOR_NAVY)
        canvas.drawString(x_izq, y_pie, f'Formato OOW · {folio}')
        canvas.drawRightString(x_der, y_pie, f'Página {doc.page}')
        canvas.restoreState()

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
            # Un poco más chico: las barras navy se veían muy altas respecto al texto
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
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaValor',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            leading=10,
        ))
        # Accesorios: SI resalta en navy; NO queda gris para escanear más rápido
        self._estilos.add(ParagraphStyle(
            'AccesorioSi',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NAVY,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'AccesorioNo',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_GRIS_TEXTO,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'CuerpoNormal',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_JUSTIFY,
            leading=11,
        ))
        self._estilos.add(ParagraphStyle(
            'CuerpoChico',
            fontName='Helvetica',
            fontSize=7,
            textColor=COLOR_NEGRO,
            alignment=TA_JUSTIFY,
            leading=9,
            spaceAfter=2,
        ))
        self._estilos.add(ParagraphStyle(
            'AvisoTitulo',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            spaceAfter=4,
        ))
        self._estilos.add(ParagraphStyle(
            'FirmaLabel',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
        ))
        self._estilos.add(ParagraphStyle(
            'QrTitulo',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=COLOR_NAVY,
            alignment=TA_LEFT,
            leading=12,
        ))
        self._estilos.add(ParagraphStyle(
            'QrLeyenda',
            fontName='Helvetica',
            fontSize=7.5,
            textColor=COLOR_NEGRO,
            alignment=TA_LEFT,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'PromoLeyenda',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
            leading=11,
        ))

    def _tiene_fotos_escaneo(self) -> bool:
        """True si la orden tiene al menos una foto de escaneo OOW."""
        from servicio_tecnico.models import ImagenOrden
        return ImagenOrden.objects.filter(
            orden=self.orden,
            tipo='escaneo_oow',
        ).exists()

    def _envolver_seccion(self, partes: List) -> List:
        """
        Agrupa header + contenido de una sección para que no se partan
        de forma fea (título en una página y tabla en otra).

        EXPLICACIÓN PARA PRINCIPIANTES:
        KeepTogether pide a ReportLab que intente mantener juntos estos
        bloques. Si no caben en lo que queda de página, salta a la siguiente.
        """
        if not partes:
            return []
        return [KeepTogether(partes)]

    def _crear_header_seccion(
        self,
        titulo: str,
        ancho: Optional[float] = None,
    ) -> Table:
        """
        Barra navy de sección (igual que cotizaciones).

        Args:
            titulo: Texto del encabezado
            ancho: Ancho de la barra en puntos. Si es None, usa toda la hoja.
                Obligatorio cuando la barra va DENTRO de una columna más
                estrecha: ReportLab no recorta, se sale y tapa lo de al lado
                (mismo cuidado que el PDF de venta mostrador).

        Returns:
            Table de una celda con fondo navy
        """
        if ancho is None:
            ancho = letter[0] - (2 * MARGEN)
        tabla = Table(
            [[Paragraph(titulo, self._estilos['TituloFormato'])]],
            colWidths=[ancho],
        )
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_NAVY),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            # Padding reducido (antes 6): barras más compactas, sin verse apretadas
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ]))
        return tabla

    def _esc(self, texto: Any) -> str:
        """Escapa texto para Paragraph XML-ish de ReportLab."""
        if texto is None:
            return ''
        s = str(texto)
        return (
            s.replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
        )

    # ------------------------------------------------------------------ secciones

    def _obtener_logo(self) -> Optional[RLImage]:
        """
        Carga logo SIC PNG desde static si existe.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Si forzamos width y height sin kind='proportional', ReportLab estira
        la imagen. Con proportional respeta la proporción real del PNG y
        la altura (15 mm) es solo un tope máximo — igual que en cotizaciones.
        """
        ruta = finders.find('images/logos/logo_sic.png')
        if not ruta:
            return None
        try:
            # Un poco menos alto (15 mm) para que no se vea estirado en vertical
            img = RLImage(ruta, width=45 * mm, height=15 * mm, kind='proportional')
            return img
        except Exception:
            return None

    def _construir_header(self) -> List:
        """Logo + nombre de empresa (sin caja de orden; esa va debajo del título)."""
        elementos: List = []
        logo = self._obtener_logo()
        empresa = self.pais_config.get(
            'empresa_nombre',
            'SIC Comercialización y Servicios de México SC',
        )

        if logo:
            fila = [[logo, Paragraph(self._esc(empresa), self._estilos['EmpresaHeader'])]]
        else:
            fila = [['', Paragraph(self._esc(empresa), self._estilos['EmpresaHeader'])]]

        tabla = Table(fila, colWidths=[55 * mm, None])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (0, 0), 0),
        ]))
        elementos.append(tabla)
        elementos.append(Spacer(1, 2 * mm))
        elementos.append(HRFlowable(width='100%', thickness=1, color=COLOR_GRIS_BORDE))
        return elementos

    def _construir_titulo(self) -> List:
        """Título principal navy."""
        return [self._crear_header_seccion(
            'FORMATO DE SERVICIO FUERA DE GARANTÍA CON COSTO'
        )]

    def _construir_tarjeta_seguimiento(
        self,
        ancho: Optional[float] = None,
    ) -> List:
        """
        Tarjeta de página 1: QR + texto para consultar el estatus.

        Objetivo de negocio:
            El cliente se lleva esta hoja. Escanea (papel) o toca el QR
            (PDF en el celular) y abre el portal de seguimiento.

        Args:
            ancho: Ancho de la tarjeta en puntos. None = toda la hoja.
                En la portada de dos columnas se pasa el ancho de la
                columna izquierda para que el fondo navy no se desborde.

        Returns:
            Lista de flowables, o vacía si la orden aún no tiene enlace.
        """
        from servicio_tecnico.services.enlace_seguimiento import (
            url_seguimiento_de_orden,
        )
        from servicio_tecnico.utils.qr_pdf import imagen_qr_para_pdf

        url = url_seguimiento_de_orden(self.orden)
        if not url:
            return []

        # 22 mm: mismo tamaño que el QR de venta mostrador / garantía.
        # Sigue siendo fácil de escanear en papel (ERROR_CORRECT_M) y
        # ocupa menos la tarjeta de la portada.
        qr_img = imagen_qr_para_pdf(url, lado_mm=22)
        titulo = Paragraph(
            'Consulta el estatus de tu servicio',
            self._estilos['QrTitulo'],
        )
        leyenda = Paragraph(
            'Escanea este código con tu celular para ver el avance de tu equipo.',
            self._estilos['QrLeyenda'],
        )
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # ReportLab suma el padding DENTRO de la celda. Si la tabla de
        # texto mide lo mismo que la columna Y además tiene padding (o
        # el default de 6 pt), el párrafo se sale del recuadro azul.
        # Por eso restamos el padding al ancho del bloque de texto.
        ancho_util = ancho if ancho is not None else (letter[0] - (2 * MARGEN))
        ancho_qr = 26 * mm
        ancho_texto = ancho_util - ancho_qr
        pad_texto_izq = 3
        pad_texto_der = 6
        bloque_texto = Table(
            [[titulo], [leyenda]],
            colWidths=[ancho_texto - pad_texto_izq - pad_texto_der],
        )
        bloque_texto.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        # Columna QR + texto: fondo navy suave, mismo lenguaje visual que el resto.
        celda_qr = qr_img if qr_img is not None else ''
        fila = Table(
            [[celda_qr, bloque_texto]],
            colWidths=[ancho_qr, ancho_texto],
        )
        fila.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_NAVY_SUAVE),
            ('BOX', (0, 0), (-1, -1), 0.7, COLOR_NAVY),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            # Padding en TODAS las celdas (si no, la de texto usa 6 pt
            # de default y el párrafo se sale ~2 mm del borde).
            ('LEFTPADDING', (0, 0), (0, 0), 2),
            ('RIGHTPADDING', (0, 0), (0, 0), 2),
            ('LEFTPADDING', (1, 0), (1, 0), pad_texto_izq),
            ('RIGHTPADDING', (1, 0), (1, 0), pad_texto_der),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        return [KeepTogether([fila])]

    def _construir_orden_servicio(
        self,
        ancho: Optional[float] = None,
        anchos_pares: Optional[List[float]] = None,
    ) -> List:
        """
        Sección Orden de servicio (barra navy + Fecha / Número).

        EXPLICACIÓN PARA PRINCIPIANTES:
        La fecha sale de finalizado_en (fecha real de cierre), no de
        "hoy", para que regenerar no la cambie. Cuando va a la derecha
        del QR hay que pasar `ancho` de ESA columna: si no, la barra
        navy se dibuja a todo el ancho de la hoja y tapa el QR.

        Args:
            ancho: Ancho de la barra navy. None = hoja completa.
            anchos_pares: [label, valor] en puntos. None = 45 mm + resto.
        """
        elementos = [
            self._crear_header_seccion('Orden de servicio', ancho=ancho),
            Spacer(1, 2 * mm),
        ]
        momento = self.formato.finalizado_en or timezone.now()
        # localtime: muestra la fecha en zona horaria del servidor/Django
        fecha_txt = timezone.localtime(momento).strftime('%Y-%m-%d')
        folio = (
            self.detalle.folio_sicser
            or self.detalle.orden_cliente
            or self.orden.numero_orden_interno
        )
        pares = [
            ('Fecha', fecha_txt),
            ('Número de orden', folio),
        ]
        elementos.append(self._tabla_pares(pares, col_widths=anchos_pares))
        return elementos

    def _construir_portada_qr_y_orden(self) -> List:
        """
        Fila de portada: QR de seguimiento a la izquierda, orden a la derecha.

        Objetivo de negocio:
            El cliente ve el QR y el folio en el mismo renglón, en dos
            columnas del mismo ancho. Fecha y número no llevan barra
            navy a toda la hoja.

        Returns:
            Lista de flowables (KeepTogether). Sin enlace de seguimiento,
            la orden vuelve a ir a todo el ancho para no dejar un hueco.
        """
        ancho_util = letter[0] - (2 * MARGEN)
        hueco = 2 * mm
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Mitad y mitad (menos el hueco de 2 mm). Así QR y «Orden de
        # servicio» miden lo mismo: ni la tarjeta azul se come la hoja,
        # ni el folio se ve más ancho que el código.
        ancho_izq = (ancho_util - hueco) / 2
        ancho_der = ancho_util - hueco - ancho_izq

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Si no hay URL de seguimiento, no hay QR. En ese caso no armamos
        # dos columnas: la sección Orden de servicio llena la hoja, igual
        # que antes de este layout.
        tarjeta_qr = self._construir_tarjeta_seguimiento(ancho=ancho_izq)
        if not tarjeta_qr:
            return self._envolver_seccion(self._construir_orden_servicio())

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # KeepTogether DENTRO de una celda de Table hace que ReportLab
        # calcule una altura absurda (~16 millones de puntos) y el PDF
        # truena. Por eso sacamos la tabla interna del QR y metemos la
        # orden en una tabla de 1 columna (no una lista suelta).
        celda_qr = tarjeta_qr[0]
        if isinstance(celda_qr, KeepTogether):
            contenido_qr = list(celda_qr._content or [])
            celda_qr = contenido_qr[0] if contenido_qr else ''

        # Labels más estrechos (~28 mm) para que el folio largo haga wrap
        # dentro de la columna, no se salga encima del QR.
        seccion_orden = self._construir_orden_servicio(
            ancho=ancho_der,
            anchos_pares=[28 * mm, ancho_der - 28 * mm],
        )
        celda_orden = Table(
            [[parte] for parte in seccion_orden],
            colWidths=[ancho_der],
        )
        celda_orden.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        fila = Table(
            [[celda_qr, '', celda_orden]],
            colWidths=[ancho_izq, hueco, ancho_der],
        )
        fila.setStyle(TableStyle([
            # MIDDLE: si la orden es más alta, el QR queda centrado en vertical
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return [KeepTogether([fila])]

    def _fila_dato(self, label: str, valor: str) -> list:
        return [
            Paragraph(self._esc(label), self._estilos['CeldaLabel']),
            Paragraph(self._esc(valor or '—'), self._estilos['CeldaValor']),
        ]

    def _tabla_pares(
        self,
        pares: List[tuple],
        valores_flowables: bool = False,
        col_widths: Optional[List[float]] = None,
    ) -> Table:
        """
        Tabla 2 columnas label|valor con jerarquía visual.

        Args:
            pares: lista de (label, valor). Si valores_flowables=False, valor es str.
            valores_flowables: si True, el segundo elemento ya es un flowable
                (p. ej. Paragraph SI/NO estilizado).
            col_widths: [label, valor] en puntos. None = 45 mm + resto.
                En la columna derecha de la portada se pasan anchos
                explícitos para que el folio no desborde.

        Returns:
            Table ReportLab lista para insertar en el documento.
        """
        if valores_flowables:
            data = [
                [
                    Paragraph(self._esc(label), self._estilos['CeldaLabel']),
                    valor,
                ]
                for label, valor in pares
            ]
        else:
            data = [self._fila_dato(l, v) for l, v in pares]

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # `None` en colWidths de ReportLab significa "el espacio que sobre".
        # Fuera de una celda estrecha está bien; dentro, mejor pasar mm fijos.
        if col_widths is None:
            col_widths = [45 * mm, None]
        tabla = Table(data, colWidths=col_widths)
        estilos = [
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            # Columna de labels: fondo navy suave (jerarquía sin cambiar layout)
            ('BACKGROUND', (0, 0), (0, -1), COLOR_NAVY_SUAVE),
        ]
        # Filas alternadas solo en la columna de valores
        for i in range(len(data)):
            if i % 2 == 0:
                estilos.append(('BACKGROUND', (1, i), (1, i), COLOR_GRIS_ALT))
        tabla.setStyle(TableStyle(estilos))
        return tabla

    def _construir_datos_cliente(self) -> List:
        elementos = [self._crear_header_seccion('Datos del cliente'), Spacer(1, 2 * mm)]
        d = self.detalle
        # Import diferido para evitar ciclo con services.formato_oow → este PDF
        from servicio_tecnico.services.formato_oow import lista_emails_envio
        pares = [
            ('Nombre', d.nombre_cliente),
            ('Razón social', d.razon_social_cliente),
            ('RFC', d.rfc_cliente),
            ('Email de contacto', d.email_cliente),
            ('Teléfono(s)', d.telefono_cliente),
            ('Dirección', d.direccion_cliente),
            ('Email envío formato', ', '.join(lista_emails_envio(self.formato)) or '—'),
        ]
        elementos.append(self._tabla_pares(pares))
        return elementos

    def _construir_datos_equipo(self) -> List:
        elementos = [self._crear_header_seccion('Datos del equipo'), Spacer(1, 2 * mm)]
        d = self.detalle
        pares = [
            ('Marca', d.marca),
            ('Modelo', d.modelo),
            ('Service Tag / Serie', d.numero_serie),
            ('Tipo', d.tipo_equipo),
            ('Contraseña', self.formato.contrasena_equipo or 'N/A'),
        ]
        elementos.append(self._tabla_pares(pares))
        elementos.append(Spacer(1, 2 * mm))
        diag = d.diagnostico_sic or d.falla_principal or ''
        elementos.append(Paragraph('<b>Diagnóstico / Instrucciones</b>', self._estilos['CeldaLabel']))
        elementos.append(Spacer(1, 1 * mm))
        elementos.append(Paragraph(self._esc(diag) or '—', self._estilos['CuerpoNormal']))
        return elementos

    def _construir_accesorios(self) -> List:
        """
        Accesorios entregados: solo los marcados, con el número de serie en la celda.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Ya no listamos Maletín/Mouse/etc. en NO. Si el cliente no lo trajo,
        esa fila no existe. El número de serie (o el detalle de “Otros”)
        va en la columna derecha, no abajo de la tabla.
        """
        # Import diferido: el servicio también importa este PDF al finalizar
        from servicio_tecnico.services.formato_oow import filas_accesorios_pdf

        elementos = [self._crear_header_seccion('Accesorios entregados'), Spacer(1, 2 * mm)]
        filas = filas_accesorios_pdf(self.formato)
        if not filas:
            elementos.append(Paragraph(
                'Sin accesorios entregados',
                self._estilos['CeldaValor'],
            ))
            return elementos

        pares = [
            (
                etiqueta,
                Paragraph(self._esc(valor), self._estilos['AccesorioSi']),
            )
            for etiqueta, valor in filas
        ]
        elementos.append(self._tabla_pares(pares, valores_flowables=True))
        return elementos

    def _construir_firmas_manuscritas_portada(self) -> List:
        """
        Leyenda de entrega + dos recuadros en blanco (se firman a mano).

        Objetivo de negocio:
            Al entregar el equipo ya reparado, técnico y cliente firman
            en papel. No se pinta la firma digital aquí: van vacíos.

        Returns:
            Lista de flowables (leyenda + tabla de 2 columnas).
        """
        # Misma jerarquía visual que “ACEPTO… ENTREGO” de la hoja de daños
        estilo_acepta = ParagraphStyle(
            'AceptaRecepcionOow',
            parent=self._estilos['CeldaLabel'],
            alignment=TA_CENTER,
            fontSize=8,
            leading=10,
        )
        leyenda = Paragraph(
            'ACEPTO LAS CONDICIONES EN LAS QUE RECIBO EL EQUIPO.',
            estilo_acepta,
        )

        # Paso 1: el ancho útil se parte en dos columnas iguales
        ancho_util = letter[0] - (2 * MARGEN)
        ancho_col = (ancho_util - 4 * mm) / 2
        alto_linea = 16 * mm

        izq = self._bloque_columna_firma(
            'Técnico que diagnostica y repara',
            imagen=None,
            ancho=ancho_col,
            alto_espacio=alto_linea,
        )
        der = self._bloque_columna_firma(
            'Firma del cliente',
            imagen=None,
            ancho=ancho_col,
            alto_espacio=alto_linea,
        )
        # Paso 2: leyenda + ambas firmas viajan juntas (KeepTogether lo aplica el caller)
        tabla = Table(
            [[izq, der]],
            colWidths=[ancho_util / 2, ancho_util / 2],
        )
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (0, 0), 0.5, COLOR_GRIS_BORDE),
            ('BOX', (1, 0), (1, 0), 0.5, COLOR_GRIS_BORDE),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        return [leyenda, Spacer(1, 3 * mm), tabla]

    def _texto_aviso_pc_audit(self) -> str:
        """Texto del aviso cuando no se pudo usar / no hay escaneo PC Audit."""
        return (
            'NO SE UTILIZÓ EL APLICATIVO PC AUDIT PARA IDENTIFICAR LAS '
            'CARACTERÍSTICAS DEL HARDWARE Y SOFTWARE INSTALADO DEBIDO A QUE '
            'EL EQUIPO NO ENCIENDE, NO TIENE SISTEMA OPERATIVO WINDOWS O SU '
            'FALLA NO PERMITE UTILIZAR LA HERRAMIENTA.'
        )

    def _construir_observaciones(self) -> List:
        """Compatibilidad: delega al bloque de observaciones."""
        return self._construir_bloque_observaciones()

    def _construir_bloque_observaciones(self) -> List:
        """
        Observaciones técnicas + aviso PC Audit si aplica.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Si NO hay foto de “Resultado del escaneo”, se muestra el aviso amarillo
        (como en el formato papel). También si el técnico marcó disclaimer_pc_audit.
        """
        elementos = [
            self._crear_header_seccion('Observaciones técnicas'),
            Spacer(1, 2 * mm),
        ]
        obs = (self.formato.observaciones_tecnicas or '').strip()
        elementos.append(Paragraph(
            self._esc(obs) if obs else '—',
            self._estilos['CuerpoChico'],
        ))

        sin_escaneo = not self._tiene_fotos_escaneo()
        mostrar_aviso = sin_escaneo or bool(self.formato.disclaimer_pc_audit)
        if mostrar_aviso:
            elementos.append(Spacer(1, 2 * mm))
            bloque = Table(
                [[Paragraph(self._texto_aviso_pc_audit(), self._estilos['CuerpoChico'])]],
                colWidths=[letter[0] - 2 * MARGEN],
            )
            bloque.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), COLOR_AMARILLO_BG),
                ('BOX', (0, 0), (-1, -1), 0.8, COLOR_NAVY),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
                ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            elementos.append(bloque)
        return elementos

    def _construir_observaciones_y_firma(self) -> List:
        """
        Pie del registro de daños: observaciones + aceptación + firma cliente.

        Objetivo: que quepa junto a los diagramas, como en el formato papel SICSER.
        """
        elementos: List = []
        elementos += self._construir_bloque_observaciones()
        elementos.append(Spacer(1, 3 * mm))
        elementos += self._construir_aceptacion_y_firmas(compacto=True)
        return elementos

    def _construir_danos(self) -> List:
        """
        Página dedicada al registro de daños estéticos.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Cada par de diagramas va en un KeepTogether para que una imagen
        no se corte a la mitad ni se encime con el título de otra.
        """
        elementos = [
            self._crear_header_seccion('Registro de daños estéticos'),
            Spacer(1, 2 * mm),
        ]
        vistas = vistas_dano_para_pdf(self.formato)
        if not vistas:
            elementos.append(Paragraph(
                'Sin anotaciones de daños en diagramas.',
                self._estilos['CeldaValor'],
            ))
            return elementos

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # vistas_dano_para_pdf ya dejó solo las caras del tipo actual
        # (laptop / escritorio / AIO) y las ordenó. Así el PDF no mezcla
        # un Top Cover de laptop si después se cambió a escritorio.
        tipo = (self.formato.tipo_diagrama or 'laptop').lower()
        labels = dict(catalogo_vistas_dano_estetico(tipo))
        bloques_vista = []
        for vista in vistas:
            try:
                path = vista.imagen_anotada.path
                # Compactas para dejar espacio a observaciones + firma en la misma hoja
                img = RLImage(path, width=72 * mm, height=42 * mm, kind='proportional')
            except Exception:
                img = Paragraph('(imagen no disponible)', self._estilos['CeldaValor'])
            # Solo el nombre de la pieza (Pantalla, Top Cover…). El tipo de
            # daño (Desgaste, etc.) se ve en el diagrama anotado; no lo
            # repetimos en el título de la tarjeta.
            titulo = labels.get(vista.clave_vista, vista.clave_vista)
            # Tarjeta con borde: título + imagen (no se mezcla con la de al lado)
            tarjeta = Table(
                [
                    [Paragraph(f'<b>{self._esc(titulo)}</b>', self._estilos['CeldaLabel'])],
                    [img],
                ],
                colWidths=[85 * mm],
            )
            tarjeta.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.6, COLOR_GRIS_BORDE),
                ('BACKGROUND', (0, 0), (-1, 0), COLOR_GRIS_ALT),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            bloques_vista.append(tarjeta)

        # Filas de 2 columnas; cada fila KeepTogether para no partir una imagen
        for i in range(0, len(bloques_vista), 2):
            izq = bloques_vista[i]
            der = bloques_vista[i + 1] if i + 1 < len(bloques_vista) else ''
            fila = Table(
                [[izq, der]],
                colWidths=['50%', '50%'],
            )
            fila.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ]))
            elementos.append(KeepTogether([fila, Spacer(1, 2 * mm)]))

        return elementos

    def _construir_escaneo(self) -> List:
        """
        Sección con la(s) foto(s) del resultado de escaneo (PC Audit / similar).

        EXPLICACIÓN PARA PRINCIPIANTES:
        Las fotos se guardan como ImagenOrden con tipo 'escaneo_oow'.
        Van en su propia página para no encimarse con daños ni firmas.
        """
        from servicio_tecnico.models import ImagenOrden

        elementos = [
            self._crear_header_seccion('Resultado del escaneo'),
            Spacer(1, 4 * mm),
        ]
        imagenes = list(
            ImagenOrden.objects.filter(
                orden=self.orden,
                tipo='escaneo_oow',
            ).order_by('-fecha_subida')[:4]
        )
        if not imagenes:
            elementos.append(Paragraph(
                'Sin foto de resultado de escaneo adjunta.',
                self._estilos['CeldaValor'],
            ))
            return elementos

        for img_orden in imagenes:
            try:
                path = img_orden.imagen.path
                rl_img = RLImage(path, width=140 * mm, height=160 * mm, kind='proportional')
            except Exception:
                rl_img = Paragraph('(imagen no disponible)', self._estilos['CeldaValor'])
            etiqueta = img_orden.descripcion or 'Resultado del escaneo'
            tarjeta = Table(
                [
                    [Paragraph(f'<b>{self._esc(etiqueta)}</b>', self._estilos['CeldaLabel'])],
                    [rl_img],
                ],
                colWidths=[letter[0] - 2 * MARGEN],
            )
            tarjeta.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.6, COLOR_GRIS_BORDE),
                ('BACKGROUND', (0, 0), (-1, 0), COLOR_GRIS_ALT),
                ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            # Una foto por bloque: si no cabe, pasa sola a la siguiente página
            elementos.append(KeepTogether([tarjeta, Spacer(1, 5 * mm)]))

        return elementos

    def _construir_aceptacion_y_firmas(self, compacto: bool = False) -> List:
        """
        Aceptación de condiciones + firma del cliente.

        Args:
            compacto: True cuando va al pie de la página de daños (menos padding).

        Efectos secundarios:
            Ninguno (solo arma elementos Platypus para el PDF).
        """
        elementos = [
            self._crear_header_seccion('Aceptación y firma del cliente'),
            Spacer(1, 2 * mm if compacto else 4 * mm),
        ]
        estilo_acepta = ParagraphStyle(
            'AceptaCondicionesOow',
            parent=self._estilos['CeldaLabel'],
            alignment=TA_CENTER,
            fontSize=8 if compacto else 9,
            leading=10,
        )
        elementos.append(Paragraph(
            'ACEPTO LAS CONDICIONES EN LAS QUE ENTREGO EL EQUIPO AL CENTRO DE SERVICIO.',
            estilo_acepta,
        ))
        elementos.append(Spacer(1, 4 * mm if compacto else 8 * mm))

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Ancho fijo de la firma para que imagen, línea y texto
        # compartan la misma columna centrada dentro del recuadro.
        ancho_firma = 45 * mm if compacto else 50 * mm
        alto_firma = 18 * mm if compacto else 22 * mm
        firma_cli = self._imagen_firma(
            self.formato.firma_cliente,
            ancho=ancho_firma,
            alto=alto_firma,
        )
        tabla_firma = self._bloque_columna_firma(
            'FIRMA CLIENTE',
            imagen=firma_cli,
            ancho=ancho_firma,
            alto_espacio=alto_firma,
        )

        pad = 6 if compacto else 10
        # Recuadro a todo el ancho; la firma queda centrada dentro
        tabla = Table(
            [[tabla_firma]],
            colWidths=[letter[0] - 2 * MARGEN],
        )
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
            ('TOPPADDING', (0, 0), (-1, -1), pad),
            ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
        ]))
        elementos.append(tabla)
        # "¿Cómo se enteró?" ya no se imprime en el PDF (sigue en pantalla/BD).
        return elementos

    def _bloque_columna_firma(
        self,
        etiqueta: str,
        imagen: Optional[RLImage],
        ancho: float,
        alto_espacio: float,
    ) -> Table:
        """
        Una columna de firma: imagen o hueco + línea + etiqueta.

        Args:
            etiqueta: Texto debajo de la línea (ej. Firma del cliente)
            imagen: Firma digital, o None para dejar el espacio en blanco
            ancho: Ancho de la columna
            alto_espacio: Alto del hueco si no hay imagen (firma a mano)

        Returns:
            Table de una columna, lista para meter en otra tabla.
        """
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Si no hay PNG, Spacer reserva el mismo alto para que se pueda
        # firmar a lápiz. La línea y la etiqueta quedan centradas.
        celda_superior = imagen if imagen is not None else Spacer(1, alto_espacio)
        col = [
            [celda_superior],
            [HRFlowable(
                width=max(ancho - 8 * mm, 30 * mm),
                thickness=0.6,
                color=COLOR_NEGRO,
                hAlign='CENTER',
            )],
            [Paragraph(f'<b>{self._esc(etiqueta)}</b>', self._estilos['FirmaLabel'])],
        ]
        tabla = Table(col, colWidths=[ancho])
        tabla.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        return tabla

    def _imagen_firma(
        self,
        campo,
        ancho: float = 50 * mm,
        alto: float = 22 * mm,
    ) -> Optional[RLImage]:
        """
        Carga la imagen de firma desde disco.

        Args:
            campo: FileField/ImageField de Django con la firma.
            ancho: Ancho máximo de la imagen.
            alto: Alto máximo (kind=proportional respeta la proporción).

        Returns:
            RLImage centrada, o None si no se puede leer el archivo.
        """
        if not campo:
            return None
        try:
            # hAlign CENTER: alinea la imagen dentro de su celda padre
            return RLImage(
                campo.path,
                width=ancho,
                height=alto,
                kind='proportional',
                hAlign='CENTER',
            )
        except Exception:
            return None

    def _construir_aviso_privacidad(self) -> List:
        """
        Página(s) finales con el aviso de privacidad (México o placeholder).
        """
        elementos: List = [PageBreak()]
        empresa = self.pais_config.get(
            'empresa_nombre',
            'SIC COMERCIALIZACIÓN Y SERVICIOS MÉXICO SC',
        )
        elementos.append(Paragraph(self._esc(empresa.upper()), self._estilos['AvisoTitulo']))
        elementos.append(Paragraph(
            'NO OLVIDE CONSULTAR NUESTRO AVISO DE PRIVACIDAD EN '
            '<font color="#003366"><b>WWW.SIC.COM.MX</b></font>',
            self._estilos['FirmaLabel'],
        ))
        elementos.append(Spacer(1, 3 * mm))
        elementos.append(self._crear_header_seccion('Aviso de privacidad'))
        elementos.append(Spacer(1, 3 * mm))

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Elegimos el texto largo del aviso según el país (México tiene el
        # aviso completo; otros países usan un placeholder). La versión
        # (ej. mx-2016-09-06) se guarda en BD al finalizar, pero ya no se
        # imprime aquí: solo dejamos la frase de aceptación digital.
        codigo = (self.pais_config.get('codigo') or 'MX').upper()
        if codigo == 'MX':
            texto = AVISO_PRIVACIDAD_OOW_MX
        else:
            texto = AVISO_PRIVACIDAD_OOW_PLACEHOLDER_OTROS

        # Dividir en párrafos por líneas en blanco
        for bloque in texto.split('\n\n'):
            limpio = ' '.join(bloque.split())
            if not limpio:
                continue
            elementos.append(Paragraph(self._esc(limpio), self._estilos['CuerpoChico']))
            elementos.append(Spacer(1, 1.5 * mm))

        # KeepTogether: la frase de aceptación y la firma no se parten
        # (evita una hoja final solo con la imagen).
        ancho_firma = 50 * mm
        alto_firma = 18 * mm
        firma_img = self._imagen_firma(
            self.formato.firma_cliente,
            ancho=ancho_firma,
            alto=alto_firma,
        )
        bloque_firma = self._bloque_columna_firma(
            'Firma del cliente',
            imagen=firma_img,
            ancho=ancho_firma,
            alto_espacio=alto_firma,
        )
        ancho_util = letter[0] - (2 * MARGEN)
        firma_centrada = Table(
            [[bloque_firma]],
            colWidths=[ancho_util],
        )
        firma_centrada.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elementos.append(KeepTogether([
            Spacer(1, 3 * mm),
            Paragraph(
                'El cliente aceptó este aviso digitalmente al finalizar '
                'el Formato OOW en SIGMA.',
                self._estilos['CeldaValor'],
            ),
            Spacer(1, 3 * mm),
            firma_centrada,
        ]))
        return elementos

    def _construir_promociones(self) -> List:
        """
        Hoja extra: QR fijos del catálogo + flyers vigentes de marketing.

        Objetivo de negocio:
            El cliente se lleva el papel y puede escanear reacondicionados
            o el catálogo. Si hay campaña vigente, también ve el flyer.

        Returns:
            Lista de flowables que empieza con PageBreak.
        """
        from servicio_tecnico.services.campanias_pdf_oow import (
            obtener_campanias_vigentes,
        )

        elementos: List = [PageBreak()]
        # Misma barra navy que el resto de secciones (un solo título, no dos).
        elementos.append(self._crear_header_seccion(OOW_PROMO_TITULO_HOJA))
        elementos.append(Spacer(1, 3 * mm))
        elementos.append(self._construir_qrs_promo_fijos())
        elementos.append(Spacer(1, 4 * mm))

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Las campañas se leen AHORA (al generar/regenerar). Si marketing
        # pausó una, el PDF nuevo ya no la trae; el PDF viejo no se reescribe
        # solo: hay que pulsar regenerar.
        try:
            campanias = obtener_campanias_vigentes()
        except Exception as exc:
            logger.warning(
                '[PDF_FORMATO_OOW] No se pudieron leer campañas vigentes: %s',
                exc,
            )
            campanias = []
        elementos += self._construir_rejilla_campanias(campanias)
        return elementos

    def _construir_rejilla_campanias(self, campanias) -> List:
        """
        Acomoda los flyers a lo ancho (2 por fila), no uno debajo del otro.

        Args:
            campanias: iterable de CampaniaPdfOow vigentes.

        Returns:
            Lista con la tabla (vacía si ninguna imagen se pudo leer).
        """
        bloques = [c for c in campanias]
        if not bloques:
            return []

        ancho_util = letter[0] - (2 * MARGEN)
        # 1 flyer: usa todo el ancho. 2 o más: dos columnas para llenar la hoja.
        columnas = 1 if len(bloques) == 1 else 2
        ancho_col = ancho_util / columnas
        # Retrato (ficha de laptop) cabe más alto cuando comparte la fila.
        alto_img = 140 * mm if columnas == 1 else 125 * mm

        celdas = []
        for campania in bloques:
            pieza = self._construir_bloque_campania(
                campania,
                ancho=ancho_col - 3 * mm,
                alto=alto_img,
            )
            # Sin imagen (archivo perdido): no dejamos un hueco a la izquierda.
            if pieza:
                celdas.append(pieza)
        if not celdas:
            return []
        # Si de 2 campañas solo una tenía archivo, no dejamos media tabla vacía.
        columnas = 1 if len(celdas) == 1 else 2
        ancho_col = ancho_util / columnas

        filas = []
        # De 2 en 2: si queda una suelta, la última fila lleva celda vacía.
        for i in range(0, len(celdas), columnas):
            fila = celdas[i:i + columnas]
            while len(fila) < columnas:
                fila.append('')
            filas.append(fila)

        tabla = Table(filas, colWidths=[ancho_col] * columnas)
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        return [tabla]

    def _construir_qrs_promo_fijos(self) -> Table:
        """
        Dos tarjetas lado a lado con los QR del catálogo (siempre visibles).

        Returns:
            Table de 2 columnas con el mismo look navy de la portada.
        """
        from servicio_tecnico.utils.qr_pdf import imagen_qr_para_pdf

        ancho_util = letter[0] - (2 * MARGEN)
        ancho_col = ancho_util / 2
        celdas = []
        for item in OOW_PROMO_QR_FIJOS:
            url = item['url']
            qr_img = imagen_qr_para_pdf(url, lado_mm=22)
            celdas.append(self._tarjeta_qr_promo(
                titulo=item['titulo'],
                leyenda=item['leyenda'],
                url=url,
                qr_img=qr_img,
                ancho=ancho_col - 2 * mm,
            ))
        tabla = Table([celdas], colWidths=[ancho_col] * len(celdas))
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return tabla

    def _tarjeta_qr_promo(
        self,
        titulo: str,
        leyenda: str,
        url: str,
        qr_img,
        ancho: float,
    ) -> Table:
        """
        Una tarjeta navy: QR a la izquierda, título + leyenda a la derecha.

        Args:
            titulo: Texto corto visible (ej. Equipos reacondicionados).
            leyenda: Ayuda para escanear.
            url: Destino del QR (no se imprime; el código ya es clicable).
            qr_img: Image de ReportLab o None si no se pudo generar.
            ancho: Ancho total de esta tarjeta.

        Returns:
            Table lista para meter en la fila de 2 columnas.
        """
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # La URL no se escribe en el papel (se veía larga y fea). El cliente
        # escanea el QR. Si qrcode no está, el título queda como enlace
        # invisible en el PDF digital, sin mostrar la dirección.
        if qr_img is None and url:
            titulo_p = Paragraph(
                f'<link href="{self._esc(url)}">{self._esc(titulo)}</link>',
                self._estilos['QrTitulo'],
            )
        else:
            titulo_p = Paragraph(self._esc(titulo), self._estilos['QrTitulo'])
        leyenda_p = Paragraph(self._esc(leyenda), self._estilos['QrLeyenda'])
        ancho_qr = 26 * mm
        ancho_texto = max(ancho - ancho_qr, 20 * mm)
        bloque_texto = Table(
            [[titulo_p], [leyenda_p]],
            colWidths=[ancho_texto],
        )
        bloque_texto.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        celda_qr = qr_img if qr_img is not None else ''
        fila = Table(
            [[celda_qr, bloque_texto]],
            colWidths=[ancho_qr, ancho_texto],
        )
        fila.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_NAVY_SUAVE),
            ('BOX', (0, 0), (-1, -1), 0.7, COLOR_NAVY),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('LEFTPADDING', (0, 0), (0, 0), 2),
            ('RIGHTPADDING', (0, 0), (0, 0), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        return fila

    def _construir_bloque_campania(
        self,
        campania,
        ancho: Optional[float] = None,
        alto: Optional[float] = None,
    ) -> List:
        """
        Flyer de una campaña vigente (imagen + leyenda).

        Args:
            campania: CampaniaPdfOow vigente.
            ancho: Tope de ancho del flyer (por defecto, toda la hoja útil).
            alto: Tope de alto (por defecto 90 mm).

        Returns:
            Lista de flowables, o vacía si no se pudo leer la imagen.

        Efectos secundarios:
            Ninguno sobre BD. Si hay url_destino, la imagen queda clicable
            en el PDF digital (sin imprimir QR ni la dirección).
        """
        if ancho is None:
            ancho = letter[0] - (2 * MARGEN)
        if alto is None:
            alto = 90 * mm
        imagen = self._imagen_campania_pdf(
            campania,
            ancho=ancho,
            alto=alto,
        )
        if imagen is None:
            return []

        # Marco del tamaño REAL de la foto (no del tope 125 mm).
        piezas: List = [self._marco_alrededor_imagen(imagen)]
        # Leyenda visible; si está vacía, caemos al texto alt (no al título interno).
        pie = (campania.leyenda or campania.texto_alt or '').strip()
        if pie:
            piezas.append(Spacer(1, 2 * mm))
            piezas.append(Paragraph(self._esc(pie), self._estilos['PromoLeyenda']))
        return piezas

    def _marco_alrededor_imagen(self, imagen: RLImage) -> Table:
        """
        Recuadro navy ajustado al flyer (respeta el ratio de la imagen).

        Args:
            imagen: RLImage ya escalada con kind=proportional.

        Returns:
            Table de 1 celda con BOX; el ancho/alto coinciden con la foto.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Si pusiéramos el borde en la columna entera, saldría un rectángulo
        enorme con la foto chica adentro. Aquí leemos drawWidth/drawHeight
        (el tamaño real que ReportLab va a pintar) y el marco es de eso.
        """
        # wrap() es la API pública de ReportLab: calcula drawWidth/drawHeight.
        try:
            imagen.wrap(imagen._width or 0, imagen._height or 0)
        except Exception:
            logger.warning('[PDF_FORMATO_OOW] No se midió el flyer para el marco')
        pad = 1.5 * mm
        ancho_real = float(getattr(imagen, 'drawWidth', 0) or 0)
        alto_real = float(getattr(imagen, 'drawHeight', 0) or 0)
        kwargs = {}
        if ancho_real > 8 and alto_real > 8:
            kwargs['colWidths'] = [ancho_real + pad]
            kwargs['rowHeights'] = [alto_real + pad]
        marco = Table([[imagen]], **kwargs)
        marco.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.8, COLOR_NAVY),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), pad / 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), pad / 2),
            ('TOPPADDING', (0, 0), (-1, -1), pad / 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), pad / 2),
        ]))
        marco.hAlign = 'CENTER'
        return marco

    def _imagen_campania_pdf(
        self,
        campania,
        ancho: float,
        alto: float,
    ) -> Optional[RLImage]:
        """
        Carga el flyer y, si hay URL, lo hace clicable en el PDF digital.

        Args:
            campania: CampaniaPdfOow con ImageField.
            ancho / alto: tope en puntos (kind=proportional respeta el ratio).

        Returns:
            RLImage o None si el archivo no se puede leer.
        """
        campo = getattr(campania, 'imagen', None)
        if not campo:
            return None
        try:
            ruta = campo.path
        except Exception:
            return None

        url = (getattr(campania, 'url_destino', None) or '').strip()
        kwargs = {
            'width': ancho,
            'height': alto,
            'kind': 'proportional',
            'hAlign': 'CENTER',
        }
        try:
            if url:
                from servicio_tecnico.utils.qr_pdf import ImagenQRClicable
                return ImagenQRClicable(ruta, url=url, **kwargs)
            return RLImage(ruta, **kwargs)
        except Exception as exc:
            logger.warning(
                '[PDF_FORMATO_OOW] No se pudo pegar campaña "%s": %s',
                getattr(campania, 'titulo', '?'),
                exc,
            )
            return None
