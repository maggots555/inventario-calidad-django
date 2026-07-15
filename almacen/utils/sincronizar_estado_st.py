"""
Sincronización de estado de OrdenServicio (ST) desde cotizaciones de Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando Almacén notifica a Front, envía cotización al cliente o recibe respuesta,
la orden en Servicio Técnico debe reflejar el mismo hito de workflow.
Estas funciones centralizan ese cambio para no duplicar lógica en views y modelos.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from almacen.models import SolicitudCotizacion

logger = logging.getLogger('almacen')

# Solo avanzamos desde este estado para no pisar workflow posterior
# (esperando_piezas, reparacion, etc.).
ESTADO_ST_ESPERANDO_CLIENTE = 'cotizacion'

# Destino al avisar a Front que la cotización de proveedores ya está lista
ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR = 'cotizacion_recibida_proveedor'

# EXPLICACIÓN PARA PRINCIPIANTES:
# Al notificar a Front solo avanzamos desde estados previos al hito
# «Se Recibe Cotización de Proveedores». Nunca desde cotizacion, reparación, etc.
ESTADOS_ST_PERMITIDOS_PARA_NOTIFICAR_FRONT = (
    'almacen',
    'espera',
    'recepcion',
    'diagnostico',
    'equipo_diagnosticado',
    'diagnostico_enviado_cliente',
    'cotizacion_enviada_proveedor',
    'rechazada',  # Re-cotización tras rechazo: vuelve al hito de proveedores
)

# EXPLICACIÓN PARA PRINCIPIANTES:
# Al enviar/reenviar la cotización al cliente, SOLO podemos pasar a «cotizacion»
# desde estados previos (diagnóstico, armado de cotización, etc.) o desde
# «rechazada» (nueva propuesta). Nunca desde esperando_piezas, reparación, etc.
ESTADOS_ST_PERMITIDOS_PARA_ESPERAR_CLIENTE = (
    'almacen',
    'espera',
    'recepcion',
    'diagnostico',
    'equipo_diagnosticado',
    'diagnostico_enviado_cliente',
    'cotizacion_enviada_proveedor',
    'cotizacion_recibida_proveedor',
    'rechazada',  # Reenvío tras rechazo: reinicia espera de aprobación
)

# Mapeo: estado de SolicitudCotizacion → estado de OrdenServicio
MAPEO_RESPUESTA_SOLICITUD_A_ESTADO_ST = {
    'totalmente_aprobada': 'cliente_acepta_cotizacion',
    'parcialmente_aprobada': 'cliente_acepta_cotizacion',
    'totalmente_rechazada': 'rechazada',
}

# Etiquetas legibles para comentarios de historial
ETIQUETAS_ESTADO_ST = {
    'cliente_acepta_cotizacion': 'Cliente Acepta Cotización',
    'rechazada': 'Cotización Rechazada',
}

ETIQUETAS_RESPUESTA_SOLICITUD = {
    'totalmente_aprobada': 'totalmente aprobada',
    'parcialmente_aprobada': 'parcialmente aprobada',
    'totalmente_rechazada': 'totalmente rechazada',
}


def sincronizar_estado_st_al_notificar_front(
    solicitud: 'SolicitudCotizacion',
    usuario=None,
) -> bool:
    """
    Al notificar a Front desde Almacén, pone la orden ST en ``cotizacion_recibida_proveedor``.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando Compras termina de cotizar y avisa a recepción («Notificar a Front»),
    el hito correcto en Servicio Técnico es «Se Recibe Cotización de Proveedores».
    Si la solicitud no tiene orden vinculada, o la orden ya avanzó (esperando
    cliente, reparación, etc.), no se cambia el estado para no romper el flujo.

    Args:
        solicitud: SolicitudCotizacion (con o sin orden_servicio).
        usuario: User opcional; si tiene empleado, se asocia al historial.

    Returns:
        bool: True si se cambió el estado; False si no aplica o se omitió a propósito.
    """
    orden = getattr(solicitud, 'orden_servicio', None)
    if not orden:
        return False

    # Ya está en el destino: no duplicar historial en reenvíos del correo
    if orden.estado == ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR:
        return False

    # Guardia anti-regresión: no pisar estados posteriores del flujo
    if orden.estado not in ESTADOS_ST_PERMITIDOS_PARA_NOTIFICAR_FRONT:
        logger.info(
            f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno} en estado "
            f"'{orden.estado}'; notificar a Front NO cambia a "
            f"'{ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR}' "
            f"(solicitud {solicitud.numero_solicitud})."
        )
        return False

    estado_anterior = orden.estado
    orden.estado = ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR
    # OrdenServicio.save() crea HistorialOrden(tipo_evento='cambio_estado')
    orden.save(update_fields=['estado'])

    # Enriquecer historial con contexto de Almacén (quién notificó / número solicitud)
    empleado = None
    if usuario is not None and hasattr(usuario, 'empleado'):
        empleado = getattr(usuario, 'empleado', None)

    from config.constants import ESTADO_ORDEN_CHOICES

    etiquetas = dict(ESTADO_ORDEN_CHOICES)
    ultimo = (
        orden.historial.filter(
            tipo_evento='cambio_estado',
            estado_nuevo=ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR,
        )
        .order_by('-fecha_evento')
        .first()
    )
    if ultimo:
        ultimo.comentario = (
            f'Cambio de estado al notificar a Front desde Almacén: '
            f'{etiquetas.get(estado_anterior, estado_anterior)} → '
            f'{etiquetas.get(ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR, ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR)} '
            f'(solicitud {solicitud.numero_solicitud})'
        )
        update_fields = ['comentario', 'es_sistema']
        if empleado is not None:
            ultimo.usuario = empleado
            update_fields.append('usuario')
        ultimo.es_sistema = True
        ultimo.save(update_fields=update_fields)

    logger.info(
        f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno}: "
        f"{estado_anterior} → {ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR} "
        f"(notificar a Front, solicitud {solicitud.numero_solicitud})"
    )
    return True


def sincronizar_estado_st_al_enviar_cotizacion_cliente(
    solicitud: 'SolicitudCotizacion',
    usuario=None,
) -> bool:
    """
    Al enviar la cotización al cliente desde Almacén, pone la orden ST en ``cotizacion``.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    El momento correcto de marcar «Esperando Aprobación Cliente» es cuando
    realmente se envía el correo. Si la orden YA avanzó (aceptada, esperando
    piezas, reparación…), un reenvío del PDF/correo NO debe retroceder el
    workflow: el correo sí se manda, pero el estado ST se deja igual.

    Args:
        solicitud: SolicitudCotizacion (con o sin orden_servicio).
        usuario: User opcional; si tiene empleado, se asocia al historial.

    Returns:
        bool: True si se cambió el estado; False si no aplica o se omitió a propósito.
    """
    orden = getattr(solicitud, 'orden_servicio', None)
    if not orden:
        return False

    # Ya está esperando al cliente: no duplicar historial ni push
    if orden.estado == ESTADO_ST_ESPERANDO_CLIENTE:
        return False

    # Guardia anti-regresión: no pisar estados posteriores del flujo
    if orden.estado not in ESTADOS_ST_PERMITIDOS_PARA_ESPERAR_CLIENTE:
        logger.info(
            f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno} en estado "
            f"'{orden.estado}'; reenvío de cotización NO cambia a 'cotizacion' "
            f"(solicitud {solicitud.numero_solicitud})."
        )
        return False

    estado_anterior = orden.estado
    orden.estado = ESTADO_ST_ESPERANDO_CLIENTE
    # OrdenServicio.save() crea HistorialOrden(tipo_evento='cambio_estado')
    orden.save(update_fields=['estado'])

    # Enriquecer historial con contexto de Almacén (quién envió / número solicitud)
    empleado = None
    if usuario is not None and hasattr(usuario, 'empleado'):
        empleado = getattr(usuario, 'empleado', None)

    from config.constants import ESTADO_ORDEN_CHOICES

    ultimo = (
        orden.historial.filter(
            tipo_evento='cambio_estado',
            estado_nuevo=ESTADO_ST_ESPERANDO_CLIENTE,
        )
        .order_by('-fecha_evento')
        .first()
    )
    if ultimo:
        ultimo.comentario = (
            f'Cambio de estado al enviar cotización al cliente desde Almacén: '
            f'{dict(ESTADO_ORDEN_CHOICES).get(estado_anterior, estado_anterior)} → '
            f'Esperando Aprobación Cliente '
            f'(solicitud {solicitud.numero_solicitud})'
        )
        update_fields = ['comentario', 'es_sistema']
        if empleado is not None:
            ultimo.usuario = empleado
            update_fields.append('usuario')
        ultimo.es_sistema = True
        ultimo.save(update_fields=update_fields)

    logger.info(
        f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno}: "
        f"{estado_anterior} → cotizacion "
        f"(envío al cliente, solicitud {solicitud.numero_solicitud})"
    )
    return True


def sincronizar_estado_st_por_respuesta_cliente(
    solicitud: 'SolicitudCotizacion',
    estado_solicitud: Optional[str] = None,
) -> bool:
    """
    Tras la respuesta completa del cliente en Almacén, actualiza el estado de la orden ST.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Si la solicitud queda totalmente/parcialmente aprobada, la orden pasa a
    «Cliente Acepta Cotización». Si queda totalmente rechazada, pasa a
    «Cotización Rechazada». Solo actúa cuando la orden está en «Esperando
    Aprobación Cliente» (cotizacion), para no sobrescribir estados posteriores.

    Args:
        solicitud: SolicitudCotizacion con (o sin) orden_servicio vinculada.
        estado_solicitud: Estado recién calculado; si es None, usa solicitud.estado.

    Returns:
        bool: True si se cambió el estado de la orden; False si no aplica.
    """
    estado_sol = estado_solicitud or getattr(solicitud, 'estado', None)
    estado_st_destino = MAPEO_RESPUESTA_SOLICITUD_A_ESTADO_ST.get(estado_sol)
    if not estado_st_destino:
        return False

    # Sin orden vinculada (modo sin_orden_activa) no hay nada que actualizar en ST
    orden = getattr(solicitud, 'orden_servicio', None)
    if not orden:
        return False

    # Solo avanzar desde «Esperando Aprobación Cliente»
    if orden.estado != ESTADO_ST_ESPERANDO_CLIENTE:
        logger.info(
            f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno} en estado "
            f"'{orden.estado}'; no se cambia a '{estado_st_destino}' "
            f"(solicitud {solicitud.numero_solicitud})."
        )
        return False

    # Ya está en el destino (poco probable desde cotizacion, pero seguro)
    if orden.estado == estado_st_destino:
        return False

    estado_anterior = orden.estado
    orden.estado = estado_st_destino
    # OrdenServicio.save() crea HistorialOrden(tipo_evento='cambio_estado')
    orden.save(update_fields=['estado'])

    # Enriquecer el historial recién creado con contexto de Almacén
    _enriquecer_historial_respuesta_cliente(
        orden=orden,
        solicitud=solicitud,
        estado_solicitud=estado_sol,
        estado_anterior=estado_anterior,
        estado_nuevo=estado_st_destino,
    )

    logger.info(
        f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno}: "
        f"{estado_anterior} → {estado_st_destino} "
        f"(solicitud {solicitud.numero_solicitud}, respuesta {estado_sol})"
    )
    return True


def _enriquecer_historial_respuesta_cliente(
    orden,
    solicitud: 'SolicitudCotizacion',
    estado_solicitud: str,
    estado_anterior: str,
    estado_nuevo: str,
) -> None:
    """
    Completa el comentario del último HistorialOrden de cambio de estado.

    Args:
        orden: OrdenServicio ya guardada con el nuevo estado.
        solicitud: SolicitudCotizacion que originó el cambio.
        estado_solicitud: Estado de la solicitud Almacén (ej. parcialmente_aprobada).
        estado_anterior: Código de estado ST previo.
        estado_nuevo: Código de estado ST nuevo.
    """
    from config.constants import ESTADO_ORDEN_CHOICES

    ultimo = (
        orden.historial.filter(tipo_evento='cambio_estado', estado_nuevo=estado_nuevo)
        .order_by('-fecha_evento')
        .first()
    )
    if not ultimo:
        return

    etiqueta_anterior = dict(ESTADO_ORDEN_CHOICES).get(estado_anterior, estado_anterior)
    etiqueta_nueva = ETIQUETAS_ESTADO_ST.get(
        estado_nuevo,
        dict(ESTADO_ORDEN_CHOICES).get(estado_nuevo, estado_nuevo),
    )
    tipo_respuesta = ETIQUETAS_RESPUESTA_SOLICITUD.get(estado_solicitud, estado_solicitud)

    ultimo.comentario = (
        f'Cambio de estado por respuesta del cliente en cotización Almacén '
        f'({tipo_respuesta}): {etiqueta_anterior} → {etiqueta_nueva} '
        f'(solicitud {solicitud.numero_solicitud})'
    )
    ultimo.es_sistema = True
    ultimo.save(update_fields=['comentario', 'es_sistema'])
