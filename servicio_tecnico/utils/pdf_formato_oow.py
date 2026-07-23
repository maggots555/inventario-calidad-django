"""
Generador PDF — Formato de Servicio Fuera de Garantía (OOW)

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Este módulo crea el PDF profesional del formato OOW con el MISMO estilo
visual que las cotizaciones al cliente (Platypus + headers navy #003366).

NO usa el layout “papel” de RHITSO (canvas manual). Usa tablas y párrafos
como PDFCotizacionCliente.

Estructura (páginas bien separadas, sin encimar):
1. Página 1 — Header + título + orden + cliente + equipo + accesorios
2. Página siguiente — Daños estéticos + observaciones técnicas + firma cliente
   (si no hay foto de escaneo, muestra aviso PC Audit en observaciones)
3. Página siguiente — Resultado del escaneo (solo si hay fotos)
4. Página(s) finales — Aviso de Privacidad México
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
    VISTAS_DANO_ESTETICO_AIO,
    VISTAS_DANO_ESTETICO_ESCRITORIO,
    VISTAS_DANO_ESTETICO_LAPTOP,
)
from config.paises_config import get_pais_actual

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
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._construir_titulo()
            elementos.append(Spacer(1, 5 * mm))
            elementos += self._envolver_seccion(self._construir_orden_servicio())
            elementos.append(Spacer(1, 5 * mm))
            elementos += self._envolver_seccion(self._construir_datos_cliente())
            elementos.append(Spacer(1, 5 * mm))
            elementos += self._envolver_seccion(self._construir_datos_equipo())
            elementos.append(Spacer(1, 5 * mm))
            elementos += self._envolver_seccion(self._construir_accesorios())

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

    def _crear_header_seccion(self, titulo: str) -> Table:
        """
        Barra navy de sección (igual que cotizaciones).

        Args:
            titulo: Texto del encabezado

        Returns:
            Table de una celda con fondo navy
        """
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

    def _construir_orden_servicio(self) -> List:
        """
        Sección Orden de servicio (mismo layout que Datos del cliente).

        EXPLICACIÓN PARA PRINCIPIANTES:
        Barra navy + tabla label|valor a todo el ancho, igual que el resto
        de secciones de la página 1. La fecha sale de finalizado_en (fecha
        real de cierre), no de "hoy", para que regenerar no la cambie.
        """
        elementos = [self._crear_header_seccion('Orden de servicio'), Spacer(1, 2 * mm)]
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
        elementos.append(self._tabla_pares(pares))
        return elementos

    def _fila_dato(self, label: str, valor: str) -> list:
        return [
            Paragraph(self._esc(label), self._estilos['CeldaLabel']),
            Paragraph(self._esc(valor or '—'), self._estilos['CeldaValor']),
        ]

    def _tabla_pares(self, pares: List[tuple], valores_flowables: bool = False) -> Table:
        """
        Tabla 2 columnas label|valor con jerarquía visual.

        Args:
            pares: lista de (label, valor). Si valores_flowables=False, valor es str.
            valores_flowables: si True, el segundo elemento ya es un flowable
                (p. ej. Paragraph SI/NO estilizado).

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

        tabla = Table(data, colWidths=[45 * mm, None])
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
            ('Nombre / Razón social', d.nombre_cliente),
            ('RFC', d.rfc_cliente),
            ('Email de contacto', d.email_cliente),
            ('Teléfono(s)', d.telefono_cliente),
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
        Accesorios entregados: tabla label|SI/NO (compatible con Helvetica).

        EXPLICACIÓN PARA PRINCIPIANTES:
        ReportLab con fuente Helvetica NO dibuja bien los símbolos ☑ / ☐
        (Unicode). Por eso usamos "SI" / "NO" en texto ASCII, visibles en el PDF.
        SI va en navy negrita y NO en gris para escanear más rápido en recepción.
        """
        elementos = [self._crear_header_seccion('Accesorios entregados'), Spacer(1, 2 * mm)]
        f = self.formato

        def _celda_si_no(activo: bool) -> Paragraph:
            if activo:
                return Paragraph('SI', self._estilos['AccesorioSi'])
            return Paragraph('NO', self._estilos['AccesorioNo'])

        pares = [
            ('Cargador', _celda_si_no(f.accesorio_cargador)),
            ('Maletín', _celda_si_no(f.accesorio_maletin)),
            ('Mouse', _celda_si_no(f.accesorio_mouse)),
            ('Teclado', _celda_si_no(f.accesorio_teclado)),
            ('Monitor', _celda_si_no(f.accesorio_monitor)),
            ('Otros', _celda_si_no(f.accesorio_otros)),
        ]
        elementos.append(self._tabla_pares(pares, valores_flowables=True))
        if f.accesorios_otros_detalle:
            elementos.append(Spacer(1, 2 * mm))
            elementos.append(Paragraph(
                f'<b>Detalle otros:</b> {self._esc(f.accesorios_otros_detalle)}',
                self._estilos['CeldaValor'],
            ))
        return elementos

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
        vistas = list(
            self.formato.vistas_dano.exclude(imagen_anotada='').exclude(imagen_anotada=None)
        )
        if not vistas:
            elementos.append(Paragraph(
                'Sin anotaciones de daños en diagramas.',
                self._estilos['CeldaValor'],
            ))
            return elementos

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Orden fijo del PDF (laptop): Pantalla → Top Cover → Palm → Bottom →
        # Lateral izq → Lateral der. Si el usuario guardó las vistas en otro
        # orden, aquí las reordenamos según el catálogo del tipo de diagrama.
        tipo = (self.formato.tipo_diagrama or 'laptop').lower()
        if tipo == 'escritorio':
            catalogo_orden = VISTAS_DANO_ESTETICO_ESCRITORIO
        elif tipo == 'aio':
            catalogo_orden = VISTAS_DANO_ESTETICO_AIO
        else:
            catalogo_orden = VISTAS_DANO_ESTETICO_LAPTOP

        orden_claves = {clave: idx for idx, (clave, _etiqueta) in enumerate(catalogo_orden)}
        vistas.sort(
            key=lambda v: (
                orden_claves.get(v.clave_vista, 999),
                v.clave_vista or '',
            )
        )

        # Mapa etiqueta amigable
        labels = dict(
            VISTAS_DANO_ESTETICO_LAPTOP
            + VISTAS_DANO_ESTETICO_ESCRITORIO
            + VISTAS_DANO_ESTETICO_AIO
        )
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
        # Ancho fijo de la firma para que imagen, línea y texto "FIRMA CLIENTE"
        # compartan la misma columna centrada dentro del recuadro (antes la
        # celda era muy ancha y la imagen quedaba a la izquierda).
        ancho_firma = 45 * mm if compacto else 50 * mm
        alto_firma = 18 * mm if compacto else 22 * mm
        firma_cli = None
        if self.formato.firma_cliente:
            try:
                firma_cli = RLImage(
                    self.formato.firma_cliente.path,
                    width=ancho_firma,
                    height=alto_firma,
                    kind='proportional',
                    hAlign='CENTER',
                )
            except Exception:
                firma_cli = self._imagen_firma(self.formato.firma_cliente)

        # Columna estrecha: firma + línea + etiqueta, todo centrado
        col_cli = [
            [firma_cli or Paragraph(' ', self._estilos['CeldaValor'])],
            [HRFlowable(
                width=ancho_firma,
                thickness=0.6,
                color=COLOR_NEGRO,
                hAlign='CENTER',
            )],
            [Paragraph('<b>FIRMA CLIENTE</b>', self._estilos['FirmaLabel'])],
        ]
        tabla_firma = Table(col_cli, colWidths=[ancho_firma])
        tabla_firma.setStyle(TableStyle([
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 1),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ]))

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

    def _imagen_firma(self, campo) -> Optional[RLImage]:
        """
        Carga la imagen de firma desde disco con tamaño estándar.

        Args:
            campo: FileField/ImageField de Django con la firma.

        Returns:
            RLImage centrada, o None si no se puede leer el archivo.
        """
        if not campo:
            return None
        try:
            # hAlign CENTER: alinea la imagen dentro de su celda padre
            return RLImage(
                campo.path,
                width=50 * mm,
                height=22 * mm,
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

        elementos.append(Spacer(1, 3 * mm))
        elementos.append(Paragraph(
            'El cliente aceptó este aviso digitalmente al finalizar el Formato OOW en SIGMA.',
            self._estilos['CeldaValor'],
        ))
        return elementos
