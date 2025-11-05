"""
Clase Base para Modelos ML Avanzados
=====================================

EXPLICACIÓN PARA PRINCIPIANTES:
Esta clase proporciona funcionalidad común que todos los modelos ML necesitan:
- Guardar y cargar modelos
- Validar datos
- Logging y métricas
- Manejo de errores

Es como un "molde" o "plantilla" que otros modelos pueden extender.

Pattern: Template Method Pattern
Todos los modelos heredan de esta clase y solo implementan lo específico.
"""

import joblib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import pandas as pd
import numpy as np

# Configurar logger
logger = logging.getLogger(__name__)


class MLModelBase:
    """
    Clase base abstracta para todos los modelos ML del sistema.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta clase tiene métodos que TODOS los modelos necesitan:
    - guardar_modelo() - Guardar modelo entrenado en disco
    - cargar_modelo() - Cargar modelo previamente entrenado
    - validar_datos() - Verificar que los datos sean correctos
    - logging() - Registrar eventos importantes
    
    Las clases hijas (PredictorMotivoRechazo, OptimizadorPrecios, etc.)
    heredan estos métodos y solo definen lo específico de su funcionalidad.
    
    Attributes:
        model_name (str): Nombre del modelo (ej: "motivos_predictor")
        model_dir (Path): Directorio donde se guardan modelos
        model: El modelo ML (RandomForest, etc.)
        is_trained (bool): True si el modelo está entrenado
        metadata (dict): Información del entrenamiento
    """
    
    def __init__(self, model_name: str, model_dir: str = 'ml_models'):
        """
        Inicializa el modelo base.
        
        Args:
            model_name: Nombre identificador del modelo
            model_dir: Directorio para almacenar modelos entrenados
        """
        self.model_name = model_name
        self.model_dir = Path(model_dir)
        self.model = None
        self.is_trained = False
        self.metadata = {
            'version': '1.0.0',
            'created_at': None,
            'last_trained': None,
            'total_samples': 0,
            'features': [],
            'metrics': {}
        }
        
        # Crear directorio si no existe
        self.model_dir.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"✅ {self.model_name} inicializado correctamente")
    
    @property
    def model_path(self) -> Path:
        """Ruta donde se guarda el modelo principal."""
        return self.model_dir / f'{self.model_name}.pkl'
    
    @property
    def metadata_path(self) -> Path:
        """Ruta donde se guardan los metadatos del modelo."""
        return self.model_dir / f'{self.model_name}_metadata.pkl'
    
    def validar_datos(self, df: pd.DataFrame, min_samples: int = 20) -> bool:
        """
        Valida que los datos sean suficientes y correctos para entrenar.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Antes de entrenar un modelo, verificamos:
        1. Que haya datos (no esté vacío)
        2. Que haya suficientes ejemplos (mínimo 20)
        3. Que las columnas requeridas existan
        
        Args:
            df: DataFrame con datos para entrenar
            min_samples: Mínimo de muestras requeridas
        
        Returns:
            bool: True si los datos son válidos, False si no
        
        Raises:
            ValueError: Si los datos no cumplen requisitos mínimos
        """
        # Validación 1: DataFrame no vacío
        if df is None or df.empty:
            logger.error(f"❌ {self.model_name}: DataFrame vacío")
            raise ValueError("DataFrame vacío. No hay datos para entrenar.")
        
        # Validación 2: Suficientes muestras
        if len(df) < min_samples:
            logger.warning(
                f"⚠️ {self.model_name}: Solo {len(df)} muestras "
                f"(mínimo recomendado: {min_samples})"
            )
            raise ValueError(
                f"Datos insuficientes. Se necesitan mínimo {min_samples} muestras, "
                f"pero solo hay {len(df)}."
            )
        
        # Validación 3: Sin valores infinitos o NaN en todas las columnas
        if df.isnull().all().any():
            columnas_problematicas = df.columns[df.isnull().all()].tolist()
            logger.error(
                f"❌ {self.model_name}: Columnas completamente vacías: "
                f"{columnas_problematicas}"
            )
            raise ValueError(
                f"Columnas con todos los valores nulos: {columnas_problematicas}"
            )
        
        logger.info(
            f"✅ {self.model_name}: Datos válidos - {len(df)} muestras, "
            f"{len(df.columns)} columnas"
        )
        return True
    
    def guardar_modelo(self) -> None:
        """
        Guarda el modelo entrenado y sus metadatos en disco.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Después de entrenar el modelo, lo guardamos en un archivo .pkl
        para poder usarlo después sin tener que reentrenar cada vez.
        
        Es como guardar tu progreso en un videojuego.
        
        Raises:
            ValueError: Si intentas guardar un modelo no entrenado
        """
        if not self.is_trained:
            raise ValueError(
                f"No se puede guardar {self.model_name} sin entrenar. "
                f"Ejecuta entrenar() primero."
            )
        
        try:
            # Guardar modelo principal
            joblib.dump(self.model, self.model_path)
            logger.info(f"💾 {self.model_name}: Modelo guardado en {self.model_path}")
            
            # Actualizar metadata
            self.metadata['last_saved'] = datetime.now().isoformat()
            
            # Guardar metadata
            joblib.dump(self.metadata, self.metadata_path)
            logger.info(f"💾 {self.model_name}: Metadata guardada en {self.metadata_path}")
            
        except Exception as e:
            logger.error(f"❌ Error guardando {self.model_name}: {str(e)}")
            raise
    
    def cargar_modelo(self) -> bool:
        """
        Carga un modelo previamente entrenado desde disco.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        En lugar de entrenar cada vez (que puede tardar varios minutos),
        cargamos el modelo ya entrenado desde el archivo .pkl.
        
        Es como cargar tu partida guardada en un videojuego.
        
        Returns:
            bool: True si cargó correctamente, False si no existe el modelo
        
        Raises:
            FileNotFoundError: Si no existe el archivo del modelo
        """
        # Verificar que existan los archivos
        if not self.model_path.exists():
            logger.warning(
                f"⚠️ {self.model_name}: No se encontró modelo en {self.model_path}. "
                f"Necesitas entrenar primero."
            )
            raise FileNotFoundError(
                f"Modelo no encontrado en {self.model_path}. "
                f"Ejecuta entrenar() antes de usar el modelo."
            )
        
        try:
            # Cargar modelo
            self.model = joblib.load(self.model_path)
            logger.info(f"✅ {self.model_name}: Modelo cargado desde {self.model_path}")
            
            # Cargar metadata si existe
            if self.metadata_path.exists():
                self.metadata = joblib.load(self.metadata_path)
                logger.info(f"✅ {self.model_name}: Metadata cargada")
            
            self.is_trained = True
            return True
            
        except Exception as e:
            logger.error(f"❌ Error cargando {self.model_name}: {str(e)}")
            raise
    
    def obtener_metricas(self) -> Dict[str, Any]:
        """
        Retorna las métricas de evaluación del modelo.
        
        Returns:
            dict: Diccionario con métricas de rendimiento
        """
        if not self.is_trained:
            logger.warning(f"⚠️ {self.model_name}: No hay métricas (modelo no entrenado)")
            return {}
        
        return self.metadata.get('metrics', {})
    
    def obtener_info(self) -> Dict[str, Any]:
        """
        Retorna información completa del modelo.
        
        Returns:
            dict: Información del modelo (versión, fecha entrenamiento, métricas, etc.)
        """
        return {
            'nombre': self.model_name,
            'version': self.metadata.get('version'),
            'entrenado': self.is_trained,
            'ultimo_entrenamiento': self.metadata.get('last_trained'),
            'total_muestras': self.metadata.get('total_samples'),
            'metricas': self.metadata.get('metrics', {}),
            'features': self.metadata.get('features', [])
        }
    
    def limpiar_datos(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Limpia y preprocesa datos eliminando valores problemáticos.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Los datos "sucios" (valores infinitos, NaN, duplicados) pueden
        romper el modelo. Esta función los limpia automáticamente.
        
        Args:
            df: DataFrame con datos posiblemente sucios
        
        Returns:
            DataFrame: Datos limpios y listos para usar
        """
        df_clean = df.copy()
        
        # 1. Eliminar duplicados exactos
        duplicados_antes = len(df_clean)
        df_clean = df_clean.drop_duplicates()
        duplicados_eliminados = duplicados_antes - len(df_clean)
        
        if duplicados_eliminados > 0:
            logger.info(
                f"🧹 {self.model_name}: {duplicados_eliminados} filas duplicadas eliminadas"
            )
        
        # 2. Reemplazar infinitos con NaN
        df_clean = df_clean.replace([np.inf, -np.inf], np.nan)
        
        # 3. Eliminar filas con demasiados NaN (>50% columnas)
        threshold = len(df_clean.columns) * 0.5
        df_clean = df_clean.dropna(thresh=threshold)
        
        # 4. Rellenar NaN restantes con 0 (asume numéricos)
        # NOTA: Esto puede personalizarse según el caso de uso
        df_clean = df_clean.fillna(0)
        
        logger.info(
            f"🧹 {self.model_name}: Limpieza completada - "
            f"{len(df_clean)}/{duplicados_antes} filas conservadas"
        )
        
        return df_clean
    
    def calcular_metricas_clasificacion(
        self, 
        y_true: np.ndarray, 
        y_pred: np.ndarray,
        y_pred_proba: Optional[np.ndarray] = None
    ) -> Dict[str, float]:
        """
        Calcula métricas estándar para modelos de clasificación.
        
        Args:
            y_true: Etiquetas verdaderas
            y_pred: Predicciones del modelo
            y_pred_proba: Probabilidades predichas (opcional)
        
        Returns:
            dict: Métricas calculadas (accuracy, precision, recall, f1)
        """
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score, f1_score,
            confusion_matrix, classification_report
        )
        
        metricas = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, average='weighted', zero_division=0),
            'recall': recall_score(y_true, y_pred, average='weighted', zero_division=0),
            'f1_score': f1_score(y_true, y_pred, average='weighted', zero_division=0),
            'total_samples': len(y_true),
            'fecha_calculo': datetime.now().isoformat()
        }
        
        # Matriz de confusión
        cm = confusion_matrix(y_true, y_pred)
        metricas['confusion_matrix'] = cm.tolist()
        
        # Report detallado (como string)
        report = classification_report(y_true, y_pred, zero_division=0)
        metricas['classification_report'] = report
        
        logger.info(
            f"📊 {self.model_name}: Métricas calculadas - "
            f"Accuracy: {metricas['accuracy']:.2%}"
        )
        
        return metricas
    
    def __repr__(self) -> str:
        """Representación string del modelo."""
        estado = "✅ Entrenado" if self.is_trained else "⚠️ No entrenado"
        return (
            f"{self.__class__.__name__}("
            f"nombre='{self.model_name}', "
            f"estado={estado}, "
            f"muestras={self.metadata.get('total_samples', 0)})"
        )
