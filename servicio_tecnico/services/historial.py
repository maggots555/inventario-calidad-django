"""
Registro de eventos en el historial de una orden de servicio.

EXPLICACIÓN PARA PRINCIPIANTES:
Antes esta función vivía en views.py y Celery/Almacén la importaban desde ahí
(con riesgo de imports circulares). Ahora vive en un módulo de servicio puro:
solo crea un HistorialOrden; no renderiza HTML ni conoce request.
"""

from servicio_tecnico.models import HistorialOrden


def registrar_historial(orden, tipo_evento, usuario, comentario='', es_sistema=False):
    """
    Crea un evento en el historial de la orden (trazabilidad del proceso).

    Args:
        orden: Instancia de OrdenServicio a la que pertenece el evento.
        tipo_evento (str): Código de TIPO_EVENTO_CHOICES
            (ej: 'comentario', 'cotizacion', 'sistema').
        usuario: Empleado (o None) asociado al evento; puede ser None si es_sistema.
        comentario (str): Texto libre que describe qué ocurrió.
        es_sistema (bool): True si el evento lo generó el sistema (no un humano).

    Returns:
        HistorialOrden: Instancia recién creada en la base de datos.

    Efectos secundarios:
        Inserta una fila en la tabla HistorialOrden (BD del país activo).
    """
    # EXPLICACIÓN PARA PRINCIPIANTES:
    # Un solo create() es suficiente: el modelo ya define defaults (fecha_evento).
    return HistorialOrden.objects.create(
        orden=orden,
        tipo_evento=tipo_evento,
        comentario=comentario,
        usuario=usuario,
        es_sistema=es_sistema,
    )
