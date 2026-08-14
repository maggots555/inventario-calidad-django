# Sistema de Permisos con Django Groups

Este documento describe el sistema de roles y permisos implementado usando Django Groups.

## 📋 Roles Disponibles

### 1. SUPERVISOR
- **Permisos**: Acceso general al sistema excepto configuraciones de Django Admin
- **Aplicaciones**: Inventario, Servicio Técnico, Scorecard, Almacén
- **Total permisos**: 97

### 2. INSPECTOR
- **Permisos**: Acceso general al sistema excepto configuraciones de Django Admin
- **Aplicaciones**: Inventario, Servicio Técnico, Scorecard, Almacén
- **Total permisos**: 97

### 3. DISPATCHER
- **Permisos**: Solo lectura en Servicio Técnico
- **Aplicaciones**: Servicio Técnico (solo vista)
- **Total permisos**: 10

### 4. COMPRAS
- **Permisos**: Acceso completo a Servicio Técnico y Almacén
- **Aplicaciones**: Servicio Técnico, Almacén
- **Total permisos**: 66

### 5. RECEPCIONISTA
- **Permisos**: Acceso general en Servicio Técnico y Almacén
- **Aplicaciones**: Servicio Técnico (completo), Almacén (limitado)
- **Total permisos**: 42

### 6. GERENTE OPERACIONAL
- **Permisos**: Acceso general al sistema excepto configuraciones de Django Admin
- **Aplicaciones**: Inventario, Servicio Técnico, Scorecard, Almacén
- **Total permisos**: 97

### 7. GERENTE GENERAL
- **Permisos**: Acceso general al sistema excepto configuraciones de Django Admin
- **Aplicaciones**: Inventario, Servicio Técnico, Scorecard, Almacén
- **Total permisos**: 97

### 8. TÉCNICO
- **Permisos**: Acceso a Servicio Técnico y consulta en Almacén
- **Aplicaciones**: Servicio Técnico (completo), Almacén (consulta)
- **Total permisos**: 38

### 9. ALMACENISTA
- **Permisos**: Acceso completo en Almacén y consulta en Servicio Técnico
- **Aplicaciones**: Almacén (completo), Servicio Técnico (consulta)
- **Total permisos**: 32

### 10. FACTURACIÓN
- **Permisos**: Lectura de órdenes y cotizaciones (ST y Almacén), dashboards gerenciales, y **registro de pagos** (`PagoOrden`)
- **Aplicaciones**: Servicio Técnico (consulta + cobros), Almacén cotizador (consulta), dashboards de dinero
- **No incluye**: crear/editar órdenes, inventario, compras, bajas ni configuración
- **Total permisos**: 20
- **Notas**: Reutiliza `view_dashboard_gerencial`. Puede `add`/`change`/`view` de `PagoOrden` (abonos y comprobantes).

## 🚀 Scripts Disponibles

### 1. Configurar Grupos y Permisos

Crea todos los grupos de Django y asigna los permisos correspondientes:

```bash
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/setup_grupos_permisos.py').read())"
```

### 2. Asignar Grupos a Empleados

Asigna automáticamente grupos a empleados existentes basado en su rol:

```bash
python -c "import os, django; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); exec(open('scripts/asignar_grupos_empleados.py').read())"
```

### 3. Gestión Interactiva

Script con menú interactivo para gestionar grupos:

```bash
python scripts/manage_grupos.py
```

## 📝 Flujo de Implementación

1. **Migración aplicada**: ✅
   - Campo `rol` agregado al modelo Empleado
   - Migración `0014_empleado_rol.py` aplicada

2. **Grupos creados**: ✅
   - 10 grupos de Django creados
   - Permisos asignados a cada grupo

3. **Asignación automática**: ✅
   - Al crear un empleado con acceso al sistema, se asigna automáticamente a su grupo
   - Función `crear_usuario_para_empleado()` actualizada en `inventario/utils.py`

## 🔧 Cómo Funciona

### Al crear un empleado con acceso al sistema:

1. Se selecciona el **rol** en el formulario de empleado
2. Se hace clic en "Dar Acceso" (si no tiene usuario)
3. Sistema automáticamente:
   - Crea usuario de Django
   - Asigna al grupo correspondiente según el rol
   - Envía credenciales por email

### Ejemplo de código:

```python
from inventario.models import Empleado
from inventario.utils import crear_usuario_para_empleado

empleado = Empleado.objects.get(id=1)
empleado.rol = 'tecnico'  # Asignar rol
empleado.save()

# Crear usuario y asignar grupo automáticamente
user, password = crear_usuario_para_empleado(empleado)
# El usuario ahora pertenece al grupo "Técnico" automáticamente
```

## 🔐 Verificar Permisos en Vistas

Para proteger vistas específicas, usa el decorador `@permission_required`:

```python
from django.contrib.auth.decorators import login_required, permission_required

@login_required
@permission_required('servicio_tecnico.add_ordenservicio', raise_exception=True)
def crear_orden(request):
    # Solo usuarios con permiso pueden acceder
    pass
```

## 📊 Estado Actual

- ✅ Campo `rol` agregado al modelo Empleado
- ✅ Formulario actualizado para incluir campo rol
- ✅ Template actualizado para mostrar campo rol
- ✅ 10 grupos de Django creados con permisos
- ✅ Asignación automática de grupos al crear usuarios
- ✅ 5 empleados actualizados con sus grupos
- ✅ Scripts de gestión disponibles

## 🎯 Próximos Pasos (Opcional)

1. Actualizar vistas específicas con `@permission_required`
2. Crear permisos personalizados si se necesitan
3. Implementar verificación de permisos en templates
4. Documentar permisos específicos por vista

## 📚 Recursos

- [Django Permissions](https://docs.djangoproject.com/en/5.2/topics/auth/default/#permissions-and-authorization)
- [Django Groups](https://docs.djangoproject.com/en/5.2/topics/auth/default/#groups)
- [Permission Required Decorator](https://docs.djangoproject.com/en/5.2/topics/auth/default/#the-permission-required-decorator)
