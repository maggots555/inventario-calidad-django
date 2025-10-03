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
    
    # Gestión de estado y atribuibilidad
    path('incidencias/<int:incidencia_id>/cambiar-estado/', views.cambiar_estado_incidencia, name='cambiar_estado_incidencia'),
    path('incidencias/<int:incidencia_id>/marcar-no-atribuible/', views.marcar_no_atribuible, name='marcar_no_atribuible'),
    path('incidencias/<int:incidencia_id>/cerrar/', views.cerrar_incidencia, name='cerrar_incidencia'),
    
    # Reportes y análisis
    path('reportes/', views.reportes, name='reportes'),
    
    # Configuración
    path('categorias/', views.lista_categorias, name='lista_categorias'),
    path('componentes/', views.lista_componentes, name='lista_componentes'),
    
    # APIs para JavaScript (autocompletado y validaciones)
    path('api/empleado/<int:empleado_id>/', views.api_empleado_data, name='api_empleado_data'),
    path('api/buscar-reincidencias/', views.api_buscar_reincidencias, name='api_buscar_reincidencias'),
    path('api/componentes-por-tipo/', views.api_componentes_por_tipo, name='api_componentes_por_tipo'),
    
    # APIs para gráficos y reportes (Fase 3)
    path('api/datos-dashboard/', views.api_datos_dashboard, name='api_datos_dashboard'),
    path('api/exportar-excel/', views.api_exportar_excel, name='api_exportar_excel'),
    
    # APIs para reportes avanzados - FASE 1
    path('api/analisis-atribuibilidad/', views.api_analisis_atribuibilidad, name='api_analisis_atribuibilidad'),
    path('api/analisis-tecnicos/', views.api_analisis_tecnicos, name='api_analisis_tecnicos'),
    
    # APIs para reportes avanzados - FASE 2
    path('api/analisis-reincidencias/', views.api_analisis_reincidencias, name='api_analisis_reincidencias'),
    path('api/analisis-tiempos/', views.api_analisis_tiempos, name='api_analisis_tiempos'),
    
    # APIs para reportes avanzados - FASE 3
    path('api/analisis-componentes/', views.api_analisis_componentes, name='api_analisis_componentes'),
    path('api/analisis-notificaciones/', views.api_analisis_notificaciones, name='api_analisis_notificaciones'),
    
    # APIs para notificaciones por email (Fase 4)
    path('api/incidencias/<int:incidencia_id>/destinatarios/', views.api_obtener_destinatarios, name='api_obtener_destinatarios'),
    path('api/incidencias/<int:incidencia_id>/enviar-notificacion/', views.api_enviar_notificacion, name='api_enviar_notificacion'),
]