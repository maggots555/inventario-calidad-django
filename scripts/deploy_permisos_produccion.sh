#!/bin/bash

# Script de despliegue de permisos para PRODUCCIÓN
# Ejecuta verificaciones y aplica permisos de forma segura

echo "======================================================================="
echo "DESPLIEGUE DE PERMISOS EN PRODUCCIÓN"
echo "======================================================================="
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "manage.py" ]; then
    echo "❌ Error: Ejecuta este script desde el directorio raíz del proyecto"
    echo "   Ejemplo: ./scripts/deploy_permisos_produccion.sh"
    exit 1
fi

# Verificar entorno virtual
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Activando entorno virtual..."
    if [ -d "venv" ]; then
        source venv/bin/activate || {
            echo "❌ Error: No se pudo activar venv"
            exit 1
        }
        echo "   ✅ Entorno virtual activado"
    else
        echo "❌ Error: No se encontró directorio venv/"
        echo "   Asegúrate de tener el entorno virtual en el directorio 'venv'"
        exit 1
    fi
fi

# PASO 1: Ejecutar verificaciones pre-despliegue
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "PASO 1: VERIFICACIONES PRE-DESPLIEGUE"
echo "═══════════════════════════════════════════════════════════════════════"
./scripts/verificar_pre_produccion.sh
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Las verificaciones fallaron. Corrige los errores antes de continuar."
    exit 1
fi

# PASO 2: Crear backup de grupos actuales (si existen)
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "PASO 2: BACKUP DE GRUPOS ACTUALES"
echo "═══════════════════════════════════════════════════════════════════════"
python -c "
import os, django, json
from datetime import datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import Group

grupos = Group.objects.all()
if grupos.exists():
    backup_data = []
    for grupo in grupos:
        backup_data.append({
            'nombre': grupo.name,
            'usuarios': list(grupo.user_set.values_list('username', flat=True)),
            'permisos': grupo.permissions.count()
        })
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f'backup_grupos_{timestamp}.json'
    
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, indent=2, ensure_ascii=False)
    
    print(f'   ✅ Backup creado: {backup_file}')
else:
    print('   ℹ️  No hay grupos existentes, no se requiere backup')
"

# PASO 3: Confirmar con el usuario
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "CONFIRMACIÓN"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
echo "Este proceso hará lo siguiente:"
echo "  1. Crear/actualizar 9 grupos de Django"
echo "  2. Asignar permisos a cada grupo"
echo "  3. Asignar grupos a empleados según su rol"
echo ""
read -p "¿Deseas continuar? (s/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo ""
    echo "❌ Operación cancelada por el usuario"
    exit 0
fi

# PASO 4: Crear grupos y permisos
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "PASO 3: CREANDO GRUPOS Y PERMISOS"
echo "═══════════════════════════════════════════════════════════════════════"
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
exec(open('scripts/setup_grupos_permisos.py').read())
"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Error al crear grupos y permisos"
    exit 1
fi

# PASO 5: Asignar grupos a empleados
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "PASO 4: ASIGNANDO GRUPOS A EMPLEADOS"
echo "═══════════════════════════════════════════════════════════════════════"
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
exec(open('scripts/asignar_grupos_empleados.py').read())
"

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Error al asignar grupos a empleados"
    exit 1
fi

# PASO 6: Verificación post-despliegue
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "PASO 5: VERIFICACIÓN POST-DESPLIEGUE"
echo "═══════════════════════════════════════════════════════════════════════"
./scripts/test_permisos.sh

# PASO 7: Resumen final
echo ""
echo "═══════════════════════════════════════════════════════════════════════"
echo "DESPLIEGUE COMPLETADO"
echo "═══════════════════════════════════════════════════════════════════════"
echo ""
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import Group
from inventario.models import Empleado

total_grupos = Group.objects.count()
total_empleados_con_grupo = Empleado.objects.filter(user__groups__isnull=False).distinct().count()

print(f'✅ Grupos creados: {total_grupos}')
print(f'✅ Empleados con grupo asignado: {total_empleados_con_grupo}')
print('')
print('📋 Próximos pasos:')
print('   1. Verifica que los permisos funcionen correctamente')
print('   2. Prueba el acceso de cada rol en el sistema')
print('   3. Consulta la documentación: docs/SISTEMA_PERMISOS.md')
"

echo ""
echo "═══════════════════════════════════════════════════════════════════════"
