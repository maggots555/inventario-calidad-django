"""
Casillas Dell / Lenovo del empleado.

EXPLICACIÓN PARA PRINCIPIANTES:
Esas casillas solo valen para el rol Dispatcher. Si el rol cambia a técnico
(u otro), al guardar deben quedar apagadas aunque vengan marcadas.
"""

from pathlib import Path

from django.conf import settings
from django.test import TestCase

from inventario.admin import EmpleadoAdmin
from inventario.forms import EmpleadoForm
from inventario.models import Empleado


class MarcasGarantiaDispatcherTest(TestCase):
    """
    Objetivo: el modelo y el formulario apagan Dell/Lenovo fuera de dispatcher.

    Efectos secundarios: crea filas de Empleado de prueba.
    """

    def test_dispatcher_conserva_las_casillas(self) -> None:
        """Caso feliz: un dispatcher puede atender Dell, Lenovo o las dos."""
        empleado = Empleado.objects.create(
            nombre_completo='Dani Dispatcher',
            cargo='Dispatcher',
            area='Operaciones',
            rol='dispatcher',
            atiende_garantias_dell=True,
            atiende_garantias_lenovo=True,
        )
        empleado.refresh_from_db()
        self.assertTrue(empleado.atiende_garantias_dell)
        self.assertTrue(empleado.atiende_garantias_lenovo)

    def test_otro_rol_apaga_casillas_al_guardar(self) -> None:
        """Borde: cambiar a técnico borra las dos marcas, también con update_fields."""
        empleado = Empleado.objects.create(
            nombre_completo='Teo Tecnico',
            cargo='Técnico',
            area='Laboratorio',
            rol='dispatcher',
            atiende_garantias_dell=True,
        )
        empleado.rol = 'tecnico'
        empleado.atiende_garantias_lenovo = True
        empleado.save(update_fields=['rol'])
        empleado.refresh_from_db()
        self.assertFalse(empleado.atiende_garantias_dell)
        self.assertFalse(empleado.atiende_garantias_lenovo)

    def test_formulario_apaga_casillas_si_no_es_dispatcher(self) -> None:
        """El formulario no guarda Dell/Lenovo cuando el rol enviado es técnico."""
        datos = {
            'nombre_completo': 'Rene Recepcion',
            'cargo': 'Recepcionista',
            'area': 'Recepción',
            'rol': 'tecnico',
            'activo': 'on',
            'mostrar_en_carga_trabajo': 'on',
            'atiende_garantias_dell': 'on',
            'atiende_garantias_lenovo': 'on',
        }
        form = EmpleadoForm(data=datos)
        self.assertTrue(form.is_valid(), form.errors)
        empleado = form.save()
        self.assertFalse(empleado.atiende_garantias_dell)
        self.assertFalse(empleado.atiende_garantias_lenovo)

    def test_plantilla_y_admin_cargan_el_js_compilado(self) -> None:
        """
        El formulario y el admin apuntan al JS que sale de TypeScript.

        No se renderiza la página completa: el almacenamiento de estáticos
        con manifiesto exige collectstatic y no hace falta para esta ruta.
        """
        plantilla = (
            Path(settings.BASE_DIR)
            / 'inventario/templates/inventario/form_empleado.html'
        )
        texto = plantilla.read_text(encoding='utf-8')
        self.assertIn("{% static 'js/empleado_marcas_garantia.js' %}", texto)
        self.assertNotIn('inventario/js/empleado_marcas_garantia.js', texto)
        self.assertEqual(EmpleadoAdmin.Media.js, ('js/empleado_marcas_garantia.js',))
