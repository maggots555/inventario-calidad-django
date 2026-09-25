"""
Tests del HTML del correo de incidencia de Score Card.

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo. Solo se rellena la plantilla para comprobar que
ya es un correo de tablas y que crítico, bajo y reincidencia no se mezclan.
"""

from datetime import date
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


PLANTILLA = 'scorecard/emails/notificacion_incidencia.html'


def _incidencia(**overrides) -> SimpleNamespace:
    """
    Incidencia falsa con los campos que el HTML lee.

    Args:
        **overrides: Campos a cambiar (severidad, orden, reincidencia).

    Returns:
        SimpleNamespace: Incidencia lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    incidencia = SimpleNamespace(
        folio='INC-9',
        grado_severidad='critico',
        get_grado_severidad_display=lambda: 'Crítico',
        get_tipo_equipo_display=lambda: 'Laptop',
        marca='Dell',
        modelo='Latitude',
        numero_serie='SN-9',
        numero_orden='OOW-9',
        servicio_realizado=SimpleNamespace(nombre='Reparación'),
        sucursal=SimpleNamespace(nombre='Satélite'),
        area_detectora='Calidad',
        tecnico_responsable=SimpleNamespace(nombre_completo='Luis Técnico'),
        area_tecnico='Taller',
        inspector_calidad='Marta Inspector',
        tipo_incidencia=SimpleNamespace(nombre='Daño estético'),
        get_categoria_fallo_display=lambda: 'Proceso',
        componente_afectado=SimpleNamespace(nombre='Cubierta'),
        fecha_deteccion=date(2026, 9, 24),
        descripcion_incidencia='Rayón en la tapa.',
        acciones_tomadas='Se documentó con foto.',
        causa_raiz='Manipulación.',
        es_reincidencia=False,
        incidencia_relacionada=None,
    )
    for clave, valor in overrides.items():
        setattr(incidencia, clave, valor)
    return incidencia


class NotificacionIncidenciaEmailTemplateTests(SimpleTestCase):
    """El HTML de incidencia debe ser correo de tablas y conservar el aviso."""

    def test_critico_es_correo_interno(self):
        """Crítico: folio, equipo, reincidencia y pie, sin CSS de página."""
        html = render_to_string(
            PLANTILLA,
            {
                'incidencia': _incidencia(
                    es_reincidencia=True,
                    incidencia_relacionada=SimpleNamespace(folio='INC-1'),
                ),
                'mensaje_adicional': 'Revisar hoy.',
                'evidencias': [SimpleNamespace(), SimpleNamespace()],
            },
        )

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('Notificación de Incidencia', html)
        self.assertIn('Sistema de Control de Calidad - Score Card', html)
        self.assertIn('INC-9', html)
        self.assertIn('CRÍTICO', html)
        self.assertIn('#b91c1c', html)
        self.assertIn('Laptop', html)
        self.assertIn('SN-9', html)
        self.assertIn('OOW-9', html)
        self.assertIn('Reparación', html)
        self.assertIn('Satélite', html)
        self.assertIn('Luis Técnico', html)
        self.assertIn('Daño estético', html)
        self.assertIn('24/09/2026', html)
        self.assertIn('Rayón en la tapa.', html)
        self.assertIn('Acciones Tomadas:', html)
        self.assertIn('Causa Raíz:', html)
        self.assertIn('Revisar hoy.', html)
        self.assertIn('2 imagen(es) adjunta(s)', html)
        self.assertIn('INC-1', html)
        self.assertIn('Hecho por Jorge Magos', html)
        self.assertIn('no responda a este correo', html)
        self.assertNotIn('display:grid', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('instagram.com', html)

    def test_bajo_omite_bloques_vacios(self):
        """Bajo: sin orden, sin acciones y sin fotos no pinta esas secciones."""
        html = render_to_string(
            PLANTILLA,
            {
                'incidencia': _incidencia(
                    grado_severidad='bajo',
                    get_grado_severidad_display=lambda: 'Bajo',
                    numero_orden='',
                    servicio_realizado=None,
                    area_tecnico='',
                    componente_afectado=None,
                    acciones_tomadas='',
                    causa_raiz='',
                ),
                'mensaje_adicional': '',
                'evidencias': [],
            },
        )

        self.assertIn('BAJO', html)
        self.assertIn('#166534', html)
        self.assertIn('N/A', html)
        self.assertNotIn('Orden Cliente', html)
        self.assertNotIn('Servicio Realizado', html)
        self.assertNotIn('Acciones Tomadas:', html)
        self.assertNotIn('Causa Raíz:', html)
        self.assertNotIn('Mensaje Adicional', html)
        self.assertNotIn('Evidencias Fotográficas', html)
        self.assertNotIn('ATENCIÓN:', html)
        self.assertNotIn('CRÍTICO', html)
