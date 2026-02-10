"""
Script de gestion de grupos y permisos — Con soporte Multi-Pais

EXPLICACION PARA PRINCIPIANTES:
================================
Este script es el "control central" para manejar grupos y permisos.
Te da un menu donde puedes:
1. Crear los 9 grupos con sus permisos
2. Asignar grupos a empleados segun su rol
3. Ver un resumen de como quedo todo

SOPORTE MULTI-PAIS (v2.0):
    Ahora puedes especificar en que base de datos trabajar.

FORMAS DE EJECUTAR:
    # Menu interactivo (te pregunta que quieres hacer)
    python scripts/manage_grupos.py

    # Crear grupos en Argentina (sin menu, directo)
    python scripts/manage_grupos.py --database=argentina

    # Crear grupos en TODAS las bases de datos
    python scripts/manage_grupos.py --todos

    # Solo ver resumen de una BD
    python scripts/manage_grupos.py --database=argentina --resumen
"""

import os
import sys

# Agregar el directorio raiz al path de Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.contrib.auth.models import Group
from django.conf import settings
from inventario.models import Empleado


# ============================================================================
# FUNCIONES DE UTILIDAD MULTI-PAIS
# ============================================================================

def obtener_bases_de_datos_pais():
    """
    Retorna la lista de aliases de BD configurados para paises.

    EXPLICACION PARA PRINCIPIANTES:
    En settings.py tenemos DATABASES con 'default', 'mexico', 'argentina'.
    'default' y 'mexico' apuntan a la misma BD, asi que solo necesitamos
    'default' y 'argentina' para no duplicar trabajo.

    Returns:
        list[tuple]: Lista de (alias, nombre_legible)
    """
    # Estos son los aliases reales de paises (sin duplicados)
    # 'default' = Mexico, 'argentina' = Argentina
    bases = [('default', 'Mexico (default)')]

    # Agregar las demas BDs configuradas (excluyendo 'default' y 'mexico' que son la misma)
    for alias in settings.DATABASES:
        if alias not in ('default', 'mexico'):
            nombre = alias.capitalize()
            bases.append((alias, nombre))

    return bases


def validar_db_alias(db_alias):
    """
    Verifica que el alias de BD exista en la configuracion.

    Args:
        db_alias: Alias a verificar

    Returns:
        bool: True si existe, False si no
    """
    if db_alias in settings.DATABASES:
        return True
    print(f"\n  Error: Base de datos '{db_alias}' no existe en la configuracion.")
    print(f"  Bases disponibles: {', '.join(settings.DATABASES.keys())}")
    return False


# ============================================================================
# FUNCIONES DEL MENU
# ============================================================================

def mostrar_menu(db_alias='default'):
    """Muestra el menu interactivo con la BD seleccionada."""
    nombres_bd = {
        'default': 'Mexico (default)',
        'mexico': 'Mexico',
        'argentina': 'Argentina',
    }
    nombre_bd = nombres_bd.get(db_alias, db_alias)

    print("\n" + "="*70)
    print(f"GESTION DE GRUPOS Y PERMISOS — {nombre_bd}")
    print("="*70)
    print(f"\nBase de datos activa: {db_alias}")
    print("\n1. Crear grupos y permisos")
    print("2. Actualizar permisos de grupos existentes")
    print("3. Asignar grupos a empleados segun su rol")
    print("4. Ver resumen de grupos y permisos")
    print("5. Cambiar base de datos")
    print("6. Ejecutar en TODAS las bases de datos")
    print("7. Salir")
    print("\n" + "="*70)
    return input("\nSelecciona una opcion (1-7): ")


def crear_grupos(db_alias='default'):
    """Ejecuta la creacion de grupos y permisos en la BD indicada."""
    from scripts.setup_grupos_permisos import setup_grupos_y_permisos
    setup_grupos_y_permisos(db_alias)


def asignar_grupos(db_alias='default'):
    """Ejecuta la asignacion de grupos a empleados en la BD indicada."""
    from scripts.asignar_grupos_empleados import asignar_grupos_empleados
    asignar_grupos_empleados(db_alias)


def ver_resumen(db_alias='default'):
    """
    Muestra resumen de grupos y empleados en la BD indicada.

    EXPLICACION PARA PRINCIPIANTES:
    Esta funcion consulta cuantos grupos hay, cuantos permisos tiene
    cada uno, y que empleados estan asignados a cada grupo.
    Ahora usa .using(db_alias) para consultar la BD correcta.
    """
    nombres_bd = {
        'default': 'Mexico (default)',
        'mexico': 'Mexico',
        'argentina': 'Argentina',
    }
    nombre_bd = nombres_bd.get(db_alias, db_alias)

    print("\n" + "="*70)
    print(f"RESUMEN DE GRUPOS Y PERMISOS — {nombre_bd}")
    print(f"Base de datos: {db_alias}")
    print("="*70 + "\n")

    grupos = Group.objects.using(db_alias).all().order_by('name')

    if not grupos.exists():
        print("  No hay grupos creados. Ejecuta la opcion 1 primero.\n")
        return

    for grupo in grupos:
        # Contar usuarios en este grupo EN ESTA BD
        usuarios_count = grupo.user_set.count()
        permisos_count = grupo.permissions.count()

        print(f"\n  {grupo.name}")
        print(f"     Permisos: {permisos_count}")
        print(f"     Usuarios: {usuarios_count}")

        if usuarios_count > 0:
            empleados = Empleado.objects.using(db_alias).filter(user__groups=grupo)
            for emp in empleados:
                print(f"        - {emp.nombre_completo} ({emp.cargo})")

    print("\n" + "="*70 + "\n")


def ejecutar_en_todas():
    """
    Ejecuta la creacion de grupos y asignacion en TODAS las BDs.

    EXPLICACION PARA PRINCIPIANTES:
    Esta funcion recorre todas las bases de datos de paises
    y ejecuta los mismos pasos en cada una. Asi no tienes que
    ejecutar el script una vez por pais.
    """
    bases = obtener_bases_de_datos_pais()

    print("\n" + "="*70)
    print("EJECUCION EN TODAS LAS BASES DE DATOS")
    print("="*70)
    print(f"\nSe ejecutara en {len(bases)} base(s) de datos:")
    for alias, nombre in bases:
        print(f"  - {nombre} ({alias})")

    respuesta = input("\nContinuar? (s/N): ").strip().lower()
    if respuesta != 's':
        print("  Operacion cancelada.\n")
        return

    for alias, nombre in bases:
        print(f"\n{'#'*70}")
        print(f"# PROCESANDO: {nombre} ({alias})")
        print(f"{'#'*70}")

        # Paso 1: Crear grupos y permisos
        crear_grupos(alias)

        # Paso 2: Asignar grupos a empleados
        asignar_grupos(alias)

    print(f"\n{'='*70}")
    print(f"  EJECUCION COMPLETA EN {len(bases)} BASE(S) DE DATOS")
    print(f"{'='*70}\n")


def seleccionar_bd():
    """
    Permite al usuario seleccionar una base de datos.

    Returns:
        str: Alias de la BD seleccionada
    """
    bases = obtener_bases_de_datos_pais()

    print("\n  Bases de datos disponibles:")
    for i, (alias, nombre) in enumerate(bases, 1):
        print(f"  {i}. {nombre} ({alias})")

    while True:
        try:
            opcion = int(input(f"\nSelecciona (1-{len(bases)}): "))
            if 1 <= opcion <= len(bases):
                alias_seleccionado = bases[opcion - 1][0]
                print(f"  Base de datos cambiada a: {bases[opcion - 1][1]}")
                return alias_seleccionado
            print("  Opcion invalida.")
        except ValueError:
            print("  Ingresa un numero.")


# ============================================================================
# EJECUCION PRINCIPAL
# ============================================================================

def main():
    """
    Funcion principal — Maneja argumentos de linea de comandos y menu.

    EXPLICACION PARA PRINCIPIANTES:
    Esta funcion detecta si le pasaste argumentos al script:

    Sin argumentos → Muestra el menu interactivo
        python scripts/manage_grupos.py

    Con --database=NOMBRE → Crea grupos en esa BD y sale
        python scripts/manage_grupos.py --database=argentina

    Con --todos → Crea grupos en TODAS las BDs y sale
        python scripts/manage_grupos.py --todos

    Con --resumen → Solo muestra el resumen
        python scripts/manage_grupos.py --database=argentina --resumen
    """
    import argparse

    parser = argparse.ArgumentParser(
        description='Gestion de grupos y permisos del sistema (multi-pais)'
    )
    parser.add_argument(
        '--database', '-d',
        default=None,
        help='Alias de la base de datos (ej: default, argentina)'
    )
    parser.add_argument(
        '--todos', '-t',
        action='store_true',
        help='Ejecutar en TODAS las bases de datos'
    )
    parser.add_argument(
        '--resumen', '-r',
        action='store_true',
        help='Solo mostrar resumen (no crear ni asignar)'
    )

    args = parser.parse_args()

    # Modo: Ejecutar en todas las BDs
    if args.todos:
        ejecutar_en_todas()
        return

    # Modo: Base de datos especifica (sin menu)
    if args.database:
        if not validar_db_alias(args.database):
            sys.exit(1)

        if args.resumen:
            ver_resumen(args.database)
        else:
            crear_grupos(args.database)
            asignar_grupos(args.database)
        return

    # Modo: Solo resumen de la BD default
    if args.resumen:
        ver_resumen('default')
        return

    # Modo: Menu interactivo
    db_alias = 'default'

    while True:
        opcion = mostrar_menu(db_alias)

        if opcion == '1':
            print("\n  Creando grupos y permisos...\n")
            crear_grupos(db_alias)
            input("\nPresiona Enter para continuar...")

        elif opcion == '2':
            print("\n  Actualizando permisos...\n")
            crear_grupos(db_alias)  # El script maneja actualizaciones automaticamente
            input("\nPresiona Enter para continuar...")

        elif opcion == '3':
            print("\n  Asignando grupos a empleados...\n")
            asignar_grupos(db_alias)
            input("\nPresiona Enter para continuar...")

        elif opcion == '4':
            ver_resumen(db_alias)
            input("\nPresiona Enter para continuar...")

        elif opcion == '5':
            db_alias = seleccionar_bd()

        elif opcion == '6':
            ejecutar_en_todas()
            input("\nPresiona Enter para continuar...")

        elif opcion == '7':
            print("\n  Hasta luego!\n")
            break

        else:
            print("\n  Opcion invalida. Intenta de nuevo.\n")


if __name__ == '__main__':
    main()
