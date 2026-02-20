"""
Configuración de Celery para el proyecto.

EXPLICACIÓN PARA PRINCIPIANTES:
Celery es un sistema de tareas en segundo plano. Cuando tu aplicación
Django necesita hacer algo que tarda (enviar un email, generar un PDF,
hacer cálculos ML), en lugar de hacer esperar al usuario, se lo "delega"
a Celery que lo procesa en paralelo.

Redis actúa como el "mensajero": Django le dice a Redis "ejecuta esta
tarea", y Celery lee ese mensaje y la ejecuta.

Flujo:
    Django (web) → Redis (cola de mensajes) → Celery Worker (procesamiento)
                                                        ↓
                                              Resultado guardado en BD
"""
import os
from celery import Celery

# EXPLICACIÓN:
# Esta línea le dice a Celery cuál es el archivo settings.py de Django.
# 'config.settings' significa: dentro de la carpeta 'config', el archivo 'settings.py'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Creamos la aplicación Celery con el nombre de nuestro proyecto
app = Celery('inventario_calidad')

# EXPLICACIÓN:
# namespace='CELERY' significa que todas las configuraciones de Celery
# en settings.py deben empezar con "CELERY_". Por ejemplo:
#   - CELERY_BROKER_URL
#   - CELERY_RESULT_BACKEND
#   - CELERY_TASK_SERIALIZER
# Esto evita conflictos con otras configuraciones de Django.
app.config_from_object('django.conf:settings', namespace='CELERY')

# EXPLICACIÓN:
# Esta línea hace que Celery busque automáticamente archivos llamados 'tasks.py'
# dentro de todas las apps instaladas en Django (INSTALLED_APPS).
# Así no tienes que registrar cada tarea manualmente.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """
    Tarea de prueba para verificar que Celery funciona correctamente.

    EXPLICACIÓN:
    'bind=True' hace que la tarea reciba una referencia a sí misma (self),
    útil para obtener información de la tarea (ID, reintentos, etc.)

    Para probar: desde la terminal Django shell ejecuta:
        from config.celery import debug_task
        debug_task.delay()
    """
    print(f'Tarea de prueba ejecutada. Request: {self.request!r}')
