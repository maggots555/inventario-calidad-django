# 🎨 Referencia Rápida - Admin de Venta Mostrador

## 📌 Guía Rápida para Administradores

Esta guía te ayudará a usar el Admin de Django para gestionar Ventas Mostrador de manera eficiente.

---

## 🔍 Vista General del Admin

### Modelos Disponibles

| Modelo | Propósito | Acceso Directo |
|--------|-----------|----------------|
| **Orden de Servicio** | Gestión de órdenes (diagnóstico y venta mostrador) | `/admin/servicio_tecnico/ordenservicio/` |
| **Venta Mostrador** | Detalles de ventas directas sin diagnóstico | `/admin/servicio_tecnico/ventamostrador/` |
| **Pieza Venta Mostrador** | Piezas vendidas individualmente | `/admin/servicio_tecnico/piezaventamostrador/` |

---

## 🛠️ ORDEN DE SERVICIO - Admin

### Cómo Identificar el Tipo de Servicio

En el listado de órdenes, verás badges de colores:

- 🔵 **Azul** = Con Diagnóstico Técnico (flujo normal)
- 🟢 **Verde** = Venta Mostrador (servicio directo)

### Filtrar Órdenes por Tipo

1. Accede a **Órdenes de Servicio** en el admin
2. En el panel lateral derecho, busca **"Tipo de servicio"**
3. Selecciona:
   - **Con Diagnóstico Técnico** - Para órdenes tradicionales
   - **Venta Mostrador - Sin Diagnóstico** - Para ventas directas

### Crear una Venta Mostrador

#### Paso 1: Crear la Orden
```
1. Click en "Agregar Orden de Servicio"
2. En "Tipo de Servicio" seleccionar: "Venta Mostrador - Sin Diagnóstico"
3. Marcar/desmarcar "Control de calidad requerido" según el caso
4. Completar datos de ubicación (sucursal, responsable, técnico)
5. Estado inicial: "En Recepción"
6. Guardar orden
```

#### Paso 2: Crear la Venta Mostrador Asociada
```
1. Ir a "Ventas Mostrador"
2. Click en "Agregar Venta Mostrador"
3. Seleccionar la orden recién creada
4. Elegir paquete (premium/oro/plata/ninguno)
5. Agregar servicios adicionales si aplican
6. Guardar
```

### Ver Órdenes Convertidas

Las órdenes de venta mostrador que se convirtieron a diagnóstico tienen:
- 🟣 **Badge Morado** en estado: "Convertida a Diagnóstico"
- Fieldset collapsible: "Conversión desde Venta Mostrador"
  - Muestra la orden original
  - Monto abonado por el cliente
  - Notas sobre por qué se convirtió

---

## 💰 VENTA MOSTRADOR - Admin

### Badges de Paquetes

| Color | Paquete | Precio | Genera Comisión |
|-------|---------|--------|-----------------|
| 🟣 Morado | Premium | $5,500 | ✅ Sí |
| 🟡 Dorado | Oro | $3,850 | ✅ Sí |
| ⚪ Plateado | Plata | $2,900 | ✅ Sí |
| ⚫ Gris | Ninguno | $0 | ❌ No |

### Agregar Piezas a una Venta

#### Opción 1: Desde el Formulario de Venta Mostrador
```
1. Editar una venta mostrador existente
2. Scroll hasta la sección "PIEZAS VENDIDAS"
3. En la tabla, llenar:
   - Componente: (buscar con autocompletado)
   - Descripción pieza: Texto libre
   - Cantidad: Número
   - Precio unitario: Monto en pesos
   - Notas: Observaciones opcionales
4. El subtotal se calcula automáticamente
5. Guardar
```

**Agregar Múltiples Piezas:**
- La última fila siempre está vacía para agregar otra pieza
- Si necesitas más, guarda primero y se agregarán más filas

#### Opción 2: Desde Piezas Venta Mostrador
```
1. Ir a "Piezas Venta Mostrador"
2. Click en "Agregar Pieza Venta Mostrador"
3. Seleccionar la venta mostrador (con autocompletado)
4. Llenar datos de la pieza
5. Guardar
```

### Filtrar por Comisiones

Para ver solo ventas que generan comisión:
```
1. Ir a "Ventas Mostrador"
2. En panel lateral: "Genera comisión"
3. Seleccionar "Sí"
```

Esto muestra solo paquetes Premium, Oro y Plata.

---

## 🧩 PIEZA VENTA MOSTRADOR - Admin

### Búsqueda Avanzada

Puedes buscar piezas por:
- ✅ Descripción de la pieza (ej: "RAM 8GB")
- ✅ Folio de venta (ej: "VM-2025-0001")
- ✅ Número de orden (ej: "ORD-2025-0234")
- ✅ Nombre del componente del catálogo

**Ejemplo de búsqueda:**
```
Buscar: "RAM"
Resultado: Todas las piezas RAM vendidas en mostrador
```

### Navegación por Fechas

En la parte superior verás:
```
2025 > Octubre > 8 de Octubre
```

Click en cualquier nivel para ver piezas de ese período.

### Reportes Rápidos

#### Ver Piezas Vendidas Hoy
```
1. Ir a "Piezas Venta Mostrador"
2. Click en la fecha de hoy en la navegación superior
```

#### Ver Piezas por Tipo de Componente
```
1. Panel lateral: "Componente"
2. Seleccionar componente deseado (RAM, SSD, etc.)
```

---

## 📊 Casos de Uso Comunes

### Caso 1: Cliente Compra Paquete Premium

```
✅ PROCESO:
1. Crear Orden:
   - Tipo: Venta Mostrador
   - Estado: Recepción
   
2. Crear Venta Mostrador:
   - Paquete: Premium ($5,500)
   - NO agregar piezas manualmente (ya incluidas en paquete)
   - Genera comisión: ✅ (automático)
   
3. Cambiar estado de orden:
   - Reparación (mientras se instala)
   - Control de Calidad
   - Finalizado
   - Entregado
```

### Caso 2: Cliente Compra Pieza Individual + Instalación

```
✅ PROCESO:
1. Crear Orden:
   - Tipo: Venta Mostrador
   - Estado: Recepción
   
2. Crear Venta Mostrador:
   - Paquete: Ninguno
   - Incluye cambio pieza: ✅
   - Costo cambio pieza: $200
   - Genera comisión: ❌ (no es paquete)
   
3. Agregar Pieza:
   - Componente: RAM 8GB DDR4
   - Descripción: "RAM 8GB DDR4 Kingston HyperX"
   - Cantidad: 1
   - Precio unitario: $800
   - Subtotal: $800 (automático)
   
4. Total Venta: $1,000 ($800 pieza + $200 instalación)
```

### Caso 3: Venta Falla → Conversión a Diagnóstico

```
⚠️ PROCESO:
1. Situación Inicial:
   - Orden VM-2025-0045 (venta mostrador)
   - Cliente compró RAM
   - Instalación falló, equipo no enciende
   
2. Conversión (desde modelo, no admin):
   - Ejecutar método: convertir_a_diagnostico()
   - Sistema crea nueva orden: ORD-2025-0234
   - Estado VM-2025-0045: "Convertida a Diagnóstico" 🟣
   
3. Ver en Admin:
   - Orden VM-2025-0045:
     * Badge morado: "Convertida a Diagnóstico"
     * Fieldset "Conversión..." muestra nueva orden
   
   - Orden ORD-2025-0234:
     * Tipo: Con Diagnóstico Técnico
     * Fieldset "Conversión..." muestra orden original
     * Monto abono previo: $1,000
```

---

## 🎯 Tips y Trucos

### 1. Autocompletado de Componentes

Cuando agregues piezas:
```
- Empieza a escribir el nombre del componente
- Aparecerá lista de sugerencias
- Selecciona el correcto
- Si no existe, deja vacío y usa solo "Descripción pieza"
```

### 2. Formato de Moneda

Todos los precios se muestran con formato:
```
✅ Correcto: $1,234.56
❌ Incorrecto: 1234.56
```

El admin formatea automáticamente al guardar.

### 3. Filtros Múltiples

Puedes combinar filtros:
```
Ejemplo: Ver ventas mostrador de paquete Premium que generan comisión
1. Filtro "Paquete": Premium
2. Filtro "Genera comisión": Sí
```

### 4. Exportar Datos

Para reportes, usa el admin:
```
1. Filtrar datos deseados
2. Seleccionar registros (checkbox)
3. Acción: "Exportar registros seleccionados"
```

*(Nota: Exportación personalizada requiere configuración adicional)*

---

## ⚠️ Advertencias Importantes

### ❌ NO Hacer

1. **NO cambiar tipo_servicio** de una orden existente después de creada
   - Esto puede causar inconsistencias
   - Crear nueva orden si se requiere cambio de tipo

2. **NO editar manualmente** el folio de venta
   - Se genera automáticamente (VM-YYYY-XXXX)
   - Modificarlo manualmente puede duplicar folios

3. **NO eliminar** piezas de venta sin verificar
   - Afecta el total de la venta
   - Consultar con supervisor antes de eliminar

4. **NO agregar cotización** a órdenes tipo venta_mostrador
   - El sistema lo impide a nivel de modelo
   - Usar solo ventas mostrador para este tipo

### ✅ SÍ Hacer

1. **SÍ verificar** que `genera_comision` se active automáticamente
   - Solo debe estar activo para paquetes premium/oro/plata
   - Si está mal, revisar lógica del modelo

2. **SÍ documentar** conversiones en "Notas de conversión"
   - Explicar por qué se convirtió
   - Ayuda para auditorías y reportes

3. **SÍ usar control de calidad** opcional sabiamente
   - Activar para instalaciones/servicios técnicos
   - Desactivar para venta de accesorios simples

4. **SÍ revisar totales** antes de guardar
   - Verificar que sumen correctamente
   - Piezas + servicios + paquete = total

---

## 🔐 Permisos Requeridos

### Para Gestionar Ventas Mostrador

| Acción | Permiso Necesario |
|--------|-------------------|
| Ver órdenes | `view_ordenservicio` |
| Crear orden de venta mostrador | `add_ordenservicio` |
| Editar venta mostrador | `change_ventamostrador` |
| Agregar piezas | `add_piezaventamostrador` |
| Ver historial | `view_historialorden` |
| Convertir a diagnóstico | `change_ordenservicio` (supervisor) |

---

## 📞 Soporte y Dudas

### Problemas Comunes

**Problema:** No puedo agregar piezas al inline
- **Solución:** Primero guarda la venta mostrador, luego agrega piezas

**Problema:** El subtotal no se calcula
- **Solución:** Guarda primero, el cálculo se hace después de guardar

**Problema:** No veo el badge de tipo de servicio
- **Solución:** Refresca la página o limpia caché del navegador

**Problema:** Genera comisión no se activa automáticamente
- **Solución:** Verifica que el paquete sea premium/oro/plata

---

## 📚 Recursos Adicionales

- [CHANGELOG_VENTA_MOSTRADOR_FASE2.md](./CHANGELOG_VENTA_MOSTRADOR_FASE2.md) - Cambios técnicos detallados
- [REFERENCIA_RAPIDA_VENTA_MOSTRADOR.md](./REFERENCIA_RAPIDA_VENTA_MOSTRADOR.md) - Guía para desarrolladores
- [VENTAS_MOSTRADOR_PLAN_IMPLEMENTACION.md](./VENTAS_MOSTRADOR_PLAN_IMPLEMENTACION.md) - Plan completo de implementación

---

**Última Actualización:** 8 de Octubre, 2025  
**Versión:** 1.0  
**Autor:** Sistema de Documentación Automática  
**Para:** Administradores y Personal de Recepción
