"""
Persistencia de precios al cliente para cotizaciones de Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El costo de proveedor (costo_unitario) ya se guarda al cotizar.
El precio al cliente (con margen de profit) se calcula con la misma fórmula
del PDF y se congela en BD en la **primera respuesta** del cliente
(aprobar o rechazar una pieza/servicio), vía fecha_precios_cliente.

Así podemos analizar después qué se cotizó aunque el cliente haya rechazado.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.utils import timezone

from .pdf_cotizacion_cliente import calcular_precios_items_cotizacion
from .parametros_cotizador import obtener_profit_config

logger = logging.getLogger('almacen')

IVA_FACTOR = 1.16

# Campos de precio al cliente que se congelan en la primera respuesta.
# Se listan aquí para poder releerlos de forma selectiva (ver helper de abajo).
CAMPOS_PRECIO_CLIENTE_LINEA = (
    'precio_unitario_cliente',
    'subtotal_cliente_sin_iva',
    'profit_aplicado',
)


def refrescar_precios_cliente_en_memoria(linea) -> bool:
    """
    Relee de la BD los precios ya congelados de una línea para no pisarlos.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    ``persistir_precios_cliente_solicitud()`` guarda los precios con
    ``LineaCotizacion.objects.filter(pk=...).update(...)``: escribe directo en
    la base de datos y NO actualiza los objetos que ya estaban cargados en
    memoria de Python.

    Eso provoca un bug cuando alguien recorre varias líneas en un mismo
    request (por ejemplo el botón "Rechazar todas"): la primera línea congela
    los precios de todas, pero las siguientes siguen trayendo
    ``precio_unitario_cliente = None`` en memoria y su ``save()`` completo
    reescribe ese ``None`` encima del precio recién guardado.

    Este helper es el candado: si la solicitud YA tiene precios congelados
    (``fecha_precios_cliente``), volvemos a leer solo los tres campos de
    precio desde la BD. Se refrescan únicamente esos campos para no perder
    lo que el llamador acabe de poner en memoria (``estado_cliente``,
    ``motivo_rechazo``, ``fecha_respuesta``, etc.).

    Args:
        linea: Instancia de ``LineaCotizacion`` (puede venir obsoleta).

    Efectos secundarios:
        Hace un SELECT a la BD y muta los atributos de precio de ``linea``.
        No guarda nada: quien llama decide cuándo hacer ``save()``.

    Returns:
        bool: True si se releyeron los precios; False si no hacía falta
        (línea sin PK todavía, o solicitud sin precios congelados aún).
    """
    # Línea que aún no existe en BD: no hay nada que releer
    if not getattr(linea, 'pk', None):
        return False

    solicitud = getattr(linea, 'solicitud', None)
    if solicitud is None:
        return False

    # Si aún no se congelaron precios, el flujo normal los calculará después
    if not getattr(solicitud, 'fecha_precios_cliente', None):
        return False

    # Refresco selectivo: solo los campos de dinero, nada más
    linea.refresh_from_db(fields=CAMPOS_PRECIO_CLIENTE_LINEA)
    return True


def obtener_tipo_servicio_solicitud(solicitud) -> str:
    """
    Determina el perfil de profit a usar para calcular precios.

    Prioridad:
    1. tipo_servicio_cliente guardado al enviar el correo/PDF
    2. mostrador si la solicitud es sin orden activa
    3. estandar como valor por defecto
    """
    # Perfiles vigentes del panel (o .env si aún no hay filas)
    perfiles_validos = obtener_profit_config()
    tipo = (getattr(solicitud, 'tipo_servicio_cliente', '') or '').strip()
    if tipo in perfiles_validos:
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
        # Las líneas de equipo reacondicionado tienen precio fijado por costeo Excel, no profit
        if getattr(linea, 'es_linea_reacondicionado', False):
            continue
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
            # Si ya se personalizó el % al enviar, el motor lo respeta
            'profit_aplicado': (
                float(linea.profit_aplicado)
                if getattr(linea, 'profit_aplicado', None) is not None
                else None
            ),
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
    mano_obra = _obtener_mano_obra_solicitud(solicitud)

    # Sin descuento ni dilución de diagnóstico: reparación completa
    calculo = calcular_precios_items_cotizacion(
        items=items,
        tipo_servicio=tipo_servicio,
        incluir_descuento_diagnostico=False,
        mano_de_obra_override=mano_obra,
    )

    precios_por_linea: Dict[int, Dict[str, Decimal]] = {}
    for item in calculo.get('items_calculados', []):
        linea_pk = item.get('linea_pk') or item.get('pk')
        if not linea_pk or item.get('es_servicio'):
            continue
        precio_unit = Decimal(str(item.get('precio_unitario_cliente', 0)))
        subtotal = Decimal(str(item.get('subtotal_cliente', 0)))
        profit_val = item.get('profit_aplicado')
        entrada: Dict[str, Decimal] = {
            'precio_unitario_cliente': precio_unit,
            'subtotal_cliente_sin_iva': subtotal,
        }
        if profit_val is not None:
            entrada['profit_aplicado'] = Decimal(str(profit_val))
        precios_por_linea[int(linea_pk)] = entrada

    return {
        'tipo_servicio': tipo_servicio,
        'precios_por_linea': precios_por_linea,
        'precio_total_sin_iva_cliente': Decimal(str(calculo.get('precio_sin_iva', 0))),
        'precio_total_con_iva_cliente': Decimal(str(calculo.get('precio_con_iva', 0))),
        # Campo histórico: ya no se calcula total menos diagnóstico
        'precio_total_menos_diagnostico_cliente': None,
    }


def persistir_precios_cliente_solicitud(solicitud) -> bool:
    """
    Guarda en BD los precios al cliente calculados para toda la solicitud.

    Solo se ejecuta la primera vez (fecha_precios_cliente vacía) para no
    modificar precios ya acordados/mostrados al cliente. Se llama tanto al
    aprobar como al rechazar la primera pieza o servicio.

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
        update_kwargs = {
            'precio_unitario_cliente': datos['precio_unitario_cliente'],
            'subtotal_cliente_sin_iva': datos['subtotal_cliente_sin_iva'],
        }
        # Conservar el % efectivo usado al cotizar (auditoría / PDF coherente)
        if 'profit_aplicado' in datos:
            update_kwargs['profit_aplicado'] = datos['profit_aplicado']
        LineaCotizacion.objects.filter(pk=linea_pk).update(**update_kwargs)

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
