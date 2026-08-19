"""
Tests del panel de cotizaciones (pestañas Front vs Cliente).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El panel mezclaba solicitudes «enviada_front» (aún en recepción) con
«enviada_cliente» (ya compartidas). Estos tests abren la vista y
revisan el HTML para comprobar:

1) Cada estado cae en su pestaña.
2) Un borrador no se lista.
3) La pestaña Front es la activa al abrir; ?tab=cliente activa Cliente.
4) En Front y en Cliente, con orden se ve el responsable de seguimiento;
   sin orden activa se ve quien creó la solicitud.
5) La alerta de días usa la vigencia de 5 días hábiles (no 3 calendario):
   vencida pinta «Venció»; por vencer (1 día hábil o menos) pinta «Por vencer».
6) ?alerta=vencida recorta la tabla pero los KPIs siguen mostrando el total.

RequestFactory (no Client HTTP) evita el middleware multi-país
(conflicto default vs mexico en tests con dos BD).
"""

import re
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

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
    Integración del panel: pestañas, responsable y vigencia de 5 días hábiles.

    Objetivo de negocio:
        Que Recepción distinga de un vistazo lo que sigue en Front
        de lo que ya se compartió al cliente, sepa a quién dar
        seguimiento y vea cuáles cotizaciones ya vencieron.
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

    def _get_panel(self, query=None):
        """
        Ejecuta GET de panel_cotizaciones y devuelve la respuesta HTML.

        Args:
            query: dict opcional de querystring (ej. ``{'tab': 'cliente'}``).

        Returns:
            HttpResponse de la vista (template real, no mockeado).
        """
        request = self.factory.get(self.url, query or {})
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return panel_cotizaciones(request)

    def _kpi_valor(self, html: str, kpi: str) -> str:
        """
        Lee el número pintado en un KPI por el atributo data-kpi.

        Args:
            html: Cuerpo HTML de la respuesta.
            kpi: Valor de data-kpi (ej. ``'vencidas'``).

        Returns:
            Texto del span.panel-cot-kpi-value de esa tarjeta.
        """
        # EXPLICACIÓN: el HTML del KPI tiene saltos de línea; [\s\S]*? cruza
        # líneas hasta el primer valor, que es el de ESA tarjeta.
        patron = (
            rf'data-kpi="{kpi}"[\s\S]*?'
            r'<span class="panel-cot-kpi-value">([^<]+)</span>'
        )
        match = re.search(patron, html)
        self.assertIsNotNone(match, f'No se encontró el KPI {kpi} en el HTML')
        return match.group(1).strip()

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
        self.assertEqual(self._kpi_valor(html, 'front'), '2')
        self.assertEqual(self._kpi_valor(html, 'cliente'), '1')
        self.assertIn(self.sol_sin_orden.numero_solicitud, html_front)
        # Sin fechas de vigencia no debe pintarse la alerta de vencida
        self.assertNotIn('Venció', html_front)
        self.assertNotIn('Venció', html_cliente)

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

        # La pestaña del cliente TAMBIÉN muestra el responsable de seguimiento
        self.assertIn('Rosa Seguimiento Panel', html_cliente)
        # Luis solo creó la de Front sin orden: no debe aparecer en Cliente
        self.assertNotIn('Luis Creador SinOrden', html_cliente)
        self.assertNotIn('Días en Front', html_cliente)
        self.assertIn('Días sin resp.', html_cliente)
        self.assertIn('Días en Front', html_front)

    def test_vigencia_vencida_pinta_alerta_y_kpi(self) -> None:
        """
        Borde: pasados los 5 días hábiles, la fila dice Venció y el KPI suma 1.

        EXPLICACIÓN: simulamos que el reloj ya se acabó empujando
        fecha_vencimiento_vigencia al pasado (igual que los tests de recotización).
        """
        self.sol_cliente.fecha_inicio_vigencia = timezone.now() - timedelta(days=10)
        self.sol_cliente.fecha_vencimiento_vigencia = timezone.now() - timedelta(days=1)
        self.sol_cliente.save(update_fields=[
            'fecha_inicio_vigencia',
            'fecha_vencimiento_vigencia',
        ])

        respuesta = self._get_panel()
        html = respuesta.content.decode()
        _html_front, html_cliente = self._html_por_pestana(html)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Venció', html_cliente)
        self.assertIn(self.sol_cliente.numero_solicitud, html_cliente)
        # KPI de vencidas (el de «por vencer» no debe contar esta)
        self.assertEqual(self._kpi_valor(html, 'vencidas'), '1')
        self.assertEqual(self._kpi_valor(html, 'por-vencer'), '0')

    def test_vigencia_por_vencer_no_cuenta_como_vencida(self) -> None:
        """
        Feliz: si vence hoy (aún no pasa la hora), es «Por vencer», no «Venció».
        """
        self.sol_front.fecha_inicio_vigencia = timezone.now() - timedelta(days=4)
        # Vence en unas horas: restantes = 0 días hábiles, pero aún no venció
        self.sol_front.fecha_vencimiento_vigencia = timezone.now() + timedelta(hours=6)
        self.sol_front.save(update_fields=[
            'fecha_inicio_vigencia',
            'fecha_vencimiento_vigencia',
        ])

        respuesta = self._get_panel()
        html = respuesta.content.decode()
        html_front, _html_cliente = self._html_por_pestana(html)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('Por vencer', html_front)
        self.assertNotIn('Venció', html_front)
        self.assertEqual(self._kpi_valor(html, 'por-vencer'), '1')
        self.assertEqual(self._kpi_valor(html, 'vencidas'), '0')

    def test_tab_cliente_en_url_activa_esa_pestana(self) -> None:
        """
        Caso feliz: ?tab=cliente pinta esa pestaña activa sin JavaScript.

        EXPLICACIÓN: las pestañas son enlaces con querystring, no botones
        Bootstrap. Así se puede recargar o compartir «ya compartidas».
        """
        respuesta = self._get_panel({'tab': 'cliente'})
        html = respuesta.content.decode()
        html_front, html_cliente = self._html_por_pestana(html)

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(
            'class="tab-pane fade show active" id="tab-compartidas-cliente"',
            html,
        )
        self.assertIn(
            'class="tab-pane fade" id="tab-enviadas-front"',
            html,
        )
        self.assertRegex(
            html,
            r'id="tab-compartidas-cliente-btn"[^>]*aria-selected="true"',
        )
        # Las filas siguen en su pestaña; solo cambia cuál se muestra.
        self.assertIn(self.sol_cliente.numero_solicitud, html_cliente)
        self.assertIn(self.sol_front.numero_solicitud, html_front)

    def test_alerta_vencida_filtra_tabla_y_kpi_sigue_total(self) -> None:
        """
        Borde: ?alerta=vencida oculta las que no vencieron; el KPI no baja.

        EXPLICACIÓN: el número grande del KPI es el total global. Si
        filtráramos también el KPI, parecería que «desaparecieron» al
        hacer clic. La tabla sí se recorta para trabajar solo esas.
        """
        self.sol_cliente.fecha_inicio_vigencia = timezone.now() - timedelta(days=10)
        self.sol_cliente.fecha_vencimiento_vigencia = timezone.now() - timedelta(days=1)
        self.sol_cliente.save(update_fields=[
            'fecha_inicio_vigencia',
            'fecha_vencimiento_vigencia',
        ])

        respuesta = self._get_panel({'alerta': 'vencida'})
        html = respuesta.content.decode()
        html_front, html_cliente = self._html_por_pestana(html)

        self.assertEqual(respuesta.status_code, 200)
        # KPI global: 1 vencida, aunque la tabla de Front quede vacía.
        self.assertEqual(self._kpi_valor(html, 'vencidas'), '1')
        # Totales de pestaña no bajan aunque la tabla de Front quede vacía
        self.assertEqual(self._kpi_valor(html, 'front'), '2')
        self.assertEqual(self._kpi_valor(html, 'cliente'), '1')
        self.assertIn(self.sol_cliente.numero_solicitud, html_cliente)
        self.assertNotIn(self.sol_front.numero_solicitud, html_front)
        self.assertNotIn(self.sol_sin_orden.numero_solicitud, html_front)
        self.assertIn('No hay cotizaciones vencidas en esta pestaña.', html_front)
        self.assertIn('data-kpi="vencidas"', html)
        self.assertIn('is-active', html)
        # El chip de filtro y el href del KPI conservan alerta=vencida.
        self.assertIn('alerta=vencida', html)
