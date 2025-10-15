# 🎨 Referencia Rápida - Venta Mostrador FASE 4 (Frontend)

**Última Actualización:** 9 de Octubre, 2025  
**Versión:** 1.0  
**Fase:** Frontend - Templates y JavaScript

---

## 📋 Tabla de Contenidos

1. [Resumen de la Fase](#-resumen-de-la-fase)
2. [Flujo de Usuario](#-flujo-de-usuario)
3. [Archivos Creados/Modificados](#-archivos-creadosmodificados)
4. [Formulario de Creación](#-formulario-de-creación-de-orden)
5. [Sección en detalle_orden.html](#-sección-en-detalle_ordenhtml)
6. [Modales Bootstrap](#-modales-bootstrap)
7. [JavaScript Functions](#-javascript-functions)
8. [Ejemplos de Uso](#-ejemplos-de-uso)
9. [Troubleshooting](#-troubleshooting)

---

## 🎯 Resumen de la Fase

FASE 4 implementa la interfaz de usuario completa para Ventas Mostrador:

✅ **Formulario web** para crear órdenes sin Django Admin  
✅ **Sección visual** en detalle de orden  
✅ **3 Modales Bootstrap** para gestión de datos  
✅ **JavaScript AJAX** completo (~700 líneas)  
✅ **Conversión a diagnóstico** con trazabilidad  

---

## 🚶 Flujo de Usuario

```
1. INICIO
   └─> Clic en "Venta Mostrador" (botón amarillo)
       └─> Formulario de creación de orden
           └─> Llenar datos del equipo
               └─> Guardar → Redirige a detalle_orden

2. DETALLE DE ORDEN
   └─> SECCIÓN 3.5 - VENTA MOSTRADOR
       ├─> Si NO tiene venta registrada:
       │   └─> Badge "No registrada"
       │   └─> Botón "Registrar Venta Mostrador"
       │       └─> Modal: Total, Método Pago, Notas
       │           └─> Guardar → Recarga página
       │
       └─> Si SÍ tiene venta registrada:
           ├─> Muestra: Total, Método, Fecha
           ├─> Tabla de Piezas/Servicios
           ├─> Botón "Agregar Pieza/Servicio"
           │   └─> Modal: Tipo, Descripción, Cantidad, Precio
           │       └─> Guardar → Actualiza tabla
           ├─> Botones por pieza: Editar, Eliminar
           └─> Botón "Convertir a Diagnóstico"
               └─> Modal: Motivo de conversión
                   └─> Confirmar → Crea nueva orden
                       └─> Redirige a nueva orden
```

---

## 📁 Archivos Creados/Modificados

### Archivos NUEVOS

#### 1. `form_nueva_orden_venta_mostrador.html`
**Ubicación:** `servicio_tecnico/templates/servicio_tecnico/`  
**Propósito:** Formulario web para crear órdenes de venta mostrador  
**Características:**
- Bootstrap 5 responsive
- 3 secciones: Equipo, Descripción, Ubicación
- Alertas informativas
- Breadcrumbs de navegación

#### 2. `venta_mostrador.js`
**Ubicación:** `static/js/`  
**Propósito:** Lógica AJAX para gestión de ventas mostrador  
**Tamaño:** ~700 líneas  
**Funciones:** 12 principales + 4 helpers

#### 3. Documentación
- `CHANGELOG_VENTA_MOSTRADOR_FASE4.md`
- `REFERENCIA_RAPIDA_VENTA_MOSTRADOR_FASE4.md` (este archivo)

### Archivos MODIFICADOS

#### 1. `servicio_tecnico/forms.py`
- Agregado: `NuevaOrdenVentaMostradorForm`
- **Fix crítico:** Usuario → Empleado en historial

#### 2. `servicio_tecnico/views.py`
- Agregado: `crear_orden_venta_mostrador(request)`

#### 3. `servicio_tecnico/models.py`
- **Fix crítico:** Método `convertir_a_diagnostico()`
- Corrección de nombres de campos
- Garantía de DetalleEquipo en nueva orden

#### 4. `servicio_tecnico/urls.py`
- Agregado: URL pattern para crear orden venta mostrador

#### 5. `detalle_orden.html`
- Agregada: SECCIÓN 3.5 - VENTA MOSTRADOR (~300 líneas)
- 3 nuevos modales
- Carga condicional de JavaScript

#### 6. `inicio.html`
- Agregado: Botón "Venta Mostrador" en grupo de acciones

---

## 📝 Formulario de Creación de Orden

### Acceso
```html
URL: /servicio-tecnico/ordenes/venta-mostrador/crear/
Botón: "🛒 Venta Mostrador" en página de inicio
```

### Campos del Formulario

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| `tipo_equipo` | Select | ✅ Sí | PC, Laptop, AIO, Otro |
| `marca` | Input Text | ✅ Sí | Marca del equipo |
| `modelo` | Input Text | ✅ Sí | Modelo del equipo |
| `numero_serie` | Input Text | ✅ Sí | Service Tag / S/N |
| `descripcion_servicio` | Textarea | ❌ No | Descripción opcional del servicio |
| `sucursal` | Select | ✅ Sí | Matriz o Sonora |

### Ejemplo de Uso

```python
# views.py
@login_required
def crear_orden_venta_mostrador(request):
    if request.method == 'POST':
        form = NuevaOrdenVentaMostradorForm(request.POST, user=request.user)
        if form.is_valid():
            orden = form.save()
            messages.success(request, f'✅ Orden {orden.numero_orden_interno} creada')
            return redirect('servicio_tecnico:detalle_orden', orden_id=orden.id)
    else:
        form = NuevaOrdenVentaMostradorForm(user=request.user)
    
    return render(request, 'servicio_tecnico/form_nueva_orden_venta_mostrador.html', {
        'form': form
    })
```

### Qué Hace el Formulario

1. **Valida datos** del equipo
2. **Crea OrdenServicio** con:
   - `tipo_servicio='venta_mostrador'` (automático)
   - `estado='recepcion'`
   - Usuario actual como responsable
3. **Crea DetalleEquipo** asociado con datos del equipo
4. **Registra en HistorialOrden** con empleado correcto
5. **Redirige** a `detalle_orden` para continuar

---

## 🎨 Sección en detalle_orden.html

### Ubicación
Después de la sección de Cotización, antes de Historial.

### Condicional de Renderizado
```django
{% if orden.tipo_servicio == 'venta_mostrador' %}
    <!-- SECCIÓN 3.5 - VENTA MOSTRADOR -->
{% endif %}
```

### Estados de la Sección

#### Estado 1: Sin Venta Registrada
```html
<div class="alert alert-warning">
    <strong>⚠️ No se ha registrado información de venta</strong>
    <p>Registra la venta mostrador para completar esta orden.</p>
</div>
<button onclick="abrirModalVentaMostrador()" class="btn btn-success">
    🛒 Registrar Venta Mostrador
</button>
```

#### Estado 2: Con Venta Registrada
```html
<!-- Información de Venta -->
<div class="row mb-3">
    <div class="col-md-4">
        <strong>💰 Total:</strong> ${{ orden.venta_mostrador.total_venta|floatformat:2 }}
    </div>
    <div class="col-md-4">
        <strong>💳 Método:</strong> {{ orden.venta_mostrador.get_metodo_pago_display }}
    </div>
    <div class="col-md-4">
        <strong>📅 Registrado:</strong> {{ orden.venta_mostrador.fecha_venta|date:"d/M/Y H:i" }}
    </div>
</div>

<!-- Tabla de Piezas/Servicios -->
<table class="table table-striped">
    <thead>
        <tr>
            <th>Tipo</th>
            <th>Descripción</th>
            <th>Cantidad</th>
            <th>Precio Unit.</th>
            <th>Total</th>
            <th>Acciones</th>
        </tr>
    </thead>
    <tbody>
        {% for pieza in orden.venta_mostrador.piezas.all %}
        <tr data-pieza-id="{{ pieza.id }}">
            <td>
                <span class="badge bg-{% if pieza.tipo == 'repuesto' %}primary{% else %}success{% endif %}">
                    {{ pieza.get_tipo_display }}
                </span>
            </td>
            <td>{{ pieza.descripcion }}</td>
            <td>{{ pieza.cantidad }}</td>
            <td>${{ pieza.precio_unitario|floatformat:2 }}</td>
            <td class="precio-total">${{ pieza.precio_total|floatformat:2 }}</td>
            <td>
                <button onclick="abrirModalPiezaVentaMostrador(true, {{ pieza.id }})" 
                        class="btn btn-sm btn-warning">✏️</button>
                <button onclick="eliminarPiezaVentaMostrador({{ pieza.id }})" 
                        class="btn btn-sm btn-danger">🗑️</button>
            </td>
        </tr>
        {% endfor %}
    </tbody>
</table>

<!-- Botones de Acción -->
<button onclick="abrirModalPiezaVentaMostrador()" class="btn btn-primary">
    ➕ Agregar Pieza/Servicio
</button>
```

### Botón Convertir a Diagnóstico
**Siempre visible** (en ambos estados):
```html
<button onclick="convertirADiagnostico({{ orden.id }})" class="btn btn-danger mt-3">
    🔄 Convertir a Diagnóstico
</button>
```

---

## 🪟 Modales Bootstrap

### Modal 1: Registrar Venta Mostrador

**ID:** `modalVentaMostrador`  
**Propósito:** Capturar datos iniciales de la venta

#### Campos:
```html
<form id="formVentaMostrador">
    <div class="mb-3">
        <label>💰 Total de Venta</label>
        <input type="number" id="total_venta" step="0.01" min="0" required>
    </div>
    <div class="mb-3">
        <label>💳 Método de Pago</label>
        <select id="metodo_pago" required>
            <option value="efectivo">Efectivo</option>
            <option value="tarjeta">Tarjeta</option>
            <option value="transferencia">Transferencia</option>
            <option value="cheque">Cheque</option>
        </select>
    </div>
    <div class="mb-3">
        <label>📝 Notas (Opcional)</label>
        <textarea id="notas" rows="3"></textarea>
    </div>
</form>
```

#### Botones:
- **Guardar** → `guardarVentaMostrador()` → POST AJAX → Recarga página
- **Cancelar** → Cierra modal

---

### Modal 2: Agregar/Editar Pieza

**ID:** `modalPiezaVentaMostrador`  
**Propósito:** Agregar servicios/repuestos a la venta

#### Campos:
```html
<form id="formPiezaVentaMostrador">
    <div class="mb-3">
        <label>🔧 Tipo</label>
        <select id="tipo_pieza" required>
            <option value="repuesto">Repuesto</option>
            <option value="servicio">Servicio</option>
        </select>
    </div>
    <div class="mb-3">
        <label>📝 Descripción</label>
        <input type="text" id="descripcion_pieza" required>
    </div>
    <div class="mb-3">
        <label>🔢 Cantidad</label>
        <input type="number" id="cantidad_pieza" min="1" value="1" required>
    </div>
    <div class="mb-3">
        <label>💵 Precio Unitario</label>
        <input type="number" id="precio_unitario" step="0.01" min="0" required>
    </div>
    <div class="mb-3">
        <label>💰 Precio Total (Calculado)</label>
        <input type="number" id="precio_total" readonly>
    </div>
    <div class="mb-3">
        <label>📄 Notas</label>
        <textarea id="notas_pieza" rows="2"></textarea>
    </div>
</form>
```

#### Funcionalidades:
- **Cálculo automático:** `cantidad × precio_unitario = precio_total`
- **Modo dual:** Agregar (sin ID) o Editar (con ID)
- **Carga de datos:** GET AJAX si es edición

#### Botones:
- **Agregar/Actualizar** → `guardarPiezaVentaMostrador()` → POST AJAX → Actualiza tabla
- **Cancelar** → Cierra modal

---

### Modal 3: Convertir a Diagnóstico

**ID:** `modalConvertirDiagnostico`  
**Propósito:** Confirmar conversión y capturar motivo

#### Contenido:
```html
<div class="alert alert-warning">
    <h6><strong>🔄 ¿Qué sucederá?</strong></h6>
    <ul>
        <li>La orden actual cambiará a estado "Convertida a Diagnóstico"</li>
        <li>Se creará una NUEVA orden de tipo Diagnóstico</li>
        <li>Se copiará toda la información del equipo</li>
        <li>El monto cobrado quedará como abono previo</li>
        <li>Podrás continuar con el proceso de diagnóstico normal</li>
    </ul>
</div>

<div class="mb-3">
    <label><strong>📝 Motivo de Conversión (Obligatorio)</strong></label>
    <textarea id="motivo_conversion" rows="4" 
              placeholder="Ej: Equipo no enciende después de instalar RAM..." 
              required></textarea>
    <small class="text-muted">Mínimo 10 caracteres</small>
</div>
```

#### Validación:
- Motivo obligatorio
- Mínimo 10 caracteres
- Se valida antes de enviar

#### Botones:
- **Confirmar Conversión** → `confirmarConversionDiagnostico()` → POST AJAX → Redirige a nueva orden
- **Cancelar** → Cierra modal

---

## ⚙️ JavaScript Functions

### Archivo: `static/js/venta_mostrador.js`

### Funciones Principales

#### 1. `guardarVentaMostrador()`
**Propósito:** Registrar información inicial de venta  
**Endpoint:** `POST /ordenes/<id>/venta-mostrador/crear/`

```javascript
function guardarVentaMostrador() {
    const total = document.getElementById('total_venta').value;
    const metodo = document.getElementById('metodo_pago').value;
    const notas = document.getElementById('notas').value;
    
    // Validaciones
    if (!total || parseFloat(total) <= 0) {
        mostrarAlerta('danger', 'El total debe ser mayor a 0');
        return;
    }
    
    // AJAX POST
    fetch(`/servicio-tecnico/ordenes/${ordenId}/venta-mostrador/crear/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({ total_venta: parseFloat(total), metodo_pago: metodo, notas })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            mostrarAlerta('success', '✅ Venta registrada exitosamente');
            setTimeout(() => location.reload(), 1500);
        }
    });
}
```

**Validaciones:**
- ✅ Total > 0
- ✅ Método de pago seleccionado
- ✅ CSRF token incluido

---

#### 2. `abrirModalPiezaVentaMostrador(esEdicion, piezaId)`
**Propósito:** Abrir modal para agregar o editar pieza  
**Modos:** Creación (sin ID) o Edición (con ID)

```javascript
function abrirModalPiezaVentaMostrador(esEdicion = false, piezaId = null) {
    const modal = new bootstrap.Modal(document.getElementById('modalPiezaVentaMostrador'));
    const titulo = document.querySelector('#modalPiezaVentaMostrador .modal-title');
    const btnGuardar = document.querySelector('#modalPiezaVentaMostrador .btn-primary');
    
    // Limpiar formulario
    document.getElementById('formPiezaVentaMostrador').reset();
    
    if (esEdicion && piezaId) {
        // Modo edición
        titulo.textContent = '✏️ Editar Pieza/Servicio';
        btnGuardar.textContent = 'Actualizar';
        btnGuardar.setAttribute('data-pieza-id', piezaId);
        
        // Cargar datos
        fetch(`/servicio-tecnico/venta-mostrador/piezas/${piezaId}/`)
            .then(response => response.json())
            .then(data => {
                document.getElementById('tipo_pieza').value = data.tipo;
                document.getElementById('descripcion_pieza').value = data.descripcion;
                document.getElementById('cantidad_pieza').value = data.cantidad;
                document.getElementById('precio_unitario').value = data.precio_unitario;
                calcularSubtotalPieza();
            });
    } else {
        // Modo creación
        titulo.textContent = '➕ Agregar Pieza/Servicio';
        btnGuardar.textContent = 'Agregar';
        btnGuardar.removeAttribute('data-pieza-id');
    }
    
    modal.show();
}
```

**Características:**
- Detecta modo automáticamente (con/sin ID)
- Cambia título y texto de botón dinámicamente
- Carga datos si es edición (AJAX GET)
- Limpia formulario si es creación

---

#### 3. `guardarPiezaVentaMostrador()`
**Propósito:** Guardar pieza nueva o actualizar existente  
**Endpoints:**
- Crear: `POST /ordenes/<id>/venta-mostrador/piezas/agregar/`
- Editar: `POST /venta-mostrador/piezas/<id>/editar/`

```javascript
function guardarPiezaVentaMostrador() {
    const tipo = document.getElementById('tipo_pieza').value;
    const descripcion = document.getElementById('descripcion_pieza').value;
    const cantidad = document.getElementById('cantidad_pieza').value;
    const precioUnitario = document.getElementById('precio_unitario').value;
    const notas = document.getElementById('notas_pieza').value;
    const piezaId = document.querySelector('#modalPiezaVentaMostrador .btn-primary')
                            .getAttribute('data-pieza-id');
    
    // Validaciones
    if (!descripcion) {
        mostrarAlerta('danger', 'La descripción es obligatoria');
        return;
    }
    
    if (parseInt(cantidad) <= 0 || parseFloat(precioUnitario) <= 0) {
        mostrarAlerta('danger', 'Cantidad y precio deben ser mayores a 0');
        return;
    }
    
    // Determinar endpoint
    const url = piezaId 
        ? `/servicio-tecnico/venta-mostrador/piezas/${piezaId}/editar/`
        : `/servicio-tecnico/ordenes/${ordenId}/venta-mostrador/piezas/agregar/`;
    
    // AJAX POST
    fetch(url, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: JSON.stringify({
            tipo, descripcion, 
            cantidad: parseInt(cantidad), 
            precio_unitario: parseFloat(precioUnitario), 
            notas
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            mostrarAlerta('success', `✅ Pieza ${piezaId ? 'actualizada' : 'agregada'}`);
            setTimeout(() => location.reload(), 1500);
        }
    });
}
```

**Validaciones:**
- ✅ Descripción obligatoria
- ✅ Cantidad > 0
- ✅ Precio > 0
- ✅ Endpoint correcto según modo

---

#### 4. `eliminarPiezaVentaMostrador(piezaId)`
**Propósito:** Eliminar pieza/servicio  
**Endpoint:** `POST /venta-mostrador/piezas/<id>/eliminar/`

```javascript
function eliminarPiezaVentaMostrador(piezaId) {
    if (!confirm('¿Estás seguro de eliminar esta pieza/servicio?')) {
        return;
    }
    
    fetch(`/servicio-tecnico/venta-mostrador/piezas/${piezaId}/eliminar/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken')
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            mostrarAlerta('success', '✅ Pieza eliminada');
            // Remover fila sin recargar
            document.querySelector(`tr[data-pieza-id="${piezaId}"]`).remove();
            actualizarTotalVenta();
        }
    });
}
```

**Características:**
- Confirmación antes de eliminar
- Actualiza tabla sin recargar página
- Recalcula total automáticamente

---

#### 5. `convertirADiagnostico(ordenId)`
**Propósito:** Iniciar proceso de conversión  
**Acción:** Abre modal de confirmación

```javascript
function convertirADiagnostico(ordenId) {
    const modal = new bootstrap.Modal(document.getElementById('modalConvertirDiagnostico'));
    modal.show();
}
```

---

#### 6. `confirmarConversionDiagnostico()`
**Propósito:** Ejecutar conversión a diagnóstico  
**Endpoint:** `POST /ordenes/<id>/convertir-a-diagnostico/`

```javascript
function confirmarConversionDiagnostico() {
    const motivo = document.getElementById('motivo_conversion').value.trim();
    
    // Validación
    if (motivo.length < 10) {
        mostrarAlerta('danger', 'El motivo debe tener al menos 10 caracteres');
        return;
    }
    
    // AJAX POST
    fetch(`/servicio-tecnico/ordenes/${ordenId}/convertir-a-diagnostico/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'X-CSRFToken': getCookie('csrftoken')
        },
        body: `motivo_conversion=${encodeURIComponent(motivo)}`
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            mostrarAlerta('success', `✅ ${data.message}`);
            // Redirigir a nueva orden
            setTimeout(() => {
                window.location.href = data.redirect_url;
            }, 2000);
        }
    });
}
```

**Proceso:**
1. Valida motivo (≥ 10 caracteres)
2. Envía POST con motivo
3. Backend crea nueva orden
4. Redirige automáticamente a nueva orden

---

#### 7. `calcularSubtotalPieza()`
**Propósito:** Calcular precio total en tiempo real  
**Fórmula:** `cantidad × precio_unitario = precio_total`

```javascript
function calcularSubtotalPieza() {
    const cantidad = parseFloat(document.getElementById('cantidad_pieza').value) || 0;
    const precioUnitario = parseFloat(document.getElementById('precio_unitario').value) || 0;
    const precioTotal = cantidad * precioUnitario;
    
    document.getElementById('precio_total').value = precioTotal.toFixed(2);
}

// Event listeners
document.getElementById('cantidad_pieza').addEventListener('input', calcularSubtotalPieza);
document.getElementById('precio_unitario').addEventListener('input', calcularSubtotalPieza);
```

**Características:**
- Actualización en tiempo real
- Formato con 2 decimales
- Listeners en cantidad y precio unitario

---

### Funciones Helper

#### `getCookie(name)`
**Propósito:** Obtener CSRF token de cookies

```javascript
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
```

---

#### `mostrarAlerta(tipo, mensaje)`
**Propósito:** Mostrar alertas Bootstrap dinámicas

```javascript
function mostrarAlerta(tipo, mensaje) {
    const alertaDiv = document.createElement('div');
    alertaDiv.className = `alert alert-${tipo} alert-dismissible fade show`;
    alertaDiv.role = 'alert';
    alertaDiv.innerHTML = `
        ${mensaje}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    container.insertBefore(alertaDiv, container.firstChild);
    
    // Auto-ocultar después de 5 segundos
    setTimeout(() => alertaDiv.remove(), 5000);
}
```

**Tipos de alerta:**
- `success` → Verde
- `danger` → Rojo
- `warning` → Amarillo
- `info` → Azul

---

#### `formatearMoneda(valor)`
**Propósito:** Formatear números como moneda mexicana

```javascript
function formatearMoneda(valor) {
    return new Intl.NumberFormat('es-MX', {
        style: 'currency',
        currency: 'MXN'
    }).format(valor);
}

// Ejemplo: formatearMoneda(1500.5) → "$1,500.50"
```

---

#### `actualizarTotalVenta()`
**Propósito:** Recalcular total sumando todas las piezas

```javascript
function actualizarTotalVenta() {
    let total = 0;
    document.querySelectorAll('tr[data-pieza-id]').forEach(row => {
        const precioText = row.querySelector('.precio-total').textContent;
        const precio = parseFloat(precioText.replace('$', '').replace(',', ''));
        total += precio;
    });
    
    document.getElementById('total-venta-mostrador').textContent = formatearMoneda(total);
}
```

---

## 💡 Ejemplos de Uso

### Ejemplo 1: Crear Orden Venta Mostrador Completa

```python
# 1. Usuario hace clic en "Venta Mostrador" en inicio.html
# 2. Se abre form_nueva_orden_venta_mostrador.html
# 3. Usuario llena formulario:

Tipo Equipo: Laptop
Marca: Dell
Modelo: Latitude 5420
Número Serie: ABC123XYZ
Descripción: Cliente solicita instalación de RAM
Sucursal: Matriz

# 4. Al guardar, forms.py crea:
OrdenServicio(
    tipo_servicio='venta_mostrador',
    estado='recepcion',
    sucursal=sucursal_matriz,
    responsable_seguimiento=empleado_actual
)

DetalleEquipo(
    orden=orden_creada,
    tipo_equipo='laptop',
    marca='Dell',
    modelo='Latitude 5420',
    numero_serie='ABC123XYZ',
    falla_principal='Cliente solicita instalación de RAM'
)

# 5. Redirige a detalle_orden con SECCIÓN 3.5 visible
```

---

### Ejemplo 2: Registrar Venta con Piezas

```javascript
// 1. En detalle_orden, clic en "Registrar Venta Mostrador"
// 2. Modal se abre, usuario llena:
Total: $1500.00
Método: Efectivo
Notas: Cliente pagó en efectivo, sin cambio

// 3. JavaScript ejecuta:
guardarVentaMostrador() 
→ POST /ordenes/8/venta-mostrador/crear/
→ Response: {success: true, folio: 'VM-2025-0008'}
→ Recarga página

// 4. Ahora sección muestra venta registrada
// 5. Usuario agrega piezas:

// Pieza 1:
abrirModalPiezaVentaMostrador() // Sin parámetros = modo creación
→ Usuario llena:
   Tipo: Repuesto
   Descripción: RAM DDR4 8GB Kingston
   Cantidad: 1
   Precio Unitario: $800.00
   (Precio Total se calcula automáticamente: $800.00)
→ guardarPiezaVentaMostrador()
→ POST /ordenes/8/venta-mostrador/piezas/agregar/
→ Tabla se actualiza con nueva fila

// Pieza 2:
abrirModalPiezaVentaMostrador()
→ Usuario llena:
   Tipo: Servicio
   Descripción: Instalación de memoria RAM
   Cantidad: 1
   Precio Unitario: $200.00
   (Precio Total: $200.00)
→ guardarPiezaVentaMostrador()
→ Tabla se actualiza

// Total final mostrado: $1,000.00 (suma de todas las piezas)
```

---

### Ejemplo 3: Convertir a Diagnóstico

```javascript
// Escenario: RAM instalada no funciona, equipo no enciende

// 1. Usuario hace clic en "Convertir a Diagnóstico"
convertirADiagnostico(8) 
→ Modal se abre con advertencia

// 2. Usuario escribe motivo:
"Después de instalar la memoria RAM DDR4 8GB, el equipo no enciende. 
Se escucha un beep continuo. Se requiere diagnóstico completo del motherboard."

// 3. Usuario confirma
confirmarConversionDiagnostico()
→ Valida motivo (≥10 chars) ✅
→ POST /ordenes/8/convertir-a-diagnostico/
→ Backend ejecuta:
   - Cambia estado de orden 8 a 'convertida_a_diagnostico'
   - Crea nueva OrdenServicio (ID: 15) tipo 'diagnostico'
   - Copia DetalleEquipo de orden 8 a orden 15
   - Registra monto_abono_previo: $1500.00
   - Crea historial en ambas órdenes
→ Response: {
    success: true,
    nueva_orden_id: 15,
    nueva_orden_numero: 'ORD-2025-0015',
    redirect_url: '/servicio-tecnico/ordenes/15/'
}
→ JavaScript redirige automáticamente a orden 15

// 4. Usuario ve nueva orden con:
- Tipo: Diagnóstico
- Estado: diagnostico
- Abono previo: $1,500.00
- Referencia a orden VM-2025-0008
- DetalleEquipo completo copiado
```

---

## 🔧 Troubleshooting

### Problema 1: Modal no se Abre
**Síntomas:** Clic en botón no hace nada

**Causas posibles:**
1. JavaScript no cargado
2. Bootstrap JS no incluido
3. Error en consola

**Solución:**
```javascript
// 1. Verificar en consola del navegador:
console.log('✅ Venta Mostrador JS inicializado');

// 2. Verificar Bootstrap:
if (typeof bootstrap === 'undefined') {
    console.error('❌ Bootstrap JS no cargado');
}

// 3. Verificar ID del modal:
const modal = document.getElementById('modalVentaMostrador');
if (!modal) {
    console.error('❌ Modal no encontrado en DOM');
}
```

---

### Problema 2: CSRF Token Error (403 Forbidden)
**Síntomas:** Peticiones AJAX fallan con 403

**Causa:** CSRF token no incluido o incorrecto

**Solución:**
```javascript
// Verificar que getCookie() funciona:
const token = getCookie('csrftoken');
console.log('CSRF Token:', token);

// Verificar headers en fetch:
headers: {
    'X-CSRFToken': getCookie('csrftoken')  // ✅ Correcto
}

// En template, asegurar que existe:
{% csrf_token %}
```

---

### Problema 3: Cálculo de Subtotal no Funciona
**Síntomas:** precio_total no se actualiza

**Causa:** Event listeners no configurados

**Solución:**
```javascript
// Verificar que existen los elementos:
const cantidadInput = document.getElementById('cantidad_pieza');
const precioInput = document.getElementById('precio_unitario');

if (cantidadInput && precioInput) {
    cantidadInput.addEventListener('input', calcularSubtotalPieza);
    precioInput.addEventListener('input', calcularSubtotalPieza);
} else {
    console.error('❌ Inputs no encontrados');
}
```

---

### Problema 4: Error al Convertir - DetalleEquipo No Existe
**Síntomas:** `OrdenServicio has no detalle_equipo`

**Causa:** Bug en `convertir_a_diagnostico()` (ya corregido en FASE 4)

**Verificación:**
```python
# En models.py, verificar que usa try-except:
try:
    detalle_original = self.detalle_equipo
    # Copiar campos...
except DetalleEquipo.DoesNotExist:
    # Crear DetalleEquipo básico
    DetalleEquipo.objects.create(...)
```

---

### Problema 5: Usuario sin Empleado Asociado
**Síntomas:** Error al crear orden: "Tu usuario no tiene un empleado asociado"

**Causa:** User no tiene relación OneToOne con Empleado

**Solución:**
```python
# En Django Admin, crear Empleado para el User:
from inventario.models import Empleado

empleado = Empleado.objects.create(
    user=request.user,
    nombre_completo='Juan Pérez',
    sucursal=sucursal_matriz,
    puesto='Técnico'
)
```

---

## 📊 Endpoints AJAX Usados

| Método | URL | Propósito | Request Body | Response |
|--------|-----|-----------|--------------|----------|
| POST | `/ordenes/<id>/venta-mostrador/crear/` | Crear venta mostrador | `{total_venta, metodo_pago, notas}` | `{success, folio}` |
| POST | `/ordenes/<id>/venta-mostrador/piezas/agregar/` | Agregar pieza | `{tipo, descripcion, cantidad, precio_unitario, notas}` | `{success, pieza_id}` |
| GET | `/venta-mostrador/piezas/<id>/` | Obtener datos de pieza | - | `{tipo, descripcion, cantidad, precio_unitario, notas}` |
| POST | `/venta-mostrador/piezas/<id>/editar/` | Editar pieza | `{tipo, descripcion, cantidad, precio_unitario, notas}` | `{success}` |
| POST | `/venta-mostrador/piezas/<id>/eliminar/` | Eliminar pieza | - | `{success}` |
| POST | `/ordenes/<id>/convertir-a-diagnostico/` | Convertir a diagnóstico | `motivo_conversion` | `{success, nueva_orden_id, redirect_url}` |

---

## ✅ Checklist de Implementación

### Formulario de Creación
- [x] Template `form_nueva_orden_venta_mostrador.html` creado
- [x] Form `NuevaOrdenVentaMostradorForm` en forms.py
- [x] Vista `crear_orden_venta_mostrador` en views.py
- [x] URL pattern agregado
- [x] Botón en inicio.html
- [x] Fix: Usuario → Empleado en historial

### Sección en Detalle Orden
- [x] SECCIÓN 3.5 agregada con condicional
- [x] Estado sin venta mostrada correctamente
- [x] Estado con venta mostrada correctamente
- [x] Tabla de piezas funcional
- [x] Botones de acción presentes

### Modales
- [x] Modal Venta Mostrador
- [x] Modal Pieza Venta Mostrador
- [x] Modal Convertir Diagnóstico
- [x] Bootstrap 5 funcional en todos

### JavaScript
- [x] Archivo venta_mostrador.js creado (~700 líneas)
- [x] Función guardarVentaMostrador()
- [x] Función abrirModalPiezaVentaMostrador()
- [x] Función guardarPiezaVentaMostrador()
- [x] Función eliminarPiezaVentaMostrador()
- [x] Función convertirADiagnostico()
- [x] Función confirmarConversionDiagnostico()
- [x] Función calcularSubtotalPieza()
- [x] Helpers: getCookie, mostrarAlerta, formatearMoneda
- [x] Event listeners configurados
- [x] Carga condicional en template

### Bugs Corregidos
- [x] HistorialOrden.usuario (User → Empleado)
- [x] convertir_a_diagnostico (hasattr → try-except)
- [x] Nombres de campos (gama_equipo → gama)
- [x] Garantía de DetalleEquipo en nueva orden

---

## 📚 Referencias Adicionales

- **CHANGELOG_VENTA_MOSTRADOR_FASE4.md** - Changelog detallado
- **VENTAS_MOSTRADOR_PLAN_IMPLEMENTACION.md** - Plan completo
- **CHANGELOG_VENTA_MOSTRADOR_FASE3.md** - Backend AJAX
- **REFERENCIA_RAPIDA_VENTA_MOSTRADOR_FASE3.md** - Backend reference

---

**Última Actualización:** 9 de Octubre, 2025  
**Autor:** GitHub Copilot + Usuario  
**Versión:** 1.0
