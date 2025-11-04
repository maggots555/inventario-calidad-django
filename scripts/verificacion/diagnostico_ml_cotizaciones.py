# -*- coding: utf-8 -*-
"""
Script de Diagnostico: Machine Learning Dashboard Cotizaciones

PROPOSITO:
Este script valida dos problemas reportados:
1. Por que aparece 89.7% como precision del modelo ML?
2. Por que dice "No hay cotizaciones pendientes" cuando supuestamente hay?

COMO EJECUTAR:
cd C:/Users/DELL/Proyecto_Django/inventario-calidad-django
python scripts/verificacion/diagnostico_ml_cotizaciones.py

EXPLICACION PARA PRINCIPIANTES:
Este script consulta la base de datos y el modelo ML para entender
que esta pasando con los datos y las predicciones.
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

# Ahora sí importar modelos
from servicio_tecnico.models import Cotizacion
from servicio_tecnico.utils_cotizaciones import obtener_dataframe_cotizaciones
from servicio_tecnico.ml_predictor import PredictorAceptacionCotizacion
import pandas as pd
from datetime import datetime, timedelta


def validar_datos_cotizaciones():
    """
    Valida el estado de las cotizaciones en la base de datos.
    
    EXPLICACIÓN:
    Verifica cuántas cotizaciones hay y su estado de aceptación.
    El campo 'usuario_acepto' puede ser:
    - True: Cliente aceptó la cotización
    - False: Cliente rechazó la cotización
    - None: Cliente NO ha respondido (pendiente)
    """
    
    print("\n" + "="*80)
    print("📊 DIAGNÓSTICO: ESTADO DE COTIZACIONES EN BASE DE DATOS")
    print("="*80)
    
    # Total de cotizaciones
    total = Cotizacion.objects.count()
    print(f"\n✅ Total de cotizaciones en BD: {total}")
    
    # Cotizaciones aceptadas
    aceptadas = Cotizacion.objects.filter(usuario_acepto=True).count()
    print(f"✅ Cotizaciones ACEPTADAS (usuario_acepto=True): {aceptadas}")
    
    # Cotizaciones rechazadas
    rechazadas = Cotizacion.objects.filter(usuario_acepto=False).count()
    print(f"❌ Cotizaciones RECHAZADAS (usuario_acepto=False): {rechazadas}")
    
    # Cotizaciones pendientes (sin respuesta)
    pendientes = Cotizacion.objects.filter(usuario_acepto__isnull=True).count()
    print(f"⏳ Cotizaciones PENDIENTES (usuario_acepto=None): {pendientes}")
    
    # Validar suma
    suma = aceptadas + rechazadas + pendientes
    print(f"\n🔍 Validación: {aceptadas} + {rechazadas} + {pendientes} = {suma}")
    if suma == total:
        print("✅ ¡Correcto! La suma cuadra con el total.")
    else:
        print(f"⚠️ Error: La suma ({suma}) no coincide con el total ({total})")
    
    # Últimas 10 cotizaciones
    print("\n" + "-"*80)
    print("📋 ÚLTIMAS 10 COTIZACIONES:")
    print("-"*80)
    ultimas = Cotizacion.objects.select_related('orden').order_by('-fecha_envio')[:10]
    
    if ultimas:
        for i, cot in enumerate(ultimas, 1):
            estado = "Aceptada" if cot.usuario_acepto == True else "Rechazada" if cot.usuario_acepto == False else "PENDIENTE"
            icono = "✅" if cot.usuario_acepto == True else "❌" if cot.usuario_acepto == False else "⏳"
            print(f"{i:2}. {icono} ID: {cot.orden_id} | Orden: {cot.orden.numero_orden_interno} | Estado: {estado} | Fecha: {cot.fecha_envio.strftime('%Y-%m-%d %H:%M')}")
    else:
        print("⚠️ No hay cotizaciones en la base de datos.")
    
    return {
        'total': total,
        'aceptadas': aceptadas,
        'rechazadas': rechazadas,
        'pendientes': pendientes,
        'ultimas': list(ultimas)
    }


def validar_dataframe_cotizaciones():
    """
    Valida cómo se están procesando las cotizaciones en el DataFrame.
    
    EXPLICACIÓN:
    El dashboard usa Pandas DataFrame para procesar datos.
    Verifica si el DataFrame refleja correctamente los datos de la BD.
    """
    
    print("\n" + "="*80)
    print("📊 DIAGNÓSTICO: DATAFRAME DE COTIZACIONES (últimos 90 días)")
    print("="*80)
    
    # Obtener DataFrame con filtros por defecto (últimos 90 días)
    fecha_fin = datetime.now().date()
    fecha_inicio = (datetime.now() - timedelta(days=90)).date()
    
    df = obtener_dataframe_cotizaciones(
        fecha_inicio=fecha_inicio.strftime('%Y-%m-%d'),
        fecha_fin=fecha_fin.strftime('%Y-%m-%d')
    )
    
    print(f"\n📅 Rango de fechas: {fecha_inicio} a {fecha_fin}")
    print(f"✅ Total de cotizaciones en DataFrame: {len(df)}")
    
    if not df.empty:
        # Analizar columna 'aceptada'
        aceptadas_df = len(df[df['aceptada'] == True])
        rechazadas_df = len(df[df['aceptada'] == False])
        pendientes_df = len(df[df['aceptada'].isna()])
        
        print(f"\nDistribución en DataFrame:")
        print(f"  ✅ Aceptadas (True): {aceptadas_df}")
        print(f"  ❌ Rechazadas (False): {rechazadas_df}")
        print(f"  ⏳ Pendientes (None/NaN): {pendientes_df}")
        
        # Validar suma
        suma_df = aceptadas_df + rechazadas_df + pendientes_df
        print(f"\n🔍 Validación: {aceptadas_df} + {rechazadas_df} + {pendientes_df} = {suma_df}")
        if suma_df == len(df):
            print("✅ ¡Correcto! La suma cuadra con el total del DataFrame.")
        else:
            print(f"⚠️ Error: La suma ({suma_df}) no coincide con el total ({len(df)})")
        
        # Mostrar muestra de cotizaciones pendientes
        if pendientes_df > 0:
            print("\n" + "-"*80)
            print(f"📋 MUESTRA DE COTIZACIONES PENDIENTES (primeras 5):")
            print("-"*80)
            df_pendientes = df[df['aceptada'].isna()].head(5)
            for idx, row in df_pendientes.iterrows():
                print(f"  ⏳ Orden: {row['numero_orden']} | Costo: ${row['costo_total']:,.2f} | Piezas: {row['total_piezas']} | Fecha: {row['fecha_envio']}")
        else:
            print("\n⚠️ No hay cotizaciones pendientes en el DataFrame (últimos 90 días)")
        
        return df
    else:
        print("\n⚠️ El DataFrame está vacío. No hay cotizaciones en los últimos 90 días.")
        return df


def validar_modelo_ml():
    """
    Valida el estado del modelo de Machine Learning.
    
    EXPLICACIÓN:
    Revisa si existe un modelo entrenado, cuándo fue entrenado,
    y cuáles son sus métricas de precisión.
    """
    
    print("\n" + "="*80)
    print("🤖 DIAGNÓSTICO: MODELO DE MACHINE LEARNING")
    print("="*80)
    
    predictor = PredictorAceptacionCotizacion()
    
    # Verificar si existe modelo guardado
    if predictor.model_path.exists():
        print(f"\n✅ Modelo encontrado en: {predictor.model_path}")
        print(f"   Tamaño del archivo: {predictor.model_path.stat().st_size / 1024:.2f} KB")
        print(f"   Última modificación: {datetime.fromtimestamp(predictor.model_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Cargar modelo
        try:
            predictor.cargar_modelo()
            print("\n✅ Modelo cargado exitosamente")
            
            # Obtener métricas
            metricas = predictor.obtener_metricas()
            
            print("\n" + "-"*80)
            print("📊 MÉTRICAS DEL MODELO GUARDADO:")
            print("-"*80)
            
            if metricas:
                print(f"  🎯 Accuracy (Precisión General): {metricas.get('accuracy', 0)*100:.2f}%")
                print(f"  📊 Precision (Acierto en positivos): {metricas.get('precision', 0)*100:.2f}%")
                print(f"  📈 Recall (Cobertura): {metricas.get('recall', 0)*100:.2f}%")
                print(f"  ⚖️  F1-Score (Balance): {metricas.get('f1_score', 0)*100:.2f}%")
                print(f"  📚 Total de muestras: {metricas.get('total_muestras', 0)}")
                print(f"  🏋️  Muestras de entrenamiento: {metricas.get('muestras_entrenamiento', 0)}")
                print(f"  🧪 Muestras de prueba: {metricas.get('muestras_prueba', 0)}")
                print(f"  📅 Fecha de entrenamiento: {metricas.get('fecha_entrenamiento', 'Desconocida')}")
                
                # ESTE ES EL PUNTO CRÍTICO: De aquí viene el 89.7%
                accuracy_pct = metricas.get('accuracy', 0) * 100
                print(f"\n💡 EXPLICACIÓN: El {accuracy_pct:.1f}% viene de este modelo pre-entrenado.")
                
                # Feature importance
                if 'feature_importance' in metricas:
                    print("\n" + "-"*80)
                    print("🔝 TOP 5 FACTORES MÁS IMPORTANTES:")
                    print("-"*80)
                    for i, feat in enumerate(metricas['feature_importance'][:5], 1):
                        print(f"  {i}. {feat['feature']}: {feat['importance']:.4f}")
                
                return metricas
            else:
                print("⚠️ No se pudieron obtener métricas del modelo.")
                return None
        
        except Exception as e:
            print(f"\n❌ Error al cargar modelo: {str(e)}")
            return None
    else:
        print(f"\n⚠️ No existe modelo pre-entrenado en: {predictor.model_path}")
        print("   El modelo se entrenará automáticamente cuando haya suficientes datos.")
        return None


def validar_predicciones_ejemplo():
    """
    Simula la lógica del dashboard para generar predicción de ejemplo.
    
    EXPLICACIÓN:
    Reproduce exactamente lo que hace views.py en la línea 7680
    para determinar si hay cotizaciones pendientes para predecir.
    """
    
    print("\n" + "="*80)
    print("🎯 DIAGNÓSTICO: LÓGICA DE PREDICCIÓN DE EJEMPLO")
    print("="*80)
    
    # Obtener DataFrame (últimos 90 días, como en el dashboard)
    fecha_fin = datetime.now().date()
    fecha_inicio = (datetime.now() - timedelta(days=90)).date()
    
    df_cotizaciones = obtener_dataframe_cotizaciones(
        fecha_inicio=fecha_inicio.strftime('%Y-%m-%d'),
        fecha_fin=fecha_fin.strftime('%Y-%m-%d')
    )
    
    print(f"\n📅 Rango de fechas del dashboard: {fecha_inicio} a {fecha_fin}")
    print(f"✅ Total cotizaciones en DataFrame: {len(df_cotizaciones)}")
    
    if not df_cotizaciones.empty:
        # Esta es la línea crítica (línea 7680 de views.py)
        df_pendientes = df_cotizaciones[df_cotizaciones['aceptada'].isna()]
        
        print(f"\n🔍 Filtro aplicado: df_cotizaciones[df_cotizaciones['aceptada'].isna()]")
        print(f"⏳ Cotizaciones pendientes encontradas: {len(df_pendientes)}")
        
        if not df_pendientes.empty:
            print("\n✅ ¡SÍ HAY COTIZACIONES PENDIENTES!")
            print("\n" + "-"*80)
            print("📋 TODAS LAS COTIZACIONES PENDIENTES:")
            print("-"*80)
            
            for idx, row in df_pendientes.iterrows():
                print(f"  Orden: {row['numero_orden']:15} | Costo: ${row['costo_total']:10,.2f} | Piezas: {row['total_piezas']:2} | Fecha: {row['fecha_envio']}")
            
            # Última cotización (la que usaría el dashboard)
            ultima = df_pendientes.iloc[-1]
            print("\n" + "-"*80)
            print("🎯 ÚLTIMA COTIZACIÓN PENDIENTE (usada para ejemplo):")
            print("-"*80)
            print(f"  📦 Orden: {ultima['numero_orden']}")
            print(f"  💰 Costo Total: ${ultima['costo_total']:,.2f}")
            print(f"  🔧 Total Piezas: {ultima['total_piezas']}")
            print(f"  📅 Fecha Envío: {ultima['fecha_envio']}")
            print(f"  🏢 Sucursal: {ultima['sucursal']}")
            print(f"  👨‍🔧 Técnico: {ultima['tecnico']}")
            print(f"  ⭐ Gama: {ultima['gama']}")
            
            # Intentar predecir
            try:
                predictor = PredictorAceptacionCotizacion()
                predictor.cargar_modelo()
                
                features_ejemplo = {
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
                
                prob_rechazo, prob_aceptacion = predictor.predecir_probabilidad(features_ejemplo)
                
                print("\n" + "-"*80)
                print("🤖 PREDICCIÓN DEL MODELO:")
                print("-"*80)
                print(f"  ✅ Probabilidad de ACEPTACIÓN: {prob_aceptacion*100:.2f}%")
                print(f"  ❌ Probabilidad de RECHAZO: {prob_rechazo*100:.2f}%")
                
            except Exception as e:
                print(f"\n⚠️ No se pudo generar predicción: {str(e)}")
        else:
            print("\n❌ NO HAY COTIZACIONES PENDIENTES")
            print("\n💡 POSIBLES RAZONES:")
            print("  1. Todas las cotizaciones de los últimos 90 días han sido respondidas")
            print("  2. Las cotizaciones sin respuesta son más antiguas (>90 días)")
            print("  3. No hay cotizaciones en ese rango de fechas")
            
            # Verificar si hay pendientes fuera del rango
            print("\n🔍 Verificando cotizaciones pendientes FUERA del rango de 90 días...")
            pendientes_totales = Cotizacion.objects.filter(usuario_acepto__isnull=True).count()
            print(f"⏳ Total cotizaciones pendientes en TODA la BD: {pendientes_totales}")
            
            if pendientes_totales > 0:
                print("\n✅ ¡Hay cotizaciones pendientes, pero están fuera del rango de 90 días!")
                print("   Para verlas, ajusta los filtros de fecha en el dashboard.")
                
                # Mostrar las más recientes
                pendientes = Cotizacion.objects.filter(usuario_acepto__isnull=True).select_related('orden').order_by('-fecha_envio')[:5]
                print("\n📋 Cotizaciones pendientes más recientes (top 5):")
                for cot in pendientes:
                    dias_desde = (datetime.now().date() - cot.fecha_envio.date()).days
                    print(f"  ⏳ Orden: {cot.orden.numero_orden_interno} | Fecha: {cot.fecha_envio.strftime('%Y-%m-%d')} | Hace {dias_desde} días")
    else:
        print("\n⚠️ El DataFrame está vacío (no hay cotizaciones en los últimos 90 días)")


def generar_recomendaciones():
    """
    Genera recomendaciones basadas en los hallazgos.
    """
    
    print("\n" + "="*80)
    print("💡 RECOMENDACIONES Y SOLUCIONES")
    print("="*80)
    
    print("""
PROBLEMA 1: ¿Por qué aparece 89.7% de precisión?
=================================================

EXPLICACIÓN:
El 89.7% proviene de un modelo pre-entrenado que fue guardado anteriormente
en ml_models/cotizaciones_predictor.pkl. Este modelo fue entrenado con datos
históricos y sus métricas quedaron guardadas.

CÓMO MEJORAR LA PRECISIÓN:
---------------------------
1. ✅ Más datos de entrenamiento:
   - Actualmente el modelo usa datos históricos limitados
   - Mientras más cotizaciones con respuesta haya, mejor será la precisión
   - Objetivo: Tener al menos 100-200 cotizaciones con respuesta

2. ✅ Re-entrenar periódicamente:
   - El modelo se entrena una vez y queda estático
   - Deberías re-entrenar cada mes o cuando haya +50 cotizaciones nuevas
   - Comando: Crear una tarea programada para re-entrenar

3. ✅ Mejorar features (variables):
   - El modelo usa variables como costo_total, total_piezas, gama, etc.
   - Podrías agregar: historial del cliente, temporalidad, etc.

4. ✅ Ajustar hiperparámetros:
   - En ml_predictor.py línea 64, hay parámetros configurables
   - n_estimators: Número de árboles (actualmente 100)
   - max_depth: Profundidad máxima (actualmente 10)
   - Experimentar con valores más altos puede mejorar precisión


PROBLEMA 2: "No hay cotizaciones pendientes para predecir"
===========================================================

EXPLICACIÓN:
El dashboard por defecto filtra los últimos 90 días. Si NO hay cotizaciones
pendientes en ese rango, muestra el mensaje.

SOLUCIONES:
-----------
1. ✅ Ajustar el filtro de fechas:
   - En el dashboard, amplía el rango de fechas para incluir más meses
   - O busca en el rango específico donde sabes que hay pendientes

2. ✅ Verificar el estado de las cotizaciones:
   - Confirma que las cotizaciones realmente estén pendientes (usuario_acepto=None)
   - Revisa si hay algún proceso que esté marcando automáticamente como respondidas

3. ✅ Modificar el comportamiento por defecto:
   - Cambiar de 90 días a 180 días o 1 año
   - Editar línea 7494 de views.py:
     fecha_inicio_default = (datetime.now() - timedelta(days=180)).date()


VERIFICACIÓN RÁPIDA:
====================
- Total cotizaciones en BD: [Ver arriba]
- Cotizaciones pendientes: [Ver arriba]
- Modelo ML cargado: [Ver arriba]
- Precisión actual: [Ver arriba]
    """)


def main():
    """
    Ejecuta todos los diagnósticos.
    """
    
    print("\n" + "="*80)
    print("🔍 INICIANDO DIAGNÓSTICO COMPLETO")
    print("="*80)
    print(f"Fecha/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 1. Validar datos en BD
    resultado_bd = validar_datos_cotizaciones()
    
    # 2. Validar DataFrame
    df = validar_dataframe_cotizaciones()
    
    # 3. Validar modelo ML
    metricas = validar_modelo_ml()
    
    # 4. Validar lógica de predicción
    validar_predicciones_ejemplo()
    
    # 5. Generar recomendaciones
    generar_recomendaciones()
    
    print("\n" + "="*80)
    print("✅ DIAGNÓSTICO COMPLETADO")
    print("="*80)


if __name__ == '__main__':
    main()
