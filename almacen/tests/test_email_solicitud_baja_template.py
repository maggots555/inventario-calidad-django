"""
Tests del HTML de los correos de solicitud de baja.

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo. Solo se rellena la plantilla para comprobar que
ya son avisos internos de tablas y que aprobar y rechazar no se mezclan.
"""

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


URL_PROCESAR = 'https://mexico.sigmasystem.work/almacen/solicitudes-baja/9/procesar/'
URL_LISTA = 'https://mexico.sigmasystem.work/almacen/solicitudes-baja/'


def _solicitud(**overrides) -> SimpleNamespace:
    """
    Solicitud de baja falsa con los campos que los HTML leen.

    Args:
        **overrides: Campos a cambiar.

    Returns:
        SimpleNamespace: Solicitud lista para el template.

    Efectos secundarios:
        Ninguno.
    """
    solicitud = SimpleNamespace(
        pk=9,
        cantidad=2,
        observaciones='Pantalla estrellada',
        observaciones_agente='',
        tecnico_asignado=SimpleNamespace(nombre_completo='Luis Técnico'),
        producto=SimpleNamespace(codigo_producto='P-15', nombre='Pantalla 15'),
        get_tipo_solicitud_display=lambda: 'Dañado',
    )
    for clave, valor in overrides.items():
        setattr(solicitud, clave, valor)
    return solicitud


def _base(**overrides) -> dict:
    """
    Contexto común de los dos correos de baja.

    Args:
        **overrides: Claves a cambiar.

    Returns:
        dict: Contexto para render_to_string.

    Efectos secundarios:
        Ninguno.
    """
    contexto = {
        'solicitud': _solicitud(),
        'nombre_solicitante': 'Marta Front',
        'folio_interno': 'INT-9',
        'folio_cliente': 'OOW-9',
        'tiene_orden': True,
        'fecha_envio_texto': '24/09/2026',
        'hora_envio_texto': '16:00',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
    }
    contexto.update(overrides)
    return contexto


class NuevaSolicitudBajaEmailTemplateTests(SimpleTestCase):
    """El aviso nuevo debe ser correo interno y conservar la petición."""

    def test_con_orden_es_correo_interno(self):
        """Con orden: producto, técnico, motivo y botón, sin redes."""
        html = render_to_string(
            'almacen/emails/nueva_solicitud_baja.html',
            _base(url_procesar=URL_PROCESAR),
        )

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('Nueva solicitud de baja', html)
        self.assertIn('Pendiente de procesar', html)
        self.assertIn('Solicitud #9', html)
        self.assertIn('Equipo de Almacén,', html)
        self.assertIn('«Procesar»', html)
        self.assertIn('P-15 — Pantalla 15', html)
        self.assertIn('Dañado', html)
        self.assertIn('Marta Front', html)
        self.assertIn('INT-9', html)
        self.assertIn('OOW-9', html)
        self.assertIn('Luis Técnico', html)
        self.assertIn('Pantalla estrellada', html)
        self.assertIn('Procesar la petición', html)
        self.assertIn(URL_PROCESAR, html)
        self.assertIn('contacte al área de Almacén', html)
        self.assertNotIn('Sin orden vinculada', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('instagram.com', html)

    def test_sin_orden_omite_tecnico_y_motivo(self):
        """Sin orden ni técnico no se pintan esas filas."""
        html = render_to_string(
            'almacen/emails/nueva_solicitud_baja.html',
            _base(
                url_procesar=URL_PROCESAR,
                tiene_orden=False,
                folio_cliente='',
                solicitud=_solicitud(
                    tecnico_asignado=None,
                    observaciones='',
                ),
            ),
        )

        self.assertIn('Sin orden vinculada', html)
        self.assertNotIn('Orden interna:', html)
        self.assertNotIn('Orden cliente:', html)
        self.assertNotIn('Técnico:', html)
        self.assertNotIn('Motivo:', html)


class SolicitudBajaProcesadaEmailTemplateTests(SimpleTestCase):
    """Aprobada y rechazada deben conservar cada aviso."""

    def test_aprobada_es_verde_y_lleva_notas(self):
        """Aprobada: stock actualizado, notas y listado."""
        html = render_to_string(
            'almacen/emails/solicitud_baja_procesada.html',
            _base(
                es_aprobada=True,
                nombre_agente='Ana Almacén',
                url_lista=URL_LISTA,
                solicitud=_solicitud(observaciones_agente='Sale a transferencia'),
            ),
        )

        self.assertIn('#166534', html)
        self.assertIn('Solicitud de baja aprobada', html)
        self.assertIn('Aprobada', html)
        self.assertIn('Hola Marta Front,', html)
        self.assertIn('fue <strong>aprobada</strong>', html)
        self.assertIn('El stock quedó actualizado', html)
        self.assertIn('Ana Almacén', html)
        self.assertIn('Notas:', html)
        self.assertIn('Sale a transferencia', html)
        self.assertIn('Ver solicitudes', html)
        self.assertIn(URL_LISTA, html)
        self.assertNotIn('Solicitud de baja rechazada', html)
        self.assertNotIn('No se descontó stock', html)
        self.assertNotIn('instagram.com', html)

    def test_rechazada_es_roja_y_lleva_motivo(self):
        """Rechazada: no descuenta stock y el texto dice Motivo, no Notas."""
        html = render_to_string(
            'almacen/emails/solicitud_baja_procesada.html',
            _base(
                es_aprobada=False,
                nombre_agente='Ana Almacén',
                url_lista=URL_LISTA,
                tiene_orden=False,
                solicitud=_solicitud(observaciones_agente='No hay evidencia'),
            ),
        )

        self.assertIn('#b91c1c', html)
        self.assertIn('Solicitud de baja rechazada', html)
        self.assertIn('Rechazada', html)
        self.assertIn('fue <strong>rechazada</strong>', html)
        self.assertIn('No se descontó stock', html)
        self.assertIn('Motivo:', html)
        self.assertIn('No hay evidencia', html)
        self.assertIn('Sin orden vinculada', html)
        self.assertNotIn('Notas:', html)
        self.assertNotIn('El stock quedó actualizado', html)
