"""
Tests del filtro de AsignarResponsablesForm (detalle_orden).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
En detalle_orden hay dos selects de responsables:
- Técnico Asignado → solo rol='tecnico' activos
- Responsable de Seguimiento → solo recepcionista/dispatcher activos

Este test crea empleados con roles distintos y verifica quién entra
y quién queda fuera de cada queryset del formulario.
"""

from django.test import TestCase

from inventario.models import Empleado, Sucursal
from servicio_tecnico.forms import AsignarResponsablesForm


class AsignarResponsablesFormFiltroTest(TestCase):
    """
    Objetivo: asegurar que ambos selects filtren por Empleado.rol (no por cargo).

    Efectos secundarios: crea empleados de prueba en BD de test.
    """

    def setUp(self):
        """
        Crea una sucursal y empleados de varios roles (activos e inactivos).
        """
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Filtro Responsables',
            ciudad='CDMX',
            direccion='Calle Test 1',
            horario_atencion='Lun-Vie 9-18',
        )

        # Candidatos para responsable_seguimiento
        self.recepcionista = Empleado.objects.create(
            nombre_completo='Ana Recepcionista',
            cargo='Recepcionista',
            area='Recepción',
            email='ana.recep@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=True,
        )
        self.dispatcher = Empleado.objects.create(
            nombre_completo='Luis Dispatcher',
            cargo='Dispatcher',
            area='Logística',
            email='luis.dispatch@test.local',
            sucursal=self.sucursal,
            rol='dispatcher',
            activo=True,
        )

        # Técnico activo (sí en select de técnico; no en select de seguimiento)
        self.tecnico = Empleado.objects.create(
            nombre_completo='Pedro Técnico',
            cargo='Técnico Lab',  # cargo libre distinto a la cadena antigua
            area='Laboratorio',
            email='pedro.tec@test.local',
            sucursal=self.sucursal,
            rol='tecnico',
            activo=True,
        )
        # Técnico inactivo (no debe aparecer en ningún select)
        self.tecnico_inactivo = Empleado.objects.create(
            nombre_completo='Mario Técnico Baja',
            cargo='TECNICO DE LABORATORIO',
            area='Laboratorio',
            email='mario.tec@test.local',
            sucursal=self.sucursal,
            rol='tecnico',
            activo=False,
        )
        # Empleado con cargo "técnico" en texto pero otro rol (no debe salir como técnico)
        self.falso_tecnico_por_cargo = Empleado.objects.create(
            nombre_completo='Nora Solo Cargo',
            cargo='TECNICO DE LABORATORIO',
            area='Laboratorio',
            email='nora.cargo@test.local',
            sucursal=self.sucursal,
            rol='compras',
            activo=True,
        )
        self.compras = Empleado.objects.create(
            nombre_completo='Carla Compras',
            cargo='Compras',
            area='Almacén',
            email='carla.compras@test.local',
            sucursal=self.sucursal,
            rol='compras',
            activo=True,
        )
        self.recepcionista_inactiva = Empleado.objects.create(
            nombre_completo='Sofía Inactiva',
            cargo='Recepcionista',
            area='Recepción',
            email='sofia.inactiva@test.local',
            sucursal=self.sucursal,
            rol='recepcionista',
            activo=False,
        )

    def test_queryset_responsable_solo_recepcionista_y_dispatcher(self):
        """
        Objetivo: el select de seguimiento solo incluye roles permitidos y activos.
        """
        form = AsignarResponsablesForm()
        ids_en_lista = set(
            form.fields['responsable_seguimiento'].queryset.values_list('pk', flat=True)
        )

        self.assertIn(self.recepcionista.pk, ids_en_lista)
        self.assertIn(self.dispatcher.pk, ids_en_lista)

        self.assertNotIn(self.tecnico.pk, ids_en_lista)
        self.assertNotIn(self.compras.pk, ids_en_lista)
        self.assertNotIn(self.recepcionista_inactiva.pk, ids_en_lista)

        self.assertEqual(
            set(AsignarResponsablesForm.ROLES_RESPONSABLE_SEGUIMIENTO),
            {'recepcionista', 'dispatcher'},
        )

    def test_queryset_tecnico_solo_rol_tecnico(self):
        """
        Objetivo: el select de técnico filtra por rol='tecnico', no por string de cargo.

        Caso borde: alguien con cargo "TECNICO DE LABORATORIO" pero rol=compras
        NO debe aparecer; alguien con cargo libre pero rol=tecnico SÍ.
        """
        form = AsignarResponsablesForm()
        ids_en_lista = set(
            form.fields['tecnico_asignado_actual'].queryset.values_list('pk', flat=True)
        )

        # Feliz: rol técnico activo sí aparece (aunque el cargo no diga LABORATORIO)
        self.assertIn(self.tecnico.pk, ids_en_lista)

        # Bordes: inactivo, otros roles, o cargo engañoso sin rol técnico
        self.assertNotIn(self.tecnico_inactivo.pk, ids_en_lista)
        self.assertNotIn(self.falso_tecnico_por_cargo.pk, ids_en_lista)
        self.assertNotIn(self.recepcionista.pk, ids_en_lista)
        self.assertNotIn(self.dispatcher.pk, ids_en_lista)
        self.assertNotIn(self.compras.pk, ids_en_lista)

        self.assertEqual(AsignarResponsablesForm.ROL_TECNICO_ASIGNADO, 'tecnico')
