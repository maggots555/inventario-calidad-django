"""
Generador PDF — Formato de Servicio Fuera de Garantía (OOW)

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Este módulo crea el PDF profesional del formato OOW con el MISMO estilo
visual que las cotizaciones al cliente (Platypus + headers navy #003366).

NO usa el layout “papel” de RHITSO (canvas manual). Usa tablas y párrafos
como PDFCotizacionCliente.

Estructura:
1. Header logo + empresa + fecha/folio
2. Título del formato
3. Datos cliente / equipo
4. Accesorios + observaciones
5. Daños estéticos (imágenes anotadas)
6. Firmas
7. Página(s) Aviso de Privacidad México
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
    AVISO_PRIVACIDAD_OOW_VERSION_MX,
    VISTAS_DANO_ESTETICO_ESCRITORIO,
    VISTAS_DANO_ESTETICO_LAPTOP,
)
from config.paises_config import get_pais_actual

logger = logging.getLogger('servicio_tecnico')

# Colores corporativos (idénticos a cotización cliente)
COLOR_NAVY = colors.HexColor('#003366')
COLOR_NAVY_LIGHT = colors.HexColor('#1d4e8f')
COLOR_GRIS_ALT = colors.HexColor('#F2F2F2')
COLOR_GRIS_BORDE = colors.HexColor('#CCCCCC')
COLOR_AMARILLO_BG = colors.HexColor('#FFF2CC')
COLOR_ROJO_BG = colors.HexColor('#FDECEC')
COLOR_ROJO_ALERTA = colors.HexColor('#C00000')
COLOR_BLANCO = colors.white
COLOR_NEGRO = colors.black

MARGEN = 15 * mm


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
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_titulo()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_datos_cliente()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_datos_equipo()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_accesorios()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_observaciones()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_danos()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_aceptacion_y_firmas()
            elementos += self._construir_aviso_privacidad()

            doc.build(elementos)
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
            fontSize=13,
            textColor=COLOR_BLANCO,
            alignment=TA_CENTER,
            leading=16,
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
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
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
        """Carga logo SIC PNG desde static si existe."""
        ruta = finders.find('images/logos/logo_sic.png')
        if not ruta:
            return None
        try:
            img = RLImage(ruta, width=45 * mm, height=18 * mm)
            return img
        except Exception:
            return None

    def _construir_header(self) -> List:
        """Logo + empresa + fecha/folio."""
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
        elementos.append(Spacer(1, 2 * mm))

        hoy = date.today()
        meses = [
            'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
            'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
        ]
        fecha_txt = f'{hoy.day} de {meses[hoy.month - 1]} de {hoy.year}'
        folio = (
            self.detalle.folio_sicser
            or self.detalle.orden_cliente
            or self.orden.numero_orden_interno
        )
        meta = Table(
            [[
                Paragraph(f'<b>Fecha:</b> {self._esc(fecha_txt)}', self._estilos['CeldaValor']),
                Paragraph(
                    f'<b>Orden de servicio:</b> {self._esc(folio)}',
                    self._estilos['CeldaValor'],
                ),
            ]],
            colWidths=['50%', '50%'],
        )
        meta.setStyle(TableStyle([
            ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ]))
        elementos.append(meta)
        return elementos

    def _construir_titulo(self) -> List:
        """Título principal navy."""
        return [self._crear_header_seccion(
            'FORMATO DE SERVICIO FUERA DE GARANTÍA CON COSTO'
        )]

    def _fila_dato(self, label: str, valor: str) -> list:
        return [
            Paragraph(self._esc(label), self._estilos['CeldaLabel']),
            Paragraph(self._esc(valor or '—'), self._estilos['CeldaValor']),
        ]

    def _tabla_pares(self, pares: List[tuple]) -> Table:
        """Tabla 2 columnas label|valor con filas alternadas."""
        data = [self._fila_dato(l, v) for l, v in pares]
        tabla = Table(data, colWidths=[45 * mm, None])
        estilos = [
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]
        for i in range(len(data)):
            if i % 2 == 0:
                estilos.append(('BACKGROUND', (0, i), (-1, i), COLOR_GRIS_ALT))
        tabla.setStyle(TableStyle(estilos))
        return tabla

    def _construir_datos_cliente(self) -> List:
        elementos = [self._crear_header_seccion('Datos del cliente'), Spacer(1, 2 * mm)]
        d = self.detalle
        pares = [
            ('Nombre / Razón social', d.nombre_cliente),
            ('RFC', d.rfc_cliente),
            ('Email de contacto', d.email_cliente),
            ('Teléfono(s)', d.telefono_cliente),
            ('Email envío formato', self.formato.email_envio),
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
        elementos = [self._crear_header_seccion('Accesorios recibidos'), Spacer(1, 2 * mm)]
        f = self.formato
        checks = [
            ('Cargador', f.accesorio_cargador),
            ('Maletín', f.accesorio_maletin),
            ('Mouse', f.accesorio_mouse),
            ('Teclado', f.accesorio_teclado),
            ('Monitor', f.accesorio_monitor),
            ('Otros', f.accesorio_otros),
        ]
        celdas = []
        for nombre, activo in checks:
            marca = '☑' if activo else '☐'
            celdas.append(Paragraph(f'{marca} {nombre}', self._estilos['CeldaValor']))
        # 3 columnas
        filas = []
        for i in range(0, len(celdas), 3):
            fila = celdas[i:i + 3]
            while len(fila) < 3:
                fila.append('')
            filas.append(fila)
        tabla = Table(filas, colWidths=['33%', '33%', '34%'])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elementos.append(tabla)
        if f.accesorios_otros_detalle:
            elementos.append(Spacer(1, 2 * mm))
            elementos.append(Paragraph(
                f'<b>Detalle otros:</b> {self._esc(f.accesorios_otros_detalle)}',
                self._estilos['CeldaValor'],
            ))
        return elementos

    def _construir_observaciones(self) -> List:
        elementos = [self._crear_header_seccion('Observaciones técnicas'), Spacer(1, 2 * mm)]
        obs = self.formato.observaciones_tecnicas or '—'
        elementos.append(Paragraph(self._esc(obs), self._estilos['CuerpoNormal']))
        if self.formato.disclaimer_pc_audit:
            elementos.append(Spacer(1, 2 * mm))
            aviso = (
                'NO SE PUDO UTILIZAR LA HERRAMIENTA DE DIAGNÓSTICO (PC AUDIT) DEBIDO A QUE '
                'EL EQUIPO NO ENCIENDE, NO CUENTA CON SISTEMA OPERATIVO WINDOWS O SU FALLA '
                'IMPOSIBILITA EL USO DE DICHA HERRAMIENTA.'
            )
            bloque = Table(
                [[Paragraph(aviso, self._estilos['CeldaValor'])]],
                colWidths=[letter[0] - 2 * MARGEN],
            )
            bloque.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), COLOR_AMARILLO_BG),
                ('BOX', (0, 0), (-1, -1), 0.8, COLOR_NAVY),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            elementos.append(bloque)
        return elementos

    def _construir_danos(self) -> List:
        elementos = [
            self._crear_header_seccion('Registro de daños estéticos'),
            Spacer(1, 2 * mm),
        ]
        vistas = list(self.formato.vistas_dano.exclude(imagen_anotada='').exclude(imagen_anotada=None))
        if not vistas:
            elementos.append(Paragraph(
                'Sin anotaciones de daños en diagramas.',
                self._estilos['CeldaValor'],
            ))
            return elementos

        # Mapa etiqueta amigable
        labels = dict(VISTAS_DANO_ESTETICO_LAPTOP + VISTAS_DANO_ESTETICO_ESCRITORIO)
        celdas_img = []
        for vista in vistas:
            try:
                path = vista.imagen_anotada.path
                img = RLImage(path, width=55 * mm, height=40 * mm, kind='proportional')
            except Exception:
                img = Paragraph('(imagen no disponible)', self._estilos['CeldaValor'])
            titulo = labels.get(vista.clave_vista, vista.clave_vista)
            if vista.etiqueta_dano:
                titulo = f'{titulo} — {vista.etiqueta_dano}'
            celdas_img.append([
                Paragraph(f'<b>{self._esc(titulo)}</b>', self._estilos['CeldaLabel']),
                img,
            ])

        # 2 columnas
        filas = []
        for i in range(0, len(celdas_img), 2):
            izq = celdas_img[i]
            der = celdas_img[i + 1] if i + 1 < len(celdas_img) else ['', '']
            filas.append([
                Table([[izq[0]], [izq[1]]], colWidths=[85 * mm]),
                Table([[der[0]], [der[1]]], colWidths=[85 * mm]) if der[0] else '',
            ])

        tabla = Table(filas, colWidths=['50%', '50%'])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        elementos.append(tabla)
        return elementos

    def _construir_aceptacion_y_firmas(self) -> List:
        elementos = [
            self._crear_header_seccion('Aceptación y firma del cliente'),
            Spacer(1, 2 * mm),
        ]
        elementos.append(Paragraph(
            'ACEPTO LAS CONDICIONES EN LAS QUE ENTREGO EL EQUIPO AL CENTRO DE SERVICIO.',
            self._estilos['CeldaLabel'],
        ))
        elementos.append(Spacer(1, 3 * mm))

        # Solo firma del cliente (no se registra técnico en este formato)
        firma_cli = self._imagen_firma(self.formato.firma_cliente)
        col_cli = [
            [firma_cli or Paragraph(' ', self._estilos['CeldaValor'])],
            [HRFlowable(width='60%', thickness=0.6, color=COLOR_NEGRO)],
            [Paragraph('<b>FIRMA CLIENTE</b>', self._estilos['FirmaLabel'])],
        ]
        tabla = Table(
            [[Table(col_cli, colWidths=[100 * mm])]],
            colWidths=[letter[0] - 2 * MARGEN],
        )
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        elementos.append(tabla)

        if self.formato.como_enteraste:
            elementos.append(Spacer(1, 3 * mm))
            elementos.append(Paragraph(
                f'<b>¿Cómo se enteró?</b> {self._esc(self.formato.get_como_enteraste_display())}',
                self._estilos['CeldaValor'],
            ))
        return elementos

    def _imagen_firma(self, campo) -> Optional[RLImage]:
        if not campo:
            return None
        try:
            return RLImage(campo.path, width=50 * mm, height=22 * mm, kind='proportional')
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

        codigo = (self.pais_config.get('codigo') or 'MX').upper()
        if codigo == 'MX':
            texto = AVISO_PRIVACIDAD_OOW_MX
            version = self.formato.version_aviso_privacidad or AVISO_PRIVACIDAD_OOW_VERSION_MX
        else:
            texto = AVISO_PRIVACIDAD_OOW_PLACEHOLDER_OTROS
            version = self.formato.version_aviso_privacidad or f'{codigo.lower()}-placeholder'

        # Dividir en párrafos por líneas en blanco
        for bloque in texto.split('\n\n'):
            limpio = ' '.join(bloque.split())
            if not limpio:
                continue
            elementos.append(Paragraph(self._esc(limpio), self._estilos['CuerpoChico']))
            elementos.append(Spacer(1, 1.5 * mm))

        elementos.append(Spacer(1, 3 * mm))
        elementos.append(Paragraph(
            f'<b>Versión del aviso aceptada:</b> {self._esc(version)}. '
            'El cliente aceptó este aviso digitalmente al finalizar el Formato OOW en SIGMA.',
            self._estilos['CeldaValor'],
        ))
        return elementos
