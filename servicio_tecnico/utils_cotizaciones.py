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
    Analiza el impacto de proveedores en la conversión de ventas.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función cruza datos de proveedores (tiempos, costos) con resultados
    de negocio (aceptación de cotizaciones, ingresos generados).
    
    ¿Por qué es importante?
    - No todos los proveedores contribuyen igual a las ventas
    - Un proveedor rápido pero caro puede tener baja conversión
    - Un proveedor barato pero lento puede perder ventas por demora
    
    Args:
        cotizacion_ids (list): Lista de IDs de cotizaciones a analizar (opcional)
    
    Returns:
        DataFrame: DataFrame con métricas de impacto por proveedor
        
    Columnas retornadas:
        - proveedor: Nombre del proveedor
        - total_pedidos: Total de pedidos realizados
        - total_cotizaciones: Cotizaciones que usaron piezas de este proveedor
        - cotizaciones_aceptadas: Cuántas cotizaciones fueron aceptadas
        - cotizaciones_rechazadas: Cuántas fueron rechazadas
        - tasa_aceptacion: % de aceptación
        - tiempo_entrega_promedio: Días promedio de entrega
        - valor_cotizado_total: Valor total cotizado con piezas de este proveedor
        - valor_generado: Ingresos reales (solo cotizaciones aceptadas)
    """
    from servicio_tecnico.models import SeguimientoPieza, Cotizacion
    
    # QuerySet base
    seguimientos = SeguimientoPieza.objects.select_related(
        'cotizacion',
        'cotizacion__orden'
    ).prefetch_related('piezas')
    
    # Filtrar por cotizaciones específicas si se proporcionan
    if cotizacion_ids:
        seguimientos = seguimientos.filter(cotizacion_id__in=cotizacion_ids)
    
    # Convertir a lista para procesamiento
    data = []
    
    for seg in seguimientos:
        cotizacion = seg.cotizacion
        
        # Calcular tiempo de entrega real (solo si se recibió)
        tiempo_entrega = None
        if seg.fecha_entrega_real:
            tiempo_entrega = (seg.fecha_entrega_real - seg.fecha_pedido).days
        
        data.append({
            'seguimiento_id': seg.id,
            'proveedor': seg.proveedor,
            'cotizacion_id': cotizacion.pk,  # pk es igual a orden_id
            'cotizacion_aceptada': cotizacion.usuario_acepto if cotizacion.usuario_acepto is not None else None,
            'costo_total_cotizacion': float(cotizacion.costo_total) if cotizacion.costo_total else 0,
            'costo_final_cotizacion': float(cotizacion.costo_total_final) if cotizacion.usuario_acepto else 0,
            'tiempo_entrega_dias': tiempo_entrega,
            'estado_seguimiento': seg.estado,
            'fecha_pedido': seg.fecha_pedido,
        })
    
    df = pd.DataFrame(data)
    
    if df.empty:
        return pd.DataFrame(columns=[
            'proveedor', 'total_pedidos', 'total_cotizaciones',
            'cotizaciones_aceptadas', 'cotizaciones_rechazadas',
            'tasa_aceptacion', 'tiempo_entrega_promedio',
            'valor_cotizado_total', 'valor_generado'
        ])
    
    # Agrupar por proveedor y calcular métricas
    metricas = []
    
    for proveedor in df['proveedor'].unique():
        df_prov = df[df['proveedor'] == proveedor]
        
        # Métricas básicas
        total_pedidos = len(df_prov)
        cotizaciones_unicas = df_prov['cotizacion_id'].nunique()
        
        # Filtrar solo cotizaciones con respuesta
        df_con_respuesta = df_prov[df_prov['cotizacion_aceptada'].notna()]
        
        if len(df_con_respuesta) > 0:
            aceptadas = (df_con_respuesta['cotizacion_aceptada'] == True).sum()
            rechazadas = (df_con_respuesta['cotizacion_aceptada'] == False).sum()
            tasa_aceptacion = (aceptadas / len(df_con_respuesta) * 100) if len(df_con_respuesta) > 0 else 0
        else:
            aceptadas = 0
            rechazadas = 0
            tasa_aceptacion = 0
        
        # Tiempo de entrega (solo pedidos entregados)
        tiempos = df_prov['tiempo_entrega_dias'].dropna()
        tiempo_promedio = tiempos.mean() if len(tiempos) > 0 else None
        
        # Valores monetarios
        valor_cotizado = df_prov['costo_total_cotizacion'].sum()
        valor_generado = df_prov[df_prov['cotizacion_aceptada'] == True]['costo_final_cotizacion'].sum()
        
        metricas.append({
            'proveedor': proveedor,
            'total_pedidos': total_pedidos,
            'total_cotizaciones': cotizaciones_unicas,
            'cotizaciones_aceptadas': aceptadas,
            'cotizaciones_rechazadas': rechazadas,
            'tasa_aceptacion': round(tasa_aceptacion, 1),
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
    Analiza qué componentes suministra cada proveedor y su resultado.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función crea una vista detallada de qué tipo de piezas (RAM, disco,
    pantalla, etc.) suministra cada proveedor y qué tan exitosas son.
    
    ¿Para qué sirve?
    - Identificar especialización de proveedores
    - Detectar proveedores con buena calidad en ciertos componentes
    - Diversificar riesgos (no depender de un solo proveedor)
    - Negociar mejores precios en componentes donde tienen volumen
    
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
    from servicio_tecnico.models import SeguimientoPieza, PiezaCotizada
    
    # QuerySet base
    seguimientos = SeguimientoPieza.objects.select_related(
        'cotizacion'
    ).prefetch_related(
        'piezas__componente',
        'piezas__cotizacion'
    )
    
    # Filtrar por cotizaciones específicas si se proporcionan
    if cotizacion_ids:
        seguimientos = seguimientos.filter(cotizacion_id__in=cotizacion_ids)
    
    # Convertir a lista para procesamiento
    data = []
    
    for seg in seguimientos:
        proveedor = seg.proveedor
        
        # Obtener piezas asociadas a este seguimiento
        piezas = seg.piezas.all()
        
        if piezas.exists():
            # Caso 1: Seguimiento tiene piezas específicas vinculadas
            for pieza in piezas:
                # Determinar resultado
                if pieza.aceptada_por_cliente is None:
                    resultado = 'Sin Respuesta'
                elif pieza.aceptada_por_cliente:
                    resultado = 'Aceptado'
                else:
                    resultado = 'Rechazado'
                
                data.append({
                    'componente_nombre': pieza.componente.nombre,
                    'proveedor': proveedor,
                    'resultado': resultado,
                    'cantidad': pieza.cantidad,
                    'valor_total': float(pieza.costo_total),
                })
        else:
            # Caso 2: Seguimiento sin piezas vinculadas específicas
            # Usar todas las piezas de la cotización como referencia
            cotizacion = seg.cotizacion
            piezas_cotizacion = cotizacion.piezas_cotizadas.all()
            
            for pieza in piezas_cotizacion:
                # Determinar resultado
                if pieza.aceptada_por_cliente is None:
                    resultado = 'Sin Respuesta'
                elif pieza.aceptada_por_cliente:
                    resultado = 'Aceptado'
                else:
                    resultado = 'Rechazado'
                
                data.append({
                    'componente_nombre': pieza.componente.nombre,
                    'proveedor': proveedor,
                    'resultado': resultado,
                    'cantidad': pieza.cantidad,
                    'valor_total': float(pieza.costo_total),
                })
    
    df = pd.DataFrame(data)
    
    if df.empty:
        return pd.DataFrame(columns=[
            'componente_nombre', 'proveedor', 'resultado', 'cantidad', 'valor_total'
        ])
    
    # Agrupar y sumar
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
