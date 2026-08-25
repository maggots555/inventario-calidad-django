"""
API HTTP de facturación en demanda (portal VO → SIGMA).

Objetivo de negocio:
    Contrato SICSER 4: POST authenticate, GET folio (venta) y PUT folio
    (CFDI timbrado: XML + PDF).

Args/entrada:
    Headers X-API-KEY y Authorization Bearer.
    GET sin body. PUT JSON con uuid, cfdi, pdf64, etc.

Efectos secundarios:
    GET reserva la venta. PUT guarda archivos y marca factura_emitida.
"""

from __future__ import annotations

import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django_ratelimit.decorators import ratelimit

from servicio_tecnico.services.facturacion_demanda import (
    FacturacionDemandaError,
    credenciales_configuradas,
    emitir_access_token,
    obtener_venta_para_facturar,
    persistir_cfdi_timbrado,
    validar_access_token,
    validar_api_key,
    validar_secret_authenticate,
)

logger = logging.getLogger(__name__)


def _error(exc: FacturacionDemandaError) -> JsonResponse:
    """Body JSON uniforme para que el portal VO lea mensaje/razón."""
    payload = {'mensaje': exc.mensaje}
    if exc.razon:
        payload['razon'] = exc.razon
    return JsonResponse(payload, status=exc.http_status)


def _bearer_token(request) -> str:
    """
    Extrae el JWT del header Authorization: Bearer ….

    Args:
        request: HttpRequest de Django.
    """
    crudo = request.META.get('HTTP_AUTHORIZATION') or ''
    prefijo = 'Bearer '
    if crudo.startswith(prefijo):
        return crudo[len(prefijo):].strip()
    if crudo.lower().startswith('bearer '):
        return crudo[7:].strip()
    return ''


def _exigir_auth(request) -> None:
    """API Key + JWT, igual que el PDF (401 si falta alguno)."""
    if not credenciales_configuradas():
        raise FacturacionDemandaError(401, 'Unauthorized', 'API no configurada')
    validar_api_key(request.META.get('HTTP_X_API_KEY'))
    token = _bearer_token(request)
    if not token:
        raise FacturacionDemandaError(
            401,
            'Unauthorized',
            'No se envió API Key o Token en header o el token ha expirado',
        )
    validar_access_token(token)


@csrf_exempt
@ratelimit(key='ip', rate='30/m', method='POST', block=True)
@require_POST
def authenticate_facturacion_web(request):
    """
    POST /facturacion-web/authenticate

    Body: {"secret": "…"}. Header: X-API-KEY.
    Respuesta 200: {"access_token": "<jwt>"}.
    """
    try:
        if not credenciales_configuradas():
            raise FacturacionDemandaError(401, 'Unauthorized', 'API no configurada')
        validar_api_key(request.META.get('HTTP_X_API_KEY'))
        try:
            cuerpo = json.loads(request.body.decode('utf-8') or '{}')
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FacturacionDemandaError(
                400,
                'Bad Request',
                'Payload JSON inválido',
            ) from exc
        if not isinstance(cuerpo, dict):
            raise FacturacionDemandaError(400, 'Bad Request', 'Payload JSON inválido')
        validar_secret_authenticate(str(cuerpo.get('secret') or ''))
        return JsonResponse({'access_token': emitir_access_token()})
    except FacturacionDemandaError as exc:
        return _error(exc)


@csrf_exempt
@ratelimit(key='ip', rate='60/m', method=['GET', 'PUT'], block=True)
@require_http_methods(['GET', 'PUT'])
def folio_facturacion_web(request, web_id: str):
    """
    GET /facturacion-web/folio/{webId} → JSON de venta.
    PUT /facturacion-web/folio/{webId} → 204 y guarda XML/PDF.

    Headers: X-API-KEY + Authorization Bearer.
    """
    try:
        _exigir_auth(request)
        if request.method == 'GET':
            payload = obtener_venta_para_facturar(web_id)
            return JsonResponse(payload)

        try:
            cuerpo = json.loads(request.body.decode('utf-8') or '{}')
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise FacturacionDemandaError(
                400,
                'Bad Request',
                'Payload JSON inválido',
            ) from exc
        persistir_cfdi_timbrado(web_id, cuerpo)
        return HttpResponse(status=204)
    except FacturacionDemandaError as exc:
        logger.info(
            'Facturación en demanda %s web_id=%s status=%s razon=%s',
            request.method,
            web_id,
            exc.http_status,
            exc.razon,
        )
        return _error(exc)
