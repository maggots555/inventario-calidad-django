"""
Tests de la plantilla HTML y del texto plano de equipo disponible.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No se envía correo SMTP real en estos tests de plantilla. Solo se rellena
el HTML y el text/plain para no romper los {% if %} (Service Tag, cláusula 6).
"""

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_equipo_disponible import (
    construir_texto_plano_equipo_disponible,
)


PLANTILLA = 'servicio_tecnico/emails/equipo_disponible_cliente.html'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_notificacion_equipo_disponible_task.

    Args:
        **overrides: Claves a cambiar (cláusula 6, Service Tag, etc.).

    Returns:
        dict: Contexto para render_to_string.
    """
    contexto = {
        'nombre_cliente': 'Ana Pérez',
        'folio': 'OOW-5005',
        'service_tag': 'ST-5005',
        'tipo_equipo': 'Laptop',
        'marca_equipo': 'Dell',
        'modelo_equipo': 'Latitude 5520',
        'horario_atencion': 'Lunes a Viernes de 09:00 a 17:30 hrs horario corrido.',
        'sucursal_nombre': 'Sucursal Satélite',
        'sucursal_direccion': 'Circuito Economistas 15-A',
        'sucursal_ciudad_estado': 'Naucalpan, Estado de México',
        'sucursal_telefono': '5555555555',
        'sucursal_horario_extra': '',
        'es_fuera_garantia': True,
    }
    contexto.update(overrides)
    return contexto


class EquipoDisponibleEmailTemplateTests(SimpleTestCase):
    """El HTML debe ser correo de tablas, paleta SIC, copy de recolección."""

    def test_render_base_incluye_recoleccion_y_layout(self):
        """Feliz OOW: invitación a recoger, sucursal, cláusula 6."""
        html = render_to_string(PLANTILLA, _contexto())
        html_plano = ' '.join(html.split())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('Equipo listo para recolección', html_plano)
        self.assertIn('Buen día estimado', html_plano)
        self.assertIn('Ana Pérez', html_plano)
        self.assertIn('listo para que pase a recolectar', html_plano)
        self.assertIn('formato digital', html_plano)
        self.assertIn('Laptop — Dell Latitude 5520', html_plano)
        self.assertIn('Folio: OOW-5005', html_plano)
        self.assertIn('Service Tag: ST-5005', html_plano)
        self.assertIn('COPIAS DE AMBAS CREDENCIALES', html_plano)
        self.assertIn('Le recuerdo los horarios de atención', html_plano)
        self.assertIn('Sucursal Satélite', html_plano)
        self.assertIn('Circuito Economistas 15-A', html_plano)
        self.assertIn('CLÁUSULA 6', html_plano)
        self.assertIn('ALMACENAJE O DESTRUCCIÓN', html_plano)
        self.assertIn('https://sicfix.mx', html_plano)
        self.assertIn('https://wa.me/523318189988', html_plano)
        self.assertIn('max-width:600px', html)
        self.assertIn('#1f6391', html)
        self.assertIn('cid:logo_sic', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)

    def test_garantia_omite_clausula_almacenaje(self):
        """Dentro de garantía no sale la cláusula 6."""
        html = render_to_string(PLANTILLA, _contexto(es_fuera_garantia=False))
        self.assertNotIn('CLÁUSULA 6', html)
        self.assertNotIn('ALMACENAJE O DESTRUCCIÓN', html)
        self.assertIn('listo para que pase a recolectar', html)

    def test_sin_service_tag_omite_fila(self):
        """Sin número de serie no se menciona Service Tag."""
        html = render_to_string(PLANTILLA, _contexto(service_tag=''))
        self.assertNotIn('Service Tag', html)

    def test_horario_extra_aparece_si_viene(self):
        """Horario extra de sucursal solo si el contexto lo trae."""
        html = render_to_string(
            PLANTILLA,
            _contexto(sucursal_horario_extra='Sábados 9-14'),
        )
        self.assertIn('Horario de la sucursal:', html)
        self.assertIn('Sábados 9-14', html)


class EquipoDisponibleTextoPlanoTests(SimpleTestCase):
    """El text/plain debe llevar recolección y la misma cláusula 6."""

    def test_oow_incluye_clausula_en_plano(self):
        """Feliz OOW: sucursal + cláusula 6 en texto plano."""
        texto = construir_texto_plano_equipo_disponible(_contexto())
        self.assertIn('listo para que pase a recolectar', texto)
        self.assertIn('OOW-5005', texto)
        self.assertIn('CLÁUSULA 6', texto)
        self.assertIn('ALMACENAJE O DESTRUCCIÓN', texto)
        self.assertIn('https://wa.me/523318189988', texto)

    def test_garantia_omite_clausula_en_plano(self):
        """Garantía: el plano invita a recoger y no menciona cláusula 6."""
        texto = construir_texto_plano_equipo_disponible(
            _contexto(es_fuera_garantia=False),
        )
        self.assertIn('listo para que pase a recolectar', texto)
        self.assertNotIn('CLÁUSULA 6', texto)
        self.assertNotIn('ALMACENAJE O DESTRUCCIÓN', texto)
