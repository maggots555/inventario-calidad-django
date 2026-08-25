"""
Cerebro de la facturación en demanda (autofacturador VO → SIGMA).

Objetivo de negocio:
    El portal http://201.149.21.30/facturador pide a SIGMA los datos de una
    venta (GET) para timbrar el CFDI. SIGMA NO timbra: solo arma el JSON
    con encabezado + conceptos SAT a partir de cotización y pagos.

EXPLICACIÓN PARA PRINCIPIANTES:
    El `webId` del API es un número. En SIGMA el folio que ve el cliente
    es `orden_cliente` (ej. OOW-11902). Extraemos solo los dígitos:
    OOW-11902 → 11902. Si dos órdenes caen al mismo número, no adivinamos.

Efectos secundarios:
    El GET deja constancia en ComprobanteFiscalOrden (solicitado_en) para
    que el PUT posterior pueda guardar XML y PDF. El PUT escribe archivos
    en media y marca factura_emitida en la orden.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
import time
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Optional

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from config.paises_config import get_pais_actual
from servicio_tecnico.models import DetalleEquipo, OrdenServicio
from servicio_tecnico.models_facturacion import ComprobanteFiscalOrden
from servicio_tecnico.services.pagos_orden import IVA_TASA_MX, _db_de, calcular_resumen_cobro

CENTAVO = Decimal('0.01')

# Catálogo interno que esperaba el portal VO (PDF SICSER 4).
EMPRESA_EMISORA = '2'
OBJETO_IMPUESTO = 2
IMPUESTOS_IVA = '[4]'

# Claves SAT genéricas (fase 1: defaults; un catálogo fino puede llegar después).
CLAVE_SAT_PIEZA = '43211600'
CLAVE_UNIDAD_PIEZA = 'H87'
UNIDAD_PIEZA = 'PIEZA'
CLAVE_SAT_SERVICIO = '81111812'
CLAVE_UNIDAD_SERVICIO = 'E48'
UNIDAD_SERVICIO = 'UNIDAD DE SERVICIO'

# forma_pago SAT c_FormaPago a partir de PagoOrden.metodo.
MAPEO_FORMA_PAGO = {
    'efectivo': '01',
    'transferencia': '03',
    'tarjeta': '04',
    'otro': '99',
}

MENSAJE_BAD_REQUEST = 'Bad Request'
MENSAJE_NO_ENCONTRADO = 'No se encontró el folio'
RAZON_NO_NUMERICO = 'Información de folio no numérico'
RAZON_SIN_ACU = 'la venta no tiene estatus ACU'
RAZON_SIN_PAGOS = 'la venta no tiene pagos para facturar'
RAZON_PAGO_INVALIDO = 'forma de pago no válida, método de pago no válido'
RAZON_COLISION = 'hay más de una orden con el mismo folio numérico'
RAZON_SOLO_MEXICO = 'la facturación en demanda solo aplica en México'
RAZON_SIN_GET_PREVIO = (
    'Solo se recibirán datos de facturas timbradas que se hayan '
    'solicitado previamente por el método GET'
)
RAZON_YA_TIMBRADA = 'la venta ya tiene una factura timbrada'
RAZON_PAYLOAD_CFDI = 'Payload de CFDI inválido o incompleto'


class FacturacionDemandaError(Exception):
    """
    Error de negocio o de contrato del API de facturación.

    Args:
        http_status: 400, 401 o 404 (lo que espera el portal VO).
        mensaje: texto corto (Bad Request / Unauthorized / No se encontró…).
        razon: detalle para el body JSON.
    """

    def __init__(self, http_status: int, mensaje: str, razon: str = ''):
        super().__init__(razon or mensaje)
        self.http_status = http_status
        self.mensaje = mensaje
        self.razon = razon


def extraer_digitos(texto: str) -> str:
    """
    Deja solo los números de un folio de cliente.

    Args:
        texto: ej. 'OOW-11902' o 'FL-2026-0001'.

    Returns:
        str: '11902' o '20260001'. Cadena vacía si no hay dígitos.
    """
    return ''.join(caracter for caracter in (texto or '') if caracter.isdigit())


def web_id_a_entero(web_id: str) -> int:
    """
    Convierte el path {webId} a entero. Si no es numérico, lanza 400.

    Args:
        web_id: fragmento de URL (puede traer ceros a la izquierda).

    Returns:
        int: el número (0123 → 123).
    """
    bruto = str(web_id or '').strip()
    # Paso: el PDF exige folio numérico; letras → 400, no 404 de Django.
    if not bruto.isdigit():
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_NO_NUMERICO)
    return int(bruto)


def _a_centavos(valor: Decimal) -> Decimal:
    """Redondea dinero a 2 decimales (0.005 sube)."""
    return Decimal(valor).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _a_float(valor: Decimal) -> float:
    """JSON numérico como el ejemplo del PDF (no string)."""
    return float(_a_centavos(valor))


def _precio_sin_iva_si_incluye(monto: Decimal, incluye_iva: bool) -> Decimal:
    """
    El API pide precio de concepto SIN IVA.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Las piezas cotizadas ya están sin IVA. La venta mostrador en SIGMA
    suele ir con IVA incluido: aquí lo quitamos para no duplicar el 16%.
    """
    monto = _a_centavos(monto)
    if not incluye_iva or monto <= 0:
        return monto
    return _a_centavos(monto / (Decimal('1') + IVA_TASA_MX))


def _concepto(
    *,
    descripcion: str,
    precio: Decimal,
    cantidad: int,
    es_servicio: bool,
    clave_cliente: str,
) -> dict[str, Any]:
    """Arma un renglón del array `conceptos` del PDF."""
    if es_servicio:
        clave_sat, clave_unidad, unidad = (
            CLAVE_SAT_SERVICIO,
            CLAVE_UNIDAD_SERVICIO,
            UNIDAD_SERVICIO,
        )
    else:
        clave_sat, clave_unidad, unidad = (
            CLAVE_SAT_PIEZA,
            CLAVE_UNIDAD_PIEZA,
            UNIDAD_PIEZA,
        )
    return {
        'clave_producto_servicio': clave_sat,
        'descripcion': descripcion,
        'clave_unidad': clave_unidad,
        'precio': _a_float(precio),
        'numero_identificacion': 'None',
        'unidad': unidad,
        'objeto_impuesto': OBJETO_IMPUESTO,
        'impuestos': IMPUESTOS_IVA,
        'empresa': EMPRESA_EMISORA,
        'clave_producto_cliente': clave_cliente or 'P0000',
        'cantidad': cantidad,
        'descuento': 0,
    }


def _codigo_pais() -> str:
    """ISO del tenant actual; MX si el middleware no corrió (tests)."""
    try:
        return get_pais_actual().get('codigo', 'MX') or 'MX'
    except Exception:
        return 'MX'


def buscar_ordenes_por_web_id(numero: int) -> list[OrdenServicio]:
    """
    Órdenes cuyo `orden_cliente` se reduce al mismo entero que `numero`.

    Args:
        numero: webId ya validado (ej. 11902).

    Returns:
        list: 0, 1 o varias (colisión OOW-1234 vs FL-1234).

    Efectos secundarios:
        Lee DetalleEquipo (folio + id de orden) y luego las órdenes.
    """
    coincidencias: list[int] = []
    # Paso 1: un query liviano (id + folio). El número concatenado de
    # FL-2026-0001 no aparece como substring, así que no filtramos en SQL.
    filas = DetalleEquipo.objects.exclude(orden_cliente='').values_list(
        'orden_id',
        'orden_cliente',
    )
    for orden_id, folio in filas:
        digitos = extraer_digitos(folio)
        if digitos and int(digitos) == numero:
            coincidencias.append(orden_id)

    if not coincidencias:
        return []

    return list(
        OrdenServicio.objects.select_related(
            'cotizacion',
            'venta_mostrador',
            'detalle_equipo',
        )
        .prefetch_related(
            'pagos',
            'cotizacion__piezas_cotizadas__componente',
            'venta_mostrador__piezas_vendidas',
        )
        .filter(pk__in=coincidencias)
    )


def _exige_acu(orden: OrdenServicio) -> None:
    """
    ACU en SICSER = Cliente Autoriza Cotización.

    En SIGMA el estado `cliente_acepta_cotizacion` es un PASO: la orden
    sigue a reparación/entrega. El dato que sí se queda es
    `cotizacion.usuario_acepto is True`.
    """
    if orden.estado in ('cancelado', 'rechazada'):
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SIN_ACU)
    cotizacion = getattr(orden, 'cotizacion', None)
    if cotizacion is None or cotizacion.usuario_acepto is not True:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SIN_ACU)


def _forma_y_metodo_pago(orden: OrdenServicio, cubierto_100: bool) -> tuple[str, str]:
    """
    Mapea abonos SIGMA → catálogos SAT.

    Returns:
        tuple: (metodo_pago PUE/PPD, forma_pago '01'/'03'/…).
    """
    metodos = {pago.metodo for pago in orden.pagos.all()}
    if not metodos:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SIN_PAGOS)
    # Paso: un solo método → su clave SAT; mixtos → 99 (por definir).
    if len(metodos) == 1:
        metodo = next(iter(metodos))
        forma = MAPEO_FORMA_PAGO.get(metodo)
        if not forma:
            raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_PAGO_INVALIDO)
    else:
        forma = '99'
    metodo_cfdi = 'PUE' if cubierto_100 else 'PPD'
    return metodo_cfdi, forma


def _conceptos_piezas(orden: OrdenServicio) -> list[dict[str, Any]]:
    """Líneas de piezas aceptadas (precio al cliente, sin IVA)."""
    cotizacion = getattr(orden, 'cotizacion', None)
    if cotizacion is None:
        return []
    conceptos: list[dict[str, Any]] = []
    piezas = cotizacion.piezas_cotizadas.filter(aceptada_por_cliente=True)
    for pieza in piezas:
        if pieza.precio_unitario_cliente is not None:
            precio = pieza.precio_unitario_cliente
        else:
            precio = pieza.costo_unitario
        nombre = pieza.componente.nombre if pieza.componente_id else 'Pieza'
        extra = (pieza.descripcion_adicional or '').strip()
        descripcion = f'{nombre} / {extra}' if extra else nombre
        clave = f'P{pieza.componente_id:04d}' if pieza.componente_id else 'P0000'
        conceptos.append(
            _concepto(
                descripcion=descripcion.upper(),
                precio=precio,
                cantidad=pieza.cantidad,
                es_servicio=False,
                clave_cliente=clave,
            )
        )
    return conceptos


def _conceptos_venta_mostrador(orden: OrdenServicio) -> list[dict[str, Any]]:
    """Servicios y piezas de VM (en SIGMA el monto suele incluir IVA)."""
    venta = getattr(orden, 'venta_mostrador', None)
    if venta is None:
        return []
    conceptos: list[dict[str, Any]] = []

    def agregar_servicio(descripcion: str, monto: Decimal, clave: str) -> None:
        if monto <= 0:
            return
        conceptos.append(
            _concepto(
                descripcion=descripcion,
                precio=_precio_sin_iva_si_incluye(monto, incluye_iva=True),
                cantidad=1,
                es_servicio=True,
                clave_cliente=clave,
            )
        )

    # Paso: cada bandera de VM es un concepto aparte (limpieza, kit, etc.).
    if venta.paquete and venta.paquete != 'ninguno':
        agregar_servicio(
            f'PAQUETE {venta.get_paquete_display()}'.upper(),
            venta.costo_paquete,
            'S-PAQ',
        )
    if venta.incluye_cambio_pieza:
        agregar_servicio('CAMBIO DE PIEZA', venta.costo_cambio_pieza, 'S-CAM')
    if venta.incluye_limpieza:
        agregar_servicio('LIMPIEZA Y MANTENIMIENTO', venta.costo_limpieza, 'S-LIM')
    if venta.incluye_kit_limpieza:
        agregar_servicio('KIT DE LIMPIEZA', venta.costo_kit, 'S-KIT')
    if venta.incluye_reinstalacion_so:
        agregar_servicio('REINSTALACION DE SO', venta.costo_reinstalacion, 'S-SO')
    if venta.incluye_respaldo:
        agregar_servicio('RESPALDO DE INFORMACION', venta.costo_respaldo, 'S-RES')

    for pieza_vm in venta.piezas_vendidas.all():
        precio_neto = _precio_sin_iva_si_incluye(
            pieza_vm.precio_unitario,
            incluye_iva=True,
        )
        conceptos.append(
            _concepto(
                descripcion=(pieza_vm.descripcion_pieza or 'PIEZA VM').upper(),
                precio=precio_neto,
                cantidad=pieza_vm.cantidad,
                es_servicio=False,
                clave_cliente=f'VM{pieza_vm.pk}',
            )
        )
    return conceptos


def armar_payload_venta(orden: OrdenServicio, web_id: int) -> dict[str, Any]:
    """
    JSON de venta listo para el GET (encabezado + conceptos).

    Args:
        orden: ya validada (ACU + pagos).
        web_id: número público del path.

    Returns:
        dict: exactamente las llaves del PDF SICSER 4.
    """
    resumen = calcular_resumen_cobro(orden, codigo_pais='MX')
    metodo_pago, forma_pago = _forma_y_metodo_pago(orden, resumen.cubierto_100)

    ultimo_pago = orden.pagos.order_by('-fecha_pago').first()
    fecha_ticket = ultimo_pago.fecha_pago if ultimo_pago else timezone.now()
    folio_visible = ''
    try:
        folio_visible = (orden.detalle_equipo.orden_cliente or '').strip()
    except Exception:
        folio_visible = orden.numero_orden_interno

    conceptos = _conceptos_piezas(orden) + _conceptos_venta_mostrador(orden)
    if not conceptos:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SIN_PAGOS)

    return {
        'encabezado': {
            'fecha_ticket': fecha_ticket.isoformat(),
            'folio': folio_visible or str(web_id),
            'web_id': str(web_id),
            'total': _a_float(resumen.total_a_cobrar),
            'metodo_pago': metodo_pago,
            'forma_pago': forma_pago,
        },
        'conceptos': conceptos,
    }


def obtener_venta_para_facturar(web_id: str) -> dict[str, Any]:
    """
    Punto de entrada del GET: valida país, ACU, pagos y arma el JSON.

    Args:
        web_id: fragmento de URL (debe ser numérico).

    Returns:
        dict: payload del PDF.

    Efectos secundarios:
        Escribe ComprobanteFiscalOrden.solicitado_en (reserva para el PUT).
    """
    if _codigo_pais() != 'MX':
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SOLO_MEXICO)

    numero = web_id_a_entero(web_id)
    ordenes = buscar_ordenes_por_web_id(numero)
    if not ordenes:
        raise FacturacionDemandaError(404, MENSAJE_NO_ENCONTRADO, MENSAJE_NO_ENCONTRADO)
    if len(ordenes) > 1:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_COLISION)

    orden = ordenes[0]
    _exige_acu(orden)
    if not orden.pagos.exists():
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SIN_PAGOS)
    payload = armar_payload_venta(orden, numero)
    # Paso: el PDF exige GET antes del PUT. Guardamos la “reserva”.
    marcar_solicitud_facturacion(orden, numero)
    return payload


def marcar_solicitud_facturacion(orden: OrdenServicio, web_id: int) -> None:
    """
    Anota que el portal ya consultó esta venta (requisito del PUT).

    Args:
        orden: orden facturable.
        web_id: número del path.

    Efectos secundarios:
        Crea o actualiza ComprobanteFiscalOrden.solicitado_en.
    """
    db_alias = _db_de(orden)
    ahora = timezone.now()
    with transaction.atomic(using=db_alias):
        comprobante, creado = ComprobanteFiscalOrden.objects.get_or_create(
            orden=orden,
            defaults={'web_id': web_id, 'solicitado_en': ahora},
        )
        if not creado and not comprobante.solicitado_en:
            comprobante.solicitado_en = ahora
            comprobante.web_id = web_id
            comprobante.save(update_fields=['solicitado_en', 'web_id'])


def _bytes_campo_base64(valor: Any, *, permitir_xml: bool = False) -> bytes:
    """
    Decodifica pdf64 / cfdi del PUT.

    EXPLICACIÓN PARA PRINCIPIANTES:
    A veces VO manda el XML en texto (`<?xml …>`). Otras veces viene en
    base64, o con prefijo data:application/pdf;base64,…
    """
    texto = str(valor or '').strip()
    if not texto:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_PAYLOAD_CFDI)
    if permitir_xml and texto.startswith('<'):
        return texto.encode('utf-8')
    if texto.lower().startswith('data:') and ',' in texto:
        texto = texto.split(',', 1)[1]
    try:
        crudo = base64.b64decode(texto, validate=False)
    except Exception as exc:
        raise FacturacionDemandaError(
            400, MENSAJE_BAD_REQUEST, RAZON_PAYLOAD_CFDI
        ) from exc
    if not crudo:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_PAYLOAD_CFDI)
    return crudo


def _parse_fecha_timbrado(valor: Any):
    """Convierte fechaTimbrado ISO a datetime con zona horaria."""
    if not valor:
        return timezone.now()
    texto = str(valor).strip().replace('Z', '+00:00')
    dt = parse_datetime(texto)
    if dt is None:
        raise FacturacionDemandaError(
            400, MENSAJE_BAD_REQUEST, 'fechaTimbrado inválida'
        )
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def persistir_cfdi_timbrado(web_id: str, payload: dict[str, Any]) -> None:
    """
    PUT: guarda XML, PDF y sellos. 204 si ok; 404 si no hubo GET.

    Args:
        web_id: path numérico.
        payload: JSON del portal VO (uuid, cfdi, pdf64, …).

    Efectos secundarios:
        Escribe archivos en media, UUID en ComprobanteFiscalOrden,
        factura_emitida=True en la orden.
    """
    if _codigo_pais() != 'MX':
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SOLO_MEXICO)
    if not isinstance(payload, dict):
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_PAYLOAD_CFDI)

    numero = web_id_a_entero(web_id)
    ordenes = buscar_ordenes_por_web_id(numero)
    if not ordenes:
        raise FacturacionDemandaError(404, MENSAJE_NO_ENCONTRADO, MENSAJE_NO_ENCONTRADO)
    if len(ordenes) > 1:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_COLISION)
    orden = ordenes[0]

    uuid_sat = str(payload.get('uuid') or '').strip()
    if not uuid_sat or len(uuid_sat) > 36:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_PAYLOAD_CFDI)

    xml_bytes = _bytes_campo_base64(payload.get('cfdi'), permitir_xml=True)
    pdf_bytes = _bytes_campo_base64(payload.get('pdf64'), permitir_xml=False)
    fecha_timbrado = _parse_fecha_timbrado(payload.get('fechaTimbrado'))
    nombre_base = re.sub(r'[^0-9A-Fa-f-]', '', uuid_sat) or 'cfdi'

    db_alias = _db_de(orden)
    with transaction.atomic(using=db_alias):
        try:
            comprobante = (
                ComprobanteFiscalOrden.objects.using(db_alias)
                .select_for_update()
                .get(orden=orden)
            )
        except ComprobanteFiscalOrden.DoesNotExist as exc:
            raise FacturacionDemandaError(
                404, MENSAJE_NO_ENCONTRADO, RAZON_SIN_GET_PREVIO
            ) from exc

        if not comprobante.solicitado_en:
            raise FacturacionDemandaError(
                404, MENSAJE_NO_ENCONTRADO, RAZON_SIN_GET_PREVIO
            )

        # Paso: mismo UUID otra vez = el portal reintentó; no duplicamos.
        if comprobante.esta_timbrado:
            if comprobante.uuid == uuid_sat:
                return
            raise FacturacionDemandaError(
                400, MENSAJE_BAD_REQUEST, RAZON_YA_TIMBRADA
            )

        comprobante.web_id = numero
        comprobante.uuid = uuid_sat
        comprobante.fecha_timbrado = fecha_timbrado
        comprobante.cadena_original_sat = str(payload.get('cadenaOriginalSAT') or '')
        comprobante.no_certificado_sat = str(payload.get('noCertificadoSAT') or '')[:40]
        comprobante.no_certificado_cfdi = str(payload.get('noCertificadoCFDI') or '')[:40]
        comprobante.sello_sat = str(payload.get('selloSAT') or '')
        comprobante.sello_cfdi = str(payload.get('selloCFDI') or '')
        comprobante.qr_code = str(payload.get('qrCode') or '')
        comprobante.recibido_en = timezone.now()
        comprobante.cfdi_xml.save(
            f'{nombre_base}.xml',
            ContentFile(xml_bytes),
            save=False,
        )
        comprobante.pdf.save(
            f'{nombre_base}.pdf',
            ContentFile(pdf_bytes),
            save=False,
        )
        comprobante.save()
        OrdenServicio.objects.using(db_alias).filter(pk=orden.pk).update(
            factura_emitida=True,
        )


# ---------------------------------------------------------------------------
# JWT mínimo (HS256) sin dependencia extra — el portal manda Bearer token.
# ---------------------------------------------------------------------------

def _b64url_encode(crudo: bytes) -> str:
    """Base64 URL sin padding, como un JWT de verdad."""
    return base64.urlsafe_b64encode(crudo).rstrip(b'=').decode('ascii')


def _b64url_decode(texto: str) -> bytes:
    """Inverso de `_b64url_encode` (rellena el padding que JWT omite)."""
    relleno = '=' * ((4 - len(texto) % 4) % 4)
    return base64.urlsafe_b64decode(texto + relleno)


def _secreto_jwt() -> bytes:
    """Clave HMAC: el secret del .env (el mismo del body authenticate)."""
    secreto = getattr(settings, 'FACTURACION_WEB_SECRET', '') or ''
    if not secreto:
        raise FacturacionDemandaError(401, 'Unauthorized', 'API no configurada')
    return secreto.encode('utf-8')


def emitir_access_token() -> str:
    """
    JWT HS256 con vigencia de pruebas (1 día) o producción (1 hora).

    Returns:
        str: token compacto header.payload.firma
    """
    ttl = int(getattr(settings, 'FACTURACION_WEB_TOKEN_TTL', 3600) or 3600)
    ahora = int(time.time())
    encabezado = _b64url_encode(json.dumps({'alg': 'HS256', 'typ': 'JWT'}).encode())
    # iss/aud iguales al PDF para no romper un portal que los lea.
    cuerpo = _b64url_encode(
        json.dumps(
            {
                'iss': 'SICSER4',
                'aud': 'SICSER4Users',
                'nbf': ahora,
                'exp': ahora + ttl,
            }
        ).encode()
    )
    firma = hmac.new(
        _secreto_jwt(),
        f'{encabezado}.{cuerpo}'.encode('ascii'),
        hashlib.sha256,
    ).digest()
    return f'{encabezado}.{cuerpo}.{_b64url_encode(firma)}'


def validar_access_token(token: str) -> None:
    """
    Verifica firma y expiración del JWT emitido por `emitir_access_token`.

    Args:
        token: valor crudo después de 'Bearer '.
    """
    partes = (token or '').split('.')
    if len(partes) != 3:
        raise FacturacionDemandaError(401, 'Unauthorized', 'Token inválido')
    encabezado, cuerpo, firma_recibida = partes
    firma_esperada = _b64url_encode(
        hmac.new(
            _secreto_jwt(),
            f'{encabezado}.{cuerpo}'.encode('ascii'),
            hashlib.sha256,
        ).digest()
    )
    if not hmac.compare_digest(firma_recibida, firma_esperada):
        raise FacturacionDemandaError(401, 'Unauthorized', 'Token inválido')
    try:
        payload = json.loads(_b64url_decode(cuerpo))
    except (ValueError, json.JSONDecodeError) as exc:
        raise FacturacionDemandaError(401, 'Unauthorized', 'Token inválido') from exc
    exp = int(payload.get('exp') or 0)
    if exp < int(time.time()):
        raise FacturacionDemandaError(401, 'Unauthorized', 'el token ha expirado')


def credenciales_configuradas() -> bool:
    """False si falta API Key o secret en settings/.env."""
    api_key = getattr(settings, 'FACTURACION_WEB_API_KEY', '') or ''
    secret = getattr(settings, 'FACTURACION_WEB_SECRET', '') or ''
    return bool(api_key.strip() and secret.strip())


def validar_api_key(valor_header: Optional[str]) -> None:
    """Compara X-API-KEY con tiempo constante (evita timing attacks)."""
    esperado = getattr(settings, 'FACTURACION_WEB_API_KEY', '') or ''
    recibido = valor_header or ''
    if not esperado or not hmac.compare_digest(recibido, esperado):
        raise FacturacionDemandaError(
            401,
            'Unauthorized',
            'No se envió API Key o Token en header o el token ha expirado',
        )


def validar_secret_authenticate(secret_body: Optional[str]) -> None:
    """El body JSON `secret` debe coincidir con FACTURACION_WEB_SECRET."""
    esperado = getattr(settings, 'FACTURACION_WEB_SECRET', '') or ''
    recibido = secret_body or ''
    if not esperado or not hmac.compare_digest(recibido, esperado):
        raise FacturacionDemandaError(401, 'Unauthorized', 'Secret inválido')
