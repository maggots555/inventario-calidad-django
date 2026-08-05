"""
Resolución de ProductoAlmacen → ComponenteEquipo para sincronización con ST.

EXPLICACIÓN PARA PRINCIPIANTES:
Los productos del almacén tienen nombres largos ("BATERÍA / PILA DELL 40 W").
Servicio Técnico usa ComponenteEquipo con nombres cortos y normalizados ("Batería").
Este módulo hace ese emparejamiento automáticamente al sincronizar cotizaciones.
"""

from __future__ import annotations

import logging
import unicodedata

from config.constants import (
    NOMBRE_COMPONENTE_EQUIPO_REACONDICIONADO,
    PALABRAS_CLAVE_COMPONENTE,
)
from scorecard.models import ComponenteEquipo

logger = logging.getLogger(__name__)


def _normalizar_texto(texto: str) -> str:
    """
    Convierte texto a mayúsculas sin acentos para comparaciones seguras.

    Args:
        texto: Cadena original del producto o descripción.

    Returns:
        str: Texto normalizado listo para búsqueda por keywords.
    """
    if not texto:
        return ''
    texto_upper = texto.upper()
    # Quitar acentos: "BATERÍA" y "BATERIA" deben coincidir igual
    descompuesto = unicodedata.normalize('NFD', texto_upper)
    return ''.join(c for c in descompuesto if unicodedata.category(c) != 'Mn')


def _texto_busqueda(nombre_producto: str, descripcion_pieza: str = '') -> str:
    """
    Une nombre de producto y descripción en un solo bloque de búsqueda.

    También agrega el segmento antes del primer '/' (ej. "BATERÍA / PILA..." → "BATERÍA").
    """
    partes = []
    for fragmento in (nombre_producto, descripcion_pieza):
        fragmento = (fragmento or '').strip()
        if fragmento:
            partes.append(fragmento)
            if '/' in fragmento:
                segmento_inicial = fragmento.split('/', 1)[0].strip()
                if segmento_inicial:
                    partes.append(segmento_inicial)
    return ' '.join(partes)


def _keywords_ordenadas() -> list[tuple[str, str]]:
    """
    Pares (keyword_normalizada, nombre_componente_bd) ordenados por longitud descendente.

    La keyword más larga gana para evitar que "SSD" capture antes que "SSD M.2".
    """
    pares: list[tuple[str, str, int]] = []
    for keywords, nombre_componente in PALABRAS_CLAVE_COMPONENTE:
        for keyword in keywords:
            pares.append((_normalizar_texto(keyword), nombre_componente, len(keyword)))
    pares.sort(key=lambda item: item[2], reverse=True)
    return [(kw, nombre) for kw, nombre, _ in pares]


def _nombres_componentes_ordenados() -> list[tuple[str, str]]:
    """
    Lista (nombre_normalizado, nombre_bd) de ComponenteEquipo activos, más largos primero.
    """
    registros = ComponenteEquipo.objects.filter(activo=True).values_list('nombre', flat=True)
    pares = [(_normalizar_texto(nombre), nombre) for nombre in registros]
    pares.sort(key=lambda item: len(item[0]), reverse=True)
    return pares


def _buscar_por_nombre_en_bd(nombre_canonico: str) -> ComponenteEquipo | None:
    """Obtiene ComponenteEquipo activo por nombre exacto (case-insensitive)."""
    return ComponenteEquipo.objects.filter(nombre__iexact=nombre_canonico, activo=True).first()


def _buscar_por_substring_componente(texto: str) -> tuple[ComponenteEquipo | None, int]:
    """
    Si el nombre de un ComponenteEquipo aparece dentro del texto del producto, lo devuelve.

    Returns:
        tuple: (componente o None, longitud del nombre normalizado que coincidió).
    """
    for nombre_norm, nombre_bd in _nombres_componentes_ordenados():
        if nombre_norm and nombre_norm in texto:
            componente = _buscar_por_nombre_en_bd(nombre_bd)
            if componente:
                return componente, len(nombre_norm)
    return None, 0


def _buscar_por_keywords(texto: str) -> tuple[ComponenteEquipo | None, int]:
    """
    Empareja palabras clave del catálogo de almacén con ComponenteEquipo.

    Returns:
        tuple: (componente o None, longitud de la keyword que coincidió).
    """
    for keyword_norm, nombre_componente in _keywords_ordenadas():
        if keyword_norm and keyword_norm in texto:
            componente = _buscar_por_nombre_en_bd(nombre_componente)
            if componente:
                return componente, len(keyword_norm)
    return None, 0


def obtener_componente_equipo_reacondicionado() -> ComponenteEquipo | None:
    """
    Devuelve el ComponenteEquipo para líneas de equipo reacondicionado (P0125).

    Returns:
        ComponenteEquipo o None si no existe en la BD del tenant.
    """
    componente = _buscar_por_nombre_en_bd(NOMBRE_COMPONENTE_EQUIPO_REACONDICIONADO)
    if not componente:
        logger.warning(
            "No existe ComponenteEquipo '%s' en la base de datos. "
            'Cree el registro en Scorecard para normalizar equipos reac.',
            NOMBRE_COMPONENTE_EQUIPO_REACONDICIONADO,
        )
    return componente


def resolver_componente_desde_producto(
    nombre_producto: str,
    descripcion_pieza: str = '',
    *,
    es_reacondicionado: bool = False,
) -> ComponenteEquipo | None:
    """
    Normaliza un producto de almacén al ComponenteEquipo correspondiente.

    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Evalúa dos pistas: (1) si el nombre del componente ST aparece en el producto
    y (2) el mapa de keywords. Gana la coincidencia MÁS LARGA. Así
    «CABLE AC PARA CARGADOR» no cae en «Cargador» solo porque la palabra
    CARGADOR está al final: la keyword «CABLE AC PARA CARGADOR» es más larga.

    Si empatan en longitud, se prefiere el nombre canónico del componente
    (substring), p. ej. «PALMREST» → Palmrest y no Teclado.

    Args:
        nombre_producto: ProductoAlmacen.nombre (fuente principal).
        descripcion_pieza: LineaCotizacion.descripcion_pieza (respaldo).
        es_reacondicionado: Si True, asigna siempre "Equipo reacondicionado".

    Returns:
        ComponenteEquipo encontrado o None si no hay match confiable.
    """
    if es_reacondicionado:
        return obtener_componente_equipo_reacondicionado()

    texto = _normalizar_texto(_texto_busqueda(nombre_producto, descripcion_pieza))
    if not texto:
        return None

    # Paso 1 y 2: substring + keywords; gana la señal más específica (más larga)
    por_nombre, len_nombre = _buscar_por_substring_componente(texto)
    por_keyword, len_keyword = _buscar_por_keywords(texto)

    if len_keyword > len_nombre:
        return por_keyword
    if por_nombre is not None:
        return por_nombre
    if por_keyword is not None:
        return por_keyword

    logger.debug(
        "Sin ComponenteEquipo para producto='%s' descripcion='%s'",
        nombre_producto,
        descripcion_pieza,
    )
    return None
