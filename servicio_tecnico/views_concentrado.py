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


def resolver_filtros_concentrado(request):
    """
    Lee la semana y la sucursal una sola vez para página, Excel y PDF.

    Objetivo de negocio:
        Los tres salidas deben ver el mismo corte. Si en pantalla elegiste
        CIS o Foráneas, el archivo no puede salir con todas las sucursales.

    Args:
        request: Petición con semana (YYYY-WNN) y sucursal_id.
            En GET los leen la página, el Excel y el PDF.
            En POST los lee el envío por correo (vienen del modal).
            sucursal_id puede ser un número, 'grupo_cis', 'grupo_foranea' o vacío.

    Returns:
        dict:
            lunes (date), sucursal_id (int o None), sucursal_ids (lista o None),
            sucursal_param (el valor crudo del GET, para remarcar el filtro),
            sucursales (queryset activas), grupos_sucursales (opciones del select).

    Efectos secundarios:
        Consulta las sucursales activas para armar CIS y foráneas.
    """
    from .concentrado_semanal import (
        lunes_desde_numero_semana,
        obtener_semana_actual,
    )

    # El modal manda la semana por POST. El resto de la página usa GET.
    origen = request.POST if request.method == 'POST' else request.GET
    semana_param = origen.get('semana', '')
    sucursal_param = origen.get('sucursal_id') or None

    lunes = obtener_semana_actual()
    if semana_param:
        try:
            año_param, num_semana_param = semana_param.split('-W')
            lunes = lunes_desde_numero_semana(int(año_param), int(num_semana_param))
        except (ValueError, IndexError):
            lunes = obtener_semana_actual()

    sucursales = Sucursal.objects.filter(activa=True).order_by('nombre')
    grupo_cis_ids = []
    grupo_foranea_ids = []
    for sucursal in sucursales:
        nombre = sucursal.nombre.lower()
        if 'drop' in nombre or 'satelit' in nombre:
            grupo_cis_ids.append(sucursal.id)
        else:
            grupo_foranea_ids.append(sucursal.id)

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

    sucursal_id = None
    sucursal_ids = None
    if sucursal_param == 'grupo_cis':
        sucursal_ids = grupo_cis_ids
    elif sucursal_param == 'grupo_foranea':
        sucursal_ids = grupo_foranea_ids
    elif sucursal_param:
        try:
            sucursal_id = int(sucursal_param)
        except ValueError:
            sucursal_id = None
            sucursal_param = None

    return {
        'lunes': lunes,
        'sucursal_id': sucursal_id,
        'sucursal_ids': sucursal_ids,
        'sucursal_param': sucursal_param,
        'sucursales': sucursales,
        'grupos_sucursales': grupos_sucursales,
    }


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
    from .concentrado_semanal import (
        obtener_concentrado_semanal,
        obtener_tendencia_semanal,
        DIAS_SEMANA,
        SITIOS,
        TIPOS_EQUIPO,
    )
    from .services.concentrado_correo import destinatarios_concentrado

    # Semana y sucursal: la misma función que usan el Excel y el PDF.
    filtros = resolver_filtros_concentrado(request)
    lunes_seleccionado = filtros['lunes']
    sucursal_id = filtros['sucursal_id']
    sucursal_ids_grupo = filtros['sucursal_ids']
    sucursal_param = filtros['sucursal_param']
    sucursales = filtros['sucursales']
    grupos_sucursales = filtros['grupos_sucursales']

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
        # El modal de correo abre con estos contactos ya marcados.
        'destinatarios_correo': destinatarios_concentrado(),
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
        obtener_concentrado_semanal,
        obtener_reporte_trimestral,
        obtener_tendencia_semanal,
        obtener_reporte_mensual,
    )
    from .excel_exporters_concentrado import generar_excel_concentrado

    filtros = resolver_filtros_concentrado(request)
    lunes_seleccionado = filtros['lunes']
    sucursal_id = filtros['sucursal_id']
    sucursal_ids = filtros['sucursal_ids']
    año = lunes_seleccionado.year

    datos_semana = obtener_concentrado_semanal(
        lunes_seleccionado,
        sucursal_id=sucursal_id,
        sucursal_ids=sucursal_ids,
    )
    datos_trimestral = obtener_reporte_trimestral(
        año,
        sucursal_id=sucursal_id,
        sucursal_ids=sucursal_ids,
    )
    datos_tendencia = obtener_tendencia_semanal(
        año,
        sucursal_id=sucursal_id,
        sucursal_ids=sucursal_ids,
    )
    datos_mensual = obtener_reporte_mensual(
        año,
        sucursal_id=sucursal_id,
        sucursal_ids=sucursal_ids,
    )

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
    Exporta el concentrado semanal a un PDF con resumen y tablas.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El PDF usa el mismo diseño que los formatos OOW y Diagnóstico
    (logo, barras navy, hoja vertical). Arriba va el resumen contra
    la semana anterior y la lista de equipos RHITSO. Debajo, las tablas.

    El filtro de sucursal respeta también los grupos CIS y Foráneas,
    igual que la página. Antes un grupo se ignoraba y el PDF salía de todo.

    Parámetros GET:
        semana (str): Semana ISO (ej: '2025-W18')
        sucursal_id (int | 'grupo_cis' | 'grupo_foranea'): Filtro de sucursal

    Returns:
        HttpResponse: Archivo PDF como descarga

    Efectos secundarios:
        Ninguno en disco. Lee órdenes de esta semana y de la anterior.
    """
    from datetime import timedelta

    from .concentrado_semanal import obtener_concentrado_semanal
    from .pdf_concentrado import generar_pdf_concentrado

    filtros = resolver_filtros_concentrado(request)
    lunes_seleccionado = filtros['lunes']
    sucursal_id = filtros['sucursal_id']
    sucursal_ids = filtros['sucursal_ids']

    datos = obtener_concentrado_semanal(
        lunes_seleccionado,
        sucursal_id=sucursal_id,
        sucursal_ids=sucursal_ids,
    )
    # La variación del resumen necesita la misma selección, siete días antes.
    datos_anterior = obtener_concentrado_semanal(
        lunes_seleccionado - timedelta(days=7),
        sucursal_id=sucursal_id,
        sucursal_ids=sucursal_ids,
    )

    pdf_buffer = generar_pdf_concentrado(datos, datos_anterior)

    num_semana = datos['numero_semana']
    año = datos['año']
    filename = f'Concentrado_Semanal_S{num_semana:02d}_{año}.pdf'

    response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def compartir_concentrado_semanal(request):
    """
    Encola el correo del concentrado que se está viendo en pantalla.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El botón «Compartir por correo» no envía nada: abre un modal con
    los contactos ya marcados. Este POST es el botón «Enviar» de ese
    modal. Solo acepta correos de esa lista. El Excel y el PDF los
    arma la tarea Celery, para no dejar esperando al navegador.

    Parámetros POST:
        semana (str): Semana ISO, la misma del filtro.
        sucursal_id (str): Sucursal o grupo, si hay filtro.
        destinatarios (list): Correos que siguieron marcados.

    Returns:
        Redirect a la misma semana del concentrado, con un mensaje.

    Efectos secundarios:
        Encola enviar_concentrado_semanal_task con el país actual.
        No envía SMTP en esta petición.
    """
    from urllib.parse import urlencode

    from django.contrib import messages
    from django.shortcuts import redirect
    from django.urls import reverse

    from config.paises_config import get_pais_actual

    from .services.concentrado_correo import (
        describir_alcance,
        filtrar_destinatarios_elegidos,
    )
    from .tasks_concentrado import enviar_concentrado_semanal_task

    if request.method != 'POST':
        return redirect('servicio_tecnico:concentrado_semanal')

    filtros = resolver_filtros_concentrado(request)
    lunes = filtros['lunes']
    iso = lunes.isocalendar()
    semana_iso = f'{iso.year}-W{iso.week:02d}'
    consulta = {'semana': semana_iso}
    if filtros['sucursal_param']:
        consulta['sucursal_id'] = filtros['sucursal_param']
    destino = (
        reverse('servicio_tecnico:concentrado_semanal')
        + '?'
        + urlencode(consulta)
    )

    elegidos = filtrar_destinatarios_elegidos(request.POST.getlist('destinatarios'))
    if not elegidos:
        messages.warning(
            request,
            'No se envió el concentrado: no quedó ningún contacto marcado.',
        )
        return redirect(destino)

    # El worker lee db_alias antes de tocar órdenes. Sin eso cae en México.
    enviar_concentrado_semanal_task.delay(
        lunes_iso=lunes.isoformat(),
        destinatarios=elegidos,
        sucursal_id=filtros['sucursal_id'],
        sucursal_ids=filtros['sucursal_ids'],
        alcance=describir_alcance(filtros),
        db_alias=get_pais_actual()['db_alias'],
    )
    messages.success(
        request,
        f'Se programó el envío del concentrado para {len(elegidos)} contacto(s). '
        'El Excel y el PDF salen en unos momentos.',
    )
    return redirect(destino)

