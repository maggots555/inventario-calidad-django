# Inventario de Calidad

Sistema básico de inventario con control de calidad desarrollado en Django.

## Características

- ✅ Gestión de productos (CRUD completo)
- ✅ Control de calidad (Bueno, Regular, Malo)
- ✅ Interfaz moderna con Bootstrap
- ✅ Panel de administración configurado
- ✅ Mensajes de confirmación para el usuario

## Instalación

1. **Clonar el repositorio**
```bash
git clone [tu-repo]
cd inventario_calidad
```

2. **Crear y activar entorno virtual**
```bash
python -m venv venv
# En Windows:
venv\Scripts\activate
# En macOS/Linux:
source venv/bin/activate
```

3. **Instalar dependencias**
```bash
pip install -r requirements.txt
```

4. **Configurar base de datos**
```bash
python manage.py makemigrations
python manage.py migrate
```

5. **Crear superusuario (opcional)**
```bash
python manage.py createsuperuser
```

6. **Ejecutar el servidor**
```bash
python manage.py runserver
```

## Uso

### Acceso a la aplicación
- **Página principal**: http://127.0.0.1:8000/
- **Panel de administración**: http://127.0.0.1:8000/admin/

### Funcionalidades principales

1. **Lista de productos**: Ver todos los productos registrados
2. **Agregar producto**: Crear nuevos productos con información básica
3. **Editar producto**: Modificar información existente
4. **Eliminar producto**: Remover productos del inventario
5. **Control de calidad**: Asignar estados de calidad a cada producto

## Estructura del Proyecto

```
inventario_calidad/
├── config/                 # Configuración del proyecto Django
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── inventario/            # App principal
│   ├── models.py          # Modelo Producto
│   ├── views.py           # Vistas del CRUD
│   ├── forms.py           # Formularios
│   ├── urls.py            # URLs de la app
│   └── templates/         # Templates de la app
├── templates/             # Templates base
│   └── base.html
├── manage.py
└── requirements.txt
```

## Tecnologías

- **Backend**: Django 5.2.5
- **Frontend**: Bootstrap 5.3.2 + Bootstrap Icons
- **Base de datos**: SQLite3 (desarrollo)

## Modelo de Datos

### Producto
- `nombre`: Nombre del producto (CharField)
- `descripcion`: Descripción detallada (TextField)
- `cantidad`: Cantidad en inventario (PositiveIntegerField)
- `fecha_ingreso`: Fecha de registro automática (DateTimeField)
- `estado_calidad`: Estado de calidad con opciones (CharField con choices)

## Próximas Mejoras

- [ ] Filtros en la lista de productos
- [ ] Paginación para listas grandes
- [ ] Exportación de datos a Excel/CSV
- [ ] Historial de cambios
- [ ] Sistema de alertas por cantidad baja

## Contribuir

1. Fork del proyecto
2. Crear rama para nueva funcionalidad
3. Commit de cambios
4. Push a la rama
5. Crear Pull Request