"""
Utilidades para Análisis de Cotizaciones
Sistema de Dashboard con Pandas y Plotly

EXPLICACIÓN PARA PRINCIPIANTES:
Este archivo contiene funciones auxiliares que procesan datos de cotizaciones
y los convierten en DataFrames de Pandas para análisis y visualización.

Pandas DataFrame: Piensa en él como una "tabla Excel en Python" que puedes
manipular con código. Facilita cálculos, filtros y agregaciones.
"""

import pandas as pd
from django.db.models import Count, Sum, Avg, Q, F, Prefetch
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta, date
from .models import (
    Cotizacion, 
    PiezaCotizada, 
    SeguimientoPieza,
    OrdenServicio,
    DetalleEquipo
)
from inventario.models import Empleado, Sucursal
from config.constants import (
    ESTADOS_PIEZA_RECIBIDOS,
    ESTADOS_PIEZA_PENDIENTES,
    ESTADOS_PIEZA_PROBLEMATICOS
)


# ============================================================================
# FUNCIÓN 1: OBTENER DATAFRAME DE COTIZACIONES
# ============================================================================

def obtener_dataframe_cotizaciones(fecha_inicio=None, fecha_fin=None, 
                                   sucursal_id=None, tecnico_id=None, 
                                   gama=None):
    """
    Convierte QuerySet de cotizaciones a DataFrame de Pandas con filtros aplicados.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función es el "motor" del dashboard. Toma datos de la base de datos Django
    y los convierte en un DataFrame de Pandas que es más fácil de analizar.
    
    Args:
        fecha_inicio (str o date): Fecha inicio del filtro (YYYY-MM-DD)
        fecha_fin (str o date): Fecha fin del filtro (YYYY-MM-DD)
        sucursal_id (int): ID de sucursal para filtrar
        tecnico_id (int): ID de técnico para filtrar
        gama (str): Gama de equipo ('alta', 'media', 'baja')
    
    Returns:
        DataFrame: DataFrame de Pandas con todas las cotizaciones y sus datos relacionados
    
    Ejemplo de uso:
        df = obtener_dataframe_cotizaciones(
            fecha_inicio='2025-01-01',
            fecha_fin='2025-12-31',
            sucursal_id=1
        )
        print(f"Total cotizaciones: {len(df)}")
    """
    
    # ========================================
    # 1. CONSTRUIR QUERYSET BASE CON OPTIMIZACIONES
    # ========================================
    # EXPLICACIÓN: select_related() evita consultas múltiples a la BD
    # Es como hacer un JOIN en SQL
    cotizaciones = Cotizacion.objects.select_related(
        'orden',
        'orden__sucursal',
        'orden__tecnico_asignado_actual',
        'orden__responsable_seguimiento',
        'orden__detalle_equipo'
    ).prefetch_related(
        'piezas_cotizadas',
        'piezas_cotizadas__componente',
        'seguimientos_piezas'
    )
    
    # ========================================
    # 2. APLICAR FILTROS
    # ========================================
    
    # Filtro por rango de fechas
    if fecha_inicio:
        if isinstance(fecha_inicio, str):
            # Convertir string a datetime timezone-aware
            fecha_dt = datetime.strptime(fecha_inicio, '%Y-%m-%d')
            fecha_inicio = timezone.make_aware(fecha_dt) if timezone.is_naive(fecha_dt) else fecha_dt
        elif isinstance(fecha_inicio, date) and not isinstance(fecha_inicio, datetime):
            # Convertir date a datetime timezone-aware (inicio del día)
            fecha_dt = datetime.combine(fecha_inicio, datetime.min.time())
            fecha_inicio = timezone.make_aware(fecha_dt)
        cotizaciones = cotizaciones.filter(fecha_envio__gte=fecha_inicio)
    
    if fecha_fin:
        if isinstance(fecha_fin, str):
            # Convertir string a datetime timezone-aware (fin del día)
            fecha_dt = datetime.strptime(fecha_fin, '%Y-%m-%d')
            fecha_dt = datetime.combine(fecha_dt, datetime.max.time())
            fecha_fin = timezone.make_aware(fecha_dt) if timezone.is_naive(fecha_dt) else fecha_dt
        elif isinstance(fecha_fin, date) and not isinstance(fecha_fin, datetime):
            # Convertir date a datetime timezone-aware (fin del día)
            fecha_dt = datetime.combine(fecha_fin, datetime.max.time())
            fecha_fin = timezone.make_aware(fecha_dt)
        cotizaciones = cotizaciones.filter(fecha_envio__lte=fecha_fin)
    
    # Filtro por sucursal
    if sucursal_id:
        cotizaciones = cotizaciones.filter(orden__sucursal_id=sucursal_id)
    
    # Filtro por técnico
    if tecnico_id:
        cotizaciones = cotizaciones.filter(orden__tecnico_asignado_actual_id=tecnico_id)
    
    # Filtro por gama
    if gama:
        cotizaciones = cotizaciones.filter(orden__detalle_equipo__gama=gama)
    
    # ========================================
    # 3. CONVERTIR A DATAFRAME
    # ========================================
    
    data = []
    
    for cot in cotizaciones:
        # Obtener datos relacionados
        orden = cot.orden
        detalle = orden.detalle_equipo if hasattr(orden, 'detalle_equipo') else None
        
        # Contar piezas
        total_piezas = cot.piezas_cotizadas.count()
        piezas_aceptadas = cot.piezas_cotizadas.filter(aceptada_por_cliente=True).count()
        piezas_rechazadas = cot.piezas_cotizadas.filter(aceptada_por_cliente=False).count()
        piezas_sugeridas_tecnico = cot.piezas_cotizadas.filter(sugerida_por_tecnico=True).count()
        piezas_necesarias = cot.piezas_cotizadas.filter(es_necesaria=True).count()
        
        # Calcular porcentajes
        porcentaje_aceptadas = (piezas_aceptadas / total_piezas * 100) if total_piezas > 0 else 0
        porcentaje_necesarias = (piezas_necesarias / total_piezas * 100) if total_piezas > 0 else 0
        
        # Construir fila del DataFrame
        fila = {
            # IDs
            'cotizacion_id': cot.orden_id,
            'orden_id': orden.id,
            'numero_orden': orden.numero_orden_interno,
            'orden_cliente': detalle.orden_cliente if detalle else '',
            'numero_serie': detalle.numero_serie if detalle else '',
            
            # Fechas
            'fecha_envio': cot.fecha_envio,
            'fecha_respuesta': cot.fecha_respuesta,
            'dias_sin_respuesta': cot.dias_sin_respuesta,
            'año': orden.año,
            'mes': orden.mes,
            'semana': orden.semana,
            
            # Estado de cotización
            'aceptada': cot.usuario_acepto,
            'motivo_rechazo': cot.motivo_rechazo if cot.usuario_acepto == False else None,
            'detalle_rechazo': cot.detalle_rechazo if cot.usuario_acepto == False else '',
            
            # Costos
            'costo_mano_obra': float(cot.costo_mano_obra),
            'costo_total_piezas': float(cot.costo_total_piezas),
            'costo_total': float(cot.costo_total),
            'costo_piezas_aceptadas': float(cot.costo_piezas_aceptadas),
            'costo_piezas_rechazadas': float(cot.costo_piezas_rechazadas),
            'costo_total_final': float(cot.costo_total_final),
            'descontar_mano_obra': cot.descontar_mano_obra,
            'monto_descuento': float(cot.monto_descuento_mano_obra),
            
            # Información de la orden
            'sucursal': orden.sucursal.nombre if orden.sucursal else 'Sin sucursal',
            'sucursal_id': orden.sucursal_id,
            'tecnico': orden.tecnico_asignado_actual.nombre_completo if orden.tecnico_asignado_actual else 'Sin técnico',
            'tecnico_id': orden.tecnico_asignado_actual_id,
            'responsable': orden.responsable_seguimiento.nombre_completo if orden.responsable_seguimiento else 'Sin responsable',
            'responsable_id': orden.responsable_seguimiento_id,
            'estado_orden': orden.estado,
            'estado_orden_display': orden.get_estado_display(),
            
            # Información del equipo
            'gama': detalle.gama if detalle else 'media',
            'marca': detalle.marca if detalle else '',
            'modelo': detalle.modelo if detalle else '',
            'tipo_equipo': detalle.tipo_equipo if detalle else '',
            
            # Métricas de piezas
            'total_piezas': total_piezas,
            'piezas_aceptadas': piezas_aceptadas,
            'piezas_rechazadas': piezas_rechazadas,
            'piezas_pendientes': total_piezas - piezas_aceptadas - piezas_rechazadas,
            'piezas_sugeridas_tecnico': piezas_sugeridas_tecnico,
            'piezas_necesarias': piezas_necesarias,
            'porcentaje_aceptadas': round(porcentaje_aceptadas, 2),
            'porcentaje_necesarias': round(porcentaje_necesarias, 2),
            
            # Seguimientos de piezas
            'tiene_seguimientos': cot.seguimientos_piezas.exists(),
            'num_seguimientos': cot.seguimientos_piezas.count(),
        }
        
        data.append(fila)
    
    # Crear DataFrame
    df = pd.DataFrame(data)
    
    # Si no hay datos, retornar DataFrame vacío con columnas
    if df.empty:
        return pd.DataFrame(columns=[
            'cotizacion_id', 'orden_id', 'numero_orden', 'orden_cliente', 'numero_serie',
            'fecha_envio', 'fecha_respuesta', 'aceptada', 'costo_total', 
            'sucursal', 'tecnico', 'gama'
        ])
    
    # Convertir fecha_envio a datetime si no lo es
    if not pd.api.types.is_datetime64_any_dtype(df['fecha_envio']):
        df['fecha_envio'] = pd.to_datetime(df['fecha_envio'])
    
    return df


# ============================================================================
# FUNCIÓN 2: CALCULAR KPIs GENERALES
# ============================================================================

def calcular_kpis_generales(df):
    """
    Calcula KPIs (Key Performance Indicators) principales del dashboard.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    KPI = Indicador Clave de Desempeño. Son métricas que te dicen rápidamente
    cómo está funcionando tu negocio.
    
    Args:
        df (DataFrame): DataFrame de cotizaciones
    
    Returns:
        dict: Diccionario con todos los KPIs calculados
    
    Ejemplo de retorno:
        {
            'total_cotizaciones': 150,
            'aceptadas': 95,
            'rechazadas': 40,
            'pendientes': 15,
            'tasa_aceptacion': 63.33,
            ...
        }
    """
    
    if df.empty:
        return {
            'total_cotizaciones': 0,
            'aceptadas': 0,
            'rechazadas': 0,
            'pendientes': 0,
            'tasa_aceptacion': 0,
            'tasa_rechazo': 0,
            'valor_total_cotizado': 0,
            'valor_aceptado': 0,
            'valor_rechazado': 0,
            'valor_pendiente': 0,
            'tiempo_respuesta_promedio': 0,
            'ticket_promedio': 0,
            'piezas_promedio': 0,
        }
    
    # Totales básicos
    total = len(df)
    aceptadas = len(df[df['aceptada'] == True])
    rechazadas = len(df[df['aceptada'] == False])
    pendientes = len(df[df['aceptada'].isna()])
    
    # Tasas (porcentajes)
    tasa_aceptacion = (aceptadas / total * 100) if total > 0 else 0
    tasa_rechazo = (rechazadas / total * 100) if total > 0 else 0
    tasa_pendiente = (pendientes / total * 100) if total > 0 else 0
    
    # Valores monetarios
    valor_total = df['costo_total'].sum()
    valor_aceptado = df[df['aceptada'] == True]['costo_total_final'].sum()
    valor_rechazado = df[df['aceptada'] == False]['costo_total'].sum()
    valor_pendiente = df[df['aceptada'].isna()]['costo_total'].sum()
    
    # Métricas de tiempo
    tiempo_respuesta_promedio = df['dias_sin_respuesta'].mean()
    
    # Ticket promedio
    ticket_promedio = df['costo_total'].mean()
    ticket_aceptado_promedio = df[df['aceptada'] == True]['costo_total_final'].mean()
    
    # Métricas de piezas
    piezas_promedio = df['total_piezas'].mean()
    piezas_aceptadas_promedio = df['piezas_aceptadas'].mean()
    total_piezas_cotizadas = df['total_piezas'].sum()  # Suma total de todas las piezas
    
    # Construir diccionario de KPIs
    kpis = {
        # Totales
        'total_cotizaciones': total,
        'aceptadas': aceptadas,
        'rechazadas': rechazadas,
        'pendientes': pendientes,
        
        # Tasas (%)
        'tasa_aceptacion': round(tasa_aceptacion, 2),
        'tasa_rechazo': round(tasa_rechazo, 2),
        'tasa_pendiente': round(tasa_pendiente, 2),
        
        # Valores monetarios
        'valor_total_cotizado': round(valor_total, 2),
        'valor_aceptado': round(valor_aceptado, 2),
        'valor_rechazado': round(valor_rechazado, 2),
        'valor_pendiente': round(valor_pendiente, 2),
        
        # Promedios
        'tiempo_respuesta_promedio': round(tiempo_respuesta_promedio, 1),
        'ticket_promedio': round(ticket_promedio, 2),
        'ticket_aceptado_promedio': round(ticket_aceptado_promedio, 2) if not pd.isna(ticket_aceptado_promedio) else 0,
        'piezas_promedio': round(piezas_promedio, 1),
        'piezas_aceptadas_promedio': round(piezas_aceptadas_promedio, 1),
        
        # Totales de piezas
        'total_piezas': int(total_piezas_cotizadas) if not pd.isna(total_piezas_cotizadas) else 0,
        
        # Formato con separadores de miles
        'valor_total_cotizado_fmt': f"${valor_total:,.2f}",
        'valor_aceptado_fmt': f"${valor_aceptado:,.2f}",
        'valor_rechazado_fmt': f"${valor_rechazado:,.2f}",
        'ticket_promedio_fmt': f"${ticket_promedio:,.2f}",
    }
    
    return kpis


# ============================================================================
# FUNCIÓN 3: ANALIZAR PIEZAS COTIZADAS
# ============================================================================

def analizar_piezas_cotizadas(cotizacion_ids=None):
    """
    Analiza patrones de piezas aceptadas/rechazadas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función crea un DataFrame específico de PIEZAS (no cotizaciones),
    permitiendo analizar qué componentes se aceptan más, cuáles se rechazan,
    y si las piezas sugeridas por técnicos tienen mejor tasa de aceptación.
    
    LÓGICA DE HERENCIA DE ACEPTACIÓN:
    Si una pieza no tiene respuesta individual (aceptada_por_cliente=None),
    hereda el estado de aceptación de la cotización completa (usuario_acepto).
    Esto permite analizar piezas de cotizaciones aceptadas/rechazadas globalmente
    cuando el cliente no especificó piezas individuales.
    
    Args:
        cotizacion_ids (list): Lista de IDs de cotizaciones a analizar (opcional)
    
    Returns:
        DataFrame: DataFrame con datos de piezas cotizadas
    """
    
    # QuerySet base
    piezas = PiezaCotizada.objects.select_related(
        'cotizacion',
        'cotizacion__orden',
        'componente'
    )
    
    # Filtrar por cotizaciones específicas si se proporcionan
    if cotizacion_ids:
        piezas = piezas.filter(cotizacion_id__in=cotizacion_ids)
    
    # Convertir a DataFrame
    data = []
    for pieza in piezas:
        # Determinar estado de aceptación con herencia
        # Si la pieza tiene respuesta explícita, usarla
        # Si no, heredar de la cotización (si la cotización fue respondida)
        aceptacion_pieza = pieza.aceptada_por_cliente
        if aceptacion_pieza is None:
            # Heredar de cotización si existe
            aceptacion_pieza = pieza.cotizacion.usuario_acepto
        
        data.append({
            'pieza_id': pieza.id,
            'cotizacion_id': pieza.cotizacion_id,
            'componente': pieza.componente.nombre if pieza.componente else 'Sin componente',
            'componente_id': pieza.componente_id,
            'descripcion': pieza.descripcion_adicional,
            'sugerida_por_tecnico': pieza.sugerida_por_tecnico,
            'es_necesaria': pieza.es_necesaria,
            'cantidad': pieza.cantidad,
            'costo_unitario': float(pieza.costo_unitario),
            'costo_total': float(pieza.costo_total),
            'aceptada': aceptacion_pieza,  # Ahora con herencia
            'aceptada_explicita': pieza.aceptada_por_cliente,  # Original sin herencia
            'motivo_rechazo': pieza.motivo_rechazo_pieza if pieza.aceptada_por_cliente == False else '',
            'orden_prioridad': pieza.orden_prioridad,
        })
    
    df = pd.DataFrame(data)
    return df


# ============================================================================
# FUNCIÓN 4: ANALIZAR PROVEEDORES
# ============================================================================

def analizar_proveedores(cotizacion_ids=None):
    """
    Analiza rendimiento de proveedores (tiempos de entrega, cumplimiento, etc.).
    
    Args:
        cotizacion_ids (list): Lista de IDs de cotizaciones a analizar (opcional)
    
    Returns:
        DataFrame: DataFrame con datos de seguimientos de proveedores
    """
    
    # QuerySet base
    seguimientos = SeguimientoPieza.objects.select_related('cotizacion')
    
    # Filtrar por cotizaciones específicas si se proporcionan
    if cotizacion_ids:
        seguimientos = seguimientos.filter(cotizacion_id__in=cotizacion_ids)
    
    # Convertir a DataFrame
    data = []
    for seg in seguimientos:
        data.append({
            'seguimiento_id': seg.id,
            'cotizacion_id': seg.cotizacion_id,
            'proveedor': seg.proveedor,
            'descripcion_piezas': seg.descripcion_piezas,
            'numero_pedido': seg.numero_pedido,
            'fecha_pedido': seg.fecha_pedido,
            'fecha_entrega_estimada': seg.fecha_entrega_estimada,
            'fecha_entrega_real': seg.fecha_entrega_real,
            'estado': seg.estado,
            'dias_desde_pedido': seg.dias_desde_pedido,
            'esta_retrasado': seg.esta_retrasado,
            'dias_retraso': seg.dias_retraso,
            'notas': seg.notas_seguimiento,
        })
    
    df = pd.DataFrame(data)
    return df


# ============================================================================
# FUNCIÓN 5: CALCULAR MÉTRICAS POR TÉCNICO
# ============================================================================

def calcular_metricas_por_tecnico(df):
    """
    Calcula métricas de rendimiento por técnico.
    
    Args:
        df (DataFrame): DataFrame de cotizaciones
    
    Returns:
        DataFrame: DataFrame con métricas por técnico
    """
    
    if df.empty:
        return pd.DataFrame(columns=['tecnico', 'total', 'aceptadas', 'tasa_aceptacion'])
    
    # Agrupar por técnico
    metricas = df.groupby('tecnico').agg({
        'cotizacion_id': 'count',  # Total cotizaciones
        'aceptada': lambda x: (x == True).sum(),  # Total aceptadas
        'costo_total': 'sum',  # Valor total cotizado
    }).reset_index()
    
    # Calcular valor aceptado de forma separada para evitar warning
    valor_aceptado = df[df['aceptada'] == True].groupby('tecnico')['costo_total_final'].sum()
    metricas['valor_aceptado'] = metricas['tecnico'].map(valor_aceptado).fillna(0)
    
    metricas.columns = ['tecnico', 'total', 'aceptadas', 'valor_cotizado', 'valor_aceptado']
    
    # Calcular tasa de aceptación
    metricas['tasa_aceptacion'] = (metricas['aceptadas'] / metricas['total'] * 100).round(2)
    
    # Ordenar por tasa de aceptación descendente
    metricas = metricas.sort_values('tasa_aceptacion', ascending=False)
    
    return metricas


# ============================================================================
# FUNCIÓN 6: CALCULAR MÉTRICAS POR SUCURSAL
# ============================================================================

def calcular_metricas_por_sucursal(df):
    """
    Calcula métricas de rendimiento por sucursal.
    
    Args:
        df (DataFrame): DataFrame de cotizaciones
    
    Returns:
        DataFrame: DataFrame con métricas por sucursal
    """
    
    if df.empty:
        return pd.DataFrame(columns=['sucursal', 'total', 'aceptadas', 'tasa_aceptacion'])
    
    # Agrupar por sucursal
    metricas = df.groupby('sucursal').agg({
        'cotizacion_id': 'count',
        'aceptada': lambda x: (x == True).sum(),
        'costo_total': 'sum',
    }).reset_index()
    
    # Calcular valor aceptado de forma separada para evitar warning
    valor_aceptado = df[df['aceptada'] == True].groupby('sucursal')['costo_total_final'].sum()
    metricas['valor_aceptado'] = metricas['sucursal'].map(valor_aceptado).fillna(0)
    
    metricas.columns = ['sucursal', 'total', 'aceptadas', 'valor_cotizado', 'valor_aceptado']
    
    # Calcular tasa de aceptación
    metricas['tasa_aceptacion'] = (metricas['aceptadas'] / metricas['total'] * 100).round(2)
    
    # Ordenar por tasa de aceptación descendente
    metricas = metricas.sort_values('tasa_aceptacion', ascending=False)
    
    return metricas


# ============================================================================
# FUNCIÓN 7: CALCULAR MÉTRICAS POR RESPONSABLE DE SEGUIMIENTO
# ============================================================================

def calcular_metricas_por_responsable(df):
    """
    Calcula métricas de rendimiento por responsable de seguimiento.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Los responsables de seguimiento son los empleados encargados de dar seguimiento
    a las órdenes y cotizaciones. Esta función analiza su desempeño:
    - ¿Cuántas cotizaciones envían?
    - ¿Qué tasa de aceptación tienen?
    - ¿Cuánto valor generan?
    - ¿Cuántas piezas ofrecen en promedio?
    
    Args:
        df (DataFrame): DataFrame de cotizaciones
    
    Returns:
        DataFrame: DataFrame con métricas por responsable
        
    Columnas retornadas:
        - responsable: Nombre del responsable
        - total: Total de cotizaciones enviadas
        - aceptadas: Cotizaciones aceptadas
        - rechazadas: Cotizaciones rechazadas
        - pendientes: Cotizaciones sin respuesta
        - tasa_aceptacion: Porcentaje de aceptación
        - valor_cotizado: Valor total cotizado
        - valor_aceptado: Valor real generado (ingresos)
        - piezas_promedio: Promedio de piezas por cotización
        - tiempo_respuesta_promedio: Días promedio hasta respuesta
    """
    
    if df.empty:
        return pd.DataFrame(columns=[
            'responsable', 'total', 'aceptadas', 'rechazadas', 'pendientes',
            'tasa_aceptacion', 'valor_cotizado', 'valor_aceptado', 'piezas_promedio'
        ])
    
    # Filtrar responsables válidos (no nulos)
    df_valido = df[df['responsable'] != 'Sin responsable'].copy()
    
    if df_valido.empty:
        return pd.DataFrame(columns=[
            'responsable', 'total', 'aceptadas', 'rechazadas', 'pendientes',
            'tasa_aceptacion', 'valor_cotizado', 'valor_aceptado', 'piezas_promedio'
        ])
    
    # Agrupar por responsable
    metricas = df_valido.groupby('responsable').agg({
        'cotizacion_id': 'count',  # Total cotizaciones
        'aceptada': [
            lambda x: (x == True).sum(),  # Aceptadas
            lambda x: (x == False).sum(),  # Rechazadas
            lambda x: x.isna().sum()  # Pendientes
        ],
        'costo_total': 'sum',  # Valor total cotizado
        'total_piezas': 'mean',  # Promedio de piezas
        'dias_sin_respuesta': 'mean'  # Tiempo respuesta promedio
    }).reset_index()
    
    # Aplanar nombres de columnas multinivel
    metricas.columns = [
        'responsable', 'total', 'aceptadas', 'rechazadas', 'pendientes',
        'valor_cotizado', 'piezas_promedio', 'tiempo_respuesta_promedio'
    ]
    
    # Calcular valor aceptado de forma separada para evitar warning
    valor_aceptado = df_valido[df_valido['aceptada'] == True].groupby('responsable')['costo_total_final'].sum()
    metricas['valor_aceptado'] = metricas['responsable'].map(valor_aceptado).fillna(0)
    
    # Calcular tasa de aceptación
    metricas['tasa_aceptacion'] = (metricas['aceptadas'] / metricas['total'] * 100).round(2)
    
    # Redondear promedios
    metricas['piezas_promedio'] = metricas['piezas_promedio'].round(1)
    metricas['tiempo_respuesta_promedio'] = metricas['tiempo_respuesta_promedio'].round(1)
    
    # Reordenar columnas
    metricas = metricas[[
        'responsable', 'total', 'aceptadas', 'rechazadas', 'pendientes',
        'tasa_aceptacion', 'valor_cotizado', 'valor_aceptado', 
        'piezas_promedio', 'tiempo_respuesta_promedio'
    ]]
    
    # Ordenar por total de cotizaciones descendente
    metricas = metricas.sort_values('total', ascending=False)
    
    return metricas


# ============================================================================
# FUNCIÓN 8: ANALIZAR IMPACTO DE PROVEEDORES EN CONVERSIÓN
# ============================================================================

def analizar_proveedores_con_conversion(cotizacion_ids=None):
    """
    Analiza el impacto de proveedores en la conversión de ventas A NIVEL DE PIEZA.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función analiza TODAS las piezas cotizadas con proveedor asignado,
    independientemente de si tienen seguimiento o no. Esto permite ver:
    - Piezas aceptadas (que generaron pedidos)
    - Piezas rechazadas (que el cliente no quiso)
    - Piezas pendientes de respuesta
    
    ¿Por qué es importante?
    - No todos los proveedores contribuyen igual a las ventas
    - Un proveedor puede tener piezas rechazadas frecuentemente
    - Permite identificar proveedores con baja conversión
    - Una cotización puede tener PIEZAS aceptadas y otras rechazadas
    
    CORRECCIÓN DICIEMBRE 2025:
    Ahora analiza TODAS las piezas cotizadas con proveedor, no solo las que
    tienen seguimiento. Esto incluye piezas rechazadas que nunca generan pedido.
    
    Args:
        cotizacion_ids (list): Lista de IDs de cotizaciones a analizar (opcional)
    
    Returns:
        DataFrame: DataFrame con métricas de impacto por proveedor
        
    Columnas retornadas:
        - proveedor: Nombre del proveedor
        - total_piezas_cotizadas: Total de piezas cotizadas con este proveedor
        - piezas_aceptadas: Piezas aceptadas por el cliente
        - piezas_rechazadas: Piezas rechazadas por el cliente
        - piezas_sin_respuesta: Piezas sin respuesta del cliente
        - tasa_aceptacion: % de piezas aceptadas
        - tasa_rechazo: % de piezas rechazadas
        - total_pedidos: Seguimientos/pedidos realizados a este proveedor
        - tiempo_entrega_promedio: Días promedio de entrega (solo piezas con seguimiento)
        - valor_cotizado_total: Valor total cotizado
        - valor_generado: Ingresos reales (solo piezas aceptadas)
    """
    from servicio_tecnico.models import PiezaCotizada, SeguimientoPieza
    
    # PASO 1: Obtener TODAS las piezas cotizadas con proveedor asignado
    piezas_query = PiezaCotizada.objects.select_related(
        'cotizacion',
        'cotizacion__orden',
        'componente'
    ).exclude(proveedor='').exclude(proveedor__isnull=True)
    
    # Filtrar por cotizaciones específicas si se proporcionan
    if cotizacion_ids:
        piezas_query = piezas_query.filter(cotizacion_id__in=cotizacion_ids)
    
    # Convertir a lista para procesamiento
    data_piezas = []
    
    for pieza in piezas_query:
        data_piezas.append({
            'pieza_id': pieza.id,
            'proveedor': pieza.proveedor,
            'componente': pieza.componente.nombre,
            'cantidad': pieza.cantidad,
            'costo_total': float(pieza.costo_total),
            'aceptada': pieza.aceptada_por_cliente,  # True/False/None
            'cotizacion_id': pieza.cotizacion_id,
        })
    
    df_piezas = pd.DataFrame(data_piezas)
    
    if df_piezas.empty:
        return pd.DataFrame(columns=[
            'proveedor', 'total_piezas_cotizadas', 'piezas_aceptadas', 
            'piezas_rechazadas', 'piezas_sin_respuesta',
            'tasa_aceptacion', 'tasa_rechazo', 'total_pedidos',
            'tiempo_entrega_promedio', 'valor_cotizado_total', 'valor_generado'
        ])
    
    # PASO 2: Obtener datos de seguimientos para tiempos de entrega
    seguimientos_query = SeguimientoPieza.objects.all()
    if cotizacion_ids:
        seguimientos_query = seguimientos_query.filter(cotizacion_id__in=cotizacion_ids)
    
    # Crear diccionario de tiempos de entrega por proveedor
    tiempos_por_proveedor = {}
    pedidos_por_proveedor = {}
    
    for seg in seguimientos_query:
        proveedor = seg.proveedor
        
        # Contar pedidos
        if proveedor not in pedidos_por_proveedor:
            pedidos_por_proveedor[proveedor] = 0
        pedidos_por_proveedor[proveedor] += 1
        
        # Calcular tiempo de entrega
        if seg.fecha_entrega_real:
            tiempo_entrega = (seg.fecha_entrega_real - seg.fecha_pedido).days
            if proveedor not in tiempos_por_proveedor:
                tiempos_por_proveedor[proveedor] = []
            tiempos_por_proveedor[proveedor].append(tiempo_entrega)
    
    # PASO 3: Agrupar por proveedor y calcular métricas
    metricas = []
    
    for proveedor in df_piezas['proveedor'].unique():
        df_prov = df_piezas[df_piezas['proveedor'] == proveedor]
        
        # Métricas de piezas
        total_piezas = len(df_prov)
        piezas_aceptadas = (df_prov['aceptada'] == True).sum()
        piezas_rechazadas = (df_prov['aceptada'] == False).sum()
        piezas_sin_respuesta = (df_prov['aceptada'].isna()).sum()
        
        # Calcular tasas (solo sobre piezas con respuesta)
        piezas_con_respuesta = piezas_aceptadas + piezas_rechazadas
        
        if piezas_con_respuesta > 0:
            tasa_aceptacion = (piezas_aceptadas / piezas_con_respuesta * 100)
            tasa_rechazo = (piezas_rechazadas / piezas_con_respuesta * 100)
        else:
            tasa_aceptacion = 0
            tasa_rechazo = 0
        
        # Tiempo de entrega promedio (de seguimientos)
        if proveedor in tiempos_por_proveedor and len(tiempos_por_proveedor[proveedor]) > 0:
            tiempo_promedio = sum(tiempos_por_proveedor[proveedor]) / len(tiempos_por_proveedor[proveedor])
        else:
            tiempo_promedio = None
        
        # Total de pedidos (de seguimientos)
        total_pedidos = pedidos_por_proveedor.get(proveedor, 0)
        
        # Valores monetarios
        valor_cotizado = df_prov['costo_total'].sum()
        valor_generado = df_prov[df_prov['aceptada'] == True]['costo_total'].sum()
        
        metricas.append({
            'proveedor': proveedor,
            'total_piezas_cotizadas': total_piezas,
            'piezas_aceptadas': piezas_aceptadas,
            'piezas_rechazadas': piezas_rechazadas,
            'piezas_sin_respuesta': piezas_sin_respuesta,
            'tasa_aceptacion': round(tasa_aceptacion, 1),
            'tasa_rechazo': round(tasa_rechazo, 1),
            'total_pedidos': total_pedidos,
            'tiempo_entrega_promedio': round(tiempo_promedio, 1) if tiempo_promedio else None,
            'valor_cotizado_total': round(valor_cotizado, 2),
            'valor_generado': round(valor_generado, 2),
        })
    
    df_metricas = pd.DataFrame(metricas)
    
    # Ordenar por valor generado descendente
    df_metricas = df_metricas.sort_values('valor_generado', ascending=False)
    
    return df_metricas


# ============================================================================
# FUNCIÓN 9: ANALIZAR COMPONENTES POR PROVEEDOR
# ============================================================================

def analizar_componentes_por_proveedor(cotizacion_ids=None):
    """
    Analiza qué componentes suministra cada proveedor y su resultado (TODAS las piezas).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función crea una vista detallada de qué tipo de piezas (RAM, disco,
    pantalla, etc.) suministra cada proveedor y qué tan exitosas son.
    Analiza TODAS las piezas cotizadas con proveedor, incluyendo rechazadas.
    
    ¿Para qué sirve?
    - Identificar especialización de proveedores
    - Detectar proveedores con buena calidad en ciertos componentes
    - Ver qué componentes generan más rechazo por proveedor
    - Diversificar riesgos (no depender de un solo proveedor)
    - Negociar mejores precios en componentes donde tienen volumen
    
    CORRECCIÓN DICIEMBRE 2025:
    Ahora analiza TODAS las piezas cotizadas con proveedor asignado,
    no solo las que tienen seguimiento. Esto incluye piezas rechazadas.
    
    Args:
        cotizacion_ids (list): Lista de IDs de cotizaciones a analizar (opcional)
    
    Returns:
        DataFrame: DataFrame jerárquico para visualización Sunburst
        
    Columnas retornadas:
        - componente_nombre: Nombre del componente (RAM, Disco, etc.)
        - proveedor: Nombre del proveedor
        - resultado: Aceptado/Rechazado/Sin Respuesta
        - cantidad: Número de piezas en esta combinación
        - valor_total: Valor total de esas piezas
    """
    from servicio_tecnico.models import PiezaCotizada
    
    # Obtener TODAS las piezas cotizadas con proveedor asignado
    piezas_query = PiezaCotizada.objects.select_related(
        'componente',
        'cotizacion'
    ).exclude(proveedor='').exclude(proveedor__isnull=True)
    
    # Filtrar por cotizaciones específicas si se proporcionan
    if cotizacion_ids:
        piezas_query = piezas_query.filter(cotizacion_id__in=cotizacion_ids)
    
    # Convertir a lista para procesamiento
    data = []
    
    for pieza in piezas_query:
        # Determinar resultado basado en aceptación del cliente
        if pieza.aceptada_por_cliente is None:
            resultado = 'Sin Respuesta'
        elif pieza.aceptada_por_cliente:
            resultado = 'Aceptado'
        else:
            resultado = 'Rechazado'
        
        data.append({
            'componente_nombre': pieza.componente.nombre,
            'proveedor': pieza.proveedor,
            'resultado': resultado,
            'cantidad': pieza.cantidad,
            'valor_total': float(pieza.costo_total),
        })
    
    df = pd.DataFrame(data)
    
    if df.empty:
        return pd.DataFrame(columns=[
            'componente_nombre', 'proveedor', 'resultado', 'cantidad', 'valor_total'
        ])
    
    # Agrupar y sumar por componente, proveedor y resultado
    df_agrupado = df.groupby(['componente_nombre', 'proveedor', 'resultado']).agg({
        'cantidad': 'sum',
        'valor_total': 'sum'
    }).reset_index()
    
    # Ordenar por componente y valor
    df_agrupado = df_agrupado.sort_values(['componente_nombre', 'valor_total'], ascending=[True, False])
    
    return df_agrupado


# ============================================================================
# FUNCIÓN 12: OBTENER DATAFRAME DE SEGUIMIENTOS DE PIEZAS
# ============================================================================

def obtener_dataframe_seguimientos_piezas(fecha_inicio=None, fecha_fin=None,
                                          sucursal_id=None, proveedor=None,
                                          estado=None):
    """
    Convierte QuerySet de seguimientos de piezas a DataFrame de Pandas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Similar a obtener_dataframe_cotizaciones pero enfocado en seguimientos de piezas.
    Extrae información relevante de pedidos de piezas incluyendo:
    - Estado actual del pedido
    - Fechas y tiempos de entrega
    - Información de la orden relacionada
    - Cálculo de días de retraso
    
    Args:
        fecha_inicio (date): Fecha inicio de pedidos
        fecha_fin (date): Fecha fin de pedidos
        sucursal_id (int): Filtrar por sucursal
        proveedor (str): Filtrar por proveedor específico
        estado (str): Filtrar por estado (pedido, transito, recibido, etc.)
    
    Returns:
        DataFrame: DataFrame con todos los seguimientos y métricas calculadas
    
    Columnas del DataFrame:
        - id: ID del seguimiento
        - orden_numero: Número de orden relacionada
        - proveedor: Nombre del proveedor
        - estado: Estado actual
        - fecha_pedido: Cuándo se pidió
        - fecha_entrega_estimada: Cuándo debería llegar
        - fecha_entrega_real: Cuándo llegó (si aplica)
        - dias_desde_pedido: Días transcurridos
        - dias_retraso: Días de retraso (0 si no hay)
        - esta_retrasado: Boolean
        - sucursal: Nombre de la sucursal
        - descripcion_piezas: Qué se pidió
        - numero_pedido: Tracking del proveedor
    """
    from django.db.models import Q, F
    from django.utils import timezone
    
    # Construir QuerySet base con relaciones optimizadas
    queryset = SeguimientoPieza.objects.select_related(
        'cotizacion__orden__sucursal',
        'cotizacion__orden__detalle_equipo',
        'cotizacion__orden__responsable_seguimiento'
    ).prefetch_related(
        'piezas'
    )
    
    # Aplicar filtros
    if fecha_inicio:
        queryset = queryset.filter(fecha_pedido__gte=fecha_inicio)
    
    if fecha_fin:
        queryset = queryset.filter(fecha_pedido__lte=fecha_fin)
    
    if sucursal_id:
        queryset = queryset.filter(cotizacion__orden__sucursal_id=sucursal_id)
    
    if proveedor:
        queryset = queryset.filter(proveedor__icontains=proveedor)
    
    if estado:
        queryset = queryset.filter(estado=estado)
    
    # Convertir a lista de diccionarios
    data = []
    hoy = timezone.now().date()
    
    for seg in queryset:
        orden = seg.cotizacion.orden
        detalle = orden.detalle_equipo
        
        # Calcular métricas
        # CORREGIDO: dias_desde_pedido debe considerar fecha_entrega_real si existe
        if seg.fecha_entrega_real:
            # Si ya llegó, calcular desde pedido hasta entrega real
            dias_desde_pedido = (seg.fecha_entrega_real - seg.fecha_pedido).days if isinstance(seg.fecha_pedido, date) else (seg.fecha_entrega_real - seg.fecha_pedido.date()).days
        else:
            # Si no ha llegado, calcular desde pedido hasta hoy
            dias_desde_pedido = (hoy - seg.fecha_pedido).days if isinstance(seg.fecha_pedido, date) else (hoy - seg.fecha_pedido.date()).days
        
        # Calcular días de retraso y días totales de espera
        if seg.fecha_entrega_real:
            # Si ya llegó, calcular retraso respecto a fecha estimada
            dias_retraso = max(0, (seg.fecha_entrega_real - seg.fecha_entrega_estimada).days)
            esta_retrasado = dias_retraso > 0
            # Días totales: mismo que dias_desde_pedido (ya llegó)
            dias_totales_espera = dias_desde_pedido
        else:
            # Si no ha llegado, calcular retraso respecto a hoy
            if hoy > seg.fecha_entrega_estimada:
                dias_retraso = (hoy - seg.fecha_entrega_estimada).days
                esta_retrasado = True
            else:
                dias_retraso = 0
                esta_retrasado = False
            # Días totales: mismo que dias_desde_pedido (hasta hoy)
            dias_totales_espera = dias_desde_pedido
        
        # Calcular días hasta entrega estimada (negativo si ya pasó)
        dias_hasta_entrega = (seg.fecha_entrega_estimada - hoy).days
        
        # Determinar prioridad visual
        if esta_retrasado and dias_retraso > 5:
            prioridad = 'critico'
        elif esta_retrasado:
            prioridad = 'alto'
        elif dias_hasta_entrega <= 3:
            prioridad = 'medio'
        else:
            prioridad = 'normal'
        
        # Obtener lista de piezas vinculadas
        piezas_vinculadas = list(seg.piezas.all().values_list('componente__nombre', flat=True))
        piezas_str = ', '.join(piezas_vinculadas) if piezas_vinculadas else seg.descripcion_piezas
        
        data.append({
            'id': seg.id,
            'orden_numero': orden.numero_orden_interno,
            'orden_id': orden.id,
            'orden_cliente': detalle.orden_cliente,
            'service_tag': detalle.numero_serie,
            'proveedor': seg.proveedor,
            'estado': seg.estado,
            'estado_display': seg.get_estado_display(),
            'fecha_pedido': seg.fecha_pedido,
            'fecha_entrega_estimada': seg.fecha_entrega_estimada,
            'fecha_entrega_real': seg.fecha_entrega_real,
            'dias_desde_pedido': dias_desde_pedido,
            'dias_totales_espera': dias_totales_espera,
            'dias_retraso': dias_retraso,
            'dias_hasta_entrega': dias_hasta_entrega,
            'esta_retrasado': esta_retrasado,
            'prioridad': prioridad,
            'sucursal': orden.sucursal.nombre,
            'sucursal_id': orden.sucursal.id,
            'responsable': orden.responsable_seguimiento.nombre_completo,
            'descripcion_piezas': piezas_str,
            'numero_pedido': seg.numero_pedido,
            'notas': seg.notas_seguimiento,
            'tipo_equipo': detalle.tipo_equipo,
            'marca_equipo': detalle.marca,
        })
    
    df = pd.DataFrame(data)
    
    # Si está vacío, retornar DataFrame vacío con columnas esperadas
    if df.empty:
        return pd.DataFrame(columns=[
            'id', 'orden_numero', 'orden_id', 'orden_cliente', 'service_tag', 'proveedor', 'estado',
            'estado_display', 'fecha_pedido', 'fecha_entrega_estimada', 'fecha_entrega_real',
            'dias_desde_pedido', 'dias_totales_espera', 'dias_retraso', 'dias_hasta_entrega', 'esta_retrasado',
            'prioridad', 'sucursal', 'sucursal_id', 'responsable', 'descripcion_piezas',
            'numero_pedido', 'notas', 'tipo_equipo', 'marca_equipo'
        ])
    
    return df


# ============================================================================
# FUNCIÓN 13: CALCULAR KPIs DE SEGUIMIENTOS DE PIEZAS
# ============================================================================

def calcular_kpis_seguimientos_piezas(df):
    """
    Calcula métricas clave (KPIs) para el dashboard de seguimiento de piezas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Los KPIs (Key Performance Indicators) son números importantes que resumen
    el estado general del negocio. Esta función calcula métricas como:
    - Cuántas piezas están en tránsito
    - Cuántas están retrasadas
    - Promedio de días de entrega
    - etc.
    
    Args:
        df (DataFrame): DataFrame de seguimientos obtenido con obtener_dataframe_seguimientos_piezas()
    
    Returns:
        dict: Diccionario con todos los KPIs calculados
    
    Ejemplo de retorno:
        {
            'total_seguimientos': 45,
            'en_transito': 12,
            'retrasados': 5,
            'promedio_dias_entrega': 7.5,
            'proximos_llegar': 3,
            ...
        }
    """
    from datetime import date
    
    if df.empty:
        return {
            'total_seguimientos': 0,
            'total_activos': 0,
            'en_transito': 0,
            'pedidos': 0,
            'recibidos': 0,
            'retrasados': 0,
            'proximos_llegar': 0,
            'promedio_dias_entrega': 0,
            'promedio_dias_retraso': 0,
            'por_sucursal': {},
            'por_proveedor': {},
            'por_estado': {},
        }
    
    # Filtros para diferentes categorías
    # ACTUALIZADO: Usar constantes globales para estados
    activos = df[df['estado'].isin(ESTADOS_PIEZA_PENDIENTES)]
    retrasados = df[df['esta_retrasado'] == True]
    proximos = df[(df['dias_hasta_entrega'] >= 0) & (df['dias_hasta_entrega'] <= 3) & (df['estado'].isin(ESTADOS_PIEZA_PENDIENTES))]
    recibidos = df[df['estado'].isin(ESTADOS_PIEZA_RECIBIDOS)]  # Incluye recibido, incorrecto, danado
    
    # Calcular promedios
    if not recibidos.empty:
        # Para piezas recibidas, calcular días reales de entrega
        promedio_dias_entrega = recibidos['dias_desde_pedido'].mean()
    else:
        promedio_dias_entrega = 0
    
    if not retrasados.empty:
        promedio_dias_retraso = retrasados['dias_retraso'].mean()
    else:
        promedio_dias_retraso = 0
    
    # Agrupar por sucursal
    por_sucursal = df.groupby('sucursal').agg({
        'id': 'count',
        'esta_retrasado': 'sum'
    }).to_dict('index')
    
    # Agrupar por proveedor
    por_proveedor = df.groupby('proveedor').agg({
        'id': 'count',
        'esta_retrasado': 'sum',
        'dias_desde_pedido': 'mean'
    }).sort_values('id', ascending=False).to_dict('index')
    
    # Agrupar por estado
    por_estado = df['estado'].value_counts().to_dict()
    
    return {
        'total_seguimientos': len(df),
        'total_activos': len(activos),
        'en_transito': len(df[df['estado'] == 'transito']),
        'pedidos': len(df[df['estado'] == 'pedido']),
        'recibidos': len(recibidos),
        'retrasados': len(retrasados),
        'proximos_llegar': len(proximos),
        'promedio_dias_entrega': round(promedio_dias_entrega, 1),
        'promedio_dias_retraso': round(promedio_dias_retraso, 1),
        'por_sucursal': por_sucursal,
        'por_proveedor': por_proveedor,
        'por_estado': por_estado,
    }


# ============================================================================
# FUNCIÓN 14: AGRUPAR SEGUIMIENTOS POR ORDEN
# ============================================================================

def agrupar_seguimientos_por_orden(df):
    """
    Agrupa múltiples seguimientos de piezas por orden, consolidando
    información de proveedores en una sola fila por orden.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Cuando una orden tiene piezas de múltiples proveedores, en lugar de mostrar
    3 filas separadas (una por proveedor), esta función las agrupa en 1 sola fila
    que muestra todos los proveedores juntos.
    
    Ejemplo:
        Antes:
            Orden #123 | Proveedor A | Estado: En tránsito
            Orden #123 | Proveedor B | Estado: Recibido
            Orden #123 | Proveedor C | Estado: Pedido
        
        Después:
            Orden #123 | 3 proveedores | 1 recibida, 2 pendientes | Tiene retrasos
    
    Args:
        df (DataFrame): DataFrame original con seguimientos individuales
    
    Returns:
        list[dict]: Lista de diccionarios con órdenes agrupadas
    
    Estructura de retorno:
        [
            {
                'orden_id': 123,
                'orden_cliente': 'ORD-2024-001',
                'service_tag': 'ABC123',
                'sucursal': 'Matriz',
                'responsable': 'Juan Pérez',
                'total_proveedores': 3,
                'proveedores_activos': [
                    {
                        'id': 1,
                        'proveedor': 'Proveedor A',
                        'estado': 'transito',
                        'estado_display': 'En Tránsito',
                        'descripcion': 'RAM 16GB DDR4',
                        'fecha_pedido': date(2024, 11, 15),
                        'fecha_estimada': date(2024, 11, 25),
                        'dias_desde_pedido': 5,
                        'dias_hasta_entrega': 3,
                        'esta_retrasado': False,
                        'dias_retraso': 0,
                        'numero_pedido': 'TRK-12345'
                    },
                    {...}
                ],
                'total_piezas': 3,
                'piezas_recibidas': 1,
                'piezas_pendientes': 2,
                'tiene_retrasados': True,
                'dias_maximo_retraso': 5,
                'prioridad_maxima': 'alto',
                'estado_general': 'parcial',  # 'todos_recibidos', 'parcial', 'todos_pendientes'
                'fecha_pedido_mas_antigua': date(2024, 11, 10),
                'fecha_entrega_mas_proxima': date(2024, 11, 22),
            }
        ]
    """
    from datetime import date
    
    if df.empty:
        return []
    
    # Agrupar por orden_id
    ordenes_agrupadas = []
    
    for orden_id, grupo in df.groupby('orden_id'):
        # Información general de la orden (igual en todos los seguimientos)
        primer_registro = grupo.iloc[0]
        
        # Construir lista de proveedores con sus detalles
        proveedores_activos = []
        for _, seg in grupo.iterrows():
            proveedores_activos.append({
                'id': seg['id'],
                'proveedor': seg['proveedor'],
                'estado': seg['estado'],
                'estado_display': seg['estado_display'],
                'descripcion': seg['descripcion_piezas'],
                'fecha_pedido': seg['fecha_pedido'],
                'fecha_estimada': seg['fecha_entrega_estimada'],
                'fecha_real': seg.get('fecha_entrega_real'),
                'dias_desde_pedido': seg['dias_desde_pedido'],
                'dias_hasta_entrega': seg['dias_hasta_entrega'],
                'dias_totales_espera': seg.get('dias_totales_espera', 0),
                'esta_retrasado': seg['esta_retrasado'],
                'dias_retraso': seg['dias_retraso'],
                'numero_pedido': seg['numero_pedido'],
                'prioridad': seg['prioridad'],
            })
        
        # Calcular métricas agregadas
        # IMPORTANTE: total_piezas son los seguimientos (1 seguimiento puede tener múltiples piezas del mismo proveedor)
        # pero para el usuario es más claro ver "cuántos pedidos/seguimientos" hay activos
        total_seguimientos = len(proveedores_activos)
        
        # ACTUALIZADO: Usar constantes globales para clasificar estados
        # Estados recibidos incluyen: recibido, incorrecto (WPB), danado (DOA)
        seguimientos_recibidos = len([p for p in proveedores_activos if p['estado'] in ESTADOS_PIEZA_RECIBIDOS])
        seguimientos_pendientes = len([p for p in proveedores_activos if p['estado'] in ESTADOS_PIEZA_PENDIENTES])
        
        # Identificar seguimientos con problemas de calidad (WPB/DOA)
        seguimientos_problematicos = len([p for p in proveedores_activos if p['estado'] in ESTADOS_PIEZA_PROBLEMATICOS])
        
        tiene_retrasados = any(p['esta_retrasado'] for p in proveedores_activos)
        dias_maximo_retraso = max([p['dias_retraso'] for p in proveedores_activos], default=0)
        
        # Determinar estado general
        if seguimientos_recibidos == total_seguimientos:
            estado_general = 'todos_recibidos'
        elif seguimientos_recibidos == 0:
            estado_general = 'todos_pendientes'
        else:
            estado_general = 'parcial'
        
        # Prioridad máxima
        prioridades_orden = ['critico', 'alto', 'medio', 'normal']
        prioridad_maxima = 'normal'
        for prioridad in prioridades_orden:
            if any(p['prioridad'] == prioridad for p in proveedores_activos):
                prioridad_maxima = prioridad
                break
        
        # Fechas relevantes
        fecha_pedido_mas_antigua = min([p['fecha_pedido'] for p in proveedores_activos])
        fechas_proximas = [p['fecha_estimada'] for p in proveedores_activos if p['estado'] in ESTADOS_PIEZA_PENDIENTES]
        fecha_entrega_mas_proxima = min(fechas_proximas) if fechas_proximas else None
        
        # Construir diccionario de orden agrupada
        orden_agrupada = {
            'orden_id': orden_id,
            'orden_numero': primer_registro['orden_numero'],
            'orden_cliente': primer_registro['orden_cliente'],
            'service_tag': primer_registro['service_tag'],
            'sucursal': primer_registro['sucursal'],
            'sucursal_id': primer_registro['sucursal_id'],
            'responsable': primer_registro['responsable'],
            'tipo_equipo': primer_registro['tipo_equipo'],
            'marca_equipo': primer_registro['marca_equipo'],
            
            # Proveedores
            'total_proveedores': total_seguimientos,
            'proveedores_activos': proveedores_activos,
            
            # Métricas (seguimientos, no piezas individuales)
            'total_seguimientos': total_seguimientos,
            'seguimientos_recibidos': seguimientos_recibidos,
            'seguimientos_pendientes': seguimientos_pendientes,
            'seguimientos_problematicos': seguimientos_problematicos,  # NUEVO: WPB/DOA
            'tiene_retrasados': tiene_retrasados,
            'dias_maximo_retraso': dias_maximo_retraso,
            'prioridad_maxima': prioridad_maxima,
            'estado_general': estado_general,
            
            # Fechas
            'fecha_pedido_mas_antigua': fecha_pedido_mas_antigua,
            'fecha_entrega_mas_proxima': fecha_entrega_mas_proxima,
        }
        
        ordenes_agrupadas.append(orden_agrupada)
    
    # Ordenar por prioridad y fecha más próxima
    prioridades_orden = {'critico': 0, 'alto': 1, 'medio': 2, 'normal': 3}
    ordenes_agrupadas.sort(
        key=lambda x: (
            prioridades_orden.get(x['prioridad_maxima'], 3),
            x['fecha_entrega_mas_proxima'] if x['fecha_entrega_mas_proxima'] else date.max
        )
    )
    
    return ordenes_agrupadas


# ============================================================================
# FUNCIÓN: ANÁLISIS DE COMENTARIOS DE RECHAZO (TEXT MINING)
# ============================================================================

def analizar_comentarios_rechazo(df_cotizaciones):
    """
    Realiza análisis de texto sobre los comentarios de rechazo.
    
    Extrae:
    - Palabras más frecuentes
    - Frases comunes (n-gramas)
    - Correlación palabra → resultado
    - Insights automáticos
    
    Args:
        df_cotizaciones: DataFrame con cotizaciones
    
    Returns:
        dict: Diccionario con análisis completo de texto
    """
    import re
    from collections import Counter, defaultdict
    
    # Filtrar solo cotizaciones rechazadas con comentarios
    df_rechazadas = df_cotizaciones[
        (df_cotizaciones['aceptada'] == False) & 
        (df_cotizaciones['detalle_rechazo'].notna()) &
        (df_cotizaciones['detalle_rechazo'] != '')
    ].copy()
    
    if df_rechazadas.empty:
        return {
            'total_comentarios': 0,
            'palabras_clave': [],
            'frases_comunes': [],
            'correlaciones': [],
            'insights': [],
            'tiene_datos': False
        }
    
    # Combinar todos los comentarios
    todos_comentarios = ' '.join(df_rechazadas['detalle_rechazo'].astype(str).tolist())
    
    # Limpiar texto
    texto_limpio = todos_comentarios.lower()
    texto_limpio = re.sub(r'[^\w\sáéíóúñü]', ' ', texto_limpio)
    
    # Palabras a ignorar (stopwords en español + contexto servicio técnico)
    stopwords = {
        # Stopwords básicas en español
        'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'haber',
        'por', 'con', 'su', 'para', 'como', 'estar', 'tener', 'le', 'lo', 'todo',
        'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
        'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'él', 'muy', 'sin',
        'vez', 'mucho', 'saber', 'qué', 'sobre', 'mi', 'alguno', 'mismo', 'yo',
        'también', 'hasta', 'año', 'dos', 'querer', 'entre', 'así', 'primero',
        'desde', 'grande', 'eso', 'ni', 'nos', 'llegar', 'pasar', 'tiempo', 'ella',
        'sí', 'día', 'uno', 'bien', 'poco', 'deber', 'entonces', 'poner', 'cosa',
        'tanto', 'hombre', 'parecer', 'nuestro', 'tan', 'donde', 'ahora', 'parte',
        'después', 'vida', 'quedar', 'siempre', 'creer', 'hablar', 'llevar', 'dejar',
        'nada', 'cada', 'seguir', 'menos', 'nuevo', 'encontrar', 'algo', 'solo',
        'decir', 'salir', 'volver', 'tomar', 'conocer', 'vivir', 'sentir', 'tratar',
        'mirar', 'contar', 'empezar', 'esperar', 'buscar', 'existir', 'entrar',
        'trabajar', 'escribir', 'perder', 'producir', 'ocurrir', 'entender', 'pedir',
        'recibir', 'recordar', 'terminar', 'permitir', 'aparecer', 'conseguir',
        'comenzar', 'servir', 'sacar', 'necesitar', 'mantener', 'resultar', 'leer',
        'caer', 'cambiar', 'presentar', 'crear', 'abrir', 'considerar', 'oír',
        'acabar', 'mil', 'nadie', 'realizar', 'suponer', 'comprender', 'lograr',
        
        # Stopwords específicas del contexto de servicio técnico
        # (palabras genéricas que aparecen en todos los comentarios pero no añaden valor)
        'usuario', 'usuarios', 'cliente', 'clientes', 'equipo', 'equipos',
        'cotizacion', 'cotizaciones', 'servicio', 'servicios', 'tecnico', 'tecnicos',
        'reparacion', 'reparaciones', 'pieza', 'piezas', 'repuesto', 'repuestos',
        'acepta', 'aceptar', 'acepto', 'aceptado', 'aceptara', 'aceptacion',
        'rechaza', 'rechazar', 'rechazo', 'rechazado', 'rechazara',
        'disponible', 'disponibles', 'disponibilidad',
        'motivo', 'motivos', 'razon', 'razones', 'causa', 'causas',
        'nivel', 'componente', 'componentes',
        'correo', 'correos', 'email', 'telefono', 'llamada', 'whatsapp',
        'recoleccion', 'entrega', 'retiro', 'retira', 'retiro', 'retirara',
        'ante', 'contra', 'mediante', 'hacia', 'bajo', 'sobre',
        'dice', 'dijo', 'indica', 'informo', 'comento', 'comenta', 'menciono', 'menciona',
        'informa', 'notifica', 'confirma', 'confirmado', 'reporta', 'reporto',
        'solicita', 'solicito', 'requiere', 'requirio', 'pregunta', 'pregunto',
        'realizara', 'realizar', 'realizo', 'hace', 'hizo', 'hara', 'hecho',
        'toma', 'tomo', 'tomara', 'tomado', 'pone', 'puso', 'pondra', 'puesto',
        'alista', 'alisto', 'alistara', 'alistado',
        'tiene', 'tuvo', 'tengo', 'tendra', 'habia', 'hubo', 'habra',
        'sera', 'seria', 'fue', 'fueron', 'seran', 'esta', 'estuvo', 'estara',
        'puede', 'pudo', 'podra', 'podria', 'debe', 'debio', 'debera', 'deberia',
        'quiere', 'quiso', 'querra', 'querria', 'sabe', 'supo', 'sabra',
        'llama', 'llamo', 'llamara', 'avisa', 'aviso', 'avisara',
        'atencion', 'favor', 'gracias', 'saludos', 'nota', 'observacion',
        'todos', 'todas', 'todo', 'toda', 'algunos', 'algunas', 'varios', 'varias',
        'mas', 'menos', 'mucho', 'mucha', 'muchos', 'muchas', 'poco', 'poca', 'pocos', 'pocas',
        'ahi', 'alla', 'aqui', 'alla', 'dentro', 'fuera', 'cerca', 'lejos',
        'antes', 'despues', 'durante', 'mientras', 'luego', 'pronto', 'tarde', 'temprano',
        'siempre', 'nunca', 'jamas', 'todavia', 'aun', 'recien',
        'tambien', 'tampoco', 'incluso', 'ademas', 'aparte', 'excepto', 'salvo',
        'segun', 'mediante', 'conforme', 'acerca', 'respecto', 'referente'
    }
    
    # Extraer palabras individuales
    palabras = [p for p in texto_limpio.split() if len(p) > 3 and p not in stopwords]
    contador_palabras = Counter(palabras)
    
    # Top 15 palabras más frecuentes
    palabras_clave = [
        {'palabra': palabra, 'frecuencia': freq}
        for palabra, freq in contador_palabras.most_common(15)
    ]
    
    # Extraer bigramas (frases de 2 palabras)
    palabras_lista = texto_limpio.split()
    bigramas = []
    for i in range(len(palabras_lista) - 1):
        palabra1 = palabras_lista[i]
        palabra2 = palabras_lista[i + 1]
        if (len(palabra1) > 3 and len(palabra2) > 3 and 
            palabra1 not in stopwords and palabra2 not in stopwords):
            bigramas.append(f"{palabra1} {palabra2}")
    
    contador_bigramas = Counter(bigramas)
    frases_comunes = [
        {'frase': frase, 'frecuencia': freq}
        for frase, freq in contador_bigramas.most_common(10)
    ]
    
    # Calcular correlación palabra → resultado
    # Para cada palabra clave, ver tasa de rechazo cuando aparece
    correlaciones = []
    
    for palabra_data in palabras_clave[:10]:  # Top 10 palabras
        palabra = palabra_data['palabra']
        
        # Cotizaciones que mencionan esta palabra
        menciona_palabra = df_cotizaciones[
            df_cotizaciones['detalle_rechazo'].str.contains(
                palabra, case=False, na=False
            )
        ]
        
        if len(menciona_palabra) > 0:
            rechazos_con_palabra = menciona_palabra[menciona_palabra['aceptada'] == False]
            tasa_rechazo = (len(rechazos_con_palabra) / len(menciona_palabra)) * 100
            
            correlaciones.append({
                'palabra': palabra,
                'menciones': len(menciona_palabra),
                'tasa_rechazo': tasa_rechazo,
                'tasa_aceptacion': 100 - tasa_rechazo
            })
    
    # Ordenar por tasa de rechazo
    correlaciones.sort(key=lambda x: x['tasa_rechazo'], reverse=True)
    
    # Generar insights automáticos
    insights = []
    
    # Insight 1: Palabra más peligrosa
    if correlaciones:
        palabra_peligrosa = correlaciones[0]
        if palabra_peligrosa['tasa_rechazo'] > 70:
            insights.append({
                'tipo': 'alerta',
                'icono': '🔴',
                'titulo': f'Alerta: "{palabra_peligrosa["palabra"].title()}"',
                'mensaje': f'La palabra "{palabra_peligrosa["palabra"]}" aparece en {palabra_peligrosa["menciones"]} cotizaciones y está asociada con {palabra_peligrosa["tasa_rechazo"]:.0f}% de rechazos.',
                'accion': f'Cuando el cliente mencione "{palabra_peligrosa["palabra"]}", actúa proactivamente para mitigar el riesgo.'
            })
    
    # Insight 2: Palabra más segura
    palabras_seguras = [p for p in correlaciones if p['tasa_aceptacion'] > 60]
    if palabras_seguras:
        palabra_segura = palabras_seguras[0]
        insights.append({
            'tipo': 'positivo',
            'icono': '🟢',
            'titulo': f'Oportunidad: "{palabra_segura["palabra"].title()}"',
            'mensaje': f'Cuando los clientes mencionan "{palabra_segura["palabra"]}", hay {palabra_segura["tasa_aceptacion"]:.0f}% de probabilidad de aceptación.',
            'accion': f'Enfatiza aspectos relacionados con "{palabra_segura["palabra"]}" en tus cotizaciones.'
        })
    
    # Insight 3: Frase más común
    if frases_comunes:
        frase_top = frases_comunes[0]
        insights.append({
            'tipo': 'info',
            'icono': '💬',
            'titulo': 'Frase Más Mencionada',
            'mensaje': f'La frase "{frase_top["frase"]}" aparece {frase_top["frecuencia"]} veces en los rechazos.',
            'accion': 'Analiza el contexto de esta frase para identificar patrones de insatisfacción.'
        })
    
    # Insight 4: Volumen de feedback
    total_palabras = sum(contador_palabras.values())
    promedio_palabras = total_palabras / len(df_rechazadas) if len(df_rechazadas) > 0 else 0
    
    if promedio_palabras > 20:
        insights.append({
            'tipo': 'info',
            'icono': '📝',
            'titulo': 'Feedback Detallado',
            'mensaje': f'Los clientes escriben en promedio {promedio_palabras:.0f} palabras al rechazar.',
            'accion': 'Alto nivel de detalle indica que los clientes están evaluando cuidadosamente. Aprovecha este feedback.'
        })
    elif promedio_palabras < 5:
        insights.append({
            'tipo': 'advertencia',
            'icono': '⚠️',
            'titulo': 'Feedback Limitado',
            'mensaje': f'Los comentarios de rechazo son muy breves (promedio: {promedio_palabras:.0f} palabras).',
            'accion': 'Considera solicitar más detalles al cliente para mejorar futuras cotizaciones.'
        })
    
    return {
        'total_comentarios': len(df_rechazadas),
        'total_palabras_unicas': len(contador_palabras),
        'promedio_palabras_por_comentario': promedio_palabras,
        'palabras_clave': palabras_clave,
        'frases_comunes': frases_comunes,
        'correlaciones': correlaciones,
        'insights': insights,
        'tiene_datos': True
    }


def analizar_diagnosticos_tecnicos(df_ordenes):
    """
    Realiza análisis de texto sobre los diagnósticos técnicos realizados por cada técnico.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    ================================
    Esta función analiza los diagnósticos escritos por los técnicos para identificar:
    - Nivel de detalle en sus diagnósticos (cuántas palabras escriben)
    - Terminología técnica vs lenguaje coloquial
    - Fallas más diagnosticadas por cada técnico
    - Comparación entre técnicos (quién es más detallado, técnico, etc.)
    - Áreas de mejora en la calidad de los diagnósticos
    
    Args:
        df_ordenes: DataFrame con órdenes de servicio (debe incluir columnas:
                   'tecnico_nombre', 'diagnostico_sic', 'falla_principal')
    
    Returns:
        dict: Diccionario con análisis completo por técnico con la estructura:
            - tiene_datos: bool (si hay datos suficientes para analizar)
            - total_diagnosticos: int (cantidad total de diagnósticos analizados)
            - total_tecnicos: int (cantidad de técnicos únicos)
            - analisis_por_tecnico: list (análisis individual de cada técnico)
            - ranking_detalle: list (técnicos ordenados por nivel de detalle)
            - ranking_tecnicidad: list (técnicos ordenados por uso de términos técnicos)
            - comparativa: dict (métricas comparativas entre técnicos)
            - insights: list (recomendaciones automáticas)
            - palabras_tecnicas_globales: list (términos técnicos más usados)
    """
    import re
    from collections import Counter, defaultdict
    
    # Filtrar solo órdenes con diagnóstico técnico completado
    df_con_diagnostico = df_ordenes[
        (df_ordenes['diagnostico_sic'].notna()) & 
        (df_ordenes['diagnostico_sic'] != '') &
        (df_ordenes['tecnico_nombre'].notna())
    ].copy()
    
    if df_con_diagnostico.empty or len(df_con_diagnostico) < 5:
        return {
            'tiene_datos': False,
            'total_diagnosticos': len(df_con_diagnostico),
            'mensaje': 'No hay suficientes diagnósticos técnicos para análisis (mínimo 5 requeridos)'
        }
    
    # ========================================
    # DICCIONARIO DE TERMINOLOGÍA TÉCNICA
    # ========================================
    # Palabras que indican conocimiento técnico especializado
    terminologia_tecnica = {
        # Componentes de hardware
        'placa', 'motherboard', 'tarjeta', 'procesador', 'cpu', 'gpu', 'ram', 'memoria',
        'disco', 'ssd', 'hdd', 'fuente', 'power', 'bateria', 'pantalla', 'display',
        'teclado', 'touchpad', 'trackpad', 'bisagra', 'hinge', 'conector', 'puerto',
        'usb', 'hdmi', 'vga', 'ethernet', 'wifi', 'bluetooth', 'webcam', 'camara',
        'ventilador', 'cooler', 'disipador', 'heatsink', 'flex', 'cable', 'ribbon',
        
        # Componentes electrónicos especializados
        'capacitor', 'condensador', 'resistencia', 'transistor', 'mosfet', 'diodo',
        'bobina', 'inductor', 'chip', 'ic', 'bga', 'smd', 'circuito', 'pcb',
        'soldadura', 'reballing', 'reflow', 'flux', 'estano', 'pasta', 'termica',
        
        # Diagnósticos técnicos
        'cortocircuito', 'corto', 'sobrecalentamiento', 'temperatura', 'voltaje',
        'amperaje', 'continuidad', 'medicion', 'multimetro', 'osciloscopio',
        'resistencia', 'capacitancia', 'inductancia', 'señal', 'clock', 'bus',
        'reset', 'power', 'enable', 'standby', 'suspend', 'boot', 'post',
        
        # Software y firmware
        'bios', 'uefi', 'firmware', 'driver', 'controlador', 'sistema', 'operativo',
        'windows', 'linux', 'macos', 'android', 'ios', 'arranque', 'booteo',
        'particion', 'formato', 'instalacion', 'actualizacion', 'recovery',
        
        # Fallas comunes técnicas
        'oxidacion', 'humedad', 'golpe', 'caida', 'impacto', 'derrame', 'liquido',
        'polvo', 'suciedad', 'desgaste', 'fisura', 'fractura', 'rotura',
        'desconexion', 'falso', 'contacto', 'intermitente', 'intermitencia',
        
        # Procesos técnicos
        'diagnostico', 'inspeccion', 'revision', 'prueba', 'testeo', 'verificacion',
        'medicion', 'analisis', 'evaluacion', 'limpieza', 'mantenimiento',
        'reparacion', 'reemplazo', 'sustitucion', 'instalacion', 'configuracion',
        
        # Herramientas y equipos
        'multimetro', 'tester', 'osciloscopio', 'estacion', 'soldadura', 'cautín',
        'desarmador', 'destornillador', 'pinzas', 'lupa', 'microscopio',
        'pistola', 'calor', 'aire', 'compresor', 'pasta', 'termica', 'alcohol',
        'isopropilico', 'flux', 'malha', 'BGA',
        
        # Términos de calidad/precisión
        'exacto', 'preciso', 'especifico', 'detallado', 'completo', 'exhaustivo',
        'minucioso', 'cuidadoso', 'correcto', 'adecuado', 'apropiado', 'optimo',
    }
    
    # Palabras genéricas que NO indican conocimiento técnico (lenguaje coloquial)
    palabras_genericas = {
        'no', 'si', 'funciona', 'sirve', 'esta', 'esta', 'tiene', 'tengo', 'hay',
        'puede', 'debe', 'quiere', 'necesita', 'requiere', 'hace', 'dice', 'da',
        'sale', 'aparece', 'muestra', 'indica', 'marca', 'presenta', 'esta',
        'bien', 'mal', 'bueno', 'malo', 'regular', 'excelente', 'pesimo',
        'cosa', 'parte', 'pedazo', 'trozo', 'pieza', 'componente', 'elemento',
        'problema', 'falla', 'error', 'daño', 'averia', 'desperfecto', 'defecto',
        'cliente', 'usuario', 'persona', 'dueño', 'propietario', 'equipo',
        'computadora', 'laptop', 'notebook', 'pc', 'desktop', 'maquina',
        'algo', 'nada', 'todo', 'poco', 'mucho', 'bastante', 'demasiado',
        'despues', 'antes', 'ahora', 'luego', 'pronto', 'tarde', 'temprano',
        'cuando', 'donde', 'como', 'porque', 'para', 'desde', 'hasta', 'segun',
    }
    
    # Stopwords completas (incluyen las básicas del español)
    stopwords = {
        'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'ser', 'se', 'no', 'haber',
        'por', 'con', 'su', 'para', 'como', 'estar', 'tener', 'le', 'lo', 'todo',
        'pero', 'más', 'hacer', 'o', 'poder', 'decir', 'este', 'ir', 'otro', 'ese',
        'la', 'si', 'me', 'ya', 'ver', 'porque', 'dar', 'cuando', 'él', 'muy', 'sin',
        'vez', 'mucho', 'saber', 'qué', 'sobre', 'mi', 'alguno', 'mismo', 'yo',
        'también', 'hasta', 'año', 'dos', 'querer', 'entre', 'así', 'primero',
        'desde', 'grande', 'eso', 'ni', 'nos', 'llegar', 'pasar', 'tiempo', 'ella',
        'sí', 'día', 'uno', 'bien', 'poco', 'deber', 'entonces', 'poner', 'cosa',
        'tanto', 'hombre', 'parecer', 'nuestro', 'tan', 'donde', 'ahora', 'parte',
        'después', 'vida', 'quedar', 'siempre', 'creer', 'hablar', 'llevar', 'dejar',
        'nada', 'cada', 'seguir', 'menos', 'nuevo', 'encontrar', 'algo', 'solo',
        'los', 'las', 'del', 'una', 'unos', 'unas', 'al', 'del', 'esto', 'esta',
        'estos', 'estas', 'ese', 'esa', 'esos', 'esas', 'aquel', 'aquella',
        'aquellos', 'aquellas', 'quien', 'cual', 'cuales', 'cuanto', 'cuanta',
        'cuantos', 'cuantas', 'fue', 'han', 'has', 'sido', 'son', 'soy', 'eres',
        'somos', 'sois', 'era', 'eras', 'eramos', 'erais', 'eran', 'fui', 'fuiste',
        'fue', 'fuimos', 'fuisteis', 'fueron', 'sea', 'seas', 'seamos', 'seais',
        'sean', 'seria', 'serias', 'seriamos', 'seriais', 'serian',
    }
    
    # ========================================
    # ANÁLISIS POR TÉCNICO
    # ========================================
    
    analisis_por_tecnico = []
    tecnicos_unicos = df_con_diagnostico['tecnico_nombre'].unique()
    
    for tecnico in tecnicos_unicos:
        # Filtrar diagnósticos de este técnico
        diagnosticos_tecnico = df_con_diagnostico[
            df_con_diagnostico['tecnico_nombre'] == tecnico
        ]
        
        # Combinar todos los diagnósticos del técnico
        texto_completo = ' '.join(diagnosticos_tecnico['diagnostico_sic'].astype(str).tolist())
        
        # Limpiar texto
        texto_limpio = texto_completo.lower()
        texto_limpio = re.sub(r'[^\w\sáéíóúñü]', ' ', texto_limpio)
        
        # Extraer todas las palabras (sin filtrar stopwords aún)
        todas_palabras = texto_limpio.split()
        total_palabras = len(todas_palabras)
        
        # Filtrar palabras válidas (más de 3 caracteres, no stopwords)
        palabras_validas = [
            p for p in todas_palabras 
            if len(p) > 3 and p not in stopwords
        ]
        
        # Contar palabras técnicas usadas
        palabras_tecnicas_usadas = [
            p for p in palabras_validas 
            if p in terminologia_tecnica
        ]
        contador_tecnicas = Counter(palabras_tecnicas_usadas)
        
        # Contar palabras genéricas
        palabras_genericas_usadas = [
            p for p in palabras_validas 
            if p in palabras_genericas
        ]
        
        # Calcular métricas
        num_diagnosticos = len(diagnosticos_tecnico)
        promedio_palabras = total_palabras / num_diagnosticos if num_diagnosticos > 0 else 0
        
        # Índice de tecnicidad: % de palabras técnicas sobre palabras válidas
        if len(palabras_validas) > 0:
            indice_tecnicidad = (len(palabras_tecnicas_usadas) / len(palabras_validas)) * 100
        else:
            indice_tecnicidad = 0
        
        # Top 5 palabras técnicas más usadas por este técnico
        top_tecnicas = [
            {'palabra': palabra, 'frecuencia': freq}
            for palabra, freq in contador_tecnicas.most_common(5)
        ]
        
        # Análisis de fallas diagnosticadas (si existe la columna)
        fallas_principales = []
        if 'falla_principal' in diagnosticos_tecnico.columns:
            fallas_texto = ' '.join(diagnosticos_tecnico['falla_principal'].dropna().astype(str).tolist())
            fallas_texto_limpio = fallas_texto.lower()
            fallas_palabras = [
                p for p in fallas_texto_limpio.split() 
                if len(p) > 4 and p not in stopwords
            ]
            fallas_counter = Counter(fallas_palabras)
            fallas_principales = [
                {'falla': falla, 'frecuencia': freq}
                for falla, freq in fallas_counter.most_common(3)
            ]
        
        # Clasificación del técnico
        if indice_tecnicidad >= 15:
            clasificacion = 'Muy Técnico'
            color = 'success'
        elif indice_tecnicidad >= 8:
            clasificacion = 'Técnico'
            color = 'primary'
        elif indice_tecnicidad >= 4:
            clasificacion = 'Moderado'
            color = 'warning'
        else:
            clasificacion = 'Básico'
            color = 'danger'
        
        # Clasificación de detalle
        if promedio_palabras >= 50:
            nivel_detalle = 'Muy Detallado'
            color_detalle = 'success'
        elif promedio_palabras >= 30:
            nivel_detalle = 'Detallado'
            color_detalle = 'primary'
        elif promedio_palabras >= 15:
            nivel_detalle = 'Moderado'
            color_detalle = 'warning'
        else:
            nivel_detalle = 'Básico'
            color_detalle = 'danger'
        
        analisis_por_tecnico.append({
            'tecnico': tecnico,
            'num_diagnosticos': num_diagnosticos,
            'total_palabras': total_palabras,
            'promedio_palabras': promedio_palabras,
            'palabras_unicas': len(set(palabras_validas)),
            'palabras_tecnicas_count': len(palabras_tecnicas_usadas),
            'palabras_genericas_count': len(palabras_genericas_usadas),
            'indice_tecnicidad': indice_tecnicidad,
            'clasificacion': clasificacion,
            'color_clasificacion': color,
            'nivel_detalle': nivel_detalle,
            'color_detalle': color_detalle,
            'top_palabras_tecnicas': top_tecnicas,
            'fallas_principales': fallas_principales,
        })
    
    # ========================================
    # RANKINGS Y COMPARATIVAS
    # ========================================
    
    # Ranking por nivel de detalle (promedio de palabras)
    ranking_detalle = sorted(
        analisis_por_tecnico, 
        key=lambda x: x['promedio_palabras'], 
        reverse=True
    )
    
    # Ranking por tecnicidad (uso de terminología técnica)
    ranking_tecnicidad = sorted(
        analisis_por_tecnico, 
        key=lambda x: x['indice_tecnicidad'], 
        reverse=True
    )
    
    # Métricas comparativas globales
    promedios_globales = {
        'promedio_palabras': sum(t['promedio_palabras'] for t in analisis_por_tecnico) / len(analisis_por_tecnico),
        'promedio_tecnicidad': sum(t['indice_tecnicidad'] for t in analisis_por_tecnico) / len(analisis_por_tecnico),
        'promedio_diagnosticos': sum(t['num_diagnosticos'] for t in analisis_por_tecnico) / len(analisis_por_tecnico),
    }
    
    # ========================================
    # ANÁLISIS DE PALABRAS TÉCNICAS GLOBALES
    # ========================================
    
    # Combinar todos los diagnósticos
    todos_diagnosticos_texto = ' '.join(df_con_diagnostico['diagnostico_sic'].astype(str).tolist())
    texto_global_limpio = todos_diagnosticos_texto.lower()
    texto_global_limpio = re.sub(r'[^\w\sáéíóúñü]', ' ', texto_global_limpio)
    
    palabras_globales = [
        p for p in texto_global_limpio.split() 
        if len(p) > 3 and p not in stopwords and p in terminologia_tecnica
    ]
    contador_global = Counter(palabras_globales)
    
    palabras_tecnicas_globales = [
        {'palabra': palabra, 'frecuencia': freq}
        for palabra, freq in contador_global.most_common(15)
    ]
    
    # ========================================
    # INSIGHTS AUTOMÁTICOS
    # ========================================
    
    insights = []
    
    # Insight 1: Técnico más detallado
    if ranking_detalle:
        mejor_detalle = ranking_detalle[0]
        if mejor_detalle['promedio_palabras'] >= 40:
            insights.append({
                'tipo': 'excelente',
                'icono': '🏆',
                'titulo': f'Mejor Detalle: {mejor_detalle["tecnico"]}',
                'mensaje': f'Escribe diagnósticos muy completos con un promedio de {mejor_detalle["promedio_palabras"]:.0f} palabras.',
                'accion': 'Considerarlo como referencia para capacitación de otros técnicos.',
                'color': 'success'
            })
        
        # Técnico menos detallado
        peor_detalle = ranking_detalle[-1]
        if peor_detalle['promedio_palabras'] < 15:
            insights.append({
                'tipo': 'mejora',
                'icono': '⚠️',
                'titulo': f'Necesita Mejorar: {peor_detalle["tecnico"]}',
                'mensaje': f'Diagnósticos muy breves ({peor_detalle["promedio_palabras"]:.0f} palabras promedio). Falta detalle técnico.',
                'accion': 'Capacitar en redacción de diagnósticos más completos y específicos.',
                'color': 'warning'
            })
    
    # Insight 2: Técnico más técnico
    if ranking_tecnicidad:
        mejor_tecnicidad = ranking_tecnicidad[0]
        if mejor_tecnicidad['indice_tecnicidad'] >= 12:
            insights.append({
                'tipo': 'excelente',
                'icono': '🔬',
                'titulo': f'Más Técnico: {mejor_tecnicidad["tecnico"]}',
                'mensaje': f'Usa terminología técnica especializada en {mejor_tecnicidad["indice_tecnicidad"]:.1f}% de sus diagnósticos.',
                'accion': 'Lenguaje profesional y técnico excelente. Modelo a seguir.',
                'color': 'success'
            })
        
        # Técnico menos técnico
        peor_tecnicidad = ranking_tecnicidad[-1]
        if peor_tecnicidad['indice_tecnicidad'] < 5:
            insights.append({
                'tipo': 'mejora',
                'icono': '📚',
                'titulo': f'Mejorar Tecnicidad: {peor_tecnicidad["tecnico"]}',
                'mensaje': f'Bajo uso de terminología técnica ({peor_tecnicidad["indice_tecnicidad"]:.1f}%). Lenguaje muy coloquial.',
                'accion': 'Capacitar en terminología técnica especializada y estándares de la industria.',
                'color': 'danger'
            })
    
    # Insight 3: Consistencia del equipo
    variabilidad_detalle = max(t['promedio_palabras'] for t in analisis_por_tecnico) - min(t['promedio_palabras'] for t in analisis_por_tecnico)
    if variabilidad_detalle > 30:
        insights.append({
            'tipo': 'info',
            'icono': '📊',
            'titulo': 'Alta Variabilidad entre Técnicos',
            'mensaje': f'Diferencia de {variabilidad_detalle:.0f} palabras entre el técnico más y menos detallado.',
            'accion': 'Estandarizar procesos de diagnóstico. Crear plantilla o guía de diagnósticos.',
            'color': 'info'
        })
    
    # Insight 4: Palabras técnicas globales
    if palabras_tecnicas_globales:
        top_palabra = palabras_tecnicas_globales[0]
        insights.append({
            'tipo': 'info',
            'icono': '🔧',
            'titulo': f'Término Más Usado: "{top_palabra["palabra"].title()}"',
            'mensaje': f'Aparece {top_palabra["frecuencia"]} veces en los diagnósticos. Es el componente más frecuentemente diagnosticado.',
            'accion': 'Considerar capacitación especializada o stock de repuestos para este componente.',
            'color': 'primary'
        })
    
    # Insight 5: Calidad general del equipo
    tecnicos_excelentes = sum(1 for t in analisis_por_tecnico if t['indice_tecnicidad'] >= 10)
    porcentaje_excelentes = (tecnicos_excelentes / len(analisis_por_tecnico)) * 100
    
    if porcentaje_excelentes >= 70:
        insights.append({
            'tipo': 'excelente',
            'icono': '✅',
            'titulo': 'Equipo de Alta Calidad',
            'mensaje': f'{porcentaje_excelentes:.0f}% de los técnicos tienen nivel técnico alto o excelente.',
            'accion': 'Mantener estándares y continuar capacitación técnica.',
            'color': 'success'
        })
    elif porcentaje_excelentes < 30:
        insights.append({
            'tipo': 'alerta',
            'icono': '🚨',
            'titulo': 'Necesidad de Capacitación',
            'mensaje': f'Solo {porcentaje_excelentes:.0f}% del equipo tiene nivel técnico alto. Mayoría usa lenguaje básico.',
            'accion': 'Implementar programa urgente de capacitación técnica y estandarización.',
            'color': 'danger'
        })
    
    return {
        'tiene_datos': True,
        'total_diagnosticos': len(df_con_diagnostico),
        'total_tecnicos': len(tecnicos_unicos),
        'analisis_por_tecnico': analisis_por_tecnico,
        'ranking_detalle': ranking_detalle,
        'ranking_tecnicidad': ranking_tecnicidad,
        'promedios_globales': promedios_globales,
        'palabras_tecnicas_globales': palabras_tecnicas_globales,
        'insights': insights,
    }
