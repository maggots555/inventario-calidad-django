"""
Tests de humo tras extraer el portal de seguimiento del cliente (Fase 3).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No abrimos tokens reales ni llamamos al chat IA. Solo confirmamos que:
1) config/urls.py y los names públicos siguen resolviendo a los callables nuevos.
2) views.py reexporta los mismos nombres (sin editar config/urls.py).
3) chat_seguimiento_cliente vive en views_seguimiento_cliente (ya no en el monolito).
"""

from django.test import SimpleTestCase
from django.urls import resolve, reverse

from servicio_tecnico import views as st_views
from servicio_tecnico import views_seguimiento_cliente as vsc


class CompatibilidadPortalClienteReexportsTest(SimpleTestCase):
    """
    Verifica reexports y resolve de URLs públicas sin tocar BD.

    Objetivo: si alguien borra un reexport, config/urls.py dejaría de importar
    seguimiento_orden_cliente / chat_seguimiento_cliente y caería el arranque.
    """

    def test_views_reexporta_portal_cliente(self):
        """Los símbolos públicos del portal siguen en servicio_tecnico.views."""
        casos = [
            'seguimiento_orden_cliente',
            'diagnostico_pdf_seguimiento',
            'manifest_seguimiento',
            'vapid_key_seguimiento',
            'suscribir_push_seguimiento',
            'cancelar_push_seguimiento',
            'registrar_evento_seguimiento_cliente',
            'feedback_rechazo_view',
            'feedback_satisfaccion_cliente',
            'confirmar_feedback_satisfaccion',
            'chat_seguimiento_cliente',
        ]
        for nombre in casos:
            with self.subTest(nombre=nombre):
                self.assertIs(
                    getattr(st_views, nombre),
                    getattr(vsc, nombre),
                    msg=f'views.{nombre} debe ser el mismo callable que views_seguimiento_cliente',
                )

    def test_chat_vive_en_modulo_seguimiento_no_en_monolito(self):
        """
        chat_seguimiento_cliente ya no está definido en el cuerpo de views.py.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Antes estaba 'en medio' del archivo (entre pulir y transcribir).
        Ahora solo se importa/reexporta desde views_seguimiento_cliente.py.
        """
        self.assertIs(
            st_views.chat_seguimiento_cliente,
            vsc.chat_seguimiento_cliente,
        )
        # __module__ apunta al módulo donde se definió la función (no al decorador)
        self.assertEqual(
            st_views.chat_seguimiento_cliente.__module__,
            'servicio_tecnico.views_seguimiento_cliente',
        )

    def test_urls_publicas_config_resuelven_modulo_nuevo(self):
        """
        Rutas públicas de config/urls.py apuntan al módulo nuevo.

        Usa los names definidos en config/urls.py (sin namespace de app).
        """
        casos = [
            ('seguimiento_orden_publico', {'token': 'abc'}, vsc.seguimiento_orden_cliente),
            ('diagnostico_pdf_seguimiento', {'token': 'abc'}, vsc.diagnostico_pdf_seguimiento),
            ('chat_seguimiento_publico', {'token': 'abc'}, vsc.chat_seguimiento_cliente),
            ('manifest_seguimiento', {'token': 'abc'}, vsc.manifest_seguimiento),
            ('push_vapid_key_seguimiento', {'token': 'abc'}, vsc.vapid_key_seguimiento),
            ('push_suscribir_seguimiento', {'token': 'abc'}, vsc.suscribir_push_seguimiento),
            ('push_cancelar_seguimiento', {'token': 'abc'}, vsc.cancelar_push_seguimiento),
            ('eventos_seguimiento_cliente', {'token': 'abc'}, vsc.registrar_evento_seguimiento_cliente),
            ('feedback_rechazo_publico', {'token': 'abc'}, vsc.feedback_rechazo_view),
            ('feedback_satisfaccion_publico', {'token': 'abc'}, vsc.feedback_satisfaccion_cliente),
        ]
        for name, kwargs, expected in casos:
            with self.subTest(name=name):
                url = reverse(name, kwargs=kwargs)
                match = resolve(url)
                self.assertIs(match.func, expected, msg=f'Fallo en {name} → {url}')

    def test_url_confirmar_feedback_satisfaccion_staff(self):
        """confirmar_feedback_satisfaccion (staff) sigue en urls de servicio_tecnico."""
        url = reverse(
            'servicio_tecnico:confirmar_feedback_satisfaccion',
            kwargs={'feedback_id': 1},
        )
        match = resolve(url)
        self.assertIs(match.func, vsc.confirmar_feedback_satisfaccion)

    def test_modulo_tiene_imports_criticos(self):
        """
        Regresión de NameError: logger, HistorialOrden, ImagenOrden, timezone, etc.

        EXPLICACIÓN PARA PRINCIPIANTES:
        En Fase 2 olvidamos importar Sucursal al sacar el concentrado.
        Aquí comprobamos que el módulo nuevo trae los nombres que el portal usa
        desde el import global antiguo de views.py.
        """
        for nombre in (
            'HistorialOrden',
            'ImagenOrden',
            'JsonResponse',
            'logger',
            'timezone',
            'settings',
            'json',
            'ratelimit',
            'csrf_exempt',
            'login_required',
            'messages',
            'get_object_or_404',
            'reverse',
        ):
            with self.subTest(nombre=nombre):
                self.assertTrue(
                    hasattr(vsc, nombre),
                    msg=f'Falta import/atributo {nombre} en views_seguimiento_cliente',
                )
