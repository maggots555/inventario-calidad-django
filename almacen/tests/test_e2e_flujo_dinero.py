"""
Tests E2E punta a punta: flujo de dinero Almacén → ST → compras.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Los tests de test_integracion_cotizacion_st.py ya cubren tramos (aprobar por
modelo, bloqueo sin orden, rechazo). Aquí reforzamos el hilo completo del
dinero con asserts explícitos de sync ST y de SeguimientoPieza:

1) Crear solicitud+línea → Cotizacion/PiezaCotizada sincronizadas.
2) Aprobar por HTTP + generar compras → CompraProducto + seguimiento + estado.
3) Sin orden: bloquear → vincular → sync ST → compras.
4) Candado: aceptar en detalle_orden NO aprueba la línea de Almacén ni desbloquea compras.

No hacemos POST al formulario gigante crear_solicitud_cotizacion: el sync real
ocurre en SolicitudCotizacion.save() / LineaCotizacion.save().
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from almacen.models import CompraProducto
from almacen.tests.helpers_integracion_cotizacion import (
    BaseIntegracionCotizacionMixin,
    request_post,
)
from almacen.views import (
    aprobar_todas_lineas,
    generar_compras_solicitud,
    vincular_orden_solicitud,
)
from servicio_tecnico.models import Cotizacion, PiezaCotizada, SeguimientoPieza
from servicio_tecnico.views import detalle_orden


class E2eFlujoDineroAlmacenStTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Recorrido Almacén ↔ ST del dinero (sync, aprobar HTTP, compras, candado).

    Objetivo de negocio:
        Blindar el camino que mueve inventario/compras reales para que una
        regresión en sync o en el candado Almacén se note en CI.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='E2E')

    def test_solicitud_con_orden_sincroniza_cotizacion_y_pieza_st(self) -> None:
        """
        Tras crear solicitud+línea con orden: existen Cotizacion y PiezaCotizada.

        EXPLICACIÓN: el save() de los modelos de Almacén es el «puente» hacia ST.
        Si este assert falla, generar compras o el detalle de orden verán datos rotos.
        """
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-E2E-SYNC-01')
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )

        # Paso 1: cabecera ST creada al guardar SolicitudCotizacion con orden
        cotizacion = Cotizacion.objects.get(orden=orden)
        self.assertEqual(cotizacion.orden_id, orden.pk)

        # Paso 2: línea sincroniza PiezaCotizada (OneToOne pieza_cotizada_origen)
        linea.refresh_from_db()
        self.assertIsNotNone(linea.pieza_cotizada_origen_id)
        pieza = PiezaCotizada.objects.get(pk=linea.pieza_cotizada_origen_id)
        self.assertEqual(pieza.cotizacion_id, cotizacion.pk)
        # Precio cliente de Almacén debe reflejarse en la pieza ST
        self.assertEqual(pieza.precio_unitario_cliente, Decimal('300.00'))
        # reverse OneToOne (related_name): desde ST se llega a la línea de Almacén
        self.assertEqual(pieza.linea_cotizacion_almacen.pk, linea.pk)

        # Paso 3: aún pendiente de decisión del cliente (ni compras ni aceptación)
        self.assertEqual(linea.estado_cliente, 'pendiente')
        self.assertIsNone(pieza.aceptada_por_cliente)
        self.assertFalse(solicitud.puede_generar_compras())

    def test_aprobar_http_y_generar_compras_crea_compra_y_seguimiento(self) -> None:
        """
        POST aprobar_todas + generar_compras → CompraProducto + SeguimientoPieza.

        EXPLICACIÓN: a diferencia del test de integración que aprueba por modelo,
        aquí usamos la vista HTTP real (como en la UI de Almacén).
        """
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-E2E-APR-01')
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        pieza = linea.pieza_cotizada_origen
        self.assertIsNotNone(pieza)

        # Paso 1: aprobar todas las líneas pendientes vía vista HTTP
        url_aprobar = reverse(
            'almacen:aprobar_todas_lineas',
            kwargs={'pk': solicitud.pk},
        )
        request_aprobar = request_post(self.factory, self.user, url_aprobar, {})
        resp_aprobar = aprobar_todas_lineas(request_aprobar, solicitud.pk)
        self.assertEqual(resp_aprobar.status_code, 302)

        linea.refresh_from_db()
        solicitud.refresh_from_db()
        self.assertEqual(linea.estado_cliente, 'aprobada')
        self.assertTrue(solicitud.puede_generar_compras())

        # Paso 2: generar compras (crea CompraProducto + sync seguimiento ST)
        url_compras = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': solicitud.pk},
        )
        request_compras = request_post(self.factory, self.user, url_compras, {})
        resp_compras = generar_compras_solicitud(request_compras, solicitud.pk)
        self.assertEqual(resp_compras.status_code, 302)

        linea.refresh_from_db()
        solicitud.refresh_from_db()
        orden.refresh_from_db()
        pieza.refresh_from_db()

        self.assertIsNotNone(linea.compra_generada_id)
        compra = CompraProducto.objects.get(pk=linea.compra_generada_id)
        self.assertEqual(linea.estado_cliente, 'compra_generada')
        self.assertEqual(solicitud.estado, 'completada')
        self.assertEqual(compra.producto_id, self.producto.pk)
        self.assertEqual(compra.orden_servicio_id, orden.pk)
        self.assertEqual(orden.estado, 'esperando_piezas')

        # SeguimientoPieza agrupado por proveedor (util sincronizar_seguimiento_piezas)
        self.assertTrue(
            SeguimientoPieza.objects.filter(cotizacion=orden.cotizacion).exists(),
            msg='Al generar compras OOW debe crearse SeguimientoPieza en ST',
        )
        seguimiento = SeguimientoPieza.objects.filter(
            cotizacion=orden.cotizacion,
        ).first()
        self.assertEqual(
            seguimiento.orden_id,
            orden.pk,
            msg='SeguimientoPieza debe anclarse a la orden',
        )
        self.assertIn(pieza, seguimiento.piezas.all())

    def test_sin_orden_bloquear_compras_luego_vincular_y_generar(self) -> None:
        """
        Sin orden: compras bloqueadas; al vincular aparece Cotizacion ST y se puede comprar.

        EXPLICACIÓN: refuerza el test de integración con asserts de Cotizacion
        tras el vínculo. PiezaCotizada se materializa al re-guardar la línea
        (p. ej. dentro de generar_compras), no necesariamente en vincular_orden.
        """
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-E2E-VIN-01')
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )

        # Sin orden aún: no debe existir Cotizacion ligada a esta orden
        self.assertFalse(Cotizacion.objects.filter(orden=orden).exists())
        self.assertIsNone(linea.pieza_cotizada_origen_id)

        self.assertTrue(linea.aprobar())
        solicitud.refresh_from_db()
        self.assertFalse(solicitud.puede_generar_compras())
        self.assertTrue(solicitud.compras_pendientes_sin_orden())

        # Intento de compras debe bloquearse
        url_compras = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': solicitud.pk},
        )
        resp_bloqueo = generar_compras_solicitud(
            request_post(self.factory, self.user, url_compras, {}),
            solicitud.pk,
        )
        self.assertEqual(resp_bloqueo.status_code, 302)
        self.assertEqual(CompraProducto.objects.count(), 0)

        # Vincular orden existente
        url_vincular = reverse(
            'almacen:vincular_orden_solicitud',
            kwargs={'pk': solicitud.pk},
        )
        resp_vincular = vincular_orden_solicitud(
            request_post(
                self.factory,
                self.user,
                url_vincular,
                {'orden_pk': str(orden.pk)},
            ),
            solicitud.pk,
        )
        self.assertEqual(resp_vincular.status_code, 302)

        solicitud.refresh_from_db()
        linea.refresh_from_db()
        self.assertEqual(solicitud.orden_servicio_id, orden.pk)
        self.assertFalse(solicitud.sin_orden_activa)

        # Tras vincular: SolicitudCotizacion.save() crea Cotizacion ST.
        # Las PiezaCotizada nacen en LineaCotizacion.save() (al generar compras
        # o al re-guardar la línea); no exigen sync inmediato en vincular_orden.
        cotizacion = Cotizacion.objects.get(orden=orden)
        self.assertEqual(cotizacion.orden_id, orden.pk)
        self.assertTrue(solicitud.puede_generar_compras())

        # Ahora sí generar compras (linea.save interno sincroniza PiezaCotizada)
        resp_compras = generar_compras_solicitud(
            request_post(self.factory, self.user, url_compras, {}),
            solicitud.pk,
        )
        self.assertEqual(resp_compras.status_code, 302)

        linea.refresh_from_db()
        self.assertIsNotNone(linea.compra_generada_id)
        self.assertEqual(linea.estado_cliente, 'compra_generada')
        compra = CompraProducto.objects.get(pk=linea.compra_generada_id)
        self.assertEqual(compra.orden_servicio_id, orden.pk)

        # Tras compras: la pieza ST debe existir y apuntar a la cotización vinculada
        self.assertIsNotNone(linea.pieza_cotizada_origen_id)
        pieza = PiezaCotizada.objects.get(pk=linea.pieza_cotizada_origen_id)
        self.assertEqual(pieza.cotizacion_id, cotizacion.pk)
        self.assertEqual(pieza.linea_cotizacion_almacen.pk, linea.pk)

    def test_pieza_almacen_no_se_aprueba_desde_detalle_orden(self) -> None:
        """
        Aceptar en detalle_orden NO desbloquea compras de una pieza de Almacén.

        EXPLICACIÓN / COMPORTAMIENTO ESPERADO:
        --------------------------------------
        La UI de ST muestra candado en piezas con linea_cotizacion_almacen.
        Aunque el handler gestionar_cotizacion pueda marcar aceptada_por_cliente
        en PiezaCotizada (no filtra el OneToOne), la fuente de verdad del dinero
        es LineaCotizacion.estado_cliente en Almacén: sin aprobar ahí,
        puede_generar_compras() sigue en False y no hay CompraProducto.
        """
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-E2E-CAND-01')
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        linea.refresh_from_db()
        pieza = linea.pieza_cotizada_origen
        self.assertIsNotNone(pieza)
        self.assertEqual(pieza.linea_cotizacion_almacen.pk, linea.pk)

        url_detalle = reverse(
            'servicio_tecnico:detalle_orden',
            args=[orden.pk],
        )
        # POST como en la UI de aceptar cotización ST (seleccionando la pieza Almacén)
        request = request_post(
            self.factory,
            self.user,
            url_detalle,
            {
                'form_type': 'gestionar_cotizacion',
                'accion': 'aceptar',
                'piezas_seleccionadas': [str(pieza.pk)],
            },
        )
        # Session persistente (algunos handlers escriben keys de feedback)
        request.session.create()
        respuesta = detalle_orden(request, orden_id=orden.pk)
        self.assertEqual(respuesta.status_code, 302)

        linea.refresh_from_db()
        solicitud.refresh_from_db()
        pieza.refresh_from_db()

        # Fuente de verdad Almacén: la línea sigue pendiente (no pasó por aprobar())
        self.assertEqual(linea.estado_cliente, 'pendiente')
        self.assertFalse(solicitud.puede_generar_compras())
        self.assertEqual(CompraProducto.objects.count(), 0)
        self.assertIsNone(linea.compra_generada_id)

        # Intento explícito de generar compras debe seguir bloqueado
        url_compras = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': solicitud.pk},
        )
        resp_compras = generar_compras_solicitud(
            request_post(self.factory, self.user, url_compras, {}),
            solicitud.pk,
        )
        self.assertEqual(resp_compras.status_code, 302)
        self.assertEqual(CompraProducto.objects.count(), 0)
        linea.refresh_from_db()
        self.assertEqual(linea.estado_cliente, 'pendiente')
