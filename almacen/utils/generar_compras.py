"""
Generación atómica de CompraProducto desde una cotización aprobada.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando el cliente ya aceptó piezas, Compras pulsa «Generar compras».
Ese clic debe crear UNA compra por cada línea aprobada, marcar las
líneas como ``compra_generada`` y, si ya no queda nada pendiente,
cerrar la solicitud a ``completada``.

El riesgo: si el servidor se cae a la mitad del loop (o hay doble
clic), quedaban compras a medias y dos POSTs veían las mismas líneas
pendientes. Recotización ya resolvió el mismo problema: transacción
en el alias del país + ``select_for_update`` de la fila.

Este módulo es el cerebro. ``SolicitudCotizacion.generar_compras``
solo delega aquí (regla fat models: el modelo no crece).

Autor: Sistema Integral de Gestión (SIGMA)
Fecha: Septiembre 2026
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from django.db import transaction
from django.utils import timezone

from almacen.utils.recotizacion import resolver_db_alias

if TYPE_CHECKING:
    from almacen.models import CompraProducto, SolicitudCotizacion
    from django.contrib.auth.models import AbstractBaseUser

logger = logging.getLogger('almacen')


def _resultado_vacio(*, motivo: str) -> dict:
    """
    Dict de sync ST cuando no se generó ninguna compra.

    Args:
        motivo: Código corto para la vista (ej. ``no_puede_generar``).

    Returns:
        dict: Forma estable que espera ``generar_compras_solicitud``.
    """
    return {
        'seguimientos_creados': 0,
        'estado_actualizado': False,
        'motivo_omitido': motivo,
    }


def generar_compras_desde_solicitud(
    solicitud: 'SolicitudCotizacion',
    usuario: Optional['AbstractBaseUser'] = None,
) -> List['CompraProducto']:
    """
    Crea CompraProducto por cada línea aprobada, con rollback si falla a mitad.

    Objetivo principal (contexto de negocio):
        Convertir las piezas que el cliente ya aceptó en compras de
        almacén, sin dejar el pedido a medias ni duplicarlo con doble clic.

    Args:
        solicitud: Cotización con líneas ``aprobada`` pendientes de compra.
        usuario: Quién pulsó el botón (queda en ``registrado_por``).

    Returns:
        list: CompraProducto creados en esta corrida (vacío si no aplicaba).

    Efectos secundarios:
        - INSERT de CompraProducto + UnidadCompra por línea.
        - UPDATE de líneas a ``compra_generada`` y de la solicitud a
          ``completada`` / ``en_proceso``.
        - Sync ST (SeguimientoPieza + estado esperando_piezas) DENTRO
          de la misma transacción.
        - Anota ``solicitud._resultado_sync_seguimiento_st`` para el mensaje
          de la vista.
    """
    from almacen.models import (
        CompraProducto,
        LineaCotizacion,
        SolicitudCotizacion,
        UnidadCompra,
    )

    # Sin transacción en el alias del país, un fallo deja compras huérfanas
    # y el segundo clic del botón vuelve a ver las mismas líneas pendientes.
    db_alias = resolver_db_alias(solicitud)

    with transaction.atomic(using=db_alias):
        # PASO 0: apartar la fila. El segundo POST espera aquí; al entrar
        # las líneas ya no están pendientes y puede_generar_compras() da False.
        (
            SolicitudCotizacion.objects
            .using(db_alias)
            .select_for_update()
            .filter(pk=solicitud.pk)
            .first()
        )
        solicitud.refresh_from_db()

        # Revalidar DESPUÉS del lock: el primer clic pudo terminar mientras
        # este esperaba, o Front aún no vinculó la orden.
        if not solicitud.puede_generar_compras():
            solicitud._resultado_sync_seguimiento_st = _resultado_vacio(
                motivo='no_puede_generar',
            )
            return []

        # PASO 1: lock de las líneas pendientes (mismo orden siempre:
        # solicitud primero, luego líneas, para no deadlock).
        lineas_pendientes = list(
            LineaCotizacion.objects
            .using(db_alias)
            .select_for_update()
            .filter(
                solicitud=solicitud,
                estado_cliente='aprobada',
                compra_generada__isnull=True,
            )
            .select_related(
                'producto',
                'proveedor',
                'pieza_cotizada_origen',
                'pieza_cotizada_origen__componente',
            )
        )

        compras_creadas: List[CompraProducto] = []
        lineas_procesadas = []

        # PASO 2: una compra + una UnidadCompra por línea. Si la 3ª falla,
        # atomic() deshace la 1ª y la 2ª: no hay pedido a medias.
        for linea in lineas_pendientes:
            compra = CompraProducto.objects.create(
                tipo='cotizacion',
                estado='pendiente_llegada',
                producto=linea.producto,
                proveedor=linea.proveedor,
                cantidad=linea.cantidad,
                costo_unitario=linea.costo_unitario,
                costo_total=linea.cantidad * linea.costo_unitario,
                fecha_pedido=timezone.now().date(),
                orden_servicio=solicitud.orden_servicio,
                orden_cliente=solicitud.numero_orden_cliente,
                observaciones=(
                    f'Generada desde solicitud {solicitud.numero_solicitud}'
                ),
                registrado_por=usuario,
            )
            # UnidadCompra: al recibir se convierten en UnidadInventario.
            # marca = producto genérico; modelo = descripción de la pieza.
            UnidadCompra.objects.create(
                compra=compra,
                numero_linea=1,
                marca=linea.producto.nombre,
                modelo=linea.descripcion_pieza,
                cantidad=linea.cantidad,
                costo_unitario=linea.costo_unitario,
                estado='pendiente',
            )
            linea.compra_generada = compra
            linea.estado_cliente = 'compra_generada'
            linea.save()
            compras_creadas.append(compra)
            lineas_procesadas.append(linea)

        # PASO 3: cerrar la solicitud si ya no quedan aprobadas sueltas.
        quedan_pendientes = (
            LineaCotizacion.objects
            .using(db_alias)
            .filter(
                solicitud=solicitud,
                estado_cliente='aprobada',
                compra_generada__isnull=True,
            )
            .exists()
        )
        if not quedan_pendientes:
            solicitud.estado = 'completada'
            solicitud.fecha_completada = timezone.now()
            solicitud.save()
        else:
            solicitud.estado = 'en_proceso'
            solicitud.save()

        # PASO 4: sync ST dentro de la misma transacción. Si falla el
        # seguimiento, tampoco queremos compras huérfanas en almacén.
        from almacen.utils.sincronizar_seguimiento_piezas import (
            sincronizar_seguimiento_piezas_al_generar_compras,
        )
        solicitud._resultado_sync_seguimiento_st = (
            sincronizar_seguimiento_piezas_al_generar_compras(
                solicitud,
                lineas=lineas_procesadas,
            )
        )

        logger.info(
            'generar_compras: %s compra(s) desde %s (alias=%s)',
            len(compras_creadas),
            solicitud.numero_solicitud,
            db_alias,
        )
        return compras_creadas
