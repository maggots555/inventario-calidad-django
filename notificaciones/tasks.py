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

MULTI-PAÍS: La tarea itera sobre TODOS los países configurados para limpiar
la tabla de notificaciones de cada base de datos independiente. Sin esto,
solo se limpiaría México y el resto de países acumularía registros sin límite.
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
    Elimina notificaciones con más de X días de antigüedad en TODAS las BDs.

    EXPLICACIÓN PARA PRINCIPIANTES:
    - timezone.now() obtiene la fecha y hora actual (con zona horaria).
    - timedelta(days=7) resta 7 días a esa fecha.
    - __lt significa "less than" (menor que), es decir, "más antigua que".
    - .delete() borra los registros de la base de datos.

    MULTI-PAÍS: Esta tarea se ejecuta desde Celery Beat sin contexto HTTP,
    por lo que el middleware de país no corre. Usamos .using(db_alias) para
    acceder explícitamente a la BD de cada país configurado.

    Args:
        dias (int): Antigüedad máxima en días. Default: 7.

    Returns:
        dict: Total de notificaciones eliminadas en todas las BDs.
    """
    from .models import Notificacion
    from config.paises_config import PAISES_CONFIG

    fecha_limite = timezone.now() - timedelta(days=dias)
    total_global = 0

    # Iterar sobre cada país para limpiar su BD independiente
    for subdominio, pais_config in PAISES_CONFIG.items():
        db_alias = pais_config['db_alias']
        try:
            # .using(db_alias) apunta la query a la BD del país correcto
            total, _ = Notificacion.objects.using(db_alias).filter(
                fecha_creacion__lt=fecha_limite
            ).delete()

            if total > 0:
                logger.info(
                    f"[LIMPIEZA] [{subdominio}] Eliminadas {total} notificación(es) "
                    f"con más de {dias} días de antigüedad."
                )

            total_global += total

        except Exception as e:
            # Si una BD falla (ej. país recién agregado sin tabla), no detener las demás
            logger.error(f"[LIMPIEZA] [{subdominio}] Error al limpiar notificaciones: {e}")

    logger.info(
        f"[LIMPIEZA] Total global: {total_global} notificación(es) eliminadas "
        f"en {len(PAISES_CONFIG)} país(es)."
    )

    return {
        'eliminadas': total_global,
        'dias_umbral': dias,
        'fecha_limite': fecha_limite.isoformat(),
        'paises_procesados': list(PAISES_CONFIG.keys()),
    }
