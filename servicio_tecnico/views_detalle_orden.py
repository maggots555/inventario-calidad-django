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

from urllib.parse import quote

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

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
# Una sola tabla: botón → (función, permiso).
# El permiso en None solo existe en los pagos, porque ese módulo ya
# decide quién cobra y quién valida. Cualquier otro botón TIENE que
# traer su permiso aquí. No hay una segunda lista que se pueda olvidar:
# si falta el permiso, esa fila no compila como acción de escritura.
#
# subir_video usa add_imagenorden a propósito. Los grupos (técnico,
# recepción, compras, gerencia) tienen ese permiso para la evidencia.
# add_videoorden no está asignado en scripts/setup_grupos_permisos.py;
# exigirlo dejaría a todo el personal sin poder subir videos.
_ACCIONES_DETALLE = {
    'configuracion': (handle_configuracion, 'servicio_tecnico.change_ordenservicio'),
    'reingreso_rhitso': (handle_reingreso_rhitso, 'servicio_tecnico.change_ordenservicio'),
    'cambio_estado': (handle_cambio_estado, 'servicio_tecnico.change_ordenservicio'),
    'asignar_responsables': (handle_asignar_responsables, 'servicio_tecnico.change_ordenservicio'),
    'editar_info_equipo': (handle_editar_info_equipo, 'servicio_tecnico.change_detalleequipo'),
    'guardar_mano_obra': (handle_guardar_mano_obra, 'servicio_tecnico.change_ordenservicio'),
    'editar_mano_obra': (handle_editar_mano_obra, 'servicio_tecnico.change_ordenservicio'),
    'comentario': (handle_comentario, 'servicio_tecnico.add_historialorden'),
    'subir_imagenes': (handle_subir_imagenes, 'servicio_tecnico.add_imagenorden'),
    'subir_video': (handle_subir_video, 'servicio_tecnico.add_imagenorden'),
    'crear_cotizacion': (handle_crear_cotizacion, 'servicio_tecnico.add_cotizacion'),
    'generar_cotizacion': (handle_crear_cotizacion, 'servicio_tecnico.add_cotizacion'),
    'editar_fecha_envio': (handle_editar_fecha_envio, 'servicio_tecnico.change_cotizacion'),
    'gestionar_cotizacion': (handle_gestionar_cotizacion, 'servicio_tecnico.change_cotizacion'),
    'registrar_pago': (handle_registrar_pago, None),
    'actualizar_datos_factura': (handle_actualizar_datos_factura, None),
    'eliminar_pago': (handle_eliminar_pago, None),
    'validar_pago': (handle_validar_pago, None),
}

# Nombres que el resto del código y los tests ya conocen.
_FORM_TYPE_HANDLERS = {
    nombre: par[0] for nombre, par in _ACCIONES_DETALLE.items()
}
_FORM_TYPES_PAGO = frozenset(
    nombre for nombre, par in _ACCIONES_DETALLE.items() if par[1] is None
)
_PERMISO_POR_FORM_TYPE = {
    nombre: par[1]
    for nombre, par in _ACCIONES_DETALLE.items()
    if par[1] is not None
}


def _redirect_sin_permiso_escritura(permiso: str):
    """
    Manda a acceso denegado cuando el POST no tiene permiso de escritura.

    Args:
        permiso: Codename Django, por ejemplo change_ordenservicio.

    Returns:
        HttpResponseRedirect a la pantalla de acceso denegado.

    Efectos secundarios:
        Ninguno en base de datos. No llama al handler.
    """
    mensaje = 'No tienes permisos para modificar esta orden.'
    url = reverse('servicio_tecnico:acceso_denegado_servicio_tecnico')
    return redirect(f'{url}?mensaje={quote(mensaje)}&permiso={quote(permiso)}')


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
        accion = _ACCIONES_DETALLE.get(form_type)
        if accion is not None:
            handler, permiso = accion
            # Paso: ver la orden no autoriza a escribirla.
            # permiso None = pagos; ese handler revisa su propia regla.
            if permiso is not None and not request.user.has_perm(permiso):
                return _redirect_sin_permiso_escritura(permiso)
            # Paso: el handler resuelve el POST; si devuelve respuesta, terminamos.
            respuesta = handler(request, orden, empleado_actual)
            if respuesta is not None:
                return respuesta

    context = build_detalle_orden_context(request, orden)
    return render(request, 'servicio_tecnico/detalle_orden.html', context)
