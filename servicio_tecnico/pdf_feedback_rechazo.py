"""
Generador de PDF — Reporte Ejecutivo de Feedback de Rechazo
==========================================================

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Espejo del PDF de encuestas de satisfacción, pero enfocado a rechazos
de cotización: KPIs de volumen/tasa, motivos, tendencia, ranking por
responsable, análisis IA cacheado y comentarios del cliente.

No llama a la IA: solo anexa AnalisisSentimientoEncuesta si la vista
lo pasa en datos['analisis_ia'].

Stack: ReportLab + matplotlib Agg (igual que pdf_encuestas.py).
"""

from __future__ import annotations

import io
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import mm, cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
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

# Reutilizamos paleta, estilos, banner y sección IA del PDF de satisfacción
from servicio_tecnico.pdf_encuestas import (
    ANCHO_PAGINA,
    MARGEN,
    COLOR_SIGMA_AZUL,
    COLOR_SIGMA_AZUL_DARK,
    COLOR_SIGMA_AZUL_LIGHT,
    COLOR_VERDE,
    COLOR_VERDE_BG,
    COLOR_ROJO,
    COLOR_AMBAR,
    COLOR_PURPURA,
    COLOR_GRIS_CLARO,
    COLOR_GRIS_THEAD,
    COLOR_GRIS_BORDE,
    COLOR_TEXTO_GRIS,
    COLOR_TEXTO_DARK,
    COLOR_BLANCO,
    MPL_AZUL,
    MPL_VERDE,
    MPL_AMBAR,
    MPL_ROJO,
    MPL_GRIS,
    _crear_estilos,
    _banner_seccion,
    _seccion_analisis_ia,
)


# ===========================================================================
# GRÁFICOS
# ===========================================================================

def _grafico_tendencia_rechazo(tendencia: dict, ancho_pt: float, alto_pt: float) -> Image:
    """
    Barras enviados/respondidos + línea de tasa de respuesta semanal.

    Args:
        tendencia: {'labels': [...], 'datasets': {total_enviados, total_respondidos, tasa_respuesta}}
    """
    labels = tendencia.get('labels', [])
    datasets = tendencia.get('datasets', {})
    enviados = datasets.get('total_enviados', [])
    respondidos = datasets.get('total_respondidos', [])
    tasas = datasets.get('tasa_respuesta', [])

    ancho_in = ancho_pt / 72.0
    alto_in = alto_pt / 72.0
    fig, ax1 = plt.subplots(figsize=(ancho_in, alto_in), dpi=120)
    fig.patch.set_facecolor('#fafafa')
    ax1.set_facecolor('#fafafa')

    if not labels:
        ax1.text(
            0.5, 0.5, 'Sin datos para el período seleccionado',
            ha='center', va='center', fontsize=9, color=MPL_GRIS,
            transform=ax1.transAxes,
        )
        ax1.set_axis_off()
    else:
        x = range(len(labels))
        w = 0.35
        ax1.bar([i - w / 2 for i in x], enviados, width=w, color=MPL_AZUL, label='Enviados')
        ax1.bar([i + w / 2 for i in x], respondidos, width=w, color=MPL_VERDE, label='Respondidos')
        ax1.set_xticks(list(x))
        ax1.set_xticklabels(labels, rotation=30, ha='right', fontsize=7)
        ax1.set_ylabel('Cantidad', fontsize=8, color=MPL_AZUL)
        ax1.tick_params(axis='y', labelsize=7)
        ax1.legend(loc='upper left', fontsize=7, frameon=False)

        ax2 = ax1.twinx()
        ax2.plot(list(x), tasas, color=MPL_AMBAR, marker='o', linewidth=1.5, label='Tasa %')
        ax2.set_ylabel('Tasa respuesta %', fontsize=8, color=MPL_AMBAR)
        ax2.tick_params(axis='y', labelsize=7, colors=MPL_AMBAR)
        ax2.set_ylim(0, 110)

    fig.tight_layout(pad=0.4)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=ancho_pt, height=alto_pt)


def _grafico_motivos_pie(motivos: list, ancho_pt: float, alto_pt: float) -> Image:
    """
    Dona de distribución por motivo de rechazo (top 6 + 'Otros').

    Args:
        motivos: lista de dicts con label, total
    """
    ancho_in = ancho_pt / 72.0
    alto_in = alto_pt / 72.0
    fig, ax = plt.subplots(figsize=(ancho_in, alto_in), dpi=120)
    fig.patch.set_facecolor('#fafafa')

    if not motivos:
        ax.text(
            0.5, 0.5, 'Sin motivos',
            ha='center', va='center', fontsize=9, color=MPL_GRIS,
            transform=ax.transAxes,
        )
        ax.set_axis_off()
    else:
        # Top 6 + agrupar resto
        ordenados = sorted(motivos, key=lambda m: m.get('total', 0), reverse=True)
        top = ordenados[:6]
        resto = sum(m.get('total', 0) for m in ordenados[6:])
        labels = [m.get('label', m.get('motivo', '—'))[:28] for m in top]
        sizes = [m.get('total', 0) for m in top]
        if resto > 0:
            labels.append('Otros')
            sizes.append(resto)

        palette = [MPL_AZUL, MPL_ROJO, MPL_AMBAR, MPL_VERDE, '#6f42c1', '#20c997', MPL_GRIS]
        colors_pie = palette[: len(sizes)]
        ax.pie(
            sizes,
            labels=None,
            colors=colors_pie,
            startangle=90,
            wedgeprops=dict(width=0.45, edgecolor='white'),
        )
        ax.legend(
            labels,
            loc='center left',
            bbox_to_anchor=(0.95, 0.5),
            fontsize=6.5,
            frameon=False,
        )
        ax.set_title('Por motivo', fontsize=9, color='#212529', pad=4)

    fig.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=ancho_pt, height=alto_pt)


def _grafico_ranking_barras_rechazo(
    responsables: list,
    ancho_pt: float,
    alto_pt: float,
) -> Image:
    """Barras horizontales de tasa de respuesta por responsable (top 8)."""
    ancho_in = ancho_pt / 72.0
    alto_in = alto_pt / 72.0
    fig, ax = plt.subplots(figsize=(ancho_in, alto_in), dpi=120)
    fig.patch.set_facecolor('#fafafa')
    ax.set_facecolor('#fafafa')

    top = responsables[:8]
    if not top:
        ax.text(
            0.5, 0.5, 'Sin responsables',
            ha='center', va='center', fontsize=9, color=MPL_GRIS,
            transform=ax.transAxes,
        )
        ax.set_axis_off()
    else:
        nombres = [r.get('nombre', '—')[:22] for r in reversed(top)]
        tasas = [r.get('tasa_respuesta', 0) for r in reversed(top)]
        ax.barh(nombres, tasas, color=MPL_AZUL, height=0.6)
        ax.set_xlim(0, 110)
        ax.set_xlabel('Tasa respuesta %', fontsize=7)
        ax.tick_params(axis='both', labelsize=7)
        ax.set_title('Tasa por responsable', fontsize=9, color='#212529', pad=4)

    fig.tight_layout(pad=0.3)
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=ancho_pt, height=alto_pt)


# ===========================================================================
# TABLAS
# ===========================================================================

def _tabla_kpis_rechazo(kpis: dict) -> Table:
    """5 KPIs de volumen + tasa en fila."""

    def _celda(valor, label, color_fondo=COLOR_GRIS_CLARO, color_valor=COLOR_TEXTO_DARK):
        return [
            Paragraph(str(valor), ParagraphStyle(
                'RKV', fontSize=18, fontName='Helvetica-Bold',
                textColor=color_valor, alignment=TA_CENTER, leading=22,
            )),
            Paragraph(label, ParagraphStyle(
                'RKL', fontSize=7, fontName='Helvetica',
                textColor=COLOR_TEXTO_GRIS, alignment=TA_CENTER, leading=9,
            )),
        ]

    tasa = kpis.get('tasa_respuesta', 0)
    datos = [[
        _celda(kpis.get('total_enviados', 0), 'ENVIADOS', COLOR_SIGMA_AZUL_LIGHT, COLOR_SIGMA_AZUL),
        _celda(kpis.get('total_respondidos', 0), 'RESPONDIDOS', COLOR_VERDE_BG, COLOR_VERDE),
        _celda(kpis.get('total_pendientes', 0), 'PENDIENTES', colors.HexColor('#fff3cd'), COLOR_AMBAR),
        _celda(kpis.get('total_expirados', 0), 'EXPIRADOS', colors.HexColor('#f8d7da'), COLOR_ROJO),
        _celda(f'{tasa}%', 'TASA RESPUESTA', COLOR_GRIS_CLARO, COLOR_TEXTO_DARK),
    ]]
    ancho = ANCHO_PAGINA - 2 * MARGEN - 4
    col_w = ancho / 5
    tabla = Table(datos, colWidths=[col_w] * 5)
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (0, 0), COLOR_SIGMA_AZUL_LIGHT),
        ('BACKGROUND', (1, 0), (1, 0), COLOR_VERDE_BG),
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#fff3cd')),
        ('BACKGROUND', (3, 0), (3, 0), colors.HexColor('#f8d7da')),
        ('BACKGROUND', (4, 0), (4, 0), COLOR_GRIS_CLARO),
    ]))
    return tabla


def _tabla_submetricas_rechazo(kpis: dict, motivos: list) -> Table:
    """Motivo top + resumen de top 3 motivos."""
    motivo_top = kpis.get('motivo_mas_frecuente') or '—'
    pct = kpis.get('motivo_mas_frecuente_porcentaje', 0)
    top3 = motivos[:3]
    lineas_top = '<br/>'.join(
        f'• {m.get("label", "—")}: {m.get("total", 0)} '
        f'({m.get("respondidos", 0)} resp.)'
        for m in top3
    ) or 'Sin datos'

    celda_motivo = [
        Paragraph('MOTIVO MÁS FRECUENTE', ParagraphStyle(
            'SubH', fontSize=7, fontName='Helvetica-Bold',
            textColor=COLOR_TEXTO_GRIS, alignment=TA_CENTER, leading=9,
        )),
        Spacer(1, 2 * mm),
        Paragraph(motivo_top[:60], ParagraphStyle(
            'SubV', fontSize=11, fontName='Helvetica-Bold',
            textColor=COLOR_ROJO, alignment=TA_CENTER, leading=14,
        )),
        Paragraph(f'{pct}% del total enviado', ParagraphStyle(
            'SubS', fontSize=8, fontName='Helvetica',
            textColor=COLOR_TEXTO_GRIS, alignment=TA_CENTER, leading=10,
        )),
    ]
    celda_top = [
        Paragraph('TOP MOTIVOS', ParagraphStyle(
            'SubH2', fontSize=7, fontName='Helvetica-Bold',
            textColor=COLOR_TEXTO_GRIS, alignment=TA_CENTER, leading=9,
        )),
        Spacer(1, 2 * mm),
        Paragraph(lineas_top, ParagraphStyle(
            'SubL', fontSize=8, fontName='Helvetica',
            textColor=COLOR_TEXTO_DARK, alignment=TA_LEFT, leading=11,
        )),
    ]
    ancho = ANCHO_PAGINA - 2 * MARGEN - 4
    tabla = Table([[celda_motivo, celda_top]], colWidths=[ancho * 0.45, ancho * 0.55])
    tabla.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.5, COLOR_GRIS_BORDE),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#f8d7da')),
        ('BACKGROUND', (1, 0), (1, 0), COLOR_SIGMA_AZUL_LIGHT),
    ]))
    return tabla


def _tabla_ranking_rechazo(responsables: list, estilos: dict) -> Table:
    """Ranking: # | Responsable | Enviados | Respondidos | Tasa."""

    def _p(texto, bold=False, align='CENTER', color=COLOR_TEXTO_DARK):
        font = 'Helvetica-Bold' if bold else 'Helvetica'
        al = {'CENTER': TA_CENTER, 'LEFT': TA_LEFT}.get(align, TA_CENTER)
        return Paragraph(str(texto), ParagraphStyle(
            'RRCell', fontSize=7.5, fontName=font,
            textColor=color, alignment=al, leading=10,
        ))

    encabezados = ['#', 'Responsable', 'Enviados', 'Respondidos', 'Tasa resp.']
    filas = [[_p(h, bold=True) for h in encabezados]]
    for i, resp in enumerate(responsables, start=1):
        tasa = resp.get('tasa_respuesta', 0)
        filas.append([
            _p({1: '1°', 2: '2°', 3: '3°'}.get(i, str(i)), bold=(i <= 3)),
            _p(resp.get('nombre', '—'), align='LEFT'),
            _p(resp.get('total_enviados', 0)),
            _p(resp.get('total_respondidos', 0)),
            _p(f'{tasa}%', bold=True, color=COLOR_VERDE if tasa >= 50 else COLOR_AMBAR),
        ])
    if len(filas) == 1:
        filas.append([_p('Sin datos', align='LEFT')] + [_p('—')] * 4)

    ancho = ANCHO_PAGINA - 2 * MARGEN - 4
    col_w = [0.8 * cm, 7 * cm, 2.2 * cm, 2.5 * cm, 2.5 * cm]
    # Ajustar si no suma exactamente
    suma = sum(col_w)
    if abs(suma - ancho) > 1:
        col_w[1] = col_w[1] + (ancho - suma)

    tabla = Table(filas, colWidths=col_w)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_SIGMA_AZUL),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLOR_BLANCO),
        ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(filas)):
        if i % 2 == 0:
            style_cmds.append(('BACKGROUND', (0, i), (-1, i), COLOR_GRIS_CLARO))
    tabla.setStyle(TableStyle(style_cmds))
    return tabla


def _bloque_comentarios_rechazo(comentarios: list, estilos: dict) -> list:
    """Lista de comentarios con motivo en lugar de NPS/estrellas."""
    if not comentarios:
        return [Paragraph(
            'No hay comentarios para el período seleccionado.',
            estilos['normal'],
        )]

    elementos = []
    ancho = ANCHO_PAGINA - 2 * MARGEN - 4

    for i, com in enumerate(comentarios, start=1):
        texto = (com.get('comentario') or '').strip()
        if not texto:
            continue
        orden = com.get('orden_numero', '—')
        resp = com.get('responsable', '—')
        fecha = com.get('fecha', '—')
        motivo = com.get('motivo_rechazo', '—')

        info = Table([[
            Paragraph(
                f'<b>Orden #{orden}</b> &nbsp;|&nbsp; {resp}',
                ParagraphStyle(
                    'RCInfo', fontSize=8, fontName='Helvetica-Bold',
                    textColor=COLOR_TEXTO_DARK, alignment=TA_LEFT, leading=10,
                ),
            ),
            Paragraph(
                f'<font color="#dc3545">{motivo}</font>',
                ParagraphStyle(
                    'RCMot', fontSize=7.5, fontName='Helvetica',
                    textColor=COLOR_ROJO, alignment=TA_RIGHT, leading=10,
                ),
            ),
            Paragraph(
                fecha,
                ParagraphStyle(
                    'RCFecha', fontSize=7.5, fontName='Helvetica',
                    textColor=COLOR_TEXTO_GRIS, alignment=TA_RIGHT, leading=10,
                ),
            ),
        ]], colWidths=[ancho * 0.45, ancho * 0.4, ancho * 0.15])
        info.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('BACKGROUND', (0, 0), (-1, -1),
             COLOR_SIGMA_AZUL_LIGHT if i % 2 == 1 else COLOR_GRIS_CLARO),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))

        texto_p = Paragraph(
            f'"{texto}"',
            ParagraphStyle(
                'RCTexto', fontSize=8, fontName='Helvetica-Oblique',
                textColor=colors.HexColor('#495057'), alignment=TA_LEFT,
                leading=11, leftIndent=8, rightIndent=8,
            ),
        )
        texto_t = Table([[texto_p]], colWidths=[ancho])
        texto_t.setStyle(TableStyle([
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('RIGHTPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('BACKGROUND', (0, 0), (-1, -1), COLOR_BLANCO),
            ('BOX', (0, 0), (-1, -1), 0.3, COLOR_GRIS_BORDE),
        ]))
        elementos.append(KeepTogether([info, texto_t, Spacer(1, 2 * mm)]))

    return elementos


# ===========================================================================
# FUNCIÓN PRINCIPAL
# ===========================================================================

def generar_pdf_reporte_rechazo(datos: dict) -> io.BytesIO:
    """
    Genera el PDF del Reporte Ejecutivo de Feedback de Rechazo.

    Args:
        datos: dict con claves:
            kpis, motivos, tendencia, responsables, comentarios,
            periodo, filtros_activos, analisis_ia (obj|None)

    Returns:
        BytesIO con el PDF listo para HttpResponse.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=MARGEN,
        bottomMargin=MARGEN,
    )
    estilos = _crear_estilos()
    elementos: list = []
    ancho_util = ANCHO_PAGINA - 2 * MARGEN

    kpis = datos.get('kpis') or {}
    motivos = datos.get('motivos') or []
    tendencia = datos.get('tendencia') or {'labels': [], 'datasets': {}}
    responsables = datos.get('responsables') or []
    comentarios = datos.get('comentarios') or []
    periodo = datos.get('periodo') or 'Todos los registros'
    filtros = bool(datos.get('filtros_activos'))
    analisis_ia = datos.get('analisis_ia')
    fecha_gen = datetime.now().strftime('%d/%m/%Y %H:%M')

    # ── Header ────────────────────────────────────────────────────────────
    header_izq = [
        Paragraph('SIGMA — Feedback de Rechazo', estilos['titulo']),
        Paragraph('Reporte ejecutivo de cotizaciones rechazadas', estilos['subtitulo']),
    ]
    header_der = [
        Paragraph(f'<b>Generado:</b> {fecha_gen}', estilos['info_header']),
        Paragraph(f'<b>Período:</b> {periodo}', estilos['info_header']),
        Paragraph(
            f'<b>Filtros:</b> {"Aplicados" if filtros else "Sin filtros"}',
            estilos['info_header'],
        ),
        Paragraph(
            f'<b>Comentarios:</b> {len(comentarios)}',
            estilos['info_header'],
        ),
    ]
    header = Table(
        [[header_izq, header_der]],
        colWidths=[ancho_util * 0.62, ancho_util * 0.38],
    )
    header.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_SIGMA_AZUL),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elementos.append(header)
    elementos.append(Spacer(1, 6 * mm))

    # ── KPIs ──────────────────────────────────────────────────────────────
    elementos.append(KeepTogether(
        _banner_seccion('KPIs PRINCIPALES', COLOR_SIGMA_AZUL)
        + [_tabla_kpis_rechazo(kpis)]
    ))
    elementos.append(Spacer(1, 5 * mm))

    # ── Submétricas motivos ───────────────────────────────────────────────
    elementos.append(KeepTogether(
        _banner_seccion('MOTIVOS DE RECHAZO', COLOR_ROJO)
        + [_tabla_submetricas_rechazo(kpis, motivos)]
    ))
    elementos.append(Spacer(1, 5 * mm))

    # ── Tendencia ─────────────────────────────────────────────────────────
    elementos.append(KeepTogether(
        _banner_seccion('TENDENCIA SEMANAL', COLOR_SIGMA_AZUL_DARK)
        + [_grafico_tendencia_rechazo(tendencia, ancho_util, 140)]
    ))
    elementos.append(Spacer(1, 5 * mm))

    # ── Pie motivos + ranking visual ──────────────────────────────────────
    ancho_pie = ancho_util * 0.42
    ancho_rank = ancho_util * 0.54
    gap = ancho_util * 0.04
    graficos = Table(
        [[
            _grafico_motivos_pie(motivos, ancho_pie, 160),
            Spacer(gap, 1),
            _grafico_ranking_barras_rechazo(responsables, ancho_rank, 160),
        ]],
        colWidths=[ancho_pie, gap, ancho_rank],
    )
    graficos.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    elementos.append(KeepTogether(
        _banner_seccion('DISTRIBUCIÓN POR MOTIVO & RESPONSABLES', COLOR_VERDE)
        + [graficos]
    ))
    elementos.append(Spacer(1, 5 * mm))

    # ── Tabla ranking ─────────────────────────────────────────────────────
    elementos.append(KeepTogether(
        _banner_seccion('RANKING POR RESPONSABLE', COLOR_SIGMA_AZUL)
        + [_tabla_ranking_rechazo(responsables, estilos)]
    ))
    elementos.append(Spacer(1, 5 * mm))

    # ── Análisis IA (caché) ───────────────────────────────────────────────
    if analisis_ia is not None:
        bloques_ia = _seccion_analisis_ia(
            analisis_ia,
            estilos,
            titulo_positivos='✓  Señales Favorables',
            titulo_negativos='⚠  Razones de Rechazo',
            vacia_positivos='Sin señales favorables destacadas.',
            vacia_negativos='Sin razones de rechazo identificadas.',
            label_unidad='feedback',
        )
        elementos.append(KeepTogether(
            _banner_seccion('ANÁLISIS DE SENTIMIENTO IA', COLOR_PURPURA)
            + bloques_ia
        ))
        elementos.append(Spacer(1, 5 * mm))

    # ── Comentarios ───────────────────────────────────────────────────────
    total_com = len(comentarios)
    label_com = (
        f'COMENTARIOS DE CLIENTES ({total_com} registros — período filtrado)'
        if filtros and total_com > 10
        else f'COMENTARIOS DE CLIENTES (últimos {min(total_com, 10)} registros)'
    )
    bloques_com = _bloque_comentarios_rechazo(comentarios, estilos)
    primer = bloques_com[:1] if bloques_com else []
    resto = bloques_com[1:] if len(bloques_com) > 1 else []
    elementos.append(KeepTogether(
        _banner_seccion(label_com, colors.HexColor('#0d6efd')) + primer
    ))
    elementos += resto
    elementos.append(Spacer(1, 5 * mm))

    # ── Footer ────────────────────────────────────────────────────────────
    elementos.append(HRFlowable(width='100%', thickness=0.5, color=COLOR_GRIS_BORDE))
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(Paragraph(
        f'SIGMA — Sistema Integrado de Gestión Técnica &nbsp;|&nbsp; '
        f'Reporte generado el {fecha_gen} &nbsp;|&nbsp; '
        f'Uso interno y confidencial.',
        estilos['footer'],
    ))

    doc.build(elementos)
    buffer.seek(0)
    return buffer
