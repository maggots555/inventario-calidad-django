"""
Script de prueba para verificar la configuración de correos RHITSO

EXPLICACIÓN PARA PRINCIPIANTES:
Este script verifica que los correos de RHITSO se cargan correctamente desde .env
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.conf import settings

print("=" * 80)
print("🔧 VERIFICACIÓN DE CONFIGURACIÓN RHITSO")
print("=" * 80)

print("\n📧 Destinatarios RHITSO cargados desde .env:")
print("-" * 80)

if settings.RHITSO_EMAIL_RECIPIENTS:
    for idx, recipient in enumerate(settings.RHITSO_EMAIL_RECIPIENTS, 1):
        print(f"\n{idx}. {recipient['nombre']}")
        print(f"   Email: {recipient['email']}")
        print(f"   Grupo: {recipient['grupo']}")
        print(f"   Descripción: {recipient['descripcion']}")
else:
    print("❌ No se encontraron destinatarios RHITSO configurados")

print("\n" + "=" * 80)
print("👥 Áreas para filtrar empleados (Con copia a):")
print("-" * 80)
for area in settings.RHITSO_AREAS_COPIA:
    print(f"  • {area}")

print("\n" + "=" * 80)
print("✅ Verificación completada")
print("=" * 80)
