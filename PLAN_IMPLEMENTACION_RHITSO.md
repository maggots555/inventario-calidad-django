# 📋 PLAN DE IMPLEMENTACIÓN - MÓDULO RHITSO

**Fecha de Creación**: 09 de Octubre de 2025  
**Proyecto**: Sistema de Gestión de Servicio Técnico - Django  
**Módulo**: Seguimiento Especializado RHITSO (Reparaciones de Alta Complejidad)

---

## 📊 PROGRESO GENERAL DE IMPLEMENTACIÓN

| Fase | Descripción | Estado | Fecha Completada |
|------|-------------|--------|------------------|
| **1** | Backend - Modelos y Base de Datos | ✅ **COMPLETADA** | 10/Oct/2025 |
| **2** | Backend - Signals y Lógica de Negocio | ⏳ **EN PROCESO** | - |
| **3** | Backend - Forms para RHITSO | ⬜ Pendiente | - |
| **4** | Backend - Vista Principal RHITSO | ⬜ Pendiente | - |
| **5** | Backend - Vistas AJAX y Auxiliares | ⬜ Pendiente | - |
| **6** | Backend - URLs y Admin | ⬜ Pendiente | - |
| **7** | Frontend - Template Principal | ⬜ Pendiente | - |
| **8** | Frontend - Timeline e Historial | ⬜ Pendiente | - |
| **9** | Frontend - Incidencias y Estadísticas | ⬜ Pendiente | - |
| **10** | Frontend - Galería RHITSO | ⬜ Pendiente | - |
| **11** | Integración - Botón en Detalle Orden | ⬜ Pendiente | - |
| **12** | Testing y Validación | ⬜ Pendiente | - |

**Progreso Total**: 8.33% (1/12 fases completadas)

---

## ✅ ÚLTIMOS CAMBIOS REALIZADOS

**Fecha**: 10 de Octubre de 2025  
**Fase Completada**: FASE 1 - Backend - Modelos y Base de Datos

**Archivos Modificados**:
- `config/constants.py` - 8 nuevos grupos de choices
- `servicio_tecnico/models.py` - 6 modelos nuevos + campos en OrdenServicio
- `servicio_tecnico/migrations/0007_...py` - Migración aplicada

**Modelos Creados**:
1. EstadoRHITSO (Modelo 11)
2. CategoriaDiagnostico (Modelo 12)
3. TipoIncidenciaRHITSO (Modelo 13)
4. SeguimientoRHITSO (Modelo 14)
5. IncidenciaRHITSO (Modelo 15)
6. ConfiguracionRHITSO (Modelo 16)

**Siguiente Paso**: Implementar FASE 2 - Signals y Lógica de Negocio

---

## 🎯 OBJETIVO GENERAL

Implementar un sistema de seguimiento especializado para órdenes que requieren reparación externa (RHITSO), que permita:

1. **Reutilizar campos existentes** en OrdenServicio y DetalleEquipo
2. **Gestionar estados específicos** del proceso RHITSO con responsables claros
3. **Registrar incidencias** detalladas con tipos predefinidos y seguimiento
4. **Mantener timeline completo** de todos los cambios y eventos
5. **Galería especializada** con tipo de imagen "Autorización/Pass"
6. **Acceso condicional** desde detalle_orden solo cuando es_candidato_rhitso=True

---

## 📊 ANÁLISIS DE CAMPOS EXISTENTES REUTILIZABLES

### ✅ En Modelo `OrdenServicio`:
- `es_candidato_rhitso` (BooleanField) - **YA EXISTE**
- `motivo_rhitso` (CharField con MOTIVO_RHITSO_CHOICES) - **YA EXISTE**
- `descripcion_rhitso` (TextField) - **YA EXISTE**

### ✅ En Modelo `DetalleEquipo`:
- `diagnostico_sic` (TextField) - **REUTILIZAR para mostrar en panel RHITSO**
- `fecha_inicio_diagnostico` - **REUTILIZAR**
- `fecha_fin_diagnostico` - **REUTILIZAR**
- `equipo_enciende` - **REUTILIZAR**
- `falla_principal` - **REUTILIZAR**

### ✅ En Modelo `ImagenOrden`:
- Sistema de galerías completo - **EXTENDER con nuevo tipo**

### ✅ En Modelo `HistorialOrden`:
- Sistema de eventos automáticos - **REUTILIZAR para comentarios**

---

## 🏗️ ARQUITECTURA DEL MÓDULO RHITSO

### Nuevos Modelos a Crear:
1. **EstadoRHITSO** - Catálogo de estados del proceso RHITSO
2. **SeguimientoRHITSO** - Historial de cambios de estado RHITSO
3. **CategoriaDiagnostico** - Categorías técnicas de problemas
4. **TipoIncidenciaRHITSO** - Catálogo de tipos de incidencias
5. **IncidenciaRHITSO** - Registro de problemas con RHITSO
6. **ConfiguracionRHITSO** - Configuración del módulo

### Campos Nuevos en OrdenServicio:
- `estado_rhitso` (CharField) - Estado actual en proceso RHITSO
- `fecha_envio_rhitso` (DateTimeField) - Fecha de envío a RHITSO
- `fecha_recepcion_rhitso` (DateTimeField) - Fecha de recepción desde RHITSO
- `tecnico_diagnostico` (ForeignKey a Empleado) - Técnico que hizo diagnóstico SIC
- `fecha_diagnostico_sic` (DateTimeField) - Fecha del diagnóstico SIC
- `complejidad_estimada` (CharField con choices) - BAJA, MEDIA, ALTA, CRITICA

---

## 📅 PLAN DE IMPLEMENTACIÓN POR FASES

---

## 🔷 FASE 1: BACKEND - MODELOS Y BASE DE DATOS ✅ COMPLETADA

### Objetivos:
Crear la estructura de base de datos completa sin tocar frontend

### ✅ Estado: COMPLETADA el 10 de Octubre de 2025

**Resumen de lo implementado:**
- ✅ Modificado `config/constants.py` con 8 nuevos grupos de choices
- ✅ Creados 6 nuevos modelos en `servicio_tecnico/models.py`
- ✅ Agregados 6 campos nuevos a OrdenServicio
- ✅ Agregada property `dias_en_rhitso()` a OrdenServicio
- ✅ Migración 0007 creada y aplicada exitosamente
- ✅ Verificación: `python manage.py check` sin errores
- ✅ Backup de base de datos creado antes de migrar

### Tareas Detalladas:

#### 1.1 Modificar `config/constants.py` ✅ COMPLETADO
- **✅ Agregado** nuevo choice `('autorizacion', 'Autorización/Pass - RHITSO')` a `TIPO_IMAGEN_CHOICES`
- **✅ Creado** `OWNER_RHITSO_CHOICES` con: SIC, RHITSO, CLIENTE, COMPRAS, CERRADO
- **✅ Creado** `COMPLEJIDAD_CHOICES` con: BAJA, MEDIA, ALTA, CRITICA
- **✅ Creado** `GRAVEDAD_INCIDENCIA_CHOICES` con: BAJA, MEDIA, ALTA, CRITICA
- **✅ Creado** `ESTADO_INCIDENCIA_CHOICES` con: ABIERTA, EN_REVISION, RESUELTA, CERRADA
- **✅ Creado** `IMPACTO_CLIENTE_CHOICES` con: NINGUNO, BAJO, MEDIO, ALTO
- **✅ Creado** `PRIORIDAD_CHOICES` con: BAJA, MEDIA, ALTA, URGENTE
- **✅ Creado** `TIPO_CONFIG_CHOICES` con: STRING, INTEGER, BOOLEAN, JSON

#### 1.2 Crear Modelo `EstadoRHITSO` en `servicio_tecnico/models.py` ✅ COMPLETADO
**Propósito**: Catálogo de estados del proceso RHITSO con responsables

**Campos**:
- `estado` (CharField, max_length=100, unique=True) - Nombre del estado
- `owner` (CharField con choices: SIC, RHITSO, CLIENTE, COMPRAS, CERRADO) - Responsable del estado
- `descripcion` (TextField, blank=True) - Descripción del estado
- `color` (CharField, max_length=20, default='secondary') - Color para badges (info, warning, success, danger, primary, secondary, dark)
- `orden` (IntegerField, default=0) - Orden de aparición (del 1 al 32)
- `activo` (BooleanField, default=True) - Estado activo
- `fecha_creacion` (DateTimeField, auto_now_add=True)

**Choices para owner**:
```python
OWNER_CHOICES = [
    ('SIC', 'SIC - Sistema de Información del Cliente'),
    ('RHITSO', 'RHITSO - Centro de Reparación Especializada'),
    ('CLIENTE', 'Cliente - Usuario Final'),
    ('COMPRAS', 'Compras - Departamento de Adquisiciones'),
    ('CERRADO', 'Cerrado - Proceso Finalizado'),
]
```

**Meta**:
- `ordering = ['orden']`
- `verbose_name = "Estado RHITSO"`
- `verbose_name_plural = "Estados RHITSO"`

**Métodos**:
- `__str__()` retorna el nombre del estado
- Método classmethod `obtener_primer_estado()` que retorna el estado con menor orden
- Método `get_badge_class()` que retorna clase CSS de Bootstrap según owner:
  - SIC → 'badge bg-info'
  - RHITSO → 'badge bg-primary'
  - CLIENTE → 'badge bg-warning'
  - COMPRAS → 'badge bg-secondary'
  - CERRADO → 'badge bg-dark'

#### 1.2 Crear Modelo `EstadoRHITSO` en `servicio_tecnico/models.py` ✅ COMPLETADO
**Propósito**: Catálogo de estados del proceso RHITSO con responsables

**✅ Implementado como MODELO 11** con todos los campos especificados:
- `estado`, `owner`, `descripcion`, `color`, `orden`, `activo`, `fecha_creacion`
- Método classmethod `obtener_primer_estado()`
- Método `get_badge_class()` con mapeo de colores por owner

#### 1.3 Crear Modelo `CategoriaDiagnostico` en `servicio_tecnico/models.py` ✅ COMPLETADO
**Propósito**: Categorías técnicas de problemas que requieren RHITSO

**✅ Implementado como MODELO 12** con todos los campos especificados:
- `nombre`, `descripcion`, `requiere_rhitso`, `tiempo_estimado_dias`, `complejidad_tipica`, `activo`, `fecha_creacion`
- Validación: MinValueValidator(1) en tiempo_estimado_dias

#### 1.4 Crear Modelo `TipoIncidenciaRHITSO` en `servicio_tecnico/models.py` ✅ COMPLETADO
**Propósito**: Catálogo de tipos de incidencias con RHITSO

**✅ Implementado como MODELO 13** con todos los campos especificados:
- `nombre`, `descripcion`, `gravedad`, `color`, `requiere_accion_inmediata`, `activo`, `fecha_creacion`

#### 1.5 Crear Modelo `SeguimientoRHITSO` en `servicio_tecnico/models.py` ✅ COMPLETADO
**Propósito**: Historial completo de cambios de estado RHITSO

**✅ Implementado como MODELO 14** con todos los campos especificados:
- `orden`, `estado`, `estado_anterior`, `observaciones`, `fecha_actualizacion`, `usuario_actualizacion`, `tiempo_en_estado_anterior`, `notificado_cliente`
- Método `calcular_tiempo_en_estado()`
- 3 índices de base de datos para optimización

#### 1.6 Crear Modelo `IncidenciaRHITSO` en `servicio_tecnico/models.py` ✅ COMPLETADO
**Propósito**: Registro de problemas e incidencias con RHITSO

**✅ Implementado como MODELO 15** con todos los campos especificados:
- Todos los 13 campos requeridos
- Property `dias_abierta()` - Calcula días desde ocurrencia
- Property `esta_resuelta()` - Verifica si está resuelta o cerrada
- Método `marcar_como_resuelta(usuario, accion_tomada)`
- 3 índices de base de datos para optimización

#### 1.7 Crear Modelo `ConfiguracionRHITSO` en `servicio_tecnico/models.py` ✅ COMPLETADO
**Propósito**: Configuración global del módulo RHITSO

**✅ Implementado como MODELO 16** con todos los campos especificados:
- `clave`, `valor`, `descripcion`, `tipo`, `fecha_actualizacion`
- Classmethod `obtener(clave, default=None)` para obtener valores de configuración

#### 1.8 Agregar Campos Nuevos en `OrdenServicio` ✅ COMPLETADO
**Ubicación**: Después de la sección RHITSO existente

**✅ Campos agregados**:
- `estado_rhitso` (CharField, max_length=100, blank=True)
- `fecha_envio_rhitso` (DateTimeField, null=True, blank=True)
- `fecha_recepcion_rhitso` (DateTimeField, null=True, blank=True)
- `tecnico_diagnostico` (ForeignKey a Empleado, related_name='diagnosticos_realizados')
- `fecha_diagnostico_sic` (DateTimeField, null=True, blank=True)
- `complejidad_estimada` (CharField con COMPLEJIDAD_CHOICES, default='MEDIA', blank=True)

**✅ Property agregada**:
- `dias_en_rhitso()` - Calcula días desde fecha_envio_rhitso hasta ahora o fecha_recepcion_rhitso

#### 1.9 Crear Migraciones ✅ COMPLETADO
- ✅ Ejecutado `python manage.py makemigrations servicio_tecnico`
- ✅ Migración 0007 creada: `0007_categoriadiagnostico_configuracionrhitso_and_more.py`
- ✅ Backup creado: `db.sqlite3.backup_rhitso_20251010_XXXXXX`
- ✅ Migración aplicada exitosamente con `python manage.py migrate servicio_tecnico`
- ✅ Verificación: `python manage.py check` - Sin errores
- ✅ Verificación: Todos los modelos accesibles y funcionales

**Archivos modificados/creados en Fase 1:**
1. `config/constants.py` - 8 nuevas constantes agregadas
2. `servicio_tecnico/models.py` - 6 nuevos modelos + campos en OrdenServicio + importaciones actualizadas
3. `servicio_tecnico/migrations/0007_categoriadiagnostico_configuracionrhitso_and_more.py` - Migración aplicada

---

## 🔷 FASE 2: BACKEND - SIGNALS Y LÓGICA DE NEGOCIO ⏳ SIGUIENTE
**Propósito**: Categorías técnicas de problemas que requieren RHITSO

**Campos**:
- `nombre` (CharField, max_length=100, unique=True)
- `descripcion` (TextField, blank=True)
- `requiere_rhitso` (BooleanField, default=True)
- `tiempo_estimado_dias` (IntegerField, default=7)
- `complejidad_tipica` (CharField con COMPLEJIDAD_CHOICES, default='MEDIA')
- `activo` (BooleanField, default=True)
- `fecha_creacion` (DateTimeField, auto_now_add=True)

**Meta**:
- `ordering = ['nombre']`
- `verbose_name = "Categoría de Diagnóstico"`
- `verbose_name_plural = "Categorías de Diagnóstico"`

#### 1.4 Crear Modelo `TipoIncidenciaRHITSO` en `servicio_tecnico/models.py`
**Propósito**: Catálogo de tipos de incidencias con RHITSO

**Campos**:
- `nombre` (CharField, max_length=100, unique=True)
- `descripcion` (TextField, blank=True)
- `gravedad` (CharField con GRAVEDAD_INCIDENCIA_CHOICES, default='MEDIA')
- `color` (CharField, max_length=20, default='warning') - Para badges
- `requiere_accion_inmediata` (BooleanField, default=False)
- `activo` (BooleanField, default=True)
- `fecha_creacion` (DateTimeField, auto_now_add=True)

**Meta**:
- `ordering = ['nombre']`
- `verbose_name = "Tipo de Incidencia RHITSO"`
- `verbose_name_plural = "Tipos de Incidencias RHITSO"`

#### 1.5 Crear Modelo `SeguimientoRHITSO` en `servicio_tecnico/models.py`
**Propósito**: Historial completo de cambios de estado RHITSO

**Campos**:
- `orden` (ForeignKey a OrdenServicio, on_delete=CASCADE, related_name='seguimientos_rhitso')
- `estado` (ForeignKey a EstadoRHITSO, on_delete=PROTECT)
- `estado_anterior` (CharField, max_length=100, blank=True) - Para referencia
- `observaciones` (TextField, blank=True)
- `fecha_actualizacion` (DateTimeField, auto_now_add=True)
- `usuario_actualizacion` (ForeignKey a Empleado, null=True, blank=True, on_delete=SET_NULL)
- `tiempo_en_estado_anterior` (IntegerField, null=True, blank=True) - Días
- `notificado_cliente` (BooleanField, default=False)

**Meta**:
- `ordering = ['-fecha_actualizacion']`
- `verbose_name = "Seguimiento RHITSO"`
- `verbose_name_plural = "Seguimientos RHITSO"`
- Índices en: `orden`, `estado`, `fecha_actualizacion`

#### 1.6 Crear Modelo `IncidenciaRHITSO` en `servicio_tecnico/models.py`
**Propósito**: Registro de problemas e incidencias con RHITSO

**Campos**:
- `orden` (ForeignKey a OrdenServicio, on_delete=CASCADE, related_name='incidencias_rhitso')
- `tipo_incidencia` (ForeignKey a TipoIncidenciaRHITSO, on_delete=PROTECT)
- `titulo` (CharField, max_length=255) - Título breve
- `descripcion_detallada` (TextField) - Descripción completa
- `fecha_ocurrencia` (DateTimeField, default=timezone.now)
- `estado` (CharField con ESTADO_INCIDENCIA_CHOICES, default='ABIERTA')
- `impacto_cliente` (CharField con choices: NINGUNO, BAJO, MEDIO, ALTO, default='BAJO')
- `accion_tomada` (TextField, blank=True) - Acciones correctivas
- `resuelto_por` (ForeignKey a Empleado, null=True, blank=True, on_delete=SET_NULL, related_name='incidencias_resueltas')
- `fecha_resolucion` (DateTimeField, null=True, blank=True)
- `usuario_registro` (ForeignKey a Empleado, on_delete=PROTECT, related_name='incidencias_registradas')
- `costo_adicional` (DecimalField, max_digits=10, decimal_places=2, default=0.00)
- `requiere_seguimiento` (BooleanField, default=True)
- `prioridad` (CharField con choices: BAJA, MEDIA, ALTA, URGENTE, default='MEDIA')

**Meta**:
- `ordering = ['-fecha_ocurrencia']`
- `verbose_name = "Incidencia RHITSO"`
- `verbose_name_plural = "Incidencias RHITSO"`
- Índices en: `orden`, `tipo_incidencia`, `estado`

**Métodos**:
- `dias_abierta()` - Property que calcula días desde fecha_ocurrencia hasta ahora o fecha_resolucion
- `esta_resuelta()` - Property que retorna True si estado es RESUELTA o CERRADA

#### 1.7 Crear Modelo `ConfiguracionRHITSO` en `servicio_tecnico/models.py`
**Propósito**: Configuración global del módulo RHITSO

**Campos**:
- `clave` (CharField, max_length=100, unique=True)
- `valor` (TextField, blank=True)
- `descripcion` (TextField, blank=True)
- `tipo` (CharField con choices: STRING, INTEGER, BOOLEAN, JSON, default='STRING')
- `fecha_actualizacion` (DateTimeField, auto_now=True)

**Meta**:
- `verbose_name = "Configuración RHITSO"`
- `verbose_name_plural = "Configuraciones RHITSO"`

**Métodos**:
- Classmethod `obtener(clave, default=None)` que retorna el valor de una configuración

#### 1.8 Agregar Campos Nuevos en `OrdenServicio`
**Ubicación**: Después de la sección RHITSO existente

**Campos a agregar**:
- `estado_rhitso` (CharField, max_length=100, blank=True) - Estado actual RHITSO
- `fecha_envio_rhitso` (DateTimeField, null=True, blank=True)
- `fecha_recepcion_rhitso` (DateTimeField, null=True, blank=True)
- `tecnico_diagnostico` (ForeignKey a Empleado, null=True, blank=True, on_delete=SET_NULL, related_name='diagnosticos_realizados')
- `fecha_diagnostico_sic` (DateTimeField, null=True, blank=True)
- `complejidad_estimada` (CharField con COMPLEJIDAD_CHOICES, default='MEDIA', blank=True)

**Agregar Property**:
- `dias_en_rhitso()` - Calcula días desde fecha_envio_rhitso hasta ahora o fecha_recepcion_rhitso

#### 1.9 Crear Migraciones
- Ejecutar `python manage.py makemigrations`
- **NO aplicar migraciones todavía** - revisar primero el archivo de migración

---

## 🔷 FASE 2: BACKEND - SIGNALS Y LÓGICA DE NEGOCIO ⏳ EN PROCESO

### Objetivos:
Implementar tracking automático y lógica de negocio para el módulo RHITSO

### 🎯 Esta es la fase actual - Lista para implementar

**¿Qué vamos a hacer en esta fase?**
1. Crear archivo `servicio_tecnico/signals.py` para tracking automático
2. Implementar signals que detecten cambios en estado_rhitso
3. Agregar properties y métodos auxiliares en modelos existentes
4. Registrar signals en `apps.py` para que se ejecuten

**Beneficios de implementar signals:**
- Tracking automático de cambios sin modificar vistas
- Historial completo de eventos del sistema
- Alertas automáticas cuando se registran incidencias críticas
- Cálculos automáticos de tiempos entre estados

### Tareas Detalladas:

#### 2.1 Crear Archivo `servicio_tecnico/signals.py` ⬜ PENDIENTE
**Propósito**: Signals para tracking automático de cambios RHITSO

**Signal 1**: `post_save` en OrdenServicio
- **Condición**: Detectar cambio en campo `estado_rhitso`
- **Acción**: 
  - Obtener estado anterior comparando con instancia en DB
  - Si cambió estado_rhitso:
    - Calcular tiempo_en_estado_anterior (días desde último seguimiento)
    - Crear registro en SeguimientoRHITSO con:
      - orden, estado (buscar en EstadoRHITSO), estado_anterior, observaciones automáticas
      - tiempo_en_estado_anterior, usuario_actualizacion='SISTEMA'

**Signal 2**: `post_save` en IncidenciaRHITSO
- **Condición**: Cuando se crea una incidencia CRITICA
- **Acción**:
  - Registrar evento en HistorialOrden con tipo_evento='sistema'
  - Comentario: "⚠️ Incidencia crítica registrada: [título]"

#### 2.2 Registrar Signals en `servicio_tecnico/apps.py`
- En método `ready()` de la clase de configuración de la app
- Importar signals: `from . import signals`

#### 2.3 Agregar Métodos Auxiliares en Modelos

**En OrdenServicio**:
- Property `ultimo_seguimiento_rhitso` que retorna el más reciente SeguimientoRHITSO
- Property `incidencias_abiertas_count` que cuenta incidencias no resueltas
- Property `incidencias_criticas_count` que cuenta incidencias críticas abiertas
- Método `puede_cambiar_estado_rhitso(usuario)` que valida permisos

**En SeguimientoRHITSO**:
- Método `calcular_tiempo_en_estado()` que calcula días hasta siguiente cambio o ahora

**En IncidenciaRHITSO**:
- Método `marcar_como_resuelta(usuario, accion_tomada)` que actualiza estado y campos

---

## 🔷 FASE 3: BACKEND - FORMS PARA RHITSO

### Objetivos:
Crear formularios especializados con validaciones

### Tareas Detalladas:

#### 3.1 Crear `ActualizarEstadoRHITSOForm` en `servicio_tecnico/forms.py`

**Propósito**: Cambiar estado RHITSO de una orden

**Campos**:
- `estado_rhitso` (ChoiceField) - Choices dinámicos desde EstadoRHITSO.objects.filter(activo=True)
- `observaciones` (Textarea) - Comentario obligatorio sobre el cambio
- `notificar_cliente` (BooleanField, initial=False, required=False)

**Widgets**:
- `estado_rhitso`: Select con class 'form-select'
- `observaciones`: Textarea con class 'form-control', rows=4, placeholder

**Validaciones**:
- Clean: Validar que el estado_rhitso existe en EstadoRHITSO
- Clean: Validar que observaciones tenga al menos 10 caracteres

#### 3.2 Crear `RegistrarIncidenciaRHITSOForm` en `servicio_tecnico/forms.py`

**Propósito**: Registrar nueva incidencia con RHITSO

**Campos**:
- `tipo_incidencia` (ModelChoiceField) - Queryset de TipoIncidenciaRHITSO activos
- `titulo` (CharField, max_length=255)
- `descripcion_detallada` (Textarea)
- `impacto_cliente` (ChoiceField) - NINGUNO, BAJO, MEDIO, ALTO
- `prioridad` (ChoiceField) - BAJA, MEDIA, ALTA, URGENTE
- `costo_adicional` (DecimalField, initial=0.00, required=False)

**Widgets**: Todos con Bootstrap classes

**Validaciones**:
- Clean costo_adicional: Validar que sea >= 0
- Clean titulo: Validar longitud mínima 5 caracteres

#### 3.3 Crear `ResolverIncidenciaRHITSOForm` en `servicio_tecnico/forms.py`

**Propósito**: Resolver/cerrar incidencia existente

**Campos**:
- `accion_tomada` (Textarea) - Obligatorio
- `costo_adicional_final` (DecimalField, required=False)

**Widgets**: Bootstrap styling

**Validaciones**:
- Clean accion_tomada: Mínimo 20 caracteres

#### 3.4 Crear `EditarDiagnosticoSICForm` en `servicio_tecnico/forms.py`

**Propósito**: Editar diagnóstico SIC y motivo RHITSO

**Modelo Base**: DetalleEquipo y OrdenServicio (MultiModelForm approach)

**Campos**:
- `diagnostico_sic` (Textarea) - Del modelo DetalleEquipo
- `motivo_rhitso` (ChoiceField) - Del modelo OrdenServicio
- `descripcion_rhitso` (Textarea) - Del modelo OrdenServicio
- `complejidad_estimada` (ChoiceField) - Del modelo OrdenServicio
- `tecnico_diagnostico` (ModelChoiceField) - Empleados activos

**Widgets**: Bootstrap styling

#### 3.5 Crear `SubirImagenRHITSOForm` en `servicio_tecnico/forms.py`

**Propósito**: Subir imagen específica de RHITSO

**Modelo Base**: ImagenOrden

**Campos**:
- `tipo` (ChoiceField) - Filtrado a tipos RHITSO: envio, recepcion, reparacion, autorizacion
- `imagen` (FileField) - Con validación de extensiones
- `descripcion` (CharField, required=False)

---

## 🔷 FASE 4: BACKEND - VISTA PRINCIPAL RHITSO

### Objetivos:
Crear vista principal que muestre todo el panel RHITSO

### Tareas Detalladas:

#### 4.1 Crear Vista `gestion_rhitso` en `servicio_tecnico/views.py`

**Decoradores**: `@login_required`

**Parámetros**: `request`, `orden_id`

**Lógica Principal**:

1. **Obtener Orden y Validar**:
   - `get_object_or_404(OrdenServicio, pk=orden_id)`
   - Validar que `orden.es_candidato_rhitso == True`, sino redirigir con error

2. **Obtener Información del Equipo**:
   - Acceder a `orden.detalle_equipo`
   - Preparar diccionario con: marca, modelo, serie, sucursal, estado general

3. **Obtener Estado RHITSO Actual**:
   - `orden.estado_rhitso`
   - Si existe, buscar en EstadoRHITSO para obtener color y owner
   - Calcular `dias_en_rhitso` usando property del modelo
   - Determinar si hay alerta (más de 7 días configurables)

4. **Obtener Diagnóstico SIC**:
   - Desde `orden.detalle_equipo.diagnostico_sic`
   - `orden.motivo_rhitso` y `orden.descripcion_rhitso`
   - `orden.complejidad_estimada`
   - `orden.tecnico_diagnostico` y `orden.fecha_diagnostico_sic`

5. **Obtener Historial RHITSO**:
   - Cambios de sistema: `orden.seguimientos_rhitso.select_related('estado', 'usuario_actualizacion')`
   - Comentarios manuales: `orden.historial.filter(tipo_evento='comentario').order_by('-fecha_evento')`

6. **Obtener Incidencias**:
   - Todas: `orden.incidencias_rhitso.select_related('tipo_incidencia', 'usuario_registro').order_by('-fecha_ocurrencia')`
   - Estadísticas:
     - Total: count()
     - Críticas abiertas: filter con gravedad CRITICA y estado ABIERTA
     - Abiertas: filter estado in [ABIERTA, EN_REVISION]
     - Resueltas: filter estado in [RESUELTA, CERRADA]

7. **Obtener Galería RHITSO**:
   - `orden.imagenes.select_related('subido_por')`
   - Filtrar por tipo si viene en GET params
   - Tipos válidos: envio, recepcion, reparacion, incidencias (si tiene imagen.incidencia_id), autorizacion

8. **Obtener Último Comentario**:
   - `orden.historial.filter(tipo_evento='comentario').order_by('-fecha_evento').first()`

9. **Preparar Forms**:
   - `form_estado = ActualizarEstadoRHITSOForm()`
   - `form_incidencia = RegistrarIncidenciaRHITSOForm()`
   - `form_diagnostico = EditarDiagnosticoSICForm(instance=orden.detalle_equipo)`
   - `form_imagen = SubirImagenRHITSOForm()`

10. **Preparar Contexto Completo**:
    - orden, detalle_equipo
    - estado_rhitso_info (diccionario con estado, color, owner, dias, alerta)
    - diagnostico_info (diccionario completo)
    - seguimientos_sistema (queryset)
    - comentarios_manuales (queryset)
    - incidencias (queryset), incidencias_stats (diccionario)
    - imagenes_rhitso (queryset filtradas)
    - filtro_imagen_actual (string)
    - forms (los 4 forms)
    - ultimo_comentario

11. **Render Template**: `'servicio_tecnico/rhitso/gestion_rhitso.html'`

---

## 🔷 FASE 5: BACKEND - VISTAS AJAX Y AUXILIARES

### Objetivos:
Crear vistas para acciones AJAX desde el panel RHITSO

### Tareas Detalladas:

#### 5.1 Vista `actualizar_estado_rhitso` (POST, AJAX)

**Decoradores**: `@login_required`, `@require_POST`

**Lógica**:
1. Obtener orden con `get_object_or_404`
2. Validar que `es_candidato_rhitso == True`
3. Instanciar form con `request.POST`
4. Si form válido:
   - Guardar estado_anterior = orden.estado_rhitso
   - Actualizar orden.estado_rhitso con form.cleaned_data
   - Si es el primer cambio a RHITSO, guardar fecha_envio_rhitso
   - Si regresa de RHITSO, guardar fecha_recepcion_rhitso
   - orden.save()
   - Crear SeguimientoRHITSO con usuario_actualizacion=request.user.empleado
   - Retornar JsonResponse con success=True, mensaje
5. Si inválido: JsonResponse con success=False, errores

#### 5.2 Vista `agregar_comentario_rhitso` (POST, AJAX)

**Decoradores**: `@login_required`, `@require_POST`

**Lógica**:
1. Obtener orden
2. Validar comentario en request.POST
3. Crear HistorialOrden con:
   - tipo_evento='comentario'
   - comentario=request.POST['comentario']
   - usuario=request.user.empleado
   - es_sistema=False
4. Retornar JsonResponse con éxito

#### 5.3 Vista `registrar_incidencia_rhitso` (POST, AJAX)

**Decoradores**: `@login_required`, `@require_POST`

**Lógica**:
1. Obtener orden
2. Instanciar form con request.POST
3. Si válido:
   - Crear IncidenciaRHITSO sin guardar (commit=False)
   - Asignar orden e usuario_registro
   - Guardar
   - Si es crítica, crear evento en historial
   - Retornar JsonResponse con éxito, datos de incidencia
4. Si inválido: errores en JsonResponse

#### 5.4 Vista `resolver_incidencia_rhitso` (POST, AJAX)

**Decoradores**: `@login_required`, `@require_POST`

**Parámetros**: `incidencia_id`

**Lógica**:
1. Obtener incidencia con `get_object_or_404`
2. Instanciar form con request.POST
3. Si válido:
   - Usar método del modelo `incidencia.marcar_como_resuelta(usuario, accion)`
   - Retornar JsonResponse con éxito
4. Si inválido: errores

#### 5.5 Vista `editar_diagnostico_sic` (POST)

**Decoradores**: `@login_required`, `@require_POST`

**Parámetros**: `orden_id`

**Lógica**:
1. Obtener orden y detalle_equipo
2. Instanciar form con request.POST, instances de ambos modelos
3. Si válido:
   - Actualizar campos en detalle_equipo y orden
   - Guardar ambos
   - Registrar evento en historial
   - Retornar redirect o JsonResponse
4. Si inválido: re-render o errores

#### 5.6 Vista `eliminar_incidencia_rhitso` (POST, AJAX)

**Decoradores**: `@login_required`, `@require_POST`

**Parámetros**: `incidencia_id`

**Lógica**:
1. Obtener incidencia
2. Validar permisos (solo quien la creó o admin)
3. Guardar orden_id antes de eliminar
4. incidencia.delete()
5. Registrar en historial
6. Retornar JsonResponse con éxito

---

## 🔷 FASE 6: BACKEND - URLS Y ADMIN

### Objetivos:
Registrar todas las URLs y configurar Admin

### Tareas Detalladas:

#### 6.1 Agregar URLs en `servicio_tecnico/urls.py`

**Ubicación**: Después de las URLs de venta mostrador

**URLs a agregar**:
```
# ========================================================================
# GESTIÓN DE RHITSO (Reparaciones Especializadas)
# ========================================================================
path('ordenes/<int:orden_id>/rhitso/', views.gestion_rhitso, name='gestion_rhitso'),
path('ordenes/<int:orden_id>/rhitso/actualizar-estado/', views.actualizar_estado_rhitso, name='actualizar_estado_rhitso'),
path('ordenes/<int:orden_id>/rhitso/agregar-comentario/', views.agregar_comentario_rhitso, name='agregar_comentario_rhitso'),
path('ordenes/<int:orden_id>/rhitso/registrar-incidencia/', views.registrar_incidencia_rhitso, name='registrar_incidencia_rhitso'),
path('rhitso/incidencias/<int:incidencia_id>/resolver/', views.resolver_incidencia_rhitso, name='resolver_incidencia_rhitso'),
path('rhitso/incidencias/<int:incidencia_id>/eliminar/', views.eliminar_incidencia_rhitso, name='eliminar_incidencia_rhitso'),
path('ordenes/<int:orden_id>/rhitso/editar-diagnostico/', views.editar_diagnostico_sic, name='editar_diagnostico_sic'),
```

#### 6.2 Configurar Admin para `EstadoRHITSO`

**Archivo**: `servicio_tecnico/admin.py`

**Configuración**:
- Decorador: `@admin.register(EstadoRHITSO)`
- `list_display = ['estado', 'owner', 'color', 'orden', 'activo']`
- `list_filter = ['activo', 'owner']`
- `search_fields = ['estado', 'descripcion']`
- `list_editable = ['orden', 'activo']`
- `ordering = ['orden']`

#### 6.3 Configurar Admin para `SeguimientoRHITSO`

**Configuración**:
- `list_display = ['orden', 'estado', 'fecha_actualizacion', 'usuario_actualizacion', 'tiempo_en_estado_anterior']`
- `list_filter = ['estado', 'fecha_actualizacion', 'notificado_cliente']`
- `search_fields = ['orden__numero_orden_interno', 'observaciones']`
- `raw_id_fields = ['orden', 'usuario_actualizacion']`
- `date_hierarchy = 'fecha_actualizacion'`
- `readonly_fields = ['fecha_actualizacion']`

#### 6.4 Configurar Admin para `CategoriaDiagnostico`

**Configuración**:
- `list_display = ['nombre', 'requiere_rhitso', 'complejidad_tipica', 'tiempo_estimado_dias', 'activo']`
- `list_filter = ['activo', 'requiere_rhitso', 'complejidad_tipica']`
- `search_fields = ['nombre', 'descripcion']`
- `list_editable = ['activo']`

#### 6.5 Configurar Admin para `TipoIncidenciaRHITSO`

**Configuración**:
- `list_display = ['nombre', 'gravedad', 'requiere_accion_inmediata', 'color', 'activo']`
- `list_filter = ['activo', 'gravedad', 'requiere_accion_inmediata']`
- `search_fields = ['nombre', 'descripcion']`
- `list_editable = ['activo']`

#### 6.6 Configurar Admin para `IncidenciaRHITSO`

**Configuración**:
- `list_display = ['titulo', 'orden', 'tipo_incidencia', 'estado', 'gravedad_display', 'fecha_ocurrencia', 'prioridad']`
- `list_filter = ['estado', 'prioridad', 'impacto_cliente', 'fecha_ocurrencia']`
- `search_fields = ['titulo', 'descripcion_detallada', 'orden__numero_orden_interno']`
- `raw_id_fields = ['orden', 'usuario_registro', 'resuelto_por']`
- `date_hierarchy = 'fecha_ocurrencia'`
- `readonly_fields = ['fecha_ocurrencia', 'usuario_registro']`
- Método personalizado `gravedad_display()` que retorna badge HTML con color

#### 6.7 Configurar Admin para `ConfiguracionRHITSO`

**Configuración**:
- `list_display = ['clave', 'valor', 'tipo', 'fecha_actualizacion']`
- `list_filter = ['tipo']`
- `search_fields = ['clave', 'descripcion']`
- `readonly_fields = ['fecha_actualizacion']`

---

## 🔷 FASE 7: FRONTEND - TEMPLATE PRINCIPAL

### Objetivos:
Crear template completo con estructura y estilos

### Tareas Detalladas:

#### 7.1 Crear Archivo `servicio_tecnico/templates/servicio_tecnico/rhitso/gestion_rhitso.html`

**Estructura Base**:
- Extender de `'base.html'`
- Bloque title: "Seguimiento RHITSO - {{ orden.numero_orden_interno }}"
- Bloque extra_css: Cargar estilos específicos si es necesario

#### 7.2 Implementar Header y Navegación

**Elementos**:
- Título H1: "🔧 Seguimiento RHITSO"
- Subtítulo: Orden {{ orden.numero_orden_interno }}
- Badge de estado actual con color dinámico
- Botón "← Vista General" que redirige a `{% url 'servicio_tecnico:detalle_orden' orden.id %}`
- Última actualización con fecha y hora

#### 7.3 Implementar Sección "Información del Equipo" (Columna Izquierda)

**Card con**:
- Icono: 💻
- Título: "Información del Equipo"
- Lista de items:
  - Marca (con icono 🏷️)
  - Modelo (con icono 💻)
  - Nº Serie (con icono 🔢)
  - Sucursal (con icono 🏢)
  - Estado General (con badge)
  - Orden (con texto destacado)
  - Nº Serie Cargador (si existe)

#### 7.4 Implementar Sección "Estado RHITSO Actual" (Columna Derecha)

**Card con**:
- Icono: ⚙️
- Título: "Estado RHITSO Actual"
- Barra de progreso visual (colores: azul inicio, amarillo medio, verde final)
- Estado actual con badge grande de color dinámico
- Responsable con badge de owner (SIC=info, RHITSO=primary, CLIENTE=warning)
- Fecha de envío
- Días en RHITSO con alerta si > 7 días (badge warning o danger)
- Último comentario (preview con "..." si es largo)
- Botón grande: "Actualizar Estado RHITSO" (abre modal)
- Botón outline: "📧 Enviar correo y formato" (funcionalidad futura)

#### 7.5 Implementar Sección "Diagnóstico SIC"

**Card con**:
- Icono: 🩺
- Título: "Diagnóstico SIC"
- Información:
  - Técnico que realizó diagnóstico
  - Fecha del diagnóstico
  - Diagnóstico completo (en card con borde)
  - Motivo para RHITSO (texto)
  - Descripción detallada del motivo
  - Badge de complejidad estimada con colores:
    - BAJA: success
    - MEDIA: info
    - ALTA: warning
    - CRITICA: danger
- Botón: "✏️ Editar Diagnóstico" (abre modal o form inline)

---

## 🔷 FASE 8: FRONTEND - TIMELINE E HISTORIAL

### Objetivos:
Implementar visualización de historial con tabs

### Tareas Detalladas:

#### 8.1 Crear Sección "Historial de Actividad RHITSO"

**Card con**:
- Icono: 🔄
- Título: "Historial de Actividad RHITSO"
- Tabs de Bootstrap:
  - Tab 1: "⚙️ Cambios Sistema" (activo por default)
  - Tab 2: "💬 Comentarios y Notas"

#### 8.2 Implementar Tab "Cambios Sistema"

**Contenido**:
- Mensaje informativo: "Esta sección muestra cambios automáticos del sistema"
- Timeline vertical con línea azul a la izquierda
- Para cada seguimiento en `seguimientos_sistema`:
  - Punto circular de color según estado
  - Badge con nombre del estado
  - Badge con owner (SIC/RHITSO/CLIENTE)
  - Fecha y hora del cambio
  - Card con:
    - Cambio: "ESTADO_ANTERIOR → ESTADO_NUEVO"
    - Observaciones (si existen)
    - Tiempo en estado anterior (si existe): "X días en estado anterior"
    - Usuario que realizó el cambio
  - Divider entre items

#### 8.3 Implementar Tab "Comentarios y Notas"

**Contenido**:
- Para cada comentario en `comentarios_manuales`:
  - Avatar o icono de usuario
  - Nombre del usuario
  - Fecha y hora
  - Comentario en card con background diferente (amarillo claro)
  - Badge: "👤 Comentario manual del usuario"
- Si no hay comentarios: Mensaje "No hay comentarios manuales registrados"
- Botón flotante: "+ Agregar Comentario" (abre modal)

#### 8.4 Crear Modal "Agregar Comentario"

**Elementos**:
- Título: "💬 Agregar Comentario RHITSO"
- Form con CSRF token
- Campo textarea para comentario (obligatorio, placeholder)
- Contador de caracteres (mínimo 10)
- Botones: "Cancelar" y "Guardar Comentario"
- Submit con AJAX a vista `agregar_comentario_rhitso`
- On success: Recargar tab de comentarios o insertar dinámicamente

---

## 🔷 FASE 9: FRONTEND - INCIDENCIAS Y ESTADÍSTICAS

### Objetivos:
Implementar gestión visual de incidencias

### Tareas Detalladas:

#### 9.1 Crear Sección "Incidencias RHITSO"

**Card con**:
- Icono: ⚠️
- Título: "Incidencias RHITSO"
- Botón: "+ Nueva Incidencia" (top right)

#### 9.2 Implementar Cards de Estadísticas

**Grid de 4 columnas responsive**:

**Card 1: Total**
- Icono: 📋
- Número grande: `{{ incidencias_stats.total }}`
- Texto: "TOTAL"
- Subtexto: "Incidencias registradas"
- Borde superior: azul

**Card 2: Críticas**
- Icono: ⚠️
- Número grande: `{{ incidencias_stats.criticas }}`
- Texto: "CRÍTICAS"
- Subtexto: "Requieren atención inmediata"
- Borde superior: rojo
- Si > 0: Animación de pulso

**Card 3: Abiertas**
- Icono: 📂
- Número grande: `{{ incidencias_stats.abiertas }}`
- Texto: "ABIERTAS"
- Subtexto: "En proceso de resolución"
- Borde superior: naranja

**Card 4: Resueltas**
- Icono: ✅
- Número grande: `{{ incidencias_stats.resueltas }}`
- Texto: "RESUELTAS"
- Subtexto: "Completadas exitosamente"
- Borde superior: verde

#### 9.3 Implementar Listado de Incidencias

**Si hay incidencias** (loop sobre `incidencias`):
- Para cada incidencia:
  - Card con borde coloreado según gravedad
  - Header:
    - Título de la incidencia
    - Badge de tipo de incidencia
    - Badge de estado con color
    - Badge de prioridad
  - Body:
    - Descripción (con "Leer más..." si es muy larga)
    - Información:
      - Fecha de ocurrencia
      - Impacto al cliente (badge)
      - Costo adicional (si > 0)
      - Registrada por: (nombre empleado)
  - Footer (si está resuelta):
    - "Resuelta por: X el DD/MM/YYYY"
    - Acción tomada (preview)
  - Botones:
    - Si está abierta: "✅ Resolver Incidencia"
    - Siempre: "🗑️ Eliminar" (con confirmación)

**Si no hay incidencias**:
- Alert success con icono ✅
- Mensaje: "No hay incidencias registradas para este equipo"

#### 9.4 Crear Modal "Nueva Incidencia"

**Elementos**:
- Título: "⚠️ Registrar Nueva Incidencia"
- Form con `form_incidencia`:
  - Select: Tipo de incidencia (con choices)
  - Input: Título (max 255 chars)
  - Textarea: Descripción detallada (obligatoria)
  - Select: Impacto al cliente
  - Select: Prioridad
  - Input number: Costo adicional (opcional, default 0)
- Botones: "Cancelar" y "Registrar Incidencia"
- Submit con AJAX a `registrar_incidencia_rhitso`
- On success: Recargar sección de incidencias

#### 9.5 Crear Modal "Resolver Incidencia"

**Elementos**:
- Título: "✅ Resolver Incidencia: {{ incidencia.titulo }}"
- Mostrar detalles de la incidencia
- Form con `form_resolver`:
  - Textarea: Acción tomada (obligatorio, min 20 chars)
  - Input number: Costo adicional final (opcional)
- Botones: "Cancelar" y "Marcar como Resuelta"
- Submit con AJAX a `resolver_incidencia_rhitso`
- On success: Actualizar card de incidencia dinámicamente

---

## 🔷 FASE 10: FRONTEND - GALERÍA RHITSO (REUTILIZACIÓN)

### Objetivos:
Reutilizar galería existente de detalle_orden con filtros específicos RHITSO

### ⚡ Concepto de Reutilización:
**NO crear galería nueva desde cero**. En su lugar:
1. La galería ya existe en `detalle_orden.html` y funciona perfectamente
2. Solo necesitamos cambiar el tipo de imagen "Otras" → "Autorización/Pass"
3. En la vista RHITSO, mostramos las MISMAS imágenes de la orden pero con filtros específicos
4. Las imágenes se suben desde detalle_orden normal (proceso existente)
5. En panel RHITSO solo se VISUALIZAN con filtros relevantes

### Tareas Detalladas:

#### 10.1 Modificar `config/constants.py` - TIPO_IMAGEN_CHOICES

**Acción**: Cambiar el choice existente de "Otras"

**ANTES** (en constants.py):
```python
TIPO_IMAGEN_CHOICES = [
    ('ingreso', 'Ingreso - Estado Inicial'),
    ('diagnostico', 'Durante Diagnóstico'),
    ('reparacion', 'Durante Reparación'),
    ('egreso', 'Egreso - Estado Final'),
    ('otras', 'Otras'),  # ← CAMBIAR ESTA LÍNEA
]
```

**DESPUÉS**:
```python
TIPO_IMAGEN_CHOICES = [
    ('ingreso', 'Ingreso - Estado Inicial'),
    ('diagnostico', 'Durante Diagnóstico'),
    ('reparacion', 'Durante Reparación'),
    ('egreso', 'Egreso - Estado Final'),
    ('autorizacion', 'Autorización/Pass - RHITSO'),  # ← NUEVO NOMBRE
]
```

**✅ CONFIRMADO**: 
- **NO hay imágenes existentes** con tipo='otras' en la base de datos
- **NO se requiere data migration**
- Simplemente cambiar el valor en constants.py
- La migración automática de Django solo actualizará el choice disponible

#### 10.2 Actualizar Vista `gestion_rhitso` - Lógica de Galería

**En `servicio_tecnico/views.py`**, en la vista `gestion_rhitso`:

**Modificar sección de "Obtener Galería RHITSO"**:

```
7. **Obtener Galería RHITSO**:
   - `imagenes_rhitso = orden.imagenes.select_related('subido_por').all()`
   - Obtener filtro de GET: `filtro_tipo = request.GET.get('filtro_imagen', 'todas')`
   - Si filtro_tipo != 'todas':
     - Filtrar: `imagenes_rhitso = imagenes_rhitso.filter(tipo=filtro_tipo)`
   - Calcular conteos por tipo para badges de filtros:
     - count_ingreso = orden.imagenes.filter(tipo='ingreso').count()
     - count_diagnostico = orden.imagenes.filter(tipo='diagnostico').count()
     - count_reparacion = orden.imagenes.filter(tipo='reparacion').count()
     - count_egreso = orden.imagenes.filter(tipo='egreso').count()
     - count_autorizacion = orden.imagenes.filter(tipo='autorizacion').count()
   - Agregar a contexto:
     - imagenes_rhitso (queryset filtrado)
     - filtro_imagen_actual (string)
     - conteos_imagenes (diccionario con todos los counts)
```

**NOTA**: NO se necesita crear nueva vista de subida ni modal. Se usa el existente de detalle_orden.

#### 10.3 Crear Sección "Galería RHITSO" en Template

**En `servicio_tecnico/templates/servicio_tecnico/rhitso/gestion_rhitso.html`**:

**Card con**:
- Icono: 🖼️
- Título: "Galería de Imágenes"
- Subtítulo: "Las imágenes se gestionan desde la vista principal de la orden"
- Link al detalle_orden: "➕ Subir más imágenes" (redirige a detalle_orden con anchor #galeria)

#### 10.4 Implementar Filtros Específicos RHITSO

**Botones Pills horizontales** (Bootstrap btn-group):

**IMPORTANTE**: Solo mostrar filtros relevantes para proceso RHITSO

- Botón 1: "📋 Todas" - Link a `?filtro_imagen=todas` 
  - Badge con total de imágenes
  - Clase `active` si filtro_imagen_actual == 'todas'

- Botón 2: "� Ingreso" - Link a `?filtro_imagen=ingreso`
  - Badge: `{{ conteos_imagenes.ingreso }}`
  - Clase `active` si filtro_imagen_actual == 'ingreso'
  - Útil para ver estado inicial del equipo

- Botón 3: "� Diagnóstico" - Link a `?filtro_imagen=diagnostico`
  - Badge: `{{ conteos_imagenes.diagnostico }}`
  - Clase `active` si filtro_imagen_actual == 'diagnostico'
  - Útil para justificar envío a RHITSO

- Botón 4: "🔧 Reparación" - Link a `?filtro_imagen=reparacion`
  - Badge: `{{ conteos_imagenes.reparacion }}`
  - Clase `active` si filtro_imagen_actual == 'reparacion'
  - Imágenes durante proceso RHITSO

- Botón 5: "📤 Egreso" - Link a `?filtro_imagen=egreso`
  - Badge: `{{ conteos_imagenes.egreso }}`
  - Clase `active` si filtro_imagen_actual == 'egreso'
  - Útil para comparar estado post-RHITSO

- Botón 6: "✅ Autorización/Pass" - Link a `?filtro_imagen=autorizacion`
  - Badge: `{{ conteos_imagenes.autorizacion }}`
  - Clase `active` si filtro_imagen_actual == 'autorizacion'
  - Color: success (verde)
  - **MUY IMPORTANTE**: Estas son las imágenes que se enviarán por correo

**Diseño Visual**:
- El botón de "Autorización" debe destacar con color verde
- Agregar tooltip: "Imágenes de autorización/pass para envío por correo"

#### 10.5 Reutilizar Grid de Imágenes de detalle_orden

**Copiar y adaptar el código de galería de `detalle_orden.html`**:

**Si hay imágenes** (`imagenes_rhitso`):
- Grid responsive (col-lg-3, col-md-4, col-sm-6)
- Para cada imagen:
  - Card con imagen:
    - Thumbnail de `imagen.imagen.url` (versión comprimida)
    - Badge overlay top-left: `{{ imagen.get_tipo_display }}`
    - Badge overlay bottom-left: Fecha subida
  - Card body:
    - Descripción (si existe)
    - "Subido por: {{ imagen.subido_por.nombre_completo }}"
  - Card footer:
    - Link: "🔍 Ver Original" → `{% url 'servicio_tecnico:descargar_imagen' imagen.id %}`
    - Botón: "🗑️ Eliminar" → `{% url 'servicio_tecnico:eliminar_imagen' imagen.id %}` (solo admin/técnico)

**Si no hay imágenes del filtro seleccionado**:
- Icono: 🖼️
- Mensaje: "No hay imágenes del tipo {{ filtro_imagen_actual|title }}"
- Botón: "Ver todas las imágenes" → Link a `?filtro_imagen=todas`

#### 10.6 Reutilizar Lightbox Existente

**NO crear lightbox nuevo**. Si ya existe uno en detalle_orden, reutilizar:

- Copiar estructura HTML del lightbox
- Adaptar IDs si hay conflictos
- Mantener misma funcionalidad:
  - Click en imagen abre modal full-screen
  - Navegación entre imágenes (anterior/siguiente)
  - Mostrar información: tipo, fecha, descripción
  - Botón de descarga de original
  - Botón de cerrar

**Alternativa Simple**:
- Solo usar atributo `data-bs-toggle="modal"` de Bootstrap 5
- Modal genérico que carga imagen clickeada

#### 10.7 Mensaje Informativo para Usuario

**Agregar alert en la sección de galería**:

```html
<div class="alert alert-info">
    <i class="bi bi-info-circle"></i>
    <strong>Información:</strong> 
    Las imágenes se gestionan desde la <a href="{% url 'servicio_tecnico:detalle_orden' orden.id %}#galeria">vista principal de la orden</a>. 
    Aquí solo se visualizan con filtros específicos de RHITSO. 
    Las imágenes de tipo "Autorización/Pass" se usarán para el correo a RHITSO.
</div>
```

#### 10.8 Enlace Rápido a Subir Imágenes

**Agregar botón prominente**:

```html
<a href="{% url 'servicio_tecnico:detalle_orden' orden.id %}#galeria" 
   class="btn btn-outline-primary">
    <i class="bi bi-upload"></i> Subir Imágenes desde Vista Principal
</a>
```

**Alternativa con Modal** (opcional):
- Pequeño modal en RHITSO que explica cómo subir imágenes
- Con GIF o captura de pantalla del proceso
- "Ir a Vista Principal" como CTA

---

### ✅ Ventajas de Este Enfoque:

1. **No Duplicación**: No creamos código repetido de galería
2. **Menos Código**: No hay que mantener dos galerías separadas
3. **Consistencia**: La misma galería funciona igual en ambas vistas
4. **Centralización**: Todas las imágenes en un solo lugar
5. **Simplicidad**: Usuario no se confunde con dos sistemas de upload
6. **Mantenibilidad**: Cambios en galería se reflejan automáticamente
7. **Performance**: No cargamos imágenes duplicadas
8. **UX Mejorada**: Flujo más natural y predecible

### ✅ Confirmación - Sin Migración de Datos Necesaria:

**Estado Actual Validado**:
- ✅ Base de datos limpia sin imágenes tipo='otras'
- ✅ Solo requiere cambio en `config/constants.py`
- ✅ NO se necesita data migration
- ✅ NO se necesita SQL de actualización
- ✅ Cambio directo y sin riesgos

**Proceso Simplificado**:
1. Cambiar choice en constants.py (FASE 1.1)
2. Django reconocerá el nuevo valor automáticamente
3. En formularios y selects aparecerá "Autorización/Pass - RHITSO"
4. Listo para usar inmediatamente

---

## 🔷 FASE 11: INTEGRACIÓN - BOTÓN EN DETALLE ORDEN

### Objetivos:
Agregar acceso condicional desde vista de detalle de orden

### Tareas Detalladas:

#### 11.1 Modificar Template `servicio_tecnico/templates/servicio_tecnico/detalle_orden.html`

**Ubicación**: En la sección de información principal de la orden, después del estado

**Agregar Bloque Condicional**:

```django
{% if orden.es_candidato_rhitso %}
<div class="alert alert-info d-flex align-items-center justify-content-between" role="alert">
    <div>
        <h5 class="alert-heading mb-1">🔧 Candidato a RHITSO</h5>
        <p class="mb-0">
            <strong>Motivo:</strong> {{ orden.get_motivo_rhitso_display }}<br>
            {% if orden.estado_rhitso %}
                <strong>Estado RHITSO:</strong> 
                <span class="badge bg-primary">{{ orden.estado_rhitso }}</span>
            {% else %}
                <em class="text-muted">Aún no se ha iniciado proceso RHITSO</em>
            {% endif %}
        </p>
    </div>
    <div>
        <a href="{% url 'servicio_tecnico:gestion_rhitso' orden.id %}" 
           class="btn btn-primary btn-lg">
            <i class="bi bi-gear-fill"></i> Gestión RHITSO
        </a>
    </div>
</div>
{% endif %}
```

**Estilos del Botón**:
- Grande y llamativo
- Color primario (azul)
- Icono de engranaje
- Tooltip: "Ir al panel de seguimiento RHITSO"

---

## 🔷 FASE 12: TESTING Y VALIDACIÓN

### Objetivos:
Probar todo el sistema y validar funcionalidad

### Tareas Detalladas:

#### 12.1 Aplicar Migraciones

1. Revisar archivo de migración generado en FASE 1.9
2. Si todo está correcto: `python manage.py migrate`
3. Verificar que todas las tablas se crearon correctamente
4. Verificar índices en base de datos

#### 12.2 Poblar Datos Iniciales

**Crear Management Command** `poblar_rhitso.py` en `servicio_tecnico/management/commands/`

**Poblar**:
1. **EstadoRHITSO** - Estados del flujo completo (32 estados definidos):

**ESTADOS RESPONSABILIDAD SIC (Owner: SIC)**:
- Estado 1: "CANDIDATO RHITSO" (color=info, descripcion="Equipo marcado como candidato para RHITSO")
- Estado 2: "PENDIENTE DE CONFIRMAR ENVIO A RHITSO" (color=warning, descripcion="Pendiente confirmar el envío a RHITSO")
- Estado 3: "USUARIO ACEPTA ENVIO A RHITSO" (color=success, descripcion="Usuario aceptó el envío a RHITSO")
- Estado 4: "USUARIO NO ACEPTA ENVIO A RHITSO" (color=danger, descripcion="Usuario no acepta el envío a RHITSO")
- Estado 5: "EN ESPERA DE ENTREGAR EQUIPO A RHITSO" (color=warning, descripcion="Equipo pendiente de envío a RHITSO")
- Estado 6: "INCIDENCIA SIC" (color=danger, descripcion="Incidencia o problema reportado en SIC")
- Estado 7: "COTIZACIÓN ENVIADA A SIC" (color=info, descripcion="RHITSO envió cotización a SIC para aprobación")
- Estado 8: "EN ESPERA DE PIEZA POR SIC" (color=warning, descripcion="SIC debe proporcionar pieza o componente")
- Estado 9: "PIEZA DE SIC ENVIADA A RHITSO" (color=warning, descripcion="Cuando se envía la pieza a RHITSO y se requiere que confirmen cuando se reciba")
- Estado 10: "EQUIPO RETORNADO A SIC" (color=success, descripcion="Equipo devuelto a SIC desde RHITSO")
- Estado 11: "EN PRUEBAS SIC" (color=info, descripcion="Equipo en proceso de pruebas en SIC")

**ESTADOS RESPONSABILIDAD RHITSO (Owner: RHITSO)**:
- Estado 12: "EN ESPERA DE CONFIRMAR INGRESO" (color=info, descripcion="RHITSO debe confirmar recepción del equipo")
- Estado 13: "EQUIPO EN RHITSO" (color=primary, descripcion="Equipo recibido y en instalaciones de RHITSO")
- Estado 14: "QR COMPARTIDO (EN DIAGNOSTICO)" (color=info, descripcion="QR del equipo compartido para el seguimiento")
- Estado 15: "DIAGNOSTICO FINAL" (color=primary, descripcion="RHITSO está realizando diagnóstico del equipo")
- Estado 16: "EN PROCESO DE RESPALDO" (color=info, descripcion="Realizando respaldo de información del equipo")
- Estado 17: "EN PROCESO DE REBALLING" (color=primary, descripcion="Proceso de reballing de componentes")
- Estado 18: "EN PRUEBAS (DE DIAGNOSTICO)" (color=info, descripcion="En pruebas (fase de diagnóstico final) en RHITSO")
- Estado 19: "NO APTO PARA REPARACIÓN" (color=danger, descripcion="Equipo determinado como no reparable")
- Estado 20: "EN ESPERA DE PARTES/COMPONENTE" (color=secondary, descripcion="Esperando llegada de componentes para reparación/terminar diagnóstico")
- Estado 21: "EN PRUEBAS (REPARADO)" (color=info, descripcion="Equipo en proceso de pruebas después de reparación")
- Estado 22: "EQUIPO REPARADO" (color=success, descripcion="Reparación completada exitosamente")
- Estado 23: "INCIDENCIA RHITSO" (color=danger, descripcion="Incidencia o problema ocasionado por RHITSO")
- Estado 24: "EN ESPERA DEL RETORNO DEL EQUIPO" (color=warning, descripcion="Esperando el retorno del equipo desde RHITSO")

**ESTADOS RESPONSABILIDAD CLIENTE (Owner: CLIENTE)**:
- Estado 25: "CLIENTE ACEPTA COTIZACIÓN" (color=success, descripcion="Cliente ha aceptado la cotización propuesta")
- Estado 26: "COTIZACIÓN ENVIADA AL CLIENTE" (color=warning, descripcion="Esperando respuesta del cliente sobre cotización")
- Estado 27: "CLIENTE NO ACEPTA COTIZACIÓN" (color=warning, descripcion="Cliente rechazó la cotización de reparación")
- Estado 28: "PETICIÓN AL CLIENTE" (color=warning, descripcion="Solicitud de información o acción al cliente")

**ESTADOS RESPONSABILIDAD COMPRAS (Owner: COMPRAS)**:
- Estado 29: "EN ESPERA DE LA OC" (color=warning, descripcion="Esperando orden de compra para proceder")
- Estado 30: "PIEZA WBP" (color=warning, descripcion="La pieza llega incorrecta")
- Estado 31: "PIEZA DOA" (color=danger, descripcion="Pieza llegó defectuosa (Dead On Arrival)")

**ESTADOS FINALES (Owner: CERRADO)**:
- Estado 32: "CERRADO" (color=dark, descripcion="Proceso RHITSO finalizado completamente")

**NOTA IMPORTANTE**: El campo `owner` debe aceptar también 'COMPRAS' además de SIC, RHITSO, CLIENTE, CERRADO

2. **CategoriaDiagnostico** - 10 categorías del SQL

3. **TipoIncidenciaRHITSO** - 10 tipos del SQL

4. **ConfiguracionRHITSO** - Configuraciones iniciales:
   - tiempo_maximo_sin_actualizacion: 7
   - email_notificaciones_rhitso: ''
   - tiempo_estimado_default: 10
   - activo_notificaciones_automaticas: 1

**Ejecutar**: `python manage.py poblar_rhitso`

#### 12.3 Crear Orden de Prueba RHITSO

1. Ir a admin o vista de crear orden
2. Crear orden nueva
3. Marcar `es_candidato_rhitso = True`
4. Llenar motivo_rhitso y descripcion_rhitso
5. Guardar orden

#### 12.4 Probar Flujo Completo

**Test 1: Acceso Condicional**
- Verificar que botón "Gestión RHITSO" aparece en detalle_orden
- Verificar que NO aparece en órdenes normales

**Test 2: Vista Principal**
- Acceder a panel RHITSO
- Verificar que se muestran todos los datos correctamente
- Verificar que secciones vacías muestran mensajes apropiados

**Test 3: Cambio de Estado**
- Abrir modal de actualizar estado
- Cambiar a "ENVIADO_RHITSO"
- Verificar que se registra en SeguimientoRHITSO
- Verificar que aparece en timeline
- Verificar que fecha_envio_rhitso se guardó

**Test 4: Agregar Comentario**
- Agregar comentario desde modal
- Verificar que aparece en tab "Comentarios y Notas"
- Verificar que se diferencia de cambios de sistema

**Test 5: Registrar Incidencia**
- Crear incidencia de prueba
- Verificar que aparece en listado
- Verificar estadísticas actualizadas
- Si es crítica, verificar evento en historial

**Test 6: Resolver Incidencia**
- Resolver incidencia creada
- Verificar cambio de estado
- Verificar que se guarda acción tomada
- Verificar actualización de estadísticas

**Test 7: Subir Imagen**
- Subir imagen tipo "Autorización"
- Verificar que aparece en galería
- Probar filtros
- Verificar descarga de original

**Test 8: Editar Diagnóstico**
- Editar diagnóstico SIC
- Cambiar complejidad
- Verificar que se guarda correctamente

**Test 9: Signal Automático**
- Cambiar estado_rhitso directamente desde admin
- Verificar que signal crea registro en SeguimientoRHITSO automáticamente

**Test 10: Cálculos de Tiempo**
- Verificar que `dias_en_rhitso` calcula correctamente
- Verificar alerta cuando excede 7 días
- Verificar `tiempo_en_estado_anterior` en timeline

#### 12.5 Validar Permisos

- Probar con diferentes usuarios (admin, técnico, recepción)
- Verificar que `@login_required` funciona
- Verificar que solo usuarios autorizados pueden eliminar incidencias
- Verificar que usuarios sin empleado asociado no causan errores

#### 12.6 Testing Responsive

- Probar en mobile (Chrome DevTools)
- Verificar que cards se apilan correctamente
- Verificar que galería funciona en pantallas pequeñas
- Verificar que modals son accesibles

#### 12.7 Validar Performance

- Usar Django Debug Toolbar
- Verificar que se usan `select_related()` correctamente
- Verificar cantidad de queries en vista principal
- Optimizar si hay N+1 queries

#### 12.8 Documentación Final

**Crear archivo** `README_RHITSO.md` con:
1. Descripción del módulo
2. Flujo de estados RHITSO
3. Cómo usar cada funcionalidad
4. Tipos de incidencias disponibles
5. Configuración de alertas
6. Screenshots de la interfaz
7. Troubleshooting común

---

## 📦 ENTREGABLES FINALES

Al completar todas las fases, deberás tener:

### Archivos Backend Nuevos:
- ✅ `servicio_tecnico/signals.py`
- ✅ 6 modelos nuevos en `models.py`
- ✅ Campos nuevos en `OrdenServicio`
- ✅ 7 forms nuevos en `forms.py`
- ✅ 7 vistas nuevas en `views.py`
- ✅ 7 URLs nuevas en `urls.py`
- ✅ 6 configuraciones de admin en `admin.py`
- ✅ Management command `poblar_rhitso.py`

### Archivos Frontend Nuevos:
- ✅ `servicio_tecnico/templates/servicio_tecnico/rhitso/gestion_rhitso.html`
- ✅ Modificación en `detalle_orden.html`

### Archivos de Configuración:
- ✅ Constantes nuevas en `config/constants.py`
- ✅ Migración aplicada

### Documentación:
- ✅ `README_RHITSO.md`
- ✅ Este plan de implementación completado

---

## 🎓 NOTAS IMPORTANTES PARA PRINCIPIANTES

### Conceptos Clave a Entender:

1. **Signals en Django**: 
   - Son "escuchadores" que se activan automáticamente cuando algo sucede
   - Permiten ejecutar código cuando un modelo se guarda, elimina, etc.
   - Útiles para tracking automático sin modificar cada vista

2. **ForeignKey vs OneToOne**:
   - ForeignKey: Una orden puede tener MUCHOS seguimientos
   - OneToOne: Una orden tiene UN solo detalle de equipo

3. **Related Names**:
   - `related_name='seguimientos_rhitso'` permite hacer `orden.seguimientos_rhitso.all()`
   - Es como crear un "atajo" desde el modelo relacionado

4. **Select Related**:
   - Optimización que carga relaciones de una sola vez
   - Evita hacer queries múltiples (N+1 problem)
   - Usa cuando tienes ForeignKey

5. **AJAX en Django**:
   - Permite actualizar partes de la página sin recargarla
   - Requiere `@require_POST` para seguridad
   - Retorna JsonResponse con datos

6. **Bootstrap 5**:
   - Framework CSS ya incluido en tu proyecto
   - Clases como `card`, `badge`, `btn` ya están estilizadas
   - Responsive por defecto

7. **Template Inheritance**:
   - `{% extends 'base.html' %}` hereda estructura base
   - `{% block content %}` define secciones que pueden cambiar
   - Evita duplicación de código

---

## ⚠️ ADVERTENCIAS Y CONSIDERACIONES

1. **Backup de Base de Datos**: Hacer backup ANTES de aplicar migraciones
2. **Testing en Desarrollo**: Probar TODO en ambiente de desarrollo primero
3. **Migraciones Complejas**: Revisar archivo de migración antes de aplicar
4. **Permisos de Usuario**: Asegurar que `request.user` tiene `empleado` asociado
5. **Manejo de Errores**: Todas las vistas deben manejar excepciones apropiadamente
6. **Validación de Formularios**: Nunca confiar en datos del cliente, validar siempre
7. **CSRF Token**: Incluir en todos los forms POST
8. **SQL Injection**: Usar ORM de Django, nunca raw SQL sin sanitizar

---

## 🚀 ORDEN RECOMENDADO DE EJECUCIÓN

Para una IA que implemente esto:

1. **Backend completo primero** (Fases 1-6)
   - Esto permite probar modelos en Django Admin antes de hacer frontend
   - Si hay errores en modelos, es más fácil corregir antes de templates

2. **Poblar datos iniciales**
   - Management command permite tener datos de prueba
   - Facilita testing de vistas

3. **Frontend después** (Fases 7-11)
   - Con backend funcionando, frontend solo consume datos
   - Más fácil debuggear problemas de templates

4. **Testing al final** (Fase 12)
   - Valida todo el sistema integrado
   - Identifica bugs que no se ven en partes individuales

---

## 📞 TROUBLESHOOTING COMÚN

### Problema: "RelatedObjectDoesNotExist: OrdenServicio has no detalle_equipo"
**Solución**: Verificar que la orden tiene DetalleEquipo asociado con OneToOne

### Problema: "Signal no se ejecuta"
**Solución**: Verificar que signals.py está siendo importado en apps.py

### Problema: "No reverse match for 'gestion_rhitso'"
**Solución**: Verificar namespace en URL: `servicio_tecnico:gestion_rhitso`

### Problema: "Imagen no se sube"
**Solución**: Verificar `enctype="multipart/form-data"` en form de upload

### Problema: "CSRF verification failed"
**Solución**: Incluir `{% csrf_token %}` en todos los forms

---

**FIN DEL PLAN DE IMPLEMENTACIÓN**

Este documento debe usarse como guía paso a paso. Cada fase es independiente y puede implementarse secuencialmente. Al completar todas las fases, tendrás un módulo RHITSO completamente funcional integrado en tu sistema de servicio técnico Django.
