"""
Avisos cuando un pago necesita (o ya tuvo) validación en la cuenta.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Recepción registra el cobro. Si fue transferencia o tarjeta, Facturación
debe mirar la cuenta de la empresa y marcar "ya aparece" o "no aparece".

Canales (mismo patrón que cotizaciones / solicitudes de baja):
1. Push al dispositivo
2. Campanita interna
3. Email en segundo plano vía Celery (no bloquea a quien cobra)

Destinatarios:
- Pago nuevo pendiente → todos los de Facturación, excepto quien
  acaba de registrarlo (si ella misma es de Facturación).
- Validado → responsable de seguimiento; si no hay, recepcionistas.
- No aparece → quien registró el pago, salvo que sea la misma
  persona que acaba de marcar (no tiene sentido avisarse a sí misma).

Si el aviso falla, el pago YA quedó guardado.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterable, List, Optional, Set

from django.urls import reverse

from almacen.utils.notificar_respuesta_cotizacion import enviar_push_y_campanita
from servicio_tecnico.services.pagos_orden import referencia_visible_orden

if TYPE_CHECKING:
    from inventario.models import Empleado
    from servicio_tecnico.models import OrdenServicio, PagoOrden

logger = logging.getLogger('servicio_tecnico')

# Tres eventos que entiende la tarea de correo.
TIPO_PAGO_PENDIENTE = 'pendiente'
TIPO_PAGO_VALIDADO = 'validado'
TIPO_PAGO_NO_APARECE = 'no_aparece'


def _empleado_notificable(empleado: Optional['Empleado']) -> bool:
    """
    True si el empleado puede recibir push/campana (user activo).

    Args:
        empleado: ficha o None.

    Returns:
        bool
    """
    if empleado is None or not getattr(empleado, 'activo', False):
        return False
    user = getattr(empleado, 'user', None)
    return user is not None and user.is_active


def _deduplicar_empleados(empleados: Iterable['Empleado']) -> List['Empleado']:
    """
    Quita repetidos por user_id y a quien no se puede notificar.

    Args:
        empleados: iterable de Empleado (puede traer None o inactivos).

    Returns:
        Lista única, estable en el orden de llegada.
    """
    resultado: List[Empleado] = []
    vistos: Set[int] = set()
    for empleado in empleados:
        if not _empleado_notificable(empleado):
            continue
        user_id = empleado.user.pk
        if user_id in vistos:
            continue
        vistos.add(user_id)
        resultado.append(empleado)
    return resultado


def obtener_empleados_por_rol(rol: str) -> List['Empleado']:
    """
    Empleados activos de un rol con usuario de sistema activo.

    Args:
        rol: código de Empleado.ROL_CHOICES (ej. 'facturacion').

    Returns:
        Lista (puede estar vacía).
    """
    from inventario.models import Empleado

    return list(
        Empleado.objects.filter(
            rol=rol,
            activo=True,
            user__is_active=True,
        ).select_related('user')
    )


def url_relativa_bandeja_pagos() -> str:
    """
    Ruta a la bandeja de pagos por validar (cola de Facturación).

    Returns:
        str: ruta relativa lista para push/campana.
    """
    return reverse('servicio_tecnico:bandeja_pagos_validacion')


def url_relativa_detalle_pagos(orden: 'OrdenServicio') -> str:
    """
    Ruta al detalle de la orden, anclada a la sección de cobros.

    Args:
        orden: OrdenServicio (usa su pk).

    Returns:
        str: ruta relativa + #seccionPagos (push y campana).
    """
    ruta = reverse(
        'servicio_tecnico:detalle_orden',
        kwargs={'orden_id': orden.pk},
    )
    return f'{ruta}#seccionPagos'


def _folio_orden(orden: 'OrdenServicio') -> str:
    """
    Identificador visible: cliente → Service Tag → interno.

    Args:
        orden: OrdenServicio.

    Returns:
        str listo para asunto, push y campana.
    """
    # EXPLICACIÓN: misma prioridad que la bandeja y el correo HTML.
    return referencia_visible_orden(orden).texto


def _resumen_pago(pago: 'PagoOrden') -> str:
    """
    Una línea: monto, método y folio.

    Args:
        pago: PagoOrden (idealmente con orden precargada).

    Returns:
        str para el cuerpo corto de push/campana.
    """
    folio = _folio_orden(pago.orden)
    return (
        f'${pago.monto} por {pago.get_metodo_display()} '
        f'en la orden {folio}'
    )


def destinatarios_pago_pendiente(pago: 'PagoOrden') -> List['Empleado']:
    """
    Facturación, excepto quien acaba de registrar el pago.

    EXPLICACIÓN: si Facturación cobra ella misma, no le mandamos
    el aviso a ella (ya está en la pantalla). Sí avisamos al resto
    del área. Si es la única persona del rol, la lista queda vacía
    y valida en el mismo detalle, sin spam.

    Args:
        pago: PagoOrden recién creado.

    Returns:
        Lista de Empleado.
    """
    # Paso: si quien cobró es de Facturación, no le mandamos el aviso a ella.
    excluir_user_id = None
    registrado = getattr(pago, 'registrado_por', None)
    if registrado is not None and getattr(registrado, 'user_id', None):
        excluir_user_id = registrado.user_id

    # Paso: el resto del área sí se entera (puede haber 0, 1 o varios).
    candidatos = []
    for empleado in obtener_empleados_por_rol('facturacion'):
        if excluir_user_id and empleado.user_id == excluir_user_id:
            continue
        candidatos.append(empleado)
    return _deduplicar_empleados(candidatos)


def destinatarios_pago_validado(pago: 'PagoOrden') -> List['Empleado']:
    """
    Responsable de seguimiento; si no hay, todos los recepcionistas.

    Args:
        pago: PagoOrden ya marcado como validado.

    Returns:
        Lista de Empleado.
    """
    orden = pago.orden
    responsable = getattr(orden, 'responsable_seguimiento', None)
    if _empleado_notificable(responsable):
        return [responsable]
    return _deduplicar_empleados(obtener_empleados_por_rol('recepcionista'))


def destinatarios_pago_no_aparece(
    pago: 'PagoOrden',
    quien_marco: Optional['Empleado'] = None,
) -> List['Empleado']:
    """
    Quien registró el cobro, salvo que sea la misma persona que marcó.

    Args:
        pago: PagoOrden en no_aparece.
        quien_marco: empleado de Facturación que acaba de decidir.

    Returns:
        Lista de 0 o 1 Empleado.
    """
    registrado = getattr(pago, 'registrado_por', None)
    if not _empleado_notificable(registrado):
        return []

    # Paso: Facturación cobró y ella misma dijo "no aparece" → no auto-aviso.
    if (
        quien_marco is not None
        and getattr(quien_marco, 'pk', None)
        and registrado.pk == quien_marco.pk
    ):
        return []
    return [registrado]


def _encolar_email_validacion(pago: 'PagoOrden', tipo_evento: str) -> None:
    """
    Encola el correo Celery del país actual.

    Args:
        pago: PagoOrden (usa su pk).
        tipo_evento: pendiente / validado / no_aparece.

    Efectos secundarios:
        .delay() a la cola. No envía SMTP aquí.
    """
    from config.paises_config import get_pais_actual
    from servicio_tecnico.tasks_pagos import notificar_validacion_pago_task

    # Paso: si Redis/Celery está caído, el cobro ya se guardó; solo logueamos.
    try:
        db_alias = get_pais_actual()['db_alias']
        notificar_validacion_pago_task.delay(
            pago.pk,
            tipo_evento,
            db_alias=db_alias,
        )
    except Exception as exc:
        logger.warning(
            '[PAGO-VALIDACION] No se pudo encolar el correo (pago=%s): %s',
            pago.pk,
            exc,
        )


def notificar_pago_pendiente_validacion(pago: 'PagoOrden') -> int:
    """
    Avisa a Facturación que hay un abono por conciliar.

    Args:
        pago: PagoOrden en estado pendiente.

    Returns:
        Cuántas personas recibieron push/campana.

    Efectos secundarios:
        Push + campana + email Celery.
    """
    destinatarios = destinatarios_pago_pendiente(pago)
    if not destinatarios:
        logger.info(
            '[PAGO-VALIDACION] Pago %s pendiente: sin Facturación que avisar',
            pago.pk,
        )
        return 0

    titulo = f'Pago por validar: ${_monto(pago)}'
    mensaje = (
        f'{_resumen_pago(pago)}. Confirma si ya aparece en la cuenta '
        f'de la empresa.'
    )
    # Facturación cae a la bandeja (toda la cola), no a una orden suelta.
    url = url_relativa_bandeja_pagos()
    enviados = enviar_push_y_campanita(
        destinatarios,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
        app_origen='servicio_tecnico',
    )
    _encolar_email_validacion(pago, TIPO_PAGO_PENDIENTE)
    logger.info(
        '[PAGO-VALIDACION] Pago %s pendiente: push/campana a %s; email encolado',
        pago.pk,
        enviados,
    )
    return enviados


def notificar_pago_validado(pago: 'PagoOrden') -> int:
    """
    Avisa al responsable (o a Recepción) que el pago ya está en la cuenta.

    Args:
        pago: PagoOrden en estado validado.

    Returns:
        Cuántas personas recibieron push/campana.
    """
    destinatarios = destinatarios_pago_validado(pago)
    if not destinatarios:
        logger.info(
            '[PAGO-VALIDACION] Pago %s validado: sin responsable ni recepción',
            pago.pk,
        )
        return 0

    titulo = f'Pago validado en cuenta: ${_monto(pago)}'
    mensaje = (
        f'{_resumen_pago(pago)} ya aparece en la cuenta de la empresa.'
    )
    url = url_relativa_detalle_pagos(pago.orden)
    enviados = enviar_push_y_campanita(
        destinatarios,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
        app_origen='servicio_tecnico',
    )
    _encolar_email_validacion(pago, TIPO_PAGO_VALIDADO)
    logger.info(
        '[PAGO-VALIDACION] Pago %s validado: push/campana a %s; email encolado',
        pago.pk,
        enviados,
    )
    return enviados


def notificar_pago_no_aparece(
    pago: 'PagoOrden',
    quien_marco: Optional['Empleado'] = None,
) -> int:
    """
    Avisa a quien cobró para que revise comprobante o monto.

    Args:
        pago: PagoOrden en estado no_aparece.
        quien_marco: empleado que marcó (para no auto-avisarse).

    Returns:
        Cuántas personas recibieron push/campana.
    """
    destinatarios = destinatarios_pago_no_aparece(pago, quien_marco=quien_marco)
    if not destinatarios:
        logger.info(
            '[PAGO-VALIDACION] Pago %s no aparece: nadie a quien avisar',
            pago.pk,
        )
        return 0

    titulo = f'Pago no aparece en cuenta: ${_monto(pago)}'
    nota = (pago.nota_validacion or '').strip()
    extra = f' Nota de Facturación: {nota}' if nota else ''
    mensaje = (
        f'{_resumen_pago(pago)} aún no se ve en la cuenta.{extra} '
        f'Revisa el comprobante o el monto.'
    )
    url = url_relativa_detalle_pagos(pago.orden)
    enviados = enviar_push_y_campanita(
        destinatarios,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
        app_origen='servicio_tecnico',
    )
    _encolar_email_validacion(pago, TIPO_PAGO_NO_APARECE)
    logger.info(
        '[PAGO-VALIDACION] Pago %s no aparece: push/campana a %s; email encolado',
        pago.pk,
        enviados,
    )
    return enviados


def _monto(pago: 'PagoOrden') -> str:
    """
    Monto con 2 decimales para títulos.

    Args:
        pago: PagoOrden.

    Returns:
        str tipo '1500.00'.
    """
    return f'{pago.monto:.2f}'


def emails_de_empleados(empleados: Iterable['Empleado']) -> List[str]:
    """
    Direcciones únicas, en minúsculas, de una lista de empleados.

    Args:
        empleados: destinatarios ya filtrados.

    Returns:
        Lista de emails (sin vacíos ni duplicados).
    """
    vistos: Set[str] = set()
    resultado: List[str] = []
    for empleado in empleados:
        correo = (getattr(empleado, 'email', None) or '').strip().lower()
        if not correo or correo in vistos:
            continue
        vistos.add(correo)
        resultado.append(correo)
    return resultado
