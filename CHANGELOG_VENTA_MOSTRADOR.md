# 📝 Changelog - Sistema Venta Mostrador

## [FASE 1] - 2025-10-08 ✅ COMPLETADA

### 🎯 Objetivo
Implementar la base de datos y lógica de negocio para el sistema de Ventas Mostrador, diferenciando servicios directos (sin diagnóstico) de servicios con diagnóstico técnico.

---

### 📦 Cambios en `config/constants.py`

#### Añadido
- **PAQUETES_CHOICES**: Nuevos paquetes `premium`, `oro`, `plata`, `ninguno`
- **PRECIOS_PAQUETES**: Premium ($5,500), Oro ($3,850), Plata ($2,900)
- **DESCRIPCION_PAQUETES**: Descripciones detalladas con emojis y especificaciones técnicas
- **COMPONENTES_PAQUETES**: Diccionario de componentes incluidos en cada paquete
- **Estado 'convertida_a_diagnostico'**: Nuevo estado en ESTADO_ORDEN_CHOICES
- **Función `obtener_componentes_paquete(codigo)`**: Obtiene lista de componentes por paquete
- **Función `paquete_genera_comision(codigo)`**: Determina si paquete genera comisión

#### Modificado
- **ESTADO_ORDEN_CHOICES**: Aumentado max_length a 30 caracteres

#### Eliminado
- ❌ Paquete "Bronce" (reemplazado por nuevos paquetes)

---

### 🗄️ Cambios en `servicio_tecnico/models.py`

#### Modelo: **OrdenServicio**

##### Campos Añadidos (5)
```python
tipo_servicio = CharField(max_length=20, default='diagnostico')
    # Discrimina entre 'diagnostico' y 'venta_mostrador'
    
orden_venta_mostrador_previa = ForeignKey('self', null=True, blank=True)
    # FK para trazabilidad de conversiones
    
monto_abono_previo = DecimalField(max_digits=10, decimal_places=2, default=0.00)
    # Monto a abonar por servicio previo
    
notas_conversion = TextField(blank=True)
    # Documentación del motivo de conversión
    
control_calidad_requerido = BooleanField(default=False)
    # Control de calidad opcional para ventas simples
```

##### Métodos Añadidos (2)
```python
def convertir_a_diagnostico(self, usuario, motivo_conversion):
    """
    Convierte orden de venta mostrador a diagnóstico técnico.
    - Valida tipo de servicio
    - Crea nueva orden vinculada
    - Copia datos del equipo
    - Registra en historial bidireccional
    - Retorna nueva orden
    """
    
def clean(self):
    """
    Validaciones personalizadas:
    1. Venta mostrador NO puede tener cotización
    2. Diagnóstico NO puede tener venta mostrador directa
    3. Si hay orden previa, monto_abono > 0
    4. Estados válidos según tipo_servicio
    5. Prevención de lógica inválida
    """
```

##### Modificado
- **Campo `estado`**: max_length de 20 → 30 caracteres

---

#### Modelo: **VentaMostrador**

##### Campos Añadidos (1)
```python
genera_comision = BooleanField(default=False)
    # ¿Esta venta genera comisión para el responsable?
    # Se activa automáticamente para paquetes premium/oro/plata
```

##### Properties Modificadas (1)
```python
@property
def total_venta(self):
    """
    Calcula total incluyendo:
    - Paquete
    - Servicios adicionales
    - Piezas vendidas individualmente (NUEVO)
    """
```

##### Properties Añadidas (1)
```python
@property
def total_piezas_vendidas(self):
    """
    Suma solo piezas vendidas individualmente.
    No incluye paquetes ni servicios.
    """
```

##### Métodos Modificados (1)
```python
def save(self, *args, **kwargs):
    """
    - Genera folio VM-YYYY-XXXX
    - Activa genera_comision automáticamente si paquete en [premium, oro, plata] (NUEVO)
    """
```

---

#### Modelo: **PiezaVentaMostrador** (NUEVO)

```python
class PiezaVentaMostrador(models.Model):
    """
    Piezas vendidas en mostrador sin diagnóstico previo.
    Versión SIMPLIFICADA sin tracking de instalación.
    """
    
    # Relaciones
    venta_mostrador = ForeignKey(VentaMostrador)
    componente = ForeignKey(ComponenteEquipo, null=True, blank=True)
    
    # Datos de la pieza
    descripcion_pieza = CharField(max_length=200)
    cantidad = PositiveIntegerField(default=1)
    precio_unitario = DecimalField(max_digits=10, decimal_places=2)
    
    # Control
    fecha_venta = DateTimeField(default=timezone.now)
    notas = TextField(blank=True)
    
    # Property
    @property
    def subtotal(self):
        return self.cantidad * self.precio_unitario
```

**Características:**
- ✅ Modelo simplificado según especificaciones
- ❌ SIN campos: `fue_instalada`, `fecha_instalacion`, `tecnico_instalador`, `notas_instalacion`
- ✅ Índices en `fecha_venta` y `venta_mostrador` para optimización

---

### 🗃️ Migraciones

#### Archivo: `0005_ordenservicio_control_calidad_requerido_and_more.py`

**Operaciones (9):**
1. ✅ AddField: `control_calidad_requerido` a OrdenServicio
2. ✅ AddField: `monto_abono_previo` a OrdenServicio
3. ✅ AddField: `notas_conversion` a OrdenServicio
4. ✅ AddField: `orden_venta_mostrador_previa` a OrdenServicio
5. ✅ AddField: `tipo_servicio` a OrdenServicio
6. ✅ AddField: `genera_comision` a VentaMostrador
7. ✅ AlterField: `estado` en OrdenServicio (max_length: 20 → 30)
8. ✅ AlterField: `paquete` en VentaMostrador (choices actualizados)
9. ✅ CreateModel: `PiezaVentaMostrador` completo

**Resultado:**
- ✅ Migración aplicada sin errores
- ✅ 6 órdenes existentes migradas como `tipo_servicio='diagnostico'`
- ✅ Todos los campos con defaults seguros
- ✅ Integridad referencial mantenida

---

### 🧪 Verificación y Testing

#### Script: `verificar_fase1.py`

**Validaciones (10/10 ✅):**
1. ✅ Imports de modelos funcionando
2. ✅ Paquetes actualizados correctamente
3. ✅ Estado 'convertida_a_diagnostico' presente
4. ✅ 5 campos nuevos en OrdenServicio verificados
5. ✅ Método `convertir_a_diagnostico()` existe
6. ✅ Método `clean()` existe
7. ✅ Campo `genera_comision` en VentaMostrador
8. ✅ Property `total_piezas_vendidas` funcional
9. ✅ Modelo PiezaVentaMostrador con 7/7 campos
10. ✅ 6/6 órdenes existentes migradas correctamente

---

## 📊 Estadísticas

| Métrica | Valor |
|---------|-------|
| **Archivos Modificados** | 2 |
| **Modelos Afectados** | 3 |
| **Campos Nuevos** | 6 |
| **Métodos Nuevos** | 2 |
| **Líneas de Código** | ~350 |
| **Tiempo Invertido** | 2.5 horas |
| **Órdenes Migradas** | 6/6 ✅ |
| **Errores Encontrados** | 0 ✅ |

---

## 🔐 Reglas de Negocio Implementadas

### Validaciones en `OrdenServicio.clean()`
1. ✅ Venta mostrador NO puede tener cotización
2. ✅ Diagnóstico NO puede tener venta mostrador directa (excepto conversiones)
3. ✅ Si hay orden previa, monto_abono debe ser > 0
4. ✅ Estados válidos según tipo_servicio
5. ✅ Prevención de conversión inversa (diagnóstico → venta_mostrador)

### Sistema de Conversión
- ✅ Solo convierte órdenes tipo 'venta_mostrador'
- ✅ Valida existencia de venta asociada
- ✅ Previene doble conversión
- ✅ Trazabilidad bidireccional completa
- ✅ Copia automática de datos del equipo

---

## 🚀 Próximos Pasos (FASE 2)

### Pendientes
- [ ] **Admin**: Configurar inline de PiezaVentaMostrador
- [ ] **Admin**: Filtros por tipo_servicio
- [ ] **Admin**: Badges de colores para paquetes
- [ ] **Vistas**: crear_venta_mostrador
- [ ] **Vistas**: agregar/editar/eliminar_pieza_venta_mostrador
- [ ] **Vistas**: convertir_venta_a_diagnostico
- [ ] **Templates**: Sección venta mostrador en detalle_orden.html
- [ ] **JavaScript**: Modales y AJAX

---

## 📝 Notas Importantes

### ✅ Decisiones de Diseño Confirmadas
- Control de calidad **OPCIONAL** (campo `control_calidad_requerido`)
- Comisiones **AUTOMÁTICAS** para paquetes premium/oro/plata
- Modelo PiezaVentaMostrador **SIMPLIFICADO** (sin tracking de instalación)
- Paquetes **SIN DESGLOSE** (se manejan como concepto único)

### ❌ No Implementado (Por Solicitud)
- ❌ Precio sin IVA para paquete Plata
- ❌ Campos de instalación en PiezaVentaMostrador
- ❌ Tracking de números de serie
- ❌ Desglose de componentes en paquetes

### 🔄 Cambios vs Plan Original
- ✅ Max_length de `estado` aumentado de 20 a 30 caracteres
- ✅ Sistema de comisiones integrado desde FASE 1
- ✅ Control de calidad opcional implementado desde inicio

---

**Versión:** 1.0  
**Fecha:** 8 de Octubre, 2025  
**Estado:** ✅ FASE 1 COMPLETADA Y VERIFICADA  
**Próximo Hito:** FASE 2 - Admin y Visualización
