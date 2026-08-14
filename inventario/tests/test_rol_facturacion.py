"""
Tests del rol Facturación (consulta de órdenes, cotizaciones y dashboards).

EXPLICACIÓN PARA PRINCIPIANTES:
El sistema tiene dos capas: el campo Empleado.rol (etiqueta) y un Group
de Django (permisos reales). Este archivo comprueba que el rol nuevo
existe, se mapea al grupo "Facturación" y solo otorga permisos de ver.
"""

from django.contrib.auth.models import Group, Permission, User
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase

from almacen.models import SolicitudCotizacion
from inventario.models import Empleado
from inventario.utils import ROL_A_GRUPO, sincronizar_grupo_empleado
from servicio_tecnico.models import Cotizacion, OrdenServicio


def _permiso(modelo, codename: str) -> Permission:
    """
    Obtiene un Permission de Django por modelo y codename.

    Args:
        modelo: clase del modelo (ej. OrdenServicio)
        codename: nombre del permiso (ej. 'view_ordenservicio')

    Returns:
        Permission encontrado en la BD de test.
    """
    content_type = ContentType.objects.get_for_model(modelo)
    return Permission.objects.get(content_type=content_type, codename=codename)


class RolFacturacionMapeoTest(TestCase):
    """
    Objetivo: el choice y el diccionario ROL_A_GRUPO incluyen facturación.

    Efectos secundarios: ninguno (solo lee constantes).
    """

    def test_choice_facturacion_existe(self) -> None:
        """El formulario de empleados debe ofrecer el rol Facturación."""
        codigos = {codigo for codigo, _etiqueta in Empleado.ROL_CHOICES}
        self.assertIn(Empleado.ROL_FACTURACION, codigos)
        self.assertIn(('facturacion', 'Facturación'), Empleado.ROL_CHOICES)

    def test_mapa_rol_a_grupo_facturacion(self) -> None:
        """El puente rol → Group apunta a 'Facturación'."""
        self.assertEqual(ROL_A_GRUPO[Empleado.ROL_FACTURACION], 'Facturación')

    def test_todo_rol_choice_tiene_grupo(self) -> None:
        """
        Borde: si alguien agrega un ROL_CHOICES y olvida ROL_A_GRUPO,
        el empleado quedaría sin grupo al guardar.
        """
        keys_choices = {codigo for codigo, _etiqueta in Empleado.ROL_CHOICES}
        self.assertEqual(keys_choices, set(ROL_A_GRUPO.keys()))


class SincronizarGrupoFacturacionTest(TestCase):
    """
    Objetivo: al guardar un empleado de facturación, el User queda en ese grupo.

    Efectos secundarios: crea User, Group y Empleado de prueba.
    """

    def setUp(self) -> None:
        """Crea el grupo Facturación y un usuario sin grupos."""
        self.grupo = Group.objects.create(name='Facturación')
        self.user = User.objects.create_user(
            username='facturacion@test.local',
            email='facturacion@test.local',
            password='testpass123',
        )

    def test_sincronizar_asigna_grupo_facturacion(self) -> None:
        """Caso feliz: el signal/helper deja un solo grupo, Facturación."""
        # Otro grupo previo simula un cambio de rol (de técnico a facturación).
        grupo_tecnico = Group.objects.create(name='Técnico')
        self.user.groups.add(grupo_tecnico)

        empleado = Empleado.objects.create(
            nombre_completo='Paty Facturación',
            cargo='Facturación',
            area='Administración',
            email='facturacion@test.local',
            rol=Empleado.ROL_FACTURACION,
            user=self.user,
            activo=True,
        )

        # El signal post_save ya llamó a sincronizar; reforzamos el helper.
        sincronizar_grupo_empleado(empleado)

        nombres = set(empleado.user.groups.values_list('name', flat=True))
        self.assertEqual(nombres, {'Facturación'})


class PermisosSoloLecturaFacturacionTest(TestCase):
    """
    Objetivo: Facturación ve órdenes/cotizaciones/dashboard; no puede escribir.

    Efectos secundarios: crea Group, User, Empleado y asigna Permission.
    """

    def setUp(self) -> None:
        """Arma el grupo con el mismo paquete de solo lectura del plan."""
        self.grupo = Group.objects.create(name='Facturación')
        # Permisos de consulta (view) — no add/change/delete.
        self.grupo.permissions.set([
            _permiso(OrdenServicio, 'view_ordenservicio'),
            _permiso(OrdenServicio, 'view_dashboard_gerencial'),
            _permiso(Cotizacion, 'view_cotizacion'),
            _permiso(SolicitudCotizacion, 'view_solicitudcotizacion'),
        ])

        self.user = User.objects.create_user(
            username='lector.fact@test.local',
            email='lector.fact@test.local',
            password='testpass123',
        )
        empleado = Empleado.objects.create(
            nombre_completo='Leo Lector',
            cargo='Facturación',
            area='Administración',
            email='lector.fact@test.local',
            rol=Empleado.ROL_FACTURACION,
            user=self.user,
            activo=True,
        )
        sincronizar_grupo_empleado(empleado)
        # Django cachea permisos en el objeto User; recargar para ver el grupo.
        self.user = User.objects.get(pk=self.user.pk)

    def test_puede_ver_orden_cotizacion_y_dashboard(self) -> None:
        """Caso feliz: has_perm de consulta en ST, Almacén y dashboard."""
        self.assertTrue(self.user.has_perm('servicio_tecnico.view_ordenservicio'))
        self.assertTrue(self.user.has_perm('servicio_tecnico.view_cotizacion'))
        self.assertTrue(self.user.has_perm('almacen.view_solicitudcotizacion'))
        self.assertTrue(self.user.has_perm('servicio_tecnico.view_dashboard_gerencial'))

    def test_no_puede_crear_ni_editar_ni_borrar(self) -> None:
        """Borde: el rol es de consulta; no debe tener escritura."""
        self.assertFalse(self.user.has_perm('servicio_tecnico.add_ordenservicio'))
        self.assertFalse(self.user.has_perm('servicio_tecnico.change_ordenservicio'))
        self.assertFalse(self.user.has_perm('servicio_tecnico.delete_ordenservicio'))
        self.assertFalse(self.user.has_perm('servicio_tecnico.add_cotizacion'))
        self.assertFalse(self.user.has_perm('almacen.add_solicitudcotizacion'))
        self.assertFalse(self.user.has_perm('almacen.change_solicitudcotizacion'))
        self.assertFalse(self.user.has_perm('almacen.delete_solicitudcotizacion'))


class SetupGruposCreaFacturacionTest(TestCase):
    """
    Objetivo: el script de producción crea el grupo Facturación con el paquete correcto.

    Efectos secundarios: crea los 10 grupos de Django en la BD de test.
    """

    def test_script_asigna_consulta_y_dashboard_sin_escritura(self) -> None:
        """El setup real (no el test) debe dejar view + dashboard, sin add."""
        from scripts.setup_grupos_permisos import setup_grupos_y_permisos

        setup_grupos_y_permisos('default')

        grupo = Group.objects.get(name='Facturación')
        codenames = set(grupo.permissions.values_list('codename', flat=True))

        self.assertIn('view_ordenservicio', codenames)
        self.assertIn('view_cotizacion', codenames)
        self.assertIn('view_solicitudcotizacion', codenames)
        self.assertIn('view_dashboard_gerencial', codenames)
        # Escritura no debe colarse en este rol.
        self.assertNotIn('add_ordenservicio', codenames)
        self.assertNotIn('change_ordenservicio', codenames)
        self.assertNotIn('delete_ordenservicio', codenames)
        self.assertNotIn('add_solicitudcotizacion', codenames)
        self.assertEqual(Group.objects.count(), 10)
