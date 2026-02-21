"""
Tareas Celery de la app notificaciones.

EXPLICACIÓN PARA PRINCIPIANTES:
Este archivo contiene tareas que Celery ejecuta automáticamente
según un horario (Celery Beat). La única tarea aquí es la limpieza
automática de notificaciones antiguas.

¿POR QUÉ limpiar notificaciones?
Sin limpieza, la tabla crece indefinidamente. Si cada tarea Celery genera
~3 notificaciones (usuario + superusuarios) y tienes 20 tareas diarias,
en un año tendrías ~22,000 registros innecesarios.

Esta tarea corre cada noche a las 3:00 AM (configurado en settings.py
con CELERY_BEAT_SCHEDULE) y borra las notificaciones de más de 7 días.
"""

from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger('notificaciones')


@shared_task(
    name='notificaciones.limpiar_antiguas',
    ignore_result=True,  # No necesitamos guardar el resultado de esta tarea
)
def limpiar_notificaciones_antiguas(dias=7):
    """
    Elimina notificaciones con más de X días de antigüedad.

    EXPLICACIÓN PARA PRINCIPIANTES:
    - timezone.now() obtiene la fecha y hora actual (con zona horaria).
    - timedelta(days=7) resta 7 días a esa fecha.
    - __lt significa "less than" (menor que), es decir, "más antigua que".
    - .delete() borra los registros de la base de datos.

    Args:
        dias (int): Antigüedad máxima en días. Default: 7.

    Returns:
        dict: Cantidad de notificaciones eliminadas.
    """
    from .models import Notificacion

    fecha_limite = timezone.now() - timedelta(days=dias)

    # .delete() retorna una tupla: (total_borrados, {modelo: cantidad})
    total, detalle = Notificacion.objects.filter(
        fecha_creacion__lt=fecha_limite
    ).delete()

    logger.info(
        f"[LIMPIEZA] Eliminadas {total} notificación(es) con más de {dias} días de antigüedad."
    )

    return {
        'eliminadas': total,
        'dias_umbral': dias,
        'fecha_limite': fecha_limite.isoformat(),
    }
