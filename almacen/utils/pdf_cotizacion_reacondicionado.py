"""
Generador de PDF para propuesta de equipo reacondicionado — Almacén SIC.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Documento distinto al PDF de reparación por piezas. Muestra las
especificaciones del equipo ofertado y los precios de contado + financiamiento.
"""

from __future__ import annotations

import io
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .pdf_cotizacion_cliente import (
    COLOR_AZUL_TOTAL,
    COLOR_BLANCO,
    COLOR_GRIS_BORDE,
    COLOR_NAVY,
    COLOR_NEGRO,
    MARGEN,
    PDFCotizacionCliente,
)

logger = logging.getLogger('almacen')

TITULO_PROPUESTA = 'Propuesta de Equipo Reacondicionado — Certificado SIC'


class PDFCotizacionReacondicionado:
    """
    Genera el PDF de propuesta de venta de equipo reacondicionado.

    Args:
        solicitud     : SolicitudCotizacion (datos del cliente y folio).
        datos_equipo  : Marca, modelo, specs capturadas en el modal.
        costeo        : Resultado de calcular_costeo().
        pais_config   : Configuración del país activo.
    """

    def __init__(
        self,
        solicitud,
        datos_equipo: Dict[str, Any],
        costeo: Dict[str, Any],
        pais_config: Optional[Dict] = None,
    ):
        self.solicitud = solicitud
        self.datos_equipo = datos_equipo or {}
        self.costeo = costeo or {}
        self.pais_config = pais_config or {}
        self._estilos = getSampleStyleSheet()
        self._configurar_estilos()
        # Generador de referencia para reutilizar secciones compartidas (cliente, términos)
        self._gen_ref = PDFCotizacionCliente(
            solicitud=self.solicitud,
            tipo_servicio='mostrador',
            items=[],
            pais_config=self.pais_config,
        )

    def _configurar_estilos(self) -> None:
        """Define estilos de texto reutilizados en el documento."""
        self._estilos.add(ParagraphStyle(
            'EmpresaHeader',
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=COLOR_NEGRO,
            alignment=TA_RIGHT,
            spaceAfter=2,
        ))
        self._estilos.add(ParagraphStyle(
            'TituloPrincipal',
            fontName='Helvetica-Bold',
            fontSize=13,
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            spaceBefore=4,
            spaceAfter=4,
        ))
        self._estilos.add(ParagraphStyle(
            'HeaderSeccion',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=COLOR_BLANCO,
            alignment=TA_CENTER,
        ))

    def generar_pdf(self) -> Dict[str, Any]:
        """
        Construye el PDF en memoria.

        Returns:
            dict: success, buffer (BytesIO), nombre_archivo o error.
        """
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                leftMargin=MARGEN,
                rightMargin=MARGEN,
                topMargin=MARGEN,
                bottomMargin=MARGEN,
            )
            elementos: List = []
            elementos += self._construir_header()
            elementos += self._construir_titulo()
            elementos += self._construir_datos_cliente()
            elementos += self._construir_equipo_ofertado()
            elementos += self._construir_precios()
            # Segunda hoja: mismos términos y condiciones que cotización de reparación
            elementos += self._gen_ref._construir_terminos_condiciones()
            doc.build(elementos)
            buffer.seek(0)
            numero = self.solicitud.numero_solicitud.replace('/', '-')
            return {
                'success': True,
                'buffer': buffer,
                'nombre_archivo': f'Propuesta_Reacondicionado_{numero}.pdf',
            }
        except Exception as exc:
            logger.error(f'[PDF_REACONDICIONADO] Error: {exc}', exc_info=True)
            return {'success': False, 'error': str(exc)}

    def _construir_header(self) -> List:
        """Logo, empresa, fecha y folio (misma lógica visual que cotización de reparación)."""
        return self._gen_ref._construir_header()

    def _construir_titulo(self) -> List:
        return [
            Spacer(1, 2 * mm),
            Paragraph(TITULO_PROPUESTA, self._estilos['TituloPrincipal']),
            Spacer(1, 3 * mm),
        ]

    def _crear_header_seccion(self, titulo: str) -> Table:
        tabla = Table([[Paragraph(titulo, self._estilos['HeaderSeccion'])]], colWidths=['100%'])
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_NAVY),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        return tabla

    def _celda_etiqueta_valor(self, etiqueta: str, valor: str) -> Paragraph:
        html = f'<b>{etiqueta}</b> {valor}'
        return Paragraph(html, ParagraphStyle(
            'CeldaEV', fontName='Helvetica', fontSize=8, textColor=COLOR_NEGRO, alignment=TA_LEFT,
        ))

    def _construir_datos_cliente(self) -> List:
        """Reutiliza la sección de cliente del PDF de reparación."""
        return self._gen_ref._construir_datos_cliente()

    def _construir_equipo_ofertado(self) -> List:
        """
        Tabla con las especificaciones del equipo reacondicionado ofertado.

        Los datos provienen del modal (captura manual del vendedor).
        """
        d = self.datos_equipo
        incluye_cargador = d.get('incluye_cargador')
        if incluye_cargador is True:
            texto_cargador = 'Sí'
        elif incluye_cargador is False:
            texto_cargador = 'No'
        else:
            texto_cargador = '—'

        elementos = [self._crear_header_seccion('Equipo reacondicionado ofertado')]

        filas = [
            [
                self._celda_etiqueta_valor('Marca:', d.get('marca') or '—'),
                self._celda_etiqueta_valor('Modelo:', d.get('modelo') or '—'),
            ],
            [
                self._celda_etiqueta_valor('Procesador:', d.get('procesador') or '—'),
                self._celda_etiqueta_valor('Memoria RAM:', d.get('ram') or '—'),
            ],
            [
                self._celda_etiqueta_valor('Sistema operativo:', d.get('sistema_operativo') or '—'),
                self._celda_etiqueta_valor('Incluye cargador:', texto_cargador),
            ],
        ]

        especificaciones = (d.get('especificaciones') or '').strip()
        if especificaciones:
            filas.append([
                self._celda_etiqueta_valor('Especificaciones:', especificaciones),
                Paragraph('', ParagraphStyle('Vacio', fontSize=8)),
            ])

        tabla = Table(filas, colWidths=[None, None])
        estilos_tabla = [
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]
        if especificaciones:
            estilos_tabla.append(('SPAN', (0, -1), (1, -1)))
        tabla.setStyle(TableStyle(estilos_tabla))

        elementos.append(tabla)
        elementos.append(Spacer(1, 4 * mm))
        return elementos

    def _construir_precios(self) -> List:
        """Totales de contado y opciones de pago diferido con IVA."""
        c = self.costeo
        diferidos = c.get('opciones_diferidas_con_iva') or {}

        elementos = [self._crear_header_seccion('Inversión y opciones de pago')]

        estilo_etq = ParagraphStyle('Etq', fontName='Helvetica', fontSize=9, alignment=TA_LEFT)
        estilo_val = ParagraphStyle('Val', fontName='Helvetica', fontSize=9, alignment=TA_RIGHT)
        estilo_bold = ParagraphStyle('Bold', fontName='Helvetica-Bold', fontSize=10,
                                     textColor=COLOR_BLANCO, alignment=TA_RIGHT)
        estilo_bold_etq = ParagraphStyle('BoldEtq', fontName='Helvetica-Bold', fontSize=10,
                                         textColor=COLOR_BLANCO, alignment=TA_LEFT)

        filas = [
            [Paragraph('Subtotal (sin IVA):', estilo_etq),
             Paragraph(f"${c.get('subtotal_sin_iva', 0):,.2f}", estilo_val)],
            [Paragraph('IVA (16%):', estilo_etq),
             Paragraph(f"${c.get('iva', 0):,.2f}", estilo_val)],
            [Paragraph('TOTAL DE CONTADO (con IVA):', estilo_bold_etq),
             Paragraph(f"${c.get('total_precio_contado_mxn', 0):,.2f}", estilo_bold)],
            [Paragraph('Pago diferido a 3 meses (con IVA):', estilo_etq),
             Paragraph(f"${diferidos.get('diferido_3_meses', 0):,.2f}", estilo_val)],
            [Paragraph('Pago diferido a 6 meses (con IVA):', estilo_etq),
             Paragraph(f"${diferidos.get('diferido_6_meses', 0):,.2f}", estilo_val)],
            [Paragraph('Pago diferido a 12 meses (con IVA):', estilo_etq),
             Paragraph(f"${diferidos.get('diferido_12_meses', 0):,.2f}", estilo_val)],
        ]

        ancho = letter[0] - 2 * MARGEN
        tabla = Table(filas, colWidths=[ancho * 0.62, ancho * 0.38])
        tabla.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('BACKGROUND', (0, 2), (-1, 2), COLOR_AZUL_TOTAL),
        ]))
        elementos.append(tabla)
        return elementos
