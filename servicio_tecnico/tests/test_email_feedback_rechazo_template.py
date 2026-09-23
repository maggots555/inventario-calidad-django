"""
Tests de la plantilla HTML y del texto plano del correo de feedback de rechazo.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo. Solo se rellena el HTML y el text/plain para no
romper los {% if %} (piezas, mano de obra, modelo) ni perder el enlace.
"""

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.forms import FeedbackRechazoClienteForm
from servicio_tecnico.services.email_feedback_rechazo import (
    construir_texto_plano_feedback_rechazo,
)


PLANTILLA = 'servicio_tecnico/emails/feedback_rechazo.html'
URL = 'https://app.sigmasystem.work/feedback/token-rechazo/'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_feedback_rechazo_task.

    Args:
        **overrides: Claves a cambiar (sin piezas, sin mano de obra, etc.).

    Returns:
        dict: Contexto para render_to_string.
    """
    contexto = {
        'nombre_cliente': 'usuario',
        'folio': 'FL-8801',
        'marca_equipo': 'Dell',
        'modelo_equipo': 'XPS 13',
        'tipo_equipo': 'Laptop',
        'motivo_rechazo': 'Precio elevado',
        'piezas': [
            {
                'nombre_pieza': 'Pantalla',
                'costo_unitario': 1500,
                'cantidad': 1,
            },
        ],
        'monto_total_piezas': 1500,
        'monto_total': 1500,
        'feedback_url': URL,
        'dias_vigencia': 7,
        'fecha_envio': '14/09/2026',
    }
    contexto.update(overrides)
    return contexto


class FeedbackRechazoEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas, paleta SIC, y respetar los if."""

    def test_render_base_incluye_enlace_y_layout(self):
        """Feliz: folio, pieza, total, botón y layout de 600 px."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Tu opinión nos importa', html)
        self.assertIn('Nos gustaría conocer tu experiencia', html)
        self.assertIn('Estimado/a usuario,', html)
        self.assertNotIn('Estimado/a Estimado', html)
        self.assertIn('Tu comentario es completamente confidencial.', html)
        self.assertIn('FL-8801', html)
        self.assertIn('Laptop Dell', html)
        self.assertIn('XPS 13', html)
        self.assertIn('Precio elevado', html)
        self.assertIn('Pantalla', html)
        self.assertIn('$1500.00', html)
        self.assertNotIn('Mano de obra', html)
        self.assertIn('Total cotizado:', html)
        self.assertIn('Dejar mi comentario', html)
        self.assertIn(URL, html)
        self.assertIn('expira en 7 días', html)
        self.assertIn('anónima y confidencial', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('class="email-brandbar"', html)
        self.assertIn('bgcolor="#1e293b"', html)
        self.assertIn('fillcolor="#1f6391"', html)
        self.assertIn('https://wa.me/', html)
        self.assertIn('Sitio Web', html)
        self.assertIn('contacte directamente a su responsable.', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('#667eea', html)

    def test_sin_piezas_omite_tabla(self):
        """Sin piezas rechazadas no se pinta el detalle ni el total."""
        html = render_to_string(PLANTILLA, _contexto(piezas=[]))
        self.assertNotIn('Detalle de la cotización', html)
        self.assertNotIn('Total cotizado:', html)
        self.assertIn('Dejar mi comentario', html)

    def test_aunque_llegue_mano_de_obra_no_se_muestra(self):
        """Si el contexto trae mano de obra, el correo igual no la pinta."""
        html = render_to_string(
            PLANTILLA,
            _contexto(monto_mano_obra=570, monto_total=1500),
        )
        self.assertNotIn('Mano de obra', html)
        self.assertNotIn('$570.00', html)
        self.assertIn('$1500.00', html)

    def test_sin_modelo_no_inventa_equipo(self):
        """Sin modelo solo se muestran tipo y marca."""
        html = render_to_string(PLANTILLA, _contexto(modelo_equipo=''))
        self.assertIn('Laptop Dell', html)
        self.assertNotIn('XPS 13', html)


class FeedbackRechazoPaginaClienteTests(SimpleTestCase):
    """La página pública del comentario no debe listar la mano de obra."""

    def test_pagina_muestra_piezas_y_omite_mano_de_obra(self):
        """Feliz: se ve la pieza y el total de piezas, no la mano de obra."""
        pieza = SimpleNamespace(
            componente=SimpleNamespace(nombre='Pantalla'),
            costo_unitario=1500,
        )
        html = render_to_string(
            'servicio_tecnico/feedback_rechazo.html',
            {
                'estado': 'formulario',
                'form': FeedbackRechazoClienteForm(),
                'detalle': SimpleNamespace(
                    orden_cliente='FL-8801',
                    tipo_equipo='Laptop',
                    marca='Dell',
                    modelo='XPS 13',
                ),
                'orden': SimpleNamespace(numero_orden_interno='INT-8801'),
                'motivo_rechazo': 'Precio elevado',
                'piezas': [pieza],
                'monto_mano_obra': 570,
                'monto_total': 1500,
                'dias_restantes': 5,
            },
        )
        self.assertIn('Pantalla', html)
        self.assertIn('$1500.00', html)
        self.assertNotIn('Mano de obra', html)
        self.assertNotIn('$570.00', html)


class FeedbackRechazoTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar el mismo enlace y el mismo aviso."""

    def test_plano_incluye_url_y_piezas(self):
        """Feliz: URL, pieza y aviso de no responder. Sin mano de obra."""
        texto = construir_texto_plano_feedback_rechazo(_contexto())
        self.assertIn('Tu opinión nos importa', texto)
        self.assertIn('FL-8801', texto)
        self.assertIn('Pantalla | 1 | $1500.00', texto)
        self.assertNotIn('Mano de obra', texto)
        self.assertIn('Total cotizado: $1500.00', texto)
        self.assertIn(URL, texto)
        self.assertIn('expira en 7 días', texto)
        self.assertIn('NO RESPONDA', texto)
        self.assertIn('WhatsApp: https://wa.me/', texto)

    def test_plano_sin_piezas_omite_detalle(self):
        """Sin piezas el plano tampoco lista la cotización."""
        texto = construir_texto_plano_feedback_rechazo(_contexto(piezas=[]))
        self.assertNotIn('DETALLE DE LA COTIZACIÓN', texto)
        self.assertIn(URL, texto)
