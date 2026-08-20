"""
Regresión: el PDF y el correo de cotización ya no mencionan el cargo de diagnóstico.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Antes, si la cotización era solo de servicios (México, sin piezas), salía un
recuadro rojo: "Este documento no incluye el cargo de diagnóstico...".
El cliente ya lo sabe al ingresar el equipo, así que se quitó.

Estos tests evitan que alguien lo vuelva a pegar por inercia.
"""

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from almacen.utils.pdf_cotizacion_cliente import PDFCotizacionCliente

# Frase ASCII que ReportLab deja legible en el PDF (sin la ó de "diagnóstico").
_FRASE_AVISO_ASCII = b'no incluye el cargo de'
_FRASE_AVISO_HTML = 'no incluye el cargo de diagnóstico'


def _solicitud_minima():
    """
    Falso modelo de SolicitudCotizacion, sin tocar la base de datos.

    Args:
        Ninguno.

    Returns:
        SimpleNamespace con los campos que el PDF lee en modo sin orden.
    """
    return SimpleNamespace(
        numero_solicitud='SC-TEST-001',
        orden_servicio=None,
        creado_por=None,
        nombre_cliente='Cliente Prueba',
        email_cliente='cliente@ejemplo.com',
        telefono_cliente='5550000000',
        rfc_cliente='',
        marca='',
        modelo='Latitude 3420',
        tipo_equipo='',
        service_tag='ABC123',
        get_marca_display=lambda: '',
        get_tipo_equipo_display=lambda: '',
    )


def _item_servicio_limpieza():
    """Ítem de servicio (sin pieza) para forzar el caso que antes mostraba el aviso."""
    return {
        'descripcion': 'Limpieza de equipo',
        'cantidad': 1,
        'costo_unitario': 580.0,
        'es_necesaria': True,
        'dias_entrega': 3,
        'es_servicio': True,
        'tipo_servicio': 'limpieza',
    }


class AvisoDiagnosticoCotizacionTest(SimpleTestCase):
    """El aviso de diagnóstico no debe reaparecer en PDF ni en correo."""

    def test_pdf_mexico_solo_servicios_no_menciona_cargo_diagnostico(self):
        """
        México + solo servicios: el PDF genera bien y no trae la frase del aviso.
        """
        gen = PDFCotizacionCliente(
            solicitud=_solicitud_minima(),
            tipo_servicio='estandar',
            items=[_item_servicio_limpieza()],
            titulo_propuesta='Cotización de prueba',
            pais_config={'codigo': 'MX', 'empresa_nombre': 'SIC México'},
        )
        resultado = gen.generar_pdf()

        self.assertTrue(resultado.get('success'), resultado.get('error'))
        pdf_bytes = resultado['buffer'].getvalue()
        self.assertGreater(len(pdf_bytes), 100)
        self.assertNotIn(_FRASE_AVISO_ASCII, pdf_bytes)

    def test_email_no_muestra_aviso_diagnostico_aunque_haya_paquete_plata(self):
        """
        El HTML del correo no lleva el aviso; sí puede mencionar Solución Plata.
        """
        html = render_to_string(
            'almacen/emails/cotizacion_cliente_final.html',
            {
                'solicitud': SimpleNamespace(numero_solicitud='SC-TEST-001'),
                'titulo_propuesta': 'Solución Plata',
                'info_equipo': None,
                'nombre_cliente': 'Cliente Prueba',
                'calculo': {
                    'precio_sin_iva': 1000.0,
                    'iva': 160.0,
                    'precio_con_iva': 1160.0,
                },
                'mensaje_personalizado': '',
                'fecha_envio_texto': '20/08/2026',
                'hora_envio_texto': '16:00',
                'empresa_nombre': 'SIC',
                'pais_nombre': 'México',
                'pais_codigo': 'MX',
                'cotizacion_email': None,
                'whatsapp_empleado': '',
                'nombre_usuario': 'Técnico',
                'incluir_descuento': False,
                'es_reacondicionado': False,
                'costeo_reac': {},
                'info_equipo_reac': {},
                'incluye_paquete_plata': True,
            },
        )

        self.assertNotIn(_FRASE_AVISO_HTML, html)
        self.assertNotIn('Aviso importante:', html)
        self.assertIn('Solución Plata', html)
        # Recuadro amarillo informativo (no rojo de alerta)
        self.assertIn('aviso-paquete-plata', html)
        self.assertIn('#fff8e1', html)
        self.assertNotIn('#C00000', html)
        self.assertNotIn('#FDECEC', html)

    def test_email_sin_paquete_plata_no_pinta_recuadro_aviso(self):
        """Sin Solución Plata no debe quedar recuadro de aviso en el correo."""
        html = render_to_string(
            'almacen/emails/cotizacion_cliente_final.html',
            {
                'solicitud': SimpleNamespace(numero_solicitud='SC-TEST-002'),
                'titulo_propuesta': 'Reparación estándar',
                'info_equipo': None,
                'nombre_cliente': 'Cliente Prueba',
                'calculo': {
                    'precio_sin_iva': 500.0,
                    'iva': 80.0,
                    'precio_con_iva': 580.0,
                },
                'mensaje_personalizado': '',
                'fecha_envio_texto': '20/08/2026',
                'hora_envio_texto': '16:00',
                'empresa_nombre': 'SIC',
                'pais_nombre': 'México',
                'pais_codigo': 'MX',
                'cotizacion_email': None,
                'whatsapp_empleado': '',
                'nombre_usuario': 'Técnico',
                'incluir_descuento': False,
                'es_reacondicionado': False,
                'costeo_reac': {},
                'info_equipo_reac': {},
                'incluye_paquete_plata': False,
            },
        )

        self.assertNotIn(_FRASE_AVISO_HTML, html)
        # El CSS de la clase puede existir; lo que no debe pintarse es el recuadro
        self.assertNotIn('<div class="aviso-paquete-plata">', html)
