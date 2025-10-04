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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from inventario import views as inventario_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
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
]

# Servir archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
