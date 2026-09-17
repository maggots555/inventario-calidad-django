"""
Tests del parser de código CIS desde folio SICSER.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cubre el caso Monterrey: el folio trae MONTERREY1 (sitio pegado a la ciudad)
y antes caía incorrectamente a Satélite (SAT).
"""

from django.test import SimpleTestCase

from servicio_tecnico.sicser_client import (
    _extraer_direccion_garantia,
    _normalizar_registro_garantia,
    _normalizar_registro_oow,
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


class DireccionGarantiaSicserTest(SimpleTestCase):
    """Extracción de dirección desde el dict crudo de garantías SICSER."""

    def test_extrae_direccion_clave_estandar(self):
        self.assertEqual(
            _extraer_direccion_garantia({'direccion': 'Calle 1 Colonia Centro'}),
            'Calle 1 Colonia Centro',
        )

    def test_extrae_domicilio_como_fallback(self):
        self.assertEqual(
            _extraer_direccion_garantia({'domicilio': 'Av. Reforma 100'}),
            'Av. Reforma 100',
        )

    def test_normalizar_incluye_direccion(self):
        reg = _normalizar_registro_garantia({
            'numero_dps': 123,
            'service_tag': 'ABC123',
            'contacto': 'Juan',
            'direccion': 'Circuito Economistas 15-A',
            'ciudad': 'tecamachalco',
            'estado': 'México',
            'pais': 'México',
        })
        self.assertEqual(reg.direccion, 'Circuito Economistas 15-A')
        self.assertEqual(reg.ciudad, 'tecamachalco')


class NormalizarRegistroOowNombresTest(SimpleTestCase):
    """
    La API OOW manda nombre_cliente (empresa) y contacto (persona) por separado.
    SIGMA ya no debe fusionarlos al normalizar.
    """

    def _payload_oow(self, **extra):
        """Dict crudo mínimo de un registro OOW de SICSER."""
        base = {
            'id_orden': 11954,
            'folio': 'MX_CIS_MX_DROPOFF_11954',
            'service_tag': 'ABC1234',
            'nombre_cliente': 'EMPRESA SA DE CV',
            'contacto': 'Juan Perez',
            'marca': 'HP',
            'tipo_equipo': 'LAPTOP',
            'modelo': 'Pavilion',
            'email': 'juan@test.local',
            'telefono': '5512345678',
            'rfc': 'EMP010101XXX',
            'direccion_cliente': 'Calle 10 Colonia Centro',
            'descripcion_falla': 'No enciende',
            'cis': '',
            'fecha': '2026-09-01 10:00:00',
        }
        base.update(extra)
        return base

    def test_conserva_contacto_y_nombre_cliente_por_separado(self):
        """
        Feliz: ambos campos llegan distintos y se conservan.
        """
        reg = _normalizar_registro_oow(self._payload_oow())
        self.assertEqual(reg.nombre_cliente, 'EMPRESA SA DE CV')
        self.assertEqual(reg.contacto, 'Juan Perez')
        self.assertEqual(reg.nombre_para_listado(), 'Juan Perez')
        self.assertTrue(reg.mostrar_razon_social_en_listado())
        self.assertEqual(reg.direccion, 'Calle 10 Colonia Centro')

    def test_sin_contacto_no_descarta_la_razon_social(self):
        """
        Borde: sin persona de contacto, el listado usa la razón social
        y no duplica una segunda fila de empresa.
        """
        reg = _normalizar_registro_oow(self._payload_oow(contacto=''))
        self.assertEqual(reg.nombre_cliente, 'EMPRESA SA DE CV')
        self.assertEqual(reg.contacto, '')
        self.assertEqual(reg.nombre_para_listado(), 'EMPRESA SA DE CV')
        self.assertFalse(reg.mostrar_razon_social_en_listado())
