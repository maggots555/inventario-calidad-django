"""
El total público del rechazo usa el precio cotizado, no el costo de SIC.
"""

from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from servicio_tecnico.services.feedback_rechazo_montos import (
    monto_rechazo_visible_cliente,
)


class MontoRechazoVisibleClienteTests(SimpleTestCase):
    """precio × cantidad. El costo interno no entra aunque sea más chico."""

    def test_suma_precio_por_cantidad_e_ignora_el_costo(self):
        """Dos piezas: una con precio y otra sin precio (no se rellena con costo)."""
        piezas = [
            SimpleNamespace(
                precio_unitario_cliente=Decimal('500.00'),
                costo_unitario=Decimal('80.00'),
                cantidad=2,
            ),
            SimpleNamespace(
                precio_unitario_cliente=None,
                costo_unitario=Decimal('999.00'),
                cantidad=1,
            ),
        ]
        self.assertEqual(monto_rechazo_visible_cliente(piezas), Decimal('1000.00'))

    def test_dict_del_correo_tambien_usa_el_precio(self):
        """La tarea del correo arma dicts, no modelos. La regla es la misma."""
        piezas = [{
            'precio_unitario_cliente': Decimal('1500.00'),
            'costo_unitario': Decimal('80.00'),
            'cantidad': 1,
        }]
        self.assertEqual(monto_rechazo_visible_cliente(piezas), Decimal('1500.00'))
