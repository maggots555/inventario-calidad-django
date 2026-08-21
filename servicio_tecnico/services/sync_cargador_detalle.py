"""
Sincroniza el número de cargador del formato digital hacia DetalleEquipo.

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
El formato Dell/OOW guarda `numero_cargador` en su propia tabla.
El detalle de la orden tiene OTRO campo: `numero_serie_cargador`.
Este helper es el puente: al guardar el wizard, copia el número
(y marca “incluye cargador”) para que se vea en la ficha del equipo,
RHITSO y correos de egreso.

No vive en models.py (regla fat models): es lógica de negocio, no de tabla.
"""

from __future__ import annotations

import logging

from django.core.exceptions import ObjectDoesNotExist
from django.db import router

from servicio_tecnico.models import DetalleEquipo, OrdenServicio

logger = logging.getLogger(__name__)

# Mismo tope que DetalleEquipo.numero_serie_cargador y Formato*.numero_cargador
MAX_NUMERO_CARGADOR = 100


def db_alias_de(instancia) -> str:
    """
    Alias de BD donde ya vive el objeto (México, Argentina, …).

    Args:
        instancia: modelo ya cargado (formato, orden, detalle, …).

    Returns:
        str: alias (`default`, `mexico`, `argentina`, …).
    """
    alias = getattr(getattr(instancia, '_state', None), 'db', None)
    if alias:
        return alias
    return router.db_for_write(type(instancia), instance=instancia) or 'default'


def sincronizar_cargador_a_detalle(
    orden: OrdenServicio,
    *,
    numero_cargador: str = '',
    accesorio_cargador: bool = False,
) -> None:
    """
    Copia el cargador capturado en el formato hacia DetalleEquipo.

    Reglas de negocio:
        - Número no vacío → se escribe en `numero_serie_cargador` (sobrescribe)
          y se marca `tiene_cargador=True`.
        - Solo checkbox “Cargador” → `tiene_cargador=True` (no borra el S/N).
        - Campo vacío en el formato → NO limpia un S/N que ya tuviera el detalle
          (pudo capturarse al crear la orden).

    Args:
        orden: OrdenServicio dueña del DetalleEquipo.
        numero_cargador: Texto del wizard (serie / descripción).
        accesorio_cargador: Checkbox “Cargador” del formato.

    Efectos secundarios:
        UPDATE de DetalleEquipo (campos de cargador) en el alias de la orden.
    """
    try:
        detalle = orden.detalle_equipo
    except (ObjectDoesNotExist, AttributeError):
        logger.warning(
            'No hay DetalleEquipo para orden %s; no se sincroniza cargador',
            getattr(orden, 'numero_orden_interno', orden.pk),
        )
        return

    numero = (numero_cargador or '').strip()[:MAX_NUMERO_CARGADOR]
    campos: list[str] = []

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Solo tocamos los campos que realmente cambian para no disparar
    # señales/save() innecesarios en un modelo gordo.
    if numero and detalle.numero_serie_cargador != numero:
        detalle.numero_serie_cargador = numero
        campos.append('numero_serie_cargador')

    debe_marcar_cargador = bool(numero) or bool(accesorio_cargador)
    if debe_marcar_cargador and not detalle.tiene_cargador:
        detalle.tiene_cargador = True
        campos.append('tiene_cargador')

    if not campos:
        return

    detalle.save(update_fields=campos)
    logger.info(
        'Cargador sincronizado a detalle de orden %s (campos=%s)',
        orden.numero_orden_interno,
        ','.join(campos),
    )
