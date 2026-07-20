# AGENTS.md - Development Guide for AI Coding Agents

> **Project**: Sistema Integrado de Gestión Técnica y Control de Calidad (SIGMA)  
> **Framework**: Django 5.2.5 | Python 3.12+ | TypeScript 5.9.3  
> **Purpose**: Enterprise technical service management with ML analytics  
> **Deployment**: PWA (Progressive Web App) — instalable en móviles como app nativa

---

## 🌍 IDIOMA DE COMUNICACIÓN

**CRITICAL**: **TODA comunicación con el usuario DEBE ser en ESPAÑOL (es-MX)**

- ✅ SIEMPRE responder en español
- ✅ SIEMPRE explicar en español
- ✅ SIEMPRE usar terminología en español para conceptos de negocio
- ❌ NUNCA responder en inglés (excepto en código/comentarios técnicos)
- ❌ NUNCA asumir que el usuario prefiere inglés

**Razón**: El usuario es hispanohablante y el proyecto usa español para toda la lógica de dominio, nombres de variables, comentarios de negocio y documentación.


### 📝 Reglas Estrictas de Documentación Inline y Docstrings

- **Idioma y Enfoque Obligatorio:** Todos los comentarios inline y docstrings DEBEN ser escritos en **Español (es-MX)**. Deben mantener un tono altamente didáctico y pedagógico, diseñado para que un desarrollador principiante pueda entender el "por qué" de la lógica.
- **Cobertura de Docstrings Estricta:** Toda clase, vista de Django, tarea de Celery, método o componente de TypeScript DEBE iniciar con un bloque de documentación que detalle:
  1. El objetivo principal de la función o componente (el contexto del negocio).
  2. Los argumentos/parámetros de entrada y sus tipos esperados.
  3. Los efectos secundarios (si modifica la base de datos, dispara eventos o encola tareas).
- **Densidad de Comentarios Inline:** No asumas que el código se explica por sí mismo. Toda lógica que involucre:
  - Manipulación de archivos o multimedia (ej. flujos de FFmpeg).
  - Lógica asíncrona o estados de tareas (ej. Celery).
  - Filtros complejos de QuerySets, manipulación de datos o condicionales.
  DEBE llevar comentarios inline detallando el flujo paso a paso cada 3 o 5 líneas de código lógico.
- **Restricción Negativa:** Se PROHÍBE rotundamente entregar funciones o bloques de código de más de 10 líneas de lógica de negocio pura sin al menos dos comentarios inline que expliquen el flujo de los datos.

---

## 1. BUILD/LINT/TEST COMMANDS

### Django Commands
```bash
# Development server
python manage.py runserver

# Database operations
python manage.py makemigrations        # Create migrations
python manage.py migrate               # Apply migrations
python manage.py createsuperuser       # Create admin user
python manage.py shell                 # Django shell

# Static files (production)
python manage.py collectstatic         # Collect static files
```

### TypeScript Commands
```bash
pnpm run build      # Compile TypeScript once
pnpm run watch      # Auto-compile on file changes
tsc                # Direct TypeScript compilation
```

### Testing
Hay **suite formal en `almacen/tests/`** (profit, sync componente, compras sin orden, reacondicionado, totales), **humo en `servicio_tecnico/tests/`** (modularización) y scripts manuales en `scripts/testing/`.

#### Política: tests con cada cambio que aporte comportamiento nuevo

**CRITICAL para agentes:** si el trabajo introduce o cambia comportamiento verificable, **debe incluirse al menos un test** (o ampliar uno existente). No dejar “solo checklist manual” cuando se pueda automatizar de forma razonable.

```
✅ SÍ aplica (hay que escribir/actualizar test):
   - Nueva vista / API / URL
   - Nueva regla de negocio en models/services/utils
   - Cambio en sync Almacén ↔ ST, profit, cotizaciones, Celery que toque BD
   - Extracción/modularización (reexport + resolve como mínimo)
   - Bugfix con causa conocida (test de regresión)

❌ NO hace falta inventar suite pesada cuando:
   - Solo docs (AGENTS.md, comentarios)
   - Solo CSS cosmético sin lógica
   - Rename/refactor puro sin cambiar comportamiento (opcional: smoke de import)
   - El usuario pide explícitamente no testear aún

Nivel mínimo aceptable:
   - Humo: reverse/resolve, reexport, import del módulo, status code 200/302/403
   - Mejor: 1 caso feliz + 1 borde (permiso, validación, sin orden, etc.)
   - No enviar correos/PDF/FFmpeg reales en CI — mockear .delay() / IO
```

**Dónde ponerlos:** `almacen/tests/` o `servicio_tecnico/tests/` (preferir suite formal; no scripts sueltos salvo herramientas manuales en `scripts/testing/`).

```bash
# Suite Django de Almacén (preferir al tocar cotizaciones / sync ST)
python manage.py test almacen
python manage.py test almacen.tests.test_profit_cotizacion
python manage.py test almacen.tests.test_sincronizar_componente_st
python manage.py test almacen.tests.test_generar_compras_sin_orden
python manage.py test almacen.tests.test_costeo_reacondicionado

# Scripts manuales de verificación
python scripts/testing/test_email_config.py
python scripts/testing/test_pdf_rhitso.py
python scripts/testing/test_dashboard_ml.py
python scripts/testing/test_dynamic_storage.py

# Permission testing
./scripts/test_permisos.sh

# Django's built-in tests
python manage.py test                           # All tests
python manage.py test inventario                # App-specific
python manage.py test inventario.tests.MyTest   # Single test

# Suite humo modularización Servicio Técnico (reexports / resolve URLs)
python manage.py test servicio_tecnico.tests
```

### Data Management
```bash
# Seed database
python scripts/poblado/poblar_sistema.py
python scripts/poblado/poblar_scorecard.py

# Verification
python scripts/verificacion/verificar_*.py
```

---

## 2. CODE STYLE GUIDELINES

### Python/Django Conventions

#### Imports
```python
# Standard library
from pathlib import Path
from datetime import datetime

# Django imports
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

# Third-party
from decouple import config
import pandas as pd

# Local app imports
from .models import Producto
from .forms import ProductoForm
```

**Order**: Standard library → Django → Third-party → Local  
**Formatting**: Explicit imports preferred over `import *`

#### Naming Conventions
- **Models**: PascalCase (`OrdenServicio`, `ComponenteScorecard`)
- **Functions/variables**: snake_case (`crear_producto`, `total_price`)
- **Constants**: UPPER_SNAKE_CASE (`MAX_FILE_SIZE`, `ESTADO_CHOICES`)
- **Spanish naming**: Primary language for domain-specific terms
- **English**: For generic programming constructs

#### Django Models
```python
class Producto(models.Model):
    """Always include docstring explaining model purpose"""
    nombre = models.CharField(max_length=200, verbose_name="Nombre del Producto")
    precio = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['-fecha_creacion']
    
    def __str__(self):
        """REQUIRED: String representation for admin and debugging"""
        return self.nombre
    
    def clean(self):
        """Custom validation logic"""
        super().clean()
        if self.precio < 0:
            raise ValidationError("Price cannot be negative")
```

#### Views Pattern
```python
@login_required
def crear_producto(request):
    """Function-based views preferred for clarity"""
    if request.method == 'POST':
        form = ProductoForm(request.POST)
        if form.is_valid():
            producto = form.save()
            messages.success(request, 'Producto creado exitosamente.')
            return redirect('inventario:lista_productos')
    else:
        form = ProductoForm()
    
    return render(request, 'inventario/crear_producto.html', {'form': form})
```

**Key Patterns**:
- Use `get_object_or_404()` for safety
- Always provide user feedback via `messages`
- Named URL patterns for `redirect()` and templates
- Explicit error handling

#### Forms with Bootstrap
```python
class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = ['nombre', 'precio', 'categoria']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ingrese nombre del producto'
            }),
            'precio': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01'
            }),
        }
```

**CRITICAL**: All form widgets must include Bootstrap classes

#### Error Handling
```python
# Explicit try/except with user-friendly messages
try:
    orden = get_object_or_404(OrdenServicio, pk=orden_id)
    orden.estado = 'COMPLETADO'
    orden.save()
    messages.success(request, 'Orden completada correctamente.')
except OrdenServicio.DoesNotExist:
    messages.error(request, 'Orden no encontrada.')
    return redirect('servicio_tecnico:lista_ordenes')
except Exception as e:
    messages.error(request, f'Error al procesar: {str(e)}')
    logger.error(f'Error in complete_order: {e}', exc_info=True)
```

### TypeScript Conventions

#### CRITICAL RULES
- **NEVER write `.js` files directly** - They are auto-generated
- **ALWAYS create `.ts` files** for new JavaScript functionality
- **NEVER use `any` type** - Be explicit with types
- **ALWAYS compile before testing** - Run `pnpm run build`

#### Type Definitions
```typescript
// Define interfaces for all data structures
interface Producto {
    id: number;
    nombre: string;
    precio: number;
    stock: number;
    activo: boolean;
}

interface ApiResponse<T> {
    success: boolean;
    data: T;
    error?: string;
}
```

#### Function Types
```typescript
// Explicit parameter and return types
function calcularTotal(productos: Producto[]): number {
    return productos.reduce((sum, p) => sum + (p.precio * p.stock), 0);
}

// Async functions
async function fetchProductos(): Promise<Producto[]> {
    const response = await fetch('/api/productos/');
    const data: ApiResponse<Producto[]> = await response.json();
    return data.data;
}
```

#### DOM Manipulation
```typescript
// Type-safe DOM queries
const button = document.querySelector<HTMLButtonElement>('#submit-btn');
if (button) {
    button.addEventListener('click', handleSubmit);
}

function handleSubmit(event: Event): void {
    event.preventDefault();
    // Implementation
}
```

### Template Conventions
```html
{% extends 'base.html' %}
{% load static %}

{% block title %}Page Title - {{ block.super }}{% endblock %}

{% block extra_css %}
    <link rel="stylesheet" href="{% static 'css/dashboard.css' %}">
{% endblock %}

{% block content %}
<div class="container mt-4">
    <!-- NEVER include extensive CSS here - use static files -->
    <h1>{{ page_title }}</h1>
    
    <!-- Always use named URLs -->
    <a href="{% url 'inventario:crear_producto' %}" class="btn btn-primary">
        Nuevo Producto
    </a>
</div>
{% endblock %}

{% block extra_js %}
    <script src="{% static 'js/dashboard.js' %}"></script>
{% endblock %}
```

---

## 3. PROJECT STRUCTURE & FILE ORGANIZATION

```
inventario-calidad-django/
├── config/                    # Project configuration (NOT an app)
│   ├── settings.py           # Main settings (Celery Beat, Redis cache, CSRF)
│   ├── urls.py              # Root URL + rutas públicas (/seguimiento/, feedback)
│   ├── storage_utils.py      # Dynamic file storage
│   ├── constants.py          # Global constants (keywords sync piezas, etc.)
│   ├── paises_config.py      # Multi-country config
│   ├── middleware_pais.py    # Country detection middleware
│   ├── db_router.py          # Multi-country DB router
│   ├── context_processors.py
│   └── pwa_views.py          # Service worker & manifest views (staff + seguimiento)
├── inventario/               # App: Product inventory & employees
│   └── middleware.py         # ForcePasswordChangeMiddleware (tras PaisMiddleware)
├── servicio_tecnico/         # App: Service orders (MAIN)
│   ├── models.py            # ~23 models (OrdenServicio, EnlaceSeguimientoCliente, etc.)
│   ├── views.py             # Reexports + detalle_orden (NO volver a monolito ~19k LOC)
│   ├── views_*.py           # Vistas por dominio (ordenes, rhitso, dashboards, etc.)
│   ├── services/            # Helpers de dominio (historial, multimedia, notifs, analytics)
│   ├── decorators.py        # permission_required_with_message, cache_page_dashboard
│   ├── tests/               # Suite humo modularización + smoke por fase
│   ├── plotly_visualizations.py  # ~4600 lines of charts
│   ├── ml_predictor.py      # ML predictions
│   ├── ml_advanced/         # Advanced ML modules
│   ├── ollama_client.py     # Ollama + Gemini AI dispatcher
│   ├── gemini_client.py     # Google Gemini client (módulo propio)
│   ├── sicser_client.py     # Cliente HTTP SICSER (solo lectura + caché Redis)
│   ├── sicser_import.py     # Importación de órdenes SICSER → SIGMA
│   ├── chat_seguimiento_helpers.py  # Lógica del chat IA público
│   ├── concentrado_semanal.py       # Concentrado semanal CIS
│   ├── utils_rhitso_analytics.py    # Análisis candidatos RHITSO
│   ├── tasks.py             # Celery tasks (email, video, push, recordatorios)
│   └── signals.py           # Push (listas blancas ESTADOS_PUSH_*)
├── scorecard/                # App: Quality control system
├── almacen/                  # App: Central warehouse + cotizador
│   ├── utils/               # profit, PDF cliente, reacondicionado, resolver_componente
│   ├── tasks.py             # notificar front/compras, enviar cotización cliente
│   └── tests/               # Suite formal (profit, sync, compras, reacondicionado)
├── notificaciones/           # App: Notifications + Web Push
│   ├── models.py            # Notificacion + PushSubscription + PushSubscriptionCliente
│   ├── push_service.py      # pywebpush VAPID (staff y cliente)
│   └── views.py             # Push endpoints + suscripción
├── static/
│   ├── ts/                  # TypeScript source (EDIT THESE — ~55 módulos)
│   │   ├── base.ts
│   │   ├── service_worker.ts              # Service worker (compilado aparte)
│   │   ├── pwa_install.ts                 # PWA install prompt (STAFF)
│   │   ├── pwa_install_seguimiento.ts     # PWA install prompt (CLIENTE)
│   │   ├── push_notifications.ts          # Web Push UI (STAFF)
│   │   ├── push_notifications_cliente.ts  # Web Push UI (CLIENTE)
│   │   ├── seguimiento_chat.ts            # Chat IA en portal público
│   │   ├── eventos_seguimiento.ts         # Analytics / embudo de adopción
│   │   ├── galeria_seguimiento.ts         # Galería en portal cliente
│   │   ├── consultar_sicser.ts            # UI consulta SICSER
│   │   ├── cotizacion_cliente_modal.ts    # Cotizador profit + PDF
│   │   ├── cotizacion_reacondicionado_modal.ts
│   │   ├── camara_integrada.ts / camara_video.ts
│   │   ├── compartir_video.ts             # Envío evidencia video + IA
│   │   ├── video_resumen.ts / upload_video.ts
│   │   ├── voz_diagnostico.ts / ollama_sic.ts
│   │   └── [otros módulos...]
│   ├── js/                  # Compiled JavaScript (AUTO-GENERATED)
│   ├── css/                 # Organized CSS files
│   │   ├── base.css        # Global styles + dark mode variables
│   │   ├── components.css  # UI components
│   │   └── forms.css       # Form styling
│   ├── audio/               # Audio assets (bg_music.mp3 para video resumen)
│   └── images/
├── templates/                # Global templates
│   ├── base.html
│   └── offline.html          # PWA offline page
├── media/                    # User uploads (organized by country)
│   ├── mexico/
│   └── argentina/
├── scripts/
│   ├── testing/             # Manual test scripts
│   ├── poblado/             # Database seeding
│   └── verificacion/        # Data validation
├── logs/                     # Application logs
├── ml_models/                # Trained ML models (.pkl)
├── manage.py
├── requirements.txt
├── package.json
├── tsconfig.json
└── tsconfig.sw.json          # TypeScript config separado para service worker
```

**Orden de middleware (no reordenar):** Auth → `PaisMiddleware` → `ForcePasswordChangeMiddleware`.

---

## 4. CRITICAL PROJECT RULES

### From `.github/copilot-instructions.md`

#### User Experience Level
**IMPORTANT**: User is a Python beginner. When making changes:
- **SIEMPRE explicar en ESPAÑOL** - Toda comunicación debe ser en español
- Explain EVERY modification in detail (en español)
- Use simple language, avoid jargon (explicar en español)
- Include "EXPLICACIÓN PARA PRINCIPIANTES" comments in code
- Show before/after comparisons (con explicaciones en español)
- Point out Django patterns and best practices (explicados en español)

#### Static Files Management
**NEVER put CSS/JS directly in templates**:
```html
<!-- ❌ WRONG - Hard to maintain -->
<style>
    .my-class { color: red; }
</style>

<!-- ✅ CORRECT - External file -->
{% load static %}
<link rel="stylesheet" href="{% static 'css/components.css' %}">
```

**Benefits**: Caching, reusability, team collaboration, debugging

#### TypeScript Mandatory
**ALL client-side code must be TypeScript**:
- ❌ NEVER edit `.js` files in `static/js/`
- ✅ ALWAYS create `.ts` files in `static/ts/`
- ❌ NEVER skip type annotations
- ✅ ALWAYS compile before committing
- ❌ NEVER ignore TypeScript errors

#### Database Configuration
Dual-database setup via environment variables:
- **Development**: SQLite3 (`DB_ENGINE=django.db.backends.sqlite3`)
- **Production**: PostgreSQL with connection pooling

Settings automatically optimize based on `DB_ENGINE` value.

#### Security
- Use `python-decouple` for all sensitive config
- Never commit `.env` file (use `.env.example`)
- Django-Axes enabled for brute-force protection
- CSRF protection always active (`CSRF_COOKIE_NAME = 'sigma_csrftoken'` en producción)
- HSTS enabled in production (`DEBUG=False`)

#### Modularidad de vistas — no re-inflar monolitos (Julio 2026)

**Contexto:** `servicio_tecnico/views.py` llegó a ~19 000 líneas. Se modularizó en fases (hermanos `views_*.py` + `services/` + reexports). Hoy `views.py` es principalmente **reexports** y aún contiene `detalle_orden` (pendiente opcional de extraer). El objetivo ya se cumplió: archivos navegables y escalables.

**Regla para agentes — aplicar en TODAS las apps (ST, Almacén, etc.):**

```
❌ NUNCA agregar features nuevas grandes dentro de un views.py ya denso
❌ NUNCA “aprovechar” el monolito residual para meter dashboards/AJAX/APIs nuevas
❌ NUNCA editar urls.py para apuntar al módulo nuevo si views.py ya reexporta
   (salvo que el usuario pida cambiar el cableado)
❌ NUNCA mover lógica de negocio a templates; helpers → services/ o utils/

✅ SIEMPRE crear un módulo hermano por dominio cuando la feature sea nueva o crezca:
   views_mi_feature.py  |  services/mi_helper.py  |  tests/test_...
✅ SIEMPRE reexportar desde views.py si urls.py usa views.foo (compatibilidad)
✅ SIEMPRE preferir archivos < ~800–1000 LOC de lógica; si un módulo se dispara,
   partir por dominio ANTES de seguir sumando
✅ SIEMPRE al tocar imports relativos dentro de services/: usar
   from servicio_tecnico.models import ...  (NO from .models — eso busca services/models)
✅ SIEMPRE añadir test de humo (resolve/reexport) si se extrae o crea un views_*.py
✅ SIEMPRE, si hay comportamiento nuevo o cambiado, incluir o ampliar un test
   (ver Sección 1 → Política de tests). No entregar feature “a ciegas” solo con checklist.
```

**Mapa actual de `servicio_tecnico` (orientativo):**

| Módulo | Dominio |
|--------|---------|
| `views_ordenes.py` | inicio, crear, listas, cerrar |
| `views_rhitso.py` / `views_envios_cliente.py` | RHITSO por orden + envíos al cliente |
| `views_dashboard_*.py` | Dashboards Plotly/Excel |
| `views_piezas_cotizadas.py`, `views_seguimiento_piezas_ajax.py`, `views_venta_mostrador_ajax.py` | AJAX piezas / VM |
| `views_multimedia.py`, `views_seguimiento_cliente.py`, `views_encuestas.py`, … | Multimedia, portal, APIs dash |
| `services/` | historial, multimedia, notificaciones_piezas, ventas_mostrador_analytics |
| `views.py` | reexports + `detalle_orden` (no volver a concentrar todo aquí) |

**Pendiente consciente (no urgente):** mover `detalle_orden` a `views_detalle_orden.py` sin partir handlers; luego (otro PR) handlers por `form_type`. No bloquear features nuevas por eso: las features nuevas van a módulos propios.

**Misma filosofía fuera de vistas:** TypeScript en `static/ts/` ya es modular — no crear un único `.ts` gigante; CSS por página/componente, no CSS inline masivo en templates enormes (`detalle_orden.html` es otro candidato a no hinchar más).

---

## 5. SPECIAL FEATURES & INTEGRATIONS

### Machine Learning
- **Location**: `servicio_tecnico/ml_advanced/`
- **Models**: Price optimizer, rejection classifier, action recommender
- **Tech**: scikit-learn, pandas, joblib
- **Storage**: Trained models in `ml_models/` directory

### Analytics Dashboard
- **File**: `servicio_tecnico/plotly_visualizations.py` (~4607 lines)
- **Charts**: 50+ interactive Plotly visualizations
- **Types**: Line, bar, scatter, heatmap, sunburst, treemap
- **Data**: Pandas DataFrames from Django QuerySets
- **Extras**: Concentrado semanal CIS (`concentrado_semanal.py` + `concentrado_semanal.ts`); análisis candidatos RHITSO (`utils_rhitso_analytics.py`); dashboard embudo seguimiento (`dashboard_seguimiento_enlaces.ts`)

### RHITSO Integration
External laboratory management system:
- Email workflows to multiple contacts
- PDF generation with ReportLab
- Status synchronization
- Color-coded states system
- Analytics de candidatos aptos/no aptos (`utils_rhitso_analytics.py`)

### Dynamic Storage
Intelligent file storage with disk failover:
- Primary/alternate disk support (`.env` configured)
- Automatic space monitoring
- Images organized by order ID
- Custom Django storage backend

### Video Gallery, Cámaras & Video Resumen (FFmpeg)
Sistema de video de evidencia implementado en `detalle_orden`:
- **Galería de videos**: Subida y reproducción de videos de evidencia por orden (`upload_video.ts`)
- **Cámaras in-browser**: `camara_integrada.ts` (fotos) y `camara_video.ts` (MediaRecorder, ~90 MB / 720p, selector de lentes)
- **Compartir evidencia al cliente**: `compartir_video.ts` + task `enviar_evidencia_video_task` (mensaje personalizado + análisis IA opcional)
- **Rewind de egreso**: task `enviar_rewind_egreso_email_task` al finalizar
- **Compresión automática**: FFmpeg vía Celery task al subir video
- **Video Resumen**: Genera un video resumen de la galería de imágenes (`video_resumen.ts`):
  - Efecto Ken Burns en cada imagen
  - Transiciones xfade entre imágenes
  - Música ambient de fondo (`static/audio/bg_music.mp3`)
  - Descarga comprimida vía Celery task
  - Envío automático al cliente al finalizar la orden
  - Disponible tanto en órdenes de Diagnóstico como en Venta Mostrador
- **Lógica en backend**: `servicio_tecnico/tasks.py` (tarea Celery para generar/comprimir/enviar)

### Dictado por Voz — Diagnóstico SIC
Botón de micrófono junto al campo de texto de Diagnóstico en `detalle_orden`:
- **Módulo**: `static/ts/voz_diagnostico.ts`
- **Arquitectura 3 capas**: Web Speech API → Ollama Whisper → Google Gemini
- Capa 1 (Web Speech API): `continuous=true`, instancia única, sin reinicio
- Deduplicación de segmentos finales para evitar repeticiones
- Inserción de texto con detección de solapamiento

### Pulir Diagnóstico SIC con IA
Modal “Mejorar Diag. con IA” — **distinto** de `voz_diagnostico.ts`:
- **Módulo**: `static/ts/ollama_sic.ts` + API `pulir_diagnostico_sic_ia`
- Mejora redacción sin cambiar el contenido técnico del diagnóstico

### Inspector Visual IA — Imágenes de Ingreso
Al enviar imágenes de ingreso al cliente, un análisis IA opcional evalúa la condición estética:
- Selector de modelo en el modal (Ollama / Gemini), ruteo sin fallback cruzado
- Resultado incluido en el correo al cliente y guardado en historial
- Diseño fail-safe: si la IA falla, el correo se envía sin la sección de análisis
- Lógica en `servicio_tecnico/ollama_client.py` y `servicio_tecnico/gemini_client.py`

### Analizador de Sentimientos de Encuestas con IA
- Análisis de sentimientos del texto libre de encuestas de satisfacción
- Generador de PDF ejecutivo con resultados del análisis
- Selector de modelo (múltiples opciones Gemini / Ollama)
- Dashboard de encuestas extendido con esta funcionalidad

### Cita Diaria (Home)
- Cita generada por IA en el dashboard home (`inventario/views.py`)
- Cascada de fallback Gemini → Ollama; botón regenerar para superusuarios

### Integración SICSER (Fase 1 — solo lectura)
Consulta e importación de órdenes desde el sistema externo SICSER (OOW / garantías):
- **Cliente HTTP**: `servicio_tecnico/sicser_client.py` (caché Redis, TTL `SICSER_CACHE_TTL`)
- **Importación**: `servicio_tecnico/sicser_import.py` → crea órdenes en SIGMA
- **UI**: `static/ts/consultar_sicser.ts` + URLs `sicser/consultar/` e `importar/`
- **Campos**: `folio_sicser` y relacionados en `DetalleEquipo`
- **Env**: `SICSER_BASE_URL`, `SICSER_TOKEN_OOW`, `SICSER_TOKEN_GARANTIAS`, `SICSER_CACHE_TTL`

**Reglas para agentes:**
- ❌ NUNCA inventar endpoints de escritura hacia SICSER (Fase 1 es solo lectura + import a SIGMA)
- ✅ Usar el cliente existente; no hardcodear URLs/tokens (van en `.env`)

### Portal de Seguimiento del Cliente (ecosistema dual)
Página pública **sin login** para que el cliente vea el estado de su orden (OOW):
- **URL**: `/seguimiento/<token>/` (definida en `config/urls.py`)
- **Modelo**: `EnlaceSeguimientoCliente` — caduca tras entrega
- **Chat IA**: `seguimiento_chat.ts` + `chat_seguimiento_helpers.py` + vars `CHAT_SEGUIMIENTO_*`
- **Galería / PDF diagnóstico**: visibles en el enlace; push al cliente al haber novedades
- **Analytics / embudo**: modelo `EventoSeguimientoCliente` + `eventos_seguimiento.ts` + dashboard `dashboard_seguimiento_enlaces.ts`
- **Banners**: `BannerPromocional` + `banner_carousel.ts`

**Dos PWAs / dos canales de Push — NO mezclar:**

| Canal | Manifest / Install | Push TS | Modelo suscripción |
|-------|-------------------|---------|-------------------|
| **Staff** (interno) | `manifest.json` + `pwa_install.ts` | `push_notifications.ts` | `PushSubscription` (FK a `User`) |
| **Cliente** (público) | `manifest_seguimiento` + `pwa_install_seguimiento.ts` | `push_notifications_cliente.ts` | `PushSubscriptionCliente` (FK a `EnlaceSeguimientoCliente`) |

**Reglas para agentes:**
- ❌ NUNCA reutilizar scripts/modelos de staff en el portal cliente (ni al revés)
- ❌ NUNCA asumir que todo cambio de estado notifica: solo estados en `ESTADOS_PUSH_TECNICO` / `ESTADOS_PUSH_CLIENTE` (`servicio_tecnico/signals.py`)
- ✅ Al editar seguimiento, preservar hooks de `eventos_seguimiento.ts` (embudo de adopción)

### Sincronización Almacén ↔ Servicio Técnico (Cotizaciones)
Sistema bidireccional de sincronización entre cotizaciones de Almacén y Servicio Técnico:

**Flujo Almacén → ST (principal):**
- Al crear `SolicitudCotizacion` con `orden_servicio` → crea automáticamente `Cotizacion` en ST
- Al agregar `LineaCotizacion` → crea/actualiza `PiezaCotizada` en ST
- Al aprobar/rechazar en Almacén → refleja en `PiezaCotizada.aceptada_por_cliente`
- Cuando todas las piezas tienen respuesta → actualiza `Cotizacion.usuario_acepto`
- **`precio_unitario_cliente`**: se sincroniza a ST; los totales de cotización en ST priorizan este precio (no solo el costo interno)

**Cotizador al cliente (profit + PDF + correo):**
- Modal `cotizacion_cliente_modal.ts` con calculadora de profit
- PDF ReportLab: `almacen/utils/pdf_cotizacion_cliente.py`
- Task Celery: `almacen/tasks.enviar_cotizacion_cliente_task`
- Márgenes/costos **solo desde `.env`**: `PROFIT_*`, `COSTOS_FIJOS_*`, `DIAGNOSTICO_*` — ❌ no hardcodear

**Cotización de equipos reacondicionados (flujo paralelo):**
- Costeo: `almacen/utils/costeo_reacondicionado.py`
- PDF: `almacen/utils/pdf_cotizacion_reacondicionado.py`
- Modal TS: `cotizacion_reacondicionado_modal.ts`
- Flags en líneas (`es_linea_reacondicionado`, financiamiento / opción de pago)
- ❌ No reutilizar a ciegas la lógica de profit de reparación

**Servicios Adicionales (Venta Mostrador en cotizaciones):**
- Modelo `LineaServicioAdicional` en Almacén para cotizar servicios (limpieza, reinstalación SO, paquetes)
- Campo `es_necesaria` controla qué servicios pasan a Venta Mostrador
- Al aprobar y generar compras → crea/actualiza `VentaMostrador` en ST
- Mapeo automático: tipo_servicio → campos booleanos de VentaMostrador

**Vinculación / creación de orden:**
- `SolicitudCotizacion` puede crearse sin orden (modo `sin_orden_activa`)
- Vista de búsqueda para vincular cuando el equipo ingresa formalmente
- Alternativa: **crear orden FL desde cotización** (`crear_orden_fl_desde_cotizacion`)
- Sincroniza datos del cliente y service tag

**Catálogo piezas Almacén → `ComponenteEquipo`:**
- `almacen/utils/resolver_componente.py` + keywords en `config/constants.py`
- La sync ST no es solo “copiar nombre”: hay mapeo semántico

**Archivos clave:**
- `almacen/models.py`: `SolicitudCotizacion`, `LineaCotizacion`, `LineaServicioAdicional`
- `almacen/views.py`: `vincular_orden_solicitud`, `generar_compras_solicitud`, `crear_orden_fl_desde_cotizacion`
- `almacen/utils/`: profit, PDF, reacondicionado, `resolver_componente`
- `servicio_tecnico/templates/.../detalle_orden.html`: Indicador de piezas de Almacén

**Reglas para agentes:**
- Las piezas con `pieza.linea_cotizacion_almacen` NO deben editarse/eliminarse desde ST
- El campo `costo_mano_obra` de `Cotizacion` se crea en $0, el técnico lo edita después
- La sincronización es automática en `save()`, no requiere intervención manual
- ❌ `generar_compras_solicitud` exige `orden_servicio` vinculada — no generar compras en modo `sin_orden_activa`
- ✅ Al tocar cotizaciones/sync, correr `python manage.py test almacen`

### PWA (Progressive Web App) — Staff
The app is installable on Android and iOS as a native-like app:
- **Manifest**: `static/manifest.json` — name, icons, theme color, `display: standalone`
- **iOS support**: `apple-mobile-web-app-capable` + `apple-mobile-web-app-status-bar-style` in `templates/base.html`
- **Viewport**: `viewport-fit=cover` for notch/Dynamic Island support on iPhones
- **Theme color**: `#1f6391` (matches brand)
- **Service Worker**: `static/ts/service_worker.ts` → compilado con `tsconfig.sw.json` separado. Registrado en `base.html`. Incluye página `templates/offline.html` para modo sin conexión.
- **Prompt de instalación personalizado**: `static/ts/pwa_install.ts` — reemplaza el prompt nativo del navegador con UI de marca
- **Web Push Notifications (staff)**: Sistema completo con VAPID keys y `pywebpush`. Modelo `PushSubscription` en `notificaciones/`. Signal en `HistorialOrden` dispara push al técnico asignado **solo si el estado está en `ESTADOS_PUSH_TECNICO`**. Push de ingreso/egreso para dispatchers. Toggle en "Mi Perfil".
- **Recordatorio imágenes**: aviso inmediato al pasar a `finalizado` (técnico según cotización; inspectores si falta egreso) + Celery Beat diario (8:00) para ingreso sin fotos (ventana 2–7 días) y pendientes en `finalizado` con ≤1 semana (`RecordatorioImagenOrden`)

**Ver también:** subsección *Portal de Seguimiento del Cliente* (PWA/push del cliente son un canal separado).

**PWA Rules for AI agents**:
- NEVER remove the `<link rel="manifest">` tag from `base.html`
- NEVER remove or alter the `apple-mobile-web-app-*` meta tags
- NEVER set `maximum-scale` > 1.0 or remove `viewport-fit=cover`
- NEVER modify the service worker registration script in `base.html`
- NEVER mezclar `pwa_install.ts` / `push_notifications.ts` con los módulos `*_seguimiento` / `*_cliente`
- All UI must be **mobile-first** — test layouts at 375px width minimum
- Touch targets must be at least **44x44px** (iOS HIG standard)
- Avoid hover-only interactions — use tap/click equivalents

### 🌙 Dark Mode (Modo Oscuro)

El proyecto tiene modo oscuro completamente implementado. **TODO código nuevo DEBE ser compatible.**

#### Cómo funciona la implementación

| Capa | Archivo | Responsabilidad |
|------|---------|----------------|
| Atributo HTML | `templates/base.html` → `<html data-bs-theme="light">` | Bootstrap 5.3 lee este atributo para aplicar su tema automáticamente |
| Anti-flash script | `templates/base.html` → inline `<script>` en `<head>` | Lee `localStorage('theme')` o `prefers-color-scheme` del SO y aplica `data-bs-theme` ANTES del render para evitar parpadeo blanco |
| Toggle button | `templates/base.html` → `#darkModeToggle` (`.dark-mode-toggle`) | Botón en la navbar con iconos luna/sol (Bootstrap Icons) |
| Lógica TypeScript | `static/ts/dark_mode.ts` → compilado en `static/js/dark_mode.js` | Click → cambia `data-bs-theme` en `<html>` → guarda en `localStorage` → actualiza `meta[name="theme-color"]` |
| Variables CSS claras | `static/css/base.css` → bloque `:root {}` | Todos los colores del proyecto como variables CSS |
| Variables CSS oscuras | `static/css/base.css` → bloque `[data-bs-theme="dark"] {}` | Sobreescribe las variables de `:root` para modo oscuro |
| Overrides de componentes | `static/css/base.css` → reglas `[data-bs-theme="dark"] .clase {}` | Overrides para elementos con colores hardcodeados (gradientes, etc.) |

#### Paleta de colores — Modo Oscuro

Estos son los valores exactos usados en el proyecto. Usar solo estos para consistencia:

```css
/* Fondos principales */
--body-bg:          #0f172a   /* Fondo del <body> */
--card-bg:          #1e293b   /* Cards, panels, dropdowns */
--sidebar-bg:       #0f172a → #1e293b (gradient)
--hover-bg:         #334155   /* Hover en filas, items */
--border-color:     #334155   /* Bordes de cards, tablas */
--secondary-bg:     #475569   /* Hover secundario */

/* Texto */
--text-primary:     #e2e8f0   /* Texto principal */
--text-secondary:   #cbd5e1   /* Texto secundario */

/* Colores de estado (modo oscuro) */
--primary:          #60a5fa
--success:          #34d399
--danger:           #f87171
--warning:          #fbbf24
--info:             #22d3ee

/* Meta theme-color del navegador */
/* Claro: #1f6391  |  Oscuro: #0f172a */
```

#### Patrón CSS obligatorio para código nuevo

**Regla de oro**: Si un componente usa colores hardcodeados, SIEMPRE agregar un bloque `[data-bs-theme="dark"]`.

```css
/* ✅ CORRECTO: Usar variables CSS — se adaptan automáticamente */
.mi-componente {
    background-color: var(--gray-100);
    color: var(--gray-900);
    border: 1px solid var(--gray-200);
}

/* ✅ CORRECTO: Override para colores hardcodeados (sin gradientes) */
.mi-componente-especial {
    background-color: #1f6391;
    color: #ffffff;
}
[data-bs-theme="dark"] .mi-componente-especial {
    background-color: #1e293b;
    color: #e2e8f0;
}

/* ❌ INCORRECTO: Color hardcodeado sin override para oscuro */
.mi-componente {
    background-color: #ffffff;  /* Se verá igual en modo oscuro — MAL */
    color: #333333;
}

/* ❌ INCORRECTO: Gradiente — prohibido, se ve como "IA Slop" */
.mi-componente {
    background: linear-gradient(135deg, #1f6391, #2980b9);
}
```

#### Variables CSS disponibles en `:root` (modo claro → uso obligatorio)

```css
/* Usar estas variables en vez de hex directos */
var(--primary-color)     /* Azul principal */
var(--success-color)     /* Verde */
var(--danger-color)      /* Rojo */
var(--warning-color)     /* Amarillo */
var(--info-color)        /* Cyan */
var(--gray-50) ... var(--gray-900)  /* Escala de grises */
var(--white)             /* Blanco en claro, #1a1a2e en oscuro */
var(--shadow-sm/md/lg/xl)  /* Sombras adaptadas al tema */
```

#### Reglas críticas para agentes — NUNCA violar

```
❌ NUNCA usar colores hardcodeados sin override [data-bs-theme="dark"]
❌ NUNCA modificar el inline <script> anti-flash en base.html
❌ NUNCA agregar data-bs-theme a elementos que no sean <html>
❌ NUNCA usar background: white o color: black directamente
❌ NUNCA olvidar sección [data-bs-theme="dark"] en archivos CSS nuevos
❌ NUNCA usar gradientes (linear-gradient, radial-gradient, glassmorphism) — se ven como "IA Slop"

✅ SIEMPRE usar var(--nombre-variable) para colores
✅ SIEMPRE agregar overrides oscuros para colores hardcodeados
✅ SIEMPRE probar visualmente en ambos modos antes de considerar listo
✅ SIEMPRE seguir la paleta de modo oscuro documentada arriba
✅ En TypeScript: leer tema con document.documentElement.getAttribute('data-bs-theme')
```

#### Estructura en archivos CSS específicos de página

Cada archivo CSS de página debe tener dos secciones claramente separadas:

```css
/* ============================================================
   ESTILOS BASE (modo claro — default)
   ============================================================ */
.mi-componente {
    background-color: var(--gray-50);
    color: var(--gray-900);
}
.mi-componente-especial {
    background-color: #1f6391;
    color: #ffffff;
}

/* ============================================================
   MODO OSCURO — Overrides para [data-bs-theme="dark"]
   ============================================================ */
[data-bs-theme="dark"] .mi-componente-especial {
    background-color: #1e293b;
    color: #e2e8f0;
}
```

#### Archivos clave del modo oscuro

| Archivo | Rol |
|---------|-----|
| `templates/base.html` línea 2 | `data-bs-theme="light"` — valor inicial |
| `templates/base.html` líneas ~60-68 | Script anti-flash (no tocar) |
| `templates/base.html` línea ~492 | Botón `#darkModeToggle` |
| `templates/base.html` línea ~981 | `<script src="dark_mode.js">` |
| `static/ts/dark_mode.ts` | Lógica del toggle (TypeScript fuente) |
| `static/js/dark_mode.js` | Compilado — no editar |
| `static/css/base.css` líneas ~144-400+ | Todas las variables y overrides del modo oscuro |

---

## 6. ENVIRONMENT VARIABLES

**Required in `.env`** (see `.env.example`):
```bash
# Django Core
SECRET_KEY='your-secret-key-here'
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (SQLite for dev)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3

# Email (Gmail SMTP)
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# File Storage
PRIMARY_MEDIA_ROOT=/path/to/primary
ALTERNATE_MEDIA_ROOT=/path/to/alternate
MIN_FREE_SPACE_GB=10

# Redis — Celery usa /0 y /1; el cache de Django usa /2
REDIS_CACHE_URL=redis://127.0.0.1:6379/2

# Chat IA del portal de seguimiento (cliente)
CHAT_SEGUIMIENTO_MODEL=gemma4:e2b
CHAT_SEGUIMIENTO_MAX_TOKENS=1200
CHAT_SEGUIMIENTO_NUM_CTX=8192

# Cotizador Almacén — márgenes y costos (NO hardcodear en código)
PROFIT_MOSTRADOR=
PROFIT_ESTANDAR=
PROFIT_EXPRESS=
PROFIT_ALTA_GAMA=
PROFIT_SERVER=
COSTOS_FIJOS_MOSTRADOR=
COSTOS_FIJOS_ESTANDAR=
DIAGNOSTICO_MOSTRADOR=
# ... ver .env.example para el resto de perfiles (incl. reacondicionado / nivel componente)

# SICSER (Fase 1 — solo lectura + import a SIGMA)
SICSER_BASE_URL=
SICSER_TOKEN_OOW=
SICSER_TOKEN_GARANTIAS=
SICSER_CACHE_TTL=120
```

**Nota CSRF:** en producción `CSRF_COOKIE_NAME = 'sigma_csrftoken'`. Todo `fetch`/TypeScript debe leer esa cookie (no asumir el nombre default `csrftoken`).

---

## 7. COMMON PATTERNS TO FOLLOW

### Creating New Features
1. **Models**: Define in `models.py` with `__str__()` and `Meta`
2. **Admin**: Configure in `admin.py` with `list_display`, `search_fields`
3. **Forms**: Create `forms.py` with `ModelForm` + Bootstrap widgets
4. **Views**: Function-based views with error handling + messages
5. **URLs**: Named patterns in `urls.py`
6. **Templates**: Extend `base.html`, use `{% static %}`
7. **Static Files**: CSS in `static/css/`, TypeScript in `static/ts/`
8. **Migrations**: `makemigrations` → review → `migrate`

### URL Patterns
```python
# app_name/urls.py
from django.urls import path
from . import views

app_name = 'inventario'  # Namespace

urlpatterns = [
    path('', views.lista_productos, name='lista_productos'),
    path('crear/', views.crear_producto, name='crear_producto'),
    path('<int:pk>/editar/', views.editar_producto, name='editar_producto'),
    path('<int:pk>/eliminar/', views.eliminar_producto, name='eliminar_producto'),
]

# In templates: {% url 'inventario:crear_producto' %}
# In views: redirect('inventario:lista_productos')
```

### Messages Framework
```python
from django.contrib import messages

messages.success(request, 'Operación exitosa.')
messages.error(request, 'Error al procesar.')
messages.warning(request, 'Advertencia importante.')
messages.info(request, 'Información adicional.')
```

---

## 8. DOCUMENTATION & COMMENTS

### Español para Lógica de Dominio y Comunicación
```python
# EXPLICACIÓN PARA PRINCIPIANTES:
# Esta función calcula el precio total de una orden de servicio
# incluyendo mano de obra, piezas y descuentos aplicables
def calcular_precio_total(orden):
    """
    Calcula el precio total de una orden de servicio.
    
    Args:
        orden (OrdenServicio): Instancia de la orden a procesar
        
    Returns:
        Decimal: Precio total con todos los cargos y descuentos
    """
    # Implementation with detailed comments
```

**IMPORTANTE**: 
- **Variables de dominio**: En español (`orden`, `precio_total`, `estado_orden`)
- **Comentarios de negocio**: En español
- **Docstrings**: En español
- **Comunicación con usuario**: SIEMPRE en español
- **Términos técnicos en código**: Pueden ser en inglés cuando sea estándar (`DataFrame`, `queryset`, `pk`)

### Inglés Solo para Términos Técnicos Estándar
```python
# Technical implementation details (comentarios técnicos pueden ser inglés)
# Using pandas DataFrame for efficient data aggregation
df = pd.DataFrame(list(queryset.values()))
```

---

## 9. TESTING & VALIDATION

### Current Approach
- **Unit / integration tests (Almacén)**: suite formal en `almacen/tests/` (profit, sync componente, compras sin orden, reacondicionado, totales)
- **Humo modularización ST**: `servicio_tecnico/tests/` (reexports, resolve URLs por fase)
- **Scripts manuales**: `scripts/testing/` (email, PDF RHITSO, ML, storage)
- **Otras apps**: cobertura aún mínima en `tests.py` por defecto
- **Política**: todo cambio con comportamiento nuevo/cambiado debe traer test (o ampliar uno). Ver Sección 1 → Testing.

### Running Tests
```bash
# Suite Almacén (preferir al tocar cotizaciones / sync ST / reacondicionados)
python manage.py test almacen
python manage.py test almacen.tests.test_profit_cotizacion
python manage.py test almacen.tests.test_sincronizar_componente_st
python manage.py test almacen.tests.test_generar_compras_sin_orden
python manage.py test almacen.tests.test_costeo_reacondicionado
python manage.py test almacen.tests.test_totales_cotizacion

# Suite ST (modularización + humo)
python manage.py test servicio_tecnico.tests

# Scripts manuales
python scripts/testing/test_email_config.py
python scripts/testing/test_pdf_rhitso.py
python scripts/testing/test_dashboard_ml.py
python scripts/testing/test_dynamic_storage.py
```

### Future Improvements
Consider adding:
- pytest configuration
- pytest-django for fixtures
- coverage.py for test coverage
- Factory Boy for test data
- Pre-commit hooks for quality checks
- Ampliar suite formal a `servicio_tecnico` (seguimiento, SICSER, push)

---

## 10. COMMON PITFALLS TO AVOID

1. **Don't edit compiled JavaScript** - Always modify `.ts` files
2. **Don't hardcode URLs** - Use `{% url %}` and `reverse()`
3. **Don't skip migrations** - Run after every model change
4. **Don't commit secrets** - Use `.env` with `python-decouple`
5. **Don't ignore messages** - Provide user feedback for all actions
6. **Don't mix Spanish/English** - Domain logic in Spanish, tech in English
7. **Don't forget Bootstrap classes** - All forms need styling
8. **Don't skip `__str__()`** - Required for all models
9. **Don't use inline styles** - Use static CSS files
10. **Don't skip TypeScript compilation** - Run `pnpm run build` before testing
11. **Don't break PWA compatibility** - Never remove manifest, apple-mobile-web-app tags, or viewport-fit=cover from `base.html`
12. **Don't use hover-only UI** - All interactions must work on touch screens (mobile-first)
13. **Don't hardcode colors without dark mode override** - Use CSS variables (`var(--nombre)`) or add `[data-bs-theme="dark"] .clase {}` override. New CSS files MUST have a dark mode section. See Section 5 → Dark Mode.
14. **Don't touch the anti-flash script in base.html** - The inline `<script>` in `<head>` that sets `data-bs-theme` before render prevents white flash — never modify or remove it.
15. **Don't use gradients** — No `linear-gradient`, `radial-gradient` ni efectos de glassmorphism genéricos. El diseño del proyecto es limpio y directo. Los gradientes se ven como "IA Slop" y están prohibidos salvo que el usuario los pida explícitamente.
16. **Don't call `.delay()` without `db_alias`** — Toda tarea Celery que acceda a la base de datos DEBE recibir `db_alias=get_pais_actual()['db_alias']`. Sin este parámetro, el worker siempre usa la BD `default` (México), rompiendo el multi-tenant para Chile, Argentina y Colombia. Ver Sección 12 → Celery Multi-Tenant.
17. **Don't mezclar PWA/push staff con cliente** — `PushSubscription` ≠ `PushSubscriptionCliente`; `pwa_install.ts` ≠ `pwa_install_seguimiento.ts`.
18. **Don't hardcodear PROFIT_*/COSTOS_FIJOS_*/DIAGNOSTICO_*** — viven en `.env`; el cotizador y el reacondicionado los leen desde settings.
19. **Don't generar compras sin orden vinculada** — `generar_compras_solicitud` exige `orden_servicio`.
20. **Don't inventar writes a SICSER** — Fase 1 es solo lectura + import a SIGMA.
21. **Don't asumir que todo cambio de estado dispara push** — solo estados en `ESTADOS_PUSH_TECNICO` / `ESTADOS_PUSH_CLIENTE`.
22. **Don't usar cookie CSRF default** — en producción la cookie se llama `sigma_csrftoken`.
23. **Don't re-inflar monolitos de vistas** — no agregar features grandes a `views.py` densos; usar `views_*.py` + `services/` + reexports. Ver Sección 4 → Modularidad de vistas. En `services/`, no usar `from .models` (rompe con `services.models`).
24. **Don't entregar comportamiento nuevo sin test** — si aplica (vista, API, regla de negocio, bugfix, sync), añadir o ampliar un test en la suite de la app. Ver Sección 1 → Política de tests. Excepción: docs/CSS cosmético o pedido explícito del usuario.

---

## 11. QUICK REFERENCE

| Task | Command |
|------|---------|
| Start server | `python manage.py runserver` |
| Apply migrations | `python manage.py migrate` |
| Create migrations | `python manage.py makemigrations` |
| Admin user | `python manage.py createsuperuser` |
| Django shell | `python manage.py shell` |
| Compile TypeScript | `pnpm run build` |
| Watch TypeScript | `pnpm run watch` |
| Run tests | `python manage.py test` |
| Run Almacén tests | `python manage.py test almacen` |
| Run ST modularización tests | `python manage.py test servicio_tecnico.tests` |
| Seed data | `python scripts/poblado/poblar_sistema.py` |

---

## 12. CELERY MULTI-TENANT — REGLAS CRÍTICAS

El proyecto usa una arquitectura **Database-per-Tenant** manual (un subdominio → una BD independiente).
Las tareas Celery se ejecutan en un worker separado, **fuera del contexto HTTP**, por lo que el middleware
`PaisMiddleware` no corre automáticamente. Sin intervención explícita, **todas las tareas usan la BD `default` (México)**.

### Cómo funciona el mecanismo

| Componente | Archivo | Rol |
|---|---|---|
| Señal `task_prerun` | `config/celery.py` | Lee `db_alias` de los kwargs de la tarea y configura thread-locals antes de ejecutarla |
| DB Router | `config/db_router.py` | Lee los thread-locals para enrutar automáticamente todas las queries al tenant correcto |
| `get_pais_actual()` | `config/paises_config.py` | En vistas HTTP, lee el subdominio. En tasks, funciona porque la señal ya configuró los thread-locals |

### Regla obligatoria al crear o modificar tareas Celery

**Toda tarea que acceda a la BD debe:**

1. **Aceptar `db_alias='default'` en su firma:**
```python
@shared_task(bind=True, ...)
def mi_nueva_tarea(self, param1, param2, usuario_id=None, db_alias='default'):
    """
    ...
    Parámetros:
        db_alias : Alias de BD del país activo. La señal task_prerun lo usa
                   para configurar el contexto de país en el worker.
    """
    # Las queries ORM se enrutan automáticamente — NO necesitas .using(db_alias)
    objeto = MiModelo.objects.get(pk=param1)
```

2. **Recibir el valor correcto al encolar desde una vista:**
```python
# ✅ CORRECTO
from config.paises_config import get_pais_actual
mi_nueva_tarea.delay(
    param1=valor,
    param2=valor,
    usuario_id=request.user.pk,
    db_alias=get_pais_actual()['db_alias'],
)

# ❌ INCORRECTO — el worker usará siempre la BD de México
mi_nueva_tarea.delay(param1=valor, param2=valor)
```

3. **En Celery chains, pasar `db_alias` dentro de `.s()`:**
```python
from config.paises_config import get_pais_actual
_db = get_pais_actual()['db_alias']

cadena = celery_chain(
    tarea_a.s(orden_id, usuario_id, _db),
    tarea_b.s(orden_id, usuario_id, _db),
)
cadena.delay()
# NOTA: cadena.delay() no lleva db_alias — ya va en cada .s()
```

### Países activos y sus db_alias

| País | Subdominio | `db_alias` |
|---|---|---|
| México | `app.sigmasystem.work` | `default` |
| Argentina | `argentina.sigmasystem.work` | `argentina` |
| Chile | `chile.sigmasystem.work` | `chile` |
| Colombia | `colombia.sigmasystem.work` | `colombia` |

### Celery Beat (tareas programadas)

Definido en `CELERY_BEAT_SCHEDULE` dentro de `config/settings.py`. Las tareas periódicas **también** deben respetar multi-tenant (cuando acceden a BD por país, iterar tenants o recibir `db_alias`).

| Job | Task | Schedule |
|-----|------|----------|
| Limpiar notificaciones antiguas | `notificaciones.limpiar_antiguas` | Cada 24 h |
| Recordatorio encuestas satisfacción | `servicio_tecnico.verificar_encuestas_pendientes` | Diario 8:00 |
| Recordatorio imágenes faltantes | `servicio_tecnico.verificar_recordatorios_imagenes` | Diario 8:00 |

### Redis: broker Celery vs cache Django

| Uso | Redis DB | Config |
|-----|----------|--------|
| Celery broker / results | `/0` y `/1` | Settings Celery |
| Cache Django (dashboards, SICSER, etc.) | `/2` | `REDIS_CACHE_URL` + `django_redis` |

Si Redis cae, el cache está configurado con `IGNORE_EXCEPTIONS=True` (la app sigue sin cache). No mezclar DBs.

### CSRF en fetch / TypeScript

En producción: `CSRF_COOKIE_NAME = 'sigma_csrftoken'`. Al hacer `POST`/`PUT`/`DELETE` desde TS, leer esa cookie (ver patrón en `ollama_sic.ts` y módulos de seguimiento).

### Inventario breve de tareas Celery

**`servicio_tecnico/tasks.py` (selección):**
- Correos RHITSO, feedback rechazo/satisfacción, vigencia vencida
- Diagnóstico / imágenes ingreso-egreso al cliente
- `enviar_seguimiento_cliente_task`, recordatorios encuesta e imágenes
- Video: `generar_video_resumen_task`, `comprimir_video_*`, `enviar_evidencia_video_task`, `enviar_rewind_egreso_email_task`

**`almacen/tasks.py`:**
- `notificar_front_cotizacion_task`, `notificar_compras_nueva_cotizacion_task`
- `enviar_cotizacion_cliente_task` (PDF reparación o reacondicionado)

Todas las tareas en `servicio_tecnico/tasks.py` y `almacen/tasks.py` ya tienen `db_alias` en su firma.
Al agregar una tarea nueva, seguir el mismo patrón.

---

**Last Updated**: Julio 2026  
**Django Version**: 5.2.5  
**Python Version**: 3.12+  
**TypeScript Version**: 5.9.3
