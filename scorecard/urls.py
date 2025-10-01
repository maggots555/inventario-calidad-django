"""
URLs para la aplicación Score Card
"""
from django.urls import path
from . import views

# Namespace para las URLs de scorecard
app_name = 'scorecard'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard, name='dashboard'),
    
    # CRUD de Incidencias
    path('incidencias/', views.lista_incidencias, name='lista_incidencias'),
    path('incidencias/crear/', views.crear_incidencia, name='crear_incidencia'),
    path('incidencias/<int:incidencia_id>/', views.detalle_incidencia, name='detalle_incidencia'),
    path('incidencias/<int:incidencia_id>/editar/', views.editar_incidencia, name='editar_incidencia'),
    path('incidencias/<int:incidencia_id>/eliminar/', views.eliminar_incidencia, name='eliminar_incidencia'),
    
    # Reportes y análisis
    path('reportes/', views.reportes, name='reportes'),
    
    # Configuración
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('componentes/', views.lista_componentes, name='lista_componentes'),
    
    # APIs para JavaScript (autocompletado y validaciones)
    path('api/empleado/<int:empleado_id>/', views.api_empleado_data, name='api_empleado_data'),
    path('api/buscar-reincidencias/', views.api_buscar_reincidencias, name='api_buscar_reincidencias'),
    path('api/componentes-por-tipo/', views.api_componentes_por_tipo, name='api_componentes_por_tipo'),
]