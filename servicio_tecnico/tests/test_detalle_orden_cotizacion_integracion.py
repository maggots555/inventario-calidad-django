"""
Integración HTTP: cotización vía detalle_orden (Fase C).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Complementa el humo de test_detalle_orden_fase_c.py y el test de
guardar_mano_obra (gama). Aquí sí tocamos BD y el dispatcher real:

1) Feliz: generar_cotizacion crea Cotizacion + copia MO.
2) Borde: generar de nuevo no duplica (warning + redirect).
3) Feliz: aceptar cotización con pieza → estado cliente_acepta_cotizacion.
4) Feliz: rechazar con motivo de feedback → FeedbackCliente + keys en session.

No enviamos correos reales; el handler solo deja datos en session para el modal.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from scorecard.models import ComponenteEquipo
from servicio_tecnico.models import (
    Cotizacion,
    DetalleEquipo,
    FeedbackCliente,
    HistorialOrden,
    OrdenServicio,
    PiezaCotizada,
)
from servicio_tecnico.views import detalle_orden


User = get_user_model()


class DetalleOrdenCotizacionIntegracionTest(TestCase):
    """
    POST reales a detalle_orden para MO/cotización/decisión del cliente.

    Efectos: inserta sucursal, usuario, orden, cotización/piezas según el caso.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Cotiz Integración',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_cotiz_integracion',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Cotiz Integración',
            cargo='Técnico',
            area='Laboratorio',
            email='cotiz.integracion@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            contraseña_configurada=True,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type=ct,
                codename='view_ordenservicio',
            ),
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
            costo_mano_obra=Decimal('0.00'),
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-COTIZ-INT-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude 5420',
            numero_serie='SN-COTIZ-INT-01',
            email_cliente='cliente.cotiz.int@test.local',
            nombre_cliente='Cliente Cotiz Integración',
            falla_principal='No enciende',
            gama='baja',
        )
        self.componente = ComponenteEquipo.objects.create(
            nombre='Pantalla Integración Cotiz',
            tipo_equipo='laptop',
            activo=True,
        )
        self.url = reverse(
            'servicio_tecnico:detalle_orden',
            args=[self.orden.pk],
        )

    def _post(self, data: dict):
        """
        Arma POST autenticado con session persistente + messages.

        Args:
            data: Campos del formulario (incluye form_type).

        Returns:
            HttpResponse de detalle_orden (casi siempre redirect 302).
        """
        request = self.factory.post(self.url, data=data)
        request.user = self.user
        # SessionStore: permite leer feedback_pendiente_* después del handler.
        request.session = SessionStore()
        request.session.create()
        request._messages = FallbackStorage(request)
        # Guardamos la request para asserts de session en el test.
        self._ultima_request = request
        return detalle_orden(request, orden_id=self.orden.pk)

    def test_generar_cotizacion_copia_mo_y_no_cambia_estado(self):
        """
        Feliz: form_type=generar_cotizacion crea Cotizacion con la MO enviada.
        """
        response = self._post({
            'form_type': 'generar_cotizacion',
            'costo_mano_obra': '500.00',
        })
        self.assertEqual(response.status_code, 302)

        self.orden.refresh_from_db()
        self.assertTrue(hasattr(self.orden, 'cotizacion'))
        cotizacion = self.orden.cotizacion
        self.assertEqual(cotizacion.costo_mano_obra, Decimal('500.00'))
        self.assertEqual(self.orden.costo_mano_obra, Decimal('500.00'))
        # El handler documenta que NO cambia estado automáticamente.
        self.assertEqual(self.orden.estado, 'diagnostico')
        self.assertTrue(
            HistorialOrden.objects.filter(
                orden=self.orden,
                tipo_evento='cotizacion',
                comentario__icontains='Cotización generada',
            ).exists(),
        )

    def test_generar_cotizacion_duplicada_no_crea_otra(self):
        """
        Borde: si ya hay cotización, no se duplica el OneToOne.
        """
        Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('100.00'),
        )
        response = self._post({
            'form_type': 'generar_cotizacion',
            'costo_mano_obra': '999.00',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Cotizacion.objects.filter(orden=self.orden).count(), 1)
        self.orden.cotizacion.refresh_from_db()
        # No debe pisar la MO de la cotización existente en este camino.
        self.assertEqual(self.orden.cotizacion.costo_mano_obra, Decimal('100.00'))

    def test_aceptar_cotizacion_con_pieza_cambia_estado(self):
        """
        Feliz: aceptar + pieza seleccionada → cliente_acepta_cotizacion.
        """
        cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('400.00'),
        )
        pieza = PiezaCotizada.objects.create(
            cotizacion=cotizacion,
            componente=self.componente,
            cantidad=1,
            costo_unitario=Decimal('1200.00'),
            proveedor='Proveedor Test',
        )

        response = self._post({
            'form_type': 'gestionar_cotizacion',
            'accion': 'aceptar',
            'piezas_seleccionadas': [str(pieza.pk)],
        })
        self.assertEqual(response.status_code, 302)

        cotizacion.refresh_from_db()
        pieza.refresh_from_db()
        self.orden.refresh_from_db()
        self.assertTrue(cotizacion.usuario_acepto)
        self.assertTrue(pieza.aceptada_por_cliente)
        self.assertEqual(self.orden.estado, 'cliente_acepta_cotizacion')

    def test_rechazar_con_feedback_deja_session_y_crea_feedback(self):
        """
        Feliz: rechazo costo_alto + email → FeedbackCliente + session para modal.
        """
        cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('800.00'),
        )
        PiezaCotizada.objects.create(
            cotizacion=cotizacion,
            componente=self.componente,
            cantidad=1,
            costo_unitario=Decimal('2500.00'),
        )

        response = self._post({
            'form_type': 'gestionar_cotizacion',
            'accion': 'rechazar',
            'motivo_rechazo': 'costo_alto',
            'detalle_rechazo': 'Cliente indica presupuesto insuficiente.',
        })
        self.assertEqual(response.status_code, 302)

        cotizacion.refresh_from_db()
        self.orden.refresh_from_db()
        self.assertFalse(cotizacion.usuario_acepto)
        self.assertEqual(cotizacion.motivo_rechazo, 'costo_alto')
        self.assertEqual(self.orden.estado, 'rechazada')

        feedback = FeedbackCliente.objects.get(
            orden=self.orden,
            cotizacion=cotizacion,
            tipo='rechazo',
        )
        self.assertEqual(feedback.motivo_rechazo_snapshot, 'costo_alto')
        self.assertEqual(feedback.enviado_por, self.empleado)

        # El modal de confirmación lee estas keys en el siguiente GET.
        session = self._ultima_request.session
        self.assertEqual(session.get('feedback_pendiente_id'), feedback.pk)
        self.assertEqual(
            session.get('feedback_pendiente_email'),
            'cliente.cotiz.int@test.local',
        )

    def test_rechazar_vigencia_vencida_deja_session_sin_feedback(self):
        """
        Borde: falta_de_respuesta → session vigencia_*, sin FeedbackCliente.
        """
        cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('300.00'),
        )

        response = self._post({
            'form_type': 'gestionar_cotizacion',
            'accion': 'rechazar',
            'motivo_rechazo': 'falta_de_respuesta',
        })
        self.assertEqual(response.status_code, 302)

        self.assertFalse(
            FeedbackCliente.objects.filter(orden=self.orden).exists(),
        )
        session = self._ultima_request.session
        self.assertEqual(
            session.get('vigencia_vencida_orden_id'),
            self.orden.pk,
        )
        self.assertEqual(
            session.get('vigencia_vencida_email'),
            'cliente.cotiz.int@test.local',
        )
        # No debe quedar feedback_pendiente en este camino.
        self.assertIsNone(session.get('feedback_pendiente_id'))
        cotizacion.refresh_from_db()
        self.assertEqual(cotizacion.motivo_rechazo, 'falta_de_respuesta')
