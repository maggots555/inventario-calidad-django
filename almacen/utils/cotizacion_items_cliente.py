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
    formatear_descripcion_servicio_con_inclusiones,
)
from config.paises_config import get_pais_actual

IVA_FACTOR = 1.16

ESTADOS_SOLICITUD_PDF_FINAL = (
    'totalmente_aprobada',
    'parcialmente_aprobada',
    'en_proceso',
    'completada',
)


def _pais_codigo_activo() -> str:
    """
    Código ISO del país del request/worker (ej. 'MX').

    Returns:
        str: Código de país; vacío si no hay configuración.
    """
    try:
        return get_pais_actual().get('codigo', '') or ''
    except Exception:
        return ''


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

    EXPLICACIÓN PARA PRINCIPIANTES:
    En México, Solución Plata (paquete_plata) lleva bullets de inclusiones en
    la descripción para que el cliente las vea en el PDF junto al precio.

    Args:
        servicio: Instancia de LineaServicioAdicional.

    Returns:
        Dict serializable; costo_unitario trae IVA incluido.
    """
    tipo = servicio.tipo_servicio
    nombre = servicio.get_tipo_servicio_display()
    # Enriquecer descripción solo si el catálogo MX tiene inclusiones para este tipo
    descripcion = formatear_descripcion_servicio_con_inclusiones(
        nombre_display=nombre,
        tipo_servicio=tipo,
        pais_codigo=_pais_codigo_activo(),
    )
    return {
        'pk': servicio.pk,
        'descripcion': descripcion,
        'cantidad': 1,
        'costo_unitario': float(servicio.costo or 0),
        'es_necesaria': servicio.es_necesaria,
        'dias_entrega': None,
        'es_servicio': True,
        'tipo_servicio': tipo,
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


def extraer_datos_equipo_desde_solicitud(solicitud) -> Dict[str, Any]:
    """
    Reconstruye el dict de especificaciones del equipo desde el snapshot de la solicitud.

    Args:
        solicitud: SolicitudCotizacion con campos reac_* guardados al enviar la propuesta.

    Returns:
        dict compatible con PDFCotizacionReacondicionado.
    """
    return {
        'marca': getattr(solicitud, 'reac_marca', '') or '',
        'modelo': getattr(solicitud, 'reac_modelo', '') or '',
        'procesador': getattr(solicitud, 'reac_procesador', '') or '',
        'ram': getattr(solicitud, 'reac_ram', '') or '',
        'sistema_operativo': getattr(solicitud, 'reac_sistema_operativo', '') or '',
        'incluye_cargador': bool(getattr(solicitud, 'reac_incluye_cargador', False)),
        'especificaciones': getattr(solicitud, 'reac_especificaciones', '') or '',
    }


def solicitud_pdf_final_es_solo_reacondicionado(solicitud) -> bool:
    """
    True si el PDF final debe ser el de equipo reacondicionado (no el de piezas).

    Condición: hay al menos una línea reac aceptada y ninguna pieza de reparación
    ni servicio adicional aceptado.
    """
    lineas_aceptadas = obtener_lineas_aceptadas_final(solicitud)
    tiene_reac = lineas_aceptadas.filter(es_linea_reacondicionado=True).exists()
    if not tiene_reac:
        return False
    tiene_reparacion = lineas_aceptadas.filter(es_linea_reacondicionado=False).exists()
    tiene_servicios = obtener_servicios_aceptados_final(solicitud).exists()
    return not tiene_reparacion and not tiene_servicios


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
    Excepción: solo equipo reacondicionado aceptado usa snapshot reac + precios en línea.
    """
    if solicitud.estado not in ESTADOS_SOLICITUD_PDF_FINAL:
        return False

    if solicitud_pdf_final_es_solo_reacondicionado(solicitud):
        linea_reac = obtener_lineas_aceptadas_final(solicitud).filter(
            es_linea_reacondicionado=True,
        ).first()
        return bool(
            linea_reac
            and linea_reac.precio_unitario_cliente is not None
            and getattr(solicitud, 'resultado_costeo_reac', None)
        )

    if not getattr(solicitud, 'fecha_precios_cliente', None):
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
    """
    Serializa servicio aceptado; costo ya es precio final con IVA.

    En México incluye las inclusiones del paquete (ej. Solución Plata) en la
    descripción, igual que en el envío inicial al cliente.
    """
    tipo = servicio.tipo_servicio
    nombre = servicio.get_tipo_servicio_display()
    descripcion = formatear_descripcion_servicio_con_inclusiones(
        nombre_display=nombre,
        tipo_servicio=tipo,
        pais_codigo=_pais_codigo_activo(),
    )
    costo_con_iva = float(servicio.costo or 0)
    precio_sin_iva = costo_con_iva / IVA_FACTOR if costo_con_iva > 0 else 0.0
    return {
        'pk': servicio.pk,
        'descripcion': descripcion,
        'cantidad': 1,
        'precio_unitario_cliente': round(precio_sin_iva, 2),
        'subtotal_cliente': round(precio_sin_iva, 2),
        'costo_unitario': costo_con_iva,
        'es_necesaria': servicio.es_necesaria,
        'dias_entrega': None,
        'es_servicio': True,
        'tipo_servicio': tipo,
        'estado_cliente': servicio.estado_cliente,
        '_precio_ya_calculado': True,
    }


def _ordenar_necesarias_luego_opcionales(
    items_piezas: List[Dict[str, Any]],
    items_servicios: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Ordena ítems para el PDF: necesarias primero, opcionales al final.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Dentro de cada bloque (necesarias / opcionales) se mantiene el orden
    relativo: primero piezas, luego servicios, tal como llegaron.
    Así una limpieza opcional no aparece arriba de un paquete necesario
    solo porque se agregó antes en la solicitud.

    Args:
        items_piezas    : Dicts de piezas (con clave es_necesaria).
        items_servicios : Dicts de servicios (con clave es_necesaria).

    Returns:
        Lista única: piezas_nec + serv_nec + piezas_opc + serv_opc.
    """
    piezas_nec = [d for d in items_piezas if d.get('es_necesaria')]
    piezas_opc = [d for d in items_piezas if not d.get('es_necesaria')]
    servicios_nec = [d for d in items_servicios if d.get('es_necesaria')]
    servicios_opc = [d for d in items_servicios if not d.get('es_necesaria')]
    return piezas_nec + servicios_nec + piezas_opc + servicios_opc


def _ordenar_lista_nec_luego_opc(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Dentro de un solo tipo (solo piezas o solo servicios): necesarias y luego opcionales.

    Args:
        items: Lista de dicts con es_necesaria.

    Returns:
        Misma lista reordenada (orden relativo estable dentro de cada grupo).
    """
    nec = [d for d in items if d.get('es_necesaria')]
    opc = [d for d in items if not d.get('es_necesaria')]
    return nec + opc


def construir_items_cotizacion_final(solicitud) -> List[Dict[str, Any]]:
    """
    Ítems para PDF final: solo aceptados con precios al cliente persistidos.

    Args:
        solicitud: SolicitudCotizacion.

    Returns:
        Lista de dicts listos para calcular_totales_items_finales / PDF modo_final.
        Orden: necesarias primero, opcionales al final.
    """
    items_piezas: List[Dict[str, Any]] = []
    items_servicios: List[Dict[str, Any]] = []

    # Separar piezas y servicios para poder ordenar nec → opc como en el envío
    for linea in obtener_lineas_aceptadas_final(solicitud):
        # El equipo reacondicionado tiene PDF propio; no entra al de piezas
        if getattr(linea, 'es_linea_reacondicionado', False):
            continue
        item = serializar_linea_final(linea)
        if item:
            items_piezas.append(item)
    for servicio in obtener_servicios_aceptados_final(solicitud):
        items_servicios.append(serializar_servicio_final(servicio))

    return _ordenar_necesarias_luego_opcionales(items_piezas, items_servicios)


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
        En modos unificados, las opcionales van siempre al final.
    """
    items_piezas_nec = [d for d in items_piezas if d.get('es_necesaria')]
    items_piezas_opc = [d for d in items_piezas if not d.get('es_necesaria')]
    items_servicios_nec = [d for d in items_servicios if d.get('es_necesaria')]
    items_servicios_opc = [d for d in items_servicios if not d.get('es_necesaria')]

    if modo_agrupacion == 'todo_junto':
        # Un solo PDF: necesarias (piezas+servicios) y luego opcionales
        grupos = [{
            'titulo': '',
            'items': _ordenar_necesarias_luego_opcionales(items_piezas, items_servicios),
        }]
    elif modo_agrupacion == 'piezas_vs_servicios':
        grupos = []
        if items_piezas:
            grupos.append({
                'titulo': 'Cotización de Piezas',
                'items': _ordenar_lista_nec_luego_opc(items_piezas),
            })
        if items_servicios:
            grupos.append({
                'titulo': 'Cotización de Servicios Adicionales',
                'items': _ordenar_lista_nec_luego_opc(items_servicios),
            })
        if not grupos:
            grupos = [{
                'titulo': '',
                'items': _ordenar_necesarias_luego_opcionales(items_piezas, items_servicios),
            }]
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
            grupos = [{
                'titulo': '',
                'items': _ordenar_necesarias_luego_opcionales(items_piezas, items_servicios),
            }]
    else:
        grupos = [{
            'titulo': '',
            'items': _ordenar_necesarias_luego_opcionales(items_piezas, items_servicios),
        }]

    return [g for g in grupos if g.get('items')]
