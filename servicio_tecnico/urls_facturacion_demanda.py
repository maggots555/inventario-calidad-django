"""
Rutas del API de facturación en demanda (mismo path que el PDF de VO).

EXPLICACIÓN PARA PRINCIPIANTES:
El portal llama /facturacion-web/authenticate y /facturacion-web/folio/123.
Por eso estas URLs viven en la raíz del sitio (config/urls.py), no bajo
/servicio-tecnico/. Sin barra final: un POST a authenticate/ perdería el body
si Django redirige por APPEND_SLASH.
"""

from django.urls import path

from servicio_tecnico import views_facturacion_demanda as views

app_name = 'facturacion_web'

urlpatterns = [
    path(
        'authenticate',
        views.authenticate_facturacion_web,
        name='authenticate',
    ),
    path(
        'folio/<str:web_id>',
        views.folio_facturacion_web,
        name='folio',
    ),
]
