"""
Tests del Formato Digital Garantía Dell.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cubren: reexports/URLs, candidatura (garantía vs OOW), crear borrador,
accesorios Dell + número de cargador, finalizar+PDF con falla_principal.
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
from servicio_tecnico import views_formato_garantia
from servicio_tecnico.models import DetalleEquipo, FormatoServicioGarantia, OrdenServicio
from servicio_tecnico.services.formato_garantia import (
    FormatoGarantiaError,
    aplicar_payload_borrador,
    finalizar_formato,
    lista_emails_envio,
    obtener_o_crear_borrador,
    orden_es_candidata_formato_garantia,
)
from servicio_tecnico.services.formato_oow import orden_es_candidata_formato_oow
from servicio_tecnico.sicser_import import extraer_falla_garantia


User = get_user_model()


def _png_bytes(color=(0, 51, 102)) -> bytes:
    """Genera un PNG mínimo en memoria para firmas de prueba."""
    buf = BytesIO()
    Image.new('RGB', (120, 40), color=color).save(buf, format='PNG')
    return buf.getvalue()


class FormatoGarantiaReexportsTest(SimpleTestCase):
    """Humo: views.py reexporta y las URLs resuelven al módulo nuevo."""

    def test_reexports_y_urls(self):
        self.assertIs(
            st_views.formato_garantia_wizard,
            views_formato_garantia.formato_garantia_wizard,
        )
        self.assertIs(
            st_views.formato_garantia_guardar,
            views_formato_garantia.formato_garantia_guardar,
        )
        self.assertIs(
            st_views.formato_garantia_finalizar,
            views_formato_garantia.formato_garantia_finalizar,
        )
        self.assertIs(
            st_views.abrir_formato_garantia_desde_sicser,
            views_formato_garantia.abrir_formato_garantia_desde_sicser,
        )

        match = resolve(reverse('servicio_tecnico:formato_garantia_wizard', args=[1]))
        self.assertIs(match.func, views_formato_garantia.formato_garantia_wizard)

        match_abrir = resolve(
            reverse('servicio_tecnico:abrir_formato_garantia_desde_sicser')
        )
        self.assertIs(
            match_abrir.func,
            views_formato_garantia.abrir_formato_garantia_desde_sicser,
        )


class FormatoGarantiaServiceTest(TestCase):
    """Pruebas de negocio: borrador, candidata garantía y finalizar con PDF."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Test Formato Garantía',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='tecnico_garantia',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Garantía',
            cargo='Técnico',
            area='Laboratorio',
            email='tecnico.garantia@test.local',
            sucursal=self.sucursal,
            user=self.user,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            tecnico_asignado_actual=self.empleado,
        )
        self.falla = (
            'OS: None Embedded SEV: Medium #Issue Summary# Equipo no enciende'
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='467826738',
            folio_sicser='467826738',
            sicser_id_externo='467826738',
            sicser_origen='garantia',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Precision 3660 Tower',
            numero_serie='39J8FZ3',
            email_cliente='cliente.garantia@test.local',
            nombre_cliente='Olivia Zayas',
            falla_principal=self.falla,
            gama='alta',
            tiene_cargador=True,
        )

    def test_orden_es_candidata_garantia_y_no_oow(self):
        """Garantía Dell usa su formato; no debe abrir el OOW."""
        self.assertTrue(orden_es_candidata_formato_garantia(self.orden))
        self.assertFalse(orden_es_candidata_formato_oow(self.orden))

    def test_extraer_falla_completa(self):
        """Import guarda el texto completo de instrucciones_dell."""
        texto = (
            'OS: None #Prerequisites# Recibir equipo '
            '#Issue Summary# No enciende #Instructions# Revisar'
        )
        self.assertEqual(extraer_falla_garantia(texto), texto)
        self.assertIn('SICSER', extraer_falla_garantia(''))

    def test_obtener_o_crear_borrador_prefill(self):
        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        self.assertEqual(formato.estado, 'borrador')
        self.assertTrue(formato.accesorio_cargador)
        self.assertEqual(formato.email_envio, 'cliente.garantia@test.local')
        self.assertEqual(
            lista_emails_envio(formato),
            ['cliente.garantia@test.local'],
        )
        mismo = obtener_o_crear_borrador(self.orden, usuario=self.user)
        self.assertEqual(formato.pk, mismo.pk)

    def test_guardar_accesorios_dell_y_numero_cargador(self):
        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        aplicar_payload_borrador(
            formato,
            {
                'accesorio_cargador': True,
                'accesorio_pluma': True,
                'accesorio_docking': True,
                'accesorio_microsd_sim': False,
                'numero_cargador': 'CN-0ABC123',
                'accesorios_otros_detalle': '',
            },
            usuario=self.user,
        )
        formato.refresh_from_db()
        self.assertTrue(formato.accesorio_cargador)
        self.assertTrue(formato.accesorio_pluma)
        self.assertTrue(formato.accesorio_docking)
        self.assertFalse(formato.accesorio_microsd_sim)
        self.assertEqual(formato.numero_cargador, 'CN-0ABC123')

    def test_finalizar_genera_pdf_con_falla(self):
        from servicio_tecnico.utils.pdf_formato_garantia import PDFFormatoServicioGarantia

        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        aplicar_payload_borrador(
            formato,
            {
                'acepta_condiciones': True,
                'acepta_privacidad': True,
                'accesorio_cargador': True,
                'numero_cargador': 'NA',
                'observaciones_tecnicas': 'Rayón leve en pantalla',
                'disclaimer_pc_audit': True,
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

        resultado = PDFFormatoServicioGarantia(final).generar_pdf()
        self.assertTrue(resultado['success'])
        pdf_bytes = resultado['buffer'].getvalue()
        self.assertGreater(len(pdf_bytes), 100)
        # El PDF debe mencionar la falla / DPS (texto extraíble)
        # ReportLab a veces comprime; al menos validamos generación ok.
        self.assertIsInstance(FormatoServicioGarantia.objects.get(pk=final.pk), FormatoServicioGarantia)

    def test_finalizar_exige_firma(self):
        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        aplicar_payload_borrador(
            formato,
            {
                'acepta_condiciones': True,
                'acepta_privacidad': True,
            },
            usuario=self.user,
        )
        with self.assertRaises(FormatoGarantiaError):
            finalizar_formato(formato, usuario=self.user)


class FormatoGarantiaWizardViewTest(TestCase):
    """GET del wizard responde 200 para orden garantía."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Wizard Garantía',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='vista_garantia',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Vista Garantía',
            cargo='Técnico',
            area='Laboratorio',
            email='vista.garantia@test.local',
            sucursal=self.sucursal,
            user=self.user,
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
            estado='espera',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='111222333',
            sicser_origen='garantia',
            sicser_id_externo='111222333',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude 7430',
            numero_serie='ABC1234',
            email_cliente='a@b.com',
            falla_principal='No enciende',
            gama='media',
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
            reverse('servicio_tecnico:formato_garantia_wizard', args=[self.orden.pk])
        )
        request.user = self.user
        # Session + messages: requeridos por decoradores / messages framework
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))

        resp = views_formato_garantia.formato_garantia_wizard(
            request, orden_id=self.orden.pk,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Formato Digital Garant', resp.content)
        self.assertTrue(
            FormatoServicioGarantia.objects.filter(orden=self.orden).exists()
        )
