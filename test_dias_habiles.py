"""
Script de prueba para validar el cálculo de días hábiles
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datetime import datetime, timedelta
from servicio_tecnico.utils_rhitso import calcular_dias_habiles

# Caso de prueba: Orden ORD-2025-0081
fecha_inicio = datetime(2025, 10, 9).date()  # Miércoles 09/10/2025
fecha_fin = datetime(2025, 10, 14).date()    # Lunes 14/10/2025

dias = calcular_dias_habiles(fecha_inicio, fecha_fin)

print("=" * 70)
print("PRUEBA DE CÁLCULO DE DÍAS HÁBILES")
print("=" * 70)
print(f"\nFecha inicio: {fecha_inicio.strftime('%d/%m/%Y')} ({fecha_inicio.strftime('%A')})")
print(f"Fecha fin:    {fecha_fin.strftime('%d/%m/%Y')} ({fecha_fin.strftime('%A')})")
print(f"\n✅ Días hábiles transcurridos: {dias}")

print("\n" + "=" * 70)
print("DESGLOSE DÍA POR DÍA:")
print("=" * 70)

# Mostrar cada día
fecha_actual = fecha_inicio
contador = 0
print(f"\n❌ {fecha_actual.strftime('%d/%m/%Y')} ({fecha_actual.strftime('%A')}) - Día de INICIO (no cuenta)")

fecha_actual += timedelta(days=1)
while fecha_actual <= fecha_fin:
    dia_nombre = fecha_actual.strftime('%A')
    es_habil = fecha_actual.weekday() < 5
    
    if es_habil:
        contador += 1
        print(f"✅ {fecha_actual.strftime('%d/%m/%Y')} ({dia_nombre}) - Día hábil #{contador}")
    else:
        print(f"⏭️  {fecha_actual.strftime('%d/%m/%Y')} ({dia_nombre}) - Fin de semana (no cuenta)")
    
    fecha_actual += timedelta(days=1)

print("\n" + "=" * 70)
print(f"TOTAL: {dias} días hábiles")
print("=" * 70)

# Más casos de prueba
print("\n\n" + "=" * 70)
print("CASOS ADICIONALES DE PRUEBA:")
print("=" * 70)

casos = [
    ("Mismo día", datetime(2025, 10, 14).date(), datetime(2025, 10, 14).date()),
    ("Viernes a Lunes", datetime(2025, 10, 11).date(), datetime(2025, 10, 14).date()),
    ("Lunes a Viernes", datetime(2025, 10, 7).date(), datetime(2025, 10, 11).date()),
]

for nombre, inicio, fin in casos:
    dias_test = calcular_dias_habiles(inicio, fin)
    print(f"\n{nombre}:")
    print(f"  {inicio.strftime('%d/%m/%Y (%A)')} → {fin.strftime('%d/%m/%Y (%A)')}")
    print(f"  Resultado: {dias_test} días hábiles")
