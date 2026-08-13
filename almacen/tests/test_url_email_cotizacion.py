"""
Tests de URLs absolutas en correos internos de Almacén.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El botón del correo debe abrir el SIGMA del país correcto:
    - Producción (DEBUG=False) → subdominio (mexico/argentina/…)
    - Desarrollo (DEBUG=True) → SITE_URL (localhost)

Django corre los tests con DEBUG=False, así que el caso “México”
usa la url_base real de paises_config.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase, override_settings

from almacen.utils.cotizacion_email_context import (
    url_absoluta_detalle_orden,
    url_absoluta_detalle_solicitud,
    url_base_pais_email,
)


class UrlBasePaisEmailTest(TestCase):
    """Reglas unitarias de la base absoluta para href de correos internos."""

    @override_settings(DEBUG=False)
    def test_produccion_mexico_usa_url_base(self) -> None:
        """Sin tenant forzado, el default es México."""
        base = url_base_pais_email()

        self.assertEqual(base, 'https://mexico.sigmasystem.work')
        self.assertFalse(base.endswith('/'))

    @override_settings(DEBUG=False)
    @patch(
        'almacen.utils.cotizacion_email_context.get_pais_actual',
        return_value={'url_base': 'https://argentina.sigmasystem.work'},
    )
    def test_produccion_argentina_usa_url_base(self, _mock_pais) -> None:
        """Celery con db_alias argentina → subdominio de Argentina."""
        base = url_base_pais_email()

        self.assertEqual(base, 'https://argentina.sigmasystem.work')

    @override_settings(DEBUG=True, SITE_URL='http://localhost:8000')
    def test_debug_usa_site_url(self) -> None:
        """En local el clic debe abrir el servidor de desarrollo."""
        base = url_base_pais_email()

        self.assertEqual(base, 'http://localhost:8000')

    @override_settings(DEBUG=False, SITE_URL='http://fallback.example')
    @patch(
        'almacen.utils.cotizacion_email_context.get_pais_actual',
        return_value={},
    )
    def test_sin_url_base_usa_site_url(self, _mock_pais) -> None:
        """Si el país no trae url_base, se usa SITE_URL."""
        base = url_base_pais_email()

        self.assertEqual(base, 'http://fallback.example')


class UrlAbsolutaDetalleTest(TestCase):
    """Junta la base del país con reverse() de solicitud y orden."""

    @override_settings(DEBUG=False)
    def test_detalle_solicitud_mexico(self) -> None:
        """El href incluye el path de Almacén y el subdominio de México."""
        solicitud = SimpleNamespace(pk=42)

        url = url_absoluta_detalle_solicitud(solicitud)

        self.assertTrue(url.startswith('https://mexico.sigmasystem.work'))
        self.assertIn('/almacen/solicitudes-cotizacion/42/', url)

    @override_settings(DEBUG=False)
    def test_detalle_orden_mexico(self) -> None:
        """El href de rechazo interno apunta al detalle ST del mismo país."""
        orden = SimpleNamespace(pk=99)

        url = url_absoluta_detalle_orden(orden)

        self.assertTrue(url.startswith('https://mexico.sigmasystem.work'))
        self.assertIn('/servicio-tecnico/ordenes/99/', url)

    @override_settings(DEBUG=True, SITE_URL='http://localhost:8000')
    def test_detalle_solicitud_en_debug_es_localhost(self) -> None:
        """En desarrollo el botón no debe mandar a producción."""
        solicitud = SimpleNamespace(pk=7)

        url = url_absoluta_detalle_solicitud(solicitud)

        self.assertEqual(
            url,
            'http://localhost:8000/almacen/solicitudes-cotizacion/7/',
        )
