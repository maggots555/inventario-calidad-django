"""
Utilidades para recordatorios push de imágenes faltantes en órdenes de servicio.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Celery Beat ejecuta una tarea diaria que busca órdenes con fotos obligatorias
pendientes. Este módulo concentra TODA la lógica de negocio (quién avisar,
cuándo y con qué mensaje) para que las tareas Celery solo orquesten el envío.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from django.db.models import Min, OuterRef, Q, Subquery
from django.utils import timezone

from config.constants import TIPO_IMAGEN_CHOICES
from servicio_tecnico.models import HistorialOrden, OrdenServicio, RecordatorioImagenOrden

# Plazo mínimo antes del primer recordatorio (48 horas)
HORAS_ANTES_RECORDATORIO = 48

# Estados finales donde ya no tiene sentido pedir fotos de ingreso al inspector
ESTADOS_EXCLUIDOS_INGRESO_INSPECTOR = {'cancelado', 'entregado'}

# Etiquetas legibles de tipos de imagen para mensajes al técnico
ETIQUETAS_TIPO_IMAGEN = dict(TIPO_IMAGEN_CHOICES)


def obtener_etiqueta_orden(orden: OrdenServicio) -> str:
    """
    Devuelve el folio visible de la orden (orden_cliente o número interno).

    Args:
        orden: Instancia de OrdenServicio.

    Returns:
        str: Texto identificador para títulos de notificación.
    """
    try:
        return orden.detalle_equipo.orden_cliente or orden.numero_orden_interno
    except Exception:
        return orden.numero_orden_interno


def obtener_tipos_imagen(orden: OrdenServicio) -> set[str]:
    """
    Obtiene el conjunto de tipos de imagen ya subidos en la orden.

    Args:
        orden: Orden a evaluar.

    Returns:
        set[str]: Códigos de tipo presentes (ej. {'ingreso', 'egreso'}).
    """
    return set(orden.imagenes.values_list('tipo', flat=True).distinct())


def fecha_creacion_orden(orden: OrdenServicio) -> datetime:
    """
    Determina la fecha de creación de la orden en el sistema.

    EXPLICACIÓN PARA PRINCIPIANTES:
    OrdenServicio no tiene campo fecha_creacion. Usamos el evento de historial
    'creacion' y, si no existe, fecha_ingreso como respaldo.

    Args:
        orden: Orden a evaluar.

    Returns:
        datetime: Momento de referencia para las 48 h del inspector.
    """
    evento_creacion = (
        orden.historial.filter(tipo_evento='creacion')
        .order_by('fecha_evento')
        .values_list('fecha_evento', flat=True)
        .first()
    )
    if evento_creacion:
        return evento_creacion
    return orden.fecha_ingreso


def fecha_primera_imagen(orden: OrdenServicio, tipo: str) -> datetime | None:
    """
    Obtiene la fecha de la primera imagen subida de un tipo dado.

    Args:
        orden: Orden a evaluar.
        tipo: Código de tipo de imagen (ej. 'egreso').

    Returns:
        datetime | None: Fecha de subida más antigua o None si no hay fotos.
    """
    return (
        orden.imagenes.filter(tipo=tipo)
        .order_by('fecha_subida')
        .values_list('fecha_subida', flat=True)
        .first()
    )


def _limite_48_horas() -> datetime:
    """Calcula el instante límite: ahora menos 48 horas."""
    return timezone.now() - timedelta(hours=HORAS_ANTES_RECORDATORIO)


def debe_recordar_hoy(orden: OrdenServicio, tipo_recordatorio: str, db_alias: str = 'default') -> bool:
    """
    Indica si corresponde enviar recordatorio hoy (máximo uno por día).

    Args:
        orden: Orden candidata.
        tipo_recordatorio: 'ingreso_inspector' o 'tecnico_faltantes'.
        db_alias: Alias de BD del país (multi-tenant).

    Returns:
        bool: True si no se envió hoy o nunca se envió.
    """
    recordatorio = RecordatorioImagenOrden.objects.using(db_alias).filter(
        orden=orden,
        tipo=tipo_recordatorio,
    ).first()
    if not recordatorio:
        return True

    hoy = timezone.localdate()
    ultimo = timezone.localtime(recordatorio.fecha_ultimo_envio).date()
    return ultimo < hoy


def registrar_envio_recordatorio(
    orden: OrdenServicio,
    tipo_recordatorio: str,
    db_alias: str = 'default',
) -> None:
    """
    Guarda o actualiza la fecha del último recordatorio enviado.

    Efectos secundarios:
        Crea o actualiza un registro en RecordatorioImagenOrden.
    """
    RecordatorioImagenOrden.objects.using(db_alias).update_or_create(
        orden=orden,
        tipo=tipo_recordatorio,
        defaults={'fecha_ultimo_envio': timezone.now()},
    )


def orden_requiere_recordatorio_ingreso_inspector(orden: OrdenServicio) -> bool:
    """
    Evalúa si una orden debe recordar al inspector que suba fotos de ingreso.

    Reglas:
        - No cancelada ni entregada.
        - Sin imágenes de tipo 'ingreso'.
        - Creada hace al menos 48 horas.
    """
    if orden.estado in ESTADOS_EXCLUIDOS_INGRESO_INSPECTOR:
        return False

    tipos = obtener_tipos_imagen(orden)
    if 'ingreso' in tipos:
        return False

    if fecha_creacion_orden(orden) > _limite_48_horas():
        return False

    return True


def tipos_faltantes_tecnico(orden: OrdenServicio) -> list[str]:
    """
    Devuelve los tipos de imagen que faltan al técnico según el flujo de la orden.

    Venta mostrador: falta 'reparacion' si ya hay egreso.
    Diagnóstico: faltan 'diagnostico' y/o 'reparacion' si ya hay egreso.
    """
    tipos = obtener_tipos_imagen(orden)
    if 'egreso' not in tipos:
        return []

    fecha_egreso = fecha_primera_imagen(orden, 'egreso')
    if not fecha_egreso or fecha_egreso > _limite_48_horas():
        return []

    if orden.tipo_servicio == 'venta_mostrador':
        if 'reparacion' not in tipos:
            return ['reparacion']
        return []

    faltantes: list[str] = []
    if 'diagnostico' not in tipos:
        faltantes.append('diagnostico')
    if 'reparacion' not in tipos:
        faltantes.append('reparacion')
    return faltantes


def orden_requiere_recordatorio_tecnico(orden: OrdenServicio) -> bool:
    """True si el técnico asignado debe recibir recordatorio por fotos faltantes."""
    if not orden.tecnico_asignado_actual:
        return False
    if not orden.tecnico_asignado_actual.user_id:
        return False
    if not orden.tecnico_asignado_actual.user.is_active:
        return False
    return bool(tipos_faltantes_tecnico(orden))


def ordenes_pendientes_ingreso_inspector(db_alias: str) -> Iterable[OrdenServicio]:
    """
    Queryset de órdenes candidatas a recordatorio de ingreso para inspectores.

    Args:
        db_alias: Alias de base de datos del país activo.

    Yields:
        OrdenServicio: Órdenes que cumplen reglas y deben recordarse hoy.
    """
    limite = _limite_48_horas()

    # Subconsulta: fecha del evento 'creacion' en historial
    fecha_creacion_subq = (
        HistorialOrden.objects.using(db_alias)
        .filter(orden=OuterRef('pk'), tipo_evento='creacion')
        .order_by('fecha_evento')
        .values('fecha_evento')[:1]
    )

    candidatas = (
        OrdenServicio.objects.using(db_alias)
        .exclude(estado__in=ESTADOS_EXCLUIDOS_INGRESO_INSPECTOR)
        .exclude(imagenes__tipo='ingreso')
        .annotate(fecha_creacion_sistema=Subquery(fecha_creacion_subq))
        .select_related('detalle_equipo')
        .distinct()
    )

    for orden in candidatas:
        # Usar fecha de creación del historial o fecha_ingreso como respaldo
        referencia = orden.fecha_creacion_sistema or orden.fecha_ingreso
        if referencia > limite:
            continue
        if not debe_recordar_hoy(orden, 'ingreso_inspector', db_alias):
            continue
        yield orden


def ordenes_pendientes_tecnico(db_alias: str) -> Iterable[OrdenServicio]:
    """
    Queryset de órdenes candidatas a recordatorio de evidencias para el técnico.

    Args:
        db_alias: Alias de base de datos del país activo.

    Yields:
        OrdenServicio: Órdenes con egreso antiguo y fotos faltantes según flujo.
    """
    limite = _limite_48_horas()

    candidatas = (
        OrdenServicio.objects.using(db_alias)
        .filter(imagenes__tipo='egreso')
        .annotate(fecha_egreso=Min('imagenes__fecha_subida', filter=Q(imagenes__tipo='egreso')))
        .filter(fecha_egreso__lte=limite)
        .select_related('tecnico_asignado_actual__user', 'detalle_equipo')
        .distinct()
    )

    for orden in candidatas:
        if not orden_requiere_recordatorio_tecnico(orden):
            continue
        if not debe_recordar_hoy(orden, 'tecnico_faltantes', db_alias):
            continue
        yield orden


def construir_mensaje_recordatorio_ingreso_inspector(orden: OrdenServicio) -> tuple[str, str]:
    """Construye título y mensaje para inspectores (ingreso faltante)."""
    etiqueta = obtener_etiqueta_orden(orden)
    titulo = f'Recordatorio: sube fotos de ingreso — {etiqueta}'
    mensaje = (
        f'La orden {etiqueta} lleva más de 48 horas sin evidencia fotográfica de ingreso. '
        f'Por favor sube las imágenes correspondientes.'
    )
    return titulo, mensaje


def construir_mensaje_recordatorio_tecnico(orden: OrdenServicio) -> tuple[str, str]:
    """Construye título y mensaje para el técnico según tipos faltantes."""
    etiqueta = obtener_etiqueta_orden(orden)
    faltantes = tipos_faltantes_tecnico(orden)
    nombres = [ETIQUETAS_TIPO_IMAGEN.get(t, t) for t in faltantes]
    lista = ', '.join(nombres)

    titulo = f'Faltan fotos — {etiqueta}'
    if orden.tipo_servicio == 'venta_mostrador':
        mensaje = (
            f'La orden {etiqueta} ya tiene fotos de egreso pero aún faltan de reparación. '
            f'Sube las evidencias pendientes: {lista}.'
        )
    else:
        mensaje = (
            f'La orden {etiqueta} ya tiene fotos de egreso pero faltan evidencias de: {lista}. '
            f'Por favor complétalas lo antes posible.'
        )
    return titulo, mensaje
