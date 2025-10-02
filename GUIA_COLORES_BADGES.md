# 🎨 Guía de Colores Personalizados para Badges

## 📋 Descripción General

Este sistema permite asignar colores personalizados a badges de **Sucursales** y **Áreas** en todo el proyecto Django. Los colores se definen centralmente en un archivo de filtros y se calculan automáticamente para garantizar la mejor legibilidad del texto.

---

## 🗂️ Ubicación de Archivos

### Archivo Principal de Configuración
```
scorecard/templatetags/scorecard_filters.py
```
Este archivo contiene:
- Diccionarios de colores para sucursales y áreas
- Filtros personalizados de Django
- Lógica de cálculo de contraste de color

### Archivos CSS Relacionados
```
static/css/components.css
```
Contiene estilos para `.badge-categoria` con efectos hover y sombras.

---

## 🎨 Colores Actuales Configurados

### Sucursales

| Sucursal | Color | Código Hex |
|----------|-------|------------|
| Satélite | 🔵 Azul | `#0d6efd` |
| Drop Off | 🟣 Morado | `#6f42c1` |
| Matriz | 🟢 Verde | `#198754` |
| Centro | 🟠 Naranja | `#fd7e14` |
| Sur | 🔴 Rojo | `#dc3545` |
| Norte | 🟦 Turquesa | `#20c997` |
| Bodega | ⚫ Gris | `#6c757d` |
| **Por defecto** | ⚫ Gris | `#6c757d` |

### Áreas

| Área | Color | Código Hex |
|------|-------|------------|
| Calidad / Control de Calidad | ⚫ Gris | `#6c757d` |
| Laboratorio OOW / Laboratorio | 🩷 Rosa | `#e83e8c` |
| Lenovo | 🟠 Naranja | `#fd7e14` |
| HP | 🔷 Cian | `#0dcaf0` |
| Dell | 🔵 Azul | `#0d6efd` |
| Recepción | 🟦 Turquesa | `#20c997` |
| Almacén | 🟡 Amarillo | `#ffc107` |
| Administración | 🟪 Índigo | `#6610f2` |
| Refacciones | 🌸 Rosa oscuro | `#d63384` |
| Empaque | 🟢 Verde | `#198754` |
| Soporte | 🔵 Azul | `#0d6efd` |
| Ventas | 🔴 Rojo | `#dc3545` |
| **Por defecto** | ⚫ Gris | `#6c757d` |

---

## 📝 Cómo Usar en Templates

### 1. Cargar los Filtros

Al inicio del template HTML, agrega:
```django
{% load scorecard_filters %}
```

### 2. Badge de Sucursal con Color Dinámico

```django
<span class="badge badge-categoria" 
      style="background-color: {{ empleado.sucursal.nombre|color_sucursal }}; 
             color: {{ empleado.sucursal.nombre|color_sucursal|text_color_for_bg }};">
    <i class="bi bi-building"></i> {{ empleado.sucursal.nombre }}
</span>
```

### 3. Badge de Área con Color Dinámico

```django
<span class="badge badge-categoria" 
      style="background-color: {{ empleado.area|color_area }}; 
             color: {{ empleado.area|color_area|text_color_for_bg }};">
    {{ empleado.area }}
</span>
```

---

## 🔧 Cómo Agregar o Modificar Colores

### Para Agregar una Nueva Sucursal

1. Abre `scorecard/templatetags/scorecard_filters.py`
2. Encuentra el diccionario `COLORES_SUCURSALES`
3. Agrega una nueva entrada:

```python
COLORES_SUCURSALES = {
    # ... colores existentes ...
    'nombre_sucursal': '#CODIGO_HEX',  # Descripción del color
}
```

**Ejemplo:**
```python
COLORES_SUCURSALES = {
    # ... otros colores ...
    'plaza patria': '#17a2b8',  # Azul claro
    'guadalajara': '#fd7e14',   # Naranja
}
```

### Para Agregar una Nueva Área

1. Abre `scorecard/templatetags/scorecard_filters.py`
2. Encuentra el diccionario `COLORES_AREAS`
3. Agrega una nueva entrada:

```python
COLORES_AREAS = {
    # ... colores existentes ...
    'nombre_area': '#CODIGO_HEX',  # Descripción del color
}
```

**Ejemplo:**
```python
COLORES_AREAS = {
    # ... otros colores ...
    'recursos humanos': '#6610f2',  # Índigo
    'finanzas': '#ffc107',          # Amarillo
}
```

---

## 🎨 Paleta de Colores Bootstrap Recomendados

Para mantener consistencia visual, usa estos colores de Bootstrap:

| Color | Código Hex | Uso Recomendado |
|-------|------------|-----------------|
| Azul | `#0d6efd` | Áreas técnicas, principal |
| Índigo | `#6610f2` | Administrativo |
| Morado | `#6f42c1` | Especial/Premium |
| Rosa | `#e83e8c` | Laboratorios |
| Rojo | `#dc3545` | Urgente/Crítico |
| Naranja | `#fd7e14` | Atención/Alerta |
| Amarillo | `#ffc107` | Advertencia |
| Verde | `#198754` | Exitoso/Activo |
| Turquesa | `#20c997` | Información |
| Cian | `#0dcaf0` | Soporte/Ayuda |
| Gris | `#6c757d` | Neutral/Por defecto |

---

## ⚙️ Cómo Funciona el Sistema

### 1. Búsqueda de Color
- El sistema convierte los nombres a **minúsculas** antes de buscar
- Ignora espacios extras al inicio y final
- Permite variaciones (ej: "Satélite" y "satelite" funcionan igual)

### 2. Cálculo Automático del Color de Texto
El filtro `text_color_for_bg` calcula automáticamente si el texto debe ser **blanco** o **negro** usando:

```python
luminosidad = (0.299 * R + 0.587 * G + 0.114 * B)
```

- Si luminosidad > 128 → texto **negro** (#000000)
- Si luminosidad ≤ 128 → texto **blanco** (#ffffff)

Esto garantiza siempre la mejor legibilidad posible.

### 3. Color Por Defecto
Si no se encuentra un color definido, se usa el color **gris** (`#6c757d`) como respaldo.

---

## 🧪 Ejemplos Prácticos

### Ejemplo 1: Badge Simple
```django
{% load scorecard_filters %}

<span class="badge badge-categoria" 
      style="background-color: {{ area_nombre|color_area }}; 
             color: {{ area_nombre|color_area|text_color_for_bg }};">
    {{ area_nombre }}
</span>
```

### Ejemplo 2: Lista de Empleados con Colores
```django
{% load scorecard_filters %}

<table>
    {% for empleado in empleados %}
    <tr>
        <td>{{ empleado.nombre_completo }}</td>
        <td>
            <span class="badge badge-categoria" 
                  style="background-color: {{ empleado.area|color_area }}; 
                         color: {{ empleado.area|color_area|text_color_for_bg }};">
                {{ empleado.area }}
            </span>
        </td>
        <td>
            <span class="badge badge-categoria" 
                  style="background-color: {{ empleado.sucursal.nombre|color_sucursal }}; 
                         color: {{ empleado.sucursal.nombre|color_sucursal|text_color_for_bg }};">
                {{ empleado.sucursal.nombre }}
            </span>
        </td>
    </tr>
    {% endfor %}
</table>
```

---

## 🚀 Reinicio del Servidor

**IMPORTANTE:** Después de modificar el archivo `scorecard_filters.py`, **DEBES reiniciar el servidor Django**:

```bash
# Detener el servidor (Ctrl + C)
# Luego reiniciar:
python manage.py runserver 0.0.0.0:8000
```

---

## 🐛 Solución de Problemas

### Error: "scorecard_filters is not a registered tag library"
**Solución:** Reinicia el servidor Django completamente.

### Los colores no se aplican
**Verificar:**
1. ¿Cargaste `{% load scorecard_filters %}` al inicio del template?
2. ¿El nombre en el diccionario coincide exactamente (ignorando mayúsculas)?
3. ¿Reiniciaste el servidor después de hacer cambios?

### El texto no se lee bien
El sistema debería calcularlo automáticamente, pero si hay problemas:
- Verifica que estés usando `|text_color_for_bg` después del filtro de color
- Asegúrate de que el código hexadecimal sea válido (6 caracteres)

---

## 📚 Recursos Adicionales

- **Documentación Django Filters:** https://docs.djangoproject.com/en/stable/howto/custom-template-tags/
- **Bootstrap Colors:** https://getbootstrap.com/docs/5.3/customize/color/
- **Calculadora de Contraste:** https://webaim.org/resources/contrastchecker/

---

## ✅ Templates Actualizados

Los siguientes templates ya están usando el sistema de colores dinámicos:

- ✅ `scorecard/templates/scorecard/lista_incidencias.html` - Categorías de incidencias
- ✅ `inventario/templates/inventario/lista_empleados.html` - Sucursales y áreas

---

**Fecha de última actualización:** Octubre 2, 2025
**Versión:** 1.0
