"""
Integración: Resumen Financiero simplificado en detalle_orden.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El panel derecho de cotizaciones debe mostrar solo lo que paga el cliente
(piezas sin IVA y total con IVA). Los costos internos (empresa, margen,
total cotización interno) ya no deben aparecer ahí.

La edición de mano de obra se movió al panel izquierdo "Estado de la Cotización".
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from scorecard.models import ComponenteEquipo
from servicio_tecnico.models import (
    Cotizacion,
    DetalleEquipo,
    OrdenServicio,
    PiezaCotizada,
)
from servicio_tecnico.views import detalle_orden


User = get_user_model()


@override_settings(
    STORAGES={
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class ResumenFinancieroCotizacionRenderTest(TestCase):
    """
    GET a detalle_orden con cotización: valida el HTML del resumen simplificado.

    Efectos: crea datos de prueba en BD (TestCase los limpia al terminar).
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Resumen Financiero',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_resumen_financiero',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Resumen Financiero',
            cargo='Técnico',
            area='Laboratorio',
            email='resumen.financiero@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            contraseña_configurada=True,
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        self.user.user_permissions.add(
            Permission.objects.get(
                content_type=ct,
                codename='view_ordenservicio',
            ),
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='cotizacion',
            tecnico_asignado_actual=self.empleado,
            costo_mano_obra=Decimal('150.00'),
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-RESUMEN-FIN-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-RESUMEN-FIN-01',
            email_cliente='cliente.resumen.fin@test.local',
            nombre_cliente='Cliente Resumen Fin',
            falla_principal='No enciende',
            gama='baja',
        )
        self.componente_a = ComponenteEquipo.objects.create(
            nombre='Pantalla Resumen Fin',
            tipo_equipo='laptop',
            activo=True,
        )
        self.componente_b = ComponenteEquipo.objects.create(
            nombre='Batería Resumen Fin',
            tipo_equipo='laptop',
            activo=True,
        )
        self.url = reverse(
            'servicio_tecnico:detalle_orden',
            args=[self.orden.pk],
        )

    def _get_html(self) -> str:
        """GET autenticado a detalle_orden y devuelve el HTML renderizado."""
        request = self.factory.get(self.url)
        request.user = self.user
        setattr(request, 'session', {})
        setattr(request, '_messages', FallbackStorage(request))
        response = detalle_orden(request, orden_id=self.orden.pk)
        self.assertEqual(response.status_code, 200)
        return response.content.decode('utf-8')

    def _crear_cotizacion_pendiente(self) -> Cotizacion:
        """
        Cotización sin respuesta del cliente y dos piezas con precio al cliente.

        Returns:
            Cotizacion creada en BD.
        """
        cotizacion = Cotizacion.objects.create(
            orden=self.orden,
            costo_mano_obra=Decimal('150.00'),
            usuario_acepto=None,
        )
        PiezaCotizada.objects.create(
            cotizacion=cotizacion,
            componente=self.componente_a,
            cantidad=1,
            costo_unitario=Decimal('200.00'),
            precio_unitario_cliente=Decimal('500.00'),
        )
        PiezaCotizada.objects.create(
            cotizacion=cotizacion,
            componente=self.componente_b,
            cantidad=1,
            costo_unitario=Decimal('100.00'),
            precio_unitario_cliente=Decimal('300.00'),
        )
        return cotizacion

    def test_resumen_muestra_solo_cobro_cliente_y_form_mano_obra_izquierda(self):
        """
        Feliz: etiquetas nuevas visibles; totales internos y desglose eliminados.

        800 sin IVA + 128 IVA = 928 con IVA (México, estimado pendiente).
        """
        self._crear_cotizacion_pendiente()
        html = self._get_html()

        # Panel simplificado — lo que paga el cliente
        self.assertIn('Piezas cotizadas (sin IVA):', html)
        self.assertIn('IVA (16%):', html)
        self.assertIn('Total (con IVA):', html)
        self.assertIn('Estimado — pendiente decisión del cliente.', html)
        self.assertIn('$800.00', html)
        self.assertIn('$928.00', html)

        # Mano de obra movida al panel izquierdo
        self.assertIn('id="formEditarManoObra"', html)
        self.assertIn('Mano de Obra (costo interno):', html)
        self.assertIn(
            'Costo interno (diagnóstico/reparación). No se cobra otra vez al cliente.',
            html,
        )

        # Totales internos que ya no deben mostrarse en el resumen
        self.assertNotIn('Total Piezas Cotizadas (costo empresa):', html)
        self.assertNotIn('Margen estimado (piezas aceptadas, sin IVA):', html)
        self.assertNotIn('TOTAL COTIZACIÓN (costo interno):', html)
        self.assertNotIn('Desglose de Piezas', html)
        self.assertNotIn('TOTAL A COBRAR (piezas', html)

    def test_resumen_cotizacion_rechazada_muestra_mensaje_sin_totales(self):
        """Borde: si el cliente rechazó, aviso claro y sin filas de cobro."""
        cotizacion = self._crear_cotizacion_pendiente()
        cotizacion.usuario_acepto = False
        cotizacion.motivo_rechazo = 'precio_alto'
        cotizacion.save(update_fields=['usuario_acepto', 'motivo_rechazo'])

        html = self._get_html()

        self.assertIn('Cotización rechazada — no hay piezas a cobrar.', html)
        self.assertNotIn('Piezas cotizadas (sin IVA):', html)
        self.assertNotIn('Piezas aceptadas (sin IVA):', html)
