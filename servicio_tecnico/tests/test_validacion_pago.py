"""
Tests de validación de pagos en la cuenta de la empresa.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Transferencia y tarjeta deben pasar por Facturación (¿ya se ve en la
cuenta?). Efectivo no. Estos tests cubren:

1) El estado inicial según el método.
2) A quién se avisa (Facturación / responsable / quien cobró).
3) POST real: Facturación sí valida; Recepción no.
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from scorecard.models import ComponenteEquipo
from servicio_tecnico.models import (
    Cotizacion,
    DetalleEquipo,
    HistorialOrden,
    OrdenServicio,
    PagoOrden,
    PiezaCotizada,
)
from servicio_tecnico.services.notificaciones_pagos import (
    destinatarios_pago_no_aparece,
    destinatarios_pago_pendiente,
    destinatarios_pago_validado,
)
from servicio_tecnico.services.pagos_orden import (
    estado_validacion_inicial,
    registrar_pago,
    usuario_puede_validar_pago,
    validar_pago_en_cuenta,
)
from servicio_tecnico.views import detalle_orden


User = get_user_model()


class EstadoValidacionInicialTest(TestCase):
    """
    Objetivo: solo transferencia y tarjeta piden conciliación.

    Efectos: ninguno (función pura).
    """

    def test_transferencia_y_tarjeta_quedan_pendientes(self):
        """Feliz: esos dos métodos nacen pendientes de Facturación."""
        self.assertEqual(estado_validacion_inicial('transferencia'), 'pendiente')
        self.assertEqual(estado_validacion_inicial('tarjeta'), 'pendiente')

    def test_efectivo_y_otro_no_aplican(self):
        """Borde: caja no se valida contra la cuenta de la empresa."""
        self.assertEqual(estado_validacion_inicial('efectivo'), 'no_aplica')
        self.assertEqual(estado_validacion_inicial('otro'), 'no_aplica')


class ValidacionPagoServiceTest(TestCase):
    """
    Objetivo: registrar/validar cambia estado, historial y destinatarios.

    Efectos: crea sucursal, empleados, orden, cotización y pagos.
    """

    def setUp(self):
        # EXPLICACIÓN: sin mock, .delay() intenta Redis y el test se cuelga.
        self._email_patcher = patch(
            'servicio_tecnico.services.notificaciones_pagos._encolar_email_validacion',
        )
        self._push_patcher = patch(
            'servicio_tecnico.services.notificaciones_pagos.enviar_push_y_campanita',
            return_value=0,
        )
        self.mock_email = self._email_patcher.start()
        self.mock_push = self._push_patcher.start()
        self.addCleanup(self._email_patcher.stop)
        self.addCleanup(self._push_patcher.stop)

        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Validación Pago',
            ciudad='CDMX',
        )
        self.recepcion = self._crear_empleado(
            'recepcion.validacion@test.local',
            'Recepción Validación',
            'recepcionista',
        )
        self.facturacion = self._crear_empleado(
            'facturacion.validacion@test.local',
            'Facturación Validación',
            'facturacion',
        )
        self.facturacion_2 = self._crear_empleado(
            'facturacion2.validacion@test.local',
            'Facturación Dos',
            'facturacion',
        )
        self.responsable = self._crear_empleado(
            'responsable.validacion@test.local',
            'Responsable Seguimiento',
            'dispatcher',
        )
        self.orden = self._crear_orden_con_cotizacion(
            self.recepcion,
            responsable=self.responsable,
        )

    def _crear_empleado(self, email, nombre, rol):
        """
        User + Empleado activos con el rol indicado.

        Args:
            email: username y correo.
            nombre: nombre_completo.
            rol: código de Empleado.ROL_CHOICES.

        Returns:
            Empleado recargado con user.
        """
        user = User.objects.create_user(
            username=email,
            email=email,
            password='testpass123',
        )
        empleado = Empleado.objects.create(
            nombre_completo=nombre,
            cargo=rol,
            area='FRONTDESK',
            email=email,
            sucursal=self.sucursal,
            user=user,
            rol=rol,
            activo=True,
            contraseña_configurada=True,
        )
        return Empleado.objects.select_related('user').get(pk=empleado.pk)

    def _crear_orden_con_cotizacion(self, tecnico, responsable=None):
        """
        Orden con pieza aceptada (total MX 580) lista para cobrar.

        Args:
            tecnico: Empleado asignado como técnico.
            responsable: Empleado o None.

        Returns:
            OrdenServicio.
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='cotizacion',
            tecnico_asignado_actual=tecnico,
            responsable_seguimiento=responsable,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='OOW-VAL-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-VAL-01',
            falla_principal='No enciende',
            gama='baja',
        )
        componente = ComponenteEquipo.objects.create(
            nombre='Pantalla Validación',
            tipo_equipo='laptop',
            activo=True,
        )
        cotizacion = Cotizacion.objects.create(
            orden=orden,
            costo_mano_obra=Decimal('100.00'),
            usuario_acepto=True,
        )
        PiezaCotizada.objects.create(
            cotizacion=cotizacion,
            componente=componente,
            cantidad=1,
            costo_unitario=Decimal('200.00'),
            precio_unitario_cliente=Decimal('500.00'),
            aceptada_por_cliente=True,
        )
        return orden

    def _registrar(self, metodo, empleado=None, monto='290.00'):
        """
        Atajo para registrar un abono de prueba.

        Args:
            metodo: transferencia / tarjeta / efectivo / otro.
            empleado: quién cobra; por default Recepción.
            monto: string o Decimal.

        Returns:
            PagoOrden.
        """
        return registrar_pago(
            orden=self.orden,
            empleado=empleado or self.recepcion,
            monto=Decimal(monto),
            tipo='anticipo',
            metodo=metodo,
            codigo_pais='MX',
        )

    def test_transferencia_nace_pendiente(self):
        """Feliz: SPEI queda pendiente de Facturación."""
        pago = self._registrar('transferencia')
        self.assertEqual(pago.estado_validacion, 'pendiente')

    def test_tarjeta_nace_pendiente(self):
        """Feliz: tarjeta también se concilia contra la cuenta."""
        pago = self._registrar('tarjeta')
        self.assertEqual(pago.estado_validacion, 'pendiente')

    def test_efectivo_no_aplica(self):
        """Borde: efectivo de caja no pide validación."""
        pago = self._registrar('efectivo')
        self.assertEqual(pago.estado_validacion, 'no_aplica')

    def test_registrar_transferencia_avisa_a_facturacion(self):
        """Feliz: Recepción cobra por SPEI → se avisa a Facturación."""
        self.mock_push.return_value = 2
        self._registrar('transferencia')
        self.mock_push.assert_called_once()
        destinatarios = list(self.mock_push.call_args[0][0])
        ids = {empleado.pk for empleado in destinatarios}
        self.assertIn(self.facturacion.pk, ids)
        self.assertIn(self.facturacion_2.pk, ids)
        self.assertNotIn(self.recepcion.pk, ids)
        self.mock_email.assert_called_once()

    def test_efectivo_no_avisa(self):
        """Borde: un cobro en caja no dispara el flujo de Facturación."""
        self._registrar('efectivo')
        self.mock_push.assert_not_called()
        self.mock_email.assert_not_called()

    def test_facturacion_que_cobra_no_se_avisa_a_si_misma(self):
        """
        Borde: si Facturación registra el pago, ella no entra en la lista.
        El resto del área sí.
        """
        pago = self._registrar('transferencia', empleado=self.facturacion)
        destinos = destinatarios_pago_pendiente(pago)
        ids = {empleado.pk for empleado in destinos}
        self.assertNotIn(self.facturacion.pk, ids)
        self.assertIn(self.facturacion_2.pk, ids)

    def test_validado_avisa_al_responsable(self):
        """Feliz: al validar, el destinatario es el responsable de seguimiento."""
        pago = self._registrar('transferencia')
        destinos = destinatarios_pago_validado(pago)
        self.assertEqual([empleado.pk for empleado in destinos], [self.responsable.pk])

    def test_validado_sin_responsable_cae_a_recepcion(self):
        """Borde: sin responsable, avisamos a recepcionistas activos."""
        self.orden.responsable_seguimiento = None
        self.orden.save(update_fields=['responsable_seguimiento'])
        pago = self._registrar('tarjeta')
        destinos = destinatarios_pago_validado(pago)
        ids = {empleado.pk for empleado in destinos}
        self.assertIn(self.recepcion.pk, ids)
        self.assertNotIn(self.responsable.pk, ids)

    def test_no_aparece_avisa_a_quien_registro(self):
        """Feliz: si no está en la cuenta, se avisa a Recepción (quien cobró)."""
        pago = self._registrar('transferencia')
        destinos = destinatarios_pago_no_aparece(
            pago,
            quien_marco=self.facturacion,
        )
        self.assertEqual([empleado.pk for empleado in destinos], [self.recepcion.pk])

    def test_no_aparece_no_autoavisa_si_facturacion_cobro(self):
        """Borde: Facturación cobró y ella misma marca no aparece → silencio."""
        pago = self._registrar('transferencia', empleado=self.facturacion)
        destinos = destinatarios_pago_no_aparece(
            pago,
            quien_marco=self.facturacion,
        )
        self.assertEqual(destinos, [])

    def test_validar_en_cuenta_escribe_historial(self):
        """Feliz: Facturación marca validado y queda auditoría + historial."""
        self.mock_push.return_value = 1
        pago = self._registrar('transferencia')
        actualizado = validar_pago_en_cuenta(
            pago,
            self.facturacion,
            aparece=True,
        )
        self.assertEqual(actualizado.estado_validacion, 'validado')
        self.assertEqual(actualizado.validado_por, self.facturacion)
        self.assertIsNotNone(actualizado.fecha_validacion)
        self.assertTrue(
            HistorialOrden.objects.filter(
                orden=self.orden,
                comentario__icontains='validado en la cuenta',
            ).exists(),
        )
        self.mock_push.assert_called()
        self.mock_email.assert_called()

    def test_no_se_valida_un_efectivo(self):
        """Borde: no se puede 'validar' un pago de caja."""
        pago = self._registrar('efectivo')
        with self.assertRaises(ValidationError) as ctx:
            validar_pago_en_cuenta(pago, self.facturacion, aparece=True)
        self.assertIn('no requiere validación', str(ctx.exception).lower())

    def test_no_se_revalida_un_pago_ya_validado(self):
        """Borde: una vez validado, no se vuelve a decidir."""
        pago = self._registrar('transferencia')
        validar_pago_en_cuenta(pago, self.facturacion, aparece=True)
        pago.refresh_from_db()
        with self.assertRaises(ValidationError):
            validar_pago_en_cuenta(pago, self.facturacion, aparece=False)


class ValidacionPagoHttpTest(TestCase):
    """
    POST a detalle_orden: Facturación valida; Recepción no.

    Efectos: usuarios, permisos, orden y un pago pendiente.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self._email_patcher = patch(
            'servicio_tecnico.services.notificaciones_pagos._encolar_email_validacion',
        )
        self._push_patcher = patch(
            'servicio_tecnico.services.notificaciones_pagos.enviar_push_y_campanita',
            return_value=1,
        )
        self._email_patcher.start()
        self._push_patcher.start()
        self.addCleanup(self._email_patcher.stop)
        self.addCleanup(self._push_patcher.stop)

        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Validación HTTP',
            ciudad='CDMX',
        )
        self.user_recepcion = self._crear_usuario(
            'recepcion.val.http@test.local',
            'Recepción HTTP',
            'recepcionista',
            con_add_pago=True,
        )
        self.user_facturacion = self._crear_usuario(
            'facturacion.val.http@test.local',
            'Facturación HTTP',
            'facturacion',
            con_add_pago=True,
        )
        self.user_tecnico = self._crear_usuario(
            'tecnico.val.http@test.local',
            'Técnico HTTP',
            'tecnico',
            con_add_pago=False,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='cliente_acepta_cotizacion',
            tecnico_asignado_actual=self.user_tecnico.empleado,
            responsable_seguimiento=self.user_recepcion.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-VAL-H-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Inspiron',
            numero_serie='SN-VAL-H-01',
            falla_principal='Teclado',
            gama='baja',
        )
        componente = ComponenteEquipo.objects.create(
            nombre='Teclado Validación HTTP',
            tipo_equipo='laptop',
            activo=True,
        )
        cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('100.00'),
            usuario_acepto=True,
        )
        PiezaCotizada.objects.create(
            cotizacion=cotizacion,
            componente=componente,
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
        User + Empleado con view_ordenservicio y, si aplica, add_pagoorden.

        Args:
            email: username/email.
            nombre: nombre_completo.
            rol: código de rol.
            con_add_pago: True para recepción/facturación.

        Returns:
            User recargado.
        """
        user = User.objects.create_user(
            username=email,
            email=email,
            password='testpass123',
        )
        Empleado.objects.create(
            nombre_completo=nombre,
            cargo=rol,
            area='FRONTDESK',
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
        POST autenticado con session + messages.

        Args:
            user: User que envía el form.
            data: campos POST.

        Returns:
            HttpResponse del dispatcher.
        """
        request = self.factory.post(self.url, data=data)
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        self._ultima_request = request
        return detalle_orden(request, orden_id=self.orden.pk)

    def test_recepcion_no_puede_validar(self):
        """Borde: Recepción cobra, pero no concilia la cuenta."""
        self.assertFalse(usuario_puede_validar_pago(self.user_recepcion))
        pago = registrar_pago(
            self.orden,
            self.user_recepcion.empleado,
            Decimal('290.00'),
            'anticipo',
            'transferencia',
            codigo_pais='MX',
        )
        response = self._post(self.user_recepcion, {
            'form_type': 'validar_pago',
            'pago_id': str(pago.pk),
            'decision': 'validado',
        })
        self.assertEqual(response.status_code, 302)
        pago.refresh_from_db()
        self.assertEqual(pago.estado_validacion, 'pendiente')
        textos = [str(m.message) for m in self._ultima_request._messages]
        self.assertTrue(any('permiso' in t.lower() for t in textos))

    def test_facturacion_valida_por_post(self):
        """Feliz: Facturación marca 'Ya aparece' desde el detalle."""
        pago = registrar_pago(
            self.orden,
            self.user_recepcion.empleado,
            Decimal('290.00'),
            'anticipo',
            'transferencia',
            codigo_pais='MX',
        )
        response = self._post(self.user_facturacion, {
            'form_type': 'validar_pago',
            'pago_id': str(pago.pk),
            'decision': 'validado',
            'nota_validacion': 'SPEI visible en BBVA',
        })
        self.assertEqual(response.status_code, 302)
        pago.refresh_from_db()
        self.assertEqual(pago.estado_validacion, 'validado')
        self.assertEqual(pago.validado_por, self.user_facturacion.empleado)
        self.assertEqual(pago.nota_validacion, 'SPEI visible en BBVA')
        self.assertTrue(usuario_puede_validar_pago(self.user_facturacion))

    def test_facturacion_marca_no_aparece_por_post(self):
        """Feliz: Facturación marca que aún no se ve; el pago no se borra."""
        pago = registrar_pago(
            self.orden,
            self.user_recepcion.empleado,
            Decimal('290.00'),
            'anticipo',
            'tarjeta',
            codigo_pais='MX',
        )
        response = self._post(self.user_facturacion, {
            'form_type': 'validar_pago',
            'pago_id': str(pago.pk),
            'decision': 'no_aparece',
            'nota_validacion': 'Sin movimiento hoy',
        })
        self.assertEqual(response.status_code, 302)
        pago.refresh_from_db()
        self.assertEqual(pago.estado_validacion, 'no_aparece')
        self.assertEqual(PagoOrden.objects.filter(orden=self.orden).count(), 1)
        textos = [str(m.message) for m in self._ultima_request._messages]
        self.assertTrue(any('no aparece' in t.lower() for t in textos))
