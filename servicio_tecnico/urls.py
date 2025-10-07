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
    
    # Listas de órdenes
    path('ordenes/activas/', views.lista_ordenes_activas, name='lista_activas'),
    path('ordenes/finalizadas/', views.lista_ordenes_finalizadas, name='lista_finalizadas'),
    
    # Acciones de cierre
    path('ordenes/cerrar/<int:orden_id>/', views.cerrar_orden, name='cerrar_orden'),
    path('ordenes/cerrar-todas/', views.cerrar_todas_finalizadas, name='cerrar_todas'),
    
    # URLs futuras para funcionalidad completa
    # path('ordenes/<int:orden_id>/', views.detalle_orden, name='detalle_orden'),
    # path('dashboard/', views.dashboard, name='dashboard'),
]
