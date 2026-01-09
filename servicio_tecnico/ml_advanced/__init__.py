"""
Módulos Avanzados de Machine Learning para Cotizaciones
========================================================

Este paquete contiene módulos ML avanzados que extienden las capacidades
del predictor base (ml_predictor.py) para proporcionar análisis más profundos
y recomendaciones accionables.

ARQUITECTURA:
- base.py: Clase base compartida con utilidades comunes
- motivo_rechazo.py: Predice POR QUÉ será rechazada una cotización
- optimizador_precios.py: Optimiza precios para maximizar aceptación
- recomendador_acciones.py: Orquestador que genera plan de acción completo

ESCALABILIDAD:
Esta estructura permite agregar más módulos sin modificar código existente.
Nuevos módulos pueden heredar de MLModelBase y seguir el mismo patrón.

Autor: Sistema de Servicio Técnico
Fecha: Noviembre 2025
Versión: 1.0.0
"""

# Importar clases principales para uso externo
from .base import MLModelBase
# from .motivo_rechazo import PredictorMotivoRechazo  # Versión original (37.78%) - deprecada
from .motivo_rechazo_mejorado import PredictorMotivoRechazoMejorado as PredictorMotivoRechazo  # Versión mejorada (73.33%)
from .optimizador_precios import OptimizadorPrecios
from .recomendador_acciones import RecomendadorAcciones

# Versión del paquete
__version__ = '1.0.0'

# Exportar clases públicas
__all__ = [
    'MLModelBase',
    'PredictorMotivoRechazo',
    'OptimizadorPrecios',
    'RecomendadorAcciones',
]

# Configuración por defecto compartida
ML_CONFIG = {
    'model_dir': 'ml_models',
    'random_state': 42,
    'n_jobs': -1,
    'min_samples_train': 20,
    'test_size': 0.2,
}
