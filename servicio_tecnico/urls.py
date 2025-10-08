"""
URLs para la aplicación de Servicio Técnico

EXPLICACIÓN PARA PRINCIPIANTES:
- urlpatterns: Lista de rutas (URLs) que Django reconoce
- path(): Define una ruta específica
  * Primer argumento: La URL (lo que escribes en el navegador)
  * Segundo argumento: La vista que se ejecuta
  * name: Nombre para usar con {% url %} en templates
"""
from django.urls import path
from . import views

app_name = 'servicio_tecnico'

urlpatterns = [
    # Página de inicio del módulo de servicio técnico
    path('', views.inicio, name='inicio'),
    
    # Crear nueva orden de servicio
    path('ordenes/crear/', views.crear_orden, name='crear_orden'),
    
    # Detalle de orden (NUEVA VISTA)
    path('ordenes/<int:orden_id>/', views.detalle_orden, name='detalle_orden'),
    
    # Descargar imagen original
    path('imagenes/<int:imagen_id>/descargar/', views.descargar_imagen_original, name='descargar_imagen'),
    
    # Listas de órdenes
    path('ordenes/activas/', views.lista_ordenes_activas, name='lista_activas'),
    path('ordenes/finalizadas/', views.lista_ordenes_finalizadas, name='lista_finalizadas'),
    
    # Acciones de cierre
    path('ordenes/cerrar/<int:orden_id>/', views.cerrar_orden, name='cerrar_orden'),
    path('ordenes/cerrar-todas/', views.cerrar_todas_finalizadas, name='cerrar_todas'),
    
    # ========================================================================
    # GESTIÓN DE REFERENCIAS DE GAMA
    # ========================================================================
    path('referencias-gama/', views.lista_referencias_gama, name='lista_referencias_gama'),
    path('referencias-gama/crear/', views.crear_referencia_gama, name='crear_referencia_gama'),
    path('referencias-gama/<int:referencia_id>/editar/', views.editar_referencia_gama, name='editar_referencia_gama'),
    path('referencias-gama/<int:referencia_id>/eliminar/', views.eliminar_referencia_gama, name='eliminar_referencia_gama'),
    path('referencias-gama/<int:referencia_id>/reactivar/', views.reactivar_referencia_gama, name='reactivar_referencia_gama'),
    
    # ========================================================================
    # GESTIÓN DE PIEZAS COTIZADAS (AJAX)
    # ========================================================================
    path('ordenes/<int:orden_id>/piezas/agregar/', views.agregar_pieza_cotizada, name='agregar_pieza'),
    path('piezas/<int:pieza_id>/editar/', views.editar_pieza_cotizada, name='editar_pieza'),
    path('piezas/<int:pieza_id>/eliminar/', views.eliminar_pieza_cotizada, name='eliminar_pieza'),
    
    # ========================================================================
    # GESTIÓN DE SEGUIMIENTOS DE PIEZAS (AJAX)
    # ========================================================================
    path('ordenes/<int:orden_id>/seguimientos/agregar/', views.agregar_seguimiento_pieza, name='agregar_seguimiento'),
    path('seguimientos/<int:seguimiento_id>/editar/', views.editar_seguimiento_pieza, name='editar_seguimiento'),
    path('seguimientos/<int:seguimiento_id>/eliminar/', views.eliminar_seguimiento_pieza, name='eliminar_seguimiento'),
    path('seguimientos/<int:seguimiento_id>/marcar-recibido/', views.marcar_pieza_recibida, name='marcar_recibido'),
    path('seguimientos/<int:seguimiento_id>/cambiar-estado/', views.cambiar_estado_seguimiento, name='cambiar_estado_seguimiento'),
    
    # URLs futuras para funcionalidad completa
    # path('dashboard/', views.dashboard, name='dashboard'),
]
