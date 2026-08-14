"""
Tests: folio FL- auto-sugerido al crear orden desde solicitud de baja.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
En Venta Mostrador el almacenista NO debe inventar un FL-. El sistema
sugiere FL-YYYY-NNNN (igual que en cotización sin orden) e infiere la
sucursal del empleado o del técnico.

Estos tests cubren:
1. El helper de consecutivo (sin FL del año → 0001; con uno → siguiente).
2. GET sugerir_fl=1 (folio + sucursal).
3. POST venta_mostrador sin sucursal_id (infiere sucursal).
4. GET de un FL inexistente NO invita a crear con ese número inventado.
5. OOW- sigue igual: buscar y, si no existe, se puede crear con sucursal.
"""

import json

from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from almacen.tests.helpers_integracion_cotizacion import BaseIntegracionCotizacionMixin
from almacen.utils.folio_orden_fl import (
    resolver_sucursal_orden_almacen,
    sugerir_siguiente_folio_fl,
)
from almacen.views import api_buscar_crear_orden_cliente
from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, OrdenServicio


class SugerirFolioFlHelperTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    Regla unitaria del consecutivo FL-YYYY-NNNN y de la sucursal inferida.

    Objetivo: el número lo genera SIGMA; la sucursal no se pide si se puede inferir.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='FL-HELP')

    def test_sin_fl_del_año_empieza_en_0001(self) -> None:
        """
        Caso feliz: no hay FL- de este año → FL-{año}-0001.
        """
        año = timezone.now().year
        self.assertEqual(sugerir_siguiente_folio_fl(), f'FL-{año}-0001')

    def test_con_fl_existente_suma_uno(self) -> None:
        """
        Si ya hay FL-2026-0003, el siguiente es 0004.
        """
        año = timezone.now().year
        self._crear_orden_con_detalle(orden_cliente=f'FL-{año}-0003')

        self.assertEqual(sugerir_siguiente_folio_fl(), f'FL-{año}-0004')

    def test_resolver_sucursal_prioriza_empleado(self) -> None:
        """
        Sucursal del empleado gana; si no tiene, usa la del técnico.
        """
        sucursal_tecnico = Sucursal.objects.create(
            nombre='Sucursal Técnico FL Help',
            codigo='TST-TEC-FLH',
            activa=True,
            ciudad='GDL',
            direccion='Calle Técnico 1',
            horario_atencion='Lun-Vie 9-18',
        )
        tecnico = Empleado.objects.create(
            nombre_completo='Técnico Otra Sucursal',
            cargo='Técnico',
            area='Laboratorio',
            email='tec.flhelp@test.local',
            sucursal=sucursal_tecnico,
            rol=Empleado.ROL_TECNICO,
            activo=True,
        )

        # El empleado del mixin ya tiene self.sucursal
        sucursal = resolver_sucursal_orden_almacen(self.empleado, tecnico)
        self.assertEqual(sucursal, self.sucursal)

        # Sin sucursal en el empleado → fallback al técnico
        self.empleado.sucursal = None
        self.empleado.save(update_fields=['sucursal'])
        sucursal_fallback = resolver_sucursal_orden_almacen(self.empleado, tecnico)
        self.assertEqual(sucursal_fallback, sucursal_tecnico)


class ApiBuscarCrearOrdenFlBajaTest(BaseIntegracionCotizacionMixin, TestCase):
    """
    API GET/POST usada por el formulario de Nueva solicitud (baja).

    Objetivo de negocio:
        Venta Mostrador sugiere FL- e infiere sucursal; OOW- no se rompe.
    """

    databases = {'default', 'mexico'}

    def setUp(self) -> None:
        self._crear_contexto_base(sufijo='FL-API')
        self.tecnico = Empleado.objects.create(
            nombre_completo='Técnico FL API Baja',
            cargo='Técnico',
            area='Laboratorio',
            email='tec.flapi@test.local',
            sucursal=self.sucursal,
            rol=Empleado.ROL_TECNICO,
            activo=True,
        )
        self.url = reverse('almacen:api_buscar_crear_orden')

    def _get(self, query: dict):
        """
        GET autenticado a la API (RequestFactory, sin middleware multi-país).

        Args:
            query: Querystring como dict (sugerir_fl, orden_cliente, etc.).
        """
        request = self.factory.get(self.url, query)
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return api_buscar_crear_orden_cliente(request)

    def _post_json(self, payload: dict):
        """
        POST JSON autenticado a la API de crear orden.

        Args:
            payload: Cuerpo JSON (orden_cliente, tecnico_id, tipo_solicitud...).
        """
        request = self.factory.post(
            self.url,
            data=json.dumps(payload),
            content_type='application/json',
        )
        request.user = self.user
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        return api_buscar_crear_orden_cliente(request)

    def test_get_sugerir_fl_devuelve_folio_y_sucursal(self) -> None:
        """
        GET ?sugerir_fl=1 → siguiente folio + sucursal del empleado logueado.
        """
        año = timezone.now().year
        response = self._get({'sugerir_fl': '1'})
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertEqual(data['numero_fl_sugerido'], f'FL-{año}-0001')
        self.assertEqual(data['sucursal_id'], self.sucursal.pk)
        self.assertEqual(data['sucursal'], self.sucursal.nombre)

    def test_post_venta_mostrador_sin_sucursal_id_infiere(self) -> None:
        """
        POST FL- sin sucursal_id crea la orden con la sucursal del empleado.
        """
        año = timezone.now().year
        folio = f'FL-{año}-0001'
        response = self._post_json({
            'orden_cliente': folio,
            'tecnico_id': self.tecnico.pk,
            'tipo_solicitud': 'venta_mostrador',
        })
        data = json.loads(response.content)

        self.assertTrue(data['success'], msg=data.get('error'))
        self.assertTrue(data['created'])
        self.assertEqual(data['orden_cliente'], folio)
        self.assertEqual(data['sucursal'], self.sucursal.nombre)

        detalle = DetalleEquipo.objects.get(orden_cliente=folio)
        self.assertEqual(detalle.orden.tipo_servicio, 'venta_mostrador')
        self.assertEqual(detalle.orden.estado, 'almacen')
        self.assertEqual(detalle.orden.sucursal, self.sucursal)

    def test_get_fl_inexistente_no_invita_a_inventar_folio(self) -> None:
        """
        Buscar un FL- que no existe NO dice que se puede crear con ese número.
        """
        response = self._get({
            'orden_cliente': 'FL-2099-9999',
            'tipo_solicitud': 'venta_mostrador',
        })
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertFalse(data['found'])
        self.assertFalse(data['puede_crear_con_folio_ingresado'])
        self.assertIn('Crear orden FL nueva', data['mensaje'])

    def test_get_oow_inexistente_sigue_permitiendo_crear(self) -> None:
        """
        OOW- inexistente: el front sí puede crear con el folio escrito + sucursal.
        """
        response = self._get({
            'orden_cliente': 'OOW-NO-EXISTE-01',
            'tipo_solicitud': 'servicio_tecnico',
        })
        data = json.loads(response.content)

        self.assertTrue(data['success'])
        self.assertFalse(data['found'])
        self.assertTrue(data['puede_crear_con_folio_ingresado'])
        self.assertIn('Se puede crear automáticamente', data['mensaje'])

    def test_post_oow_sin_sucursal_id_sigue_exigiendo_sucursal(self) -> None:
        """
        Regresión OOW: sin sucursal_id el POST no infiere (el usuario la elige).
        """
        response = self._post_json({
            'orden_cliente': 'OOW-SIN-SUC-01',
            'tecnico_id': self.tecnico.pk,
            'tipo_solicitud': 'servicio_tecnico',
        })
        data = json.loads(response.content)

        self.assertFalse(data['success'])
        self.assertFalse(data.get('created', False))
        self.assertIn('sucursal', data['error'].lower())
        self.assertFalse(
            DetalleEquipo.objects.filter(orden_cliente='OOW-SIN-SUC-01').exists()
        )

    def test_post_oow_con_sucursal_crea_orden(self) -> None:
        """
        Feliz OOW: con sucursal_id se crea la orden de diagnóstico.
        """
        response = self._post_json({
            'orden_cliente': 'OOW-CON-SUC-01',
            'tecnico_id': self.tecnico.pk,
            'sucursal_id': self.sucursal.pk,
            'tipo_solicitud': 'servicio_tecnico',
        })
        data = json.loads(response.content)

        self.assertTrue(data['success'], msg=data.get('error'))
        self.assertTrue(data['created'])
        orden = OrdenServicio.objects.get(pk=data['orden_id'])
        self.assertEqual(orden.tipo_servicio, 'diagnostico')
        self.assertEqual(orden.estado, 'almacen')
