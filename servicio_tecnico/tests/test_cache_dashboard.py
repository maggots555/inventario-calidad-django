"""
Tests del cache de dashboards (no mezclar HTML entre usuarios).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El dashboard se cachea 10 minutos para no regenerar Plotly en cada clic.
Ese HTML incluye el navbar con el nombre de quien está logueado.
Si el cache solo mira la URL, el segundo usuario ve el nombre del primero.

``cache_page_dashboard`` ahora varía por cookie de sesión. Este test clava
ese contrato con una vista dummy (no abre el dashboard real).
"""

from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase, override_settings

from servicio_tecnico.decorators import cache_page_dashboard

_CACHE_LOCAL = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'test-cache-dashboard-usuarios',
    }
}


@override_settings(CACHES=_CACHE_LOCAL, CACHE_TTL_DASHBOARD=60)
class CacheDashboardPorCookieTest(SimpleTestCase):
    """Cada sesión debe ver su propio HTML cacheado, no el del colega."""

    def setUp(self) -> None:
        self.factory = RequestFactory()

        @cache_page_dashboard
        def _vista_dummy(request):
            # El navbar real pinta el nombre; aquí basta un marcador por cookie.
            nombre = request.COOKIES.get('sessionid', 'anonimo')
            return HttpResponse(f'dashboard-de-{nombre}')

        self.vista = _vista_dummy

    def test_vary_cookie_en_la_respuesta(self) -> None:
        """Django debe anunciar que el cache depende de la cookie."""
        request = self.factory.get('/dashboard-test/', HTTP_COOKIE='sessionid=ana')
        respuesta = self.vista(request)
        vary = respuesta.get('Vary', '')
        self.assertIn('Cookie', vary)

    def test_dos_sesiones_no_comparten_html_cacheado(self) -> None:
        """
        Ana calienta el cache; Beto pide la misma URL y NO debe ver a Ana.
        """
        req_ana = self.factory.get(
            '/dashboard-test/',
            HTTP_COOKIE='sessionid=ana',
        )
        req_beto = self.factory.get(
            '/dashboard-test/',
            HTTP_COOKIE='sessionid=beto',
        )

        resp_ana = self.vista(req_ana)
        resp_beto = self.vista(req_beto)

        self.assertEqual(resp_ana.content, b'dashboard-de-ana')
        self.assertEqual(resp_beto.content, b'dashboard-de-beto')
