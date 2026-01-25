#!/usr/bin/env python
"""
Script de prueba para el Dashboard de Distribución Multi-Sucursal
Verifica que la lógica de agregación de datos funcione correctamente
"""
import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from almacen.models import ProductoAlmacen, UnidadInventario
from inventario.models import Sucursal
from django.db.models import Q

def test_dashboard_logic():
    """Prueba la lógica de agregación del dashboard"""
    
    print("=" * 70)
    print("PRUEBA: Dashboard de Distribución Multi-Sucursal")
    print("=" * 70)
    
    # 1. Obtener sucursales activas
    sucursales = Sucursal.objects.filter(activa=True).order_by('codigo')
    print(f"\n✓ Sucursales activas encontradas: {sucursales.count()}")
    for suc in sucursales:
        print(f"  - {suc.codigo}: {suc.nombre}")
    
    # 2. Obtener productos con unidades disponibles
    productos_con_stock = ProductoAlmacen.objects.filter(
        activo=True,
        unidades__disponibilidad='disponible'
    ).distinct()
    
    print(f"\n✓ Productos con stock disponible: {productos_con_stock.count()}")
    
    # 3. Simular la lógica del dashboard para los primeros 5 productos
    print("\n" + "=" * 70)
    print("EJEMPLO DE DISTRIBUCIÓN (Primeros 5 productos)")
    print("=" * 70)
    
    for producto in productos_con_stock[:5]:
        print(f"\n📦 {producto.codigo_producto} - {producto.nombre}")
        print(f"   Categoría: {producto.categoria.nombre if producto.categoria else 'Sin categoría'}")
        
        # Calcular inventario por sucursal (igual que en la vista)
        inventario_sucursales = {}
        total_general = 0
        
        # Central (sucursal_actual = NULL)
        central_disponibles = producto.unidades.filter(
            sucursal_actual__isnull=True,
            disponibilidad='disponible'
        ).count()
        
        inventario_sucursales['central'] = {
            'entradas': central_disponibles,
            'salidas': 0,
            'total': central_disponibles
        }
        total_general += central_disponibles
        
        print(f"   🏢 Central: {central_disponibles} unidades", end="")
        if central_disponibles == 0:
            print(" 🔴")
        elif central_disponibles <= 10:
            print(" 🟡")
        else:
            print(" 🟢")
        
        # Por cada sucursal
        for sucursal in sucursales:
            sucursal_disponibles = producto.unidades.filter(
                sucursal_actual=sucursal,
                disponibilidad='disponible'
            ).count()
            
            inventario_sucursales[sucursal.codigo] = {
                'entradas': sucursal_disponibles,
                'salidas': 0,
                'total': sucursal_disponibles
            }
            total_general += sucursal_disponibles
            
            print(f"   📍 {sucursal.codigo}: {sucursal_disponibles} unidades", end="")
            if sucursal_disponibles == 0:
                print(" 🔴")
            elif sucursal_disponibles <= 10:
                print(" 🟡")
            else:
                print(" 🟢")
        
        print(f"   ✅ TOTAL GENERAL: {total_general} unidades")
    
    # 4. Estadísticas generales
    print("\n" + "=" * 70)
    print("ESTADÍSTICAS GENERALES")
    print("=" * 70)
    
    productos_con_stock_count = ProductoAlmacen.objects.filter(
        activo=True,
        unidades__disponibilidad='disponible'
    ).distinct().count()
    
    productos_sin_stock_count = ProductoAlmacen.objects.filter(
        activo=True
    ).exclude(
        id__in=ProductoAlmacen.objects.filter(
            unidades__disponibilidad='disponible'
        ).values_list('id', flat=True)
    ).count()
    
    total_unidades = UnidadInventario.objects.filter(
        disponibilidad='disponible'
    ).count()
    
    print(f"✓ Productos con stock: {productos_con_stock_count}")
    print(f"✓ Productos sin stock: {productos_sin_stock_count}")
    print(f"✓ Total unidades disponibles: {total_unidades}")
    print(f"✓ Sucursales activas: {sucursales.count()}")
    
    # 5. Verificar que no hay errores de cálculo
    print("\n" + "=" * 70)
    print("VERIFICACIÓN DE INTEGRIDAD")
    print("=" * 70)
    
    # Sumar todas las unidades por ubicación
    central_total = UnidadInventario.objects.filter(
        sucursal_actual__isnull=True,
        disponibilidad='disponible'
    ).count()
    
    sucursales_total = 0
    for suc in sucursales:
        count = UnidadInventario.objects.filter(
            sucursal_actual=suc,
            disponibilidad='disponible'
        ).count()
        sucursales_total += count
    
    suma_calculada = central_total + sucursales_total
    
    print(f"Unidades en Central: {central_total}")
    print(f"Unidades en Sucursales: {sucursales_total}")
    print(f"Suma calculada: {suma_calculada}")
    print(f"Total en BD: {total_unidades}")
    
    if suma_calculada == total_unidades:
        print("✅ INTEGRIDAD VERIFICADA: Los números coinciden")
    else:
        print("❌ ERROR: Hay discrepancia en los totales")
    
    print("\n" + "=" * 70)
    print("✅ PRUEBA COMPLETADA")
    print("=" * 70)

if __name__ == '__main__':
    try:
        test_dashboard_logic()
    except Exception as e:
        print(f"\n❌ ERROR en la prueba: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
