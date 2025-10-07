# 🔄 Cambio Automático de Estados al Subir Imágenes

## 🎯 Objetivo
Automatizar el cambio de estado de las órdenes de servicio técnico cuando se suben imágenes de ingreso o egreso, mejorando el flujo de trabajo y evitando olvidos manuales.

---

## ✨ Funcionalidad Implementada

### 📸 Reglas de Cambio Automático

#### 1. **Imágenes de Ingreso** → Estado: "En Diagnóstico"
**¿Cuándo se activa?**
- Al subir imágenes con tipo "Ingreso - Estado Inicial"

**¿Qué hace?**
- Cambia automáticamente el estado de la orden a **"En Diagnóstico"**
- Solo si el estado actual **NO es ya** "En Diagnóstico"
- Registra el cambio en el historial como evento del sistema

**Lógica:**
```
SI tipo_imagen == 'ingreso' Y estado_actual != 'diagnostico' ENTONCES:
    estado = 'diagnostico'
    Mostrar mensaje informativo
    Registrar en historial
```

**Ejemplo de flujo:**
```
Estado actual: "En Espera"
↓
Usuario sube 3 imágenes de ingreso
↓
✅ Sistema cambia automáticamente a "En Diagnóstico"
↓
ℹ️ Mensaje: "Estado actualizado: En Espera → En Diagnóstico"
```

---

#### 2. **Imágenes de Egreso** → Estado: "Finalizado - Listo para Entrega"
**¿Cuándo se activa?**
- Al subir imágenes con tipo "Egreso - Estado Final"

**¿Qué hace?**
- Cambia automáticamente el estado de la orden a **"Finalizado - Listo para Entrega"**
- Solo si el estado actual **NO es ya** "Finalizado"
- **Marca la fecha de finalización** (`fecha_finalizacion`) con la fecha/hora actual
- Registra el cambio en el historial como evento del sistema

**Lógica:**
```
SI tipo_imagen == 'egreso' Y estado_actual != 'finalizado' ENTONCES:
    estado = 'finalizado'
    fecha_finalizacion = AHORA
    Mostrar mensaje de éxito
    Registrar en historial
```

**Ejemplo de flujo:**
```
Estado actual: "En Reparación"
↓
Usuario sube 5 imágenes de egreso
↓
✅ Sistema cambia automáticamente a "Finalizado"
↓
📅 Marca fecha_finalizacion: 07/10/2025 14:30:00
↓
🎉 Mensaje: "Estado actualizado: En Reparación → Finalizado"
```

---

## 📊 Diagrama de Flujo

```
┌─────────────────────────────┐
│ Usuario sube imágenes       │
└──────────┬──────────────────┘
           │
           ▼
    ┌──────────────┐
    │ Tipo imagen? │
    └──────┬───────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌─────────┐   ┌─────────┐
│ Ingreso │   │ Egreso  │
└────┬────┘   └────┬────┘
     │             │
     ▼             ▼
┌──────────┐  ┌──────────┐
│Estado ya │  │Estado ya │
│es diag.? │  │es final.?│
└────┬─────┘  └────┬─────┘
     │ No          │ No
     ▼             ▼
┌──────────┐  ┌──────────┐
│Cambiar a │  │Cambiar a │
│Diagnóst. │  │Finalizado│
└────┬─────┘  └────┬─────┘
     │             │
     └──────┬──────┘
            │
            ▼
    ┌───────────────┐
    │Guardar cambio │
    │+ Historial    │
    └───────────────┘
```

---

## 💻 Código Implementado

### Ubicación
**Archivo**: `servicio_tecnico/views.py`  
**Función**: `detalle_orden()`  
**Sección**: Formulario 6 - Subir Imágenes (líneas ~607-677)

### Código Completo

```python
# ================================================================
# CAMBIO AUTOMÁTICO DE ESTADO SEGÚN TIPO DE IMAGEN
# ================================================================
estado_anterior = orden.estado
cambio_realizado = False

# Si se suben imágenes de INGRESO → Cambiar a "En Diagnóstico"
if tipo_imagen == 'ingreso' and estado_anterior != 'diagnostico':
    orden.estado = 'diagnostico'
    cambio_realizado = True
    
    messages.info(
        request,
        f'ℹ️ Estado actualizado automáticamente: '
        f'{dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → '
        f'En Diagnóstico (imágenes de ingreso cargadas)'
    )
    
    # Registrar cambio automático en historial
    HistorialOrden.objects.create(
        orden=orden,
        tipo_evento='estado',
        comentario=f'Cambio automático de estado: {dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → En Diagnóstico (imágenes de ingreso cargadas)',
        usuario=empleado_actual,
        es_sistema=True
    )

# Si se suben imágenes de EGRESO → Cambiar a "Finalizado - Listo para Entrega"
elif tipo_imagen == 'egreso' and estado_anterior != 'finalizado':
    orden.estado = 'finalizado'
    orden.fecha_finalizacion = timezone.now()
    cambio_realizado = True
    
    messages.success(
        request,
        f'🎉 Estado actualizado automáticamente: '
        f'{dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → '
        f'Finalizado - Listo para Entrega (imágenes de egreso cargadas)'
    )
    
    # Registrar cambio automático en historial
    HistorialOrden.objects.create(
        orden=orden,
        tipo_evento='estado',
        comentario=f'Cambio automático de estado: {dict(ESTADO_ORDEN_CHOICES).get(estado_anterior)} → Finalizado - Listo para Entrega (imágenes de egreso cargadas)',
        usuario=empleado_actual,
        es_sistema=True
    )

# Guardar cambios si hubo actualización de estado
if cambio_realizado:
    orden.save()
```

---

## 📝 Explicación para Principiantes

### ¿Por qué esto es útil?

**Problema anterior:**
1. Usuario sube imágenes de ingreso
2. Olvida cambiar el estado manualmente
3. La orden queda en "En Espera" aunque ya está en diagnóstico
4. Genera confusión en el seguimiento

**Solución actual:**
1. Usuario sube imágenes de ingreso
2. ✅ **Sistema cambia automáticamente** a "En Diagnóstico"
3. ✅ **Registra el cambio** en el historial
4. ✅ **Notifica al usuario** con mensaje claro

### ¿Cómo funciona el código?

#### 1. **Guardar el estado anterior**
```python
estado_anterior = orden.estado
```
**Explicación**: Guardamos el estado actual antes de cambiarlo para poder mostrarlo en los mensajes.

#### 2. **Verificar el tipo de imagen**
```python
if tipo_imagen == 'ingreso' and estado_anterior != 'diagnostico':
```
**Explicación**: 
- `tipo_imagen == 'ingreso'`: Si el usuario seleccionó "Ingreso - Estado Inicial"
- `and estado_anterior != 'diagnostico'`: Y el estado NO es ya "En Diagnóstico"
- Solo entonces hacemos el cambio (evita cambios innecesarios)

#### 3. **Cambiar el estado**
```python
orden.estado = 'diagnostico'
cambio_realizado = True
```
**Explicación**: 
- Actualizamos el campo `estado` del objeto `orden`
- Marcamos `cambio_realizado = True` para saber que hubo cambio

#### 4. **Mostrar mensaje al usuario**
```python
messages.info(request, '...')
```
**Explicación**: 
- `messages.info()`: Muestra un mensaje azul informativo
- `messages.success()`: Muestra un mensaje verde de éxito
- El usuario ve estos mensajes en la página después de la recarga

#### 5. **Registrar en historial**
```python
HistorialOrden.objects.create(
    orden=orden,
    tipo_evento='estado',
    comentario='...',
    usuario=empleado_actual,
    es_sistema=True
)
```
**Explicación**: 
- Crea un nuevo registro en el historial de la orden
- `tipo_evento='estado'`: Indica que fue un cambio de estado
- `es_sistema=True`: Marca que fue automático (no manual)
- Aparecerá en la timeline del historial de la orden

#### 6. **Guardar cambios**
```python
if cambio_realizado:
    orden.save()
```
**Explicación**: 
- Solo guarda en la base de datos si hubo cambios
- `orden.save()`: Persiste los cambios del objeto en la base de datos

---

## 🔍 Casos de Uso Reales

### Caso 1: Ingreso Normal
```
Situación: Orden recién creada
Estado inicial: "En Espera"
Acción: Subir 3 imágenes de ingreso

Resultado:
✅ Imágenes guardadas
✅ Estado → "En Diagnóstico"
✅ Historial: "Cambio automático de estado: En Espera → En Diagnóstico"
ℹ️ Mensaje al usuario: "Estado actualizado automáticamente"
```

### Caso 2: Finalización de Reparación
```
Situación: Orden reparada
Estado inicial: "En Reparación"
Acción: Subir 5 imágenes de egreso

Resultado:
✅ Imágenes guardadas
✅ Estado → "Finalizado - Listo para Entrega"
✅ fecha_finalizacion = 07/10/2025 14:30:00
✅ Historial: "Cambio automático de estado: En Reparación → Finalizado"
🎉 Mensaje al usuario: "Estado actualizado automáticamente"
```

### Caso 3: Imágenes Adicionales (Sin Cambio)
```
Situación: Ya se habían subido imágenes antes
Estado inicial: "En Diagnóstico"
Acción: Subir 2 imágenes más de ingreso

Resultado:
✅ Imágenes guardadas
❌ Estado NO cambia (ya está en "En Diagnóstico")
ℹ️ Solo mensaje: "2 imagen(es) subida(s) correctamente"
```

### Caso 4: Otras Imágenes (Sin Cambio)
```
Situación: Orden en reparación
Estado inicial: "En Reparación"
Acción: Subir 3 imágenes de diagnóstico o reparación

Resultado:
✅ Imágenes guardadas
❌ Estado NO cambia (solo aplica a ingreso/egreso)
ℹ️ Solo mensaje: "3 imagen(es) subida(s) correctamente"
```

---

## 🎨 Mensajes al Usuario

### Mensajes Informativos (Azul - `messages.info()`)
```
ℹ️ Estado actualizado automáticamente: En Espera → En Diagnóstico (imágenes de ingreso cargadas)
```
**Cuándo**: Al subir imágenes de ingreso

### Mensajes de Éxito (Verde - `messages.success()`)
```
✅ 3 imagen(es) subida(s) correctamente.
🎉 Estado actualizado automáticamente: En Reparación → Finalizado - Listo para Entrega (imágenes de egreso cargadas)
```
**Cuándo**: 
- Siempre al subir imágenes exitosamente
- Adicionalmente cuando se suben imágenes de egreso

---

## 📊 Registro en Historial

### Formato del Historial

**Para cambios automáticos:**
```
Tipo: estado
Comentario: "Cambio automático de estado: [Estado Anterior] → [Estado Nuevo] (imágenes de [tipo] cargadas)"
Usuario: El empleado que subió las imágenes
Es Sistema: true
```

**Ejemplo visualizado en la interfaz:**
```
┌─────────────────────────────────────────────┐
│ 📋 HISTORIAL AUTOMÁTICO                     │
├─────────────────────────────────────────────┤
│ 🔄 Estado                                    │
│ Cambio automático de estado:                │
│ En Reparación → Finalizado - Listo para     │
│ Entrega (imágenes de egreso cargadas)       │
│                                              │
│ 👤 Juan Pérez                                │
│ 📅 07/10/2025 14:30                          │
└─────────────────────────────────────────────┘
```

---

## 🚀 Beneficios de la Implementación

### Para los Técnicos
- ✅ **Menos pasos manuales**: No necesitan recordar cambiar el estado
- ✅ **Menos errores**: Evita olvidos que afectan el seguimiento
- ✅ **Workflow natural**: El sistema refleja automáticamente el progreso real

### Para los Supervisores
- ✅ **Mejor trazabilidad**: Cada cambio queda registrado
- ✅ **Estados precisos**: Las órdenes reflejan su estado real
- ✅ **Reportes exactos**: Los KPIs y métricas son más confiables

### Para el Sistema
- ✅ **Integridad de datos**: Los estados siempre son coherentes
- ✅ **Historial completo**: Todo cambio está documentado
- ✅ **Automatización inteligente**: Reduce intervención manual

---

## ⚙️ Configuración Técnica

### Dependencias Necesarias
```python
from django.utils import timezone
from config.constants import ESTADO_ORDEN_CHOICES
```

### Campos del Modelo Afectados
- `OrdenServicio.estado` (CharField)
- `OrdenServicio.fecha_finalizacion` (DateTimeField)
- `HistorialOrden` (nuevo registro)

### Estados Involucrados
```python
ESTADO_ORDEN_CHOICES = [
    ('espera', 'En Espera'),
    ('diagnostico', 'En Diagnóstico'),      # ← Ingreso
    ('reparacion', 'En Reparación'),
    ('finalizado', 'Finalizado - Listo para Entrega'),  # ← Egreso
    # ... otros estados
]
```

---

## 🧪 Casos de Prueba

### Prueba 1: Ingreso desde Espera
```
Estado inicial: espera
Tipo imagen: ingreso
Resultado esperado: estado = diagnostico
```

### Prueba 2: Egreso desde Reparación
```
Estado inicial: reparacion
Tipo imagen: egreso
Resultado esperado: estado = finalizado, fecha_finalizacion != null
```

### Prueba 3: Ingreso cuando ya está en Diagnóstico
```
Estado inicial: diagnostico
Tipo imagen: ingreso
Resultado esperado: estado = diagnostico (sin cambio)
```

### Prueba 4: Otros tipos de imagen
```
Estado inicial: cualquiera
Tipo imagen: diagnostico/reparacion/otras
Resultado esperado: Sin cambio de estado
```

### Prueba 5: Historial registrado
```
Acción: Subir imágenes de ingreso
Verificar: Nuevo registro en HistorialOrden con es_sistema=True
```

---

## 🐛 Solución de Problemas

### El estado no cambia
**Posibles causas:**
1. Ya estaba en el estado objetivo (diagnóstico o finalizado)
2. El tipo de imagen no es ingreso ni egreso
3. Error en el guardado (`orden.save()`)

**Verificar:**
- Console del navegador por errores
- Logs del servidor de Django
- Estado anterior de la orden

### No aparece en el historial
**Posibles causas:**
1. Error al crear el registro de historial
2. Falta el empleado actual

**Verificar:**
- `empleado_actual` está definido
- Tabla `HistorialOrden` existe
- Permisos de base de datos

### Fecha de finalización no se guarda
**Posibles causas:**
1. Error en `timezone.now()`
2. Campo `fecha_finalizacion` no acepta valores

**Verificar:**
- Import de `timezone` correcto
- Campo en el modelo acepta null

---

## 📚 Recursos Relacionados

### Archivos Modificados
- ✅ `servicio_tecnico/views.py` (líneas ~13, ~607-677)
- ✅ Documentación: Este archivo

### Modelos Relacionados
- `OrdenServicio` → Estado y fecha de finalización
- `HistorialOrden` → Registro de cambios

### Constantes Utilizadas
- `ESTADO_ORDEN_CHOICES` → Estados disponibles
- `TIPO_IMAGEN_CHOICES` → Tipos de imagen

---

## 🔮 Mejoras Futuras Posibles

1. **Notificaciones push** cuando cambia el estado
2. **Validaciones adicionales** antes de cambiar estado
3. **Webhooks** para integrar con otros sistemas
4. **Dashboard en tiempo real** mostrando cambios de estado
5. **Reportes automáticos** de tiempo en cada estado
6. **Alertas** si una orden está mucho tiempo en un estado

---

## ✅ Checklist de Funcionalidad

- [x] Cambio automático para imágenes de ingreso
- [x] Cambio automático para imágenes de egreso
- [x] Verificación de estado previo (evitar duplicados)
- [x] Registro en historial con `es_sistema=True`
- [x] Mensajes informativos al usuario
- [x] Actualización de `fecha_finalizacion` para egreso
- [x] Guardado correcto en base de datos
- [x] Import de constantes necesarias
- [x] Documentación completa
- [x] Manejo de casos edge (estado ya correcto)

---

**Fecha de implementación**: 7 de octubre de 2025  
**Versión**: 1.0  
**Estado**: ✅ Implementado y documentado  
**Autor**: Sistema de Gestión de Servicio Técnico
