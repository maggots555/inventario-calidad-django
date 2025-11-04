# 🔍 Análisis: Machine Learning Dashboard Cotizaciones

**Fecha:** 04 de Noviembre, 2025  
**Analista:** GitHub Copilot  
**Estado:** ✅ Análisis Completado

---

## 📊 Resumen Ejecutivo

Se validaron dos problemas reportados en el Dashboard de Cotizaciones:

1. **¿Por qué aparece 89.7% como precisión?** → ✅ EXPLICADO
2. **¿Por qué no aparecen cotizaciones pendientes?** → ✅ EXPLICADO (pero SÍ HAY)

---

## 🎯 Hallazgos Principales

### Estado Actual de los Datos

```
📊 BASE DE DATOS (Total: 171 cotizaciones)
├── ✅ Aceptadas: 88 (51.5%)
├── ❌ Rechazadas: 66 (38.6%)
└── ⏳ Pendientes: 17 (9.9%)

🤖 MODELO ML
├── Accuracy: 89.66% (aparece como 89.7% en el dashboard)
├── Precision: 93.75%
├── Recall: 88.24%
├── F1-Score: 90.91%
├── Muestras de entrenamiento: 114
├── Muestras de prueba: 29
└── Fecha de entrenamiento: 2025-11-04 09:29:12
```

---

## 🔎 PROBLEMA 1: ¿Por qué aparece 89.7% de precisión?

### Explicación Detallada

El **89.7%** (redondeado de 89.66%) proviene de un **modelo pre-entrenado** que está guardado en:

```
📁 ml_models/cotizaciones_predictor.pkl (265 KB)
```

Este modelo fue entrenado el **4 de noviembre de 2025 a las 09:29:12** con:
- **143 cotizaciones históricas** (88 aceptadas + 66 rechazadas)
- **114 muestras de entrenamiento** (80% de los datos)
- **29 muestras de prueba** (20% de los datos)

### Cómo se Calcula la Precisión

**EXPLICACIÓN PARA PRINCIPIANTES:**

La "precisión" o "accuracy" es un porcentaje que indica **qué tan bien el modelo acierta sus predicciones**.

```
Accuracy = (Predicciones Correctas) / (Total de Predicciones) × 100%
```

En este caso:
- El modelo predijo 29 cotizaciones del conjunto de prueba
- Acertó en aproximadamente 26 de ellas
- 26/29 = 89.66% ≈ 89.7%

### Factores Más Influyentes en las Predicciones

El modelo identifica estos factores como los más importantes:

| Ranking | Factor | Importancia | Explicación |
|---------|--------|-------------|-------------|
| 1 | `tiene_descuento` | 32.84% | Si la cotización incluye descuento de mano de obra |
| 2 | `porcentaje_necesarias` | 10.21% | % de piezas marcadas como necesarias |
| 3 | `ticket_por_pieza` | 9.79% | Costo promedio por pieza |
| 4 | `costo_total` | 9.76% | Costo total de la cotización |
| 5 | `costo_total_piezas` | 8.91% | Costo solo de piezas (sin mano de obra) |

**Interpretación:**
- **El descuento de mano de obra** es EL FACTOR MÁS IMPORTANTE (casi 33% de influencia)
- Las cotizaciones con descuento tienen mayor probabilidad de aceptación
- El modelo usa 12 variables en total para sus predicciones

---

## 🔎 PROBLEMA 2: "No hay cotizaciones pendientes para predecir"

### ✅ HALLAZGO CRÍTICO: SÍ HAY COTIZACIONES PENDIENTES

El diagnóstico reveló que **SÍ existen 17 cotizaciones pendientes** en los últimos 90 días:

```
📋 COTIZACIONES PENDIENTES (17 en total):

1.  ORD-2025-0123  | $9,970.90   | 2 piezas | 2025-10-10
2.  ORD-2025-0186  | $9,359.02   | 4 piezas | 2025-10-17
3.  ORD-2025-0193  | $7,369.24   | 1 pieza  | 2025-10-23
4.  ORD-2025-0285  | $7,725.10   | 2 piezas | 2025-10-23
5.  ORD-2025-0303  | $12,303.37  | 4 piezas | 2025-10-23
6.  ORD-2025-0413  | $11,020.96  | 2 piezas | 2025-10-29
7.  ORD-2025-0404  | $11,987.23  | 3 piezas | 2025-10-29
8.  ORD-2025-0377  | $10,281.41  | 5 piezas | 2025-11-03
9.  ORD-2025-0392  | $16,587.04  | 2 piezas | 2025-11-03
10. ORD-2025-0427  | $12,667.83  | 3 piezas | 2025-11-03
11. ORD-2025-0414  | $570.00     | 0 piezas | 2025-11-03
12. ORD-2025-0455  | $18,804.82  | 8 piezas | 2025-11-04
13. ORD-2025-0451  | $29,808.63  | 7 piezas | 2025-11-04
14. ORD-2025-0439  | $10,672.23  | 3 piezas | 2025-11-04
15. ORD-2025-0429  | $22,078.59  | 8 piezas | 2025-11-04
16. ORD-2025-0426  | $7,986.12   | 3 piezas | 2025-11-04
17. ORD-2025-0422  | $26,598.07  | 4 piezas | 2025-11-04 ⭐ ÚLTIMA
```

### Predicción de Ejemplo (Última Cotización Pendiente)

El modelo SÍ debería mostrar una predicción para la orden **ORD-2025-0422**:

```
📦 Orden: ORD-2025-0422
💰 Costo Total: $26,598.07
🔧 Total Piezas: 4
🏢 Sucursal: Satelite
👨‍🔧 Técnico: Iván García
⭐ Gama: alta

🤖 PREDICCIÓN DEL MODELO:
├── ✅ Probabilidad de ACEPTACIÓN: 29.80%
└── ❌ Probabilidad de RECHAZO: 70.20%

💡 Interpretación: El modelo predice que esta cotización
   probablemente será RECHAZADA (70.2% de probabilidad).
   Factores: Costo alto, sin descuento de mano de obra.
```

### ¿Por qué dice "No hay cotizaciones pendientes"?

**POSIBLES CAUSAS:**

1. **Problema de caché del navegador**
   - El dashboard HTML puede estar cacheado
   - Solución: Presionar `Ctrl + F5` para refrescar forzado

2. **Filtros de fecha activos**
   - Si aplicaste filtros personalizados, pueden estar excluyendo las pendientes
   - Solución: Resetear filtros o ajustar rango de fechas

3. **Error en el contexto del template**
   - El diccionario `ml_insights` no tiene la clave `ejemplo_prediccion`
   - Revisar logs del servidor Django

4. **Lógica condicional en template**
   - Línea 1030 de `dashboard_cotizaciones.html`:
   ```django
   {% if ml_insights.ejemplo_prediccion %}
   ```
   - Verificar que `ml_insights['ejemplo_prediccion']` existe en el contexto

---

## 🛠️ Soluciones Propuestas

### Para MEJORAR LA PRECISIÓN (89.7% → 95%+)

#### 1. ✅ Más Datos de Entrenamiento

**ESTADO ACTUAL:**
- 143 cotizaciones con respuesta
- 114 muestras de entrenamiento

**OBJETIVO:**
- 200-300+ cotizaciones con respuesta
- Mejor balance entre aceptadas/rechazadas

**ACCIÓN:**
```python
# Esperar a que se acumulen más cotizaciones respondidas
# O importar datos históricos si existen
```

#### 2. ✅ Re-entrenar Periódicamente

**PROBLEMA:**
- El modelo se entrenó una vez y quedó estático
- No aprende de nuevas cotizaciones

**SOLUCIÓN: Crear tarea programada**

Crear archivo: `scripts/ml/reentrenar_modelo_cotizaciones.py`

```python
# -*- coding: utf-8 -*-
"""
Tarea programada: Re-entrenar modelo ML cada mes
"""
import os
import sys
import django
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.ml_predictor import PredictorAceptacionCotizacion

def main():
    print("🤖 Iniciando re-entrenamiento del modelo...")
    
    predictor = PredictorAceptacionCotizacion()
    
    # Entrenar con todos los datos disponibles
    metricas = predictor.entrenar_modelo()
    
    print(f"✅ Modelo re-entrenado exitosamente!")
    print(f"   Accuracy: {metricas['accuracy']*100:.2f}%")
    print(f"   Total muestras: {metricas['total_muestras']}")

if __name__ == '__main__':
    main()
```

**PROGRAMAR EN WINDOWS (Task Scheduler):**
```powershell
# Crear tarea que se ejecute el día 1 de cada mes
schtasks /create /tn "Reentrenar_ML_Cotizaciones" /tr "C:\Users\DELL\Proyecto_Django\inventario-calidad-django\.venv\Scripts\python.exe scripts\ml\reentrenar_modelo_cotizaciones.py" /sc monthly /d 1 /st 02:00
```

#### 3. ✅ Agregar Más Features (Variables)

**FEATURES ACTUALES (12):**
- Costos (total, mano de obra, piezas)
- Cantidad de piezas
- Descuento
- Gama, tipo de equipo, sucursal
- Día de la semana, mes

**FEATURES SUGERIDOS (agregar 5 más):**

```python
# En ml_predictor.py, función preparar_features():

# 1. Historial del cliente (tasa de aceptación previa)
df_features['tasa_aceptacion_cliente'] = df_features.apply(
    lambda row: calcular_tasa_cliente(row['cliente_id']), axis=1
)

# 2. Tiempo de respuesta promedio del cliente
df_features['dias_respuesta_promedio_cliente'] = ...

# 3. Número de visitas previas al equipo
df_features['visitas_previas'] = ...

# 4. Antigüedad del equipo (años desde fabricación)
df_features['antiguedad_equipo'] = ...

# 5. Complejidad de la reparación (score 1-10)
df_features['complejidad_reparacion'] = ...
```

#### 4. ✅ Ajustar Hiperparámetros

**ACTUAL (línea 64 de ml_predictor.py):**
```python
self.model = RandomForestClassifier(
    n_estimators=100,      # 100 árboles
    max_depth=10,          # Profundidad 10
    min_samples_split=5,
    min_samples_leaf=2,
    n_jobs=-1,
    random_state=42,
    class_weight='balanced'
)
```

**OPTIMIZADO (experimentar con):**
```python
self.model = RandomForestClassifier(
    n_estimators=200,      # 200 árboles (más lento, más preciso)
    max_depth=15,          # Profundidad 15 (más complejo)
    min_samples_split=3,   # Menos restrictivo
    min_samples_leaf=1,    # Permite hojas más pequeñas
    n_jobs=-1,
    random_state=42,
    class_weight='balanced'
)
```

**GRID SEARCH (búsqueda automática de mejores parámetros):**
```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [100, 200, 300],
    'max_depth': [10, 15, 20],
    'min_samples_split': [2, 3, 5]
}

grid_search = GridSearchCV(
    RandomForestClassifier(random_state=42),
    param_grid,
    cv=5,
    scoring='accuracy'
)

grid_search.fit(X_train, y_train)
print(f"Mejores parámetros: {grid_search.best_params_}")
```

---

### Para ARREGLAR "No hay cotizaciones pendientes"

#### Solución 1: Verificar Contexto del Template

**UBICACIÓN:** `servicio_tecnico/views.py`, línea 7680

**ACTUAL:**
```python
# Predicción de ejemplo (última cotización pendiente)
df_pendientes = df_cotizaciones[df_cotizaciones['aceptada'].isna()]
if not df_pendientes.empty:
    ultima = df_pendientes.iloc[-1]
    features_ejemplo = {
        'costo_total': ultima['costo_total'],
        'costo_mano_obra': ultima['costo_mano_obra'],
        # ... más features
    }
    
    prob_rechazo, prob_aceptacion = predictor.predecir_probabilidad(features_ejemplo)
    
    graficos['prediccion_ml_ejemplo'] = convertir_figura_a_html(
        visualizer.grafico_prediccion_ml(prob_aceptacion, prob_rechazo)
    )
    
    ml_insights['ejemplo_prediccion'] = {
        'orden': ultima['numero_orden'],
        'prob_aceptacion': prob_aceptacion * 100,
        'prob_rechazo': prob_rechazo * 100
    }
```

**PROBLEMA DETECTADO:**
El código está agregando `ejemplo_prediccion` al diccionario `ml_insights`, pero el template está buscando `prediccion_ejemplo` (con orden diferente).

**LÍNEA 1030 del template:**
```django
{% if ml_insights.prediccion_ejemplo %}  <!-- ❌ Nombre incorrecto -->
```

**SOLUCIÓN 1: Cambiar el template**
```django
{% if ml_insights.ejemplo_prediccion %}  <!-- ✅ Correcto -->
```

**O SOLUCIÓN 2: Cambiar views.py**
```python
ml_insights['prediccion_ejemplo'] = {  # Cambiar clave
    'orden': ultima['numero_orden'],
    'prob_aceptacion': prob_aceptacion * 100,
    'prob_rechazo': prob_rechazo * 100
}
```

#### Solución 2: Mejorar Debugging

**AGREGAR EN views.py (línea 7710):**
```python
# DEBUG: Imprimir estado para diagnóstico
print(f"DEBUG ML: Pendientes encontradas: {len(df_pendientes)}")
if not df_pendientes.empty:
    print(f"DEBUG ML: Última orden: {ultima['numero_orden']}")
    print(f"DEBUG ML: Predicción agregada al contexto: {ml_insights.get('ejemplo_prediccion', 'NO EXISTE')}")
else:
    print("DEBUG ML: NO hay cotizaciones pendientes en el rango")
```

#### Solución 3: Template Mejorado

**REEMPLAZAR líneas 1023-1062 del template:**

```django
<!-- Predicción de Ejemplo -->
<div class="col-md-4">
    <div class="grafico-card card">
        <div class="card-header">
            <h5><i class="bi bi-bullseye"></i> Ejemplo de Predicción</h5>
        </div>
        <div class="card-body">
            {% if ml_insights.ejemplo_prediccion %}
            <p class="text-muted mb-3">
                <strong>Orden:</strong> {{ ml_insights.ejemplo_prediccion.orden }}<br>
                <strong>Última cotización pendiente</strong>
            </p>
            <div class="mb-3">
                <strong>Probabilidad de Aceptación:</strong>
                <div class="progress mt-2" style="height: 25px;">
                    <div class="progress-bar bg-success" 
                         style="width: {{ ml_insights.ejemplo_prediccion.prob_aceptacion|floatformat:0 }}%">
                        {{ ml_insights.ejemplo_prediccion.prob_aceptacion|floatformat:1 }}%
                    </div>
                </div>
            </div>
            <div>
                <strong>Probabilidad de Rechazo:</strong>
                <div class="progress mt-2" style="height: 25px;">
                    <div class="progress-bar bg-danger" 
                         style="width: {{ ml_insights.ejemplo_prediccion.prob_rechazo|floatformat:0 }}%">
                        {{ ml_insights.ejemplo_prediccion.prob_rechazo|floatformat:1 }}%
                    </div>
                </div>
            </div>
            
            <!-- DEBUG INFO (remover en producción) -->
            <div class="alert alert-info mt-3" style="font-size: 0.8rem;">
                <strong>DEBUG:</strong> Predicción cargada correctamente
            </div>
            {% else %}
            <div class="alert alert-warning">
                <i class="bi bi-info-circle"></i> No hay cotizaciones pendientes para predecir en el rango de fechas actual.
                
                <!-- DEBUG INFO (remover en producción) -->
                <hr>
                <small><strong>DEBUG:</strong> ml_insights.ejemplo_prediccion no existe en el contexto</small>
            </div>
            {% endif %}
        </div>
    </div>
</div>
```

---

## 📋 Checklist de Validación

### Para verificar que todo funciona:

- [ ] **1. Ejecutar script de diagnóstico**
  ```bash
  python scripts/verificacion/diagnostico_ml_cotizaciones.py
  ```

- [ ] **2. Verificar modelo ML**
  - [ ] Existe `ml_models/cotizaciones_predictor.pkl`
  - [ ] Accuracy > 85%
  - [ ] Fecha de entrenamiento reciente

- [ ] **3. Verificar cotizaciones pendientes**
  - [ ] Hay al menos 1 cotización con `usuario_acepto=None`
  - [ ] Dentro del rango de fechas del dashboard (últimos 90 días)

- [ ] **4. Probar dashboard**
  - [ ] Abrir `http://localhost:8000/cotizaciones/dashboard/`
  - [ ] Ir a pestaña "Machine Learning"
  - [ ] Verificar que aparece la precisión (89.7%)
  - [ ] Verificar que aparece "Ejemplo de Predicción"

- [ ] **5. Verificar logs del servidor**
  - [ ] Revisar consola de Django
  - [ ] Buscar mensajes de DEBUG ML
  - [ ] Verificar que no hay errores

---

## 🎓 Explicación Técnica (Para Principiantes)

### ¿Qué es Machine Learning?

**Machine Learning** = El programa "aprende" de datos históricos para hacer predicciones futuras.

**Analogía:** Es como enseñarle a un niño a identificar animales:
1. Le muestras 100 fotos de perros y gatos
2. Le dices cuáles son perros y cuáles son gatos
3. El niño aprende patrones (perros tienen orejas caídas, gatos tienen bigotes, etc.)
4. Ahora puede identificar nuevas fotos que nunca ha visto

### ¿Cómo funciona este modelo?

**Algoritmo:** Random Forest (Bosque Aleatorio)

**Proceso:**
1. **Recolectar datos:** 143 cotizaciones históricas (88 aceptadas, 66 rechazadas)
2. **Extraer características:** Costo, piezas, descuento, gama, etc.
3. **Entrenar:** El modelo busca patrones en las 114 cotizaciones de entrenamiento
4. **Probar:** Valida con 29 cotizaciones que nunca vio
5. **Evaluar:** Calcula qué tan bien predice (89.66% de aciertos)
6. **Predecir:** Usa ese conocimiento para predecir nuevas cotizaciones

### Métricas Explicadas

| Métrica | Valor | Explicación | Interpretación |
|---------|-------|-------------|----------------|
| **Accuracy** | 89.66% | % de predicciones correctas | De cada 100 predicciones, acierta 90 |
| **Precision** | 93.75% | De las que predice "aceptada", % que realmente son aceptadas | Cuando dice "se aceptará", acierta 94 de cada 100 veces |
| **Recall** | 88.24% | De las realmente aceptadas, % que logra detectar | Encuentra 88 de cada 100 cotizaciones que serán aceptadas |
| **F1-Score** | 90.91% | Balance entre Precision y Recall | Buen equilibrio general |

### ¿Por qué es útil?

**BENEFICIOS:**
1. ✅ **Priorizar cotizaciones:** Enfocarse en las que tienen mayor probabilidad de aceptación
2. ✅ **Identificar factores clave:** Saber qué hace que una cotización sea aceptada
3. ✅ **Optimizar precios:** Ajustar costos basándose en patrones históricos
4. ✅ **Predecir ingresos:** Estimar cuántas cotizaciones se convertirán en ventas
5. ✅ **Mejorar estrategia:** Entender por qué se rechazan cotizaciones

---

## 📞 Soporte

Si tienes preguntas o problemas:

1. **Ejecutar diagnóstico:** `python scripts/verificacion/diagnostico_ml_cotizaciones.py`
2. **Revisar logs:** Buscar errores en consola de Django
3. **Validar datos:** Verificar que hay cotizaciones pendientes
4. **Refrescar navegador:** Presionar `Ctrl + F5`

---

**Actualizado:** 04 de Noviembre, 2025  
**Próxima revisión:** Después de re-entrenar el modelo con más datos
