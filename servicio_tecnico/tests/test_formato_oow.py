"""
Tests del Formato Digital OOW.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cubren: reexports/URLs, crear borrador, finalizar+PDF, y que el wizard
responde 200 para una orden de diagnóstico.
"""

from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse
from PIL import Image

from inventario.models import Empleado, Sucursal
from servicio_tecnico import views as st_views
from servicio_tecnico import views_formato_oow
from servicio_tecnico.models import DetalleEquipo, FormatoServicioOOW, OrdenServicio
from servicio_tecnico.services.formato_oow import (
    FormatoOOWError,
    aplicar_payload_borrador,
    finalizar_formato,
    lista_emails_envio,
    normalizar_emails_envio,
    obtener_o_crear_borrador,
    orden_es_candidata_formato_oow,
)


User = get_user_model()


def _png_bytes(color=(0, 51, 102)) -> bytes:
    """Genera un PNG mínimo en memoria para firmas de prueba."""
    buf = BytesIO()
    Image.new('RGB', (120, 40), color=color).save(buf, format='PNG')
    return buf.getvalue()


class FormatoOowReexportsTest(SimpleTestCase):
    """Humo: views.py reexporta y las URLs resuelven al módulo nuevo."""

    def test_reexports_y_urls(self):
        self.assertIs(st_views.formato_oow_wizard, views_formato_oow.formato_oow_wizard)
        self.assertIs(st_views.formato_oow_guardar, views_formato_oow.formato_oow_guardar)
        self.assertIs(st_views.formato_oow_finalizar, views_formato_oow.formato_oow_finalizar)
        self.assertIs(st_views.formato_oow_reenviar_email, views_formato_oow.formato_oow_reenviar_email)
        self.assertIs(st_views.formato_oow_pdf, views_formato_oow.formato_oow_pdf)
        self.assertIs(
            st_views.abrir_formato_oow_desde_sicser,
            views_formato_oow.abrir_formato_oow_desde_sicser,
        )

        match = resolve(reverse('servicio_tecnico:formato_oow_wizard', args=[1]))
        self.assertIs(match.func, views_formato_oow.formato_oow_wizard)

        match_reenviar = resolve(
            reverse('servicio_tecnico:formato_oow_reenviar_email', args=[1])
        )
        self.assertIs(match_reenviar.func, views_formato_oow.formato_oow_reenviar_email)

        match_abrir = resolve(reverse('servicio_tecnico:abrir_formato_oow_desde_sicser'))
        self.assertIs(match_abrir.func, views_formato_oow.abrir_formato_oow_desde_sicser)


class FormatoOowServiceTest(TestCase):
    """Pruebas de negocio: borrador, candidata OOW y finalizar con PDF."""

    # get_pais_actual / storage pueden tocar el alias mexico en tests
    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Test Formato OOW',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='tecnico_oow',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico OOW',
            cargo='Técnico',
            area='Laboratorio',
            email='tecnico.oow@test.local',
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
            orden_cliente='OOW-99999',
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='Latitude 3520',
            numero_serie='TESTSTAG01',
            email_cliente='cliente@test.local',
            nombre_cliente='Cliente Prueba',
            falla_principal='Bisagras dañadas',
            gama='media',
            tiene_cargador=True,
        )

    def test_orden_es_candidata_oow(self):
        self.assertTrue(orden_es_candidata_formato_oow(self.orden))

    def test_obtener_o_crear_borrador_prefill(self):
        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        self.assertEqual(formato.estado, 'borrador')
        self.assertTrue(formato.accesorio_cargador)
        self.assertEqual(formato.email_envio, 'cliente@test.local')
        self.assertEqual(lista_emails_envio(formato), ['cliente@test.local'])
        mismo = obtener_o_crear_borrador(self.orden, usuario=self.user)
        self.assertEqual(formato.pk, mismo.pk)

    def test_guardar_hasta_tres_emails(self):
        """
        Se pueden guardar hasta 3 correos; el primero sincroniza email_envio.
        """
        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        aplicar_payload_borrador(
            formato,
            {
                'emails_envio': [
                    'uno@test.local',
                    'dos@test.local',
                    'tres@test.local',
                    'cuarto-ignorado@test.local',
                ],
            },
            usuario=self.user,
        )
        formato.refresh_from_db()
        self.assertEqual(
            lista_emails_envio(formato),
            ['uno@test.local', 'dos@test.local', 'tres@test.local'],
        )
        self.assertEqual(formato.email_envio, 'uno@test.local')
        # Duplicados y vacíos se limpian
        self.assertEqual(
            normalizar_emails_envio(['A@x.com', '', 'a@x.com', 'b@y.com']),
            ['A@x.com', 'b@y.com'],
        )

    def test_finalizar_genera_pdf(self):
        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        aplicar_payload_borrador(
            formato,
            {
                'acepta_condiciones': True,
                'acepta_privacidad': True,
                'observaciones_tecnicas': 'Rayones leves en top cover',
            },
            usuario=self.user,
        )
        formato.refresh_from_db()
        formato.firma_cliente.save(
            'firma_cli.png',
            ContentFile(_png_bytes()),
            save=True,
        )

        final = finalizar_formato(formato, usuario=self.user)
        self.assertEqual(final.estado, 'finalizado')
        self.assertTrue(final.pdf)
        self.assertTrue(final.pdf.size > 100)
        self.assertTrue(final.version_aviso_privacidad)

    def test_pdf_muestra_accesorios_marcados(self):
        """
        Los checkboxes se guardan y el PDF se regenera sin fallar.
        (Antes usaba ☑/☐ que Helvetica no dibuja; ahora SI/NO en tabla.)
        """
        from servicio_tecnico.utils.pdf_formato_oow import PDFFormatoServicioOOW

        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        aplicar_payload_borrador(
            formato,
            {
                'acepta_condiciones': True,
                'acepta_privacidad': True,
                'accesorio_cargador': True,
                'accesorio_maletin': False,
                'accesorio_mouse': True,
                'accesorio_teclado': False,
                'accesorio_monitor': False,
                'accesorio_otros': True,
                'accesorios_otros_detalle': 'Bolsa térmica',
            },
            usuario=self.user,
        )
        formato.refresh_from_db()
        self.assertTrue(formato.accesorio_cargador)
        self.assertTrue(formato.accesorio_mouse)
        self.assertFalse(formato.accesorio_maletin)
        self.assertTrue(formato.accesorio_otros)
        self.assertEqual(formato.accesorios_otros_detalle, 'Bolsa térmica')

        formato.firma_cliente.save(
            'firma_cli.png',
            ContentFile(_png_bytes()),
            save=True,
        )
        final = finalizar_formato(formato, usuario=self.user, forzar_regenerar=True)
        resultado = PDFFormatoServicioOOW(final).generar_pdf()
        self.assertTrue(resultado['success'])
        self.assertGreater(len(resultado['buffer'].getvalue()), 100)

        # La sección construye pares SI/NO a partir de los booleans del modelo
        pares_esperados = {
            'Cargador': 'SI',
            'Maletín': 'NO',
            'Mouse': 'SI',
            'Teclado': 'NO',
            'Monitor': 'NO',
            'Otros': 'SI',
        }
        f = final
        pares_reales = {
            'Cargador': 'SI' if f.accesorio_cargador else 'NO',
            'Maletín': 'SI' if f.accesorio_maletin else 'NO',
            'Mouse': 'SI' if f.accesorio_mouse else 'NO',
            'Teclado': 'SI' if f.accesorio_teclado else 'NO',
            'Monitor': 'SI' if f.accesorio_monitor else 'NO',
            'Otros': 'SI' if f.accesorio_otros else 'NO',
        }
        self.assertEqual(pares_reales, pares_esperados)

    def test_regenerar_pdf_ya_finalizado(self):
        """
        Tras finalizar, se pueden actualizar datos y regenerar el PDF
        con permitir_finalizado / forzar_regenerar (sin error).
        """
        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        aplicar_payload_borrador(
            formato,
            {
                'acepta_condiciones': True,
                'acepta_privacidad': True,
                'accesorio_cargador': False,
                'observaciones_tecnicas': 'Primera versión',
            },
            usuario=self.user,
        )
        formato.refresh_from_db()
        formato.firma_cliente.save(
            'firma_cli.png',
            ContentFile(_png_bytes()),
            save=True,
        )
        final = finalizar_formato(formato, usuario=self.user)
        self.assertEqual(final.estado, 'finalizado')

        # Sin el flag, no se debe poder editar
        with self.assertRaises(FormatoOOWError):
            aplicar_payload_borrador(
                final,
                {'accesorio_cargador': True},
                usuario=self.user,
            )

        # Con permitir_finalizado: guarda y regenera
        aplicar_payload_borrador(
            final,
            {
                'acepta_condiciones': True,
                'acepta_privacidad': True,
                'accesorio_cargador': True,
                'observaciones_tecnicas': 'Segunda versión con cargador',
            },
            usuario=self.user,
            permitir_finalizado=True,
        )
        final.refresh_from_db()
        self.assertTrue(final.accesorio_cargador)
        regenerado = finalizar_formato(
            final,
            usuario=self.user,
            forzar_regenerar=True,
        )
        self.assertEqual(regenerado.estado, 'finalizado')
        self.assertTrue(regenerado.pdf)
        self.assertIn('cargador', regenerado.observaciones_tecnicas.lower())

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
    def test_reenviar_email_encola_task(self):
        """
        Reenviar por correo actualiza destinatarios y encola Celery (mock).
        """
        from unittest.mock import patch

        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.test import RequestFactory

        ct = ContentType.objects.get_for_model(OrdenServicio)
        for codename in ('view_ordenservicio', 'change_ordenservicio'):
            self.user.user_permissions.add(
                Permission.objects.get(content_type=ct, codename=codename)
            )

        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        aplicar_payload_borrador(
            formato,
            {
                'acepta_condiciones': True,
                'acepta_privacidad': True,
                'emails_envio': ['viejo@test.local'],
            },
            usuario=self.user,
        )
        formato.refresh_from_db()
        formato.firma_cliente.save(
            'firma_cli.png',
            ContentFile(_png_bytes()),
            save=True,
        )
        finalizar_formato(formato, usuario=self.user)
        formato.refresh_from_db()

        factory = RequestFactory()
        request = factory.post(
            reverse('servicio_tecnico:formato_oow_reenviar_email', args=[self.orden.pk]),
            data='{"emails_envio":["nuevo1@test.local","nuevo2@test.local"]}',
            content_type='application/json',
        )
        request.user = self.user
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))

        with patch(
            'servicio_tecnico.tasks.enviar_formato_oow_email_task.delay'
        ) as mock_delay:
            resp = views_formato_oow.formato_oow_reenviar_email(
                request, orden_id=self.orden.pk,
            )
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode('utf-8')
        self.assertIn('nuevo1@test.local', body)
        self.assertTrue(mock_delay.called)
        formato.refresh_from_db()
        self.assertEqual(
            lista_emails_envio(formato),
            ['nuevo1@test.local', 'nuevo2@test.local'],
        )


class FormatoOowVistaTest(TestCase):
    """Wizard HTTP responde 200 con permisos (RequestFactory, sin Axes/sesión)."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Vista OOW',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_vista_oow',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='User Vista',
            cargo='Técnico',
            area='Laboratorio',
            email='vista.oow@test.local',
            sucursal=self.sucursal,
            user=self.user,
            contraseña_configurada=True,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        for codename in (
            'view_ordenservicio',
            'change_ordenservicio',
            'add_ordenservicio',
        ):
            perm = Permission.objects.get(content_type=ct, codename=codename)
            self.user.user_permissions.add(perm)

        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-88888',
            tipo_equipo='Laptop',
            marca='HP',
            modelo='EliteBook',
            numero_serie='HPTEST001',
            email_cliente='hp@test.local',
            falla_principal='No enciende',
            gama='alta',
        )

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
    def test_wizard_get_200(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware

        request = self.factory.get(
            reverse('servicio_tecnico:formato_oow_wizard', args=[self.orden.pk])
        )
        request.user = self.user
        # Session + messages: requeridos por decoradores / messages framework
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))

        resp = views_formato_oow.formato_oow_wizard(request, orden_id=self.orden.pk)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Formato Digital OOW', resp.content)
        self.assertTrue(
            FormatoServicioOOW.objects.filter(orden=self.orden).exists()
        )


class FormatoOowEmailTaskTest(TestCase):
    """
    La task Celery envía HTML profesional (template) conservando el asunto.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Mockeamos EmailMessage.send para no mandar correos reales en CI.
    Creamos un PDF mínimo en el FileField (no hace falta regenerar ReportLab).
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Email OOW',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='email_oow',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Email OOW',
            cargo='Técnico',
            area='Laboratorio',
            email='email.oow@test.local',
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
            orden_cliente='OOW-EMAIL01',
            folio_sicser='OOW-EMAIL01',
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='Latitude 5520',
            numero_serie='EMAILSTAG01',
            email_cliente='cliente.email@test.local',
            nombre_cliente='Cliente Email',
            falla_principal='Pantalla',
            gama='media',
        )

    @override_settings(
        EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
        STORAGES={
            'default': {
                'BACKEND': 'django.core.files.storage.FileSystemStorage',
            },
            'staticfiles': {
                'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
            },
        },
    )
    def test_task_asunto_y_cuerpo_profesional(self):
        from unittest.mock import patch

        from servicio_tecnico.models import HistorialOrden
        from servicio_tecnico.tasks import enviar_formato_oow_email_task

        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        # PDF mínimo: basta con bytes para adjuntar; no validamos el contenido PDF.
        formato.pdf.save(
            'FormatoOOW_test.pdf',
            ContentFile(b'%PDF-1.4 fake-oow-pdf'),
            save=True,
        )
        formato.emails_envio = ['cliente.email@test.local']
        formato.email_envio = 'cliente.email@test.local'
        formato.save(update_fields=['emails_envio', 'email_envio'])

        capturados = []

        def _fake_send(self_msg):
            capturados.append(self_msg)
            return 1

        with patch(
            'django.core.mail.EmailMessage.send',
            new=_fake_send,
        ):
            # .run() ejecuta el cuerpo de la task sin broker Celery.
            resultado = enviar_formato_oow_email_task.run(
                formato_id=formato.pk,
                usuario_id=self.user.pk,
                db_alias='default',
            )

        self.assertTrue(resultado.get('success'))
        self.assertEqual(len(capturados), 1)
        msg = capturados[0]
        self.assertEqual(
            msg.subject,
            'Formato de Servicio OOW — OOW-EMAIL01',
        )
        body = msg.body
        # Template profesional (no el HTML mínimo antiguo).
        self.assertIn('FORMATO DE SERVICIO FUERA DE GARANTÍA', body)
        self.assertIn('equipment-info', body)
        self.assertIn('cid:logo_sic', body)
        self.assertIn('OOW-EMAIL01', body)
        self.assertIn('EMAILSTAG01', body)
        self.assertNotIn('Estimado(a) cliente', body)
        self.assertTrue(
            HistorialOrden.objects.filter(
                orden=self.orden,
                tipo_evento='email',
            ).exists()
        )
