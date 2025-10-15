# 📋 Gestión de Referencias de Gama de Equipos

## 🎯 Descripción General

El sistema de **Referencias de Gama** permite clasificar automáticamente los equipos en **Alta**, **Media** o **Baja** gama basándose en un catálogo de referencias predefinidas. Esto agiliza la creación de órdenes de servicio y estandariza la clasificación de equipos.

---

## 🔍 ¿Cómo Funciona la Clasificación Automática?

### Proceso de Clasificación

Cuando se crea una **Orden de Servicio** y se captura la información del equipo:

1. **Se capturan** la marca y modelo del equipo
2. **El sistema busca** en la tabla `ReferenciaGamaEquipo` una coincidencia
3. **Si encuentra coincidencia**, asigna automáticamente la gama
4. **Si no encuentra**, el usuario puede seleccionar manualmente

### Tipos de Coincidencia

#### 1️⃣ Coincidencia Exacta
- **Marca** y **Modelo** deben ser idénticos (sin distinguir mayúsculas/minúsculas)
- Ejemplo:
  - **Referencia:** `Lenovo ThinkPad`
  - **Equipo capturado:** `Lenovo ThinkPad` ✅ Coincide

#### 2️⃣ Coincidencia Parcial
- El modelo capturado **contiene** el modelo base de la referencia
- Ejemplo:
  - **Referencia:** `Lenovo ThinkPad`
  - **Equipo capturado:** `Lenovo ThinkPad X1 Carbon Gen 9` ✅ Coincide
  - **Equipo capturado:** `Lenovo ThinkPad T14` ✅ Coincide

---

## 🛠️ Gestión de Referencias (CRUD)

### 📄 Lista de Referencias

**URL:** `/servicio-tecnico/referencias-gama/`

**Funcionalidades:**
- ✅ Ver todas las referencias activas e inactivas
- 🔍 Búsqueda por marca o modelo
- 🎯 Filtros por marca, gama y estado
- 📊 Estadísticas de referencias registradas
- 🔄 Ordenamiento por columnas

**Campos mostrados:**
- Marca del equipo
- Modelo base o familia
- Gama asignada (Alta/Media/Baja)
- Rango de costo (referencial)
- Estado (Activo/Inactivo)
- Acciones disponibles

### ➕ Crear Nueva Referencia

**URL:** `/servicio-tecnico/referencias-gama/crear/`

**Campos requeridos:**
- **Marca:** Nombre del fabricante (ej: Lenovo, HP, Dell)
- **Modelo Base:** Familia o modelo base (ej: ThinkPad, Pavilion, Inspiron)
- **Gama:** Clasificación (Alta, Media, Baja)
- **Rango Costo Mínimo:** Precio aproximado mínimo
- **Rango Costo Máximo:** Precio aproximado máximo
- **Activo:** Si está activa para clasificación automática

**Validaciones:**
- ✅ El costo máximo debe ser mayor al mínimo
- ✅ No pueden existir duplicados (marca + modelo base únicos)
- ✅ Todos los campos son obligatorios excepto "Activo" (default: True)

**Ejemplo de referencia:**
```
Marca: Lenovo
Modelo Base: ThinkPad X1
Gama: Alta
Costo Mínimo: $25,000.00
Costo Máximo: $45,000.00
Activo: ✓
```

### ✏️ Editar Referencia

**URL:** `/servicio-tecnico/referencias-gama/<id>/editar/`

**Funcionalidad:**
- Modificar cualquier campo de la referencia
- Útil para actualizar rangos de precio
- Corregir clasificaciones de gama

**Nota:** Al editar, la validación de duplicados **no aplica** para la referencia actual.

### 🗑️ Desactivar Referencia

**URL:** `/servicio-tecnico/referencias-gama/<id>/eliminar/`

**Funcionalidad:**
- **Soft delete:** No elimina, solo marca como inactiva
- La referencia ya no se usa para clasificación automática
- Se mantiene el registro en la base de datos
- Se puede reactivar en cualquier momento

**¿Por qué soft delete?**
- ✅ Mantiene consistencia en órdenes existentes
- ✅ Conserva historial
- ✅ Permite reactivación fácil
- ✅ Evita problemas de integridad referencial

### 🔄 Reactivar Referencia

**URL:** `/servicio-tecnico/referencias-gama/<id>/reactivar/`

**Funcionalidad:**
- Marca la referencia como activa nuevamente
- Vuelve a usarse para clasificación automática
- Proceso instantáneo (no requiere confirmación)

---

## 💻 Implementación Técnica

### Modelo: `ReferenciaGamaEquipo`

```python
class ReferenciaGamaEquipo(models.Model):
    marca = models.CharField(max_length=50)
    modelo_base = models.CharField(max_length=100)
    gama = models.CharField(max_length=10, choices=GAMA_EQUIPO_CHOICES)
    rango_costo_min = models.DecimalField(max_digits=10, decimal_places=2)
    rango_costo_max = models.DecimalField(max_digits=10, decimal_places=2)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['marca', 'modelo_base']
```

### Método de Clasificación Automática

```python
@classmethod
def obtener_gama(cls, marca, modelo):
    """
    Busca la gama de un equipo según su marca y modelo.
    Retorna: ReferenciaGamaEquipo o None
    """
    # 1. Buscar coincidencia exacta
    referencia = cls.objects.filter(
        marca__iexact=marca,
        modelo_base__iexact=modelo,
        activo=True
    ).first()
    
    if referencia:
        return referencia
    
    # 2. Buscar coincidencia parcial
    referencias = cls.objects.filter(marca__iexact=marca, activo=True)
    for ref in referencias:
        if ref.modelo_base.lower() in modelo.lower():
            return ref
    
    return None
```

### Uso en Creación de Órdenes

```python
# En servicio_tecnico/forms.py - NuevaOrdenForm.save()
detalle = DetalleEquipo(
    orden=orden,
    marca=self.cleaned_data['marca'],
    modelo=self.cleaned_data.get('modelo', ''),
    gama='media',  # Valor por defecto
)

# Intentar calcular la gama automáticamente
gama_calculada = ReferenciaGamaEquipo.obtener_gama(
    self.cleaned_data['marca'],
    self.cleaned_data.get('modelo', '')
)

if gama_calculada:
    detalle.gama = gama_calculada.gama  # Asignar gama encontrada

detalle.save()
```

---

## 📊 Ejemplos de Referencias Comunes

### Gama Alta (Premium/Empresarial)
| Marca | Modelo Base | Rango de Costo |
|-------|-------------|----------------|
| Lenovo | ThinkPad X1 | $25,000 - $45,000 |
| Dell | XPS | $28,000 - $50,000 |
| HP | EliteBook | $22,000 - $40,000 |
| Apple | MacBook Pro | $35,000 - $70,000 |
| Microsoft | Surface Laptop | $25,000 - $50,000 |

### Gama Media (Mainstream/Hogar-Oficina)
| Marca | Modelo Base | Rango de Costo |
|-------|-------------|----------------|
| Lenovo | IdeaPad | $8,000 - $18,000 |
| Dell | Inspiron | $9,000 - $20,000 |
| HP | Pavilion | $8,000 - $18,000 |
| Acer | Aspire | $7,000 - $15,000 |
| ASUS | VivoBook | $8,000 - $17,000 |

### Gama Baja (Entrada/Básico)
| Marca | Modelo Base | Rango de Costo |
|-------|-------------|----------------|
| HP | Stream | $3,500 - $7,000 |
| Lenovo | Essential | $4,000 - $8,000 |
| Acer | Chromebook | $3,000 - $6,500 |
| Dell | Vostro | $5,000 - $10,000 |
| ASUS | E Series | $4,000 - $8,000 |

---

## 🎓 Guía de Uso para Usuarios

### Paso 1: Agregar Referencias Iniciales

1. Navega a **Servicio Técnico** → **Referencias de Gama**
2. Clic en **"Nueva Referencia"**
3. Completa los campos:
   - Marca y Modelo Base (familias comunes)
   - Selecciona la Gama correspondiente
   - Define el rango de costos aproximado
4. Guarda la referencia

**Recomendación:** Empieza con 10-15 referencias de los modelos más comunes.

### Paso 2: Crear Orden de Servicio

1. Navega a **Servicio Técnico** → **Nueva Orden**
2. Captura la marca y modelo del equipo
3. **El sistema automáticamente:**
   - Busca coincidencias en las referencias
   - Si encuentra, asigna la gama automáticamente
   - El campo "Gama" se actualiza solo

### Paso 3: Mantenimiento de Referencias

**Revisar periódicamente:**
- ✅ Actualizar rangos de precio según el mercado
- ✅ Agregar nuevos modelos populares
- ✅ Desactivar referencias obsoletas
- ✅ Reclasificar gamas si es necesario

---

## ⚙️ Configuración del Sistema

### URLs Configuradas

```python
# En servicio_tecnico/urls.py
urlpatterns = [
    # ... otras URLs ...
    
    # Gestión de Referencias de Gama
    path('referencias-gama/', 
         views.lista_referencias_gama, 
         name='lista_referencias_gama'),
    
    path('referencias-gama/crear/', 
         views.crear_referencia_gama, 
         name='crear_referencia_gama'),
    
    path('referencias-gama/<int:referencia_id>/editar/', 
         views.editar_referencia_gama, 
         name='editar_referencia_gama'),
    
    path('referencias-gama/<int:referencia_id>/eliminar/', 
         views.eliminar_referencia_gama, 
         name='eliminar_referencia_gama'),
    
    path('referencias-gama/<int:referencia_id>/reactivar/', 
         views.reactivar_referencia_gama, 
         name='reactivar_referencia_gama'),
]
```

### Acceso desde el Menú

Agrega un enlace en el menú de navegación:

```html
<!-- En templates/base.html -->
<li class="nav-item">
    <a class="nav-link" href="{% url 'servicio_tecnico:lista_referencias_gama' %}">
        <i class="bi bi-bookmark-star"></i> Referencias de Gama
    </a>
</li>
```

---

## 🔧 Troubleshooting

### Problema: La gama no se asigna automáticamente

**Causas posibles:**
1. ✅ No existe una referencia para esa marca/modelo
2. ✅ La referencia está marcada como inactiva
3. ✅ Hay diferencias en mayúsculas/minúsculas (verificar)
4. ✅ El modelo es demasiado específico

**Solución:**
- Verifica las referencias activas en el listado
- Crea una referencia con modelo base más genérico
- Ejemplo: Usa "ThinkPad" en lugar de "ThinkPad X1 Carbon Gen 9"

### Problema: Error al crear referencia duplicada

**Mensaje:** "Ya existe una referencia para [Marca] [Modelo]"

**Solución:**
- Busca la referencia existente en el listado
- Edita la referencia en lugar de crear una nueva
- Si está inactiva, reactívala

### Problema: El rango de costo es inconsistente

**Validación:** El sistema verifica que `costo_max > costo_min`

**Solución:**
- Asegúrate de que el máximo sea mayor al mínimo
- Usa valores aproximados del mercado actual
- Los rangos son solo referenciales, no afectan funcionalidad

---

## 📈 Mejores Prácticas

### 1. Nomenclatura de Modelos Base

✅ **Recomendado:** Usar familias de productos
- `ThinkPad` (coincide con X1, T14, E15, etc.)
- `Pavilion` (coincide con Pavilion 15, 14, Gaming, etc.)
- `Inspiron` (coincide con Inspiron 15 3000, 5000, etc.)

❌ **No recomendado:** Modelos muy específicos
- `ThinkPad X1 Carbon Gen 9` (solo coincide exactamente)
- `Pavilion Gaming 15-ec2000` (demasiado específico)

### 2. Actualización de Referencias

- 📅 Revisar cada **6 meses** los rangos de precio
- 🆕 Agregar nuevas familias de productos populares
- 🗑️ Desactivar modelos descontinuados

### 3. Clasificación de Gamas

**Criterios sugeridos:**
- **Alta:** Equipos empresariales premium ($20,000+)
- **Media:** Equipos mainstream hogar/oficina ($7,000 - $20,000)
- **Baja:** Equipos de entrada básicos (< $7,000)

---

## 🔐 Permisos y Seguridad

- ✅ Requiere **login** (`@login_required`)
- ✅ Acceso desde cualquier cuenta de empleado
- ✅ Soft delete para evitar pérdida de datos
- ✅ Validación en backend y frontend

---

## 📝 Notas Finales

- El sistema de clasificación automática es **opcional** - si no hay coincidencia, el usuario selecciona manualmente
- Las referencias **no afectan órdenes existentes** - solo se aplican en nuevas órdenes
- El catálogo puede crecer orgánicamente según las necesidades del negocio
- Los rangos de costo son **referenciales** - no se usan en cálculos, solo para clasificación

---

**Documento creado:** Octubre 2025  
**Versión:** 1.0  
**Módulo:** Servicio Técnico - Referencias de Gama
