"""
Script para verificar el estado de ReferenciaGamaEquipo
"""
import os
import sys
import django

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import ReferenciaGamaEquipo
from django.db.models import Count

print("=" * 80)
print("ESTADO DE ReferenciaGamaEquipo")
print("=" * 80)
print()

total = ReferenciaGamaEquipo.objects.count()
activas = ReferenciaGamaEquipo.objects.filter(activo=True).count()

print(f"📊 Total referencias: {total}")
print(f"✅ Referencias activas: {activas}")
print()

print("Distribución por Marca:")
print("-" * 40)
for marca_data in ReferenciaGamaEquipo.objects.values('marca').annotate(total=Count('id')).order_by('-total'):
    print(f"  {marca_data['marca']}: {marca_data['total']} modelos")

print()
print("Distribución por Gama:")
print("-" * 40)
for gama in ['alta', 'media', 'baja']:
    count = ReferenciaGamaEquipo.objects.filter(gama=gama, activo=True).count()
    print(f"  {gama.capitalize()}: {count} referencias")

print()
