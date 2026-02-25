# config/middleware_pais.py
"""
EXPLICACIÓN PARA PRINCIPIANTES:
================================
Un "middleware" en Django es como un guardia de seguridad en la puerta.
Cada vez que alguien hace un request (visita una página), el middleware
lo intercepta ANTES de que llegue a la vista.

Este middleware hace lo siguiente:
1. Mira la URL que visitó el usuario (ej: mexico.sigmasystem.work)
2. Extrae la parte del subdominio (ej: "mexico")
3. Busca la configuración de ese país
4. Guarda esa info en un lugar especial (thread-locals) para que
   el Database Router sepa a qué base de datos enviar las queries

CONCEPTO CLAVE - Thread-locals:
Imagina que cada "hilo" (thread) de tu servidor es un trabajador.
Thread-locals es como una nota adhesiva personal de cada trabajador.
Si el trabajador A atiende a México, su nota dice "México".
Si el trabajador B atiende a Argentina, su nota dice "Argentina".
Así no se confunden entre sí.

BUG CORREGIDO (v2.0):
La v1.0 NO limpiaba las notas adhesivas si ocurría un error.
Ahora usamos try/finally para SIEMPRE limpiar, sin importar si hubo error.
"""

import threading
import logging
from zoneinfo import ZoneInfo

from django.utils import timezone as dj_timezone

from .paises_config import PAISES_CONFIG, PAIS_DEFAULT, get_pais_config

logger = logging.getLogger(__name__)

# ============================================================================
# THREAD-LOCALS — "Notas adhesivas" por hilo del servidor
# ============================================================================
# 
# EXPLICACIÓN PARA PRINCIPIANTES:
# _thread_locals es una variable global PERO cada thread (hilo) del servidor
# tiene su propia copia. Es como si cada mesero de un restaurante tuviera
# su propia libreta donde anota qué mesa está atendiendo.
#
# Gunicorn usa 5 workers (procesos), y cada uno puede tener múltiples threads.
# Thread-locals garantiza que si un thread atiende a México y otro a Argentina,
# no se mezclen los datos.

_thread_locals = threading.local()


def get_current_db_alias() -> str:
    """
    Retorna el alias de la base de datos del país activo en este thread.

    EXPLICACIÓN PARA PRINCIPIANTES:
    El Database Router llama a esta función para saber a qué BD enviar
    cada query. Si no hay país activo (ej: manage.py, migrations),
    retorna 'default'.

    Returns:
        str: Alias de BD ('mexico', 'argentina', o 'default')
    """
    return getattr(_thread_locals, 'db_alias', 'default')


def get_current_pais_config() -> dict | None:
    """
    Retorna la configuración completa del país activo.
    Útil en vistas y utilidades que necesitan datos del país
    pero no tienen acceso al request.

    Returns:
        dict con configuración del país, o None
    """
    return getattr(_thread_locals, 'pais_config', None)


def get_current_pais_codigo() -> str | None:
    """
    Retorna el código ISO del país activo (ej: 'MX', 'AR').
    """
    return getattr(_thread_locals, 'pais_codigo', None)


class PaisMiddleware:
    """
    Middleware que detecta el país del request y configura thread-locals.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Este middleware se ejecuta en CADA request, antes que cualquier vista.
    Su trabajo es:
    1. Leer el subdominio de la URL
    2. Buscar la configuración del país
    3. Guardar esa info para que el resto del sistema la use
    4. SIEMPRE limpiar la info al terminar (incluso si hay error)

    POSICIÓN EN MIDDLEWARE (settings.py):
    Debe ir DESPUÉS de SessionMiddleware y AuthenticationMiddleware,
    pero ANTES de ForcePasswordChangeMiddleware.

    ¿POR QUÉ después de AuthenticationMiddleware?
    Porque necesitamos que request.user ya esté disponible.

    ¿POR QUÉ antes de ForcePasswordChangeMiddleware?
    Porque ese middleware hace queries (request.user.empleado)
    y necesita que el DB Router ya sepa a qué BD ir.
    """

    def __init__(self, get_response):
        """
        EXPLICACIÓN PARA PRINCIPIANTES:
        __init__ se ejecuta UNA SOLA VEZ cuando Django arranca.
        get_response es la función que llama al siguiente middleware o vista.
        """
        self.get_response = get_response

    def __call__(self, request):
        """
        Se ejecuta en CADA request HTTP.

        FLUJO:
        1. Detectar país del subdominio
        2. Configurar thread-locals
        3. Procesar request (try)
        4. SIEMPRE limpiar thread-locals (finally)

        BUG CORREGIDO (v2.0):
        La v1.0 hacía esto:
            self._set_thread_locals(...)
            response = self.get_response(request)  # Si esto explota...
            self._clear_thread_locals()             # ...esto NUNCA se ejecuta

        La v2.0 usa try/finally:
            self._set_thread_locals(...)
            try:
                response = self.get_response(request)
            finally:
                self._clear_thread_locals()  # SIEMPRE se ejecuta
        """
        # Paso 1: Detectar el país
        pais_subdominio = self._detectar_pais(request)
        pais_config = get_pais_config(pais_subdominio)

        if pais_config is None:
            # Subdominio no reconocido → usar país por defecto
            logger.warning(
                f"Subdominio no reconocido: '{pais_subdominio}' "
                f"(Host: {request.get_host()}). Usando país default: {PAIS_DEFAULT}"
            )
            pais_subdominio = PAIS_DEFAULT
            pais_config = get_pais_config(PAIS_DEFAULT)

        # Paso 2: Configurar thread-locals y request
        self._set_thread_locals(pais_config)
        request.pais_config = pais_config
        request.pais_codigo = pais_config['codigo']
        request.pais_subdominio = pais_subdominio

        # EXPLICACIÓN PARA PRINCIPIANTES:
        # Aquí le decimos a Django: "Para este request, usa esta zona horaria".
        # Esto hace que el filtro |date: en los templates convierta
        # automáticamente todas las fechas UTC a la hora local del país.
        # Sin esto, Django muestra todas las fechas en UTC (el valor de TIME_ZONE).
        # Es el mecanismo oficial de Django para zonas horarias por request.
        tz_nombre = pais_config.get('timezone', 'America/Mexico_City')
        dj_timezone.activate(ZoneInfo(tz_nombre))

        # Paso 3: Procesar request con limpieza garantizada
        try:
            response = self.get_response(request)
        finally:
            # Paso 4: SIEMPRE limpiar thread-locals y zona horaria activa
            # Esto es CRÍTICO — sin esto, el siguiente request en este
            # thread podría heredar datos del país equivocado
            dj_timezone.deactivate()
            self._clear_thread_locals()

        return response

    def _detectar_pais(self, request) -> str:
        """
        Detecta el país a partir del Host header del request.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Cuando visitas mexico.sigmasystem.work, el navegador envía
        un header "Host: mexico.sigmasystem.work". Esta función
        extrae "mexico" de ese header.

        MODO DESARROLLO:
        En desarrollo local, los subdominios pueden no funcionar.
        Por eso soportamos un parámetro GET ?pais=argentina
        que tiene prioridad sobre el subdominio.
        Esto permite probar: http://localhost:8000/ordenes/?pais=argentina

        Además, cuando se detecta ?pais=X, se guarda en la SESIÓN
        para que los POSTs siguientes (como el login del admin)
        mantengan el país correcto sin necesitar ?pais= en cada URL.

        Returns:
            str: Subdominio del país (ej: 'mexico', 'argentina')
        """
        # Prioridad 1: Parámetro GET para desarrollo
        # SOLO funciona si DEBUG=True (seguridad)
        from django.conf import settings
        if settings.DEBUG:
            pais_param = request.GET.get('pais')
            if pais_param and pais_param in PAISES_CONFIG:
                # Guardar en sesión para que los POSTs siguientes
                # (ej: login del admin) mantengan el país correcto
                # EXPLICACIÓN PARA PRINCIPIANTES:
                # Sin esto, si entras a /sic-gestion-sistema/?pais=argentina,
                # la página se muestra bien (GET), pero cuando envías el
                # formulario de login (POST), el ?pais= se pierde y Django
                # busca tu usuario en México en vez de Argentina.
                if hasattr(request, 'session'):
                    request.session['_pais_override'] = pais_param
                return pais_param

            # Prioridad 1b: País guardado en sesión (de un ?pais= anterior)
            if hasattr(request, 'session'):
                pais_sesion = request.session.get('_pais_override')
                if pais_sesion and pais_sesion in PAISES_CONFIG:
                    return pais_sesion

        # Prioridad 2: Subdominio del Host header
        host = request.get_host().split(':')[0]  # Quitar puerto si existe

        # Extraer subdominio: "mexico.sigmasystem.work" → "mexico"
        parts = host.split('.')

        if len(parts) >= 3:
            # Tiene subdominio: mexico.sigmasystem.work → ['mexico', 'sigmasystem', 'work']
            subdominio = parts[0]
            if subdominio in PAISES_CONFIG:
                return subdominio

        # También soportar: mexico.localhost (para desarrollo con /etc/hosts)
        if len(parts) >= 2:
            subdominio = parts[0]
            if subdominio in PAISES_CONFIG:
                return subdominio

        # No se detectó país → usar default
        return PAIS_DEFAULT

    def _set_thread_locals(self, pais_config: dict):
        """Guarda la configuración del país en thread-locals."""
        _thread_locals.pais_codigo = pais_config['codigo']
        _thread_locals.db_alias = pais_config['db_alias']
        _thread_locals.pais_config = pais_config

    def _clear_thread_locals(self):
        """
        Limpia thread-locals al terminar el request.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Esto es como borrar la pizarra después de cada clase.
        Si no lo haces, el siguiente "estudiante" (request) podría
        ver datos que no le corresponden.

        Usamos hasattr() porque en algunos edge cases el atributo
        podría no existir (ej: si _set_thread_locals falló a medias).
        """
        if hasattr(_thread_locals, 'pais_codigo'):
            del _thread_locals.pais_codigo
        if hasattr(_thread_locals, 'db_alias'):
            del _thread_locals.db_alias
        if hasattr(_thread_locals, 'pais_config'):
            del _thread_locals.pais_config
