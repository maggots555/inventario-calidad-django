# 📅 CAMBIO: FECHAS RHITSO AHORA SON EXCLUSIVAMENTE MANUALES

**Fecha de implementación:** 13 de octubre de 2025  
**Motivo:** Mayor control y precisión en el registro de fechas de eventos RHITSO

---

## 🎯 RESUMEN DEL CAMBIO

Las fechas de envío a RHITSO (`fecha_envio_rhitso`) y retorno a SIC (`fecha_recepcion_rhitso`) ya **NO se registran automáticamente** al cambiar el estado RHITSO. Ahora son **exclusivamente manuales**.

### ¿Qué significa esto?

**ANTES:** 
- Al cambiar el estado a "ENVIADO A RHITSO" → Sistema registraba `fecha_envio_rhitso` automáticamente
- Al cambiar el estado a "EQUIPO RETORNADO A SIC" → Sistema registraba `fecha_recepcion_rhitso` automáticamente

**AHORA:**
- El usuario DEBE ingresar manualmente las fechas en el formulario cuando ocurran los eventos reales
- NO hay detección automática basada en estados
- Mayor precisión: se registra la fecha exacta del evento físico, no la fecha del cambio de estado

---

## 📂 MODELO: OrdenServicio

Las fechas están definidas en el modelo **`OrdenServicio`** en `servicio_tecnico/models.py`:

```python
class OrdenServicio(models.Model):
    """
    Modelo central que representa una orden de servicio técnico.
    """
    
    # ... otros campos ...
    
    # RHITSO - Campos adicionales del módulo de seguimiento especializado
    estado_rhitso = models.CharField(
        max_length=100,
        blank=True,
        help_text="Estado actual en el proceso RHITSO"
    )
    
    fecha_envio_rhitso = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de envío del equipo a RHITSO"
    )
    
    fecha_recepcion_rhitso = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de recepción del equipo desde RHITSO"
    )
```

**Ubicación:** `servicio_tecnico/models.py`, líneas 166-175

---

## 🔧 ARCHIVOS MODIFICADOS

### 1. **servicio_tecnico/views.py**
Vista: `actualizar_estado_rhitso(request, orden_id)`

**Cambio realizado (líneas ~3526-3548):**

```python
# ANTES (CON DETECCIÓN AUTOMÁTICA):
# Si el usuario proporcionó una fecha de envío, usarla
if fecha_envio:
    orden.fecha_envio_rhitso = fecha_envio
# Si no, detectar automáticamente si es un estado de envío
elif 'ENVIADO' in nuevo_estado.upper() or 'ACEPTA ENVIO' in nuevo_estado.upper():
    if not orden.fecha_envio_rhitso:
        orden.fecha_envio_rhitso = timezone.now()

# AHORA (SOLO MANUAL):
# Si el usuario proporcionó una fecha de envío, usarla
if fecha_envio:
    orden.fecha_envio_rhitso = fecha_envio
```

**Explicación del cambio:**
- ❌ **Eliminado:** Toda la lógica `elif` que detectaba palabras clave en el estado
- ❌ **Eliminado:** Registro automático de `timezone.now()` 
- ✅ **Mantenido:** Solo se registra si el usuario proporciona explícitamente la fecha

---

### 2. **servicio_tecnico/forms.py**
Formulario: `ActualizarEstadoRHITSOForm`

**Cambio realizado (líneas ~2148-2171):**

```python
# Labels actualizados para claridad
fecha_envio_rhitso = forms.DateTimeField(
    label="Fecha de Envío a RHITSO (Manual)",  # ← ANTES: "Fecha de Envío a RHITSO"
    help_text="⚠️ Ingresa manualmente la fecha y hora exacta cuando el equipo sea enviado físicamente a RHITSO. NO se registra automáticamente.",
    required=False,
    ...
)

fecha_recepcion_rhitso = forms.DateTimeField(
    label="Fecha de Retorno a SIC (Manual)",  # ← ANTES: "Fecha de Retorno a SIC"
    help_text="⚠️ Ingresa manualmente la fecha y hora exacta cuando el equipo regrese de RHITSO a SIC. NO se registra automáticamente.",
    required=False,
    ...
)
```

**Explicación del cambio:**
- ✅ Labels incluyen "(Manual)" para claridad visual
- ✅ Textos de ayuda explican que NO hay registro automático
- ⚠️ Advertencia visible con emoji para llamar la atención

---

### 3. **servicio_tecnico/templates/servicio_tecnico/rhitso/gestion_rhitso.html**
Template: Formulario de actualización de estado RHITSO

**Cambio realizado (líneas ~312-348):**

```html
<!-- ANTES: Sin alerta explicativa -->
<div class="row">
    <div class="col-md-6 mb-3">
        {{ form_estado.fecha_envio_rhitso.label_tag }}
        {{ form_estado.fecha_envio_rhitso }}
        ...
    </div>
</div>

<!-- AHORA: Con alerta informativa -->
<div class="alert alert-info border-start border-info border-4 mb-3">
    <i class="bi bi-info-circle"></i>
    <strong>Importante:</strong> Las fechas de envío y recepción son <strong>exclusivamente manuales</strong>. 
    Ingresa la fecha exacta cuando ocurra el evento real. No se registran automáticamente al cambiar el estado.
</div>
<div class="row">
    <div class="col-md-6 mb-3">
        {{ form_estado.fecha_envio_rhitso.label_tag }}
        {{ form_estado.fecha_envio_rhitso }}
        ...
        {% if orden.fecha_envio_rhitso %}
            <small class="text-success d-block mt-1">
                <i class="bi bi-check-circle"></i> Registrada: {{ orden.fecha_envio_rhitso|date:"d/m/Y H:i" }}
            </small>
        {% else %}
            <small class="text-muted d-block mt-1">
                <i class="bi bi-clock-history"></i> Aún no registrada - Ingrésala manualmente cuando envíes el equipo
            </small>
        {% endif %}
    </div>
</div>
```

**Explicación del cambio:**
- ✅ Alerta informativa destacada en azul antes de los campos
- ✅ Mensajes de ayuda contextuales cuando la fecha no está registrada
- ✅ Claridad visual sobre el estado actual de cada fecha

---

## ✅ VERIFICACIONES REALIZADAS

### 1. **Signals (servicio_tecnico/signals.py)** ✅
- ✅ Confirmado: Los signals NO registran fechas automáticamente
- ✅ Solo hacen seguimiento de cambios de estado (`SeguimientoRHITSO`)
- ✅ No requieren modificación

### 2. **Otras vistas** ✅
- ✅ Revisado: No hay otras vistas que modifiquen estas fechas automáticamente
- ✅ La única vista que gestiona fechas es `actualizar_estado_rhitso()`

---

## 🎓 INSTRUCCIONES PARA USUARIOS

### ¿Cómo registrar las fechas ahora?

1. **Navega a:** Servicio Técnico → Dashboard RHITSO → Gestión RHITSO (de una orden específica)

2. **Haz clic en:** "Actualizar Estado RHITSO" (botón azul)

3. **Llena el formulario:**
   - Selecciona el nuevo estado (ejemplo: "ENVIADO A RHITSO")
   - **IMPORTANTE:** Ingresa manualmente la fecha de envío en el campo "Fecha de Envío a RHITSO (Manual)"
   - Agrega observaciones si es necesario
   - Guarda

4. **Para fecha de retorno:**
   - Cuando el equipo regrese, actualiza el estado (ejemplo: "EQUIPO RETORNADO A SIC")
   - **IMPORTANTE:** Ingresa manualmente la fecha de retorno en el campo "Fecha de Retorno a SIC (Manual)"

### ⚠️ Advertencias

- ❌ **NO** asumas que la fecha se registrará automáticamente al cambiar el estado
- ✅ **SÍ** ingresa siempre la fecha exacta manualmente
- ✅ **SÍ** verifica que la fecha se haya guardado correctamente (aparecerá en verde)

---

## 📊 IMPACTO EN MÉTRICAS

### Cálculos que usan estas fechas:

1. **`dias_en_rhitso`** (Property del modelo):
   ```python
   @property
   def dias_en_rhitso(self):
       if not self.fecha_envio_rhitso:
           return 0
       if self.fecha_recepcion_rhitso:
           delta = self.fecha_recepcion_rhitso - self.fecha_envio_rhitso
       else:
           delta = timezone.now() - self.fecha_envio_rhitso
       return delta.days
   ```

2. **Dashboard RHITSO** - Columna "Tiempo":
   - Muestra días en SIC y días en RHITSO
   - Requiere `fecha_envio_rhitso` para calcular correctamente

3. **Reportes Excel** - Columna "Fecha Envío":
   - Exporta la fecha si existe
   - Muestra "No enviado" si no se ha registrado manualmente

### ¿Qué pasa si no se registra la fecha?

- `fecha_envio_rhitso = None` → `dias_en_rhitso = 0`
- Reportes mostrarán "No enviado"
- Métricas de tiempo en RHITSO no se calcularán correctamente

**Por eso es CRÍTICO** registrar las fechas manualmente cuando ocurran los eventos.

---

## 🔄 COMPATIBILIDAD CON DATOS EXISTENTES

### Órdenes antiguas con fechas automáticas

- ✅ **Mantienen sus fechas:** No se modifican registros existentes
- ✅ **Siguen funcionando:** Todos los cálculos y reportes funcionan igual
- ℹ️ **Nueva conducta:** Solo aplica para cambios de estado FUTUROS

### Migración de base de datos

- ❌ **NO requiere migración:** No se modificó la estructura de la base de datos
- ✅ **Solo lógica de negocio:** Los cambios son en Python (views, forms, templates)

---

## 🐛 SOLUCIÓN DE PROBLEMAS

### Problema: "La fecha no se guardó"

**Causa posible:**
1. No ingresaste la fecha en el formulario
2. Error de validación del formulario (revisa mensajes)

**Solución:**
1. Abre el formulario nuevamente
2. Ingresa la fecha en formato: `YYYY-MM-DD HH:MM`
3. Guarda y verifica que aparezca el mensaje de éxito

### Problema: "Los reportes muestran días incorrectos"

**Causa posible:**
- La `fecha_envio_rhitso` no está registrada

**Solución:**
1. Navega a la orden específica
2. Actualiza el estado RHITSO
3. Ingresa manualmente la fecha correcta de envío
4. Guarda y regenera el reporte

---

## 📚 REFERENCIAS

- **Modelo:** `servicio_tecnico/models.py` - `OrdenServicio` (líneas 166-175)
- **Vista:** `servicio_tecnico/views.py` - `actualizar_estado_rhitso()` (líneas 3451+)
- **Formulario:** `servicio_tecnico/forms.py` - `ActualizarEstadoRHITSOForm` (líneas 2100+)
- **Template:** `servicio_tecnico/templates/servicio_tecnico/rhitso/gestion_rhitso.html`
- **Signals:** `servicio_tecnico/signals.py` (sin cambios - solo seguimiento de estados)

---

## ✨ BENEFICIOS DE ESTE CAMBIO

1. **Mayor precisión:** Fechas reflejan el evento físico real, no el cambio de estado en el sistema
2. **Más control:** El usuario decide cuándo y cómo registrar las fechas
3. **Evita errores:** No hay registros automáticos incorrectos por cambios de estado fuera de tiempo
4. **Documentación clara:** El usuario sabe que debe ingresar las fechas manualmente
5. **Auditoría mejorada:** Las fechas son siempre intencionales, no automáticas

---

## 📝 NOTAS ADICIONALES

- Los **seguimientos de estado** (`SeguimientoRHITSO`) siguen funcionando automáticamente vía signals
- El **historial de eventos** (`HistorialOrden`) sigue registrando cambios automáticamente
- Solo las **fechas específicas** `fecha_envio_rhitso` y `fecha_recepcion_rhitso` son manuales

---

**Documentación creada el:** 13 de octubre de 2025  
**Autor:** Sistema de Gestión SIC  
**Versión:** 1.0
