"""
Script para verificar datos necesarios para las APIs de Fase 3
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from scorecard.models import Incidencia, NotificacionIncidencia

print("=" * 60)
print("VERIFICACIÓN DE DATOS PARA FASE 3")
print("=" * 60)

# Verificar Incidencias
total_incidencias = Incidencia.objects.count()
print(f"\n✅ Total de incidencias: {total_incidencias}")

# Verificar Incidencias con componente
incidencias_con_componente = Incidencia.objects.exclude(componente_afectado__isnull=True).count()
print(f"✅ Incidencias con componente: {incidencias_con_componente}")

if incidencias_con_componente > 0:
    # Listar algunos componentes
    componentes = Incidencia.objects.exclude(componente_afectado__isnull=True).values_list(
        'componente_afectado__nombre', flat=True
    ).distinct()[:5]
    print(f"   Ejemplos de componentes: {list(componentes)}")
else:
    print("   ⚠️ NO HAY incidencias con componentes asignados")

# Verificar Notificaciones
total_notificaciones = NotificacionIncidencia.objects.count()
print(f"\n✅ Total de notificaciones: {total_notificaciones}")

if total_notificaciones > 0:
    exitosas = NotificacionIncidencia.objects.filter(exitoso=True).count()
    fallidas = NotificacionIncidencia.objects.filter(exitoso=False).count()
    print(f"   Exitosas: {exitosas}")
    print(f"   Fallidas: {fallidas}")
else:
    print("   ⚠️ NO HAY notificaciones registradas")

print("\n" + "=" * 60)
print("RECOMENDACIONES:")
print("=" * 60)

if incidencias_con_componente == 0:
    print("⚠️  No hay componentes asignados a incidencias.")
    print("   Solución: Edita algunas incidencias y asigna componentes")

if total_notificaciones == 0:
    print("⚠️  No hay notificaciones enviadas.")
    print("   Solución: Las notificaciones se crean automáticamente al:")
    print("   - Marcar una incidencia como no atribuible")
    print("   - Cerrar una incidencia")
    print("   - Enviar notificación manual")

print("\n")
