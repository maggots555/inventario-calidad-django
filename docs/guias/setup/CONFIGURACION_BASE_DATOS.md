# 🗄️ Guía de Configuración de Base de Datos

## 📋 Descripción General

Este proyecto está configurado para funcionar con **dos tipos de bases de datos**:

- **SQLite**: Para desarrollo local en Windows (simple, sin servidor)
- **PostgreSQL**: Para pruebas y producción en Linux (robusto, profesional)

La configuración detecta automáticamente qué motor estás usando y aplica las optimizaciones correspondientes.

---

## 🔧 Configuración para Desarrollo Local (SQLite)

### ✅ Ventajas de SQLite
- No requiere instalación de servidor de base de datos
- Archivo único (`db.sqlite3`) fácil de respaldar
- Ideal para desarrollo y pruebas locales
- Funciona perfectamente en Windows

### 📝 Configuración en `.env`

```env
# Base de datos SQLite (desarrollo local)
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
DB_USER=
DB_PASSWORD=
DB_HOST=
DB_PORT=
```

### 🚀 Comandos para Inicializar

```bash
# 1. Activar entorno virtual
.venv\Scripts\Activate.ps1

# 2. Aplicar migraciones
python manage.py migrate

# 3. Crear superusuario
python manage.py createsuperuser

# 4. Iniciar servidor
python manage.py runserver
```

---

## 🐘 Configuración para Servidor Linux (PostgreSQL)

### ✅ Ventajas de PostgreSQL
- Mayor rendimiento con múltiples usuarios simultáneos
- Mejor para entornos de producción
- Soporta operaciones concurrentes sin bloqueos
- Sistema de optimización de conexiones incluido

### 📝 Configuración en `.env`

```env
# Base de datos PostgreSQL (producción/pruebas)
DB_ENGINE=django.db.backends.postgresql
DB_NAME=inventario_django
DB_USER=django_user
DB_PASSWORD=tu_password_seguro
DB_HOST=localhost
DB_PORT=5432
```

### 🔐 Instalación de PostgreSQL en Ubuntu

```bash
# 1. Actualizar sistema
sudo apt update && sudo apt upgrade -y

# 2. Instalar PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# 3. Iniciar servicio
sudo systemctl start postgresql
sudo systemctl enable postgresql

# 4. Acceder a PostgreSQL
sudo -u postgres psql

# 5. Crear base de datos y usuario
CREATE DATABASE inventario_django;
CREATE USER django_user WITH PASSWORD 'tu_password_seguro';
ALTER ROLE django_user SET client_encoding TO 'utf8';
ALTER ROLE django_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE django_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE inventario_django TO django_user;
\q

# 6. Instalar psycopg2 (driver de PostgreSQL para Python)
pip install psycopg2-binary
```

### 🚀 Comandos para Inicializar

```bash
# 1. Activar entorno virtual
source .venv/bin/activate

# 2. Aplicar migraciones
python manage.py migrate

# 3. Crear superusuario
python manage.py createsuperuser

# 4. Iniciar servidor (desarrollo)
python manage.py runserver 0.0.0.0:8000

# 5. O usar Gunicorn (producción)
gunicorn config.wsgi:application --bind 0.0.0.0:8000
```

---

## ⚙️ Optimizaciones Automáticas

### 🎯 PostgreSQL (Aplicadas Automáticamente)

El sistema detecta cuando usas PostgreSQL y aplica estas optimizaciones:

```python
DATABASES['default']['CONN_MAX_AGE'] = 600  # Mantener conexiones 10 minutos
DATABASES['default']['OPTIONS'] = {
    'connect_timeout': 10,  # Timeout de conexión 10 segundos
}
```

**¿Qué hacen estas optimizaciones?**

- **CONN_MAX_AGE**: Reutiliza conexiones existentes en lugar de crear nuevas en cada petición
  - Mejora el rendimiento significativamente
  - Reduce errores de timeout en PostgreSQL
  - Solo aplica a PostgreSQL (múltiples conexiones simultáneas)

- **connect_timeout**: Limita el tiempo de espera para conectar
  - Evita que el servidor se quede esperando indefinidamente
  - Falla rápido si hay problemas de conexión
  - Mejora la experiencia del usuario

### 🎯 SQLite (Sin Optimizaciones)

Para SQLite **NO se aplican** estas optimizaciones porque:

- SQLite solo permite una escritura a la vez
- `CONN_MAX_AGE` puede causar errores "database is locked"
- SQLite no soporta `connect_timeout` (opción específica de PostgreSQL)

La configuración se mantiene simple y predeterminada para SQLite.

---

## 🔍 Sistema de Logging

El proyecto incluye un sistema de logging profesional que funciona en ambos entornos:

### 📁 Archivos de Log Generados

```
logs/
├── django_errors.log    # Errores críticos (500, excepciones)
├── django_debug.log     # Información de depuración
└── django_db.log        # Consultas SQL (advertencias y errores)
```

### 📝 Características del Logging

- **Creación automática**: El directorio `logs/` se crea automáticamente
- **Compatible multi-plataforma**: Funciona en Windows, Linux y Mac
- **Rotación automática**: Los archivos grandes se rotan automáticamente
  - `django_errors.log`: Máximo 10 MB, 5 respaldos
  - `django_debug.log`: Máximo 10 MB, 3 respaldos
  - `django_db.log`: Máximo 5 MB, 3 respaldos

### 🔎 Cómo Revisar Logs

**En Windows (PowerShell):**
```powershell
# Ver últimas 50 líneas de errores
Get-Content logs\django_errors.log -Tail 50

# Ver logs en tiempo real
Get-Content logs\django_errors.log -Wait -Tail 10
```

**En Linux (Bash):**
```bash
# Ver últimas 50 líneas de errores
tail -n 50 logs/django_errors.log

# Ver logs en tiempo real
tail -f logs/django_errors.log
```

---

## 🚨 Solución de Problemas Comunes

### ❌ Error: "database is locked" (SQLite)

**Causa**: Múltiples procesos intentando escribir simultáneamente

**Solución**:
1. Asegúrate de que solo una instancia del servidor esté corriendo
2. Cierra todas las conexiones de DB Browser o herramientas similares
3. Reinicia el servidor de desarrollo

### ❌ Error: "FATAL: password authentication failed" (PostgreSQL)

**Causa**: Credenciales incorrectas en `.env`

**Solución**:
1. Verifica que `DB_USER` y `DB_PASSWORD` sean correctos
2. Confirma que el usuario tenga permisos en la base de datos:
   ```sql
   GRANT ALL PRIVILEGES ON DATABASE inventario_django TO django_user;
   ```

### ❌ Error: "could not connect to server" (PostgreSQL)

**Causa**: Servidor PostgreSQL no está corriendo

**Solución Linux**:
```bash
sudo systemctl status postgresql
sudo systemctl start postgresql
```

**Solución Windows**:
- Verificar que PostgreSQL esté instalado y corriendo en Servicios

### ❌ Error: "FileNotFoundError: logs/django_errors.log"

**Causa**: Este error ya está solucionado en la versión actual

**Confirmación**: El directorio `logs/` ahora se crea automáticamente con:
```python
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)
```

---

## 📊 Comparación de Rendimiento

| Característica | SQLite | PostgreSQL |
|----------------|--------|------------|
| **Instalación** | ✅ Incluido | ⚙️ Requiere instalación |
| **Usuarios simultáneos** | ⚠️ Limitado | ✅ Excelente |
| **Escrituras concurrentes** | ❌ Una a la vez | ✅ Múltiples |
| **Velocidad lectura** | ✅ Muy rápido | ✅ Muy rápido |
| **Velocidad escritura** | ✅ Rápido (bajo volumen) | ✅ Rápido (alto volumen) |
| **Tamaño máximo DB** | ⚠️ ~281 TB | ✅ Ilimitado |
| **Respaldo** | ✅ Copiar archivo | ⚙️ Herramientas especiales |
| **Ideal para** | 🏠 Desarrollo local | 🏢 Producción |

---

## 🎓 Recomendaciones de Uso

### 💻 Desarrollo Local (Windows)
```env
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
```

✅ **Usa SQLite cuando:**
- Estás desarrollando en tu computadora personal
- Quieres una configuración simple sin servidores
- Estás probando nuevas funcionalidades
- Trabajas solo en el proyecto

### 🚀 Servidor de Pruebas/Producción (Linux)
```env
DB_ENGINE=django.db.backends.postgresql
DB_NAME=inventario_django
DB_USER=django_user
DB_PASSWORD=tu_password_seguro
```

✅ **Usa PostgreSQL cuando:**
- Vas a desplegar en un servidor
- Necesitas múltiples usuarios simultáneos
- Requieres alto rendimiento en producción
- Trabajas en equipo con acceso compartido

---

## 📚 Referencias Adicionales

- [Django Database Documentation](https://docs.djangoproject.com/en/5.2/ref/databases/)
- [PostgreSQL Official Docs](https://www.postgresql.org/docs/)
- [SQLite Documentation](https://www.sqlite.org/docs.html)
- [Django Logging](https://docs.djangoproject.com/en/5.2/topics/logging/)

---

## ✅ Checklist de Configuración

### Desarrollo Local (SQLite)
- [ ] Archivo `.env` configurado con `DB_ENGINE=django.db.backends.sqlite3`
- [ ] Migraciones aplicadas con `python manage.py migrate`
- [ ] Superusuario creado
- [ ] Servidor funcionando sin errores
- [ ] Logs generándose correctamente en `logs/`

### Servidor Producción (PostgreSQL)
- [ ] PostgreSQL instalado y corriendo
- [ ] Base de datos y usuario creados
- [ ] Archivo `.env` configurado con credenciales de PostgreSQL
- [ ] `psycopg2-binary` instalado en el entorno virtual
- [ ] Migraciones aplicadas
- [ ] Superusuario creado
- [ ] Gunicorn configurado (opcional)
- [ ] Logs funcionando correctamente
- [ ] Respaldos automáticos configurados

---

**Última actualización**: 25 de Noviembre, 2025
**Mantenedor**: Sistema de Inventario Django Team
