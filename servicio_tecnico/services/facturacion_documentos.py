"""
Construcción de los documentos facturables PUE y PPD de una orden.

Objetivo de negocio:
    Decidir qué puede facturar el cliente en el portal VO y por cuánto:

    * PUE — servicios pagados al 100%: el Diagnóstico (mano de obra) y los
      servicios de venta mostrador como "Limpieza y Mantenimiento". Se factura
      el servicio completo con IVA desglosado.
    * PPD — anticipo de una reparación que todavía no se liquida. Un solo
      concepto, "Anticipo del bien o servicio", sin describir piezas.

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
    TIPO_PAGO_DIAGNOSTICO,
    descripcion_servicio_diagnostico,
    orden_en_garantia,
    resumen_diagnostico,
)
from servicio_tecnico.services.pagos_orden import (
    IVA_TASA_MX,
    _db_de,
    calcular_resumen_cobro,
)

CENTAVO = Decimal('0.01')

# Claves del catálogo del SAT. Fase 1: una clave genérica por naturaleza.
# 81111812 = servicios de mantenimiento/soporte técnico. E48 = unidad de servicio.
CLAVE_SAT_SERVICIO = '81111812'
CLAVE_UNIDAD_SERVICIO = 'E48'
# 84111506 = servicios de facturación/anticipos. ACT = actividad.
CLAVE_SAT_ANTICIPO = '84111506'
CLAVE_UNIDAD_ANTICIPO = 'ACT'

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
        clave_sat / clave_unidad: catálogos del SAT.
    """

    descripcion: str
    importe: Decimal
    cantidad: Decimal = Decimal('1.00')
    clave_sat: str = CLAVE_SAT_SERVICIO
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


def _pagado_confirmado_reparacion(orden) -> Decimal:
    """
    Dinero de la REPARACIÓN que Facturación ya dio por bueno.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Excluimos los abonos tipo 'diagnostico' porque ese bolsillo se factura
    aparte (PUE) y no debe contarse dos veces.

    Args:
        orden: OrdenServicio.

    Returns:
        Decimal con 2 decimales.
    """
    agregado = (
        orden.pagos.exclude(tipo=TIPO_PAGO_DIAGNOSTICO)
        .filter(estado_validacion__in=ESTADOS_PAGO_CONFIRMADO)
        .aggregate(total=Sum('monto'))['total']
    )
    return _dinero(agregado)


def _lineas_servicios_venta_mostrador(orden) -> list[LineaFacturable]:
    """
    Servicios de venta mostrador como líneas sin IVA.

    Objetivo: "Limpieza y Mantenimiento", kit, reinstalación de SO, etc. son
    servicios puros; son exactamente lo que el negocio quiere facturar PUE.
    Las piezas vendidas en mostrador NO entran aquí: eso es mercancía.

    Args:
        orden: OrdenServicio.

    Returns:
        list[LineaFacturable] (vacía si no hay venta mostrador).
    """
    venta = getattr(orden, 'venta_mostrador', None)
    if venta is None:
        return []

    lineas: list[LineaFacturable] = []

    def agregar(descripcion: str, monto_con_iva) -> None:
        """Suma una línea solo si el servicio tiene costo real."""
        importe = _sin_iva(monto_con_iva)
        if importe > 0:
            lineas.append(LineaFacturable(descripcion=descripcion, importe=importe))

    # Paso 1: el paquete comercial (premium, oro, plata…) si se eligió uno.
    if venta.paquete and venta.paquete != 'ninguno':
        agregar(f'Paquete {venta.get_paquete_display()}', venta.costo_paquete)

    # Paso 2: cada servicio suelto es un concepto propio, con el texto que
    # el negocio pidió ver en la factura.
    if venta.incluye_limpieza:
        agregar('Limpieza y Mantenimiento', venta.costo_limpieza)
    if venta.incluye_kit_limpieza:
        agregar('Kit de limpieza', venta.costo_kit)
    if venta.incluye_reinstalacion_so:
        agregar('Reinstalación de sistema operativo', venta.costo_reinstalacion)
    if venta.incluye_respaldo:
        agregar('Respaldo de información', venta.costo_respaldo)
    if venta.incluye_cambio_pieza:
        agregar('Cambio de pieza (mano de obra)', venta.costo_cambio_pieza)

    return lineas


def _tiene_piezas_por_cobrar(orden) -> bool:
    """
    True si la orden incluye mercancía (piezas cotizadas o vendidas en VM).

    EXPLICACIÓN PARA PRINCIPIANTES:
    Nos sirve para no mezclar bolsillos. Si la orden trae piezas, el dinero
    que entró puede ser de las piezas y no de los servicios, así que los
    servicios de mostrador NO se facturan PUE por su cuenta.
    """
    cotizacion = getattr(orden, 'cotizacion', None)
    if cotizacion is not None and cotizacion.piezas_cotizadas.filter(
        aceptada_por_cliente=True
    ).exists():
        return True

    venta = getattr(orden, 'venta_mostrador', None)
    if venta is not None and venta.piezas_vendidas.exists():
        return True
    return False


def _servicios_mostrador_van_en_pue(orden) -> bool:
    """
    True si los servicios de venta mostrador se facturan como PUE.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Solo cuando la orden es de PUROS servicios (sin piezas de por medio) y el
    cliente ya liquidó el 100% verificado. Si hubiera piezas no podríamos
    saber qué parte del dinero pagó los servicios y qué parte la mercancía.

    Args:
        orden: OrdenServicio.

    Returns:
        bool
    """
    if _tiene_piezas_por_cobrar(orden):
        return False
    resumen = calcular_resumen_cobro(orden, codigo_pais='MX')
    if resumen.total_a_cobrar <= 0 or not resumen.cubierto_100:
        return False
    # Paso: además del saldo en cero, el dinero debe estar verificado.
    return _pagado_confirmado_reparacion(orden) >= resumen.total_a_cobrar


def calcular_lineas_pue(orden) -> list[LineaFacturable]:
    """
    Servicios pagados al 100% que se facturan en una sola exhibición.

    Args:
        orden: OrdenServicio.

    Returns:
        list[LineaFacturable]. Vacía significa "todavía no hay PUE".

    Efectos secundarios:
        Lee cotización, venta mostrador y pagos. No escribe.
    """
    lineas: list[LineaFacturable] = []

    # Paso 1: el diagnóstico. Solo si está cubierto Y verificado en cuenta.
    diagnostico = resumen_diagnostico(orden)
    if diagnostico.confirmado_100:
        lineas.append(
            LineaFacturable(
                descripcion=descripcion_servicio_diagnostico(orden),
                importe=diagnostico.monto,
            )
        )

    # Paso 2: los servicios de mostrador, cuando la orden es solo servicios.
    if _servicios_mostrador_van_en_pue(orden):
        lineas.extend(_lineas_servicios_venta_mostrador(orden))

    return lineas


def calcular_linea_ppd(orden) -> Optional[LineaFacturable]:
    """
    Anticipo facturable de la reparación (piezas y mercancía).

    EXPLICACIÓN PARA PRINCIPIANTES:
    El CFDI de anticipo no describe piezas (cuando se cobra todavía no se sabe
    con certeza qué se va a instalar): es una sola línea que dice "Anticipo del
    bien o servicio". El importe es lo que el cliente ya entregó y que
    Facturación ya verificó en la cuenta.

    Lo que decide que sea PPD es la NATURALEZA del cobro (una reparación que
    se paga en partes: anticipo del 50% y saldo a la entrega), no el monto.
    Por eso no preguntamos si ya está liquidada.

    Args:
        orden: OrdenServicio.

    Returns:
        LineaFacturable o None si no hay anticipo que facturar.

    Efectos secundarios:
        Lee resumen de cobro y pagos. No escribe.
    """
    resumen = calcular_resumen_cobro(orden, codigo_pais='MX')
    # Paso 1: sin total a cobrar no hay reparación que facturar.
    if resumen.total_a_cobrar <= 0:
        return None

    # Paso 2: si ese mismo dinero ya se fue al PUE (orden de puros servicios
    # liquidada), no lo volvemos a facturar aquí. Nunca dos CFDI por un peso.
    if _servicios_mostrador_van_en_pue(orden):
        return None

    # Paso 3: solo el dinero que Facturación ya dio por bueno.
    anticipo = _pagado_confirmado_reparacion(orden)
    if anticipo <= 0:
        return None

    # Paso 3: el monto recibido viene con IVA (es lo que pagó el cliente);
    # el CFDI pide el valor antes de impuestos.
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
        list[DocumentoFiscalOrden] vigentes (0, 1 o 2).

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
