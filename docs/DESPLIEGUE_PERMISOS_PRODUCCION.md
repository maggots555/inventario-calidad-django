# 🚀 Guía de Despliegue de Permisos en Producción

## 📋 Índice
1. [Resumen Ejecutivo](#resumen-ejecutivo)
2. [Prerequisitos](#prerequisitos)
3. [Flujo Recomendado](#flujo-recomendado)
4. [Scripts Disponibles](#scripts-disponibles)
5. [Solución de Problemas](#solución-de-problemas)
6. [Rollback](#rollback)

---

## 🎯 Resumen Ejecutivo

Este sistema de permisos está **LISTO PARA PRODUCCIÓN** con las siguientes características:

✅ **Idempotente**: Puede ejecutarse múltiples veces sin causar problemas
✅ **Seguro**: Incluye verificaciones y backups automáticos
✅ **Compatible**: Funciona con SQLite (desarrollo) y PostgreSQL (producción)
✅ **Automático**: Asignación automática de grupos según rol de empleado
✅ **Validado**: Scripts de verificación pre y post-despliegue

---

## 📦 Prerequisitos

### 1. Base de Datos en Producción
- **PostgreSQL configurado** según `.env.example`
- **Migraciones aplicadas**: `python manage.py migrate`
- **Acceso SSH** al servidor de producción

### 2. Entorno Virtual
```bash
# En el servidor de producción
cd /ruta/al/proyecto
source venv/bin/activate
```

### 3. Archivos Requeridos
Todos estos archivos ya están en tu repositorio:
- ✅ `scripts/setup_grupos_permisos.py`
- ✅ `scripts/asignar_grupos_empleados.py`
- ✅ `scripts/manage_grupos.py`
- ✅ `scripts/test_permisos.sh`
- ✅ `scripts/verificar_pre_produccion.sh` (NUEVO)
- ✅ `scripts/deploy_permisos_produccion.sh` (NUEVO)

---

## 🔄 Flujo Recomendado

### **Opción A: Despliegue Automático** (RECOMENDADO)

Este es el método más seguro y rápido:

```bash
# 1. Conectar al servidor de producción
ssh usuario@servidor-produccion

# 2. Ir al directorio del proyecto
cd /ruta/al/proyecto/inventario-calidad-django

# 3. Activar entorno virtual
source venv/bin/activate

# 4. Ejecutar script de despliegue automático
./scripts/deploy_permisos_produccion.sh
```

**Este script hará automáticamente:**
1. ✅ Verificar entorno virtual
2. ✅ Validar conexión a base de datos
3. ✅ Verificar migraciones aplicadas
4. ✅ Crear backup de grupos actuales
5. ✅ Pedir confirmación al usuario
6. ✅ Crear/actualizar 9 grupos
7. ✅ Asignar permisos a cada grupo
8. ✅ Asignar grupos a empleados
9. ✅ Verificar resultado

**Duración estimada**: 2-3 minutos

---

### **Opción B: Despliegue Manual** (Control total)

Si prefieres ejecutar paso a paso:

#### **PASO 1: Verificación Pre-Despliegue**
```bash
./scripts/verificar_pre_produccion.sh
```

**Verifica:**
- Variables de entorno (.env)
- Conexión a PostgreSQL
- Estado de migraciones
- Permisos personalizados
- Empleados con rol asignado
- Scripts requeridos

**Si todas las verificaciones pasan**, continúa al PASO 2.

#### **PASO 2: Crear Backup Manual** (Opcional pero recomendado)
```bash
# Backup de base de datos PostgreSQL
pg_dump -U usuario_db nombre_db > backup_antes_permisos_$(date +%Y%m%d_%H%M%S).sql

# O usar el script de backup
./scripts/backup_postgres.sh
```

#### **PASO 3: Ejecutar Scripts de Permisos**
```bash
# Opción 1: Menú interactivo
python scripts/manage_grupos.py

# Seleccionar:
# → Opción 1: Crear grupos y permisos
# → Opción 3: Asignar grupos a empleados
# → Opción 4: Ver resumen
```

```bash
# Opción 2: Ejecución directa
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/setup_grupos_permisos.py').read())"

python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/asignar_grupos_empleados.py').read())"
```

#### **PASO 4: Verificación Post-Despliegue**
```bash
./scripts/test_permisos.sh
```

---

## 📜 Scripts Disponibles

### 🆕 `deploy_permisos_produccion.sh` (NUEVO)
**Script principal de despliegue automatizado**

```bash
./scripts/deploy_permisos_produccion.sh
```

**Características:**
- ✅ Verificaciones automáticas
- ✅ Backup automático de grupos
- ✅ Confirmación antes de ejecutar
- ✅ Rollback en caso de error
- ✅ Verificación post-despliegue

---

### 🆕 `verificar_pre_produccion.sh` (NUEVO)
**Verificación exhaustiva antes de aplicar cambios**

```bash
./scripts/verificar_pre_produccion.sh
```

**Verifica:**
1. Variables de entorno (.env)
2. Conexión a base de datos
3. Estado de migraciones
4. Permisos personalizados
5. Empleados en BD
6. Grupos existentes
7. Scripts requeridos

---

### `manage_grupos.py`
**Menú interactivo para gestión de grupos**

```bash
python scripts/manage_grupos.py
```

**Opciones:**
1. Crear grupos y permisos desde cero
2. Actualizar permisos de grupos existentes
3. Asignar grupos a empleados según su rol
4. Ver resumen de grupos y permisos

---

### `test_permisos.sh`
**Verificación rápida del sistema**

```bash
./scripts/test_permisos.sh
```

**Verifica:**
- Importación de módulos
- Grupos creados (esperados: 9)
- Empleados con grupos
- Script manage_grupos.py

---

## 🛠️ Solución de Problemas

### ❌ Error: "No module named 'django'"
**Causa**: Entorno virtual no activado

**Solución**:
```bash
source venv/bin/activate
python scripts/manage_grupos.py
```

---

### ❌ Error: "No module named 'config'"
**Causa**: Ejecutando desde directorio incorrecto

**Solución**:
```bash
cd /ruta/al/proyecto/inventario-calidad-django
python scripts/manage_grupos.py
```

---

### ❌ Error: "django.db.utils.OperationalError: FATAL: password authentication failed"
**Causa**: Credenciales incorrectas en `.env`

**Solución**:
```bash
# Verificar variables en .env
cat .env | grep DB_

# Probar conexión manual
psql -U usuario_db -d nombre_db -h localhost
```

---

### ⚠️ Advertencia: "Hay X migraciones pendientes"
**Causa**: Migraciones no aplicadas

**Solución**:
```bash
python manage.py migrate
```

---

### ⚠️ Advertencia: "Permisos personalizados no encontrados"
**Causa**: Migración de permisos personalizados no aplicada

**Solución**:
```bash
# Esto es NORMAL si no has creado permisos personalizados
# Los scripts continuarán sin problema
# Los permisos personalizados se ignorarán automáticamente
```

---

### ❌ Error: "Empleados sin rol asignado"
**Causa**: Campo `rol` vacío en algunos empleados

**Solución**:
```bash
# Opción 1: Asignar roles desde el admin de Django
http://tu-servidor/admin/inventario/empleado/

# Opción 2: Asignar roles por código
python manage.py shell
>>> from inventario.models import Empleado
>>> emp = Empleado.objects.get(id=1)
>>> emp.rol = 'tecnico'
>>> emp.save()
```

---

## 🔙 Rollback

### Si algo sale mal durante el despliegue:

#### **Opción 1: Restaurar desde backup de grupos**
```bash
# El script crea un backup automático
# Buscar archivo: backup_grupos_YYYYMMDD_HHMMSS.json

python -c "
import os, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()
from django.contrib.auth.models import Group, User

# Leer backup
with open('backup_grupos_20250124_153000.json') as f:
    backup = json.load(f)

# Restaurar grupos (si es necesario)
for grupo_data in backup:
    grupo = Group.objects.get(name=grupo_data['nombre'])
    # Restaurar usuarios del grupo
    for username in grupo_data['usuarios']:
        user = User.objects.get(username=username)
        grupo.user_set.add(user)
"
```

#### **Opción 2: Restaurar base de datos completa**
```bash
# Solo si creaste backup antes
psql -U usuario_db -d nombre_db < backup_antes_permisos_20250124.sql
```

#### **Opción 3: Eliminar grupos y volver a crear**
```bash
python manage.py shell

from django.contrib.auth.models import Group
Group.objects.all().delete()

# Luego ejecutar scripts de nuevo
python scripts/manage_grupos.py
```

---

## 📊 Verificación Final

Después del despliegue, verifica:

### 1. Grupos creados
```bash
python manage.py shell

from django.contrib.auth.models import Group
print(f"Total grupos: {Group.objects.count()}")  # Debe ser 9
for g in Group.objects.all():
    print(f"- {g.name}: {g.permissions.count()} permisos")
```

### 2. Empleados con grupos
```bash
from inventario.models import Empleado
empleados = Empleado.objects.filter(user__isnull=False)
for emp in empleados:
    grupos = emp.user.groups.all()
    print(f"{emp.nombre_completo} ({emp.rol}): {list(grupos)}")
```

### 3. Prueba de acceso
```bash
# Iniciar sesión con diferentes usuarios y verificar acceso
# Ejemplo: usuario técnico NO debe ver módulo de almacén completo
```

---

## 🎯 Resumen de Comandos Rápidos

```bash
# VERIFICACIÓN PRE-DESPLIEGUE
./scripts/verificar_pre_produccion.sh

# DESPLIEGUE AUTOMÁTICO (RECOMENDADO)
./scripts/deploy_permisos_produccion.sh

# DESPLIEGUE MANUAL
python scripts/manage_grupos.py

# VERIFICACIÓN POST-DESPLIEGUE
./scripts/test_permisos.sh
```

---

## 📞 Soporte

Si tienes problemas:
1. Revisa la sección [Solución de Problemas](#solución-de-problemas)
2. Consulta la documentación completa: `docs/SISTEMA_PERMISOS.md`
3. Revisa los logs: `logs/django.log`

---

## ✅ Checklist de Despliegue

- [ ] Backup de base de datos creado
- [ ] Entorno virtual activado
- [ ] Variables de entorno verificadas (`.env`)
- [ ] Migraciones aplicadas
- [ ] Verificación pre-despliegue ejecutada ✅
- [ ] Script de despliegue ejecutado ✅
- [ ] Verificación post-despliegue ejecutada ✅
- [ ] Prueba de acceso por rol completada ✅
- [ ] Documentación actualizada ✅

---

**Fecha de última actualización**: Enero 2026
**Versión del sistema**: Django 5.2.14 | Python 3.12+ | SIGMA v1.0.0
