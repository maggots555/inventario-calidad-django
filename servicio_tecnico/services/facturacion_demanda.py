"""
Cerebro del autofacturador (portal VO → SIGMA).

Objetivo de negocio:
    El cliente entra al portal de facturación, teclea su `webId` y el portal
    le pregunta a SIGMA qué debe timbrar (GET). SIGMA NO timbra: arma el JSON
    con encabezado + conceptos SAT. Cuando VO termina, devuelve el CFDI
    timbrado (PUT) y aquí guardamos XML, PDF y UUID.

EXPLICACIÓN PARA PRINCIPIANTES — el webId manda:
    `SAT9596-1` significa "sucursal Satélite, folio 9596, documento tipo 1
    (PUE)". De ahí sacamos la orden y el documento exacto. Cómo se arma y se
    lee ese texto está en facturacion_web_id.py; qué se puede facturar y por
    cuánto, en facturacion_documentos.py. Este archivo solo traduce eso al
    contrato HTTP que espera VO.

Efectos secundarios:
    El GET deja constancia en DocumentoFiscalOrden (solicitado_en), requisito
    para aceptar el PUT. El PUT escribe archivos en media y marca
    factura_emitida en la orden.
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
from urllib.parse import urlencode

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from config.paises_config import get_pais_actual
from servicio_tecnico.models import DetalleEquipo, OrdenServicio
from servicio_tecnico.models_facturacion import DocumentoFiscalOrden
from servicio_tecnico.services.facturacion_documentos import (
    aplica_autofacturacion,
    pagos_confirmados_del_documento,
    sincronizar_documentos_orden,
)
from servicio_tecnico.services.facturacion_web_id import (  # noqa: F401
    PartesWebId,
    construir_web_id,
    desglosar_web_id,
    extraer_digitos,
    filtrar_ordenes_por_prefijo,
)
from servicio_tecnico.services.pagos_orden import _db_de

CENTAVO = Decimal('0.01')

# Catálogo interno que espera el portal VO (PDF SICSER 4).
EMPRESA_EMISORA = '2'
OBJETO_IMPUESTO = 2
IMPUESTOS_IVA = '[4]'
MONEDA_DEFAULT = 'MXN'

# forma_pago SAT c_FormaPago a partir de PagoOrden.metodo.
# efectivo / tarjeta / otro se conservan para abonos viejos.
MAPEO_FORMA_PAGO = {
    'efectivo': '01',
    'transferencia': '03',
    'tarjeta': '04',
    'tarjeta_credito': '04',
    'tarjeta_debito': '28',
    'otro': '99',
}

# Cómo se llama cada tipo en el catálogo c_MetodoPago del SAT.
# El -3 también es PUE: tipo_factura sigue en 1.
METODO_PAGO_SAT = {
    DocumentoFiscalOrden.TIPO_PUE: 'PUE',
    DocumentoFiscalOrden.TIPO_PUE_REPARACION: 'PUE',
    DocumentoFiscalOrden.TIPO_PPD: 'PPD',
}

MENSAJE_BAD_REQUEST = 'Bad Request'
MENSAJE_NO_ENCONTRADO = 'No se encontró el folio'
RAZON_WEB_ID_INVALIDO = 'El webId no tiene un formato válido'
RAZON_SIN_PAGOS = 'la venta no tiene pagos validados para facturar'
RAZON_PAGO_INVALIDO = 'forma de pago no válida, método de pago no válido'
RAZON_COLISION = 'hay más de una orden con el mismo folio'
RAZON_TIPO_AMBIGUO = (
    'el folio tiene más de un documento facturable; '
    'indique el documento en el webId (-1 diagnóstico, -2 anticipo, -3 contado)'
)
RAZON_SOLO_MEXICO = 'la facturación en demanda solo aplica en México'
RAZON_NO_FACTURABLE = 'la venta no está disponible para autofacturación'
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


def _a_centavos(valor: Decimal) -> Decimal:
    """Redondea dinero a 2 decimales (0.005 sube)."""
    return Decimal(valor or 0).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _a_float(valor: Decimal) -> float:
    """JSON numérico como el ejemplo del PDF (no string)."""
    return float(_a_centavos(valor))


def _codigo_pais() -> str:
    """ISO del tenant actual; MX si el middleware no corrió (tests)."""
    try:
        return get_pais_actual().get('codigo', 'MX') or 'MX'
    except Exception:
        return 'MX'


def partes_web_id(web_id: str) -> PartesWebId:
    """
    Lee el webId del path o lanza 400 si no se entiende.

    Args:
        web_id: fragmento de URL ('SAT9596-1', 'SAT9596', '9596').

    Returns:
        PartesWebId con prefijo, dígitos y tipo.
    """
    partes = desglosar_web_id(web_id)
    if partes is None:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_WEB_ID_INVALIDO)
    return partes


def buscar_ordenes_por_web_id(numero: int) -> list[OrdenServicio]:
    """
    Órdenes cuyo `orden_cliente` se reduce al mismo entero que `numero`.

    Args:
        numero: dígitos del webId ya validados (ej. 9596).

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
            'sucursal',
        )
        .prefetch_related(
            'pagos',
            'cotizacion__piezas_cotizadas__componente',
            'venta_mostrador__piezas_vendidas',
        )
        .filter(pk__in=coincidencias)
    )


def resolver_documento(web_id: str) -> DocumentoFiscalOrden:
    """
    Del texto que tecleó el cliente al documento fiscal exacto.

    Objetivo de negocio:
        Es el corazón del GET y del PUT. Encuentra la orden, recalcula qué
        se puede facturar hoy y devuelve el documento que corresponde al
        webId recibido.

    Args:
        web_id: fragmento de URL ('SAT9596-1').

    Returns:
        DocumentoFiscalOrden listo para armar el payload.

    Raises:
        FacturacionDemandaError: 400 si el webId es inválido o ambiguo,
        404 si no existe folio o todavía no hay nada facturable.

    Efectos secundarios:
        Recalcula y guarda los documentos de la orden (ver
        facturacion_documentos.sincronizar_documentos_orden).
    """
    if _codigo_pais() != 'MX':
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SOLO_MEXICO)

    partes = partes_web_id(web_id)

    # Paso 1: buscar por los dígitos del folio (OOW-9596 → 9596).
    ordenes = buscar_ordenes_por_web_id(partes.numero)
    if not ordenes:
        raise FacturacionDemandaError(404, MENSAJE_NO_ENCONTRADO, MENSAJE_NO_ENCONTRADO)

    # Paso 2: si hay varias, el prefijo de sucursal desempata (SAT vs DROP).
    ordenes = filtrar_ordenes_por_prefijo(ordenes, partes.prefijo)
    if len(ordenes) > 1:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_COLISION)

    orden = ordenes[0]
    if not aplica_autofacturacion(orden):
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_NO_FACTURABLE)

    # Paso 3: recalcular. Si el cliente acaba de pagar, su documento nace aquí.
    documentos = sincronizar_documentos_orden(orden)
    if not documentos:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SIN_PAGOS)

    # Paso 4: el sufijo del webId elige el documento. Sin sufijo solo
    # funciona si hay uno nada más (si no, no adivinamos: pedimos el tipo).
    if partes.tipo is not None:
        for documento in documentos:
            if documento.tipo == partes.tipo:
                return documento
        raise FacturacionDemandaError(404, MENSAJE_NO_ENCONTRADO, MENSAJE_NO_ENCONTRADO)

    if len(documentos) > 1:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_TIPO_AMBIGUO)
    return documentos[0]


def _forma_pago(documento: DocumentoFiscalOrden) -> str:
    """
    Clave c_FormaPago del SAT a partir de los abonos de ESE documento.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El diagnóstico puede entrar con débito y el anticipo por transferencia.
    Cada factura mira solo su bolsillo, para no marcar las dos como mixtas.

    Args:
        documento: DocumentoFiscalOrden ya resuelto.

    Returns:
        str: '03' transferencia, '04' crédito, '28' débito, '01' efectivo
        histórico, '99' si en ese bolsillo se mezclaron métodos.
    """
    pagos = pagos_confirmados_del_documento(documento.orden, documento.tipo)
    metodos = {pago.metodo for pago in pagos}
    if not metodos:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SIN_PAGOS)
    # Paso: un solo método → su clave SAT; mezclados → 99 (por definir).
    if len(metodos) > 1:
        return '99'
    forma = MAPEO_FORMA_PAGO.get(next(iter(metodos)))
    if not forma:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_PAGO_INVALIDO)
    return forma


def _concepto_json(concepto, indice: int) -> dict[str, Any]:
    """
    Traduce un ConceptoDocumentoFiscal al renglón que espera VO.

    Args:
        concepto: ConceptoDocumentoFiscal guardado.
        indice: posición (para la clave interna del cliente).

    Returns:
        dict con las llaves exactas del contrato SICSER 4.
    """
    return {
        'clave_producto_servicio': concepto.clave_sat,
        'descripcion': concepto.descripcion,
        'clave_unidad': concepto.clave_unidad,
        'precio': _a_float(concepto.precio_unitario),
        'numero_identificacion': 'None',
        'unidad': concepto.clave_unidad,
        'objeto_impuesto': OBJETO_IMPUESTO,
        'impuestos': IMPUESTOS_IVA,
        'empresa': EMPRESA_EMISORA,
        'clave_producto_cliente': f'S{indice:04d}',
        'cantidad': _a_float(concepto.cantidad),
        'descuento': 0,
    }


def armar_payload_documento(documento: DocumentoFiscalOrden) -> dict[str, Any]:
    """
    JSON de la venta listo para el GET (encabezado + conceptos).

    EXPLICACIÓN PARA PRINCIPIANTES:
    El encabezado trae el IVA desglosado (subtotal, iva, total) para que el
    portal no tenga que calcular nada y para que Contabilidad pueda cuadrar
    contra SIGMA sin abrir el XML.

    Args:
        documento: DocumentoFiscalOrden ya resuelto.

    Returns:
        dict con 'encabezado' y 'conceptos'.

    Efectos secundarios:
        Lee la orden y sus pagos. No escribe.
    """
    orden = documento.orden

    ultimo_pago = orden.pagos.order_by('-fecha_pago').first()
    fecha_ticket = ultimo_pago.fecha_pago if ultimo_pago else timezone.now()

    try:
        folio_visible = (orden.detalle_equipo.orden_cliente or '').strip()
    except Exception:
        folio_visible = ''
    if not folio_visible:
        folio_visible = orden.numero_orden_interno

    conceptos = [
        _concepto_json(concepto, indice)
        for indice, concepto in enumerate(documento.conceptos.all(), start=1)
    ]
    if not conceptos:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_SIN_PAGOS)

    return {
        'encabezado': {
            'fecha_ticket': fecha_ticket.isoformat(),
            'folio': folio_visible,
            'web_id': documento.web_id,
            # 1 = PUE, 2 = PPD (estructura escalable pedida por VO).
            'tipo_factura': documento.codigo_tipo,
            'metodo_pago': METODO_PAGO_SAT[documento.tipo],
            'forma_pago': _forma_pago(documento),
            'moneda': documento.moneda or MONEDA_DEFAULT,
            'subtotal': _a_float(documento.subtotal),
            'tasa_iva': float(documento.tasa_iva),
            'iva': _a_float(documento.iva),
            'total': _a_float(documento.total),
        },
        'conceptos': conceptos,
    }


def obtener_venta_para_facturar(web_id: str) -> dict[str, Any]:
    """
    Punto de entrada del GET: resuelve el documento y arma el JSON.

    Args:
        web_id: fragmento de URL ('SAT9596-1').

    Returns:
        dict: payload para el portal VO.

    Efectos secundarios:
        Sincroniza documentos y marca `solicitado_en` (reserva para el PUT).
    """
    documento = resolver_documento(web_id)
    payload = armar_payload_documento(documento)
    # Paso: el contrato exige GET antes del PUT. Guardamos la "reserva".
    marcar_solicitud_facturacion(documento)
    return payload


def marcar_solicitud_facturacion(documento: DocumentoFiscalOrden) -> None:
    """
    Anota que el portal ya consultó este documento (requisito del PUT).

    Args:
        documento: DocumentoFiscalOrden consultado.

    Efectos secundarios:
        Escribe `solicitado_en` la primera vez.
    """
    if documento.solicitado_en:
        return
    db_alias = _db_de(documento.orden)
    documento.solicitado_en = timezone.now()
    documento.save(using=db_alias, update_fields=['solicitado_en', 'actualizado_en'])


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
        web_id: webId del path ('SAT9596-1').
        payload: JSON del portal VO (uuid, cfdi, pdf64, …).

    Efectos secundarios:
        Escribe archivos en media, UUID en DocumentoFiscalOrden y
        factura_emitida=True en la orden.
    """
    if not isinstance(payload, dict):
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_PAYLOAD_CFDI)

    documento = resolver_documento(web_id)
    orden = documento.orden

    uuid_sat = str(payload.get('uuid') or '').strip()
    if not uuid_sat or len(uuid_sat) > 36:
        raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_PAYLOAD_CFDI)

    xml_bytes = _bytes_campo_base64(payload.get('cfdi'), permitir_xml=True)
    pdf_bytes = _bytes_campo_base64(payload.get('pdf64'), permitir_xml=False)
    fecha_timbrado = _parse_fecha_timbrado(payload.get('fechaTimbrado'))
    nombre_base = re.sub(r'[^0-9A-Fa-f-]', '', uuid_sat) or 'cfdi'

    db_alias = _db_de(orden)
    with transaction.atomic(using=db_alias):
        bloqueado = (
            DocumentoFiscalOrden.objects.using(db_alias)
            .select_for_update()
            .get(pk=documento.pk)
        )

        if not bloqueado.solicitado_en:
            raise FacturacionDemandaError(
                404, MENSAJE_NO_ENCONTRADO, RAZON_SIN_GET_PREVIO
            )

        # Paso: mismo UUID otra vez = el portal reintentó; no duplicamos.
        if bloqueado.esta_timbrado:
            if bloqueado.uuid == uuid_sat:
                return
            raise FacturacionDemandaError(400, MENSAJE_BAD_REQUEST, RAZON_YA_TIMBRADA)

        bloqueado.uuid = uuid_sat
        bloqueado.fecha_timbrado = fecha_timbrado
        bloqueado.cadena_original_sat = str(payload.get('cadenaOriginalSAT') or '')
        bloqueado.no_certificado_sat = str(payload.get('noCertificadoSAT') or '')[:40]
        bloqueado.no_certificado_cfdi = str(payload.get('noCertificadoCFDI') or '')[:40]
        bloqueado.sello_sat = str(payload.get('selloSAT') or '')
        bloqueado.sello_cfdi = str(payload.get('selloCFDI') or '')
        bloqueado.qr_code = str(payload.get('qrCode') or '')
        bloqueado.recibido_en = timezone.now()
        bloqueado.cfdi_xml.save(
            f'{nombre_base}.xml',
            ContentFile(xml_bytes),
            save=False,
        )
        bloqueado.pdf.save(
            f'{nombre_base}.pdf',
            ContentFile(pdf_bytes),
            save=False,
        )
        bloqueado.save(using=db_alias)

        # Paso: la orden queda "facturada" solo cuando YA NO queda ningún
        # documento suyo sin timbrar. Si tiene PUE y PPD y apenas se timbró
        # uno, el cliente todavía debe poder facturar el otro.
        quedan_pendientes = (
            DocumentoFiscalOrden.objects.using(db_alias)
            .filter(orden=orden, uuid='')
            .exists()
        )
        if not quedan_pendientes:
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


def contexto_autofactura_seguimiento(orden: OrdenServicio) -> dict[str, Any]:
    """
    Datos del bloque de autofactura en el enlace de seguimiento del cliente.

    Objetivo de negocio:
        Mostrarle al cliente su `webId` y el enlace al portal VO. El cliente
        NO ve API Key ni secret: esos solo viajan servidor a servidor.

    Args:
        orden: OrdenServicio del enlace público.

    Returns:
        dict con:
            mostrar_autofactura: si se pinta el bloque.
            documentos: lista de dicts (web_id, tipo, descripcion, total).
            url_autofactura: enlace al portal (con webId si hay uno solo).
            factura_ya_emitida: si ya se timbró.

    Efectos secundarios:
        Recalcula los documentos de la orden (puede crear filas nuevas).
    """
    oculto = {
        'mostrar_autofactura': False,
        'documentos': [],
        'url_autofactura': '',
        'factura_ya_emitida': False,
    }
    # Paso 1: CFDI solo México; el portal VO no aplica a otros países.
    if _codigo_pais() != 'MX':
        return oculto
    if not aplica_autofacturacion(orden):
        return oculto

    # Paso 2: recalcular qué puede facturar hoy (aquí nacen los webId).
    documentos = sincronizar_documentos_orden(orden)
    if not documentos:
        return oculto

    # Paso 3: solo ofrecemos los que aún no tienen UUID del SAT.
    pendientes = [
        documento for documento in documentos if not documento.esta_timbrado
    ]
    # Si Facturación ya marcó la orden como facturada (por ejemplo, la
    # emitieron por fuera del portal) o ya no queda nada por timbrar,
    # avisamos en lugar de mandarlo otra vez al facturador.
    if orden.factura_emitida or not pendientes:
        return {
            'mostrar_autofactura': True,
            'documentos': [],
            'url_autofactura': '',
            'factura_ya_emitida': True,
        }
    documentos = pendientes

    portal = (getattr(settings, 'FACTURACION_WEB_PORTAL_URL', '') or '').rstrip('/')
    if not portal:
        return oculto

    datos = [
        {
            'web_id': documento.web_id,
            'tipo': documento.get_tipo_display(),
            'descripcion': documento.descripcion,
            'total': documento.total,
        }
        for documento in documentos
    ]

    # Paso 4: con un solo documento precargamos el webId en la URL; con dos
    # el cliente elige en el portal cuál quiere facturar.
    if len(documentos) == 1:
        url = f'{portal}?{urlencode({"webId": documentos[0].web_id})}'
    else:
        url = portal

    return {
        'mostrar_autofactura': True,
        'documentos': datos,
        'url_autofactura': url,
        'factura_ya_emitida': False,
    }
