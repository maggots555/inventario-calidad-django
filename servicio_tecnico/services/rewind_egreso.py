"""
Reglas de negocio del video rewind de egreso (individual y masivo).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El rewind NO es un modelo aparte. Es el video resumen (FFmpeg) que se manda
al cliente por correo. Hoy el botón del detalle de orden lo dispara uno a uno.

Este módulo es el "cerebro":
  1) Decide qué órdenes YA pueden mandar rewind y AÚN no lo han enviado.
  2) Recupera los CC del correo de ingreso (si existieron).
  3) Encola la misma cadena Celery del envío individual.

Las vistas HTTP solo preguntan y muestran messages. FFmpeg y el correo
siguen en tasks.py (no se duplican aquí).
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta

from django.db.models import Exists, OuterRef, Q, QuerySet
from django.utils import timezone

from servicio_tecnico.models import HistorialOrden, OrdenServicio

logger = logging.getLogger('servicio_tecnico')

# Cuántos días hacia atrás se revisan órdenes YA entregadas.
# EXPLICACIÓN: si gerencia cerró primero y olvidó el rewind, todavía entra.
DIAS_ENTREGADO_REWIND_PENDIENTE = 30

# Email placeholder de DetalleEquipo: no es un cliente real.
EMAIL_CLIENTE_DUMMY = 'cliente@ejemplo.com'

# Subcadena que el detalle de orden usa para marcar "rewind ya enviado".
MARCA_HISTORIAL_REWIND = 'video rewind'

# Grupos Django que pueden disparar el envío masivo (igual que Cerrar Finalizados).
ROLES_GERENCIA_REWIND = ('Gerente Operacional', 'Gerente General')

TIPOS_FOTO_DIAGNOSTICO = frozenset({'ingreso', 'diagnostico', 'reparacion', 'egreso'})
TIPOS_FOTO_VENTA_MOSTRADOR = frozenset({'ingreso', 'reparacion', 'egreso'})

# Regex igual al rewind individual: "Copia a: a@x.com, b@y.com"
_RE_CC_INGRESO = re.compile(r'Copia a:\s*(.+)', re.IGNORECASE)


def usuario_es_gerencia(user) -> bool:
    """
    True si el usuario puede usar el botón masivo Mandar Rewind.

    Args:
        user: usuario autenticado de Django (puede ser AnonymousUser).

    Returns:
        True para superusuario o grupos de gerencia; False en cualquier otro caso.

    Efectos secundarios:
        Ninguno (solo lectura de grupos).
    """
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    # Superusuario ve el mismo botón que gerencia en lista_ordenes.html.
    if getattr(user, 'is_superuser', False):
        return True
    grupos = set(user.groups.values_list('name', flat=True))
    return bool(grupos.intersection(ROLES_GERENCIA_REWIND))


def tipos_foto_requeridos(orden: OrdenServicio) -> frozenset[str]:
    """
    Tipos de foto mínimos para armar el rewind de esa orden.

    Args:
        orden: OrdenServicio (se mira tipo_servicio).

    Returns:
        3 tipos en venta mostrador; 4 tipos en diagnóstico.
    """
    if orden.tipo_servicio == 'venta_mostrador':
        return TIPOS_FOTO_VENTA_MOSTRADOR
    return TIPOS_FOTO_DIAGNOSTICO


def email_cliente_valido(orden: OrdenServicio) -> bool:
    """
    True si hay un email real al que mandar el correo rewind.

    Args:
        orden: debe traer detalle_equipo (select_related o acceso lazy).

    Returns:
        False si no hay detalle, está vacío o es el dummy de sistema.
    """
    detalle = getattr(orden, 'detalle_equipo', None)
    email = getattr(detalle, 'email_cliente', None) if detalle else None
    if not email:
        return False
    return email.strip() != EMAIL_CLIENTE_DUMMY


def orden_tiene_fotos_rewind(orden: OrdenServicio) -> bool:
    """
    True si la galería cubre todos los tipos que el rewind necesita.

    Args:
        orden: con imagenes prefetched si se llama en lote (evita N+1).

    Returns:
        True cuando el set de tipos de ImagenOrden cubre el requerido.
    """
    # .all() usa el prefetch; no uses values_list aquí (iría otra vez a BD).
    tipos_presentes = {img.tipo for img in orden.imagenes.all()}
    return tipos_foto_requeridos(orden).issubset(tipos_presentes)


def queryset_candidatas_rewind() -> QuerySet:
    """
    Órdenes en ventana de negocio, con email y SIN historial de rewind.

    Returns:
        QuerySet de OrdenServicio (aún NO filtra fotos; eso va en Python).

    Efectos secundarios:
        Ninguno. La exclusión de 'video rewind' evita reenviar y también
        evita un segundo clic del botón masivo (el historial se escribe al encolar).
    """
    limite_entregado = timezone.now() - timedelta(days=DIAS_ENTREGADO_REWIND_PENDIENTE)

    # Subconsulta: ¿ya hay un email cuyo texto mencione el rewind?
    ya_enviado = HistorialOrden.objects.filter(
        orden_id=OuterRef('pk'),
        tipo_evento='email',
        comentario__icontains=MARCA_HISTORIAL_REWIND,
    )

    return (
        OrdenServicio.objects.filter(
            Q(estado='finalizado')
            | Q(estado='entregado', fecha_entrega__gte=limite_entregado)
        )
        .select_related('detalle_equipo')
        .prefetch_related('imagenes')
        .annotate(_rewind_enviado=Exists(ya_enviado))
        .filter(_rewind_enviado=False)
        .exclude(detalle_equipo__email_cliente__isnull=True)
        .exclude(detalle_equipo__email_cliente='')
        .exclude(detalle_equipo__email_cliente=EMAIL_CLIENTE_DUMMY)
    )


def listar_rewinds_pendientes() -> list[OrdenServicio]:
    """
    Lista final: candidatas + fotos completas + email válido.

    Returns:
        Lista de órdenes listas para encolar (puede estar vacía).

    Efectos secundarios:
        Ninguno.
    """
    pendientes: list[OrdenServicio] = []
    # Paso 1: estado + email + no enviado (SQL).
    for orden in queryset_candidatas_rewind():
        # Paso 2: fotos 3/4 tipos (Python, porque diagnóstico ≠ venta mostrador).
        if not email_cliente_valido(orden):
            continue
        if orden_tiene_fotos_rewind(orden):
            pendientes.append(orden)
    return pendientes


def destinatarios_cc_ingreso(orden: OrdenServicio) -> list[str]:
    """
    Recupera los CC del último correo de imágenes de ingreso.

    Args:
        orden: orden cuyo historial se inspecciona.

    Returns:
        Lista de emails (puede ser vacía). Misma regla que el rewind individual.

    Efectos secundarios:
        Ninguno.
    """
    # El correo de ingreso deja un rastro de texto; no hay tabla de CC.
    historial_ingreso = (
        HistorialOrden.objects.filter(orden=orden, tipo_evento='email')
        .filter(comentario__icontains='imágenes de ingreso')
        .order_by('-fecha_evento')
        .first()
    )
    if not historial_ingreso:
        return []

    match_cc = _RE_CC_INGRESO.search(historial_ingreso.comentario)
    if not match_cc:
        return []

    # Misma limpieza que el rewind individual: solo tokens que parecen email.
    raw_cc = match_cc.group(1).strip()
    return [
        email.strip()
        for email in raw_cc.split(',')
        if email.strip() and '@' in email.strip()
    ]


def _delay_chain_rewind(
    orden_id: int,
    usuario_id: int | None,
    destinatarios_copia: list[str],
    db_alias: str,
):
    """
    Dispara la cadena Celery: generar video → enviar correo.

    Args:
        orden_id: PK de OrdenServicio.
        usuario_id: PK del User que pidió el envío (o None).
        destinatarios_copia: CC extraídos del ingreso.
        db_alias: país/tenant para el worker (nunca omitir).

    Returns:
        AsyncResult de la cadena (tiene .id).

    Efectos secundarios:
        Encola 2 tareas en Redis. No genera el video en este proceso.
    """
    # Import local: tasks.py es enorme; evitamos ciclos al cargar el service.
    from celery import chain as celery_chain

    from servicio_tecnico.tasks import (
        enviar_rewind_egreso_email_task,
        generar_video_resumen_task,
    )

    cadena = celery_chain(
        generar_video_resumen_task.s(orden_id, usuario_id, db_alias),
        enviar_rewind_egreso_email_task.s(
            orden_id, usuario_id, destinatarios_copia, db_alias
        ),
    )
    return cadena.delay()


def encolar_rewind_orden(orden: OrdenServicio, usuario, db_alias: str) -> str:
    """
    Encola el rewind de UNA orden y deja rastro inmediato en el historial.

    Args:
        orden: orden ya validada como elegible.
        usuario: User de Django (para task + empleado en historial).
        db_alias: alias de BD del país actual.

    Returns:
        ID de la tarea raíz de Celery (string).

    Efectos secundarios:
        Escribe HistorialOrden tipo email con 'video rewind' ANTES de que
        termine FFmpeg. Así el botón del detalle pasa a "ya enviado" y el
        masivo no vuelve a encolar la misma orden.
    """
    usuario_id = getattr(usuario, 'pk', None) if usuario else None
    copias = destinatarios_cc_ingreso(orden)
    tarea_raiz = _delay_chain_rewind(orden.pk, usuario_id, copias, db_alias)

    HistorialOrden.objects.create(
        orden=orden,
        usuario=getattr(usuario, 'empleado', None) if usuario else None,
        tipo_evento='email',
        comentario=(
            'Generación de video rewind al cliente iniciada — '
            f'tarea en segundo plano (task_id: {tarea_raiz.id})'
        ),
    )
    return str(tarea_raiz.id)


def encolar_rewinds_pendientes(usuario, db_alias: str) -> int:
    """
    Encola el rewind de todas las órdenes pendientes (botón masivo).

    Args:
        usuario: User que pulsó Mandar Rewind.
        db_alias: país actual (get_pais_actual()['db_alias']).

    Returns:
        Cantidad de cadenas Celery lanzadas con éxito.

    Efectos secundarios:
        N chains en cola + N filas de HistorialOrden. Si una orden falla,
        se registra en log y se continúa con las demás (no aborta el lote).
    """
    pendientes = listar_rewinds_pendientes()
    encoladas = 0

    for orden in pendientes:
        try:
            encolar_rewind_orden(orden, usuario, db_alias)
            encoladas += 1
        except Exception as exc:
            logger.warning(
                '[REWIND-BULK] No se pudo encolar orden %s: %s',
                orden.pk,
                exc,
            )

    return encoladas
