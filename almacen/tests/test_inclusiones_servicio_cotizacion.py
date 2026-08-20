"""
Tests del catálogo de inclusiones de servicios en el PDF de cotización.

EXPLICACIÓN PARA PRINCIPIANTES:
--------------------------------
El PDF no inventa el texto de Solución Plata o Limpieza: lo arma un helper
en constants.py. Aquí comprobamos las reglas sin generar un PDF real:

- México + Limpieza → kit + nota de 6 meses
- Otro país → solo el nombre
- Solución Plata en MX sigue con sus bullets
- El kit suelto (kit_limpieza) no lleva texto extra
"""

from django.test import SimpleTestCase

from config.constants import formatear_descripcion_servicio_con_inclusiones


class InclusionesServicioCotizacionTest(SimpleTestCase):
    """Reglas unitarias del HTML de descripción que va al PDF."""

    def test_limpieza_mexico_incluye_kit_y_nota_seis_meses(self):
        """MX: Limpieza y Mantenimiento trae kit + recomendación cada 6 meses."""
        html = formatear_descripcion_servicio_con_inclusiones(
            nombre_display='Limpieza y Mantenimiento',
            tipo_servicio='limpieza',
            pais_codigo='MX',
        )

        self.assertIn('<b>Limpieza y Mantenimiento</b>', html)
        self.assertIn('Kit de limpieza', html)
        self.assertIn('cada 6 meses', html)
        self.assertIn('<i>', html)

    def test_limpieza_otro_pais_solo_nombre(self):
        """Fuera de MX no se enriquecen inclusiones ni notas."""
        html = formatear_descripcion_servicio_con_inclusiones(
            nombre_display='Limpieza y Mantenimiento',
            tipo_servicio='limpieza',
            pais_codigo='AR',
        )

        self.assertEqual(html, 'Limpieza y Mantenimiento')
        self.assertNotIn('Kit de limpieza', html)
        self.assertNotIn('cada 6 meses', html)

    def test_paquete_plata_mexico_conserva_bullets(self):
        """Solución Plata en MX sigue listando lo que incluye el paquete."""
        html = formatear_descripcion_servicio_con_inclusiones(
            nombre_display='Solución Plata',
            tipo_servicio='paquete_plata',
            pais_codigo='MX',
        )

        self.assertIn('<b>Solución Plata</b>', html)
        self.assertIn('SSD 1 TB', html)
        self.assertIn('Respaldo de información', html)
        self.assertNotIn('cada 6 meses', html)

    def test_kit_limpieza_suelto_sin_texto_extra(self):
        """El kit vendido aparte no hereda las inclusiones del servicio limpieza."""
        html = formatear_descripcion_servicio_con_inclusiones(
            nombre_display='Kit de Limpieza Profesional',
            tipo_servicio='kit_limpieza',
            pais_codigo='MX',
        )

        self.assertEqual(html, 'Kit de Limpieza Profesional')
        self.assertNotIn('cada 6 meses', html)
