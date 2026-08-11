"""
Vistas para el módulo Almacén - Sistema de Inventario de Almacén Central

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Este archivo es la FACHADA de reexports tras la modularización (Fase 0..4).
La lógica HTTP vive en módulos hermanos views_*.py.
urls.py sigue haciendo `from . import views` y `views.nombre`.

Organización:
- decorators.py: permission_required_with_message
- views_dashboard_distribucion.py: distribución multi-sucursal + Excel
- views_parametros_cotizador.py: panel de márgenes del cotizador
- views_catalogo.py: dashboard, productos, proveedores, categorías, bajas
- views_unidades.py: UnidadesInventario + APIs + buscar/crear orden
- views_compras.py: CompraProducto (lista, recibir, devoluciones)
- views_solicitudes_cotizacion.py: SolicitudCotizacion CRUD/detalle/servicios/imágenes
- views_cotizacion_cliente.py: envío cliente, PDF, respuestas, motivos rechazo
- views_cotizacion_sync_st.py: generar compras, vincular/crear orden FL
- utils/cotizacion_reacondicionado_helpers.py: helpers profit/REAC compartidos
"""

# ============================================================================
# REEXPORTS (modularización Fase 0 .. Fase 4)
# ============================================================================
# EXPLICACIÓN PARA PRINCIPIANTES:
# Los reexportamos aquí para que urls.py (views.foo) e imports antiguos
# (from almacen.views import ...) sigan funcionando sin cambios.
from .decorators import permission_required_with_message  # noqa: F401
from .views_dashboard_distribucion import (  # noqa: F401
    dashboard_distribucion_sucursales,
    exportar_distribucion_excel,
)
from .views_parametros_cotizador import (  # noqa: F401
    panel_parametros_cotizador,
)
from .views_catalogo import (  # noqa: F401
    acceso_denegado,
    api_buscar_productos,
    api_info_producto,
    crear_categoria,
    crear_producto,
    crear_proveedor,
    crear_solicitud,
    dashboard_almacen,
    detalle_producto,
    editar_categoria,
    editar_producto,
    editar_proveedor,
    eliminar_proveedor,
    lista_categorias,
    lista_movimientos,
    lista_productos,
    lista_proveedores,
    lista_solicitudes,
    procesar_solicitud,
)
from .views_unidades import (  # noqa: F401
    api_buscar_crear_orden_cliente,
    api_tecnicos_disponibles,
    api_unidad_info,
    api_unidades_producto,
    cambiar_estado_unidad,
    crear_unidad,
    detalle_unidad,
    editar_unidad,
    eliminar_unidad,
    lista_unidades,
    unidades_por_producto,
)
from .views_compras import (  # noqa: F401
    aprobar_cotizacion,
    cancelar_compra,
    confirmar_devolucion,
    crear_compra,
    detalle_compra,
    editar_compra,
    iniciar_devolucion,
    lista_compras,
    panel_cotizaciones,
    problema_unidad_compra,
    recibir_compra,
    recibir_unidad_compra,
    rechazar_cotizacion,
    reportar_problema_compra,
)
from .views_solicitudes_cotizacion import (  # noqa: F401
    agregar_servicio_adicional,
    api_imagenes_linea,
    aprobar_todos_servicios,
    cancelar_solicitud_cotizacion,
    crear_solicitud_cotizacion,
    detalle_solicitud_cotizacion,
    editar_lineas_cotizacion,
    editar_solicitud_cotizacion,
    eliminar_imagen_linea,
    eliminar_servicio_adicional,
    eliminar_solicitud_cotizacion,
    gestionar_imagenes_linea,
    lista_solicitudes_cotizacion,
    rechazar_todos_servicios,
    responder_servicio_adicional,
)
from .views_cotizacion_cliente import (  # noqa: F401
    api_enviar_cotizacion_cliente,
    aprobar_todas_lineas,
    descargar_pdf_cotizacion_final,
    enviar_solicitud_a_cliente,
    enviar_solicitud_cliente,
    notificar_front,
    preview_pdf_cotizacion,
    rechazar_todas_lineas,
    registrar_motivo_rechazo_solicitud,
    registrar_motivo_rechazo_st,
    responder_linea_cotizacion,
)
from .views_cotizacion_pnc_cliente import (  # noqa: F401
    notificar_cliente_pnc,
)
from .views_cotizacion_sync_st import (  # noqa: F401
    crear_orden_fl_desde_cotizacion,
    generar_compras_solicitud,
    vincular_orden_solicitud,
)
