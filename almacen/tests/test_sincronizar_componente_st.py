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
        # EXPLICACIÓN: incluye componentes reales del catálogo Almacén→ST
        # que antes fallaban (BEZEL, BOTTOM BASE, BRACKET, USB, SOLUCION).
        nombres = [
            'Batería',
            'Cargador',
            'Pantalla',
            'RAM',
            'Motherboard',
            'Bisel LCD',
            'Top Cover',
            'Bottom Cover/Case',
            'HDD/SSD Bracket',
            'Disco Duro / SSD',
            'Memoria USB',
            'Paquete Oro',
            'Paquete Plata',
            'Paquete Premium',
            'Stylus',
            'Unidad optica',
            'Cable de AC',
            'Kit de Limpieza',
            'Pasta termica/Metal liquido',
            'Disipador de calor',
            'Limpieza y mantenimiento',
            'LCD Assembly',
            'Audifonos',
            'Backpack Laptop',
            'Convertidor de video',
            'Hub USB',
            'Tapete antiestatico',
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

    def test_bezel_solo_a_bisel_lcd(self):
        """Producto P0026 BEZEL → Bisel LCD (antes no coincidía)."""
        componente = resolver_componente_desde_producto('BEZEL')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Bisel LCD')

    def test_bezel_protector_a_bisel_lcd(self):
        """Producto P00261 BEZEL PROTECTOR → Bisel LCD (substring BEZEL)."""
        componente = resolver_componente_desde_producto('BEZEL PROTECTOR')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Bisel LCD')

    def test_top_cover_lcd_cover(self):
        """Producto P0025 TOP COVER / LCD COVER → Top Cover (control)."""
        componente = resolver_componente_desde_producto('TOP COVER / LCD COVER')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Top Cover')

    def test_bottom_base_a_bottom_cover(self):
        """Producto P0027 BOTTOM BASE / BASE COVER / LOWER CASE."""
        componente = resolver_componente_desde_producto(
            'BOTTOM BASE / BASE COVER / LOWER CASE'
        )
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Bottom Cover/Case')

    def test_bracket_ssd_no_es_disco_duro(self):
        """Producto P1037 BRACKET SSD → HDD/SSD Bracket (no Disco Duro)."""
        componente = resolver_componente_desde_producto('BRACKET SSD')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'HDD/SSD Bracket')

    def test_usb_32gb_a_memoria_usb(self):
        """Producto P0048 USB 32GB → Memoria USB."""
        componente = resolver_componente_desde_producto('USB 32GB')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Memoria USB')

    def test_usb_kingston_a_memoria_usb(self):
        """Producto P0075 USB KINGSTON 128 GB → Memoria USB."""
        componente = resolver_componente_desde_producto('USB KINGSTON 128 GB')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Memoria USB')

    def test_solucion_oro_a_paquete_oro(self):
        """Producto PQ0101 SOLUCION ORO → Paquete Oro."""
        componente = resolver_componente_desde_producto('SOLUCION ORO')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Paquete Oro')

    def test_lapiz_optico_a_stylus(self):
        """Producto P0113 LAPIZ OPTICO → Stylus."""
        componente = resolver_componente_desde_producto('LAPIZ OPTICO')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Stylus')

    def test_unidad_optica_dvd(self):
        """Producto P0038 UNIDAD ÓPTICA / UNIDAD DE DVD → Unidad optica."""
        componente = resolver_componente_desde_producto(
            'UNIDAD ÓPTICA / UNIDAD DE DVD'
        )
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Unidad optica')

    def test_cable_ac_para_cargador(self):
        """Producto P0120 CABLE AC PARA CARGADOR → Cable de AC (no Cargador)."""
        componente = resolver_componente_desde_producto('CABLE AC PARA CARGADOR')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Cable de AC')

    def test_cargador_sigue_siendo_cargador(self):
        """Control: un cargador real no debe ir a Cable de AC."""
        componente = resolver_componente_desde_producto(
            'CARGADOR / ADAPTADOR 65 W DELL PLUG CHICO'
        )
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Cargador')

    def test_kit_de_limpieza(self):
        """Producto P0186 KIT DE LIMPIEZA → Kit de Limpieza."""
        componente = resolver_componente_desde_producto('KIT DE LIMPIEZA')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Kit de Limpieza')

    def test_limpieza_y_mantenimiento_servicio(self):
        """Servicio LIMPIEZA Y MANTENIMIENTO sigue en Limpieza y mantenimiento."""
        componente = resolver_componente_desde_producto('LIMPIEZA Y MANTENIMIENTO')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Limpieza y mantenimiento')

    def test_pasta_termica(self):
        """Producto P0190 PASTA TERMICA → Pasta termica/Metal liquido."""
        componente = resolver_componente_desde_producto('PASTA TERMICA')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Pasta termica/Metal liquido')

    def test_disipador_sigue_disipador(self):
        """Control: DISIPADOR DE CALOR no debe ir a pasta térmica."""
        componente = resolver_componente_desde_producto(
            'DISIPADOR DE CALOR / HEATSINK'
        )
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Disipador de calor')

    def test_lcd_assembly(self):
        """Producto P0006 LCD ASSEMBLY → LCD Assembly (no Pantalla)."""
        componente = resolver_componente_desde_producto('LCD ASSEMBLY')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'LCD Assembly')

    def test_lcd_display_sigue_pantalla(self):
        """Control: LCD / DISPLAY genérico sigue siendo Pantalla."""
        componente = resolver_componente_desde_producto('LCD / DISPLAY 15.6"')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Pantalla')

    def test_audifonos(self):
        """Producto P0085 AUDÍFONOS → Audifonos."""
        componente = resolver_componente_desde_producto('AUDÍFONOS')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Audifonos')

    def test_backpack(self):
        """Producto P1043 BACKPACK → Backpack Laptop."""
        componente = resolver_componente_desde_producto('BACKPACK')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Backpack Laptop')

    def test_convertidor_hdmi_a_vga(self):
        """Producto P0076 CONVERTIDOR HDMI A VGA → Convertidor de video."""
        componente = resolver_componente_desde_producto('CONVERTIDOR HDMI A VGA')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Convertidor de video')

    def test_hub_type_c(self):
        """Producto P0118 HUB TYPE C → Hub USB."""
        componente = resolver_componente_desde_producto('HUB TYPE C')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Hub USB')

    def test_tapete_antiestatico(self):
        """Producto P0187 TAPETE ANTIESTATICO → Tapete antiestatico."""
        componente = resolver_componente_desde_producto('TAPETE ANTIESTATICO')
        self.assertIsNotNone(componente)
        self.assertEqual(componente.nombre, 'Tapete antiestatico')

    def test_accesorio_sin_mapear_sigue_none(self):
        """Pendientes sin componente ST siguen sin match."""
        for nombre in (
            'FUNDA PARA IPAD / TABLETA',
            'ESPIRAL PROTECTOR CABLE USB COLORES',
            '4H MISSION CRITICAL PROSUPPORT PLUS',
            'LAPTOP',
        ):
            with self.subTest(nombre=nombre):
                self.assertIsNone(resolver_componente_desde_producto(nombre))


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
