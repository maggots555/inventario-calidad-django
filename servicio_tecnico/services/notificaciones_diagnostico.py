"""
Avisos staff cuando el Diagnóstico SIC queda guardado por primera vez.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Al guardar el Diagnóstico SIC con texto (primera vez), dos áreas deben enterarse:

1) Responsable de seguimiento → compartir el diagnóstico con el cliente.
2) Personal con rol Compras → revisar el SIC y buscar/cotizar piezas.

Canales (mismo patrón que pagos y cotizaciones):
  - Campanita in-app (`notificar_info`)
  - Web Push (`enviar_push_a_usuario` vía `enviar_push_y_campanita`)
  - Email HTML en segundo plano vía Celery

Si el aviso falla, el SIC YA quedó guardado en la orden.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from django.db import transaction
from django.urls import reverse

from almacen.utils.notificar_respuesta_cotizacion import (
    enviar_push_y_campanita,
    obtener_empleados_compras,
)
from servicio_tecnico.services.pagos_orden import referencia_visible_orden

if TYPE_CHECKING:
    from inventario.models import Empleado
    from servicio_tecnico.models import OrdenServicio

logger = logging.getLogger('servicio_tecnico')

# Audiencias que entiende la tarea de correo.
AUDIENCIA_RESPONSABLE = 'responsable'
AUDIENCIA_COMPRAS = 'compras'

# Extracto del SIC en correos (evita cuerpos enormes).
_MAX_EXTRACTO_SIC = 300


def notificar_diagnostico_sic_listo(
    orden: 'OrdenServicio',
    *,
    diagnostico_sic_anterior: str,
    diagnostico_sic_nuevo: str,
) -> dict[str, int]:
    """
    Avisa a responsable de seguimiento y Compras que el SIC quedó listo.

    Objetivo de negocio:
        Primera vez que hay texto en Diagnóstico SIC (no re-edición).

    Args:
        orden: OrdenServicio con pk.
        diagnostico_sic_anterior: Texto del SIC antes del guardado.
        diagnostico_sic_nuevo: Texto del SIC después del guardado.

    Returns:
        dict con claves ``responsable`` y ``compras``: cantidad de personas
        que recibieron push/campanita por audiencia.

    Efectos secundarios:
        Push + campanita + encola email Celery; puede escribir HistorialOrden.
    """
    resultado = {'responsable': 0, 'compras': 0}

    if not orden or not getattr(orden, 'pk', None):
        return resultado

    # Paso 1: reglas globales — VM, SIC vacío o re-edición → no avisar.
    if getattr(orden, 'tipo_servicio', None) == 'venta_mostrador':
        return resultado

    sic_nuevo = (diagnostico_sic_nuevo or '').strip()
    sic_anterior = (diagnostico_sic_anterior or '').strip()
    if not sic_nuevo or sic_anterior:
        return resultado

    # Paso 2: push/campanita por audiencia (mensajes distintos).
    enviados_responsable = _avisar_responsable_seguimiento(orden)
    enviados_compras = _avisar_compras(orden)
    resultado['responsable'] = enviados_responsable
    resultado['compras'] = enviados_compras

    # Paso 3: correo en segundo plano (una sola tarea para ambas audiencias).
    if enviados_responsable or enviados_compras:
        _encolar_email_diagnostico_sic(orden)

    # Paso 4: historial de sistema con totales.
    if enviados_responsable or enviados_compras:
        _registrar_historial_aviso(
            orden,
            enviados_responsable=enviados_responsable,
            enviados_compras=enviados_compras,
        )

    logger.info(
        '[AVISO-DIAG-SIC] Orden %s: responsable=%s compras=%s',
        orden.pk,
        enviados_responsable,
        enviados_compras,
    )
    return resultado


def url_relativa_detalle_orden(orden: 'OrdenServicio') -> str:
    """
    Ruta relativa al detalle de la orden (push, campanita y anclas).

    Args:
        orden: OrdenServicio.

    Returns:
        str: ruta relativa lista para reverse + href.
    """
    return reverse(
        'servicio_tecnico:detalle_orden',
        kwargs={'orden_id': orden.pk},
    )


def destinatarios_responsable_seguimiento(orden: 'OrdenServicio') -> List['Empleado']:
    """
    Responsable de seguimiento con usuario activo (para correo/push).

    Args:
        orden: OrdenServicio (FK responsable_seguimiento).

    Returns:
        Lista de 0 o 1 Empleado.
    """
    from inventario.models import Empleado

    responsable = getattr(orden, 'responsable_seguimiento', None)
    if responsable is None:
        return []

    # Recargar con user si hace falta (patrón notificaciones_recepcion).
    if responsable.user_id is None or getattr(responsable, 'user', None) is None:
        try:
            responsable = Empleado.objects.select_related('user').get(
                pk=responsable.pk
            )
        except Empleado.DoesNotExist:
            return []

    user = getattr(responsable, 'user', None)
    if user is None or not user.is_active:
        return []

    return [responsable]


def destinatarios_compras() -> List['Empleado']:
    """
    Todos los empleados activos con rol Compras y user activo.

    Returns:
        Lista de Empleado (puede estar vacía).
    """
    return obtener_empleados_compras()


def emails_de_empleados(empleados) -> List[str]:
    """
    Direcciones únicas en minúsculas de empleados con email configurado.

    Args:
        empleados: iterable de Empleado.

    Returns:
        Lista de correos sin vacíos ni duplicados.
    """
    vistos: set[str] = set()
    resultado: List[str] = []
    for empleado in empleados:
        correo = (getattr(empleado, 'email', None) or '').strip().lower()
        if not correo or correo in vistos:
            continue
        vistos.add(correo)
        resultado.append(correo)
    return resultado


def extracto_diagnostico_sic(texto: str, max_chars: int = _MAX_EXTRACTO_SIC) -> str:
    """
    Primeras líneas del SIC para el cuerpo del correo.

    Args:
        texto: Diagnóstico SIC completo.
        max_chars: Límite de caracteres.

    Returns:
        str: extracto con «…» si se truncó.
    """
    limpio = (texto or '').strip()
    if len(limpio) <= max_chars:
        return limpio
    return limpio[: max_chars - 1].rstrip() + '…'


def _avisar_responsable_seguimiento(orden: 'OrdenServicio') -> int:
    """
    Push + campanita al responsable de seguimiento.

    Returns:
        Cantidad de destinatarios notificados.
    """
    destinatarios = destinatarios_responsable_seguimiento(orden)
    if not destinatarios:
        logger.info(
            '[AVISO-DIAG-SIC] Orden %s: sin responsable de seguimiento activo',
            orden.pk,
        )
        return 0

    referencia = referencia_visible_orden(orden)
    titulo = 'Diagnóstico listo para compartir'
    mensaje = (
        f'La orden {referencia.texto} ya tiene Diagnóstico SIC. '
        f'Usa «Enviar diagnóstico» para compartirlo con el cliente.'
    )
    url = url_relativa_detalle_orden(orden)

    return enviar_push_y_campanita(
        destinatarios,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
        app_origen='servicio_tecnico',
    )


def _avisar_compras(orden: 'OrdenServicio') -> int:
    """
    Push + campanita a todo el personal con rol Compras.

    Returns:
        Cantidad de destinatarios notificados.
    """
    destinatarios = destinatarios_compras()
    if not destinatarios:
        logger.info(
            '[AVISO-DIAG-SIC] Orden %s: sin empleados de Compras activos',
            orden.pk,
        )
        return 0

    referencia = referencia_visible_orden(orden)
    titulo = 'Diagnóstico SIC disponible — cotizar piezas'
    mensaje = (
        f'La orden {referencia.texto} tiene Diagnóstico SIC. '
        f'Revisa los componentes identificados y comienza la cotización.'
    )
    url = url_relativa_detalle_orden(orden)

    return enviar_push_y_campanita(
        destinatarios,
        titulo=titulo,
        mensaje=mensaje,
        url=url,
        app_origen='servicio_tecnico',
    )


def _encolar_email_diagnostico_sic(orden: 'OrdenServicio') -> None:
    """
    Encola la tarea Celery de correo (no bloquea al técnico).

    Efectos secundarios:
        Llama a .delay() con db_alias del país activo.
    """
    from config.paises_config import get_pais_actual
    from servicio_tecnico.tasks_diagnostico import notificar_diagnostico_sic_listo_task

    try:
        db_alias = get_pais_actual()['db_alias']
        notificar_diagnostico_sic_listo_task.delay(
            orden.pk,
            db_alias=db_alias,
        )
    except Exception as exc:
        logger.warning(
            '[AVISO-DIAG-SIC] No se pudo encolar correo (orden=%s): %s',
            orden.pk,
            exc,
        )


def _registrar_historial_aviso(
    orden: 'OrdenServicio',
    *,
    enviados_responsable: int,
    enviados_compras: int,
) -> None:
    """Escribe en el timeline que se avisó a responsable y/o Compras."""
    from servicio_tecnico.models import HistorialOrden

    comentario = (
        'Aviso de Diagnóstico SIC listo: '
        f'responsable seguimiento ({enviados_responsable}); '
        f'Compras ({enviados_compras})'
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
            '[AVISO-DIAG-SIC] No se pudo escribir historial orden %s: %s',
            orden.pk,
            exc,
        )
