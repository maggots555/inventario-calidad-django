# 📦 Plan de Implementación: Sistema de Inventario de Almacén

**Fecha de Creación:** 2 de Diciembre, 2025  
**Estado:** 📋 Planificación  
**Autor:** Equipo de Desarrollo

---

## 📑 Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Análisis de Viabilidad](#análisis-de-viabilidad)
3. [Arquitectura del Sistema](#arquitectura-del-sistema)
4. [Componentes Principales](#componentes-principales)
5. [Modelos de Base de Datos](#modelos-de-base-de-datos)
6. [Flujos de Trabajo](#flujos-de-trabajo)
7. [Interfaz de Usuario](#interfaz-de-usuario)
8. [Roadmap de Implementación](#roadmap-de-implementación)
9. [Preguntas y Decisiones Pendientes](#preguntas-y-decisiones-pendientes)
10. [Notas y Expansiones Futuras](#notas-y-expansiones-futuras)

---

## 🎯 Visión General

### Problema a Resolver

Actualmente el sistema cuenta con un **inventario de oficina** para materiales de uso diario. Se requiere un nuevo módulo robusto para gestionar el **inventario de almacén central** con las siguientes características:

- Control estricto de productos mediante códigos únicos
- Sistema de auditorías con registro de diferencias
- Flujo de aprobación para bajas de inventario
- Notificaciones en tiempo real entre recepción y almacén
- Trazabilidad completa de movimientos
- Reportes de discrepancias y análisis de diferencias

### Objetivos del Sistema

✅ **Control Robusto:** Cada movimiento debe ser aprobado y trazable  
✅ **Transparencia:** Sistema de auditorías formales con evidencia  
✅ **Eficiencia:** Notificaciones automáticas reducen tiempos de espera  
✅ **Prevención:** Alertas de reposición y análisis de patrones  
✅ **Integración:** Se conecta con el ecosistema Django existente  

### Diferencias con Inventario Actual

| Característica | Inventario Oficina | Inventario Almacén |
|----------------|--------------------|--------------------|
| **Propósito** | Consumibles diarios | Productos de almacén central |
| **Control** | Movimientos rápidos | Aprobación obligatoria |
| **Usuarios** | Personal de oficina | Recepción + Agente Almacén |
| **Auditorías** | Básicas | Formales con diferencias |
| **Notificaciones** | No | Sí, en tiempo real |
| **Trazabilidad** | Simple | Completa con responsables |
| **Integración ST** | No | Sí, con órdenes de servicio |

### 🔗 Integración con Servicio Técnico

**IMPORTANTE:** El inventario de almacén manejará piezas de repuesto para reparaciones.

**Flujo de Piezas para Servicio Técnico:**

```
1. SOLICITUD DE PIEZA (Servicio Técnico)
   ↓ Técnico diagnostica equipo
   ↓ Identifica pieza necesaria
   ↓ Crea solicitud de pieza desde orden de servicio
   ↓ Solicitud llega a Almacén
   
2. RECEPCIÓN DE PIEZA (Almacén)
   ↓ Pieza llega del proveedor
   ↓ Se da de alta en almacén
   ↓ Se vincula con orden de servicio
   ↓ Estado: "Disponible para servicio"
   
3. ASIGNACIÓN (Almacén → Servicio Técnico)
   ↓ Agente de almacén aprueba salida
   ↓ Stock se descuenta automáticamente
   ↓ Pieza queda ligada a la orden
   ↓ Trazabilidad completa: Orden → Pieza → Equipo
   
4. SEGUIMIENTO
   ↓ Historial en orden de servicio
   ↓ Historial en producto de almacén
   ↓ Costo de pieza se suma al servicio
   ↓ Auditoría: quién, cuándo, para qué orden
```

**Beneficios de esta Integración:**
- 📊 **Trazabilidad Total:** Sabes exactamente qué pieza se usó en qué equipo
- 💰 **Costeo Preciso:** Suma automática del costo de piezas al servicio
- 📈 **Analytics:** Piezas más usadas, tiempos de espera, proveedores
- 🔍 **Auditoría:** Verificación cruzada entre inventario y servicios
- ⚡ **Eficiencia:** Menos errores en asignación de piezas

---

## ✅ Análisis de Viabilidad

### Viabilidad Técnica: **ALTA** ✅

**Fortalezas del Proyecto Actual:**
- ✅ Django 5.2.5 estable y probado
- ✅ Arquitectura multi-app ya establecida
- ✅ Sistema de autenticación y permisos funcional
- ✅ Bootstrap 5 + TypeScript configurados
- ✅ Experiencia en reportes (Excel, PDF) y analytics (Plotly)
- ✅ Infraestructura de static files y media files
- ✅ QR code generation ya implementado

**Tecnologías Disponibles:**
```python
# Ya instaladas y probadas:
- Django 5.2.5              # Framework principal
- Bootstrap 5.3.2           # UI consistente
- TypeScript 5.9.3          # JavaScript tipado
- Plotly >= 6.3.0          # Visualizaciones interactivas
- OpenPyXL 3.1.5           # Exportación Excel
- ReportLab 4.4.4          # Generación PDF
- QRCode[pil] 7.4.2        # Códigos QR automáticos
- Pillow 11.3.0            # Procesamiento de imágenes
```

### Viabilidad Operativa: **ALTA** ✅

**Recursos Humanos:**
- Personal de recepción (solicitan bajas)
- Agentes de almacén (aprueban/gestionan)
- Auditores (realizan conteos físicos)
- Supervisores (resuelven discrepancias)

**Infraestructura:**
- Servidor existente con Django
- Base de datos SQLite (dev) / PostgreSQL (prod)
- Sistema de archivos para imágenes de evidencia
- Posibilidad de lectores QR/barcode

### Viabilidad Económica: **ALTA** ✅

**Inversión:**
- ⏱️ Tiempo de desarrollo (principal recurso)
- 💻 No requiere hardware adicional
- 📚 No requiere nuevas licencias de software
- 🔧 Usa stack tecnológico existente

**Retorno de Inversión (ROI):**
- 📉 Reducción de pérdidas por diferencias no detectadas
- ⚡ Mayor velocidad en aprobación de bajas
- 📊 Visibilidad de problemas recurrentes
- 🎯 Mejor control de reposiciones

---

## 🏗️ Arquitectura del Sistema

### Estructura de Aplicación Django

```
almacen/                          # Nueva app independiente
├── __init__.py
├── admin.py                      # Configuración del admin de Django
├── apps.py                       # Configuración de la app
├── models.py                     # Modelos de base de datos
├── views.py                      # Vistas principales
├── forms.py                      # Formularios personalizados
├── urls.py                       # Rutas de la aplicación
├── signals.py                    # Señales para notificaciones automáticas
│
├── utils/                        # Utilidades especializadas
│   ├── __init__.py
│   ├── auditoria.py             # Lógica de auditorías
│   ├── notificaciones.py        # Sistema de notificaciones
│   ├── reportes.py              # Generación de reportes
│   └── validaciones.py          # Validaciones de negocio
│
├── migrations/                   # Migraciones de base de datos
│   └── __init__.py
│
├── templates/almacen/           # Templates específicos
│   ├── base_almacen.html        # Template base del módulo
│   ├── dashboard_almacen.html   # Dashboard principal
│   ├── panel_solicitudes.html   # Panel de notificaciones
│   ├── lista_productos.html     # Catálogo de productos
│   ├── detalle_producto.html    # Detalle con historial
│   ├── crear_auditoria.html     # Formulario de auditoría
│   ├── registrar_diferencia.html # Registro de discrepancias
│   └── reportes/                # Templates de reportes
│       ├── reporte_diferencias.html
│       └── reporte_auditoria.html
│
├── static/almacen/              # Static files específicos (opcional)
│   ├── css/
│   │   └── almacen.css          # Estilos específicos
│   └── js/
│       └── almacen.js           # JavaScript compilado
│
└── tests/                       # Tests unitarios
    ├── __init__.py
    ├── test_models.py
    ├── test_views.py
    └── test_utils.py
```

### Integración con Proyecto Existente

**settings.py:**
```python
INSTALLED_APPS = [
    # ... apps existentes ...
    'inventario',              # Inventario de oficina
    'scorecard',               # Control de calidad
    'servicio_tecnico',        # Órdenes de servicio
    'almacen',                 # ← NUEVA APP
]
```

**config/urls.py:**
```python
urlpatterns = [
    # ... rutas existentes ...
    path('inventario/', include('inventario.urls')),
    path('almacen/', include('almacen.urls')),  # ← NUEVA RUTA
]
```

**Navegación (base.html):**
```html
<!-- Añadir en navbar -->
<li class="nav-item">
    <a class="nav-link" href="{% url 'almacen:dashboard' %}">
        <i class="bi bi-box-seam"></i> Almacén
    </a>
</li>
```

---

## 🧩 Componentes Principales

### 1. Gestión de Productos de Almacén

**Características:**
- Código único por producto (SKU, EAN, código interno)
- Información detallada (nombre, descripción, categoría)
- Ubicación física en almacén (pasillo-estante-nivel)
- Tracking de stock (actual, mínimo, máximo)
- **Tipo de producto: Resurtible vs Único** (nueva característica)
- Generación automática de código QR
- Imagen del producto
- Información del proveedor
- Tiempo estimado de reposición

**Tipos de Producto:**

1. **📦 Productos Resurtibles** (Stock permanente)
   - Son productos que se compran regularmente para mantener en stock
   - Tienen niveles mínimo/máximo definidos
   - Generan alertas de reposición automáticas
   - **Ejemplos:**
     - Botellas de limpiador LCD
     - Alcohol isopropílico
     - Pasta térmica
     - Cables HDMI genéricos
     - Cajas de cartón
     - Bolsas antiestáticas
   - **Comportamiento:**
     - Cuando baja del mínimo → Alerta de reposición
     - Se compran en cantidad para mantener stock
     - Estadísticas de rotación y consumo

2. **🔧 Productos Únicos** (Compra específica)
   - Son piezas que se compran para un servicio específico
   - NO tienen stock mínimo/máximo (siempre es opcional)
   - Generalmente vinculados a una orden de servicio
   - **Ejemplos:**
     - Pantalla LCD para laptop específica
     - Placa madre de un modelo exacto
     - Batería de equipo descontinuado
     - Componente especializado
   - **Comportamiento:**
     - No generan alertas de reposición
     - Se registran cuando llegan
     - Típicamente se agotan al usarse (stock → 0)
     - Pueden o no volver a comprarse

**Funcionalidades:**
- ✅ Crear/Editar/Eliminar productos
- ✅ Marcar como Resurtible o Único al crear
- ✅ Búsqueda por código, nombre, categoría, ubicación
- ✅ Filtros avanzados (incluyendo tipo de producto)
- ✅ Vista de detalle con historial completo
- ✅ Alertas de stock bajo (solo para resurtibles)
- ✅ Exportación a Excel/PDF

---

### 2. Sistema de Notificaciones y Solicitudes de Baja

**Propósito:** Comunicación fluida entre recepción y almacén

**Actores:**
- **Solicitante (Recepción):** Persona que necesita un producto
- **Agente de Almacén:** Persona que aprueba y ejecuta la baja

**Tipos de Solicitud:**
- 🏢 **Consumo Interno:** Uso general de oficina/recepción
- 🔧 **Servicio Técnico:** Pieza para reparación de equipo
- 🛒 **Venta Mostrador:** Venta directa al cliente
- 📦 **Transferencia:** Movimiento entre sucursales

**Estados de Solicitud:**
- 🟡 **Pendiente:** Recién creada, esperando atención
- 🟢 **Aprobada:** Agente aprobó, stock descontado
- 🔴 **Rechazada:** Agente rechazó (requiere justificación)
- ⏸️ **En Espera:** Producto no disponible, en proceso de reposición
- 🔗 **Vinculada a Orden:** Asignada a orden de servicio técnico

**Información de Solicitud:**
- Producto solicitado
- Cantidad requerida
- Tipo de solicitud (consumo, servicio técnico, venta, transferencia)
- **Orden de servicio técnico** (si aplica - ForeignKey a servicio_tecnico.OrdenServicio)
- Solicitante (empleado de recepción o técnico)
- Fecha y hora de solicitud
- Observaciones del solicitante
- Estado actual
- Agente que procesó (si aplica)
- Fecha de procesamiento
- Observaciones del agente
- Flag de reposición necesaria

**Campo Especial para Servicio Técnico:**
```python
# En el modelo SolicitudBaja
orden_servicio = models.ForeignKey(
    'servicio_tecnico.OrdenServicio',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='solicitudes_piezas',
    verbose_name='Orden de Servicio Técnico',
    help_text='Vincula esta pieza con una orden de reparación'
)
```

---

### 3. Sistema de Auditorías

**Tipos de Auditoría:**

1. **Auditoría Completa**
   - Se revisan todos los productos del almacén
   - Se realiza típicamente de forma anual o semestral
   - Requiere más tiempo y recursos

2. **Auditoría Cíclica**
   - Se audita por categoría o ubicación
   - Rotación periódica (semanal/mensual)
   - Permite cobertura continua sin cerrar operaciones

3. **Auditoría por Diferencias**
   - Solo productos con discrepancias previas
   - Verificación de correcciones aplicadas
   - Identificación de productos problemáticos

4. **Auditoría ABC**
   - Enfoque en productos de alto valor
   - Basada en análisis de Pareto
   - Optimiza recursos de auditoría

**Proceso de Auditoría:**

```
PASO 1: Creación de Auditoría
├─ Seleccionar tipo
├─ Asignar auditor
├─ Definir productos a auditar
└─ Estado: "En Proceso"

PASO 2: Conteo Físico
├─ Auditor recorre almacén
├─ Cuenta productos físicamente
├─ Registra cantidad real
└─ Toma fotografías de evidencia (opcional)

PASO 3: Registro de Diferencias
├─ Sistema compara stock_sistema vs stock_físico
├─ Calcula diferencias automáticamente
├─ Auditor registra razón de la diferencia
└─ Documenta acciones correctivas

PASO 4: Aprobación y Ajuste
├─ Supervisor revisa diferencias
├─ Aprueba ajustes al sistema
├─ Stock se actualiza
└─ Estado: "Completada"
```

**Razones de Diferencias (Catálogo):**
- 📉 **Merma natural:** Evaporación, degradación
- 🔨 **Daño:** Producto dañado no registrado
- 🚨 **Robo:** Pérdida no autorizada
- 📝 **Error de sistema:** Problema en registro
- 📦 **Error de recepción:** Conteo incorrecto al ingresar
- 🚚 **Error de despacho:** Entregado sin registrar
- ❓ **Desconocida:** Requiere investigación

---

### 4. Panel de Control para Agente de Almacén

**Dashboard Principal:**

```
┌─────────────────────────────────────────────────────────┐
│  🏢 Dashboard de Almacén                                │
│  Usuario: Juan Pérez (Agente de Almacén)               │
└─────────────────────────────────────────────────────────┘

┌──────────────────── KPIs Principales ─────────────────────┐
│  📬 Solicitudes      ⚠️ Stock         🔄 Reposiciones    │
│     Pendientes          Bajo             Activas         │
│        15                8                  3            │
│                                                           │
│  📊 Diferencias      💰 Valor         📈 Rotación        │
│     por Resolver        Total            Mensual         │
│        2            $1,250,000            89%            │
└───────────────────────────────────────────────────────────┘

┌───────────────── Cola de Solicitudes ─────────────────────┐
│  🔔 URGENTE - Hace 5 minutos                             │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Solicitante: María González (Recepción)            │ │
│  │ Producto: Cable HDMI 2.0 - 3 metros (SKU-12345)   │ │
│  │ Cantidad: 2 unidades                                │ │
│  │ Stock Actual: 15 unidades                           │ │
│  │ Observaciones: Cliente en mostrador esperando      │ │
│  │                                                     │ │
│  │ [✅ Aprobar]  [❌ Rechazar]  [👁️ Ver Detalles]     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  🔔 Hace 12 minutos                                      │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ Solicitante: Carlos Ramírez (Recepción)            │ │
│  │ Producto: Teclado USB Mecánico (SKU-67890)         │ │
│  │ Cantidad: 1 unidad                                  │ │
│  │ Stock Actual: 3 unidades ⚠️ (Mínimo: 5)            │ │
│  │                                                     │ │
│  │ [✅ Aprobar]  [❌ Rechazar]  [👁️ Ver Detalles]     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
│  [Ver todas las solicitudes (15 pendientes)]             │
└───────────────────────────────────────────────────────────┘

┌────────────── Productos Requieren Reposición ────────────┐
│  📦 Mouse Inalámbrico Logitech M185                      │
│      Stock: 2 / Mínimo: 10 / Máximo: 30                 │
│      [🛒 Crear Orden de Compra]  [📊 Ver Historial]     │
│  ─────────────────────────────────────────────────────── │
│  📦 Adaptador USB-C a HDMI                               │
│      Stock: 0 / Mínimo: 8 / Máximo: 20                  │
│      ⚠️ AGOTADO - Solicitud de compra enviada            │
│  ─────────────────────────────────────────────────────── │
│  📦 Cable de Red CAT6 - 5 metros                         │
│      Stock: 4 / Mínimo: 15 / Máximo: 40                 │
│      [🛒 Crear Orden de Compra]  [📊 Ver Historial]     │
└───────────────────────────────────────────────────────────┘
```

**Funcionalidades del Panel:**
- ✅ Vista en tiempo real de solicitudes pendientes
- ✅ Notificaciones visuales (badges, colores)
- ✅ Acciones rápidas (aprobar/rechazar con un clic)
- ✅ Alertas de stock bajo integradas
- ✅ Gestión de reposiciones
- ✅ Historial de actividad del agente

---

### 5. Integración con Servicio Técnico - Gestión de Piezas

**Objetivo:** Vincular piezas de repuesto con órdenes de servicio para reparación de equipos.

#### Flujo Simplificado: Recepción de Pieza para Servicio

```
┌─────────────────────────────────────────────────────────────┐
│  PASO 1: LLEGA LA PIEZA                                    │
├─────────────────────────────────────────────────────────────┤
│  • Pieza llega del proveedor                                │
│  • Agente de almacén la recibe físicamente                  │
│  • Escanea/busca el producto en el sistema                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PASO 2: DAR DE ALTA Y VINCULAR (TODO EN UNA PANTALLA)    │
├─────────────────────────────────────────────────────────────┤
│  • Formulario de ingreso al almacén:                        │
│    ├─ Producto: [Memoria RAM DDR4 8GB]                     │
│    ├─ Cantidad: [1]                                        │
│    ├─ Costo: [$1,200]                                      │
│    └─ ¿Es para un servicio técnico?                        │
│         ☑ Sí                                                │
│         └─ Buscar Orden: [ST-2024-___] 🔍                  │
│                                                             │
│  • Campo de búsqueda de órdenes activas:                    │
│    - Busca por número de orden                              │
│    - Busca por cliente                                      │
│    - Busca por equipo                                       │
│    - Muestra solo órdenes activas (en proceso)              │
│                                                             │
│  • Selecciona la orden → Listo                              │
│  • Al guardar:                                              │
│    ✅ Pieza se da de alta en almacén                        │
│    ✅ Stock aumenta                                         │
│    ✅ Pieza queda vinculada a la orden                      │
│    ✅ Marca automática: "Asignada a ST-2024-001"           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  PASO 3: USO DE LA PIEZA                                   │
├─────────────────────────────────────────────────────────────┤
│  • Técnico retira la pieza                                  │
│  • Stock se descuenta automáticamente                       │
│  • Costo de pieza se suma al servicio                       │
│  • Trazabilidad completa: Orden → Pieza → Equipo           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  CONSULTAS Y REPORTES                                       │
├─────────────────────────────────────────────────────────────┤
│  DESDE ORDEN DE SERVICIO:                                   │
│    • Ver qué piezas se usaron                               │
│    • Costo total de piezas                                  │
│                                                             │
│  DESDE PRODUCTO DE ALMACÉN:                                 │
│    • Ver en qué órdenes se usó                              │
│    • Historial de servicios                                 │
│                                                             │
│  REPORTES:                                                  │
│    • Piezas más usadas en reparaciones                      │
│    • Costo promedio de piezas por servicio                  │
└─────────────────────────────────────────────────────────────┘
```

#### Modelos Simplificados

**En `almacen/models.py`:**
```python
class MovimientoAlmacen(models.Model):
    """
    Registro de entrada/salida de productos en almacén.
    Puede estar vinculado a una orden de servicio técnico.
    """
    TIPO_MOVIMIENTO = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
    ]
    
    tipo = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO)
    producto = models.ForeignKey('ProductoAlmacen', on_delete=models.CASCADE)
    cantidad = models.IntegerField()
    fecha = models.DateTimeField(auto_now_add=True)
    empleado = models.ForeignKey('inventario.Empleado', on_delete=models.SET_NULL, null=True)
    
    # Vinculación SIMPLE con Servicio Técnico
    orden_servicio = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='piezas_almacen',
        verbose_name='Orden de Servicio',
        help_text='Si esta pieza es para un servicio, selecciona la orden'
    )
    
    observaciones = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Movimiento de Almacén'
        verbose_name_plural = 'Movimientos de Almacén'
        ordering = ['-fecha']
```

**En `servicio_tecnico/models.py` (AGREGAR MÉTODOS):**
```python
class OrdenServicio(models.Model):
    # ... campos existentes ...
    
    def get_piezas_almacen(self):
        """Obtiene todas las piezas de almacén usadas en esta orden"""
        from almacen.models import MovimientoAlmacen
        return MovimientoAlmacen.objects.filter(orden_servicio=self)
    
    def calcular_costo_piezas_almacen(self):
        """Calcula el costo total de piezas de almacén utilizadas"""
        piezas = self.get_piezas_almacen()
        total = sum(
            movimiento.producto.costo_unitario * movimiento.cantidad
            for movimiento in piezas
        )
        return total
```

#### Interfaz de Usuario Simplificada

**1. Al Recibir Pieza en Almacén - Formulario de Ingreso:**
```html
┌─────────────────────────────────────────────────────────────┐
│  📦 REGISTRAR ENTRADA AL ALMACÉN                           │
├─────────────────────────────────────────────────────────────┤
│  Producto:        [Memoria RAM DDR4 8GB ▼]                 │
│  Cantidad:        [1]                                       │
│  Costo Unitario:  [$1,200.00]                              │
│  Proveedor:       [Tech Parts S.A. ▼]                      │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ ¿Esta pieza es para un Servicio Técnico?             │ │
│  │                                                       │ │
│  │ ☐ No, es para stock general                          │ │
│  │ ☑ Sí, es para una orden específica                   │ │
│  │                                                       │ │
│  │   Buscar Orden Activa:                                │ │
│  │   [ST-2024-___________] 🔍 Buscar                    │ │
│  │                                                       │ │
│  │   📋 Órdenes Activas Recientes:                       │ │
│  │   ┌─────────────────────────────────────────────────┐ │ │
│  │   │ ○ ST-2024-145 - Juan Pérez                      │ │ │
│  │   │   Laptop HP EliteBook 840 G8                    │ │ │
│  │   │   Técnico: Carlos Méndez                        │ │ │
│  │   ├─────────────────────────────────────────────────┤ │ │
│  │   │ ○ ST-2024-148 - María González                  │ │ │
│  │   │   Desktop Dell OptiPlex 7090                    │ │ │
│  │   │   Técnico: Ana Torres                           │ │ │
│  │   ├─────────────────────────────────────────────────┤ │ │
│  │   │ ○ ST-2024-150 - Roberto Sánchez                 │ │ │
│  │   │   Laptop Lenovo ThinkPad X1                     │ │ │
│  │   │   Técnico: Carlos Méndez                        │ │ │
│  │   └─────────────────────────────────────────────────┘ │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  Observaciones:   [Pieza solicitada para reparación...]    │
│                                                             │
│  [💾 Guardar Entrada]  [❌ Cancelar]                       │
└─────────────────────────────────────────────────────────────┘

Al guardar:
✅ Stock aumenta automáticamente
✅ Pieza queda vinculada a ST-2024-145
✅ Aparece en el historial de la orden de servicio
```

**2. Vista en la Orden de Servicio Técnico:**
```html
┌─────────────────────────────────────────────────────────────┐
│  ORDEN DE SERVICIO #ST-2024-145                            │
├─────────────────────────────────────────────────────────────┤
│  Cliente: Juan Pérez                                        │
│  Equipo: Laptop HP EliteBook 840 G8                         │
│  Estado: En Reparación                                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  📦 PIEZAS ASIGNADAS DESDE ALMACÉN                          │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐ │
│  │ ✅ Memoria RAM DDR4 8GB (SKU-RAM-001)                 │ │
│  │    Cantidad: 1                                        │ │
│  │    Costo: $1,200                                      │ │
│  │    Recibida: 02/12/2024 09:30                         │ │
│  │    Almacenista: Pedro López                           │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  💰 RESUMEN DE COSTOS:                                      │
│     Diagnóstico: $200                                       │
│     Mano de Obra: $500                                      │
│     Piezas Almacén: $1,200                                  │
│     ─────────────────                                       │
│     Total: $1,900                                           │
└─────────────────────────────────────────────────────────────┘
```

**3. Historial del Producto en Almacén:**
```html
┌─────────────────────────────────────────────────────────────┐
│  PRODUCTO: Memoria RAM DDR4 8GB (SKU-RAM-001)              │
│  Stock Actual: 8 unidades                                   │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  📊 HISTORIAL DE MOVIMIENTOS                                │
├─────────────────────────────────────────────────────────────┤
│  02/12/2024 09:30 - ENTRADA (+1)                           │
│  🔗 Vinculado a: ST-2024-145 (Juan Pérez - Laptop HP)      │
│  Empleado: Pedro López                                      │
│  Costo: $1,200                                              │
│  ─────────────────────────────────────────────────────────  │
│  28/11/2024 14:15 - ENTRADA (+5)                           │
│  📦 Stock general                                           │
│  Empleado: Ana Martínez                                     │
│  Costo unitario: $1,150                                     │
│  ─────────────────────────────────────────────────────────  │
│  25/11/2024 10:20 - SALIDA (-2)                            │
│  🔗 Vinculado a: ST-2024-120 (Carlos Ruiz - Desktop Dell)  │
│  Empleado: Pedro López                                      │
└─────────────────────────────────────────────────────────────┘
```

#### Reportes y Consultas

**1. Consulta Rápida: Piezas de una Orden**
- Desde la orden de servicio ver todas las piezas asignadas
- Costo total de piezas
- Fecha de llegada de cada pieza

**2. Consulta Rápida: Órdenes donde se Usó una Pieza**
- Desde el producto en almacén ver historial de servicios
- En qué equipos se instaló
- Clientes que recibieron esa pieza

**3. Reporte de Piezas Más Usadas**
- Top 10 piezas utilizadas en reparaciones
- Valor total consumido por mes
- Stock promedio necesario

#### Ventajas de esta Integración Simplificada

✅ **Proceso Simple:**
- Un solo paso: recibir pieza y vincular a orden
- No requiere múltiples aprobaciones
- Interfaz intuitiva con búsqueda de órdenes

✅ **Trazabilidad Básica pero Efectiva:**
- Sabes qué pieza se usó en qué equipo
- Historial visible desde ambos módulos
- Vinculación permanente en la base de datos

✅ **Costeo Automático:**
- El costo de la pieza se suma automáticamente al servicio
- No hay cálculos manuales
- Cotización precisa

✅ **Control de Inventario:**
- Stock actualizado automáticamente
- Visibilidad de piezas asignadas vs disponibles
- Reportes de consumo por servicio técnico

---

## 💾 Modelos de Base de Datos

### Modelo Principal: ProductoAlmacen

```python
from django.db import models
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User

class CategoriaAlmacen(models.Model):
    """Categorías de productos de almacén"""
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Categoría de Almacén'
        verbose_name_plural = 'Categorías de Almacén'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class Proveedor(models.Model):
    """Proveedores de productos"""
    nombre = models.CharField(max_length=200)
    contacto = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    direccion = models.TextField(blank=True)
    tiempo_entrega_dias = models.IntegerField(
        default=7,
        help_text='Tiempo promedio de entrega en días'
    )
    
    class Meta:
        verbose_name = 'Proveedor'
        verbose_name_plural = 'Proveedores'
        ordering = ['nombre']
    
    def __str__(self):
        return self.nombre


class ProductoAlmacen(models.Model):
    """
    Producto almacenado en el almacén central.
    Puede ser resurtible (stock permanente) o único (compra específica).
    """
    TIPO_PRODUCTO = [
        ('resurtible', 'Resurtible - Stock Permanente'),
        ('unico', 'Único - Compra Específica'),
    ]
    
    # Identificación
    codigo_producto = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Código/SKU',
        help_text='Código único del producto (SKU, EAN, etc.)'
    )
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    categoria = models.ForeignKey(
        CategoriaAlmacen,
        on_delete=models.SET_NULL,
        null=True,
        related_name='productos'
    )
    
    # Tipo de producto (NUEVO)
    tipo_producto = models.CharField(
        max_length=20,
        choices=TIPO_PRODUCTO,
        default='resurtible',
        verbose_name='Tipo de Producto',
        help_text='Resurtible: se mantiene en stock. Único: compra específica'
    )
    
    # Ubicación física
    ubicacion_fisica = models.CharField(
        max_length=50,
        blank=True,
        help_text='Ej: A-03-2 (pasillo-estante-nivel)'
    )
    
    # Stock
    stock_actual = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    stock_minimo = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Solo aplica para productos resurtibles'
    )
    stock_maximo = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Solo aplica para productos resurtibles'
    )
    
    # Costos (costo promedio o último costo)
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text='Costo unitario actual o promedio'
    )
    
    # Proveedor principal (puede cambiar)
    proveedor_principal = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productos_principales',
        verbose_name='Proveedor Principal',
        help_text='Proveedor habitual de este producto'
    )
    tiempo_reposicion_dias = models.IntegerField(
        default=7,
        help_text='Tiempo estimado de reposición en días'
    )
    
    # Multimedia
    imagen = models.ImageField(
        upload_to='almacen/productos/',
        blank=True,
        null=True
    )
    qr_code = models.ImageField(
        upload_to='almacen/qr_codes/',
        blank=True,
        null=True,
        help_text='Código QR generado automáticamente'
    )
    
    # Metadatos
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    creado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='productos_almacen_creados'
    )
    
    class Meta:
        verbose_name = 'Producto de Almacén'
        verbose_name_plural = 'Productos de Almacén'
        ordering = ['nombre']
    
    def __str__(self):
        tipo_emoji = '📦' if self.tipo_producto == 'resurtible' else '🔧'
        return f"{tipo_emoji} {self.codigo_producto} - {self.nombre}"
    
    def esta_bajo_minimo(self):
        """Verifica si el stock está bajo el mínimo (solo para resurtibles)"""
        if self.tipo_producto == 'resurtible':
            return self.stock_actual <= self.stock_minimo
        return False
    
    def requiere_reposicion(self):
        """Alias de esta_bajo_minimo para claridad"""
        return self.esta_bajo_minimo()
    
    def porcentaje_stock(self):
        """Porcentaje de stock actual respecto al máximo"""
        if self.tipo_producto == 'resurtible' and self.stock_maximo > 0:
            return (self.stock_actual / self.stock_maximo) * 100
        return 0
    
    def valor_total_stock(self):
        """Valor total del stock actual"""
        return self.stock_actual * self.costo_unitario
    
    def save(self, *args, **kwargs):
        # Auto-generar código QR si no existe
        if not self.qr_code:
            # Aquí iría la lógica de generación de QR
            pass
        super().save(*args, **kwargs)
```

### Modelo: CompraProducto (NUEVO - Historial de Compras)

```python
class CompraProducto(models.Model):
    """
    Historial de compras de productos.
    Registra cada compra con su proveedor y costo específico.
    Permite analizar variaciones de precio y evaluar proveedores.
    """
    # Producto comprado
    producto = models.ForeignKey(
        ProductoAlmacen,
        on_delete=models.CASCADE,
        related_name='historial_compras'
    )
    
    # Proveedor de esta compra específica
    proveedor = models.ForeignKey(
        Proveedor,
        on_delete=models.SET_NULL,
        null=True,
        related_name='compras_realizadas',
        verbose_name='Proveedor de esta Compra'
    )
    
    # Detalles de la compra
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Costo unitario en esta compra específica'
    )
    costo_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Cantidad × Costo Unitario'
    )
    
    # Fechas
    fecha_pedido = models.DateField()
    fecha_recepcion = models.DateField(null=True, blank=True)
    dias_entrega = models.IntegerField(
        null=True,
        blank=True,
        help_text='Días entre pedido y recepción (calculado)'
    )
    
    # Documentos
    numero_factura = models.CharField(max_length=50, blank=True)
    numero_orden_compra = models.CharField(max_length=50, blank=True)
    
    # Vinculación con Servicio Técnico (si aplica)
    orden_servicio = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='compras_piezas',
        verbose_name='Orden de Servicio',
        help_text='Si esta compra es para un servicio específico'
    )
    
    # Observaciones
    observaciones = models.TextField(blank=True)
    
    # Metadatos
    registrado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    fecha_registro = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Compra de Producto'
        verbose_name_plural = 'Compras de Productos'
        ordering = ['-fecha_recepcion', '-fecha_pedido']
    
    def __str__(self):
        return f"{self.producto.codigo_producto} - {self.cantidad} uds de {self.proveedor} ({self.fecha_pedido})"
    
    def calcular_dias_entrega(self):
        """Calcula días entre pedido y recepción"""
        if self.fecha_recepcion and self.fecha_pedido:
            delta = self.fecha_recepcion - self.fecha_pedido
            self.dias_entrega = delta.days
    
    def save(self, *args, **kwargs):
        # Calcular costo total
        self.costo_total = self.cantidad * self.costo_unitario
        
        # Calcular días de entrega
        self.calcular_dias_entrega()
        
        # Actualizar costo unitario del producto (puede ser promedio o último)
        # Opción 1: Usar el último costo
        self.producto.costo_unitario = self.costo_unitario
        
        # Opción 2: Calcular promedio ponderado (comentado, elegir una)
        # total_compras = CompraProducto.objects.filter(producto=self.producto)
        # costo_promedio = total_compras.aggregate(
        #     promedio=Avg('costo_unitario')
        # )['promedio']
        # self.producto.costo_unitario = costo_promedio
        
        self.producto.save()
        
        super().save(*args, **kwargs)
```

### Modelo: MovimientoAlmacen

```python
class MovimientoAlmacen(models.Model):
    """
    Registro de entrada/salida de productos en almacén.
    Puede estar vinculado a una orden de servicio técnico.
    """
    TIPO_MOVIMIENTO = [
        ('entrada', 'Entrada'),
        ('salida', 'Salida'),
    ]
    
    # Movimiento básico
    tipo = models.CharField(max_length=10, choices=TIPO_MOVIMIENTO)
    producto = models.ForeignKey(
        ProductoAlmacen,
        on_delete=models.CASCADE,
        related_name='movimientos'
    )
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    fecha = models.DateTimeField(auto_now_add=True)
    
    # Responsable
    empleado = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Registrado por'
    )
    
    # Vinculación SIMPLE con Servicio Técnico
    orden_servicio = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='piezas_almacen',
        verbose_name='Orden de Servicio',
        help_text='Si esta pieza es para un servicio, selecciona la orden'
    )
    
    # Relación con compra (si es una entrada)
    compra = models.ForeignKey(
        CompraProducto,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='movimientos',
        help_text='Compra asociada a este movimiento (si aplica)'
    )
    
    # Detalles
    costo_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text='Costo al momento del movimiento'
    )
    observaciones = models.TextField(blank=True)
    
    # Tracking
    stock_anterior = models.IntegerField(
        help_text='Stock antes del movimiento'
    )
    stock_posterior = models.IntegerField(
        help_text='Stock después del movimiento'
    )
    
    class Meta:
        verbose_name = 'Movimiento de Almacén'
        verbose_name_plural = 'Movimientos de Almacén'
        ordering = ['-fecha']
    
    def __str__(self):
        tipo_icon = '📥' if self.tipo == 'entrada' else '📤'
        return f"{tipo_icon} {self.producto.codigo_producto} - {self.cantidad} ({self.fecha.strftime('%d/%m/%Y')})"
    
    def costo_total(self):
        """Costo total del movimiento"""
        return self.cantidad * self.costo_unitario
    
    def save(self, *args, **kwargs):
        # Registrar stock antes del movimiento
        if not self.pk:  # Solo en creación
            self.stock_anterior = self.producto.stock_actual
            
            # Actualizar stock del producto
            if self.tipo == 'entrada':
                self.producto.stock_actual += self.cantidad
            else:  # salida
                self.producto.stock_actual -= self.cantidad
            
            self.stock_posterior = self.producto.stock_actual
            self.producto.save()
        
        super().save(*args, **kwargs)
```

### Modelo: Auditoria

```python
class Auditoria(models.Model):
    """Auditoría de inventario de almacén"""
    TIPO_AUDITORIA = [
        ('completa', 'Auditoría Completa'),
        ('ciclica', 'Auditoría Cíclica'),
        ('diferencias', 'Auditoría por Diferencias'),
        ('abc', 'Auditoría ABC (Alto Valor)'),
    ]
    
    ESTADO_AUDITORIA = [
        ('en_proceso', 'En Proceso'),
        ('completada', 'Completada'),
        ('con_diferencias', 'Completada con Diferencias'),
    ]
    
    # Información básica
    tipo = models.CharField(max_length=20, choices=TIPO_AUDITORIA)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_AUDITORIA,
        default='en_proceso'
    )
    
    # Fechas
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    
    # Auditor
    auditor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='auditorias_almacen'
    )
    
    # Detalles
    observaciones_generales = models.TextField(blank=True)
    total_productos_auditados = models.IntegerField(default=0)
    total_diferencias_encontradas = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = 'Auditoría'
        verbose_name_plural = 'Auditorías'
        ordering = ['-fecha_inicio']
    
    def __str__(self):
        return f"Auditoría {self.get_tipo_display()} - {self.fecha_inicio.strftime('%d/%m/%Y')}"


class DiferenciaAuditoria(models.Model):
    """Diferencias encontradas en auditoría"""
    RAZON_DIFERENCIA = [
        ('merma', 'Merma Natural'),
        ('dano', 'Daño/Deterioro'),
        ('robo', 'Robo/Pérdida'),
        ('error_sistema', 'Error de Sistema'),
        ('error_recepcion', 'Error al Recibir'),
        ('error_despacho', 'Error al Despachar'),
        ('desconocida', 'Razón Desconocida'),
    ]
    
    # Relaciones
    auditoria = models.ForeignKey(
        Auditoria,
        on_delete=models.CASCADE,
        related_name='diferencias'
    )
    producto = models.ForeignKey(
        ProductoAlmacen,
        on_delete=models.CASCADE
    )
    
    # Cantidades
    stock_sistema = models.IntegerField(
        help_text='Stock según el sistema'
    )
    stock_fisico = models.IntegerField(
        help_text='Stock contado físicamente'
    )
    diferencia = models.IntegerField(
        help_text='Diferencia (físico - sistema). Negativo = faltante'
    )
    
    # Análisis
    razon = models.CharField(max_length=20, choices=RAZON_DIFERENCIA)
    razon_detalle = models.TextField(
        blank=True,
        verbose_name='Detalle de la Razón'
    )
    evidencia = models.ImageField(
        upload_to='almacen/auditorias/evidencias/',
        blank=True,
        null=True,
        help_text='Fotografía de la evidencia'
    )
    
    # Ajuste
    ajuste_realizado = models.BooleanField(default=False)
    fecha_ajuste = models.DateTimeField(null=True, blank=True)
    responsable_ajuste = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ajustes_auditoria'
    )
    acciones_correctivas = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Diferencia de Auditoría'
        verbose_name_plural = 'Diferencias de Auditoría'
        ordering = ['-auditoria__fecha_inicio']
    
    def __str__(self):
        signo = '+' if self.diferencia > 0 else ''
        return f"{self.producto.codigo_producto}: {signo}{self.diferencia}"
    
    def save(self, *args, **kwargs):
        # Calcular diferencia automáticamente
        self.diferencia = self.stock_fisico - self.stock_sistema
        super().save(*args, **kwargs)
```

### Modelo: SolicitudBaja

```python
class SolicitudBaja(models.Model):
    """
    Solicitud de baja de producto del almacén.
    Sistema de aprobación para control de salidas.
    """
    TIPO_SOLICITUD = [
        ('consumo', 'Consumo Interno'),
        ('servicio_tecnico', 'Servicio Técnico'),
        ('venta', 'Venta Mostrador'),
        ('transferencia', 'Transferencia'),
    ]
    
    ESTADO_SOLICITUD = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('rechazada', 'Rechazada'),
    ]
    
    # Básico
    tipo_solicitud = models.CharField(
        max_length=20,
        choices=TIPO_SOLICITUD,
        default='consumo'
    )
    producto = models.ForeignKey(
        ProductoAlmacen,
        on_delete=models.CASCADE,
        related_name='solicitudes_baja'
    )
    cantidad = models.IntegerField(validators=[MinValueValidator(1)])
    
    # Vinculación con Servicio Técnico (OPCIONAL)
    orden_servicio = models.ForeignKey(
        'servicio_tecnico.OrdenServicio',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_piezas_almacen',
        verbose_name='Orden de Servicio'
    )
    
    # Solicitante
    solicitante = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        related_name='solicitudes_almacen'
    )
    fecha_solicitud = models.DateTimeField(auto_now_add=True)
    observaciones = models.TextField(blank=True)
    
    # Estado
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_SOLICITUD,
        default='pendiente'
    )
    
    # Procesamiento
    agente_almacen = models.ForeignKey(
        'inventario.Empleado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='solicitudes_procesadas'
    )
    fecha_procesado = models.DateTimeField(null=True, blank=True)
    observaciones_agente = models.TextField(blank=True)
    requiere_reposicion = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Solicitud de Baja'
        verbose_name_plural = 'Solicitudes de Baja'
        ordering = ['-fecha_solicitud']
    
    def __str__(self):
        return f"{self.producto.codigo_producto} - {self.cantidad} ({self.get_estado_display()})"
```

---

## 🎨 Interfaz de Usuario: Gestión de Productos

### Formulario de Creación/Edición de Producto

```html
┌─────────────────────────────────────────────────────────────┐
│  📦 CREAR PRODUCTO DE ALMACÉN                              │
├─────────────────────────────────────────────────────────────┤
│  Código/SKU: *     [LCD-CLEANER-500ML___________]          │
│  Nombre: *         [Limpiador LCD 500ml__________]         │
│  Descripción:      [Limpiador especial para pantallas...]  │
│  Categoría: *      [Químicos y Limpieza ▼]                 │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 🏷️ TIPO DE PRODUCTO: *                                │ │
│  │                                                       │ │
│  │ ○ 📦 Resurtible - Stock Permanente                   │ │
│  │   ├─ Se mantiene en inventario regularmente          │ │
│  │   ├─ Genera alertas de reposición                    │ │
│  │   └─ Ej: Limpiadores, cables, consumibles            │ │
│  │                                                       │ │
│  │ ○ 🔧 Único - Compra Específica                       │ │
│  │   ├─ Compra para un servicio específico              │ │
│  │   ├─ NO genera alertas automáticas                   │ │
│  │   └─ Ej: Pantalla laptop específica, placa madre     │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  📍 Ubicación Física:  [A-05-3_____] (pasillo-estante-nivel)│
│                                                             │
│  ┌─────────── STOCK (solo si es Resurtible) ────────────┐ │
│  │ Stock Inicial:     [50___]                           │ │
│  │ Stock Mínimo:      [10___]  ← Alerta de reposición  │ │
│  │ Stock Máximo:      [100__]                           │ │
│  └──────────────────────────────────────────────────────┘ │
│                                                             │
│  💰 Costo Unitario: *  [$___85.50__]                       │
│                                                             │
│  🏭 Proveedor:         [Distribuidora Tech ▼]              │
│  ⏱️ Tiempo Reposición: [5___] días                         │
│                                                             │
│  📸 Imagen:            [Subir archivo] [Examinar...]       │
│                                                             │
│  [💾 Guardar Producto]  [❌ Cancelar]                      │
└─────────────────────────────────────────────────────────────┘

NOTA: Si selecciona "Único", los campos de stock mínimo/máximo
      se deshabilitan o se marcan como opcionales.
```

### Lista de Productos con Filtro por Tipo

```html
┌─────────────────────────────────────────────────────────────┐
│  📦 PRODUCTOS DE ALMACÉN                                   │
├─────────────────────────────────────────────────────────────┤
│  Buscar: [__________] 🔍   [➕ Nuevo Producto]            │
│                                                             │
│  Filtros:                                                   │
│  Tipo: [Todos ▼] [Resurtibles] [Únicos]                   │
│  Categoría: [Todas ▼]                                       │
│  Stock: [Todos] [Stock Bajo] [Agotados]                    │
│                                                             │
│  Mostrando: 156 productos (📦 120 Resurtibles, 🔧 36 Únicos)│
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  📦 LCD-CLEANER-500ML - Limpiador LCD 500ml                │
│  Tipo: Resurtible • Categoría: Químicos                    │
│  Stock: 45/100 (Mín: 10) • Ubicación: A-05-3               │
│  [Editar] [Ver Historial] [Reporte]                        │
├─────────────────────────────────────────────────────────────┤
│  🔧 LCD-HP-840G8 - Pantalla LCD 14" HP EliteBook 840 G8    │
│  Tipo: Único • Categoría: Pantallas                         │
│  Stock: 1 • Vinculado a: ST-2024-145                        │
│  [Editar] [Ver Historial]                                   │
├─────────────────────────────────────────────────────────────┤
│  📦 HDMI-CABLE-2M - Cable HDMI 2.0 - 2 metros              │
│  Tipo: Resurtible • Categoría: Cables                       │
│  Stock: 8/50 ⚠️ (Mín: 15) • Ubicación: B-02-1              │
│  [Editar] [Ver Historial] [Crear Orden Compra]             │
└─────────────────────────────────────────────────────────────┘
```

### Registro de Compra con Proveedor y Costo

```html
┌─────────────────────────────────────────────────────────────┐
│  🛒 REGISTRAR COMPRA DE PRODUCTO                           │
├─────────────────────────────────────────────────────────────┤
│  Producto: *           [Memoria RAM DDR4 8GB ▼]            │
│                        SKU: RAM-DDR4-8GB-001                │
│                        Stock Actual: 12 unidades            │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 🏭 INFORMACIÓN DEL PROVEEDOR                          │ │
│  │                                                       │ │
│  │ Proveedor: *       [Tech Parts S.A. ▼]               │ │
│  │                    Tel: 555-1234                      │ │
│  │                    Email: ventas@techparts.com        │ │
│  │                    Tiempo Entrega: 5 días             │ │
│  │                                                       │ │
│  │ [➕ Agregar Nuevo Proveedor]                          │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 💰 INFORMACIÓN DE COSTOS                              │ │
│  │                                                       │ │
│  │ Cantidad: *        [10__] unidades                    │ │
│  │ Costo Unitario: *  [$1,250.00_____]                  │ │
│  │ Costo Total:       $12,500.00 (calculado)            │ │
│  │                                                       │ │
│  │ 📊 Historial de Costos de este Producto:             │ │
│  │ ┌─────────────────────────────────────────────────┐  │ │
│  │ │ Última compra: $1,200 (Tech Parts, 15/11/2024) │  │ │
│  │ │ Promedio: $1,225                                │  │ │
│  │ │ Mínimo: $1,180 (Distribuidora XYZ)             │  │ │
│  │ │ Máximo: $1,290 (CompuSuministros)              │  │ │
│  │ └─────────────────────────────────────────────────┘  │ │
│  │                                                       │ │
│  │ ⚠️ El costo actual ($1,250) es 4% mayor que la       │ │
│  │    última compra. ¿Desea continuar?                  │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 📅 FECHAS Y DOCUMENTOS                                │ │
│  │                                                       │ │
│  │ Fecha Pedido: *    [02/12/2024___]                   │ │
│  │ Fecha Recepción:   [02/12/2024___] (hoy)             │ │
│  │ Días de Entrega:   0 días (calculado)                │ │
│  │                                                       │ │
│  │ Nº Factura:        [FAC-2024-12345__________]        │ │
│  │ Nº Orden Compra:   [OC-2024-890____________]         │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐ │
│  │ 🔗 VINCULACIÓN (Opcional)                             │ │
│  │                                                       │ │
│  │ ☐ Esta compra es para un Servicio Técnico            │ │
│  │                                                       │ │
│  │   Buscar Orden: [ST-2024-___] 🔍                     │ │
│  │                                                       │ │
│  │   Si se vincula, la pieza quedará asignada a esa     │ │
│  │   orden de servicio automáticamente.                 │ │
│  └───────────────────────────────────────────────────────┘ │
│                                                             │
│  Observaciones:        [Proveedor ofreció descuento...]    │
│                                                             │
│  [💾 Registrar Compra]  [❌ Cancelar]                      │
└─────────────────────────────────────────────────────────────┘

Al guardar:
✅ Se registra la compra en historial
✅ Stock aumenta automáticamente (+10)
✅ Se registra MovimientoAlmacen (entrada)
✅ Se guarda proveedor y costo de esta compra
✅ Si está vinculado a orden, queda asignado
```

### Historial de Compras del Producto

```html
┌─────────────────────────────────────────────────────────────┐
│  PRODUCTO: Memoria RAM DDR4 8GB (RAM-DDR4-8GB-001)         │
│  Stock: 22 unidades • Costo Actual: $1,250                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  📊 HISTORIAL DE COMPRAS Y PROVEEDORES                      │
├─────────────────────────────────────────────────────────────┤
│  [Filtrar por Proveedor ▼] [Últimos 6 meses ▼] [Exportar] │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  02/12/2024 - Tech Parts S.A.                              │
│  ├─ Cantidad: 10 unidades                                  │
│  ├─ Costo Unitario: $1,250.00                              │
│  ├─ Costo Total: $12,500.00                                │
│  ├─ Días de Entrega: 0 días (entrega inmediata)            │
│  ├─ Factura: FAC-2024-12345                                │
│  └─ OC: OC-2024-890                                        │
├─────────────────────────────────────────────────────────────┤
│  15/11/2024 - Tech Parts S.A.                              │
│  ├─ Cantidad: 5 unidades                                   │
│  ├─ Costo Unitario: $1,200.00 ⬇️ (4% menos)               │
│  ├─ Costo Total: $6,000.00                                 │
│  ├─ Días de Entrega: 5 días                                │
│  ├─ Factura: FAC-2024-11890                                │
│  ├─ Vinculado a: ST-2024-120 (Carlos Ruiz)                 │
│  └─ OC: OC-2024-750                                        │
├─────────────────────────────────────────────────────────────┤
│  28/10/2024 - Distribuidora XYZ                            │
│  ├─ Cantidad: 20 unidades                                  │
│  ├─ Costo Unitario: $1,180.00 ⬇️ (5.6% menos)             │
│  ├─ Costo Total: $23,600.00                                │
│  ├─ Días de Entrega: 7 días                                │
│  ├─ Factura: DX-2024-5678                                  │
│  └─ OC: OC-2024-620                                        │
├─────────────────────────────────────────────────────────────┤
│  10/10/2024 - CompuSuministros                             │
│  ├─ Cantidad: 8 unidades                                   │
│  ├─ Costo Unitario: $1,290.00 ⬆️ (3.2% más)               │
│  ├─ Costo Total: $10,320.00                                │
│  ├─ Días de Entrega: 10 días (retraso)                     │
│  ├─ Factura: CS-2024-3456                                  │
│  └─ OC: OC-2024-510                                        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  📈 ANÁLISIS DE PROVEEDORES                                 │
├─────────────────────────────────────────────────────────────┤
│  Proveedor              | Compras | Promedio  | Entrega    │
│  ──────────────────────────────────────────────────────────│
│  Tech Parts S.A.        |    2    | $1,225    | 2.5 días ✅│
│  Distribuidora XYZ      |    1    | $1,180 🏆 | 7 días     │
│  CompuSuministros       |    1    | $1,290    | 10 días ⚠️ │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  💡 RECOMENDACIONES                                         │
├─────────────────────────────────────────────────────────────┤
│  • Mejor Precio: Distribuidora XYZ ($1,180)                │
│  • Más Rápido: Tech Parts S.A. (2.5 días promedio)         │
│  • Más Confiable: Tech Parts S.A. (2 compras exitosas)     │
│                                                             │
│  Sugerencia: Considerar comprar a Distribuidora XYZ para   │
│  ahorrar $70 por unidad, aunque la entrega es más lenta.   │
└─────────────────────────────────────────────────────────────┘
```

### Comparación de Proveedores para un Producto

```html
┌─────────────────────────────────────────────────────────────┐
│  🏭 COMPARAR PROVEEDORES - Memoria RAM DDR4 8GB            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Tech Parts S.A.                            ⭐⭐⭐⭐    │  │
│  │ ─────────────────────────────────────────────────────│  │
│  │ Último Precio: $1,250                                │  │
│  │ Promedio: $1,225                                     │  │
│  │ Entregas: 2.5 días promedio                          │  │
│  │ Compras: 2 veces                                     │  │
│  │ Confiabilidad: Alta ✅                                │  │
│  │                                                      │  │
│  │ [🛒 Comprar a este Proveedor]                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ Distribuidora XYZ                          ⭐⭐⭐⭐⭐  │  │
│  │ ─────────────────────────────────────────────────────│  │
│  │ Último Precio: $1,180 🏆 MEJOR PRECIO                │  │
│  │ Promedio: $1,180                                     │  │
│  │ Entregas: 7 días promedio                            │  │
│  │ Compras: 1 vez                                       │  │
│  │ Confiabilidad: Media ⚠️                               │  │
│  │                                                      │  │
│  │ [🛒 Comprar a este Proveedor]                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ CompuSuministros                           ⭐⭐⭐     │  │
│  │ ─────────────────────────────────────────────────────│  │
│  │ Último Precio: $1,290 ⚠️ MÁS CARO                    │  │
│  │ Promedio: $1,290                                     │  │
│  │ Entregas: 10 días promedio ⏱️                        │  │
│  │ Compras: 1 vez                                       │  │
│  │ Confiabilidad: Baja (tuvo retrasos) ❌                │  │
│  │                                                      │  │
│  │ [🛒 Comprar a este Proveedor]                        │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  [➕ Agregar Nuevo Proveedor]                               │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Reportes con Análisis de Proveedores

### 1. Reporte de Variación de Costos
- Gráfica de evolución de precio por producto
- Identificar tendencias (aumento/disminución)
- Alertas de aumentos significativos (>10%)

### 2. Reporte de Desempeño de Proveedores
- Tiempo promedio de entrega por proveedor
- Tasa de cumplimiento de fechas
- Comparación de costos entre proveedores
- Recomendación del mejor proveedor por producto

### 3. Dashboard de Compras
- Total gastado por proveedor (mensual/anual)
- Productos más caros vs más baratos
- Proveedores más utilizados
- Ahorros potenciales cambiando de proveedor

---

*(Continuará en la siguiente sección...)*
