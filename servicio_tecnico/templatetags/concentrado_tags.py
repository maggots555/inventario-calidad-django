"""
Filtros personalizados para el Concentrado Semanal de CIS
==========================================================

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este archivo contiene "filtros" y "tags" de Django que se usan en el template
del concentrado semanal.

El problema que resuelven:
--------------------------
La estructura de datos del concentrado es un diccionario anidado:
    ingreso['DROP OFF']['LENOVO']['Lunes'] = 3

En Django templates NO se puede hacer:
    {{ ingreso.sitio.tipo.dia }}    <-- El punto no funciona con variables dinámicas

Con este filtro podemos hacer:
    {{ ingreso|get_item:sitio|get_item:tipo|get_item:dia }}

Uso en el template:
    {% load concentrado_tags %}
    {{ ingreso|concentrado_valor:sitio|concentrado_valor:tipo|concentrado_valor:dia }}
"""

from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Obtiene el valor de un diccionario por clave dinámica.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El filtro |get_item permite acceder a diccionarios con claves variables.
    En los templates de Django, los corchetes no están disponibles,
    pero sí los filtros personalizados.

    Uso en template:
        {{ mi_diccionario|get_item:mi_variable_clave }}

    Ejemplo:
        {% with clave="Lunes" %}
        {{ datos_ingreso|get_item:clave }}   --> valor de datos_ingreso["Lunes"]
        {% endwith %}

    Args:
        dictionary: Diccionario (o cualquier objeto con método .get)
        key: Clave a buscar

    Returns:
        El valor del diccionario para esa clave, o 0 si no existe
    """
    if dictionary is None:
        return 0
    if isinstance(dictionary, dict):
        return dictionary.get(key, 0)
    return 0


@register.filter(name='concentrado_valor')
def concentrado_valor(obj, key):
    """
    Alias de get_item para uso semántico en el concentrado.
    Idéntico a get_item pero con nombre más descriptivo.

    Args:
        obj: Diccionario
        key: Clave

    Returns:
        Valor o 0
    """
    if obj is None:
        return 0
    if isinstance(obj, dict):
        return obj.get(key, 0)
    return 0


@register.filter(name='zero_dash')
def zero_dash(value):
    """
    Muestra '—' en lugar de 0 para una lectura más limpia de las tablas.

    EXPLICACIÓN PARA PRINCIPIANTES:
    En las tablas del concentrado hay muchas celdas con valor 0.
    Ver columnas llenas de "0" es visualmente ruidoso y dificulta
    identificar los valores relevantes. Este filtro reemplaza el 0
    por un guion largo (—) para que la tabla se vea más limpia.

    Uso en template:
        {{ tipo_data|get_item:dia|zero_dash }}
        → Si el valor es 0  →  muestra "—"
        → Si el valor es 3  →  muestra "3"

    Args:
        value: Número entero o flotante

    Returns:
        '—' si el valor es 0 o falsy, el valor original en caso contrario
    """
    try:
        if int(value) == 0:
            return '—'
        return value
    except (TypeError, ValueError):
        return value


@register.filter(name='celda_clase')
def celda_clase(value):
    """
    Retorna la clase CSS apropiada para una celda numérica.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Para resaltar visualmente las celdas que tienen datos reales (> 0)
    vs las que están vacías (= 0), este filtro devuelve el nombre de
    la clase CSS que se debe agregar a la celda.

    Uso en template:
        <td class="celda-numero text-center {{ tipo_data|get_item:dia|celda_clase }}">

    Clases retornadas:
        'valor-positivo' → celda con fondo azul claro y texto negrita
        'valor-cero'     → celda con texto gris atenuado

    Args:
        value: Número entero o flotante

    Returns:
        Nombre de clase CSS como string
    """
    try:
        if int(value) > 0:
            return 'valor-positivo'
        return 'valor-cero'
    except (TypeError, ValueError):
        return ''
