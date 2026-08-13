"""
Notificaciones al crear una SolicitudBaja (salida de producto del almacén).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando alguien envía el formulario de solicitud de baja, el almacenista
tiene que enterarse para aprobar o rechazar. Compras y quien pidió el
producto reciben el mismo correo en copia (CC), como constancia.

Canales (mismo patrón que cotizaciones):
1. Push al dispositivo — solo almacenistas (ellos procesan)
2. Campanita interna — solo almacenistas
3. Email en segundo plano vía Celery
   - Para (To): almacenistas
   - Copia (CC): Compras + el solicitante

Al procesar (aprobar/rechazar):
1. Push + campanita — solo quien levantó la solicitud
2. Email To = solicitante; CC = Compras

Si el aviso falla, la solicitud YA quedó guardada. Nunca se revierte.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional, Tuple

from django.urls import reverse

from almacen.utils.notificar_respuesta_cotizacion import (
    enviar_push_y_campanita,
    obtener_empleados_compras,
)

if TYPE_CHECKING:
    from almacen.models import SolicitudBaja
    from inventario.models import Empleado

logger = logging.getLogger('almacen')

# Motivo corto en push/campanita: el cuerpo de esas notificaciones es breve.
_MAX_MOTIVO_PUSH = 120


def obtener_empleados_almacenista() -> List['Empleado']:
    """
    Empleados activos con rol Almacenista y usuario de sistema activo.

    Returns:
        Lista de Empleado (puede estar vacía).
    """
    from inventario.models import Empleado

    return list(
        Empleado.objects.filter(
            rol='almacenista',
            activo=True,
            user__is_active=True,
        ).select_related('user')
    )


def _normalizar_email(empleado: Optional['Empleado']) -> str:
    """
    Email en minúsculas sin espacios, o cadena vacía si no hay.

    Args:
        empleado: Ficha de empleado o None.

    Returns:
        str: Dirección lista para comparar, o ''.
    """
    if empleado is None:
        return ''
    return (getattr(empleado, 'email', None) or '').strip().lower()


def armar_destinatarios_email(
    solicitud: 'SolicitudBaja',
) -> Tuple[List[str], List[str]]:
    """
    Arma listas To / CC sin repetir la misma dirección.

    EXPLICACIÓN: si un almacenista y alguien de Compras comparten email,
    esa dirección va solo en To. Si el solicitante ya está en To o CC
    por su rol, no se agrega otra vez.

    Args:
        solicitud: SolicitudBaja recién creada (usa solicitante).

    Returns:
        tuple: (emails_to, emails_cc) ya normalizados.
    """
    emails_to: List[str] = []
    vistos_to: set[str] = set()

    # Paso 1: To = almacenistas con correo en su ficha.
    for almacenista in obtener_empleados_almacenista():
        email = _normalizar_email(almacenista)
        if not email or email in vistos_to:
            continue
        vistos_to.add(email)
        emails_to.append(email)

    emails_cc: List[str] = []
    vistos_cc: set[str] = set()

    def _agregar_cc(empleado: Optional['Empleado']) -> None:
        # Paso a paso: sin email, o ya va en To/CC → no duplicar.
        email = _normalizar_email(empleado)
        if not email or email in vistos_to or email in vistos_cc:
            return
        vistos_cc.add(email)
        emails_cc.append(email)

    # Paso 2: CC = Compras, luego el solicitante (si no estaba ya).
    for comprador in obtener_empleados_compras():
        _agregar_cc(comprador)

    _agregar_cc(getattr(solicitud, 'solicitante', None))

    return emails_to, emails_cc


def url_relativa_procesar_solicitud(solicitud: 'SolicitudBaja') -> str:
    """
    Ruta relativa a la pantalla de aprobar/rechazar (push / campanita).

    Args:
        solicitud: SolicitudBaja (solo se usa su pk).

    Returns:
        str: Ruta Django, ej. /almacen/solicitudes/42/procesar/
    """
    return reverse('almacen:procesar_solicitud', kwargs={'pk': solicitud.pk})


def url_absoluta_procesar_solicitud(solicitud: 'SolicitudBaja') -> str:
    """
    URL absoluta al procesar solicitud, lista para un href de correo.

    Args:
        solicitud: SolicitudBaja (solo se usa su pk).

    Returns:
        str: Enlace con subdominio del país (o localhost si DEBUG).
    """
    from almacen.utils.cotizacion_email_context import url_base_pais_email

    return f'{url_base_pais_email()}{url_relativa_procesar_solicitud(solicitud)}'


def resumen_orden_vinculada(solicitud: 'SolicitudBaja') -> str:
    """
    Texto corto de la orden ST vinculada, o aviso si no hay.

    Args:
        solicitud: SolicitudBaja (puede no tener orden).

    Returns:
        str: Folio interno y folio cliente, o 'Sin orden vinculada'.
    """
    orden = getattr(solicitud, 'orden_servicio', None)
    if orden is None:
        return 'Sin orden vinculada'

    folio_interno = orden.numero_orden_interno or f'#{orden.pk}'
    detalle = getattr(orden, 'detalle_equipo', None)
    folio_cliente = ''
    if detalle is not None:
        folio_cliente = (getattr(detalle, 'orden_cliente', None) or '').strip()

    if folio_cliente:
        return f'{folio_interno} ({folio_cliente})'
    return folio_interno


def construir_titulo_notificacion(solicitud: 'SolicitudBaja') -> str:
    """
    Título corto para push, campanita y asunto del correo.

    Args:
        solicitud: SolicitudBaja con producto cargado.

    Returns:
        str: Ej. 'Nueva solicitud de baja: SKU-01 (2)'
    """
    producto = getattr(solicitud, 'producto', None)
    codigo = getattr(producto, 'codigo_producto', None) or 'N/A'
    return f'Nueva solicitud de baja: {codigo} ({solicitud.cantidad})'


def construir_mensaje_notificacion(solicitud: 'SolicitudBaja') -> str:
    """
    Cuerpo de push/campanita: producto, cantidad, tipo, quién pidió, orden.

    Args:
        solicitud: SolicitudBaja con FKs de producto/solicitante/orden.

    Returns:
        str: Un párrafo corto (el motivo se recorta si es muy largo).
    """
    producto = getattr(solicitud, 'producto', None)
    codigo = getattr(producto, 'codigo_producto', None) or 'N/A'
    nombre = getattr(producto, 'nombre', None) or 'Producto'
    solicitante = getattr(solicitud, 'solicitante', None)
    nombre_quien_pidio = (
        getattr(solicitante, 'nombre_completo', None) or 'Desconocido'
    )
    tipo = solicitud.get_tipo_solicitud_display()
    motivo = (solicitud.observaciones or '').strip()
    if len(motivo) > _MAX_MOTIVO_PUSH:
        motivo = motivo[: _MAX_MOTIVO_PUSH - 3] + '...'

    partes = [
        f'Producto: {codigo} — {nombre}.',
        f'Cantidad: {solicitud.cantidad}.',
        f'Tipo: {tipo}.',
        f'Solicitó: {nombre_quien_pidio}.',
        f'Orden: {resumen_orden_vinculada(solicitud)}.',
    ]
    if motivo:
        partes.append(f'Motivo: {motivo}')
    return ' '.join(partes)


def notificar_nueva_solicitud_baja(solicitud: 'SolicitudBaja') -> None:
    """
    Avisa a almacenistas (push/campanita) y encola el correo To/CC.

    Efectos secundarios:
        - Push + campanita a cada empleado rol=almacenista con usuario
        - Encola email Celery (multi-tenant con db_alias)
        - No lanza excepciones al llamador (la solicitud ya está guardada)

    Args:
        solicitud: SolicitudBaja recién creada.
    """
    try:
        _notificar_nueva_solicitud_baja_interno(solicitud)
    except Exception:
        logger.exception(
            '[NOTIF-BAJA] Error al notificar solicitud #%s; la baja ya quedó guardada',
            solicitud.pk,
        )


def _notificar_nueva_solicitud_baja_interno(solicitud: 'SolicitudBaja') -> None:
    """
    Cuerpo de la notificación. Separado para poder loguear el fallo global.

    Args:
        solicitud: SolicitudBaja recién creada.
    """
    from config.paises_config import get_pais_actual
    from almacen.tasks_solicitud_baja import (
        notificar_almacenista_solicitud_baja_task,
    )

    almacenistas = obtener_empleados_almacenista()
    titulo = construir_titulo_notificacion(solicitud)
    mensaje = construir_mensaje_notificacion(solicitud)
    url = url_relativa_procesar_solicitud(solicitud)

    # Push/campanita solo a quien procesa (almacenista), no a CC.
    if almacenistas:
        enviados = enviar_push_y_campanita(
            almacenistas,
            titulo=titulo,
            mensaje=mensaje,
            url=url,
        )
        logger.info(
            '[NOTIF-BAJA] Solicitud #%s: push/campanita a %s almacenista(s)',
            solicitud.pk,
            enviados,
        )
    else:
        logger.info(
            '[NOTIF-BAJA] Solicitud #%s: no hay almacenistas activos para push',
            solicitud.pk,
        )

    emails_to, emails_cc = armar_destinatarios_email(solicitud)
    if not emails_to and not emails_cc:
        logger.info(
            '[NOTIF-BAJA] Solicitud #%s: nadie tiene email; no se encola correo',
            solicitud.pk,
        )
        return

    db_alias = get_pais_actual()['db_alias']
    notificar_almacenista_solicitud_baja_task.delay(
        solicitud.pk,
        db_alias=db_alias,
    )
    logger.info(
        '[NOTIF-BAJA] Solicitud #%s: email encolado (To=%s, CC=%s)',
        solicitud.pk,
        len(emails_to),
        len(emails_cc),
    )


def armar_destinatarios_email_procesada(
    solicitud: 'SolicitudBaja',
) -> Tuple[List[str], List[str]]:
    """
    To = quien levantó la baja; CC = Compras, sin repetir direcciones.

    EXPLICACIÓN: si el solicitante también es de Compras, su email va
    solo en To. No se notifica al almacenista que acaba de procesar.

    Args:
        solicitud: SolicitudBaja ya aprobada o rechazada.

    Returns:
        tuple: (emails_to, emails_cc) ya normalizados.
    """
    emails_to: List[str] = []
    vistos_to: set[str] = set()

    email_solicitante = _normalizar_email(
        getattr(solicitud, 'solicitante', None)
    )
    if email_solicitante:
        vistos_to.add(email_solicitante)
        emails_to.append(email_solicitante)

    emails_cc: List[str] = []
    vistos_cc: set[str] = set()
    for comprador in obtener_empleados_compras():
        email = _normalizar_email(comprador)
        if not email or email in vistos_to or email in vistos_cc:
            continue
        vistos_cc.add(email)
        emails_cc.append(email)

    return emails_to, emails_cc


def url_relativa_lista_solicitudes() -> str:
    """Ruta relativa al listado de solicitudes de baja (ya procesada)."""
    return reverse('almacen:lista_solicitudes')


def url_absoluta_lista_solicitudes() -> str:
    """
    URL absoluta al listado, lista para un href de correo.

    Returns:
        str: Enlace con subdominio del país (o localhost si DEBUG).
    """
    from almacen.utils.cotizacion_email_context import url_base_pais_email

    return f'{url_base_pais_email()}{url_relativa_lista_solicitudes()}'


def _es_aprobada(solicitud: 'SolicitudBaja') -> bool:
    """True si la solicitud quedó aprobada (no rechazada)."""
    return solicitud.estado == 'aprobada'


def construir_titulo_procesada(solicitud: 'SolicitudBaja') -> str:
    """
    Título corto de push/campanita al cerrar la baja.

    Args:
        solicitud: SolicitudBaja ya procesada.

    Returns:
        str: Ej. 'Solicitud de baja #12 aprobada'
    """
    verbo = 'aprobada' if _es_aprobada(solicitud) else 'rechazada'
    return f'Solicitud de baja #{solicitud.pk} {verbo}'


def construir_mensaje_procesada(solicitud: 'SolicitudBaja') -> str:
    """
    Cuerpo de push/campanita: resultado, producto, orden y notas del agente.

    Args:
        solicitud: SolicitudBaja con producto, orden y observaciones_agente.

    Returns:
        str: Un párrafo corto.
    """
    producto = getattr(solicitud, 'producto', None)
    codigo = getattr(producto, 'codigo_producto', None) or 'N/A'
    nombre = getattr(producto, 'nombre', None) or 'Producto'
    agente = getattr(solicitud, 'agente_almacen', None)
    nombre_agente = getattr(agente, 'nombre_completo', None) or 'Almacén'
    notas = (solicitud.observaciones_agente or '').strip()
    if len(notas) > _MAX_MOTIVO_PUSH:
        notas = notas[: _MAX_MOTIVO_PUSH - 3] + '...'

    if _es_aprobada(solicitud):
        resultado = 'fue aprobada'
    else:
        resultado = 'fue rechazada'

    partes = [
        f'Tu solicitud de baja de {codigo} — {nombre} {resultado}.',
        f'Cantidad: {solicitud.cantidad}.',
        f'Orden: {resumen_orden_vinculada(solicitud)}.',
        f'Procesó: {nombre_agente}.',
    ]
    if notas:
        etiqueta = 'Motivo' if not _es_aprobada(solicitud) else 'Notas'
        partes.append(f'{etiqueta}: {notas}')
    return ' '.join(partes)


def notificar_solicitud_baja_procesada(solicitud: 'SolicitudBaja') -> None:
    """
    Avisa al solicitante (push/campanita) y encola el correo To/CC.

    Efectos secundarios:
        - Push + campanita a quien levantó la solicitud (si tiene usuario)
        - Encola email Celery (To solicitante, CC Compras)
        - No lanza excepciones al llamador (el procesado ya está guardado)

    Args:
        solicitud: SolicitudBaja ya aprobada o rechazada.
    """
    try:
        _notificar_solicitud_baja_procesada_interno(solicitud)
    except Exception:
        logger.exception(
            '[NOTIF-BAJA] Error al notificar procesamiento #%s; el estado ya quedó',
            solicitud.pk,
        )


def _notificar_solicitud_baja_procesada_interno(
    solicitud: 'SolicitudBaja',
) -> None:
    """
    Cuerpo del aviso al procesar. Separado para loguear el fallo global.

    Args:
        solicitud: SolicitudBaja ya aprobada o rechazada.
    """
    from config.paises_config import get_pais_actual
    from almacen.tasks_solicitud_baja import (
        notificar_solicitud_baja_procesada_task,
    )

    titulo = construir_titulo_procesada(solicitud)
    mensaje = construir_mensaje_procesada(solicitud)
    url = url_relativa_lista_solicitudes()

    # Push/campanita solo a quien pidió (no a Compras ni al que procesó).
    solicitante = getattr(solicitud, 'solicitante', None)
    user_solicitante = getattr(solicitante, 'user', None) if solicitante else None
    if solicitante is not None and user_solicitante is not None:
        if user_solicitante.is_active:
            enviar_push_y_campanita(
                [solicitante],
                titulo=titulo,
                mensaje=mensaje,
                url=url,
            )
            logger.info(
                '[NOTIF-BAJA] Solicitud #%s procesada: push/campanita al solicitante',
                solicitud.pk,
            )
        else:
            logger.info(
                '[NOTIF-BAJA] Solicitud #%s: solicitante sin usuario activo; sin push',
                solicitud.pk,
            )
    else:
        logger.info(
            '[NOTIF-BAJA] Solicitud #%s: sin solicitante/usuario; sin push',
            solicitud.pk,
        )

    emails_to, emails_cc = armar_destinatarios_email_procesada(solicitud)
    if not emails_to and not emails_cc:
        logger.info(
            '[NOTIF-BAJA] Solicitud #%s procesada: nadie tiene email; no se encola',
            solicitud.pk,
        )
        return

    db_alias = get_pais_actual()['db_alias']
    notificar_solicitud_baja_procesada_task.delay(
        solicitud.pk,
        db_alias=db_alias,
    )
    logger.info(
        '[NOTIF-BAJA] Solicitud #%s procesada: email encolado (To=%s, CC=%s)',
        solicitud.pk,
        len(emails_to),
        len(emails_cc),
    )
