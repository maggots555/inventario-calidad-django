"""
Tests del HTML y del texto plano del correo de validación de pago.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo. Solo se rellena la plantilla para no romper los
tres avisos (pendiente, validado, no aparece) ni el botón.
"""

from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_validacion_pago import (
    construir_texto_plano_validacion_pago,
)


PLANTILLA = 'servicio_tecnico/emails/validacion_pago.html'
URL_BANDEJA = 'https://app.sigmasystem.work/servicio-tecnico/pagos/'
URL_ORDEN = 'https://app.sigmasystem.work/servicio-tecnico/orden/9/#seccionPagos'


def _pago(**overrides):
    """
    Pago de mentira con los métodos que la plantilla llama.

    Args:
        **overrides: Campos a cambiar (notas, monto, etc.).

    Returns:
        SimpleNamespace: Pago listo para el template.
    """
    pago = SimpleNamespace(
        monto=1500,
        notas='',
        nota_validacion='',
        registrado_por=SimpleNamespace(nombre_completo='Ana Recepción'),
        get_metodo_display=lambda: 'Transferencia',
        get_tipo_display=lambda: 'Anticipo',
    )
    for clave, valor in overrides.items():
        setattr(pago, clave, valor)
    return pago


def _contexto(**overrides):
    """
    Contexto mínimo igual al de notificar_validacion_pago_task.

    Args:
        **overrides: Claves a cambiar (evento, folios, etc.).

    Returns:
        dict: Contexto para render_to_string.
    """
    contexto = {
        'pago': _pago(),
        'tipo_evento': 'pendiente',
        'url_pagos': URL_BANDEJA,
        'referencia_orden': 'FL-4401',
        'folio_cliente': 'FL-4401',
        'service_tag': 'SN-PAGO-1',
        'folio_interno': 'INT-4401',
        'ahora_local': datetime(2026, 9, 23, 17, 5),
    }
    contexto.update(overrides)
    return contexto


class ValidacionPagoEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas y respetar los tres avisos."""

    def test_pendiente_pide_bandeja(self):
        """Pendiente: texto de recepción y botón de la bandeja."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Pago pendiente de validar', html)
        self.assertIn('Recepción registró un abono', html)
        self.assertIn('Abrir bandeja de pagos', html)
        self.assertIn(URL_BANDEJA, html)
        self.assertIn('$1500.00', html)
        self.assertIn('Transferencia', html)
        self.assertIn('Anticipo', html)
        self.assertIn('FL-4401', html)
        self.assertIn('SN-PAGO-1', html)
        self.assertIn('INT-4401', html)
        self.assertIn('Ana Recepción', html)
        self.assertIn('Aviso interno de SIGMA', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('Pago validado en la cuenta', html)

    def test_validado_abre_cobros(self):
        """Validado: aviso de cuenta y botón de cobros, no la bandeja."""
        html = render_to_string(
            PLANTILLA,
            _contexto(tipo_evento='validado', url_pagos=URL_ORDEN),
        )
        self.assertIn('Pago validado en la cuenta', html)
        self.assertIn('ya aparece en la cuenta', html)
        self.assertIn('Abrir cobros de la orden', html)
        self.assertIn(URL_ORDEN, html)
        self.assertNotIn('Abrir bandeja de pagos', html)

    def test_no_aparece_conserva_el_aviso(self):
        """No aparece: pide revisar comprobante y abre cobros."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                tipo_evento='no_aparece',
                url_pagos=URL_ORDEN,
                folio_cliente='',
                service_tag='',
                pago=_pago(notas='Ref 9988', nota_validacion='No está en el estado de cuenta'),
            ),
        )
        self.assertIn('El pago aún no aparece en la cuenta', html)
        self.assertIn('corrígelo si hace falta', html)
        self.assertIn('Ref 9988', html)
        self.assertIn('No está en el estado de cuenta', html)
        self.assertNotIn('Folio cliente', html)
        self.assertNotIn('Service Tag', html)

    def test_sin_notas_omite_esas_filas(self):
        """Sin notas no se pintan las etiquetas vacías."""
        html = render_to_string(PLANTILLA, _contexto())
        self.assertNotIn('Notas del cobro', html)
        self.assertNotIn('Nota de Facturación', html)


class ValidacionPagoTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar la misma URL y el mismo aviso."""

    def test_plano_pendiente_incluye_bandeja(self):
        """Pendiente: URL de la bandeja y monto."""
        texto = construir_texto_plano_validacion_pago(_contexto())
        self.assertIn('Pago pendiente de validar', texto)
        self.assertIn('bandeja de pagos', texto)
        self.assertIn(URL_BANDEJA, texto)
        self.assertIn('$1500.00', texto)
        self.assertIn('Aviso interno de SIGMA', texto)

    def test_plano_no_aparece_incluye_nota(self):
        """No aparece: la nota de Facturación y la URL de cobros."""
        texto = construir_texto_plano_validacion_pago(
            _contexto(
                tipo_evento='no_aparece',
                url_pagos=URL_ORDEN,
                folio_cliente='',
                pago=_pago(nota_validacion='No está en el estado de cuenta'),
            ),
        )
        self.assertIn('aún no aparece', texto)
        self.assertIn('No está en el estado de cuenta', texto)
        self.assertIn(URL_ORDEN, texto)
        self.assertNotIn('Folio cliente:', texto)
