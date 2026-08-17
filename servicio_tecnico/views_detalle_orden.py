"""
Vista detalle_orden — dispatcher delgado (Fase C).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1) Carga la orden.
2) Si es POST, despacha al handler según form_type.
3) Arma el context (services/detalle_orden_context.py) y renderiza.

Handlers:
- views_detalle_orden_estado.py
- views_detalle_orden_multimedia.py
- views_detalle_orden_cotizacion.py
- views_detalle_orden_pagos.py

urls.py sigue con views.detalle_orden (reexport en views.py).
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from .decorators import permission_required_with_message
from .models import OrdenServicio
from .services.detalle_orden_context import build_detalle_orden_context
from .views_detalle_orden_cotizacion import (
    handle_crear_cotizacion,
    handle_editar_fecha_envio,
    handle_editar_mano_obra,
    handle_gestionar_cotizacion,
    handle_guardar_mano_obra,
)
from .views_detalle_orden_estado import (
    handle_asignar_responsables,
    handle_cambio_estado,
    handle_comentario,
    handle_configuracion,
    handle_editar_info_equipo,
    handle_reingreso_rhitso,
)
from .views_detalle_orden_multimedia import (
    handle_subir_imagenes,
    handle_subir_video,
)
from .views_detalle_orden_pagos import (
    handle_actualizar_datos_factura,
    handle_eliminar_pago,
    handle_registrar_pago,
    handle_validar_pago,
)


# EXPLICACIÓN PARA PRINCIPIANTES:
# Diccionario form_type → función. crear/generar cotización comparten handler.
_FORM_TYPE_HANDLERS = {
    'configuracion': handle_configuracion,
    'reingreso_rhitso': handle_reingreso_rhitso,
    'cambio_estado': handle_cambio_estado,
    'asignar_responsables': handle_asignar_responsables,
    'comentario': handle_comentario,
    'subir_imagenes': handle_subir_imagenes,
    'subir_video': handle_subir_video,
    'editar_info_equipo': handle_editar_info_equipo,
    'guardar_mano_obra': handle_guardar_mano_obra,
    'crear_cotizacion': handle_crear_cotizacion,
    'generar_cotizacion': handle_crear_cotizacion,
    'editar_fecha_envio': handle_editar_fecha_envio,
    'editar_mano_obra': handle_editar_mano_obra,
    'gestionar_cotizacion': handle_gestionar_cotizacion,
    'registrar_pago': handle_registrar_pago,
    'actualizar_datos_factura': handle_actualizar_datos_factura,
    'eliminar_pago': handle_eliminar_pago,
    'validar_pago': handle_validar_pago,
}


@login_required
@permission_required_with_message('servicio_tecnico.view_ordenservicio')
def detalle_orden(request, orden_id):
    """
    Vista completa de detalles de una orden de servicio.

    Args:
        request: Petición HTTP.
        orden_id: ID de la orden a mostrar.

    Returns:
        HttpResponse del template o redirect/JSON del handler POST.

    Efectos secundarios:
        Handlers POST pueden escribir BD, session y encolar Celery.
    """
    orden = get_object_or_404(
        OrdenServicio.objects.select_related(
            'sucursal',
            'responsable_seguimiento',
            'tecnico_asignado_actual',
            'detalle_equipo',
            'orden_original',
            'incidencia_scorecard',
        ).prefetch_related(
            'imagenes',
            'historial__usuario',
            'historial__tecnico_anterior',
            'historial__tecnico_nuevo',
            'pagos__registrado_por',
        ),
        pk=orden_id,
    )

    empleado_actual = None
    if hasattr(request.user, 'empleado'):
        empleado_actual = request.user.empleado

    if request.method == 'POST':
        form_type = request.POST.get('form_type', '')
        handler = _FORM_TYPE_HANDLERS.get(form_type)
        if handler is not None:
            # Paso: el handler resuelve el POST; si devuelve respuesta, terminamos.
            respuesta = handler(request, orden, empleado_actual)
            if respuesta is not None:
                return respuesta

    context = build_detalle_orden_context(request, orden)
    return render(request, 'servicio_tecnico/detalle_orden.html', context)
