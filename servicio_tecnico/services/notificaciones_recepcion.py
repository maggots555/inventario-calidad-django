"""
Aviso staff cuando el equipo está listo para recolección.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Cuando se suben fotos de egreso o la orden pasa a "finalizado", alguien del
staff debe enterarse para poder avisar al cliente (botón
"Notificar equipo disponible").

¿A quién le llega?
  - Fuera de garantía (OOW/FL, es_fuera_garantia=True):
      responsable_seguimiento, o todos los rol=recepcionista.
  - En garantía (es_fuera_garantia=False):
      todos los empleados con rol=dispatcher.

Hay DOS disparadores posibles (egreso y cambio a finalizado). Para no spamear,
usamos el flag `orden.aviso_recepcion_listo_enviado`: la primera llamada gana;
la segunda se omite (viceversa).

Canales:
  - Campanita in-app (`notificar_info`)
  - Web Push (`enviar_push_a_usuario`)

Efectos secundarios:
  - Crea Notificacion(es) + push
  - Marca aviso_recepcion_listo_enviado=True
  - Escribe HistorialOrden tipo sistema
"""

from __future__ import annotations

import logging
from typing import Literal

from django.db import transaction
from django.urls import reverse

logger = logging.getLogger('servicio_tecnico')

MotivoAviso = Literal['egreso', 'finalizado']


def notificar_recepcion_equipo_listo(orden, motivo: MotivoAviso = 'finalizado') -> bool:
    """
    Avisa al staff correcto de que el equipo está listo para recolectar.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El nombre histórico dice "recepcion", pero el destinatario depende de
    si la orden es OOW (recepción) o garantía (dispatchers).

    Args:
        orden: instancia de OrdenServicio (debe tener pk).
        motivo: 'egreso' si vino de subir fotos; 'finalizado' si vino de
            cambio de estado. Solo afecta el texto del historial.

    Returns:
        True si se envió el aviso; False si ya estaba avisado o no hay
        destinatarios / falló de forma controlada.
    """
    # Import local: evita ciclos al cargar apps (models ↔ services ↔ notificaciones).
    from notificaciones.push_service import enviar_push_a_usuario
    from notificaciones.utils import notificar_info
    from servicio_tecnico.models import OrdenServicio

    if not orden or not getattr(orden, 'pk', None):
        return False

    # ------------------------------------------------------------------
    # Anti-spam atómico: solo el primer aviso gana.
    # EXPLICACIÓN: update() en BD evita carrera si egreso y finalizado
    # disparan casi al mismo tiempo en el mismo request.
    # ------------------------------------------------------------------
    filas = OrdenServicio.objects.filter(
        pk=orden.pk,
        aviso_recepcion_listo_enviado=False,
    ).update(aviso_recepcion_listo_enviado=True)

    if filas == 0:
        logger.info(
            '[AVISO-EQUIPO-LISTO] Orden %s ya avisada — omitiendo (motivo=%s)',
            orden.pk,
            motivo,
        )
        return False

    # Mantener la instancia en memoria alineada con la BD.
    orden.aviso_recepcion_listo_enviado = True

    audiencia = _etiqueta_audiencia(orden)
    destinatarios = _resolver_destinatarios_aviso(orden)
    if not destinatarios:
        logger.warning(
            '[AVISO-EQUIPO-LISTO] Orden %s sin destinatarios (%s)',
            orden.pk,
            audiencia,
        )
        # El flag ya quedó en True para no reintentar en bucle; historial igual.
        _registrar_historial_aviso(orden, motivo, enviados=0, audiencia=audiencia)
        return False

    url_orden = reverse(
        'servicio_tecnico:detalle_orden',
        kwargs={'orden_id': orden.pk},
    ) + '#notificar-equipo-disponible'

    etiqueta, service_tag = _etiqueta_orden(orden)
    titulo = f'Equipo listo para avisar al cliente — {etiqueta}'
    mensaje = (
        f'La orden {etiqueta} (S/T: {service_tag}) está lista. '
        f'Notifica al cliente que puede recolectar el equipo.'
    )

    enviados = 0
    for empleado in destinatarios:
        usuario = getattr(empleado, 'user', None)
        if not usuario or not usuario.is_active:
            continue

        try:
            notificar_info(
                titulo=titulo,
                mensaje=mensaje,
                usuario=usuario,
                url=url_orden,
                app_origen='servicio_tecnico',
            )
        except Exception as exc:
            logger.warning(
                '[AVISO-EQUIPO-LISTO] Campanita falló para %s: %s',
                usuario.username,
                exc,
            )

        try:
            enviar_push_a_usuario(
                usuario=usuario,
                titulo=titulo,
                mensaje=mensaje,
                url=url_orden,
            )
        except Exception as exc:
            logger.warning(
                '[AVISO-EQUIPO-LISTO] Push falló para %s: %s',
                usuario.username,
                exc,
            )

        enviados += 1

    _registrar_historial_aviso(orden, motivo, enviados=enviados, audiencia=audiencia)
    logger.info(
        '[AVISO-EQUIPO-LISTO] Orden %s avisada (motivo=%s, audiencia=%s, destinatarios=%s)',
        orden.pk,
        motivo,
        audiencia,
        enviados,
    )
    return enviados > 0


def _etiqueta_audiencia(orden) -> str:
    """Texto corto para logs/historial según tipo de orden."""
    if getattr(orden, 'es_fuera_garantia', False):
        return 'recepción'
    return 'dispatchers'


def _resolver_destinatarios_aviso(orden) -> list:
    """
    Elige a quién avisar según garantía vs OOW.

    EXPLICACIÓN PARA PRINCIPIANTES:
    - OOW (fuera de garantía): el responsable de seguimiento (suele ser
      recepcionista). Si no hay, todos los recepcionistas activos.
    - Garantía: todos los dispatchers activos (mismo criterio que otros
      avisos de "orden lista" del sistema).

    Returns:
        Lista de Empleado con user cargado (select_related).
    """
    from inventario.models import Empleado

    # ------------------------------------------------------------------
    # GARANTÍA → dispatchers
    # ------------------------------------------------------------------
    if not getattr(orden, 'es_fuera_garantia', False):
        return list(
            Empleado.objects.filter(
                rol='dispatcher',
                user__is_active=True,
            ).select_related('user')
        )

    # ------------------------------------------------------------------
    # OOW / FL → responsable o recepcionistas
    # ------------------------------------------------------------------
    responsable = getattr(orden, 'responsable_seguimiento', None)
    if responsable is not None:
        # Puede venir sin select_related; recargar con user si hace falta.
        if responsable.user_id is None or getattr(responsable, 'user', None) is None:
            try:
                responsable = Empleado.objects.select_related('user').get(
                    pk=responsable.pk
                )
            except Empleado.DoesNotExist:
                responsable = None

        if responsable and responsable.user_id and responsable.user.is_active:
            return [responsable]

    return list(
        Empleado.objects.filter(
            rol='recepcionista',
            user__is_active=True,
        ).select_related('user')
    )


def _etiqueta_orden(orden) -> tuple[str, str]:
    """Folio visible y service tag para el mensaje."""
    try:
        detalle = orden.detalle_equipo
        etiqueta = detalle.orden_cliente or orden.numero_orden_interno
        service_tag = detalle.numero_serie or 'S/N no registrado'
    except Exception:
        etiqueta = orden.numero_orden_interno
        service_tag = 'S/N no registrado'
    return etiqueta, service_tag


def _registrar_historial_aviso(
    orden,
    motivo: MotivoAviso,
    enviados: int,
    audiencia: str,
) -> None:
    """Escribe en el timeline de la orden el aviso al staff correcto."""
    from servicio_tecnico.models import HistorialOrden

    etiqueta_motivo = (
        'imágenes de egreso'
        if motivo == 'egreso'
        else 'cambio a Finalizado / Listo para Entrega'
    )
    comentario = (
        f'Aviso a {audiencia}: equipo listo para notificar recolección '
        f'(disparador: {etiqueta_motivo}; destinatarios: {enviados})'
    )

    try:
        with transaction.atomic():
            HistorialOrden.objects.create(
                orden=orden,
                tipo_evento='sistema',
                comentario=comentario,
                usuario=None,
                es_sistema=True,
            )
    except Exception as exc:
        logger.warning(
            '[AVISO-EQUIPO-LISTO] No se pudo escribir historial orden %s: %s',
            orden.pk,
            exc,
        )
