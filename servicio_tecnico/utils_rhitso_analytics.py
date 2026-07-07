"""
Utilidades de análisis y embudo de conversión RHITSO.

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo calcula métricas del embudo RHITSO a partir del historial
de estados en SeguimientoRHITSO. Cada orden candidata puede pasar por
estados como "USUARIO ACEPTA ENVIO A RHITSO" o "CLIENTE NO ACEPTA COTIZACIÓN";
aquí contamos cuántas órdenes alcanzaron cada estado al menos una vez.
"""

from datetime import date, datetime

from django.db.models import Prefetch, Q
from django.utils import timezone

from .models import OrdenServicio, SeguimientoRHITSO

# ============================================================================
# CONSTANTES — Estados del embudo de conversión RHITSO
# ============================================================================
ESTADO_ACEPTA_ENVIO = 'USUARIO ACEPTA ENVIO A RHITSO'
ESTADO_RECHAZA_ENVIO = 'USUARIO NO ACEPTA ENVIO A RHITSO'
ESTADO_ACEPTA_COTIZ = 'CLIENTE ACEPTA COTIZACIÓN'
ESTADO_RECHAZA_COTIZ = 'CLIENTE NO ACEPTA COTIZACIÓN'
ESTADO_NO_APTO = 'NO APTO PARA REPARACIÓN'

ESTADOS_DECISION_ENVIO = (ESTADO_ACEPTA_ENVIO, ESTADO_RECHAZA_ENVIO)


def _normalizar_fecha_inicio(fecha_inicio):
    """
    Convierte fecha de inicio a datetime con zona horaria (inicio del día).

    Args:
        fecha_inicio: str 'YYYY-MM-DD', date o datetime, o None.

    Returns:
        datetime timezone-aware o None.
    """
    if not fecha_inicio:
        return None
    if isinstance(fecha_inicio, str):
        fecha_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        fecha_dt = datetime.combine(fecha_dt.date(), datetime.min.time())
        return timezone.make_aware(fecha_dt) if timezone.is_naive(fecha_dt) else fecha_dt
    if isinstance(fecha_inicio, date) and not isinstance(fecha_inicio, datetime):
        fecha_dt = datetime.combine(fecha_inicio, datetime.min.time())
        return timezone.make_aware(fecha_dt)
    return fecha_inicio


def _normalizar_fecha_fin(fecha_fin):
    """
    Convierte fecha de fin a datetime con zona horaria (fin del día).

    Args:
        fecha_fin: str 'YYYY-MM-DD', date o datetime, o None.

    Returns:
        datetime timezone-aware o None.
    """
    if not fecha_fin:
        return None
    if isinstance(fecha_fin, str):
        fecha_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
        fecha_dt = datetime.combine(fecha_dt.date(), datetime.max.time())
        return timezone.make_aware(fecha_dt) if timezone.is_naive(fecha_dt) else fecha_dt
    if isinstance(fecha_fin, date) and not isinstance(fecha_fin, datetime):
        fecha_dt = datetime.combine(fecha_fin, datetime.max.time())
        return timezone.make_aware(fecha_dt)
    return fecha_fin


def obtener_queryset_candidatos(fecha_inicio=None, fecha_fin=None, sucursal_id=None):
    """
    Retorna el queryset base de órdenes candidatas RHITSO con filtros opcionales.

    Args:
        fecha_inicio: Filtro por fecha_ingreso >= (str, date o datetime).
        fecha_fin: Filtro por fecha_ingreso <= (str, date o datetime).
        sucursal_id: ID de sucursal para filtrar.

    Returns:
        QuerySet de OrdenServicio optimizado con relaciones frecuentes.
    """
    candidatos = OrdenServicio.objects.filter(
        es_candidato_rhitso=True
    ).select_related(
        'detalle_equipo',
        'sucursal',
        'tecnico_asignado_actual',
    ).prefetch_related(
        Prefetch(
            'seguimientos_rhitso',
            queryset=SeguimientoRHITSO.objects.select_related(
                'estado', 'usuario_actualizacion'
            ).order_by('-fecha_actualizacion'),
        ),
    )

    fecha_inicio_dt = _normalizar_fecha_inicio(fecha_inicio)
    if fecha_inicio_dt:
        candidatos = candidatos.filter(fecha_ingreso__gte=fecha_inicio_dt)

    fecha_fin_dt = _normalizar_fecha_fin(fecha_fin)
    if fecha_fin_dt:
        candidatos = candidatos.filter(fecha_ingreso__lte=fecha_fin_dt)

    if sucursal_id:
        candidatos = candidatos.filter(sucursal_id=sucursal_id)

    return candidatos.order_by('-fecha_ingreso')


def _con_estado_historico(queryset, nombre_estado):
    """
    Filtra órdenes que alguna vez pasaron por un estado RHITSO específico.

    Args:
        queryset: QuerySet de OrdenServicio.
        nombre_estado: Texto exacto del catálogo EstadoRHITSO.estado.

    Returns:
        QuerySet distinto por orden.
    """
    return queryset.filter(
        seguimientos_rhitso__estado__estado=nombre_estado
    ).distinct()


def _porcentaje(parte, total):
    """Calcula porcentaje redondeado a 1 decimal; retorna 0.0 si total es 0."""
    if not total:
        return 0.0
    return round((parte / total) * 100, 1)


def _ids_de_queryset(queryset):
    """Extrae lista de IDs de un queryset de órdenes."""
    return list(queryset.values_list('id', flat=True))


def obtener_embudo_rhitso(fecha_inicio=None, fecha_fin=None, sucursal_id=None):
    """
    Calcula el embudo completo de conversión RHITSO.

    Args:
        fecha_inicio: Filtro opcional por fecha de ingreso.
        fecha_fin: Filtro opcional por fecha de ingreso.
        sucursal_id: Filtro opcional por sucursal.

    Returns:
        dict con conteos, porcentajes, IDs por segmento y queryset de candidatos.
    """
    candidatos = obtener_queryset_candidatos(fecha_inicio, fecha_fin, sucursal_id)
    total_candidatos = candidatos.count()

    acepto_envio = _con_estado_historico(candidatos, ESTADO_ACEPTA_ENVIO)
    rechazo_envio = _con_estado_historico(candidatos, ESTADO_RECHAZA_ENVIO)

    # Sin decisión de envío: nunca llegaron a aceptar ni rechazar envío
    sin_decision_envio = candidatos.exclude(
        Q(seguimientos_rhitso__estado__estado=ESTADO_ACEPTA_ENVIO)
        | Q(seguimientos_rhitso__estado__estado=ESTADO_RECHAZA_ENVIO)
    ).distinct()

    # Cohorte nivel 3: solo quienes aceptaron el envío a RHITSO
    cohorte_acepto_envio = acepto_envio
    total_cohorte_acepto = cohorte_acepto_envio.count()

    acepto_cotiz = _con_estado_historico(cohorte_acepto_envio, ESTADO_ACEPTA_COTIZ)
    rechazo_cotiz = _con_estado_historico(cohorte_acepto_envio, ESTADO_RECHAZA_COTIZ)
    no_apto = _con_estado_historico(cohorte_acepto_envio, ESTADO_NO_APTO)

    # En proceso: aceptaron envío pero sin ningún estado de cotización/no apto
    en_proceso_cohorte = cohorte_acepto_envio.exclude(
        Q(seguimientos_rhitso__estado__estado=ESTADO_ACEPTA_COTIZ)
        | Q(seguimientos_rhitso__estado__estado=ESTADO_RECHAZA_COTIZ)
        | Q(seguimientos_rhitso__estado__estado=ESTADO_NO_APTO)
    ).distinct()

    return {
        'candidatos_qs': candidatos,
        'total_candidatos': total_candidatos,
        # Nivel 2 — decisión de envío
        'acepto_envio_count': acepto_envio.count(),
        'rechazo_envio_count': rechazo_envio.count(),
        'sin_decision_envio_count': sin_decision_envio.count(),
        'acepto_envio_pct': _porcentaje(acepto_envio.count(), total_candidatos),
        'rechazo_envio_pct': _porcentaje(rechazo_envio.count(), total_candidatos),
        'sin_decision_envio_pct': _porcentaje(sin_decision_envio.count(), total_candidatos),
        'acepto_envio_ids': _ids_de_queryset(acepto_envio),
        'rechazo_envio_ids': _ids_de_queryset(rechazo_envio),
        'sin_decision_envio_ids': _ids_de_queryset(sin_decision_envio),
        # Nivel 3 — cohorte aceptó envío
        'cohorte_acepto_envio_qs': cohorte_acepto_envio,
        'total_cohorte_acepto': total_cohorte_acepto,
        'acepto_cotiz_count': acepto_cotiz.count(),
        'rechazo_cotiz_count': rechazo_cotiz.count(),
        'no_apto_count': no_apto.count(),
        'en_proceso_cohorte_count': en_proceso_cohorte.count(),
        'acepto_cotiz_pct': _porcentaje(acepto_cotiz.count(), total_cohorte_acepto),
        'rechazo_cotiz_pct': _porcentaje(rechazo_cotiz.count(), total_cohorte_acepto),
        'no_apto_pct': _porcentaje(no_apto.count(), total_cohorte_acepto),
        'en_proceso_cohorte_pct': _porcentaje(en_proceso_cohorte.count(), total_cohorte_acepto),
        'acepto_cotiz_ids': _ids_de_queryset(acepto_cotiz),
        'rechazo_cotiz_ids': _ids_de_queryset(rechazo_cotiz),
        'no_apto_ids': _ids_de_queryset(no_apto),
        'en_proceso_cohorte_ids': _ids_de_queryset(en_proceso_cohorte),
        # Querysets para detalle
        'acepto_envio_qs': acepto_envio,
        'rechazo_envio_qs': rechazo_envio,
        'sin_decision_envio_qs': sin_decision_envio,
        'acepto_cotiz_qs': acepto_cotiz,
        'rechazo_cotiz_qs': rechazo_cotiz,
        'no_apto_qs': no_apto,
        'en_proceso_cohorte_qs': en_proceso_cohorte,
    }


def obtener_comentarios_rechazo_cotizacion(cohorte_qs):
    """
    Obtiene seguimientos manuales con observaciones de cierre negativo en RHITSO.

    Incluye cambios de estado a:
    - CLIENTE NO ACEPTA COTIZACIÓN
    - NO APTO PARA REPARACIÓN

    Solo registros manuales (es_cambio_automatico=False). Si no hay
    observaciones, el reporte Excel muestra "Sin comentario disponible".

    Args:
        cohorte_qs: QuerySet de órdenes candidatas RHITSO.

    Returns:
        QuerySet de SeguimientoRHITSO ordenado por fecha descendente.
    """
    return SeguimientoRHITSO.objects.filter(
        orden__in=cohorte_qs,
        estado__estado__in=[ESTADO_RECHAZA_COTIZ, ESTADO_NO_APTO],
        es_cambio_automatico=False,
    ).select_related(
        'orden',
        'orden__detalle_equipo',
        'orden__sucursal',
        'usuario_actualizacion',
        'estado',
    ).order_by('-fecha_actualizacion')


def obtener_filas_hoja_rechazos_y_no_aptos(candidatos_qs):
    """
    Lista seguimientos para la hoja Excel de rechazos y no aptos.

    Incluye todos los cambios manuales aunque no tengan observaciones.
    Si una orden solo tiene registro automático para ese estado, también
    se incluye una fila (el Excel mostrará "Sin comentario disponible").

    Args:
        candidatos_qs: QuerySet de órdenes candidatas RHITSO.

    Returns:
        list[SeguimientoRHITSO]: Filas ordenadas por fecha descendente.
    """
    estados_cierre = [ESTADO_RECHAZA_COTIZ, ESTADO_NO_APTO]

    manuales = list(obtener_comentarios_rechazo_cotizacion(candidatos_qs))

    # Evitar duplicar orden+estado ya cubierto por un cambio manual
    cubiertas = {(seg.orden_id, seg.estado.estado) for seg in manuales}

    automaticos_sin_manual = SeguimientoRHITSO.objects.filter(
        orden__in=candidatos_qs,
        estado__estado__in=estados_cierre,
        es_cambio_automatico=True,
    ).select_related(
        'orden',
        'orden__detalle_equipo',
        'orden__sucursal',
        'usuario_actualizacion',
        'estado',
    ).order_by('-fecha_actualizacion')

    extras = []
    for seg in automaticos_sin_manual:
        clave = (seg.orden_id, seg.estado.estado)
        if clave not in cubiertas:
            extras.append(seg)
            cubiertas.add(clave)

    return sorted(
        manuales + extras,
        key=lambda s: s.fecha_actualizacion,
        reverse=True,
    )


def _orden_tiene_estado_historico(orden, nombre_estado):
    """Verifica si una orden pasó alguna vez por un estado RHITSO."""
    return orden.seguimientos_rhitso.filter(estado__estado=nombre_estado).exists()


def construir_fila_detalle_orden(orden):
    """
    Construye un diccionario con datos de detalle para reportes Excel/dashboard.

    Args:
        orden: Instancia de OrdenServicio (candidato RHITSO).

    Returns:
        dict con columnas de identificación y flags de segmento del embudo.
    """
    detalle = orden.detalle_equipo

    # Técnico asignado directamente en la orden de servicio
    if orden.tecnico_asignado_actual:
        tecnico_asignado_nombre = orden.tecnico_asignado_actual.nombre_completo
    else:
        tecnico_asignado_nombre = 'Sin asignar'

    return {
        'id': orden.id,
        'numero_orden_interno': orden.numero_orden_interno,
        'orden_cliente': detalle.orden_cliente if detalle else 'N/A',
        'numero_serie': detalle.numero_serie if detalle else 'N/A',
        'marca': detalle.marca if detalle else 'N/A',
        'modelo': detalle.modelo if detalle else 'N/A',
        'sucursal': orden.sucursal.nombre if orden.sucursal else 'N/A',
        'fecha_ingreso': orden.fecha_ingreso,
        'tecnico_asignado': tecnico_asignado_nombre,
        'estado_rhitso_actual': orden.estado_rhitso or 'Pendiente',
        'estado_orden': orden.get_estado_display(),
        'acepto_envio': _orden_tiene_estado_historico(orden, ESTADO_ACEPTA_ENVIO),
        'rechazo_envio': _orden_tiene_estado_historico(orden, ESTADO_RECHAZA_ENVIO),
        'acepto_cotiz': _orden_tiene_estado_historico(orden, ESTADO_ACEPTA_COTIZ),
        'rechazo_cotiz': _orden_tiene_estado_historico(orden, ESTADO_RECHAZA_COTIZ),
        'no_apto': _orden_tiene_estado_historico(orden, ESTADO_NO_APTO),
    }


def obtener_detalle_todas_candidatas(fecha_inicio=None, fecha_fin=None, sucursal_id=None):
    """
    Lista de detalle para todas las órdenes candidatas con flags de embudo.

    Args:
        fecha_inicio: Filtro opcional por fecha de ingreso.
        fecha_fin: Filtro opcional por fecha de ingreso.
        sucursal_id: Filtro opcional por sucursal.

    Returns:
        list[dict]: Una fila por orden candidata.
    """
    candidatos = obtener_queryset_candidatos(fecha_inicio, fecha_fin, sucursal_id)
    return [construir_fila_detalle_orden(orden) for orden in candidatos]


def obtener_detalle_ordenes_por_segmento(segmento, embudo):
    """
    Retorna filas de detalle para un segmento específico del embudo.

    Args:
        segmento: Clave del segmento ('acepto_envio', 'rechazo_cotiz', etc.).
        embudo: dict retornado por obtener_embudo_rhitso().

    Returns:
        list[dict]: Filas de detalle del segmento solicitado.
    """
    mapa_segmentos = {
        'acepto_envio': embudo['acepto_envio_qs'],
        'rechazo_envio': embudo['rechazo_envio_qs'],
        'sin_decision_envio': embudo['sin_decision_envio_qs'],
        'acepto_cotiz': embudo['acepto_cotiz_qs'],
        'rechazo_cotiz': embudo['rechazo_cotiz_qs'],
        'no_apto': embudo['no_apto_qs'],
        'en_proceso_cohorte': embudo['en_proceso_cohorte_qs'],
    }
    qs = mapa_segmentos.get(segmento)
    if qs is None:
        return []
    return [construir_fila_detalle_orden(orden) for orden in qs]
