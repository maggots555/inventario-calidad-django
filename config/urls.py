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
from django.views.generic.base import RedirectView
from django.templatetags.static import static as static_file
from inventario import views as inventario_views
from config.media_views import serve_media_from_multiple_locations
from config.pwa_views import service_worker_view, offline_view
from servicio_tecnico.views import (
    feedback_rechazo_view,
    feedback_satisfaccion_cliente,
    seguimiento_orden_cliente,
    diagnostico_pdf_seguimiento,
    chat_seguimiento_cliente,
    manifest_seguimiento,
    vapid_key_seguimiento,
    suscribir_push_seguimiento,
    cancelar_push_seguimiento,
    registrar_evento_seguimiento_cliente,
)

urlpatterns = [
    # ── Favicons e iconos en la raíz ──
    # iOS Safari y todos los navegadores buscan estos archivos automáticamente en /,
    # no en /static/. Redireccionamos permanentemente a los archivos estáticos reales.
    path('favicon.ico', RedirectView.as_view(url=static_file('images/favicon.ico'), permanent=True), name='favicon'),
    path('apple-touch-icon.png', RedirectView.as_view(url=static_file('images/apple-touch-icon.png'), permanent=True), name='apple_touch_icon'),
    path('apple-touch-icon-precomposed.png', RedirectView.as_view(url=static_file('images/apple-touch-icon-precomposed.png'), permanent=True), name='apple_touch_icon_precomposed'),
    path('apple-touch-icon-120x120.png', RedirectView.as_view(url=static_file('images/apple-touch-icon-120x120.png'), permanent=True), name='apple_touch_icon_120'),
    path('apple-touch-icon-120x120-precomposed.png', RedirectView.as_view(url=static_file('images/apple-touch-icon-120x120-precomposed.png'), permanent=True), name='apple_touch_icon_120_precomposed'),
    path('apple-touch-icon-152x152.png', RedirectView.as_view(url=static_file('images/apple-touch-icon-152x152.png'), permanent=True), name='apple_touch_icon_152'),

    # ── PWA: Service Worker (debe estar en la raíz para tener scope global) ──
    # El SW intercepta peticiones de todo el sitio. Si estuviera en /static/js/
    # solo controlaría esa sub-ruta, que no sirve de nada.
    path('service_worker.js', service_worker_view, name='service_worker'),

    # ── PWA: Página offline ──
    # El SW muestra esta página cuando el usuario no tiene conexión.
    # No requiere login: si no hay red, el usuario tampoco puede autenticarse.
    path('offline/', offline_view, name='offline'),

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

    # ── URL PÚBLICA: Feedback de rechazo de cotización (sin autenticación) ──
    # El cliente abre este link desde el correo. No requiere login.
    # Formato: /feedback/<token>/
    path('feedback/<str:token>/', feedback_rechazo_view, name='feedback_rechazo_publico'),

    # ── URL PÚBLICA: Encuesta de satisfacción (sin autenticación) ──
    # El cliente abre este link desde el correo de entrega. No requiere login.
    # Formato: /feedback-satisfaccion/<token>/
    path('feedback-satisfaccion/<str:token>/', feedback_satisfaccion_cliente, name='feedback_satisfaccion_publico'),

    # ── URL PÚBLICA: Seguimiento de orden (sin autenticación) ──
    # El cliente abre este link desde el correo de imágenes de ingreso.
    # Muestra timeline del estado, info del equipo y contacto del responsable.
    # Caduca 3 días después de estado 'entregado'. Formato: /seguimiento/<token>/
    path('seguimiento/<str:token>/', seguimiento_orden_cliente, name='seguimiento_orden_publico'),

    # ── URL PÚBLICA: PDF de diagnóstico del cliente (sin autenticación) ──
    # Abre el PDF enviado al cliente. Se usa desde push y desde la PWA.
    # Formato: GET /seguimiento/<token>/diagnostico/
    path('seguimiento/<str:token>/diagnostico/', diagnostico_pdf_seguimiento, name='diagnostico_pdf_seguimiento'),

    # ── URL PÚBLICA: Chat de IA del seguimiento (sin autenticación) ──
    # Endpoint AJAX del chatbot de IA accesible desde la vista de seguimiento.
    # Valida el mismo token de la vista padre. Rate limit: 10 req/min por IP.
    # Formato: POST /seguimiento/<token>/chat/
    path('seguimiento/<str:token>/chat/', chat_seguimiento_cliente, name='chat_seguimiento_publico'),

    # ── PWA: Manifest dinámico del seguimiento del cliente (sin autenticación) ──
    # A diferencia del manifest global (static/manifest.json, start_url="/"),
    # este manifest apunta al token específico del cliente, para que al
    # instalar la PWA el ícono abra directo SU página de seguimiento.
    # Formato: GET /seguimiento/<token>/manifest.json
    path('seguimiento/<str:token>/manifest.json', manifest_seguimiento, name='manifest_seguimiento'),

    # ── URLS PÚBLICAS: Web Push del cliente en el seguimiento (sin autenticación) ──
    # Versión "para clientes" de /notificaciones/push/*, identificando al
    # suscriptor por el token del enlace en vez de una sesión de usuario.
    path('seguimiento/<str:token>/push/vapid-key/', vapid_key_seguimiento, name='push_vapid_key_seguimiento'),
    path('seguimiento/<str:token>/push/suscribir/', suscribir_push_seguimiento, name='push_suscribir_seguimiento'),
    path('seguimiento/<str:token>/push/cancelar/', cancelar_push_seguimiento, name='push_cancelar_seguimiento'),
    path('seguimiento/<str:token>/eventos/', registrar_evento_seguimiento_cliente, name='eventos_seguimiento_cliente'),
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
