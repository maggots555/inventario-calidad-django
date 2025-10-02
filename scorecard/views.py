"""
Vistas para el sistema de Score Card
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from .models import Incidencia, CategoriaIncidencia, ComponenteEquipo, EvidenciaIncidencia
from .forms import IncidenciaForm, EvidenciaIncidenciaForm
from .emails import enviar_notificacion_incidencia, obtener_destinatarios_disponibles
from inventario.models import Empleado, Sucursal
from datetime import datetime, timedelta
from collections import defaultdict
import json


def dashboard(request):
    """
    Dashboard principal con KPIs y gráficos
    """
    # Obtener estadísticas
    total_incidencias = Incidencia.objects.count()
    incidencias_abiertas = Incidencia.objects.filter(estado='abierta').count()
    incidencias_criticas = Incidencia.objects.filter(grado_severidad='critico').count()
    
    # Contexto para el template
    context = {
        'total_incidencias': total_incidencias,
        'incidencias_abiertas': incidencias_abiertas,
        'incidencias_criticas': incidencias_criticas,
    }
    
    return render(request, 'scorecard/dashboard.html', context)


def lista_incidencias(request):
    """
    Lista todas las incidencias con filtros
    """
    incidencias = Incidencia.objects.all().select_related(
        'sucursal',
        'tecnico_responsable',
        'inspector_calidad',
        'tipo_incidencia'
    )
    
    context = {
        'incidencias': incidencias,
    }
    
    return render(request, 'scorecard/lista_incidencias.html', context)


def detalle_incidencia(request, incidencia_id):
    """
    Detalle completo de una incidencia
    """
    incidencia = get_object_or_404(
        Incidencia.objects.select_related(
            'sucursal',
            'tecnico_responsable',
            'inspector_calidad',
            'tipo_incidencia',
            'componente_afectado'
        ),
        id=incidencia_id
    )
    
    # Obtener evidencias
    evidencias = incidencia.evidencias.all()
    
    # Obtener historial de notificaciones enviadas (ordenadas por más reciente)
    from .models import NotificacionIncidencia
    notificaciones_enviadas = NotificacionIncidencia.objects.filter(
        incidencia=incidencia
    ).order_by('-fecha_envio')
    
    context = {
        'incidencia': incidencia,
        'evidencias': evidencias,
        'notificaciones_enviadas': notificaciones_enviadas,
    }
    
    return render(request, 'scorecard/detalle_incidencia.html', context)


def crear_incidencia(request):
    """
    Crear una nueva incidencia con formulario completo
    """
    if request.method == 'POST':
        form = IncidenciaForm(request.POST)
        
        if form.is_valid():
            incidencia = form.save(commit=False)
            
            # Auto-completar el área del técnico desde el empleado seleccionado
            tecnico = form.cleaned_data['tecnico_responsable']
            if tecnico and tecnico.area:
                incidencia.area_tecnico = tecnico.area
            
            incidencia.save()
            
            # Manejar las imágenes subidas
            imagenes = request.FILES.getlist('evidencias')
            inspector = form.cleaned_data['inspector_calidad']
            
            for imagen in imagenes:
                EvidenciaIncidencia.objects.create(
                    incidencia=incidencia,
                    imagen=imagen,
                    descripcion='',
                    subido_por=inspector
                )
            
            messages.success(
                request,
                f'Incidencia {incidencia.folio} registrada exitosamente.'
            )
            return redirect('scorecard:detalle_incidencia', incidencia_id=incidencia.id)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = IncidenciaForm()
    
    # Obtener datos para autocompletado
    marcas_comunes = ['HP', 'Dell', 'Lenovo', 'Acer', 'ASUS', 'Toshiba', 'Apple', 'MSI']
    
    context = {
        'form': form,
        'marcas_comunes': marcas_comunes,
    }
    
    return render(request, 'scorecard/form_incidencia.html', context)


def editar_incidencia(request, incidencia_id):
    """
    Editar una incidencia existente
    """
    incidencia = get_object_or_404(Incidencia, id=incidencia_id)
    
    if request.method == 'POST':
        form = IncidenciaForm(request.POST, instance=incidencia)
        
        if form.is_valid():
            incidencia = form.save(commit=False)
            
            # Auto-completar el área del técnico desde el empleado seleccionado
            tecnico = form.cleaned_data['tecnico_responsable']
            if tecnico and tecnico.area:
                incidencia.area_tecnico = tecnico.area
            
            incidencia.save()
            
            # Manejar nuevas imágenes si se suben
            imagenes = request.FILES.getlist('evidencias')
            inspector = form.cleaned_data['inspector_calidad']
            
            for imagen in imagenes:
                EvidenciaIncidencia.objects.create(
                    incidencia=incidencia,
                    imagen=imagen,
                    descripcion='',
                    subido_por=inspector
                )
            
            messages.success(
                request,
                f'Incidencia {incidencia.folio} actualizada exitosamente.'
            )
            return redirect('scorecard:detalle_incidencia', incidencia_id=incidencia.id)
        else:
            messages.error(request, 'Por favor corrige los errores en el formulario.')
    else:
        form = IncidenciaForm(instance=incidencia)
    
    # Obtener evidencias existentes
    evidencias = incidencia.evidencias.all()
    
    # Obtener datos para autocompletado
    marcas_comunes = ['HP', 'Dell', 'Lenovo', 'Acer', 'ASUS', 'Toshiba', 'Apple', 'MSI']
    
    context = {
        'form': form,
        'incidencia': incidencia,
        'evidencias': evidencias,
        'marcas_comunes': marcas_comunes,
        'editando': True,
    }
    
    return render(request, 'scorecard/form_incidencia.html', context)


def eliminar_incidencia(request, incidencia_id):
    """
    Eliminar una incidencia
    """
    incidencia = get_object_or_404(Incidencia, id=incidencia_id)
    
    if request.method == 'POST':
        folio = incidencia.folio
        incidencia.delete()
        messages.success(request, f'Incidencia {folio} eliminada exitosamente.')
        return redirect('scorecard:lista_incidencias')
    
    return render(request, 'scorecard/confirmar_eliminacion.html', {'incidencia': incidencia})


def reportes(request):
    """
    Página de reportes y análisis
    """
    return render(request, 'scorecard/reportes.html')


def lista_categorias(request):
    """
    Lista de categorías de incidencias
    """
    categorias = CategoriaIncidencia.objects.all()
    return render(request, 'scorecard/lista_categorias.html', {'categorias': categorias})


def lista_componentes(request):
    """
    Lista de componentes de equipos
    """
    componentes = ComponenteEquipo.objects.all()
    return render(request, 'scorecard/lista_componentes.html', {'componentes': componentes})


# APIs para JavaScript
def api_empleado_data(request, empleado_id):
    """
    API para obtener datos de un empleado (para autocompletar)
    """
    try:
        empleado = Empleado.objects.get(id=empleado_id)
        data = {
            'success': True,
            'empleado': {
                'id': empleado.id,
                'nombre': empleado.nombre_completo,
                'area': empleado.area,
                'cargo': empleado.cargo,
                'email': empleado.email or '',
                'sucursal_id': empleado.sucursal.id if empleado.sucursal else None,
                'sucursal_nombre': empleado.sucursal.nombre if empleado.sucursal else '',
            }
        }
    except Empleado.DoesNotExist:
        data = {'success': False, 'error': 'Empleado no encontrado'}
    
    return JsonResponse(data)


def api_buscar_reincidencias(request):
    """
    API para buscar incidencias previas por número de serie
    """
    numero_serie = request.GET.get('numero_serie', '').strip().upper()
    
    if not numero_serie:
        return JsonResponse({'success': False, 'error': 'Número de serie requerido'})
    
    # Buscar incidencias previas con el mismo número de serie
    incidencias_previas = Incidencia.objects.filter(
        numero_serie__iexact=numero_serie
    ).order_by('-fecha_deteccion')[:5]  # Últimas 5
    
    data = {
        'success': True,
        'count': incidencias_previas.count(),
        'incidencias': []
    }
    
    for inc in incidencias_previas:
        data['incidencias'].append({
            'id': inc.id,
            'folio': inc.folio,
            'fecha': inc.fecha_deteccion.strftime('%d/%m/%Y'),
            'tipo_equipo': inc.get_tipo_equipo_display(),
            'marca': inc.marca,
            'tecnico': inc.tecnico_responsable.nombre_completo,
            'categoria': inc.tipo_incidencia.nombre,
            'estado': inc.get_estado_display(),
            'severidad': inc.get_grado_severidad_display(),
        })
    
    return JsonResponse(data)


def api_componentes_por_tipo(request):
    """
    API para obtener componentes filtrados por tipo de equipo
    """
    tipo_equipo = request.GET.get('tipo', 'todos')
    
    componentes = ComponenteEquipo.objects.filter(
        Q(tipo_equipo=tipo_equipo) | Q(tipo_equipo='todos'),
        activo=True
    ).order_by('nombre')
    
    data = {
        'success': True,
        'componentes': [
            {
                'id': comp.id,
                'nombre': comp.nombre,
                'tipo': comp.get_tipo_equipo_display()
            }
            for comp in componentes
        ]
    }
    
    return JsonResponse(data)


# === APIs para Gráficos y Reportes (Fase 3) ===

def api_datos_dashboard(request):
    """
    API que proporciona todos los datos para gráficos del dashboard
    Retorna: tendencias, distribuciones, rankings, etc.
    """
    # 1. Tendencia mensual (últimos 6 meses)
    hoy = timezone.now()
    hace_6_meses = hoy - timedelta(days=180)
    
    incidencias_recientes = Incidencia.objects.filter(
        fecha_deteccion__gte=hace_6_meses
    )
    
    # Agrupar por mes
    meses_data = defaultdict(int)
    for inc in incidencias_recientes:
        mes_key = inc.fecha_deteccion.strftime('%Y-%m')
        meses_data[mes_key] += 1
    
    # Ordenar por fecha
    meses_ordenados = sorted(meses_data.items())
    
    tendencia_mensual = {
        'labels': [datetime.strptime(mes, '%Y-%m').strftime('%b %Y') for mes, _ in meses_ordenados],
        'data': [count for _, count in meses_ordenados]
    }
    
    # 2. Distribución por severidad
    severidad_counts = Incidencia.objects.values('grado_severidad').annotate(
        count=Count('id')
    ).order_by('grado_severidad')
    
    severidad_labels = {
        'critico': 'Crítico',
        'alto': 'Alto',
        'medio': 'Medio',
        'bajo': 'Bajo'
    }
    
    severidad_colors = {
        'critico': '#dc3545',
        'alto': '#fd7e14',
        'medio': '#ffc107',
        'bajo': '#28a745'
    }
    
    distribucion_severidad = {
        'labels': [severidad_labels.get(item['grado_severidad'], item['grado_severidad']) 
                   for item in severidad_counts],
        'data': [item['count'] for item in severidad_counts],
        'colors': [severidad_colors.get(item['grado_severidad'], '#6c757d') 
                   for item in severidad_counts]
    }
    
    # 3. Top 10 técnicos con más incidencias
    top_tecnicos = Incidencia.objects.values(
        'tecnico_responsable__nombre_completo'
    ).annotate(
        total=Count('id')
    ).order_by('-total')[:10]
    
    ranking_tecnicos = {
        'labels': [item['tecnico_responsable__nombre_completo'] or 'Sin técnico' 
                   for item in top_tecnicos],
        'data': [item['total'] for item in top_tecnicos]
    }
    
    # 4. Distribución por categoría
    categorias_counts = Incidencia.objects.values(
        'tipo_incidencia__nombre',
        'tipo_incidencia__color'
    ).annotate(
        count=Count('id')
    ).order_by('-count')
    
    distribucion_categorias = {
        'labels': [item['tipo_incidencia__nombre'] or 'Sin categoría' 
                   for item in categorias_counts],
        'data': [item['count'] for item in categorias_counts],
        'colors': [item['tipo_incidencia__color'] or '#6c757d' 
                   for item in categorias_counts]
    }
    
    # 5. Análisis por sucursal
    sucursales_counts = Incidencia.objects.values(
        'sucursal__nombre'
    ).annotate(
        total=Count('id')
    ).order_by('-total')
    
    analisis_sucursales = {
        'labels': [item['sucursal__nombre'] or 'Sin sucursal' 
                   for item in sucursales_counts],
        'data': [item['total'] for item in sucursales_counts]
    }
    
    # 6. Componentes más afectados
    componentes_counts = Incidencia.objects.values(
        'componente_afectado__nombre'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    componentes_afectados = {
        'labels': [item['componente_afectado__nombre'] or 'Sin componente' 
                   for item in componentes_counts],
        'data': [item['count'] for item in componentes_counts]
    }
    
    # 7. KPIs adicionales
    total_incidencias = Incidencia.objects.count()
    incidencias_abiertas = Incidencia.objects.filter(estado='abierta').count()
    incidencias_criticas = Incidencia.objects.filter(grado_severidad='critico').count()
    incidencias_cerradas = Incidencia.objects.filter(estado='cerrada').count()
    reincidencias = Incidencia.objects.filter(es_reincidencia=True).count()
    
    # Calcular porcentaje de reincidencias
    porcentaje_reincidencias = round((reincidencias / total_incidencias * 100), 2) if total_incidencias > 0 else 0
    
    # Promedio de días para cerrar incidencias
    incidencias_cerradas_obj = Incidencia.objects.filter(estado='cerrada')
    if incidencias_cerradas_obj.exists():
        dias_totales = sum([inc.dias_abierta for inc in incidencias_cerradas_obj])
        promedio_dias_cierre = round(dias_totales / incidencias_cerradas_obj.count(), 1)
    else:
        promedio_dias_cierre = 0
    
    kpis = {
        'total_incidencias': total_incidencias,
        'incidencias_abiertas': incidencias_abiertas,
        'incidencias_criticas': incidencias_criticas,
        'incidencias_cerradas': incidencias_cerradas,
        'reincidencias': reincidencias,
        'porcentaje_reincidencias': porcentaje_reincidencias,
        'promedio_dias_cierre': promedio_dias_cierre
    }
    
    # Retornar todos los datos
    data = {
        'success': True,
        'kpis': kpis,
        'tendencia_mensual': tendencia_mensual,
        'distribucion_severidad': distribucion_severidad,
        'ranking_tecnicos': ranking_tecnicos,
        'distribucion_categorias': distribucion_categorias,
        'analisis_sucursales': analisis_sucursales,
        'componentes_afectados': componentes_afectados
    }
    
    return JsonResponse(data)


def api_exportar_excel(request):
    """
    API para exportar incidencias a Excel
    Requiere: openpyxl instalado (pip install openpyxl)
    """
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        return JsonResponse({
            'success': False,
            'error': 'Librería openpyxl no instalada. Ejecuta: pip install openpyxl'
        })
    
    # Crear workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Incidencias"
    
    # Encabezados
    headers = [
        'Folio', 'Fecha Detección', 'Tipo Equipo', 'Marca', 'Modelo',
        'No. Serie', 'Sucursal', 'Técnico', 'Inspector', 'Categoría',
        'Severidad', 'Estado', 'Componente', 'Descripción', 'Días Abierta'
    ]
    
    # Estilo de encabezados
    header_fill = PatternFill(start_color="0d6efd", end_color="0d6efd", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = header
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
    
    # Obtener incidencias
    incidencias = Incidencia.objects.all().select_related(
        'sucursal', 'tecnico_responsable', 'inspector_calidad',
        'tipo_incidencia', 'componente_afectado'
    ).order_by('-fecha_deteccion')
    
    # Escribir datos
    for row_num, inc in enumerate(incidencias, 2):
        ws.cell(row=row_num, column=1).value = inc.folio
        ws.cell(row=row_num, column=2).value = inc.fecha_deteccion.strftime('%d/%m/%Y')
        ws.cell(row=row_num, column=3).value = inc.get_tipo_equipo_display()
        ws.cell(row=row_num, column=4).value = inc.marca
        ws.cell(row=row_num, column=5).value = inc.modelo
        ws.cell(row=row_num, column=6).value = inc.numero_serie
        ws.cell(row=row_num, column=7).value = inc.sucursal.nombre if inc.sucursal else ''
        ws.cell(row=row_num, column=8).value = inc.tecnico_responsable.nombre_completo if inc.tecnico_responsable else ''
        ws.cell(row=row_num, column=9).value = inc.inspector_calidad.nombre_completo if inc.inspector_calidad else ''
        ws.cell(row=row_num, column=10).value = inc.tipo_incidencia.nombre if inc.tipo_incidencia else ''
        ws.cell(row=row_num, column=11).value = inc.get_grado_severidad_display()
        ws.cell(row=row_num, column=12).value = inc.get_estado_display()
        ws.cell(row=row_num, column=13).value = inc.componente_afectado.nombre if inc.componente_afectado else ''
        ws.cell(row=row_num, column=14).value = inc.descripcion_incidencia[:100]  # Truncar para Excel
        ws.cell(row=row_num, column=15).value = inc.dias_abierta
    
    # Ajustar anchos de columna
    for col_num in range(1, len(headers) + 1):
        column_letter = get_column_letter(col_num)
        ws.column_dimensions[column_letter].width = 15
    
    # Crear respuesta HTTP
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename=incidencias_{datetime.now().strftime("%Y%m%d")}.xlsx'
    
    wb.save(response)
    return response


# ==========================================
# SISTEMA DE NOTIFICACIONES POR EMAIL
# ==========================================

@require_http_methods(["GET"])
def api_obtener_destinatarios(request, incidencia_id):
    """
    API: Obtiene la lista de destinatarios disponibles para una incidencia
    GET /scorecard/api/incidencias/<id>/destinatarios/
    
    Retorna JSON con lista de destinatarios disponibles
    """
    try:
        incidencia = get_object_or_404(Incidencia, id=incidencia_id)
        destinatarios = obtener_destinatarios_disponibles(incidencia)
        
        return JsonResponse({
            'success': True,
            'destinatarios': destinatarios
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error al obtener destinatarios: {str(e)}'
        }, status=400)


@require_http_methods(["POST"])
def api_enviar_notificacion(request, incidencia_id):
    """
    API: Envía notificación por email sobre una incidencia
    POST /scorecard/api/incidencias/<id>/enviar-notificacion/
    
    Body (JSON):
    {
        "destinatarios": [
            {"nombre": "Juan Pérez", "email": "juan@email.com", "rol": "Técnico"},
            ...
        ],
        "mensaje_adicional": "Texto opcional"
    }
    
    Retorna JSON con resultado del envío
    """
    try:
        incidencia = get_object_or_404(Incidencia, id=incidencia_id)
        
        # Parsear el body JSON
        data = json.loads(request.body)
        destinatarios_seleccionados = data.get('destinatarios', [])
        mensaje_adicional = data.get('mensaje_adicional', '')
        
        # Validar que hay destinatarios
        if not destinatarios_seleccionados:
            return JsonResponse({
                'success': False,
                'message': 'Debe seleccionar al menos un destinatario'
            }, status=400)
        
        # Enviar la notificación
        resultado = enviar_notificacion_incidencia(
            incidencia=incidencia,
            destinatarios_seleccionados=destinatarios_seleccionados,
            mensaje_adicional=mensaje_adicional,
            enviado_por=request.user.username if request.user.is_authenticated else 'Sistema'
        )
        
        if resultado['success']:
            return JsonResponse(resultado)
        else:
            return JsonResponse(resultado, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Error al parsear JSON del request'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error inesperado: {str(e)}'
        }, status=500)

