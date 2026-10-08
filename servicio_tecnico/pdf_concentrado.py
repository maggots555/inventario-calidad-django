"""
PDF del Concentrado Semanal CIS
===============================

EXPLICACIÓN PARA PRINCIPIANTES:
Este PDF no es una copia del Excel. Arriba se lee la semana (cuántos
entraron, cuántos salieron y cómo cambió contra la semana anterior) y
la lista de equipos candidatos a RHITSO. Debajo siguen las tablas por día.

El diseño es el de los formatos OOW y Diagnóstico: hoja vertical, logo
SIC, barras navy #003366 y pie con el número de página.
"""

import io
import os
from datetime import datetime

from django.conf import settings
from django.contrib.staticfiles import finders
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from config.paises_config import get_pais_actual
from servicio_tecnico.concentrado_semanal import comparar_concentrado_con_semana_anterior


# Misma paleta que OOW y Diagnóstico. El rojo suave marca RHITSO
# para que no se confunda con una fila más de ingenieros.
COLOR_NAVY = colors.HexColor('#003366')
COLOR_NAVY_SUAVE = colors.HexColor('#E8EEF5')
COLOR_GRIS_ALT = colors.HexColor('#F2F2F2')
COLOR_GRIS_BORDE = colors.HexColor('#CCCCCC')
COLOR_AMARILLO_BG = colors.HexColor('#FFF2CC')
COLOR_ROJO_BG = colors.HexColor('#FDECEC')
COLOR_ROJO_ALERTA = colors.HexColor('#C00000')
COLOR_BLANCO = colors.white
COLOR_NEGRO = colors.black

DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes']
TIPOS_EQUIPO = ['LENOVO', 'DELL', 'OOW', 'MIS DELL', 'MIS LENOVO']
SITIOS = ['DROP OFF', 'SATELITE']

MARGEN = 15 * mm
MARGEN_INFERIOR = 20 * mm


def _ancho_util():
    """Ancho de la hoja vertical menos los dos márgenes."""
    return letter[0] - (2 * MARGEN)


def _repartir(partes):
    """
    Reparte el ancho útil según una lista de pesos.

    Args:
        partes (list): Pesos relativos de cada columna.

    Returns:
        list: Anchos en puntos que suman el ancho útil.
    """
    ancho = _ancho_util()
    total = sum(partes) or 1
    return [ancho * peso / total for peso in partes]


def _esc(texto):
    """
    Deja un texto seguro para un Paragraph de ReportLab.

    Args:
        texto: Valor a mostrar. None se vuelve cadena vacía.

    Returns:
        str: Texto con &, < y > escapados.
    """
    if texto is None:
        return ''
    return (
        str(texto)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
    )


def _variacion(numero):
    """
    Pone el signo + cuando la semana subió.

    Args:
        numero (int): Esta semana menos la anterior.

    Returns:
        str: Por ejemplo '+2', '0' o '-1'.
    """
    if numero > 0:
        return f'+{numero}'
    return str(numero)


def _crear_estilos():
    """
    Estilos de párrafo, los mismos papeles que en el formato de diagnóstico.

    Returns:
        dict: Estilos con nombre corto para armar el PDF.

    Efectos secundarios:
        Ninguno.
    """
    base = getSampleStyleSheet()
    return {
        'empresa': ParagraphStyle(
            'EmpresaHeader',
            parent=base['Normal'],
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=COLOR_NAVY,
            alignment=TA_RIGHT,
            leading=14,
        ),
        'barra': ParagraphStyle(
            'TituloFormato',
            parent=base['Normal'],
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=COLOR_BLANCO,
            alignment=TA_CENTER,
            leading=12,
        ),
        'label': ParagraphStyle(
            'CeldaLabel',
            parent=base['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NAVY,
            leading=10,
        ),
        'label_centro': ParagraphStyle(
            'CeldaLabelCentro',
            parent=base['Normal'],
            fontName='Helvetica-Bold',
            fontSize=8,
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            leading=10,
        ),
        'valor': ParagraphStyle(
            'CeldaValor',
            parent=base['Normal'],
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            leading=10,
        ),
        'valor_centro': ParagraphStyle(
            'CeldaValorCentro',
            parent=base['Normal'],
            fontName='Helvetica',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_CENTER,
            leading=10,
        ),
        'kpi': ParagraphStyle(
            'KpiValor',
            parent=base['Normal'],
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=COLOR_NAVY,
            alignment=TA_CENTER,
            leading=16,
        ),
        'nota': ParagraphStyle(
            'Nota',
            parent=base['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=8,
            textColor=COLOR_NEGRO,
            alignment=TA_LEFT,
            leading=10,
        ),
        'vacio': ParagraphStyle(
            'Vacio',
            parent=base['Normal'],
            fontName='Helvetica-Oblique',
            fontSize=8,
            textColor=COLOR_ROJO_ALERTA,
            alignment=TA_LEFT,
            leading=10,
        ),
    }


def _barra_seccion(titulo, estilos):
    """
    Barra navy de sección, igual que OOW y Diagnóstico.

    Args:
        titulo (str): Texto blanco centrado.
        estilos (dict): Estilos de _crear_estilos().

    Returns:
        Table: Una fila con fondo navy.
    """
    tabla = Table(
        [[Paragraph(_esc(titulo), estilos['barra'])]],
        colWidths=[_ancho_util()],
    )
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_NAVY),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))
    return tabla


def _obtener_logo():
    """
    Carga el PNG del logo SIC. Si no está, el encabezado sigue sin imagen.

    Returns:
        RLImage | None
    """
    ruta = finders.find('images/logos/logo_sic.png')
    if not ruta or not os.path.exists(ruta):
        static_root = getattr(settings, 'STATIC_ROOT', None)
        if static_root:
            candidato = os.path.join(static_root, 'images', 'logos', 'logo_sic.png')
            ruta = candidato if os.path.exists(candidato) else None
        else:
            ruta = None
    if not ruta:
        return None
    try:
        return RLImage(ruta, width=45 * mm, height=15 * mm, kind='proportional')
    except Exception:
        return None


def _estilo_tabla_datos():
    """
    Comandos comunes: encabezado navy, filas alternadas, borde gris.

    Returns:
        list: Comandos de TableStyle. El que llama agrega la fila de totales.
    """
    return [
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLOR_BLANCO),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [COLOR_BLANCO, COLOR_GRIS_ALT]),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]


def _tabla_ingreso_egreso(datos, totales):
    """
    Tabla de ingreso o de egreso por sitio y tipo de equipo.

    Args:
        datos (dict): {sitio: {tipo: {dia, total, promedio}}}
        totales (dict): Totales de la semana.

    Returns:
        Table: Tabla a todo el ancho de la hoja.

    Efectos secundarios:
        Ninguno.
    """
    encabezados = ['SITIO', 'EQUIPO'] + [d[:3].upper() for d in DIAS_SEMANA] + ['TOTAL', 'PROM']
    filas = [encabezados]
    style_cmds = _estilo_tabla_datos()
    style_cmds += [
        ('FONTNAME', (0, 1), (1, -2), 'Helvetica-Bold'),
        ('ALIGN', (0, 1), (0, -2), 'CENTER'),
        ('ALIGN', (1, 1), (1, -2), 'LEFT'),
        ('ALIGN', (2, 1), (-1, -2), 'CENTER'),
        ('BACKGROUND', (0, 1), (0, -2), COLOR_NAVY_SUAVE),
        ('TEXTCOLOR', (0, 1), (0, -2), COLOR_NAVY),
        ('FONTNAME', (-2, 1), (-2, -2), 'Helvetica-Bold'),
        ('TEXTCOLOR', (-2, 1), (-2, -2), COLOR_NAVY),
    ]

    fila_actual = 1
    for sitio in SITIOS:
        fila_inicio_sitio = fila_actual
        for tipo in TIPOS_EQUIPO:
            tipo_data = datos[sitio][tipo]
            fila = [sitio, tipo]
            for dia in DIAS_SEMANA:
                fila.append(tipo_data.get(dia, 0))
            fila.append(tipo_data.get('total', 0))
            fila.append(tipo_data.get('promedio', 0))
            filas.append(fila)
            fila_actual += 1
        if len(TIPOS_EQUIPO) > 1:
            style_cmds.append(('SPAN', (0, fila_inicio_sitio), (0, fila_actual - 1)))

    fila_totales = ['TOTALES', '']
    for dia in DIAS_SEMANA:
        fila_totales.append(totales.get(dia, 0))
    fila_totales.append(totales.get('total', 0))
    fila_totales.append(totales.get('promedio', 0))
    filas.append(fila_totales)

    idx_total = len(filas) - 1
    style_cmds += [
        ('BACKGROUND', (0, idx_total), (-1, idx_total), COLOR_NAVY_SUAVE),
        ('TEXTCOLOR', (0, idx_total), (-1, idx_total), COLOR_NAVY),
        ('FONTNAME', (0, idx_total), (-1, idx_total), 'Helvetica-Bold'),
        ('ALIGN', (0, idx_total), (-1, idx_total), 'CENTER'),
        ('SPAN', (0, idx_total), (1, idx_total)),
    ]

    # Sitio y equipo un poco más anchos; el resto se reparte parejo.
    tabla = Table(filas, colWidths=_repartir([1.8, 2.4, 1.3, 1.3, 1.3, 1.3, 1.3, 1.5, 1.4]), repeatRows=1)
    tabla.setStyle(TableStyle(style_cmds))
    return tabla


def _tabla_asignacion(asignacion, totales_asignacion):
    """
    Tabla de equipos por ingeniero. El total no incluye RHITSO.

    Args:
        asignacion (list): Filas {nombre, Lunes..Viernes, total}.
        totales_asignacion (dict): Suma por día y total de la semana.

    Returns:
        Table
    """
    encabezados = ['INGENIERO'] + [d[:3].upper() for d in DIAS_SEMANA] + ['TOTAL']
    filas = [encabezados]
    style_cmds = _estilo_tabla_datos()
    if not asignacion:
        # Sin ingenieros no hay filas de datos: -2 apuntaría al encabezado.
        style_cmds = [cmd for cmd in style_cmds if cmd[0] != 'ROWBACKGROUNDS']
    else:
        style_cmds += [
            ('ALIGN', (0, 1), (0, -2), 'LEFT'),
            ('ALIGN', (1, 1), (-1, -2), 'CENTER'),
            ('FONTNAME', (-1, 1), (-1, -2), 'Helvetica-Bold'),
            ('TEXTCOLOR', (-1, 1), (-1, -2), COLOR_NAVY),
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
                ('BACKGROUND', (0, fila_idx), (-1, fila_idx), COLOR_AMARILLO_BG),
                ('FONTNAME', (0, fila_idx), (-1, fila_idx), 'Helvetica-Oblique'),
            ]
        fila_idx += 1

    # El total por día sale de totales_asignacion, que ya excluye RHITSO.
    totales = totales_asignacion or {}
    fila_total = ['TOTAL EQUIPOS INGRESADOS']
    for dia in DIAS_SEMANA:
        fila_total.append(totales.get(dia, 0))
    fila_total.append(totales.get('total', 0))
    filas.append(fila_total)
    idx_total = len(filas) - 1
    style_cmds += [
        ('BACKGROUND', (0, idx_total), (-1, idx_total), COLOR_NAVY_SUAVE),
        ('TEXTCOLOR', (0, idx_total), (-1, idx_total), COLOR_NAVY),
        ('FONTNAME', (0, idx_total), (-1, idx_total), 'Helvetica-Bold'),
        ('ALIGN', (0, idx_total), (-1, idx_total), 'CENTER'),
        ('ALIGN', (0, idx_total), (0, idx_total), 'LEFT'),
    ]

    tabla = Table(filas, colWidths=_repartir([3.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.4]), repeatRows=1)
    tabla.setStyle(TableStyle(style_cmds))
    return tabla


def _tabla_candidatos_rhitso(candidatos_rhitso):
    """
    Conteo por día de candidatos RHITSO. No es un ingeniero más.

    Args:
        candidatos_rhitso (dict): {nombre, Lunes..Viernes, total}

    Returns:
        Table
    """
    fila = candidatos_rhitso or {}
    encabezados = ['CONCEPTO'] + [d[:3].upper() for d in DIAS_SEMANA] + ['TOTAL']
    datos = [fila.get('nombre', 'Candidatos RHITSO')]
    for dia in DIAS_SEMANA:
        datos.append(fila.get(dia, 0))
    datos.append(fila.get('total', 0))
    tabla = Table(
        [encabezados, datos],
        colWidths=_repartir([3.2, 1.2, 1.2, 1.2, 1.2, 1.2, 1.4]),
    )
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_NAVY),
        ('TEXTCOLOR', (0, 0), (-1, 0), COLOR_BLANCO),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 1), (-1, 1), COLOR_ROJO_BG),
        ('TEXTCOLOR', (0, 1), (-1, 1), COLOR_ROJO_ALERTA),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Oblique'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, 1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return tabla


def _bloque_resumen(comparacion, estilos):
    """
    Cuatro cifras de la semana y cómo cambiaron contra la anterior.

    Args:
        comparacion (dict): Salida de comparar_concentrado_con_semana_anterior.
        estilos (dict): Estilos de párrafo.

    Returns:
        list: Barra, tabla y una nota que explica el balance.
    """
    celdas = []
    for titulo, valor, variacion in (
        ('Ingresaron', comparacion['ingresaron'], comparacion['variacion_ingresaron']),
        ('Salieron', comparacion['salieron'], comparacion['variacion_salieron']),
        ('Balance', _variacion(comparacion['balance']), comparacion['variacion_balance']),
        ('Candidatos RHITSO', comparacion['candidatos_rhitso'], comparacion['variacion_rhitso']),
    ):
        # El título dice qué cifra es. El número grande es esta semana.
        # Abajo, la diferencia contra la semana previa.
        texto = (
            f'<font size="8">{_esc(titulo)}</font><br/>'
            f'{_esc(valor)}<br/>'
            f'<font size="7">vs sem. ant. {_esc(_variacion(variacion))}</font>'
        )
        celdas.append(Paragraph(texto, estilos['kpi']))

    tabla = Table([celdas], colWidths=_repartir([1, 1, 1, 1]))
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), COLOR_NAVY_SUAVE),
        ('BOX', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
        ('INNERGRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('BACKGROUND', (3, 0), (3, 0), COLOR_ROJO_BG),
    ]))
    nota = Paragraph(
        'El balance es cuántos equipos entraron de más respecto a los que salieron. '
        'La variación compara esta semana con la anterior. '
        'Los candidatos RHITSO ya van dentro del ingreso: aquí solo se ven aparte.',
        estilos['nota'],
    )
    return [
        _barra_seccion('Resumen de la semana', estilos),
        Spacer(1, 2 * mm),
        tabla,
        Spacer(1, 2 * mm),
        nota,
    ]


def _bloque_lista_rhitso(lista, estilos):
    """
    Cada equipo candidato, con folio, técnico y sucursal.

    Args:
        lista (list): lista_candidatos_rhitso del concentrado.
        estilos (dict): Estilos de párrafo.

    Returns:
        list: Barra, nota y la tabla, o un aviso si no hubo candidatos.
    """
    elementos = [
        _barra_seccion('Equipos candidatos a RHITSO', estilos),
        Spacer(1, 2 * mm),
    ]
    if not lista:
        elementos.append(Paragraph(
            'Esta semana no hubo candidatos RHITSO.',
            estilos['vacio'],
        ))
        return elementos

    elementos.append(Paragraph(
        'Es el mismo equipo que ya tiene un técnico. Esta lista dice cuál es, no suma otro ingreso.',
        estilos['nota'],
    ))
    elementos.append(Spacer(1, 2 * mm))

    filas = [[
        Paragraph('DÍA', estilos['barra']),
        Paragraph('FOLIO', estilos['barra']),
        Paragraph('TÉCNICO', estilos['barra']),
        Paragraph('SUCURSAL', estilos['barra']),
    ]]
    for item in lista:
        filas.append([
            Paragraph(_esc(item.get('dia', '')), estilos['valor_centro']),
            Paragraph(_esc(item.get('folio', '')), estilos['valor']),
            Paragraph(_esc(item.get('tecnico', '')), estilos['valor']),
            Paragraph(_esc(item.get('sucursal', '')), estilos['valor']),
        ])

    tabla = Table(filas, colWidths=_repartir([1.4, 2.2, 2.6, 2.4]), repeatRows=1)
    comandos = [
        ('BACKGROUND', (0, 0), (-1, 0), COLOR_NAVY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [COLOR_ROJO_BG, COLOR_BLANCO]),
    ]
    tabla.setStyle(TableStyle(comandos))
    elementos.append(tabla)
    return elementos


def _bloque_canales(datos, estilos):
    """
    Carry In y Mail In, debajo de la tabla de ingreso.

    Args:
        datos (dict): Concentrado de la semana.
        estilos (dict): Estilos de párrafo.

    Returns:
        Table: Tres pares etiqueta | número.
    """
    pares = [
        ('Carry In – Drop Off', datos.get('carry_in_dropoff', 0)),
        ('Carry In – SIC (Satélite)', datos.get('carry_in_sic', 0)),
        ('Mail In Service (MIS)', datos.get('mail_in_service', 0)),
    ]
    fila = []
    for etiqueta, valor in pares:
        fila.append(Paragraph(_esc(etiqueta), estilos['label_centro']))
        fila.append(Paragraph(_esc(valor), estilos['valor_centro']))
    tabla = Table([fila], colWidths=_repartir([2.2, 0.8, 2.4, 0.8, 2.2, 0.8]))
    tabla.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), COLOR_NAVY_SUAVE),
        ('BACKGROUND', (2, 0), (2, 0), COLOR_NAVY_SUAVE),
        ('BACKGROUND', (4, 0), (4, 0), COLOR_NAVY_SUAVE),
        ('BACKGROUND', (1, 0), (1, 0), COLOR_GRIS_ALT),
        ('BACKGROUND', (3, 0), (3, 0), COLOR_GRIS_ALT),
        ('BACKGROUND', (5, 0), (5, 0), COLOR_GRIS_ALT),
        ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    return tabla


def _construir_encabezado(datos, estilos):
    """
    Logo, razón social, título y la semana con sus fechas.

    Args:
        datos (dict): Concentrado de la semana.
        estilos (dict): Estilos de párrafo.

    Returns:
        list: Flowables del encabezado.
    """
    pais = get_pais_actual()
    empresa = pais.get(
        'empresa_nombre',
        'SIC Comercialización y Servicios de México SC',
    )
    logo = _obtener_logo()
    fila = [[logo or '', Paragraph(_esc(empresa), estilos['empresa'])]]
    cabecera = Table(fila, colWidths=[55 * mm, None])
    cabecera.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 0),
        ('RIGHTPADDING', (0, 0), (0, 0), 0),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))

    lunes = datos.get('lunes')
    viernes = datos.get('viernes')
    if lunes and viernes:
        rango = f'{lunes.strftime("%d/%m/%Y")} — {viernes.strftime("%d/%m/%Y")}'
    else:
        rango = ''
    semana = f'Semana {datos.get("numero_semana", "")} de {datos.get("año", "")}'

    etiqueta = 22 * mm
    ancho = _ancho_util()
    ancho_semana = ancho * 0.42 - etiqueta
    ancho_fechas = ancho * 0.58 - etiqueta
    meta = Table([[
        Paragraph('Semana', estilos['label']),
        Paragraph(_esc(semana), estilos['valor']),
        Paragraph('Fechas', estilos['label']),
        Paragraph(_esc(rango), estilos['valor']),
    ]], colWidths=[etiqueta, ancho_semana, etiqueta, ancho_fechas])
    meta.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), COLOR_NAVY_SUAVE),
        ('BACKGROUND', (2, 0), (2, 0), COLOR_NAVY_SUAVE),
        ('BACKGROUND', (1, 0), (1, 0), COLOR_GRIS_ALT),
        ('BACKGROUND', (3, 0), (3, 0), COLOR_GRIS_ALT),
        ('GRID', (0, 0), (-1, -1), 0.4, COLOR_GRIS_BORDE),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    return [
        cabecera,
        Spacer(1, 2 * mm),
        HRFlowable(width='100%', thickness=1, color=COLOR_GRIS_BORDE),
        Spacer(1, 3 * mm),
        _barra_seccion('CONCENTRADO SEMANAL', estilos),
        Spacer(1, 2 * mm),
        meta,
    ]


def generar_pdf_concentrado(datos, datos_anterior=None):
    """
    Arma el PDF del concentrado en memoria.

    Objetivo de negocio:
        Quien imprime el reporte lee primero cómo estuvo la semana y
        cuáles equipos van a RHITSO. Las tablas por día quedan debajo,
        con el mismo estilo visual que el formato OOW y el de diagnóstico.

    Args:
        datos (dict): Resultado de obtener_concentrado_semanal() de esta semana.
        datos_anterior (dict | None): El mismo cálculo del lunes anterior.
            Si no llega, la variación se calcula contra ceros.

    Returns:
        io.BytesIO: PDF listo para enviar al navegador.

    Efectos secundarios:
        Ninguno en disco ni en la base. Solo llena un buffer en memoria.
    """
    comparacion = comparar_concentrado_con_semana_anterior(datos, datos_anterior)
    estilos = _crear_estilos()
    buffer = io.BytesIO()
    num_semana = datos.get('numero_semana', '')
    año = datos.get('año', '')
    pais = get_pais_actual()
    empresa = pais.get('empresa_nombre', 'SIGMA')

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=MARGEN,
        rightMargin=MARGEN,
        topMargin=MARGEN,
        bottomMargin=MARGEN_INFERIOR,
        title=f'Concentrado semanal - Semana {num_semana} de {año}',
        author=empresa,
        subject='Concentrado semanal CIS',
        creator='SIGMA',
    )

    elementos = []
    elementos += _construir_encabezado(datos, estilos)
    elementos.append(Spacer(1, 4 * mm))
    elementos += _bloque_resumen(comparacion, estilos)
    elementos.append(Spacer(1, 4 * mm))
    elementos += _bloque_lista_rhitso(datos.get('lista_candidatos_rhitso') or [], estilos)
    elementos.append(Spacer(1, 4 * mm))

    elementos.append(_barra_seccion('Ingreso de equipos en CIS', estilos))
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(_tabla_ingreso_egreso(datos['ingreso'], datos['totales_ingreso']))
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(_bloque_canales(datos, estilos))
    elementos.append(Spacer(1, 4 * mm))

    elementos.append(_barra_seccion('Asignación de equipos a ingeniería', estilos))
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(_tabla_asignacion(
        datos.get('asignacion', []),
        datos.get('totales_asignacion', {}),
    ))
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(Paragraph(
        'Estos conteos ya están en la fila de cada técnico. No se suman al total de arriba.',
        estilos['nota'],
    ))
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(_tabla_candidatos_rhitso(datos.get('candidatos_rhitso', {})))
    elementos.append(Spacer(1, 4 * mm))

    elementos.append(_barra_seccion('Egreso de equipos en CIS', estilos))
    elementos.append(Spacer(1, 2 * mm))
    elementos.append(_tabla_ingreso_egreso(datos['egreso'], datos['totales_egreso']))

    def _dibujar_pie(canvas, documento):
        """
        Pie en cada hoja: semana a la izquierda, página a la derecha.

        Efectos secundarios:
            Dibuja en el margen inferior. No tapa las tablas porque
            bottomMargin ya reservó ese espacio.
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
        canvas.drawString(x_izq, y_pie, f'Concentrado semanal · Semana {num_semana} de {año}')
        canvas.drawRightString(x_der, y_pie, f'Página {documento.page}')
        canvas.restoreState()

    # La fecha de generación va al cierre del cuerpo, no en el pie,
    # para que el pie se quede igual que en OOW (identificador + página).
    elementos.append(Spacer(1, 4 * mm))
    elementos.append(Paragraph(
        f'Generado el {datetime.now().strftime("%d/%m/%Y %H:%M")}',
        estilos['nota'],
    ))

    doc.build(elementos, onFirstPage=_dibujar_pie, onLaterPages=_dibujar_pie)
    buffer.seek(0)
    return buffer
