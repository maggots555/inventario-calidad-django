"""
Fechas de reparación automáticas (inicio y fin).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El técnico ya no tiene que poner a mano "Inicio / Fin Reparación".
El sistema las llena la primera vez que ocurre el hito de negocio:

- Inicio: Piezas Recibidas (Almacén o cambio manual), fotos de ingreso en
  Venta Mostrador, o paso manual a En Reparación si aún no había fecha.
- Fin: fotos tipo Reparación (la orden pasa a Control de Calidad).

Nunca se pisa una fecha ya guardada (manual o de un hito anterior).
"""

from __future__ import annotations

from typing import Any

from django.utils import timezone

from servicio_tecnico.services.historial import registrar_historial


def _detalle_de(orden: Any) -> Any | None:
    """
    Obtiene DetalleEquipo de la orden, o None si aún no existe.

    Args:
        orden: OrdenServicio.

    Returns:
        DetalleEquipo o None.
    """
    return getattr(orden, 'detalle_equipo', None)


def aplicar_inicio_reparacion_si_vacia(
    orden: Any,
    empleado: Any = None,
    *,
    motivo: str = '',
) -> dict[str, Any]:
    """
    Llena fecha_inicio_reparacion con hoy si todavía está vacía.

    Objetivo de negocio:
        Arrancar el reloj de reparación en el primer hito real (piezas
        recibidas, ingreso VM o paso a En Reparación), sin pisar una fecha
        ya capturada.

    Args:
        orden: OrdenServicio (con detalle_equipo).
        empleado: Quién dispara el hito, o None si es sync de sistema.
        motivo: Texto corto para el historial (ej. "Piezas Recibidas").

    Returns:
        dict con aplicada (bool) y fecha_inicio (date | None).

    Efectos secundarios:
        Puede actualizar DetalleEquipo.fecha_inicio_reparacion e historial.
    """
    resultado: dict[str, Any] = {
        'aplicada': False,
        'fecha_inicio': None,
    }
    detalle = _detalle_de(orden)
    if detalle is None:
        return resultado

    resultado['fecha_inicio'] = detalle.fecha_inicio_reparacion
    if detalle.fecha_inicio_reparacion is not None:
        return resultado

    fecha_hoy = timezone.localdate()
    detalle.fecha_inicio_reparacion = fecha_hoy
    detalle.save(update_fields=['fecha_inicio_reparacion'])

    resultado['aplicada'] = True
    resultado['fecha_inicio'] = fecha_hoy

    motivo_txt = motivo or 'hito de reparación'
    registrar_historial(
        orden=orden,
        tipo_evento='sistema',
        usuario=empleado,
        comentario=(
            'Inicio de reparación registrado automáticamente '
            f'({fecha_hoy.strftime("%d/%m/%Y")}) — {motivo_txt}'
        ),
        es_sistema=True,
    )
    return resultado


def aplicar_fin_reparacion_si_vacia(
    orden: Any,
    empleado: Any = None,
    *,
    motivo: str = '',
) -> dict[str, Any]:
    """
    Llena fecha_fin_reparacion con hoy si todavía está vacía.

    Objetivo de negocio:
        Al evidenciar la reparación con fotos, el trabajo de taller ya
        terminó. No pisa un fin ya guardado a mano o en una carga previa.

    Args:
        orden: OrdenServicio (con detalle_equipo).
        empleado: Quién sube las fotos, o None.
        motivo: Texto corto para el historial.

    Returns:
        dict con aplicada (bool) y fecha_fin (date | None).

    Efectos secundarios:
        Puede actualizar DetalleEquipo.fecha_fin_reparacion e historial.
    """
    resultado: dict[str, Any] = {
        'aplicada': False,
        'fecha_fin': None,
    }
    detalle = _detalle_de(orden)
    if detalle is None:
        return resultado

    resultado['fecha_fin'] = detalle.fecha_fin_reparacion
    if detalle.fecha_fin_reparacion is not None:
        return resultado

    fecha_hoy = timezone.localdate()
    detalle.fecha_fin_reparacion = fecha_hoy
    detalle.save(update_fields=['fecha_fin_reparacion'])

    resultado['aplicada'] = True
    resultado['fecha_fin'] = fecha_hoy

    motivo_txt = motivo or 'imágenes de reparación'
    registrar_historial(
        orden=orden,
        tipo_evento='sistema',
        usuario=empleado,
        comentario=(
            'Fin de reparación registrado automáticamente '
            f'({fecha_hoy.strftime("%d/%m/%Y")}) — {motivo_txt}'
        ),
        es_sistema=True,
    )
    return resultado
