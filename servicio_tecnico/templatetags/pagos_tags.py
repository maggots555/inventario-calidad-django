"""
Tags de template para cobros y validación de pagos.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El HTML no debe repetir la prioridad del folio (cliente → ST → interno)
ni la lista de roles que pueden validar. Esos cerebros viven en
pagos_orden.py; aquí solo los exponemos al template.
"""

from django import template

from servicio_tecnico.services.pagos_orden import (
    referencia_visible_orden,
    usuario_puede_validar_pago,
)

register = template.Library()


@register.simple_tag
def referencia_visible(orden):
    """
    Folio visible de la orden (misma regla que correos y push).

    Args:
        orden: OrdenServicio (puede no tener detalle_equipo).

    Returns:
        ReferenciaOrdenVisible (texto, tipo, cliente, ST, interno).
    """
    return referencia_visible_orden(orden)


@register.filter
def puede_validar_pagos(user):
    """
    True si el menú/bandeja de validación aplica a este usuario.

    Args:
        user: request.user (puede no tener empleado).

    Returns:
        bool (misma regla que la vista).
    """
    return usuario_puede_validar_pago(user)
