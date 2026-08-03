"""
Humo Fase C: dispatcher detalle_orden + context service + assets TS.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Tras partir handlers y sacar el JS inline a TypeScript, validamos:
1) El dispatcher conoce los form_type y apunta a callables reales.
2) build_detalle_orden_context expone claves críticas del template.
3) Existen los .ts / .js compilados de la página (no se edita static/js a mano).

Integración de negocio (POST cotización/rechazo): ver
test_detalle_orden_cotizacion_integracion.py
"""

from pathlib import Path

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, OrdenServicio
from servicio_tecnico.services.detalle_orden_context import build_detalle_orden_context
from servicio_tecnico.views_detalle_orden import _FORM_TYPE_HANDLERS, detalle_orden


User = get_user_model()

_ROOT = Path(__file__).resolve().parents[2]
_TS_DIR = _ROOT / 'static' / 'ts'
_JS_DIR = _ROOT / 'static' / 'js'

_ASSETS = (
    'detalle_orden_page',
    'detalle_orden_enviar_imagenes',
    'detalle_orden_ver_video',
    'detalle_orden_fabs',
)


class DetalleOrdenFaseCDispatcherTest(SimpleTestCase):
    """Sin BD: mapa form_type → handler."""

    def test_form_types_criticos_registrados(self):
        """
        Objetivo: si alguien borra una clave del dispatcher, el POST se ignora.

        Efectos: ninguno.
        """
        esperados = {
            'configuracion',
            'reingreso_rhitso',
            'cambio_estado',
            'asignar_responsables',
            'comentario',
            'subir_imagenes',
            'subir_video',
            'editar_info_equipo',
            'guardar_mano_obra',
            'crear_cotizacion',
            'generar_cotizacion',
            'editar_fecha_envio',
            'editar_mano_obra',
            'gestionar_cotizacion',
        }
        self.assertEqual(set(_FORM_TYPE_HANDLERS.keys()), esperados)
        for nombre, handler in _FORM_TYPE_HANDLERS.items():
            with self.subTest(form_type=nombre):
                self.assertTrue(callable(handler))

    def test_multimedia_tiene_imports_criticos(self):
        """
        Regresión NameError al subir imágenes/video.

        EXPLICACIÓN PARA PRINCIPIANTES:
        En el monolito HistorialOrden / ESTADO_ORDEN_CHOICES / settings
        venían del import global. Al mover el handler a
        views_detalle_orden_multimedia.py deben vivir ahí; si faltan,
        el usuario ve "Error inesperado al procesar imágenes: name 'X'...".
        """
        from servicio_tecnico import views_detalle_orden_multimedia as multimedia

        for nombre in (
            'HistorialOrden',
            'ESTADO_ORDEN_CHOICES',
            'settings',
            'comprimir_y_guardar_imagen',
            'SubirImagenesForm',
            'SubirVideoForm',
            'JsonResponse',
        ):
            with self.subTest(nombre=nombre):
                self.assertTrue(
                    hasattr(multimedia, nombre),
                    msg=f'Falta {nombre} en views_detalle_orden_multimedia',
                )


class DetalleOrdenFaseCAssetsTest(SimpleTestCase):
    """Fuente TS + JS compilado presentes."""

    def test_existen_ts_y_js_compilados(self):
        """
        EXPLICACIÓN: el template carga static/js/*.js; la fuente es static/ts/.
        """
        for stem in _ASSETS:
            ts = _TS_DIR / f'{stem}.ts'
            js = _JS_DIR / f'{stem}.js'
            self.assertTrue(ts.is_file(), f'Falta fuente {ts.name}')
            self.assertTrue(js.is_file(), f'Falta compilado {js.name} (¿pnpm run build?)')

    def test_modal_email_invalido_no_usa_helpers_privados_en_onclick(self):
        """
        Regresión IIFE: onclick="_qs(...)" / "_el(...)" rompe en el navegador
        porque esos helpers no están en window.
        """
        fuente = (_TS_DIR / 'detalle_orden_page.ts').read_text(encoding='utf-8')
        compilado = (_JS_DIR / 'detalle_orden_page.js').read_text(encoding='utf-8')
        # Patrón exacto del bug (atributo del botón), no el comentario didáctico.
        patron_roto = 'onclick="_qs(\'[data-bs-target'
        for blob in (fuente, compilado):
            self.assertNotIn(patron_roto, blob)
        self.assertIn('btnEditarInfoDesdeEmailInvalido', fuente)
        self.assertIn('btnEditarInfoDesdeEmailInvalido', compilado)


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class DetalleOrdenFaseCContextTest(TestCase):
    """Context GET + script de config en el HTML renderizado."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Fase C',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_fase_c',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Usuario Fase C',
            cargo='Técnico',
            area='Laboratorio',
            email='fase.c@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            contraseña_configurada=True,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        self.user.user_permissions.add(
            Permission.objects.get(content_type=ct, codename='view_ordenservicio'),
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-FASE-C',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-FASE-C',
            email_cliente='cliente.fase.c@test.local',
            nombre_cliente='Cliente Fase C',
            falla_principal='No enciende',
        )

    def test_context_tiene_claves_criticas(self):
        """
        build_detalle_orden_context debe devolver lo que el template espera.
        """
        request = self.factory.get('/')
        request.user = self.user
        request.session = {}
        ctx = build_detalle_orden_context(request, self.orden)
        for clave in (
            'orden',
            'detalle',
            'form_estado',
            'form_pieza',
            'estadisticas_tecnicos',
            'componentes_diagnostico_orden',
            'es_orden_diagnostico',
            'ollama_enabled',
        ):
            with self.subTest(clave=clave):
                self.assertIn(clave, ctx)

    def test_render_incluye_config_json_y_scripts_fase_c(self):
        """GET renderiza el JSON de config y los script src nuevos."""
        request = self.factory.get(
            reverse('servicio_tecnico:detalle_orden', args=[self.orden.pk]),
        )
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)
        response = detalle_orden(request, orden_id=self.orden.pk)
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('id="detalle-orden-page-config"', html)
        self.assertIn('detalle_orden_page.js', html)
        self.assertIn('detalle_orden_enviar_imagenes.js', html)
        self.assertIn('detalle_orden_ver_video.js', html)
        self.assertIn('detalle_orden_fabs.js', html)
