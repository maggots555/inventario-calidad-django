"""
Tests de cascada: gama del equipo según el diagnóstico cobrado.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Hay DOS cascadas conviviendo, y es a propósito:

A) LEGADO (por dinero) — órdenes viejas, cuando la mano de obra se tecleaba
   libre. Umbrales: < 400 → baja | 400–799 → media | >= 800 → alta.
   Se conserva porque esas órdenes ya existen en la base.

B) VIGENTE (por perfil) — el técnico elige el TIPO de diagnóstico y de ahí
   sale la gama. Estándar no decide entre baja y media (ambas pagan lo mismo),
   así que respeta lo que dijo el catálogo marca/modelo.

Qué cubre cada bloque:
1) resolver_gama_por_mano_obra: función pura del legado, sin BD.
2) aplicar_gama_por_mano_obra: legado, actualiza DetalleEquipo + historial.
3) gama_por_perfil: función pura de la cascada vigente.
4) guardar_mano_obra vía detalle_orden: el técnico elige perfil y la gama cambia.
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
from servicio_tecnico.services.diagnostico_catalogo import gama_por_perfil
from servicio_tecnico.tests.helpers_tarifario import sembrar_tarifario
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


class GamaPorPerfilTest(SimpleTestCase):
    """
    Cascada vigente: el tipo de diagnóstico decide la gama.

    Sin BD: gama_por_perfil es una función pura que solo consulta el mapa
    PERFIL_DIAGNOSTICO_GAMA de constants.
    """

    def test_alta_gama_fuerza_alta(self):
        """Un diagnóstico de Alta Gama sube el equipo a gama alta."""
        self.assertEqual(gama_por_perfil('alta_gama', 'baja'), 'alta')

    def test_server_fuerza_alta(self):
        """Server también es concluyente: gama alta."""
        self.assertEqual(gama_por_perfil('server', 'media'), 'alta')

    def test_express_fuerza_alta(self):
        """Express se considera gama alta por decisión del negocio."""
        self.assertEqual(gama_por_perfil('express', 'media'), 'alta')

    def test_estandar_respeta_baja(self):
        """
        Estándar cubre baja y media, así que no debe pisar una 'baja' válida.

        Si lo hiciera, perderíamos la información del catálogo marca/modelo,
        que es el único que sí distingue entre esas dos gamas.
        """
        self.assertIsNone(gama_por_perfil('estandar', 'baja'))

    def test_estandar_respeta_media(self):
        """Estándar sobre un equipo ya en media: nada que cambiar."""
        self.assertIsNone(gama_por_perfil('estandar', 'media'))

    def test_estandar_corrige_alta(self):
        """
        Si el equipo venía marcado 'alta' pero se cobró Estándar, baja a media.

        'alta' no está en las gamas compatibles de Estándar, así que el
        diagnóstico real corrige el estimado del catálogo.
        """
        self.assertEqual(gama_por_perfil('estandar', 'alta'), 'media')

    def test_estandar_sin_gama_previa_pone_media(self):
        """Sin estimado previo, Estándar deja 'media' como valor por defecto."""
        self.assertEqual(gama_por_perfil('estandar', ''), 'media')

    def test_mostrador_no_toca_gama(self):
        """Mostrador no cobra diagnóstico: no dice nada sobre la gama."""
        self.assertIsNone(gama_por_perfil('mostrador', 'baja'))

    def test_rep_nivel_componente_no_toca_gama(self):
        """Reparación nivel componente tampoco define gama."""
        self.assertIsNone(gama_por_perfil('rep_nivel_componente', 'media'))

    def test_perfil_desconocido_no_toca_gama(self):
        """Una clave inventada no debe mover nada."""
        self.assertIsNone(gama_por_perfil('inexistente', 'baja'))


class GuardarManoObraActualizaGamaViewTest(TestCase):
    """
    Integración HTTP: form_type=guardar_mano_obra en detalle_orden.

    Ahora el POST manda `perfil_diagnostico` (no un monto): el precio lo pone
    el tarifario. Sembramos ese tarifario en BD para que el test no dependa
    del .env de cada máquina.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        sembrar_tarifario()
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

    def _post_guardar_mo(self, perfil: str):
        """
        POST autenticado con soporte de messages (RequestFactory no lo trae solo).

        Args:
            perfil: clave del catálogo de diagnósticos ('estandar', 'alta_gama'…).
        """
        request = self.factory.post(
            self.url,
            data={
                'form_type': 'guardar_mano_obra',
                'perfil_diagnostico': perfil,
            },
        )
        request.user = self.user
        # FallbackStorage: permite messages.success sin SessionMiddleware completo
        setattr(request, 'session', {})
        messages_storage = FallbackStorage(request)
        setattr(request, '_messages', messages_storage)
        return detalle_orden(request, orden_id=self.orden.pk)

    def test_estandar_toma_tarifa_sin_iva_y_respeta_gama_baja(self):
        """
        Elegir Estándar cobra $570 sin IVA y deja la gama baja intacta.

        Este es el caso que antes salía mal: el técnico tecleaba $661 (el
        precio con IVA) y el equipo subía a 'media' por un umbral de dinero.
        """
        response = self._post_guardar_mo('estandar')
        self.assertEqual(response.status_code, 302)

        self.orden.refresh_from_db()
        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.perfil_diagnostico, 'estandar')
        self.assertEqual(self.orden.costo_mano_obra, Decimal('570.00'))
        self.assertEqual(self.orden.detalle_equipo.gama, 'baja')

    def test_alta_gama_cobra_tarifa_y_sube_a_alta(self):
        """Elegir Alta Gama cobra $864 sin IVA y sube la gama a alta."""
        response = self._post_guardar_mo('alta_gama')
        self.assertEqual(response.status_code, 302)

        self.orden.refresh_from_db()
        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.costo_mano_obra, Decimal('864.00'))
        self.assertEqual(self.orden.detalle_equipo.gama, 'alta')

    def test_express_sube_a_alta(self):
        """Express cobra $774 sin IVA y también deja el equipo en gama alta."""
        self._post_guardar_mo('express')

        self.orden.refresh_from_db()
        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.costo_mano_obra, Decimal('774.00'))
        self.assertEqual(self.orden.detalle_equipo.gama, 'alta')

    def test_monto_libre_ya_no_se_acepta(self):
        """
        Mandar un monto suelto no cambia nada: el catálogo es cerrado.

        Es la garantía de que nadie puede volver a inyectar un importe a mano
        (por ejemplo desde una herramienta externa o un POST manipulado).
        """
        request = self.factory.post(
            self.url,
            data={
                'form_type': 'guardar_mano_obra',
                'costo_mano_obra': '9999.00',
            },
        )
        request.user = self.user
        setattr(request, 'session', {})
        setattr(request, '_messages', FallbackStorage(request))
        detalle_orden(request, orden_id=self.orden.pk)

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.costo_mano_obra, Decimal('0.00'))
        self.assertEqual(self.orden.perfil_diagnostico, '')

    def test_perfil_inventado_no_cambia_la_orden(self):
        """Una clave fuera del catálogo se rechaza sin tocar la orden."""
        self._post_guardar_mo('perfil_pirata')

        self.orden.refresh_from_db()
        self.assertEqual(self.orden.costo_mano_obra, Decimal('0.00'))
        self.assertEqual(self.orden.perfil_diagnostico, '')

    def test_historial_registra_perfil_y_monto(self):
        """
        El historial debe decir QUÉ diagnóstico se cobró y por cuánto.

        Guardar ambos importa: si mañana Gerencia cambia la tarifa, el
        historial sigue probando cuánto se cobró ese día.
        """
        self._post_guardar_mo('alta_gama')

        evento = HistorialOrden.objects.filter(
            orden=self.orden,
            tipo_evento='cotizacion',
            comentario__icontains='Diagnóstico:',
        ).first()
        self.assertIsNotNone(evento)
        self.assertIn('Alta Gama', evento.comentario)
        self.assertIn('864.00', evento.comentario)
        self.assertIn('sin IVA', evento.comentario)
