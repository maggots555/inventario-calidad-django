"""
Tests de humo tras modularizar vistas de Almacén (Fase 0 + Fase 1).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Estos tests NO abren el dashboard ni generan Excel real. Solo confirman que:
1) Los nombres siguen disponibles en almacen.views (urls.py no se rompe).
2) El callable de views.py es EXACTAMENTE el del módulo nuevo (misma identidad).
3) reverse/resolve apuntan a las funciones del módulo extraído.

Si alguien borra un reexport por error, este test falla antes de producción.
"""

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from almacen import views as almacen_views
from almacen import views_dashboard_distribucion
from almacen import views_parametros_cotizador
from almacen.decorators import permission_required_with_message


class CompatibilidadReexportsFase0Test(SimpleTestCase):
    """
    Verifica que el decorador se reexporta desde views.py.

    Objetivo de negocio:
        Mantener compatibilidad con imports antiguos y con los
        decoradores @permission_required_with_message del monolito residual.
    """

    def test_views_reexporta_decorador(self):
        """permission_required_with_message en views es el de decorators.py."""
        self.assertTrue(callable(almacen_views.permission_required_with_message))
        self.assertIs(
            almacen_views.permission_required_with_message,
            permission_required_with_message,
        )


class CompatibilidadReexportsFase1Test(SimpleTestCase):
    """
    Verifica reexports y resolución de URLs de la Fase 1.

    Módulos extraídos:
        - views_dashboard_distribucion
        - views_parametros_cotizador
    """

    def test_views_reexporta_dashboard_distribucion(self):
        """Los símbolos públicos de distribución siguen en views."""
        self.assertIs(
            almacen_views.dashboard_distribucion_sucursales,
            views_dashboard_distribucion.dashboard_distribucion_sucursales,
        )
        self.assertIs(
            almacen_views.exportar_distribucion_excel,
            views_dashboard_distribucion.exportar_distribucion_excel,
        )

    def test_views_reexporta_parametros_cotizador(self):
        """panel_parametros_cotizador en views es el del módulo nuevo."""
        self.assertIs(
            almacen_views.panel_parametros_cotizador,
            views_parametros_cotizador.panel_parametros_cotizador,
        )

    def test_modulo_correcto_fase1(self):
        """__module__ apunta al archivo hermano, no al monolito."""
        self.assertEqual(
            almacen_views.dashboard_distribucion_sucursales.__module__,
            'almacen.views_dashboard_distribucion',
        )
        self.assertEqual(
            almacen_views.exportar_distribucion_excel.__module__,
            'almacen.views_dashboard_distribucion',
        )
        self.assertEqual(
            almacen_views.panel_parametros_cotizador.__module__,
            'almacen.views_parametros_cotizador',
        )

    def test_url_distribucion_resuelve_al_modulo_nuevo(self):
        """
        reverse/resolve de distribución apuntan al callable extraído.

        Nota: exportar_distribucion_excel no tiene path() propio; se invoca
        desde el dashboard con ?export=excel, por eso solo resolvemos el dashboard.
        """
        url = reverse('almacen:dashboard_distribucion_sucursales')
        match = resolve(url)
        self.assertIs(
            match.func,
            views_dashboard_distribucion.dashboard_distribucion_sucursales,
        )

    def test_url_parametros_resuelve_al_modulo_nuevo(self):
        """reverse/resolve de parámetros apuntan al callable extraído."""
        url = reverse('almacen:panel_parametros_cotizador')
        match = resolve(url)
        self.assertIs(
            match.func,
            views_parametros_cotizador.panel_parametros_cotizador,
        )
