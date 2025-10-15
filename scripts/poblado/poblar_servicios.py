"""
Script para poblar el catálogo de Servicios Realizados
Ejecutar con: python poblar_servicios.py
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from scorecard.models import ServicioRealizado


def poblar_servicios():
    """
    Crea los servicios predefinidos en el sistema
    """
    servicios = [
        {"nombre": "Ingreso del equipo al CIS", "orden": 1},
        {"nombre": "Revisión de detalles estéticos", "orden": 2},
        {"nombre": "Reparación del equipo", "orden": 3},
        {"nombre": "Reparación a nivel componente", "orden": 4},
        {"nombre": "Cambio de piezas", "orden": 5},
        {"nombre": "Revisión de funcionalidad", "orden": 6},
        {"nombre": "Limpieza interna/externa", "orden": 7},
        {"nombre": "Respaldo de información", "orden": 8},
        {"nombre": "Entrega del equipo", "orden": 9},
    ]
    
    print("=" * 60)
    print("POBLANDO CATÁLOGO DE SERVICIOS REALIZADOS")
    print("=" * 60)
    
    servicios_creados = 0
    servicios_existentes = 0
    
    for servicio_data in servicios:
        servicio, created = ServicioRealizado.objects.get_or_create(
            nombre=servicio_data["nombre"],
            defaults={
                'orden': servicio_data["orden"],
                'activo': True,
            }
        )
        
        if created:
            servicios_creados += 1
            print(f"✅ Creado: {servicio.nombre}")
        else:
            servicios_existentes += 1
            print(f"ℹ️  Ya existe: {servicio.nombre}")
    
    print("\n" + "=" * 60)
    print(f"✅ Servicios creados: {servicios_creados}")
    print(f"ℹ️  Servicios ya existentes: {servicios_existentes}")
    print(f"📊 Total de servicios: {ServicioRealizado.objects.count()}")
    print("=" * 60)


if __name__ == '__main__':
    poblar_servicios()
    print("\n🎉 ¡Proceso completado exitosamente!")
