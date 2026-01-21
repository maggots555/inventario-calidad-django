# 🚀 COMANDOS RÁPIDOS - SISTEMA DE PERMISOS

## ⚡ Comandos de Un Solo Paso

### Probar que todo funciona:
```bash
./scripts/test_permisos.sh
```

### Gestionar grupos (menú interactivo):
```bash
python scripts/manage_grupos.py
```

### Crear/actualizar grupos y permisos:
```bash
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/setup_grupos_permisos.py').read())"
```

### Asignar grupos a empleados:
```bash
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/asignar_grupos_empleados.py').read())"
```

---

## 📊 Verificación Rápida en Django Shell

### Ver todos los grupos:
```bash
python manage.py shell
```
```python
from django.contrib.auth.models import Group
list(Group.objects.values_list('name', 'permissions__count'))
```

### Ver empleados con grupos:
```python
from inventario.models import Empleado
for e in Empleado.objects.filter(user__isnull=False):
    print(f"{e.nombre_completo}: {e.rol} → {list(e.user.groups.values_list('name', flat=True))}")
```

---

## 🔧 Instalación Inicial (Solo Primera Vez)

```bash
# 1. Aplicar migraciones
python manage.py migrate

# 2. Crear grupos y permisos
python scripts/manage_grupos.py  # Opción 1

# 3. Asignar grupos a empleados existentes
python scripts/manage_grupos.py  # Opción 3

# 4. Verificar que todo está bien
./scripts/test_permisos.sh
```

---

## 🐛 Troubleshooting Rápido

### Si los grupos no existen:
```bash
python scripts/manage_grupos.py  # Opción 1
```

### Si los empleados no tienen grupo:
```bash
python scripts/manage_grupos.py  # Opción 3
```

### Si hay problemas con Django:
```bash
# Activar venv
source venv/bin/activate

# Verificar instalación
python -c "import django; print(django.VERSION)"
```

---

## 📝 Archivos de Documentación

- `SISTEMA_PERMISOS_FUNCIONANDO.md` - Guía completa y verificación
- `docs/SISTEMA_PERMISOS.md` - Documentación técnica detallada
- `scripts/README_PERMISOS.md` - Guía de scripts

---

## ✅ Estado Actual

```
✅ 9 grupos creados
✅ 5 empleados con grupos
✅ Asignación automática activa
✅ Scripts funcionando
✅ Sistema intacto
```

Todo funcionando correctamente! 🎉
