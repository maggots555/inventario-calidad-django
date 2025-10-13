"""
Script de prueba para verificar que los filtros de colores RHITSO funcionan correctamente.

EXPLICACIÓN PARA PRINCIPIANTES:
Este script prueba que el filtro color_estado_especifico retorna colores correctos.
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Importar el filtro
from servicio_tecnico.templatetags.rhitso_filters import color_estado_especifico

# Estados a probar
estados_prueba = [
    'CANDIDATO RHITSO',
    'PENDIENTE DE CONFIRMAR ENVIO A RHITSO',
    'USUARIO ACEPTA ENVIO A RHITSO',
    'EQUIPO EN RHITSO',
    'EQUIPO RETORNADO A SIC',
    'INCIDENCIA RHITSO',
    'EQUIPO REPARADO',
    'CERRADO',
]

print("=" * 80)
print("🎨 PRUEBA DE FILTRO color_estado_especifico")
print("=" * 80)
print()

for estado in estados_prueba:
    color = color_estado_especifico(estado)
    print(f"📍 Estado: {estado}")
    print(f"   Color HEX: {color}")
    print()

print("=" * 80)
print("✅ Prueba completada. Si ves códigos HEX diferentes, el filtro funciona correctamente.")
print("=" * 80)
