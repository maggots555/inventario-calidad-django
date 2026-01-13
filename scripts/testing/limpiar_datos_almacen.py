"""
Script para limpiar datos de prueba del módulo Almacén

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Este script borra todos los datos de prueba del módulo almacén,
EXCEPTO la tabla de Productos de Almacén que necesitas para continuar.

Tablas que se BORRARÁN (datos de prueba):
- Compras de Productos
- Unidades de Compra
- Movimientos de Almacén
- Solicitudes de Baja
- Auditorías
- Diferencias de Auditoría
- Unidades de Inventario
- Solicitudes de Cotización
- Líneas de Cotización
- Imágenes de Líneas de Cotización

Tablas que se MANTIENEN (datos importantes):
✅ ProductoAlmacen (Productos de Almacén)
✅ CategoriaAlmacen (Categorías de Almacén)
✅ Proveedor (Proveedores)

USO:
    python scripts/testing/limpiar_datos_almacen.py
"""

import os
import sys
import django

# Configurar Django
# EXPLICACIÓN: Necesitamos inicializar Django para poder usar los modelos
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from almacen.models import (
    Proveedor,
    CategoriaAlmacen,
    ProductoAlmacen,
    CompraProducto,
    UnidadCompra,
    MovimientoAlmacen,
    SolicitudBaja,
    Auditoria,
    DiferenciaAuditoria,
    UnidadInventario,
    SolicitudCotizacion,
    LineaCotizacion,
    ImagenLineaCotizacion,
)


def confirmar_accion():
    """
    Pide confirmación al usuario antes de borrar datos.
    
    EXPLICACIÓN:
    Esta función es una medida de seguridad para evitar borrar datos por accidente.
    """
    print("\n" + "="*70)
    print("⚠️  ADVERTENCIA: LIMPIEZA DE DATOS DE PRUEBA - ALMACÉN")
    print("="*70)
    print("\nEste script borrará TODOS los datos de prueba del módulo Almacén.")
    print("\n📋 Tablas que se BORRARÁN:")
    print("   ❌ Compras de Productos")
    print("   ❌ Unidades de Compra")
    print("   ❌ Movimientos de Almacén")
    print("   ❌ Solicitudes de Baja")
    print("   ❌ Auditorías")
    print("   ❌ Diferencias de Auditoría")
    print("   ❌ Unidades de Inventario")
    print("   ❌ Solicitudes de Cotización")
    print("   ❌ Líneas de Cotización")
    print("   ❌ Imágenes de Líneas de Cotización")
    print("\n✅ Tablas que se MANTENDRÁN:")
    print(f"   ✅ Productos de Almacén ({ProductoAlmacen.objects.count()} registros)")
    print(f"   ✅ Categorías de Almacén ({CategoriaAlmacen.objects.count()} registros)")
    print(f"   ✅ Proveedores ({Proveedor.objects.count()} registros)")
    print("\n" + "="*70)
    
    respuesta = input("\n¿Estás seguro de continuar? (escribe 'SI' para confirmar): ")
    return respuesta.strip().upper() == 'SI'


def limpiar_datos():
    """
    Borra los datos de prueba manteniendo ProductoAlmacen, CategoriaAlmacen y Proveedor intactos.
    
    EXPLICACIÓN:
    Esta función borra los datos en orden para evitar problemas de
    relaciones entre tablas (Foreign Keys).
    
    Orden de borrado (de hijos a padres):
    1. Imágenes de líneas de cotización
    2. Líneas de cotización
    3. Solicitudes de cotización
    4. Diferencias de auditoría
    5. Auditorías
    6. Solicitudes de baja
    7. Unidades de compra
    8. Movimientos de almacén
    9. Unidades de inventario
    10. Compras de productos
    
    SE MANTIENEN (no se borran):
    - ProductoAlmacen
    - CategoriaAlmacen
    - Proveedor
    """
    
    print("\n🔄 Iniciando limpieza de datos...\n")
    
    # Contador de registros eliminados
    total_eliminados = 0
    
    # Orden de borrado (de hijos a padres para evitar conflictos)
    # NOTA: Proveedores y CategoriaAlmacen NO se borran
    modelos_a_limpiar = [
        ('Imágenes de Líneas de Cotización', ImagenLineaCotizacion),
        ('Líneas de Cotización', LineaCotizacion),
        ('Solicitudes de Cotización', SolicitudCotizacion),
        ('Diferencias de Auditoría', DiferenciaAuditoria),
        ('Auditorías', Auditoria),
        ('Solicitudes de Baja', SolicitudBaja),
        ('Unidades de Compra', UnidadCompra),
        ('Movimientos de Almacén', MovimientoAlmacen),
        ('Unidades de Inventario', UnidadInventario),
        ('Compras de Productos', CompraProducto),
    ]
    
    for nombre_modelo, modelo in modelos_a_limpiar:
        # Contar registros antes de borrar
        count = modelo.objects.count()
        
        if count > 0:
            # Borrar todos los registros
            modelo.objects.all().delete()
            total_eliminados += count
            print(f"   ✅ {nombre_modelo}: {count} registros eliminados")
        else:
            print(f"   ⚪ {nombre_modelo}: Sin datos (omitido)")
    
    # Verificar que ProductoAlmacen, CategoriaAlmacen y Proveedor siguen intactos
    productos_count = ProductoAlmacen.objects.count()
    categorias_count = CategoriaAlmacen.objects.count()
    proveedores_count = Proveedor.objects.count()
    
    print(f"\n✅ Productos de Almacén PRESERVADOS: {productos_count} registros")
    print(f"✅ Categorías de Almacén PRESERVADAS: {categorias_count} registros")
    print(f"✅ Proveedores PRESERVADOS: {proveedores_count} registros")
    
    print("\n" + "="*70)
    print(f"✅ LIMPIEZA COMPLETADA")
    print(f"   Total de registros eliminados: {total_eliminados}")
    print(f"   Productos de Almacén mantenidos: {productos_count}")
    print(f"   Categorías de Almacén mantenidas: {categorias_count}")
    print(f"   Proveedores mantenidos: {proveedores_count}")
    print("="*70)


def main():
    """
    Función principal del script.
    
    EXPLICACIÓN:
    Esta es la función que se ejecuta cuando corres el script.
    Pide confirmación y luego ejecuta la limpieza.
    """
    try:
        # Pedir confirmación
        if not confirmar_accion():
            print("\n❌ Operación cancelada por el usuario.")
            print("   No se eliminó ningún dato.")
            return
        
        # Ejecutar limpieza
        limpiar_datos()
        
        print("\n✅ Script completado exitosamente.")
        
    except Exception as e:
        print(f"\n❌ ERROR durante la limpieza: {e}")
        print("   Los datos pueden estar parcialmente eliminados.")
        print("   Revisa la base de datos manualmente.")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
