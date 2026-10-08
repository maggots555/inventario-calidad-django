"""
Tests de la copia (Cc) al empleado al enviar un formato digital.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
No envían correo. Solo comprueban la regla: si el empleado tiene
correo y no está ya en "Para", va en copia; si no, no se duplica.
"""

from django.test import SimpleTestCase

from servicio_tecnico.services.email_copia_empleado import copia_empleado_sesion


class CopiaEmpleadoSesionTest(SimpleTestCase):
    """Regla de Cc compartida por OOW, Garantía y Nota de venta."""

    def test_con_correo_distinto_va_en_copia(self):
        """Feliz: el empleado recibe copia y el cliente sigue en Para."""
        copia = copia_empleado_sesion(
            'front@sic.local',
            ['cliente@test.local'],
        )
        self.assertEqual(copia, ['front@sic.local'])

    def test_sin_correo_no_hay_copia(self):
        """Borde: empleado sin correo. El cliente igual puede recibir el PDF."""
        self.assertIsNone(copia_empleado_sesion('', ['cliente@test.local']))
        self.assertIsNone(copia_empleado_sesion('   ', ['cliente@test.local']))

    def test_si_ya_esta_en_para_no_se_repite(self):
        """Borde: el mismo buzón no va dos veces (mayúsculas no importan)."""
        copia = copia_empleado_sesion(
            'Front@SIC.local',
            ['cliente@test.local', 'front@sic.local'],
        )
        self.assertIsNone(copia)
