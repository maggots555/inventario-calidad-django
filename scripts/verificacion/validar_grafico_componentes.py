"""
Script de Validación - Gráfico de Especialización por Componente
================================================================

Este script genera el gráfico "Especialización por Componente" y lo guarda
como archivo HTML para validación visual completa.
"""

import os
import sys
import django

# Configurar Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.utils_cotizaciones import analizar_componentes_por_proveedor
from servicio_tecnico.plotly_visualizations import DashboardCotizacionesVisualizer, convertir_figura_a_html

def validar_grafico_componentes():
    """Valida y genera el gráfico de componentes por proveedor."""
    
    print("\n" + "="*80)
    print("VALIDACIÓN: GRÁFICO DE ESPECIALIZACIÓN POR COMPONENTE")
    print("="*80)
    
    try:
        # 1. Obtener datos
        print("\n📊 PASO 1: Obteniendo datos de componentes por proveedor...")
        df_componentes = analizar_componentes_por_proveedor(cotizacion_ids=None)
        
        print(f"   ✅ Datos obtenidos: {len(df_componentes)} registros")
        
        if df_componentes.empty:
            print("\n❌ ERROR: No hay datos disponibles")
            return
        
        # Mostrar resumen de datos
        print(f"\n📊 RESUMEN DE DATOS:")
        print(f"   - Componentes únicos: {df_componentes['componente_nombre'].nunique()}")
        print(f"   - Proveedores únicos: {df_componentes['proveedor'].nunique()}")
        print(f"   - Total de piezas: {df_componentes['cantidad'].sum()}")
        print(f"   - Valor total: ${df_componentes['valor_total'].sum():,.2f}")
        
        print(f"\n📊 DISTRIBUCIÓN POR RESULTADO:")
        for resultado, count in df_componentes['resultado'].value_counts().items():
            print(f"   - {resultado}: {count} registros")
        
        print(f"\n📊 TOP 5 COMPONENTES:")
        top_componentes = df_componentes.groupby('componente_nombre')['cantidad'].sum().sort_values(ascending=False).head(5)
        for comp, cant in top_componentes.items():
            print(f"   - {comp}: {cant} piezas")
        
        print(f"\n📊 TOP 5 PROVEEDORES:")
        top_proveedores = df_componentes.groupby('proveedor')['cantidad'].sum().sort_values(ascending=False).head(5)
        for prov, cant in top_proveedores.items():
            print(f"   - {prov}: {cant} piezas")
        
        # 2. Generar gráfico
        print("\n📊 PASO 2: Generando gráfico Sunburst...")
        graficador = DashboardCotizacionesVisualizer()
        fig = graficador.grafico_componentes_por_proveedor(df_componentes)
        print("   ✅ Gráfico generado exitosamente")
        
        # 3. Convertir a HTML
        print("\n📊 PASO 3: Convirtiendo a HTML...")
        html = convertir_figura_a_html(fig)
        
        if not html:
            print("   ❌ ERROR: Conversión a HTML falló")
            return
        
        print(f"   ✅ HTML generado: {len(html)} caracteres")
        
        # 4. Guardar archivo HTML
        output_path = os.path.join(
            os.path.dirname(__file__),
            'grafico_componentes_validacion.html'
        )
        
        print(f"\n📊 PASO 4: Guardando archivo HTML...")
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"   ✅ Archivo guardado: {output_path}")
        
        # 5. Validar estructura del HTML
        print(f"\n📊 PASO 5: Validando estructura del HTML...")
        
        validaciones = {
            'Contiene etiquetas HTML': '<html>' in html and '</html>' in html,
            'Contiene script de Plotly': 'plotly' in html.lower(),
            'Contiene datos del gráfico': 'Sunburst' in html or 'sunburst' in html.lower(),
            'Contiene configuración': 'PlotlyConfig' in html,
            'Tiene tamaño válido': len(html) > 5000
        }
        
        for validacion, resultado in validaciones.items():
            status = "✅" if resultado else "❌"
            print(f"   {status} {validacion}")
        
        if all(validaciones.values()):
            print("\n✅ VALIDACIÓN EXITOSA: El HTML está correctamente generado")
            print(f"\n🌐 Puedes abrir el archivo en un navegador:")
            print(f"   {output_path}")
        else:
            print("\n⚠️  ADVERTENCIA: Algunas validaciones fallaron")
        
        # 6. Análisis de jerarquía del Sunburst
        print(f"\n📊 PASO 6: Verificando estructura jerárquica del Sunburst...")
        
        # El Sunburst tiene 4 niveles:
        # Nivel 0: Raíz ("Todos los Componentes")
        # Nivel 1: Componentes (RAM, Disco, etc.)
        # Nivel 2: Proveedores por componente
        # Nivel 3: Resultados (Aceptado/Rechazado)
        
        niveles_esperados = {
            'Nivel 0 (Raíz)': 1,
            'Nivel 1 (Componentes)': df_componentes['componente_nombre'].nunique(),
            'Nivel 2 (Proveedor-Componente)': len(df_componentes.groupby(['componente_nombre', 'proveedor'])),
            'Nivel 3 (Resultados)': len(df_componentes)
        }
        
        print("\n   Estructura jerárquica esperada:")
        for nivel, cantidad in niveles_esperados.items():
            print(f"   - {nivel}: {cantidad} nodos")
        
        total_nodos = sum(niveles_esperados.values())
        print(f"\n   📊 Total de nodos en el Sunburst: {total_nodos}")
        
        # 7. Ejemplo de datos que debería mostrar
        print(f"\n📊 PASO 7: Ejemplo de datos visibles en el gráfico...")
        print("\n   Al hacer click en el centro verás:")
        print("   └─ 📦 Todos los Componentes")
        
        # Mostrar primer componente con sus proveedores
        primer_componente = df_componentes.iloc[0]['componente_nombre']
        proveedores_comp = df_componentes[df_componentes['componente_nombre'] == primer_componente]
        
        print(f"\n   Ejemplo: Componente '{primer_componente}':")
        for _, row in proveedores_comp.head(3).iterrows():
            print(f"      └─ {row['proveedor']}: {row['cantidad']} piezas | {row['resultado']}")
        
        print("\n" + "="*80)
        print("VALIDACIÓN COMPLETADA")
        print("="*80)
        print(f"\n💡 SIGUIENTE PASO:")
        print(f"   1. Abre el archivo: {output_path}")
        print(f"   2. Verifica que el gráfico Sunburst se visualice correctamente")
        print(f"   3. Haz click en los segmentos para navegar por la jerarquía")
        print(f"   4. Verifica que los datos coincidan con el resumen mostrado arriba")
        
    except Exception as e:
        print(f"\n❌ ERROR durante validación:")
        print(f"   {type(e).__name__}: {e}")
        import traceback
        print("\n" + traceback.format_exc())


if __name__ == '__main__':
    validar_grafico_componentes()
