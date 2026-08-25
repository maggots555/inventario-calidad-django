"""
Integración: auto-llenar fecha_inicio_diagnostico al subir imágenes de ingreso.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Cuando el técnico sube fotos tipo "ingreso", la orden pasa a En Diagnóstico
y ahora también se llena "Inicio Diagnóstico" si estaba vacío.

Casos que validamos:
1) Feliz: orden normal + ingreso → estado diagnostico + fecha_inicio = hoy.
2) No sobrescribir: si ya había fecha, se conserva.
3) Venta Mostrador: no setea fecha de diagnóstico (va a reparación).
"""

from datetime import timedelta
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from PIL import Image

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, OrdenServicio
from servicio_tecnico.views_detalle_orden_multimedia import handle_subir_imagenes


User = get_user_model()


def _png_upload(nombre: str = 'ingreso_test.png') -> SimpleUploadedFile:
    """
    Objetivo: PNG mínimo válido para que PIL verify() del handler no falle.

    Args:
        nombre: Nombre del archivo simulado.

    Returns:
        SimpleUploadedFile listo para request.FILES.
    """
    buf = BytesIO()
    Image.new('RGB', (32, 32), color=(30, 90, 150)).save(buf, format='PNG')
    return SimpleUploadedFile(nombre, buf.getvalue(), content_type='image/png')


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class FechaInicioDiagnosticoAlSubirIngresoTest(TestCase):
    """
    Objetivo (negocio): al evidenciar ingreso, arranca el reloj de diagnóstico.

    Efectos: crea sucursal/usuario/orden; mockea IO de compresión de imagen.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Fecha Diagnóstico',
            ciudad='CDMX',
        )
        self.user = User.objects.create_user(
            username='user_fecha_diag_ingreso',
            password='testpass123',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Fecha Diagnóstico',
            cargo='Técnico',
            area='Laboratorio',
            email='fecha.diag.ingreso@test.local',
            sucursal=self.sucursal,
            user=self.user,
            rol='tecnico',
            contraseña_configurada=True,
        )

    def _crear_orden(self, tipo_servicio: str, estado: str) -> OrdenServicio:
        """
        Crea orden + detalle mínimo para el handler de imágenes.

        Args:
            tipo_servicio: Código de tipo (diagnostico, venta_mostrador, etc.).
            estado: Estado inicial de la orden.

        Returns:
            OrdenServicio persistida con DetalleEquipo.
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio=tipo_servicio,
            estado=estado,
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='OOW-FECHA-DIAG',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-FECHA-DIAG',
            email_cliente='cliente.fecha.diag@test.local',
            nombre_cliente='Cliente Fecha Diagnóstico',
            falla_principal='No enciende',
        )
        return orden

    def _post_ingreso(self, orden: OrdenServicio):
        """
        Simula POST de galería con una imagen tipo ingreso.

        Args:
            orden: OrdenServicio ya cargada.

        Returns:
            JsonResponse del handler.
        """
        request = self.factory.post(
            '/',
            data={
                'tipo': 'ingreso',
                'descripcion': 'Evidencia de ingreso test',
            },
        )
        request.user = self.user
        # EXPLICACIÓN: getlist('imagenes') lee de FILES; FileInput usa ese name.
        request.FILES['imagenes'] = _png_upload()
        return handle_subir_imagenes(request, orden, self.empleado)

    @patch(
        'servicio_tecnico.views_detalle_orden_multimedia.comprimir_y_guardar_imagen',
    )
    def test_ingreso_llena_fecha_inicio_y_pasa_a_diagnostico(self, mock_comprimir):
        """
        Feliz: orden en recepción + fotos ingreso → diagnostico + fecha hoy.
        """
        mock_img = MagicMock()
        mock_img.pk = 99
        mock_comprimir.return_value = mock_img

        orden = self._crear_orden(tipo_servicio='diagnostico', estado='recepcion')
        self.assertIsNone(orden.detalle_equipo.fecha_inicio_diagnostico)

        response = self._post_ingreso(orden)
        self.assertEqual(response.status_code, 200)

        orden.refresh_from_db()
        detalle = orden.detalle_equipo
        detalle.refresh_from_db()

        # Paso 1: estado automático
        self.assertEqual(orden.estado, 'diagnostico')
        # Paso 2: fecha de inicio = hoy (zona local)
        self.assertEqual(detalle.fecha_inicio_diagnostico, timezone.localdate())
        # Paso 3: fin sigue vacío (el técnico lo pone al terminar)
        self.assertIsNone(detalle.fecha_fin_diagnostico)

    @patch(
        'servicio_tecnico.views_detalle_orden_multimedia.comprimir_y_guardar_imagen',
    )
    def test_no_sobrescribe_fecha_inicio_existente(self, mock_comprimir):
        """
        Borde: si ya había fecha manual, una nueva carga de ingreso no la pisa.
        """
        mock_img = MagicMock()
        mock_img.pk = 100
        mock_comprimir.return_value = mock_img

        orden = self._crear_orden(tipo_servicio='diagnostico', estado='diagnostico')
        fecha_manual = timezone.localdate() - timedelta(days=3)
        detalle = orden.detalle_equipo
        detalle.fecha_inicio_diagnostico = fecha_manual
        detalle.save(update_fields=['fecha_inicio_diagnostico'])

        self._post_ingreso(orden)

        detalle.refresh_from_db()
        self.assertEqual(detalle.fecha_inicio_diagnostico, fecha_manual)

    @patch(
        'servicio_tecnico.views_detalle_orden_multimedia.comprimir_y_guardar_imagen',
    )
    def test_venta_mostrador_no_setea_fecha_diagnostico(self, mock_comprimir):
        """
        Venta Mostrador no pasa por diagnóstico: no debe llenar esas fechas.
        """
        mock_img = MagicMock()
        mock_img.pk = 101
        mock_comprimir.return_value = mock_img

        orden = self._crear_orden(
            tipo_servicio='venta_mostrador',
            estado='recepcion',
        )

        self._post_ingreso(orden)

        orden.refresh_from_db()
        detalle = orden.detalle_equipo
        detalle.refresh_from_db()

        self.assertEqual(orden.estado, 'reparacion')
        self.assertIsNone(detalle.fecha_inicio_diagnostico)
        self.assertIsNone(detalle.fecha_fin_diagnostico)
