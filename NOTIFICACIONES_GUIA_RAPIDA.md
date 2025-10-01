# 📧 GUÍA RÁPIDA - Sistema de Notificaciones por Email

## 🚀 Inicio Rápido

### **Paso 1: Configurar Jefes Directos**
1. Abrir navegador: http://localhost:8000/admin/
2. Ir a **Inventario → Empleados**
3. Editar cada empleado y seleccionar su jefe directo
4. Guardar cambios

### **Paso 2: Enviar una Notificación**
1. Ir a: http://localhost:8000/scorecard/incidencias/
2. Click en cualquier incidencia para ver el detalle
3. Scroll hasta la sección **"Notificaciones"**
4. Click en botón **"Enviar Notificación por Email"**
5. Seleccionar destinatarios en el modal
6. (Opcional) Agregar mensaje personalizado
7. Click en **"Enviar Notificación"**
8. ¡Listo! El email se envió

### **Paso 3: Verificar Historial**
1. Ir a: http://localhost:8000/admin/scorecard/notificacionincidencia/
2. Ver lista de todas las notificaciones enviadas
3. Click en cualquier registro para ver detalles

---

## 👥 Destinatarios Automáticos

El sistema detecta automáticamente:

1. **Técnico Responsable** ✅ (seleccionado por defecto)
   - Email tomado de: `incidencia.tecnico_responsable.email`
   
2. **Jefe Directo del Técnico** ☐ (opcional)
   - Email tomado de: `incidencia.tecnico_responsable.jefe_directo.email`
   - Solo aparece si el técnico tiene jefe directo asignado
   
3. **Jefe de Calidad** ☐ (opcional)
   - Email: amartel@sic.com.mx
   - Configurado en: `config/settings.py`

---

## 📧 Contenido del Email

El email incluye automáticamente:

### **Información del Equipo:**
- Tipo (PC/Laptop/AIO)
- Marca y Modelo
- Número de Serie

### **Responsables:**
- Sucursal
- Área Detectora
- Técnico Responsable
- Inspector de Calidad

### **Clasificación:**
- Tipo de Incidencia
- Categoría del Fallo
- Severidad (con badge de color)
- Componente Afectado

### **Descripción:**
- Descripción de la incidencia
- Acciones tomadas
- Causa raíz (si existe)

### **Mensaje Adicional:**
- Tu mensaje personalizado (si lo agregaste)

### **Botón de Acción:**
- Link directo al detalle de la incidencia

---

## ⚙️ Configuración SMTP (Ya está configurada)

```python
# Gmail SMTP
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'jorgemahos@gmail.com'
EMAIL_HOST_PASSWORD = 'sysyzuiempnhtrbz'  # App Password
DEFAULT_FROM_EMAIL = 'Score Card System <j.alvarez@sic.com.mx>'
```

---

## 🎨 Personalizar el Email

**Archivo:** `scorecard/templates/scorecard/emails/notificacion_incidencia.html`

Puedes modificar:
- Colores (buscar códigos hex como #0d6efd)
- Textos y mensajes
- Logo (agregar imagen)
- Estilos CSS inline

---

## 🔍 Troubleshooting

### ❌ No aparece el botón de notificación
**Solución:** Actualizar la página (Ctrl+F5)

### ❌ No aparecen destinatarios en el modal
**Verificar:**
- ¿El técnico tiene email configurado?
- ¿El jefe directo tiene email?
- Ver consola del navegador (F12) para errores

### ❌ El email no se envía
**Verificar:**
1. Que el empleado tenga email válido
2. Conexión a internet
3. Ver Django admin → Notificaciones para ver el error
4. Revisar consola del servidor de Django

### ❌ Jefe directo no aparece
**Solución:**
1. Ir al admin de empleados
2. Editar el técnico
3. Seleccionar su jefe directo
4. Guardar
5. Intentar de nuevo

---

## 📊 Ver Estadísticas

### **Total de Notificaciones:**
Admin → Notificaciones de Incidencias

### **Notificaciones por Incidencia:**
1. Admin → Incidencias
2. Click en una incidencia
3. Ver sección "Notificaciones" (al final)

### **Notificaciones Fallidas:**
Admin → Notificaciones de Incidencias
- Filtrar por: "Exitoso = No"
- Ver "Mensaje de error" para diagnosticar

---

## 💡 Tips y Buenas Prácticas

### ✅ **DO:**
- Siempre revisar que los empleados tengan email configurado
- Usar mensajes adicionales para contexto importante
- Verificar en el admin que la notificación se envió exitosamente
- Configurar jefes directos para aprovechar la jerarquía

### ❌ **DON'T:**
- No enviar notificaciones en exceso (spam)
- No olvidar configurar los jefes directos
- No usar emails personales en producción
- No compartir las credenciales SMTP

---

## 🎯 Casos de Uso

### **Caso 1: Notificar a un técnico sobre una incidencia**
1. Abrir detalle de incidencia
2. Enviar notificación
3. Seleccionar solo al técnico
4. Enviar

### **Caso 2: Escalar a jefe directo**
1. Abrir detalle de incidencia crítica
2. Enviar notificación
3. Seleccionar técnico + jefe directo
4. Agregar mensaje: "Requiere atención inmediata"
5. Enviar

### **Caso 3: Alerta al departamento de calidad**
1. Abrir detalle de reincidencia
2. Enviar notificación
3. Seleccionar técnico + jefe de calidad
4. Agregar mensaje sobre la reincidencia
5. Enviar

---

## 🔗 Enlaces Útiles

- **Admin Django:** http://localhost:8000/admin/
- **Lista Incidencias:** http://localhost:8000/scorecard/incidencias/
- **Dashboard:** http://localhost:8000/scorecard/
- **Empleados:** http://localhost:8000/admin/inventario/empleado/
- **Notificaciones:** http://localhost:8000/admin/scorecard/notificacionincidencia/

---

## 📞 Soporte

**Problemas técnicos:**
- Revisar consola del servidor Django
- Revisar consola del navegador (F12)
- Ver logs en admin de notificaciones

**Configuración:**
- Ver archivo: `SCORECARD_FASE4.md` (documentación completa)
- Ver código: `scorecard/emails.py`

---

**¡Sistema listo para usar!** 🎉

Desarrollado por: GitHub Copilot AI Assistant  
Fecha: Octubre 1, 2025
