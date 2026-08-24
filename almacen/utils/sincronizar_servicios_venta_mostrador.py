"""
Copia servicios adicionales aceptados a Venta Mostrador en Servicio Técnico.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Las piezas de reparación se sincronizan a ST en cuanto el cliente las acepta
(PiezaCotizada). Los servicios (limpieza, respaldo, paquetes) deben hacer lo
mismo: al CERRAR la respuesta del cliente (todas las líneas con sí/no) se
copian a VentaMostrador para que Front cobre el 50% correcto.

Este módulo es la ÚNICA puerta de ese traslado. Lo llaman:

1. actualizar_estado_segun_lineas() al cerrar la respuesta.
2. vincular_orden() si se aceptó antes de tener orden.
3. generar_compras_solicitud() como red de seguridad (solicitudes viejas).

No crea CompraProducto. Eso sigue siendo «Generar Compras».
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from django.db import transaction
from django.utils import timezone

from almacen.utils.recotizacion import resolver_db_alias

if TYPE_CHECKING:
    from almacen.models import SolicitudCotizacion
    from servicio_tecnico.models import VentaMostrador

logger = logging.getLogger('almacen')

# Cliente ya cerró con algo aceptado (aún no se compraron piezas).
ESTADOS_SOLICITUD_CON_ACEPTACION = (
    'totalmente_aprobada',
    'parcialmente_aprobada',
)

# Red de seguridad: «Generar Compras» puede haber pasado la solicitud a
# en_proceso/completada ANTES de copiar servicios (casos viejos).
ESTADOS_PUEDEN_COPIAR_VM = ESTADOS_SOLICITUD_CON_ACEPTACION + (
    'en_proceso',
    'completada',
)


def materializar_servicios_aprobados_en_st(
    solicitud: 'SolicitudCotizacion',
) -> Optional['VentaMostrador']:
    """
    Traslada servicios adicionales aprobados a VentaMostrador en la orden ST.

    Objetivo de negocio:
        Que Front vea el costo de limpieza/paquetes en el recuadro de pagos
        (y el 50%) en cuanto confirma lo que aceptó el cliente, sin esperar
        a que Compras pida las piezas al proveedor.

    Args:
        solicitud: SolicitudCotizacion. Puede no tener orden aún.

    Returns:
        VentaMostrador creado/actualizado, o None si no había nada que copiar
        (sin orden, sin servicios aprobados, o ya estaban en ST).

    Efectos secundarios:
        - Crea/actualiza VentaMostrador y marca servicios como compra_generada.
        - Si no hay piezas pendientes de compra Y ya está el anticipo del 50%:
          pasa a completada y la orden ST a «En reparación».
        - Si falta el 50%, deja la Venta Mostrador para el cobro y no cierra.
        - No crea CompraProducto. Si falla, no revierte la aceptación del
          cliente (se registra el error y «Generar Compras» puede reintentar).
    """
    if solicitud.estado not in ESTADOS_PUEDEN_COPIAR_VM:
        return None

    # Paso: sin orden no hay dónde colgar la Venta Mostrador.
    # Al vincular/crear la orden se vuelve a llamar este util.
    if not solicitud.orden_servicio_id:
        logger.info(
            '[SYNC-SERVICIOS-ST] Solicitud %s aprobada sin orden; '
            'VentaMostrador se creará al vincular.',
            solicitud.numero_solicitud,
        )
        return None

    db_alias = resolver_db_alias(solicitud)
    venta = None
    try:
        # Paso: misma conexión que la solicitud (multi-país). Si copia o
        # cierre fallan, no queda medio servicio marcado compra_generada.
        with transaction.atomic(using=db_alias):
            venta = solicitud.generar_venta_mostrador()
            _completar_solicitud_si_solo_servicios(solicitud, venta)
    except Exception:
        logger.exception(
            '[SYNC-SERVICIOS-ST] Error al copiar servicios de %s a ST. '
            'La respuesta del cliente ya está guardada; se puede reintentar '
            'con Generar Compras.',
            solicitud.numero_solicitud,
        )
        return None

    if venta:
        logger.info(
            '[SYNC-SERVICIOS-ST] Solicitud %s: servicios copiados a '
            'VentaMostrador %s (orden %s).',
            solicitud.numero_solicitud,
            venta.folio_venta,
            solicitud.orden_servicio.numero_orden_interno,
        )
    return venta


def _completar_solicitud_si_solo_servicios(
    solicitud: 'SolicitudCotizacion',
    venta: Optional['VentaMostrador'],
) -> None:
    """
    Cierra solo-servicio si NO hay piezas por comprar y YA está el 50%.

    Args:
        solicitud: Solicitud con respuesta del cliente ya cerrada.
        venta: VentaMostrador recién creada, o None si no hubo servicios
            nuevos que copiar.

    Efectos secundarios:
        Puede pasar la solicitud a completada y la orden a reparación.
        No hace nada si faltan piezas, si no hay VM nueva, o si falta el 50%.
    """
    if solicitud.puede_generar_compras():
        return
    if venta is None:
        return
    cerrar_solicitud_solo_servicios(solicitud)


def cerrar_solicitud_solo_servicios(solicitud: 'SolicitudCotizacion') -> bool:
    """
    Completa la solicitud y pasa la orden a En reparación (solo servicios).

    Objetivo de negocio:
        El técnico no arranca hasta que Front cargó el anticipo del 50%.
        Si aún no alcanza, no cierra: el botón «Generar servicio» espera.

    Args:
        solicitud: Debe tener servicios ya en ST y ninguna pieza por comprar.

    Returns:
        bool: True si se cambió el estado de la orden a reparación.

    Efectos secundarios:
        solicitud.estado → completada; orden.estado → reparacion.
    """
    from almacen.utils.anticipo_solicitud import cubre_anticipo_50_solicitud

    if solicitud.puede_generar_compras():
        return False
    if not cubre_anticipo_50_solicitud(solicitud):
        logger.info(
            '[SYNC-SERVICIOS-ST] Solicitud %s: servicios en ST, pero falta '
            'el anticipo del 50%%; no se pasa a En reparación.',
            solicitud.numero_solicitud,
        )
        return False

    solicitud.refresh_from_db()
    if solicitud.estado in ESTADOS_SOLICITUD_CON_ACEPTACION:
        solicitud.estado = 'completada'
        solicitud.fecha_completada = timezone.now()
        solicitud.save(update_fields=['estado', 'fecha_completada'])

    from almacen.utils.sincronizar_estado_st import (
        sincronizar_estado_st_al_confirmar_servicios,
    )
    return sincronizar_estado_st_al_confirmar_servicios(solicitud)
