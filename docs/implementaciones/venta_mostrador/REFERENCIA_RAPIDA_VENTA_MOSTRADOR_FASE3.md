# 🚀 Referencia Rápida - Sistema Venta Mostrador FASE 3 (Backend)

## 📋 Índice Rápido
- [Formularios](#-formularios)
- [Vistas AJAX](#-vistas-ajax)
- [URLs](#-urls)
- [Respuestas JSON](#-respuestas-json)
- [Validaciones](#-validaciones)
- [Ejemplos de Uso](#-ejemplos-de-uso)
- [Troubleshooting](#-troubleshooting)

---

## 📝 Formularios

### VentaMostradorForm

**Archivo:** `servicio_tecnico/forms.py`

**Modelo asociado:** `VentaMostrador`

#### Campos (10)
```python
paquete                    # Select: premium/oro/plata/ninguno
incluye_cambio_pieza       # Boolean (checkbox)
costo_cambio_pieza         # Decimal (solo si checkbox marcado)
incluye_limpieza           # Boolean (checkbox)
costo_limpieza             # Decimal (solo si checkbox marcado)
incluye_kit_limpieza       # Boolean (checkbox)
costo_kit                  # Decimal (solo si checkbox marcado)
incluye_reinstalacion_so   # Boolean (checkbox)
costo_reinstalacion        # Decimal (solo si checkbox marcado)
notas_adicionales          # TextField (opcional)
```

#### Validaciones
- Si `incluye_*` = True → `costo_*` debe ser > 0
- 4 validaciones en método `clean()`

#### Uso en vistas
```python
# Crear nueva venta
form = VentaMostradorForm(request.POST)
if form.is_valid():
    venta = form.save(commit=False)
    venta.orden = orden
    venta.save()

# Editar venta existente
form = VentaMostradorForm(request.POST, instance=venta_existente)
if form.is_valid():
    form.save()
```

#### Ejemplo de validación
```python
# Si el usuario marca "incluye_cambio_pieza" pero pone costo 0
# El formulario devuelve:
ValidationError({
    'costo_cambio_pieza': '❌ Si incluye cambio de pieza, el costo debe ser mayor a 0'
})
```

---

### PiezaVentaMostradorForm

**Archivo:** `servicio_tecnico/forms.py`

**Modelo asociado:** `PiezaVentaMostrador`

#### Campos (5)
```python
componente          # ForeignKey opcional (ScoreCard ComponenteInventario)
descripcion_pieza   # TextField (obligatorio, min 3 caracteres)
cantidad            # PositiveIntegerField (mínimo 1)
precio_unitario     # DecimalField (mínimo 0.01)
notas               # TextField (opcional)
```

#### Validaciones
- `descripcion_pieza`: No vacía, mínimo 3 caracteres
- `cantidad`: Mínimo 1
- `precio_unitario`: Mayor a 0

#### Uso en vistas
```python
# Agregar pieza
form = PiezaVentaMostradorForm(request.POST)
if form.is_valid():
    pieza = form.save(commit=False)
    pieza.venta_mostrador = venta
    pieza.save()

# Editar pieza
form = PiezaVentaMostradorForm(request.POST, instance=pieza_existente)
if form.is_valid():
    form.save()
```

#### Propiedades calculadas
```python
pieza.subtotal  # = cantidad * precio_unitario (property del modelo)
```

---

## 🔧 Vistas AJAX

### 1. crear_venta_mostrador

**URL:** `/ordenes/<orden_id>/venta-mostrador/crear/`  
**Método:** `POST`  
**Decoradores:** `@login_required`, `@require_http_methods(["POST"])`

#### Parámetros POST
```python
paquete                    # Required: premium/oro/plata/ninguno
incluye_cambio_pieza       # Optional: on/off
costo_cambio_pieza         # Required if incluye_cambio_pieza
incluye_limpieza           # Optional: on/off
costo_limpieza             # Required if incluye_limpieza
incluye_kit_limpieza       # Optional: on/off
costo_kit                  # Required if incluye_kit_limpieza
incluye_reinstalacion_so   # Optional: on/off
costo_reinstalacion        # Required if incluye_reinstalacion_so
notas_adicionales          # Optional
```

#### Validaciones
- Orden debe existir
- `tipo_servicio` debe ser `'venta_mostrador'`
- No debe existir venta mostrador previa
- Formulario debe ser válido

#### Respuesta exitosa
```json
{
    "success": true,
    "message": "✅ Venta Mostrador creada: VM-2025-0001",
    "folio_venta": "VM-2025-0001",
    "total_venta": 5500.00,
    "paquete": "Solución Premium",
    "redirect_url": "/servicio-tecnico/ordenes/123/"
}
```

#### Respuesta con error
```json
{
    "success": false,
    "errors": {
        "costo_cambio_pieza": "Si incluye cambio de pieza, el costo debe ser mayor a 0"
    }
}
```

#### Ejemplo AJAX (JavaScript)
```javascript
fetch(`/servicio-tecnico/ordenes/${ordenId}/venta-mostrador/crear/`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCookie('csrftoken')
    },
    body: new URLSearchParams({
        'paquete': 'premium',
        'incluye_limpieza': 'on',
        'costo_limpieza': '500.00',
        'notas_adicionales': 'Limpieza profunda solicitada'
    })
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        alert(data.message);
        window.location.href = data.redirect_url;
    } else {
        mostrarErrores(data.errors);
    }
});
```

---

### 2. agregar_pieza_venta_mostrador

**URL:** `/ordenes/<orden_id>/venta-mostrador/piezas/agregar/`  
**Método:** `POST`  
**Decoradores:** `@login_required`, `@require_http_methods(["POST"])`

#### Parámetros POST
```python
componente          # Optional: ID del componente
descripcion_pieza   # Required: min 3 caracteres
cantidad            # Required: >= 1
precio_unitario     # Required: > 0
notas               # Optional
```

#### Validaciones
- Orden debe tener venta mostrador asociada
- Todos los campos requeridos deben estar presentes
- Cantidad >= 1
- Precio > 0

#### Respuesta exitosa
```json
{
    "success": true,
    "message": "✅ Pieza agregada: RAM 8GB DDR4 Kingston",
    "pieza_id": 42,
    "descripcion": "RAM 8GB DDR4 Kingston",
    "cantidad": 1,
    "precio_unitario": 800.00,
    "subtotal": 800.00,
    "total_venta_actualizado": 6300.00,
    "redirect_url": "/servicio-tecnico/ordenes/123/"
}
```

#### Ejemplo AJAX
```javascript
fetch(`/servicio-tecnico/ordenes/${ordenId}/venta-mostrador/piezas/agregar/`, {
    method: 'POST',
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCookie('csrftoken')
    },
    body: new URLSearchParams({
        'descripcion_pieza': 'RAM 8GB DDR4 Kingston',
        'cantidad': '1',
        'precio_unitario': '800.00',
        'notas': 'Compatible con laptop HP'
    })
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        // Actualizar tabla de piezas
        agregarPiezaATabla(data);
        // Actualizar total
        actualizarTotal(data.total_venta_actualizado);
        // Cerrar modal
        $('#modalPiezaVentaMostrador').modal('hide');
    }
});
```

---

### 3. editar_pieza_venta_mostrador

**URL:** `/venta-mostrador/piezas/<pieza_id>/editar/`  
**Método:** `POST`  
**Decoradores:** `@login_required`, `@require_http_methods(["POST"])`

#### Parámetros POST
```python
componente          # Optional
descripcion_pieza   # Required
cantidad            # Required
precio_unitario     # Required
notas               # Optional
```

#### Respuesta exitosa
```json
{
    "success": true,
    "message": "✅ Pieza actualizada: RAM 8GB DDR4 Kingston",
    "pieza_id": 42,
    "descripcion": "RAM 8GB DDR4 Kingston",
    "cantidad": 2,
    "precio_unitario": 750.00,
    "subtotal": 1500.00,
    "total_venta_actualizado": 7000.00,
    "redirect_url": "/servicio-tecnico/ordenes/123/"
}
```

#### Ejemplo AJAX
```javascript
function editarPieza(piezaId) {
    fetch(`/servicio-tecnico/venta-mostrador/piezas/${piezaId}/editar/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: new URLSearchParams({
            'descripcion_pieza': document.getElementById('desc').value,
            'cantidad': document.getElementById('cant').value,
            'precio_unitario': document.getElementById('precio').value
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            actualizarFilaTabla(piezaId, data);
            actualizarTotal(data.total_venta_actualizado);
        }
    });
}
```

---

### 4. eliminar_pieza_venta_mostrador

**URL:** `/venta-mostrador/piezas/<pieza_id>/eliminar/`  
**Método:** `POST`  
**Decoradores:** `@login_required`, `@require_http_methods(["POST"])`

#### Parámetros POST
Ninguno (solo pieza_id en URL)

#### Respuesta exitosa
```json
{
    "success": true,
    "message": "✅ Pieza eliminada: RAM 8GB DDR4 Kingston",
    "total_venta_actualizado": 5500.00,
    "redirect_url": "/servicio-tecnico/ordenes/123/"
}
```

#### Ejemplo AJAX
```javascript
function eliminarPieza(piezaId) {
    if (!confirm('¿Seguro que deseas eliminar esta pieza?')) {
        return;
    }
    
    fetch(`/servicio-tecnico/venta-mostrador/piezas/${piezaId}/eliminar/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Eliminar fila de la tabla
            document.getElementById(`pieza-${piezaId}`).remove();
            // Actualizar total
            actualizarTotal(data.total_venta_actualizado);
            alert(data.message);
        }
    });
}
```

---

### 5. convertir_venta_a_diagnostico ⚠️

**URL:** `/ordenes/<orden_id>/convertir-a-diagnostico/`  
**Método:** `POST`  
**Decoradores:** `@login_required`, `@require_http_methods(["POST"])`

**⚠️ IMPORTANTE:** Esta es una operación crítica que no se puede deshacer.

#### Parámetros POST
```python
motivo_conversion   # Required: mínimo 10 caracteres
```

#### Validaciones (5)
1. `tipo_servicio` debe ser `'venta_mostrador'`
2. Debe tener venta mostrador asociada
3. Estado no debe ser `'convertida_a_diagnostico'` (ya convertida)
4. Estado debe ser uno de: `'recepcion'`, `'reparacion'`, `'control_calidad'`
5. `motivo_conversion` debe tener al menos 10 caracteres

#### Respuesta exitosa
```json
{
    "success": true,
    "message": "✅ Orden convertida a diagnóstico exitosamente",
    "orden_original": "VM-2025-0001",
    "nueva_orden_id": 234,
    "nueva_orden_numero": "ORD-2025-0234",
    "monto_abono": 1000.00,
    "redirect_url": "/servicio-tecnico/ordenes/234/"
}
```

#### Respuesta con error
```json
{
    "success": false,
    "error": "❌ Solo se pueden convertir órdenes de tipo 'Venta Mostrador'"
}
```

#### Ejemplo AJAX
```javascript
function convertirADiagnostico(ordenId) {
    const motivo = prompt('¿Por qué necesitas convertir esta orden a diagnóstico?\n(Mínimo 10 caracteres)');
    
    if (!motivo || motivo.length < 10) {
        alert('El motivo debe tener al menos 10 caracteres');
        return;
    }
    
    if (!confirm('⚠️ Esta acción no se puede deshacer. ¿Continuar?')) {
        return;
    }
    
    fetch(`/servicio-tecnico/ordenes/${ordenId}/convertir-a-diagnostico/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: new URLSearchParams({
            'motivo_conversion': motivo
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(`${data.message}\n\nNueva orden: ${data.nueva_orden_numero}\nMonto abonado: $${data.monto_abono}`);
            window.location.href = data.redirect_url;
        } else {
            alert(data.error);
        }
    });
}
```

---

## 🔗 URLs

### Patrón de nombres
Todas las URLs usan el prefijo `venta_mostrador_` para facilitar búsqueda.

### Lista completa
```python
# Crear venta mostrador
venta_mostrador_crear

# Gestión de piezas
venta_mostrador_agregar_pieza
venta_mostrador_editar_pieza
venta_mostrador_eliminar_pieza

# Conversión especial
venta_mostrador_convertir
```

### Uso en templates
```html
<!-- Crear venta mostrador -->
<form action="{% url 'venta_mostrador_crear' orden.id %}" method="post">
    {% csrf_token %}
    <!-- campos del formulario -->
</form>

<!-- Agregar pieza -->
<form action="{% url 'venta_mostrador_agregar_pieza' orden.id %}" method="post">
    {% csrf_token %}
    <!-- campos de pieza -->
</form>

<!-- Editar pieza -->
<form action="{% url 'venta_mostrador_editar_pieza' pieza.id %}" method="post">
    {% csrf_token %}
    <!-- campos de pieza -->
</form>

<!-- Eliminar pieza -->
<form action="{% url 'venta_mostrador_eliminar_pieza' pieza.id %}" method="post">
    {% csrf_token %}
    <button type="submit">Eliminar</button>
</form>

<!-- Convertir a diagnóstico -->
<form action="{% url 'venta_mostrador_convertir' orden.id %}" method="post">
    {% csrf_token %}
    <input type="text" name="motivo_conversion" required>
    <button type="submit">Convertir</button>
</form>
```

### Uso en vistas (reverse)
```python
from django.urls import reverse
from django.shortcuts import redirect

# Redireccionar después de crear venta
return redirect('detalle_orden', orden_id=orden.id)

# O usando reverse en respuesta JSON
redirect_url = reverse('detalle_orden', kwargs={'orden_id': orden.id})
```

---

## 📦 Respuestas JSON

### Formato estándar

#### Éxito
```json
{
    "success": true,
    "message": "✅ Mensaje descriptivo",
    "redirect_url": "/url/destino/",
    // ... datos específicos de cada endpoint
}
```

#### Error de validación
```json
{
    "success": false,
    "errors": {
        "campo1": "Mensaje de error 1",
        "campo2": "Mensaje de error 2"
    }
}
```

#### Error general
```json
{
    "success": false,
    "error": "❌ Descripción del error"
}
```

### Campos comunes en respuestas exitosas

#### crear_venta_mostrador
```json
{
    "success": true,
    "message": "...",
    "folio_venta": "VM-2025-0001",
    "total_venta": 5500.00,
    "paquete": "Solución Premium",
    "redirect_url": "..."
}
```

#### agregar/editar_pieza
```json
{
    "success": true,
    "message": "...",
    "pieza_id": 42,
    "descripcion": "RAM 8GB DDR4 Kingston",
    "cantidad": 1,
    "precio_unitario": 800.00,
    "subtotal": 800.00,
    "total_venta_actualizado": 6300.00,
    "redirect_url": "..."
}
```

#### eliminar_pieza
```json
{
    "success": true,
    "message": "...",
    "total_venta_actualizado": 5500.00,
    "redirect_url": "..."
}
```

#### convertir_a_diagnostico
```json
{
    "success": true,
    "message": "...",
    "orden_original": "VM-2025-0001",
    "nueva_orden_id": 234,
    "nueva_orden_numero": "ORD-2025-0234",
    "monto_abono": 1000.00,
    "redirect_url": "..."
}
```

---

## ✅ Validaciones

### Por Formulario

#### VentaMostradorForm
| Campo | Validación | Mensaje de error |
|-------|-----------|------------------|
| `costo_cambio_pieza` | Si `incluye_cambio_pieza` = True → costo > 0 | ❌ Si incluye cambio de pieza, el costo debe ser mayor a 0 |
| `costo_limpieza` | Si `incluye_limpieza` = True → costo > 0 | ❌ Si incluye limpieza, el costo debe ser mayor a 0 |
| `costo_kit` | Si `incluye_kit_limpieza` = True → costo > 0 | ❌ Si incluye kit de limpieza, el costo debe ser mayor a 0 |
| `costo_reinstalacion` | Si `incluye_reinstalacion_so` = True → costo > 0 | ❌ Si incluye reinstalación, el costo debe ser mayor a 0 |

#### PiezaVentaMostradorForm
| Campo | Validación | Mensaje de error |
|-------|-----------|------------------|
| `descripcion_pieza` | No vacía y >= 3 caracteres | ❌ La descripción de la pieza es obligatoria / ❌ La descripción debe tener al menos 3 caracteres |
| `cantidad` | >= 1 | ❌ La cantidad debe ser al menos 1 |
| `precio_unitario` | > 0 | ❌ El precio unitario debe ser mayor a 0 |

### Por Vista

#### crear_venta_mostrador
- Orden existe (404 si no)
- `tipo_servicio` == `'venta_mostrador'` (400 si no)
- NO tiene venta mostrador previa (400 si tiene)
- Formulario válido (400 con errores si no)

#### agregar_pieza_venta_mostrador
- Orden existe (404 si no)
- Orden tiene venta mostrador (400 si no)
- Formulario válido (400 con errores si no)

#### editar_pieza_venta_mostrador
- Pieza existe (404 si no)
- Formulario válido (400 con errores si no)

#### eliminar_pieza_venta_mostrador
- Pieza existe (404 si no)

#### convertir_venta_a_diagnostico
1. `tipo_servicio` == `'venta_mostrador'` (400 si no)
2. Tiene venta mostrador asociada (400 si no)
3. Estado != `'convertida_a_diagnostico'` (400 si ya convertida)
4. Estado en `['recepcion', 'reparacion', 'control_calidad']` (400 si no)
5. `motivo_conversion` >= 10 caracteres (400 si no)

---

## 💡 Ejemplos de Uso

### Ejemplo 1: Crear venta mostrador completa

```javascript
// HTML: Modal con formulario
<form id="formVentaMostrador">
    <select name="paquete" id="paquete" required>
        <option value="premium">Solución Premium - $5000</option>
        <option value="oro">Solución Oro - $3500</option>
        <option value="plata">Solución Plata - $2000</option>
        <option value="ninguno">Ninguno - $0</option>
    </select>
    
    <input type="checkbox" name="incluye_limpieza" id="incluye_limpieza">
    <input type="number" name="costo_limpieza" id="costo_limpieza" step="0.01">
    
    <textarea name="notas_adicionales" id="notas_adicionales"></textarea>
    
    <button type="submit">Crear Venta</button>
</form>

// JavaScript: Enviar formulario
document.getElementById('formVentaMostrador').addEventListener('submit', function(e) {
    e.preventDefault();
    
    const formData = new FormData(this);
    
    fetch(`/servicio-tecnico/ordenes/${ordenId}/venta-mostrador/crear/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: new URLSearchParams(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert(data.message);
            window.location.reload();
        } else {
            mostrarErroresFormulario(data.errors);
        }
    });
});
```

---

### Ejemplo 2: Agregar múltiples piezas

```javascript
const piezas = [
    { descripcion: 'RAM 8GB DDR4', cantidad: 1, precio: 800 },
    { descripcion: 'Disco SSD 256GB', cantidad: 1, precio: 1200 },
    { descripcion: 'Teclado externo USB', cantidad: 1, precio: 350 }
];

async function agregarTodasLasPiezas(ordenId, piezas) {
    for (const pieza of piezas) {
        const response = await fetch(
            `/servicio-tecnico/ordenes/${ordenId}/venta-mostrador/piezas/agregar/`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': getCookie('csrftoken')
                },
                body: new URLSearchParams({
                    'descripcion_pieza': pieza.descripcion,
                    'cantidad': pieza.cantidad,
                    'precio_unitario': pieza.precio
                })
            }
        );
        
        const data = await response.json();
        
        if (data.success) {
            console.log(`✅ ${data.message}`);
            agregarPiezaATabla(data);
        } else {
            console.error(`❌ Error: ${JSON.stringify(data.errors)}`);
            break;
        }
    }
    
    // Al final, actualizar total
    window.location.reload();
}
```

---

### Ejemplo 3: Editar pieza inline

```javascript
// HTML: Tabla con piezas editables
<table id="tablaPiezas">
    <thead>
        <tr>
            <th>Descripción</th>
            <th>Cantidad</th>
            <th>Precio Unit.</th>
            <th>Subtotal</th>
            <th>Acciones</th>
        </tr>
    </thead>
    <tbody>
        {% for pieza in piezas_venta_mostrador %}
        <tr id="pieza-{{ pieza.id }}">
            <td>
                <input type="text" class="form-control" 
                       value="{{ pieza.descripcion_pieza }}" 
                       id="desc-{{ pieza.id }}">
            </td>
            <td>
                <input type="number" class="form-control" 
                       value="{{ pieza.cantidad }}" 
                       id="cant-{{ pieza.id }}" 
                       min="1">
            </td>
            <td>
                <input type="number" class="form-control" 
                       value="{{ pieza.precio_unitario }}" 
                       id="precio-{{ pieza.id }}" 
                       step="0.01" 
                       min="0.01">
            </td>
            <td id="subtotal-{{ pieza.id }}">${{ pieza.subtotal }}</td>
            <td>
                <button onclick="guardarPieza({{ pieza.id }})">
                    💾 Guardar
                </button>
                <button onclick="eliminarPieza({{ pieza.id }})">
                    🗑️ Eliminar
                </button>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>

// JavaScript: Guardar cambios
function guardarPieza(piezaId) {
    const descripcion = document.getElementById(`desc-${piezaId}`).value;
    const cantidad = document.getElementById(`cant-${piezaId}`).value;
    const precio = document.getElementById(`precio-${piezaId}`).value;
    
    fetch(`/servicio-tecnico/venta-mostrador/piezas/${piezaId}/editar/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: new URLSearchParams({
            'descripcion_pieza': descripcion,
            'cantidad': cantidad,
            'precio_unitario': precio
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Actualizar subtotal en la tabla
            document.getElementById(`subtotal-${piezaId}`).textContent = 
                `$${data.subtotal.toFixed(2)}`;
            
            // Actualizar total general
            document.getElementById('total-venta').textContent = 
                `$${data.total_venta_actualizado.toFixed(2)}`;
            
            alert(data.message);
        } else {
            alert('Error: ' + JSON.stringify(data.errors));
        }
    });
}
```

---

### Ejemplo 4: Conversión con confirmación

```javascript
function mostrarModalConversion(ordenId) {
    // Crear modal dinámico
    const modal = `
        <div class="modal fade" id="modalConversion" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header bg-warning">
                        <h5 class="modal-title">⚠️ Convertir a Diagnóstico</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="alert alert-warning">
                            <strong>⚠️ Advertencia:</strong> Esta acción no se puede deshacer.
                            <br>Se creará una nueva orden y se transferirá el monto pagado.
                        </div>
                        
                        <label for="motivo">Motivo de conversión (mínimo 10 caracteres):</label>
                        <textarea id="motivo" class="form-control" rows="3" required></textarea>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
                            Cancelar
                        </button>
                        <button type="button" class="btn btn-warning" onclick="confirmarConversion(${ordenId})">
                            Convertir a Diagnóstico
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modal);
    new bootstrap.Modal(document.getElementById('modalConversion')).show();
}

function confirmarConversion(ordenId) {
    const motivo = document.getElementById('motivo').value.trim();
    
    if (motivo.length < 10) {
        alert('El motivo debe tener al menos 10 caracteres');
        return;
    }
    
    fetch(`/servicio-tecnico/ordenes/${ordenId}/convertir-a-diagnostico/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: new URLSearchParams({
            'motivo_conversion': motivo
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            const mensaje = `
                ${data.message}
                
                📋 Orden original: ${data.orden_original}
                🆕 Nueva orden: ${data.nueva_orden_numero} (ID: ${data.nueva_orden_id})
                💵 Monto abonado: $${data.monto_abono.toFixed(2)}
            `;
            
            alert(mensaje);
            window.location.href = data.redirect_url;
        } else {
            alert('Error: ' + data.error);
        }
    });
}
```

---

## 🔍 Troubleshooting

### Error: "❌ Solo se pueden convertir órdenes de tipo 'Venta Mostrador'"

**Causa:** Intentas convertir una orden que no es de tipo `venta_mostrador`.

**Solución:** Verifica el `tipo_servicio` de la orden:
```python
if orden.tipo_servicio == 'venta_mostrador':
    # Permitir conversión
```

---

### Error: "❌ Si incluye cambio de pieza, el costo debe ser mayor a 0"

**Causa:** El checkbox `incluye_cambio_pieza` está marcado pero `costo_cambio_pieza` es 0 o vacío.

**Solución JavaScript (frontend):**
```javascript
document.getElementById('incluye_cambio_pieza').addEventListener('change', function() {
    const costoField = document.getElementById('costo_cambio_pieza');
    if (this.checked) {
        costoField.required = true;
        costoField.min = '0.01';
    } else {
        costoField.required = false;
        costoField.value = '0';
    }
});
```

---

### Error: "❌ Esta orden ya tiene venta mostrador"

**Causa:** Intentas crear una segunda venta mostrador en la misma orden.

**Solución:** Verifica antes de mostrar el formulario:
```python
if hasattr(orden, 'venta_mostrador'):
    # Mostrar venta existente, no formulario de creación
else:
    # Mostrar formulario para crear
```

---

### Error: 403 Forbidden (CSRF)

**Causa:** No estás enviando el token CSRF en la petición AJAX.

**Solución:**
```javascript
// Función para obtener el token CSRF
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Usar en fetch
fetch(url, {
    method: 'POST',
    headers: {
        'X-CSRFToken': getCookie('csrftoken')
    },
    body: data
})
```

---

### Error: Total no se actualiza automáticamente

**Causa:** Estás intentando leer `total_venta` directamente después de modificar piezas sin refrescar.

**Solución:** El `total_venta` es un `@property` que se calcula dinámicamente. Necesitas:
1. Recargar el objeto desde la BD
2. O usar la respuesta JSON que devuelve `total_venta_actualizado`

```python
# Backend: Refrescar objeto
venta.refresh_from_db()
nuevo_total = venta.total_venta

# Frontend: Usar respuesta JSON
.then(data => {
    document.getElementById('total-venta').textContent = 
        `$${data.total_venta_actualizado.toFixed(2)}`;
});
```

---

### Error: 404 en URL de pieza

**Causa:** El `pieza_id` en la URL no existe o fue eliminado.

**Solución:** Verifica que el ID sea válido antes de hacer la petición:
```javascript
function editarPieza(piezaId) {
    // Verificar que la fila existe en el DOM
    const fila = document.getElementById(`pieza-${piezaId}`);
    if (!fila) {
        alert('La pieza ya no existe');
        return;
    }
    
    // Continuar con la petición AJAX
    fetch(`/servicio-tecnico/venta-mostrador/piezas/${piezaId}/editar/`, ...)
}
```

---

### Error: "No se puede convertir desde el estado 'Completada'"

**Causa:** Solo puedes convertir órdenes en estados tempranos (recepción, reparación, control_calidad).

**Solución:** Verifica el estado antes de mostrar el botón de conversión:
```html
{% if orden.estado in 'recepcion,reparacion,control_calidad' %}
    <button onclick="convertirADiagnostico({{ orden.id }})">
        Convertir a Diagnóstico
    </button>
{% else %}
    <span class="text-muted">
        No se puede convertir desde el estado "{{ orden.get_estado_display }}"
    </span>
{% endif %}
```

---

## 📚 Recursos Adicionales

### Documentos relacionados
- `VENTAS_MOSTRADOR_PLAN_IMPLEMENTACION.md` - Plan maestro completo
- `CHANGELOG_VENTA_MOSTRADOR_FASE3.md` - Changelog detallado
- `README_SERVICIO_TECNICO.md` - Documentación general del módulo

### Archivos de código
- `servicio_tecnico/forms.py` - Formularios (líneas ~1440-1670)
- `servicio_tecnico/views.py` - Vistas AJAX (líneas ~2380-2789)
- `servicio_tecnico/urls.py` - URLs (sección "VENTA MOSTRADOR")
- `servicio_tecnico/models.py` - Modelos VentaMostrador y PiezaVentaMostrador

### Próximos pasos
- **FASE 4:** Implementación de frontend (templates, modales, JavaScript)
- **FASE 5:** Testing completo del flujo
- **FASE 6:** Documentación final y capacitación

---

**Última actualización:** 8 de Octubre, 2025  
**Versión:** FASE 3 Backend  
**Estado:** ✅ Completado y probado
