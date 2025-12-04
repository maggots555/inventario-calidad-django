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
    # COMPRAS Y COTIZACIONES
    # ============================================================================
    # Vista principal: todas las compras y cotizaciones
    path('compras/', views.lista_compras, name='lista_compras'),
    
    # Panel de cotizaciones pendientes (dashboard específico)
    path('cotizaciones/', views.panel_cotizaciones, name='panel_cotizaciones'),
    
    # CRUD de compras/cotizaciones
    path('compras/crear/', views.crear_compra, name='crear_compra'),
    path('compras/<int:pk>/', views.detalle_compra, name='detalle_compra'),
    path('compras/<int:pk>/editar/', views.editar_compra, name='editar_compra'),
    
    # Workflow de cotizaciones
    path('compras/<int:pk>/aprobar/', views.aprobar_cotizacion, name='aprobar_cotizacion'),
    path('compras/<int:pk>/rechazar/', views.rechazar_cotizacion, name='rechazar_cotizacion'),
    
    # Workflow de compras
    path('compras/<int:pk>/recibir/', views.recibir_compra, name='recibir_compra'),
    path('compras/<int:pk>/problema/', views.reportar_problema_compra, name='reportar_problema'),
    path('compras/<int:pk>/devolucion/', views.iniciar_devolucion, name='iniciar_devolucion'),
    path('compras/<int:pk>/confirmar-devolucion/', views.confirmar_devolucion, name='confirmar_devolucion'),
    path('compras/<int:pk>/cancelar/', views.cancelar_compra, name='cancelar_compra'),
    
    # Unidades de compra (detalle por pieza individual)
    path('compras/<int:compra_pk>/unidad/<int:pk>/recibir/', views.recibir_unidad_compra, name='recibir_unidad'),
    path('compras/<int:compra_pk>/unidad/<int:pk>/problema/', views.problema_unidad_compra, name='problema_unidad'),
    
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
    path('api/tecnicos-disponibles/', views.api_tecnicos_disponibles, name='api_tecnicos_disponibles'),
    
    # API endpoint para buscar o crear orden de servicio por orden_cliente
    path('api/buscar-crear-orden/', views.api_buscar_crear_orden_cliente, name='api_buscar_crear_orden'),
]

