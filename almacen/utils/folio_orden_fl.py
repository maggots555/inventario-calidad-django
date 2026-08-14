"""
Folio FL- (Venta Mostrador) y sucursal al crear órdenes desde Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Las órdenes FL- no vienen de Dell: las genera SIGMA con formato
FL-YYYY-NNNN (año + consecutivo de 4 dígitos).

Este módulo concentra dos reglas que antes estaban copiadas en la vista
de cotización:

1. ¿Cuál es el siguiente folio FL- de este año?
2. ¿A qué sucursal se asigna la orden si el usuario no la elige?

La solicitud de baja y la cotización sin orden reutilizan las mismas
funciones para no inventar números distintos en cada pantalla.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.utils import timezone

if TYPE_CHECKING:
    from inventario.models import Empleado, Sucursal


def sugerir_siguiente_folio_fl() -> str:
    """
    Calcula el siguiente folio FL- del año en curso.

    Objetivo de negocio:
        El almacenista no debe inventar un FL-; el sistema sugiere
        el consecutivo (ej. FL-2026-0001, luego FL-2026-0002).

    Returns:
        str: Folio sugerido con formato FL-YYYY-NNNN.

    Efectos secundarios:
        Solo lectura sobre DetalleEquipo; no crea filas.
    """
    from servicio_tecnico.models import DetalleEquipo

    # El consecutivo es por año civil: en 2027 se reinicia en 0001.
    año_actual = timezone.now().year
    prefijo_año = f'FL-{año_actual}'

    # Orden lexicográfico funciona porque el número va con 4 dígitos (0001).
    ultimo_fl = DetalleEquipo.objects.filter(
        orden_cliente__startswith=prefijo_año
    ).order_by('-orden_cliente').first()

    siguiente_num = 1
    if ultimo_fl and ultimo_fl.orden_cliente:
        # FL-2026-0007 → tomar el último segmento y sumar 1.
        try:
            siguiente_num = int(ultimo_fl.orden_cliente.split('-')[-1]) + 1
        except (ValueError, IndexError):
            siguiente_num = 1

    return f'{prefijo_año}-{siguiente_num:04d}'


def resolver_sucursal_orden_almacen(
    empleado: Empleado | None,
    tecnico: Empleado | None,
) -> Sucursal | None:
    """
    Elige la sucursal de la orden nueva sin pedirla al usuario.

    Objetivo de negocio:
        Igual que en cotización: primero la sucursal del empleado
        (quien está creando), si no tiene, la del técnico asignado.

    Args:
        empleado: Empleado del usuario actual o del creador de la solicitud.
        tecnico: Técnico que se asignará a la orden (puede ser None).

    Returns:
        Sucursal o None si ninguno de los dos tiene sucursal asignada.
    """
    if empleado is not None and empleado.sucursal_id:
        return empleado.sucursal
    if tecnico is not None and tecnico.sucursal_id:
        return tecnico.sucursal
    return None


def datos_sugerencia_folio_fl(
    empleado: Empleado | None,
    tecnico: Empleado | None = None,
) -> dict:
    """
    Empaqueta folio sugerido + sucursal inferida para el JSON del front.

    Args:
        empleado: Empleado logueado (prioridad de sucursal).
        tecnico: Técnico ya elegido en el formulario, si hay.

    Returns:
        dict: numero_fl_sugerido, sucursal_id, sucursal (nombre o None).
    """
    sucursal = resolver_sucursal_orden_almacen(empleado, tecnico)
    return {
        'numero_fl_sugerido': sugerir_siguiente_folio_fl(),
        'sucursal_id': sucursal.pk if sucursal else None,
        'sucursal': sucursal.nombre if sucursal else None,
    }
