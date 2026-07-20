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
4. Páginas finales — Aviso de Privacidad México
"""

from __future__ import annotations

import io
import logging
from datetime import date
from typing import Any, Dict, List, Optional

from django.contrib.staticfiles import finders
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
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
    AVISO_PRIVACIDAD_OOW_MX,
    AVISO_PRIVACIDAD_OOW_PLACEHOLDER_OTROS,
    AVISO_PRIVACIDAD_OOW_VERSION_MX,
    TEXTO_PC_AUDIT_FORMATO_GARANTIA,
    TEXTO_TIEMPO_RESPUESTA_GARANTIA,
    TEXTOS_LEGALES_FORMATO_GARANTIA_DER,
    TEXTOS_LEGALES_FORMATO_GARANTIA_IZQ,
    VISTAS_DANO_ESTETICO_AIO,
    VISTAS_DANO_ESTETICO_ESCRITORIO,
    VISTAS_DANO_ESTETICO_LAPTOP,
)
from config.paises_config import get_pais_actual

logger = logging.getLogger('servicio_tecnico')

# Colores del formato papel Dell/SICSER (barras grises, no navy cotización)
COLOR_NAVY = colors.HexColor('#003366')
COLOR_GRIS_HEADER = colors.HexColor('#6E6E6E')
COLOR_GRIS_ALT = colors.HexColor('#F2F2F2')
COLOR_GRIS_BORDE = colors.HexColor('#CCCCCC')
COLOR_AMARILLO_BG = colors.HexColor('#FFF2CC')
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

            # --- Aviso de privacidad ---
            elementos += self._construir_aviso_privacidad()

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
        Cabecera Dell | ORDEN DE SERVICIO | SIC (como el papel).

        Layout: logo Dell izq + banner gris título + logo SIC der.
        """
        logo_dell = self._cargar_logo('logo_dell.png', 18, 18)
        logo_sic = (
            self._cargar_logo('logo_sic_formato.png', 28, 10)
            or self._cargar_logo('logo_sic.png', 28, 11)
        )

        banner = Table(
            [[Paragraph('ORDEN DE SERVICIO', self._estilos['TituloBanner'])]],
            colWidths=[95 * mm],
        )
        banner.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_GRIS_HEADER),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
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
                self._campo_inline('Dirección', ''),
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
        """Diagnóstico vacío + tabla de piezas (líneas en blanco como el papel)."""
        elementos = [
            self._crear_header_seccion('DIAGNÓSTICO TÉCNICO REALIZADO'),
            Spacer(1, 10 * mm),
            self._crear_header_seccion(
                'NOMBRE DE LA PARTE Y/O WIP PIEZAS / REMPLAZO No.de Serie'
            ),
            Spacer(1, 2 * mm),
        ]
        lineas = [
            [
                Paragraph('1. ___________________________', self._estilos['CeldaValor']),
                Paragraph('2. ___________________________', self._estilos['CeldaValor']),
            ],
            [
                Paragraph('#. ___________________________', self._estilos['CeldaValor']),
                Paragraph('#. ___________________________', self._estilos['CeldaValor']),
            ],
        ]
        tabla = Table(lineas, colWidths=['50%', '50%'])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elementos.append(tabla)

        # Observaciones del wizard: no las metemos en pág.1 del papel Dell;
        # si existen, van en un renglón chico bajo piezas para no perderlas.
        obs = (self.formato.observaciones_tecnicas or '').strip()
        if obs:
            elementos.append(Spacer(1, 2 * mm))
            elementos.append(Paragraph(
                f'<b>Observaciones técnicas:</b> {self._esc(obs)}',
                self._estilos['CuerpoChico'],
            ))
        return elementos

    def _construir_firma_aceptacion(self, compacto: bool = False) -> List:
        """Bloque ACEPTO + firma del cliente."""
        elementos = [
            Paragraph(
                'ACEPTO LAS CONDICIONES EN LAS QUE ENTREGO EL EQUIPO '
                'AL CENTRO DE SERVICIO',
                ParagraphStyle(
                    'AceptaGar',
                    parent=self._estilos['CeldaLabel'],
                    alignment=TA_CENTER,
                    fontSize=8,
                    leading=10,
                ),
            ),
            Spacer(1, 4 * mm if compacto else 6 * mm),
        ]
        firma_cli = None
        if self.formato.firma_cliente:
            try:
                firma_cli = RLImage(
                    self.formato.firma_cliente.path,
                    width=45 * mm,
                    height=18 * mm,
                    kind='proportional',
                )
            except Exception:
                firma_cli = None

        col_cli = [
            [firma_cli or Paragraph(' ', self._estilos['CeldaValor'])],
            [HRFlowable(width='55%', thickness=0.6, color=COLOR_NEGRO)],
            [Paragraph('<b>FIRMA CLIENTE</b>', self._estilos['FirmaLabel'])],
        ]
        tabla = Table(
            [[Table(col_cli, colWidths=[90 * mm])]],
            colWidths=[letter[0] - 2 * MARGEN],
        )
        tabla.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elementos.append(tabla)
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
            titulo = labels.get(vista.clave_vista, vista.clave_vista)
            if vista.etiqueta_dano:
                titulo = f'{titulo} — {vista.etiqueta_dano}'
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

    def _construir_aviso_privacidad(self) -> List:
        """Página(s) finales con el aviso de privacidad (igual OOW)."""
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

        codigo = (self.pais_config.get('codigo') or 'MX').upper()
        if codigo == 'MX':
            texto = AVISO_PRIVACIDAD_OOW_MX
            version = self.formato.version_aviso_privacidad or AVISO_PRIVACIDAD_OOW_VERSION_MX
        else:
            texto = AVISO_PRIVACIDAD_OOW_PLACEHOLDER_OTROS
            version = self.formato.version_aviso_privacidad or f'{codigo.lower()}-placeholder'

        for bloque in texto.split('\n\n'):
            limpio = ' '.join(bloque.split())
            if not limpio:
                continue
            elementos.append(Paragraph(self._esc(limpio), self._estilos['CuerpoChico']))
            elementos.append(Spacer(1, 1.5 * mm))

        elementos.append(Spacer(1, 3 * mm))
        elementos.append(Paragraph(
            f'<b>Versión del aviso aceptada:</b> {self._esc(version)}. '
            'El cliente aceptó este aviso digitalmente al finalizar el '
            'Formato Garantía Dell en SIGMA.',
            self._estilos['CeldaValor'],
        ))
        return elementos
