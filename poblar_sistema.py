#!/usr/bin/env python
"""
Script para poblar el sistema de inventario con datos de ejemplo.

Productos basados en los ejemplos proporcionados por el usuario:
- ROLLO DE ETIQUETAS CHICO
- BOTELLA ATOMIZADOR
- Y otros productos de oficina/almacén

Este script crea:
1. Sucursales de ejemplo
2. Productos específicos del usuario
3. Movimientos de prueba para demostrar el sistema

Ejecutar desde la raíz del proyecto Django:
python poblar_sistema.py
"""

import os
import sys
import django
from datetime import datetime, timedelta
import random

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from inventario.models import Producto, Sucursal, Movimiento
from django.contrib.auth.models import User
from django.db.models import F

def crear_sucursales():
    """Crear sucursales de ejemplo"""
    print("Creando sucursales...")
    
    sucursales_data = [
        {
            'nombre': 'Sucursal Principal',
            'direccion': 'Av. Reforma 123, Col. Centro, Ciudad de México, CDMX',
            'responsable': 'María González',
            'telefono': '555-123-4567',
            'activa': True,
        },
        {
            'nombre': 'Sucursal Norte',
            'direccion': 'Av. Constitución 456, Col. Centro, Monterrey, Nuevo León',
            'responsable': 'Carlos Ramírez',
            'telefono': '555-987-6543',
            'activa': True,
        },
        {
            'nombre': 'Sucursal Sur',
            'direccion': 'Av. Vallarta 789, Col. Americana, Guadalajara, Jalisco',
            'responsable': 'Ana López',
            'telefono': '555-456-7890',
            'activa': True,
        },
        {
            'nombre': 'Almacén Temporal',
            'direccion': 'Zona Industrial Norte s/n, Puebla, Puebla',
            'responsable': 'Luis Martín',
            'telefono': '555-321-0987',
            'activa': False,  # Sucursal inactiva para ejemplo
        },
    ]
    
    sucursales_creadas = []
    for data in sucursales_data:
        sucursal, created = Sucursal.objects.get_or_create(
            nombre=data['nombre'],
            defaults=data
        )
        if created:
            print(f"  ✓ Creada: {sucursal.nombre}")
        else:
            print(f"  - Ya existe: {sucursal.nombre}")
        sucursales_creadas.append(sucursal)
    
    return sucursales_creadas

def crear_productos():
    """Crear productos específicos mencionados por el usuario"""
    print("\nCreando productos de ejemplo...")
    
    productos_data = [
        # Productos específicos del usuario
        {
            'nombre': 'ROLLO DE ETIQUETAS CHICO',
            'descripcion': 'Rollo de etiquetas adhesivas tamaño pequeño para impresora térmica',
            'categoria': 'etiquetas',
            'tipo': 'consumible',
            'cantidad': 25,
            'stock_minimo': 10,
            'costo_unitario': 45.50,
            'proveedor': 'Etiquetas y Más SA',
            'estado_calidad': 'bueno',
        },
        {
            'nombre': 'BOTELLA ATOMIZADOR',
            'descripcion': 'Botella atomizadora de plástico para líquidos de limpieza',
            'categoria': 'envases',
            'tipo': 'reutilizable',
            'cantidad': 12,
            'stock_minimo': 5,
            'costo_unitario': 35.00,
            'proveedor': 'Envases Industriales',
            'estado_calidad': 'bueno',
        },
        
        # Productos adicionales de oficina/almacén
        {
            'nombre': 'PAPEL BOND CARTA',
            'descripcion': 'Resma de papel bond tamaño carta, 500 hojas, 75 gramos',
            'categoria': 'oficina',
            'tipo': 'consumible',
            'cantidad': 45,
            'stock_minimo': 20,
            'costo_unitario': 85.00,
            'proveedor': 'Papelería Central',
            'estado_calidad': 'bueno',
        },
        {
            'nombre': 'MARCADOR PERMANENTE NEGRO',
            'descripcion': 'Marcador de tinta permanente color negro, punta gruesa',
            'categoria': 'oficina',
            'tipo': 'consumible',
            'cantidad': 8,  # Stock bajo para mostrar alerta
            'stock_minimo': 15,
            'costo_unitario': 22.50,
            'proveedor': 'Materiales de Oficina',
            'estado_calidad': 'bueno',
        },
        {
            'nombre': 'CAJA ARCHIVO MUERTO',
            'descripcion': 'Caja de cartón corrugado para archivo muerto, tamaño estándar',
            'categoria': 'oficina',
            'tipo': 'reutilizable',
            'cantidad': 15,
            'stock_minimo': 8,
            'costo_unitario': 28.75,
            'proveedor': 'Cajas y Empaques',
            'estado_calidad': 'bueno',
        },
        {
            'nombre': 'GRAPADORA METALICA',
            'descripcion': 'Grapadora metálica resistente, capacidad 25 hojas',
            'categoria': 'herramientas',
            'tipo': 'reutilizable',
            'cantidad': 7,
            'stock_minimo': 3,
            'costo_unitario': 125.00,
            'proveedor': 'Herramientas de Oficina',
            'estado_calidad': 'bueno',
        },
        {
            'nombre': 'CLIPS METALICOS #1',
            'descripcion': 'Clips metálicos galvanizados número 1, caja con 100 piezas',
            'categoria': 'oficina',
            'tipo': 'consumible',
            'cantidad': 23,
            'stock_minimo': 12,
            'costo_unitario': 18.50,
            'proveedor': 'Materiales de Oficina',
            'estado_calidad': 'bueno',
        },
        {
            'nombre': 'FOLDER TABULAR AMARILLO',
            'descripcion': 'Folder tabular amarillo, tamaño carta, paquete con 100',
            'categoria': 'oficina',
            'tipo': 'consumible',
            'cantidad': 11,
            'stock_minimo': 5,
            'costo_unitario': 95.00,
            'proveedor': 'Papelería Central',
            'estado_calidad': 'bueno',
        },
        {
            'nombre': 'CALCULADORA BASICA',
            'descripcion': 'Calculadora básica de escritorio, 8 dígitos, solar',
            'categoria': 'herramientas',
            'tipo': 'reutilizable',
            'cantidad': 6,
            'stock_minimo': 4,
            'costo_unitario': 75.50,
            'proveedor': 'Electrónicos Básicos',
            'estado_calidad': 'bueno',
        },
        {
            'nombre': 'BOTELLA AGUA PURIFICADA',
            'descripcion': 'Botella de agua purificada 500ml para despachador',
            'categoria': 'limpieza',
            'tipo': 'consumible',
            'cantidad': 75,
            'stock_minimo': 50,
            'costo_unitario': 12.00,
            'proveedor': 'Agua Pura SA',
            'estado_calidad': 'bueno',
        },
        
        # Productos con stock crítico para mostrar alertas
        {
            'nombre': 'TONER IMPRESORA HP',
            'descripcion': 'Cartucho de tóner compatible HP LaserJet, negro',
            'categoria': 'oficina',
            'tipo': 'consumible',
            'cantidad': 2,  # Stock crítico
            'stock_minimo': 5,
            'costo_unitario': 450.00,
            'proveedor': 'Suministros Tecnológicos',
            'estado_calidad': 'bueno',
        },
        {
            'nombre': 'ROLLO PAPEL HIGIENICO',
            'descripcion': 'Rollo de papel higiénico institucional, doble hoja',
            'categoria': 'limpieza',
            'tipo': 'consumible',
            'cantidad': 18,  # Stock bajo
            'stock_minimo': 30,
            'costo_unitario': 15.75,
            'proveedor': 'Productos de Limpieza',
            'estado_calidad': 'bueno',
        },
    ]
    
    productos_creados = []
    for data in productos_data:
        producto, created = Producto.objects.get_or_create(
            nombre=data['nombre'],
            defaults=data
        )
        if created:
            print(f"  ✓ Creado: {producto.nombre} (Stock: {producto.cantidad})")
            # El QR se genera automáticamente en el método save()
        else:
            print(f"  - Ya existe: {producto.nombre}")
        productos_creados.append(producto)
    
    return productos_creados

def crear_usuario_ejemplo():
    """Crear usuario de ejemplo para los movimientos"""
    usuario, created = User.objects.get_or_create(
        username='admin_inventario',
        defaults={
            'email': 'admin@inventario.com',
            'first_name': 'Administrador',
            'last_name': 'Inventario',
            'is_staff': True,
        }
    )
    if created:
        usuario.set_password('admin123')
        usuario.save()
        print(f"  ✓ Usuario creado: {usuario.username}")
    else:
        print(f"  - Usuario ya existe: {usuario.username}")
    
    return usuario

def crear_movimientos_ejemplo(productos, sucursales, usuario):
    """Crear movimientos de ejemplo para demostrar el sistema"""
    print("\nCreando movimientos de ejemplo...")
    
    # Motivos comunes
    motivos_entrada = [
        'Compra a proveedor',
        'Devolución de cliente',
        'Ajuste de inventario positivo',
        'Transferencia de otra sucursal',
        'Donación recibida'
    ]
    
    motivos_salida = [
        'Venta a cliente',
        'Uso interno',
        'Transferencia a otra sucursal',
        'Producto dañado',
        'Muestra gratuita'
    ]
    
    motivos_ajuste = [
        'Ajuste por conteo físico',
        'Corrección de error',
        'Merma por caducidad',
        'Diferencia de inventario'
    ]
    
    areas = ['Administración', 'Ventas', 'Almacén', 'Contabilidad', 'Recursos Humanos']
    destinatarios = ['Juan Pérez', 'María García', 'Carlos López', 'Ana Martínez', 'Luis Rodríguez']
    
    movimientos_creados = 0
    
    # Crear movimientos para los últimos 30 días
    for dias_atras in range(30, 0, -1):
        fecha = datetime.now() - timedelta(days=dias_atras)
        
        # Crear algunos movimientos aleatorios por día
        num_movimientos = random.randint(1, 5)
        
        for _ in range(num_movimientos):
            producto = random.choice(productos)
            sucursal = random.choice(sucursales[:3])  # Solo sucursales activas
            tipo = random.choice(['entrada', 'salida', 'ajuste'])
            
            if tipo == 'entrada':
                cantidad = random.randint(5, 50)
                motivo = random.choice(motivos_entrada)
                destinatario = None
                area_destino = None
                sucursal_destino = None
            elif tipo == 'salida':
                cantidad = random.randint(1, 15)
                motivo = random.choice(motivos_salida)
                destinatario = random.choice(destinatarios) if random.random() > 0.5 else None
                area_destino = random.choice(areas) if random.random() > 0.3 else None
                sucursal_destino = random.choice(sucursales) if random.random() > 0.7 else None
            else:  # ajuste
                cantidad = random.randint(-10, 20)
                motivo = random.choice(motivos_ajuste)
                destinatario = None
                area_destino = None
                sucursal_destino = None
            
            # Crear el movimiento
            try:
                movimiento = Movimiento.objects.create(
                    producto=producto,
                    tipo=tipo,
                    cantidad=cantidad,
                    motivo=motivo,
                    destinatario=destinatario,
                    area_destino=area_destino,
                    sucursal_destino=sucursal_destino,
                    numero_proyecto=f"PROY{random.randint(1000, 9999)}" if random.random() > 0.7 else None,
                    observaciones=f"Movimiento de ejemplo generado automáticamente" if random.random() > 0.5 else None,
                    usuario_registro=usuario.get_full_name() or usuario.username,
                    fecha=fecha
                )
                movimientos_creados += 1
                
            except Exception as e:
                print(f"  ! Error creando movimiento: {e}")
    
    print(f"  ✓ Creados {movimientos_creados} movimientos de ejemplo")

def mostrar_resumen():
    """Mostrar resumen de los datos creados"""
    print("\n" + "="*60)
    print("RESUMEN DEL SISTEMA POBLADO")
    print("="*60)
    
    # Estadísticas de productos
    total_productos = Producto.objects.count()
    productos_stock_bajo = Producto.objects.filter(
        cantidad__lt=F('stock_minimo')
    ).count()
    
    print(f"📦 PRODUCTOS:")
    print(f"   Total: {total_productos}")
    print(f"   Con stock bajo: {productos_stock_bajo}")
    
    # Estadísticas de sucursales
    total_sucursales = Sucursal.objects.count()
    sucursales_activas = Sucursal.objects.filter(activa=True).count()
    
    print(f"\n🏢 SUCURSALES:")
    print(f"   Total: {total_sucursales}")
    print(f"   Activas: {sucursales_activas}")
    
    # Estadísticas de movimientos
    total_movimientos = Movimiento.objects.count()
    entradas = Movimiento.objects.filter(tipo='entrada').count()
    salidas = Movimiento.objects.filter(tipo='salida').count()
    ajustes = Movimiento.objects.filter(tipo='ajuste').count()
    
    print(f"\n📊 MOVIMIENTOS:")
    print(f"   Total: {total_movimientos}")
    print(f"   Entradas: {entradas}")
    print(f"   Salidas: {salidas}")
    print(f"   Ajustes: {ajustes}")
    
    # Productos con stock crítico
    print(f"\n⚠️  PRODUCTOS CON STOCK BAJO:")
    productos_criticos = Producto.objects.filter(
        cantidad__lt=F('stock_minimo')
    )
    
    if productos_criticos.exists():
        for producto in productos_criticos:
            print(f"   • {producto.nombre}: {producto.cantidad}/{producto.stock_minimo}")
    else:
        print("   ✓ Todos los productos tienen stock suficiente")
    
    print(f"\n🌐 ACCESO AL SISTEMA:")
    print(f"   URL: http://127.0.0.1:8000/")
    print(f"   Dashboard: http://127.0.0.1:8000/inventario/")
    print(f"   Admin: http://127.0.0.1:8000/admin/")
    print(f"   Usuario admin: admin_inventario")
    print(f"   Contraseña: admin123")
    
    print("\n" + "="*60)
    print("¡SISTEMA LISTO PARA USAR!")
    print("="*60)

def main():
    """Función principal para poblar el sistema"""
    print("🚀 POBLANDO SISTEMA DE INVENTARIO")
    print("="*60)
    
    try:
        # Crear datos de ejemplo
        sucursales = crear_sucursales()
        productos = crear_productos()
        usuario = crear_usuario_ejemplo()
        
        print(f"\nCreando usuario de ejemplo...")
        
        # Crear movimientos de ejemplo
        crear_movimientos_ejemplo(productos, sucursales, usuario)
        
        # Mostrar resumen
        mostrar_resumen()
        
    except Exception as e:
        print(f"\n❌ Error durante la población: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()