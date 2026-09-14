"""
Tests de las tres plantillas HTML y del texto plano de diagnóstico al cliente.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No enviamos correo. Solo rellenamos el HTML (`render_to_string`) y el
text/plain con datos de prueba, para no romper los {% if %} al pasar
el diseño a tablas (Gmail/Outlook no entienden flex ni CSS de página web).

Hay tres plantillas (mismo envío Celery, radio distinto):
- estandar
- nivel_componente
- validacion
"""

from datetime import datetime
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from servicio_tecnico.services.email_diagnostico_cliente import (
    construir_texto_plano_diagnostico,
)


PLANTILLA_ESTANDAR = 'servicio_tecnico/emails/diagnostico_cliente.html'
PLANTILLA_NIVEL = 'servicio_tecnico/emails/diagnostico_cliente_nivel_componente.html'
PLANTILLA_VALIDACION = 'servicio_tecnico/emails/diagnostico_cliente_validacion.html'


def _contexto(**overrides):
    """
    Contexto mínimo igual al de enviar_diagnostico_cliente_task.

    Args:
        **overrides: Claves a cambiar (seguimiento, Drop Off, etc.).

    Returns:
        dict: Contexto para render_to_string y texto plano.
    """
    detalle = SimpleNamespace(
        orden_cliente='FL-3003',
        tipo_equipo='Laptop',
        marca='Dell',
        modelo='Latitude 5520',
        numero_serie='SN-DIAG-001',
        nombre_cliente='Ana Pérez',
    )
    orden = SimpleNamespace(
        numero_orden_interno='INT-3003',
        fecha_ingreso=datetime(2026, 9, 14, 10, 30),
    )
    contexto = {
        'orden': orden,
        'detalle': detalle,
        'folio': 'DX-3003',
        'mensaje_personalizado': '',
        'fecha_envio_texto': '14/09/2026',
        'hora_envio_texto': '11:00',
        'cantidad_imagenes': 2,
        'componentes_seleccionados': [],
        'piezas_creadas': 0,
        'empresa_nombre': 'SIC México',
        'pais_nombre': 'México',
        'email_empleado': 'tech@test.local',
        'nombre_empleado': 'Técnico Test',
        'whatsapp_empleado': '525512345678',
        'seguimiento_url': None,
        'nombre_cliente': 'Ana Pérez',
        'horario_atencion': 'Lunes a Viernes de 09:00 a 17:30 hrs horario corrido.',
        'sucursal_nombre': 'Sucursal Satélite',
        'sucursal_direccion': 'Circuito Economistas 15-A',
        'sucursal_ciudad_estado': 'Naucalpan, Estado de México',
        'sucursal_telefono': '5555555555',
        'es_fuera_garantia': True,
        'es_sucursal_drop_off': False,
    }
    contexto.update(overrides)
    return contexto


def _assert_layout_correo(test_case: SimpleTestCase, html: str) -> None:
    """
    Checklist visual común: DOCTYPE, tablas 600px, paleta SIC, sin flex.

    Args:
        test_case: El TestCase que hace los asserts.
        html: HTML ya renderizado.
    """
    test_case.assertTrue(html.lstrip().startswith('<!DOCTYPE html>'))
    test_case.assertNotIn('{#', html)
    test_case.assertIn('max-width:600px', html)
    test_case.assertIn('#1f6391', html)
    test_case.assertIn('cid:logo_sic_white', html)
    test_case.assertIn('class="email-brandbar"', html)
    test_case.assertIn('bgcolor="#1e293b"', html)
    test_case.assertIn('role="presentation"', html)
    test_case.assertNotIn('display:flex', html)
    test_case.assertNotIn('linear-gradient', html)
    test_case.assertNotIn('#667eea', html)
    test_case.assertNotIn('#764ba2', html)


class DiagnosticoEstandarEmailTemplateTests(SimpleTestCase):
    """Plantilla estándar: cotización en camino, pie sicfix.mx."""

    def test_render_base_incluye_copy_y_layout(self):
        """Feliz: folio, equipo, PDF+fotos, paleta SIC."""
        html = render_to_string(PLANTILLA_ESTANDAR, _contexto())
        _assert_layout_correo(self, html)

        self.assertIn('Diagnóstico de equipo', html)
        self.assertIn('Buen día estimado usuario', html)
        self.assertIn('DX-3003', html)
        self.assertIn('FL-3003', html)
        self.assertIn('Laptop Dell Latitude 5520', html)
        self.assertIn('SN-DIAG-001', html)
        self.assertIn('1 a 6 días hábiles', html)
        self.assertIn('https://sicfix.mx/', html)
        # 2 fotos + 1 PDF = 3 adjuntos
        self.assertIn('3', html)
        self.assertNotIn('Ver seguimiento de mi equipo', html)

    def test_con_seguimiento_muestra_boton(self):
        """El CTA HTML lleva la URL pública."""
        url = 'https://app.sigmasystem.work/seguimiento/token-demo/'
        html = render_to_string(
            PLANTILLA_ESTANDAR,
            _contexto(seguimiento_url=url),
        )
        self.assertIn(url, html)
        self.assertIn('Ver seguimiento de mi equipo', html)
        self.assertIn('fillcolor="#1f6391"', html)

    def test_mensaje_personalizado_aparece(self):
        """El recado del técnico se inserta cuando viene en el contexto."""
        html = render_to_string(
            PLANTILLA_ESTANDAR,
            _contexto(mensaje_personalizado='Favor de revisar el PDF adjunto.'),
        )
        self.assertIn('Mensaje adicional', html)
        self.assertIn('Favor de revisar el PDF adjunto.', html)


class DiagnosticoNivelComponenteEmailTemplateTests(SimpleTestCase):
    """Plantilla nivel componente: FAQ, galería CID, pie sic.com.mx."""

    def test_render_base_incluye_faq_galeria_y_layout(self):
        """Feliz: copy TM, FAQ, CIDs RHITSO, sin diagrama."""
        html = render_to_string(PLANTILLA_NIVEL, _contexto())
        _assert_layout_correo(self, html)

        self.assertIn('Diagnóstico — Reparación a nivel componente', html)
        self.assertIn('Preguntas frecuentes', html)
        self.assertIn('cid:rhitso_reballing', html)
        self.assertIn('cid:rhitso_pistas', html)
        self.assertIn('cid:rhitso_ultrasonica', html)
        self.assertIn('cid:rhitso_revision', html)
        self.assertIn('cid:rhitso_datos', html)
        self.assertIn('cid:rhitso_integridad', html)
        self.assertIn('https://sicfix.mx/reparacion-tarjeta-madre/', html)
        self.assertIn('https://sic.com.mx/', html)
        self.assertIn('https://wa.me/525512345678', html)
        self.assertNotIn('diagrama', html.lower())


class DiagnosticoValidacionEmailTemplateTests(SimpleTestCase):
    """Plantilla validación: garantía 1 semana, recolección vs Drop Off."""

    def test_recoleccion_incluye_horario_y_clausula(self):
        """Sucursal normal + OOW: invitación a recolectar y cláusula 6."""
        html = render_to_string(PLANTILLA_VALIDACION, _contexto())
        _assert_layout_correo(self, html)
        html_plano = ' '.join(html.split())

        self.assertIn('Diagnóstico de validación', html_plano)
        self.assertIn('no será necesario cotizar ningún componente', html_plano)
        self.assertIn('garantía de validación es de 1 semana', html_plano.lower())
        self.assertIn('listo para que pase a recolectar', html_plano)
        self.assertIn('Le recuerdo los horarios de atención', html_plano)
        self.assertIn('Circuito Economistas 15-A', html_plano)
        self.assertIn('CLÁUSULA 6', html_plano)
        self.assertIn('https://sic.com.mx/', html_plano)
        self.assertNotIn('espere la notificación de equipo disponible', html_plano)

    def test_garantia_omite_clausula_almacenaje(self):
        """Dentro de garantía no sale la cláusula 6."""
        html = render_to_string(
            PLANTILLA_VALIDACION,
            _contexto(es_fuera_garantia=False),
        )
        self.assertNotIn('CLÁUSULA 6', html)
        self.assertNotIn('ALMACENAJE O DESTRUCCIÓN', html)

    def test_drop_off_pide_esperar_aviso(self):
        """Drop Off: esperar equipo disponible; no recolección ni cláusula 6."""
        html = render_to_string(
            PLANTILLA_VALIDACION,
            _contexto(es_sucursal_drop_off=True, es_fuera_garantia=True),
        )
        html_plano = ' '.join(html.split())
        self.assertIn('espere la notificación de equipo disponible', html_plano)
        self.assertNotIn('listo para que pase a recolectar', html_plano)
        self.assertNotIn('CLÁUSULA 6', html_plano)
        self.assertNotIn('Le recuerdo los horarios de atención', html_plano)


class DiagnosticoClienteTextoPlanoTests(SimpleTestCase):
    """El text/plain debe decir lo mismo que el HTML (paridad)."""

    def test_estandar_incluye_nucleo_y_omite_url_si_falta(self):
        """Feliz estándar: folio, cotización, pie sicfix, sin seguimiento."""
        texto = construir_texto_plano_diagnostico('estandar', _contexto())
        self.assertIn('Diagnóstico de equipo', texto)
        self.assertIn('DX-3003', texto)
        self.assertIn('FL-3003', texto)
        self.assertIn('3 archivo', texto)
        self.assertIn('1 a 6 días hábiles', texto)
        self.assertIn('https://sicfix.mx/', texto)
        self.assertIn('NO RESPONDA', texto)
        self.assertNotIn('https://app.sigmasystem.work/seguimiento/', texto)

    def test_estandar_con_seguimiento_lleva_la_misma_url(self):
        """Borde: la URL pública viaja también en texto plano."""
        url = 'https://app.sigmasystem.work/seguimiento/token-demo/'
        texto = construir_texto_plano_diagnostico(
            'estandar',
            _contexto(seguimiento_url=url),
        )
        self.assertIn(url, texto)
        self.assertIn('Consulte el estado de su equipo', texto)

    def test_nivel_componente_incluye_faq_y_sitio_sic(self):
        """Nivel componente: FAQ, más info, pie sic.com.mx."""
        texto = construir_texto_plano_diagnostico(
            'nivel_componente',
            _contexto(),
        )
        self.assertIn('Reparación a nivel componente', texto)
        self.assertIn('PREGUNTAS FRECUENTES', texto)
        self.assertIn('https://sicfix.mx/reparacion-tarjeta-madre/', texto)
        self.assertIn('https://sic.com.mx/', texto)
        self.assertIn('https://wa.me/525512345678', texto)

    def test_validacion_drop_off_omite_recoleccion(self):
        """Drop Off en plano: esperar aviso, sin cláusula 6."""
        texto = construir_texto_plano_diagnostico(
            'validacion',
            _contexto(es_sucursal_drop_off=True, es_fuera_garantia=True),
        )
        self.assertIn('espere la notificación de equipo disponible', texto)
        self.assertNotIn('listo para que pase a recolectar', texto)
        self.assertNotIn('CLÁUSULA 6', texto)

    def test_tipo_desconocido_cae_a_estandar(self):
        """Valor raro del radio → mismo texto que estándar."""
        texto = construir_texto_plano_diagnostico('plantilla_inventada', _contexto())
        self.assertIn('Diagnóstico de equipo', texto)
        self.assertIn('https://sicfix.mx/', texto)
