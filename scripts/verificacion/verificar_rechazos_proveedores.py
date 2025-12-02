"""
Script de verificación: Rechazos de piezas por proveedor

Este script verifica si la nueva lógica de rechazo de piezas por proveedor
está funcionando correctamente y si hay datos disponibles para los gráficos.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este script hace lo siguiente:
1. Verifica que existan piezas cotizadas con proveedor asignado
2. Verifica que existan rechazos de piezas (aceptada_por_cliente=False)
3. Simula la lógica de las funciones de análisis de proveedores
4. Muestra estadísticas detalladas de los datos disponibles

Cómo ejecutar:
    python scripts/verificacion/verificar_rechazos_proveedores.py
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import PiezaCotizada, SeguimientoPieza, Cotizacion
from servicio_tecnico.utils_cotizaciones import (
    analizar_proveedores_con_conversion,
    analizar_componentes_por_proveedor
)
import pandas as pd

def linea_separadora(titulo=""):
    """Imprime una línea separadora visual"""
    if titulo:
        print(f"\n{'='*80}")
        print(f"  {titulo}")
        print(f"{'='*80}")
    else:
        print(f"{'='*80}")


def verificar_piezas_cotizadas():
    """Verifica el estado de las piezas cotizadas"""
    linea_separadora("1. VERIFICACIÓN DE PIEZAS COTIZADAS")
    
    # Total de piezas cotizadas
    total_piezas = PiezaCotizada.objects.count()
    print(f"✅ Total de piezas cotizadas en el sistema: {total_piezas}")
    
    # Piezas con proveedor asignado
    piezas_con_proveedor = PiezaCotizada.objects.exclude(proveedor='').exclude(proveedor__isnull=True).count()
    print(f"✅ Piezas con proveedor asignado: {piezas_con_proveedor}")
    
    # Piezas sin proveedor
    piezas_sin_proveedor = PiezaCotizada.objects.filter(proveedor='').count() + \
                           PiezaCotizada.objects.filter(proveedor__isnull=True).count()
    print(f"⚠️  Piezas sin proveedor: {piezas_sin_proveedor}")
    
    # Piezas con respuesta del cliente
    piezas_con_respuesta = PiezaCotizada.objects.exclude(aceptada_por_cliente__isnull=True).count()
    print(f"✅ Piezas con respuesta del cliente: {piezas_con_respuesta}")
    
    # Desglose de respuestas
    piezas_aceptadas = PiezaCotizada.objects.filter(aceptada_por_cliente=True).count()
    piezas_rechazadas = PiezaCotizada.objects.filter(aceptada_por_cliente=False).count()
    piezas_sin_respuesta = PiezaCotizada.objects.filter(aceptada_por_cliente__isnull=True).count()
    
    print(f"\n   📊 Desglose de respuestas:")
    print(f"      ✅ Aceptadas: {piezas_aceptadas} ({piezas_aceptadas/total_piezas*100:.1f}%)")
    print(f"      ❌ Rechazadas: {piezas_rechazadas} ({piezas_rechazadas/total_piezas*100:.1f}%)")
    print(f"      ⏳ Sin respuesta: {piezas_sin_respuesta} ({piezas_sin_respuesta/total_piezas*100:.1f}%)")
    
    # Piezas rechazadas CON proveedor (CLAVE PARA LOS GRÁFICOS)
    piezas_rechazadas_con_proveedor = PiezaCotizada.objects.filter(
        aceptada_por_cliente=False
    ).exclude(proveedor='').exclude(proveedor__isnull=True).count()
    
    print(f"\n   🎯 CLAVE: Piezas rechazadas CON proveedor: {piezas_rechazadas_con_proveedor}")
    
    if piezas_rechazadas_con_proveedor == 0:
        print(f"   ⚠️  ALERTA: No hay piezas rechazadas con proveedor asignado.")
        print(f"   ⚠️  Los gráficos de rechazo por proveedor NO tendrán datos.")
    else:
        print(f"   ✅ Hay datos suficientes para gráficos de rechazo.")
    
    return {
        'total': total_piezas,
        'con_proveedor': piezas_con_proveedor,
        'sin_proveedor': piezas_sin_proveedor,
        'aceptadas': piezas_aceptadas,
        'rechazadas': piezas_rechazadas,
        'rechazadas_con_proveedor': piezas_rechazadas_con_proveedor
    }


def verificar_seguimientos_piezas():
    """Verifica los seguimientos de piezas"""
    linea_separadora("2. VERIFICACIÓN DE SEGUIMIENTOS DE PIEZAS")
    
    total_seguimientos = SeguimientoPieza.objects.count()
    print(f"✅ Total de seguimientos de piezas: {total_seguimientos}")
    
    # Seguimientos con piezas vinculadas
    seguimientos_con_piezas = SeguimientoPieza.objects.exclude(piezas=None).distinct().count()
    print(f"✅ Seguimientos con piezas específicas vinculadas: {seguimientos_con_piezas}")
    
    # Proveedores únicos
    proveedores = SeguimientoPieza.objects.values('proveedor').distinct().count()
    print(f"✅ Proveedores únicos en seguimientos: {proveedores}")
    
    # Lista de proveedores
    lista_proveedores = SeguimientoPieza.objects.values_list('proveedor', flat=True).distinct()
    print(f"\n   📋 Lista de proveedores:")
    for proveedor in lista_proveedores[:10]:  # Mostrar primeros 10
        count = SeguimientoPieza.objects.filter(proveedor=proveedor).count()
        print(f"      - {proveedor}: {count} seguimientos")
    
    return {
        'total': total_seguimientos,
        'con_piezas_vinculadas': seguimientos_con_piezas,
        'proveedores_unicos': proveedores
    }


def probar_funcion_analizar_proveedores_conversion():
    """Prueba la función de análisis de proveedores con conversión"""
    linea_separadora("3. PRUEBA: analizar_proveedores_con_conversion()")
    
    try:
        df = analizar_proveedores_con_conversion()
        
        if df.empty:
            print("❌ La función retornó un DataFrame VACÍO")
            print("   Posible causa: No hay seguimientos de piezas o datos insuficientes")
            return None
        
        print(f"✅ DataFrame generado exitosamente")
        print(f"   - Filas (proveedores): {len(df)}")
        print(f"   - Columnas: {len(df.columns)}")
        
        print(f"\n   📊 Columnas disponibles:")
        for col in df.columns:
            print(f"      - {col}")
        
        print(f"\n   🔍 Primeros 5 proveedores:")
        print(df.head().to_string())
        
        # Verificar si hay datos de rechazo
        if 'cotizaciones_rechazadas' in df.columns:
            total_rechazos = df['cotizaciones_rechazadas'].sum()
            print(f"\n   ❌ Total de cotizaciones rechazadas: {total_rechazos}")
            
            if total_rechazos == 0:
                print(f"   ⚠️  ALERTA: No hay rechazos registrados en proveedores")
                print(f"   ⚠️  El gráfico 'Impacto en Conversión' mostrará 0% rechazo")
        
        return df
        
    except Exception as e:
        print(f"❌ ERROR al ejecutar la función: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def probar_funcion_analizar_componentes_proveedor():
    """Prueba la función de análisis de componentes por proveedor"""
    linea_separadora("4. PRUEBA: analizar_componentes_por_proveedor()")
    
    try:
        df = analizar_componentes_por_proveedor()
        
        if df.empty:
            print("❌ La función retornó un DataFrame VACÍO")
            print("   Posible causa: No hay seguimientos o piezas vinculadas")
            return None
        
        print(f"✅ DataFrame generado exitosamente")
        print(f"   - Filas: {len(df)}")
        print(f"   - Columnas: {len(df.columns)}")
        
        print(f"\n   📊 Columnas disponibles:")
        for col in df.columns:
            print(f"      - {col}")
        
        print(f"\n   🔍 Primeros 10 registros:")
        print(df.head(10).to_string())
        
        # Verificar si hay datos de rechazo
        if 'resultado' in df.columns:
            rechazados = df[df['resultado'] == 'Rechazado']
            print(f"\n   ❌ Componentes rechazados: {len(rechazados)}")
            print(f"   ✅ Componentes aceptados: {len(df[df['resultado'] == 'Aceptado'])}")
            print(f"   ⏳ Sin respuesta: {len(df[df['resultado'] == 'Sin Respuesta'])}")
            
            if len(rechazados) == 0:
                print(f"\n   ⚠️  ALERTA: No hay componentes rechazados")
                print(f"   ⚠️  El gráfico 'Especialización por Componente' no mostrará rechazos")
            else:
                print(f"\n   ✅ Desglose de rechazos por componente:")
                rechazos_por_componente = rechazados.groupby('componente_nombre')['cantidad'].sum()
                for componente, cantidad in rechazos_por_componente.items():
                    print(f"      - {componente}: {cantidad} piezas rechazadas")
        
        return df
        
    except Exception as e:
        print(f"❌ ERROR al ejecutar la función: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def analizar_relacion_seguimientos_piezas():
    """Analiza cómo están relacionados seguimientos y piezas"""
    linea_separadora("5. ANÁLISIS DE RELACIÓN SEGUIMIENTOS-PIEZAS")
    
    # Verificar cuántos seguimientos tienen piezas vinculadas
    seguimientos = SeguimientoPieza.objects.all()
    
    con_piezas = 0
    sin_piezas = 0
    
    for seg in seguimientos:
        if seg.piezas.exists():
            con_piezas += 1
        else:
            sin_piezas += 1
    
    print(f"✅ Seguimientos CON piezas vinculadas: {con_piezas}")
    print(f"⚠️  Seguimientos SIN piezas vinculadas: {sin_piezas}")
    
    if sin_piezas > 0:
        print(f"\n   ℹ️  NOTA: Los seguimientos sin piezas vinculadas usarán")
        print(f"   ℹ️  todas las piezas de la cotización como referencia.")
    
    # Analizar un caso específico
    if con_piezas > 0:
        ejemplo = SeguimientoPieza.objects.exclude(piezas=None).first()
        print(f"\n   📝 Ejemplo de seguimiento con piezas vinculadas:")
        print(f"      - Proveedor: {ejemplo.proveedor}")
        print(f"      - Piezas vinculadas: {ejemplo.piezas.count()}")
        
        for pieza in ejemplo.piezas.all():
            resultado = "✅ Aceptada" if pieza.aceptada_por_cliente == True else \
                       "❌ Rechazada" if pieza.aceptada_por_cliente == False else \
                       "⏳ Sin respuesta"
            print(f"         • {pieza.componente.nombre} - {resultado}")


def generar_reporte_final(stats_piezas):
    """Genera un reporte final con recomendaciones"""
    linea_separadora("6. REPORTE FINAL Y RECOMENDACIONES")
    
    print("📋 RESUMEN EJECUTIVO:")
    print(f"   - Total de piezas cotizadas: {stats_piezas['total']}")
    print(f"   - Piezas con proveedor: {stats_piezas['con_proveedor']} ({stats_piezas['con_proveedor']/stats_piezas['total']*100:.1f}%)")
    print(f"   - Piezas rechazadas: {stats_piezas['rechazadas']}")
    print(f"   - Piezas rechazadas CON proveedor: {stats_piezas['rechazadas_con_proveedor']}")
    
    print(f"\n🎯 EVALUACIÓN DE GRÁFICOS:")
    
    # Gráfico 1: Impacto en Conversión
    if stats_piezas['rechazadas_con_proveedor'] > 0:
        print(f"   ✅ 'Impacto en Conversión de Ventas': FUNCIONARÁ correctamente")
        print(f"      - Mostrará tasa de rechazo por proveedor")
        print(f"      - {stats_piezas['rechazadas_con_proveedor']} piezas rechazadas disponibles")
    else:
        print(f"   ⚠️  'Impacto en Conversión de Ventas': DATOS INSUFICIENTES")
        print(f"      - No hay piezas rechazadas con proveedor asignado")
        print(f"      - El gráfico mostrará 0% rechazo para todos los proveedores")
    
    # Gráfico 2: Especialización por Componente
    if stats_piezas['rechazadas'] > 0:
        print(f"   ✅ 'Especialización por Componente': FUNCIONARÁ correctamente")
        print(f"      - Mostrará segmentos de rechazos por componente y proveedor")
        print(f"      - {stats_piezas['rechazadas']} piezas rechazadas disponibles")
    else:
        print(f"   ⚠️  'Especialización por Componente': DATOS INSUFICIENTES")
        print(f"      - No hay piezas rechazadas")
        print(f"      - No se mostrará el segmento 'Rechazado' en el Sunburst")
    
    print(f"\n💡 RECOMENDACIONES:")
    
    if stats_piezas['rechazadas_con_proveedor'] == 0:
        print(f"   1. Asignar proveedores a las piezas cotizadas existentes")
        print(f"   2. Asegurar que al cotizar se seleccione el proveedor")
        print(f"   3. Revisar formularios de cotización para incluir campo 'proveedor'")
    
    if stats_piezas['sin_proveedor'] > stats_piezas['con_proveedor']:
        print(f"   4. Actualizar piezas antiguas sin proveedor ({stats_piezas['sin_proveedor']} piezas)")
        print(f"   5. Implementar validación obligatoria de proveedor en formularios")


def main():
    """Función principal de verificación"""
    print("\n" + "="*80)
    print("  🔍 VERIFICACIÓN: RECHAZOS DE PIEZAS POR PROVEEDOR")
    print("="*80)
    print("\nEste script verifica la implementación de la nueva lógica de")
    print("rechazo de piezas por proveedor y valida los datos para los gráficos.")
    
    # 1. Verificar piezas cotizadas
    stats_piezas = verificar_piezas_cotizadas()
    
    # 2. Verificar seguimientos
    stats_seguimientos = verificar_seguimientos_piezas()
    
    # 3. Probar función de análisis de proveedores
    df_proveedores = probar_funcion_analizar_proveedores_conversion()
    
    # 4. Probar función de análisis de componentes
    df_componentes = probar_funcion_analizar_componentes_proveedor()
    
    # 5. Analizar relación seguimientos-piezas
    analizar_relacion_seguimientos_piezas()
    
    # 6. Generar reporte final
    generar_reporte_final(stats_piezas)
    
    print("\n" + "="*80)
    print("  ✅ VERIFICACIÓN COMPLETADA")
    print("="*80 + "\n")


if __name__ == '__main__':
    main()
