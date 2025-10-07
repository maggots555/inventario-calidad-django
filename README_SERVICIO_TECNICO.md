# 📋 Sistema de Gestión de Órdenes de Servicio Técnico

## 🎯 Descripción General

Sistema completo para gestionar el ciclo de vida de reparación de equipos de cómputo (PC, Laptops, All-in-One). Integrado con el sistema de inventario y ScoreCard de calidad.

**Versión:** FASE 1 - Modelos y Administración Base  
**Fecha:** Octubre 2025  
**Estado:** ✅ Funcional - Listo para uso en Admin de Django

---

## 📊 Arquitectura de Modelos

### Diagrama de Relaciones

```
OrdenServicio (Central)
├── DetalleEquipo (1:1)
│   └── ReferenciaGamaEquipo (Lookup)
├── Cotizacion (1:1)
│   ├── PiezaCotizada (1:N)
│   │   └── ComponenteEquipo (ScoreCard)
│   └── SeguimientoPieza (1:N)
├── VentaMostrador (1:1)
├── ImagenOrden (1:N)
├── HistorialOrden (1:N)
├── Sucursal (FK - Inventario)
├── Empleado (FK × 2 - Inventario)
└── Incidencia (FK - ScoreCard si es reingreso)
```

---

## 🗄️ Modelos Detallados

### 1️⃣ **OrdenServicio** - Modelo Central

**Propósito:** Gestiona el ciclo completo de una orden de servicio.

**Campos Principales:**
- `numero_orden_interno`: Auto-generado (ORD-2025-0001)
- `sucursal`: Sucursal donde se registra
- `responsable_seguimiento`: Empleado a cargo del seguimiento
- `tecnico_asignado_actual`: Técnico actual (puede cambiar)
- `estado`: Estado actual del workflow (11 estados posibles)
- `es_reingreso`: Marca si es un equipo que regresa
- `orden_original`: Referencia a orden anterior si es reingreso
- `incidencia_scorecard`: Incidencia creada automáticamente si es reingreso
- `es_candidato_rhitso`: Marca para reparación especializada
- `requiere_factura`: Control de facturación

**Estados del Workflow:**
1. `espera` - En Espera
2. `recepcion` - En Recepción  
3. `diagnostico` - En Diagnóstico
4. `cotizacion` - Esperando Aprobación Cliente
5. `rechazada` - Cotización Rechazada
6. `esperando_piezas` - Esperando Llegada de Piezas
7. `reparacion` - En Reparación
8. `control_calidad` - Control de Calidad
9. `finalizado` - Finalizado - Listo para Entrega
10. `entregado` - Entregado al Cliente
11. `cancelado` - Cancelado

**Propiedades Calculadas:**
- `dias_en_servicio`: Días desde ingreso hasta entrega/actual
- `esta_retrasada`: True si lleva >15 días sin entregar

**Métodos Importantes:**
- `crear_incidencia_reingreso()`: Crea automáticamente incidencia en ScoreCard

**Comportamiento Automático:**
- Genera número de orden automático al crear
- Registra eventos en historial al cambiar estado o técnico
- Calcula campos de fecha (año, mes, semana) para reportes

---

### 2️⃣ **DetalleEquipo** - Información del Equipo

**Propósito:** Almacena toda la información técnica del equipo en servicio.

**Relación:** OneToOne con OrdenServicio

**Campos Principales:**
- `tipo_equipo`: PC/Laptop/AIO
- `marca` y `modelo`: Identificación del equipo
- `numero_serie`: Service Tag único
- `gama`: Alta/Media/Baja (calculada automáticamente)
- `tiene_cargador` y `numero_serie_cargador`: Control de accesorios
- `equipo_enciende`: Estado al ingreso
- `falla_principal`: Descripción del problema reportado
- `diagnostico_sic`: Diagnóstico técnico completo
- Fechas de diagnóstico y reparación

**Propiedades Calculadas:**
- `dias_diagnostico`: Tiempo que tomó el diagnóstico
- `dias_reparacion`: Tiempo que tomó la reparación

**Funcionalidad Especial:**
- `calcular_gama()`: Consulta tabla de referencias para determinar gama automáticamente

---

### 3️⃣ **ReferenciaGamaEquipo** - Catálogo de Gamas

**Propósito:** Tabla de referencia para clasificar equipos por gama automáticamente.

**Campos:**
- `marca` y `modelo_base`: Identificación (ej: "Dell", "Inspiron")
- `gama`: alta/media/baja
- `rango_costo_min` y `rango_costo_max`: Rangos de referencia
- `activo`: Control de referencias activas

**Método Importante:**
- `obtener_gama(marca, modelo)`: Busca coincidencias exactas o parciales

**Ejemplo de Uso:**
```python
# Crear referencia
ReferenciaGamaEquipo.objects.create(
    marca="Dell",
    modelo_base="XPS",
    gama="alta",
    rango_costo_min=25000,
    rango_costo_max=50000
)

# Se usa automáticamente al guardar DetalleEquipo
```

---

### 4️⃣ **Cotizacion** - Propuesta al Cliente

**Propósito:** Gestiona la cotización enviada al cliente.

**Relación:** OneToOne con OrdenServicio

**Campos Principales:**
- `fecha_envio` y `fecha_respuesta`: Control de tiempos
- `usuario_acepto`: True/False/Null (sin respuesta)
- `motivo_rechazo`: Razón del rechazo
- `costo_mano_obra`: Costo de servicio

**Propiedades Calculadas:**
- `costo_total_piezas`: Suma de todas las piezas cotizadas
- `costo_piezas_aceptadas`: Suma solo de piezas aceptadas
- `costo_total`: Piezas + mano de obra
- `dias_sin_respuesta`: Días esperando respuesta del cliente

---

### 5️⃣ **PiezaCotizada** - Piezas Individuales

**Propósito:** Cada pieza incluida en la cotización.

**Relación:** ManyToOne con Cotizacion

**Campos Principales:**
- `componente`: FK a ComponenteEquipo (reutiliza catálogo de ScoreCard)
- `descripcion_adicional`: Detalles específicos
- `cantidad` y `costo_unitario`: Precios
- `sugerida_por_tecnico`: Origen de la sugerencia
- `es_necesaria`: True = funcionalidad, False = mejora
- `aceptada_por_cliente`: Respuesta del cliente
- `orden_prioridad`: Orden de importancia

**Propiedad Calculada:**
- `costo_total`: cantidad × costo_unitario

**Uso para KPIs:**
- Permite analizar qué piezas se rechazan más
- Tasa de aceptación de cotizaciones
- Piezas más solicitadas

---

### 6️⃣ **SeguimientoPieza** - Tracking de Pedidos

**Propósito:** Seguimiento de pedidos a proveedores.

**Relación:** ManyToOne con Cotizacion (una cotización puede tener múltiples pedidos)

**Campos Principales:**
- `proveedor` y `numero_pedido`: Identificación
- `descripcion_piezas`: Qué se pidió
- `fecha_pedido`, `fecha_entrega_estimada`, `fecha_entrega_real`: Control de fechas
- `estado`: pedido/confirmado/transito/retrasado/recibido
- `notas_seguimiento`: Actualizaciones

**Propiedades Calculadas:**
- `dias_desde_pedido`: Días transcurridos
- `esta_retrasado`: True si pasó la fecha estimada
- `dias_retraso`: Cuántos días de retraso lleva

**Para KPIs:**
- Tiempo promedio de entrega por proveedor
- Proveedores más confiables
- Retrasos más comunes

---

### 7️⃣ **VentaMostrador** - Servicios Adicionales

**Propósito:** Ventas adicionales realizadas junto con la orden.

**Relación:** OneToOne con OrdenServicio

**Campos Principales:**
- `folio_venta`: Auto-generado (VM-2025-0001)
- `paquete`: Oro/Plata/Bronce/Ninguno (precios fijos en constants.py)
- Servicios: cambio_pieza, limpieza, kit_limpieza, reinstalacion_so
- Cada servicio tiene su campo de costo

**Propiedades Calculadas:**
- `costo_paquete`: Obtiene precio desde constants.py
- `total_venta`: Suma todos los conceptos

**Precios de Paquetes (definidos en constants.py):**
- **Oro:** $1,500 - Limpieza profunda + pasta térmica premium + optimización + garantía 6 meses
- **Plata:** $1,000 - Limpieza profunda + pasta térmica + optimización + garantía 3 meses  
- **Bronce:** $500 - Limpieza básica + pasta térmica + garantía 1 mes

---

### 8️⃣ **ImagenOrden** - Evidencias Fotográficas

**Propósito:** Almacenar imágenes del equipo en diferentes etapas.

**Relación:** ManyToOne con OrdenServicio (múltiples imágenes por orden)

**Campos Principales:**
- `tipo`: ingreso/diagnostico/reparacion/egreso/problema/otro
- `imagen`: Archivo (JPG, PNG, GIF)
- `descripcion`: Descripción breve
- `subido_por`: Empleado que subió la imagen
- `fecha_subida`: Timestamp automático

**Comportamiento Automático:**
- Al guardar, registra evento en el historial

**Ubicación de Archivos:**
- `media/servicio_tecnico/imagenes/YYYY/MM/`

---

### 9️⃣ **HistorialOrden** - Trazabilidad Completa

**Propósito:** Registro completo de todos los eventos en una orden.

**Relación:** ManyToOne con OrdenServicio

**Campos Principales:**
- `fecha_evento`: Timestamp del evento
- `tipo_evento`: creacion/cambio_estado/cambio_tecnico/comentario/sistema/imagen/cotizacion/pieza
- `estado_anterior` y `estado_nuevo`: Para cambios de estado
- `tecnico_anterior` y `tecnico_nuevo`: Para cambios de técnico
- `comentario`: Descripción detallada
- `usuario`: Quién realizó la acción (null si es sistema)
- `es_sistema`: True si fue generado automáticamente

**Eventos Automáticos:**
- Creación de orden
- Cambio de estado
- Cambio de técnico
- Subida de imágenes
- Creación de incidencia ScoreCard

**Para Auditoría:**
- Trazabilidad completa de quién hizo qué y cuándo
- Historial de comentarios y observaciones
- Timeline completo del proceso

---

## 🔗 Integraciones con Otras Apps

### Integración con `inventario` (Existente)

**Modelos Utilizados:**
- `Sucursal`: Para ubicación de la orden
- `Empleado`: Para responsables y técnicos

**Relaciones:**
```python
OrdenServicio.sucursal → Sucursal
OrdenServicio.responsable_seguimiento → Empleado
OrdenServicio.tecnico_asignado_actual → Empleado
```

### Integración con `scorecard` (Existente)

**Modelos Utilizados:**
- `ComponenteEquipo`: Catálogo de componentes (reutilizado en PiezaCotizada)
- `Incidencia`: Para crear incidencias cuando hay reingresos

**Relaciones:**
```python
PiezaCotizada.componente → ComponenteEquipo
OrdenServicio.incidencia_scorecard → Incidencia
```

**Flujo de Reingreso:**
1. Se marca orden como `es_reingreso = True`
2. Se selecciona `orden_original` (orden anterior)
3. Sistema llama automáticamente a `crear_incidencia_reingreso()`
4. Se crea una incidencia en ScoreCard con:
   - Categoría: "Reingreso de equipo"
   - Severidad: Alta
   - Todos los datos del equipo
   - Referencia al técnico responsable original

### Constantes Compartidas (`config/constants.py`)

**Nuevo archivo** que estandariza valores entre apps:
- `TIPO_EQUIPO_CHOICES`: PC/Laptop/AIO
- `ESTADO_ORDEN_CHOICES`: 11 estados del workflow
- `PAQUETES_CHOICES` y `PRECIOS_PAQUETES`: Servicios adicionales
- `MOTIVO_RHITSO_CHOICES`: Razones para reparación especializada
- Funciones de utilidad: `obtener_precio_paquete()`, etc.

---

## 🎨 Admin de Django - Configuración Completa

### Características Principales

**Inlines (Modelos anidados):**
- `DetalleEquipoInline`: Datos del equipo dentro de la orden
- `ImagenOrdenInline`: Subir imágenes directamente
- `HistorialOrdenInline`: Ver historial (solo lectura)
- `PiezaCotizadaInline`: Agregar piezas en la cotización
- `SeguimientoPiezaInline`: Seguimiento de pedidos

**Visualización Mejorada:**
- **Badges de colores** para estados (verde, amarillo, rojo)
- **Alertas visuales** para órdenes retrasadas
- **Miniaturas de imágenes** en listados
- **Filtros avanzados** por estado, sucursal, fecha
- **Búsqueda** por número de orden, serie, marca, técnico

**Acciones Automáticas:**
- Números de orden auto-generados
- Historial automático de cambios
- Cálculos automáticos de costos y tiempos

---

## 📱 Interfaz de Usuario

### Página de Inicio `/servicio-tecnico/`

**Estadísticas:**
- Total de órdenes
- Órdenes activas (sin entregar)
- Órdenes que requieren atención
- Acceso rápido al admin

**Gráficas y Reportes:**
- Órdenes por estado (tabla)
- Últimas 10 órdenes recientes
- Enlaces rápidos a secciones

**Accesos Directos:**
- Nueva orden
- Ver todas las órdenes
- Cotizaciones
- Imágenes
- Referencias de gama

---

## 📈 KPIs y Métricas Disponibles

### Tiempos de Proceso

**Desde los modelos:**
- `dias_diagnostico`: DetalleEquipo
- `dias_reparacion`: DetalleEquipo
- `dias_en_servicio`: OrdenServicio
- `dias_sin_respuesta`: Cotizacion
- `dias_desde_pedido`: SeguimientoPieza

**Para Análisis:**
```python
# Tiempo promedio de diagnóstico
from django.db.models import Avg
DetalleEquipo.objects.aggregate(
    promedio=Avg('fecha_fin_diagnostico' - 'fecha_inicio_diagnostico')
)

# Órdenes retrasadas
OrdenServicio.objects.filter(
    estado__in=['diagnostico', 'reparacion'],
    fecha_ingreso__lt=timezone.now() - timedelta(days=15)
)
```

### Tasa de Aceptación

```python
# Cotizaciones aceptadas vs rechazadas
total = Cotizacion.objects.count()
aceptadas = Cotizacion.objects.filter(usuario_acepto=True).count()
tasa = (aceptadas / total) * 100
```

### Piezas Más Solicitadas

```python
from django.db.models import Count, Sum
PiezaCotizada.objects.values('componente__nombre').annotate(
    total=Count('id'),
    cantidad_total=Sum('cantidad')
).order_by('-total')
```

### Proveedores Confiables

```python
# Pedidos a tiempo vs retrasados
SeguimientoPieza.objects.values('proveedor').annotate(
    total_pedidos=Count('id'),
    retrasados=Count('id', filter=Q(esta_retrasado=True))
)
```

### Reingresos por Técnico

```python
OrdenServicio.objects.filter(es_reingreso=True).values(
    'tecnico_asignado_actual__nombre'
).annotate(total=Count('id'))
```

---

## 🚀 Uso del Sistema

### Crear una Nueva Orden

**Desde el Admin:**
1. Ir a `Admin > Servicio Técnico > Órdenes de Servicio`
2. Click en "Agregar Orden de Servicio"
3. Llenar datos básicos:
   - Seleccionar sucursal
   - Asignar responsable y técnico
   - Estado inicial: "En Espera"
4. En la sección "Detalle de Equipo":
   - Tipo, marca, modelo, número de serie
   - ¿Tiene cargador?
   - ¿Equipo enciende?
   - Descripción de la falla
5. Guardar → Se genera automáticamente:
   - Número de orden (ORD-2025-XXXX)
   - Primer evento en historial
   - Campos de fecha calculados

### Proceso de Diagnóstico

1. Cambiar estado a "En Diagnóstico"
2. En DetalleEquipo:
   - Registrar fecha_inicio_diagnostico
   - Realizar diagnóstico
   - Registrar diagnóstico_sic
   - Registrar fecha_fin_diagnostico
3. Sistema calcula automáticamente `dias_diagnostico`

### Crear Cotización

1. Cambiar estado a "Esperando Aprobación Cliente"
2. En pestaña "Cotización":
   - Click "Agregar Cotización"
   - Agregar piezas necesarias (inline)
   - Registrar costo de mano de obra
3. Sistema calcula automáticamente `costo_total`
4. Enviar al cliente
5. Al recibir respuesta:
   - Marcar `usuario_acepto` (Sí/No)
   - Si rechaza, seleccionar motivo
   - Marcar piezas aceptadas individualmente

### Seguimiento de Piezas

1. En la cotización, agregar "Seguimiento de Pieza"
2. Registrar:
   - Proveedor
   - Fecha de pedido
   - Fecha estimada de entrega
   - Número de pedido
3. Actualizar estado conforme avanza:
   - Pedido → Confirmado → Tránsito → Recibido
4. Si se retrasa:
   - Estado: "Retrasado"
   - Sistema alerta visualmente
   - Actualizar fecha estimada

### Subir Imágenes

1. En la orden, sección "Imágenes":
2. Click "Agregar Imagen"
3. Seleccionar tipo (ingreso/egreso/diagnóstico)
4. Subir archivo
5. Agregar descripción
6. Sistema registra automáticamente en historial

### Reingresos

**Cuando un equipo regresa:**
1. Crear nueva orden
2. Marcar `es_reingreso = True`
3. Seleccionar `orden_original`
4. Guardar
5. **Sistema automáticamente:**
   - Crea incidencia en ScoreCard
   - Vincula ambas órdenes
   - Registra en historial
   - Notifica (si está configurado)

---

## 🔧 Configuración de Gamas de Equipos

### Poblar Tabla de Referencias

```python
# Ejemplo de población inicial
from servicio_tecnico.models import ReferenciaGamaEquipo

referencias = [
    # Gama Alta
    ('Dell', 'XPS', 'alta', 25000, 50000),
    ('Lenovo', 'ThinkPad', 'alta', 20000, 45000),
    ('HP', 'ZBook', 'alta', 22000, 48000),
    ('Apple', 'MacBook', 'alta', 30000, 80000),
    
    # Gama Media
    ('Dell', 'Inspiron', 'media', 12000, 22000),
    ('Lenovo', 'IdeaPad', 'media', 10000, 20000),
    ('HP', 'Pavilion', 'media', 11000, 21000),
    ('Acer', 'Aspire', 'media', 9000, 18000),
    
    # Gama Baja
    ('HP', 'Compaq', 'baja', 5000, 10000),
    ('Acer', 'Extensa', 'baja', 5500, 11000),
    ('Lenovo', 'V Series', 'baja', 6000, 12000),
]

for marca, modelo, gama, min_cost, max_cost in referencias:
    ReferenciaGamaEquipo.objects.get_or_create(
        marca=marca,
        modelo_base=modelo,
        defaults={
            'gama': gama,
            'rango_costo_min': min_cost,
            'rango_costo_max': max_cost
        }
    )
```

---

## 🛠️ Próximas Fases

### FASE 2 - Formularios Personalizados
- Formulario de ingreso de orden más intuitivo
- Wizard multi-paso para nuevas órdenes
- Validaciones personalizadas
- Auto-completado de marcas y modelos

### FASE 3 - Dashboard Avanzado con KPIs
- Gráficas interactivas (Chart.js)
- Reportes por sucursal, técnico, periodo
- Exportación a Excel/PDF
- Métricas en tiempo real

### FASE 4 - Búsqueda y Filtros
- Búsqueda avanzada de órdenes
- Filtros combinados
- Búsqueda por historial de equipo (número de serie)
- Autocompletar en búsquedas

### FASE 5 - Notificaciones
- Emails automáticos al cambiar estados
- Alertas de retrasos
- Notificación cuando llegan piezas
- Recordatorios de seguimiento

### FASE 6 - App Móvil / PWA
- Escaneo de códigos QR
- Subida de imágenes desde móvil
- Consulta rápida de órdenes
- Notificaciones push

---

## 📚 Ejemplos de Consultas Útiles

### Órdenes Pendientes de un Técnico

```python
from servicio_tecnico.models import OrdenServicio

tecnico_id = 1
ordenes = OrdenServicio.objects.filter(
    tecnico_asignado_actual_id=tecnico_id,
    estado__in=['diagnostico', 'reparacion']
).select_related('detalle_equipo', 'sucursal')
```

### Historial de un Equipo (por número de serie)

```python
from servicio_tecnico.models import DetalleEquipo

numero_serie = "ABC123XYZ"
historial = DetalleEquipo.objects.filter(
    numero_serie=numero_serie
).select_related('orden').order_by('-orden__fecha_ingreso')
```

### Cotizaciones Sin Respuesta > 7 Días

```python
from django.utils import timezone
from datetime import timedelta
from servicio_tecnico.models import Cotizacion

hace_7_dias = timezone.now() - timedelta(days=7)
sin_respuesta = Cotizacion.objects.filter(
    usuario_acepto__isnull=True,
    fecha_envio__lt=hace_7_dias
)
```

### Top 10 Fallas Más Comunes

```python
from django.db.models import Count
from servicio_tecnico.models import DetalleEquipo

fallas = DetalleEquipo.objects.values('falla_principal').annotate(
    total=Count('orden')
).order_by('-total')[:10]
```

---

## 🆘 Solución de Problemas

### La gama no se calcula automáticamente

**Causa:** No hay referencias en `ReferenciaGamaEquipo` para esa marca/modelo.

**Solución:**
1. Agregar referencia en el admin
2. O el sistema asigna "media" por defecto

### No se crea la incidencia de reingreso

**Verificar:**
```python
# En la consola Django
orden = OrdenServicio.objects.get(numero_orden_interno='ORD-2025-0001')
incidencia = orden.crear_incidencia_reingreso(usuario=request.user)
print(incidencia)  # Debe mostrar el objeto Incidencia
```

### No aparece el historial

**Causa:** El historial se crea automáticamente al guardar.

**Solución:** Hacer un cambio (ej: cambiar estado) y guardar.

---

## 📞 Soporte y Contribuciones

**Desarrollado para:** Centro de Servicio Técnico  
**Tecnologías:** Django 5.2.5, Python 3.13, Bootstrap 5  
**Integrado con:** `inventario`, `scorecard`

**Documentación adicional:**
- `GUIA_COLORES_BADGES.md` - Colores estandarizados
- `SCORECARD_README.md` - Integración con calidad

---

## ✅ Checklist de Implementación

- [x] Modelos creados y migrados
- [x] Admin configurado con inlines
- [x] Constantes compartidas en `config/constants.py`
- [x] Integración con inventario (Sucursal, Empleado)
- [x] Integración con scorecard (ComponenteEquipo, Incidencia)
- [x] Página de inicio funcional
- [x] Historial automático
- [x] Cálculos automáticos (días, costos)
- [x] Folios auto-generados
- [x] Documentación completa

**¡Sistema listo para usar!** 🎉

Accede a:
- **Administración:** http://localhost:8000/admin/servicio_tecnico/
- **Página de inicio:** http://localhost:8000/servicio-tecnico/

