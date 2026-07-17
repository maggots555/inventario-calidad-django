"""
Tests de humo tras extraer dashboards de encuestas / feedback / enlaces (Fase 4).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No generamos Excel/PDF ni llamamos IA de sentimiento. Solo confirmamos que:
1) urls.py resuelve a los callables nuevos.
2) views.py reexporta los nombres.
3) _anotar_push_enlaces ya no se importa desde views (vive en eventos_seguimiento).
4) calcular_embudo_enlaces funciona sin ciclo de importación.
"""

from django.test import SimpleTestCase, TestCase
from django.urls import resolve, reverse

from servicio_tecnico import eventos_seguimiento
from servicio_tecnico import views as st_views
from servicio_tecnico import views_encuestas
from servicio_tecnico import views_feedback_rechazo_dash
from servicio_tecnico import views_seguimiento_enlaces


class CompatibilidadFase4ReexportsTest(SimpleTestCase):
    """Reexports + resolve de URLs sin tocar BD."""

    def test_views_reexporta_dashboards_fase4(self):
        """Los símbolos públicos de Fase 4 siguen en servicio_tecnico.views."""
        casos = [
            (st_views.dashboard_encuestas, views_encuestas.dashboard_encuestas),
            (st_views.api_encuestas_kpis, views_encuestas.api_encuestas_kpis),
            (st_views.api_analisis_sentimiento_ia, views_encuestas.api_analisis_sentimiento_ia),
            (st_views.exportar_encuestas_excel, views_encuestas.exportar_encuestas_excel),
            (
                st_views.dashboard_feedback_rechazo,
                views_feedback_rechazo_dash.dashboard_feedback_rechazo,
            ),
            (
                st_views.api_feedback_rechazo_kpis,
                views_feedback_rechazo_dash.api_feedback_rechazo_kpis,
            ),
            (
                st_views.dashboard_seguimiento_enlaces,
                views_seguimiento_enlaces.dashboard_seguimiento_enlaces,
            ),
            (
                st_views.api_seguimiento_enlaces_embudo,
                views_seguimiento_enlaces.api_seguimiento_enlaces_embudo,
            ),
            (
                st_views.api_seguimiento_enlaces_tabla,
                views_seguimiento_enlaces.api_seguimiento_enlaces_tabla,
            ),
        ]
        for desde_views, esperado in casos:
            with self.subTest(nombre=esperado.__name__):
                self.assertIs(desde_views, esperado)

    def test_urls_fase4_resuelven_modulos_nuevos(self):
        """reverse/resolve apuntan a los módulos de Fase 4."""
        casos = [
            ('servicio_tecnico:dashboard_encuestas', None, views_encuestas.dashboard_encuestas),
            ('servicio_tecnico:api_encuestas_kpis', None, views_encuestas.api_encuestas_kpis),
            (
                'servicio_tecnico:api_analisis_sentimiento_ia',
                None,
                views_encuestas.api_analisis_sentimiento_ia,
            ),
            (
                'servicio_tecnico:exportar_encuestas_excel',
                None,
                views_encuestas.exportar_encuestas_excel,
            ),
            (
                'servicio_tecnico:exportar_encuestas_pdf',
                None,
                views_encuestas.exportar_encuestas_pdf,
            ),
            (
                'servicio_tecnico:dashboard_feedback_rechazo',
                None,
                views_feedback_rechazo_dash.dashboard_feedback_rechazo,
            ),
            (
                'servicio_tecnico:api_feedback_rechazo_kpis',
                None,
                views_feedback_rechazo_dash.api_feedback_rechazo_kpis,
            ),
            (
                'servicio_tecnico:exportar_feedback_rechazo_excel',
                None,
                views_feedback_rechazo_dash.exportar_feedback_rechazo_excel,
            ),
            (
                'servicio_tecnico:dashboard_seguimiento_enlaces',
                None,
                views_seguimiento_enlaces.dashboard_seguimiento_enlaces,
            ),
            (
                'servicio_tecnico:api_seguimiento_enlaces_kpis',
                None,
                views_seguimiento_enlaces.api_seguimiento_enlaces_kpis,
            ),
            (
                'servicio_tecnico:api_seguimiento_enlaces_embudo',
                None,
                views_seguimiento_enlaces.api_seguimiento_enlaces_embudo,
            ),
            (
                'servicio_tecnico:api_seguimiento_enlaces_tabla',
                None,
                views_seguimiento_enlaces.api_seguimiento_enlaces_tabla,
            ),
        ]
        for name, kwargs, expected in casos:
            with self.subTest(name=name):
                url = reverse(name, kwargs=kwargs) if kwargs else reverse(name)
                match = resolve(url)
                self.assertIs(match.func, expected, msg=f'Fallo en {name}')

    def test_modulos_tienen_imports_criticos(self):
        """
        Regresión NameError: timezone/Q/Paginator/Sucursal etc. en dashboards.

        EXPLICACIÓN PARA PRINCIPIANTES:
        En el monolito estos nombres venían del import global de views.py.
        Al mover, hay que traerlos al módulo nuevo.
        """
        self.assertTrue(hasattr(views_encuestas, 'timezone'))
        self.assertTrue(hasattr(views_encuestas, 'Q'))
        self.assertTrue(hasattr(views_encuestas, 'Paginator'))
        self.assertTrue(hasattr(views_encuestas, 'Sucursal'))
        self.assertTrue(hasattr(views_encuestas, 'Font'))
        self.assertTrue(hasattr(views_feedback_rechazo_dash, 'timezone'))
        self.assertTrue(hasattr(views_feedback_rechazo_dash, 'Count'))
        self.assertTrue(hasattr(views_feedback_rechazo_dash, 'get_column_letter'))
        self.assertTrue(hasattr(views_seguimiento_enlaces, 'Empleado'))
        self.assertTrue(hasattr(views_seguimiento_enlaces, 'Sucursal'))


class HelpersEnlacesEnEventosSeguimientoTest(SimpleTestCase):
    """
    El helper de push ya no vive en views.py (rompe el ciclo con eventos).

    EXPLICACIÓN PARA PRINCIPIANTES:
    Antes calcular_embudo_enlaces hacía:
        from servicio_tecnico.views import _anotar_push_enlaces
    Eso acoplaba eventos ↔ views. Ahora el helper está en el mismo módulo.
    """

    def test_anotar_push_vive_en_eventos_seguimiento(self):
        self.assertTrue(callable(eventos_seguimiento.anotar_push_enlaces))
        self.assertTrue(callable(eventos_seguimiento._anotar_push_enlaces))
        self.assertIs(
            eventos_seguimiento.anotar_push_enlaces,
            eventos_seguimiento._anotar_push_enlaces,
        )

    def test_filtrar_enlaces_vive_en_eventos_seguimiento(self):
        self.assertTrue(callable(eventos_seguimiento.filtrar_enlaces_seguimiento))
        self.assertIs(
            eventos_seguimiento.filtrar_enlaces_seguimiento,
            eventos_seguimiento._filtrar_enlaces_seguimiento,
        )

    def test_views_reexporta_helpers_para_compatibilidad(self):
        """Imports antiguos `from views import _anotar_push_enlaces` siguen vivos."""
        self.assertIs(
            st_views._anotar_push_enlaces,
            eventos_seguimiento.anotar_push_enlaces,
        )
        self.assertIs(
            st_views._filtrar_enlaces_seguimiento,
            eventos_seguimiento.filtrar_enlaces_seguimiento,
        )

    def test_calcular_embudo_no_importa_desde_views(self):
        """
        El código fuente de calcular_embudo no debe volver a importar views.

        Así evitamos el ciclo de importación que había antes.
        """
        import inspect

        src = inspect.getsource(eventos_seguimiento.calcular_embudo_enlaces)
        self.assertNotIn(
            'servicio_tecnico.views',
            src,
            msg='calcular_embudo_enlaces no debe importar desde views.py',
        )
        self.assertIn('anotar_push_enlaces', src)


class EmbudoEnlacesSmokeTest(TestCase):
    """
    Smoke: calcular_embudo_enlaces con queryset vacío no revienta.

    Efectos secundarios: consulta BD de pruebas (tabla enlaces vacía).
    """

    def test_embudo_queryset_vacio(self):
        from servicio_tecnico.models import EnlaceSeguimientoCliente

        qs = EnlaceSeguimientoCliente.objects.none()
        datos = eventos_seguimiento.calcular_embudo_enlaces(qs)

        self.assertEqual(datos['total_enlaces'], 0)
        self.assertIn('pasos', datos)
        self.assertIsInstance(datos['pasos'], list)
        self.assertGreater(len(datos['pasos']), 0)
