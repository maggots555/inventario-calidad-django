"""
Generador de PDF para el Concentrado Semanal CIS
=================================================

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este módulo genera un PDF en orientación HORIZONTAL (landscape) con las
3 tablas del Concentrado Semanal:

  Tabla 1 → Ingreso de Equipos en CIS
  Tabla 2 → Asignación de Equipos a Ingeniería
  Tabla 3 → Egreso de Equipos en CIS

Usa ReportLab, que es la librería más usada para PDFs en Python.
El flujo es:
  1. Crear un "buffer" (archivo en memoria)
  2. Crear el documento SimpleDocTemplate con orientación horizontal
  3. Construir lista de elementos (Paragraph, Table, Spacer)
  4. Llamar a doc.build() para generar el PDF
  5. Devolver el buffer listo para enviarse como respuesta HTTP

REFERENCIA:
  Ver pdf_diagnostico.py para un ejemplo de PDF con canvas manual.
  Este archivo usa el enfoque por "elementos" (Flowables), más sencillo
  para tablas de datos.
"""

import io
from datetime import date

# ReportLab — Librería para generar PDFs
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    HRFlowable,
)


# ===========================================================================
# CONSTANTES DE DISEÑO
# ===========================================================================

# Colores corporativos del proyecto
COLOR_AZUL = colors.HexColor('#0d6efd')       # Bootstrap primary
COLOR_AZUL_OSCURO = colors.HexColor('#0a58ca')
COLOR_INDIGO = colors.HexColor('#6610f2')     # Bootstrap indigo
COLOR_VERDE = colors.HexColor('#198754')      # Bootstrap success
COLOR_GRIS_CLARO = colors.HexColor('#f8f9fa')
COLOR_GRIS_THEAD = colors.HexColor('#e9ecef')
COLOR_AMARILLO = colors.HexColor('#fff3cd')   # Fila escalados
COLOR_AZUL_THEAD_ING = colors.HexColor('#cfe2ff')
COLOR_INDIGO_THEAD = colors.HexColor('#e0cffc')
COLOR_VERDE_THEAD = colors.HexColor('#d1e7dd')
COLOR_TOTAL_BG = colors.HexColor('#f0f4ff')
COLOR_TEXTO_GRIS = colors.HexColor('#6c757d')

# Días de la semana (replicados aquí para no importar models)
DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
TIPOS_EQUIPO = ['LENOVO', 'DELL', 'OOW', 'MIS DELL', 'MIS LENOVO']
SITIOS = ['DROP OFF', 'SATELITE']

# Ancho de página horizontal letter en mm
ANCHO_PAGINA = landscape(letter)[0]   # ~279 mm
ALTO_PAGINA = landscape(letter)[1]    # ~216 mm
MARGEN = 12 * mm


# ===========================================================================
# ESTILOS DE PÁRRAFO
# ===========================================================================

def _crear_estilos():
    """
    Crea y retorna el diccionario de estilos de párrafo para el PDF.

    EXPLICACIÓN:
    En ReportLab, los estilos de párrafo definen la fuente, tamaño,
    color y alineación del texto. Es como las clases CSS para el PDF.
    """
    estilos = getSampleStyleSheet()

    # Título principal del documento
    titulo_estilo = ParagraphStyle(
        'TituloPrincipal',
        parent=estilos['Heading1'],
        fontSize=14,
        fontName='Helvetica-Bold',
        textColor=colors.HexColor('#1e3a5f'),
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )

    # Subtítulo (rango de fechas)
    subtitulo_estilo = ParagraphStyle(
        'Subtitulo',
        parent=estilos['Normal'],
        fontSize=9,
        fontName='Helvetica',
        textColor=COLOR_TEXTO_GRIS,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )

    # Título de sección (Ingreso, Asignación, Egreso)
    seccion_estilo = ParagraphStyle(
        'TituloSeccion',
        parent=estilos['Heading2'],
        fontSize=11,
        fontName='Helvetica-Bold',
        textColor=colors.white,
        alignment=TA_LEFT,
        spaceBefore=4 * mm,
        spaceAfter=1 * mm,
    )

    # Texto de resumen (Carry-In / MIS)
    resumen_estilo = ParagraphStyle(
        'Resumen',
        parent=estilos['Normal'],
        fontSize=9,
        fontName='Helvetica',
        textColor=colors.HexColor('#212529'),
        alignment=TA_LEFT,
        spaceAfter=2 * mm,
    )

    return {
        'titulo': titulo_estilo,
        'subtitulo': subtitulo_estilo,
        'seccion': seccion_estilo,
        'resumen': resumen_estilo,
    }


# ===========================================================================
# CONSTRUCCIÓN DE TABLAS
# ===========================================================================

def _tabla_ingreso_egreso(datos, totales, color_header, color_thead):
    """
    Construye la tabla de Ingreso o Egreso como objeto ReportLab Table.

    EXPLICACIÓN:
    ReportLab representa las tablas como listas de listas (filas × columnas).
    La primera lista es la fila de encabezados, el resto son datos.
    Luego se aplica un TableStyle con comandos de estilo.

    Estructura de columnas:
      SITIO | EQUIPO | Lun | Mar | Mié | Jue | Vie | TOTAL | PROM

    Args:
        datos (dict): {sitio: {tipo: {dia: N, total: N, promedio: N}}}
        totales (dict): {dia: N, total: N, promedio: N}
        color_header (colors.Color): Color del encabezado de sección (no se usa directamente aquí)
        color_thead (colors.Color): Color de la fila de nombres de columnas

    Returns:
        Table: Objeto Table de ReportLab listo para agregar al documento
    """
    # Fila de encabezados
    encabezados = ['SITIO', 'EQUIPO'] + [d[:3].upper() for d in DIAS_SEMANA] + ['TOTAL', 'PROM']
    filas = [encabezados]

    # Comandos de estilo para la tabla
    style_cmds = [
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), color_thead),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#333333')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Bordes generales
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
        # Columna SITIO: fondo gris claro
        ('BACKGROUND', (0, 1), (0, -2), COLOR_GRIS_CLARO),
        ('FONTNAME', (0, 1), (0, -2), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (0, -2), 8),
        ('ALIGN', (0, 1), (0, -2), 'CENTER'),
        # Columna EQUIPO
        ('FONTNAME', (1, 1), (1, -2), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 1), (1, -2), 8),
        ('ALIGN', (1, 1), (1, -2), 'LEFT'),
        # Columnas numéricas
        ('FONTSIZE', (2, 1), (-1, -2), 8),
        ('ALIGN', (2, 1), (-1, -2), 'CENTER'),
        # Columna TOTAL: azul
        ('BACKGROUND', (-2, 1), (-2, -2), COLOR_TOTAL_BG),
        ('TEXTCOLOR', (-2, 1), (-2, -2), COLOR_AZUL),
        ('FONTNAME', (-2, 1), (-2, -2), 'Helvetica-Bold'),
        # Columna PROMEDIO: gris
        ('TEXTCOLOR', (-1, 1), (-1, -2), COLOR_TEXTO_GRIS),
    ]

    # Acumular filas de datos y rastrear rangos de merge
    fila_actual = 1  # Fila 0 = encabezados

    for sitio in SITIOS:
        fila_inicio_sitio = fila_actual

        for tipo in TIPOS_EQUIPO:
            tipo_data = datos[sitio][tipo]
            fila = [
                sitio,           # Se mergea por sitio
                tipo,
            ]
            for dia in DIAS_SEMANA:
                fila.append(tipo_data.get(dia, 0))
            fila.append(tipo_data.get('total', 0))
            fila.append(tipo_data.get('promedio', 0))
            filas.append(fila)
            fila_actual += 1

        # Merge de celdas SITIO para las filas de este grupo
        if len(TIPOS_EQUIPO) > 1:
            style_cmds.append((
                'SPAN', (0, fila_inicio_sitio), (0, fila_actual - 1)
            ))

    # Fila de totales
    fila_totales = ['TOTALES', '']
    for dia in DIAS_SEMANA:
        fila_totales.append(totales.get(dia, 0))
    fila_totales.append(totales.get('total', 0))
    fila_totales.append(totales.get('promedio', 0))
    filas.append(fila_totales)

    # Estilo de fila de totales
    idx_total = len(filas) - 1
    style_cmds += [
        ('BACKGROUND', (0, idx_total), (-1, idx_total), COLOR_GRIS_THEAD),
        ('FONTNAME', (0, idx_total), (-1, idx_total), 'Helvetica-Bold'),
        ('FONTSIZE', (0, idx_total), (-1, idx_total), 8),
        ('ALIGN', (0, idx_total), (-1, idx_total), 'CENTER'),
        ('SPAN', (0, idx_total), (1, idx_total)),
        ('LINEABOVE', (0, idx_total), (-1, idx_total), 1.0, colors.HexColor('#adb5bd')),
    ]

    # Anchos de columna adaptados al ancho de página horizontal letter
    ancho_util = ANCHO_PAGINA - 2 * MARGEN  # ~255 mm
    col_widths = [
        1.5 * cm,  # SITIO
        2.5 * cm,  # EQUIPO
        1.6 * cm,  # Lun
        1.6 * cm,  # Mar
        1.7 * cm,  # Mié
        1.6 * cm,  # Jue
        1.6 * cm,  # Vie
        1.8 * cm,  # TOTAL
        1.8 * cm,  # PROM
    ]

    tabla = Table(filas, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(TableStyle(style_cmds))
    return tabla


def _tabla_asignacion(asignacion, total_asignados):
    """
    Construye la tabla de Asignación a Ingeniería.

    Estructura:
      INGENIERO | Lun | Mar | Mié | Jue | Vie | TOTAL

    Args:
        asignacion (list): Lista de dicts {nombre, Lunes, ..., total}
        total_asignados (int): Total general de equipos asignados

    Returns:
        Table: Objeto Table de ReportLab
    """
    encabezados = ['INGENIERO'] + [d[:3].upper() for d in DIAS_SEMANA] + ['TOTAL']
    filas = [encabezados]

    style_cmds = [
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_INDIGO_THEAD),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#3d0a91')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Bordes
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8f9fa')]),
        # Columna ingeniero
        ('FONTNAME', (0, 1), (0, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (0, -2), 8),
        ('ALIGN', (0, 1), (0, -2), 'LEFT'),
        # Columnas numéricas
        ('FONTSIZE', (1, 1), (-1, -2), 8),
        ('ALIGN', (1, 1), (-1, -2), 'CENTER'),
        # Total
        ('BACKGROUND', (-1, 1), (-1, -2), COLOR_TOTAL_BG),
        ('TEXTCOLOR', (-1, 1), (-1, -2), COLOR_AZUL),
        ('FONTNAME', (-1, 1), (-1, -2), 'Helvetica-Bold'),
    ]

    fila_idx = 1
    for fila_ing in asignacion:
        es_escalados = fila_ing.get('nombre') == 'Escalados / Packing'
        fila = [fila_ing.get('nombre', '')]
        for dia in DIAS_SEMANA:
            fila.append(fila_ing.get(dia, 0))
        fila.append(fila_ing.get('total', 0))
        filas.append(fila)

        if es_escalados:
            style_cmds += [
                ('BACKGROUND', (0, fila_idx), (-1, fila_idx), COLOR_AMARILLO),
                ('TEXTCOLOR', (0, fila_idx), (-1, fila_idx), colors.HexColor('#664d03')),
                ('FONTNAME', (0, fila_idx), (-1, fila_idx), 'Helvetica-Oblique'),
            ]
        fila_idx += 1

    # Fila total
    fila_total = ['TOTAL EQUIPOS INGRESADOS'] + [''] * len(DIAS_SEMANA) + [total_asignados]
    filas.append(fila_total)
    idx_total = len(filas) - 1
    style_cmds += [
        ('BACKGROUND', (0, idx_total), (-1, idx_total), COLOR_GRIS_THEAD),
        ('FONTNAME', (0, idx_total), (-1, idx_total), 'Helvetica-Bold'),
        ('FONTSIZE', (0, idx_total), (-1, idx_total), 8),
        ('ALIGN', (0, idx_total), (-1, idx_total), 'CENTER'),
        ('SPAN', (0, idx_total), (-2, idx_total)),
        ('LINEABOVE', (0, idx_total), (-1, idx_total), 1.0, colors.HexColor('#adb5bd')),
    ]

    col_widths = [5.5 * cm] + [1.6 * cm] * len(DIAS_SEMANA) + [1.8 * cm]
    tabla = Table(filas, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(TableStyle(style_cmds))
    return tabla


# ===========================================================================
# FUNCIÓN PRINCIPAL EXPORTADA
# ===========================================================================

def generar_pdf_concentrado(datos):
    """
    Genera el PDF del Concentrado Semanal en orientación horizontal.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función recibe el diccionario 'datos' tal como lo devuelve
    obtener_concentrado_semanal() y construye un PDF con las 3 tablas
    del reporte en orientación horizontal (landscape) usando ReportLab.

    El PDF se guarda en un 'buffer' (archivo en memoria) que luego
    se envía directamente al navegador para descargar, sin guardar
    ningún archivo en el disco del servidor.

    Args:
        datos (dict): Resultado de obtener_concentrado_semanal().
            Claves esperadas:
              - ingreso, egreso, asignacion
              - totales_ingreso, totales_egreso
              - total_asignados, carry_in_dropoff, carry_in_sic, mail_in_service
              - numero_semana, año, lunes, viernes

    Returns:
        io.BytesIO: Buffer con el contenido del PDF listo para enviar.

    Ejemplo de uso en la vista:
        pdf_buffer = generar_pdf_concentrado(datos)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="concentrado.pdf"'
        return response
    """
    buffer = io.BytesIO()

    # Crear documento en orientación horizontal letter
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(letter),
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=MARGEN,
        bottomMargin=MARGEN,
        title='Concentrado Semanal CIS',
        author='Sistema CIS',
    )

    estilos = _crear_estilos()
    elementos = []

    # ---- Título principal ----
    num_semana = datos.get('numero_semana', '?')
    año = datos.get('año', '?')
    lunes = datos.get('lunes')
    viernes = datos.get('viernes')

    titulo_texto = f'CONCENTRADO SEMANAL CIS — Semana {num_semana} de {año}'
    elementos.append(Paragraph(titulo_texto, estilos['titulo']))

    # Subtítulo con rango de fechas
    if lunes and viernes:
        fecha_str = f'{lunes.strftime("%d/%m/%Y")} — {viernes.strftime("%d/%m/%Y")}'
        elementos.append(Paragraph(fecha_str, estilos['subtitulo']))

    elementos.append(Spacer(1, 3 * mm))

    # ================================================================
    # TABLA 1: INGRESO DE EQUIPOS EN CIS
    # ================================================================
    # Barra de color azul como "header" de sección
    elementos.append(
        HRFlowable(
            width='100%',
            thickness=14,
            color=COLOR_AZUL,
            spaceAfter=1,
        )
    )
    elementos.append(
        Paragraph(
            '<font color="white"><b>  INGRESO DE EQUIPOS EN CIS</b></font>',
            ParagraphStyle(
                'HeaderIngreso',
                fontSize=10,
                fontName='Helvetica-Bold',
                textColor=colors.white,
                backColor=COLOR_AZUL,
                alignment=TA_LEFT,
                leading=12,
                leftIndent=4,
                spaceBefore=-14,
                spaceAfter=2,
            )
        )
    )

    tabla_ingreso = _tabla_ingreso_egreso(
        datos=datos['ingreso'],
        totales=datos['totales_ingreso'],
        color_header=COLOR_AZUL,
        color_thead=COLOR_AZUL_THEAD_ING,
    )
    elementos.append(tabla_ingreso)

    # Resumen Carry-In / MIS
    carry_drop = datos.get('carry_in_dropoff', 0)
    carry_sic = datos.get('carry_in_sic', 0)
    mail_in = datos.get('mail_in_service', 0)
    resumen_html = (
        f'<b>Carry In – Drop Off:</b> {carry_drop} &nbsp;&nbsp;&nbsp; '
        f'<b>Carry In – SIC (Satélite):</b> {carry_sic} &nbsp;&nbsp;&nbsp; '
        f'<b>Mail In Service (MIS):</b> {mail_in}'
    )
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(Paragraph(resumen_html, estilos['resumen']))
    elementos.append(Spacer(1, 4 * mm))

    # ================================================================
    # TABLA 2: ASIGNACIÓN A INGENIERÍA
    # ================================================================
    elementos.append(
        HRFlowable(
            width='100%',
            thickness=14,
            color=COLOR_INDIGO,
            spaceAfter=1,
        )
    )
    elementos.append(
        Paragraph(
            '<font color="white"><b>  ASIGNACIÓN DE EQUIPOS A INGENIERÍA</b></font>',
            ParagraphStyle(
                'HeaderAsignacion',
                fontSize=10,
                fontName='Helvetica-Bold',
                textColor=colors.white,
                backColor=COLOR_INDIGO,
                alignment=TA_LEFT,
                leading=12,
                leftIndent=4,
                spaceBefore=-14,
                spaceAfter=2,
            )
        )
    )

    tabla_asig = _tabla_asignacion(
        asignacion=datos.get('asignacion', []),
        total_asignados=datos.get('total_asignados', 0),
    )
    elementos.append(tabla_asig)
    elementos.append(Spacer(1, 4 * mm))

    # ================================================================
    # TABLA 3: EGRESO DE EQUIPOS EN CIS
    # ================================================================
    elementos.append(
        HRFlowable(
            width='100%',
            thickness=14,
            color=COLOR_VERDE,
            spaceAfter=1,
        )
    )
    elementos.append(
        Paragraph(
            '<font color="white"><b>  EGRESO DE EQUIPOS EN CIS</b></font>',
            ParagraphStyle(
                'HeaderEgreso',
                fontSize=10,
                fontName='Helvetica-Bold',
                textColor=colors.white,
                backColor=COLOR_VERDE,
                alignment=TA_LEFT,
                leading=12,
                leftIndent=4,
                spaceBefore=-14,
                spaceAfter=2,
            )
        )
    )

    tabla_egreso = _tabla_ingreso_egreso(
        datos=datos['egreso'],
        totales=datos['totales_egreso'],
        color_header=COLOR_VERDE,
        color_thead=COLOR_VERDE_THEAD,
    )
    elementos.append(tabla_egreso)

    # ---- Footer con fecha de generación ----
    elementos.append(Spacer(1, 4 * mm))
    from datetime import datetime
    fecha_gen = datetime.now().strftime('%d/%m/%Y %H:%M')
    elementos.append(
        Paragraph(
            f'Generado el {fecha_gen} — Sistema de Gestión CIS',
            ParagraphStyle(
                'Footer',
                fontSize=7,
                fontName='Helvetica',
                textColor=COLOR_TEXTO_GRIS,
                alignment=TA_RIGHT,
            )
        )
    )

    # ---- Construir el PDF ----
    doc.build(elementos)

    buffer.seek(0)
    return buffer
