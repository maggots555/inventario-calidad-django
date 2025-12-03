# ALMACÉN - Funcionalidades Pendientes de Implementar

**Contexto**: Módulo Almacén creado en Diciembre 2025. Modelos y formularios completos, faltan vistas/templates/URLs.

---

## 📊 RESUMEN RÁPIDO

| Modelo | Forms | URLs | Views | Templates | Estado |
|--------|-------|------|-------|-----------|--------|
| Proveedor | ✅ ProveedorForm | ✅ CRUD | ✅ | ✅ | **COMPLETO** |
| CategoriaAlmacen | ✅ CategoriaAlmacenForm | ✅ CRUD | ✅ | ✅ | **COMPLETO** |
| ProductoAlmacen | ✅ ProductoAlmacenForm | ✅ CRUD | ✅ | ✅ | **COMPLETO** |
| CompraProducto | ✅ CompraProductoForm | ❌ | ❌ | ❌ | **PENDIENTE** |
| MovimientoAlmacen | ✅ MovimientoAlmacenForm | ⚠️ Solo lista/entrada | ⚠️ | ⚠️ | **PARCIAL** |
| SolicitudBaja | ✅ SolicitudBajaForm | ✅ CRUD | ✅ | ✅ | **COMPLETO** |
| Auditoria | ✅ AuditoriaForm | ❌ | ❌ | ❌ | **PENDIENTE** |
| DiferenciaAuditoria | ✅ DiferenciaAuditoriaForm | ❌ | ❌ | ❌ | **PENDIENTE** |
| UnidadInventario | ✅ UnidadInventarioForm | ✅ CRUD | ✅ | ✅ | **COMPLETO** |

---

## 1️⃣ COMPRAS DE PRODUCTO (CompraProducto)

### Modelo: `almacen/models.py` línea 540
- ForeignKey: producto, proveedor, orden_servicio
- Campos: cantidad, costo_unitario, costo_total (auto), fecha_pedido, fecha_recepcion
- Método save(): calcula costo_total, dias_entrega, actualiza costo_unitario del producto

### Formulario: `almacen/forms.py` línea 325 - `CompraProductoForm`
- Ya creado con todos los campos y widgets Bootstrap

### URLs a crear:
```python
# En almacen/urls.py agregar:
path('compras/', views.lista_compras, name='lista_compras'),
path('compras/crear/', views.crear_compra, name='crear_compra'),
path('compras/<int:pk>/', views.detalle_compra, name='detalle_compra'),
path('compras/<int:pk>/editar/', views.editar_compra, name='editar_compra'),
# Opcional: recibir compra (actualiza fecha_recepcion y crea MovimientoAlmacen entrada)
path('compras/<int:pk>/recibir/', views.recibir_compra, name='recibir_compra'),
```

### Vistas a crear:
```python
# lista_compras: filtros por producto, proveedor, fecha, estado (pendiente/recibida)
# crear_compra: formulario, al guardar NO actualiza stock (se hace al recibir)
# detalle_compra: mostrar info, historial de producto, tiempo entrega
# editar_compra: solo si no ha sido recibida
# recibir_compra: marca fecha_recepcion, crea MovimientoAlmacen tipo='entrada'
```

### Templates a crear:
```
almacen/templates/almacen/compras/
├── lista_compras.html      # Tabla con filtros, estado pendiente/recibida
├── form_compra.html        # Crear/editar compra
├── detalle_compra.html     # Info completa + botón recibir si pendiente
```

### Lógica importante:
1. Al CREAR compra: solo registra, NO modifica stock
2. Al RECIBIR compra:
   - Actualiza fecha_recepcion = hoy
   - Calcula dias_entrega
   - Crea MovimientoAlmacen(tipo='entrada', cantidad, producto)
   - El signal de MovimientoAlmacen actualiza stock_actual del producto

---

## 2️⃣ AUDITORÍAS (Auditoria + DiferenciaAuditoria)

### Modelo Auditoria: `almacen/models.py` línea 1074
- Campos: tipo (completa/ciclica/diferencias/abc), estado, sucursal, auditor
- Métodos: actualizar_totales(), finalizar()
- Related: diferencias (DiferenciaAuditoria)

### Modelo DiferenciaAuditoria: `almacen/models.py` línea 1188
- ForeignKey: auditoria, producto
- Campos: stock_sistema, stock_fisico, diferencia (auto), razon, evidencia (imagen)
- Método: aplicar_ajuste(responsable, acciones) - actualiza stock real

### Formularios existentes:
- `AuditoriaForm` línea 654
- `DiferenciaAuditoriaForm` línea 694

### URLs a crear:
```python
# AUDITORÍAS
path('auditorias/', views.lista_auditorias, name='lista_auditorias'),
path('auditorias/crear/', views.crear_auditoria, name='crear_auditoria'),
path('auditorias/<int:pk>/', views.detalle_auditoria, name='detalle_auditoria'),
path('auditorias/<int:pk>/finalizar/', views.finalizar_auditoria, name='finalizar_auditoria'),

# DIFERENCIAS (dentro de una auditoría)
path('auditorias/<int:auditoria_pk>/diferencia/crear/', views.crear_diferencia, name='crear_diferencia'),
path('auditorias/<int:auditoria_pk>/diferencia/<int:pk>/ajustar/', views.ajustar_diferencia, name='ajustar_diferencia'),
```

### Vistas a crear:
```python
# lista_auditorias: filtros por estado, tipo, fecha, auditor
# crear_auditoria: seleccionar tipo, sucursal, asignar auditor
# detalle_auditoria: 
#   - Info general + lista de diferencias
#   - Botones: agregar diferencia, finalizar auditoría
#   - Si tiene diferencias sin ajustar, mostrar alerta
# finalizar_auditoria: marca estado completada/con_diferencias
# crear_diferencia:
#   - Seleccionar producto
#   - Mostrar stock_sistema actual (readonly)
#   - Ingresar stock_fisico (conteo real)
#   - diferencia se calcula automáticamente
#   - Seleccionar razon, subir evidencia opcional
# ajustar_diferencia:
#   - Aplica método aplicar_ajuste()
#   - Actualiza stock del producto al valor físico
#   - Registra responsable y acciones correctivas
```

### Templates a crear:
```
almacen/templates/almacen/auditorias/
├── lista_auditorias.html       # Tabla con estados, filtros
├── form_auditoria.html         # Crear auditoría
├── detalle_auditoria.html      # Info + tabla diferencias + botones
├── form_diferencia.html        # Registrar diferencia encontrada
├── ajustar_diferencia.html     # Confirmar ajuste de stock
```

### Flujo completo:
1. Crear auditoría → estado='en_proceso'
2. Auditor cuenta físicamente productos
3. Por cada diferencia: crear DiferenciaAuditoria
4. Supervisor revisa y aplica ajustes (opcional)
5. Finalizar auditoría → estado='completada' o 'con_diferencias'

---

## 3️⃣ MOVIMIENTOS - Mejoras pendientes

### Actualmente implementado:
- ✅ lista_movimientos (filtros básicos)
- ✅ registrar_entrada (formulario manual)
- ✅ Signals para actualizar stock automáticamente

### Faltante:
```python
# URLs adicionales:
path('movimientos/<int:pk>/', views.detalle_movimiento, name='detalle_movimiento'),
path('movimientos/salida/', views.registrar_salida_manual, name='registrar_salida'),
```

### Vistas a crear:
```python
# detalle_movimiento: info completa, trazabilidad (qué lo generó: compra, solicitud, etc)
# registrar_salida_manual: para salidas no vinculadas a solicitud (ajustes, mermas)
```

### Templates:
```
almacen/templates/almacen/movimientos/
├── detalle_movimiento.html     # NUEVO: info completa
├── form_salida.html            # NUEVO: salida manual
```

---

## 4️⃣ FORMULARIOS AUXILIARES EXISTENTES (no usados aún)

### BusquedaProductoForm (línea 748)
- Para búsqueda avanzada de productos
- Campos: codigo, nombre, categoria, tipo, estado_stock, proveedor
- **Uso**: Mejorar filtros en lista_productos

### EntradaRapidaForm (línea 799)
- Entrada rápida sin crear compra formal
- Campos: producto (autocomplete), cantidad, costo_unitario, observaciones
- **Uso**: Vista rápida para entradas sin todo el proceso de compra

---

## 5️⃣ FUNCIONALIDADES ADICIONALES SUGERIDAS

### Dashboard - Mejorar con:
- Gráfico de movimientos (entradas vs salidas por mes)
- Top 10 productos más solicitados
- Alertas de productos sin movimiento (estancados)
- Valor total del inventario

### Reportes (nuevos):
```python
path('reportes/inventario/', views.reporte_inventario, name='reporte_inventario'),
path('reportes/movimientos/', views.reporte_movimientos, name='reporte_movimientos'),
path('reportes/valorizado/', views.reporte_valorizado, name='reporte_valorizado'),
```

### Exportación Excel:
- Lista de productos con stock
- Historial de movimientos
- Reporte de auditorías

---

## 📋 ORDEN DE IMPLEMENTACIÓN SUGERIDO

### Prioridad 1 (Core):
1. **Compras** - Necesario para entrada formal de productos
2. **Auditorías** - Control de inventario

### Prioridad 2 (Mejoras):
3. **Detalle de movimiento**
4. **Salida manual**
5. **Búsqueda avanzada de productos**

### Prioridad 3 (Nice to have):
6. Reportes y exportación Excel
7. Gráficos en dashboard
8. Entrada rápida

---

## 🔧 ARCHIVOS A MODIFICAR

### Para cada funcionalidad:
1. `almacen/urls.py` - Agregar paths
2. `almacen/views.py` - Crear vistas
3. `almacen/templates/almacen/` - Crear templates
4. `almacen/templates/almacen/base_almacen.html` - Agregar enlaces en navbar si es sección nueva

### Navbar actual tiene:
- Dashboard, Productos, Proveedores, Categorías, Movimientos, Solicitudes, Unidades
- **Agregar**: Compras, Auditorías

---

## 📝 NOTAS TÉCNICAS

### Signals existentes (`almacen/models.py`):
- MovimientoAlmacen post_save → actualiza stock_actual del producto
- Ya funciona automáticamente para entradas/salidas

### Métodos de modelo útiles:
- `CompraProducto.save()`: calcula totales automáticamente
- `Auditoria.finalizar()`: cierra auditoría
- `DiferenciaAuditoria.aplicar_ajuste()`: actualiza stock real
- `SolicitudBaja.aprobar()`: ya actualiza UnidadInventario.disponibilidad

### Select_related a usar:
```python
# Compras
CompraProducto.objects.select_related('producto', 'proveedor', 'orden_servicio')

# Auditorías
Auditoria.objects.select_related('sucursal', 'auditor')
DiferenciaAuditoria.objects.select_related('auditoria', 'producto', 'responsable_ajuste')
```

---

**Última actualización**: Diciembre 2025
**Estado**: Documento de referencia para implementación futura
