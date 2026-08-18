"""
Tests de regresión: precios al cliente en respuestas masivas (todas las líneas).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Bug que cubren estos tests:

Al pulsar "Rechazar todas" (o "Aprobar todas"), la PRIMERA línea congela los
precios al cliente de TODAS las líneas con un UPDATE directo a la base de datos
(``persistir_precios_cliente``). Ese UPDATE no actualiza los objetos Python que
ya estaban cargados en memoria, así que las líneas siguientes seguían con
``precio_unitario_cliente = None`` y su ``save()`` completo pisaba el precio
recién guardado: solo la primera pieza quedaba con costo y las demás en blanco
(también en ``PiezaCotizada`` de Servicio Técnico).

Aquí verificamos que las 3 líneas terminen con precio al cliente, tanto por la
vista HTTP como llamando al modelo con un objeto obsoleto a propósito.

Las notificaciones (Celery) se mockean para no tocar broker/correo en CI.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from almacen.models import LineaCotizacion, SolicitudCotizacion
from almacen.tests.helpers_integracion_cotizacion import (
    BaseIntegracionCotizacionMixin,
    request_post,
)
from almacen.views import aprobar_todas_lineas, rechazar_todas_lineas
from servicio_tecnico.models import Cotizacion


class PreciosClienteRespuestaMasivaTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Objetivo de negocio: que el costo compartido al cliente quede guardado en
    TODAS las piezas cuando se responde en bloque, no solo en la primera.
    """

    def setUp(self) -> None:
        """
        Crea contexto base + orden ST + solicitud enviada con 3 líneas sin precio.

        Efectos secundarios:
            Inserta filas reales en Almacén y Servicio Técnico (la Cotizacion ST
            y las PiezaCotizada nacen al guardar cada línea con orden vinculada).
        """
        self._crear_contexto_base(sufijo='MAS')
        self.orden = self._crear_orden_con_detalle(orden_cliente='OOW-MAS-01')
        self.solicitud = SolicitudCotizacion.objects.create(
            orden_servicio=self.orden,
            estado='enviada_cliente',
            creado_por=self.user,
            # Perfil de profit con el que se calculan los precios al cliente
            tipo_servicio_cliente='estandar',
        )
        self.cotizacion = Cotizacion.objects.get(orden=self.orden)

        # Tres piezas con costos distintos: si el bug existe, solo la #1 salva precio
        self.linea_a = self._crear_linea_sin_precio('RAM 8GB ranura A', '100.00')
        self.linea_b = self._crear_linea_sin_precio('RAM 16GB ranura B', '250.00')
        self.linea_c = self._crear_linea_sin_precio('RAM 32GB ranura C', '480.00')

    def _crear_linea_sin_precio(self, descripcion: str, costo: str) -> LineaCotizacion:
        """
        Crea una línea pendiente SIN precio al cliente (cotización recién enviada).

        Args:
            descripcion: Texto único por línea (evita que el sync ST confunda piezas).
            costo: Costo de proveedor como string decimal.

        Returns:
            LineaCotizacion recién creada.
        """
        return LineaCotizacion.objects.create(
            solicitud=self.solicitud,
            producto=self.producto,
            proveedor=self.proveedor,
            descripcion_pieza=descripcion,
            cantidad=1,
            costo_unitario=Decimal(costo),
            precio_unitario_cliente=None,
            subtotal_cliente_sin_iva=None,
            estado_cliente='pendiente',
        )

    def _assert_todas_con_precio(self, estado_esperado: str) -> None:
        """
        Verifica que las 3 líneas quedaron con precio al cliente y estado correcto.

        Args:
            estado_esperado: 'rechazada' o 'aprobada'.

        Efectos secundarios:
            Relee líneas y piezas ST desde la BD (refresh_from_db).
        """
        self.solicitud.refresh_from_db()
        self.assertIsNotNone(
            self.solicitud.fecha_precios_cliente,
            'La primera respuesta debe congelar los precios de la solicitud.',
        )

        for linea in (self.linea_a, self.linea_b, self.linea_c):
            linea.refresh_from_db()
            self.assertEqual(linea.estado_cliente, estado_esperado)
            # Núcleo de la regresión: ninguna línea debe quedarse sin precio
            self.assertIsNotNone(
                linea.precio_unitario_cliente,
                f'La línea "{linea.descripcion_pieza}" quedó sin precio al cliente.',
            )
            self.assertGreater(linea.precio_unitario_cliente, 0)
            self.assertIsNotNone(linea.subtotal_cliente_sin_iva)
            self.assertGreater(linea.subtotal_cliente_sin_iva, 0)

            # El precio también debe viajar a Servicio Técnico (PiezaCotizada)
            self.assertIsNotNone(linea.pieza_cotizada_origen_id)
            pieza = linea.pieza_cotizada_origen
            pieza.refresh_from_db()
            self.assertEqual(pieza.precio_unitario_cliente, linea.precio_unitario_cliente)

    @patch('almacen.utils.notificar_respuesta_cotizacion.notificar_cotizacion_rechazada')
    def test_rechazar_todas_guarda_precio_en_todas_las_lineas(self, _mock_notif) -> None:
        """POST «Rechazar todas»: las 3 piezas conservan su costo al cliente."""
        url = reverse(
            'almacen:rechazar_todas_lineas',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(
            self.factory,
            self.user,
            url,
            {'motivo': 'Cliente rechaza toda la cotización'},
        )
        respuesta = rechazar_todas_lineas(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self._assert_todas_con_precio('rechazada')
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'totalmente_rechazada')

    @patch('almacen.utils.notificar_respuesta_cotizacion.notificar_cotizacion_aceptada')
    def test_aprobar_todas_guarda_precio_en_todas_las_lineas(self, _mock_notif) -> None:
        """POST «Aprobar todas»: mismo patrón de bug, mismas garantías."""
        url = reverse(
            'almacen:aprobar_todas_lineas',
            kwargs={'pk': self.solicitud.pk},
        )
        request = request_post(self.factory, self.user, url, {})
        respuesta = aprobar_todas_lineas(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self._assert_todas_con_precio('aprobada')
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'totalmente_aprobada')

    @patch('almacen.utils.notificar_respuesta_cotizacion.notificar_cotizacion_rechazada')
    def test_objeto_obsoleto_no_borra_precio_ya_congelado(self, _mock_notif) -> None:
        """
        Blindaje del modelo: rechazar desde un objeto viejo no pisa el precio.

        EXPLICACIÓN: cargamos las líneas en una lista (como hacía el bucle de la
        vista), rechazamos la primera (eso congela precios en BD) y luego
        rechazamos la segunda SIN refrescarla a mano. El helper
        refrescar_precios_cliente_en_memoria() debe releer el precio antes de guardar.
        """
        lineas_en_memoria = list(self.solicitud.lineas.all().order_by('numero_linea'))
        self.assertEqual(len(lineas_en_memoria), 3)
        # Punto de partida: nadie tiene precio todavía
        for linea in lineas_en_memoria:
            self.assertIsNone(linea.precio_unitario_cliente)

        # Primera respuesta: congela precios de las 3 líneas en la BD
        self.assertTrue(lineas_en_memoria[0].rechazar(motivo='no autoriza'))

        # Segunda línea: sigue obsoleta en memoria (precio None) a propósito
        linea_obsoleta = lineas_en_memoria[1]
        self.assertIsNone(linea_obsoleta.precio_unitario_cliente)
        self.assertTrue(linea_obsoleta.rechazar(motivo='no autoriza'))

        linea_obsoleta.refresh_from_db()
        self.assertEqual(linea_obsoleta.estado_cliente, 'rechazada')
        self.assertIsNotNone(
            linea_obsoleta.precio_unitario_cliente,
            'El objeto obsoleto borró el precio ya congelado.',
        )
        self.assertGreater(linea_obsoleta.precio_unitario_cliente, 0)
