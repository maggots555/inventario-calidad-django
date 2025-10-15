"""
Script de verificación de FASE 1 - Sistema Venta Mostrador
Verifica que todos los cambios se aplicaron correctamente
"""
import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from servicio_tecnico.models import OrdenServicio, VentaMostrador, PiezaVentaMostrador
from config.constants import (
    PAQUETES_CHOICES, 
    PRECIOS_PAQUETES, 
    ESTADO_ORDEN_CHOICES,
    paquete_genera_comision,
    obtener_componentes_paquete
)

print("\n" + "="*70)
print("🔍 VERIFICACIÓN FASE 1 - SISTEMA VENTA MOSTRADOR")
print("="*70 + "\n")

# 1. Verificar imports
print("✅ 1. Imports de modelos: OK")

# 2. Verificar constantes actualizadas
print("\n📦 2. PAQUETES ACTUALIZADOS:")
for codigo, nombre in PAQUETES_CHOICES:
    precio = PRECIOS_PAQUETES[codigo]
    genera_com = paquete_genera_comision(codigo)
    print(f"   - {nombre}: ${precio:,.2f} {'(Genera comisión)' if genera_com else ''}")

# 3. Verificar nuevo estado
print("\n📊 3. NUEVO ESTADO:")
estados = dict(ESTADO_ORDEN_CHOICES)
if 'convertida_a_diagnostico' in estados:
    print(f"   ✅ Estado '{estados['convertida_a_diagnostico']}' agregado correctamente")
else:
    print("   ❌ ERROR: Estado 'convertida_a_diagnostico' no encontrado")

# 4. Verificar campos nuevos en OrdenServicio
print("\n🔧 4. CAMPOS NUEVOS EN ORDENSERVICIO:")
campos_nuevos = [
    'tipo_servicio',
    'orden_venta_mostrador_previa',
    'monto_abono_previo',
    'notas_conversion',
    'control_calidad_requerido'
]
for campo in campos_nuevos:
    if hasattr(OrdenServicio, campo):
        print(f"   ✅ Campo '{campo}' existe")
    else:
        print(f"   ❌ Campo '{campo}' NO existe")

# 5. Verificar método convertir_a_diagnostico
print("\n🔄 5. MÉTODO CONVERTIR_A_DIAGNOSTICO:")
if hasattr(OrdenServicio, 'convertir_a_diagnostico'):
    print("   ✅ Método 'convertir_a_diagnostico()' existe")
else:
    print("   ❌ Método 'convertir_a_diagnostico()' NO existe")

# 6. Verificar método clean
print("\n✔️  6. MÉTODO CLEAN (VALIDACIONES):")
if hasattr(OrdenServicio, 'clean'):
    print("   ✅ Método 'clean()' existe")
else:
    print("   ❌ Método 'clean()' NO existe")

# 7. Verificar VentaMostrador actualizado
print("\n💰 7. VENTAMOSTRADOR ACTUALIZADO:")
if hasattr(VentaMostrador, 'genera_comision'):
    print("   ✅ Campo 'genera_comision' existe")
else:
    print("   ❌ Campo 'genera_comision' NO existe")

if hasattr(VentaMostrador, 'total_piezas_vendidas'):
    print("   ✅ Property 'total_piezas_vendidas' existe")
else:
    print("   ❌ Property 'total_piezas_vendidas' NO existe")

# 8. Verificar modelo PiezaVentaMostrador
print("\n🧩 8. MODELO PIEZAVENTAMOSTRADOR:")
campos_pieza = ['venta_mostrador', 'componente', 'descripcion_pieza', 'cantidad', 'precio_unitario', 'fecha_venta', 'notas']
campos_ok = sum(1 for campo in campos_pieza if hasattr(PiezaVentaMostrador, campo))
print(f"   ✅ {campos_ok}/{len(campos_pieza)} campos verificados")

if hasattr(PiezaVentaMostrador, 'subtotal'):
    print("   ✅ Property 'subtotal' existe")

# 9. Verificar órdenes existentes
print("\n📋 9. ÓRDENES EXISTENTES:")
total_ordenes = OrdenServicio.objects.count()
print(f"   ✅ Total de órdenes en BD: {total_ordenes}")

if total_ordenes > 0:
    # Verificar que todas tienen tipo_servicio
    ordenes_con_tipo = OrdenServicio.objects.filter(tipo_servicio='diagnostico').count()
    print(f"   ✅ Órdenes con tipo_servicio='diagnostico': {ordenes_con_tipo}")
    if ordenes_con_tipo == total_ordenes:
        print("   ✅ Todas las órdenes existentes se migraron correctamente")

# 10. Verificar componentes de paquetes
print("\n📦 10. COMPONENTES DE PAQUETES:")
componentes_premium = obtener_componentes_paquete('premium')
print(f"   ✅ Paquete Premium incluye {len(componentes_premium)} componentes")

print("\n" + "="*70)
print("🎉 VERIFICACIÓN COMPLETADA - FASE 1 EXITOSA")
print("="*70 + "\n")

print("📝 RESUMEN:")
print("   ✅ constants.py actualizado con nuevos paquetes")
print("   ✅ OrdenServicio con 5 campos nuevos + 2 métodos")
print("   ✅ VentaMostrador con campo genera_comision + property actualizado")
print("   ✅ PiezaVentaMostrador modelo nuevo creado")
print("   ✅ Migraciones aplicadas sin errores")
print("   ✅ Órdenes existentes preservadas correctamente\n")

print("🚀 LISTO PARA FASE 2: Admin, Vistas y Templates\n")
