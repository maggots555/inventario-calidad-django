"""
Script para asignar grupos a empleados existentes basado en su rol

FORMA RECOMENDADA DE EJECUTAR:
    python scripts/manage_grupos.py

O directamente:
    python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/asignar_grupos_empleados.py').read())"

IMPORTANTE: Ejecutar desde el directorio raíz del proyecto
"""

from django.contrib.auth.models import Group
from inventario.models import Empleado

def asignar_grupos_empleados():
    """
    Asigna grupos de Django a usuarios existentes según el rol del empleado
    """
    
    print("\n" + "="*70)
    print("ASIGNACIÓN DE GRUPOS A EMPLEADOS EXISTENTES")
    print("="*70 + "\n")
    
    # Mapeo de roles de empleado a nombres de grupos de Django
    rol_a_grupo = {
        'supervisor': 'Supervisor',
        'inspector': 'Inspector',
        'dispatcher': 'Dispatcher',
        'compras': 'Compras',
        'recepcionista': 'Recepcionista',
        'gerente_operacional': 'Gerente Operacional',
        'gerente_general': 'Gerente General',
        'tecnico': 'Técnico',
        'almacenista': 'Almacenista',
    }
    
    # Obtener empleados que tienen usuario del sistema
    empleados_con_usuario = Empleado.objects.filter(user__isnull=False)
    
    print(f"📊 Total de empleados con usuario: {empleados_con_usuario.count()}\n")
    
    actualizado = 0
    sin_grupo = 0
    
    for empleado in empleados_con_usuario:
        nombre_grupo = rol_a_grupo.get(empleado.rol)
        
        if nombre_grupo:
            try:
                grupo = Group.objects.get(name=nombre_grupo)
                
                # Limpiar grupos actuales del usuario
                empleado.user.groups.clear()
                
                # Asignar el grupo correspondiente
                empleado.user.groups.add(grupo)
                
                print(f"✅ {empleado.nombre_completo}: Asignado a grupo '{nombre_grupo}'")
                actualizado += 1
                
            except Group.DoesNotExist:
                print(f"⚠️  {empleado.nombre_completo}: Grupo '{nombre_grupo}' no existe")
                sin_grupo += 1
        else:
            print(f"❌ {empleado.nombre_completo}: Rol '{empleado.rol}' no tiene grupo asignado")
            sin_grupo += 1
    
    print("\n" + "="*70)
    print("RESUMEN")
    print("="*70)
    print(f"✅ Empleados actualizados: {actualizado}")
    print(f"⚠️  Empleados sin grupo asignado: {sin_grupo}")
    print("="*70 + "\n")


if __name__ == '__main__':
    asignar_grupos_empleados()
