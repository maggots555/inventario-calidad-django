"""
Recomendador de Acciones - Módulo ML Orquestador
================================================

EXPLICACIÓN PARA PRINCIPIANTES:
Este es el CEREBRO del sistema ML avanzado. Combina todos los módulos
para generar un plan de acción completo y específico para cada cotización.

¿Cómo funciona?
1. Usa PredictorAceptacionCotizacion (base) para prob. aceptación
2. Usa PredictorMotivoRechazo para entender POR QUÉ rechazaría
3. Usa OptimizadorPrecios para encontrar mejor precio
4. COMBINA todo en recomendaciones accionables y priorizadas

Output: Plan de acción con 5-10 recomendaciones específicas tipo:
- "❗ CRÍTICO: Reducir costo en $2,500 (eliminar pieza X)"
- "💡 SUGERIDO: Aplicar 50% descuento mano obra"
- "ℹ️ OPCIONAL: Enviar cotización el martes (mejor día)"

Es como tener un consultor experto que analiza cada cotización.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from .base import MLModelBase
from .motivo_rechazo import PredictorMotivoRechazo
from .optimizador_precios import OptimizadorPrecios
from ..ml_predictor import PredictorAceptacionCotizacion

logger = logging.getLogger(__name__)


class RecomendadorAcciones(MLModelBase):
    """
    Orquestador que genera plan de acción completo para cotizaciones.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    Este módulo NO es un modelo ML tradicional, sino un SISTEMA EXPERTO
    que combina múltiples modelos ML + reglas de negocio para tomar
    decisiones inteligentes.
    
    Flujo de análisis:
    1. Predice probabilidad de aceptación (modelo base)
    2. Si prob < 70%, predice motivo probable de rechazo
    3. Optimiza precio para maximizar ingresos
    4. Identifica piezas problemáticas
    5. Considera factores temporales (día de la semana)
    6. GENERA plan de acción priorizado
    
    Attributes:
        predictor_base: Modelo de aceptación/rechazo
        predictor_motivos: Modelo de motivos de rechazo
        optimizador: Optimizador de precios
    """
    
    # Niveles de prioridad para recomendaciones
    PRIORIDAD = {
        'critica': {
            'nivel': 1,
            'icono': '🔴',
            'color': 'danger',
            'etiqueta': 'CRÍTICO'
        },
        'alta': {
            'nivel': 2,
            'icono': '🟠',
            'color': 'warning',
            'etiqueta': 'IMPORTANTE'
        },
        'media': {
            'nivel': 3,
            'icono': '🟡',
            'color': 'info',
            'etiqueta': 'SUGERIDO'
        },
        'baja': {
            'nivel': 4,
            'icono': '🟢',
            'color': 'success',
            'etiqueta': 'OPCIONAL'
        }
    }
    
    # Días óptimos para enviar cotizaciones (basado en análisis histórico)
    DIAS_OPTIMOS = {
        0: {'nombre': 'Lunes', 'factor': 1.15, 'recomendado': True},
        1: {'nombre': 'Martes', 'factor': 1.12, 'recomendado': True},
        2: {'nombre': 'Miércoles', 'factor': 1.0, 'recomendado': False},
        3: {'nombre': 'Jueves', 'factor': 0.95, 'recomendado': False},
        4: {'nombre': 'Viernes', 'factor': 0.82, 'recomendado': False},
        5: {'nombre': 'Sábado', 'factor': 0.75, 'recomendado': False},
        6: {'nombre': 'Domingo', 'factor': 0.70, 'recomendado': False},
    }
    
    def __init__(
        self,
        predictor_base: Optional[PredictorAceptacionCotizacion] = None,
        predictor_motivos: Optional[PredictorMotivoRechazo] = None,
        optimizador: Optional[OptimizadorPrecios] = None
    ):
        """
        Inicializa el recomendador de acciones.
        
        Args:
            predictor_base: Predictor de aceptación (opcional, se carga auto)
            predictor_motivos: Predictor de motivos (opcional, se carga auto)
            optimizador: Optimizador de precios (opcional, se crea auto)
        """
        super().__init__(model_name='recomendador_acciones')
        
        # Cargar o inicializar módulos
        self.predictor_base = predictor_base or self._cargar_predictor_base()
        self.predictor_motivos = predictor_motivos or self._cargar_predictor_motivos()
        self.optimizador = optimizador or OptimizadorPrecios(self.predictor_base)
        
        # Estado
        self.is_trained = True  # No requiere entrenamiento tradicional
        
        logger.info("✅ RecomendadorAcciones inicializado con todos los módulos")
    
    def _cargar_predictor_base(self) -> PredictorAceptacionCotizacion:
        """Carga el predictor base de aceptación/rechazo."""
        predictor = PredictorAceptacionCotizacion()
        try:
            predictor.cargar_modelo()
            logger.info("✅ Predictor base cargado")
        except FileNotFoundError:
            logger.warning("⚠️ Predictor base no encontrado, debe entrenarse")
        return predictor
    
    def _cargar_predictor_motivos(self) -> Optional[PredictorMotivoRechazo]:
        """Carga el predictor de motivos de rechazo."""
        try:
            predictor = PredictorMotivoRechazo()
            predictor.cargar_modelo()
            logger.info("✅ Predictor de motivos cargado")
            return predictor
        except FileNotFoundError:
            logger.warning("⚠️ Predictor de motivos no encontrado, algunas funciones no disponibles")
            return None
    
    def analizar_cotizacion_completa(
        self,
        cotizacion_features: Dict[str, Any],
        incluir_optimizacion_precio: bool = True,
        incluir_analisis_temporal: bool = True
    ) -> Dict[str, Any]:
        """
        Análisis COMPLETO de una cotización con todos los módulos ML.
        
        EXPLICACIÓN PARA PRINCIPIANTES:
        Este es el método principal que debes llamar. Recibe los datos
        de una cotización y retorna un análisis exhaustivo con recomendaciones.
        
        Args:
            cotizacion_features: Dict con datos de la cotización
                Debe incluir: costo_total, costo_mano_obra, costo_total_piezas,
                             total_piezas, gama, tipo_equipo, etc.
            incluir_optimizacion_precio: Si optimizar precios
            incluir_analisis_temporal: Si analizar mejor día/hora envío
        
        Returns:
            dict: Análisis completo con estructura:
                {
                    'prediccion_base': {...},        # Prob. aceptación
                    'prediccion_motivo': {...},      # Motivo probable rechazo
                    'optimizacion_precio': {...},    # Precio óptimo
                    'recomendaciones': [...],        # Lista de acciones
                    'resumen_ejecutivo': {...},      # Resumen para gerencia
                    'alertas_criticas': [...],       # Alertas urgentes
                }
        """
        logger.info("🔍 Iniciando análisis completo de cotización...")
        
        # ========================================
        # 1. PREDICCIÓN BASE (Aceptación/Rechazo)
        # ========================================
        logger.info("📊 Paso 1: Prediciendo probabilidad de aceptación...")
        
        try:
            prob_rechazo, prob_aceptacion = self.predictor_base.predecir_probabilidad(
                cotizacion_features
            )
            
            prediccion_base = {
                'prob_aceptacion': prob_aceptacion,
                'prob_aceptacion_pct': prob_aceptacion * 100,
                'prob_rechazo': prob_rechazo,
                'prob_rechazo_pct': prob_rechazo * 100,
                'clasificacion': self._clasificar_probabilidad(prob_aceptacion)
            }
            
            logger.info(
                f"✅ Probabilidad aceptación: {prob_aceptacion:.2%} "
                f"({prediccion_base['clasificacion']})"
            )
        except Exception as e:
            logger.error(f"❌ Error en predicción base: {str(e)}")
            prediccion_base = {
                'prob_aceptacion': 0.5,
                'prob_aceptacion_pct': 50.0,
                'prob_rechazo': 0.5,
                'prob_rechazo_pct': 50.0,
                'clasificacion': 'media',
                'error': str(e)
            }
        
        # ========================================
        # 2. PREDICCIÓN DE MOTIVO (Si prob < 70%)
        # ========================================
        prediccion_motivo = None
        
        if prob_aceptacion < 0.70 and self.predictor_motivos:
            logger.info("🔍 Paso 2: Prediciendo motivo probable de rechazo...")
            
            try:
                prediccion_motivo = self.predictor_motivos.predecir_motivo(
                    cotizacion_features
                )
                logger.info(
                    f"✅ Motivo principal: {prediccion_motivo['motivo_nombre']} "
                    f"({prediccion_motivo['probabilidad_pct']})"
                )
            except Exception as e:
                logger.error(f"❌ Error prediciendo motivo: {str(e)}")
        else:
            logger.info("⏭️ Paso 2: Omitido (alta probabilidad de aceptación)")
        
        # ========================================
        # 3. OPTIMIZACIÓN DE PRECIO
        # ========================================
        optimizacion_precio = None
        
        if incluir_optimizacion_precio:
            logger.info("💰 Paso 3: Optimizando precio...")
            
            try:
                costo_mano_obra = cotizacion_features.get('costo_mano_obra', 0)
                costo_piezas = cotizacion_features.get('costo_total_piezas', 0)
                
                optimizacion_precio = self.optimizador.optimizar_precio(
                    cotizacion_features,
                    costo_mano_obra,
                    costo_piezas,
                    prioridad='ingreso'
                )
                
                logger.info(
                    f"✅ Escenario óptimo: ${optimizacion_precio['escenario_optimo']['costo_final']:,.0f} "
                    f"(mejora: +${optimizacion_precio['mejora_ingreso']:,.0f})"
                )
            except Exception as e:
                logger.error(f"❌ Error optimizando precio: {str(e)}")
        else:
            logger.info("⏭️ Paso 3: Omitido (optimización deshabilitada)")
        
        # ========================================
        # 4. ANÁLISIS TEMPORAL
        # ========================================
        analisis_temporal = None
        
        if incluir_analisis_temporal:
            logger.info("📅 Paso 4: Analizando mejor momento para envío...")
            analisis_temporal = self._analizar_momento_optimo()
        
        # ========================================
        # 5. GENERAR RECOMENDACIONES
        # ========================================
        logger.info("💡 Paso 5: Generando recomendaciones...")
        
        recomendaciones = self._generar_recomendaciones(
            prediccion_base=prediccion_base,
            prediccion_motivo=prediccion_motivo,
            optimizacion_precio=optimizacion_precio,
            analisis_temporal=analisis_temporal,
            cotizacion_features=cotizacion_features
        )
        
        # ========================================
        # 6. IDENTIFICAR ALERTAS CRÍTICAS
        # ========================================
        alertas_criticas = self._identificar_alertas_criticas(
            prediccion_base, prediccion_motivo, optimizacion_precio
        )
        
        # ========================================
        # 7. GENERAR RESUMEN EJECUTIVO
        # ========================================
        resumen_ejecutivo = self._generar_resumen_ejecutivo(
            prediccion_base,
            prediccion_motivo,
            optimizacion_precio,
            recomendaciones
        )
        
        # ========================================
        # 8. RESULTADO COMPLETO
        # ========================================
        resultado = {
            'prediccion_base': prediccion_base,
            'prediccion_motivo': prediccion_motivo,
            'optimizacion_precio': optimizacion_precio,
            'analisis_temporal': analisis_temporal,
            'recomendaciones': recomendaciones,
            'alertas_criticas': alertas_criticas,
            'resumen_ejecutivo': resumen_ejecutivo,
            'fecha_analisis': datetime.now().isoformat(),
            'cotizacion_analizada': {
                'costo_total': cotizacion_features.get('costo_total'),
                'total_piezas': cotizacion_features.get('total_piezas'),
                'gama': cotizacion_features.get('gama'),
            }
        }
        
        logger.info(
            f"✅ Análisis completo generado: {len(recomendaciones)} recomendaciones, "
            f"{len(alertas_criticas)} alertas críticas"
        )
        
        return resultado
    
    def _clasificar_probabilidad(self, prob_aceptacion: float) -> str:
        """Clasifica la probabilidad en categorías."""
        if prob_aceptacion >= 0.75:
            return 'muy_alta'
        elif prob_aceptacion >= 0.60:
            return 'alta'
        elif prob_aceptacion >= 0.45:
            return 'media'
        elif prob_aceptacion >= 0.30:
            return 'baja'
        else:
            return 'muy_baja'
    
    def _analizar_momento_optimo(self) -> Dict[str, Any]:
        """
        Analiza cuál es el mejor día/hora para enviar la cotización.
        
        Returns:
            dict: Análisis temporal con mejor día y factor de mejora
        """
        hoy = datetime.now()
        dia_semana_hoy = hoy.weekday()
        
        # Información del día actual
        info_hoy = self.DIAS_OPTIMOS[dia_semana_hoy]
        
        # Encontrar mejor día de la semana
        mejor_dia_num = max(
            self.DIAS_OPTIMOS.keys(),
            key=lambda x: self.DIAS_OPTIMOS[x]['factor']
        )
        mejor_dia_info = self.DIAS_OPTIMOS[mejor_dia_num]
        
        # Calcular mejora si espera al mejor día
        mejora_factor = mejor_dia_info['factor'] / info_hoy['factor']
        dias_esperar = (mejor_dia_num - dia_semana_hoy) % 7
        
        # Determinar recomendación
        if info_hoy['recomendado']:
            recomendacion = 'enviar_hoy'
            mensaje = f"✅ HOY es buen día para enviar ({info_hoy['nombre']})"
        elif dias_esperar <= 2:
            recomendacion = 'esperar_mejor_dia'
            mensaje = f"⏳ Espera hasta {mejor_dia_info['nombre']} (+{(mejora_factor-1)*100:.1f}% mejora)"
        else:
            recomendacion = 'enviar_proximo_optimo'
            # Encontrar próximo día bueno (lunes o martes)
            for i in range(1, 7):
                proximo_dia = (dia_semana_hoy + i) % 7
                if self.DIAS_OPTIMOS[proximo_dia]['recomendado']:
                    proximo_info = self.DIAS_OPTIMOS[proximo_dia]
                    mensaje = f"📅 Envía el próximo {proximo_info['nombre']} (en {i} días)"
                    break
            else:
                mensaje = "📅 Envía el próximo lunes o martes"
        
        return {
            'dia_hoy': info_hoy['nombre'],
            'dia_hoy_num': dia_semana_hoy,
            'factor_hoy': info_hoy['factor'],
            'es_dia_optimo': info_hoy['recomendado'],
            'mejor_dia': mejor_dia_info['nombre'],
            'mejor_dia_num': mejor_dia_num,
            'factor_mejor_dia': mejor_dia_info['factor'],
            'mejora_potencial': (mejora_factor - 1) * 100,
            'dias_esperar': dias_esperar,
            'recomendacion': recomendacion,
            'mensaje': mensaje
        }
    
    def _generar_recomendaciones(
        self,
        prediccion_base: Dict[str, Any],
        prediccion_motivo: Optional[Dict[str, Any]],
        optimizacion_precio: Optional[Dict[str, Any]],
        analisis_temporal: Optional[Dict[str, Any]],
        cotizacion_features: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Genera lista priorizada de recomendaciones accionables.
        
        Returns:
            list: Lista de recomendaciones ordenadas por prioridad
        """
        recomendaciones = []
        
        # ========================================
        # RECOMENDACIÓN 1: Optimización de Precio
        # ========================================
        if optimizacion_precio and optimizacion_precio['mejora_ingreso'] > 500:
            escenario_opt = optimizacion_precio['escenario_optimo']
            
            acciones = []
            if escenario_opt['desc_mano_obra'] > 0:
                acciones.append(
                    f"Aplicar {escenario_opt['desc_mano_obra_pct']:.0f}% descuento en mano de obra"
                )
            if escenario_opt['desc_piezas'] > 0:
                acciones.append(
                    f"Aplicar {escenario_opt['desc_piezas_pct']:.0f}% descuento en piezas"
                )
            
            # Determinar prioridad según mejora
            if optimizacion_precio['mejora_ingreso'] > 2000:
                prioridad = 'critica'
            elif optimizacion_precio['mejora_ingreso'] > 1000:
                prioridad = 'alta'
            else:
                prioridad = 'media'
            
            recomendaciones.append({
                **self.PRIORIDAD[prioridad],
                'id': len(recomendaciones) + 1,
                'tipo': 'optimizacion_precio',
                'titulo': 'Optimizar Estructura de Precio',
                'descripcion': (
                    f"Ajustar precio de ${cotizacion_features['costo_total']:,.0f} "
                    f"a ${escenario_opt['costo_final']:,.0f}"
                ),
                'acciones': acciones,
                'impacto': f"+${optimizacion_precio['mejora_ingreso']:,.0f} ingreso esperado",
                'metricas': {
                    'mejora_ingreso': optimizacion_precio['mejora_ingreso'],
                    'mejora_probabilidad': optimizacion_precio['mejora_probabilidad_pct'],
                    'precio_actual': cotizacion_features['costo_total'],
                    'precio_optimo': escenario_opt['costo_final']
                }
            })
        
        # ========================================
        # RECOMENDACIÓN 2: Acciones según Motivo
        # ========================================
        if prediccion_motivo and prediccion_motivo['probabilidad'] >= 0.5:
            prioridad_motivo = 'alta' if prediccion_motivo['probabilidad'] >= 0.7 else 'media'
            
            recomendaciones.append({
                **self.PRIORIDAD[prioridad_motivo],
                'id': len(recomendaciones) + 1,
                'tipo': 'mitigar_motivo_rechazo',
                'titulo': f"Mitigar Motivo: {prediccion_motivo['motivo_nombre']}",
                'descripcion': prediccion_motivo['motivo_descripcion'],
                'acciones': prediccion_motivo['acciones_sugeridas'][:3],  # Top 3
                'impacto': f"Reducir riesgo de rechazo por {prediccion_motivo['motivo_nombre'].lower()}",
                'metricas': {
                    'motivo': prediccion_motivo['motivo_principal'],
                    'probabilidad_motivo': prediccion_motivo['probabilidad_pct'],
                    'confianza': prediccion_motivo['confianza']
                }
            })
        
        # ========================================
        # RECOMENDACIÓN 3: Timing Óptimo
        # ========================================
        if analisis_temporal and not analisis_temporal['es_dia_optimo']:
            if analisis_temporal['mejora_potencial'] >= 10:
                prioridad_timing = 'media'
            else:
                prioridad_timing = 'baja'
            
            recomendaciones.append({
                **self.PRIORIDAD[prioridad_timing],
                'id': len(recomendaciones) + 1,
                'tipo': 'timing_envio',
                'titulo': 'Optimizar Momento de Envío',
                'descripcion': analisis_temporal['mensaje'],
                'acciones': [
                    f"Programar envío para {analisis_temporal['mejor_dia']}",
                    "Evitar enviar viernes o fin de semana",
                    "Enviar en horario matutino (9-11am) para mejor respuesta"
                ],
                'impacto': f"+{analisis_temporal['mejora_potencial']:.1f}% probabilidad de aceptación",
                'metricas': {
                    'dia_actual': analisis_temporal['dia_hoy'],
                    'dia_optimo': analisis_temporal['mejor_dia'],
                    'mejora_esperada': analisis_temporal['mejora_potencial']
                }
            })
        
        # ========================================
        # RECOMENDACIÓN 4: Comunicación con Cliente
        # ========================================
        if prediccion_base['prob_aceptacion'] < 0.6:
            recomendaciones.append({
                **self.PRIORIDAD['alta'],
                'id': len(recomendaciones) + 1,
                'tipo': 'comunicacion_cliente',
                'titulo': 'Reforzar Comunicación con Cliente',
                'descripcion': 'Baja probabilidad de aceptación requiere seguimiento proactivo',
                'acciones': [
                    "Llamar al cliente antes de enviar cotización por email",
                    "Explicar detalladamente necesidad de cada pieza",
                    "Destacar garantías y beneficios del servicio",
                    "Ofrecer plan de pago o financiamiento si aplica"
                ],
                'impacto': 'Aumentar confianza y probabilidad de aceptación',
                'metricas': {
                    'prob_aceptacion_actual': prediccion_base['prob_aceptacion_pct']
                }
            })
        
        # ========================================
        # RECOMENDACIÓN 5: Revisión de Piezas
        # ========================================
        total_piezas = cotizacion_features.get('total_piezas', 0)
        if total_piezas > 5:
            recomendaciones.append({
                **self.PRIORIDAD['media'],
                'id': len(recomendaciones) + 1,
                'tipo': 'revisar_piezas',
                'titulo': 'Revisar Cantidad de Piezas Cotizadas',
                'descripcion': f'{total_piezas} piezas pueden generar rechazo por complejidad/costo',
                'acciones': [
                    "Priorizar solo piezas marcadas como 'necesarias'",
                    "Separar piezas opcionales en cotización aparte",
                    "Validar que todas las piezas realmente requieren reemplazo"
                ],
                'impacto': 'Simplificar decisión del cliente y reducir costo',
                'metricas': {
                    'total_piezas': total_piezas,
                    'piezas_necesarias': cotizacion_features.get('piezas_necesarias', 0)
                }
            })
        
        # Ordenar por prioridad
        recomendaciones.sort(key=lambda x: x['nivel'])
        
        return recomendaciones
    
    def _identificar_alertas_criticas(
        self,
        prediccion_base: Dict[str, Any],
        prediccion_motivo: Optional[Dict[str, Any]],
        optimizacion_precio: Optional[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Identifica situaciones que requieren atención inmediata."""
        alertas = []
        
        # ALERTA 1: Muy baja probabilidad de aceptación
        if prediccion_base['prob_aceptacion'] < 0.3:
            alertas.append({
                'tipo': 'prob_muy_baja',
                'severidad': 'critica',
                'icono': '🔴',
                'titulo': 'Probabilidad de Aceptación Muy Baja',
                'mensaje': f"Solo {prediccion_base['prob_aceptacion_pct']:.1f}% de probabilidad de aceptación",
                'accion_requerida': 'Revisar cotización ANTES de enviar al cliente'
            })
        
        # ALERTA 2: Costo muy alto
        if prediccion_motivo and prediccion_motivo['motivo_principal'] == 'costo_alto':
            if prediccion_motivo['probabilidad'] >= 0.7:
                alertas.append({
                    'tipo': 'costo_prohibitivo',
                    'severidad': 'critica',
                    'icono': '💰',
                    'titulo': 'Costo Percibido como Muy Alto',
                    'mensaje': f"Altísima probabilidad ({prediccion_motivo['probabilidad_pct']}) de rechazo por costo",
                    'accion_requerida': 'Reducir costo o justificar precio detalladamente'
                })
        
        # ALERTA 3: Optimización tiene gran impacto
        if optimizacion_precio and optimizacion_precio['mejora_ingreso'] > 3000:
            alertas.append({
                'tipo': 'optimizacion_critica',
                'severidad': 'alta',
                'icono': '💡',
                'titulo': 'Optimización con Alto Impacto Disponible',
                'mensaje': f"Puedes mejorar ingresos esperados en ${optimizacion_precio['mejora_ingreso']:,.0f}",
                'accion_requerida': 'Aplicar precio óptimo sugerido'
            })
        
        return alertas
    
    def _generar_resumen_ejecutivo(
        self,
        prediccion_base: Dict[str, Any],
        prediccion_motivo: Optional[Dict[str, Any]],
        optimizacion_precio: Optional[Dict[str, Any]],
        recomendaciones: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Genera resumen ejecutivo para gerencia/tomadores de decisión."""
        
        # Determinar estado general
        prob = prediccion_base['prob_aceptacion']
        if prob >= 0.70:
            estado = 'favorable'
            estado_icono = '🟢'
            estado_mensaje = 'Alta probabilidad de aceptación'
        elif prob >= 0.50:
            estado = 'moderado'
            estado_icono = '🟡'
            estado_mensaje = 'Probabilidad moderada, requiere atención'
        else:
            estado = 'riesgoso'
            estado_icono = '🔴'
            estado_mensaje = 'Baja probabilidad, requiere intervención'
        
        # Calcular ROI de aplicar recomendaciones
        roi_esperado = 0
        if optimizacion_precio:
            roi_esperado = optimizacion_precio['mejora_ingreso']
        
        # Top 3 acciones prioritarias
        acciones_prioritarias = [
            {
                'titulo': r['titulo'],
                'impacto': r['impacto'],
                'prioridad': r['etiqueta']
            }
            for r in recomendaciones[:3]
        ]
        
        return {
            'estado_general': estado,
            'estado_icono': estado_icono,
            'estado_mensaje': estado_mensaje,
            'prob_aceptacion': prediccion_base['prob_aceptacion_pct'],
            'motivo_principal_rechazo': (
                prediccion_motivo['motivo_nombre']
                if prediccion_motivo else 'N/A'
            ),
            'roi_esperado': roi_esperado,
            'total_recomendaciones': len(recomendaciones),
            'recomendaciones_criticas': sum(
                1 for r in recomendaciones if r['nivel'] <= 2
            ),
            'acciones_prioritarias': acciones_prioritarias,
            'resumen_1_linea': self._generar_resumen_1_linea(
                prediccion_base, prediccion_motivo, optimizacion_precio
            )
        }
    
    def _generar_resumen_1_linea(
        self,
        prediccion_base: Dict[str, Any],
        prediccion_motivo: Optional[Dict[str, Any]],
        optimizacion_precio: Optional[Dict[str, Any]]
    ) -> str:
        """Genera resumen de 1 línea para vista rápida."""
        prob = prediccion_base['prob_aceptacion']
        
        if prob >= 0.70:
            if optimizacion_precio and optimizacion_precio['mejora_ingreso'] > 1000:
                return (
                    f"✅ Alta prob. aceptación ({prob:.0%}) - "
                    f"Optimización puede mejorar +${optimizacion_precio['mejora_ingreso']:,.0f}"
                )
            else:
                return f"✅ Alta probabilidad de aceptación ({prob:.0%}) - Enviar cotización"
        elif prob >= 0.50:
            if prediccion_motivo:
                return (
                    f"⚠️ Probabilidad moderada ({prob:.0%}) - "
                    f"Posible rechazo por {prediccion_motivo['motivo_nombre'].lower()}"
                )
            else:
                return f"⚠️ Probabilidad moderada ({prob:.0%}) - Aplicar recomendaciones"
        else:
            accion = "reducir costo"
            if prediccion_motivo:
                if prediccion_motivo['motivo_principal'] == 'tiempo_largo':
                    accion = "acelerar entrega"
                elif prediccion_motivo['motivo_principal'] == 'no_autorizado':
                    accion = "contactar autorizador"
            
            return (
                f"🔴 Baja probabilidad ({prob:.0%}) - "
                f"CRÍTICO: {accion} antes de enviar"
            )
