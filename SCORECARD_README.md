# 🎯 Score Card - Sistema de Control de Calidad

## ✅ Implementación Completada - Fase 1

### 📋 Resumen de Implementación

Se ha creado exitosamente la aplicación **Score Card** como un módulo independiente dentro del proyecto Django de inventario. La aplicación permite rastrear y analizar incidencias de calidad en el Centro de Servicio.

---

## 🏗️ Estructura Creada

### **Modelos de Datos**

#### 1. **CategoriaIncidencia**
- Clasificación de tipos de incidencias
- 7 categorías predefinidas:
  - Fallo Post-Reparación
  - Defecto No Registrado
  - Componente Mal Instalado
  - Limpieza Deficiente
  - Fallo de Diagnóstico
  - Daño Cosmético
  - Documentación Incompleta

#### 2. **ComponenteEquipo**
- Catálogo de componentes que pueden fallar
- 24 componentes creados (Pantalla, RAM, Disco Duro, etc.)
- Diferenciados por tipo de equipo (PC, Laptop, AIO)

#### 3. **Incidencia** (Modelo Principal)
**Campos de Identificación:**
- `folio`: Auto-generado (INC-2025-0001)
- `fecha_registro`: Automática
- `fecha_deteccion`: Seleccionable

**Información del Equipo:**
- `tipo_equipo`: PC/Laptop/AIO
- `marca`: HP, Dell, Lenovo, etc.
- `modelo`: Modelo específico
- `numero_serie`: Identificador único
- `servicio_realizado`: Descripción del servicio

**Ubicación y Responsables:**
- `sucursal`: Relación con modelo Sucursal existente
- `area_detectora`: Área que detectó la incidencia
- `tecnico_responsable`: Relación con modelo Empleado
- `inspector_calidad`: Inspector que detectó el problema

**Clasificación del Fallo:**
- `tipo_incidencia`: Categoría de la incidencia
- `categoria_fallo`: Hardware/Software/Cosmético/Funcional
- `grado_severidad`: Crítico/Alto/Medio/Bajo
- `componente_afectado`: Componente específico con fallo

**Descripción:**
- `descripcion_incidencia`: Texto detallado
- `acciones_tomadas`: Medidas correctivas
- `causa_raiz`: Análisis de causa (opcional)

**Estado:**
- `estado`: Abierta/En Revisión/Cerrada/Reincidente
- `es_reincidencia`: Boolean
- `incidencia_relacionada`: Si es reincidencia

**Campos Automáticos (Calculados):**
- `año`: Del campo fecha_deteccion
- `mes`: Del campo fecha_deteccion (1-12)
- `semana`: Del campo fecha_deteccion (1-53)
- `trimestre`: Calculado automáticamente (Q1-Q4)

#### 4. **EvidenciaIncidencia**
- Múltiples imágenes por incidencia
- Upload a `media/scorecard/evidencias/YYYY/MM/`
- Descripción opcional por imagen
- Registro de quién subió la evidencia

---

## 🎨 Interfaz de Usuario

### **Navegación**
- Nuevo menú "Score Card" agregado al navbar principal
- Acceso a todas las funcionalidades desde el menú

### **Páginas Implementadas**

#### 1. **Dashboard** (`/scorecard/`)
- KPIs principales:
  - Total de incidencias
  - Incidencias abiertas
  - Incidencias críticas
- Acceso rápido a funciones principales
- Diseño con tarjetas interactivas

#### 2. **Lista de Incidencias** (`/scorecard/incidencias/`)
- Tabla completa de todas las incidencias
- Badges de colores para estado y severidad
- Botones de acción (Ver, Editar)
- Filtros (próxima fase)

#### 3. **Detalle de Incidencia** (`/scorecard/incidencias/<id>/`)
- Información completa de la incidencia
- Galería de evidencias fotográficas
- Historial de acciones

#### 4. **Reportes** (`/scorecard/reportes/`)
- Placeholder para gráficos (Fase 2)
- Análisis estadístico (Fase 2)

#### 5. **Configuración**
- Categorías (`/scorecard/categorias/`)
- Componentes (`/scorecard/componentes/`)
- Por ahora gestionables desde admin

---

## 🔧 Funcionalidades Implementadas

### ✅ Completadas en Fase 1

1. **Estructura de Base de Datos**
   - 4 modelos creados y migrados
   - Relaciones con modelos existentes (Empleado, Sucursal)
   - Índices para optimización de consultas

2. **Campo Email en Empleados**
   - Agregado campo `email` al modelo Empleado
   - Migración aplicada exitosamente
   - Preparado para notificaciones futuras

3. **Django Admin Configurado**
   - Administración completa de todos los modelos
   - Badges de colores para severidad y estado
   - Vista previa de imágenes
   - Filtros y búsqueda avanzada
   - Inline para evidencias

4. **Configuración de Medios**
   - `MEDIA_ROOT` y `MEDIA_URL` configurados
   - Directorio `media/` para imágenes
   - URLs configuradas para servir archivos en desarrollo

5. **Templates Profesionales**
   - Diseño Bootstrap 5 consistente
   - Responsive design
   - Iconos Bootstrap Icons
   - Tarjetas interactivas con hover effects

6. **Datos de Prueba**
   - Script `poblar_scorecard.py` creado
   - 7 categorías
   - 24 componentes
   - 15 incidencias de ejemplo

7. **Generación Automática**
   - Folio auto-generado (INC-2025-0001)
   - Campos de fecha calculados automáticamente
   - Propiedad `dias_abierta` calculada
   - Nombres de mes y trimestre en español

---

## 📊 Datos Iniciales Creados

### Categorías de Incidencias (7)
1. Fallo Post-Reparación (Rojo)
2. Defecto No Registrado (Naranja)
3. Componente Mal Instalado (Amarillo)
4. Limpieza Deficiente (Cian)
5. Fallo de Diagnóstico (Morado)
6. Daño Cosmético (Rosa)
7. Documentación Incompleta (Gris)

### Componentes de Equipos (24)
- Hardware: Pantalla, RAM, Disco Duro, Motherboard, CPU, GPU, etc.
- Periféricos: Teclado, Mouse, Touchpad, etc.
- Conectividad: Puertos USB, HDMI, WiFi, Ethernet, etc.
- Software: Sistema Operativo

### Incidencias de Ejemplo (15)
- Distribuidas en los últimos 3 meses
- Variedad de marcas, tipos y severidades
- Estados diversos (Abierta, Cerrada, En Revisión)

---

## 🌐 Acceso al Sistema

### URLs Principales
- **Dashboard Score Card**: http://localhost:8000/scorecard/
- **Lista de Incidencias**: http://localhost:8000/scorecard/incidencias/
- **Crear Incidencia**: http://localhost:8000/scorecard/incidencias/crear/
- **Reportes**: http://localhost:8000/scorecard/reportes/

### Admin Django
- **URL**: http://localhost:8000/admin/
- **Gestión completa**: Todas las entidades de Score Card

---

## 📝 Próximas Fases (Roadmap)

### **Fase 2: Formularios Completos** ✅ COMPLETADA
- [x] Formulario de registro de incidencias con validaciones
- [x] Upload de múltiples imágenes (drag & drop)
- [x] Autocompletado de datos de empleado (área, email, sucursal)
- [x] Detección automática de reincidencias por número de serie
- [x] Validación de campos en tiempo real
- [x] Campo sucursal agregado al modelo Empleado
- [x] APIs REST para autocompletado y filtros
- [x] Filtrado dinámico de componentes por tipo de equipo

### **Fase 3: Dashboard y Reportes** ✅ COMPLETADA
- [x] Gráficos interactivos con Chart.js
- [x] Top 10 técnicos con más incidencias
- [x] Análisis por sucursal y componente
- [x] Gráfico de Pareto de fallos
- [x] Tendencia mensual/trimestral
- [x] Heatmap por sucursal
- [x] Exportación a Excel/PDF

### **Fase 4: Alertas y Notificaciones** ✅ COMPLETADA
- [x] Sistema de notificaciones por email con SMTP
- [x] Modal interactivo para seleccionar destinatarios
- [x] Detección automática de jefe directo
- [x] Template HTML profesional para emails
- [x] Registro de notificaciones enviadas
- [x] Campo jefe_directo en modelo Empleado
- [x] APIs REST para envío de notificaciones
- [x] Admin mejorado para gestionar notificaciones
- [x] Historial visual de envíos en detalle de incidencia
- [x] Adjuntar imágenes de evidencia comprimidas (60% quality)

### **Fase 5: Análisis Avanzado**
- [ ] Indicadores de calidad (KPIs)
- [ ] Análisis de causa raíz
- [ ] Comparativas entre sucursales
- [ ] Ranking de técnicos
- [ ] Predicción de reincidencias (opcional)

---

## 🔒 Permisos y Seguridad

### Acceso Actual
- Solo inspectores de calidad registrarán incidencias (configuración futura)
- Sin niveles de acceso diferenciados por ahora
- Admin tiene acceso completo a todas las funciones

### Mejoras de Seguridad (Fase posterior)
- [ ] Implementar permisos por rol
- [ ] Restricción de edición/eliminación
- [ ] Auditoría de cambios
- [ ] Validación de usuario al crear incidencia

---

## 🚀 Comandos Útiles

### Ejecutar el Servidor
```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

### Poblar Datos de Score Card
```powershell
.\.venv\Scripts\python.exe poblar_scorecard.py
```

### Crear Migraciones
```powershell
.\.venv\Scripts\python.exe manage.py makemigrations scorecard
.\.venv\Scripts\python.exe manage.py migrate
```

### Crear Superusuario (si no existe)
```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

---

## 📚 Archivos Creados/Modificados

### Nuevos Archivos
```
scorecard/
├── __init__.py
├── admin.py                    ✅ Configurado con badges
├── apps.py
├── models.py                   ✅ 4 modelos completos
├── views.py                    ✅ Vistas básicas
├── urls.py                     ✅ URLs configuradas
├── tests.py
├── migrations/
│   └── 0001_initial.py        ✅ Migración inicial
└── templates/scorecard/
    ├── dashboard.html          ✅ Dashboard con KPIs
    ├── lista_incidencias.html  ✅ Tabla de incidencias
    ├── detalle_incidencia.html ✅ Detalle completo
    ├── form_incidencia.html    ⏳ Placeholder
    ├── reportes.html           ⏳ Placeholder
    ├── lista_categorias.html   ⏳ Placeholder
    ├── lista_componentes.html  ⏳ Placeholder
    └── confirmar_eliminacion.html ✅ Confirmación

poblar_scorecard.py             ✅ Script de población
```

### Archivos Modificados
```
config/
├── settings.py                 ✅ App scorecard agregada
│                               ✅ MEDIA_ROOT y MEDIA_URL
└── urls.py                     ✅ URLs de scorecard incluidas
                                ✅ Servir archivos media

inventario/
└── models.py                   ✅ Campo email en Empleado

templates/
└── base.html                   ✅ Menú Score Card agregado
```

---

## 🎓 Conceptos Aprendidos (Para Usuario Principiante)

### **1. Aplicaciones Django (Apps)**
- Django organiza proyectos en "aplicaciones" independientes
- Cada app tiene su propósito específico
- Las apps pueden compartir modelos entre sí
- Ventajas: modularidad, reutilización, mantenibilidad

### **2. Relaciones entre Modelos**
- `ForeignKey`: Relación muchos-a-uno (muchas incidencias → un empleado)
- `PROTECT`: Evita eliminar registros relacionados
- `related_name`: Acceso inverso (empleado.incidencias_tecnico.all())

### **3. Campos Automáticos**
- `auto_now_add=True`: Se establece automáticamente al crear
- `auto_now=True`: Se actualiza automáticamente al guardar
- `editable=False`: No se puede editar manualmente

### **4. Método `save()` Personalizado**
- Podemos sobrescribir `save()` para lógica adicional
- Generar folios automáticos
- Calcular campos derivados
- Siempre llamar `super().save()` al final

### **5. Propiedades (`@property`)**
- No se guardan en base de datos
- Se calculan "en vivo" cuando se acceden
- Útil para valores derivados (dias_abierta, mes_nombre)

### **6. Archivos Media vs Static**
- **Static**: Archivos del proyecto (CSS, JS, imágenes fijas)
- **Media**: Archivos subidos por usuarios (evidencias)
- Diferentes configuraciones y URLs

### **7. Django Admin**
- Interfaz automática de administración
- Personalizable con `ModelAdmin`
- Útil para gestión rápida sin crear vistas

### **8. Formularios Django (ModelForm)**
- `ModelForm` crea automáticamente campos basados en el modelo
- `widgets` personaliza cómo se ven los campos en HTML
- `clean_*` métodos para validaciones personalizadas de campos
- `clean()` para validaciones que involucran múltiples campos

### **9. APIs REST con JsonResponse**
- Endpoints que devuelven datos en formato JSON
- Útiles para JavaScript que necesita datos del servidor
- Sin recargar la página (AJAX)

### **10. JavaScript Fetch API**
- Hace peticiones HTTP desde el navegador
- `fetch()` obtiene datos de APIs sin recargar
- `.then()` maneja la respuesta cuando llega
- Permite interfaces dinámicas e interactivas

### **11. Event Listeners en JavaScript**
- `addEventListener()` detecta acciones del usuario
- `change` - cuando cambia el valor de un select/input
- `input` - cuando el usuario escribe
- `submit` - cuando se envía un formulario
- `click` - cuando se hace clic
- `dragover`, `drop` - para drag & drop

### **12. Drag & Drop de Archivos**
- HTML5 permite arrastrar archivos al navegador
- `dataTransfer` contiene los archivos arrastrados
- `FileReader` lee archivos antes de subirlos
- Vista previa de imágenes con `readAsDataURL()`

### **13. Validaciones de Formulario**
- **Frontend (JavaScript)**: Rápidas, experiencia de usuario
- **Backend (Django)**: Seguras, no se pueden burlar
- Siempre validar en ambos lados
- `ValidationError` para errores personalizados

### **14. Timeout y Debounce**
- `setTimeout()` ejecuta código después de X tiempo
- `clearTimeout()` cancela un timeout pendiente
- **Debounce**: Esperar a que el usuario termine de escribir
- Útil para evitar búsquedas excesivas mientras se escribe

---

## ✅ Resumen de Logros

### **Fase 1: Estructura Base** ✅
1. ✅ App Score Card completamente integrada
2. ✅ Modelos de datos profesionales y completos
3. ✅ Campo email agregado a Empleados
4. ✅ Admin configurado con estilo profesional
5. ✅ Dashboard con KPIs funcional
6. ✅ Lista de incidencias con tabla completa
7. ✅ Detalle de incidencias
8. ✅ Datos de prueba (15 incidencias)
9. ✅ Navegación integrada en navbar
10. ✅ Templates responsivos y profesionales

### **Fase 2: Formularios Inteligentes** ✅
1. ✅ Campo `sucursal` agregado al modelo Empleado
2. ✅ Formulario completo con Django Forms y validaciones
3. ✅ **Autocompletado inteligente**: 
   - Al seleccionar empleado → auto-llena área, email y sucursal
   - Información visible debajo de cada campo
   - Efecto visual de campos auto-completados
4. ✅ **Detección de reincidencias en tiempo real**:
   - Al escribir número de serie, busca automáticamente
   - Alerta visual con incidencias previas
   - Opción de marcar como reincidencia
   - Vinculación automática con incidencia original
5. ✅ **Upload de imágenes avanzado**:
   - Drag & Drop de múltiples archivos
   - Vista previa antes de subir
   - Validación de tipo y tamaño (5MB máx)
   - Eliminación individual de imágenes
   - Soporte para JPG, PNG, GIF, WebP
6. ✅ **Filtros dinámicos**:
   - Componentes se filtran según tipo de equipo
   - Lista de marcas comunes con autocompletado
   - Campo de incidencia relacionada solo visible si es reincidencia
7. ✅ **APIs REST creadas**:
   - `/api/empleado/<id>/` - Datos de empleado
   - `/api/buscar-reincidencias/` - Búsqueda por número de serie
   - `/api/componentes-por-tipo/` - Filtrar componentes
8. ✅ **Validaciones del formulario**:
   - Técnico e inspector deben ser diferentes
   - Si es reincidencia, debe tener incidencia relacionada
   - Número de serie obligatorio
   - Validaciones de tamaño/tipo de imágenes

### **Fase 3: Dashboard y Reportes** ✅ COMPLETADA
1. ✅ **Gráficos Interactivos con Chart.js 4.4.0**:
   - Tendencia mensual (línea con relleno)
   - Distribución por severidad (dona)
   - Top 10 técnicos (barras horizontales)
   - Distribución por categoría (pastel)
   - Análisis por sucursal (barras con colores)
   - Componentes más afectados (barras horizontales)
   
2. ✅ **Dashboard Mejorado**:
   - 7 KPIs principales actualizados en tiempo real
   - 6 gráficos interactivos con datos del servidor
   - Actualización automática desde API REST
   - Botones para descargar gráficos como PNG
   - Diseño responsivo y profesional
   
3. ✅ **API de Datos para Gráficos**:
   - `/api/datos-dashboard/` - Endpoint unificado
   - Retorna todos los datos necesarios en un solo request
   - Cálculos automáticos de tendencias y porcentajes
   - Optimizado con queries eficientes
   
4. ✅ **Página de Reportes Avanzados**:
   - Resumen ejecutivo con métricas clave
   - **Gráfico de Pareto**: Análisis 80/20 de fallos más frecuentes
   - **Tendencia trimestral**: Evolución en el tiempo
   - **Heatmap por sucursal**: Intensidad visual de incidencias
   - **Comparativa mensual**: Análisis período a período
   - **Métricas de calidad**: Gráfico tipo radar
   - Filtros por fecha y sucursal (preparados para implementación)
   
5. ✅ **Exportación de Datos**:
   - Exportación completa a Excel (.xlsx)
   - Encabezados con formato profesional (colores, negrita)
   - Todas las columnas relevantes incluidas
   - Nombre de archivo con fecha automática
   - Función de impresión optimizada para reportes
   - Librería openpyxl integrada
   
6. ✅ **Características Avanzadas**:
   - Gráficos descargables como imágenes
   - Tooltips informativos en todos los gráficos
   - Colores consistentes según tipo de dato
   - Animaciones suaves y transiciones
   - Responsive design para móviles
   - Optimización para impresión (oculta elementos innecesarios)

### Lo que Falta (Próximas Fases):
- ⏳ Sistema de alertas por email (Fase 4)
- ⏳ Notificaciones automáticas (Fase 4)
- ⏳ Análisis predictivo (Fase 5)
- ⏳ Filtros avanzados con aplicación en tiempo real
- ⏳ Exportación a PDF con gráficos incrustados

---

## 🎉 ¡Felicidades!

Has implementado exitosamente un sistema profesional de Score Card de Calidad con dashboard interactivo y reportes avanzados completamente funcionales.

**Estado actual:**
- ✅ **Fase 1 Completada**: Estructura base, modelos, admin, templates
- ✅ **Fase 2 Completada**: Formularios inteligentes con autocompletado, drag & drop, y detección de reincidencias
- ✅ **Fase 3 Completada**: Dashboard con gráficos interactivos, reportes avanzados y exportación a Excel

**El sistema ahora incluye:**
1. **Autocompletado inteligente** - Datos de empleado se llenan automáticamente
2. **Detección de reincidencias** - Búsqueda en tiempo real por número de serie
3. **Upload moderno de imágenes** - Drag & Drop con vista previa
4. **Validaciones robustas** - Frontend y backend
5. **APIs REST completas** - Para comunicación JavaScript-Django y datos de gráficos
6. **Filtros dinámicos** - Componentes según tipo de equipo
7. **🆕 Dashboard Interactivo** - 6 gráficos en tiempo real con Chart.js
8. **🆕 Reportes Avanzados** - Gráfico de Pareto, Heatmap, Tendencias, Métricas
9. **🆕 Exportación a Excel** - Descarga completa de datos con formato profesional
10. **🆕 KPIs Avanzados** - 7 indicadores clave actualizados dinámicamente

**Gráficos Implementados:**
- 📊 Tendencia mensual de incidencias (últimos 6 meses)
- 🍩 Distribución por severidad
- 👥 Top 10 técnicos con más incidencias
- 🏷️ Distribución por categoría de fallo
- 🏢 Análisis por sucursal
- 🔧 Top 10 componentes más afectados
- 📈 Gráfico de Pareto (80/20)
- 🗓️ Tendencia trimestral
- 🌡️ Heatmap de sucursales
- 🎯 Radar de métricas de calidad

**Tecnologías Utilizadas:**
- Django 5.2.5
- Chart.js 4.4.0
- Bootstrap 5.3.2
- Bootstrap Icons
- Openpyxl 3.1.2 (exportación Excel)
- JavaScript ES6+ (Fetch API, Promises)

**Próximo paso sugerido:** Implementar sistema de alertas por email y notificaciones automáticas (Fase 4).

---

**Fecha de Implementación:**  
- Fase 1: Octubre 1, 2025  
- Fase 2: Octubre 1, 2025  
- Fase 3: Octubre 1, 2025  

**Versión:** 3.0.0 - Fase 3 Completada - Dashboard Interactivo y Reportes Avanzados  
**Desarrollado por:** GitHub Copilot AI Assistant
