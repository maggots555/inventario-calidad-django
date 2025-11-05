# -*- coding: utf-8 -*-
"""
Script: Entrenar Predictor de Motivos de Rechazo

PROPÓSITO:
Entrena el modelo ML avanzado que predice POR QUÉ una cotización será rechazada.
Este es uno de los 3 módulos del sistema ML avanzado.

REQUISITOS:
- Modelo base (cotizaciones_predictor.pkl) debe estar entrenado
- Mínimo 20 cotizaciones rechazadas con observaciones

CÓMO EJECUTAR:
cd C:/Users/chavo/mi_proyecto_django
.\venv\Scripts\Activate.ps1
python scripts/ml/entrenar_predictor_motivos.py

EXPLICACIÓN PARA PRINCIPIANTES:
Este modelo es diferente al modelo base. Mientras que el modelo base predice
SI/NO (será aceptada o rechazada), este modelo predice el MOTIVO específico
del rechazo (costo alto, tiempo largo, etc.). Es como tener un consultor que
no solo dice "fracasarás", sino "fracasarás POR ESTA RAZÓN".
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime

# Configurar Django
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.ml_advanced import PredictorMotivoRechazo
from servicio_tecnico.models import Cotizacion


def verificar_requisitos():
    """
    Verifica que se cumplan los requisitos para entrenar el modelo de motivos.
    
    Returns:
        bool: True si se puede entrenar, False si no
    """
    
    print("\n" + "="*80)
    print("VERIFICACIÓN DE REQUISITOS")
    print("="*80)
    
    # 1. Verificar que existe el modelo base
    modelo_base_path = BASE_DIR / 'ml_models' / 'cotizaciones_predictor.pkl'
    if not modelo_base_path.exists():
        print("❌ FALTA MODELO BASE")
        print(f"   No se encontró: {modelo_base_path}")
        print("   Ejecuta primero: python scripts/ml/reentrenar_modelo_cotizaciones.py")
        return False
    else:
        print(f"✅ Modelo base encontrado: {modelo_base_path}")
    
    # 2. Verificar datos disponibles
    total_cotizaciones = Cotizacion.objects.count()
    rechazadas = Cotizacion.objects.filter(usuario_acepto=False).count()
    
    print(f"\n📊 DATOS DISPONIBLES:")
    print(f"   Total cotizaciones: {total_cotizaciones}")
    print(f"   Rechazadas: {rechazadas}")
    
    if rechazadas < 10:
        print(f"\n⚠️ DATOS INSUFICIENTES")
        print(f"   Se necesitan mínimo 10 cotizaciones rechazadas")
        print(f"   Actualmente hay: {rechazadas}")
        print(f"   Faltan: {10 - rechazadas}")
        return False
    elif rechazadas < 30:
        print(f"\n⚠️ DATOS SUFICIENTES PERO LIMITADOS")
        print(f"   Recomendación: 30+ rechazadas para mejor precisión")
        return True
    else:
        print(f"\n✅ DATOS SUFICIENTES: {rechazadas} rechazadas")
        return True


def entrenar_modelo_motivos():
    """
    Entrena el predictor de motivos de rechazo.
    """
    
    print("\n" + "="*80)
    print("ENTRENAMIENTO: PREDICTOR DE MOTIVOS DE RECHAZO")
    print("="*80)
    print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Verificar requisitos
    if not verificar_requisitos():
        print("\n❌ Abortando entrenamiento por requisitos no cumplidos.")
        return False
    
    print("\n" + "-"*80)
    print("🔬 Iniciando entrenamiento del predictor de motivos...")
    print("-"*80)
    
    try:
        # Inicializar predictor de motivos
        predictor = PredictorMotivoRechazo()
        
        # Entrenar modelo
        print("\n📈 Entrenando modelo multiclase (5 motivos posibles)...")
        metricas = predictor.entrenar()
        
        print("\n" + "="*80)
        print("✅ ENTRENAMIENTO COMPLETADO EXITOSAMENTE")
        print("="*80)
        print(f"Accuracy (Precisión General): {metricas['accuracy']*100:.2f}%")
        print(f"Precision (Macro): {metricas['precision']*100:.2f}%")
        print(f"Recall (Macro): {metricas['recall']*100:.2f}%")
        print(f"F1-Score (Macro): {metricas['f1_score']*100:.2f}%")
        print(f"\nTotal de muestras: {metricas['total_muestras']}")
        print(f"Muestras entrenamiento: {metricas['muestras_entrenamiento']}")
        print(f"Muestras prueba: {metricas['muestras_prueba']}")
        
        print("\n📊 Distribución por motivo:")
        for motivo, count in metricas['distribucion_motivos'].items():
            print(f"   - {motivo}: {count} casos")
        
        print(f"\n💾 Modelo guardado en: ml_models/motivos_predictor.pkl")
        print("="*80)
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR durante el entrenamiento: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """
    Función principal.
    """
    
    print("\n" + "="*80)
    print("SCRIPT: ENTRENAR PREDICTOR DE MOTIVOS DE RECHAZO")
    print("Parte del Sistema ML Avanzado de Cotizaciones")
    print("="*80)
    
    exito = entrenar_modelo_motivos()
    
    if exito:
        print("\n✅ SUCCESS: Predictor de motivos entrenado correctamente.")
        print("   El dashboard ahora puede identificar motivos específicos de rechazo.")
    else:
        print("\n❌ FAILED: No se pudo entrenar el predictor de motivos.")
        print("   Revisa los errores y asegúrate de tener datos suficientes.")
    
    print("\n" + "="*80)


if __name__ == '__main__':
    main()
