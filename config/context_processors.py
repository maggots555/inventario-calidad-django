# config/context_processors.py
"""
EXPLICACIÓN PARA PRINCIPIANTES:
================================
Un "context processor" en Django es una función que agrega variables
automáticamente a TODOS los templates. Sin esto, tendrías que hacer:

    # En CADA vista:
    return render(request, 'mi_template.html', {
        'pais_nombre': 'México',
        'moneda_simbolo': '$',
        ... (repetir en las 100+ vistas del sistema)
    })

Con un context processor, esas variables están disponibles en
TODOS los templates automáticamente. Solo necesitas registrar
esta función en TEMPLATES → OPTIONS → context_processors en settings.py.

Uso en templates:
    <title>SigmaSystem - {{ pais_nombre }}</title>
    <span>{{ empresa_nombre }}</span>
    <p>Total: {{ moneda_simbolo }}{{ total }}</p>
"""

from .paises_config import PAIS_DEFAULT, get_pais_config, get_todos_los_paises


def pais_context(request):
    """
    Agrega variables del país activo al contexto de todos los templates.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Django llama esta función automáticamente antes de renderizar
    cualquier template. El diccionario que retornamos se "fusiona"
    con el contexto de la vista.

    Args:
        request: El request HTTP actual

    Returns:
        dict con variables disponibles en todos los templates
    """
    # Obtener configuración del país (el middleware ya la puso en request)
    pais_config = getattr(request, 'pais_config', None)

    # Fallback si el middleware no se ejecutó (ej: página de error 500)
    if pais_config is None:
        pais_config = get_pais_config(PAIS_DEFAULT)

    return {
        # Información básica del país
        'pais_codigo': pais_config.get('codigo', ''),
        'pais_nombre': pais_config.get('nombre', ''),
        'pais_subdominio': getattr(request, 'pais_subdominio', PAIS_DEFAULT),

        # Moneda (para mostrar en templates)
        'moneda_simbolo': pais_config.get('moneda_simbolo', '$'),
        'moneda_codigo': pais_config.get('moneda_codigo', ''),

        # Empresa (para headers, footers, emails)
        'empresa_nombre': pais_config.get('empresa_nombre', ''),
        'empresa_nombre_corto': pais_config.get('empresa_nombre_corto', ''),
        'empresa_direccion': pais_config.get('empresa_direccion', ''),
        'empresa_telefono': pais_config.get('empresa_telefono', ''),

        # URLs
        'pais_url_base': pais_config.get('url_base', ''),
        'pais_dominio': pais_config.get('dominio', ''),

        # Lista de todos los países (para selector de país en el navbar)
        'todos_los_paises': get_todos_los_paises(),

        # Config completa (para acceso avanzado en templates)
        'pais_config': pais_config,
    }
