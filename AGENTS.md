# AGENTS.md - Development Guide for AI Coding Agents

> **Project**: Sistema Integrado de Gestión Técnica y Control de Calidad  
> **Framework**: Django 5.2.5 | Python 3.10+ | TypeScript 5.9.3  
> **Purpose**: Enterprise technical service management with ML analytics

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

**Last Updated**: January 2026  
**Django Version**: 5.2.5  
**Python Version**: 3.10+  
**TypeScript Version**: 5.9.3
