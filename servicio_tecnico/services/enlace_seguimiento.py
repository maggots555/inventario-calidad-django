"""
Enlace público de seguimiento para el cliente (portal /seguimiento/<token>/).

EXPLICACIÓN PARA PRINCIPIANTES:
------------------------------------------------
El cliente consulta el estatus de su orden con un link único, sin iniciar
sesión. Ese enlace se crea al mandar el correo de seguimiento; también lo
necesitamos al generar el PDF OOW/FL para dibujar el código QR.

Este módulo es el cerebro (get_or_create + URL). No vive en models.py
(regla fat models) ni en el generador PDF (ese archivo no escribe en BD).
"""

from __future__ import annotations

import logging
import secrets

from django.conf import settings

from config.paises_config import get_pais_actual
from servicio_tecnico.models import EnlaceSeguimientoCliente, OrdenServicio
from servicio_tecnico.services.sync_cargador_detalle import db_alias_de

logger = logging.getLogger(__name__)

# Fallback si el país activo no trae url_base (tests / misconfig).
_URL_BASE_FALLBACK = 'http://localhost:8000'


def obtener_o_crear_enlace_seguimiento(orden: OrdenServicio) -> EnlaceSeguimientoCliente:
    """
    Devuelve el enlace de la orden; lo crea si todavía no existe.

    Objetivo de negocio:
        El QR del PDF debe funcionar aunque el cliente no haya dejado email
        (el correo de seguimiento no se llegó a mandar).

    Args:
        orden: OrdenServicio dueña del enlace (relación 1 a 1).

    Returns:
        EnlaceSeguimientoCliente persistido.

    Efectos secundarios:
        Puede INSERTAR una fila `EnlaceSeguimientoCliente` (token nuevo).
        No envía correo.
    """
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Usamos el mismo alias de BD que ya tiene la orden (México, Chile…).
    # Si no, get_or_create caería en `default` y el QR apuntaría a otro país.
    db_alias = db_alias_de(orden)
    enlace, creado = EnlaceSeguimientoCliente.objects.using(db_alias).get_or_create(
        orden=orden,
        defaults={'token': secrets.token_urlsafe(32)},
    )
    if creado:
        logger.info(
            '[ENLACE_SEGUIMIENTO] Creado para orden=%s (origen PDF/formato)',
            orden.numero_orden_interno,
        )
    return enlace


def url_publica_seguimiento(enlace: EnlaceSeguimientoCliente) -> str:
    """
    Arma la URL absoluta del portal de seguimiento.

    Args:
        enlace: EnlaceSeguimientoCliente con token válido.

    Returns:
        str: ej. https://mexico.sigmasystem.work/seguimiento/<token>/

    Efectos secundarios:
        Ninguno.
    """
    # Misma receta que enviar_seguimiento_cliente_task: url_base del país activo.
    pais = get_pais_actual() or {}
    site_url = (
        pais.get('url_base')
        or getattr(settings, 'SITE_URL', None)
        or _URL_BASE_FALLBACK
    )
    base = str(site_url).rstrip('/')
    return f'{base}/seguimiento/{enlace.token}/'


def url_seguimiento_de_orden(orden: OrdenServicio) -> str | None:
    """
    URL pública si la orden ya tiene enlace; None si aún no existe.

    El PDF llama esto (solo lectura). Crear el enlace es trabajo de
    `obtener_o_crear_enlace_seguimiento` en el servicio de finalizar.

    Args:
        orden: OrdenServicio (puede o no tener `enlace_seguimiento`).

    Returns:
        str | None

    Efectos secundarios:
        Ninguno sobre BD (sí hace un SELECT del OneToOne si no está en caché).
    """
    # getattr con default: el OneToOne inexistente lanza AttributeError
    # (RelatedObjectDoesNotExist). Así no truena el PDF.
    enlace = getattr(orden, 'enlace_seguimiento', None)
    if enlace is None:
        return None
    return url_publica_seguimiento(enlace)
