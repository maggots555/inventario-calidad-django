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
from datetime import datetime, timedelta
from .models import (
    Cotizacion, 
    PiezaCotizada, 
    SeguimientoPieza,
    OrdenServicio,
    DetalleEquipo
)
from inventario.models import Empleado, Sucursal


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
            fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        cotizaciones = cotizaciones.filter(fecha_envio__date__gte=fecha_inicio)
    
    if fecha_fin:
        if isinstance(fecha_fin, str):
            fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
        cotizaciones = cotizaciones.filter(fecha_envio__date__lte=fecha_fin)
    
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
