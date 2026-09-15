"""
Generador PDF — Formato de envío a RHITSO.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Este módulo crea el PDF que se adjunta al correo del laboratorio RHITSO.
Usa el MISMO estilo visual que OOW / Venta mostrador (Platypus + barras
navy #003366). Ya NO dibuja con canvas y coordenadas Y fijas: ese diseño
viejo ponía el pie ENCIMA del diagrama de daños.

Platypus apila bloques (tablas, párrafos, imágenes). Si no caben, saltan
a la página siguiente. El pie de página vive en el margen inferior y no
tapa los dibujos que RHITSO usa para marcar defectos a mano.

Estructura (misma información de siempre):
1. Header logo SIC + empresa + logo RHITSO
2. Título Formato RHITSO
3. Fecha y orden
4. Datos del equipo (modelo, serie)
5. Motivo del envío
6. Accesorios
7. Diagrama de revisión de daños (imagen para marcar a mano)
8. Imágenes de autorización/pass (si hay)
9. Contacto operativo SIC
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.staticfiles import finders
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config.paises_config import fecha_local_pais, get_pais_actual

logger = logging.getLogger('servicio_tecnico')

# Paleta idéntica a OOW / Venta mostrador.
COLOR_NAVY = colors.HexColor('#003366')
COLOR_NAVY_SUAVE = colors.HexColor('#E8EEF5')
COLOR_GRIS_ALT = colors.HexColor('#F2F2F2')
COLOR_GRIS_BORDE = colors.HexColor('#CCCCCC')
COLOR_AMARILLO_BG = colors.HexColor('#FFF2CC')
COLOR_BLANCO = colors.white
COLOR_NEGRO = colors.black

MARGEN = 15 * mm
MARGEN_INFERIOR = 20 * mm
# Alto del diagrama: ~250 pt históricos (~88 mm) para que quepa marcar a mano.
ALTO_DIAGRAMA = 88 * mm
ALTO_IMAGEN_PASS = 90 * mm

# Contacto que hoy ve el laboratorio (no sale del contexto de la orden).
CONTACTO_AGENTE = 'Alejandro García'
CONTACTO_CELULAR = '55-35-45-81-92'
CONTACTO_CORREO = 'cis_mex@sic.com.mx'


class PDFGeneratorRhitso:
    """
    Genera el PDF del formato RHITSO con estilo OOW/Venta mostrador.

    Args:
        orden: instancia OrdenServicio (o un objeto con los mismos atributos).
        imagenes_autorizacion: lista de ImagenOrden tipo autorización/pass.

    Efectos secundarios:
        Escribe un archivo en MEDIA_ROOT/temp/rhitso/. No toca la BD.
    """

    def __init__(self, orden, imagenes_autorizacion: List = None):
        """
        Args:
            orden: OrdenServicio con detalle_equipo y descripcion_rhitso.
            imagenes_autorizacion: ImagenOrden de tipo 'autorizacion'.
        """
        self.orden = orden
        # EXPLICACIÓN: si la orden no tiene DetalleEquipo, Django lanza
        # DoesNotExist; en tests usamos SimpleNamespace con None.
        try:
            self.detalle = orden.detalle_equipo
        except (ObjectDoesNotExist, AttributeError):
            self.detalle = None
        self.imagenes_autorizacion = imagenes_autorizacion or []
        self.pais_config = get_pais_actual()
        self._estilos = getSampleStyleSheet()
        self._crear_estilos()

    def generar_pdf(self) -> Dict[str, Any]:
        """
        Construye el PDF en disco (Celery y la vista de prueba leen `ruta`).

        Returns:
            dict: {success, archivo, ruta, size} o {success: False, error}.
        """
        try:
            folio = self._folio()
            empresa = self.pais_config.get(
                'empresa_nombre',
                'SIC Comercialización y Servicios de México SC',
            )
            fecha = timezone.now().strftime('%Y%m%d')
            serie_cruda = ''
            if self.detalle is not None:
                serie_cruda = getattr(self.detalle, 'numero_serie', '') or ''
            serie = (serie_cruda or folio or 'SIN_SERIE').replace(' ', '_').replace('/', '_')
            nombre_archivo = f'RHITSO_{fecha}_{serie}.pdf'

            directorio_temp = os.path.join(settings.MEDIA_ROOT, 'temp', 'rhitso')
            os.makedirs(directorio_temp, exist_ok=True)
            ruta_archivo = os.path.join(directorio_temp, nombre_archivo)

            doc = SimpleDocTemplate(
                ruta_archivo,
                pagesize=letter,
                leftMargin=MARGEN,
                rightMargin=MARGEN,
                topMargin=MARGEN,
                bottomMargin=MARGEN_INFERIOR,
                title=f'Formato RHITSO — {folio}',
                author=empresa,
                subject='Envío de equipo a RHITSO para revisión especializada',
                creator='SIGMA',
            )

            elementos: List = []
            elementos += self._construir_header()
            elementos.append(Spacer(1, 3 * mm))
            elementos += self._construir_titulo()
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._envolver_seccion(self._construir_fecha_orden())
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._envolver_seccion(self._construir_info_equipo())
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._envolver_seccion(self._construir_motivo())
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._envolver_seccion(self._construir_accesorios())
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._construir_revision_danos()
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._construir_imagenes_autorizacion()
            elementos.append(Spacer(1, 4 * mm))
            elementos += self._envolver_seccion(self._construir_contacto())

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
            logger.error('[PDF RHITSO] Error generando PDF: %s', exc, exc_info=True)
            return {'success': False, 'error': f'Error generando PDF: {exc}'}

    def _folio(self) -> str:
        """Orden visible: orden_cliente, número interno o ORD-{id}."""
        if self.detalle is not None:
            orden_cliente = getattr(self.detalle, 'orden_cliente', None) or ''
            if orden_cliente:
                return str(orden_cliente)
        interno = getattr(self.orden, 'numero_orden_interno', None) or ''
        if interno:
            return str(interno)
        return f"ORD-{getattr(self.orden, 'id', '')}"

    def _ancho_util(self) -> float:
        """Ancho de página menos márgenes izquierdo y derecho."""
        return letter[0] - (2 * MARGEN)

    # ------------------------------------------------------------------ estilos

    def _crear_estilos(self) -> None:
        """Registra ParagraphStyles reutilizados en el documento."""
        self._estilos.add(ParagraphStyle(
            'EmpresaHeaderCentro',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            leading=13,
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
            fontSize=9,
            textColor=COLOR_NEGRO,
            alignment=TA_LEFT,
            leading=12,
        ))
        self._estilos.add(ParagraphStyle(
            'AccesorioCelda',
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
            leading=11,
        ))
        self._estilos.add(ParagraphStyle(
            'Placeholder',
            fontName='Helvetica',
            fontSize=9,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
            leading=12,
        ))

    def _dibujar_pie_pagina(self, canvas, doc) -> None:
        """
        Pie corporativo en CADA hoja: folio a la izquierda, página a la derecha.

        Args:
            canvas: canvas de ReportLab de la página actual.
            doc: SimpleDocTemplate (número de página).

        Efectos secundarios:
            Dibuja sobre el canvas (línea + textos). No tapa el diagrama
            porque vive en el bottomMargin reservado.
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
        canvas.drawString(x_izq, y_pie, f'Formato RHITSO · {self._folio()}')
        canvas.drawRightString(x_der, y_pie, f'Página {doc.page}')
        canvas.restoreState()

    def _envolver_seccion(self, partes: List) -> List:
        """
        Agrupa header + contenido para que no se partan (título en una
        página y tabla en otra).
        """
        if not partes:
            return []
        return [KeepTogether(partes)]

    def _crear_header_seccion(self, titulo: str) -> Table:
        """Barra navy de sección (igual que OOW)."""
        tabla = Table(
            [[Paragraph(titulo, self._estilos['TituloFormato'])]],
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

    def _fila_dato(self, label: str, valor: str) -> list:
        return [
            Paragraph(self._esc(label), self._estilos['CeldaLabel']),
            Paragraph(self._esc(valor or 'N/A'), self._estilos['CeldaValor']),
        ]

    def _tabla_pares(self, pares: List[tuple]) -> Table:
        """Tabla 2 columnas label|valor con jerarquía visual navy."""
        data = [self._fila_dato(label, valor) for label, valor in pares]
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

    def _obtener_logo(self) -> Optional[RLImage]:
        """Carga el PNG del logo SIC desde static si existe."""
        ruta = finders.find('images/logos/logo_sic.png')
        if not ruta:
            return None
        try:
            return RLImage(ruta, width=45 * mm, height=15 * mm, kind='proportional')
        except Exception:
            return None

    def _obtener_logo_rhitso(self) -> Optional[RLImage]:
        """
        Carga el PNG circular de RHITSO (derecha del encabezado).

        EXPLICACIÓN PARA PRINCIPIANTES:
        En el formato original el logo SIC iba a la izquierda y el de
        RHITSO a la derecha. ``kind='proportional'`` evita aplastar el
        círculo. Si el archivo no está, esa celda queda vacía.
        """
        ruta = finders.find('images/logos/logo_rhitso.png')
        if not ruta:
            return None
        try:
            # ~20 mm: similar al alto visual del logo SIC, sin tapar el título.
            return RLImage(ruta, width=22 * mm, height=22 * mm, kind='proportional')
        except Exception:
            return None

    def _ruta_static(self, relativo: str) -> Optional[str]:
        """
        Busca un archivo bajo static/images/.

        Args:
            relativo: Ruta relativa, ej. ``rhitso/diagrama.png``.
        """
        return finders.find(f'images/{relativo}') or None

    # ------------------------------------------------------------------ secciones

    def _construir_header(self) -> List:
        """
        Encabezado a 3 columnas, como el formato original:

        Logo SIC | razón social centrada | Logo RHITSO
        """
        elementos: List = []
        logo_sic = self._obtener_logo()
        logo_rhitso = self._obtener_logo_rhitso()
        empresa = self.pais_config.get(
            'empresa_nombre',
            'SIC Comercialización y Servicios de México SC',
        )
        texto_centro = Paragraph(self._esc(empresa), self._estilos['EmpresaHeaderCentro'])
        fila = [[logo_sic or '', texto_centro, logo_rhitso or '']]
        ancho_logo = 50 * mm
        ancho_centro = self._ancho_util() - (2 * ancho_logo)
        tabla = Table(fila, colWidths=[ancho_logo, ancho_centro, ancho_logo])
        tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (0, 0), (0, 0), 'LEFT'),
            ('ALIGN', (1, 0), (1, 0), 'CENTER'),
            ('ALIGN', (2, 0), (2, 0), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ]))
        elementos.append(tabla)
        elementos.append(Spacer(1, 2 * mm))
        elementos.append(HRFlowable(width='100%', thickness=1, color=COLOR_GRIS_BORDE))
        return elementos

    def _construir_titulo(self) -> List:
        """Barra navy con el nombre del formato."""
        return [self._crear_header_seccion('FORMATO RHITSO')]

    def _construir_fecha_orden(self) -> List:
        """Fecha local del país + número de orden."""
        elementos = [self._crear_header_seccion('Orden de servicio'), Spacer(1, 2 * mm)]
        ahora_local = fecha_local_pais(timezone.now(), self.pais_config)
        pares = [
            ('Fecha', ahora_local.strftime('%d/%m/%Y')),
            ('Orden de servicio', self._folio()),
        ]
        elementos.append(self._tabla_pares(pares))
        return elementos

    def _construir_info_equipo(self) -> List:
        """Modelo y número de serie (mismos campos que el PDF original)."""
        elementos = [self._crear_header_seccion('Información del equipo'), Spacer(1, 2 * mm)]
        modelo = 'N/A'
        serie = 'N/A'
        if self.detalle is not None:
            modelo = getattr(self.detalle, 'modelo', None) or 'N/A'
            serie = getattr(self.detalle, 'numero_serie', None) or 'N/A'
        elementos.append(self._tabla_pares([
            ('Modelo', modelo),
            ('Número de serie', serie),
        ]))
        return elementos

    def _construir_motivo(self) -> List:
        """
        Diagnóstico / motivo del envío.

        EXPLICACIÓN: Paragraph envuelve solo. Ya no medimos líneas a mano
        ni agrandamos un rectángulo de canvas (eso era lo que tapaba
        ACCESORIOS cuando el texto era largo).
        """
        elementos = [self._crear_header_seccion('Motivo'), Spacer(1, 2 * mm)]
        texto = getattr(self.orden, 'descripcion_rhitso', None) or 'No especificado'
        cuerpo = Table(
            [[Paragraph(self._esc(texto), self._estilos['CuerpoNormal'])]],
            colWidths=[self._ancho_util()],
        )
        cuerpo.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BLANCO),
        ]))
        elementos.append(cuerpo)
        return elementos

    def _construir_accesorios(self) -> List:
        """Adaptador / Sin cargador / Otros + fila amarilla si hay serie."""
        elementos = [self._crear_header_seccion('Accesorios enviados'), Spacer(1, 2 * mm)]
        tiene_cargador = False
        serie_cargador = ''
        if self.detalle is not None:
            tiene_cargador = bool(getattr(self.detalle, 'tiene_cargador', False))
            serie_cargador = getattr(self.detalle, 'numero_serie_cargador', None) or ''

        check_adaptador = '[X] ADAPTADOR' if tiene_cargador else '[ ] ADAPTADOR'
        check_sin = '[X] SIN CARGADOR' if not tiene_cargador else '[ ] SIN CARGADOR'
        ancho_col = self._ancho_util() / 3
        fila = Table(
            [[
                Paragraph(check_adaptador, self._estilos['AccesorioCelda']),
                Paragraph(check_sin, self._estilos['AccesorioCelda']),
                Paragraph('[ ] OTROS', self._estilos['AccesorioCelda']),
            ]],
            colWidths=[ancho_col, ancho_col, ancho_col],
        )
        fila.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elementos.append(fila)

        if tiene_cargador and serie_cargador:
            # EXPLICACIÓN: el amarillo destaca el SN del cargador (igual que antes).
            destacada = Table(
                [[Paragraph(
                    self._esc(f'CARGADOR Y CABLE: {serie_cargador}'),
                    self._estilos['CeldaLabel'],
                )]],
                colWidths=[self._ancho_util()],
            )
            destacada.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), COLOR_AMARILLO_BG),
                ('BOX', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 5),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ]))
            elementos.append(destacada)
        return elementos

    def _construir_revision_danos(self) -> List:
        """
        Diagrama Laptop / AIO / PC para marcar defectos a mano.

        KeepTogether: si no cabe el encabezado + dibujo, saltan JUNTOS a
        la página siguiente. Nunca se recorta ni se tapa con el pie.
        """
        partes: List = [
            self._crear_header_seccion('Revisión de daños externos'),
            Spacer(1, 2 * mm),
        ]
        ruta = self._ruta_static('rhitso/diagrama.png')
        if ruta and os.path.exists(ruta):
            try:
                img = RLImage(
                    ruta,
                    width=self._ancho_util(),
                    height=ALTO_DIAGRAMA,
                    kind='proportional',
                )
                partes.append(img)
            except Exception as exc:
                logger.warning('[PDF RHITSO] No se pudo cargar el diagrama: %s', exc)
                partes.append(Paragraph(
                    'Diagrama de revisión física del equipo',
                    self._estilos['Placeholder'],
                ))
        else:
            partes.append(Paragraph(
                'Diagrama de revisión física del equipo',
                self._estilos['Placeholder'],
            ))
        return self._envolver_seccion(partes)

    def _resolver_ruta_imagen_orden(self, imagen) -> Optional[str]:
        """
        Busca el archivo de una ImagenOrden en disco principal o alterno.

        Args:
            imagen: ImagenOrden (o mock con atributo ``imagen``).

        Returns:
            Ruta absoluta si existe; None si no se encontró.
        """
        if not hasattr(imagen, 'imagen') or not imagen.imagen:
            return None
        try:
            from config.storage_utils import ALTERNATE_STORAGE_PATH, PRIMARY_STORAGE_PATH
            nombre_relativo = str(imagen.imagen)
            for ubicacion in (ALTERNATE_STORAGE_PATH, PRIMARY_STORAGE_PATH):
                completa = Path(ubicacion) / nombre_relativo
                if completa.exists() and completa.is_file():
                    return str(completa)
        except Exception as exc:
            logger.warning('[PDF RHITSO] Error buscando imagen de autorización: %s', exc)
        # Fallback: ImageField.path (tests / storage local de Django).
        try:
            ruta = imagen.imagen.path
            if ruta and os.path.exists(ruta):
                return ruta
        except Exception:
            return None
        return None

    def _construir_imagenes_autorizacion(self) -> List:
        """Primera imagen de autorización/pass, si existe."""
        if not self.imagenes_autorizacion:
            return []
        partes: List = [
            self._crear_header_seccion('Imágenes de autorización / contraseñas'),
            Spacer(1, 2 * mm),
        ]
        imagen = self.imagenes_autorizacion[0]
        ruta = self._resolver_ruta_imagen_orden(imagen)
        if ruta:
            try:
                partes.append(RLImage(
                    ruta,
                    width=self._ancho_util(),
                    height=ALTO_IMAGEN_PASS,
                    kind='proportional',
                ))
            except Exception as exc:
                logger.warning('[PDF RHITSO] No se pudo incrustar pass: %s', exc)
                partes.append(Paragraph(
                    'Imagen de autorización no disponible',
                    self._estilos['Placeholder'],
                ))
        else:
            partes.append(Paragraph(
                'Imagen de autorización no disponible',
                self._estilos['Placeholder'],
            ))
        return self._envolver_seccion(partes)

    def _construir_contacto(self) -> List:
        """
        Seguimiento SIC: va DESPUÉS del diagrama (flowable).

        Antes se pintaba a Y fija y tapaba los dibujos. Empresa y domicilio
        salen de get_pais_actual(); el agente es el mismo que ve RHITSO hoy.
        """
        elementos = [self._crear_header_seccion('Seguimiento SIC'), Spacer(1, 2 * mm)]
        empresa = self.pais_config.get(
            'empresa_nombre',
            'SIC Comercialización y Servicios México SC',
        )
        direccion = self.pais_config.get('empresa_direccion', '')
        pares = [
            ('Empresa', empresa),
            ('Domicilio', direccion),
            ('Agente', CONTACTO_AGENTE),
            ('Celular', CONTACTO_CELULAR),
            ('Correo', CONTACTO_CORREO),
        ]
        elementos.append(self._tabla_pares(pares))
        return elementos
