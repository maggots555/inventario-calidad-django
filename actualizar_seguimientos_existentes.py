"""
Script de Migración de Datos - Actualizar Seguimientos RHITSO Existentes

PROPÓSITO:
==========
Actualizar todos los registros existentes en SeguimientoRHITSO para marcar
correctamente si son cambios automáticos o manuales.

LÓGICA:
=======
1. Los seguimientos SIN usuario_actualizacion → Automáticos (signals del sistema)
2. Los seguimientos CON usuario_actualizacion → Manuales (usuario usó formulario)

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este script se ejecuta una sola vez para actualizar registros antiguos que
se crearon antes de implementar el campo es_cambio_automatico.

Django ORM (Object-Relational Mapping):
- Es una forma de trabajar con la base de datos usando Python
- En lugar de escribir SQL, usamos métodos de Python
- Django traduce automáticamente a SQL

Ejemplo:
  SQL: UPDATE seguimientorhitso SET es_cambio_automatico = true WHERE usuario_actualizacion_id IS NULL
  Django ORM: SeguimientoRHITSO.objects.filter(usuario_actualizacion__isnull=True).update(es_cambio_automatico=True)
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import SeguimientoRHITSO

def actualizar_seguimientos():
    """
    Actualiza los seguimientos existentes clasificándolos correctamente.
    
    Returns:
        dict: Estadísticas de la actualización
    """
    print("=" * 70)
    print("ACTUALIZACIÓN DE SEGUIMIENTOS RHITSO EXISTENTES")
    print("=" * 70)
    print()
    
    # Obtener todos los seguimientos
    total_seguimientos = SeguimientoRHITSO.objects.count()
    print(f"📊 Total de seguimientos en la base de datos: {total_seguimientos}")
    print()
    
    # PASO 1: Marcar como automáticos los que NO tienen usuario
    # EXPLICACIÓN: Si usuario_actualizacion es None/null, significa que
    # el seguimiento fue creado automáticamente por un signal del sistema
    seguimientos_sin_usuario = SeguimientoRHITSO.objects.filter(
        usuario_actualizacion__isnull=True
    )
    count_sin_usuario = seguimientos_sin_usuario.count()
    
    if count_sin_usuario > 0:
        print(f"🤖 Seguimientos sin usuario (automáticos): {count_sin_usuario}")
        # update() ejecuta un UPDATE en SQL directamente
        # Es más eficiente que hacer save() en cada objeto
        seguimientos_sin_usuario.update(es_cambio_automatico=True)
        print("   ✅ Marcados como AUTOMÁTICOS (es_cambio_automatico=True)")
    else:
        print("ℹ️  No hay seguimientos sin usuario")
    
    print()
    
    # PASO 2: Marcar como manuales los que SÍ tienen usuario
    # EXPLICACIÓN: Si usuario_actualizacion tiene un valor, significa que
    # un usuario específico registró ese cambio mediante el formulario
    seguimientos_con_usuario = SeguimientoRHITSO.objects.filter(
        usuario_actualizacion__isnull=False
    )
    count_con_usuario = seguimientos_con_usuario.count()
    
    if count_con_usuario > 0:
        print(f"👤 Seguimientos con usuario (manuales): {count_con_usuario}")
        seguimientos_con_usuario.update(es_cambio_automatico=False)
        print("   ✅ Marcados como MANUALES (es_cambio_automatico=False)")
    else:
        print("ℹ️  No hay seguimientos con usuario")
    
    print()
    print("=" * 70)
    print("RESUMEN DE LA ACTUALIZACIÓN")
    print("=" * 70)
    
    # Verificar resultados finales
    total_automaticos = SeguimientoRHITSO.objects.filter(es_cambio_automatico=True).count()
    total_manuales = SeguimientoRHITSO.objects.filter(es_cambio_automatico=False).count()
    
    print(f"✅ Seguimientos AUTOMÁTICOS: {total_automaticos}")
    print(f"✅ Seguimientos MANUALES: {total_manuales}")
    print(f"📊 TOTAL: {total_automaticos + total_manuales}")
    print()
    
    if (total_automaticos + total_manuales) == total_seguimientos:
        print("🎉 ¡Actualización completada exitosamente!")
        print("   Todos los seguimientos fueron clasificados correctamente.")
    else:
        print("⚠️  ADVERTENCIA: Hay una discrepancia en los números.")
        print(f"   Se esperaban {total_seguimientos} seguimientos")
        print(f"   Se clasificaron {total_automaticos + total_manuales}")
    
    print("=" * 70)
    
    return {
        'total': total_seguimientos,
        'automaticos': total_automaticos,
        'manuales': total_manuales,
        'actualizados_sin_usuario': count_sin_usuario,
        'actualizados_con_usuario': count_con_usuario,
    }

if __name__ == '__main__':
    try:
        stats = actualizar_seguimientos()
        print()
        print("ℹ️  PRÓXIMOS PASOS:")
        print("   1. Verifica que los números sean correctos")
        print("   2. Accede a la vista de gestión RHITSO en el navegador")
        print("   3. Comprueba que los tabs muestran correctamente:")
        print("      - Tab 'Cambios Manuales' → Seguimientos con usuario")
        print("      - Tab 'Cambios Automáticos' → Seguimientos del sistema")
        print()
    except Exception as e:
        print()
        print("❌ ERROR durante la actualización:")
        print(f"   {str(e)}")
        print()
        print("   Verifica que:")
        print("   1. La migración se haya aplicado correctamente")
        print("   2. El modelo SeguimientoRHITSO tenga el campo es_cambio_automatico")
        print("   3. El entorno virtual esté activado")
        import traceback
        traceback.print_exc()
