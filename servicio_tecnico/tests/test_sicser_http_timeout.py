"""
Tests del manejo de timeout HTTP al consultar SICSER.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Si el servidor de SICSER no responde a tiempo, Python lanza TimeoutError.
Antes ese error no se atrapaba y la pantalla «Consulta SICSER» caía en 500.
Estos tests verifican que ahora se convierte en SicserAPIError (mensaje amigable).
"""

from unittest.mock import patch

from django.test import SimpleTestCase

from servicio_tecnico.sicser_client import SicserAPIError, _http_get_json


class HttpGetJsonTimeoutTest(SimpleTestCase):
    """_http_get_json convierte TimeoutError en SicserAPIError."""

    def test_timeout_error_se_convierte_en_sicser_api_error(self):
        """
        Objetivo:
            Simular que urlopen se queda sin respuesta y lanza TimeoutError.
        Esperado:
            Se lanza SicserAPIError con texto claro (no un 500 crudo).
        """
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # patch reemplaza urlopen solo durante este test; no llama a SICSER de verdad.
        with patch(
            'servicio_tecnico.sicser_client.urllib.request.urlopen',
            side_effect=TimeoutError('timed out'),
        ):
            with self.assertRaises(SicserAPIError) as contexto:
                _http_get_json(
                    url='http://ejemplo.test/listado.php',
                    token='token-de-prueba',
                    timeout=5,
                )

        mensaje = str(contexto.exception)
        self.assertIn('no respondió a tiempo', mensaje)
        self.assertIn('5s', mensaje)

    def test_oserror_de_red_tambien_se_convierte(self):
        """Otros fallos de socket/red también deben ser SicserAPIError."""
        with patch(
            'servicio_tecnico.sicser_client.urllib.request.urlopen',
            side_effect=OSError('Connection reset by peer'),
        ):
            with self.assertRaises(SicserAPIError) as contexto:
                _http_get_json(
                    url='http://ejemplo.test/listado.php',
                    token='token-de-prueba',
                    timeout=5,
                )

        self.assertIn('Error de red', str(contexto.exception))

    def test_sin_token_falla_antes_de_llamar_red(self):
        """Sin token no debe intentar la petición HTTP."""
        with patch(
            'servicio_tecnico.sicser_client.urllib.request.urlopen',
        ) as mock_urlopen:
            with self.assertRaises(SicserAPIError) as contexto:
                _http_get_json(url='http://ejemplo.test/listado.php', token='')

        mock_urlopen.assert_not_called()
        self.assertIn('Token SICSER no configurado', str(contexto.exception))
