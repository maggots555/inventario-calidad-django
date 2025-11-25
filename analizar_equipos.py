"""
Script para analizar equipos registrados en el sistema y evaluar
la viabilidad de poblar la tabla ReferenciaGamaEquipo automáticamente.
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import DetalleEquipo, ReferenciaGamaEquipo
from collections import Counter
from django.db.models import Count

print("\n" + "="*70)
print("ANÁLISIS DE EQUIPOS REGISTRADOS EN EL SISTEMA")
print("="*70)

# Obtener todos los equipos
equipos = DetalleEquipo.objects.all()
total_equipos = equipos.count()

print(f"\n📊 RESUMEN GENERAL:")
print(f"   Total de órdenes con equipos registrados: {total_equipos}")

if total_equipos == 0:
    print("\n⚠️  No hay equipos registrados en el sistema aún.")
    exit()

# Análisis de marcas
marcas = list(equipos.values_list('marca', flat=True))
marcas_unicas = set(marcas)
print(f"   Marcas únicas registradas: {len(marcas_unicas)}")

# Análisis de modelos
modelos = list(equipos.values_list('modelo', flat=True))
modelos_unicos = set(modelos)
print(f"   Modelos únicos registrados: {len(modelos_unicos)}")

# Distribución por gama
print(f"\n📈 DISTRIBUCIÓN POR GAMA:")
gamas = list(equipos.values_list('gama', flat=True))
gama_counter = Counter(gamas)
for gama, count in gama_counter.most_common():
    porcentaje = (count / total_equipos) * 100
    print(f"   {gama.upper()}: {count} equipos ({porcentaje:.1f}%)")

# Top marcas
print(f"\n🏆 TOP 15 MARCAS MÁS FRECUENTES:")
marca_counter = Counter(marcas)
for i, (marca, count) in enumerate(marca_counter.most_common(15), 1):
    porcentaje = (count / total_equipos) * 100
    print(f"   {i:2}. {marca:20} → {count:3} equipos ({porcentaje:.1f}%)")

# Top modelos
print(f"\n🏆 TOP 20 MODELOS MÁS FRECUENTES:")
modelo_counter = Counter(modelos)
for i, (modelo, count) in enumerate(modelo_counter.most_common(20), 1):
    # Obtener la gama más común para este modelo
    gama_modelo = equipos.filter(modelo=modelo).values_list('gama', flat=True)
    gama_comun = Counter(gama_modelo).most_common(1)[0][0] if gama_modelo else 'N/A'
    
    porcentaje = (count / total_equipos) * 100
    print(f"   {i:2}. {modelo[:40]:40} → {count:3} equipos ({porcentaje:.1f}%) [Gama: {gama_comun.upper()}]")

# Análisis de combinaciones marca-modelo
print(f"\n🔍 COMBINACIONES MARCA-MODELO CON MÁS DE 1 REGISTRO:")
combinaciones = equipos.values('marca', 'modelo', 'gama').annotate(
    total=Count('orden')
).filter(total__gt=1).order_by('-total')

print(f"   Total de combinaciones con 2+ registros: {combinaciones.count()}")
print()
for i, combo in enumerate(combinaciones[:25], 1):
    print(f"   {i:2}. {combo['marca']:15} | {combo['modelo'][:35]:35} | Gama: {combo['gama'].upper():5} → {combo['total']} veces")

# Referencias actuales
print(f"\n📚 REFERENCIAS ACTUALES EN TABLA ReferenciaGamaEquipo:")
referencias = ReferenciaGamaEquipo.objects.filter(activo=True)
referencias_count = referencias.count()
print(f"   Referencias activas: {referencias_count}")

if referencias_count > 0:
    print(f"\n   Listado de referencias existentes:")
    for i, ref in enumerate(referencias[:20], 1):
        print(f"   {i:2}. {ref.marca:15} {ref.modelo_base:30} - Gama: {ref.gama.upper()}")
    
    if referencias_count > 20:
        print(f"   ... y {referencias_count - 20} más")
else:
    print("   ❌ No hay referencias registradas aún.")

# Análisis de viabilidad
print(f"\n" + "="*70)
print("💡 ANÁLISIS DE VIABILIDAD")
print("="*70)

# Combos con 3+ registros (suficientes para ser confiables)
combos_confiables = combinaciones.filter(total__gte=3).count()
combos_moderados = combinaciones.filter(total=2).count()

print(f"\n✅ Combinaciones marca-modelo CONFIABLES (3+ registros): {combos_confiables}")
print(f"⚠️  Combinaciones marca-modelo MODERADAS (2 registros): {combos_moderados}")
print(f"❌ Combinaciones marca-modelo CON SOLO 1 REGISTRO: {modelos_unicos.__len__() - combos_confiables - combos_moderados}")

print(f"\n📋 RECOMENDACIONES:")

if combos_confiables >= 10:
    print(f"   ✅ EXCELENTE: Tienes {combos_confiables} combinaciones confiables.")
    print(f"      Se recomienda crear referencias automáticamente para estas combinaciones.")
    print(f"      Esto cubrirá una porción significativa de tus órdenes futuras.")
elif combos_confiables >= 5:
    print(f"   ⚠️  BUENO: Tienes {combos_confiables} combinaciones confiables.")
    print(f"      Es viable crear referencias, pero el catálogo será limitado.")
    print(f"      Considera agregar también las combinaciones con 2 registros.")
elif combos_confiables > 0:
    print(f"   ⚠️  LIMITADO: Solo tienes {combos_confiables} combinaciones confiables.")
    print(f"      Puedes crear referencias, pero necesitarás seguir alimentando manualmente.")
else:
    print(f"   ❌ INSUFICIENTE: No hay suficientes registros para poblar automáticamente.")
    print(f"      Necesitas más órdenes de servicio para tener datos confiables.")
    print(f"      Sigue usando el sistema y revisa en un mes.")

print(f"\n" + "="*70)
print("FIN DEL ANÁLISIS")
print("="*70 + "\n")
