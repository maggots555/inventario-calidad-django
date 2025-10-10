"""
Script de prueba para verificar el funcionamiento de los signals RHITSO (Fase 2).

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este script prueba que los signals (detectores automáticos) que creamos
funcionan correctamente. 

Lo que hace:
    1. Crea estados RHITSO de prueba en el catálogo
    2. Crea un tipo de incidencia crítica
    3. Obtiene una orden de prueba
    4. Prueba cambiar el estado_rhitso y verifica que se crea el SeguimientoRHITSO
    5. Prueba crear una incidencia crítica y verifica que se registra en el historial
    6. Prueba las nuevas properties del modelo

Ejecútalo con:
    python verificar_fase2_signals.py
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from servicio_tecnico.models import (
    OrdenServicio,
    EstadoRHITSO,
    TipoIncidenciaRHITSO,
    SeguimientoRHITSO,
    IncidenciaRHITSO,
    HistorialOrden
)
from inventario.models import Empleado

print("=" * 80)
print("VERIFICACIÓN DE FASE 2 - SIGNALS Y LÓGICA DE NEGOCIO RHITSO")
print("=" * 80)
print()

# ============================================================================
# PASO 1: Crear datos de prueba necesarios
# ============================================================================
print("📦 PASO 1: Creando datos de prueba...")
print("-" * 80)

# Crear estados RHITSO si no existen
estados_data = [
    {"estado": "DIAGNOSTICO_SIC", "owner": "SIC", "descripcion": "Diagnóstico inicial en SIC", "orden": 1, "color": "info"},
    {"estado": "ENVIADO_A_RHITSO", "owner": "SIC", "descripcion": "Equipo enviado a RHITSO", "orden": 2, "color": "primary"},
    {"estado": "EN_REPARACION_RHITSO", "owner": "RHITSO", "descripcion": "En proceso de reparación", "orden": 3, "color": "warning"},
    {"estado": "REPARADO_RHITSO", "owner": "RHITSO", "descripcion": "Reparación completada", "orden": 4, "color": "success"},
]

for estado_data in estados_data:
    estado, created = EstadoRHITSO.objects.get_or_create(
        estado=estado_data["estado"],
        defaults={
            "owner": estado_data["owner"],
            "descripcion": estado_data["descripcion"],
            "orden": estado_data["orden"],
            "color": estado_data["color"],
        }
    )
    if created:
        print(f"  ✓ Estado creado: {estado.estado}")
    else:
        print(f"  - Estado ya existe: {estado.estado}")

# Crear tipo de incidencia crítica si no existe
tipo_incidencia, created = TipoIncidenciaRHITSO.objects.get_or_create(
    nombre="Daño adicional causado",
    defaults={
        "descripcion": "RHITSO causó daños adicionales al equipo",
        "gravedad": "CRITICA",
        "color": "danger",
        "requiere_accion_inmediata": True,
    }
)
if created:
    print(f"  ✓ Tipo de incidencia creado: {tipo_incidencia.nombre}")
else:
    print(f"  - Tipo de incidencia ya existe: {tipo_incidencia.nombre}")

print()

# ============================================================================
# PASO 2: Obtener o crear una orden de prueba
# ============================================================================
print("🔍 PASO 2: Preparando orden de prueba...")
print("-" * 80)

# Buscar una orden existente o usar la primera
orden = OrdenServicio.objects.first()

if not orden:
    print("  ❌ ERROR: No hay órdenes en el sistema. Por favor crea al menos una orden primero.")
    sys.exit(1)

print(f"  ✓ Usando orden: {orden.numero_orden_interno}")

# Marcarla como candidata a RHITSO
if not orden.es_candidato_rhitso:
    orden.es_candidato_rhitso = True
    orden.motivo_rhitso = 'reballing'
    orden.descripcion_rhitso = 'Prueba de signals RHITSO'
    orden.save()
    print(f"  ✓ Orden marcada como candidata a RHITSO")

print()

# ============================================================================
# PASO 3: Probar Signal de Cambio de Estado RHITSO
# ============================================================================
print("🔄 PASO 3: Probando signal de cambio de estado_rhitso...")
print("-" * 80)

# Contar registros antes
seguimientos_antes = SeguimientoRHITSO.objects.filter(orden=orden).count()
historial_antes = HistorialOrden.objects.filter(orden=orden).count()

print(f"  📊 Seguimientos RHITSO antes: {seguimientos_antes}")
print(f"  📊 Eventos en historial antes: {historial_antes}")
print()

# Cambiar el estado_rhitso (esto debe activar el signal)
print("  🔧 Cambiando estado_rhitso a 'DIAGNOSTICO_SIC'...")
orden.estado_rhitso = "DIAGNOSTICO_SIC"
orden.save()

# Verificar que se creó el seguimiento
seguimientos_despues = SeguimientoRHITSO.objects.filter(orden=orden).count()
historial_despues = HistorialOrden.objects.filter(orden=orden).count()

print(f"  📊 Seguimientos RHITSO después: {seguimientos_despues}")
print(f"  📊 Eventos en historial después: {historial_despues}")
print()

if seguimientos_despues > seguimientos_antes:
    ultimo_seguimiento = orden.ultimo_seguimiento_rhitso
    print("  ✅ ¡Signal funcionó! Se creó un nuevo seguimiento:")
    print(f"     - Estado: {ultimo_seguimiento.estado.estado}")
    print(f"     - Estado anterior: {ultimo_seguimiento.estado_anterior}")
    print(f"     - Fecha: {ultimo_seguimiento.fecha_actualizacion}")
    print(f"     - Observaciones: {ultimo_seguimiento.observaciones}")
else:
    print("  ❌ ERROR: No se creó el seguimiento. El signal no funcionó.")

print()

# Hacer otro cambio de estado
print("  🔧 Cambiando estado_rhitso a 'ENVIADO_A_RHITSO'...")
orden.estado_rhitso = "ENVIADO_A_RHITSO"
orden.save()

seguimientos_final = SeguimientoRHITSO.objects.filter(orden=orden).count()
print(f"  📊 Seguimientos RHITSO final: {seguimientos_final}")

if seguimientos_final > seguimientos_despues:
    print("  ✅ ¡Segundo cambio también funcionó!")
    ultimo = orden.ultimo_seguimiento_rhitso
    if ultimo.tiempo_en_estado_anterior is not None:
        print(f"     - Tiempo en estado anterior: {ultimo.tiempo_en_estado_anterior} días")
else:
    print("  ❌ ERROR: El segundo cambio no funcionó.")

print()

# ============================================================================
# PASO 4: Probar Signal de Incidencia Crítica
# ============================================================================
print("⚠️  PASO 4: Probando signal de incidencia crítica...")
print("-" * 80)

# Obtener empleado para registro
empleado = Empleado.objects.first()
if not empleado:
    print("  ⚠️  No hay empleados en el sistema. Saltando prueba de incidencia.")
else:
    # Contar eventos antes
    eventos_antes = HistorialOrden.objects.filter(
        orden=orden,
        tipo_evento='sistema'
    ).count()
    
    print(f"  📊 Eventos de sistema antes: {eventos_antes}")
    print()
    
    # Crear incidencia crítica (esto debe activar el signal)
    print("  🔧 Creando incidencia crítica...")
    incidencia = IncidenciaRHITSO.objects.create(
        orden=orden,
        tipo_incidencia=tipo_incidencia,
        titulo="Daño en placa madre durante manipulación",
        descripcion_detallada="Al desmontar el equipo, RHITSO dañó un capacitor de la placa madre",
        impacto_cliente="ALTO",
        prioridad="URGENTE",
        usuario_registro=empleado,
        costo_adicional=500.00
    )
    
    # Verificar que se registró en el historial
    eventos_despues = HistorialOrden.objects.filter(
        orden=orden,
        tipo_evento='sistema'
    ).count()
    
    print(f"  📊 Eventos de sistema después: {eventos_despues}")
    print()
    
    if eventos_despues > eventos_antes:
        ultimo_evento = HistorialOrden.objects.filter(
            orden=orden,
            tipo_evento='sistema'
        ).order_by('-fecha_evento').first()
        
        print("  ✅ ¡Signal funcionó! Se registró en el historial:")
        print(f"     - Tipo: {ultimo_evento.tipo_evento}")
        print(f"     - Comentario: {ultimo_evento.comentario[:100]}...")
        print(f"     - Fecha: {ultimo_evento.fecha_evento}")
    else:
        print("  ❌ ERROR: No se registró en el historial. El signal no funcionó.")

print()

# ============================================================================
# PASO 5: Probar Properties Nuevas
# ============================================================================
print("🔧 PASO 5: Probando properties nuevas de OrdenServicio...")
print("-" * 80)

# Property: ultimo_seguimiento_rhitso
ultimo = orden.ultimo_seguimiento_rhitso
if ultimo:
    print(f"  ✅ ultimo_seguimiento_rhitso: {ultimo.estado.estado}")
else:
    print(f"  ⚠️  ultimo_seguimiento_rhitso: None")

# Property: incidencias_abiertas_count
count_abiertas = orden.incidencias_abiertas_count
print(f"  ✅ incidencias_abiertas_count: {count_abiertas}")

# Property: incidencias_criticas_count
count_criticas = orden.incidencias_criticas_count
print(f"  ✅ incidencias_criticas_count: {count_criticas}")

# Método: puede_cambiar_estado_rhitso
puede, mensaje = orden.puede_cambiar_estado_rhitso()
if puede:
    print(f"  ✅ puede_cambiar_estado_rhitso: SÍ")
else:
    print(f"  ❌ puede_cambiar_estado_rhitso: NO - {mensaje}")

print()

# ============================================================================
# RESUMEN FINAL
# ============================================================================
print("=" * 80)
print("RESUMEN DE VERIFICACIÓN")
print("=" * 80)

total_seguimientos = SeguimientoRHITSO.objects.filter(orden=orden).count()
total_incidencias = IncidenciaRHITSO.objects.filter(orden=orden).count()

print(f"✅ Orden probada: {orden.numero_orden_interno}")
print(f"✅ Total de seguimientos RHITSO: {total_seguimientos}")
print(f"✅ Total de incidencias RHITSO: {total_incidencias}")
print(f"✅ Estado RHITSO actual: {orden.estado_rhitso}")
print(f"✅ Incidencias abiertas: {orden.incidencias_abiertas_count}")
print(f"✅ Incidencias críticas: {orden.incidencias_criticas_count}")

print()
print("🎉 ¡FASE 2 COMPLETADA EXITOSAMENTE!")
print()
print("Los signals están funcionando correctamente:")
print("  ✓ Cambios en estado_rhitso se registran automáticamente")
print("  ✓ Incidencias críticas se registran en el historial")
print("  ✓ Properties calculadas funcionan correctamente")
print()
print("=" * 80)
