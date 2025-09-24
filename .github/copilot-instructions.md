# Copilot Instructions for Django Projects

## Project Overview
These are Django 5.2.5 projects following Django best practices with proper separation between project configuration and application logic. Both projects demonstrate different architectural approaches and evolution of best practices.

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
- **EXPLAIN TO USER**: When creating or modifying models, explain what each field type does (CharField, IntegerField, etc.), what the Meta class is for, and why `__str__()` method is important for displaying objects in admin and templates
- **Example**:
```python
# Este es un modelo de Django - piensa en él como una plantilla para crear objetos en la base de datos
class Producto(models.Model):
    # ESTADO_CHOICES es una tupla que define las opciones válidas para el campo estado_calidad
    ESTADO_CHOICES = [('bueno', 'Bueno'), ('regular', 'Regular'), ('malo', 'Malo')]
    
    # CharField: Campo de texto con longitud máxima de 100 caracteres
    nombre = models.CharField(max_length=100)
    # TextField: Campo de texto largo, blank=True significa que puede estar vacío
    descripcion = models.TextField(blank=True)
    # PositiveIntegerField: Solo acepta números enteros positivos, default=0 pone 0 como valor inicial
    cantidad = models.PositiveIntegerField(default=0)
    # DateTimeField: Guarda fecha y hora, auto_now_add=True se llena automáticamente al crear el objeto
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    # CharField con choices: El usuario solo puede elegir entre las opciones definidas arriba
    estado_calidad = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='bueno')
    
    # __str__ define cómo se muestra este objeto cuando se imprime o aparece en el admin
    def __str__(self):
        return self.nombre
    
    # Meta class: Configuración adicional del modelo
    class Meta:
        ordering = ['-fecha_ingreso']  # Ordena por fecha más reciente primero (el - significa descendente)
        verbose_name_plural = "Productos"  # Nombre en plural para el admin de Django
```

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
- **EXPLAIN TO USER**: When creating forms, explain what ModelForm does (automatically creates form fields based on your model), what widgets are (how the form fields appear in HTML), and why we use template inheritance (to avoid repeating code)
- **Example form**:
```python
# forms.py - Este archivo define cómo se ven y comportan los formularios
from django import forms
from .models import Producto

# ModelForm: Django crea automáticamente campos de formulario basados en tu modelo
class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto  # Le dice a Django qué modelo usar como base
        fields = ['nombre', 'descripcion', 'cantidad', 'estado_calidad']  # Qué campos incluir
        
        # widgets: Define cómo se ve cada campo en HTML (con clases CSS de Bootstrap)
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre del producto'}),
            'descripcion': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'cantidad': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'estado_calidad': forms.Select(attrs={'class': 'form-control'}),
        }
```

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

## File Organization & Project Structure

### Recommended Directory Structure
```
project_root/
├── config/                    # Project configuration
│   ├── settings.py           # Django settings
│   ├── urls.py              # Main URL routing
│   ├── wsgi.py              # WSGI config
│   └── asgi.py              # ASGI config (optional)
├── apps/                     # Application directory (optional organization)
│   └── app_name/            # Individual apps
│       ├── models.py
│       ├── views.py
│       ├── forms.py
│       ├── urls.py
│       ├── admin.py
│       ├── apps.py
│       ├── tests.py
│       ├── migrations/
│       └── templates/app_name/
├── templates/               # Global templates
│   ├── base.html           # Base template
│   └── components/         # Reusable components
├── static/                 # Global static files
│   ├── css/
│   │   ├── base.css        # Global styles (layout, navbar, footer)
│   │   ├── components.css  # Reusable UI components
│   │   └── forms.css       # Form-specific styling
│   ├── js/
│   │   ├── base.js         # Global JavaScript utilities
│   │   └── feature.js      # Feature-specific JavaScript
│   └── images/
│       ├── logos/
│       └── icons/
├── media/                  # User uploaded files (production)
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
├── .gitignore            # Git ignore rules
├── README.md             # Project documentation
└── manage.py             # Django management script
```

### Configuration Files
- **requirements.txt**: List all Python dependencies with versions
- **.gitignore**: Include Python, Django, IDE, and OS-specific ignore patterns
- **README.md**: Include setup instructions, usage, and project overview
- **.env.example**: Template for environment variables (never commit actual .env)

## Key Dependencies
- Django 5.2.5
- Bootstrap 5.3.2 (CDN)
- Bootstrap Icons (CDN)
- SQLite3 (default database)

## Common Patterns to Follow
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
- **NEVER put CSS/JS directly in templates** - Always use separate static files
- Organize static files by functionality (base.css, components.css, forms.css)
- Use CSS variables for consistent theming and easy maintenance
- Load static files properly with `{% load static %}` and `{% static 'path' %}`
- Structure JavaScript in modular files with clear responsibilities
- Always configure `STATICFILES_DIRS` in settings.py for static file discovery

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