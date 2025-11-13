"""
Predictor de Motivo de Rechazo - Módulo ML Avanzado
====================================================

EXPLICACIÓN PARA PRINCIPIANTES:
En lugar de solo predecir SI una cotización será rechazada,
este módulo predice POR QUÉ será rechazada.

¿Cómo funciona?
- Analiza cotizaciones históricas que fueron rechazadas
- Identifica patrones comunes para cada motivo de rechazo
- Predice el motivo más probable para cotizaciones nuevas
- Retorna probabilidades para TODOS los motivos posibles

Tipo de Modelo: Clasificación Multiclase
- Entrada: Features de cotización (costo, piezas, cliente, etc.)
- Salida: Probabilidad para cada motivo de rechazo

Uso:
    predictor = PredictorMotivoRechazo()
    predictor.entrenar()
    
    resultado = predictor.predecir_motivo({
        'costo_total': 12500,
        'total_piezas': 7,
        'gama': 'baja',
        ...
    })
    
    # resultado = {
    #     'motivo_principal': 'costo_alto',
    #     'probabilidad': 0.72,
    #     'motivos_alternativos': [...]
    # }
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
import logging

from .base import MLModelBase
from ..models import Cotizacion
from ..utils_cotizaciones import obtener_dataframe_cotizaciones

logger = logging.getLogger(__name__)


class PredictorMotivoRechazo(MLModelBase):
    """
    Predice el motivo probable de rechazo de una cotización.
    
    MOTIVOS DETECTADOS:
    1. costo_alto: Cliente considera el precio muy elevado
    2. tiempo_largo: Tiempo de reparación muy extenso
    3. no_autorizado: Cliente no autoriza la reparación
    4. encontro_mejor: Cliente encontró opción más económica
    5. reparacion_no_justifica: El costo no justifica reparar
    
    Attributes:
        model: RandomForestClassifier para clasificación multiclase
        label_encoder: Codificador para motivos de rechazo
        feature_encoders: Codificadores para features categóricas
    """
    
    # Mapeo de motivos de rechazo del modelo a descripciones legibles
    MOTIVOS = {
        'costo_alto': {
            'nombre': 'Costo Muy Alto',
            'icono': '💰',
            'descripcion': 'El cliente considera que el precio es excesivo',
            'acciones_sugeridas': [
                'Ofrecer descuento del 10-15% en mano de obra',
                'Proponer plan de pagos en 2 partes',
                'Eliminar piezas opcionales no críticas',
                'Comparar con precios promedio del segmento'
            ]
        },
        'tiempo_largo': {
            'nombre': 'Tiempo de Entrega Largo',
            'icono': '⏰',
            'descripcion': 'El cliente necesita el equipo más rápido',
            'acciones_sugeridas': [
                'Priorizar pedido de piezas (entrega express)',
                'Reasignar a técnico con menor carga',
                'Ofrecer equipo de préstamo mientras se repara',
                'Reducir tiempo estimado si es posible'
            ]
        },
        'no_autorizado': {
            'nombre': 'Cliente No Autoriza',
            'icono': '🚫',
            'descripcion': 'El cliente no tiene autorización para aprobar',
            'acciones_sugeridas': [
                'Solicitar contacto del autorizador',
                'Enviar cotización formal por escrito',
                'Ofrecer extensión del plazo de respuesta',
                'Explicar consecuencias de no reparar'
            ]
        },
        'encontro_mejor': {
            'nombre': 'Encontró Opción Mejor',
            'icono': '🔍',
            'descripcion': 'Cliente encontró servicio más barato o rápido',
            'acciones_sugeridas': [
                'Igualar o mejorar oferta competitiva',
                'Destacar garantías y calidad del servicio',
                'Ofrecer servicios adicionales sin costo',
                'Negociar términos más flexibles'
            ]
        },
        'reparacion_no_justifica': {
            'nombre': 'Reparación No Justifica',
            'icono': '⚖️',
            'descripcion': 'El costo de reparación excede valor del equipo',
            'acciones_sugeridas': [
                'Ofrecer reparación parcial (solo lo esencial)',
                'Sugerir venta de piezas rescatables',
                'Proponer servicio de recuperación de datos',
                'Descontar costo completo de mano de obra'
            ]
        }
    }
    
    def __init__(self):
        """Inicializa el predictor de motivos de rechazo."""
        super().__init__(model_name='motivos_predictor')
        
        # Modelo de clasificación multiclase
        self.model = RandomForestClassifier(
            n_estimators=150,      # Más árboles para capturar matices
            max_depth=12,          # Mayor profundidad
            min_samples_split=3,   # Más sensible a patrones
            min_samples_leaf=1,
            n_jobs=-1,
            random_state=42,
            class_weight='balanced'  # Balance entre clases
        )
        
        # Encoders para variables categóricas
        self.label_encoder = LabelEncoder()  # Para motivos de rechazo
        self.feature_encoders = {
            'gama': LabelEncoder(),
            'tipo_equipo': LabelEncoder(),
            'sucursal': LabelEncoder(),
        }
        
        self.feature_names = []
        
        logger.info("✅ PredictorMotivoRechazo inicializado")
    
    def preparar_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepara features específicas para predicción de motivos.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Convierte datos crudos en variables que el modelo puede entender.
        
        Features incluidas:
        - Numéricas: costos, cantidad de piezas, tiempo respuesta
        - Derivadas: ratios, porcentajes, banderas binarias
        - Categóricas codificadas: gama, tipo equipo, sucursal
        
        Args:
            df: DataFrame con cotizaciones
        
        Returns:
            DataFrame con features preparadas
        """
        df_features = df.copy()
        
        # ========================================
        # FEATURES NUMÉRICAS DIRECTAS
        # ========================================
        numeric_features = [
            'costo_total',
            'costo_mano_obra',
            'costo_total_piezas',
            'total_piezas',
            'piezas_necesarias',
            'piezas_sugeridas_tecnico',
        ]
        
        # ========================================
        # FEATURES DERIVADAS (las que más importan para motivos)
        # ========================================
        
        # 1. Ratio de costo (qué tan cara es esta cotización vs promedio)
        costo_promedio = df_features['costo_total'].median()
        df_features['ratio_vs_promedio'] = (
            df_features['costo_total'] / costo_promedio
        ).fillna(1.0)
        
        # 2. Porcentaje de mano de obra sobre total
        df_features['porcentaje_mano_obra'] = (
            df_features['costo_mano_obra'] / df_features['costo_total'] * 100
        ).fillna(0)
        
        # 3. Costo promedio por pieza
        df_features['costo_por_pieza'] = (
            df_features['costo_total_piezas'] / df_features['total_piezas']
        ).fillna(0)
        
        # 4. Porcentaje de piezas necesarias
        df_features['porcentaje_necesarias'] = (
            df_features['piezas_necesarias'] / df_features['total_piezas'] * 100
        ).fillna(0)
        
        # 5. Tiene descuento (binario)
        df_features['tiene_descuento'] = df_features['descontar_mano_obra'].astype(int)
        
        # 6. Tiempo de respuesta (días)
        if 'dias_hasta_respuesta' in df_features.columns:
            df_features['tiempo_respuesta'] = df_features['dias_hasta_respuesta'].fillna(
                df_features['dias_hasta_respuesta'].median()
            )
        else:
            df_features['tiempo_respuesta'] = 0
        
        # 7. Rango de costo (categorizado)
        # bajo: < $5,000 | medio: $5,000-$10,000 | alto: > $10,000
        df_features['rango_costo_bajo'] = (df_features['costo_total'] < 5000).astype(int)
        df_features['rango_costo_medio'] = (
            (df_features['costo_total'] >= 5000) & 
            (df_features['costo_total'] <= 10000)
        ).astype(int)
        df_features['rango_costo_alto'] = (df_features['costo_total'] > 10000).astype(int)
        
        # 8. Cantidad de piezas (categorizada)
        df_features['pocas_piezas'] = (df_features['total_piezas'] <= 2).astype(int)
        df_features['muchas_piezas'] = (df_features['total_piezas'] > 5).astype(int)
        
        # 9. Temporal: día de la semana y mes
        if 'fecha_envio' in df_features.columns:
            df_features['dia_semana'] = pd.to_datetime(
                df_features['fecha_envio']
            ).dt.dayofweek
            df_features['mes'] = pd.to_datetime(df_features['fecha_envio']).dt.month
        else:
            df_features['dia_semana'] = 0
            df_features['mes'] = 1
        
        # ========================================
        # FEATURES CATEGÓRICAS (codificar)
        # ========================================
        for col, encoder in self.feature_encoders.items():
            if col in df_features.columns:
                # Entrenar encoder si no está entrenado
                if not hasattr(encoder, 'classes_'):
                    encoder.fit(df_features[col].fillna('desconocido'))
                
                # Transformar
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
            'piezas_sugeridas_tecnico',
            
            # Derivadas
            'ratio_vs_promedio',
            'porcentaje_mano_obra',
            'costo_por_pieza',
            'porcentaje_necesarias',
            'tiene_descuento',
            'tiempo_respuesta',
            
            # Rangos
            'rango_costo_bajo',
            'rango_costo_medio',
            'rango_costo_alto',
            'pocas_piezas',
            'muchas_piezas',
            
            # Temporales
            'dia_semana',
            'mes',
            
            # Categóricas codificadas
            'gama_encoded',
            'tipo_equipo_encoded',
        ]
        
        # Filtrar solo features que existan
        final_features = [f for f in final_features if f in df_features.columns]
        
        # Guardar nombres de features
        self.feature_names = final_features
        
        # Rellenar NaN y limpiar infinitos
        df_features[final_features] = df_features[final_features].fillna(0)
        df_features[final_features] = df_features[final_features].replace(
            [np.inf, -np.inf], 0
        )
        
        return df_features[final_features]
    
    def entrenar(
        self, 
        fecha_inicio: Optional[str] = None,
        fecha_fin: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Entrena el modelo con datos históricos de cotizaciones rechazadas.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        1. Obtiene cotizaciones RECHAZADAS con motivo especificado
        2. Extrae features de cada cotización
        3. Entrena modelo para aprender patrones de cada motivo
        4. Evalúa precisión y guarda modelo
        
        Args:
            fecha_inicio: Fecha inicio para filtrar datos
            fecha_fin: Fecha fin para filtrar datos
        
        Returns:
            dict: Métricas de evaluación del modelo
        """
        logger.info("📊 Obteniendo datos de cotizaciones rechazadas...")
        
        # Obtener datos completos
        df = obtener_dataframe_cotizaciones(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin
        )
        
        # Filtrar SOLO cotizaciones rechazadas CON motivo especificado
        df_rechazadas = df[
            (df['aceptada'] == False) & 
            (df['motivo_rechazo'].notna()) &
            (df['motivo_rechazo'] != '')
        ].copy()
        
        if len(df_rechazadas) < 20:
            raise ValueError(
                f"❌ Datos insuficientes para entrenar. Se necesitan mínimo 20 "
                f"cotizaciones rechazadas con motivo, pero solo hay {len(df_rechazadas)}."
            )
        
        logger.info(
            f"✅ {len(df_rechazadas)} cotizaciones rechazadas con motivo encontradas"
        )
        
        # Validar datos
        self.validar_datos(df_rechazadas, min_samples=20)
        
        # Preparar features (X)
        logger.info("🔧 Preparando features...")
        X = self.preparar_features(df_rechazadas)
        
        # Preparar target (y) - motivo de rechazo
        y = df_rechazadas['motivo_rechazo'].values
        
        # Entrenar label encoder
        self.label_encoder.fit(y)
        y_encoded = self.label_encoder.transform(y)
        
        logger.info(f"✅ {len(self.feature_names)} features preparadas")
        logger.info(f"   Motivos únicos detectados: {list(self.label_encoder.classes_)}")
        
        # Dividir en entrenamiento y prueba
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded,
            test_size=0.2,
            random_state=42,
            stratify=y_encoded  # Mantener proporción de clases
        )
        
        logger.info(f"📈 Entrenando modelo con {len(X_train)} muestras...")
        
        # ENTRENAR MODELO
        self.model.fit(X_train, y_train)
        
        logger.info("✅ Modelo entrenado exitosamente!")
        
        # Hacer predicciones en test set
        y_pred = self.model.predict(X_test)
        y_pred_proba = self.model.predict_proba(X_test)
        
        # Calcular métricas
        metricas = self.calcular_metricas_clasificacion(y_test, y_pred, y_pred_proba)
        
        # Agregar información adicional de entrenamiento
        metricas['muestras_entrenamiento'] = len(X_train)
        metricas['muestras_prueba'] = len(X_test)
        metricas['total_muestras'] = len(df_rechazadas)
        
        # Distribución de motivos en el dataset completo (y ya contiene nombres, no códigos)
        distribucion_motivos = pd.Series(y).value_counts().to_dict()
        metricas['distribucion_motivos'] = distribucion_motivos
        
        # Feature importance
        feature_importance = pd.DataFrame({
            'feature': self.feature_names,
            'importance': self.model.feature_importances_
        }).sort_values('importance', ascending=False)
        
        metricas['feature_importance'] = feature_importance.to_dict('records')
        metricas['motivos_detectados'] = list(self.label_encoder.classes_)
        
        # Actualizar metadata
        self.metadata.update({
            'total_samples': len(df_rechazadas),
            'muestras_entrenamiento': len(X_train),
            'muestras_prueba': len(X_test),
            'features': self.feature_names,
            'motivos': list(self.label_encoder.classes_),
            'metrics': metricas,
            'last_trained': pd.Timestamp.now().isoformat(),
        })
        
        self.is_trained = True
        
        # Imprimir resumen
        print("\n" + "="*70)
        print("📊 MÉTRICAS DEL PREDICTOR DE MOTIVOS")
        print("="*70)
        print(f"Accuracy (Precisión General): {metricas['accuracy']:.2%}")
        print(f"Precision (Weighted): {metricas['precision']:.2%}")
        print(f"Recall (Weighted): {metricas['recall']:.2%}")
        print(f"F1-Score (Weighted): {metricas['f1_score']:.2%}")
        print(f"\n🎯 Motivos Detectados: {len(self.label_encoder.classes_)}")
        for motivo in self.label_encoder.classes_:
            print(f"   - {motivo}")
        print("\n🔝 Top 5 Features Más Importantes:")
        for i, row in enumerate(feature_importance.head(5).itertuples(), 1):
            print(f"   {i}. {row.feature}: {row.importance:.4f}")
        print("="*70)
        
        # Guardar modelo
        self.guardar_modelo()
        
        return metricas
    
    def predecir_motivo(
        self, 
        cotizacion_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Predice el motivo probable de rechazo de una cotización.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Dada una cotización nueva, predice cuál es el motivo más probable
        por el que será rechazada, junto con probabilidades de cada motivo.
        
        Args:
            cotizacion_features: Diccionario con características de la cotización
                Ejemplo: {
                    'costo_total': 12500,
                    'costo_mano_obra': 3500,
                    'total_piezas': 7,
                    'gama': 'baja',
                    ...
                }
        
        Returns:
            dict: Resultado de la predicción con formato:
                {
                    'motivo_principal': 'costo_alto',
                    'motivo_info': {...},  # Info del motivo
                    'probabilidad': 0.72,
                    'confianza': 'alta',  # alta/media/baja
                    'motivos_alternativos': [
                        {'motivo': 'tiempo_largo', 'prob': 0.15, ...},
                        ...
                    ],
                    'acciones_sugeridas': [...]
                }
        """
        if not self.is_trained:
            try:
                self.cargar_modelo()
            except FileNotFoundError:
                raise ValueError(
                    "Modelo no entrenado. Ejecuta entrenar() primero."
                )
        
        # Convertir dict a DataFrame
        df_input = pd.DataFrame([cotizacion_features])
        
        # Preparar features
        X = self.preparar_features(df_input)
        
        # Predecir probabilidades
        proba = self.model.predict_proba(X)[0]
        
        # Obtener índice del motivo con mayor probabilidad
        idx_principal = np.argmax(proba)
        motivo_principal = self.label_encoder.classes_[idx_principal]
        prob_principal = proba[idx_principal]
        
        # Determinar confianza
        if prob_principal >= 0.7:
            confianza = 'alta'
            confianza_icono = '🟢'
        elif prob_principal >= 0.5:
            confianza = 'media'
            confianza_icono = '🟡'
        else:
            confianza = 'baja'
            confianza_icono = '🔴'
        
        # Obtener información del motivo
        motivo_info = self.MOTIVOS.get(motivo_principal, {
            'nombre': motivo_principal.replace('_', ' ').title(),
            'icono': '❓',
            'descripcion': 'Motivo no catalogado',
            'acciones_sugeridas': []
        })
        
        # Motivos alternativos (top 3 excluyendo el principal)
        motivos_alternativos = []
        for idx, prob in enumerate(proba):
            if idx != idx_principal and prob > 0.05:  # Solo si prob > 5%
                motivo = self.label_encoder.classes_[idx]
                motivo_alt_info = self.MOTIVOS.get(motivo, {})
                
                motivos_alternativos.append({
                    'motivo': motivo,
                    'nombre': motivo_alt_info.get('nombre', motivo),
                    'probabilidad': float(prob),
                    'probabilidad_pct': f"{prob*100:.1f}%",
                    'icono': motivo_alt_info.get('icono', '❓')
                })
        
        # Ordenar por probabilidad descendente y tomar top 3
        motivos_alternativos = sorted(
            motivos_alternativos,
            key=lambda x: x['probabilidad'],
            reverse=True
        )[:3]
        
        # Resultado completo
        resultado = {
            'motivo_principal': motivo_principal,
            'motivo_nombre': motivo_info['nombre'],
            'motivo_icono': motivo_info['icono'],
            'motivo_descripcion': motivo_info['descripcion'],
            'probabilidad': float(prob_principal),
            'probabilidad_pct': f"{prob_principal*100:.1f}%",
            'confianza': confianza,
            'confianza_icono': confianza_icono,
            'motivos_alternativos': motivos_alternativos,
            'acciones_sugeridas': motivo_info['acciones_sugeridas'],
            'todas_probabilidades': {
                self.label_encoder.classes_[i]: float(p) 
                for i, p in enumerate(proba)
            }
        }
        
        return resultado
    
    def analizar_cotizaciones_pendientes(
        self, 
        df_cotizaciones: pd.DataFrame
    ) -> List[Dict[str, Any]]:
        """
        Analiza múltiples cotizaciones pendientes y predice motivos de rechazo.
        
        Args:
            df_cotizaciones: DataFrame con cotizaciones a analizar
        
        Returns:
            list: Lista de predicciones para cada cotización pendiente
        """
        if not self.is_trained:
            try:
                self.cargar_modelo()
            except FileNotFoundError:
                logger.warning("⚠️ Modelo no entrenado, no se pueden hacer predicciones")
                return []
        
        # Filtrar solo cotizaciones sin respuesta
        df_pendientes = df_cotizaciones[df_cotizaciones['aceptada'].isna()].copy()
        
        if df_pendientes.empty:
            logger.info("ℹ️ No hay cotizaciones pendientes para analizar")
            return []
        
        resultados = []
        
        for idx, row in df_pendientes.iterrows():
            try:
                # Preparar features de esta cotización
                features = row.to_dict()
                
                # Predecir motivo
                prediccion = self.predecir_motivo(features)
                
                # Agregar información de la cotización
                prediccion['cotizacion_id'] = row.get('cotizacion_id')
                prediccion['numero_orden'] = row.get('numero_orden')
                prediccion['costo_total'] = row.get('costo_total')
                
                resultados.append(prediccion)
                
            except Exception as e:
                logger.error(
                    f"❌ Error prediciendo cotización {row.get('cotizacion_id')}: {str(e)}"
                )
                continue
        
        logger.info(f"✅ {len(resultados)} cotizaciones analizadas")
        
        return resultados
