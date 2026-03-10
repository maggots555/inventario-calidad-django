# Sistema de Feedback de Satisfacción — Implementación

> **Objetivo**: Enviar encuestas de satisfacción a clientes cuando se entrega su equipo reparado, **excluyendo órdenes con cotizaciones rechazadas**.

---

## 📋 Contexto

### ✅ Ya implementado (Feedback de Rechazo):
- Modelo `FeedbackCliente` con campos para ambos tipos (`rechazo` y `satisfaccion`)
- Sistema de tokens firmados con expiración de 7 días
- Envío de correos via Celery con CC al jefe de calidad
- Vista pública sin autenticación para recibir respuestas

### 🎯 Por implementar (Feedback de Satisfacción):
- Trigger automático cuando la orden cambia a estado `entregado`
- Excluir órdenes que tuvieron cotización rechazada
- Formulario de satisfacción con calificaciones (estrellas, NPS, recomendación)
- Email con diseño similar al de rechazo
- Dashboard para visualizar métricas de satisfacción

---

## 🚀 Pasos de Implementación

### **PASO 1: Crear el Trigger Automático**

**Ubicación**: `servicio_tecnico/views.py` o `servicio_tecnico/signals.py` (recomendado)

**Lógica**:
```
Cuando una orden cambia a estado 'entregado':
  1. Verificar que tenga cotización
  2. Verificar que la cotización NO haya sido rechazada
  3. Verificar que el email del cliente sea válido
  4. Crear registro FeedbackCliente tipo='satisfaccion'
  5. Generar token único firmado
  6. Encolar tarea Celery para envío de correo
```

**Exclusión crítica**:
- Si `cotizacion.motivo_rechazo` tiene valor → **NO enviar**
- Si `cotizacion.estado_cotizacion == 'rechazada'` → **NO enviar**
- Solo enviar si `cotizacion.estado_cotizacion == 'aceptada'`

**Archivo recomendado**: `servicio_tecnico/signals.py`
- Usar signal `post_save` de `OrdenServicio`
- Detectar cambio de estado a `'entregado'`

---

### **PASO 2: Crear Tarea Celery para Envío de Email**

**Ubicación**: `servicio_tecnico/tasks.py`

**Función**: `enviar_feedback_satisfaccion_task(feedback_id, usuario_id=None)`

**Contenido del email**:
- Saludo: "Estimado usuario"
- Datos del equipo: marca, modelo, folio
- Fecha de entrega
- Link al formulario de satisfacción
- Mensaje: "Nos gustaría conocer tu experiencia"
- Vigencia: 7 días

**Patrón a seguir**: Igual que `enviar_feedback_rechazo_task`
- CC a `JEFE_CALIDAD_EMAIL` y a JEFE_CALIDAD_2_EMAIL
- Logo SIC con CID
- Iconos de redes sociales
- Registrar en `HistorialOrden`
- Notificar éxito/error

---

### **PASO 3: Crear Formulario de Satisfacción**

**Ubicación**: `servicio_tecnico/forms.py`

**Clase**: `FeedbackSatisfaccionClienteForm`

**Campos obligatorios**:
1. `calificacion_general` (1-5 estrellas) — Radio buttons con ⭐
2. `nps` (0-10) — Escala numérica
3. `recomienda` (Sí/No) — 👍 👎

**Campos opcionales**:
4. `calificacion_atencion` (1-5 estrellas)
5. `calificacion_tiempo` (1-5 estrellas)
6. `comentario_cliente` (textarea, max 1000 chars, opcional)

**Validaciones**:
- `calificacion_general`: requerido, rango 1-5
- `nps`: requerido, rango 0-10
- `recomienda`: requerido, booleano

---

### **PASO 4: Crear Vista Pública**

**Ubicación**: `servicio_tecnico/views.py`

**Función**: `feedback_satisfaccion_cliente(request, token)`

**Estados del template**:
1. **`formulario`**: Mostrar form si token válido
2. **`gracias`**: Después de enviar
3. **`ya_respondido`**: Si `utilizado=True`
4. **`expirado`**: Si pasaron 7 días

**Lógica al guardar**:
- Guardar calificaciones en `FeedbackCliente`
- Marcar `utilizado=True`
- Guardar `ip_respuesta` y `fecha_respuesta`
- Registrar en `HistorialOrden`
- Redirigir a estado `gracias`

**URL pública**: `/feedback-satisfaccion/<token>/`

---

### **PASO 5: Crear Templates**

#### **5.1 Email**: `servicio_tecnico/templates/servicio_tecnico/emails/feedback_satisfaccion.html`

**Estructura**:
- Header con gradiente azul + logo SIC (CID)
- Saludo genérico
- Info del equipo (marca, modelo, folio, fecha entrega)
- CTA: "Calificar mi experiencia" (botón grande)
- Footer con redes sociales

**Contexto requerido**:
```python
{
    'folio': str,
    'marca_equipo': str,
    'modelo_equipo': str,
    'tipo_equipo': str,
    'fecha_entrega': str,
    'feedback_url': str,
    'dias_vigencia': 7,
}
```

#### **5.2 Vista pública**: `servicio_tecnico/templates/servicio_tecnico/feedback_satisfaccion.html`

**Diseño**:
- Mobile-first (viewport-fit=cover para PWA)
- Layout 2 columnas en desktop
- Izquierda: Info del equipo
- Derecha: Formulario con estrellas interactivas
- Estados: formulario, gracias, ya_respondido, expirado

**Características**:
- Estrellas clickeables con JavaScript/TypeScript
- Escala NPS visual (0-10)
- Botones de pulgar arriba/abajo para recomendación
- Validación frontend + backend

---

### **PASO 6: Crear CSS para Estrellas y NPS**

**Ubicación**: `static/css/feedback_satisfaccion.css`

**Componentes**:
- `.star-rating`: Estrellas interactivas hover
- `.nps-scale`: Escala 0-10 con colores (rojo 0-6, amarillo 7-8, verde 9-10)
- `.thumb-buttons`: Botones de recomendación
- Responsive para móviles (<600px)

---

### **PASO 7: TypeScript Interactivo (Opcional)**

**Ubicación**: `static/ts/feedback_satisfaccion.ts`

**Funcionalidad**:
- Manejar clicks en estrellas
- Mostrar estrellas llenas/vacías
- Resaltar selección de NPS
- Validar antes de submit

**Compilar**: `npm run build`

---

### **PASO 8: Registrar URLs**

#### `servicio_tecnico/urls.py`:
```python
# Confirmación de envío (requiere login)
path('feedback-satisfaccion/confirmar/<int:feedback_id>/', 
     views.confirmar_feedback_satisfaccion, 
     name='confirmar_feedback_satisfaccion'),
```

#### `config/urls.py`:
```python
# Vista pública (sin login)
path('feedback-satisfaccion/<str:token>/', 
     servicio_tecnico_views.feedback_satisfaccion_cliente, 
     name='feedback_satisfaccion_publico'),
```

---

### **PASO 9: Configurar Admin de Django**

**Ubicación**: `servicio_tecnico/admin.py`

**Mejoras a `FeedbackClienteAdmin`**:
- Filtro por `tipo` (rechazo vs satisfaccion)
- Campos readonly para satisfacción: todas las calificaciones
- List display: agregar `calificacion_general`, `nps`, `recomienda`
- Búsqueda por orden

---

### **PASO 10: Dashboard de Métricas (Futuro)**

**Ubicación**: `servicio_tecnico/plotly_visualizations.py`

**Gráficas recomendadas**:
1. Promedio de `calificacion_general` por mes
2. Distribución NPS (Detractores 0-6, Pasivos 7-8, Promotores 9-10)
3. % de clientes que recomiendan
4. Promedio `calificacion_atencion` vs `calificacion_tiempo`
5. Tabla de comentarios recientes

---

## 🔒 Validaciones Críticas

### Al crear el FeedbackCliente:
- ✅ Email válido (no `cliente@ejemplo.com`)
- ✅ Cotización existe y NO está rechazada
- ✅ No existe feedback previo de tipo `satisfaccion` para esa orden
- ✅ Orden en estado `entregado`

### Al recibir respuesta del cliente:
- ✅ Token válido y no expirado
- ✅ No ha sido utilizado antes
- ✅ Calificaciones en rango válido (1-5 para estrellas, 0-10 para NPS)

---

## 📊 Flujo Completo

```
1. Técnico marca orden como "Entregado"
   ↓
2. Signal/View detecta cambio de estado
   ↓
3. Validar: ¿tiene cotización aceptada? ¿email válido?
   ↓
4. Crear FeedbackCliente tipo='satisfaccion' + token
   ↓
5. Encolar tarea Celery: enviar_feedback_satisfaccion_task
   ↓
6. Celery envía email a cliente (CC: jefe calidad)
   ↓
7. Cliente recibe email, click en link
   ↓
8. Vista pública muestra formulario de satisfacción
   ↓
9. Cliente califica (estrellas, NPS, recomendación)
   ↓
10. Guardar respuesta, marcar token como utilizado
   ↓
11. Registrar en HistorialOrden
   ↓
12. Mostrar página "Gracias por tu opinión"
```

---

## ⚠️ Exclusiones Importantes

### NO enviar feedback de satisfacción si:
1. `cotizacion.motivo_rechazo` tiene valor (fue rechazada)
2. `cotizacion.estado_cotizacion == 'rechazada'`
3. Email inválido (`cliente@ejemplo.com`, vacío, null)
4. Ya existe `FeedbackCliente` tipo='satisfaccion' para esa orden
5. Orden NO tiene cotización (solo venta mostrador sin diagnóstico)

---

## 🎨 Diseño Visual

### Paleta de colores (mismo que feedback rechazo):
- Header: Gradiente azul `#ffffff → #e3f2fd → #90caf9`
- Botón CTA: Gradiente `#667eea → #764ba2`
- Footer: `#2c3e50 → #34495e`

### Estrellas:
- Vacía: `⭐` gris (#ccc)
- Llena: `⭐` amarillo/dorado (#ffc107)
- Hover: animación de escala

### NPS:
- 0-6: Rojo (#e53e3e) — Detractores
- 7-8: Amarillo (#fbbf24) — Pasivos
- 9-10: Verde (#10b981) — Promotores

---

## 📝 Variables de Entorno

**Ya configuradas**:
- `JEFE_CALIDAD_EMAIL` — Recibe copia de todos los emails

**No requiere nuevas variables**.

---

## 🧪 Testing

### Casos de prueba:
1. **Caso exitoso**: Orden entregada con cotización aceptada
2. **Caso rechazado**: Orden con `motivo_rechazo != ''`
3. **Email inválido**: Debe fallar validación
4. **Token expirado**: Mostrar mensaje de expiración
5. **Token ya usado**: Mostrar "Ya respondido"
6. **Calificaciones fuera de rango**: Validar backend

---

## 📌 Archivos a Crear/Modificar

### Crear:
- [ ] `servicio_tecnico/signals.py` (si no existe)
- [ ] `servicio_tecnico/templates/servicio_tecnico/emails/feedback_satisfaccion.html`
- [ ] `servicio_tecnico/templates/servicio_tecnico/feedback_satisfaccion.html`
- [ ] `static/css/feedback_satisfaccion.css`
- [ ] `static/ts/feedback_satisfaccion.ts` (opcional)

### Modificar:
- [ ] `servicio_tecnico/tasks.py` — Agregar `enviar_feedback_satisfaccion_task`
- [ ] `servicio_tecnico/forms.py` — Agregar `FeedbackSatisfaccionClienteForm`
- [ ] `servicio_tecnico/views.py` — Agregar 2 vistas nuevas
- [ ] `servicio_tecnico/urls.py` — Agregar ruta de confirmación
- [ ] `config/urls.py` — Agregar ruta pública
- [ ] `servicio_tecnico/admin.py` — Mejorar filtros y display

---

## 🔄 Diferencias con Feedback de Rechazo

| Aspecto | Rechazo | Satisfacción |
|---------|---------|--------------|
| **Trigger** | Manual (operador rechaza) | Automático (orden → entregado) |
| **Modal confirmación** | Sí (operador puede cancelar) | No (automático) |
| **Formulario** | Textarea simple | Estrellas + NPS + Recomendación |
| **Email** | Pide explicar rechazo | Pide calificar experiencia |
| **Exclusión** | Solo motivos específicos | Solo órdenes con cotización rechazada |
| **Datos guardados** | `comentario_cliente` | Calificaciones estructuradas |

---

## ✅ Checklist Final

- [ ] Signal/trigger configurado para estado `entregado`
- [ ] Exclusión de cotizaciones rechazadas funciona
- [ ] Tarea Celery envía email correctamente
- [ ] Email tiene diseño profesional y responsive
- [ ] Vista pública muestra formulario de estrellas
- [ ] Validaciones frontend y backend funcionan
- [ ] Token de seguridad funciona (7 días, uso único)
- [ ] Se registra en `HistorialOrden`
- [ ] CC al jefe de calidad se envía
- [ ] Admin de Django muestra calificaciones
- [ ] CSS/TypeScript compilado (`npm run build`)
- [ ] Testing completo de flujo
- [ ] Celery reiniciado después de cambios

---

**Prioridad**: Media-Alta  
**Complejidad**: Media (usa infraestructura existente)  
**Tiempo estimado**: 6-8 horas de desarrollo + testing

**Última actualización**: Enero 2026
