"""
URLs del manual de operación (OOW y FL). Se montan en /manual/ desde config/urls.py.

EXPLICACIÓN PARA PRINCIPIANTES:
El app_name `manual` permite escribir {% url 'manual:indice' %} en las
plantillas. Cada path apunta a una vista en views_manual.py (no al
views.py gordo de inventario).
"""

from django.urls import path

from inventario import views_manual as views

app_name = 'manual'

urlpatterns = [
    path('', views.manual_indice, name='indice'),
    path('proceso/', views.manual_proceso, name='proceso'),
    path('proceso/fl/', views.manual_proceso_fl, name='proceso_fl'),
    path('proceso/fl/alta-directa/', views.manual_alta_directa_fl, name='alta_directa_fl'),
    path('acepta/', views.manual_acepta, name='acepta'),
    path('rechaza/', views.manual_rechaza, name='rechaza'),
    path('pnc/', views.manual_pnc, name='pnc'),
    path('recotizacion/', views.manual_recotizacion, name='recotizacion'),
    path('rol/front/', views.manual_rol_front, name='rol_front'),
    path('rol/tecnico/', views.manual_rol_tecnico, name='rol_tecnico'),
    path('rol/calidad/', views.manual_rol_calidad, name='rol_calidad'),
    path('rol/compras/', views.manual_rol_compras, name='rol_compras'),
    path('rol/facturacion/', views.manual_rol_facturacion, name='rol_facturacion'),
    path('glosario/', views.manual_glosario, name='glosario'),
]
