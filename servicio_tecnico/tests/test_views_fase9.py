"""
Tests de humo tras extraer órdenes CRUD / listas / inicio (Fase 9).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No creamos órdenes reales en CI. Solo confirmamos que:
1) urls.py resuelve cada ruta a views_ordenes.
2) views.py reexporta (compatibilidad).
3) Imports críticos existen (regresión NameError).
4) detalle_orden ya vive en views_detalle_orden (Fase 10 / B) y se reexporta.
"""

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from servicio_tecnico import views as st_views
from servicio_tecnico import views_ordenes


class CompatibilidadOrdenesFase9Test(SimpleTestCase):
    """Reexports + resolve sin tocar BD."""

    def test_views_reexporta_ordenes(self):
        """Funciones de órdenes siguen disponibles en servicio_tecnico.views."""
        pares = [
            ('seleccionar_tipo_orden', views_ordenes.seleccionar_tipo_orden),
            ('inicio', views_ordenes.inicio),
            ('crear_orden', views_ordenes.crear_orden),
            ('crear_orden_venta_mostrador', views_ordenes.crear_orden_venta_mostrador),
            ('lista_ordenes_activas', views_ordenes.lista_ordenes_activas),
            ('lista_ordenes_finalizadas', views_ordenes.lista_ordenes_finalizadas),
            ('cerrar_orden', views_ordenes.cerrar_orden),
            ('cerrar_todas_finalizadas', views_ordenes.cerrar_todas_finalizadas),
            ('cerrar_finalizados_garantia', views_ordenes.cerrar_finalizados_garantia),
        ]
        for attr, expected in pares:
            with self.subTest(attr=attr):
                self.assertIs(getattr(st_views, attr), expected)

    def test_modulo_correcto(self):
        """__module__ apunta a views_ordenes, no al monolito."""
        self.assertEqual(st_views.inicio.__module__, 'servicio_tecnico.views_ordenes')
        self.assertEqual(
            st_views.lista_ordenes_activas.__module__,
            'servicio_tecnico.views_ordenes',
        )
        self.assertEqual(st_views.crear_orden.__module__, 'servicio_tecnico.views_ordenes')

    def test_urls_ordenes_resuelven_modulo_nuevo(self):
        """reverse/resolve → views_ordenes."""
        casos = [
            ('servicio_tecnico:inicio', {}, views_ordenes.inicio),
            (
                'servicio_tecnico:seleccionar_tipo_orden',
                {},
                views_ordenes.seleccionar_tipo_orden,
            ),
            ('servicio_tecnico:crear_orden', {}, views_ordenes.crear_orden),
            (
                'servicio_tecnico:crear_orden_venta_mostrador',
                {},
                views_ordenes.crear_orden_venta_mostrador,
            ),
            (
                'servicio_tecnico:lista_activas',
                {},
                views_ordenes.lista_ordenes_activas,
            ),
            (
                'servicio_tecnico:lista_finalizadas',
                {},
                views_ordenes.lista_ordenes_finalizadas,
            ),
            (
                'servicio_tecnico:cerrar_orden',
                {'orden_id': 1},
                views_ordenes.cerrar_orden,
            ),
            ('servicio_tecnico:cerrar_todas', {}, views_ordenes.cerrar_todas_finalizadas),
            (
                'servicio_tecnico:cerrar_finalizados_garantia',
                {},
                views_ordenes.cerrar_finalizados_garantia,
            ),
        ]
        for name, kwargs, expected in casos:
            with self.subTest(name=name):
                url = reverse(name, kwargs=kwargs)
                match = resolve(url)
                self.assertIs(match.func, expected, msg=f'Fallo en {name}')

    def test_detalle_orden_vive_en_views_detalle_orden(self):
        """
        Fase 10 / B: módulo hermano + URL sigue resolviendo al reexport.

        EXPLICACIÓN PARA PRINCIPIANTES:
        resolve() debe devolver la misma función que st_views.detalle_orden
        (que a su vez es la de views_detalle_orden.py).
        """
        from servicio_tecnico import views_detalle_orden as vdo

        self.assertEqual(
            st_views.detalle_orden.__module__,
            'servicio_tecnico.views_detalle_orden',
        )
        self.assertIs(st_views.detalle_orden, vdo.detalle_orden)
        url = reverse('servicio_tecnico:detalle_orden', kwargs={'orden_id': 1})
        match = resolve(url)
        self.assertIs(match.func, st_views.detalle_orden)
        self.assertIs(match.func, vdo.detalle_orden)

    def test_imports_criticos(self):
        """Regresión NameError: forms/models/paginator en views_ordenes."""
        for nombre in (
            'NuevaOrdenForm',
            'NuevaOrdenVentaMostradorForm',
            'OrdenServicio',
            'HistorialOrden',
            'IncidenciaRHITSO',
            'Empleado',
            'ESTADO_ORDEN_CHOICES',
            'Paginator',
            'EmptyPage',
            'PageNotAnInteger',
            'Prefetch',
            'Count',
            'Q',
            'timezone',
            'messages',
            'get_object_or_404',
            'permission_required_with_message',
        ):
            with self.subTest(nombre=nombre):
                self.assertTrue(
                    hasattr(views_ordenes, nombre),
                    msg=f'Falta {nombre} en views_ordenes',
                )

    def test_imports_criticos_detalle_orden(self):
        """
        Regresión NameError: imports de nivel módulo en views_detalle_orden.

        EXPLICACIÓN: al mudarla desde views.py, los símbolos que antes venían
        del import global del monolito deben vivir en el módulo nuevo.
        """
        from servicio_tecnico import views_detalle_orden as vdo

        for nombre in (
            'OrdenServicio',
            'HistorialOrden',
            'Cotizacion',
            'EstadoRHITSO',
            'Empleado',
            'ComponenteEquipo',
            'ConfiguracionAdicionalForm',
            'GuardarManoObraForm',
            'GestionarCotizacionForm',
            'comprimir_y_guardar_imagen',
            'registrar_historial',
            'COMPONENTES_DIAGNOSTICO_ORDEN',
            'ESTADO_ORDEN_CHOICES',
            'JsonResponse',
            'mark_safe',
            'permission_required_with_message',
        ):
            with self.subTest(nombre=nombre):
                self.assertTrue(
                    hasattr(vdo, nombre),
                    msg=f'Falta {nombre} en views_detalle_orden',
                )
