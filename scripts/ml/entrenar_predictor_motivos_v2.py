# -*- coding: utf-8 -*-
"""
Script: Entrenar Predictor de Motivos de Rechazo - VERSIÓN MEJORADA

PROPÓSITO:
Entrena la versión mejorada del modelo con análisis NLP y features avanzadas.

MEJORAS vs versión anterior:
1. ✅ Procesamiento de texto NLP del campo detalle_rechazo
2. ✅ Features adicionales: marca, modelo, sucursal
3. ✅ Manejo de clases desbalanceadas con class_weight
4. ✅ Mejores hiperparámetros de RandomForest
5. ✅ Motivos actualizados (11 categorías reales)
6. ✅ Features de piezas individuales

PRECISION ESPERADA: 50-60% (mejora de ~15-20% vs versión anterior 37.78%)

CÓMO EJECUTAR:
cd /home/maggots555/Proyecto\ Django/inventario-calidad-django
python3 scripts/ml/entrenar_predictor_motivos_v2.py

REQUISITOS:
- Modelo base (cotizaciones_predictor.pkl) debe estar entrenado
- Mínimo 20 cotizaciones rechazadas con observaciones
- Scikit-learn instalado

EXPLICACIÓN PARA PRINCIPIANTES:
Esta versión mejorada del modelo analiza más información para predecir mejor
el motivo de rechazo. Es como darle al modelo mejores "ojos" para ver patrones.

Cambios principales:
- ANTES: Solo veía números (costo, cantidad de piezas)
- AHORA: Lee también el texto del rechazo, marca del equipo, sucursal, etc.
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

from servicio_tecnico.ml_advanced.motivo_rechazo_mejorado import PredictorMotivoRechazoMejorado
from servicio_tecnico.models import Cotizacion


def verificar_requisitos():
    """
    Verifica que se cumplan los requisitos para entrenar el modelo de motivos.
    
    Returns:
        bool: True si se puede entrenar, False si no
    """
    
    print("\n" + "="*80)
    print("VERIFICACIÓN DE REQUISITOS - VERSIÓN MEJORADA")
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
    
    # 3. Verificar datos con detalle_rechazo (importante para NLP)
    con_detalle = Cotizacion.objects.filter(
        usuario_acepto=False,
        detalle_rechazo__isnull=False
    ).exclude(detalle_rechazo='').count()
    
    print(f"\n📊 DATOS DISPONIBLES:")
    print(f"   Total cotizaciones: {total_cotizaciones}")
    print(f"   Rechazadas: {rechazadas}")
    print(f"   Con detalle de rechazo (para NLP): {con_detalle}")
    
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
        
    # Info adicional sobre NLP
    if con_detalle < rechazadas * 0.5:
        print(f"\n⚠️ ADVERTENCIA: Solo {con_detalle} de {rechazadas} tienen detalle de rechazo")
        print(f"   El análisis NLP será menos efectivo")
        print(f"   Recomendación: Agregar detalles de rechazo en futuras cotizaciones")
    else:
        print(f"\n✅ {con_detalle} cotizaciones con detalle para análisis NLP")
    
    return True


def entrenar_modelo_motivos_mejorado():
    """
    Entrena el predictor de motivos de rechazo - VERSIÓN MEJORADA.
    """
    
    print("\n" + "="*80)
    print("ENTRENAMIENTO: PREDICTOR DE MOTIVOS DE RECHAZO - VERSIÓN MEJORADA v2")
    print("="*80)
    print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    print("MEJORAS IMPLEMENTADAS:")
    print("  ✅ Procesamiento de texto NLP del campo detalle_rechazo")
    print("  ✅ Features adicionales: marca, modelo, sucursal")
    print("  ✅ Manejo de clases desbalanceadas mejorado")
    print("  ✅ 40+ features (vs 21 anterior)")
    print("  ✅ Hiperparámetros optimizados")
    print()
    
    # Verificar requisitos
    if not verificar_requisitos():
        print("\n❌ Abortando entrenamiento por requisitos no cumplidos.")
        return False
    
    print("\n" + "-"*80)
    print("🔬 Iniciando entrenamiento del predictor MEJORADO...")
    print("-"*80)
    
    try:
        # Inicializar predictor de motivos MEJORADO
        predictor = PredictorMotivoRechazoMejorado()
        
        # Entrenar modelo
        print("\n📈 Entrenando modelo multiclase con NLP (11 motivos posibles)...")
        metricas = predictor.entrenar()
        
        print("\n" + "="*80)
        print("✅ ENTRENAMIENTO COMPLETADO EXITOSAMENTE - VERSIÓN MEJORADA")
        print("="*80)
        
        # Comparación con versión anterior
        accuracy_anterior = 0.3778  # 37.78% de la versión anterior
        accuracy_nueva = metricas['accuracy']
        mejora_absoluta = accuracy_nueva - accuracy_anterior
        mejora_relativa = (mejora_absoluta / accuracy_anterior) * 100 if accuracy_anterior > 0 else 0
        
        print(f"\n📊 COMPARACIÓN CON VERSIÓN ANTERIOR:")
        print(f"   Versión Anterior:  {accuracy_anterior:.2%}")
        print(f"   Versión Mejorada:  {accuracy_nueva:.2%}")
        if mejora_absoluta > 0:
            print(f"   ✅ MEJORA: +{mejora_absoluta:.2%} ({mejora_relativa:+.1f}% relativo)")
        else:
            print(f"   ⚠️ Sin mejora significativa: {mejora_absoluta:.2%}")
        
        print(f"\n📈 MÉTRICAS PRINCIPALES:")
        print(f"   Accuracy:  {metricas['accuracy']*100:.2f}%")
        print(f"   Precision: {metricas['precision']*100:.2f}%")
        print(f"   Recall:    {metricas['recall']*100:.2f}%")
        print(f"   F1-Score:  {metricas['f1_score']*100:.2f}%")
        
        # Información de muestras
        print(f"\n📊 DATOS DE ENTRENAMIENTO:")
        print(f"   Total de muestras:         {metricas.get('total_muestras', 'N/A')}")
        print(f"   Muestras entrenamiento:    {metricas.get('muestras_entrenamiento', 'N/A')}")
        print(f"   Muestras prueba:           {metricas.get('muestras_prueba', 'N/A')}")
        
        # Mostrar motivos detectados
        if 'motivos_detectados' in metricas:
            print(f"\n🎯 Motivos Detectados: {len(metricas['motivos_detectados'])}")
            for motivo in metricas['motivos_detectados']:
                print(f"   - {motivo}")
        
        # Distribución por motivo
        if 'distribucion_motivos' in metricas:
            print("\n📈 Distribución de Motivos en Dataset:")
            for motivo, count in sorted(metricas['distribucion_motivos'].items(), 
                                       key=lambda x: x[1], reverse=True):
                porcentaje = (count / metricas['total_muestras']) * 100
                print(f"   - {motivo:30s}: {count:4d} casos ({porcentaje:5.1f}%)")
        
        # Mostrar top features importantes (separar NLP de numéricas)
        if 'feature_importance' in metricas and len(metricas['feature_importance']) > 0:
            print("\n🔝 Top 10 Features Más Importantes:")
            for i, feat in enumerate(metricas['feature_importance'][:10], 1):
                feature_name = feat['feature']
                is_text = feature_name.startswith('texto_')
                tipo = "📝 Texto NLP" if is_text else "📊 Numérica  "
                print(f"   {i:2d}. {tipo} | {feature_name:35s} | {feat['importance']:.4f}")
        
        # Rendimiento por motivo
        if 'reporte_clasificacion' in metricas:
            print("\n📊 Rendimiento por Motivo (F1-Score):")
            reporte = metricas['reporte_clasificacion']
            # Ordenar por F1-score
            motivos_ordenados = [
                (motivo, metricas_motivo) 
                for motivo, metricas_motivo in reporte.items()
                if isinstance(metricas_motivo, dict) and 'f1-score' in metricas_motivo
            ]
            motivos_ordenados.sort(key=lambda x: x[1]['f1-score'], reverse=True)
            
            for motivo, metricas_motivo in motivos_ordenados[:8]:
                f1 = metricas_motivo['f1-score']
                precision = metricas_motivo['precision']
                recall = metricas_motivo['recall']
                support = metricas_motivo['support']
                
                # Emoji según rendimiento
                if f1 >= 0.6:
                    emoji = "🟢"
                elif f1 >= 0.4:
                    emoji = "🟡"
                else:
                    emoji = "🔴"
                
                print(f"   {emoji} {motivo:30s} | F1: {f1:.2%} | P: {precision:.2%} | R: {recall:.2%} | N={int(support)}")
        
        print(f"\n💾 Modelo guardado en: ml_models/motivos_predictor_v2.pkl")
        print(f"💾 Encoders y TF-IDF: ml_models/motivos_predictor_v2_encoders.pkl")
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
    print("SCRIPT: ENTRENAR PREDICTOR DE MOTIVOS DE RECHAZO - VERSIÓN MEJORADA v2")
    print("Parte del Sistema ML Avanzado de Cotizaciones")
    print("="*80)
    
    exito = entrenar_modelo_motivos_mejorado()
    
    if exito:
        print("\n✅ SUCCESS: Predictor de motivos MEJORADO entrenado correctamente.")
        print("   El dashboard ahora puede identificar motivos con MAYOR PRECISIÓN.")
        print("\n🎯 PRÓXIMOS PASOS:")
        print("   1. Revisar el rendimiento por motivo arriba")
        print("   2. Si algún motivo tiene F1 < 30%, considera combinar categorías")
        print("   3. Agregar más detalles de rechazo en futuras cotizaciones")
        print("   4. Re-entrenar mensualmente con datos nuevos")
    else:
        print("\n❌ FAILED: No se pudo entrenar el predictor mejorado.")
        print("   Revisa los errores y asegúrate de tener datos suficientes.")
    
    print("\n" + "="*80)


if __name__ == '__main__':
    main()
