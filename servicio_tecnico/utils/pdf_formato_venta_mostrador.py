"""
Generador PDF — Nota de Venta Directa (Venta Mostrador / FL)

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Este módulo crea el PDF profesional de la nota de venta con el MISMO
estilo visual que OOW (Platypus + headers navy #003366), pero el
contenido sigue el formato papel: tabla de conceptos, IVA, equipo,
firmas opcionales y términos.

Estructura:
1. Página 1 — Header + título + cliente + venta + equipo + daños
   (si hay) + firmas + leyenda + WhatsApp
2. Página 2 — Términos y condiciones + firma de conformidad
"""

from __future__ import annotations

import io
import logging
from decimal import Decimal
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
    LEYENDA_VENTA_MOSTRADOR,
    TERMINOS_VENTA_MOSTRADOR,
    WHATSAPP_FORMATO_VENTA_MOSTRADOR_INTRO,
    WHATSAPP_FORMATO_VENTA_MOSTRADOR_SUCURSALES,
    catalogo_vistas_dano_estetico,
)
from config.paises_config import get_pais_actual
from servicio_tecnico.services.formato_venta_mostrador import armar_conceptos_venta
from servicio_tecnico.services.vistas_dano import vistas_dano_para_pdf

logger = logging.getLogger('servicio_tecnico')

COLOR_NAVY = colors.HexColor('#003366')
COLOR_NAVY_SUAVE = colors.HexColor('#E8EEF5')
COLOR_GRIS_ALT = colors.HexColor('#F2F2F2')
COLOR_GRIS_BORDE = colors.HexColor('#CCCCCC')
COLOR_BLANCO = colors.white
COLOR_NEGRO = colors.black

MARGEN = 15 * mm
MARGEN_INFERIOR = 20 * mm


class PDFFormatoVentaMostrador:
    """
    Genera el PDF de la Nota de Venta Directa.

    Args:
        formato: instancia FormatoServicioVentaMostrador

    Efectos secundarios:
        Ninguno sobre BD; solo construye un BytesIO en memoria.
    """

    def __init__(self, formato):
        """
        Args:
            formato: FormatoServicioVentaMostrador
        """
        self.formato = formato
        self.orden = formato.orden
        self.detalle = getattr(formato.orden, 'detalle_equipo', None)
        self.pais_config = get_pais_actual()
        self._estilos = getSampleStyleSheet()
        self._crear_estilos()
        self.conceptos = armar_conceptos_venta(self.orden)

    def _folio(self) -> str:
        """Folio visible: SICSER, orden cliente o número interno."""
        detalle = self.detalle
        if detalle is not None:
            return (
                detalle.folio_sicser
                or detalle.orden_cliente
                or self.orden.numero_orden_interno
            )
        return self.orden.numero_orden_interno

    def generar_pdf(self) -> Dict[str, Any]:
        """
        Construye el PDF completo en un buffer BytesIO.

        Returns:
            dict: {success, buffer, nombre_archivo} o {success: False, error}
        """
        try:
            buffer = io.BytesIO()
            folio = self._folio()
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
                title=f'Nota de Venta Directa — {folio}',
                author=empresa,
                subject='Nota de venta directa (venta mostrador)',
                creator='SIGMA',
            )

            elementos: List = []
            elementos += self._construir_header()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_titulo_y_folio()
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._envolver_seccion(self._construir_datos_cliente())
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._envolver_seccion(self._construir_conceptos())
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._envolver_seccion(self._construir_datos_equipo())

            danos = self._construir_danos()
            if danos:
                elementos.append(Spacer(1, 4 * mm))
                elementos += self._envolver_seccion(danos)

            elementos.append(Spacer(1, 5 * mm))
            elementos.append(KeepTogether(self._construir_firmas()))
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_leyenda()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_whatsapp()

            elementos.append(PageBreak())
            elementos += self._construir_terminos()

            doc.build(
                elementos,
                onFirstPage=self._dibujar_pie_pagina,
                onLaterPages=self._dibujar_pie_pagina,
            )
            buffer.seek(0)
            nombre = f"NotaVenta_{self.orden.numero_orden_interno}.pdf"
            return {
                'success': True,
                'buffer': buffer,
                'nombre_archivo': nombre,
            }
        except Exception as exc:
            logger.error('[PDF_FORMATO_VM] Error: %s', exc, exc_info=True)
            return {'success': False, 'error': str(exc), 'buffer': None}

    def _dibujar_pie_pagina(self, canvas, doc) -> None:
        """Pie: folio a la izquierda, página a la derecha."""
        canvas.saveState()
        folio = self._folio() or ''
        y_pie = 10 * mm
        x_izq = MARGEN
        x_der = letter[0] - MARGEN
        canvas.setStrokeColor(COLOR_GRIS_BORDE)
        canvas.setLineWidth(0.5)
        canvas.line(x_izq, y_pie + 5 * mm, x_der, y_pie + 5 * mm)
        canvas.setFont('Helvetica', 7)
        canvas.setFillColor(COLOR_NAVY)
        canvas.drawString(x_izq, y_pie, f'Nota de Venta Directa · {folio}')
        canvas.drawRightString(x_der, y_pie, f'Página {doc.page}')
        canvas.restoreState()

    def _crear_estilos(self) -> None:
        """Registra ParagraphStyles reutilizados en el documento."""
        self._estilos.add(ParagraphStyle(
            'EmpresaHeaderVm',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=COLOR_NAVY,
            alignment=TA_LEFT,
            leading=13,
        ))
        self._estilos.add(ParagraphStyle(
            'TituloFormatoVm',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=COLOR_BLANCO,
            alignment=TA_CENTER,
            leading=12,
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaLabelVm',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NAVY,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaValorVm',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaTablaVm',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            leading=10,
            alignment=TA_LEFT,
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaTablaDerVm',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            leading=10,
            alignment=TA_RIGHT,
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaTablaBoldVm',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NAVY,
            leading=10,
            alignment=TA_RIGHT,
        ))
        self._estilos.add(ParagraphStyle(
            'CuerpoChicoVm',
            fontName='Helvetica',
            fontSize=7,
            textColor=COLOR_NEGRO,
            alignment=TA_JUSTIFY,
            leading=9,
            spaceAfter=2,
        ))
        self._estilos.add(ParagraphStyle(
            'LeyendaVm',
            fontName='Helvetica-Bold',
            fontSize=6.5,
            textColor=COLOR_NEGRO,
            alignment=TA_JUSTIFY,
            leading=8.5,
        ))
        self._estilos.add(ParagraphStyle(
            'FirmaLabelVm',
            fontName='Helvetica',
            fontSize=7,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
            leading=9,
        ))
        self._estilos.add(ParagraphStyle(
            'WhatsappIntroVm',
            fontName='Helvetica',
            fontSize=7,
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            leading=9,
        ))
        self._estilos.add(ParagraphStyle(
            'WhatsappCiudadVm',
            fontName='Helvetica',
            fontSize=6.5,
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            leading=8,
        ))
        self._estilos.add(ParagraphStyle(
            'WhatsappNumeroVm',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            leading=11,
        ))
        self._estilos.add(ParagraphStyle(
            'TerminoNumVm',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NAVY,
            leading=10,
        ))

    def _envolver_seccion(self, partes: List) -> List:
        """KeepTogether para no partir título de sección y tabla."""
        if not partes:
            return []
        return [KeepTogether(partes)]

    def _crear_header_seccion(self, titulo: str) -> Table:
        """Barra navy de sección (ancho completo del contenido)."""
        ancho = self._ancho_util()
        tabla = Table(
            [[Paragraph(titulo, self._estilos['TituloFormatoVm'])]],
            colWidths=[ancho],
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

    def _fmt_dinero(self, monto: Decimal) -> str:
        """Formatea $1,050.00 con coma de miles."""
        valor = Decimal(monto or 0)
        return f"${valor:,.2f}"

    def _obtener_logo(self) -> Optional[RLImage]:
        """Carga logo SIC PNG desde static si existe."""
        ruta = finders.find('images/logos/logo_sic.png')
        if not ruta:
            return None
        try:
            return RLImage(ruta, width=38 * mm, height=13 * mm, kind='proportional')
        except Exception:
            return None

    def _ancho_util(self) -> float:
        """Ancho de página menos márgenes izquierdo y derecho."""
        return letter[0] - (2 * MARGEN)

    def _construir_header(self) -> List:
        """
        Un solo logo SIC a la derecha + razón social a la izquierda.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Antes se repetía el mismo PNG a ambos lados (`[logo, centro, logo]`).
        Eso apretaba el texto de la empresa y se veían dos logotipos. Ahora
        hay dos columnas: datos de contacto | un logo.
        """
        elementos: List = []
        logo = self._obtener_logo()
        empresa = self.pais_config.get(
            'empresa_nombre',
            'SIC Comercialización y Servicios de México SC',
        )
        direccion = self.pais_config.get('empresa_direccion', '')
        telefono = self.pais_config.get('empresa_telefono', '')
        bloque_empresa = (
            f'<b>{self._esc(empresa)}</b><br/>'
            f'<font size="7">{self._esc(direccion)}</font><br/>'
            f'<font size="7">Atención a clientes {self._esc(telefono)}</font>'
        )
        texto = Paragraph(bloque_empresa, self._estilos['EmpresaHeaderVm'])
        ancho_logo = 42 * mm
        ancho_texto = self._ancho_util() - ancho_logo
        if logo:
            fila = [[texto, logo]]
        else:
            fila = [[texto, '']]
        tabla = Table(fila, colWidths=[ancho_texto, ancho_logo])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elementos.append(tabla)
        elementos.append(Spacer(1, 2 * mm))
        elementos.append(HRFlowable(width='100%', thickness=1, color=COLOR_GRIS_BORDE))
        return elementos

    def _construir_titulo_y_folio(self) -> List:
        """
        Título NOTA DE VENTA DIRECTA + recuadro fecha/folio, sin solaparse.

        EXPLICACIÓN PARA PRINCIPIANTES:
        `_crear_header_seccion()` dibuja la barra navy al ANCHO COMPLETO de
        la hoja. Si esa barra se mete en una celda más estrecha (porque al
        lado va Fecha/Folio), ReportLab no recorta: la barra se sale y tapa
        el recuadro. Por eso aquí el título usa el ancho de SU columna.
        """
        momento = self.formato.finalizado_en or timezone.now()
        fecha_txt = timezone.localtime(momento).strftime('%d/%m/%Y')
        folio = self._folio()
        # Columna folio + hueco entre título y recuadro
        hueco = 3 * mm
        ancho_folio = 60 * mm
        ancho_titulo = self._ancho_util() - ancho_folio - hueco

        recuadro = Table(
            [
                [
                    Paragraph('Fecha', self._estilos['CeldaLabelVm']),
                    Paragraph(self._esc(fecha_txt), self._estilos['CeldaValorVm']),
                ],
                [
                    Paragraph('FOLIO', self._estilos['CeldaLabelVm']),
                    Paragraph(self._esc(folio), self._estilos['CeldaValorVm']),
                ],
            ],
            colWidths=[20 * mm, 40 * mm],
        )
        recuadro.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
            ('BACKGROUND', (0, 0), (0, -1), COLOR_NAVY_SUAVE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        fila = Table(
            [[
                Paragraph('NOTA DE VENTA DIRECTA', self._estilos['TituloFormatoVm']),
                '',
                recuadro,
            ]],
            colWidths=[ancho_titulo, hueco, ancho_folio],
        )
        fila.setStyle(TableStyle([
            # Navy solo en la columna del título, hueco blanco, recuadro a la derecha.
            # Así ambas celdas de contenido quedan a la misma altura (la del folio).
            ('BACKGROUND', (0, 0), (0, 0), COLOR_NAVY),
            ('ALIGN', (0, 0), (0, 0), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
            ('LEFTPADDING', (0, 0), (0, 0), 4),
            ('RIGHTPADDING', (0, 0), (0, 0), 4),
        ]))
        return [fila]

    def _tabla_pares(self, pares: List[tuple]) -> Table:
        """Tabla 2 columnas label|valor."""
        data = [
            [
                Paragraph(self._esc(label), self._estilos['CeldaLabelVm']),
                Paragraph(self._esc(valor or ''), self._estilos['CeldaValorVm']),
            ]
            for label, valor in pares
        ]
        tabla = Table(data, colWidths=[48 * mm, None])
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

    def _centro_servicio(self) -> str:
        """Nombre de sucursal o razón social del país."""
        sucursal = getattr(self.orden, 'sucursal', None)
        if sucursal is not None and sucursal.nombre:
            return sucursal.nombre
        return self.pais_config.get(
            'empresa_nombre',
            'SIC Comercialización y Servicios México SC',
        )

    def _construir_datos_cliente(self) -> List:
        """DATOS DEL CLIENTE como el formato papel."""
        elementos = [self._crear_header_seccion('DATOS DEL CLIENTE'), Spacer(1, 2 * mm)]
        d = self.detalle
        nombre = (d.nombre_cliente if d else '') or ''
        empresa = (self.formato.empresa_cliente or '').strip() or nombre
        contacto = (self.formato.persona_contacto or '').strip()
        pares = [
            ('CENTRO DE SERVICIO', self._centro_servicio()),
            ('EMPRESA', empresa),
            ('R.F.C.', (d.rfc_cliente if d else '') or ''),
            ('PERSONA DE CONTACTO', contacto),
            ('EMAIL DE CONTACTO', (d.email_cliente if d else '') or ''),
            ('TELÉFONO', (d.telefono_cliente if d else '') or ''),
        ]
        elementos.append(self._tabla_pares(pares))
        return elementos

    def _construir_conceptos(self) -> List:
        """Tabla CANTIDAD / CONCEPTO / PRECIO / IMPORTE + totales."""
        elementos = [self._crear_header_seccion('CONCEPTOS ADQUIRIDOS'), Spacer(1, 2 * mm)]
        encabezado = [
            Paragraph('<b>CANTIDAD</b>', self._estilos['CeldaLabelVm']),
            Paragraph('<b>CONCEPTO</b>', self._estilos['CeldaLabelVm']),
            Paragraph('<b>PRECIO</b>', self._estilos['CeldaLabelVm']),
            Paragraph('<b>IMPORTE</b>', self._estilos['CeldaLabelVm']),
        ]
        data = [encabezado]
        lineas = self.conceptos.get('lineas') or []
        if not lineas:
            data.append([
                Paragraph('', self._estilos['CeldaTablaVm']),
                Paragraph('Sin conceptos capturados en venta mostrador', self._estilos['CeldaTablaVm']),
                Paragraph('', self._estilos['CeldaTablaVm']),
                Paragraph('', self._estilos['CeldaTablaVm']),
            ])
        for linea in lineas:
            data.append([
                Paragraph(str(linea['cantidad']), self._estilos['CeldaTablaVm']),
                Paragraph(self._esc(linea['descripcion']), self._estilos['CeldaTablaVm']),
                Paragraph(self._fmt_dinero(linea['precio_unitario']), self._estilos['CeldaTablaDerVm']),
                Paragraph(self._fmt_dinero(linea['importe']), self._estilos['CeldaTablaDerVm']),
            ])

        tabla = Table(data, colWidths=[22 * mm, None, 32 * mm, 32 * mm])
        estilos_tabla = [
            ('BACKGROUND', (0, 0), (-1, 0), COLOR_NAVY_SUAVE),
            ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, -1), 'CENTER'),
            ('ALIGN', (2, 0), (-1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]
        for i in range(1, len(data)):
            if i % 2 == 0:
                estilos_tabla.append(('BACKGROUND', (0, i), (-1, i), COLOR_GRIS_ALT))
        tabla.setStyle(TableStyle(estilos_tabla))
        elementos.append(tabla)
        elementos.append(Spacer(1, 2 * mm))
        elementos.append(self._tabla_totales())
        return elementos

    def _tabla_totales(self) -> Table:
        """SUBTOTAL / IVA / TOTAL alineados a la derecha."""
        subtotal = self.conceptos['subtotal']
        iva = self.conceptos['iva']
        total = self.conceptos['total']
        aplica_iva = self.conceptos['aplica_iva']
        filas = [
            [
                Paragraph('SUBTOTAL', self._estilos['CeldaTablaBoldVm']),
                Paragraph(self._fmt_dinero(subtotal), self._estilos['CeldaTablaDerVm']),
            ],
        ]
        if aplica_iva:
            filas.append([
                Paragraph('IVA 16%', self._estilos['CeldaTablaBoldVm']),
                Paragraph(self._fmt_dinero(iva), self._estilos['CeldaTablaDerVm']),
            ])
        filas.append([
            Paragraph('TOTAL IVA INCLUIDO' if aplica_iva else 'TOTAL', self._estilos['CeldaTablaBoldVm']),
            Paragraph(self._fmt_dinero(total), self._estilos['CeldaTablaDerVm']),
        ])
        tabla = Table(filas, colWidths=[50 * mm, 32 * mm])
        tabla.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('BACKGROUND', (0, -1), (-1, -1), COLOR_NAVY_SUAVE),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        # Empujar la tabla de totales a la derecha
        envoltorio = Table([['', tabla]], colWidths=[None, 84 * mm])
        envoltorio.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        return envoltorio

    def _construir_datos_equipo(self) -> List:
        """Marca / modelo / service tag / cargador (pueden ir vacíos)."""
        elementos = [self._crear_header_seccion('DATOS DEL EQUIPO'), Spacer(1, 2 * mm)]
        d = self.detalle
        pares = [
            ('MARCA', (d.marca if d else '') or ''),
            ('MODELO', (d.modelo if d else '') or ''),
            ('SERVICE TAG', (d.numero_serie if d else '') or ''),
            ('CARGADOR', self.formato.numero_cargador or ''),
        ]
        elementos.append(self._tabla_pares(pares))
        return elementos

    def _construir_danos(self) -> List:
        """Diagramas anotados; vacío si no se capturó nada (se omite)."""
        vistas = vistas_dano_para_pdf(self.formato)
        if not vistas:
            return []
        elementos = [
            self._crear_header_seccion('ESTADO ESTÉTICO DEL EQUIPO'),
            Spacer(1, 2 * mm),
        ]
        tipo = (self.formato.tipo_diagrama or 'laptop').lower()
        labels = dict(catalogo_vistas_dano_estetico(tipo))
        bloques_vista = []
        for vista in vistas:
            try:
                path = vista.imagen_anotada.path
                img = RLImage(path, width=72 * mm, height=42 * mm, kind='proportional')
            except Exception:
                img = Paragraph('(imagen no disponible)', self._estilos['CeldaValorVm'])
            titulo = labels.get(vista.clave_vista, vista.clave_vista)
            tarjeta = Table(
                [
                    [Paragraph(f'<b>{self._esc(titulo)}</b>', self._estilos['CeldaLabelVm'])],
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

        for i in range(0, len(bloques_vista), 2):
            izq = bloques_vista[i]
            der = bloques_vista[i + 1] if i + 1 < len(bloques_vista) else ''
            fila = Table([[izq, der]], colWidths=['50%', '50%'])
            fila.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ]))
            elementos.append(KeepTogether([fila, Spacer(1, 2 * mm)]))
        return elementos

    def _celda_firma(self, campo, etiqueta: str) -> Table:
        """Imagen de firma o raya vacía, con leyenda debajo."""
        imagen = None
        archivo = getattr(self.formato, campo, None)
        if archivo:
            try:
                imagen = RLImage(
                    archivo.path,
                    width=70 * mm,
                    height=22 * mm,
                    kind='proportional',
                )
            except Exception:
                imagen = None
        if imagen is None:
            contenido = Paragraph('______________________________', self._estilos['FirmaLabelVm'])
        else:
            contenido = imagen
        tabla = Table(
            [
                [contenido],
                [Paragraph(self._esc(etiqueta), self._estilos['FirmaLabelVm'])],
            ],
            colWidths=[88 * mm],
        )
        tabla.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (0, 0), 'BOTTOM'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        return tabla

    def _construir_firmas(self) -> List:
        """Dos líneas: entrega en CIS / entrega a cliente."""
        izq = self._celda_firma(
            'firma_entrega_cis',
            'NOMBRE, FECHA Y FIRMA DE ENTREGA DE EQUIPO EN CIS',
        )
        der = self._celda_firma(
            'firma_entrega_cliente',
            'NOMBRE, FECHA Y FIRMA DE ENTREGA DE EQUIPO A CLIENTE',
        )
        fila = Table([[izq, der]], colWidths=['50%', '50%'])
        fila.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        return [fila]

    def _construir_leyenda(self) -> List:
        """Disclaimer en mayúsculas del formato papel."""
        caja = Table(
            [[Paragraph(self._esc(LEYENDA_VENTA_MOSTRADOR), self._estilos['LeyendaVm'])]],
            colWidths=[letter[0] - 2 * MARGEN],
        )
        caja.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.6, COLOR_GRIS_BORDE),
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_GRIS_ALT),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        return [caja]

    def _fmt_tel_mx(self, digitos: str) -> str:
        """
        Separa un teléfono mexicano de 10 dígitos: 5575615114 → 55 7561 5114.

        EXPLICACIÓN PARA PRINCIPIANTES:
        En el PDF se lee mejor con espacios. Si el número no tiene 10
        dígitos (otro país o dato raro), se imprime tal cual.
        """
        solo = ''.join(c for c in (digitos or '') if c.isdigit())
        if len(solo) == 10:
            return f'{solo[:2]} {solo[2:6]} {solo[6:]}'
        return digitos or ''

    def _construir_whatsapp(self) -> List:
        """
        Bloque de contacto WhatsApp: encabezado + intro + columnas de sucursal.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Antes era un párrafo corrido y el texto se partía a la mitad
        (el primer número en una línea y el resto en otra). Ahora es una
        tarjetita con 3 columnas, igual de corporativa que el resto del PDF.
        """
        codigo = (self.pais_config.get('codigo') or 'MX').upper()
        elementos: List = [
            self._crear_header_seccion('ATENCIÓN POR WHATSAPP'),
            Spacer(1, 2 * mm),
        ]
        if codigo == 'MX':
            intro = WHATSAPP_FORMATO_VENTA_MOSTRADOR_INTRO
            sucursales = WHATSAPP_FORMATO_VENTA_MOSTRADOR_SUCURSALES
        else:
            tel = self.pais_config.get('empresa_telefono', '')
            intro = (
                'Estimado Usuario, cualquier duda referente a la pieza y/o '
                'servicio adquirido estamos para servirle.'
            )
            sucursales = [('Teléfono de contacto', tel)]

        elementos.append(Paragraph(self._esc(intro), self._estilos['WhatsappIntroVm']))
        elementos.append(Spacer(1, 2 * mm))

        n = max(len(sucursales), 1)
        ancho_col = self._ancho_util() / n
        celdas = []
        for ciudad, telefono in sucursales:
            tarjeta = Table(
                [
                    [Paragraph(self._esc(ciudad), self._estilos['WhatsappCiudadVm'])],
                    [Paragraph(self._esc(self._fmt_tel_mx(telefono)), self._estilos['WhatsappNumeroVm'])],
                ],
                colWidths=[ancho_col],
            )
            tarjeta.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (0, 0), 3),
                ('BOTTOMPADDING', (0, -1), (0, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ]))
            celdas.append(tarjeta)

        fila = Table([celdas], colWidths=[ancho_col] * n)
        fila.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_NAVY_SUAVE),
            ('BOX', (0, 0), (-1, -1), 0.6, COLOR_NAVY),
            ('INNERGRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        elementos.append(fila)
        return [KeepTogether(elementos)]

    def _construir_terminos(self) -> List:
        """Página 2: 11 cláusulas + línea de conformidad."""
        elementos = [
            self._crear_header_seccion('TÉRMINOS Y CONDICIONES GENERALES'),
            Spacer(1, 3 * mm),
            Paragraph(
                'Por la presente acepto y autorizo a '
                f'"{self._esc(self.pais_config.get("empresa_nombre", "SIC"))}" '
                'en adelante (SIC) a:',
                self._estilos['CuerpoChicoVm'],
            ),
            Spacer(1, 2 * mm),
        ]
        for idx, texto in enumerate(TERMINOS_VENTA_MOSTRADOR, start=1):
            elementos.append(Paragraph(
                f'<b>{idx}.</b> {self._esc(texto)}',
                self._estilos['CuerpoChicoVm'],
            ))
        elementos.append(Spacer(1, 8 * mm))
        elementos.append(self._celda_firma(
            'firma_entrega_cliente',
            'NOMBRE Y FIRMA DE CLIENTE — ENTERADO, ACEPTADO Y CONFORME',
        ))
        return elementos
