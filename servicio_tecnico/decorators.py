"""
Decoradores reutilizables de Servicio Técnico.

EXPLICACIÓN PARA PRINCIPIANTES:
Antes vivían al inicio de views.py (~20 000 líneas). Los sacamos aquí para
poder modularizar vistas sin romper permisos ni el cache de dashboards.

Efectos secundarios:
- permission_required_with_message redirige a la página de acceso denegado.
- cache_page_dashboard guarda HTML de dashboards en Redis (TTL de settings).
"""

from functools import wraps

from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.cache import cache_page


# ===== CACHE DE DASHBOARDS (Redis) =====
# EXPLICACIÓN PARA PRINCIPIANTES:
# cache_page() guarda la respuesta HTML completa en Redis durante X segundos.
# La segunda vez que alguien abre la misma URL, Django la sirve desde Redis
# sin ejecutar la vista (sin consultar BD, sin generar gráficas Plotly).
#
# cache_page cachea POR URL COMPLETA, así que:
#   /dashboard/?fecha_inicio=2025-01-01  → cache separado
#   /dashboard/?fecha_inicio=2025-06-01  → otro cache separado
#
# IMPORTANTE: cache_page debe ir DESPUÉS de @login_required para que
# cada usuario autenticado tenga su propio cache (no mezclar datos).
#
# CACHE_TTL_DASHBOARD viene de settings.py (10 minutos por defecto).
cache_page_dashboard = cache_page(getattr(settings, 'CACHE_TTL_DASHBOARD', 600))


def permission_required_with_message(perm, message=None):
    """
    Verifica un permiso de Django y, si falta, redirige a acceso denegado.

    Args:
        perm (str): Permiso en formato 'app.codename'
            (ej: 'servicio_tecnico.add_ordenservicio').
        message (str | None): Mensaje personalizado de error (opcional).

    Returns:
        Callable: Decorador listo para usar sobre una vista.

    Efectos secundarios:
        Si el usuario no tiene el permiso, responde con redirect a
        servicio_tecnico:acceso_denegado_servicio_tecnico (no ejecuta la vista).

    Uso:
        @login_required
        @permission_required_with_message('servicio_tecnico.add_ordenservicio')
        def crear_orden(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Paso 1: comprobar permiso del usuario autenticado
            if not request.user.has_perm(perm):
                error_msg = message or 'No tienes permisos para realizar esta acción.'
                # Paso 2: redirigir con mensaje y permiso en query string
                return redirect(
                    f"{reverse('servicio_tecnico:acceso_denegado_servicio_tecnico')}"
                    f"?mensaje={error_msg}&permiso={perm}"
                )
            # Paso 3: permiso OK → ejecutar la vista original
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
