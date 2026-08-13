"""
Tests: folio/orden_cliente visible en la lista de unidades.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando una pieza está ASIGNADA, el almacén ya sabe a qué orden va
(`UnidadInventario.orden_servicio_destino`). El número que el usuario
reconoce es `DetalleEquipo.orden_cliente` (ej. OOW-11902).

Estos tests comprueban que la lista `/almacen/unidades/` muestra ese
folio (con enlace a la orden) y que el recuadro de búsqueda lo encuentra.
No enviamos HTTP real con Client: RequestFactory evita el middleware
multi-país (conflicto default vs mexico en tests).
"""

from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase, override_settings
from django.urls import reverse

from almacen.models import UnidadInventario
from almacen.tests.helpers_integracion_cotizacion import BaseIntegracionCotizacionMixin
from almacen.views import lista_unidades


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
class ListaUnidadesFolioTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Integración de la lista de unidades con el folio de la orden asignada.

    Objetivo de negocio:
        Ver OOW-… en la fila ASIGNADA y poder filtrar por ese folio,
        sin entrar al detalle de la unidad.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='LISTA-FOLIO')
        self.orden = self._crear_orden_con_detalle(orden_cliente='OOW-LISTA-01')
        # Pieza ya salida de almacén hacia esa orden
        self.unidad_asignada = UnidadInventario.objects.create(
            producto=self.producto,
            marca='Samsung',
            modelo='EvoLista',
            disponibilidad='asignada',
            orden_servicio_destino=self.orden,
            sucursal_actual=self.sucursal,
            registrado_por=self.user,
        )
        # Pieza en anaquel: no debe inventar un folio
        self.unidad_disponible = UnidadInventario.objects.create(
            producto=self.producto,
            marca='Kingston',
            modelo='LibreLista',
            disponibilidad='disponible',
            sucursal_actual=self.sucursal,
            registrado_por=self.user,
        )
        self.url_lista = reverse('almacen:lista_unidades')
        self.url_orden = reverse(
            'servicio_tecnico:detalle_orden',
            args=[self.orden.pk],
        )

    def _get_lista(self, query: str = ''):
        """
        Ejecuta GET de lista_unidades y devuelve la respuesta HTML.

        Args:
            query: Querystring sin el `?` (ej. `buscar=OOW-LISTA-01`).

        Returns:
            HttpResponse de la vista (template real, no mockeado).
        """
        url = f'{self.url_lista}?{query}' if query else self.url_lista
        request = self.factory.get(url)
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return lista_unidades(request)

    def test_lista_muestra_folio_y_enlace_de_unidad_asignada(self) -> None:
        """
        Caso feliz: la fila ASIGNADA muestra OOW-LISTA-01 y link a la orden.

        EXPLICACIÓN: simula abrir Unidades de Inventario y ver, bajo el
        badge, a qué folio del cliente está ligada la pieza.
        """
        respuesta = self._get_lista()
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn('OOW-LISTA-01', html)
        self.assertIn(self.url_orden, html)
        self.assertIn(self.unidad_asignada.codigo_interno, html)

    def test_unidad_disponible_no_inventa_folio(self) -> None:
        """
        Borde: una unidad disponible no fabrica enlace ni folio de orden.

        EXPLICACIÓN: solo la asignada tiene `orden_servicio_destino`.
        En la misma página debe haber un único link a esa orden.
        """
        respuesta = self._get_lista()
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(self.unidad_disponible.codigo_interno, html)
        self.assertEqual(html.count(self.url_orden), 1)

    def test_buscar_por_orden_cliente_encuentra_unidad_asignada(self) -> None:
        """
        Caso feliz: filtrar por OOW-LISTA-01 deja solo la pieza asignada.

        EXPLICACIÓN: el recuadro Buscar ahora también mira
        `detalle_equipo.orden_cliente` de la orden destino.
        """
        respuesta = self._get_lista(query='buscar=OOW-LISTA-01')
        html = respuesta.content.decode()

        self.assertEqual(respuesta.status_code, 200)
        self.assertIn(self.unidad_asignada.codigo_interno, html)
        self.assertIn('OOW-LISTA-01', html)
        self.assertNotIn(self.unidad_disponible.codigo_interno, html)
