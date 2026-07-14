"""
Creación de SeguimientoPieza y avance a «Esperando Llegada de Piezas» desde Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando se genera la compra de piezas en Almacén, ya se confirmó el pedido al
proveedor. En ese momento Servicio Técnico debe:
1. Ver los pedidos en «Seguimiento de Piezas» (modelo SeguimientoPieza).
2. Pasar la orden a «Esperando Llegada de Piezas» (esperando_piezas).

Se reutiliza el mismo criterio que al aceptar cotización en ST: agrupar por
proveedor y enlazar las PiezaCotizada ya sincronizadas desde LineaCotizacion.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional

if TYPE_CHECKING:
    from almacen.models import LineaCotizacion, SolicitudCotizacion

logger = logging.getLogger('almacen')

# Estados desde los que sí avanzamos a esperando_piezas (no pisar reparacion, etc.)
ESTADOS_ST_ANTES_DE_ESPERAR_PIEZAS = (
    'cotizacion',
    'cliente_acepta_cotizacion',
)

ESTADO_ST_ESPERANDO_PIEZAS = 'esperando_piezas'
DIAS_ENTREGA_DEFAULT = 7


def sincronizar_seguimiento_piezas_al_generar_compras(
    solicitud: 'SolicitudCotizacion',
    lineas: Optional[Iterable['LineaCotizacion']] = None,
) -> Dict[str, Any]:
    """
    Crea SeguimientoPieza por proveedor y pasa la orden ST a esperando_piezas.

    Args:
        solicitud: SolicitudCotizacion con orden vinculada (idealmente).
        lineas: Líneas recién convertidas en compra. Si es None, usa todas las
            líneas de la solicitud en estado compra_generada elegibles.

    Returns:
        dict con:
            seguimientos_creados (int),
            estado_actualizado (bool),
            motivo_omitido (str|None) — por qué no se hizo nada si aplica.
    """
    resultado: Dict[str, Any] = {
        'seguimientos_creados': 0,
        'estado_actualizado': False,
        'motivo_omitido': None,
    }

    orden = getattr(solicitud, 'orden_servicio', None)
    if not orden:
        resultado['motivo_omitido'] = 'sin_orden'
        return resultado

    # FL- / Venta Mostrador: las piezas van a PiezaVentaMostrador, no a este tracking
    if getattr(orden, 'tipo_servicio', None) == 'venta_mostrador':
        resultado['motivo_omitido'] = 'venta_mostrador'
        return resultado

    # Cotización ST requerida para SeguimientoPieza
    try:
        cotizacion = orden.cotizacion
    except Exception:
        resultado['motivo_omitido'] = 'sin_cotizacion_st'
        logger.warning(
            f"[SYNC_SEGUIMIENTO] Orden {orden.numero_orden_interno} sin Cotizacion ST "
            f"(solicitud {solicitud.numero_solicitud})."
        )
        return resultado

    lineas_elegibles = _obtener_lineas_elegibles(solicitud, lineas)
    if not lineas_elegibles:
        resultado['motivo_omitido'] = 'sin_piezas_reparacion'
        return resultado

    # Agrupar PiezaCotizada por nombre de proveedor (mismo patrón que ST)
    piezas_por_proveedor: Dict[str, List] = defaultdict(list)
    dias_por_proveedor: Dict[str, int] = defaultdict(lambda: DIAS_ENTREGA_DEFAULT)

    for linea in lineas_elegibles:
        pieza = linea.pieza_cotizada_origen
        # Anti-duplicado: si la pieza ya está en algún seguimiento, no la repetimos
        if pieza.seguimientos.exists():
            continue

        proveedor_nombre = _nombre_proveedor(linea, pieza)
        if not proveedor_nombre:
            logger.warning(
                f"[SYNC_SEGUIMIENTO] Línea {linea.pk} sin proveedor; se omite del seguimiento."
            )
            continue

        piezas_por_proveedor[proveedor_nombre].append(pieza)
        dias_eta = _dias_entrega_linea(linea)
        if dias_eta > dias_por_proveedor[proveedor_nombre]:
            dias_por_proveedor[proveedor_nombre] = dias_eta

    if not piezas_por_proveedor:
        # Piezas elegibles ya tenían seguimiento: igual avanzar estado si aplica
        if cotizacion.seguimientos_piezas.exists():
            resultado['estado_actualizado'] = _pasar_orden_a_esperando_piezas(
                orden=orden,
                solicitud=solicitud,
            )
        else:
            resultado['motivo_omitido'] = 'piezas_sin_proveedor_o_ya_seguidas'
        return resultado

    from servicio_tecnico.models import SeguimientoPieza

    hoy = date.today()
    seguimientos_creados = 0

    for proveedor_nombre, piezas_grupo in piezas_por_proveedor.items():
        descripcion = '\n'.join([
            f"• {pieza.componente.nombre} × {pieza.cantidad}"
            + (f" (${pieza.costo_total})" if getattr(pieza, 'costo_total', None) else '')
            for pieza in piezas_grupo
        ])
        dias_eta = dias_por_proveedor[proveedor_nombre]

        seguimiento = SeguimientoPieza.objects.create(
            cotizacion=cotizacion,
            proveedor=proveedor_nombre,
            descripcion_piezas=descripcion,
            fecha_pedido=hoy,
            fecha_entrega_estimada=hoy + timedelta(days=dias_eta),
            # Al generar la compra en Almacén el pedido ya está en camino
            estado='transito',
            notas_seguimiento=(
                f'Seguimiento creado automáticamente al generar compras desde Almacén '
                f'(solicitud {solicitud.numero_solicitud}). Estado inicial: En Tránsito.'
            ),
        )
        seguimiento.piezas.set(piezas_grupo)
        seguimientos_creados += 1

    resultado['seguimientos_creados'] = seguimientos_creados

    # Con piezas pedidas, la orden debe quedar en «Esperando Llegada de Piezas»
    resultado['estado_actualizado'] = _pasar_orden_a_esperando_piezas(
        orden=orden,
        solicitud=solicitud,
    )

    logger.info(
        f"[SYNC_SEGUIMIENTO] Solicitud {solicitud.numero_solicitud}: "
        f"{seguimientos_creados} seguimiento(s); "
        f"estado_actualizado={resultado['estado_actualizado']}"
    )
    return resultado


def _obtener_lineas_elegibles(
    solicitud: 'SolicitudCotizacion',
    lineas: Optional[Iterable['LineaCotizacion']],
) -> List['LineaCotizacion']:
    """
    Filtra líneas de reparación OOW con PiezaCotizada vinculada.

    Excluye reacondicionado (van a Venta Mostrador) y líneas sin sync ST.
    """
    if lineas is None:
        qs = solicitud.lineas.filter(
            estado_cliente='compra_generada',
            es_linea_reacondicionado=False,
            pieza_cotizada_origen__isnull=False,
        ).select_related(
            'pieza_cotizada_origen',
            'pieza_cotizada_origen__componente',
            'proveedor',
            'producto',
        )
        return list(qs)

    elegibles: List['LineaCotizacion'] = []
    for linea in lineas:
        if getattr(linea, 'es_linea_reacondicionado', False):
            continue
        if not getattr(linea, 'pieza_cotizada_origen_id', None):
            continue
        elegibles.append(linea)
    return elegibles


def _nombre_proveedor(linea: 'LineaCotizacion', pieza) -> str:
    """Nombre de proveedor para SeguimientoPieza (CharField en ST)."""
    if linea.proveedor_id and linea.proveedor:
        nombre = (linea.proveedor.nombre or '').strip()
        if nombre:
            return nombre
    return (getattr(pieza, 'proveedor', None) or '').strip()


def _dias_entrega_linea(linea: 'LineaCotizacion') -> int:
    """Días estimados de entrega; default 7 si la línea no trae valor."""
    dias = getattr(linea, 'tiempo_entrega_estimado', None)
    try:
        dias_int = int(dias) if dias is not None else DIAS_ENTREGA_DEFAULT
    except (TypeError, ValueError):
        dias_int = DIAS_ENTREGA_DEFAULT
    return max(dias_int, 1)


def _pasar_orden_a_esperando_piezas(orden, solicitud: 'SolicitudCotizacion') -> bool:
    """
    Cambia OrdenServicio a esperando_piezas si aún está en fase de cotización/aceptación.

    Returns:
        bool: True si se cambió el estado.
    """
    if orden.estado == ESTADO_ST_ESPERANDO_PIEZAS:
        return False

    if orden.estado not in ESTADOS_ST_ANTES_DE_ESPERAR_PIEZAS:
        logger.info(
            f"[SYNC_SEGUIMIENTO] Orden {orden.numero_orden_interno} en estado "
            f"'{orden.estado}'; no se cambia a esperando_piezas "
            f"(solicitud {solicitud.numero_solicitud})."
        )
        return False

    from config.constants import ESTADO_ORDEN_CHOICES

    estado_anterior = orden.estado
    orden.estado = ESTADO_ST_ESPERANDO_PIEZAS
    orden.save(update_fields=['estado'])

    ultimo = (
        orden.historial.filter(
            tipo_evento='cambio_estado',
            estado_nuevo=ESTADO_ST_ESPERANDO_PIEZAS,
        )
        .order_by('-fecha_evento')
        .first()
    )
    if ultimo:
        etiqueta_anterior = dict(ESTADO_ORDEN_CHOICES).get(estado_anterior, estado_anterior)
        ultimo.comentario = (
            f'Cambio de estado al generar compras desde Almacén: '
            f'{etiqueta_anterior} → Esperando Llegada de Piezas '
            f'(solicitud {solicitud.numero_solicitud})'
        )
        ultimo.es_sistema = True
        ultimo.save(update_fields=['comentario', 'es_sistema'])

    logger.info(
        f"[SYNC_SEGUIMIENTO] Orden {orden.numero_orden_interno}: "
        f"{estado_anterior} → esperando_piezas "
        f"(solicitud {solicitud.numero_solicitud})"
    )
    return True
