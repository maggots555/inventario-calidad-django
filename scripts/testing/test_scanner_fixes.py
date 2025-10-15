#!/usr/bin/env python
"""
Script para probar las mejoras en el manejo de códigos QR de scanners físicos
"""

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from inventario.models import Producto
from inventario.views import limpiar_codigo_scanner, buscar_producto_fuzzy

def test_limpieza_codigos():
    """Probar la función de limpieza de códigos corruptos"""
    
    print("🧪 PRUEBAS DE LIMPIEZA DE CÓDIGOS QR")
    print("=" * 50)
    
    # Código original correcto
    codigo_original = 'INV2025092319145056FFF6'
    print(f"✅ Código original: {codigo_original}")
    
    # Códigos corruptos típicos de scanners físicos
    codigos_corruptos = [
        'INV"="%=)"#!)!$%=%&FFF&',  # Tu ejemplo
        'INV202509231914#$%5056F%F&F6',  # Corrupción parcial
        'I!NV20250923191@4505#6FFF6',   # Corrupción al inicio
        '"INV"2025"09"23"19"14"50"56"FFF"6"',  # Muchas comillas
        'INV=2025%09%23%19%14%50%56%FFF%6',    # Símbolos URL encoding
    ]
    
    print("\n📱 Probando limpieza de códigos corruptos:")
    for i, codigo_corrupto in enumerate(codigos_corruptos, 1):
        codigo_limpio = limpiar_codigo_scanner(codigo_corrupto)
        print(f"{i}. Corrupto: '{codigo_corrupto}'")
        print(f"   Limpio:   '{codigo_limpio}'")
        print(f"   ¿Coincide?: {'✅' if codigo_limpio == codigo_original else '❌'}")
        print()

def test_busqueda_productos():
    """Probar búsqueda de productos con códigos corruptos"""
    
    print("🔍 PRUEBAS DE BÚSQUEDA CON CÓDIGOS CORRUPTOS")
    print("=" * 50)
    
    # Obtener un producto real de la base de datos
    try:
        producto = Producto.objects.first()
        if not producto:
            print("❌ No hay productos en la base de datos para probar")
            return
            
        codigo_real = producto.codigo_qr
        print(f"✅ Producto de prueba: {producto.nombre}")
        print(f"✅ Código real: {codigo_real}")
        
        # Simular códigos corruptos basados en el código real
        codigos_test = [
            codigo_real,  # Código correcto
            codigo_real.replace('0', '#').replace('5', '%'),  # Corrupto
            f'"{codigo_real}"',  # Con comillas
            codigo_real.replace('INV', 'I!NV'),  # Inicio corrupto
        ]
        
        print("\n🔍 Resultados de búsqueda:")
        for i, codigo_test in enumerate(codigos_test, 1):
            try:
                # Intentar búsqueda directa
                producto_encontrado = Producto.objects.get(codigo_qr=codigo_test)
                print(f"{i}. '{codigo_test}' -> ✅ ENCONTRADO DIRECTO")
            except Producto.DoesNotExist:
                # Intentar búsqueda con limpieza
                codigo_limpio = limpiar_codigo_scanner(codigo_test)
                try:
                    producto_encontrado = Producto.objects.get(codigo_qr=codigo_limpio)
                    print(f"{i}. '{codigo_test}' -> ✅ ENCONTRADO LIMPIO")
                except Producto.DoesNotExist:
                    # Intentar búsqueda fuzzy
                    try:
                        producto_encontrado = buscar_producto_fuzzy(codigo_test)
                        print(f"{i}. '{codigo_test}' -> ✅ ENCONTRADO FUZZY")
                    except Producto.DoesNotExist:
                        print(f"{i}. '{codigo_test}' -> ❌ NO ENCONTRADO")
            
    except Exception as e:
        print(f"❌ Error en las pruebas: {e}")

def generar_producto_prueba():
    """Generar un producto de prueba con el nuevo formato de código"""
    
    print("🆕 GENERANDO PRODUCTO DE PRUEBA CON NUEVO FORMATO")
    print("=" * 50)
    
    try:
        # Crear producto de prueba
        producto_nuevo = Producto(
            nombre="PRODUCTO PRUEBA SCANNER",
            descripcion="Producto para probar compatibilidad con scanners físicos",
            categoria="otros",
            cantidad=10,
            stock_minimo=5
        )
        
        # El código se genera automáticamente en save()
        producto_nuevo.save()
        
        print(f"✅ Producto creado exitosamente!")
        print(f"📝 ID: {producto_nuevo.id}")
        print(f"📝 Nombre: {producto_nuevo.nombre}")
        print(f"📝 Código QR: {producto_nuevo.codigo_qr}")
        print(f"📝 Solo números en sufijo: {'✅' if producto_nuevo.codigo_qr.replace('INV', '').replace('20250923', '').isdigit() else '❌'}")
        
        return producto_nuevo
        
    except Exception as e:
        print(f"❌ Error creando producto: {e}")
        return None

if __name__ == "__main__":
    print("🔧 SCRIPT DE PRUEBA - MEJORAS SCANNER QR")
    print("=" * 60)
    
    # Ejecutar todas las pruebas
    test_limpieza_codigos()
    print("\n" + "="*60 + "\n")
    
    test_busqueda_productos()
    print("\n" + "="*60 + "\n")
    
    producto_prueba = generar_producto_prueba()
    
    print("\n" + "="*60)
    print("✅ PRUEBAS COMPLETADAS")
    print("📋 Resumen:")
    print("   - Función de limpieza de códigos implementada")
    print("   - Búsqueda fuzzy para códigos corruptos")
    print("   - Nuevo formato de código QR (solo números)")
    print("   - QR con mayor tolerancia a errores")
    
    if producto_prueba:
        print(f"\n🎯 Usa este código para probar tu scanner: {producto_prueba.codigo_qr}")
