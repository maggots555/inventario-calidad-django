"""
Export Excel: Productividad técnicos (Dashboard Cotizaciones).

Objetivo de negocio:
    Descargar un reporte .xlsx con reparaciones productivas, ventas mostrador
    y diagnósticos agrupados por técnico, reutilizando los filtros GET del
    dashboard de cotizaciones.

EXPLICACIÓN PARA PRINCIPIANTES:
    Esta vista es delgada a propósito: no calcula métricas aquí.
    Toda la lógica vive en services/productividad_tecnicos.py para no
    hinchar views_dashboard_cotizaciones.py (~3400 LOC).
"""

from datetime import datetime
from io import BytesIO

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect

from servicio_tecnico.decorators import permission_required_with_message
from servicio_tecnico.services.productividad_tecnicos import (
    generar_workbook_productividad_tecnicos,
)


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_productividad_tecnicos(request: HttpRequest) -> HttpResponse:
    """
    Genera y descarga el Excel «Productividad técnicos».

    Args:
        request: GET con los mismos filtros del dashboard
            (fecha_inicio, fecha_fin, sucursal, tecnico, gama).

    Returns:
        HttpResponse con attachment .xlsx, o redirect al dashboard si no hay datos.

    Efectos secundarios:
        Solo lectura de BD; no encola tareas ni modifica registros.
    """
    # Mismos query params que dashboard_cotizaciones / otros exports.
    fecha_inicio = request.GET.get('fecha_inicio') or None
    fecha_fin = request.GET.get('fecha_fin') or None
    sucursal_id = request.GET.get('sucursal') or None
    tecnico_id = request.GET.get('tecnico') or None
    gama = request.GET.get('gama') or None

    workbook = generar_workbook_productividad_tecnicos(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        sucursal_id=sucursal_id,
        tecnico_id=tecnico_id,
        gama=gama,
    )

    if workbook is None:
        messages.warning(
            request,
            'No hay datos de productividad de técnicos con los filtros aplicados.',
        )
        return redirect('servicio_tecnico:dashboard_cotizaciones')

    # Serializar a memoria y devolver como descarga.
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    nombre = f'Productividad_Tecnicos_{timestamp}.xlsx'

    response = HttpResponse(
        buffer.getvalue(),
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ),
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response
