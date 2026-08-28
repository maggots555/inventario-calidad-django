"""
Notificaciones al cerrar la respuesta del cliente en una cotización.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando el cliente termina de responder (todas las piezas/servicios), la
solicitud queda en uno de estos estados:

- totalmente_aprobada / parcialmente_aprobada CON piezas aceptadas
  → avisar a Compras (pedir al proveedor y Generar compras).
- totalmente_aprobada / parcialmente_aprobada SOLO con servicios
  (el cliente no aceptó piezas) → avisar al responsable de seguimiento
  (el servicio ya quedó en la orden; no se avisa a Compras).
- totalmente_rechazada → avisar a Compras + técnico asignado +
  responsable de seguimiento (si hay orden ST).

Canales (mismo patrón que la cotización «sin orden»):
1. Push al dispositivo
2. Campanita interna (BD)
3. Email en segundo plano vía Celery (no bloquea al usuario)

Se llama desde SolicitudCotizacion.actualizar_estado_segun_lineas()
solo cuando el estado *cambia* a uno de esos cierres.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterable, List, Optional, Set

from django.urls import reverse

if TYPE_CHECKING:
    from almacen.models import SolicitudCotizacion
    from inventario.models import Empleado

logger = logging.getLogger('almacen')


def obtener_empleados_compras() -> List['Empleado']:
    """
    Empleados activos con rol Compras y usuario de sistema activo.

    Returns:
        Lista de Empleado (puede estar vacía).
    """
    from inventario.models import Empleado

    return list(
        Empleado.objects.filter(
            rol='compras',
            user__is_active=True,
        ).select_related('user')
    )


def obtener_destinatarios_rechazo(solicitud: 'SolicitudCotizacion') -> List['Empleado']:
    """
    Destinatarios del rechazo: Compras + técnico + responsable (deduplicados).

    EXPLICACIÓN: si el técnico también tiene rol compras, o si técnico y
    responsable son la misma persona, solo se notifica una vez (por user_id).

    Args:
        solicitud: Solicitud que quedó totalmente_rechazada.

    Returns:
        Lista de Empleado únicos con user activo.
    """
    destinatarios: List[Empleado] = []
    vistos: Set[int] = set()

    def _agregar(empleado: Optional[Empleado]) -> None:
        # Paso a paso: sin empleado, sin user o user inactivo → no agregar
        if empleado is None:
            return
        user = getattr(empleado, 'user', None)
        if user is None or not user.is_active:
            return
        if user.pk in vistos:
            return
        vistos.add(user.pk)
        destinatarios.append(empleado)

    for comprador in obtener_empleados_compras():
        _agregar(comprador)

    orden = getattr(solicitud, 'orden_servicio', None)
    if orden is not None:
        # Técnico asignado (FK obligatorio en OrdenServicio, pero por seguridad)
        _agregar(getattr(orden, 'tecnico_asignado_actual', None))
        # Responsable de seguimiento (nullable)
        _agregar(getattr(orden, 'responsable_seguimiento', None))

    return destinatarios


def _url_detalle_solicitud(solicitud: 'SolicitudCotizacion') -> str:
    """Ruta relativa al detalle de la solicitud (push / campanita)."""
    return reverse(
        'almacen:detalle_solicitud_cotizacion',
        kwargs={'pk': solicitud.pk},
    )


def _resumen_cliente_solicitud(solicitud: 'SolicitudCotizacion') -> str:
    """Texto corto cliente + identificador para el mensaje push."""
    cliente = (solicitud.nombre_cliente or '').strip() or 'Sin nombre'
    if solicitud.numero_orden_cliente:
        ref = solicitud.numero_orden_cliente
    elif solicitud.service_tag:
        ref = f'S/T: {solicitud.service_tag}'
    else:
        ref = solicitud.numero_solicitud or f'#{solicitud.pk}'
    return f'Cliente: {cliente} — {ref}'


def enviar_push_y_campanita(
    empleados: Iterable['Empleado'],
    *,
    titulo: str,
    mensaje: str,
    url: str,
    app_origen: str = 'almacen',
    requiere_accion: bool = True,
) -> int:
    """
    Envía push + campanita a cada empleado (fallos aislados por persona).

    Args:
        empleados: Destinatarios con user activo.
        titulo: Título corto de la notificación.
        mensaje: Cuerpo del aviso.
        url: Ruta relativa al hacer clic.
        app_origen: etiqueta de la app que dispara (campanita / logs).
        requiere_accion: True (default) = pestaña «Por hacer»; False = «Avisos».

    Returns:
        Cantidad de empleados a los que se intentó notificar.
    """
    from notificaciones.push_service import enviar_push_a_usuario
    from notificaciones.utils import notificar_info

    contador = 0
    for empleado in empleados:
        contador += 1
        user = empleado.user
        nombre = getattr(empleado, 'nombre_completo', str(empleado))
        try:
            enviar_push_a_usuario(
                usuario=user,
                titulo=titulo,
                mensaje=mensaje,
                url=url,
            )
        except Exception as push_err:
            logger.warning(
                '[NOTIF-COTIZ] Error push a %s: %s',
                nombre,
                push_err,
            )
        try:
            notificar_info(
                titulo=titulo,
                mensaje=mensaje,
                usuario=user,
                url=url,
                app_origen=app_origen,
                requiere_accion=requiere_accion,
            )
        except Exception as notif_err:
            logger.warning(
                '[NOTIF-COTIZ] Error campanita a %s: %s',
                nombre,
                notif_err,
            )
    return contador


def obtener_responsable_seguimiento_activo(
    solicitud: 'SolicitudCotizacion',
) -> Optional['Empleado']:
    """
    Responsable de seguimiento de la orden, si tiene usuario de sistema activo.

    Args:
        solicitud: Solicitud con o sin orden_servicio.

    Returns:
        Empleado o None.
    """
    orden = getattr(solicitud, 'orden_servicio', None)
    if orden is None:
        return None
    empleado = getattr(orden, 'responsable_seguimiento', None)
    if empleado is None:
        return None
    user = getattr(empleado, 'user', None)
    if user is None or not user.is_active:
        return None
    return empleado


def solicitud_tiene_piezas_aprobadas(solicitud: 'SolicitudCotizacion') -> bool:
    """
    True si el cliente aceptó al menos una pieza (hay algo que comprar).

    Args:
        solicitud: Solicitud ya cerrada (parcial/total aprobada).

    Returns:
        bool: True si existe LineaCotizacion con estado_cliente='aprobada'.
    """
    return solicitud.lineas.filter(estado_cliente='aprobada').exists()


def notificar_cotizacion_aceptada(solicitud: 'SolicitudCotizacion') -> None:
    """
    Avisa quién debe continuar tras una aceptación total o parcial.

    Efectos secundarios:
        - Si hay piezas aprobadas: push + campanita + email Celery a Compras.
        - Si solo hay servicios aceptados: push + campanita al responsable
          de seguimiento (Front). No se avisa a Compras.

    Args:
        solicitud: Solicitud en totalmente_aprobada o parcialmente_aprobada.
    """
    if solicitud_tiene_piezas_aprobadas(solicitud):
        _notificar_aceptacion_a_compras(solicitud)
        return
    _notificar_aceptacion_solo_servicios(solicitud)


def _notificar_aceptacion_a_compras(solicitud: 'SolicitudCotizacion') -> None:
    """
    Camino clásico: el cliente aceptó piezas y Compras debe pedirlas.

    Args:
        solicitud: Solicitud con al menos una LineaCotizacion aprobada.
    """
    from config.paises_config import get_pais_actual
    from almacen.tasks import notificar_compras_cotizacion_aceptada_task

    compradores = obtener_empleados_compras()
    if not compradores:
        logger.info(
            '[NOTIF-COTIZ] Aceptación %s: no hay empleados de Compras activos',
            solicitud.numero_solicitud,
        )
        return

    url = _url_detalle_solicitud(solicitud)
    parcial = solicitud.estado == 'parcialmente_aprobada'
    tipo = 'parcialmente' if parcial else 'totalmente'
    titulo = f'Cotización {tipo} aceptada: {solicitud.numero_solicitud}'
    mensaje = (
        f'{_resumen_cliente_solicitud(solicitud)}. '
        f'Revisa las piezas aceptadas, solicítalas al proveedor y usa '
        f'«Generar compras» cuando las hayas pedido.'
    )

    enviados = enviar_push_y_campanita(
        compradores,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
    )

    db_alias = get_pais_actual()['db_alias']
    notificar_compras_cotizacion_aceptada_task.delay(
        solicitud.pk,
        db_alias=db_alias,
    )
    logger.info(
        '[NOTIF-COTIZ] Aceptación %s: push/campanita a %s compra(s); email encolado',
        solicitud.numero_solicitud,
        enviados,
    )


def _notificar_aceptacion_solo_servicios(solicitud: 'SolicitudCotizacion') -> None:
    """
    El cliente no aceptó piezas: el servicio ya quedó en la orden ST.

    Args:
        solicitud: Solicitud aprobada/parcial sin líneas de pieza aceptadas.
    """
    responsable = obtener_responsable_seguimiento_activo(solicitud)
    if responsable is None:
        logger.info(
            '[NOTIF-COTIZ] Aceptación solo-servicio %s: sin responsable de seguimiento activo',
            solicitud.numero_solicitud,
        )
        return

    url = _url_detalle_solicitud(solicitud)
    titulo = f'Servicio aceptado: {solicitud.numero_solicitud}'
    mensaje = (
        f'{_resumen_cliente_solicitud(solicitud)}. '
        f'El cliente aceptó solo servicio(s) adicional(es). '
        f'Ya quedaron registrados en la orden. '
        f'Cuando Front cargue el anticipo del 50%, se puede pasar a En reparación.'
    )
    enviados = enviar_push_y_campanita(
        [responsable],
        titulo=titulo,
        mensaje=mensaje,
        url=url,
    )
    logger.info(
        '[NOTIF-COTIZ] Aceptación solo-servicio %s: push/campanita a responsable (%s)',
        solicitud.numero_solicitud,
        enviados,
    )


def notificar_cotizacion_rechazada(solicitud: 'SolicitudCotizacion') -> None:
    """
    Avisa a Compras + técnico + responsable que la cotización fue rechazada.

    Sin orden vinculada solo notifica a Compras.
    Deduplica si la misma persona aparece en varios roles.

    Args:
        solicitud: Solicitud en totalmente_rechazada.
    """
    from config.paises_config import get_pais_actual
    from almacen.tasks import notificar_respuesta_cotizacion_rechazada_task

    # Prefetch de orden + FKs para no hacer N+1 al resolver destinatarios
    orden = getattr(solicitud, 'orden_servicio', None)
    if orden is not None:
        # Acceder a FKs fuerza carga si no venían en select_related
        _ = orden.tecnico_asignado_actual_id
        _ = orden.responsable_seguimiento_id

    destinatarios = obtener_destinatarios_rechazo(solicitud)
    if not destinatarios:
        logger.info(
            '[NOTIF-COTIZ] Rechazo %s: sin destinatarios (compras/técnico/responsable)',
            solicitud.numero_solicitud,
        )
        return

    url = _url_detalle_solicitud(solicitud)
    titulo = f'Cotización rechazada: {solicitud.numero_solicitud}'
    mensaje = (
        f'{_resumen_cliente_solicitud(solicitud)}. '
        f'El cliente rechazó todas las piezas/servicios. No generar compras.'
    )

    enviados = enviar_push_y_campanita(
        destinatarios,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
    )

    db_alias = get_pais_actual()['db_alias']
    notificar_respuesta_cotizacion_rechazada_task.delay(
        solicitud.pk,
        db_alias=db_alias,
    )
    logger.info(
        '[NOTIF-COTIZ] Rechazo %s: push/campanita a %s persona(s); email encolado',
        solicitud.numero_solicitud,
        enviados,
    )
