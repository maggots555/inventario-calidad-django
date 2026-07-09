"""
Tests de filtrado por estado_cliente y PDF final de cotización.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from almacen.utils.cotizacion_items_cliente import (
    construir_items_cotizacion_activos,
    construir_items_cotizacion_final,
    linea_es_aceptada_final,
    linea_es_cotizable,
    serializar_linea_cotizacion,
    solicitud_pdf_final_es_solo_reacondicionado,
    solicitud_puede_descargar_pdf_final,
    solicitud_tiene_items_cotizables,
)
from almacen.utils.pdf_cotizacion_cliente import calcular_totales_items_finales


def _linea_mock(pk=1, estado='pendiente', costo=100.0, cantidad=1, es_reac=False, precio_cliente=None):
    """Crea un mock de LineaCotizacion para pruebas sin BD."""
    producto = SimpleNamespace(nombre='RAM 8GB' if not es_reac else 'EQUIPO REACONDICIONADO')
    if precio_cliente is None and es_reac:
        precio_cliente = 500.0
    return SimpleNamespace(
        pk=pk,
        producto=producto,
        descripcion_pieza='',
        cantidad=cantidad,
        costo_unitario=costo,
        es_necesaria=True,
        es_linea_reacondicionado=es_reac,
        tiempo_entrega_estimado=5,
        estado_cliente=estado,
        precio_unitario_cliente=precio_cliente,
        subtotal_cliente_sin_iva=precio_cliente,
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
        resultado = list(lineas)
        if estado_in:
            resultado = [l for l in resultado if l.estado_cliente in estado_in]
        if costo_gt is not None:
            resultado = [l for l in resultado if float(l.costo_unitario or 0) > costo_gt]
        if 'es_linea_reacondicionado' in kwargs:
            flag = kwargs['es_linea_reacondicionado']
            resultado = [l for l in resultado if l.es_linea_reacondicionado == flag]
        return resultado

    def _filtrar_servicios(**kwargs):
        estado_in = kwargs.get('estado_cliente__in', ())
        costo_gt = kwargs.get('costo__gt')
        return [
            s for s in servicios
            if s.estado_cliente in estado_in
            and (costo_gt is None or float(s.costo or 0) > costo_gt)
        ]

    def lineas_filter(**kwargs):
        filtradas = _filtrar_lineas(**kwargs)
        mock_qs = MagicMock()
        mock_qs.__iter__ = lambda s: iter(filtradas)
        mock_qs.exists.return_value = len(filtradas) > 0
        mock_qs.first.return_value = filtradas[0] if filtradas else None
        mock_qs.filter.side_effect = lambda **kw: lineas_filter(**{**kwargs, **kw})
        mock_qs.select_related.return_value = mock_qs
        return mock_qs

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


class CotizacionPdfFinalReacondicionadoTest(SimpleTestCase):
    """PDF final cuando solo se acepta equipo reacondicionado."""

    def test_solo_reac_aceptado_detectado(self):
        sol = _solicitud_mock(
            lineas=[
                _linea_mock(pk=1, estado='rechazada', costo=200),
                _linea_mock(pk=2, estado='aprobada', costo=8000, es_reac=True),
            ],
        )
        self.assertTrue(solicitud_pdf_final_es_solo_reacondicionado(sol))

    def test_reac_y_reparacion_no_es_solo_reac(self):
        sol = _solicitud_mock(
            lineas=[
                _linea_mock(pk=1, estado='aprobada', costo=200),
                _linea_mock(pk=2, estado='aprobada', costo=8000, es_reac=True),
            ],
        )
        self.assertFalse(solicitud_pdf_final_es_solo_reacondicionado(sol))

    def test_construir_final_excluye_linea_reac(self):
        sol = _solicitud_mock(
            lineas=[
                _linea_mock(pk=1, estado='aprobada', costo=200, precio_cliente=150.0),
                _linea_mock(pk=2, estado='aprobada', costo=8000, es_reac=True),
            ],
        )
        items = construir_items_cotizacion_final(sol)
        pks = [i['pk'] for i in items]
        self.assertIn(1, pks)
        self.assertNotIn(2, pks)

    def test_puede_descargar_pdf_final_solo_reac_sin_fecha_precios(self):
        sol = _solicitud_mock(
            lineas=[_linea_mock(pk=2, estado='aprobada', costo=8000, es_reac=True)],
        )
        sol.estado = 'parcialmente_aprobada'
        sol.fecha_precios_cliente = None
        sol.resultado_costeo_reac = {'total_precio_contado_mxn': 15000}
        self.assertTrue(solicitud_puede_descargar_pdf_final(sol))
