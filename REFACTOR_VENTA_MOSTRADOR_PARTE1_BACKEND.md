# 🔧 REFACTORIZACIÓN: Venta Mostrador como Complemento - PARTE 1 (BACKEND)

**Fecha:** 9 de Octubre, 2025  
**Versión:** 2.0 - SIMPLIFICADA (Sin compatibilidad con sistema antiguo)  
**Estado:** 📋 PLANIFICACIÓN - NO IMPLEMENTADO AÚN  
**Decisión:** ⚡ Eliminación completa - No hay datos en producción

---

## 📋 ÍNDICE

1. [Resumen Ejecutivo](#-resumen-ejecutivo)
2. [Análisis del Sistema](#-análisis-del-sistema)
3. [FASE 1: Modelos](#-fase-1-modelos-2-horas)
4. [FASE 2: Vistas Backend](#-fase-2-vistas-backend-2-horas)
5. [FASE 3: Admin](#-fase-3-admin-1-hora)
6. [Tests](#-tests)
7. [Checklist](#-checklist-completo)

---

## 🎯 RESUMEN EJECUTIVO

### **Problema Actual**
- Venta Mostrador es un "tipo de orden" excluyente
- No se puede vender accesorios en órdenes de diagnóstico
- Si venta mostrador falla, se crea NUEVA orden (duplicación)

### **Solución**
- Venta Mostrador = **complemento opcional** de CUALQUIER orden
- Coexiste con cotización libremente
- ⛔ **ELIMINAR** sistema de conversión completamente

### **Decisión Arquitectónica**
Como el proyecto **NO está en producción** y solo hay **1 registro de prueba**:
- ✅ **Eliminar** campos de conversión del modelo
- ✅ **Eliminar** estado 'convertida_a_diagnostico'
- ✅ **Eliminar** método `convertir_a_diagnostico()`
- ✅ **Eliminar** vista y URL de conversión
- ❌ **NO** mantener compatibilidad retroactiva

---

## 🔍 ANÁLISIS DEL SISTEMA

### **Antes (Restrictivo)**
```python
# Una orden puede ser DIAGNÓSTICO o VENTA MOSTRADOR (no ambos)
if orden.tipo_servicio == 'diagnostico':
    orden.cotizacion ✅  # Permitido
    orden.venta_mostrador ❌  # BLOQUEADO

if orden.tipo_servicio == 'venta_mostrador':
    orden.cotizacion ❌  # BLOQUEADO
    orden.venta_mostrador ✅  # Permitido
```

### **Después (Flexible)**
```python
# Una orden puede tener AMBOS complementos
orden.tipo_servicio = 'diagnostico' OR 'venta_mostrador'
orden.cotizacion ✅ OPCIONAL
orden.venta_mostrador ✅ OPCIONAL
# Ambos pueden coexistir sin problemas
```

### **Archivos Principales a Modificar**

| Archivo | Ubicación | Líneas Clave | Acción |
|---------|-----------|--------------|--------|
| `models.py` | servicio_tecnico/ | 296-310 | ⛔ ELIMINAR validaciones |
| `models.py` | servicio_tecnico/ | 150-180 | ⛔ ELIMINAR campos conversión |
| `models.py` | servicio_tecnico/ | 80 | ⛔ ELIMINAR estado obsoleto |
| `models.py` | servicio_tecnico/ | 462-600 | ⛔ ELIMINAR método conversión |
| `views.py` | servicio_tecnico/ | 1264 | ✅ CAMBIAR lógica carga contexto |
| `views.py` | servicio_tecnico/ | 2588-2660 | ✅ ELIMINAR validación tipo |
| `views.py` | servicio_tecnico/ | 2893-3000 | ⛔ ELIMINAR vista conversión |
| `urls.py` | servicio_tecnico/ | 80 | ⛔ ELIMINAR URL conversión |
| `admin.py` | servicio_tecnico/ | 243-266 | ✅ ACTUALIZAR badges |

---

## 🔧 FASE 1: MODELOS (2 horas)

### **1.1. ELIMINAR Validaciones Restrictivas**

**ARCHIVO:** `servicio_tecnico/models.py`  
**LÍNEAS:** 296-310

**❌ BUSCAR Y ELIMINAR:**
```python
    def clean(self):
        # Validar que venta mostrador no tenga cotización
        if self.tipo_servicio == 'venta_mostrador':
            if hasattr(self, 'cotizacion'):
                raise ValidationError(
                    'Una orden de venta mostrador no puede tener cotización'
                )
        
        # Validar que diagnóstico no tenga VM (salvo conversión)
        if self.tipo_servicio == 'diagnostico':
            if hasattr(self, 'venta_mostrador') and not self.orden_venta_mostrador_previa:
                raise ValidationError(
                    'Una orden de diagnóstico no puede tener venta mostrador'
                )
```

**✅ REEMPLAZAR POR (versión simplificada):**
```python
    def clean(self):
        """
        Validaciones del modelo OrdenServicio.
        
        ACTUALIZACIÓN (Oct 2025): Venta mostrador ahora es un complemento opcional.
        - Una orden puede tener cotización, venta_mostrador, o ambos
        - No hay restricciones basadas en tipo_servicio
        """
        # Validaciones de negocio (no relacionadas con VM)
        if self.estado == 'entregado' and not self.fecha_entrega:
            raise ValidationError('Debe especificar fecha de entrega')
        
        # ... (mantener otras validaciones no relacionadas con tipo_servicio) ...
```

**🎓 Explicación para principiante:**
- **Antes:** El método `clean()` bloqueaba tener cotización + VM simultáneamente
- **Ahora:** Eliminamos esas validaciones para permitir coexistencia
- **`clean()`:** Método especial de Django que se ejecuta antes de guardar para validar datos
- **`ValidationError`:** Error que Django muestra al usuario si algo está mal

---

### **1.2. ELIMINAR Campos de Conversión**

**ARCHIVO:** `servicio_tecnico/models.py`  
**LÍNEAS:** ~150-180

**❌ BUSCAR Y ELIMINAR COMPLETAMENTE:**
```python
    # Campos de conversión
    orden_venta_mostrador_previa = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orden_diagnostico_posterior',
        verbose_name="Orden VM Previa"
    )
    fecha_conversion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Fecha de Conversión"
    )
    notas_conversion = models.TextField(
        blank=True,
        verbose_name="Notas de Conversión"
    )
```

**🎓 Explicación para principiante:**
- **`ForeignKey('self')`:** Campo que apunta a otra orden del mismo modelo
- **`on_delete=models.SET_NULL`:** Si se elimina la orden referenciada, este campo se pone en NULL
- **Decisión:** Como no hay datos en producción, eliminamos completamente estos campos
- **Efecto:** La base de datos ya no reservará espacio para estos campos

---

### **1.3. ELIMINAR Estado 'convertida_a_diagnostico'**

**ARCHIVO:** `servicio_tecnico/models.py`  
**LÍNEA:** ~80

**❌ BUSCAR:**
```python
    ESTADO_CHOICES = [
        ('espera', 'En espera de atención'),
        ('recepcion', 'Recepción'),
        ('diagnostico', 'En diagnóstico'),
        ('cotizado', 'Cotizado'),
        # ... otros estados ...
        ('convertida_a_diagnostico', 'Convertida a Diagnóstico'),  # ⛔ ELIMINAR ESTA LÍNEA
    ]
```

**✅ ELIMINAR la línea completa** (solo elimina la línea de 'convertida_a_diagnostico')

**🎓 Explicación para principiante:**
- **`ESTADO_CHOICES`:** Lista de opciones válidas para el campo `estado`
- **Tuple format:** `('valor_bd', 'Texto visible')`
- **Eliminar:** Como no usaremos más conversiones, quitamos esta opción
- **Django:** Automáticamente no mostrará esta opción en formularios

---

### **1.4. ELIMINAR Método convertir_a_diagnostico()**

**ARCHIVO:** `servicio_tecnico/models.py`  
**LÍNEAS:** 462-600 (aprox. 138 líneas)

**❌ BUSCAR Y ELIMINAR TODO EL MÉTODO:**
```python
    def convertir_a_diagnostico(self, notas='', usuario=None):
        """
        Convierte una orden de venta mostrador a diagnóstico.
        Crea una NUEVA orden de tipo diagnóstico y vincula a la original.
        """
        # Validaciones
        if self.tipo_servicio != 'venta_mostrador':
            raise ValueError("...")
        
        # Crear nueva orden
        orden_diagnostico = OrdenServicio.objects.create(...)
        
        # ... (~130 líneas más) ...
        
        return orden_diagnostico
```

**✅ OPCIONAL - Agregar comentario explicativo:**
```python
    # ⛔ MÉTODO ELIMINADO: convertir_a_diagnostico()
    # 
    # Este método creaba una NUEVA orden cuando una venta mostrador fallaba.
    # En el sistema refactorizado (Oct 2025), ya no es necesario:
    # 
    # - Venta mostrador es un complemento opcional
    # - Puede coexistir con cotización en la misma orden
    # - No se requiere duplicar órdenes
```

**🎓 Explicación para principiante:**
- **Método largo:** ~138 líneas que manejaban la conversión (crear nueva orden)
- **Lógica compleja:** Copiaba datos, actualizaba estados, creaba relaciones
- **Eliminado:** Ya no lo necesitamos porque una orden puede tener ambos complementos
- **Simplificación:** Código más limpio y mantenible

---

### **1.5. Actualizar Docstring del Modelo**

**ARCHIVO:** `servicio_tecnico/models.py`  
**LÍNEA:** ~20 (inicio de clase OrdenServicio)

**BUSCAR:**
```python
class OrdenServicio(models.Model):
    """
    Modelo principal para órdenes de servicio técnico.
    
    Puede ser de dos tipos:
    - diagnostico: Requiere diagnóstico y cotización
    - venta_mostrador: Venta directa sin diagnóstico
    """
```

**✅ REEMPLAZAR POR:**
```python
class OrdenServicio(models.Model):
    """
    Modelo principal para órdenes de servicio técnico.
    
    ACTUALIZACIÓN (Oct 2025): Sistema refactorizado
    
    tipo_servicio indica el flujo PRINCIPAL:
    - 'diagnostico': Servicio con diagnóstico técnico (cotización)
    - 'venta_mostrador': Servicio directo sin diagnóstico
    
    COMPLEMENTOS OPCIONALES (pueden coexistir):
    - cotizacion: Reparación/diagnóstico (OneToOne con Cotizacion)
    - venta_mostrador: Ventas adicionales (OneToOne con VentaMostrador)
    
    Una orden puede tener:
    - Solo cotización (diagnóstico puro)
    - Solo venta_mostrador (venta directa)
    - Ambos (diagnóstico + ventas adicionales)
    - Ninguno (orden recién creada)
    """
```

**🎓 Explicación para principiante:**
- **Docstring:** Comentario especial que aparece en ayuda de Python (`help(OrdenServicio)`)
- **Triple comillas:** Permite comentarios multilínea
- **Actualizado:** Refleja la nueva filosofía del sistema
- **OneToOne:** Relación 1-a-1 (una orden tiene máximo una cotización)

---

### **1.6. Crear Migración**

**Después de todos los cambios:**

```bash
# Generar migraciones
python manage.py makemigrations servicio_tecnico

# Revisar migración generada
# Debe incluir:
# - RemoveField: orden_venta_mostrador_previa
# - RemoveField: fecha_conversion
# - RemoveField: notas_conversion
# - AlterField: estado (sin 'convertida_a_diagnostico')

# Aplicar migraciones
python manage.py migrate
```

**🎓 Explicación para principiante:**
- **makemigrations:** Django detecta cambios en models.py y crea archivo de migración
- **RemoveField:** Operación que elimina campos de la base de datos
- **migrate:** Aplica los cambios a la base de datos real
- **Reversible:** Si algo sale mal, puedes hacer `migrate` a versión anterior

---

## 🌐 FASE 2: VISTAS BACKEND (2 horas)

### **2.1. Actualizar detalle_orden() - Cargar Contexto Siempre**

**ARCHIVO:** `servicio_tecnico/views.py`  
**LÍNEA:** ~1264

**❌ BUSCAR (condicional restrictivo):**
```python
def detalle_orden(request, orden_id):
    orden = get_object_or_404(OrdenServicio, id=orden_id)
    
    # Cargar venta mostrador solo si es tipo venta_mostrador
    context = {'orden': orden}
    
    if orden.tipo_servicio == 'venta_mostrador':  # ⛔ ELIMINAR CONDICIONAL
        context['form_venta_mostrador'] = VentaMostradorForm()
        context['form_pieza_venta_mostrador'] = PiezaVentaMostradorForm()
        # ...
    
    return render(request, 'detalle_orden.html', context)
```

**✅ REEMPLAZAR POR (siempre cargar):**
```python
def detalle_orden(request, orden_id):
    """
    Vista de detalle de una orden de servicio.
    
    ACTUALIZACIÓN (Oct 2025): El contexto de venta_mostrador se carga
    SIEMPRE, independientemente del tipo_servicio, porque ahora es
    un complemento opcional disponible para todas las órdenes.
    """
    orden = get_object_or_404(OrdenServicio, id=orden_id)
    
    # Cargar contexto base
    context = {
        'orden': orden,
    }
    
    # ✅ NUEVO: Cargar contexto de venta mostrador SIEMPRE
    # (Ya no depende de tipo_servicio)
    try:
        venta_mostrador = orden.venta_mostrador
    except VentaMostrador.DoesNotExist:
        venta_mostrador = None
    
    context.update({
        'venta_mostrador': venta_mostrador,
        'form_venta_mostrador': VentaMostradorForm(),
        'form_pieza_venta_mostrador': PiezaVentaMostradorForm(),
        
        # Información contextual para la UI
        'es_orden_diagnostico': orden.tipo_servicio == 'diagnostico',
        'es_orden_directa': orden.tipo_servicio == 'venta_mostrador',
        'tiene_cotizacion': hasattr(orden, 'cotizacion'),
        'tiene_venta_mostrador': venta_mostrador is not None,
    })
    
    return render(request, 'servicio_tecnico/detalle_orden.html', context)
```

**🎓 Explicación para principiante:**
- **`get_object_or_404`:** Busca la orden o devuelve error 404 si no existe
- **`context`:** Diccionario con datos que se envían al template HTML
- **`try/except`:** Manejo de error cuando la orden no tiene venta_mostrador
- **`.update()`:** Método que agrega más items al diccionario context
- **Cambio clave:** YA NO verificamos `if tipo_servicio == 'venta_mostrador'`

---

### **2.2. Actualizar crear_venta_mostrador() - Eliminar Validación**

**ARCHIVO:** `servicio_tecnico/views.py`  
**LÍNEAS:** 2588-2660

**❌ BUSCAR (validación restrictiva):**
```python
@login_required
def crear_venta_mostrador(request, orden_id):
    orden = get_object_or_404(OrdenServicio, id=orden_id)
    
    # ⛔ ELIMINAR ESTA VALIDACIÓN
    if orden.tipo_servicio != 'venta_mostrador':
        return JsonResponse({
            'success': False,
            'error': 'Esta orden no es de tipo venta mostrador'
        }, status=400)
    
    # ... resto del código ...
```

**✅ REEMPLAZAR POR (sin validación de tipo):**
```python
@login_required
def crear_venta_mostrador(request, orden_id):
    """
    Crea una venta mostrador para cualquier orden.
    
    ACTUALIZACIÓN (Oct 2025): Ya no valida tipo_servicio porque
    venta_mostrador es un complemento opcional de cualquier orden.
    """
    orden = get_object_or_404(OrdenServicio, id=orden_id)
    
    # Validar que no exista ya una venta mostrador
    if hasattr(orden, 'venta_mostrador'):
        return JsonResponse({
            'success': False,
            'error': 'Esta orden ya tiene una venta mostrador registrada'
        }, status=400)
    
    if request.method == 'POST':
        form = VentaMostradorForm(request.POST)
        
        if form.is_valid():
            venta = form.save(commit=False)
            venta.orden = orden
            venta.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Venta mostrador creada exitosamente',
                'es_complemento': orden.tipo_servicio == 'diagnostico',  # ✅ Info contextual
                'redirect_url': reverse('servicio_tecnico:detalle_orden', args=[orden.id])
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Formulario inválido',
                'form_errors': form.errors
            }, status=400)
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)
```

**🎓 Explicación para principiante:**
- **`@login_required`:** Decorador que requiere que el usuario esté logueado
- **`request.method == 'POST'`:** Verifica que sea una petición de envío de formulario
- **`commit=False`:** Crea el objeto pero NO lo guarda aún en la BD
- **`JsonResponse`:** Respuesta en formato JSON para peticiones AJAX
- **Cambio clave:** ⛔ Ya NO verificamos `if tipo_servicio != 'venta_mostrador'`

---

### **2.3. ELIMINAR Vista convertir_venta_a_diagnostico()**

**ARCHIVO:** `servicio_tecnico/views.py`  
**LÍNEAS:** 2893-3000 (aprox. 107 líneas)

**❌ BUSCAR Y ELIMINAR TODO:**
```python
@login_required
def convertir_venta_a_diagnostico(request, orden_id):
    """
    Vista para convertir una orden de venta mostrador a diagnóstico.
    Crea una nueva orden vinculada a la original.
    """
    orden = get_object_or_404(OrdenServicio, id=orden_id)
    
    # Validaciones...
    # Crear nueva orden...
    # ... (~100 líneas) ...
    
    return JsonResponse(data)
```

**⛔ ELIMINAR COMPLETAMENTE** - Borrar todo el método

**🎓 Explicación para principiante:**
- **Esta vista:** Manejaba la conversión (crear nueva orden)
- **Ya no necesaria:** El nuevo sistema no requiere conversiones
- **Efecto:** Si alguien intenta acceder a esta URL, dará error 404 (correcto)

---

### **2.4. ELIMINAR URL de Conversión**

**ARCHIVO:** `servicio_tecnico/urls.py`  
**LÍNEA:** ~80

**❌ BUSCAR Y ELIMINAR:**
```python
    path('ordenes/<int:orden_id>/convertir-diagnostico/', 
         views.convertir_venta_a_diagnostico, 
         name='convertir_venta_diagnostico'),
```

**⛔ ELIMINAR la línea completa**

**🎓 Explicación para principiante:**
- **`path()`:** Define una URL que Django reconoce
- **`<int:orden_id>`:** Captura un número de la URL y lo pasa como parámetro
- **`name=`:** Nombre interno para hacer reverse URLs
- **Eliminado:** La URL ya no existirá (404 si alguien la intenta usar)

---

## 🎨 FASE 3: ADMIN (1 hora)

### **3.1. Actualizar tipo_servicio_badge() - Agregar Indicadores**

**ARCHIVO:** `servicio_tecnico/admin.py`  
**LÍNEAS:** 243-266

**❌ BUSCAR (versión simple):**
```python
    def tipo_servicio_badge(self, obj):
        """Muestra badge de tipo de servicio"""
        if obj.tipo_servicio == 'venta_mostrador':
            return format_html(
                '<span class="badge badge-warning">Venta Mostrador</span>'
            )
        return format_html(
            '<span class="badge badge-info">Diagnóstico</span>'
        )
    tipo_servicio_badge.short_description = 'Tipo'
```

**✅ REEMPLAZAR POR (con indicadores de complementos):**
```python
    def tipo_servicio_badge(self, obj):
        """
        Muestra badge de tipo de servicio + indicadores de complementos.
        
        ACTUALIZACIÓN (Oct 2025): Ahora muestra iconos adicionales
        para cotización y venta_mostrador si existen.
        """
        # Badge principal de tipo
        if obj.tipo_servicio == 'venta_mostrador':
            badge = '<span class="badge badge-warning">🛒 Directo</span>'
        else:
            badge = '<span class="badge badge-info">🔧 Diagnóstico</span>'
        
        # ✅ NUEVO: Indicadores de complementos
        indicadores = []
        
        if hasattr(obj, 'cotizacion') and obj.cotizacion:
            indicadores.append('<span class="badge badge-primary" title="Tiene cotización">📋</span>')
        
        if hasattr(obj, 'venta_mostrador') and obj.venta_mostrador:
            indicadores.append('<span class="badge badge-success" title="Tiene venta mostrador">💰</span>')
        
        # Combinar badge + indicadores
        if indicadores:
            return format_html(
                '{} {}',
                mark_safe(badge),
                mark_safe(' '.join(indicadores))
            )
        
        return format_html(badge)
    
    tipo_servicio_badge.short_description = 'Tipo / Complementos'
```

**Resultado visual en admin:**
```
🔧 Diagnóstico 📋 💰  (tiene cotización + venta mostrador)
🛒 Directo 💰        (solo venta mostrador)
🔧 Diagnóstico 📋    (solo cotización)
```

**🎓 Explicación para principiante:**
- **`format_html()`:** Función segura de Django para generar HTML
- **`mark_safe()`:** Marca una cadena como "HTML seguro" (ya sanitizado)
- **`title=`:** Atributo HTML que muestra tooltip al pasar el mouse
- **`short_description`:** Texto del encabezado de la columna en el admin
- **Emojis:** Iconos Unicode que funcionan sin necesidad de archivos externos

---

## 🧪 TESTS

### **Crear archivo de tests**

**ARCHIVO:** `servicio_tecnico/tests/test_refactor_venta_mostrador.py`

```python
"""
Tests para verificar refactorización de venta mostrador.
Sistema actualizado (Oct 2025): Venta mostrador como complemento.
"""
from django.test import TestCase
from django.core.exceptions import ValidationError
from servicio_tecnico.models import OrdenServicio, VentaMostrador, Cotizacion
from inventario.models import Sucursal, Empleado
from django.contrib.auth.models import User


class VentaMostradorComplementoTests(TestCase):
    """Tests del nuevo sistema de venta mostrador como complemento"""
    
    def setUp(self):
        """Configuración inicial para cada test"""
        self.sucursal = Sucursal.objects.create(nombre="Test", activa=True)
        
        self.user = User.objects.create_user(username='testuser', password='12345')
        self.empleado = Empleado.objects.create(
            nombre="Test",
            apellido_paterno="User",
            activo=True,
            usuario=self.user
        )
    
    def test_orden_diagnostico_puede_tener_venta_mostrador(self):
        """
        ✅ TEST: Orden de diagnóstico PUEDE tener venta mostrador
        (Antes esto lanzaba ValidationError)
        """
        # Crear orden de diagnóstico
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            responsable_seguimiento=self.empleado,
            tecnico_asignado_actual=self.empleado,
            tipo_servicio='diagnostico',  # ⚠️ Tipo diagnóstico
            estado='diagnostico'
        )
        
        # Agregar venta mostrador
        venta = VentaMostrador.objects.create(
            orden=orden,
            paquete='ninguno',
            incluye_kit_limpieza=True,
            costo_kit=150.00
        )
        
        # ✅ NO debe lanzar error
        try:
            orden.clean()  # Validación de modelo
            exito = True
        except ValidationError:
            exito = False
        
        self.assertTrue(exito, "Orden de diagnóstico DEBE poder tener venta mostrador")
        self.assertTrue(hasattr(orden, 'venta_mostrador'))
    
    def test_orden_puede_tener_cotizacion_y_venta_mostrador(self):
        """
        ✅ TEST: Una orden puede tener AMBOS complementos simultáneamente
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            responsable_seguimiento=self.empleado,
            tecnico_asignado_actual=self.empleado,
            tipo_servicio='diagnostico',
            estado='diagnostico'
        )
        
        # Agregar cotización
        cotizacion = Cotizacion.objects.create(
            orden=orden,
            total_piezas=500.00,
            total_mano_obra=300.00,
            total_general=800.00
        )
        
        # Agregar venta mostrador
        venta = VentaMostrador.objects.create(
            orden=orden,
            paquete='ninguno',
            incluye_kit_limpieza=True,
            costo_kit=150.00
        )
        
        # ✅ Validar que ambos existen
        orden.refresh_from_db()
        self.assertTrue(hasattr(orden, 'cotizacion'))
        self.assertTrue(hasattr(orden, 'venta_mostrador'))
        self.assertEqual(orden.cotizacion, cotizacion)
        self.assertEqual(orden.venta_mostrador, venta)
    
    def test_metodo_convertir_a_diagnostico_eliminado(self):
        """
        ✅ TEST: El método convertir_a_diagnostico() ya NO existe
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            responsable_seguimiento=self.empleado,
            tecnico_asignado_actual=self.empleado,
            tipo_servicio='venta_mostrador'
        )
        
        # ✅ El método NO debe existir
        self.assertFalse(
            hasattr(orden, 'convertir_a_diagnostico'),
            "El método convertir_a_diagnostico() debe haber sido eliminado"
        )
    
    def test_campos_conversion_eliminados(self):
        """
        ✅ TEST: Los campos de conversión ya NO existen en el modelo
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            responsable_seguimiento=self.empleado,
            tecnico_asignado_actual=self.empleado,
            tipo_servicio='diagnostico'
        )
        
        # ✅ Estos campos NO deben existir
        self.assertFalse(hasattr(orden, 'orden_venta_mostrador_previa'))
        self.assertFalse(hasattr(orden, 'fecha_conversion'))
        self.assertFalse(hasattr(orden, 'notas_conversion'))
```

**Ejecutar tests:**
```bash
python manage.py test servicio_tecnico.tests.test_refactor_venta_mostrador
```

**🎓 Explicación para principiante:**
- **`TestCase`:** Clase base de Django para crear tests
- **`setUp()`:** Método que se ejecuta ANTES de cada test (crear datos)
- **`self.assertTrue()`:** Verifica que algo sea True, falla el test si es False
- **`refresh_from_db()`:** Recarga el objeto desde la base de datos
- **`hasattr()`:** Verifica si un objeto tiene un atributo/campo

---

## ✅ CHECKLIST COMPLETO

### **FASE 1: Modelos (2h)**
- [ ] ⛔ Eliminar validaciones restrictivas en `clean()` (línea 296-310)
- [ ] ✅ Actualizar docstring de `clean()`
- [ ] ⛔ Eliminar campos: `orden_venta_mostrador_previa`, `fecha_conversion`, `notas_conversion` (línea 150-180)
- [ ] ⛔ Eliminar estado 'convertida_a_diagnostico' de ESTADO_CHOICES (línea 80)
- [ ] ✅ Actualizar docstring del modelo OrdenServicio (línea 20)
- [ ] ⛔ Eliminar método `convertir_a_diagnostico()` (~138 líneas, 462-600)
- [ ] ✅ Ejecutar: `python manage.py makemigrations servicio_tecnico`
- [ ] ✅ Revisar migración: Debe tener `RemoveField` x3 + `AlterField` de estado
- [ ] ✅ Ejecutar: `python manage.py migrate`
- [ ] ✅ Verificar: `python manage.py shell` → crear orden → no hay errores

### **FASE 2: Vistas (2h)**
- [ ] ✅ Actualizar `detalle_orden()`: Cargar contexto VM siempre (línea 1264)
- [ ] ⛔ Eliminar validación tipo en `crear_venta_mostrador()` (línea 2588-2660)
- [ ] ⛔ Eliminar vista `convertir_venta_a_diagnostico()` completa (línea 2893-3000)
- [ ] ⛔ Eliminar URL de conversión en `urls.py` (línea 80)
- [ ] ✅ Probar en navegador: Abrir detalle orden diagnóstico
- [ ] ✅ Verificar: Panel VM visible en orden diagnóstico
- [ ] ✅ Crear venta mostrador en orden diagnóstico (debe funcionar)

### **FASE 3: Admin (1h)**
- [ ] ✅ Actualizar `tipo_servicio_badge()` con indicadores (línea 243-266)
- [ ] ✅ Abrir admin: `/admin/servicio_tecnico/ordenservicio/`
- [ ] ✅ Verificar badges: 🔧/🛒 + 📋/💰 según complementos
- [ ] ✅ Verificar campos eliminados NO aparecen en formulario

### **Tests**
- [ ] ✅ Crear archivo: `tests/test_refactor_venta_mostrador.py`
- [ ] ✅ Ejecutar: `python manage.py test servicio_tecnico.tests.test_refactor_venta_mostrador`
- [ ] ✅ Todos los tests pasan (4/4)

### **Verificación Final**
- [ ] ✅ No hay errores en consola
- [ ] ✅ Migraciones aplicadas correctamente
- [ ] ✅ Sistema funciona sin errores 500
- [ ] ✅ Datos de prueba funcionan correctamente

---

## 🚀 COMANDOS RÁPIDOS

```bash
# ANTES DE EMPEZAR
git checkout -b refactor-venta-mostrador
python manage.py dumpdata > backup_$(Get-Date -Format "yyyyMMdd").json

# DURANTE DESARROLLO
python manage.py makemigrations servicio_tecnico
python manage.py migrate
python manage.py test servicio_tecnico.tests.test_refactor_venta_mostrador

# VERIFICAR
python manage.py shell
>>> from servicio_tecnico.models import OrdenServicio
>>> orden = OrdenServicio.objects.first()
>>> hasattr(orden, 'convertir_a_diagnostico')  # Debe ser False
>>> hasattr(orden, 'orden_venta_mostrador_previa')  # Debe ser False

# AL FINALIZAR
git add .
git commit -m "feat: Refactorizar venta mostrador como complemento"
git push origin refactor-venta-mostrador
```

---

## 📊 RESUMEN DE ELIMINACIONES

| Elemento | Líneas | Archivo | Acción |
|----------|--------|---------|--------|
| Validaciones restrictivas | 296-310 | models.py | ⛔ ELIMINAR |
| Campos de conversión (x3) | 150-180 | models.py | ⛔ ELIMINAR |
| Estado 'convertida_a_diagnostico' | 80 | models.py | ⛔ ELIMINAR |
| Método convertir_a_diagnostico() | 462-600 | models.py | ⛔ ELIMINAR |
| Vista convertir_venta_a_diagnostico() | 2893-3000 | views.py | ⛔ ELIMINAR |
| URL de conversión | 80 | urls.py | ⛔ ELIMINAR |
| **TOTAL LÍNEAS ELIMINADAS** | **~350** | | |

---

**FIN DE PARTE 1 - BACKEND SIMPLIFICADO**

✅ Versión sin compatibilidad con sistema antiguo  
⚡ Código más limpio y mantenible  
🎯 Listo para implementar

---

_Última actualización: 9 de Octubre, 2025_  
_Versión: 2.0 - Simplificada_
