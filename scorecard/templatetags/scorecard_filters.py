"""
Filtros personalizados para templates del sistema Score Card
"""
from django import template

register = template.Library()


# =============================================================================
# DICCIONARIOS DE COLORES PARA SUCURSALES Y ÁREAS
# Estos diccionarios definen los colores personalizados para cada sucursal y área
# =============================================================================

# Colores para Sucursales
COLORES_SUCURSALES = {
    # Sucursales principales
    'satelite': '#0d6efd',      # Azul Bootstrap
    'satélite': '#0d6efd',      # Azul Bootstrap (con acento)
    'drop off sur': '#6f42c1',      # Morado
    'drop-off': '#6f42c1',      # Morado (con guión)
    'guadalajara': "#B12A2A",        # rojo vino
    'monterrey': "#b97d4b",        # Naranja
    'sur': '#dc3545',           # Rojo
    'norte': '#20c997',         # Turquesa
    'bodega': '#6c757d',        # Gris
    
    # Color por defecto para sucursales no definidas
    'default': '#6c757d',       # Gris
}

# Colores para Áreas
COLORES_AREAS = {
    # Áreas de calidad y control
    'calidad': "#66b0db",           # azul claro
    'control de calidad': '#6c757d', # Gris
    
    # Áreas técnicas
    'laboratorio oow': '#e83e8c',   # Rosa
    'laboratorio': '#e83e8c',       # Rosa
    'oow': '#e83e8c',               # Rosa
    'laboratorio lenovo': '#fd7e14',            # Naranja
    'hp': '#0dcaf0',                # Cian
    'laboratorio dell': '#0d6efd',              # Azul
    
    # Áreas administrativas
    'frontdesk': '#20c997',         # Turquesa
    'recepción': '#20c997',         # Turquesa
    'carry in': '#ffc107',           # Amarillo
    'almacén': '#ffc107',           # Amarillo
    'gerencia': '#6610f2',    # Índigo
    'administración': '#6610f2',    # Índigo
    
    # Áreas operativas
    'refacciones': '#d63384',       # Rosa oscuro
    'empaque': '#198754',           # Verde
    'soporte': '#0d6efd',           # Azul
    'ventas': '#dc3545',            # Rojo
    
    # Color por defecto para áreas no definidas
    'default': '#6c757d',           # Gris
}

# Colores para Grado de Severidad
COLORES_SEVERIDAD = {
    'critico': '#dc3545',      # Rojo - Crítico (máxima prioridad)
    'crítico': '#dc3545',      # Rojo - Crítico (con acento)
    'alto': '#fd7e14',         # Naranja - Alto (requiere atención inmediata)
    'medio': '#ffc107',        # Amarillo - Medio (atención moderada)
    'bajo': '#198754',         # Verde - Bajo (menor impacto)
    
    # Color por defecto
    'default': '#6c757d',      # Gris
}


@register.filter(name='text_color_for_bg')
def text_color_for_bg(hex_color):
    """
    Calcula el color de texto óptimo (blanco o negro) para un color de fondo dado.
    
    Este filtro recibe un color en formato hexadecimal (ejemplo: #FF5733)
    y calcula si el texto debe ser blanco (#ffffff) o negro (#000000)
    para tener el mejor contraste posible.
    
    ¿Cómo funciona?
    - Convierte el color hexadecimal a valores RGB (Rojo, Verde, Azul)
    - Calcula la "luminosidad" del color usando una fórmula estándar
    - Si el color es claro (luminosidad > 128), usa texto negro
    - Si el color es oscuro (luminosidad <= 128), usa texto blanco
    
    Args:
        hex_color (str): Color en formato hexadecimal (ej: #FF5733 o FF5733)
    
    Returns:
        str: Color de texto recomendado ('#ffffff' o '#000000')
    
    Ejemplo de uso en template:
        {% load scorecard_filters %}
        <span style="background-color: {{ categoria.color }}; 
                     color: {{ categoria.color|text_color_for_bg }};">
            {{ categoria.nombre }}
        </span>
    """
    # Si el color no está definido o está vacío, retornar blanco por defecto
    if not hex_color:
        return '#ffffff'
    
    # Remover el símbolo # si está presente
    hex_color = hex_color.lstrip('#')
    
    # Validar que sea un color hexadecimal válido (6 caracteres)
    if len(hex_color) != 6:
        return '#ffffff'
    
    try:
        # Convertir valores hexadecimales a RGB
        # hex_color[0:2] = Rojo (Red)
        # hex_color[2:4] = Verde (Green)
        # hex_color[4:6] = Azul (Blue)
        r = int(hex_color[0:2], 16)  # Convertir los primeros 2 caracteres de hex a decimal
        g = int(hex_color[2:4], 16)  # Convertir los siguientes 2 caracteres de hex a decimal
        b = int(hex_color[4:6], 16)  # Convertir los últimos 2 caracteres de hex a decimal
        
        # Calcular luminosidad usando la fórmula estándar de percepción humana
        # Esta fórmula pondera los colores de forma similar a cómo el ojo humano
        # percibe el brillo: el verde afecta más que el rojo, y el rojo más que el azul
        luminosidad = (0.299 * r + 0.587 * g + 0.114 * b)
        
        # Si la luminosidad es mayor a 128 (escala de 0-255), el fondo es claro
        # entonces usamos texto negro para mejor contraste
        # Si es menor o igual a 128, el fondo es oscuro, usamos texto blanco
        return '#000000' if luminosidad > 128 else '#ffffff'
    
    except (ValueError, TypeError):
        # Si hay algún error al procesar el color, retornar blanco por seguridad
        return '#ffffff'


@register.filter(name='get_color_brightness')
def get_color_brightness(hex_color):
    """
    Calcula el brillo de un color en una escala de 0-255.
    
    Este filtro auxiliar puede usarse para otros propósitos como
    ajustar opacidades o efectos basados en el brillo del color.
    
    Args:
        hex_color (str): Color en formato hexadecimal
    
    Returns:
        int: Valor de brillo (0-255), o 128 si hay error
    """
    if not hex_color:
        return 128
    
    hex_color = hex_color.lstrip('#')
    
    if len(hex_color) != 6:
        return 128
    
    try:
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        
        # Retornar el valor de luminosidad calculado
        return int(0.299 * r + 0.587 * g + 0.114 * b)
    
    except (ValueError, TypeError):
        return 128


@register.filter(name='color_sucursal')
def color_sucursal(nombre_sucursal):
    """
    Obtiene el color asignado para una sucursal específica.
    
    Este filtro busca el color correspondiente a una sucursal en el diccionario
    COLORES_SUCURSALES. Si no encuentra coincidencia exacta, devuelve el color
    por defecto.
    
    ¿Cómo funciona?
    - Convierte el nombre de la sucursal a minúsculas para hacer búsqueda sin importar mayúsculas
    - Busca el nombre en el diccionario de colores
    - Si encuentra coincidencia, retorna el color hexadecimal
    - Si no encuentra, retorna el color por defecto (gris)
    
    Args:
        nombre_sucursal (str): Nombre de la sucursal (ej: "Satélite", "Drop Off")
    
    Returns:
        str: Color en formato hexadecimal (ej: '#0d6efd')
    
    Ejemplo de uso en template:
        {% load scorecard_filters %}
        <span class="badge" 
              style="background-color: {{ empleado.sucursal.nombre|color_sucursal }}; 
                     color: {{ empleado.sucursal.nombre|color_sucursal|text_color_for_bg }};">
            {{ empleado.sucursal.nombre }}
        </span>
    """
    if not nombre_sucursal:
        return COLORES_SUCURSALES['default']
    
    # Convertir a minúsculas y eliminar espacios extras para búsqueda
    nombre_limpio = str(nombre_sucursal).lower().strip()
    
    # Buscar el color en el diccionario
    return COLORES_SUCURSALES.get(nombre_limpio, COLORES_SUCURSALES['default'])


@register.filter(name='color_area')
def color_area(nombre_area):
    """
    Obtiene el color asignado para un área específica.
    
    Este filtro busca el color correspondiente a un área en el diccionario
    COLORES_AREAS. Si no encuentra coincidencia exacta, devuelve el color
    por defecto.
    
    ¿Cómo funciona?
    - Convierte el nombre del área a minúsculas para hacer búsqueda sin importar mayúsculas
    - Busca el nombre en el diccionario de colores
    - Si encuentra coincidencia, retorna el color hexadecimal
    - Si no encuentra, retorna el color por defecto (gris)
    
    Args:
        nombre_area (str): Nombre del área (ej: "Calidad", "Laboratorio OOW", "Lenovo")
    
    Returns:
        str: Color en formato hexadecimal (ej: '#6c757d')
    
    Ejemplo de uso en template:
        {% load scorecard_filters %}
        <span class="badge" 
              style="background-color: {{ empleado.area|color_area }}; 
                     color: {{ empleado.area|color_area|text_color_for_bg }};">
            {{ empleado.area }}
        </span>
    """
    if not nombre_area:
        return COLORES_AREAS['default']
    
    # Convertir a minúsculas y eliminar espacios extras para búsqueda
    nombre_limpio = str(nombre_area).lower().strip()
    
    # Buscar el color en el diccionario
    return COLORES_AREAS.get(nombre_limpio, COLORES_AREAS['default'])


@register.filter(name='color_severidad')
def color_severidad(grado_severidad):
    """
    Obtiene el color asignado para un grado de severidad específico.
    
    Este filtro busca el color correspondiente a un nivel de severidad en el diccionario
    COLORES_SEVERIDAD. Si no encuentra coincidencia exacta, devuelve el color por defecto.
    
    ¿Cómo funciona?
    - Convierte el grado de severidad a minúsculas para hacer búsqueda sin importar mayúsculas
    - Busca el valor en el diccionario de colores
    - Si encuentra coincidencia, retorna el color hexadecimal
    - Si no encuentra, retorna el color por defecto (gris)
    
    Args:
        grado_severidad (str): Grado de severidad (ej: "Crítico", "Alto", "Medio", "Bajo")
    
    Returns:
        str: Color en formato hexadecimal (ej: '#dc3545')
    
    Ejemplo de uso en template:
        {% load scorecard_filters %}
        <span class="badge" 
              style="background-color: {{ incidencia.grado_severidad|color_severidad }}; 
                     color: {{ incidencia.grado_severidad|color_severidad|text_color_for_bg }};">
            {{ incidencia.get_grado_severidad_display }}
        </span>
    """
    if not grado_severidad:
        return COLORES_SEVERIDAD['default']
    
    # Convertir a minúsculas y eliminar espacios extras para búsqueda
    severidad_limpia = str(grado_severidad).lower().strip()
    
    # Buscar el color en el diccionario
    return COLORES_SEVERIDAD.get(severidad_limpia, COLORES_SEVERIDAD['default'])
