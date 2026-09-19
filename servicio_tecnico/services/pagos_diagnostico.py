"""
El diagnóstico como servicio cobrable y facturable (PUE).

Objetivo de negocio:
    El diagnóstico (lo que en SIGMA se llama "mano de obra") es un servicio
    que el cliente paga completo, aunque después rechace la reparación. Esa
    es exactamente la definición de PUE: pago en una sola exhibición.

EXPLICACIÓN PARA PRINCIPIANTES — por qué este archivo existe:
    `pagos_orden.py` calcula el saldo de la REPARACIÓN (piezas + venta
    mostrador) y a propósito deja fuera el diagnóstico. Pero para facturar
    necesitamos saber cuánto vale el diagnóstico y si ya está pagado. Ese
    cálculo vive aquí, separado, para no mezclar los dos bolsillos.

    Además Contabilidad pidió poder verificar el importe: el diagnóstico
    debería costar lo que marca el tarifario según la gama del equipo
    (baja/media/alta). Aquí comparamos lo capturado contra esa referencia y
    avisamos si no cuadra — pero NUNCA cambiamos el monto solo. El dinero que
    se factura es el que Recepción capturó, no el que nosotros supongamos.

Efectos secundarios:
    Solo lectura de BD. El alta de pagos sigue siendo de pagos_orden.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Sum

CENTAVO = Decimal('0.01')
TIPO_PAGO_DIAGNOSTICO = 'diagnostico'

# Estados de validación que Facturación considera "el dinero ya es nuestro".
# 'no_aplica' es efectivo cobrado en caja; 'validado' es transferencia vista
# en el estado de cuenta. Los dos habilitan la factura.
ESTADOS_PAGO_CONFIRMADO = ('validado', 'no_aplica')

# Gama del equipo (DetalleEquipo.gama) → perfil del tarifario del cotizador.
#
# ⚠️ RESPALDO (Septiembre 2026): desde que existe OrdenServicio.perfil_diagnostico
# la orden dice explícitamente qué diagnóstico se cobró, y ese perfil manda.
# Este mapa solo se usa en órdenes viejas, capturadas cuando el monto se tecleaba
# libre y no había forma de saber qué servicio era. Adivinar por gama es peor
# que preguntar, pero mejor que no tener referencia alguna.
PERFIL_TARIFARIO_POR_GAMA = {
    'baja': 'estandar',
    'media': 'estandar',
    'alta': 'alta_gama',
}
PERFIL_TARIFARIO_DEFAULT = 'estandar'

# Textos que van al CFDI. El SAT pide descripción clara del servicio.
DESCRIPCION_DIAGNOSTICO = 'Diagnóstico'
DESCRIPCION_MANTENIMIENTO = 'Limpieza y Mantenimiento'


def _dinero(valor) -> Decimal:
    """Redondea a 2 decimales como un cajero (0.005 sube a 0.01)."""
    return Decimal(valor or 0).quantize(CENTAVO, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ResumenDiagnostico:
    """
    Foto del diagnóstico de una orden: cuánto vale, cuánto pagaron y si cuadra.

    EXPLICACIÓN PARA PRINCIPIANTES — los dos montos y por qué son distintos:
        `monto` es el precio del servicio SIN IVA ($570). Es el que va al CFDI,
        porque el SAT pide el valor antes de impuestos.
        `monto_con_iva` es lo que el cliente entrega en caja ($661.20). Es el
        que se compara contra los pagos, porque un comprobante de transferencia
        dice 661.20, no 570.
        Confundirlos es justo lo que provocaba que no se pudiera cobrar el
        diagnóstico: el sistema pedía 570 cuando en la práctica entraban 661.20.

    Args/campos:
        monto: precio del diagnóstico SIN IVA (mano de obra ya con el descuento
            aplicado si el cliente aceptó la cotización).
        iva: impuesto sobre ese monto ($0.00 fuera de México).
        monto_con_iva: total que el cliente debe cubrir en caja.
        pagado: suma de abonos tipo 'diagnostico' ya capturados (con IVA).
        pagado_confirmado: de esos abonos, los que Facturación ya dio por
            buenos (validado o no_aplica).
        saldo: monto_con_iva − pagado (nunca negativo), en pesos reales.
        cubierto_100: True si ya no debe nada de diagnóstico.
        confirmado_100: True y además el dinero está verificado → se factura.
        tarifa_referencia: lo que dice el tarifario para este diagnóstico
            (sin IVA, para comparar contra `monto`).
        gama: gama del equipo ('baja', 'media', 'alta') o ''.
        perfil: tipo de diagnóstico elegido ('estandar', 'alta_gama'…) o ''
            en órdenes viejas con monto capturado a mano.
        coincide_con_tarifario: True si monto == tarifa de referencia.
    """

    monto: Decimal
    iva: Decimal
    monto_con_iva: Decimal
    pagado: Decimal
    pagado_confirmado: Decimal
    saldo: Decimal
    cubierto_100: bool
    confirmado_100: bool
    tarifa_referencia: Decimal
    gama: str
    perfil: str
    coincide_con_tarifario: bool


def monto_diagnostico(orden) -> Decimal:
    """
    Cuánto se cobra por el diagnóstico de esta orden.

    EXPLICACIÓN PARA PRINCIPIANTES:
    La mano de obra vive en dos lugares. En `OrdenServicio.costo_mano_obra`
    desde que el técnico la captura, y se copia a `Cotizacion.costo_mano_obra`
    cuando se genera la cotización. La cotización manda porque ahí también
    vive el descuento: si el cliente acepta la reparación, el negocio puede
    regalar el diagnóstico (`descontar_mano_obra`) y entonces vale $0.

    Args:
        orden: OrdenServicio.

    Returns:
        Decimal con 2 decimales. $0.00 significa "no hay diagnóstico que
        cobrar" (gratis por promoción o todavía no capturado).

    Efectos secundarios:
        Lee la cotización si existe. No escribe.
    """
    cotizacion = getattr(orden, 'cotizacion', None)
    # Paso 1: con cotización usamos el monto ya "aplicado" (respeta descuento).
    if cotizacion is not None:
        return _dinero(cotizacion.costo_mano_obra_aplicado)
    # Paso 2: sin cotización, la orden es la única fuente.
    return _dinero(getattr(orden, 'costo_mano_obra', Decimal('0.00')))


def _gama_de(orden) -> str:
    """Gama del equipo ('baja'/'media'/'alta') o '' si no hay detalle."""
    try:
        return (orden.detalle_equipo.gama or '').strip().lower()
    except ObjectDoesNotExist:
        return ''


def tarifa_diagnostico_por_gama(gama: str) -> Decimal:
    """
    Precio de lista del diagnóstico deducido de la gama del equipo (respaldo).

    Objetivo: dar a Contabilidad un número contra el cual comparar cuando la
    orden NO trae perfil de diagnóstico capturado. Sale del mismo tarifario que
    usa el cotizador (panel gerencial con respaldo .env), así que si Presidencia
    cambia el precio, aquí cambia solo.

    Args:
        gama: 'baja', 'media' o 'alta'.

    Returns:
        Decimal con la tarifa. $0.00 si el tarifario no está disponible
        (en ese caso simplemente no verificamos nada).

    Efectos secundarios:
        Lee la configuración de profit (BD del tenant + .env).
    """
    perfil = PERFIL_TARIFARIO_POR_GAMA.get(
        (gama or '').strip().lower(),
        PERFIL_TARIFARIO_DEFAULT,
    )
    # Import diferido: el catálogo importa Almacén y no queremos ciclos al cargar.
    from servicio_tecnico.services.diagnostico_catalogo import tarifa_perfil

    return tarifa_perfil(perfil)


def _perfil_de(orden) -> str:
    """Tipo de diagnóstico elegido en la orden, o '' si es una orden vieja."""
    return (getattr(orden, 'perfil_diagnostico', '') or '').strip()


def tarifa_diagnostico(orden) -> Decimal:
    """
    Precio de lista contra el que Contabilidad verifica esta orden.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Hay dos caminos y el orden importa:
      1. Si la orden dice qué diagnóstico se cobró (perfil), usamos ESE precio.
         Es un dato, no una suposición, y siempre está sin IVA.
      2. Si no lo dice (orden anterior al catálogo), deducimos el perfil desde
         la gama del equipo. Es aproximado y por eso es el último recurso.

    Args:
        orden: OrdenServicio.

    Returns:
        Decimal con la tarifa de referencia, o $0.00 si no hay forma de saberla.

    Efectos secundarios:
        Lee la configuración de profit (BD del tenant + .env).
    """
    perfil = _perfil_de(orden)
    if perfil:
        from servicio_tecnico.services.diagnostico_catalogo import tarifa_perfil

        return tarifa_perfil(perfil)
    return tarifa_diagnostico_por_gama(_gama_de(orden))


def _pagos_diagnostico(orden):
    """QuerySet de abonos tipo 'diagnostico' de la orden."""
    return orden.pagos.filter(tipo=TIPO_PAGO_DIAGNOSTICO)


def iva_diagnostico(monto_sin_iva: Decimal, codigo_pais: Optional[str] = None) -> Decimal:
    """
    IVA que le toca al diagnóstico según el país de la orden.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El 16% es de México. Las demás operaciones del grupo no lo cobran, así que
    preguntamos por el país igual que lo hace el resumen de cobro de piezas
    (`calcular_resumen_cobro`), para no inventar una regla distinta.

    Args:
        monto_sin_iva: precio del servicio antes de impuestos.
        codigo_pais: override del país (útil en tests).

    Returns:
        Decimal con el impuesto; $0.00 fuera de México.

    Efectos secundarios:
        Lee el país activo del request/thread-local.
    """
    from servicio_tecnico.services.pagos_orden import (
        IVA_TASA_MX,
        _codigo_pais_activo,
    )

    if _codigo_pais_activo(codigo_pais) != 'MX':
        return Decimal('0.00')
    return _dinero(_dinero(monto_sin_iva) * IVA_TASA_MX)


def resumen_diagnostico(orden, codigo_pais: Optional[str] = None) -> ResumenDiagnostico:
    """
    Calcula todo lo que hay que saber del diagnóstico de una orden.

    Args:
        orden: OrdenServicio (idealmente con cotizacion y pagos precargados).
        codigo_pais: override del país para el IVA (útil en tests).

    Returns:
        ResumenDiagnostico listo para la UI y para decidir si hay factura PUE.

    Efectos secundarios:
        Dos agregados sobre PagoOrden. No escribe.
    """
    monto = monto_diagnostico(orden)

    # Paso 1: el cliente paga el servicio MÁS su IVA. Este es el número que
    # debe aparecer en el recibo y contra el que se comparan los abonos.
    iva = iva_diagnostico(monto, codigo_pais=codigo_pais)
    monto_con_iva = _dinero(monto + iva)

    # Paso 2: cuánto ha entrado por diagnóstico, en total y ya verificado.
    pagos = _pagos_diagnostico(orden)
    pagado = _dinero(pagos.aggregate(total=Sum('monto'))['total'])
    pagado_confirmado = _dinero(
        pagos.filter(estado_validacion__in=ESTADOS_PAGO_CONFIRMADO)
        .aggregate(total=Sum('monto'))['total']
    )

    # Paso 3: saldo nunca negativo (si cobraron de más, es cero, no crédito).
    # Se mide contra el total CON IVA porque los pagos son dinero real de caja.
    saldo = _dinero(monto_con_iva - pagado)
    if saldo < 0:
        saldo = Decimal('0.00')

    # Paso 4: para facturar PUE exigimos las dos cosas: que esté cubierto
    # al 100% y que el dinero ya esté verificado por Facturación.
    hay_cobro = monto > Decimal('0.00')
    cubierto = hay_cobro and pagado >= monto_con_iva
    confirmado = hay_cobro and pagado_confirmado >= monto_con_iva

    # Paso 4: comparación contra el tarifario (solo informativa). Con perfil
    # capturado esto debería coincidir siempre, porque el monto se calculó
    # desde el mismo tarifario; si no coincide, es que la tarifa cambió
    # después de cobrar, y eso es justo lo que Contabilidad quiere ver.
    gama = _gama_de(orden)
    perfil = _perfil_de(orden)
    tarifa = tarifa_diagnostico(orden)
    coincide = bool(tarifa > 0 and monto == tarifa)

    return ResumenDiagnostico(
        monto=monto,
        iva=iva,
        monto_con_iva=monto_con_iva,
        pagado=pagado,
        pagado_confirmado=pagado_confirmado,
        saldo=saldo,
        cubierto_100=cubierto,
        confirmado_100=confirmado,
        tarifa_referencia=tarifa,
        gama=gama,
        perfil=perfil,
        coincide_con_tarifario=coincide,
    )


def validar_monto_pago_diagnostico(orden, monto: Decimal) -> None:
    """
    Revisa que un abono de diagnóstico quepa dentro de la mano de obra.

    Args:
        orden: OrdenServicio ya bloqueada por el llamador.
        monto: importe del abono que se quiere registrar.

    Raises:
        ValidationError: si no hay mano de obra capturada o si el abono
        supera lo que falta por pagar del diagnóstico.

    Efectos secundarios:
        Ninguno (solo lectura). Lo llama registrar_pago dentro de su
        transacción, por eso aquí no abrimos otra.
    """
    resumen = resumen_diagnostico(orden)

    if resumen.monto <= Decimal('0.00'):
        raise ValidationError(
            'Esta orden no tiene mano de obra capturada. Registra el costo '
            'del diagnóstico antes de cobrarlo.'
        )

    # Paso: el techo es el total CON IVA, que es lo que el cliente entrega.
    # Si el mensaje solo dijera "supera el saldo", quien cobra pensaría que
    # el monto correcto es el del servicio sin impuesto, que es precisamente
    # el error que hacía imposible registrar este cobro.
    if monto > resumen.saldo:
        raise ValidationError(
            f'El pago de diagnóstico (${monto}) supera lo que falta por '
            f'cubrir (${resumen.saldo}). El diagnóstico cuesta '
            f'${resumen.monto} + ${resumen.iva} de IVA = '
            f'${resumen.monto_con_iva}.'
        )


def descripcion_servicio_diagnostico(orden) -> str:
    """
    Texto del concepto que irá en la factura PUE.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El SAT quiere saber qué se vendió. Si la orden es una venta mostrador con
    limpieza, el servicio real fue "Limpieza y Mantenimiento"; en cualquier
    otro caso el cliente pagó un "Diagnóstico".

    Args:
        orden: OrdenServicio.

    Returns:
        str: 'Diagnóstico' o 'Limpieza y Mantenimiento'.
    """
    venta = getattr(orden, 'venta_mostrador', None)
    # Paso: la bandeja de limpieza de venta mostrador manda sobre el default.
    if venta is not None and getattr(venta, 'incluye_limpieza', False):
        return DESCRIPCION_MANTENIMIENTO
    return DESCRIPCION_DIAGNOSTICO


def orden_en_garantia(orden) -> bool:
    """
    True si la orden está DENTRO de garantía y por lo tanto no se autofactura.

    EXPLICACIÓN PARA PRINCIPIANTES:
    En una orden de garantía el cliente no paga: responde el fabricante. Sin
    cobro no hay CFDI que emitir, así que el autofacturador ni siquiera debe
    mostrar el botón.

    SIGMA ya distingue esto solo: `OrdenServicio.es_fuera_garantia` se pone en
    True automáticamente cuando el folio del cliente empieza con OOW- o FL-
    (ver DetalleEquipo.save()). Fuera de garantía = sí factura.

    Args:
        orden: OrdenServicio.

    Returns:
        bool: True si NO aplica autofacturación por ser garantía.
    """
    return not bool(getattr(orden, 'es_fuera_garantia', False))
