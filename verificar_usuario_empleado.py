"""
Script de diagnóstico: Verifica la relación User <-> Empleado

Este script te ayuda a diagnosticar si tu usuario tiene un empleado asociado,
que es necesario para realizar operaciones como convertir órdenes.
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User
from inventario.models import Empleado

def verificar_usuarios_empleados():
    """
    Verifica todos los usuarios y sus empleados asociados
    """
    print("\n" + "="*70)
    print("DIAGNÓSTICO: USUARIOS Y EMPLEADOS")
    print("="*70 + "\n")
    
    usuarios = User.objects.all()
    print(f"📊 Total de usuarios en el sistema: {usuarios.count()}\n")
    
    for user in usuarios:
        print(f"👤 Usuario: {user.username}")
        print(f"   - ID: {user.id}")
        print(f"   - Email: {user.email}")
        print(f"   - Es superusuario: {'Sí' if user.is_superuser else 'No'}")
        print(f"   - Es staff: {'Sí' if user.is_staff else 'No'}")
        
        # Verificar si tiene empleado asociado
        if hasattr(user, 'empleado'):
            emp = user.empleado
            print(f"   ✅ TIENE EMPLEADO ASOCIADO:")
            print(f"      - ID Empleado: {emp.id}")
            print(f"      - Nombre: {emp.nombre_completo}")
            print(f"      - Sucursal: {emp.sucursal}")
            print(f"      - Activo: {'Sí' if emp.activo else 'No'}")
        else:
            print(f"   ❌ NO TIENE EMPLEADO ASOCIADO")
            print(f"      ⚠️ Este usuario NO puede:")
            print(f"         - Crear órdenes de venta mostrador")
            print(f"         - Convertir órdenes")
            print(f"         - Registrar en historial de órdenes")
        
        print("-" * 70 + "\n")
    
    # Verificar empleados sin usuario
    print("\n" + "="*70)
    print("EMPLEADOS SIN USUARIO ASOCIADO")
    print("="*70 + "\n")
    
    empleados_sin_usuario = Empleado.objects.filter(usuario__isnull=True)
    if empleados_sin_usuario.exists():
        print(f"⚠️ Hay {empleados_sin_usuario.count()} empleados sin usuario:\n")
        for emp in empleados_sin_usuario:
            print(f"   - {emp.nombre_completo} (ID: {emp.id}, Sucursal: {emp.sucursal})")
    else:
        print("✅ Todos los empleados tienen usuario asociado")
    
    print("\n" + "="*70)
    print("RECOMENDACIONES")
    print("="*70 + "\n")
    
    usuarios_sin_empleado = [u for u in usuarios if not hasattr(u, 'empleado')]
    if usuarios_sin_empleado:
        print("⚠️ Los siguientes usuarios necesitan un empleado asociado:\n")
        for user in usuarios_sin_empleado:
            print(f"   - {user.username}")
        print("\n💡 Para crear la relación, ve al Django Admin:")
        print("   1. Ve a Inventario > Empleados")
        print("   2. Edita o crea un empleado")
        print("   3. Asigna el usuario correspondiente en el campo 'Usuario'")
        print("   4. Guarda los cambios")
    else:
        print("✅ Todos los usuarios tienen empleado asociado. ¡Todo bien!")
    
    print("\n" + "="*70 + "\n")

if __name__ == '__main__':
    verificar_usuarios_empleados()
