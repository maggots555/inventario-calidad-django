"""
Humo Fase A: template detalle_orden partido en {% include %} / partials.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
La Fase A NO cambia Python ni el context de la vista. Solo mueve HTML a
archivos en partials/detalle_orden/ y deja detalle_orden.html como orquestador.

Qué validamos aquí:
1) Existen los 26 partials esperados y el orquestador los incluye.
2) Un GET real a detalle_orden responde 200 y conserva IDs críticos
   (el JS/TS busca esos id en el DOM).
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
from servicio_tecnico.views import detalle_orden


User = get_user_model()

# Rutas de templates (mismo layout que el resto de tests ST).
_TEMPLATES_ST = (
    Path(__file__).resolve().parents[1] / 'templates' / 'servicio_tecnico'
)
_PARTIALS_DIR = _TEMPLATES_ST / 'partials' / 'detalle_orden'
_ORQUESTADOR = _TEMPLATES_ST / 'detalle_orden.html'

# Lista canónica Fase A: si alguien borra un include, este test lo detecta.
_PARTIALS_ESPERADOS = (
    '_header_alertas.html',
    '_seccion_info_config.html',
    '_seccion_reingreso.html',
    '_seccion_cotizacion.html',
    '_seccion_venta_mostrador.html',
    '_seccion_pagos.html',
    '_seccion_estado_responsables.html',
    '_seccion_historial.html',
    '_seccion_galeria_imagenes.html',
    '_seccion_galeria_videos.html',
    '_seccion_video_resumen.html',
    '_modal_editar_info_equipo.html',
    '_modal_pieza.html',
    '_modal_seguimiento.html',
    '_modal_venta_mostrador.html',
    '_modal_pieza_venta_mostrador.html',
    '_modal_enviar_diagnostico.html',
    '_modal_enviar_imagenes.html',
    '_modal_compartir_evidencia.html',
    '_modal_camara_integrada.html',
    '_modal_camara_video.html',
    '_modal_ver_video.html',
    '_modal_confirmacion_salida_camara.html',
    '_modal_confirmar_feedback.html',
    '_modal_confirmar_satisfaccion.html',
    '_modal_confirmar_vigencia_vencida.html',
)

# IDs siempre presentes en un GET de orden diagnóstico “vacía”.
# EXPLICACIÓN: tablaPiezas solo sale si hay cotización; modalConfirmarFeedback
# solo si hay feedback_pendiente_* en sesión — esos se validan en los partials.
_IDS_SIEMPRE_EN_RENDER = (
    'id="modalPieza"',
    'id="modalSeguimiento"',
    'id="formCambioEstado"',
    'id="modalCamaraIntegrada"',
    'id="modalEnviarDiagnostico"',
    'id="modalEnviarImagenesCliente"',
    'id="modalCompartirEvidencia"',
    'id="galeria-videos"',
    'id="seccionPagos"',
)

# IDs condicionales: deben vivir en el markup de los partials (aunque el GET
# mínimo no los renderice).
_IDS_EN_PARTIALS = (
    ('id="tablaPiezas"', '_seccion_cotizacion.html'),
    ('id="modalConfirmarFeedback"', '_modal_confirmar_feedback.html'),
)


class DetalleOrdenPartialsEstructuraTest(SimpleTestCase):
    """
    Sin BD: solo comprueba archivos e includes del orquestador.
    """

    def test_existen_los_partials_y_el_orquestador_los_incluye(self):
        """
        Objetivo: detectar borrados accidentales de partials o includes.

        Args: ninguno (lee el filesystem).
        Efectos: ninguno.
        """
        self.assertTrue(_ORQUESTADOR.is_file())
        self.assertTrue(_PARTIALS_DIR.is_dir())

        orquestador = _ORQUESTADOR.read_text(encoding='utf-8')
        # EXPLICACIÓN: el orquestador debe ser corto; el markup pesado vive abajo.
        self.assertIn("{% include 'servicio_tecnico/partials/detalle_orden/", orquestador)
        self.assertIn('detalle-orden-page', orquestador)
        self.assertIn('{% block extra_js %}', orquestador)

        for nombre in _PARTIALS_ESPERADOS:
            ruta = _PARTIALS_DIR / nombre
            self.assertTrue(ruta.is_file(), f'Falta partial: {nombre}')
            # EXPLICACIÓN: en f-string, `}}` se imprime como un solo `}`.
            include_tag = (
                "{% include 'servicio_tecnico/partials/detalle_orden/"
                f"{nombre}' %}}"
            )
            self.assertIn(
                include_tag,
                orquestador,
                f'El orquestador no incluye {nombre}',
            )

        self.assertEqual(
            orquestador.count("{% include 'servicio_tecnico/partials/detalle_orden/"),
            len(_PARTIALS_ESPERADOS),
            'Cantidad de includes distinta a la lista canónica Fase A',
        )

        # IDs que solo aparecen con cotización / feedback de sesión
        for needle, archivo in _IDS_EN_PARTIALS:
            texto = (_PARTIALS_DIR / archivo).read_text(encoding='utf-8')
            self.assertIn(
                needle,
                texto,
                f'Falta {needle} en partial {archivo}',
            )


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            # EXPLICACIÓN: en tests no hay collectstatic/manifest; sin esto
            # falla {% static 'js/jpeg_encode_worker.js' %} del modal cámara.
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class DetalleOrdenPartialsRenderTest(TestCase):
    """
    Integración ligera: GET a detalle_orden con orden mínima.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Si un {% include %} apunta mal o un {% load %} falta en un partial,
    Django revienta al renderizar. Este test atrapa ese error.

    Usamos RequestFactory (no Client) para no pasar por
    ForcePasswordChangeMiddleware / PaisMiddleware en tests multi-BD.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Partials Fase A',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_partials_fase_a',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Usuario Partials Fase A',
            cargo='Técnico',
            area='Laboratorio',
            email='partials.fase.a@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            # Evita redirección si algún día se usa Client en este test.
            contraseña_configurada=True,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        perm = Permission.objects.get(
            content_type=ct,
            codename='view_ordenservicio',
        )
        self.user.user_permissions.add(perm)

        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-PARTIALS-FASE-A',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-PARTIALS-FASE-A',
            email_cliente='cliente.partials@test.local',
            nombre_cliente='Cliente Partials',
            falla_principal='No enciende',
        )
        self.url = reverse(
            'servicio_tecnico:detalle_orden',
            args=[self.orden.pk],
        )

    def _get_detalle(self):
        """
        Arma un GET autenticado con soporte de messages y session.

        Returns:
            HttpResponse del render de detalle_orden.
        """
        request = self.factory.get(self.url)
        request.user = self.user
        # La vista hace request.session.pop(...) para feedback; session vacía basta.
        setattr(request, 'session', {})
        messages_storage = FallbackStorage(request)
        setattr(request, '_messages', messages_storage)
        return detalle_orden(request, orden_id=self.orden.pk)

    def test_get_renderiza_200_con_ids_criticos(self):
        """
        GET autenticado: 200 + IDs que el JS necesita.

        Efectos: crea datos de prueba en BD de test (TestCase los limpia).
        """
        response = self._get_detalle()

        self.assertEqual(
            response.status_code,
            200,
            f'Render falló: status={response.status_code}',
        )
        # TemplateResponse puede diferir el render; forzamos el HTML.
        html = response.content.decode('utf-8')
        self.assertIn('detalle-orden-page', html)
        self.assertIn(self.orden.numero_orden_interno, html)

        for needle in _IDS_SIEMPRE_EN_RENDER:
            self.assertIn(
                needle,
                html,
                f'Falta ID crítico en HTML renderizado: {needle}',
            )
