"""
Tests del filtro del dashboard OOW/FL por es_fuera_garantia.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Antes el dashboard buscaba folios que empezaran con "OOW-" o "FL-".
Ahora usa el booleano es_fuera_garantia y, si eliges OOW o FL, refina
por tipo_servicio (diagnóstico vs venta mostrador).

Estos tests verifican el helper queryset_base_oow_fl sin renderizar
gráficas ni Excel (más rápido y estable en CI).
"""

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase

from inventario.models import Empleado, Sucursal
from servicio_tecnico import views as st_views
from servicio_tecnico import views_dashboard_oow_fl
from servicio_tecnico.models import OrdenServicio
from servicio_tecnico.views_dashboard_oow_fl import queryset_base_oow_fl


User = get_user_model()


class QuerysetBaseOowFlFiltroTest(TestCase):
    """
    Regla de negocio del dashboard: fuera de garantía + tipo de servicio.

    Objetivo:
        Confirmar que "ambos" / "OOW" / "FL" excluyen órdenes en garantía
        y distinguen diagnóstico vs venta mostrador.
    """

    def setUp(self):
        """
        Crea 3 órdenes de prueba:

        1) OOW: fuera de garantía + diagnóstico
        2) FL: fuera de garantía + venta mostrador
        3) Garantía: es_fuera_garantia=False (NO debe aparecer)
        """
        # EXPLICACIÓN PARA PRINCIPIANTES:
        # setUp corre antes de cada test; así cada caso parte de datos limpios.
        # OrdenServicio exige tecnico_asignado_actual (NOT NULL en BD).
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Test Dashboard OOW/FL',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='tecnico_dash_oow_fl',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Dashboard OOW/FL',
            cargo='Técnico',
            area='Laboratorio',
            email='tecnico.dash.oowfl@test.local',
            sucursal=self.sucursal,
            user=self.user,
        )

        # Orden OOW: fuera de garantía con diagnóstico técnico
        self.orden_oow = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            es_fuera_garantia=True,
            tecnico_asignado_actual=self.empleado,
        )

        # Orden FL: fuera de garantía en venta mostrador
        self.orden_fl = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='venta_mostrador',
            estado='espera',
            es_fuera_garantia=True,
            tecnico_asignado_actual=self.empleado,
        )

        # Orden en garantía: debe quedar fuera del dashboard
        self.orden_garantia = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='espera',
            es_fuera_garantia=False,
            tecnico_asignado_actual=self.empleado,
        )

    def test_ambos_solo_fuera_de_garantia(self):
        """
        prefijo=ambos: las 2 fuera de garantía; la de garantía no entra.
        """
        ids = set(queryset_base_oow_fl('ambos').values_list('pk', flat=True))

        self.assertIn(self.orden_oow.pk, ids)
        self.assertIn(self.orden_fl.pk, ids)
        self.assertNotIn(self.orden_garantia.pk, ids)
        self.assertEqual(len(ids), 2)

    def test_oow_solo_diagnostico_fuera_garantia(self):
        """
        prefijo=OOW: solo diagnóstico + es_fuera_garantia=True.
        """
        ids = set(queryset_base_oow_fl('OOW').values_list('pk', flat=True))

        self.assertEqual(ids, {self.orden_oow.pk})
        self.assertNotIn(self.orden_fl.pk, ids)
        self.assertNotIn(self.orden_garantia.pk, ids)

    def test_fl_solo_venta_mostrador_fuera_garantia(self):
        """
        prefijo=FL: solo venta_mostrador + es_fuera_garantia=True.
        """
        ids = set(queryset_base_oow_fl('FL').values_list('pk', flat=True))

        self.assertEqual(ids, {self.orden_fl.pk})
        self.assertNotIn(self.orden_oow.pk, ids)
        self.assertNotIn(self.orden_garantia.pk, ids)

    def test_default_es_ambos(self):
        """
        Sin argumento, el helper se comporta como 'ambos'.
        """
        ids_default = set(queryset_base_oow_fl().values_list('pk', flat=True))
        ids_ambos = set(queryset_base_oow_fl('ambos').values_list('pk', flat=True))
        self.assertEqual(ids_default, ids_ambos)


class QuerysetBaseOowFlHumoTest(SimpleTestCase):
    """Humo: el helper está en el módulo del dashboard y se puede importar."""

    def test_helper_exportado_desde_modulo_dashboard(self):
        """
        Confirma que queryset_base_oow_fl vive en views_dashboard_oow_fl
        (y no se perdió el reexport de las vistas del dashboard).
        """
        self.assertTrue(callable(views_dashboard_oow_fl.queryset_base_oow_fl))
        self.assertIs(
            st_views.dashboard_seguimiento_oow_fl,
            views_dashboard_oow_fl.dashboard_seguimiento_oow_fl,
        )
        self.assertIs(
            st_views.exportar_excel_dashboard_oow_fl,
            views_dashboard_oow_fl.exportar_excel_dashboard_oow_fl,
        )
