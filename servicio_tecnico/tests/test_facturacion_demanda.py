"""
Tests de la fase 1 del autofacturador (GET venta + authenticate).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El portal VO pide un número (webId). SIGMA lo busca en los dígitos de
orden_cliente (OOW-11902 → 11902). Estos tests no llaman al portal ni
al SAT: solo comprueban el JSON y los códigos 200/400/401/404.
"""

import base64
import json
from decimal import Decimal
from unittest.mock import patch

from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse

from inventario.models import Empleado, Sucursal
from scorecard.models import ComponenteEquipo
from servicio_tecnico import views as st_views
from servicio_tecnico import views_facturacion_demanda
from servicio_tecnico.models import (
    Cotizacion,
    DetalleEquipo,
    OrdenServicio,
    PagoOrden,
    PiezaCotizada,
)
from servicio_tecnico.models_facturacion import ComprobanteFiscalOrden
from servicio_tecnico.services.facturacion_demanda import (
    RAZON_COLISION,
    RAZON_NO_NUMERICO,
    RAZON_SIN_ACU,
    RAZON_SIN_GET_PREVIO,
    RAZON_SIN_PAGOS,
    RAZON_YA_TIMBRADA,
    FacturacionDemandaError,
    extraer_digitos,
    obtener_venta_para_facturar,
    web_id_a_entero,
)


API_KEY = 'clave-test-facturacion'
SECRET = 'secret-test-facturacion'


class ExtraerDigitosFolioTest(SimpleTestCase):
    """Unidad: el webId son solo los números del folio del cliente."""

    def test_oow_clasico(self):
        """Feliz: OOW-11902 → 11902."""
        self.assertEqual(extraer_digitos('OOW-11902'), '11902')

    def test_fl_con_anio(self):
        """Feliz: FL-2026-0001 junta todos los dígitos."""
        self.assertEqual(extraer_digitos('FL-2026-0001'), '20260001')

    def test_web_id_no_numerico_lanza_400(self):
        """Borde: letras en el path no son 404, son 400 del PDF."""
        with self.assertRaises(FacturacionDemandaError) as ctx:
            web_id_a_entero('OOW-11902')
        self.assertEqual(ctx.exception.http_status, 400)
        self.assertEqual(ctx.exception.razon, RAZON_NO_NUMERICO)


@override_settings(
    RATELIMIT_ENABLE=False,
    FACTURACION_WEB_API_KEY=API_KEY,
    FACTURACION_WEB_SECRET=SECRET,
    FACTURACION_WEB_TOKEN_TTL=3600,
)
class FacturacionDemandaGetTest(TestCase):
    """
    Integración: authenticate + GET folio con una orden OOW aceptada y pagada.
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Facturación Demanda',
            ciudad='CDMX',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Cajero Facturacion',
            cargo='Recepcionista',
            area='FRONTDESK',
            email='cajero.facturacion@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
        )
        self.orden = self._crear_orden('OOW-11902', 'SN-FAC-11902')
        self.componente = ComponenteEquipo.objects.create(
            nombre='Bateria Dell 40 W',
            tipo_equipo='laptop',
            activo=True,
        )
        self.cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('100.00'),
            usuario_acepto=True,
        )
        PiezaCotizada.objects.create(
            cotizacion=self.cotizacion,
            componente=self.componente,
            cantidad=1,
            costo_unitario=Decimal('200.00'),
            precio_unitario_cliente=Decimal('500.00'),
            aceptada_por_cliente=True,
        )
        PagoOrden.objects.create(
            orden=self.orden,
            monto=Decimal('580.00'),
            tipo='pago_completo',
            metodo='transferencia',
            registrado_por=self.empleado,
        )

    def _crear_orden(self, orden_cliente: str, serie: str) -> OrdenServicio:
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='reparacion',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente=orden_cliente,
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie=serie,
            falla_principal='No enciende',
            gama='baja',
        )
        return orden

    def _token(self) -> str:
        request = self.factory.post(
            reverse('facturacion_web:authenticate'),
            data='{"secret": "%s"}' % SECRET,
            content_type='application/json',
            HTTP_X_API_KEY=API_KEY,
        )
        response = views_facturacion_demanda.authenticate_facturacion_web(request)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)['access_token']

    def _get(self, web_id: str, token: str | None = None, api_key: str | None = None):
        headers = {
            'HTTP_X_API_KEY': API_KEY if api_key is None else api_key,
            'HTTP_AUTHORIZATION': f'Bearer {token or self._token()}',
        }
        request = self.factory.get(
            reverse('facturacion_web:folio', args=[web_id]),
            **headers,
        )
        return views_facturacion_demanda.folio_facturacion_web(request, web_id)

    def test_urls_y_reexport(self):
        """Humo: reverse/resolve y views.py reexportan las vistas nuevas."""
        url_auth = reverse('facturacion_web:authenticate')
        url_folio = reverse('facturacion_web:folio', args=['11902'])
        self.assertEqual(url_auth, '/facturacion-web/authenticate')
        self.assertEqual(url_folio, '/facturacion-web/folio/11902')
        self.assertIs(
            resolve(url_folio).func,
            views_facturacion_demanda.folio_facturacion_web,
        )
        self.assertIs(
            st_views.folio_facturacion_web,
            views_facturacion_demanda.folio_facturacion_web,
        )

    def test_get_feliz_arma_encabezado_y_concepto(self):
        """
        Feliz: OOW-11902 aceptada + pagada → 200.
        Pieza 500 sin IVA; total cobrado 580 (IVA 16%). empresa=2.
        """
        response = self._get('11902')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        encabezado = data['encabezado']
        self.assertEqual(encabezado['folio'], 'OOW-11902')
        self.assertEqual(encabezado['web_id'], '11902')
        self.assertEqual(encabezado['total'], 580.0)
        self.assertEqual(encabezado['metodo_pago'], 'PUE')
        self.assertEqual(encabezado['forma_pago'], '03')
        self.assertEqual(len(data['conceptos']), 1)
        concepto = data['conceptos'][0]
        self.assertEqual(concepto['precio'], 500.0)
        self.assertEqual(concepto['cantidad'], 1)
        self.assertEqual(concepto['empresa'], '2')
        self.assertEqual(concepto['objeto_impuesto'], 2)
        self.assertIn('BATERIA', concepto['descripcion'])
        reserva = ComprobanteFiscalOrden.objects.get(orden=self.orden)
        self.assertIsNotNone(reserva.solicitado_en)
        self.assertEqual(reserva.web_id, 11902)
        self.assertFalse(reserva.esta_timbrado)

    def test_servicio_tambien_encuentra_fl_con_anio(self):
        """Feliz: FL-2026-0001 se pide como webId 20260001."""
        orden_fl = self._crear_orden('FL-2026-0001', 'SN-FAC-FL-0001')
        cot = Cotizacion.objects.create(
            orden=orden_fl,
            usuario_acepto=True,
        )
        PiezaCotizada.objects.create(
            cotizacion=cot,
            componente=self.componente,
            cantidad=1,
            costo_unitario=Decimal('10.00'),
            precio_unitario_cliente=Decimal('100.00'),
            aceptada_por_cliente=True,
        )
        PagoOrden.objects.create(
            orden=orden_fl,
            monto=Decimal('116.00'),
            tipo='pago_completo',
            metodo='efectivo',
            registrado_por=self.empleado,
        )
        payload = obtener_venta_para_facturar('20260001')
        self.assertEqual(payload['encabezado']['folio'], 'FL-2026-0001')
        self.assertEqual(payload['encabezado']['forma_pago'], '01')

    def test_400_si_web_id_no_es_numero(self):
        """Borde: el path trae el folio con letras."""
        response = self._get('OOW-11902')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['razon'], RAZON_NO_NUMERICO)

    def test_404_si_no_existe_el_folio(self):
        """Borde: número que no corresponde a ninguna orden."""
        response = self._get('999001')
        self.assertEqual(response.status_code, 404)

    def test_400_si_cotizacion_no_aceptada(self):
        """ACU: sin usuario_acepto=True el GET no arma la venta."""
        self.cotizacion.usuario_acepto = None
        self.cotizacion.save(update_fields=['usuario_acepto'])
        response = self._get('11902')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['razon'], RAZON_SIN_ACU)

    def test_400_si_no_hay_pagos(self):
        """El PDF pide pagos para facturar además de ACU."""
        PagoOrden.objects.filter(orden=self.orden).delete()
        response = self._get('11902')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['razon'], RAZON_SIN_PAGOS)

    def test_400_si_oow_y_fl_comparten_digitos(self):
        """Colisión: OOW-11902 y FL-11902 no se facturan a ciegas."""
        self._crear_orden('FL-11902', 'SN-FAC-FL-11902')
        response = self._get('11902')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['razon'], RAZON_COLISION)

    def test_401_sin_api_key(self):
        """Sin X-API-KEY el portal no entra."""
        response = self._get('11902', api_key='')
        self.assertEqual(response.status_code, 401)

    def test_authenticate_secret_incorrecto(self):
        """Body con secret equivocado → 401."""
        request = self.factory.post(
            reverse('facturacion_web:authenticate'),
            data='{"secret": "no-es"}',
            content_type='application/json',
            HTTP_X_API_KEY=API_KEY,
        )
        response = views_facturacion_demanda.authenticate_facturacion_web(request)
        self.assertEqual(response.status_code, 401)

    def test_ppd_si_el_saldo_no_esta_cubierto(self):
        """Borde: anticipo 290 de 580 → metodo_pago PPD."""
        PagoOrden.objects.filter(orden=self.orden).update(monto=Decimal('290.00'))
        response = self._get('11902')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['encabezado']['metodo_pago'], 'PPD')

    def _put(self, web_id: str, body: dict, token: str | None = None):
        """PUT autenticado al mismo path del GET."""
        request = self.factory.put(
            reverse('facturacion_web:folio', args=[web_id]),
            data=json.dumps(body),
            content_type='application/json',
            HTTP_X_API_KEY=API_KEY,
            HTTP_AUTHORIZATION=f'Bearer {token or self._token()}',
        )
        return views_facturacion_demanda.folio_facturacion_web(request, web_id)

    def _payload_cfdi(self, uuid_sat: str = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'):
        xml = '<?xml version="1.0"?><cfdi:Comprobante/>'
        pdf_b64 = base64.b64encode(b'%PDF-1.4 test').decode('ascii')
        return {
            'cadenaOriginalSAT': 'cadena-test',
            'noCertificadoSAT': '000010000001',
            'noCertificadoCFDI': '000010000002',
            'uuid': uuid_sat,
            'selloSAT': 'sello-sat',
            'selloCFDI': 'sello-cfdi',
            'fechaTimbrado': '2025-01-13T15:00:00',
            'qrCode': 'qr-test',
            'cfdi': xml,
            'pdf64': pdf_b64,
        }

    def test_put_sin_get_previo_es_404(self):
        """El PDF: sin GET antes, el PUT no acepta el CFDI."""
        response = self._put('11902', self._payload_cfdi())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            json.loads(response.content)['razon'],
            RAZON_SIN_GET_PREVIO,
        )
        self.orden.refresh_from_db()
        self.assertFalse(self.orden.factura_emitida)

    def test_put_despues_del_get_guarda_xml_y_pdf(self):
        """Feliz: GET reserva + PUT 204 + archivos + factura_emitida."""
        self.assertEqual(self._get('11902').status_code, 200)
        response = self._put('11902', self._payload_cfdi())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b'')
        comprobante = ComprobanteFiscalOrden.objects.get(orden=self.orden)
        self.assertEqual(comprobante.uuid, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        self.assertTrue(comprobante.cfdi_xml)
        self.assertTrue(comprobante.pdf)
        self.assertIn(b'<cfdi:Comprobante', comprobante.cfdi_xml.read())
        self.assertTrue(comprobante.pdf.read().startswith(b'%PDF'))
        self.orden.refresh_from_db()
        self.assertTrue(self.orden.factura_emitida)

    def test_put_mismo_uuid_es_idempotente(self):
        """Borde: el portal reintenta el mismo UUID → 204 otra vez."""
        self._get('11902')
        payload = self._payload_cfdi()
        self.assertEqual(self._put('11902', payload).status_code, 204)
        self.assertEqual(self._put('11902', payload).status_code, 204)
        self.assertEqual(ComprobanteFiscalOrden.objects.filter(orden=self.orden).count(), 1)

    def test_put_otro_uuid_cuando_ya_hay_factura_es_400(self):
        """Borde: no se pisa un CFDI ya guardado con otro UUID."""
        self._get('11902')
        self._put('11902', self._payload_cfdi('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'))
        response = self._put(
            '11902',
            self._payload_cfdi('ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee'),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['razon'], RAZON_YA_TIMBRADA)


class FacturacionDemandaPaisTest(TestCase):
    """CFDI solo México: otro país no debe armar venta."""

    def test_argentina_responde_400(self):
        with patch(
            'servicio_tecnico.services.facturacion_demanda.get_pais_actual',
            return_value={'codigo': 'AR'},
        ):
            with self.assertRaises(FacturacionDemandaError) as ctx:
                obtener_venta_para_facturar('11902')
        self.assertEqual(ctx.exception.http_status, 400)
        self.assertIn('México', ctx.exception.razon)
