"""
Tests de productividad técnicos (Excel export).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Validamos las reglas de negocio del plan:
1) Solo cuentan órdenes finalizadas/entregadas con cot aceptada o VM.
2) Órdenes sin cot/VM o aún en reparación no entran.
3) Diagnósticos con texto SIC sí aparecen.
4) El workbook tiene exactamente las 4 hojas acordadas.
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
    obtener_ventas_mostrador_productivas,
)


class ProductividadTecnicosServiceTest(TestCase):
    """
    Integración ligera contra BD: reglas de conteo del service.

    Objetivo: asegurar que el Excel no cuente órdenes “a medias”.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        """
        Crea sucursal + técnico y un rango de fechas de prueba.

        Efectos secundarios: registros en BD de test.
        """
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
        # Ventana: hoy ± margen (fecha_finalizacion / ingreso dentro del rango).
        self.hoy = timezone.now()
        self.fecha_inicio = (self.hoy - timedelta(days=7)).date().isoformat()
        self.fecha_fin = (self.hoy + timedelta(days=1)).date().isoformat()
        self._contador = 0

    def _crear_orden(
        self,
        *,
        estado: str = 'finalizado',
        con_fecha_fin: bool = True,
        orden_cliente: str | None = None,
        diagnostico: str = '',
        fecha_fin_diagnostico: date | None = None,
    ) -> OrdenServicio:
        """
        Helper: orden mínima + detalle de equipo.

        Args:
            estado: código de ESTADO_ORDEN_CHOICES.
            con_fecha_fin: si True, setea fecha_finalizacion = ahora.
            orden_cliente: folio cliente único.
            diagnostico: texto SIC (vacío = sin diagnóstico contable).
            fecha_fin_diagnostico: DateField opcional del detalle.

        Returns:
            OrdenServicio creada.
        """
        self._contador += 1
        folio = orden_cliente or f'OOW-PROD-{self._contador:03d}'
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
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

    def test_finalizada_con_cot_aceptada_cuenta_reparacion(self):
        """Feliz: finalizada + cotización aceptada → entra en reparaciones."""
        orden = self._crear_orden(estado='finalizado')
        Cotizacion.objects.create(
            orden=orden,
            usuario_acepto=True,
            costo_mano_obra=Decimal('200.00'),
        )

        filas = obtener_reparaciones_productivas(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        folios = [f['folio'] for f in filas]
        self.assertIn(orden.numero_orden_interno, folios)
        fila = next(f for f in filas if f['folio'] == orden.numero_orden_interno)
        self.assertTrue(fila['cot_aceptada'])

    def test_finalizada_solo_vm_cuenta_reparacion_y_vm(self):
        """Feliz: finalizada solo con VM → reparación + hoja VM."""
        orden = self._crear_orden(estado='entregado')
        VentaMostrador.objects.create(
            orden=orden,
            paquete='plata',
            costo_paquete=Decimal('100.00'),
            incluye_limpieza=True,
            costo_limpieza=Decimal('50.00'),
        )

        reparaciones = obtener_reparaciones_productivas(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        ventas = obtener_ventas_mostrador_productivas(
            fecha_inicio=self.fecha_inicio,
            fecha_fin=self.fecha_fin,
        )
        self.assertTrue(
            any(f['folio'] == orden.numero_orden_interno for f in reparaciones),
        )
        self.assertTrue(
            any(f['folio'] == orden.numero_orden_interno for f in ventas),
        )
        vm_fila = next(f for f in ventas if f['folio'] == orden.numero_orden_interno)
        self.assertTrue(vm_fila['incluye_limpieza'])
        self.assertEqual(vm_fila['paquete'], 'plata')

    def test_finalizada_sin_cot_ni_vm_no_cuenta_reparacion(self):
        """Borde: finalizada sin cot aceptada ni VM → no es reparación productiva."""
        orden = self._crear_orden(estado='finalizado')
        # Cotización pendiente (None) no debe contar.
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
            any(f['folio'] == orden.numero_orden_interno for f in filas),
        )

    def test_en_reparacion_con_cot_aceptada_no_cuenta(self):
        """Borde: aún en reparación aunque cot aceptada → fuera del reporte."""
        orden = self._crear_orden(
            estado='reparacion',
            con_fecha_fin=False,
        )
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
            any(f['folio'] == orden.numero_orden_interno for f in filas),
        )

    def test_diagnostico_con_texto_aparece(self):
        """Diagnóstico SIC no vacío con fecha_fin en período → hoja diagnósticos."""
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
        self.assertTrue(
            any(f['folio'] == orden.numero_orden_interno for f in filas),
        )
        fila = next(f for f in filas if f['folio'] == orden.numero_orden_interno)
        self.assertGreater(fila['longitud_texto'], 10)
        self.assertIn('board', fila['extracto'].lower())

    def test_workbook_tiene_cuatro_hojas(self):
        """Workbook con datos tiene exactamente las 4 hojas del plan."""
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

        resumen = agregar_resumen_por_tecnico(
            obtener_reparaciones_productivas(
                fecha_inicio=self.fecha_inicio,
                fecha_fin=self.fecha_fin,
            ),
            obtener_ventas_mostrador_productivas(
                fecha_inicio=self.fecha_inicio,
                fecha_fin=self.fecha_fin,
            ),
            obtener_diagnosticos_realizados(
                fecha_inicio=self.fecha_inicio,
                fecha_fin=self.fecha_fin,
            ),
        )
        self.assertTrue(any(r['reparaciones'] >= 1 for r in resumen))
        self.assertTrue(any(r['diagnosticos'] >= 1 for r in resumen))


class ProductividadTecnicosVistaTest(TestCase):
    """
    HTTP: descarga Excel o redirect si no hay datos.

    EXPLICACIÓN PARA PRINCIPIANTES:
    Usamos RequestFactory (no Client) para evitar PaisMiddleware, que enruta
    lecturas a la BD 'mexico' mientras setUp escribe en 'default'.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        """Usuario con permiso de dashboard gerencial + factory."""
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
        """
        Arma GET autenticado con session + messages hacia la vista export.

        Args:
            query: query string (filtros de fechas, etc.).

        Returns:
            HttpResponse de exportar_productividad_tecnicos.
        """
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
        """Sin filas → redirect al dashboard (no 500)."""
        response = self._get({
            'fecha_inicio': '2099-01-01',
            'fecha_fin': '2099-01-31',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('dashboard', response.url)

    def test_con_datos_descarga_xlsx(self):
        """Con reparación productiva → attachment Excel."""
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
        self.assertIn(
            'spreadsheetml',
            response['Content-Type'],
        )
        self.assertIn(
            'Productividad_Tecnicos_',
            response['Content-Disposition'],
        )
        self.assertTrue(len(response.content) > 100)
