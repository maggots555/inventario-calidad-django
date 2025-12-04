# ALMACÉN - Funcionalidades Pendientes de Implementar

**Contexto**: Módulo Almacén creado en Diciembre 2025. Modelos y formularios completos.

---

## 📊 RESUMEN RÁPIDO

| Modelo | Forms | URLs | Views | Templates | Estado |
|--------|-------|------|-------|-----------|--------|
| Proveedor | ✅ ProveedorForm | ✅ CRUD | ✅ | ✅ | **COMPLETO** |
| CategoriaAlmacen | ✅ CategoriaAlmacenForm | ✅ CRUD | ✅ | ✅ | **COMPLETO** |
| ProductoAlmacen | ✅ ProductoAlmacenForm | ✅ CRUD | ✅ | ✅ | **COMPLETO** |
| CompraProducto | ✅ CompraProductoForm | ✅ CRUD + Workflow | ✅ | ✅ | **✅ COMPLETO** |
| UnidadCompra | ✅ UnidadCompraForm | ✅ Integrado | ✅ | ✅ | **✅ COMPLETO** |
| MovimientoAlmacen | ✅ MovimientoAlmacenForm | ⚠️ Solo lista/entrada | ⚠️ | ⚠️ | **PARCIAL** |
| SolicitudBaja | ✅ SolicitudBajaForm | ✅ CRUD | ✅ | ✅ | **COMPLETO** |
| Auditoria | ✅ AuditoriaForm | ❌ | ❌ | ❌ | **PENDIENTE** |
| DiferenciaAuditoria | ✅ DiferenciaAuditoriaForm | ❌ | ❌ | ❌ | **PENDIENTE** |
| UnidadInventario | ✅ UnidadInventarioForm | ✅ CRUD | ✅ | ✅ | **COMPLETO** |

---

## ✅ IMPLEMENTADO: COMPRAS Y COTIZACIONES (Diciembre 2025)

### Modelo CompraProducto - MEJORADO
**Ubicación**: `almacen/models.py`

**Nuevos campos agregados**:
- `tipo`: 'cotizacion' o 'compra' (diferencia cotización de compra formal)
- `estado`: Workflow completo con 10 estados:
  - `pendiente_aprobacion` → `aprobada` → `pendiente_llegada` → `recibida`
  - Estados de problema: `wpb` (Wrong Part), `doa` (Dead On Arrival)
  - Estados de devolución: `devolucion_garantia` → `devuelta`
  - `rechazada`, `cancelada`
- `orden_cliente`: Búsqueda por número visible al cliente (ej: OS-2024-0001)
- `fecha_aprobacion`, `fecha_rechazo`, `fecha_problema`, `fecha_devolucion`
- `motivo_problema`, `motivo_rechazo`

**Métodos de workflow**:
- `aprobar()`: Convierte cotización en compra pendiente
- `rechazar(motivo)`: Rechaza cotización con motivo
- `recibir(fecha)`: Marca como recibida
- `marcar_wpb(motivo)`: Marca pieza incorrecta
- `marcar_doa(motivo)`: Marca pieza dañada
- `iniciar_devolucion()`: Inicia proceso de devolución
- `confirmar_devolucion()`: Confirma devolución y descuenta stock
- `cancelar(motivo)`: Cancela compra/cotización

### Modelo UnidadCompra - NUEVO
**Ubicación**: `almacen/models.py`

Permite definir especificaciones individuales por pieza en una compra:
- `compra`: FK a CompraProducto
- `numero_linea`: Secuencial dentro de la compra
- `marca`, `modelo`, `numero_serie`, `especificaciones`
- `costo_unitario`: Costo específico si difiere del general
- `estado`: pendiente, recibida, wpb, doa, devolucion, devuelta
- `unidad_inventario`: OneToOne a UnidadInventario creada al recibir

**Métodos**:
- `recibir()`: Crea UnidadInventario automáticamente
- `marcar_wpb()`, `marcar_doa()`, `iniciar_devolucion()`, `confirmar_devolucion()`

### Constantes agregadas
**Ubicación**: `config/constants.py`

```python
TIPO_COMPRA_CHOICES = [('cotizacion', 'Cotización'), ('compra', 'Compra Formal')]
ESTADO_COMPRA_CHOICES = [10 estados del workflow]
ESTADO_UNIDAD_COMPRA_CHOICES = [6 estados por unidad]
```

### Formularios
**Ubicación**: `almacen/forms.py`

- `CompraProductoForm`: Actualizado con nuevos campos
- `UnidadCompraForm`: Para detalles de cada pieza
- `UnidadCompraFormSet`: Formset inline para múltiples unidades
- `RecepcionCompraForm`: Confirmar recepción
- `ProblemaCompraForm`: Reportar WPB/DOA
- `RechazoCotizacionForm`: Rechazar cotización
- `DevolucionCompraForm`: Confirmar devolución

### URLs implementadas
**Ubicación**: `almacen/urls.py`

```python
# CRUD
path('compras/', views.lista_compras, name='lista_compras'),
path('cotizaciones/', views.panel_cotizaciones, name='panel_cotizaciones'),
path('compras/crear/', views.crear_compra, name='crear_compra'),
path('compras/<int:pk>/', views.detalle_compra, name='detalle_compra'),
path('compras/<int:pk>/editar/', views.editar_compra, name='editar_compra'),

# Workflow cotizaciones
path('compras/<int:pk>/aprobar/', views.aprobar_cotizacion, name='aprobar_cotizacion'),
path('compras/<int:pk>/rechazar/', views.rechazar_cotizacion, name='rechazar_cotizacion'),

# Workflow compras
path('compras/<int:pk>/recibir/', views.recibir_compra, name='recibir_compra'),
path('compras/<int:pk>/problema/', views.reportar_problema_compra, name='reportar_problema'),
path('compras/<int:pk>/devolucion/', views.iniciar_devolucion, name='iniciar_devolucion'),
path('compras/<int:pk>/confirmar-devolucion/', views.confirmar_devolucion, name='confirmar_devolucion'),
path('compras/<int:pk>/cancelar/', views.cancelar_compra, name='cancelar_compra'),

# Unidades individuales
path('compras/<int:compra_pk>/unidad/<int:pk>/recibir/', views.recibir_unidad_compra, name='recibir_unidad'),
path('compras/<int:compra_pk>/unidad/<int:pk>/problema/', views.problema_unidad_compra, name='problema_unidad'),
```

### Templates creados
**Ubicación**: `almacen/templates/almacen/compras/`

- `lista_compras.html`: Tabla con filtros por tipo, estado, producto, proveedor
- `panel_cotizaciones.html`: Dashboard de cotizaciones pendientes con estadísticas
- `form_compra.html`: Crear/editar con formset dinámico para unidades
- `detalle_compra.html`: Info completa + botones de acción según estado
- `recibir_compra.html`: Confirmar recepción
- `rechazar_cotizacion.html`: Formulario de rechazo
- `problema_compra.html`: Reportar WPB/DOA
- `confirmar_devolucion.html`: Confirmar devolución completada

### Navbar actualizado
**Ubicación**: `almacen/templates/almacen/base_almacen.html`

Agregada nueva columna "Compras y Cotizaciones":
- Lista de Compras
- Panel Cotizaciones
- Nueva Compra/Cotización

---

## 🔧 AJUSTES PENDIENTES EN COMPRAS (Mejoras Menores)

1. **Formset dinámico en frontend**: Agregar botón "Agregar otra unidad" con JavaScript
2. **Validación de cantidad vs unidades**: Verificar que unidades_compra.count() <= cantidad
3. **Filtro avanzado en lista_compras**: Agregar filtro por rango de fechas
4. **Exportar a Excel**: Lista de compras/cotizaciones
5. **Notificaciones**: Alertas para cotizaciones con muchos días sin respuesta

---

## 1️⃣ AUDITORÍAS (Auditoria + DiferenciaAuditoria) - PENDIENTE

### Modelo Auditoria: `almacen/models.py`
- Campos: tipo (completa/ciclica/diferencias/abc), estado, sucursal, auditor
- Métodos: actualizar_totales(), finalizar()
- Related: diferencias (DiferenciaAuditoria)

### Modelo DiferenciaAuditoria: `almacen/models.py`
- ForeignKey: auditoria, producto
- Campos: stock_sistema, stock_fisico, diferencia (auto), razon, evidencia (imagen)
- Método: aplicar_ajuste(responsable, acciones) - actualiza stock real

### Formularios existentes:
- `AuditoriaForm`
- `DiferenciaAuditoriaForm`

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

## 2️⃣ MOVIMIENTOS - Mejoras pendientes

### Actualmente implementado:
- ✅ lista_movimientos (filtros básicos)
- ✅ registrar_entrada (formulario manual)
- ✅ Stock se actualiza automáticamente en save()

### Faltante:
```python
# URLs adicionales:
path('movimientos/<int:pk>/', views.detalle_movimiento, name='detalle_movimiento'),
path('movimientos/salida/', views.registrar_salida_manual, name='registrar_salida'),
```

### Templates:
```
almacen/templates/almacen/movimientos/
├── detalle_movimiento.html     # NUEVO: info completa
├── form_salida.html            # NUEVO: salida manual
```

---

## 3️⃣ FUNCIONALIDADES ADICIONALES SUGERIDAS

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

### ✅ Completado:
1. **Compras y Cotizaciones** - Sistema completo con workflow

### Prioridad 1 (Siguiente):
2. **Auditorías** - Control de inventario físico vs sistema

### Prioridad 2 (Mejoras):
3. **Detalle de movimiento**
4. **Salida manual**
5. **Ajustes menores en Compras** (formset dinámico, etc.)

### Prioridad 3 (Nice to have):
6. Reportes y exportación Excel
7. Gráficos en dashboard
8. Notificaciones automáticas

---

## 📝 NOTAS TÉCNICAS

### Migraciones aplicadas:
- `0004_compraproducto_estado_compraproducto_...` - Nuevos campos en CompraProducto
- `0005_unidadcompra` - Modelo para tracking individual de unidades

### Métodos de modelo útiles:
- `CompraProducto.aprobar()`, `.rechazar()`, `.recibir()`, `.marcar_wpb()`, `.marcar_doa()`
- `UnidadCompra.recibir()` - Crea UnidadInventario automáticamente
- `Auditoria.finalizar()`: cierra auditoría
- `DiferenciaAuditoria.aplicar_ajuste()`: actualiza stock real

### Select_related a usar:
```python
# Compras
CompraProducto.objects.select_related('producto', 'proveedor', 'orden_servicio').prefetch_related('unidades_compra')

# Auditorías
Auditoria.objects.select_related('sucursal', 'auditor')
DiferenciaAuditoria.objects.select_related('auditoria', 'producto', 'responsable_ajuste')
```

---

**Última actualización**: Diciembre 2025
**Estado**: Compras ✅ completado | Auditorías pendiente
