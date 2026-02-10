"""
Script para asignar grupos a empleados existentes basado en su rol

SOPORTE MULTI-PAIS (v2.0):
    Ahora soporta un parametro db_alias para asignar grupos en la
    base de datos de cualquier pais.

FORMA RECOMENDADA DE EJECUTAR:
    python scripts/manage_grupos.py                      # Menu interactivo
    python scripts/manage_grupos.py --database=argentina  # Argentina directa

O directamente:
    python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/asignar_grupos_empleados.py').read())"

IMPORTANTE: Ejecutar desde el directorio raiz del proyecto
"""

from django.contrib.auth.models import Group
from inventario.models import Empleado


def asignar_grupos_empleados(db_alias='default'):
    """
    Asigna grupos de Django a usuarios existentes segun el rol del empleado.

    EXPLICACION PARA PRINCIPIANTES:
    Cada empleado tiene un campo 'rol' (supervisor, tecnico, etc.).
    Esta funcion busca el grupo de Django correspondiente a ese rol
    y lo asigna al usuario del empleado.

    SOPORTE MULTI-PAIS (v2.0):
    Antes buscaba empleados y grupos solo en la BD de Mexico.
    Ahora recibe db_alias para operar en cualquier BD.

    Uso:
        asignar_grupos_empleados()                 # Mexico (default)
        asignar_grupos_empleados('argentina')      # Argentina

    Args:
        db_alias: Alias de la BD ('default', 'mexico', 'argentina', etc.)
    """

    # Obtener nombre legible del pais para los mensajes
    nombres_bd = {
        'default': 'Mexico (default)',
        'mexico': 'Mexico',
        'argentina': 'Argentina',
    }
    nombre_bd = nombres_bd.get(db_alias, db_alias)

    print("\n" + "="*70)
    print(f"ASIGNACION DE GRUPOS A EMPLEADOS — {nombre_bd}")
    print(f"Base de datos: {db_alias}")
    print("="*70 + "\n")

    # Mapeo de roles de empleado a nombres de grupos de Django
    #
    # EXPLICACION PARA PRINCIPIANTES:
    # El campo 'rol' del modelo Empleado guarda valores como 'supervisor',
    # 'tecnico', etc. Los nombres de los grupos en Django son 'Supervisor',
    # 'Técnico', etc. Este diccionario conecta uno con otro.
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

    # Obtener empleados que tienen usuario del sistema EN LA BD ESPECIFICADA
    #
    # EXPLICACION PARA PRINCIPIANTES:
    # .using(db_alias) le dice a Django: "busca en esta BD especifica".
    # Sin .using(), siempre busca en 'default' (Mexico).
    empleados_con_usuario = Empleado.objects.using(db_alias).filter(user__isnull=False)

    print(f"  Total de empleados con usuario: {empleados_con_usuario.count()}\n")

    actualizado = 0
    sin_grupo = 0

    for empleado in empleados_con_usuario:
        nombre_grupo = rol_a_grupo.get(empleado.rol)

        if nombre_grupo:
            try:
                # Buscar el grupo EN LA MISMA BD del empleado
                grupo = Group.objects.using(db_alias).get(name=nombre_grupo)

                # Limpiar grupos actuales del usuario
                # NOTA: user.groups es una relacion M2M que Django maneja
                # a traves de la tabla auth_user_groups
                empleado.user.groups.clear()

                # Asignar el grupo correspondiente
                empleado.user.groups.add(grupo)

                print(f"  {empleado.nombre_completo}: Asignado a grupo '{nombre_grupo}'")
                actualizado += 1

            except Group.DoesNotExist:
                print(f"  {empleado.nombre_completo}: Grupo '{nombre_grupo}' no existe")
                print(f"     Ejecuta primero: python scripts/manage_grupos.py --database={db_alias}")
                sin_grupo += 1
        else:
            print(f"  {empleado.nombre_completo}: Rol '{empleado.rol}' no tiene grupo asignado")
            sin_grupo += 1

    print("\n" + "="*70)
    print(f"RESUMEN — {nombre_bd}")
    print("="*70)
    print(f"  Empleados actualizados: {actualizado}")
    print(f"  Empleados sin grupo asignado: {sin_grupo}")
    print("="*70 + "\n")


if __name__ == '__main__':
    asignar_grupos_empleados()
