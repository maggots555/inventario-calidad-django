# AGENTS.md - Development Guide for AI Coding Agents

> **Project**: Sistema Integrado de Gestión Técnica y Control de Calidad (SIGMA)  
> **Framework**: Django 5.2.5 | Python 3.10+ | TypeScript 5.9.3  
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
npm run build      # Compile TypeScript once
npm run watch      # Auto-compile on file changes
tsc                # Direct TypeScript compilation
```

### Testing
**No formal test framework configured** - Uses manual test scripts:
```bash
# Run individual test scripts
python scripts/testing/test_email_config.py
python scripts/testing/test_pdf_rhitso.py
python scripts/testing/test_dashboard_ml.py
python scripts/testing/test_dynamic_storage.py

# Permission testing
./scripts/test_permisos.sh

# Django's built-in tests (minimal coverage currently)
python manage.py test                           # All tests
python manage.py test inventario                # App-specific
python manage.py test inventario.tests.MyTest   # Single test
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
- **ALWAYS compile before testing** - Run `npm run build`

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
│   ├── settings.py           # Main settings
│   ├── urls.py              # Root URL configuration
│   ├── storage_utils.py      # Dynamic file storage
│   └── constants.py          # Global constants
├── inventario/               # App: Product inventory & employees
├── servicio_tecnico/         # App: Service orders (MAIN)
│   ├── models.py            # 20+ models (OrdenServicio, etc.)
│   ├── plotly_visualizations.py  # 3900+ lines of charts
│   ├── ml_predictor.py      # ML predictions
│   └── ml_advanced/         # Advanced ML modules
├── scorecard/                # App: Quality control system
├── almacen/                  # App: Central warehouse
├── static/
│   ├── ts/                  # TypeScript source (EDIT THESE)
│   │   ├── base.ts
│   │   └── scanner.ts
│   ├── js/                  # Compiled JavaScript (AUTO-GENERATED)
│   ├── css/                 # Organized CSS files
│   │   ├── base.css        # Global styles
│   │   ├── components.css  # UI components
│   │   └── forms.css       # Form styling
│   └── images/
├── templates/                # Global templates
│   └── base.html
├── media/                    # User uploads (organized by app)
├── scripts/
│   ├── testing/             # Manual test scripts (15 files)
│   ├── poblado/             # Database seeding
│   └── verificacion/        # Data validation
├── logs/                     # Application logs
├── ml_models/                # Trained ML models (.pkl)
├── manage.py
├── requirements.txt
├── package.json
└── tsconfig.json
```

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
- CSRF protection always active
- HSTS enabled in production (`DEBUG=False`)

---

## 5. SPECIAL FEATURES & INTEGRATIONS

### Machine Learning
- **Location**: `servicio_tecnico/ml_advanced/`
- **Models**: Price optimizer, rejection classifier, action recommender
- **Tech**: scikit-learn, pandas, joblib
- **Storage**: Trained models in `ml_models/` directory

### Analytics Dashboard
- **File**: `servicio_tecnico/plotly_visualizations.py` (3939 lines)
- **Charts**: 50+ interactive Plotly visualizations
- **Types**: Line, bar, scatter, heatmap, sunburst, treemap
- **Data**: Pandas DataFrames from Django QuerySets

### RHITSO Integration
External laboratory management system:
- Email workflows to multiple contacts
- PDF generation with ReportLab
- Status synchronization
- Color-coded states system

### Dynamic Storage
Intelligent file storage with disk failover:
- Primary/alternate disk support (`.env` configured)
- Automatic space monitoring
- Images organized by order ID
- Custom Django storage backend

### PWA (Progressive Web App)
The app is installable on Android and iOS as a native-like app:
- **Manifest**: `static/manifest.json` — name, icons, theme color, `display: standalone`
- **iOS support**: `apple-mobile-web-app-capable` + `apple-mobile-web-app-status-bar-style` in `templates/base.html`
- **Viewport**: `viewport-fit=cover` for notch/Dynamic Island support on iPhones
- **Theme color**: `#1f6391` (matches brand)
- **No service worker** currently — app requires internet connection (no offline mode)

**PWA Rules for AI agents**:
- NEVER remove the `<link rel="manifest">` tag from `base.html`
- NEVER remove or alter the `apple-mobile-web-app-*` meta tags
- NEVER set `maximum-scale` > 1.0 or remove `viewport-fit=cover`
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
/* ✅ CORRECTO: Usar variables CSS en modo claro */
.mi-componente {
    background-color: var(--gray-100);   /* Se adapta automáticamente */
    color: var(--gray-900);
    border: 1px solid var(--gray-200);
}

/* ✅ CORRECTO: Override para colores hardcodeados */
.mi-componente-con-gradiente {
    background: linear-gradient(135deg, #1f6391, #2980b9); /* Color hardcodeado */
}
[data-bs-theme="dark"] .mi-componente-con-gradiente {
    background: linear-gradient(135deg, #1e3a5f, #1e293b); /* Versión oscura */
}

/* ❌ INCORRECTO: Color hardcodeado sin override para oscuro */
.mi-componente {
    background-color: #ffffff;  /* Se verá igual en modo oscuro — MAL */
    color: #333333;
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

✅ SIEMPRE usar var(--nombre-variable) para colores
✅ SIEMPRE agregar overrides oscuros para gradientes y colores hardcodeados
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
    background: linear-gradient(135deg, #1f6391, #2980b9);
}

/* ============================================================
   MODO OSCURO — Overrides para [data-bs-theme="dark"]
   ============================================================ */
[data-bs-theme="dark"] .mi-componente-especial {
    background: linear-gradient(135deg, #1e3a5f, #0f172a);
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
```

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
- **Unit tests**: Minimal (default boilerplate in `tests.py`)
- **Integration tests**: Manual scripts in `scripts/testing/`
- **Validation**: Standalone Python scripts

### Running Manual Tests
```bash
# Email configuration
python scripts/testing/test_email_config.py

# PDF generation
python scripts/testing/test_pdf_rhitso.py

# ML dashboard
python scripts/testing/test_dashboard_ml.py

# Dynamic storage
python scripts/testing/test_dynamic_storage.py
```

### Future Improvements
Consider adding:
- pytest configuration
- pytest-django for fixtures
- coverage.py for test coverage
- Factory Boy for test data
- Pre-commit hooks for quality checks

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
10. **Don't skip TypeScript compilation** - Run `npm run build` before testing
11. **Don't break PWA compatibility** - Never remove manifest, apple-mobile-web-app tags, or viewport-fit=cover from `base.html`
12. **Don't use hover-only UI** - All interactions must work on touch screens (mobile-first)
13. **Don't hardcode colors without dark mode override** - Use CSS variables (`var(--nombre)`) or add `[data-bs-theme="dark"] .clase {}` override. New CSS files MUST have a dark mode section. See Section 5 → Dark Mode.
14. **Don't touch the anti-flash script in base.html** - The inline `<script>` in `<head>` that sets `data-bs-theme` before render prevents white flash — never modify or remove it.

---

## 11. QUICK REFERENCE

| Task | Command |
|------|---------|
| Start server | `python manage.py runserver` |
| Apply migrations | `python manage.py migrate` |
| Create migrations | `python manage.py makemigrations` |
| Admin user | `python manage.py createsuperuser` |
| Django shell | `python manage.py shell` |
| Compile TypeScript | `npm run build` |
| Watch TypeScript | `npm run watch` |
| Run tests | `python manage.py test` |
| Seed data | `python scripts/poblado/poblar_sistema.py` |

---

**Last Updated**: March 2026  
**Django Version**: 5.2.5  
**Python Version**: 3.10+  
**TypeScript Version**: 5.9.3
