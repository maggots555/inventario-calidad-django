"""
Cálculo de cobros y registro de pagos de una orden de servicio.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El modelo PagoOrden solo guarda cada abono (monto, foto, quién cobró).
Este archivo es el "cerebro": suma cotización + venta mostrador, aplica
IVA de México, resta lo ya pagado y valida que no se cobre de más.

No es una vista HTTP: lo llaman detalle_orden, el banner de alertas y
los tests. Así no hinchamos OrdenServicio ni models.py (regla fat models).
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO
from typing import Optional

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Sum
from PIL import Image, ImageOps, UnidentifiedImageError

from config.paises_config import get_pais_actual
from servicio_tecnico.services.historial import registrar_historial


# IVA 16% igual que el PDF de cotización al cliente en Almacén (solo MX).
IVA_TASA_MX = Decimal('0.16')
CENTAVO = Decimal('0.01')
PERMISO_REGISTRAR_PAGO = 'servicio_tecnico.add_pagoorden'

# Estados en los que el negocio espera al menos el 50% (anticipo).
ESTADOS_REQUIEREN_ANTICIPO_50 = (
    'reparacion',
    'partes_solicitadas_proveedor',
    'esperando_piezas',
)


@dataclass
class ResumenCobro:
    """
    Totales listos para mostrar en el detalle de la orden.

    Objetivo de negocio:
        Una sola foto del dinero: qué se cotizó, cuánto IVA, qué se
        pagó y cuánto falta (incluyendo si ya cubre el 50% de anticipo).
    """

    subtotal_cotizacion: Decimal
    iva_cotizacion: Decimal
    total_venta_mostrador: Decimal
    total_a_cobrar: Decimal
    pagado: Decimal
    saldo: Decimal
    porcentaje_pagado: Decimal
    anticipo_minimo: Decimal
    cubre_anticipo_50: bool
    cubierto_100: bool
    es_estimado: bool
    aplica_iva: bool
    tasa_iva: Decimal


def _db_de(instancia) -> str:
    """
    Alias de BD donde ya vive el objeto (México, Argentina, …).

    EXPLICACIÓN PARA PRINCIPIANTES:
    SIGMA tiene una base por país. Django abre una CONEXIÓN distinta
    por alias (`default`, `mexico`, `argentina`…). `transaction.atomic()`
    sin `using=` siempre usa `default`. Si la orden se leyó en `mexico`,
    `select_for_update` corre en esa conexión… fuera de la transacción
    → error en producción: "select_for_update cannot be used outside
    of a transaction".

    Args:
        instancia: modelo ya cargado (OrdenServicio, PagoOrden, …).

    Returns:
        str: alias (`default`, `mexico`, …).
    """
    return getattr(instancia._state, 'db', None) or 'default'


def _dinero(valor) -> Decimal:
    """
    Redondea a 2 decimales como un cajero (0.005 sube a 0.01).

    Args:
        valor: número o Decimal.

    Returns:
        Decimal con exactamente 2 decimales.
    """
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _codigo_pais_activo(codigo_pais: Optional[str] = None) -> str:
    """
    Código ISO del país del request (MX, AR, …).

    Args:
        codigo_pais: Si llega, se usa tal cual (útil en tests).

    Returns:
        str: código de país; MX si no hay middleware.
    """
    if codigo_pais:
        return codigo_pais
    try:
        return get_pais_actual().get('codigo', 'MX') or 'MX'
    except Exception:
        return 'MX'


def _subtotal_cotizacion(orden) -> tuple[Decimal, bool]:
    """
    Subtotal de la cotización ST (sin IVA).

    EXPLICACIÓN PARA PRINCIPIANTES:
    Si el cliente ya aceptó, usamos costo_total_final (solo piezas
    aceptadas + mano de obra con descuento). Si todavía no responde,
    usamos un estimado (todas las piezas + MO) para poder cobrar el
    anticipo del 50% antes de pedir refacciones.

    Args:
        orden: OrdenServicio (puede o no tener cotizacion).

    Returns:
        tuple: (subtotal Decimal, es_estimado bool).
    """
    cotizacion = getattr(orden, 'cotizacion', None)
    if cotizacion is None:
        return Decimal('0.00'), False

    # Paso: cotización aceptada → total real a cobrar (piezas sí).
    if cotizacion.usuario_acepto:
        return _dinero(cotizacion.costo_total_final), False

    # Paso: rechazada → ya no cobramos esa cotización (sí puede haber VM).
    if cotizacion.usuario_acepto is False:
        return Decimal('0.00'), False

    # Paso: sin respuesta → estimado con todas las piezas al precio cliente.
    total_piezas = Decimal('0.00')
    for pieza in cotizacion.piezas_cotizadas.all():
        if pieza.precio_unitario_cliente is not None:
            total_piezas += pieza.cantidad * pieza.precio_unitario_cliente
        else:
            total_piezas += pieza.costo_total
    estimado = total_piezas + (cotizacion.costo_mano_obra or Decimal('0.00'))
    return _dinero(estimado), True


def calcular_resumen_cobro(orden, codigo_pais: Optional[str] = None) -> ResumenCobro:
    """
    Arma el total a cobrar, lo pagado y el saldo de una orden.

    Args:
        orden: OrdenServicio (idealmente con cotizacion, venta_mostrador y pagos).
        codigo_pais: Override opcional ('MX', 'AR', …) para tests.

    Returns:
        ResumenCobro con todos los importes ya redondeados.

    Efectos secundarios:
        Lee BD (piezas, pagos, venta mostrador). No escribe.
    """
    subtotal, es_estimado = _subtotal_cotizacion(orden)

    # Paso: IVA 16% solo en México, igual que el PDF que ve el cliente.
    codigo = _codigo_pais_activo(codigo_pais)
    aplica_iva = codigo == 'MX'
    tasa = IVA_TASA_MX if aplica_iva else Decimal('0.00')
    iva = _dinero(subtotal * tasa) if aplica_iva else Decimal('0.00')

    venta = getattr(orden, 'venta_mostrador', None)
    total_vm = _dinero(venta.total_venta) if venta is not None else Decimal('0.00')

    total = _dinero(subtotal + iva + total_vm)

    # Paso: suma de abonos ya capturados (si no hay, 0).
    agregado = orden.pagos.aggregate(total=Sum('monto'))['total']
    pagado = _dinero(agregado or Decimal('0.00'))

    saldo = _dinero(total - pagado)
    if saldo < 0:
        saldo = Decimal('0.00')

    if total > 0:
        porcentaje = _dinero((pagado / total) * Decimal('100'))
        anticipo_minimo = _dinero(total * Decimal('0.50'))
        cubre_50 = pagado >= anticipo_minimo
        cubierto = saldo <= Decimal('0.00')
    else:
        porcentaje = Decimal('0.00')
        anticipo_minimo = Decimal('0.00')
        cubre_50 = True
        cubierto = True

    return ResumenCobro(
        subtotal_cotizacion=subtotal,
        iva_cotizacion=iva,
        total_venta_mostrador=total_vm,
        total_a_cobrar=total,
        pagado=pagado,
        saldo=saldo,
        porcentaje_pagado=porcentaje,
        anticipo_minimo=anticipo_minimo,
        cubre_anticipo_50=cubre_50,
        cubierto_100=cubierto,
        es_estimado=es_estimado,
        aplica_iva=aplica_iva,
        tasa_iva=tasa,
    )


def usuario_puede_registrar_pago(user: Optional[AbstractBaseUser]) -> bool:
    """
    True si el usuario puede capturar un abono (permiso add_pagoorden).

    Args:
        user: request.user o None.

    Returns:
        bool: superuser siempre sí; el resto según el Group de Django.
    """
    if user is None or not getattr(user, 'is_authenticated', False):
        return False
    return user.has_perm(PERMISO_REGISTRAR_PAGO)


def _comprimir_comprobante(imagen_file) -> ContentFile:
    """
    Comprime el comprobante a JPEG (corrige EXIF, baja peso).

    Args:
        imagen_file: archivo subido (InMemoryUploadedFile / UploadedFile).

    Returns:
        ContentFile listo para asignar a PagoOrden.comprobante.

    Efectos secundarios:
        Lee el archivo en memoria; no toca disco todavía.
    """
    try:
        imagen_file.seek(0)
        img = Image.open(imagen_file)
        img = ImageOps.exif_transpose(img)

        # Paso: JPEG no soporta transparencia; fondo blanco si viene PNG.
        if img.mode in ('RGBA', 'LA', 'P'):
            fondo = Image.new('RGB', img.size, (255, 255, 255))
            mascara = img.split()[-1] if img.mode == 'RGBA' else None
            fondo.paste(img, mask=mascara)
            img = fondo
        elif img.mode != 'RGB':
            img = img.convert('RGB')

        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=82, optimize=True)
        buffer.seek(0)
        return ContentFile(buffer.read(), name='comprobante.jpg')
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        # EXPLICACIÓN: un .jpg corrupto pasa la extensión pero Pillow no
        # puede abrirlo. Devolvemos error de formulario, no un 500.
        raise ValidationError(
            'El comprobante no es una imagen válida. Sube un JPG o PNG nítido.'
        ) from exc


def registrar_pago(
    orden,
    empleado,
    monto,
    tipo: str,
    metodo: str,
    notas: str = '',
    comprobante_file=None,
    codigo_pais: Optional[str] = None,
):
    """
    Crea un PagoOrden, opcionalmente con foto, y lo anota en el historial.

    Args:
        orden: OrdenServicio destino.
        empleado: Empleado que captura (obligatorio).
        monto: Decimal o string del abono.
        tipo: clave de PagoOrden.TIPO_PAGO_CHOICES.
        metodo: clave de PagoOrden.METODO_PAGO_CHOICES.
        notas: texto corto opcional.
        comprobante_file: archivo de imagen o None.
        codigo_pais: override de país para el cálculo de saldo.

    Returns:
        PagoOrden recién creado.

    Efectos secundarios:
        Inserta PagoOrden, escribe media/ si hay foto, crea HistorialOrden.

    Raises:
        ValidationError: monto inválido o mayor al saldo pendiente.
    """
    from servicio_tecnico.models import OrdenServicio, PagoOrden

    if empleado is None:
        raise ValidationError('Se necesita un empleado para registrar el pago.')

    monto_dec = _dinero(monto)
    if monto_dec <= Decimal('0.00'):
        raise ValidationError('El monto del pago debe ser mayor a cero.')

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # atomic(using=la BD de ESTA orden) + select_for_update: si dos
    # personas cobran a la vez, la segunda espera y vuelve a leer el saldo.
    # using= es obligatorio por el router multi-país (ver _db_de).
    db_alias = _db_de(orden)
    with transaction.atomic(using=db_alias):
        orden_bloqueada = (
            OrdenServicio.objects.using(db_alias)
            .select_for_update()
            .get(pk=orden.pk)
        )
        resumen = calcular_resumen_cobro(orden_bloqueada, codigo_pais=codigo_pais)

        # Paso: sin cotización ni venta no hay cifra contra la cual abonar.
        if resumen.total_a_cobrar <= Decimal('0.00'):
            raise ValidationError(
                'No hay un total a cobrar todavía. Genera la cotización '
                'o una venta mostrador antes de registrar un pago.'
            )

        if monto_dec > resumen.saldo:
            raise ValidationError(
                f'El pago (${monto_dec}) supera el saldo pendiente '
                f'(${resumen.saldo}).'
            )

        pago = PagoOrden(
            orden=orden_bloqueada,
            monto=monto_dec,
            tipo=tipo,
            metodo=metodo,
            notas=(notas or '').strip(),
            registrado_por=empleado,
        )
        if comprobante_file:
            pago.comprobante = _comprimir_comprobante(comprobante_file)
        pago.save()

        registrar_historial(
            orden=orden_bloqueada,
            tipo_evento='sistema',
            usuario=empleado,
            comentario=(
                f'Pago registrado: ${monto_dec} ({pago.get_tipo_display()}, '
                f'{pago.get_metodo_display()}).'
            ),
            es_sistema=True,
        )
    return pago


def eliminar_pago(pago, empleado) -> None:
    """
    Borra un abono capturado por error y lo deja en el historial.

    Args:
        pago: PagoOrden a eliminar.
        empleado: quién lo borra (para el historial).

    Efectos secundarios:
        DELETE del pago (y archivo de comprobante) + HistorialOrden.
    """
    if empleado is None:
        raise ValidationError('Se necesita un empleado para eliminar el pago.')

    orden = pago.orden
    monto = pago.monto
    db_alias = _db_de(pago)
    with transaction.atomic(using=db_alias):
        pago.delete()
        registrar_historial(
            orden=orden,
            tipo_evento='sistema',
            usuario=empleado,
            comentario=f'Pago eliminado (corrección): ${monto}.',
            es_sistema=True,
        )


def mensaje_alerta_pago_por_estado(orden, nuevo_estado: str) -> Optional[str]:
    """
    Texto de alerta si el nuevo estado no cuadra con lo pagado.

    No bloquea el cambio: solo avisa (anticipo 50% / liquidación 100%).

    Args:
        orden: OrdenServicio (se recalcula el resumen).
        nuevo_estado: código de ESTADO_ORDEN_CHOICES.

    Returns:
        str para messages.warning, o None si no hay que avisar.
    """
    resumen = calcular_resumen_cobro(orden)
    if resumen.total_a_cobrar <= 0:
        return None

    if (
        nuevo_estado in ESTADOS_REQUIEREN_ANTICIPO_50
        and not resumen.cubre_anticipo_50
    ):
        return (
            f'El cliente aún no cubre el anticipo del 50% '
            f'(pagado ${resumen.pagado} de ${resumen.anticipo_minimo} '
            f'mínimo). Puedes continuar, pero coordina el cobro.'
        )

    if nuevo_estado == 'entregado' and not resumen.cubierto_100:
        return (
            f'Hay saldo pendiente (${resumen.saldo} de '
            f'${resumen.total_a_cobrar}). El equipo se puede entregar, '
            f'pero el cliente aún debe.'
        )
    return None
