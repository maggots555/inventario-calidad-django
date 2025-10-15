# 🖥️ Guía Completa: Configurar Proyecto Django en Nueva Máquina

## 📋 Información del Proyecto
- **Nombre del proyecto**: Sistema de Gestión de Inventario con Control de Calidad
- **Repositorio GitHub**: https://github.com/maggots555/inventario-calidad-django
- **Framework**: Django 5.2.5
- **Base de datos**: SQLite3
- **Configuración actual**:
  - Usuario Git: Jorge Magos
  - Email Git: jorgemahos@gmail.com

---

## 🎯 Requisitos Previos

### 1. Sistema Operativo
- Windows 10/11 (estas instrucciones son para Windows)
- PowerShell (incluido por defecto)

### 2. Conexión a Internet
- Para descargar Python, Git y dependencias
- Para clonar el repositorio desde GitHub

---

## 🔧 Paso 1: Instalar Python

### Verificar si Python ya está instalado
```powershell
python --version
```

### Si NO está instalado:
1. **Ir a**: https://www.python.org/downloads/
2. **Descargar** la versión más reciente de Python (3.11 o superior)
3. **Ejecutar el instalador** con estas configuraciones IMPORTANTES:
   - ✅ **Marcar "Add Python to PATH"** (muy importante)
   - ✅ **Marcar "Install pip"**
   - Usar configuración predeterminada para el resto

### Verificar instalación:
```powershell
# Verificar Python
python --version

# Verificar pip (gestor de paquetes)
pip --version
```

**Resultado esperado**:
```
Python 3.11.x
pip 23.x.x
```

---

## 🔧 Paso 2: Instalar Git

### Verificar si Git ya está instalado
```powershell
git --version
```

### Si NO está instalado:
1. **Ir a**: https://git-scm.com/download/windows
2. **Descargar** el instalador para Windows
3. **Ejecutar** con configuración predeterminada
4. **Reiniciar** PowerShell después de la instalación

### Verificar instalación:
```powershell
git --version
```

**Resultado esperado**:
```
git version 2.x.x.windows.x
```

---

## 🔧 Paso 3: Configurar Git

**IMPORTANTE**: Usa exactamente estos datos para mantener consistencia:

```powershell
# Configurar nombre (USAR EXACTAMENTE ESTE NOMBRE)
git config --global user.name "Jorge Magos"

# Configurar email (USAR EXACTAMENTE ESTE EMAIL)
git config --global user.email "jorgemahos@gmail.com"

# Verificar configuración
git config --global --list
```

**Resultado esperado**:
```
user.name=Jorge Magos
user.email=jorgemahos@gmail.com
```

---

## 📥 Paso 4: Clonar el Proyecto desde GitHub

### Elegir ubicación del proyecto
```powershell
# Navegar a donde quieres el proyecto (ejemplo: Documentos)
cd C:\Users\TU_USUARIO\Documents

# O crear una carpeta específica para proyectos
mkdir C:\Users\TU_USUARIO\Documents\Proyectos_Django
cd C:\Users\TU_USUARIO\Documents\Proyectos_Django
```

### Clonar el repositorio
```powershell
git clone https://github.com/maggots555/inventario-calidad-django.git
```

### Navegar al proyecto
```powershell
cd inventario-calidad-django
```

**¿Qué hace esto?**
- Descarga TODO el código fuente del proyecto
- Crea una carpeta `inventario-calidad-django`
- Configura automáticamente la conexión con GitHub

---

## 🐍 Paso 5: Configurar Entorno Python

### Verificar que estás en el directorio correcto
```powershell
# Deberías ver archivos como: manage.py, requirements.txt, config/, etc.
dir
```

### Instalar dependencias del proyecto
```powershell
# Instala todas las librerías necesarias (Django, etc.)
pip install -r requirements.txt
```

**¿Qué instala?**
- Django 5.2.5
- Otras dependencias específicas del proyecto

---

## 🗄️ Paso 6: Configurar Base de Datos

### Crear la base de datos SQLite
```powershell
# Aplica las migraciones (crea las tablas en la base de datos)
python manage.py migrate
```

### Crear usuario administrador
```powershell
# Crea un superusuario para acceder al panel admin
python manage.py createsuperuser
```

**Te pedirá**:
- **Username**: (elige el que prefieras, ej: admin)
- **Email**: (tu email personal)
- **Password**: (elige una contraseña segura)
- **Password (again)**: (confirma la contraseña)

### (Opcional) Poblar con datos de prueba
```powershell
# Llena la base de datos con datos de ejemplo
python poblar_sistema.py
python poblar_productos.py
```

---

## 🚀 Paso 7: Ejecutar el Proyecto

### Iniciar el servidor de desarrollo
```powershell
python manage.py runserver
```

**Resultado esperado**:
```
Starting development server at http://127.0.0.1:8000/
Quit the server with CTRL-BREAK.
```

### Acceder a la aplicación
1. **Aplicación principal**: http://127.0.0.1:8000/
2. **Panel administrativo**: http://127.0.0.1:8000/admin/
   - Usuario: el que creaste con `createsuperuser`
   - Contraseña: la que elegiste

### Detener el servidor
- Presiona `Ctrl + C` en la terminal

---

## 🔄 Trabajar con Git (Subir y Sincronizar Cambios)

### Antes de empezar a trabajar (SIEMPRE)
```powershell
# Descargar cambios más recientes de GitHub
git pull origin master
```

### Después de hacer cambios
```powershell
# 1. Ver qué archivos cambiaron
git status

# 2. Agregar todos los cambios
git add .

# 3. Crear un commit con mensaje descriptivo
git commit -m "Descripción clara de los cambios realizados"

# 4. Subir cambios a GitHub
git push origin master
```

### Comandos útiles
```powershell
# Ver historial de cambios
git log --oneline

# Ver estado actual
git status

# Ver diferencias
git diff
```

---

## 🛠️ Comandos Django Útiles

### Gestión de la base de datos
```powershell
# Crear nuevas migraciones (después de cambiar models.py)
python manage.py makemigrations

# Aplicar migraciones
python manage.py migrate

# Ver estado de migraciones
python manage.py showmigrations
```

### Gestión de usuarios
```powershell
# Crear nuevo superusuario
python manage.py createsuperuser

# Cambiar contraseña de usuario
python manage.py changepassword username
```

### Desarrollo
```powershell
# Iniciar servidor
python manage.py runserver

# Iniciar en puerto específico
python manage.py runserver 8080

# Recopilar archivos estáticos (para producción)
python manage.py collectstatic
```

---

## 📁 Estructura del Proyecto

```
inventario-calidad-django/
├── manage.py                 # Script principal de Django
├── requirements.txt          # Dependencias Python
├── README.md                # Documentación del proyecto
├── .gitignore               # Archivos que Git debe ignorar
├── config/                  # Configuración del proyecto
│   ├── settings.py         # Configuraciones Django
│   ├── urls.py             # URLs principales
│   └── wsgi.py             # Configuración servidor web
├── inventario/             # Aplicación principal
│   ├── models.py           # Modelos de datos
│   ├── views.py            # Lógica de negocio
│   ├── forms.py            # Formularios
│   ├── urls.py             # URLs de la app
│   ├── admin.py            # Configuración admin
│   ├── migrations/         # Migraciones de base de datos
│   └── templates/          # Plantillas HTML
├── static/                 # Archivos estáticos (CSS, JS, imágenes)
│   ├── css/
│   ├── js/
│   └── images/
├── templates/              # Plantillas globales
└── pobladores/             # Scripts para datos de prueba
```

---

## ❌ Archivos que NO se sincronizan

Estos archivos se crean localmente en cada máquina (están en `.gitignore`):

- `db.sqlite3` - Base de datos local
- `__pycache__/` - Archivos Python compilados
- `ssl_certs/` - Certificados SSL
- `.env` - Variables de entorno
- `media/` - Archivos subidos por usuarios

**Esto significa**: Cada máquina tendrá su propia base de datos independiente.

---

## 🚨 Solución de Problemas Comunes

### Error: "python no se reconoce como comando"
**Solución**: 
1. Reinstalar Python marcando "Add to PATH"
2. O agregar Python al PATH manualmente
3. Reiniciar PowerShell

### Error: "git no se reconoce como comando"
**Solución**:
1. Reinstalar Git
2. Reiniciar PowerShell
3. Verificar que Git esté en PATH

### Error: "No module named 'django'"
**Solución**:
```powershell
pip install -r requirements.txt
```

### Error: "Permission denied" al hacer git push
**Solución**:
1. Verificar configuración Git
2. Autenticarse en GitHub
3. Usar token de acceso personal si es necesario

### Error al ejecutar migraciones
**Solución**:
```powershell
# Eliminar migraciones conflictivas y recrear
python manage.py migrate --fake-initial
```

---

## 🔐 Configuración Adicional de Seguridad

### Variables de Entorno (Opcional)
Para configuraciones sensibles, crear archivo `.env`:

```bash
SECRET_KEY=tu-secret-key-aqui
DEBUG=True
DATABASE_URL=sqlite:///db.sqlite3
```

### Configurar HTTPS (Opcional)
El proyecto incluye script para generar certificados SSL:

```powershell
python generar_ssl.py
```

---

## 📞 Contacto y Soporte

### Repositorio del Proyecto
- **GitHub**: https://github.com/maggots555/inventario-calidad-django
- **Issues**: Para reportar problemas
- **Wiki**: Documentación adicional

### Recursos de Aprendizaje
- **Django Docs**: https://docs.djangoproject.com/
- **Python Docs**: https://docs.python.org/
- **Git Tutorial**: https://git-scm.com/docs/gittutorial

---

## ✅ Lista de Verificación Final

Antes de considerar la configuración completa, verifica:

- [ ] Python instalado y funcionando (`python --version`)
- [ ] Git instalado y configurado (`git config --global --list`)
- [ ] Proyecto clonado desde GitHub
- [ ] Dependencias instaladas (`pip list` muestra Django)
- [ ] Base de datos creada (`python manage.py migrate`)
- [ ] Superusuario creado (`python manage.py createsuperuser`)
- [ ] Servidor ejecutándose (`python manage.py runserver`)
- [ ] Acceso a aplicación (http://127.0.0.1:8000/)
- [ ] Acceso a admin (http://127.0.0.1:8000/admin/)
- [ ] Git sincronizando correctamente (`git status`)

---

## 🎉 ¡Configuración Completada!

Si todos los pasos anteriores funcionaron correctamente, ya tienes el proyecto Django completamente funcional en la nueva máquina.

**Recuerda**:
- Hacer `git pull` antes de trabajar
- Hacer `git push` después de cambios importantes
- Mantener las dependencias actualizadas
- Hacer backups regulares de tu base de datos local

¡Feliz programación! 🚀