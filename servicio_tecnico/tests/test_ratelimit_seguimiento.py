"""
Tests del rate limit del portal de seguimiento (sí debe bloquear).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
``@ratelimit`` sin ``block=True`` solo anota ``request.limited`` y la
vista sigue. El portal público ahora copia el patrón de facturación:
``block=True`` → Django responde 403 (Ratelimited es PermissionDenied).

Este archivo clava dos cosas:
1) El módulo de seguimiento no tiene ningún ``@ratelimit`` decorativo.
2) El patrón ``block=True`` sí corta el abuso (vista dummy, cache local).
"""

from pathlib import Path

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.views.decorators.http import require_GET
from django_ratelimit.decorators import ratelimit
from django_ratelimit.exceptions import Ratelimited

_CACHE_LOCAL = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-ratelimit-seguimiento',
    }
}

_VISTA_SEGUIMIENTO = (
    Path(__file__).resolve().parents[1] / 'views_seguimiento_cliente.py'
)


class RatelimitSeguimientoFuenteTest(SimpleTestCase):
    """Ningún @ratelimit del portal puede quedarse sin block=True."""

    def test_todos_los_ratelimit_del_portal_bloquean(self) -> None:
        fuente = _VISTA_SEGUIMIENTO.read_text(encoding='utf-8')
        # Solo las líneas del decorador: el comentario también dice block=True.
        decoradores = [
            linea.strip()
            for linea in fuente.splitlines()
            if linea.strip().startswith('@ratelimit(')
        ]
        self.assertGreater(len(decoradores), 0)
        sin_bloqueo = [d for d in decoradores if 'block=True' not in d]
        self.assertEqual(sin_bloqueo, [])


@override_settings(
    RATELIMIT_ENABLE=True,
    RATELIMIT_USE_CACHE='default',
    CACHES=_CACHE_LOCAL,
)
class RatelimitBlockTrueCortaAbusoTest(SimpleTestCase):
    """Con block=True, la 3ª petición en un límite 2/m debe ser 403."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

        @ratelimit(key='ip', rate='2/m', method='GET', block=True)
        @require_GET
        def _vista_dummy(request):
            return HttpResponse('ok-seguimiento')

        self.vista = _vista_dummy

    def test_exceso_lanza_ratelimited(self) -> None:
        """
        Las dos primeras pasan; la tercera es abuso y Django la trata como 403.
        """
        # EXPLICACIÓN: misma IP en las tres (REMOTE_ADDR del factory).
        req1 = self.factory.get('/seguimiento-test/')
        req2 = self.factory.get('/seguimiento-test/')
        req3 = self.factory.get('/seguimiento-test/')

        self.assertEqual(self.vista(req1).status_code, 200)
        self.assertEqual(self.vista(req2).status_code, 200)
        with self.assertRaises(Ratelimited):
            self.vista(req3)
