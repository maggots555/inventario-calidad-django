from django.urls import path
from . import views

urlpatterns = [
    # Dashboard de inventario (renombrado para claridad)
    path('', views.dashboard_inventario, name='dashboard'),
    path('dashboard/', views.dashboard_inventario, name='dashboard_inventario'),
    
    # Acceso denegado
    path('acceso-denegado/', views.acceso_denegado, name='acceso_denegado'),
    
    # Gestión de productos
    path('productos/', views.lista_productos, name='lista_productos'),
    path('productos/crear/', views.crear_producto, name='crear_producto'),
    path('productos/<int:producto_id>/', views.detalle_producto, name='detalle_producto'),
    path('productos/<int:producto_id>/editar/', views.editar_producto, name='editar_producto'),
    path('productos/<int:producto_id>/eliminar/', views.eliminar_producto, name='eliminar_producto'),
    path('productos/<int:producto_id>/qr/', views.generar_qr_producto, name='generar_qr_producto'),
    
    # Gestión de movimientos
    path('movimientos/', views.lista_movimientos, name='lista_movimientos'),
    path('movimientos/crear/', views.crear_movimiento, name='crear_movimiento'),
    path('movimientos/rapido/', views.movimiento_rapido, name='movimiento_rapido'),
    path('movimientos/fraccionario/', views.movimiento_fraccionario, name='movimiento_fraccionario'),
    
    # Gestión de sucursales
    path('sucursales/', views.lista_sucursales, name='lista_sucursales'),
    path('sucursales/crear/', views.crear_sucursal, name='crear_sucursal'),
    path('sucursales/<int:sucursal_id>/editar/', views.editar_sucursal, name='editar_sucursal'),
    path('sucursales/<int:sucursal_id>/eliminar/', views.eliminar_sucursal, name='eliminar_sucursal'),
    
    # Gestión de empleados
    path('empleados/', views.lista_empleados, name='lista_empleados'),
    path('empleados/crear/', views.crear_empleado, name='crear_empleado'),
    path('empleados/<int:empleado_id>/editar/', views.editar_empleado, name='editar_empleado'),
    path('empleados/<int:empleado_id>/eliminar/', views.eliminar_empleado, name='eliminar_empleado'),
    
    # Gestión de acceso al sistema para empleados
    path('empleados/<int:empleado_id>/dar-acceso/', views.dar_acceso_empleado, name='dar_acceso_empleado'),
    path('empleados/<int:empleado_id>/reenviar-credenciales/', views.reenviar_credenciales, name='reenviar_credenciales'),
    path('empleados/<int:empleado_id>/resetear-contraseña/', views.resetear_contraseña_empleado, name='resetear_contraseña_empleado'),
    path('empleados/<int:empleado_id>/revocar-acceso/', views.revocar_acceso_empleado, name='revocar_acceso_empleado'),
    path('empleados/<int:empleado_id>/reactivar-acceso/', views.reactivar_acceso_empleado, name='reactivar_acceso_empleado'),
    
    # API endpoints
    path('api/buscar-producto-qr/', views.buscar_producto_qr, name='buscar_producto_qr'),
    path('api/buscar-producto-fraccionable-qr/', views.buscar_producto_fraccionable_qr, name='buscar_producto_fraccionable_qr'),
    
    # Reportes
    path('reportes/excel/', views.descargar_reporte_excel, name='descargar_reporte_excel'),
    
    # Administración
    path('admin/storage-monitor/', views.admin_storage_monitor, name='admin_storage_monitor'),
]