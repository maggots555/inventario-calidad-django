"""
Prueba el GET del autofacturador contra un webId real de la base.

Objetivo de negocio:
    Antes de que el portal VO apunte a SIGMA, necesitamos comprobar con
    nuestros propios datos que un webId (por ejemplo `DROP12092-1`) responde
    con el JSON que el proveedor espera: encabezado, conceptos y totales.

EXPLICACIÓN PARA PRINCIPIANTES — los dos modos y por qué existen:
    --solo-lectura (default): arma el mismo JSON pero NO marca la reserva.
        Sirve para mirar los datos cuantas veces quieras sin alterar nada.
    --http: recorre el camino completo y real (POST authenticate → GET folio)
        usando el cliente de pruebas de Django, que ejercita las URLs, la
        API Key y el JWT igual que lo hará VO. Este SÍ marca `solicitado_en`,
        que es justamente el requisito para que después se acepte el PUT.

    El modo --http no necesita `runserver`: el cliente de pruebas llama a la
    aplicación directamente, pero contra la base de datos real.

    --url=https://…: pregunta a un servidor REAL por la red (producción o
        staging). Úsalo cuando la orden no vive en esta computadora. Manda
        las credenciales del .env local; si el servidor usa otras, responde
        401 sin haber cambiado nada.

Uso:
    python scripts/verificacion/probar_webid_facturacion.py DROP12092-1
    python scripts/verificacion/probar_webid_facturacion.py DROP12092-1 --http
    python scripts/verificacion/probar_webid_facturacion.py GDL3430-1 \\
        --url=https://mexico.sigmasystem.work

Efectos secundarios:
    En modo --http y --url escribe `solicitado_en` del documento (una sola
    vez). En modo solo lectura, ninguno.
"""

import json
import os
import sys
from pathlib import Path

import django

# EXPLICACIÓN PARA PRINCIPIANTES:
# Python busca los módulos en la carpeta del script, que aquí es
# scripts/verificacion/. Como necesitamos importar `config` y las apps,
# agregamos la raíz del proyecto (dos niveles arriba) a la lista de rutas.
RAIZ_PROYECTO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ_PROYECTO))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings  # noqa: E402

from servicio_tecnico.services.facturacion_demanda import (  # noqa: E402
    FacturacionDemandaError,
    armar_payload_documento,
    credenciales_configuradas,
    resolver_documento,
)


SEPARADOR = '=' * 70


def _imprimir_json(titulo: str, datos) -> None:
    """Muestra un bloque JSON legible, con acentos tal cual."""
    print(f'\n--- {titulo} ---')
    print(json.dumps(datos, indent=2, ensure_ascii=False, default=str))


def probar_solo_lectura(web_id: str) -> bool:
    """
    Arma el payload sin marcar la reserva.

    Args:
        web_id: identificador que teclea el cliente en el portal.

    Returns:
        bool: True si se pudo armar el JSON.

    Efectos secundarios:
        Ninguno: no escribe en la base.
    """
    print(SEPARADOR)
    print(f'MODO SOLO LECTURA — webId: {web_id}')
    print(SEPARADOR)

    try:
        documento = resolver_documento(web_id)
    except FacturacionDemandaError as exc:
        # Paso: este es el mismo error que recibiría VO, con su código HTTP.
        print(f'\n[X] SIGMA respondería {exc.http_status}: {exc.mensaje}')
        if exc.razon:
            print(f'    Razón: {exc.razon}')
        return False

    # Paso: datos de contexto que ayudan a entender QUÉ se está facturando.
    orden = documento.orden
    print(f'\n[OK] Documento encontrado')
    print(f'     Orden interna : {orden.numero_orden_interno}')
    print(f'     Tipo          : {documento.get_tipo_display()}')
    print(f'     Reservado el  : {documento.solicitado_en or "todavía no"}')
    # Paso: con UUID el CFDI ya está timbrado y no se puede volver a facturar.
    print(f'     Ya timbrado   : {"sí, UUID " + documento.uuid if documento.uuid else "no"}')
    print(f'     Subtotal      : ${documento.subtotal}')
    print(f'     IVA           : ${documento.iva}')
    print(f'     Total         : ${documento.total}')

    payload = armar_payload_documento(documento)
    _imprimir_json('JSON que recibiría el portal VO', payload)
    return True


def probar_http(web_id: str, host: str) -> bool:
    """
    Recorre authenticate + GET folio como lo hará el portal VO.

    Args:
        web_id: identificador a consultar.
        host: dominio con el que se simula la petición. Importa porque
            SIGMA es multi-país: el subdominio decide en qué base busca
            (`mexico.localhost` → México). Debe estar en ALLOWED_HOSTS.

    Returns:
        bool: True si el GET respondió 200.

    Efectos secundarios:
        Marca `solicitado_en` en el documento (reserva para el PUT).
    """
    from django.test import Client
    from django.test.utils import override_settings

    print('\n' + SEPARADOR)
    print(f'MODO HTTP REAL — webId: {web_id}')
    print(SEPARADOR)

    # Paso 1: sin credenciales configuradas el API responde 401 a todo.
    if not credenciales_configuradas():
        print('\n[X] Faltan FACTURACION_WEB_API_KEY / FACTURACION_WEB_SECRET '
              'en el .env. El API respondería 401.')
        return False

    api_key = settings.FACTURACION_WEB_API_KEY
    secret = settings.FACTURACION_WEB_SECRET
    # SERVER_NAME simula el dominio: sin esto Django rechaza con DisallowedHost
    # y, además, el middleware de país no sabría en qué base buscar la orden.
    cliente = Client(SERVER_NAME=host)
    print(f'     (simulando dominio: {host})')

    # EXPLICACIÓN PARA PRINCIPIANTES:
    # El API limita las peticiones por IP (30/min) y responde 403 al bloquear.
    # Como aquí probamos el contrato una y otra vez desde la misma máquina,
    # apagamos ese límite SOLO durante esta ejecución. En producción sigue
    # activo: es lo que evita que alguien pruebe webIds al azar.
    with override_settings(RATELIMIT_ENABLE=False):
        # Paso 2: login del portal. Devuelve el JWT de corta duración.
        respuesta_auth = cliente.post(
            '/facturacion-web/authenticate',
            data=json.dumps({'secret': secret}),
            content_type='application/json',
            HTTP_X_API_KEY=api_key,
        )
        print(f'\nPOST /facturacion-web/authenticate → {respuesta_auth.status_code}')
        if respuesta_auth.status_code != 200:
            print(respuesta_auth.content.decode('utf-8', errors='replace')[:400])
            return False

        token = json.loads(respuesta_auth.content)['access_token']
        print(f'     access_token recibido ({len(token)} caracteres)')

        # Paso 3: la consulta real. Esto es lo que dispara el cliente al
        # teclear su webId en el portal del proveedor.
        respuesta_get = cliente.get(
            f'/facturacion-web/folio/{web_id}',
            HTTP_X_API_KEY=api_key,
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        print(f'\nGET /facturacion-web/folio/{web_id} → {respuesta_get.status_code}')

    cuerpo = json.loads(respuesta_get.content)
    _imprimir_json('Respuesta HTTP', cuerpo)
    return respuesta_get.status_code == 200


def probar_remoto(web_id: str, base_url: str) -> bool:
    """
    Consulta un servidor real por la red (producción o staging).

    EXPLICACIÓN PARA PRINCIPIANTES — por qué existe este modo:
        Los otros dos modos hablan con la base de datos de ESTA computadora.
        Si la orden vive en el servidor de producción, aquí no está y siempre
        dará 404. Este modo hace exactamente lo que hará el portal VO: una
        petición HTTP por internet, con su API Key y su JWT.

    Args:
        web_id: identificador a consultar.
        base_url: raíz del servidor, ej. https://mexico.sigmasystem.work

    Returns:
        bool: True si el GET respondió 200.

    Efectos secundarios:
        ⚠️ Escribe en el servidor consultado: el GET marca `solicitado_en`
        (la reserva que el contrato exige antes del PUT).
    """
    import requests

    print('\n' + SEPARADOR)
    print(f'MODO REMOTO — {base_url}')
    print(f'webId: {web_id}')
    print(SEPARADOR)

    # Paso 1: las credenciales salen del .env de ESTA máquina. Si el servidor
    # remoto usa otras, la respuesta será 401 y no habrá pasado nada.
    api_key = os.environ.get('FACTURACION_WEB_API_KEY') or getattr(
        settings, 'FACTURACION_WEB_API_KEY', ''
    )
    secret = os.environ.get('FACTURACION_WEB_SECRET') or getattr(
        settings, 'FACTURACION_WEB_SECRET', ''
    )
    if not api_key or not secret:
        print('\n[X] No hay credenciales para autenticarse.')
        return False
    # Nunca imprimimos el secreto completo: solo lo suficiente para saber cuál es.
    print(f'\n     API Key usada: {api_key[:6]}… ({len(api_key)} caracteres)')

    raiz = base_url.rstrip('/')

    # Paso 2: login. Mismo contrato que en local.
    try:
        auth = requests.post(
            f'{raiz}/facturacion-web/authenticate',
            json={'secret': secret},
            headers={'X-API-KEY': api_key},
            timeout=20,
        )
    except requests.RequestException as exc:
        print(f'\n[X] No se pudo conectar: {exc}')
        return False

    print(f'\nPOST {raiz}/facturacion-web/authenticate → {auth.status_code}')
    if auth.status_code != 200:
        print(auth.text[:400])
        return False

    token = auth.json().get('access_token', '')
    print(f'     access_token recibido ({len(token)} caracteres)')

    # Paso 3: la consulta real contra el servidor remoto.
    get = requests.get(
        f'{raiz}/facturacion-web/folio/{web_id}',
        headers={
            'X-API-KEY': api_key,
            'Authorization': f'Bearer {token}',
        },
        timeout=20,
    )
    print(f'\nGET {raiz}/facturacion-web/folio/{web_id} → {get.status_code}')

    try:
        _imprimir_json('Respuesta del servidor', get.json())
    except ValueError:
        print(get.text[:600])
    return get.status_code == 200


def main() -> int:
    """Lee los argumentos y ejecuta el modo pedido."""
    argumentos = [arg for arg in sys.argv[1:] if not arg.startswith('--')]
    web_id = argumentos[0] if argumentos else 'DROP12092-1'
    con_http = '--http' in sys.argv

    # Host por defecto: el subdominio local de México (ver ALLOWED_HOSTS).
    host = 'mexico.localhost'
    base_url = ''
    for arg in sys.argv[1:]:
        if arg.startswith('--host='):
            host = arg.split('=', 1)[1]
        elif arg.startswith('--url='):
            base_url = arg.split('=', 1)[1]

    # Paso: contra un servidor remoto no tiene sentido leer la base local,
    # porque la orden vive en el otro lado.
    if base_url:
        return 0 if probar_remoto(web_id, base_url) else 1

    ok = probar_solo_lectura(web_id)

    if con_http:
        ok = probar_http(web_id, host) and ok
    else:
        print('\n(Para probar el flujo HTTP completo con API Key y JWT, '
              'vuelve a correrlo agregando --http)')

    print('\n' + SEPARADOR)
    print('RESULTADO: ' + ('todo respondió correctamente' if ok else 'hubo errores'))
    print(SEPARADOR)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
