"""
Registra en Venta Mostrador las piezas que salen por SolicitudBaja (stock interno).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
La cotización (SolicitudCotizacion → LineaCotizacion) ya crea piezas en ST.
Este módulo es un camino PARALELO: la pieza ya está en el anaquel, el agente
aprueba la baja y queremos verla en el apartado Venta Mostrador de la orden.

No crea LineaCotizacion, CompraProducto, PiezaCotizada ni SeguimientoPieza.
Así no se pisa el flujo de cotización / compras a proveedor.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import TYPE_CHECKING

from django.utils import timezone

from almacen.utils.resolver_componente import resolver_componente_desde_producto
from config.constants import PALABRAS_CLAVE_COMPONENTE
from servicio_tecnico.models import PiezaVentaMostrador, VentaMostrador
from servicio_tecnico.services.historial import registrar_historial

if TYPE_CHECKING:
    from almacen.models import SolicitudBaja, ProductoAlmacen
    from scorecard.models import ComponenteEquipo

logger = logging.getLogger(__name__)

# Solo estos tipos van a una orden ST (OOW- o FL-). Consumo interno y
# transferencia no deben crear piezas de venta mostrador.
TIPOS_SOLICITUD_CON_VENTA_MOSTRADOR = ('servicio_tecnico', 'venta_mostrador')
PAQUETES_CON_COSTO_YA_CARGADO = ('premium', 'oro', 'plata')
NOMBRE_COMPONENTE_KIT_LIMPIEZA = 'Kit de Limpieza'


def _keywords_kit_limpieza() -> tuple[str, ...]:
    """
    Keywords del catálogo Almacén→ST para reconocer un kit de limpieza.

    Returns:
        tuple[str, ...]: Frases en mayúsculas (ej. KIT DE LIMPIEZA).
    """
    for keywords, nombre_componente in PALABRAS_CLAVE_COMPONENTE:
        if nombre_componente == NOMBRE_COMPONENTE_KIT_LIMPIEZA:
            return tuple(keyword.upper() for keyword in keywords)
    return ('KIT DE LIMPIEZA', 'KIT LIMPIEZA', 'CLEANING KIT')


def _es_kit_de_limpieza(producto: ProductoAlmacen, componente: ComponenteEquipo | None) -> bool:
    """
    True si el producto de almacén es un kit de limpieza (no el servicio).

    Args:
        producto: ProductoAlmacen de la SolicitudBaja.
        componente: ComponenteEquipo ya resuelto, o None.

    Returns:
        bool: True solo para el kit físico, no para «Limpieza y mantenimiento».
    """
    # El resolver ya mapea P0186 «KIT DE LIMPIEZA» → componente Kit de Limpieza.
    if componente is not None and componente.nombre == NOMBRE_COMPONENTE_KIT_LIMPIEZA:
        return True
    texto = f"{producto.nombre or ''} {producto.descripcion or ''}".upper()
    return any(keyword in texto for keyword in _keywords_kit_limpieza())


def _calcular_precio_pieza_stock_interno(
    solicitud: SolicitudBaja,
    venta_mostrador: VentaMostrador,
    componente: ComponenteEquipo | None,
) -> Decimal:
    """
    Decide el precio de la pieza según si un servicio/paquete ya cubre el cobro.

    Args:
        solicitud: SolicitudBaja aprobada (se usa el costo del producto).
        venta_mostrador: VM de la orden (puede ser nueva o ya existir).
        componente: ComponenteEquipo resuelto para saber si es kit de limpieza.

    Returns:
        Decimal: $0.00 si el cobro ya está en paquete o en limpieza; si no,
        costo_unitario del producto.
    """
    # Paquete plata/oro/premium: SSD/RAM/kit ya van en el precio del paquete.
    if venta_mostrador.paquete in PAQUETES_CON_COSTO_YA_CARGADO:
        return Decimal('0.00')
    # Limpieza y mantenimiento incluye el kit de regalo: solo el kit va a $0.
    # Una RAM u otra pieza en la misma orden SÍ lleva costo de stock.
    if (
        venta_mostrador.incluye_limpieza
        and _es_kit_de_limpieza(solicitud.producto, componente)
    ):
        return Decimal('0.00')
    return solicitud.producto.costo_unitario or Decimal('0.00')


def registrar_pieza_vm_desde_solicitud_baja(solicitud: SolicitudBaja):
    """
    Crea (o reutiliza) VentaMostrador y una PiezaVentaMostrador de stock interno.

    Objetivo de negocio:
        Al aprobar una SolicitudBaja vinculada a OOW- o FL-, la pieza debe
        aparecer en Venta Mostrador para control de inventario (SSD, kit, etc.).

    Args:
        solicitud: SolicitudBaja ya aprobada, con producto y opcionalmente orden.

    Returns:
        PiezaVentaMostrador creada o ya existente; None si el tipo/orden no aplica.

    Efectos secundarios:
        - get_or_create de VentaMostrador en la orden (no duplica si ya hay paquete).
        - Inserta PiezaVentaMostrador con linea_cotizacion=NULL y solicitud_baja.
        - Escribe un evento en HistorialOrden (tipo 'pieza').
    """
    # Paso 1: filtros de negocio — sin orden o tipo incorrecto, no hay nada que hacer.
    if solicitud.estado != 'aprobada':
        return None
    if solicitud.tipo_solicitud not in TIPOS_SOLICITUD_CON_VENTA_MOSTRADOR:
        return None
    if not solicitud.orden_servicio_id:
        return None

    # Paso 2: anti-duplicado — una solicitud genera a lo más una pieza VM.
    pieza_existente = PiezaVentaMostrador.objects.filter(
        solicitud_baja=solicitud,
    ).first()
    if pieza_existente:
        return pieza_existente

    orden = solicitud.orden_servicio
    producto = solicitud.producto

    # Paso 3: reutilizar VM si la orden ya tiene paquete/cotización; si no, crearla.
    venta_mostrador, _creada = VentaMostrador.objects.get_or_create(
        orden=orden,
        defaults={'fecha_venta': timezone.now()},
    )

    # Resolver componente ANTES del precio: el kit de limpieza se reconoce así.
    nombre_producto = (producto.nombre or 'Pieza de almacén').strip()
    componente = resolver_componente_desde_producto(
        nombre_producto,
        producto.descripcion or '',
    )
    precio_unitario = _calcular_precio_pieza_stock_interno(
        solicitud,
        venta_mostrador,
        componente,
    )

    descripcion_pieza = nombre_producto[:200]
    notas_pieza = (
        f"Stock interno — solicitud #{solicitud.pk}. "
        f"{(solicitud.observaciones or '')[:400]}"
    ).strip()
    # Deja rastro visible en ST de por qué el kit salió a $0.
    if (
        precio_unitario == Decimal('0.00')
        and venta_mostrador.incluye_limpieza
        and _es_kit_de_limpieza(producto, componente)
    ):
        notas_pieza = (
            f"{notas_pieza} Incluido en el servicio de limpieza y mantenimiento."
        ).strip()

    pieza = PiezaVentaMostrador.objects.create(
        venta_mostrador=venta_mostrador,
        linea_cotizacion=None,
        solicitud_baja=solicitud,
        componente=componente,
        descripcion_pieza=descripcion_pieza,
        cantidad=solicitud.cantidad,
        precio_unitario=precio_unitario,
        notas=notas_pieza,
    )

    registrar_historial(
        orden=orden,
        tipo_evento='pieza',
        usuario=solicitud.agente_almacen,
        comentario=(
            f"Pieza de stock interno en Venta Mostrador: {descripcion_pieza} "
            f"(x{solicitud.cantidad}) — solicitud #{solicitud.pk}. "
            f"Precio: ${precio_unitario}."
        ),
        es_sistema=True,
    )
    logger.info(
        "SolicitudBaja #%s: PiezaVentaMostrador #%s en orden %s (precio=%s)",
        solicitud.pk,
        pieza.pk,
        orden.numero_orden_interno,
        precio_unitario,
    )
    return pieza
