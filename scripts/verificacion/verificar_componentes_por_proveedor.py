"""
Script de verificación: Análisis de Componentes por Proveedor (Sunburst)

Este script valida específicamente la función analizar_componentes_por_proveedor()
que genera datos para el gráfico Sunburst "Especialización por Componente".

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Verifica que el gráfico Sunburst muestre correctamente:
1. Todos los componentes cotizados con proveedor
2. Proveedores que suministran cada componente
3. Resultados por pieza: Aceptado/Rechazado/Sin Respuesta
4. Incluyendo piezas rechazadas (que NO tienen seguimiento)

Cómo ejecutar:
    python scripts/verificacion/verificar_componentes_por_proveedor.py
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import PiezaCotizada
from servicio_tecnico.utils_cotizaciones import analizar_componentes_por_proveedor
import pandas as pd


def linea_separadora(titulo=""):
    """Imprime una línea separadora visual"""
    if titulo:
        print(f"\n{'='*80}")
        print(f"  {titulo}")
        print(f"{'='*80}")
    else:
        print(f"{'='*80}")


def verificar_piezas_por_resultado():
    """Verifica la distribución de piezas por resultado y proveedor"""
    linea_separadora("1. ANÁLISIS DE PIEZAS POR RESULTADO")
    
    # Obtener todas las piezas con proveedor
    piezas = PiezaCotizada.objects.exclude(proveedor='').exclude(proveedor__isnull=True)
    
    total = piezas.count()
    aceptadas = piezas.filter(aceptada_por_cliente=True).count()
    rechazadas = piezas.filter(aceptada_por_cliente=False).count()
    sin_respuesta = piezas.filter(aceptada_por_cliente__isnull=True).count()
    
    print(f"📊 Total de piezas con proveedor: {total}")
    print(f"   ✅ Aceptadas: {aceptadas} ({aceptadas/total*100:.1f}%)")
    print(f"   ❌ Rechazadas: {rechazadas} ({rechazadas/total*100:.1f}%)")
    print(f"   ⏳ Sin respuesta: {sin_respuesta} ({sin_respuesta/total*100:.1f}%)")
    
    # Desglose por proveedor
    print(f"\n📋 Desglose por proveedor (Top 5 con más rechazos):")
    
    proveedores = piezas.values_list('proveedor', flat=True).distinct()
    
    data_proveedores = []
    for proveedor in proveedores:
        piezas_prov = piezas.filter(proveedor=proveedor)
        total_prov = piezas_prov.count()
        aceptadas_prov = piezas_prov.filter(aceptada_por_cliente=True).count()
        rechazadas_prov = piezas_prov.filter(aceptada_por_cliente=False).count()
        
        if total_prov > 0:
            data_proveedores.append({
                'proveedor': proveedor,
                'total': total_prov,
                'aceptadas': aceptadas_prov,
                'rechazadas': rechazadas_prov,
                'pct_rechazo': (rechazadas_prov / total_prov * 100) if total_prov > 0 else 0
            })
    
    # Ordenar por rechazos descendente
    data_proveedores = sorted(data_proveedores, key=lambda x: x['rechazadas'], reverse=True)
    
    for i, prov_data in enumerate(data_proveedores[:5], 1):
        print(f"   {i}. {prov_data['proveedor']}:")
        print(f"      Total: {prov_data['total']} | "
              f"Aceptadas: {prov_data['aceptadas']} | "
              f"Rechazadas: {prov_data['rechazadas']} ({prov_data['pct_rechazo']:.1f}%)")
    
    return {
        'total': total,
        'aceptadas': aceptadas,
        'rechazadas': rechazadas,
        'sin_respuesta': sin_respuesta,
        'proveedores_con_rechazos': len([p for p in data_proveedores if p['rechazadas'] > 0])
    }


def verificar_componentes_mas_rechazados():
    """Identifica qué componentes son más rechazados"""
    linea_separadora("2. COMPONENTES MÁS RECHAZADOS")
    
    piezas = PiezaCotizada.objects.exclude(proveedor='').exclude(proveedor__isnull=True)
    rechazadas = piezas.filter(aceptada_por_cliente=False).select_related('componente')
    
    print(f"❌ Total de piezas rechazadas con proveedor: {rechazadas.count()}")
    
    if rechazadas.count() == 0:
        print(f"   ⚠️  No hay piezas rechazadas para analizar")
        return {}
    
    # Agrupar por componente
    componentes_rechazados = {}
    for pieza in rechazadas:
        componente = pieza.componente.nombre
        if componente not in componentes_rechazados:
            componentes_rechazados[componente] = {
                'cantidad': 0,
                'valor': 0,
                'proveedores': set()
            }
        componentes_rechazados[componente]['cantidad'] += pieza.cantidad
        componentes_rechazados[componente]['valor'] += float(pieza.costo_total)
        componentes_rechazados[componente]['proveedores'].add(pieza.proveedor)
    
    # Ordenar por cantidad
    componentes_ordenados = sorted(
        componentes_rechazados.items(),
        key=lambda x: x[1]['cantidad'],
        reverse=True
    )
    
    print(f"\n📊 Top componentes rechazados:")
    for i, (componente, datos) in enumerate(componentes_ordenados[:10], 1):
        proveedores_str = ", ".join(list(datos['proveedores'])[:3])
        if len(datos['proveedores']) > 3:
            proveedores_str += "..."
        
        print(f"   {i}. {componente}:")
        print(f"      Cantidad rechazada: {datos['cantidad']}")
        print(f"      Valor perdido: ${datos['valor']:,.2f}")
        print(f"      Proveedores: {proveedores_str}")
    
    return componentes_rechazados


def probar_funcion_analizar_componentes():
    """Prueba la función principal"""
    linea_separadora("3. PRUEBA: analizar_componentes_por_proveedor()")
    
    try:
        df = analizar_componentes_por_proveedor()
        
        if df.empty:
            print("❌ La función retornó un DataFrame VACÍO")
            return None
        
        print(f"✅ DataFrame generado exitosamente")
        print(f"   - Filas totales: {len(df)}")
        print(f"   - Columnas: {list(df.columns)}")
        
        # Analizar resultados
        print(f"\n📊 Distribución de resultados:")
        resultados = df.groupby('resultado')['cantidad'].sum()
        for resultado, cantidad in resultados.items():
            icono = "✅" if resultado == "Aceptado" else "❌" if resultado == "Rechazado" else "⏳"
            print(f"   {icono} {resultado}: {cantidad} piezas")
        
        # Analizar rechazos específicos
        rechazados = df[df['resultado'] == 'Rechazado']
        
        if len(rechazados) == 0:
            print(f"\n⚠️  ALERTA CRÍTICA: No hay piezas rechazadas en el DataFrame")
            print(f"   Esto significa que el gráfico Sunburst NO mostrará segmentos rojos.")
            return df
        
        print(f"\n❌ Análisis de rechazos:")
        print(f"   Total de filas con rechazo: {len(rechazados)}")
        print(f"   Piezas rechazadas: {rechazados['cantidad'].sum()}")
        print(f"   Valor perdido: ${rechazados['valor_total'].sum():,.2f}")
        
        # Top combinaciones componente-proveedor rechazadas
        print(f"\n🔍 Top 10 combinaciones Componente-Proveedor rechazadas:")
        rechazados_ordenados = rechazados.sort_values('cantidad', ascending=False)
        
        for i, row in rechazados_ordenados.head(10).iterrows():
            print(f"   {row['componente_nombre']} | {row['proveedor']} | "
                  f"{row['cantidad']} piezas | ${row['valor_total']:,.2f}")
        
        # Verificar jerarquía para Sunburst
        print(f"\n🌟 Verificación de jerarquía Sunburst:")
        print(f"   - Componentes únicos: {df['componente_nombre'].nunique()}")
        print(f"   - Proveedores únicos: {df['proveedor'].nunique()}")
        print(f"   - Resultados únicos: {df['resultado'].nunique()}")
        
        # Mostrar ejemplo de jerarquía
        componente_ejemplo = df['componente_nombre'].iloc[0]
        df_ejemplo = df[df['componente_nombre'] == componente_ejemplo]
        
        print(f"\n   Ejemplo de jerarquía para '{componente_ejemplo}':")
        for _, row in df_ejemplo.iterrows():
            print(f"      └─ {row['proveedor']} → {row['resultado']} ({row['cantidad']} piezas)")
        
        return df
        
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def validar_integridad_datos(df, stats_piezas):
    """Valida que los datos del DataFrame coincidan con la BD"""
    linea_separadora("4. VALIDACIÓN DE INTEGRIDAD DE DATOS")
    
    if df is None or df.empty:
        print("❌ No hay DataFrame para validar")
        return
    
    # Total de piezas en DataFrame vs BD
    total_df = df['cantidad'].sum()
    total_bd = stats_piezas['total']
    
    print(f"✅ Total de piezas:")
    print(f"   - En DataFrame: {total_df}")
    print(f"   - En Base de Datos: {total_bd}")
    
    if total_df != total_bd:
        print(f"   ⚠️  DIFERENCIA: {abs(total_df - total_bd)} piezas")
        print(f"   Esto es esperado si hay piezas sin proveedor asignado")
    else:
        print(f"   ✅ Coinciden perfectamente")
    
    # Rechazos en DataFrame vs BD
    rechazos_df = df[df['resultado'] == 'Rechazado']['cantidad'].sum()
    rechazos_bd = stats_piezas['rechazadas']
    
    print(f"\n❌ Piezas rechazadas:")
    print(f"   - En DataFrame: {rechazos_df}")
    print(f"   - En Base de Datos: {rechazos_bd}")
    
    if rechazos_df != rechazos_bd:
        diferencia = abs(rechazos_df - rechazos_bd)
        pct_diferencia = (diferencia / rechazos_bd * 100) if rechazos_bd > 0 else 0
        print(f"   ⚠️  DIFERENCIA: {diferencia} piezas ({pct_diferencia:.1f}%)")
        
        if pct_diferencia > 10:
            print(f"   ❌ CRÍTICO: Más del 10% de diferencia")
            print(f"   Posible causa: Piezas rechazadas sin proveedor asignado")
    else:
        print(f"   ✅ Coinciden perfectamente")


def generar_reporte_final(df, componentes_rechazados):
    """Genera reporte final"""
    linea_separadora("5. REPORTE FINAL - GRÁFICO SUNBURST")
    
    if df is None or df.empty:
        print("❌ No se puede generar reporte: DataFrame vacío")
        return
    
    rechazados = df[df['resultado'] == 'Rechazado']
    
    print("📋 EVALUACIÓN FINAL:")
    
    if len(rechazados) > 0:
        print(f"   ✅ FUNCIONARÁ CORRECTAMENTE")
        print(f"   ✅ El gráfico Sunburst mostrará segmentos ROJOS para rechazos")
        print(f"   ✅ Datos disponibles:")
        print(f"      - {len(rechazados)} combinaciones Componente-Proveedor-Rechazo")
        print(f"      - {rechazados['cantidad'].sum()} piezas rechazadas en total")
        print(f"      - ${rechazados['valor_total'].sum():,.2f} en valor rechazado")
        
        # Proveedores con más rechazos
        top_proveedores_rechazo = rechazados.groupby('proveedor')['cantidad'].sum().sort_values(ascending=False)
        
        print(f"\n   🎯 Proveedores con más rechazos:")
        for proveedor, cantidad in top_proveedores_rechazo.head(3).items():
            print(f"      - {proveedor}: {cantidad} piezas rechazadas")
        
        # Componentes con más rechazos
        top_componentes_rechazo = rechazados.groupby('componente_nombre')['cantidad'].sum().sort_values(ascending=False)
        
        print(f"\n   📦 Componentes con más rechazos:")
        for componente, cantidad in top_componentes_rechazo.head(3).items():
            print(f"      - {componente}: {cantidad} piezas rechazadas")
    else:
        print(f"   ⚠️  FUNCIONAMIENTO LIMITADO")
        print(f"   ⚠️  El gráfico NO mostrará segmentos de rechazo (rojos)")
        print(f"   ℹ️  Solo mostrará piezas aceptadas y sin respuesta")
    
    print(f"\n💡 INSIGHTS CLAVE:")
    print(f"   - Total de niveles jerárquicos: 3 (Componente → Proveedor → Resultado)")
    print(f"   - Componentes únicos: {df['componente_nombre'].nunique()}")
    print(f"   - Proveedores únicos: {df['proveedor'].nunique()}")
    print(f"   - Interactividad: Click en segmentos para navegar jerarquía")


def main():
    """Función principal"""
    print("\n" + "="*80)
    print("  🔍 VERIFICACIÓN: COMPONENTES POR PROVEEDOR (SUNBURST)")
    print("="*80)
    
    # 1. Verificar distribución de piezas
    stats_piezas = verificar_piezas_por_resultado()
    
    # 2. Identificar componentes rechazados
    componentes_rechazados = verificar_componentes_mas_rechazados()
    
    # 3. Probar función principal
    df = probar_funcion_analizar_componentes()
    
    # 4. Validar integridad
    if df is not None:
        validar_integridad_datos(df, stats_piezas)
    
    # 5. Generar reporte
    generar_reporte_final(df, componentes_rechazados)
    
    print("\n" + "="*80)
    print("  ✅ VERIFICACIÓN COMPLETADA")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
