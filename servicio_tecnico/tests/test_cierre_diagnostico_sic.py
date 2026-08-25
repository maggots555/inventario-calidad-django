"""
Tests: auto-llenar fecha_fin_diagnostico al guardar Diagnóstico SIC.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
Al guardar un Diagnóstico SIC con texto, el helper debe:
1) Poner Fin Diagnóstico = hoy (si estaba vacío).
2) Pasar la orden a Equipo Diagnosticado la primera vez.
3) No pisar una fecha ya guardada.
4) Ignorar SIC vacío y Venta Mostrador.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from inventario.models import Empleado, Sucursal
from servicio_tecnico.models import DetalleEquipo, OrdenServicio
from servicio_tecnico.services.cierre_diagnostico import (
    aplicar_fecha_fin_al_guardar_diagnostico_sic,
)


class CierreDiagnosticoPorSICTest(TestCase):
    """
    Objetivo: validar el helper de cierre sin pasar por HTTP completo.

    Efectos: crea sucursal, empleado, orden y detalle mínimos.
    """

    databases = {'default', 'mexico'}

    def setUp(self):
        self.sucursal = Sucursal.objects.create(
            nombre='Sucursal Cierre Diagnóstico',
            ciudad='CDMX',
        )
        self.empleado = Empleado.objects.create(
            nombre_completo='Técnico Cierre Diagnóstico',
            cargo='Técnico',
            area='Laboratorio',
            email='cierre.diag@test.local',
            sucursal=self.sucursal,
            rol='tecnico',
            activo=True,
        )

    def _crear_orden(
        self,
        *,
        tipo_servicio: str = 'diagnostico',
        estado: str = 'diagnostico',
        diagnostico_sic: str = '',
        fecha_fin=None,
    ) -> OrdenServicio:
        """
        Crea orden + detalle con el Diagnóstico SIC/fechas indicados.

        Args:
            tipo_servicio: Código de tipo de servicio.
            estado: Estado inicial de la orden.
            diagnostico_sic: Texto del diagnóstico (puede ir vacío).
            fecha_fin: Fecha de fin ya existente, o None.

        Returns:
            OrdenServicio con DetalleEquipo asociado.
        """
        orden = OrdenServicio.objects.create(
            sucursal=self.sucursal,
            tipo_servicio=tipo_servicio,
            estado=estado,
            tecnico_asignado_actual=self.empleado,
        )
        DetalleEquipo.objects.create(
            orden=orden,
            orden_cliente='OOW-CIERRE-SIC',
            tipo_equipo='Laptop',
            marca='Dell',
            modelo='Latitude',
            numero_serie='SN-CIERRE-SIC',
            email_cliente='cliente.cierre@test.local',
            nombre_cliente='Cliente Cierre',
            falla_principal='No enciende',
            diagnostico_sic=diagnostico_sic,
            fecha_fin_diagnostico=fecha_fin,
        )
        return orden

    def test_sic_con_texto_llena_fecha_fin_y_cambia_estado(self):
        """
        Feliz: SIC no vacío + fecha_fin vacía → hoy + equipo_diagnosticado.
        """
        orden = self._crear_orden(
            estado='diagnostico',
            diagnostico_sic='Se revisó placa madre y fuente; falla en regulador.',
        )
        detalle = orden.detalle_equipo
        fecha_fin_anterior = detalle.fecha_fin_diagnostico

        resultado = aplicar_fecha_fin_al_guardar_diagnostico_sic(
            detalle,
            orden,
            self.empleado,
            fecha_fin_anterior=fecha_fin_anterior,
        )

        detalle.refresh_from_db()
        orden.refresh_from_db()

        self.assertTrue(resultado['fecha_fin_aplicada'])
        self.assertTrue(resultado['estado_cambiado'])
        self.assertEqual(detalle.fecha_fin_diagnostico, timezone.localdate())
        self.assertEqual(orden.estado, 'equipo_diagnosticado')

    def test_no_sobrescribe_fecha_fin_existente(self):
        """
        Borde: si ya había Fin Diagnóstico, no se pisa al reeditar el SIC.
        """
        fecha_manual = timezone.localdate() - timedelta(days=2)
        orden = self._crear_orden(
            estado='equipo_diagnosticado',
            diagnostico_sic='Diagnóstico previo ya cerrado.',
            fecha_fin=fecha_manual,
        )
        detalle = orden.detalle_equipo

        resultado = aplicar_fecha_fin_al_guardar_diagnostico_sic(
            detalle,
            orden,
            self.empleado,
            fecha_fin_anterior=fecha_manual,
        )

        detalle.refresh_from_db()
        orden.refresh_from_db()

        self.assertFalse(resultado['fecha_fin_aplicada'])
        self.assertFalse(resultado['estado_cambiado'])
        self.assertEqual(detalle.fecha_fin_diagnostico, fecha_manual)
        self.assertEqual(orden.estado, 'equipo_diagnosticado')

    def test_sic_vacio_no_setea_fecha(self):
        """
        Borde: SIC vacío o solo espacios → no cierra el diagnóstico.
        """
        orden = self._crear_orden(
            estado='diagnostico',
            diagnostico_sic='   ',
        )
        detalle = orden.detalle_equipo

        resultado = aplicar_fecha_fin_al_guardar_diagnostico_sic(
            detalle,
            orden,
            self.empleado,
            fecha_fin_anterior=None,
        )

        detalle.refresh_from_db()
        orden.refresh_from_db()

        self.assertFalse(resultado['fecha_fin_aplicada'])
        self.assertFalse(resultado['estado_cambiado'])
        self.assertIsNone(detalle.fecha_fin_diagnostico)
        self.assertEqual(orden.estado, 'diagnostico')

    def test_venta_mostrador_no_setea_fecha_ni_estado(self):
        """
        Venta Mostrador no usa el ciclo de diagnóstico clásico.
        """
        orden = self._crear_orden(
            tipo_servicio='venta_mostrador',
            estado='reparacion',
            diagnostico_sic='Texto que no debería cerrar diagnóstico en VM.',
        )
        detalle = orden.detalle_equipo

        resultado = aplicar_fecha_fin_al_guardar_diagnostico_sic(
            detalle,
            orden,
            self.empleado,
            fecha_fin_anterior=None,
        )

        detalle.refresh_from_db()
        orden.refresh_from_db()

        self.assertFalse(resultado['fecha_fin_aplicada'])
        self.assertFalse(resultado['estado_cambiado'])
        self.assertIsNone(detalle.fecha_fin_diagnostico)
        self.assertEqual(orden.estado, 'reparacion')

    def test_fecha_fin_manual_sin_sic_igual_cambia_estado(self):
        """
        Regresión: fecha_fin puesta a mano (sin auto SIC) sigue cerrando estado.
        """
        orden = self._crear_orden(
            estado='diagnostico',
            diagnostico_sic='',
        )
        detalle = orden.detalle_equipo
        # Simula que el formulario ya guardó la fecha a mano
        detalle.fecha_fin_diagnostico = timezone.localdate()
        detalle.save(update_fields=['fecha_fin_diagnostico'])

        resultado = aplicar_fecha_fin_al_guardar_diagnostico_sic(
            detalle,
            orden,
            self.empleado,
            fecha_fin_anterior=None,
        )

        orden.refresh_from_db()

        self.assertFalse(resultado['fecha_fin_aplicada'])
        self.assertTrue(resultado['estado_cambiado'])
        self.assertEqual(orden.estado, 'equipo_diagnosticado')
