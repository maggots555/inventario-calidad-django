"""
Tests de humo tras modularizar vistas de Almacén (Fase 0 + Fase 1 + Fase 2).

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
from almacen import views_catalogo
from almacen import views_dashboard_distribucion
from almacen import views_parametros_cotizador
from almacen import views_unidades
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


class CompatibilidadReexportsFase2Test(SimpleTestCase):
    """
    Verifica reexports y resolución de URLs de la Fase 2.

    Módulos extraídos:
        - views_catalogo (dashboard, productos, bajas, APIs producto, acceso denegado)
        - views_unidades (CRUD unidades + APIs + buscar/crear orden)
    """

    def test_views_reexporta_catalogo_representativo(self):
        """Símbolos clave del catálogo siguen en views con la misma identidad."""
        pares = [
            ('dashboard_almacen', views_catalogo.dashboard_almacen),
            ('lista_productos', views_catalogo.lista_productos),
            ('lista_proveedores', views_catalogo.lista_proveedores),
            ('lista_categorias', views_catalogo.lista_categorias),
            ('lista_solicitudes', views_catalogo.lista_solicitudes),
            ('lista_movimientos', views_catalogo.lista_movimientos),
            ('api_buscar_productos', views_catalogo.api_buscar_productos),
            ('api_info_producto', views_catalogo.api_info_producto),
            ('acceso_denegado', views_catalogo.acceso_denegado),
        ]
        for attr, expected in pares:
            self.assertIs(getattr(almacen_views, attr), expected, msg=attr)

    def test_views_reexporta_unidades_representativo(self):
        """Símbolos clave de unidades siguen en views con la misma identidad."""
        pares = [
            ('lista_unidades', views_unidades.lista_unidades),
            ('crear_unidad', views_unidades.crear_unidad),
            ('detalle_unidad', views_unidades.detalle_unidad),
            ('cambiar_estado_unidad', views_unidades.cambiar_estado_unidad),
            ('unidades_por_producto', views_unidades.unidades_por_producto),
            ('api_unidad_info', views_unidades.api_unidad_info),
            ('api_unidades_producto', views_unidades.api_unidades_producto),
            ('api_tecnicos_disponibles', views_unidades.api_tecnicos_disponibles),
            (
                'api_buscar_crear_orden_cliente',
                views_unidades.api_buscar_crear_orden_cliente,
            ),
        ]
        for attr, expected in pares:
            self.assertIs(getattr(almacen_views, attr), expected, msg=attr)

    def test_modulo_correcto_fase2(self):
        """__module__ apunta a views_catalogo / views_unidades."""
        self.assertEqual(
            almacen_views.dashboard_almacen.__module__,
            'almacen.views_catalogo',
        )
        self.assertEqual(
            almacen_views.acceso_denegado.__module__,
            'almacen.views_catalogo',
        )
        self.assertEqual(
            almacen_views.lista_unidades.__module__,
            'almacen.views_unidades',
        )
        self.assertEqual(
            almacen_views.api_buscar_crear_orden_cliente.__module__,
            'almacen.views_unidades',
        )

    def test_urls_catalogo_resuelven_al_modulo_nuevo(self):
        """reverse/resolve de catálogo apuntan a views_catalogo."""
        casos = [
            ('almacen:dashboard', {}, views_catalogo.dashboard_almacen),
            ('almacen:lista_productos', {}, views_catalogo.lista_productos),
            ('almacen:lista_proveedores', {}, views_catalogo.lista_proveedores),
            ('almacen:lista_categorias', {}, views_catalogo.lista_categorias),
            ('almacen:lista_solicitudes', {}, views_catalogo.lista_solicitudes),
            ('almacen:lista_movimientos', {}, views_catalogo.lista_movimientos),
            ('almacen:api_buscar_productos', {}, views_catalogo.api_buscar_productos),
            (
                'almacen:api_info_producto',
                {'pk': 1},
                views_catalogo.api_info_producto,
            ),
            (
                'almacen:acceso_denegado_almacen',
                {},
                views_catalogo.acceso_denegado,
            ),
        ]
        for name, kwargs, expected in casos:
            match = resolve(reverse(name, kwargs=kwargs))
            self.assertIs(match.func, expected, msg=name)

    def test_urls_unidades_resuelven_al_modulo_nuevo(self):
        """reverse/resolve de unidades apuntan a views_unidades."""
        casos = [
            ('almacen:lista_unidades', {}, views_unidades.lista_unidades),
            ('almacen:crear_unidad', {}, views_unidades.crear_unidad),
            (
                'almacen:detalle_unidad',
                {'pk': 1},
                views_unidades.detalle_unidad,
            ),
            (
                'almacen:unidades_por_producto',
                {'producto_id': 1},
                views_unidades.unidades_por_producto,
            ),
            (
                'almacen:api_unidad_info',
                {'pk': 1},
                views_unidades.api_unidad_info,
            ),
            (
                'almacen:api_unidades_producto',
                {},
                views_unidades.api_unidades_producto,
            ),
            (
                'almacen:api_tecnicos_disponibles',
                {},
                views_unidades.api_tecnicos_disponibles,
            ),
            (
                'almacen:api_buscar_crear_orden',
                {},
                views_unidades.api_buscar_crear_orden_cliente,
            ),
        ]
        for name, kwargs, expected in casos:
            match = resolve(reverse(name, kwargs=kwargs))
            self.assertIs(match.func, expected, msg=name)
