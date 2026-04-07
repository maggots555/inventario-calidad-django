"""
Visualizaciones Interactivas con Plotly para Dashboard de Cotizaciones
Sistema de gráficos profesionales tipo Power BI

EXPLICACIÓN PARA PRINCIPIANTES:
Este archivo contiene funciones que generan gráficos HTML interactivos usando Plotly.
Plotly es como "Excel con superpoderes" - crea gráficos hermosos que puedes
hacer zoom, hover, filtrar, y exportar como imágenes.

NO REQUIERE JAVASCRIPT: Los gráficos se crean en Python y se insertan como HTML.
"""

import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
from datetime import datetime


# ============================================================================
# CONFIGURACIÓN GLOBAL DE PLOTLY
# ============================================================================

# Paleta de colores Bootstrap 5 (para consistencia con el resto del sitio)
COLORES = {
    'primary': '#0d6efd',      # Azul
    'success': '#198754',      # Verde
    'danger': '#dc3545',       # Rojo
    'warning': '#ffc107',      # Amarillo
    'info': '#0dcaf0',         # Cyan
    'secondary': '#6c757d',    # Gris
    'light': '#f8f9fa',        # Blanco grisáceo
    'dark': '#212529',         # Negro grisáceo
    
    # Colores adicionales para gráficos
    'purple': '#6f42c1',
    'pink': '#d63384',
    'orange': '#fd7e14',
    'teal': '#20c997',
    'indigo': '#6610f2',
}

# Configuración estándar para todos los gráficos
CONFIG_PLOTLY = {
    'responsive': True,                      # Se adapta al tamaño del contenedor
    'displayModeBar': True,                  # Mostrar barra de herramientas
    'displaylogo': False,                    # Ocultar logo de Plotly
    'modeBarButtonsToRemove': [              # Remover botones innecesarios
        'lasso2d', 
        'select2d'
    ],
    'toImageButtonOptions': {                # Configuración de exportación
        'format': 'png',
        'filename': 'dashboard_cotizaciones',
        'height': 1080,
        'width': 1920,
        'scale': 2
    },
    'locale': 'es'                           # Idioma español
}

# Layout estándar para todos los gráficos
LAYOUT_BASE = dict(
    font=dict(family='Segoe UI, sans-serif', size=12),
    paper_bgcolor='white',
    plot_bgcolor='#f8f9fa',
    hovermode='closest',
    margin=dict(l=50, r=50, t=80, b=50),
)


# ============================================================================
# CLASE PRINCIPAL: GENERADOR DE VISUALIZACIONES
# ============================================================================

class DashboardCotizacionesVisualizer:
    """
    Generador de visualizaciones interactivas para el dashboard de cotizaciones.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta clase contiene 20+ métodos, cada uno genera un tipo de gráfico diferente.
    Todos los gráficos son interactivos (zoom, hover, filtros) y se ven profesionales.
    
    Uso:
        visualizer = DashboardCotizacionesVisualizer()
        fig = visualizer.grafico_evolucion_cotizaciones(df, periodo='M')
        html = fig.to_html(config=CONFIG_PLOTLY)  # Convertir a HTML
    """
    
    def __init__(self):
        """Inicializa el visualizador con configuración por defecto."""
        self.colores = COLORES
        self.config = CONFIG_PLOTLY
    
    # ========================================================================
    # GRÁFICOS TEMPORALES (2 funciones)
    # ========================================================================
    
    def grafico_evolucion_cotizaciones(self, df, periodo='M'):
        """
        Gráfico de líneas: Evolución temporal de cotizaciones.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Muestra cómo han evolucionado las cotizaciones a lo largo del tiempo,
        separadas en tres series: Aceptadas, Rechazadas y Pendientes.
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
            periodo (str): Frecuencia temporal
                - 'D': Diario
                - 'W': Semanal
                - 'M': Mensual (default)
                - 'Q': Trimestral
                - 'Y': Anual
        
        Returns:
            Figure: Gráfico de Plotly listo para renderizar
        
        Ejemplo:
            fig = visualizer.grafico_evolucion_cotizaciones(df, periodo='M')
            html = fig.to_html(config=CONFIG_PLOTLY)
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay datos para mostrar")
        
        # Asegurar que fecha_envio sea datetime
        df = df.copy()
        df['fecha_envio'] = pd.to_datetime(df['fecha_envio'])
        
        # Diccionario de frecuencias para pandas
        freq_map = {
            'D': 'D',      # Diario
            'W': 'W',      # Semanal
            'M': 'ME',     # Mensual (fin de mes) - ME en lugar de M deprecado
            'Q': 'QE',     # Trimestral (fin de trimestre) - QE en lugar de Q
            'Y': 'YE'      # Anual (fin de año) - YE en lugar de Y
        }
        
        # Establecer fecha como índice
        df_temporal = df.set_index('fecha_envio')
        
        # Agrupar por período
        freq = freq_map.get(periodo, 'ME')
        
        # Contar aceptadas por período
        aceptadas = df_temporal[df_temporal['aceptada'] == True].resample(freq).size()
        rechazadas = df_temporal[df_temporal['aceptada'] == False].resample(freq).size()
        pendientes = df_temporal[df_temporal['aceptada'].isna()].resample(freq).size()
        
        # Crear figura
        fig = go.Figure()
        
        # Línea de aceptadas
        fig.add_trace(go.Scatter(
            x=aceptadas.index,
            y=aceptadas.values,
            mode='lines+markers',
            name='Aceptadas',
            line=dict(color=self.colores['success'], width=3),
            marker=dict(size=8),
            hovertemplate='<b>Aceptadas</b><br>Fecha: %{x|%b %Y}<br>Cantidad: %{y}<extra></extra>'
        ))
        
        # Línea de rechazadas
        fig.add_trace(go.Scatter(
            x=rechazadas.index,
            y=rechazadas.values,
            mode='lines+markers',
            name='Rechazadas',
            line=dict(color=self.colores['danger'], width=3),
            marker=dict(size=8),
            hovertemplate='<b>Rechazadas</b><br>Fecha: %{x|%b %Y}<br>Cantidad: %{y}<extra></extra>'
        ))
        
        # Línea de pendientes
        fig.add_trace(go.Scatter(
            x=pendientes.index,
            y=pendientes.values,
            mode='lines+markers',
            name='Pendientes',
            line=dict(color=self.colores['warning'], width=3),
            marker=dict(size=8),
            hovertemplate='<b>Pendientes</b><br>Fecha: %{x|%b %Y}<br>Cantidad: %{y}<extra></extra>'
        ))
        
        # Configurar layout
        periodo_nombres = {
            'D': 'Diaria',
            'W': 'Semanal',
            'M': 'Mensual',
            'Q': 'Trimestral',
            'Y': 'Anual'
        }
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text=f'📈 Evolución Temporal de Cotizaciones ({periodo_nombres[periodo]})',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(
                title='Período',
                showgrid=True,
                gridcolor='lightgray'
            ),
            yaxis=dict(
                title='Número de Cotizaciones',
                showgrid=True,
                gridcolor='lightgray'
            ),
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
            # hovermode ya está definido en LAYOUT_BASE
        )
        
        return fig
    
    def grafico_comparativo_periodos(self, df_actual, df_anterior):
        """
        Gráfico de barras: Comparación entre período actual y anterior.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Compara las métricas clave (total, aceptadas, rechazadas) entre dos períodos,
        mostrando si hubo crecimiento o decrecimiento.
        
        Args:
            df_actual (DataFrame): DataFrame del período actual
            df_anterior (DataFrame): DataFrame del período anterior
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_actual.empty and df_anterior.empty:
            return self._crear_grafico_vacio("No hay datos para comparar")
        
        # Calcular métricas para ambos períodos
        metricas = {
            'Total': [
                len(df_actual),
                len(df_anterior)
            ],
            'Aceptadas': [
                len(df_actual[df_actual['aceptada'] == True]),
                len(df_anterior[df_anterior['aceptada'] == True])
            ],
            'Rechazadas': [
                len(df_actual[df_actual['aceptada'] == False]),
                len(df_anterior[df_anterior['aceptada'] == False])
            ]
        }
        
        # Crear figura con barras agrupadas
        fig = go.Figure()
        
        periodos = ['Período Actual', 'Período Anterior']
        colores_barras = [self.colores['primary'], self.colores['info'], self.colores['danger']]
        
        for i, (metrica, valores) in enumerate(metricas.items()):
            fig.add_trace(go.Bar(
                name=metrica,
                x=periodos,
                y=valores,
                marker_color=colores_barras[i],
                text=valores,
                textposition='auto',
                hovertemplate=f'<b>{metrica}</b><br>%{{x}}<br>Cantidad: %{{y}}<extra></extra>'
            ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='📊 Comparativo: Período Actual vs Anterior',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Período'),
            yaxis=dict(title='Número de Cotizaciones'),
            barmode='group',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        )
        
        return fig
    
    # ========================================================================
    # GRÁFICOS DE DISTRIBUCIÓN (3 funciones)
    # ========================================================================
    
    def grafico_tasas_aceptacion(self, df, agrupar_por='sucursal'):
        """
        Gráfico de barras: Tasas de aceptación comparativas.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Muestra la tasa de aceptación (porcentaje) por diferentes dimensiones:
        sucursal, técnico o gama de equipo.
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
            agrupar_por (str): Dimensión de agrupación
                - 'sucursal' (default)
                - 'tecnico'
                - 'gama'
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay datos para mostrar tasas")
        
        # Filtrar solo cotizaciones con respuesta
        df_con_respuesta = df[df['aceptada'].notna()].copy()
        
        if df_con_respuesta.empty:
            return self._crear_grafico_vacio("No hay cotizaciones con respuesta aún")
        
        # Agrupar y calcular tasas
        grupos = df_con_respuesta.groupby(agrupar_por).agg({
            'aceptada': [
                ('total', 'count'),
                ('aceptadas', lambda x: (x == True).sum()),
                ('rechazadas', lambda x: (x == False).sum())
            ]
        })
        
        # Aplanar columnas multi-nivel
        grupos.columns = ['_'.join(col).strip() for col in grupos.columns.values]
        grupos = grupos.reset_index()
        
        # Calcular tasas
        grupos['tasa_aceptacion'] = (grupos['aceptada_aceptadas'] / grupos['aceptada_total'] * 100).round(2)
        grupos['tasa_rechazo'] = (grupos['aceptada_rechazadas'] / grupos['aceptada_total'] * 100).round(2)
        
        # Ordenar por tasa de aceptación descendente
        grupos = grupos.sort_values('tasa_aceptacion', ascending=True)
        
        # Crear gráfico de barras horizontales
        fig = go.Figure()
        
        # Barras de aceptación
        fig.add_trace(go.Bar(
            y=grupos[agrupar_por],
            x=grupos['tasa_aceptacion'],
            name='Aceptadas',
            orientation='h',
            marker=dict(color=self.colores['success']),
            text=grupos['tasa_aceptacion'].apply(lambda x: f'{x:.1f}%'),
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Tasa Aceptación: %{x:.2f}%<extra></extra>'
        ))
        
        # Barras de rechazo
        fig.add_trace(go.Bar(
            y=grupos[agrupar_por],
            x=grupos['tasa_rechazo'],
            name='Rechazadas',
            orientation='h',
            marker=dict(color=self.colores['danger']),
            text=grupos['tasa_rechazo'].apply(lambda x: f'{x:.1f}%'),
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Tasa Rechazo: %{x:.2f}%<extra></extra>'
        ))
        
        # Títulos según agrupación
        titulos = {
            'sucursal': 'Tasas de Aceptación por Sucursal',
            'tecnico': 'Tasas de Aceptación por Técnico',
            'gama': 'Tasas de Aceptación por Gama de Equipo'
        }
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text=f'📊 {titulos.get(agrupar_por, "Tasas de Aceptación")}',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Porcentaje (%)', range=[0, 100]),
            yaxis=dict(title=''),
            barmode='stack',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        )
        
        return fig
    
    def grafico_distribucion_costos(self, df):
        """
        Histograma + Boxplot: Distribución de montos de cotizaciones.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        - Histograma: Muestra cuántas cotizaciones hay en cada rango de precios
        - Boxplot: Muestra estadísticas (mínimo, máximo, mediana, cuartiles)
        
        Ayuda a identificar rangos típicos de precios y valores atípicos (outliers).
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
        
        Returns:
            Figure: Gráfico de Plotly con subplot (2 gráficos en uno)
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay datos de costos")
        
        # Crear figura con subplots (1 fila, 2 columnas)
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Distribución de Costos (Histograma)', 'Estadísticas (Boxplot)'),
            specs=[[{"type": "histogram"}, {"type": "box"}]]
        )
        
        # Histograma
        fig.add_trace(
            go.Histogram(
                x=df['costo_total'],
                name='Distribución',
                marker_color=self.colores['primary'],
                nbinsx=20,  # Número de barras
                hovertemplate='Rango: $%{x}<br>Frecuencia: %{y}<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Boxplot
        fig.add_trace(
            go.Box(
                y=df['costo_total'],
                name='Estadísticas',
                marker_color=self.colores['info'],
                boxmean='sd',  # Mostrar media y desviación estándar
                hovertemplate='Valor: $%{y:,.2f}<extra></extra>'
            ),
            row=1, col=2
        )
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='💰 Distribución de Costos de Cotizaciones',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            showlegend=False,
            height=500
        )
        
        # Configurar ejes
        fig.update_xaxes(title_text="Costo Total ($)", row=1, col=1)
        fig.update_yaxes(title_text="Frecuencia", row=1, col=1)
        fig.update_yaxes(title_text="Costo Total ($)", row=1, col=2)
        
        return fig
    
    def grafico_gamas_equipos(self, df):
        """
        Sunburst Chart: Distribución jerárquica por gama → tipo → marca.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Un gráfico de "sol" que muestra jerarquías. Cada nivel representa:
        - Centro: Total
        - Anillo 1: Gama (alta/media/baja)
        - Anillo 2: Tipo de equipo (laptop/pc/aio)
        - Anillo 3: Marca
        
        Permite ver rápidamente qué combinaciones son más comunes.
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay datos de equipos")
        
        # Crear jerarquía de datos
        # Formato: labels=['Total', 'Alta', 'Media', ...], parents=['', 'Total', 'Total', ...]
        labels = ['Total']
        parents = ['']
        values = [len(df)]
        
        # Nivel 1: Gamas
        for gama in df['gama'].unique():
            if pd.notna(gama):
                count = len(df[df['gama'] == gama])
                labels.append(f'Gama {gama.capitalize()}')
                parents.append('Total')
                values.append(count)
                
                # Nivel 2: Tipos de equipo dentro de cada gama
                df_gama = df[df['gama'] == gama]
                for tipo in df_gama['tipo_equipo'].unique():
                    if pd.notna(tipo):
                        count_tipo = len(df_gama[df_gama['tipo_equipo'] == tipo])
                        labels.append(f'{tipo.upper()}')
                        parents.append(f'Gama {gama.capitalize()}')
                        values.append(count_tipo)
        
        # Crear gráfico sunburst
        fig = go.Figure(go.Sunburst(
            labels=labels,
            parents=parents,
            values=values,
            branchvalues="total",
            marker=dict(
                colors=[
                    self.colores['primary'],
                    self.colores['success'],
                    self.colores['warning'],
                    self.colores['danger']
                ],
                line=dict(color='white', width=2)
            ),
            hovertemplate='<b>%{label}</b><br>Cotizaciones: %{value}<br>Porcentaje: %{percentParent}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='⭐ Distribución por Gama y Tipo de Equipo',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            height=600
        )
        
        return fig
    
    # ========================================================================
    # ANÁLISIS DE PIEZAS (3 funciones)
    # ========================================================================
    
    def grafico_top_piezas_rechazadas(self, df_piezas, top_n=10):
        """
        Barras horizontales: Top N piezas más rechazadas.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Identifica qué componentes son rechazados con mayor frecuencia por los clientes.
        Útil para entender resistencias de los clientes o problemas de pricing.
        
        Args:
            df_piezas (DataFrame): DataFrame de piezas cotizadas
            top_n (int): Número de piezas a mostrar (default: 10)
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_piezas.empty:
            return self._crear_grafico_vacio("No hay datos de piezas")
        
        # Filtrar solo piezas rechazadas
        rechazadas = df_piezas[df_piezas['aceptada'] == False].copy()
        
        if rechazadas.empty:
            return self._crear_grafico_vacio("No hay piezas rechazadas")
        
        # Contar por componente
        top_rechazadas = rechazadas.groupby('componente').size().reset_index(name='count')
        top_rechazadas = top_rechazadas.sort_values('count', ascending=True).tail(top_n)
        
        # Crear gráfico
        fig = go.Figure(go.Bar(
            y=top_rechazadas['componente'],
            x=top_rechazadas['count'],
            orientation='h',
            marker=dict(color=self.colores['danger']),
            text=top_rechazadas['count'],
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Rechazos: %{x}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text=f'🚫 Top {top_n} Piezas Más Rechazadas',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Número de Rechazos'),
            yaxis=dict(title=''),
            height=500
        )
        
        return fig
    
    def grafico_top_piezas_aceptadas(self, df_piezas, top_n=10):
        """
        Barras horizontales: Top N piezas más aceptadas.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Identifica qué componentes son aceptados con mayor frecuencia por los clientes.
        Útil para entender qué piezas tienen mejor recepción y pueden ser priorizadas
        en futuras cotizaciones. Complementa el análisis de piezas rechazadas.
        
        Args:
            df_piezas (DataFrame): DataFrame de piezas cotizadas
            top_n (int): Número de piezas a mostrar (default: 10)
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_piezas.empty:
            return self._crear_grafico_vacio("No hay datos de piezas")
        
        # Filtrar solo piezas aceptadas
        aceptadas = df_piezas[df_piezas['aceptada'] == True].copy()
        
        if aceptadas.empty:
            return self._crear_grafico_vacio("No hay piezas aceptadas")
        
        # Contar por componente
        top_aceptadas = aceptadas.groupby('componente').size().reset_index(name='count')
        top_aceptadas = top_aceptadas.sort_values('count', ascending=True).tail(top_n)
        
        # Crear gráfico
        fig = go.Figure(go.Bar(
            y=top_aceptadas['componente'],
            x=top_aceptadas['count'],
            orientation='h',
            marker=dict(color=self.colores['success']),
            text=top_aceptadas['count'],
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Aceptaciones: %{x}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text=f'✅ Top {top_n} Piezas Más Aceptadas',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Número de Aceptaciones'),
            yaxis=dict(title=''),
            height=500
        )
        
        return fig
    
    def grafico_sugerencias_tecnico(self, df_piezas):
        """
        Sankey Diagram: Flujo de piezas sugeridas → Aceptadas/Rechazadas.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Un diagrama de flujo que muestra:
        - ¿Cuántas piezas fueron sugeridas por técnicos vs solicitadas por clientes?
        - De las sugeridas por técnicos, ¿cuántas se aceptaron vs rechazaron?
        
        Permite evaluar la efectividad de las sugerencias técnicas.
        
        Args:
            df_piezas (DataFrame): DataFrame de piezas cotizadas
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_piezas.empty:
            return self._crear_grafico_vacio("No hay datos de piezas")
        
        # Calcular flujos
        sugeridas_tecnico_aceptadas = len(df_piezas[
            (df_piezas['sugerida_por_tecnico'] == True) & 
            (df_piezas['aceptada'] == True)
        ])
        sugeridas_tecnico_rechazadas = len(df_piezas[
            (df_piezas['sugerida_por_tecnico'] == True) & 
            (df_piezas['aceptada'] == False)
        ])
        solicitadas_cliente_aceptadas = len(df_piezas[
            (df_piezas['sugerida_por_tecnico'] == False) & 
            (df_piezas['aceptada'] == True)
        ])
        solicitadas_cliente_rechazadas = len(df_piezas[
            (df_piezas['sugerida_por_tecnico'] == False) & 
            (df_piezas['aceptada'] == False)
        ])
        
        # Nodos del diagrama
        labels = [
            'Sugeridas por Técnico',    # 0
            'Solicitadas por Cliente',  # 1
            'Aceptadas',                 # 2
            'Rechazadas'                 # 3
        ]
        
        # Flujos (source → target con valor)
        source = [0, 0, 1, 1]  # Índices de nodos origen
        target = [2, 3, 2, 3]  # Índices de nodos destino
        value = [
            sugeridas_tecnico_aceptadas,
            sugeridas_tecnico_rechazadas,
            solicitadas_cliente_aceptadas,
            solicitadas_cliente_rechazadas
        ]
        
        # Colores de los flujos
        link_colors = [
            self.colores['success'],  # Sugeridas → Aceptadas (verde)
            self.colores['danger'],   # Sugeridas → Rechazadas (rojo)
            self.colores['info'],     # Solicitadas → Aceptadas (cyan)
            self.colores['warning']   # Solicitadas → Rechazadas (amarillo)
        ]
        
        # Crear diagrama Sankey
        fig = go.Figure(go.Sankey(
            node=dict(
                pad=15,
                thickness=20,
                line=dict(color='black', width=0.5),
                label=labels,
                color=[
                    self.colores['primary'],
                    self.colores['secondary'],
                    self.colores['success'],
                    self.colores['danger']
                ]
            ),
            link=dict(
                source=source,
                target=target,
                value=value,
                color=link_colors
            )
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🔧 Efectividad de Sugerencias de Técnicos',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            height=500
        )
        
        return fig
    
    def grafico_piezas_necesarias_vs_opcionales(self, df_piezas):
        """
        Barras apiladas: Necesarias vs Opcionales por estado.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Compara piezas marcadas como "necesarias" vs "opcionales" (mejoras)
        y cómo fueron recibidas por los clientes (aceptadas/rechazadas).
        
        Args:
            df_piezas (DataFrame): DataFrame de piezas cotizadas
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_piezas.empty:
            return self._crear_grafico_vacio("No hay datos de piezas")
        
        # Filtrar solo piezas con respuesta
        df_con_respuesta = df_piezas[df_piezas['aceptada'].notna()].copy()
        
        if df_con_respuesta.empty:
            return self._crear_grafico_vacio("No hay piezas con respuesta")
        
        # Calcular conteos
        necesarias_aceptadas = len(df_con_respuesta[
            (df_con_respuesta['es_necesaria'] == True) & 
            (df_con_respuesta['aceptada'] == True)
        ])
        necesarias_rechazadas = len(df_con_respuesta[
            (df_con_respuesta['es_necesaria'] == True) & 
            (df_con_respuesta['aceptada'] == False)
        ])
        opcionales_aceptadas = len(df_con_respuesta[
            (df_con_respuesta['es_necesaria'] == False) & 
            (df_con_respuesta['aceptada'] == True)
        ])
        opcionales_rechazadas = len(df_con_respuesta[
            (df_con_respuesta['es_necesaria'] == False) & 
            (df_con_respuesta['aceptada'] == False)
        ])
        
        # Crear gráfico de barras apiladas
        fig = go.Figure()
        
        categorias = ['Necesarias', 'Opcionales (Mejoras)']
        
        fig.add_trace(go.Bar(
            name='Aceptadas',
            x=categorias,
            y=[necesarias_aceptadas, opcionales_aceptadas],
            marker_color=self.colores['success'],
            text=[necesarias_aceptadas, opcionales_aceptadas],
            textposition='auto'
        ))
        
        fig.add_trace(go.Bar(
            name='Rechazadas',
            x=categorias,
            y=[necesarias_rechazadas, opcionales_rechazadas],
            marker_color=self.colores['danger'],
            text=[necesarias_rechazadas, opcionales_rechazadas],
            textposition='auto'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🔩 Piezas Necesarias vs Opcionales',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Tipo de Pieza'),
            yaxis=dict(title='Cantidad'),
            barmode='stack',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        )
        
        return fig
    
    # ========================================================================
    # RENDIMIENTO DE TÉCNICOS (2 funciones)
    # ========================================================================
    
    def grafico_rendimiento_tecnicos(self, df):
        """
        Barras apiladas: Rendimiento de técnicos con métricas múltiples.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Muestra para cada técnico:
        - Total de cotizaciones generadas
        - Cuántas fueron aceptadas vs rechazadas
        - Permite identificar quiénes tienen mejor desempeño
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay datos de técnicos")
        
        # Filtrar solo con respuesta
        df_con_respuesta = df[df['aceptada'].notna()].copy()
        
        if df_con_respuesta.empty:
            return self._crear_grafico_vacio("No hay cotizaciones con respuesta")
        
        # Agrupar por técnico
        tecnicos = df_con_respuesta.groupby('tecnico').agg({
            'cotizacion_id': 'count',
            'aceptada': [
                ('aceptadas', lambda x: (x == True).sum()),
                ('rechazadas', lambda x: (x == False).sum())
            ]
        })
        
        tecnicos.columns = ['total', 'aceptadas', 'rechazadas']
        tecnicos = tecnicos.reset_index()
        
        # Calcular tasa
        tecnicos['tasa'] = (tecnicos['aceptadas'] / tecnicos['total'] * 100).round(2)
        
        # Ordenar por tasa descendente
        tecnicos = tecnicos.sort_values('tasa', ascending=True)
        
        # Tomar top 10 si hay muchos
        if len(tecnicos) > 10:
            tecnicos = tecnicos.tail(10)
        
        # Crear figura con eje secundario
        fig = go.Figure()
        
        # Barras apiladas
        fig.add_trace(go.Bar(
            y=tecnicos['tecnico'],
            x=tecnicos['aceptadas'],
            name='Aceptadas',
            orientation='h',
            marker=dict(color=self.colores['success']),
            text=tecnicos['aceptadas'],
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Aceptadas: %{x}<extra></extra>'
        ))
        
        fig.add_trace(go.Bar(
            y=tecnicos['tecnico'],
            x=tecnicos['rechazadas'],
            name='Rechazadas',
            orientation='h',
            marker=dict(color=self.colores['danger']),
            text=tecnicos['rechazadas'],
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Rechazadas: %{x}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='👨‍🔧 Rendimiento de Técnicos',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Número de Cotizaciones'),
            yaxis=dict(title=''),
            barmode='stack',
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            ),
            height=max(400, len(tecnicos) * 40)  # Altura dinámica
        )
        
        return fig
    
    def grafico_ranking_tecnicos(self, df_metricas):
        """
        Barras horizontales: Top técnicos por tasa de aceptación.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Ranking visual de técnicos ordenados de mejor a peor tasa de aceptación.
        Útil para identificar mejores prácticas y áreas de mejora.
        
        Args:
            df_metricas (DataFrame): DataFrame con métricas por técnico
                                    (generado por calcular_metricas_por_tecnico)
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_metricas.empty:
            return self._crear_grafico_vacio("No hay métricas de técnicos")
        
        # Tomar top 10
        top_10 = df_metricas.head(10).copy()
        
        # Crear gráfico
        fig = go.Figure(go.Bar(
            y=top_10['tecnico'][::-1],  # Invertir para que el mejor esté arriba
            x=top_10['tasa_aceptacion'][::-1],
            orientation='h',
            marker=dict(
                color=top_10['tasa_aceptacion'][::-1],
                colorscale=[
                    [0, self.colores['danger']],
                    [0.5, self.colores['warning']],
                    [1, self.colores['success']]
                ],
                showscale=True,
                colorbar=dict(title="Tasa %")
            ),
            text=top_10['tasa_aceptacion'][::-1].apply(lambda x: f'{x:.1f}%'),
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Tasa: %{x:.2f}%<br>Total: %{text}<extra></extra>',
            customdata=top_10[['total', 'aceptadas']][::-1].values
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🏆 Top 10 Técnicos por Tasa de Aceptación',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Tasa de Aceptación (%)', range=[0, 100]),
            yaxis=dict(title=''),
            height=500
        )
        
        return fig
    
    # ========================================================================
    # ANÁLISIS POR SUCURSAL (2 funciones)
    # ========================================================================
    
    def grafico_rendimiento_sucursales(self, df_metricas):
        """
        Mapa de calor: Métricas por sucursal.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Un "heatmap" que muestra varias métricas simultáneamente:
        - Total de cotizaciones
        - Tasa de aceptación
        - Valor total
        
        Colores más intensos = valores más altos
        
        Args:
            df_metricas (DataFrame): DataFrame con métricas por sucursal
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_metricas.empty:
            return self._crear_grafico_vacio("No hay métricas de sucursales")
        
        # Preparar datos para heatmap
        # Normalizar valores a escala 0-100 para comparar
        metricas_norm = df_metricas[['total', 'tasa_aceptacion', 'valor_cotizado']].copy()
        metricas_norm['total_norm'] = (metricas_norm['total'] / metricas_norm['total'].max() * 100)
        metricas_norm['valor_norm'] = (metricas_norm['valor_cotizado'] / metricas_norm['valor_cotizado'].max() * 100)
        
        # Crear matriz de datos
        z_data = [
            metricas_norm['total_norm'].values,
            metricas_norm['tasa_aceptacion'].values,
            metricas_norm['valor_norm'].values
        ]
        
        # Labels
        y_labels = ['Total Cotizaciones', 'Tasa Aceptación (%)', 'Valor Cotizado']
        x_labels = df_metricas['sucursal'].tolist()
        
        # Crear heatmap
        fig = go.Figure(go.Heatmap(
            z=z_data,
            x=x_labels,
            y=y_labels,
            colorscale='RdYlGn',  # Rojo-Amarillo-Verde
            text=[
                df_metricas['total'].values,
                df_metricas['tasa_aceptacion'].values,
                df_metricas['valor_cotizado'].apply(lambda x: f'${x:,.0f}').values
            ],
            texttemplate='%{text}',
            textfont=dict(size=12),
            hovertemplate='%{y}<br>%{x}<br>Valor: %{text}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🏢 Mapa de Calor: Rendimiento por Sucursal',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Sucursal'),
            yaxis=dict(title='Métrica'),
            height=400
        )
        
        return fig
    
    def grafico_distribucion_sucursales(self, df_metricas):
        """
        Treemap: Distribución de sucursales por valor y tasa.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Cuadros de diferentes tamaños y colores donde:
        - Tamaño del cuadro = Valor total cotizado
        - Color = Tasa de aceptación (verde=alta, rojo=baja)
        
        Permite identificar rápidamente sucursales con alto volumen y buena tasa.
        
        Args:
            df_metricas (DataFrame): DataFrame con métricas por sucursal
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_metricas.empty:
            return self._crear_grafico_vacio("No hay métricas de sucursales")
        
        # Crear treemap
        fig = go.Figure(go.Treemap(
            labels=df_metricas['sucursal'],
            parents=[''] * len(df_metricas),  # Todos hijos de raíz
            values=df_metricas['valor_cotizado'],
            marker=dict(
                colors=df_metricas['tasa_aceptacion'],
                colorscale='RdYlGn',
                cmid=50,  # Centro de escala en 50%
                colorbar=dict(title="Tasa %", ticksuffix='%')
            ),
            text=df_metricas.apply(
                lambda row: f"{row['sucursal']}<br>Total: {row['total']}<br>Tasa: {row['tasa_aceptacion']:.1f}%<br>${row['valor_cotizado']:,.0f}",
                axis=1
            ),
            textposition='middle center',
            hovertemplate='<b>%{label}</b><br>Valor: $%{value:,.0f}<br>Tasa: %{color:.1f}%<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🗺️ Treemap: Distribución de Valor por Sucursal',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            height=600
        )
        
        return fig
    
    # ========================================================================
    # ANÁLISIS DE PROVEEDORES (2 funciones)
    # ========================================================================
    
    def grafico_proveedores_performance(self, df_seguimientos):
        """
        Scatter plot: Rendimiento de proveedores.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Gráfico de dispersión donde cada punto es un proveedor:
        - Eje X: Tiempo promedio de entrega
        - Eje Y: Cantidad de piezas suministradas
        - Tamaño: Costo total
        
        Proveedores ideales: Muchas piezas + Entregas rápidas
        
        Args:
            df_seguimientos (DataFrame): DataFrame de seguimientos de piezas
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_seguimientos.empty:
            return self._crear_grafico_vacio("No hay datos de proveedores")
        
        # Agrupar por proveedor
        proveedores = df_seguimientos.groupby('proveedor').agg({
            'seguimiento_id': 'count',  # Cantidad de pedidos
            'dias_desde_pedido': 'mean',  # Tiempo promedio
        }).reset_index()
        
        proveedores.columns = ['proveedor', 'total_pedidos', 'dias_promedio']
        
        # Crear scatter
        fig = go.Figure(go.Scatter(
            x=proveedores['dias_promedio'],
            y=proveedores['total_pedidos'],
            mode='markers+text',
            marker=dict(
                size=proveedores['total_pedidos'] * 10,  # Tamaño proporcional
                color=proveedores['dias_promedio'],
                colorscale='RdYlGn_r',  # Invertido: rojo=lento, verde=rápido
                showscale=True,
                colorbar=dict(title="Días"),
                line=dict(width=1, color='white')
            ),
            text=proveedores['proveedor'],
            textposition='top center',
            hovertemplate='<b>%{text}</b><br>Pedidos: %{y}<br>Días promedio: %{x:.1f}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='📦 Rendimiento de Proveedores',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Tiempo Promedio de Entrega (días)'),
            yaxis=dict(title='Cantidad de Pedidos'),
            height=600
        )
        
        return fig
    
    def grafico_top_proveedores(self, df_seguimientos, top_n=10):
        """
        Barras horizontales: Top proveedores por cantidad de pedidos.
        
        Args:
            df_seguimientos (DataFrame): DataFrame de seguimientos
            top_n (int): Número de proveedores a mostrar
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_seguimientos.empty:
            return self._crear_grafico_vacio("No hay datos de proveedores")
        
        # Agrupar y contar
        top_prov = df_seguimientos.groupby('proveedor').size().reset_index(name='pedidos')
        top_prov = top_prov.sort_values('pedidos', ascending=True).tail(top_n)
        
        # Crear gráfico
        fig = go.Figure(go.Bar(
            y=top_prov['proveedor'],
            x=top_prov['pedidos'],
            orientation='h',
            marker=dict(color=self.colores['primary']),
            text=top_prov['pedidos'],
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Pedidos: %{x}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text=f'📊 Top {top_n} Proveedores Más Utilizados',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Número de Pedidos'),
            yaxis=dict(title=''),
            height=max(400, len(top_prov) * 40)
        )
        
        return fig
    
    def grafico_proveedores_impacto_conversion(self, df_proveedores_conversion):
        """
        Heatmap: Impacto de proveedores en conversión de ventas A NIVEL DE PIEZA.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Este heatmap (mapa de calor) muestra 4 métricas clave por proveedor:
        1. Tasa de Aceptación (%) - ¿Las PIEZAS de este proveedor se aceptan?
        2. Tasa de Rechazo (%) - ¿Cuántas PIEZAS son rechazadas?
        3. Velocidad de Entrega - Score normalizado (100 = más rápido)
        4. Valor Generado ($) - ¿Cuántos ingresos reales genera?
        
        Colores:
        - Verde: Buen desempeño
        - Amarillo: Desempeño medio
        - Rojo: Desempeño bajo
        
        INSIGHT CLAVE:
        Permite identificar proveedores "estrella" (alto en las 3 métricas) vs
        proveedores "problemáticos" (alto volumen pero baja conversión).
        
        CORRECCIÓN NOVIEMBRE 2025:
        Ahora muestra rechazos A NIVEL DE PIEZA, no de cotización completa.
        
        Args:
            df_proveedores_conversion (DataFrame): DataFrame de métricas de proveedores
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_proveedores_conversion.empty:
            return self._crear_grafico_vacio("No hay datos de impacto de proveedores")
        
        # Filtrar top 15 proveedores por valor generado
        df_top = df_proveedores_conversion.nlargest(15, 'valor_generado').copy()
        
        if df_top.empty:
            return self._crear_grafico_vacio("No hay suficientes datos de proveedores")
        
        # Preparar datos para el heatmap
        # Normalizar métricas para comparación visual (0-100 scale)
        
        # 1. Tasa de aceptación (ya está en 0-100)
        tasa_aceptacion = df_top['tasa_aceptacion'].values
        
        # 2. Tasa de rechazo (NUEVO - invertir para visualización: menos rechazo = mejor)
        # Invertir: 100 - rechazo, para que verde = bajo rechazo
        tasa_rechazo = df_top['tasa_rechazo'].values
        tasa_rechazo_invertida = 100 - tasa_rechazo
        
        # 3. Tiempo de entrega (invertir: menos días = mejor)
        # Normalizar a escala 0-100 donde 100 = más rápido
        tiempos = df_top['tiempo_entrega_promedio'].fillna(df_top['tiempo_entrega_promedio'].max())
        max_tiempo = tiempos.max() if tiempos.max() > 0 else 1
        tiempo_normalizado = 100 - (tiempos / max_tiempo * 100)
        
        # 4. Valor generado (normalizar a 0-100)
        valores = df_top['valor_generado'].values
        max_valor = valores.max() if valores.max() > 0 else 1
        valor_normalizado = (valores / max_valor * 100)
        
        # Crear matriz de datos (proveedores x métricas)
        z_data = [
            tasa_aceptacion.tolist(),
            tasa_rechazo_invertida.tolist(),  # NUEVO: Tasa de rechazo invertida
            tiempo_normalizado.tolist(),
            valor_normalizado.tolist()
        ]
        
        # Etiquetas de texto para mostrar valores reales
        text_data = [
            [f"{val:.1f}%" for val in tasa_aceptacion],
            [f"{val:.1f}%" for val in tasa_rechazo],  # Mostrar valor real (no invertido)
            [f"{val:.0f} días" for val in tiempos],
            [f"${val:,.0f}" for val in valores]
        ]
        
        # Crear heatmap
        fig = go.Figure(data=go.Heatmap(
            z=z_data,
            x=df_top['proveedor'].tolist(),
            y=['Tasa Aceptación', 'Tasa Rechazo', 'Velocidad Entrega', 'Valor Generado'],
            text=text_data,
            texttemplate='%{text}',
            textfont={"size": 10, "color": "white"},
            colorscale='RdYlGn',  # Rojo-Amarillo-Verde
            showscale=True,
            colorbar=dict(
                title=dict(
                    text="Desempeño<br>(0-100)",
                    side="right"
                ),
                tickmode="linear",
                tick0=0,
                dtick=25
            ),
            hovertemplate='<b>%{y}</b><br>Proveedor: %{x}<br>Valor: %{text}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🎯 Impacto de Proveedores en Conversión (Top 15) - Análisis por Pieza',
                x=0.5,
                xanchor='center',
                font=dict(size=17, color=self.colores['dark'])
            ),
            xaxis=dict(
                title='',
                tickangle=-45,
                tickfont=dict(size=10)
            ),
            yaxis=dict(
                title='',
                tickfont=dict(size=11)
            ),
            height=550
        )
        
        # Actualizar margen por separado para evitar conflicto con LAYOUT_BASE
        fig.update_layout(margin=dict(b=120, l=150, r=100, t=80))
        
        return fig
    
    def grafico_componentes_por_proveedor(self, df_componentes):
        """
        Sunburst: Análisis jerárquico de componentes por proveedor.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Un "sunburst chart" es un gráfico de anillos concéntricos que muestra
        jerarquías de datos. Cada anillo representa un nivel de detalle.
        
        ESTRUCTURA:
        - Centro: Todas las piezas
        - Anillo 1: Tipo de componente (RAM, Disco, Pantalla, etc.)
        - Anillo 2: Proveedor que suministra ese componente
        - Anillo 3: Resultado (Aceptado/Rechazado/Sin Respuesta)
        
        CÓMO USAR:
        - Click en cualquier segmento para hacer zoom
        - El tamaño representa cantidad de piezas o valor
        - Colores diferenciados por nivel jerárquico
        
        INSIGHTS QUE REVELA:
        - ¿Qué proveedor domina cada categoría de componente?
        - ¿Hay diversificación o dependencia de un solo proveedor?
        - ¿Ciertos proveedores tienen mejor aceptación en componentes específicos?
        - ¿Qué categorías generan más rechazo?
        
        Args:
            df_componentes (DataFrame): DataFrame de componentes por proveedor
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_componentes.empty:
            return self._crear_grafico_vacio("No hay datos de componentes por proveedor")
        
        # Preparar datos jerárquicos para Sunburst
        # Estructura: Raíz -> Componente -> Proveedor -> Resultado
        
        labels = ['Todos los Componentes']
        parents = ['']
        values = [df_componentes['cantidad'].sum()]
        colors = [self.colores['primary']]
        
        # Nivel 1: Componentes
        componentes = df_componentes.groupby('componente_nombre').agg({
            'cantidad': 'sum',
            'valor_total': 'sum'
        }).reset_index()
        
        for _, comp in componentes.iterrows():
            labels.append(comp['componente_nombre'])
            parents.append('Todos los Componentes')
            values.append(comp['cantidad'])
            colors.append(self.colores['info'])
        
        # Nivel 2: Proveedores por componente
        proveedores_por_comp = df_componentes.groupby(['componente_nombre', 'proveedor']).agg({
            'cantidad': 'sum',
            'valor_total': 'sum'
        }).reset_index()
        
        for _, prov_comp in proveedores_por_comp.iterrows():
            # Crear ID único para evitar conflictos (mismo proveedor en diferentes componentes)
            label_id = f"{prov_comp['componente_nombre']} - {prov_comp['proveedor']}"
            parent = prov_comp['componente_nombre']
            labels.append(label_id)
            parents.append(parent)
            values.append(prov_comp['cantidad'])
            colors.append(self.colores['warning'])
        
        # Nivel 3: Resultados por proveedor-componente
        for _, row in df_componentes.iterrows():
            # Usar el mismo formato de ID único para el padre
            label = f"{row['resultado']}"
            parent = f"{row['componente_nombre']} - {row['proveedor']}"
            
            # Colores según resultado
            if row['resultado'] == 'Aceptado':
                color = self.colores['success']
            elif row['resultado'] == 'Rechazado':
                color = self.colores['danger']
            else:
                color = self.colores['secondary']
            
            labels.append(label)
            parents.append(parent)
            values.append(row['cantidad'])
            colors.append(color)
        
        # Crear figura Sunburst
        fig = go.Figure(go.Sunburst(
            labels=labels,
            parents=parents,
            values=values,
            branchvalues='total',
            marker=dict(
                colors=colors,
                line=dict(color='white', width=2)
            ),
            hovertemplate='<b>%{label}</b><br>Cantidad: %{value}<br>%{percentParent}<extra></extra>',
            textfont=dict(size=11, color='white', family='Arial')
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🔧 Análisis de Componentes por Proveedor y Resultado',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            height=700
        )
        
        # Actualizar margen por separado para evitar conflicto con LAYOUT_BASE
        fig.update_layout(margin=dict(t=80, l=0, r=0, b=0))
        
        return fig
    
    # ========================================================================
    # TIEMPOS Y EFICIENCIA (2 funciones)
    # ========================================================================
    
    def grafico_tiempos_respuesta(self, df):
        """
        Violin plot: Distribución de tiempos de respuesta.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Un "violin plot" es como un histograma rotado que muestra:
        - La distribución completa de tiempos de respuesta
        - Dónde se concentran la mayoría de casos
        - Si hay valores atípicos (muy rápidos o muy lentos)
        
        Más ancho = más cotizaciones en ese tiempo
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay datos de tiempos")
        
        # Filtrar solo con respuesta
        df_con_respuesta = df[df['fecha_respuesta'].notna()].copy()
        
        if df_con_respuesta.empty:
            return self._crear_grafico_vacio("No hay cotizaciones con respuesta")
        
        # Crear violin plot
        fig = go.Figure()
        
        # Por estado (aceptada/rechazada)
        for estado, color in [
            (True, self.colores['success']),
            (False, self.colores['danger'])
        ]:
            df_estado = df_con_respuesta[df_con_respuesta['aceptada'] == estado]
            if not df_estado.empty:
                nombre = 'Aceptadas' if estado else 'Rechazadas'
                fig.add_trace(go.Violin(
                    y=df_estado['dias_sin_respuesta'],
                    name=nombre,
                    box_visible=True,
                    meanline_visible=True,
                    fillcolor=color,
                    opacity=0.6,
                    hovertemplate=f'<b>{nombre}</b><br>Días: %{{y}}<extra></extra>'
                ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='⏱️ Distribución de Tiempos de Respuesta',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            yaxis=dict(title='Días de Respuesta'),
            xaxis=dict(title=''),
            height=500
        )
        
        return fig
    
    def grafico_motivos_rechazo(self, df):
        """
        Gráfico de barras: Motivos por los cuales los clientes rechazan cotizaciones.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Analiza y visualiza las razones específicas por las que los clientes
        deciden NO aceptar una cotización. Esto ayuda a identificar:
        - Problemas recurrentes (ej: costos altos, muchas piezas)
        - Áreas de mejora en el servicio
        - Patrones de rechazo que se pueden prevenir
        
        Los motivos vienen del campo 'motivo_rechazo' del modelo Cotizacion.
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay datos de cotizaciones")
        
        # Filtrar solo cotizaciones rechazadas que tengan motivo registrado
        df_rechazadas = df[(df['aceptada'] == False) & (df['motivo_rechazo'].notna())].copy()
        
        if df_rechazadas.empty:
            return self._crear_grafico_vacio("No hay cotizaciones rechazadas con motivo registrado")
        
        # Contar por motivo
        motivos_count = df_rechazadas['motivo_rechazo'].value_counts().reset_index()
        motivos_count.columns = ['motivo', 'count']
        
        # Diccionario de etiquetas legibles (basado en MOTIVO_RECHAZO_COTIZACION)
        labels_motivos = {
            'costo_alto': 'Costo muy elevado',
            'muchas_piezas': 'Demasiadas piezas',
            'tiempo_largo': 'Tiempo muy largo',
            'falta_justificacion': 'Falta justificación',
            'no_vale_pena': 'No vale la pena reparar',
            'no_hay_partes': 'No hay partes disponibles',
            'otro': 'Otro motivo',
        }
        
        # Aplicar etiquetas legibles
        motivos_count['motivo_label'] = motivos_count['motivo'].map(
            lambda x: labels_motivos.get(x, x.replace('_', ' ').title())
        )
        
        # Ordenar de mayor a menor
        motivos_count = motivos_count.sort_values('count', ascending=True)
        
        # Calcular porcentajes
        total_rechazadas = motivos_count['count'].sum()
        motivos_count['porcentaje'] = (motivos_count['count'] / total_rechazadas * 100).round(1)
        
        # Crear gráfico de barras horizontales
        fig = go.Figure(go.Bar(
            y=motivos_count['motivo_label'],
            x=motivos_count['count'],
            orientation='h',
            marker=dict(
                color=motivos_count['count'],
                colorscale='Reds',
                showscale=False
            ),
            text=[f"{count} ({pct}%)" for count, pct in zip(motivos_count['count'], motivos_count['porcentaje'])],
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Rechazos: %{x}<br>Porcentaje: %{text}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text=f'❌ Motivos de Rechazo de Cotizaciones ({total_rechazadas} rechazos)',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Número de Rechazos'),
            yaxis=dict(title=''),
            height=500
        )
        
        return fig
    
    def grafico_motivos_rechazo_vs_costos(self, df):
        """
        Boxplot: Distribución de costos por motivo de rechazo.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Este gráfico cruza dos variables importantes:
        - MOTIVO por el que rechazan (eje X)
        - COSTO de la cotización rechazada (eje Y)
        
        Un "boxplot" (diagrama de caja) muestra:
        - La MEDIANA (línea central) = costo típico para ese motivo
        - El RANGO intercuartílico (caja) = donde están el 50% de los casos
        - Los VALORES ATÍPICOS (puntos) = casos extremos
        
        INSIGHTS CLAVE QUE REVELA:
        1. ¿Es verdad que rechazan por "costo alto" solo en cotizaciones caras?
        2. ¿"No vale la pena" aparece en cotizaciones baratas o caras?
        3. ¿Hay motivos asociados con rangos de costo específicos?
        4. ¿Los costos altos garantizan cierto tipo de rechazo?
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay datos de cotizaciones")
        
        # Filtrar solo cotizaciones rechazadas con motivo y costo
        df_rechazadas = df[
            (df['aceptada'] == False) & 
            (df['motivo_rechazo'].notna()) & 
            (df['costo_total'].notna())
        ].copy()
        
        if df_rechazadas.empty:
            return self._crear_grafico_vacio("No hay cotizaciones rechazadas con motivo y costo registrados")
        
        # Diccionario de etiquetas legibles
        labels_motivos = {
            'costo_alto': 'Costo muy elevado',
            'muchas_piezas': 'Demasiadas piezas',
            'tiempo_largo': 'Tiempo muy largo',
            'falta_justificacion': 'Falta justificación',
            'no_vale_pena': 'No vale la pena',
            'no_hay_partes': 'No hay partes',
            'otro': 'Otro motivo',
        }
        
        # Aplicar etiquetas legibles
        df_rechazadas['motivo_label'] = df_rechazadas['motivo_rechazo'].map(
            lambda x: labels_motivos.get(x, x.replace('_', ' ').title())
        )
        
        # Obtener motivos únicos ordenados por mediana de costo (descendente)
        medianas = df_rechazadas.groupby('motivo_label')['costo_total'].median().sort_values(ascending=False)
        motivos_ordenados = medianas.index.tolist()
        
        # Crear figura
        fig = go.Figure()
        
        # Paleta de colores para cada motivo
        colores_motivos = [
            self.colores['danger'],
            self.colores['warning'],
            self.colores['orange'],
            self.colores['purple'],
            self.colores['info'],
            self.colores['secondary'],
            self.colores['pink'],
        ]
        
        # Agregar un boxplot por cada motivo
        for idx, motivo in enumerate(motivos_ordenados):
            df_motivo = df_rechazadas[df_rechazadas['motivo_label'] == motivo]
            costos = df_motivo['costo_total']
            
            # Calcular estadísticas
            cantidad = len(costos)
            mediana = costos.median()
            promedio = costos.mean()
            minimo = costos.min()
            maximo = costos.max()
            
            fig.add_trace(go.Box(
                y=costos,
                name=motivo,
                marker=dict(color=colores_motivos[idx % len(colores_motivos)]),
                boxmean='sd',  # Muestra media y desviación estándar
                hovertemplate=(
                    f'<b>{motivo}</b><br>'
                    'Costo: $%{y:,.0f}<br>'
                    f'Casos: {cantidad}<br>'
                    f'Mediana: ${mediana:,.0f}<br>'
                    f'Promedio: ${promedio:,.0f}<br>'
                    '<extra></extra>'
                )
            ))
        
        # Calcular estadística global
        costo_mediano_global = df_rechazadas['costo_total'].median()
        
        # Agregar línea de referencia del costo mediano global
        fig.add_hline(
            y=costo_mediano_global,
            line_dash="dash",
            line_color="gray",
            annotation_text=f"Mediana Global: ${costo_mediano_global:,.0f}",
            annotation_position="right"
        )
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='💰 Distribución de Costos por Motivo de Rechazo',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            yaxis=dict(
                title='Costo Total de la Cotización ($)',
                tickformat='$,.0f'
            ),
            xaxis=dict(title='Motivo de Rechazo'),
            showlegend=False,
            height=600
        )
        
        return fig
    
    def grafico_correlacion_tiempo_resultado(self, df):
        """
        Gráfico de dispersión: Correlación entre tiempo de respuesta y resultado.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Este gráfico revela patrones críticos para optimizar seguimiento:
        
        EJES:
        - Eje X: Días transcurridos hasta que el cliente respondió
        - Eje Y: Costo total de la cotización
        
        COLORES:
        - Verde (🟢): Cotizaciones ACEPTADAS
        - Rojo (🔴): Cotizaciones RECHAZADAS
        
        TAMAÑO DE PUNTOS:
        - Más grande = Más piezas cotizadas (cotizaciones complejas)
        - Más pequeño = Pocas piezas (cotizaciones simples)
        
        INSIGHTS CLAVE QUE REVELA:
        ==========================
        1. **Punto de Quiebre Temporal:**
           - ¿A partir de cuántos días sin respuesta aumenta el rechazo?
           - Ejemplo: "Después de 7 días, 80% son rechazadas"
        
        2. **Relación Precio-Urgencia:**
           - ¿Los clientes responden más rápido a cotizaciones caras o baratas?
           - ¿Cotizaciones caras respondidas rápido = cliente muy interesado?
        
        3. **Patrones de Comportamiento:**
           - Verde concentrado abajo-izquierda = "Sweet Spot" (rápido + acepta)
           - Rojo disperso derecha = Respuestas lentas correlacionan con rechazo
           - Puntos grandes rojos = Cotizaciones complejas tienden a rechazarse
        
        4. **Estrategia de Seguimiento:**
           - Define umbrales: "Cotizaciones >$5000 sin respuesta a 3 días → llamar"
           - Prioriza según zona del gráfico donde está cada cotización pendiente
        
        5. **Indicador de Complejidad:**
           - Si puntos grandes (muchas piezas) tardan más en decidir
           - Ayuda a ajustar expectativas de tiempo de respuesta
        
        ACCIONABLE:
        ===========
        - Implementar alertas automáticas basadas en días transcurridos y costo
        - Segmentar estrategia de seguimiento por zona del gráfico
        - Identificar cotizaciones en "zona de riesgo" para acción proactiva
        
        Args:
            df (DataFrame): DataFrame de cotizaciones con respuesta
        
        Returns:
            Figure: Gráfico de dispersión interactivo de Plotly
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay datos de cotizaciones")
        
        # Filtrar solo cotizaciones con respuesta (aceptadas o rechazadas)
        # Usamos 'aceptada' en lugar de 'fecha_respuesta' porque es el campo que indica respuesta
        df_con_respuesta = df[df['aceptada'].notna()].copy()
        
        if df_con_respuesta.empty:
            return self._crear_grafico_vacio("No hay cotizaciones con respuesta del cliente")
        
        # Asegurar que dias_sin_respuesta esté calculado
        if 'dias_sin_respuesta' not in df_con_respuesta.columns:
            # Si existe fecha_respuesta, usarla; sino calcular desde fecha_envio
            if 'fecha_respuesta' in df_con_respuesta.columns:
                df_con_respuesta['dias_sin_respuesta'] = (
                    df_con_respuesta['fecha_respuesta'] - df_con_respuesta['fecha_envio']
                ).dt.days
            else:
                # Si no hay fecha_respuesta, usar fecha actual como referencia
                from datetime import datetime
                df_con_respuesta['dias_sin_respuesta'] = (
                    pd.to_datetime('today') - df_con_respuesta['fecha_envio']
                ).dt.days
        
        # Calcular total de piezas si no existe
        if 'total_piezas' not in df_con_respuesta.columns:
            df_con_respuesta['total_piezas'] = 1  # Default si no hay dato
        
        # Separar por resultado
        df_aceptadas = df_con_respuesta[df_con_respuesta['aceptada'] == True].copy()
        df_rechazadas = df_con_respuesta[df_con_respuesta['aceptada'] == False].copy()
        
        # Crear figura
        fig = go.Figure()
        
        # Trace para ACEPTADAS (Verde)
        if not df_aceptadas.empty:
            fig.add_trace(go.Scatter(
                x=df_aceptadas['dias_sin_respuesta'],
                y=df_aceptadas['costo_total'],
                mode='markers',
                name='Aceptadas',
                marker=dict(
                    color=self.colores['success'],
                    size=df_aceptadas['total_piezas'].clip(lower=5, upper=30),  # Tamaño basado en piezas
                    sizemode='diameter',
                    line=dict(width=1, color='white'),
                    opacity=0.7
                ),
                customdata=df_aceptadas['total_piezas'],  # Pasar valor real de piezas
                hovertemplate=(
                    '<b>✅ ACEPTADA</b><br>'
                    'Días de respuesta: %{x}<br>'
                    'Costo: $%{y:,.0f}<br>'
                    'Piezas: %{customdata}<br>'
                    '<extra></extra>'
                )
            ))
        
        # Trace para RECHAZADAS (Rojo)
        if not df_rechazadas.empty:
            fig.add_trace(go.Scatter(
                x=df_rechazadas['dias_sin_respuesta'],
                y=df_rechazadas['costo_total'],
                mode='markers',
                name='Rechazadas',
                marker=dict(
                    color=self.colores['danger'],
                    size=df_rechazadas['total_piezas'].clip(lower=5, upper=30),
                    sizemode='diameter',
                    line=dict(width=1, color='white'),
                    opacity=0.7
                ),
                customdata=df_rechazadas['total_piezas'],  # Pasar valor real de piezas
                hovertemplate=(
                    '<b>❌ RECHAZADA</b><br>'
                    'Días de respuesta: %{x}<br>'
                    'Costo: $%{y:,.0f}<br>'
                    'Piezas: %{customdata}<br>'
                    '<extra></extra>'
                )
            ))
        
        # Calcular líneas de tendencia si hay suficientes datos
        # IMPORTANTE: Solo calcular si hay variabilidad en los datos
        import numpy as np
        
        if len(df_aceptadas) >= 3:  # Mínimo 3 puntos para una tendencia confiable
            try:
                # Verificar que hay variabilidad en ambos ejes
                x_aceptadas = df_aceptadas['dias_sin_respuesta'].values
                y_aceptadas = df_aceptadas['costo_total'].values
                
                # Solo calcular si hay variación (no todos los valores son iguales)
                if (x_aceptadas.std() > 0) and (y_aceptadas.std() > 0):
                    z = np.polyfit(x_aceptadas, y_aceptadas, 1)
                    p = np.poly1d(z)
                    x_tend = np.linspace(x_aceptadas.min(), x_aceptadas.max(), 50)
                    fig.add_trace(go.Scatter(
                        x=x_tend,
                        y=p(x_tend),
                        mode='lines',
                        name='Tendencia Aceptadas',
                        line=dict(color=self.colores['success'], width=2, dash='dash'),
                        hoverinfo='skip',
                        showlegend=True
                    ))
            except Exception as e:
                # Si falla el cálculo de tendencia, continuar sin ella
                print(f"⚠️ No se pudo calcular tendencia para aceptadas: {str(e)}")
        
        if len(df_rechazadas) >= 3:
            try:
                x_rechazadas = df_rechazadas['dias_sin_respuesta'].values
                y_rechazadas = df_rechazadas['costo_total'].values
                
                if (x_rechazadas.std() > 0) and (y_rechazadas.std() > 0):
                    z = np.polyfit(x_rechazadas, y_rechazadas, 1)
                    p = np.poly1d(z)
                    x_tend = np.linspace(x_rechazadas.min(), x_rechazadas.max(), 50)
                    fig.add_trace(go.Scatter(
                        x=x_tend,
                        y=p(x_tend),
                        mode='lines',
                        name='Tendencia Rechazadas',
                        line=dict(color=self.colores['danger'], width=2, dash='dash'),
                        hoverinfo='skip',
                        showlegend=True
                    ))
            except Exception as e:
                print(f"⚠️ No se pudo calcular tendencia para rechazadas: {str(e)}")
        
        # Calcular estadísticas para anotaciones
        tiempo_promedio_aceptadas = df_aceptadas['dias_sin_respuesta'].mean() if not df_aceptadas.empty else 0
        tiempo_promedio_rechazadas = df_rechazadas['dias_sin_respuesta'].mean() if not df_rechazadas.empty else 0
        
        # Línea vertical de referencia: tiempo promedio global
        tiempo_promedio_global = df_con_respuesta['dias_sin_respuesta'].mean()
        fig.add_vline(
            x=tiempo_promedio_global,
            line_dash="dot",
            line_color="gray",
            annotation_text=f"⏱️ Promedio: {tiempo_promedio_global:.1f} días",
            annotation_position="top"
        )
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='⏱️💰 Correlación: Tiempo de Respuesta vs Costo y Resultado',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(
                title='Días Transcurridos hasta Respuesta del Cliente',
                showgrid=True,
                gridcolor='lightgray',
                gridwidth=0.5
            ),
            yaxis=dict(
                title='Costo Total de la Cotización ($)',
                tickformat='$,.0f',
                showgrid=True,
                gridcolor='lightgray',
                gridwidth=0.5
            ),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            height=600
        )
        
        return fig
    
    def grafico_funnel_conversion(self, df):
        """
        Embudo de conversión: Etapas del proceso de cotización.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Un "funnel" (embudo) muestra cómo se van filtrando las cotizaciones:
        1. Total enviadas (100%)
        2. Con respuesta (X%)
        3. Aceptadas (Y%)
        4. Finalizadas (Z%)
        
        Ayuda a identificar dónde se "pierden" más cotizaciones.
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay datos para embudo")
        
        # Calcular etapas
        total_enviadas = len(df)
        con_respuesta = len(df[df['aceptada'].notna()])
        aceptadas = len(df[df['aceptada'] == True])
        # Necesitamos cruzar con estado de orden para "finalizadas"
        # Por ahora usamos aceptadas como proxy
        finalizadas = aceptadas  # Simplificación
        
        # Calcular tasas de conversión
        tasa_respuesta = (con_respuesta / total_enviadas * 100) if total_enviadas > 0 else 0
        tasa_aceptacion = (aceptadas / con_respuesta * 100) if con_respuesta > 0 else 0
        tasa_finalizacion = (finalizadas / aceptadas * 100) if aceptadas > 0 else 0
        
        # Crear funnel
        fig = go.Figure(go.Funnel(
            y=['Cotizaciones Enviadas', 'Con Respuesta del Cliente', 'Aceptadas', 'Trabajos Finalizados'],
            x=[total_enviadas, con_respuesta, aceptadas, finalizadas],
            textposition='inside',
            textinfo='value+percent initial',
            marker=dict(
                color=[
                    self.colores['primary'],
                    self.colores['info'],
                    self.colores['success'],
                    self.colores['teal']
                ]
            ),
            connector=dict(line=dict(color='lightgray', width=2)),
            hovertemplate='<b>%{y}</b><br>Cantidad: %{x}<br>%{percentInitial}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🎯 Embudo de Conversión de Cotizaciones',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            height=500
        )
        
        return fig
    
    # ========================================================================
    # MACHINE LEARNING (2 funciones)
    # ========================================================================
    
    def grafico_prediccion_ml(self, prob_aceptacion, prob_rechazo):
        """
        Gauge chart: Probabilidad de aceptación predicha por ML.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Un "velocímetro" visual que muestra la probabilidad de que
        una cotización sea aceptada según el modelo de Machine Learning.
        
        - Verde (0-40%): Probabilidad baja
        - Amarillo (40-70%): Probabilidad media
        - Verde (70-100%): Probabilidad alta
        
        Args:
            prob_aceptacion (float): Probabilidad de aceptación (0.0 a 1.0)
            prob_rechazo (float): Probabilidad de rechazo (0.0 a 1.0)
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        # Convertir a porcentaje
        prob_pct = prob_aceptacion * 100
        
        # Determinar color según probabilidad
        if prob_pct >= 70:
            color_gauge = self.colores['success']
            mensaje = 'ALTA probabilidad de aceptación ✅'
        elif prob_pct >= 40:
            color_gauge = self.colores['warning']
            mensaje = 'MEDIA probabilidad de aceptación ⚠️'
        else:
            color_gauge = self.colores['danger']
            mensaje = 'BAJA probabilidad de aceptación ❌'
        
        # Crear gauge
        fig = go.Figure(go.Indicator(
            mode='gauge+number+delta',
            value=prob_pct,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': f'Predicción ML<br><sub>{mensaje}</sub>', 'font': {'size': 20}},
            delta={'reference': 50, 'suffix': '%'},
            gauge={
                'axis': {'range': [0, 100], 'ticksuffix': '%'},
                'bar': {'color': color_gauge},
                'steps': [
                    {'range': [0, 40], 'color': 'rgba(220, 53, 69, 0.2)'},   # Rojo claro
                    {'range': [40, 70], 'color': 'rgba(255, 193, 7, 0.2)'},  # Amarillo claro
                    {'range': [70, 100], 'color': 'rgba(25, 135, 84, 0.2)'}  # Verde claro
                ],
                'threshold': {
                    'line': {'color': 'red', 'width': 4},
                    'thickness': 0.75,
                    'value': 50
                }
            }
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            height=400
        )
        
        return fig
    
    def grafico_factores_influyentes(self, feature_importance, top_n=10):
        """
        Barras horizontales: Factores más influyentes según ML.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Muestra qué variables son más importantes para el modelo ML
        al hacer predicciones. "Feature Importance" = Importancia de cada factor.
        
        Por ejemplo:
        - costo_total: 0.35 → El 35% de la decisión se basa en el costo
        - total_piezas: 0.20 → El 20% se basa en cantidad de piezas
        
        Args:
            feature_importance (list): Lista de dicts con 'feature' e 'importance'
            top_n (int): Número de factores a mostrar
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if not feature_importance:
            return self._crear_grafico_vacio("No hay datos de feature importance")
        
        # Convertir a DataFrame y tomar top N
        df_fi = pd.DataFrame(feature_importance).head(top_n)
        
        # Nombres más legibles
        nombres_legibles = {
            'costo_total': 'Costo Total',
            'costo_mano_obra': 'Mano de Obra',
            'total_piezas': 'Cantidad de Piezas',
            'piezas_necesarias': 'Piezas Necesarias',
            'porcentaje_necesarias': '% Piezas Necesarias',
            'ticket_por_pieza': 'Costo por Pieza',
            'porcentaje_mano_obra': '% Mano de Obra',
            'tiene_descuento': 'Tiene Descuento',
            'dia_semana': 'Día de la Semana',
            'mes_envio': 'Mes del Año',
            'gama_encoded': 'Gama del Equipo',
            'tipo_equipo_encoded': 'Tipo de Equipo'
        }
        
        df_fi['feature_legible'] = df_fi['feature'].map(
            lambda x: nombres_legibles.get(x, x.replace('_', ' ').title())
        )
        
        # Crear gráfico
        fig = go.Figure(go.Bar(
            y=df_fi['feature_legible'],
            x=df_fi['importance'] * 100,  # Convertir a porcentaje
            orientation='h',
            marker=dict(
                color=df_fi['importance'],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Importancia")
            ),
            text=df_fi['importance'].apply(lambda x: f'{x*100:.1f}%'),
            textposition='auto',
            hovertemplate='<b>%{y}</b><br>Importancia: %{x:.2f}%<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🧠 Factores Más Influyentes en Aceptación (ML)',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Importancia (%)', range=[0, max(df_fi['importance']) * 100 * 1.1]),
            yaxis=dict(title=''),
            height=max(400, len(df_fi) * 50)
        )
        
        return fig
    
    # ========================================================================
    # TABLAS INTERACTIVAS (2 funciones)
    # ========================================================================
    
    def generar_tabla_kpis(self, kpis):
        """
        Tabla HTML: KPIs principales con formato profesional.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Genera una tabla Bootstrap con los KPIs principales formateados
        con colores, iconos y formato de moneda.
        
        Args:
            kpis (dict): Diccionario de KPIs (generado por calcular_kpis_generales)
        
        Returns:
            go.Figure: Tabla de Plotly
        """
        
        # Preparar datos de la tabla
        filas = [
            ['📊 Total Cotizaciones', kpis.get('total_cotizaciones', 0), ''],
            ['✅ Aceptadas', kpis.get('aceptadas', 0), f"{kpis.get('tasa_aceptacion', 0):.1f}%"],
            ['❌ Rechazadas', kpis.get('rechazadas', 0), f"{kpis.get('tasa_rechazo', 0):.1f}%"],
            ['⏳ Pendientes', kpis.get('pendientes', 0), f"{kpis.get('tasa_pendiente', 0):.1f}%"],
            ['💰 Valor Total', '', kpis.get('valor_total_cotizado_fmt', '$0')],
            ['✅ Valor Aceptado', '', kpis.get('valor_aceptado_fmt', '$0')],
            ['❌ Valor Rechazado', '', kpis.get('valor_rechazado_fmt', '$0')],
            ['📈 Ticket Promedio', '', kpis.get('ticket_promedio_fmt', '$0')],
            ['⏱️ Tiempo Respuesta Promedio', f"{kpis.get('tiempo_respuesta_promedio', 0):.1f} días", ''],
        ]
        
        # Crear tabla con Plotly
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Métrica</b>', '<b>Cantidad</b>', '<b>Porcentaje/Valor</b>'],
                fill_color=self.colores['primary'],
                align='left',
                font=dict(color='white', size=14)
            ),
            cells=dict(
                values=list(zip(*filas)),  # Transponer filas a columnas
                fill_color='white',
                align=['left', 'right', 'right'],
                font=dict(size=12),
                height=30
            )
        )])
        
        fig.update_layout(
            title=dict(
                text='📊 Resumen de KPIs Principales',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            height=400,
            margin=dict(l=20, r=20, t=60, b=20)
        )
        
        return fig
    
    def generar_tabla_detalle_cotizaciones(self, df, limite=50):
        """
        Tabla HTML: Detalle de cotizaciones con paginación.
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
            limite (int): Número máximo de filas a mostrar
        
        Returns:
            go.Figure: Tabla de Plotly
        """
        
        if df.empty:
            return self._crear_grafico_vacio("No hay cotizaciones para mostrar")
        
        # Limitar filas
        df_tabla = df.head(limite).copy()
        
        # Formatear columnas
        df_tabla['fecha_fmt'] = pd.to_datetime(df_tabla['fecha_envio']).dt.strftime('%d/%m/%Y')
        df_tabla['costo_fmt'] = df_tabla['costo_total'].apply(lambda x: f'${x:,.2f}')
        df_tabla['estado_texto'] = df_tabla['aceptada'].map({
            True: '✅ Aceptada',
            False: '❌ Rechazada',
            None: '⏳ Pendiente'
        })
        
        # Seleccionar columnas
        columnas = [
            ('numero_orden', 'Orden'),
            ('fecha_fmt', 'Fecha'),
            ('sucursal', 'Sucursal'),
            ('tecnico', 'Técnico'),
            ('gama', 'Gama'),
            ('costo_fmt', 'Costo Total'),
            ('total_piezas', 'Piezas'),
            ('estado_texto', 'Estado')
        ]
        
        # Preparar valores
        header_values = [f'<b>{col[1]}</b>' for col in columnas]
        cell_values = [df_tabla[col[0]].tolist() for col in columnas]
        
        # Crear tabla
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=header_values,
                fill_color=self.colores['primary'],
                align='left',
                font=dict(color='white', size=12)
            ),
            cells=dict(
                values=cell_values,
                fill_color='white',
                align=['left'] * len(columnas),
                font=dict(size=11),
                height=25
            )
        )])
        
        fig.update_layout(
            title=dict(
                text=f'📋 Detalle de Cotizaciones (mostrando {len(df_tabla)} de {len(df)})',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            height=600,
            margin=dict(l=20, r=20, t=60, b=20)
        )
        
        return fig
    
    # ========================================================================
    # ANÁLISIS POR RESPONSABLE DE SEGUIMIENTO (4 funciones)
    # ========================================================================
    
    def grafico_ranking_responsables(self, df_metricas):
        """
        Barras horizontales: Ranking de responsables por total de cotizaciones.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Muestra quiénes son los responsables más activos en enviar cotizaciones,
        con barras coloreadas según su tasa de aceptación.
        
        Args:
            df_metricas (DataFrame): DataFrame con métricas por responsable
                                    (generado por calcular_metricas_por_responsable)
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_metricas.empty:
            return self._crear_grafico_vacio("No hay métricas de responsables")
        
        # Tomar top 10
        top_10 = df_metricas.head(10).copy()
        
        # Crear gráfico de barras horizontales
        fig = go.Figure(go.Bar(
            y=top_10['responsable'][::-1],  # Invertir para que el top esté arriba
            x=top_10['total'][::-1],
            orientation='h',
            marker=dict(
                color=top_10['tasa_aceptacion'][::-1],
                colorscale=[
                    [0, self.colores['danger']],
                    [0.5, self.colores['warning']],
                    [1, self.colores['success']]
                ],
                showscale=True,
                colorbar=dict(title="Tasa %")
            ),
            text=top_10['total'][::-1].apply(lambda x: f'{x}'),
            textposition='auto',
            hovertemplate=(
                '<b>%{y}</b><br>'
                'Total: %{x} cotizaciones<br>'
                'Aceptadas: %{customdata[0]}<br>'
                'Rechazadas: %{customdata[1]}<br>'
                'Pendientes: %{customdata[2]}<br>'
                'Tasa aceptación: %{customdata[3]:.1f}%'
                '<extra></extra>'
            ),
            customdata=top_10[['aceptadas', 'rechazadas', 'pendientes', 'tasa_aceptacion']][::-1].values
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🏆 Top 10 Responsables por Volumen de Cotizaciones',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Total de Cotizaciones'),
            yaxis=dict(title=''),
            height=500
        )
        
        return fig
    
    def grafico_tasas_aceptacion_responsables(self, df_metricas):
        """
        Barras agrupadas: Aceptadas vs Rechazadas por responsable.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Muestra la distribución de resultados (aceptadas/rechazadas/pendientes)
        para cada responsable, permitiendo comparar su efectividad.
        
        Args:
            df_metricas (DataFrame): DataFrame con métricas por responsable
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_metricas.empty:
            return self._crear_grafico_vacio("No hay métricas de responsables")
        
        # Tomar top 8 para mejor visualización
        top_8 = df_metricas.head(8).copy()
        
        # Crear gráfico de barras agrupadas
        fig = go.Figure()
        
        # Barras de aceptadas
        fig.add_trace(go.Bar(
            name='Aceptadas',
            x=top_8['responsable'],
            y=top_8['aceptadas'],
            marker_color=self.colores['success'],
            text=top_8['aceptadas'],
            textposition='auto',
            hovertemplate='<b>Aceptadas</b><br>%{x}<br>Cantidad: %{y}<extra></extra>'
        ))
        
        # Barras de rechazadas
        fig.add_trace(go.Bar(
            name='Rechazadas',
            x=top_8['responsable'],
            y=top_8['rechazadas'],
            marker_color=self.colores['danger'],
            text=top_8['rechazadas'],
            textposition='auto',
            hovertemplate='<b>Rechazadas</b><br>%{x}<br>Cantidad: %{y}<extra></extra>'
        ))
        
        # Barras de pendientes
        fig.add_trace(go.Bar(
            name='Pendientes',
            x=top_8['responsable'],
            y=top_8['pendientes'],
            marker_color=self.colores['warning'],
            text=top_8['pendientes'],
            textposition='auto',
            hovertemplate='<b>Pendientes</b><br>%{x}<br>Cantidad: %{y}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='📊 Distribución de Resultados por Responsable',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            barmode='group',
            xaxis=dict(title='Responsable', tickangle=-45),
            yaxis=dict(title='Cantidad de Cotizaciones'),
            height=500,
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        )
        
        return fig
    
    def grafico_valor_generado_responsables(self, df_metricas):
        """
        Barras comparativas: Valor cotizado vs Valor real generado.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Compara el valor TOTAL cotizado (potencial) con el valor REAL aceptado
        (ingresos confirmados) para cada responsable.
        
        Args:
            df_metricas (DataFrame): DataFrame con métricas por responsable
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_metricas.empty:
            return self._crear_grafico_vacio("No hay métricas de responsables")
        
        # Tomar top 8 por valor aceptado
        top_8 = df_metricas.nlargest(8, 'valor_aceptado').copy()
        
        # Crear gráfico de barras agrupadas
        fig = go.Figure()
        
        # Barras de valor cotizado (potencial)
        fig.add_trace(go.Bar(
            name='Valor Cotizado',
            x=top_8['responsable'],
            y=top_8['valor_cotizado'],
            marker_color=self.colores['info'],
            text=top_8['valor_cotizado'].apply(lambda x: f'${x:,.0f}'),
            textposition='auto',
            hovertemplate='<b>Valor Cotizado</b><br>%{x}<br>$%{y:,.2f}<extra></extra>'
        ))
        
        # Barras de valor aceptado (real)
        fig.add_trace(go.Bar(
            name='Ingresos Reales',
            x=top_8['responsable'],
            y=top_8['valor_aceptado'],
            marker_color=self.colores['success'],
            text=top_8['valor_aceptado'].apply(lambda x: f'${x:,.0f}'),
            textposition='auto',
            hovertemplate='<b>Ingresos Reales</b><br>%{x}<br>$%{y:,.2f}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='💰 Valor Generado por Responsable',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            barmode='group',
            xaxis=dict(title='Responsable', tickangle=-45),
            yaxis=dict(title='Valor ($)', tickformat='$,.0f'),
            height=500,
            showlegend=True,
            legend=dict(
                orientation='h',
                yanchor='bottom',
                y=1.02,
                xanchor='right',
                x=1
            )
        )
        
        return fig
    
    def grafico_piezas_promedio_responsables(self, df_metricas):
        """
        Gráfico de dispersión: Piezas promedio vs Tasa de aceptación.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Analiza la relación entre cantidad de piezas ofrecidas y tasa de aceptación.
        ¿Ofrecer más piezas aumenta o disminuye la tasa de aceptación?
        
        Args:
            df_metricas (DataFrame): DataFrame con métricas por responsable
        
        Returns:
            Figure: Gráfico de Plotly
        """
        
        if df_metricas.empty:
            return self._crear_grafico_vacio("No hay métricas de responsables")
        
        # Crear scatter plot
        fig = go.Figure(go.Scatter(
            x=df_metricas['piezas_promedio'],
            y=df_metricas['tasa_aceptacion'],
            mode='markers+text',
            marker=dict(
                size=df_metricas['total'],  # Tamaño según total cotizaciones
                sizemode='diameter',
                sizeref=df_metricas['total'].max() / 40,
                color=df_metricas['valor_aceptado'],
                colorscale='Viridis',
                showscale=True,
                colorbar=dict(title="Valor<br>Generado"),
                line=dict(width=2, color='white')
            ),
            text=df_metricas['responsable'],
            textposition='top center',
            textfont=dict(size=10),
            hovertemplate=(
                '<b>%{text}</b><br>'
                'Piezas promedio: %{x:.1f}<br>'
                'Tasa aceptación: %{y:.1f}%<br>'
                'Total cotizaciones: %{marker.size}<br>'
                'Valor generado: $%{marker.color:,.0f}'
                '<extra></extra>'
            )
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🔧 Relación: Piezas Promedio vs Tasa de Aceptación',
                x=0.5,
                xanchor='center',
                font=dict(size=18, color=self.colores['dark'])
            ),
            xaxis=dict(title='Piezas Promedio por Cotización'),
            yaxis=dict(title='Tasa de Aceptación (%)', range=[0, 100]),
            height=600,
            annotations=[
                dict(
                    text='<i>Tamaño de la burbuja = Total de cotizaciones</i>',
                    xref='paper',
                    yref='paper',
                    x=0.5,
                    y=-0.15,
                    xanchor='center',
                    yanchor='top',
                    showarrow=False,
                    font=dict(size=12, color='gray')
                )
            ]
        )
        
        return fig
    
    # ========================================================================
    # FUNCIÓN ORQUESTADORA PRINCIPAL
    # ========================================================================
    
    def crear_dashboard_completo(self, df, df_piezas=None, df_seguimientos=None,
                                 df_metricas_tecnicos=None, df_metricas_sucursales=None,
                                 df_metricas_responsables=None,
                                 kpis=None, ml_predictor=None, periodo='M'):
        """
        Genera TODOS los gráficos del dashboard en un solo llamado.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Esta es la función "maestra" que genera todo el dashboard completo.
        Llama a todas las funciones individuales y retorna un diccionario
        con todos los HTMLs de gráficos listos para insertar en el template.
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
            df_piezas (DataFrame): DataFrame de piezas cotizadas
            df_seguimientos (DataFrame): DataFrame de seguimientos
            df_metricas_tecnicos (DataFrame): Métricas por técnico
            df_metricas_sucursales (DataFrame): Métricas por sucursal
            kpis (dict): Diccionario de KPIs
            ml_predictor (PredictorAceptacionCotizacion): Modelo ML entrenado
            periodo (str): Período para gráfico temporal
        
        Returns:
            dict: Diccionario con todos los HTMLs de gráficos
        
        Ejemplo de uso en views.py:
            visualizer = DashboardCotizacionesVisualizer()
            graficos = visualizer.crear_dashboard_completo(
                df=df_cotizaciones,
                df_piezas=df_piezas,
                kpis=kpis,
                periodo='M'
            )
            
            # En template:
            {{ graficos.evolucion_temporal|safe }}
        """
        
        graficos = {}
        
        try:
            # GRÁFICOS TEMPORALES
            graficos['evolucion_temporal'] = convertir_figura_a_html(
                self.grafico_evolucion_cotizaciones(df, periodo)
            )
            
            # GRÁFICOS DE DISTRIBUCIÓN
            graficos['tasas_aceptacion_sucursal'] = convertir_figura_a_html(
                self.grafico_tasas_aceptacion(df, 'sucursal')
            )
            graficos['tasas_aceptacion_tecnico'] = convertir_figura_a_html(
                self.grafico_tasas_aceptacion(df, 'tecnico')
            )
            graficos['distribucion_costos'] = convertir_figura_a_html(
                self.grafico_distribucion_costos(df)
            )
            graficos['gamas_equipos'] = convertir_figura_a_html(
                self.grafico_gamas_equipos(df)
            )
            
            # ANÁLISIS DE PIEZAS
            if df_piezas is not None and not df_piezas.empty:
                graficos['top_piezas_rechazadas'] = convertir_figura_a_html(
                    self.grafico_top_piezas_rechazadas(df_piezas)
                )
                graficos['top_piezas_aceptadas'] = convertir_figura_a_html(
                    self.grafico_top_piezas_aceptadas(df_piezas)
                )
                graficos['sugerencias_tecnico'] = convertir_figura_a_html(
                    self.grafico_sugerencias_tecnico(df_piezas)
                )
                graficos['piezas_necesarias_vs_opcionales'] = convertir_figura_a_html(
                    self.grafico_piezas_necesarias_vs_opcionales(df_piezas)
                )
            
            # RENDIMIENTO DE TÉCNICOS
            if df_metricas_tecnicos is not None and not df_metricas_tecnicos.empty:
                graficos['rendimiento_tecnicos'] = convertir_figura_a_html(
                    self.grafico_rendimiento_tecnicos(df)
                )
                graficos['ranking_tecnicos'] = convertir_figura_a_html(
                    self.grafico_ranking_tecnicos(df_metricas_tecnicos)
                )
            
            # ANÁLISIS POR SUCURSAL
            if df_metricas_sucursales is not None and not df_metricas_sucursales.empty:
                graficos['rendimiento_sucursales'] = convertir_figura_a_html(
                    self.grafico_rendimiento_sucursales(df_metricas_sucursales)
                )
                graficos['distribucion_sucursales'] = convertir_figura_a_html(
                    self.grafico_distribucion_sucursales(df_metricas_sucursales)
                )
            
            # ANÁLISIS POR RESPONSABLE DE SEGUIMIENTO
            if df_metricas_responsables is not None and not df_metricas_responsables.empty:
                graficos['ranking_responsables'] = convertir_figura_a_html(
                    self.grafico_ranking_responsables(df_metricas_responsables)
                )
                graficos['tasas_aceptacion_responsables'] = convertir_figura_a_html(
                    self.grafico_tasas_aceptacion_responsables(df_metricas_responsables)
                )
                graficos['valor_generado_responsables'] = convertir_figura_a_html(
                    self.grafico_valor_generado_responsables(df_metricas_responsables)
                )
                graficos['piezas_promedio_responsables'] = convertir_figura_a_html(
                    self.grafico_piezas_promedio_responsables(df_metricas_responsables)
                )
            
            # PROVEEDORES
            if df_seguimientos is not None and not df_seguimientos.empty:
                graficos['proveedores_performance'] = convertir_figura_a_html(
                    self.grafico_proveedores_performance(df_seguimientos)
                )
                graficos['top_proveedores'] = convertir_figura_a_html(
                    self.grafico_top_proveedores(df_seguimientos)
                )
                
                # NUEVOS GRÁFICOS DE PROVEEDORES (Noviembre 2025)
                try:
                    # Importar funciones de análisis avanzado
                    from servicio_tecnico.utils_cotizaciones import (
                        analizar_proveedores_con_conversion,
                        analizar_componentes_por_proveedor
                    )
                    
                    # Obtener IDs de cotizaciones del DataFrame actual
                    if 'cotizacion_id' in df.columns:
                        cotizacion_ids = df['cotizacion_id'].dropna().unique().tolist()
                    else:
                        cotizacion_ids = None
                    
                    # Gráfico 1: Impacto de proveedores en conversión
                    try:
                        df_prov_conversion = analizar_proveedores_con_conversion(cotizacion_ids)
                        if not df_prov_conversion.empty:
                            graficos['proveedores_impacto_conversion'] = convertir_figura_a_html(
                                self.grafico_proveedores_impacto_conversion(df_prov_conversion)
                            )
                    except Exception as e:
                        print(f"Error generando gráfico de impacto de proveedores: {e}")
                        graficos['proveedores_impacto_conversion'] = None
                    
                    # Gráfico 2: Componentes por proveedor (Sunburst)
                    try:
                        df_componentes = analizar_componentes_por_proveedor(cotizacion_ids)
                        if not df_componentes.empty:
                            graficos['componentes_por_proveedor'] = convertir_figura_a_html(
                                self.grafico_componentes_por_proveedor(df_componentes)
                            )
                    except Exception as e:
                        print(f"Error generando gráfico de componentes por proveedor: {e}")
                        graficos['componentes_por_proveedor'] = None
                        
                except Exception as e:
                    print(f"Error en importación de funciones de análisis avanzado: {e}")
                    graficos['proveedores_impacto_conversion'] = None
                    graficos['componentes_por_proveedor'] = None
            
            # TIEMPOS Y EFICIENCIA
            graficos['tiempos_respuesta'] = convertir_figura_a_html(
                self.grafico_tiempos_respuesta(df)
            )
            graficos['motivos_rechazo'] = convertir_figura_a_html(
                self.grafico_motivos_rechazo(df)
            )
            graficos['motivos_rechazo_vs_costos'] = convertir_figura_a_html(
                self.grafico_motivos_rechazo_vs_costos(df)
            )
            # NUEVO: Correlación tiempo de respuesta vs resultado
            graficos['correlacion_tiempo_resultado'] = convertir_figura_a_html(
                self.grafico_correlacion_tiempo_resultado(df)
            )
            graficos['funnel_conversion'] = convertir_figura_a_html(
                self.grafico_funnel_conversion(df)
            )
            
            # MACHINE LEARNING
            if ml_predictor and ml_predictor.is_trained:
                # Obtener feature importance
                feature_importance = ml_predictor.obtener_factores_influyentes()
                graficos['factores_influyentes'] = convertir_figura_a_html(
                    self.grafico_factores_influyentes(feature_importance)
                )
                
                # Predicción de ejemplo (última cotización pendiente)
                df_pendientes = df[df['aceptada'].isna()]
                if not df_pendientes.empty:
                    # Tomar última pendiente
                    ultima = df_pendientes.iloc[-1]
                    features = {
                        'costo_total': ultima['costo_total'],
                        'total_piezas': ultima['total_piezas'],
                        'gama': ultima['gama'],
                        'descontar_mano_obra': ultima['descontar_mano_obra'],
                        # ... agregar más features según necesidad
                    }
                    prob_rechazo, prob_aceptacion = ml_predictor.predecir_probabilidad(features)
                    graficos['prediccion_ml'] = convertir_figura_a_html(
                        self.grafico_prediccion_ml(prob_aceptacion, prob_rechazo)
                    )
            
            # TABLAS
            if kpis:
                graficos['tabla_kpis'] = convertir_figura_a_html(
                    self.generar_tabla_kpis(kpis)
                )
            
            graficos['tabla_detalle'] = convertir_figura_a_html(
                self.generar_tabla_detalle_cotizaciones(df)
            )
            
            # ================================================================
            # ANÁLISIS DE ACEPTACIONES + VENTA MOSTRADOR
            # ================================================================
            # EXPLICACIÓN PARA PRINCIPIANTES:
            # Estos gráficos muestran información específica de cotizaciones
            # aceptadas, incluyendo servicios VM, paquetes, seguimientos, etc.
            
            try:
                # Gráficos que usan directamente el DataFrame
                graficos['evolucion_aceptaciones'] = convertir_figura_a_html(
                    self.grafico_evolucion_aceptaciones(df, periodo)
                )
                graficos['aceptacion_parcial_vs_total'] = convertir_figura_a_html(
                    self.grafico_aceptacion_parcial_vs_total(df)
                )
                graficos['valor_aceptado_vs_cotizado'] = convertir_figura_a_html(
                    self.grafico_valor_aceptado_vs_cotizado(df)
                )
                graficos['descuento_mano_obra'] = convertir_figura_a_html(
                    self.grafico_descuento_mano_obra(df)
                )
                graficos['valor_combinado'] = convertir_figura_a_html(
                    self.grafico_valor_combinado(df)
                )
                graficos['tasa_upsell'] = convertir_figura_a_html(
                    self.grafico_tasa_upsell(df)
                )
                
                # Gráficos que usan análisis de VM (requiere funciones de utils)
                from servicio_tecnico.utils_cotizaciones import (
                    analizar_servicios_vm_aceptadas,
                    analizar_seguimiento_piezas_aceptadas,
                )
                
                analisis_vm = analizar_servicios_vm_aceptadas(df)
                if analisis_vm.get('tiene_datos'):
                    graficos['servicios_vm_distribucion'] = convertir_figura_a_html(
                        self.grafico_servicios_vm_distribucion(analisis_vm)
                    )
                    graficos['paquetes_vm_vendidos'] = convertir_figura_a_html(
                        self.grafico_paquetes_vm_vendidos(analisis_vm)
                    )
                    graficos['top_piezas_vm_aceptadas'] = convertir_figura_a_html(
                        self.grafico_top_piezas_vm_aceptadas(analisis_vm)
                    )
                    graficos['combinaciones_servicios'] = convertir_figura_a_html(
                        self.grafico_combinaciones_servicios(analisis_vm)
                    )
                
                analisis_seguimiento = analizar_seguimiento_piezas_aceptadas(df)
                if analisis_seguimiento.get('tiene_datos'):
                    graficos['seguimiento_piezas_estado'] = convertir_figura_a_html(
                        self.grafico_seguimiento_piezas_estado(analisis_seguimiento)
                    )
                    graficos['tiempos_entrega_proveedor'] = convertir_figura_a_html(
                        self.grafico_tiempos_entrega_proveedor(analisis_seguimiento)
                    )
                    
            except Exception as e:
                print(f"Error generando gráficos de aceptaciones: {e}")
            
        except Exception as e:
            print(f"⚠️ Error generando gráfico: {str(e)}")
            # Continuar con el resto de gráficos
        
        return graficos
    
    # ========================================================================
    # VISUALIZACIONES DE ANÁLISIS DE ACEPTACIONES
    # ========================================================================
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Estos métodos generan gráficos enfocados exclusivamente en cotizaciones
    # aceptadas, incluyendo datos cruzados con VentaMostrador (servicios
    # adicionales como limpieza, reinstalación, paquetes, etc.)
    
    def grafico_evolucion_aceptaciones(self, df, periodo='M'):
        """
        Gráfico de líneas: Evolución temporal de aceptaciones
        (total, parcial, con VentaMostrador).
        """
        if df.empty or len(df[df['aceptada'] == True]) == 0:
            return self._crear_grafico_vacio("Sin cotizaciones aceptadas")
        
        df_aceptadas = df[df['aceptada'] == True].copy()
        
        # Clasificar tipos de aceptación
        df_aceptadas['tipo_aceptacion'] = df_aceptadas.apply(
            lambda row: 'Con VM' if row.get('tiene_venta_mostrador', False)
            else ('Parcial' if row.get('piezas_rechazadas', 0) > 0 else 'Total'),
            axis=1
        )
        
        freq_map = {'D': 'D', 'W': 'W', 'M': 'MS', 'Q': 'QS', 'Y': 'YS'}
        freq = freq_map.get(periodo, 'MS')
        
        fig = go.Figure()
        
        colores_tipo = {
            'Total': self.colores['success'],
            'Parcial': self.colores['warning'],
            'Con VM': self.colores['info'],
        }
        
        for tipo, color in colores_tipo.items():
            df_tipo = df_aceptadas[df_aceptadas['tipo_aceptacion'] == tipo]
            if len(df_tipo) > 0:
                agrupado = df_tipo.set_index('fecha_envio').resample(freq).size()
                fig.add_trace(go.Scatter(
                    x=agrupado.index,
                    y=agrupado.values,
                    mode='lines+markers',
                    name=tipo,
                    line=dict(color=color, width=2),
                    marker=dict(size=6),
                    hovertemplate='%{x|%b %Y}<br>%{y} cotizaciones<extra>' + tipo + '</extra>'
                ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Evolución de Aceptaciones', font=dict(size=16)),
            xaxis_title='Período',
            yaxis_title='Cotizaciones Aceptadas',
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            height=400,
        )
        
        return fig
    
    def grafico_aceptacion_parcial_vs_total(self, df):
        """
        Gráfico de dona: Proporción de aceptación total vs parcial.
        """
        if df.empty or len(df[df['aceptada'] == True]) == 0:
            return self._crear_grafico_vacio("Sin cotizaciones aceptadas")
        
        df_aceptadas = df[df['aceptada'] == True]
        
        parcial = len(df_aceptadas[(df_aceptadas['piezas_rechazadas'] > 0) & (df_aceptadas['piezas_aceptadas'] > 0)])
        total = len(df_aceptadas) - parcial
        
        labels = ['Aceptación Total', 'Aceptación Parcial']
        values = [total, parcial]
        colors = [self.colores['success'], self.colores['warning']]
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.5,
            marker_colors=colors,
            textinfo='label+percent+value',
            textfont_size=12,
            hovertemplate='%{label}<br>%{value} cotizaciones (%{percent})<extra></extra>'
        )])
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Aceptación Total vs Parcial', font=dict(size=16)),
            height=400,
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
        )
        
        return fig
    
    def grafico_valor_aceptado_vs_cotizado(self, df):
        """
        Gráfico de barras agrupadas: Valor original cotizado vs valor aceptado
        por sucursal.
        """
        if df.empty or len(df[df['aceptada'] == True]) == 0:
            return self._crear_grafico_vacio("Sin cotizaciones aceptadas")
        
        df_aceptadas = df[df['aceptada'] == True]
        
        por_sucursal = df_aceptadas.groupby('sucursal').agg(
            valor_cotizado=('costo_total', 'sum'),
            valor_aceptado=('costo_total_final', 'sum'),
        ).reset_index().sort_values('valor_cotizado', ascending=False).head(10)
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Valor Cotizado Original',
            x=por_sucursal['sucursal'],
            y=por_sucursal['valor_cotizado'],
            marker_color=self.colores['primary'],
            text=[f"${v:,.0f}" for v in por_sucursal['valor_cotizado']],
            textposition='outside',
            hovertemplate='%{x}<br>Cotizado: $%{y:,.2f}<extra></extra>'
        ))
        
        fig.add_trace(go.Bar(
            name='Valor Aceptado Final',
            x=por_sucursal['sucursal'],
            y=por_sucursal['valor_aceptado'],
            marker_color=self.colores['success'],
            text=[f"${v:,.0f}" for v in por_sucursal['valor_aceptado']],
            textposition='outside',
            hovertemplate='%{x}<br>Aceptado: $%{y:,.2f}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Valor Cotizado vs Aceptado por Sucursal', font=dict(size=16)),
            barmode='group',
            xaxis_title='Sucursal',
            yaxis_title='Monto ($)',
            height=450,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        )
        
        return fig
    
    def grafico_descuento_mano_obra(self, df):
        """
        Gráfico de barras horizontales: Impacto del descuento de mano de obra
        en la decisión de aceptar.
        """
        if df.empty or len(df[df['aceptada'] == True]) == 0:
            return self._crear_grafico_vacio("Sin cotizaciones aceptadas")
        
        df_aceptadas = df[df['aceptada'] == True]
        
        con_descuento = len(df_aceptadas[df_aceptadas['descontar_mano_obra'] == True])
        sin_descuento = len(df_aceptadas[df_aceptadas['descontar_mano_obra'] == False])
        
        monto_descontado = df_aceptadas[df_aceptadas['descontar_mano_obra'] == True]['monto_descuento'].sum()
        ticket_con = df_aceptadas[df_aceptadas['descontar_mano_obra'] == True]['costo_total_final'].mean()
        ticket_sin = df_aceptadas[df_aceptadas['descontar_mano_obra'] == False]['costo_total_final'].mean()
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Cantidad de Aceptaciones', 'Ticket Promedio'),
            column_widths=[0.5, 0.5],
        )
        
        # Panel izquierdo: cantidades
        fig.add_trace(go.Bar(
            y=['Con Descuento', 'Sin Descuento'],
            x=[con_descuento, sin_descuento],
            orientation='h',
            marker_color=[self.colores['teal'], self.colores['secondary']],
            text=[f'{con_descuento} ({con_descuento/(con_descuento+sin_descuento)*100:.0f}%)' if (con_descuento+sin_descuento) > 0 else '0',
                  f'{sin_descuento} ({sin_descuento/(con_descuento+sin_descuento)*100:.0f}%)' if (con_descuento+sin_descuento) > 0 else '0'],
            textposition='inside',
            hovertemplate='%{y}: %{x} cotizaciones<extra></extra>',
            showlegend=False,
        ), row=1, col=1)
        
        # Panel derecho: ticket promedio
        fig.add_trace(go.Bar(
            y=['Con Descuento', 'Sin Descuento'],
            x=[ticket_con if not pd.isna(ticket_con) else 0,
               ticket_sin if not pd.isna(ticket_sin) else 0],
            orientation='h',
            marker_color=[self.colores['teal'], self.colores['secondary']],
            text=[f"${ticket_con:,.0f}" if not pd.isna(ticket_con) else "$0",
                  f"${ticket_sin:,.0f}" if not pd.isna(ticket_sin) else "$0"],
            textposition='inside',
            hovertemplate='%{y}: $%{x:,.2f}<extra></extra>',
            showlegend=False,
        ), row=1, col=2)
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text=f'Impacto del Descuento de Mano de Obra (Total descontado: ${monto_descontado:,.2f})',
                font=dict(size=16)
            ),
            height=350,
        )
        
        return fig
    
    def grafico_servicios_vm_distribucion(self, analisis_vm):
        """
        Gráfico de barras: Distribución de servicios VM en cotizaciones aceptadas.
        Recibe el resultado de analizar_servicios_vm_aceptadas().
        """
        if not analisis_vm or not analisis_vm.get('tiene_datos'):
            return self._crear_grafico_vacio("Sin ventas mostrador en aceptadas")
        
        servicios = analisis_vm['distribucion_servicios']
        if not servicios:
            return self._crear_grafico_vacio("Sin servicios registrados")
        
        nombres = [s['servicio'] for s in servicios]
        cantidades = [s['cantidad'] for s in servicios]
        ingresos = [s['ingreso_total'] for s in servicios]
        
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Frecuencia de Servicios', 'Ingreso por Servicio'),
            column_widths=[0.5, 0.5],
            specs=[[{"type": "bar"}, {"type": "bar"}]]
        )
        
        colores_servicios = [
            self.colores['info'],
            self.colores['primary'],
            self.colores['teal'],
            self.colores['purple'],
            self.colores['orange'],
        ]
        
        fig.add_trace(go.Bar(
            y=nombres,
            x=cantidades,
            orientation='h',
            marker_color=colores_servicios[:len(nombres)],
            text=[f'{c} ventas' for c in cantidades],
            textposition='auto',
            hovertemplate='%{y}: %{x} ventas<extra></extra>',
            showlegend=False,
        ), row=1, col=1)
        
        fig.add_trace(go.Bar(
            y=nombres,
            x=ingresos,
            orientation='h',
            marker_color=colores_servicios[:len(nombres)],
            text=[f'${i:,.0f}' for i in ingresos],
            textposition='auto',
            hovertemplate='%{y}: $%{x:,.2f}<extra></extra>',
            showlegend=False,
        ), row=1, col=2)
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Servicios de Venta Mostrador en Aceptadas', font=dict(size=16)),
            height=400,
        )
        fig.update_layout(margin=dict(l=160, r=50, t=80, b=50))
        
        return fig
    
    def grafico_paquetes_vm_vendidos(self, analisis_vm):
        """
        Gráfico de dona: Distribución de paquetes (premium/oro/plata) vendidos
        en cotizaciones aceptadas con VentaMostrador.
        """
        if not analisis_vm or not analisis_vm.get('tiene_datos'):
            return self._crear_grafico_vacio("Sin ventas mostrador en aceptadas")
        
        paquetes = analisis_vm['distribucion_paquetes']
        if not paquetes:
            return self._crear_grafico_vacio("Sin datos de paquetes")
        
        # Filtrar paquetes con cantidad > 0
        paquetes = [p for p in paquetes if p['cantidad'] > 0]
        if not paquetes:
            return self._crear_grafico_vacio("Sin paquetes vendidos")
        
        labels = [p['nombre'] for p in paquetes]
        values = [p['cantidad'] for p in paquetes]
        ingresos = [p['ingreso_total'] for p in paquetes]
        
        colores_paquetes = {
            'premium': '#FFD700',     # Dorado
            'oro': '#FFA500',         # Naranja
            'plata': '#C0C0C0',       # Plateado
            'ninguno': self.colores['secondary'],
        }
        colors = [colores_paquetes.get(p['paquete'], self.colores['info']) for p in paquetes]
        
        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.45,
            marker_colors=colors,
            textinfo='label+percent+value',
            textfont_size=11,
            hovertemplate='%{label}<br>%{value} ventas (%{percent})<br>Ingreso: $' + 
                          '<extra></extra>',
            customdata=ingresos,
        )])
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Distribución de Paquetes VM', font=dict(size=16)),
            height=400,
            showlegend=True,
            legend=dict(orientation='h', yanchor='bottom', y=-0.15, xanchor='center', x=0.5),
        )
        
        return fig
    
    def grafico_valor_combinado(self, df):
        """
        Gráfico de barras apiladas: Valor cotización aceptada + valor VM
        por sucursal o técnico.
        """
        if df.empty or len(df[df['aceptada'] == True]) == 0:
            return self._crear_grafico_vacio("Sin cotizaciones aceptadas")
        
        df_aceptadas = df[df['aceptada'] == True]
        
        por_sucursal = df_aceptadas.groupby('sucursal').agg(
            valor_cotizacion=('costo_total_final', 'sum'),
            valor_vm=('vm_total_venta', 'sum'),
        ).reset_index()
        por_sucursal['valor_total'] = por_sucursal['valor_cotizacion'] + por_sucursal['valor_vm']
        por_sucursal = por_sucursal.sort_values('valor_total', ascending=True).tail(10)
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            name='Cotización Aceptada',
            y=por_sucursal['sucursal'],
            x=por_sucursal['valor_cotizacion'],
            orientation='h',
            marker_color=self.colores['success'],
            text=[f"${v:,.0f}" for v in por_sucursal['valor_cotizacion']],
            textposition='inside',
            hovertemplate='%{y}<br>Cotización: $%{x:,.2f}<extra></extra>'
        ))
        
        fig.add_trace(go.Bar(
            name='Venta Mostrador',
            y=por_sucursal['sucursal'],
            x=por_sucursal['valor_vm'],
            orientation='h',
            marker_color=self.colores['info'],
            text=[f"${v:,.0f}" if v > 0 else '' for v in por_sucursal['valor_vm']],
            textposition='inside',
            hovertemplate='%{y}<br>Venta Mostrador: $%{x:,.2f}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Valor Combinado: Cotización + Venta Mostrador', font=dict(size=16)),
            barmode='stack',
            xaxis_title='Monto ($)',
            yaxis_title='',
            height=450,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
        )
        fig.update_layout(margin=dict(l=150, r=50, t=80, b=50))
        
        return fig
    
    def grafico_tasa_upsell(self, df):
        """
        Gráfico de barras horizontales: Tasa de upsell (% de aceptadas con VM)
        por sucursal y técnico.
        """
        if df.empty or len(df[df['aceptada'] == True]) == 0:
            return self._crear_grafico_vacio("Sin cotizaciones aceptadas")
        
        df_aceptadas = df[df['aceptada'] == True]
        
        # Por sucursal
        upsell_sucursal = df_aceptadas.groupby('sucursal').agg(
            total=('aceptada', 'count'),
            con_vm=('tiene_venta_mostrador', 'sum'),
        ).reset_index()
        upsell_sucursal['tasa_upsell'] = (upsell_sucursal['con_vm'] / upsell_sucursal['total'] * 100).round(1)
        upsell_sucursal = upsell_sucursal.sort_values('tasa_upsell', ascending=True)
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=upsell_sucursal['sucursal'],
            x=upsell_sucursal['tasa_upsell'],
            orientation='h',
            marker_color=[
                self.colores['success'] if t >= 30 
                else self.colores['warning'] if t >= 15
                else self.colores['danger']
                for t in upsell_sucursal['tasa_upsell']
            ],
            text=[f'{t:.1f}% ({int(c)}/{int(tot)})' 
                  for t, c, tot in zip(upsell_sucursal['tasa_upsell'], upsell_sucursal['con_vm'], upsell_sucursal['total'])],
            textposition='auto',
            hovertemplate='%{y}<br>Tasa Upsell: %{x:.1f}%<extra></extra>',
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Tasa de Upsell: Aceptadas con Venta Mostrador por Sucursal', font=dict(size=16)),
            xaxis_title='Tasa de Upsell (%)',
            yaxis_title='',
            height=400,
            showlegend=False,
        )
        fig.update_layout(margin=dict(l=150, r=50, t=80, b=50))
        
        return fig
    
    def grafico_top_piezas_vm_aceptadas(self, analisis_vm):
        """
        Gráfico de barras horizontales: Top 10 piezas más vendidas en VM
        de cotizaciones aceptadas.
        """
        if not analisis_vm or not analisis_vm.get('tiene_datos'):
            return self._crear_grafico_vacio("Sin ventas mostrador en aceptadas")
        
        piezas = analisis_vm.get('top_piezas_vm', [])
        if not piezas:
            return self._crear_grafico_vacio("Sin piezas vendidas en VM")
        
        nombres = [p['descripcion'][:40] for p in piezas]
        cantidades = [p['cantidad'] for p in piezas]
        ingresos = [p['ingreso_total'] for p in piezas]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=nombres[::-1],
            x=cantidades[::-1],
            orientation='h',
            marker_color=self.colores['info'],
            text=[f'{c} uds - ${i:,.0f}' for c, i in zip(cantidades[::-1], ingresos[::-1])],
            textposition='auto',
            hovertemplate='%{y}<br>Cantidad: %{x}<extra></extra>',
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Top Piezas Vendidas en Venta Mostrador (Aceptadas)', font=dict(size=16)),
            xaxis_title='Cantidad Vendida',
            yaxis_title='',
            height=400,
            showlegend=False,
        )
        fig.update_layout(margin=dict(l=200, r=50, t=80, b=50))
        
        return fig
    
    def grafico_seguimiento_piezas_estado(self, analisis_seguimiento):
        """
        Gráfico de barras: Estado de los seguimientos de piezas post-aceptación.
        """
        if not analisis_seguimiento or not analisis_seguimiento.get('tiene_datos'):
            return self._crear_grafico_vacio("Sin seguimientos de piezas")
        
        estados = analisis_seguimiento['distribucion_estados']
        if not estados:
            return self._crear_grafico_vacio("Sin datos de estados")
        
        labels = [e['label'] for e in estados]
        valores = [e['cantidad'] for e in estados]
        colores = []
        for e in estados:
            if e['es_problematico']:
                colores.append(self.colores['danger'])
            elif e['es_recibido']:
                colores.append(self.colores['success'])
            else:
                colores.append(self.colores['warning'])
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=labels,
            y=valores,
            marker_color=colores,
            text=[f'{v} ({v/sum(valores)*100:.0f}%)' for v in valores],
            textposition='outside',
            hovertemplate='%{x}: %{y} seguimientos<extra></extra>',
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Estado de Seguimiento de Piezas Post-Aceptación', font=dict(size=16)),
            xaxis_title='Estado',
            yaxis_title='Cantidad',
            height=400,
            showlegend=False,
        )
        
        return fig
    
    def grafico_tiempos_entrega_proveedor(self, analisis_seguimiento):
        """
        Gráfico de barras: Tiempo promedio de entrega por proveedor.
        """
        if not analisis_seguimiento or not analisis_seguimiento.get('tiene_datos'):
            return self._crear_grafico_vacio("Sin seguimientos de piezas")
        
        proveedores = analisis_seguimiento.get('proveedores_ranking', [])
        # Solo proveedores con tiempo promedio registrado
        proveedores = [p for p in proveedores if p['tiempo_promedio'] is not None]
        if not proveedores:
            return self._crear_grafico_vacio("Sin datos de tiempo de entrega")
        
        # Ordenar por tiempo promedio ascendente (mejores primero)
        proveedores = sorted(proveedores, key=lambda x: x['tiempo_promedio'])[:15]
        
        nombres = [p['proveedor'][:30] for p in proveedores]
        tiempos = [p['tiempo_promedio'] for p in proveedores]
        tasas_exito = [p['tasa_exito'] for p in proveedores]
        totales = [p['total_pedidos'] for p in proveedores]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=nombres[::-1],
            x=tiempos[::-1],
            orientation='h',
            marker_color=[
                self.colores['success'] if t <= 7
                else self.colores['warning'] if t <= 14
                else self.colores['danger']
                for t in tiempos[::-1]
            ],
            text=[f'{t:.0f} días ({tot} pedidos, {te:.0f}% éxito)' 
                  for t, tot, te in zip(tiempos[::-1], totales[::-1], tasas_exito[::-1])],
            textposition='auto',
            hovertemplate='%{y}<br>Tiempo: %{x:.1f} días<extra></extra>',
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Tiempo de Entrega por Proveedor (Post-Aceptación)', font=dict(size=16)),
            xaxis_title='Días Promedio de Entrega',
            yaxis_title='',
            height=450,
            showlegend=False,
        )
        fig.update_layout(margin=dict(l=180, r=50, t=80, b=50))
        
        return fig
    
    def grafico_combinaciones_servicios(self, analisis_vm):
        """
        Gráfico de barras horizontales: Combinaciones más frecuentes de servicios
        vendidos en VentaMostrador de aceptadas.
        """
        if not analisis_vm or not analisis_vm.get('tiene_datos'):
            return self._crear_grafico_vacio("Sin ventas mostrador en aceptadas")
        
        combos = analisis_vm.get('combinaciones_frecuentes', [])
        if not combos:
            return self._crear_grafico_vacio("Sin combinaciones registradas")
        
        nombres = [c['combinacion'][:50] for c in combos[:10]]
        cantidades = [c['cantidad'] for c in combos[:10]]
        porcentajes = [c['porcentaje'] for c in combos[:10]]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=nombres[::-1],
            x=cantidades[::-1],
            orientation='h',
            marker_color=self.colores['purple'],
            text=[f'{c} ventas ({p}%)' for c, p in zip(cantidades[::-1], porcentajes[::-1])],
            textposition='auto',
            hovertemplate='%{y}<br>%{x} ventas<extra></extra>',
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(text='Combinaciones de Servicios Más Frecuentes', font=dict(size=16)),
            xaxis_title='Cantidad',
            yaxis_title='',
            height=400,
            showlegend=False,
        )
        fig.update_layout(margin=dict(l=250, r=50, t=80, b=50))
        
        return fig
    
    # ========================================================================
    # MÉTODOS AUXILIARES
    # ========================================================================
    
    def _crear_grafico_vacio(self, mensaje="No hay datos disponibles"):
        """
        Crea un gráfico vacío con mensaje para casos sin datos.
        
        Args:
            mensaje (str): Mensaje a mostrar
        
        Returns:
            Figure: Gráfico vacío de Plotly
        """
        fig = go.Figure()
        
        fig.add_annotation(
            text=mensaje,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=16, color=self.colores['secondary'])
        )
        
        fig.update_layout(
            **LAYOUT_BASE,
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(showgrid=False, showticklabels=False),
            height=400
        )
        
        return fig
    
    # ========================================================================
    # VISUALIZACIONES DE TEXT MINING (ANÁLISIS DE COMENTARIOS)
    # ========================================================================
    
    def grafico_palabras_frecuentes(self, palabras_clave):
        """
        Gráfico de barras horizontales con las palabras más frecuentes.
        
        Muestra las palabras que más aparecen en los comentarios de rechazo,
        ordenadas de mayor a menor frecuencia.
        
        Args:
            palabras_clave: Lista de dicts [{'palabra': str, 'frecuencia': int}]
        
        Returns:
            Figure: Gráfico de barras horizontales de Plotly
        """
        if not palabras_clave:
            return self._crear_grafico_vacio("No hay palabras para analizar")
        
        # Ordenar por frecuencia descendente
        palabras_ordenadas = sorted(palabras_clave, key=lambda x: x['frecuencia'], reverse=True)
        
        palabras = [p['palabra'].title() for p in palabras_ordenadas]
        frecuencias = [p['frecuencia'] for p in palabras_ordenadas]
        
        # Crear degradado de colores (más frecuente = más oscuro)
        max_freq = max(frecuencias)
        colores = [
            f'rgba(13, 110, 253, {0.3 + (freq / max_freq) * 0.7})'  # Azul con opacidad variable
            for freq in frecuencias
        ]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=palabras,
            x=frecuencias,
            orientation='h',
            text=frecuencias,
            textposition='outside',
            marker=dict(
                color=colores,
                line=dict(color=self.colores['primary'], width=1)
            ),
            hovertemplate='<b>%{y}</b><br>Aparece: %{x} veces<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🔤 Palabras Más Mencionadas en Rechazos',
                x=0.5,
                xanchor='center',
                font=dict(size=16, color=self.colores['dark'])
            ),
            xaxis=dict(
                title='Frecuencia (veces mencionada)',
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)'
            ),
            yaxis=dict(title='', autorange="reversed"),
            height=500,
            showlegend=False
        )
        
        # Ajustar margen después del update_layout
        fig.update_layout(margin=dict(l=150, r=50, t=80, b=50))
        
        return fig
    
    def grafico_frases_comunes(self, frases_comunes):
        """
        Gráfico de barras con las frases más comunes (bigramas).
        
        Muestra las combinaciones de 2 palabras que aparecen juntas
        frecuentemente en los comentarios de rechazo.
        
        Args:
            frases_comunes: Lista de dicts [{'frase': str, 'frecuencia': int}]
        
        Returns:
            Figure: Gráfico de barras de Plotly
        """
        if not frases_comunes:
            return self._crear_grafico_vacio("No hay frases para analizar")
        
        # Ordenar por frecuencia
        frases_ordenadas = sorted(frases_comunes, key=lambda x: x['frecuencia'], reverse=True)
        
        frases = [f['frase'].title() for f in frases_ordenadas]
        frecuencias = [f['frecuencia'] for f in frases_ordenadas]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            y=frases,
            x=frecuencias,
            orientation='h',
            text=frecuencias,
            textposition='outside',
            marker=dict(
                color=self.colores['info'],
                line=dict(color='white', width=2)
            ),
            hovertemplate='<b>"%{y}"</b><br>Aparece: %{x} veces<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='💬 Frases Más Comunes (Bigramas)',
                x=0.5,
                xanchor='center',
                font=dict(size=16, color=self.colores['dark'])
            ),
            xaxis=dict(
                title='Frecuencia',
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)'
            ),
            yaxis=dict(title='', autorange="reversed"),
            height=450,
            showlegend=False
        )
        
        # Ajustar margen después del update_layout
        fig.update_layout(margin=dict(l=180, r=50, t=80, b=50))
        
        return fig
    
    def grafico_correlacion_palabras(self, correlaciones):
        """
        Heatmap: Correlación entre palabras y tasa de rechazo/aceptación.
        
        Muestra qué palabras están más asociadas con aceptación vs rechazo.
        Verde = Alta aceptación cuando aparece
        Rojo = Alto rechazo cuando aparece
        
        Args:
            correlaciones: Lista de dicts [{'palabra': str, 'tasa_rechazo': float, 
                          'tasa_aceptacion': float, 'menciones': int}]
        
        Returns:
            Figure: Gráfico de barras apiladas de Plotly
        """
        if not correlaciones:
            return self._crear_grafico_vacio("No hay correlaciones para analizar")
        
        # Ordenar por tasa de rechazo (más peligrosas primero)
        correlaciones_ordenadas = sorted(correlaciones, key=lambda x: x['tasa_rechazo'], reverse=True)
        
        palabras = [c['palabra'].title() for c in correlaciones_ordenadas]
        tasas_rechazo = [c['tasa_rechazo'] for c in correlaciones_ordenadas]
        tasas_aceptacion = [c['tasa_aceptacion'] for c in correlaciones_ordenadas]
        menciones = [c['menciones'] for c in correlaciones_ordenadas]
        
        fig = go.Figure()
        
        # Barra de rechazo (rojo)
        fig.add_trace(go.Bar(
            y=palabras,
            x=tasas_rechazo,
            name='% Rechazo',
            orientation='h',
            marker=dict(color=self.colores['danger']),
            text=[f'{t:.0f}%' for t in tasas_rechazo],
            textposition='inside',
            hovertemplate='<b>%{y}</b><br>Rechazo: %{x:.1f}%<br>Menciones: %{customdata}<extra></extra>',
            customdata=menciones
        ))
        
        # Barra de aceptación (verde)
        fig.add_trace(go.Bar(
            y=palabras,
            x=tasas_aceptacion,
            name='% Aceptación',
            orientation='h',
            marker=dict(color=self.colores['success']),
            text=[f'{t:.0f}%' for t in tasas_aceptacion],
            textposition='inside',
            hovertemplate='<b>%{y}</b><br>Aceptación: %{x:.1f}%<br>Menciones: %{customdata}<extra></extra>',
            customdata=menciones
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🎯 Correlación Palabra → Resultado',
                x=0.5,
                xanchor='center',
                font=dict(size=16, color=self.colores['dark'])
            ),
            xaxis=dict(
                title='Porcentaje (%)',
                range=[0, 100],
                showgrid=True,
                gridcolor='rgba(0,0,0,0.1)'
            ),
            yaxis=dict(title='', autorange="reversed"),
            barmode='stack',
            height=500,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="center",
                x=0.5
            )
        )
        
        # Ajustar margen después del update_layout
        fig.update_layout(margin=dict(l=150, r=50, t=100, b=50))
        
        return fig
    
    def grafico_nube_palabras_simple(self, palabras_clave):
        """
        Visualización alternativa tipo "nube de palabras" usando burbujas.
        
        Dado que Python no tiene word cloud nativo fácil para web,
        esta función crea un gráfico de burbujas donde:
        - Tamaño de burbuja = frecuencia de palabra
        - Posición aleatoria pero organizada
        
        Args:
            palabras_clave: Lista de dicts [{'palabra': str, 'frecuencia': int}]
        
        Returns:
            Figure: Gráfico de burbujas de Plotly
        """
        if not palabras_clave:
            return self._crear_grafico_vacio("No hay palabras para visualizar")
        
        # Tomar top 25 palabras
        palabras_top = sorted(palabras_clave, key=lambda x: x['frecuencia'], reverse=True)[:25]
        
        palabras = [p['palabra'].title() for p in palabras_top]
        frecuencias = [p['frecuencia'] for p in palabras_top]
        
        # Generar posiciones en espiral
        import math
        n = len(palabras)
        theta = [2 * math.pi * i / n for i in range(n)]
        radio = [math.sqrt(freq) for freq in frecuencias]
        x = [r * math.cos(t) for r, t in zip(radio, theta)]
        y = [r * math.sin(t) for r, t in zip(radio, theta)]
        
        # Normalizar tamaños de burbuja
        max_freq = max(frecuencias)
        sizes = [(freq / max_freq) * 100 + 20 for freq in frecuencias]
        
        # Colores degradados
        colores_burbujas = [
            f'rgba(13, 110, 253, {0.3 + (freq / max_freq) * 0.7})'
            for freq in frecuencias
        ]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=x,
            y=y,
            mode='markers+text',
            text=palabras,
            textposition="middle center",
            textfont=dict(
                size=[10 + (freq / max_freq) * 20 for freq in frecuencias],
                color='white',
                family='Arial Black'
            ),
            marker=dict(
                size=sizes,
                color=colores_burbujas,
                line=dict(color=self.colores['primary'], width=2)
            ),
            hovertemplate='<b>%{text}</b><br>Frecuencia: %{customdata}<extra></extra>',
            customdata=frecuencias
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='☁️ Nube de Palabras Interactiva',
                x=0.5,
                xanchor='center',
                font=dict(size=16, color=self.colores['dark'])
            ),
            xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
            height=600,
            showlegend=False
        )
        
        # Ajustar hovermode después del update_layout
        fig.update_layout(hovermode='closest')
        
        return fig

    # ========================================================================
    # VISUALIZACIONES ML AVANZADAS (Sistema Experto)
    # ========================================================================
    
    def grafico_escenarios_precio(self, escenarios_dict):
        """
        Gráfico comparativo de escenarios de optimización de precio.
        
        Muestra los 4 escenarios (actual, óptimo, conservador, agresivo)
        comparando precio vs probabilidad de aceptación vs ingreso esperado.
        
        Args:
            escenarios_dict: Dict con 'escenario_actual', 'escenario_optimo', etc.
        
        Returns:
            Figure: Gráfico de barras agrupadas
        """
        escenarios = ['Actual', 'Conservador', 'Óptimo', 'Agresivo']
        
        # Extraer datos de cada escenario
        costos = [
            escenarios_dict.get('costo_actual', 0),
            escenarios_dict['escenario_conservador']['costo_final'],
            escenarios_dict['escenario_optimo']['costo_final'],
            escenarios_dict['escenario_agresivo']['costo_final']
        ]
        
        probabilidades = [
            escenarios_dict['escenario_actual']['prob_aceptacion'] * 100,
            escenarios_dict['escenario_conservador']['prob_aceptacion'] * 100,
            escenarios_dict['escenario_optimo']['prob_aceptacion'] * 100,
            escenarios_dict['escenario_agresivo']['prob_aceptacion'] * 100
        ]
        
        ingresos = [
            escenarios_dict['escenario_actual']['ingreso_esperado'],
            escenarios_dict['escenario_conservador']['ingreso_esperado'],
            escenarios_dict['escenario_optimo']['ingreso_esperado'],
            escenarios_dict['escenario_agresivo']['ingreso_esperado']
        ]
        
        fig = go.Figure()
        
        # Barras de costo
        fig.add_trace(go.Bar(
            name='Costo Final',
            x=escenarios,
            y=costos,
            text=[f'${c:,.0f}' for c in costos],
            textposition='outside',
            marker_color=self.colores['primary'],
            yaxis='y'
        ))
        
        # Línea de probabilidad
        fig.add_trace(go.Scatter(
            name='Prob. Aceptación',
            x=escenarios,
            y=probabilidades,
            mode='lines+markers+text',
            text=[f'{p:.1f}%' for p in probabilidades],
            textposition='top center',
            marker=dict(size=12, color=self.colores['success']),
            line=dict(width=3, color=self.colores['success']),
            yaxis='y2'
        ))
        
        # Línea de ingreso esperado
        fig.add_trace(go.Scatter(
            name='Ingreso Esperado',
            x=escenarios,
            y=ingresos,
            mode='lines+markers+text',
            text=[f'${i:,.0f}' for i in ingresos],
            textposition='bottom center',
            marker=dict(size=10, color=self.colores['warning']),
            line=dict(width=2, color=self.colores['warning'], dash='dash'),
            yaxis='y'
        ))
        
        fig.update_layout(
            font=dict(family='Segoe UI, sans-serif', size=12),
            paper_bgcolor='white',
            plot_bgcolor='#f8f9fa',
            margin=dict(l=50, r=50, t=80, b=50),
            title='Comparación de Escenarios de Precio',
            xaxis=dict(title='Escenario'),
            yaxis=dict(
                title='Costo / Ingreso ($)',
                side='left'
            ),
            yaxis2=dict(
                title='Probabilidad de Aceptación (%)',
                overlaying='y',
                side='right',
                range=[0, 100]
            ),
            hovermode='x unified',
            height=500
        )
        
        return fig
    
    def grafico_matriz_riesgo_beneficio(self, analisis_completo):
        """
        Matriz de riesgo vs beneficio para decisiones sobre cotización.
        
        Muestra las recomendaciones en un espacio de 4 cuadrantes:
        - Alto Riesgo / Alto Beneficio: Acciones audaces
        - Bajo Riesgo / Alto Beneficio: Acciones prioritarias
        - Alto Riesgo / Bajo Beneficio: Evitar
        - Bajo Riesgo / Bajo Beneficio: Opcional
        
        Args:
            analisis_completo: Dict con análisis del RecomendadorAcciones
        
        Returns:
            Figure: Scatter plot de matriz 2x2
        """
        recomendaciones = analisis_completo.get('recomendaciones', [])
        
        if not recomendaciones:
            return self._crear_grafico_vacio("No hay recomendaciones disponibles")
        
        # Asignar riesgo y beneficio a cada recomendación (heurística)
        # Prioridad alta = bajo riesgo, media/baja = alto riesgo
        # Nivel bajo (1-2) = alto beneficio, alto (3-4) = bajo beneficio
        
        x_riesgo = []
        y_beneficio = []
        textos = []
        colores_puntos = []
        tamaños = []
        
        for recom in recomendaciones:
            # Riesgo: inverso a la prioridad (1-4 -> 4-1)
            riesgo = 5 - recom['nivel']  # Nivel 1 = riesgo 4, Nivel 4 = riesgo 1
            
            # Beneficio: basado en tipo de recomendación
            beneficio = 3  # Default medio
            if recom['tipo'] == 'optimizacion_precio':
                beneficio = 4  # Alto beneficio
            elif recom['tipo'] == 'mitigar_motivo_rechazo':
                beneficio = 4
            elif recom['tipo'] == 'comunicacion_cliente':
                beneficio = 3
            elif recom['tipo'] == 'timing_envio':
                beneficio = 2
            
            x_riesgo.append(riesgo)
            y_beneficio.append(beneficio)
            textos.append(f"{recom['id']}. {recom['titulo'][:30]}...")
            
            # Color según prioridad
            if recom['color'] == 'danger':
                colores_puntos.append(self.colores['danger'])
            elif recom['color'] == 'warning':
                colores_puntos.append(self.colores['warning'])
            elif recom['color'] == 'info':
                colores_puntos.append(self.colores['info'])
            else:
                colores_puntos.append(self.colores['success'])
            
            # Tamaño según nivel
            tamaños.append(40 - (recom['nivel'] * 5))
        
        fig = go.Figure()
        
        # Puntos de recomendaciones
        fig.add_trace(go.Scatter(
            x=x_riesgo,
            y=y_beneficio,
            mode='markers+text',
            marker=dict(
                size=tamaños,
                color=colores_puntos,
                line=dict(width=2, color='white')
            ),
            text=[str(r['id']) for r in recomendaciones],
            textposition='middle center',
            textfont=dict(size=12, color='white', family='Arial Black'),
            hovertext=textos,
            hoverinfo='text',
            showlegend=False
        ))
        
        # Líneas de cuadrantes
        fig.add_hline(y=2.5, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=2.5, line_dash="dash", line_color="gray", opacity=0.5)
        
        # Anotaciones de cuadrantes
        fig.add_annotation(x=3.5, y=3.5, text="🎯 PRIORITARIO<br>Alto Beneficio<br>Bajo Riesgo",
                          showarrow=False, font=dict(size=10, color='green'), bgcolor='lightgreen', opacity=0.7)
        fig.add_annotation(x=1.5, y=3.5, text="⚡ AUDAZ<br>Alto Beneficio<br>Alto Riesgo",
                          showarrow=False, font=dict(size=10, color='orange'), bgcolor='lightyellow', opacity=0.7)
        fig.add_annotation(x=3.5, y=1.5, text="💤 OPCIONAL<br>Bajo Beneficio<br>Bajo Riesgo",
                          showarrow=False, font=dict(size=10, color='gray'), bgcolor='lightgray', opacity=0.7)
        fig.add_annotation(x=1.5, y=1.5, text="❌ EVITAR<br>Bajo Beneficio<br>Alto Riesgo",
                          showarrow=False, font=dict(size=10, color='red'), bgcolor='lightcoral', opacity=0.7)
        
        fig.update_layout(
            **LAYOUT_BASE,
            title='Matriz Riesgo-Beneficio de Recomendaciones',
            xaxis=dict(
                title='Nivel de Riesgo',
                range=[0.5, 4.5],
                tickvals=[1, 2, 3, 4],
                ticktext=['Muy Alto', 'Alto', 'Medio', 'Bajo']
            ),
            yaxis=dict(
                title='Beneficio Esperado',
                range=[0.5, 4.5],
                tickvals=[1, 2, 3, 4],
                ticktext=['Bajo', 'Medio', 'Alto', 'Muy Alto']
            ),
            height=600
        )
        
        return fig
    
    def grafico_probabilidad_por_dia(self, analisis_temporal):
        """
        Timeline de probabilidad de aceptación por día de la semana.
        
        Muestra qué días tienen mejor/peor probabilidad de aceptación
        basado en factores temporales históricos.
        
        Args:
            analisis_temporal: Dict con datos de DIAS_OPTIMOS
        
        Returns:
            Figure: Gráfico de barras horizontal con días de la semana
        """
        # Datos hardcodeados de DIAS_OPTIMOS del RecomendadorAcciones
        dias = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        factores = [1.15, 1.12, 1.0, 0.95, 0.82, 0.75, 0.70]
        recomendados = [True, True, False, False, False, False, False]
        
        # Probabilidad base: 50% * factor
        probabilidades = [50 * f for f in factores]
        
        # Colores según si es recomendado
        colores_barras = [
            self.colores['success'] if rec else self.colores['danger']
            for rec in recomendados
        ]
        
        # Marcar día actual
        dia_actual = analisis_temporal.get('dia_hoy', 'Lunes')
        marcadores = ['📍 HOY' if d == dia_actual else '' for d in dias]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=probabilidades,
            y=dias,
            orientation='h',
            text=[f'{p:.0f}% {m}' for p, m in zip(probabilidades, marcadores)],
            textposition='outside',
            marker=dict(
                color=colores_barras,
                line=dict(color='white', width=2)
            ),
            hovertemplate='<b>%{y}</b><br>Probabilidad: %{x:.1f}%<extra></extra>'
        ))
        
        # Línea de referencia (100% = base)
        fig.add_vline(x=50, line_dash="dash", line_color="gray", 
                     annotation_text="Base (50%)", annotation_position="top")
        
        fig.update_layout(
            **LAYOUT_BASE,
            title='Probabilidad de Aceptación por Día de la Semana',
            xaxis=dict(
                title='Probabilidad Relativa (%)',
                range=[0, max(probabilidades) * 1.2]
            ),
            yaxis=dict(title='Día'),
            height=400,
            showlegend=False
        )
        
        return fig

    # ========================================================================
    # VISUALIZACIONES PARA ANÁLISIS DE DIAGNÓSTICOS TÉCNICOS
    # ========================================================================
    
    def grafico_ranking_tecnicos_detalle(self, analisis_por_tecnico):
        """
        Gráfico de barras horizontales mostrando el promedio de palabras
        por diagnóstico de cada técnico (nivel de detalle).
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Este gráfico muestra qué técnico escribe diagnósticos más completos
        medido por el promedio de palabras que usa. Ayuda a identificar
        quién da más detalles y quién necesita mejorar.
        
        Args:
            analisis_por_tecnico: Lista de dicts con análisis de cada técnico
        
        Returns:
            Figure: Gráfico de barras horizontal
        """
        if not analisis_por_tecnico:
            return self._crear_grafico_vacio("No hay datos de técnicos disponibles")
        
        # Ordenar por promedio de palabras (descendente)
        tecnicos_ordenados = sorted(
            analisis_por_tecnico,
            key=lambda x: x['promedio_palabras'],
            reverse=True
        )
        
        tecnicos = [t['tecnico'] for t in tecnicos_ordenados]
        promedio_palabras = [t['promedio_palabras'] for t in tecnicos_ordenados]
        colores_barras = [self._mapear_color_nivel(t['color_detalle']) for t in tecnicos_ordenados]
        
        # Textos de hover personalizados
        hover_texts = [
            f"<b>{t['tecnico']}</b><br>" +
            f"📝 Promedio: {t['promedio_palabras']:.1f} palabras<br>" +
            f"📊 Diagnósticos: {t['num_diagnosticos']}<br>" +
            f"🏷️ Nivel: {t['nivel_detalle']}"
            for t in tecnicos_ordenados
        ]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=promedio_palabras,
            y=tecnicos,
            orientation='h',
            marker=dict(
                color=colores_barras,
                line=dict(color='white', width=1.5)
            ),
            text=[f"{p:.0f}" for p in promedio_palabras],
            textposition='outside',
            hovertext=hover_texts,
            hovertemplate='%{hovertext}<extra></extra>'
        ))
        
        # Línea de referencia (promedio global)
        promedio_global = sum(promedio_palabras) / len(promedio_palabras)
        fig.add_vline(
            x=promedio_global,
            line_dash="dash",
            line_color="gray",
            annotation_text=f"Promedio: {promedio_global:.0f}",
            annotation_position="top"
        )
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='📝 Ranking: Nivel de Detalle en Diagnósticos',
                x=0.5,
                xanchor='center',
                font=dict(size=16, color=self.colores['dark'])
            ),
            xaxis=dict(
                title='Promedio de Palabras por Diagnóstico',
                gridcolor='rgba(200,200,200,0.3)'
            ),
            yaxis=dict(title=''),
            height=max(400, len(tecnicos) * 40),
            showlegend=False
        )
        
        # Ajustar márgenes después del update_layout
        fig.update_layout(margin=dict(l=150, r=50, t=80, b=60))
        
        return fig
    
    def grafico_ranking_tecnicos_tecnicidad(self, analisis_por_tecnico):
        """
        Gráfico de barras mostrando el índice de tecnicidad de cada técnico
        (% de palabras técnicas usadas en sus diagnósticos).
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Este gráfico muestra qué técnico usa más terminología técnica
        especializada (como "motherboard", "cortocircuito", "voltaje", etc.)
        vs lenguaje coloquial. Ayuda a identificar el nivel profesional.
        
        Args:
            analisis_por_tecnico: Lista de dicts con análisis de cada técnico
        
        Returns:
            Figure: Gráfico de barras horizontal
        """
        if not analisis_por_tecnico:
            return self._crear_grafico_vacio("No hay datos de técnicos disponibles")
        
        # Ordenar por índice de tecnicidad (descendente)
        tecnicos_ordenados = sorted(
            analisis_por_tecnico,
            key=lambda x: x['indice_tecnicidad'],
            reverse=True
        )
        
        tecnicos = [t['tecnico'] for t in tecnicos_ordenados]
        indice_tecnicidad = [t['indice_tecnicidad'] for t in tecnicos_ordenados]
        colores_barras = [self._mapear_color_nivel(t['color_clasificacion']) for t in tecnicos_ordenados]
        
        # Textos de hover personalizados
        hover_texts = [
            f"<b>{t['tecnico']}</b><br>" +
            f"🔬 Tecnicidad: {t['indice_tecnicidad']:.1f}%<br>" +
            f"📊 Diagnósticos: {t['num_diagnosticos']}<br>" +
            f"🏷️ Clasificación: {t['clasificacion']}"
            for t in tecnicos_ordenados
        ]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=indice_tecnicidad,
            y=tecnicos,
            orientation='h',
            marker=dict(
                color=colores_barras,
                line=dict(color='white', width=1.5)
            ),
            text=[f"{i:.1f}%" for i in indice_tecnicidad],
            textposition='outside',
            hovertext=hover_texts,
            hovertemplate='%{hovertext}<extra></extra>'
        ))
        
        # Línea de referencia (promedio global)
        promedio_global = sum(indice_tecnicidad) / len(indice_tecnicidad)
        fig.add_vline(
            x=promedio_global,
            line_dash="dash",
            line_color="gray",
            annotation_text=f"Promedio: {promedio_global:.1f}%",
            annotation_position="top"
        )
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🔬 Ranking: Uso de Terminología Técnica',
                x=0.5,
                xanchor='center',
                font=dict(size=16, color=self.colores['dark'])
            ),
            xaxis=dict(
                title='Índice de Tecnicidad (%)',
                gridcolor='rgba(200,200,200,0.3)',
                range=[0, max(indice_tecnicidad) * 1.15]
            ),
            yaxis=dict(title=''),
            height=max(400, len(tecnicos) * 40),
            showlegend=False
        )
        
        # Ajustar márgenes después del update_layout
        fig.update_layout(margin=dict(l=150, r=50, t=80, b=60))
        
        return fig
    
    def grafico_comparativa_tecnicos_scatter(self, analisis_por_tecnico):
        """
        Gráfico de dispersión (scatter plot) comparando dos dimensiones:
        - Eje X: Promedio de palabras (nivel de detalle)
        - Eje Y: Índice de tecnicidad (uso de terminología técnica)
        
        Cada técnico es un punto, el tamaño indica cantidad de diagnósticos.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Este gráfico posiciona a cada técnico en un plano donde:
        - Derecha = Más detallado (escribe más)
        - Arriba = Más técnico (usa mejores términos)
        - Tamaño = Más diagnósticos realizados
        
        Objetivo: Identificar al técnico ideal (arriba-derecha)
        y quién necesita más capacitación (abajo-izquierda).
        
        Args:
            analisis_por_tecnico: Lista de dicts con análisis de cada técnico
        
        Returns:
            Figure: Gráfico de dispersión
        """
        if not analisis_por_tecnico:
            return self._crear_grafico_vacio("No hay datos de técnicos disponibles")
        
        tecnicos = [t['tecnico'] for t in analisis_por_tecnico]
        promedio_palabras = [t['promedio_palabras'] for t in analisis_por_tecnico]
        indice_tecnicidad = [t['indice_tecnicidad'] for t in analisis_por_tecnico]
        num_diagnosticos = [t['num_diagnosticos'] for t in analisis_por_tecnico]
        
        # Textos de hover personalizados
        hover_texts = [
            f"<b>{t['tecnico']}</b><br>" +
            f"📝 Detalle: {t['promedio_palabras']:.0f} palabras<br>" +
            f"🔬 Tecnicidad: {t['indice_tecnicidad']:.1f}%<br>" +
            f"📊 Diagnósticos: {t['num_diagnosticos']}<br>" +
            f"🏷️ {t['nivel_detalle']} / {t['clasificacion']}"
            for t in analisis_por_tecnico
        ]
        
        # Normalizar tamaños (entre 20 y 80)
        max_diag = max(num_diagnosticos)
        sizes = [20 + (n / max_diag) * 60 for n in num_diagnosticos]
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=promedio_palabras,
            y=indice_tecnicidad,
            mode='markers+text',
            text=[t.split()[0] for t in tecnicos],  # Solo primer nombre
            textposition="top center",
            textfont=dict(size=10, color=self.colores['dark']),
            marker=dict(
                size=sizes,
                color=indice_tecnicidad,
                colorscale='RdYlGn',  # Rojo-Amarillo-Verde
                colorbar=dict(
                    title="Tecnicidad<br>(%)",
                    thickness=15,
                    len=0.7
                ),
                line=dict(color='white', width=2),
                opacity=0.8
            ),
            hovertext=hover_texts,
            hovertemplate='%{hovertext}<extra></extra>'
        ))
        
        # Líneas de referencia (promedios)
        promedio_palabras_global = sum(promedio_palabras) / len(promedio_palabras)
        promedio_tecnicidad_global = sum(indice_tecnicidad) / len(indice_tecnicidad)
        
        fig.add_vline(
            x=promedio_palabras_global,
            line_dash="dash",
            line_color="gray",
            opacity=0.5,
            annotation_text=f"Promedio detalle",
            annotation_position="bottom"
        )
        
        fig.add_hline(
            y=promedio_tecnicidad_global,
            line_dash="dash",
            line_color="gray",
            opacity=0.5,
            annotation_text=f"Promedio tecnicidad",
            annotation_position="left"
        )
        
        # Anotaciones de cuadrantes
        max_x = max(promedio_palabras)
        max_y = max(indice_tecnicidad)
        
        fig.add_annotation(
            x=max_x * 0.85,
            y=max_y * 0.85,
            text="⭐ IDEAL",
            showarrow=False,
            font=dict(size=14, color='green', family='Arial Black'),
            opacity=0.3
        )
        
        fig.add_annotation(
            x=max_x * 0.15,
            y=max_y * 0.15,
            text="⚠️ NECESITA MEJORA",
            showarrow=False,
            font=dict(size=12, color='red', family='Arial Black'),
            opacity=0.3
        )
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🎯 Comparativa: Detalle vs Tecnicidad por Técnico',
                x=0.5,
                xanchor='center',
                font=dict(size=16, color=self.colores['dark'])
            ),
            xaxis=dict(
                title='📝 Promedio de Palabras (Nivel de Detalle)',
                gridcolor='rgba(200,200,200,0.3)',
                range=[0, max(promedio_palabras) * 1.15]
            ),
            yaxis=dict(
                title='🔬 Índice de Tecnicidad (%)',
                gridcolor='rgba(200,200,200,0.3)',
                range=[0, max(indice_tecnicidad) * 1.15]
            ),
            height=600,
            showlegend=False
        )
        
        # Ajustar hovermode después del update_layout
        fig.update_layout(hovermode='closest')
        
        return fig
    
    def grafico_palabras_tecnicas_globales(self, palabras_tecnicas_globales):
        """
        Gráfico de barras de las palabras técnicas más usadas globalmente
        por todos los técnicos.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        ================================
        Muestra qué términos técnicos se usan más frecuentemente en todos
        los diagnósticos. Ayuda a identificar componentes problemáticos
        más comunes y necesidades de capacitación/stock.
        
        Args:
            palabras_tecnicas_globales: Lista de dicts [{'palabra': str, 'frecuencia': int}]
        
        Returns:
            Figure: Gráfico de barras horizontal
        """
        if not palabras_tecnicas_globales:
            return self._crear_grafico_vacio("No hay palabras técnicas para visualizar")
        
        # Tomar top 15
        palabras_top = palabras_tecnicas_globales[:15]
        
        palabras = [p['palabra'].title() for p in palabras_top]
        frecuencias = [p['frecuencia'] for p in palabras_top]
        
        # Colores degradados
        max_freq = max(frecuencias)
        colores = [
            f'rgba(13, 110, 253, {0.4 + (freq / max_freq) * 0.6})'
            for freq in frecuencias
        ]
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=frecuencias,
            y=palabras,
            orientation='h',
            marker=dict(
                color=colores,
                line=dict(color='white', width=1.5)
            ),
            text=frecuencias,
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>Frecuencia: %{x}<extra></extra>'
        ))
        
        fig.update_layout(
            **LAYOUT_BASE,
            title=dict(
                text='🔧 Top Términos Técnicos Más Usados',
                x=0.5,
                xanchor='center',
                font=dict(size=16, color=self.colores['dark'])
            ),
            xaxis=dict(
                title='Frecuencia de Uso',
                gridcolor='rgba(200,200,200,0.3)'
            ),
            yaxis=dict(title=''),
            height=max(400, len(palabras) * 30),
            showlegend=False
        )
        
        # Ajustar márgenes después del update_layout
        fig.update_layout(margin=dict(l=120, r=50, t=80, b=60))
        
        return fig
    
    def _mapear_color_nivel(self, color_string):
        """
        Mapea los nombres de colores de Bootstrap a colores RGB.
        
        Args:
            color_string: Nombre del color ('success', 'warning', 'danger', 'primary', 'info')
        
        Returns:
            str: Color RGB correspondiente
        """
        mapeo = {
            'success': 'rgba(39, 174, 96, 0.8)',    # Verde
            'primary': 'rgba(13, 110, 253, 0.8)',   # Azul
            'warning': 'rgba(255, 193, 7, 0.8)',    # Amarillo
            'danger': 'rgba(231, 76, 60, 0.8)',     # Rojo
            'info': 'rgba(23, 162, 184, 0.8)',      # Cian
        }
        return mapeo.get(color_string, 'rgba(108, 117, 125, 0.8)')  # Gris por defecto


# ============================================================================
# FUNCIÓN AUXILIAR PARA TEMPLATES
# ============================================================================

def convertir_figura_a_html(fig, include_plotlyjs='cdn'):
    """
    Convierte una figura de Plotly a HTML para insertar en templates Django.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función toma un gráfico de Plotly y lo convierte a código HTML
    que puedes poner directamente en un template de Django con {{ grafico|safe }}.
    
    Args:
        fig (Figure): Figura de Plotly
        include_plotlyjs (str): Cómo incluir Plotly.js
            - 'cdn': Desde CDN (recomendado, más rápido)
            - 'directory': Desde archivos locales
            - False: No incluir (si ya está en base.html)
    
    Returns:
        str: HTML del gráfico
    
    Ejemplo en template Django:
        # En views.py:
        fig = visualizer.grafico_evolucion_cotizaciones(df)
        context['grafico_evolucion'] = convertir_figura_a_html(fig)
        
        # En template:
        {{ grafico_evolucion|safe }}
    """
    return fig.to_html(
        config=CONFIG_PLOTLY,
        include_plotlyjs=include_plotlyjs,
        div_id=None  # Auto-generar IDs únicos
    )
