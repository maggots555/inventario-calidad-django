"""
Servicios de dominio de Servicio Técnico (lógica fuera de las vistas HTTP).

EXPLICACIÓN PARA PRINCIPIANTES:
Aquí van helpers que crean registros o coordinan reglas de negocio y que
pueden usarse desde views, tasks Celery u otras apps (p. ej. Almacén),
sin depender del monolito views.py.
"""

from .historial import registrar_historial
from .multimedia import comprimir_y_guardar_imagen, comprimir_y_guardar_video
from .notificaciones_piezas import (
    enviar_notificacion_pieza_recibida,
    _enviar_notificacion_pieza_recibida,
)
from .ventas_mostrador_analytics import (
    determinar_categoria_venta,
    obtener_top_productos_vendidos,
)

__all__ = [
    'registrar_historial',
    'comprimir_y_guardar_imagen',
    'comprimir_y_guardar_video',
    'enviar_notificacion_pieza_recibida',
    '_enviar_notificacion_pieza_recibida',
    'determinar_categoria_venta',
    'obtener_top_productos_vendidos',
]
