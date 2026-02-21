"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from inventario import views as inventario_views
from config.media_views import serve_media_from_multiple_locations

urlpatterns = [
    # Panel de administración (URL personalizada por seguridad)
    path('sic-gestion-sistema/', admin.site.urls),
    
    # Autenticación
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(template_name='logout.html'), name='logout'),
    
    # Cambio de contraseña inicial (Fase 5)
    # NOTA: Usar solo caracteres ASCII en URLs para evitar problemas de codificación
    path('cambiar-password-inicial/', inventario_views.cambiar_contraseña_inicial, name='cambiar_contraseña_inicial'),
    
    # Dashboard principal
    path('', inventario_views.dashboard_principal, name='home'),  # Dashboard principal unificado
    
    # Módulos de la aplicación
    path('inventario/', include('inventario.urls')),  # URLs del módulo de inventario
    path('scorecard/', include('scorecard.urls')),  # URLs del módulo de control de calidad
    path('servicio-tecnico/', include('servicio_tecnico.urls')),  # URLs del módulo de servicio técnico
    path('almacen/', include('almacen.urls')),  # URLs del módulo de almacén central - Dic 2025
    path('notificaciones/', include('notificaciones.urls')),  # API de notificaciones 🔔
]

# ============================================================================
# SERVIR ARCHIVOS MEDIA EN DESARROLLO (CON SOPORTE PARA MÚLTIPLES UBICACIONES)
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# En desarrollo (DEBUG=True), Django necesita servir los archivos media.
# Usamos una vista personalizada que busca archivos en DOS ubicaciones:
# 1. Disco alterno (D:\Media_Django\...) - Archivos nuevos
# 2. Disco principal (C:\...\media\) - Archivos antiguos
#
# IMPORTANTE: En producción (DEBUG=False), el servidor web (nginx/apache)
# debe configurarse para servir ambas ubicaciones.
if settings.DEBUG:
    # Usar vista personalizada para servir archivos media desde múltiples ubicaciones
    # re_path permite usar regex para capturar cualquier ruta después de /media/
    urlpatterns += [
        re_path(
            r'^media/(?P<path>.*)$',  # Captura cualquier ruta después de /media/
            serve_media_from_multiple_locations,
            name='serve_media_multi_location'
        ),
    ]
