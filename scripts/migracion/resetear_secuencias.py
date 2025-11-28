#!/usr/bin/env python
"""
Script para resetear las secuencias (auto-increment) de PostgreSQL.

EXPLICACIÓN PARA PRINCIPIANTES:
Cuando cargas datos desde JSON, los IDs se insertan directamente (ej: 1, 2, 3...).
Pero PostgreSQL no actualiza automáticamente su "contador" interno (secuencia).
Este script actualiza todos los contadores para que comiencen desde el último ID usado + 1.

CUÁNDO USAR:
- Después de cargar datos con loaddata
- Cuando obtienes errores de "duplicate key" al crear nuevos registros
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, '/var/www/inventario-django/inventario-calidad-django')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.core.management.color import no_style
from django.db import connection

def resetear_secuencias():
    """
    Resetea las secuencias de todas las tablas de la base de datos.
    
    Esto ajusta el contador automático de IDs para que comience desde
    el máximo ID actual + 1, evitando errores de duplicate key.
    """
    
    print("🔧 Reseteando secuencias de PostgreSQL...")
    print("=" * 70)
    
    # Obtener el comando SQL para resetear secuencias
    # Django genera automáticamente los comandos correctos
    sequence_sql = connection.ops.sequence_reset_sql(no_style(), django.apps.apps.get_models())
    
    if sequence_sql:
        print(f"\n📝 Se encontraron {len(sequence_sql)} secuencias para resetear\n")
        
        with connection.cursor() as cursor:
            for sql_command in sequence_sql:
                print(f"   Ejecutando: {sql_command[:80]}...")
                cursor.execute(sql_command)
        
        print("\n" + "=" * 70)
        print("✅ ¡Todas las secuencias se resetearon correctamente!")
        print("\nAhora puedes crear nuevos registros sin problemas.")
        print("=" * 70)
    else:
        print("ℹ️  No se encontraron secuencias que resetear")
        print("   (Esto es normal si usas SQLite en lugar de PostgreSQL)")

if __name__ == '__main__':
    resetear_secuencias()
