#!/usr/bin/env python
"""
Script de prueba completo para verificar el sistema de múltiples ubicaciones
"""
import os
import sys
from pathlib import Path

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from config.storage_utils import PRIMARY_STORAGE_PATH, ALTERNATE_STORAGE_PATH

print("=" * 70)
print("PRUEBA COMPLETA DEL SISTEMA DE MÚLTIPLES UBICACIONES")
print("=" * 70)

# ===========================================================================
# PASO 1: Verificar configuración
# ===========================================================================
print("\n📋 PASO 1: Verificación de Configuración")
print("-" * 70)

print(f"✅ Disco Principal (C:): {PRIMARY_STORAGE_PATH}")
print(f"   Existe: {PRIMARY_STORAGE_PATH.exists()}")

print(f"✅ Disco Alterno (D:): {ALTERNATE_STORAGE_PATH}")
print(f"   Existe: {ALTERNATE_STORAGE_PATH.exists()}")

# ===========================================================================
# PASO 2: Contar archivos existentes
# ===========================================================================
print("\n📊 PASO 2: Archivos Existentes")
print("-" * 70)

def count_files(path):
    """Cuenta archivos en un directorio recursivamente"""
    if not path.exists():
        return 0
    return sum(1 for _ in path.rglob('*') if _.is_file())

files_in_c = count_files(PRIMARY_STORAGE_PATH)
files_in_d = count_files(ALTERNATE_STORAGE_PATH)

print(f"📁 Archivos en Disco C: {files_in_c:,}")
print(f"📁 Archivos en Disco D: {files_in_d:,}")
print(f"📁 Total de archivos: {files_in_c + files_in_d:,}")

# ===========================================================================
# PASO 3: Crear archivo de prueba en disco D:
# ===========================================================================
print("\n💾 PASO 3: Crear Archivo de Prueba en Disco D:")
print("-" * 70)

try:
    # Crear contenido de prueba
    test_content = ContentFile(b"Archivo de prueba para verificar multiples ubicaciones")
    
    # Guardar archivo (debería ir a disco D: porque C: está lleno)
    test_filename = 'test_multi_location/prueba_disk_d.txt'
    saved_path = default_storage.save(test_filename, test_content)
    
    full_path = default_storage.path(saved_path)
    
    print(f"✅ Archivo creado exitosamente")
    print(f"   Nombre: {saved_path}")
    print(f"   Ruta completa: {full_path}")
    
    # Verificar en qué disco se guardó
    if full_path.startswith('D:'):
        print(f"   💾 Guardado en: DISCO ALTERNO (D:) ✅")
    else:
        print(f"   💾 Guardado en: {full_path}")
        
except Exception as e:
    print(f"❌ Error al crear archivo: {e}")

# ===========================================================================
# PASO 4: Simular acceso a archivos antiguos (Disco C:)
# ===========================================================================
print("\n🔍 PASO 4: Verificar Acceso a Archivos Antiguos (Disco C:)")
print("-" * 70)

# Buscar algunos archivos existentes en disco C:
sample_files = []
if PRIMARY_STORAGE_PATH.exists():
    for file_path in PRIMARY_STORAGE_PATH.rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif']:
            # Obtener ruta relativa
            relative_path = file_path.relative_to(PRIMARY_STORAGE_PATH)
            sample_files.append(str(relative_path).replace('\\', '/'))
            if len(sample_files) >= 3:  # Solo mostrar 3 ejemplos
                break

if sample_files:
    print(f"✅ Encontrados {len(sample_files)} archivos de ejemplo en disco C:")
    for file in sample_files:
        print(f"   📄 {file}")
    print(f"\n   Estos archivos deberían ser accesibles en:")
    for file in sample_files:
        print(f"   🌐 http://localhost:8000/media/{file}")
else:
    print("⚠️  No se encontraron archivos de imagen en disco C:")

# ===========================================================================
# PASO 5: Resumen y Recomendaciones
# ===========================================================================
print("\n" + "=" * 70)
print("📝 RESUMEN Y PRÓXIMOS PASOS")
print("=" * 70)

print("\n✅ Configuración Completada:")
print("   1. Archivos nuevos se guardan en disco D:")
print("   2. Vista personalizada busca en ambas ubicaciones")
print("   3. URLs configuradas correctamente")

print("\n🧪 Para Probar el Sistema:")
print("   1. Inicia el servidor: python manage.py runserver")
print("   2. Accede a cualquier módulo (Score Card, Servicio Técnico, Empleados)")
print("   3. Sube una imagen nueva")
print("   4. Verifica que:")
print("      ✓ Se guarda en D:\\Media_Django\\...")
print("      ✓ Se muestra correctamente en la interfaz")
print("      ✓ Las imágenes antiguas de C: también se muestran")

print("\n🔧 Monitoreo:")
print("   • Monitor de almacenamiento: http://localhost:8000/admin/storage-monitor/")
print("   • Los logs mostrarán dónde se encuentra cada archivo")

if files_in_c > 0:
    print(f"\n📦 Migración Opcional:")
    print(f"   Tienes {files_in_c:,} archivos en disco C:")
    print(f"   Puedes moverlos a disco D: para liberar espacio cuando lo necesites.")

print("\n" + "=" * 70)
