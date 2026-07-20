"""
Tests del parser de código CIS desde folio SICSER.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cubre el caso Monterrey: el folio trae MONTERREY1 (sitio pegado a la ciudad)
y antes caía incorrectamente a Satélite (SAT).
"""

from django.test import SimpleTestCase

from servicio_tecnico.sicser_client import (
    etiqueta_cis_legible,
    parsear_codigo_cis_para_url,
)


class ParsearCodigoCisUrlTest(SimpleTestCase):
    """parsear_codigo_cis_para_url reconoce ciudades con dígito de sitio pegado."""

    def test_monterrey1_no_cae_a_satelite(self):
        """
        Folio real SICSER: MX_CIS_MX_MONTERREY1_02821 → MTR (Monterrey).
        """
        codigo = parsear_codigo_cis_para_url('MX_CIS_MX_MONTERREY1_02821')
        self.assertEqual(codigo, 'MTR')
        self.assertEqual(etiqueta_cis_legible(codigo), 'Monterrey')

    def test_guadalajara_con_digito_sitio(self):
        codigo = parsear_codigo_cis_para_url('MX_CIS_MX_GUADALAJARA1_03398')
        self.assertEqual(codigo, 'GDL')

    def test_dropoff_exacto_sigue_igual(self):
        codigo = parsear_codigo_cis_para_url('MX_CIS_MX_DROPOFF_11954')
        self.assertEqual(codigo, 'DROP')

    def test_monterrey_sin_digito(self):
        codigo = parsear_codigo_cis_para_url('MX_CIS_MX_MONTERREY_02821')
        self.assertEqual(codigo, 'MTR')
