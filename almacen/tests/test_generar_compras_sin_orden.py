"""
Tests de bloqueo de Generar Compras sin orden vinculada.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando una cotización se crea en modo "sin orden activa", el cliente puede
aprobar líneas antes de que exista una OrdenServicio. Estos tests verifican
que no se permita generar compras hasta vincular o crear la orden.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

from django.test import SimpleTestCase

from almacen.models import SolicitudCotizacion


def _solicitud_mock(
    *,
    sin_orden_activa=False,
    orden_servicio=None,
    estado='totalmente_aprobada',
    lineas_aprobadas_pendientes=True,
):
    """Construye un mock de SolicitudCotizacion con líneas filtrables."""
    qs_lineas = MagicMock()
    qs_lineas.exists.return_value = lineas_aprobadas_pendientes

    solicitud = SimpleNamespace(
        sin_orden_activa=sin_orden_activa,
        orden_servicio=orden_servicio,
        estado=estado,
        lineas=MagicMock(),
    )
    solicitud.lineas.filter.return_value = qs_lineas
    return solicitud


class GenerarComprasSinOrdenTest(SimpleTestCase):
    """Valida puede_generar_compras() y compras_pendientes_sin_orden()."""

    def test_sin_orden_activa_sin_orden_servicio_bloquea_compras(self):
        solicitud = _solicitud_mock(sin_orden_activa=True, orden_servicio=None)

        self.assertFalse(SolicitudCotizacion.puede_generar_compras(solicitud))
        self.assertTrue(SolicitudCotizacion.compras_pendientes_sin_orden(solicitud))

    def test_sin_orden_activa_con_orden_servicio_permite_compras(self):
        orden = SimpleNamespace(pk=1, numero_orden_interno='FL-2026-0001')
        solicitud = _solicitud_mock(sin_orden_activa=True, orden_servicio=orden)

        self.assertTrue(SolicitudCotizacion.puede_generar_compras(solicitud))
        self.assertFalse(SolicitudCotizacion.compras_pendientes_sin_orden(solicitud))

    def test_con_orden_desde_inicio_no_requiere_vinculacion_extra(self):
        """Cotizaciones normales (sin_orden_activa=False) no cambian de comportamiento."""
        orden = SimpleNamespace(pk=2, numero_orden_interno='OOW-2026-0005')
        solicitud = _solicitud_mock(sin_orden_activa=False, orden_servicio=orden)

        self.assertTrue(SolicitudCotizacion.puede_generar_compras(solicitud))
        self.assertFalse(SolicitudCotizacion.compras_pendientes_sin_orden(solicitud))

    def test_sin_lineas_pendientes_no_marca_compras_bloqueadas(self):
        solicitud = _solicitud_mock(
            sin_orden_activa=True,
            orden_servicio=None,
            lineas_aprobadas_pendientes=False,
        )

        self.assertFalse(SolicitudCotizacion.puede_generar_compras(solicitud))
        self.assertFalse(SolicitudCotizacion.compras_pendientes_sin_orden(solicitud))
