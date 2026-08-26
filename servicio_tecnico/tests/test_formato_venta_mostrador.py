"""
Tests del Formato Digital de Venta Mostrador (Nota de Venta Directa).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cubren: reexports/URLs, candidatura solo FL, finalizar SIN firma/daños,
conceptos + IVA 16% en el PDF, y que el correo se encola con db_alias.
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico import views as st_views
from servicio_tecnico import views_formato_venta_mostrador
from servicio_tecnico.models import (
    DetalleEquipo,
    FormatoServicioVentaMostrador,
    OrdenServicio,
    PiezaVentaMostrador,
    VentaMostrador,
)
from servicio_tecnico.services.formato_venta_mostrador import (
    armar_conceptos_venta,
    finalizar_formato,
    obtener_o_crear_borrador,
    orden_es_candidata_formato_venta_mostrador,
)


User = get_user_model()


class FormatoVmReexportsTest(SimpleTestCase):
    """Humo: views.py reexporta y las URLs resuelven al módulo nuevo."""

    def test_reexports_y_urls(self):
        self.assertIs(
            st_views.formato_venta_mostrador_wizard,
            views_formato_venta_mostrador.formato_venta_mostrador_wizard,
        )
        self.assertIs(
            st_views.formato_venta_mostrador_guardar,
            views_formato_venta_mostrador.formato_venta_mostrador_guardar,
        )
        self.assertIs(
            st_views.formato_venta_mostrador_finalizar,
            views_formato_venta_mostrador.formato_venta_mostrador_finalizar,
        )
        self.assertIs(
            st_views.formato_venta_mostrador_reenviar_email,
            views_formato_venta_mostrador.formato_venta_mostrador_reenviar_email,
        )
        self.assertIs(
            st_views.formato_venta_mostrador_pdf,
            views_formato_venta_mostrador.formato_venta_mostrador_pdf,
        )

        match = resolve(
            reverse('servicio_tecnico:formato_venta_mostrador_wizard', args=[1])
        )
        self.assertIs(
            match.func,
            views_formato_venta_mostrador.formato_venta_mostrador_wizard,
        )


class FormatoVmServiceTest(TestCase):
    """Candidatura, IVA y PDF opcional (sin firma ni daños)."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Test Formato VM',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='front_vm',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Front VM',
            cargo='Recepcion',
            area='Front',
            email='front.vm@test.local',
            sucursal=self.sucursal,
            user=self.user,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='venta_mostrador',
            estado='recepcion',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='FL-9570',
            tipo_equipo='Laptop',
            marca='ASUS',
            modelo='X412FA',
            numero_serie='KCNC0V153226527',
            email_cliente='cliente.vm@test.local',
            nombre_cliente='Cliente Venta Mostrador',
            rfc_cliente='TCM180912JC5',
            falla_principal='Venta Mostrador - Servicio Directo',
            gama='media',
        )
        VentaMostrador.objects.create(
            orden=self.orden,
            folio_venta='VM-TEST-9570',
            incluye_limpieza=True,
            costo_limpieza=Decimal('1050.00'),
        )

    def test_orden_es_candidata_vm(self):
        """Solo venta mostrador ve este formato."""
        self.assertTrue(orden_es_candidata_formato_venta_mostrador(self.orden))

    def test_no_candidata_diagnostico(self):
        """OOW / diagnóstico NO usa la nota de venta (tiene formato OOW)."""
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='OOW-11111',
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='Latitude',
            numero_serie='DIAG001',
            gama='media',
        )
        self.assertFalse(orden_es_candidata_formato_venta_mostrador(orden))

    def test_conceptos_iva_mx_1050(self):
        """
        $1,050 con IVA → subtotal $905.17 e IVA $144.83 (como el formato papel).
        """
        conceptos = armar_conceptos_venta(self.orden)
        self.assertTrue(conceptos['aplica_iva'])
        self.assertEqual(len(conceptos['lineas']), 1)
        self.assertEqual(
            conceptos['lineas'][0]['descripcion'],
            'Limpieza y Mantenimiento',
        )
        self.assertEqual(conceptos['lineas'][0]['precio_unitario'], Decimal('905.17'))
        self.assertEqual(conceptos['subtotal'], Decimal('905.17'))
        self.assertEqual(conceptos['iva'], Decimal('144.83'))
        self.assertEqual(conceptos['total'], Decimal('1050.00'))

    def test_finalizar_sin_firma_ni_danos(self):
        """El de front puede generar la nota aunque el equipo no haya ingresado."""
        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        final = finalizar_formato(formato, usuario=self.user)
        self.assertEqual(final.estado, 'finalizado')
        self.assertTrue(final.pdf)
        self.assertTrue(final.pdf.size > 100)

    def test_pdf_incluye_concepto_e_iva(self):
        """El PDF se genera con título de nota de venta (2 páginas)."""
        from servicio_tecnico.utils.pdf_formato_venta_mostrador import (
            PDFFormatoVentaMostrador,
        )

        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        final = finalizar_formato(formato, usuario=self.user)
        resultado = PDFFormatoVentaMostrador(final).generar_pdf()
        self.assertTrue(resultado['success'])
        raw = resultado['buffer'].getvalue()
        # El stream de texto va comprimido; el metadato Title sí queda en claro.
        self.assertIn(b'Nota de Venta Directa', raw)
        self.assertIn(b'/Count 2', raw)
        self.assertGreater(len(raw), 2000)

    def test_formato_telefono_whatsapp_mx(self):
        """Los 10 dígitos de WhatsApp se leen con espacios en el PDF."""
        from servicio_tecnico.utils.pdf_formato_venta_mostrador import (
            PDFFormatoVentaMostrador,
        )

        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        generador = PDFFormatoVentaMostrador(formato)
        self.assertEqual(generador._fmt_tel_mx('5575615114'), '55 7561 5114')
        self.assertEqual(generador._fmt_tel_mx('123'), '123')

    def test_pdf_sin_equipo_completo(self):
        """Campos de equipo vacíos no rompen la generación."""
        detalle = self.orden.detalle_equipo
        detalle.marca = ''
        detalle.modelo = ''
        detalle.numero_serie = ''
        detalle.save()
        formato = obtener_o_crear_borrador(self.orden, usuario=self.user)
        final = finalizar_formato(formato, usuario=self.user, forzar_regenerar=True)
        self.assertTrue(final.pdf)

    def test_incluye_pieza_en_conceptos(self):
        """Las piezas vendidas salen como renglón aparte."""
        PiezaVentaMostrador.objects.create(
            venta_mostrador=self.orden.venta_mostrador,
            descripcion_pieza='SSD 1TB',
            cantidad=1,
            precio_unitario=Decimal('1160.00'),
        )
        conceptos = armar_conceptos_venta(self.orden)
        descripciones = [l['descripcion'] for l in conceptos['lineas']]
        self.assertIn('SSD 1TB', descripciones)
        self.assertEqual(conceptos['total'], Decimal('2210.00'))


class FormatoVmVistasTest(TestCase):
    """Wizard 200 y correo mockeado con db_alias."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Wizard VM',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='front_vm_view',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Front Wizard',
            cargo='Recepcion',
            area='Front',
            email='front.wizard@test.local',
            sucursal=self.sucursal,
            user=self.user,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        for codename in ('view_ordenservicio', 'change_ordenservicio'):
            self.user.user_permissions.add(
                Permission.objects.get(content_type=ct, codename=codename)
            )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='venta_mostrador',
            estado='recepcion',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='FL-WIZ-01',
            tipo_equipo='Laptop',
            marca='ASUS',
            modelo='X412',
            numero_serie='WIZ001',
            email_cliente='wiz@test.local',
            nombre_cliente='Cliente Wizard',
            gama='media',
        )

    def _request_con_sesion(self, request):
        request.user = self.user
        SessionMiddleware(lambda r: None).process_request(request)
        request.session.save()
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
    def test_wizard_get_200(self):
        request = self._request_con_sesion(
            self.factory.get(
                reverse(
                    'servicio_tecnico:formato_venta_mostrador_wizard',
                    args=[self.orden.pk],
                )
            )
        )
        resp = views_formato_venta_mostrador.formato_venta_mostrador_wizard(
            request, orden_id=self.orden.pk,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'Nota de Venta Directa', resp.content)
        self.assertTrue(
            FormatoServicioVentaMostrador.objects.filter(orden=self.orden).exists()
        )

    def test_finalizar_encola_email_con_db_alias(self):
        """Al marcar enviar_email, delay() recibe db_alias (multi-país)."""
        request = self._request_con_sesion(
            self.factory.post(
                reverse(
                    'servicio_tecnico:formato_venta_mostrador_finalizar',
                    args=[self.orden.pk],
                ),
                data='{"enviar_email": true, "emails_envio": ["cliente@test.local"]}',
                content_type='application/json',
            )
        )
        with patch(
            'servicio_tecnico.tasks.enviar_formato_venta_mostrador_email_task.delay'
        ) as mock_delay:
            resp = views_formato_venta_mostrador.formato_venta_mostrador_finalizar(
                request, orden_id=self.orden.pk,
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(mock_delay.called)
        kwargs = mock_delay.call_args.kwargs
        self.assertIn('db_alias', kwargs)
        self.assertTrue(kwargs['db_alias'])
