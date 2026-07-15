"""
Tests de orden necesaria → opcional en el armado de ítems del PDF.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
En el modo «Un solo PDF» las opcionales deben ir al final, aunque se hayan
agregado antes en la solicitud. Estos tests no usan base de datos: solo
listas de dicts como las que serializa cotizacion_items_cliente.
"""

from unittest import TestCase

from almacen.utils.cotizacion_items_cliente import (
    _ordenar_lista_nec_luego_opc,
    _ordenar_necesarias_luego_opcionales,
    construir_grupos_cotizacion,
)


def _item(nombre: str, es_necesaria: bool, es_servicio: bool = False) -> dict:
    """Dict mínimo con la forma que espera el armado de grupos."""
    return {
        'descripcion': nombre,
        'es_necesaria': es_necesaria,
        'es_servicio': es_servicio,
    }


class OrdenNecesariasOpcionalesTest(TestCase):
    """Verifica que las opcionales queden siempre después de las necesarias."""

    def test_helper_pone_opcionales_al_final(self):
        # Orden de alta: limpieza opc, motherboard nec, paquete nec
        piezas = [
            _item('Motherboard', True),
        ]
        servicios = [
            _item('Limpieza', False, es_servicio=True),
            _item('Solución Plata', True, es_servicio=True),
        ]
        ordenados = _ordenar_necesarias_luego_opcionales(piezas, servicios)
        nombres = [i['descripcion'] for i in ordenados]
        self.assertEqual(
            nombres,
            ['Motherboard', 'Solución Plata', 'Limpieza'],
        )
        # Todas las necesarias antes de la primera opcional
        flags = [i['es_necesaria'] for i in ordenados]
        self.assertEqual(flags, [True, True, False])

    def test_helper_preserva_orden_relativo_de_necesarias(self):
        piezas = [
            _item('Pieza A', True),
            _item('Pieza B', True),
            _item('Pieza Opc', False),
        ]
        ordenados = _ordenar_necesarias_luego_opcionales(piezas, [])
        self.assertEqual(
            [i['descripcion'] for i in ordenados],
            ['Pieza A', 'Pieza B', 'Pieza Opc'],
        )

    def test_todo_junto_reordena_en_grupos(self):
        piezas = [_item('Motherboard', True)]
        servicios = [
            _item('Limpieza', False, es_servicio=True),
            _item('Solución Plata', True, es_servicio=True),
        ]
        grupos = construir_grupos_cotizacion(piezas, servicios, 'todo_junto')
        self.assertEqual(len(grupos), 1)
        nombres = [i['descripcion'] for i in grupos[0]['items']]
        self.assertEqual(nombres, ['Motherboard', 'Solución Plata', 'Limpieza'])

    def test_piezas_vs_servicios_ordena_dentro_de_cada_grupo(self):
        piezas = [
            _item('Opcional pieza', False),
            _item('Necesaria pieza', True),
        ]
        servicios = [
            _item('Limpieza', False, es_servicio=True),
            _item('Paquete', True, es_servicio=True),
        ]
        grupos = construir_grupos_cotizacion(piezas, servicios, 'piezas_vs_servicios')
        self.assertEqual(len(grupos), 2)
        piezas_nombres = [i['descripcion'] for i in grupos[0]['items']]
        serv_nombres = [i['descripcion'] for i in grupos[1]['items']]
        self.assertEqual(piezas_nombres, ['Necesaria pieza', 'Opcional pieza'])
        self.assertEqual(serv_nombres, ['Paquete', 'Limpieza'])

    def test_ordenar_lista_sola(self):
        items = [
            _item('Opc', False),
            _item('Nec', True),
        ]
        self.assertEqual(
            [i['descripcion'] for i in _ordenar_lista_nec_luego_opc(items)],
            ['Nec', 'Opc'],
        )
