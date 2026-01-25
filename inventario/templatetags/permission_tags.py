"""
Template tags personalizados para el sistema de permisos y roles.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Los template tags son funciones Python que puedes usar dentro de las plantillas HTML.
Son útiles para obtener información compleja que no viene directamente en el context.

Este módulo proporciona:
- user_groups: Obtiene los roles/grupos de un usuario
- user_primary_role: Obtiene el rol principal del usuario
"""

from django import template
from django.contrib.auth.models import Group

register = template.Library()


@register.filter(name='user_groups')
def user_groups(user):
    """
    Retorna una lista de nombres de grupos del usuario.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este filtro toma un usuario y retorna todos sus grupos (roles) como una lista.
    
    Uso en template:
        {{ user|user_groups }}
        
    Retorna:
        Lista de nombres de grupos, ej: ['Supervisor', 'Almacenista']
    """
    if not user or not user.is_authenticated:
        return []
    return [group.name for group in user.groups.all()]


@register.filter(name='user_primary_role')
def user_primary_role(user):
    """
    Retorna el rol principal del usuario (primer grupo alfabéticamente).
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Un usuario puede tener múltiples grupos/roles. Este filtro retorna el "principal",
    que es el primero alfabéticamente. Si el usuario no tiene grupos, retorna un mensaje.
    
    Uso en template:
        {{ user|user_primary_role }}
        
    Retorna:
        String con el nombre del grupo principal, ej: 'Almacenista'
        O 'Sin rol asignado' si no tiene grupos
    """
    if not user or not user.is_authenticated:
        return 'Usuario no autenticado'
    
    groups = user.groups.order_by('name')
    if groups.exists():
        return groups.first().name
    else:
        # Si es superusuario pero no tiene grupos
        if user.is_superuser:
            return 'Superusuario'
        elif user.is_staff:
            return 'Staff'
        else:
            return 'Sin rol asignado'


@register.filter(name='user_roles_display')
def user_roles_display(user):
    """
    Retorna los roles del usuario en formato legible para mostrar.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Este filtro formatea los roles del usuario de forma bonita para mostrar
    en el navbar. Si tiene múltiples roles, los une con " • ".
    
    Uso en template:
        {{ user|user_roles_display }}
        
    Retorna:
        'Supervisor • Almacenista' (si tiene 2 roles)
        'Técnico' (si tiene 1 rol)
        'Superusuario' (si es superusuario sin grupos)
        'Sin rol asignado' (si no tiene roles)
    """
    if not user or not user.is_authenticated:
        return 'Usuario no autenticado'
    
    groups = user.groups.order_by('name')
    
    if groups.exists():
        # Si tiene grupos, unirlos con •
        return ' • '.join([group.name for group in groups])
    else:
        # Si no tiene grupos pero es superusuario/staff
        if user.is_superuser:
            return 'Superusuario'
        elif user.is_staff:
            return 'Staff'
        else:
            return 'Sin rol asignado'


@register.simple_tag
def user_has_any_role(user, *role_names):
    """
    Verifica si el usuario tiene alguno de los roles especificados.
    
    EXPLICACIÓN PARA PRINCIPIANTES:
    --------------------------------
    Esta tag verifica si el usuario pertenece a alguno de los grupos especificados.
    Útil para mostrar/ocultar elementos en el template según el rol.
    
    Uso en template:
        {% user_has_any_role user 'Supervisor' 'Almacenista' as is_manager %}
        {% if is_manager %}
            <button>Acceso especial</button>
        {% endif %}
        
    Parámetros:
        user: El usuario a verificar
        *role_names: Lista de nombres de roles a verificar
        
    Retorna:
        True si el usuario tiene al menos uno de los roles, False de lo contrario
    """
    if not user or not user.is_authenticated:
        return False
    
    # Superusuarios tienen acceso a todo
    if user.is_superuser:
        return True
    
    user_groups = set(user.groups.values_list('name', flat=True))
    return bool(user_groups.intersection(set(role_names)))
