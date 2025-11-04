# 🤖 Machine Learning Models Directory

## 📁 Propósito

Este directorio almacena los modelos de Machine Learning entrenados para el sistema de predicción de cotizaciones.

**IMPORTANTE**: Los archivos `.pkl` **NO están en Git** porque son específicos de cada base de datos y deben generarse en cada máquina.

---

## 🚀 Primer Uso (Nueva Máquina)

### 1️⃣ **El Dashboard Auto-Entrena el Modelo**

Cuando accedas al dashboard de cotizaciones por primera vez:

```
http://localhost:8000/servicio-tecnico/dashboard-cotizaciones/
```

**Si no encuentra modelos pre-entrenados**, el sistema automáticamente:
1. ✅ Recopila datos de tu base de datos actual
2. ✅ Entrena un nuevo modelo Random Forest
3. ✅ Guarda los archivos `.pkl` en esta carpeta
4. ✅ Muestra el dashboard con predicciones

**Requisito Mínimo**: Necesitas **al menos 20 cotizaciones** con respuestas (aceptadas/rechazadas) para entrenar el modelo.

---

## 📊 Archivos Generados

Después del primer entrenamiento, encontrarás estos archivos (ignorados por Git):

```
ml_models/
├── cotizaciones_predictor.pkl    # Modelo Random Forest entrenado
├── cotizaciones_encoders.pkl     # Encoders para features categóricas
└── metadata.pkl                   # Metadata del entrenamiento
```

### 🔍 **Descripción de Archivos**

**`cotizaciones_predictor.pkl`**
- Contiene el modelo Random Forest entrenado
- Pesa ~50-200 KB dependiendo de tus datos
- Predice probabilidad de aceptación de cotizaciones

**`cotizaciones_encoders.pkl`**
- Encoders para convertir datos categóricos a numéricos
- Incluye: sucursales, técnicos, gamas de equipos, motivos de rechazo
- Específico de TU base de datos

**`metadata.pkl`**
- Información sobre el entrenamiento
- Fecha, accuracy, número de cotizaciones usadas
- Nombres de features y versión del modelo

---

## 🔄 Re-Entrenar el Modelo

### **Opción 1: Desde Django Shell**

```bash
python manage.py shell
```

```python
from servicio_tecnico.ml_predictor import PredictorAceptacionCotizacion

predictor = PredictorAceptacionCotizacion()
predictor.entrenar_modelo()
print(f"Accuracy: {predictor.model_accuracy:.2%}")
```

### **Opción 2: Desde el Dashboard**

El dashboard re-entrena automáticamente si:
- ❌ No encuentra archivos `.pkl`
- ❌ Los archivos están corruptos
- ⚠️ Han pasado más de 30 días desde el último entrenamiento (recomendado)

---

## 📈 Requisitos de Datos

Para entrenar el modelo necesitas:

| Requisito | Mínimo | Recomendado |
|-----------|--------|-------------|
| Cotizaciones totales | 20 | 100+ |
| Con respuesta (aceptadas/rechazadas) | 20 | 80+ |
| Cotizaciones aceptadas | 10 | 40+ |
| Cotizaciones rechazadas | 10 | 40+ |
| Distribución temporal | 1 mes | 3+ meses |

**Nota**: Con pocos datos, el modelo puede tener baja precisión (accuracy < 60%).

---

## 🎯 Features Utilizadas

El modelo usa **14 características** para predecir aceptación:

### **Numéricas (6)**
1. `costo_total` - Costo total de la cotización
2. `costo_mano_obra` - Costo de mano de obra
3. `total_piezas` - Número de piezas cotizadas
4. `piezas_necesarias` - Piezas necesarias para funcionamiento
5. `piezas_opcionales` - Piezas de mejora/estética
6. `dias_sin_respuesta` - Tiempo transcurrido sin respuesta

### **Categóricas (8)**
7. `sucursal` - Sucursal donde se generó la orden
8. `tecnico` - Técnico que realizó el diagnóstico
9. `gama_equipo` - Gama del equipo (Alta, Media, Baja, Básica)
10. `tipo_servicio` - Tipo de servicio solicitado
11. `mes` - Mes de la cotización (estacionalidad)
12. `dia_semana` - Día de la semana
13. `motivo_rechazo_mas_comun` - Motivo de rechazo más frecuente en período
14. `tiene_descuento_mano_obra` - Si aplica descuento

---

## 🛠️ Mantenimiento

### **Cuándo Re-Entrenar**

Deberías re-entrenar el modelo cuando:
- ✅ Tienes 50+ nuevas cotizaciones
- ✅ Han pasado 30+ días
- ✅ Cambiaron patrones de aceptación
- ✅ Agregaste nuevas sucursales/técnicos
- ✅ El accuracy bajó significativamente

### **Cómo Verificar el Modelo**

En el dashboard, revisa la sección **"Machine Learning & Insights"**:
- 📊 **Accuracy**: Debe ser > 70% (bueno), > 80% (excelente)
- 📈 **Factores Influyentes**: Verifica que tenga sentido
- 💡 **Sugerencias**: Deben ser accionables

---

## ⚠️ Problemas Comunes

### **Error: "No hay suficientes datos para entrenar"**
- **Causa**: Menos de 20 cotizaciones con respuesta
- **Solución**: Espera a tener más datos históricos

### **Error: "FileNotFoundError: cotizaciones_predictor.pkl"**
- **Causa**: Primera vez usando el dashboard
- **Solución**: El sistema entrenará automáticamente

### **Warning: "Accuracy muy bajo (< 60%)"**
- **Causa**: Pocos datos o patrones inconsistentes
- **Solución**: Acumula más datos y re-entrena

### **Error: "KeyError: 'sucursal_X'"**
- **Causa**: Sucursal nueva no vista en entrenamiento
- **Solución**: Re-entrena el modelo con datos actualizados

---

## 🔒 Seguridad y Privacy

- ✅ Los modelos son **locales** a cada instalación
- ✅ No se envían datos a servicios externos
- ✅ Los `.pkl` no se suben a Git
- ✅ Cada máquina tiene su propio modelo independiente

---

## 📚 Más Información

- **Algoritmo**: Random Forest Classifier (scikit-learn)
- **Implementación**: `servicio_tecnico/ml_predictor.py`
- **Documentación ML**: `docs/implementaciones/dashboard_cotizaciones/`

---

**Última Actualización**: Noviembre 4, 2025
