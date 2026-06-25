"""
Utilidades para armar el contexto del correo de cotización al cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Cuando se envía una cotización por email, el contenido puede variar según el país
(México tiene textos legales y datos bancarios propios) y la referencia de pago
se arma con el prefijo de la sucursal + el identificador del equipo.

Prioridad del sufijo de la referencia:
    - Con orden vinculada  → orden_cliente (ej. OOW-11902 → DROP11902)
    - Sin orden vinculada  → service_tag (ej. PYFHF888A → DROPPYFHF888A)
    - Último fallback      → asunto del correo
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from almacen.models import SolicitudCotizacion


# Mapeo de palabras clave en el nombre/código de sucursal → prefijo de referencia.
# El orden importa: se evalúa de arriba hacia abajo y se usa la primera coincidencia.
_REGLAS_PREFIJO_SUCURSAL = (
    ('drop', 'DROP'),
    ('satelite', 'SAT'),
    ('satélite', 'SAT'),
    ('guadalajara', 'GDL'),
    ('gdl', 'GDL'),
    ('monterrey', 'MTY'),
    ('mty', 'MTY'),
)


def _normalizar_texto_sucursal(texto: str) -> str:
    """
    Convierte el texto a minúsculas sin acentos para comparaciones seguras.

    Args:
        texto: Nombre o código de la sucursal.

    Returns:
        str: Texto normalizado (ej. 'Satélite' → 'satelite').
    """
    if not texto:
        return ''
    sin_acentos = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return sin_acentos.lower().strip()


def obtener_prefijo_sucursal(nombre_sucursal: str = '', codigo_sucursal: str = '') -> str:
    """
    Obtiene el prefijo de referencia de pago según la sucursal de la orden.

    Reglas (según nombre o código de sucursal):
        - Drop Off        → DROP
        - Satélite        → SAT
        - Guadalajara     → GDL
        - Monterrey       → MTY

    Args:
        nombre_sucursal: Nombre legible de la sucursal.
        codigo_sucursal: Código interno de la sucursal.

    Returns:
        str: Prefijo en mayúsculas o cadena vacía si no hay coincidencia.
    """
    texto_busqueda = _normalizar_texto_sucursal(f'{nombre_sucursal} {codigo_sucursal}')

    for palabra_clave, prefijo in _REGLAS_PREFIJO_SUCURSAL:
        if palabra_clave in texto_busqueda:
            return prefijo

    return ''


def _obtener_orden_cliente_para_referencia(solicitud: 'SolicitudCotizacion') -> str:
    """
    Obtiene el número de orden del cliente cuando hay orden vinculada.

    Prioridad:
        1. numero_orden_cliente sincronizado en la solicitud
        2. orden_cliente del DetalleEquipo

    Args:
        solicitud: Solicitud con orden_servicio vinculada.

    Returns:
        str: Número de orden visible (ej. OOW-11902) o cadena vacía.
    """
    if not solicitud.orden_servicio:
        return ''

    if solicitud.numero_orden_cliente:
        return solicitud.numero_orden_cliente.strip()

    try:
        orden_cliente = solicitud.orden_servicio.detalle_equipo.orden_cliente
        if orden_cliente and str(orden_cliente).strip():
            return str(orden_cliente).strip()
    except Exception:
        pass

    return ''


def _obtener_service_tag_solicitud(solicitud: 'SolicitudCotizacion') -> str:
    """
    Obtiene el Service Tag solo para solicitudes sin orden vinculada.

    Args:
        solicitud: Solicitud en modo sin_orden_activa.

    Returns:
        str: service_tag de la solicitud o cadena vacía.
    """
    if solicitud.orden_servicio:
        return ''

    if solicitud.service_tag:
        return solicitud.service_tag.strip()

    return ''


def extraer_sufijo_desde_identificador(identificador: str) -> str:
    """
    Normaliza un identificador (orden_cliente o service tag) al sufijo de referencia.

    Reglas:
        - Si termina en 4+ dígitos (ej. OOW-11902), usa solo esos dígitos → 11902
        - Si no, usa el identificador alfanumérico completo (ej. PYFHF888A)

    Args:
        identificador: orden_cliente o service tag.

    Returns:
        str: Sufijo para la referencia de pago.
    """
    if not identificador:
        return ''

    # Dejar solo letras y números en mayúsculas
    limpio = re.sub(r'[^A-Z0-9]', '', identificador.upper())
    if not limpio:
        return ''

    # Si termina en un bloque largo de dígitos (folio tipo 11902), usar solo esos dígitos
    coincidencia_digitos = re.search(r'(\d+)$', limpio)
    if coincidencia_digitos and len(coincidencia_digitos.group(1)) >= 4:
        return coincidencia_digitos.group(1)

    # Tag alfanumérico completo (ej. Dell 7XK9VN2)
    return limpio


def extraer_sufijo_desde_asunto(asunto: str, prefijo: str = '') -> str:
    """
    Extrae el sufijo de referencia desde el asunto del correo (último fallback).

    Busca patrones como:
        - ... - DROP11902
        - ... _11902
        - ... - 11902
        - Último grupo de dígitos en el asunto

    Args:
        asunto: Asunto del correo (personalizado o generado).
        prefijo: Prefijo de sucursal ya calculado (DROP, SAT, etc.).

    Returns:
        str: Sufijo extraído o cadena vacía.
    """
    if not asunto:
        return ''

    asunto_limpio = asunto.strip()

    # Identificador después de "Cotización SIC —" (orden cliente o service tag)
    coincidencia_asunto = re.search(
        r'Cotización\s+SIC\s*—\s*(.+)$',
        asunto_limpio,
        re.IGNORECASE,
    )
    if coincidencia_asunto:
        identificador = coincidencia_asunto.group(1).strip()
        # Quitar referencia de pago si ya venía al final (ej. ... - DROP11902)
        identificador = re.sub(
            r'\s*-\s*(DROP|SAT|GDL|MTY)[A-Z0-9]+$',
            '',
            identificador,
            flags=re.IGNORECASE,
        ).strip()
        # Quitar prefijo "S/T:" si el asunto lo incluye
        if identificador.upper().startswith('S/T:'):
            identificador = identificador[4:].strip()
        sufijo_desde_asunto = extraer_sufijo_desde_identificador(identificador)
        if sufijo_desde_asunto:
            return sufijo_desde_asunto

    # Referencia completa ya presente: DROP11902, GDL11902, etc.
    if prefijo:
        coincidencia_completa = re.search(
            rf'{re.escape(prefijo)}([A-Z0-9]+)',
            asunto_limpio,
            re.IGNORECASE,
        )
        if coincidencia_completa:
            return coincidencia_completa.group(1).upper()

    # Sufijos con guión o guión bajo al final: _11902 o -11902
    coincidencia_sufijo = re.search(r'[-_](\d+)\s*$', asunto_limpio)
    if coincidencia_sufijo:
        return coincidencia_sufijo.group(1)

    # Último grupo de dígitos en todo el asunto
    grupos_digitos = re.findall(r'\d+', asunto_limpio)
    if grupos_digitos:
        return grupos_digitos[-1]

    return ''


def _obtener_sucursal_desde_solicitud(solicitud: 'SolicitudCotizacion'):
    """
    Obtiene la sucursal para la referencia de pago.

    Prioridad:
        1. Sucursal de la orden de servicio vinculada
        2. Sucursal del empleado que creó la solicitud (modo sin orden activa)

    Args:
        solicitud: Solicitud de cotización.

    Returns:
        Instancia de Sucursal o None.
    """
    orden = solicitud.orden_servicio
    if orden and orden.sucursal:
        return orden.sucursal

    # Sin orden vinculada: usar la sucursal de quien creó la cotización
    try:
        creador = solicitud.creado_por
        if creador and hasattr(creador, 'empleado') and creador.empleado:
            sucursal_creador = creador.empleado.sucursal
            if sucursal_creador:
                return sucursal_creador
    except Exception:
        pass

    return None


def _obtener_prefijo_desde_solicitud(solicitud: 'SolicitudCotizacion') -> str:
    """
    Obtiene el prefijo de sucursal desde la orden o desde el creador de la solicitud.

    Args:
        solicitud: Solicitud con orden_servicio y/o creado_por.empleado.sucursal.

    Returns:
        str: Prefijo DROP/SAT/GDL/MTY o cadena vacía.
    """
    sucursal = _obtener_sucursal_desde_solicitud(solicitud)
    if not sucursal:
        return ''

    return obtener_prefijo_sucursal(
        nombre_sucursal=sucursal.nombre or '',
        codigo_sucursal=sucursal.codigo or '',
    )


def _obtener_sufijo_referencia(
    solicitud: 'SolicitudCotizacion',
    asunto_fallback: str = '',
) -> str:
    """
    Obtiene el sufijo de la referencia según el tipo de solicitud.

    Con orden vinculada usa orden_cliente; sin orden usa service_tag.
    Si no hay dato, intenta extraerlo del asunto del correo.

    Args:
        solicitud: Solicitud de cotización.
        asunto_fallback: Asunto del correo para último fallback.

    Returns:
        str: Sufijo de referencia o cadena vacía.
    """
    if solicitud.orden_servicio:
        # Con orden: NUNCA usar service tag — solo orden_cliente
        identificador = _obtener_orden_cliente_para_referencia(solicitud)
    else:
        # Sin orden: usar service tag de la solicitud
        identificador = _obtener_service_tag_solicitud(solicitud)

    sufijo = extraer_sufijo_desde_identificador(identificador)

    if not sufijo and asunto_fallback:
        prefijo = _obtener_prefijo_desde_solicitud(solicitud)
        sufijo = extraer_sufijo_desde_asunto(asunto_fallback, prefijo=prefijo)

    return sufijo


def generar_referencia_pago(
    solicitud: 'SolicitudCotizacion',
    asunto_fallback: str = '',
) -> str:
    """
    Genera la referencia de pago: prefijo sucursal + sufijo según el caso.

    - Con orden vinculada: prefijo + dígitos de orden_cliente (ej. DROP11902)
    - Sin orden vinculada: prefijo + service_tag (ej. DROPPYFHF888A)

    Args:
        solicitud: Solicitud de cotización.
        asunto_fallback: Asunto del correo para último fallback.

    Returns:
        str: Referencia completa o cadena vacía si no se puede calcular.
    """
    prefijo = _obtener_prefijo_desde_solicitud(solicitud)
    sufijo = _obtener_sufijo_referencia(solicitud, asunto_fallback=asunto_fallback)

    if prefijo and sufijo:
        return f'{prefijo}{sufijo}'

    return ''


PREFIJO_ASUNTO_CORREO = 'Cotización SIC — '


def construir_asunto_correo_default(
    solicitud: 'SolicitudCotizacion',
    info_orden: Any = None,
) -> str:
    """
    Arma el asunto sugerido para el modal de envío al cliente.

    Prioridad del identificador:
        1. numero_orden_cliente de la solicitud
        2. service_tag (solicitud sin orden vinculada)
        3. orden_cliente del DetalleEquipo (respaldo)
        4. numero_serie / Service Tag del equipo (respaldo)

    Args:
        solicitud: Solicitud de cotización.
        info_orden: DetalleEquipo vinculado, si existe.

    Returns:
        str: Asunto parcial, ej. 'Cotización SIC — OOW-11902' o solo el prefijo.
    """
    identificador = ''

    if solicitud.numero_orden_cliente:
        identificador = solicitud.numero_orden_cliente.strip()
    elif solicitud.service_tag:
        identificador = solicitud.service_tag.strip()
    elif info_orden is not None:
        orden_cliente = getattr(info_orden, 'orden_cliente', '') or ''
        if orden_cliente.strip():
            identificador = orden_cliente.strip()
        else:
            numero_serie = getattr(info_orden, 'numero_serie', '') or ''
            if str(numero_serie).strip():
                identificador = str(numero_serie).strip()

    if identificador:
        return f'{PREFIJO_ASUNTO_CORREO}{identificador}'

    return PREFIJO_ASUNTO_CORREO


def es_asunto_correo_vacio(asunto: str) -> bool:
    """
    Indica si el asunto debe tratarse como vacío para generación automática.

    Args:
        asunto: Texto capturado en el modal o API.

    Returns:
        bool: True si solo contiene el prefijo por defecto sin identificador.
    """
    asunto_limpio = (asunto or '').strip()
    return asunto_limpio in (
        PREFIJO_ASUNTO_CORREO.strip(),
        PREFIJO_ASUNTO_CORREO.rstrip(),
    )


def formatear_fecha_limite_factura(fecha_local: datetime, dia_limite: int = 25) -> str:
    """
    Formatea la fecha límite para subir datos fiscales (día 25 del mes actual).

    Args:
        fecha_local: Fecha/hora en zona horaria del país.
        dia_limite: Día del mes (por defecto 25).

    Returns:
        str: Texto legible, ej. '25 de junio de 2026'.
    """
    meses_es = (
        'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
        'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
    )
    mes_nombre = meses_es[fecha_local.month - 1]
    return f'{dia_limite} de {mes_nombre} de {fecha_local.year}'


def construir_contexto_email_cotizacion(
    solicitud: 'SolicitudCotizacion',
    pais_config: Dict[str, Any],
    fecha_local: datetime,
    asunto_fallback: str = '',
) -> Dict[str, Any]:
    """
    Arma variables adicionales del correo según el país y la solicitud.

    Args:
        solicitud: Solicitud de cotización enviada al cliente.
        pais_config: Bloque de configuración del país activo (paises_config).
        fecha_local: Fecha/hora local del país para textos dinámicos.
        asunto_fallback: Asunto base del correo para calcular referencia si falta ST.

    Returns:
        dict: Variables para el template (pais_codigo, referencia_pago, etc.).
    """
    pais_codigo = pais_config.get('codigo', '')
    cotizacion_email = pais_config.get('cotizacion_email') or None

    referencia_pago = ''
    sucursal = _obtener_sucursal_desde_solicitud(solicitud)
    sucursal_nombre = sucursal.nombre if sucursal else ''

    if pais_codigo == 'MX' and cotizacion_email:
        referencia_pago = generar_referencia_pago(
            solicitud,
            asunto_fallback=asunto_fallback,
        )

    fecha_limite_factura_texto = ''
    if cotizacion_email:
        dia_limite = cotizacion_email.get('dia_limite_factura_mes', 25)
        fecha_limite_factura_texto = formatear_fecha_limite_factura(
            fecha_local, dia_limite=dia_limite
        )

    return {
        'pais_codigo': pais_codigo,
        'cotizacion_email': cotizacion_email,
        'referencia_pago': referencia_pago,
        'sucursal_nombre': sucursal_nombre,
        'fecha_limite_factura_texto': fecha_limite_factura_texto,
        'empresa_nombre_mayus': (pais_config.get('empresa_nombre_corto') or 'SIC').upper(),
    }
