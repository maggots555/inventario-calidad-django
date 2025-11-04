"""
Predictor de Aceptación de Cotizaciones con Machine Learning
Utiliza Random Forest para predecir si una cotizacíón será aceptada o rechazada

EXPLICACIÓN PARA PRINCIPIANTES:
Machine Learning = El programa "aprende" de datos históricos para hacer predicciones.
Random Forest = Algoritmo que crea muchos "árboles de decisión" y los combina para
               hacer predicciones más precisas.

Este módulo NO requiere GPU, funciona perfecto en CPU normal.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import (
    accuracy_score, 
    precision_score, 
    recall_score, 
    f1_score,
    classification_report,
    confusion_matrix
)
import joblib
import os
from pathlib import Path
from datetime import datetime

from .models import Cotizacion, PiezaCotizada
from .utils_cotizaciones import obtener_dataframe_cotizaciones


class PredictorAceptacionCotizacion:
    """
    Modelo de Machine Learning para predecir si una cotización será aceptada.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta clase encapsula todo el proceso de Machine Learning:
    1. Preparar datos (features)
    2. Entrenar modelo
    3. Hacer predicciones
    4. Evaluar precisión
    
    Funciona 100% en CPU, NO requiere GPU.
    """
    
    def __init__(self):
        """
        Inicializa el predictor con configuración por defecto.
        
        Random Forest: Crea 100 "árboles de decisión" que votan juntos.
        n_jobs=-1: Usa todos los cores del CPU para ir más rápido.
        random_state=42: Semilla para reproducibilidad (siempre mismos resultados).
        """
        self.model = RandomForestClassifier(
            n_estimators=100,      # 100 árboles de decisión
            max_depth=10,          # Profundidad máxima (evita overfitting)
            min_samples_split=5,   # Mínimo de muestras para dividir
            min_samples_leaf=2,    # Mínimo de muestras en hoja
            n_jobs=-1,             # Usar todos los cores del CPU
            random_state=42,       # Reproducibilidad
            class_weight='balanced'  # Balance entre aceptadas/rechazadas
        )
        
        # Encoders para variables categóricas
        self.encoders = {
            'gama': LabelEncoder(),
            'sucursal': LabelEncoder(),
            'tipo_equipo': LabelEncoder(),
        }
        
        # Estado del modelo
        self.is_trained = False
        self.feature_names = []
        self.metricas_entrenamiento = {}
        
        # Rutas de archivos
        self.model_dir = Path('ml_models')
        self.model_path = self.model_dir / 'cotizaciones_predictor.pkl'
        self.encoders_path = self.model_dir / 'cotizaciones_encoders.pkl'
        
        # Crear directorio si no existe
        self.model_dir.mkdir(exist_ok=True)
    
    def preparar_features(self, df):
        """
        Prepara las características (features) para el modelo ML.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Features = Variables que el modelo usa para aprender y predecir.
        Por ejemplo: costo total, número de piezas, gama del equipo, etc.
        
        El modelo aprende patrones como:
        "Si costo > $10,000 Y piezas > 5 Y gama=baja → probabilidad rechazo alta"
        
        Args:
            df (DataFrame): DataFrame con datos de cotizaciones
        
        Returns:
            DataFrame: DataFrame solo con features preparadas para el modelo
        """
        
        # Copiar DataFrame para no modificar el original
        df_features = df.copy()
        
        # ========================================
        # FEATURES NUMÉRICAS (directas)
        # ========================================
        numeric_features = [
            'costo_total',              # Costo total de la cotización
            'costo_mano_obra',          # Costo de mano de obra
            'costo_total_piezas',       # Costo solo de piezas
            'total_piezas',             # Número de piezas cotizadas
            'piezas_necesarias',        # Piezas marcadas como necesarias
            'porcentaje_necesarias',    # % de piezas necesarias
            'piezas_sugeridas_tecnico', # Piezas sugeridas por técnico
        ]
        
        # ========================================
        # FEATURES DERIVADAS (calculadas)
        # ========================================
        
        # 1. Ticket promedio por pieza
        df_features['ticket_por_pieza'] = (
            df_features['costo_total'] / df_features['total_piezas']
        ).fillna(0)
        
        # 2. Porcentaje de mano de obra sobre total
        df_features['porcentaje_mano_obra'] = (
            df_features['costo_mano_obra'] / df_features['costo_total'] * 100
        ).fillna(0)
        
        # 3. Tiene descuento (booleano → numérico)
        df_features['tiene_descuento'] = df_features['descontar_mano_obra'].astype(int)
        
        # 4. Día de la semana (0=Lunes, 6=Domingo)
        # Usar 'fecha' si 'fecha_envio' no existe
        if 'fecha_envio' in df_features.columns:
            fecha_col = 'fecha_envio'
        elif 'fecha' in df_features.columns:
            fecha_col = 'fecha'
        else:
            # Si no hay columna de fecha, usar valor por defecto
            df_features['dia_semana'] = 0
            fecha_col = None
        
        if fecha_col:
            df_features['dia_semana'] = pd.to_datetime(df_features[fecha_col]).dt.dayofweek
        
        # 5. Mes del año
        if fecha_col:
            df_features['mes_envio'] = pd.to_datetime(df_features[fecha_col]).dt.month
        else:
            # Si no hay fecha, usar mes por defecto
            df_features['mes_envio'] = df_features.get('mes', 1)
        
        # ========================================
        # FEATURES CATEGÓRICAS (codificar)
        # ========================================
        
        # EXPLICACIÓN: Label Encoding convierte texto a números
        # Ejemplo: 'alta' → 2, 'media' → 1, 'baja' → 0
        
        for col, encoder in self.encoders.items():
            if col in df_features.columns:
                # Entrenar encoder si no está entrenado
                if not hasattr(encoder, 'classes_'):
                    encoder.fit(df_features[col].fillna('desconocido'))
                
                # Transformar valores
                df_features[f'{col}_encoded'] = encoder.transform(
                    df_features[col].fillna('desconocido')
                )
        
        # ========================================
        # SELECCIONAR FEATURES FINALES
        # ========================================
        
        final_features = [
            # Numéricas originales
            'costo_total',
            'costo_mano_obra',
            'costo_total_piezas',
            'total_piezas',
            'piezas_necesarias',
            'porcentaje_necesarias',
            'piezas_sugeridas_tecnico',
            
            # Derivadas
            'ticket_por_pieza',
            'porcentaje_mano_obra',
            'tiene_descuento',
            'dia_semana',
            'mes_envio',
            
            # Categóricas codificadas
            'gama_encoded',
            'tipo_equipo_encoded',
        ]
        
        # Filtrar solo features que existan
        final_features = [f for f in final_features if f in df_features.columns]
        
        # Guardar nombres de features
        self.feature_names = final_features
        
        # Rellenar valores faltantes con 0
        df_features[final_features] = df_features[final_features].fillna(0)
        
        # ========================================
        # LIMPIAR VALORES INFINITOS Y EXTREMOS
        # ========================================
        # EXPLICACIÓN: Prevenir errores por divisiones por cero o valores muy grandes
        
        # Reemplazar infinitos con 0
        df_features[final_features] = df_features[final_features].replace([np.inf, -np.inf], 0)
        
        # Limitar valores extremos (clip a rango razonable)
        for col in final_features:
            # Si hay valores muy grandes (> 1 millón), limitarlos
            max_val = df_features[col].abs().max()
            if max_val > 1e6:
                # Limitar a rango más razonable
                df_features[col] = df_features[col].clip(-1e6, 1e6)
        
        return df_features[final_features]
    
    def entrenar_modelo(self, fecha_inicio=None, fecha_fin=None):
        """
        Entrena el modelo con datos históricos de cotizaciones.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Entrenar = El modelo "aprende" de cotizaciones pasadas.
        Ve cuáles fueron aceptadas/rechazadas y busca patrones.
        
        TIEMPO ESTIMADO (en CPU normal):
        - 100 cotizaciones: < 1 segundo
        - 1,000 cotizaciones: 2-3 segundos
        - 10,000 cotizaciones: 10-15 segundos
        
        NO REQUIERE GPU ✅
        
        Args:
            fecha_inicio (str): Fecha inicio para datos de entrenamiento
            fecha_fin (str): Fecha fin para datos de entrenamiento
        
        Returns:
            dict: Métricas de evaluación del modelo
        """
        
        print("📊 Obteniendo datos de cotizaciones...")
        
        # Obtener datos históricos
        df = obtener_dataframe_cotizaciones(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )
        
        # Filtrar solo cotizaciones con respuesta (True o False, no None)
        df_con_respuesta = df[df['aceptada'].notna()].copy()
        
        if len(df_con_respuesta) < 20:
            raise ValueError(
                f"❌ Datos insuficientes para entrenar. "
                f"Se necesitan mínimo 20 cotizaciones con respuesta, "
                f"pero solo hay {len(df_con_respuesta)}."
            )
        
        print(f"✅ {len(df_con_respuesta)} cotizaciones con respuesta encontradas")
        
        # Preparar features (X) y target (y)
        print("🔧 Preparando features...")
        X = self.preparar_features(df_con_respuesta)
        y = df_con_respuesta['aceptada'].astype(int)  # True → 1, False → 0
        
        print(f"✅ {len(self.feature_names)} features preparadas")
        print(f"   Features: {', '.join(self.feature_names)}")
        
        # Dividir en entrenamiento (80%) y prueba (20%)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, 
            test_size=0.2, 
            random_state=42,
            stratify=y  # Mantener proporción de clases
        )
        
        print(f"📈 Entrenando modelo con {len(X_train)} muestras...")
        print(f"   Test: {len(X_test)} muestras")
        
        # ENTRENAR MODELO (aquí sucede el "aprendizaje")
        self.model.fit(X_train, y_train)
        
        print("✅ Modelo entrenado exitosamente!")
        
        # Hacer predicciones en conjunto de prueba
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)
        
        # Calcular métricas de evaluación
        metricas = {
            'accuracy': accuracy_score(y_test, y_pred),
            'precision': precision_score(y_test, y_pred, zero_division=0),
            'recall': recall_score(y_test, y_pred, zero_division=0),
            'f1_score': f1_score(y_test, y_pred, zero_division=0),
            'total_muestras': len(df_con_respuesta),
            'muestras_entrenamiento': len(X_train),
            'muestras_prueba': len(X_test),
            'fecha_entrenamiento': datetime.now().isoformat(),
        }
        
        # Matriz de confusión
        cm = confusion_matrix(y_test, y_pred)
        metricas['confusion_matrix'] = cm.tolist()
        
        # Feature importance (importancia de cada variable)
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        metricas['feature_importance'] = feature_importance.to_dict('records')
        
        # Guardar métricas
        self.metricas_entrenamiento = metricas
        self.is_trained = True
        
        # Imprimir resumen
        print("\n" + "="*60)
        print("📊 MÉTRICAS DEL MODELO")
        print("="*60)
        print(f"Accuracy (Precisión General): {metricas['accuracy']:.2%}")
        print(f"Precision (Acierto en positivos): {metricas['precision']:.2%}")
        print(f"Recall (Cobertura): {metricas['recall']:.2%}")
        print(f"F1-Score (Balance): {metricas['f1_score']:.2%}")
        print("\n🔝 Top 5 Features Más Importantes:")
        for i, row in enumerate(feature_importance.head(5).itertuples(), 1):
            print(f"   {i}. {row.feature}: {row.importance:.4f}")
        print("="*60)
        
        # Guardar modelo
        self.guardar_modelo()
        
        return metricas
    
    def predecir_probabilidad(self, cotizacion_features):
        """
        Predice la probabilidad de que una cotización sea aceptada.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Una vez entrenado el modelo, puede predecir nuevas cotizaciones.
        Retorna dos probabilidades que suman 100%:
        - Probabilidad de rechazo
        - Probabilidad de aceptación
        
        TIEMPO: Milisegundos (instantáneo)
        
        Args:
            cotizacion_features (dict): Diccionario con las características de la cotización
        
        Returns:
            tuple: (probabilidad_rechazo, probabilidad_aceptacion)
        
        Ejemplo:
            features = {
                'costo_total': 5000,
                'total_piezas': 3,
                'gama': 'alta',
                ...
            }
            prob_rechazo, prob_aceptacion = predictor.predecir_probabilidad(features)
            print(f"Probabilidad de aceptación: {prob_aceptacion:.2%}")
        """
        
        if not self.is_trained:
            self.cargar_modelo()
        
        # Convertir dict a DataFrame
        df_input = pd.DataFrame([cotizacion_features])
        
        # Preparar features
        X = self.preparar_features(df_input)
        
        # Predecir probabilidades
        proba = self.model.predict_proba(X)[0]
        
        # proba[0] = probabilidad de False (rechazada)
        # proba[1] = probabilidad de True (aceptada)
        return proba[0], proba[1]
    
    def obtener_factores_influyentes(self, top_n=10):
        """
        Retorna los factores más importantes para la decisión del modelo.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Feature Importance = Qué tan importante es cada variable para las predicciones.
        Por ejemplo, si "costo_total" tiene 0.35, significa que el 35% de las
        decisiones del modelo se basan en el costo.
        
        Args:
            top_n (int): Número de factores a retornar
        
        Returns:
            list: Lista de diccionarios con feature y su importancia
        """
        
        if not self.is_trained:
            return []
        
        importance_df = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False).head(top_n)
        
        return importance_df.to_dict('records')
    
    def generar_sugerencias(self, df):
        """
        Genera sugerencias accionables basadas en análisis de datos.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Basándose en patrones históricos, genera recomendaciones para
        mejorar la tasa de aceptación de cotizaciones.
        
        Args:
            df (DataFrame): DataFrame de cotizaciones
        
        Returns:
            list: Lista de sugerencias con formato
        """
        
        sugerencias = []
        
        if df.empty:
            return sugerencias
        
        # Sugerencia 1: Costo promedio
        df_aceptadas = df[df['aceptada'] == True]
        if not df_aceptadas.empty:
            costo_promedio_aceptadas = df_aceptadas['costo_total'].mean()
            sugerencias.append({
                'tipo': 'costo',
                'icono': '💰',
                'titulo': 'Optimización de Costos',
                'mensaje': f'Las cotizaciones aceptadas tienen un costo promedio de ${costo_promedio_aceptadas:,.2f}. Considera mantener cotizaciones cerca de este rango.',
                'color': 'success'
            })
        
        # Sugerencia 2: Número de piezas
        if not df_aceptadas.empty:
            piezas_promedio = df_aceptadas['total_piezas'].mean()
            sugerencias.append({
                'tipo': 'piezas',
                'icono': '🔧',
                'titulo': 'Cantidad de Piezas',
                'mensaje': f'Las cotizaciones aceptadas incluyen en promedio {piezas_promedio:.1f} piezas. Evita cotizar demasiadas piezas a la vez.',
                'color': 'info'
            })
        
        # Sugerencia 3: Descuento de mano de obra
        df_con_descuento = df[df['descontar_mano_obra'] == True]
        if not df_con_descuento.empty:
            tasa_con_descuento = (df_con_descuento['aceptada'] == True).mean() * 100
            sugerencias.append({
                'tipo': 'descuento',
                'icono': '🎁',
                'titulo': 'Efecto del Descuento',
                'mensaje': f'Las cotizaciones con descuento de mano de obra tienen {tasa_con_descuento:.1f}% de tasa de aceptación.',
                'color': 'warning'
            })
        
        # Sugerencia 4: Gama del equipo
        gama_stats = df.groupby('gama')['aceptada'].apply(lambda x: (x == True).mean() * 100)
        if not gama_stats.empty:
            mejor_gama = gama_stats.idxmax()
            tasa_mejor = gama_stats.max()
            sugerencias.append({
                'tipo': 'gama',
                'icono': '⭐',
                'titulo': 'Gama de Equipos',
                'mensaje': f'Equipos de gama {mejor_gama} tienen la mejor tasa de aceptación ({tasa_mejor:.1f}%).',
                'color': 'primary'
            })
        
        return sugerencias
    
    def guardar_modelo(self):
        """
        Guarda el modelo entrenado en disco para reutilizar.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Una vez entrenado, el modelo se guarda en un archivo .pkl
        para no tener que reentrenar cada vez. Es como guardar
        el "conocimiento aprendido" del modelo.
        """
        
        if not self.is_trained:
            raise ValueError("No se puede guardar un modelo sin entrenar")
        
        # Guardar modelo
        joblib.dump(self.model, self.model_path)
        
        # Guardar encoders
        joblib.dump(self.encoders, self.encoders_path)
        
        # Guardar feature names y métricas
        metadata = {
            'feature_names': self.feature_names,
            'metricas': self.metricas_entrenamiento,
        }
        metadata_path = self.model_dir / 'metadata.pkl'
        joblib.dump(metadata, metadata_path)
        
        print(f"✅ Modelo guardado en: {self.model_path}")
    
    def cargar_modelo(self):
        """
        Carga un modelo previamente entrenado desde disco.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Carga el modelo guardado para hacer predicciones sin
        tener que entrenar de nuevo. Mucho más rápido!
        """
        
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"❌ No se encontró modelo entrenado en {self.model_path}. "
                f"Ejecuta entrenar_modelo() primero."
            )
        
        # Cargar modelo
        self.model = joblib.load(self.model_path)
        
        # Cargar encoders
        if self.encoders_path.exists():
            self.encoders = joblib.load(self.encoders_path)
        
        # Cargar metadata
        metadata_path = self.model_dir / 'metadata.pkl'
        if metadata_path.exists():
            metadata = joblib.load(metadata_path)
            self.feature_names = metadata['feature_names']
            self.metricas_entrenamiento = metadata['metricas']
        
        self.is_trained = True
        print(f"✅ Modelo cargado desde: {self.model_path}")
    
    def obtener_metricas(self):
        """
        Retorna las métricas de evaluación del modelo.
        
        Returns:
            dict: Diccionario con métricas
        """
        return self.metricas_entrenamiento
