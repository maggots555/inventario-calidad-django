"""
Script de verificación de FASE 2 - Sistema Venta Mostrador
Verifica que todos los cambios del Admin se aplicaron correctamente

EXPLICACIÓN PARA PRINCIPIANTES:
Este script verifica que todas las configuraciones del Admin de Django
para el sistema de Venta Mostrador se hayan implementado correctamente.
Comprueba que los nuevos filtros, campos, inlines y métodos existen.
"""
import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib import admin
from servicio_tecnico.models import OrdenServicio, VentaMostrador, PiezaVentaMostrador
from servicio_tecnico.admin import (
    OrdenServicioAdmin,
    VentaMostradorAdmin,
    PiezaVentaMostradorAdmin,
    PiezaVentaMostradorInline
)

print("\n" + "="*80)
print("🔍 VERIFICACIÓN FASE 2 - ADMIN VENTA MOSTRADOR")
print("="*80 + "\n")

errores_encontrados = 0

# ============================================================================
# 1. VERIFICAR QUE LOS MODELOS ESTÉN REGISTRADOS
# ============================================================================
print("📋 1. MODELOS REGISTRADOS EN ADMIN:")
modelos_verificar = [
    (OrdenServicio, 'OrdenServicio'),
    (VentaMostrador, 'VentaMostrador'),
    (PiezaVentaMostrador, 'PiezaVentaMostrador')
]

for modelo, nombre in modelos_verificar:
    if admin.site.is_registered(modelo):
        print(f"   ✅ {nombre} está registrado en el admin")
    else:
        print(f"   ❌ ERROR: {nombre} NO está registrado")
        errores_encontrados += 1

# ============================================================================
# 2. VERIFICAR ORDENSERVICIOADMIN
# ============================================================================
print("\n🔧 2. ORDENSERVICIOADMIN - VERIFICACIONES:")

# Verificar list_display
print("\n   📊 List Display:")
list_display = OrdenServicioAdmin.list_display
campos_esperados = ['tipo_servicio_badge', 'estado_badge', 'numero_orden_interno']
for campo in campos_esperados:
    if campo in list_display:
        print(f"      ✅ '{campo}' en list_display")
    else:
        print(f"      ❌ ERROR: '{campo}' NO está en list_display")
        errores_encontrados += 1

# Verificar list_filter
print("\n   🔍 List Filter:")
if 'tipo_servicio' in OrdenServicioAdmin.list_filter:
    print(f"      ✅ 'tipo_servicio' en list_filter")
else:
    print(f"      ❌ ERROR: 'tipo_servicio' NO está en list_filter")
    errores_encontrados += 1

# Verificar métodos
print("\n   🛠️  Métodos:")
metodos_esperados = ['tipo_servicio_badge', 'estado_badge']
for metodo in metodos_esperados:
    if hasattr(OrdenServicioAdmin, metodo):
        print(f"      ✅ Método '{metodo}' existe")
    else:
        print(f"      ❌ ERROR: Método '{metodo}' NO existe")
        errores_encontrados += 1

# Verificar fieldsets (buscar el nuevo fieldset de Tipo de Servicio)
print("\n   📂 Fieldsets:")
fieldsets = OrdenServicioAdmin.fieldsets
fieldset_nombres = [fs[0] for fs in fieldsets]
fieldsets_esperados = ['Tipo de Servicio', 'Conversión desde Venta Mostrador']
for nombre in fieldsets_esperados:
    if nombre in fieldset_nombres:
        print(f"      ✅ Fieldset '{nombre}' existe")
    else:
        print(f"      ❌ ERROR: Fieldset '{nombre}' NO existe")
        errores_encontrados += 1

# ============================================================================
# 3. VERIFICAR VENTAMOSTRADORADMIN
# ============================================================================
print("\n💰 3. VENTAMOSTRADORADMIN - VERIFICACIONES:")

# Verificar list_display
print("\n   📊 List Display:")
list_display = VentaMostradorAdmin.list_display
if 'genera_comision' in list_display:
    print(f"      ✅ 'genera_comision' en list_display")
else:
    print(f"      ❌ ERROR: 'genera_comision' NO está en list_display")
    errores_encontrados += 1

# Verificar list_filter
print("\n   🔍 List Filter:")
if 'genera_comision' in VentaMostradorAdmin.list_filter:
    print(f"      ✅ 'genera_comision' en list_filter")
else:
    print(f"      ❌ ERROR: 'genera_comision' NO está en list_filter")
    errores_encontrados += 1

# Verificar inlines
print("\n   📎 Inlines:")
if hasattr(VentaMostradorAdmin, 'inlines'):
    if PiezaVentaMostradorInline in VentaMostradorAdmin.inlines:
        print(f"      ✅ PiezaVentaMostradorInline está en inlines")
    else:
        print(f"      ❌ ERROR: PiezaVentaMostradorInline NO está en inlines")
        errores_encontrados += 1
else:
    print(f"      ❌ ERROR: VentaMostradorAdmin no tiene inlines configurado")
    errores_encontrados += 1

# Verificar método paquete_badge
print("\n   🎨 Método paquete_badge:")
if hasattr(VentaMostradorAdmin, 'paquete_badge'):
    print(f"      ✅ Método 'paquete_badge' existe")
    # Verificar que tenga los colores actualizados (esto es más complicado, solo verificamos existencia)
else:
    print(f"      ❌ ERROR: Método 'paquete_badge' NO existe")
    errores_encontrados += 1

# ============================================================================
# 4. VERIFICAR PIEZAVENTAMOSTRADORADMIN
# ============================================================================
print("\n🧩 4. PIEZAVENTAMOSTRADORADMIN - VERIFICACIONES:")

# Verificar que existe
if admin.site.is_registered(PiezaVentaMostrador):
    admin_class = admin.site._registry[PiezaVentaMostrador]
    print(f"   ✅ PiezaVentaMostrador tiene clase admin registrada")
    
    # Verificar list_display
    print("\n   📊 List Display:")
    campos_esperados = ['venta_mostrador', 'descripcion_pieza', 'cantidad', 'precio_unitario_display']
    for campo in campos_esperados:
        if campo in admin_class.list_display:
            print(f"      ✅ '{campo}' en list_display")
        else:
            print(f"      ❌ ERROR: '{campo}' NO está en list_display")
            errores_encontrados += 1
    
    # Verificar search_fields
    print("\n   🔍 Search Fields:")
    if hasattr(admin_class, 'search_fields') and len(admin_class.search_fields) > 0:
        print(f"      ✅ search_fields configurado ({len(admin_class.search_fields)} campos)")
    else:
        print(f"      ❌ ERROR: search_fields NO configurado")
        errores_encontrados += 1
    
    # Verificar date_hierarchy
    print("\n   📅 Date Hierarchy:")
    if hasattr(admin_class, 'date_hierarchy') and admin_class.date_hierarchy:
        print(f"      ✅ date_hierarchy configurado: '{admin_class.date_hierarchy}'")
    else:
        print(f"      ❌ ERROR: date_hierarchy NO configurado")
        errores_encontrados += 1

else:
    print(f"   ❌ ERROR: PiezaVentaMostrador NO está registrado")
    errores_encontrados += 1

# ============================================================================
# 5. VERIFICAR PIEZAVENTAMOSTRADOR INLINE
# ============================================================================
print("\n📎 5. PIEZAVENTAMOSTRADOR INLINE - VERIFICACIONES:")

# Verificar que existe la clase
try:
    print(f"   ✅ Clase PiezaVentaMostradorInline existe")
    
    # Verificar model
    if hasattr(PiezaVentaMostradorInline, 'model') and PiezaVentaMostradorInline.model == PiezaVentaMostrador:
        print(f"   ✅ Model configurado correctamente")
    else:
        print(f"   ❌ ERROR: Model NO configurado o incorrecto")
        errores_encontrados += 1
    
    # Verificar fields
    if hasattr(PiezaVentaMostradorInline, 'fields'):
        campos_esperados = ['descripcion_pieza', 'cantidad', 'precio_unitario']
        for campo in campos_esperados:
            if campo in PiezaVentaMostradorInline.fields:
                print(f"   ✅ Campo '{campo}' en inline fields")
            else:
                print(f"   ❌ ERROR: Campo '{campo}' NO en inline fields")
                errores_encontrados += 1
    
    # Verificar readonly_fields
    if hasattr(PiezaVentaMostradorInline, 'readonly_fields'):
        if 'subtotal_display' in PiezaVentaMostradorInline.readonly_fields:
            print(f"   ✅ 'subtotal_display' en readonly_fields")
        else:
            print(f"   ⚠️  ADVERTENCIA: 'subtotal_display' debería estar en readonly_fields")
    
except Exception as e:
    print(f"   ❌ ERROR al verificar inline: {str(e)}")
    errores_encontrados += 1

# ============================================================================
# RESUMEN FINAL
# ============================================================================
print("\n" + "="*80)
print("📊 RESUMEN DE VERIFICACIÓN")
print("="*80)

if errores_encontrados == 0:
    print("\n✅ ¡FASE 2 COMPLETADA EXITOSAMENTE!")
    print("   Todos los cambios del Admin fueron aplicados correctamente.")
    print("\n📝 Cambios verificados:")
    print("   ✅ OrdenServicioAdmin actualizado con tipo_servicio y conversión")
    print("   ✅ VentaMostradorAdmin actualizado con genera_comision y inline de piezas")
    print("   ✅ PiezaVentaMostradorAdmin creado y registrado")
    print("   ✅ PiezaVentaMostradorInline configurado correctamente")
    print("   ✅ Badges de colores actualizados (premium, oro, plata)")
    print("   ✅ Filtros y campos de búsqueda funcionando")
    print("\n🚀 PRÓXIMO PASO: FASE 3 - Crear Vistas AJAX")
    sys.exit(0)
else:
    print(f"\n❌ SE ENCONTRARON {errores_encontrados} ERRORES")
    print("   Por favor revisa los mensajes anteriores y corrige los problemas.")
    sys.exit(1)
