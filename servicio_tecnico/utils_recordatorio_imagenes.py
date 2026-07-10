"""
Utilidades para recordatorios push de imágenes faltantes en órdenes de servicio.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Hay DOS disparadores:

1) Inmediato: cuando la orden pasa a estado 'finalizado' (señal en signals.py),
   se avisa al técnico (fotos diag/rep según cotización) y a inspectores
   (si faltan fotos de egreso).

2) Diario (Celery Beat 8:00):
   - Inspectores: órdenes sin ingreso tras 2 días (48 h), solo si la orden
     tiene menos de 1 semana de antigüedad.
   - Técnicos / egreso inspector: órdenes que SIGUEN en 'finalizado' con
     fotos pendientes, solo si llevan ≤ 1 semana finalizadas.
   - Si ya pasaron más de 7 días, el Beat deja de insistir.

Este módulo concentra TODA la lógica de negocio (quién avisar, qué fotos
faltan y con qué mensaje) para que las tareas Celery solo orquesten el envío.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

from django.db.models import OuterRef, Subquery
from django.utils import timezone

from config.constants import TIPO_IMAGEN_CHOICES
from servicio_tecnico.models import Cotizacion, HistorialOrden, OrdenServicio, RecordatorioImagenOrden

# Plazo mínimo antes del recordatorio de ingreso al inspector (2 días = 48 h)
HORAS_ANTES_RECORDATORIO = 48

# Ventana máxima de repetición del Beat: después de 1 semana ya no insistimos
DIAS_MAX_VENTANA_RECORDATORIO = 7

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
        datetime: Momento de referencia para las 48 h del inspector (ingreso).
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


def _limite_48_horas() -> datetime:
    """Calcula el instante límite: ahora menos 48 horas (2 días)."""
    return timezone.now() - timedelta(hours=HORAS_ANTES_RECORDATORIO)


def _limite_ventana_maxima() -> datetime:
    """
    Calcula el corte de 1 semana: ahora menos 7 días.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El Beat diario solo insiste mientras la orden esté "fresca".
    Si la fecha de referencia es ANTERIOR a este instante, ya no notificamos.
    """
    return timezone.now() - timedelta(days=DIAS_MAX_VENTANA_RECORDATORIO)


def dentro_ventana_una_semana(fecha_referencia: datetime | None) -> bool:
    """
    Indica si una fecha de referencia tiene como máximo 7 días de antigüedad.

    Args:
        fecha_referencia: Fecha a evaluar (creación o finalización). None = fuera.

    Returns:
        bool: True si está dentro de la ventana de 1 semana.
    """
    if fecha_referencia is None:
        return False
    return fecha_referencia >= _limite_ventana_maxima()


def _obtener_cotizacion(orden: OrdenServicio) -> Cotizacion | None:
    """
    Obtiene la cotización de la orden si existe.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cotizacion es OneToOne con related_name='cotizacion'. Si la orden no tiene
    cotización, acceder a orden.cotizacion lanza DoesNotExist; aquí lo
    convertimos en None para simplificar las reglas.

    Args:
        orden: Orden a evaluar.

    Returns:
        Cotizacion | None: Cotización vinculada o None.
    """
    try:
        return orden.cotizacion
    except Cotizacion.DoesNotExist:
        return None


def _faltantes_entre(tipos_presentes: set[str], requeridos: list[str]) -> list[str]:
    """
    Filtra la lista de tipos requeridos y deja solo los que aún no se subieron.

    Args:
        tipos_presentes: Tipos ya subidos en la orden.
        requeridos: Tipos que deberían existir según la regla de negocio.

    Returns:
        list[str]: Tipos faltantes en el mismo orden que 'requeridos'.
    """
    return [t for t in requeridos if t not in tipos_presentes]


def debe_recordar_hoy(orden: OrdenServicio, tipo_recordatorio: str, db_alias: str = 'default') -> bool:
    """
    Indica si corresponde enviar recordatorio hoy (máximo uno por día).

    Args:
        orden: Orden candidata.
        tipo_recordatorio: 'ingreso_inspector', 'egreso_inspector' o 'tecnico_faltantes'.
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
        - Creada hace al menos 48 horas (2 días).
        - Creada hace como máximo 7 días (si ya pasó 1 semana, no insistir).
    """
    if orden.estado in ESTADOS_EXCLUIDOS_INGRESO_INSPECTOR:
        return False

    tipos = obtener_tipos_imagen(orden)
    if 'ingreso' in tipos:
        return False

    creacion = fecha_creacion_orden(orden)

    # Aún no cumplen 2 días → demasiado pronto
    if creacion > _limite_48_horas():
        return False

    # Más de 1 semana → el Beat ya no insiste
    if not dentro_ventana_una_semana(creacion):
        return False

    return True


def orden_requiere_recordatorio_egreso_inspector(orden: OrdenServicio) -> bool:
    """
    Evalúa si hay que avisar a inspectores por fotos de egreso faltantes.

    Reglas:
        - Estado actual = 'finalizado' (listo para entrega).
        - Sin ninguna imagen de tipo 'egreso'.
        - Finalizada hace ≤ 7 días (ventana del Beat; el aviso inmediato
          del día 0 siempre cae dentro de esta ventana).
    """
    if orden.estado != 'finalizado':
        return False

    # Si hay fecha y ya pasó 1 semana → no insistir (Beat).
    # Si aún no hay fecha (caso raro al guardar), no bloqueamos el aviso inmediato.
    if orden.fecha_finalizacion is not None and not dentro_ventana_una_semana(orden.fecha_finalizacion):
        return False

    tipos = obtener_tipos_imagen(orden)
    return 'egreso' not in tipos


def tipos_requeridos_tecnico(orden: OrdenServicio) -> list[str]:
    """
    Define qué tipos de foto debe tener el técnico según cotización / flujo.

    EXPLICACIÓN PARA PRINCIPIANTES — matriz de negocio:
    1) Si hay cotización aceptada → diagnóstico + reparación.
    2) Si hay cotización rechazada o pendiente (sin respuesta) → solo diagnóstico.
    3) Si NO hay cotización y es venta_mostrador → solo reparación.
    4) Si NO hay cotización y no es venta_mostrador → nada (no avisar).

    Args:
        orden: Orden a evaluar.

    Returns:
        list[str]: Códigos de tipo requeridos (puede estar vacía).
    """
    cotizacion = _obtener_cotizacion(orden)

    # Paso 1: hay cotización → la respuesta del cliente manda
    if cotizacion is not None:
        if cotizacion.usuario_acepto is True:
            return ['diagnostico', 'reparacion']
        # Rechazada (False) o pendiente (None): solo diagnóstico
        return ['diagnostico']

    # Paso 2: sin cotización → solo venta mostrador pide reparación
    if orden.tipo_servicio == 'venta_mostrador':
        return ['reparacion']

    # Paso 3: otro servicio sin cotización → no hay regla, no pedir nada
    return []


def tipos_faltantes_tecnico(orden: OrdenServicio) -> list[str]:
    """
    Devuelve los tipos de imagen que aún faltan al técnico.

    Solo aplica cuando la orden está en 'finalizado'. Ya no depende de
    que exista egreso ni de un plazo de 48 h tras el egreso.

    Args:
        orden: Orden a evaluar.

    Returns:
        list[str]: Tipos faltantes según la matriz de cotización/flujo.
    """
    if orden.estado != 'finalizado':
        return []

    requeridos = tipos_requeridos_tecnico(orden)
    if not requeridos:
        return []

    tipos = obtener_tipos_imagen(orden)
    return _faltantes_entre(tipos, requeridos)


def orden_requiere_recordatorio_tecnico(orden: OrdenServicio) -> bool:
    """
    True si el técnico asignado debe recibir recordatorio por fotos faltantes.

    Requisitos:
        - Estado 'finalizado'.
        - Finalizada hace ≤ 7 días (misma ventana del Beat).
        - Técnico asignado con usuario activo.
        - Al menos un tipo de foto requerido aún no subido.
    """
    if orden.estado != 'finalizado':
        return False
    # Misma ventana de 1 semana; sin fecha no bloqueamos el push inmediato
    if orden.fecha_finalizacion is not None and not dentro_ventana_una_semana(orden.fecha_finalizacion):
        return False
    if not orden.tecnico_asignado_actual:
        return False
    if not orden.tecnico_asignado_actual.user_id:
        return False
    if not orden.tecnico_asignado_actual.user.is_active:
        return False
    return bool(tipos_faltantes_tecnico(orden))


def ordenes_pendientes_ingreso_inspector(db_alias: str) -> Iterable[OrdenServicio]:
    """
    Órdenes candidatas a recordatorio de ingreso para inspectores (Beat diario).

    Ventana: creadas hace entre 2 días y 7 días (inclusive el corte).

    Args:
        db_alias: Alias de base de datos del país activo.

    Yields:
        OrdenServicio: Órdenes sin ingreso en ventana y que deben recordarse hoy.
    """
    limite_min = _limite_48_horas()
    limite_max = _limite_ventana_maxima()

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
        # Menos de 2 días → aún no toca
        if referencia > limite_min:
            continue
        # Más de 1 semana → ya no insistimos
        if referencia < limite_max:
            continue
        if not debe_recordar_hoy(orden, 'ingreso_inspector', db_alias):
            continue
        yield orden


def ordenes_pendientes_egreso_inspector(db_alias: str) -> Iterable[OrdenServicio]:
    """
    Órdenes en finalizado sin fotos de egreso (repetición diaria vía Beat).

    Solo órdenes finalizadas en los últimos 7 días.

    Args:
        db_alias: Alias de base de datos del país activo.

    Yields:
        OrdenServicio: Órdenes que aún requieren aviso de egreso hoy.
    """
    limite_max = _limite_ventana_maxima()

    candidatas = (
        OrdenServicio.objects.using(db_alias)
        .filter(estado='finalizado')
        .filter(fecha_finalizacion__gte=limite_max)
        .exclude(imagenes__tipo='egreso')
        .select_related('detalle_equipo')
        .distinct()
    )

    for orden in candidatas:
        if not orden_requiere_recordatorio_egreso_inspector(orden):
            continue
        if not debe_recordar_hoy(orden, 'egreso_inspector', db_alias):
            continue
        yield orden


def ordenes_pendientes_tecnico(db_alias: str) -> Iterable[OrdenServicio]:
    """
    Órdenes en finalizado con evidencias pendientes para el técnico (Beat).

    Solo órdenes finalizadas en los últimos 7 días.

    Args:
        db_alias: Alias de base de datos del país activo.

    Yields:
        OrdenServicio: Órdenes que aún requieren aviso al técnico hoy.
    """
    limite_max = _limite_ventana_maxima()

    candidatas = (
        OrdenServicio.objects.using(db_alias)
        .filter(estado='finalizado')
        .filter(fecha_finalizacion__gte=limite_max)
        .select_related(
            'tecnico_asignado_actual__user',
            'detalle_equipo',
            'cotizacion',
        )
        .distinct()
    )

    for orden in candidatas:
        if not orden_requiere_recordatorio_tecnico(orden):
            continue
        if not debe_recordar_hoy(orden, 'tecnico_faltantes', db_alias):
            continue
        yield orden


def construir_mensaje_recordatorio_ingreso_inspector(orden: OrdenServicio) -> tuple[str, str]:
    """Construye título y mensaje para inspectores (ingreso faltante tras 2 días)."""
    etiqueta = obtener_etiqueta_orden(orden)
    titulo = f'Recordatorio: sube fotos de ingreso — {etiqueta}'
    mensaje = (
        f'La orden {etiqueta} lleva más de 2 días sin evidencia fotográfica de ingreso. '
        f'Por favor sube las imágenes correspondientes.'
    )
    return titulo, mensaje


def construir_mensaje_recordatorio_egreso_inspector(orden: OrdenServicio) -> tuple[str, str]:
    """Construye título y mensaje para inspectores (egreso faltante en finalizado)."""
    etiqueta = obtener_etiqueta_orden(orden)
    titulo = f'Recordatorio: sube fotos de egreso — {etiqueta}'
    mensaje = (
        f'La orden {etiqueta} está en Finalizado - Listo para Entrega pero aún no tiene '
        f'evidencia fotográfica de egreso. Por favor sube las imágenes correspondientes.'
    )
    return titulo, mensaje


def construir_mensaje_recordatorio_tecnico(orden: OrdenServicio) -> tuple[str, str]:
    """
    Construye título y mensaje para el técnico según tipos faltantes y cotización.

    Args:
        orden: Orden en finalizado con fotos pendientes.

    Returns:
        tuple[str, str]: (titulo, mensaje) listos para push/campanita.
    """
    etiqueta = obtener_etiqueta_orden(orden)
    faltantes = tipos_faltantes_tecnico(orden)
    nombres = [ETIQUETAS_TIPO_IMAGEN.get(t, t) for t in faltantes]
    lista = ', '.join(nombres)

    titulo = f'Faltan fotos — {etiqueta}'

    cotizacion = _obtener_cotizacion(orden)
    if cotizacion is not None and cotizacion.usuario_acepto is True:
        contexto = 'cotización aceptada'
    elif cotizacion is not None and cotizacion.usuario_acepto is False:
        contexto = 'cotización rechazada'
    elif cotizacion is not None:
        contexto = 'cotización pendiente de respuesta'
    elif orden.tipo_servicio == 'venta_mostrador':
        contexto = 'venta mostrador'
    else:
        contexto = 'orden finalizada'

    mensaje = (
        f'La orden {etiqueta} ({contexto}) está lista para entrega pero faltan evidencias de: '
        f'{lista}. Por favor súbelas lo antes posible.'
    )
    return titulo, mensaje
