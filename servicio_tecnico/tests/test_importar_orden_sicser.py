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
