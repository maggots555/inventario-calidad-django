"""
Anticipo del 50% para poder generar compras o cerrar solo-servicio.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Front cobra en el detalle de la orden. Compras no debe pedir piezas al
proveedor (ni pasar a En reparación si solo hay servicios) hasta que
esté cargado al menos el 50% del total que ve el cliente (el del PDF).

Este módulo NO decide si hay piezas por comprar: eso sigue siendo
``puede_generar_compras()``. Aquí solo preguntamos: ¿el dinero ya alcanzó?

Usa el mismo cálculo que el recuadro de pagos
(``calcular_resumen_cobro``): piezas + IVA MX + Venta Mostrador, y suma
todos los abonos que Front registró (aunque Facturación aún no convalide).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from almacen.models import SolicitudCotizacion

ESTADOS_SOLICITUD_CERRADA_CON_ACEPTACION = (
    'totalmente_aprobada',
    'parcialmente_aprobada',
)


def resumen_cobro_solicitud(
    solicitud: 'SolicitudCotizacion',
):
    """
    Totales de cobro de la orden vinculada, o None si aún no hay orden.

    Args:
        solicitud: SolicitudCotizacion (puede no tener orden_servicio).

    Returns:
        ResumenCobro o None.

    Efectos secundarios:
        Lee BD (piezas, pagos, venta mostrador). No escribe.
    """
    orden = getattr(solicitud, 'orden_servicio', None)
    if orden is None:
        return None

    from servicio_tecnico.models import OrdenServicio
    from servicio_tecnico.services.pagos_orden import calcular_resumen_cobro

    # Recargar: al aceptar, la Cotizacion/VentaMostrador/pagos pudieron
    # cambiar hace un instante y la instancia en memoria sigue vieja.
    orden = OrdenServicio.objects.get(pk=orden.pk)
    return calcular_resumen_cobro(orden)


def cubre_anticipo_50_solicitud(solicitud: 'SolicitudCotizacion') -> bool:
    """
    True si ya se puede proceder (50% cargado, o no hay nada que cobrar).

    Args:
        solicitud: SolicitudCotizacion.

    Returns:
        bool: True si no hay orden, si el total es $0, o si pagado >= 50%.
    """
    resumen = resumen_cobro_solicitud(solicitud)
    if resumen is None:
        # Sin orden el POST ya se bloquea por compras/servicios_pendientes_sin_orden.
        return True
    return bool(resumen.cubre_anticipo_50)


def puede_cerrar_solo_servicios(solicitud: 'SolicitudCotizacion') -> bool:
    """
    True si el cliente solo aceptó servicios y ya están en ST, pero la
    solicitud aún no se completó (falta el 50% o el clic de confirmar).

    Args:
        solicitud: SolicitudCotizacion.

    Returns:
        bool: listo para el botón «Generar servicio» / pasar a En reparación.
    """
    # Completada ya cerró: el botón de «Generar servicio» no debe aparecer.
    if solicitud.estado == 'completada':
        return False
    # Aceptación cerrada (todas las líneas con sí/no), pero aún no comprada.
    if solicitud.estado not in ESTADOS_SOLICITUD_CERRADA_CON_ACEPTACION:
        return False
    # Si hay piezas por comprar, este no es un caso de solo-servicio.
    if solicitud.puede_generar_compras():
        return False
    if not solicitud.orden_servicio_id:
        return False
    return solicitud.servicios_adicionales.filter(
        estado_cliente='compra_generada',
    ).exists()


def mensaje_falta_anticipo(solicitud: 'SolicitudCotizacion') -> str:
    """
    Texto para el botón apagado y para el error del POST.

    Args:
        solicitud: SolicitudCotizacion.

    Returns:
        str: mensaje con pagado vs mínimo, o genérico si no hay resumen.
    """
    resumen = resumen_cobro_solicitud(solicitud)
    if resumen is None:
        return (
            'Falta el anticipo del 50%. Cárgalo en el detalle de la orden '
            'antes de generar compras.'
        )
    return (
        f'Falta anticipo: pagado ${resumen.pagado} de '
        f'${resumen.anticipo_minimo} (50%). Cárgalo en el detalle de la orden.'
    )
