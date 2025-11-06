"""
Script de Validación: Tipos de Servicio en Órdenes

PROPÓSITO:
Verificar que todas las órdenes tienen el campo tipo_servicio correctamente establecido
y generar estadísticas para análisis.

EXPLICACIÓN PARA PRINCIPIANTES:
Este script consulta la base de datos para ver:
1. Cuántas órdenes hay de cada tipo (diagnóstico vs venta mostrador)
2. Si hay órdenes sin tipo_servicio definido (NULL o vacío)
3. Distribución por estado y tipo
4. Métricas básicas de tiempo por tipo

USO:
    python manage.py shell < scripts/verificacion/validar_tipos_servicio.py

O ejecutar desde Django shell:
    python manage.py shell
    >>> exec(open('scripts/verificacion/validar_tipos_servicio.py').read())
"""

import os
import django

# Configurar Django (necesario si se ejecuta como script standalone)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db.models import Count, Avg, Q
from servicio_tecnico.models import OrdenServicio
from datetime import datetime

print("=" * 80)
print("📊 VALIDACIÓN DE TIPOS DE SERVICIO EN ÓRDENES")
print("=" * 80)
print(f"Fecha de ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print()

# ============================================================================
# 1. ESTADÍSTICAS GENERALES
# ============================================================================
print("🔍 1. ESTADÍSTICAS GENERALES")
print("-" * 80)

total_ordenes = OrdenServicio.objects.count()
print(f"Total de órdenes en el sistema: {total_ordenes}")

if total_ordenes == 0:
    print("\n⚠️  No hay órdenes registradas en el sistema.")
    exit()

# Órdenes por tipo
ordenes_por_tipo = OrdenServicio.objects.values('tipo_servicio').annotate(
    total=Count('id')
).order_by('-total')

print("\n📊 Distribución por tipo de servicio:")
for tipo in ordenes_por_tipo:
    tipo_servicio = tipo['tipo_servicio']
    total = tipo['total']
    porcentaje = (total / total_ordenes) * 100
    
    # Emoji según tipo
    emoji = "🔵" if tipo_servicio == 'diagnostico' else "🟠" if tipo_servicio == 'venta_mostrador' else "❓"
    
    print(f"  {emoji} {tipo_servicio:20s}: {total:4d} órdenes ({porcentaje:5.1f}%)")

# ============================================================================
# 2. VALIDAR INTEGRIDAD
# ============================================================================
print("\n🔍 2. VALIDACIÓN DE INTEGRIDAD")
print("-" * 80)

# Órdenes sin tipo definido (NULL o vacío)
ordenes_sin_tipo = OrdenServicio.objects.filter(
    Q(tipo_servicio__isnull=True) | Q(tipo_servicio='')
).count()

if ordenes_sin_tipo > 0:
    print(f"⚠️  ADVERTENCIA: {ordenes_sin_tipo} órdenes sin tipo_servicio definido")
    print("   Estas órdenes necesitan ser corregidas manualmente.")
else:
    print("✅ Todas las órdenes tienen tipo_servicio definido correctamente")

# Verificar tipos válidos
tipos_validos = ['diagnostico', 'venta_mostrador']
ordenes_tipo_invalido = OrdenServicio.objects.exclude(
    tipo_servicio__in=tipos_validos
).count()

if ordenes_tipo_invalido > 0:
    print(f"⚠️  ADVERTENCIA: {ordenes_tipo_invalido} órdenes con tipo_servicio no válido")
    print(f"   Tipos válidos: {tipos_validos}")
else:
    print("✅ Todos los tipos de servicio son válidos")

# ============================================================================
# 3. DISTRIBUCIÓN POR ESTADO Y TIPO
# ============================================================================
print("\n🔍 3. DISTRIBUCIÓN POR ESTADO Y TIPO")
print("-" * 80)

print("\n📋 Órdenes de DIAGNÓSTICO:")
diagnostico_stats = OrdenServicio.objects.filter(
    tipo_servicio='diagnostico'
).values('estado').annotate(
    total=Count('id')
).order_by('-total')

if diagnostico_stats:
    for stat in diagnostico_stats:
        print(f"  • {stat['estado']:20s}: {stat['total']:4d} órdenes")
else:
    print("  (No hay órdenes de diagnóstico)")

print("\n📋 Órdenes de VENTA MOSTRADOR:")
venta_stats = OrdenServicio.objects.filter(
    tipo_servicio='venta_mostrador'
).values('estado').annotate(
    total=Count('id')
).order_by('-total')

if venta_stats:
    for stat in venta_stats:
        print(f"  • {stat['estado']:20s}: {stat['total']:4d} órdenes")
else:
    print("  (No hay órdenes de venta mostrador)")

# ============================================================================
# 4. MÉTRICAS DE TIEMPO
# ============================================================================
print("\n🔍 4. MÉTRICAS DE TIEMPO PROMEDIO")
print("-" * 80)

# Tiempo promedio por tipo (solo órdenes finalizadas)
print("\n⏱️  Tiempo promedio de servicio (órdenes finalizadas):")

diagnostico_tiempo = OrdenServicio.objects.filter(
    tipo_servicio='diagnostico',
    estado='finalizada'
).aggregate(
    promedio=Avg('tiempo_total_dias')
)

if diagnostico_tiempo['promedio']:
    print(f"  🔵 Diagnóstico:      {diagnostico_tiempo['promedio']:.1f} días")
else:
    print(f"  🔵 Diagnóstico:      N/A (sin órdenes finalizadas)")

venta_tiempo = OrdenServicio.objects.filter(
    tipo_servicio='venta_mostrador',
    estado='finalizada'
).aggregate(
    promedio=Avg('tiempo_total_dias')
)

if venta_tiempo['promedio']:
    print(f"  🟠 Venta Mostrador:  {venta_tiempo['promedio']:.1f} días")
else:
    print(f"  🟠 Venta Mostrador:  N/A (sin órdenes finalizadas)")

# ============================================================================
# 5. PREFIJOS DE ORDEN_CLIENTE
# ============================================================================
print("\n🔍 5. VALIDACIÓN DE PREFIJOS (orden_cliente)")
print("-" * 80)

print("\n🏷️  Prefijos utilizados:")

# Diagnóstico debería tener OOW-
diagnostico_oow = OrdenServicio.objects.filter(
    tipo_servicio='diagnostico',
    detalle_equipo__orden_cliente__istartswith='OOW-'
).count()

diagnostico_total = OrdenServicio.objects.filter(tipo_servicio='diagnostico').count()

if diagnostico_total > 0:
    porcentaje_oow = (diagnostico_oow / diagnostico_total) * 100
    print(f"  🔵 Diagnóstico con OOW-:      {diagnostico_oow:4d} / {diagnostico_total:4d} ({porcentaje_oow:5.1f}%)")
    
    if porcentaje_oow < 100:
        otros_prefijos = diagnostico_total - diagnostico_oow
        print(f"     ⚠️  {otros_prefijos} órdenes de diagnóstico sin prefijo OOW-")

# Venta Mostrador debería tener FL-
venta_fl = OrdenServicio.objects.filter(
    tipo_servicio='venta_mostrador',
    detalle_equipo__orden_cliente__istartswith='FL-'
).count()

venta_total = OrdenServicio.objects.filter(tipo_servicio='venta_mostrador').count()

if venta_total > 0:
    porcentaje_fl = (venta_fl / venta_total) * 100
    print(f"  🟠 Venta Mostrador con FL-:   {venta_fl:4d} / {venta_total:4d} ({porcentaje_fl:5.1f}%)")
    
    if porcentaje_fl < 100:
        otros_prefijos = venta_total - venta_fl
        print(f"     ⚠️  {otros_prefijos} órdenes de venta mostrador sin prefijo FL-")

# ============================================================================
# 6. RESUMEN Y RECOMENDACIONES
# ============================================================================
print("\n" + "=" * 80)
print("📋 RESUMEN Y RECOMENDACIONES")
print("=" * 80)

problemas_encontrados = []

if ordenes_sin_tipo > 0:
    problemas_encontrados.append(f"• {ordenes_sin_tipo} órdenes sin tipo_servicio definido")

if ordenes_tipo_invalido > 0:
    problemas_encontrados.append(f"• {ordenes_tipo_invalido} órdenes con tipo_servicio inválido")

if diagnostico_total > 0 and porcentaje_oow < 100:
    problemas_encontrados.append(f"• {diagnostico_total - diagnostico_oow} diagnósticos sin prefijo OOW-")

if venta_total > 0 and porcentaje_fl < 100:
    problemas_encontrados.append(f"• {venta_total - venta_fl} ventas mostrador sin prefijo FL-")

if problemas_encontrados:
    print("\n⚠️  PROBLEMAS DETECTADOS:")
    for problema in problemas_encontrados:
        print(f"   {problema}")
    print("\n💡 RECOMENDACIONES:")
    print("   1. Revisar y corregir manualmente las órdenes con problemas")
    print("   2. Asegurarse de usar los formularios correctos al crear órdenes")
    print("   3. Validar prefijos al momento de creación")
else:
    print("\n✅ NO SE DETECTARON PROBLEMAS")
    print("   El sistema está correctamente configurado.")

print("\n" + "=" * 80)
print("✅ Validación completada")
print("=" * 80)
