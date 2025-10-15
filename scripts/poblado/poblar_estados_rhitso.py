"""
Script para poblar estados RHITSO en el sistema.

EXPLICACIÓN PARA PRINCIPIANTES:
================================
Este script crea los estados del proceso RHITSO (reparación especializada).
Cada estado tiene:
- nombre: El nombre del estado (ej: "EN DIAGNOSTICO")
- owner: Quién es responsable (SIC, RHITSO, CLIENTE, COMPRAS)
- color: Color del badge en la interfaz
- orden: Orden de aparición en el flujo (1, 2, 3, etc.)

EJECUTAR:
python poblar_estados_rhitso.py
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import EstadoRHITSO

def poblar_estados_rhitso():
    """
    Crea los estados del proceso RHITSO según el flujo estándar.
    Basado en el archivo CSV proporcionado con 32 estados.
    """
    
    estados = [
        # ESTADOS SIC (Owner: SIC)
        {'estado': 'CANDIDATO RHITSO', 'owner': 'SIC', 'descripcion': 'Equipo marcado como candidato para RHITSO', 'color': 'info', 'orden': 1},
        {'estado': 'PENDIENTE DE CONFIRMAR ENVIO A RHITSO', 'owner': 'SIC', 'descripcion': 'Pendiente confirmar el envío a RHITSO', 'color': 'warning', 'orden': 2},
        {'estado': 'USUARIO ACEPTA ENVIO A RHITSO', 'owner': 'SIC', 'descripcion': 'Usuario aceptó el envío a RHITSO', 'color': 'success', 'orden': 3},
        {'estado': 'USUARIO NO ACEPTA ENVIO A RHITSO', 'owner': 'SIC', 'descripcion': 'Usuario no acepta el envío a RHITSO', 'color': 'danger', 'orden': 4},
        {'estado': 'EN ESPERA DE ENTREGAR EQUIPO A RHITSO', 'owner': 'SIC', 'descripcion': 'Equipo pendiente de envío a RHITSO', 'color': 'warning', 'orden': 5},
        {'estado': 'INCIDENCIA SIC', 'owner': 'SIC', 'descripcion': 'Incidencia o problema reportado en SIC', 'color': 'danger', 'orden': 6},
        {'estado': 'COTIZACIÓN ENVIADA A SIC', 'owner': 'SIC', 'descripcion': 'RHITSO envió cotización a SIC para aprobación', 'color': 'info', 'orden': 7},
        {'estado': 'EN ESPERA DE PIEZA POR SIC', 'owner': 'SIC', 'descripcion': 'SIC debe proporcionar pieza o componente', 'color': 'warning', 'orden': 8},
        {'estado': 'PIEZA DE SIC ENVIADA A RHITSO', 'owner': 'SIC', 'descripcion': 'Cuando se envía la pieza a RHITSO y se requiere que confirmen cuando se reciba', 'color': 'warning', 'orden': 9},
        {'estado': 'EQUIPO RETORNADO A SIC', 'owner': 'SIC', 'descripcion': 'Equipo devuelto a SIC desde RHITSO', 'color': 'success', 'orden': 10},
        {'estado': 'EN PRUEBAS SIC', 'owner': 'SIC', 'descripcion': 'Equipo en proceso de pruebas en SIC', 'color': 'info', 'orden': 11},
        
        # ESTADOS RHITSO (Owner: RHITSO)
        {'estado': 'EN ESPERA DE CONFIRMAR INGRESO', 'owner': 'RHITSO', 'descripcion': 'RHITSO debe confirmar recepción del equipo', 'color': 'info', 'orden': 12},
        {'estado': 'EQUIPO EN RHITSO', 'owner': 'RHITSO', 'descripcion': 'Equipo recibido y en instalaciones de RHITSO', 'color': 'primary', 'orden': 13},
        {'estado': 'QR COMPARTIDO (EN DIAGNOSTICO)', 'owner': 'RHITSO', 'descripcion': 'QR del equipo compartido para el seguimiento', 'color': 'info', 'orden': 14},
        {'estado': 'DIAGNOSTICO FINAL', 'owner': 'RHITSO', 'descripcion': 'RHITSO está realizando diagnóstico del equipo', 'color': 'primary', 'orden': 15},
        {'estado': 'EN PROCESO DE RESPALDO', 'owner': 'RHITSO', 'descripcion': 'Realizando respaldo de información del equipo', 'color': 'info', 'orden': 16},
        {'estado': 'EN PROCESO DE REBALLING', 'owner': 'RHITSO', 'descripcion': 'Proceso de reballing de componentes', 'color': 'primary', 'orden': 17},
        {'estado': 'EN PRUEBAS (DE DIAGNOSTICO)', 'owner': 'RHITSO', 'descripcion': 'En pruebas (fase de diagnóstico final) en RHITSO', 'color': 'info', 'orden': 18},
        {'estado': 'NO APTO PARA REPARACIÓN', 'owner': 'RHITSO', 'descripcion': 'Equipo determinado como no reparable', 'color': 'danger', 'orden': 19},
        {'estado': 'EN ESPERA DE PARTES/COMPONENTE', 'owner': 'RHITSO', 'descripcion': 'Esperando llegada de componentes para reparación/terminar diagnóstico', 'color': 'secondary', 'orden': 20},
        {'estado': 'EN PRUEBAS (REPARADO)', 'owner': 'RHITSO', 'descripcion': 'Equipo en proceso de pruebas después de reparación', 'color': 'info', 'orden': 21},
        {'estado': 'EQUIPO REPARADO', 'owner': 'RHITSO', 'descripcion': 'Reparación completada exitosamente', 'color': 'success', 'orden': 22},
        {'estado': 'INCIDENCIA RHITSO', 'owner': 'RHITSO', 'descripcion': 'Incidencia o problema ocasionado por RHITSO', 'color': 'danger', 'orden': 23},
        {'estado': 'EN ESPERA DEL RETORNO DEL EQUIPO', 'owner': 'RHITSO', 'descripcion': 'Esperando el retorno del equipo desde RHITSO', 'color': 'warning', 'orden': 24},
        
        # ESTADOS CLIENTE (Owner: CLIENTE)
        {'estado': 'CLIENTE ACEPTA COTIZACIÓN', 'owner': 'CLIENTE', 'descripcion': 'Cliente ha aceptado la cotización propuesta', 'color': 'success', 'orden': 25},
        {'estado': 'COTIZACIÓN ENVIADA AL CLIENTE', 'owner': 'CLIENTE', 'descripcion': 'Esperando respuesta del cliente sobre cotización', 'color': 'warning', 'orden': 26},
        {'estado': 'CLIENTE NO ACEPTA COTIZACIÓN', 'owner': 'CLIENTE', 'descripcion': 'Cliente rechazó la cotización de reparación', 'color': 'warning', 'orden': 27},
        {'estado': 'PETICIÓN AL CLIENTE', 'owner': 'CLIENTE', 'descripcion': 'Solicitud de información o acción al cliente', 'color': 'warning', 'orden': 28},
        
        # ESTADOS COMPRAS (Owner: COMPRAS)
        {'estado': 'EN ESPERA DE LA OC', 'owner': 'COMPRAS', 'descripcion': 'Esperando orden de compra para proceder', 'color': 'warning', 'orden': 29},
        {'estado': 'PIEZA WBP', 'owner': 'COMPRAS', 'descripcion': 'La pieza llega incorrecta', 'color': 'warning', 'orden': 30},
        {'estado': 'PIEZA DOA', 'owner': 'COMPRAS', 'descripcion': 'Pieza llegó defectuosa (Dead On Arrival)', 'color': 'danger', 'orden': 31},
        
        # ESTADO FINAL
        {'estado': 'CERRADO', 'owner': 'CERRADO', 'descripcion': 'Proceso RHITSO finalizado completamente', 'color': 'dark', 'orden': 32},
    ]
    
    print("=" * 80)
    print("POBLANDO ESTADOS RHITSO")
    print("=" * 80)
    
    creados = 0
    actualizados = 0
    
    for estado_data in estados:
        estado_nombre = estado_data['estado']
        
        # Verificar si ya existe
        estado, created = EstadoRHITSO.objects.get_or_create(
            estado=estado_nombre,
            defaults=estado_data
        )
        
        if created:
            print(f"✅ CREADO: {estado_nombre} (Owner: {estado_data['owner']}, Orden: {estado_data['orden']})")
            creados += 1
        else:
            # Actualizar si ya existe
            for key, value in estado_data.items():
                if key != 'estado':  # No actualizar el nombre
                    setattr(estado, key, value)
            estado.save()
            print(f"🔄 ACTUALIZADO: {estado_nombre}")
            actualizados += 1
    
    print("\n" + "=" * 80)
    print(f"RESUMEN:")
    print(f"  - Estados creados: {creados}")
    print(f"  - Estados actualizados: {actualizados}")
    print(f"  - Total de estados RHITSO: {EstadoRHITSO.objects.count()}")
    print("=" * 80)
    
    # Mostrar primer estado (el que se asignará por defecto)
    primer_estado = EstadoRHITSO.obtener_primer_estado()
    if primer_estado:
        print(f"\n📌 PRIMER ESTADO (por defecto): {primer_estado.estado}")
        print(f"   Owner: {primer_estado.owner}")
        print(f"   Color: {primer_estado.color}")
        print(f"   Orden: {primer_estado.orden}")
    
    return creados, actualizados

if __name__ == '__main__':
    try:
        creados, actualizados = poblar_estados_rhitso()
        print("\n✅ Script ejecutado exitosamente")
    except Exception as e:
        print(f"\n❌ Error al ejecutar script: {e}")
        import traceback
        traceback.print_exc()
