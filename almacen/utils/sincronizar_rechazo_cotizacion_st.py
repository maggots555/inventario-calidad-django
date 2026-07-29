"""
Sincronización de rechazo total Almacén → Cotización ST + feedback opcional.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando Front/Compras rechaza TODA la cotización desde Almacén, necesitamos:

1. Escribir en la Cotización de Servicio Técnico el motivo de catálogo
   (`motivo_rechazo`) y el detalle con plantilla (`detalle_rechazo`).
2. Opcionalmente crear un FeedbackCliente y encolar el correo Celery,
   igual que cuando se rechaza desde detalle_orden en ST.

Este módulo concentra esa lógica para no hinchar las vistas
y para poder testearla sola. El modal de catálogo ST se muestra
cuando la solicitud queda en estado ``totalmente_rechazada``,
no al rechazar una sola pieza.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Optional

from django.core.signing import TimestampSigner
from django.utils import timezone

from config.constants import (
    MOTIVO_RECHAZO_COTIZACION,
    MOTIVOS_RECHAZO_CON_FEEDBACK,
    MOTIVOS_RECHAZO_VIGENCIA_VENCIDA,
)

if TYPE_CHECKING:
    from almacen.models import SolicitudCotizacion
    from inventario.models import Empleado
    from servicio_tecnico.models import Cotizacion, FeedbackCliente, OrdenServicio

logger = logging.getLogger('almacen')

# Diccionario clave → etiqueta legible (ej. 'costo_alto' → 'Costo muy elevado')
_LABELS_MOTIVO_RECHAZO = dict(MOTIVO_RECHAZO_COTIZACION)


def label_motivo_rechazo(motivo_clave: str) -> str:
    """
    Devuelve el texto legible del motivo de catálogo ST.

    Args:
        motivo_clave: Clave del choice (ej. 'costo_alto').

    Returns:
        Etiqueta para mostrar / guardar en líneas y piezas.
    """
    return _LABELS_MOTIVO_RECHAZO.get(motivo_clave, motivo_clave)


def motivo_rechazo_es_valido(motivo_clave: str) -> bool:
    """True si la clave existe en MOTIVO_RECHAZO_COTIZACION."""
    return bool(motivo_clave) and motivo_clave in _LABELS_MOTIVO_RECHAZO


def orden_admite_cotizacion_st(orden: Optional['OrdenServicio']) -> bool:
    """
    True si la orden usa Cotizacion/PiezaCotizada de ST (no FL- venta_mostrador).

    EXPLICACIÓN: en órdenes FL- el flujo va a VentaMostrador; no debe crearse
    una Cotizacion ST vacía desde Almacén.
    """
    if orden is None:
        return False
    return getattr(orden, 'tipo_servicio', '') != 'venta_mostrador'


def obtener_email_cliente_solicitud(solicitud: 'SolicitudCotizacion') -> str:
    """
    Resuelve el email del cliente para feedback / vigencia.

    Prioridad: DetalleEquipo.email_cliente (si hay orden) → solicitud.email_cliente.
    Ignora el placeholder 'cliente@ejemplo.com' que usa ST cuando no hay email real.
    """
    email = ''
    orden = solicitud.orden_servicio
    if orden is not None:
        detalle = getattr(orden, 'detalle_equipo', None)
        if detalle is not None:
            email = (getattr(detalle, 'email_cliente', '') or '').strip()
    if not email:
        email = (getattr(solicitud, 'email_cliente', '') or '').strip()
    if email == 'cliente@ejemplo.com':
        return ''
    return email


def solicitud_requiere_motivo_rechazo_st(solicitud: 'SolicitudCotizacion') -> bool:
    """
    True si la solicitud está totalmente rechazada y aún falta el motivo de catálogo en ST.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    El botón/modal de motivo ST aparece en Acciones cuando:
    - estado = totalmente_rechazada
    - hay orden de servicio vinculada (no FL-)
    - la Cotizacion ST no tiene motivo_rechazo (o aún no existe la cotización)
    """
    if solicitud.estado != 'totalmente_rechazada':
        return False
    if not solicitud.orden_servicio_id:
        return False
    if not orden_admite_cotizacion_st(solicitud.orden_servicio):
        return False

    from servicio_tecnico.models import Cotizacion

    try:
        cotizacion = Cotizacion.objects.get(orden_id=solicitud.orden_servicio_id)
    except Cotizacion.DoesNotExist:
        # Sin cotización ST aún: igual hay que registrar (se crea al guardar)
        return True

    return not bool((cotizacion.motivo_rechazo or '').strip())


# Máximo de caracteres del detalle precargado desde piezas/servicios
_MAX_DETALLE_RECHAZO_ITEMS = 2000


def admite_motivo_rechazo_almacen(solicitud: 'SolicitudCotizacion') -> bool:
    """
    True si el rechazo total se tipifica en la cabecera de Almacén (no en ST).

    Aplica cuando no hay orden, o la orden es venta_mostrador (FL-):
    no se crea Cotizacion ST ni FeedbackCliente.
    """
    if solicitud.estado != 'totalmente_rechazada':
        return False
    # EXPLICACIÓN: si hay camino ST válido, el modal de ST manda; aquí no.
    return not orden_admite_cotizacion_st(solicitud.orden_servicio)


def solicitud_requiere_motivo_rechazo_almacen(
    solicitud: 'SolicitudCotizacion',
) -> bool:
    """
    True si falta tipificar el rechazo en SolicitudCotizacion (sin orden ST).

    Condiciones:
    - estado = totalmente_rechazada
    - no admite flujo Cotizacion ST (sin orden o FL-)
    - motivo_rechazo de la solicitud aún vacío
    """
    if not admite_motivo_rechazo_almacen(solicitud):
        return False
    return not bool((solicitud.motivo_rechazo or '').strip())


def armar_detalle_rechazo_desde_items(solicitud: 'SolicitudCotizacion') -> str:
    """
    Concatena motivos de líneas y servicios rechazados para precargar el detalle.

    Formato por renglón:
        Pieza: HDD — costo alto
        Servicio: Limpieza — no autorizado

    Salta ítems sin motivo; recorta a ``_MAX_DETALLE_RECHAZO_ITEMS`` caracteres.

    Args:
        solicitud: Solicitud de cotización de Almacén.

    Returns:
        Texto multilínea listo para el textarea (puede ser vacío).
    """
    partes: list[str] = []

    # EXPLICACIÓN: solo líneas ya rechazadas; el motivo por línea es texto libre
    lineas_rechazadas = solicitud.lineas.filter(estado_cliente='rechazada')
    for linea in lineas_rechazadas:
        motivo = (linea.motivo_rechazo or '').strip()
        if not motivo:
            continue
        nombre = (linea.descripcion_pieza or '').strip() or f'Línea #{linea.numero_linea}'
        partes.append(f'Pieza: {nombre} — {motivo}')

    # Servicios adicionales rechazados (mismo patrón)
    servicios_rechazados = solicitud.servicios_adicionales.filter(
        estado_cliente='rechazada',
    )
    for servicio in servicios_rechazados:
        motivo = (servicio.motivo_rechazo or '').strip()
        if not motivo:
            continue
        nombre = servicio.get_tipo_servicio_display()
        partes.append(f'Servicio: {nombre} — {motivo}')

    texto = '\n'.join(partes)
    if len(texto) > _MAX_DETALLE_RECHAZO_ITEMS:
        return texto[: _MAX_DETALLE_RECHAZO_ITEMS - 1] + '…'
    return texto


def guardar_motivo_rechazo_solicitud(
    solicitud: 'SolicitudCotizacion',
    motivo_clave: str,
    detalle: str = '',
) -> 'SolicitudCotizacion':
    """
    Guarda motivo/detalle de catálogo en la cabecera de Almacén (sin tocar ST).

    Args:
        solicitud: Solicitud totalmente rechazada sin camino ST.
        motivo_clave: Clave de MOTIVO_RECHAZO_COTIZACION.
        detalle: Texto libre / plantilla / resumen de ítems.

    Returns:
        La misma solicitud refrescada tras el save.

    Raises:
        ValueError: si el motivo no está en el catálogo.
    """
    if not motivo_rechazo_es_valido(motivo_clave):
        raise ValueError(f'Motivo de rechazo inválido: {motivo_clave!r}')

    # EXPLICACIÓN: solo campos de cabecera Almacén; no crea orden ni Cotizacion
    solicitud.motivo_rechazo = motivo_clave
    solicitud.detalle_rechazo = detalle or ''
    solicitud.save(update_fields=['motivo_rechazo', 'detalle_rechazo'])
    solicitud.refresh_from_db()

    logger.info(
        '[RECHAZO_ALM] Solicitud %s motivo=%s (sin Cotizacion ST)',
        solicitud.numero_solicitud,
        motivo_clave,
    )
    return solicitud


def mensaje_flash_tras_rechazo_total(solicitud: 'SolicitudCotizacion') -> str:
    """
    Texto del messages.info tras quedar ``totalmente_rechazada``.

    Con orden ST válida → pide motivo en catálogo ST.
    Sin orden / FL- → pide tipificar en Acciones (cabecera Almacén).
    """
    base = 'La cotización quedó totalmente rechazada. '
    if orden_admite_cotizacion_st(solicitud.orden_servicio):
        return base + 'Registra el motivo de catálogo de Servicio Técnico.'
    return base + 'Registra el motivo de rechazo en Acciones.'


def sincronizar_cabecera_rechazo_st(
    solicitud: 'SolicitudCotizacion',
    motivo_clave: str,
    detalle_rechazo: str = '',
    *,
    empleado: Optional['Empleado'] = None,
) -> Optional['Cotizacion']:
    """
    Escribe motivo/detalle de rechazo en la Cotización ST vinculada.

    Efectos secundarios:
        - Cotizacion.usuario_acepto = False
        - Cotizacion.motivo_rechazo / detalle_rechazo / fecha_respuesta
        - Si no existe Cotizacion (y la orden la admite), la crea
        - HistorialOrden con el motivo registrado

    Args:
        solicitud: Solicitud de Almacén (debe tener orden_servicio).
        motivo_clave: Clave del catálogo ST.
        detalle_rechazo: Texto libre / plantilla editada.
        empleado: Quién registra (para historial; opcional).

    Returns:
        Cotizacion actualizada, o None si no hay orden / es FL-.
    """
    from servicio_tecnico.models import Cotizacion, HistorialOrden

    orden = solicitud.orden_servicio
    if orden is None:
        return None
    if not orden_admite_cotizacion_st(orden):
        logger.info(
            '[RECHAZO_ST] Orden %s es venta_mostrador: no se escribe Cotizacion ST',
            orden.numero_orden_interno,
        )
        return None

    cotizacion, creada = Cotizacion.objects.get_or_create(orden=orden)
    if creada:
        logger.info(
            '[RECHAZO_ST] Cotizacion ST creada al registrar rechazo (orden %s)',
            orden.numero_orden_interno,
        )

    # EXPLICACIÓN: la cabecera ST es la que leen dashboards/ML/feedback;
    # las piezas ya se sincronizan en LineaCotizacion.rechazar().
    cotizacion.usuario_acepto = False
    cotizacion.motivo_rechazo = motivo_clave
    cotizacion.detalle_rechazo = detalle_rechazo or ''
    if not cotizacion.fecha_respuesta:
        cotizacion.fecha_respuesta = timezone.now()
    cotizacion.save(
        update_fields=[
            'usuario_acepto',
            'motivo_rechazo',
            'detalle_rechazo',
            'fecha_respuesta',
        ]
    )

    etiqueta = label_motivo_rechazo(motivo_clave)
    comentario = (
        f'Cliente RECHAZÓ la cotización (registrado desde Almacén) — '
        f'Motivo: {etiqueta}'
    )
    if detalle_rechazo:
        comentario += f' | Detalle: {detalle_rechazo[:500]}'

    HistorialOrden.objects.create(
        orden=orden,
        tipo_evento='cotizacion',
        comentario=comentario,
        usuario=empleado,
        es_sistema=False,
    )

    logger.info(
        '[RECHAZO_ST] Cotizacion ST orden=%s motivo=%s',
        orden.numero_orden_interno,
        motivo_clave,
    )
    return cotizacion


def procesar_feedback_rechazo_desde_almacen(
    solicitud: 'SolicitudCotizacion',
    motivo_clave: str,
    *,
    enviar_feedback: bool,
    empleado: Optional['Empleado'] = None,
    usuario_id: Optional[int] = None,
) -> dict:
    """
    Crea FeedbackCliente (o reutiliza uno existente) y encola el correo.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    - Motivos en MOTIVOS_RECHAZO_CON_FEEDBACK → FeedbackCliente + task rechazo
    - Motivo falta_de_respuesta → task vigencia (sin token)
    - Otros / sin email / checkbox OFF → no hace nada
    - Si ya existe FeedbackCliente tipo rechazo para la orden, NO se crea otro:
      se reutiliza el mismo token (evita duplicados al editar/reenviar).

    Args:
        solicitud: Solicitud rechazada.
        motivo_clave: Motivo de catálogo ST.
        enviar_feedback: True si el checkbox del modal estaba marcado.
        empleado: Empleado que registra (FK enviado_por).
        usuario_id: PK del User para Celery (auditoría).

    Returns:
        Dict con claves: enviado (bool), tipo ('feedback'|'vigencia'|''),
        mensaje (str para messages), feedback_id (int|None).
    """
    resultado = {
        'enviado': False,
        'tipo': '',
        'mensaje': '',
        'feedback_id': None,
    }

    if not enviar_feedback:
        resultado['mensaje'] = 'Correo de feedback no solicitado.'
        return resultado

    orden = solicitud.orden_servicio
    if orden is None:
        resultado['mensaje'] = 'Sin orden ST: no se puede enviar feedback.'
        return resultado
    if not orden_admite_cotizacion_st(orden):
        resultado['mensaje'] = (
            'Órdenes de venta mostrador no usan feedback de cotización ST.'
        )
        return resultado

    email = obtener_email_cliente_solicitud(solicitud)
    if not email:
        resultado['mensaje'] = (
            'No hay email del cliente: el rechazo se guardó, pero no se envió correo.'
        )
        return resultado

    from config.paises_config import get_pais_actual

    db_alias = get_pais_actual()['db_alias']

    # --- Feedback con link (encuesta de rechazo) ---
    if motivo_clave in MOTIVOS_RECHAZO_CON_FEEDBACK:
        feedback, creado = _obtener_o_crear_feedback_rechazo(
            orden=orden,
            motivo_clave=motivo_clave,
            empleado=empleado,
        )
        from servicio_tecnico.tasks import enviar_feedback_rechazo_task

        # EXPLICACIÓN: db_alias es obligatorio en Celery multi-tenant
        enviar_feedback_rechazo_task.delay(
            feedback_id=feedback.pk,
            usuario_id=usuario_id,
            db_alias=db_alias,
        )
        if creado:
            mensaje = f'Correo de feedback de rechazo encolado para {email}.'
        elif feedback.correo_enviado:
            mensaje = (
                f'Reenvío de feedback encolado para {email} '
                f'(se reutiliza el mismo enlace).'
            )
        else:
            mensaje = (
                f'Correo de feedback pendiente re-encolado para {email}.'
            )
        resultado.update({
            'enviado': True,
            'tipo': 'feedback',
            'feedback_id': feedback.pk,
            'mensaje': mensaje,
        })
        return resultado

    # --- Vigencia vencida (solo informativo) ---
    if motivo_clave in MOTIVOS_RECHAZO_VIGENCIA_VENCIDA:
        from servicio_tecnico.tasks import enviar_vigencia_vencida_task

        enviar_vigencia_vencida_task.delay(
            orden_id=orden.pk,
            usuario_id=usuario_id,
            db_alias=db_alias,
        )
        resultado.update({
            'enviado': True,
            'tipo': 'vigencia',
            'mensaje': (
                f'Correo de cotización vencida encolado para {email}.'
            ),
        })
        return resultado

    resultado['mensaje'] = (
        'Este motivo de rechazo no envía correo al cliente.'
    )
    return resultado


def _obtener_o_crear_feedback_rechazo(
    *,
    orden,
    motivo_clave: str,
    empleado: Optional['Empleado'],
) -> tuple['FeedbackCliente', bool]:
    """
    Reutiliza el FeedbackCliente tipo rechazo más reciente de la orden, o crea uno.

    Returns:
        (feedback, creado) — creado=True solo si se insertó una fila nueva.
    """
    from servicio_tecnico.models import Cotizacion, FeedbackCliente

    existente = (
        FeedbackCliente.objects.filter(orden=orden, tipo='rechazo')
        .order_by('-pk')
        .first()
    )
    if existente is not None:
        # Actualizar snapshot si el usuario cambió el motivo al editar
        campos = []
        if existente.motivo_rechazo_snapshot != motivo_clave:
            existente.motivo_rechazo_snapshot = motivo_clave
            campos.append('motivo_rechazo_snapshot')
        if empleado is not None and existente.enviado_por_id != getattr(empleado, 'pk', None):
            existente.enviado_por = empleado
            campos.append('enviado_por')
        if campos:
            existente.save(update_fields=campos)
        return existente, False

    cotizacion = Cotizacion.objects.get(orden=orden)
    token_firmado = TimestampSigner().sign(str(uuid.uuid4()))
    nuevo = FeedbackCliente.objects.create(
        orden=orden,
        cotizacion=cotizacion,
        token=token_firmado,
        tipo='rechazo',
        motivo_rechazo_snapshot=motivo_clave,
        enviado_por=empleado,
    )
    return nuevo, True
