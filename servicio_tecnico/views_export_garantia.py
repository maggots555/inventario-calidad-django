"""
Export Excel: base de servicios en garantía (página de filtros + descarga).

Objetivo de negocio:
    Permitir a gerencia descargar la lista maestra de órdenes DENTRO de
    garantía, con el mismo espíritu del Excel OOW/FL, sin un dashboard
    dedicado (gráficas / KPIs en pantalla).

EXPLICACIÓN PARA PRINCIPIANTES:
    Hay dos vistas delgadas:
    1) La página GET muestra filtros y un conteo.
    2) El botón Exportar envía los mismos filtros a otra URL que arma el .xlsx.
    Toda la lógica de negocio vive en services/export_excel_garantia.py
    para no hinchar views_dashboard_oow_fl.py.
"""

from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from config.constants import ESTADO_ORDEN_CHOICES
from inventario.models import Empleado, Sucursal
from servicio_tecnico.decorators import permission_required_with_message
from servicio_tecnico.services.export_excel_garantia import (
    construir_queryset_export,
    generar_workbook_base_garantia,
    nombre_archivo_base_garantia,
    queryset_base_garantia,
    texto_filtros_aplicados,
)


def _filtros_desde_request(request: HttpRequest) -> dict[str, str]:
    """
    Lee los query params de la página / del export.

    Args:
        request: GET con responsable_id, fechas, estado, sucursal_id.

    Returns:
        Diccionario de strings (vacío = “sin ese filtro”).

    Efectos secundarios:
        Ninguno.
    """
    return {
        'responsable_id': request.GET.get('responsable_id', ''),
        'fecha_desde': request.GET.get('fecha_desde', ''),
        'fecha_hasta': request.GET.get('fecha_hasta', ''),
        'estado': request.GET.get('estado', ''),
        'sucursal_id': request.GET.get('sucursal_id', ''),
    }


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_base_garantia(request: HttpRequest) -> HttpResponse:
    """
    Página liviana: filtros + conteo de órdenes en garantía.

    Args:
        request: GET con los filtros opcionales.

    Returns:
        HTML del formulario (sin gráficas ni loader de dashboard).

    Efectos secundarios:
        Solo lecturas ORM.
    """
    filtros = _filtros_desde_request(request)
    ordenes = construir_queryset_export(**filtros)

    # Listas de selects: todo lo que existe en garantía (no el queryset ya filtrado),
    # para que el usuario no “pierda” opciones al aplicar un filtro.
    base = queryset_base_garantia()
    lista_responsables = Empleado.objects.filter(
        ordenes_responsable__in=base,
    ).distinct().order_by('nombre_completo')
    lista_sucursales = Sucursal.objects.filter(
        ordenes_servicio__in=base,
    ).distinct().order_by('nombre')

    context = {
        'filtros': filtros,
        'total_ordenes': ordenes.count(),
        'lista_responsables': lista_responsables,
        'lista_sucursales': lista_sucursales,
        'lista_estados': ESTADO_ORDEN_CHOICES,
    }
    return render(request, 'servicio_tecnico/exportar_base_garantia.html', context)


@login_required
@permission_required_with_message('servicio_tecnico.view_dashboard_gerencial')
def exportar_excel_base_garantia(request: HttpRequest) -> HttpResponse:
    """
    Genera y descarga el Excel de órdenes en garantía.

    Args:
        request: GET con los mismos filtros que la página.

    Returns:
        Attachment .xlsx.

    Efectos secundarios:
        Ninguno de escritura en BD; el archivo se arma en memoria.
    """
    filtros = _filtros_desde_request(request)
    ordenes = construir_queryset_export(**filtros)
    leyenda = texto_filtros_aplicados(**filtros)

    workbook = generar_workbook_base_garantia(ordenes, leyenda)

    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)

    nombre = nombre_archivo_base_garantia(
        responsable_id=filtros['responsable_id'],
        estado=filtros['estado'],
        sucursal_id=filtros['sucursal_id'],
    )
    response = HttpResponse(
        buffer.getvalue(),
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ),
    )
    response['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return response
