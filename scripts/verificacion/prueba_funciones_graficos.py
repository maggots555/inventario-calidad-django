"""
Script de Prueba - Funciones de Análisis de Proveedores
=======================================================

Este script llama directamente a las funciones que generan los datos
para los gráficos y muestra exactamente qué están devolviendo.
"""

import os
import sys
import django
import pandas as pd

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.utils_cotizaciones import (
    analizar_proveedores_con_conversion,
    analizar_componentes_por_proveedor
)

def probar_funcion_conversion():
    """Prueba la función de análisis de conversión de proveedores."""
    
    print("\n" + "="*80)
    print("PROBANDO: analizar_proveedores_con_conversion()")
    print("="*80)
    
    try:
        # Llamar sin filtro (todas las cotizaciones)
        df = analizar_proveedores_con_conversion(cotizacion_ids=None)
        
        print(f"\n✅ Función ejecutada exitosamente")
        print(f"📊 Registros devueltos: {len(df)}")
        print(f"📋 Columnas: {list(df.columns)}")
        
        if df.empty:
            print("\n❌ PROBLEMA: DataFrame vacío")
            print("   La función no está devolviendo datos.")
        else:
            print("\n✅ Datos encontrados!")
            print("\n📊 Primeros 10 registros:")
            print(df.head(10).to_string())
            
            print("\n📊 Resumen estadístico:")
            print(df.describe().to_string())
            
            # Verificar columnas críticas
            print("\n🔍 Análisis de columnas críticas:")
            
            if 'tasa_aceptacion' in df.columns:
                print(f"   - Tasa de aceptación promedio: {df['tasa_aceptacion'].mean():.1f}%")
                print(f"   - Tasa de aceptación mín/máx: {df['tasa_aceptacion'].min():.1f}% / {df['tasa_aceptacion'].max():.1f}%")
                print(f"   - Proveedores con tasa < 100%: {len(df[df['tasa_aceptacion'] < 100])}")
            
            if 'tiempo_entrega_promedio' in df.columns:
                no_nulos = df['tiempo_entrega_promedio'].notna().sum()
                print(f"   - Proveedores con tiempo de entrega: {no_nulos} de {len(df)}")
                if no_nulos > 0:
                    print(f"   - Tiempo promedio: {df['tiempo_entrega_promedio'].mean():.1f} días")
            
            if 'valor_generado' in df.columns:
                print(f"   - Valor total generado: ${df['valor_generado'].sum():,.2f}")
                print(f"   - Proveedores con valor > 0: {len(df[df['valor_generado'] > 0])}")
        
    except Exception as e:
        print(f"\n❌ ERROR al ejecutar función:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        print("\n" + traceback.format_exc())


def probar_funcion_componentes():
    """Prueba la función de análisis de componentes por proveedor."""
    
    print("\n" + "="*80)
    print("PROBANDO: analizar_componentes_por_proveedor()")
    print("="*80)
    
    try:
        # Llamar sin filtro (todas las cotizaciones)
        df = analizar_componentes_por_proveedor(cotizacion_ids=None)
        
        print(f"\n✅ Función ejecutada exitosamente")
        print(f"📊 Registros devueltos: {len(df)}")
        print(f"📋 Columnas: {list(df.columns)}")
        
        if df.empty:
            print("\n❌ PROBLEMA: DataFrame vacío")
            print("   La función no está devolviendo datos.")
        else:
            print("\n✅ Datos encontrados!")
            print("\n📊 Primeros 20 registros:")
            print(df.head(20).to_string())
            
            print("\n📊 Estadísticas generales:")
            print(f"   - Componentes únicos: {df['componente_nombre'].nunique()}")
            print(f"   - Proveedores únicos: {df['proveedor'].nunique()}")
            print(f"   - Resultados únicos: {df['resultado'].unique()}")
            
            print("\n📊 Distribución por resultado:")
            dist_resultado = df['resultado'].value_counts()
            print(dist_resultado.to_string())
            
            print("\n📊 Top 5 proveedores por cantidad de piezas:")
            top_proveedores = df.groupby('proveedor')['cantidad'].sum().sort_values(ascending=False).head()
            print(top_proveedores.to_string())
            
            print("\n📊 Top 5 componentes más cotizados:")
            top_componentes = df.groupby('componente_nombre')['cantidad'].sum().sort_values(ascending=False).head()
            print(top_componentes.to_string())
        
    except Exception as e:
        print(f"\n❌ ERROR al ejecutar función:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        print("\n" + traceback.format_exc())


def analizar_problema():
    """Análisis final del problema."""
    
    print("\n" + "="*80)
    print("ANÁLISIS DEL PROBLEMA")
    print("="*80)
    
    from servicio_tecnico.models import SeguimientoPieza, Cotizacion
    
    # Verificar seguimientos vinculados a cotizaciones rechazadas
    seguimientos_rechazados = SeguimientoPieza.objects.filter(
        cotizacion__usuario_acepto=False
    ).exclude(proveedor__in=['', None])
    
    print(f"\n📊 Seguimientos vinculados a cotizaciones RECHAZADAS: {seguimientos_rechazados.count()}")
    
    if seguimientos_rechazados.count() == 0:
        print("\n⚠️  PROBLEMA IDENTIFICADO:")
        print("   Todos los seguimientos están vinculados solo a cotizaciones aceptadas.")
        print("   Los gráficos necesitan variación (aceptadas Y rechazadas) para ser útiles.")
        print("\n💡 EXPLICACIÓN:")
        print("   El gráfico 'Impacto en Conversión' compara proveedores por su tasa de éxito.")
        print("   Si todos tienen 100% de aceptación, no hay nada que comparar o mostrar.")
        print("\n🔧 SOLUCIÓN:")
        print("   1. Vincular seguimientos a TODAS las cotizaciones (no solo aceptadas)")
        print("   2. O crear seguimientos para cotizaciones rechazadas también")
        print("   3. Esto dará variación real en las tasas de aceptación por proveedor")
    else:
        print("\n✅ Hay seguimientos vinculados a cotizaciones rechazadas")
        print(f"   Proveedores con rechazos: {seguimientos_rechazados.values('proveedor').distinct().count()}")
    
    # Verificar seguimientos vinculados a cotizaciones sin respuesta
    seguimientos_sin_respuesta = SeguimientoPieza.objects.filter(
        cotizacion__usuario_acepto__isnull=True
    ).exclude(proveedor__in=['', None])
    
    print(f"\n📊 Seguimientos vinculados a cotizaciones SIN RESPUESTA: {seguimientos_sin_respuesta.count()}")


if __name__ == '__main__':
    print("\n" + "="*80)
    print("PRUEBA DE FUNCIONES DE ANÁLISIS DE PROVEEDORES")
    print("="*80)
    
    probar_funcion_conversion()
    probar_funcion_componentes()
    analizar_problema()
    
    print("\n" + "="*80)
    print("FIN DE PRUEBAS")
    print("="*80 + "\n")
