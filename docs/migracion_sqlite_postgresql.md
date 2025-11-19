# 🔄 Guía de Migración: SQLite → PostgreSQL

## Contexto
Migrar datos desde base de datos SQLite en Windows hacia PostgreSQL en servidor Linux.

---

## ✅ Opción 1: Django dumpdata/loaddata (Recomendado)

### **PASO 1: Exportar datos desde SQLite (En Windows)**

1. Abre **Command Prompt** o **PowerShell** en tu proyecto Django en Windows
2. Navega al directorio del proyecto donde está `manage.py`
3. Activa tu entorno virtual (si tienes uno)
4. Ejecuta:

```cmd
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission --indent 4 > datos_backup.json
```

**EXPLICACIÓN de los parámetros:**
- `--natural-foreign`: Usa identificadores legibles en lugar de IDs numéricos
- `--natural-primary`: Usa claves primarias naturales (como username)
- `-e contenttypes`: Excluye tabla de tipos de contenido (se regenera automáticamente)
- `-e auth.Permission`: Excluye permisos (se regeneran automáticamente)
- `--indent 4`: Formatea el JSON con indentación para que sea legible
- `> datos_backup.json`: Guarda todo en un archivo JSON

**Resultado:** Tendrás un archivo `datos_backup.json` con TODOS tus datos.

---

### **PASO 2: Transferir el archivo al servidor**

**Opción A - SCP (Linux/Mac/Windows con OpenSSH):**
```bash
scp datos_backup.json sicsystem@192.168.1.235:/var/www/inventario-django/inventario-calidad-django/
```

**Opción B - WinSCP (Windows GUI):**
1. Descarga WinSCP: https://winscp.net/
2. Conecta al servidor: 192.168.1.235
3. Usuario: sicsystem
4. Arrastra `datos_backup.json` a `/var/www/inventario-django/inventario-calidad-django/`

**Opción C - Filezilla (Windows/Mac/Linux GUI):**
1. Descarga Filezilla: https://filezilla-project.org/
2. Protocolo: SFTP
3. Host: 192.168.1.235
4. Usuario: sicsystem
5. Sube el archivo

---

### **PASO 3: Preparar PostgreSQL (En el servidor Linux - SSH)**

```bash
# Navegar al proyecto
cd /var/www/inventario-django/inventario-calidad-django

# Activar entorno virtual
source /var/www/inventario-django/venv/bin/activate

# IMPORTANTE: Verificar que settings.py esté usando PostgreSQL
# Ya debería estar configurado según tu .env

# Eliminar base de datos PostgreSQL existente (si tiene datos de prueba)
python manage.py dbshell
```

**En el shell de PostgreSQL, ejecuta:**
```sql
-- Ver tablas existentes
\dt

-- Si quieres empezar desde cero (CUIDADO: esto borra TODO)
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO django_user;
GRANT ALL ON SCHEMA public TO public;

-- Salir
\q
```

---

### **PASO 4: Aplicar migraciones en PostgreSQL**

```bash
# Crear todas las tablas en PostgreSQL
python manage.py migrate

# Verificar que las tablas se crearon
python manage.py dbshell
\dt
\q
```

---

### **PASO 5: Importar datos en PostgreSQL**

```bash
# Cargar los datos desde el archivo JSON
python manage.py loaddata datos_backup.json
```

**Si hay errores de permisos o contenttypes:**
```bash
# Primero migrar auth y contenttypes
python manage.py migrate auth
python manage.py migrate contenttypes

# Luego cargar datos
python manage.py loaddata datos_backup.json
```

---

### **PASO 6: Verificar la migración**

```bash
# Acceder a Django shell
python manage.py shell
```

**Dentro del shell de Django:**
```python
# Verificar modelos principales
from inventario.models import Producto, Movimiento, Sucursal, Empleado
from django.contrib.auth.models import User

# Contar registros
print(f"Productos: {Producto.objects.count()}")
print(f"Movimientos: {Movimiento.objects.count()}")
print(f"Sucursales: {Sucursal.objects.count()}")
print(f"Empleados: {Empleado.objects.count()}")
print(f"Usuarios: {User.objects.count()}")

# Ver algunos registros
print("\nPrimeros 5 productos:")
for p in Producto.objects.all()[:5]:
    print(f"  - {p.nombre}")

# Salir
exit()
```

---

### **PASO 7: Reiniciar servicios**

```bash
# Reiniciar Gunicorn para que use la nueva base de datos
sudo systemctl restart gunicorn

# Verificar que todo funciona
sudo systemctl status gunicorn
```

---

## ⚠️ Solución de Problemas Comunes

### **Error: "contenttypes is not unique"**
```bash
# Exportar SIN contenttypes ni permisos
python manage.py dumpdata --natural-foreign --natural-primary -e contenttypes -e auth.Permission > datos_backup.json
```

### **Error: "IntegrityError: duplicate key"**
```bash
# Limpiar base de datos PostgreSQL y empezar de nuevo
python manage.py dbshell
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO django_user;
\q

python manage.py migrate
python manage.py loaddata datos_backup.json
```

### **Error: "relation does not exist"**
```bash
# Asegurarse de que todas las migraciones están aplicadas
python manage.py migrate --run-syncdb
python manage.py loaddata datos_backup.json
```

### **Archivos media (imágenes, QR codes)**

Si tienes imágenes de productos, QR codes, fotos de empleados, etc.:

```bash
# En Windows, comprimir carpeta media
# Crear archivo media.zip con tu carpeta media/

# Transferir al servidor
scp media.zip sicsystem@192.168.1.235:/var/www/inventario-django/inventario-calidad-django/

# En el servidor, extraer
cd /var/www/inventario-django/inventario-calidad-django
unzip media.zip

# Ajustar permisos
sudo chown -R sicsystem:www-data media/
sudo chmod -R 775 media/
```

---

## 🚀 Opción 2: Usando pgloader (Método Avanzado)

Si `dumpdata/loaddata` no funciona o es muy lento, puedes usar `pgloader`:

### **Instalación en el servidor:**
```bash
sudo apt update
sudo apt install pgloader
```

### **Transferir SQLite al servidor:**
```bash
# Desde Windows (usando SCP o WinSCP)
scp db.sqlite3 sicsystem@192.168.1.235:/tmp/
```

### **Crear script de migración:**
```bash
# En el servidor
nano /tmp/migrate.load
```

**Contenido del archivo:**
```
LOAD DATABASE
    FROM sqlite:///tmp/db.sqlite3
    INTO postgresql://django_user:sicmexico2025%i@localhost/inventario_django

WITH include drop, create tables, create indexes, reset sequences

ALTER SCHEMA 'main' RENAME TO 'public'
;
```

### **Ejecutar migración:**
```bash
pgloader /tmp/migrate.load
```

---

## 📊 Comparación de Métodos

| Método | Ventajas | Desventajas |
|--------|----------|-------------|
| **dumpdata/loaddata** | ✅ Nativo de Django<br>✅ Maneja relaciones correctamente<br>✅ Incluye todos los modelos | ❌ Más lento con muchos datos |
| **pgloader** | ✅ Muy rápido<br>✅ Migración directa | ❌ Puede tener problemas con tipos de datos específicos |

---

## ✅ Checklist Final

- [ ] Exportar datos desde SQLite (`dumpdata`)
- [ ] Transferir archivo JSON al servidor
- [ ] Aplicar migraciones en PostgreSQL (`migrate`)
- [ ] Importar datos (`loaddata`)
- [ ] Verificar conteo de registros
- [ ] Transferir archivos media (si aplica)
- [ ] Reiniciar servicios (`gunicorn`)
- [ ] Probar acceso desde navegador
- [ ] Crear backup de PostgreSQL

---

## 💾 Crear Backup de PostgreSQL (Después de migrar)

```bash
# Backup completo
pg_dump -U django_user -h localhost inventario_django > backup_$(date +%Y%m%d).sql

# Backup comprimido
pg_dump -U django_user -h localhost inventario_django | gzip > backup_$(date +%Y%m%d).sql.gz
```

---

## 🎓 Para Principiantes - Resumen Simple

1. **En Windows**: Exporta datos con `python manage.py dumpdata > datos_backup.json`
2. **Transferir**: Sube `datos_backup.json` al servidor (WinSCP/Filezilla)
3. **En servidor**: Crea tablas con `python manage.py migrate`
4. **En servidor**: Importa datos con `python manage.py loaddata datos_backup.json`
5. **Reiniciar**: `sudo systemctl restart gunicorn`
6. **Probar**: Abre el sitio en el navegador

---

**Documentación oficial Django:**
- https://docs.djangoproject.com/en/5.2/ref/django-admin/#dumpdata
- https://docs.djangoproject.com/en/5.2/ref/django-admin/#loaddata
