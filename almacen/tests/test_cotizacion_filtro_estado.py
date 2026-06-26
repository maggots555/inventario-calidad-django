"""
Tests de filtrado por estado_cliente y PDF final de cotización.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from almacen.utils.cotizacion_items_cliente import (
    construir_items_cotizacion_activos,
    linea_es_aceptada_final,
    linea_es_cotizable,
    serializar_linea_cotizacion,
    solicitud_tiene_items_cotizables,
)
from almacen.utils.pdf_cotizacion_cliente import calcular_totales_items_finales


def _linea_mock(pk=1, estado='pendiente', costo=100.0, cantidad=1):
    """Crea un mock de LineaCotizacion para pruebas sin BD."""
    producto = SimpleNamespace(nombre='RAM 8GB')
    return SimpleNamespace(
        pk=pk,
        producto=producto,
        descripcion_pieza='',
        cantidad=cantidad,
        costo_unitario=costo,
        es_necesaria=True,
        tiempo_entrega_estimado=5,
        estado_cliente=estado,
        precio_unitario_cliente=None,
        subtotal_cliente_sin_iva=None,
    )


def _servicio_mock(pk=10, estado='pendiente', costo=1160.0):
    return SimpleNamespace(
        pk=pk,
        get_tipo_servicio_display=lambda: 'Limpieza',
        costo=costo,
        es_necesaria=True,
        estado_cliente=estado,
    )


def _solicitud_mock(lineas=None, servicios=None):
    """Mock de SolicitudCotizacion con lineas/servicios filtrables."""
    lineas = lineas or []
    servicios = servicios or []

    def _filtrar_lineas(**kwargs):
        estado_in = kwargs.get('estado_cliente__in', ())
        costo_gt = kwargs.get('costo_unitario__gt')
        return [
            l for l in lineas
            if l.estado_cliente in estado_in
            and (costo_gt is None or float(l.costo_unitario or 0) > costo_gt)
        ]

    def _filtrar_servicios(**kwargs):
        estado_in = kwargs.get('estado_cliente__in', ())
        costo_gt = kwargs.get('costo__gt')
        return [
            s for s in servicios
            if s.estado_cliente in estado_in
            and (costo_gt is None or float(s.costo or 0) > costo_gt)
        ]

    def lineas_filter(**kwargs):
        outer = MagicMock()
        filtradas = _filtrar_lineas(**kwargs)
        inner = MagicMock()
        inner.__iter__ = lambda s: iter(filtradas)
        inner.exists.return_value = len(filtradas) > 0
        outer.select_related.return_value = inner
        return outer

    def servicios_filter(**kwargs):
        resultado = MagicMock()
        filtradas = _filtrar_servicios(**kwargs)
        resultado.__iter__ = lambda s: iter(filtradas)
        resultado.exists.return_value = len(filtradas) > 0
        return resultado

    solicitud = MagicMock()
    solicitud.lineas.filter.side_effect = lineas_filter
    solicitud.servicios_adicionales.filter.side_effect = servicios_filter
    return solicitud


class CotizacionFiltroEstadoTest(SimpleTestCase):
    """Pruebas de reglas pendiente/aprobada vs rechazada."""

    def test_linea_rechazada_no_es_cotizable(self):
        self.assertFalse(linea_es_cotizable('rechazada'))
        self.assertTrue(linea_es_cotizable('pendiente'))
        self.assertTrue(linea_es_cotizable('aprobada'))

    def test_compra_generada_solo_en_pdf_final(self):
        self.assertFalse(linea_es_cotizable('compra_generada'))
        self.assertTrue(linea_es_aceptada_final('compra_generada'))

    def test_serializar_incluye_estado_cliente(self):
        item = serializar_linea_cotizacion(_linea_mock(estado='aprobada'))
        self.assertEqual(item['estado_cliente'], 'aprobada')
        self.assertEqual(item['costo_unitario'], 100.0)

    def test_construir_activos_excluye_rechazada(self):
        sol = _solicitud_mock(
            lineas=[
                _linea_mock(pk=1, estado='pendiente', costo=500),
                _linea_mock(pk=2, estado='rechazada', costo=300),
            ],
        )
        items = construir_items_cotizacion_activos(sol)
        pks = [i['pk'] for i in items]
        self.assertIn(1, pks)
        self.assertNotIn(2, pks)
        self.assertEqual(
            sum(i['costo_unitario'] * i['cantidad'] for i in items if not i['es_servicio']),
            500.0,
        )

    def test_sin_items_cotizables(self):
        sol = _solicitud_mock(
            lineas=[_linea_mock(estado='rechazada')],
        )
        self.assertFalse(solicitud_tiene_items_cotizables(sol))


class CotizacionTotalesFinalTest(SimpleTestCase):
    """Pruebas de suma de precios persistidos (PDF final)."""

    def test_suma_subtotales_aceptados(self):
        items = [
            {
                'descripcion': 'Pantalla',
                'cantidad': 1,
                'precio_unitario_cliente': 1200.0,
                'subtotal_cliente': 1200.0,
                'es_servicio': False,
            },
            {
                'descripcion': 'Limpieza',
                'cantidad': 1,
                'precio_unitario_cliente': 1000.0,
                'subtotal_cliente': 1000.0,
                'costo_unitario': 1160.0,
                'es_servicio': True,
            },
        ]
        calculo = calcular_totales_items_finales(items, diagnostico=570)
        self.assertEqual(calculo['precio_sin_iva'], 2200.0)
        self.assertEqual(calculo['precio_con_iva'], round(1200 * 1.16 + 1160, 2))
