"""
Generador de PDF — Reporte Ejecutivo de Encuestas de Satisfacción
=================================================================

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este módulo genera un PDF en orientación vertical (portrait) con el
reporte ejecutivo completo del Panel de Encuestas de Satisfacción.

Secciones del PDF:
  1. Header corporativo — título, fecha de generación y período filtrado
  2. KPIs Principales — 6 tarjetas con métricas clave
  3. Sub-métricas — Calificación atención, tiempo y tasa de recomendación
  4. Gráfico de Tendencia Semanal — generado con matplotlib
  5. Distribución NPS — gráfico de pie con matplotlib
  6. Ranking por Responsable — tabla coloreada con posiciones
  7. Comentarios Recientes — lista de comentarios de clientes

Librerías utilizadas:
  - ReportLab: estructura del documento, tablas, texto
  - matplotlib: gráficas (line chart y pie chart) incrustadas como imágenes

Patrón de uso:
  pdf_buffer = generar_pdf_reporte_encuestas(datos)
  response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
  response['Content-Disposition'] = 'attachment; filename="reporte.pdf"'
  return response
"""

import io
from datetime import datetime

# Matplotlib en modo no interactivo (CRÍTICO para servidores: sin pantalla)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.gridspec import GridSpec

# ReportLab — estructura del documento
from reportlab.lib.pagesizes import letter
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
    Image,
    KeepTogether,
)


# ===========================================================================
# CONSTANTES DE DISEÑO — Paleta corporativa SIGMA
# ===========================================================================

# Azul principal del proyecto (#1f6391)
COLOR_SIGMA_AZUL       = colors.HexColor('#1f6391')
COLOR_SIGMA_AZUL_DARK  = colors.HexColor('#164f74')
COLOR_SIGMA_AZUL_LIGHT = colors.HexColor('#d0e8f5')

# Colores semánticos
COLOR_VERDE     = colors.HexColor('#198754')
COLOR_VERDE_BG  = colors.HexColor('#d1e7dd')
COLOR_ROJO      = colors.HexColor('#dc3545')
COLOR_ROJO_BG   = colors.HexColor('#f8d7da')
COLOR_AMBAR     = colors.HexColor('#fd7e14')
COLOR_AMBAR_BG  = colors.HexColor('#fff3cd')
COLOR_PURPURA   = colors.HexColor('#6f42c1')
COLOR_PURPURA_BG = colors.HexColor('#e8d8f5')
COLOR_DORADO    = colors.HexColor('#ffc107')
COLOR_DORADO_BG = colors.HexColor('#fff9db')

# Neutrales
COLOR_GRIS_CLARO  = colors.HexColor('#f8f9fa')
COLOR_GRIS_THEAD  = colors.HexColor('#e9ecef')
COLOR_GRIS_BORDE  = colors.HexColor('#dee2e6')
COLOR_TEXTO_GRIS  = colors.HexColor('#6c757d')
COLOR_TEXTO_DARK  = colors.HexColor('#212529')
COLOR_BLANCO      = colors.white

# Colores matplotlib (hex strings)
MPL_AZUL     = '#1f6391'
MPL_VERDE    = '#198754'
MPL_AMBAR    = '#fd7e14'
MPL_PURPURA  = '#6f42c1'
MPL_ROJO     = '#dc3545'
MPL_GRIS     = '#adb5bd'
MPL_AZUL_LT  = '#cce5f6'
MPL_VERDE_LT = '#d1e7dd'
MPL_ROJO_LT  = '#f8d7da'

# Dimensiones de página
ANCHO_PAGINA = letter[0]    # 612 pt ≈ 215.9 mm
ALTO_PAGINA  = letter[1]    # 792 pt ≈ 279.4 mm
MARGEN       = 15 * mm


# ===========================================================================
# ESTILOS DE PÁRRAFO
# ===========================================================================

def _crear_estilos():
    """
    Crea y retorna el diccionario de estilos de párrafo para el PDF.

    EXPLICACIÓN:
    Los estilos de ReportLab son como clases CSS — definen fuente,
    tamaño, color y alineación del texto. Se crean una sola vez y
    se reutilizan en todo el documento para consistencia visual.
    """
    estilos = getSampleStyleSheet()

    # ---- Título del documento ----
    titulo = ParagraphStyle(
        'TituloReporte',
        parent=estilos['Heading1'],
        fontSize=18,
        fontName='Helvetica-Bold',
        textColor=COLOR_BLANCO,
        alignment=TA_LEFT,
        spaceAfter=1 * mm,
        leading=22,
    )

    # ---- Subtítulo / descripción del header ----
    subtitulo = ParagraphStyle(
        'SubtituloReporte',
        parent=estilos['Normal'],
        fontSize=10,
        fontName='Helvetica',
        textColor=colors.HexColor('#cce5f6'),
        alignment=TA_LEFT,
        spaceAfter=0,
    )

    # ---- Etiqueta info (a la derecha del header) ----
    info_header = ParagraphStyle(
        'InfoHeader',
        parent=estilos['Normal'],
        fontSize=8,
        fontName='Helvetica',
        textColor=colors.HexColor('#cce5f6'),
        alignment=TA_RIGHT,
        leading=11,
    )

    # ---- Título de sección ----
    seccion = ParagraphStyle(
        'TituloSeccion',
        parent=estilos['Heading2'],
        fontSize=10,
        fontName='Helvetica-Bold',
        textColor=COLOR_BLANCO,
        alignment=TA_LEFT,
        leading=12,
        leftIndent=4,
        spaceBefore=-14,
        spaceAfter=2,
    )

    # ---- Valor grande en KPI card ----
    kpi_valor = ParagraphStyle(
        'KpiValor',
        parent=estilos['Normal'],
        fontSize=22,
        fontName='Helvetica-Bold',
        textColor=COLOR_TEXTO_DARK,
        alignment=TA_CENTER,
        leading=26,
        spaceAfter=0,
    )

    # ---- Etiqueta pequeña de KPI ----
    kpi_label = ParagraphStyle(
        'KpiLabel',
        parent=estilos['Normal'],
        fontSize=7,
        fontName='Helvetica',
        textColor=COLOR_TEXTO_GRIS,
        alignment=TA_CENTER,
        leading=9,
        spaceAfter=0,
    )

    # ---- Sub-valor (porcentaje debajo del KPI) ----
    kpi_sub = ParagraphStyle(
        'KpiSub',
        parent=estilos['Normal'],
        fontSize=8,
        fontName='Helvetica',
        textColor=COLOR_TEXTO_GRIS,
        alignment=TA_CENTER,
        leading=10,
        spaceAfter=0,
    )

    # ---- Texto normal ----
    normal = ParagraphStyle(
        'NormalEncuestas',
        parent=estilos['Normal'],
        fontSize=8,
        fontName='Helvetica',
        textColor=COLOR_TEXTO_DARK,
        alignment=TA_LEFT,
        leading=11,
    )

    # ---- Texto centrado ----
    centrado = ParagraphStyle(
        'CentradoEncuestas',
        parent=estilos['Normal'],
        fontSize=8,
        fontName='Helvetica',
        textColor=COLOR_TEXTO_DARK,
        alignment=TA_CENTER,
        leading=11,
    )

    # ---- Texto de comentario ----
    comentario = ParagraphStyle(
        'TextoComentario',
        parent=estilos['Normal'],
        fontSize=8,
        fontName='Helvetica-Oblique',
        textColor=colors.HexColor('#495057'),
        alignment=TA_LEFT,
        leading=11,
        leftIndent=4,
        rightIndent=4,
        spaceAfter=2,
    )

    # ---- Footer ----
    footer = ParagraphStyle(
        'FooterEncuestas',
        parent=estilos['Normal'],
        fontSize=7,
        fontName='Helvetica',
        textColor=COLOR_TEXTO_GRIS,
        alignment=TA_RIGHT,
        leading=9,
    )

    # ---- Texto bold pequeño ----
    bold_small = ParagraphStyle(
        'BoldSmall',
        parent=estilos['Normal'],
        fontSize=8,
        fontName='Helvetica-Bold',
        textColor=COLOR_TEXTO_DARK,
        alignment=TA_LEFT,
        leading=11,
    )

    return {
        'titulo': titulo,
        'subtitulo': subtitulo,
        'info_header': info_header,
        'seccion': seccion,
        'kpi_valor': kpi_valor,
        'kpi_label': kpi_label,
        'kpi_sub': kpi_sub,
        'normal': normal,
        'centrado': centrado,
        'comentario': comentario,
        'footer': footer,
        'bold_small': bold_small,
    }


# ===========================================================================
# GRÁFICOS CON MATPLOTLIB
# ===========================================================================

def _grafico_tendencia(tendencia: dict, ancho_pt: float, alto_pt: float) -> Image:
    """
    Genera el gráfico de barras agrupadas de Tendencia Semanal con matplotlib.

    EXPLICACIÓN:
    Se crea un gráfico de barras agrupadas (enviadas vs respondidas) con una
    línea secundaria para la calificación promedio. El gráfico se guarda en
    un buffer de memoria (BytesIO) y se convierte a imagen ReportLab.

    Args:
        tendencia (dict): {'labels': [...], 'datasets': {...}}
        ancho_pt (float): Ancho en puntos ReportLab
        alto_pt (float): Alto en puntos ReportLab

    Returns:
        Image: Objeto Image de ReportLab listo para insertar en el PDF
    """
    labels   = tendencia.get('labels', [])
    datasets = tendencia.get('datasets', {})

    enviadas    = datasets.get('total_enviadas', [])
    respondidas = datasets.get('total_respondidas', [])
    calificacion = datasets.get('calificacion_promedio', [])

    # Convertir pt → pulgadas para matplotlib (1 pt = 1/72 in)
    ancho_in = ancho_pt / 72.0
    alto_in  = alto_pt / 72.0

    fig, ax1 = plt.subplots(figsize=(ancho_in, alto_in), dpi=120)
    fig.patch.set_facecolor('#fafafa')
    ax1.set_facecolor('#fafafa')

    if not labels:
        # Sin datos: mensaje centrado
        ax1.text(0.5, 0.5, 'Sin datos para el período seleccionado',
                 ha='center', va='center', fontsize=9, color=MPL_GRIS,
                 transform=ax1.transAxes)
        ax1.set_axis_off()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', facecolor='#fafafa')
        plt.close(fig)
        buf.seek(0)
        return Image(buf, width=ancho_pt, height=alto_pt)

    x = range(len(labels))
    barra_ancho = 0.35

    # Barras enviadas y respondidas
    barras_env = ax1.bar(
        [i - barra_ancho / 2 for i in x], enviadas,
        barra_ancho, label='Enviadas', color=MPL_AZUL_LT, edgecolor=MPL_AZUL,
        linewidth=0.6, zorder=2,
    )
    barras_resp = ax1.bar(
        [i + barra_ancho / 2 for i in x], respondidas,
        barra_ancho, label='Respondidas', color=MPL_VERDE_LT, edgecolor=MPL_VERDE,
        linewidth=0.6, zorder=2,
    )

    ax1.set_xticks(list(x))
    ax1.set_xticklabels(labels, rotation=35, ha='right', fontsize=7)
    ax1.set_ylabel('Cantidad de Encuestas', fontsize=8, color='#212529')
    ax1.tick_params(axis='y', labelsize=7)
    ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f'{int(v)}'))
    ax1.grid(axis='y', linestyle='--', alpha=0.5, color='#dee2e6', zorder=1)
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # Eje secundario — Calificación promedio
    if any(c > 0 for c in calificacion):
        ax2 = ax1.twinx()
        ax2.plot(
            list(x), calificacion,
            color=MPL_AMBAR, marker='o', linewidth=1.8,
            markersize=4, label='Calificación Prom.', zorder=3,
        )
        ax2.set_ylim(0, 5.5)
        ax2.set_ylabel('Calificación Promedio (0-5)', fontsize=8, color=MPL_AMBAR)
        ax2.tick_params(axis='y', labelsize=7, labelcolor=MPL_AMBAR)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_color(MPL_AMBAR)
        # Leyenda combinada
        handles = [barras_env, barras_resp,
                   mpatches.Patch(color=MPL_AMBAR, label='Calificación Prom.')]
        ax1.legend(handles=handles, loc='upper left', fontsize=7, framealpha=0.8)
    else:
        ax1.legend(loc='upper left', fontsize=7, framealpha=0.8)

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='#fafafa', dpi=120)
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=ancho_pt, height=alto_pt)


def _grafico_nps_pie(nps_dist: dict, ancho_pt: float, alto_pt: float) -> Image:
    """
    Genera el gráfico de pie (dona) de distribución NPS con matplotlib.

    EXPLICACIÓN:
    Los tres segmentos del NPS son:
      - Promotores (NPS 9-10): Clientes muy satisfechos
      - Pasivos   (NPS 7-8):  Clientes satisfechos pero no entusiastas
      - Detractores (NPS 0-6): Clientes insatisfechos

    El NPS Score final = % Promotores - % Detractores

    Args:
        nps_dist (dict): {'promotores': N, 'pasivos': N, 'detractores': N, 'nps_score': N}
        ancho_pt, alto_pt: Dimensiones en puntos

    Returns:
        Image: Objeto Image de ReportLab
    """
    promotores  = nps_dist.get('promotores', 0)
    pasivos     = nps_dist.get('pasivos', 0)
    detractores = nps_dist.get('detractores', 0)
    nps_score   = nps_dist.get('nps_score', 0)
    total       = promotores + pasivos + detractores

    ancho_in = ancho_pt / 72.0
    alto_in  = alto_pt / 72.0

    fig, ax = plt.subplots(figsize=(ancho_in, alto_in), dpi=120)
    fig.patch.set_facecolor('#fafafa')
    ax.set_facecolor('#fafafa')

    if total == 0:
        ax.text(0.5, 0.5, 'Sin respuestas\ncon NPS registrado',
                ha='center', va='center', fontsize=9, color=MPL_GRIS,
                transform=ax.transAxes, multialignment='center')
        ax.set_axis_off()
    else:
        valores = [promotores, pasivos, detractores]
        labels_nps = [
            f'Promotores\n{promotores} ({round(promotores/total*100, 1)}%)',
            f'Pasivos\n{pasivos} ({round(pasivos/total*100, 1)}%)',
            f'Detractores\n{detractores} ({round(detractores/total*100, 1)}%)',
        ]
        colores_nps = [MPL_VERDE, MPL_AZUL, MPL_ROJO]
        explode = (0.04, 0.01, 0.04)

        wedges, texts = ax.pie(
            valores,
            labels=None,
            colors=colores_nps,
            explode=explode,
            startangle=90,
            wedgeprops=dict(width=0.58, edgecolor='white', linewidth=2),
            autopct=None,
        )

        # Texto central — NPS Score
        color_score = MPL_VERDE if nps_score >= 0 else MPL_ROJO
        ax.text(0, 0.1, f'{nps_score:+.0f}',
                ha='center', va='center', fontsize=20, fontweight='bold',
                color=color_score, transform=ax.transAxes)
        ax.text(0, -0.05, 'NPS Score',
                ha='center', va='center', fontsize=7, color=MPL_GRIS,
                transform=ax.transAxes)

        # Leyenda lateral
        ax.legend(
            wedges, labels_nps,
            loc='lower center',
            bbox_to_anchor=(0.5, -0.15),
            fontsize=7,
            ncol=1,
            framealpha=0.8,
            handlelength=1.2,
        )

    plt.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='#fafafa', dpi=120)
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=ancho_pt, height=alto_pt)


def _grafico_ranking_barras(responsables: list, ancho_pt: float, alto_pt: float) -> Image:
    """
    Genera un gráfico de barras horizontales con la calificación promedio
    de cada responsable de seguimiento.

    Args:
        responsables (list): Lista de dicts con 'nombre', 'calificacion_promedio'
        ancho_pt, alto_pt: Dimensiones en puntos

    Returns:
        Image: Objeto Image de ReportLab
    """
    if not responsables:
        ancho_in = ancho_pt / 72.0
        alto_in  = alto_pt / 72.0
        fig, ax = plt.subplots(figsize=(ancho_in, alto_in), dpi=120)
        fig.patch.set_facecolor('#fafafa')
        ax.text(0.5, 0.5, 'Sin datos de responsables',
                ha='center', va='center', fontsize=9, color=MPL_GRIS,
                transform=ax.transAxes)
        ax.set_axis_off()
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', facecolor='#fafafa', dpi=120)
        plt.close(fig)
        buf.seek(0)
        return Image(buf, width=ancho_pt, height=alto_pt)

    # Ordenar por calificación descendente, tomar top 10
    datos_sorted = sorted(responsables, key=lambda r: r.get('calificacion_promedio', 0), reverse=True)[:10]
    nombres = [r.get('nombre', '').split()[0] for r in datos_sorted]  # Solo primer nombre
    calificaciones = [r.get('calificacion_promedio', 0) for r in datos_sorted]

    # Altura dinámica según cantidad de responsables
    n = len(datos_sorted)
    alto_in  = max(alto_pt / 72.0, n * 0.4 + 0.5)
    ancho_in = ancho_pt / 72.0

    fig, ax = plt.subplots(figsize=(ancho_in, alto_in), dpi=120)
    fig.patch.set_facecolor('#fafafa')
    ax.set_facecolor('#fafafa')

    y_pos = range(n - 1, -1, -1)  # Invertido para mostrar el mejor arriba
    barras = ax.barh(
        list(y_pos), calificaciones,
        color=[MPL_VERDE if c >= 4.0 else (MPL_AMBAR if c >= 3.0 else MPL_ROJO) for c in calificaciones],
        edgecolor='white', linewidth=0.5, height=0.55,
    )

    # Etiquetas de valor al final de cada barra
    for i, (barra, val) in enumerate(zip(barras, calificaciones)):
        ax.text(val + 0.05, barra.get_y() + barra.get_height() / 2,
                f'{val:.1f}', va='center', ha='left', fontsize=7.5,
                fontweight='bold', color='#212529')

    ax.set_yticks(list(y_pos))
    ax.set_yticklabels(nombres, fontsize=7.5)
    ax.set_xlim(0, 5.5)
    ax.set_xlabel('Calificación Promedio (0-5)', fontsize=8)
    ax.axvline(x=4.0, color=MPL_GRIS, linestyle='--', alpha=0.6, linewidth=1)
    ax.text(4.0, -0.6, 'Meta: 4.0', fontsize=6.5, color=MPL_GRIS, ha='center')
    ax.grid(axis='x', linestyle='--', alpha=0.4, color='#dee2e6')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout(pad=0.5)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', facecolor='#fafafa', dpi=120)
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=ancho_pt, height=alto_pt)


# ===========================================================================
# SECCIONES DEL PDF
# ===========================================================================

def _banner_seccion(texto: str, color_bg: colors.Color) -> list:
    """
    Genera un banner de sección con fondo de color usando una Tabla de una
    sola celda. Este enfoque es más robusto que el truco HRFlowable+spaceBefore
    negativo, especialmente en orientación portrait.

    EXPLICACIÓN:
    Una Table de 1 fila × 1 columna con fondo de color y padding controlado
    produce un resultado perfectamente alineado sin depender de offsets.
    """
    ancho_util = ANCHO_PAGINA - 2 * MARGEN

    banner_tabla = Table(
        [[Paragraph(
            f'<font color="white"><b>{texto}</b></font>',
            ParagraphStyle(
                f'BannerTxt_{hash(texto) % 9999}',
                fontSize=10,
                fontName='Helvetica-Bold',
                textColor=colors.white,
                alignment=TA_LEFT,
                leading=13,
            )
        )]],
        colWidths=[ancho_util],
    )
    banner_tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), color_bg),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))

    return [banner_tabla, Spacer(1, 3 * mm)]


def _tabla_kpis(kpis: dict, estilos: dict) -> Table:
    """
    Construye la tabla visual de 6 KPI cards en 2 filas × 3 columnas.

    EXPLICACIÓN:
    Cada "card" es una celda de la tabla con fondo de color, valor grande
    y etiqueta pequeña. Esto simula el diseño de tarjetas del dashboard web.

    Layout:
      [Enviadas]   [Respondidas]   [Pendientes]
      [Expiradas]  [NPS Score]     [Calificación]
    """
    def _celda_kpi(valor, label, sub='', color_fondo=COLOR_GRIS_CLARO,
                   color_valor=COLOR_TEXTO_DARK):
        """Construye el contenido de una celda KPI como lista de Paragraphs."""
        contenido = [
            Paragraph(str(valor), ParagraphStyle(
                'KV', fontSize=22, fontName='Helvetica-Bold',
                textColor=color_valor, alignment=TA_CENTER, leading=26,
            )),
            Paragraph(label, ParagraphStyle(
                'KL', fontSize=7, fontName='Helvetica',
                textColor=COLOR_TEXTO_GRIS, alignment=TA_CENTER, leading=9,
            )),
        ]
        if sub:
            contenido.append(Paragraph(sub, ParagraphStyle(
                'KS', fontSize=8, fontName='Helvetica',
                textColor=COLOR_TEXTO_GRIS, alignment=TA_CENTER, leading=10,
            )))
        return contenido

    tasa_resp = kpis.get('tasa_respuesta', 0)
    nps_score = kpis.get('nps_score', 0)
    cal_prom  = kpis.get('calificacion_promedio', 0)

    # Color del NPS Score (verde positivo, rojo negativo)
    color_nps = COLOR_VERDE if nps_score >= 0 else COLOR_ROJO

    # 2 filas × 3 columnas
    datos_tabla = [
        [
            _celda_kpi(kpis.get('total_enviadas', 0), 'ENVIADAS',
                       color_valor=COLOR_SIGMA_AZUL),
            _celda_kpi(kpis.get('total_respondidas', 0), 'RESPONDIDAS',
                       f'Tasa: {tasa_resp}%', color_valor=COLOR_VERDE),
            _celda_kpi(kpis.get('total_pendientes', 0), 'PENDIENTES',
                       color_valor=COLOR_AMBAR),
        ],
        [
            _celda_kpi(kpis.get('total_expiradas', 0), 'EXPIRADAS',
                       color_valor=COLOR_ROJO),
            _celda_kpi(f'{nps_score:+.0f}', 'NPS SCORE',
                       color_valor=color_nps),
            _celda_kpi(f'{cal_prom:.1f}/5', 'CALIFICACIÓN PROM.',
                       color_valor=colors.HexColor('#ffc107')),
        ],
    ]

    # Definir anchos: 3 columnas iguales dentro del margen útil
    ancho_util = ANCHO_PAGINA - 2 * MARGEN - 4  # pequeño margen extra
    col_w = ancho_util / 3

    style_cmds = [
        # Borde y relleno general
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        # Fondos de cards — fila 1
        ('BACKGROUND', (0, 0), (0, 0), COLOR_SIGMA_AZUL_LIGHT),
        ('BACKGROUND', (1, 0), (1, 0), COLOR_VERDE_BG),
        ('BACKGROUND', (2, 0), (2, 0), COLOR_AMBAR_BG),
        # Fondos de cards — fila 2
        ('BACKGROUND', (0, 1), (0, 1), COLOR_ROJO_BG),
        ('BACKGROUND', (1, 1), (1, 1), COLOR_PURPURA_BG),
        ('BACKGROUND', (2, 1), (2, 1), COLOR_DORADO_BG),
        # Radio visual con bordes redondeados (simulado con padding extra)
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 4),
    ]

    tabla = Table(datos_tabla, colWidths=[col_w, col_w, col_w], rowHeights=None)
    tabla.setStyle(TableStyle(style_cmds))
    return tabla


def _tabla_submetricas(kpis: dict) -> Table:
    """
    Construye la tabla de 3 sub-métricas (atención, tiempo, recomendación)
    con barras de progreso simuladas con texto y color.

    Cada columna muestra:
      - Icono textual (·)
      - Nombre de la métrica
      - Valor numérico grande
      - Barra de progreso textual
    """
    cal_atencion  = kpis.get('calificacion_atencion_promedio', 0)
    cal_tiempo    = kpis.get('calificacion_tiempo_promedio', 0)
    tasa_rec      = kpis.get('tasa_recomendacion', 0)

    def _barra_texto(porcentaje: float, max_val: float = 100.0,
                     color_hex: str = '#1f6391') -> str:
        """
        Genera una barra de progreso visual usando caracteres unicode llenos.
        Retorna HTML con color para usar en un Paragraph de ReportLab.
        """
        bloques_total = 20
        bloques_llenos = round((porcentaje / max_val) * bloques_total)
        bloques_vacios = bloques_total - bloques_llenos
        barra = '█' * bloques_llenos + '░' * bloques_vacios
        return f'<font color="{color_hex}">{barra}</font>'

    def _celda_sub(label: str, valor_str: str, porcentaje: float,
                   max_val: float, color_hex: str) -> list:
        barra = _barra_texto(porcentaje, max_val, color_hex)
        return [
            Paragraph(label, ParagraphStyle(
                'SubLabel', fontSize=8, fontName='Helvetica',
                textColor=COLOR_TEXTO_GRIS, alignment=TA_CENTER, leading=10,
            )),
            Paragraph(valor_str, ParagraphStyle(
                'SubValor', fontSize=18, fontName='Helvetica-Bold',
                textColor=colors.HexColor(color_hex), alignment=TA_CENTER, leading=22,
            )),
            Paragraph(barra, ParagraphStyle(
                'SubBarra', fontSize=7, fontName='Helvetica',
                textColor=colors.HexColor(color_hex), alignment=TA_CENTER,
                leading=9, spaceAfter=2,
            )),
        ]

    datos = [[
        _celda_sub('CALIFICACIÓN ATENCIÓN', f'{cal_atencion:.1f} / 5',
                   cal_atencion, 5.0, '#1f6391'),
        _celda_sub('CALIFICACIÓN TIEMPO', f'{cal_tiempo:.1f} / 5',
                   cal_tiempo, 5.0, '#6f42c1'),
        _celda_sub('TASA DE RECOMENDACIÓN', f'{tasa_rec:.1f}%',
                   tasa_rec, 100.0, '#198754'),
    ]]

    ancho_util = ANCHO_PAGINA - 2 * MARGEN - 4
    col_w = ancho_util / 3

    style_cmds = [
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (0, 0), COLOR_SIGMA_AZUL_LIGHT),
        ('BACKGROUND', (1, 0), (1, 0), COLOR_PURPURA_BG),
        ('BACKGROUND', (2, 0), (2, 0), COLOR_VERDE_BG),
    ]

    tabla = Table(datos, colWidths=[col_w, col_w, col_w])
    tabla.setStyle(TableStyle(style_cmds))
    return tabla


def _tabla_ranking(responsables: list, estilos: dict) -> Table:
    """
    Construye la tabla de ranking por responsable de seguimiento.

    Columnas:
      # | Responsable | Enviadas | Respondidas | Tasa Resp. | Calificación | NPS Score | Recomienda
    """
    encabezados = ['#', 'Responsable', 'Enviadas', 'Respondidas',
                   'Tasa Resp.', 'Calificación', 'NPS Score', 'Recomienda']

    def _p(texto: str, bold: bool = False, align: str = 'CENTER',
           color=COLOR_TEXTO_DARK) -> Paragraph:
        font = 'Helvetica-Bold' if bold else 'Helvetica'
        al = {'CENTER': TA_CENTER, 'LEFT': TA_LEFT, 'RIGHT': TA_RIGHT}.get(align, TA_CENTER)
        return Paragraph(str(texto), ParagraphStyle(
            'TRCell', fontSize=7.5, fontName=font,
            textColor=color, alignment=al, leading=10,
        ))

    # Encabezados
    filas = [[_p(h, bold=True) for h in encabezados]]

    for i, resp in enumerate(responsables, start=1):
        cal    = resp.get('calificacion_promedio', 0)
        nps_s  = resp.get('nps_score', 0)
        tasa   = resp.get('tasa_recomendacion', 0)
        t_resp = resp.get('total_respondidas', 0)
        t_env  = resp.get('total_enviadas', 1)
        tasa_r = round(t_resp / t_env * 100, 1) if t_env > 0 else 0

        # Color del NPS
        color_nps = COLOR_VERDE if nps_s >= 0 else COLOR_ROJO
        # Emoji-sustituto para el ranking
        medalla = {1: '1°', 2: '2°', 3: '3°'}.get(i, str(i))

        filas.append([
            _p(medalla, bold=(i <= 3)),
            _p(resp.get('nombre', '—'), bold=False, align='LEFT'),
            _p(resp.get('total_enviadas', 0)),
            _p(t_resp),
            _p(f'{tasa_r}%'),
            _p(f'{cal:.1f} / 5', bold=True,
               color=COLOR_VERDE if cal >= 4.0 else (COLOR_AMBAR if cal >= 3.0 else COLOR_ROJO)),
            _p(f'{nps_s:+.0f}', bold=True, color=color_nps),
            _p(f'{tasa:.1f}%'),
        ])

    if len(filas) == 1:
        filas.append([_p('Sin datos', bold=False, align='LEFT')] + [_p('—')] * 7)

    ancho_util = ANCHO_PAGINA - 2 * MARGEN - 4
    col_widths = [
        0.8 * cm,   # #
        4.5 * cm,   # Responsable
        1.5 * cm,   # Enviadas
        1.8 * cm,   # Respondidas
        1.6 * cm,   # Tasa Resp.
        2.2 * cm,   # Calificación
        1.8 * cm,   # NPS Score
        1.8 * cm,   # Recomienda
    ]

    style_cmds = [
        # Encabezado
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_SIGMA_AZUL),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLOR_BLANCO),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # Bordes
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
        # Filas alternas
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLOR_BLANCO, COLOR_GRIS_CLARO]),
        # Top 3 — resaltado dorado
        ('BACKGROUND', (0, 1), (-1, 1), COLOR_DORADO_BG),
        # Padding
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]

    # Resaltar top 3 si hay suficientes filas
    if len(filas) >= 3:
        style_cmds.append(('BACKGROUND', (0, 2), (-1, 2), COLOR_GRIS_CLARO))
    if len(filas) >= 4:
        style_cmds.append(('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#fff8e6')))

    tabla = Table(filas, colWidths=col_widths, repeatRows=1)
    tabla.setStyle(TableStyle(style_cmds))
    return tabla


def _bloque_comentarios(comentarios: list, estilos: dict) -> list:
    """
    Genera la lista de bloques de comentarios de clientes.

    Cada comentario se presenta como una "tarjeta" con:
      - Número de orden + responsable + fecha
      - Calificación con estrellitas (texto)
      - Texto del comentario en cursiva
      - NPS y recomendación

    Args:
        comentarios (list): Lista de dicts con datos del comentario
        estilos (dict): Diccionario de estilos de párrafo

    Returns:
        list: Lista de flowables ReportLab
    """
    if not comentarios:
        return [
            Paragraph(
                'No hay comentarios para el período seleccionado.',
                estilos['normal']
            )
        ]

    elementos = []
    ancho_util = ANCHO_PAGINA - 2 * MARGEN - 4

    for i, com in enumerate(comentarios, start=1):
        # Cabecera del comentario
        orden    = com.get('orden_numero', '—')
        resp     = com.get('responsable', '—')
        fecha    = com.get('fecha', '—')
        cal      = com.get('calificacion', 0) or 0
        nps      = com.get('nps', '—')
        rec      = com.get('recomienda')
        texto    = com.get('comentario', '').strip()

        if not texto:
            continue

        # Estrellas (texto)
        cal_int = int(round(cal)) if cal else 0
        estrellas = '★' * cal_int + '☆' * (5 - cal_int)
        rec_texto = 'Sí recomienda' if rec is True else ('No recomienda' if rec is False else '')
        nps_texto = f'NPS: {nps}' if nps is not None else ''

        color_cal_hex = ('#198754' if cal >= 4.0 else
                         ('#fd7e14' if cal >= 3.0 else '#dc3545'))

        # Fila de info del comentario
        info_data = [[
            Paragraph(
                f'<b>Orden #{orden}</b> &nbsp;|&nbsp; {resp}',
                ParagraphStyle('CInfo', fontSize=8, fontName='Helvetica-Bold',
                               textColor=COLOR_TEXTO_DARK, alignment=TA_LEFT, leading=10)
            ),
            Paragraph(
                f'<font color="{color_cal_hex}">{estrellas}</font>'
                f' &nbsp; {nps_texto} &nbsp; {rec_texto}',
                ParagraphStyle('CCal', fontSize=8, fontName='Helvetica',
                               textColor=COLOR_TEXTO_DARK, alignment=TA_RIGHT, leading=10)
            ),
            Paragraph(
                fecha,
                ParagraphStyle('CFecha', fontSize=7.5, fontName='Helvetica',
                               textColor=COLOR_TEXTO_GRIS, alignment=TA_RIGHT, leading=10)
            ),
        ]]

        info_table = Table(info_data, colWidths=[ancho_util * 0.5,
                                                 ancho_util * 0.35,
                                                 ancho_util * 0.15])
        info_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('BACKGROUND', (0, 0), (-1, -1),
             COLOR_SIGMA_AZUL_LIGHT if i % 2 == 1 else COLOR_GRIS_CLARO),
        ]))

        # Texto del comentario
        texto_com = Paragraph(
            f'"{texto}"',
            ParagraphStyle(
                'ComTexto', fontSize=8, fontName='Helvetica-Oblique',
                textColor=colors.HexColor('#495057'), alignment=TA_LEFT,
                leading=11, leftIndent=8, rightIndent=8,
                spaceAfter=0,
            )
        )

        texto_table = Table([[texto_com]], colWidths=[ancho_util])
        texto_table.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BLANCO),
            ('BOX', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
        ]))

        elementos.append(info_table)
        elementos.append(texto_table)
        elementos.append(Spacer(1, 3 * mm))

    return elementos if elementos else [
        Paragraph('No hay comentarios con texto para el período seleccionado.',
                  estilos['normal'])
    ]


# ===========================================================================
# SECCIÓN ANÁLISIS DE SENTIMIENTO IA
# ===========================================================================

def _seccion_analisis_ia(analisis, estilos: dict) -> list:
    """
    Genera los flowables de la sección "Análisis de Sentimiento IA".

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función toma un objeto AnalisisSentimientoEncuesta (guardado en la
    base de datos por el análisis previo con Ollama/Gemma) y lo convierte en
    tablas y párrafos ReportLab para incluirlos en el PDF.

    Estructura visual:
      ┌─────────────────────────────────────────────────────┐
      │  BADGE sentimiento  │  Resumen ejecutivo             │
      ├─────────────────────┴────────────────────────────────┤
      │  ✅ Aspectos positivos   │  ⚠ Áreas de mejora        │
      │  • tema 1               │  • tema 1                  │
      │  • tema 2               │  • tema 2                  │
      ├──────────────────────────────────────────────────────┤
      │  Recomendación IA (fondo azul claro, ancho completo) │
      ├──────────────────────────────────────────────────────┤
      │  Generado por: modelo | fecha | total encuestas      │
      └──────────────────────────────────────────────────────┘

    Args:
        analisis: Instancia de AnalisisSentimientoEncuesta
        estilos (dict): Diccionario de estilos de párrafo

    Returns:
        list: Lista de flowables ReportLab listos para agregar a `elementos`
    """
    ancho_util = ANCHO_PAGINA - 2 * MARGEN

    # ── Colores según sentimiento ────────────────────────────────────────────
    _COLORES_SENTIMIENTO = {
        'positivo': (COLOR_VERDE,     COLOR_VERDE_BG,  '#198754'),
        'negativo': (COLOR_ROJO,      COLOR_ROJO_BG,   '#dc3545'),
        'neutro':   (COLOR_TEXTO_GRIS, COLOR_GRIS_CLARO, '#6c757d'),
        'mixto':    (COLOR_AMBAR,     COLOR_AMBAR_BG,  '#fd7e14'),
    }
    sent = (analisis.sentimiento_general or 'neutro').lower()
    color_sent, color_sent_bg, hex_sent = _COLORES_SENTIMIENTO.get(
        sent, _COLORES_SENTIMIENTO['neutro']
    )

    # ── Estilos locales ──────────────────────────────────────────────────────
    st_badge = ParagraphStyle(
        'IABadge',
        fontSize=13, fontName='Helvetica-Bold',
        textColor=COLOR_BLANCO,
        alignment=TA_CENTER, leading=16,
        spaceBefore=4, spaceAfter=4,
    )
    st_resumen = ParagraphStyle(
        'IAResumen',
        fontSize=8.5, fontName='Helvetica',
        textColor=COLOR_TEXTO_DARK,
        alignment=TA_LEFT, leading=12,
    )
    st_header_col = ParagraphStyle(
        'IAColHeader',
        fontSize=8.5, fontName='Helvetica-Bold',
        textColor=COLOR_BLANCO,
        alignment=TA_LEFT, leading=11,
    )
    st_item = ParagraphStyle(
        'IAItem',
        fontSize=8, fontName='Helvetica',
        textColor=COLOR_TEXTO_DARK,
        alignment=TA_LEFT, leading=11,
        leftIndent=6,
    )
    st_recomendacion = ParagraphStyle(
        'IARecom',
        fontSize=8.5, fontName='Helvetica-Oblique',
        textColor=colors.HexColor('#0a3d62'),
        alignment=TA_LEFT, leading=12,
        leftIndent=6, rightIndent=6,
    )
    st_meta = ParagraphStyle(
        'IAMeta',
        fontSize=7, fontName='Helvetica',
        textColor=COLOR_TEXTO_GRIS,
        alignment=TA_CENTER, leading=9,
    )

    # ── Fila 1: Badge sentimiento + Resumen ejecutivo ────────────────────────
    sent_label = sent.upper()
    icono_sent = {
        'positivo': '✓ POSITIVO',
        'negativo': '✗ NEGATIVO',
        'neutro':   '~ NEUTRO',
        'mixto':    '≈ MIXTO',
    }.get(sent, sent_label)

    badge_cell = [
        Spacer(1, 4 * mm),
        Paragraph(icono_sent, st_badge),
        Spacer(1, 2 * mm),
        Paragraph(
            f'{analisis.total_encuestas} encuesta{"s" if analisis.total_encuestas != 1 else ""} analizadas',
            ParagraphStyle('IASub', fontSize=7.5, fontName='Helvetica',
                           textColor=COLOR_BLANCO, alignment=TA_CENTER, leading=9),
        ),
        Spacer(1, 4 * mm),
    ]

    resumen_cell = [
        Spacer(1, 3 * mm),
        Paragraph('<b>Resumen Ejecutivo</b>', ParagraphStyle(
            'IAResTitle', fontSize=8.5, fontName='Helvetica-Bold',
            textColor=COLOR_TEXTO_GRIS, alignment=TA_LEFT, leading=11,
        )),
        Spacer(1, 2 * mm),
        Paragraph(analisis.resumen_ejecutivo or '—', st_resumen),
        Spacer(1, 3 * mm),
    ]

    fila1_tabla = Table(
        [[badge_cell, resumen_cell]],
        colWidths=[ancho_util * 0.22, ancho_util * 0.78],
    )
    fila1_tabla.setStyle(TableStyle([
        ('BACKGROUND',     (0, 0), (0, 0), color_sent),
        ('BACKGROUND',     (1, 0), (1, 0), COLOR_GRIS_CLARO),
        ('VALIGN',         (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING',    (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',   (0, 0), (-1, -1), 8),
        ('TOPPADDING',     (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), 0),
        ('LINEBELOW',      (0, 0), (-1, 0), 0.5, COLOR_GRIS_BORDE),
    ]))

    # ── Fila 2: Temas positivos | Temas negativos ────────────────────────────
    temas_pos = analisis.temas_positivos or []
    temas_neg = analisis.temas_negativos or []

    def _lista_temas(temas: list, vacia: str) -> list:
        if not temas:
            return [Paragraph(vacia, st_item)]
        return [Paragraph(f'• {t}', st_item) for t in temas]

    col_pos = [Paragraph('✓  Aspectos Positivos', st_header_col), Spacer(1, 2 * mm)]
    col_neg = [Paragraph('⚠  Áreas de Mejora', st_header_col), Spacer(1, 2 * mm)]

    fila2_tabla = Table(
        [[col_pos, col_neg]],
        colWidths=[ancho_util * 0.5, ancho_util * 0.5],
    )
    fila2_tabla.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (0, 0), COLOR_VERDE),
        ('BACKGROUND',    (1, 0), (1, 0), COLOR_ROJO),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LINEBELOW',     (0, 0), (-1, 0), 0.5, COLOR_GRIS_BORDE),
    ]))

    # Fila de items (fondo claro) — mismas columnas
    items_pos = _lista_temas(temas_pos, 'Sin temas positivos identificados.')
    items_neg = _lista_temas(temas_neg, 'Sin áreas de mejora identificadas.')
    # Agregar spacers al final de cada columna para padding uniforme
    col_pos_items = items_pos + [Spacer(1, 4 * mm)]
    col_neg_items = items_neg + [Spacer(1, 4 * mm)]

    fila2b_tabla = Table(
        [[col_pos_items, col_neg_items]],
        colWidths=[ancho_util * 0.5, ancho_util * 0.5],
    )
    fila2b_tabla.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (0, 0), COLOR_VERDE_BG),
        ('BACKGROUND',    (1, 0), (1, 0), COLOR_ROJO_BG),
        ('VALIGN',        (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('LINEBELOW',     (0, 0), (-1, 0), 0.5, COLOR_GRIS_BORDE),
    ]))

    # ── Fila 3: Recomendación IA (ancho completo) ────────────────────────────
    recom_texto = analisis.recomendacion_ia or ''
    recom_tabla = Table(
        [[
            Paragraph('<b>Recomendación IA:</b>', ParagraphStyle(
                'IARecomTitle', fontSize=8.5, fontName='Helvetica-Bold',
                textColor=colors.HexColor('#0a3d62'), alignment=TA_LEFT, leading=11,
            )),
        ], [
            Paragraph(recom_texto, st_recomendacion),
        ]],
        colWidths=[ancho_util],
    )
    recom_tabla.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), COLOR_SIGMA_AZUL_LIGHT),
        ('LEFTPADDING',   (0, 0), (-1, -1), 10),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 10),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LINEBELOW',     (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
    ]))

    # ── Fila 4: Meta-información ─────────────────────────────────────────────
    fecha_str = (
        analisis.fecha_analisis.strftime('%d/%m/%Y a las %H:%M')
        if analisis.fecha_analisis else '—'
    )
    meta_tabla = Table(
        [[Paragraph(
            f'Modelo: {analisis.modelo_usado or "—"} &nbsp;|&nbsp; '
            f'Analizado: {fecha_str} &nbsp;|&nbsp; '
            f'Basado en {analisis.total_encuestas} encuesta'
            f'{"s" if analisis.total_encuestas != 1 else ""}',
            st_meta,
        )]],
        colWidths=[ancho_util],
    )
    meta_tabla.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), COLOR_GRIS_THEAD),
        ('LEFTPADDING',   (0, 0), (-1, -1), 8),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))

    return [
        fila1_tabla,
        fila2_tabla,
        fila2b_tabla,
        recom_tabla,
        meta_tabla,
    ]


# ===========================================================================
# FUNCIÓN PRINCIPAL EXPORTADA
# ===========================================================================

def generar_pdf_reporte_encuestas(datos: dict) -> io.BytesIO:
    """
    Genera el PDF del Reporte Ejecutivo de Encuestas de Satisfacción.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta es la función principal. Recibe un diccionario 'datos' con toda
    la información necesaria y construye el PDF completo usando ReportLab
    (texto, tablas, colores) y matplotlib (gráficas de líneas y pie).

    El PDF se guarda en un 'buffer' (archivo en memoria RAM) que luego
    se envía directamente al navegador para descarga, sin tocar el disco.

    Args:
        datos (dict): Diccionario con las siguientes claves:
            - 'kpis' (dict):          Métricas globales del dashboard
            - 'tendencia' (dict):     Datos semana a semana para el gráfico
            - 'nps_dist' (dict):      Distribución promotores/pasivos/detractores
            - 'responsables' (list):  Lista de dicts con métricas por responsable
            - 'comentarios' (list):   Lista de comentarios recientes
            - 'periodo' (str):        Descripción del período filtrado
            - 'filtros_activos' (bool): True si hay filtros aplicados
            - 'analisis_ia' (obj|None): Instancia de AnalisisSentimientoEncuesta
                                        cacheada; None omite la sección IA

    Returns:
        io.BytesIO: Buffer con el PDF listo para enviar como HttpResponse.

    Ejemplo de uso en la vista:
        pdf_buffer = generar_pdf_reporte_encuestas(datos)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="reporte.pdf"'
        return response
    """
    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=MARGEN,
        bottomMargin=MARGEN,
        title='Reporte Ejecutivo — Encuestas de Satisfacción',
        author='SIGMA — Sistema Integrado de Gestión Técnica',
    )

    estilos  = _crear_estilos()
    elementos = []

    # Extraer datos
    kpis         = datos.get('kpis', {})
    tendencia    = datos.get('tendencia', {'labels': [], 'datasets': {}})
    nps_dist     = datos.get('nps_dist', {})
    responsables = datos.get('responsables', [])
    comentarios  = datos.get('comentarios', [])
    periodo      = datos.get('periodo', 'Sin filtros — todos los registros')
    filtros      = datos.get('filtros_activos', False)
    analisis_ia  = datos.get('analisis_ia')   # None → sección IA se omite

    fecha_gen = datetime.now().strftime('%d/%m/%Y %H:%M')

    # Ancho útil para gráficos (en puntos)
    ancho_util_pt = ANCHO_PAGINA - 2 * MARGEN

    # ================================================================
    # HEADER DEL DOCUMENTO
    # ================================================================
    # Tabla de 2 columnas: título a la izq, info de fecha a la der
    header_izq = [
        Paragraph('SIGMA', ParagraphStyle(
            'LogoTexto', fontSize=10, fontName='Helvetica-Bold',
            textColor=colors.HexColor('#cce5f6'), leading=12,
        )),
        Paragraph(
            'Reporte Ejecutivo de Encuestas de Satisfacción',
            estilos['titulo']
        ),
        Paragraph(
            'Métricas, tendencias y análisis de experiencia del cliente',
            estilos['subtitulo']
        ),
    ]

    header_der = [
        Paragraph(
            f'<b>Generado:</b> {fecha_gen}',
            estilos['info_header']
        ),
        Paragraph(
            f'<b>Período:</b> {periodo}',
            estilos['info_header']
        ),
        Paragraph(
            f'<b>Filtros:</b> {"Aplicados" if filtros else "Sin filtros"}',
            estilos['info_header']
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            f'<b>Total comentarios:</b> {len(comentarios)}',
            estilos['info_header']
        ),
    ]

    header_tabla = Table(
        [[header_izq, header_der]],
        colWidths=[ancho_util_pt * 0.65, ancho_util_pt * 0.35],
    )
    header_tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_SIGMA_AZUL),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 6),
    ]))

    elementos.append(header_tabla)
    elementos.append(Spacer(1, 6 * mm))

    # ================================================================
    # SECCIÓN 1 — KPIs PRINCIPALES
    # ================================================================
    elementos.append(KeepTogether(
        _banner_seccion('KPIs PRINCIPALES', COLOR_SIGMA_AZUL) +
        [_tabla_kpis(kpis, estilos)]
    ))
    elementos.append(Spacer(1, 6 * mm))

    # ================================================================
    # SECCIÓN 2 — SUB-MÉTRICAS
    # ================================================================
    elementos.append(KeepTogether(
        _banner_seccion('SUB-MÉTRICAS DE CALIDAD', COLOR_PURPURA) +
        [_tabla_submetricas(kpis)]
    ))
    elementos.append(Spacer(1, 6 * mm))

    # ================================================================
    # SECCIÓN 3 — GRÁFICO TENDENCIA SEMANAL
    # ================================================================
    grafico_tend = _grafico_tendencia(
        tendencia,
        ancho_pt=ancho_util_pt,
        alto_pt=145,
    )
    elementos.append(KeepTogether(
        _banner_seccion('TENDENCIA SEMANAL', COLOR_SIGMA_AZUL_DARK) +
        [grafico_tend]
    ))
    elementos.append(Spacer(1, 6 * mm))

    # ================================================================
    # SECCIÓN 4 — NPS + RANKING VISUAL (2 columnas)
    # ================================================================
    # Gráfico NPS (izquierda) + Barras ranking (derecha) en paralelo
    ancho_nps     = ancho_util_pt * 0.38
    ancho_ranking = ancho_util_pt * 0.58
    gap           = ancho_util_pt * 0.04

    img_nps = _grafico_nps_pie(nps_dist, ancho_pt=ancho_nps, alto_pt=165)
    img_bar = _grafico_ranking_barras(responsables, ancho_pt=ancho_ranking, alto_pt=165)

    graficos_tabla = Table(
        [[img_nps, Spacer(gap, 1), img_bar]],
        colWidths=[ancho_nps, gap, ancho_ranking],
    )
    graficos_tabla.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
    ]))

    elementos.append(KeepTogether(
        _banner_seccion('DISTRIBUCIÓN NPS & RANKING DE RESPONSABLES', COLOR_VERDE) +
        [graficos_tabla]
    ))
    elementos.append(Spacer(1, 6 * mm))

    # ================================================================
    # SECCIÓN 5 — TABLA DE RANKING POR RESPONSABLE
    # ================================================================
    elementos.append(KeepTogether(
        _banner_seccion('RANKING DETALLADO POR RESPONSABLE', COLOR_SIGMA_AZUL) +
        [_tabla_ranking(responsables, estilos)]
    ))
    elementos.append(Spacer(1, 6 * mm))

    # ================================================================
    # SECCIÓN 5B — ANÁLISIS DE SENTIMIENTO IA (solo si hay caché)
    # ================================================================
    if analisis_ia is not None:
        bloques_ia = _seccion_analisis_ia(analisis_ia, estilos)
        elementos.append(KeepTogether(
            _banner_seccion('ANÁLISIS DE SENTIMIENTO IA', COLOR_PURPURA) +
            bloques_ia
        ))
        elementos.append(Spacer(1, 6 * mm))

    # ================================================================
    # SECCIÓN 6 — COMENTARIOS DE CLIENTES
    # ================================================================
    total_com = len(comentarios)
    label_com = (
        f'COMENTARIOS DE CLIENTES ({total_com} registros — período filtrado)'
        if filtros and total_com > 10
        else f'COMENTARIOS DE CLIENTES (últimos {min(total_com, 10)} registros)'
    )
    # El banner de comentarios siempre va junto con el primer comentario
    bloques_com = _bloque_comentarios(comentarios, estilos)
    primer_bloque = bloques_com[:1] if bloques_com else []
    resto_bloques = bloques_com[1:] if len(bloques_com) > 1 else []

    elementos.append(KeepTogether(
        _banner_seccion(label_com, colors.HexColor('#0d6efd')) +
        primer_bloque
    ))
    elementos += resto_bloques
    elementos.append(Spacer(1, 6 * mm))

    # ================================================================
    # FOOTER DEL DOCUMENTO
    # ================================================================
    elementos.append(
        HRFlowable(width='100%', thickness=0.5, color=COLOR_GRIS_BORDE)
    )
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(
        Paragraph(
            f'SIGMA — Sistema Integrado de Gestión Técnica &nbsp;|&nbsp; '
            f'Reporte generado el {fecha_gen} &nbsp;|&nbsp; '
            f'Este documento es de uso interno y confidencial.',
            estilos['footer']
        )
    )

    # ---- Construir el PDF ----
    doc.build(elementos)
    buffer.seek(0)
    return buffer
