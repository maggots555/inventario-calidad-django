"""
URLs de la app notificaciones.

EXPLICACIÓN PARA PRINCIPIANTES:
app_name define el "namespace" de las URLs. Esto permite usar nombres
como 'notificaciones:listar' en templates y vistas sin conflictos
con URLs de otras apps que tengan nombres similares.

En config/urls.py se incluye así:
    path('notificaciones/', include('notificaciones.urls'))

Resultado final de cada URL:
    /notificaciones/api/listar/              → obtener_notificaciones (GET)
    /notificaciones/api/marcar/<id>/         → marcar_leida (POST)
    /notificaciones/api/marcar-todas/        → marcar_todas_leidas (POST)
    /notificaciones/push/vapid-key/          → vapid_public_key (GET)
    /notificaciones/push/suscribir/          → suscribir_push (POST)
    /notificaciones/push/cancelar/           → cancelar_push (POST)
"""

from django.urls import path
from . import views

app_name = 'notificaciones'

urlpatterns = [
    # ── Campanita 🔔 (polling) ──
    path('api/listar/',                         views.obtener_notificaciones, name='listar'),
    path('api/marcar/<int:notificacion_id>/',   views.marcar_leida,           name='marcar_leida'),
    path('api/marcar-todas/',                   views.marcar_todas_leidas,    name='marcar_todas'),
    path('api/eliminar/<int:notificacion_id>/', views.eliminar_notificacion,  name='eliminar'),
    path('api/eliminar-todas/',                 views.eliminar_todas,         name='eliminar_todas'),

    # ── Web Push ──
    path('push/vapid-key/', views.vapid_public_key, name='push_vapid_key'),
    path('push/suscribir/', views.suscribir_push,   name='push_suscribir'),
    path('push/cancelar/',  views.cancelar_push,    name='push_cancelar'),
]
