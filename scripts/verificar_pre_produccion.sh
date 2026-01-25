#!/bin/bash

# Script de verificación PRE-DESPLIEGUE para producción
# Ejecutar ANTES de aplicar permisos en producción

echo "======================================================================="
echo "VERIFICACIÓN PRE-DESPLIEGUE DE PERMISOS"
echo "======================================================================="
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "manage.py" ]; then
    echo "❌ Error: Ejecuta este script desde el directorio raíz del proyecto"
    exit 1
fi

# 1. Verificar variables de entorno
echo "1️⃣  Verificando variables de entorno..."
python -c "
import os
from decouple import config

try:
    db_engine = config('DB_ENGINE')
    print(f'   ✅ DB_ENGINE: {db_engine}')
    
    if 'postgresql' in db_engine:
        print('   ✅ Configurado para PostgreSQL (Producción)')
    else:
        print('   ⚠️  Usando SQLite (Desarrollo)')
except Exception as e:
    print(f'   ❌ Error: {e}')
    exit(1)
"

# 2. Verificar conexión a base de datos
echo ""
echo "2️⃣  Verificando conexión a base de datos..."
python manage.py check --database default
if [ $? -ne 0 ]; then
    echo "   ❌ Error: No se puede conectar a la base de datos"
    exit 1
fi
echo "   ✅ Conexión exitosa"

# 3. Verificar estado de migraciones
echo ""
echo "3️⃣  Verificando migraciones..."
PENDING=$(python manage.py showmigrations --plan | grep "\[ \]" | wc -l)
if [ $PENDING -gt 0 ]; then
    echo "   ⚠️  Hay $PENDING migraciones pendientes"
    echo "   💡 Ejecuta: python manage.py migrate"
    exit 1
else
    echo "   ✅ Todas las migraciones están aplicadas"
fi

# 4. Verificar permisos personalizados
echo ""
echo "4️⃣  Verificando permisos personalizados..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from servicio_tecnico.models import OrdenServicio

ct = ContentType.objects.get_for_model(OrdenServicio)

permisos_esperados = [
    'view_dashboard_gerencial',
    'view_dashboard_seguimiento'
]

faltantes = []
for codename in permisos_esperados:
    try:
        Permission.objects.get(codename=codename, content_type=ct)
        print(f'   ✅ Permiso encontrado: {codename}')
    except Permission.DoesNotExist:
        print(f'   ⚠️  Permiso faltante: {codename}')
        faltantes.append(codename)

if faltantes:
    print('')
    print('   💡 Los permisos faltantes se ignorarán (comportamiento esperado)')
"

# 5. Verificar empleados existentes
echo ""
echo "5️⃣  Verificando empleados en la base de datos..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from inventario.models import Empleado

total_empleados = Empleado.objects.count()
empleados_con_user = Empleado.objects.filter(user__isnull=False).count()
empleados_con_rol = Empleado.objects.exclude(rol='').count()

print(f'   📊 Total empleados: {total_empleados}')
print(f'   📊 Empleados con usuario: {empleados_con_user}')
print(f'   📊 Empleados con rol asignado: {empleados_con_rol}')

if empleados_con_user > 0 and empleados_con_rol < empleados_con_user:
    print('')
    print('   ⚠️  Hay empleados con usuario pero sin rol asignado')
    print('   💡 Asigna roles manualmente desde el admin antes de ejecutar')
"

# 6. Verificar grupos existentes
echo ""
echo "6️⃣  Verificando grupos existentes..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import Group

grupos_existentes = Group.objects.count()
print(f'   📊 Grupos existentes: {grupos_existentes}')

if grupos_existentes == 0:
    print('   ℹ️  No hay grupos creados (se crearán al ejecutar scripts)')
elif grupos_existentes == 9:
    print('   ✅ Ya existen los 9 grupos esperados')
else:
    print(f'   ⚠️  Se esperaban 9 grupos, hay {grupos_existentes}')
"

# 7. Verificar scripts requeridos
echo ""
echo "7️⃣  Verificando scripts requeridos..."
SCRIPTS=(
    "scripts/setup_grupos_permisos.py"
    "scripts/asignar_grupos_empleados.py"
    "scripts/manage_grupos.py"
)

for script in "${SCRIPTS[@]}"; do
    if [ -f "$script" ]; then
        echo "   ✅ $script"
    else
        echo "   ❌ $script NO ENCONTRADO"
        exit 1
    fi
done

echo ""
echo "======================================================================="
echo "RESULTADO DE LA VERIFICACIÓN"
echo "======================================================================="
echo ""
echo "✅ El sistema está listo para aplicar permisos en producción"
echo ""
echo "Siguientes pasos:"
echo "  1. Asegúrate de tener un backup de la base de datos"
echo "  2. Ejecuta: python scripts/manage_grupos.py"
echo "  3. Selecciona opción 1 (Crear grupos y permisos)"
echo "  4. Selecciona opción 3 (Asignar grupos a empleados)"
echo "  5. Verifica: ./scripts/test_permisos.sh"
echo ""
echo "======================================================================="
