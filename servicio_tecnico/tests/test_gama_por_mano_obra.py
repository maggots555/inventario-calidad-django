"""
Tests de cascada: gama del equipo según costo de mano de obra.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
1) resolver_gama_por_mano_obra: función pura (umbrales), sin BD.
2) aplicar_gama_por_mano_obra: actualiza DetalleEquipo + historial.
3) guardar_mano_obra vía detalle_orden: el técnico registra MO y la gama cambia.

Umbrales (constants):
  < 400 → baja | 400–799 → media | >= 800 → alta
Ejemplos del negocio: 661 → media, 1002 → alta.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, HistorialOrden, OrdenServicio
from servicio_tecnico.utils_gama import (
    aplicar_gama_por_mano_obra,
    etiqueta_gama,
    resolver_gama_por_mano_obra,
)
from servicio_tecnico.views import detalle_orden


User = get_user_model()


class ResolverGamaPorManoObraTest(SimpleTestCase):
    """
    Umbrales sin tocar la base de datos.

    EXPLICACIÓN: SimpleTestCase es más rápido porque no crea BD de prueba.
    """

    def test_ejemplos_negocio_661_media_y_1002_alta(self):
        """Casos que pidió el usuario: 661=media, 1002=alta."""
        self.assertEqual(resolver_gama_por_mano_obra(661), 'media')
        self.assertEqual(resolver_gama_por_mano_obra(Decimal('1002')), 'alta')

    def test_umbrales_limites(self):
        """Fronteras exactas de los umbrales."""
        self.assertEqual(resolver_gama_por_mano_obra(399.99), 'baja')
        self.assertEqual(resolver_gama_por_mano_obra(400), 'media')
        self.assertEqual(resolver_gama_por_mano_obra(799.99), 'media')
        self.assertEqual(resolver_gama_por_mano_obra(800), 'alta')

    def test_cero_o_vacio_no_define_gama(self):
        """MO no registrada → cascada deja el estimado por modelo."""
        self.assertIsNone(resolver_gama_por_mano_obra(0))
        self.assertIsNone(resolver_gama_por_mano_obra(Decimal('0.00')))
        self.assertIsNone(resolver_gama_por_mano_obra(None))
        self.assertIsNone(resolver_gama_por_mano_obra(''))

    def test_etiqueta_gama_legible(self):
        """Las etiquetas salen de GAMA_EQUIPO_CHOICES."""
        self.assertEqual(etiqueta_gama('alta'), 'Gama Alta')
        self.assertEqual(etiqueta_gama('media'), 'Gama Media')
        self.assertEqual(etiqueta_gama(None), 'Sin definir')


class AplicarGamaPorManoObraTest(TestCase):
    """
    Persiste el cambio de gama en DetalleEquipo e historial.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Gama MO',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='tec_gama_mo',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Gama MO',
            cargo='Técnico',
            area='Laboratorio',
            email='tec.gama.mo@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
        )
        # Gama inicial = estimado por modelo (p. ej. media)
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-GAMA-MO-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude 5520',
            numero_serie='SN-GAMA-MO-01',
            email_cliente='cliente.gama@test.local',
            nombre_cliente='Cliente Gama MO',
            falla_principal='No enciende',
            gama='media',
        )

    def test_aplica_alta_y_registra_historial(self):
        """$1002 debe subir la gama a alta y dejar rastro en historial."""
        resultado = aplicar_gama_por_mano_obra(
            self.orden,
            Decimal('1002.00'),
            usuario=self.empleado,
        )
        self.assertEqual(resultado, 'alta')
        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.detalle_equipo.gama, 'alta')

        hist = HistorialOrden.objects.filter(
            orden=self.orden,
            tipo_evento='sistema',
            comentario__icontains='Gama actualizada por mano de obra',
        )
        self.assertEqual(hist.count(), 1)
        self.assertIn('Gama Alta', hist.first().comentario)

    def test_mo_cero_no_cambia_gama(self):
        """Con MO=0 no se pisa el estimado por modelo."""
        resultado = aplicar_gama_por_mano_obra(
            self.orden,
            Decimal('0.00'),
            usuario=self.empleado,
        )
        self.assertIsNone(resultado)
        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.detalle_equipo.gama, 'media')

    def test_misma_gama_no_reescribe_ni_historial(self):
        """Si ya es media y MO=661, no crea evento de historial extra."""
        antes = HistorialOrden.objects.filter(orden=self.orden).count()
        resultado = aplicar_gama_por_mano_obra(
            self.orden,
            Decimal('661.00'),
            usuario=self.empleado,
        )
        self.assertIsNone(resultado)
        despues = HistorialOrden.objects.filter(orden=self.orden).count()
        self.assertEqual(antes, despues)


class GuardarManoObraActualizaGamaViewTest(TestCase):
    """
    Integración HTTP: form_type=guardar_mano_obra en detalle_orden.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Guardar MO Gama',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_guardar_mo_gama',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Usuario Guardar MO Gama',
            cargo='Técnico',
            area='Laboratorio',
            email='guardar.mo.gama@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        perm = Permission.objects.get(
            content_type=ct,
            codename='view_ordenservicio',
        )
        self.user.user_permissions.add(perm)

        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
            tecnico_asignado_actual=self.empleado,
            costo_mano_obra=Decimal('0.00'),
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-GUARDAR-MO-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Inspiron 15',
            numero_serie='SN-GUARDAR-MO-01',
            email_cliente='cliente.guardar@test.local',
            nombre_cliente='Cliente Guardar MO',
            falla_principal='Pantalla rota',
            gama='baja',  # estimado inicial por modelo
        )
        self.url = reverse(
            'servicio_tecnico:detalle_orden',
            args=[self.orden.pk],
        )

    def _post_guardar_mo(self, costo: str):
        """
        POST autenticado con soporte de messages (RequestFactory no lo trae solo).
        """
        request = self.factory.post(
            self.url,
            data={
                'form_type': 'guardar_mano_obra',
                'costo_mano_obra': costo,
            },
        )
        request.user = self.user
        # FallbackStorage: permite messages.success sin SessionMiddleware completo
        setattr(request, 'session', {})
        messages_storage = FallbackStorage(request)
        setattr(request, '_messages', messages_storage)
        return detalle_orden(request, orden_id=self.orden.pk)

    def test_guardar_661_pasa_a_gama_media(self):
        """Sin cotización: registrar $661 cambia baja → media."""
        response = self._post_guardar_mo('661.00')
        self.assertEqual(response.status_code, 302)

        self.orden.refresh_from_db()
        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.costo_mano_obra, Decimal('661.00'))
        self.assertEqual(self.orden.detalle_equipo.gama, 'media')

    def test_guardar_1002_pasa_a_gama_alta(self):
        """Sin cotización: registrar $1002 cambia a alta."""
        response = self._post_guardar_mo('1002.00')
        self.assertEqual(response.status_code, 302)

        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.detalle_equipo.gama, 'alta')
