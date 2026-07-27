"""
Tests de importar_orden_sicser: redirect con query string y errores de negocio.

EXPLICACIÓN PARA PRINCIPIANTES:
En producción el 500 no venía del «ya existe la orden», sino de armar mal el
redirect: concatenar '?tab=garantia' al *nombre* de la vista. Django intenta
hacer reverse de ese string y falla (NoReverseMatch). Estos tests cubren eso.
"""

from unittest.mock import MagicMock, patch

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico import views_sicser
from servicio_tecnico.models import DetalleEquipo, OrdenServicio
from servicio_tecnico.sicser_import import (
    SicserImportError,
    importar_orden_garantia_desde_sicser,
)


def _request_con_mensajes(factory, path, user, data):
    """
    Arma un POST con sesión y messages (requeridos por la vista).

    Args:
        factory: RequestFactory de Django.
        path: URL relativa del endpoint.
        user: Usuario autenticado.
        data: Dict del body POST.

    Returns:
        HttpRequest listo para pasar a la vista.
    """
    request = factory.post(path, data)
    request.user = user
    # Paso 1: sesión (messages la necesita por debajo)
    SessionMiddleware(lambda r: None).process_request(request)
    request.session.save()
    # Paso 2: almacén de mensajes en memoria (sin cookies reales)
    setattr(request, '_messages', FallbackStorage(request))
    return request


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class ImportarOrdenSicserRedirectTest(TestCase):
    """
    El error de negocio debe redirigir al listado con ?tab=…, sin 500.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        """
        Usuario con permiso add_ordenservicio + sucursal mínima.

        Efectos secundarios: crea User, Permission, Sucursal y Empleado en BD test.
        """
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Import SICSER',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='import_sicser',
            password='testpass123',
        )
        Empleado.objects.create(
            nombre_completo='Importador SICSER',
            cargo='Técnico',
            area='Laboratorio',
            email='import.sicser@test.local',
            sucursal=self.sucursal,
            user=self.user,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        perm = Permission.objects.get(
            content_type=ct,
            codename='add_ordenservicio',
        )
        self.user.user_permissions.add(perm)
        self.url = reverse('servicio_tecnico:importar_orden_sicser')
        self.listado = reverse('servicio_tecnico:consultar_sicser')

    def test_datos_invalidos_redirige_con_query_tab(self):
        """
        POST incompleto → redirect a consultar_sicser?tab=garantia (URL real).

        Antes del fix, redirect('…consultar_sicser?tab=garantia') lanzaba
        NoReverseMatch porque Django trataba todo el string como nombre de vista.
        """
        request = _request_con_mensajes(
            self.factory,
            self.url,
            self.user,
            {
                'tipo': 'garantia',
                # Sin id_externo → rama de datos incompletos
                'tab': 'garantia',
                'q': 'Dell',
            },
        )
        response = views_sicser.importar_orden_sicser(request)
        self.assertEqual(response.status_code, 302)
        # Debe ser URL resuelta + query, no el nombre de la vista
        self.assertEqual(
            response.url,
            f'{self.listado}?tab=garantia&q=Dell',
        )

    @patch('servicio_tecnico.sicser_client.buscar_registro_garantia_por_dps')
    @patch('servicio_tecnico.sicser_import.importar_orden_garantia_desde_sicser')
    def test_sicser_import_error_redirige_sin_no_reverse_match(
        self,
        mock_importar,
        mock_buscar,
    ):
        """
        Si la importación falla por negocio (duplicado), no hay 500:
        mensaje de error + redirect al listado con la pestaña correcta.
        """
        # Simula que SICSER sí devolvió un registro
        mock_buscar.return_value = MagicMock()
        # Simula el error que viste en producción (orden ya existente)
        mock_importar.side_effect = SicserImportError(
            'Ya existe una orden con número de cliente "467801924" en SIGMA.'
        )

        request = _request_con_mensajes(
            self.factory,
            self.url,
            self.user,
            {
                'tipo': 'garantia',
                'id_externo': '467801924',
                'tab': 'garantia',
            },
        )
        response = views_sicser.importar_orden_sicser(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f'{self.listado}?tab=garantia')


class ImportarGarantiaDuplicadoMensajeTest(TestCase):
    """
    El mensaje de conflicto por orden_cliente incluye el folio interno SIGMA.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        """Crea una orden ya existente con orden_cliente = DPS de prueba."""
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Dup Garantía',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='dup_garantia',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Dup Garantía',
            cargo='Técnico',
            area='Laboratorio',
            email='dup.garantia@test.local',
            sucursal=self.sucursal,
            user=self.user,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='467801924',
            sicser_origen='garantia',
            sicser_id_externo='999999999',  # otro id externo: conflicto por orden_cliente
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='STEXISTENTE',
            email_cliente='a@b.com',
            falla_principal='No enciende',
            gama='media',
        )

    def test_mensaje_incluye_numero_orden_interno(self):
        """
        Al chocar por orden_cliente, el error menciona el folio interno.

        Así en producción el usuario sabe qué orden abrir (no solo el DPS).
        """
        registro = MagicMock()
        registro.numero_dps = 467801924
        registro.service_tag = 'OTROSTAG'
        registro.especificaciones = 'Latitude'
        registro.email_contacto = 'x@y.com'
        registro.contacto = 'Cliente'
        registro.empresa = 'Empresa'
        registro.codigo_cis_url = 'SAT'
        registro.ciudad = 'CDMX'
        registro.estado = 'CDMX'
        registro.fecha_recepcion = None

        with self.assertRaises(SicserImportError) as ctx:
            importar_orden_garantia_desde_sicser(registro, self.user)

        mensaje = str(ctx.exception)
        self.assertIn('467801924', mensaje)
        self.assertIn(self.orden.numero_orden_interno, mensaje)


class FechaImportacionSicserTest(TestCase):
    """
    fecha_importacion_sicser = momento del click Importar en SIGMA.

    EXPLICACIÓN PARA PRINCIPIANTES:
    fecha_ingreso puede ser la fecha antigua de SICSER. La pestaña «Hoy»
    solo debe mirar fecha_importacion_sicser.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        """Sucursal + usuario técnico mínimos para crear órdenes de prueba."""
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Fecha Import SICSER',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='fecha_import_sicser',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Fecha Import SICSER',
            cargo='Técnico',
            area='Laboratorio',
            email='fecha.import@test.local',
            sucursal=self.sucursal,
            user=self.user,
        )

    def _crear_detalle_importado(
        self,
        *,
        id_externo: str,
        orden_cliente: str,
        fecha_ingreso,
        fecha_importacion,
    ):
        """
        Crea una orden + detalle con origen SICSER y fechas controladas.

        Args:
            id_externo: sicser_id_externo único.
            orden_cliente: Número de cliente SIGMA.
            fecha_ingreso: Fecha de recepción / SICSER en la orden.
            fecha_importacion: Momento de importación a SIGMA (o None).

        Returns:
            DetalleEquipo: Registro creado.
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            tecnico_asignado_actual=self.empleado,
            fecha_ingreso=fecha_ingreso,
        )
        return DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente=orden_cliente,
            sicser_origen='garantia',
            sicser_id_externo=id_externo,
            folio_sicser=id_externo,
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie=f'ST{id_externo}'[:20],
            email_cliente='a@b.com',
            falla_principal='Prueba fecha importación',
            gama='media',
            fecha_importacion_sicser=fecha_importacion,
        )

    def test_importar_garantia_llena_fecha_importacion_sicser(self):
        """
        Al importar, se guarda timezone.now() aunque fecha_ingreso sea antigua.
        """
        from datetime import timedelta

        from django.utils import timezone

        from servicio_tecnico.sicser_import import importar_orden_garantia_desde_sicser

        # Fecha SICSER = hace 3 días (no debe confundirse con la de importación)
        hace_tres_dias = timezone.now() - timedelta(days=3)
        registro = MagicMock()
        registro.numero_dps = 555001001
        registro.service_tag = 'STHOY001'
        registro.especificaciones = 'Latitude 5420'
        registro.email_contacto = 'cli@test.local'
        registro.contacto = 'Cliente Hoy'
        registro.empresa = 'Empresa'
        registro.codigo_cis_url = 'SAT'
        registro.ciudad = 'CDMX'
        registro.estado = 'CDMX'
        registro.telefono = '5551234567'
        registro.direccion = ''
        registro.instrucciones_dell = 'No enciende'
        registro.nombre_grupo = 'CIS'
        registro.fecha_recepcion = hace_tres_dias.strftime('%Y-%m-%d %H:%M:%S')

        antes = timezone.now()
        resultado = importar_orden_garantia_desde_sicser(registro, self.user)
        despues = timezone.now()

        detalle = resultado.orden.detalle_equipo
        self.assertIsNotNone(detalle.fecha_importacion_sicser)
        self.assertGreaterEqual(detalle.fecha_importacion_sicser, antes)
        self.assertLessEqual(detalle.fecha_importacion_sicser, despues)
        # La fecha de ingreso debe seguir siendo la de SICSER (ayer/hace días)
        self.assertEqual(detalle.orden.fecha_ingreso.date(), hace_tres_dias.date())

    def test_listar_solo_hoy_usa_fecha_importacion_no_ingreso(self):
        """
        Ingreso ayer + importación hoy → aparece en solo_hoy.
        Importación ayer → no aparece en solo_hoy; sí en histórico.
        Sin fecha_importacion → solo histórico.
        """
        from datetime import timedelta

        from django.utils import timezone

        from servicio_tecnico.sicser_import import (
            contar_ordenes_importadas_sicser,
            listar_ordenes_importadas_sicser,
        )

        ahora = timezone.now()
        ayer = ahora - timedelta(days=1)

        # Caso A: fecha_ingreso antigua, importada hoy → SÍ en Hoy
        self._crear_detalle_importado(
            id_externo='1001',
            orden_cliente='1001',
            fecha_ingreso=ayer,
            fecha_importacion=ahora,
        )
        # Caso B: importada ayer → NO en Hoy
        self._crear_detalle_importado(
            id_externo='1002',
            orden_cliente='1002',
            fecha_ingreso=ayer,
            fecha_importacion=ayer,
        )
        # Caso C: registro viejo sin fecha_importacion → NO en Hoy
        self._crear_detalle_importado(
            id_externo='1003',
            orden_cliente='1003',
            fecha_ingreso=ayer,
            fecha_importacion=None,
        )

        ids_hoy = {
            f['sicser_id_externo']
            for f in listar_ordenes_importadas_sicser(solo_hoy=True)
        }
        ids_historico = {
            f['sicser_id_externo']
            for f in listar_ordenes_importadas_sicser(solo_hoy=False)
        }

        self.assertEqual(ids_hoy, {'1001'})
        self.assertEqual(ids_historico, {'1001', '1002', '1003'})
        self.assertEqual(contar_ordenes_importadas_sicser(solo_hoy=True), 1)
        self.assertEqual(contar_ordenes_importadas_sicser(solo_hoy=False), 3)


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class ConsultarSicserPestanasImportadasTest(TestCase):
    """Humo HTTP de las pestañas importadas_hoy e importadas."""

    databases = {'default', 'mexico'}

    def setUp(self):
        """Usuario con permiso de ver órdenes + RequestFactory (sin middleware)."""
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Tabs SICSER',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='tabs_sicser',
            password='testpass123',
        )
        Empleado.objects.create(
            nombre_completo='Tabs SICSER',
            cargo='Técnico',
            area='Laboratorio',
            email='tabs.sicser@test.local',
            sucursal=self.sucursal,
            user=self.user,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        perm = Permission.objects.get(
            content_type=ct,
            codename='view_ordenservicio',
        )
        self.user.user_permissions.add(perm)
        self.listado = reverse('servicio_tecnico:consultar_sicser')

    @patch('servicio_tecnico.sicser_client.fetch_listado_garantias')
    @patch('servicio_tecnico.sicser_client.fetch_listado_oow')
    def test_tabs_importadas_hoy_e_historico_responden_200(
        self,
        mock_oow,
        mock_garantia,
    ):
        """
        Ambas pestañas locales responden 200 sin depender de la API real.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Usamos RequestFactory (no Client) para no pasar por middleware que
        redirige (cambio de contraseña, etc.) y solo probar la vista.
        """
        mock_oow.return_value = ([], 0)
        mock_garantia.return_value = ([], 0)

        for tab in ('importadas_hoy', 'importadas'):
            with self.subTest(tab=tab):
                request = self.factory.get(self.listado, {'tab': tab})
                request.user = self.user
                response = views_sicser.consultar_sicser(request)
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                # Marcas de ambas pestañas en el nav
                self.assertIn('tab=importadas_hoy', html)
                self.assertIn('Histórico importadas', html)
                if tab == 'importadas_hoy':
                    self.assertIn('Órdenes importadas a SIGMA hoy', html)
                else:
                    self.assertIn('Histórico de órdenes importadas a SIGMA', html)
