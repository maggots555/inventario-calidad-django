"""
Tests de cobros: resumen (IVA/saldo/50%) y POST en detalle_orden.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1) Unidad: calcular_resumen_cobro suma cotización + IVA MX + venta
   mostrador, y marca si ya cubre el 50% o el 100%.
2) Unidad: registrar_pago rechaza un abono mayor al saldo.
3) Integración: recepción SÍ guarda el pago (con foto); el técnico NO.
4) Integración: pasar a "entregado" con saldo avisa, pero SÍ cambia estado.
"""

from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from inventario.models import Empleado, Sucursal
from scorecard.models import ComponenteEquipo
from servicio_tecnico.models import (
    Cotizacion,
    DetalleEquipo,
    HistorialOrden,
    OrdenServicio,
    PagoOrden,
    PiezaCotizada,
    VentaMostrador,
)
from servicio_tecnico.services.pagos_orden import (
    calcular_resumen_cobro,
    mensaje_alerta_pago_por_estado,
    registrar_pago,
)
from servicio_tecnico.views import detalle_orden


User = get_user_model()


def _png_bytes() -> bytes:
    """PNG mínimo en memoria para el comprobante de prueba."""
    buf = BytesIO()
    Image.new('RGB', (40, 40), color=(20, 80, 140)).save(buf, format='PNG')
    return buf.getvalue()


class CalcularResumenCobroTest(TestCase):
    """
    Objetivo: el total combina cotización (con IVA en MX) y venta mostrador.

    Efectos: crea sucursal, orden, cotización y opcionalmente VM/pagos.
    """

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Pagos Unidad',
            ciudad='CDMX',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Cajero Unidad',
            cargo='Recepcionista',
            area='FRONTDESK',
            email='cajero.unidad@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='cotizacion',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-PAGO-U-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-PAGO-U-01',
            falla_principal='No enciende',
            gama='baja',
        )
        self.componente = ComponenteEquipo.objects.create(
            nombre='Pantalla Pagos Unidad',
            tipo_equipo='laptop',
            activo=True,
        )
        self.cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('100.00'),
            usuario_acepto=True,
        )
        PiezaCotizada.objects.create(
            cotizacion=self.cotizacion,
            componente=self.componente,
            cantidad=1,
            costo_unitario=Decimal('200.00'),
            precio_unitario_cliente=Decimal('500.00'),
            aceptada_por_cliente=True,
        )

    def test_mexico_suma_iva_y_marca_anticipo(self):
        """
        Feliz MX: piezas 500 + MO 100 = 600; IVA 96; total 696.
        Un pago de 348 cubre el 50% y deja saldo.
        """
        # 600 * 0.16 = 96.00 → total 696.00; 50% = 348.00
        registrar_pago(
            orden=self.orden,
            empleado=self.empleado,
            monto=Decimal('348.00'),
            tipo='anticipo',
            metodo='transferencia',
            codigo_pais='MX',
        )
        resumen = calcular_resumen_cobro(self.orden, codigo_pais='MX')
        self.assertEqual(resumen.subtotal_cotizacion, Decimal('600.00'))
        self.assertEqual(resumen.iva_cotizacion, Decimal('96.00'))
        self.assertEqual(resumen.total_a_cobrar, Decimal('696.00'))
        self.assertEqual(resumen.pagado, Decimal('348.00'))
        self.assertEqual(resumen.saldo, Decimal('348.00'))
        self.assertTrue(resumen.cubre_anticipo_50)
        self.assertFalse(resumen.cubierto_100)
        self.assertTrue(resumen.aplica_iva)

    def test_argentina_no_suma_iva(self):
        """Borde: fuera de MX el total es subtotal + VM, sin IVA inventado."""
        resumen = calcular_resumen_cobro(self.orden, codigo_pais='AR')
        self.assertEqual(resumen.iva_cotizacion, Decimal('0.00'))
        self.assertEqual(resumen.total_a_cobrar, Decimal('600.00'))
        self.assertFalse(resumen.aplica_iva)

    def test_incluye_venta_mostrador(self):
        """Feliz: el total suma la venta mostrador (ya con IVA)."""
        VentaMostrador.objects.create(
            orden=self.orden,
            folio_venta='VM-PAGO-U-01',
            costo_limpieza=Decimal('200.00'),
            incluye_limpieza=True,
        )
        resumen = calcular_resumen_cobro(self.orden, codigo_pais='MX')
        # 600 + 96 IVA + 200 VM = 896
        self.assertEqual(resumen.total_venta_mostrador, Decimal('200.00'))
        self.assertEqual(resumen.total_a_cobrar, Decimal('896.00'))

    def test_estimado_si_cotizacion_pendiente(self):
        """Borde: sin aceptar, el total es estimado (todas las piezas + MO)."""
        self.cotizacion.usuario_acepto = None
        self.cotizacion.save()
        resumen = calcular_resumen_cobro(self.orden, codigo_pais='MX')
        self.assertTrue(resumen.es_estimado)
        self.assertEqual(resumen.subtotal_cotizacion, Decimal('600.00'))

    def test_liquidado_cuando_se_cubre_el_total(self):
        """Feliz: dos pagos (50% + 50%) dejan saldo 0 y cubierto_100."""
        registrar_pago(
            self.orden, self.empleado, Decimal('348.00'),
            'anticipo', 'efectivo', codigo_pais='MX',
        )
        registrar_pago(
            self.orden, self.empleado, Decimal('348.00'),
            'saldo', 'efectivo', codigo_pais='MX',
        )
        resumen = calcular_resumen_cobro(self.orden, codigo_pais='MX')
        self.assertEqual(resumen.saldo, Decimal('0.00'))
        self.assertTrue(resumen.cubierto_100)

    def test_sobrepago_se_rechaza(self):
        """Borde: no se puede registrar un abono mayor al saldo."""
        with self.assertRaises(ValidationError):
            registrar_pago(
                self.orden, self.empleado, Decimal('9999.00'),
                'pago_completo', 'tarjeta', codigo_pais='MX',
            )
        self.assertEqual(PagoOrden.objects.filter(orden=self.orden).count(), 0)

    def test_sin_total_no_permite_pago(self):
        """
        Borde: orden sin cotización ni venta no acepta abonos sueltos.
        Evita que el saldo se quede en $0 con pagos 'fantasma'.
        """
        self.cotizacion.delete()
        with self.assertRaises(ValidationError) as ctx:
            registrar_pago(
                self.orden, self.empleado, Decimal('100.00'),
                'otro', 'efectivo', codigo_pais='MX',
            )
        self.assertIn('total a cobrar', str(ctx.exception).lower())
        self.assertEqual(PagoOrden.objects.filter(orden=self.orden).count(), 0)

    def test_cotizacion_rechazada_subtotal_cero(self):
        """Borde: si el cliente rechazó, esa cotización ya no se cobra."""
        self.cotizacion.usuario_acepto = False
        self.cotizacion.save()
        resumen = calcular_resumen_cobro(self.orden, codigo_pais='MX')
        self.assertEqual(resumen.subtotal_cotizacion, Decimal('0.00'))
        self.assertEqual(resumen.total_a_cobrar, Decimal('0.00'))
        self.assertFalse(resumen.es_estimado)

    def test_comprobante_corrupto_no_tira_500(self):
        """Borde: un archivo con extensión de imagen pero contenido basura."""
        falso = SimpleUploadedFile(
            'ticket.jpg',
            b'esto no es una imagen',
            content_type='image/jpeg',
        )
        with self.assertRaises(ValidationError) as ctx:
            registrar_pago(
                self.orden, self.empleado, Decimal('348.00'),
                'anticipo', 'transferencia',
                comprobante_file=falso,
                codigo_pais='MX',
            )
        self.assertIn('imagen válida', str(ctx.exception).lower())
        self.assertEqual(PagoOrden.objects.filter(orden=self.orden).count(), 0)


class DetalleOrdenPagosIntegracionTest(TestCase):
    """
    POST reales a detalle_orden para registrar pago y alertar al entregar.

    Efectos: inserta sucursal, usuarios, orden, cotización y permisos.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Pagos HTTP',
            ciudad='CDMX',
        )
        self.componente = ComponenteEquipo.objects.create(
            nombre='Teclado Pagos HTTP',
            tipo_equipo='laptop',
            activo=True,
        )
        self.user_recepcion = self._crear_usuario(
            'recepcion.pagos@test.local',
            'Recepcionista Pagos',
            'recepcionista',
            con_add_pago=True,
        )
        self.user_tecnico = self._crear_usuario(
            'tecnico.pagos@test.local',
            'Técnico Pagos',
            'tecnico',
            con_add_pago=False,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='cliente_acepta_cotizacion',
            tecnico_asignado_actual=self.user_tecnico.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-PAGO-H-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Inspiron',
            numero_serie='SN-PAGO-H-01',
            falla_principal='Teclado',
            gama='baja',
        )
        cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('100.00'),
            usuario_acepto=True,
        )
        PiezaCotizada.objects.create(
            cotizacion=cotizacion,
            componente=self.componente,
            cantidad=1,
            costo_unitario=Decimal('200.00'),
            precio_unitario_cliente=Decimal('500.00'),
            aceptada_por_cliente=True,
        )
        self.url = reverse(
            'servicio_tecnico:detalle_orden',
            args=[self.orden.pk],
        )

    def _crear_usuario(self, email, nombre, rol, con_add_pago):
        """
        Crea User + Empleado con view_ordenservicio y, si aplica, add_pagoorden.

        Args:
            email: username/email del User.
            nombre: nombre_completo del Empleado.
            rol: código de Empleado.ROL_CHOICES.
            con_add_pago: True para recepción/facturación.

        Returns:
            User recargado (permisos visibles en has_perm).
        """
        user = User.objects.create_user(
            username=email,
            email=email,
            password='testpass123',
        )
        Empleado.objects.create(
            nombre_completo=nombre,
            cargo=rol,
            area='FRONTDESK' if rol == 'recepcionista' else 'Laboratorio',
            email=email,
            sucursal=self.sucursal,
            user=user,
            rol=rol,
            activo=True,
            contraseña_configurada=True,
        )
        ct_orden = ContentType.objects.get_for_model(OrdenServicio)
        user.user_permissions.add(
            Permission.objects.get(
                content_type=ct_orden,
                codename='view_ordenservicio',
            ),
        )
        if con_add_pago:
            ct_pago = ContentType.objects.get_for_model(PagoOrden)
            user.user_permissions.add(
                Permission.objects.get(
                    content_type=ct_pago,
                    codename='add_pagoorden',
                ),
            )
        return User.objects.get(pk=user.pk)

    def _post(self, user, data: dict):
        """
        POST autenticado con session + messages (mismo patrón que cotización).

        Args:
            user: User que "inicia sesión".
            data: campos del form (incluye form_type y opcional archivo).

        Returns:
            HttpResponse del dispatcher.
        """
        request = self.factory.post(self.url, data=data)
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        self._ultima_request = request
        return detalle_orden(request, orden_id=self.orden.pk)

    def test_recepcion_registra_pago_con_comprobante(self):
        """Feliz: recepción sube monto + foto y queda PagoOrden + historial."""
        imagen = SimpleUploadedFile(
            'comprobante.png',
            _png_bytes(),
            content_type='image/png',
        )
        response = self._post(self.user_recepcion, {
            'form_type': 'registrar_pago',
            'monto': '348.00',
            'tipo': 'anticipo',
            'metodo': 'transferencia',
            'notas': 'SPEI prueba',
            'comprobante': imagen,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PagoOrden.objects.filter(orden=self.orden).count(), 1)
        pago = PagoOrden.objects.get(orden=self.orden)
        self.assertEqual(pago.monto, Decimal('348.00'))
        self.assertTrue(pago.comprobante)
        self.assertTrue(
            HistorialOrden.objects.filter(
                orden=self.orden,
                tipo_evento='sistema',
                comentario__icontains='Pago registrado',
            ).exists(),
        )

    def test_tecnico_no_puede_registrar_pago(self):
        """Borde: el técnico ve el detalle pero no cobra."""
        response = self._post(self.user_tecnico, {
            'form_type': 'registrar_pago',
            'monto': '348.00',
            'tipo': 'anticipo',
            'metodo': 'efectivo',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PagoOrden.objects.filter(orden=self.orden).count(), 0)
        textos = [str(m.message) for m in self._ultima_request._messages]
        self.assertTrue(any('permiso' in t.lower() for t in textos))

    def test_eliminar_pago_recalcula_saldo(self):
        """Feliz: borrar un abono capturado por error deja el saldo otra vez."""
        registrar_pago(
            self.orden,
            self.user_recepcion.empleado,
            Decimal('348.00'),
            'anticipo',
            'efectivo',
            codigo_pais='MX',
        )
        pago = PagoOrden.objects.get(orden=self.orden)
        response = self._post(self.user_recepcion, {
            'form_type': 'eliminar_pago',
            'pago_id': str(pago.pk),
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(PagoOrden.objects.filter(orden=self.orden).count(), 0)
        resumen = calcular_resumen_cobro(self.orden, codigo_pais='MX')
        self.assertEqual(resumen.pagado, Decimal('0.00'))
        self.assertEqual(resumen.saldo, Decimal('696.00'))

    @override_settings(MEDIA_ROOT='/tmp/sigma_pagos_test_media')
    def test_entregar_con_saldo_avisa_pero_cambia_estado(self):
        """
        Feliz/borde: hay saldo, el warning aparece y el estado SÍ pasa a entregado.
        """
        response = self._post(self.user_recepcion, {
            'form_type': 'cambio_estado',
            'estado': 'entregado',
            'comentario_cambio': 'Entrega con saldo (alerta)',
        })
        self.assertEqual(response.status_code, 302)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'entregado')
        textos = [str(m.message) for m in self._ultima_request._messages]
        self.assertTrue(any('saldo pendiente' in t.lower() for t in textos))

    def test_alerta_reparacion_sin_anticipo(self):
        """Unidad del texto: reparación sin 50% genera aviso, no excepción."""
        aviso = mensaje_alerta_pago_por_estado(self.orden, 'reparacion')
        self.assertIsNotNone(aviso)
        self.assertIn('anticipo', aviso.lower())
