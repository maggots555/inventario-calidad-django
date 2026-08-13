"""
Tests del orden por defecto de la lista de compras.

EXPLICACIÓN PARA PRINCIPIANTES:
-------------------------------
No hace falta crear compras reales en la BD: el helper solo lee
estado, dias_para_llegada y fecha_registro. Usamos objetos simples
(SimpleNamespace) para comprobar la regla de negocio.
"""

from datetime import datetime, timedelta
from types import SimpleNamespace

from django.test import SimpleTestCase

from almacen.utils.lista_compras_orden import ordenar_compras_para_lista


def _compra(*, estado, dias_para_llegada, hace_horas=0, pk=1):
    """Compra falsa con los atributos que usa el ordenador."""
    return SimpleNamespace(
        pk=pk,
        estado=estado,
        dias_para_llegada=dias_para_llegada,
        fecha_registro=datetime(2026, 8, 13, 12, 0, 0) - timedelta(hours=hace_horas),
    )


class OrdenarComprasParaListaTest(SimpleTestCase):
    """Valida pendiente_llegada primero y countdown de ETA."""

    def test_pendientes_primero_y_por_dias_que_faltan(self):
        """Caso feliz: pendientes arriba; la de 1 día antes que la de 10."""
        recibida = _compra(estado='recibida', dias_para_llegada=None, pk=1)
        falta_diez = _compra(estado='pendiente_llegada', dias_para_llegada=10, pk=2)
        falta_uno = _compra(estado='pendiente_llegada', dias_para_llegada=1, pk=3)

        ordenadas = ordenar_compras_para_lista([recibida, falta_diez, falta_uno])

        self.assertEqual([c.pk for c in ordenadas], [3, 2, 1])

    def test_retrasada_sin_eta_y_recibida_al_final(self):
        """Borde: atraso (−6) primero; sin ETA después de las que sí tienen fecha."""
        recibida = _compra(estado='recibida', dias_para_llegada=None, pk=1)
        sin_eta = _compra(estado='pendiente_llegada', dias_para_llegada=None, pk=2)
        falta_dos = _compra(estado='pendiente_llegada', dias_para_llegada=2, pk=3)
        retrasada = _compra(estado='pendiente_llegada', dias_para_llegada=-6, pk=4)

        ordenadas = ordenar_compras_para_lista(
            [recibida, sin_eta, falta_dos, retrasada]
        )

        self.assertEqual([c.pk for c in ordenadas], [4, 3, 2, 1])
