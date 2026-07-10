"""
Cliente de consulta para las APIs externas de SICSER (solo lectura — Fase 1).

Objetivo de negocio:
    Permitir a SIGMA listar órdenes OOW y de garantía en tiempo real y construir
    los hipervínculos del formato digital, sin crear registros en la base de datos.

Efectos secundarios:
    - Realiza peticiones HTTP GET hacia el servidor SICSER.
    - Puede escribir/leer caché en Redis vía django.core.cache (TTL corto).
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from decouple import config
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURACIÓN (variables de entorno — nunca hardcodear tokens)
# ============================================================================

SICSER_BASE_URL = config(
    'SICSER_BASE_URL',
    default='http://201.149.44.108/intranet',
).rstrip('/')

SICSER_API_OOW_URL = config(
    'SICSER_API_OOW_URL',
    default=f'{SICSER_BASE_URL}/includes/api/oow/listados/listado.php',
)

SICSER_API_GARANTIAS_URL = config(
    'SICSER_API_GARANTIAS_URL',
    default=f'{SICSER_BASE_URL}/includes/api/garantias/listados/listado.php',
)

SICSER_TOKEN_OOW = config('SICSER_TOKEN_OOW', default='')
SICSER_TOKEN_GARANTIAS = config('SICSER_TOKEN_GARANTIAS', default='')

# Segundos que se conserva la respuesta en caché para no saturar SICSER al refrescar.
SICSER_CACHE_TTL = config('SICSER_CACHE_TTL', default=120, cast=int)

# Mapeo de nombres de país que devuelve la API de garantías → código ISO usado en SIGMA.
PAIS_SICSER_A_CODIGO: dict[str, str] = {
    'mexico': 'MX',
    'méxico': 'MX',
    'argentina': 'AR',
    'chile': 'CL',
    'colombia': 'CO',
}

# Segmentos del folio OOW / campo cis → código corto del manual SICSER (formulario-oow.php).
SEGMENTO_CIS_A_CODIGO_URL: dict[str, str] = {
    'DROPOFF': 'DROP',
    'DROP': 'DROP',
    'SIC': 'SAT',
    'SATELITE': 'SAT',
    'SATÉLITE': 'SAT',
    'SAT': 'SAT',
    'MONTERREY': 'MTR',
    'MTR': 'MTR',
    'GUADALAJARA': 'GDL',
    'GDL': 'GDL',
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # El folio de Argentina suele traer "BUENOSAIRES" junto (sin espacio).
    # Si no lo mapeamos, parsear_codigo_cis_para_url() no lo reconoce y
    # cae al valor por defecto "SAT" (Satélite), que es incorrecto.
    'BUENOSAIRES': 'BUA',
    'BUENOS': 'BUA',
    'BUA': 'BUA',
    'BOGOTA': 'BOG',
    'BOGOTÁ': 'BOG',
    'BOG': 'BOG',
    'MEDELLIN': 'MED',
    'MEDELLÍN': 'MED',
    'MED': 'MED',
    'SANTIAGO': 'SAN',
    'SAN': 'SAN',
}


class SicserAPIError(Exception):
    """Error al consultar o interpretar una respuesta de SICSER."""


@dataclass(frozen=True)
class OrdenOOWSicser:
    """
    Representación normalizada de un registro OOW devuelto por SICSER.

    Atributos:
        id_orden: ID interno en SICSER.
        folio: Folio completo (ej. MX_CIS_MX_DROPOFF_11954).
        service_tag: Número de serie / Service Tag del equipo.
        nombre_cliente: Nombre del cliente.
        marca: Marca reportada por SICSER.
        tipo_equipo: Tipo reportado (ej. LAPTOP).
        modelo: Modelo del equipo.
        email: Correo del cliente.
        telefono: Teléfono de contacto.
        rfc: RFC del cliente (si aplica).
        descripcion_falla: Texto de la falla reportada.
        cis: Código CIS en SICSER (puede ser null).
        fecha: Fecha de ingreso en SICSER.
        codigo_pais: Código ISO del país (MX, CL, etc.).
        codigo_cis_url: Código corto para el parámetro codigo_cis del formato digital.
        preview_orden_sigma: Cómo se vería en SIGMA si se importara (OOW-11954).
        url_formato_digital: Hipervínculo al formulario OOW de SICSER.
    """

    id_orden: int
    folio: str
    service_tag: str
    nombre_cliente: str
    marca: str
    tipo_equipo: str
    modelo: str
    email: str
    telefono: str
    rfc: str
    descripcion_falla: str
    cis: str
    fecha: str
    codigo_pais: str
    codigo_cis_url: str
    cis_etiqueta: str
    preview_orden_sigma: str
    url_formato_digital: str


@dataclass(frozen=True)
class OrdenGarantiaSicser:
    """
    Representación normalizada de un registro de garantía Dell en SICSER.

    Atributos:
        numero_dps: Número DPS (identificador de garantía).
        service_tag: Service Tag del equipo.
        contacto: Persona de contacto.
        empresa: Razón social o empresa.
        telefono: Teléfono principal.
        email_contacto: Correo de contacto.
        especificaciones: Modelo / especificaciones (ej. Latitude 7430).
        instrucciones_dell: Texto de diagnóstico Dell.
        nombre_grupo: Tipo de ingreso (Carry In, Mail In, etc.).
        fecha_recepcion: Fecha de recepción en SICSER.
        pais_texto: País tal como lo devuelve la API.
        codigo_pais: Código ISO para filtrar por tenant.
        url_formato_digital: Hipervínculo al formulario de garantías.
    """

    numero_dps: int
    service_tag: str
    contacto: str
    empresa: str
    telefono: str
    email_contacto: str
    especificaciones: str
    instrucciones_dell: str
    nombre_grupo: str
    fecha_recepcion: str
    pais_texto: str
    codigo_pais: str
    url_formato_digital: str


def preview_orden_sigma_desde_folio(folio: str) -> str:
    """
    Convierte el folio SICSER al formato que usaría SIGMA al importar.

    Args:
        folio: Folio completo de SICSER (ej. MX_CIS_MX_DROPOFF_11954).

    Returns:
        str: Número de orden cliente propuesto (ej. OOW-11954).
    """
    sufijo = folio.rsplit('_', 1)[-1].strip()
    return f'OOW-{sufijo}' if sufijo else folio


def parsear_codigo_pais_desde_folio_oow(folio: str) -> str:
    """
    Extrae el código de país del prefijo del folio OOW.

    Args:
        folio: Folio SICSER (ej. MX_CIS_MX_DROPOFF_11954 o CL_CIS_CL_SANTIAGO_05981).

    Returns:
        str: Código ISO de dos letras (MX, CL, AR, CO) o cadena vacía si no se detecta.
    """
    if not folio:
        return ''
    return folio.split('_', 1)[0].strip().upper()


def parsear_codigo_cis_para_url(folio: str, cis: str | None = None) -> str:
    """
    Determina el parámetro codigo_cis del formulario digital OOW.

    Args:
        folio: Folio completo de SICSER.
        cis: Valor del campo cis de la API (opcional).

    Returns:
        str: Código corto aceptado por SICSER (DROP, SAT, MTR, etc.).
    """
    candidatos: list[str] = []

    if cis:
        candidatos.extend(
            parte.strip().upper()
            for parte in cis.replace('CIS_', '').split('_')
            if parte.strip()
        )

    candidatos.extend(parte.strip().upper() for parte in folio.split('_') if parte.strip())

    for candidato in candidatos:
        if candidato in SEGMENTO_CIS_A_CODIGO_URL:
            return SEGMENTO_CIS_A_CODIGO_URL[candidato]

    return 'SAT'


def parsear_codigo_pais_garantia(pais_texto: str) -> str:
    """
    Normaliza el nombre de país de la API de garantías a código ISO.

    Args:
        pais_texto: Texto devuelto por SICSER (ej. Mexico).

    Returns:
        str: Código ISO (MX, AR, CL, CO) o cadena vacía.
    """
    clave = (pais_texto or '').strip().lower()
    return PAIS_SICSER_A_CODIGO.get(clave, '')


def url_formato_oow(folio: str, codigo_cis: str, codigo_pais: str) -> str:
    """
    Construye la URL del formulario digital OOW en SICSER.

    Args:
        folio: Folio completo (folio_dps_servicio).
        codigo_cis: Código del CIS (DROP, SAT, MTR, etc.).
        codigo_pais: Código del país (MX, AR, CL, CO).

    Returns:
        str: URL lista para abrir en nueva pestaña.
    """
    params = urllib.parse.urlencode({
        'folio_dps_servicio': folio,
        'codigo_cis': codigo_cis,
        'pais': codigo_pais,
    })
    return f'{SICSER_BASE_URL}/formatoDigital/formulario-oow.php?{params}'


def url_formato_garantia(numero_dps: int | str) -> str:
    """
    Construye la URL del formulario digital de garantías en SICSER.

    Args:
        numero_dps: Número DPS de la orden de garantía.

    Returns:
        str: URL lista para abrir en nueva pestaña.
    """
    params = urllib.parse.urlencode({'folio_dps_servicio': str(numero_dps)})
    return f'{SICSER_BASE_URL}/formatoDigital/formulario-garantias.php?{params}'


def _http_get_json(url: str, token: str, timeout: int = 20) -> dict[str, Any]:
    """
    Ejecuta GET JSON contra SICSER con autenticación Bearer.

    Args:
        url: Endpoint completo.
        token: Bearer token del servicio.
        timeout: Segundos máximos de espera.

    Returns:
        dict: Respuesta JSON decodificada.

    Raises:
        SicserAPIError: Si falta token, hay error HTTP o JSON inválido.
    """
    if not token:
        raise SicserAPIError(
            'Token SICSER no configurado. Agrega la variable correspondiente en el archivo .env'
        )

    request = urllib.request.Request(
        url,
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/json',
        },
        method='GET',
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode('utf-8')
    except urllib.error.HTTPError as exc:
        cuerpo = exc.read().decode('utf-8', errors='replace')[:300]
        raise SicserAPIError(f'SICSER respondió HTTP {exc.code}: {cuerpo}') from exc
    except urllib.error.URLError as exc:
        raise SicserAPIError(f'No se pudo conectar con SICSER: {exc.reason}') from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SicserAPIError('La respuesta de SICSER no es JSON válido.') from exc

    if not payload.get('success'):
        raise SicserAPIError('SICSER indicó success=false en la respuesta.')

    return payload


def _filtrar_por_busqueda(texto_busqueda: str, *valores: str) -> bool:
    """
    Evalúa si un registro coincide con el texto de búsqueda del usuario.

    Args:
        texto_busqueda: Texto ingresado en el filtro (puede estar vacío).
        *valores: Campos donde buscar coincidencias parciales.

    Returns:
        bool: True si coincide o si no hay filtro activo.
    """
    filtro = texto_busqueda.strip().lower()
    if not filtro:
        return True
    bloque = ' '.join(str(valor or '') for valor in valores).lower()
    return filtro in bloque


def _normalizar_registro_oow(item: dict[str, Any]) -> OrdenOOWSicser:
    """Transforma un dict crudo de la API OOW en OrdenOOWSicser."""
    folio = str(item.get('folio') or '').strip()
    cis_raw = str(item.get('cis') or '').strip()
    codigo_pais = parsear_codigo_pais_desde_folio_oow(folio)
    codigo_cis = parsear_codigo_cis_para_url(folio, cis_raw or None)

    return OrdenOOWSicser(
        id_orden=int(item.get('id_orden') or 0),
        folio=folio,
        service_tag=str(item.get('service_tag') or '').strip().upper(),
        nombre_cliente=str(item.get('nombre_cliente') or item.get('contacto') or '').strip(),
        marca=str(item.get('marca') or '').strip(),
        tipo_equipo=str(item.get('tipo_equipo') or '').strip(),
        modelo=str(item.get('modelo') or '').strip(),
        email=str(item.get('email') or '').strip().lower(),
        telefono=str(item.get('telefono') or '').strip(),
        rfc=str(item.get('rfc') or '').strip().upper(),
        descripcion_falla=str(item.get('descripcion_falla') or '').strip(),
        cis=cis_raw,
        fecha=str(item.get('fecha') or '').strip(),
        codigo_pais=codigo_pais,
        codigo_cis_url=codigo_cis,
        cis_etiqueta=etiqueta_cis_legible(codigo_cis),
        preview_orden_sigma=preview_orden_sigma_desde_folio(folio),
        url_formato_digital=url_formato_oow(folio, codigo_cis, codigo_pais or 'MX'),
    )


def _normalizar_registro_garantia(item: dict[str, Any]) -> OrdenGarantiaSicser:
    """Transforma un dict crudo de la API de garantías en OrdenGarantiaSicser."""
    numero_dps = int(item.get('numero_dps') or 0)
    pais_texto = str(item.get('pais') or '').strip()

    return OrdenGarantiaSicser(
        numero_dps=numero_dps,
        service_tag=str(item.get('service_tag') or '').strip().upper(),
        contacto=str(item.get('contacto') or '').strip(),
        empresa=str(item.get('empresa') or '').strip(),
        telefono=str(item.get('telefono') or '').strip(),
        email_contacto=str(item.get('email_contacto') or '').strip().lower(),
        especificaciones=str(item.get('especificaciones') or '').strip(),
        instrucciones_dell=str(item.get('instrucciones_dell') or '').strip(),
        nombre_grupo=str(item.get('nombre_grupo') or '').strip(),
        fecha_recepcion=str(item.get('fecha_recepcion') or '').strip(),
        pais_texto=pais_texto,
        codigo_pais=parsear_codigo_pais_garantia(pais_texto),
        url_formato_digital=url_formato_garantia(numero_dps),
    )


def fetch_listado_oow(
    codigo_pais: str,
    texto_busqueda: str = '',
    usar_cache: bool = True,
) -> tuple[list[OrdenOOWSicser], int]:
    """
    Obtiene y filtra el listado OOW de SICSER para el país activo.

    Args:
        codigo_pais: Código ISO del tenant (MX, CL, AR, CO).
        texto_busqueda: Filtro opcional por folio, service tag o cliente.
        usar_cache: Si True, reutiliza respuesta cacheada por SICSER_CACHE_TTL segundos.

    Returns:
        tuple: (lista filtrada, total sin filtro de búsqueda en el país).
    """
    cache_key = f'sicser:oow:{codigo_pais.upper()}'
    registros: list[dict[str, Any]] | None = cache.get(cache_key) if usar_cache else None

    if registros is None:
        payload = _http_get_json(SICSER_API_OOW_URL, SICSER_TOKEN_OOW)
        registros = list(payload.get('data') or [])
        if usar_cache:
            cache.set(cache_key, registros, SICSER_CACHE_TTL)

    codigo = codigo_pais.upper()
    normalizados = [_normalizar_registro_oow(item) for item in registros]
    por_pais = [orden for orden in normalizados if orden.codigo_pais == codigo]
    total_pais = len(por_pais)

    if texto_busqueda.strip():
        por_pais = [
            orden for orden in por_pais
            if _filtrar_por_busqueda(
                texto_busqueda,
                orden.folio,
                orden.service_tag,
                orden.nombre_cliente,
                orden.marca,
                orden.preview_orden_sigma,
            )
        ]

    por_pais.sort(key=lambda orden: orden.fecha, reverse=True)
    return por_pais, total_pais


def fetch_listado_garantias(
    codigo_pais: str,
    texto_busqueda: str = '',
    usar_cache: bool = True,
) -> tuple[list[OrdenGarantiaSicser], int]:
    """
    Obtiene y filtra el listado de garantías Dell de SICSER para el país activo.

    Args:
        codigo_pais: Código ISO del tenant (MX, CL, AR, CO).
        texto_busqueda: Filtro opcional por DPS, service tag o contacto.
        usar_cache: Si True, reutiliza respuesta cacheada por SICSER_CACHE_TTL segundos.

    Returns:
        tuple: (lista filtrada, total sin filtro de búsqueda en el país).
    """
    cache_key = f'sicser:garantias:{codigo_pais.upper()}'
    registros: list[dict[str, Any]] | None = cache.get(cache_key) if usar_cache else None

    if registros is None:
        payload = _http_get_json(SICSER_API_GARANTIAS_URL, SICSER_TOKEN_GARANTIAS)
        registros = list(payload.get('data') or [])
        if usar_cache:
            cache.set(cache_key, registros, SICSER_CACHE_TTL)

    codigo = codigo_pais.upper()
    normalizados = [_normalizar_registro_garantia(item) for item in registros]
    por_pais = [orden for orden in normalizados if orden.codigo_pais == codigo]
    total_pais = len(por_pais)

    if texto_busqueda.strip():
        por_pais = [
            orden for orden in por_pais
            if _filtrar_por_busqueda(
                texto_busqueda,
                str(orden.numero_dps),
                orden.service_tag,
                orden.contacto,
                orden.empresa,
                orden.especificaciones,
            )
        ]

    por_pais.sort(key=lambda orden: orden.fecha_recepcion, reverse=True)
    return por_pais, total_pais


def buscar_registro_oow_por_id(
    id_orden: int,
    codigo_pais: str,
) -> OrdenOOWSicser | None:
    """
    Localiza un registro OOW en el listado cacheado o en vivo de SICSER.

    Args:
        id_orden: ID interno SICSER (id_orden).
        codigo_pais: Código ISO del tenant activo.

    Returns:
        OrdenOOWSicser | None: Registro encontrado o None.
    """
    registros, _ = fetch_listado_oow(codigo_pais=codigo_pais, usar_cache=True)
    for registro in registros:
        if registro.id_orden == id_orden:
            return registro
    return None


def buscar_registro_garantia_por_dps(
    numero_dps: int,
    codigo_pais: str,
) -> OrdenGarantiaSicser | None:
    """
    Localiza un registro de garantía en el listado de SICSER.

    Args:
        numero_dps: Número DPS de la garantía.
        codigo_pais: Código ISO del tenant activo.

    Returns:
        OrdenGarantiaSicser | None: Registro encontrado o None.
    """
    registros, _ = fetch_listado_garantias(codigo_pais=codigo_pais, usar_cache=True)
    for registro in registros:
        if registro.numero_dps == numero_dps:
            return registro
    return None


def etiqueta_cis_legible(codigo_cis_url: str) -> str:
    """
    Devuelve una etiqueta amigable para mostrar el CIS en la tabla.

    Args:
        codigo_cis_url: Código corto (DROP, SAT, etc.).

    Returns:
        str: Nombre legible para el operador.
    """
    etiquetas = {
        'DROP': 'Drop Off',
        'SAT': 'Satélite',
        'MTR': 'Monterrey',
        'GDL': 'Guadalajara',
        'BUA': 'Buenos Aires',
        'BOG': 'Bogotá',
        'MED': 'Medellín',
        'SAN': 'Santiago',
    }
    return etiquetas.get(codigo_cis_url, codigo_cis_url)
