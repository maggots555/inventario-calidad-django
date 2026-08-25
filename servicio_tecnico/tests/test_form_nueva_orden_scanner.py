"""
Humo: scanner QR/Data Matrix en formularios de crear orden (OOW y FL).

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
Validamos que los templates de alta de orden incluyen los botones de cámara,
scripts del scanner y que el botón del cargador inicia deshabilitado.
No probamos la cámara real (getUserMedia) — eso es manual en navegador.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import OrdenServicio
from servicio_tecnico.views_ordenes import crear_orden, crear_orden_venta_mostrador


User = get_user_model()


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class FormNuevaOrdenScannerRenderTest(TestCase):
    """GET a crear_orden y crear_orden_venta_mostrador incluye assets del scanner."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Scanner Crear',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_scanner_crear',
            password='testpass123',
        )
        Empleado.objects.create(
            nombre_completo='Usuario Scanner Crear',
            cargo='Recepción',
            area='Mostrador',
            email='scanner.crear@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='recepcion',
            contraseña_configurada=True,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        self.user.user_permissions.add(
            Permission.objects.get(content_type=ct, codename='add_ordenservicio'),
        )

    def _get_html(self, vista, url_name: str) -> str:
        """GET autenticado a la vista de crear orden y devuelve HTML."""
        request = self.factory.get(reverse(url_name))
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        response = vista(request)
        self.assertEqual(response.status_code, 200)
        return response.content.decode('utf-8')

    def _assert_scanner_en_html(self, html: str) -> None:
        """Asserts comunes para ambos formularios de crear orden."""
        self.assertIn('btnEscanearNumeroSerieCrear', html)
        self.assertIn('btnEscanearCargadorCrear', html)
        self.assertIn('scanner_codigo.js', html)
        self.assertIn('scanner_enlace.js', html)
        self.assertIn('form_nueva_orden_scanner.js', html)
        self.assertIn('zxing-wasm@3.1.2', html)
        self.assertIn('btn-scanner-codigo-inline', html)
        # Botón cargador debe iniciar disabled (checkbox apagado al cargar)
        self.assertRegex(html, r'id="btnEscanearCargadorCrear"[^>]*\bdisabled\b')

    def test_crear_orden_oow_incluye_scanner(self):
        """Formulario OOW renderiza botones y scripts del scanner."""
        html = self._get_html(crear_orden, 'servicio_tecnico:crear_orden')
        self._assert_scanner_en_html(html)
        self.assertIn('formNuevaOrden', html)

    def test_crear_orden_venta_mostrador_incluye_scanner(self):
        """Formulario Venta Mostrador (FL) renderiza botones y scripts del scanner."""
        html = self._get_html(
            crear_orden_venta_mostrador,
            'servicio_tecnico:crear_orden_venta_mostrador',
        )
        self._assert_scanner_en_html(html)
        self.assertIn('formNuevaOrdenVentaMostrador', html)
