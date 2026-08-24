"""
Tests: SeguimientoPieza en órdenes FL (Venta Mostrador) vía sync Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Antes el sync omitía ``venta_mostrador``. Ahora al generar compras en una
orden FL debe:

1. Crear PiezaVentaMostrador con ``linea_cotizacion`` (trazabilidad).
2. Crear SeguimientoPieza anclado a la orden (cotizacion=NULL).
3. Pasar la orden de ``almacen`` → ``esperando_piezas``.
4. Al recibir la compra → seguimiento ``recibido`` y orden ``piezas_recibidas``.

También se verifica anti-duplicado de PiezaVentaMostrador y regresión OOW
(que siga creando seguimiento con cotizacion + PiezaCotizada).
"""

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.test import TestCase
from django.urls import reverse

from almacen.models import CompraProducto, LineaServicioAdicional
from almacen.tests.helpers_integracion_cotizacion import (
    BaseIntegracionCotizacionMixin,
    request_post,
)
from almacen.views import crear_orden_fl_desde_cotizacion, generar_compras_solicitud
from inventario.models import Empleado
from servicio_tecnico.models import (
    Cotizacion,
    PiezaVentaMostrador,
    SeguimientoPieza,
    VentaMostrador,
)
from servicio_tecnico.services.pagos_orden import calcular_resumen_cobro


class SeguimientoPiezasFlTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Flujo sin orden → Crear FL → generar compras → recibir → tracking ST.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='FLSEG')
        # Técnico con rol de sistema (requerido por crear_orden_fl)
        self.tecnico = Empleado.objects.create(
            user=None,
            nombre_completo='Técnico FL Seg',
            cargo='Técnico',
            area='CALIDAD',
            email='tecnico.flseg@test.local',
            sucursal=self.sucursal,
            rol=Empleado.ROL_TECNICO,
            activo=True,
            tiene_acceso_sistema=False,
            contraseña_configurada=False,
        )

    def _crear_orden_fl(self, solicitud, numero_fl: str):
        """
        POST crear_orden_fl_desde_cotizacion y devuelve la orden vinculada.

        Args:
            solicitud: SolicitudCotizacion sin orden (modo sin_orden_activa).
            numero_fl: Folio FL- visible para el cliente.

        Returns:
            OrdenServicio recién creada y vinculada.
        """
        url_fl = reverse(
            'almacen:crear_orden_fl_desde_cotizacion',
            kwargs={'pk': solicitud.pk},
        )
        resp_fl = crear_orden_fl_desde_cotizacion(
            request_post(
                self.factory,
                self.user,
                url_fl,
                {
                    'tecnico_id': str(self.tecnico.pk),
                    'numero_fl': numero_fl,
                },
            ),
            solicitud.pk,
        )
        self.assertEqual(resp_fl.status_code, 302)
        solicitud.refresh_from_db()
        self.assertIsNotNone(solicitud.orden_servicio)
        return solicitud.orden_servicio

    def test_fl_generar_compras_crea_seguimiento_y_recibir_cierra(self) -> None:
        """
        Caso principal: FL sin Cotizacion ST igual tiene SeguimientoPieza.
        """
        # Paso 1: cotización sin orden; cliente aprueba en Almacén
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        # Datos mínimos de cliente/equipo para crear FL
        solicitud.nombre_cliente = 'Cliente FL Seg'
        solicitud.email_cliente = 'cliente.flseg@test.local'
        solicitud.service_tag = 'SN-FL-SEG-01'
        solicitud.tipo_equipo = 'Laptop'
        solicitud.marca = 'DELL'
        solicitud.modelo = 'Latitude'
        solicitud.save()

        self.assertTrue(linea.aprobar())
        solicitud.refresh_from_db()
        self.assertTrue(solicitud.compras_pendientes_sin_orden())
        self.assertFalse(Cotizacion.objects.filter(
            orden__detalle_equipo__numero_serie='SN-FL-SEG-01'
        ).exists())

        # Paso 2: crear orden FL vía vista HTTP
        orden = self._crear_orden_fl(solicitud, 'FL-2099-0001')
        self.assertEqual(orden.tipo_servicio, 'venta_mostrador')
        self.assertEqual(orden.estado, 'almacen')
        # FL no debe crear Cotizacion ST
        self.assertFalse(
            Cotizacion.objects.filter(orden=orden).exists(),
            msg='Órdenes FL no deben crear Cotizacion ST',
        )

        # Paso 3: generar compras → PiezaVentaMostrador + SeguimientoPieza
        self._registrar_anticipo_50(orden)
        url_compras = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': solicitud.pk},
        )
        resp_compras = generar_compras_solicitud(
            request_post(self.factory, self.user, url_compras, {}),
            solicitud.pk,
        )
        self.assertEqual(resp_compras.status_code, 302)

        linea.refresh_from_db()
        orden.refresh_from_db()
        solicitud.refresh_from_db()

        self.assertIsNotNone(linea.compra_generada_id)
        self.assertEqual(linea.estado_cliente, 'compra_generada')

        # Trazabilidad línea ↔ Pieza VM
        pieza_vm = PiezaVentaMostrador.objects.get(linea_cotizacion=linea)
        self.assertEqual(pieza_vm.venta_mostrador.orden_id, orden.pk)

        # Seguimiento anclado a orden, sin cotización
        seguimientos = SeguimientoPieza.objects.filter(orden=orden)
        self.assertEqual(seguimientos.count(), 1)
        seguimiento = seguimientos.first()
        self.assertIsNone(seguimiento.cotizacion_id)
        self.assertEqual(seguimiento.estado, 'transito')
        self.assertIn(pieza_vm, seguimiento.piezas_venta_mostrador.all())
        self.assertEqual(orden.estado, 'esperando_piezas')

        # Paso 4: recibir compra (sin email real)
        compra = CompraProducto.objects.get(pk=linea.compra_generada_id)
        ok = compra.recibir(
            fecha_recepcion=date.today(),
            crear_unidades=False,
            notificar_tecnico_st=False,
        )
        self.assertTrue(ok)

        seguimiento.refresh_from_db()
        orden.refresh_from_db()
        self.assertEqual(seguimiento.estado, 'recibido')
        self.assertEqual(seguimiento.fecha_entrega_real, date.today())
        self.assertEqual(orden.estado, 'piezas_recibidas')

        # Resultado del sync expuesto en la compra
        resultado = getattr(compra, '_resultado_sync_seguimiento_st', {})
        self.assertEqual(resultado.get('seguimientos_actualizados'), 1)
        self.assertTrue(resultado.get('estado_orden_actualizado'))

    def test_fl_al_aceptar_pieza_y_servicio_entran_al_cobro_sin_compra(self) -> None:
        """
        Al vincular la FL, pieza y servicio ya están en Venta Mostrador
        (cobro = PDF). Aún no existe CompraProducto.
        """
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        solicitud.nombre_cliente = 'Cliente FL Cobro'
        solicitud.email_cliente = 'cliente.flcobro@test.local'
        solicitud.service_tag = 'SN-FL-COBRO-01'
        solicitud.tipo_equipo = 'Laptop'
        solicitud.marca = 'DELL'
        solicitud.modelo = 'Latitude'
        solicitud.save()
        LineaServicioAdicional.objects.create(
            solicitud=solicitud,
            tipo_servicio='limpieza',
            costo=Decimal('450.00'),
            estado_cliente='pendiente',
        )

        self.assertTrue(linea.aprobar())
        servicio = solicitud.servicios_adicionales.get(tipo_servicio='limpieza')
        self.assertTrue(servicio.aprobar())
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.estado, 'totalmente_aprobada')
        self.assertEqual(CompraProducto.objects.count(), 0)

        orden = self._crear_orden_fl(solicitud, 'FL-2099-0100')
        linea.refresh_from_db()
        servicio.refresh_from_db()

        # Pieza y servicio ya en ST; Compras aún no pidió al proveedor.
        self.assertEqual(CompraProducto.objects.count(), 0)
        self.assertEqual(linea.estado_cliente, 'aprobada')
        self.assertIsNone(linea.compra_generada_id)
        pieza_vm = PiezaVentaMostrador.objects.get(linea_cotizacion=linea)
        self.assertEqual(pieza_vm.venta_mostrador.orden_id, orden.pk)
        venta = VentaMostrador.objects.get(orden=orden)
        self.assertTrue(venta.incluye_limpieza)
        self.assertEqual(venta.costo_limpieza, Decimal('450.00'))

        linea.refresh_from_db()
        precio_sin_iva = linea.precio_unitario_cliente * linea.cantidad
        precio_con_iva = (precio_sin_iva * Decimal('1.16')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        self.assertEqual(pieza_vm.precio_unitario, precio_con_iva)

        resumen = calcular_resumen_cobro(orden, codigo_pais='MX')
        total_esperado = solicitud.total_aprobado_con_iva
        self.assertEqual(resumen.total_venta_mostrador, total_esperado)
        self.assertEqual(resumen.total_a_cobrar, total_esperado)
        self.assertEqual(resumen.total_a_cobrar, precio_con_iva + Decimal('450.00'))
        self.assertFalse(resumen.cubre_anticipo_50)

        # Generar Compras no duplica la pieza; sí nace CompraProducto.
        self._registrar_anticipo_50(orden)
        url_compras = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': solicitud.pk},
        )
        resp_compras = generar_compras_solicitud(
            request_post(self.factory, self.user, url_compras, {}),
            solicitud.pk,
        )
        self.assertEqual(resp_compras.status_code, 302)
        self.assertEqual(
            PiezaVentaMostrador.objects.filter(linea_cotizacion=linea).count(),
            1,
        )
        linea.refresh_from_db()
        self.assertIsNotNone(linea.compra_generada_id)
        self.assertEqual(CompraProducto.objects.count(), 1)

    def test_generar_piezas_vm_idempotente_por_linea(self) -> None:
        """
        Segunda llamada a generar_piezas_venta_mostrador no duplica Pieza VM.
        """
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='totalmente_aprobada',
            estado_linea='aprobada',
        )
        solicitud.nombre_cliente = 'Cliente Idem'
        solicitud.service_tag = 'SN-FL-IDEM'
        solicitud.save()

        # Crear FL manualmente (mismo efecto que la vista)
        from servicio_tecnico.models import DetalleEquipo, OrdenServicio, VentaMostrador

        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='venta_mostrador',
            estado='almacen',
            tecnico_asignado_actual=self.tecnico,
            responsable_seguimiento=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='FL-2099-0099',
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='X',
            numero_serie='SN-FL-IDEM',
            email_cliente='idem@test.local',
            nombre_cliente='Cliente Idem',
        )
        solicitud.vincular_orden(orden)
        VentaMostrador.objects.get_or_create(orden=orden)

        # Al vincular una solicitud ya aceptada, la pieza ya se copió.
        self.assertEqual(
            PiezaVentaMostrador.objects.filter(linea_cotizacion=linea).count(),
            1,
        )
        n1 = solicitud.generar_piezas_venta_mostrador()
        n2 = solicitud.generar_piezas_venta_mostrador()
        self.assertEqual(n1, 0)
        self.assertEqual(n2, 0)
        self.assertEqual(
            PiezaVentaMostrador.objects.filter(linea_cotizacion=linea).count(),
            1,
        )


class SeguimientoPiezasOowRegresionTest(BaseIntegracionCotizacionMixin, TestCase):
    """Regresión: OOW sigue creando SeguimientoPieza con Cotizacion + PiezaCotizada."""

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='OOWSEG')

    def test_oow_generar_compras_sigue_creando_seguimiento_con_cotizacion(self) -> None:
        orden = self._crear_orden_con_detalle(
            orden_cliente='OOW-SEG-REG-01',
            estado='cliente_acepta_cotizacion',
        )
        solicitud, linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_cliente',
            estado_linea='pendiente',
        )
        self.assertTrue(linea.aprobar())
        self._registrar_anticipo_50(orden)

        url_compras = reverse(
            'almacen:generar_compras_solicitud',
            kwargs={'pk': solicitud.pk},
        )
        resp = generar_compras_solicitud(
            request_post(self.factory, self.user, url_compras, {}),
            solicitud.pk,
        )
        self.assertEqual(resp.status_code, 302)

        linea.refresh_from_db()
        orden.refresh_from_db()
        pieza = linea.pieza_cotizada_origen
        self.assertIsNotNone(pieza)

        seguimiento = SeguimientoPieza.objects.filter(orden=orden).first()
        self.assertIsNotNone(seguimiento)
        self.assertEqual(seguimiento.cotizacion_id, orden.pk)  # Cotizacion PK = orden
        self.assertIn(pieza, seguimiento.piezas.all())
        # El texto del seguimiento es nombre × cantidad, sin precio.
        self.assertIn(pieza.componente.nombre, seguimiento.descripcion_piezas)
        self.assertNotIn('$', seguimiento.descripcion_piezas)
        self.assertEqual(orden.estado, 'esperando_piezas')
        self.assertFalse(
            PiezaVentaMostrador.objects.filter(linea_cotizacion=linea).exists(),
        )
