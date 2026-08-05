"""
Creación/actualización de SeguimientoPieza y avance de estado de orden desde Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Ciclo completo piezas Almacén ↔ Servicio Técnico:

1. Generar compras → crea SeguimientoPieza en «En Tránsito» y orden en
   «Esperando Llegada de Piezas».
2. Recibir compra → marca SeguimientoPieza como «Recibido» con la fecha de
   llegada, y si ya no quedan pendientes pasa la orden a «Piezas Recibidas».

Soporta dos familias de piezas (Ago 2026):
- Reparación OOW → PiezaCotizada (vía linea.pieza_cotizada_origen).
- FL / reacondicionado → PiezaVentaMostrador (vía linea.pieza_venta_mostrador).

El ancla del seguimiento es siempre la OrdenServicio; Cotizacion es opcional.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple

if TYPE_CHECKING:
    from almacen.models import CompraProducto, LineaCotizacion, SolicitudCotizacion

logger = logging.getLogger('almacen')

# Estados OOW desde los que sí avanzamos a esperando_piezas
ESTADOS_ST_ANTES_DE_ESPERAR_PIEZAS_OOW = (
    'cotizacion',
    'cliente_acepta_cotizacion',
)

# FL nace en «almacen»; desde ahí sí avanzamos al pedir piezas
ESTADOS_ST_ANTES_DE_ESPERAR_PIEZAS_FL = (
    'almacen',
)

ESTADO_ST_ESPERANDO_PIEZAS = 'esperando_piezas'
ESTADO_ST_PIEZAS_RECIBIDAS = 'piezas_recibidas'
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

    # Cotizacion ST solo existe en OOW; en FL queda None (válido)
    cotizacion = _obtener_cotizacion_st(orden)

    lineas_oow, lineas_vm = _obtener_lineas_elegibles_por_familia(solicitud, lineas)
    if not lineas_oow and not lineas_vm:
        resultado['motivo_omitido'] = 'sin_piezas_trackeables'
        return resultado

    from servicio_tecnico.models import SeguimientoPieza

    hoy = date.today()
    seguimientos_creados = 0

    # --- Rama OOW (PiezaCotizada) ---
    grupos_oow = _agrupar_piezas_oow_por_proveedor(lineas_oow)
    for proveedor_nombre, (piezas_grupo, dias_eta) in grupos_oow.items():
        descripcion = '\n'.join([
            f"• {pieza.componente.nombre} × {pieza.cantidad}"
            + (f" (${pieza.costo_total})" if getattr(pieza, 'costo_total', None) else '')
            for pieza in piezas_grupo
        ])
        seguimiento = SeguimientoPieza.objects.create(
            orden=orden,
            cotizacion=cotizacion,
            proveedor=proveedor_nombre,
            descripcion_piezas=descripcion,
            fecha_pedido=hoy,
            fecha_entrega_estimada=hoy + timedelta(days=dias_eta),
            estado='transito',
            notas_seguimiento=(
                f'Seguimiento creado automáticamente al generar compras desde Almacén '
                f'(solicitud {solicitud.numero_solicitud}). Estado inicial: En Tránsito.'
            ),
        )
        seguimiento.piezas.set(piezas_grupo)
        seguimientos_creados += 1

    # --- Rama VM (PiezaVentaMostrador: FL o reacondicionado) ---
    grupos_vm = _agrupar_piezas_vm_por_proveedor(lineas_vm)
    for proveedor_nombre, (piezas_grupo, dias_eta) in grupos_vm.items():
        descripcion = '\n'.join([
            f"• {pieza.descripcion_pieza} × {pieza.cantidad}"
            for pieza in piezas_grupo
        ])
        seguimiento = SeguimientoPieza.objects.create(
            orden=orden,
            cotizacion=cotizacion,  # None en FL puro; presente en OOW+reac
            proveedor=proveedor_nombre,
            descripcion_piezas=descripcion,
            fecha_pedido=hoy,
            fecha_entrega_estimada=hoy + timedelta(days=dias_eta),
            estado='transito',
            notas_seguimiento=(
                f'Seguimiento VM creado automáticamente al generar compras desde Almacén '
                f'(solicitud {solicitud.numero_solicitud}). Estado inicial: En Tránsito.'
            ),
        )
        seguimiento.piezas_venta_mostrador.set(piezas_grupo)
        seguimientos_creados += 1

    resultado['seguimientos_creados'] = seguimientos_creados

    # Si no creamos nada nuevo pero ya hay seguimientos, igual intentar avanzar estado
    if seguimientos_creados == 0:
        if orden.seguimientos_piezas.exists():
            resultado['estado_actualizado'] = _pasar_orden_a_esperando_piezas(
                orden=orden,
                solicitud=solicitud,
            )
        else:
            resultado['motivo_omitido'] = 'piezas_sin_proveedor_o_ya_seguidas'
        return resultado

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


def _obtener_cotizacion_st(orden):
    """Devuelve Cotizacion ST si existe; None en FL."""
    try:
        return orden.cotizacion
    except Exception:
        return None


def _obtener_lineas_elegibles_por_familia(
    solicitud: 'SolicitudCotizacion',
    lineas: Optional[Iterable['LineaCotizacion']],
) -> Tuple[List['LineaCotizacion'], List['LineaCotizacion']]:
    """
    Separa líneas trackeables en OOW (PiezaCotizada) y VM (PiezaVentaMostrador).

    Returns:
        (lineas_oow, lineas_vm)
    """
    if lineas is None:
        qs = solicitud.lineas.filter(
            estado_cliente='compra_generada',
        ).select_related(
            'pieza_cotizada_origen',
            'pieza_cotizada_origen__componente',
            'pieza_venta_mostrador',
            'proveedor',
            'producto',
        )
        candidatas = list(qs)
    else:
        candidatas = list(lineas)

    lineas_oow: List['LineaCotizacion'] = []
    lineas_vm: List['LineaCotizacion'] = []

    for linea in candidatas:
        # OOW reparación: tiene PiezaCotizada y no es reacondicionado
        if (
            not getattr(linea, 'es_linea_reacondicionado', False)
            and getattr(linea, 'pieza_cotizada_origen_id', None)
        ):
            lineas_oow.append(linea)
            continue

        # FL / reac: tiene PiezaVentaMostrador enlazada
        pieza_vm = _pieza_vm_de_linea(linea)
        if pieza_vm is not None:
            lineas_vm.append(linea)

    return lineas_oow, lineas_vm


def _pieza_vm_de_linea(linea: 'LineaCotizacion'):
    """PiezaVentaMostrador OneToOne desde la línea, o None."""
    try:
        return linea.pieza_venta_mostrador
    except Exception:
        return None


def _agrupar_piezas_oow_por_proveedor(
    lineas: List['LineaCotizacion'],
) -> Dict[str, Tuple[List, int]]:
    """Agrupa PiezaCotizada por proveedor; omite ya seguidas o sin proveedor."""
    piezas_por_proveedor: Dict[str, List] = defaultdict(list)
    dias_por_proveedor: Dict[str, int] = defaultdict(lambda: DIAS_ENTREGA_DEFAULT)

    for linea in lineas:
        pieza = linea.pieza_cotizada_origen
        if pieza is None:
            continue
        # Anti-duplicado
        if pieza.seguimientos.exists():
            continue

        proveedor_nombre = _nombre_proveedor(linea, pieza)
        if not proveedor_nombre:
            logger.warning(
                f"[SYNC_SEGUIMIENTO] Línea OOW {linea.pk} sin proveedor; se omite."
            )
            continue

        piezas_por_proveedor[proveedor_nombre].append(pieza)
        dias_eta = _dias_entrega_linea(linea)
        if dias_eta > dias_por_proveedor[proveedor_nombre]:
            dias_por_proveedor[proveedor_nombre] = dias_eta

    return {
        prov: (piezas, dias_por_proveedor[prov])
        for prov, piezas in piezas_por_proveedor.items()
    }


def _agrupar_piezas_vm_por_proveedor(
    lineas: List['LineaCotizacion'],
) -> Dict[str, Tuple[List, int]]:
    """Agrupa PiezaVentaMostrador por proveedor; omite ya seguidas o sin proveedor."""
    piezas_por_proveedor: Dict[str, List] = defaultdict(list)
    dias_por_proveedor: Dict[str, int] = defaultdict(lambda: DIAS_ENTREGA_DEFAULT)

    for linea in lineas:
        pieza = _pieza_vm_de_linea(linea)
        if pieza is None:
            continue
        # Anti-duplicado
        if pieza.seguimientos.exists():
            continue

        proveedor_nombre = _nombre_proveedor(linea, pieza)
        if not proveedor_nombre:
            logger.warning(
                f"[SYNC_SEGUIMIENTO] Línea VM {linea.pk} sin proveedor; se omite."
            )
            continue

        piezas_por_proveedor[proveedor_nombre].append(pieza)
        dias_eta = _dias_entrega_linea(linea)
        if dias_eta > dias_por_proveedor[proveedor_nombre]:
            dias_por_proveedor[proveedor_nombre] = dias_eta

    return {
        prov: (piezas, dias_por_proveedor[prov])
        for prov, piezas in piezas_por_proveedor.items()
    }


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


def _estados_permitidos_antes_de_esperar(orden) -> tuple:
    """Estados desde los que se puede pasar a esperando_piezas según tipo de orden."""
    if getattr(orden, 'tipo_servicio', None) == 'venta_mostrador':
        return ESTADOS_ST_ANTES_DE_ESPERAR_PIEZAS_FL
    return ESTADOS_ST_ANTES_DE_ESPERAR_PIEZAS_OOW


def _pasar_orden_a_esperando_piezas(orden, solicitud: 'SolicitudCotizacion') -> bool:
    """
    Cambia OrdenServicio a esperando_piezas si el estado actual lo permite.

    OOW: desde cotizacion / cliente_acepta_cotizacion.
    FL: desde almacen (estado natal al crear orden FL).

    Returns:
        bool: True si se cambió el estado.
    """
    if orden.estado == ESTADO_ST_ESPERANDO_PIEZAS:
        return False

    permitidos = _estados_permitidos_antes_de_esperar(orden)
    if orden.estado not in permitidos:
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


def sincronizar_seguimiento_piezas_al_recibir_compra(
    compra: 'CompraProducto',
    notificar_tecnico: bool = True,
) -> Dict[str, Any]:
    """
    Al recibir una compra en Almacén, actualiza SeguimientoPieza y la orden ST.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Un SeguimientoPieza puede agrupar varias piezas del mismo proveedor
    (PiezaCotizada y/o PiezaVentaMostrador). Solo se marca como «Recibido»
    cuando TODAS esas piezas ya tienen su CompraProducto en estado «recibida».
    Si después todos los seguimientos de la ORDEN están recibidos, la orden
    pasa a «Piezas Recibidas».

    Args:
        compra: CompraProducto recién marcada como recibida (con fecha_recepcion).
        notificar_tecnico: Si True, envía el email al técnico por cada seguimiento cerrado.

    Returns:
        dict: seguimientos_actualizados, estado_orden_actualizado,
        emails_enviados, emails_fallidos, motivo_omitido.
    """
    from config.constants import ESTADOS_PIEZA_PENDIENTES

    resultado: Dict[str, Any] = {
        'seguimientos_actualizados': 0,
        'estado_orden_actualizado': False,
        'emails_enviados': 0,
        'emails_fallidos': 0,
        'motivo_omitido': None,
    }

    if getattr(compra, 'estado', None) != 'recibida':
        resultado['motivo_omitido'] = 'compra_no_recibida'
        return resultado

    # Cadena: Compra → LineaCotizacion → PiezaCotizada | PiezaVentaMostrador
    linea = None
    try:
        linea = compra.linea_cotizacion_origen
    except Exception:
        linea = None

    if linea is None:
        resultado['motivo_omitido'] = 'sin_linea_cotizacion'
        return resultado

    pieza_oow = getattr(linea, 'pieza_cotizada_origen', None)
    pieza_vm = _pieza_vm_de_linea(linea)

    if pieza_oow is None and pieza_vm is None:
        resultado['motivo_omitido'] = 'sin_pieza_st'
        return resultado

    orden = None
    solicitud = getattr(linea, 'solicitud', None)
    if solicitud is not None:
        orden = getattr(solicitud, 'orden_servicio', None)
    if orden is None:
        orden = getattr(compra, 'orden_servicio', None)

    if orden is None:
        resultado['motivo_omitido'] = 'sin_orden'
        return resultado

    # Buscar seguimientos pendientes que incluyen esta pieza (OOW o VM)
    seguimientos_pendientes = []
    if pieza_oow is not None:
        seguimientos_pendientes.extend(
            list(
                pieza_oow.seguimientos.filter(estado__in=ESTADOS_PIEZA_PENDIENTES)
                .prefetch_related(
                    'piezas',
                    'piezas__linea_cotizacion_almacen',
                    'piezas__linea_cotizacion_almacen__compra_generada',
                    'piezas_venta_mostrador',
                    'piezas_venta_mostrador__linea_cotizacion',
                    'piezas_venta_mostrador__linea_cotizacion__compra_generada',
                )
            )
        )
    if pieza_vm is not None:
        seguimientos_pendientes.extend(
            list(
                pieza_vm.seguimientos.filter(estado__in=ESTADOS_PIEZA_PENDIENTES)
                .prefetch_related(
                    'piezas',
                    'piezas__linea_cotizacion_almacen',
                    'piezas__linea_cotizacion_almacen__compra_generada',
                    'piezas_venta_mostrador',
                    'piezas_venta_mostrador__linea_cotizacion',
                    'piezas_venta_mostrador__linea_cotizacion__compra_generada',
                )
            )
        )

    # Deduplicar por pk (por si una pieza estuviera en ambos caminos)
    vistos = set()
    unicos = []
    for seg in seguimientos_pendientes:
        if seg.pk in vistos:
            continue
        vistos.add(seg.pk)
        unicos.append(seg)
    seguimientos_pendientes = unicos

    if not seguimientos_pendientes:
        resultado['motivo_omitido'] = 'sin_seguimientos_pendientes'
        resultado['estado_orden_actualizado'] = _pasar_orden_a_piezas_recibidas_si_aplica(
            orden=orden,
            solicitud=solicitud,
        )
        return resultado

    fecha_recepcion = compra.fecha_recepcion or date.today()
    actualizados = 0
    emails_enviados = 0
    emails_fallidos = 0

    for seguimiento in seguimientos_pendientes:
        # Solo cerrar el seguimiento si TODAS sus piezas ya llegaron a Almacén
        if not _todas_piezas_del_seguimiento_recibidas_en_almacen(seguimiento):
            continue

        fecha_real = _fecha_recepcion_mas_reciente(seguimiento) or fecha_recepcion
        seguimiento.estado = 'recibido'
        seguimiento.fecha_entrega_real = fecha_real
        nota_extra = (
            f'\nRecepción registrada automáticamente desde Almacén '
            f'(compra #{compra.pk}, fecha {fecha_real}).'
        )
        seguimiento.notas_seguimiento = (
            (seguimiento.notas_seguimiento or '').rstrip() + nota_extra
        )
        seguimiento.save(update_fields=[
            'estado',
            'fecha_entrega_real',
            'notas_seguimiento',
            'fecha_actualizacion',
        ])
        actualizados += 1

        if notificar_tecnico:
            email_ok = _notificar_tecnico_pieza_recibida(
                orden=orden,
                seguimiento=seguimiento,
            )
            if email_ok:
                emails_enviados += 1
            else:
                emails_fallidos += 1

    resultado['seguimientos_actualizados'] = actualizados
    resultado['emails_enviados'] = emails_enviados
    resultado['emails_fallidos'] = emails_fallidos
    resultado['estado_orden_actualizado'] = _pasar_orden_a_piezas_recibidas_si_aplica(
        orden=orden,
        solicitud=solicitud,
    )

    if actualizados == 0 and not resultado['estado_orden_actualizado']:
        resultado['motivo_omitido'] = 'grupo_incompleto'

    logger.info(
        f"[SYNC_SEGUIMIENTO_RECIBIR] Compra #{compra.pk}: "
        f"{actualizados} seguimiento(s) → recibido; "
        f"emails_ok={emails_enviados} fallidos={emails_fallidos}; "
        f"orden_actualizada={resultado['estado_orden_actualizado']}"
    )
    return resultado


def _notificar_tecnico_pieza_recibida(orden, seguimiento) -> bool:
    """
    Reutiliza el email de ST al marcar pieza recibida y deja rastro en historial.

    Args:
        orden: OrdenServicio.
        seguimiento: SeguimientoPieza ya en estado «recibido».

    Returns:
        bool: True si el email se envió correctamente.
    """
    from servicio_tecnico.services.historial import registrar_historial
    from servicio_tecnico.services.notificaciones_piezas import (
        enviar_notificacion_pieza_recibida as _enviar_notificacion_pieza_recibida,
    )

    try:
        resultado_email = _enviar_notificacion_pieza_recibida(orden, seguimiento)
    except Exception as exc:
        logger.error(
            f"[SYNC_SEGUIMIENTO_RECIBIR] Error al notificar técnico "
            f"(orden {orden.numero_orden_interno}, seguimiento {seguimiento.pk}): {exc}",
            exc_info=True,
        )
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=None,
            comentario=(
                f'📬 Pieza recibida desde Almacén - {seguimiento.proveedor}\n'
                f'❌ Error inesperado al enviar email: {exc}'
            ),
            es_sistema=True,
        )
        return False

    if resultado_email.get('success'):
        destinatarios_str = ', '.join(resultado_email.get('destinatarios') or [])
        mensaje = (
            f'📬 Pieza recibida desde Almacén - {seguimiento.proveedor}\n'
            f'✉️ Email enviado a: {destinatarios_str}'
        )
        cc = resultado_email.get('destinatarios_copia') or []
        if cc:
            mensaje += f"\n📧 Con copia a: {', '.join(cc)}"
        registrar_historial(
            orden=orden,
            tipo_evento='cotizacion',
            usuario=None,
            comentario=mensaje,
            es_sistema=True,
        )
        return True

    registrar_historial(
        orden=orden,
        tipo_evento='cotizacion',
        usuario=None,
        comentario=(
            f'📬 Pieza recibida desde Almacén - {seguimiento.proveedor}\n'
            f'❌ Error al enviar email: {resultado_email.get("message", "desconocido")}\n'
            f'⚠️ El técnico NO fue notificado automáticamente'
        ),
        es_sistema=True,
    )
    return False


def _pieza_oow_tiene_compra_recibida(pieza) -> bool:
    """True si la PiezaCotizada tiene LineaCotizacion con CompraProducto recibida."""
    try:
        linea = pieza.linea_cotizacion_almacen
    except Exception:
        return False
    if linea is None:
        return False
    compra = getattr(linea, 'compra_generada', None)
    if compra is None:
        return False
    return compra.estado == 'recibida'


def _pieza_vm_tiene_compra_recibida(pieza) -> bool:
    """True si la PiezaVentaMostrador tiene LineaCotizacion con CompraProducto recibida."""
    linea = getattr(pieza, 'linea_cotizacion', None)
    if linea is None:
        # Pieza VM manual (sin compra Almacén): no cierra por sync automático
        return False
    compra = getattr(linea, 'compra_generada', None)
    if compra is None:
        return False
    return compra.estado == 'recibida'


def _todas_piezas_del_seguimiento_recibidas_en_almacen(seguimiento) -> bool:
    """
    True si todas las piezas del seguimiento (OOW y/o VM) ya tienen compra recibida.

    Sin piezas M2M no se cierra automáticamente (evita falsos positivos).
    """
    piezas_oow = list(seguimiento.piezas.all())
    piezas_vm = list(seguimiento.piezas_venta_mostrador.all())
    if not piezas_oow and not piezas_vm:
        return False

    oow_ok = all(_pieza_oow_tiene_compra_recibida(p) for p in piezas_oow) if piezas_oow else True
    vm_ok = all(_pieza_vm_tiene_compra_recibida(p) for p in piezas_vm) if piezas_vm else True
    return oow_ok and vm_ok


def _fecha_recepcion_mas_reciente(seguimiento) -> Optional[date]:
    """Fecha de recepción más reciente entre las compras OOW y VM del seguimiento."""
    fechas: List[date] = []

    for pieza in seguimiento.piezas.all():
        try:
            linea = pieza.linea_cotizacion_almacen
        except Exception:
            continue
        if linea is None:
            continue
        compra = getattr(linea, 'compra_generada', None)
        if compra is None or compra.estado != 'recibida':
            continue
        if compra.fecha_recepcion:
            fechas.append(compra.fecha_recepcion)

    for pieza in seguimiento.piezas_venta_mostrador.all():
        linea = getattr(pieza, 'linea_cotizacion', None)
        if linea is None:
            continue
        compra = getattr(linea, 'compra_generada', None)
        if compra is None or compra.estado != 'recibida':
            continue
        if compra.fecha_recepcion:
            fechas.append(compra.fecha_recepcion)

    return max(fechas) if fechas else None


def _pasar_orden_a_piezas_recibidas_si_aplica(orden, solicitud=None) -> bool:
    """
    Si la orden está en esperando_piezas y todos los seguimientos ya llegaron,
    pasa a piezas_recibidas.

    Usa ``orden.seguimientos_piezas`` (no cotizacion) para cubrir FL y OOW mixto.

    Returns:
        bool: True si se cambió el estado.
    """
    from config.constants import ESTADOS_PIEZA_RECIBIDOS, ESTADO_ORDEN_CHOICES

    if orden.estado == ESTADO_ST_PIEZAS_RECIBIDAS:
        return False

    if orden.estado != ESTADO_ST_ESPERANDO_PIEZAS:
        logger.info(
            f"[SYNC_SEGUIMIENTO_RECIBIR] Orden {orden.numero_orden_interno} en estado "
            f"'{orden.estado}'; no se cambia a piezas_recibidas."
        )
        return False

    seguimientos = list(orden.seguimientos_piezas.all())
    if not seguimientos:
        return False

    if not all(s.estado in ESTADOS_PIEZA_RECIBIDOS for s in seguimientos):
        return False

    estado_anterior = orden.estado
    orden.estado = ESTADO_ST_PIEZAS_RECIBIDAS
    orden.save(update_fields=['estado'])

    ultimo = (
        orden.historial.filter(
            tipo_evento='cambio_estado',
            estado_nuevo=ESTADO_ST_PIEZAS_RECIBIDAS,
        )
        .order_by('-fecha_evento')
        .first()
    )
    if ultimo:
        etiqueta_anterior = dict(ESTADO_ORDEN_CHOICES).get(estado_anterior, estado_anterior)
        ref_solicitud = ''
        if solicitud is not None:
            ref_solicitud = f' (solicitud {solicitud.numero_solicitud})'
        ultimo.comentario = (
            f'Cambio de estado al recibir todas las piezas desde Almacén: '
            f'{etiqueta_anterior} → Piezas Recibidas{ref_solicitud}'
        )
        ultimo.es_sistema = True
        ultimo.save(update_fields=['comentario', 'es_sistema'])

    logger.info(
        f"[SYNC_SEGUIMIENTO_RECIBIR] Orden {orden.numero_orden_interno}: "
        f"{estado_anterior} → piezas_recibidas"
    )
    return True
