"""
Tests de humo tras extraer AJAX piezas / seguimiento / venta mostrador (Fase 6).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No creamos piezas reales ni enviamos correos. Solo confirmamos que:
1) urls.py resuelve cada ruta al módulo nuevo (no a un stub vacío).
2) views.py reexporta las mismas funciones (compatibilidad urls/imports).
3) La notificación de pieza recibida vive en services/ (Almacén ya no importa views).
4) Helpers internos (_render_*) y defs no quedaron en el monolito.
"""

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from servicio_tecnico import views as st_views
from servicio_tecnico import views_piezas_cotizadas
from servicio_tecnico import views_seguimiento_piezas_ajax
from servicio_tecnico import views_venta_mostrador_ajax
from servicio_tecnico.services import notificaciones_piezas as notif_svc


class CompatibilidadPiezasReexportsTest(SimpleTestCase):
    """Reexports + resolve sin tocar BD."""

    def test_views_reexporta_piezas_cotizadas(self):
        """Piezas cotizadas siguen disponibles en servicio_tecnico.views."""
        self.assertIs(
            st_views.agregar_pieza_cotizada,
            views_piezas_cotizadas.agregar_pieza_cotizada,
        )
        self.assertIs(
            st_views.obtener_pieza_cotizada,
            views_piezas_cotizadas.obtener_pieza_cotizada,
        )
        self.assertIs(
            st_views.editar_pieza_cotizada,
            views_piezas_cotizadas.editar_pieza_cotizada,
        )
        self.assertIs(
            st_views.eliminar_pieza_cotizada,
            views_piezas_cotizadas.eliminar_pieza_cotizada,
        )

    def test_views_reexporta_seguimiento_piezas(self):
        """Seguimiento AJAX sigue disponible vía views."""
        self.assertIs(
            st_views.marcar_pieza_recibida,
            views_seguimiento_piezas_ajax.marcar_pieza_recibida,
        )
        self.assertIs(
            st_views.reenviar_notificacion_pieza,
            views_seguimiento_piezas_ajax.reenviar_notificacion_pieza,
        )
        self.assertIs(
            st_views.cambiar_estado_seguimiento,
            views_seguimiento_piezas_ajax.cambiar_estado_seguimiento,
        )
        self.assertIs(
            st_views.marcar_pieza_incorrecta,
            views_seguimiento_piezas_ajax.marcar_pieza_incorrecta,
        )
        self.assertIs(
            st_views.marcar_pieza_danada,
            views_seguimiento_piezas_ajax.marcar_pieza_danada,
        )

    def test_views_reexporta_venta_mostrador(self):
        """Venta mostrador AJAX sigue disponible vía views."""
        self.assertIs(
            st_views.crear_venta_mostrador,
            views_venta_mostrador_ajax.crear_venta_mostrador,
        )
        self.assertIs(
            st_views.agregar_pieza_venta_mostrador,
            views_venta_mostrador_ajax.agregar_pieza_venta_mostrador,
        )
        self.assertIs(
            st_views.editar_pieza_venta_mostrador,
            views_venta_mostrador_ajax.editar_pieza_venta_mostrador,
        )
        self.assertIs(
            st_views.eliminar_pieza_venta_mostrador,
            views_venta_mostrador_ajax.eliminar_pieza_venta_mostrador,
        )

    def test_notificacion_reexport_y_modulo(self):
        """
        Alias _enviar_... en views apunta al service (compat Almacén antiguo).

        EXPLICACIÓN PARA PRINCIPIANTES:
        Almacén ahora importa desde services/. El alias en views.py evita romper
        código legacy que aún haga ``from servicio_tecnico.views import _enviar_...``.
        """
        self.assertIs(
            st_views._enviar_notificacion_pieza_recibida,
            notif_svc.enviar_notificacion_pieza_recibida,
        )
        self.assertEqual(
            notif_svc.enviar_notificacion_pieza_recibida.__module__,
            'servicio_tecnico.services.notificaciones_piezas',
        )

    def test_urls_piezas_resuelven_modulo_nuevo(self):
        """reverse/resolve de piezas cotizadas → views_piezas_cotizadas."""
        casos = [
            (
                'servicio_tecnico:agregar_pieza',
                {'orden_id': 1},
                views_piezas_cotizadas.agregar_pieza_cotizada,
            ),
            (
                'servicio_tecnico:obtener_pieza',
                {'pieza_id': 1},
                views_piezas_cotizadas.obtener_pieza_cotizada,
            ),
            (
                'servicio_tecnico:editar_pieza',
                {'pieza_id': 1},
                views_piezas_cotizadas.editar_pieza_cotizada,
            ),
            (
                'servicio_tecnico:eliminar_pieza',
                {'pieza_id': 1},
                views_piezas_cotizadas.eliminar_pieza_cotizada,
            ),
        ]
        for name, kwargs, expected in casos:
            with self.subTest(name=name):
                url = reverse(name, kwargs=kwargs)
                match = resolve(url)
                self.assertIs(match.func, expected, msg=f'Fallo en {name}')

    def test_urls_seguimiento_resuelven_modulo_nuevo(self):
        """reverse/resolve de seguimiento → views_seguimiento_piezas_ajax."""
        casos = [
            (
                'servicio_tecnico:obtener_seguimiento',
                {'seguimiento_id': 1},
                views_seguimiento_piezas_ajax.obtener_seguimiento_pieza,
            ),
            (
                'servicio_tecnico:agregar_seguimiento',
                {'orden_id': 1},
                views_seguimiento_piezas_ajax.agregar_seguimiento_pieza,
            ),
            (
                'servicio_tecnico:editar_seguimiento',
                {'seguimiento_id': 1},
                views_seguimiento_piezas_ajax.editar_seguimiento_pieza,
            ),
            (
                'servicio_tecnico:eliminar_seguimiento',
                {'seguimiento_id': 1},
                views_seguimiento_piezas_ajax.eliminar_seguimiento_pieza,
            ),
            (
                'servicio_tecnico:marcar_recibido',
                {'seguimiento_id': 1},
                views_seguimiento_piezas_ajax.marcar_pieza_recibida,
            ),
            (
                'servicio_tecnico:reenviar_notificacion',
                {'seguimiento_id': 1},
                views_seguimiento_piezas_ajax.reenviar_notificacion_pieza,
            ),
            (
                'servicio_tecnico:cambiar_estado_seguimiento',
                {'seguimiento_id': 1},
                views_seguimiento_piezas_ajax.cambiar_estado_seguimiento,
            ),
            (
                'servicio_tecnico:marcar_incorrecta',
                {'seguimiento_id': 1},
                views_seguimiento_piezas_ajax.marcar_pieza_incorrecta,
            ),
            (
                'servicio_tecnico:marcar_danada',
                {'seguimiento_id': 1},
                views_seguimiento_piezas_ajax.marcar_pieza_danada,
            ),
        ]
        for name, kwargs, expected in casos:
            with self.subTest(name=name):
                url = reverse(name, kwargs=kwargs)
                match = resolve(url)
                self.assertIs(match.func, expected, msg=f'Fallo en {name}')

    def test_urls_venta_mostrador_resuelven_modulo_nuevo(self):
        """reverse/resolve de VM → views_venta_mostrador_ajax."""
        casos = [
            (
                'servicio_tecnico:venta_mostrador_crear',
                {'orden_id': 1},
                views_venta_mostrador_ajax.crear_venta_mostrador,
            ),
            (
                'servicio_tecnico:venta_mostrador_agregar_pieza',
                {'orden_id': 1},
                views_venta_mostrador_ajax.agregar_pieza_venta_mostrador,
            ),
            (
                'servicio_tecnico:venta_mostrador_editar_pieza',
                {'pieza_id': 1},
                views_venta_mostrador_ajax.editar_pieza_venta_mostrador,
            ),
            (
                'servicio_tecnico:venta_mostrador_eliminar_pieza',
                {'pieza_id': 1},
                views_venta_mostrador_ajax.eliminar_pieza_venta_mostrador,
            ),
        ]
        for name, kwargs, expected in casos:
            with self.subTest(name=name):
                url = reverse(name, kwargs=kwargs)
                match = resolve(url)
                self.assertIs(match.func, expected, msg=f'Fallo en {name}')

    def test_helpers_render_en_modulos_nuevos(self):
        """_render_pieza_row / _render_seguimiento_card no viven en el monolito."""
        self.assertTrue(hasattr(views_piezas_cotizadas, '_render_pieza_row'))
        self.assertTrue(
            hasattr(views_seguimiento_piezas_ajax, '_render_seguimiento_card')
        )
        self.assertFalse(hasattr(st_views, '_render_pieza_row'))
        self.assertFalse(hasattr(st_views, '_render_seguimiento_card'))

    def test_almacen_importa_desde_services(self):
        """
        Almacén no debe importar la notificación desde views.py.

        Leemos el fuente de sincronizar_seguimiento_piezas para evitar
        cargar toda la cadena de imports de Almacén en un SimpleTestCase.
        """
        from pathlib import Path

        fuente = Path(
            'almacen/utils/sincronizar_seguimiento_piezas.py'
        ).read_text(encoding='utf-8')
        self.assertIn(
            'servicio_tecnico.services.notificaciones_piezas',
            fuente,
        )
        self.assertNotIn(
            'from servicio_tecnico.views import',
            fuente,
        )

    def test_modulos_tienen_imports_criticos(self):
        """Regresión NameError: decorators/models/JsonResponse en cada módulo."""
        for modulo, nombres in (
            (
                views_piezas_cotizadas,
                ('JsonResponse', 'OrdenServicio', 'get_object_or_404', 'registrar_historial'),
            ),
            (
                views_seguimiento_piezas_ajax,
                (
                    'JsonResponse',
                    'OrdenServicio',
                    'get_object_or_404',
                    'registrar_historial',
                    '_enviar_notificacion_pieza_recibida',
                ),
            ),
            (
                views_venta_mostrador_ajax,
                ('JsonResponse', 'OrdenServicio', 'get_object_or_404', 'registrar_historial'),
            ),
            (
                notif_svc,
                ('enviar_notificacion_pieza_recibida', '_enviar_notificacion_pieza_recibida', 'config'),
            ),
        ):
            for nombre in nombres:
                with self.subTest(modulo=modulo.__name__, nombre=nombre):
                    self.assertTrue(
                        hasattr(modulo, nombre),
                        msg=f'Falta {nombre} en {modulo.__name__}',
                    )
