# 🎯 Sistema de Atribuibilidad y Gestión de Estados - Score Card

## 📋 Resumen de Implementación

### Fecha: 2 de Octubre, 2025
### Funcionalidades Agregadas: Gestión de Atribuibilidad y Estados de Incidencias

---

## ✨ Nuevas Funcionalidades

### 1️⃣ **Campo "Atribuible al Técnico"**

#### ¿Qué es?
Sistema para marcar incidencias que **NO son responsabilidad del técnico**, permitiendo llevar registro completo sin afectar injustamente el Score Card.

#### Casos de Uso:
- Cliente rechazó piezas que no fueron reemplazadas
- Falla de componente sin relación con el servicio realizado
- Problema preexistente no detectado en recepción
- Error en diagnóstico inicial por terceros

#### Campos Agregados al Modelo `Incidencia`:
```python
es_atribuible = BooleanField(default=True)
justificacion_no_atribuible = TextField(blank=True)
fecha_marcado_no_atribuible = DateTimeField(null=True, blank=True)
marcado_no_atribuible_por = ForeignKey(Empleado)
```

---

### 2️⃣ **Gestión de Estados desde Detalle**

#### Nuevas Acciones Rápidas:
1. **Cambiar Estado** - Modificar estado sin editar toda la incidencia
2. **Marcar como NO Atribuible** - Con justificación obligatoria
3. **Cerrar Incidencia** - Con formulario de cierre y conclusiones
4. **Enviar Notificación Manual** - A destinatarios específicos

#### Estados Disponibles:
- ✅ Abierta
- 🔍 En Revisión
- ✅ Cerrada
- 🔄 Reincidente

---

### 3️⃣ **Sistema de Notificaciones Mejorado**

#### Tipos de Notificaciones Automáticas:

| Acción | Tipo | Destinatario | Contenido |
|--------|------|--------------|-----------|
| Marcar NO Atribuible | `no_atribuible` | Técnico | Explicación de por qué no se le atribuye |
| Cerrar Incidencia Normal | `cierre` | Técnico | Confirmación de cierre y acciones tomadas |
| Cerrar NO Atribuible | `cierre_no_atribuible` | Técnico | Conclusión final (informativo) |
| Notificación Manual | `manual` | Varios | Mensaje personalizado |

#### Campos Agregados al Modelo `NotificacionIncidencia`:
```python
tipo_notificacion = CharField(choices=TIPO_NOTIFICACION_CHOICES)
destinatarios_json = TextField(default='[]')
enviado_exitoso = BooleanField(default=True)
```

---

## 🗂️ Archivos Modificados/Creados

### **Modelos**
- ✅ `scorecard/models.py` - Campos de atribuibilidad agregados

### **Formularios**
- ✅ `scorecard/forms.py` - 3 nuevos formularios:
  - `CambiarEstadoIncidenciaForm`
  - `MarcarNoAtribuibleForm`
  - `CerrarIncidenciaForm`

### **Vistas**
- ✅ `scorecard/views.py` - 3 nuevas vistas:
  - `cambiar_estado_incidencia()`
  - `marcar_no_atribuible()`
  - `cerrar_incidencia()`

### **Emails**
- ✅ `scorecard/emails.py` - 2 nuevas funciones:
  - `enviar_notificacion_no_atribuible()`
  - `enviar_notificacion_cierre_incidencia()`

### **URLs**
- ✅ `scorecard/urls.py` - 3 nuevas rutas agregadas

### **Templates HTML**
- ✅ `scorecard/templates/scorecard/cambiar_estado.html`
- ✅ `scorecard/templates/scorecard/marcar_no_atribuible.html`
- ✅ `scorecard/templates/scorecard/cerrar_incidencia.html`
- ✅ `scorecard/templates/scorecard/detalle_incidencia.html` - Actualizado con botones de acción

### **Templates de Email**
- ✅ `scorecard/templates/scorecard/emails/no_atribuible.html`
- ✅ `scorecard/templates/scorecard/emails/cierre_incidencia.html`
- ✅ `scorecard/templates/scorecard/emails/cierre_no_atribuible.html`

### **Migraciones**
- ✅ `scorecard/migrations/0005_atribuibilidad_y_notificaciones.py`

---

## 🔄 Flujo de Trabajo Completo

### **Escenario 1: Incidencia Normal (Atribuible)**
```
1. Crear incidencia → Estado: Abierta
2. [Opcional] Cambiar a "En Revisión"
3. Cerrar incidencia → Notificación automática al técnico
4. SÍ cuenta en Score Card del técnico
```

### **Escenario 2: Incidencia NO Atribuible**
```
1. Crear incidencia → Estado: Abierta
2. Marcar como "NO Atribuible" (requiere justificación)
   → Notificación automática: "No se te atribuirá porque..."
3. [Opcional] Cambiar estados
4. Cerrar incidencia
   → Notificación automática: "Conclusión final (informativa)"
5. NO cuenta en Score Card del técnico
```

---

## 🎨 Interfaz de Usuario

### **Detalle de Incidencia - Nuevos Botones**

```
┌─────────────────────────────────────────────────────────────┐
│ 📋 INCIDENCIA INC-2025-0001 [Badge: No Atribuible]        │
├─────────────────────────────────────────────────────────────┤
│ ⚡ ACCIONES RÁPIDAS                                         │
│                                                             │
│ [Cambiar Estado] [Marcar NO Atribuible] [Cerrar] [Enviar] │
│                                                             │
│ ℹ️ Justificación NO Atribuible:                            │
│ "Cliente rechazó pieza que no fue reemplazada..."          │
│ Marcado por: Juan Pérez | 02/10/2025 14:30                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📧 Ejemplos de Emails

### **Email 1: Marcada como NO Atribuible**
- **Asunto:** `[INFO] INC-2025-0001 - Incidencia NO Atribuible`
- **Color:** Azul info
- **Mensaje:** Explica que NO afecta scorecard + justificación
- **Badge:** "NO ATRIBUIBLE"

### **Email 2: Cierre Normal**
- **Asunto:** `[CERRADA] INC-2025-0001 - Incidencia Cerrada`
- **Color:** Verde success
- **Mensaje:** Confirmación + acciones tomadas + causa raíz
- **Badge:** "CERRADA"

### **Email 3: Cierre NO Atribuible**
- **Asunto:** `[INFO] INC-2025-0001 - Conclusión Final (No Atribuible)`
- **Color:** Azul info
- **Mensaje:** Conclusión para conocimiento + recordatorio de no impacto
- **Badge:** "CERRADA - NO ATRIBUIBLE"

---

## 🔐 Validaciones Implementadas

### **Marcar como NO Atribuible**
- ✅ Solo si está marcada como atribuible (evita duplicados)
- ✅ Justificación obligatoria (mínimo 20 caracteres)
- ✅ Registro de quién y cuándo marcó
- ✅ Notificación automática al técnico

### **Cerrar Incidencia**
- ✅ Solo si NO está ya cerrada
- ✅ Acciones correctivas obligatorias (mínimo 20 caracteres)
- ✅ Causa raíz opcional pero recomendada
- ✅ Notificación automática diferenciada (atribuible vs no atribuible)

### **Cambiar Estado**
- ✅ Permite cambiar entre cualquier estado
- ✅ Notas opcionales sobre el cambio
- ✅ Solo notifica automáticamente si se cierra
- ✅ Registra cambios en historial

---

## 🎯 Beneficios del Sistema

### **Para Técnicos:**
- ✅ **Justicia:** No penalizados por problemas ajenos
- ✅ **Transparencia:** Saben por qué no se les atribuye
- ✅ **Comunicación:** Reciben conclusión final para aprendizaje

### **Para Jefes de Calidad:**
- ✅ **Trazabilidad:** Todo queda registrado
- ✅ **Flexibilidad:** Gestión rápida de estados
- ✅ **Análisis:** Pueden analizar incidencias no atribuibles por separado

### **Para el Sistema:**
- ✅ **Integridad:** Registro completo sin afectar métricas injustamente
- ✅ **Auditabilidad:** Historial de cambios y justificaciones
- ✅ **Reportes precisos:** Métricas reales de desempeño

---

## 📊 Reportes (Próximas Modificaciones)

**Nota:** Los reportes y dashboards necesitarán actualización para:
- Filtrar por `es_atribuible=True` al calcular métricas de técnicos
- Agregar sección de "Incidencias No Atribuibles" para análisis
- Mostrar indicadores visuales (badges) en todas las listas

---

## 🚀 Cómo Usar

### **Paso 1: Acceder al Detalle de una Incidencia**
```
Score Card → Lista de Incidencias → Clic en Folio
```

### **Paso 2: Usar Acciones Rápidas**
```
Botones en la parte superior del detalle:
- [Cambiar Estado] - Para actualizar sin editar todo
- [Marcar NO Atribuible] - Requiere justificación
- [Cerrar Incidencia] - Formulario de cierre
- [Enviar Notificación] - Personalizada
```

### **Paso 3: Completar Formularios**
- Todos tienen validación
- Campos obligatorios marcados con (*)
- Ayuda contextual en cada campo

---

## ⚠️ Importante

### **Notificaciones Automáticas SOLO en:**
1. ✅ Marcar como NO atribuible
2. ✅ Cerrar incidencia (atribuible o no)

### **SIN Notificación Automática:**
- ❌ Cambiar a "En Revisión"
- ❌ Cambiar a "Reincidente"
- ❌ Reabrir incidencia
- ℹ️ Para estos casos, usar "Enviar Notificación Manual" si se requiere

---

## 🔧 Configuración Requerida

### **Variables de Email (settings.py)**
```python
DEFAULT_FROM_EMAIL = 'scorecard@empresa.com'
JEFE_CALIDAD_NOMBRE = 'Nombre del Jefe'
JEFE_CALIDAD_EMAIL = 'jefe@empresa.com'
```

### **Empleados con Email**
- Asegurarse de que los técnicos tengan email registrado
- El sistema valida antes de enviar notificaciones

---

## 📝 Próximos Pasos (Recomendados)

1. **Actualizar Dashboard/Reportes** para filtrar por atribuibilidad
2. **Agregar filtros** en lista de incidencias (Atribuibles / No Atribuibles)
3. **Crear reporte** específico de incidencias no atribuibles
4. **Agregar permisos** si se requiere control de acceso
5. **Implementar búsqueda** por justificación en no atribuibles

---

## ✅ Estado de Implementación

- ✅ **Modelos:** Completos y migrados
- ✅ **Formularios:** Creados con validaciones
- ✅ **Vistas:** Implementadas y probadas (lógica)
- ✅ **Templates:** Diseñados con Bootstrap
- ✅ **Emails:** Templates HTML responsive
- ✅ **URLs:** Configuradas
- ✅ **Migración:** Aplicada exitosamente

**Estado:** ✅ **LISTO PARA USAR**

---

## 🐛 Testing Recomendado

### **Test 1: Marcar NO Atribuible**
1. Crear incidencia de prueba
2. Marcar como NO atribuible con justificación
3. Verificar email recibido
4. Confirmar badge en detalle

### **Test 2: Cerrar Normal**
1. Crear incidencia atribuible
2. Cerrar con acciones correctivas
3. Verificar email de cierre normal

### **Test 3: Cerrar NO Atribuible**
1. Crear incidencia
2. Marcar como NO atribuible
3. Cerrar incidencia
4. Verificar email de conclusión final

### **Test 4: Cambios de Estado**
1. Cambiar entre diferentes estados
2. Verificar que NO envía notificaciones
3. Confirmar que registra cambios

---

## 📞 Soporte

Para dudas o problemas:
1. Revisar logs de Django
2. Verificar configuración de email
3. Confirmar que empleados tienen email registrado
4. Revisar mensajes de error en formularios

---

**Documento creado:** 2 de Octubre, 2025
**Versión:** 1.0
**Sistema:** Django 5.2.5 - Score Card
