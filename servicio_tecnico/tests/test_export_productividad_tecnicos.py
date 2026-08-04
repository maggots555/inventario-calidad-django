"""
Tests de productividad técnicos (Excel export) — OOW vs FL.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Validamos las reglas del plan Separar OOW vs FL:
1) Reparación = solo diagnóstico + cot aceptada (no mete FL).
2) Upsell OOW = diagnóstico finalizado con VM.
3) VM pura FL = tipo_servicio venta_mostrador con VM; no cuenta como reparación.
4) El workbook tiene exactamente 5 hojas.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import (
    Cotizacion,
    DetalleEquipo,
    OrdenServicio,
    VentaMostrador,
)
from servicio_tecnico.services.productividad_tecnicos import (
    HOJAS_EXCEL,
    agregar_resumen_por_tecnico,
    generar_workbook_productividad_tecnicos,
    obtener_diagnosticos_realizados,
    obtener_reparaciones_productivas,
    obtener_upsell_oow,
    obtener_vm_pura_fl,
)


class ProductividadTecnicosServiceTest(TestCase):
    """Integración ligera: reglas OOW / upsell / FL."""

    databases = {'default', 'mexico'}

    def setUp(self):
        """Crea sucursal + técnico y rango de fechas."""
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Prod Técnicos',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='tec_prod_excel',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Productividad Excel',
            cargo='Técnico',
            area='Laboratorio',
            email='prod.excel@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            contraseña_configurada=True,
        )
        self.hoy = timezone.now()
        self.fecha_inicio = (self.hoy - timedelta(days=7)).date().isoformat()
        self.fecha_fin = (self.hoy + timedelta(days=1)).date().isoformat()
        self._contador = 0

    def _crear_orden(
        self,
        *,
        estado: str = 'finalizado',
        tipo_servicio: str = 'diagnostico',
        con_fecha_fin: bool = True,
        orden_cliente: str | None = None,
        diagnostico: str = '',
        fecha_fin_diagnostico: date | None = None,
    ) -> OrdenServicio:
        """
        Helper: orden mínima + detalle.

        Args:
            tipo_servicio: 'diagnostico' (OOW) o 'venta_mostrador' (FL).
        """
        self._contador += 1
        if orden_cliente:
            folio = orden_cliente
        elif tipo_servicio == 'venta_mostrador':
            folio = f'FL-PROD-{self._contador:03d}'
        else:
            folio = f'OOW-PROD-{self._contador:03d}'

        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio=tipo_servicio,
            estado=estado,
            tecnico_asignado_actual=self.empleado,
            costo_mano_obra=Decimal('0.00'),
            fecha_finalizacion=self.hoy if con_fecha_fin else None,
            fecha_ingreso=self.hoy - timedelta(days=2),
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente=folio,
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude Test',
            numero_serie=f'SN-PROD-{self._contador:03d}',
            email_cliente='cliente.prod@test.local',
            nombre_cliente='Cliente Prod',
            falla_principal='No enciende',
            gama='media',
            diagnostico_sic=diagnostico,
            fecha_fin_diagnostico=fecha_fin_diagnostico,
        )
        return orden

    def _folio_cliente(self, orden: OrdenServicio) -> str:
        return orden.detalle_equipo.orden_cliente

    def _service_tag(self, orden: OrdenServicio) -> str:
        return orden.detalle_equipo.numero_serie

    def test_oow_con_cot_aceptada_cuenta_reparacion(self):
        """OOW finalizada + cot aceptada → reparaciones OOW."""
        orden = self._crear_orden(estado='finalizado', tipo_servicio='diagnostico')
        Cotizacion.objects.create(
            orden=orden,
            usuario_acepto=True,
            costo_mano_obra=Decimal('200.00'),
        )

        filas = obtener_reparaciones_productivas(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        folio = self._folio_cliente(orden)
        self.assertIn(folio, [f['folio'] for f in filas])
        fila = next(f for f in filas if f['folio'] == folio)
        self.assertTrue(fila['cot_aceptada'])
        self.assertEqual(fila['service_tag'], self._service_tag(orden))
        self.assertFalse(fila['tiene_upsell_vm'])

    def test_oow_con_vm_es_upsell_no_reparacion_sin_cot(self):
        """OOW finalizada solo con VM (sin cot) → upsell; NO reparación."""
        orden = self._crear_orden(estado='entregado', tipo_servicio='diagnostico')
        VentaMostrador.objects.create(
            orden=orden,
            paquete='plata',
            costo_paquete=Decimal('100.00'),
            incluye_limpieza=True,
            costo_limpieza=Decimal('50.00'),
            incluye_reinstalacion_so=True,
            costo_reinstalacion=Decimal('80.00'),
        )

        folio = self._folio_cliente(orden)
        reparaciones = obtener_reparaciones_productivas(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        upsell = obtener_upsell_oow(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        fl = obtener_vm_pura_fl(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )

        self.assertFalse(any(f['folio'] == folio for f in reparaciones))
        self.assertTrue(any(f['folio'] == folio for f in upsell))
        self.assertFalse(any(f['folio'] == folio for f in fl))

        vm_fila = next(f for f in upsell if f['folio'] == folio)
        self.assertEqual(vm_fila['tipo_flujo'], 'upsell_oow')
        self.assertTrue(vm_fila['incluye_limpieza'])

        resumen = agregar_resumen_por_tecnico([], upsell, fl, [])
        self.assertEqual(resumen[0]['upsell_limpieza'], 1)
        self.assertEqual(resumen[0]['upsell_reinstalacion'], 1)
        self.assertEqual(resumen[0]['upsell_paquete_plata'], 1)
        self.assertEqual(resumen[0]['fl_conteo'], 0)
        self.assertEqual(resumen[0]['reparaciones_oow'], 0)

    def test_oow_con_cot_y_vm_aparece_en_reparacion_y_upsell(self):
        """OOW + cot aceptada + VM → reparación Y upsell."""
        orden = self._crear_orden(estado='finalizado', tipo_servicio='diagnostico')
        Cotizacion.objects.create(
            orden=orden,
            usuario_acepto=True,
            costo_mano_obra=Decimal('150.00'),
        )
        VentaMostrador.objects.create(
            orden=orden,
            paquete='ninguno',
            incluye_limpieza=True,
            costo_limpieza=Decimal('40.00'),
        )
        folio = self._folio_cliente(orden)

        reparaciones = obtener_reparaciones_productivas(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        upsell = obtener_upsell_oow(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        self.assertTrue(any(f['folio'] == folio for f in reparaciones))
        self.assertTrue(any(f['folio'] == folio for f in upsell))
        rep = next(f for f in reparaciones if f['folio'] == folio)
        self.assertTrue(rep['tiene_upsell_vm'])

    def test_fl_con_vm_solo_en_vm_pura_no_reparacion(self):
        """FL finalizada + VM → solo VM pura; nunca reparación ni upsell OOW."""
        orden = self._crear_orden(
            estado='finalizado',
            tipo_servicio='venta_mostrador',
        )
        VentaMostrador.objects.create(
            orden=orden,
            paquete='oro',
            costo_paquete=Decimal('200.00'),
            incluye_kit_limpieza=True,
            costo_kit=Decimal('30.00'),
        )
        folio = self._folio_cliente(orden)

        reparaciones = obtener_reparaciones_productivas(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        upsell = obtener_upsell_oow(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        fl = obtener_vm_pura_fl(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )

        self.assertFalse(any(f['folio'] == folio for f in reparaciones))
        self.assertFalse(any(f['folio'] == folio for f in upsell))
        self.assertTrue(any(f['folio'] == folio for f in fl))
        self.assertEqual(
            next(f for f in fl if f['folio'] == folio)['tipo_flujo'],
            'vm_pura_fl',
        )

        resumen = agregar_resumen_por_tecnico(reparaciones, upsell, fl, [])
        self.assertEqual(resumen[0]['fl_conteo'], 1)
        self.assertEqual(resumen[0]['fl_kit'], 1)
        self.assertEqual(resumen[0]['fl_paquete_oro'], 1)
        self.assertEqual(resumen[0]['upsell_conteo'], 0)
        self.assertEqual(resumen[0]['reparaciones_oow'], 0)

    def test_finalizada_sin_cot_no_cuenta_reparacion(self):
        """OOW finalizada sin cot aceptada → no reparación."""
        orden = self._crear_orden(estado='finalizado')
        Cotizacion.objects.create(
            orden=orden,
            usuario_acepto=None,
            costo_mano_obra=Decimal('100.00'),
        )
        filas = obtener_reparaciones_productivas(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        self.assertFalse(
            any(f['folio'] == self._folio_cliente(orden) for f in filas),
        )

    def test_en_reparacion_con_cot_aceptada_no_cuenta(self):
        """Aún en reparación → fuera aunque cot aceptada."""
        orden = self._crear_orden(estado='reparacion', con_fecha_fin=False)
        Cotizacion.objects.create(
            orden=orden,
            usuario_acepto=True,
            costo_mano_obra=Decimal('150.00'),
        )
        filas = obtener_reparaciones_productivas(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        self.assertFalse(
            any(f['folio'] == self._folio_cliente(orden) for f in filas),
        )

    def test_diagnostico_con_texto_aparece(self):
        """Diagnóstico SIC no vacío → hoja diagnósticos."""
        orden = self._crear_orden(
            estado='diagnostico',
            con_fecha_fin=False,
            diagnostico='Falla en board principal; requiere reballing BGA.',
            fecha_fin_diagnostico=self.hoy.date(),
        )
        filas = obtener_diagnosticos_realizados(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        folio = self._folio_cliente(orden)
        self.assertTrue(any(f['folio'] == folio for f in filas))
        fila = next(f for f in filas if f['folio'] == folio)
        self.assertIn('board', fila['extracto'].lower())
        self.assertEqual(fila['service_tag'], self._service_tag(orden))

    def test_workbook_tiene_cinco_hojas(self):
        """Workbook con datos tiene exactamente las 5 hojas del plan."""
        orden = self._crear_orden(estado='finalizado')
        Cotizacion.objects.create(
            orden=orden,
            usuario_acepto=True,
            costo_mano_obra=Decimal('80.00'),
        )
        self._crear_orden(
            estado='equipo_diagnosticado',
            con_fecha_fin=False,
            diagnostico='Pantalla rota y teclado con teclas muertas.',
            fecha_fin_diagnostico=self.hoy.date(),
        )

        wb = generar_workbook_productividad_tecnicos(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        self.assertIsNotNone(wb)
        self.assertEqual(tuple(wb.sheetnames), HOJAS_EXCEL)
        self.assertEqual(len(HOJAS_EXCEL), 5)

        resumen = agregar_resumen_por_tecnico(
            obtener_reparaciones_productivas(
                fecha_inicio=self.fecha_inicio,
                fecha_fin=self.fecha_fin,
            ),
            obtener_upsell_oow(
                fecha_inicio=self.fecha_inicio,
                fecha_fin=self.fecha_fin,
            ),
            obtener_vm_pura_fl(
                fecha_inicio=self.fecha_inicio,
                fecha_fin=self.fecha_fin,
            ),
            obtener_diagnosticos_realizados(
                fecha_inicio=self.fecha_inicio,
                fecha_fin=self.fecha_fin,
            ),
        )
        self.assertTrue(any(r['reparaciones_oow'] >= 1 for r in resumen))
        self.assertTrue(any(r['diagnosticos'] >= 1 for r in resumen))


class ProductividadTecnicosVistaTest(TestCase):
    """HTTP: descarga Excel o redirect si no hay datos."""

    databases = {'default', 'mexico'}

    def setUp(self):
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.backends.db import SessionStore
        from django.test import RequestFactory

        self.factory = RequestFactory()
        self.SessionStore = SessionStore
        self.FallbackStorage = FallbackStorage

        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Vista Prod',
            ciudad='GDL',
        )
        self.user = User.objects.create_user(
            username='gerencia_prod',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Gerente Prod Excel',
            cargo='Gerente',
            area='Administración',
            email='gerencia.prod@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            contraseña_configurada=True,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type=ct,
                codename='view_dashboard_gerencial',
            ),
        )
        self.url = reverse('servicio_tecnico:exportar_productividad_tecnicos')

    def _get(self, query: dict | None = None):
        from servicio_tecnico.views_export_productividad_tecnicos import (
            exportar_productividad_tecnicos,
        )

        request = self.factory.get(self.url, data=query or {})
        request.user = self.user
        request.session = self.SessionStore()
        request.session.create()
        request._messages = self.FallbackStorage(request)
        return exportar_productividad_tecnicos(request)

    def test_sin_datos_redirige_con_mensaje(self):
        """Sin filas → redirect al dashboard."""
        response = self._get({
            'fecha_inicio': '2099-01-01',
            'fecha_fin': '2099-01-31',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('dashboard', response.url)

    def test_con_datos_descarga_xlsx(self):
        """Con reparación OOW → attachment Excel."""
        hoy = timezone.now()
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='finalizado',
            tecnico_asignado_actual=self.empleado,
            costo_mano_obra=Decimal('0.00'),
            fecha_finalizacion=hoy,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='OOW-VISTA-PROD-01',
            tipo_equipo='Laptop',
            marca='HP',
            modelo='EliteBook',
            numero_serie='SN-VISTA-PROD-01',
            email_cliente='vista.prod@test.local',
            nombre_cliente='Cliente Vista',
            falla_principal='No carga',
            gama='alta',
        )
        Cotizacion.objects.create(
            orden=orden,
            usuario_acepto=True,
            costo_mano_obra=Decimal('300.00'),
        )

        response = self._get({
            'fecha_inicio': (hoy - timedelta(days=3)).date().isoformat(),
            'fecha_fin': (hoy + timedelta(days=1)).date().isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('spreadsheetml', response['Content-Type'])
        self.assertIn('Productividad_Tecnicos_', response['Content-Disposition'])
        self.assertTrue(len(response.content) > 100)
