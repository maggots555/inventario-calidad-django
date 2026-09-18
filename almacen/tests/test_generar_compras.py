"""
Tests de generación atómica de compras (sin dejar pedidos a medias).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Antes, ``generar_compras`` creaba compras en un loop sin transacción.
Si reventaba en la línea 2, la línea 1 ya estaba comprada en BD.
Estos tests clavan el contrato nuevo:

1) Caso feliz: dos líneas → dos CompraProducto y solicitud completada.
2) Falla a mitad: cero compras, las líneas siguen ``aprobada``.
3) Segundo clic: no duplica (idempotente).
4) El alias de BD sale de la solicitud (mismo helper que recotización).

No se envían correos ni se toca Celery real.
"""

from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from almacen.models import CompraProducto, LineaCotizacion, UnidadCompra
from almacen.tests.helpers_integracion_cotizacion import (
    BaseIntegracionCotizacionMixin,
)
from almacen.utils.generar_compras import generar_compras_desde_solicitud
from almacen.utils.recotizacion import resolver_db_alias


class GenerarComprasAtomicoTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Contrato de negocio: compras completas o nada.

    Objetivo:
        Proteger el clic de Compras contra cortes a mitad de loop y
        contra doble POST.
    """

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='GEN')
        self.orden = self._crear_orden_con_detalle(orden_cliente='OOW-GEN-ATOM-01')
        self.solicitud, self.linea_a = self._crear_solicitud_con_linea(
            orden=self.orden,
            sin_orden_activa=False,
            estado='totalmente_aprobada',
            estado_linea='aprobada',
        )
        # Segunda pieza: el rollback solo se ve con 2+ líneas.
        self.linea_b = LineaCotizacion.objects.create(
            solicitud=self.solicitud,
            producto=self.producto,
            proveedor=self.proveedor,
            descripcion_pieza=f'{self.producto.nombre} BIS',
            cantidad=1,
            costo_unitario=Decimal('80.00'),
            precio_unitario_cliente=Decimal('160.00'),
            estado_cliente='aprobada',
        )

    def test_feliz_crea_una_compra_por_linea_y_cierra_solicitud(self) -> None:
        """
        Caso feliz: dos líneas aprobadas → dos compras y estado completada.
        """
        compras = self.solicitud.generar_compras(usuario=self.user)

        self.assertEqual(len(compras), 2)
        self.assertEqual(CompraProducto.objects.count(), 2)
        self.assertEqual(UnidadCompra.objects.count(), 2)

        self.solicitud.refresh_from_db()
        self.linea_a.refresh_from_db()
        self.linea_b.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'completada')
        self.assertEqual(self.linea_a.estado_cliente, 'compra_generada')
        self.assertEqual(self.linea_b.estado_cliente, 'compra_generada')
        self.assertIsNotNone(self.linea_a.compra_generada_id)
        self.assertIsNotNone(self.linea_b.compra_generada_id)

    def test_falla_a_mitad_no_deja_compras_huerfanas(self) -> None:
        """
        Si la 2ª CompraProducto revienta, la 1ª también se deshace.

        EXPLICACIÓN: simulamos un corte de luz a mitad del loop. La
        transacción debe dejar la BD como al inicio: cero compras,
        líneas todavía ``aprobada``, solicitud sin marcar completada.
        """
        real_create = CompraProducto.objects.create
        contador = {'n': 0}

        def _falla_en_la_segunda(*args, **kwargs):
            # EXPLICACIÓN: la 1ª create sí escribe; la 2ª lanza. atomic()
            # tiene que revertir también esa 1ª escritura.
            contador['n'] += 1
            if contador['n'] >= 2:
                raise RuntimeError('falla simulada a mitad de generar_compras')
            return real_create(*args, **kwargs)

        with patch.object(
            CompraProducto.objects,
            'create',
            side_effect=_falla_en_la_segunda,
        ):
            with self.assertRaises(RuntimeError):
                generar_compras_desde_solicitud(self.solicitud, usuario=self.user)

        self.assertEqual(CompraProducto.objects.count(), 0)
        self.assertEqual(UnidadCompra.objects.count(), 0)
        self.solicitud.refresh_from_db()
        self.linea_a.refresh_from_db()
        self.linea_b.refresh_from_db()
        self.assertEqual(self.solicitud.estado, 'totalmente_aprobada')
        self.assertEqual(self.linea_a.estado_cliente, 'aprobada')
        self.assertEqual(self.linea_b.estado_cliente, 'aprobada')
        self.assertIsNone(self.linea_a.compra_generada_id)
        self.assertIsNone(self.linea_b.compra_generada_id)

    def test_segundo_clic_no_duplica_compras(self) -> None:
        """
        Idempotencia: volver a generar no crea CompraProducto de más.
        """
        primeras = self.solicitud.generar_compras(usuario=self.user)
        self.assertEqual(len(primeras), 2)

        segundas = self.solicitud.generar_compras(usuario=self.user)
        self.assertEqual(segundas, [])
        self.assertEqual(CompraProducto.objects.count(), 2)
        self.assertEqual(
            getattr(self.solicitud, '_resultado_sync_seguimiento_st', {}).get(
                'motivo_omitido'
            ),
            'no_puede_generar',
        )

    def test_alias_de_base_sale_de_la_instancia(self) -> None:
        """
        La transacción debe abrirse en el alias del país, no a ciegas.
        """
        self.solicitud._state.db = 'mexico'
        self.assertEqual(resolver_db_alias(self.solicitud), 'mexico')

    def test_lock_de_lineas_no_bloquea_el_join_nullable(self) -> None:
        """
        PostgreSQL revienta si FOR UPDATE cae en el LEFT JOIN de
        pieza_cotizada_origen / proveedor. El candado debe ser of=('self',).
        """
        import inspect

        fuente = inspect.getsource(generar_compras_desde_solicitud)
        self.assertIn("select_for_update(of=('self',))", fuente)
