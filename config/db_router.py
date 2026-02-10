# config/db_router.py
"""
EXPLICACIÓN PARA PRINCIPIANTES:
================================
En Django, normalmente todas las queries van a una sola base de datos.
Pero nosotros tenemos una BD por país: inventario_mexico, inventario_argentina, etc.

El Database Router es una clase que Django consulta ANTES de cada query:
- "¿Dónde leo este modelo?" → db_for_read()
- "¿Dónde escribo este modelo?" → db_for_write()
- "¿Puedo hacer relaciones entre estas tablas?" → allow_relation()
- "¿Aplico esta migración en esta BD?" → allow_migrate()

CÓMO FUNCIONA:
1. El PaisMiddleware guarda en thread-locals el país activo
2. Este router consulta thread-locals para saber la BD
3. Si hay un hint de instancia (ej: .using('argentina')), lo respeta

APPS QUE SIEMPRE VAN A 'default' (no se enrutan por país):
- sessions: Las sesiones de Django (cookies) deben ser consistentes
  sin importar el país. Si las enrutamos por país, el SessionMiddleware
  carga la sesión desde una BD y la intenta guardar en otra → crash.
- axes: Los registros de intentos de login fallidos. Si se enrutan
  por país, un atacante podría tener 5 intentos en México + 5 en
  Argentina = 10 intentos antes de ser bloqueado.
- contenttypes: ContentTypes debe ser consistente para el admin.

BUGS CORREGIDOS (v2.0):
- v1.0 ignoraba hints['instance'] — si hacías .using('argentina'),
  el router podía enviar la query a otra BD
- v1.0 fallaba con manage.py porque no hay request HTTP activo
  (thread-locals está vacío)

BUG CORREGIDO (v2.1):
- v2.0 enrutaba sessions/axes por país, causando SessionInterrupted
  porque SessionMiddleware carga la sesión desde 'default' al inicio
  del request (antes de PaisMiddleware), pero al final del request
  intenta guardarla en 'argentina' (donde no existe esa sesión).
"""

import logging
from .middleware_pais import get_current_db_alias

logger = logging.getLogger(__name__)

# ============================================================================
# APPS QUE SIEMPRE VAN A 'default' (NO se enrutan por país)
# ============================================================================
#
# EXPLICACIÓN PARA PRINCIPIANTES:
# Estas apps son de "infraestructura" de Django, no son datos de negocio.
# Si las enrutamos por país, se producen errores difíciles de depurar.
#
# Ejemplo del bug:
# 1. Visitas /admin/?pais=argentina (GET)
# 2. SessionMiddleware carga sesión desde 'default' (aún no hay país)
# 3. PaisMiddleware configura thread-locals → argentina
# 4. Haces login (POST) → Django intenta guardar sesión en 'argentina'
# 5. La sesión no existe en 'argentina' → SessionInterrupted!
#
# Solución: sessions, axes y contenttypes SIEMPRE van a 'default'.

APPS_SIEMPRE_DEFAULT = {
    'sessions',       # django.contrib.sessions — cookies de sesión
    'axes',           # django-axes — protección contra fuerza bruta
    'contenttypes',   # django.contrib.contenttypes — tipos de contenido
}


class PaisDBRouter:
    """
    Router que dirige queries a la base de datos del país activo.

    ORDEN DE PRIORIDAD para determinar la BD:
    0. Si la app está en APPS_SIEMPRE_DEFAULT → siempre 'default'
    1. hints['instance']._state.db — Si el objeto ya sabe su BD (ej: .using())
    2. Thread-locals (del PaisMiddleware) — País del request actual
    3. 'default' — Fallback seguro (para manage.py, migrations, shell)
    """

    def _get_db(self, model, **hints) -> str:
        """
        Determina la base de datos correcta para una operación.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Este método privado centraliza la lógica de decisión.
        Tanto db_for_read como db_for_write lo usan.

        Args:
            model: La clase del modelo (ej: OrdenServicio, Producto)
            **hints: Pistas que Django pasa, como la instancia del objeto

        Returns:
            str: Alias de la base de datos ('mexico', 'argentina', 'default')
        """
        # PRIORIDAD 0: Apps que SIEMPRE van a 'default'
        #
        # EXPLICACIÓN: Sessions, axes y contenttypes son de infraestructura.
        # Si las enrutamos por país, causan errores de SessionInterrupted
        # y problemas con el bloqueo de django-axes.
        app_label = model._meta.app_label
        if app_label in APPS_SIEMPRE_DEFAULT:
            return 'default'

        # PRIORIDAD 1: Respetar BD de la instancia (para .using() explícito)
        #
        # EXPLICACIÓN: Cuando haces OrdenServicio.objects.using('argentina').all()
        # Django pasa hints={'instance': <objeto>} y ese objeto tiene
        # _state.db = 'argentina'. Debemos respetar eso.
        instance = hints.get('instance')
        if instance is not None:
            db = getattr(getattr(instance, '_state', None), 'db', None)
            if db is not None:
                return db

        # PRIORIDAD 2: Thread-locals del middleware (request activo)
        #
        # EXPLICACIÓN: Si hay un request HTTP activo, el PaisMiddleware
        # ya guardó el alias de BD en thread-locals.
        db_alias = get_current_db_alias()
        if db_alias and db_alias != 'default':
            return db_alias

        # PRIORIDAD 3: Fallback a 'default'
        #
        # EXPLICACIÓN: Esto ocurre cuando:
        # - Ejecutas manage.py (no hay request HTTP)
        # - Ejecutas python manage.py shell
        # - Ejecutas migraciones
        # - Un celery task (si lo agregas en el futuro)
        # En estos casos, 'default' apunta a México (BD principal)
        return 'default'

    def db_for_read(self, model, **hints) -> str:
        """
        ¿En qué BD busco cuando QUIERO LEER datos?

        Django llama esto para: Model.objects.all(), .filter(), .get(), etc.
        """
        return self._get_db(model, **hints)

    def db_for_write(self, model, **hints) -> str:
        """
        ¿En qué BD escribo cuando QUIERO GUARDAR datos?

        Django llama esto para: .save(), .create(), .delete(), .update(), etc.
        """
        return self._get_db(model, **hints)

    def allow_relation(self, obj1, obj2, **hints) -> bool | None:
        """
        ¿Puedo crear una relación (ForeignKey) entre estos dos objetos?

        EXPLICACIÓN PARA PRINCIPIANTES:
        Django pregunta esto cuando intentas hacer algo como:
            orden.tecnico = empleado  # ForeignKey

        Si 'orden' está en BD México y 'empleado' en BD Argentina,
        eso sería un ERROR (no puedes hacer JOIN entre BDs diferentes).

        Regla: Solo permitir relaciones si ambos objetos están en la misma BD.

        Returns:
            True: Sí permitir
            False: No permitir
            None: No tengo opinión (dejar que Django decida)
        """
        db1 = getattr(getattr(obj1, '_state', None), 'db', None)
        db2 = getattr(getattr(obj2, '_state', None), 'db', None)

        if db1 and db2:
            return db1 == db2

        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints) -> bool | None:
        """
        ¿Aplico esta migración en esta base de datos?

        EXPLICACIÓN PARA PRINCIPIANTES:
        Cuando ejecutas: python manage.py migrate --database=argentina
        Django pregunta para CADA migración: "¿La aplico en 'argentina'?"

        Nuestra respuesta: SÍ, todas las apps van a todas las BDs.
        Cada país tiene una copia completa del schema (todas las tablas).

        Esto es diferente a un setup donde auth va a una BD y el resto a otra.
        En nuestro caso, CADA país tiene users, ordenes, productos, TODO.

        NOTA: Aunque sessions/axes se LEEN/ESCRIBEN solo desde 'default',
        las TABLAS sí se crean en todas las BDs (por si acaso).

        Returns:
            True: Sí aplicar migración
            None: Dejar que Django decida (equivalente a True para la mayoría)
        """
        # Todas las apps van a todas las BDs de país
        # Cada BD es una copia completa e independiente
        return True
