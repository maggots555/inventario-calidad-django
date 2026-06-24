"""
Persistencia de precios al cliente para cotizaciones de Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El costo de proveedor (costo_unitario) ya se guarda al cotizar.
El precio al cliente (con margen de profit) solo existía en el PDF.
Este módulo calcula esos precios con la misma fórmula del PDF y los
guarda en la base de datos cuando el cliente aprueba las líneas.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.utils import timezone

from .pdf_cotizacion_cliente import (
    PROFIT_CONFIG,
    calcular_precios_items_cotizacion,
)

logger = logging.getLogger('almacen')

IVA_FACTOR = 1.16


def obtener_tipo_servicio_solicitud(solicitud) -> str:
    """
    Determina el perfil de profit a usar para calcular precios.

    Prioridad:
    1. tipo_servicio_cliente guardado al enviar el correo/PDF
    2. mostrador si la solicitud es sin orden activa
    3. estandar como valor por defecto
    """
    tipo = (getattr(solicitud, 'tipo_servicio_cliente', '') or '').strip()
    if tipo in PROFIT_CONFIG:
        return tipo
    if getattr(solicitud, 'sin_orden_activa', False):
        return 'mostrador'
    return 'estandar'


def construir_items_desde_solicitud(solicitud) -> List[Dict[str, Any]]:
    """
    Convierte líneas de piezas y servicios adicionales al formato del calculador PDF.

    Cada ítem de pieza incluye linea_pk para mapear el resultado de vuelta al modelo.
    """
    items: List[Dict[str, Any]] = []

    for linea in solicitud.lineas.select_related('producto').all():
        costo = float(linea.costo_unitario or 0)
        if costo <= 0:
            continue
        descripcion = linea.descripcion_pieza or linea.producto.nombre
        if linea.descripcion_pieza and linea.producto:
            descripcion = f"{linea.producto.nombre}: {linea.descripcion_pieza}"
        items.append({
            'linea_pk': linea.pk,
            'pk': linea.pk,
            'descripcion': descripcion,
            'cantidad': int(linea.cantidad or 1),
            'costo_unitario': costo,
            'es_necesaria': linea.es_necesaria,
            'dias_entrega': linea.tiempo_entrega_estimado,
            'es_servicio': False,
        })

    for servicio in solicitud.servicios_adicionales.all():
        costo = float(servicio.costo or 0)
        if costo <= 0:
            continue
        items.append({
            'linea_pk': None,
            'pk': servicio.pk,
            'descripcion': servicio.get_tipo_servicio_display(),
            'cantidad': 1,
            'costo_unitario': costo,
            'es_necesaria': servicio.es_necesaria,
            'dias_entrega': None,
            'es_servicio': True,
        })

    return items


def _obtener_mano_obra_solicitud(solicitud) -> float:
    """Lee mano de obra desde la cotización ST vinculada, si existe."""
    orden = getattr(solicitud, 'orden_servicio', None)
    if not orden:
        return 0.0
    try:
        return float(orden.cotizacion.costo_mano_obra or 0)
    except Exception:
        return 0.0


def calcular_precios_cliente_solicitud(solicitud) -> Dict[str, Any]:
    """
    Calcula precios al cliente por línea y totales de cabecera.

    Usa la misma lógica que el PDF (todo junto) para que los importes coincidan
    con la cotización que recibió el cliente.
    """
    items = construir_items_desde_solicitud(solicitud)
    tipo_servicio = obtener_tipo_servicio_solicitud(solicitud)
    incluir_descuento = bool(
        getattr(solicitud, 'incluir_descuento_diagnostico_cliente', True)
    )
    mano_obra = _obtener_mano_obra_solicitud(solicitud)

    calculo = calcular_precios_items_cotizacion(
        items=items,
        tipo_servicio=tipo_servicio,
        incluir_descuento_diagnostico=incluir_descuento,
        mano_de_obra_override=mano_obra,
    )

    precios_por_linea: Dict[int, Dict[str, Decimal]] = {}
    for item in calculo.get('items_calculados', []):
        linea_pk = item.get('linea_pk') or item.get('pk')
        if not linea_pk or item.get('es_servicio'):
            continue
        precio_unit = Decimal(str(item.get('precio_unitario_cliente', 0)))
        subtotal = Decimal(str(item.get('subtotal_cliente', 0)))
        precios_por_linea[int(linea_pk)] = {
            'precio_unitario_cliente': precio_unit,
            'subtotal_cliente_sin_iva': subtotal,
        }

    return {
        'tipo_servicio': tipo_servicio,
        'precios_por_linea': precios_por_linea,
        'precio_total_sin_iva_cliente': Decimal(str(calculo.get('precio_sin_iva', 0))),
        'precio_total_con_iva_cliente': Decimal(str(calculo.get('precio_con_iva', 0))),
        'precio_total_menos_diagnostico_cliente': (
            Decimal(str(calculo['precio_menos_diagnostico']))
            if calculo.get('precio_menos_diagnostico') is not None
            else None
        ),
    }


def persistir_precios_cliente_solicitud(solicitud) -> bool:
    """
    Guarda en BD los precios al cliente calculados para toda la solicitud.

    Solo se ejecuta la primera vez (fecha_precios_cliente vacía) para no
    modificar precios ya acordados con el cliente.

    Returns:
        bool: True si se persistieron precios, False si ya estaban bloqueados o sin ítems.
    """
    if getattr(solicitud, 'fecha_precios_cliente', None):
        return False

    resultado = calcular_precios_cliente_solicitud(solicitud)
    precios_por_linea = resultado.get('precios_por_linea') or {}

    if not precios_por_linea:
        logger.warning(
            f"[PRECIOS_CLIENTE] Solicitud {solicitud.numero_solicitud}: "
            'sin líneas con costo para calcular precios al cliente.'
        )
        return False

    from almacen.models import LineaCotizacion

    for linea_pk, datos in precios_por_linea.items():
        LineaCotizacion.objects.filter(pk=linea_pk).update(
            precio_unitario_cliente=datos['precio_unitario_cliente'],
            subtotal_cliente_sin_iva=datos['subtotal_cliente_sin_iva'],
        )

    solicitud.precio_total_sin_iva_cliente = resultado['precio_total_sin_iva_cliente']
    solicitud.precio_total_con_iva_cliente = resultado['precio_total_con_iva_cliente']
    solicitud.precio_total_menos_diagnostico_cliente = resultado[
        'precio_total_menos_diagnostico_cliente'
    ]
    solicitud.fecha_precios_cliente = timezone.now()
    solicitud.save(update_fields=[
        'precio_total_sin_iva_cliente',
        'precio_total_con_iva_cliente',
        'precio_total_menos_diagnostico_cliente',
        'fecha_precios_cliente',
    ])

    if solicitud.orden_servicio_id:
        for linea in solicitud.lineas.select_related('pieza_cotizada_origen').all():
            linea.refresh_from_db()
            if linea.pieza_cotizada_origen_id or solicitud.orden_servicio_id:
                linea._sincronizar_pieza_st()

    logger.info(
        f"[PRECIOS_CLIENTE] Solicitud {solicitud.numero_solicitud}: "
        f'{len(precios_por_linea)} línea(s) con precio cliente persistido.'
    )
    return True
