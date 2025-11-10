#!/usr/bin/env python
"""
Script de prueba para verificar que Django guarda archivos en el disco alterno
"""
import os
import sys

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

print("=" * 60)
print("PRUEBA DE ALMACENAMIENTO DINÁMICO")
print("=" * 60)

# Ver qué storage se está usando
print(f"\n📦 Storage en uso: {type(default_storage).__name__}")
print(f"📍 Clase completa: {default_storage.__class__.__module__}.{default_storage.__class__.__name__}")

# Ver la ubicación actual
if hasattr(default_storage, 'location'):
    print(f"📂 Ubicación actual: {default_storage.location}")

# Intentar guardar un archivo de prueba
print("\n" + "=" * 60)
print("GUARDANDO ARCHIVO DE PRUEBA...")
print("=" * 60)

try:
    # Crear contenido de prueba
    test_content = ContentFile(b"Este es un archivo de prueba para validar el almacenamiento dinamico")
    
    # Guardar el archivo
    filename = 'test_storage_prueba.txt'
    saved_path = default_storage.save(f'test/{filename}', test_content)
    
    print(f"\n✅ Archivo guardado exitosamente!")
    print(f"📄 Nombre: {saved_path}")
    print(f"📂 Ruta completa: {default_storage.path(saved_path)}")
    
    # Verificar en qué disco se guardó
    full_path = default_storage.path(saved_path)
    if full_path.startswith('D:'):
        print(f"💾 ✅ CORRECTO: Se guardó en el DISCO ALTERNO (D:)")
    elif full_path.startswith('C:'):
        print(f"💾 ⚠️ ADVERTENCIA: Se guardó en el DISCO PRINCIPAL (C:)")
    else:
        print(f"💾 Ubicación: {full_path}")
    
    # Limpiar archivo de prueba
    default_storage.delete(saved_path)
    print(f"\n🗑️ Archivo de prueba eliminado")
    
except Exception as e:
    print(f"\n❌ Error al guardar archivo: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
