"""
Tests del autofacturador PUE/PPD: webId, API GET/PUT y bloque de seguimiento.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El cliente teclea un identificador en el portal VO: `SAT9596-1`. Eso quiere
decir sucursal Satélite (prefijo), folio 9596 y documento tipo 1 (PUE). SIGMA
resuelve ese texto, calcula qué se puede facturar y arma el JSON del CFDI.

Cubrimos tres capas:
    1. Unidad — armar y leer el webId (sin base de datos).
    2. Integración — GET/PUT del API con órdenes reales.
    3. Vista pública — el cliente ve su webId y nunca los secretos.
"""

import base64
import json
import secrets
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
    EnlaceSeguimientoCliente,
    OrdenServicio,
    PagoOrden,
    PiezaCotizada,
    VentaMostrador,
)
from servicio_tecnico.models_facturacion import DocumentoFiscalOrden
from servicio_tecnico.services.facturacion_demanda import (
    RAZON_COLISION,
    RAZON_NO_FACTURABLE,
    RAZON_SIN_GET_PREVIO,
    RAZON_SIN_PAGOS,
    RAZON_TIPO_AMBIGUO,
    RAZON_WEB_ID_INVALIDO,
    RAZON_YA_TIMBRADA,
    FacturacionDemandaError,
    contexto_autofactura_seguimiento,
    obtener_venta_para_facturar,
)
from servicio_tecnico.services.facturacion_web_id import (
    construir_web_id,
    desglosar_web_id,
    extraer_digitos,
)
from servicio_tecnico.services.diagnostico_catalogo import (
    aplicar_perfil_diagnostico,
    tarifa_perfil,
)
from servicio_tecnico.services.pagos_diagnostico import resumen_diagnostico
from servicio_tecnico.services.pagos_orden import calcular_resumen_cobro
from servicio_tecnico.tests.helpers_tarifario import sembrar_tarifario
from servicio_tecnico.views_seguimiento_cliente import seguimiento_orden_cliente


API_KEY = 'clave-test-facturacion'
SECRET = 'secret-test-facturacion'

# Storage sin manifest: los tests renderizan templates con {% static %} y no
# corremos collectstatic en CI.
STORAGES_TEST = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
    },
}


class WebIdUnidadTest(SimpleTestCase):
    """Unidad: armar y leer el identificador que teclea el cliente."""

    def test_extraer_digitos_oow(self):
        """Feliz: OOW-11902 → 11902."""
        self.assertEqual(extraer_digitos('OOW-11902'), '11902')

    def test_extraer_digitos_fl_con_anio(self):
        """Feliz: FL-2026-0001 junta todos los dígitos."""
        self.assertEqual(extraer_digitos('FL-2026-0001'), '20260001')

    def test_desglosar_completo(self):
        """Feliz: SAT9596-1 se parte en sucursal, folio y tipo PUE."""
        partes = desglosar_web_id('SAT9596-1')
        self.assertEqual(partes.prefijo, 'SAT')
        self.assertEqual(partes.digitos, '9596')
        self.assertEqual(partes.tipo, DocumentoFiscalOrden.TIPO_PUE)

    def test_desglosar_ppd(self):
        """Feliz: el sufijo 2 es PPD."""
        self.assertEqual(
            desglosar_web_id('DROP2545-2').tipo,
            DocumentoFiscalOrden.TIPO_PPD,
        )

    def test_desglosar_tolera_minusculas_y_sin_sufijo(self):
        """Borde: el cliente teclea en minúsculas y sin el guion."""
        partes = desglosar_web_id(' sat9596 ')
        self.assertEqual(partes.prefijo, 'SAT')
        self.assertIsNone(partes.tipo)

    def test_desglosar_solo_digitos(self):
        """Compatibilidad: las primeras pruebas mandaban solo el número."""
        partes = desglosar_web_id('9596')
        self.assertEqual(partes.prefijo, '')
        self.assertEqual(partes.numero, 9596)

    def test_desglosar_normaliza_ceros_a_la_izquierda(self):
        """Borde: 0123 y 123 deben ser el mismo folio."""
        self.assertEqual(desglosar_web_id('SAT0123-1').digitos, '123')

    def test_desglosar_invalido(self):
        """Borde: sin dígitos o con sufijo desconocido no hay webId."""
        self.assertIsNone(desglosar_web_id('SAT'))
        self.assertIsNone(desglosar_web_id(''))
        self.assertIsNone(desglosar_web_id('SAT9596-9'))


class BaseFacturacionTest(TestCase):
    """Semillas compartidas: sucursal con prefijo, empleado y órdenes OOW."""

    def _crear_sucursal(self, nombre: str, prefijo: str) -> Sucursal:
        return Sucursal.objects.create(
            nombre=nombre,
            ciudad='CDMX',
            prefijo_facturacion=prefijo,
        )

    def _crear_orden(
        self,
        orden_cliente: str,
        serie: str,
        sucursal=None,
        gama: str = 'baja',
    ) -> OrdenServicio:
        """Orden con detalle de equipo (el save sincroniza es_fuera_garantia)."""
        orden = OrdenServicio.objects.create(
            sucursal=sucursal or self.sucursal,
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
            gama=gama,
        )
        orden.refresh_from_db()
        return orden


@override_settings(
    RATELIMIT_ENABLE=False,
    FACTURACION_WEB_API_KEY=API_KEY,
    FACTURACION_WEB_SECRET=SECRET,
    FACTURACION_WEB_TOKEN_TTL=3600,
    STORAGES=STORAGES_TEST,
)
class FacturacionApiTest(BaseFacturacionTest):
    """
    Integración del contrato HTTP: authenticate, GET folio y PUT folio.

    La orden base tiene diagnóstico de $500 pagado en efectivo (PUE) y piezas
    por $500 + IVA con un anticipo de $290 validado (PPD).
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = self._crear_sucursal('Satelite', 'SAT')
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
            costo_mano_obra=Decimal('500.00'),
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

    # ── Helpers HTTP ────────────────────────────────────────────────────

    def _pagar_diagnostico(self, monto='500.00'):
        """Efectivo = nace en no_aplica, o sea dinero ya verificado."""
        return PagoOrden.objects.create(
            orden=self.orden,
            monto=Decimal(monto),
            tipo='diagnostico',
            metodo='efectivo',
            estado_validacion='no_aplica',
            registrado_por=self.empleado,
        )

    def _pagar_reparacion(self, monto='290.00', estado='validado'):
        return PagoOrden.objects.create(
            orden=self.orden,
            monto=Decimal(monto),
            tipo='anticipo',
            metodo='transferencia',
            estado_validacion=estado,
            registrado_por=self.empleado,
        )

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

    def _get(self, web_id: str, api_key: str | None = None):
        request = self.factory.get(
            reverse('facturacion_web:folio', args=[web_id]),
            HTTP_X_API_KEY=API_KEY if api_key is None else api_key,
            HTTP_AUTHORIZATION=f'Bearer {self._token()}',
        )
        return views_facturacion_demanda.folio_facturacion_web(request, web_id)

    def _put(self, web_id: str, body: dict):
        request = self.factory.put(
            reverse('facturacion_web:folio', args=[web_id]),
            data=json.dumps(body),
            content_type='application/json',
            HTTP_X_API_KEY=API_KEY,
            HTTP_AUTHORIZATION=f'Bearer {self._token()}',
        )
        return views_facturacion_demanda.folio_facturacion_web(request, web_id)

    def _payload_cfdi(self, uuid_sat: str = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'):
        return {
            'cadenaOriginalSAT': 'cadena-test',
            'noCertificadoSAT': '000010000001',
            'noCertificadoCFDI': '000010000002',
            'uuid': uuid_sat,
            'selloSAT': 'sello-sat',
            'selloCFDI': 'sello-cfdi',
            'fechaTimbrado': '2025-01-13T15:00:00',
            'qrCode': 'qr-test',
            'cfdi': '<?xml version="1.0"?><cfdi:Comprobante/>',
            'pdf64': base64.b64encode(b'%PDF-1.4 test').decode('ascii'),
        }

    # ── Humo de rutas ───────────────────────────────────────────────────

    def test_urls_y_reexport(self):
        """Humo: reverse/resolve y views.py reexportan las vistas."""
        self.assertEqual(
            reverse('facturacion_web:authenticate'),
            '/facturacion-web/authenticate',
        )
        url_folio = reverse('facturacion_web:folio', args=['SAT11902-1'])
        self.assertEqual(url_folio, '/facturacion-web/folio/SAT11902-1')
        self.assertIs(
            resolve(url_folio).func,
            views_facturacion_demanda.folio_facturacion_web,
        )
        self.assertIs(
            st_views.folio_facturacion_web,
            views_facturacion_demanda.folio_facturacion_web,
        )

    # ── PUE: el diagnóstico ─────────────────────────────────────────────

    def test_get_pue_desglosa_iva_del_diagnostico(self):
        """
        Feliz: diagnóstico de $500 pagado en efectivo → PUE con IVA aparte.
        500 + 80 de IVA = 580 y un solo concepto de servicio.
        """
        self._pagar_diagnostico()
        response = self._get('SAT11902-1')
        self.assertEqual(response.status_code, 200)

        encabezado = json.loads(response.content)['encabezado']
        self.assertEqual(encabezado['web_id'], 'SAT11902-1')
        self.assertEqual(encabezado['folio'], 'OOW-11902')
        self.assertEqual(encabezado['tipo_factura'], 1)
        self.assertEqual(encabezado['metodo_pago'], 'PUE')
        self.assertEqual(encabezado['forma_pago'], '01')
        self.assertEqual(encabezado['subtotal'], 500.0)
        self.assertEqual(encabezado['iva'], 80.0)
        self.assertEqual(encabezado['total'], 580.0)

        conceptos = json.loads(response.content)['conceptos']
        self.assertEqual(len(conceptos), 1)
        self.assertEqual(conceptos[0]['descripcion'], 'Diagnóstico')
        self.assertEqual(conceptos[0]['precio'], 500.0)
        self.assertEqual(conceptos[0]['empresa'], '2')

    def test_get_pue_reserva_para_el_put(self):
        """El GET deja constancia (solicitado_en) sin timbrar nada."""
        self._pagar_diagnostico()
        self._get('SAT11902-1')
        documento = DocumentoFiscalOrden.objects.get(
            orden=self.orden,
            tipo=DocumentoFiscalOrden.TIPO_PUE,
        )
        self.assertIsNotNone(documento.solicitado_en)
        self.assertFalse(documento.esta_timbrado)

    def test_diagnostico_pendiente_de_validar_no_factura(self):
        """
        Borde: transferencia sin conciliar no habilita la factura.
        El dinero todavía no se vio en la cuenta de la empresa.
        """
        PagoOrden.objects.create(
            orden=self.orden,
            monto=Decimal('500.00'),
            tipo='diagnostico',
            metodo='transferencia',
            estado_validacion='pendiente',
            registrado_por=self.empleado,
        )
        response = self._get('SAT11902-1')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['razon'], RAZON_SIN_PAGOS)

    # ── PPD: el anticipo ────────────────────────────────────────────────

    def test_get_ppd_es_anticipo_sin_piezas(self):
        """
        Feliz: anticipo de $290 sobre $580 → PPD con un solo concepto,
        "Anticipo del bien o servicio", sin mencionar la batería.
        """
        self._pagar_reparacion()
        response = self._get('SAT11902-2')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)

        self.assertEqual(data['encabezado']['tipo_factura'], 2)
        self.assertEqual(data['encabezado']['metodo_pago'], 'PPD')
        self.assertEqual(data['encabezado']['total'], 290.0)
        self.assertEqual(len(data['conceptos']), 1)
        self.assertEqual(
            data['conceptos'][0]['descripcion'],
            'Anticipo del bien o servicio',
        )
        self.assertNotIn('Bateria', json.dumps(data))

    def test_reparacion_liquidada_sigue_siendo_ppd(self):
        """
        Regla: lo que define PPD es la naturaleza del cobro (una reparación
        con piezas que se paga en partes), no si ya quedó liquidada. Aunque
        el cliente cubra el 100%, el documento sigue siendo el de anticipo.
        """
        self._pagar_reparacion(monto='580.00')
        response = self._get('SAT11902-2')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['encabezado']['total'], 580.0)

    def test_servicio_de_mostrador_liquidado_solo_genera_pue(self):
        """
        Borde crítico: una orden de puros servicios (limpieza) liquidada se
        factura UNA sola vez, como PUE. Nunca dos CFDI por el mismo peso.
        """
        # Orden nueva sin cotización: solo venta mostrador con limpieza.
        orden = self._crear_orden('OOW-11950', 'SN-FAC-VM-11950')
        VentaMostrador.objects.create(
            orden=orden,
            folio_venta='VM-TEST-0001',
            incluye_limpieza=True,
            costo_limpieza=Decimal('580.00'),
        )
        PagoOrden.objects.create(
            orden=orden,
            monto=Decimal('580.00'),
            tipo='pago_completo',
            metodo='efectivo',
            estado_validacion='no_aplica',
            registrado_por=self.empleado,
        )

        response = self._get('SAT11950-1')
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['encabezado']['metodo_pago'], 'PUE')
        # 580 con IVA incluido → 500 antes de IVA + 80 de IVA.
        self.assertEqual(data['encabezado']['subtotal'], 500.0)
        self.assertEqual(data['encabezado']['total'], 580.0)
        self.assertEqual(
            data['conceptos'][0]['descripcion'],
            'Limpieza y Mantenimiento',
        )
        # Y no se creó también un PPD por ese mismo dinero.
        self.assertEqual(
            list(
                DocumentoFiscalOrden.objects.filter(orden=orden)
                .values_list('tipo', flat=True)
            ),
            [DocumentoFiscalOrden.TIPO_PUE],
        )

    # ── Resolución del webId ────────────────────────────────────────────

    def test_sin_sufijo_con_dos_documentos_pide_el_tipo(self):
        """Borde: PUE y PPD a la vez → SIGMA no adivina cuál quiso."""
        self._pagar_diagnostico()
        self._pagar_reparacion()
        response = self._get('SAT11902')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['razon'], RAZON_TIPO_AMBIGUO)

    def test_sin_sufijo_con_un_solo_documento_funciona(self):
        """Compatibilidad: si solo hay uno, el webId corto basta."""
        self._pagar_diagnostico()
        self.assertEqual(self._get('SAT11902').status_code, 200)
        self.assertEqual(self._get('11902').status_code, 200)

    def test_prefijo_resuelve_colision_de_folios(self):
        """
        Feliz: OOW-11902 en Satélite y FL-11902 en Drop Off ya no chocan,
        porque el prefijo del webId dice de qué sucursal es.
        """
        self._pagar_diagnostico()
        drop = self._crear_sucursal('Drop Off Sur', 'DROP')
        self._crear_orden('FL-11902', 'SN-FAC-FL-11902', sucursal=drop)
        self.assertEqual(self._get('SAT11902-1').status_code, 200)

    def test_colision_sin_prefijo_sigue_siendo_400(self):
        """Borde: sin prefijo dos folios iguales siguen siendo ambiguos."""
        self._pagar_diagnostico()
        drop = self._crear_sucursal('Drop Off Sur', 'DROP')
        self._crear_orden('FL-11902', 'SN-FAC-FL-11902', sucursal=drop)
        response = self._get('11902')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['razon'], RAZON_COLISION)

    def test_web_id_con_formato_invalido_es_400(self):
        """Borde: texto sin dígitos no es 404 de Django, es 400 del contrato."""
        response = self._get('SAT')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content)['razon'],
            RAZON_WEB_ID_INVALIDO,
        )

    def test_404_si_no_existe_el_folio(self):
        """Borde: número que no corresponde a ninguna orden."""
        self.assertEqual(self._get('SAT999001-1').status_code, 404)

    def test_400_si_no_hay_pagos(self):
        """Sin dinero verificado no hay nada que facturar."""
        response = self._get('SAT11902-1')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['razon'], RAZON_SIN_PAGOS)

    # ── Reglas de negocio que bloquean ──────────────────────────────────

    def test_orden_en_garantia_no_se_autofactura(self):
        """Regla: dentro de garantía el cliente no paga, así que no factura."""
        orden_garantia = self._crear_orden('G-11903', 'SN-FAC-GARANTIA')
        self.assertFalse(orden_garantia.es_fuera_garantia)
        PagoOrden.objects.create(
            orden=orden_garantia,
            monto=Decimal('100.00'),
            tipo='diagnostico',
            metodo='efectivo',
            estado_validacion='no_aplica',
            registrado_por=self.empleado,
        )
        response = self._get('SAT11903-1')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            json.loads(response.content)['razon'],
            RAZON_NO_FACTURABLE,
        )

    def test_sucursal_sin_prefijo_no_factura(self):
        """Regla: sin prefijo capturado no hay webId que ofrecer."""
        sin_prefijo = self._crear_sucursal('Sucursal Preview', '')
        orden = self._crear_orden('OOW-11904', 'SN-FAC-11904', sucursal=sin_prefijo)
        self.assertEqual(construir_web_id(orden, DocumentoFiscalOrden.TIPO_PUE), '')

    # ── Autenticación ───────────────────────────────────────────────────

    def test_401_sin_api_key(self):
        """Sin X-API-KEY el portal no entra."""
        self.assertEqual(self._get('SAT11902-1', api_key='').status_code, 401)

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

    # ── PUT del CFDI timbrado ───────────────────────────────────────────

    def test_put_sin_get_previo_es_404(self):
        """El contrato: sin GET antes, el PUT no acepta el CFDI."""
        self._pagar_diagnostico()
        response = self._put('SAT11902-1', self._payload_cfdi())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            json.loads(response.content)['razon'],
            RAZON_SIN_GET_PREVIO,
        )
        self.orden.refresh_from_db()
        self.assertFalse(self.orden.factura_emitida)

    def test_put_despues_del_get_guarda_xml_y_pdf(self):
        """Feliz: GET reserva + PUT 204 + archivos + factura_emitida."""
        self._pagar_diagnostico()
        self.assertEqual(self._get('SAT11902-1').status_code, 200)
        response = self._put('SAT11902-1', self._payload_cfdi())
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b'')

        documento = DocumentoFiscalOrden.objects.get(
            orden=self.orden,
            tipo=DocumentoFiscalOrden.TIPO_PUE,
        )
        self.assertEqual(documento.uuid, 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee')
        self.assertIn(b'<cfdi:Comprobante', documento.cfdi_xml.read())
        self.assertTrue(documento.pdf.read().startswith(b'%PDF'))
        self.orden.refresh_from_db()
        self.assertTrue(self.orden.factura_emitida)

    def test_put_mismo_uuid_es_idempotente(self):
        """Borde: el portal reintenta el mismo UUID → 204 otra vez."""
        self._pagar_diagnostico()
        self._get('SAT11902-1')
        payload = self._payload_cfdi()
        self.assertEqual(self._put('SAT11902-1', payload).status_code, 204)
        self.assertEqual(self._put('SAT11902-1', payload).status_code, 204)
        self.assertEqual(
            DocumentoFiscalOrden.objects.filter(orden=self.orden).count(),
            1,
        )

    def test_put_otro_uuid_cuando_ya_hay_factura_es_400(self):
        """Borde: no se pisa un CFDI ya guardado con otro UUID."""
        self._pagar_diagnostico()
        self._get('SAT11902-1')
        self._put('SAT11902-1', self._payload_cfdi())
        response = self._put(
            'SAT11902-1',
            self._payload_cfdi('ffffffff-bbbb-cccc-dddd-eeeeeeeeeeee'),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(json.loads(response.content)['razon'], RAZON_YA_TIMBRADA)

    def test_documento_timbrado_no_se_recalcula(self):
        """
        Regla fiscal: una vez timbrado, el documento se congela aunque
        después cambie el costo de la mano de obra.
        """
        self._pagar_diagnostico()
        self._get('SAT11902-1')
        self._put('SAT11902-1', self._payload_cfdi())

        self.cotizacion.costo_mano_obra = Decimal('999.00')
        self.cotizacion.save(update_fields=['costo_mano_obra'])
        contexto_autofactura_seguimiento(self.orden)

        documento = DocumentoFiscalOrden.objects.get(
            orden=self.orden,
            tipo=DocumentoFiscalOrden.TIPO_PUE,
        )
        self.assertEqual(documento.subtotal, Decimal('500.00'))

    def test_pue_timbrado_deja_abierto_el_ppd(self):
        """
        Borde: timbrar el diagnóstico no debe cerrar la orden si todavía
        falta facturar el anticipo de la reparación.
        """
        self._pagar_diagnostico()
        self._pagar_reparacion()
        self._get('SAT11902-1')
        self.assertEqual(self._put('SAT11902-1', self._payload_cfdi()).status_code, 204)
        self.orden.refresh_from_db()
        self.assertFalse(self.orden.factura_emitida)
        self.assertEqual(self._get('SAT11902-2').status_code, 200)


class DiagnosticoPagosTest(BaseFacturacionTest):
    """El diagnóstico es un bolsillo aparte del saldo de la reparación."""

    def setUp(self):
        self.sucursal = self._crear_sucursal('Satelite', 'SAT')
        self.empleado = Empleado.objects.create(
            nombre_completo='Cajero Diagnostico',
            cargo='Recepcionista',
            area='FRONTDESK',
            email='cajero.diag@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
        )
        self.orden = self._crear_orden('OOW-12050', 'SN-DIAG-12050', gama='alta')
        componente = ComponenteEquipo.objects.create(
            nombre='Teclado Diag',
            tipo_equipo='laptop',
            activo=True,
        )
        self.cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('864.00'),
            usuario_acepto=True,
        )
        PiezaCotizada.objects.create(
            cotizacion=self.cotizacion,
            componente=componente,
            cantidad=1,
            costo_unitario=Decimal('100.00'),
            precio_unitario_cliente=Decimal('1000.00'),
            aceptada_por_cliente=True,
        )

    def test_pago_de_diagnostico_no_toca_el_saldo_de_piezas(self):
        """
        Regla: el diagnóstico no está sumado en el total de piezas, así que
        tampoco puede contarse como abono de esas piezas.
        """
        antes = calcular_resumen_cobro(self.orden, codigo_pais='MX')
        self.assertEqual(antes.total_a_cobrar, Decimal('1160.00'))
        self.assertEqual(antes.pagado, Decimal('0.00'))

        PagoOrden.objects.create(
            orden=self.orden,
            monto=Decimal('864.00'),
            tipo='diagnostico',
            metodo='efectivo',
            estado_validacion='no_aplica',
            registrado_por=self.empleado,
        )

        despues = calcular_resumen_cobro(self.orden, codigo_pais='MX')
        self.assertEqual(despues.pagado, Decimal('0.00'))
        self.assertEqual(despues.saldo, Decimal('1160.00'))

    def test_resumen_diagnostico_compara_contra_el_tarifario(self):
        """
        Contabilidad: el diagnóstico de un equipo de gama alta debe coincidir
        con la tarifa del perfil Alta Gama del cotizador.
        """
        with patch(
            'almacen.utils.parametros_cotizador.obtener_profit_config',
            return_value={'alta_gama': {'diagnostico': 864.0}},
        ):
            resumen = resumen_diagnostico(self.orden)
        self.assertEqual(resumen.gama, 'alta')
        self.assertEqual(resumen.tarifa_referencia, Decimal('864.00'))
        self.assertTrue(resumen.coincide_con_tarifario)

    def test_diagnostico_regalado_no_se_factura(self):
        """
        Borde: si el negocio descuenta la mano de obra al aceptar la
        cotización, el diagnóstico vale $0 y no hay PUE.
        """
        self.cotizacion.descontar_mano_obra = True
        self.cotizacion.save(update_fields=['descontar_mano_obra'])
        resumen = resumen_diagnostico(self.orden)
        self.assertEqual(resumen.monto, Decimal('0.00'))
        self.assertFalse(resumen.confirmado_100)

    def test_perfil_capturado_manda_sobre_la_gama(self):
        """
        Con perfil elegido, la referencia sale del perfil y NO de la gama.

        EXPLICACIÓN PARA PRINCIPIANTES:
        Este test protege la corrección de fondo. El equipo está marcado como
        gama alta, así que el camino viejo habría buscado la tarifa de Alta
        Gama ($864). Pero la orden dice que se cobró un diagnóstico Estándar,
        y ese dato es un hecho, no una deducción: debe ganar.
        """
        sembrar_tarifario()
        self.orden.perfil_diagnostico = 'estandar'
        self.orden.costo_mano_obra = Decimal('570.00')
        self.orden.save(update_fields=['perfil_diagnostico', 'costo_mano_obra'])
        self.cotizacion.costo_mano_obra = Decimal('570.00')
        self.cotizacion.save(update_fields=['costo_mano_obra'])

        resumen = resumen_diagnostico(self.orden)
        self.assertEqual(resumen.gama, 'alta')
        self.assertEqual(resumen.perfil, 'estandar')
        self.assertEqual(resumen.tarifa_referencia, Decimal('570.00'))
        self.assertTrue(resumen.coincide_con_tarifario)

    def test_sin_perfil_cae_a_la_deduccion_por_gama(self):
        """
        Respaldo: las órdenes viejas no tienen perfil y siguen comparándose
        contra la tarifa deducida de la gama del equipo.
        """
        sembrar_tarifario()
        self.assertEqual(self.orden.perfil_diagnostico, '')

        resumen = resumen_diagnostico(self.orden)
        self.assertEqual(resumen.perfil, '')
        self.assertEqual(resumen.tarifa_referencia, Decimal('864.00'))


class DiagnosticoCatalogoTest(BaseFacturacionTest):
    """
    El catálogo pone el precio y la factura lo desglosa sin IVA.

    Es el cierre del problema original: antes Recepción tecleaba $661 (precio
    con IVA) y el CFDI le sumaba otro 16% encima. Ahora se elige "Estándar",
    se guardan $570 sin IVA y la factura suma el IVA una sola vez: $661.20.
    """

    def setUp(self):
        sembrar_tarifario()
        self.factory = RequestFactory()
        self.sucursal = self._crear_sucursal('Satelite', 'SAT')
        self.empleado = Empleado.objects.create(
            nombre_completo='Cajero Catalogo',
            cargo='Recepcionista',
            area='FRONTDESK',
            email='cajero.catalogo@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
        )
        self.orden = self._crear_orden('OOW-13700', 'SN-CAT-13700', gama='baja')

    def test_tarifa_perfil_lee_el_tarifario_vigente(self):
        """Cada perfil devuelve su precio sin IVA; los sin cargo devuelven $0."""
        self.assertEqual(tarifa_perfil('estandar'), Decimal('570.00'))
        self.assertEqual(tarifa_perfil('express'), Decimal('774.00'))
        self.assertEqual(tarifa_perfil('alta_gama'), Decimal('864.00'))
        self.assertEqual(tarifa_perfil('server'), Decimal('1000.00'))
        self.assertEqual(tarifa_perfil('mostrador'), Decimal('0.00'))

    def test_tarifa_perfil_invalido_es_cero(self):
        """Una clave fuera del catálogo nunca inventa un precio."""
        self.assertEqual(tarifa_perfil('no_existe'), Decimal('0.00'))
        self.assertEqual(tarifa_perfil(''), Decimal('0.00'))

    def test_aplicar_perfil_sincroniza_orden_y_cotizacion(self):
        """
        Si ya hay cotización, el monto debe quedar igual en los dos lados.

        Si se desincronizan, el total que ve el cliente deja de cuadrar con
        el de la factura, que es justo el tipo de error que nadie detecta
        hasta que Contabilidad cierra el mes.
        """
        cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('0.00'),
        )
        resultado = aplicar_perfil_diagnostico(self.orden, 'alta_gama')

        self.orden.refresh_from_db()
        cotizacion.refresh_from_db()
        self.assertEqual(resultado.monto_nuevo, Decimal('864.00'))
        self.assertEqual(self.orden.costo_mano_obra, Decimal('864.00'))
        self.assertEqual(cotizacion.costo_mano_obra, Decimal('864.00'))

    def test_aplicar_perfil_desconocido_falla(self):
        """El catálogo es cerrado: una clave inventada levanta ValueError."""
        with self.assertRaises(ValueError):
            aplicar_perfil_diagnostico(self.orden, 'perfil_pirata')

    @override_settings(
        RATELIMIT_ENABLE=False,
        FACTURACION_WEB_API_KEY=API_KEY,
        FACTURACION_WEB_SECRET=SECRET,
        FACTURACION_WEB_TOKEN_TTL=3600,
        STORAGES=STORAGES_TEST,
    )
    def test_factura_pue_desglosa_570_mas_iva(self):
        """
        End to end: Estándar cobrado en efectivo → CFDI de $570 + $91.20.

        El total ($661.20) es exactamente lo que el cliente pagó en caja. Con
        el esquema anterior el mismo servicio habría facturado $766.99.
        """
        aplicar_perfil_diagnostico(self.orden, 'estandar')
        PagoOrden.objects.create(
            orden=self.orden,
            monto=Decimal('570.00'),
            tipo='diagnostico',
            metodo='efectivo',
            estado_validacion='no_aplica',
            registrado_por=self.empleado,
        )

        request = self.factory.post(
            reverse('facturacion_web:authenticate'),
            data='{"secret": "%s"}' % SECRET,
            content_type='application/json',
            HTTP_X_API_KEY=API_KEY,
        )
        token = json.loads(
            views_facturacion_demanda.authenticate_facturacion_web(request).content
        )['access_token']

        get_request = self.factory.get(
            reverse('facturacion_web:folio', args=['SAT13700-1']),
            HTTP_X_API_KEY=API_KEY,
            HTTP_AUTHORIZATION=f'Bearer {token}',
        )
        response = views_facturacion_demanda.folio_facturacion_web(
            get_request, 'SAT13700-1'
        )
        self.assertEqual(response.status_code, 200)

        datos = json.loads(response.content)
        self.assertEqual(datos['encabezado']['subtotal'], 570.0)
        self.assertEqual(datos['encabezado']['iva'], 91.2)
        self.assertEqual(datos['encabezado']['total'], 661.2)
        self.assertEqual(datos['encabezado']['metodo_pago'], 'PUE')
        self.assertEqual(datos['conceptos'][0]['precio'], 570.0)


class FacturacionDemandaPaisTest(TestCase):
    """CFDI solo México: otro país no debe armar venta."""

    def test_argentina_responde_400(self):
        with patch(
            'servicio_tecnico.services.facturacion_demanda.get_pais_actual',
            return_value={'codigo': 'AR'},
        ):
            with self.assertRaises(FacturacionDemandaError) as ctx:
                obtener_venta_para_facturar('SAT11902-1')
        self.assertEqual(ctx.exception.http_status, 400)
        self.assertIn('México', ctx.exception.razon)


@override_settings(
    RATELIMIT_ENABLE=False,
    FACTURACION_WEB_PORTAL_URL='http://201.149.21.30/facturador',
    STORAGES=STORAGES_TEST,
)
class AutofacturaSeguimientoTest(BaseFacturacionTest):
    """El cliente ve su webId en /seguimiento/<token>/, nunca los secretos."""

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = self._crear_sucursal('Satelite', 'SAT')
        self.empleado = Empleado.objects.create(
            nombre_completo='Seguimiento Factura',
            cargo='Recepcionista',
            area='FRONTDESK',
            email='seg.factura@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
        )
        self.orden = self._crear_orden('OOW-11902', 'SN-SEG-FAC-01')
        self.cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('500.00'),
            usuario_acepto=True,
        )
        componente = ComponenteEquipo.objects.create(
            nombre='Pantalla Seg Fac',
            tipo_equipo='laptop',
            activo=True,
        )
        PiezaCotizada.objects.create(
            cotizacion=self.cotizacion,
            componente=componente,
            cantidad=1,
            costo_unitario=Decimal('100.00'),
            precio_unitario_cliente=Decimal('200.00'),
            aceptada_por_cliente=True,
        )
        self.pago = PagoOrden.objects.create(
            orden=self.orden,
            monto=Decimal('500.00'),
            tipo='diagnostico',
            metodo='efectivo',
            estado_validacion='no_aplica',
            registrado_por=self.empleado,
        )
        self.token = secrets.token_urlsafe(32)
        EnlaceSeguimientoCliente.objects.create(orden=self.orden, token=self.token)

    def _get_seguimiento(self):
        """GET de la página pública sin pasar por Axes / middleware."""
        request = self.factory.get(
            reverse('seguimiento_orden_publico', args=[self.token]),
        )
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        return seguimiento_orden_cliente(request, self.token)

    def test_helper_entrega_web_id_y_url(self):
        """Feliz: el cliente recibe SAT11902-1 y el enlace al portal."""
        ctx = contexto_autofactura_seguimiento(self.orden)
        self.assertTrue(ctx['mostrar_autofactura'])
        self.assertFalse(ctx['factura_ya_emitida'])
        self.assertEqual(len(ctx['documentos']), 1)
        self.assertEqual(ctx['documentos'][0]['web_id'], 'SAT11902-1')
        self.assertEqual(
            ctx['url_autofactura'],
            'http://201.149.21.30/facturador?webId=SAT11902-1',
        )

    def test_helper_oculto_si_el_pago_no_esta_validado(self):
        """Regla nueva: transferencia sin conciliar no habilita el webId."""
        self.pago.metodo = 'transferencia'
        self.pago.estado_validacion = 'pendiente'
        self.pago.save(update_fields=['metodo', 'estado_validacion'])
        ctx = contexto_autofactura_seguimiento(self.orden)
        self.assertFalse(ctx['mostrar_autofactura'])

    def test_helper_oculto_si_no_hay_pagos(self):
        """Sin abono no hay nada que facturar."""
        PagoOrden.objects.filter(orden=self.orden).delete()
        ctx = contexto_autofactura_seguimiento(self.orden)
        self.assertFalse(ctx['mostrar_autofactura'])

    def test_helper_ya_emitida_no_abre_portal(self):
        """Si ya hay factura, se informa y no se manda a timbrar otra vez."""
        self.orden.factura_emitida = True
        self.orden.save(update_fields=['factura_emitida'])
        ctx = contexto_autofactura_seguimiento(self.orden)
        self.assertTrue(ctx['mostrar_autofactura'])
        self.assertTrue(ctx['factura_ya_emitida'])
        self.assertEqual(ctx['url_autofactura'], '')

    def test_pagina_muestra_web_id_sin_secretos(self):
        """Feliz HTTP: el HTML trae el webId y el botón; no la API Key."""
        response = self._get_seguimiento()
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Facturar ahora', html)
        self.assertIn('SAT11902-1', html)
        self.assertNotIn('FACTURACION_WEB_API_KEY', html)
        self.assertNotIn('X-API-KEY', html)

    def test_pagina_sin_boton_si_no_hay_documento(self):
        """Borde: sin pago validado no aparece el bloque de facturación."""
        PagoOrden.objects.filter(orden=self.orden).delete()
        response = self._get_seguimiento()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('Facturar ahora', response.content.decode('utf-8'))

    def test_pagina_ya_emitida_muestra_mensaje_sin_boton(self):
        """Si ya hay CFDI, se informa y no se reabre el portal."""
        self.orden.factura_emitida = True
        self.orden.save(update_fields=['factura_emitida'])
        response = self._get_seguimiento()
        self.assertEqual(response.status_code, 200)
        html = response.content.decode('utf-8')
        self.assertIn('Tu factura ya fue emitida', html)
        self.assertNotIn('Facturar ahora', html)
