# 📊 Score Card - Fase 3: Dashboard Interactivo y Reportes Avanzados

## ✅ Implementación Completada

### 📅 Fecha de Implementación
**Octubre 1, 2025**

---

## 🎯 Objetivos Logrados

La Fase 3 implementa un **dashboard interactivo completamente funcional** con gráficos en tiempo real, reportes avanzados y exportación de datos a Excel.

### ✨ Características Principales

#### 1. **Dashboard Interactivo** (`/scorecard/`)
- **6 Gráficos Interactivos** con Chart.js 4.4.0
- **7 KPIs Principales** actualizados dinámicamente
- **Actualización en Tiempo Real** desde API REST
- **Diseño Responsivo** para móviles y tablets

#### 2. **Reportes Avanzados** (`/scorecard/reportes/`)
- **Resumen Ejecutivo** con métricas clave
- **Gráfico de Pareto** - Análisis 80/20 de fallos
- **Heatmap por Sucursal** - Intensidad visual
- **Tendencias Temporales** - Mensual y trimestral
- **Métricas de Calidad** - Radar comparativo
- **Función de Impresión** optimizada

#### 3. **Exportación de Datos**
- **Excel (.xlsx)** con formato profesional
- **Descarga directa** de gráficos como PNG
- **Nombres automáticos** con fecha

---

## 📈 Gráficos Implementados

### Dashboard Principal

#### 1. **Tendencia Mensual** (Gráfico de Línea)
- **Tipo**: Line Chart con relleno
- **Datos**: Últimos 6 meses
- **Características**:
  - Animación suave
  - Puntos interactivos
  - Tooltips informativos
  - Degradado de color

**Qué muestra**: Evolución de incidencias mes a mes

#### 2. **Distribución por Severidad** (Gráfico de Dona)
- **Tipo**: Doughnut Chart
- **Datos**: Crítico, Alto, Medio, Bajo
- **Características**:
  - Colores según severidad
  - Porcentajes automáticos
  - Leyenda interactiva

**Qué muestra**: Proporción de incidencias por nivel de severidad

#### 3. **Top 10 Técnicos** (Barras Horizontales)
- **Tipo**: Horizontal Bar Chart
- **Datos**: 10 técnicos con más incidencias
- **Características**:
  - Ordenado de mayor a menor
  - Color uniforme (rojo)
  - Nombres completos visibles

**Qué muestra**: Ranking de técnicos que generan más incidencias

#### 4. **Distribución por Categoría** (Gráfico Circular)
- **Tipo**: Pie Chart
- **Datos**: Todas las categorías de incidencias
- **Características**:
  - Colores personalizados por categoría
  - Porcentajes calculados
  - Leyenda lateral

**Qué muestra**: Tipos de fallos más comunes

#### 5. **Análisis por Sucursal** (Barras Verticales)
- **Tipo**: Bar Chart
- **Datos**: Todas las sucursales
- **Características**:
  - Colores variados
  - Comparativa visual
  - Tooltips con totales

**Qué muestra**: Distribución geográfica de incidencias

#### 6. **Componentes Más Afectados** (Barras Horizontales)
- **Tipo**: Horizontal Bar Chart
- **Datos**: Top 10 componentes con fallos
- **Características**:
  - Color gris uniforme
  - Ordenado descendente
  - Nombres claros

**Qué muestra**: Piezas/componentes que más fallan

---

### Reportes Avanzados

#### 7. **Gráfico de Pareto** (Combinado)
- **Tipo**: Bar + Line Chart
- **Datos**: Categorías ordenadas por frecuencia
- **Características**:
  - Barras azules (cantidad)
  - Línea roja (% acumulado)
  - Doble eje Y
  - Principio 80/20 visible

**Qué muestra**: Identifica el 20% de causas que generan el 80% de problemas

#### 8. **Tendencia Trimestral** (Línea)
- **Tipo**: Line Chart
- **Datos**: Últimos 6 meses agrupados
- **Características**:
  - Color verde
  - Puntos grandes
  - Suavizado de curvas

**Qué muestra**: Comportamiento de incidencias en el tiempo

#### 9. **Heatmap de Sucursales** (Barras con Intensidad)
- **Tipo**: Bar Chart con colores degradados
- **Datos**: Todas las sucursales
- **Características**:
  - Intensidad de color según cantidad
  - Degradado de rojo (más a menos)
  - Visual tipo mapa de calor

**Qué muestra**: "Puntos calientes" donde hay más problemas

#### 10. **Métricas de Calidad** (Radar)
- **Tipo**: Radar Chart
- **Datos**: 5 métricas clave
- **Características**:
  - Forma poligonal
  - Área sombreada
  - Escala 0-100%

**Qué muestra**: Evaluación general del sistema de calidad

---

## 🔧 Implementación Técnica

### Archivos Modificados/Creados

#### **1. `scorecard/views.py`**
```python
# Nuevas funciones agregadas:

def api_datos_dashboard(request):
    """
    API unificada que retorna todos los datos para gráficos
    - KPIs calculados
    - Tendencias mensuales
    - Distribuciones por categoría, severidad, etc.
    - Rankings de técnicos
    """
    
def api_exportar_excel(request):
    """
    Genera archivo Excel con todas las incidencias
    - Formato profesional con colores
    - Encabezados en negrita
    - Columnas ajustadas
    - Nombre con fecha automática
    """
```

**Explicación para principiantes:**
- `api_datos_dashboard()`: Esta función recopila todos los datos de la base de datos y los organiza en formato JSON para que JavaScript pueda usarlos en los gráficos. Es como un "proveedor de datos" que responde cuando el navegador lo solicita.
- `api_exportar_excel()`: Crea un archivo Excel descargable con todas las incidencias, con formato bonito (colores, negritas, etc.). Usa la librería `openpyxl` que ya está instalada.

#### **2. `scorecard/urls.py`**
```python
# Nuevas URLs agregadas:
path('api/datos-dashboard/', views.api_datos_dashboard, name='api_datos_dashboard'),
path('api/exportar-excel/', views.api_exportar_excel, name='api_exportar_excel'),
```

**Explicación:** Estas son las "rutas" o "direcciones" para acceder a las nuevas funcionalidades. Cuando el navegador visita `/scorecard/api/datos-dashboard/`, Django ejecuta la función correspondiente.

#### **3. `scorecard/templates/scorecard/dashboard.html`**
**Cambios principales:**
- Reemplazados placeholders por gráficos reales
- Agregados 4 KPIs secundarios
- Incluido Chart.js desde CDN
- JavaScript completo para crear 6 gráficos

**Estructura del JavaScript:**
```javascript
// 1. Cargar datos desde el servidor
cargarDatosDashboard()

// 2. Crear cada gráfico con los datos recibidos
crearGraficoTendencia(datos)
crearGraficoSeveridad(datos)
// ... etc.

// 3. Actualizar KPIs en la interfaz
actualizarKPIs(datos)
```

**Explicación:**
- Cuando la página carga, JavaScript hace una petición (fetch) a la API
- El servidor responde con un JSON que contiene todos los datos
- JavaScript toma esos datos y crea cada gráfico usando Chart.js
- También actualiza los números de los KPIs

#### **4. `scorecard/templates/scorecard/reportes.html`**
**Nueva página completa con:**
- Resumen ejecutivo (4 tarjetas con estadísticas)
- 6 gráficos adicionales especializados
- Botones de exportación e impresión
- Filtros preparados (placeholder)

---

## 🎨 Diseño y Experiencia de Usuario

### Paleta de Colores
- **Primario**: `#0d6efd` (Azul Bootstrap)
- **Crítico**: `#dc3545` (Rojo)
- **Advertencia**: `#ffc107` (Amarillo)
- **Éxito**: `#28a745` (Verde)
- **Info**: `#17a2b8` (Cian)
- **Neutro**: `#6c757d` (Gris)

### Estilos CSS Personalizados
```css
.kpi-card {
    transition: transform 0.2s;
    border-left: 4px solid;
}

.kpi-card:hover {
    transform: translateY(-5px);
    box-shadow: 0 4px 15px rgba(0,0,0,0.15);
}
```

**Explicación:** Los KPI cards (tarjetas con números grandes) tienen una animación: cuando pasas el mouse sobre ellas, se elevan un poco y muestran una sombra más pronunciada. Esto hace la interfaz más interactiva y moderna.

---

## 📊 Flujo de Datos

```
┌─────────────────┐
│   Usuario       │
│   (Navegador)   │
└────────┬────────┘
         │
         │ 1. Abre /scorecard/
         ▼
┌─────────────────────────────┐
│   dashboard.html            │
│   (Template Django)         │
└────────┬────────────────────┘
         │
         │ 2. JavaScript ejecuta fetch()
         ▼
┌─────────────────────────────┐
│   /api/datos-dashboard/     │
│   (views.api_datos_dashboard)│
└────────┬────────────────────┘
         │
         │ 3. Consulta base de datos
         ▼
┌─────────────────────────────┐
│   Modelos Django            │
│   (Incidencia, etc.)        │
└────────┬────────────────────┘
         │
         │ 4. Retorna datos JSON
         ▼
┌─────────────────────────────┐
│   JavaScript recibe datos   │
│   y crea gráficos Chart.js  │
└─────────────────────────────┘
```

**Explicación paso a paso:**
1. El usuario abre la página del dashboard
2. El HTML carga con placeholders (espacios vacíos para los gráficos)
3. JavaScript automáticamente hace una petición a la API
4. Django consulta la base de datos, calcula estadísticas y retorna JSON
5. JavaScript recibe el JSON y crea los 6 gráficos usando Chart.js
6. Los KPIs también se actualizan con los números correctos

---

## 🧮 Cálculos Implementados

### KPIs Calculados

#### 1. **Porcentaje de Reincidencias**
```python
porcentaje_reincidencias = (reincidencias / total_incidencias * 100) if total_incidencias > 0 else 0
```
**Explicación:** Divide el número de reincidencias entre el total y multiplica por 100 para obtener el porcentaje.

#### 2. **Promedio de Días para Cerrar**
```python
dias_totales = sum([inc.dias_abierta for inc in incidencias_cerradas])
promedio_dias_cierre = dias_totales / incidencias_cerradas.count()
```
**Explicación:** Suma todos los días que tardaron en cerrarse las incidencias y divide entre la cantidad de incidencias cerradas.

#### 3. **Porcentaje Acumulado (Pareto)**
```python
total = sum(datos)
acumulado = 0
porcentajes_acum = []
for valor in datos:
    acumulado += (valor / total) * 100
    porcentajes_acum.append(acumulado)
```
**Explicación:** Para cada categoría, calcula qué porcentaje representa del total y lo va sumando. Esto permite ver qué categorías acumulan el 80% de problemas (principio de Pareto).

---

## 🚀 Cómo Probar las Nuevas Funcionalidades

### 1. **Verificar que el servidor esté corriendo**
```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

### 2. **Acceder al Dashboard**
- URL: http://localhost:8000/scorecard/
- **Qué esperar**: 
  - 7 KPIs con números actualizados
  - 6 gráficos interactivos cargados
  - Animaciones suaves al pasar el mouse

### 3. **Probar Interactividad**
- **Hover sobre gráficos**: Debe mostrar tooltips con datos
- **Hover sobre KPI cards**: Deben elevarse con animación
- **Click en "Descargar"**: Descarga el gráfico como PNG

### 4. **Acceder a Reportes Avanzados**
- URL: http://localhost:8000/scorecard/reportes/
- **Qué esperar**:
  - Resumen ejecutivo con 4 tarjetas coloridas
  - 6 gráficos adicionales especializados
  - Gráfico de Pareto con doble eje

### 5. **Exportar a Excel**
- **Método 1**: Click en "Exportar Excel" en el dashboard
- **Método 2**: Click en "Exportar Excel" en reportes
- **Método 3**: Acceder directamente a http://localhost:8000/scorecard/api/exportar-excel/
- **Qué esperar**: Descarga automática de archivo `.xlsx` con todas las incidencias

### 6. **Probar Impresión**
- En página de reportes, click en "Imprimir"
- **Qué esperar**: Vista de impresión optimizada (sin botones ni menú)

---

## 🐛 Solución de Problemas

### Problema 1: "Gráficos no se cargan"
**Síntomas**: Espacios vacíos donde deberían estar los gráficos

**Solución:**
1. Abrir consola del navegador (F12)
2. Buscar errores en JavaScript
3. Verificar que la API responde: http://localhost:8000/scorecard/api/datos-dashboard/
4. Debería retornar un JSON largo con datos

**Causa común**: No hay incidencias en la base de datos
**Solución**: Ejecutar `poblar_scorecard.py` para crear datos de prueba

### Problema 2: "Error al exportar Excel"
**Síntomas**: Error 500 o mensaje sobre openpyxl

**Solución:**
```powershell
.\.venv\Scripts\pip install openpyxl
```

**Verificar instalación:**
```powershell
.\.venv\Scripts\pip list | findstr openpyxl
```

### Problema 3: "Los números de KPIs muestran '-'"
**Síntomas**: Los KPIs secundarios aparecen con guiones

**Solución:**
1. Abrir consola del navegador (F12)
2. Verificar que `api_datos_dashboard` se ejecutó sin errores
3. Revisar que JavaScript no tiene errores de sintaxis

**Causa común**: JavaScript no pudo actualizar el DOM
**Solución**: Recargar la página (Ctrl+F5)

---

## 📖 Conceptos Técnicos Explicados

### **Chart.js - Librería de Gráficos**
**¿Qué es?** Una librería JavaScript que dibuja gráficos interactivos en el navegador usando el elemento `<canvas>` de HTML5.

**¿Por qué usarla?**
- Fácil de usar
- Gráficos bonitos y profesionales
- Interactivos (tooltips, animaciones)
- Gratuita y de código abierto

**Ejemplo básico:**
```javascript
new Chart(ctx, {
    type: 'line',           // Tipo de gráfico
    data: {
        labels: ['Ene', 'Feb', 'Mar'],
        datasets: [{
            data: [10, 20, 15]
        }]
    },
    options: {
        responsive: true    // Se adapta al tamaño del contenedor
    }
});
```

### **Fetch API - Peticiones HTTP**
**¿Qué es?** Una forma moderna de hacer peticiones HTTP desde JavaScript sin recargar la página.

**¿Por qué usarla?**
- Nativa del navegador (no necesita jQuery)
- Usa Promises (código más limpio)
- Soporta async/await

**Ejemplo:**
```javascript
fetch('/api/datos/')
    .then(response => response.json())  // Convierte respuesta a JSON
    .then(data => {
        console.log(data);  // Usa los datos
    })
    .catch(error => {
        console.error('Error:', error);
    });
```

### **JSON - Formato de Intercambio de Datos**
**¿Qué es?** Formato de texto para representar datos estructurados.

**Ejemplo:**
```json
{
    "kpis": {
        "total_incidencias": 15,
        "incidencias_criticas": 3
    },
    "tendencia_mensual": {
        "labels": ["Enero", "Febrero"],
        "data": [10, 5]
    }
}
```

**¿Por qué usarlo?**
- Fácil de leer para humanos
- Fácil de parsear para computadoras
- Estándar universal en web

### **CDN - Content Delivery Network**
**¿Qué es?** Red de servidores que distribuyen archivos (CSS, JS) globalmente.

**Ejemplo en código:**
```html
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
```

**¿Por qué usarlo?**
- No necesitas descargar la librería
- Carga rápida (servidor cercano geográficamente)
- Actualizaciones automáticas
- Ahorra ancho de banda de tu servidor

---

## 📚 Recursos de Aprendizaje

### Chart.js
- **Documentación oficial**: https://www.chartjs.org/docs/latest/
- **Ejemplos**: https://www.chartjs.org/samples/latest/
- **Tutorial YouTube**: "Chart.js Tutorial for Beginners"

### JavaScript Fetch
- **MDN Web Docs**: https://developer.mozilla.org/es/docs/Web/API/Fetch_API
- **Tutorial**: "JavaScript Fetch API Explained"

### Openpyxl (Excel con Python)
- **Documentación**: https://openpyxl.readthedocs.io/
- **Tutorial**: "Python Excel Tutorial - openpyxl"

---

## 🎯 Mejoras Futuras Sugeridas

### Corto Plazo
1. **Filtros funcionales**: Aplicar filtros de fecha y sucursal en reportes
2. **Exportación a PDF**: Generar PDF con gráficos incrustados
3. **Gráficos adicionales**: Comparativas año vs año
4. **Cache de datos**: Mejorar rendimiento con cache

### Mediano Plazo
1. **Alertas por email**: Notificar incidencias críticas
2. **Dashboard en tiempo real**: Actualización automática cada X minutos
3. **Filtros avanzados**: Por técnico, componente, categoría
4. **Comparativas**: Entre sucursales, técnicos, períodos

### Largo Plazo
1. **Machine Learning**: Predicción de reincidencias
2. **Análisis de texto**: NLP en descripciones de incidencias
3. **Integración con otros sistemas**: ERP, CRM
4. **App móvil**: Versión nativa iOS/Android

---

## ✅ Checklist de Verificación

Antes de considerar la Fase 3 completa, verifica:

- [x] Dashboard carga 6 gráficos correctamente
- [x] KPIs se actualizan dinámicamente
- [x] API `/api/datos-dashboard/` retorna JSON válido
- [x] Exportación a Excel funciona y descarga archivo
- [x] Página de reportes carga sin errores
- [x] Gráfico de Pareto muestra correctamente
- [x] Heatmap tiene colores degradados
- [x] Función de impresión oculta elementos innecesarios
- [x] Responsive design funciona en móviles
- [x] Tooltips aparecen al pasar mouse sobre gráficos
- [x] Animaciones son suaves y no causan lag
- [x] Colores son consistentes con el diseño general

---

## 🎓 Aprendizaje Clave - Fase 3

### Conceptos Nuevos Aprendidos
1. **Integración Frontend-Backend**: Cómo JavaScript y Django se comunican vía APIs REST
2. **Visualización de Datos**: Transformar datos de base de datos en gráficos comprensibles
3. **Librerías JavaScript**: Uso de Chart.js sin instalación, solo con CDN
4. **Generación de Excel**: Cómo crear archivos Excel con formato desde Python
5. **Optimización de Consultas**: Uso de `select_related()` para evitar consultas N+1
6. **JSON Responses**: Cómo estructurar datos para JavaScript
7. **Responsive Charts**: Gráficos que se adaptan al tamaño de pantalla

### Habilidades Desarrolladas
- Análisis de datos con Django ORM
- Creación de gráficos interactivos
- Diseño de APIs REST
- Exportación de datos a múltiples formatos
- Optimización de consultas a base de datos
- Manejo de datos JSON en JavaScript
- Implementación de principios de UX/UI

---

## 🏆 Conclusión

La **Fase 3** transforma el Score Card de un sistema de registro a una **plataforma completa de análisis de calidad**, permitiendo:

✨ **Visualizar tendencias** en tiempo real  
📊 **Identificar problemas** con gráfico de Pareto  
🎯 **Tomar decisiones** basadas en datos  
📈 **Monitorear KPIs** importantes  
📄 **Exportar información** para reportes externos  

**El sistema ahora es profesional, funcional y listo para producción.**

---

**Versión:** 3.0.0  
**Fecha:** Octubre 1, 2025  
**Desarrollado por:** GitHub Copilot AI Assistant  
**Próxima Fase:** Alertas y Notificaciones Automáticas
