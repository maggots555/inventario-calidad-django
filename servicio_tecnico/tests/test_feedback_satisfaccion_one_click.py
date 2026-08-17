"""
Tests One-Click Survey: estrellas del correo prellenan el formulario.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El correo no puede ejecutar JavaScript. Cada estrella es un enlace
?estrellas=1 … 5. Al abrir el GET, Django pone esa calificación en el
formulario; NO la guarda hasta el POST (Gmail/Outlook pueden “cliclear”
el enlace al escanear el mail).

Usamos RequestFactory (no Client) para no pelear con Axes / PaisMiddleware.
"""

from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, FeedbackCliente, OrdenServicio
from servicio_tecnico.views_seguimiento_cliente import (
    _estrellas_preseleccionadas_desde_query,
    feedback_satisfaccion_cliente,
)

User = get_user_model()


class EmailOneClickSurveyTemplateTest(SimpleTestCase):
    """
    Objetivo: el HTML del correo incluye 5 enlaces de estrellas y el CTA de respaldo.

    Efectos secundarios: ninguno (solo renderiza template, sin BD).
    """

    def test_email_incluye_enlaces_estrellas_y_cta_respaldo(self):
        """Cada estrella apunta a ?estrellas=N; el botón de respaldo sigue al form."""
        url_base = 'https://example.test/feedback-satisfaccion/token-demo/'
        html = render_to_string(
            'servicio_tecnico/emails/feedback_satisfaccion.html',
            {
                'folio': 'ORD-TEST-0001',
                'marca_equipo': 'Dell',
                'modelo_equipo': 'Latitude',
                'tipo_equipo': 'Laptop',
                'fecha_entrega': '14/08/2026',
                'feedback_url': url_base,
                'dias_vigencia': 12,
                'fecha_envio': '14/08/2026',
            },
        )
        # EXPLICACIÓN: el cliente toca la estrella N y cae en el form con ese valor.
        for n in range(1, 6):
            self.assertIn(f'{url_base}?estrellas={n}', html)
        self.assertIn('O completa la encuesta aquí', html)
        self.assertIn(url_base, html)
        # Footer: mismo contenido, diseño estándar (pills + empresa + fecha).
        self.assertIn('SIC - Comercialización y Servicios', html)
        self.assertIn('Visítanos y síguenos en nuestras redes sociales', html)
        self.assertIn('Este correo fue enviado el 14/08/2026', html)
        self.assertIn('https://instagram.com/sicfix.mx', html)
        self.assertIn('https://wa.me/523318189988', html)


class EstrellasQueryHelperTest(SimpleTestCase):
    """
    Objetivo: el helper solo acepta enteros 1–5; el resto se ignora.

    Efectos secundarios: ninguno.
    """

    def setUp(self):
        self.factory = RequestFactory()

    def test_valores_validos_uno_a_cinco(self):
        """1 a 5 se convierten a int; son las únicas calificaciones del form."""
        for n in (1, 2, 3, 4, 5):
            request = self.factory.get('/', {'estrellas': str(n)})
            self.assertEqual(_estrellas_preseleccionadas_desde_query(request), n)

    def test_valores_invalidos_se_ignoran(self):
        """Fuera de rango, texto o ausente → None (form vacío, no error)."""
        casos = [
            {},
            {'estrellas': '99'},
            {'estrellas': '0'},
            {'estrellas': 'abc'},
            {'estrellas': ''},
            {'estrellas': '-1'},
        ]
        for query in casos:
            with self.subTest(query=query):
                request = self.factory.get('/', query)
                self.assertIsNone(_estrellas_preseleccionadas_desde_query(request))


@override_settings(
    RATELIMIT_ENABLE=False,
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class FeedbackSatisfaccionOneClickVistaTest(TestCase):
    """
    Objetivo: GET ?estrellas= prellena el form sin consumir el token;
    POST completo sí guarda y marca utilizado=True.

    Efectos secundarios: crea sucursal, orden, detalle y FeedbackCliente de prueba.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal One-Click Survey',
            ciudad='CDMX',
        )
        # tecnico_asignado_actual es NOT NULL en OrdenServicio.
        self.user = User.objects.create_user(
            username='tec_oneclick',
            password='testpass123',
        )
        self.tecnico = Empleado.objects.create(
            nombre_completo='Técnico One Click',
            cargo='Técnico',
            area='Laboratorio',
            email='tec.oneclick@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='entregado',
            tecnico_asignado_actual=self.tecnico,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-ONECLICK-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude 5420',
            numero_serie='SN-ONECLICK-01',
            email_cliente='cliente.oneclick@test.local',
            nombre_cliente='Cliente One Click',
            falla_principal='No enciende',
        )
        self.token = 'token-one-click-survey-test-abc123'
        self.feedback = FeedbackCliente.objects.create(
            orden=self.orden,
            token=self.token,
            tipo='satisfaccion',
            utilizado=False,
        )
        self.path = reverse(
            'feedback_satisfaccion_publico',
            kwargs={'token': self.token},
        )

    def _get(self, query=None):
        """Arma un GET público listo para llamar la vista."""
        request = self.factory.get(self.path, data=query or {})
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        return feedback_satisfaccion_cliente(request, token=self.token)

    def _post(self, data):
        """Arma un POST público (RequestFactory no pasa por CSRF middleware)."""
        request = self.factory.post(self.path, data=data)
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        return feedback_satisfaccion_cliente(request, token=self.token)

    def test_get_estrellas_5_prellena_y_no_consume_token(self):
        """Feliz: clic en 5 estrellas del mail abre el form con value=5."""
        response = self._get({'estrellas': '5'})
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="feedbackForm"', html)
        self.assertIn('id="id_calificacion_general"', html)
        self.assertIn('value="5"', html)

        self.feedback.refresh_from_db()
        self.assertFalse(self.feedback.utilizado)
        self.assertIsNone(self.feedback.calificacion_general)

    def test_get_estrellas_invalida_no_prellena(self):
        """Borde: 99 o texto se ignoran; el form queda sin calificación."""
        for crudo in ('99', 'abc'):
            with self.subTest(estrellas=crudo):
                response = self._get({'estrellas': crudo})
                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn('id="feedbackForm"', html)
                # Sin initial, Django no pone value en el hidden de calificación.
                self.assertNotRegex(
                    html,
                    r'id="id_calificacion_general"[^>]*value="\d+"',
                )
                self.feedback.refresh_from_db()
                self.assertFalse(self.feedback.utilizado)

    def test_get_sin_query_igual_que_hoy(self):
        """Sin ?estrellas= el formulario aparece vacío y el token sigue vivo."""
        response = self._get()
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('id="feedbackForm"', html)
        self.assertNotRegex(
            html,
            r'id="id_calificacion_general"[^>]*value="\d+"',
        )
        self.feedback.refresh_from_db()
        self.assertFalse(self.feedback.utilizado)

    def test_get_ya_no_pide_pulgares(self):
        """La encuesta ya no muestra la pregunta binaria de recomendar."""
        response = self._get()
        html = response.content.decode()
        self.assertIn('id="feedbackForm"', html)
        self.assertNotIn('section-recomienda', html)
        self.assertNotIn('id_recomienda', html)
        self.assertNotIn('¿Recomendarías nuestro servicio?', html)

    def test_post_completo_guarda_y_marca_utilizado(self):
        """El voto real ocurre en el POST (estrellas + NPS). recomienda se deriva."""
        response = self._post({
            'calificacion_general': '4',
            'nps': '9',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('gracias', response.content.decode().lower())

        self.feedback.refresh_from_db()
        self.assertTrue(self.feedback.utilizado)
        self.assertEqual(self.feedback.calificacion_general, 4)
        self.assertEqual(self.feedback.nps, 9)
        # NPS 9 = promotor → Django marca recomienda=True sin preguntar pulgares.
        self.assertTrue(self.feedback.recomienda)

    def test_post_nps_detractor_deriva_no_recomienda(self):
        """NPS 0–6 (detractor) se guarda como recomienda=False."""
        response = self._post({
            'calificacion_general': '2',
            'nps': '6',
        })
        self.assertEqual(response.status_code, 200)
        self.feedback.refresh_from_db()
        self.assertTrue(self.feedback.utilizado)
        self.assertEqual(self.feedback.nps, 6)
        self.assertFalse(self.feedback.recomienda)
