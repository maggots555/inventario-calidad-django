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
    
    # Seleccionar tipo de orden (Diagnóstico vs Venta Mostrador)
    path('ordenes/nueva/', views.seleccionar_tipo_orden, name='seleccionar_tipo_orden'),
    
    # Crear nueva orden de servicio
    path('ordenes/crear/', views.crear_orden, name='crear_orden'),
    
    # Crear nueva orden de Venta Mostrador (sin diagnóstico)
    path('ordenes/venta-mostrador/crear/', views.crear_orden_venta_mostrador, name='crear_orden_venta_mostrador'),
    
    # Detalle de orden (NUEVA VISTA)
    path('ordenes/<int:orden_id>/', views.detalle_orden, name='detalle_orden'),
    
    # Descargar imagen original
    path('imagenes/<int:imagen_id>/descargar/', views.descargar_imagen_original, name='descargar_imagen'),
    
    # Eliminar imagen
    path('imagenes/<int:imagen_id>/eliminar/', views.eliminar_imagen, name='eliminar_imagen'),
    
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
    path('piezas/<int:pieza_id>/obtener/', views.obtener_pieza_cotizada, name='obtener_pieza'),
    path('piezas/<int:pieza_id>/editar/', views.editar_pieza_cotizada, name='editar_pieza'),
    path('piezas/<int:pieza_id>/eliminar/', views.eliminar_pieza_cotizada, name='eliminar_pieza'),
    
    # ========================================================================
    # GESTIÓN DE SEGUIMIENTOS DE PIEZAS (AJAX)
    # ========================================================================
    path('seguimientos/<int:seguimiento_id>/obtener/', views.obtener_seguimiento_pieza, name='obtener_seguimiento'),
    path('ordenes/<int:orden_id>/seguimientos/agregar/', views.agregar_seguimiento_pieza, name='agregar_seguimiento'),
    path('seguimientos/<int:seguimiento_id>/editar/', views.editar_seguimiento_pieza, name='editar_seguimiento'),
    path('seguimientos/<int:seguimiento_id>/eliminar/', views.eliminar_seguimiento_pieza, name='eliminar_seguimiento'),
    path('seguimientos/<int:seguimiento_id>/marcar-recibido/', views.marcar_pieza_recibida, name='marcar_recibido'),
    path('seguimientos/<int:seguimiento_id>/reenviar-notificacion/', views.reenviar_notificacion_pieza, name='reenviar_notificacion'),
    path('seguimientos/<int:seguimiento_id>/cambiar-estado/', views.cambiar_estado_seguimiento, name='cambiar_estado_seguimiento'),
    
    # NUEVOS: Marcar piezas con problemas (Noviembre 2025)
    path('seguimientos/<int:seguimiento_id>/marcar-incorrecta/', views.marcar_pieza_incorrecta, name='marcar_incorrecta'),
    path('seguimientos/<int:seguimiento_id>/marcar-danada/', views.marcar_pieza_danada, name='marcar_danada'),
    
    # ========================================================================
    # GESTIÓN DE VENTA MOSTRADOR (AJAX) - FASE 3
    # ========================================================================
    # Crear venta mostrador
    path('ordenes/<int:orden_id>/venta-mostrador/crear/', views.crear_venta_mostrador, name='venta_mostrador_crear'),
    
    # Gestión de piezas de venta mostrador
    path('ordenes/<int:orden_id>/venta-mostrador/piezas/agregar/', views.agregar_pieza_venta_mostrador, name='venta_mostrador_agregar_pieza'),
    path('venta-mostrador/piezas/<int:pieza_id>/editar/', views.editar_pieza_venta_mostrador, name='venta_mostrador_editar_pieza'),
    path('venta-mostrador/piezas/<int:pieza_id>/eliminar/', views.eliminar_pieza_venta_mostrador, name='venta_mostrador_eliminar_pieza'),
    
    # ⛔ URL ELIMINADA: 'convertir-a-diagnostico/' 
    # Esta URL manejaba la conversión de venta mostrador a diagnóstico.
    # ELIMINADA EN: Octubre 2025 (Sistema Refactorizado)
    # Ya no es necesaria porque venta_mostrador es ahora un complemento opcional.
    
    # ========================================================================
    # MÓDULO RHITSO - SEGUIMIENTO ESPECIALIZADO (FASES 4 Y 5)
    # ========================================================================
    
    # Dashboard consolidado de candidatos RHITSO (Octubre 2025)
    path('rhitso/dashboard/', views.dashboard_rhitso, name='dashboard_rhitso'),
    
    # Exportación Excel de dashboard RHITSO con openpyxl (Octubre 2025)
    path('rhitso/exportar-excel/', views.exportar_excel_rhitso, name='exportar_excel_rhitso'),
    
    # Vista principal del panel RHITSO (FASE 4)
    path('rhitso/orden/<int:orden_id>/', views.gestion_rhitso, name='gestion_rhitso'),
    
    # Vistas AJAX para gestión RHITSO (FASE 5 + FASE 8.4)
    # ========================================================================
    # Actualizar estado RHITSO de una orden
    path('rhitso/orden/<int:orden_id>/actualizar-estado/', 
         views.actualizar_estado_rhitso, 
         name='actualizar_estado_rhitso'),
    
    # Registrar nueva incidencia en proceso RHITSO
    path('rhitso/orden/<int:orden_id>/registrar-incidencia/', 
         views.registrar_incidencia, 
         name='registrar_incidencia'),
    
    # Resolver/cerrar una incidencia existente
    path('rhitso/incidencia/<int:incidencia_id>/resolver/', 
         views.resolver_incidencia, 
         name='resolver_incidencia'),
    
    # Editar diagnóstico SIC y datos RHITSO
    path('rhitso/orden/<int:orden_id>/editar-diagnostico/', 
         views.editar_diagnostico_sic, 
         name='editar_diagnostico_sic'),
    
    # Agregar comentario manual al historial RHITSO (FASE 8.4)
    path('rhitso/orden/<int:orden_id>/agregar-comentario/', 
         views.agregar_comentario_rhitso, 
         name='agregar_comentario_rhitso'),
    
    # Enviar correo con formato a RHITSO (FASE 10)
    path('rhitso/orden/<int:orden_id>/enviar-correo/', 
         views.enviar_correo_rhitso, 
         name='enviar_correo_rhitso'),
    
    # Enviar imágenes de ingreso al cliente por correo
    path('orden/<int:orden_id>/enviar-imagenes-cliente/', 
         views.enviar_imagenes_cliente, 
         name='enviar_imagenes_cliente'),
    
    # Vista de prueba: GENERACIÓN DE PDF RHITSO (FASE 10.2)
    # ========================================================================
    # Esta vista es temporal para probar la generación de PDF
    # Una vez integrado al modal de correo, se puede eliminar
    path('rhitso/orden/<int:orden_id>/generar-pdf-prueba/', 
         views.generar_pdf_rhitso_prueba, 
         name='generar_pdf_rhitso_prueba'),
    
    # ========================================================================
    # DASHBOARD DE SEGUIMIENTO OOW-/FL- (Octubre 2025)
    # ========================================================================
    # Dashboard especializado para seguimiento de órdenes con prefijo OOW- y FL-
    # Incluye métricas, KPIs, gráficos interactivos y análisis por responsable
    path('dashboard/seguimiento-oow-fl/', 
         views.dashboard_seguimiento_oow_fl, 
         name='dashboard_seguimiento_oow_fl'),
    
    # Exportación a Excel del dashboard OOW-/FL-
    # Genera archivo Excel con múltiples hojas: resumen, responsables, productos, etc.
    path('dashboard/seguimiento-oow-fl/exportar-excel/', 
         views.exportar_excel_dashboard_oow_fl, 
         name='exportar_excel_dashboard_oow_fl'),
    
    # ========================================================================
    # DASHBOARD DE COTIZACIONES - ANALYTICS CON PLOTLY Y ML (Enero 2025)
    # ========================================================================
    # Dashboard analítico tipo Power BI con 20+ visualizaciones interactivas
    # Incluye: KPIs, gráficos temporales, análisis de piezas, proveedores,
    # ranking de técnicos/sucursales, y predicciones con Machine Learning
    path('cotizaciones/dashboard/', 
         views.dashboard_cotizaciones, 
         name='dashboard_cotizaciones'),
    
    # Exportación a Excel del dashboard de cotizaciones
    # Genera archivo Excel con 6 hojas: resumen, cotizaciones, piezas, 
    # proveedores, técnicos, sucursales
    path('cotizaciones/dashboard/exportar/', 
         views.exportar_dashboard_cotizaciones, 
         name='exportar_dashboard_cotizaciones'),
    
    # ========================================================================
    # API: BÚSQUEDA DE ÓRDENES (Noviembre 2025)
    # ========================================================================
    # API endpoint para buscar órdenes por número de serie o orden del cliente
    # Usado por el formulario de ScoreCard para autocompletar datos
    # Soporta búsqueda inteligente: si serie es "NO VISIBLE", busca por orden_cliente
    path('api/buscar-orden-por-serie/', 
         views.api_buscar_orden_por_serie, 
         name='api_buscar_orden_por_serie'),
    
    # API: BÚSQUEDA DE MODELOS POR MARCA (Diciembre 2025)
    # ========================================================================
    # API endpoint para autocompletado del campo "Modelo" en formularios
    # Busca en ReferenciaGamaEquipo los modelos disponibles para la marca seleccionada
    # Usado por Select2 para proporcionar sugerencias mientras el usuario escribe
    path('api/buscar-modelos-por-marca/', 
         views.api_buscar_modelos_por_marca, 
         name='api_buscar_modelos_por_marca'),
    
    # ========================================================================
    # DASHBOARD DE SEGUIMIENTO DE PIEZAS EN TRÁNSITO (Noviembre 2025)
    # ========================================================================
    # Dashboard dedicado para seguimiento de piezas pedidas a proveedores
    # Incluye: KPIs (activos, retrasados, próximos), gráficos interactivos con Plotly,
    # tabla filtrable, alertas visuales, y análisis por proveedor/sucursal
    path('dashboard/seguimiento-piezas/', 
         views.dashboard_seguimiento_piezas, 
         name='dashboard_seguimiento_piezas'),
    
    # Exportación a Excel del dashboard de seguimiento de piezas
    # Genera archivo Excel con 5 hojas: resumen, seguimientos completos,
    # solo retrasados, agrupado por proveedor, agrupado por sucursal
    path('dashboard/seguimiento-piezas/exportar/', 
         views.exportar_dashboard_seguimiento_piezas, 
         name='exportar_dashboard_seguimiento_piezas'),
    
    # URLs futuras para funcionalidad completa
    # path('dashboard/', views.dashboard, name='dashboard'),
]
