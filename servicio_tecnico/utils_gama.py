"""
Utilidades para clasificar la gama del equipo.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Hay DOS formas de decidir la gama (alta / media / baja), en cascada:

1) Por marca/modelo (catálogo ReferenciaGamaEquipo) → estimado al crear la orden
   (útil para gaming → alta cuando aún no hay mano de obra).

2) Por costo de mano de obra → fuente de verdad cuando el técnico ya registró
   un monto > 0. Sobrescribe la gama del paso 1.

Este módulo solo implementa el paso 2. El paso 1 vive en
DetalleEquipo.calcular_gama() y ReferenciaGamaEquipo.obtener_gama().
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional, Union

from config.constants import (
    GAMA_EQUIPO_CHOICES,
    GAMA_POR_MANO_OBRA_UMBRAL_ALTA,
    GAMA_POR_MANO_OBRA_UMBRAL_MEDIA,
)

# Mapa código → etiqueta legible ("alta" → "Gama Alta")
_GAMA_LABELS = dict(GAMA_EQUIPO_CHOICES)


def resolver_gama_por_mano_obra(
    costo: Optional[Union[Decimal, int, float, str]],
) -> Optional[str]:
    """
    Decide la gama del equipo según el costo de mano de obra.

    Objetivo de negocio:
        Traducir el monto de MO a 'baja' / 'media' / 'alta' con umbrales fijos.

    Args:
        costo: Monto de mano de obra (Decimal, int, float o str convertible).
               Si es None, vacío, inválido o <= 0, retorna None (no cambiar gama).

    Returns:
        'baja' | 'media' | 'alta' | None

    Efectos secundarios:
        Ninguno (función pura).
    """
    # EXPLICACIÓN: Si no hay costo real, la cascada deja la gama del modelo.
    if costo is None or costo == '':
        return None

    try:
        monto = Decimal(str(costo))
    except Exception:
        return None

    # EXPLICACIÓN: MO en 0 significa "aún no registrada" → no pisar el estimado.
    if monto <= 0:
        return None

    # Umbrales: baja < 400 ≤ media < 800 ≤ alta
    if monto >= GAMA_POR_MANO_OBRA_UMBRAL_ALTA:
        return 'alta'
    if monto >= GAMA_POR_MANO_OBRA_UMBRAL_MEDIA:
        return 'media'
    return 'baja'


def etiqueta_gama(codigo: Optional[str]) -> str:
    """
    Convierte el código de gama a texto legible para mensajes e historial.

    Args:
        codigo: 'alta', 'media', 'baja' o None.

    Returns:
        Etiqueta de GAMA_EQUIPO_CHOICES, o 'Sin definir' si no hay código.
    """
    if not codigo:
        return 'Sin definir'
    return _GAMA_LABELS.get(codigo, codigo)


def aplicar_gama_por_mano_obra(orden, costo, usuario=None) -> Optional[str]:
    """
    Actualiza DetalleEquipo.gama según el costo de mano de obra (cascada).

    Objetivo de negocio:
        Cuando se guarda MO > 0, la gama del equipo pasa a depender del costo,
        no del modelo. Si el costo no define gama (0 / inválido), no hace nada.

    Args:
        orden: Instancia de OrdenServicio (debe tener detalle_equipo).
        costo: Monto de mano de obra recién guardado.
        usuario: Empleado opcional para el historial (puede ser None).

    Returns:
        Código de gama aplicado ('alta'/'media'/'baja') si hubo cambio,
        o None si no se cambió nada (mismo valor, sin detalle, o costo <= 0).

    Efectos secundarios:
        - Guarda DetalleEquipo.gama si cambió.
        - Crea HistorialOrden con tipo_evento='sistema' si hubo cambio.
    """
    from servicio_tecnico.models import HistorialOrden

    # Paso 1: resolver qué gama corresponde al monto
    gama_nueva = resolver_gama_por_mano_obra(costo)
    if gama_nueva is None:
        return None

    # Paso 2: la orden debe tener detalle de equipo (OneToOne)
    detalle = getattr(orden, 'detalle_equipo', None)
    if detalle is None:
        return None

    gama_anterior = detalle.gama or ''

    # Paso 3: si ya está en esa gama, no reescribimos ni ensuciamos el historial
    if gama_anterior == gama_nueva:
        return None

    # Paso 4: persistir el cambio (update_fields evita tocar email/RFC/etc.)
    detalle.gama = gama_nueva
    detalle.save(update_fields=['gama'])

    # Paso 5: dejar rastro en el historial de la orden
    HistorialOrden.objects.create(
        orden=orden,
        tipo_evento='sistema',
        comentario=(
            f'Gama actualizada por mano de obra (${costo}): '
            f'{etiqueta_gama(gama_anterior)} → {etiqueta_gama(gama_nueva)}'
        ),
        usuario=usuario,
        es_sistema=True,
    )

    return gama_nueva
