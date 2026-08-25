"""
Tests: fechas de reparación automáticas (inicio y fin).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El reloj de reparación arranca en el primer hito:
- Piezas Recibidas (Almacén o cambio manual), diagnóstico o Venta Mostrador.
- Fotos de ingreso en VM si no hubo espera de piezas.
- Cambio manual a En Reparación si aún no hay fecha.

El fin se llena al subir fotos de reparación. Nunca se pisa una fecha previa.
"""

from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from almacen.utils.sincronizar_seguimiento_piezas import (
    _pasar_orden_a_piezas_recibidas_si_aplica,
)
from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, OrdenServicio, SeguimientoPieza
from servicio_tecnico.services.fechas_reparacion import (
    aplicar_fin_reparacion_si_vacia,
    aplicar_inicio_reparacion_si_vacia,
)
from servicio_tecnico.views_detalle_orden_estado import handle_cambio_estado
from servicio_tecnico.views_detalle_orden_multimedia import handle_subir_imagenes


User = get_user_model()


def _png_upload(nombre: str = 'evidencia.png') -> SimpleUploadedFile:
    """
    PNG mínimo válido para que PIL verify() del handler no falle.

    Args:
        nombre: Nombre del archivo simulado.

    Returns:
        SimpleUploadedFile listo para request.FILES.
    """
    buf = BytesIO()
    Image.new('RGB', (32, 32), color=(40, 100, 160)).save(buf, format='PNG')
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type='image/png')


class FechasReparacionHelperTest(TestCase):
    """
    Objetivo: el helper llena solo si está vacío.

    Efectos: sucursal, empleado, orden y detalle mínimos.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Fechas Reparación',
            ciudad='CDMX',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Fechas Reparación',
            cargo='Técnico',
            area='Laboratorio',
            email='fechas.rep@test.local',
            sucursal=self.sucursal,
            rol='tecnico',
            activo=True,
        )

    def _crear_orden(
        self,
        *,
        tipo_servicio: str = 'diagnostico',
        estado: str = 'esperando_piezas',
        fecha_inicio=None,
        fecha_fin=None,
    ) -> OrdenServicio:
        """
        Crea orden + detalle con fechas de reparación opcionales.

        Args:
            tipo_servicio: diagnostico o venta_mostrador.
            estado: Estado inicial.
            fecha_inicio: Fecha ya guardada, o None.
            fecha_fin: Fecha ya guardada, o None.

        Returns:
            OrdenServicio con DetalleEquipo.
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio=tipo_servicio,
            estado=estado,
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='OOW-FECHA-REP',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-FECHA-REP',
            email_cliente='cliente.fecha.rep@test.local',
            nombre_cliente='Cliente Fechas Rep',
            falla_principal='No enciende',
            fecha_inicio_reparacion=fecha_inicio,
            fecha_fin_reparacion=fecha_fin,
        )
        return orden

    def test_inicio_vacio_se_llena_con_hoy(self):
        """Feliz: sin fecha de inicio → hoy."""
        orden = self._crear_orden()
        resultado = aplicar_inicio_reparacion_si_vacia(
            orden,
            self.empleado,
            motivo='test',
        )
        orden.detalle_equipo.refresh_from_db()
        self.assertTrue(resultado['aplicada'])
        self.assertEqual(
            orden.detalle_equipo.fecha_inicio_reparacion,
            timezone.localdate(),
        )

    def test_inicio_existente_no_se_pisa(self):
        """Borde: fecha previa se conserva."""
        fecha_manual = timezone.localdate() - timedelta(days=4)
        orden = self._crear_orden(fecha_inicio=fecha_manual)
        resultado = aplicar_inicio_reparacion_si_vacia(orden, motivo='test')
        orden.detalle_equipo.refresh_from_db()
        self.assertFalse(resultado['aplicada'])
        self.assertEqual(
            orden.detalle_equipo.fecha_inicio_reparacion,
            fecha_manual,
        )

    def test_fin_vacio_se_llena_con_hoy(self):
        """Feliz: sin fecha de fin → hoy."""
        orden = self._crear_orden(estado='reparacion')
        resultado = aplicar_fin_reparacion_si_vacia(orden, motivo='test')
        orden.detalle_equipo.refresh_from_db()
        self.assertTrue(resultado['aplicada'])
        self.assertEqual(
            orden.detalle_equipo.fecha_fin_reparacion,
            timezone.localdate(),
        )

    def test_fin_existente_no_se_pisa(self):
        """Borde: fin previo se conserva."""
        fecha_manual = timezone.localdate() - timedelta(days=1)
        orden = self._crear_orden(fecha_fin=fecha_manual)
        resultado = aplicar_fin_reparacion_si_vacia(orden, motivo='test')
        orden.detalle_equipo.refresh_from_db()
        self.assertFalse(resultado['aplicada'])
        self.assertEqual(
            orden.detalle_equipo.fecha_fin_reparacion,
            fecha_manual,
        )


class FechasReparacionAlmacenSyncTest(TestCase):
    """
    Objetivo: Almacén al pasar a Piezas Recibidas llena el inicio (diag y VM).
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Sync Rep',
            ciudad='CDMX',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Sync Rep',
            cargo='Técnico',
            area='Laboratorio',
            email='sync.rep@test.local',
            sucursal=self.sucursal,
            rol='tecnico',
            activo=True,
        )

    def _orden_esperando_con_seguimiento_recibido(
        self,
        tipo_servicio: str,
    ) -> OrdenServicio:
        """
        Orden en esperando_piezas con un seguimiento ya recibido.

        Args:
            tipo_servicio: diagnostico o venta_mostrador.

        Returns:
            OrdenServicio lista para el sync de Piezas Recibidas.
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio=tipo_servicio,
            estado='esperando_piezas',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='FL-SYNC-REP',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie=f'SN-SYNC-{tipo_servicio}',
            email_cliente='cliente.sync.rep@test.local',
            nombre_cliente='Cliente Sync Rep',
            falla_principal='Cambio de pieza',
        )
        hoy = timezone.localdate()
        SeguimientoPieza.objects.create(
            orden=orden,
            proveedor='Proveedor Test',
            descripcion_piezas='SSD 1TB',
            fecha_entrega_estimada=hoy,
            estado='recibido',
            fecha_entrega_real=hoy,
        )
        return orden

    def test_sync_diagnostico_llena_inicio(self):
        """Última pieza (diagnóstico) → piezas_recibidas + inicio = hoy."""
        orden = self._orden_esperando_con_seguimiento_recibido('diagnostico')
        cambiado = _pasar_orden_a_piezas_recibidas_si_aplica(orden)
        self.assertTrue(cambiado)
        orden.refresh_from_db()
        orden.detalle_equipo.refresh_from_db()
        self.assertEqual(orden.estado, 'piezas_recibidas')
        self.assertEqual(
            orden.detalle_equipo.fecha_inicio_reparacion,
            timezone.localdate(),
        )

    def test_sync_venta_mostrador_llena_inicio(self):
        """Última pieza (VM) también arranca la reparación."""
        orden = self._orden_esperando_con_seguimiento_recibido('venta_mostrador')
        cambiado = _pasar_orden_a_piezas_recibidas_si_aplica(orden)
        self.assertTrue(cambiado)
        orden.refresh_from_db()
        orden.detalle_equipo.refresh_from_db()
        self.assertEqual(orden.estado, 'piezas_recibidas')
        self.assertEqual(
            orden.detalle_equipo.fecha_inicio_reparacion,
            timezone.localdate(),
        )


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class FechasReparacionImagenesTest(TestCase):
    """
    Objetivo: fotos de ingreso VM y fotos de reparación llenan fechas.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Img Rep',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_fechas_rep_img',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Img Rep',
            cargo='Técnico',
            area='Laboratorio',
            email='img.rep@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            contraseña_configurada=True,
        )

    def _crear_orden(self, tipo_servicio: str, estado: str) -> OrdenServicio:
        """Crea orden + detalle mínimo para el handler de imágenes."""
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio=tipo_servicio,
            estado=estado,
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='OOW-IMG-REP',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-IMG-REP',
            email_cliente='cliente.img.rep@test.local',
            nombre_cliente='Cliente Img Rep',
            falla_principal='No enciende',
        )
        return orden

    def _post_imagenes(self, orden: OrdenServicio, tipo: str):
        """POST de galería con una imagen del tipo indicado."""
        request = self.factory.post(
            '/',
            data={'tipo': tipo, 'descripcion': 'Evidencia test'},
        )
        request.user = self.user
        request.FILES['imagenes'] = _png_upload()
        return handle_subir_imagenes(request, orden, self.empleado)

    @patch(
        'servicio_tecnico.views_detalle_orden_multimedia.comprimir_y_guardar_imagen',
    )
    def test_vm_ingreso_sin_piezas_llena_inicio(self, mock_comprimir):
        """VM directa: fotos ingreso → En Reparación + inicio = hoy."""
        mock_comprimir.return_value = MagicMock(pk=1)
        orden = self._crear_orden('venta_mostrador', 'recepcion')
        response = self._post_imagenes(orden, 'ingreso')
        self.assertEqual(response.status_code, 200)
        orden.refresh_from_db()
        orden.detalle_equipo.refresh_from_db()
        self.assertEqual(orden.estado, 'reparacion')
        self.assertEqual(
            orden.detalle_equipo.fecha_inicio_reparacion,
            timezone.localdate(),
        )
        self.assertIsNone(orden.detalle_equipo.fecha_inicio_diagnostico)

    @patch(
        'servicio_tecnico.views_detalle_orden_multimedia.comprimir_y_guardar_imagen',
    )
    def test_vm_ingreso_no_pisa_inicio_de_piezas(self, mock_comprimir):
        """Si Almacén ya puso el inicio, las fotos de ingreso no lo cambian."""
        mock_comprimir.return_value = MagicMock(pk=2)
        fecha_piezas = timezone.localdate() - timedelta(days=2)
        orden = self._crear_orden('venta_mostrador', 'piezas_recibidas')
        detalle = orden.detalle_equipo
        detalle.fecha_inicio_reparacion = fecha_piezas
        detalle.save(update_fields=['fecha_inicio_reparacion'])

        self._post_imagenes(orden, 'ingreso')
        detalle.refresh_from_db()
        self.assertEqual(detalle.fecha_inicio_reparacion, fecha_piezas)

    @patch(
        'servicio_tecnico.views_detalle_orden_multimedia.comprimir_y_guardar_imagen',
    )
    def test_fotos_reparacion_llenan_fin_diagnostico(self, mock_comprimir):
        """Diagnóstico: fotos reparación → CC + fin = hoy."""
        mock_comprimir.return_value = MagicMock(pk=3)
        orden = self._crear_orden('diagnostico', 'reparacion')
        response = self._post_imagenes(orden, 'reparacion')
        self.assertEqual(response.status_code, 200)
        orden.refresh_from_db()
        orden.detalle_equipo.refresh_from_db()
        self.assertEqual(orden.estado, 'control_calidad')
        self.assertEqual(
            orden.detalle_equipo.fecha_fin_reparacion,
            timezone.localdate(),
        )

    @patch(
        'servicio_tecnico.views_detalle_orden_multimedia.comprimir_y_guardar_imagen',
    )
    def test_fotos_reparacion_llenan_fin_vm_y_no_pisan(self, mock_comprimir):
        """VM: primera carga llena fin; la segunda no lo pisa."""
        mock_comprimir.return_value = MagicMock(pk=4)
        orden = self._crear_orden('venta_mostrador', 'reparacion')
        self._post_imagenes(orden, 'reparacion')
        orden.detalle_equipo.refresh_from_db()
        fecha_fin = orden.detalle_equipo.fecha_fin_reparacion
        self.assertEqual(fecha_fin, timezone.localdate())

        mock_comprimir.return_value = MagicMock(pk=5)
        self._post_imagenes(orden, 'reparacion')
        orden.detalle_equipo.refresh_from_db()
        self.assertEqual(orden.detalle_equipo.fecha_fin_reparacion, fecha_fin)


class FechasReparacionCambioEstadoTest(TestCase):
    """
    Objetivo: cambio manual a En Reparación llena inicio si estaba vacío.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Estado Rep',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_fechas_rep_estado',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Estado Rep',
            cargo='Técnico',
            area='Laboratorio',
            email='estado.rep@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            contraseña_configurada=True,
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='equipo_diagnosticado',
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-ESTADO-REP',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-ESTADO-REP',
            email_cliente='cliente.estado.rep@test.local',
            nombre_cliente='Cliente Estado Rep',
            falla_principal='No enciende',
        )

    def test_cambio_manual_a_reparacion_llena_inicio(self):
        """Diagnóstico sin piezas: pasar a En Reparación arranca el reloj."""
        request = self.factory.post(
            '/',
            data={'estado': 'reparacion', 'comentario_cambio': ''},
        )
        request.user = self.user
        request.session = {}
        request._messages = FallbackStorage(request)

        response = handle_cambio_estado(request, self.orden, self.empleado)
        self.assertEqual(response.status_code, 302)

        self.orden.refresh_from_db()
        self.orden.detalle_equipo.refresh_from_db()
        self.assertEqual(self.orden.estado, 'reparacion')
        self.assertEqual(
            self.orden.detalle_equipo.fecha_inicio_reparacion,
            timezone.localdate(),
        )
