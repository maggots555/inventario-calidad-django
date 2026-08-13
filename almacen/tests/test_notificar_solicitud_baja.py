"""
Tests: notificaciones al crear una SolicitudBaja.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando se envía el formulario de baja, el sistema debe:

- Push + campanita solo a rol Almacenista (ellos procesan)
- Correo To = almacenistas, CC = Compras + quien pidió
- El enlace lleva a procesar la solicitud
- Si falla el aviso, la baja igual queda guardada

Estos tests mockean push/campanita/Celery para no enviar nada real en CI.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from almacen.models import SolicitudBaja, UnidadInventario
from almacen.tests.helpers_integracion_cotizacion import (
    BaseIntegracionCotizacionMixin,
    request_post,
)
from almacen.utils.notificar_solicitud_baja import (
    armar_destinatarios_email,
    construir_mensaje_notificacion,
    notificar_nueva_solicitud_baja,
    url_relativa_procesar_solicitud,
)
from almacen.views import crear_solicitud
from inventario.models import Empleado

User = get_user_model()


@override_settings(
    # En tests no hay collectstatic: ManifestStaticFilesStorage rompe {% static %}
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class NotificarSolicitudBajaTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Destinatarios To/CC, mensaje con/sin orden, y gancho al crear.

    Objetivo de negocio:
        El almacenista se entera al instante; Compras y el solicitante
        quedan en copia del mismo correo, sin duplicar direcciones.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='NOTIF-BAJA')
        # El mixin deja stock en 0; el formulario rechaza cantidad > stock.
        self.producto.stock_actual = 10
        self.producto.save(update_fields=['stock_actual'])
        # El formulario exige unidades físicas disponibles aunque no se marquen.
        UnidadInventario.objects.create(
            producto=self.producto,
            marca='Test',
            modelo='NotifBaja',
            disponibilidad='disponible',
            sucursal_actual=self.sucursal,
            registrado_por=self.user,
        )

        self.user_almacen = User.objects.create_user(
            username='almacenista_notif_baja',
            password='testpass123',
            email='almacenista.notif@test.local',
        )
        self.empleado_almacen = Empleado.objects.create(
            user=self.user_almacen,
            nombre_completo='Almacenista Notif',
            cargo='Almacenista',
            area='ALMACEN',
            email='almacenista.notif@test.local',
            sucursal=self.sucursal,
            rol='almacenista',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )
        self.user_compras = User.objects.create_user(
            username='compras_notif_baja',
            password='testpass123',
            email='compras.notif.baja@test.local',
        )
        self.empleado_compras = Empleado.objects.create(
            user=self.user_compras,
            nombre_completo='Compras Notif Baja',
            cargo='Compras',
            area='COMPRAS',
            email='compras.notif.baja@test.local',
            sucursal=self.sucursal,
            rol='compras',
            activo=True,
            tiene_acceso_sistema=True,
            contraseña_configurada=True,
        )

    def _crear_solicitud_baja(self, *, orden=None) -> SolicitudBaja:
        """
        SolicitudBaja pendiente mínima (consumo interno o con orden).

        Args:
            orden: OrdenServicio o None.

        Returns:
            SolicitudBaja con solicitante = empleado del mixin (recepción).
        """
        tipo = 'servicio_tecnico' if orden is not None else 'consumo_interno'
        return SolicitudBaja.objects.create(
            tipo_solicitud=tipo,
            producto=self.producto,
            cantidad=2,
            orden_servicio=orden,
            solicitante=self.empleado,
            observaciones='Necesito la pieza para la reparación',
        )

    def test_armar_to_almacenista_cc_compras_y_solicitante(self) -> None:
        """
        To = almacenista; CC = Compras + quien pidió (emails distintos).
        """
        solicitud = self._crear_solicitud_baja()
        emails_to, emails_cc = armar_destinatarios_email(solicitud)

        self.assertEqual(emails_to, ['almacenista.notif@test.local'])
        self.assertEqual(
            set(emails_cc),
            {
                'compras.notif.baja@test.local',
                self.empleado.email.lower(),
            },
        )
        self.assertNotIn(emails_to[0], emails_cc)

    def test_solicitante_con_mismo_email_que_almacenista_no_duplica(self) -> None:
        """
        Si quien pide ya es almacenista (mismo email), no va otra vez en CC.
        """
        self.empleado.email = self.empleado_almacen.email
        self.empleado.save(update_fields=['email'])
        solicitud = self._crear_solicitud_baja()
        emails_to, emails_cc = armar_destinatarios_email(solicitud)

        self.assertEqual(emails_to, ['almacenista.notif@test.local'])
        self.assertEqual(emails_cc, ['compras.notif.baja@test.local'])

    def test_mismo_email_almacenista_y_compras_solo_en_to(self) -> None:
        """
        Un email compartido entre almacenista y Compras queda solo en To.
        """
        self.empleado_compras.email = self.empleado_almacen.email
        self.empleado_compras.save(update_fields=['email'])
        solicitud = self._crear_solicitud_baja()
        emails_to, emails_cc = armar_destinatarios_email(solicitud)

        self.assertEqual(emails_to, ['almacenista.notif@test.local'])
        self.assertEqual(emails_cc, [self.empleado.email.lower()])

    def test_url_relativa_es_procesar_solicitud(self) -> None:
        """El clic de push/campanita abre la pantalla de procesar."""
        solicitud = self._crear_solicitud_baja()
        url = url_relativa_procesar_solicitud(solicitud)
        self.assertEqual(
            url,
            reverse('almacen:procesar_solicitud', kwargs={'pk': solicitud.pk}),
        )

    def test_mensaje_incluye_folios_cuando_hay_orden(self) -> None:
        """Con orden vinculada: folio interno y folio cliente en el texto."""
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-NOTIF-BAJA-01')
        solicitud = self._crear_solicitud_baja(orden=orden)
        mensaje = construir_mensaje_notificacion(solicitud)

        self.assertIn(orden.numero_orden_interno, mensaje)
        self.assertIn('OOW-NOTIF-BAJA-01', mensaje)
        self.assertIn(self.producto.codigo_producto, mensaje)
        self.assertNotIn('Sin orden vinculada', mensaje)

    def test_mensaje_sin_orden_no_truena(self) -> None:
        """Consumo interno / transferencia: texto claro, sin excepción."""
        solicitud = self._crear_solicitud_baja(orden=None)
        mensaje = construir_mensaje_notificacion(solicitud)
        self.assertIn('Sin orden vinculada', mensaje)

    @patch('almacen.utils.notificar_solicitud_baja.enviar_push_y_campanita')
    @patch(
        'almacen.tasks_solicitud_baja.notificar_almacenista_solicitud_baja_task.delay'
    )
    def test_notificar_push_solo_almacenistas_y_encola_email(
        self,
        mock_delay,
        mock_push_campanita,
    ) -> None:
        """
        Push/campanita solo a almacenistas; Celery se encola una vez.
        """
        solicitud = self._crear_solicitud_baja()
        notificar_nueva_solicitud_baja(solicitud)

        mock_push_campanita.assert_called_once()
        empleados_notif = list(mock_push_campanita.call_args.args[0])
        self.assertEqual(len(empleados_notif), 1)
        self.assertEqual(empleados_notif[0].pk, self.empleado_almacen.pk)
        self.assertEqual(
            mock_push_campanita.call_args.kwargs['url'],
            reverse('almacen:procesar_solicitud', kwargs={'pk': solicitud.pk}),
        )
        mock_delay.assert_called_once()
        self.assertEqual(mock_delay.call_args.args[0], solicitud.pk)

    @patch('almacen.utils.notificar_solicitud_baja.enviar_push_y_campanita')
    @patch(
        'almacen.tasks_solicitud_baja.notificar_almacenista_solicitud_baja_task.delay'
    )
    def test_sin_almacenistas_igual_encola_si_hay_cc(
        self,
        mock_delay,
        mock_push_campanita,
    ) -> None:
        """
        Sin almacenistas: no hay push, pero el correo a CC sí se encola.
        """
        self.empleado_almacen.activo = False
        self.empleado_almacen.save(update_fields=['activo'])
        solicitud = self._crear_solicitud_baja()
        notificar_nueva_solicitud_baja(solicitud)

        mock_push_campanita.assert_not_called()
        mock_delay.assert_called_once()

    @patch('almacen.utils.notificar_solicitud_baja.enviar_push_y_campanita')
    @patch(
        'almacen.tasks_solicitud_baja.notificar_almacenista_solicitud_baja_task.delay'
    )
    def test_post_crear_solicitud_dispara_notificacion(
        self,
        mock_delay,
        mock_push_campanita,
    ) -> None:
        """
        POST válido del formulario: se crea la baja y se avisa a almacenistas.
        """
        url = reverse('almacen:crear_solicitud')
        request = request_post(
            self.factory,
            self.user,
            url,
            data={
                'tipo_solicitud': 'consumo_interno',
                'producto': str(self.producto.pk),
                'cantidad': '1',
                'observaciones': 'Prueba notificación desde el formulario',
            },
        )
        respuesta = crear_solicitud(request)

        self.assertEqual(respuesta.status_code, 302)
        solicitud = SolicitudBaja.objects.get(producto=self.producto)
        mock_push_campanita.assert_called_once()
        empleados_notif = list(mock_push_campanita.call_args.args[0])
        self.assertEqual(
            {e.rol for e in empleados_notif},
            {'almacenista'},
        )
        self.assertEqual(
            mock_push_campanita.call_args.kwargs['url'],
            reverse('almacen:procesar_solicitud', kwargs={'pk': solicitud.pk}),
        )
        mock_delay.assert_called_once()

    @patch(
        'almacen.utils.notificar_solicitud_baja.notificar_nueva_solicitud_baja',
        side_effect=RuntimeError('fallo simulado'),
    )
    def test_post_crea_solicitud_aunque_falle_el_aviso(
        self,
        mock_notificar,
    ) -> None:
        """
        Si el aviso explota, la solicitud igual queda guardada.
        """
        url = reverse('almacen:crear_solicitud')
        request = request_post(
            self.factory,
            self.user,
            url,
            data={
                'tipo_solicitud': 'consumo_interno',
                'producto': str(self.producto.pk),
                'cantidad': '1',
                'observaciones': 'Debe guardarse aunque falle el aviso',
            },
        )
        try:
            respuesta = crear_solicitud(request)
        except RuntimeError:
            self.fail(
                'La vista no debe dejar escapar el error del aviso; '
                'la solicitud ya está guardada.'
            )

        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(
            SolicitudBaja.objects.filter(producto=self.producto).exists()
        )
        mock_notificar.assert_called_once()
