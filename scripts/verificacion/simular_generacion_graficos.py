"""
Script de Simulación - Generación Completa de Gráficos
======================================================

Este script simula exactamente lo que hace la vista del dashboard
para generar los gráficos y muestra cualquier error que ocurra.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.utils_cotizaciones import (
    analizar_proveedores_con_conversion,
    analizar_componentes_por_proveedor
)
from servicio_tecnico.plotly_visualizations import DashboardCotizacionesVisualizer

def simular_generacion_graficos():
    """Simula la generación de gráficos como en la vista."""
    
    print("\n" + "="*80)
    print("SIMULACIÓN DE GENERACIÓN DE GRÁFICOS")
    print("="*80)
    
    # Inicializar graficador
    graficador = DashboardCotizacionesVisualizer()
    print("\n✅ Graficador inicializado")
    
    # ========================================================================
    # GRÁFICO 1: IMPACTO EN CONVERSIÓN
    # ========================================================================
    print("\n" + "-"*80)
    print("GRÁFICO 1: IMPACTO EN CONVERSIÓN DE VENTAS")
    print("-"*80)
    
    try:
        print("\n📊 Obteniendo datos de proveedores...")
        df_prov_conversion = analizar_proveedores_con_conversion(cotizacion_ids=None)
        
        print(f"   - Registros obtenidos: {len(df_prov_conversion)}")
        print(f"   - DataFrame vacío: {df_prov_conversion.empty}")
        
        if not df_prov_conversion.empty:
            print("\n📊 Generando gráfico de impacto en conversión...")
            
            try:
                # Intentar generar el gráfico
                fig = graficador.grafico_proveedores_impacto_conversion(df_prov_conversion)
                print("   ✅ Gráfico generado exitosamente")
                
                # Intentar convertir a HTML
                from servicio_tecnico.plotly_visualizations import convertir_figura_a_html
                html = convertir_figura_a_html(fig)
                
                if html:
                    print(f"   ✅ Convertido a HTML exitosamente ({len(html)} caracteres)")
                    print(f"   📄 Primeros 200 caracteres del HTML:")
                    print(f"   {html[:200]}...")
                else:
                    print("   ❌ Conversión a HTML devolvió None o vacío")
                
            except Exception as e:
                print(f"\n❌ ERROR al generar gráfico:")
                print(f"   {type(e).__name__}: {e}")
                import traceback
                print(traceback.format_exc())
        else:
            print("\n⚠️  DataFrame vacío - no se puede generar gráfico")
            
    except Exception as e:
        print(f"\n❌ ERROR al obtener datos:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
    
    # ========================================================================
    # GRÁFICO 2: ESPECIALIZACIÓN POR COMPONENTE
    # ========================================================================
    print("\n" + "-"*80)
    print("GRÁFICO 2: ESPECIALIZACIÓN POR COMPONENTE")
    print("-"*80)
    
    try:
        print("\n📊 Obteniendo datos de componentes...")
        df_componentes = analizar_componentes_por_proveedor(cotizacion_ids=None)
        
        print(f"   - Registros obtenidos: {len(df_componentes)}")
        print(f"   - DataFrame vacío: {df_componentes.empty}")
        
        if not df_componentes.empty:
            print("\n📊 Muestra de datos:")
            print(df_componentes.head(10).to_string())
            
            print("\n📊 Generando gráfico de componentes por proveedor...")
            
            try:
                # Intentar generar el gráfico
                fig = graficador.grafico_componentes_por_proveedor(df_componentes)
                print("   ✅ Gráfico generado exitosamente")
                
                # Intentar convertir a HTML
                from servicio_tecnico.plotly_visualizations import convertir_figura_a_html
                html = convertir_figura_a_html(fig)
                
                if html:
                    print(f"   ✅ Convertido a HTML exitosamente ({len(html)} caracteres)")
                    print(f"   📄 Primeros 200 caracteres del HTML:")
                    print(f"   {html[:200]}...")
                else:
                    print("   ❌ Conversión a HTML devolvió None o vacío")
                
            except Exception as e:
                print(f"\n❌ ERROR al generar gráfico:")
                print(f"   {type(e).__name__}: {e}")
                import traceback
                print(traceback.format_exc())
        else:
            print("\n⚠️  DataFrame vacío - no se puede generar gráfico")
            
    except Exception as e:
        print(f"\n❌ ERROR al obtener datos:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        print(traceback.format_exc())
    
    print("\n" + "="*80)
    print("FIN DE SIMULACIÓN")
    print("="*80 + "\n")


if __name__ == '__main__':
    simular_generacion_graficos()
