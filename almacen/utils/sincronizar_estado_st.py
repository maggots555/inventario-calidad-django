"""
Sincronización de estado de OrdenServicio (ST) desde cotizaciones de Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando Almacén crea una solicitud con orden, notifica a Front, envía cotización
al cliente o recibe respuesta, la orden en Servicio Técnico debe reflejar el
mismo hito de workflow. Estas funciones centralizan ese cambio para no
duplicar lógica en views y modelos.
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

# Destino al crear una solicitud de cotización CON orden vinculada
ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR = 'cotizacion_enviada_proveedor'

# Destino al avisar a Front que la cotización de proveedores ya está lista
ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR = 'cotizacion_recibida_proveedor'

# Destino al avisar a Front que NO hay partes disponibles en mercado (PNC)
ESTADO_ST_PNC = 'pnc_parte_no_disponible'

# Tipos de plantilla del modal «Notificar a Front»
# EXPLICACIÓN: cotizacion_lista = correo normal con precios + sync ST a recibida;
# partes_no_disponibles = correo PNC a Front SIN cambiar ST (el PNC en ST lo
# pone solo el botón «Notificar cliente: sin piezas»).
TIPO_PLANTILLA_COTIZACION_LISTA = 'cotizacion_lista'
TIPO_PLANTILLA_PARTES_NO_DISPONIBLES = 'partes_no_disponibles'
TIPOS_PLANTILLA_NOTIFICAR_FRONT = frozenset({
    TIPO_PLANTILLA_COTIZACION_LISTA,
    TIPO_PLANTILLA_PARTES_NO_DISPONIBLES,
})

# Solo la plantilla de cotización lista cambia ST al notificar a Front.
# La plantilla PNC quedó obsoleta como destino ST (fuente única = botón cliente).
MAPEO_PLANTILLA_A_ESTADO_ST = {
    TIPO_PLANTILLA_COTIZACION_LISTA: ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR,
}

# EXPLICACIÓN PARA PRINCIPIANTES:
# Al crear la solicitud con orden, solo avanzamos desde fases previas
# (diagnóstico, recepción, etc.) o desde «rechazada» (re-cotización).
# Nunca desde cotizacion / esperando_piezas / reparación, etc.
ESTADOS_ST_PERMITIDOS_PARA_CREAR_SOLICITUD = (
    'almacen',
    'espera',
    'recepcion',
    'diagnostico',
    'equipo_diagnosticado',
    'diagnostico_enviado_cliente',
    'rechazada',  # Re-cotización tras rechazo: vuelve al hito de envío a proveedor
)

# EXPLICACIÓN PARA PRINCIPIANTES:
# Al notificar a Front solo avanzamos desde estados previos al hito
# «Se Recibe Cotización de Proveedores» o desde PNC (recuperación cuando
# sí encontraron partes). Nunca desde cotizacion, reparación, etc.
ESTADOS_ST_PERMITIDOS_PARA_NOTIFICAR_FRONT = (
    'almacen',
    'espera',
    'recepcion',
    'diagnostico',
    'equipo_diagnosticado',
    'diagnostico_enviado_cliente',
    'cotizacion_enviada_proveedor',
    'rechazada',  # Re-cotización tras rechazo: vuelve al hito de proveedores
    ESTADO_ST_PNC,  # Recuperación: partes encontradas tras un PNC previo
)

# EXPLICACIÓN PARA PRINCIPIANTES:
# Al enviar/reenviar la cotización al cliente, SOLO podemos pasar a «cotizacion»
# desde estados previos (diagnóstico, armado de cotización, etc.), desde
# «rechazada» (nueva propuesta) o desde PNC (alternativa reacondicionado /
# reparación componente cuando no hubo partes). Nunca desde esperando_piezas,
# reparación, etc.
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
    ESTADO_ST_PNC,  # Tras PNC: alternativa (REAC / reparación componente)
)

# EXPLICACIÓN PARA PRINCIPIANTES:
# Al avisar al cliente que no hay piezas (PNC), ponemos la orden en PNC
# desde fases de cotización / proveedores. No desde reparación, etc.
ESTADOS_ST_PERMITIDOS_PARA_NOTIFICAR_CLIENTE_PNC = (
    'almacen',
    'espera',
    'recepcion',
    'diagnostico',
    'equipo_diagnosticado',
    'diagnostico_enviado_cliente',
    'cotizacion_enviada_proveedor',
    ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR,
    'rechazada',
)

# EXPLICACIÓN PARA PRINCIPIANTES:
# Al RECOTIZAR (venció la vigencia y el cliente reapareció), la solicitud
# vuelve a manos de Compras, así que la orden debe retroceder al hito
# «Envío de Cotización al Proveedor». Solo retrocedemos desde los estados en
# los que realmente puede estar una cotización vencida sin respuesta:
# esperando al cliente, cotización recibida de proveedor, o PNC.
# Nunca desde reparación, esperando piezas, entregada, etc.
ESTADOS_ST_PERMITIDOS_PARA_RECOTIZAR = (
    ESTADO_ST_ESPERANDO_CLIENTE,
    ESTADO_ST_COTIZACION_RECIBIDA_PROVEEDOR,
    ESTADO_ST_PNC,
    'diagnostico_enviado_cliente',
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


def sincronizar_estado_st_al_crear_solicitud(
    solicitud: 'SolicitudCotizacion',
    usuario=None,
) -> bool:
    """
    Al crear una SolicitudCotizacion CON orden, pone la orden ST en
    ``cotizacion_enviada_proveedor``.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Cuando el técnico ya tiene una OrdenServicio y crea la solicitud de
    cotización en Almacén, el primer hito del workflow es «Envío de Cotización
    al Proveedor». Si la solicitud es modo sin orden (aún no hay ST), o la
    orden ya avanzó (esperando cliente, piezas, reparación…), no tocamos el
    estado para no romper el flujo.

    Args:
        solicitud: SolicitudCotizacion recién creada (con o sin orden_servicio).
        usuario: User opcional; si tiene empleado, se asocia al historial.

    Returns:
        bool: True si se cambió el estado; False si no aplica o se omitió.
    """
    # Sin orden vinculada (modo sin_orden_activa) no hay nada que actualizar en ST
    orden = getattr(solicitud, 'orden_servicio', None)
    if not orden:
        return False

    # Ya está en el destino: no duplicar historial
    if orden.estado == ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR:
        return False

    # Guardia anti-regresión: no pisar estados posteriores del flujo
    if orden.estado not in ESTADOS_ST_PERMITIDOS_PARA_CREAR_SOLICITUD:
        logger.info(
            f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno} en estado "
            f"'{orden.estado}'; crear solicitud NO cambia a "
            f"'{ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR}' "
            f"(solicitud {solicitud.numero_solicitud})."
        )
        return False

    estado_anterior = orden.estado
    orden.estado = ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR
    # OrdenServicio.save() crea HistorialOrden(tipo_evento='cambio_estado')
    orden.save(update_fields=['estado'])

    # Enriquecer historial con contexto de Almacén (quién creó / número solicitud)
    empleado = None
    if usuario is not None and hasattr(usuario, 'empleado'):
        empleado = getattr(usuario, 'empleado', None)

    from config.constants import ESTADO_ORDEN_CHOICES

    etiquetas = dict(ESTADO_ORDEN_CHOICES)
    ultimo = (
        orden.historial.filter(
            tipo_evento='cambio_estado',
            estado_nuevo=ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR,
        )
        .order_by('-fecha_evento')
        .first()
    )
    if ultimo:
        ultimo.comentario = (
            f'Cambio de estado al crear solicitud de cotización en Almacén: '
            f'{etiquetas.get(estado_anterior, estado_anterior)} → '
            f'{etiquetas.get(ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR, ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR)} '
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
        f"{estado_anterior} → {ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR} "
        f"(crear solicitud, {solicitud.numero_solicitud})"
    )
    return True


def _listar_piezas_solicitud_para_historial(solicitud: 'SolicitudCotizacion') -> str:
    """
    Arma un texto corto con las líneas de la solicitud (producto + descripción).

    EXPLICACIÓN PARA PRINCIPIANTES:
    En el flujo PNC necesitamos dejar constancia en el historial de ST de
    *qué* piezas no se encontraron. Las líneas de Almacén ya son ese listado.

    Args:
        solicitud: SolicitudCotizacion con líneas precargadas o no.

    Returns:
        Texto multilínea (puede ser vacío si no hay líneas).
    """
    partes: list[str] = []
    # EXPLICACIÓN: ordenamos por numero_linea para un historial legible
    for linea in solicitud.lineas.order_by('numero_linea'):
        nombre = ''
        if getattr(linea, 'producto_id', None) and linea.producto:
            nombre = (linea.producto.nombre or '').strip()
        descripcion = (linea.descripcion_pieza or '').strip()
        if nombre and descripcion:
            partes.append(f'- {nombre}: {descripcion}')
        elif nombre:
            partes.append(f'- {nombre}')
        elif descripcion:
            partes.append(f'- {descripcion}')
    return '\n'.join(partes)


def sincronizar_estado_st_al_notificar_front(
    solicitud: 'SolicitudCotizacion',
    usuario=None,
    tipo_plantilla: str = TIPO_PLANTILLA_COTIZACION_LISTA,
) -> bool:
    """
    Al notificar a Front desde Almacén, actualiza el estado ST según la plantilla.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    El modal «Notificar a Front» tiene dos plantillas:
    - ``cotizacion_lista`` → «Se Recibe Cotización de Proveedores»
    - ``partes_no_disponibles`` → solo correo a Front; **NO** cambia ST.
      El PNC en ST lo pone únicamente «Notificar cliente: sin piezas».

    Si la solicitud no tiene orden vinculada, o la orden ya avanzó (esperando
    cliente, reparación, etc.), no se cambia el estado para no romper el flujo.
    Desde PNC sí se permite recuperar con la plantilla de cotización lista.

    Args:
        solicitud: SolicitudCotizacion (con o sin orden_servicio).
        usuario: User opcional; si tiene empleado, se asocia al historial.
        tipo_plantilla: ``cotizacion_lista`` o ``partes_no_disponibles``.

    Returns:
        bool: True si se cambió el estado; False si no aplica o se omitió a propósito.
    """
    orden = getattr(solicitud, 'orden_servicio', None)
    if not orden:
        return False

    # Normalizar plantilla inválida al default (cotización lista)
    if tipo_plantilla not in TIPOS_PLANTILLA_NOTIFICAR_FRONT:
        tipo_plantilla = TIPO_PLANTILLA_COTIZACION_LISTA

    # EXPLICACIÓN: plantilla PNC a Front ya no toca ST (fuente única = botón cliente)
    if tipo_plantilla == TIPO_PLANTILLA_PARTES_NO_DISPONIBLES:
        logger.info(
            f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno}: "
            f"plantilla PNC a Front NO cambia ST "
            f"(solicitud {solicitud.numero_solicitud})."
        )
        return False

    estado_destino = MAPEO_PLANTILLA_A_ESTADO_ST[tipo_plantilla]

    # Ya está en el destino: no duplicar historial en reenvíos del correo
    if orden.estado == estado_destino:
        return False

    # Guardia anti-regresión: no pisar estados posteriores del flujo
    if orden.estado not in ESTADOS_ST_PERMITIDOS_PARA_NOTIFICAR_FRONT:
        logger.info(
            f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno} en estado "
            f"'{orden.estado}'; notificar a Front NO cambia a "
            f"'{estado_destino}' "
            f"(solicitud {solicitud.numero_solicitud}, plantilla {tipo_plantilla})."
        )
        return False

    estado_anterior = orden.estado
    orden.estado = estado_destino
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
            estado_nuevo=estado_destino,
        )
        .order_by('-fecha_evento')
        .first()
    )
    if ultimo:
        comentario = (
            f'Cambio de estado al notificar a Front desde Almacén: '
            f'{etiquetas.get(estado_anterior, estado_anterior)} → '
            f'{etiquetas.get(estado_destino, estado_destino)} '
            f'(solicitud {solicitud.numero_solicitud}, plantilla {tipo_plantilla})'
        )
        ultimo.comentario = comentario
        update_fields = ['comentario', 'es_sistema']
        if empleado is not None:
            ultimo.usuario = empleado
            update_fields.append('usuario')
        ultimo.es_sistema = True
        ultimo.save(update_fields=update_fields)

    logger.info(
        f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno}: "
        f"{estado_anterior} → {estado_destino} "
        f"(notificar a Front, plantilla {tipo_plantilla}, "
        f"solicitud {solicitud.numero_solicitud})"
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

    Caso especial PNC: si Compras avisó partes no disponibles y luego Front
    envía una alternativa (reacondicionado / reparación componente), la orden
    SÍ debe pasar de ``pnc_parte_no_disponible`` a ``cotizacion``.

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


def _registrar_comentario_historial_pnc(
    orden,
    solicitud: 'SolicitudCotizacion',
    usuario=None,
    *,
    es_reenvio: bool = False,
) -> bool:
    """
    Crea un HistorialOrden de tipo comentario para aviso PNC al cliente.

    Args:
        orden: OrdenServicio vinculada.
        solicitud: SolicitudCotizacion de Almacén.
        usuario: User opcional (para asociar empleado).
        es_reenvio: True si ST ya estaba en PNC (reaviso).

    Returns:
        bool: True si se creó el registro de historial.
    """
    from servicio_tecnico.models import HistorialOrden

    empleado = None
    if usuario is not None and hasattr(usuario, 'empleado'):
        empleado = getattr(usuario, 'empleado', None)

    prefijo = (
        'Cliente re-notificado: partes no disponibles (PNC) desde Almacén'
        if es_reenvio
        else 'Cliente notificado: partes no disponibles (PNC) desde Almacén'
    )
    comentario = f'{prefijo} (solicitud {solicitud.numero_solicitud})'
    listado = _listar_piezas_solicitud_para_historial(solicitud)
    if listado:
        comentario += f'\nPiezas no disponibles en mercado:\n{listado}'

    HistorialOrden.objects.create(
        orden=orden,
        tipo_evento='comentario',
        comentario=comentario,
        usuario=empleado,
        es_sistema=True,
    )
    return True


def sincronizar_estado_st_al_notificar_cliente_pnc(
    solicitud: 'SolicitudCotizacion',
    usuario=None,
) -> bool:
    """
    Al avisar al cliente que no hay piezas, pone la orden ST en PNC.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta es la **única** fuente de verdad para poner ST en
    ``pnc_parte_no_disponible``. La plantilla PNC de «Notificar a Front»
    ya no cambia ST.

    Si la orden ya está en PNC (reenvío del aviso), se registra un comentario
    en el historial sin volver a cambiar el estado.

    Args:
        solicitud: SolicitudCotizacion (con o sin orden_servicio).
        usuario: User opcional; si tiene empleado, se asocia al historial.

    Returns:
        bool: True si se cambió el estado o se registró comentario de reaviso.
    """
    orden = getattr(solicitud, 'orden_servicio', None)
    if not orden:
        return False

    # Ya en PNC: reaviso → solo comentario en historial
    if orden.estado == ESTADO_ST_PNC:
        registrado = _registrar_comentario_historial_pnc(
            orden,
            solicitud,
            usuario=usuario,
            es_reenvio=True,
        )
        logger.info(
            f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno}: "
            f"ya en PNC; reaviso cliente registrado "
            f"(solicitud {solicitud.numero_solicitud})."
        )
        return registrado

    if orden.estado not in ESTADOS_ST_PERMITIDOS_PARA_NOTIFICAR_CLIENTE_PNC:
        logger.info(
            f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno} en estado "
            f"'{orden.estado}'; notificar cliente PNC NO cambia a "
            f"'{ESTADO_ST_PNC}' (solicitud {solicitud.numero_solicitud})."
        )
        return False

    estado_anterior = orden.estado
    orden.estado = ESTADO_ST_PNC
    orden.save(update_fields=['estado'])

    empleado = None
    if usuario is not None and hasattr(usuario, 'empleado'):
        empleado = getattr(usuario, 'empleado', None)

    from config.constants import ESTADO_ORDEN_CHOICES

    etiquetas = dict(ESTADO_ORDEN_CHOICES)
    ultimo = (
        orden.historial.filter(
            tipo_evento='cambio_estado',
            estado_nuevo=ESTADO_ST_PNC,
        )
        .order_by('-fecha_evento')
        .first()
    )
    if ultimo:
        # EXPLICACIÓN: dejamos constancia de que el cliente fue avisado + piezas
        comentario = (
            f'Cliente notificado: partes no disponibles (PNC) desde Almacén: '
            f'{etiquetas.get(estado_anterior, estado_anterior)} → '
            f'{etiquetas.get(ESTADO_ST_PNC, ESTADO_ST_PNC)} '
            f'(solicitud {solicitud.numero_solicitud})'
        )
        listado = _listar_piezas_solicitud_para_historial(solicitud)
        if listado:
            comentario += f'\nPiezas no disponibles en mercado:\n{listado}'
        ultimo.comentario = comentario
        update_fields = ['comentario', 'es_sistema']
        if empleado is not None:
            ultimo.usuario = empleado
            update_fields.append('usuario')
        ultimo.es_sistema = True
        ultimo.save(update_fields=update_fields)

    logger.info(
        f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno}: "
        f"{estado_anterior} → {ESTADO_ST_PNC} "
        f"(notificar cliente PNC, solicitud {solicitud.numero_solicitud})"
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
    «Cotización Rechazada».

    Orígenes permitidos:
    - Normalmente desde «Esperando Aprobación Cliente» (cotizacion).
    - Si el destino es «rechazada», también desde PNC (avisaron sin piezas
      y luego tipificaron el rechazo total).

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

    # EXPLICACIÓN: rechazo total también puede venir desde PNC (sin cotización de precios)
    estados_origen_ok = {ESTADO_ST_ESPERANDO_CLIENTE}
    if estado_st_destino == 'rechazada':
        estados_origen_ok.add(ESTADO_ST_PNC)

    if orden.estado not in estados_origen_ok:
        logger.info(
            f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno} en estado "
            f"'{orden.estado}'; no se cambia a '{estado_st_destino}' "
            f"(solicitud {solicitud.numero_solicitud})."
        )
        return False

    # Ya está en el destino (poco probable, pero seguro)
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


def sincronizar_estado_st_al_recotizar(
    solicitud: 'SolicitudCotizacion',
    usuario=None,
    ronda_cerrada: int = 1,
) -> bool:
    """
    Regresa la orden ST al hito de proveedores cuando se abre una ronda nueva.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Al recotizar, la solicitud de Almacén vuelve a ``borrador`` porque Compras
    tiene que confirmar disponibilidad y precios otra vez. Si no avisáramos a
    Servicio Técnico, la orden se quedaría marcada como «Esperando Aprobación
    Cliente» durante toda la ronda nueva, y el técnico creería que la pelota
    está del lado del cliente cuando en realidad está del lado de Compras.

    Además hay un motivo técnico: las guardias anti-regresión del resto de este
    archivo no permiten avanzar desde ``cotizacion``, así que si dejáramos la
    orden ahí, el próximo «Notificar a Front» se omitiría y la orden quedaría
    congelada para siempre en ese estado.

    Este es el ÚNICO lugar del sistema donde la orden retrocede a propósito,
    por eso la lista de estados permitidos es corta y explícita.

    Args:
        solicitud: SolicitudCotizacion que acaba de entrar a una ronda nueva.
        usuario: User opcional; si tiene empleado, se asocia al historial.
        ronda_cerrada: Número de la ronda que se acaba de cerrar (para el texto
            del historial, ej. "ronda 1 vencida").

    Returns:
        bool: True si se cambió el estado; False si no hay orden vinculada,
        si ya estaba en el hito de proveedores, o si la orden avanzó a una
        fase donde retroceder sería peligroso (reparación, entrega, etc.).

    Efectos secundarios:
        Cambia ``orden.estado`` y crea una entrada de HistorialOrden mediante
        el ``save()`` de OrdenServicio, cuyo comentario se enriquece aquí.
    """
    # Modo sin orden vinculada: no hay nada que sincronizar
    orden = getattr(solicitud, 'orden_servicio', None)
    if not orden:
        return False

    # Ya está en el hito de proveedores: no duplicamos historial
    if orden.estado == ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR:
        return False

    # Guardia: solo retrocedemos desde donde puede estar una cotización
    # vencida. Si la orden ya está en reparación o entregada, algo raro pasó
    # y preferimos dejarla quieta antes que romper el workflow del técnico.
    if orden.estado not in ESTADOS_ST_PERMITIDOS_PARA_RECOTIZAR:
        logger.info(
            f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno} en estado "
            f"'{orden.estado}'; la recotización NO la regresa a "
            f"'{ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR}' "
            f"(solicitud {solicitud.numero_solicitud})."
        )
        return False

    estado_anterior = orden.estado
    orden.estado = ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR
    # OrdenServicio.save() crea HistorialOrden(tipo_evento='cambio_estado')
    orden.save(update_fields=['estado'])

    # Enriquecer el historial para que el técnico entienda POR QUÉ retrocedió
    empleado = None
    if usuario is not None and hasattr(usuario, 'empleado'):
        empleado = getattr(usuario, 'empleado', None)

    from config.constants import ESTADO_ORDEN_CHOICES

    etiquetas = dict(ESTADO_ORDEN_CHOICES)
    ultimo = (
        orden.historial.filter(
            tipo_evento='cambio_estado',
            estado_nuevo=ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR,
        )
        .order_by('-fecha_evento')
        .first()
    )
    if ultimo:
        ultimo.comentario = (
            f'Recotización solicitada en Almacén: la ronda {ronda_cerrada} '
            f'venció sin respuesta del cliente. '
            f'{etiquetas.get(estado_anterior, estado_anterior)} → '
            f'{etiquetas.get(ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR, ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR)} '
            f'(solicitud {solicitud.numero_solicitud}, '
            f'ronda {solicitud.ronda_cotizacion})'
        )
        update_fields = ['comentario', 'es_sistema']
        if empleado is not None:
            ultimo.usuario = empleado
            update_fields.append('usuario')
        ultimo.es_sistema = True
        ultimo.save(update_fields=update_fields)

    logger.info(
        f"[SYNC_ESTADO_ST] Orden {orden.numero_orden_interno}: "
        f"{estado_anterior} → {ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR} "
        f"(recotización, {solicitud.numero_solicitud}, "
        f"ronda {solicitud.ronda_cotizacion})"
    )
    return True
