#!/usr/bin/env python
"""
Script de prueba para verificar la configuración del disco alterno
"""
import os
import sys

# Configurar Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from config.storage_utils import get_storage_info

# Obtener información de almacenamiento
info = get_storage_info()

print("=" * 60)
print("CONFIGURACIÓN DE ALMACENAMIENTO")
print("=" * 60)

print("\n📀 DISCO PRINCIPAL (C:)")
print(f"  Ruta: {info['primary']['path']}")
print(f"  Espacio Total: {info['primary']['total_gb']:.2f} GB")
print(f"  Espacio Usado: {info['primary']['used_gb']:.2f} GB")
print(f"  Espacio Libre: {info['primary']['free_gb']:.2f} GB")
print(f"  Estado: {'✅ ACTIVO' if info['primary']['is_active'] else '⚪ Inactivo'}")

print("\n💾 DISCO ALTERNO (D:)")
print(f"  Ruta: {info['alternate']['path']}")
print(f"  Espacio Total: {info['alternate']['total_gb']:.2f} GB")
print(f"  Espacio Usado: {info['alternate']['used_gb']:.2f} GB")
print(f"  Espacio Libre: {info['alternate']['free_gb']:.2f} GB")
print(f"  Estado: {'✅ ACTIVO' if info['alternate']['is_active'] else '⚪ Inactivo'}")

print(f"\n⚙️ CONFIGURACIÓN")
print(f"  Umbral Mínimo: {info['min_free_space_gb']} GB")
print(f"  Disco Actualmente en Uso: {'PRINCIPAL' if info['primary']['is_active'] else 'ALTERNO'}")

print("\n" + "=" * 60)

# Verificar estado
if info['primary']['is_active'] and info['primary']['free_gb'] < info['min_free_space_gb']:
    print("⚠️  ADVERTENCIA: El disco principal tiene poco espacio.")
    print(f"   Quedan {info['primary']['free_gb']:.2f} GB (mínimo recomendado: {info['min_free_space_gb']} GB)")
    print("   Las nuevas imágenes se guardarán en el disco alterno.")
elif info['primary']['is_active']:
    print("✅ El disco principal tiene suficiente espacio.")
    print("   Las imágenes se están guardando en el disco C:")
else:
    print("🔄 El sistema está usando el disco alterno.")
    print("   Las nuevas imágenes se guardan en el disco D:")

print("=" * 60)
