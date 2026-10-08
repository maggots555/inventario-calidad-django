"""
Frase del clima para el saludo del inicio.

EXPLICACIÓN PARA PRINCIPIANTES:
El dashboard ya dice "Buenos días, Jorge". Este módulo le agrega una cola
según el pronóstico de hoy, por ejemplo "hoy nos espera un día lluvioso".

De dónde sale la ciudad:
  1. La sucursal del empleado (campo ciudad).
  2. Si no hay empleado, sucursal o ciudad, la capital del país activo
     (Ciudad de México, Buenos Aires, Santiago o Bogotá).

No usa llave de API. Pregunta a Open-Meteo (pronóstico público) y guarda
la respuesta en el caché de Django para no consultar en cada recarga.
Si el servicio no contesta, devolvemos texto vacío y el saludo se queda igual.
"""

import json
import logging
import re
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from django.core.cache import cache

logger = logging.getLogger(__name__)

# Segundos que esperamos a Open-Meteo antes de rendirnos.
# El inicio no debe quedarse colgado si el servicio está lento.
_TIMEOUT_SEGUNDOS = 2.5

# La sucursal no se mueve: las coordenadas se recuerdan un mes.
_CACHE_COORDENADAS_SEG = 30 * 24 * 60 * 60

# El clima del día cambia, así que la frase se refresca cada 3 horas.
_CACHE_FRASE_SEG = 3 * 60 * 60

# Si la red falla, no insistimos en cada visita al inicio.
_CACHE_FALLO_SEG = 15 * 60

# Tope de la respuesta. Un pronóstico normal pesa unos pocos KB.
# Si alguien manda un archivo enorme, no lo cargamos en memoria.
_MAX_BYTES_RESPUESTA = 65_536

# Umbrales en grados Celsius de la temperatura máxima del día.
# La lluvia, la nieve y la tormenta ganan: un día de 32° con lluvia
# se dice "lluvioso", no "caluroso".
_UMBRAL_CALUROSO = 30.0
_UMBRAL_FRIO = 12.0

# Códigos WMO que devuelve Open-Meteo (weather_code).
# https://open-meteo.com/en/docs  — tabla "WMO Weather interpretation codes"
_CODIGOS_TORMENTA = {95, 96, 99}
_CODIGOS_LLUVIA = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82}
_CODIGOS_NIEVE = {71, 73, 75, 77, 85, 86}
_CODIGOS_NIEBLA = {45, 48}
_CODIGOS_DESPEJADO = {0, 1}
_CODIGOS_NUBLADO = {2, 3}

# Coordenadas fijas de la capital. Sirven de respaldo cuando la sucursal
# no trae ciudad o cuando el buscador de ciudades no reconoce el nombre.
_CAPITALES = {
    'MX': {
        'nombre': 'Ciudad de México',
        'latitud': 19.4326,
        'longitud': -99.1332,
    },
    'AR': {
        'nombre': 'Buenos Aires',
        'latitud': -34.6037,
        'longitud': -58.3816,
    },
    'CL': {
        'nombre': 'Santiago',
        'latitud': -33.4489,
        'longitud': -70.6693,
    },
    'CO': {
        'nombre': 'Bogotá',
        'latitud': 4.7110,
        'longitud': -74.0721,
    },
}

_URL_GEO = 'https://geocoding-api.open-meteo.com/v1/search'
_URL_PRONOSTICO = 'https://api.open-meteo.com/v1/forecast'


def frase_clima_para_usuario(user) -> str:
    """
    Arma la frase del clima para el saludo de este usuario.

    Objetivo: que el inicio pueda decir "hoy nos espera un día lluvioso"
    según la sucursal de quien entró.

    Args:
        user: usuario de Django ya autenticado (request.user).

    Returns:
        str: frase lista para pegar después del nombre, o '' si no hubo clima.
             Nunca lanza error hacia la vista: un fallo de red no tumba el inicio.

    Efectos secundarios:
        Lee y escribe el caché de Django. Puede hacer hasta dos peticiones HTTP
        (buscar la ciudad y pedir el pronóstico) si todavía no hay nada guardado.
    """
    try:
        from config.paises_config import get_pais_actual

        pais = get_pais_actual()
        lugar = resolver_lugar(user, pais)
        fecha = _fecha_local(lugar['timezone'])
        # Paso 1: si ya armamos esta frase hoy, la devolvemos sin salir a Internet.
        clave_ciudad = _clave_frase(lugar['codigo_pais'], lugar['nombre'], fecha)
        frase_guardada = cache.get(clave_ciudad)
        if frase_guardada is not None:
            return frase_guardada

        # Paso 2: coordenadas. Si la ciudad no se encuentra, caemos a la capital.
        # None aquí es otra cosa: la red falló. No inventamos el clima de la capital.
        coordenadas = _coordenadas(lugar)
        if coordenadas is None:
            cache.set(clave_ciudad, '', _CACHE_FALLO_SEG)
            return ''

        latitud, longitud, nombre_efectivo = coordenadas
        clave = _clave_frase(lugar['codigo_pais'], nombre_efectivo, fecha)
        if clave != clave_ciudad:
            frase_capital = cache.get(clave)
            if frase_capital is not None:
                return frase_capital

        # Paso 3: pronóstico de hoy y traducción a una frase corta.
        pronostico = _consultar_pronostico(latitud, longitud, lugar['timezone'])
        if pronostico is None:
            cache.set(clave, '', _CACHE_FALLO_SEG)
            return ''

        codigo_tiempo, temperatura_max = pronostico
        frase = frase_desde_codigo(codigo_tiempo, temperatura_max)
        cache.set(clave, frase, _CACHE_FRASE_SEG)
        return frase
    except Exception:
        # Cualquier sorpresa (país mal configurado, caché caído) deja el saludo quieto.
        logger.exception('[ClimaSaludo] No se pudo armar la frase del clima')
        return ''


def resolver_lugar(user, pais: dict) -> dict:
    """
    Elige la ciudad cuyo clima vamos a consultar.

    Args:
        user: usuario de Django. Puede no tener empleado ligado.
        pais: dict de get_pais_actual() (codigo, timezone, etc.).

    Returns:
        dict con nombre, es_capital, codigo_pais y timezone.
    """
    codigo = (pais or {}).get('codigo') or 'MX'
    timezone_nombre = (pais or {}).get('timezone') or 'America/Mexico_City'
    capital = _capital(codigo)

    # user.empleado es un OneToOne. Si este usuario no es empleado,
    # Django lanza un error al leerlo; getattr lo convierte en None.
    empleado = getattr(user, 'empleado', None)
    sucursal = getattr(empleado, 'sucursal', None) if empleado is not None else None
    ciudad = ''
    if sucursal is not None:
        ciudad = (sucursal.ciudad or '').strip()

    if not ciudad:
        return {
            'nombre': capital['nombre'],
            'es_capital': True,
            'codigo_pais': codigo,
            'timezone': timezone_nombre,
        }

    return {
        'nombre': ciudad,
        'es_capital': False,
        'codigo_pais': codigo,
        'timezone': timezone_nombre,
    }


def frase_desde_codigo(codigo_tiempo: int, temperatura_max: float | None) -> str:
    """
    Traduce el código del tiempo y la máxima del día a una frase en español.

    Args:
        codigo_tiempo: weather_code de Open-Meteo (entero WMO).
        temperatura_max: máxima del día en °C, o None si no vino.

    Returns:
        str: por ejemplo "hoy nos espera un día lluvioso".
    """
    # Primero lo que se siente al salir: agua, nieve, niebla o tormenta.
    if codigo_tiempo in _CODIGOS_TORMENTA:
        como_esta = 'con tormentas'
    elif codigo_tiempo in _CODIGOS_LLUVIA:
        como_esta = 'lluvioso'
    elif codigo_tiempo in _CODIGOS_NIEVE:
        como_esta = 'con nieve'
    elif codigo_tiempo in _CODIGOS_NIEBLA:
        como_esta = 'con niebla'
    elif temperatura_max is not None and temperatura_max >= _UMBRAL_CALUROSO:
        como_esta = 'caluroso'
    elif temperatura_max is not None and temperatura_max <= _UMBRAL_FRIO:
        como_esta = 'frío'
    elif codigo_tiempo in _CODIGOS_DESPEJADO:
        como_esta = 'soleado'
    elif codigo_tiempo in _CODIGOS_NUBLADO:
        como_esta = 'nublado'
    else:
        # Código que no reconocemos: una frase neutra, sin inventar el clima.
        como_esta = 'variable'

    return f'hoy nos espera un día {como_esta}'


def _capital(codigo_pais: str) -> dict:
    """
    Datos fijos de la capital. Si el código no está en la tabla, México.

    Args:
        codigo_pais: ISO de dos letras (MX, AR, CL, CO).

    Returns:
        dict con nombre, latitud y longitud.
    """
    return _CAPITALES.get(codigo_pais, _CAPITALES['MX'])


def _clave_ciudad(nombre: str) -> str:
    """
    Vuelve el nombre de la ciudad seguro para usarlo como llave de caché.

    "Ciudad de México" y "ciudad de mexico" terminan en la misma llave.

    Args:
        nombre: ciudad tal como está en la sucursal o en la tabla de capitales.

    Returns:
        str: solo letras minúsculas, números y guiones bajos.
    """
    sin_acentos = unicodedata.normalize('NFKD', nombre or '')
    sin_acentos = ''.join(
        caracter for caracter in sin_acentos if not unicodedata.combining(caracter)
    )
    limpio = re.sub(r'[^a-z0-9]+', '_', sin_acentos.lower()).strip('_')
    return limpio or 'sin_ciudad'


def _clave_frase(codigo_pais: str, nombre_ciudad: str, fecha: str) -> str:
    """
    Llave del caché de la frase: país + ciudad + día local.

    Args:
        codigo_pais: MX, AR, CL o CO.
        nombre_ciudad: ciudad efectiva (sucursal o capital).
        fecha: día local en formato AAAA-MM-DD.

    Returns:
        str: clave para cache.get / cache.set.
    """
    return f'clima_frase_{codigo_pais}_{_clave_ciudad(nombre_ciudad)}_{fecha}'


def _fecha_local(timezone_nombre: str) -> str:
    """
    Día de hoy en la zona horaria del país, no en UTC.

    Args:
        timezone_nombre: por ejemplo America/Mexico_City.

    Returns:
        str: fecha AAAA-MM-DD.
    """
    try:
        zona = ZoneInfo(timezone_nombre)
    except Exception:
        zona = ZoneInfo('America/Mexico_City')
    return datetime.now(zona).date().isoformat()


def _coordenadas(lugar: dict) -> tuple[float, float, str] | None:
    """
    Latitud y longitud de la ciudad, o las de la capital si no se pudo ubicar.

    Args:
        lugar: dict que devolvió resolver_lugar.

    Returns:
        tuple (latitud, longitud, nombre_efectivo), o None si la red falló.
        nombre_efectivo cambia a la capital solo cuando el buscador contestó
        y no conoce la ciudad. Un timeout no cuenta como "ciudad desconocida":
        si no, Guadalajara vería el clima de la capital durante 15 minutos.
    """
    codigo = lugar['codigo_pais']
    capital = _capital(codigo)
    if lugar['es_capital']:
        return capital['latitud'], capital['longitud'], capital['nombre']

    clave_coords = f"clima_coords_{codigo}_{_clave_ciudad(lugar['nombre'])}"
    crudas = cache.get(clave_coords)
    guardadas = _coords_validas(crudas)
    if guardadas is not None:
        return guardadas[0], guardadas[1], lugar['nombre']
    # Un dato viejo o a medias no se reutiliza: se vuelve a pedir.
    if crudas is not None:
        cache.delete(clave_coords)

    # Un nombre que Open-Meteo no reconoció se recuerda poco tiempo
    # para no preguntar lo mismo en cada visita al inicio.
    clave_fallo = f"clima_geo_miss_{codigo}_{_clave_ciudad(lugar['nombre'])}"
    if cache.get(clave_fallo):
        return capital['latitud'], capital['longitud'], capital['nombre']

    encontradas, red_ok = _geocodificar(lugar['nombre'], codigo)
    if not red_ok:
        # No se marca la ciudad como desconocida. El siguiente intento
        # (después del caché de fallo de la frase) vuelve a buscarla.
        return None
    if encontradas is None:
        cache.set(clave_fallo, True, _CACHE_FALLO_SEG)
        logger.warning(
            '[ClimaSaludo] No se ubicó la ciudad "%s" (%s); se usa la capital',
            lugar['nombre'],
            codigo,
        )
        return capital['latitud'], capital['longitud'], capital['nombre']

    cache.set(clave_coords, encontradas, _CACHE_COORDENADAS_SEG)
    return encontradas['latitud'], encontradas['longitud'], lugar['nombre']


def _coords_validas(guardadas) -> tuple[float, float] | None:
    """
    Revisa que lo guardado en caché sean coordenadas de verdad.

    Args:
        guardadas: lo que devolvió cache.get. Puede no ser un dict.

    Returns:
        tuple (latitud, longitud) o None si el dato no sirve.
    """
    if not isinstance(guardadas, dict):
        return None
    try:
        latitud = float(guardadas['latitud'])
        longitud = float(guardadas['longitud'])
    except (KeyError, TypeError, ValueError):
        return None
    # Fuera de este rango no existe un punto en el mapa.
    if not (-90.0 <= latitud <= 90.0 and -180.0 <= longitud <= 180.0):
        return None
    return latitud, longitud


def _geocodificar(ciudad: str, codigo_pais: str) -> tuple[dict | None, bool]:
    """
    Pide a Open-Meteo la latitud y longitud de un nombre de ciudad.

    Args:
        ciudad: texto libre de la sucursal, por ejemplo "Guadalajara".
        codigo_pais: limita la búsqueda a ese país (MX, AR, CL, CO).

    Returns:
        tuple (coordenadas, red_ok):
        - (dict, True) si se ubicó la ciudad.
        - (None, True) si el servicio contestó y no la conoce.
        - (None, False) si la red falló. Eso no es lo mismo que "no existe".
    """
    consulta = urlencode({
        'name': ciudad,
        'count': 1,
        'language': 'es',
        'format': 'json',
        'countryCode': codigo_pais,
    })
    datos = _leer_json(f'{_URL_GEO}?{consulta}')
    if datos is None:
        return None, False

    # La API manda una lista "results". Nos quedamos con el primer match.
    resultados = datos.get('results') or []
    if not resultados:
        return None, True

    primero = resultados[0]
    try:
        latitud = float(primero['latitude'])
        longitud = float(primero['longitude'])
    except (KeyError, TypeError, ValueError):
        return None, True
    if not (-90.0 <= latitud <= 90.0 and -180.0 <= longitud <= 180.0):
        return None, True
    return {'latitud': latitud, 'longitud': longitud}, True


def _consultar_pronostico(
    latitud: float,
    longitud: float,
    timezone_nombre: str,
) -> tuple[int, float | None] | None:
    """
    Pide el código del tiempo y la máxima de hoy.

    Args:
        latitud: grados, norte positivo.
        longitud: grados, este positivo.
        timezone_nombre: zona del país, para que "hoy" sea el día local.

    Returns:
        tuple (codigo_tiempo, temperatura_max) o None si la respuesta no sirve.
    """
    consulta = urlencode({
        'latitude': f'{latitud:.4f}',
        'longitude': f'{longitud:.4f}',
        'daily': 'weather_code,temperature_2m_max',
        'timezone': timezone_nombre,
        'forecast_days': 1,
    })
    datos = _leer_json(f'{_URL_PRONOSTICO}?{consulta}')
    if not datos:
        return None

    # daily.weather_code y daily.temperature_2m_max son listas de un solo día.
    diario = datos.get('daily') or {}
    codigos = diario.get('weather_code') or []
    temperaturas = diario.get('temperature_2m_max') or []
    if not codigos:
        return None

    try:
        codigo = int(codigos[0])
    except (TypeError, ValueError):
        return None

    temperatura_max = None
    if temperaturas and temperaturas[0] is not None:
        try:
            temperatura_max = float(temperaturas[0])
        except (TypeError, ValueError):
            temperatura_max = None

    return codigo, temperatura_max


def _leer_json(url: str) -> dict | None:
    """
    Descarga una URL y la interpreta como JSON.

    Args:
        url: dirección completa, ya con los parámetros.

    Returns:
        dict con la respuesta, o None si hubo timeout, error HTTP o JSON inválido.

    Efectos secundarios:
        Una petición HTTP de como máximo _TIMEOUT_SEGUNDOS. No escribe en la BD.
    """
    peticion = urllib.request.Request(
        url,
        headers={'User-Agent': 'SIGMA-clima-saludo/1.0'},
    )
    try:
        with urllib.request.urlopen(peticion, timeout=_TIMEOUT_SEGUNDOS) as respuesta:
            # +1 para detectar que se pasó del tope sin leer el archivo entero.
            cuerpo = respuesta.read(_MAX_BYTES_RESPUESTA + 1)
        if len(cuerpo) > _MAX_BYTES_RESPUESTA:
            logger.warning('[ClimaSaludo] Open-Meteo contestó con un cuerpo demasiado grande')
            return None
        datos = json.loads(cuerpo.decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError) as exc:
        logger.warning('[ClimaSaludo] Open-Meteo no respondió: %s', exc)
        return None
    # Una lista o un texto no traen "results" ni "daily". Lo tratamos como fallo.
    if not isinstance(datos, dict):
        logger.warning('[ClimaSaludo] Open-Meteo contestó con un JSON que no es un objeto')
        return None
    return datos
