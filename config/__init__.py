# EXPLICACIÓN PARA PRINCIPIANTES:
# Este archivo __init__.py le dice a Python que la carpeta 'config' es un paquete.
# Al importar la app de Celery aquí, nos aseguramos de que Celery se inicialice
# cada vez que Django arranque, para que las tareas decoradas con @shared_task
# funcionen correctamente en todas las apps.

from .celery import app as celery_app

# Exportamos 'celery_app' para que esté disponible cuando otros módulos
# hagan: from config import celery_app
__all__ = ('celery_app',)
