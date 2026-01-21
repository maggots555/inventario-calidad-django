# 🔐 Scripts de Gestión de Permisos

## 📋 Scripts Disponibles

### 1. `manage_grupos.py` - Script Principal (RECOMENDADO)
**Descripción**: Menú interactivo para gestionar grupos y permisos.

**Cómo ejecutar**:
```bash
# Desde el directorio raíz del proyecto
python scripts/manage_grupos.py
```

**Opciones del menú**:
1. Crear grupos y permisos desde cero
2. Actualizar permisos de grupos existentes
3. Asignar grupos a empleados según su rol
4. Ver resumen de grupos y permisos
5. Salir

---

### 2. `setup_grupos_permisos.py` - Configurar Grupos
**Descripción**: Crea los 9 grupos de Django y asigna permisos a cada uno.

**Cómo ejecutar**:
```bash
# Opción 1: Usando manage_grupos.py (recomendado)
python scripts/manage_grupos.py
# Luego selecciona la opción 1

# Opción 2: Directamente
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/setup_grupos_permisos.py').read())"
```

**Qué hace**:
- Crea 9 grupos: Supervisor, Inspector, Dispatcher, Compras, Recepcionista, Gerente Operacional, Gerente General, Técnico, Almacenista
- Asigna permisos específicos a cada grupo
- Si el grupo ya existe, actualiza sus permisos

---

### 3. `asignar_grupos_empleados.py` - Asignar Grupos a Empleados
**Descripción**: Asigna grupos a empleados existentes basándose en su campo `rol`.

**Cómo ejecutar**:
```bash
# Opción 1: Usando manage_grupos.py (recomendado)
python scripts/manage_grupos.py
# Luego selecciona la opción 3

# Opción 2: Directamente
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/asignar_grupos_empleados.py').read())"
```

**Qué hace**:
- Obtiene todos los empleados con usuario del sistema
- Lee su campo `rol`
- Asigna el grupo correspondiente
- Limpia grupos anteriores y asigna el nuevo

---

## 🚀 Flujo de Instalación Inicial

### Primera vez que implementas el sistema:

```bash
# Paso 1: Aplicar migraciones (si no están aplicadas)
python manage.py migrate

# Paso 2: Ejecutar script principal
python scripts/manage_grupos.py

# Paso 3: En el menú, ejecutar en orden:
# → Opción 1: Crear grupos y permisos
# → Opción 3: Asignar grupos a empleados
# → Opción 4: Ver resumen (verificar que todo esté correcto)
```

---

## 🔄 Actualizar Permisos

Si cambias la configuración de permisos en `setup_grupos_permisos.py`:

```bash
python scripts/manage_grupos.py
# Opción 2: Actualizar permisos
```

---

## 🐛 Solución de Problemas

### Error: "ModuleNotFoundError: No module named 'django'"
**Solución**: Asegúrate de ejecutar desde el entorno virtual activado:
```bash
source venv/bin/activate  # Linux/Mac
# o
venv\Scripts\activate  # Windows

python scripts/manage_grupos.py
```

### Error: "ModuleNotFoundError: No module named 'config'"
**Solución**: Asegúrate de estar en el directorio raíz del proyecto:
```bash
cd /ruta/al/proyecto/inventario-calidad-django
python scripts/manage_grupos.py
```

### Error: "Group matching query does not exist"
**Solución**: Primero debes crear los grupos:
```bash
python scripts/manage_grupos.py
# Opción 1: Crear grupos y permisos
```

### Los empleados no tienen grupo asignado
**Solución**: Ejecuta el script de asignación:
```bash
python scripts/manage_grupos.py
# Opción 3: Asignar grupos a empleados
```

---

## 📊 Verificar que Todo Funciona

### Desde Django Shell:
```python
python manage.py shell

# Verificar grupos creados
from django.contrib.auth.models import Group
print(Group.objects.all())

# Verificar empleado con grupo
from inventario.models import Empleado
emp = Empleado.objects.filter(user__isnull=False).first()
print(f"Empleado: {emp.nombre_completo}")
print(f"Rol: {emp.rol}")
print(f"Grupos: {emp.user.groups.all()}")
print(f"Permisos: {emp.user.get_all_permissions()}")
```

### Desde el Admin de Django:
1. Ve a: http://localhost:8000/admin/
2. Navega a: Autenticación y autorización → Grupos
3. Verifica que existan los 9 grupos
4. Haz clic en cada grupo para ver sus permisos

---

## 🎯 Integración con tu Flujo de Trabajo

### Al crear un nuevo empleado con acceso:
```
1. Admin crea empleado → Selecciona ROL
2. Admin hace clic en "Dar Acceso"
3. Sistema automáticamente:
   ✅ Crea usuario
   ✅ Asigna al grupo según el rol (AUTOMÁTICO)
   ✅ Envía email con credenciales
```

**No necesitas ejecutar scripts manualmente después de esto**

---

## 📝 Notas Importantes

1. **Ejecutar desde el directorio raíz**: Todos los scripts deben ejecutarse desde el directorio raíz del proyecto.

2. **Entorno virtual activado**: Asegúrate de tener el entorno virtual activado.

3. **Primera instalación**: Solo necesitas ejecutar los scripts UNA VEZ para configurar el sistema inicial.

4. **Actualizaciones**: Solo ejecuta los scripts de nuevo si:
   - Cambias la configuración de permisos
   - Agregas nuevos roles
   - Migras empleados de un sistema anterior

5. **Asignación automática**: Los nuevos empleados se asignan automáticamente a su grupo cuando se les da acceso al sistema.

---

## 🔗 Archivos Relacionados

- `inventario/models.py` - Modelo Empleado con campo `rol`
- `inventario/utils.py` - Función `crear_usuario_para_empleado()` con asignación automática
- `inventario/forms.py` - EmpleadoForm con campo `rol`
- `docs/SISTEMA_PERMISOS.md` - Documentación completa del sistema
