# Copilot Instructions for Django Project

## Project Overview
Django 5.2.5 project with proper separation between project configuration (`config/`) and application logic. Multi-app architecture with advanced data science and analytics capabilities.

### Core Applications
1. **inventario**: Product inventory, employee management, QR codes, stock tracking
2. **scorecard**: Quality control system, incident tracking, component management
3. **servicio_tecnico**: Technical service orders (MAIN APP)
   - Complete repair lifecycle management
   - RHITSO integration (external laboratory)
   - Venta Mostrador (counter sales)
   - Analytics dashboard with ML predictions
   - Cotización system with approval workflows
   - Image management with dynamic storage

### Tech Stack
- **Backend**: Django 5.2.5, Python 3.10+
- **Frontend**: Bootstrap 5.3.2, TypeScript 5.9.3
- **Data Science**: Plotly, Pandas, Scikit-learn, Matplotlib
- **Database**: SQLite (dev) / PostgreSQL (production) with connection pooling
- **Documents**: ReportLab (PDF), OpenPyXL (Excel), QRCode generation

## 🎓 User Experience Level
**IMPORTANT**: The user is new to Python programming. When making any modifications or suggesting code changes:
- **Explain every change in detail**: What the code does, why it's needed, and how it works
- **Break down complex concepts**: Use simple language and avoid assuming prior Python knowledge
- **Provide context**: Explain how the code fits into the larger Django application
- **Show before/after**: When modifying code, explain what changed and why
- **Include learning opportunities**: Point out Python concepts, Django patterns, and best practices
- **Use beginner-friendly examples**: Provide simple, clear examples when introducing new concepts
- **Explain imports and dependencies**: What each import does and why it's needed
- **Describe file structure**: Explain where files go and why they're organized that way

## 🏆 Django Best Practices & Recommended Structure

### ✅ Proper Django Project Structure (Follow This Pattern)
**Example: `inventario` project**
```
project_name/
├── config/                    # Project configuration (settings, main URLs, WSGI)
│   ├── __init__.py
│   ├── settings.py           # Project settings
│   ├── urls.py              # Main URL configuration
│   ├── wsgi.py              # WSGI application
│   └── asgi.py              # ASGI application (optional)
├── app_name/                 # Individual Django apps
│   ├── __init__.py
│   ├── models.py            # Data models
│   ├── views.py             # Business logic
│   ├── forms.py             # Form definitions
│   ├── urls.py              # App-specific URLs
│   ├── admin.py             # Admin configuration
│   ├── apps.py              # App configuration
│   ├── migrations/          # Database migrations
│   └── templates/app_name/  # App-specific templates
├── templates/               # Global templates (base.html, etc.)
├── static/                  # Global static files
├── manage.py               # Django management script
├── requirements.txt        # Project dependencies
├── .gitignore             # Git ignore patterns
└── README.md              # Project documentation
```

### ❌ Avoid This Structure (Legacy/Confusing Pattern)
**Example: `mi_sitio` project (problematic)**
- Same name for project and app: `mi_sitio/mi_sitio/`
- Mixed project and app files in same directory
- Confusing file organization

## Django Development Best Practices

### Models & Database
- **Clear model definitions**: Use descriptive field names and appropriate field types
- **Model Meta options**: Include `ordering`, `verbose_name_plural` for better admin experience
- **String representation**: Always implement `__str__()` method for models
- **Validation**: Use `clean()` method for custom model validation
- **EXPLAIN TO USER**: When creating or modifying models, explain field types (CharField, IntegerField, etc.), Meta class purpose, and why `__str__()` is important

### Views & URL Patterns
- **Function-based views**: Use for simple operations, clear and explicit
- **URL naming convention**: Use descriptive names for reverse URL lookups
- **Proper imports**: Import specific functions, use get_object_or_404 for safety
- **Message framework**: Provide user feedback for all CRUD operations
- **Example URL patterns**:
```python
urlpatterns = [
    path('', views.lista_productos, name='lista_productos'),
    path('crear/', views.crear_producto, name='crear_producto'),
    path('editar/<int:producto_id>/', views.editar_producto, name='editar_producto'),
    path('eliminar/<int:producto_id>/', views.eliminar_producto, name='eliminar_producto'),
]
```

### Forms & Templates
- **ModelForm pattern**: Extend ModelForm with Bootstrap widgets for consistent styling
- **Template inheritance**: Use base.html for consistent layout
- **Named URLs**: Always use `{% url 'name' %}` instead of hardcoded paths
- **Bootstrap integration**: Apply Bootstrap classes through form widgets
- **EXPLAIN TO USER**: When creating forms, explain ModelForm (auto-generates fields from model), widgets (HTML appearance), and template inheritance (avoid code repetition)

### Frontend Architecture
- **Bootstrap-based UI**: Use Bootstrap 5+ for responsive design
- **Template structure**: Separate base templates from app-specific templates
- **Static files**: Organize CSS, JS, and images in appropriate directories
- **Template pattern**:
```html
{% extends 'base.html' %}
{% block title %}Page Title - {{ block.super }}{% endblock %}
{% block content %}
    <!-- Page content -->
{% endblock %}
```

### 🚀 TypeScript Integration - MANDATORY FOR ALL JAVASCRIPT
**CRITICAL**: This project uses TypeScript for ALL client-side scripting. NEVER write plain JavaScript files directly.

#### ✅ Why TypeScript is Required
**EXPLAIN TO USER**: TypeScript es un "superset" de JavaScript - significa que es JavaScript con superpoderes adicionales:

1. **Type Safety (Seguridad de Tipos)**: El compilador detecta errores antes de ejecutar
   - Evita errores como `undefined is not a function`
   - Te avisa si usas una variable incorrectamente
   - Previene bugs comunes de JavaScript

2. **IntelliSense & Autocompletado**: Tu editor VS Code te ayuda mientras escribes
   - Sugiere métodos y propiedades disponibles
   - Muestra documentación inline
   - Detecta errores de sintaxis inmediatamente

3. **Better Refactoring**: Cambiar código es más seguro
   - Renombrar variables afecta todas las referencias
   - El editor te muestra dónde se usa cada función
   - Menos probabilidad de romper algo al modificar código

4. **Self-Documenting Code**: Los tipos sirven como documentación
   - Sabes qué parámetros espera una función
   - Ves qué tipo de datos retorna cada función
   - No necesitas adivinar la estructura de objetos

5. **Compila a JavaScript estándar**: Funciona en todos los navegadores
   - TypeScript se convierte a JavaScript puro
   - Compatible con todos los navegadores modernos
   - No requiere plugins o extensiones en el navegador

#### 📁 TypeScript Project Structure
```
project_root/
├── static/
│   ├── js/                    # Compiled JavaScript (DO NOT EDIT)
│   │   ├── base.js           # Generated from base.ts
│   │   ├── scanner.js        # Generated from scanner.ts
│   │   └── dashboard.js      # Generated from dashboard.ts
│   └── ts/                   # TypeScript Source Files (EDIT THESE)
│       ├── base.ts           # Global TypeScript utilities
│       ├── scanner.ts        # QR Scanner functionality
│       ├── dashboard.ts      # Dashboard functionality
│       └── types/            # Type definitions
│           ├── models.ts     # Data model interfaces
│           └── api.ts        # API response types
├── tsconfig.json             # TypeScript compiler configuration
└── package.json              # Node dependencies (TypeScript, etc.)
```

#### 🔧 TypeScript Configuration
**tsconfig.json** configured for this project:
```json
{
  "compilerOptions": {
    "target": "ES2018",                 // Compile to ES2018 JavaScript
    "lib": ["ES2018", "DOM"],          // Include ES2018 and DOM libraries
    "outDir": "./static/js",            // Output compiled JS here
    "strict": true,                     // Enable all strict type-checking
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "sourceMap": true                   // Generate .map files for debugging
  },
  "include": ["static/ts/**/*.ts"]
}
```

#### ✍️ TypeScript Development Workflow

**1. Write TypeScript**: Edit `.ts` files in `static/ts/` with proper types and interfaces
**2. Compile**: Run `npm run watch` (auto-compile) or `npm run build` (single compile)
**3. Include in Templates**: Load compiled `.js` files with `{% static 'js/file.js' %}`

**EXPLAIN TO USER**: Define interfaces for data structures, use type annotations for functions, leverage VS Code IntelliSense for autocomplete

#### ⚠️ CRITICAL RULES - NEVER VIOLATE

❌ **NEVER edit `.js` files directly** - They are generated from TypeScript
❌ **NEVER write new `.js` files** - Create `.ts` files instead
❌ **NEVER skip type annotations** - Use explicit types for function parameters and returns
❌ **NEVER use `any` type** - Be specific with types (use `unknown` if truly unknown)
❌ **NEVER ignore TypeScript errors** - Fix them before committing code
❌ **NEVER commit without compiling** - Always run `npm run build` before committing

✅ **ALWAYS write `.ts` files** - For all new JavaScript functionality
✅ **ALWAYS define interfaces** - For data structures and API responses
✅ **ALWAYS use strict mode** - TypeScript strict checks prevent bugs
✅ **ALWAYS add JSDoc comments** - Explain complex functions
✅ **ALWAYS compile before testing** - Run `tsc` or `npm run build`
✅ **ALWAYS commit both `.ts` and compiled `.js`** - Others can use without compiling

#### 📦 package.json Scripts
```json
{
  "scripts": {
    "build": "tsc",
    "watch": "tsc --watch",
    "dev": "tsc --watch"
  },
  "devDependencies": {
    "typescript": "^5.3.0"
  }
}
```

### 📊 Data Science & Machine Learning Integration

This project includes advanced analytics and predictive capabilities using Python's data science ecosystem.

#### Core Analytics Features
1. **Dashboard de Cotizaciones**: Interactive analytics dashboard with 20+ Plotly visualizations
2. **ML Predictor**: Machine learning models for repair outcome predictions
3. **Excel Exporters**: Automated data export with openpyxl
4. **Statistical Analysis**: Trend analysis and forecasting

#### Key Files
```
servicio_tecnico/
├── plotly_visualizations.py    # Interactive Plotly chart generators
├── ml_predictor.py             # ML models for predictions
├── ml_advanced/                # Advanced ML algorithms
│   └── motivo_rechazo.py      # Rejection reason classifier
├── excel_exporters.py          # Excel export functionality
└── utils_cotizaciones.py       # Analytics utilities
```

#### Technologies Used
- **Plotly**: Interactive charts (line, bar, scatter, heatmaps, sunburst)
- **Pandas**: Data manipulation and aggregation
- **Scikit-learn**: Classification, regression, clustering algorithms
- **Matplotlib/Seaborn**: Statistical visualizations

**EXPLAIN TO USER**: When working with analytics, explain what each visualization shows, how ML models make predictions, and how data flows from Django models to Pandas DataFrames to Plotly charts.

### Static Files Organization & Best Practices
**CRITICAL**: Never put extensive CSS/JS directly in templates. Always use separate static files for maintainability, performance, and scalability.

#### ✅ Recommended Static Files Structure
```
project_name/
├── static/                     # Global static files directory
│   ├── css/
│   │   ├── base.css           # Global styles (navbar, footer, layout)
│   │   ├── components.css     # Reusable components (cards, badges, alerts)
│   │   ├── forms.css          # Form-specific styling
│   │   └── dashboard.css      # Page-specific styles (optional)
│   ├── js/
│   │   ├── base.js            # Global JavaScript utilities
│   │   ├── scanner.js         # Feature-specific JS (QR scanner)
│   │   └── dashboard.js       # Page-specific JavaScript
│   └── images/
│       ├── logos/
│       └── icons/
├── app_name/
│   └── static/app_name/       # App-specific static files (if needed)
│       ├── css/
│       └── js/
```

#### 🔧 Django Static Files Configuration
In `settings.py`:
```python
# Static files configuration
STATIC_URL = 'static/'

# Directories where Django looks for static files
STATICFILES_DIRS = [
    BASE_DIR / "static",  # Global static files
]

# For production (uncomment when deploying):
# STATIC_ROOT = BASE_DIR / "staticfiles"
```

#### 📝 CSS Organization Principles
**EXPLAIN TO USER**: CSS should be organized by responsibility, not by page. This makes styles reusable and easier to maintain.

**base.css** - Global styles that apply everywhere:
```css
/* Variables for consistent theming */
:root {
    --primary-color: #0d6efd;
    --success-color: #27ae60;
    --danger-color: #e74c3c;
    --border-radius: 8px;
    --box-shadow: 0 2px 10px rgba(0,0,0,0.1);
}

/* Global elements */
body { font-family: 'Segoe UI', sans-serif; }
.navbar-brand { font-weight: bold; }
.card { border-radius: var(--border-radius); }
```

**components.css** - Specific component styles:
```css
/* Inventory-specific components */
.stock-bajo { color: var(--danger-color); font-weight: bold; }
.qr-code { max-width: 200px; border-radius: var(--border-radius); }
.scanner-container { background-color: #000; }
```

**forms.css** - Form styling for consistency:
```css
/* Enhanced form controls */
.form-control {
    border: 2px solid #e9ecef;
    border-radius: var(--border-radius);
    transition: all 0.3s ease;
}
.form-control:focus {
    border-color: var(--primary-color);
    box-shadow: 0 0 0 0.2rem rgba(13,110,253,0.15);
}
```

#### 🔗 Loading Static Files in Templates
**base.html pattern**:
```html
<!DOCTYPE html>
<html>
<head>
    <!-- External CSS (Bootstrap) -->
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    
    <!-- Custom CSS - Load Django static files -->
    {% load static %}
    <link rel="stylesheet" href="{% static 'css/base.css' %}">
    <link rel="stylesheet" href="{% static 'css/components.css' %}">
    <link rel="stylesheet" href="{% static 'css/forms.css' %}">
    
    <!-- Page-specific CSS -->
    {% block extra_css %}{% endblock %}
</head>
<body>
    <!-- Content -->
    
    <!-- JavaScript -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script src="{% static 'js/base.js' %}"></script>
    {% block extra_js %}{% endblock %}
</body>
</html>
```

**Page-specific template pattern**:
```html
{% extends 'base.html' %}

{% block extra_css %}
    <link rel="stylesheet" href="{% static 'css/dashboard.css' %}">
{% endblock %}

{% block content %}
    <!-- Page content -->
{% endblock %}

{% block extra_js %}
    <script src="{% static 'js/dashboard.js' %}"></script>
{% endblock %}
```

#### 📱 JavaScript Organization
**base.js** - Global utilities and common functions:
```javascript
// Auto-hide alerts, form validation, utility functions
document.addEventListener('DOMContentLoaded', function() {
    // Global initialization code
});

function confirmarEliminacion(mensaje) {
    return confirm(mensaje);
}
```

**Feature-specific JS files** - Keep related functionality together:
```javascript
// scanner.js - QR Scanner functionality
const QRScanner = {
    init: function() { /* Scanner initialization */ },
    procesarCodigo: function(codigo) { /* Process QR code */ }
};
```

#### ⚠️ What NOT to Do
❌ **Don't put CSS in `<style>` tags in templates**:
```html
<!-- WRONG - Hard to maintain -->
<style>
    .my-style { color: red; }
</style>
```

❌ **Don't mix concerns in CSS files**:
```css
/* WRONG - Don't mix page-specific and global styles */
/* base.css should not contain dashboard-specific styles */
```

❌ **Don't use inline styles extensively**:
```html
<!-- WRONG - Not reusable or maintainable -->
<div style="color: red; font-weight: bold;">
```

#### ✅ Benefits of This Approach
**For Beginners**: This organization helps you:
- **Find styles quickly**: Each file has a clear purpose
- **Avoid duplication**: Reuse styles across pages
- **Debug easier**: Know exactly where to look for specific styles
- **Scale your project**: Add new features without breaking existing styles
- **Work in teams**: Multiple people can edit different files simultaneously
- **Cache performance**: Browsers cache CSS files separately from HTML

#### 🎨 When to Modify Appearance
- **Global changes** (colors, fonts): Edit `base.css`
- **Component styling** (buttons, cards): Edit `components.css`
- **Form improvements**: Edit `forms.css`
- **Page-specific styles**: Create new CSS file (e.g., `dashboard.css`)
- **New functionality**: Add JavaScript in appropriate `.js` file

**EXPLAIN TO USER**: This structure grows with your project. Start simple, but organize from the beginning to avoid technical debt.

## Development Workflows

### Project Setup (Recommended)
```bash
# Create project with proper separation
django-admin startproject config project_name
cd project_name
python manage.py startapp app_name

# Install app in settings.py
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'app_name',  # Your app here
]
```

### Running the Server
```bash
# Navigate to project directory (where manage.py is located)
cd project_name
python manage.py runserver
```
**Note**: Run from directory containing `manage.py`, not parent directory

### Database Operations
```bash
# Create migrations after model changes
python manage.py makemigrations

# Apply migrations to database
python manage.py migrate

# Create superuser for admin access
python manage.py createsuperuser
```

### Adding New Features (Recommended Workflow)
1. **Models**: Define in `app_name/models.py` with proper Meta class
2. **Admin**: Configure in `app_name/admin.py` with list_display and search_fields
3. **Forms**: Create in `app_name/forms.py` using ModelForm with Bootstrap widgets
4. **Views**: Add function-based views in `app_name/views.py` with proper error handling
5. **URLs**: Update `app_name/urls.py` with descriptive names, include in main urls.py
6. **Templates**: Create in `app_name/templates/app_name/` extending base.html
7. **Test**: Create basic tests in `app_name/tests.py`

## Code Conventions

### Form Widgets
Always include Bootstrap classes in form widgets:
```python
widgets = {
    'field_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Description'}),
}
```

### Template Pattern
Use base template inheritance and proper block structure:
```html
{% extends 'base.html' %}
{% block title %}Page Title - {{ block.super }}{% endblock %}
{% block content %}
    <div class="container mt-4">
        <!-- Page content -->
    </div>
{% endblock %}
```

### URL Patterns & Navigation
- Use named URL patterns in all templates: `{% url 'view_name' %}`
- Use reverse() in views: `return redirect('view_name')`
- Include app namespace when needed: `{% url 'app_name:view_name' %}`

### Messages Framework
Always provide user feedback for CRUD operations:
```python
from django.contrib import messages

def create_view(request):
    if form.is_valid():
        form.save()
        messages.success(request, 'Item created successfully.')
        return redirect('list_view')
```

### Admin Configuration
Include proper admin configuration for all models:
```python
@admin.register(ModelName)
class ModelNameAdmin(admin.ModelAdmin):
    list_display = ('field1', 'field2', 'field3')
    list_filter = ('status_field', 'date_field')
    search_fields = ('name_field', 'description_field')
    ordering = ['-date_field']
```

## Project-Specific Features

### 🔬 RHITSO Integration
External laboratory management system for specialized equipment testing:
- Automated email workflows to multiple lab contacts
- Specialized forms for sending equipment to lab
- Bidirectional tracking between internal orders and external testing
- Status synchronization and notifications

### 🛒 Venta Mostrador (Counter Sales)
Streamlined sales system for direct purchases without full diagnosis:
- Quick order entry without cotización workflow
- Simplified pricing and payment tracking
- Integration with main service orders
- Independent or complementary to repair services

### 📊 Analytics Dashboard
Real-time business intelligence with Machine Learning:
- 20+ interactive Plotly visualizations (trends, heatmaps, sunburst charts)
- Predictive models for repair outcomes and costs
- Excel export functionality for offline analysis
- Statistical trend analysis and forecasting
- KPI tracking (active orders, delays, revenue projections)

### 💾 Dynamic Storage Management
Intelligent file storage with automatic disk switching:
- Primary and alternate disk support (configurable via `.env`)
- Automatic space monitoring (MIN_FREE_SPACE_GB threshold)
- Images organized by order (not generic folders)
- Secure media file serving with Django views

### 📸 Image Management
Reorganized structure for better scalability:
- Images stored by order ID: `servicio_tecnico/orden_<ID>/`
- Automatic directory creation per order
- Multiple image types: evidencia_inicial, diagnostico, reparacion_progreso, trabajo_finalizado
- Integration with dynamic storage system

## File Organization & Project Structure

### Recommended Directory Structure
```
project_root/
├── config/                    # Project configuration
│   ├── settings.py           # Django settings with dual DB support
│   ├── urls.py              # Main URL routing
│   ├── constants.py          # Global constants (choices, configs)
│   ├── storage_utils.py      # Dynamic storage management
│   └── media_views.py        # Secure media file serving
├── inventario/               # Inventory management app
├── scorecard/                # Quality control app
├── servicio_tecnico/         # Technical service orders (MAIN)
│   ├── plotly_visualizations.py
│   ├── ml_predictor.py
│   ├── ml_advanced/
│   └── utils/
├── templates/                # Global templates
├── static/                   # Global static files
│   ├── css/                 # Organized CSS files
│   ├── js/                  # Compiled JavaScript (from TypeScript)
│   ├── ts/                  # TypeScript source files
│   └── images/
├── staticfiles/              # Production static files (collectstatic)
├── media/                    # User uploads (organized by app)
│   ├── empleados/
│   ├── scorecard/
│   ├── servicio_tecnico/
│   └── temp/
├── ml_models/                # Trained ML models
├── scripts/                  # Utility scripts
│   ├── poblado/             # Database seeding
│   ├── testing/             # Test scripts
│   ├── verificacion/        # Validation scripts
│   └── ml/                  # ML training scripts
├── docs/                     # Project documentation
│   ├── guias/               # Setup and reference guides
│   └── implementaciones/    # Feature implementation docs
├── logs/                     # Application logs
├── package.json              # Node dependencies (TypeScript)
├── tsconfig.json             # TypeScript configuration
├── requirements.txt          # Python dependencies
├── .env                      # Environment variables (not in git)
├── .env.example             # Environment template
└── manage.py                # Django management script
```

### Configuration Files
- **requirements.txt**: List all Python dependencies with versions
- **.gitignore**: Include Python, Django, IDE, and OS-specific ignore patterns
- **README.md**: Include setup instructions, usage, and project overview
- **.env.example**: Template for environment variables (never commit actual .env)

## Key Dependencies

### Core Framework
- **Django** 5.2.5
- **Python** 3.10+
- **Bootstrap** 5.3.2 (CDN)
- **TypeScript** 5.9.3

### Data Science & Analytics
- **plotly** >= 6.3.0 - Interactive visualizations
- **pandas** >= 2.3.0 - Data analysis
- **scikit-learn** >= 1.5.0 - Machine Learning
- **matplotlib** >= 3.9.0 - Statistical plots
- **seaborn** >= 0.13.0 - Advanced visualizations

### Document Processing
- **openpyxl** 3.1.5 - Excel files
- **reportlab** 4.4.4 - PDF generation
- **qrcode[pil]** 7.4.2 - QR code generation
- **Pillow** 11.3.0 - Image processing

### Database & Configuration
- **SQLite3** (development)
- **PostgreSQL** (production with connection pooling)
- **python-decouple** 3.8 - Environment variables

## Database Configuration

### Dual-Database Setup (SQLite + PostgreSQL)
The project is configured to work with BOTH databases seamlessly using environment variables:

**Development (Windows)**: SQLite3
```bash
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
```

**Production (Linux Server)**: PostgreSQL with optimizations
```bash
DB_ENGINE=django.db.backends.postgresql
DB_NAME=inventario_django
DB_USER=django_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### PostgreSQL Optimizations
Settings automatically applied ONLY when using PostgreSQL (prevents SQLite "database locked" issues):
- **Connection Pooling**: `CONN_MAX_AGE = 600` (10 minutes)
- **Timeout Protection**: `connect_timeout = 10` seconds
- **Automatic Detection**: Optimizations skip SQLite to prevent conflicts

**EXPLAIN TO USER**: The system detects the database engine and applies appropriate settings. SQLite is simple for local development; PostgreSQL handles production traffic with connection pooling.

## Common Patterns to Follow

### Backend (Django/Python)
- Use function-based views consistently
- Include Bootstrap styling in all forms
- Maintain proper template inheritance with base.html
- Use descriptive URL names for reverse lookups
- Keep models simple with appropriate field types
- Use ModelForm for all forms with widget customization
- Always provide user feedback with Django messages
- Separate project configuration from app logic
- Follow Django's "apps" pattern for modular development
- Include proper admin configuration for all models

### Frontend (CSS/TypeScript)
- **NEVER put CSS/JS directly in templates** - Always use separate static files
- **ALWAYS write TypeScript (`.ts`), NEVER plain JavaScript (`.js`)** for new code
- **ALWAYS compile TypeScript before testing** - Run `npm run build` or `tsc`
- **ALWAYS define interfaces** for data structures and API responses
- **ALWAYS use strict type checking** - No `any` types, explicit types for parameters/returns
- Organize static files by functionality (base.css, components.css, forms.css)
- Use CSS variables for consistent theming and easy maintenance
- Load static files properly with `{% load static %}` and `{% static 'path' %}`
- Structure TypeScript in modular files with clear responsibilities
- Always configure `STATICFILES_DIRS` in settings.py for static file discovery
- Keep TypeScript source (`.ts`) in `static/ts/`, compiled JavaScript in `static/js/`
- Include both source `.ts` and compiled `.js` files in version control

## Security & Best Practices
- Never commit SECRET_KEY or sensitive data
- Use environment variables for configuration
- Set DEBUG=False in production
- Use HTTPS in production
- Implement proper user authentication when needed
- Validate and sanitize all user inputs
- Use Django's built-in CSRF protection
- Keep Django and dependencies updated

## Visual Appearance & UI Improvements

### When Asked to Improve Visual Appearance
**NEVER modify only base.html** - Follow these professional practices:

#### ✅ Correct Approach:
1. **Assess current structure**: Check if static files are properly organized
2. **Create/update CSS files**: Modify `static/css/` files, not templates
3. **Separate concerns**: 
   - `base.css`: Global styles (layout, typography, colors)
   - `components.css`: UI components (buttons, cards, badges)
   - `forms.css`: Form styling and validation
4. **Use CSS variables**: For consistent theming and easy updates
5. **Maintain responsiveness**: Ensure mobile-friendly design

#### 🎯 File-Specific Modifications:
- **Global color scheme**: Update CSS variables in `base.css`
- **Navigation/footer**: Modify navbar and footer styles in `base.css`
- **Forms appearance**: Enhance form controls in `forms.css`
- **Component styling**: Update cards, badges, alerts in `components.css`
- **Page-specific styles**: Create new CSS file (e.g., `dashboard.css`)

#### 📝 Example CSS Variable Usage:
```css
/* In base.css */
:root {
    --primary-color: #0d6efd;
    --success-color: #27ae60;
    --danger-color: #e74c3c;
    --border-radius: 8px;
}

/* Use throughout CSS files */
.btn-primary { background-color: var(--primary-color); }
.card { border-radius: var(--border-radius); }
```

#### 🔧 Implementation Workflow:
1. Create static files structure if not exists
2. Configure `STATICFILES_DIRS` in settings.py
3. Extract existing styles from templates to CSS files
4. Update templates to load static files with `{% load static %}`
5. Test changes and ensure proper loading

**EXPLAIN TO USER**: This approach ensures maintainability, better performance, and professional code organization. Changes are easier to manage and reuse across the project.