"""
Descarga Excel del catálogo de productos activos.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
La pantalla de productos sigue en views_catalogo.py. Este archivo solo
responde el botón «Descargar Excel»: mismos filtros, archivo .xlsx.
urls.py llega aquí porque views.py reexporta el nombre.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone

from almacen.decorators import permission_required_with_message
from almacen.utils.consulta_productos import queryset_productos_activos
from almacen.utils.excel_productos import construir_excel_productos_activos


@login_required
@permission_required_with_message('almacen.view_productoalmacen')
def exportar_productos_excel(request):
    """
    Descarga los productos activos que coinciden con los filtros de la lista.

    Objetivo de negocio:
        Desde la pantalla de productos, bajar el detalle del catálogo
        activo (no solo las 20 filas de la página en pantalla).

    Args:
        request: GET con los mismos parámetros que la lista
            (q, tipo, categoria, stock, clave_sat). `page` no recorta.

    Returns:
        HttpResponse con el .xlsx adjunto.

    Efectos secundarios:
        Ninguno de escritura. Lee ProductoAlmacen del país activo.
        Sin permiso, el decorador redirige a acceso denegado.
    """
    # Mismos filtros que la tabla. order_by explícito: el archivo sale
    # por nombre aunque alguien cambie el orden por defecto del modelo.
    productos = queryset_productos_activos(request.GET).order_by('nombre')
    contenido = construir_excel_productos_activos(productos)

    fecha = timezone.localdate().strftime('%Y%m%d')
    nombre = f'Productos_Almacen_Activos_{fecha}.xlsx'
    respuesta = HttpResponse(
        contenido,
        content_type=(
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ),
    )
    respuesta['Content-Disposition'] = f'attachment; filename="{nombre}"'
    return respuesta
