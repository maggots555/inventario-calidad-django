@echo off
REM Script de prueba rápida del sistema de permisos
REM Ejecutar desde el directorio raíz: scripts\test_permisos.bat

echo =======================================================================
echo PRUEBA RAPIDA DEL SISTEMA DE PERMISOS
echo =======================================================================
echo.

REM Verificar que estamos en el directorio correcto
if not exist "manage.py" (
    echo ❌ Error: Ejecuta este script desde el directorio raiz del proyecto
    echo    Ejemplo: scripts\test_permisos.bat
    pause
    exit /b 1
)

REM Verificar entorno virtual
if not exist "venv" (
    echo ⚠️  Advertencia: No se encontro el directorio venv\
    echo    Asegurate de tener el entorno virtual activado
)

echo 1️⃣  Probando importacion de modulos...
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from django.contrib.auth.models import Group; from inventario.models import Empleado; print('   ✅ Importaciones correctas')"

if errorlevel 1 (
    echo    ❌ Error en importaciones
    pause
    exit /b 1
)

echo.
echo 2️⃣  Verificando grupos creados...
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from django.contrib.auth.models import Group; grupos = Group.objects.all().count(); print(f'   ✅ {grupos} grupos encontrados') if grupos == 9 else print(f'   ⚠️  Se esperaban 9 grupos, se encontraron {grupos}')"

echo.
echo 3️⃣  Verificando empleados con grupos...
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from inventario.models import Empleado; empleados_con_user = Empleado.objects.filter(user__isnull=False).count(); empleados_con_grupo = Empleado.objects.filter(user__groups__isnull=False).distinct().count(); print(f'   📊 Empleados con usuario: {empleados_con_user}'); print(f'   📊 Empleados con grupo: {empleados_con_grupo}'); print('   ✅ Empleados tienen grupos asignados') if empleados_con_grupo > 0 else print('   ⚠️  Hay empleados sin grupo asignado')"

echo.
echo 4️⃣  Verificando script manage_grupos.py...
if exist "scripts\manage_grupos.py" (
    echo    ✅ Script manage_grupos.py encontrado
) else (
    echo    ❌ Script manage_grupos.py NO encontrado
)

echo.
echo =======================================================================
echo RESULTADO DEL TEST
echo =======================================================================
echo.
echo ✅ Si todo esta verde, el sistema esta funcionando correctamente
echo.
echo Para gestionar grupos y permisos ejecuta:
echo    python scripts\manage_grupos.py
echo.
echo Para ver documentacion completa:
echo    type docs\SISTEMA_PERMISOS.md
echo    type scripts\README_PERMISOS.md
echo.
echo =======================================================================
pause
