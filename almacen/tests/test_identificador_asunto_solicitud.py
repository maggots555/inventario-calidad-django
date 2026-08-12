"""
Tests del identificador de asuntos de correos Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Regla de negocio:
    - Con orden vinculada → orden_cliente (ej. OOW-11902)
    - Sin orden → S/T: {service_tag}
    - Si falta dato → numero_solicitud

También validamos que el asunto sugerido del modal use la misma regla.
"""

from __future__ import annotations

from unittest.mock import patch

from django.test import TestCase

from almacen.tests.helpers_integracion_cotizacion import BaseIntegracionCotizacionMixin
from almacen.utils.cotizacion_email_context import (
    PREFIJO_ASUNTO_CORREO,
    construir_asunto_correo_default,
    identificador_asunto_solicitud,
)


class IdentificadorAsuntoSolicitudTest(BaseIntegracionCotizacionMixin, TestCase):
    """Reglas unitarias de identificador_asunto_solicitud."""

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='ASUNTO-ID')

    def test_con_orden_usa_orden_cliente(self) -> None:
        """Con orden vinculada el asunto lleva OOW-…, no el service tag."""
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-ASUNTO-01')
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_front',
        )
        solicitud.refresh_from_db()

        identificador = identificador_asunto_solicitud(solicitud)

        self.assertEqual(identificador, 'OOW-ASUNTO-01')
        self.assertNotIn('S/T:', identificador)
        # El número de serie del equipo NO debe mandar en el asunto
        self.assertNotIn(orden.detalle_equipo.numero_serie, identificador)

    def test_sin_orden_usa_service_tag(self) -> None:
        """Sin orden vinculada → prefijo S/T: + service_tag."""
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_front',
        )
        solicitud.service_tag = 'PYFHF888A'
        solicitud.save(update_fields=['service_tag'])

        identificador = identificador_asunto_solicitud(solicitud)

        self.assertEqual(identificador, 'S/T: PYFHF888A')

    def test_sin_orden_sin_tag_usa_numero_solicitud(self) -> None:
        """Sin orden y sin service_tag → fallback al número de solicitud."""
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=None,
            sin_orden_activa=True,
            estado='enviada_front',
        )
        solicitud.service_tag = ''
        solicitud.numero_orden_cliente = ''
        solicitud.save(update_fields=['service_tag', 'numero_orden_cliente'])

        identificador = identificador_asunto_solicitud(solicitud)

        self.assertEqual(identificador, solicitud.numero_solicitud)
        self.assertFalse(identificador.startswith('S/T:'))

    def test_modal_asunto_default_alineado(self) -> None:
        """construir_asunto_correo_default usa el mismo identificador."""
        orden = self._crear_orden_con_detalle(orden_cliente='OOW-MODAL-02')
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_cliente',
        )
        solicitud.refresh_from_db()

        asunto = construir_asunto_correo_default(solicitud, info_orden=None)

        self.assertEqual(
            asunto,
            f'{PREFIJO_ASUNTO_CORREO}OOW-MODAL-02',
        )


class NotificarFrontAsuntoIdentificadorTest(
    BaseIntegracionCotizacionMixin,
    TestCase,
):
    """Task Front: el subject usa orden_cliente o S/T según el caso."""

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='ASUNTO-FR')

    def test_front_con_orden_asunto_usa_orden_cliente(self) -> None:
        """Notificar Front con orden → subject con OOW-, no S/T del equipo."""
        from almacen.tasks import notificar_front_cotizacion_task

        orden = self._crear_orden_con_detalle(orden_cliente='OOW-FRONT-09')
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_front',
        )
        solicitud.refresh_from_db()

        capturados = []

        def _fake_send(self_msg, fail_silently=False):
            capturados.append(self_msg)
            return 1

        with patch('django.core.mail.EmailMessage.send', new=_fake_send):
            resultado = notificar_front_cotizacion_task.run(
                solicitud_id=solicitud.pk,
                destinatarios=[self.empleado.email],
                mensaje_personalizado='',
                usuario_id=self.user.pk,
                tipo_plantilla='cotizacion_lista',
                db_alias='default',
            )

        self.assertTrue(resultado.get('success'))
        self.assertEqual(len(capturados), 1)
        asunto = capturados[0].subject
        self.assertIn('OOW-FRONT-09', asunto)
        self.assertNotIn('S/T:', asunto)

    def test_pnc_cliente_con_orden_asunto_usa_orden_cliente(self) -> None:
        """PNC al cliente con orden → subject con orden_cliente."""
        from almacen.tasks import notificar_cliente_pnc_task

        orden = self._crear_orden_con_detalle(orden_cliente='OOW-PNC-ASUNTO')
        solicitud, _linea = self._crear_solicitud_con_linea(
            orden=orden,
            sin_orden_activa=False,
            estado='enviada_cliente',
        )
        solicitud.aviso_pnc_cliente_enviado = True
        solicitud.save(update_fields=['aviso_pnc_cliente_enviado'])
        solicitud.refresh_from_db()

        capturados = []

        def _fake_send(self_msg, fail_silently=False):
            capturados.append(self_msg)
            return 1

        with patch('django.core.mail.EmailMessage.send', new=_fake_send):
            resultado = notificar_cliente_pnc_task.run(
                solicitud_id=solicitud.pk,
                email_cliente='cliente.pnc@test.local',
                mensaje_personalizado='',
                copia_empleados=[],
                usuario_id=self.user.pk,
                db_alias='default',
            )

        self.assertTrue(resultado.get('success'))
        self.assertEqual(len(capturados), 1)
        asunto = capturados[0].subject
        self.assertTrue(asunto.startswith('⚠️'))
        self.assertIn('OOW-PNC-ASUNTO', asunto)
        self.assertNotIn('S/T:', asunto)
