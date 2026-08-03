"""
Vistas para la aplicación de Servicio Técnico — fachada de reexports.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Este archivo YA NO contiene la lógica HTTP grande.
Cada dominio vive en un módulo hermano `views_*.py` (o `services/`).
Aquí solo reexportamos los nombres para que:
- `urls.py` siga usando `views.nombre_vista`
- imports antiguos `from servicio_tecnico.views import ...` no se rompan

Mapa rápido (fases de modularización):
- Fase 4: encuestas / feedback rechazo / enlaces
- Fase 5: multimedia (compressors + eliminar/descargar)
- Fase 6: AJAX piezas / seguimiento / venta mostrador
- Fase 7: RHITSO por orden + envíos al cliente
- Fase 8: dashboards grandes + analytics VM
- Fase 9: órdenes CRUD / listas / inicio
- Fase 10 / B: detalle_orden → views_detalle_orden.py
- SICSER, formatos OOW/garantía, gama, video resumen, APIs, misc, concentrado,
  IA diag, perfil, portal cliente: módulos propios (reexport abajo)

❌ No agregues vistas nuevas aquí. Crea views_<dominio>.py y reexporta.
"""

# ============================================================================
# REEXPORTS (modularización)
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# Helpers, SICSER, gama, video, APIs, misc, concentrado, IA diag y perfil salieron del monolito.
# Reexportamos aquí para que urls.py (views.foo) e imports antiguos sigan igual.
from .decorators import cache_page_dashboard, permission_required_with_message
from .services.historial import registrar_historial
from .services.multimedia import (  # noqa: F401
    comprimir_y_guardar_imagen,
    comprimir_y_guardar_video,
)
from .views_multimedia import (  # noqa: F401
    descargar_imagen_original,
    eliminar_imagen,
    eliminar_video,
)
from .views_piezas_cotizadas import (  # noqa: F401
    agregar_pieza_cotizada,
    editar_pieza_cotizada,
    eliminar_pieza_cotizada,
    obtener_pieza_cotizada,
)
from .views_seguimiento_piezas_ajax import (  # noqa: F401
    agregar_seguimiento_pieza,
    cambiar_estado_seguimiento,
    editar_seguimiento_pieza,
    eliminar_seguimiento_pieza,
    marcar_pieza_danada,
    marcar_pieza_incorrecta,
    marcar_pieza_recibida,
    obtener_seguimiento_pieza,
    reenviar_notificacion_pieza,
)
from .views_venta_mostrador_ajax import (  # noqa: F401
    agregar_pieza_venta_mostrador,
    crear_venta_mostrador,
    editar_pieza_venta_mostrador,
    eliminar_pieza_venta_mostrador,
)
from .services.notificaciones_piezas import (  # noqa: F401
    enviar_notificacion_pieza_recibida as _enviar_notificacion_pieza_recibida,
)
from .views_rhitso import (  # noqa: F401
    actualizar_estado_rhitso,
    agregar_comentario_rhitso,
    editar_diagnostico_sic,
    enviar_correo_rhitso,
    generar_pdf_rhitso_prueba,
    gestion_rhitso,
    registrar_incidencia,
    resolver_incidencia,
)
from .views_envios_cliente import (  # noqa: F401
    confirmar_envio_feedback,
    confirmar_envio_vigencia_vencida,
    enviar_diagnostico_cliente,
    enviar_evidencia_video,
    enviar_imagenes_cliente,
    enviar_imagenes_egreso_cliente,
    enviar_rewind_egreso_cliente,
    notificar_equipo_disponible,
    obtener_destinatarios_egreso,
    preview_pdf_diagnostico,
)
from .services.ventas_mostrador_analytics import (  # noqa: F401
    determinar_categoria_venta,
    obtener_top_productos_vendidos,
)
from .views_dashboard_rhitso import (  # noqa: F401
    dashboard_rhitso,
    exportar_analisis_rhitso,
    exportar_excel_rhitso,
)
from .views_dashboard_oow_fl import (  # noqa: F401
    dashboard_seguimiento_oow_fl,
    exportar_excel_dashboard_oow_fl,
)
from .views_dashboard_cotizaciones import (  # noqa: F401
    dashboard_cotizaciones,
    exportar_analisis_aceptaciones,
    exportar_analisis_rechazos,
    exportar_dashboard_cotizaciones,
)
from .views_dashboard_seguimiento_piezas import (  # noqa: F401
    dashboard_seguimiento_piezas,
    exportar_dashboard_seguimiento_piezas,
)
from .views_ordenes import (  # noqa: F401
    cerrar_finalizados_garantia,
    cerrar_orden,
    cerrar_todas_finalizadas,
    crear_orden,
    crear_orden_venta_mostrador,
    inicio,
    lista_ordenes_activas,
    lista_ordenes_finalizadas,
    seleccionar_tipo_orden,
)
from .views_sicser import consultar_sicser, importar_orden_sicser  # noqa: F401
from .views_formato_oow import (  # noqa: F401
    abrir_formato_oow_desde_sicser,
    formato_oow_eliminar_evidencia,
    formato_oow_finalizar,
    formato_oow_guardar,
    formato_oow_pdf,
    formato_oow_reenviar_email,
    formato_oow_subir_evidencia,
    formato_oow_wizard,
)
from .views_formato_garantia import (  # noqa: F401
    abrir_formato_garantia_desde_sicser,
    formato_garantia_eliminar_evidencia,
    formato_garantia_finalizar,
    formato_garantia_guardar,
    formato_garantia_pdf,
    formato_garantia_reenviar_email,
    formato_garantia_subir_evidencia,
    formato_garantia_wizard,
)
from .views_referencias_gama import (  # noqa: F401
    crear_referencia_gama,
    editar_referencia_gama,
    eliminar_referencia_gama,
    lista_referencias_gama,
    reactivar_referencia_gama,
)
from .views_video_resumen import (  # noqa: F401
    comprimir_video_resumen,
    estado_compresion_resumen,
    estado_video_resumen,
    generar_video_resumen,
)
from .views_apis_busqueda import (  # noqa: F401
    api_buscar_modelos_por_marca,
    api_buscar_orden_por_serie,
    api_buscar_ordenes_autocomplete,
    api_buscar_ordenes_reingreso,
)
from .views_misc import (  # noqa: F401
    acceso_denegado,
    actualizar_email_cliente,
)
from .views_concentrado import (  # noqa: F401
    concentrado_semanal,
    exportar_concentrado_excel,
    exportar_concentrado_pdf,
)
from .views_ia_diagnostico import (  # noqa: F401
    guardar_diagnostico_sic_ia,
    pulir_diagnostico_sic_ia,
    transcribir_audio_diagnostico,
)
from .views_perfil import (  # noqa: F401
    directorio_empleados,
    exportar_excel_mi_perfil,
    mi_perfil,
    perfil_empleado,
)
from .views_seguimiento_cliente import (  # noqa: F401
    cancelar_push_seguimiento,
    chat_seguimiento_cliente,
    confirmar_feedback_satisfaccion,
    diagnostico_pdf_seguimiento,
    feedback_rechazo_view,
    feedback_satisfaccion_cliente,
    manifest_seguimiento,
    registrar_evento_seguimiento_cliente,
    seguimiento_orden_cliente,
    suscribir_push_seguimiento,
    vapid_key_seguimiento,
)
from .views_encuestas import (  # noqa: F401
    api_analisis_sentimiento_ia,
    api_encuestas_comentarios,
    api_encuestas_distribucion_nps,
    api_encuestas_kpis,
    api_encuestas_lista,
    api_encuestas_por_responsable,
    api_encuestas_tendencia,
    dashboard_encuestas,
    exportar_encuestas_excel,
    exportar_encuestas_pdf,
)
from .views_feedback_rechazo_dash import (  # noqa: F401
    api_analisis_sentimiento_rechazo,
    api_feedback_rechazo_comentarios,
    api_feedback_rechazo_kpis,
    api_feedback_rechazo_lista,
    api_feedback_rechazo_por_motivo,
    api_feedback_rechazo_tendencia,
    dashboard_feedback_rechazo,
    exportar_feedback_rechazo_excel,
    exportar_feedback_rechazo_pdf,
)
from .views_seguimiento_enlaces import (  # noqa: F401
    api_seguimiento_enlaces_embudo,
    api_seguimiento_enlaces_kpis,
    api_seguimiento_enlaces_tabla,
    api_seguimiento_enlaces_tendencia,
    api_seguimiento_enlaces_top,
    dashboard_seguimiento_enlaces,
)
# Helpers de enlaces (antes privados en views.py; ahora en eventos_seguimiento)
from .eventos_seguimiento import (  # noqa: F401
    anotar_push_enlaces as _anotar_push_enlaces,
    filtrar_enlaces_seguimiento as _filtrar_enlaces_seguimiento,
)

# ============================================================================
# DETALLE DE ORDEN (Fase 10 / B)
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# La función vive en views_detalle_orden.py. urls.py sigue con views.detalle_orden.
# Template ya partido en partials (Fase A). Handlers form_type → Fase C.
from .views_detalle_orden import detalle_orden  # noqa: F401
