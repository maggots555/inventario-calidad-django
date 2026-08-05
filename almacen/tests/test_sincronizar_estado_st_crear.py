"""
Tests: sync de estado ST al crear SolicitudCotizacion con orden vinculada.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Al crear una solicitud YA ligada a una OrdenServicio, la orden debe pasar a
«Envío de Cotización al Proveedor» (cotizacion_enviada_proveedor).

Casos:
1) Feliz: orden en diagnóstico → cambia al hito.
2) Borde: orden ya en esperando_piezas → NO retrocede.
3) Vista HTTP: POST crear_solicitud_cotizacion con orden → mismo efecto.
4) Sin orden: el util no hace nada (no hay ST que actualizar).

No cubrimos vincular/crear FL: ese hilo se personaliza aparte.
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from almacen.models import SolicitudCotizacion
from almacen.tests.helpers_integracion_cotizacion import (
    BaseIntegracionCotizacionMixin,
    request_post,
)
from almacen.utils.sincronizar_estado_st import (
    ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR,
    sincronizar_estado_st_al_crear_solicitud,
)
from almacen.views import crear_solicitud_cotizacion


class SincronizarEstadoStAlCrearSolicitudUtilTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Regla unitaria del util: feliz + anti-regresión + sin orden.

    Objetivo de negocio:
        Solo avanzar a cotizacion_enviada_proveedor desde fases previas.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='SYNC-CREAR')

    def test_feliz_diagnostico_pasa_a_enviada_proveedor(self) -> None:
        """
        Caso feliz: orden en diagnóstico + solicitud con orden → cambia estado.

        EXPLICACIÓN: simula el momento en que Almacén pide cotización a
        proveedores y ST debe reflejar ese hito.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-SYNC-CREAR-01',
            estado='diagnostico',
        )
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='borrador',
        )

        cambiado = sincronizar_estado_st_al_crear_solicitud(
            solicitud,
            usuario=self.user,
        )

        self.assertTrue(cambiado)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR)

        # Historial enriquecido con contexto de Almacén
        ultimo = (
            orden.historial.filter(
                tipo_evento='cambio_estado',
                estado_nuevo=ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR,
            )
            .order_by('-fecha_evento')
            .first()
        )
        self.assertIsNotNone(ultimo)
        self.assertIn(solicitud.numero_solicitud, ultimo.comentario or '')
        self.assertTrue(ultimo.es_sistema)

    def test_borde_esperando_piezas_no_retrocede(self) -> None:
        """
        Caso borde: orden ya avanzada → el util NO pisa el estado.

        EXPLICACIÓN: si por algún motivo se llama el sync con una orden en
        esperando_piezas, no debe volver a cotizacion_enviada_proveedor.
        """
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-SYNC-CREAR-02',
            estado='esperando_piezas',
        )
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='borrador',
        )

        cambiado = sincronizar_estado_st_al_crear_solicitud(
            solicitud,
            usuario=self.user,
        )

        self.assertFalse(cambiado)
        orden.refresh_from_db()
        self.assertEqual(orden.estado, 'esperando_piezas')

    def test_sin_orden_no_cambia_nada(self) -> None:
        """
        Sin orden vinculada: el util retorna False y no toca ST.
        """
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='borrador',
        )

        cambiado = sincronizar_estado_st_al_crear_solicitud(
            solicitud,
            usuario=self.user,
        )
        self.assertFalse(cambiado)


class SincronizarEstadoStAlCrearSolicitudVistaTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Integración HTTP: POST crear_solicitud_cotizacion con orden vinculada.

    Objetivo de negocio:
        El hook de la vista (no solo el util aislado) actualiza ST.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='SYNC-VISTA')
        self.orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-SYNC-VISTA-01',
            estado='equipo_diagnosticado',
        )

    @patch('almacen.tasks.notificar_compras_nueva_cotizacion_task.delay')
    def test_crear_solicitud_con_orden_actualiza_estado_st(self, _mock_email) -> None:
        """
        POST crear con número de orden del cliente → ST a enviada_proveedor.

        EXPLICACIÓN: el formset exige al menos una línea; mockeamos el email
        de Compras por si el POST tocara el otro ramo (aquí no debería).
        """
        url = reverse('almacen:crear_solicitud_cotizacion')
        data = {
            'numero_orden_cliente': 'OOW-SYNC-VISTA-01',
            'sin_orden_activa': '',
            'observaciones': 'Test sync crear',
            # Management form del formset de líneas
            'lineas-TOTAL_FORMS': '1',
            'lineas-INITIAL_FORMS': '0',
            'lineas-MIN_NUM_FORMS': '1',
            'lineas-MAX_NUM_FORMS': '1000',
            'lineas-0-producto': str(self.producto.pk),
            'lineas-0-proveedor': str(self.proveedor.pk),
            'lineas-0-descripcion_pieza': self.producto.nombre,
            'lineas-0-cantidad': '1',
            'lineas-0-costo_unitario': '150.00',
            'lineas-0-DELETE': '',
        }
        request = request_post(self.factory, self.user, url, data)
        respuesta = crear_solicitud_cotizacion(request)

        self.assertEqual(respuesta.status_code, 302)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, ESTADO_ST_COTIZACION_ENVIADA_PROVEEDOR)

        # La solicitud quedó ligada a la orden
        solicitud = SolicitudCotizacion.objects.get(orden_servicio=self.orden)
        self.assertFalse(solicitud.sin_orden_activa)
        # Compras NO recibe email en modo con orden
        _mock_email.assert_not_called()
