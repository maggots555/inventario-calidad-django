# -*- coding: utf-8 -*-
"""
Script: Re-entrenar Modelo de Machine Learning para Cotizaciones

PROPOSITO:
Re-entrena el modelo ML con los datos mas recientes para mejorar la precision.

CUANDO EJECUTAR:
- Cada mes (tarea programada)
- Despues de acumular +50 cotizaciones nuevas con respuesta
- Cuando la precision baje significativamente

COMO EJECUTAR:
cd C:/Users/DELL/Proyecto_Django/inventario-calidad-django
.venv/Scripts/activate
python scripts/ml/reentrenar_modelo_cotizaciones.py

EXPLICACION PARA PRINCIPIANTES:
El modelo ML aprende de datos historicos. A medida que se acumulan mas
cotizaciones con respuesta, el modelo puede mejorar su precision si lo re-entrenas.
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

from servicio_tecnico.ml_predictor import PredictorAceptacionCotizacion
from servicio_tecnico.models import Cotizacion


def verificar_datos_disponibles():
    """
    Verifica si hay suficientes datos para entrenar el modelo.
    
    Minimo requerido: 20 cotizaciones con respuesta
    Recomendado: 100+ cotizaciones con respuesta
    """
    
    total = Cotizacion.objects.count()
    con_respuesta = Cotizacion.objects.filter(usuario_acepto__isnull=False).count()
    aceptadas = Cotizacion.objects.filter(usuario_acepto=True).count()
    rechazadas = Cotizacion.objects.filter(usuario_acepto=False).count()
    
    print("\n" + "="*80)
    print("DATOS DISPONIBLES PARA ENTRENAMIENTO")
    print("="*80)
    print(f"Total cotizaciones: {total}")
    print(f"Con respuesta (aceptadas o rechazadas): {con_respuesta}")
    print(f"  - Aceptadas: {aceptadas}")
    print(f"  - Rechazadas: {rechazadas}")
    print("-"*80)
    
    if con_respuesta < 20:
        print(f"INSUFICIENTES: Se necesitan minimo 20 cotizaciones con respuesta.")
        print(f"Faltan: {20 - con_respuesta} cotizaciones")
        return False
    elif con_respuesta < 100:
        print(f"SUFICIENTES PERO BAJOS: {con_respuesta} cotizaciones.")
        print(f"Recomendacion: Esperar a tener 100+ para mejor precision.")
        return True
    else:
        print(f"EXCELENTE: {con_respuesta} cotizaciones con respuesta.")
        return True


def reentrenar_modelo():
    """
    Re-entrena el modelo con todos los datos disponibles.
    """
    
    print("\n" + "="*80)
    print("RE-ENTRENAMIENTO DEL MODELO ML")
    print("="*80)
    print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Verificar datos disponibles
    if not verificar_datos_disponibles():
        print("\nAbortando entrenamiento por datos insuficientes.")
        return False
    
    print("\nIniciando entrenamiento...")
    print("-"*80)
    
    try:
        # Inicializar predictor
        predictor = PredictorAceptacionCotizacion()
        
        # Entrenar con todos los datos (sin filtros de fecha)
        metricas = predictor.entrenar_modelo()
        
        print("\n" + "="*80)
        print("ENTRENAMIENTO COMPLETADO EXITOSAMENTE")
        print("="*80)
        print(f"Accuracy (Precision General): {metricas['accuracy']*100:.2f}%")
        print(f"Precision (Acierto en positivos): {metricas['precision']*100:.2f}%")
        print(f"Recall (Cobertura): {metricas['recall']*100:.2f}%")
        print(f"F1-Score (Balance): {metricas['f1_score']*100:.2f}%")
        print(f"Total de muestras: {metricas['total_muestras']}")
        print(f"Muestras de entrenamiento: {metricas['muestras_entrenamiento']}")
        print(f"Muestras de prueba: {metricas['muestras_prueba']}")
        
        print("\nTop 5 Factores Mas Influyentes:")
        for i, feat in enumerate(metricas['feature_importance'][:5], 1):
            print(f"  {i}. {feat['feature']}: {feat['importance']:.4f}")
        
        print("\nModelo guardado en: ml_models/cotizaciones_predictor.pkl")
        print("="*80)
        
        return True
        
    except Exception as e:
        print(f"\nERROR durante el entrenamiento: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """
    Funcion principal.
    """
    
    print("\n" + "="*80)
    print("SCRIPT: RE-ENTRENAR MODELO ML DE COTIZACIONES")
    print("="*80)
    
    exito = reentrenar_modelo()
    
    if exito:
        print("\nSUCCESS: Modelo re-entrenado correctamente.")
        print("El dashboard de cotizaciones ahora usara este modelo actualizado.")
    else:
        print("\nFAILED: No se pudo re-entrenar el modelo.")
        print("Revisa los errores arriba y verifica que haya datos suficientes.")
    
    print("\n" + "="*80)


if __name__ == '__main__':
    main()
