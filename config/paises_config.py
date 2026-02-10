# config/paises_config.py
"""
EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este archivo es el "diccionario" central de todos los países del sistema.
Cada país tiene su propia configuración: zona horaria, moneda, empresa, etc.

¿POR QUÉ un solo archivo?
- Cuando necesites cambiar algo de un país, solo vienes aquí
- Cuando agregues un nuevo país, solo agregas un bloque aquí
- Evita tener datos de país regados por todo el código

¿CÓMO se usa?
- El middleware lee este archivo para saber qué país corresponde al subdominio
- Las vistas lo usan para formatear moneda, fechas, etc.
- Los templates lo usan via context_processors para mostrar el nombre del país
"""

from decouple import config


# ============================================================================
# CONFIGURACIÓN MAESTRA DE PAÍSES
# ============================================================================
# 
# Cada clave del diccionario es el SUBDOMINIO que identifica al país.
# Ejemplo: 'mexico' → mexico.sigmasystem.work
#
# PARA AGREGAR UN NUEVO PAÍS:
# 1. Copia un bloque existente
# 2. Cambia todos los valores
# 3. Crea la base de datos (Fase 2)
# 4. Agrega el subdominio en DNS (Fase 1)
# 5. ¡Listo!
# ============================================================================

PAISES_CONFIG = {
    'mexico': {
        # --- Identificación ---
        'codigo': 'MX',                    # Código ISO 3166-1 alpha-2
        'nombre': 'México',                # Nombre para mostrar al usuario
        'nombre_completo': 'México',

        # --- Base de datos ---
        'db_alias': 'mexico',              # Alias en DATABASES de settings.py

        # --- Zona horaria ---
        'timezone': 'America/Mexico_City',
        'language_code': 'es-mx',

        # --- Moneda ---
        'moneda_codigo': 'MXN',            # Código ISO 4217
        'moneda_simbolo': '$',             # Símbolo para mostrar
        'moneda_nombre': 'Peso Mexicano',
        'moneda_locale': 'es_MX',          # Para formateo con locale

        # --- Empresa ---
        'empresa_nombre': 'SIC Comercialización y Servicios México SC',
        'empresa_nombre_corto': 'SIC México',
        'empresa_direccion': 'Circuito Economistas 15-A, Col. Satélite, Naucalpan, Estado de México, CP 53100',
        'empresa_telefono': '+52-55-35-45-81-92',
        'empresa_email': config('EMPRESA_EMAIL_MX', default='contacto@sigmasystem.work'),

        # --- Contacto de seguimiento (para PDFs y emails) ---
        'agente_nombre': 'Alejandro Garcia',
        'agente_celular': '55-35-45-81-92',
        'agente_email': 'cis_mex@sic.com.mx',

        # --- RHITSO (laboratorio externo) ---
        'rhitso_habilitado': True,
        'rhitso_email_recipients': [],      # Se cargan desde .env en settings.py

        # --- URLs ---
        'dominio': 'mexico.sigmasystem.work',
        'url_base': 'https://mexico.sigmasystem.work',

        # --- Media ---
        'media_subdir': 'mexico',           # Subcarpeta dentro de MEDIA_ROOT
    },

    'argentina': {
        # --- Identificación ---
        'codigo': 'AR',
        'nombre': 'Argentina',
        'nombre_completo': 'Argentina',

        # --- Base de datos ---
        'db_alias': 'argentina',

        # --- Zona horaria ---
        'timezone': 'America/Argentina/Buenos_Aires',
        'language_code': 'es-ar',

        # --- Moneda ---
        'moneda_codigo': 'ARS',
        'moneda_simbolo': '$',
        'moneda_nombre': 'Peso Argentino',
        'moneda_locale': 'es_AR',

        # --- Empresa ---
        'empresa_nombre': config('EMPRESA_NOMBRE_AR', default='SIC Argentina (Pendiente Razón Social)'),
        'empresa_nombre_corto': 'SIC Argentina',
        'empresa_direccion': config('EMPRESA_DIRECCION_AR', default='(Pendiente dirección)'),
        'empresa_telefono': config('EMPRESA_TELEFONO_AR', default='(Pendiente teléfono)'),
        'empresa_email': config('EMPRESA_EMAIL_AR', default=''),

        # --- Contacto de seguimiento ---
        'agente_nombre': config('AGENTE_NOMBRE_AR', default='(Pendiente)'),
        'agente_celular': config('AGENTE_CELULAR_AR', default='(Pendiente)'),
        'agente_email': config('AGENTE_EMAIL_AR', default=''),

        # --- RHITSO ---
        'rhitso_habilitado': False,         # Argentina no usa RHITSO inicialmente
        'rhitso_email_recipients': [],

        # --- URLs ---
        'dominio': 'argentina.sigmasystem.work',
        'url_base': 'https://argentina.sigmasystem.work',

        # --- Media ---
        'media_subdir': 'argentina',
    },
}


# ============================================================================
# MAPEO DE SUBDOMINIO → PAÍS (para lookup rápido en middleware)
# ============================================================================
# Se genera automáticamente desde PAISES_CONFIG
# No necesitas mantener esto manualmente

SUBDOMINIO_A_PAIS = {
    subdominio: datos for subdominio, datos in PAISES_CONFIG.items()
}

# País por defecto cuando no se detecta subdominio (desarrollo local, manage.py, etc.)
PAIS_DEFAULT = 'mexico'


# ============================================================================
# FUNCIONES HELPER — Para usar en vistas, templates y utilidades
# ============================================================================

def get_pais_config(subdominio: str) -> dict | None:
    """
    Obtiene la configuración completa de un país por su subdominio.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función busca en el diccionario PAISES_CONFIG usando el subdominio.
    Si el subdominio no existe, retorna None.

    Args:
        subdominio: El subdominio extraído del request (ej: 'mexico', 'argentina')

    Returns:
        dict con la configuración del país, o None si no existe

    Ejemplo:
        config = get_pais_config('mexico')
        print(config['timezone'])  # 'America/Mexico_City'
    """
    return PAISES_CONFIG.get(subdominio)


def get_pais_por_codigo(codigo: str) -> dict | None:
    """
    Busca un país por su código ISO (MX, AR, CO, PE).

    Args:
        codigo: Código ISO del país (ej: 'MX')

    Returns:
        dict con la configuración, o None si no existe
    """
    for subdominio, datos in PAISES_CONFIG.items():
        if datos['codigo'] == codigo.upper():
            return datos
    return None


def get_todos_los_paises() -> list[dict]:
    """
    Retorna lista de todos los países configurados.
    Útil para generar selectores de país o menús.
    """
    return [
        {
            'subdominio': sub,
            'codigo': datos['codigo'],
            'nombre': datos['nombre'],
            'url_base': datos['url_base'],
        }
        for sub, datos in PAISES_CONFIG.items()
    ]


def formato_moneda(valor: float, pais_config: dict) -> str:
    """
    Formatea un valor numérico como moneda del país.

    EXPLICACIÓN PARA PRINCIPIANTES:
    En lugar de hardcodear f"${valor:,.2f}" por todo el código,
    usamos esta función que adapta el símbolo y código de moneda
    según el país activo.

    Args:
        valor: Cantidad numérica (ej: 5500.00)
        pais_config: Diccionario de configuración del país

    Returns:
        str formateado (ej: '$5,500.00 MXN' o '$5,500.00 ARS')

    Ejemplo:
        config_mx = get_pais_config('mexico')
        texto = formato_moneda(5500, config_mx)
        # Resultado: '$5,500.00 MXN'
    """
    simbolo = pais_config.get('moneda_simbolo', '$')
    codigo = pais_config.get('moneda_codigo', '')

    # Formateo estándar con separador de miles
    valor_formateado = f"{valor:,.2f}"

    return f"{simbolo}{valor_formateado} {codigo}".strip()


def get_pais_actual() -> dict:
    """
    Obtiene la configuración del país activo en el request actual.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función es un ATAJO que se usa mucho en el código.
    Intenta obtener el país del thread-local (configurado por el middleware),
    y si no lo encuentra (ej: manage.py shell, cron jobs, migrations),
    usa el país por defecto (México).

    Returns:
        dict con la configuración del país activo

    Ejemplo:
        from config.paises_config import get_pais_actual, formato_moneda
        pais = get_pais_actual()
        texto = formato_moneda(5500, pais)
    """
    from config.middleware_pais import get_current_pais_config
    pais = get_current_pais_config()
    if pais is None:
        pais = get_pais_config(PAIS_DEFAULT)
    return pais


def fecha_local_pais(fecha_utc, pais_config: dict):
    """
    Convierte una fecha UTC a la hora local del país.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Reemplaza la función fecha_local() que tenía 'America/Mexico_City'
    hardcodeado. Ahora usa la zona horaria del país activo.

    Args:
        fecha_utc: Fecha/hora en UTC (datetime)
        pais_config: Diccionario de configuración del país

    Returns:
        datetime en la zona horaria local del país
    """
    from zoneinfo import ZoneInfo
    from django.utils import timezone

    tz_name = pais_config.get('timezone', 'America/Mexico_City')
    tz_local = ZoneInfo(tz_name)

    if timezone.is_aware(fecha_utc):
        return fecha_utc.astimezone(tz_local)
    else:
        fecha_aware = timezone.make_aware(fecha_utc, timezone.utc)
        return fecha_aware.astimezone(tz_local)
