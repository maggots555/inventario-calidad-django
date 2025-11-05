"""
Optimizador de Precios Inteligente - Módulo ML Avanzado
=======================================================

EXPLICACIÓN PARA PRINCIPIANTES:
Este módulo encuentra el PRECIO ÓPTIMO para maximizar la probabilidad
de que el cliente acepte la cotización, sin sacrificar demasiado margen.

¿Cómo funciona?
1. Genera múltiples escenarios de precio (con diferentes descuentos)
2. Para cada escenario, predice probabilidad de aceptación
3. Calcula "ingreso esperado" = precio × prob_aceptación
4. Recomienda el escenario con mayor ingreso esperado

Matemática simple:
- Escenario A: $10,000 × 40% aceptación = $4,000 esperado
- Escenario B: $8,500 × 75% aceptación = $6,375 esperado ✅ MEJOR
- Escenario C: $7,000 × 85% aceptación = $5,950 esperado

Aunque Escenario C tiene mayor aceptación, B genera más ingresos.

Dependencias:
- Requiere PredictorAceptacionCotizacion (modelo base) entrenado
- Usa scipy.optimize para encontrar precio óptimo
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from scipy.optimize import minimize_scalar
import logging

from .base import MLModelBase
from ..ml_predictor import PredictorAceptacionCotizacion

logger = logging.getLogger(__name__)


class OptimizadorPrecios(MLModelBase):
    """
    Optimiza precios de cotizaciones para maximizar ingresos esperados.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    No es un modelo que se "entrena" como los otros, sino un OPTIMIZADOR
    que usa el predictor base para simular diferentes precios y encontrar
    el mejor balance entre precio y probabilidad de aceptación.
    
    Attributes:
        predictor_base: Modelo que predice prob. aceptación
        escenarios_evaluados: Lista de escenarios probados
        configuracion: Parámetros de optimización
    """
    
    # Configuración de descuentos permitidos
    DESCUENTOS_CONFIG = {
        'mano_obra': {
            'min': 0.0,    # 0% (sin descuento)
            'max': 1.0,    # 100% (gratis)
            'step': 0.25   # Incrementos de 25%
        },
        'piezas': {
            'min': 0.0,    # 0% (sin descuento)
            'max': 0.3,    # 30% (máximo permitido)
            'step': 0.05   # Incrementos de 5%
        }
    }
    
    # Rangos de sensibilidad por segmento de cliente
    SENSIBILIDAD_PRECIO = {
        'premium': {
            'umbral_alto': 15000,  # Acepta hasta $15k sin problemas
            'sensibilidad': 0.3,   # Baja sensibilidad
        },
        'balanceado': {
            'umbral_alto': 10000,
            'sensibilidad': 0.6,   # Media sensibilidad
        },
        'sensible': {
            'umbral_alto': 6000,
            'sensibilidad': 0.9,   # Alta sensibilidad
        }
    }
    
    def __init__(self, predictor_base: Optional[PredictorAceptacionCotizacion] = None):
        """
        Inicializa el optimizador de precios.
        
        Args:
            predictor_base: Predictor de aceptación entrenado (opcional)
                           Si no se proporciona, se cargará automáticamente
        """
        super().__init__(model_name='optimizador_precios')
        
        # Cargar o usar predictor base
        if predictor_base is None:
            self.predictor_base = PredictorAceptacionCotizacion()
            try:
                self.predictor_base.cargar_modelo()
                logger.info("✅ Predictor base cargado correctamente")
            except FileNotFoundError:
                logger.warning(
                    "⚠️ Predictor base no encontrado. Debe entrenarse primero."
                )
        else:
            self.predictor_base = predictor_base
        
        self.escenarios_evaluados = []
        self.configuracion = {
            'margen_minimo': 0.15,  # 15% margen mínimo aceptable
            'max_descuento_mano_obra': 1.0,  # Hasta 100%
            'max_descuento_piezas': 0.3,     # Hasta 30%
        }
        
        # Este módulo no requiere entrenamiento tradicional
        self.is_trained = True
        
        logger.info("✅ OptimizadorPrecios inicializado")
    
    def calcular_costo_con_descuento(
        self,
        costo_mano_obra: float,
        costo_piezas: float,
        desc_mano_obra: float = 0.0,
        desc_piezas: float = 0.0
    ) -> Dict[str, float]:
        """
        Calcula el costo total aplicando descuentos.
        
        Args:
            costo_mano_obra: Costo base de mano de obra
            costo_piezas: Costo total de piezas
            desc_mano_obra: % descuento en mano de obra (0.0 a 1.0)
            desc_piezas: % descuento en piezas (0.0 a 0.3)
        
        Returns:
            dict: Desglose de costos
                {
                    'mano_obra_original': 3500,
                    'mano_obra_descuento': 875,
                    'mano_obra_final': 2625,
                    'piezas_original': 8200,
                    'piezas_descuento': 410,
                    'piezas_final': 7790,
                    'total_descuentos': 1285,
                    'costo_final': 10415
                }
        """
        # Calcular descuentos
        descuento_mo = costo_mano_obra * desc_mano_obra
        descuento_piezas = costo_piezas * desc_piezas
        
        # Costos finales
        costo_mo_final = costo_mano_obra - descuento_mo
        costo_piezas_final = costo_piezas - descuento_piezas
        costo_total = costo_mo_final + costo_piezas_final
        
        return {
            'mano_obra_original': costo_mano_obra,
            'mano_obra_descuento': descuento_mo,
            'mano_obra_final': costo_mo_final,
            'piezas_original': costo_piezas,
            'piezas_descuento': descuento_piezas,
            'piezas_final': costo_piezas_final,
            'total_descuentos': descuento_mo + descuento_piezas,
            'costo_final': costo_total,
            'desc_mano_obra_pct': desc_mano_obra * 100,
            'desc_piezas_pct': desc_piezas * 100,
        }
    
    def generar_escenarios(
        self,
        costo_mano_obra: float,
        costo_piezas: float,
        incluir_extremos: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Genera múltiples escenarios de precio para evaluar.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Crea una lista de posibles combinaciones de descuentos a probar.
        Por ejemplo:
        - Sin descuentos
        - 25% descuento mano de obra
        - 50% descuento mano de obra
        - 100% descuento mano de obra
        - Combinaciones con descuentos en piezas
        
        Args:
            costo_mano_obra: Costo de mano de obra
            costo_piezas: Costo de piezas
            incluir_extremos: Si incluir escenarios extremos (0% y 100%)
        
        Returns:
            list: Lista de escenarios con descuentos y costos
        """
        escenarios = []
        
        # Generar rangos de descuentos
        desc_mo_values = np.arange(
            self.DESCUENTOS_CONFIG['mano_obra']['min'],
            self.DESCUENTOS_CONFIG['mano_obra']['max'] + 0.01,
            self.DESCUENTOS_CONFIG['mano_obra']['step']
        )
        
        desc_piezas_values = np.arange(
            self.DESCUENTOS_CONFIG['piezas']['min'],
            self.DESCUENTOS_CONFIG['piezas']['max'] + 0.01,
            self.DESCUENTOS_CONFIG['piezas']['step']
        )
        
        # Generar todas las combinaciones
        for desc_mo in desc_mo_values:
            for desc_piezas in desc_piezas_values:
                # Calcular costos con estos descuentos
                costos = self.calcular_costo_con_descuento(
                    costo_mano_obra,
                    costo_piezas,
                    desc_mo,
                    desc_piezas
                )
                
                # Crear escenario
                escenario = {
                    'id': len(escenarios) + 1,
                    'desc_mano_obra': desc_mo,
                    'desc_piezas': desc_piezas,
                    **costos
                }
                
                escenarios.append(escenario)
        
        logger.info(f"✅ {len(escenarios)} escenarios generados")
        
        return escenarios
    
    def evaluar_escenario(
        self,
        escenario: Dict[str, Any],
        cotizacion_features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Evalúa un escenario prediciendo probabilidad de aceptación e ingreso esperado.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Para cada escenario de precio:
        1. Actualiza las features con el nuevo precio
        2. Predice probabilidad de aceptación
        3. Calcula ingreso esperado = precio × probabilidad
        
        Args:
            escenario: Diccionario con descuentos y costos
            cotizacion_features: Features de la cotización original
        
        Returns:
            dict: Escenario evaluado con prob_aceptacion e ingreso_esperado
        """
        # Copiar features y actualizar con nuevo costo
        features_ajustadas = cotizacion_features.copy()
        features_ajustadas['costo_total'] = escenario['costo_final']
        features_ajustadas['costo_mano_obra'] = escenario['mano_obra_final']
        features_ajustadas['costo_total_piezas'] = escenario['piezas_final']
        features_ajustadas['descontar_mano_obra'] = (escenario['desc_mano_obra'] > 0)
        
        # Predecir probabilidad de aceptación
        try:
            prob_rechazo, prob_aceptacion = self.predictor_base.predecir_probabilidad(
                features_ajustadas
            )
        except Exception as e:
            logger.error(f"❌ Error prediciendo escenario: {str(e)}")
            prob_aceptacion = 0.0
            prob_rechazo = 1.0
        
        # Calcular ingreso esperado
        ingreso_esperado = escenario['costo_final'] * prob_aceptacion
        
        # Calcular margen (asumiendo costo de piezas + 30% mano obra como costo real)
        costo_real = escenario['piezas_final'] + (escenario['mano_obra_final'] * 0.3)
        margen = escenario['costo_final'] - costo_real
        margen_porcentaje = (margen / escenario['costo_final'] * 100) if escenario['costo_final'] > 0 else 0
        
        # Actualizar escenario con predicciones
        escenario_evaluado = {
            **escenario,
            'prob_aceptacion': prob_aceptacion,
            'prob_aceptacion_pct': prob_aceptacion * 100,
            'prob_rechazo': prob_rechazo,
            'ingreso_esperado': ingreso_esperado,
            'margen': margen,
            'margen_porcentaje': margen_porcentaje,
        }
        
        return escenario_evaluado
    
    def optimizar_precio(
        self,
        cotizacion_features: Dict[str, Any],
        costo_mano_obra: float,
        costo_piezas: float,
        prioridad: str = 'ingreso'  # 'ingreso', 'aceptacion', 'margen'
    ) -> Dict[str, Any]:
        """
        Encuentra el precio óptimo para una cotización.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Este es el método principal que:
        1. Genera ~40-60 escenarios de precio
        2. Evalúa cada uno con el predictor
        3. Encuentra el mejor según la prioridad
        
        Args:
            cotizacion_features: Features de la cotización
            costo_mano_obra: Costo de mano de obra
            costo_piezas: Costo de piezas
            prioridad: Qué optimizar ('ingreso', 'aceptacion', 'margen')
        
        Returns:
            dict: Resultado de optimización con:
                {
                    'escenario_actual': {...},  # Sin cambios
                    'escenario_optimo': {...},  # Mejor encontrado
                    'escenario_conservador': {...},  # Alternativa segura
                    'escenario_agresivo': {...},  # Máximo descuento
                    'mejora_esperada': 2336,  # Aumento en ingreso
                    'mejora_porcentaje': 48.5,
                    'recomendacion': 'aplicar_optimo',
                    'todos_escenarios': [...]
                }
        """
        logger.info("🔍 Optimizando precio de cotización...")
        
        # Generar escenarios
        escenarios = self.generar_escenarios(costo_mano_obra, costo_piezas)
        
        # Evaluar todos los escenarios
        escenarios_evaluados = []
        for escenario in escenarios:
            escenario_eval = self.evaluar_escenario(escenario, cotizacion_features)
            escenarios_evaluados.append(escenario_eval)
        
        # Guardar para análisis posterior
        self.escenarios_evaluados = escenarios_evaluados
        
        # Identificar escenarios clave
        
        # 1. Escenario ACTUAL (sin descuentos)
        escenario_actual = next(
            (e for e in escenarios_evaluados 
             if e['desc_mano_obra'] == 0 and e['desc_piezas'] == 0),
            escenarios_evaluados[0]
        )
        
        # 2. Escenario ÓPTIMO (según prioridad)
        if prioridad == 'ingreso':
            # Maximizar ingreso esperado
            escenario_optimo = max(
                escenarios_evaluados,
                key=lambda x: x['ingreso_esperado']
            )
        elif prioridad == 'aceptacion':
            # Maximizar probabilidad de aceptación
            escenario_optimo = max(
                escenarios_evaluados,
                key=lambda x: x['prob_aceptacion']
            )
        else:  # prioridad == 'margen'
            # Maximizar margen manteniendo prob_aceptacion > 60%
            escenarios_viables = [
                e for e in escenarios_evaluados 
                if e['prob_aceptacion'] >= 0.6
            ]
            if escenarios_viables:
                escenario_optimo = max(
                    escenarios_viables,
                    key=lambda x: x['margen']
                )
            else:
                # Si ninguno tiene >60%, tomar el de mayor probabilidad
                escenario_optimo = max(
                    escenarios_evaluados,
                    key=lambda x: x['prob_aceptacion']
                )
        
        # 3. Escenario CONSERVADOR (solo 25-50% desc. mano obra)
        escenarios_conservadores = [
            e for e in escenarios_evaluados
            if 0.25 <= e['desc_mano_obra'] <= 0.5 and e['desc_piezas'] == 0
        ]
        if escenarios_conservadores:
            escenario_conservador = max(
                escenarios_conservadores,
                key=lambda x: x['ingreso_esperado']
            )
        else:
            escenario_conservador = escenario_optimo
        
        # 4. Escenario AGRESIVO (máximo descuento)
        escenario_agresivo = max(
            escenarios_evaluados,
            key=lambda x: x['total_descuentos']
        )
        
        # Calcular mejoras vs escenario actual
        mejora_ingreso = escenario_optimo['ingreso_esperado'] - escenario_actual['ingreso_esperado']
        mejora_porcentaje = (
            (mejora_ingreso / escenario_actual['ingreso_esperado'] * 100)
            if escenario_actual['ingreso_esperado'] > 0 else 0
        )
        
        mejora_prob = escenario_optimo['prob_aceptacion'] - escenario_actual['prob_aceptacion']
        
        # Determinar recomendación
        if mejora_ingreso > 500:  # Mejora significativa ($500+)
            recomendacion = 'aplicar_optimo'
            mensaje = f"✅ RECOMENDADO: Aplicar escenario óptimo (mejora: +${mejora_ingreso:,.0f})"
        elif mejora_prob > 0.15:  # Mejora en probabilidad >15%
            recomendacion = 'aplicar_optimo'
            mensaje = f"✅ RECOMENDADO: Aplicar escenario óptimo (mejora prob: +{mejora_prob*100:.1f}%)"
        elif mejora_ingreso > 0:  # Cualquier mejora
            recomendacion = 'considerar_optimo'
            mensaje = f"💡 CONSIDERAR: Escenario óptimo con mejora moderada (+${mejora_ingreso:,.0f})"
        else:
            recomendacion = 'mantener_actual'
            mensaje = "✅ MANTENER: Precio actual es óptimo"
        
        # Resultado completo
        resultado = {
            'costo_actual': costo_mano_obra + costo_piezas,  # NUEVO: costo sin descuentos
            'escenario_actual': escenario_actual,
            'escenario_optimo': escenario_optimo,
            'escenario_conservador': escenario_conservador,
            'escenario_agresivo': escenario_agresivo,
            'mejora_ingreso': mejora_ingreso,
            'mejora_porcentaje': mejora_porcentaje,
            'mejora_probabilidad': mejora_prob,
            'mejora_probabilidad_pct': mejora_prob * 100,
            'recomendacion': recomendacion,
            'mensaje': mensaje,
            'total_escenarios_evaluados': len(escenarios_evaluados),
            'todos_escenarios': escenarios_evaluados,
            'prioridad_optimizacion': prioridad,
        }
        
        logger.info(
            f"✅ Optimización completada: {len(escenarios_evaluados)} escenarios evaluados"
        )
        logger.info(mensaje)
        
        return resultado
    
    def generar_recomendaciones_detalladas(
        self,
        resultado_optimizacion: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Genera recomendaciones específicas y accionables basadas en la optimización.
        
        Returns:
            list: Lista de recomendaciones con formato para UI
        """
        recomendaciones = []
        
        escenario_actual = resultado_optimizacion['escenario_actual']
        escenario_optimo = resultado_optimizacion['escenario_optimo']
        mejora_ingreso = resultado_optimizacion['mejora_ingreso']
        
        # RECOMENDACIÓN 1: Aplicar descuentos
        if escenario_optimo['total_descuentos'] > 0:
            desc_mo = escenario_optimo['desc_mano_obra']
            desc_piezas = escenario_optimo['desc_piezas']
            
            acciones = []
            if desc_mo > 0:
                acciones.append(
                    f"Descuento {desc_mo*100:.0f}% en mano de obra "
                    f"(ahorro cliente: ${escenario_optimo['mano_obra_descuento']:,.0f})"
                )
            if desc_piezas > 0:
                acciones.append(
                    f"Descuento {desc_piezas*100:.0f}% en piezas "
                    f"(ahorro cliente: ${escenario_optimo['piezas_descuento']:,.0f})"
                )
            
            recomendaciones.append({
                'tipo': 'descuentos',
                'prioridad': 'alta',
                'icono': '💰',
                'titulo': 'Optimizar Descuentos',
                'descripcion': f"Ajustar estructura de precios para maximizar aceptación",
                'acciones': acciones,
                'impacto': f"+${mejora_ingreso:,.0f} en ingresos esperados",
                'color': 'success'
            })
        
        # RECOMENDACIÓN 2: Comparación con competencia
        if escenario_actual['prob_aceptacion'] < 0.5:
            recomendaciones.append({
                'tipo': 'competencia',
                'prioridad': 'media',
                'icono': '🔍',
                'titulo': 'Verificar Precios de Mercado',
                'descripcion': 'Baja probabilidad de aceptación sugiere precio fuera de rango',
                'acciones': [
                    'Investigar precios de competidores para reparación similar',
                    'Validar que diagnóstico y piezas sean correctos',
                    'Considerar ofrecer alternativas más económicas'
                ],
                'impacto': 'Evitar rechazo por precio no competitivo',
                'color': 'warning'
            })
        
        # RECOMENDACIÓN 3: Destacar valor
        if escenario_optimo['prob_aceptacion'] >= 0.7:
            recomendaciones.append({
                'tipo': 'valor',
                'prioridad': 'media',
                'icono': '⭐',
                'titulo': 'Destacar Valor del Servicio',
                'descripcion': 'Alta probabilidad de aceptación permite enfocarse en valor',
                'acciones': [
                    'Enfatizar garantía y calidad del servicio',
                    'Mencionar experiencia y certificaciones',
                    'Ofrecer servicios complementarios sin costo'
                ],
                'impacto': 'Fortalecer relación con cliente y reputación',
                'color': 'info'
            })
        
        return recomendaciones
