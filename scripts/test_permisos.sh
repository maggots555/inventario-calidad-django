#!/bin/bash

# Script de prueba rápida del sistema de permisos
# Ejecutar desde el directorio raíz: ./scripts/test_permisos.sh

echo "======================================================================="
echo "PRUEBA RÁPIDA DEL SISTEMA DE PERMISOS"
echo "======================================================================="
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "manage.py" ]; then
    echo "❌ Error: Ejecuta este script desde el directorio raíz del proyecto"
    echo "   Ejemplo: ./scripts/test_permisos.sh"
    exit 1
fi

# Verificar entorno virtual
if [ ! -d "venv" ]; then
    echo "⚠️  Advertencia: No se encontró el directorio venv/"
    echo "   Asegúrate de tener el entorno virtual activado"
fi

echo "1️⃣  Probando importación de módulos..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import Group
from inventario.models import Empleado
print('   ✅ Importaciones correctas')
"

if [ $? -ne 0 ]; then
    echo "   ❌ Error en importaciones"
    exit 1
fi

echo ""
echo "2️⃣  Verificando grupos creados..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import Group

grupos = Group.objects.all().count()
if grupos == 9:
    print(f'   ✅ {grupos} grupos encontrados')
else:
    print(f'   ⚠️  Se esperaban 9 grupos, se encontraron {grupos}')
    print('   💡 Ejecuta: python scripts/manage_grupos.py → Opción 1')
"

echo ""
echo "3️⃣  Verificando empleados con grupos..."
python -c "
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from inventario.models import Empleado

empleados_con_user = Empleado.objects.filter(user__isnull=False).count()
empleados_con_grupo = Empleado.objects.filter(user__groups__isnull=False).distinct().count()

print(f'   📊 Empleados con usuario: {empleados_con_user}')
print(f'   📊 Empleados con grupo: {empleados_con_grupo}')

if empleados_con_user > 0 and empleados_con_grupo == 0:
    print('   ⚠️  Hay empleados sin grupo asignado')
    print('   💡 Ejecuta: python scripts/manage_grupos.py → Opción 3')
elif empleados_con_grupo > 0:
    print('   ✅ Empleados tienen grupos asignados')
"

echo ""
echo "4️⃣  Verificando script manage_grupos.py..."
if [ -f "scripts/manage_grupos.py" ]; then
    echo "   ✅ Script manage_grupos.py encontrado"
else
    echo "   ❌ Script manage_grupos.py NO encontrado"
fi

echo ""
echo "======================================================================="
echo "RESULTADO DEL TEST"
echo "======================================================================="
echo ""
echo "✅ Si todo está verde, el sistema está funcionando correctamente"
echo ""
echo "Para gestionar grupos y permisos ejecuta:"
echo "   python scripts/manage_grupos.py"
echo ""
echo "Para ver documentación completa:"
echo "   cat docs/SISTEMA_PERMISOS.md"
echo "   cat scripts/README_PERMISOS.md"
echo ""
echo "======================================================================="
