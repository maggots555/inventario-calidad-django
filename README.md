# 🏥 Sistema Integrado de Gestión Técnica y Control de Calidad

<!-- Badges -->
<p align="center">
  <img src="https://img.shields.io/badge/Django-5.2.5-092E20?style=for-the-badge&logo=django&logoColor=white" alt="Django 5.2.5">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/TypeScript-5.9.3-3178C6?style=for-the-badge&logo=typescript&logoColor=white" alt="TypeScript 5.9.3">
  <img src="https://img.shields.io/badge/Bootstrap-5.3.2-7952B3?style=for-the-badge&logo=bootstrap&logoColor=white" alt="Bootstrap 5.3.2">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Plotly-6.3+-3F4F75?style=for-the-badge&logo=plotly&logoColor=white" alt="Plotly">
  <img src="https://img.shields.io/badge/Pandas-2.3+-150458?style=for-the-badge&logo=pandas&logoColor=white" alt="Pandas">
  <img src="https://img.shields.io/badge/scikit--learn-1.5+-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white" alt="Scikit-learn">
  <img src="https://img.shields.io/badge/Chart.js-4.4.0-FF6384?style=for-the-badge&logo=chartdotjs&logoColor=white" alt="Chart.js">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Status-Production-success?style=for-the-badge" alt="Status">
  <img src="https://img.shields.io/badge/Version-3.0-blue?style=for-the-badge" alt="Version">
  <img src="https://img.shields.io/badge/License-Proprietary-red?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Modules-4-orange?style=for-the-badge" alt="Modules">
</p>

---

**Sistema empresarial de última generación** para centros de servicio técnico de equipos de cómputo con **Machine Learning**, **Analytics avanzado** y **TypeScript frontend**.

Combina gestión de órdenes de servicio, control de calidad, **predicciones con IA**, **dashboards interactivos tipo Power BI**, seguimiento de incidencias y sistema RHITSO para casos complejos.

---

## 📸 Capturas de Pantalla

### Dashboard Principal - Score Card

<p align="center">
  <img src="docs/screenshots/dashboard_scorecard.png" alt="Dashboard Score Card" width="800">
  <br>
  <em>Dashboard interactivo con métricas en tiempo real, gráficas de tendencias y KPIs principales</em>
</p>

### Gestión de Órdenes de Servicio

<p align="center">
  <img src="docs/screenshots/lista_ordenes.png" alt="Lista de Órdenes" width="800">
  <br>
  <em>Sistema de gestión de órdenes con 21 estados de seguimiento y filtros avanzados</em>
</p>

### Detalle de Orden con RHITSO

<p align="center">
  <img src="docs/screenshots/detalle_orden_rhitso.png" alt="Detalle Orden RHITSO" width="800">
  <br>
  <em>Vista detallada con seguimiento RHITSO, timeline de eventos e incidencias</em>
</p>

### Registro de Incidencias de Calidad

<p align="center">
  <img src="docs/screenshots/form_incidencia.png" alt="Formulario Incidencia" width="800">
  <br>
  <em>Formulario inteligente con autocompletado, detección de reincidencias y drag & drop de imágenes</em>
</p>

### Reportes Avanzados con 7 Tabs

<p align="center">
  <img src="docs/screenshots/reportes_avanzados.png" alt="Reportes Avanzados" width="800">
  <br>
  <em>Sistema de reportes con Pareto, heatmaps, análisis de atribuibilidad y exportación Excel</em>
</p>

### Sistema de Notificaciones

<p align="center">
  <img src="docs/screenshots/notificaciones.png" alt="Sistema de Notificaciones" width="800">
  <br>
  <em>Historial de notificaciones enviadas con seguimiento de éxito/fallo</em>
</p>

> **Nota**: Las capturas de pantalla se encuentran en la carpeta [`docs/screenshots/`](./docs/screenshots/). Si no las ves, significa que aún no se han agregado al repositorio.

---

## 🎯 Módulos Principales del Sistema

### 1️⃣ **Servicio Técnico** - Gestión de Órdenes de Reparación

**Módulo**: `servicio_tecnico`

Sistema completo de órdenes de servicio técnico con flujo dual:

- **📋 Diagnóstico y Cotización**: Evaluación técnica → Cotización → Aprobación cliente → Reparación
- **🛍️ Venta Mostrador**: Servicios directos sin diagnóstico (formateos, instalaciones, upgrades)
- **🔄 Sistema Híbrido**: Una orden puede combinar ambos flujos (diagnóstico + ventas adicionales)

**Características principales:**

- ✅ Gestión completa del ciclo de vida de reparaciones
- ✅ 21 estados de seguimiento (desde ingreso hasta entrega)
- ✅ Sistema de cotización con gestión de piezas y proveedores
- ✅ Seguimiento de piezas solicitadas (WPB, DOA, PNC)
- ✅ Referencias de gama de equipos para cotización rápida
- ✅ Historial completo de eventos por orden
- ✅ Sistema de imágenes con tipos (ingreso, diagnóstico, reparación, entrega)
- ✅ Venta mostrador con paquetes predefinidos y servicios adicionales
- ✅ Integración con sistema de calidad para reingresos

**Estados del flujo:**

```
INGRESO → ASIGNADO → EN DIAGNÓSTICO → DIAGNÓSTICO ENVIADO →
EQUIPO DIAGNOSTICADO → COTIZACIÓN ENVIADA → CLIENTE ACEPTA →
PIEZAS SOLICITADAS → PIEZAS RECIBIDAS → EN REPARACIÓN →
REPARACIÓN COMPLETADA → CONTROL CALIDAD → LISTO PARA ENTREGA → ENTREGADO
```

**Casos especiales:**

- WPB (Wrong Part Bought): Pieza incorrecta
- DOA (Dead On Arrival): Pieza dañada
- PNC (Part Not Compatible): Parte no disponible
- Cliente rechaza cotización

---

### 2️⃣ **Score Card de Calidad** - Control de Calidad e Incidencias

**Módulo**: `scorecard`

Sistema avanzado de registro y análisis de incidencias de calidad en reparaciones.

**Características principales:**

- ✅ Registro detallado de incidencias con 4 niveles de severidad (Baja, Media, Alta, Crítica)
- ✅ Clasificación por tipo de fallo (Estético, Funcional, Software, Hardware, Documentación)
- ✅ **Sistema de Atribuibilidad**: Distingue entre errores atribuibles al técnico vs. causas externas
- ✅ Detección automática de reincidencias por número de serie
- ✅ Gestión de evidencias fotográficas con drag & drop
- ✅ **Sistema de Notificaciones por Email**: Automatizado y manual con múltiples destinatarios
- ✅ Workflow completo: Abierta → En Revisión → Reincidente → Cerrada
- ✅ Seguimiento de componentes defectuosos
- ✅ Justificaciones para incidencias NO atribuibles

**Dashboard de Métricas:**

- 📊 KPIs en tiempo real (Total incidencias, Tasa de reincidencia, Promedio de cierre)
- 📈 Gráficas de tendencias y análisis
- 🏆 Ranking de técnicos por desempeño
- 📉 Análisis de Pareto de fallos más frecuentes

**Reportes Avanzados con 7 Tabs:**

1. **Resumen Ejecutivo**: KPIs, Pareto, Heatmaps, Tendencias
2. **Atribuibilidad**: Análisis de responsabilidad técnica
3. **Por Técnico**: Scorecard individual de cada técnico
4. **Reincidencias**: Cadenas de reincidencias detectadas
5. **Tiempos**: Análisis de tiempos de cierre y alertas
6. **Componentes**: Componentes más problemáticos
7. **Notificaciones**: Análisis del sistema de emails

**Exportación:**

- 📥 Excel completo con múltiples hojas de análisis
- 🖨️ Impresión optimizada de reportes

---

### 3️⃣ **Sistema RHITSO** - Seguimiento de Reparaciones Complejas

**Módulo**: `servicio_tecnico` (submódulo)

Subsistema especializado para reparaciones que requieren seguimiento externo con RHITSO (proveedor/partner).

**Características principales:**

- ✅ 12 estados específicos de seguimiento RHITSO
- ✅ Gestión de múltiples owners (Dell, HP, Lenovo, Asus, etc.)
- ✅ Clasificación por complejidad (Simple, Moderada, Compleja)
- ✅ Registro de incidencias durante reparación externa
- ✅ Sistema de notificaciones automáticas por cambios de estado
- ✅ Generación de PDFs con resumen completo
- ✅ Cálculo de días hábiles para SLA
- ✅ Paleta de colores distintiva para identificación visual

**Estados RHITSO:**

```
PENDIENTE ENVÍO → ENVIADO RHITSO → RECIBIDO RHITSO →
EN DIAGNÓSTICO RHITSO → COTIZADO → APROBADO → EN REPARACIÓN →
REPARADO → ENVIADO RETORNO → RECIBIDO → PROBADO → FINALIZADO
```

**Incidencias RHITSO:**

- Gravedad: Baja, Media, Alta, Crítica
- Impacto al cliente: Ninguno, Bajo, Medio, Alto
- Prioridad: Baja, Normal, Alta, Urgente
- Seguimiento completo con notificaciones

---

### 4️⃣ **Inventario** - Gestión de Productos

**Módulo**: `inventario`

Módulo base de gestión de productos con control de calidad simple.

**Características:**

- ✅ CRUD completo de productos
- ✅ Control de calidad (Bueno, Regular, Malo)
- ✅ Gestión de sucursales y empleados (base compartida)
- ✅ Sistema de usuarios con roles personalizados

---

## 🚀 Funcionalidades Destacadas del Sistema

### 🔐 Sistema de Autenticación y Permisos

- Login personalizado con usuarios de Django
- Relación Usuario ↔ Empleado para gestión completa
- Forzado de cambio de contraseña en primer inicio
- Permisos granulares por módulo

---

## 🤖 Machine Learning & Inteligencia Artificial

### Sistema ML Avanzado (`ml_advanced/`)

El sistema integra un módulo completo de Machine Learning con 4 componentes especializados:

#### 1. **Optimizador de Precios con ML**

- **Archivo**: `optimizador_precios.py` (21KB)
- **Funcionalidad**:
  - Predicción de precios óptimos para cotizaciones
  - Análisis de elasticidad de precios por gama y marca
  - Recomendaciones basadas en histórico de aceptación
  - Ajuste automático según patrones de comportamiento del cliente

#### 2. **Análisis de Motivos de Rechazo**

- **Archivo**: `motivo_rechazo.py` (24KB)
- **Funcionalidad**:
  - Clasificación automática de rechazos
  - Predicción de probabilidad de rechazo pre-envío
  - Identificación de patrones en rechazos por técnico/sucursal
  - Sugerencias inteligentes para mejorar tasa de aceptación

#### 3. **Recomendador de Acciones**

- **Archivo**: `recomendador_acciones.py` (29KB)
- **Funcionalidad**:
  - Sistema de recomendaciones inteligentes basado en contexto
  - Predicción de próximas acciones necesarias por orden
  - Optimización de flujo de trabajo
  - Alertas proactivas basadas en ML

#### 4. **Predictor de Servicio Técnico**

- **Archivo**: `ml_predictor.py` (21KB)
- **Funcionalidad**:
  - Predicción de tiempo de reparación estimado
  - Estimación de probabilidad de fallo/reincidencia
  - Análisis de tendencias de servicio
  - Detección de anomalías en procesos

---

## 📊 Dashboard Analytics Avanzado (Tipo Power BI)

### Sistema de Visualizaciones Interactivas con Plotly

**Archivo**: `plotly_visualizations.py` (3939 líneas, 148KB)

Clase `DashboardCotizacionesVisualizer` con **50+ métodos de visualización** que generan gráficos HTML interactivos profesionales:

**Gráficos Implementados:**

- **Temporales**: Evolución de cotizaciones, comparativos entre períodos, tendencias
- **Distribución**: Histogramas + Boxplots de costos, análisis de rangos
- **Jerárquicos**: Sunburst (Gama → Tipo → Marca), Sankey (flujos), Treemap
- **Avanzados**: Heatmaps de desempeño, Pareto, rankings dinámicos, matrices de correlación

**Características Destacadas:**

- ✅ **Totalmente interactivo**: Zoom, pan, hover tooltips, click events
- ✅ **Paleta Bootstrap**: Colores consistentes con el diseño del sistema
- ✅ **Responsive**: Mobile-friendly y adaptable
- ✅ **Exportación**: PNG, SVG, PDF desde el navegador
- ✅ **Performance**: Optimizado para grandes volúmenes de datos

**Tipos de Análisis:**

- Tasas de aceptación por sucursal/técnico/gama
- Evolución temporal (diario, semanal, mensual)
- Top piezas rechazadas/aceptadas
- Distribución de costos y outliers
- Análisis de sugerencias técnicas vs. solicitudes de cliente
- Efectividad de cotizaciones por categoría

---

## 💻 TypeScript Integration - Frontend Type-Safe

### Stack Frontend Moderno

El sistema utiliza **TypeScript 5.9.3** para desarrollo frontend profesional y mantenible.

**Configuración**:

- `tsconfig.json` - Strict mode, ES2018 target
- Compilación automática: `static/ts/` → `static/js/`
- Source maps para debugging
- Types de Bootstrap incluidos (@types/bootstrap)

**Módulos TypeScript** (8 archivos, 160KB total):

1. **`base.ts`** (23KB) - Funcionalidad base compartida, utilities y helpers
2. **`dashboard_cotizaciones.ts`** (22KB) - Dashboard interactivo con filtros dinámicos
3. **`dashboard_rhitso.ts`** (35KB) - Timeline RHITSO, estadísticas en tiempo real
4. **`dashboard_seguimiento_piezas.ts`** (20KB) - Tracking WPB, DOA, PNC
5. **`lightbox_galeria.ts`** (15KB) - Sistema de galería completo con navegación
6. **`login_particles.ts`** (6KB) - Efectos de partículas, canvas interactivo
7. **`plantillas_rechazo.ts`** (11KB) - Gestión de plantillas con autocompletado
8. **`scorecard_form.ts`** (24KB) - Formularios con detección de reincidencias

**Ventajas del TypeScript:**

- ✅ Type safety en todo el frontend
- ✅ Autocompletado inteligente en IDEs
- ✅ Refactoring seguro sin romper funcionalidad
- ✅ Detección temprana de errores
- ✅ Mejor mantenibilidad y escalabilidad del código

**Scripts disponibles**:

```bash
npm run build  # Compilar TypeScript a JavaScript
npm run watch  # Modo watch para desarrollo (recompila automáticamente)
```

---

### 📧 Sistema de Notificaciones por Email

**Configurado con Gmail SMTP**

- Notificaciones automáticas de incidencias
- Envío manual con múltiples destinatarios
- Plantillas profesionales con branding
- Historial completo de notificaciones enviadas
- Seguimiento de éxito/fallo de envíos

### 📊 Sistema de Reportes y Análisis

- **Dashboards interactivos con Plotly**: 50+ visualizaciones tipo Power BI
- **Chart.js**: Gráficas básicas complementarias
- Filtros avanzados (fechas, sucursales, técnicos, severidad, etc.)
- Exportación a Excel con múltiples hojas y análisis estadístico
- Gráficas dinámicas: Pareto, Sunburst, Sankey, Heatmaps, Rankings
- Análisis de reincidencias y tiempos de resolución
- **Machine Learning**: Predicciones y recomendaciones inteligentes

### 📱 Interfaz de Usuario Moderna

- **TypeScript 5.9.3**: Frontend type-safe con 8 módulos (160KB)
- **Glassmorphism UI**: Efectos 3D y transparencias modernas
- **Particle Effects**: Canvas interactivo en login/logout
- Diseño responsivo con Bootstrap 5.3.2
- Drag & Drop avanzado para carga de imágenes
- Autocompletado inteligente en formularios
- Pestañas dinámicas para organización de datos
- **Lightbox Gallery**: Sistema completo con navegación (TypeScript)
- Sistema de badges con colores semánticos

### 🔄 APIs REST Internas

- Endpoints para carga dinámica de datos
- Autocompletado de campos por relaciones
- Filtrado de componentes por tipo de equipo
- Búsqueda de reincidencias en tiempo real
- Datos para gráficas y reportes

---

## 📋 Características Técnicas

### Backend (Django 5.2.5)

- **Arquitectura MVC** con separación de responsabilidades
- **ORM avanzado** con relaciones complejas (OneToOne, ForeignKey, ManyToMany)
- **Signals de Django** para automatizaciones (cambios de estado, notificaciones)
- **Validaciones personalizadas** a nivel de modelo y formulario
- **Sistema de archivos** con gestión de media uploads
- **Custom Template Tags y Filters** para lógica de presentación
- **APIs REST** con JsonResponse para frontend dinámico
- **Machine Learning Models** integrados en el flujo de trabajo

### Frontend Moderno

- **TypeScript 5.9.3** - Type-safe development (8 módulos, 160KB)
- **Plotly.js** - Dashboards interactivos tipo Power BI
- **Bootstrap 5.3.2** - Framework CSS responsivo
- **Bootstrap Icons** - Iconografía consistente
- **Chart.js 4.4.0** - Gráficas básicas complementarias
- **JavaScript ES2018+** - Interactividad moderna
- **CSS modular** organizado por responsabilidad
- **Glassmorphism & 3D Effects** - UI de última generación
- **Drag & Drop API** nativa para carga de archivos

### Data Science & Analytics

- **Plotly 6.3.0** - Visualizaciones interactivas profesionales
- **Pandas 2.3.0** - Análisis y manipulación de datos
- **Scikit-learn 1.5.0** - Machine Learning models
- **Matplotlib 3.9.0** - Gráficos estadísticos
- **Seaborn 0.13.0** - Visualizaciones estadísticas avanzadas
- **NumPy** - Cálculos numéricos eficientes

### Base de Datos

- **SQLite3** (desarrollo)
- **Migraciones versionadas** con Django Migrations
- **Índices optimizados** para consultas frecuentes
- **Backup automatizado** de base de datos

### Seguridad

- **CSRF Protection** habilitada
- **Sanitización de inputs** con validadores Django
- **Permisos granulares** por modelo
- **Passwords hasheados** con PBKDF2
- **Variables de entorno** (.env) para configuración sensible

---

## 🗄️ Modelos de Datos Principales

### Servicio Técnico

- **OrdenServicio**: Orden principal (21 estados posibles)
- **DetalleEquipo**: Información técnica del equipo
- **Cotizacion**: Cotizaciones de reparación
- **PiezaCotizada**: Piezas en cotizaciones
- **SeguimientoPieza**: Tracking de piezas solicitadas
- **VentaMostrador**: Ventas directas
- **PiezaVentaMostrador**: Items de venta mostrador
- **ImagenOrden**: Evidencias fotográficas (4 tipos)
- **HistorialOrden**: Eventos de auditoría
- **EstadoRHITSO**: Estados de proceso RHITSO
- **SeguimientoRHITSO**: Fechas clave del proceso
- **IncidenciaRHITSO**: Problemas durante reparación externa

### Score Card

- **Incidencia**: Registro de fallas de calidad
- **EvidenciaIncidencia**: Imágenes de incidencias
- **TipoIncidencia**: Categorización de fallos
- **ComponenteEquipo**: Catálogo de componentes
- **NotificacionIncidencia**: Historial de emails
- **DestinatarioNotificacion**: Destinatarios de notificaciones

### Inventario (Base)

- **Producto**: Productos en inventario
- **Sucursal**: Sucursales de la empresa
- **Empleado**: Personal (técnicos, inspectores, etc.)

---

## 🎨 Paletas de Colores del Sistema

### Estados de Orden (21 estados)

- **Azul**: Ingreso/Recepción
- **Púrpura**: Diagnóstico
- **Naranja**: Cotización
- **Verde**: Aprobaciones
- **Amarillo**: Gestión de piezas
- **Cian**: Reparación
- **Verde oscuro**: Calidad
- **Rojo**: Rechazos/Problemas

### Severidad de Incidencias

- **Verde (#27ae60)**: Baja
- **Amarillo (#f39c12)**: Media
- **Naranja (#e67e22)**: Alta
- **Rojo (#e74c3c)**: Crítica

### Sistema RHITSO

- Paleta distintiva con colores Tailwind
- Estados claramente diferenciables
- Badges con contraste automático

---

## 📱 Rutas Principales del Sistema

### Servicio Técnico

- `/servicio/` - Lista de órdenes
- `/servicio/crear/` - Nueva orden
- `/servicio/<id>/` - Detalle de orden
- `/servicio/<id>/editar/` - Editar orden
- `/servicio/<id>/cotizacion/` - Crear cotización
- `/servicio/<id>/venta-mostrador/` - Crear venta
- `/servicio/rhitso/` - Gestión RHITSO

### Score Card

- `/scorecard/` - Dashboard principal
- `/scorecard/incidencias/` - Lista de incidencias
- `/scorecard/incidencias/crear/` - Registrar incidencia
- `/scorecard/incidencias/<id>/` - Detalle con acciones
- `/scorecard/reportes/` - Reportes avanzados (7 tabs)
- `/scorecard/api/` - APIs REST internas

### Sistema

- `/admin/` - Panel de administración Django
- `/login/` - Autenticación de usuarios
- `/` - Página principal (redirect según rol)

---

## 🛠️ Instalación y Configuración

### Requisitos Previos

- Python 3.10+
- pip (gestor de paquetes Python)
- Git
- Cuenta Gmail (para notificaciones por email)

### Instalación

### Instalación

1. **Clonar el repositorio**

```bash
git clone https://github.com/maggots555/inventario-calidad-django.git
cd inventario-calidad-django
```

2. **Crear y activar entorno virtual**

```bash
python -m venv venv

# En Windows:
venv\Scripts\activate

# En macOS/Linux:
source venv/bin/activate
```

3. **Instalar dependencias**

```bash
pip install -r requirements.txt
```

4. **Configurar variables de entorno**

Crear archivo `.env` en la raíz del proyecto:

```env
# Django
SECRET_KEY=tu-secret-key-aqui
DEBUG=True

# Email (Gmail)
EMAIL_HOST_USER=tu-email@gmail.com
EMAIL_HOST_PASSWORD=tu-app-password-gmail

# Notificaciones
CORREO_REMITENTE_NOMBRE=Sistema de Calidad
CORREO_REMITENTE_EMAIL=sistema@tuempresa.com
```

**Obtener App Password de Gmail:**

1. Ir a [Cuenta de Google](https://myaccount.google.com/)
2. Seguridad → Verificación en dos pasos (activar)
3. Contraseñas de aplicaciones → Generar
4. Copiar el password de 16 caracteres

5. **Aplicar migraciones**

```bash
python manage.py migrate
```

6. **Crear superusuario**

```bash
python manage.py createsuperuser
```

7. **Poblar datos iniciales** (Opcional)

```bash
# Sucursales y empleados base
python scripts/poblado/poblar_sistema.py

# Catálogo de servicios
python scripts/poblado/poblar_servicios.py

# Estados RHITSO
python scripts/poblado/poblar_estados_rhitso.py

# Datos de ejemplo para Score Card
python scripts/poblado/poblar_scorecard.py
```

8. **Ejecutar el servidor**

```bash
python manage.py runserver
```

9. **Acceder al sistema**

- Sistema: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin/

---

## 🎯 Uso del Sistema

### Para Recepcionistas

1. **Crear orden de servicio** desde `/servicio/crear/`
2. Capturar datos del cliente y equipo
3. Tomar fotos de ingreso
4. Asignar técnico responsable

### Para Técnicos

1. Ver órdenes asignadas en `/servicio/`
2. Actualizar estado a "En Diagnóstico"
3. Subir imágenes de diagnóstico
4. Crear cotización con piezas necesarias
5. Actualizar a "Reparación" tras aprobación
6. Marcar como "Control de Calidad" al terminar

### Para Control de Calidad

1. Revisar órdenes en "Control de Calidad"
2. Verificar funcionamiento del equipo
3. **Si encuentra problemas**: Registrar incidencia en Score Card
4. Aprobar o devolver a técnico
5. Cambiar estado a "Listo para Entrega"

### Para Inspectores de Calidad

1. Dashboard en `/scorecard/`
2. Registrar incidencias con evidencias
3. Enviar notificaciones a responsables
4. Marcar incidencias como NO atribuibles (si aplica)
5. Cerrar incidencias resueltas
6. Generar reportes ejecutivos

### Para Gerencia

1. Ver dashboard de Score Card
2. Analizar reportes avanzados (7 tabs)
3. Exportar Excel para análisis externo
4. Revisar métricas de técnicos
5. Identificar tendencias y áreas de mejora

---

## 📊 KPIs y Métricas del Sistema

### Servicio Técnico

- Órdenes activas por estado
- Tiempo promedio de reparación
- Tasa de aprobación de cotizaciones
- Órdenes en cada estado del flujo
- Días promedio por fase

### Score Card

- **Total de incidencias** (desglosado por estado)
- **Tasa de reincidencia** (% de equipos con 2+ incidencias)
- **Promedio días de cierre** (desde detección hasta cierre)
- **Top técnicos** (ranking por menor incidencias)
- **Componentes problemáticos** (más frecuentes)
- **Atribuibilidad** (% errores técnicos vs. externos)
- **Efectividad de notificaciones** (tasa de éxito de envíos)

### RHITSO

- Órdenes en proceso RHITSO por estado
- Tiempo promedio de reparación externa
- Incidencias durante proceso externo
- SLA cumplidos vs. vencidos

---

## 🔧 Scripts de Utilidades

Ver documentación completa en [`docs/README.md`](./docs/README.md)

### Poblado de Datos (`scripts/poblado/`)

- `poblar_sistema.py` - Sucursales, empleados, usuarios
- `poblar_servicios.py` - Catálogo de servicios
- `poblar_estados_rhitso.py` - Estados del proceso RHITSO
- `poblar_productos.py` - Productos de inventario
- `poblar_scorecard.py` - Datos de ejemplo Score Card

### Verificación (`scripts/verificacion/`)

- `verificar_datos.py` - Validación de integridad de datos
- `verificar_fase*.py` - Verificación por fase de implementación
- `actualizar_seguimientos_existentes.py` - Actualización masiva

### Testing (`scripts/testing/`)

- `test_email_config.py` - Prueba de configuración de email
- `test_pdf_rhitso.py` - Prueba de generación de PDFs
- `test_rhitso_config.py` - Validación de configuración RHITSO
- `test_compresion_imagenes.py` - Prueba de compresión de imágenes

---

## 📚 Documentación Completa

El proyecto incluye **42 documentos técnicos** organizados en [`docs/`](./docs/):

### Por Módulo

- **RHITSO**: 8 documentos (plan, fases, colores, PDFs)
- **Score Card**: 8 documentos (fases, atribuibilidad, notificaciones)
- **Venta Mostrador**: 11 documentos (changelogs, refactors, referencias)
- **Servicio Técnico**: 5 documentos (vistas, piezas, estados)

### Guías

- **Setup**: Configuración inicial, comandos Git
- **Referencias**: Colores, mejoras, planes de reportes

Ver índice completo en [`docs/README.md`](./docs/README.md)

---

## 🚦 Próximas Mejoras

### Corto Plazo

- [ ] Módulo de reportes PDF personalizados
- [ ] Firma digital del cliente en entregas
- [ ] App móvil para técnicos (seguimiento en campo)
- [ ] Integración con WhatsApp Business API
- [ ] Dashboard ejecutivo con métricas financieras

### Mediano Plazo

- [ ] Sistema de garantías automatizado
- [ ] Portal de clientes (consulta de órdenes)
- [ ] Integración con sistema de facturación
- [ ] IA para predicción de fallas recurrentes
- [ ] Sistema de feedback del cliente

### Largo Plazo

- [ ] Multi-tenant para franquicias
- [ ] Marketplace de refacciones
- [ ] Sistema de capacitación de técnicos
- [ ] Integración con ERPs empresariales

---

## Estructura del Proyecto

```
mi_proyecto_django/
├── config/                 # Configuración del proyecto Django
│   ├── settings.py
│   ├── urls.py
│   ├── constants.py       # Constantes del sistema
│   └── wsgi.py
├── inventario/            # App de gestión de inventario
├── servicio_tecnico/      # App de servicio técnico
├── scorecard/             # App de control de calidad
├── venta_mostrador/       # App de ventas mostrador
├── templates/             # Templates base
├── static/                # Archivos estáticos
├── media/                 # Archivos subidos por usuarios
├── docs/                  # 📚 Documentación completa del proyecto
│   ├── README.md          # Índice de documentación
│   ├── implementaciones/  # Docs por módulo (RHITSO, Scorecard, etc.)
│   └── guias/             # Guías de setup y referencias
├── scripts/               # 🔧 Scripts de utilidades
│   ├── poblado/           # Scripts para datos iniciales
│   ├── verificacion/      # Scripts de validación
│   └── testing/           # Scripts de pruebas
├── manage.py
└── requirements.txt
```

> **📖 Documentación Completa**: Ver [`docs/README.md`](./docs/README.md) para acceso a toda la documentación técnica, guías de implementación y scripts de utilidades.

---

## 💡 Tecnologías Utilizadas

### Backend

- **Django 5.2.5** - Framework web Python
- **Python 3.10+** - Lenguaje de programación
- **SQLite3** - Base de datos (desarrollo)
- **Pillow** - Procesamiento de imágenes
- **openpyxl** - Exportación Excel avanzada
- **ReportLab** - Generación de PDFs
- **Plotly** - Visualizaciones servidor-side
- **Pandas** - Procesamiento y análisis de datos
- **Scikit-learn** - Machine Learning
- **Matplotlib & Seaborn** - Análisis estadístico

### Frontend

- **TypeScript 5.9.3** - Type-safe development
- **Plotly.js** - Dashboards interactivos tipo Power BI
- **Bootstrap 5.3.2** - Framework CSS
- **Bootstrap Icons** - Iconografía
- **Chart.js 4.4.0** - Gráficas básicas
- **JavaScript ES2018+** - Interactividad moderna
- **Glassmorphism & 3D Effects** - UI de última generación

### DevOps & Herramientas

- **Git** - Control de versiones
- **PowerShell** - Automatización Windows
- **VS Code** - Editor recomendado
- **Django Debug Toolbar** - Debugging (dev)

---

## 👥 Contribuir

1. Fork del proyecto
2. Crear rama para nueva funcionalidad (`git checkout -b feature/NuevaCaracteristica`)
3. Commit de cambios (`git commit -m 'Agregar nueva característica'`)
4. Push a la rama (`git push origin feature/NuevaCaracteristica`)
5. Crear Pull Request

**Código de Conducta:**

- Seguir convenciones de Django
- Documentar código complejo
- Incluir tests para nuevas features
- Mantener compatibilidad con versiones anteriores

---

## 📄 Licencia

Este proyecto es software propietario desarrollado para uso interno empresarial.

---

## 📞 Soporte y Contacto

**Desarrollador**: Sistema Integrado de Gestión Técnica  
**Repositorio**: [github.com/maggots555/inventario-calidad-django](https://github.com/maggots555/inventario-calidad-django)

**Documentación Técnica**: Ver [`docs/README.md`](./docs/README.md) para documentación detallada de cada módulo.

---

## 🏆 Reconocimientos

Este sistema integra las mejores prácticas de:

- **Django Documentation** - Arquitectura MVC
- **Bootstrap** - Diseño responsivo
- **Plotly** - Visualizaciones interactivas profesionales
- **TypeScript** - Type-safe frontend development
- **Scikit-learn** - Machine Learning best practices
- **Chart.js** - Visualización de datos
- **Metodologías Lean** - Optimización de procesos

---

## 📈 Estado del Proyecto

**Versión Actual**: 3.0 (Noviembre 2025)  
**Estado**: ✅ Producción (4 módulos integrados + ML/Analytics)  
**Última Actualización**: Noviembre 28, 2025

### Módulos Completados

- ✅ **Inventario** (v1.0) - Sistema base
- ✅ **Servicio Técnico** (v2.0) - Con RHITSO y venta mostrador
- ✅ **Score Card** (v2.0) - Con reportes avanzados y notificaciones
- ✅ **RHITSO** (v1.1) - Seguimiento externo completo

### Estadísticas del Sistema

- **21 estados** de orden de servicio
- **12 estados** RHITSO
- **4 niveles** de severidad de incidencias
- **7 tabs** de reportes avanzados
- **50+ visualizaciones** Plotly interactivas tipo Power BI
- **8 módulos** TypeScript (160KB)
- **4 sistemas** ML/IA especializados
- **42 documentos** técnicos
- **23 scripts** de utilidades
- **10,000+ líneas** de código Python
- **5,000+ líneas** de TypeScript
- **2,000+ líneas** de templates Django

---

## 🎓 Para Desarrolladores Nuevos

Si eres nuevo en el proyecto, sigue este orden:

1. **Leer**: [`docs/guias/setup/SETUP_NUEVA_MAQUINA.md`](./docs/guias/setup/SETUP_NUEVA_MAQUINA.md)
2. **Configurar**: Entorno local siguiendo la instalación arriba
3. **Explorar**: Navega por cada módulo en orden:
   - Inventario (más simple)
   - Servicio Técnico (core del sistema)
   - Score Card (análisis de calidad)
   - RHITSO (seguimiento externo)
4. **Documentar**: Lee la documentación de cada módulo en [`docs/implementaciones/`](./docs/implementaciones/)
5. **Practicar**: Usa los scripts de poblado para crear datos de prueba
6. **Verificar**: Ejecuta los scripts de testing para validar tu setup

---

**🎯 Objetivo del Sistema**: Digitalizar y optimizar el flujo completo de un centro de servicio técnico, desde el ingreso del equipo hasta la entrega, con control de calidad integrado y análisis de desempeño continuo.

**Made with ❤️ using Django**
