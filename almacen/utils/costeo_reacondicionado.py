"""
Motor de costeo para cotización de equipos reacondicionados (Certificados SIC).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Este módulo replica la matriz de Excel operativa para vender equipos
reacondicionados. A diferencia del cotizador de reparación (margen sobre piezas),
aquí se suman costos fijos y se resuelve el subtotal dividiendo entre
(1 - porcentajes variables de overhead, marketing, comisión y margen).

Los parámetros fijos se leen del .env; el vendedor captura en el modal
el costo de proveedor y los días de front desk.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from decouple import config as env_config


def _cargar_config_costeo() -> Dict[str, float]:
    """
    Lee los porcentajes y montos base del archivo .env.

    Returns:
        dict: Parámetros numéricos del Excel de Certificados SIC.
    """
    return {
        'recurso_front_desk_mensual': env_config(
            'REAC_RECURSO_FRONT_DESK_MENSUAL', cast=float, default=10000.0
        ),
        'pct_front_desk': env_config('REAC_PCT_FRONT_DESK', cast=float, default=0.21),
        'mantenimiento_materiales': env_config(
            'REAC_MANTENIMIENTO_MATERIALES', cast=float, default=25.0
        ),
        'gastos_operacion_ingeniero': env_config(
            'REAC_GASTOS_OPERACION_INGENIERO', cast=float, default=160.0
        ),
        'pct_overhead': env_config('REAC_PCT_OVERHEAD', cast=float, default=0.01),
        'pct_mkt': env_config('REAC_PCT_MKT', cast=float, default=0.01),
        'pct_comision_venta': env_config(
            'REAC_PCT_COMISION_VENTA', cast=float, default=0.036
        ),
        'pct_margen_ganancia': env_config(
            'REAC_PCT_MARGEN_GANANCIA', cast=float, default=0.194
        ),
        'pct_iva': env_config('REAC_PCT_IVA', cast=float, default=0.16),
        'pct_comision_cobro_base': env_config(
            'REAC_PCT_COMISION_COBRO_BASE', cast=float, default=0.035
        ),
        'pct_comision_3m': env_config('REAC_PCT_COMISION_3M', cast=float, default=0.0469),
        'pct_comision_6m': env_config('REAC_PCT_COMISION_6M', cast=float, default=0.0769),
        'pct_comision_12m': env_config(
            'REAC_PCT_COMISION_12M', cast=float, default=0.1289
        ),
    }


# Respaldo estático desde .env (compatibilidad / semilla).
# El valor VIGENTE se obtiene con obtener_costeo_reacondicionado_config().
COSTEO_REACONDICIONADO_CONFIG: Dict[str, float] = _cargar_config_costeo()


def _costeo_config_vigente() -> Dict[str, float]:
    """
    Parámetros REAC activos (panel BD + fallback .env).

    Import diferido para evitar ciclo con parametros_cotizador.
    """
    from .parametros_cotizador import obtener_costeo_reacondicionado_config

    return obtener_costeo_reacondicionado_config()


def calcular_costeo(
    costo_proveedor: float,
    dias_front_desk: int = 1,
    pct_margen_ganancia: Optional[float] = None,
    config: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """
    Calcula el desglose completo de costos, subtotales, precio de contado
    y opciones de pago diferido (matriz Certificados SIC).

    Args:
        costo_proveedor     : Costo de adquisición del equipo (MXN sin IVA).
        dias_front_desk     : Días de uso proporcional del recurso front desk.
        pct_margen_ganancia : Override opcional del margen (simulación).
        config              : Dict de parámetros; si es None usa panel/.env.

    Returns:
        dict: Resultados redondeados a 2 decimales, listos para PDF/email/JSON.
    """
    # Si el caller no pasa config, leemos la vigente (BD o .env)
    cfg = config or _costeo_config_vigente()
    margen = (
        pct_margen_ganancia
        if pct_margen_ganancia is not None
        else cfg['pct_margen_ganancia']
    )

    # 1. Gastos de administración proporcionales (Front Desk)
    diario_front_desk = cfg['recurso_front_desk_mensual'] / 30.0
    gastos_administracion = diario_front_desk * float(dias_front_desk) * cfg['pct_front_desk']

    # 2. Total de costos fijos directos
    costos_fijos = (
        float(costo_proveedor)
        + gastos_administracion
        + cfg['mantenimiento_materiales']
        + cfg['gastos_operacion_ingeniero']
    )

    # 3. Subtotal sin IVA (ecuación de costos variables)
    pct_variables_total = (
        cfg['pct_overhead']
        + cfg['pct_mkt']
        + cfg['pct_comision_venta']
        + margen
    )
    if pct_variables_total >= 1:
        raise ValueError('La suma de porcentajes variables debe ser menor a 100%.')
    subtotal_sin_iva = costos_fijos / (1.0 - pct_variables_total)

    # 4. Desglose de conceptos variables sobre el subtotal
    overhead = subtotal_sin_iva * cfg['pct_overhead']
    mkt = subtotal_sin_iva * cfg['pct_mkt']
    comision_venta = subtotal_sin_iva * cfg['pct_comision_venta']
    margen_ganancia = subtotal_sin_iva * margen

    # 5. IVA y precio total de contado
    iva = subtotal_sin_iva * cfg['pct_iva']
    total_contado = subtotal_sin_iva + iva

    def _calcular_monto_diferido(pct_meses: float) -> float:
        """Monto diferido absorbiendo comisiones bancarias + IVA."""
        pct_comision_total_con_iva = (
            cfg['pct_comision_cobro_base'] + pct_meses
        ) * (1.0 + cfg['pct_iva'])
        return total_contado / (1.0 - pct_comision_total_con_iva)

    return {
        'gastos_administracion_front_desk': round(gastos_administracion, 2),
        'total_costos_fijos': round(costos_fijos, 2),
        'desglose_variables': {
            'overhead': round(overhead, 2),
            'marketing': round(mkt, 2),
            'comision_venta': round(comision_venta, 2),
            'margen_ganancia': round(margen_ganancia, 2),
        },
        'subtotal_sin_iva': round(subtotal_sin_iva, 2),
        'iva': round(iva, 2),
        'total_precio_contado_mxn': round(total_contado, 2),
        'opciones_diferidas_con_iva': {
            'diferido_3_meses': round(_calcular_monto_diferido(cfg['pct_comision_3m']), 2),
            'diferido_6_meses': round(_calcular_monto_diferido(cfg['pct_comision_6m']), 2),
            'diferido_12_meses': round(_calcular_monto_diferido(cfg['pct_comision_12m']), 2),
        },
        'dias_front_desk': int(dias_front_desk),
        'costo_proveedor': round(float(costo_proveedor), 2),
        'pct_margen_ganancia_aplicado': margen,
    }


def serializar_config_costeo() -> Dict[str, float]:
    """
    Expone la configuración vigente para inyectarla en el modal (TypeScript).

    Returns:
        dict: Copia de los parámetros REAC (panel BD o .env).
    """
    return dict(_costeo_config_vigente())


IVA_FACTOR_REAC = 1.16


def obtener_precio_reac_con_iva(costeo: Optional[Dict[str, Any]], opcion: str):
    """
    Obtiene el monto con IVA según la forma de pago elegida por el cliente.

    Args:
        costeo: Snapshot resultado_costeo_reac de la solicitud.
        opcion: Clave de OPCION_PAGO_REAC_CHOICES (contado, diferido_3_meses, etc.).

    Returns:
        Decimal: Precio con IVA; 0 si no hay datos válidos.
    """
    from decimal import Decimal

    if not costeo or not opcion:
        return Decimal('0.00')

    if opcion == 'contado':
        valor = costeo.get('total_precio_contado_mxn')
    else:
        diferidos = costeo.get('opciones_diferidas_con_iva') or {}
        valor = diferidos.get(opcion)

    if valor is None:
        return Decimal('0.00')
    return Decimal(str(valor))


def obtener_precio_reac_sin_iva(costeo: Optional[Dict[str, Any]], opcion: str):
    """
    Convierte el precio con IVA a monto sin IVA (coherente con LineaCotizacion).

    Args:
        costeo: Snapshot de costeo reacondicionado.
        opcion: Forma de pago elegida.

    Returns:
        Decimal: Precio unitario al cliente sin IVA.
    """
    from decimal import Decimal, ROUND_HALF_UP

    con_iva = obtener_precio_reac_con_iva(costeo, opcion)
    if con_iva <= 0:
        return Decimal('0.00')
    return (con_iva / Decimal(str(IVA_FACTOR_REAC))).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )


def obtener_etiqueta_opcion_pago_reac(opcion: str) -> str:
    """
    Texto legible para mostrar en UI, PDF y notas de Venta Mostrador.

    Args:
        opcion: Valor de opcion_pago_reac.

    Returns:
        str: Etiqueta en español.
    """
    etiquetas = {
        'contado': 'Pago de contado',
        'diferido_3_meses': 'Financiamiento 3 meses',
        'diferido_6_meses': 'Financiamiento 6 meses',
        'diferido_12_meses': 'Financiamiento 12 meses',
    }
    return etiquetas.get(opcion, opcion or 'Sin especificar')
