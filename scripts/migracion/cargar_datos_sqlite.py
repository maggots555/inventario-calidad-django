#!/usr/bin/env python
"""
Script para cargar datos JSON en SQLite con dependencias circulares.

EXPLICACIÓN PARA PRINCIPIANTES:
Este script carga los datos JSON evitando errores de foreign keys circulares en SQLite.
A diferencia de PostgreSQL, SQLite usa PRAGMA para controlar las validaciones.

DIFERENCIAS CON POSTGRESQL:
- PostgreSQL usa: SET CONSTRAINTS ALL DEFERRED
- SQLite usa: PRAGMA foreign_keys = OFF

USO:
    python scripts/migracion/cargar_datos_sqlite.py
"""

import os
import sys
import django
import json
from pathlib import Path

# Configurar la ruta del proyecto (adaptable a diferentes entornos)
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # Sube dos niveles hasta la raíz del proyecto

# Añadir el proyecto al path de Python
sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core import serializers
from django.db import connection, transaction

def cargar_datos():
    """Carga todos los archivos JSON con validaciones diferidas en SQLite."""
    
    print("🔄 Iniciando carga de datos en SQLite...")
    print(f"📁 Ruta del proyecto: {PROJECT_ROOT}")
    
    # Orden de archivos a cargar (relativo a la raíz del proyecto)
    archivos = [
        'backup_sqlite_utf8/users.json',
        'backup_sqlite_utf8/inventario.json',
        'backup_sqlite_utf8/almacen.json',
        'backup_sqlite_utf8/scorecard.json',
        'backup_sqlite_utf8/servicio_tecnico.json',
    ]
    
    # Verificar que los archivos existen
    print("\n📋 Verificando archivos...")
    archivos_completos = []
    for archivo in archivos:
        ruta_completa = PROJECT_ROOT / archivo
        if ruta_completa.exists():
            archivos_completos.append(ruta_completa)
            print(f"  ✅ Encontrado: {archivo}")
        else:
            print(f"  ⚠️  No encontrado: {archivo}")
    
    if not archivos_completos:
        print("\n❌ No se encontraron archivos JSON para cargar")
        print("💡 Verifica que los archivos estén en la carpeta 'backup_sqlite_utf8/'")
        sys.exit(1)
    
    try:
        # Iniciar transacción y deshabilitar constraints
        with transaction.atomic():
            # Deshabilitar validaciones de foreign keys en SQLite
            with connection.cursor() as cursor:
                print("\n⚙️  Deshabilitando validaciones de foreign keys (SQLite)...")
                cursor.execute('PRAGMA foreign_keys = OFF;')
                
                # Verificar que se deshabilitaron correctamente
                cursor.execute('PRAGMA foreign_keys;')
                resultado = cursor.fetchone()
                print(f"  Estado de foreign_keys: {resultado[0]} (0 = deshabilitado)")
            
            # Cargar cada archivo y deserializar manualmente
            total_objetos = 0
            print("\n📦 Cargando archivos JSON...")
            
            for archivo in archivos_completos:
                print(f"\n  Procesando: {archivo.name}")
                
                try:
                    with open(archivo, 'r', encoding='utf-8') as f:
                        contenido = f.read()
                    
                    # Deserializar objetos JSON
                    objetos = serializers.deserialize('json', contenido)
                    
                    # Guardar cada objeto (sin validar foreign keys aún)
                    contador = 0
                    for obj in objetos:
                        obj.save()
                        contador += 1
                    
                    total_objetos += contador
                    print(f"    ✅ {contador} objetos guardados")
                    
                except Exception as e:
                    print(f"    ❌ Error en {archivo.name}: {e}")
                    raise
            
            # Reactivar foreign keys antes de finalizar la transacción
            with connection.cursor() as cursor:
                print("\n⚙️  Reactivando validaciones de foreign keys...")
                cursor.execute('PRAGMA foreign_keys = ON;')
                
                # Verificar integridad de la base de datos
                print("🔍 Verificando integridad de la base de datos...")
                cursor.execute('PRAGMA foreign_key_check;')
                errores = cursor.fetchall()
                
                if errores:
                    print(f"\n⚠️  Se encontraron {len(errores)} violaciones de foreign keys:")
                    for error in errores[:10]:  # Mostrar solo los primeros 10
                        print(f"    - {error}")
                    raise Exception("Hay violaciones de foreign keys. Revisa los datos.")
                else:
                    print("  ✅ Sin violaciones de integridad")
        
        print(f"\n✅ ¡Todos los datos se cargaron exitosamente!")
        print(f"🎉 Total de objetos cargados: {total_objetos}")
        print("✅ Las validaciones de foreign keys se verificaron correctamente")
        
    except Exception as e:
        print(f"\n❌ Error durante la carga: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 SUGERENCIAS:")
        print("  1. Verifica que los archivos JSON tengan el formato correcto")
        print("  2. Asegúrate de que la base de datos esté vacía o limpia")
        print("  3. Revisa que no haya conflictos de IDs o referencias inválidas")
        print("  4. Puedes limpiar la BD con: python manage.py flush")
        sys.exit(1)

if __name__ == '__main__':
    # Mostrar información del entorno
    print("=" * 60)
    print("  SCRIPT DE MIGRACIÓN DE DATOS A SQLITE")
    print("=" * 60)
    print(f"Sistema operativo: {sys.platform}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"Django: {django.get_version()}")
    
    # Verificar que estamos usando SQLite
    from django.conf import settings
    db_engine = settings.DATABASES['default']['ENGINE']
    print(f"Motor de BD: {db_engine}")
    
    if 'sqlite' not in db_engine.lower():
        print("\n⚠️  ADVERTENCIA: Este script está diseñado para SQLite")
        print(f"  Tu base de datos actual es: {db_engine}")
        respuesta = input("\n¿Deseas continuar de todas formas? (s/n): ")
        if respuesta.lower() != 's':
            print("❌ Operación cancelada")
            sys.exit(0)
    
    print("\n" + "=" * 60)
    
    # Confirmar antes de proceder
    respuesta = input("\n¿Deseas cargar los datos ahora? (s/n): ")
    if respuesta.lower() == 's':
        cargar_datos()
    else:
        print("❌ Operación cancelada por el usuario")
