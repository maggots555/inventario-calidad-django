#!/usr/bin/env python
"""
Script de Verificación - Modelo de Motivos
==========================================

PROPÓSITO:
Verifica que el sistema esté usando la versión mejorada del predictor
de motivos (73.33% accuracy) en lugar de la versión original (37.78%).

EXPLICACIÓN PARA PRINCIPIANTES:
Este script carga el predictor de motivos y muestra información
sobre qué versión se está usando, verificando que sea la correcta.
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.ml_advanced import PredictorMotivoRechazo

def verificar_modelo():
    """Verifica que el modelo correcto esté siendo usado."""
    
    print("\n" + "="*70)
    print("🔍 VERIFICACIÓN DEL MODELO DE MOTIVOS DE RECHAZO")
    print("="*70)
    
    # Crear instancia del predictor
    print("\n1️⃣ Creando instancia del predictor...")
    predictor = PredictorMotivoRechazo()
    
    # Información de la clase
    print(f"\n📦 Información de la Clase:")
    print(f"   - Nombre de clase: {predictor.__class__.__name__}")
    print(f"   - Módulo: {predictor.__class__.__module__}")
    print(f"   - Archivo: {predictor.__class__.__module__.replace('.', '/')}.py")
    
    # Información del modelo
    print(f"\n💾 Información del Modelo:")
    print(f"   - Nombre del modelo: {predictor.model_name}")
    print(f"   - Ruta del modelo: {predictor.model_path}")
    print(f"   - ¿Existe el archivo?: {'✅ Sí' if predictor.model_path.exists() else '❌ No'}")
    
    # Intentar cargar
    print(f"\n🔄 Cargando modelo...")
    if predictor.cargar_modelo():
        print(f"   ✅ Modelo cargado exitosamente")
        print(f"   - ¿Entrenado?: {'✅ Sí' if predictor.is_trained else '❌ No'}")
        
        # Verificar metadata
        if hasattr(predictor, 'metadata') and predictor.metadata:
            print(f"\n📊 Metadata del Modelo:")
            accuracy = predictor.metadata.get('accuracy', 0)
            if isinstance(accuracy, str):
                accuracy = float(accuracy) if accuracy != 'N/A' else 0
            print(f"   - Accuracy: {accuracy:.2%}")
            print(f"   - Muestras entrenamiento: {predictor.metadata.get('n_samples', 'N/A')}")
            print(f"   - Features: {predictor.metadata.get('n_features', 'N/A')}")
            print(f"   - Fecha entrenamiento: {predictor.metadata.get('fecha_entrenamiento', 'N/A')}")
            
            # Verificación crítica: ¿Es el modelo mejorado?
            print(f"\n✨ VERIFICACIÓN:")
            if accuracy > 0.70:
                print(f"   ✅ CORRECTO: Usando modelo MEJORADO (accuracy: {accuracy:.2%})")
                print(f"   ✨ El modelo tiene >70% accuracy - es la versión mejorada")
            elif accuracy > 0.35 and accuracy < 0.40:
                print(f"   ❌ ERROR: Usando modelo ORIGINAL (accuracy: {accuracy:.2%})")
                print(f"   ⚠️ Este es el modelo viejo de 37.78% - NO es el mejorado")
            else:
                print(f"   ⚠️ ADVERTENCIA: Accuracy inusual ({accuracy:.2%})")
        else:
            print(f"   ⚠️ No se encontró metadata")
            
    else:
        print(f"   ❌ Error al cargar modelo")
    
    print("\n" + "="*70)
    print()

if __name__ == '__main__':
    verificar_modelo()
