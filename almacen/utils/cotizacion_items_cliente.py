"""
Filtrado y serialización de ítems de cotización al cliente por estado_cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Centraliza qué piezas y servicios entran al PDF de reenvío (pendiente + aprobada)
y cuáles al PDF final descargable (aprobada + compra_generada con precios guardados).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from config.constants import (
    ESTADOS_LINEA_COTIZACION_ACEPTADA,
    ESTADOS_LINEA_COTIZACION_ACTIVA,
)

IVA_FACTOR = 1.16

ESTADOS_SOLICITUD_PDF_FINAL = (
    'totalmente_aprobada',
    'parcialmente_aprobada',
    'en_proceso',
    'completada',
)


def linea_es_cotizable(estado_cliente: str) -> bool:
    """True si la línea entra al cálculo/PDF de cotización activa."""
    return estado_cliente in ESTADOS_LINEA_COTIZACION_ACTIVA


def linea_es_aceptada_final(estado_cliente: str) -> bool:
    """True si la línea entra al PDF final con precios persistidos."""
    return estado_cliente in ESTADOS_LINEA_COTIZACION_ACEPTADA


def serializar_linea_cotizacion(linea) -> Dict[str, Any]:
    """
    Convierte LineaCotizacion al dict usado por el generador PDF (costo interno).

    Args:
        linea: Instancia de LineaCotizacion.

    Returns:
        Dict serializable para PDFCotizacionCliente y Celery.
    """
    costo = float(linea.costo_unitario or 0)
    descripcion = linea.producto.nombre
    if linea.descripcion_pieza:
        descripcion = f"{linea.producto.nombre}: {linea.descripcion_pieza}"
    return {
        'pk': linea.pk,
        'descripcion': descripcion,
        'cantidad': int(linea.cantidad),
        'costo_unitario': costo,
        'es_necesaria': linea.es_necesaria,
        'dias_entrega': linea.tiempo_entrega_estimado,
        'es_servicio': False,
        'estado_cliente': linea.estado_cliente,
    }


def serializar_servicio_cotizacion(servicio) -> Dict[str, Any]:
    """
    Convierte LineaServicioAdicional al dict del generador PDF.

    Args:
        servicio: Instancia de LineaServicioAdicional.

    Returns:
        Dict serializable; costo_unitario trae IVA incluido.
    """
    return {
        'pk': servicio.pk,
        'descripcion': servicio.get_tipo_servicio_display(),
        'cantidad': 1,
        'costo_unitario': float(servicio.costo or 0),
        'es_necesaria': servicio.es_necesaria,
        'dias_entrega': None,
        'es_servicio': True,
        'estado_cliente': servicio.estado_cliente,
    }


def obtener_lineas_cotizables(solicitud):
    """
    QuerySet de piezas cotizables (pendiente o aprobada) con costo > 0.

    Args:
        solicitud: SolicitudCotizacion.

    Returns:
        QuerySet de LineaCotizacion filtrado.
    """
    return solicitud.lineas.filter(
        estado_cliente__in=ESTADOS_LINEA_COTIZACION_ACTIVA,
        costo_unitario__gt=0,
    ).select_related('producto')


def obtener_servicios_cotizables(solicitud):
    """
    QuerySet de servicios adicionales cotizables con costo > 0.

    Args:
        solicitud: SolicitudCotizacion.

    Returns:
        QuerySet de LineaServicioAdicional filtrado.
    """
    return solicitud.servicios_adicionales.filter(
        estado_cliente__in=ESTADOS_LINEA_COTIZACION_ACTIVA,
        costo__gt=0,
    )


def obtener_lineas_aceptadas_final(solicitud):
    """Piezas aceptadas para el PDF final (aprobada o compra_generada)."""
    return solicitud.lineas.filter(
        estado_cliente__in=ESTADOS_LINEA_COTIZACION_ACEPTADA,
    ).select_related('producto')


def obtener_servicios_aceptados_final(solicitud):
    """Servicios aceptados para el PDF final."""
    return solicitud.servicios_adicionales.filter(
        estado_cliente__in=ESTADOS_LINEA_COTIZACION_ACEPTADA,
        costo__gt=0,
    )


def solicitud_tiene_items_cotizables(solicitud) -> bool:
    """True si queda al menos una pieza o servicio para cotizar activamente."""
    return (
        obtener_lineas_cotizables(solicitud).exists()
        or obtener_servicios_cotizables(solicitud).exists()
    )


def solicitud_puede_descargar_pdf_final(solicitud) -> bool:
    """
    True si la solicitud puede generar el PDF final con precios aceptados.

    Requiere precios persistidos y al menos un ítem aceptado.
    """
    if not getattr(solicitud, 'fecha_precios_cliente', None):
        return False
    if solicitud.estado not in ESTADOS_SOLICITUD_PDF_FINAL:
        return False
    tiene_piezas = obtener_lineas_aceptadas_final(solicitud).exists()
    tiene_servicios = obtener_servicios_aceptados_final(solicitud).exists()
    return tiene_piezas or tiene_servicios


def construir_items_cotizacion_activos(solicitud) -> List[Dict[str, Any]]:
    """
    Lista de ítems para PDF/email activo: solo pendiente y aprobada.

    Args:
        solicitud: SolicitudCotizacion.

    Returns:
        Lista de dicts (piezas + servicios cotizables).
    """
    items: List[Dict[str, Any]] = []
    for linea in obtener_lineas_cotizables(solicitud):
        items.append(serializar_linea_cotizacion(linea))
    for servicio in obtener_servicios_cotizables(solicitud):
        items.append(serializar_servicio_cotizacion(servicio))
    return items


def serializar_linea_final(linea) -> Optional[Dict[str, Any]]:
    """
    Serializa pieza aceptada con precios al cliente ya guardados en BD.

    Returns:
        Dict con precios finales, o None si no hay precio persistido.
    """
    precio_unit = linea.precio_unitario_cliente
    subtotal = linea.subtotal_cliente_sin_iva
    if precio_unit is None and subtotal is None:
        return None
    precio_unit_f = float(precio_unit or 0)
    subtotal_f = float(subtotal if subtotal is not None else linea.cantidad * precio_unit_f)
    descripcion = linea.producto.nombre
    if linea.descripcion_pieza:
        descripcion = f"{linea.producto.nombre}: {linea.descripcion_pieza}"
    return {
        'pk': linea.pk,
        'descripcion': descripcion,
        'cantidad': int(linea.cantidad),
        'precio_unitario_cliente': round(precio_unit_f, 2),
        'subtotal_cliente': round(subtotal_f, 2),
        'es_necesaria': linea.es_necesaria,
        'dias_entrega': linea.tiempo_entrega_estimado,
        'es_servicio': False,
        'estado_cliente': linea.estado_cliente,
        '_precio_ya_calculado': True,
    }


def serializar_servicio_final(servicio) -> Dict[str, Any]:
    """Serializa servicio aceptado; costo ya es precio final con IVA."""
    costo_con_iva = float(servicio.costo or 0)
    precio_sin_iva = costo_con_iva / IVA_FACTOR if costo_con_iva > 0 else 0.0
    return {
        'pk': servicio.pk,
        'descripcion': servicio.get_tipo_servicio_display(),
        'cantidad': 1,
        'precio_unitario_cliente': round(precio_sin_iva, 2),
        'subtotal_cliente': round(precio_sin_iva, 2),
        'costo_unitario': costo_con_iva,
        'es_necesaria': servicio.es_necesaria,
        'dias_entrega': None,
        'es_servicio': True,
        'estado_cliente': servicio.estado_cliente,
        '_precio_ya_calculado': True,
    }


def construir_items_cotizacion_final(solicitud) -> List[Dict[str, Any]]:
    """
    Ítems para PDF final: solo aceptados con precios al cliente persistidos.

    Args:
        solicitud: SolicitudCotizacion.

    Returns:
        Lista de dicts listos para calcular_totales_items_finales / PDF modo_final.
    """
    items: List[Dict[str, Any]] = []
    for linea in obtener_lineas_aceptadas_final(solicitud):
        item = serializar_linea_final(linea)
        if item:
            items.append(item)
    for servicio in obtener_servicios_aceptados_final(solicitud):
        items.append(serializar_servicio_final(servicio))
    return items


def construir_grupos_cotizacion(
    items_piezas: List[Dict[str, Any]],
    items_servicios: List[Dict[str, Any]],
    modo_agrupacion: str,
) -> List[Dict[str, Any]]:
    """
    Agrupa ítems según el modo elegido en el modal (todo_junto, separado, etc.).

    Args:
        items_piezas      : Piezas ya filtradas y serializadas.
        items_servicios   : Servicios ya filtrados y serializados.
        modo_agrupacion   : Clave del modo de agrupación del modal.

    Returns:
        Lista de dicts {'titulo': str, 'items': list}.
    """
    items_piezas_nec = [d for d in items_piezas if d.get('es_necesaria')]
    items_piezas_opc = [d for d in items_piezas if not d.get('es_necesaria')]
    items_servicios_nec = [d for d in items_servicios if d.get('es_necesaria')]
    items_servicios_opc = [d for d in items_servicios if not d.get('es_necesaria')]

    if modo_agrupacion == 'todo_junto':
        grupos = [{'titulo': '', 'items': items_piezas + items_servicios}]
    elif modo_agrupacion == 'piezas_vs_servicios':
        grupos = []
        if items_piezas:
            grupos.append({'titulo': 'Cotización de Piezas', 'items': items_piezas})
        if items_servicios:
            grupos.append({
                'titulo': 'Cotización de Servicios Adicionales',
                'items': items_servicios,
            })
        if not grupos:
            grupos = [{'titulo': '', 'items': items_piezas + items_servicios}]
    elif modo_agrupacion == 'necesarias_vs_opcionales':
        grupos = []
        items_necesarios = items_piezas_nec + items_servicios_nec
        items_opcionales = items_piezas_opc + items_servicios_opc
        if items_necesarios:
            grupos.append({
                'titulo': 'Cotización — Piezas y Servicios Necesarios',
                'items': items_necesarios,
            })
        if items_opcionales:
            grupos.append({
                'titulo': 'Cotización — Piezas y Servicios Opcionales',
                'items': items_opcionales,
            })
        if not grupos:
            grupos = [{'titulo': '', 'items': items_piezas + items_servicios}]
    else:
        grupos = [{'titulo': '', 'items': items_piezas + items_servicios}]

    return [g for g in grupos if g.get('items')]
