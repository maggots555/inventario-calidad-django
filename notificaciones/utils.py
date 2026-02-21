"""
Funciones helper para crear notificaciones desde tareas Celery.

EXPLICACIÓN PARA PRINCIPIANTES:
Estas funciones simplifican la creación de notificaciones.
En lugar de importar el modelo y escribir Notificacion.objects.create(...)
en cada tarea, usas atajos como:

    from notificaciones.utils import notificar_exito, notificar_error

    # Cuando la tarea termina bien:
    notificar_exito(
        titulo="Correo RHITSO enviado",
        mensaje="Se envió a 3 destinatarios correctamente.",
        usuario=usuario,
        app_origen="servicio_tecnico"
    )

    # Cuando la tarea falla:
    notificar_error(
        titulo="Error al enviar correo",
        mensaje="No se pudo conectar al servidor SMTP.",
        usuario=usuario,
        app_origen="servicio_tecnico"
    )

Estas funciones también crean notificaciones para superusuarios automáticamente,
para que los administradores siempre estén al tanto de lo que pasa.
"""

import logging
from django.core.cache import cache
from django.contrib.auth.models import User

logger = logging.getLogger('notificaciones')


def crear_notificacion(titulo, mensaje, tipo='info', usuario=None,
                       task_id=None, app_origen=None):
    """
    Función base para crear una notificación en la base de datos.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Esta función guarda un registro en la tabla Notificacion.
    El panel de la campanita (TypeScript) lee estos registros cada 15 segundos.

    Args:
        titulo (str): Texto corto (máx 200 caracteres).
        mensaje (str): Descripción detallada de lo que pasó.
        tipo (str): 'exito', 'error', 'warning', 'info'.
        usuario (User, optional): Usuario que disparó la tarea. None = global.
        task_id (str, optional): ID de la tarea Celery.
        app_origen (str, optional): App que originó la notificación.

    Returns:
        list[Notificacion]: Lista de notificaciones creadas (usuario + superusers).
    """
    # EXPLICACIÓN: Import local para evitar importaciones circulares.
    # Si importamos el modelo al inicio del archivo, puede causar problemas
    # cuando Django aún está cargando las apps.
    from .models import Notificacion

    notificaciones_creadas = []

    # ── 1. Crear notificación para el usuario que disparó la tarea ──
    if usuario:
        notif = Notificacion.objects.create(
            titulo=titulo,
            mensaje=mensaje,
            tipo=tipo,
            usuario=usuario,
            task_id=task_id,
            app_origen=app_origen,
        )
        notificaciones_creadas.append(notif)
        # Invalidar cache para que el próximo polling muestre la nueva notificación
        cache.delete(f'notif:{usuario.pk}')
        logger.info(f"[NOTIF] Creada para usuario '{usuario.username}': {titulo}")

    # ── 2. Crear notificación para superusuarios (que no sean el mismo usuario) ──
    # EXPLICACIÓN: Los superusuarios ven TODO. Si el usuario que disparó la tarea
    # ya es superusuario, no le duplicamos la notificación.
    superusers = User.objects.filter(is_superuser=True)
    if usuario:
        superusers = superusers.exclude(pk=usuario.pk)

    for su in superusers:
        notif_su = Notificacion.objects.create(
            titulo=titulo,
            mensaje=mensaje,
            tipo=tipo,
            usuario=su,
            task_id=task_id,
            app_origen=app_origen,
        )
        notificaciones_creadas.append(notif_su)
        # Invalidar cache de cada superusuario
        cache.delete(f'notif:{su.pk}')

    if superusers.exists():
        logger.info(f"[NOTIF] Creada para {superusers.count()} superusuario(s): {titulo}")

    return notificaciones_creadas


def notificar_exito(titulo, mensaje, **kwargs):
    """
    Atajo para notificaciones de éxito ✅

    Uso:
        notificar_exito("Correo enviado", "Enviado a cliente@email.com",
                        usuario=user_obj, app_origen="servicio_tecnico")
    """
    return crear_notificacion(titulo, mensaje, tipo='exito', **kwargs)


def notificar_error(titulo, mensaje, **kwargs):
    """
    Atajo para notificaciones de error ❌

    Uso:
        notificar_error("Error al enviar correo", "Timeout en servidor SMTP",
                        usuario=user_obj, app_origen="servicio_tecnico")
    """
    return crear_notificacion(titulo, mensaje, tipo='error', **kwargs)


def notificar_warning(titulo, mensaje, **kwargs):
    """
    Atajo para notificaciones de advertencia ⚠️

    Uso:
        notificar_warning("Disco casi lleno", "Quedan 2 GB libres",
                          app_origen="config")
    """
    return crear_notificacion(titulo, mensaje, tipo='warning', **kwargs)


def notificar_info(titulo, mensaje, **kwargs):
    """
    Atajo para notificaciones informativas ℹ️

    Uso:
        notificar_info("Backup completado", "Se respaldaron 150 registros",
                       app_origen="scripts")
    """
    return crear_notificacion(titulo, mensaje, tipo='info', **kwargs)
