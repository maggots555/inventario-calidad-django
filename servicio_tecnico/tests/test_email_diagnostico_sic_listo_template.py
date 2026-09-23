"""
Tests del HTML y del texto plano del correo de Diagnóstico SIC listo.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo. Solo se rellena la plantilla para no romper los
dos avisos (responsable y Compras) ni el extracto del SIC.
"""

from datetime import datetime

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_diagnostico_sic_listo import (
    construir_texto_plano_diagnostico_sic_listo,
)


PLANTILLA = 'servicio_tecnico/emails/diagnostico_sic_listo_staff.html'
URL = 'https://app.sigmasystem.work/servicio-tecnico/orden/12/'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de notificar_diagnostico_sic_listo_task.

    Args:
        **overrides: Claves a cambiar (audiencia, extracto, etc.).

    Returns:
        dict: Contexto para render_to_string.
    """
    contexto = {
        'audiencia': 'responsable',
        'referencia_orden': 'FL-5501',
        'folio_cliente': 'FL-5501',
        'service_tag': 'SN-SIC-1',
        'folio_interno': 'INT-5501',
        'nombre_cliente': 'Ana Pérez',
        'extracto_sic': 'Pantalla sin imagen.\nRevisar flex.',
        'url_detalle': URL,
        'ahora_local': datetime(2026, 9, 23, 17, 20),
    }
    contexto.update(overrides)
    return contexto


class DiagnosticoSicListoEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas y respetar las dos audiencias."""

    def test_responsable_pide_enviar_al_cliente(self):
        """Responsable: texto de compartir y botón de la orden."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Diagnóstico listo para compartir', html)
        self.assertIn('«Enviar diagnóstico»', html)
        self.assertIn('Abrir orden y enviar al cliente', html)
        self.assertIn(URL, html)
        self.assertIn('FL-5501', html)
        self.assertIn('SN-SIC-1', html)
        self.assertIn('INT-5501', html)
        self.assertIn('Ana Pérez', html)
        self.assertIn('Extracto del Diagnóstico SIC:', html)
        self.assertIn('Pantalla sin imagen.', html)
        self.assertIn('white-space:pre-wrap;">Pantalla sin imagen.', html)
        self.assertIn('Aviso interno de SIGMA — Servicio Técnico', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('cotizar piezas', html)

    def test_compras_pide_cotizar(self):
        """Compras: aviso de piezas y su botón, no el del responsable."""
        html = render_to_string(PLANTILLA, _contexto(audiencia='compras'))
        self.assertIn('Diagnóstico SIC disponible — cotizar piezas', html)
        self.assertIn('búsqueda o cotización de piezas', html)
        self.assertIn('Revisar piezas a cotizar', html)
        self.assertNotIn('Abrir orden y enviar al cliente', html)
        self.assertNotIn('«Enviar diagnóstico»', html)

    def test_sin_opcionales_omite_filas_y_extracto(self):
        """Sin folio, tag, cliente ni extracto no se pintan esas etiquetas."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                folio_cliente='',
                service_tag='',
                nombre_cliente='',
                extracto_sic='',
            ),
        )
        self.assertNotIn('Folio cliente', html)
        self.assertNotIn('Service Tag', html)
        self.assertNotIn('>Cliente<', html)
        self.assertNotIn('Extracto del Diagnóstico SIC:', html)
        self.assertIn('Folio interno', html)


class DiagnosticoSicListoTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar la misma URL y el mismo aviso."""

    def test_plano_responsable_incluye_url(self):
        """Responsable: URL de la orden y extracto."""
        texto = construir_texto_plano_diagnostico_sic_listo(_contexto())
        self.assertIn('Diagnóstico listo para compartir', texto)
        self.assertIn('«Enviar diagnóstico»', texto)
        self.assertIn(URL, texto)
        self.assertIn('Pantalla sin imagen.', texto)
        self.assertIn('Aviso interno de SIGMA — Servicio Técnico', texto)

    def test_plano_compras_omite_extracto_vacio(self):
        """Compras sin extracto: no inventa el bloque del SIC."""
        texto = construir_texto_plano_diagnostico_sic_listo(
            _contexto(audiencia='compras', extracto_sic='', folio_cliente=''),
        )
        self.assertIn('cotizar piezas', texto)
        self.assertIn('Revisar piezas a cotizar:', texto)
        self.assertNotIn('Extracto del Diagnóstico SIC:', texto)
        self.assertNotIn('Folio cliente:', texto)
