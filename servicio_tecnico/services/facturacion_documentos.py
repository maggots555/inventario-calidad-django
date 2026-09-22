"""
Construcción de los documentos facturables PUE y PPD de una orden.

Objetivo de negocio:
    Decidir qué puede facturar el cliente en el portal VO y por cuánto.
    Lo decide el pago, no el tipo de servicio:

    * webId -1 (pue) — el diagnóstico cubierto al 100% y ya validado.
    * webId -3 (pue_rep) — la reparación o los servicios pagados en una
      sola exhibición, cuando ese dinero ya cubre el total y está validado.
    * webId -2 (ppd) — el anticipo de la reparación, desde el primer peso
      validado. Una sola línea, "Anticipo del bien o servicio".

EXPLICACIÓN PARA PRINCIPIANTES — ¿cuándo nace un documento?
    Cuando el dinero ya es de la empresa. No basta con que Recepción capture
    el cobro: si fue transferencia o tarjeta, Facturación tiene que haberlo
    visto en el estado de cuenta (`estado_validacion='validado'`). El efectivo
    entra directo porque nace como `no_aplica`. Hasta entonces el cliente no
    ve su webId y el portal no encuentra nada que timbrar.

CRITICAL — mientras no esté timbrado, el documento se recalcula:
    Si alguien corrige un precio, el documento se actualiza solo. En cuanto
    llega el UUID del SAT (PUT de VO) se congela para siempre: una factura
    timbrada ya no se toca.

Efectos secundarios:
    Crea y actualiza DocumentoFiscalOrden y sus ConceptoDocumentoFiscal,
    dentro de una transacción abierta en la BD del país de la orden.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from servicio_tecnico.models_facturacion import (
    ConceptoDocumentoFiscal,
    DocumentoFiscalOrden,
)
from servicio_tecnico.services.facturacion_web_id import construir_web_id
from servicio_tecnico.services.pagos_diagnostico import (
    ESTADOS_PAGO_CONFIRMADO,
    descripcion_servicio_diagnostico,
    orden_en_garantia,
    resumen_diagnostico,
)
from servicio_tecnico.services.pagos_orden import (
    IVA_TASA_MX,
    SALDO_DIAGNOSTICO,
    SALDO_REPARACION,
    TIPO_ANTICIPO,
    TIPO_PAGO_COMPLETO,
    _db_de,
    calcular_resumen_cobro,
)

CENTAVO = Decimal('0.01')

# Claves del catálogo del SAT. Cada servicio lleva la suya: una sola clave
# genérica facturaba el diagnóstico como si fuera limpieza.
# E48 = unidad de servicio.
CLAVE_UNIDAD_SERVICIO = 'E48'
CLAVE_SAT_DIAGNOSTICO = '81111820'
# Instalación / cambio de pieza sin diagnóstico.
CLAVE_SAT_INSTALACION_PARTES = '81111814'
CLAVE_SAT_LIMPIEZA = '72151800'
CLAVE_SAT_REINSTALACION_SO = '81111505'
CLAVE_SAT_RESPALDO = '81112218'
# Oro, plata, premium y el kit de limpieza: equipo, no servicio de diagnóstico.
CLAVE_SAT_PAQUETE = '43211600'
CLAVE_SAT_KIT = '43211600'
# 84111506 = servicios de facturación/anticipos. ACT = actividad.
CLAVE_SAT_ANTICIPO = '84111506'
CLAVE_UNIDAD_ANTICIPO = 'ACT'
# 01010101 = "no existe en el catálogo". Se usa cuando el producto de
# almacén todavía no tiene su ClaveProdServ. H87 = pieza.
CLAVE_SAT_MERCANCIA = '01010101'
CLAVE_UNIDAD_PIEZA = 'H87'

DESCRIPCION_ANTICIPO = 'Anticipo del bien o servicio'


def _dinero(valor) -> Decimal:
    """Redondea a 2 decimales como un cajero (0.005 sube a 0.01)."""
    return Decimal(valor or 0).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _sin_iva(monto_con_iva: Decimal) -> Decimal:
    """
    Quita el IVA a un importe que ya lo trae dentro.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Los montos de venta mostrador en SIGMA se capturan con IVA incluido (lo
    que el cliente pagó en caja). El CFDI pide el precio ANTES de IVA, así que
    dividimos entre 1.16 en lugar de restar un 16% (que daría otro número).
    """
    monto = _dinero(monto_con_iva)
    if monto <= 0:
        return Decimal('0.00')
    return _dinero(monto / (Decimal('1') + IVA_TASA_MX))


@dataclass
class LineaFacturable:
    """
    Una línea candidata a concepto del CFDI, ya sin IVA.

    Args/campos:
        descripcion: texto que verá el cliente.
        importe: total de la línea antes de IVA.
        cantidad: piezas/servicios (normalmente 1).
        clave_sat / clave_unidad: catálogos del SAT. El default es solo el
        diagnóstico; el resto de las líneas debe pasar su clave.
    """

    descripcion: str
    importe: Decimal
    cantidad: Decimal = Decimal('1.00')
    clave_sat: str = CLAVE_SAT_DIAGNOSTICO
    clave_unidad: str = CLAVE_UNIDAD_SERVICIO


def aplica_autofacturacion(orden) -> bool:
    """
    Dice si esta orden puede pasar por el autofacturador.

    Reglas de negocio (todas se deben cumplir):
        1. No está cancelada ni rechazada.
        2. Está FUERA de garantía (dentro de garantía el cliente no paga).
        3. Su sucursal tiene prefijo de facturación capturado.
        4. Tiene folio de cliente con dígitos.

    Args:
        orden: OrdenServicio.

    Returns:
        bool

    Efectos secundarios:
        Lee sucursal y detalle del equipo. No escribe.
    """
    if orden.estado in ('cancelado', 'rechazada'):
        return False
    # Paso: garantía nunca se autofactura (lo confirmó el negocio).
    if orden_en_garantia(orden):
        return False
    # Paso: sin prefijo o sin folio no hay webId que darle al cliente.
    return bool(construir_web_id(orden, DocumentoFiscalOrden.TIPO_PUE))


def _suma_confirmada(orden, saldo: str, tipo: str) -> Decimal:
    """
    Dinero ya validado de un bolsillo y un tipo de pago.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El diagnóstico no se suma con la reparación, y un anticipo no se suma
    con un pago de contado. Cada factura lee solo su cajón.

    Args:
        orden: OrdenServicio.
        saldo: 'diagnostico' o 'reparacion'.
        tipo: 'anticipo' o 'pago_completo'.

    Returns:
        Decimal con 2 decimales. $0.00 si todavía no hay nada validado.
    """
    agregado = (
        orden.pagos.filter(
            saldo_a_cubrir=saldo,
            tipo=tipo,
            estado_validacion__in=ESTADOS_PAGO_CONFIRMADO,
        )
        .aggregate(total=Sum('monto'))['total']
    )
    return _dinero(agregado)


def pagos_confirmados_del_documento(orden, tipo_documento: str):
    """
    Abonos validados que respaldan un documento fiscal.

    Sirve para la forma de pago del CFDI: el diagnóstico en débito no debe
    cambiar la clave del anticipo que entró por transferencia.

    Args:
        orden: OrdenServicio.
        tipo_documento: DocumentoFiscalOrden.TIPO_PUE, TIPO_PUE_REPARACION
            o TIPO_PPD.

    Returns:
        QuerySet de PagoOrden. Vacío si el tipo no se reconoce.
    """
    base = orden.pagos.filter(estado_validacion__in=ESTADOS_PAGO_CONFIRMADO)
    if tipo_documento == DocumentoFiscalOrden.TIPO_PUE:
        return base.filter(saldo_a_cubrir=SALDO_DIAGNOSTICO)
    if tipo_documento == DocumentoFiscalOrden.TIPO_PUE_REPARACION:
        return base.filter(
            saldo_a_cubrir=SALDO_REPARACION,
            tipo=TIPO_PAGO_COMPLETO,
        )
    if tipo_documento == DocumentoFiscalOrden.TIPO_PPD:
        return base.filter(
            saldo_a_cubrir=SALDO_REPARACION,
            tipo=TIPO_ANTICIPO,
        )
    return base.none()


def _lineas_servicios_venta_mostrador(orden) -> list[LineaFacturable]:
    """
    Servicios de venta mostrador como líneas sin IVA.

    Objetivo: cada servicio sale con su ClaveProdServ (limpieza, respaldo,
    instalación de partes, paquete, kit). Las piezas vendidas en mostrador
    NO entran aquí.

    Args:
        orden: OrdenServicio.

    Returns:
        list[LineaFacturable] (vacía si no hay venta mostrador).
    """
    venta = getattr(orden, 'venta_mostrador', None)
    if venta is None:
        return []

    lineas: list[LineaFacturable] = []

    def agregar(descripcion: str, monto_con_iva, clave_sat: str) -> None:
        """Suma una línea solo si el servicio tiene costo y su clave SAT."""
        importe = _sin_iva(monto_con_iva)
        if importe > 0:
            lineas.append(LineaFacturable(
                descripcion=descripcion,
                importe=importe,
                clave_sat=clave_sat,
            ))

    # Paso 1: oro, plata y premium comparten la clave de equipo, no la del diagnóstico.
    if venta.paquete and venta.paquete != 'ninguno':
        agregar(
            f'Paquete {venta.get_paquete_display()}',
            venta.costo_paquete,
            CLAVE_SAT_PAQUETE,
        )

    # Paso 2: cada servicio suelto lleva la ClaveProdServ que pidió Contabilidad.
    if venta.incluye_limpieza:
        agregar('Limpieza y Mantenimiento', venta.costo_limpieza, CLAVE_SAT_LIMPIEZA)
    if venta.incluye_reinstalacion_so:
        agregar(
            'Reinstalación de sistema operativo',
            venta.costo_reinstalacion,
            CLAVE_SAT_REINSTALACION_SO,
        )
    if venta.incluye_respaldo:
        agregar('Respaldo de información', venta.costo_respaldo, CLAVE_SAT_RESPALDO)
    if venta.incluye_cambio_pieza:
        agregar(
            'Cambio de pieza (mano de obra)',
            venta.costo_cambio_pieza,
            CLAVE_SAT_INSTALACION_PARTES,
        )

    # Paso 3: el kit es mercancía (unidad H87), con la clave de equipo.
    # No hereda la del diagnóstico ni la genérica de pieza sin catálogo.
    if venta.incluye_kit_limpieza:
        linea_kit = _linea_si_hay_importe(
            'Kit de limpieza',
            _sin_iva(venta.costo_kit),
            Decimal('1'),
            CLAVE_SAT_KIT,
            CLAVE_UNIDAD_PIEZA,
        )
        if linea_kit is not None:
            lineas.append(linea_kit)

    return lineas


def _clave_mercancia(producto) -> tuple[str, str]:
    """
    Clave SAT de una mercancía y su unidad.

    EXPLICACIÓN PARA PRINCIPIANTES:
    La clave vive en el producto de almacén. Si todavía no la capturaron,
    no detenemos la factura: usamos la clave genérica del SAT.

    Args:
        producto: ProductoAlmacen o None.

    Returns:
        tuple (clave de 8 dígitos, unidad H87).
    """
    clave = (getattr(producto, 'clave_sat', '') or '').strip()
    if len(clave) == 8 and clave.isdigit():
        return clave, CLAVE_UNIDAD_PIEZA
    return CLAVE_SAT_MERCANCIA, CLAVE_UNIDAD_PIEZA


def _linea_si_hay_importe(
    descripcion: str,
    importe,
    cantidad,
    clave_sat: str,
    clave_unidad: str,
) -> Optional[LineaFacturable]:
    """
    Arma una línea solo cuando el importe neto es mayor a cero.

    Args:
        descripcion: texto del concepto, ya recortado.
        importe: total de la línea antes de IVA.
        cantidad: unidades.
        clave_sat / clave_unidad: catálogos del SAT.

    Returns:
        LineaFacturable o None.
    """
    neto = _dinero(importe)
    if neto <= 0:
        return None
    piezas = Decimal(cantidad or 1)
    if piezas <= 0:
        piezas = Decimal('1')
    return LineaFacturable(
        descripcion=descripcion[:200],
        importe=neto,
        cantidad=piezas,
        clave_sat=clave_sat,
        clave_unidad=clave_unidad,
    )


def _cuadrar_centavos(lineas: list[LineaFacturable], neto_pagado: Decimal) -> list[LineaFacturable]:
    """
    Ajusta la última línea si el redondeo deja uno o dos centavos.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Cada línea se redondea sola. Al sumarlas, a veces el CFDI queda un
    centavo arriba o abajo de lo que realmente se pagó. Ese centavo se
    recorre a la última línea para que el total timbrado sea el de caja.
    Una diferencia grande no se esconde: ahí el catálogo y el pago no
    están diciendo lo mismo.

    Args:
        lineas: conceptos ya calculados.
        neto_pagado: lo cobrado, ya sin IVA.

    Returns:
        La misma lista, con la última línea corregida si hizo falta.
    """
    if not lineas:
        return lineas
    suma = _dinero(sum((linea.importe for linea in lineas), Decimal('0.00')))
    diferencia = _dinero(neto_pagado - suma)
    if diferencia == 0 or abs(diferencia) > Decimal('0.05'):
        return lineas
    # Paso: solo movemos el centavo en una línea de cantidad 1. Si la
    # cantidad es 2 o más, precio × cantidad dejaría de cuadrar con el
    # importe y el SAT puede rechazar el timbrado.
    indice = next(
        (
            pos for pos in range(len(lineas) - 1, -1, -1)
            if lineas[pos].cantidad == Decimal('1') or lineas[pos].cantidad == Decimal('1.00')
        ),
        None,
    )
    if indice is None:
        return lineas
    ultima = lineas[indice]
    nuevo = _dinero(ultima.importe + diferencia)
    if nuevo <= 0:
        return lineas
    lineas[indice] = LineaFacturable(
        descripcion=ultima.descripcion,
        importe=nuevo,
        cantidad=ultima.cantidad,
        clave_sat=ultima.clave_sat,
        clave_unidad=ultima.clave_unidad,
    )
    return lineas


def _lineas_piezas_cotizadas(orden) -> list[LineaFacturable]:
    """
    Una línea por pieza aceptada de la cotización, precio ya sin IVA.

    Args:
        orden: OrdenServicio.

    Returns:
        list[LineaFacturable]. Vacía si no hay cotización o fue rechazada.
    """
    cotizacion = getattr(orden, 'cotizacion', None)
    if cotizacion is None or cotizacion.usuario_acepto is False:
        return []
    if cotizacion.usuario_acepto:
        piezas = cotizacion.piezas_cotizadas.filter(aceptada_por_cliente=True)
    else:
        piezas = cotizacion.piezas_cotizadas.all()
    piezas = piezas.select_related(
        'componente',
        'linea_cotizacion_almacen__producto',
    )

    lineas: list[LineaFacturable] = []
    for pieza in piezas:
        # Paso: el precio al cliente ya está sin IVA. Si una pieza vieja
        # no lo tiene, usamos el costo (el mismo respaldo del saldo).
        if pieza.precio_unitario_cliente is not None:
            importe = pieza.cantidad * pieza.precio_unitario_cliente
        else:
            importe = pieza.costo_total
        nombre = pieza.componente.nombre if pieza.componente_id else 'Pieza'
        extra = (pieza.descripcion_adicional or '').strip()
        if extra and extra.lower() not in nombre.lower():
            descripcion = f'{nombre} — {extra}'
        else:
            descripcion = nombre
        producto = None
        linea_almacen = getattr(pieza, 'linea_cotizacion_almacen', None)
        if linea_almacen is not None:
            producto = linea_almacen.producto
        clave, unidad = _clave_mercancia(producto)
        linea = _linea_si_hay_importe(
            descripcion, importe, pieza.cantidad, clave, unidad,
        )
        if linea is not None:
            lineas.append(linea)
    return lineas


def _lineas_piezas_mostrador(orden) -> list[LineaFacturable]:
    """
    Piezas vendidas en mostrador. Su precio trae IVA incluido.

    Args:
        orden: OrdenServicio.

    Returns:
        list[LineaFacturable].
    """
    venta = getattr(orden, 'venta_mostrador', None)
    if venta is None:
        return []
    vendidas = venta.piezas_vendidas.select_related(
        'linea_cotizacion__producto',
        'solicitud_baja__producto',
    )
    lineas: list[LineaFacturable] = []
    for pieza in vendidas:
        producto = None
        if pieza.linea_cotizacion_id and pieza.linea_cotizacion.producto_id:
            producto = pieza.linea_cotizacion.producto
        elif pieza.solicitud_baja_id and pieza.solicitud_baja.producto_id:
            producto = pieza.solicitud_baja.producto
        clave, unidad = _clave_mercancia(producto)
        # Paso: el subtotal de mostrador ya incluye IVA. Lo pasamos a neto
        # de una sola vez (cantidad × precio) para no redondear dos veces.
        linea = _linea_si_hay_importe(
            pieza.descripcion_pieza,
            _sin_iva(pieza.subtotal),
            pieza.cantidad,
            clave,
            unidad,
        )
        if linea is not None:
            lineas.append(linea)
    return lineas


def _reparacion_de_contado_lista(orden) -> bool:
    """
    True si el pago de contado de la reparación ya cubre el total y está validado.

    EXPLICACIÓN PARA PRINCIPIANTES:
    No publicamos el webId -3 con un abono parcial: si el cliente timbra
    esa factura, después no podríamos agregarle el resto. Esperamos a que
    los abonos "en una sola exhibición" cubran el total de la reparación.

    Args:
        orden: OrdenServicio.

    Returns:
        bool
    """
    resumen = calcular_resumen_cobro(orden, codigo_pais='MX')
    if resumen.total_a_cobrar <= 0:
        return False
    pagado = _suma_confirmada(orden, SALDO_REPARACION, TIPO_PAGO_COMPLETO)
    return pagado >= resumen.total_a_cobrar


def calcular_lineas_pue(orden) -> list[LineaFacturable]:
    """
    Línea del diagnóstico (webId -1), solo si ya está cubierto y validado.

    Args:
        orden: OrdenServicio.

    Returns:
        list[LineaFacturable] de un elemento, o vacía si aún no se factura.

    Efectos secundarios:
        Lee pagos y mano de obra. No escribe.
    """
    # Paso: el diagnóstico es PUE por el saldo, no por el tipo de servicio.
    diagnostico = resumen_diagnostico(orden)
    if not diagnostico.confirmado_100:
        return []
    return [
        LineaFacturable(
            descripcion=descripcion_servicio_diagnostico(orden),
            importe=diagnostico.monto,
            clave_sat=CLAVE_SAT_DIAGNOSTICO,
        )
    ]


def calcular_lineas_pue_reparacion(orden) -> list[LineaFacturable]:
    """
    Conceptos del pago en una sola exhibición de la reparación (webId -3).

    EXPLICACIÓN PARA PRINCIPIANTES:
    Un PUE de contado describe lo que se vendió: cada servicio de mostrador
    y cada pieza aceptada. La clave SAT sale del producto de almacén; si
    todavía no la tiene, se usa la genérica. El anticipo no pasa por aquí.

    Args:
        orden: OrdenServicio.

    Returns:
        list[LineaFacturable]. Vacía si el contado todavía no cubre el total.

    Efectos secundarios:
        Lee venta mostrador, cotización, productos y pagos. No escribe.
    """
    if not _reparacion_de_contado_lista(orden):
        return []

    lineas: list[LineaFacturable] = []
    lineas.extend(_lineas_servicios_venta_mostrador(orden))
    lineas.extend(_lineas_piezas_cotizadas(orden))
    lineas.extend(_lineas_piezas_mostrador(orden))
    if not lineas:
        return []
    # Paso: el neto de lo pagado es la cifra de caja. Si las líneas
    # difieren por un centavo de redondeo, se corrige la última.
    neto = _sin_iva(_suma_confirmada(orden, SALDO_REPARACION, TIPO_PAGO_COMPLETO))
    return _cuadrar_centavos(lineas, neto)


def calcular_linea_ppd(orden) -> Optional[LineaFacturable]:
    """
    Anticipo facturable de la reparación (webId -2).

    EXPLICACIÓN PARA PRINCIPIANTES:
    El CFDI de anticipo no describe piezas: es una sola línea que dice
    "Anticipo del bien o servicio". El importe es lo que el cliente ya
    entregó como anticipo y que Finanzas ya vio en la cuenta. No importa
    si con eso ya liquidó el 100%: el tipo de pago es el que manda.

    Args:
        orden: OrdenServicio.

    Returns:
        LineaFacturable o None si no hay anticipo validado.

    Efectos secundarios:
        Lee resumen de cobro y pagos. No escribe.
    """
    resumen = calcular_resumen_cobro(orden, codigo_pais='MX')
    # Paso 1: sin total a cobrar no hay reparación que facturar.
    if resumen.total_a_cobrar <= 0:
        return None

    # Paso 2: solo los anticipos validados. El pago de contado va al -3
    # y el diagnóstico al -1. Nunca dos CFDI por el mismo peso.
    anticipo = _suma_confirmada(orden, SALDO_REPARACION, TIPO_ANTICIPO)
    if anticipo <= 0:
        return None

    # Paso 3: el monto recibido viene con IVA; el CFDI pide el valor neto.
    return LineaFacturable(
        descripcion=DESCRIPCION_ANTICIPO,
        importe=_sin_iva(anticipo),
        clave_sat=CLAVE_SAT_ANTICIPO,
        clave_unidad=CLAVE_UNIDAD_ANTICIPO,
    )


def _guardar_documento(
    orden,
    tipo: str,
    lineas: list[LineaFacturable],
    db_alias: str,
) -> Optional[DocumentoFiscalOrden]:
    """
    Crea o actualiza un documento fiscal con sus conceptos.

    Args:
        orden: OrdenServicio dueña.
        tipo: DocumentoFiscalOrden.TIPO_PUE / TIPO_PPD.
        lineas: conceptos ya calculados (sin IVA). Vacío = borrar el borrador.
        db_alias: base del país (obligatorio por el router multi-tenant).

    Returns:
        DocumentoFiscalOrden vigente o None si no hay nada que facturar.

    Efectos secundarios:
        INSERT/UPDATE/DELETE sobre DocumentoFiscalOrden y sus conceptos.
        Debe llamarse dentro de una transacción abierta en `db_alias`.
    """
    existente = (
        DocumentoFiscalOrden.objects.using(db_alias)
        .filter(orden=orden, tipo=tipo)
        .first()
    )

    # Paso 1: timbrado = intocable. Ni recalculamos ni borramos.
    if existente is not None and existente.esta_timbrado:
        return existente

    # Paso 2: sin líneas ya no hay nada facturable. Si había un borrador
    # (por ejemplo se corrigió un pago), se retira para no ofrecer de más.
    if not lineas:
        if existente is not None:
            existente.delete()
        return None

    web_id = construir_web_id(orden, tipo)
    if not web_id:
        return None

    # Paso 3: totales del documento = suma de líneas + IVA sobre esa suma.
    subtotal = _dinero(sum((linea.importe for linea in lineas), Decimal('0.00')))
    iva = _dinero(subtotal * IVA_TASA_MX)
    total = _dinero(subtotal + iva)
    descripcion = lineas[0].descripcion

    if existente is None:
        documento = DocumentoFiscalOrden(orden=orden, tipo=tipo)
    else:
        documento = existente

    documento.web_id = web_id
    documento.descripcion = descripcion
    documento.subtotal = subtotal
    documento.tasa_iva = IVA_TASA_MX
    documento.iva = iva
    documento.total = total
    # Paso 4: la primera vez que hay monto facturable, el cliente ya puede
    # ver su webId. La fecha no se reescribe en recálculos posteriores.
    if documento.disponible_desde is None:
        documento.disponible_desde = timezone.now()
    documento.save(using=db_alias)

    # Paso 5: los conceptos se reescriben completos (son pocos y así no
    # quedan líneas viejas de un cálculo anterior).
    documento.conceptos.all().delete()
    ConceptoDocumentoFiscal.objects.using(db_alias).bulk_create([
        ConceptoDocumentoFiscal(
            documento=documento,
            descripcion=linea.descripcion,
            clave_sat=linea.clave_sat,
            clave_unidad=linea.clave_unidad,
            cantidad=linea.cantidad,
            precio_unitario=_dinero(linea.importe / linea.cantidad),
            importe=linea.importe,
            orden_linea=posicion,
        )
        for posicion, linea in enumerate(lineas, start=1)
    ])
    return documento


def sincronizar_documentos_orden(orden) -> list[DocumentoFiscalOrden]:
    """
    Recalcula los documentos PUE y PPD de una orden.

    Objetivo de negocio:
        Es el único punto donde nacen los webId. Lo llaman el enlace de
        seguimiento (para mostrarle el dato al cliente) y el GET del API
        (por si el cliente lo teclea antes de que abramos su enlace).

    Args:
        orden: OrdenServicio.

    Returns:
        list[DocumentoFiscalOrden] vigentes (0 a 3).

    Efectos secundarios:
        Crea/actualiza/borra documentos y conceptos en la BD del país de la
        orden. Los documentos ya timbrados no se tocan.
    """
    if not aplica_autofacturacion(orden):
        return []

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # `using=` es obligatorio: el router manda las queries a la base del país,
    # pero transaction.atomic() sin using abriría la transacción en 'default'
    # y no protegería nada (ver AGENTS.md §11).
    db_alias = _db_de(orden)
    documentos: list[DocumentoFiscalOrden] = []

    with transaction.atomic(using=db_alias):
        pue = _guardar_documento(
            orden,
            DocumentoFiscalOrden.TIPO_PUE,
            calcular_lineas_pue(orden),
            db_alias,
        )
        if pue is not None:
            documentos.append(pue)

        # Paso: el contado de la reparación es otro PUE. No se cuelga del
        # diagnóstico, porque ese CFDI puede timbrarse el día del ingreso.
        pue_reparacion = _guardar_documento(
            orden,
            DocumentoFiscalOrden.TIPO_PUE_REPARACION,
            calcular_lineas_pue_reparacion(orden),
            db_alias,
        )
        if pue_reparacion is not None:
            documentos.append(pue_reparacion)

        linea_ppd = calcular_linea_ppd(orden)
        ppd = _guardar_documento(
            orden,
            DocumentoFiscalOrden.TIPO_PPD,
            [linea_ppd] if linea_ppd is not None else [],
            db_alias,
        )
        if ppd is not None:
            documentos.append(ppd)

    return documentos


def documentos_disponibles(orden) -> list[DocumentoFiscalOrden]:
    """
    Documentos que el cliente ya puede facturar, recalculados al momento.

    Args:
        orden: OrdenServicio.

    Returns:
        list[DocumentoFiscalOrden] con webId listo para mostrar.

    Efectos secundarios:
        Los mismos que sincronizar_documentos_orden.
    """
    return [
        documento
        for documento in sincronizar_documentos_orden(orden)
        if documento.disponible_desde is not None
    ]
