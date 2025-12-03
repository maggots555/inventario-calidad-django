# -*- coding: utf-8 -*-
"""
Script para cargar productos al almacén desde un archivo CSV.

EXPLICACIÓN PARA PRINCIPIANTES:
Este script lee un archivo CSV (Excel guardado como CSV) con productos
y los carga automáticamente en la base de datos del sistema de almacén.

Qué hace exactamente:
1. Lee el archivo CSV línea por línea
2. Para cada producto verifica si ya existe por código
3. Si existe actualiza el nombre y precio
4. Si NO existe crea uno nuevo
5. Asigna valores por defecto razonables

USO:
1. Activar entorno virtual
2. Ejecutar: python scripts/poblado/cargar_productos_almacen.py
3. Cuando pida la ruta pegar la ruta completa del CSV

Agregado: Diciembre 2025
"""

import os
import sys
import django
import csv
from decimal import Decimal, InvalidOperation

# Configurar Django para que el script pueda usar los modelos
# EXPLICACIÓN: Necesitamos "preparar" Django antes de importar modelos
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Ahora sí podemos importar los modelos de Django
from almacen.models import ProductoAlmacen, CategoriaAlmacen


def limpiar_precio(precio_str):
    """
    Convierte un texto de precio a número decimal.
    
    EXPLICACIÓN:
    - Elimina espacios en blanco
    - Elimina comas que separan miles (1,500.00 -> 1500.00)
    - Si está vacío o es inválido, retorna 0
    
    Parámetros:
    - precio_str: Texto con el precio (ej: "1,500.00", "1500", "")
    
    Retorna:
    - Decimal: Número decimal listo para guardar en la base de datos
    """
    if not precio_str or precio_str.strip() == '':
        return Decimal('0.00')
    
    try:
        # Limpiar el string: eliminar espacios y comas
        precio_limpio = precio_str.strip().replace(',', '')
        return Decimal(precio_limpio)
    except (InvalidOperation, ValueError):
        print(f"⚠️  Advertencia: No se pudo convertir el precio '{precio_str}'. Se usará 0.00")
        return Decimal('0.00')


def categorizar_producto(nombre_producto, codigo_producto):
    """
    Intenta asignar automáticamente una categoría basándose en el nombre.
    
    EXPLICACIÓN:
    Este método usa palabras clave para detectar el tipo de producto.
    Por ejemplo, si el nombre contiene "LCD" o "DISPLAY", lo categoriza
    como "Pantallas y Displays".
    
    Parámetros:
    - nombre_producto: Nombre del producto
    - codigo_producto: Código del producto (para casos especiales)
    
    Retorna:
    - CategoriaAlmacen o None: La categoría detectada, o None si no coincide
    """
    nombre_upper = nombre_producto.upper()
    codigo_upper = codigo_producto.upper()
    
    # Diccionario de palabras clave por categoría
    # EXPLICACIÓN: Si el nombre del producto contiene alguna de estas palabras,
    # se asigna a la categoría correspondiente
    categorias_palabras_clave = {
        'Pantallas y Displays': ['LCD', 'DISPLAY', 'SCREEN', 'MONITOR', 'BEZEL', 'TOP COVER', 'LCD COVER'],
        'Discos y Almacenamiento': ['HDD', 'SSD', 'DISCO DURO', 'STORAGE', 'EXTERNO', 'USB'],
        'Cargadores y Adaptadores': ['CARGADOR', 'ADAPTADOR', 'FUENTE DE PODER', 'AC', 'DC-IN'],
        'Baterías': ['BATERÍA', 'BATERIA', 'PILA'],
        'Componentes de Input': ['TECLADO', 'KEYBOARD', 'TOUCH PAD', 'TOUCHPAD', 'MOUSE', 'LAPIZ OPTICO'],
        'Memoria RAM': ['RAM', 'MEMORIA'],
        'Placas y Tarjetas': ['MOTHERBOARD', 'TARJETA MADRE', 'TARJETA WIFI', 'WIFI', 'DAUGHTERBOARD', 'IO BOARD'],
        'Refrigeración': ['VENTILADOR', 'FAN', 'DISIPADOR', 'HEATSINK'],
        'Carcasas y Estructuras': ['PALMREST', 'BOTTOM BASE', 'BASE COVER', 'LOWER CASE', 'REAR COVER', 'HINGE COVER', 'BISAGRAS'],
        'Cables y Conectores': ['CABLE', 'BUS', 'LVDS', 'ANTENA', 'HUB', 'CONVERTIDOR'],
        'Audio y Video': ['BOCINA', 'AUDÍFONOS', 'AUDIFONOS', 'CAMARA'],
        'Accesorios': ['FUNDA', 'BACKPACK', 'MOUSE PAD', 'CASE', 'BASE DE COMPUTADORA', 'KIT', 'ESPIRAL'],
        'Equipos Completos': ['LAPTOP', 'PORTÁTIL', 'PORTATIL', 'PC'],
        'Herramientas y Consumibles': ['PASTA TERMICA', 'TORNILLOS', 'TAPETE', 'LIMPIEZA', 'KIT DE LIMPIEZA'],
        'Servicios y Soluciones': ['SOLUCION', 'MISSION CRITICAL', 'PROSUPPORT', 'MANTENIMIENTO'],
    }
    
    # Buscar coincidencias
    for nombre_categoria, palabras_clave in categorias_palabras_clave.items():
        for palabra in palabras_clave:
            if palabra in nombre_upper:
                # Intentar obtener o crear la categoría
                categoria, created = CategoriaAlmacen.objects.get_or_create(
                    nombre=nombre_categoria,
                    defaults={'activo': True}
                )
                if created:
                    print(f"  ✨ Categoría '{nombre_categoria}' creada automáticamente")
                return categoria
    
    # Si no se encontró categoría específica, usar "General"
    categoria_general, created = CategoriaAlmacen.objects.get_or_create(
        nombre='General',
        defaults={
            'descripcion': 'Productos sin categoría específica',
            'activo': True
        }
    )
    return categoria_general


def cargar_productos_desde_csv(ruta_csv):
    """
    Función principal que lee el CSV y carga los productos.
    
    EXPLICACIÓN PASO A PASO:
    1. Abre el archivo CSV
    2. Lee cada línea (omitiendo la primera que tiene los encabezados)
    3. Por cada línea:
       - Extrae código, nombre y precio
       - Verifica si el producto ya existe
       - Crea o actualiza el producto
       - Asigna categoría automática
    4. Al final, muestra un resumen
    
    Parámetros:
    - ruta_csv: Ruta completa al archivo CSV
    
    Retorna:
    - dict: Diccionario con estadísticas (creados, actualizados, errores)
    """
    print("\n" + "="*70)
    print("🚀 INICIANDO CARGA DE PRODUCTOS AL ALMACÉN")
    print("="*70)
    
    if not os.path.exists(ruta_csv):
        print(f"❌ ERROR: El archivo no existe: {ruta_csv}")
        return None
    
    # Contadores para estadísticas
    productos_creados = 0
    productos_actualizados = 0
    errores = 0
    
    try:
        # Abrir el archivo CSV
        # EXPLICACIÓN: 'r' = read (lectura), encoding='utf-8' = para leer acentos correctamente
        with open(ruta_csv, 'r', encoding='utf-8') as archivo:
            # csv.DictReader lee el CSV y crea un diccionario por cada fila
            # Las claves del diccionario son los nombres de las columnas
            lector = csv.DictReader(archivo)
            
            print(f"\n📄 Leyendo archivo: {os.path.basename(ruta_csv)}")
            print(f"📊 Columnas detectadas: {lector.fieldnames}\n")
            
            # Iterar sobre cada fila del CSV
            for numero_fila, fila in enumerate(lector, start=2):  # start=2 porque la fila 1 es el encabezado
                try:
                    # Extraer datos de la fila
                    codigo = fila.get('CODIGO UNICO', '').strip()
                    nombre = fila.get('PRODUCTO', '').strip()
                    precio_str = fila.get('PRECIO', '').strip()
                    
                    # Validar que al menos tenga código y nombre
                    if not codigo or not nombre:
                        print(f"⚠️  Fila {numero_fila}: Omitida - falta código o nombre")
                        continue
                    
                    # Convertir el precio a decimal
                    costo_unitario = limpiar_precio(precio_str)
                    
                    # Verificar si el producto ya existe
                    producto_existente = ProductoAlmacen.objects.filter(codigo_producto=codigo).first()
                    
                    if producto_existente:
                        # ACTUALIZAR producto existente
                        producto_existente.nombre = nombre
                        producto_existente.costo_unitario = costo_unitario
                        # Re-categorizar por si cambió el nombre
                        producto_existente.categoria = categorizar_producto(nombre, codigo)
                        producto_existente.save()
                        
                        print(f"🔄 Actualizado: {codigo} - {nombre[:50]}")
                        productos_actualizados += 1
                        
                    else:
                        # CREAR nuevo producto
                        categoria = categorizar_producto(nombre, codigo)
                        
                        producto_nuevo = ProductoAlmacen.objects.create(
                            codigo_producto=codigo,
                            nombre=nombre,
                            descripcion='',  # Se llenará después manualmente
                            categoria=categoria,
                            tipo_producto='resurtible',  # Por defecto, se mantiene en inventario
                            stock_actual=0,  # Comienza en 0, se actualizará con compras
                            stock_minimo=5,  # Valor por defecto razonable
                            stock_maximo=50,  # Valor por defecto razonable
                            costo_unitario=costo_unitario,
                            activo=True,
                            tiempo_reposicion_dias=7,
                        )
                        
                        print(f"✅ Creado: {codigo} - {nombre[:50]} (Cat: {categoria.nombre})")
                        productos_creados += 1
                
                except Exception as e:
                    print(f"❌ Error en fila {numero_fila}: {str(e)}")
                    errores += 1
                    continue
        
        # Resumen final
        print("\n" + "="*70)
        print("📊 RESUMEN DE CARGA")
        print("="*70)
        print(f"✅ Productos creados:     {productos_creados}")
        print(f"🔄 Productos actualizados: {productos_actualizados}")
        print(f"❌ Errores:                {errores}")
        print(f"📦 Total procesados:       {productos_creados + productos_actualizados}")
        print("="*70 + "\n")
        
        return {
            'creados': productos_creados,
            'actualizados': productos_actualizados,
            'errores': errores
        }
    
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO: {str(e)}")
        return None


def main():
    """
    Función principal que ejecuta el script.
    
    EXPLICACIÓN:
    - Solicita la ruta del archivo CSV al usuario
    - Llama a la función de carga
    - Muestra mensajes de éxito o error
    """
    print("\n" + "🎯" + " CARGA DE PRODUCTOS AL ALMACÉN ".center(68, "=") + "🎯\n")
    print("Este script carga productos desde un archivo CSV al sistema de almacén.")
    print("El CSV debe tener las columnas: CODIGO UNICO, PRODUCTO, PRECIO\n")
    
    # Verificar si se pasó la ruta como argumento de línea de comandos
    if len(sys.argv) > 1:
        ruta_csv = sys.argv[1].strip('"').strip("'")
        print(f"📁 Usando archivo: {ruta_csv}\n")
    else:
        # Solicitar la ruta del archivo
        print("📁 Por favor, proporciona la ruta completa del archivo CSV:")
        print("   Ejemplo: C:\\Users\\DELL\\Downloads\\LISTADO DE PRODUCTOS.csv.csv")
        
        ruta_csv = input("\n👉 Ruta del archivo CSV: ").strip()
        
        # Limpiar comillas si el usuario las incluyó al copiar la ruta
        ruta_csv = ruta_csv.strip('"').strip("'")
    
    # Ejecutar la carga
    resultado = cargar_productos_desde_csv(ruta_csv)
    
    if resultado:
        print("\n🎉 ¡Carga completada exitosamente!")
        print("💡 Ahora puedes:")
        print("   1. Editar productos individualmente en el admin")
        print("   2. Agregar imágenes a cada producto")
        print("   3. Ajustar stocks mínimos/máximos según necesidades")
        print("   4. Asignar proveedores principales")
        print("   5. Actualizar descripciones y ubicaciones físicas")
    else:
        print("\n❌ La carga falló. Revisa los mensajes de error arriba.")


if __name__ == '__main__':
    main()
