"""
Generador PDF — Formato de Servicio Fuera de Garantía (OOW)

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
Este módulo crea el PDF profesional del formato OOW con el MISMO estilo
visual que las cotizaciones al cliente (Platypus + headers navy #003366).

NO usa el layout “papel” de RHITSO (canvas manual). Usa tablas y párrafos
como PDFCotizacionCliente.

Estructura (páginas bien separadas, sin encimar):
1. Página 1 — Header + título + cliente + equipo + accesorios + observaciones
2. Página siguiente — Registro de daños estéticos (diagramas anotados)
3. Página siguiente — Resultado del escaneo (si hay fotos)
4. Página siguiente — Aceptación y firma del cliente
5. Página(s) finales — Aviso de Privacidad México
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
    AVISO_PRIVACIDAD_OOW_MX,
    AVISO_PRIVACIDAD_OOW_PLACEHOLDER_OTROS,
    AVISO_PRIVACIDAD_OOW_VERSION_MX,
    VISTAS_DANO_ESTETICO_AIO,
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
            # --- Página 1: datos generales (secciones con espacio claro) ---
            elementos += self._construir_header()
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._construir_titulo()
            elementos.append(Spacer(1, 5 * mm))
            # Orden de servicio justo debajo del título (mismo estilo que cliente)
            elementos += self._envolver_seccion(self._construir_orden_servicio())
            elementos.append(Spacer(1, 5 * mm))
            elementos += self._envolver_seccion(self._construir_datos_cliente())
            elementos.append(Spacer(1, 5 * mm))
            elementos += self._envolver_seccion(self._construir_datos_equipo())
            elementos.append(Spacer(1, 5 * mm))
            elementos += self._envolver_seccion(self._construir_accesorios())
            elementos.append(Spacer(1, 5 * mm))
            elementos += self._envolver_seccion(self._construir_observaciones())

            # --- Página nueva: daños estéticos (nunca se mezcla con lo anterior) ---
            elementos.append(PageBreak())
            elementos += self._construir_danos()

            # --- Escaneo: página propia solo si hay fotos (evita hoja casi vacía) ---
            if self._tiene_fotos_escaneo():
                elementos.append(PageBreak())
                elementos += self._construir_escaneo()

            # --- Página nueva: firma del cliente ---
            elementos.append(PageBreak())
            elementos += self._construir_aceptacion_y_firmas()

            # --- Aviso de privacidad (ya trae su PageBreak interno) ---
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
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
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
        de secciones de la página 1.
        """
        elementos = [self._crear_header_seccion('Orden de servicio'), Spacer(1, 2 * mm)]
        hoy = date.today()
        fecha_txt = hoy.strftime('%Y-%m-%d')
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
        """
        elementos = [self._crear_header_seccion('Accesorios entregados'), Spacer(1, 2 * mm)]
        f = self.formato
        pares = [
            ('Cargador', 'SI' if f.accesorio_cargador else 'NO'),
            ('Maletín', 'SI' if f.accesorio_maletin else 'NO'),
            ('Mouse', 'SI' if f.accesorio_mouse else 'NO'),
            ('Teclado', 'SI' if f.accesorio_teclado else 'NO'),
            ('Monitor', 'SI' if f.accesorio_monitor else 'NO'),
            ('Otros', 'SI' if f.accesorio_otros else 'NO'),
        ]
        elementos.append(self._tabla_pares(pares))
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
        """
        Página dedicada al registro de daños estéticos.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Cada par de diagramas va en un KeepTogether para que una imagen
        no se corte a la mitad ni se encime con el título de otra.
        """
        elementos = [
            self._crear_header_seccion('Registro de daños estéticos'),
            Spacer(1, 4 * mm),
            Paragraph(
                'A continuación se muestran las vistas del equipo con las '
                'anotaciones de daños capturadas en el Formato Digital OOW.',
                self._estilos['CuerpoNormal'],
            ),
            Spacer(1, 4 * mm),
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
                # Un poco más chicas para que quepan 2 por fila sin apretarse
                img = RLImage(path, width=80 * mm, height=55 * mm, kind='proportional')
            except Exception:
                img = Paragraph('(imagen no disponible)', self._estilos['CeldaValor'])
            titulo = labels.get(vista.clave_vista, vista.clave_vista)
            if vista.etiqueta_dano:
                titulo = f'{titulo} — {vista.etiqueta_dano}'
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
                ('LEFTPADDING', (0, 0), (-1, -1), 4),
                ('RIGHTPADDING', (0, 0), (-1, -1), 4),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
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
            elementos.append(KeepTogether([fila, Spacer(1, 5 * mm)]))

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

    def _construir_aceptacion_y_firmas(self) -> List:
        elementos = [
            self._crear_header_seccion('Aceptación y firma del cliente'),
            Spacer(1, 4 * mm),
        ]
        elementos.append(Paragraph(
            'ACEPTO LAS CONDICIONES EN LAS QUE ENTREGO EL EQUIPO AL CENTRO DE SERVICIO.',
            self._estilos['CeldaLabel'],
        ))
        elementos.append(Spacer(1, 8 * mm))

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
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ]))
        elementos.append(KeepTogether([tabla]))

        if self.formato.como_enteraste:
            elementos.append(Spacer(1, 6 * mm))
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
