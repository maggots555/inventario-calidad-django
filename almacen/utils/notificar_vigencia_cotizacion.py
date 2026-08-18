"""
Avisos de vigencia vencida y de recotización solicitada
========================================================

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Este archivo decide QUIÉN se entera y CON QUÉ TEXTO cuando pasa algo con la
vigencia de una cotización. Hay dos momentos distintos:

1. VENCIÓ LA VIGENCIA (automático, una vez al día)
   La tarea diaria encuentra cotizaciones que pasaron los 5 días hábiles sin
   respuesta. Avisa a Recepción (que es quien habla con el cliente) y a
   Compras. Nadie tiene que hacer nada todavía: es un recordatorio de que hay
   que darle seguimiento antes de que el caso se enfríe.

2. SE PIDIÓ UNA RECOTIZACIÓN (manual, cuando alguien presiona el botón)
   El cliente reapareció y quiere continuar. Ahora sí Compras tiene trabajo:
   confirmar si la pieza sigue disponible y a qué precio.

Igual que en el resto de Almacén, se usan tres canales: push al celular,
campanita dentro del sistema y correo. Si un canal falla, los otros siguen:
perder un correo nunca debe romper la operación.

Autor: Sistema Integral de Gestión (SIGMA)
Fecha: Agosto 2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List

from django.urls import reverse

from almacen.utils.notificar_respuesta_cotizacion import (
    enviar_push_y_campanita,
    obtener_empleados_compras,
)

if TYPE_CHECKING:
    from almacen.models import SolicitudCotizacion
    from inventario.models import Empleado

logger = logging.getLogger('almacen')


# ============================================================================
# DESTINATARIOS
# ============================================================================

def obtener_empleados_recepcion() -> List['Empleado']:
    """
    Empleados activos con rol Recepcionista y usuario de sistema activo.

    Objetivo principal (contexto de negocio):
        Recepción (Front) es quien tiene el trato directo con el cliente, así
        que es la primera en enterarse de que una cotización se está enfriando.

    Returns:
        list[Empleado]: Puede venir vacía si nadie tiene ese rol.

    Efectos secundarios:
        Ninguno (una consulta de solo lectura).
    """
    from inventario.models import Empleado

    return list(
        Empleado.objects.filter(
            rol='recepcionista',
            activo=True,
            user__is_active=True,
        ).select_related('user')
    )


def _deduplicar_empleados(*grupos) -> List['Empleado']:
    """
    Junta varias listas de empleados sin repetir personas.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Una misma persona puede aparecer en dos listas (por ejemplo, si alguien de
    recepción también cubre compras). Sin este filtro recibiría la notificación
    dos veces. Comparamos por el ID del usuario, que es único.

    Args:
        *grupos: Una o más listas de Empleado.

    Returns:
        list[Empleado]: Lista combinada sin duplicados.

    Efectos secundarios:
        Ninguno.
    """
    vistos = set()
    resultado: List['Empleado'] = []

    for grupo in grupos:
        for empleado in grupo:
            user = getattr(empleado, 'user', None)
            # Sin usuario de sistema no hay a dónde mandar la notificación
            if user is None or user.pk in vistos:
                continue
            vistos.add(user.pk)
            resultado.append(empleado)

    return resultado


# ============================================================================
# TEXTOS Y ENLACES
# ============================================================================

def _url_detalle(solicitud: 'SolicitudCotizacion') -> str:
    """Ruta relativa al detalle de la solicitud (push y campanita)."""
    return reverse(
        'almacen:detalle_solicitud_cotizacion',
        kwargs={'pk': solicitud.pk},
    )


def _referencia_solicitud(solicitud: 'SolicitudCotizacion') -> str:
    """
    Identificador corto para que el usuario reconozca de qué caso hablamos.

    Args:
        solicitud: Cotización a describir.

    Returns:
        str: Número de orden del cliente, service tag o folio de la solicitud.
    """
    if solicitud.numero_orden_cliente:
        return solicitud.numero_orden_cliente
    if solicitud.service_tag:
        return f'S/T: {solicitud.service_tag}'
    return solicitud.numero_solicitud or f'#{solicitud.pk}'


# ============================================================================
# AVISO 1: LA VIGENCIA VENCIÓ
# ============================================================================

def notificar_vigencia_vencida(solicitud: 'SolicitudCotizacion') -> int:
    """
    Avisa a Recepción y Compras que una cotización perdió vigencia.

    Objetivo principal (contexto de negocio):
        Que nadie se entere tarde. Si el cliente no contestó en 5 días hábiles,
        Recepción debe llamarle; si ya no quiere, se cierra con el motivo
        "falta de respuesta"; si quiere seguir, se pide recotización.

    Args:
        solicitud (SolicitudCotizacion): Cotización cuya vigencia venció.

    Returns:
        int: Cantidad de personas notificadas.

    Efectos secundarios:
        Envía push y crea campanitas. No manda correo: es un recordatorio
        interno de bajo ruido que se repite para varias cotizaciones el mismo
        día, y saturar el buzón sería contraproducente.
    """
    destinatarios = _deduplicar_empleados(
        obtener_empleados_recepcion(),
        obtener_empleados_compras(),
    )

    if not destinatarios:
        logger.info(
            '[VIGENCIA] Sin destinatarios para avisar el vencimiento de %s',
            solicitud.numero_solicitud,
        )
        return 0

    referencia = _referencia_solicitud(solicitud)
    cliente = (solicitud.nombre_cliente or '').strip() or 'Sin nombre'

    titulo = f'Cotización vencida: {referencia}'
    mensaje = (
        f'La cotización {solicitud.numero_solicitud} ({cliente}) cumplió sus '
        f'5 días hábiles de vigencia sin respuesta del cliente. Contáctalo '
        f'para cerrar el caso o solicitar una recotización.'
    )

    return enviar_push_y_campanita(
        destinatarios,
        titulo=titulo,
        mensaje=mensaje,
        url=_url_detalle(solicitud),
    )


def procesar_solicitudes_vencidas() -> dict:
    """
    Busca cotizaciones vencidas sin avisar y notifica una sola vez.

    Objetivo principal (contexto de negocio):
        Es el cuerpo de la tarea diaria. Corre sobre la base de datos del país
        que Celery ya enrutó (por eso NO usa .using() aquí).

    Returns:
        dict: ``{'revisadas': int, 'notificadas': int}`` para los logs.

    Efectos secundarios:
        - Envía push y campanita por cada cotización vencida.
        - Marca ``aviso_vencimiento_enviado=True`` para no repetir el aviso
          mañana. La bandera se reinicia cuando arranca una ronda nueva.
    """
    from django.utils import timezone

    from almacen.models import SolicitudCotizacion
    from config.constants import ESTADOS_SOLICITUD_CON_VIGENCIA

    # Buscamos solo lo que realmente necesita aviso:
    # estado esperando respuesta + ya pasó la fecha límite + aún no se avisó
    vencidas = SolicitudCotizacion.objects.filter(
        estado__in=ESTADOS_SOLICITUD_CON_VIGENCIA,
        fecha_vencimiento_vigencia__lt=timezone.now(),
        aviso_vencimiento_enviado=False,
    )

    revisadas = 0
    notificadas = 0

    for solicitud in vencidas:
        revisadas += 1
        try:
            notificar_vigencia_vencida(solicitud)
            notificadas += 1
        except Exception as exc:
            # Si una falla (por ejemplo, push sin suscripción válida) seguimos
            # con las demás: una cotización problemática no debe frenar el job.
            logger.error(
                '[VIGENCIA] Error avisando vencimiento de %s: %s',
                solicitud.numero_solicitud,
                exc,
            )

        # La marcamos aunque el aviso haya fallado parcialmente, para no
        # spamear al equipo con el mismo caso todos los días.
        solicitud.aviso_vencimiento_enviado = True
        solicitud.save(update_fields=['aviso_vencimiento_enviado'])

    logger.info(
        '[VIGENCIA] Revisadas %s cotización(es) vencida(s), notificadas %s',
        revisadas,
        notificadas,
    )

    return {'revisadas': revisadas, 'notificadas': notificadas}


# ============================================================================
# AVISO 2: SE PIDIÓ UNA RECOTIZACIÓN
# ============================================================================

def notificar_recotizacion_a_compras(
    solicitud: 'SolicitudCotizacion',
    usuario=None,
) -> int:
    """
    Avisa a Compras que debe volver a cotizar (push y campanita).

    Objetivo principal (contexto de negocio):
        La solicitud acaba de regresar a borrador con una ronda nueva. Compras
        tiene que confirmar disponibilidad y capturar los costos actualizados.

    Args:
        solicitud (SolicitudCotizacion): Cotización que entró a ronda nueva.
        usuario (User | None): Quien pidió la recotización (aparece en el texto).

    Returns:
        int: Cantidad de compradores notificados.

    Efectos secundarios:
        Envía push y crea campanitas para el rol Compras.
    """
    compradores = obtener_empleados_compras()

    if not compradores:
        logger.info(
            '[RECOTIZACION] Sin empleados de Compras para avisar sobre %s',
            solicitud.numero_solicitud,
        )
        return 0

    referencia = _referencia_solicitud(solicitud)
    quien = getattr(usuario, 'get_full_name', lambda: '')() or getattr(
        usuario, 'username', 'Recepción'
    )

    titulo = f'Recotización solicitada: {referencia}'
    mensaje = (
        f'{quien} solicitó recotizar {solicitud.numero_solicitud} '
        f'(ronda {solicitud.ronda_cotizacion}). La cotización anterior venció; '
        f'confirma disponibilidad y actualiza los costos de las piezas.'
    )

    return enviar_push_y_campanita(
        compradores,
        titulo=titulo,
        mensaje=mensaje,
        url=_url_detalle(solicitud),
    )


def armar_destinatarios_email_recotizacion(
    solicitud: 'SolicitudCotizacion',
) -> List[str]:
    """
    Correos de Compras para el email de recotización.

    Args:
        solicitud (SolicitudCotizacion): Cotización en ronda nueva (se usa solo
            para dejar rastro en logs si no hay destinatarios).

    Returns:
        list[str]: Correos válidos, sin repetir.

    Efectos secundarios:
        Ninguno.
    """
    correos = []
    for comprador in obtener_empleados_compras():
        # Preferimos el correo del empleado; si no tiene, el del usuario
        email = (comprador.email or '').strip() or (
            comprador.user.email or ''
        ).strip()
        if email and email not in correos:
            correos.append(email)

    if not correos:
        logger.info(
            '[RECOTIZACION] Sin correos de Compras para %s',
            solicitud.numero_solicitud,
        )

    return correos
