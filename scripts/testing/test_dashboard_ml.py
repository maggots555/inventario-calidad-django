# -*- coding: utf-8 -*-
"""
Script de Prueba: Dashboard ML - Diagnóstico de Motivo Predicho

PROPÓSITO:
Diagnostica por qué no aparece "Motivo Probable" en el dashboard.

CÓMO EJECUTAR:
cd C:/Users/DELL/Proyecto_Django/inventario-calidad-django
.venv/Scripts/activate
python scripts/testing/test_dashboard_ml.py
"""

import os
import sys
import django
from pathlib import Path

# Configurar Django
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.utils_cotizaciones import obtener_dataframe_cotizaciones
from servicio_tecnico.ml_predictor import PredictorAceptacionCotizacion
from servicio_tecnico.ml_advanced import PredictorMotivoRechazo, RecomendadorAcciones


def diagnosticar_dashboard():
    """
    Diagnostica qué está pasando con el ML en el dashboard.
    """
    
    print("\n" + "="*80)
    print("DIAGNÓSTICO: DASHBOARD ML - MOTIVO PROBABLE")
    print("="*80)
    
    # 1. Obtener datos de cotizaciones
    print("\n📊 Paso 1: Obteniendo datos de cotizaciones...")
    df = obtener_dataframe_cotizaciones()
    
    print(f"   Total cotizaciones: {len(df)}")
    print(f"   Con respuesta: {df['aceptada'].notna().sum()}")
    print(f"   Pendientes: {df['aceptada'].isna().sum()}")
    
    # 2. Verificar si hay cotizaciones pendientes
    df_pendientes = df[df['aceptada'].isna()]
    
    if df_pendientes.empty:
        print("\n❌ PROBLEMA ENCONTRADO: No hay cotizaciones pendientes")
        print("   El análisis ML avanzado solo funciona con cotizaciones sin respuesta.")
        print("   Solución: Crea una nueva cotización sin respuesta para probar el ML.")
        return
    
    print(f"\n✅ Hay {len(df_pendientes)} cotización(es) pendiente(s)")
    
    # 3. Analizar última cotización pendiente
    ultima = df_pendientes.iloc[-1]
    print(f"\n📋 Cotización a analizar:")
    print(f"   ID: {ultima['cotizacion_id']}")
    print(f"   Orden: {ultima['numero_orden']}")
    print(f"   Costo: ${ultima['costo_total']:,.0f}")
    print(f"   Piezas: {ultima['total_piezas']}")
    print(f"   Gama: {ultima['gama']}")
    
    # 4. Cargar predictor base
    print("\n🤖 Paso 2: Cargando predictor base...")
    predictor_base = PredictorAceptacionCotizacion()
    
    try:
        predictor_base.cargar_modelo()
        print("   ✅ Predictor base cargado")
    except FileNotFoundError as e:
        print(f"   ❌ Error: {str(e)}")
        return
    
    # 5. Hacer predicción base
    features = {
        'costo_total': ultima['costo_total'],
        'costo_mano_obra': ultima['costo_mano_obra'],
        'costo_total_piezas': ultima['costo_total_piezas'],
        'total_piezas': ultima['total_piezas'],
        'piezas_necesarias': ultima['piezas_necesarias'],
        'porcentaje_necesarias': ultima['porcentaje_necesarias'],
        'piezas_sugeridas_tecnico': ultima['piezas_sugeridas_tecnico'],
        'descontar_mano_obra': ultima['descontar_mano_obra'],
        'gama': ultima['gama'],
        'tipo_equipo': ultima['tipo_equipo'],
    }
    
    prob_rechazo, prob_aceptacion = predictor_base.predecir_probabilidad(features)
    
    print(f"\n📈 Predicción Base:")
    print(f"   Probabilidad Aceptación: {prob_aceptacion*100:.1f}%")
    print(f"   Probabilidad Rechazo: {prob_rechazo*100:.1f}%")
    
    # 6. Verificar umbral para predicción de motivo
    print("\n🔍 Paso 3: Verificando umbral para predicción de motivo...")
    
    if prob_aceptacion >= 0.70:
        print(f"   ❌ PROBLEMA ENCONTRADO: Prob. aceptación = {prob_aceptacion*100:.1f}% (>= 70%)")
        print("   El predictor de motivos SOLO se ejecuta si prob. aceptación < 70%")
        print("   Esto es un filtro de eficiencia: no tiene sentido predecir motivo")
        print("   de rechazo si probablemente será aceptada.")
        print("\n💡 SOLUCIÓN:")
        print("   1. Esto NO es un error, es comportamiento esperado")
        print("   2. Para ver 'Motivo Probable', necesitas una cotización con:")
        print("      - Costo alto (> $10,000)")
        print("      - Muchas piezas (> 5)")
        print("      - Sin descuento de mano de obra")
        return
    
    print(f"   ✅ Prob. aceptación = {prob_aceptacion*100:.1f}% (< 70%)")
    print("   Se ejecutará predicción de motivo...")
    
    # 7. Cargar predictor de motivos
    print("\n🔬 Paso 4: Cargando predictor de motivos...")
    predictor_motivos = PredictorMotivoRechazo()
    
    try:
        predictor_motivos.cargar_modelo()
        print("   ✅ Predictor de motivos cargado")
    except FileNotFoundError as e:
        print(f"   ❌ Error: {str(e)}")
        return
    
    # 8. Predecir motivo
    print("\n🎯 Paso 5: Prediciendo motivo de rechazo...")
    
    try:
        resultado = predictor_motivos.predecir_motivo(features)
        
        print(f"\n✅ PREDICCIÓN EXITOSA:")
        print(f"   Motivo Principal: {resultado['motivo_nombre']}")
        print(f"   Probabilidad: {resultado['probabilidad_pct']}")
        print(f"   Confianza: {resultado['confianza']} {resultado['confianza_icono']}")
        print(f"   Descripción: {resultado['motivo_descripcion']}")
        
        print(f"\n📝 Acciones Sugeridas:")
        for i, accion in enumerate(resultado['acciones_sugeridas'], 1):
            print(f"   {i}. {accion}")
        
        if resultado['motivos_alternativos']:
            print(f"\n🔄 Motivos Alternativos:")
            for alt in resultado['motivos_alternativos']:
                print(f"   - {alt['nombre']}: {alt['probabilidad_pct']}")
        
        print("\n" + "="*80)
        print("✅ TODO FUNCIONA CORRECTAMENTE")
        print("="*80)
        print("El dashboard debería mostrar esta información en 'Motivo Probable'.")
        print("Si no aparece, verifica:")
        print("1. Que estés viendo el dashboard con los filtros correctos")
        print("2. Que la cotización pendiente tenga prob. aceptación < 70%")
        print("3. Que no haya errores de JavaScript en la consola del navegador")
        
    except Exception as e:
        print(f"\n❌ ERROR prediciendo motivo: {str(e)}")
        import traceback
        traceback.print_exc()
        
        print("\n💡 SOLUCIÓN:")
        print("   Vuelve a entrenar el modelo con:")
        print("   python scripts/ml/entrenar_predictor_motivos.py")


def main():
    diagnosticar_dashboard()


if __name__ == '__main__':
    main()
