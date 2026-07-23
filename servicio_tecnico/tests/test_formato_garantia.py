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
        self.assertIs(
            st_views.formato_garantia_eliminar_evidencia,
            views_formato_garantia.formato_garantia_eliminar_evidencia,
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

        match_elim = resolve(
            reverse(
                'servicio_tecnico:formato_garantia_eliminar_evidencia',
                args=[1, 2],
            )
        )
        self.assertIs(
            match_elim.func,
            views_formato_garantia.formato_garantia_eliminar_evidencia,
        )

    def test_vistas_escritorio_tienen_laterales_izq_der(self):
        """PC escritorio: laterales separados (no un solo 'lateral')."""
        from config.constants import VISTAS_DANO_ESTETICO_ESCRITORIO

        claves = [c for c, _ in VISTAS_DANO_ESTETICO_ESCRITORIO]
        self.assertIn('esc_lat_izq', claves)
        self.assertIn('esc_lat_der', claves)
        self.assertNotIn('lateral', claves)
        labels = dict(VISTAS_DANO_ESTETICO_ESCRITORIO)
        self.assertEqual(labels['esc_lat_izq'], 'Lateral Izquierdo')
        self.assertEqual(labels['esc_lat_der'], 'Lateral Derecho')


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
            telefono_cliente='5541430017',
            direccion_cliente='Circuito Economistas 15-A Colonia Satelite C.P. 53100',
            falla_principal=self.falla,
            gama='alta',
            tiene_cargador=True,
        )

    def test_orden_es_candidata_garantia_y_no_oow(self):
        """Garantía Dell usa su formato; no debe abrir el OOW."""
        self.assertTrue(orden_es_candidata_formato_garantia(self.orden))
        self.assertFalse(orden_es_candidata_formato_oow(self.orden))

    def test_candidata_diagnostico_dell_dentro_garantia(self):
        """
        Diagnóstico Dell dentro de garantía (sin SICSER) → sí.
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            es_fuera_garantia=False,
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='CLI-DELL-001',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude 5420',
            numero_serie='TESTDELL01',
            gama='media',
        )
        orden.refresh_from_db()
        self.assertFalse(orden.es_fuera_garantia)
        self.assertTrue(orden_es_candidata_formato_garantia(orden))

    def test_no_candidata_otra_marca(self):
        """Diagnóstico HP dentro de garantía → no (solo Dell)."""
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            es_fuera_garantia=False,
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='CLI-HP-001',
            tipo_equipo='Laptop',
            marca='HP',
            modelo='EliteBook',
            numero_serie='TESTHP0001',
            gama='media',
        )
        self.assertFalse(orden_es_candidata_formato_garantia(orden))

    def test_no_candidata_dell_fuera_garantia(self):
        """Dell fuera de garantía → Formato OOW, no Garantía."""
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='OOW-77777',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude 3520',
            numero_serie='TESTOOW01',
            gama='media',
        )
        orden.refresh_from_db()
        self.assertTrue(orden.es_fuera_garantia)
        self.assertFalse(orden_es_candidata_formato_garantia(orden))
        self.assertTrue(orden_es_candidata_formato_oow(orden))

    def test_no_candidata_venta_mostrador_dell(self):
        """Venta mostrador Dell nunca debe ver Formato Garantía."""
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='venta_mostrador',
            estado='espera',
            es_fuera_garantia=False,
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='VM-DELL-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Inspiron',
            numero_serie='TESTVMD01',
            gama='media',
            sicser_origen='garantia',
        )
        self.assertFalse(orden_es_candidata_formato_garantia(orden))

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

        # El contenido textual del PDF va comprimido: usamos pdftotext para leerlo.
        # Así verificamos que YA NO va el aviso SIC y SÍ van exclusiones Dell.
        import os
        import subprocess
        import tempfile

        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
            tmp.write(pdf_bytes)
            ruta_pdf = tmp.name
        try:
            texto = subprocess.check_output(
                ['pdftotext', '-layout', ruta_pdf, '-'],
                text=True,
                stderr=subprocess.DEVNULL,
            )
        finally:
            os.unlink(ruta_pdf)

        self.assertNotIn('WWW.SIC.COM.MX', texto)
        self.assertNotIn('Aviso de privacidad', texto)
        self.assertIn('ACTIVIDADES NO INCLUIDAS', texto)
        self.assertIn('SERVICIO FINAL', texto)
        self.assertIn('55 1133 1295', texto)
        self.assertIn('ENTERADO Y ACEPTADO', texto)
        # Dirección del cliente debe estar en DetalleEquipo (fuente del PDF)
        self.assertIn(
            'Circuito Economistas',
            self.orden.detalle_equipo.direccion_cliente,
        )
        self.assertIsInstance(FormatoServicioGarantia.objects.get(pk=final.pk), FormatoServicioGarantia)

    def test_barcode_dps_solo_en_header_pagina_1(self):
        """
        Code128 del DPS: se genera con valor válido y solo se pide en hoja 1.

        EXPLICACIÓN PARA PRINCIPIANTES:
        No podemos "ver" el dibujo del barcode en el PDF fácilmente, pero sí
        comprobamos que el helper lo crea y que el header de otras páginas
        tiene una fila menos en el centro (solo el banner, sin barcode).
        """
        from reportlab.graphics.barcode.code128 import Code128

        from servicio_tecnico.utils.pdf_formato_garantia import PDFFormatoServicioGarantia

        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        gen = PDFFormatoServicioGarantia(formato)

        # Con DPS real (orden_cliente del setUp) debe devolver Code128.
        self.assertEqual(gen._dps(), '467826738')
        barcode = gen._crear_barcode_dps()
        self.assertIsInstance(barcode, Code128)

        # Página 1: columna central = barcode + banner (2 filas).
        centro_p1 = gen._construir_header(incluir_barcode=True)[0]._cellvalues[0][1]
        self.assertEqual(len(centro_p1._cellvalues), 2)
        self.assertIsInstance(centro_p1._cellvalues[0][0], Code128)

        # Páginas 2+: solo banner (1 fila), sin barcode.
        centro_otras = gen._construir_header(incluir_barcode=False)[0]._cellvalues[0][1]
        self.assertEqual(len(centro_otras._cellvalues), 1)
        self.assertNotIsInstance(centro_otras._cellvalues[0][0], Code128)

        # Sin DPS válido → None (no rompe el PDF).
        gen._dps = lambda: '—'  # type: ignore[method-assign]
        self.assertIsNone(gen._crear_barcode_dps())

    def test_datos_orden_incluye_direccion(self):
        from servicio_tecnico.services.formato_garantia import datos_orden_para_wizard

        datos = datos_orden_para_wizard(self.orden)
        self.assertIn('direccion_cliente', datos)
        self.assertIn('Circuito Economistas', datos['direccion_cliente'])

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
        # Aviso Dell informativo (sin guardar aceptación): debe verse en el wizard
        self.assertIn(b'ACTIVIDADES NO INCLUIDAS EN EL SERVICIO DE GARANTIA', resp.content)
        self.assertIn(b'modalActividadesDell', resp.content)
        self.assertIn(b'Servidores y equipos de almacenamiento', resp.content)
        # Scanner QR/barras junto al número de cargador
        self.assertIn(b'id="numeroCargador"', resp.content)
        self.assertIn(b'id="btnEscanearCargador"', resp.content)
        self.assertIn(b'scanner_codigo.js', resp.content)
        self.assertIn(b'zxing-wasm', resp.content)
        self.assertTrue(
            FormatoServicioGarantia.objects.filter(orden=self.orden).exists()
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
    def test_pdf_view_headers_anti_cache(self):
        """
        Tras regenerar, la URL del PDF es la misma; sin no-store el navegador
        puede mostrar el PDF viejo (p. ej. número de cargador anterior).
        """
        from django.core.files.base import ContentFile
        from servicio_tecnico.services.formato_garantia import obtener_o_crear_borrador

        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        formato.estado = 'finalizado'
        formato.pdf.save(
            'garantia_test.pdf',
            ContentFile(b'%PDF-1.4\n%fake\n'),
            save=True,
        )

        request = self.factory.get(
            reverse('servicio_tecnico:formato_garantia_pdf', args=[self.orden.pk]),
            {'inline': '1'},
        )
        request.user = self.user
        resp = views_formato_garantia.formato_garantia_pdf(
            request, orden_id=self.orden.pk,
        )
        self.assertEqual(resp.status_code, 200)
        cache_ctrl = resp.get('Cache-Control', '')
        self.assertIn('no-store', cache_ctrl)
        self.assertIn('no-cache', cache_ctrl)


class FormatoGarantiaEliminarEvidenciaTest(TestCase):
    """POST eliminar solo borra escaneo_garantia de esa orden."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Elim Evidencia Garantía',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='elim_gar_evid',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Elim Evidencia',
            cargo='Técnico',
            area='Laboratorio',
            email='elim.gar@test.local',
            sucursal=self.sucursal,
            user=self.user,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        for codename in ('view_ordenservicio', 'change_ordenservicio'):
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
            orden_cliente='555666777',
            sicser_origen='garantia',
            sicser_id_externo='555666777',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='XPS',
            numero_serie='SNELIM1',
            email_cliente='c@d.com',
            falla_principal='Falla',
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
    def test_eliminar_escaneo_garantia(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware
        from servicio_tecnico.models import ImagenOrden

        img = ImagenOrden(
            orden=self.orden,
            tipo='escaneo_garantia',
            descripcion='PC Audit test',
            subido_por=self.empleado,
        )
        img.imagen.save('escaneo_test.png', ContentFile(_png_bytes()), save=True)

        url = reverse(
            'servicio_tecnico:formato_garantia_eliminar_evidencia',
            args=[self.orden.pk, img.pk],
        )
        request = self.factory.post(url)
        request.user = self.user
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))

        resp = views_formato_garantia.formato_garantia_eliminar_evidencia(
            request, orden_id=self.orden.pk, imagen_id=img.pk,
        )
        self.assertEqual(resp.status_code, 200)
        import json
        data = json.loads(resp.content.decode('utf-8'))
        self.assertTrue(data.get('success'))
        self.assertFalse(ImagenOrden.objects.filter(pk=img.pk).exists())

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
    def test_no_elimina_otro_tipo(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware
        from servicio_tecnico.models import ImagenOrden

        img = ImagenOrden(
            orden=self.orden,
            tipo='ingreso',
            descripcion='No debe borrarse',
            subido_por=self.empleado,
        )
        img.imagen.save('ingreso_test.png', ContentFile(_png_bytes()), save=True)

        request = self.factory.post(
            reverse(
                'servicio_tecnico:formato_garantia_eliminar_evidencia',
                args=[self.orden.pk, img.pk],
            )
        )
        request.user = self.user
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
        setattr(request, '_messages', FallbackStorage(request))

        resp = views_formato_garantia.formato_garantia_eliminar_evidencia(
            request, orden_id=self.orden.pk, imagen_id=img.pk,
        )
        self.assertEqual(resp.status_code, 404)
        self.assertTrue(ImagenOrden.objects.filter(pk=img.pk).exists())


class FormatoGarantiaEmailTaskTest(TestCase):
    """
    La task Celery envía HTML profesional (template) conservando el asunto.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Mockeamos EmailMessage.send para no mandar correos reales en CI.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Email Garantía',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='email_garantia',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Email Garantía',
            cargo='Técnico',
            area='Laboratorio',
            email='email.garantia@test.local',
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
            orden_cliente='999888777',
            folio_sicser='FOLIO-GAR-01',
            sicser_origen='garantia',
            sicser_id_externo='999888777',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude 7430',
            numero_serie='GARSTAG01',
            email_cliente='cliente.gar@test.local',
            nombre_cliente='Cliente Garantía',
            falla_principal='Teclado',
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
        from servicio_tecnico.tasks import enviar_formato_garantia_email_task

        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        formato.pdf.save(
            'FormatoGarantia_test.pdf',
            ContentFile(b'%PDF-1.4 fake-garantia-pdf'),
            save=True,
        )
        formato.emails_envio = ['cliente.gar@test.local']
        formato.email_envio = 'cliente.gar@test.local'
        formato.save(update_fields=['emails_envio', 'email_envio'])

        capturados = []

        def _fake_send(self_msg):
            capturados.append(self_msg)
            return 1

        with patch(
            'django.core.mail.EmailMessage.send',
            new=_fake_send,
        ):
            resultado = enviar_formato_garantia_email_task.run(
                formato_id=formato.pk,
                usuario_id=self.user.pk,
                db_alias='default',
            )

        self.assertTrue(resultado.get('success'))
        self.assertEqual(len(capturados), 1)
        msg = capturados[0]
        # Asunto: prioridad orden_cliente (DPS) sobre folio_sicser.
        self.assertEqual(
            msg.subject,
            'Formato de Servicio Garantía Dell — 999888777',
        )
        body = msg.body
        self.assertIn('FORMATO DE SERVICIO GARANTÍA DELL', body)
        self.assertIn('equipment-info', body)
        self.assertIn('cid:logo_sic', body)
        self.assertIn('999888777', body)
        self.assertIn('GARSTAG01', body)
        self.assertNotIn('Estimado(a) cliente', body)
        self.assertTrue(
            HistorialOrden.objects.filter(
                orden=self.orden,
                tipo_evento='email',
            ).exists()
        )
