"""
La IP de los límites no sale de una cabecera que el visitante puede inventar.
"""

from django.test import RequestFactory, SimpleTestCase

from config.cliente_ip import ip_cliente


class IpClienteTests(SimpleTestCase):
    """X-Real-IP manda. Una lista X-Forwarded-For falsa se ignora."""

    def setUp(self):
        self.factory = RequestFactory()

    def test_usa_x_real_ip_aunque_forwarded_for_mienta(self):
        """Nginx ya escribió la IP buena. La lista del cliente no cuenta."""
        request = self.factory.get('/')
        request.META['HTTP_X_REAL_IP'] = '203.0.113.8'
        request.META['HTTP_X_FORWARDED_FOR'] = '1.2.3.4, 5.6.7.8'
        request.META['REMOTE_ADDR'] = '172.18.0.5'
        self.assertEqual(ip_cliente(request), '203.0.113.8')

    def test_sin_proxy_usa_el_socket(self):
        """runserver no manda X-Real-IP: queda la IP de la conexión."""
        request = self.factory.get('/')
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        self.assertEqual(ip_cliente(request), '127.0.0.1')
