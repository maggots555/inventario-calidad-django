"""
Tests de humo tras extraer dashboards grandes + exports (Fase 8).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No renderizamos Plotly ni generamos Excel reales en CI. Solo confirmamos:
1) urls.py resuelve cada ruta al módulo nuevo.
2) views.py reexporta (compatibilidad).
3) Helpers de venta mostrador viven en services/.
4) Imports críticos existen (regresión NameError).
5) detalle_orden sigue en el monolito (Fase 10).
"""

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from servicio_tecnico import views as st_views
from servicio_tecnico import views_dashboard_cotizaciones
from servicio_tecnico import views_dashboard_oow_fl
from servicio_tecnico import views_dashboard_rhitso
from servicio_tecnico import views_dashboard_seguimiento_piezas
from servicio_tecnico.services import ventas_mostrador_analytics as vm_analytics


class CompatibilidadDashboardsFase8Test(SimpleTestCase):
    """Reexports + resolve sin tocar BD."""

    def test_helpers_en_services_y_reexport(self):
        """Analytics VM viven en services y se reexportan desde views."""
        self.assertIs(
            st_views.determinar_categoria_venta,
            vm_analytics.determinar_categoria_venta,
        )
        self.assertIs(
            st_views.obtener_top_productos_vendidos,
            vm_analytics.obtener_top_productos_vendidos,
        )
        self.assertEqual(
            vm_analytics.determinar_categoria_venta.__module__,
            'servicio_tecnico.services.ventas_mostrador_analytics',
        )
        # OOW importa los mismos símbolos (no copia del monolito)
        self.assertIs(
            views_dashboard_oow_fl.determinar_categoria_venta,
            vm_analytics.determinar_categoria_venta,
        )

    def test_views_reexporta_dashboard_rhitso(self):
        """Dashboard RHITSO consolidado vía views."""
        self.assertIs(st_views.dashboard_rhitso, views_dashboard_rhitso.dashboard_rhitso)
        self.assertIs(
            st_views.exportar_excel_rhitso,
            views_dashboard_rhitso.exportar_excel_rhitso,
        )
        self.assertIs(
            st_views.exportar_analisis_rhitso,
            views_dashboard_rhitso.exportar_analisis_rhitso,
        )

    def test_views_reexporta_oow_fl(self):
        """Dashboard OOW/FL vía views."""
        self.assertIs(
            st_views.dashboard_seguimiento_oow_fl,
            views_dashboard_oow_fl.dashboard_seguimiento_oow_fl,
        )
        self.assertIs(
            st_views.exportar_excel_dashboard_oow_fl,
            views_dashboard_oow_fl.exportar_excel_dashboard_oow_fl,
        )

    def test_views_reexporta_cotizaciones(self):
        """Dashboard cotizaciones + exports vía views."""
        self.assertIs(
            st_views.dashboard_cotizaciones,
            views_dashboard_cotizaciones.dashboard_cotizaciones,
        )
        self.assertIs(
            st_views.exportar_dashboard_cotizaciones,
            views_dashboard_cotizaciones.exportar_dashboard_cotizaciones,
        )
        self.assertIs(
            st_views.exportar_analisis_rechazos,
            views_dashboard_cotizaciones.exportar_analisis_rechazos,
        )
        self.assertIs(
            st_views.exportar_analisis_aceptaciones,
            views_dashboard_cotizaciones.exportar_analisis_aceptaciones,
        )

    def test_views_reexporta_seguimiento_piezas(self):
        """Dashboard piezas vía views."""
        self.assertIs(
            st_views.dashboard_seguimiento_piezas,
            views_dashboard_seguimiento_piezas.dashboard_seguimiento_piezas,
        )
        self.assertIs(
            st_views.exportar_dashboard_seguimiento_piezas,
            views_dashboard_seguimiento_piezas.exportar_dashboard_seguimiento_piezas,
        )

    def test_urls_dashboards_resuelven_modulos_nuevos(self):
        """reverse/resolve apuntan a los hermanos Fase 8."""
        casos = [
            (
                'servicio_tecnico:dashboard_rhitso',
                {},
                views_dashboard_rhitso.dashboard_rhitso,
            ),
            (
                'servicio_tecnico:exportar_excel_rhitso',
                {},
                views_dashboard_rhitso.exportar_excel_rhitso,
            ),
            (
                'servicio_tecnico:exportar_analisis_rhitso',
                {},
                views_dashboard_rhitso.exportar_analisis_rhitso,
            ),
            (
                'servicio_tecnico:dashboard_seguimiento_oow_fl',
                {},
                views_dashboard_oow_fl.dashboard_seguimiento_oow_fl,
            ),
            (
                'servicio_tecnico:exportar_excel_dashboard_oow_fl',
                {},
                views_dashboard_oow_fl.exportar_excel_dashboard_oow_fl,
            ),
            (
                'servicio_tecnico:dashboard_cotizaciones',
                {},
                views_dashboard_cotizaciones.dashboard_cotizaciones,
            ),
            (
                'servicio_tecnico:exportar_dashboard_cotizaciones',
                {},
                views_dashboard_cotizaciones.exportar_dashboard_cotizaciones,
            ),
            (
                'servicio_tecnico:exportar_analisis_rechazos',
                {},
                views_dashboard_cotizaciones.exportar_analisis_rechazos,
            ),
            (
                'servicio_tecnico:exportar_analisis_aceptaciones',
                {},
                views_dashboard_cotizaciones.exportar_analisis_aceptaciones,
            ),
            (
                'servicio_tecnico:dashboard_seguimiento_piezas',
                {},
                views_dashboard_seguimiento_piezas.dashboard_seguimiento_piezas,
            ),
            (
                'servicio_tecnico:exportar_dashboard_seguimiento_piezas',
                {},
                views_dashboard_seguimiento_piezas.exportar_dashboard_seguimiento_piezas,
            ),
        ]
        for name, kwargs, expected in casos:
            with self.subTest(name=name):
                url = reverse(name, kwargs=kwargs)
                match = resolve(url)
                self.assertIs(match.func, expected, msg=f'Fallo en {name}')

    def test_detalle_orden_sigue_en_monolito(self):
        """Fase 10: detalle_orden aún no se movió (inicio/listas ya son Fase 9)."""
        self.assertEqual(
            st_views.detalle_orden.__module__,
            'servicio_tecnico.views',
        )
        # Fase 9 movió inicio/listas a views_ordenes
        self.assertEqual(
            st_views.inicio.__module__,
            'servicio_tecnico.views_ordenes',
        )

    def test_imports_criticos_modulos(self):
        """Regresión NameError en headers de cada dashboard."""
        casos = [
            (
                views_dashboard_rhitso,
                (
                    'Prefetch',
                    'timezone',
                    'openpyxl',
                    'Font',
                    'OrdenServicio',
                    'EstadoRHITSO',
                    'calcular_dias_habiles',
                    'permission_required_with_message',
                ),
            ),
            (
                views_dashboard_oow_fl,
                (
                    'Empleado',
                    'Sucursal',
                    'OrdenServicio',
                    'cache_page_dashboard',
                    'determinar_categoria_venta',
                    'obtener_top_productos_vendidos',
                ),
            ),
            (
                views_dashboard_cotizaciones,
                (
                    'Empleado',
                    'Sucursal',
                    'OrdenServicio',
                    'HttpResponse',
                    'messages',
                    'cache_page_dashboard',
                ),
            ),
            (
                views_dashboard_seguimiento_piezas,
                (
                    'Sucursal',
                    'ESTADO_PIEZA_CHOICES',
                    'ESTADOS_PIEZA_PENDIENTES',
                    'ESTADOS_PIEZA_PROBLEMATICOS',
                    'messages',
                ),
            ),
            (
                vm_analytics,
                ('determinar_categoria_venta', 'obtener_top_productos_vendidos'),
            ),
        ]
        for modulo, nombres in casos:
            for nombre in nombres:
                with self.subTest(modulo=modulo.__name__, nombre=nombre):
                    self.assertTrue(
                        hasattr(modulo, nombre),
                        msg=f'Falta {nombre} en {modulo.__name__}',
                    )
