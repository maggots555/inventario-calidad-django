"""
Script para normalizar marcas de equipos en la base de datos.

REGLAS DE NORMALIZACIÓN:
- Primera letra mayúscula, resto minúsculas: Dell, Lenovo, Asus, Acer
- Excepciones con iniciales completas: HP, MSI (todas mayúsculas)

Este script actualiza los registros de DetalleEquipo para mantener consistencia
en los nombres de marcas y facilitar búsquedas y clasificaciones automáticas.
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import DetalleEquipo
from django.db import transaction
from collections import Counter

# Diccionario de normalización
# Mapea variaciones incorrectas a la forma correcta
MARCAS_NORMALIZADAS = {
    # Dell y variaciones
    'dell': 'Dell',
    'DELL': 'Dell',
    'Dell': 'Dell',  # Ya está correcta
    
    # Lenovo y variaciones
    'lenovo': 'Lenovo',
    'LENOVO': 'Lenovo',
    'Lenovo': 'Lenovo',  # Ya está correcta
    
    # HP y variaciones (SIEMPRE MAYÚSCULAS)
    'hp': 'HP',
    'Hp': 'HP',
    'HP': 'HP',  # Ya está correcta
    
    # Asus y variaciones
    'asus': 'Asus',
    'ASUS': 'Asus',
    'Asus': 'Asus',  # Ya está correcta
    
    # Acer y variaciones
    'acer': 'Acer',
    'ACER': 'Acer',
    'Acer': 'Acer',  # Ya está correcta
    
    # MSI y variaciones (SIEMPRE MAYÚSCULAS)
    'msi': 'MSI',
    'Msi': 'MSI',
    'MSI': 'MSI',  # Ya está correcta
    
    # Apple y variaciones
    'apple': 'Apple',
    'APPLE': 'Apple',
    'Apple': 'Apple',  # Ya está correcta
    
    # VAIO y variaciones
    'vaio': 'Vaio',
    'VAIO': 'Vaio',
    'Vaio': 'Vaio',  # Ya está correcta
    
    # Samsung y variaciones
    'samsung': 'Samsung',
    'SAMSUNG': 'Samsung',
    'Samsung': 'Samsung',  # Ya está correcta
    
    # Toshiba y variaciones
    'toshiba': 'Toshiba',
    'TOSHIBA': 'Toshiba',
    'Toshiba': 'Toshiba',  # Ya está correcta
}


def analizar_marcas_actuales():
    """
    Analiza las marcas actuales en la base de datos antes de normalizar.
    
    Returns:
        tuple: (marcas_counter, total_equipos)
    """
    equipos = DetalleEquipo.objects.all()
    marcas = list(equipos.values_list('marca', flat=True))
    marcas_counter = Counter(marcas)
    
    return marcas_counter, equipos.count()


def normalizar_marca(marca_original):
    """
    Normaliza una marca según las reglas definidas.
    
    Args:
        marca_original (str): Marca original sin normalizar
    
    Returns:
        str: Marca normalizada según las reglas
    """
    # Si está en el diccionario, usar el valor normalizado
    if marca_original in MARCAS_NORMALIZADAS:
        return MARCAS_NORMALIZADAS[marca_original]
    
    # Si no está en el diccionario, aplicar regla general:
    # Primera letra mayúscula, resto minúsculas
    return marca_original.capitalize()


def preview_cambios():
    """
    Muestra un preview de los cambios que se realizarán SIN ejecutarlos.
    
    Returns:
        dict: Resumen de cambios por marca
    """
    equipos = DetalleEquipo.objects.all()
    cambios = {}
    
    for equipo in equipos:
        marca_original = equipo.marca
        marca_normalizada = normalizar_marca(marca_original)
        
        if marca_original != marca_normalizada:
            if marca_original not in cambios:
                cambios[marca_original] = {
                    'nueva_marca': marca_normalizada,
                    'cantidad': 0,
                    'ejemplos_modelos': []
                }
            
            cambios[marca_original]['cantidad'] += 1
            
            # Guardar hasta 3 ejemplos de modelos
            if len(cambios[marca_original]['ejemplos_modelos']) < 3:
                cambios[marca_original]['ejemplos_modelos'].append(equipo.modelo)
    
    return cambios


def ejecutar_normalizacion(dry_run=True):
    """
    Ejecuta la normalización de marcas en la base de datos.
    
    Args:
        dry_run (bool): Si es True, solo muestra qué se haría sin guardar cambios
    
    Returns:
        int: Cantidad de registros actualizados
    """
    equipos = DetalleEquipo.objects.all()
    registros_actualizados = 0
    
    if not dry_run:
        with transaction.atomic():
            for equipo in equipos:
                marca_original = equipo.marca
                marca_normalizada = normalizar_marca(marca_original)
                
                if marca_original != marca_normalizada:
                    equipo.marca = marca_normalizada
                    equipo.save(update_fields=['marca'])
                    registros_actualizados += 1
    else:
        # Solo contar sin guardar
        for equipo in equipos:
            marca_original = equipo.marca
            marca_normalizada = normalizar_marca(marca_original)
            
            if marca_original != marca_normalizada:
                registros_actualizados += 1
    
    return registros_actualizados


def main():
    """
    Función principal del script de normalización.
    """
    print("\n" + "="*70)
    print("SCRIPT DE NORMALIZACIÓN DE MARCAS")
    print("="*70)
    
    # Análisis previo
    print("\n📊 ANALIZANDO MARCAS ACTUALES...")
    marcas_counter, total_equipos = analizar_marcas_actuales()
    
    print(f"\nTotal de equipos: {total_equipos}")
    print(f"Marcas diferentes encontradas: {len(marcas_counter)}")
    
    print("\n📋 DISTRIBUCIÓN ACTUAL DE MARCAS:")
    for marca, count in marcas_counter.most_common():
        porcentaje = (count / total_equipos) * 100
        print(f"   '{marca}' → {count:3} equipos ({porcentaje:.1f}%)")
    
    # Preview de cambios
    print("\n" + "="*70)
    print("🔍 PREVIEW DE CAMBIOS A REALIZAR")
    print("="*70)
    
    cambios = preview_cambios()
    
    if not cambios:
        print("\n✅ ¡TODAS LAS MARCAS YA ESTÁN NORMALIZADAS!")
        print("   No se requieren cambios.")
        return
    
    print(f"\n⚠️  Se encontraron {len(cambios)} marcas que necesitan normalización:\n")
    
    total_registros_afectados = 0
    for marca_original, info in sorted(cambios.items()):
        total_registros_afectados += info['cantidad']
        print(f"   '{marca_original}' → '{info['nueva_marca']}'")
        print(f"      Afectará {info['cantidad']} equipos")
        
        if info['ejemplos_modelos']:
            ejemplos = ', '.join(info['ejemplos_modelos'][:3])
            print(f"      Ejemplos: {ejemplos}")
        print()
    
    print(f"📌 TOTAL DE REGISTROS A ACTUALIZAR: {total_registros_afectados}")
    
    # Confirmación
    print("\n" + "="*70)
    print("⚠️  CONFIRMACIÓN REQUERIDA")
    print("="*70)
    
    respuesta = input("\n¿Deseas ejecutar la normalización? (si/no): ").lower().strip()
    
    if respuesta in ['si', 'sí', 's', 'yes', 'y']:
        print("\n🔄 EJECUTANDO NORMALIZACIÓN...")
        
        registros_actualizados = ejecutar_normalizacion(dry_run=False)
        
        print(f"\n✅ ¡NORMALIZACIÓN COMPLETADA!")
        print(f"   {registros_actualizados} registros actualizados correctamente.")
        
        # Análisis posterior
        print("\n📊 VERIFICANDO RESULTADOS...")
        marcas_counter_final, _ = analizar_marcas_actuales()
        
        print(f"\n📋 DISTRIBUCIÓN FINAL DE MARCAS:")
        for marca, count in marcas_counter_final.most_common():
            porcentaje = (count / total_equipos) * 100
            print(f"   '{marca}' → {count:3} equipos ({porcentaje:.1f}%)")
        
        print(f"\n✅ Marcas únicas después de normalización: {len(marcas_counter_final)}")
        print(f"   (Antes: {len(marcas_counter)})")
        
        print("\n💡 SIGUIENTE PASO:")
        print("   Ejecuta 'python analizar_equipos.py' para ver el análisis actualizado.")
    else:
        print("\n❌ Normalización cancelada por el usuario.")
        print("   No se realizaron cambios en la base de datos.")
    
    print("\n" + "="*70)
    print("FIN DEL SCRIPT")
    print("="*70 + "\n")


if __name__ == '__main__':
    main()
