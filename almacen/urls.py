"""
URLs para el módulo Almacén - Sistema de Inventario de Almacén Central

Este módulo maneja:
- Gestión de productos de almacén (resurtibles y únicos)
- Solicitudes de baja con flujo de aprobación
- Auditorías de inventario
- Historial de compras y proveedores
- Integración con órdenes de servicio técnico

Agregado: Diciembre 2025
"""

from django.urls import path
from . import views

# Nombre de la aplicación para usar en templates con {% url 'almacen:nombre_vista' %}
app_name = 'almacen'

urlpatterns = [
    # ============================================================================
    # DASHBOARD Y VISTAS PRINCIPALES
    # ============================================================================
    path('', views.dashboard_almacen, name='dashboard'),
    
    # ============================================================================
    # GESTIÓN DE PRODUCTOS
    # ============================================================================
    path('productos/', views.lista_productos, name='lista_productos'),
    path('productos/crear/', views.crear_producto, name='crear_producto'),
    path('productos/<int:pk>/', views.detalle_producto, name='detalle_producto'),
    path('productos/<int:pk>/editar/', views.editar_producto, name='editar_producto'),
    
    # ============================================================================
    # PROVEEDORES
    # ============================================================================
    path('proveedores/', views.lista_proveedores, name='lista_proveedores'),
    path('proveedores/crear/', views.crear_proveedor, name='crear_proveedor'),
    path('proveedores/<int:pk>/editar/', views.editar_proveedor, name='editar_proveedor'),
    path('proveedores/<int:pk>/eliminar/', views.eliminar_proveedor, name='eliminar_proveedor'),
    
    # ============================================================================
    # CATEGORÍAS
    # ============================================================================
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('categorias/crear/', views.crear_categoria, name='crear_categoria'),
    path('categorias/<int:pk>/editar/', views.editar_categoria, name='editar_categoria'),
    
    # ============================================================================
    # MOVIMIENTOS (ENTRADAS/SALIDAS)
    # ============================================================================
    path('movimientos/', views.lista_movimientos, name='lista_movimientos'),
    path('movimientos/entrada/', views.registrar_entrada, name='registrar_entrada'),
    
    # ============================================================================
    # SOLICITUDES DE BAJA
    # ============================================================================
    path('solicitudes/', views.lista_solicitudes, name='lista_solicitudes'),
    path('solicitudes/crear/', views.crear_solicitud, name='crear_solicitud'),
    path('solicitudes/<int:pk>/procesar/', views.procesar_solicitud, name='procesar_solicitud'),
    
    # ============================================================================
    # API / AJAX ENDPOINTS
    # ============================================================================
    path('api/buscar-productos/', views.api_buscar_productos, name='api_buscar_productos'),
    path('api/producto/<int:pk>/', views.api_info_producto, name='api_info_producto'),
    
    # ============================================================================
    # UNIDADES DE INVENTARIO (Seguimiento Individual)
    # ============================================================================
    # Lista general de todas las unidades
    path('unidades/', views.lista_unidades, name='lista_unidades'),
    
    # CRUD de unidades
    path('unidades/crear/', views.crear_unidad, name='crear_unidad'),
    path('unidades/crear/<int:producto_id>/', views.crear_unidad, name='crear_unidad_producto'),
    path('unidades/<int:pk>/', views.detalle_unidad, name='detalle_unidad'),
    path('unidades/<int:pk>/editar/', views.editar_unidad, name='editar_unidad'),
    path('unidades/<int:pk>/eliminar/', views.eliminar_unidad, name='eliminar_unidad'),
    
    # Unidades por producto específico
    path('productos/<int:producto_id>/unidades/', views.unidades_por_producto, name='unidades_por_producto'),
    
    # API endpoints para unidades
    path('api/unidad/<int:pk>/', views.api_unidad_info, name='api_unidad_info'),
    path('api/unidad/<int:pk>/cambiar-estado/', views.cambiar_estado_unidad, name='cambiar_estado_unidad'),
    path('api/unidades-producto/', views.api_unidades_producto, name='api_unidades_producto'),
]

