"""
Tests del panel de cotizaciones (pestañas Front vs Cliente).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El panel mezclaba solicitudes «enviada_front» (aún en recepción) con
«enviada_cliente» (ya compartidas). Estos tests abren la vista y
revisan el HTML para comprobar:

1) Cada estado cae en su pestaña.
2) Un borrador no se lista.
3) La pestaña Front es la activa al abrir.
4) En Front, con orden se ve el responsable de seguimiento; sin orden
   activa se ve quien creó la solicitud.

RequestFactory (no Client HTTP) evita el middleware multi-país
(conflicto default vs mexico en tests con dos BD).
"""

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase, override_settings
from django.urls import reverse

from inventario.models import Empleado
from almacen.tests.helpers_integracion_cotizacion import BaseIntegracionCotizacionMixin
from almacen.views import panel_cotizaciones

User = get_user_model()


@override_settings(
    # En tests no hay collectstatic: ManifestStaticFilesStorage rompe {% static %}
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class PanelCotizacionesPestanasTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Integración del panel: pestañas por estatus y columna de responsable.

    Objetivo de negocio:
        Que Recepción distinga de un vistazo lo que sigue en Front
        de lo que ya se compartió al cliente, y sepa a quién dar
        seguimiento (o, si no hay orden, quién armó la solicitud).
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='PANEL-COT')
        self.url = reverse('almacen:panel_cotizaciones')

        # Responsable de seguimiento distinto del creador del mixin
        self.user_responsable = User.objects.create_user(
            username='rosa_seguimiento_panel',
            password='testpass123',
        )
        self.responsable = Empleado.objects.create(
            user=self.user_responsable,
            nombre_completo='Rosa Seguimiento Panel',
            cargo='Front Desk',
            area='FRONTDESK',
            email='rosa.panel@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )

        # Creador de la cotización sin orden (nombre único para buscarlo en HTML)
        self.user_creador = User.objects.create_user(
            username='luis_creador_sinorden',
            password='testpass123',
            first_name='Luis',
            last_name='CreadorSinOrden',
        )
        self.creador_sin_orden = Empleado.objects.create(
            user=self.user_creador,
            nombre_completo='Luis Creador SinOrden',
            cargo='Compras',
            area='ALMACEN',
            email='luis.panel@test.local',
            sucursal=self.sucursal,
            rol='almacenista',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )

        self.orden_front = self._crear_orden_con_detalle(orden_cliente='OOW-PANEL-FRONT')
        self.orden_front.responsable_seguimiento = self.responsable
        self.orden_front.save(update_fields=['responsable_seguimiento'])

        self.orden_cliente = self._crear_orden_con_detalle(orden_cliente='OOW-PANEL-CLIENTE')
        self.orden_cliente.responsable_seguimiento = self.responsable
        self.orden_cliente.save(update_fields=['responsable_seguimiento'])

        self.sol_front, _linea_front = self._crear_solicitud_con_linea(
            orden=self.orden_front,
            sin_orden_activa=False,
            estado='enviada_front',
        )
        self.sol_sin_orden, _linea_sin = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_front',
        )
        # EXPLICACIÓN: el helper pone creado_por=self.user; aquí queremos
        # un nombre distinto para afirmarlo en la columna Responsable.
        self.sol_sin_orden.creado_por = self.user_creador
        self.sol_sin_orden.save(update_fields=['creado_por'])

        self.sol_cliente, _linea_cli = self._crear_solicitud_con_linea(
            orden=self.orden_cliente,
            sin_orden_activa=False,
            estado='enviada_cliente',
        )
        self.sol_borrador, _linea_bor = self._crear_solicitud_con_linea(
            orden=self.orden_front,
            sin_orden_activa=False,
            estado='borrador',
        )

    def _get_panel(self):
        """
        Ejecuta GET de panel_cotizaciones y devuelve la respuesta HTML.

        Returns:
            HttpResponse de la vista (template real, no mockeado).
        """
        request = self.factory.get(self.url)
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return panel_cotizaciones(request)

    def _html_por_pestana(self, html: str) -> tuple[str, str]:
        """
        Recorta el HTML de cada pestaña para no confundir filas mezcladas.

        Args:
            html: Cuerpo completo de la respuesta.

        Returns:
            tuple: (html_front, html_cliente)
        """
        # Usamos role=tabpanel para no confundir con los botones *-btn
        inicio_front = html.find('id="tab-enviadas-front" role="tabpanel"')
        inicio_cliente = html.find('id="tab-compartidas-cliente" role="tabpanel"')
        return html[inicio_front:inicio_cliente], html[inicio_cliente:]

    def test_separa_estados_y_front_es_activa(self) -> None:
        """
        Caso feliz: Front y Cliente en su pestaña; Front sale activa; borrador no.

        EXPLICACIÓN: simula abrir el panel y ver dos listas, no un revoltijo.
        """
        respuesta = self._get_panel()
        html = respuesta.content.decode()
        html_front, html_cliente = self._html_por_pestana(html)

        self.assertEqual(respuesta.status_code, 200)
        # Pestaña Front activa al abrir (el pane lleva show active ANTES del id)
        self.assertIn(
            'class="tab-pane fade show active" id="tab-enviadas-front"',
            html,
        )
        self.assertIn(
            'class="tab-pane fade" id="tab-compartidas-cliente"',
            html,
        )
        self.assertRegex(
            html,
            r'id="tab-enviadas-front-btn"[^>]*aria-selected="true"',
        )

        self.assertIn(self.sol_front.numero_solicitud, html_front)
        self.assertNotIn(self.sol_cliente.numero_solicitud, html_front)
        self.assertNotIn(self.sol_borrador.numero_solicitud, html_front)

        self.assertIn(self.sol_cliente.numero_solicitud, html_cliente)
        self.assertNotIn(self.sol_front.numero_solicitud, html_cliente)
        self.assertNotIn(self.sol_borrador.numero_solicitud, html_cliente)

        # Dos en Front (con orden + sin orden) y una ya compartida al cliente
        self.assertIn('2 en Front', html)
        self.assertIn('1 con el cliente', html)
        self.assertIn(self.sol_sin_orden.numero_solicitud, html_front)

    def test_responsable_con_orden_y_creador_sin_orden(self) -> None:
        """
        Borde: con orden se ve el seguimiento; sin orden, quien creó.

        EXPLICACIÓN: Recepción necesita saber a quién preguntar. Si la
        cotización nació sin orden, no hay responsable de ST → se muestra
        el nombre de Compras (creado_por).
        """
        respuesta = self._get_panel()
        html_front, html_cliente = self._html_por_pestana(respuesta.content.decode())

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(self.sol_front.numero_solicitud, html_front)
        self.assertIn(self.sol_sin_orden.numero_solicitud, html_front)
        self.assertIn('Rosa Seguimiento Panel', html_front)
        self.assertIn('Luis Creador SinOrden', html_front)

        # La pestaña del cliente no trae la columna Responsable
        self.assertNotIn('Rosa Seguimiento Panel', html_cliente)
        self.assertNotIn('Luis Creador SinOrden', html_cliente)
        self.assertNotIn('Días en Front', html_cliente)
        self.assertIn('Días sin resp.', html_cliente)
        self.assertIn('Días en Front', html_front)
