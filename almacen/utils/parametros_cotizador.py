"""
Lectura dinámica de parámetros del cotizador (reparación + reacondicionados).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Antes los márgenes vivían solo en el archivo .env y se cargaban UNA vez
al arrancar Django. Eso obligaba a reiniciar el servidor para aplicar
cambios de Presidencia.

Este módulo:
1. Lee primero la base de datos (panel gerencial).
2. Si falta algún valor, completa con el .env (respaldo).
3. Se llama en cada cálculo → los cambios aplican sin reiniciar.

Multi-tenant: cada país tiene su propia BD; el router ya enruta las
consultas ORM al tenant correcto (incluido Celery con db_alias).
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Dict, List, Optional

from django.db import transaction

logger = logging.getLogger('almacen')

# Orden canónico de perfiles (mismo que el motor de profit / PDF)
PERFILES_PROFIT: List[str] = [
    'mostrador',
    'estandar',
    'express',
    'alta_gama',
    'server',
    'rep_nivel_componente',
]

# Etiquetas en español para el panel
PERFIL_ETIQUETAS: Dict[str, str] = {
    'mostrador': 'Mostrador',
    'estandar': 'Estándar',
    'express': 'Express',
    'alta_gama': 'Alta Gama',
    'server': 'Server',
    'rep_nivel_componente': 'Reparación nivel componente',
}


def _cargar_profit_desde_env() -> Dict[str, Dict]:
    """
    Respaldo: lee PROFIT_* / COSTOS_FIJOS_* / DIAGNOSTICO_* del .env.

    Returns:
        dict: Misma forma que PROFIT_CONFIG histórico.
    """
    # Import diferido para no crear ciclo al cargar pdf_cotizacion_cliente
    from .pdf_cotizacion_cliente import _cargar_profit_config

    return _cargar_profit_config()


def _cargar_reac_desde_env() -> Dict[str, float]:
    """
    Respaldo: lee REAC_* del .env.

    Returns:
        dict: Misma forma que COSTEO_REACONDICIONADO_CONFIG histórico.
    """
    from .costeo_reacondicionado import _cargar_config_costeo

    return _cargar_config_costeo()


def obtener_profit_config() -> Dict[str, Dict]:
    """
    Devuelve la configuración de profit vigente (BD con fallback .env).

    Returns:
        dict: {
            'mostrador': {'profit_target': float, 'costos_fijos': [float], 'diagnostico': float},
            ...
        }

    Efectos secundarios:
        Solo lectura. No modifica BD ni .env.
    """
    # Paso 1: base desde .env (siempre completa los 6 perfiles)
    config = _cargar_profit_desde_env()

    # Paso 2: sobrescribir con filas de BD si existen
    # EXPLICACIÓN: si el panel aún no se ha usado, no hay filas y
    # todo sigue funcionando igual que antes con el .env.
    try:
        from almacen.models import ConfiguracionProfitPerfil

        filas = list(ConfiguracionProfitPerfil.objects.all())
    except Exception as exc:
        # Tabla aún no migrada / tests SimpleTestCase sin BD
        logger.warning(
            'No se pudo leer ConfiguracionProfitPerfil (uso .env): %s',
            exc,
        )
        return config

    # Una fila mala no tumba el resto de perfiles (se deja el .env en ese perfil)
    for fila in filas:
        if fila.perfil not in config:
            continue
        try:
            config[fila.perfil] = {
                'profit_target': float(fila.profit_target),
                'costos_fijos': fila.costos_fijos_lista(),
                'diagnostico': float(fila.diagnostico),
            }
        except (TypeError, ValueError) as exc:
            logger.warning(
                'Perfil profit "%s" inválido en BD; se mantiene .env: %s',
                fila.perfil,
                exc,
            )

    return config


def obtener_costeo_reacondicionado_config() -> Dict[str, float]:
    """
    Devuelve parámetros REAC vigentes (BD singleton con fallback .env).

    Returns:
        dict: Claves float usadas por calcular_costeo().

    Efectos secundarios:
        Solo lectura.
    """
    config = _cargar_reac_desde_env()

    try:
        from almacen.models import ConfiguracionReacondicionado

        # Preferir pk=1 (singleton del panel); si no existe, la fila más antigua
        fila = (
            ConfiguracionReacondicionado.objects.filter(pk=1).first()
            or ConfiguracionReacondicionado.objects.order_by('pk').first()
        )
        if fila is not None:
            config = fila.a_dict()
    except Exception as exc:
        logger.warning(
            'No se pudo leer ConfiguracionReacondicionado (uso .env): %s',
            exc,
        )

    return config


def asegurar_parametros_iniciales(usuario=None) -> bool:
    """
    Si la BD no tiene parámetros, los siembra desde el .env actual.

    Args:
        usuario: User opcional que queda como actualizado_por.

    Returns:
        bool: True si se creó al menos una fila nueva; False si ya existían.

    Efectos secundarios:
        Inserta filas en ConfiguracionProfitPerfil y/o ConfiguracionReacondicionado.
    """
    from almacen.models import ConfiguracionProfitPerfil, ConfiguracionReacondicionado

    creado = False
    env_profit = _cargar_profit_desde_env()
    env_reac = _cargar_reac_desde_env()

    with transaction.atomic():
        # Sembrar perfiles con get_or_create (evita carrera si dos gerentes
        # abren el panel a la vez en un tenant vacío)
        for perfil in PERFILES_PROFIT:
            datos = env_profit[perfil]
            costos_txt = ','.join(str(x) for x in datos['costos_fijos'])
            _obj, was_created = ConfiguracionProfitPerfil.objects.get_or_create(
                perfil=perfil,
                defaults={
                    'profit_target': Decimal(str(datos['profit_target'])),
                    'costos_fijos': costos_txt,
                    'diagnostico': Decimal(str(datos['diagnostico'])),
                    'actualizado_por': usuario,
                },
            )
            if was_created:
                creado = True
                logger.info('Sembrado perfil profit desde .env: %s', perfil)

        # Singleton REAC: crear solo si no hay ninguna fila
        if not ConfiguracionReacondicionado.objects.exists():
            ConfiguracionReacondicionado.objects.get_or_create(
                pk=1,
                defaults={
                    'recurso_front_desk_mensual': Decimal(
                        str(env_reac['recurso_front_desk_mensual'])
                    ),
                    'pct_front_desk': Decimal(str(env_reac['pct_front_desk'])),
                    'mantenimiento_materiales': Decimal(
                        str(env_reac['mantenimiento_materiales'])
                    ),
                    'gastos_operacion_ingeniero': Decimal(
                        str(env_reac['gastos_operacion_ingeniero'])
                    ),
                    'pct_overhead': Decimal(str(env_reac['pct_overhead'])),
                    'pct_mkt': Decimal(str(env_reac['pct_mkt'])),
                    'pct_comision_venta': Decimal(
                        str(env_reac['pct_comision_venta'])
                    ),
                    'pct_margen_ganancia': Decimal(
                        str(env_reac['pct_margen_ganancia'])
                    ),
                    'pct_iva': Decimal(str(env_reac['pct_iva'])),
                    'pct_comision_cobro_base': Decimal(
                        str(env_reac['pct_comision_cobro_base'])
                    ),
                    'pct_comision_3m': Decimal(str(env_reac['pct_comision_3m'])),
                    'pct_comision_6m': Decimal(str(env_reac['pct_comision_6m'])),
                    'pct_comision_12m': Decimal(str(env_reac['pct_comision_12m'])),
                    'actualizado_por': usuario,
                },
            )
            creado = True
            logger.info('Sembrada ConfiguracionReacondicionado desde .env')

    return creado


def puede_editar_parametros_cotizador(user) -> bool:
    """
    Indica si el usuario puede abrir/guardar el panel de parámetros.

    Acceso permitido:
        - Superusuario Django
        - Empleado con rol gerente_general
        - Empleado con rol gerente_operacional

    Args:
        user: Usuario autenticado (request.user).

    Returns:
        bool: True si tiene permiso.
    """
    from django.core.exceptions import ObjectDoesNotExist

    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if user.is_superuser:
        return True
    # OneToOne inverso: getattr(..., None) NO atrapa DoesNotExist
    try:
        empleado = user.empleado
    except ObjectDoesNotExist:
        return False
    if empleado and empleado.rol in ('gerente_general', 'gerente_operacional'):
        return True
    return False


def guardar_profit_perfiles(
    datos_por_perfil: Dict[str, Dict],
    usuario=None,
) -> None:
    """
    Guarda o actualiza los 6 perfiles de profit desde el formulario del panel.

    Args:
        datos_por_perfil: {
            'estandar': {
                'profit_target': Decimal|float,
                'costos_fijos': str,
                'diagnostico': Decimal|float,
            },
            ...
        }
        usuario: User que realiza el cambio (auditoría).

    Efectos secundarios:
        Crea/actualiza filas ConfiguracionProfitPerfil.
    """
    from almacen.models import ConfiguracionProfitPerfil

    with transaction.atomic():
        for perfil, datos in datos_por_perfil.items():
            if perfil not in PERFILES_PROFIT:
                continue
            ConfiguracionProfitPerfil.objects.update_or_create(
                perfil=perfil,
                defaults={
                    'profit_target': Decimal(str(datos['profit_target'])),
                    'costos_fijos': str(datos['costos_fijos']).strip(),
                    'diagnostico': Decimal(str(datos['diagnostico'])),
                    'actualizado_por': usuario,
                },
            )


def guardar_reacondicionado(datos: Dict, usuario=None) -> None:
    """
    Guarda la fila singleton de parámetros REAC.

    Args:
        datos: Dict con las claves de ConfiguracionReacondicionado.
        usuario: User que realiza el cambio.

    Efectos secundarios:
        update_or_create de ConfiguracionReacondicionado pk=1.
    """
    from almacen.models import ConfiguracionReacondicionado

    campos_decimal = [
        'recurso_front_desk_mensual',
        'pct_front_desk',
        'mantenimiento_materiales',
        'gastos_operacion_ingeniero',
        'pct_overhead',
        'pct_mkt',
        'pct_comision_venta',
        'pct_margen_ganancia',
        'pct_iva',
        'pct_comision_cobro_base',
        'pct_comision_3m',
        'pct_comision_6m',
        'pct_comision_12m',
    ]
    defaults = {campo: Decimal(str(datos[campo])) for campo in campos_decimal}
    defaults['actualizado_por'] = usuario

    ConfiguracionReacondicionado.objects.update_or_create(
        pk=1,
        defaults=defaults,
    )
