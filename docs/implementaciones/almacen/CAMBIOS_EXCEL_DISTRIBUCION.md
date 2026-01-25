# 📊 ACTUALIZACIÓN: Excel de Distribución Multi-Sucursal

**Fecha**: 24 de enero de 2026  
**Módulo**: Almacén - Dashboard de Distribución Multi-Sucursal  
**Tipo de cambio**: Mejora de funcionalidad - Exportación Excel

---

## 🎯 OBJETIVO

Mantener la **vista web simple** (mostrando solo stock actual) pero generar un **Excel completo y profesional** con análisis histórico detallado de entradas/salidas por sucursal.

---

## ✅ CAMBIOS IMPLEMENTADOS

### 1. Vista Web (SIN CAMBIOS - Queda Simple)

La vista en el navegador sigue mostrando **únicamente el stock actual**:

| Código | Producto | Central | Guadalajara | Monterrey | Satélite | TOTAL |
|--------|----------|:-------:|:-----------:|:---------:|:--------:|:-----:|
| P0021  | RAM 4GB  | **6**   | **4**       | **0**     | **0**    | **10** |

✅ **Beneficios**:
- Fácil de leer
- Enfoque en lo importante (disponibilidad actual)
- Sin confusión con números históricos

---

### 2. Exportación Excel (MEJORADO - 7 Hojas Profesionales)

El archivo Excel descargado ahora incluye **7 hojas especializadas**:

#### 📄 **HOJA 1: Distribución Actual**
- **Contenido**: Stock actual por sucursal (simple y claro)
- **Columnas**: Código | Producto | Categoría | Proveedor | Central | Sucursales... | TOTAL
- **Formato**: 
  - 🔴 Rojo: 0 unidades
  - 🟡 Amarillo: 1-10 unidades
  - 🟢 Verde: 10+ unidades
- **Propósito**: Vista rápida de disponibilidad actual

---

#### 📄 **HOJA 2: Análisis de Movimientos** ⭐ NUEVO

- **Contenido**: Análisis histórico completo de entradas/salidas por sucursal
- **Columnas**: Sucursal | Producto | Entradas | Salidas | Transferencias Netas | Stock Actual
- **Datos**: 
  - **Entradas**: Todos los movimientos de tipo "entrada" desde el inicio
  - **Salidas**: Todos los movimientos de tipo "salida" (servicios técnicos, consumos, etc.)
  - **Transferencias Netas**: Diferencia entre transferencias entrantes y salientes
  - **Stock Actual**: Unidades físicamente disponibles ahora
- **Propósito**: Entender el flujo histórico de inventario y tomar decisiones de compra

**Ejemplo**:
```
Sucursal          | Producto | Entradas | Salidas | Trans. Netas | Stock Actual
Almacén Central   | RAM 4GB  |    10    |    4    |      0       |      6
Guadalajara       | RAM 4GB  |     4    |    0    |     +4       |      4
```

---

#### 📄 **HOJA 3: Historial de Transferencias** ⭐ NUEVO

- **Contenido**: Registro completo de todas las transferencias entre sucursales
- **Columnas**: Fecha | Producto | Cantidad | Origen | Destino | Solicitante | Estado
- **Datos**: Todas las transferencias desde el inicio del sistema
- **Estados con color**:
  - 🟢 Verde: Aprobado
  - 🔴 Rojo: Rechazado
  - 🟡 Amarillo: Pendiente
- **Propósito**: Trazabilidad completa de movimientos entre ubicaciones

**Ejemplo**:
```
Fecha           | Producto | Cant. | Origen          | Destino      | Solicitante | Estado
24/01/2026 14:30| RAM 4GB  |   4   | Almacén Central | Guadalajara  | Juan Pérez  | ✅ Aprobado
```

---

#### 📄 **HOJA 4: Resumen por Sucursal**

- **Contenido**: Estadísticas y porcentajes por ubicación
- **Columnas**: Sucursal | Total Unidades | Productos Diferentes | % del Total
- **Propósito**: Vista macro de la distribución del inventario

---

#### 📄 **HOJA 5: Productos Sin Stock**

- **Contenido**: Lista de productos agotados en todas las ubicaciones
- **Columnas**: Código | Producto | Categoría | Proveedor | Días sin Movimiento
- **Propósito**: Identificar qué productos necesitan reposición urgente

---

#### 📄 **HOJA 6: Movimientos Recientes**

- **Contenido**: Últimos 30 días de actividad en el almacén
- **Columnas**: Fecha | Producto | Tipo | Cantidad | Empleado | Observaciones
- **Tipos**: Entrada, Salida, Transferencia
- **Propósito**: Monitoreo de actividad reciente

---

#### 📄 **HOJA 7: Alertas de Reposición**

- **Contenido**: Productos con stock crítico (1-10 unidades)
- **Columnas**: Código | Producto | Stock Actual | Stock Mínimo | Proveedor | Costo Unit.
- **Formato**: Celdas amarillas para stock bajo
- **Propósito**: Lista de compras sugeridas

---

## 🔍 LÓGICA DE CÁLCULO (Hoja 2 - Análisis de Movimientos)

### Para Almacén Central:

```python
# Entradas: Todos los MovimientoAlmacen de tipo 'entrada'
entradas_central = MovimientoAlmacen.objects.filter(
    producto=producto,
    tipo='entrada'
).aggregate(Sum('cantidad'))

# Salidas: Todos los MovimientoAlmacen de tipo 'salida'
salidas_central = MovimientoAlmacen.objects.filter(
    producto=producto,
    tipo='salida'
).aggregate(Sum('cantidad'))

# Transferencias Salientes: SolicitudBaja aprobadas desde Central
transferencias_salientes = SolicitudBaja.objects.filter(
    producto=producto,
    tipo_solicitud='transferencia',
    estado='aprobado',
    producto__sucursal__isnull=True  # Origen: Central
).aggregate(Sum('cantidad'))

# Transferencias Entrantes: SolicitudBaja aprobadas hacia Central
transferencias_entrantes = SolicitudBaja.objects.filter(
    producto=producto,
    tipo_solicitud='transferencia',
    estado='aprobado',
    sucursal_destino__isnull=True  # Destino: Central
).aggregate(Sum('cantidad'))
```

### Para Sucursales:

```python
# Entradas: Transferencias aprobadas HACIA esta sucursal
entradas_suc = SolicitudBaja.objects.filter(
    producto=producto,
    tipo_solicitud='transferencia',
    estado='aprobado',
    sucursal_destino=sucursal
).aggregate(Sum('cantidad'))

# Salidas: Transferencias aprobadas DESDE esta sucursal
salidas_suc = SolicitudBaja.objects.filter(
    producto=producto,
    tipo_solicitud='transferencia',
    estado='aprobado',
    producto__sucursal=sucursal
).aggregate(Sum('cantidad'))
```

---

## 📁 ARCHIVOS MODIFICADOS

| Archivo | Líneas Modificadas | Descripción |
|---------|-------------------|-------------|
| `almacen/views.py` | ~4245-4680 | Función `exportar_distribucion_excel()` reescrita |

**Total de líneas agregadas**: ~435 líneas de código nuevo

---

## 🎨 FORMATO PROFESIONAL DEL EXCEL

### Colores Utilizados:

- **Encabezados**: Azul oscuro (#366092) con texto blanco
- **Subencabezados**: Azul claro (#B4C7E7)
- **Stock cero**: Rojo (#FF6B6B) con texto blanco
- **Stock bajo (1-10)**: Amarillo (#FFD93D)
- **Stock normal (10+)**: Verde (#6BCF7F) con texto blanco
- **Totales**: Naranja (#FFC000)

### Características:

- ✅ Bordes en todas las celdas
- ✅ Alineación centrada para números
- ✅ Anchos de columna ajustados automáticamente
- ✅ Celdas fusionadas para títulos
- ✅ Formato de fecha: DD/MM/YYYY HH:MM
- ✅ Formato de moneda: $X.XX
- ✅ Notas explicativas al final de cada hoja

---

## 🚀 CÓMO USAR

### 1. Acceder al Dashboard

```
http://localhost:8000/almacen/dashboard/distribucion-sucursales/
```

### 2. Exportar Excel

Hacer clic en el botón **"Exportar Excel"** en la parte superior derecha del dashboard.

### 3. Archivo Descargado

```
Distribucion_Multi_Sucursal_YYYYMMDD_HHMMSS.xlsx
```

Ejemplo: `Distribucion_Multi_Sucursal_20260124_143045.xlsx`

### 4. Abrir en Excel/LibreOffice

El archivo se puede abrir en:
- Microsoft Excel 2010+
- LibreOffice Calc
- Google Sheets (subir archivo)
- WPS Office

---

## 📊 CASOS DE USO

### Caso 1: Planificar Compras

1. Abrir **Hoja 2 (Análisis de Movimientos)**
2. Buscar productos con muchas salidas y pocas entradas
3. Ir a **Hoja 7 (Alertas de Reposición)** para ver costos
4. Generar orden de compra

### Caso 2: Auditar Transferencias

1. Abrir **Hoja 3 (Historial de Transferencias)**
2. Filtrar por fecha/producto/sucursal
3. Verificar que todas las transferencias estén aprobadas
4. Cruzar con inventario físico

### Caso 3: Distribuir Inventario

1. Abrir **Hoja 1 (Distribución Actual)**
2. Identificar desbalances (mucho en una sucursal, poco en otra)
3. Crear solicitudes de transferencia en el sistema
4. Exportar nuevamente para verificar

### Caso 4: Reportes Gerenciales

1. Abrir **Hoja 4 (Resumen por Sucursal)**
2. Ver porcentajes de distribución
3. Analizar eficiencia de cada ubicación
4. Tomar decisiones estratégicas

---

## 🔄 COMPATIBILIDAD CON DATOS EXISTENTES

El sistema es **100% compatible** con los datos actuales:

- ✅ Funciona con productos que tienen unidades disponibles
- ✅ Funciona con productos sin stock
- ✅ Maneja correctamente transferencias históricas
- ✅ Procesa movimientos de entrada/salida existentes
- ✅ Soporta filtros de búsqueda aplicados en la vista web

Si no hay datos históricos:
- Hoja 2 mostrará entradas/salidas en 0 (stock actual solo)
- Hoja 3 mostrará mensaje "No hay transferencias registradas"
- Hoja 6 mostrará mensaje "No hay movimientos en los últimos 30 días"

---

## 🎯 BENEFICIOS DE LA IMPLEMENTACIÓN

### Para el Usuario Final:

✅ **Vista web simple** - No se confunde con números históricos  
✅ **Excel completo** - Tiene todo el análisis cuando lo necesita  
✅ **Trazabilidad** - Puede rastrear cada movimiento  
✅ **Toma de decisiones** - Datos históricos para planificar compras  

### Para el Negocio:

✅ **Reducción de costos** - Mejor planificación de compras  
✅ **Optimización de inventario** - Distribución balanceada entre sucursales  
✅ **Auditoría** - Historial completo para revisiones  
✅ **Reportes profesionales** - Excel listo para presentar a gerencia  

### Para el Sistema:

✅ **Sin cambios en la BD** - Usa datos existentes  
✅ **Performance** - Optimizado con `select_related()` y `prefetch_related()`  
✅ **Mantenible** - Código bien documentado con comentarios en español  
✅ **Escalable** - Funciona con 10 o 10,000 productos  

---

## 📝 NOTAS TÉCNICAS

### Rendimiento:

- **Query optimization**: Se usan `aggregate(Sum())` en lugar de loops
- **Prefetch**: `select_related()` y `prefetch_related()` para reducir queries
- **Límites**: Hoja 6 limitada a 100 movimientos recientes para evitar archivos gigantes

### Mantenimiento:

- **Código documentado**: Cada sección tiene comentarios explicativos
- **Formato consistente**: Mismos estilos en todas las hojas
- **Extensible**: Fácil agregar más hojas o columnas

### Consideraciones:

- ⚠️ El Excel puede tardar ~5-10 segundos en generarse con muchos productos
- ⚠️ Los datos históricos dependen de que `MovimientoAlmacen` esté correctamente registrado
- ⚠️ Las transferencias solo se cuentan si están con `estado='aprobado'`

---

## ✨ PRÓXIMAS MEJORAS POSIBLES (Futuro)

1. **Filtro de fechas en el Excel**: Permitir seleccionar rango de fechas para análisis
2. **Gráficos en Excel**: Agregar gráficos de tendencias usando `openpyxl.chart`
3. **Comparativa mensual**: Hoja adicional con comparación mes a mes
4. **Predicción de demanda**: Usar datos históricos para predecir necesidades
5. **Export PDF**: Versión PDF del reporte para impresión
6. **Programar exportaciones**: Generar Excel automáticamente cada mes

---

## 🆘 SOLUCIÓN DE PROBLEMAS

### Problema: Excel se descarga vacío

**Solución**: Verificar que hay productos con `activo=True` en la base de datos

### Problema: Hoja 2 muestra todos ceros en Entradas/Salidas

**Causa**: No hay movimientos registrados en `MovimientoAlmacen`  
**Solución**: Normal si es sistema nuevo. Los movimientos se registrarán automáticamente con futuras operaciones.

### Problema: Hoja 3 dice "No hay transferencias"

**Causa**: No se han creado solicitudes de transferencia o ninguna está aprobada  
**Solución**: Normal. Esta hoja se llenará conforme se usen las transferencias entre sucursales.

### Problema: Error al abrir el Excel

**Causa**: Archivo corrupto o versión de Excel muy antigua  
**Solución**: Usar Excel 2010+ o LibreOffice Calc

---

**Desarrollado**: Enero 2026  
**Versión**: 1.0  
**Módulo**: Almacén - Sistema SIGMA  
**Tecnología**: Django 5.2.5 + openpyxl 3.1.2
