"""
Tests del enlace de seguimiento y del helper de QR para PDF.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cubren la URL pública (url_base del país) y que, si falta la librería
qrcode, no se rompe el PDF: el helper devuelve None.
"""

from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, EnlaceSeguimientoCliente, OrdenServicio
from servicio_tecnico.services.enlace_seguimiento import (
    obtener_o_crear_enlace_seguimiento,
    url_publica_seguimiento,
    url_seguimiento_de_orden,
)
from servicio_tecnico.utils.qr_pdf import ImagenQRClicable, imagen_qr_para_pdf


class UrlSeguimientoHelperTest(TestCase):
    """get_or_create del enlace y armado de la URL pública."""

    databases = {'default', 'mexico'}

    def setUp(self):
        sucursal = Sucursal.objects.create(
            nombre='Sucursal Enlace QR',
            ciudad='CDMX',
        )
        empleado = Empleado.objects.create(
            nombre_completo='Técnico Enlace',
            cargo='Técnico',
            area='Laboratorio',
            email='enlace.qr@test.local',
            sucursal=sucursal,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            es_fuera_garantia=True,
            tecnico_asignado_actual=empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-QR-01',
            tipo_equipo='Laptop',
            marca='DELL',
            modelo='Latitude',
            numero_serie='QRTEST001',
            email_cliente='',
            gama='media',
        )

    def test_obtener_o_crear_sin_email(self):
        """Aunque no hay correo, se crea el enlace (el PDF lo necesita)."""
        self.assertFalse(
            EnlaceSeguimientoCliente.objects.filter(orden=self.orden).exists()
        )
        enlace = obtener_o_crear_enlace_seguimiento(self.orden)
        self.assertTrue(enlace.token)
        self.assertEqual(enlace.orden_id, self.orden.pk)
        # Segunda llamada: no duplica (get_or_create).
        otro = obtener_o_crear_enlace_seguimiento(self.orden)
        self.assertEqual(enlace.pk, otro.pk)
        self.assertEqual(
            EnlaceSeguimientoCliente.objects.filter(orden=self.orden).count(),
            1,
        )

    @patch('servicio_tecnico.services.enlace_seguimiento.get_pais_actual')
    def test_url_publica_usa_url_base_del_pais(self, mock_pais):
        """
        La URL del QR/correo usa el subdominio del país activo, no un hardcode.
        """
        mock_pais.return_value = {'url_base': 'https://mexico.sigmasystem.work'}
        enlace = obtener_o_crear_enlace_seguimiento(self.orden)
        url = url_publica_seguimiento(enlace)
        self.assertEqual(
            url,
            f'https://mexico.sigmasystem.work/seguimiento/{enlace.token}/',
        )

    def test_url_seguimiento_de_orden_sin_enlace(self):
        """Sin fila de enlace, el PDF no inventa una URL."""
        self.assertIsNone(url_seguimiento_de_orden(self.orden))


class QrPdfHelperTest(SimpleTestCase):
    """Fail-safe del PNG QR (sin BD)."""

    def test_url_vacia_devuelve_none(self):
        self.assertIsNone(imagen_qr_para_pdf(''))
        self.assertIsNone(imagen_qr_para_pdf('   '))

    def test_sin_libreria_qrcode_devuelve_none(self):
        """Si qrcode no está instalado, no truena: el PDF sigue sin QR."""
        with patch(
            'servicio_tecnico.utils.qr_pdf._importar_qrcode',
            side_effect=ImportError,
        ):
            self.assertIsNone(
                imagen_qr_para_pdf('https://mexico.sigmasystem.work/seguimiento/abc/')
            )

    def test_url_valida_genera_imagen_clicable(self):
        img = imagen_qr_para_pdf(
            'https://mexico.sigmasystem.work/seguimiento/tokenprueba/',
            lado_mm=20,
        )
        self.assertIsNotNone(img)
        self.assertIsInstance(img, ImagenQRClicable)
        self.assertEqual(
            img._url_enlace,
            'https://mexico.sigmasystem.work/seguimiento/tokenprueba/',
        )
