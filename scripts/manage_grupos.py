"""
Script de gestión de grupos y permisos

Para ejecutar este archivo, usa desde el directorio raíz del proyecto:
    python scripts/manage_grupos.py

Opciones disponibles:
    1. Crear grupos y permisos desde cero
    2. Actualizar permisos de grupos existentes
    3. Asignar grupos a empleados según su rol
    4. Ver resumen de grupos y permisos
"""

import os
import sys

# Agregar el directorio raíz al path de Python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.contrib.auth.models import Group
from inventario.models import Empleado


def mostrar_menu():
    print("\n" + "="*70)
    print("GESTIÓN DE GRUPOS Y PERMISOS")
    print("="*70)
    print("\n1. Crear grupos y permisos desde cero")
    print("2. Actualizar permisos de grupos existentes")
    print("3. Asignar grupos a empleados según su rol")
    print("4. Ver resumen de grupos y permisos")
    print("5. Salir")
    print("\n" + "="*70)
    return input("\nSelecciona una opción (1-5): ")


def crear_grupos():
    """Ejecuta el script setup_grupos_permisos.py"""
    exec(open('scripts/setup_grupos_permisos.py').read())


def asignar_grupos():
    """Ejecuta el script asignar_grupos_empleados.py"""
    exec(open('scripts/asignar_grupos_empleados.py').read())


def ver_resumen():
    """Muestra resumen de grupos y empleados"""
    print("\n" + "="*70)
    print("RESUMEN DE GRUPOS Y PERMISOS")
    print("="*70 + "\n")
    
    grupos = Group.objects.all().order_by('name')
    
    if not grupos.exists():
        print("⚠️  No hay grupos creados. Ejecuta la opción 1 primero.\n")
        return
    
    for grupo in grupos:
        usuarios_count = grupo.user_set.count()
        permisos_count = grupo.permissions.count()
        
        print(f"\n📋 {grupo.name}")
        print(f"   └─ Permisos: {permisos_count}")
        print(f"   └─ Usuarios: {usuarios_count}")
        
        if usuarios_count > 0:
            empleados = Empleado.objects.filter(user__groups=grupo)
            for emp in empleados:
                print(f"      • {emp.nombre_completo} ({emp.cargo})")
    
    print("\n" + "="*70 + "\n")


def main():
    """Función principal"""
    while True:
        opcion = mostrar_menu()
        
        if opcion == '1':
            print("\n🔧 Creando grupos y permisos...\n")
            crear_grupos()
            input("\nPresiona Enter para continuar...")
            
        elif opcion == '2':
            print("\n🔧 Actualizando permisos...\n")
            crear_grupos()  # El script maneja actualizaciones automáticamente
            input("\nPresiona Enter para continuar...")
            
        elif opcion == '3':
            print("\n🔧 Asignando grupos a empleados...\n")
            asignar_grupos()
            input("\nPresiona Enter para continuar...")
            
        elif opcion == '4':
            ver_resumen()
            input("\nPresiona Enter para continuar...")
            
        elif opcion == '5':
            print("\n👋 ¡Hasta luego!\n")
            break
            
        else:
            print("\n❌ Opción inválida. Intenta de nuevo.\n")


if __name__ == '__main__':
    main()
