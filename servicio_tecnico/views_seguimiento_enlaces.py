"""
Dashboard y APIs del embudo de enlaces de seguimiento cliente (Fase 4).

Los helpers filtrar_enlaces_seguimiento / anotar_push_enlaces viven en
eventos_seguimiento.py (también los usa calcular_embudo_enlaces).

urls.py sigue usando views.<nombre> porque views.py reexporta estos símbolos.
"""

import logging

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from inventario.models import Empleado, Sucursal

from .decorators import permission_required_with_message
from .eventos_seguimiento import (
    anotar_eventos_enlaces,
    anotar_push_enlaces,
    calcular_embudo_enlaces,
    filtrar_enlaces_seguimiento,
)

logger = logging.getLogger(__name__)


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def dashboard_seguimiento_enlaces(request):
    """
    Vista principal del panel de métricas de seguimiento de clientes.
    Renderiza el template con lookups; la data se carga vía AJAX.
    """
    empleados = Empleado.objects.filter(activo=True).order_by('nombre_completo')
    sucursales = Sucursal.objects.filter(activa=True).order_by('nombre')

    return render(request, 'servicio_tecnico/dashboard_seguimiento_enlaces.html', {
        'empleados': empleados,
        'sucursales': sucursales,
    })




@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_seguimiento_enlaces_kpis(request):
    """
    API JSON: KPIs del dashboard de seguimiento de clientes.
    """
    from django.db.models import Sum, Avg, Count

    qs = anotar_push_enlaces(filtrar_enlaces_seguimiento(request))

    total_enlaces = qs.count()
    agregados = qs.aggregate(
        total_accesos=Sum('accesos_count'),
        promedio_accesos=Avg('accesos_count'),
    )
    total_accesos = agregados['total_accesos'] or 0
    promedio_accesos = round(agregados['promedio_accesos'] or 0, 1)

    sin_visitas = qs.filter(accesos_count=0).count()
    correos_enviados = qs.filter(correo_enviado=True).count()
    correos_no_enviados = qs.filter(correo_enviado=False).count()

    tasa_apertura = round(
        ((total_enlaces - sin_visitas) / total_enlaces * 100) if total_enlaces > 0 else 0, 1
    )

    push_suscritos = qs.filter(push_activo=True).count()
    push_sin_suscripcion = total_enlaces - push_suscritos
    tasa_push = round(
        (push_suscritos / total_enlaces * 100) if total_enlaces > 0 else 0, 1
    )

    return JsonResponse({
        'total_enlaces': total_enlaces,
        'total_accesos': total_accesos,
        'promedio_accesos': promedio_accesos,
        'sin_visitas': sin_visitas,
        'correos_enviados': correos_enviados,
        'correos_no_enviados': correos_no_enviados,
        'tasa_apertura': tasa_apertura,
        'push_suscritos': push_suscritos,
        'push_sin_suscripcion': push_sin_suscripcion,
        'tasa_push': tasa_push,
    })




@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_seguimiento_enlaces_embudo(request):
    """
    API JSON: embudo de adopción (correo → visita → PWA → push → chat).
    """
    from servicio_tecnico.eventos_seguimiento import calcular_embudo_enlaces

    datos = calcular_embudo_enlaces(filtrar_enlaces_seguimiento(request))
    return JsonResponse(datos)




@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_seguimiento_enlaces_tendencia(request):
    """
    API JSON: tendencia de accesos agrupados por día (últimos 60 días).
    Retorna dos series: enlaces creados y suma de accesos por día de creación.
    """
    from django.db.models.functions import TruncDate
    from django.db.models import Sum, Count

    qs = filtrar_enlaces_seguimiento(request)

    # Nuevos enlaces creados por día
    creados_por_dia = (
        qs
        .annotate(dia=TruncDate('fecha_creacion'))
        .values('dia')
        .annotate(total=Count('id'))
        .order_by('dia')
    )

    # Accesos registrados por día de último acceso (solo enlaces con accesos)
    accesos_por_dia = (
        qs
        .filter(fecha_ultimo_acceso__isnull=False)
        .annotate(dia=TruncDate('fecha_ultimo_acceso'))
        .values('dia')
        .annotate(total=Sum('accesos_count'))
        .order_by('dia')
    )

    return JsonResponse({
        'creados': [
            {'dia': str(r['dia']), 'total': r['total']}
            for r in creados_por_dia
        ],
        'accesos': [
            {'dia': str(r['dia']), 'total': r['total']}
            for r in accesos_por_dia
        ],
    })




@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_seguimiento_enlaces_top(request):
    """
    API JSON: top 15 órdenes más consultadas por los clientes.
    """
    from config.paises_config import fecha_local_pais, get_pais_actual
    pais = get_pais_actual()

    qs = filtrar_enlaces_seguimiento(request)

    top = (
        qs
        .filter(accesos_count__gt=0)
        .select_related('orden__detalle_equipo', 'orden__sucursal')
        .order_by('-accesos_count')[:15]
    )

    data = []
    for enlace in top:
        de = getattr(enlace.orden, 'detalle_equipo', None)
        equipo = f"{de.marca} {de.modelo}".strip() if de else '—'
        orden_cliente = de.orden_cliente if de else enlace.orden.numero_orden_interno
        data.append({
            'folio': orden_cliente,
            'equipo': equipo,
            'accesos': enlace.accesos_count,
            'ultimo_acceso': fecha_local_pais(enlace.fecha_ultimo_acceso, pais).strftime('%d/%m/%Y %H:%M') if enlace.fecha_ultimo_acceso else '—',
        })

    return JsonResponse({'top': data})




@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
@require_http_methods(['GET'])
def api_seguimiento_enlaces_tabla(request):
    """
    API JSON: lista paginada de enlaces de seguimiento con datos de la orden.
    """
    from django.core.paginator import Paginator
    from config.paises_config import fecha_local_pais, get_pais_actual
    from servicio_tecnico.eventos_seguimiento import anotar_eventos_enlaces
    pais = get_pais_actual()

    qs = anotar_eventos_enlaces(anotar_push_enlaces(filtrar_enlaces_seguimiento(request)))

    # Ordenamiento
    order_by = request.GET.get('order_by', '-fecha_creacion')
    campos_validos = {'fecha_creacion', '-fecha_creacion', 'accesos_count', '-accesos_count'}
    if order_by in campos_validos:
        qs = qs.order_by(order_by)
    else:
        qs = qs.order_by('-fecha_creacion')

    paginator = Paginator(qs, 50)
    page_num = request.GET.get('page', 1)
    page = paginator.get_page(page_num)

    filas = []
    for enlace in page.object_list:
        de = getattr(enlace.orden, 'detalle_equipo', None)
        equipo = f"{de.marca} {de.modelo}".strip() if de else '—'
        orden_cliente = de.orden_cliente if de else '—'
        email = de.email_cliente if de else '—'
        sucursal = enlace.orden.sucursal.nombre if enlace.orden.sucursal else '—'
        responsable = ''
        if enlace.orden.responsable_seguimiento:
            responsable = enlace.orden.responsable_seguimiento.nombre_completo

        push_fecha_str = '—'
        if enlace.push_fecha:
            push_fecha_str = fecha_local_pais(enlace.push_fecha, pais).strftime('%d/%m/%Y %H:%M')

        filas.append({
            'folio': orden_cliente or enlace.orden.numero_orden_interno,
            'orden_id': enlace.orden.id,
            'orden_cliente': orden_cliente,
            'numero_serie': de.numero_serie if de else '—',
            'equipo': equipo,
            'email': email,
            'sucursal': sucursal,
            'responsable': responsable,
            'estado': enlace.orden.get_estado_display(),
            'accesos': enlace.accesos_count,
            'correo_enviado': enlace.correo_enviado,
            'push_activo': enlace.push_activo,
            'push_dispositivos': enlace.push_dispositivos,
            'push_fecha': push_fecha_str,
            'pwa_instalada': enlace.evento_pwa_instalada,
            'chat_usado': enlace.evento_chat_usado,
            'tiene_pdf_diagnostico': bool(enlace.pdf_diagnostico),
            'diagnostico_pdf_abierto': enlace.evento_diagnostico_pdf_abierto,
            'fecha_creacion': enlace.fecha_creacion.strftime('%d/%m/%Y'),
            'ultimo_acceso': fecha_local_pais(enlace.fecha_ultimo_acceso, pais).strftime('%d/%m/%Y %H:%M') if enlace.fecha_ultimo_acceso else '—',
        })

    return JsonResponse({
        'filas': filas,
        'total': paginator.count,
        'pagina': page.number,
        'total_paginas': paginator.num_pages,
        'tiene_siguiente': page.has_next(),
        'tiene_anterior': page.has_previous(),
    })
