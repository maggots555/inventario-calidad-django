#!/usr/bin/env python
"""
Script para poblar la base de datos con productos de ejemplo
Ejecutar con: python manage.py shell < poblar_productos.py
"""

from inventario.models import Producto, Sucursal
from django.db.models import F

# Crear sucursales de ejemplo
sucursal_norte, created = Sucursal.objects.get_or_create(
    nombre="Sucursal Norte",
    defaults={
        'direccion': 'Av. Principal 123, Zona Norte',
        'responsable': 'Juan Pérez',
        'telefono': '555-0123',
        'activa': True
    }
)

sucursal_sur, created = Sucursal.objects.get_or_create(
    nombre="Sucursal Sur", 
    defaults={
        'direccion': 'Calle Secundaria 456, Zona Sur',
        'responsable': 'María González',
        'telefono': '555-0456',
        'activa': True
    }
)

# Lista de productos de ejemplo basados en los que proporcionaste
productos_ejemplo = [
    {
        'nombre': 'ROLLO DE ETIQUETAS CHICO',
        'descripcion': 'Rollo de etiquetas adhesivas tamaño pequeño para etiquetado general',
        'categoria': 'etiquetas',
        'tipo': 'consumible',
        'cantidad': 25,
        'stock_minimo': 10,
        'ubicacion': 'Estante A-1',
        'proveedor': 'Papelería Industrial',
        'costo_unitario': 15.50,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'ROLLO DE ETIQUETA GRANDE',
        'descripcion': 'Rollo de etiquetas adhesivas tamaño grande para productos grandes',
        'categoria': 'etiquetas', 
        'tipo': 'consumible',
        'cantidad': 15,
        'stock_minimo': 8,
        'ubicacion': 'Estante A-2',
        'proveedor': 'Papelería Industrial',
        'costo_unitario': 28.75,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'BOTELLA ATOMIZADOR',
        'descripcion': 'Botella pulverizadora de plástico con gatillo atomizador',
        'categoria': 'envases',
        'tipo': 'reutilizable',
        'cantidad': 45,
        'stock_minimo': 15,
        'ubicacion': 'Estante B-1',
        'proveedor': 'Envases del Norte',
        'costo_unitario': 12.30,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'BOTELLA GRANDE',
        'descripcion': 'Botella de plástico grande de 1 litro para líquidos',
        'categoria': 'envases',
        'tipo': 'reutilizable', 
        'cantidad': 32,
        'stock_minimo': 20,
        'ubicacion': 'Estante B-2',
        'proveedor': 'Envases del Norte',
        'costo_unitario': 8.90,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'BOTELLA CHICA',
        'descripcion': 'Botella de plástico pequeña de 250ml para líquidos',
        'categoria': 'envases',
        'tipo': 'reutilizable',
        'cantidad': 18,
        'stock_minimo': 25,  # Stock bajo intencionalmente
        'ubicacion': 'Estante B-3',
        'proveedor': 'Envases del Norte', 
        'costo_unitario': 4.50,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'CARETA',
        'descripcion': 'Careta de protección facial transparente',
        'categoria': 'seguridad',
        'tipo': 'reutilizable',
        'cantidad': 12,
        'stock_minimo': 10,
        'ubicacion': 'Armario Seguridad A',
        'proveedor': 'Seguridad Total',
        'costo_unitario': 35.00,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'ATOMIZADORES TAPA',
        'descripcion': 'Tapas atomizadoras de repuesto para botellas',
        'categoria': 'envases',
        'tipo': 'consumible',
        'cantidad': 8,
        'stock_minimo': 15,  # Stock bajo
        'ubicacion': 'Gaveta C-1',
        'proveedor': 'Envases del Norte',
        'costo_unitario': 6.25,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'TAPAS',
        'descripcion': 'Tapas estándar para botellas y envases',
        'categoria': 'envases',
        'tipo': 'consumible',
        'cantidad': 120,
        'stock_minimo': 50,
        'ubicacion': 'Gaveta C-2',
        'proveedor': 'Envases del Norte',
        'costo_unitario': 2.10,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'ESPUMA LIMPIADORA',
        'descripcion': 'Producto de limpieza en espuma para superficies',
        'categoria': 'limpieza',
        'tipo': 'consumible',
        'cantidad': 28,
        'stock_minimo': 12,
        'ubicacion': 'Estante D-1',
        'proveedor': 'Químicos Industriales',
        'costo_unitario': 45.80,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'DISPERSER',
        'descripcion': 'Agente dispersante para mezclas químicas',
        'categoria': 'limpieza',
        'tipo': 'consumible',
        'cantidad': 6,
        'stock_minimo': 8,  # Stock bajo
        'ubicacion': 'Estante D-2',
        'proveedor': 'Químicos Industriales',
        'costo_unitario': 125.00,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'REMOVER',
        'descripcion': 'Producto removedor de adhesivos y residuos',
        'categoria': 'limpieza',
        'tipo': 'consumible',
        'cantidad': 15,
        'stock_minimo': 10,
        'ubicacion': 'Estante D-3',
        'proveedor': 'Químicos Industriales',
        'costo_unitario': 78.50,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'GALON LÍQUIDO AZUL',
        'descripcion': 'Galón de líquido limpiador azul concentrado',
        'categoria': 'limpieza',
        'tipo': 'consumible',
        'cantidad': 8,
        'stock_minimo': 5,
        'ubicacion': 'Estante D-4',
        'proveedor': 'Químicos Industriales',
        'costo_unitario': 185.00,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'CUARTOS DE TRAPO',
        'descripcion': 'Trapos de limpieza cortados en cuartos',
        'categoria': 'limpieza',
        'tipo': 'consumible',
        'cantidad': 45,
        'stock_minimo': 20,
        'ubicacion': 'Estante E-1',
        'proveedor': 'Textiles López',
        'costo_unitario': 3.25,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'DUSTER',
        'descripcion': 'Paño para quitar polvo y limpiar superficies',
        'categoria': 'limpieza',
        'tipo': 'reutilizable',
        'cantidad': 22,
        'stock_minimo': 15,
        'ubicacion': 'Estante E-2',
        'proveedor': 'Textiles López',
        'costo_unitario': 12.75,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'ATOMIZADOR L. AZUL',
        'descripcion': 'Atomizador con líquido azul de limpieza',
        'categoria': 'limpieza',
        'tipo': 'consumible',
        'cantidad': 18,
        'stock_minimo': 12,
        'ubicacion': 'Estante E-3',
        'proveedor': 'Químicos Industriales',
        'costo_unitario': 32.40,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'MOUSE',
        'descripcion': 'Mouse óptico USB para computadora',
        'categoria': 'oficina',
        'tipo': 'reutilizable',
        'cantidad': 5,
        'stock_minimo': 8,  # Stock bajo
        'ubicacion': 'Gaveta F-1',
        'proveedor': 'TecnoOficina',
        'costo_unitario': 85.00,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'CINTA DIUREX',
        'descripcion': 'Cinta adhesiva transparente para oficina',
        'categoria': 'oficina',
        'tipo': 'consumible',
        'cantidad': 36,
        'stock_minimo': 20,
        'ubicacion': 'Gaveta F-2',
        'proveedor': 'Papelería Industrial',
        'costo_unitario': 8.75,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'MASQUIN',
        'descripcion': 'Cinta masking tape para protección y marcado',
        'categoria': 'oficina',
        'tipo': 'consumible',
        'cantidad': 24,
        'stock_minimo': 15,
        'ubicacion': 'Gaveta F-3',
        'proveedor': 'Papelería Industrial',
        'costo_unitario': 12.60,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'TECLADO',
        'descripcion': 'Teclado USB estándar para computadora',
        'categoria': 'oficina',
        'tipo': 'reutilizable',
        'cantidad': 4,
        'stock_minimo': 6,  # Stock bajo
        'ubicacion': 'Gaveta F-4',
        'proveedor': 'TecnoOficina',
        'costo_unitario': 125.00,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'CHALECO DE SEGURIDAD',
        'descripcion': 'Chaleco reflectivo de alta visibilidad',
        'categoria': 'seguridad',
        'tipo': 'reutilizable',
        'cantidad': 15,
        'stock_minimo': 10,
        'ubicacion': 'Armario Seguridad B',
        'proveedor': 'Seguridad Total',
        'costo_unitario': 65.00,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'BOTAS DE SEGURIDAD TALLA 8',
        'descripcion': 'Botas de seguridad con punta de acero talla 8',
        'categoria': 'seguridad',
        'tipo': 'reutilizable',
        'cantidad': 3,
        'stock_minimo': 5,  # Stock bajo
        'ubicacion': 'Armario Seguridad C',
        'proveedor': 'Seguridad Total',
        'costo_unitario': 185.00,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'BOTAS DE SEGURIDAD TALLA 6',
        'descripcion': 'Botas de seguridad con punta de acero talla 6',
        'categoria': 'seguridad',
        'tipo': 'reutilizable',
        'cantidad': 2,
        'stock_minimo': 4,  # Stock bajo
        'ubicacion': 'Armario Seguridad C',
        'proveedor': 'Seguridad Total',
        'costo_unitario': 185.00,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'CASCO DE SEGURIDAD',
        'descripcion': 'Casco de protección industrial',
        'categoria': 'seguridad',
        'tipo': 'reutilizable',
        'cantidad': 8,
        'stock_minimo': 6,
        'ubicacion': 'Armario Seguridad D',
        'proveedor': 'Seguridad Total',
        'costo_unitario': 95.00,
        'estado_calidad': 'bueno'
    },
    {
        'nombre': 'PORTA LAPTOPS',
        'descripcion': 'Maletín para transportar laptop y accesorios',
        'categoria': 'oficina',
        'tipo': 'reutilizable',
        'cantidad': 6,
        'stock_minimo': 4,
        'ubicacion': 'Estante G-1',
        'proveedor': 'TecnoOficina',
        'costo_unitario': 145.00,
        'estado_calidad': 'bueno'
    }
]

print("Creando productos de ejemplo...")

productos_creados = 0
productos_actualizados = 0

for producto_data in productos_ejemplo:
    producto, created = Producto.objects.get_or_create(
        nombre=producto_data['nombre'],
        defaults=producto_data
    )
    
    if created:
        productos_creados += 1
        print(f"✓ Creado: {producto.nombre} (QR: {producto.codigo_qr})")
    else:
        productos_actualizados += 1
        print(f"○ Ya existe: {producto.nombre} (QR: {producto.codigo_qr})")

print(f"\n--- RESUMEN ---")
print(f"Productos creados: {productos_creados}")
print(f"Productos ya existentes: {productos_actualizados}")
print(f"Total de productos en el sistema: {Producto.objects.count()}")
print(f"Productos con stock bajo: {Producto.objects.filter(cantidad__lte=F('stock_minimo')).count()}")
print(f"Sucursales creadas: {Sucursal.objects.count()}")

print(f"\n--- ALERTAS DE STOCK BAJO ---")
productos_stock_bajo = Producto.objects.filter(cantidad__lt=F('stock_minimo'))
for producto in productos_stock_bajo:
    print(f"⚠️  {producto.nombre}: {producto.cantidad}/{producto.stock_minimo}")

print(f"\n¡Listo! Puedes ver los productos en: http://127.0.0.1:8000/productos/")
print(f"Dashboard: http://127.0.0.1:8000/")