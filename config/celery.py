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
import inspect
import os
from celery import Celery
from celery.signals import task_prerun, task_postrun

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


# ============================================================================
# SEÑALES CELERY — Contexto Multi-País
# ============================================================================
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# Celery corre en un proceso separado al servidor web (Gunicorn). Eso significa
# que cuando una tarea se ejecuta, NO hay ningún request HTTP activo, y el
# middleware PaisMiddleware nunca se ejecuta. Por lo tanto, el DB router no sabe
# en qué base de datos buscar — y por defecto usa 'default' (México).
#
# SOLUCIÓN: Usamos señales de Celery.
#   - task_prerun  → se dispara ANTES de cada tarea → establece el contexto de país
#   - task_postrun → se dispara DESPUÉS de cada tarea → limpia el contexto
#
# ¿Cómo llega el db_alias a la tarea?
# Cada .delay() pasa `db_alias=get_pais_actual()['db_alias']` (con nombre).
# La cadena del video rewind antes lo mandaba suelto, en la posición 3.
# Esta señal lo busca por nombre y, si no está, en la firma de la función.
# Con eso configura los thread-locals, igual que PaisMiddleware en un request.
# ============================================================================

def resolver_db_alias_tarea(task, args, kwargs) -> str:
    """
    Saca el alias de base que la vista le pasó a la tarea Celery.

    Objetivo: que el worker abra la base del país correcto (argentina, chile,
    colombia o mexico) antes de buscar la orden. Si el alias no viene, el
    país por defecto es México.

    Args:
        task   : tarea Celery que está por correr (tiene .run con la firma).
        args   : valores posicionales. En el rewind viejo, el país iba aquí.
        kwargs : valores con nombre. Los correos mandan db_alias= aquí.

    Returns:
        str: alias tal como lo encoló la vista, o PAIS_DEFAULT ('mexico')
        si la tarea no trae país (Beat, tarea vieja).

    Efectos secundarios:
        Ninguno. No toca thread-locals ni la base de datos.
    """
    from config.paises_config import PAIS_DEFAULT

    argumentos = kwargs or {}
    # Los correos y el video de galería llegan así: db_alias='argentina'.
    alias_nombrado = argumentos.get('db_alias')
    if alias_nombrado:
        return alias_nombrado

    # Cadena del rewind: el país iba suelto (posición), sin el nombre db_alias=.
    # La firma dice en qué lugar está, para no confundirlo con el id de la orden.
    try:
        firma = inspect.signature(task.run)
        ligados = firma.bind_partial(*(args or ()), **argumentos)
        alias_posicional = ligados.arguments.get('db_alias')
    except (TypeError, ValueError, AttributeError):
        alias_posicional = None

    if alias_posicional:
        return alias_posicional

    return PAIS_DEFAULT


@task_prerun.connect
def configurar_contexto_pais(task_id, task, args, kwargs, **extra):
    """
    Señal que se ejecuta antes de cada tarea Celery.
    Lee db_alias (por nombre o por posición en la firma) y establece el
    contexto de país en los thread-locals del worker, para que el DB router
    y get_pais_actual() funcionen dentro de la tarea.

    Args:
        task_id : ID único de la tarea en ejecución
        task    : Instancia de la tarea Celery
        args    : Argumentos posicionales (el rewind viejo traía el país aquí)
        kwargs  : Argumentos con nombre (aquí suele venir 'db_alias')

    Efectos secundarios:
        Escribe db_alias, pais_config y pais_codigo en el thread-local
        de este worker. La señal task_postrun los borra al terminar.
    """
    from config.middleware_pais import _thread_locals
    from config.paises_config import PAISES_CONFIG, PAIS_DEFAULT

    # País que encoló la vista. Si no vino, PAIS_DEFAULT es la clave 'mexico'.
    db_alias = resolver_db_alias_tarea(task, args, kwargs)

    # Buscar la configuración completa del país que corresponde a ese alias
    pais_config = None
    for subdominio, config in PAISES_CONFIG.items():
        if config['db_alias'] == db_alias:
            pais_config = config
            break

    # Fallback al país por defecto si el alias no existe en la configuración
    if pais_config is None:
        pais_config = PAISES_CONFIG[PAIS_DEFAULT]

    # Establecer los tres valores en el thread-local del worker de Celery
    # Esto replica exactamente lo que hace PaisMiddleware._set_thread_locals()
    _thread_locals.db_alias = pais_config['db_alias']
    _thread_locals.pais_config = pais_config
    _thread_locals.pais_codigo = pais_config['codigo']


@task_postrun.connect
def limpiar_contexto_pais(task_id, task, args, kwargs, retval, state, **extra):
    """
    Señal que se ejecuta después de cada tarea Celery (éxito o fallo).
    Limpia los thread-locals del worker para evitar que el contexto de un país
    contamine la siguiente tarea que ejecute el mismo proceso worker.

    Args:
        state  : Estado final ('SUCCESS', 'FAILURE', etc.)
        retval : Valor de retorno de la tarea
    """
    from config.middleware_pais import _thread_locals

    # Eliminar los tres atributos que estableció configurar_contexto_pais
    for atributo in ('db_alias', 'pais_config', 'pais_codigo'):
        if hasattr(_thread_locals, atributo):
            delattr(_thread_locals, atributo)
