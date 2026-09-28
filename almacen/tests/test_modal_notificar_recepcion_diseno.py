"""
Regresión visual del modal «Notificar a Recepción».

EXPLICACIÓN PARA PRINCIPIANTES:
El modal pasó a dos columnas, pero detalle_solicitud.ts sigue buscando
los mismos id y name para cambiar la plantilla y enviar el correo.
Este test lee el HTML (sin base de datos) y confirma que esos ganchos
siguen escritos.
"""

from pathlib import Path

from django.test import SimpleTestCase


_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / 'templates'
    / 'almacen'
    / 'cotizaciones'
    / 'detalle_solicitud.html'
)
_CSS = (
    Path(__file__).resolve().parents[2]
    / 'static'
    / 'css'
    / 'notificar_recepcion_modal.css'
)


class ModalNotificarRecepcionDisenoTest(SimpleTestCase):
    """
    Sin BD: el markup fuente conserva el contrato del formulario.
    """

    def test_modal_conserva_ganchos_del_envio(self):
        """
        Objetivo: el rediseño no borra lo que el TypeScript y el POST usan.

        Efectos: ninguno.
        """
        texto = _TEMPLATE.read_text(encoding='utf-8')

        for gancho in (
            'id="notificarFrontModal"',
            'id="notificarFrontModalLabel"',
            'id="formNotificarFront"',
            'id="btnNotificarFront"',
            'name="tipo_plantilla"',
            'id="plantilla_cotizacion_lista"',
            'id="plantilla_partes_no_disponibles"',
            'id="labelPlantillaCotizacionLista"',
            'id="labelPlantillaPnc"',
            'id="alertTipoPlantillaNotificar"',
            'id="tituloAlertTipoPlantilla"',
            'id="textoAlertTipoPlantilla"',
            'id="iconAlertTipoPlantilla"',
            'name="copia_empleados"',
            'id="emp_cot_{{ empleado.id }}"',
            'id="cot_emp_current_user"',
            'id="tituloResumenNotificar"',
            'id="ayudaResumenPnc"',
            'id="iconResumenNotificar"',
            'id="mensaje_personalizado"',
            'name="mensaje_personalizado"',
            'rec-modal-split',
            'order-1',
            'order-2',
        ):
            self.assertIn(gancho, texto, f'Falta en el modal: {gancho}')

    def test_css_verde_esta_enlazado(self):
        """
        Objetivo: la hoja nueva se carga en el detalle de la solicitud.

        Efectos: ninguno.
        """
        texto = _TEMPLATE.read_text(encoding='utf-8')
        self.assertIn('css/notificar_recepcion_modal.css', texto)
        self.assertTrue(_CSS.is_file())
        css = _CSS.read_text(encoding='utf-8')
        self.assertIn('#notificarFrontModal', css)
        self.assertIn('[data-bs-theme="dark"]', css)
