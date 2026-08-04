"""
Tests del filtro de técnicos en SolicitudBajaForm (Almacén).

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Al pedir baja tipo Servicio Técnico, el select de técnico debe listar
solo empleados con rol='tecnico' activos — no por el texto del cargo.
"""

from django.test import TestCase

from inventario.models import Empleado, Sucursal
from almacen.forms import SolicitudBajaForm


class SolicitudBajaFormFiltroTecnicoTest(TestCase):
    """
    Objetivo: el queryset de tecnico_asignado usa Empleado.ROL_TECNICO.

    Efectos secundarios: crea empleados de prueba en BD de test.
    """

    def setUp(self):
        """Crea sucursal y empleados con roles distintos."""
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Filtro Baja Técnico',
            ciudad='CDMX',
            direccion='Calle Test Baja 1',
            horario_atencion='Lun-Vie 9-18',
        )

        # Sí debe aparecer: rol técnico aunque el cargo sea texto libre
        self.tecnico = Empleado.objects.create(
            nombre_completo='Juan Técnico OK',
            cargo='Técnico Lab Dell',
            area='Laboratorio',
            email='juan.tec@test.local',
            sucursal=self.sucursal,
            rol=Empleado.ROL_TECNICO,
            activo=True,
        )
        # No: cargo engañoso pero rol compras
        self.falso_por_cargo = Empleado.objects.create(
            nombre_completo='Nora Solo Cargo',
            cargo='TECNICO DE LABORATORIO',
            area='Laboratorio',
            email='nora.cargo@test.local',
            sucursal=self.sucursal,
            rol='compras',
            activo=True,
        )
        # No: técnico inactivo
        self.tecnico_inactivo = Empleado.objects.create(
            nombre_completo='Mario Baja',
            cargo='Técnico',
            area='Laboratorio',
            email='mario.baja@test.local',
            sucursal=self.sucursal,
            rol=Empleado.ROL_TECNICO,
            activo=False,
        )

    def test_queryset_tecnico_solo_rol_tecnico(self):
        """
        Objetivo: solo rol técnico activo entra al select de SolicitudBajaForm.
        """
        form = SolicitudBajaForm()
        ids_en_lista = set(
            form.fields['tecnico_asignado'].queryset.values_list('pk', flat=True)
        )

        self.assertIn(self.tecnico.pk, ids_en_lista)
        self.assertNotIn(self.falso_por_cargo.pk, ids_en_lista)
        self.assertNotIn(self.tecnico_inactivo.pk, ids_en_lista)
