"""
Tests del HTML del correo de cotización final al cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
No se envía correo ni se genera PDF. Solo se rellena la plantilla
para comprobar que ya es un correo de tablas y que México, el
genérico y el reacondicionado siguen diciendo lo mismo.
"""

from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase


PLANTILLA = 'almacen/emails/cotizacion_cliente_final.html'


def _calculo() -> dict:
    """
    Totales falsos del resumen de reparación.

    Returns:
        dict: Subtotal, IVA y total con IVA.

    Efectos secundarios:
        Ninguno.
    """
    return {
        'precio_sin_iva': 1000.0,
        'iva': 160.0,
        'precio_con_iva': 1160.0,
    }


def _contexto(**overrides) -> dict:
    """
    Contexto mínimo igual al de enviar_cotizacion_cliente_task.

    Args:
        **overrides: Claves a cambiar (país, reacondicionado, nota).

    Returns:
        dict: Contexto para render_to_string.

    Efectos secundarios:
        Ninguno.
    """
    contexto = {
        'solicitud': SimpleNamespace(numero_solicitud='SC-900'),
        'titulo_propuesta': 'Reparación estándar',
        'info_equipo': {
            'marca': 'Dell',
            'modelo': 'Latitude',
            'tipo': 'Laptop',
            'service_tag': 'SN-900',
        },
        'nombre_cliente': 'Ana López',
        'calculo': _calculo(),
        'mensaje_personalizado': '',
        'fecha_envio_texto': '24/09/2026',
        'hora_envio_texto': '11:00',
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'pais_codigo': 'MX',
        'cotizacion_email': None,
        'whatsapp_empleado': '',
        'nombre_usuario': 'Luis Front',
        'es_reacondicionado': False,
        'costeo_reac': {},
        'info_equipo_reac': {},
        'incluye_paquete_plata': False,
    }
    contexto.update(overrides)
    return contexto


class CotizacionClienteFinalEmailTemplateTests(SimpleTestCase):
    """El HTML al cliente debe ser correo de tablas y conservar el resumen."""

    def test_generico_es_correo_de_tablas(self):
        """Sin bloque México: saludo, totales, redes y pie, sin CSS de página."""
        html = render_to_string(PLANTILLA, _contexto())

        self.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
        self.assertNotIn('{#', html)
        self.assertIn('role="presentation"', html)
        self.assertIn('max-width:600px', html)
        self.assertIn('cid:logo_sic_white', html)
        self.assertIn('Cotización de servicio', html)
        self.assertIn('Folio: SC-900', html)
        self.assertIn('Reparación estándar', html)
        self.assertIn('Estimado/a Ana López,', html)
        self.assertIn('Datos del Equipo', html)
        self.assertIn('Dell', html)
        self.assertIn('SN-900', html)
        self.assertIn('Resumen de Cotización', html)
        self.assertIn('$1160.00 MXN', html)
        self.assertIn('TOTAL CON IVA (16%)', html)
        self.assertIn('SC-900.pdf', html)
        self.assertIn('15 días hábiles', html)
        self.assertNotIn('Aviso importante — Vigencia', html)
        self.assertIn('Sistema de Cotizaciones', html)
        self.assertIn('Luis Front', html)
        self.assertIn('NO RESPONDA', html)
        self.assertIn('Visítanos y síguenos en nuestras redes sociales', html)
        self.assertIn('https://sicfix.mx/', html)
        self.assertIn('Sitio Web', html)
        self.assertNotIn('Buenos días:', html)
        self.assertNotIn('display:flex', html)
        self.assertNotIn('linear-gradient', html)
        self.assertNotIn('box-shadow', html)
        self.assertNotIn('wa.me', html)
        self.assertNotIn('<div class="aviso-paquete-plata">', html)

    def test_mexico_muestra_banco_referencia_y_cierre(self):
        """México con datos bancarios: carta, CLABE, referencia azul y 5 días."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                cotizacion_email=SimpleNamespace(
                    banco='BBVA',
                    titular_cuenta='SIC SA de CV',
                    numero_cuenta='0123456789',
                    clabe='012180001234567899',
                    formulario_factura_url='https://forms.example/factura',
                ),
                empresa_nombre_mayus='SIC MÉXICO',
                referencia_pago='SAT9596',
                fecha_limite_factura_texto='30 de septiembre',
                mensaje_personalizado='Favor de confirmar hoy.',
            ),
        )

        self.assertIn('Buenos días:', html)
        self.assertIn('SIC MÉXICO', html)
        self.assertIn('NO SERÁ POSIBLE INICIAR EL PROCESO', html)
        self.assertIn('Nuestras condiciones de pago', html)
        self.assertIn('BBVA', html)
        self.assertIn('012180001234567899', html)
        self.assertIn('COLOCAR COMO REFERENCIA:', html)
        self.assertIn('SAT9596', html)
        self.assertIn('Formulario de datos fiscales (Google Forms)', html)
        self.assertIn('30 DE SEPTIEMBRE', html)
        self.assertIn('5 días hábiles', html)
        self.assertIn('Saludos cordiales.', html)
        self.assertIn('Favor de confirmar hoy.', html)
        self.assertNotIn('Estimado/a Ana López,', html)
        self.assertNotIn('15 días hábiles', html)

    def test_sin_referencia_avisa_pendiente(self):
        """Sin referencia de pago no se inventa un folio: pide al responsable."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                cotizacion_email=SimpleNamespace(
                    banco='BBVA',
                    titular_cuenta='SIC',
                    numero_cuenta='1',
                    clabe='2',
                    formulario_factura_url='https://forms.example/factura',
                ),
                empresa_nombre_mayus='SIC MÉXICO',
                referencia_pago='',
                fecha_limite_factura_texto='1 de octubre',
            ),
        )

        self.assertIn('REFERENCIA DE PAGO', html)
        self.assertIn('Pendiente — contacte a su responsable de seguimiento', html)
        self.assertNotIn('COLOCAR COMO REFERENCIA:', html)

    def test_reacondicionado_lista_plazos(self):
        """Reacondicionado: equipo ofertado y plazos, sin el total de reparación."""
        html = render_to_string(
            PLANTILLA,
            _contexto(
                es_reacondicionado=True,
                titulo_propuesta='Equipo reacondicionado',
                info_equipo_reac={
                    'marca': 'HP',
                    'modelo': 'ProBook',
                    'procesador': 'i5',
                    'ram': '16 GB',
                    'sistema_operativo': 'Windows 11',
                    'incluye_cargador': True,
                    'especificaciones': 'Grado A',
                },
                costeo_reac={
                    'subtotal_sin_iva': 8000,
                    'iva': 1280,
                    'total_precio_contado_mxn': 9280,
                    'opciones_diferidas_con_iva': {
                        'diferido_3_meses': 3200,
                        'diferido_6_meses': 1700,
                        'diferido_12_meses': 900,
                    },
                },
            ),
        )

        self.assertIn('Equipo reacondicionado ofertado', html)
        self.assertIn('HP', html)
        self.assertIn('Incluye cargador:', html)
        self.assertIn('Sí', html)
        self.assertIn('Inversión y opciones de pago', html)
        self.assertIn('Pago diferido a 12 meses (con IVA)', html)
        self.assertIn('$9280.00 MXN', html)
        self.assertIn('financiamiento', html)
        self.assertNotIn('TOTAL CON IVA (16%)', html)
        self.assertNotIn('Resumen de Cotización', html)
