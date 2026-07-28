"""
Tests del rechazo total Almacén → motivo catálogo ST + feedback opcional.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1. Rechazar líneas (una o todas) con texto libre → estado totalmente_rechazada
2. Luego el modal pide motivo de catálogo ST + detalle (+ feedback opcional)
3. La vista `registrar_motivo_rechazo_st` escribe la cabecera ST

Usamos RequestFactory para evitar middleware multi-tenant / Axes.
"""

from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory, TestCase
from django.urls import reverse

from almacen.models import LineaCotizacion, ProductoAlmacen, SolicitudCotizacion
from almacen.utils.sincronizar_rechazo_cotizacion_st import (
    solicitud_requiere_motivo_rechazo_st,
)
from almacen.views import rechazar_todas_lineas, registrar_motivo_rechazo_st, responder_linea_cotizacion
from inventario.models import Empleado, Sucursal
from scorecard.models import ComponenteEquipo
from servicio_tecnico.models import Cotizacion, DetalleEquipo, FeedbackCliente, OrdenServicio, PiezaCotizada


User = get_user_model()


def _request_post(factory: RequestFactory, user, url: str, data: dict):
    """Arma un POST autenticado con sesión y messages."""
    request = factory.post(url, data)
    request.user = user
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    return request


class RechazoTotalSyncStTest(TestCase):
    """Objetivo: rechazo total dispara modal ST; el registro llena cabecera."""

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Rechazo Total',
            codigo='TST-RECH',
            activa=True,
            ciudad='CDMX',
            direccion='Calle Test 1',
            horario_atencion='Lun-Vie 9-18',
        )
        self.user = User.objects.create_user(
            username='front_rechazo',
            password='testpass123',
            is_superuser=True,
        )
        self.empleado = Empleado.objects.create(
            user=self.user,
            nombre_completo='Front Rechazo',
            cargo='Recepción',
            area='FRONTDESK',
            email='front.rechazo@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )
        self.componente = ComponenteEquipo.objects.get_or_create(
            nombre='RAM',
            defaults={'activo': True, 'tipo_equipo': 'todos'},
        )[0]

        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='cotizacion',
            tecnico_asignado_actual=self.empleado,
        )
        self.detalle = DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-RECH-TOTAL-01',
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='Latitude',
            numero_serie='STRECH001',
            email_cliente='cliente.rechazo@test.local',
        )
        self.solicitud = SolicitudCotizacion.objects.create(
            orden_servicio=self.orden,
            estado='enviada_cliente',
            creado_por=self.user,
        )
        self.cotizacion = Cotizacion.objects.get(orden=self.orden)

        self.producto = ProductoAlmacen.objects.create(
            codigo_producto='SKU-RAM-RECH-01',
            nombre='MEMORIA RAM DDR4 16GB TEST',
            tipo_producto='unico',
            costo_unitario=Decimal('100.00'),
            stock_actual=0,
        )
        self.linea = LineaCotizacion.objects.create(
            solicitud=self.solicitud,
            producto=self.producto,
            descripcion_pieza='MEMORIA RAM DDR4 16GB TEST',
            cantidad=1,
            costo_unitario=Decimal('100.00'),
            precio_unitario_cliente=Decimal('200.00'),
            estado_cliente='pendiente',
        )
        self.url_rechazar_todas = reverse(
            'almacen:rechazar_todas_lineas',
            kwargs={'pk': self.solicitud.pk},
        )
        self.url_registrar_motivo = reverse(
            'almacen:registrar_motivo_rechazo_st',
            kwargs={'pk': self.solicitud.pk},
        )

    def test_rechazar_todas_no_llena_motivo_catalogo_aun(self) -> None:
        """Rechazar todas solo marca líneas; el catálogo ST se registra después."""
        request = _request_post(
            self.factory,
            self.user,
            self.url_rechazar_todas,
            {'motivo': 'Cliente no quiere ninguna pieza'},
        )
        respuesta = rechazar_todas_lineas(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self.solicitud.refresh_from_db()
        self.linea.refresh_from_db()
        self.cotizacion.refresh_from_db()

        self.assertEqual(self.solicitud.estado, 'totalmente_rechazada')
        self.assertEqual(self.linea.estado_cliente, 'rechazada')
        self.assertEqual(self.linea.motivo_rechazo, 'Cliente no quiere ninguna pieza')
        self.assertEqual(self.cotizacion.motivo_rechazo, '')
        self.assertTrue(solicitud_requiere_motivo_rechazo_st(self.solicitud))

        pieza = PiezaCotizada.objects.filter(cotizacion=self.cotizacion).first()
        self.assertIsNotNone(pieza)
        assert pieza is not None
        self.assertIs(pieza.aceptada_por_cliente, False)
        self.assertEqual(pieza.motivo_rechazo_pieza, 'Cliente no quiere ninguna pieza')

    def test_rechazar_ultima_pieza_pide_motivo_st(self) -> None:
        """Rechazar la única pieza pendiente también deja pendiente el modal ST."""
        url = reverse(
            'almacen:responder_linea_cotizacion',
            kwargs={
                'solicitud_pk': self.solicitud.pk,
                'linea_pk': self.linea.pk,
            },
        )
        request = _request_post(
            self.factory,
            self.user,
            url,
            {
                'decision': 'rechazar',
                'motivo_rechazo': 'Solo esta pieza no le conviene',
            },
        )
        respuesta = responder_linea_cotizacion(
            request,
            self.solicitud.pk,
            self.linea.pk,
        )
        self.assertEqual(respuesta.status_code, 302)

        self.solicitud.refresh_from_db()
        self.cotizacion.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'totalmente_rechazada')
        self.assertEqual(self.cotizacion.motivo_rechazo, '')
        self.assertTrue(solicitud_requiere_motivo_rechazo_st(self.solicitud))

    def test_registrar_motivo_st_llena_cabecera(self) -> None:
        """Tras rechazo total, registrar motivo llena Cotizacion ST."""
        self.linea.rechazar(motivo='Texto libre de línea')
        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'totalmente_rechazada')

        detalle = (
            '[RAZÓN PRINCIPAL]: Presupuesto excedido\n'
            '[DETALLE]: Costo de $5000 supera el máximo'
        )
        request = _request_post(
            self.factory,
            self.user,
            self.url_registrar_motivo,
            {
                'motivo_rechazo': 'costo_alto',
                'detalle_rechazo': detalle,
            },
        )
        with patch('servicio_tecnico.tasks.enviar_feedback_rechazo_task.delay') as mock_delay:
            respuesta = registrar_motivo_rechazo_st(request, self.solicitud.pk)
            mock_delay.assert_not_called()

        self.assertEqual(respuesta.status_code, 302)
        self.cotizacion.refresh_from_db()
        self.assertIs(self.cotizacion.usuario_acepto, False)
        self.assertEqual(self.cotizacion.motivo_rechazo, 'costo_alto')
        self.assertEqual(self.cotizacion.detalle_rechazo, detalle)
        self.assertFalse(solicitud_requiere_motivo_rechazo_st(self.solicitud))
        self.assertEqual(FeedbackCliente.objects.count(), 0)

    @patch('config.paises_config.get_pais_actual', return_value={'db_alias': 'default'})
    @patch('servicio_tecnico.tasks.enviar_feedback_rechazo_task.delay')
    def test_checkbox_on_crea_feedback_y_encola(self, mock_delay, _mock_pais) -> None:
        """Al registrar motivo con checkbox ON → FeedbackCliente + delay."""
        self.linea.rechazar(motivo='Rechazo total')
        self.solicitud.refresh_from_db()

        request = _request_post(
            self.factory,
            self.user,
            self.url_registrar_motivo,
            {
                'motivo_rechazo': 'costo_alto',
                'detalle_rechazo': 'Detalle de prueba feedback',
                'enviar_feedback': 'on',
            },
        )
        respuesta = registrar_motivo_rechazo_st(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self.assertEqual(FeedbackCliente.objects.count(), 1)
        feedback = FeedbackCliente.objects.get()
        self.assertEqual(feedback.tipo, 'rechazo')
        self.assertEqual(feedback.motivo_rechazo_snapshot, 'costo_alto')
        mock_delay.assert_called_once()
        self.assertEqual(mock_delay.call_args.kwargs['feedback_id'], feedback.pk)

    @patch('servicio_tecnico.tasks.enviar_feedback_rechazo_task.delay')
    def test_motivo_sin_correo_no_crea_feedback(self, mock_delay) -> None:
        """Motivo no_apto no envía correo aunque el checkbox venga ON."""
        self.linea.rechazar(motivo='No reparable')
        self.solicitud.refresh_from_db()

        request = _request_post(
            self.factory,
            self.user,
            self.url_registrar_motivo,
            {
                'motivo_rechazo': 'no_apto',
                'detalle_rechazo': 'Equipo no reparable',
                'enviar_feedback': 'on',
            },
        )
        respuesta = registrar_motivo_rechazo_st(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)

        self.cotizacion.refresh_from_db()
        self.assertEqual(self.cotizacion.motivo_rechazo, 'no_apto')
        self.assertEqual(FeedbackCliente.objects.count(), 0)
        mock_delay.assert_not_called()

    @patch('config.paises_config.get_pais_actual', return_value={'db_alias': 'default'})
    @patch('servicio_tecnico.tasks.enviar_feedback_rechazo_task.delay')
    def test_segundo_envio_reutiliza_feedback(self, mock_delay, _mock_pais) -> None:
        """Reenviar feedback no crea un segundo FeedbackCliente."""
        self.linea.rechazar(motivo='Rechazo total')
        self.solicitud.refresh_from_db()

        datos = {
            'motivo_rechazo': 'costo_alto',
            'detalle_rechazo': 'Detalle',
            'enviar_feedback': 'on',
        }
        request1 = _request_post(
            self.factory, self.user, self.url_registrar_motivo, datos,
        )
        registrar_motivo_rechazo_st(request1, self.solicitud.pk)
        self.assertEqual(FeedbackCliente.objects.count(), 1)
        feedback_id = FeedbackCliente.objects.get().pk

        request2 = _request_post(
            self.factory, self.user, self.url_registrar_motivo, datos,
        )
        registrar_motivo_rechazo_st(request2, self.solicitud.pk)
        self.assertEqual(FeedbackCliente.objects.count(), 1)
        self.assertEqual(FeedbackCliente.objects.get().pk, feedback_id)
        self.assertEqual(mock_delay.call_count, 2)

    def test_venta_mostrador_no_requiere_motivo_st(self) -> None:
        """Órdenes FL- no muestran/usan el flujo de Cotizacion ST."""
        from almacen.utils.sincronizar_rechazo_cotizacion_st import (
            orden_admite_cotizacion_st,
            sincronizar_cabecera_rechazo_st,
            solicitud_requiere_motivo_rechazo_st,
        )

        self.orden.tipo_servicio = 'venta_mostrador'
        self.orden.save(update_fields=['tipo_servicio'])
        self.solicitud.estado = 'totalmente_rechazada'
        self.solicitud.save(update_fields=['estado'])

        self.assertFalse(orden_admite_cotizacion_st(self.orden))
        self.assertFalse(solicitud_requiere_motivo_rechazo_st(self.solicitud))
        # No debe tocar ni crear cabecera ST en FL-
        motivo_antes = Cotizacion.objects.get(orden=self.orden).motivo_rechazo
        self.assertIsNone(
            sincronizar_cabecera_rechazo_st(
                self.solicitud,
                motivo_clave='costo_alto',
                detalle_rechazo='x',
            )
        )
        self.assertEqual(
            Cotizacion.objects.get(orden=self.orden).motivo_rechazo,
            motivo_antes,
        )

    def test_registrar_motivo_sin_estado_total_falla(self) -> None:
        """No se puede registrar catálogo ST si aún no está totalmente rechazada."""
        request = _request_post(
            self.factory,
            self.user,
            self.url_registrar_motivo,
            {'motivo_rechazo': 'costo_alto', 'detalle_rechazo': 'x'},
        )
        respuesta = registrar_motivo_rechazo_st(request, self.solicitud.pk)
        self.assertEqual(respuesta.status_code, 302)
        self.cotizacion.refresh_from_db()
        self.assertEqual(self.cotizacion.motivo_rechazo, '')
        self.assertFalse(solicitud_requiere_motivo_rechazo_st(self.solicitud))
