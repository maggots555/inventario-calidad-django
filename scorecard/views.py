"""
Vistas para el sistema de Score Card
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from django.http import JsonResponse
from .models import Incidencia, CategoriaIncidencia, ComponenteEquipo, EvidenciaIncidencia
from .forms import IncidenciaForm, EvidenciaIncidenciaForm
from inventario.models import Empleado, Sucursal


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
    
    context = {
        'incidencia': incidencia,
        'evidencias': evidencias,
    }
    
    return render(request, 'scorecard/detalle_incidencia.html', context)


def crear_incidencia(request):
    """
    Crear una nueva incidencia con formulario completo
    """
    if request.method == 'POST':
        form = IncidenciaForm(request.POST)
        
        if form.is_valid():
            incidencia = form.save()
            
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
            incidencia = form.save()
            
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
