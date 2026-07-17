"""
Vistas HTTP del Concentrado Semanal de CIS (Fase 2 modularización).

EXPLICACIÓN PARA PRINCIPIANTES:
La lógica pesada (cálculos, tablas) vive en concentrado_semanal.py,
excel_exporters_concentrado.py y pdf_concentrado.py.
Estas vistas solo leen parámetros GET, llaman esos módulos y
devuelven HTML / Excel / PDF.

urls.py sigue usando views.concentrado_semanal porque views.py reexporta.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from inventario.models import Sucursal

from .decorators import permission_required_with_message


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def concentrado_semanal(request):
    """
    Página principal del Concentrado Semanal de CIS.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista genera el reporte semanal de ingresos, asignaciones y egresos
    de equipos en el CIS. El usuario puede navegar entre semanas usando el
    parámetro GET 'semana' (formato ISO: 'YYYY-WNN', ej: '2025-W18').

    También calcula:
      - Los gráficos de tendencia anual de ingresos y egresos por semana
      - La lista de sucursales para el filtro

    Parámetros GET:
        semana (str): Semana ISO seleccionada, ej: '2025-W18'. Default: semana actual.
        sucursal_id (int): Filtrar por sucursal. Default: todas.

    Returns:
        HttpResponse: Template con el concentrado completo
    """
    import json as _json
    import plotly.graph_objects as go
    import plotly.io as pio
    from datetime import date
    from .concentrado_semanal import (
        obtener_semana_actual,
        lunes_desde_numero_semana,
        obtener_concentrado_semanal,
        obtener_tendencia_semanal,
        DIAS_SEMANA,
        SITIOS,
        TIPOS_EQUIPO,
    )

    # ------------------------------------------------------------------
    # Leer parámetros GET
    # ------------------------------------------------------------------
    semana_param = request.GET.get('semana', '')
    sucursal_param = request.GET.get('sucursal_id', None)

    # sucursal_id puede ser:
    #   - None / '' → todas las sucursales
    #   - 'grupo_cis'     → Drop Off + Satélite (se resuelve a lista de IDs más abajo)
    #   - 'grupo_foranea' → MTY + GDL (ídem)
    #   - Un número entero → sucursal individual
    sucursal_id = None          # valor que se pasa a las funciones de negocio (int o None)
    sucursal_ids_grupo = None   # lista de IDs cuando es un grupo

    if sucursal_param in ('grupo_cis', 'grupo_foranea'):
        # Se resuelve después de cargar las sucursales (ver más abajo)
        sucursal_id = None
    elif sucursal_param:
        try:
            sucursal_id = int(sucursal_param)
        except ValueError:
            sucursal_id = None

    # ------------------------------------------------------------------
    # Determinar la semana seleccionada
    # ------------------------------------------------------------------
    lunes_seleccionado = obtener_semana_actual()

    if semana_param:
        # Formato esperado: "2025-W18"
        try:
            partes = semana_param.split('-W')
            año_param = int(partes[0])
            num_semana_param = int(partes[1])
            lunes_seleccionado = lunes_desde_numero_semana(año_param, num_semana_param)
        except (ValueError, IndexError):
            lunes_seleccionado = obtener_semana_actual()

    # ------------------------------------------------------------------
    # Lista de sucursales para el filtro + resolución de grupos
    # (debe hacerse ANTES de llamar a las funciones del concentrado)
    # ------------------------------------------------------------------
    sucursales = Sucursal.objects.filter(activa=True).order_by('nombre')

    # Clasificamos cada sucursal en un grupo según su nombre.
    # Grupo "CIS"     → nombre contiene 'drop' o 'satelit'
    # Grupo "Foránea" → cualquier otra (MTY, GDL, etc.)
    grupo_cis_ids = []
    grupo_foranea_ids = []
    for suc in sucursales:
        nombre_lower = suc.nombre.lower()
        if 'drop' in nombre_lower or 'satelit' in nombre_lower:
            grupo_cis_ids.append(suc.id)
        else:
            grupo_foranea_ids.append(suc.id)

    # Resolver grupos: convertir 'grupo_cis'/'grupo_foranea' a lista de IDs
    if sucursal_param == 'grupo_cis':
        sucursal_ids_grupo = grupo_cis_ids
    elif sucursal_param == 'grupo_foranea':
        sucursal_ids_grupo = grupo_foranea_ids

    # Estructura de grupos para renderizar optgroup en el template
    grupos_sucursales = []
    if grupo_cis_ids:
        grupos_sucursales.append({
            'label': 'CIS (Drop Off + Satélite)',
            'value': 'grupo_cis',
        })
    if grupo_foranea_ids:
        grupos_sucursales.append({
            'label': 'Foráneas (MTY + GDL)',
            'value': 'grupo_foranea',
        })

    # ------------------------------------------------------------------
    # Calcular datos del concentrado
    # ------------------------------------------------------------------
    datos = obtener_concentrado_semanal(
        lunes_seleccionado,
        sucursal_id=sucursal_id,
        sucursal_ids=sucursal_ids_grupo,
    )

    # ------------------------------------------------------------------
    # Calcular semana anterior y siguiente para navegación
    # ------------------------------------------------------------------
    from datetime import timedelta
    lunes_anterior = lunes_seleccionado - timedelta(days=7)
    lunes_siguiente = lunes_seleccionado + timedelta(days=7)

    def _formatear_semana_iso(lunes):
        num = lunes.isocalendar()[1]
        año = lunes.year
        return f"{año}-W{num:02d}"

    semana_anterior_iso = _formatear_semana_iso(lunes_anterior)
    semana_siguiente_iso = _formatear_semana_iso(lunes_siguiente)
    semana_actual_iso = _formatear_semana_iso(lunes_seleccionado)

    # ------------------------------------------------------------------
    # Gráficos de tendencia anual (Plotly)
    # ------------------------------------------------------------------
    año_actual = lunes_seleccionado.year
    tendencia = obtener_tendencia_semanal(
        año_actual,
        sucursal_id=sucursal_id,
        sucursal_ids=sucursal_ids_grupo,
    )

    # Gráfico de Ingresos por semana
    fig_ingresos = go.Figure()
    fig_ingresos.add_trace(go.Bar(
        x=tendencia['etiquetas'],
        y=tendencia['ingresos'],
        name='Ingresos',
        marker_color='#0d6efd',
        hovertemplate='<b>%{x}</b><br>Ingresos: %{y}<extra></extra>',
    ))
    fig_ingresos.add_trace(go.Scatter(
        x=tendencia['etiquetas'],
        y=tendencia['ingresos'],
        name='Tendencia',
        mode='lines+markers',
        line=dict(color='#0a58ca', width=2),
        marker=dict(size=5),
        hoverinfo='skip',
    ))
    fig_ingresos.update_layout(
        title=dict(text=f'Ingresos de Equipos por Semana — {año_actual}', font=dict(size=14)),
        xaxis_title='Semana',
        yaxis_title='Equipos Ingresados',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=40, r=20, t=60, b=40),
        height=320,
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=False, tickangle=-45 if len(tendencia['etiquetas']) > 30 else 0),
        yaxis=dict(showgrid=True, gridcolor='#f0f0f0'),
    )
    # Resaltar la semana seleccionada
    semana_label_actual = f"S{datos['numero_semana']}"
    if semana_label_actual in tendencia['etiquetas']:
        idx = tendencia['etiquetas'].index(semana_label_actual)
        fig_ingresos.add_vline(
            x=idx,
            line_dash='dash',
            line_color='#dc3545',
            annotation_text='Semana actual',
            annotation_position='top right',
            annotation_font_size=10,
        )

    grafico_ingresos_html = pio.to_html(
        fig_ingresos,
        full_html=False,
        include_plotlyjs=False,
        config={'responsive': True, 'displayModeBar': False},
    )

    # Gráfico de Egresos por semana
    fig_egresos = go.Figure()
    fig_egresos.add_trace(go.Bar(
        x=tendencia['etiquetas'],
        y=tendencia['egresos'],
        name='Egresos',
        marker_color='#198754',
        hovertemplate='<b>%{x}</b><br>Egresos: %{y}<extra></extra>',
    ))
    fig_egresos.add_trace(go.Scatter(
        x=tendencia['etiquetas'],
        y=tendencia['egresos'],
        name='Tendencia',
        mode='lines+markers',
        line=dict(color='#146c43', width=2),
        marker=dict(size=5),
        hoverinfo='skip',
    ))
    fig_egresos.update_layout(
        title=dict(text=f'Egresos de Equipos por Semana — {año_actual}', font=dict(size=14)),
        xaxis_title='Semana',
        yaxis_title='Equipos Egresados',
        hovermode='x unified',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        margin=dict(l=40, r=20, t=60, b=40),
        height=320,
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis=dict(showgrid=False, tickangle=-45 if len(tendencia['etiquetas']) > 30 else 0),
        yaxis=dict(showgrid=True, gridcolor='#f0f0f0'),
    )
    if semana_label_actual in tendencia['etiquetas']:
        fig_egresos.add_vline(
            x=idx,
            line_dash='dash',
            line_color='#dc3545',
            annotation_text='Semana actual',
            annotation_position='top right',
            annotation_font_size=10,
        )

    grafico_egresos_html = pio.to_html(
        fig_egresos,
        full_html=False,
        include_plotlyjs=False,
        config={'responsive': True, 'displayModeBar': False},
    )

    # ------------------------------------------------------------------
    # Construir el contexto para el template
    # ------------------------------------------------------------------
    context = {
        # Datos del concentrado
        **datos,

        # Navegación
        'semana_actual_iso': semana_actual_iso,
        'semana_anterior_iso': semana_anterior_iso,
        'semana_siguiente_iso': semana_siguiente_iso,
        'sucursal_id_seleccionada': sucursal_param,  # puede ser int, 'grupo_cis', 'grupo_foranea' o None
        'sucursales': sucursales,
        'grupos_sucursales': grupos_sucursales,

        # Gráficos Plotly
        'grafico_ingresos_html': grafico_ingresos_html,
        'grafico_egresos_html': grafico_egresos_html,

        # Constantes para el template
        'dias_semana': DIAS_SEMANA,
        'sitios': SITIOS,
        'tipos_equipo': TIPOS_EQUIPO,

        # Metadatos de la página
        'page_title': (
            f'Concentrado Semanal — Semana {datos["numero_semana"]}, {datos["año"]}'
        ),
    }

    return render(request, 'servicio_tecnico/concentrado_semanal.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_concentrado_excel(request):
    """
    Exporta el concentrado semanal a un archivo Excel (.xlsx) con 4 hojas:
      1. Concentrado Semanal (datos de la semana seleccionada)
      2. Reporte Trimestral (Q1-Q4 del año)
      3. Gráfico de Ingresos por semana
      4. Gráfico de Egresos por semana

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista no renderiza una página HTML. En cambio, genera un archivo Excel
    y lo envía directamente al navegador para descargarlo.
    Usa la misma lógica de 'concentrado_semanal' para obtener los datos,
    y luego llama a las funciones del módulo excel_exporters para crear el Excel.

    Parámetros GET:
        semana (str): Semana ISO (ej: '2025-W18')
        sucursal_id (int): Filtrar por sucursal
        año (int): Año para el reporte trimestral (default: año de la semana)

    Returns:
        HttpResponse: Archivo Excel como descarga
    """
    import openpyxl
    from django.http import HttpResponse
    from .concentrado_semanal import (
        obtener_semana_actual,
        lunes_desde_numero_semana,
        obtener_concentrado_semanal,
        obtener_reporte_trimestral,
        obtener_tendencia_semanal,
        obtener_reporte_mensual,
    )
    from .excel_exporters_concentrado import generar_excel_concentrado

    # Leer parámetros
    semana_param = request.GET.get('semana', '')
    sucursal_id = request.GET.get('sucursal_id', None)
    if sucursal_id:
        try:
            sucursal_id = int(sucursal_id)
        except ValueError:
            sucursal_id = None

    lunes_seleccionado = obtener_semana_actual()
    if semana_param:
        try:
            partes = semana_param.split('-W')
            lunes_seleccionado = lunes_desde_numero_semana(int(partes[0]), int(partes[1]))
        except (ValueError, IndexError):
            lunes_seleccionado = obtener_semana_actual()

    año = lunes_seleccionado.year

    # Obtener datos
    datos_semana = obtener_concentrado_semanal(lunes_seleccionado, sucursal_id=sucursal_id)
    datos_trimestral = obtener_reporte_trimestral(año, sucursal_id=sucursal_id)
    datos_tendencia = obtener_tendencia_semanal(año, sucursal_id=sucursal_id)
    datos_mensual = obtener_reporte_mensual(año, sucursal_id=sucursal_id)

    # Generar el archivo Excel
    wb = generar_excel_concentrado(datos_semana, datos_trimestral, datos_tendencia, datos_mensual)

    # Preparar respuesta HTTP para descarga
    num_semana = datos_semana['numero_semana']
    filename = f'Concentrado_Semanal_S{num_semana:02d}_{año}.xlsx'

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)

    return response


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_concentrado_pdf(request):
    """
    Exporta el concentrado semanal a un PDF con las 3 tablas del reporte.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Usa la librería ReportLab para generar un PDF en orientación horizontal
    (landscape) con las 3 tablas del concentrado semanal:
      1. Ingreso de Equipos
      2. Asignación a Ingeniería
      3. Egreso de Equipos

    Parámetros GET:
        semana (str): Semana ISO (ej: '2025-W18')
        sucursal_id (int): Filtrar por sucursal

    Returns:
        HttpResponse: Archivo PDF como descarga
    """
    from .concentrado_semanal import (
        obtener_semana_actual,
        lunes_desde_numero_semana,
        obtener_concentrado_semanal,
        DIAS_SEMANA,
        SITIOS,
        TIPOS_EQUIPO,
    )
    from .pdf_concentrado import generar_pdf_concentrado

    # Leer parámetros
    semana_param = request.GET.get('semana', '')
    sucursal_id = request.GET.get('sucursal_id', None)
    if sucursal_id:
        try:
            sucursal_id = int(sucursal_id)
        except ValueError:
            sucursal_id = None

    lunes_seleccionado = obtener_semana_actual()
    if semana_param:
        try:
            partes = semana_param.split('-W')
            lunes_seleccionado = lunes_desde_numero_semana(int(partes[0]), int(partes[1]))
        except (ValueError, IndexError):
            lunes_seleccionado = obtener_semana_actual()

    # Obtener datos
    datos = obtener_concentrado_semanal(lunes_seleccionado, sucursal_id=sucursal_id)

    # Generar PDF
    pdf_buffer = generar_pdf_concentrado(datos)

    # Preparar respuesta
    num_semana = datos['numero_semana']
    año = datos['año']
    filename = f'Concentrado_Semanal_S{num_semana:02d}_{año}.pdf'

    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response

