"""
Decoradores reutilizables del módulo Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Antes vivía al inicio de views.py (~7400 líneas). Lo sacamos aquí para
poder modularizar vistas sin romper permisos ni urls.py.

Efectos secundarios:
- permission_required_with_message redirige a la página de acceso denegado
  del módulo Almacén si el usuario no tiene el permiso.
"""

from functools import wraps

from django.shortcuts import redirect
from django.urls import reverse


def permission_required_with_message(perm, message=None):
    """
    Decorador personalizado para verificar permisos con redirección a página de acceso denegado.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este decorador verifica que el usuario tenga el permiso requerido.
    Si NO lo tiene, redirige a una página amigable explicando el problema.
    
    Args:
        perm (str): Permiso requerido en formato 'app.permiso_modelo'
                   Ejemplo: 'almacen.view_productoalmacen'
        message (str, opcional): Mensaje personalizado de error
    
    Uso:
        @login_required
        @permission_required_with_message('almacen.view_productoalmacen')
        def lista_productos(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Verificar si el usuario tiene el permiso
            if not request.user.has_perm(perm):
                # Mensaje personalizado o genérico
                error_msg = message or 'No tienes permisos para realizar esta acción.'
                
                # Redirigir a la página de acceso denegado con parámetros
                return redirect(
                    f"{reverse('almacen:acceso_denegado_almacen')}?mensaje={error_msg}&permiso={perm}"
                )
            
            # Si tiene permiso, ejecutar la vista normalmente
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
