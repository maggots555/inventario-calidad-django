"""
Tests de normalización ProductoAlmacen → ComponenteEquipo al sincronizar con ST.
"""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase

from almacen.utils.resolver_componente import (
    obtener_componente_equipo_reacondicionado,
    resolver_componente_desde_producto,
)
from config.constants import NOMBRE_COMPONENTE_EQUIPO_REACONDICIONADO
from scorecard.models import ComponenteEquipo


class ResolverComponenteDesdeProductoTest(TestCase):
    """Pruebas del emparejamiento por nombre de producto de almacén."""

    @classmethod
    def setUpTestData(cls):
        """Catálogo mínimo de ComponenteEquipo para las pruebas."""
        nombres = [
            'Batería',
            'Cargador',
            'Pantalla',
            'RAM',
            'Motherboard',
            NOMBRE_COMPONENTE_EQUIPO_REACONDICIONADO,
        ]
        for nombre in nombres:
            ComponenteEquipo.objects.get_or_create(
                nombre=nombre,
                defaults={'activo': True, 'tipo_equipo': 'todos'},
            )

    def test_bateria_desde_nombre_producto(self):
        componente = resolver_componente_desde_producto('BATERÍA / PILA DELL 40 W')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Batería')

    def test_cargador_desde_nombre_producto(self):
        componente = resolver_componente_desde_producto(
            'CARGADOR / ADAPTADOR 150 W DELL'
        )
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Cargador')

    def test_pantalla_desde_lcd(self):
        componente = resolver_componente_desde_producto('PANTALLA LCD 15.6 FHD DELL')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Pantalla')

    def test_ram_desde_memoria(self):
        componente = resolver_componente_desde_producto('MEMORIA RAM DDR4 16GB KINGSTON')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'RAM')

    def test_sin_match_devuelve_none(self):
        componente = resolver_componente_desde_producto('ACCESORIO GENERICO SIN CLAVE XYZ')
        self.assertIsNone(componente)

    def test_equipo_reacondicionado_flag(self):
        componente = resolver_componente_desde_producto(
            'EQUIPO REACONDICIONADO',
            es_reacondicionado=True,
        )
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, NOMBRE_COMPONENTE_EQUIPO_REACONDICIONADO)

    def test_obtener_componente_reacondicionado_helper(self):
        componente = obtener_componente_equipo_reacondicionado()
        self.assertEqual(componente.nombre, NOMBRE_COMPONENTE_EQUIPO_REACONDICIONADO)

    def test_descripcion_pieza_como_respaldo(self):
        componente = resolver_componente_desde_producto(
            'SKU-GENERICO',
            descripcion_pieza='MOTHERBOARD DELL LATITUDE 7420',
        )
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Motherboard')


class SincronizarPiezaStComponenteTest(SimpleTestCase):
    """Verifica que _sincronizar_pieza_st asigna componente vía el resolver."""

    @patch('servicio_tecnico.models.PiezaCotizada')
    @patch('servicio_tecnico.models.Cotizacion')
    @patch('almacen.utils.resolver_componente.resolver_componente_desde_producto')
    def test_asigna_componente_resuelto(
        self,
        mock_resolver,
        mock_cotizacion_cls,
        mock_pieza_cls,
    ):
        from almacen.models import LineaCotizacion

        componente_mock = MagicMock()
        componente_mock.nombre = 'Batería'
        mock_resolver.return_value = componente_mock

        orden = SimpleNamespace(
            tipo_servicio='diagnostico',
            numero_orden_interno='OOW-001',
        )

        solicitud = SimpleNamespace(orden_servicio=orden)

        producto = SimpleNamespace(nombre='BATERÍA / PILA DELL 40 W')

        linea = SimpleNamespace(
            pk=99,
            solicitud=solicitud,
            producto=producto,
            producto_id=1,
            descripcion_pieza='BATERÍA / PILA DELL 40 W',
            pieza_cotizada_origen=None,
            pieza_cotizada_origen_id=None,
            es_linea_reacondicionado=False,
            cantidad=1,
            costo_unitario=Decimal('100'),
            precio_unitario_cliente=Decimal('150'),
            proveedor=None,
            sugerida_por_tecnico=False,
            es_necesaria=True,
            numero_linea=1,
            estado_cliente='aprobada',
            motivo_rechazo='',
        )

        cotizacion = MagicMock()
        mock_cotizacion_cls.objects.get.return_value = cotizacion

        pieza_instancia = MagicMock()
        mock_pieza_cls.objects.filter.return_value.first.return_value = None
        mock_pieza_cls.return_value = pieza_instancia

        # Evitar super().save() al vincular pieza_cotizada_origen (linea es SimpleNamespace)
        linea.pieza_cotizada_origen = pieza_instancia

        LineaCotizacion._sincronizar_pieza_st(linea)

        mock_resolver.assert_called_once_with(
            'BATERÍA / PILA DELL 40 W',
            'BATERÍA / PILA DELL 40 W',
        )
        self.assertEqual(pieza_instancia.componente, componente_mock)
        pieza_instancia.save.assert_called_once()


class SincronizarPiezaStNoReutilizaVinculadaTest(SimpleTestCase):
    """
    La búsqueda por descripción debe exigir piezas aún libres
    (linea_cotizacion_almacen__isnull=True) para no romper el OneToOne.
    """

    @patch('servicio_tecnico.models.PiezaCotizada')
    @patch('servicio_tecnico.models.Cotizacion')
    @patch('almacen.utils.resolver_componente.resolver_componente_desde_producto')
    def test_filtro_busca_solo_piezas_sin_linea_almacen(
        self,
        mock_resolver,
        mock_cotizacion_cls,
        mock_pieza_cls,
    ):
        from almacen.models import LineaCotizacion

        mock_resolver.return_value = MagicMock()

        orden = SimpleNamespace(
            tipo_servicio='diagnostico',
            numero_orden_interno='OOW-002',
        )
        solicitud = SimpleNamespace(orden_servicio=orden)
        producto = SimpleNamespace(nombre='SSD 1TB')

        # MagicMock(spec=...) permite super(LineaCotizacion, self).save()
        linea = MagicMock(spec=LineaCotizacion)
        linea.pk = 100
        linea.solicitud = solicitud
        linea.producto = producto
        linea.producto_id = 2
        linea.descripcion_pieza = 'SSD 1TB NVMe'
        linea.pieza_cotizada_origen = None
        linea.pieza_cotizada_origen_id = None
        linea.es_linea_reacondicionado = False
        linea.cantidad = 1
        linea.costo_unitario = Decimal('50')
        linea.precio_unitario_cliente = None
        linea.proveedor = None
        linea.sugerida_por_tecnico = False
        linea.es_necesaria = True
        linea.numero_linea = 2
        linea.estado_cliente = 'pendiente'
        linea.motivo_rechazo = ''

        mock_cotizacion_cls.objects.get.return_value = MagicMock()
        mock_pieza_cls.objects.filter.return_value.first.return_value = None
        mock_pieza_cls.return_value = MagicMock()

        with patch('django.db.models.base.Model.save'):
            LineaCotizacion._sincronizar_pieza_st(linea)

        filter_kwargs = mock_pieza_cls.objects.filter.call_args.kwargs
        self.assertEqual(filter_kwargs.get('linea_cotizacion_almacen__isnull'), True)
        self.assertEqual(
            filter_kwargs.get('descripcion_adicional__icontains'),
            'SSD 1TB NVMe',
        )


class GenerarPiezasVentaMostradorComponenteTest(SimpleTestCase):
    """Verifica asignación de componente al crear PiezaVentaMostrador."""

    @patch('servicio_tecnico.models.PiezaVentaMostrador')
    @patch('servicio_tecnico.models.VentaMostrador')
    @patch('almacen.utils.resolver_componente.resolver_componente_desde_producto')
    def test_crea_pieza_con_componente_normalizado(
        self,
        mock_resolver,
        mock_vm_cls,
        mock_pieza_vm_cls,
    ):
        from almacen.models import SolicitudCotizacion

        componente_mock = MagicMock()
        componente_mock.nombre = 'RAM'
        mock_resolver.return_value = componente_mock

        orden = SimpleNamespace(
            tipo_servicio='venta_mostrador',
            numero_orden_interno='FL-001',
        )

        producto = SimpleNamespace(nombre='MEMORIA RAM DDR4 16GB')

        linea = SimpleNamespace(
            producto=producto,
            descripcion_pieza='MEMORIA RAM DDR4 16GB',
            es_linea_reacondicionado=False,
            cantidad=1,
            precio_unitario_cliente=Decimal('500'),
            costo_unitario=Decimal('300'),
            proveedor=None,
        )

        qs_lineas = MagicMock()
        qs_lineas.__iter__ = MagicMock(return_value=iter([linea]))

        solicitud = SimpleNamespace(
            orden_servicio=orden,
            numero_solicitud='COT-001',
            resultado_costeo_reac={},
            lineas=MagicMock(),
        )
        solicitud.lineas.filter.return_value = qs_lineas

        vm = MagicMock()
        mock_vm_cls.objects.get_or_create.return_value = (vm, True)

        SolicitudCotizacion.generar_piezas_venta_mostrador(solicitud)

        mock_resolver.assert_called_once_with(
            'MEMORIA RAM DDR4 16GB',
            'MEMORIA RAM DDR4 16GB',
            es_reacondicionado=False,
        )
        mock_pieza_vm_cls.objects.create.assert_called_once()
        kwargs_create = mock_pieza_vm_cls.objects.create.call_args.kwargs
        self.assertEqual(kwargs_create['componente'], componente_mock)

    @patch('servicio_tecnico.models.PiezaVentaMostrador')
    @patch('servicio_tecnico.models.VentaMostrador')
    @patch('almacen.utils.resolver_componente.resolver_componente_desde_producto')
    def test_reac_asigna_equipo_reacondicionado(
        self,
        mock_resolver,
        mock_vm_cls,
        mock_pieza_vm_cls,
    ):
        from almacen.models import SolicitudCotizacion

        componente_reac = MagicMock()
        componente_reac.nombre = NOMBRE_COMPONENTE_EQUIPO_REACONDICIONADO
        mock_resolver.return_value = componente_reac

        orden = SimpleNamespace(tipo_servicio='diagnostico', numero_orden_interno='OOW-REAC')

        producto = SimpleNamespace(nombre='EQUIPO REACONDICIONADO')

        linea = SimpleNamespace(
            producto=producto,
            descripcion_pieza='Laptop Dell Latitude reac',
            es_linea_reacondicionado=True,
            cantidad=1,
            opcion_pago_reac='contado',
            precio_unitario_cliente=Decimal('8000'),
            costo_unitario=Decimal('5000'),
            notas='',
        )

        qs_reac = MagicMock()
        qs_reac.exists.return_value = True
        qs_reac.__iter__ = MagicMock(return_value=iter([linea]))

        qs_pendientes = MagicMock()
        qs_pendientes.filter.return_value = qs_reac

        solicitud = SimpleNamespace(
            orden_servicio=orden,
            numero_solicitud='COT-REAC',
            resultado_costeo_reac={'total_precio_contado_mxn': 9000},
            lineas=MagicMock(),
        )
        solicitud.lineas.filter.return_value = qs_pendientes

        mock_vm_cls.objects.get_or_create.return_value = (MagicMock(), True)

        SolicitudCotizacion.generar_piezas_venta_mostrador(solicitud)

        mock_resolver.assert_called_once_with(
            'EQUIPO REACONDICIONADO',
            'Laptop Dell Latitude reac',
            es_reacondicionado=True,
        )
        kwargs_create = mock_pieza_vm_cls.objects.create.call_args.kwargs
        self.assertEqual(kwargs_create['componente'].nombre, NOMBRE_COMPONENTE_EQUIPO_REACONDICIONADO)
