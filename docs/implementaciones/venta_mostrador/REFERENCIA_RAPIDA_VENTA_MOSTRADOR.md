# 🚀 Referencia Rápida - Sistema Venta Mostrador

## 📌 Guía Rápida para Desarrolladores

### 🔑 Conceptos Clave

**Venta Mostrador** = Servicio DIRECTO sin diagnóstico técnico previo
- Cliente espera o regresa el mismo día
- No pasa por cotización
- Folio: `VM-2025-0001`
- Estados: `espera → recepcion → reparacion → control_calidad → finalizado → entregado`

**Orden con Diagnóstico** = Servicio COMPLETO con análisis técnico
- Cliente deja equipo varios días
- Pasa por diagnóstico y cotización
- Folio: `ORD-2025-0001`
- Estados: `espera → recepcion → diagnostico → cotizacion → ... → entregado`

---

## 🎯 Casos de Uso Principales

### 1️⃣ Venta de Paquete Premium
```python
# El cliente quiere mejorar su laptop
orden = OrdenServicio.objects.create(
    sucursal=sucursal,
    responsable_seguimiento=empleado,
    tecnico_asignado_actual=tecnico,
    tipo_servicio='venta_mostrador',  # ← IMPORTANTE
    estado='recepcion'
)

venta = VentaMostrador.objects.create(
    orden=orden,
    paquete='premium',  # Precio: $5,500
    # genera_comision se activa automáticamente
)

# El paquete incluye:
# - RAM 16GB DDR5 Samsung
# - SSD 1TB
# - Kit de Limpieza de regalo
```

### 2️⃣ Venta de Pieza Individual
```python
# Cliente compra RAM sin paquete
venta = VentaMostrador.objects.create(
    orden=orden,
    paquete='ninguno',
    incluye_cambio_pieza=True,
    costo_cambio_pieza=200.00
)

pieza = PiezaVentaMostrador.objects.create(
    venta_mostrador=venta,
    descripcion_pieza="RAM 8GB DDR4 Kingston",
    cantidad=1,
    precio_unitario=800.00
)

# Total: $1,000 (pieza + instalación)
```

### 3️⃣ Conversión a Diagnóstico (Falla técnica)
```python
# La instalación falla, necesita diagnóstico
try:
    nueva_orden = orden.convertir_a_diagnostico(
        usuario=request.user.empleado,
        motivo_conversion="Equipo no enciende después de instalar RAM"
    )
    
    # Resultado:
    # - Orden original: estado = 'convertida_a_diagnostico'
    # - Nueva orden: tipo_servicio = 'diagnostico'
    # - nueva_orden.monto_abono_previo = $1,000
    # - Historial completo en ambas órdenes
    
except ValueError as e:
    # Manejo de error si no se puede convertir
    messages.error(request, str(e))
```

---

## 📦 Paquetes Disponibles

| Código | Nombre | Precio | Componentes | Comisión |
|--------|--------|--------|-------------|----------|
| `premium` | Solución Premium | $5,500 | RAM 16GB + SSD 1TB + Kit | ✅ Sí |
| `oro` | Solución Oro | $3,850 | RAM 8GB + SSD 1TB | ✅ Sí |
| `plata` | Solución Plata | $2,900 | SSD 1TB | ✅ Sí |
| `ninguno` | Sin Paquete | $0 | Sin componentes | ❌ No |

### Uso de Constantes
```python
from config.constants import (
    PAQUETES_CHOICES,
    PRECIOS_PAQUETES,
    DESCRIPCION_PAQUETES,
    obtener_precio_paquete,
    paquete_genera_comision,
    obtener_componentes_paquete
)

# Obtener precio
precio = obtener_precio_paquete('premium')  # 5500.00

# Verificar si genera comisión
if paquete_genera_comision('premium'):
    calcular_comision()

# Obtener componentes
componentes = obtener_componentes_paquete('premium')
# [{'tipo': 'RAM', 'capacidad': '16GB', ...}, ...]
```

---

## 🔐 Validaciones Automáticas

### En `OrdenServicio.clean()`

#### ❌ Error: Venta mostrador con cotización
```python
orden.tipo_servicio = 'venta_mostrador'
orden.cotizacion = cotizacion  # ← PROHIBIDO

# ValidationError: "❌ Una orden de venta mostrador no puede 
# tener cotización. Si necesita diagnóstico, debe convertirse primero."
```

#### ❌ Error: Estados inválidos
```python
orden.tipo_servicio = 'venta_mostrador'
orden.estado = 'diagnostico'  # ← PROHIBIDO

# ValidationError: "❌ Estado 'En Diagnóstico' no es válido 
# para ventas mostrador."
```

#### ❌ Error: Conversión sin monto de abono
```python
nueva_orden.orden_venta_mostrador_previa = orden_vm
nueva_orden.monto_abono_previo = 0  # ← PROHIBIDO

# ValidationError: "❌ Si hay una orden de venta mostrador previa, 
# debe registrar el monto de abono."
```

---

## 💻 Queries Comunes

### Obtener todas las ventas mostrador de hoy
```python
from django.utils import timezone

ventas_hoy = VentaMostrador.objects.filter(
    fecha_venta__date=timezone.now().date()
)
```

### Obtener ventas por paquete
```python
ventas_premium = VentaMostrador.objects.filter(paquete='premium')
total_ingresos = sum(v.total_venta for v in ventas_premium)
```

### Obtener órdenes convertidas
```python
ordenes_convertidas = OrdenServicio.objects.filter(
    estado='convertida_a_diagnostico'
)

# Obtener la nueva orden generada
for orden in ordenes_convertidas:
    nueva = orden.orden_diagnostico_posterior.first()
    print(f"Original: {orden.numero_orden_interno}")
    print(f"Nueva: {nueva.numero_orden_interno}")
```

### Calcular total con piezas
```python
venta = VentaMostrador.objects.get(folio_venta='VM-2025-0001')

print(f"Paquete: ${venta.costo_paquete}")
print(f"Servicios: ${venta.costo_cambio_pieza + venta.costo_limpieza}")
print(f"Piezas: ${venta.total_piezas_vendidas}")
print(f"TOTAL: ${venta.total_venta}")
```

### Filtrar por tipo de servicio
```python
# Solo ventas mostrador
ventas = OrdenServicio.objects.filter(tipo_servicio='venta_mostrador')

# Solo diagnósticos
diagnosticos = OrdenServicio.objects.filter(tipo_servicio='diagnostico')

# Ventas con control de calidad opcional
sin_qa = OrdenServicio.objects.filter(
    tipo_servicio='venta_mostrador',
    control_calidad_requerido=False
)
```

---

## 🎨 En Templates

### Detectar tipo de servicio
```django
{% if orden.tipo_servicio == 'venta_mostrador' %}
    <span class="badge bg-warning">Venta Mostrador</span>
    
    {% if orden.venta_mostrador %}
        <p>Folio: {{ orden.venta_mostrador.folio_venta }}</p>
        <p>Paquete: {{ orden.venta_mostrador.get_paquete_display }}</p>
        <p>Total: ${{ orden.venta_mostrador.total_venta }}</p>
    {% endif %}
    
{% elif orden.tipo_servicio == 'diagnostico' %}
    <span class="badge bg-primary">Con Diagnóstico</span>
    
    {% if orden.orden_venta_mostrador_previa %}
        <div class="alert alert-info">
            ⚠️ Convertida desde Venta Mostrador
            <a href="{% url 'detalle_orden' orden.orden_venta_mostrador_previa.id %}">
                {{ orden.orden_venta_mostrador_previa.numero_orden_interno }}
            </a>
            | Monto abonado: ${{ orden.monto_abono_previo }}
        </div>
    {% endif %}
{% endif %}
```

### Mostrar piezas vendidas
```django
{% if venta_mostrador.piezas_vendidas.exists %}
    <h5>Piezas Vendidas</h5>
    <table class="table">
        {% for pieza in venta_mostrador.piezas_vendidas.all %}
        <tr>
            <td>{{ pieza.descripcion_pieza }}</td>
            <td>x{{ pieza.cantidad }}</td>
            <td>${{ pieza.precio_unitario }}</td>
            <td>${{ pieza.subtotal }}</td>
        </tr>
        {% endfor %}
    </table>
{% endif %}
```

---

## 🛠️ En Django Admin

### Filtrar órdenes
```python
# En servicio_tecnico/admin.py
class OrdenServicioAdmin(admin.ModelAdmin):
    list_filter = [
        'tipo_servicio',  # ← NUEVO FILTRO
        'estado',
        'sucursal',
    ]
    
    search_fields = [
        'numero_orden_interno',
        'venta_mostrador__folio_venta',  # ← Buscar por folio VM
    ]
```

### Inline de piezas
```python
class PiezaVentaMostradorInline(admin.TabularInline):
    model = PiezaVentaMostrador
    extra = 1
    fields = ['descripcion_pieza', 'cantidad', 'precio_unitario', 'subtotal']
    readonly_fields = ['subtotal']

class VentaMostradorAdmin(admin.ModelAdmin):
    inlines = [PiezaVentaMostradorInline]
```

---

## 🔍 Debugging

### Verificar tipo de orden
```python
# En shell de Django
from servicio_tecnico.models import OrdenServicio

orden = OrdenServicio.objects.get(numero_orden_interno='VM-2025-0001')

print(f"Tipo: {orden.tipo_servicio}")
print(f"Tiene venta mostrador: {hasattr(orden, 'venta_mostrador')}")
print(f"Tiene cotización: {hasattr(orden, 'cotizacion')}")

if orden.orden_venta_mostrador_previa:
    print(f"Convertida desde: {orden.orden_venta_mostrador_previa.numero_orden_interno}")
```

### Validar piezas
```python
venta = VentaMostrador.objects.get(folio_venta='VM-2025-0001')

print(f"Piezas registradas: {venta.piezas_vendidas.count()}")

for pieza in venta.piezas_vendidas.all():
    print(f"- {pieza.descripcion_pieza}: ${pieza.subtotal}")
```

---

## ⚠️ Errores Comunes

### Error 1: Intentar agregar cotización a venta mostrador
```python
# ❌ MAL
orden.tipo_servicio = 'venta_mostrador'
Cotizacion.objects.create(orden=orden)  # ValidationError

# ✅ BIEN - Convertir primero
nueva_orden = orden.convertir_a_diagnostico(usuario, motivo)
Cotizacion.objects.create(orden=nueva_orden)
```

### Error 2: Estado inválido
```python
# ❌ MAL
orden.tipo_servicio = 'venta_mostrador'
orden.estado = 'esperando_piezas'  # ValidationError

# ✅ BIEN - Estados válidos
orden.estado = 'reparacion'  # OK
orden.estado = 'control_calidad'  # OK
orden.estado = 'finalizado'  # OK
```

### Error 3: Olvidar activar comisión
```python
# ❌ Innecesario - Se activa automáticamente
venta = VentaMostrador(paquete='premium')
venta.genera_comision = True  # Redundante
venta.save()

# ✅ BIEN - Automático en save()
venta = VentaMostrador(paquete='premium')
venta.save()
# venta.genera_comision ya es True
```

---

## 📚 Referencias Rápidas

### Campos Clave
- `OrdenServicio.tipo_servicio`: 'diagnostico' | 'venta_mostrador'
- `OrdenServicio.control_calidad_requerido`: Boolean
- `VentaMostrador.paquete`: 'premium' | 'oro' | 'plata' | 'ninguno'
- `VentaMostrador.genera_comision`: Boolean (auto)
- `PiezaVentaMostrador.subtotal`: Property calculada

### Métodos Importantes
- `orden.convertir_a_diagnostico(usuario, motivo)`: Conversión
- `orden.clean()`: Validaciones automáticas
- `venta.total_venta`: Total incluyendo piezas
- `venta.total_piezas_vendidas`: Solo piezas

### URLs Esperadas (FASE 2)
- `/servicio/crear-venta-mostrador/<orden_id>/`
- `/servicio/agregar-pieza/<venta_id>/`
- `/servicio/convertir-diagnostico/<orden_id>/`

---

**Versión:** 1.0  
**Última Actualización:** 8 de Octubre, 2025  
**Estado:** ✅ FASE 1 Lista para Usar
