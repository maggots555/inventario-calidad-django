#!/usr/bin/env python
"""
Script para cargar datos JSON con dependencias circulares.

EXPLICACIÓN PARA PRINCIPIANTES:
Este script carga los datos JSON evitando errores de foreign keys circulares.
Funciona procesando los archivos JSON manualmente y guardando todo en una
sola transacción con validaciones diferidas.
"""

import os
import sys
import django
import json

# Configurar Django
sys.path.insert(0, '/var/www/inventario-django/inventario-calidad-django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core import serializers
from django.db import connection, transaction

def cargar_datos():
    """Carga todos los archivos JSON con validaciones diferidas."""
    
    print("🔄 Iniciando carga de datos...")
    
    # Orden de archivos a cargar
    archivos = [
        'backup_sqlite_utf8/users.json',
        'backup_sqlite_utf8/inventario.json',
        'backup_sqlite_utf8/almacen.json',
        'backup_sqlite_utf8/scorecard.json',
        'backup_sqlite_utf8/servicio_tecnico.json',
    ]
    
    try:
        # Iniciar transacción y deshabilitar constraints
        with transaction.atomic():
            # Deshabilitar todas las validaciones de foreign keys
            with connection.cursor() as cursor:
                print("⚙️  Deshabilitando validaciones de foreign keys...")
                cursor.execute('SET CONSTRAINTS ALL DEFERRED;')
            
            # Cargar cada archivo y deserializar manualmente
            for archivo in archivos:
                print(f"📦 Cargando {archivo}...")
                
                with open(archivo, 'r', encoding='utf-8') as f:
                    contenido = f.read()
                
                # Deserializar objetos JSON
                objetos = serializers.deserialize('json', contenido)
                
                # Guardar cada objeto (sin validar foreign keys aún)
                contador = 0
                for obj in objetos:
                    obj.save()
                    contador += 1
                
                print(f"✅ {archivo} cargado: {contador} objetos")
        
        print("\n✅ ¡Todos los datos se cargaron exitosamente!")
        print("🎉 Las validaciones de foreign keys se verificaron al final de la transacción")
        
    except Exception as e:
        print(f"\n❌ Error durante la carga: {e}")
        import traceback
        traceback.print_exc()
        print("\n💡 Intenta revisar los archivos JSON o la integridad de los datos")
        sys.exit(1)

if __name__ == '__main__':
    cargar_datos()
