#!/bin/bash

# Script de despliegue de permisos para PRODUCCION
# Con soporte Multi-Pais (v2.0)
#
# EXPLICACION PARA PRINCIPIANTES:
# Este script ejecuta toda la cadena de creacion de grupos y permisos
# de forma segura, con verificaciones antes y despues.
#
# SOPORTE MULTI-PAIS:
# Ahora ejecuta los pasos en TODAS las bases de datos configuradas,
# o puedes especificar una BD especifica con --database=NOMBRE.
#
# FORMAS DE EJECUTAR:
#   ./scripts/deploy_permisos_produccion.sh                      # Todas las BDs
#   ./scripts/deploy_permisos_produccion.sh --database=argentina  # Solo Argentina
#   ./scripts/deploy_permisos_produccion.sh --database=default    # Solo Mexico

echo "======================================================================="
echo "DESPLIEGUE DE PERMISOS EN PRODUCCION (Multi-Pais)"
echo "======================================================================="
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "manage.py" ]; then
    echo "Error: Ejecuta este script desde el directorio raiz del proyecto"
    echo "   Ejemplo: ./scripts/deploy_permisos_produccion.sh"
    exit 1
fi

# Verificar entorno virtual
if [ -z "$VIRTUAL_ENV" ]; then
    echo "  Activando entorno virtual..."
    if [ -d "venv" ]; then
        source venv/bin/activate || {
            echo "Error: No se pudo activar venv"
            exit 1
        }
        echo "   Entorno virtual activado"
    else
        echo "Error: No se encontro directorio venv/"
        echo "   Asegurate de tener el entorno virtual en el directorio 'venv'"
        exit 1
    fi
fi

# Detectar base de datos objetivo
DB_TARGET=""
for arg in "$@"; do
    case $arg in
        --database=*)
            DB_TARGET="${arg#*=}"
            ;;
    esac
done

if [ -n "$DB_TARGET" ]; then
    echo "Base de datos objetivo: $DB_TARGET"
else
    echo "Base de datos objetivo: TODAS"
fi

# PASO 1: Ejecutar verificaciones pre-despliegue
echo ""
echo "======================================================================="
echo "PASO 1: VERIFICACIONES PRE-DESPLIEGUE"
echo "======================================================================="
if [ -f "./scripts/verificar_pre_produccion.sh" ]; then
    ./scripts/verificar_pre_produccion.sh
    if [ $? -ne 0 ]; then
        echo ""
        echo "Error: Las verificaciones fallaron. Corrige los errores antes de continuar."
        exit 1
    fi
else
    echo "  Script de verificacion no encontrado, continuando..."
fi

# PASO 2: Crear backup de grupos actuales (si existen)
echo ""
echo "======================================================================="
echo "PASO 2: BACKUP DE GRUPOS ACTUALES"
echo "======================================================================="
python -c "
import os, django, json
from datetime import datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import Group
from django.conf import settings

# Determinar en que BDs hacer backup
db_target = '$DB_TARGET'
if db_target:
    databases = [db_target]
else:
    databases = [alias for alias in settings.DATABASES if alias != 'mexico']

for db_alias in databases:
    grupos = Group.objects.using(db_alias).all()
    if grupos.exists():
        backup_data = {
            'database': db_alias,
            'grupos': []
        }
        for grupo in grupos:
            backup_data['grupos'].append({
                'nombre': grupo.name,
                'usuarios': list(grupo.user_set.values_list('username', flat=True)),
                'permisos': grupo.permissions.count()
            })

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'backup_grupos_{db_alias}_{timestamp}.json'

        with open(backup_file, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2, ensure_ascii=False)

        print(f'  Backup creado: {backup_file} ({db_alias})')
    else:
        print(f'  No hay grupos existentes en {db_alias}, no se requiere backup')
"

# PASO 3: Confirmar con el usuario
echo ""
echo "======================================================================="
echo "CONFIRMACION"
echo "======================================================================="
echo ""
echo "Este proceso hara lo siguiente:"
echo "  1. Crear/actualizar 9 grupos de Django"
echo "  2. Asignar permisos a cada grupo"
echo "  3. Asignar grupos a empleados segun su rol"
if [ -n "$DB_TARGET" ]; then
    echo "  Base de datos: $DB_TARGET"
else
    echo "  En TODAS las bases de datos configuradas"
fi
echo ""
read -p "Deseas continuar? (s/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Ss]$ ]]; then
    echo ""
    echo "Operacion cancelada por el usuario"
    exit 0
fi

# PASO 4: Crear grupos, permisos y asignar a empleados
echo ""
echo "======================================================================="
echo "PASO 3: CREANDO GRUPOS, PERMISOS Y ASIGNANDO A EMPLEADOS"
echo "======================================================================="

if [ -n "$DB_TARGET" ]; then
    # Solo una BD especifica
    python scripts/manage_grupos.py --database="$DB_TARGET"
else
    # Todas las BDs
    python scripts/manage_grupos.py --todos
fi

if [ $? -ne 0 ]; then
    echo ""
    echo "Error al crear grupos y permisos"
    exit 1
fi

# PASO 5: Verificacion post-despliegue
echo ""
echo "======================================================================="
echo "PASO 4: VERIFICACION POST-DESPLIEGUE"
echo "======================================================================="
if [ -f "./scripts/test_permisos.sh" ]; then
    ./scripts/test_permisos.sh
fi

# PASO 6: Resumen final
echo ""
echo "======================================================================="
echo "DESPLIEGUE COMPLETADO"
echo "======================================================================="
echo ""
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import Group
from django.conf import settings
from inventario.models import Empleado

db_target = '$DB_TARGET'
if db_target:
    databases = [(db_target, db_target.capitalize())]
else:
    databases = [(alias, alias.capitalize()) for alias in settings.DATABASES if alias != 'mexico']

for db_alias, nombre in databases:
    total_grupos = Group.objects.using(db_alias).count()
    total_empleados = Empleado.objects.using(db_alias).filter(user__groups__isnull=False).distinct().count()

    print(f'  {nombre} ({db_alias}):')
    print(f'     Grupos creados: {total_grupos}')
    print(f'     Empleados con grupo: {total_empleados}')
    print()

print('Proximos pasos:')
print('   1. Verifica que los permisos funcionen correctamente')
print('   2. Prueba el acceso de cada rol en el sistema')
print('   3. Consulta la documentacion: docs/SISTEMA_PERMISOS.md')
"

echo ""
echo "======================================================================="
