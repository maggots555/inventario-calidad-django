"""
Tests del envío masivo de video rewind (botón Mandar Rewind).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No generamos video ni mandamos correo real. Celery se mockea
(_delay_chain_rewind): solo comprobamos QUIÉN entra al lote y que
se escribe historial para no duplicar.

Casos:
1) Humo: reexport + URL.
2) Feliz: gerencia encola finalizado + entregado reciente.
3) Bordes: fotos incompletas, email dummy, ya enviado, entregado viejo,
   no-gerencia, segundo POST no duplica, venta mostrador 3 tipos.
"""

from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.core.files.base import ContentFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import resolve, reverse
from django.utils import timezone
from PIL import Image

from inventario.models import Empleado, Sucursal
from servicio_tecnico import views as st_views
from servicio_tecnico import views_rewind
from servicio_tecnico.models import DetalleEquipo, HistorialOrden, ImagenOrden, OrdenServicio
from servicio_tecnico.services.rewind_egreso import (
    DIAS_ENTREGADO_REWIND_PENDIENTE,
    EMAIL_CLIENTE_DUMMY,
    destinatarios_cc_ingreso,
    listar_rewinds_pendientes,
)


User = get_user_model()

TIPOS_DIAGNOSTICO = ('ingreso', 'diagnostico', 'reparacion', 'egreso')
TIPOS_VM = ('ingreso', 'reparacion', 'egreso')


def _png_bytes() -> bytes:
    """PNG mínimo válido para ImageField (no hace falta una foto real)."""
    buf = BytesIO()
    Image.new('RGB', (8, 8), color=(20, 40, 80)).save(buf, format='PNG')
    return buf.getvalue()


def _request_con_usuario(factory: RequestFactory, user, path: str, method: str = 'post'):
    """
    Arma un request listo para llamar la vista (sesión + messages).

    Args:
        factory: RequestFactory de Django.
        user: usuario autenticado.
        path: ruta URL.
        method: 'post' o 'get'.

    Returns:
        HttpRequest con user, session y storage de messages.
    """
    request = factory.post(path) if method == 'post' else factory.get(path)
    request.user = user
    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    return request


class CompatibilidadRewindMasivoReexportTest(SimpleTestCase):
    """Humo: reexport + reverse/resolve sin tocar BD."""

    def test_reexport_y_url(self):
        self.assertIs(
            st_views.enviar_rewinds_pendientes,
            views_rewind.enviar_rewinds_pendientes,
        )
        self.assertEqual(
            st_views.enviar_rewinds_pendientes.__module__,
            'servicio_tecnico.views_rewind',
        )
        match = resolve(reverse('servicio_tecnico:enviar_rewinds_pendientes'))
        self.assertIs(match.func, views_rewind.enviar_rewinds_pendientes)


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class ListarRewindsPendientesTest(TestCase):
    """
    Objetivo: el service elige bien quién entra al lote.

    Efectos: crea sucursal, empleado, órdenes e imágenes PNG de prueba.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Rewind Bulk',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='tec_rewind_bulk',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Rewind Bulk',
            cargo='Técnico',
            area='Laboratorio',
            email='tec.rewind.bulk@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
        )
        self._folio = 0

    def _crear_orden(
        self,
        *,
        estado: str = 'finalizado',
        tipo_servicio: str = 'diagnostico',
        email: str = 'cliente.rewind@test.local',
        folio: str | None = None,
        fecha_entrega=None,
    ) -> OrdenServicio:
        """Crea orden + detalle. El folio único evita chocar números de serie."""
        self._folio += 1
        folio_final = folio or f'SIC-RW-{self._folio:03d}'
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio=tipo_servicio,
            estado=estado,
            tecnico_asignado_actual=self.empleado,
            fecha_entrega=fecha_entrega,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente=folio_final,
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie=f'SNRW{self._folio:04d}',
            email_cliente=email,
            nombre_cliente='Cliente Rewind',
            falla_principal='No enciende',
            gama='media',
        )
        orden.refresh_from_db()
        return orden

    def _agregar_fotos(self, orden: OrdenServicio, tipos: tuple[str, ...]) -> None:
        """Sube un PNG por tipo (ImagenOrden.imagen es obligatorio)."""
        for tipo in tipos:
            img = ImagenOrden(
                orden=orden,
                tipo=tipo,
                descripcion=f'foto {tipo}',
                subido_por=self.empleado,
            )
            img.imagen.save(
                f'{tipo}_{orden.pk}.png',
                ContentFile(_png_bytes()),
                save=True,
            )

    def test_feliz_finalizado_y_entregado_reciente(self):
        """Entran una finalizada y una entregada de hace pocos días."""
        finalizada = self._crear_orden(estado='finalizado')
        self._agregar_fotos(finalizada, TIPOS_DIAGNOSTICO)

        reciente = self._crear_orden(
            estado='entregado',
            fecha_entrega=timezone.now() - timedelta(days=5),
        )
        self._agregar_fotos(reciente, TIPOS_DIAGNOSTICO)

        pks = {o.pk for o in listar_rewinds_pendientes()}
        self.assertEqual(pks, {finalizada.pk, reciente.pk})

    def test_sin_fotos_completas_no_entra(self):
        """Diagnóstico con solo ingreso no alcanza para rewind."""
        orden = self._crear_orden()
        self._agregar_fotos(orden, ('ingreso',))
        pks = {o.pk for o in listar_rewinds_pendientes()}
        self.assertNotIn(orden.pk, pks)

    def test_email_dummy_no_entra(self):
        """cliente@ejemplo.com no es un destinatario real."""
        orden = self._crear_orden(email=EMAIL_CLIENTE_DUMMY)
        self._agregar_fotos(orden, TIPOS_DIAGNOSTICO)
        pks = {o.pk for o in listar_rewinds_pendientes()}
        self.assertNotIn(orden.pk, pks)

    def test_ya_enviado_no_entra(self):
        """Historial con 'video rewind' marca la orden como ya enviada."""
        orden = self._crear_orden()
        self._agregar_fotos(orden, TIPOS_DIAGNOSTICO)
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='email',
            comentario='Generación de video rewind al cliente iniciada — task_id: abc',
        )
        pks = {o.pk for o in listar_rewinds_pendientes()}
        self.assertNotIn(orden.pk, pks)

    def test_entregado_viejo_no_entra(self):
        """Entregada hace más de 30 días queda fuera (histórico)."""
        orden = self._crear_orden(
            estado='entregado',
            fecha_entrega=timezone.now()
            - timedelta(days=DIAS_ENTREGADO_REWIND_PENDIENTE + 1),
        )
        self._agregar_fotos(orden, TIPOS_DIAGNOSTICO)
        pks = {o.pk for o in listar_rewinds_pendientes()}
        self.assertNotIn(orden.pk, pks)

    def test_venta_mostrador_con_3_tipos_entra(self):
        """VM no pide foto de diagnóstico."""
        orden = self._crear_orden(
            tipo_servicio='venta_mostrador',
            estado='finalizado',
        )
        self._agregar_fotos(orden, TIPOS_VM)
        pks = {o.pk for o in listar_rewinds_pendientes()}
        self.assertIn(orden.pk, pks)

    def test_diagnostico_sin_foto_diagnostico_no_entra(self):
        """Los 3 tipos de VM NO bastan en una orden de diagnóstico."""
        orden = self._crear_orden(tipo_servicio='diagnostico')
        self._agregar_fotos(orden, TIPOS_VM)
        pks = {o.pk for o in listar_rewinds_pendientes()}
        self.assertNotIn(orden.pk, pks)

    def test_cc_se_leen_del_historial_de_ingreso(self):
        """Misma regla que el rewind individual: 'Copia a:' en el ingreso."""
        orden = self._crear_orden()
        HistorialOrden.objects.create(
            orden=orden,
            tipo_evento='email',
            comentario=(
                'imágenes de ingreso enviadas al cliente\n'
                'Copia a: copia1@test.local, copia2@test.local'
            ),
        )
        copias = destinatarios_cc_ingreso(orden)
        self.assertEqual(copias, ['copia1@test.local', 'copia2@test.local'])


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class EnviarRewindsPendientesVistaTest(TestCase):
    """POST de gerencia encola chains; no-gerencia y GET no disparan Celery."""

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.url = reverse('servicio_tecnico:enviar_rewinds_pendientes')
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Rewind Vista',
            ciudad='GDL',
        )
        self.user_gerencia = User.objects.create_user(
            username='gerente_rewind',
            password='testpass123',
            is_superuser=True,
            is_staff=True,
        )
        self.empleado_gerencia = Empleado.objects.create(
            nombre_completo='Gerente Rewind',
            cargo='Gerente',
            area='Dirección',
            email='gerente.rewind@test.local',
            sucursal=self.sucursal,
            user=self.user_gerencia,
            rol='gerente_general',
        )
        self.user_tecnico = User.objects.create_user(
            username='tec_rewind_vista',
            password='testpass123',
        )
        ct = ContentType.objects.get_for_model(OrdenServicio)
        self.user_tecnico.user_permissions.add(
            Permission.objects.get(content_type=ct, codename='change_ordenservicio'),
        )
        self.empleado_tec = Empleado.objects.create(
            nombre_completo='Técnico Vista Rewind',
            cargo='Técnico',
            area='Laboratorio',
            email='tec.rewind.vista@test.local',
            sucursal=self.sucursal,
            user=self.user_tecnico,
            rol='tecnico',
        )
        self._folio = 0

    def _crear_orden_elegible(self, *, estado='finalizado', fecha_entrega=None):
        self._folio += 1
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado=estado,
            tecnico_asignado_actual=self.empleado_tec,
            fecha_entrega=fecha_entrega,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente=f'SIC-RWV-{self._folio:03d}',
            tipo_equipo='Laptop',
            marca='HP',
            modelo='EliteBook',
            numero_serie=f'SNVW{self._folio:04d}',
            email_cliente='cliente.vista.rewind@test.local',
            nombre_cliente='Cliente Vista',
            falla_principal='Pantalla',
            gama='alta',
        )
        for tipo in TIPOS_DIAGNOSTICO:
            img = ImagenOrden(
                orden=orden,
                tipo=tipo,
                descripcion=f'foto {tipo}',
                subido_por=self.empleado_tec,
            )
            img.imagen.save(
                f'{tipo}_{orden.pk}.png',
                ContentFile(_png_bytes()),
                save=True,
            )
        return orden

    @patch('servicio_tecnico.services.rewind_egreso._delay_chain_rewind')
    def test_gerencia_encola_dos_pendientes(self, mock_delay):
        """Feliz: 1 finalizado + 1 entregado reciente → 2 chains."""
        mock_delay.return_value = MagicMock(id='task-rw-bulk')
        finalizada = self._crear_orden_elegible(estado='finalizado')
        entregada = self._crear_orden_elegible(
            estado='entregado',
            fecha_entrega=timezone.now() - timedelta(days=2),
        )

        request = _request_con_usuario(
            self.factory, self.user_gerencia, self.url, method='post',
        )
        response = views_rewind.enviar_rewinds_pendientes(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(mock_delay.call_count, 2)
        textos = [
            h.comentario
            for h in HistorialOrden.objects.filter(
                orden__in=[finalizada, entregada],
                tipo_evento='email',
            )
        ]
        self.assertEqual(
            sum('video rewind' in t for t in textos),
            2,
        )
        msgs = [m.message for m in get_messages(request)]
        self.assertTrue(any('Se encolaron 2' in m for m in msgs))

    @patch('servicio_tecnico.services.rewind_egreso._delay_chain_rewind')
    def test_no_gerencia_no_encola(self, mock_delay):
        """Técnico con change_ordenservicio no puede disparar el lote."""
        self._crear_orden_elegible()
        request = _request_con_usuario(
            self.factory, self.user_tecnico, self.url, method='post',
        )
        response = views_rewind.enviar_rewinds_pendientes(request)
        self.assertEqual(response.status_code, 302)
        mock_delay.assert_not_called()
        msgs = [m.message for m in get_messages(request)]
        self.assertTrue(any('Solo gerencia' in m for m in msgs))

    @patch('servicio_tecnico.services.rewind_egreso._delay_chain_rewind')
    def test_get_no_encola(self, mock_delay):
        """GET no dispara Celery (igual que Cerrar Finalizados)."""
        request = _request_con_usuario(
            self.factory, self.user_gerencia, self.url, method='get',
        )
        response = views_rewind.enviar_rewinds_pendientes(request)
        self.assertEqual(response.status_code, 302)
        mock_delay.assert_not_called()

    @patch('servicio_tecnico.services.rewind_egreso._delay_chain_rewind')
    def test_segundo_post_no_duplica(self, mock_delay):
        """El historial escrito al encolar saca la orden del siguiente lote."""
        mock_delay.return_value = MagicMock(id='task-rw-once')
        self._crear_orden_elegible()

        r1 = _request_con_usuario(
            self.factory, self.user_gerencia, self.url, method='post',
        )
        views_rewind.enviar_rewinds_pendientes(r1)
        self.assertEqual(mock_delay.call_count, 1)

        r2 = _request_con_usuario(
            self.factory, self.user_gerencia, self.url, method='post',
        )
        views_rewind.enviar_rewinds_pendientes(r2)
        self.assertEqual(mock_delay.call_count, 1)
        msgs = [m.message for m in get_messages(r2)]
        self.assertTrue(any('No hay rewind pendientes' in m for m in msgs))

    @patch('servicio_tecnico.services.rewind_egreso._delay_chain_rewind')
    def test_sin_pendientes_mensaje_info(self, mock_delay):
        """Lista vacía: info, cero chains."""
        request = _request_con_usuario(
            self.factory, self.user_gerencia, self.url, method='post',
        )
        views_rewind.enviar_rewinds_pendientes(request)
        mock_delay.assert_not_called()
        msgs = [m.message for m in get_messages(request)]
        self.assertTrue(any('No hay rewind pendientes' in m for m in msgs))
