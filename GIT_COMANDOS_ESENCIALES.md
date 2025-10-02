# 🔄 Comandos Git Esenciales - Flujo de Trabajo Diario

## 🎯 Flujo Básico de Trabajo

### ✅ **Secuencia COMPLETA (Memoriza esto)**

```powershell
# 1. ANTES de trabajar - Sincronizar con GitHub
git pull origin master

# 2. [TRABAJAR EN TU CÓDIGO]
# - Modificar archivos Python
# - Cambiar templates HTML
# - Actualizar CSS/JavaScript
# - Agregar nuevas funcionalidades

# 3. DESPUÉS de trabajar - Subir cambios
git status                           # Ver qué archivos cambiaron
git add .                           # Agregar TODOS los cambios
git commit -m "Descripción clara"   # Crear punto de guardado
git push origin master             # Subir a GitHub
```

---

## 📋 **Comandos Paso a Paso**

### 🔽 **1. Antes de Trabajar**
```powershell
# OPCIÓN 1: Solo REVISAR si hay cambios nuevos (sin descargar)
git fetch

# Ver si hay cambios después del fetch
git status

# OPCIÓN 2: Descargar e integrar cambios directamente
git pull origin master
```
**¿Cuál usar?**
- **`git fetch`**: Solo pregunta "¿hay algo nuevo?" pero NO descarga los archivos a tu proyecto. Útil para verificar antes de descargar.
- **`git pull`**: Descarga Y aplica los cambios automáticamente. Es más directo.

**¿Por qué?** Asegura que tienes la versión más actualizada antes de hacer cambios.

### 🔍 **2. Durante el Trabajo**
```powershell
# Ver estado actual (opcional, pero útil)
git status

# Ver diferencias de lo que has cambiado (opcional)
git diff
```

### 📤 **3. Después de Trabajar**

#### **3a. Verificar cambios**
```powershell
git status
```
**Te muestra**: Qué archivos modificaste, agregaste o eliminaste.

#### **3b. Agregar archivos al staging area**
```powershell
# Agregar TODOS los cambios
git add .

# O agregar archivos específicos
git add nombre_archivo.py
git add inventario/views.py
```

#### **3c. Crear commit (punto de guardado)**
```powershell
git commit -m "Descripción clara de los cambios"
```

**Ejemplos de buenos mensajes**:
- `"Agregué validación de stock mínimo en productos"`
- `"Corregí error en formulario de empleados"`
- `"Mejoré diseño del dashboard principal"`
- `"Implementé búsqueda por código QR"`

#### **3d. Subir a GitHub**
```powershell
git push origin master
```

---

## 🚨 **Comandos de Emergencia**

### **Si algo sale mal**
```powershell
# Ver historial de commits
git log --oneline

# Deshacer cambios NO guardados (¡CUIDADO!)
git checkout -- nombre_archivo.py

# Ver configuración actual
git config --global --list

# Ver repositorio remoto configurado
git remote -v
```

### **Si olvidaste hacer pull**
```powershell
# Forzar sincronización (si hay conflictos)
git pull origin master --rebase
```

---

## 📝 **Comandos de Información**

### **Estado y verificación**
```powershell
# Ver qué cambios tienes pendientes
git status

# Ver historial de commits (últimos 10)
git log --oneline -10

# Ver diferencias sin hacer commit
git diff

# Ver diferencias de archivos en staging
git diff --staged
```

### **Configuración**
```powershell
# Ver configuración de usuario
git config --global user.name
git config --global user.email

# Ver toda la configuración
git config --global --list
```

---

## 🎯 **Flujo Específico por Situación**

### **📅 Inicio del día de trabajo**
```powershell
cd C:\ruta\a\tu\proyecto\inventario-calidad-django
git pull origin master
python manage.py runserver
```

### **📝 Durante el desarrollo**
```powershell
# Verificar qué has cambiado (cada cierto tiempo)
git status
git diff
```

### **🏁 Final del día de trabajo**
```powershell
git status
git add .
git commit -m "Descripción del trabajo realizado hoy"
git push origin master
```

### **🔄 Al cambiar de máquina**
```powershell
# En la nueva máquina, SIEMPRE antes de trabajar:
git pull origin master

# Después de trabajar:
git add .
git commit -m "Cambios desde [nombre de la máquina]"
git push origin master
```

---

## ⚠️ **Errores Comunes y Soluciones**

### **Error: "Your branch is behind"**
```powershell
# Solución: Hacer pull primero
git pull origin master
# Luego continuar con tu flujo normal
```

### **Error: "Please tell me who you are"**
```powershell
# Solución: Configurar identidad
git config --global user.name "Jorge Magos"
git config --global user.email "jorgemahos@gmail.com"
```

### **Error: "Nothing to commit"**
```powershell
# Significa: No has hecho cambios
# Verificar con: git status
# Si hay cambios, usar: git add .
```

### **Olvidaste el mensaje del commit**
```powershell
# Si aparece un editor, escribe el mensaje y presiona:
# Ctrl + X (nano) o :wq (vim) o Ctrl + C (cerrar)
```

---

## 🏷️ **Comandos para Archivos Específicos**

### **Agregar archivos por tipo**
```powershell
# Solo archivos Python
git add *.py

# Solo templates
git add inventario/templates/

# Solo archivos CSS
git add static/css/

# Solo un archivo específico
git add inventario/views.py
```

### **Ignorar cambios temporalmente**
```powershell
# Ver archivos ignorados
cat .gitignore

# Ignorar archivo específico temporalmente
git update-index --skip-worktree archivo.py
```

---

## 📊 **Comandos de Historial**

```powershell
# Ver últimos 5 commits
git log --oneline -5

# Ver cambios de un commit específico
git show [hash_del_commit]

# Ver quién cambió qué en un archivo
git blame archivo.py

# Ver historial de un archivo específico
git log --follow archivo.py
```

---

## 🎯 **Tu Rutina Diaria Resumida**

### **🌅 Al empezar:**
```powershell
git pull origin master
```

### **⚡ Al terminar una funcionalidad:**
```powershell
git add .
git commit -m "Descripción de la funcionalidad"
git push origin master
```

### **🌙 Al terminar el día:**
```powershell
git status  # Verificar que todo esté subido
git log --oneline -3  # Ver últimos commits
```

---

## 🎓 **Consejos Pro**

1. **Haz commits frecuentes**: No esperes a tener 50 cambios
2. **Mensajes descriptivos**: Tu yo del futuro te lo agradecerá
3. **Siempre pull antes de push**: Evita conflictos
4. **Verifica con git status**: Antes y después de cada operación
5. **Backup mental**: GitHub ES tu backup, úsalo frecuentemente

---

## 🔗 **Links Útiles**

- **Tu repositorio**: https://github.com/maggots555/inventario-calidad-django
- **Configuración**: `SETUP_NUEVA_MAQUINA.md`
- **Git Docs**: https://git-scm.com/docs

---

## 📱 **Comandos de Una Línea (Para Copiar Rápido)**

```powershell
# Flujo completo estándar
git pull origin master && git add . && git commit -m "Cambios realizados" && git push origin master

# Solo verificar estado
git status

# Solo sincronizar
git pull origin master

# Solo subir cambios (después de add y commit)
git push origin master
```

---

**💡 Tip**: Guarda este archivo como favorito y consúltalo hasta que memorices el flujo básico.