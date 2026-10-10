"""
Ver una orden no autoriza a cambiarla.

EXPLICACIÓN PARA PRINCIPIANTES:
detalle_orden abre con view_ordenservicio. Estos tests comprueban que
un POST de cambio de estado exige change_ordenservicio, y que un
comentario exige add_historialorden. Quien solo consulta no escribe.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, TestCase
from django.urls import reverse

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, HistorialOrden, OrdenServicio
from servicio_tecnico.views_detalle_orden import detalle_orden


User = get_user_model()


def _permiso(modelo, codename: str) -> Permission:
    """
    Permission de Django para ese modelo.

    Args:
        modelo: clase del modelo.
        codename: por ejemplo 'change_ordenservicio'.

    Returns:
        Permission de la BD de test.
    """
    content_type = ContentType.objects.get_for_model(modelo)
    return Permission.objects.get(content_type=content_type, codename=codename)


class DetalleOrdenPermisoEscrituraTest(TestCase):
    """
    Objetivo: el dispatcher rechaza escrituras sin el permiso de esa acción.

    Efectos: crea sucursal, dos usuarios y una orden de diagnóstico.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.factory = RequestFactory()
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Permiso Escritura',
            ciudad='CDMX',
        )
        self.orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio='diagnostico',
            estado='diagnostico',
        )
        DetalleEquipo.objects.create(
            orden=self.orden,
            orden_cliente='OOW-PERM-01',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-PERM-01',
            falla_principal='No enciende',
        )
        self.url = reverse(
            'servicio_tecnico:detalle_orden',
            args=[self.orden.pk],
        )
        self.user_lectura = self._usuario(
            'lectura.orden@test.local',
            'Solo Lectura',
            [_permiso(OrdenServicio, 'view_ordenservicio')],
        )
        self.user_cambio = self._usuario(
            'cambio.orden@test.local',
            'Puede Cambiar',
            [
                _permiso(OrdenServicio, 'view_ordenservicio'),
                _permiso(OrdenServicio, 'change_ordenservicio'),
            ],
        )

    def _usuario(self, email: str, nombre: str, permisos: list) -> User:
        """
        User + Empleado con los permisos indicados, ya recargado.

        Args:
            email: username.
            nombre: nombre_completo.
            permisos: lista de Permission.

        Returns:
            User con has_perm al día.
        """
        user = User.objects.create_user(username=email, email=email, password='testpass123')
        Empleado.objects.create(
            nombre_completo=nombre,
            cargo='Técnico',
            area='Laboratorio',
            email=email,
            sucursal=self.sucursal,
            user=user,
            rol='tecnico',
            activo=True,
            contraseña_configurada=True,
        )
        user.user_permissions.add(*permisos)
        return User.objects.get(pk=user.pk)

    def _post(self, user, data: dict):
        """
        POST directo a detalle_orden (sin el middleware de país).

        Args:
            user: quién envía el formulario.
            data: campos, incluido form_type.

        Returns:
            HttpResponse.
        """
        request = self.factory.post(self.url, data=data)
        request.user = user
        request.session = {}
        request._messages = FallbackStorage(request)
        return detalle_orden(request, orden_id=self.orden.pk)

    def test_solo_lectura_no_cambia_el_estado(self):
        """Borde: view_ordenservicio no mueve la orden."""
        response = self._post(self.user_lectura, {
            'form_type': 'cambio_estado',
            'estado': 'reparacion',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('acceso-denegado', response.url)
        self.assertIn('change_ordenservicio', response.url)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'diagnostico')

    def test_con_change_si_cambia_el_estado(self):
        """Feliz: change_ordenservicio sí aplica el cambio."""
        response = self._post(self.user_cambio, {
            'form_type': 'cambio_estado',
            'estado': 'reparacion',
        })
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('acceso-denegado', response.url)
        self.orden.refresh_from_db()
        self.assertEqual(self.orden.estado, 'reparacion')

    def test_cambiar_orden_no_autoriza_el_comentario(self):
        """
        Borde: cada acción pide su permiso.

        change_ordenservicio no incluye add_historialorden.
        """
        response = self._post(self.user_cambio, {
            'form_type': 'comentario',
            'comentario': 'Nota que no debe guardarse',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('acceso-denegado', response.url)
        self.assertIn('add_historialorden', response.url)
        self.assertFalse(
            HistorialOrden.objects.filter(
                orden=self.orden,
                comentario='Nota que no debe guardarse',
            ).exists()
        )
