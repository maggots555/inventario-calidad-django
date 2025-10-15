# 🎨 PALETA DE COLORES RHITSO - Nueva Configuración

**Fecha de actualización:** 13 de octubre de 2025  
**Archivo modificado:** `servicio_tecnico/templatetags/rhitso_filters.py`

---

## 📋 RESUMEN DE CAMBIOS

Se actualizó la paleta de colores para los estados RHITSO, pasando de una paleta genérica de Bootstrap a **colores personalizados específicos** para cada estado, mejorando la diferenciación visual y la experiencia del usuario.

---

## 🎨 PALETA DE COLORES BASE

| Nombre Color | Código HEX | Vista Previa | Uso |
|--------------|------------|--------------|-----|
| **rosa-claro** | `#FFB6C1` | ![#FFB6C1](https://via.placeholder.com/50x20/FFB6C1/000000?text=+) | Estados de espera suaves |
| **rhitso-rosa-claro** | `#FFC0CB` | ![#FFC0CB](https://via.placeholder.com/50x20/FFC0CB/000000?text=+) | Candidato RHITSO |
| **azul-cian** | `#00CED1` | ![#00CED1](https://via.placeholder.com/50x20/00CED1/000000?text=+) | Confirmaciones pendientes |
| **verde-lima** | `#32CD32` | ![#32CD32](https://via.placeholder.com/50x20/32CD32/000000?text=+) | Aceptaciones del usuario/cliente |
| **rojo-intenso** | `#DC143C` | ![#DC143C](https://via.placeholder.com/50x20/DC143C/FFFFFF?text=+) | Rechazos e incidencias críticas |
| **naranja-claro** | `#FFB347` | ![#FFB347](https://via.placeholder.com/50x20/FFB347/000000?text=+) | Cotizaciones y notificaciones |
| **naranja** | `#FF8C00` | ![#FF8C00](https://via.placeholder.com/50x20/FF8C00/000000?text=+) | Esperas de piezas |
| **verde-fuerte** | `#228B22` | ![#228B22](https://via.placeholder.com/50x20/228B22/FFFFFF?text=+) | Retorno exitoso a SIC |
| **azul-electrico** | `#0080FF` | ![#0080FF](https://via.placeholder.com/50x20/0080FF/FFFFFF?text=+) | Procesos activos y pruebas |
| **morado-claro** | `#B19CD9` | ![#B19CD9](https://via.placeholder.com/50x20/B19CD9/000000?text=+) | Equipo en RHITSO |
| **azul-claro** | `#87CEEB` | ![#87CEEB](https://via.placeholder.com/50x20/87CEEB/000000?text=+) | Diagnósticos |
| **amarillo-claro** | `#FFE66D` | ![#FFE66D](https://via.placeholder.com/50x20/FFE66D/000000?text=+) | Procesos técnicos |
| **morado-fuerte** | `#8B00FF` | ![#8B00FF](https://via.placeholder.com/50x20/8B00FF/FFFFFF?text=+) | Procesos complejos (reballing) |
| **rojo** | `#FF0000` | ![#FF0000](https://via.placeholder.com/50x20/FF0000/FFFFFF?text=+) | No apto para reparación |
| **verde-agua** | `#40E0D0` | ![#40E0D0](https://via.placeholder.com/50x20/40E0D0/000000?text=+) | Espera de componentes |
| **verde** | `#00FF00` | ![#00FF00](https://via.placeholder.com/50x20/00FF00/000000?text=+) | Pruebas exitosas |
| **verde-claro** | `#90EE90` | ![#90EE90](https://via.placeholder.com/50x20/90EE90/000000?text=+) | Equipo reparado |
| **magenta** | `#FF00FF` | ![#FF00FF](https://via.placeholder.com/50x20/FF00FF/000000?text=+) | Incidencias RHITSO |
| **marron-claro** | `#D2B48C` | ![#D2B48C](https://via.placeholder.com/50x20/D2B48C/000000?text=+) | Esperas administrativas |
| **azul-marino** | `#000080` | ![#000080](https://via.placeholder.com/50x20/000080/FFFFFF?text=+) | Peticiones al usuario |
| **coral** | `#FF7F50` | ![#FF7F50](https://via.placeholder.com/50x20/FF7F50/000000?text=+) | Piezas defectuosas (DOA/WPB) |
| **gris** | `#808080` | ![#808080](https://via.placeholder.com/50x20/808080/FFFFFF?text=+) | Estado cerrado |

---

## 📊 MAPEO DE ESTADOS A COLORES

### 🏁 ESTADOS SIC - INICIO DEL PROCESO

| Estado | Color | HEX | Explicación |
|--------|-------|-----|-------------|
| **CANDIDATO RHITSO** | rhitso-rosa-claro | `#FFC0CB` | Equipo marcado como candidato para envío |
| **PENDIENTE DE CONFIRMAR ENVIO A RHITSO** | azul-cian | `#00CED1` | Esperando confirmación de envío |
| **USUARIO ACEPTA ENVIO A RHITSO** | verde-lima | `#32CD32` | Usuario autorizó el envío ✅ |
| **USUARIO NO ACEPTA ENVIO A RHITSO** | rojo-intenso | `#DC143C` | Usuario rechazó el envío ❌ |
| **EN ESPERA DE ENTREGAR EQUIPO A RHITSO** | rosa-claro | `#FFB6C1` | Listo para enviar físicamente |

### 🔴 INCIDENCIAS Y COTIZACIONES SIC

| Estado | Color | HEX | Explicación |
|--------|-------|-----|-------------|
| **INCIDENCIA SIC** | rojo-intenso | `#DC143C` | Problema detectado en SIC ⚠️ |
| **COTIZACIÓN ENVIADA A SIC** | naranja-claro | `#FFB347` | Cotización recibida de RHITSO |
| **EN ESPERA DE PIEZA POR SIC** | naranja | `#FF8C00` | SIC debe proporcionar pieza |
| **PIEZA DE SIC ENVIADA A RHITSO** | naranja | `#FF8C00` | Pieza en tránsito a RHITSO |

### ✅ RETORNO Y PRUEBAS EN SIC

| Estado | Color | HEX | Explicación |
|--------|-------|-----|-------------|
| **EQUIPO RETORNADO A SIC** | verde-fuerte | `#228B22` | Equipo devuelto desde RHITSO ✅ |
| **EN PRUEBAS SIC** | azul-electrico | `#0080FF` | Pruebas de calidad en SIC |

---

### 🔧 ESTADOS RHITSO - INGRESO Y DIAGNÓSTICO

| Estado | Color | HEX | Explicación |
|--------|-------|-----|-------------|
| **EN ESPERA DE CONFIRMAR INGRESO** | azul-cian | `#00CED1` | RHITSO debe confirmar recepción |
| **EQUIPO EN RHITSO** | morado-claro | `#B19CD9` | Equipo físicamente en RHITSO |
| **QR COMPARTIDO (EN DIAGNOSTICO)** | azul-electrico | `#0080FF` | QR compartido, en diagnóstico activo |
| **DIAGNOSTICO FINAL** | azul-claro | `#87CEEB` | Diagnóstico técnico completado |

### 🛠️ PROCESOS TÉCNICOS RHITSO

| Estado | Color | HEX | Explicación |
|--------|-------|-----|-------------|
| **EN PROCESO DE RESPALDO** | amarillo-claro | `#FFE66D` | Respaldando datos del equipo |
| **EN PROCESO DE REBALLING** | morado-fuerte | `#8B00FF` | Proceso técnico complejo de reballing |
| **EN PRUEBAS (DE DIAGNOSTICO)** | amarillo-claro | `#FFE66D` | Pruebas después del diagnóstico |
| **NO APTO PARA REPARACIÓN** | rojo | `#FF0000` | Equipo irreparable ❌ |

### 🔄 ESPERAS Y REPARACIÓN RHITSO

| Estado | Color | HEX | Explicación |
|--------|-------|-----|-------------|
| **EN ESPERA DE PARTES/COMPONENTE** | verde-agua | `#40E0D0` | Esperando llegada de piezas |
| **EN PRUEBAS (REPARADO)** | verde | `#00FF00` | Pruebas post-reparación |
| **EQUIPO REPARADO** | verde-claro | `#90EE90` | Reparación exitosa ✅ |
| **INCIDENCIA RHITSO** | magenta | `#FF00FF` | Problema en RHITSO ⚠️ |
| **EN ESPERA DEL RETORNO DEL EQUIPO** | marron-claro | `#D2B48C` | Listo para envío de vuelta |

---

### 👤 ESTADOS CLIENTE

| Estado | Color | HEX | Explicación |
|--------|-------|-----|-------------|
| **CLIENTE ACEPTA COTIZACIÓN** | verde-lima | `#32CD32` | Cliente autorizó reparación ✅ |
| **COTIZACIÓN ENVIADA AL CLIENTE** | morado-claro | `#B19CD9` | Cotización compartida con cliente |
| **CLIENTE NO ACEPTA COTIZACIÓN** | rojo-intenso | `#DC143C` | Cliente rechazó cotización ❌ |
| **PETICIÓN AL USUARIO** | azul-marino | `#000080` | Solicitud de información al cliente |

### 🛒 ESTADOS COMPRAS Y PIEZAS

| Estado | Color | HEX | Explicación |
|--------|-------|-----|-------------|
| **EN ESPERA DE LA OC** | marron-claro | `#D2B48C` | Esperando orden de compra |
| **PIEZA DOA** | coral | `#FF7F50` | Pieza llegó defectuosa (Dead On Arrival) |
| **PIEZA WPB** | coral | `#FF7F50` | Pieza con problemas (Wrong Part/Bad) |

### ✔️ ESTADO FINAL

| Estado | Color | HEX | Explicación |
|--------|-------|-----|-------------|
| **CERRADO** | gris | `#808080` | Proceso finalizado y cerrado |

---

## 🔄 COMPARACIÓN: ANTES vs AHORA

### Antes (Paleta Genérica)
- ✅ Verdes para todo lo positivo
- ❌ Rojos para todo lo negativo
- ⚠️ Amarillos/naranjas para esperas
- 💙 Azules para información
- 💜 Púrpuras para procesos especiales

**Problema:** Muchos estados compartían el mismo color, dificultando la diferenciación visual.

### Ahora (Paleta Personalizada)
- 🎨 **32 estados diferentes** con colores únicos o semánticos
- 🌈 **21 colores distintos** en la paleta
- 📊 Mejor diferenciación visual entre estados similares
- 🎯 Colores específicos para cada fase del proceso

**Beneficio:** Identificación visual inmediata del estado exacto de cada orden.

---

## 📁 ARCHIVOS AFECTADOS

### 1. **servicio_tecnico/templatetags/rhitso_filters.py**
- ✅ Agregada paleta `PALETA_COLORES_RHITSO` con 21 colores
- ✅ Actualizado diccionario `COLORES_ESTADO_ESPECIFICO` con nuevos mapeos
- ✅ Mantenida compatibilidad con filtros existentes

### 2. **Templates que usan los colores**
Los siguientes templates se benefician automáticamente (sin cambios necesarios):
- ✅ `servicio_tecnico/templates/servicio_tecnico/rhitso/gestion_rhitso.html`
- ✅ `servicio_tecnico/templates/servicio_tecnico/rhitso/dashboard_rhitso.html`
- ✅ `servicio_tecnico/templates/servicio_tecnico/detalle_orden.html`

**Nota:** No requieren modificación porque usan el filtro `color_estado_especifico` que lee del diccionario actualizado.

---

## 🎯 CÓMO SE APLICAN LOS COLORES

### En Templates (HTML)
```django
{% load rhitso_filters %}

<!-- Usando el filtro color_estado_especifico -->
<span class="badge" 
      style="background-color: {{ orden.estado_rhitso|color_estado_especifico }}; 
             color: {{ orden.estado_rhitso|color_estado_especifico|text_color_for_bg }};">
    {{ orden.estado_rhitso }}
</span>
```

### Lógica del Filtro
1. Recibe el nombre del estado (ej: "CANDIDATO RHITSO")
2. Busca en `COLORES_ESTADO_ESPECIFICO`
3. Retorna el código HEX correspondiente
4. Si no encuentra el estado, retorna `#6c757d` (gris neutro)

---

## ✅ COMPATIBILIDAD Y MIGRACIÓN

### ¿Requiere migración de base de datos?
**NO** ❌ - Los colores están en código Python, no en la BD.

### ¿Afecta órdenes existentes?
**NO** ❌ - Cambio visual únicamente, no afecta datos.

### ¿Requiere actualizar estados en la BD?
**NO** ❌ - El modelo `EstadoRHITSO` tiene campo `color` pero los templates usan el filtro, no el modelo.

### ¿Cómo se actualiza el admin?
El campo `color` en el modelo `EstadoRHITSO` sigue usando valores Bootstrap (info, warning, etc.) para el método `get_badge_class()`. La nueva paleta solo afecta templates que usan el filtro `color_estado_especifico`.

---

## 🧪 PRUEBAS RECOMENDADAS

### 1. Dashboard RHITSO
- [ ] Navegar a: Servicio Técnico → Dashboard RHITSO
- [ ] Verificar que los badges de estado muestren los nuevos colores
- [ ] Confirmar legibilidad del texto sobre fondos coloreados

### 2. Gestión RHITSO
- [ ] Abrir una orden con estado RHITSO
- [ ] Verificar badge del estado actual
- [ ] Revisar timeline de seguimiento (colores en iconos circulares)
- [ ] Confirmar que los colores sean distintivos y claros

### 3. Detalle de Orden
- [ ] Ver una orden con módulo RHITSO
- [ ] Verificar badge de estado RHITSO en la sección correspondiente

### 4. Contrast Check
- [ ] Verificar que texto sea legible en todos los fondos
- [ ] El filtro `text_color_for_bg` debería ajustar automáticamente
- [ ] Textos blancos en fondos oscuros, negros en fondos claros

---

## 🎨 CONSIDERACIONES DE DISEÑO

### Contraste y Accesibilidad
- ✅ Colores vivos facilitan identificación rápida
- ⚠️ Algunos colores pueden ser muy brillantes en modo claro
- 💡 El filtro `text_color_for_bg` calcula automáticamente el color de texto óptimo

### Consistencia Semántica
- 🔴 **Rojos:** Rechazos, incidencias, errores
- 🟢 **Verdes:** Éxitos, aceptaciones, completados
- 🟡 **Amarillos:** Procesos en curso, advertencias leves
- 🔵 **Azules:** Información, procesos activos
- 🟣 **Púrpuras:** Procesos técnicos complejos
- 🟤 **Marrones:** Esperas administrativas
- 🟠 **Naranjas:** Piezas, compras, logística
- 🩷 **Rosas:** Estados iniciales, candidatos

---

## 📝 NOTAS PARA FUTUROS CAMBIOS

### Agregar Nuevo Estado
1. Agregar el estado en el modelo `EstadoRHITSO` (si es nuevo)
2. Agregar mapeo en `COLORES_ESTADO_ESPECIFICO` del filtro
3. Opcionalmente agregar nuevo color a `PALETA_COLORES_RHITSO`

### Cambiar Color de un Estado
Simplemente actualizar el valor en `COLORES_ESTADO_ESPECIFICO`:
```python
'NOMBRE DEL ESTADO': PALETA_COLORES_RHITSO['nombre-color'],
```

### Agregar Nuevo Color a la Paleta
Agregar en `PALETA_COLORES_RHITSO`:
```python
'nuevo-color': '#HEXCODE',
```

---

## 🔗 REFERENCIAS

- **Archivo de filtros:** `servicio_tecnico/templatetags/rhitso_filters.py`
- **Documentación de fechas manuales:** `CAMBIO_FECHAS_RHITSO_MANUAL.md`
- **Modelo EstadoRHITSO:** `servicio_tecnico/models.py` (líneas 1681+)
- **Template principal:** `servicio_tecnico/templates/servicio_tecnico/rhitso/gestion_rhitso.html`

---

**Documentación creada el:** 13 de octubre de 2025  
**Autor:** Sistema de Gestión SIC  
**Versión:** 1.0
