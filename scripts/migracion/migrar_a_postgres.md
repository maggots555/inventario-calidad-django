# 🔄 Guía de Migración de SQLite a PostgreSQL

## 📦 Archivos exportados desde SQLite (Windows)
- ✅ `users.json` - Usuarios del sistema (5 KB)
- ✅ `inventario.json` - Datos de inventario (161 KB)
- ✅ `scorecard.json` - Datos de scorecard (671 KB)
- ✅ `servicio_tecnico.json` - Datos de servicio técnico (34 MB)

## 🚀 Pasos para migrar a PostgreSQL en Ubuntu

### 1️⃣ Subir archivos JSON al servidor Ubuntu

Desde tu terminal de Windows (o usa FileZilla/WinSCP):

```powershell
# Opción A: Usando SCP desde PowerShell
scp users.json inventario.json scorecard.json servicio_tecnico.json usuario@ip_servidor:/ruta/proyecto/

# Opción B: Usando VS Code
# - Abre la paleta de comandos (Ctrl+Shift+P)
# - Busca "Remote-SSH: Connect to Host"
# - Conecta a tu servidor
# - Copia los archivos manualmente
```

### 2️⃣ En el servidor Ubuntu (por SSH)

```bash
# Conectarte por SSH
ssh usuario@ip_servidor

# Ir al directorio del proyecto
cd /ruta/tu/proyecto

# Activar entorno virtual (si lo usas)
source venv/bin/activate

# Verificar que estés usando PostgreSQL
python manage.py showmigrations

# IMPORTANTE: Asegúrate de que tu .env en Ubuntu esté configurado con PostgreSQL
# DB_ENGINE=django.db.backends.postgresql
# DB_NAME=nombre_base_datos
# DB_USER=usuario_postgres
# DB_PASSWORD=password_postgres
```

### 3️⃣ Preparar base de datos PostgreSQL (si es nueva)

```bash
# Si la base de datos está vacía, aplicar migraciones primero
python manage.py migrate

# Esto crea todas las tablas necesarias en PostgreSQL
```

### 4️⃣ Importar datos a PostgreSQL

```bash
# Importar en orden (usuarios primero, luego el resto)
python manage.py loaddata users.json
python manage.py loaddata inventario.json
python manage.py loaddata scorecard.json
python manage.py loaddata servicio_tecnico.json

# Si hay errores de integridad, puedes usar --ignorenonexistent
python manage.py loaddata --ignorenonexistent servicio_tecnico.json
```

### 5️⃣ Verificar que todo se importó correctamente

```bash
# Verificar usuarios
python manage.py shell
>>> from django.contrib.auth.models import User
>>> User.objects.count()
>>> exit()

# Verificar inventario
python manage.py shell
>>> from inventario.models import Producto
>>> Producto.objects.count()
>>> exit()

# Probar el servidor
python manage.py runserver 0.0.0.0:8000
```

### 6️⃣ Copiar archivos media (imágenes, documentos)

```bash
# Desde Windows, copiar carpeta media al servidor
scp -r media/ usuario@ip_servidor:/ruta/proyecto/

# O usar rsync para sincronizar
rsync -avz media/ usuario@ip_servidor:/ruta/proyecto/media/
```

## ⚠️ Solución de problemas comunes

### Error: "duplicate key value violates unique constraint"
Significa que ya existen datos en PostgreSQL. Opciones:
```bash
# Opción A: Limpiar base de datos PostgreSQL
python manage.py flush  # ⚠️ CUIDADO: Borra todos los datos

# Opción B: Borrar y recrear base de datos
sudo -u postgres psql
DROP DATABASE nombre_base_datos;
CREATE DATABASE nombre_base_datos;
GRANT ALL PRIVILEGES ON DATABASE nombre_base_datos TO usuario_postgres;
\q
python manage.py migrate
```

### Error: "No such table" o "relation does not exist"
Primero debes correr las migraciones:
```bash
python manage.py migrate
```

### Error de encoding en JSON
Editar el archivo JSON con un editor que soporte UTF-8 (VS Code) y guardar con encoding UTF-8.

## 📋 Checklist final

- [ ] Archivos JSON exportados desde SQLite
- [ ] Archivos subidos al servidor Ubuntu
- [ ] Base de datos PostgreSQL creada y configurada en .env
- [ ] Migraciones aplicadas (`python manage.py migrate`)
- [ ] Datos importados con `loaddata`
- [ ] Archivos media copiados
- [ ] Servidor funciona correctamente
- [ ] Pruebas de login y funcionalidad básica

## 🎯 Verificación de datos

```bash
# Contar registros en cada modelo
python manage.py shell
>>> from django.contrib.auth.models import User
>>> from inventario.models import Producto, Movimiento, Empleado
>>> from scorecard.models import Incidencia
>>> from servicio_tecnico.models import OrdenServicio

>>> print(f"Usuarios: {User.objects.count()}")
>>> print(f"Productos: {Producto.objects.count()}")
>>> print(f"Movimientos: {Movimiento.objects.count()}")
>>> print(f"Empleados: {Empleado.objects.count()}")
>>> print(f"Incidencias: {Incidencia.objects.count()}")
>>> print(f"Órdenes: {OrdenServicio.objects.count()}")
>>> exit()
```

## 💡 Notas importantes

1. **No subas los archivos JSON a Git** - Contienen datos sensibles
2. **Haz backup de PostgreSQL después de importar** - Por seguridad
3. **Los archivos media deben copiarse manualmente** - No están en los JSON
4. **Las contraseñas de usuarios se mantienen** - Están hasheadas en los JSON
5. **Verifica permisos de archivos media en Ubuntu** - `chmod` si es necesario

## 🔐 Backup de PostgreSQL (después de migrar)

```bash
# Crear backup de PostgreSQL
pg_dump -U usuario_postgres nombre_base_datos > backup_postgres_$(date +%Y%m%d).sql

# Restaurar desde backup (si necesitas)
psql -U usuario_postgres nombre_base_datos < backup_postgres_20251119.sql
```
