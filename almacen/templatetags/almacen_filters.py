"""
Template filters personalizados para la app Almacén

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Los template filters son funciones de Python que transforman datos
en las plantillas de Django. Se usan con la sintaxis: {{ valor|filtro }}

Por ejemplo: {{ 5|mul:100 }} → devuelve 500

Django incluye filtros básicos como |floatformat, |date, etc.
Este archivo define filtros personalizados específicos para almacén.
"""

from django import template

# Registrar el módulo de template tags
register = template.Library()


@register.filter(name='mul')
def mul(value, arg):
    """
    Multiplica dos valores
    
    Uso en template:
        {{ cantidad|mul:precio }}
    
    Args:
        value: Primer número (ej: cantidad = 5)
        arg: Segundo número (ej: precio = 100)
    
    Returns:
        Resultado de la multiplicación (ej: 500)
    
    EXPLICACIÓN:
    - @register.filter: Registra la función como filtro de template
    - name='mul': El nombre que se usa en el template
    - try/except: Maneja errores si los valores no son números
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
