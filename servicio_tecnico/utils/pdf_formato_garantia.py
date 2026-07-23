"""
Generador PDF — Formato de Servicio Garantía Dell (plantilla SIGMA).

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Recrea el layout del formato papel Dell/SICSER (Orden de Servicio) con
ReportLab Platypus. NO rellena el PDF de SICSER (no tiene campos AcroForm):
dibujamos nuestra propia plantilla con los mismos títulos y secciones.

Estructura:
1. Página 1 — ORDEN DE SERVICIO: DPS, cliente, equipo, accesorios Dell,
   textos legales, DESCRIPCIÓN DE LA FALLA INICIAL, diagnóstico vacío,
   piezas vacías, firma ingreso
2. Página 2 — ESTADO DEL EQUIPO RECIBIDO: daños anotados + PC Audit + firma
3. Página opcional — foto escaneo PC Audit
4. Página final — SERVICIO FINAL Dell (exclusiones de garantía + checklist
   del auditor + pie WhatsApp). NO lleva el aviso de privacidad SIC
   (ese es solo del formato OOW / fuera de garantía).
"""

from __future__ import annotations

import io
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from django.contrib.staticfiles import finders
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
    ACCESORIOS_FORMATO_GARANTIA,
    ACTIVIDADES_NO_INCLUIDAS_GARANTIA_DELL,
    CHECKLIST_AUDITOR_GARANTIA_DELL,
    TEXTO_PC_AUDIT_FORMATO_GARANTIA,
    TEXTO_TIEMPO_RESPUESTA_GARANTIA,
    TEXTOS_LEGALES_FORMATO_GARANTIA_DER,
    TEXTOS_LEGALES_FORMATO_GARANTIA_IZQ,
    VISTAS_DANO_ESTETICO_AIO,
    VISTAS_DANO_ESTETICO_ESCRITORIO,
    VISTAS_DANO_ESTETICO_LAPTOP,
    WHATSAPP_FORMATO_GARANTIA_NUMEROS,
    WHATSAPP_FORMATO_GARANTIA_TEXTO,
)
from config.paises_config import get_pais_actual

logger = logging.getLogger('servicio_tecnico')

# Colores del formato papel Dell/SICSER (barras grises, no navy cotización)
COLOR_NAVY = colors.HexColor('#003366')
COLOR_GRIS_HEADER = colors.HexColor('#6E6E6E')
COLOR_GRIS_ALT = colors.HexColor('#F2F2F2')
COLOR_GRIS_BORDE = colors.HexColor('#CCCCCC')
COLOR_AMARILLO_BG = colors.HexColor('#FFF2CC')
COLOR_WHATSAPP = colors.HexColor('#25D366')
COLOR_BLANCO = colors.white
COLOR_NEGRO = colors.black

MARGEN = 10 * mm
ANCHO_UTIL = letter[0] - (2 * MARGEN)


class PDFFormatoServicioGarantia:
    """
    Genera el PDF del Formato Digital Garantía Dell (plantilla propia).

    Args:
        formato: instancia FormatoServicioGarantia (con orden y vistas)

    Efectos secundarios:
        Ninguno sobre BD; solo construye un BytesIO en memoria.
    """

    def __init__(self, formato):
        """
        Args:
            formato: FormatoServicioGarantia
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
            doc = SimpleDocTemplate(
                buffer,
                pagesize=letter,
                leftMargin=MARGEN,
                rightMargin=MARGEN,
                topMargin=MARGEN,
                bottomMargin=MARGEN,
            )

            elementos: List = []
            # --- Página 1: plantilla Dell (layout papel 1:1) ---
            elementos += self._construir_header()
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._construir_cabecera_orden()
            elementos.append(Spacer(1, 2.5 * mm))
            elementos += self._construir_datos_cliente()
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._construir_datos_equipo()
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._construir_accesorios()
            elementos.append(Spacer(1, 1.5 * mm))
            elementos += self._construir_legales()
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._construir_falla_inicial()
            elementos.append(Spacer(1, 2 * mm))
            elementos += self._construir_diagnostico_y_piezas()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_firma_aceptacion()

            # --- Página 2: estado estético ---
            elementos.append(PageBreak())
            elementos += self._construir_pagina_estado_equipo()

            # --- Escaneo opcional ---
            if self._tiene_fotos_escaneo():
                elementos.append(PageBreak())
                elementos += self._construir_escaneo()

            # --- SERVICIO FINAL Dell (exclusiones + checklist; sin aviso SIC) ---
            elementos.append(PageBreak())
            elementos += self._construir_pagina_servicio_final()

            doc.build(elementos)
            buffer.seek(0)

            dps = (
                self.detalle.orden_cliente
                or self.detalle.folio_sicser
                or self.orden.numero_orden_interno
            )
            nombre = f"FormatoGarantia_{dps}.pdf"
            return {
                'success': True,
                'buffer': buffer,
                'nombre_archivo': nombre,
            }
        except Exception as exc:
            logger.error('[PDF_FORMATO_GARANTIA] Error: %s', exc, exc_info=True)
            return {'success': False, 'error': str(exc), 'buffer': None}

    def _crear_estilos(self) -> None:
        """Registra ParagraphStyles reutilizados en el documento."""
        self._estilos.add(ParagraphStyle(
            'TituloBanner',
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=COLOR_BLANCO,
            alignment=TA_CENTER,
            leading=14,
        ))
        self._estilos.add(ParagraphStyle(
            'TituloOrden',
            fontName='Helvetica-Bold',
            fontSize=12,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
            leading=14,
        ))
        self._estilos.add(ParagraphStyle(
            'TituloSeccion',
            fontName='Helvetica-Bold',
            fontSize=8.5,
            textColor=COLOR_BLANCO,
            alignment=TA_CENTER,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaLabel',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NEGRO,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'CeldaValor',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'CampoInline',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'CuerpoNormal',
            fontName='Helvetica',
            fontSize=7.5,
            textColor=COLOR_NEGRO,
            alignment=TA_JUSTIFY,
            leading=9.5,
        ))
        self._estilos.add(ParagraphStyle(
            'CuerpoChico',
            fontName='Helvetica',
            fontSize=6.2,
            textColor=COLOR_NEGRO,
            alignment=TA_JUSTIFY,
            leading=8,
            spaceAfter=1,
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
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
        ))
        self._estilos.add(ParagraphStyle(
            'CheckAcc',
            fontName='Helvetica',
            fontSize=7.5,
            textColor=COLOR_NEGRO,
            leading=9,
            alignment=TA_LEFT,
        ))
        # --- Estilos página SERVICIO FINAL (fuentes chicas para caber en 1 hoja) ---
        self._estilos.add(ParagraphStyle(
            'ServicioFinalTitulo',
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
            leading=13,
        ))
        self._estilos.add(ParagraphStyle(
            'ServicioFinalAcepto',
            fontName='Helvetica-Oblique',
            fontSize=6.5,
            textColor=COLOR_NEGRO,
            alignment=TA_RIGHT,
            leading=8,
        ))
        self._estilos.add(ParagraphStyle(
            'ServicioFinalCampo',
            fontName='Helvetica',
            fontSize=7,
            textColor=COLOR_NEGRO,
            leading=9,
        ))
        self._estilos.add(ParagraphStyle(
            'ExclusionesTitulo',
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
            leading=10,
        ))
        self._estilos.add(ParagraphStyle(
            'ExclusionItem',
            fontName='Helvetica',
            fontSize=5.2,
            textColor=COLOR_NEGRO,
            alignment=TA_JUSTIFY,
            leading=6.4,
        ))
        self._estilos.add(ParagraphStyle(
            'ChecklistMini',
            fontName='Helvetica',
            fontSize=5,
            textColor=COLOR_NEGRO,
            leading=6,
        ))
        self._estilos.add(ParagraphStyle(
            'ChecklistMiniBold',
            fontName='Helvetica-Bold',
            fontSize=5,
            textColor=COLOR_NEGRO,
            leading=6,
        ))
        self._estilos.add(ParagraphStyle(
            'AuditorNota',
            fontName='Helvetica',
            fontSize=5.5,
            textColor=COLOR_NEGRO,
            alignment=TA_JUSTIFY,
            leading=6.8,
        ))
        self._estilos.add(ParagraphStyle(
            'WhatsAppPie',
            fontName='Helvetica',
            fontSize=6.5,
            textColor=COLOR_NEGRO,
            alignment=TA_LEFT,
            leading=8,
        ))
        self._estilos.add(ParagraphStyle(
            'HeaderTipoServicio',
            fontName='Helvetica',
            fontSize=6,
            textColor=COLOR_BLANCO,
            leading=7,
            alignment=TA_LEFT,
        ))

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

    def _tiene_fotos_escaneo(self) -> bool:
        """True si la orden tiene al menos una foto de escaneo garantía."""
        from servicio_tecnico.models import ImagenOrden
        return ImagenOrden.objects.filter(
            orden=self.orden,
            tipo='escaneo_garantia',
        ).exists()

    def _crear_header_seccion(self, titulo: str) -> Table:
        """
        Barra gris de sección centrada (igual al papel Dell).

        EXPLICACIÓN PARA PRINCIPIANTES:
        El formato Dell usa encabezados gris medio (#6E6E6E) con texto blanco,
        no las barras navy de las cotizaciones SIGMA.
        """
        tabla = Table(
            [[Paragraph(titulo, self._estilos['TituloSeccion'])]],
            colWidths=[ANCHO_UTIL],
        )
        tabla.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_GRIS_HEADER),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 3.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3.5),
        ]))
        return tabla

    def _cargar_logo(self, nombre_static: str, ancho_mm: float, alto_mm: float) -> Optional[RLImage]:
        """Carga un logo PNG desde static/images/logos/."""
        ruta = finders.find(f'images/logos/{nombre_static}')
        if not ruta:
            return None
        try:
            return RLImage(ruta, width=ancho_mm * mm, height=alto_mm * mm, kind='proportional')
        except Exception:
            return None

    def _construir_header(self) -> List:
        """
        Cabecera Dell | ORDEN DE SERVICIO + tipos CIS/WIS/OOW/ON SITE | SIC.

        En garantía Dell marcamos CIS (como el papel del centro de servicio).
        """
        logo_dell = self._cargar_logo('logo_dell.png', 18, 18)
        logo_sic = (
            self._cargar_logo('logo_sic_formato.png', 28, 10)
            or self._cargar_logo('logo_sic.png', 28, 11)
        )

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # En el papel Dell hay 4 casillas. Para órdenes de garantía importadas
        # desde SICSER, el tipo correcto es CIS (no OOW).
        # Usamos [X]/[ ] porque Helvetica no dibuja bien ☑/☐ (Unicode).
        tipos = Paragraph(
            '<b>CIS</b> [X] &nbsp;&nbsp; WIS [ ] &nbsp;&nbsp; OOW [ ] &nbsp;&nbsp; ON SITE [ ]',
            self._estilos['HeaderTipoServicio'],
        )
        banner = Table(
            [
                [Paragraph('ORDEN DE SERVICIO', self._estilos['TituloBanner'])],
                [tipos],
            ],
            colWidths=[95 * mm],
        )
        banner.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_GRIS_HEADER),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, 0), 4),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 1),
            ('TOPPADDING', (0, 1), (-1, 1), 0),
            ('BOTTOMPADDING', (0, 1), (-1, 1), 3),
        ]))

        izq = logo_dell or Paragraph('<b>Dell</b>', self._estilos['CeldaLabel'])
        der = logo_sic or Paragraph('<b>SIC</b>', self._estilos['CeldaLabel'])
        fila = Table(
            [[izq, banner, der]],
            colWidths=[28 * mm, 95 * mm, 40 * mm],
        )
        fila.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        return [fila]

    def _dps(self) -> str:
        """Número DPS / orden cliente SICSER."""
        return (
            self.detalle.orden_cliente
            or self.detalle.folio_sicser
            or self.orden.numero_orden_interno
            or '—'
        )

    def _campo_inline(self, label: str, valor: str) -> Paragraph:
        """Campo estilo papel: <b>Label</b> valor (sin rejilla)."""
        v = (valor or '').strip()
        return Paragraph(
            f'<b>{self._esc(label)}</b> {self._esc(v)}',
            self._estilos['CampoInline'],
        )

    def _construir_cabecera_orden(self) -> List:
        """Fila DPS + fechas (creación, ingreso, salida vacía)."""
        hoy = date.today().strftime('%Y-%m-%d')
        fecha_ingreso = (
            self.orden.fecha_ingreso.strftime('%Y-%m-%d')
            if self.orden.fecha_ingreso
            else hoy
        )
        data = [[
            self._campo_inline('Orden (DPS)', self._dps()),
            self._campo_inline('Fecha Creación', hoy),
            self._campo_inline('Fecha Ingreso', fecha_ingreso),
            self._campo_inline('Fecha salida', ''),
        ]]
        tabla = Table(data, colWidths=['27%', '25%', '25%', '23%'])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 0),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ]))
        return [tabla]

    def _construir_datos_cliente(self) -> List:
        """
        INFORMACIÓN DEL CLIENTE — 2 filas × 3 columnas (como el papel Dell).

        Fila 1: Nombre | Teléfono | Móvil
        Fila 2: Dirección | Ciudad | Email
        """
        d = self.detalle
        # No hay dirección/móvil en DetalleEquipo; ciudad viene de SICSER si existe
        ciudad = (getattr(d, 'sicser_ciudad', None) or '').strip()
        elementos = [
            self._crear_header_seccion('INFORMACIÓN DEL CLIENTE'),
            Spacer(1, 1.5 * mm),
        ]
        data = [
            [
                self._campo_inline('Nombre', d.nombre_cliente or ''),
                self._campo_inline('Teléfono', d.telefono_cliente or ''),
                self._campo_inline('Móvil', ''),
            ],
            [
                self._campo_inline('Dirección', d.direccion_cliente or ''),
                self._campo_inline('Ciudad', ciudad),
                self._campo_inline('Email', d.email_cliente or ''),
            ],
        ]
        tabla = Table(data, colWidths=['40%', '30%', '30%'])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        elementos.append(tabla)
        return elementos

    def _construir_datos_equipo(self) -> List:
        """INFORMACIÓN DEL EQUIPO — Modelo | Tipo | Service Tag."""
        d = self.detalle
        elementos = [
            self._crear_header_seccion('INFORMACIÓN DEL EQUIPO'),
            Spacer(1, 1.5 * mm),
        ]
        data = [[
            self._campo_inline('Modelo', d.modelo or ''),
            self._campo_inline('Tipo', d.tipo_equipo or ''),
            self._campo_inline('Service Tag', d.numero_serie or ''),
        ]]
        tabla = Table(data, colWidths=['40%', '30%', '30%'])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        elementos.append(tabla)
        return elementos

    def _marcar_check(self, activo: bool) -> str:
        """
        Marca del papel Dell: 'x' marcado, '_' vacío.

        EXPLICACIÓN PARA PRINCIPIANTES:
        En el PDF de referencia se ve `_ Cargador` o `x Otros`.
        """
        return 'x' if activo else '_'

    def _construir_accesorios(self) -> List:
        """
        Accesorios en una sola línea + No. Serie / Descripción (número cargador).

        Lo remarcado en amarillo del papel:
        - checks de accesorios (y “SIN ACCESORIOS” si no hay ninguno / va en Otros)
        - No. Serie / Descripción ← campo numero_cargador del wizard
        """
        f = self.formato
        elementos = [
            self._crear_header_seccion('ACCESORIOS RECIBIDOS / ENTREGADOS'),
            Spacer(1, 1.5 * mm),
        ]

        # Paso 1: ¿hay algún accesorio marcado? (para “SIN ACCESORIOS”)
        algun_accesorio = any(
            bool(getattr(f, campo, False))
            for campo, _etiqueta in ACCESORIOS_FORMATO_GARANTIA
        )
        detalle_otros = (f.accesorios_otros_detalle or '').strip()

        # Paso 2: una sola línea como el papel: _ Cargador _ Teclado x Otros …
        partes: list[str] = []
        for campo, etiqueta in ACCESORIOS_FORMATO_GARANTIA:
            marcado = bool(getattr(f, campo, False))
            marca = self._marcar_check(marcado)
            if campo == 'accesorio_otros':
                # Papel Dell: si no hay accesorios → "x Otros SIN ACCESORIOS"
                if not algun_accesorio:
                    partes.append('x Otros SIN ACCESORIOS')
                elif marcado and detalle_otros:
                    partes.append(f'{marca} Otros {self._esc(detalle_otros)}')
                else:
                    partes.append(f'{marca} Otros')
            else:
                partes.append(f'{marca} {self._esc(etiqueta)}')

        elementos.append(Paragraph(' '.join(partes), self._estilos['CheckAcc']))
        elementos.append(Spacer(1, 1.5 * mm))

        # Número del cargador / descripción (campo del wizard)
        num = (f.numero_cargador or '').strip() or 'NA'
        elementos.append(Paragraph(
            f'<b>No. Serie / Descripción:</b> {self._esc(num)}',
            self._estilos['CeldaValor'],
        ))
        return elementos

    def _construir_legales(self) -> List:
        """Avisos legales en 2 columnas + párrafo Tiempo de Respuesta."""
        izq = [
            Paragraph(self._esc(t), self._estilos['CuerpoChico'])
            for t in TEXTOS_LEGALES_FORMATO_GARANTIA_IZQ
        ]
        der = [
            Paragraph(self._esc(t), self._estilos['CuerpoChico'])
            for t in TEXTOS_LEGALES_FORMATO_GARANTIA_DER
        ]
        # Emparejar filas
        filas = []
        max_len = max(len(izq), len(der))
        for i in range(max_len):
            filas.append([
                izq[i] if i < len(izq) else '',
                der[i] if i < len(der) else '',
            ])
        tabla = Table(filas, colWidths=['55%', '45%'])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 0.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
        ]))
        elementos: List = [tabla, Spacer(1, 1.5 * mm)]
        # “Tiempo de Respuesta” en negrita al inicio del párrafo
        tr = TEXTO_TIEMPO_RESPUESTA_GARANTIA
        if tr.startswith('Tiempo de Respuesta:'):
            resto = tr[len('Tiempo de Respuesta:'):].strip()
            elementos.append(Paragraph(
                f'<b>Tiempo de Respuesta:</b> {self._esc(resto)}',
                self._estilos['CuerpoChico'],
            ))
        else:
            elementos.append(Paragraph(self._esc(tr), self._estilos['CuerpoChico']))
        return elementos

    def _construir_falla_inicial(self) -> List:
        """
        DESCRIPCIÓN DE LA FALLA INICIAL = falla_principal (SICSER).

        Es el bloque amarillo del papel con instrucciones Dell / Issue Summary.
        """
        elementos = [
            self._crear_header_seccion('DESCRIPCIÓN DE LA FALLA INICIAL'),
            Spacer(1, 1.5 * mm),
        ]
        falla = (self.detalle.falla_principal or '').strip()
        elementos.append(Paragraph(
            self._esc(falla) if falla else '',
            self._estilos['CuerpoNormal'],
        ))
        return elementos

    def _construir_diagnostico_y_piezas(self) -> List:
        """
        Diagnóstico vacío (espacio a mano) + tabla de piezas más grande.

        EXPLICACIÓN PARA PRINCIPIANTES:
        En el papel Dell el técnico escribe a mano el diagnóstico; por eso
        dejamos espacio en blanco (Spacer). Las líneas de piezas van grandes
        para poder rellenarlas a mano o leerlas fácil.
        """
        # Dos saltos de línea extra ≈ +2 × ~5 mm sobre el espacio base
        elementos = [
            self._crear_header_seccion('DIAGNÓSTICO TÉCNICO REALIZADO'),
            Spacer(1, 20 * mm),
            self._crear_header_seccion(
                'NOMBRE DE LA PARTE Y/O WIP PIEZAS / REMPLAZO No.de Serie'
            ),
            Spacer(1, 4 * mm),
        ]
        # Líneas más largas y tipografía un poco mayor (estilo papel Dell)
        estilo_pieza = ParagraphStyle(
            'LineaPiezaGar',
            parent=self._estilos['CeldaValor'],
            fontSize=10,
            leading=14,
            alignment=TA_CENTER,
        )
        lineas = [
            [
                Paragraph('1. ________________________________', estilo_pieza),
                Paragraph('2. ________________________________', estilo_pieza),
            ],
            [
                Paragraph('#. ________________________________', estilo_pieza),
                Paragraph('#. ________________________________', estilo_pieza),
            ],
        ]
        tabla = Table(lineas, colWidths=['50%', '50%'])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elementos.append(tabla)
        # Sin “Observaciones técnicas” en el PDF (el papel Dell no las trae aquí)
        return elementos

    def _construir_firma_aceptacion(self, compacto: bool = False) -> List:
        """
        Bloque ACEPTO + firma del cliente, todo centrado en la página.

        EXPLICACIÓN PARA PRINCIPIANTES:
        El papel Dell centra el texto de aceptación, la firma y el label
        “FIRMA CLIENTE”. Cada celda de la tabla interna va alineada al centro.
        """
        estilo_acepta = ParagraphStyle(
            'AceptaGar',
            parent=self._estilos['CeldaLabel'],
            alignment=TA_CENTER,
            fontSize=9 if not compacto else 8,
            leading=11,
        )
        elementos = [
            Paragraph(
                'ACEPTO LAS CONDICIONES EN LAS QUE ENTREGO EL EQUIPO '
                'AL CENTRO DE SERVICIO',
                estilo_acepta,
            ),
            Spacer(1, 5 * mm if compacto else 8 * mm),
        ]

        firma_cli = None
        if self.formato.firma_cliente:
            try:
                firma_cli = RLImage(
                    self.formato.firma_cliente.path,
                    width=50 * mm if not compacto else 42 * mm,
                    height=20 * mm if not compacto else 16 * mm,
                    kind='proportional',
                )
            except Exception:
                firma_cli = None

        # Columna única centrada: imagen + línea + etiqueta
        ancho_firma = 70 * mm
        celda_firma = firma_cli if firma_cli is not None else Paragraph(
            '<br/>', self._estilos['CeldaValor'],
        )
        col_cli = Table(
            [
                [celda_firma],
                [HRFlowable(
                    width=ancho_firma,
                    thickness=0.8,
                    color=COLOR_NEGRO,
                    spaceBefore=1,
                    spaceAfter=1,
                )],
                [Paragraph('<b>FIRMA CLIENTE</b>', self._estilos['FirmaLabel'])],
            ],
            colWidths=[ancho_firma],
        )
        col_cli.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))

        # Tabla exterior a todo el ancho para centrar el bloque
        envoltorio = Table([[col_cli]], colWidths=[ANCHO_UTIL])
        envoltorio.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elementos.append(envoltorio)
        return elementos

    def _construir_pagina_estado_equipo(self) -> List:
        """
        Página 2: ESTADO DEL EQUIPO RECIBIDO + daños + PC Audit + firma.

        EXPLICACIÓN PARA PRINCIPIANTES:
        En el PDF papel Dell aquí van Pantalla / Top Cover / Palm.
        Nosotros embebemos las vistas anotadas del canvas del wizard.
        """
        elementos = []
        elementos += self._construir_header()
        elementos.append(Spacer(1, 2 * mm))
        elementos.append(self._campo_inline('Orden (DPS)', self._dps()))
        elementos.append(Spacer(1, 3 * mm))
        elementos.append(self._crear_header_seccion('ESTADO DEL EQUIPO RECIBIDO'))
        elementos.append(Spacer(1, 3 * mm))
        elementos += self._construir_danos()
        elementos.append(Spacer(1, 3 * mm))

        # Aviso PC Audit (si no hay foto o marcaron disclaimer)
        sin_escaneo = not self._tiene_fotos_escaneo()
        mostrar_aviso = sin_escaneo or bool(self.formato.disclaimer_pc_audit)
        if mostrar_aviso:
            bloque = Table(
                [[Paragraph(
                    self._esc(TEXTO_PC_AUDIT_FORMATO_GARANTIA),
                    self._estilos['CuerpoChico'],
                )]],
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
            elementos.append(Spacer(1, 4 * mm))

        elementos += self._construir_firma_aceptacion(compacto=True)
        return elementos

    def _construir_danos(self) -> List:
        """Grid de vistas de daño anotadas (página 2)."""
        elementos: List = []
        vistas = list(
            self.formato.vistas_dano.exclude(
                imagen_anotada='',
            ).exclude(imagen_anotada=None)
        )
        if not vistas:
            elementos.append(Paragraph(
                'Sin anotaciones de daños en diagramas.',
                self._estilos['CeldaValor'],
            ))
            return elementos

        tipo = (self.formato.tipo_diagrama or 'laptop').lower()
        if tipo == 'escritorio':
            catalogo_orden = VISTAS_DANO_ESTETICO_ESCRITORIO
        elif tipo == 'aio':
            catalogo_orden = VISTAS_DANO_ESTETICO_AIO
        else:
            catalogo_orden = VISTAS_DANO_ESTETICO_LAPTOP

        orden_claves = {clave: idx for idx, (clave, _) in enumerate(catalogo_orden)}
        vistas.sort(
            key=lambda v: (orden_claves.get(v.clave_vista, 999), v.clave_vista or '')
        )
        labels = dict(
            VISTAS_DANO_ESTETICO_LAPTOP
            + VISTAS_DANO_ESTETICO_ESCRITORIO
            + VISTAS_DANO_ESTETICO_AIO
        )

        bloques = []
        for vista in vistas:
            try:
                img = RLImage(
                    vista.imagen_anotada.path,
                    width=72 * mm,
                    height=42 * mm,
                    kind='proportional',
                )
            except Exception:
                img = Paragraph('(imagen no disponible)', self._estilos['CeldaValor'])
            # Solo el nombre de la pieza (Pantalla, Top Cover…). El tipo de
            # daño (Desgaste, etc.) se ve en el diagrama anotado; no lo
            # repetimos en el título de la tarjeta.
            titulo = labels.get(vista.clave_vista, vista.clave_vista)
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
                ('ALIGN', (0, 1), (-1, 1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))
            bloques.append(tarjeta)

        for i in range(0, len(bloques), 2):
            izq = bloques[i]
            der = bloques[i + 1] if i + 1 < len(bloques) else ''
            fila = Table([[izq, der]], colWidths=['50%', '50%'])
            fila.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ]))
            elementos.append(KeepTogether([fila, Spacer(1, 2 * mm)]))
        return elementos

    def _construir_escaneo(self) -> List:
        """Página con foto(s) de resultado PC Audit."""
        from servicio_tecnico.models import ImagenOrden

        elementos = [
            self._crear_header_seccion('Resultado del escaneo (PC Audit)'),
            Spacer(1, 4 * mm),
        ]
        imagenes = list(
            ImagenOrden.objects.filter(
                orden=self.orden,
                tipo='escaneo_garantia',
            ).order_by('-fecha_subida')[:4]
        )
        for img_orden in imagenes:
            try:
                rl_img = RLImage(
                    img_orden.imagen.path,
                    width=140 * mm,
                    height=160 * mm,
                    kind='proportional',
                )
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
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            elementos.append(KeepTogether([tarjeta, Spacer(1, 5 * mm)]))
        return elementos

    def _tipo_dispositivo_checks(self) -> str:
        """
        Casillas NOTEBOOK / TABLET / PC / AIO vacías (se marcan a mano en papel).

        Returns:
            str: HTML con las cuatro casillas sin marcar.
        """
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Antes marcábamos según tipo_equipo de SIGMA ([X] NOTEBOOK, etc.).
        # En el papel Dell el auditor lo llena a mano, así que dejamos todo vacío.
        partes = []
        for etiqueta in ('NOTEBOOK', 'TABLET', 'PC', 'AIO'):
            partes.append(f'[&#160;] {etiqueta}')
        return ' &nbsp;&nbsp; '.join(partes)

    def _generar_qr_whatsapp(self, lado_mm: float = 22) -> Optional[RLImage]:
        """
        Genera un QR hacia el primer WhatsApp del pie Dell.

        Args:
            lado_mm: tamaño del cuadrado en milímetros.

        Returns:
            RLImage o None si falla la librería qrcode.
        """
        try:
            import qrcode
        except ImportError:
            logger.warning('[PDF_FORMATO_GARANTIA] qrcode no disponible; se omite QR')
            return None

        # wa.me espera dígitos internacionales (México = 52)
        digitos = ''.join(c for c in WHATSAPP_FORMATO_GARANTIA_NUMEROS[0] if c.isdigit())
        url = f'https://wa.me/52{digitos}'
        try:
            qr = qrcode.QRCode(version=1, box_size=4, border=1)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color='black', back_color='white')
            # EXPLICACIÓN PARA PRINCIPIANTES:
            # RLImage de ReportLab pide una ruta de archivo (o file-like BytesIO
            # en algunas versiones). Guardamos el PNG en BytesIO y lo pasamos
            # directo; si falla, caemos a archivo temporal.
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            buf.seek(0)
            try:
                return RLImage(buf, width=lado_mm * mm, height=lado_mm * mm)
            except Exception:
                import tempfile
                import os
                fd, ruta = tempfile.mkstemp(suffix='.png')
                os.close(fd)
                with open(ruta, 'wb') as fh:
                    fh.write(buf.getvalue())
                # Guardamos la ruta para no perder el archivo antes de build()
                if not hasattr(self, '_qr_temp_paths'):
                    self._qr_temp_paths = []
                self._qr_temp_paths.append(ruta)
                return RLImage(ruta, width=lado_mm * mm, height=lado_mm * mm)
        except Exception as exc:
            logger.warning('[PDF_FORMATO_GARANTIA] No se pudo generar QR: %s', exc)
            return None

    def _construir_pagina_servicio_final(self) -> List:
        """
        Última página estilo papel Dell «SERVICIO FINAL».

        Objetivo de negocio:
            Sustituye el aviso de privacidad SIC (solo aplica a OOW). Aquí van
            las exclusiones Dell (1–15), firma ENTERADO Y ACEPTADO, checklist
            del auditor de calidad y el pie de WhatsApp.

        Efectos secundarios:
            Ninguno sobre BD; solo construye flowables ReportLab.
        """
        elementos: List = []
        elementos += self._construir_header()
        elementos.append(Spacer(1, 1.5 * mm))

        # --- Título SERVICIO FINAL + frase de aceptación ---
        elementos.append(self._crear_header_seccion('SERVICIO FINAL'))
        elementos.append(Paragraph(
            'Acepto las condiciones y estado en el que recibo el equipo del CIS',
            self._estilos['ServicioFinalAcepto'],
        ))
        elementos.append(Spacer(1, 1.2 * mm))

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # En el papel Dell estos campos se llenan a mano al entregar el equipo.
        # No auto-rellenamos con el técnico de SIGMA.
        linea_tec = '<b>Técnico que repara:</b> __________________________'
        linea_entrega = (
            '<b>Persona que entrega el equipo:</b> __________________________'
        )
        linea_pruebas = (
            '<b>Se realizan pruebas frente al usuario</b> &nbsp; Si [ ] &nbsp; No [ ]'
        )
        firma_cli = Paragraph(
            '________________________________________<br/>'
            '<font size="5.5">Nombre Cliente - Fecha - Firma</font>',
            self._estilos['FirmaLabel'],
        )
        bloque_izq = Table(
            [
                [Paragraph(linea_tec, self._estilos['ServicioFinalCampo'])],
                [Paragraph(linea_entrega, self._estilos['ServicioFinalCampo'])],
                [Paragraph(linea_pruebas, self._estilos['ServicioFinalCampo'])],
            ],
            colWidths=[110 * mm],
        )
        bloque_izq.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        fila_entrega = Table(
            [[bloque_izq, firma_cli]],
            colWidths=[115 * mm, ANCHO_UTIL - 115 * mm],
        )
        fila_entrega.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elementos.append(fila_entrega)
        elementos.append(Spacer(1, 1.2 * mm))

        elementos.append(Paragraph(
            '¿Cuál es su nivel de satisfaccion del servicio recibido? '
            '&nbsp;&nbsp; <b>Insatisfecho</b> [ ] &nbsp;&nbsp;&nbsp; <b>Satisfecho</b> [ ]',
            self._estilos['ServicioFinalCampo'],
        ))
        elementos.append(Spacer(1, 0.8 * mm))
        elementos.append(Paragraph(
            '<b>Observaciones cliente:</b> '
            '___________________________________________________________________________',
            self._estilos['ServicioFinalCampo'],
        ))
        elementos.append(Spacer(1, 2 * mm))

        # --- Exclusiones Dell 1–15 ---
        elementos.append(Paragraph(
            'ACTIVIDADES NO INCLUIDAS EN EL SERVICIO DE GARANTIA',
            self._estilos['ExclusionesTitulo'],
        ))
        elementos.append(Spacer(1, 1 * mm))
        for i, texto in enumerate(ACTIVIDADES_NO_INCLUIDAS_GARANTIA_DELL, start=1):
            elementos.append(Paragraph(
                f'<b>{i}.</b> {self._esc(texto)}',
                self._estilos['ExclusionItem'],
            ))
        elementos.append(Spacer(1, 2.5 * mm))

        # --- Firma ENTERADO Y ACEPTADO + QR ---
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Aquí reutilizamos la misma firma digital capturada en el wizard
        # (firma_cliente). En el papel se firma a mano; en SIGMA ya la tenemos.
        qr_img = self._generar_qr_whatsapp(20)
        firma_img = None
        if self.formato.firma_cliente:
            try:
                firma_img = RLImage(
                    self.formato.firma_cliente.path,
                    width=48 * mm,
                    height=16 * mm,
                    kind='proportional',
                )
            except Exception:
                firma_img = None

        nombre_cli = (
            getattr(self.detalle, 'nombre_cliente', None)
            or getattr(self.detalle, 'contacto_cliente', None)
            or ''
        )
        nombre_cli = (nombre_cli or '').strip()

        filas_firma: List[List] = [
            [Paragraph('NOMBRE Y FIRMA DEL CLIENTE', self._estilos['FirmaLabel'])],
        ]
        if firma_img is not None:
            filas_firma.append([firma_img])
        else:
            filas_firma.append([
                Paragraph('_____________________________________', self._estilos['FirmaLabel']),
            ])
        if nombre_cli:
            filas_firma.append([
                Paragraph(self._esc(nombre_cli), self._estilos['FirmaLabel']),
            ])
        filas_firma.append([
            Paragraph('<b>ENTERADO Y ACEPTADO</b>', self._estilos['FirmaLabel']),
        ])

        firma_bloque = Table(filas_firma, colWidths=[90 * mm])
        firma_bloque.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))
        celda_qr = qr_img if qr_img is not None else Paragraph('', self._estilos['CeldaValor'])
        fila_firma_qr = Table(
            [[firma_bloque, celda_qr]],
            colWidths=[ANCHO_UTIL - 28 * mm, 28 * mm],
        )
        fila_firma_qr.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elementos.append(fila_firma_qr)
        elementos.append(Spacer(1, 2 * mm))

        # --- Checklist auditor ---
        elementos += self._construir_checklist_auditor()
        elementos.append(Spacer(1, 1.5 * mm))

        # Daños cosméticos + DPS / Revisa / Fecha / Técnico
        obs = (self.formato.observaciones_tecnicas or '').strip()
        desc_dano = self._esc(obs[:180]) if obs else '_______________________________'
        elementos.append(Paragraph(
            f"<b>Seleccione con una 'X' los daños cosméticos que tiene el equipo</b>"
            f'&nbsp;&nbsp;&nbsp; <b>Descripción:</b> {desc_dano}',
            self._estilos['ChecklistMini'],
        ))
        elementos.append(Spacer(1, 1.2 * mm))

        pie_datos = Table(
            [[
                Paragraph(
                    f'<b>Número de DPS:</b> {self._esc(self._dps())}',
                    self._estilos['ServicioFinalCampo'],
                ),
                Paragraph(
                    '<b>Revisa:</b> ______________________',
                    self._estilos['ServicioFinalCampo'],
                ),
            ], [
                Paragraph(
                    '<b>Fecha:</b> _______________',
                    self._estilos['ServicioFinalCampo'],
                ),
                Paragraph(
                    '<b>Técnico a cargo:</b> _____________________________',
                    self._estilos['ServicioFinalCampo'],
                ),
            ]],
            colWidths=['50%', '50%'],
        )
        pie_datos.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elementos.append(pie_datos)
        elementos.append(Spacer(1, 2 * mm))

        # --- Pie WhatsApp ---
        icono = Table(
            [[Paragraph('<b>WA</b>', ParagraphStyle(
                'WAIcon',
                fontName='Helvetica-Bold',
                fontSize=8,
                textColor=COLOR_BLANCO,
                alignment=TA_CENTER,
                leading=10,
            ))]],
            colWidths=[10 * mm],
            rowHeights=[10 * mm],
        )
        icono.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_WHATSAPP),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_WHATSAPP),
        ]))
        texto_wa = Paragraph(
            self._esc(WHATSAPP_FORMATO_GARANTIA_TEXTO),
            self._estilos['WhatsAppPie'],
        )
        pie_wa = Table(
            [[icono, texto_wa]],
            colWidths=[12 * mm, ANCHO_UTIL - 12 * mm],
        )
        pie_wa.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.8, COLOR_GRIS_BORDE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_GRIS_ALT),
        ]))
        elementos.append(pie_wa)
        return elementos

    def _construir_checklist_auditor(self) -> List:
        """
        Tabla del auditor de calidad (Si/No + observaciones).

        Returns:
            list: flowables (marca/tipo + nota + tabla checklist).
        """
        elementos: List = []
        marca = getattr(self.detalle, 'marca', '') or ''
        cabecera = Table(
            [[
                Paragraph(
                    f'<b>Marca</b> {self._esc(marca)}',
                    self._estilos['ChecklistMiniBold'],
                ),
                Paragraph(
                    f'<b>Tipo de dispositivo</b> &nbsp; {self._tipo_dispositivo_checks()}',
                    self._estilos['ChecklistMini'],
                ),
            ]],
            colWidths=['28%', '72%'],
        )
        cabecera.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_GRIS_ALT),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 3),
            ('RIGHTPADDING', (0, 0), (-1, -1), 3),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elementos.append(cabecera)
        elementos.append(Spacer(1, 0.8 * mm))
        elementos.append(Paragraph(
            'Estimado Auditor de Calidad, por favor llena todos los campos del checklist, '
            'en caso de tener más de 2 NO devolver al técnico encargado de la reparación, '
            'recuerda que tu participación es muy importante antes de entregar un equipo.',
            self._estilos['AuditorNota'],
        ))
        elementos.append(Spacer(1, 0.8 * mm))

        # Encabezado de columnas
        data: List[List] = [[
            Paragraph('<b></b>', self._estilos['ChecklistMiniBold']),
            Paragraph('<b></b>', self._estilos['ChecklistMiniBold']),
            Paragraph('<b>Funciona</b>', self._estilos['ChecklistMiniBold']),
            Paragraph('', self._estilos['ChecklistMini']),
            Paragraph('<b>Observaciones</b>', self._estilos['ChecklistMiniBold']),
        ], [
            Paragraph('', self._estilos['ChecklistMini']),
            Paragraph('', self._estilos['ChecklistMini']),
            Paragraph('<b>SI</b>', self._estilos['ChecklistMiniBold']),
            Paragraph('<b>NO</b>', self._estilos['ChecklistMiniBold']),
            Paragraph('', self._estilos['ChecklistMini']),
        ]]

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Si la categoría viene vacía, repetimos la anterior visualmente
        # solo en la primera fila del grupo (como el papel: celda fusionada).
        categoria_actual = ''
        for categoria, item in CHECKLIST_AUDITOR_GARANTIA_DELL:
            if categoria:
                categoria_actual = categoria
                cat_txt = categoria_actual
            else:
                cat_txt = ''
            data.append([
                Paragraph(self._esc(cat_txt), self._estilos['ChecklistMiniBold']),
                Paragraph(self._esc(item), self._estilos['ChecklistMini']),
                # &#160; = espacio que ReportLab no comprime (así se ve "[ ]" y no "[]")
                Paragraph('[&#160;]', self._estilos['ChecklistMini']),
                Paragraph('[&#160;]', self._estilos['ChecklistMini']),
                Paragraph('', self._estilos['ChecklistMini']),
            ])

        col_w = [32 * mm, 38 * mm, 12 * mm, 12 * mm, ANCHO_UTIL - 94 * mm]
        tabla = Table(data, colWidths=col_w)
        estilo = TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_NEGRO),
            ('INNERGRID', (0, 0), (-1, -1), 0.3, COLOR_GRIS_BORDE),
            ('BACKGROUND', (0, 0), (-1, 1), COLOR_GRIS_ALT),
            ('SPAN', (2, 0), (3, 0)),  # "Funciona" abarca SI/NO
            ('ALIGN', (2, 0), (3, 1), 'CENTER'),
            ('ALIGN', (2, 2), (3, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 0.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 0.5),
        ])
        # Filas alternas suaves para leer mejor
        for fila_idx in range(2, len(data)):
            if fila_idx % 2 == 0:
                estilo.add('BACKGROUND', (0, fila_idx), (-1, fila_idx), colors.HexColor('#FAFAFA'))
        tabla.setStyle(estilo)
        elementos.append(tabla)
        return elementos
