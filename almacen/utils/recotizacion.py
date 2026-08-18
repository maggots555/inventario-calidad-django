"""
Recotización: abrir una ronda nueva sobre la misma solicitud
=============================================================

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Escenario real: mandamos la cotización el día 1, el cliente no contesta, pasan
los 5 días hábiles de vigencia y al día 9 llama diciendo "sí la quiero". Ese
"sí" no se puede aceptar de inmediato: los costos que le dimos ya caducaron.
Hay que preguntarle otra vez a Compras si la pieza sigue existiendo y a qué
precio. A eso le llamamos RECOTIZAR.

¿Cómo lo resolvemos? NO creamos una solicitud nueva (perderíamos el historial y
el vínculo con la orden de Servicio Técnico). En vez de eso:

1. Guardamos una "foto" (snapshot) de cómo estaba la cotización -> RondaCotizacion
2. Subimos el contador ``ronda_cotizacion`` (1 -> 2 -> 3...)
3. Regresamos la solicitud a estado ``borrador`` para que Compras la vuelva a
   ver en su bandeja y capture los costos actualizados
4. Borramos los precios congelados de la ronda anterior (para que nadie los
   confunda con precios vigentes)
5. Avisamos a Compras por campanita, push y correo

Al volver a ``borrador`` se reutiliza TODO el flujo que ya existe:
borrador -> notificar a Front -> enviada_front (arranca vigencia nueva) ->
enviar cotización al cliente. No hubo que inventar estados nuevos.

Autor: Sistema Integral de Gestión (SIGMA)
Fecha: Agosto 2026
"""

import logging
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)


# ============================================================================
# CAMPOS QUE SE LIMPIAN AL ABRIR UNA RONDA NUEVA
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# Estos son los precios "congelados" que se calcularon cuando el cliente
# respondió por primera vez. Como esa ronda ya murió, hay que borrarlos para
# que Compras capture costos frescos y el motor de profit los recalcule.
CAMPOS_PRECIO_A_LIMPIAR_LINEA = (
    'precio_unitario_cliente',
    'subtotal_cliente_sin_iva',
    'profit_aplicado',
)


# ============================================================================
# CONSTRUCCIÓN DEL SNAPSHOT
# ============================================================================

def _serializar_linea(linea) -> dict:
    """
    Convierte una LineaCotizacion a un diccionario guardable en JSON.

    Objetivo principal (contexto de negocio):
        Conservar qué pieza, a qué costo de proveedor y a qué precio de cliente
        se ofreció en la ronda que está por cerrarse.

    Args:
        linea (LineaCotizacion): Línea de pieza a fotografiar.

    Returns:
        dict: Datos planos (str/float/int) listos para JSONField.

    Efectos secundarios:
        Ninguno.
    """
    # EXPLICACIÓN: JSON no entiende Decimal ni objetos de Django, así que
    # convertimos a str los importes (str conserva los centavos exactos) y
    # guardamos solo el nombre del proveedor, no el objeto completo.
    return {
        'numero_linea': linea.numero_linea,
        'descripcion_pieza': linea.descripcion_pieza,
        'producto_id': linea.producto_id,
        'proveedor': linea.proveedor.nombre if linea.proveedor else '',
        'cantidad': linea.cantidad,
        'costo_unitario': str(linea.costo_unitario or Decimal('0.00')),
        'precio_unitario_cliente': (
            str(linea.precio_unitario_cliente)
            if linea.precio_unitario_cliente is not None else None
        ),
        'profit_aplicado': (
            str(linea.profit_aplicado)
            if linea.profit_aplicado is not None else None
        ),
        'estado_cliente': linea.estado_cliente,
        'es_necesaria': linea.es_necesaria,
        'tiempo_entrega_estimado': linea.tiempo_entrega_estimado,
    }


def _serializar_servicio(servicio) -> dict:
    """
    Convierte una LineaServicioAdicional a diccionario JSON.

    Args:
        servicio (LineaServicioAdicional): Servicio de venta mostrador.

    Returns:
        dict: Datos planos listos para JSONField.

    Efectos secundarios:
        Ninguno.
    """
    return {
        'numero_linea': servicio.numero_linea,
        'tipo_servicio': servicio.tipo_servicio,
        'tipo_servicio_label': servicio.get_tipo_servicio_display(),
        'costo': str(servicio.costo or Decimal('0.00')),
        'es_necesaria': servicio.es_necesaria,
        'estado_cliente': servicio.estado_cliente,
    }


def construir_snapshot(solicitud) -> dict:
    """
    Arma la foto completa de la ronda actual antes de cerrarla.

    Objetivo principal (contexto de negocio):
        Permitir comparar después "cuánto subió el costo entre la ronda 1 y la
        ronda 2" sin tener que reconstruirlo a mano.

    Args:
        solicitud (SolicitudCotizacion): Cotización a fotografiar.

    Returns:
        dict: Con claves ``lineas``, ``servicios``, ``costo_total`` y
        ``precio_cliente_total``.

    Efectos secundarios:
        Ninguno (solo lecturas).
    """
    lineas = list(solicitud.lineas.all().order_by('numero_linea'))
    servicios = list(solicitud.servicios_adicionales.all().order_by('numero_linea'))

    # Acumuladores de totales para poder comparar rondas en SQL sin abrir JSON
    costo_total = Decimal('0.00')
    precio_cliente_total = Decimal('0.00')

    for linea in lineas:
        # Costo del proveedor: lo que nos cuesta a nosotros
        costo_total += (linea.costo_unitario or Decimal('0.00')) * linea.cantidad
        # Precio al cliente: puede ser None si el cliente nunca respondió
        if linea.precio_unitario_cliente is not None:
            precio_cliente_total += linea.precio_unitario_cliente * linea.cantidad

    return {
        'lineas': [_serializar_linea(linea) for linea in lineas],
        'servicios': [_serializar_servicio(servicio) for servicio in servicios],
        'costo_total': costo_total,
        'precio_cliente_total': precio_cliente_total,
    }


# ============================================================================
# APERTURA DE UNA RONDA NUEVA
# ============================================================================

@transaction.atomic
def iniciar_nueva_ronda(solicitud, usuario=None, observaciones: str = ''):
    """
    Cierra la ronda vencida y reabre la solicitud para que Compras recotice.

    Objetivo principal (contexto de negocio):
        Es el corazón del flujo de recotización. Se dispara desde el botón
        "Solicitar Recotización" cuando la vigencia venció y el cliente quiere
        continuar con la reparación.

    Args:
        solicitud (SolicitudCotizacion): Cotización vencida a reciclar.
        usuario (User | None): Quien solicita la recotización (auditoría).
        observaciones (str): Nota opcional del motivo.

    Returns:
        RondaCotizacion: El snapshot de la ronda que se acaba de cerrar.

    Raises:
        ValueError: Si la solicitud no cumple las condiciones para recotizar
            (no venció, o el cliente ya respondió algo).

    Efectos secundarios:
        - Crea una fila en ``RondaCotizacion`` con la foto de la ronda anterior.
        - Modifica la solicitud: sube ``ronda_cotizacion``, la regresa a
          ``borrador`` y limpia fechas y banderas de la ronda anterior.
        - Borra los precios congelados de todas las líneas.
        - Encola una tarea Celery que avisa a Compras.

    Nota: todo corre dentro de una transacción. Si algo falla a mitad del
    camino, la base de datos queda como estaba (no hay rondas a medias).
    """
    # Importaciones locales para evitar ciclos: models importa utils al final
    from almacen.models import RondaCotizacion
    from almacen.utils.vigencia_cotizacion import puede_recotizar

    # ---- PASO 1: validar que realmente se pueda recotizar ----
    # Regla de negocio: solo si venció Y el cliente no respondió absolutamente
    # nada. Si ya aprobó una pieza hay precios congelados y posiblemente
    # compras generadas; reciclar la solicitud rompería ese historial.
    if not puede_recotizar(solicitud):
        raise ValueError(
            'Esta cotización no se puede recotizar. Solo aplica cuando la '
            'vigencia ya venció y el cliente no ha respondido ninguna pieza '
            'ni servicio.'
        )

    ronda_actual = solicitud.ronda_cotizacion or 1

    # ---- PASO 2: fotografiar la ronda que estamos cerrando ----
    snapshot = construir_snapshot(solicitud)

    ronda = RondaCotizacion.objects.create(
        solicitud=solicitud,
        numero_ronda=ronda_actual,
        fecha_inicio_vigencia=solicitud.fecha_inicio_vigencia,
        fecha_vencimiento=solicitud.fecha_vencimiento_vigencia,
        motivo_cierre='recotizacion',
        snapshot_lineas=snapshot['lineas'],
        snapshot_servicios=snapshot['servicios'],
        costo_total_snapshot=snapshot['costo_total'],
        precio_cliente_total_snapshot=snapshot['precio_cliente_total'],
        creada_por=usuario,
        observaciones=observaciones,
    )

    # ---- PASO 3: limpiar los precios congelados de las líneas ----
    # EXPLICACIÓN: si dejáramos estos precios, la calculadora de profit creería
    # que ya están confirmados y el PDF nuevo saldría con importes viejos.
    for linea in solicitud.lineas.all():
        for campo in CAMPOS_PRECIO_A_LIMPIAR_LINEA:
            setattr(linea, campo, None)
        linea.save(update_fields=list(CAMPOS_PRECIO_A_LIMPIAR_LINEA))

    # ---- PASO 4: reabrir la solicitud como borrador de la ronda siguiente ----
    solicitud.ronda_cotizacion = ronda_actual + 1
    solicitud.estado = 'borrador'
    # El reloj de vigencia se reinicia cuando Compras vuelva a notificar a Front
    solicitud.fecha_inicio_vigencia = None
    solicitud.fecha_vencimiento_vigencia = None
    solicitud.aviso_vencimiento_enviado = False
    # Los precios de cabecera también se descongelan
    solicitud.fecha_precios_cliente = None
    solicitud.tipo_servicio_cliente = ''
    # Las banderas de PNC pertenecían a la ronda anterior
    solicitud.plantilla_pnc_front_enviada = False
    solicitud.aviso_pnc_cliente_enviado = False

    solicitud.save(update_fields=[
        'ronda_cotizacion',
        'estado',
        'fecha_inicio_vigencia',
        'fecha_vencimiento_vigencia',
        'aviso_vencimiento_enviado',
        'fecha_precios_cliente',
        'tipo_servicio_cliente',
        'plantilla_pnc_front_enviada',
        'aviso_pnc_cliente_enviado',
    ])

    # ---- PASO 5: avisarle a Compras que tiene trabajo nuevo ----
    _notificar_compras_recotizacion(solicitud, usuario)

    logger.info(
        '[RECOTIZACION] %s pasó de ronda %s a ronda %s (solicitada por %s)',
        solicitud.numero_solicitud,
        ronda_actual,
        solicitud.ronda_cotizacion,
        getattr(usuario, 'username', 'sistema'),
    )

    return ronda


def _notificar_compras_recotizacion(solicitud, usuario=None) -> None:
    """
    Encola la tarea Celery que avisa a Compras de la recotización.

    Args:
        solicitud (SolicitudCotizacion): Cotización que entró a ronda nueva.
        usuario (User | None): Quien solicitó la recotización.

    Efectos secundarios:
        Encola ``almacen.notificar_recotizacion_solicitada``. Si Celery o Redis
        están caídos, solo se registra el error: la recotización NO se revierte
        (perder un correo no debe bloquear la operación).
    """
    try:
        from config.paises_config import get_pais_actual
        from almacen.tasks import notificar_recotizacion_solicitada_task

        # db_alias: los workers de Celery no pasan por el middleware de país,
        # así que hay que decirles explícitamente en qué base escribir.
        notificar_recotizacion_solicitada_task.delay(
            solicitud_id=solicitud.pk,
            usuario_id=usuario.pk if usuario and usuario.is_authenticated else None,
            db_alias=get_pais_actual()['db_alias'],
        )
    except Exception as exc:  # pragma: no cover - depende de infraestructura
        logger.error(
            '[RECOTIZACION] No se pudo encolar el aviso a Compras de %s: %s',
            solicitud.numero_solicitud,
            exc,
        )
